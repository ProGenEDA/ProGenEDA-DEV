"""Coordinate/rotation-only beautifier stage.

The beautifier applies coordinate and rotation edits decided elsewhere. It
intentionally does not invent placement logic, choose routes, or inspect KiCad
files.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any


Point = tuple[float, float]


def _edit_map(coordinate_plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    edits: dict[str, dict[str, Any]] = {}
    raw_edits = coordinate_plan.get("coordinate_edits", [])
    if isinstance(raw_edits, dict):
        raw_edits = raw_edits.values()
    if not isinstance(raw_edits, list):
        return edits
    for item in raw_edits:
        if isinstance(item, dict) and item.get("ref") and isinstance(item.get("to"), (list, tuple)):
            edits[str(item["ref"])] = item
    return edits


def _point(value: Any, fallback: Point = (0.0, 0.0)) -> Point:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return fallback


def _rotation(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value) % 360.0
    except (TypeError, ValueError):
        return fallback % 360.0


def _rotate_point(point: Point, *, origin: Point, degrees: float) -> Point:
    if abs(degrees % 360.0) <= 0.001:
        return point
    angle = math.radians(degrees)
    dx = point[0] - origin[0]
    dy = point[1] - origin[1]
    return (
        origin[0] + dx * math.cos(angle) - dy * math.sin(angle),
        origin[1] + dx * math.sin(angle) + dy * math.cos(angle),
    )


def _transform_point(point: Point, *, old_at: Point, new_at: Point, delta_rotation: float) -> list[float]:
    rotated = _rotate_point(point, origin=old_at, degrees=delta_rotation)
    return [
        round(rotated[0] + (new_at[0] - old_at[0]), 3),
        round(rotated[1] + (new_at[1] - old_at[1]), 3),
    ]


def _transformed_rect(rect: dict[str, Any], *, old_at: Point, new_at: Point, delta_rotation: float) -> dict[str, float]:
    corners = [
        (float(rect["left"]), float(rect["top"])),
        (float(rect["right"]), float(rect["top"])),
        (float(rect["right"]), float(rect["bottom"])),
        (float(rect["left"]), float(rect["bottom"])),
    ]
    transformed = [_transform_point(point, old_at=old_at, new_at=new_at, delta_rotation=delta_rotation) for point in corners]
    xs = [point[0] for point in transformed]
    ys = [point[1] for point in transformed]
    return {"left": round(min(xs), 3), "right": round(max(xs), 3), "top": round(min(ys), 3), "bottom": round(max(ys), 3)}


def _coordinate_transform(transform: dict[str, Any]) -> dict[str, Any]:
    return {
        "old_at": transform["old_at"],
        "new_at": transform["new_at"],
        "delta_rotation": transform["delta_rotation"],
    }


def apply_coordinate_edits(placement: dict[str, Any], coordinate_plan: dict[str, Any]) -> dict[str, Any]:
    """Return a new placement JSON object with coordinates/rotations changed."""
    updated = deepcopy(placement)
    components = updated.setdefault("components", {})
    if not isinstance(components, dict):
        raise ValueError("placement.components must be an object")

    edits = _edit_map(coordinate_plan)
    applied: list[dict[str, Any]] = []
    transforms: dict[str, dict[str, Any]] = {}

    for ref, edit in edits.items():
        if ref not in components or not isinstance(components[ref], dict):
            continue
        component = components[ref]
        old_at = _point(component.get("at"))
        old_rotation = _rotation(component.get("rotation", 0.0))
        new_at = edit["to"]
        x = round(float(new_at[0]), 3)
        y = round(float(new_at[1]), 3)
        new_at_point = (x, y)
        new_rotation = _rotation(edit.get("rotation", old_rotation), old_rotation)
        dx = round(x - old_at[0], 3)
        dy = round(y - old_at[1], 3)
        delta_rotation = (new_rotation - old_rotation) % 360.0
        component["at"] = [x, y]
        component["rotation"] = new_rotation
        transforms[ref] = {
            "old_at": old_at,
            "new_at": new_at_point,
            "old_rotation": old_rotation,
            "new_rotation": new_rotation,
            "delta_rotation": delta_rotation,
        }
        applied.append(
            {
                "ref": ref,
                "from": [round(old_at[0], 3), round(old_at[1], 3)],
                "to": [x, y],
                "delta": [dx, dy],
                "from_rotation": old_rotation,
                "to_rotation": new_rotation,
                "delta_rotation": round(delta_rotation, 3),
            }
        )

    obstacles = updated.setdefault("obstacles", [])
    if isinstance(obstacles, list):
        for obstacle in obstacles:
            if not isinstance(obstacle, dict):
                continue
            owner = str(obstacle.get("owner") or "")
            if owner not in transforms:
                continue
            if all(key in obstacle for key in ("left", "right", "top", "bottom")):
                rect = _transformed_rect(obstacle, **_coordinate_transform(transforms[owner]))
                obstacle.update(rect)

    pin_points = updated.get("pin_points")
    if isinstance(pin_points, dict):
        for ref, pins in pin_points.items():
            if ref not in transforms or not isinstance(pins, dict):
                continue
            transform = transforms[str(ref)]
            for pin_data in pins.values():
                if not isinstance(pin_data, dict):
                    continue
                point = pin_data.get("point")
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    pin_data["point"] = _transform_point(_point(point), **_coordinate_transform(transform))
                if "side" in pin_data and transform.get("delta_rotation"):
                    pin_data["side"] = _rotate_side(str(pin_data.get("side") or ""), float(transform["delta_rotation"]))

    updated["schema"] = "progen-kicad-beautified-placement/v0.2"
    updated["stage"] = "beautifier"
    updated["applied_edits"] = applied
    updated["source_coordinate_plan_schema"] = coordinate_plan.get("schema")
    return updated


def _rotate_side(side: str, delta_rotation: float) -> str:
    order = ["left", "top", "right", "bottom"]
    value = side.lower()
    if value not in order:
        return side
    steps = int(round(delta_rotation / 90.0)) % 4
    return order[(order.index(value) + steps) % 4]
