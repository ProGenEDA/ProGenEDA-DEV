"""Routing v2 orchestration.

The orchestrator follows the PDF contract: Python handles JSON, catalogue
loading, exporter-facing artifacts, and reports. It prefers a future compiled
Rust core when available, while keeping the existing Python router as a
compatibility backend for today's KiCad generation.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from kicad.pipeline.catelogues import load_component_catalogue
from kicad.pipeline.wire_planner import plan_wire_routes

from .live_routing_state import LiveRoutingState, build_live_routing_state
from .routing_config import routing_v2_config
from .validation_report import build_validation_report


def _project_name(circuit: dict[str, Any]) -> str:
    project = circuit.get("project")
    if isinstance(project, dict) and project.get("name"):
        return str(project["name"])
    return str(circuit.get("name") or "unnamed_project")


def _try_rust_plan(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        import progen_routing_core  # type: ignore[import-not-found]
    except Exception:
        return None
    result_json = progen_routing_core.plan_full(json.dumps(payload))
    result = json.loads(result_json)
    if not isinstance(result, dict):
        raise ValueError("Rust routing core returned non-object JSON")
    return result


def _legalize_existing_overlaps(state: LiveRoutingState, config: dict[str, Any]) -> dict[str, Any]:
    legalization = config.get("legalization", {}) if isinstance(config.get("legalization"), dict) else {}
    max_depth = int(legalization.get("max_depth", 3))
    moved: list[dict[str, Any]] = []
    failed: list[str] = []
    for ref, component in sorted(state.components.items(), key=lambda item: -float(item[1].get("priority", 0.0))):
        if not state.find_blockers(ref):
            continue
        report = state.legalize_after_move(ref, max_depth=max_depth)
        moved.extend(report.get("moved", []))
        failed.extend(report.get("failed", []))
    return {"moved": moved, "failed": sorted(set(failed)), "overlap_count": len(state.find_overlaps())}


def _rotation_improvement_pass(state: LiveRoutingState) -> list[dict[str, Any]]:
    """Cheap rotation-aware scoring pass using only LiveRoutingState math."""
    edits: list[dict[str, Any]] = []
    for ref in sorted(state.components):
        component = state.components[ref]
        if component.get("locked"):
            continue
        current_rotation = int(component.get("rotation", 0))
        current_score = state.score_fast()["score"]
        best_rotation = current_rotation
        best_score = current_score
        for rotation in component.get("legal_rotations", [0]):
            rotation = int(rotation)
            if rotation == current_rotation:
                continue
            candidate = state.clone_state()
            candidate.apply_rotation(ref, rotation)
            if candidate.find_overlaps(ref) or candidate._component_out_of_sheet(ref):
                continue
            score = candidate.score_fast()["score"]
            if score + 0.001 < best_score:
                best_rotation = rotation
                best_score = score
        if best_rotation != current_rotation:
            state.apply_rotation(ref, best_rotation)
            edits.append({"ref": ref, "from_rotation": current_rotation, "to_rotation": best_rotation, "score": round(best_score, 3)})
    return edits


def _python_live_state_plan(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    component_catalogue_path: str | None,
    config: dict[str, Any],
    wire_config: dict[str, Any] | None,
) -> dict[str, Any]:
    catalogue = load_component_catalogue(component_catalogue_path)
    state = build_live_routing_state(placement, circuit, component_catalogue=catalogue, config=config)
    initial_score = state.score_routeability()
    rotation_edits: list[dict[str, Any]] = []
    if config.get("placement", {}).get("enable_python_live_state_placement", True):
        rotation_edits = _rotation_improvement_pass(state)
        legalization_report = _legalize_existing_overlaps(state, config)
    else:
        legalization_report = {"moved": [], "failed": [], "overlap_count": len(state.find_overlaps())}

    coordinate_plan = state.to_coordinate_plan()
    coordinate_plan["rotation_score_edits"] = rotation_edits
    coordinate_plan["legalization"] = legalization_report
    routing_placement = state.to_routing_placement()
    fallback_wire_config = deepcopy(config.get("wire_fallback", {}))
    if wire_config:
        fallback_wire_config.update(wire_config)
    wire_plan = plan_wire_routes(routing_placement, circuit, config=fallback_wire_config)
    validation = build_validation_report(
        project=_project_name(circuit),
        engine="python_live_state_v0.1_with_legacy_router",
        routing_placement=routing_placement,
        wire_plan=wire_plan,
    )
    final_score = state.score_routeability()
    return {
        "schema": "progen-kicad-wire-planner-output/v0.2",
        "coordinate_plan": coordinate_plan,
        "routing_placement": routing_placement,
        "wire_plan": wire_plan,
        "arrangement_selection": {
            "schema": "progen-kicad-routeable-arrangement-selection/v0.2",
            "selected_variant": "python_live_state_current_best",
            "selected_score": final_score,
            "initial_score": initial_score,
            "variants": [
                {
                    "name": "python_live_state_current_best",
                    "score": final_score,
                    "rotation_edit_count": len(rotation_edits),
                    "legalization_move_count": len(legalization_report.get("moved", [])),
                }
            ],
        },
        "component_motion_policy": {
            "phase": "before_route_search",
            "coordinate_source": "LiveRoutingState",
            "applied_by": "routing_orchestrator",
            "purpose": "optimize component state mathematically before routing; export only the winning state",
        },
        "engine": "python_live_state_v0.1_with_legacy_router",
        "metrics": {
            "live_state": final_score,
            "wire_plan": wire_plan.get("metrics", {}),
            "validation": validation.get("metrics", {}),
        },
        "warnings": [
            "Rust routing core is not installed; used Python LiveRoutingState plus legacy Python router fallback.",
            *wire_plan.get("warnings", []),
        ],
        "validation_report": validation,
    }


def plan_wiring_v2(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    component_catalogue_path: str | None = None,
    config: dict[str, Any] | None = None,
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    merged_config = routing_v2_config(config)
    catalogue = load_component_catalogue(component_catalogue_path)
    payload = {
        "catalogue": catalogue.as_dict(),
        "placement": placement,
        "circuit": circuit,
        "config": merged_config,
    }
    rust_result = _try_rust_plan(payload)
    if rust_result is not None:
        validation = build_validation_report(
            project=_project_name(circuit),
            engine=str(rust_result.get("engine") or "rust_core_v0.1"),
            routing_placement=rust_result.get("routing_placement", {}),
            wire_plan=rust_result.get("wire_plan", {}),
        )
        return {
            "schema": "progen-kicad-wire-planner-output/v0.2",
            "coordinate_plan": rust_result["coordinate_plan"],
            "routing_placement": rust_result["routing_placement"],
            "wire_plan": rust_result["wire_plan"],
            "arrangement_selection": rust_result["arrangement_selection"],
            "engine": str(rust_result.get("engine") or "rust_core_v0.1"),
            "metrics": rust_result.get("metrics", {}),
            "warnings": rust_result.get("warnings", []),
            "validation_report": validation,
        }
    return _python_live_state_plan(
        placement,
        circuit,
        component_catalogue_path=component_catalogue_path,
        config=merged_config,
        wire_config=wire_config,
    )
