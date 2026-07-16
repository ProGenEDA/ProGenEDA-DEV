"""Placer-only pipeline entrypoint."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from . import placement_input_validator, placement_validator
from .context import PipelineContext, PipelineError
from .placement_catalog import CatalogPlacementPlan
from .placement_project_writer import write_placement_project


def _load_circuit(input_data: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(input_data, dict):
        return deepcopy(input_data)
    if isinstance(input_data, Path):
        return json.loads(input_data.read_text(encoding="utf-8"))
    text = str(input_data)
    if text.lstrip().startswith("{"):
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("placer input must be a CircuitIR JSON object")
        return parsed
    path = Path(text)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("placer input must be a CircuitIR JSON object")
    return parsed


def _write_trace(ctx: PipelineContext) -> None:
    if ctx.out_dir is None or ctx.placement_plan is None:
        return
    ctx.out_dir.mkdir(parents=True, exist_ok=True)
    if isinstance(ctx.placement_plan, CatalogPlacementPlan):
        write_placement_project(ctx.circuit, ctx.placement_plan, ctx.out_dir, clean=True)
    placement = ctx.placement_plan.as_dict()
    (ctx.out_dir / "placement.json").write_text(json.dumps(placement, indent=2), encoding="utf-8")
    (ctx.out_dir / "placement_trace.json").write_text(json.dumps(ctx.pipeline_summary(), indent=2), encoding="utf-8")


def run_placer_pipeline(
    input_data: str | Path | dict[str, Any],
    *,
    out_dir: str | Path | None = None,
    write_trace: bool = True,
    stop_on_error: bool = True,
) -> PipelineContext:
    circuit = _load_circuit(input_data)
    ctx = PipelineContext(
        original_input=deepcopy(circuit),
        circuit=circuit,
        out_dir=Path(out_dir) if out_dir is not None else None,
    )
    from . import kicad_component_placer

    for stage in (placement_input_validator.run, kicad_component_placer.run, placement_validator.run):
        result = ctx.record(stage(ctx))
        if not result.ok and stop_on_error:
            raise PipelineError(result)
    if write_trace:
        _write_trace(ctx)
    return ctx
