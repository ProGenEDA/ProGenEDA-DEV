"""Deterministic square-fill placement for supported physical footprints."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .physical_design_compiler import PhysicalComponent, PhysicalDesign


PLACEMENT_SCHEMA = "progen-kicad-pcb-placement/v0.1"


def _snap(value: float, grid: float = 1.27) -> float:
    return round(round(value / grid) * grid, 4)


@dataclass(frozen=True)
class PlacedFootprint:
    component: PhysicalComponent
    at: tuple[float, float]
    rotation: float
    bounds: tuple[float, float, float, float]

    def world_pad(self, pad_number: str) -> tuple[float, float]:
        pad = next((item for item in self.component.footprint.pads if str(item["number"]) == str(pad_number)), None)
        if pad is None:
            raise KeyError(f"{self.component.ref} footprint has no pad {pad_number}")
        return self.world_pad_record(pad)

    def world_pad_record(self, pad: dict[str, Any]) -> tuple[float, float]:
        local_x, local_y = (float(value) for value in pad["at"])
        angle = math.radians(self.rotation)
        world_x = self.at[0] + local_x * math.cos(angle) - local_y * math.sin(angle)
        world_y = self.at[1] + local_x * math.sin(angle) + local_y * math.cos(angle)
        return (round(world_x, 4), round(world_y, 4))

    def pad_record(self, pad_number: str) -> dict[str, Any]:
        pad = next((item for item in self.component.footprint.pads if str(item["number"]) == str(pad_number)), None)
        if pad is None:
            raise KeyError(f"{self.component.ref} footprint has no pad {pad_number}")
        return pad

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.component.ref,
            "kind": self.component.kind,
            "footprint_id": self.component.footprint_id,
            "at": list(self.at),
            "rotation": self.rotation,
            "bounds": list(self.bounds),
            "pads": {
                number: {
                    "net": net,
                    "point": list(self.world_pad(number)),
                    "source": self.pad_record(number),
                }
                for number, net in sorted(self.component.pad_nets.items())
            },
        }


@dataclass(frozen=True)
class PCBPlacement:
    footprints: tuple[PlacedFootprint, ...]
    board_bounds: tuple[float, float, float, float]
    placement_area_bounds: tuple[float, float, float, float]
    overlap_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": PLACEMENT_SCHEMA,
            "board_bounds": list(self.board_bounds),
            "placement_area_bounds": list(self.placement_area_bounds),
            "board_width": round(self.board_bounds[2] - self.board_bounds[0], 4),
            "board_height": round(self.board_bounds[3] - self.board_bounds[1], 4),
            "footprint_count": len(self.footprints),
            "overlap_count": self.overlap_count,
            "ok": self.overlap_count == 0,
            "footprints": {footprint.component.ref: footprint.as_dict() for footprint in self.footprints},
        }


def _rectangles_overlap(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> bool:
    return not (left[2] <= right[0] or right[2] <= left[0] or left[3] <= right[1] or right[3] <= left[1])


def _routing_halo(component: PhysicalComponent) -> float:
    smd_count = sum(1 for pad in component.footprint.pads if pad.get("mount_type") == "smd")
    return min(30.0, 2.54 + 0.635 * smd_count) if smd_count else 0.0


def _connectivity_order(design: PhysicalDesign, *, ignore_global_nets: bool) -> list[PhysicalComponent]:
    """Keep physical neighbours near the parts they must electrically reach.

    The PCB compiler deliberately works from the physical subset.  A component
    connected only to omitted components has no physical peer, so placing it
    after the routable graph keeps it from needlessly fragmenting routing space.
    """

    by_ref = {component.ref: component for component in design.components}
    adjacency: dict[str, dict[str, float]] = {component.ref: {} for component in design.components}
    for members in design.nets.values():
        refs = sorted({member.rsplit(".", 1)[0] for member in members})
        if len(refs) < 2:
            continue
        # Dense boards route global rails after local topology. Letting a 40+
        # member rail influence their placement turns every component into an
        # equal neighbour and destroys short signal-net locality. Smaller
        # boards retain the global influence, which is more compact there.
        if ignore_global_nets and len(refs) > 8:
            continue
        # Direct two-pad nets deserve the strongest locality preference.  A
        # wide power net still matters, but should not collapse every member
        # into one arbitrary row.
        weight = 8.0 if len(refs) == 2 else (3.0 if len(refs) <= 4 else 1.0)
        for index, left in enumerate(refs):
            for right in refs[index + 1 :]:
                adjacency[left][right] = adjacency[left].get(right, 0.0) + weight
                adjacency[right][left] = adjacency[right].get(left, 0.0) + weight

    degree = {ref: sum(neighbours.values()) for ref, neighbours in adjacency.items()}
    active = {ref for ref, value in degree.items() if value > 0.0}
    ordered_refs: list[str] = []
    placed: set[str] = set()
    while active:
        def score(ref: str) -> tuple[float, float, float, str]:
            affinity = sum(weight for peer, weight in adjacency[ref].items() if peer in placed)
            component = by_ref[ref]
            area = component.footprint.bounds["width"] * component.footprint.bounds["height"]
            return (affinity, degree[ref], area, ref)

        # A deterministic high-degree seed starts each disconnected physical
        # island.  Thereafter affinity dominates so local nets remain local.
        ref = max(active, key=score)
        active.remove(ref)
        placed.add(ref)
        ordered_refs.append(ref)

    inactive = sorted(
        (component for component in design.components if component.ref not in placed),
        key=lambda component: (
            component.block,
            -component.footprint.bounds["height"],
            -component.footprint.bounds["width"],
            component.ref,
        ),
    )
    return [by_ref[ref] for ref in ordered_refs] + inactive


def place_footprints(
    design: PhysicalDesign,
    *,
    margin: float = 10.0,
    gap: float = 8.0,
    ignore_global_nets: bool | None = None,
) -> PCBPlacement:
    if not design.components:
        return PCBPlacement(footprints=(), board_bounds=(0.0, 0.0, 0.0, 0.0), placement_area_bounds=(0.0, 0.0, 0.0, 0.0), overlap_count=0)

    total_area = sum(
        (component.footprint.bounds["width"] + 2 * _routing_halo(component) + gap)
        * (component.footprint.bounds["height"] + 2 * _routing_halo(component) + gap)
        for component in design.components
    )
    dense_board = len(design.components) > 80
    if ignore_global_nets is None:
        ignore_global_nets = dense_board
    # A wider initial shelf target compensates for large connector and module
    # cells on dense boards. Small boards retain the compact proven profile.
    fill_factor = 1.5 if dense_board else 1.2
    target_width = max(50.0, math.sqrt(total_area) * fill_factor)
    ordered = _connectivity_order(design, ignore_global_nets=ignore_global_nets)
    placed: list[PlacedFootprint] = []
    cursor_x = margin
    cursor_y = margin
    shelf_height = 0.0
    max_right = margin
    max_bottom = margin

    for component in ordered:
        local = component.footprint.bounds
        width = float(local["width"])
        height = float(local["height"])
        halo = _routing_halo(component)
        cell_width = width + 2 * halo
        cell_height = height + 2 * halo
        if cursor_x > margin and cursor_x + cell_width > margin + target_width:
            cursor_x = margin
            cursor_y = _snap(cursor_y + shelf_height + gap)
            shelf_height = 0.0
        left = _snap(cursor_x + halo)
        top = _snap(cursor_y + halo)
        anchor_x = _snap(left - float(local["min_x"]))
        anchor_y = _snap(top - float(local["min_y"]))
        right = round(left + width, 4)
        bottom = round(top + height, 4)
        placed.append(
            PlacedFootprint(
                component=component,
                at=(anchor_x, anchor_y),
                rotation=0.0,
                bounds=(left, top, right, bottom),
            )
        )
        cursor_x = _snap(right + halo + gap)
        shelf_height = max(shelf_height, cell_height)
        max_right = max(max_right, right + halo)
        max_bottom = max(max_bottom, bottom + halo)

    overlap_count = sum(
        1
        for index, left in enumerate(placed)
        for right in placed[index + 1 :]
        if _rectangles_overlap(left.bounds, right.bounds)
    )
    route_band = max(12.0, min(30.0, 4.0 + 0.4 * len(design.nets)))
    board_right = _snap(max_right + margin)
    board_bottom = _snap(max_bottom + margin + route_band)
    return PCBPlacement(
        footprints=tuple(placed),
        board_bounds=(0.0, 0.0, board_right, board_bottom),
        placement_area_bounds=(margin, margin, max_right, max_bottom),
        overlap_count=overlap_count,
    )
