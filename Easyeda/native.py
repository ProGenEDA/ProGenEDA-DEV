"""Native EasyEDA Pro SQLite project emitter."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from itertools import chain
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Iterable
import uuid

from .donor_source import DonorPacket, EasyedaDonorSource
from .geometry import (
    PlacedComponent,
    Point,
    Rect,
    RoutedNet,
    WireSpanIndex,
    _visibility_route,
    inflate,
    points_to_segments,
    rects_overlap,
    rotate_point,
    segment_hits_rect,
    simplify_points,
)
from .ir import Circuit


NATIVE_SCHEMA = "progen-easyeda-native-project/v1"


class NativeProjectError(RuntimeError):
    """A donor-native project cannot be emitted without unsupported guessing."""


@dataclass(frozen=True)
class TerminalInstance:
    net: str
    endpoint: str
    packet: DonorPacket
    x: float
    y: float
    rotation: int
    wire_points: tuple[Point, ...]


@dataclass(frozen=True)
class PcbResult:
    ready: bool
    reason: str
    document_data: str | None
    component_count: int
    track_count: int
    placements: dict[str, tuple[float, float]]
    pad_points: dict[str, Point]
    variations: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class NativeWriteResult:
    project_path: Path
    schematic_document_uuid: str
    pcb_document_uuid: str | None
    terminal_instances: tuple[TerminalInstance, ...]
    pcb: PcbResult
    donor_manifest: dict[str, Any]


class _Ids:
    def __init__(self) -> None:
        self.value = 0

    def next(self, prefix: str = "e") -> str:
        self.value += 1
        return f"{prefix}{self.value}"


def _record(row: list[Any]) -> str:
    return json.dumps(row, ensure_ascii=False, separators=(",", ":"))


def _records(text: str) -> list[list[Any]]:
    result: list[list[Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, list) and value:
            result.append(value)
    return result


def _base_records(template_path: Path, doc_type: int) -> list[list[Any]]:
    with sqlite3.connect(template_path) as connection:
        row = connection.execute(
            "SELECT dataStr FROM documents WHERE docType = ? ORDER BY length(dataStr) DESC LIMIT 1",
            (doc_type,),
        ).fetchone()
    if row is None:
        raise NativeProjectError(f"Donor template contains no document type {doc_type}.")
    return _records(str(row[0]))


def _schematic_prelude(template_path: Path) -> list[list[Any]]:
    source = _base_records(template_path, 1)
    prelude: list[list[Any]] = []
    seen_styles: set[str] = set()
    for row in source:
        if row[0] in {"DOCTYPE", "HEAD"}:
            prelude.append(row)
        elif row[0] in {"LINESTYLE", "FONTSTYLE"}:
            identifier = str(row[1])
            if identifier not in seen_styles:
                prelude.append(row)
                seen_styles.add(identifier)
        if len(prelude) >= 14:
            break
    if not prelude or prelude[0][0] != "DOCTYPE":
        raise NativeProjectError("Donor schematic has no native document prelude.")
    return prelude


def _pcb_prelude(template_path: Path) -> list[list[Any]]:
    source = _base_records(template_path, 3)
    prelude: list[list[Any]] = []
    for row in source:
        if row[0] == "NET":
            break
        if row[0] in {"DOCTYPE", "CANVAS", "LAYER"}:
            prelude.append(row)
    if not prelude or prelude[0][0] != "DOCTYPE":
        raise NativeProjectError("Donor PCB has no native document prelude.")
    return prelude


def _style(prelude: Iterable[list[Any]], kind: str, fallback: str) -> str:
    for row in prelude:
        if row[0] == kind and len(row) > 1:
            return str(row[1])
    return fallback


def _endpoint_map(placed: tuple[PlacedComponent, ...]) -> dict[str, tuple[PlacedComponent, str, Point]]:
    result: dict[str, tuple[PlacedComponent, str, Point]] = {}
    for item in placed:
        for requested, point in item.pins.items():
            result[f"{item.component.reference}.{requested}"] = (item, requested, point)
    return result


def _terminal_orientation(item: PlacedComponent, point: Point) -> tuple[str, int, Point]:
    left, top, right, bottom = item.body
    outside = {
        "left": left - point[0],
        "right": point[0] - right,
        "top": top - point[1],
        "bottom": point[1] - bottom,
    }
    outside = {
        side: amount
        for side, amount in outside.items()
        if amount > 0
    }
    distances = {
        "left": abs(point[0] - left),
        "right": abs(point[0] - right),
        "top": abs(point[1] - top),
        "bottom": abs(point[1] - bottom),
    }
    side = max(outside, key=outside.get) if outside else min(distances, key=distances.get)
    if side == "left":
        return "in", 0, (min(point[0], left) - 50.0, point[1])
    if side == "right":
        return "out", 0, (max(point[0], right) + 50.0, point[1])
    if side == "top":
        return "out", 270, (point[0], min(point[1], top) - 50.0)
    return "out", 90, (point[0], max(point[1], bottom) + 50.0)


def _build_terminals(
    source: EasyedaDonorSource,
    routed: tuple[RoutedNet, ...],
    placed: tuple[PlacedComponent, ...],
) -> tuple[TerminalInstance, ...]:
    endpoints = _endpoint_map(placed)
    packets: dict[str, DonorPacket] = {}
    result: list[TerminalInstance] = []
    component_obstacles: list[Rect] = [inflate(item.body, 8.0) for item in placed]
    terminal_rects: list[Rect] = []
    terminal_wires: list[tuple[str, Point, Point]] = []
    pin_keepouts = {
        endpoint: (point[0] - 5.0, point[1] - 5.0, point[0] + 5.0, point[1] + 5.0)
        for endpoint, (_, _, point) in endpoints.items()
    }
    route_segments = [
        (net.name, start, end)
        for net in routed
        for start, end in net.segments
    ]
    wire_spans = WireSpanIndex()
    for route_net, start, end in route_segments:
        wire_spans.add(route_net, start, end)
    component_envelope = (
        min(rect[0] for rect in component_obstacles),
        min(rect[1] for rect in component_obstacles),
        max(rect[2] for rect in component_obstacles),
        max(rect[3] for rect in component_obstacles),
    )
    component_pin_envelopes: dict[str, Rect] = {}
    for item, body in zip(placed, component_obstacles):
        related = [
            keepout
            for endpoint, keepout in pin_keepouts.items()
            if endpoint.startswith(f"{item.component.reference}.")
        ]
        component_pin_envelopes[item.component.reference] = (
            min([body[0], *(rect[0] for rect in related)]),
            min([body[1], *(rect[1] for rect in related)]),
            max([body[2], *(rect[2] for rect in related)]),
            max([body[3], *(rect[3] for rect in related)]),
        )

    def terminal_rect(packet: DonorPacket, point: Point, rotation: int) -> Rect:
        body_left, body_top, body_right, body_bottom = packet.body_bbox
        local = [
            rotate_point((body_left, body_top), rotation),
            rotate_point((body_right, body_top), rotation),
            rotate_point((body_right, body_bottom), rotation),
            rotate_point((body_left, body_bottom), rotation),
        ]
        return (
            min(point[0] + value[0] for value in local),
            min(point[1] + value[1] for value in local),
            max(point[0] + value[0] for value in local),
            max(point[1] + value[1] for value in local),
        )

    def placement_candidates(
        point: Point,
        target: Point,
        rotation: int,
    ) -> Iterable[tuple[Point, tuple[Point, ...]]]:
        horizontal = rotation in {0, 180}
        outward_sign = (
            1.0
            if (horizontal and target[0] >= point[0])
            or (not horizontal and target[1] >= point[1])
            else -1.0
        )
        for shift in (
            12.0,
            -12.0,
            18.0,
            -18.0,
            24.0,
            -24.0,
            36.0,
            -36.0,
            48.0,
            -48.0,
            60.0,
            -60.0,
            72.0,
            -72.0,
            96.0,
            -96.0,
            120.0,
            -120.0,
            144.0,
            -144.0,
            180.0,
            -180.0,
            216.0,
            -216.0,
            240.0,
            -240.0,
        ):
            for distance in (
                32.0,
                40.0,
                48.0,
                56.0,
                72.0,
                88.0,
                104.0,
                120.0,
                152.0,
                184.0,
                216.0,
                248.0,
            ):
                if horizontal:
                    pivot = (point[0] + 8.0 * outward_sign, point[1])
                    candidate = (
                        point[0] + distance * outward_sign,
                        point[1] + shift,
                    )
                    points = (
                        point,
                        pivot,
                        (pivot[0], candidate[1]),
                        candidate,
                    )
                else:
                    pivot = (point[0], point[1] + 8.0 * outward_sign)
                    candidate = (
                        point[0] + shift,
                        point[1] + distance * outward_sign,
                    )
                    points = (
                        point,
                        pivot,
                        (candidate[0], pivot[1]),
                        candidate,
                    )
                yield candidate, points
        for distance in (24.0, 32.0, 40.0, 48.0):
            candidate = (
                (point[0] + distance * outward_sign, point[1])
                if horizontal
                else (point[0], point[1] + distance * outward_sign)
            )
            yield candidate, (point, candidate)
        for radial_step in range(80):
            radial = radial_step * 30.0 * outward_sign
            if horizontal:
                candidate = (target[0] + radial, target[1])
                escape = (
                    candidate[0] - outward_sign * 16.0,
                    point[1],
                )
                points = (point, escape, (escape[0], candidate[1]), candidate)
            else:
                candidate = (target[0], target[1] + radial)
                escape = (
                    point[0],
                    candidate[1] - outward_sign * 16.0,
                )
                points = (point, escape, (candidate[0], escape[1]), candidate)
            yield candidate, points
        for shift_step in range(1, 41):
            for shift_sign in (1.0, -1.0):
                shift = shift_step * 18.0 * shift_sign
                for radial_step in range(24):
                    radial = radial_step * 30.0 * outward_sign
                    if horizontal:
                        candidate = (
                            target[0] + radial,
                            target[1] + shift,
                        )
                        escape = (
                            candidate[0] - outward_sign * 16.0,
                            point[1],
                        )
                        points = (
                            point,
                            escape,
                            (escape[0], candidate[1]),
                            candidate,
                        )
                    else:
                        candidate = (
                            target[0] + shift,
                            target[1] + radial,
                        )
                        escape = (
                            point[0],
                            candidate[1] - outward_sign * 16.0,
                        )
                        points = (
                            point,
                            escape,
                            (candidate[0], escape[1]),
                            candidate,
                        )
                    yield candidate, points

    def point_in_rect(point: Point, rect: Rect) -> bool:
        return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]

    def path_is_clear(points: tuple[Point, ...], obstacles: list[Rect]) -> bool:
        for start, end in points_to_segments(points):
            for obstacle in obstacles:
                if not segment_hits_rect(start, end, obstacle):
                    continue
                if start == point and point_in_rect(point, obstacle):
                    continue
                return False
        return True

    def path_reuses_other_net(points: tuple[Point, ...], net_name: str) -> bool:
        return wire_spans.overlaps(points_to_segments(points), net_name)

    def terminal_body_hits_wire(
        rect: Rect,
        candidate: Point,
        net_name: str,
    ) -> bool:
        return any(
            segment_hits_rect(start, end, rect)
            for wire_net, start, end in (*route_segments, *terminal_wires)
            if wire_net != net_name
            or not (start == candidate or end == candidate)
        )

    def path_enters_own_terminal_body(
        points: tuple[Point, ...],
        rect: Rect,
        candidate: Point,
    ) -> bool:
        return any(
            segment_hits_rect(start, end, rect)
            and start != candidate
            and end != candidate
            for start, end in points_to_segments(points)
        )

    def normalize_terminal_approach(
        points: tuple[Point, ...],
        rect: Rect,
        candidate: Point,
    ) -> tuple[Point, ...] | None:
        if not path_enters_own_terminal_body(points, rect, candidate):
            return points
        anchor_index = next(
            (
                index
                for index in range(len(points) - 2, -1, -1)
                if not point_in_rect(points[index], rect)
            ),
            None,
        )
        if anchor_index is None:
            return None
        anchor = points[anchor_index]
        left, top, right, bottom = rect
        if anchor[0] < left:
            corner = (anchor[0], candidate[1])
            approach = (left - 6.0, candidate[1])
        elif anchor[0] > right:
            corner = (anchor[0], candidate[1])
            approach = (right + 6.0, candidate[1])
        elif anchor[1] < top:
            corner = (candidate[0], anchor[1])
            approach = (candidate[0], top - 6.0)
        elif anchor[1] > bottom:
            corner = (candidate[0], anchor[1])
            approach = (candidate[0], bottom + 6.0)
        else:
            return None
        normalized = simplify_points(
            (*points[: anchor_index + 1], corner, approach, candidate)
        )
        if path_enters_own_terminal_body(normalized, rect, candidate):
            return None
        return normalized

    component_order = {
        item.component.reference: index
        for index, item in enumerate(placed)
    }
    requests: list[tuple[RoutedNet, str, PlacedComponent, Point, str, int, Point]] = []
    for net in routed:
        if not net.terminalized:
            continue
        terminal_endpoints = (
            net.endpoints[:1]
            if net.reason == "shared_power_terminal"
            else net.endpoints
        )
        for endpoint in terminal_endpoints:
            binding = endpoints.get(endpoint)
            if binding is None:
                continue
            item, _, point = binding
            direction, rotation, target = _terminal_orientation(item, point)
            requests.append((net, endpoint, item, point, direction, rotation, target))

    grouped: dict[
        tuple[str, str, int, int],
        list[tuple[RoutedNet, str, PlacedComponent, Point, str, int, Point]],
    ] = {}
    for request in requests:
        _, _, item, point, direction, rotation, target = request
        sign = 1 if (
            (rotation in {0, 180} and target[0] >= point[0])
            or (rotation not in {0, 180} and target[1] >= point[1])
        ) else -1
        grouped.setdefault(
            (item.component.reference, direction, rotation, sign),
            [],
        ).append(request)

    assigned_targets: dict[tuple[str, str], Point] = {}
    for (_, _, rotation, sign), group in grouped.items():
        horizontal = rotation in {0, 180}
        ordered = sorted(
            group,
            key=lambda request: (
                request[3][1] if horizontal else request[3][0],
                request[1],
            ),
        )
        coordinates = [
            request[3][1] if horizontal else request[3][0]
            for request in ordered
        ]
        center = sum(coordinates) / len(coordinates)
        spacing = 18.0
        slots = [
            center + (index - (len(ordered) - 1) / 2.0) * spacing
            for index in range(len(ordered))
        ]
        outward = (
            (max(request[6][0] for request in ordered) if sign > 0 else min(request[6][0] for request in ordered))
            if horizontal
            else (max(request[6][1] for request in ordered) if sign > 0 else min(request[6][1] for request in ordered))
        )
        for request, slot in zip(ordered, slots):
            assigned_targets[(request[0].name, request[1])] = (
                (outward, slot) if horizontal else (slot, outward)
            )

    requests.sort(
        key=lambda request: (
            -len(
                grouped[
                    (
                        request[2].component.reference,
                        request[4],
                        request[5],
                        1
                        if (
                            (request[5] in {0, 180} and request[6][0] >= request[3][0])
                            or (
                                request[5] not in {0, 180}
                                and request[6][1] >= request[3][1]
                            )
                        )
                        else -1,
                    )
                ]
            ),
            -len(request[2].pins),
            component_order[request[2].component.reference],
            request[5],
            assigned_targets[(request[0].name, request[1])],
            request[0].name,
        )
    )
    for net, endpoint, item, point, direction, rotation, _ in requests:
        target = assigned_targets[(net.name, endpoint)]
        foreign_terminal_zones = [
            inflate(other.body, 80.0)
            for other in placed
            if other.component.reference != item.component.reference
        ]
        selected: tuple[str, int, Point, DonorPacket, Rect, tuple[Point, ...]] | None = None
        rejection_counts = {
            "occupied": 0,
            "planned_route": 0,
            "component": 0,
            "other_pin": 0,
            "terminal_body": 0,
            "terminal_wire": 0,
        }
        packet = packets.setdefault(
            direction,
            source.resolve_terminal_port(direction=direction),
        )
        direct_candidates: Iterable[tuple[Point, tuple[Point, ...]]] = (
            ((point, (point,)),)
            if net.reason == "single_endpoint"
            else ()
        )
        for candidate, candidate_points in chain(
            direct_candidates,
            placement_candidates(point, target, rotation),
        ):
            rect = terminal_rect(packet, candidate, rotation)
            direct_attachment = candidate == point and len(candidate_points) == 1
            component_collision = (
                any(
                    rects_overlap(
                        rect,
                        other.body,
                        touch_is_overlap=False,
                    )
                    for other in placed
                )
                if direct_attachment
                else any(
                    rects_overlap(inflate(rect, 4.0), other)
                    for other in component_obstacles
                )
            )
            if component_collision or any(
                rects_overlap(rect, other, touch_is_overlap=False)
                for other in terminal_rects
            ) or (
                not direct_attachment
                and any(
                    rects_overlap(rect, other, touch_is_overlap=False)
                    for other in foreign_terminal_zones
                )
            ):
                rejection_counts["occupied"] += 1
                continue
            if terminal_body_hits_wire(rect, candidate, net.name):
                rejection_counts["planned_route"] += 1
                continue
            candidate_wires = points_to_segments(candidate_points)
            if wire_spans.overlaps(candidate_wires, net.name):
                rejection_counts["terminal_wire"] += 1
                continue
            if any(
                segment_hits_rect(start, end, obstacle)
                for start, end in candidate_wires
                for obstacle in component_obstacles
                if not (
                    (start == point or end == point)
                    and point_in_rect(point, obstacle)
                )
            ):
                rejection_counts["component"] += 1
                continue
            if any(
                segment_hits_rect(start, end, keepout)
                for start, end in candidate_wires
                for other_endpoint, keepout in pin_keepouts.items()
                if other_endpoint != endpoint
            ):
                rejection_counts["other_pin"] += 1
                continue
            if any(
                segment_hits_rect(start, end, other_rect)
                for start, end in candidate_wires
                for other_rect in terminal_rects
            ):
                rejection_counts["terminal_body"] += 1
                continue
            if any(
                segment_hits_rect(start, end, inflate(rect, 3.0))
                for _, start, end in terminal_wires
            ):
                rejection_counts["terminal_wire"] += 1
                continue
            selected = (
                direction,
                rotation,
                candidate,
                packet,
                rect,
                tuple(candidate_points),
            )
            break
        if selected is None:
            horizontal = rotation in {0, 180}
            outward_sign = (
                1.0
                if (horizontal and target[0] >= point[0])
                or (not horizontal and target[1] >= point[1])
                else -1.0
            )
            obstacles = [
                *component_obstacles,
                *(
                    keepout
                    for other_endpoint, keepout in pin_keepouts.items()
                    if other_endpoint != endpoint
                ),
                *terminal_rects,
            ]
            pivot_offsets = (
                0.0,
                *(
                    signed
                    for step in range(1, 13)
                    for signed in (step * 18.0, -step * 18.0)
                ),
            )
            for shift_step in range(25):
                shifts = (0.0,) if shift_step == 0 else (
                    shift_step * 22.0,
                    -shift_step * 22.0,
                )
                for shift in shifts:
                    for radial_step in range(4):
                        radial = 110.0 + radial_step * 45.0
                        if horizontal:
                            outer_x = (
                                component_envelope[2] + radial
                                if outward_sign > 0
                                else component_envelope[0] - radial
                            )
                            candidate = (outer_x, target[1] + shift)
                            corridor_values = (
                                component_envelope[1] - 90.0 - radial_step * 24.0,
                                component_envelope[3] + 90.0 + radial_step * 24.0,
                            )
                        else:
                            outer_y = (
                                component_envelope[3] + radial
                                if outward_sign > 0
                                else component_envelope[1] - radial
                            )
                            candidate = (target[0] + shift, outer_y)
                            corridor_values = (
                                component_envelope[0] - 90.0 - radial_step * 24.0,
                                component_envelope[2] + 90.0 + radial_step * 24.0,
                            )
                        rect = terminal_rect(packet, candidate, rotation)
                        if any(
                            rects_overlap(inflate(rect, 4.0), other)
                            for other in component_obstacles
                        ) or any(
                            rects_overlap(rect, other, touch_is_overlap=False)
                            for other in terminal_rects
                        ) or any(
                            rects_overlap(rect, other, touch_is_overlap=False)
                            for other in foreign_terminal_zones
                        ):
                            continue
                        if terminal_body_hits_wire(rect, candidate, net.name):
                            continue
                        for pivot_offset in pivot_offsets:
                            if horizontal:
                                base_pivot = target[0] - outward_sign * 16.0
                                pivot = (base_pivot + pivot_offset, point[1])
                                paths = tuple(
                                    (
                                        point,
                                        pivot,
                                        (pivot[0], corridor),
                                        (candidate[0], corridor),
                                        candidate,
                                    )
                                    for corridor in corridor_values
                                )
                            else:
                                base_pivot = target[1] - outward_sign * 16.0
                                pivot = (point[0], base_pivot + pivot_offset)
                                paths = tuple(
                                    (
                                        point,
                                        pivot,
                                        (corridor, pivot[1]),
                                        (corridor, candidate[1]),
                                        candidate,
                                    )
                                    for corridor in corridor_values
                                )
                            wire_points = next(
                                (
                                    candidate_path
                                    for candidate_path in paths
                                    if path_is_clear(candidate_path, obstacles)
                                    and not path_reuses_other_net(
                                        candidate_path,
                                        net.name,
                                    )
                                ),
                                None,
                            )
                            if wire_points is None:
                                continue
                            selected = (
                                direction,
                                rotation,
                                candidate,
                                packet,
                                rect,
                                wire_points,
                            )
                            break
                        if selected is not None:
                            break
                    if selected is not None:
                        break
                if selected is not None:
                    break
        if selected is None:
            horizontal = rotation in {0, 180}
            outward_sign = (
                1.0
                if (horizontal and target[0] >= point[0])
                or (not horizontal and target[1] >= point[1])
                else -1.0
            )
            for alternate_rotation in (
                (rotation + 90) % 360,
                (rotation + 270) % 360,
            ):
                for distance in (18.0, 24.0, 32.0, 40.0, 48.0, 56.0, 64.0, 72.0):
                    candidate = (
                        (point[0] + distance * outward_sign, point[1])
                        if horizontal
                        else (point[0], point[1] + distance * outward_sign)
                    )
                    wire_points = (point, candidate)
                    candidate_wires = points_to_segments(wire_points)
                    rect = terminal_rect(packet, candidate, alternate_rotation)
                    if any(
                        rects_overlap(inflate(rect, 4.0), other)
                        for other in component_obstacles
                    ) or any(
                        rects_overlap(rect, other, touch_is_overlap=False)
                        for other in terminal_rects
                    ) or any(
                        rects_overlap(rect, other, touch_is_overlap=False)
                        for other in foreign_terminal_zones
                    ):
                        continue
                    if terminal_body_hits_wire(rect, candidate, net.name):
                        continue
                    if wire_spans.overlaps(candidate_wires, net.name):
                        continue
                    if any(
                        segment_hits_rect(start, end, obstacle)
                        for start, end in candidate_wires
                        for obstacle in component_obstacles
                        if not (
                            (start == point or end == point)
                            and point_in_rect(point, obstacle)
                        )
                    ):
                        continue
                    if any(
                        segment_hits_rect(start, end, keepout)
                        for start, end in candidate_wires
                        for other_endpoint, keepout in pin_keepouts.items()
                        if other_endpoint != endpoint
                    ):
                        continue
                    if any(
                        segment_hits_rect(start, end, other_rect)
                        for start, end in candidate_wires
                        for other_rect in terminal_rects
                    ):
                        continue
                    selected = (
                        direction,
                        alternate_rotation,
                        candidate,
                        packet,
                        rect,
                        wire_points,
                    )
                    break
                if selected is not None:
                    break
        if selected is None:
            current_body = component_obstacles[
                component_order[item.component.reference]
            ]
            compact_obstacles = [
                envelope
                for reference, envelope in component_pin_envelopes.items()
                if reference != item.component.reference
            ]
            compact_obstacles.append(current_body)
            compact_obstacles.extend(
                keepout
                for other_endpoint, keepout in pin_keepouts.items()
                if other_endpoint != endpoint
                and other_endpoint.startswith(f"{item.component.reference}.")
            )
            compact_obstacles.extend(terminal_rects)
            horizontal = rotation in {0, 180}
            outward_sign = (
                1.0
                if (horizontal and target[0] >= point[0])
                or (not horizontal and target[1] >= point[1])
                else -1.0
            )
            for shift_step in range(13):
                shifts = (0.0,) if shift_step == 0 else (
                    shift_step * 24.0,
                    -shift_step * 24.0,
                )
                for shift in shifts:
                    for radial_step in range(3):
                        radial = 120.0 + radial_step * 55.0
                        if horizontal:
                            candidate = (
                                component_envelope[2] + radial
                                if outward_sign > 0
                                else component_envelope[0] - radial,
                                target[1] + shift,
                            )
                        else:
                            candidate = (
                                target[0] + shift,
                                component_envelope[3] + radial
                                if outward_sign > 0
                                else component_envelope[1] - radial,
                            )
                        rect = terminal_rect(packet, candidate, rotation)
                        if any(
                            rects_overlap(rect, other, touch_is_overlap=False)
                            for other in terminal_rects
                        ) or any(
                            rects_overlap(rect, other, touch_is_overlap=False)
                            for other in foreign_terminal_zones
                        ):
                            continue
                        if terminal_body_hits_wire(rect, candidate, net.name):
                            continue
                        path = _visibility_route(
                            point,
                            candidate,
                            compact_obstacles,
                            component_envelope,
                            len(result) + shift_step,
                        )
                        if path is None:
                            continue
                        wire_points = (point, *(segment[1] for segment in path))
                        if path_reuses_other_net(wire_points, net.name):
                            continue
                        selected = (
                            direction,
                            rotation,
                            candidate,
                            packet,
                            rect,
                            wire_points,
                        )
                        break
                    if selected is not None:
                        break
                if selected is not None:
                    break
        if selected is None:
            raise NativeProjectError(
                f"Cannot place native terminal for {endpoint} on {net.name!r} "
                "without touching a component or planned route; "
                f"candidate rejections={rejection_counts}."
            )
        _, rotation, candidate, packet, rect, wire_points = selected
        normalized_wire_points = normalize_terminal_approach(
            tuple(wire_points),
            rect,
            candidate,
        )
        if normalized_wire_points is not None:
            normalized_segments = points_to_segments(normalized_wire_points)
            normalized_is_clear = (
                not wire_spans.overlaps(normalized_segments, net.name)
                and not any(
                    segment_hits_rect(start, end, obstacle)
                    for start, end in normalized_segments
                    for obstacle in component_obstacles
                    if not (
                        (start == point or end == point)
                        and point_in_rect(point, obstacle)
                    )
                )
                and not any(
                    segment_hits_rect(start, end, keepout)
                    for start, end in normalized_segments
                    for other_endpoint, keepout in pin_keepouts.items()
                    if other_endpoint != endpoint
                )
                and not any(
                    segment_hits_rect(start, end, other_rect)
                    for start, end in normalized_segments
                    for other_rect in terminal_rects
                )
            )
            if normalized_is_clear:
                wire_points = normalized_wire_points
        terminal_rects.append(rect)
        terminal_wires.extend(
            (net.name, start, end)
            for start, end in points_to_segments(wire_points)
        )
        for start, end in points_to_segments(wire_points):
            wire_spans.add(net.name, start, end)
        normalized_wire_points = tuple(
            (round(wire_point[0], 6), round(wire_point[1], 6))
            for wire_point in wire_points
        )
        result.append(
            TerminalInstance(
                net=net.name,
                endpoint=endpoint,
                packet=packet,
                x=round(candidate[0], 6),
                y=round(candidate[1], 6),
                rotation=rotation,
                wire_points=normalized_wire_points,
            )
        )
    return tuple(result)


def _component_records(
    ids: _Ids,
    item: PlacedComponent,
    *,
    line_style: str,
    font_style: str,
) -> list[list[Any]]:
    component_id = ids.next()
    rows: list[list[Any]] = [
        ["COMPONENT", component_id, item.packet.part_name, item.x, item.y, item.rotation, 0, {}, 0],
        [
            "ATTR",
            ids.next(),
            component_id,
            "Designator",
            item.component.reference,
            0,
            1,
            item.body[0],
            item.body[1] - 12,
            0,
            font_style,
            0,
        ],
    ]
    if item.component.value:
        rows.append(
            [
                "ATTR",
                ids.next(),
                component_id,
                "Value",
                item.component.value,
                0,
                1,
                item.body[0],
                item.body[3] + 12,
                0,
                font_style,
                0,
            ]
        )
    hidden_keys = {"Symbol", "Footprint", "Designator", "Value", "3D Model"}
    for attribute in item.packet.attributes:
        key = str(attribute.get("key") or "")
        value = str(attribute.get("value") or "")
        if not key or key in hidden_keys or not value:
            continue
        rows.append(
            ["ATTR", ids.next(), component_id, key, value, 0, 0, None, None, 0, font_style, 0]
        )
    rows.extend(
        [
            [
                "ATTR",
                ids.next(),
                component_id,
                "Device",
                str(item.packet.device["uuid"]),
                0,
                0,
                item.x,
                item.y,
                0,
                font_style,
                0,
            ],
            ["ATTR", ids.next(), component_id, "Name", "", 0, 0, None, None, 0, font_style, 0],
            [
                "ATTR",
                ids.next(),
                component_id,
                "Unique ID",
                f"pg{component_id}",
                0,
                0,
                None,
                None,
                0,
                font_style,
                0,
            ],
        ]
    )
    return rows


def _native_terminal_records(
    ids: _Ids,
    terminal: TerminalInstance,
    *,
    line_style: str,
    font_style: str,
) -> list[list[Any]]:
    component_id = ids.next()
    wire_id = ids.next()
    wire_segments = points_to_segments(terminal.wire_points)
    geometry = [
        [start[0], start[1], end[0], end[1]]
        for start, end in wire_segments
    ]
    label_anchor = wire_segments[0][0] if wire_segments else (terminal.x, terminal.y)
    return [
        [
            "WIRE",
            wire_id,
            geometry,
            line_style,
            0,
        ],
        [
            "ATTR",
            ids.next(),
            wire_id,
            "NET",
            terminal.net,
            0,
            0,
            (label_anchor[0] + terminal.x) / 2,
            (label_anchor[1] + terminal.y) / 2,
            0,
            font_style,
            0,
        ],
        [
            "COMPONENT",
            component_id,
            terminal.packet.part_name,
            terminal.x,
            terminal.y,
            terminal.rotation,
            0,
            {},
            0,
        ],
        [
            "ATTR",
            ids.next(),
            component_id,
            "Name",
            terminal.net,
            0,
            1,
            terminal.x,
            terminal.y,
            terminal.rotation,
            font_style,
            0,
        ],
        [
            "ATTR",
            ids.next(),
            component_id,
            "Device",
            str(terminal.packet.device["uuid"]),
            0,
            0,
            terminal.x,
            terminal.y,
            terminal.rotation,
            font_style,
            0,
        ],
        ["ATTR", ids.next(), component_id, "Unique ID", "", 0, 0, None, None, 0, font_style, 0],
    ]


def build_schematic_data(
    source: EasyedaDonorSource,
    circuit: Circuit,
    placed: tuple[PlacedComponent, ...],
    routed: tuple[RoutedNet, ...],
) -> tuple[str, tuple[TerminalInstance, ...]]:
    template_path = source.materialize().template_path
    prelude = _schematic_prelude(template_path)
    line_style = _style(prelude, "LINESTYLE", "st1")
    font_style = _style(prelude, "FONTSTYLE", "st2")
    ids = _Ids()
    rows = list(prelude)
    for net in routed:
        if not net.segments:
            continue
        if net.terminalized and net.reason != "shared_power_terminal":
            continue
        wire_id = ids.next()
        geometry = [
            [start[0], start[1], end[0], end[1]]
            for start, end in net.segments
        ]
        rows.append(["WIRE", wire_id, geometry, line_style, 0])
        anchor = net.segments[0][0]
        rows.append(
            ["ATTR", ids.next(), wire_id, "NET", net.name, 0, 0, anchor[0], anchor[1], 0, font_style, 0]
        )
    terminals = _build_terminals(source, routed, placed)
    for terminal in terminals:
        rows.extend(
            _native_terminal_records(ids, terminal, line_style=line_style, font_style=font_style)
        )
    for item in placed:
        if item.component.kind in {"GND", "VCC"}:
            component_id = ids.next()
            net_name = next(iter(item.component.pins.values()), item.component.kind)
            rows.append(
                ["COMPONENT", component_id, item.packet.part_name, item.x, item.y, item.rotation, 0, {}, 0]
            )
            rows.append(
                [
                    "ATTR",
                    ids.next(),
                    component_id,
                    "Designator",
                    item.component.reference,
                    0,
                    0,
                    None,
                    None,
                    0,
                    font_style,
                    0,
                ]
            )
            if item.component.kind == "VCC":
                rows.append(
                    [
                        "ATTR",
                        ids.next(),
                        component_id,
                        "Global Net Name",
                        net_name,
                        0,
                        1,
                        item.x,
                        item.y + 15,
                        item.rotation,
                        font_style,
                        0,
                    ]
                )
            rows.extend(
                [
                    ["ATTR", ids.next(), component_id, "Name", net_name, 0, 0, None, None, 0, font_style, 0],
                    [
                        "ATTR",
                        ids.next(),
                        component_id,
                        "Device",
                        str(item.packet.device["uuid"]),
                        0,
                        0,
                        item.x,
                        item.y,
                        item.rotation,
                        font_style,
                        0,
                    ],
                    ["ATTR", ids.next(), component_id, "Unique ID", "", 0, 0, None, None, 0, font_style, 0],
                ]
            )
        else:
            rows.extend(
                _component_records(ids, item, line_style=line_style, font_style=font_style)
            )
    return "\n".join(_record(row) for row in rows), terminals


def _footprint_rect(
    packet: DonorPacket,
    x: float,
    y: float,
    rotation: int = 0,
    margin: float = 65.0,
) -> Rect:
    if packet.footprint_bbox is not None:
        x1, y1, x2, y2 = packet.footprint_bbox
        source_points = ((x1, y1), (x1, y2), (x2, y1), (x2, y2))
    else:
        source_points = tuple(packet.footprint_pads.values())
    rotated = [rotate_point(point, rotation) for point in source_points]
    if not rotated:
        rotated = [(0.0, 0.0)]
    xs = [point[0] for point in rotated]
    ys = [point[1] for point in rotated]
    return min(xs) + x - margin, min(ys) + y - margin, max(xs) + x + margin, max(ys) + y + margin


def _track_crosses_other(
    segments: Iterable[tuple[Point, Point]],
    existing: Iterable[tuple[str, int, Point, Point]],
    net: str,
    layer: int,
) -> bool:
    def intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
        if a[0] == b[0] and c[1] == d[1]:
            return min(a[1], b[1]) <= c[1] <= max(a[1], b[1]) and min(c[0], d[0]) <= a[0] <= max(c[0], d[0])
        if a[1] == b[1] and c[0] == d[0]:
            return min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(c[1], d[1]) <= a[1] <= max(c[1], d[1])
        if a[0] == b[0] == c[0] == d[0]:
            return max(min(a[1], b[1]), min(c[1], d[1])) <= min(max(a[1], b[1]), max(c[1], d[1]))
        if a[1] == b[1] == c[1] == d[1]:
            return max(min(a[0], b[0]), min(c[0], d[0])) <= min(max(a[0], b[0]), max(c[0], d[0]))
        return False

    for start, end in segments:
        for other_net, other_layer, other_start, other_end in existing:
            if other_layer == layer and other_net != net and intersects(start, end, other_start, other_end):
                return True
    return False


def _pcb_route(
    start: Point,
    end: Point,
    obstacles: list[Rect],
    envelope: Rect,
    lane: int,
    existing: list[tuple[str, int, Point, Point]],
    net: str,
    layer: int,
) -> tuple[tuple[Point, Point], ...] | None:
    left, top, right, bottom = envelope
    offset = 100 + lane * 35
    candidates = (
        (start, (end[0], start[1]), end),
        (start, (start[0], end[1]), end),
        (start, (start[0], top - offset), (end[0], top - offset), end),
        (start, (start[0], bottom + offset), (end[0], bottom + offset), end),
        (start, (left - offset, start[1]), (left - offset, end[1]), end),
        (start, (right + offset, start[1]), (right + offset, end[1]), end),
    )
    for candidate in candidates:
        segments = points_to_segments(candidate)
        blocked = False
        for segment_start, segment_end in segments:
            for obstacle in obstacles:
                if segment_hits_rect(segment_start, segment_end, obstacle):
                    if segment_start in {start, end} or segment_end in {start, end}:
                        continue
                    blocked = True
                    break
            if blocked:
                break
        if not blocked and not _track_crosses_other(segments, existing, net, layer):
            return segments
    return None


def _pcb_channel_routes(
    circuit: Circuit,
    endpoint_lookup: dict[str, Point],
    endpoint_keepouts: dict[str, Rect],
    endpoint_bodies: dict[str, Rect],
    pad_net: dict[str, str],
    envelope: Rect,
    *,
    order_variant: str,
) -> tuple[list[tuple[str, int, Point, Point]], set[tuple[str, Point]]] | str:
    """Route dense boards with top-layer spokes and bottom-layer net trunks."""

    tracks: list[tuple[str, int, Point, Point]] = []
    vias: set[tuple[str, Point]] = set()
    used_lane_x: list[float] = []
    power_names = {"GND", "GROUND", "VSS", "VCC", "VDD", "+5V", "5V", "+3V3", "3V3"}

    def net_anchor(item: tuple[str, tuple[str, ...]], *, right: bool) -> float:
        points = [
            endpoint_lookup[endpoint]
            for endpoint in item[1]
            if endpoint in endpoint_lookup
        ]
        if not points:
            return 0.0
        selector = max if right else min
        return selector(points, key=lambda point: (point[0], -point[1]))[1]

    def order_key(item: tuple[str, tuple[str, ...]]) -> tuple[object, ...]:
        power = item[0].upper() in power_names
        if order_variant == "left_desc":
            return power, -net_anchor(item, right=False), -len(item[1]), item[0]
        if order_variant == "right_asc":
            return power, net_anchor(item, right=True), -len(item[1]), item[0]
        if order_variant == "right_desc":
            return power, -net_anchor(item, right=True), -len(item[1]), item[0]
        if order_variant == "fanout":
            return power, -len(item[1]), item[0]
        if order_variant == "alpha":
            return power, item[0]
        return power, net_anchor(item, right=False), -len(item[1]), item[0]

    routed_nets = [
        (net, [(endpoint, endpoint_lookup[endpoint]) for endpoint in members if endpoint in endpoint_lookup])
        for net, members in sorted(
            circuit.nets.items(),
            key=order_key,
        )
    ]
    routed_nets = [(net, pads) for net, pads in routed_nets if len(pads) >= 2]
    top = envelope[1]
    for net_index, (net, routed_pads) in enumerate(routed_nets):
        trunk_y = top - 220.0 - net_index * 60.0
        spoke_segments: list[tuple[Point, Point]] = []
        trunk_points: list[Point] = []
        for endpoint, point in sorted(routed_pads, key=lambda item: (item[1][1], item[1][0], item[0])):
            selected: tuple[tuple[Point, Point], ...] | None = None
            selected_lane_x: float | None = None
            body = endpoint_bodies[endpoint]
            escape_ys = (
                point[1],
                body[1] - 30.0,
                body[3] + 30.0,
            )
            for step in range(641):
                if step == 0:
                    delta = 0.0
                else:
                    delta = ((step + 1) // 2) * 35.0 * (1 if step % 2 else -1)
                lane_x = round(point[0] + delta, 4)
                if any(abs(lane_x - used) < 8.0 for used in used_lane_x):
                    continue
                for escape_y in escape_ys:
                    segments = points_to_segments(
                        (
                            point,
                            (point[0], escape_y),
                            (lane_x, escape_y),
                            (lane_x, trunk_y),
                        )
                    )
                    if any(
                        segment_hits_rect(start, end, keepout)
                        for start, end in segments
                        for other_endpoint, keepout in endpoint_keepouts.items()
                        if other_endpoint != endpoint and pad_net.get(other_endpoint) != net
                    ):
                        continue
                    if _track_crosses_other(segments, tracks, net, 1):
                        continue
                    selected = segments
                    selected_lane_x = lane_x
                    break
                if selected is not None:
                    break
            if selected is None or selected_lane_x is None:
                return f"channel_unroutable:{order_variant}:{net}:{endpoint}"
            tracks.extend((net, 1, start, end) for start, end in selected)
            spoke_segments.extend(selected)
            trunk_point = (selected_lane_x, trunk_y)
            trunk_points.append(trunk_point)
            used_lane_x.append(selected_lane_x)
            vias.add((net, trunk_point))
        trunk_start = (min(point[0] for point in trunk_points), trunk_y)
        trunk_end = (max(point[0] for point in trunk_points), trunk_y)
        tracks.append((net, 2, trunk_start, trunk_end))
    return tracks, vias


def _pcb_escape_channel_routes(
    circuit: Circuit,
    endpoint_lookup: dict[str, Point],
    endpoint_keepouts: dict[str, Rect],
    endpoint_bodies: dict[str, Rect],
    endpoint_sides: dict[str, str],
    pad_net: dict[str, str],
    envelope: Rect,
) -> tuple[list[tuple[str, int, Point, Point]], set[tuple[str, Point]]] | str:
    """Fan pads out by footprint side before joining isolated net trunks."""

    endpoint_plan: dict[str, tuple[str, str]] = {}
    side_groups: dict[tuple[str, str, str], list[str]] = {}
    for endpoint, point in endpoint_lookup.items():
        reference = endpoint.rsplit(".", 1)[0]
        left, top, right, bottom = endpoint_bodies[endpoint]
        side = endpoint_sides[endpoint]
        direction = "top" if point[1] <= (top + bottom) / 2.0 else "bottom"
        endpoint_plan[endpoint] = (side, direction)
        if side in {"left", "right"}:
            side_groups.setdefault((reference, side, direction), []).append(endpoint)

    lane_x: dict[str, float] = {}
    for (_, side, direction), endpoints in side_groups.items():
        ordered = sorted(
            endpoints,
            key=lambda endpoint: endpoint_lookup[endpoint][1],
            reverse=direction == "bottom",
        )
        body = endpoint_bodies[ordered[0]]
        for index, endpoint in enumerate(ordered, start=1):
            lane_x[endpoint] = (
                body[0] - index * 35.0
                if side == "left"
                else body[2] + index * 35.0
            )
    for endpoint, point in endpoint_lookup.items():
        lane_x.setdefault(endpoint, point[0])

    power_names = {"GND", "GROUND", "VSS", "VCC", "VDD", "+5V", "5V", "+3V3", "3V3"}
    routed_nets = [
        (
            net,
            [endpoint for endpoint in members if endpoint in endpoint_lookup],
        )
        for net, members in sorted(
            circuit.nets.items(),
            key=lambda item: (
                item[0].upper() in power_names,
                -len(item[1]),
                item[0],
            ),
        )
    ]
    routed_nets = [(net, endpoints) for net, endpoints in routed_nets if len(endpoints) >= 2]
    tracks: list[tuple[str, int, Point, Point]] = []
    vias: set[tuple[str, Point]] = set()
    top_trunks: dict[str, tuple[float, list[Point]]] = {}
    bottom_trunks: dict[str, tuple[float, list[Point]]] = {}
    top_y = envelope[1] - 220.0
    bottom_y = envelope[3] + 220.0
    for net_index, (net, endpoints) in enumerate(routed_nets):
        net_top_y = top_y - net_index * 60.0
        net_bottom_y = bottom_y + net_index * 60.0
        for endpoint in endpoints:
            point = endpoint_lookup[endpoint]
            side, direction = endpoint_plan[endpoint]
            if side == "center":
                body = endpoint_bodies[endpoint]
                selected_center: tuple[
                    tuple[tuple[Point, Point], ...],
                    str,
                    float,
                ] | None = None
                for center_direction, center_destination_y in (
                    ("top", net_top_y),
                    ("bottom", net_bottom_y),
                ):
                    for outside_x in (body[0] - 45.0, body[2] + 45.0):
                        for step in range(33):
                            shift = (
                                0.0
                                if step == 0
                                else ((step + 1) // 2)
                                * 10.0
                                * (1.0 if step % 2 else -1.0)
                            )
                            escape_y = point[1] + shift
                            if not body[1] + 8.0 <= escape_y <= body[3] - 8.0:
                                continue
                            segments = points_to_segments(
                                (
                                    point,
                                    (point[0], escape_y),
                                    (outside_x, escape_y),
                                    (outside_x, center_destination_y),
                                )
                            )
                            if any(
                                segment_hits_rect(start, end, keepout)
                                for start, end in segments
                                for other_endpoint, keepout in endpoint_keepouts.items()
                                if other_endpoint != endpoint
                                and pad_net.get(other_endpoint) != net
                            ):
                                continue
                            if _track_crosses_other(segments, tracks, net, 1):
                                continue
                            selected_center = (
                                segments,
                                center_direction,
                                outside_x,
                            )
                            break
                        if selected_center is not None:
                            break
                    if selected_center is not None:
                        break
                if selected_center is None:
                    return f"center_escape_unroutable:{net}:{endpoint}"
                segments, direction, x = selected_center
                destination_y = net_top_y if direction == "top" else net_bottom_y
                tracks.extend((net, 1, start, end) for start, end in segments)
                trunk_point = (x, destination_y)
                vias.add((net, trunk_point))
                target = top_trunks if direction == "top" else bottom_trunks
                target.setdefault(net, (destination_y, []))[1].append(trunk_point)
                continue
            destination_y = net_top_y if direction == "top" else net_bottom_y
            x = lane_x[endpoint]
            points = (
                (point, (x, point[1]), (x, destination_y))
                if side in {"left", "right"}
                else (point, (point[0], destination_y))
            )
            segments = points_to_segments(points)
            if any(
                segment_hits_rect(start, end, keepout)
                for start, end in segments
                for other_endpoint, keepout in endpoint_keepouts.items()
                if other_endpoint != endpoint and pad_net.get(other_endpoint) != net
            ):
                return f"escape_unroutable:{net}:{endpoint}"
            if _track_crosses_other(segments, tracks, net, 1):
                return f"escape_crossing:{net}:{endpoint}"
            tracks.extend((net, 1, start, end) for start, end in segments)
            trunk_point = (x, destination_y)
            vias.add((net, trunk_point))
            target = top_trunks if direction == "top" else bottom_trunks
            target.setdefault(net, (destination_y, []))[1].append(trunk_point)

    for net, (y, points) in top_trunks.items():
        tracks.append(
            (
                net,
                2,
                (min(point[0] for point in points), y),
                (max(point[0] for point in points), y),
            )
        )
    for net, (y, points) in bottom_trunks.items():
        tracks.append(
            (
                net,
                2,
                (min(point[0] for point in points), y),
                (max(point[0] for point in points), y),
            )
        )

    bridge_base_x = max(
        [envelope[2], *lane_x.values()],
    ) + 300.0
    bridge_index = 0
    for net, (net_top_y, top_points) in top_trunks.items():
        bottom = bottom_trunks.get(net)
        if bottom is None:
            continue
        net_bottom_y, bottom_points = bottom
        bridge_x = bridge_base_x + bridge_index * 60.0
        bridge_index += 1
        top_anchor = (bridge_x, net_top_y)
        bottom_anchor = (bridge_x, net_bottom_y)
        tracks.extend(
            (
                (
                    net,
                    2,
                    (max(point[0] for point in top_points), net_top_y),
                    top_anchor,
                ),
                (
                    net,
                    2,
                    (max(point[0] for point in bottom_points), net_bottom_y),
                    bottom_anchor,
                ),
                (net, 1, top_anchor, bottom_anchor),
            )
        )
        vias.add((net, top_anchor))
        vias.add((net, bottom_anchor))
    return tracks, vias


def build_pcb_data(
    source: EasyedaDonorSource,
    circuit: Circuit,
    placed: tuple[PlacedComponent, ...],
) -> PcbResult:
    physical = [item for item in placed if item.component.kind not in {"GND", "VCC"}]
    if not physical:
        return PcbResult(False, "no_physical_components", None, 0, 0, {}, {})
    if len(physical) > 32:
        return PcbResult(False, "basic_pcb_component_limit_32", None, len(physical), 0, {}, {})
    for item in physical:
        if not item.packet.pcb_ready:
            return PcbResult(False, f"missing_footprint:{item.component.reference}", None, len(physical), 0, {}, {})
        for requested, descriptor in item.source_pins.items():
            if descriptor.number not in item.packet.footprint_pads:
                return PcbResult(
                    False,
                    f"missing_pad_mapping:{item.component.reference}.{requested}->{descriptor.number}",
                    None,
                    len(physical),
                    0,
                    {},
                    {},
                )

    prefer_channel_layout = len(physical) > 8 or any(
        len(item.source_pins) > 6
        for item in physical
    )
    placements: dict[str, tuple[float, float]] = {}
    rotations: dict[str, int] = {
        item.component.reference: (
            180
            if item.component.kind in {"DIODE", "1N4007", "1N4148"}
            else 90
            if item.component.kind
            in {
                "PIN_HEADER",
                "HEADER_1X6",
                "HEADER_2X3",
                "HEADER_2X5_1P27",
            }
            else 0
        )
        for item in physical
    }
    rects: dict[str, Rect] = {}
    x = 400.0
    y = -400.0
    row_height = 0.0
    max_width = float("inf") if prefer_channel_layout else 3600.0
    for item in physical:
        rotation = rotations[item.component.reference]
        local_rect = _footprint_rect(item.packet, 0, 0, rotation)
        width = local_rect[2] - local_rect[0]
        height = local_rect[3] - local_rect[1]
        if x > 400 and x + width > max_width:
            x = 400.0
            y -= row_height + 300.0
            row_height = 0.0
        place_x = x - local_rect[0]
        place_y = y - local_rect[1]
        rect = _footprint_rect(item.packet, place_x, place_y, rotation)
        if any(rects_overlap(rect, other) for other in rects.values()):
            return PcbResult(False, f"footprint_overlap:{item.component.reference}", None, len(physical), 0, placements, {})
        placements[item.component.reference] = (round(place_x, 4), round(place_y, 4))
        rects[item.component.reference] = rect
        x += width + (1200.0 if prefer_channel_layout else 260.0)
        row_height = max(row_height, height)

    endpoint_lookup: dict[str, Point] = {}
    endpoint_keepouts: dict[str, Rect] = {}
    endpoint_bodies: dict[str, Rect] = {}
    endpoint_sides: dict[str, str] = {}
    for item in physical:
        origin = placements[item.component.reference]
        rotation = rotations[item.component.reference]
        for requested, descriptor in item.source_pins.items():
            local = item.packet.footprint_pads[descriptor.number]
            local = rotate_point(local, rotation)
            endpoint_lookup[f"{item.component.reference}.{requested}"] = (
                round(origin[0] + local[0], 4),
                round(origin[1] + local[1], 4),
            )
            pad = item.packet.footprint_pad_details[descriptor.number]
            shape = pad.shape if isinstance(pad.shape, list) else []
            width = float(shape[1]) if len(shape) > 1 and isinstance(shape[1], (int, float)) else 18.0
            height = float(shape[2]) if len(shape) > 2 and isinstance(shape[2], (int, float)) else width
            total_pad_rotation = (pad.rotation + rotation) % 360
            if 45.0 <= total_pad_rotation < 135.0 or 225.0 <= total_pad_rotation < 315.0:
                width, height = height, width
            point = endpoint_lookup[f"{item.component.reference}.{requested}"]
            clearance = 2.0
            endpoint_keepouts[f"{item.component.reference}.{requested}"] = (
                point[0] - width / 2.0 - clearance,
                point[1] - height / 2.0 - clearance,
                point[0] + width / 2.0 + clearance,
                point[1] + height / 2.0 + clearance,
            )
            endpoint_bodies[f"{item.component.reference}.{requested}"] = rects[
                item.component.reference
            ]
            left, top, right, bottom = rects[item.component.reference]
            if (
                width > (right - left) * 0.30
                and height > (bottom - top) * 0.30
                and left + width / 2.0 + 12.0
                < point[0]
                < right - width / 2.0 - 12.0
                and top + height / 2.0 + 12.0 < point[1] < bottom - height / 2.0 - 12.0
            ):
                side = "center"
            elif width > height * 1.5:
                side = "left" if point[0] <= (left + right) / 2.0 else "right"
            elif height > width * 1.5:
                side = "top" if point[1] <= (top + bottom) / 2.0 else "bottom"
            else:
                distances = {
                    "left": abs(point[0] - left),
                    "right": abs(point[0] - right),
                    "top": abs(point[1] - top),
                    "bottom": abs(point[1] - bottom),
                }
                side = min(distances, key=distances.get)
            endpoint_sides[f"{item.component.reference}.{requested}"] = side
    all_rects = list(rects.values())
    envelope = (
        min(rect[0] for rect in all_rects),
        min(rect[1] for rect in all_rects),
        max(rect[2] for rect in all_rects),
        max(rect[3] for rect in all_rects),
    )
    pad_net: dict[str, str] = {}
    for net, members in circuit.nets.items():
        for endpoint in members:
            if endpoint in endpoint_lookup:
                pad_net[endpoint] = net
    tracks: list[tuple[str, int, Point, Point]] = []
    via_points: set[tuple[str, Point]] = set()
    lane = 0
    power_names = {
        net
        for net, members in circuit.nets.items()
        if net.upper() in {"GND", "VSS", "GROUND", "VCC", "VDD", "+5V", "5V", "+3V3", "3V3"}
        and sum(endpoint in endpoint_lookup for endpoint in members) >= 2
    }
    use_split_power_rails = len(power_names) <= 2
    channel_result: tuple[list[tuple[str, int, Point, Point]], set[tuple[str, Point]]] | str | None
    pcb_variations: list[dict[str, Any]] = []
    if (
        len(physical) > 8
        or len(power_names) > 2
        or any(len(item.source_pins) > 6 for item in physical)
    ):
        escape_result = _pcb_escape_channel_routes(
            circuit,
            endpoint_lookup,
            endpoint_keepouts,
            endpoint_bodies,
            endpoint_sides,
            pad_net,
            envelope,
        )
        variants = (
            "left_asc",
            "left_desc",
            "right_asc",
            "right_desc",
            "fanout",
            "alpha",
        )
        with ThreadPoolExecutor(max_workers=len(variants), thread_name_prefix="easyeda-pcb") as executor:
            futures = [
                executor.submit(
                    _pcb_channel_routes,
                    circuit,
                    endpoint_lookup,
                    endpoint_keepouts,
                    endpoint_bodies,
                    pad_net,
                    envelope,
                    order_variant=variant,
                )
                for variant in variants
            ]
            channel_results = [future.result() for future in futures]
        named_results = [
            ("escape_side_channels", escape_result),
            *zip(variants, channel_results),
        ]
        accepted = next(
            (
                (name, result)
                for name, result in named_results
                if isinstance(result, tuple)
            ),
            (named_results[0][0], named_results[0][1]),
        )
        accepted_name, channel_result = accepted
        pcb_variations = [
            {
                "name": name,
                "passed": isinstance(result, tuple),
                "accepted": name == accepted_name and isinstance(result, tuple),
                "track_count": len(result[0]) if isinstance(result, tuple) else 0,
                "via_count": len(result[1]) if isinstance(result, tuple) else 0,
                "failure": result if isinstance(result, str) else None,
            }
            for name, result in named_results
        ]
        channel_failures = (
            [escape_result] if isinstance(escape_result, str) else []
        ) + [
            result for result in channel_results if isinstance(result, str)
        ]
    else:
        channel_result = None
        channel_failures = []
    channel_failure = (
        ";".join(channel_failures)
        if isinstance(channel_result, str)
        else None
    )
    channel_routes = channel_result if isinstance(channel_result, tuple) else None
    if channel_routes is not None:
        tracks, via_points = channel_routes
    routing_items = (
        []
        if channel_routes is not None
        else sorted(circuit.nets.items(), key=lambda item: (-len(item[1]), item[0]))
    )
    for net, members in routing_items:
        routed_pads = [
            (endpoint, endpoint_lookup[endpoint])
            for endpoint in members
            if endpoint in endpoint_lookup
        ]
        if len(routed_pads) < 2:
            continue
        if use_split_power_rails and net in power_names:
            is_ground = net.upper() in {"GND", "VSS", "GROUND"}
            rail_layer = 2 if is_ground else 1
            rail_y = envelope[3] + 180.0 if is_ground else envelope[1] - 180.0
            drops: list[tuple[Point, Point]] = []
            drop_xs: list[float] = []
            for endpoint, point in routed_pads:
                selected_drop: tuple[tuple[Point, Point], ...] | None = None
                for step in range(40):
                    if step == 0:
                        delta = 0.0
                    else:
                        delta = ((step + 1) // 2) * 35.0 * (1 if step % 2 else -1)
                    drop_x = point[0] + delta
                    segments = points_to_segments(
                        (point, (drop_x, point[1]), (drop_x, rail_y))
                    )
                    if any(
                        segment_hits_rect(
                            start,
                            end,
                            (
                                other_point[0] - 22.0,
                                other_point[1] - 22.0,
                                other_point[0] + 22.0,
                                other_point[1] + 22.0,
                            ),
                        )
                        for start, end in segments
                        for other_endpoint, other_point in endpoint_lookup.items()
                        if other_endpoint != endpoint and pad_net.get(other_endpoint) != net
                    ):
                        continue
                    if _track_crosses_other(segments, tracks, net, rail_layer):
                        continue
                    selected_drop = segments
                    drop_xs.append(drop_x)
                    break
                if selected_drop is None:
                    return PcbResult(
                        False,
                        f"pcb_unroutable:{net}",
                        None,
                        len(physical),
                        len(tracks),
                        placements,
                        endpoint_lookup,
                    )
                drops.extend(selected_drop)
            rail_start = (min(drop_xs), rail_y)
            rail_end = (max(drop_xs), rail_y)
            candidate_tracks = [(rail_start, rail_end), *drops]
            if _track_crosses_other(candidate_tracks, tracks, net, rail_layer):
                return PcbResult(
                    False,
                    f"pcb_unroutable:{net}",
                    None,
                    len(physical),
                    len(tracks),
                    placements,
                    endpoint_lookup,
                )
            tracks.extend((net, rail_layer, start, end) for start, end in candidate_tracks)
            if rail_layer == 2:
                via_points.update((net, point) for _, point in routed_pads)
            continue
        connected = [routed_pads[0]]
        remaining = list(routed_pads[1:])
        while remaining:
            root_endpoint, root, end_index, end_endpoint, end = min(
                (
                    (
                        connected_endpoint,
                        connected_point,
                        candidate_index,
                        candidate_endpoint,
                        candidate_point,
                    )
                    for connected_endpoint, connected_point in connected
                    for candidate_index, (candidate_endpoint, candidate_point) in enumerate(remaining)
                ),
                key=lambda item: (
                    abs(item[1][0] - item[4][0]) + abs(item[1][1] - item[4][1]),
                    item[0],
                    item[3],
                ),
            )
            chosen_layer: int | None = None
            chosen_segments: tuple[tuple[Point, Point], ...] | None = None
            obstacles = [
                (point[0] - 28, point[1] - 28, point[0] + 28, point[1] + 28)
                for endpoint, point in endpoint_lookup.items()
                if endpoint not in {root_endpoint, end_endpoint}
                and pad_net.get(endpoint) != net
            ]
            for layer in (1, 2):
                segments = _pcb_route(
                    root,
                    end,
                    obstacles,
                    envelope,
                    lane,
                    tracks,
                    net,
                    layer,
                )
                if segments is not None:
                    chosen_segments = segments
                    chosen_layer = layer
                    break
            lane += 1
            if chosen_layer is None or chosen_segments is None:
                return PcbResult(
                    False,
                    channel_failure or f"pcb_unroutable:{net}",
                    None,
                    len(physical),
                    len(tracks),
                    placements,
                    endpoint_lookup,
                )
            tracks.extend(
                (net, chosen_layer, start, finish)
                for start, finish in chosen_segments
            )
            if chosen_layer == 2:
                via_points.add((net, root))
                via_points.add((net, end))
            connected.append(remaining.pop(end_index))

    prelude = _pcb_prelude(source.materialize().template_path)
    ids = _Ids()
    rows = list(prelude)
    for net in sorted(circuit.nets):
        rows.append(["NET", net, None, None, 1, None, 0, None])
    component_ids: dict[str, str] = {}
    for item in physical:
        component_id = ids.next()
        component_ids[item.component.reference] = component_id
        px, py = placements[item.component.reference]
        rotation = rotations[item.component.reference]
        rows.extend(
            [
                ["COMPONENT", component_id, 0, 1, px, py, rotation, {"Value": item.component.value, "Name": "", "Unique ID": f"pg{component_id}"}, 0],
                [
                    "ATTR",
                    ids.next(),
                    0,
                    component_id,
                    3,
                    px,
                    py,
                    "Designator",
                    item.component.reference,
                    0,
                    1,
                    "Arial",
                    78.7402,
                    10,
                    0,
                    0,
                    3,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
                [
                    "ATTR",
                    ids.next(),
                    0,
                    component_id,
                    3,
                    0,
                    0,
                    "Device",
                    str(item.packet.device["uuid"]),
                    0,
                    0,
                    "default",
                    45,
                    6,
                    0,
                    0,
                    3,
                    0,
                    0,
                    0,
                    0,
                    0,
                ],
            ]
        )
    for item in physical:
        component_id = component_ids[item.component.reference]
        for requested, descriptor in item.source_pins.items():
            endpoint = f"{item.component.reference}.{requested}"
            net = pad_net.get(endpoint)
            pad_id = item.packet.footprint_pad_ids.get(descriptor.number)
            if net and pad_id:
                rows.append(["PAD_NET", component_id, descriptor.number, net, f"{component_id}{pad_id}"])
    source_pcb_rows = _base_records(source.materialize().template_path, 3)
    via_template = next(
        (row for row in source_pcb_rows if row[0] == "PAD" and len(row) >= 18),
        None,
    )
    if via_template is None and via_points:
        return PcbResult(False, "donor_has_no_via_pad_record", None, len(physical), len(tracks), placements, endpoint_lookup)
    for net, point in sorted(via_points):
        via = list(via_template or [])
        via[1] = ids.next()
        via[3] = net
        via[6] = point[0]
        via[7] = point[1]
        rows.append(via)
    for net, layer, start, end in tracks:
        rows.append(["LINE", ids.next(), 0, net, layer, start[0], start[1], end[0], end[1], 6, 0])
    track_points = [
        point
        for _, _, start, end in tracks
        for point in (start, end)
    ]
    left = min([envelope[0]] + [point[0] for point in track_points])
    top = min([envelope[1]] + [point[1] for point in track_points])
    right = max([envelope[2]] + [point[0] for point in track_points])
    bottom = max([envelope[3]] + [point[1] for point in track_points])
    margin = 180.0
    outline = [
        left - margin,
        top - margin,
        "L",
        right + margin,
        top - margin,
        right + margin,
        bottom + margin,
        left - margin,
        bottom + margin,
        left - margin,
        top - margin,
    ]
    rows.append(["POLY", ids.next(), 0, "", 11, 10, outline, 0])
    return PcbResult(
        True,
        "ready",
        "\n".join(_record(row) for row in rows),
        len(physical),
        len(tracks),
        placements,
        endpoint_lookup,
        tuple(
            pcb_variations
            or [
                {
                    "name": "direct_two_layer",
                    "passed": True,
                    "accepted": True,
                    "track_count": len(tracks),
                    "via_count": len(via_points),
                    "failure": None,
                }
            ]
        ),
    )


def _insert_dict(connection: sqlite3.Connection, table: str, row: dict[str, Any]) -> None:
    columns = {info[1] for info in connection.execute(f"PRAGMA table_info({table})")}
    selected = {key: value for key, value in row.items() if key in columns}
    names = ", ".join(f'"{name}"' for name in selected)
    placeholders = ", ".join("?" for _ in selected)
    connection.execute(
        f'INSERT OR REPLACE INTO "{table}" ({names}) VALUES ({placeholders})',
        tuple(selected.values()),
    )


def _template_row(connection: sqlite3.Connection, table: str) -> dict[str, Any]:
    connection.row_factory = sqlite3.Row
    row = connection.execute(f'SELECT * FROM "{table}" LIMIT 1').fetchone()
    if row is None:
        columns = [info[1] for info in connection.execute(f"PRAGMA table_info({table})")]
        return {column: None for column in columns}
    return dict(row)


def _prepare_project_identity(
    connection: sqlite3.Connection,
    *,
    project_uuid: str,
    branch_uuid: str,
    timestamp: str,
) -> None:
    """Remove donor-scoped state and make the clone a native 3.x project."""

    project_columns = {
        info[1] for info in connection.execute("PRAGMA table_info(projects)")
    }
    if "branch_uuid" not in project_columns:
        connection.execute("ALTER TABLE projects ADD COLUMN branch_uuid varchar")

    member = connection.execute(
        "SELECT role, user_uuid FROM project_members LIMIT 1"
    ).fetchone()
    connection.execute("DELETE FROM project_members")
    if member is not None:
        connection.execute(
            """
            INSERT INTO project_members
                (role, project_uuid, user_uuid, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (member[0], project_uuid, member[1], timestamp, timestamp),
        )

    # These are derived caches for the donor PCB. Keeping them makes EasyEDA
    # attempt legacy history recovery for the donor project during open.
    for table in ("coppers", "texts"):
        connection.execute(f'DELETE FROM "{table}"')

    connection.execute(
        "UPDATE projects SET branch_uuid = ? WHERE uuid = ?",
        (branch_uuid, project_uuid),
    )


def _manifest_packet(packet: DonorPacket) -> dict[str, Any]:
    return {
        "kind": packet.kind,
        "resolved_title": packet.resolved_title,
        "device_uuid": packet.device["uuid"],
        "symbol_uuid": packet.symbol["uuid"],
        "footprint_uuid": packet.footprint["uuid"] if packet.footprint else None,
        "part_name": packet.part_name,
        "pins": [
            {"number": pin.number, "name": pin.name, "type": pin.pin_type, "x": pin.x, "y": pin.y}
            for pin in packet.pins
        ],
        "source_hashes": packet.source_hashes,
    }


def write_project(
    output_path: Path,
    source: EasyedaDonorSource,
    circuit: Circuit,
    placed: tuple[PlacedComponent, ...],
    routed: tuple[RoutedNet, ...],
    packets: dict[str, DonorPacket],
) -> NativeWriteResult:
    """Clone a donor project and replace its contents with generated records."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source.materialize().template_path, output_path)
    schematic_data, terminals = build_schematic_data(source, circuit, placed, routed)
    pcb = build_pcb_data(source, circuit, placed)
    namespace = uuid.UUID("21ca8d1d-ad75-42fa-a03d-b2c8f49bb56c")
    project_uuid = uuid.uuid5(namespace, f"{circuit.name}:project").hex
    branch_uuid = uuid.uuid5(namespace, f"{circuit.name}:branch").hex
    schematic_uuid = uuid.uuid5(namespace, f"{circuit.name}:schematic").hex
    sheet_uuid = uuid.uuid5(namespace, f"{circuit.name}:sheet").hex
    pcb_uuid = uuid.uuid5(namespace, f"{circuit.name}:pcb").hex if pcb.ready else None
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    epoch = int(datetime.now(timezone.utc).timestamp())
    all_packets = {str(packet.device["uuid"]): packet for packet in packets.values()}
    for terminal in terminals:
        all_packets[str(terminal.packet.device["uuid"])] = terminal.packet

    with sqlite3.connect(output_path) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        project_base = _template_row(connection, "projects")
        schematic_base = _template_row(connection, "schematics")
        document_base = _template_row(connection, "documents")
        board_base = _template_row(connection, "boards")
        for table in ("attributes", "devices", "components", "resources", "documents", "boards", "schematics", "projects"):
            connection.execute(f'DELETE FROM "{table}"')
        for packet in all_packets.values():
            device = dict(packet.device)
            device["project_uuid"] = project_uuid
            _insert_dict(connection, "devices", device)
            for attribute in packet.attributes:
                _insert_dict(connection, "attributes", dict(attribute))
            symbol = dict(packet.symbol)
            symbol["project_uuid"] = project_uuid
            _insert_dict(connection, "components", symbol)
            if packet.footprint is not None:
                footprint = dict(packet.footprint)
                footprint["project_uuid"] = project_uuid
                _insert_dict(connection, "components", footprint)
            for resource in packet.resources:
                resource_row = dict(resource)
                resource_row["owner_uuid"] = project_uuid
                _insert_dict(connection, "resources", resource_row)
        board_map = (
            [{"sch": schematic_uuid, "name": circuit.title, "pcb": pcb_uuid}]
            if pcb_uuid is not None
            else []
        )
        project = dict(project_base)
        project.update(
            {
                "uuid": project_uuid,
                "archive": 0,
                "name": circuit.title,
                "content": "",
                "cbb_project": 0,
                "thumb": "",
                "ticket": 1,
                "g_ticket": 1,
                "created_at": timestamp,
                "updated_at": timestamp,
                "boards": json.dumps(board_map, separators=(",", ":")),
                "block_symbol_attrs_groups": "{}",
                "pcb_count": 1 if pcb.ready else 0,
                "default_sheet": sheet_uuid,
                "branch_uuid": branch_uuid,
            }
        )
        _insert_dict(connection, "projects", project)
        _prepare_project_identity(
            connection,
            project_uuid=project_uuid,
            branch_uuid=branch_uuid,
            timestamp=timestamp,
        )
        schematic = dict(schematic_base)
        schematic.update(
            {
                "uuid": schematic_uuid,
                "description": "",
                "ticket": 1,
                "sheet_count": 1,
                "project_uuid": project_uuid,
                "name": "schematic",
                "display_name": "Schematic",
                "createtime": epoch,
                "updatetime": epoch,
                "created_at": timestamp,
                "updated_at": timestamp,
                "sort": sheet_uuid,
            }
        )
        _insert_dict(connection, "schematics", schematic)
        document = dict(document_base)
        document.update(
            {
                "uuid": sheet_uuid,
                "title": "p1",
                "display_title": "P1",
                "description": "",
                "docType": 1,
                "dataStr": schematic_data,
                "sheet_id": 1,
                "ticket": 1,
                "sort_ticket": 0,
                "created_at": timestamp,
                "updated_at": timestamp,
                "schematic_uuid": schematic_uuid,
                "project_uuid": project_uuid,
                "image": None,
            }
        )
        _insert_dict(connection, "documents", document)
        if pcb.ready and pcb_uuid is not None and pcb.document_data is not None:
            pcb_document = dict(document_base)
            pcb_document.update(
                {
                    "uuid": pcb_uuid,
                    "title": "pcb",
                    "display_title": "PCB",
                    "description": "",
                    "docType": 3,
                    "dataStr": pcb.document_data,
                    "sheet_id": 1,
                    "ticket": 1,
                    "sort_ticket": 0,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "schematic_uuid": "",
                    "project_uuid": project_uuid,
                    "image": None,
                }
            )
            _insert_dict(connection, "documents", pcb_document)
            board = dict(board_base)
            board.update(
                {
                    "project_uuid": project_uuid,
                    "sch_uuid": schematic_uuid,
                    "name": circuit.title,
                    "sort": 1,
                }
            )
            board.pop("id", None)
            _insert_dict(connection, "boards", board)
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity is None or integrity[0] != "ok":
            raise NativeProjectError(f"Generated EasyEDA SQLite integrity check failed: {integrity!r}")

    manifest = {
        "schema": NATIVE_SCHEMA,
        "source": source.provenance(),
        "project": {
            "path": str(output_path),
            "project_uuid": project_uuid,
            "branch_uuid": branch_uuid,
            "schematic_uuid": schematic_uuid,
            "sheet_uuid": sheet_uuid,
            "pcb_uuid": pcb_uuid,
        },
        "packets": {
            reference: _manifest_packet(packets[item.component.identifier])
            for reference, item in ((placed_item.component.reference, placed_item) for placed_item in placed)
        },
        "terminal_packets": {
            str(terminal.packet.device["uuid"]): _manifest_packet(terminal.packet)
            for terminal in terminals
        },
        "terminal_instances": [
            {
                "net": terminal.net,
                "endpoint": terminal.endpoint,
                "x": terminal.x,
                "y": terminal.y,
                "rotation": terminal.rotation,
                "wire_points": [list(point) for point in terminal.wire_points],
                "device_uuid": str(terminal.packet.device["uuid"]),
            }
            for terminal in terminals
        ],
        "raw_library_embedded": False,
        "generated_project_rows_only": True,
    }
    return NativeWriteResult(
        project_path=output_path,
        schematic_document_uuid=sheet_uuid,
        pcb_document_uuid=pcb_uuid,
        terminal_instances=terminals,
        pcb=pcb,
        donor_manifest=manifest,
    )
