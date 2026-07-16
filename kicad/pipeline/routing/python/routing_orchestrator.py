"""Routing v2 orchestration.

The orchestrator follows the PDF contract: Python handles JSON, catalogue
loading, exporter-facing artifacts, and reports. It prefers a future compiled
Rust core when available, while keeping the existing Python router as a
compatibility backend for today's KiCad generation.
"""

from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any

from kicad.pipeline.arrangement_decider import GROUND_NETS, POWER_NETS
from kicad.pipeline.catelogues import load_component_catalogue
from kicad.pipeline.placement_catalog import normalize_kind, resolve_placement_spec
from kicad.pipeline.wire_planner import plan_wire_routes, select_routeable_arrangement

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


def _try_rust_terminal_policy(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        import progen_routing_core  # type: ignore[import-not-found]
    except Exception:
        return None
    if not hasattr(progen_routing_core, "plan_terminal_policy"):
        return None
    result_json = progen_routing_core.plan_terminal_policy(json.dumps(payload))
    result = json.loads(result_json)
    if not isinstance(result, dict):
        raise ValueError("Rust routing core returned non-object terminal policy JSON")
    if result.get("implemented") is False:
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
        int(validation_metrics.get("component_overlap_count", 0)) * 1_000_000_000_000_000
        + int(validation_metrics.get("body_hit_count", 0)) * 100_000_000_000_000
        + int(wire_metrics.get("unroutable_net_count", 0)) * 10_000_000_000_000
        + int(wire_metrics.get("partial_wire_net_count", 0)) * 1_000_000_000_000
        + int(wire_metrics.get("label_strategy_count", 0)) * 100_000_000_000
        + int(validation_metrics.get("forbidden_contact_count", 0)) * 1_000_000_000
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


def _incomplete_wire_nets(wire_plan: dict[str, Any]) -> list[str]:
    nets = wire_plan.get("nets", {})
    if not isinstance(nets, dict):
        return []
    failed = [
        str(net)
        for net, data in nets.items()
        if isinstance(data, dict) and data.get("strategy") not in {"wire", "local_labels", "single_endpoint_label"}
    ]
    return sorted(failed)


def _wire_completion_key(wire_plan: dict[str, Any]) -> tuple[int, int, int, int, float]:
    metrics = wire_plan.get("metrics", {}) if isinstance(wire_plan.get("metrics"), dict) else {}
    route_quality = [route.get("route_quality", {}) for route in wire_plan.get("routes", []) if isinstance(route, dict)]
    route_length = sum(float(item.get("length", 0.0)) for item in route_quality if isinstance(item, dict))
    return (
        int(metrics.get("unroutable_net_count", 0)),
        int(metrics.get("partial_wire_net_count", 0)),
        int(metrics.get("label_strategy_count", 0)),
        -int(metrics.get("wired_route_count", 0)),
        route_length,
    )


def _path_from_route(route: dict[str, Any]) -> list[tuple[float, float]]:
    raw = route.get("path")
    if isinstance(raw, list) and len(raw) >= 2:
        points: list[tuple[float, float]] = []
        for point in raw:
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                points.append((round(float(point[0]), 3), round(float(point[1]), 3)))
        if len(points) >= 2:
            return points
    points = []
    for segment in route.get("segments", []):
        if not isinstance(segment, dict):
            continue
        start = segment.get("start")
        end = segment.get("end")
        if isinstance(start, (list, tuple)) and len(start) >= 2 and not points:
            points.append((round(float(start[0]), 3), round(float(start[1]), 3)))
        if isinstance(end, (list, tuple)) and len(end) >= 2:
            points.append((round(float(end[0]), 3), round(float(end[1]), 3)))
    return points


def _compress_path_points(path: list[tuple[float, float]]) -> list[tuple[float, float]]:
    if len(path) <= 2:
        return path
    out = [path[0]]
    last_direction = ""
    for left, right in zip(path, path[1:]):
        if left == right:
            continue
        direction = "H" if abs(left[1] - right[1]) <= 0.001 else "V"
        if not last_direction:
            last_direction = direction
            continue
        if direction != last_direction:
            out.append(left)
            last_direction = direction
    out.append(path[-1])
    return out


def _segments_from_path(path: list[tuple[float, float]]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for start, end in zip(path, path[1:]):
        if start == end:
            continue
        if abs(start[0] - end[0]) <= 0.001:
            direction = "down" if end[1] > start[1] else "up"
        elif abs(start[1] - end[1]) <= 0.001:
            direction = "right" if end[0] > start[0] else "left"
        else:
            direction = "non_orthogonal"
        segments.append(
            {
                "start": [round(start[0], 3), round(start[1], 3)],
                "end": [round(end[0], 3), round(end[1], 3)],
                "direction": direction,
                "length": round(abs(end[0] - start[0]) + abs(end[1] - start[1]), 3),
            }
        )
    return segments


def _turn_count(path: list[tuple[float, float]]) -> int:
    turns = 0
    previous = ""
    for left, right in zip(path, path[1:]):
        if left == right:
            continue
        direction = "H" if abs(left[1] - right[1]) <= 0.001 else "V"
        if previous and previous != direction:
            turns += 1
        previous = direction
    return turns


def _refresh_route_path(route: dict[str, Any], path: list[tuple[float, float]]) -> dict[str, Any]:
    path = _compress_path_points([(round(point[0], 3), round(point[1], 3)) for point in path])
    updated = deepcopy(route)
    updated["path"] = [[point[0], point[1]] for point in path]
    updated["segments"] = _segments_from_path(path)
    quality = dict(updated.get("route_quality", {})) if isinstance(updated.get("route_quality"), dict) else {}
    quality["length"] = round(sum(segment["length"] for segment in updated["segments"]), 3)
    quality["turns"] = _turn_count(path)
    updated["route_quality"] = quality
    return updated


def _violation_route_segments(validation: dict[str, Any]) -> dict[int, set[int]]:
    out: dict[int, set[int]] = {}
    pattern = re.compile(r"route:(\d+):segment:(\d+)")
    geometry = validation.get("geometry_report", {}) if isinstance(validation.get("geometry_report"), dict) else {}
    for violation in geometry.get("violations", []):
        if not isinstance(violation, dict):
            continue
        for key in ("segment", "left_segment", "right_segment"):
            segment = violation.get(key)
            if not isinstance(segment, dict):
                continue
            match = pattern.search(str(segment.get("source") or ""))
            if not match:
                continue
            route_index = int(match.group(1))
            segment_index = int(match.group(2))
            out.setdefault(route_index, set()).add(segment_index)
    return out


def _wire_validation_badness(validation: dict[str, Any]) -> tuple[int, int, int, int]:
    metrics = validation.get("metrics", {}) if isinstance(validation.get("metrics"), dict) else {}
    return (
        int(metrics.get("body_hit_count", 0)),
        int(metrics.get("forbidden_contact_count", 0)),
        int(metrics.get("component_overlap_count", 0)),
        int(metrics.get("out_of_sheet_count", 0)),
    )


def _shift_route_segment(path: list[tuple[float, float]], segment_index: int, delta: float) -> list[tuple[float, float]] | None:
    if segment_index <= 0 or segment_index >= len(path) - 2:
        return None
    start = path[segment_index]
    end = path[segment_index + 1]
    if abs(start[1] - end[1]) <= 0.001:
        shifted = list(path)
        shifted[segment_index] = (start[0], round(start[1] + delta, 3))
        shifted[segment_index + 1] = (end[0], round(end[1] + delta, 3))
        return shifted
    if abs(start[0] - end[0]) <= 0.001:
        shifted = list(path)
        shifted[segment_index] = (round(start[0] + delta, 3), start[1])
        shifted[segment_index + 1] = (round(end[0] + delta, 3), end[1])
        return shifted
    return None


def _refresh_wire_plan_metrics(wire_plan: dict[str, Any]) -> None:
    routes = [route for route in wire_plan.get("routes", []) if isinstance(route, dict)]
    metrics = wire_plan.setdefault("metrics", {})
    if isinstance(metrics, dict):
        metrics["wired_route_count"] = len(routes)
        metrics["segment_count"] = sum(len(route.get("segments", [])) for route in routes)


def _repair_relaxed_geometry_by_doglegs(
    routing_placement: dict[str, Any],
    wire_plan: dict[str, Any],
    *,
    project: str,
    engine: str,
    max_passes: int = 12,
    candidate_budget: int = 300,
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = deepcopy(wire_plan)
    grid = float(current.get("sheet", {}).get("grid", 1.27)) if isinstance(current.get("sheet"), dict) else 1.27
    validation = build_validation_report(project=project, engine=engine, routing_placement=routing_placement, wire_plan=current)
    initial_metrics = validation.get("metrics", {}) if isinstance(validation.get("metrics"), dict) else {}
    if int(initial_metrics.get("forbidden_contact_count", 0)) > 40:
        current = deepcopy(current)
        current["dogleg_geometry_repair"] = {
            "schema": "progen-kicad-dogleg-geometry-repair/v0.1",
            "pass_count": 0,
            "skipped": True,
            "reason": "initial_forbidden_contact_count_exceeds_safe_local_repair_limit",
            "initial_forbidden_contact_count": int(initial_metrics.get("forbidden_contact_count", 0)),
            "final_badness": list(_wire_validation_badness(validation)),
        }
        return current, validation
    passes: list[dict[str, Any]] = []
    deltas = [sign * grid * step for step in range(1, 5) for sign in (-1.0, 1.0)]
    max_routes_per_pass = 6
    max_segments_per_route = 2
    candidate_evaluations = 0
    budget_exhausted = False
    for pass_index in range(1, max_passes + 1):
        if candidate_evaluations >= candidate_budget:
            budget_exhausted = True
            break
        badness = _wire_validation_badness(validation)
        if badness == (0, 0, 0, 0):
            break
        route_segments = _violation_route_segments(validation)
        if not route_segments:
            break
        best_plan: dict[str, Any] | None = None
        best_validation: dict[str, Any] | None = None
        best_record: dict[str, Any] | None = None
        best_badness = badness
        routes = current.get("routes", [])
        if not isinstance(routes, list):
            break
        for route_index, segment_indexes in sorted(route_segments.items(), key=lambda item: (-len(item[1]), item[0]))[:max_routes_per_pass]:
            if route_index >= len(routes) or not isinstance(routes[route_index], dict):
                continue
            route = routes[route_index]
            path = _path_from_route(route)
            if len(path) < 4:
                continue
            candidate_segment_indexes = sorted(
                {index + offset for index in segment_indexes for offset in (-1, 0, 1) if 0 < index + offset < len(path) - 2}
            )[:max_segments_per_route]
            for segment_index in candidate_segment_indexes:
                for delta in deltas:
                    if candidate_evaluations >= candidate_budget:
                        budget_exhausted = True
                        break
                    shifted = _shift_route_segment(path, segment_index, delta)
                    if shifted is None:
                        continue
                    candidate = deepcopy(current)
                    candidate_routes = candidate.get("routes", [])
                    if not isinstance(candidate_routes, list):
                        continue
                    candidate_routes[route_index] = _refresh_route_path(route, shifted)
                    _refresh_wire_plan_metrics(candidate)
                    candidate_validation = build_validation_report(
                        project=project,
                        engine=engine,
                        routing_placement=routing_placement,
                        wire_plan=candidate,
                    )
                    candidate_evaluations += 1
                    candidate_badness = _wire_validation_badness(candidate_validation)
                    if candidate_badness < best_badness:
                        best_plan = candidate
                        best_validation = candidate_validation
                        best_badness = candidate_badness
                        best_record = {
                            "pass": pass_index,
                            "route_index": route_index,
                            "segment_index": segment_index,
                            "delta": round(delta, 3),
                            "before": badness,
                            "after": candidate_badness,
                        }
                        if candidate_badness == (0, 0, 0, 0):
                            break
                if best_badness == (0, 0, 0, 0):
                    break
                if budget_exhausted:
                    break
            if best_badness == (0, 0, 0, 0):
                break
            if budget_exhausted:
                break
        if best_plan is None or best_validation is None or best_record is None:
            break
        passes.append(best_record)
        current = best_plan
        validation = best_validation
    current = deepcopy(current)
    current.setdefault("algorithm", {})
    if isinstance(current["algorithm"], dict):
        current["algorithm"]["dogleg_geometry_repair"] = True
    current.setdefault("warnings", [])
    if isinstance(current["warnings"], list) and passes:
        current["warnings"].append(f"dogleg_geometry_repair_passes: {len(passes)}")
    current["dogleg_geometry_repair"] = {
        "schema": "progen-kicad-dogleg-geometry-repair/v0.1",
        "pass_count": len(passes),
        "passes": passes,
        "final_badness": list(_wire_validation_badness(validation)),
        "candidate_evaluations": candidate_evaluations,
        "candidate_budget": candidate_budget,
        "budget_exhausted": budget_exhausted,
    }
    return current, validation


def _signal_priority_nets(circuit: dict[str, Any]) -> list[str]:
    nets = circuit.get("nets", {})
    if not isinstance(nets, dict):
        return []
    return [str(net) for net in nets if str(net).upper() not in POWER_NETS and str(net).upper() not in GROUND_NETS]


def _routing_pin_point(routing_placement: dict[str, Any], member: str) -> tuple[float, float] | None:
    ref, _dot, pin = member.partition(".")
    if not ref or not pin:
        return None
    components = routing_placement.get("components", {})
    if not isinstance(components, dict):
        return None
    component = components.get(ref)
    if not isinstance(component, dict):
        return None
    pins = component.get("pins", {})
    if not isinstance(pins, dict):
        return None
    pin_record = pins.get(pin)
    if not isinstance(pin_record, dict):
        return None
    point = pin_record.get("point")
    if not isinstance(point, (list, tuple)) or len(point) < 2:
        return None
    return (float(point[0]), float(point[1]))


def _net_span_priority_nets(routing_placement: dict[str, Any], circuit: dict[str, Any]) -> list[str]:
    nets = circuit.get("nets", {})
    if not isinstance(nets, dict):
        return []
    scored: list[tuple[float, str]] = []
    for net, members in nets.items():
        if not isinstance(members, list):
            continue
        points = [_routing_pin_point(routing_placement, str(member)) for member in members]
        clean_points = [point for point in points if point is not None]
        if len(clean_points) < 2:
            continue
        xs = [point[0] for point in clean_points]
        ys = [point[1] for point in clean_points]
        span = (max(xs) - min(xs)) + (max(ys) - min(ys))
        scored.append((span, str(net)))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [net for _span, net in scored]


def _fanout_priority_nets(circuit: dict[str, Any]) -> list[str]:
    nets = circuit.get("nets", {})
    if not isinstance(nets, dict):
        return []
    scored = [
        (len(members), str(net))
        for net, members in nets.items()
        if isinstance(members, list) and len(members) >= 2
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [net for _fanout, net in scored]


def _ordered_unique(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _strict_reroute_profiles(
    routing_placement: dict[str, Any],
    circuit: dict[str, Any],
    failed: list[str],
) -> list[tuple[str, list[str]]]:
    signals = _signal_priority_nets(circuit)
    span = _net_span_priority_nets(routing_placement, circuit)
    fanout = _fanout_priority_nets(circuit)
    profiles: list[tuple[str, list[str]]] = []
    if failed:
        profiles.append(("priority_failed_nets", failed))
        profiles.append(("ripup_failed_then_signals", _ordered_unique([*failed, *signals])))
        profiles.append(("ripup_failed_then_span", _ordered_unique([*failed, *span])))
    profiles.extend(
        [
            ("ripup_signals_first", signals),
            ("ripup_long_span_first", span),
            ("ripup_high_fanout_first", fanout),
            ("ripup_signal_span_fanout", _ordered_unique([*signals, *span, *fanout])),
        ]
    )
    return [(name, priority_nets) for name, priority_nets in profiles if priority_nets]


def _plan_wire_routes_with_priority_retries(
    routing_placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    config: dict[str, Any],
    project: str,
    engine: str,
) -> dict[str, Any]:
    max_retries = max(0, int(float(config.get("strict_priority_reroute_attempts", 0.0))))
    attempts: list[dict[str, Any]] = []
    best = plan_wire_routes(routing_placement, circuit, config=config)
    attempts.append({"name": "default_order", "priority_nets": [], "metrics": best.get("metrics", {})})
    failed = _incomplete_wire_nets(best)
    seen: set[tuple[str, ...]] = {tuple()}
    for index, (profile_name, priority_nets) in enumerate(_strict_reroute_profiles(routing_placement, circuit, failed)):
        if index >= max_retries or _wire_completion_key(best)[:3] == (0, 0, 0):
            break
        priority_nets = _ordered_unique(priority_nets)
        key = tuple(priority_nets)
        if key in seen:
            continue
        seen.add(key)
        retry_config = dict(config)
        retry_config["priority_nets"] = priority_nets
        candidate = plan_wire_routes(routing_placement, circuit, config=retry_config)
        attempts.append(
            {
                "name": profile_name,
                "priority_nets": priority_nets,
                "metrics": candidate.get("metrics", {}),
            }
        )
        if _wire_completion_key(candidate) < _wire_completion_key(best):
            best = candidate
    if len(attempts) > 1:
        best = deepcopy(best)
        warnings = list(best.get("warnings", []))
        warnings.append("strict_priority_reroute_attempts: " + json.dumps(attempts, sort_keys=True))
        best["warnings"] = warnings
    if (
        _wire_completion_key(best)[:3] != (0, 0, 0)
        and config.get("strict_forbidden_contact_filter", 1.0) >= 1.0
        and config.get("strict_relaxed_dogleg_repair", 1.0) >= 1.0
    ):
        failed = _incomplete_wire_nets(best)
        profiles: list[tuple[str, list[str]]] = [
            ("relaxed_default_order", []),
            ("relaxed_signal_order", _signal_priority_nets(circuit)),
        ]
        if failed:
            profiles.append(("relaxed_failed_first", [*failed, *[net for net in _signal_priority_nets(circuit) if net not in set(failed)]]))
        seen_profiles: set[tuple[str, ...]] = set()
        for profile_name, priority_nets in profiles:
            key = tuple(priority_nets)
            if key in seen_profiles:
                continue
            seen_profiles.add(key)
            relaxed_config = dict(config)
            relaxed_config["strict_forbidden_contact_filter"] = 0.0
            relaxed_config["priority_nets"] = priority_nets
            relaxed = plan_wire_routes(routing_placement, circuit, config=relaxed_config)
            if _wire_completion_key(relaxed)[:3] != (0, 0, 0):
                continue
            repaired, validation = _repair_relaxed_geometry_by_doglegs(
                routing_placement,
                relaxed,
                project=project,
                engine=engine,
                max_passes=max(1, int(float(config.get("strict_dogleg_repair_max_passes", 12.0)))),
                candidate_budget=max(1, int(float(config.get("strict_dogleg_repair_candidate_budget", 300.0)))),
            )
            if _wire_validation_badness(validation) == (0, 0, 0, 0):
                repaired = deepcopy(repaired)
                repaired.setdefault("warnings", [])
                if isinstance(repaired["warnings"], list):
                    repaired["warnings"].append(f"strict_relaxed_dogleg_repair_selected: {profile_name}")
                return repaired
    return best


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


def _dedupe_named_states(states: list[tuple[str, LiveRoutingState]]) -> list[tuple[str, LiveRoutingState]]:
    seen: set[tuple[tuple[str, tuple[float, float], int], ...]] = set()
    out: list[tuple[str, LiveRoutingState]] = []
    for name, state in states:
        signature = _state_signature(state)
        if signature in seen:
            continue
        seen.add(signature)
        out.append((name, state))
    return out


def _route_final_state_variant(
    *,
    index: int,
    name: str,
    state: LiveRoutingState,
    circuit: dict[str, Any],
    engine: str,
    config: dict[str, Any],
    wire_config: dict[str, Any],
) -> dict[str, Any]:
    started = time.perf_counter()
    routing_placement = state.to_routing_placement()
    wire_plan = _wire_plan_v2(
        _plan_wire_routes_with_priority_retries(
            routing_placement,
            circuit,
            config=wire_config,
            project=_project_name(circuit),
            engine=engine,
        )
    )
    validation = build_validation_report(
        project=_project_name(circuit),
        engine=engine,
        routing_placement=routing_placement,
        wire_plan=wire_plan,
    )
    score = _wire_score(wire_plan, validation)
    square_fill = state.score_square_fill()
    score = dict(score)
    score["square_fill"] = square_fill
    score["score"] = round(float(score["score"]) + float(square_fill.get("score", 0.0)) * 100.0, 3)
    return {
        "index": index,
        "name": name,
        "state": state,
        "routing_placement": routing_placement,
        "wire_plan": wire_plan,
        "validation_report": validation,
        "score": score,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def _legacy_routeable_state_candidate(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    catalogue: Any,
    config: dict[str, Any],
    wire_config: dict[str, Any] | None,
) -> tuple[LiveRoutingState | None, dict[str, Any]]:
    placement_config = config.get("placement", {}) if isinstance(config.get("placement"), dict) else {}
    if not placement_config.get("enable_legacy_routeable_floor", True):
        return None, {"ok": False, "skipped": True, "reason": "disabled_by_config"}

    started = time.perf_counter()
    legacy_wire_config = deepcopy(config.get("wire_fallback", {}))
    if wire_config:
        legacy_wire_config.update(wire_config)
    legacy_wire_config["arrangement_variant_search"] = 1.0
    legacy_wire_config["arrangement_final_wire_route"] = 0.0
    legacy_wire_config["max_arrangement_variants"] = float(placement_config.get("legacy_routeable_max_arrangement_variants", 3))
    try:
        selected = select_routeable_arrangement(placement, circuit, wire_config=legacy_wire_config)
        routing_placement = selected.get("routing_placement")
        if not isinstance(routing_placement, dict):
            raise ValueError("legacy routeable arrangement did not return routing_placement")
        state = build_live_routing_state(routing_placement, circuit, component_catalogue=catalogue, config=config)
        report = selected.get("arrangement_selection", {})
        if not isinstance(report, dict):
            report = {}
        return state, {
            "ok": True,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "selected_variant": report.get("selected_variant"),
            "selected_score": report.get("selected_score", {}),
            "variant_count": report.get("variant_count"),
            "worker_count": report.get("worker_count"),
            "max_arrangement_variants": int(legacy_wire_config["max_arrangement_variants"]),
            "purpose": "route-complete floor candidate from v0.1 arrangement selector; still rerouted and validated by v2",
        }
    except Exception as exc:  # pragma: no cover - defensive report path
        return None, {
            "ok": False,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "error": str(exc),
        }


def _route_final_states(
    states: list[LiveRoutingState],
    circuit: dict[str, Any],
    *,
    engine: str,
    config: dict[str, Any],
    wire_config: dict[str, Any] | None,
    state_names: list[str] | None = None,
) -> dict[str, Any]:
    fallback_wire_config = deepcopy(config.get("wire_fallback", {}))
    if wire_config:
        fallback_wire_config.update(wire_config)
    parallel_cfg = config.get("parallel", {}) if isinstance(config.get("parallel"), dict) else {}
    min_variants = max(2, int(parallel_cfg.get("final_state_parallel_min_variants", 2)))
    configured_workers = int(parallel_cfg.get("final_state_route_workers", 0) or 0)
    max_workers = configured_workers if configured_workers > 0 else int(parallel_cfg.get("threads", 1) or 1)
    worker_count = max(1, min(len(states), max_workers))
    if len(states) < min_variants:
        worker_count = 1

    tasks = [
        {
            "index": index,
            "name": state_names[index] if state_names and index < len(state_names) else f"beam_state_{index}",
            "state": state,
            "circuit": circuit,
            "engine": engine,
            "config": config,
            "wire_config": fallback_wire_config,
        }
        for index, state in enumerate(states)
    ]
    routed_variants: list[dict[str, Any]] = []
    parallel_error = ""
    if worker_count > 1:
        try:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                future_map = {executor.submit(_route_final_state_variant, **task): task["name"] for task in tasks}
                for future in as_completed(future_map):
                    routed_variants.append(future.result())
        except Exception as exc:  # pragma: no cover - defensive fallback for thread/runtime edge cases.
            parallel_error = str(exc)
            routed_variants = []
            worker_count = 1
    if not routed_variants:
        routed_variants = [_route_final_state_variant(**task) for task in tasks]
        worker_count = 1
    routed_variants.sort(key=lambda item: (float(item["score"]["score"]), str(item["name"])))
    selected = routed_variants[0]
    return {
        "selected": selected,
        "worker_count": worker_count,
        "parallel_error": parallel_error,
        "variants": [
            {
                "name": item["name"],
                "score": item["score"],
                "elapsed_seconds": item.get("elapsed_seconds"),
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
    rust_terminal_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalogue = load_component_catalogue(component_catalogue_path)
    state = build_live_routing_state(placement, circuit, component_catalogue=catalogue, config=config)
    baseline_state = state.clone_state()
    initial_score = state.score_routeability()
    engine = "python_live_state_v0.2_full_math_router"
    rotation_edits: list[dict[str, Any]] = []
    beam_report: dict[str, Any] = {"strategy": "disabled"}
    final_named_states: list[tuple[str, LiveRoutingState]] = [("initial_live_state", state)]
    variation_cfg = config.get("variation", {}) if isinstance(config.get("variation"), dict) else {}
    variation_enabled = bool(variation_cfg.get("enabled", False))
    if config.get("placement", {}).get("enable_python_live_state_placement", True):
        placement_cfg = config.get("placement", {}) if isinstance(config.get("placement"), dict) else {}
        component_count = len(state.components)
        max_beam_components = int(placement_cfg.get("max_beam_search_components", 12))
        use_beam_search = bool(placement_cfg.get("enable_cluster_growth_beam_search", True)) and (
            variation_enabled or component_count <= max_beam_components
        )
        if use_beam_search:
            rotation_baseline = baseline_state.clone_state()
            baseline_rotation_edits = _rotation_improvement_pass(rotation_baseline)
            baseline_legalization = _legalize_existing_overlaps(rotation_baseline, config)
            beam = state.beam_search_cluster_growth(config)
            state = beam["selected_state"]
            final_named_states = [
                ("initial_baseline", baseline_state),
                ("rotation_baseline", rotation_baseline),
                *[
                    (f"beam_state_{index}", beam_state)
                    for index, beam_state in enumerate(list(beam.get("final_states") or [state]))
                ],
            ]
            beam_report = dict(beam.get("report") or {})
            beam_report["baseline_rotation_edit_count"] = len(baseline_rotation_edits)
            beam_report["baseline_legalization"] = baseline_legalization
            legalization_report = _legalize_existing_overlaps(state, config)
        else:
            rotation_edits = _rotation_improvement_pass(state)
            legalization_report = _legalize_existing_overlaps(state, config)
            final_named_states = [("rotation_improved_state", state)]
            if placement_cfg.get("enable_cluster_growth_beam_search", True) and component_count > max_beam_components:
                beam_report = {
                    "strategy": "adaptive_beam_skipped",
                    "reason": "component_count_exceeds_max_beam_search_components",
                    "component_count": component_count,
                    "max_beam_search_components": max_beam_components,
                    "variation_mode_enabled": variation_enabled,
                }
    else:
        legalization_report = {"moved": [], "failed": [], "overlap_count": len(state.find_overlaps())}

    legacy_state, legacy_report = _legacy_routeable_state_candidate(
        placement,
        circuit,
        catalogue=catalogue,
        config=config,
        wire_config=wire_config,
    )
    beam_report["legacy_routeable_arrangement"] = legacy_report
    if legacy_state is not None:
        final_named_states.insert(0, ("legacy_routeable_arrangement", legacy_state))
    final_named_states = _dedupe_named_states(final_named_states)
    deep_route_candidate_count = len(final_named_states)
    parallel_cfg = config.get("parallel", {}) if isinstance(config.get("parallel"), dict) else {}
    placement_cfg = config.get("placement", {}) if isinstance(config.get("placement"), dict) else {}
    adaptive_cap_disabled = variation_enabled and bool(variation_cfg.get("disable_adaptive_cap", True))
    if adaptive_cap_disabled:
        max_final_states = max(1, len(final_named_states))
    else:
        max_final_states = max(
            1,
            int(
                parallel_cfg.get(
                    "max_final_state_route_variants",
                    placement_cfg.get("deep_route_top_n", 4),
                )
            ),
        )
    protected_names = {"legacy_routeable_arrangement", "rotation_baseline", "rotation_improved_state"}
    protected_states = [item for item in final_named_states if item[0] in protected_names]
    remaining_states = [item for item in final_named_states if item[0] not in protected_names]
    protected_states.sort(key=lambda item: (0 if item[0] == "legacy_routeable_arrangement" else 1, float(item[1].score_routeability()["score"]), item[0]))
    remaining_states.sort(key=lambda item: (float(item[1].score_routeability()["score"]), item[0]))
    final_named_states = [*protected_states, *remaining_states][:max_final_states]
    final_states = [item[1] for item in final_named_states]
    final_state_names = [item[0] for item in final_named_states]

    routed = _route_final_states(
        final_states,
        circuit,
        engine=engine,
        config=config,
        wire_config=wire_config,
        state_names=final_state_names,
    )
    selected = routed["selected"]
    state = selected["state"]
    coordinate_plan = state.to_coordinate_plan()
    coordinate_plan["rotation_score_edits"] = rotation_edits
    coordinate_plan["legalization"] = legalization_report
    coordinate_plan["beam_search"] = beam_report
    coordinate_plan["variation"] = {
        "enabled": variation_enabled,
        "adaptive_cap_disabled": adaptive_cap_disabled,
        "max_final_state_route_variants": max_final_states,
    }
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
            "deep_route_candidate_count": deep_route_candidate_count,
            "deep_route_selected_count": len(final_named_states),
            "variation_mode_enabled": variation_enabled,
            "adaptive_cap_disabled": adaptive_cap_disabled,
            "final_state_route_worker_count": routed.get("worker_count", 1),
            "final_state_parallel_error": routed.get("parallel_error", ""),
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
            "rust_terminal_policy": rust_terminal_policy.get("metrics", {}) if isinstance(rust_terminal_policy, dict) else {},
        },
        "warnings": [
            (
                "Rust terminal policy applied; Python LiveRoutingState remains authoritative for placement and full routing."
                if rust_terminal_policy
                else "Rust routing core is not installed; used Python LiveRoutingState full mathematical fallback."
            ),
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
    effective_wire_config = deepcopy(wire_config) if wire_config else None
    payload = {
        "catalogue": catalogue.as_dict(),
        "placement_fallbacks": _placement_fallbacks_for_rust(placement, circuit),
        "placement": placement,
        "circuit": circuit,
        "config": merged_config,
    }
    rust_terminal_policy = None
    wire_fallback = merged_config.get("wire_fallback", {}) if isinstance(merged_config.get("wire_fallback"), dict) else {}
    requested_routing_mode = str(
        (wire_config or {}).get("routing_mode") if isinstance(wire_config, dict) and wire_config.get("routing_mode") else wire_fallback.get("routing_mode", "wire")
    ).lower()
    if requested_routing_mode == "wire":
        rust_terminal_policy = _try_rust_terminal_policy(payload)
        if isinstance(rust_terminal_policy, dict):
            patch = rust_terminal_policy.get("wire_config_patch")
            if isinstance(patch, dict):
                effective_wire_config = dict(effective_wire_config or {})
                effective_wire_config.update(patch)
                merged_config.setdefault("wire_fallback", {}).update(patch)
                payload["config"] = merged_config
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
        wire_config=effective_wire_config,
        rust_terminal_policy=rust_terminal_policy,
    )
