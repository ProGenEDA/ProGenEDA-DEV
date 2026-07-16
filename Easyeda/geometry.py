"""Deterministic placement and routing geometry for EasyEDA records."""

from __future__ import annotations

from dataclasses import dataclass
import heapq
import math
from typing import Iterable

from .donor_source import DonorPacket, PinDescriptor
from .ir import Circuit, CircuitComponent, resolve_pin


Point = tuple[float, float]
Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class PlacedComponent:
    component: CircuitComponent
    packet: DonorPacket
    x: float
    y: float
    rotation: int
    body: Rect
    pins: dict[str, Point]
    source_pins: dict[str, PinDescriptor]


@dataclass(frozen=True)
class RoutedNet:
    name: str
    segments: tuple[tuple[Point, Point], ...]
    terminalized: bool
    endpoints: tuple[str, ...]
    reason: str


def _normalize_bbox(bbox: tuple[float, float, float, float]) -> Rect:
    x1, y1, x2, y2 = bbox
    return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)


def rotate_point(point: Point, rotation: int) -> Point:
    x, y = point
    angle = rotation % 360
    if angle == 0:
        return x, y
    if angle == 90:
        return -y, x
    if angle == 180:
        return -x, -y
    if angle == 270:
        return y, -x
    radians = math.radians(angle)
    return x * math.cos(radians) - y * math.sin(radians), x * math.sin(radians) + y * math.cos(radians)


def transform_point(point: Point, x: float, y: float, rotation: int) -> Point:
    local_x, local_y = rotate_point(point, rotation)
    return round(x + local_x, 6), round(y + local_y, 6)


def transform_rect(bbox: Rect, x: float, y: float, rotation: int) -> Rect:
    left, top, right, bottom = _normalize_bbox(bbox)
    points = [
        transform_point((left, top), x, y, rotation),
        transform_point((right, top), x, y, rotation),
        transform_point((right, bottom), x, y, rotation),
        transform_point((left, bottom), x, y, rotation),
    ]
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def inflate(rect: Rect, amount: float) -> Rect:
    left, top, right, bottom = rect
    return left - amount, top - amount, right + amount, bottom + amount


def rects_overlap(first: Rect, second: Rect, *, touch_is_overlap: bool = True) -> bool:
    a_left, a_top, a_right, a_bottom = first
    b_left, b_top, b_right, b_bottom = second
    if touch_is_overlap:
        return not (a_right < b_left or b_right < a_left or a_bottom < b_top or b_bottom < a_top)
    return not (a_right <= b_left or b_right <= a_left or a_bottom <= b_top or b_bottom <= a_top)


def _choose_rotation(packet: DonorPacket) -> int:
    left, top, right, bottom = _normalize_bbox(packet.body_bbox)
    width = right - left
    height = bottom - top
    return 90 if width > height * 2.4 and width > 75 else 0


def place_components(circuit: Circuit, packets: dict[str, DonorPacket]) -> tuple[PlacedComponent, ...]:
    """Shelf-pack source bodies into a compact square-like schematic."""

    prepared: list[
        tuple[CircuitComponent, DonorPacket, int, float, float, float, float]
    ] = []
    total_area = 0.0
    for component in circuit.components:
        packet = packets[component.identifier]
        rotation = _choose_rotation(packet)
        left, top, right, bottom = transform_rect(packet.body_bbox, 0, 0, rotation)
        width = max(30.0, right - left)
        height = max(30.0, bottom - top)
        pin_pressure = max(0, len({pin.number for pin in packet.pins}) - 4)
        horizontal_halo = min(440.0, 240.0 + pin_pressure * 7.0)
        vertical_halo = min(300.0, 190.0 + pin_pressure * 4.0)
        prepared.append(
            (
                component,
                packet,
                rotation,
                width,
                height,
                horizontal_halo,
                vertical_halo,
            )
        )
        total_area += (width + horizontal_halo) * (height + vertical_halo)
    target_width = max(700.0, min(3600.0, math.sqrt(total_area) * 1.35))
    cursor_x = 160.0
    cursor_y = 160.0
    row_height = 0.0
    placed: list[PlacedComponent] = []
    for component, packet, rotation, width, height, horizontal_halo, vertical_halo in prepared:
        if cursor_x > 160 and cursor_x + width + horizontal_halo > target_width:
            cursor_x = 160.0
            cursor_y += row_height
            row_height = 0.0
        local_left, local_top, _, _ = transform_rect(packet.body_bbox, 0, 0, rotation)
        x = round(cursor_x - local_left, 3)
        y = round(cursor_y - local_top, 3)
        body = transform_rect(packet.body_bbox, x, y, rotation)
        pins: dict[str, Point] = {}
        source_pins: dict[str, PinDescriptor] = {}
        for requested in component.pins:
            descriptor = resolve_pin(packet, requested)
            pins[requested] = transform_point((descriptor.x, descriptor.y), x, y, rotation)
            source_pins[requested] = descriptor
        placed.append(
            PlacedComponent(
                component=component,
                packet=packet,
                x=x,
                y=y,
                rotation=rotation,
                body=body,
                pins=pins,
                source_pins=source_pins,
            )
        )
        cursor_x += width + horizontal_halo
        row_height = max(row_height, height + vertical_halo)
    return tuple(placed)


def _point_in_rect(point: Point, rect: Rect, *, strict: bool = False) -> bool:
    x, y = point
    left, top, right, bottom = rect
    if strict:
        return left < x < right and top < y < bottom
    return left <= x <= right and top <= y <= bottom


def segment_hits_rect(start: Point, end: Point, rect: Rect) -> bool:
    """Return true when an orthogonal segment enters or lies on a body."""

    left, top, right, bottom = rect
    x1, y1 = start
    x2, y2 = end
    if abs(y1 - y2) < 1e-6:
        low, high = sorted((x1, x2))
        return top <= y1 <= bottom and high >= left and low <= right
    if abs(x1 - x2) < 1e-6:
        low, high = sorted((y1, y2))
        return left <= x1 <= right and high >= top and low <= bottom
    return True


def simplify_points(points: Iterable[Point]) -> tuple[Point, ...]:
    result: list[Point] = []
    for point in points:
        rounded = (round(point[0], 6), round(point[1], 6))
        if result and rounded == result[-1]:
            continue
        if len(result) >= 2:
            a = result[-2]
            b = result[-1]
            if (a[0] == b[0] == rounded[0]) or (a[1] == b[1] == rounded[1]):
                result[-1] = rounded
                continue
        result.append(rounded)
    return tuple(result)


def points_to_segments(points: Iterable[Point]) -> tuple[tuple[Point, Point], ...]:
    cleaned = simplify_points(points)
    return tuple((first, second) for first, second in zip(cleaned, cleaned[1:]) if first != second)


def segments_collinear_overlap(
    first_start: Point,
    first_end: Point,
    second_start: Point,
    second_end: Point,
    *,
    tolerance: float = 1e-6,
) -> bool:
    """Return true only when two orthogonal segments share a positive-length span."""

    first_horizontal = abs(first_start[1] - first_end[1]) <= tolerance
    second_horizontal = abs(second_start[1] - second_end[1]) <= tolerance
    if first_horizontal and second_horizontal:
        if abs(first_start[1] - second_start[1]) > tolerance:
            return False
        overlap = min(
            max(first_start[0], first_end[0]),
            max(second_start[0], second_end[0]),
        ) - max(
            min(first_start[0], first_end[0]),
            min(second_start[0], second_end[0]),
        )
        return overlap > tolerance
    first_vertical = abs(first_start[0] - first_end[0]) <= tolerance
    second_vertical = abs(second_start[0] - second_end[0]) <= tolerance
    if first_vertical and second_vertical:
        if abs(first_start[0] - second_start[0]) > tolerance:
            return False
        overlap = min(
            max(first_start[1], first_end[1]),
            max(second_start[1], second_end[1]),
        ) - max(
            min(first_start[1], first_end[1]),
            min(second_start[1], second_end[1]),
        )
        return overlap > tolerance
    return False


class WireSpanIndex:
    """Coordinate-indexed positive-length spans reserved by emitted nets."""

    def __init__(self) -> None:
        self.horizontal: dict[
            float,
            list[tuple[str, float, float, Point, Point]],
        ] = {}
        self.vertical: dict[
            float,
            list[tuple[str, float, float, Point, Point]],
        ] = {}
        self.entries: list[tuple[str, float]] = []

    def checkpoint(self) -> int:
        return len(self.entries)

    def add(self, net_name: str, start: Point, end: Point) -> None:
        if abs(start[1] - end[1]) <= 1e-6:
            key = round(start[1], 6)
            self.horizontal.setdefault(key, []).append(
                (
                    net_name,
                    min(start[0], end[0]),
                    max(start[0], end[0]),
                    start,
                    end,
                )
            )
            self.entries.append(("horizontal", key))
        elif abs(start[0] - end[0]) <= 1e-6:
            key = round(start[0], 6)
            self.vertical.setdefault(key, []).append(
                (
                    net_name,
                    min(start[1], end[1]),
                    max(start[1], end[1]),
                    start,
                    end,
                )
            )
            self.entries.append(("vertical", key))

    def find_overlap(
        self,
        segments: Iterable[tuple[Point, Point]],
        net_name: str,
    ) -> tuple[str, Point, Point, Point, Point] | None:
        for start, end in segments:
            if abs(start[1] - end[1]) <= 1e-6:
                spans = self.horizontal.get(round(start[1], 6), ())
                low, high = sorted((start[0], end[0]))
            elif abs(start[0] - end[0]) <= 1e-6:
                spans = self.vertical.get(round(start[0], 6), ())
                low, high = sorted((start[1], end[1]))
            else:
                continue
            for other_net, other_low, other_high, other_start, other_end in spans:
                if (
                    other_net != net_name
                    and min(high, other_high) - max(low, other_low) > 1e-6
                ):
                    return other_net, start, end, other_start, other_end
        return None

    def overlaps(
        self,
        segments: Iterable[tuple[Point, Point]],
        net_name: str,
    ) -> bool:
        return self.find_overlap(segments, net_name) is not None

    def rollback(self, checkpoint: int) -> None:
        while len(self.entries) > checkpoint:
            orientation, key = self.entries.pop()
            target = (
                self.horizontal
                if orientation == "horizontal"
                else self.vertical
            )
            target[key].pop()
            if not target[key]:
                del target[key]


def _path_clear(
    points: tuple[Point, ...],
    obstacles: Iterable[Rect],
    *,
    allowed_start: Point,
    allowed_end: Point,
) -> bool:
    for start, end in points_to_segments(points):
        for obstacle in obstacles:
            if not segment_hits_rect(start, end, obstacle):
                continue
            start_allowed = start == allowed_start and _point_in_rect(start, obstacle)
            end_allowed = end == allowed_end and _point_in_rect(end, obstacle)
            if start_allowed or end_allowed:
                continue
            return False
    return True


def _candidate_paths(start: Point, end: Point, envelope: Rect, lane_index: int) -> tuple[tuple[Point, ...], ...]:
    left, top, right, bottom = envelope
    offset = 35.0 + lane_index * 12.0
    nudge = 12.0 + (lane_index % 24) * 6.0
    return (
        (start, (end[0], start[1]), end),
        (start, (start[0], end[1]), end),
        (start, (start[0], top - offset), (end[0], top - offset), end),
        (start, (start[0], bottom + offset), (end[0], bottom + offset), end),
        (start, (left - offset, start[1]), (left - offset, end[1]), end),
        (start, (right + offset, start[1]), (right + offset, end[1]), end),
        (
            start,
            (start[0] + nudge, start[1]),
            (start[0] + nudge, top - offset),
            (end[0] - nudge, top - offset),
            (end[0] - nudge, end[1]),
            end,
        ),
        (
            start,
            (start[0] - nudge, start[1]),
            (start[0] - nudge, bottom + offset),
            (end[0] + nudge, bottom + offset),
            (end[0] + nudge, end[1]),
            end,
        ),
        (
            start,
            (start[0], start[1] + nudge),
            (left - offset, start[1] + nudge),
            (left - offset, end[1] - nudge),
            (end[0], end[1] - nudge),
            end,
        ),
        (
            start,
            (start[0], start[1] - nudge),
            (right + offset, start[1] - nudge),
            (right + offset, end[1] + nudge),
            (end[0], end[1] + nudge),
            end,
        ),
    )


def _pin_escape(point: Point, body: Rect, distance: float = 18.0) -> Point:
    left, top, right, bottom = body
    outside = {
        "left": left - point[0],
        "right": point[0] - right,
        "top": top - point[1],
        "bottom": point[1] - bottom,
    }
    outside = {side: amount for side, amount in outside.items() if amount > 0}
    if outside:
        side = max(outside, key=outside.get)
    else:
        distances = {
            "left": abs(point[0] - left),
            "right": abs(point[0] - right),
            "top": abs(point[1] - top),
            "bottom": abs(point[1] - bottom),
        }
        side = min(distances, key=distances.get)
    if side == "left":
        return round(min(point[0], left) - distance, 6), point[1]
    if side == "right":
        return round(max(point[0], right) + distance, 6), point[1]
    if side == "top":
        return point[0], round(min(point[1], top) - distance, 6)
    return point[0], round(max(point[1], bottom) + distance, 6)


def _visibility_route(
    start: Point,
    end: Point,
    obstacles: list[Rect],
    envelope: Rect,
    lane_index: int,
) -> tuple[tuple[Point, Point], ...] | None:
    """Find an orthogonal obstacle-free path on a sparse visibility grid."""

    left, top, right, bottom = envelope
    outer = 45.0 + lane_index * 4.0
    xs = {start[0], end[0], left - outer, right + outer}
    ys = {start[1], end[1], top - outer, bottom + outer}
    for obstacle in obstacles:
        xs.update((obstacle[0] - 12.0, obstacle[2] + 12.0))
        ys.update((obstacle[1] - 12.0, obstacle[3] + 12.0))
    ordered_x = sorted(xs)
    ordered_y = sorted(ys)
    nodes = {
        (x, y)
        for x in ordered_x
        for y in ordered_y
        if (x, y) in {start, end} or not any(_point_in_rect((x, y), obstacle) for obstacle in obstacles)
    }
    if start not in nodes or end not in nodes:
        return None
    x_index = {value: index for index, value in enumerate(ordered_x)}
    y_index = {value: index for index, value in enumerate(ordered_y)}

    def neighbors(point: Point) -> Iterable[Point]:
        x, y = point
        candidates: list[Point] = []
        xi = x_index[x]
        yi = y_index[y]
        if xi > 0:
            candidates.append((ordered_x[xi - 1], y))
        if xi + 1 < len(ordered_x):
            candidates.append((ordered_x[xi + 1], y))
        if yi > 0:
            candidates.append((x, ordered_y[yi - 1]))
        if yi + 1 < len(ordered_y):
            candidates.append((x, ordered_y[yi + 1]))
        for candidate in candidates:
            if candidate not in nodes:
                continue
            blocked = False
            for obstacle in obstacles:
                if not segment_hits_rect(point, candidate, obstacle):
                    continue
                if (point == start and _point_in_rect(point, obstacle)) or (
                    candidate == end and _point_in_rect(candidate, obstacle)
                ):
                    continue
                blocked = True
                break
            if not blocked:
                yield candidate

    queue: list[tuple[float, float, Point]] = [(0.0, 0.0, start)]
    cost: dict[Point, float] = {start: 0.0}
    previous: dict[Point, Point] = {}
    while queue:
        _, current_cost, current = heapq.heappop(queue)
        if current == end:
            path: list[Point] = [end]
            while path[-1] != start:
                path.append(previous[path[-1]])
            path.reverse()
            return points_to_segments(path)
        if current_cost != cost.get(current):
            continue
        for candidate in neighbors(current):
            new_cost = current_cost + abs(candidate[0] - current[0]) + abs(candidate[1] - current[1])
            if new_cost >= cost.get(candidate, math.inf):
                continue
            cost[candidate] = new_cost
            previous[candidate] = current
            heuristic = abs(end[0] - candidate[0]) + abs(end[1] - candidate[1])
            heapq.heappush(queue, (new_cost + heuristic, new_cost, candidate))
    return None


def route_nets(
    circuit: Circuit,
    placed: tuple[PlacedComponent, ...],
    *,
    high_fanout_threshold: int = 5,
) -> tuple[RoutedNet, ...]:
    by_reference = {item.component.reference: item for item in placed}
    obstacles = [inflate(item.body, 8.0) for item in placed if item.component.kind not in {"GND", "VCC"}]
    all_bodies = [item.body for item in placed]
    envelope = (
        min(rect[0] for rect in all_bodies) - 20,
        min(rect[1] for rect in all_bodies) - 20,
        max(rect[2] for rect in all_bodies) + 20,
        max(rect[3] for rect in all_bodies) + 20,
    )
    routed: list[RoutedNet] = []
    reserved_segments = WireSpanIndex()
    lane_index = 0
    for net_name, members in sorted(circuit.nets.items(), key=lambda item: (-len(item[1]), item[0])):
        resolved: list[tuple[str, Point, Point]] = []
        for endpoint in members:
            if "." not in endpoint:
                continue
            reference, requested_pin = endpoint.rsplit(".", 1)
            item = by_reference.get(reference)
            if item is None or requested_pin not in item.pins:
                continue
            point = item.pins[requested_pin]
            resolved.append((endpoint, point, _pin_escape(point, item.body)))
        if len(resolved) < 2:
            routed.append(
                RoutedNet(
                    net_name,
                    (),
                    True,
                    tuple(endpoint for endpoint, _, _ in resolved),
                    "single_endpoint",
                )
            )
            continue
        power = net_name.upper() in {"GND", "VCC", "+5V", "5V", "+3V3", "3V3", "VDD", "VSS"}
        shared_power_terminal = circuit.routing_mode == "combination" and power
        policy_terminal = circuit.routing_mode == "terminal" or (
            circuit.routing_mode == "combination"
            and not shared_power_terminal
            and len(resolved) > high_fanout_threshold
        )
        if policy_terminal:
            reason = "terminal_mode" if circuit.routing_mode == "terminal" else "high_fanout"
            routed.append(
                RoutedNet(
                    net_name,
                    (),
                    True,
                    tuple(endpoint for endpoint, _, _ in resolved),
                    reason,
                )
            )
            continue
        root_endpoint, root_point, root_escape = resolved[0]
        other_pin_obstacles = [
            (
                pin_point[0] - 5.0,
                pin_point[1] - 5.0,
                pin_point[0] + 5.0,
                pin_point[1] + 5.0,
            )
            for item in placed
            for requested, pin_point in item.pins.items()
            if f"{item.component.reference}.{requested}" not in members
        ]
        net_obstacles = obstacles + other_pin_obstacles
        net_segments: list[tuple[Point, Point]] = []
        reserved_before_net = reserved_segments.checkpoint()
        failed = False
        for endpoint, point, escape in resolved[1:]:
            branch: tuple[tuple[Point, Point], ...] | None = None
            lane_attempts = 0
            lane_limit = 32 if circuit.routing_mode == "combination" else 128
            for lane_attempts in range(lane_limit):
                candidate_lane = lane_index + lane_attempts
                for candidate in _candidate_paths(
                    root_escape,
                    escape,
                    envelope,
                    candidate_lane,
                ):
                    candidate_segments = points_to_segments(candidate)
                    candidate_branch = (
                        (root_point, root_escape),
                        *candidate_segments,
                        (escape, point),
                    )
                    if not _path_clear(
                        candidate,
                        net_obstacles,
                        allowed_start=root_escape,
                        allowed_end=escape,
                    ) or reserved_segments.overlaps(
                        candidate_branch,
                        net_name,
                    ):
                        continue
                    branch = candidate_branch
                    break
                if branch is not None:
                    break
            if branch is None:
                visibility_attempts = 0 if circuit.routing_mode == "combination" else 16
                for visibility_attempt in range(visibility_attempts):
                    found = _visibility_route(
                        root_escape,
                        escape,
                        net_obstacles,
                        envelope,
                        lane_index + visibility_attempt,
                    )
                    if found is None:
                        continue
                    candidate_branch = (
                        (root_point, root_escape),
                        *found,
                        (escape, point),
                    )
                    if reserved_segments.overlaps(
                        candidate_branch,
                        net_name,
                    ):
                        continue
                    branch = candidate_branch
                    break
            lane_index += lane_attempts + 1
            if branch is None:
                failed = True
                break
            for segment in branch:
                if segment not in net_segments:
                    net_segments.append(segment)
                reserved_segments.add(net_name, *segment)
        if failed and circuit.routing_mode != "wire":
            reserved_segments.rollback(reserved_before_net)
        if failed:
            if circuit.routing_mode == "wire":
                routed.append(
                    RoutedNet(
                        net_name,
                        tuple(net_segments),
                        False,
                        tuple(endpoint for endpoint, _, _ in resolved),
                        "unroutable",
                    )
                )
            else:
                routed.append(
                    RoutedNet(
                        net_name,
                        (),
                        True,
                        tuple(endpoint for endpoint, _, _ in resolved),
                        "router_fallback",
                    )
                )
        else:
            routed.append(
                RoutedNet(
                    net_name,
                    tuple(net_segments),
                    shared_power_terminal,
                    tuple(endpoint for endpoint, _, _ in resolved),
                    "shared_power_terminal" if shared_power_terminal else "routed",
                )
            )
    return tuple(routed)
