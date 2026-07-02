"""Stage-based KiCad generation pipeline."""

from .context import PipelineContext, PipelineError, StageResult
from .arrangement_decider import decide_arrangement
from .beautifier import apply_coordinate_edits
from .placement_input_validator import validate_placement_input
from .placement_validator import validate_placement
from .placer_pipeline import run_placer_pipeline
from .terminal_placer import place_terminals
from .wire_planner import plan_wire_routes, plan_wiring, write_wire_planner_jsons


def place_components(*args, **kwargs):
    from .kicad_component_placer import place_components as _place_components

    return _place_components(*args, **kwargs)


def run_placer_pack(*args, **kwargs):
    from .kicad_component_placer import run_placer_pack as _run_placer_pack

    return _run_placer_pack(*args, **kwargs)

__all__ = [
    "PipelineContext",
    "PipelineError",
    "StageResult",
    "apply_coordinate_edits",
    "decide_arrangement",
    "place_components",
    "place_terminals",
    "plan_wire_routes",
    "plan_wiring",
    "run_placer_pipeline",
    "run_placer_pack",
    "validate_placement",
    "validate_placement_input",
    "write_wire_planner_jsons",
]
