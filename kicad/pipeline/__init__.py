"""Stage-based KiCad generation pipeline."""

from .context import PipelineContext, PipelineError, StageResult
from .placement_input_validator import validate_placement_input
from .placement_validator import validate_placement
from .placer_pipeline import run_placer_pipeline


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
    "place_components",
    "run_placer_pipeline",
    "run_placer_pack",
    "validate_placement",
    "validate_placement_input",
]
