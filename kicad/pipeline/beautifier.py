"""Coordinate-only beautifier stage.

The beautifier applies coordinate edits decided elsewhere. It intentionally
does not invent placement logic, choose routes, or inspect KiCad files.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


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


def apply_coordinate_edits(placement: dict[str, Any], coordinate_plan: dict[str, Any]) -> dict[str, Any]:
    """Return a new placement JSON object with only coordinates changed."""
    updated = deepcopy(placement)
    components = updated.setdefault("components", {})
    if not isinstance(components, dict):
        raise ValueError("placement.components must be an object")

    edits = _edit_map(coordinate_plan)
    applied: list[dict[str, Any]] = []
    deltas: dict[str, tuple[float, float]] = {}

    for ref, edit in edits.items():
        if ref not in components or not isinstance(components[ref], dict):
            continue
        component = components[ref]
        old_at = component.get("at", [0.0, 0.0])
        if not isinstance(old_at, (list, tuple)) or len(old_at) < 2:
            old_at = [0.0, 0.0]
        new_at = edit["to"]
        x = round(float(new_at[0]), 3)
        y = round(float(new_at[1]), 3)
        dx = round(x - float(old_at[0]), 3)
        dy = round(y - float(old_at[1]), 3)
        component["at"] = [x, y]
        if "rotation" in edit:
            component["rotation"] = float(edit["rotation"])
        deltas[ref] = (dx, dy)
        applied.append({"ref": ref, "from": [float(old_at[0]), float(old_at[1])], "to": [x, y], "delta": [dx, dy]})

    obstacles = updated.setdefault("obstacles", [])
    if isinstance(obstacles, list):
        for obstacle in obstacles:
            if not isinstance(obstacle, dict):
                continue
            owner = str(obstacle.get("owner") or "")
            if owner not in deltas:
                continue
            dx, dy = deltas[owner]
            for key in ("left", "right"):
                if key in obstacle:
                    obstacle[key] = round(float(obstacle[key]) + dx, 3)
            for key in ("top", "bottom"):
                if key in obstacle:
                    obstacle[key] = round(float(obstacle[key]) + dy, 3)

    updated["schema"] = "progen-kicad-beautified-placement/v0.1"
    updated["stage"] = "beautifier"
    updated["applied_edits"] = applied
    updated["source_coordinate_plan_schema"] = coordinate_plan.get("schema")
    return updated
