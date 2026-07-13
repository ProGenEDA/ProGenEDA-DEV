"""Deterministic, topology-aware placement for project-local LTspice symbols."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

from .component_selector import SelectedComponent
from .geometry import GRID, Point, normalize_orientation, transform_offset, transform_point


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
    # Project-local symbols declare their value/reference windows for the
    # unrotated native orientation.  Rotating every two-terminal component
    # makes those windows vertical in LTspice, which is needlessly difficult
    # to read in an automatically placed circuit.  Keep the default R0; an
    # explicit LTspice orientation (or legacy rotation) remains authoritative.
    return "R0"


def _is_ground_net(name: object) -> bool:
    return str(name).strip().upper() in {"0", "GND", "GROUND"}


def _default_slot(index: int, population: int, columns: int) -> tuple[int, int]:
    """Return a compact automatic grid slot with room for a rail below input.

    Three non-pseudo components are the common source--series--shunt shape.
    Putting the third item below the second yields a legible L-shaped RC/RL
    layout while leaving the first device's lower pin free for its ground
    anchor.  Larger designs keep the regular deterministic grid.
    """

    if population == 3:
        return ((0, 0), (1, 0), (1, 1))[index]
    return index % columns, index // columns


def _default_ground_anchor(
    item: SelectedComponent,
    circuit: dict[str, Any],
    placed_by_ref: dict[str, PlacedComponent],
) -> Point | None:
    """Attach an implicit GND marker to an existing physical ground terminal.

    The ground pseudo-component is represented by a native ``FLAG 0`` rather
    than a drawable symbol.  Placing that flag in an unrelated grid slot can
    land it on a later wire and silently short a net.  A canonical ground net
    already names a physical endpoint, so use the visible terminal anchor for
    its first placed endpoint when the user did not supply ``ltspice_at``.
    This also co-locates the pseudo flag with the deterministic ground lead
    instead of rendering a duplicate ground glyph one grid step away.
    """

    endpoint_prefix = f"{item.ref}."
    raw_nets = circuit.get("nets")
    if not isinstance(raw_nets, dict):
        return None
    for net_name, members in raw_nets.items():
        if not _is_ground_net(net_name) or not isinstance(members, list):
            continue
        endpoints = [str(member).strip() for member in members]
        if not any(endpoint.startswith(endpoint_prefix) for endpoint in endpoints):
            continue
        for endpoint in endpoints:
            try:
                ref, pin_number = endpoint.rsplit(".", 1)
            except ValueError:
                continue
            placed = placed_by_ref.get(ref)
            if placed is None or placed.component.profile.is_pseudo_component:
                continue
            pin = placed.component.profile.pin(pin_number)
            exit_directions = {
                "TOP": Point(0, -1),
                "BOTTOM": Point(0, 1),
                "LEFT": Point(-1, 0),
                "RIGHT": Point(1, 0),
            }
            local_direction = exit_directions.get(pin.justification.upper(), Point(0, -1))
            direction = transform_offset(local_direction, placed.orientation)
            return placed.pin_point(pin_number).translate(direction.x * GRID * 2, direction.y * GRID * 2)
    return None


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
    placed_by_ref: dict[str, PlacedComponent] = {}
    warnings: list[str] = []
    generated_index = 0
    occupied_origins: set[Point] = set()
    # Physical symbols come first so a default ground marker can attach to an
    # actual ground endpoint even if the pseudo component appeared first in
    # the input JSON.
    for item in non_pseudo:
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
            column, row = _default_slot(generated_index, len(non_pseudo), columns)
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
        placed_by_ref[item.ref] = candidate

    for item in selected:
        if not item.profile.is_pseudo_component:
            continue
        raw = raw_by_ref.get(item.ref, {})
        orientation = _canonical_rotation(raw, len(item.profile.pins))
        requested = _requested_at(raw)
        if requested is not None and raw.get("ltspice_at") is None:
            warnings.append(f"{item.ref}.at is not native LTspice geometry; placer chose a safe grid position.")
            requested = None
        if requested is None:
            anchor = _default_ground_anchor(item, circuit, placed_by_ref)
            if anchor is not None:
                requested = (anchor.x, anchor.y)
            else:
                column, row = _default_slot(generated_index, len(non_pseudo), columns)
                requested = (left + column * x_pitch, top + row * y_pitch)
                generated_index += 1
        origin = Point(int(round(requested[0] / GRID)) * GRID, int(round(requested[1] / GRID)) * GRID)
        candidate = PlacedComponent(component=item, origin=origin, orientation=orientation)
        if any(point.x < 0 or point.y < 0 for point in (candidate.pin_point(pin.number) for pin in item.profile.pins)):
            raise ValueError(
                f"{item.ref} placement/orientation puts a native LTspice pin at a negative coordinate; "
                "use a non-negative ltspice_at position."
            )
        # Pseudo components have no native symbol geometry; sharing the native
        # ground terminal anchor is intentional and yields one visible flag.
        placed_by_ref[item.ref] = candidate

    placed = [placed_by_ref[item.ref] for item in selected]
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
