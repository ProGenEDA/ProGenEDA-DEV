"""Validation report writer for routing v2 outputs."""

from __future__ import annotations

from collections import Counter
from typing import Any

from kicad.pipeline.wire_geometry_validator import (
    AllowedTouch,
    ComponentBody,
    WireGeometrySegment,
    validate_wire_geometry,
)


def _point(value: Any) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return (0.0, 0.0)


def _segments_from_wire_plan(wire_plan: dict[str, Any]) -> list[WireGeometrySegment]:
    segments: list[WireGeometrySegment] = []
    for route_index, route in enumerate(wire_plan.get("routes", [])):
        if not isinstance(route, dict):
            continue
        net = str(route.get("net") or "")
        allowed: list[AllowedTouch] = []
        for endpoint_key in ("from", "to"):
            endpoint = route.get(endpoint_key)
            if not isinstance(endpoint, dict):
                continue
            if not endpoint.get("exact"):
                continue
            ref = str(endpoint.get("ref") or "")
            point = _point(endpoint.get("point"))
            if ref:
                allowed.append(AllowedTouch(ref=ref, point=point))
        for segment_index, segment in enumerate(route.get("segments", [])):
            if not isinstance(segment, dict):
                continue
            segments.append(
                WireGeometrySegment(
                    net=net,
                    start=_point(segment.get("start")),
                    end=_point(segment.get("end")),
                    allowed_touches=tuple(allowed),
                    source=f"route:{route_index}:segment:{segment_index}",
                )
            )
    return segments


def _bodies_from_placement(routing_placement: dict[str, Any]) -> list[ComponentBody]:
    bodies: list[ComponentBody] = []
    for obstacle in routing_placement.get("obstacles", []):
        if not isinstance(obstacle, dict):
            continue
        owner = str(obstacle.get("component_ref") or obstacle.get("owner") or "")
        if not owner:
            continue
        bodies.append(
            ComponentBody(
                ref=owner,
                left=float(obstacle.get("left", 0.0)),
                top=float(obstacle.get("top", 0.0)),
                right=float(obstacle.get("right", 0.0)),
                bottom=float(obstacle.get("bottom", 0.0)),
                source=str(obstacle.get("owner") or ""),
            )
        )
    return bodies


def _component_overlap_count(routing_placement: dict[str, Any]) -> int:
    bodies = _bodies_from_placement(routing_placement)
    count = 0
    for index, left in enumerate(bodies):
        for right in bodies[index + 1 :]:
            if left.left < right.right and left.right > right.left and left.top < right.bottom and left.bottom > right.top:
                count += 1
    return count


def _out_of_sheet_count(routing_placement: dict[str, Any], wire_plan: dict[str, Any]) -> int:
    sheet = wire_plan.get("sheet", {}) if isinstance(wire_plan.get("sheet"), dict) else {}
    width = float(sheet.get("width", 420.0))
    height = float(sheet.get("height", 297.0))
    count = 0
    for body in _bodies_from_placement(routing_placement):
        if body.left < 0 or body.top < 0 or body.right > width or body.bottom > height:
            count += 1
    return count


def _pin_resolution_counts(routing_placement: dict[str, Any], wire_plan: dict[str, Any]) -> tuple[int, int]:
    pin_points = routing_placement.get("pin_points", {})
    if not isinstance(pin_points, dict):
        pin_points = {}
    total = 0
    missing = 0
    for net_data in wire_plan.get("nets", {}).values():
        if not isinstance(net_data, dict):
            continue
        for endpoint in net_data.get("endpoints", []):
            if not isinstance(endpoint, dict):
                continue
            total += 1
            ref = str(endpoint.get("ref") or "")
            pin = str(endpoint.get("pin") or "")
            pins = pin_points.get(ref, {}) if isinstance(pin_points.get(ref), dict) else {}
            if pin not in pins:
                missing += 1
    return total, missing


def build_validation_report(
    *,
    project: str,
    engine: str,
    routing_placement: dict[str, Any],
    wire_plan: dict[str, Any],
) -> dict[str, Any]:
    segments = _segments_from_wire_plan(wire_plan)
    bodies = _bodies_from_placement(routing_placement)
    geometry = validate_wire_geometry(segments, bodies)
    overlap_count = _component_overlap_count(routing_placement)
    out_of_sheet_count = _out_of_sheet_count(routing_placement, wire_plan)
    pin_total, pin_missing = _pin_resolution_counts(routing_placement, wire_plan)
    wire_metrics = wire_plan.get("metrics", {}) if isinstance(wire_plan.get("metrics"), dict) else {}
    violations = Counter(str(item.get("rule") or "") for item in geometry.get("violations", []))
    blocking_failures: list[dict[str, Any]] = []
    if overlap_count:
        blocking_failures.append({"rule": "component_overlap", "count": overlap_count})
    if out_of_sheet_count:
        blocking_failures.append({"rule": "out_of_sheet", "count": out_of_sheet_count})
    if pin_missing:
        blocking_failures.append({"rule": "missing_pin_anchor", "count": pin_missing})
    for rule, count in sorted(violations.items()):
        blocking_failures.append({"rule": rule, "count": count})
    if int(wire_metrics.get("unroutable_net_count", 0)):
        blocking_failures.append({"rule": "unroutable_net", "count": int(wire_metrics.get("unroutable_net_count", 0))})
    if int(wire_metrics.get("partial_wire_net_count", 0)):
        blocking_failures.append({"rule": "partial_wire_net", "count": int(wire_metrics.get("partial_wire_net_count", 0))})

    body_hit_count = int(geometry.get("violations_by_rule", {}).get("wire_must_not_touch_component_except_intended_pin", 0))
    forbidden_contact_count = sum(
        int(geometry.get("violations_by_rule", {}).get(rule, 0))
        for rule in (
            "different_net_collinear_overlap_forbidden",
            "different_net_t_touch_forbidden",
            "different_net_endpoint_touch_forbidden",
            "different_net_crossing_on_pin_forbidden",
        )
    )
    return {
        "schema": "progen-routing-validation-report/v0.2",
        "project": project,
        "engine": engine,
        "checks": {
            "component_overlap": "pass" if overlap_count == 0 else "fail",
            "out_of_sheet": "pass" if out_of_sheet_count == 0 else "fail",
            "pin_resolution": "pass" if pin_missing == 0 else "fail",
            "wire_geometry": "pass" if geometry.get("ok") else "fail",
            "forbidden_contacts": "pass" if forbidden_contact_count == 0 else "fail",
            "netlist_equivalence_ready": not blocking_failures,
        },
        "metrics": {
            "component_count": len(routing_placement.get("components", {})) if isinstance(routing_placement.get("components"), dict) else 0,
            "net_count": int(wire_metrics.get("net_count", 0)),
            "route_count": int(wire_metrics.get("wired_route_count", 0)),
            "wire_length": round(
                sum(float(segment.get("length", 0.0)) for route in wire_plan.get("routes", []) if isinstance(route, dict) for segment in route.get("segments", []) if isinstance(segment, dict)),
                3,
            ),
            "turn_count": sum(
                int(route.get("route_quality", {}).get("turns", 0))
                for route in wire_plan.get("routes", [])
                if isinstance(route, dict) and isinstance(route.get("route_quality"), dict)
            ),
            "different_net_crossing_count": int(wire_metrics.get("different_net_crossing_count", 0)),
            "crossing_density_overflow": int(wire_metrics.get("crossing_density_overflow", 0)),
            "unroutable_net_count": int(wire_metrics.get("unroutable_net_count", 0)),
            "partial_wire_net_count": int(wire_metrics.get("partial_wire_net_count", 0)),
            "body_hit_count": body_hit_count,
            "forbidden_contact_count": forbidden_contact_count,
            "component_overlap_count": overlap_count,
            "out_of_sheet_count": out_of_sheet_count,
            "pin_anchor_count": pin_total,
            "missing_pin_anchor_count": pin_missing,
        },
        "accepted_warnings": [
            "different-net 90-degree schematic crossings accepted as readability penalties"
        ],
        "blocking_failures": blocking_failures,
        "geometry_report": geometry,
    }
