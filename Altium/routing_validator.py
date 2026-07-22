"""Independent geometry and logical-plan validation before native Altium writing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .pipeline_contracts import PlacedDesign, RoutingPlan, WireSegment
from .source_catalogue import Point
from .wire_planner import (
    is_outward_pin_escape,
    outward_escape,
    point_on_segment,
    segments_have_unsafe_contact,
)


ROUTING_VALIDATION_SCHEMA = "progen-altium-routing-validation/v1"


@dataclass(frozen=True)
class RoutingValidationReport:
    passed: bool
    routing_mode: str
    wire_count: int
    terminal_net_count: int
    label_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = ROUTING_VALIDATION_SCHEMA
        return result


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _touches_body_without_pin_escape(segment: WireSegment, design: PlacedDesign) -> str | None:
    for component in design.components:
        escape = any(
            is_outward_pin_escape(segment, point, component.pin_directions[pin], pin_is_start=True)
            or is_outward_pin_escape(segment, point, component.pin_directions[pin], pin_is_start=False)
            for pin, point in component.pins.items()
        )
        if escape:
            continue
        bounds = component.bounds.expanded(12)
        if segment.start.x == segment.end.x and bounds.min_x <= segment.start.x <= bounds.max_x:
            lower = max(min(segment.start.y, segment.end.y), bounds.min_y)
            upper = min(max(segment.start.y, segment.end.y), bounds.max_y)
            if lower <= upper:
                return component.reference
        if segment.start.y == segment.end.y and bounds.min_y <= segment.start.y <= bounds.max_y:
            lower = max(min(segment.start.x, segment.end.x), bounds.min_x)
            upper = min(max(segment.start.x, segment.end.x), bounds.max_x)
            if lower <= upper:
                return component.reference
    return None


def _segments_connect(left: WireSegment, right: WireSegment) -> bool:
    return any(
        point_on_segment(point, other)
        for point, other in (
            (left.start, right),
            (left.end, right),
            (right.start, left),
            (right.end, left),
        )
    )


def validate_routing(design: PlacedDesign, routing: RoutingPlan) -> RoutingValidationReport:
    """Validate the pure wire/terminal graph before serializing native records."""

    errors: list[str] = []
    warnings: list[str] = []
    terminalized = set(routing.terminalized_nets)
    non_nc = {net for net in design.nets if not net.startswith("NC_")}
    if routing.routing_mode == "wire" and terminalized:
        errors.append("strict wire mode contains terminalized nets")
    if routing.routing_mode == "wire" and routing.unresolved_nets:
        errors.append(
            "Strict wire mode does not terminalize failures; "
            f"unresolved nets: {list(routing.unresolved_nets)}"
        )
    if routing.routing_mode == "terminal" and terminalized != non_nc:
        errors.append("terminal mode must terminalize every non-NC net")
    if routing.routing_mode == "combination" and not terminalized.issubset(non_nc):
        errors.append("combination mode terminalizes an unknown or NC net")

    for segment in routing.wires:
        if segment.start == segment.end:
            errors.append(f"zero-length wire on {segment.net}")
        elif segment.start.x != segment.end.x and segment.start.y != segment.end.y:
            errors.append(f"non-orthogonal wire on {segment.net}")
        body = _touches_body_without_pin_escape(segment, design)
        if body:
            errors.append(f"wire on {segment.net} touches component body {body}")
    for index, left in enumerate(routing.wires):
        for right in routing.wires[index + 1 :]:
            if left.net != right.net and segments_have_unsafe_contact(left, right):
                errors.append(f"nets {left.net!r} and {right.net!r} have unsafe wire contact")

    endpoints = design.endpoint_locations()
    labels_by_net: dict[str, list[Any]] = {}
    for label in routing.labels:
        labels_by_net.setdefault(label.net, []).append(label)
        if label.net not in terminalized:
            errors.append(f"label {label.net!r} is not declared terminalized")
        point_component = endpoints.get(label.endpoint)
        if point_component is None:
            errors.append(f"label {label.net!r} has unknown endpoint {label.endpoint!r}")
            continue
        pin_point, component = point_component
        pin = label.endpoint.rsplit(".", 1)[1]
        expected = outward_escape(pin_point, component, pin, 40)
        if expected != label.location:
            errors.append(f"label {label.net!r} is not at the expected source-direction terminal point")
        if not any(
            stem.net == label.net
            and stem.start == pin_point
            and stem.end == label.location
            and is_outward_pin_escape(stem, pin_point, component.pin_directions[pin], pin_is_start=True)
            for stem in routing.wires
        ):
            errors.append(f"label {label.net!r} is not attached to its source-direction pin stem")
    for net in terminalized:
        expected_count = len(design.nets.get(net, ()))
        if len(labels_by_net.get(net, ())) != expected_count:
            errors.append(f"terminalized net {net!r} has wrong label count")

    graph = _UnionFind()
    for endpoint in endpoints:
        graph.find(endpoint)
    segment_nodes: list[tuple[str, WireSegment]] = []
    for index, segment in enumerate(routing.wires):
        start = f"segment:{index}:start"
        end = f"segment:{index}:end"
        graph.union(start, end)
        segment_nodes.append((start, segment))
    for endpoint, (point, _) in endpoints.items():
        for node, segment in segment_nodes:
            if point_on_segment(point, segment):
                graph.union(endpoint, node)
    for index, (left_node, left_segment) in enumerate(segment_nodes):
        for right_node, right_segment in segment_nodes[index + 1 :]:
            if _segments_connect(left_segment, right_segment):
                graph.union(left_node, right_node)
    for net, labels in labels_by_net.items():
        nodes: list[str] = []
        for label in labels:
            node = f"label:{label.endpoint}:{label.net}"
            nodes.append(node)
            for segment_node, segment in segment_nodes:
                if point_on_segment(label.location, segment):
                    graph.union(node, segment_node)
        for node in nodes[1:]:
            graph.union(nodes[0], node)

    roots_by_net: dict[str, set[str]] = {}
    for net, members in design.nets.items():
        roots_by_net[net] = {graph.find(endpoint) for endpoint in members}
        if net.startswith("NC_"):
            continue
        if len(members) > 1 and len(roots_by_net[net]) != 1:
            errors.append(f"routing plan does not connect expected net {net!r}")
    net_by_root: dict[str, set[str]] = {}
    for net, roots in roots_by_net.items():
        for root in roots:
            net_by_root.setdefault(root, set()).add(net)
    shorts = [sorted(nets) for nets in net_by_root.values() if len(nets) > 1]
    if shorts:
        errors.append(f"routing plan merges distinct nets: {sorted(shorts)}")

    if routing.routing_mode == "combination" and terminalized:
        warnings.append(f"combination mode terminalized {len(terminalized)} whole net(s)")
    return RoutingValidationReport(
        passed=not errors,
        routing_mode=routing.routing_mode,
        wire_count=len(routing.wires),
        terminal_net_count=len(terminalized),
        label_count=len(routing.labels),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
