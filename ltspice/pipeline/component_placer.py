"""Deterministic, topology-aware placement for project-local LTspice symbols."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .component_selector import SelectedComponent
from .geometry import GRID, Point, normalize_orientation, transform_point


PLACEMENT_SCHEMA = "progen-ltspice-placement/v0.1"


@dataclass(frozen=True)
class PlacedComponent:
    component: SelectedComponent
    origin: Point
    orientation: str

    def pin_point(self, pin_number: object) -> Point:
        pin = self.component.profile.pin(pin_number)
        return transform_point(self.origin, Point(pin.x, pin.y), self.orientation)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.component.ref,
            "kind": self.component.kind,
            "symbol": self.component.profile.symbol,
            "origin": {"x": self.origin.x, "y": self.origin.y},
            "orientation": self.orientation,
            "pins": {
                pin.number: {
                    "name": pin.name,
                    "role": pin.role,
                    "x": self.pin_point(pin.number).x,
                    "y": self.pin_point(pin.number).y,
                }
                for pin in self.component.profile.pins
            },
        }


def _requested_at(raw_component: dict[str, Any]) -> tuple[int, int] | None:
    value = raw_component.get("ltspice_at")
    if value is None:
        value = raw_component.get("at")
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return None


def _canonical_rotation(raw_component: dict[str, Any], pin_count: int) -> str:
    raw = raw_component.get("ltspice_orientation")
    if raw is not None:
        return normalize_orientation(raw)
    raw_rotation = raw_component.get("rotation")
    if raw_rotation is not None:
        try:
            rotation = int(raw_rotation) % 360
        except (TypeError, ValueError):
            rotation = 0
        return {0: "R0", 90: "R90", 180: "R180", 270: "R270"}.get(rotation, "R0")
    # Multi-pin symbols retain the predictable vertical supply axis. Two-pin
    # devices alternate orientation in an otherwise compact grid.
    return "R0" if pin_count != 2 else "R90"


def place_components(circuit: dict[str, Any], selected: list[SelectedComponent]) -> tuple[list[PlacedComponent], dict[str, Any]]:
    """Place selected symbols without donor slot or filename dependence."""

    raw_by_ref: dict[str, dict[str, Any]] = {}
    for raw in circuit.get("components", []):
        if isinstance(raw, dict):
            ref = str(raw.get("ref") or raw.get("id") or "")
            if ref:
                raw_by_ref[ref] = raw

    non_pseudo = [item for item in selected if not item.profile.is_pseudo_component]
    columns = max(1, math.ceil(math.sqrt(max(1, len(non_pseudo)))))
    x_pitch = 16 * 18
    y_pitch = 16 * 14
    left = 16 * 12
    top = 16 * 10
    placed: list[PlacedComponent] = []
    warnings: list[str] = []
    generated_index = 0
    occupied_origins: set[Point] = set()
    for item in selected:
        raw = raw_by_ref.get(item.ref, {})
        orientation = _canonical_rotation(raw, len(item.profile.pins))
        requested = _requested_at(raw)
        if requested is not None:
            # Canonical KiCad coordinates are millimetre-ish; only an explicit
            # ltspice_at is native. Use supplied at merely as a deterministic
            # ordering hint instead of silently treating it as an ASC position.
            if raw.get("ltspice_at") is None:
                warnings.append(f"{item.ref}.at is not native LTspice geometry; placer chose a safe grid position.")
                requested = None
        if requested is None:
            column = generated_index % columns
            row = generated_index // columns
            requested = (left + column * x_pitch, top + row * y_pitch)
            generated_index += 1
        origin = Point(int(round(requested[0] / GRID)) * GRID, int(round(requested[1] / GRID)) * GRID)
        while origin in occupied_origins:
            origin = origin.translate(x_pitch, 0)
            warnings.append(f"Moved {item.ref} to avoid an identical symbol origin.")
        candidate = PlacedComponent(component=item, origin=origin, orientation=orientation)
        if any(point.x < 0 or point.y < 0 for point in (candidate.pin_point(pin.number) for pin in item.profile.pins)):
            raise ValueError(
                f"{item.ref} placement/orientation puts a native LTspice pin at a negative coordinate; "
                "use a non-negative ltspice_at position."
            )
        occupied_origins.add(origin)
        placed.append(candidate)
    report = {
        "schema": PLACEMENT_SCHEMA,
        "stage": "ltspice_component_placer",
        "ok": True,
        "grid": GRID,
        "component_count": len(placed),
        "warnings": warnings,
        "placed_components": [item.as_dict() for item in placed],
    }
    return placed, report
