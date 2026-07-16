"""Independent hosted validation for generated KiCad PCBs."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .footprint_placer import PCBPlacement
from .kicad_pcb_parser import ParsedPad, ParsedPCB, ParsedSegment, parse_kicad_pcb
from .pcb_router import PCBRoutePlan
from .physical_design_compiler import PhysicalDesign


VALIDATION_SCHEMA = "progen-kicad-pcb-validation/v0.1"
Node = tuple[float, float, str]


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[Node, Node] = {}

    def find(self, item: Node) -> Node:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, left: Node, right: Node) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _node(point: tuple[float, float], layer: str) -> Node:
    return (round(point[0], 4), round(point[1], 4), layer)


def _orientation(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(point: tuple[float, float], segment: ParsedSegment, tolerance: float = 1e-4) -> bool:
    if abs(_orientation(segment.start, segment.end, point)) > tolerance:
        return False
    return (
        min(segment.start[0], segment.end[0]) - tolerance <= point[0] <= max(segment.start[0], segment.end[0]) + tolerance
        and min(segment.start[1], segment.end[1]) - tolerance <= point[1] <= max(segment.start[1], segment.end[1]) + tolerance
    )


def _segments_intersect(left: ParsedSegment, right: ParsedSegment) -> bool:
    if left.layer != right.layer:
        return False
    o1 = _orientation(left.start, left.end, right.start)
    o2 = _orientation(left.start, left.end, right.end)
    o3 = _orientation(right.start, right.end, left.start)
    o4 = _orientation(right.start, right.end, left.end)
    tolerance = 1e-6
    if ((o1 > tolerance and o2 < -tolerance) or (o1 < -tolerance and o2 > tolerance)) and (
        (o3 > tolerance and o4 < -tolerance) or (o3 < -tolerance and o4 > tolerance)
    ):
        return True
    return any(
        abs(value) <= tolerance and on_segment
        for value, on_segment in (
            (o1, _on_segment(right.start, left)),
            (o2, _on_segment(right.end, left)),
            (o3, _on_segment(left.start, right)),
            (o4, _on_segment(left.end, right)),
        )
    )


def _connectivity(parsed: ParsedPCB) -> tuple[_UnionFind, dict[str, list[ParsedPad]]]:
    union = _UnionFind()
    pads_by_net: dict[str, list[ParsedPad]] = defaultdict(list)
    for footprint in parsed.footprints:
        for pad in footprint.pads:
            if not pad.net_name:
                continue
            pads_by_net[pad.net_name].append(pad)
            nodes = [_node(pad.point, layer) for layer in pad.layers]
            for item in nodes:
                union.find(item)
            for item in nodes[1:]:
                union.union(nodes[0], item)
    for segment in parsed.segments:
        union.union(_node(segment.start, segment.layer), _node(segment.end, segment.layer))
    for index, left in enumerate(parsed.segments):
        for right in parsed.segments[index + 1 :]:
            if left.net_name == right.net_name and _segments_intersect(left, right):
                union.union(_node(left.start, left.layer), _node(right.start, right.layer))
    for via in parsed.vias:
        union.union(_node(via.at, "F.Cu"), _node(via.at, "B.Cu"))
    for segment in parsed.segments:
        for pad in pads_by_net.get(segment.net_name, []):
            if segment.layer in pad.layers and _segment_intersects_box(
                segment,
                pad.point,
                _pad_half_extents(pad),
            ):
                union.union(_node(pad.point, segment.layer), _node(segment.start, segment.layer))
        for via in parsed.vias:
            if via.net_name == segment.net_name and _on_segment(via.at, segment):
                union.union(_node(via.at, segment.layer), _node(segment.start, segment.layer))
    return union, pads_by_net


def _point_segment_distance(point: tuple[float, float], segment: ParsedSegment) -> float:
    dx = segment.end[0] - segment.start[0]
    dy = segment.end[1] - segment.start[1]
    denominator = dx * dx + dy * dy
    if denominator <= 1e-12:
        return math.hypot(point[0] - segment.start[0], point[1] - segment.start[1])
    ratio = ((point[0] - segment.start[0]) * dx + (point[1] - segment.start[1]) * dy) / denominator
    ratio = min(1.0, max(0.0, ratio))
    closest = (segment.start[0] + ratio * dx, segment.start[1] + ratio * dy)
    return math.hypot(point[0] - closest[0], point[1] - closest[1])


def _pad_half_extents(pad: ParsedPad) -> tuple[float, float]:
    """Return the axis-aligned half extents of a possibly rotated pad."""

    half_x = pad.size[0] / 2
    half_y = pad.size[1] / 2
    angle = math.radians(pad.rotation)
    return (
        abs(math.cos(angle)) * half_x + abs(math.sin(angle)) * half_y,
        abs(math.sin(angle)) * half_x + abs(math.cos(angle)) * half_y,
    )


def _segment_intersects_box(
    segment: ParsedSegment,
    center: tuple[float, float],
    half_extents: tuple[float, float],
) -> bool:
    """Liang-Barsky segment/AABB intersection used for copper clearance."""

    min_x = center[0] - half_extents[0]
    max_x = center[0] + half_extents[0]
    min_y = center[1] - half_extents[1]
    max_y = center[1] + half_extents[1]
    dx = segment.end[0] - segment.start[0]
    dy = segment.end[1] - segment.start[1]
    entering = 0.0
    leaving = 1.0
    for origin, delta, lower, upper in (
        (segment.start[0], dx, min_x, max_x),
        (segment.start[1], dy, min_y, max_y),
    ):
        if abs(delta) <= 1e-12:
            if origin < lower or origin > upper:
                return False
            continue
        first = (lower - origin) / delta
        second = (upper - origin) / delta
        if first > second:
            first, second = second, first
        entering = max(entering, first)
        leaving = min(leaving, second)
        if entering > leaving:
            return False
    return True


def _point_box_distance(
    point: tuple[float, float],
    center: tuple[float, float],
    half_extents: tuple[float, float],
) -> float:
    dx = max(abs(point[0] - center[0]) - half_extents[0], 0.0)
    dy = max(abs(point[1] - center[1]) - half_extents[1], 0.0)
    return math.hypot(dx, dy)


def validate_pcb(
    pcb_path: Path,
    design: PhysicalDesign,
    placement: PCBPlacement,
    route_plan: PCBRoutePlan,
    *,
    output_report: Path | None = None,
) -> dict[str, Any]:
    parsed = parse_kicad_pcb(pcb_path)
    expected_components = {component.ref: component for component in design.components}
    actual_components = {footprint.ref: footprint for footprint in parsed.footprints}
    missing_components = sorted(set(expected_components) - set(actual_components))
    extra_components = sorted(set(actual_components) - set(expected_components))
    value_mismatches = [
        {"ref": ref, "expected": expected_components[ref].value, "actual": actual_components[ref].value}
        for ref in sorted(set(expected_components) & set(actual_components))
        if expected_components[ref].value != actual_components[ref].value
    ]

    expected_members = {name: set(members) for name, members in design.nets.items()}
    actual_members: dict[str, set[str]] = defaultdict(set)
    for footprint in parsed.footprints:
        for pad in footprint.pads:
            if pad.net_name:
                actual_members[pad.net_name].add(pad.identity)
    net_membership_failures: list[dict[str, Any]] = []
    for net, expected in sorted(expected_members.items()):
        actual = actual_members.get(net, set())
        if expected != actual:
            net_membership_failures.append(
                {
                    "net": net,
                    "missing": sorted(expected - actual),
                    "extra": sorted(actual - expected),
                }
            )

    union, pads_by_net = _connectivity(parsed)
    disconnected_nets: list[dict[str, Any]] = []
    for net, pads in sorted(pads_by_net.items()):
        if len(pads) < 2:
            continue
        roots = {
            union.find(_node(pad.point, pad.layers[0]))
            for pad in pads
        }
        if len(roots) > 1:
            disconnected_nets.append({"net": net, "member_count": len(pads), "island_count": len(roots)})

    cross_net_track_contacts: list[dict[str, Any]] = []
    for index, left in enumerate(parsed.segments):
        for right in parsed.segments[index + 1 :]:
            if left.net_name == right.net_name:
                continue
            if _segments_intersect(left, right):
                cross_net_track_contacts.append(
                    {
                        "left_net": left.net_name,
                        "right_net": right.net_name,
                        "layer": left.layer,
                        "left": [list(left.start), list(left.end)],
                        "right": [list(right.start), list(right.end)],
                    }
                )

    pad_track_contacts: list[dict[str, Any]] = []
    pad_via_contacts: list[dict[str, Any]] = []
    via_track_contacts: list[dict[str, Any]] = []
    via_pad_hole_contacts: list[dict[str, Any]] = []
    for footprint in parsed.footprints:
        for pad in footprint.pads:
            half_extents = _pad_half_extents(pad)
            for segment in parsed.segments:
                if (pad.net_name and segment.net_name == pad.net_name) or segment.layer not in pad.layers:
                    continue
                expanded = (
                    half_extents[0] + segment.width / 2 + 0.2,
                    half_extents[1] + segment.width / 2 + 0.2,
                )
                if _segment_intersects_box(segment, pad.point, expanded):
                    pad_track_contacts.append(
                        {"pad": pad.identity, "pad_net": pad.net_name or "<no net>", "track_net": segment.net_name}
                    )
            for via in parsed.vias:
                same_net = bool(pad.net_name and via.net_name == pad.net_name)
                if not same_net and _point_box_distance(via.at, pad.point, half_extents) < via.size / 2 + 0.2:
                    pad_via_contacts.append(
                        {"pad": pad.identity, "pad_net": pad.net_name or "<no net>", "via_net": via.net_name}
                    )
                if pad.drill:
                    drill_diameter = max(pad.drill)
                    center_distance = math.hypot(pad.point[0] - via.at[0], pad.point[1] - via.at[1])
                    hole_clearance = center_distance - drill_diameter / 2 - via.drill / 2
                    if hole_clearance < 0.25:
                        via_pad_hole_contacts.append(
                            {
                                "pad": pad.identity,
                                "pad_net": pad.net_name or "<no net>",
                                "via_net": via.net_name,
                                "hole_clearance": round(hole_clearance, 4),
                            }
                        )
    for via in parsed.vias:
        for segment in parsed.segments:
            if via.net_name == segment.net_name:
                continue
            if _point_segment_distance(via.at, segment) < via.size / 2 + segment.width / 2 + 0.2:
                via_track_contacts.append(
                    {
                        "via_net": via.net_name,
                        "track_net": segment.net_name,
                        "track_layer": segment.layer,
                        "via_at": list(via.at),
                    }
                )

    outline_ok = parsed.outline is not None and parsed.outline[2] > parsed.outline[0] and parsed.outline[3] > parsed.outline[1]
    checks = {
        "file_validity": bool(parsed.file_validity.get("ok")),
        "component_identity": not missing_components and not extra_components and not value_mismatches,
        "pad_net_membership": not net_membership_failures,
        "routed_connectivity": not disconnected_nets and route_plan.unrouted_net_count == 0,
        "cross_net_track_clearance": not cross_net_track_contacts,
        "pad_track_clearance": not pad_track_contacts,
        "pad_via_clearance": not pad_via_contacts,
        "via_track_clearance": not via_track_contacts,
        "via_pad_hole_clearance": not via_pad_hole_contacts,
        "placement": placement.overlap_count == 0,
        "board_outline": outline_ok,
    }
    report = {
        "schema": VALIDATION_SCHEMA,
        "ok": all(checks.values()),
        "ready_for_output": all(checks.values()),
        "checks": checks,
        "file_validity": parsed.file_validity,
        "expected_component_count": len(expected_components),
        "actual_component_count": len(actual_components),
        "missing_components": missing_components,
        "extra_components": extra_components,
        "value_mismatches": value_mismatches,
        "net_membership_failures": net_membership_failures,
        "disconnected_nets": disconnected_nets,
        "cross_net_track_contacts": cross_net_track_contacts,
        "pad_track_contacts": pad_track_contacts,
        "pad_via_contacts": pad_via_contacts,
        "via_track_contacts": via_track_contacts,
        "via_pad_hole_contacts": via_pad_hole_contacts,
        "route_plan_unrouted_net_count": route_plan.unrouted_net_count,
        "placement_overlap_count": placement.overlap_count,
        "outline": list(parsed.outline) if parsed.outline else None,
        "parsed_segment_count": len(parsed.segments),
        "parsed_via_count": len(parsed.vias),
    }
    if output_report is not None:
        output_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
