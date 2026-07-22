"""Pure rectilinear wire planning for the direct Altium placed-design contract."""

from __future__ import annotations

from typing import Iterable, Mapping

from .pipeline_contracts import PipelineError, PlacedComponent, PlacedDesign, WirePlan, WireSegment
from .source_catalogue import Bounds, Point


class WirePlanningError(PipelineError):
    """The pure wire planner received an invalid placed-design contract."""


def _segment_has_invalid_body_contact(segment: WireSegment, bounds: Bounds) -> bool:
    if segment.start.x == segment.end.x:
        if not bounds.min_x <= segment.start.x <= bounds.max_x:
            return False
        lower = max(min(segment.start.y, segment.end.y), bounds.min_y)
        upper = min(max(segment.start.y, segment.end.y), bounds.max_y)
        if lower > upper:
            return False
        return True
    if segment.start.y == segment.end.y:
        if not bounds.min_y <= segment.start.y <= bounds.max_y:
            return False
        lower = max(min(segment.start.x, segment.end.x), bounds.min_x)
        upper = min(max(segment.start.x, segment.end.x), bounds.max_x)
        if lower > upper:
            return False
        return True
    return True


def is_outward_pin_escape(
    segment: WireSegment,
    pin: Point,
    direction: str,
    *,
    pin_is_start: bool,
) -> bool:
    """Recognize a short source-direction escape from or into an exact pin."""

    if pin_is_start:
        if segment.start != pin:
            return False
        dx, dy = segment.end.x - pin.x, segment.end.y - pin.y
    else:
        if segment.end != pin:
            return False
        dx, dy = segment.start.x - pin.x, segment.start.y - pin.y
    length = abs(dx) + abs(dy)
    if not 0 < length <= 80:
        return False
    return {
        "left": dx < 0 and dy == 0,
        "right": dx > 0 and dy == 0,
        "top": dx == 0 and dy < 0,
        "bottom": dx == 0 and dy > 0,
    }.get(direction, False)


def segments_intersect(left: WireSegment, right: WireSegment) -> bool:
    if left.start.x == left.end.x and right.start.x == right.end.x:
        if left.start.x != right.start.x:
            return False
        return max(min(left.start.y, left.end.y), min(right.start.y, right.end.y)) <= min(
            max(left.start.y, left.end.y), max(right.start.y, right.end.y)
        )
    if left.start.y == left.end.y and right.start.y == right.end.y:
        if left.start.y != right.start.y:
            return False
        return max(min(left.start.x, left.end.x), min(right.start.x, right.end.x)) <= min(
            max(left.start.x, left.end.x), max(right.start.x, right.end.x)
        )
    vertical = left if left.start.x == left.end.x else right
    horizontal = right if vertical is left else left
    return (
        min(horizontal.start.x, horizontal.end.x) <= vertical.start.x <= max(horizontal.start.x, horizontal.end.x)
        and min(vertical.start.y, vertical.end.y) <= horizontal.start.y <= max(vertical.start.y, vertical.end.y)
    )


def point_on_segment(point: Point, segment: WireSegment) -> bool:
    if segment.start.x == segment.end.x == point.x:
        return min(segment.start.y, segment.end.y) <= point.y <= max(segment.start.y, segment.end.y)
    if segment.start.y == segment.end.y == point.y:
        return min(segment.start.x, segment.end.x) <= point.x <= max(segment.start.x, segment.end.x)
    return False


def segments_have_unsafe_contact(left: WireSegment, right: WireSegment) -> bool:
    """Reject accidental joins/overlaps but allow a bare visual crossing."""

    if not segments_intersect(left, right):
        return False
    left_vertical = left.start.x == left.end.x
    right_vertical = right.start.x == right.end.x
    if left_vertical == right_vertical:
        return True
    return any(
        point_on_segment(point, other)
        for point, other in (
            (left.start, right),
            (left.end, right),
            (right.start, left),
            (right.end, left),
        )
    )


def outward_escape(point: Point, component: PlacedComponent, pin: str, amount: int) -> Point:
    """Follow audited source pin direction rather than inferring from bounds."""

    direction = component.pin_directions[pin]
    if direction == "left":
        return Point(point.x - amount, point.y)
    if direction == "right":
        return Point(point.x + amount, point.y)
    if direction == "top":
        return Point(point.x, point.y - amount)
    return Point(point.x, point.y + amount)


def _deduplicate_points(points: Iterable[Point]) -> tuple[Point, ...]:
    result: list[Point] = []
    for point in points:
        if not result or result[-1] != point:
            result.append(point)
    return tuple(result)


def _points_to_segments(net: str, points: Iterable[Point]) -> tuple[WireSegment, ...]:
    compact = _deduplicate_points(points)
    segments = tuple(
        WireSegment(net, start, end)
        for start, end in zip(compact, compact[1:])
        if start != end
    )
    if any(segment.start.x != segment.end.x and segment.start.y != segment.end.y for segment in segments):
        raise WirePlanningError("Internal route construction produced a diagonal segment.")
    return segments


def _path_is_clear(
    candidate: tuple[WireSegment, ...],
    *,
    source: PlacedComponent,
    target: PlacedComponent,
    components: tuple[PlacedComponent, ...],
    existing: tuple[WireSegment, ...],
) -> bool:
    if not candidate:
        return False
    source_pin = next((pin for pin, point in source.pins.items() if point == candidate[0].start), None)
    target_pin = next((pin for pin, point in target.pins.items() if point == candidate[-1].end), None)
    if source_pin is None or target_pin is None:
        return False
    for segment in candidate:
        for component in components:
            source_escape = (
                component.reference == source.reference
                and segment == candidate[0]
                and is_outward_pin_escape(
                    segment,
                    source.pins[source_pin],
                    source.pin_directions[source_pin],
                    pin_is_start=True,
                )
            )
            target_escape = (
                component.reference == target.reference
                and segment == candidate[-1]
                and is_outward_pin_escape(
                    segment,
                    target.pins[target_pin],
                    target.pin_directions[target_pin],
                    pin_is_start=False,
                )
            )
            if source_escape or target_escape:
                continue
            if _segment_has_invalid_body_contact(segment, component.bounds.expanded(12)):
                return False
        for previous in existing:
            if previous.net != segment.net and segments_have_unsafe_contact(segment, previous):
                return False
    return True


def _perpendicular_offset(point: Point, direction: str, offset: int) -> Point:
    if direction in {"left", "right"}:
        return Point(point.x, point.y + offset)
    return Point(point.x + offset, point.y)


def _pin_port_options(
    point: Point,
    component: PlacedComponent,
    pin: str,
) -> tuple[tuple[Point, Point, Point], ...]:
    direction = component.pin_directions[pin]
    escape = outward_escape(point, component, pin, 40)
    options: list[tuple[Point, Point, Point]] = []
    for offset in (0, -64, 64, -112, 112):
        jog = _perpendicular_offset(escape, direction, offset)
        channel = outward_escape(jog, component, pin, 32)
        options.append((escape, jog, channel))
    return tuple(options)


def _candidate_paths(
    net: str,
    start: Point,
    end: Point,
    source: PlacedComponent,
    source_pin: str,
    target: PlacedComponent,
    target_pin: str,
    components: tuple[PlacedComponent, ...],
) -> tuple[tuple[WireSegment, ...], ...]:
    start_ports = _pin_port_options(start, source, source_pin)
    end_ports = _pin_port_options(end, target, target_pin)
    left = min(component.bounds.min_x for component in components) - 80
    right = max(component.bounds.max_x for component in components) + 80
    top = min(component.bounds.min_y for component in components) - 80
    bottom = max(component.bounds.max_y for component in components) + 80
    candidates: list[tuple[WireSegment, ...]] = []
    seen: set[tuple[WireSegment, ...]] = set()

    def add(points: Iterable[Point]) -> None:
        candidate = _points_to_segments(net, points)
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    for start_escape, start_jog, start_channel in start_ports:
        for end_escape, end_jog, end_channel in end_ports:
            start_prefix = (start, start_escape, start_jog, start_channel)
            end_suffix = (end_channel, end_jog, end_escape, end)
            add((*start_prefix, Point(end_channel.x, start_channel.y), *end_suffix))
            add((*start_prefix, Point(start_channel.x, end_channel.y), *end_suffix))
            for lane in (
                left,
                right,
                start_channel.x - 60,
                start_channel.x + 60,
                end_channel.x - 60,
                end_channel.x + 60,
            ):
                add((*start_prefix, Point(lane, start_channel.y), Point(lane, end_channel.y), *end_suffix))
            for lane in (
                top,
                bottom,
                start_channel.y - 60,
                start_channel.y + 60,
                end_channel.y - 60,
                end_channel.y + 60,
            ):
                add((*start_prefix, Point(start_channel.x, lane), Point(end_channel.x, lane), *end_suffix))
    return tuple(candidates)


def _ordered_nets(
    nets: Mapping[str, tuple[str, ...]],
    endpoints: Mapping[str, tuple[Point, PlacedComponent]],
) -> list[tuple[str, tuple[str, ...]]]:
    return sorted(
        nets.items(),
        key=lambda item: (
            len(item[1]),
            sum(
                abs(endpoints[item[1][0]][0].x - endpoints[member][0].x)
                + abs(endpoints[item[1][0]][0].y - endpoints[member][0].y)
                for member in item[1][1:]
            ),
            item[0],
        ),
    )


def _route_one_net(
    net: str,
    members: tuple[str, ...],
    *,
    design: PlacedDesign,
    endpoints: Mapping[str, tuple[Point, PlacedComponent]],
    existing: tuple[WireSegment, ...],
) -> tuple[WireSegment, ...] | None:
    if len(members) < 2:
        return None
    values: list[tuple[str, Point, PlacedComponent]] = []
    for endpoint in members:
        try:
            point, component = endpoints[endpoint]
        except KeyError as exc:
            raise WirePlanningError(f"Net {net!r} refers to absent endpoint {endpoint!r}.") from exc
        values.append((endpoint, point, component))
    values.sort(key=lambda item: item[0])
    anchor_name, anchor_point, anchor_component = values[0]
    local: list[WireSegment] = []
    for endpoint_name, point, component in values[1:]:
        options = _candidate_paths(
            net,
            anchor_point,
            point,
            anchor_component,
            anchor_name.rsplit(".", 1)[1],
            component,
            endpoint_name.rsplit(".", 1)[1],
            design.components,
        )
        selected = next(
            (
                option
                for option in options
                if _path_is_clear(
                    option,
                    source=anchor_component,
                    target=component,
                    components=design.components,
                    existing=(*existing, *local),
                )
            ),
            None,
        )
        if selected is None:
            return None
        local.extend(selected)
    return tuple(local)


def plan_wires(
    design: PlacedDesign,
    routing_mode: str,
    *,
    forced_terminal_nets: tuple[str, ...] = (),
) -> WirePlan:
    """Plan physical wires only; terminal fallback is owned by another stage."""

    if routing_mode not in {"wire", "terminal", "combination"}:
        raise WirePlanningError(f"Unsupported routing mode {routing_mode!r}.")
    endpoints = design.endpoint_locations()
    forced = set(forced_terminal_nets)
    unknown_forced = sorted(forced - set(design.nets))
    if unknown_forced:
        raise WirePlanningError(f"Routing decision forced unknown terminal nets: {unknown_forced}")
    wires: list[WireSegment] = []
    routed: list[str] = []
    unresolved: list[str] = []
    skipped: list[str] = []
    for net, members in _ordered_nets(design.nets, endpoints):
        if net.startswith("NC_"):
            skipped.append(net)
            continue
        if routing_mode == "terminal":
            unresolved.append(net)
            continue
        if net in forced:
            unresolved.append(net)
            continue
        route = _route_one_net(net, members, design=design, endpoints=endpoints, existing=tuple(wires))
        if route is None:
            unresolved.append(net)
            continue
        wires.extend(route)
        routed.append(net)
    return WirePlan(
        routing_mode=routing_mode,
        wires=tuple(wires),
        routed_nets=tuple(sorted(routed)),
        unresolved_nets=tuple(sorted(unresolved)),
        skipped_nc_nets=tuple(sorted(skipped)),
    )
