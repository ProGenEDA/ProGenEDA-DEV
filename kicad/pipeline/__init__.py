"""Stage-based KiCad generation pipeline."""

from .context import PipelineContext, PipelineError, StageResult
from .arrangement_decider import decide_arrangement
from .beautifier import apply_coordinate_edits
from .placement_input_validator import validate_placement_input
from .placement_validator import validate_placement
from .placer_pipeline import run_placer_pipeline
from .terminal_placer import place_terminals
from .wire_planner import (
    plan_partial_route_component_moves,
    plan_wire_routes,
    plan_wiring,
    select_routeable_arrangement,
    write_wire_planner_jsons,
)
from .routing.python import (
    LiveRoutingState,
    build_live_routing_state,
    build_validation_report,
    plan_wiring_v2,
    rotate_point,
    rotate_side,
)


def place_components(*args, **kwargs):
    from .kicad_component_placer import place_components as _place_components

    return _place_components(*args, **kwargs)


def run_placer_pack(*args, **kwargs):
    from .kicad_component_placer import run_placer_pack as _run_placer_pack

    return _run_placer_pack(*args, **kwargs)


def compare_expected_netlist(*args, **kwargs):
    from .kicad_netlist_validator import compare_expected_netlist as _compare_expected_netlist

    return _compare_expected_netlist(*args, **kwargs)


def parse_schematic(*args, **kwargs):
    from .kicad_netlist_validator import parse_schematic as _parse_schematic

    return _parse_schematic(*args, **kwargs)


def run_optional_kicad_erc(*args, **kwargs):
    from .kicad_netlist_validator import run_optional_kicad_erc as _run_optional_kicad_erc

    return _run_optional_kicad_erc(*args, **kwargs)


def validate_schematic_netlist(*args, **kwargs):
    from .kicad_netlist_validator import validate_schematic_netlist as _validate_schematic_netlist

    return _validate_schematic_netlist(*args, **kwargs)


def write_validation_report(*args, **kwargs):
    from .kicad_netlist_validator import write_validation_report as _write_validation_report

    return _write_validation_report(*args, **kwargs)


def apply_value_edits(*args, **kwargs):
    from .value_editor import apply_value_edits as _apply_value_edits

    return _apply_value_edits(*args, **kwargs)


def validate_component_values(*args, **kwargs):
    from .value_validator import validate_component_values as _validate_component_values

    return _validate_component_values(*args, **kwargs)


def validate_final_project(*args, **kwargs):
    from .final_validator import validate_final_project as _validate_final_project

    return _validate_final_project(*args, **kwargs)

__all__ = [
    "PipelineContext",
    "PipelineError",
    "StageResult",
    "LiveRoutingState",
    "apply_coordinate_edits",
    "apply_value_edits",
    "build_live_routing_state",
    "build_validation_report",
    "compare_expected_netlist",
    "decide_arrangement",
    "parse_schematic",
    "place_components",
    "place_terminals",
    "plan_partial_route_component_moves",
    "plan_wire_routes",
    "plan_wiring",
    "plan_wiring_v2",
    "rotate_point",
    "rotate_side",
    "select_routeable_arrangement",
    "run_placer_pipeline",
    "run_placer_pack",
    "run_optional_kicad_erc",
    "validate_placement",
    "validate_placement_input",
    "validate_component_values",
    "validate_final_project",
    "validate_schematic_netlist",
    "write_validation_report",
    "write_wire_planner_jsons",
]
