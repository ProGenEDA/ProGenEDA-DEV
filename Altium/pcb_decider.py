"""Explicit PCB-decision stage for the direct Altium pipeline.

The schematic pipeline exposes this stage now so frontends and internal runs
never have to infer why a `.PcbDoc` was absent.  It intentionally returns a
blocking decision until native board donor evidence and a matching validator
are available.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .pipeline_contracts import ComponentSelection, PlacedDesign


PCB_DECISION_SCHEMA = "progen-altium-pcb-decision/v1"


@dataclass(frozen=True)
class PcbDecision:
    status: str
    component_count: int
    reason: str

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = PCB_DECISION_SCHEMA
        return result


def decide_pcb_output(selection: ComponentSelection, design: PlacedDesign) -> PcbDecision:
    """Report the deliberate native-PCB boundary without fabricating a board."""

    return PcbDecision(
        status="not_generated",
        component_count=len(design.components),
        reason=(
            "Direct PcbDoc generation is blocked until audited native board, pad, stackup, "
            "rule, footprint, and routing donor evidence exists for every selected source pin."
        ),
    )
