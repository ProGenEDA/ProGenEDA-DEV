"""Validation for the replaceable direct-Altium placed-design contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .pipeline_contracts import PlacedDesign


PLACEMENT_VALIDATION_SCHEMA = "progen-altium-placement-validation/v1"


@dataclass(frozen=True)
class PlacementValidationReport:
    passed: bool
    component_count: int
    pin_count: int
    overlap_pairs: tuple[tuple[str, str], ...]
    errors: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = PLACEMENT_VALIDATION_SCHEMA
        return result


def validate_placement(design: PlacedDesign) -> PlacementValidationReport:
    """Check native pin completeness, collision-free bounds, and net coverage."""

    errors: list[str] = []
    references = [component.reference for component in design.components]
    if len(references) != len(set(references)):
        errors.append("placed component references are not unique")
    endpoint_set: set[str] = set()
    pin_count = 0
    for component in design.components:
        pins = set(component.pins)
        if pins != set(component.pin_directions) or pins != set(component.pin_nets):
            errors.append(f"{component.reference} has incomplete pin geometry/direction/net facts")
        if component.record_count <= 0:
            errors.append(f"{component.reference} has no source record payload")
        for pin in pins:
            endpoint_set.add(f"{component.reference}.{pin}")
            pin_count += 1
    net_endpoints = {endpoint for members in design.nets.values() for endpoint in members}
    if endpoint_set != net_endpoints:
        errors.append("placed pin endpoints and placed-design netlist differ")

    overlaps: list[tuple[str, str]] = []
    for index, left in enumerate(design.components):
        for right in design.components[index + 1 :]:
            if left.bounds.intersects(right.bounds):
                overlaps.append((left.reference, right.reference))
    if overlaps:
        errors.append(f"component bodies overlap: {overlaps}")
    return PlacementValidationReport(
        passed=not errors,
        component_count=len(design.components),
        pin_count=pin_count,
        overlap_pairs=tuple(overlaps),
        errors=tuple(errors),
    )
