"""Named placeholders for future pipeline stages.

These stages are intentionally not part of the placer-only pipeline yet.
They exist so the architecture has stable names without pretending the later
logic is already implemented.
"""

from __future__ import annotations

from .context import StageResult


FUTURE_STAGE_NAMES = (
    "prompt_enhancer",
    "script_json",
    "json_enhancer",
    "json_validator",
    "file_name_decider",
    "arrangement_decider",
    "component_selector",
    "validator",
    "user_specification_validator",
    "beautifier",
    "beautifier_validator",
    "routing_decider",
    "combination_decider",
    "wire_planner",
    "wire_maker",
    "terminal_placer",
    "terminal_validator",
)


def placeholder_result(stage: str) -> StageResult:
    if stage not in FUTURE_STAGE_NAMES:
        return StageResult(stage, ok=False, errors=[f"Unknown placeholder stage {stage!r}."])
    return StageResult(
        stage,
        ok=False,
        summary="Placeholder only. This stage is not active until the previous slice is proven.",
        data={"status": "placeholder", "active": False},
    )
