"""Native EasyEDA Pro SQLite project emitter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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
    inflate,
    points_to_segments,
    rects_overlap,
    rotate_point,
    segment_hits_rect,
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
    wire_start: Point


@dataclass(frozen=True)
class PcbResult:
    ready: bool
    reason: str
    document_data: str | None
    component_count: int
    track_count: int
    placements: dict[str, tuple[float, float]]
    pad_points: dict[str, Point]


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
    distances = {
        "left": abs(point[0] - left),
        "right": abs(point[0] - right),
        "top": abs(point[1] - top),
        "bottom": abs(point[1] - bottom),
    }
    side = min(distances, key=distances.get)
    if side == "left":
        return "in", 0, (point[0] - 35.0, point[1])
    if side == "right":
        return "out", 0, (point[0] + 35.0, point[1])
    if side == "top":
        return "out", 270, (point[0], point[1] - 35.0)
    return "out", 90, (point[0], point[1] + 35.0)


def _build_terminals(
    source: EasyedaDonorSource,
    routed: tuple[RoutedNet, ...],
    placed: tuple[PlacedComponent, ...],
) -> tuple[TerminalInstance, ...]:
    endpoints = _endpoint_map(placed)
    packets: dict[str, DonorPacket] = {}
    result: list[TerminalInstance] = []
    occupied: list[Rect] = [inflate(item.body, 8.0) for item in placed]
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
            packet = packets.setdefault(direction, source.resolve_terminal_port(direction=direction))
            candidate = target
            for attempt in range(12):
                body_left, body_top, body_right, body_bottom = packet.body_bbox
                local = [
                    rotate_point((body_left, body_top), rotation),
                    rotate_point((body_right, body_top), rotation),
                    rotate_point((body_right, body_bottom), rotation),
                    rotate_point((body_left, body_bottom), rotation),
                ]
                rect = (
                    min(candidate[0] + value[0] for value in local),
                    min(candidate[1] + value[1] for value in local),
                    max(candidate[0] + value[0] for value in local),
                    max(candidate[1] + value[1] for value in local),
                )
                if not any(rects_overlap(inflate(rect, 4.0), other) for other in occupied):
                    occupied.append(inflate(rect, 4.0))
                    break
                shift = (attempt // 2 + 1) * 18.0 * (1 if attempt % 2 == 0 else -1)
                if rotation in {0, 180}:
                    candidate = (target[0], target[1] + shift)
                else:
                    candidate = (target[0] + shift, target[1])
            result.append(
                TerminalInstance(
                    net=net.name,
                    endpoint=endpoint,
                    packet=packet,
                    x=round(candidate[0], 3),
                    y=round(candidate[1], 3),
                    rotation=rotation,
                    wire_start=point,
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
    start_x, start_y = terminal.wire_start
    if start_x == terminal.x or start_y == terminal.y:
        geometry = [[start_x, start_y, terminal.x, terminal.y]]
    else:
        geometry = [
            [start_x, start_y, terminal.x, start_y],
            [terminal.x, start_y, terminal.x, terminal.y],
        ]
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
            (terminal.wire_start[0] + terminal.x) / 2,
            (terminal.wire_start[1] + terminal.y) / 2,
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
    rotated = [rotate_point(point, rotation) for point in packet.footprint_pads.values()]
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


def build_pcb_data(
    source: EasyedaDonorSource,
    circuit: Circuit,
    placed: tuple[PlacedComponent, ...],
) -> PcbResult:
    physical = [item for item in placed if item.component.kind not in {"GND", "VCC"}]
    if not physical:
        return PcbResult(False, "no_physical_components", None, 0, 0, {}, {})
    if len(physical) > 24:
        return PcbResult(False, "basic_pcb_component_limit_24", None, len(physical), 0, {}, {})
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

    placements: dict[str, tuple[float, float]] = {}
    rotations: dict[str, int] = {
        item.component.reference: (
            180 if item.component.kind in {"DIODE", "1N4007", "1N4148"} else 0
        )
        for item in physical
    }
    rects: dict[str, Rect] = {}
    x = 400.0
    y = -400.0
    row_height = 0.0
    max_width = 3600.0
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
        x += width + 260.0
        row_height = max(row_height, height)

    endpoint_lookup: dict[str, Point] = {}
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
    for net, members in sorted(circuit.nets.items(), key=lambda item: (-len(item[1]), item[0])):
        pads = [endpoint_lookup[endpoint] for endpoint in members if endpoint in endpoint_lookup]
        if len(pads) < 2:
            continue
        upper_name = net.upper()
        is_ground = upper_name in {"GND", "VSS", "GROUND"}
        is_positive_power = upper_name in {"VCC", "VDD", "+5V", "5V", "+3V3", "3V3"}
        if is_ground or is_positive_power:
            rail_y = envelope[3] + 180.0 + lane * 35.0 if is_ground else envelope[1] - 180.0 - lane * 35.0
            min_x = min(point[0] for point in pads)
            max_x = max(point[0] for point in pads)
            tracks.append((net, 2, (min_x, rail_y), (max_x, rail_y)))
            for point in pads:
                tracks.append((net, 2, point, (point[0], rail_y)))
                via_points.add((net, point))
            lane += 1
            continue
        root = pads[0]
        chosen_layer: int | None = None
        chosen_segments: list[tuple[Point, Point]] = []
        for layer in (1, 2):
            trial: list[tuple[Point, Point]] = []
            trial_existing = list(tracks)
            succeeded = True
            for branch_index, end in enumerate(pads[1:]):
                if layer == 1:
                    obstacles = [inflate(rect, 20.0) for rect in all_rects]
                else:
                    obstacles = [
                        (point[0] - 28, point[1] - 28, point[0] + 28, point[1] + 28)
                        for endpoint, point in endpoint_lookup.items()
                        if pad_net.get(endpoint) != net
                    ]
                segments = _pcb_route(
                    root,
                    end,
                    obstacles,
                    envelope,
                    lane + branch_index,
                    trial_existing,
                    net,
                    layer,
                )
                if segments is None:
                    succeeded = False
                    break
                trial.extend(segments)
                trial_existing.extend((net, layer, start, finish) for start, finish in segments)
            if succeeded:
                chosen_layer = layer
                chosen_segments = trial
                break
        lane += len(pads) - 1
        if chosen_layer is None:
            return PcbResult(False, f"pcb_unroutable:{net}", None, len(physical), len(tracks), placements, endpoint_lookup)
        tracks.extend((net, chosen_layer, start, finish) for start, finish in chosen_segments)
        if chosen_layer == 2:
            via_points.update((net, point) for point in pads)

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
        rows.append(["LINE", ids.next(), 0, net, layer, start[0], start[1], end[0], end[1], 12, 0])
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
