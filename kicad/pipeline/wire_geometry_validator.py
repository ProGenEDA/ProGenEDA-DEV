"""Geometry validation for generated schematic wires.

This validator is EDA-neutral. It receives already-planned/drawn wire segments
with net names plus component body rectangles, then checks hard schematic
readability rules:

1. Different nets must not touch or cross.
2. Same-net wires must not form visual X crossings or overlaps.
3. Wires must not touch component bodies except at explicitly allowed pin
   points.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any


Point = tuple[float, float]


@dataclass(frozen=True)
class AllowedTouch:
    ref: str
    point: Point


@dataclass(frozen=True)
class WireGeometrySegment:
    net: str
    start: Point
    end: Point
    allowed_touches: tuple[AllowedTouch, ...] = ()
    source: str = ""


@dataclass(frozen=True)
class ComponentBody:
    ref: str
    left: float
    top: float
    right: float
    bottom: float
    source: str = ""


@dataclass(frozen=True)
class Contact:
    kind: str
    point: Point | None = None
    start: Point | None = None
    end: Point | None = None


def _round_point(point: Point) -> Point:
    return (round(float(point[0]), 3), round(float(point[1]), 3))


def _same_point(left: Point, right: Point, eps: float) -> bool:
    return abs(left[0] - right[0]) <= eps and abs(left[1] - right[1]) <= eps


def _between_closed(value: float, left: float, right: float, eps: float) -> bool:
    low, high = sorted((left, right))
    return low - eps <= value <= high + eps


def _between_strict(value: float, left: float, right: float, eps: float) -> bool:
    low, high = sorted((left, right))
    return low + eps < value < high - eps


def _is_horizontal(segment: WireGeometrySegment, eps: float) -> bool:
    return abs(segment.start[1] - segment.end[1]) <= eps


def _is_vertical(segment: WireGeometrySegment, eps: float) -> bool:
    return abs(segment.start[0] - segment.end[0]) <= eps


def _is_endpoint(point: Point, segment: WireGeometrySegment, eps: float) -> bool:
    return _same_point(point, segment.start, eps) or _same_point(point, segment.end, eps)


def _is_strict_interior(point: Point, segment: WireGeometrySegment, eps: float) -> bool:
    if _is_endpoint(point, segment, eps):
        return False
    return _between_closed(point[0], segment.start[0], segment.end[0], eps) and _between_closed(
        point[1], segment.start[1], segment.end[1], eps
    )


def _segment_contact(left: WireGeometrySegment, right: WireGeometrySegment, eps: float) -> Contact | None:
    left_h = _is_horizontal(left, eps)
    left_v = _is_vertical(left, eps)
    right_h = _is_horizontal(right, eps)
    right_v = _is_vertical(right, eps)
    if not (left_h or left_v) or not (right_h or right_v):
        return None

    if left_h and right_h:
        if abs(left.start[1] - right.start[1]) > eps:
            return None
        low = max(min(left.start[0], left.end[0]), min(right.start[0], right.end[0]))
        high = min(max(left.start[0], left.end[0]), max(right.start[0], right.end[0]))
        if low > high + eps:
            return None
        y = left.start[1]
        if abs(low - high) <= eps:
            return Contact("point", point=_round_point((low, y)))
        return Contact("overlap", start=_round_point((low, y)), end=_round_point((high, y)))

    if left_v and right_v:
        if abs(left.start[0] - right.start[0]) > eps:
            return None
        low = max(min(left.start[1], left.end[1]), min(right.start[1], right.end[1]))
        high = min(max(left.start[1], left.end[1]), max(right.start[1], right.end[1]))
        if low > high + eps:
            return None
        x = left.start[0]
        if abs(low - high) <= eps:
            return Contact("point", point=_round_point((x, low)))
        return Contact("overlap", start=_round_point((x, low)), end=_round_point((x, high)))

    horizontal = left if left_h else right
    vertical = right if left_h else left
    point = (vertical.start[0], horizontal.start[1])
    if _between_closed(point[0], horizontal.start[0], horizontal.end[0], eps) and _between_closed(
        point[1], vertical.start[1], vertical.end[1], eps
    ):
        return Contact("point", point=_round_point(point))
    return None


def _segment_body_contact(segment: WireGeometrySegment, body: ComponentBody, eps: float) -> Contact | None:
    if _is_horizontal(segment, eps):
        y = segment.start[1]
        if not _between_closed(y, body.top, body.bottom, eps):
            return None
        low = max(min(segment.start[0], segment.end[0]), body.left)
        high = min(max(segment.start[0], segment.end[0]), body.right)
        if low > high + eps:
            return None
        if abs(low - high) <= eps:
            return Contact("point", point=_round_point((low, y)))
        return Contact("overlap", start=_round_point((low, y)), end=_round_point((high, y)))
    if _is_vertical(segment, eps):
        x = segment.start[0]
        if not _between_closed(x, body.left, body.right, eps):
            return None
        low = max(min(segment.start[1], segment.end[1]), body.top)
        high = min(max(segment.start[1], segment.end[1]), body.bottom)
        if low > high + eps:
            return None
        if abs(low - high) <= eps:
            return Contact("point", point=_round_point((x, low)))
        return Contact("overlap", start=_round_point((x, low)), end=_round_point((x, high)))
    return None


def _contact_dict(contact: Contact) -> dict[str, Any]:
    if contact.kind == "point":
        return {"kind": contact.kind, "point": list(contact.point or (0.0, 0.0))}
    return {
        "kind": contact.kind,
        "start": list(contact.start or (0.0, 0.0)),
        "end": list(contact.end or (0.0, 0.0)),
    }


def _segment_dict(segment: WireGeometrySegment) -> dict[str, Any]:
    return {
        "net": segment.net,
        "start": list(segment.start),
        "end": list(segment.end),
        "source": segment.source,
    }


def _body_dict(body: ComponentBody) -> dict[str, Any]:
    return {
        "ref": body.ref,
        "left": body.left,
        "top": body.top,
        "right": body.right,
        "bottom": body.bottom,
        "source": body.source,
    }


def _allowed_component_touch(segment: WireGeometrySegment, body: ComponentBody, contact: Contact, eps: float) -> bool:
    if contact.kind != "point" or contact.point is None:
        return False
    for allowed in segment.allowed_touches:
        if allowed.ref == body.ref and _same_point(contact.point, allowed.point, eps):
            return True
    return False


def validate_wire_geometry(
    segments: list[WireGeometrySegment] | tuple[WireGeometrySegment, ...],
    component_bodies: list[ComponentBody] | tuple[ComponentBody, ...],
    *,
    eps: float = 0.001,
    max_violations: int = 500,
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []

    for index, segment in enumerate(segments):
        if segment.start == segment.end:
            continue
        if not (_is_horizontal(segment, eps) or _is_vertical(segment, eps)):
            violations.append(
                {
                    "rule": "wire_must_be_orthogonal",
                    "segment_index": index,
                    "segment": _segment_dict(segment),
                }
            )

    for left_index, left in enumerate(segments):
        if left.start == left.end:
            continue
        for right_index in range(left_index + 1, len(segments)):
            right = segments[right_index]
            if right.start == right.end:
                continue
            contact = _segment_contact(left, right, eps)
            if contact is None:
                continue
            if left.net != right.net:
                violations.append(
                    {
                        "rule": "different_net_wires_must_not_touch_or_cross",
                        "left_index": left_index,
                        "right_index": right_index,
                        "left": _segment_dict(left),
                        "right": _segment_dict(right),
                        "contact": _contact_dict(contact),
                    }
                )
                continue
            if contact.kind == "overlap":
                violations.append(
                    {
                        "rule": "same_net_wires_must_not_overlap",
                        "left_index": left_index,
                        "right_index": right_index,
                        "left": _segment_dict(left),
                        "right": _segment_dict(right),
                        "contact": _contact_dict(contact),
                    }
                )
                continue
            point = contact.point or (0.0, 0.0)
            if _is_strict_interior(point, left, eps) and _is_strict_interior(point, right, eps):
                violations.append(
                    {
                        "rule": "same_net_wires_must_not_visually_cross",
                        "left_index": left_index,
                        "right_index": right_index,
                        "left": _segment_dict(left),
                        "right": _segment_dict(right),
                        "contact": _contact_dict(contact),
                    }
                )

    for segment_index, segment in enumerate(segments):
        if segment.start == segment.end:
            continue
        for body in component_bodies:
            contact = _segment_body_contact(segment, body, eps)
            if contact is None:
                continue
            if _allowed_component_touch(segment, body, contact, eps):
                continue
            violations.append(
                {
                    "rule": "wire_must_not_touch_component_except_intended_pin",
                    "segment_index": segment_index,
                    "segment": _segment_dict(segment),
                    "component_body": _body_dict(body),
                    "contact": _contact_dict(contact),
                }
            )

    by_rule = Counter(str(item["rule"]) for item in violations)
    return {
        "schema": "progen-kicad-wire-geometry-validation/v0.1",
        "stage": "wire_geometry_validator",
        "rule_set": {
            "different_net_wires_must_not_touch_or_cross": True,
            "same_net_wires_must_not_visually_cross": True,
            "same_net_wires_must_not_overlap": True,
            "wire_must_not_touch_component_except_intended_pin": True,
        },
        "ok": not violations,
        "segment_count": len(segments),
        "component_body_count": len(component_bodies),
        "violation_count": len(violations),
        "violations_by_rule": dict(sorted(by_rule.items())),
        "violations": violations[:max_violations],
        "violations_truncated": len(violations) > max_violations,
    }
