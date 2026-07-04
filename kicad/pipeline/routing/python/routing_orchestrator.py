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
from kicad.pipeline.placement_catalog import normalize_kind, resolve_placement_spec
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
    if result.get("implemented") is False:
        return None
    required = {"coordinate_plan", "routing_placement", "wire_plan", "arrangement_selection"}
    if not required.issubset(result):
        return None
    return result


def _placement_fallbacks_for_rust(placement: dict[str, Any], circuit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    kinds: set[str] = set()
    for component in circuit.get("components", []):
        if isinstance(component, dict):
            kind = component.get("kind") or component.get("name")
            if kind:
                kinds.add(str(kind))
    placement_components = placement.get("components")
    if isinstance(placement_components, dict):
        for component in placement_components.values():
            if isinstance(component, dict):
                kind = component.get("kind") or component.get("name")
                if kind:
                    kinds.add(str(kind))
    fallbacks: dict[str, dict[str, Any]] = {}
    for kind in sorted(kinds):
        spec = resolve_placement_spec(kind)
        if spec is None:
            continue
        fallbacks[normalize_kind(kind)] = {
            "kind": spec.kind,
            "name": spec.name,
            "width": spec.width,
            "height": spec.height,
            "category": spec.category,
            "source": spec.source,
        }
    return fallbacks


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


def _wire_plan_v2(wire_plan: dict[str, Any]) -> dict[str, Any]:
    upgraded = deepcopy(wire_plan)
    upgraded["schema"] = "progen-kicad-wire-plan/v0.2"
    algorithm = upgraded.get("algorithm")
    if not isinstance(algorithm, dict):
        algorithm = {}
    algorithm.setdefault("hanan_grid_lanes", True)
    algorithm.setdefault("rectilinear_mst_tree", True)
    algorithm.setdefault("astar_manhattan_fallback", True)
    algorithm.setdefault("segment_indexed_crossing_metrics", True)
    upgraded["algorithm"] = algorithm
    return upgraded


def _wire_score(wire_plan: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    wire_metrics = wire_plan.get("metrics", {}) if isinstance(wire_plan.get("metrics"), dict) else {}
    validation_metrics = validation.get("metrics", {}) if isinstance(validation.get("metrics"), dict) else {}
    route_quality = [route.get("route_quality", {}) for route in wire_plan.get("routes", []) if isinstance(route, dict)]
    route_length = sum(float(item.get("length", 0.0)) for item in route_quality if isinstance(item, dict))
    turns = sum(int(item.get("turns", 0)) for item in route_quality if isinstance(item, dict))
    score = (
        int(validation_metrics.get("component_overlap_count", 0)) * 10_000_000_000
        + int(validation_metrics.get("body_hit_count", 0)) * 1_000_000_000
        + int(validation_metrics.get("forbidden_contact_count", 0)) * 750_000_000
        + int(wire_metrics.get("unroutable_net_count", 0)) * 500_000_000
        + int(wire_metrics.get("partial_wire_net_count", 0)) * 100_000_000
        + int(wire_metrics.get("label_strategy_count", 0)) * 10_000_000
        + int(wire_metrics.get("crossing_density_overflow", 0)) * 1_000_000
        + turns * 10
        + route_length
        + int(wire_metrics.get("different_net_crossing_count", 0)) * 0.01
    )
    return {
        "score": round(score, 3),
        "route_length": round(route_length, 3),
        "turn_count": turns,
        "unroutable_net_count": int(wire_metrics.get("unroutable_net_count", 0)),
        "partial_wire_net_count": int(wire_metrics.get("partial_wire_net_count", 0)),
        "forbidden_contact_count": int(validation_metrics.get("forbidden_contact_count", 0)),
        "body_hit_count": int(validation_metrics.get("body_hit_count", 0)),
        "component_overlap_count": int(validation_metrics.get("component_overlap_count", 0)),
        "different_net_crossing_count": int(wire_metrics.get("different_net_crossing_count", 0)),
        "crossing_density_overflow": int(wire_metrics.get("crossing_density_overflow", 0)),
    }


def _state_signature(state: LiveRoutingState) -> tuple[tuple[str, tuple[float, float], int], ...]:
    return tuple(
        (
            ref,
            (round(float(component.get("at", [0.0, 0.0])[0]), 3), round(float(component.get("at", [0.0, 0.0])[1]), 3)),
            int(component.get("rotation", 0)) % 360,
        )
        for ref, component in sorted(state.components.items())
    )


def _dedupe_states(states: list[LiveRoutingState]) -> list[LiveRoutingState]:
    seen: set[tuple[tuple[str, tuple[float, float], int], ...]] = set()
    out: list[LiveRoutingState] = []
    for state in states:
        signature = _state_signature(state)
        if signature in seen:
            continue
        seen.add(signature)
        out.append(state)
    return out


def _route_final_states(
    states: list[LiveRoutingState],
    circuit: dict[str, Any],
    *,
    engine: str,
    config: dict[str, Any],
    wire_config: dict[str, Any] | None,
) -> dict[str, Any]:
    fallback_wire_config = deepcopy(config.get("wire_fallback", {}))
    if wire_config:
        fallback_wire_config.update(wire_config)
    routed_variants: list[dict[str, Any]] = []
    for index, state in enumerate(states):
        routing_placement = state.to_routing_placement()
        wire_plan = _wire_plan_v2(plan_wire_routes(routing_placement, circuit, config=fallback_wire_config))
        validation = build_validation_report(
            project=_project_name(circuit),
            engine=engine,
            routing_placement=routing_placement,
            wire_plan=wire_plan,
        )
        score = _wire_score(wire_plan, validation)
        routed_variants.append(
            {
                "name": f"beam_state_{index}",
                "state": state,
                "routing_placement": routing_placement,
                "wire_plan": wire_plan,
                "validation_report": validation,
                "score": score,
            }
        )
    routed_variants.sort(key=lambda item: (float(item["score"]["score"]), str(item["name"])))
    selected = routed_variants[0]
    return {
        "selected": selected,
        "variants": [
            {
                "name": item["name"],
                "score": item["score"],
                "coordinate_edit_count": len(item["state"].to_coordinate_plan().get("coordinate_edits", [])),
                "validation_checks": item["validation_report"].get("checks", {}),
            }
            for item in routed_variants
        ],
    }


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
    baseline_state = state.clone_state()
    initial_score = state.score_routeability()
    engine = "python_live_state_v0.2_full_math_router"
    rotation_edits: list[dict[str, Any]] = []
    beam_report: dict[str, Any] = {"strategy": "disabled"}
    final_states = [state]
    if config.get("placement", {}).get("enable_python_live_state_placement", True):
        if config.get("placement", {}).get("enable_cluster_growth_beam_search", True):
            rotation_baseline = baseline_state.clone_state()
            baseline_rotation_edits = _rotation_improvement_pass(rotation_baseline)
            baseline_legalization = _legalize_existing_overlaps(rotation_baseline, config)
            beam = state.beam_search_cluster_growth(config)
            state = beam["selected_state"]
            final_states = _dedupe_states([baseline_state, rotation_baseline, *list(beam.get("final_states") or [state])])
            beam_report = dict(beam.get("report") or {})
            beam_report["baseline_rotation_edit_count"] = len(baseline_rotation_edits)
            beam_report["baseline_legalization"] = baseline_legalization
            legalization_report = _legalize_existing_overlaps(state, config)
        else:
            rotation_edits = _rotation_improvement_pass(state)
            legalization_report = _legalize_existing_overlaps(state, config)
            final_states = [state]
    else:
        legalization_report = {"moved": [], "failed": [], "overlap_count": len(state.find_overlaps())}

    routed = _route_final_states(
        final_states,
        circuit,
        engine=engine,
        config=config,
        wire_config=wire_config,
    )
    selected = routed["selected"]
    state = selected["state"]
    coordinate_plan = state.to_coordinate_plan()
    coordinate_plan["rotation_score_edits"] = rotation_edits
    coordinate_plan["legalization"] = legalization_report
    coordinate_plan["beam_search"] = beam_report
    routing_placement = selected["routing_placement"]
    wire_plan = selected["wire_plan"]
    validation = selected["validation_report"]
    final_score = state.score_routeability()
    return {
        "schema": "progen-kicad-wire-planner-output/v0.2",
        "coordinate_plan": coordinate_plan,
        "routing_placement": routing_placement,
        "wire_plan": wire_plan,
        "arrangement_selection": {
            "schema": "progen-kicad-routeable-arrangement-selection/v0.2",
            "selected_variant": selected["name"],
            "selected_score": selected["score"],
            "initial_score": initial_score,
            "placement_beam": beam_report,
            "variants": routed["variants"],
        },
        "component_motion_policy": {
            "phase": "before_route_search",
            "coordinate_source": "LiveRoutingState",
            "applied_by": "routing_orchestrator",
            "purpose": "optimize component state mathematically before routing; export only the winning state",
        },
        "engine": engine,
        "metrics": {
            "live_state": final_score,
            "wire_plan": wire_plan.get("metrics", {}),
            "validation": validation.get("metrics", {}),
            "selected_wire_score": selected["score"],
        },
        "warnings": [
            "Rust routing core is not installed; used Python LiveRoutingState full mathematical fallback.",
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
        "placement_fallbacks": _placement_fallbacks_for_rust(placement, circuit),
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
