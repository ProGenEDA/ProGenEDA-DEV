"""Coordinate-only application of Altium arrangement plans."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .pipeline_contracts import ArrangementPlan, PipelineError, PlacedDesign


BEAUTIFIER_SCHEMA = "progen-altium-beautifier/v1"


class BeautifierError(PipelineError):
    """An arrangement plan does not match the placed-design contract."""


@dataclass(frozen=True)
class BeautifierResult:
    design: PlacedDesign
    moved_references: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        return {
            "schema": BEAUTIFIER_SCHEMA,
            "moved_references": list(self.moved_references),
            "placed_design": self.design.json(),
        }


def apply_coordinate_edits(design: PlacedDesign, plan: ArrangementPlan) -> BeautifierResult:
    """Apply only validated coordinate edits, never symbols, nets, or values."""

    edits = {edit.reference: edit for edit in plan.edits}
    references = {component.reference for component in design.components}
    if set(edits) != references:
        missing = sorted(references - set(edits))
        unexpected = sorted(set(edits) - references)
        raise BeautifierError(
            f"Arrangement plan references differ from placement: missing={missing}, unexpected={unexpected}."
        )
    moved: list[str] = []
    components = []
    for component in design.components:
        edit = edits[component.reference]
        if edit.from_root != component.root_location:
            raise BeautifierError(
                f"Arrangement plan starts {component.reference} at {edit.from_root.json()}, "
                f"but placement is {component.root_location.json()}."
            )
        if edit.to_root != component.root_location:
            moved.append(component.reference)
        components.append(component.translated(edit.to_root))
    return BeautifierResult(
        design=PlacedDesign(components=tuple(components), nets=dict(design.nets)),
        moved_references=tuple(moved),
    )
