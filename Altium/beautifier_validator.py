"""Separate validation boundary for coordinate-only beautifier output."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .beautifier import BeautifierResult
from .placement_validator import PlacementValidationReport, validate_placement


BEAUTIFIER_VALIDATION_SCHEMA = "progen-altium-beautifier-validation/v1"


@dataclass(frozen=True)
class BeautifierValidationReport:
    passed: bool
    moved_component_count: int
    placement: PlacementValidationReport

    def json(self) -> dict[str, Any]:
        return {
            "schema": BEAUTIFIER_VALIDATION_SCHEMA,
            "passed": self.passed,
            "moved_component_count": self.moved_component_count,
            "placement": self.placement.json(),
        }


def validate_beautifier_result(result: BeautifierResult) -> BeautifierValidationReport:
    """Prove coordinate edits preserved collision-free pin/body geometry."""

    placement = validate_placement(result.design)
    return BeautifierValidationReport(
        passed=placement.passed,
        moved_component_count=len(result.moved_references),
        placement=placement,
    )
