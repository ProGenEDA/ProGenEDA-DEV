"""Pure JSON wire planner.

The wire planner is EDA-agnostic. It consumes:

1. placement JSON with component centers and obstacle boxes
2. CircuitIR-style JSON with component pins / net connections

It emits two JSON contracts:

1. coordinate-plan JSON for the beautifier
2. wire-plan JSON for a later KiCad/Proteus-specific wire maker
"""

from __future__ import annotations

import heapq
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .arrangement_decider import DEFAULT_ARRANGEMENT_CONFIG, GROUND_NETS, POWER_NETS, decide_arrangement, extract_connection_nets
from .beautifier import apply_coordinate_edits


Point = tuple[float, float]
GridPoint = tuple[int, int]


@dataclass(frozen=True)
class Body:
    ref: str
    left: float
    top: float
    right: float
    bottom: float
    component_ref: str | None = None

    @property
    def center(self) -> Point:
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)

    def contains(self, point: Point, clearance: float = 0.0) -> bool:
        x, y = point
        return self.left - clearance <= x <= self.right + clearance and self.top - clearance <= y <= self.bottom + clearance


ROUTING_MODES = {"wire", "terminal", "combination"}
LABEL_STRATEGIES = {"local_labels", "single_endpoint_label", "local_labels_after_router_failure", "local_labels_after_geometry_violation"}

DEFAULT_WIRE_CONFIG: dict[str, Any] = {
    "routing_mode": "wire",
    "grid": 2.54,
    "sheet_width": 420.0,
    "sheet_height": 297.0,
    "margin": 15.24,
    "clearance": 2.54,
    "pin_stub": 5.08,
    "wire_spacing": 2.54,
    "turn_penalty": 0.15,
    "near_wire_penalty": 0.0,
    "block_existing_wires": 0.0,
    "max_astar_expansions": 50_000.0,
    "strict_fallback_max_astar_expansions": 50_000.0,
    "max_wired_routes": 10_000.0,
    "lane_router": 1.0,
    "lane_step": 7.62,
    "max_lane_candidates": 256.0,
    "crossing_penalty": 0.0,
    "forbidden_contact_penalty": 250_000.0,
    "density_tile_size": 25.4,
    "max_crossings_per_tile_soft": 6.0,
    "same_net_reuse_penalty": 0.05,
    "body_crossing_penalty": 100_000.0,
    "component_shadow_penalty": 80.0,
    "component_shadow_clearance": 12.7,
    "long_lane_threshold": 80.0,
    "long_lane_outer_penalty": 12.0,
    "exact_crossing_score_segment_limit": 80.0,
    "body_grid_score_component_limit": 80.0,
    "dense_design_component_limit": 90.0,
    "dense_max_lane_candidates": 256.0,
    "dense_max_astar_expansions": 1500.0,
    "max_failed_endpoints_per_net": 1000.0,
    "dense_max_failed_endpoints_per_net": 1000.0,
    "dense_force_grid_contact_scoring": 1.0,
    "dense_skip_astar_when_lane_candidate": 1.0,
    "crossing_risk_astar": 0.0,
    "lane_zero_crossing_fast_accept": 1.0,
    "arrangement_variant_search": 1.0,
    "max_arrangement_variants": 5.0,
    "arrangement_variant_workers": 0.0,
    "arrangement_variant_parallel_min_components": 40.0,
    "arrangement_variant_max_astar_expansions": 600.0,
    "arrangement_variant_max_lane_candidates": 32.0,
    "arrangement_variant_max_failed_endpoints_per_net": 1.0,
    "arrangement_variant_max_root_candidates": 1.0,
    "arrangement_final_wire_route": 1.0,
    "max_root_candidates_per_endpoint": 3.0,
    "max_endpoint_retry_attempts": 4.0,
    "salvage_astar_expansions": 200_000.0,
    "max_salvage_astar_attempts": 12.0,
    "max_partial_route_component_moves": 8.0,
    "partial_route_move_search_steps": 14.0,
    "partial_route_move_body_clearance": 0.0,
    "partial_route_move_min_pin_gap": 10.16,
}


def normalize_routing_mode(value: object) -> str:
    mode = str(value or "wire").strip().lower().replace("-", "_")
    if mode not in ROUTING_MODES:
        raise ValueError(f"Unsupported routing_mode {value!r}; expected one of: {', '.join(sorted(ROUTING_MODES))}")
    return mode


def _wire_config(config: dict[str, Any] | None, circuit: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = dict(DEFAULT_WIRE_CONFIG)
    explicit_strict_fallback_budget = False
    circuit_mode = None
    if isinstance(circuit, dict):
        raw_routing = circuit.get("routing")
        if isinstance(raw_routing, dict):
            circuit_mode = raw_routing.get("mode")
    if circuit_mode:
        cfg["routing_mode"] = circuit_mode
    if config:
        explicit_strict_fallback_budget = "strict_fallback_max_astar_expansions" in config
        for key, value in config.items():
            cfg[key] = value if key == "routing_mode" else float(value)
    cfg["routing_mode"] = normalize_routing_mode(cfg.get("routing_mode"))
    if not explicit_strict_fallback_budget:
        cfg["strict_fallback_max_astar_expansions"] = float(cfg.get("max_astar_expansions", 50_000.0))
    return cfg


def _snap(value: float, grid: float) -> float:
    return round(round(value / grid) * grid, 3)


def _round_point(point: Point) -> Point:
    return (round(point[0], 3), round(point[1], 3))


def _bodies(placement: dict[str, Any]) -> dict[str, Body]:
    bodies: dict[str, Body] = {}
    for item in placement.get("obstacles", []):
        if isinstance(item, dict) and item.get("owner"):
            owner = str(item["owner"])
            bodies[owner] = Body(
                owner,
                float(item.get("left", 0.0)),
                float(item.get("top", 0.0)),
                float(item.get("right", 0.0)),
                float(item.get("bottom", 0.0)),
                str(item.get("component_ref") or owner),
            )
    components = placement.get("components", {})
    if isinstance(components, dict):
        for ref, component in components.items():
            if not isinstance(component, dict):
                continue
            if ref in bodies or any(body.component_ref == str(ref) for body in bodies.values()):
                continue
            at = component.get("at", [0.0, 0.0])
            if not isinstance(at, (list, tuple)) or len(at) < 2:
                at = [0.0, 0.0]
            width = float(component.get("width", 10.0))
            height = float(component.get("height", 8.0))
            x = float(at[0])
            y = float(at[1])
            bodies[str(ref)] = Body(str(ref), x - width / 2, y - height / 2, x + width / 2, y + height / 2, str(ref))
    return bodies


def _sheet_bounds(bodies: dict[str, Body], cfg: dict[str, float]) -> tuple[float, float]:
    max_right = max((body.right for body in bodies.values()), default=cfg["sheet_width"])
    max_bottom = max((body.bottom for body in bodies.values()), default=cfg["sheet_height"])
    return (max(cfg["sheet_width"], max_right + cfg["margin"]), max(cfg["sheet_height"], max_bottom + cfg["margin"]))


def _body_for_component(ref: str, bodies: dict[str, Body], point: Point | None = None) -> Body | None:
    candidates = [body for body in bodies.values() if body.ref == ref or body.component_ref == ref]
    if not candidates:
        return None
    if point is None:
        return candidates[0]
    return min(
        candidates,
        key=lambda body: (
            0 if body.contains(point, 0.001) else 1,
            abs(body.center[0] - point[0]) + abs(body.center[1] - point[1]),
        ),
    )


def _body_center_x(ref: str, bodies: dict[str, Body]) -> float | None:
    body = _body_for_component(ref, bodies)
    return body.center[0] if body else None


def _side_from_pin_point(point: Point, body: Body | None, net: str) -> str:
    if body is None:
        return "right"
    if point[0] < body.left:
        return "left"
    if point[0] > body.right:
        return "right"
    if point[1] < body.top:
        return "top"
    if point[1] > body.bottom:
        return "bottom"
    distances = {
        "left": abs(point[0] - body.left),
        "right": abs(point[0] - body.right),
        "top": abs(point[1] - body.top),
        "bottom": abs(point[1] - body.bottom),
    }
    return min(distances.items(), key=lambda item: item[1])[0]


def _pin_point_lookup(placement: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    raw = placement.get("pin_points") or {}
    out: dict[tuple[str, str], dict[str, Any]] = {}
    if isinstance(raw, dict):
        for ref, pins in raw.items():
            if not isinstance(pins, dict):
                continue
            for pin, data in pins.items():
                if not isinstance(data, dict):
                    continue
                point = data.get("point")
                if isinstance(point, (list, tuple)) and len(point) >= 2:
                    key = (str(ref), str(pin))
                    item = dict(data)
                    item["point"] = [float(point[0]), float(point[1])]
                    out[key] = item
                    out[(key[0], key[1].upper())] = item
    elif isinstance(raw, list):
        for data in raw:
            if not isinstance(data, dict):
                continue
            ref = str(data.get("ref") or "")
            pin = str(data.get("pin") or "")
            point = data.get("point")
            if ref and pin and isinstance(point, (list, tuple)) and len(point) >= 2:
                item = dict(data)
                item["point"] = [float(point[0]), float(point[1])]
                out[(ref, pin)] = item
                out[(ref, pin.upper())] = item
    return out


def _side_for_endpoint(net: str, ref: str, refs: list[str], bodies: dict[str, Body]) -> str:
    upper = net.upper()
    if upper in POWER_NETS:
        return "top"
    if upper in GROUND_NETS:
        return "bottom"
    body = _body_for_component(ref, bodies)
    if body is None:
        return "right"
    others = [center_x for other in refs if other != ref and (center_x := _body_center_x(other, bodies)) is not None]
    if not others:
        return "right"
    return "right" if sum(others) / len(others) >= body.center[0] else "left"


def _endpoint_points(placement: dict[str, Any], circuit: dict[str, Any], cfg: dict[str, float]) -> dict[str, list[dict[str, Any]]]:
    bodies = _bodies(placement)
    pin_points = _pin_point_lookup(placement)
    nets = extract_connection_nets(circuit)
    side_buckets: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    endpoint_meta: dict[tuple[str, str, str], str] = {}
    for net, endpoints in nets.items():
        refs = sorted({endpoint.ref for endpoint in endpoints if _body_for_component(endpoint.ref, bodies) is not None or (endpoint.ref, endpoint.pin) in pin_points})
        for endpoint in endpoints:
            exact = pin_points.get((endpoint.ref, endpoint.pin)) or pin_points.get((endpoint.ref, endpoint.pin.upper()))
            body = _body_for_component(endpoint.ref, bodies)
            if body is None and exact is None:
                continue
            if exact:
                raw_point = exact["point"]
                point = (float(raw_point[0]), float(raw_point[1]))
                side = str(exact.get("side") or _side_from_pin_point(point, _body_for_component(endpoint.ref, bodies, point), net))
            else:
                side = _side_for_endpoint(net, endpoint.ref, refs, bodies)
            key = (endpoint.ref, side)
            side_buckets[key].append((net, endpoint.pin))
            endpoint_meta[(net, endpoint.ref, endpoint.pin)] = side

    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for net, endpoints in nets.items():
        refs = sorted({endpoint.ref for endpoint in endpoints if _body_for_component(endpoint.ref, bodies) is not None or (endpoint.ref, endpoint.pin) in pin_points})
        for endpoint in endpoints:
            exact = pin_points.get((endpoint.ref, endpoint.pin)) or pin_points.get((endpoint.ref, endpoint.pin.upper()))
            body = _body_for_component(endpoint.ref, bodies)
            if body is None and exact is None:
                continue
            side = endpoint_meta[(net, endpoint.ref, endpoint.pin)]
            if exact:
                raw_point = exact["point"]
                point = (_snap(float(raw_point[0]), cfg["grid"]), _snap(float(raw_point[1]), cfg["grid"]))
                exact_source = str(exact.get("source") or "exact_pin_point")
            else:
                if body is None:
                    continue
                bucket = sorted(side_buckets[(endpoint.ref, side)])
                index = bucket.index((net, endpoint.pin))
                count = len(bucket)
                offset = (index - (count - 1) / 2) * cfg["wire_spacing"]
                if side == "left":
                    point = (body.left - cfg["pin_stub"], body.center[1] + offset)
                elif side == "right":
                    point = (body.right + cfg["pin_stub"], body.center[1] + offset)
                elif side == "top":
                    point = (body.center[0] + offset, body.top - cfg["pin_stub"])
                else:
                    point = (body.center[0] + offset, body.bottom + cfg["pin_stub"])
                point = (_snap(point[0], cfg["grid"]), _snap(point[1], cfg["grid"]))
                exact_source = ""
            out[net].append(
                {
                    "ref": endpoint.ref,
                    "pin": endpoint.pin,
                    "side": side,
                    "point": [point[0], point[1]],
                    "exact": bool(exact),
                    "source": exact_source or "estimated_component_edge",
                }
            )
    return dict(sorted(out.items()))


def _to_grid(point: Point, grid: float) -> GridPoint:
    return (round(point[0] / grid), round(point[1] / grid))


def _from_grid(point: GridPoint, grid: float) -> Point:
    return (round(point[0] * grid, 3), round(point[1] * grid, 3))


def _blocked_cells(
    bodies: dict[str, Body],
    cfg: dict[str, float],
    *,
    ignore_refs: set[str],
    clearance: float | None = None,
) -> set[GridPoint]:
    grid = cfg["grid"]
    use_clearance = cfg["clearance"] if clearance is None else clearance
    blocked: set[GridPoint] = set()
    for ref, body in bodies.items():
        if ref in ignore_refs or (body.component_ref and body.component_ref in ignore_refs):
            continue
        left = round((body.left - use_clearance) / grid)
        right = round((body.right + use_clearance) / grid)
        top = round((body.top - use_clearance) / grid)
        bottom = round((body.bottom + use_clearance) / grid)
        for x in range(left, right + 1):
            for y in range(top, bottom + 1):
                blocked.add((x, y))
    return blocked


def _open_pin_portals(
    blocked: set[GridPoint],
    bodies: dict[str, Body],
    portals: list[tuple[str, Point, str]],
    cfg: dict[str, float],
) -> None:
    grid = cfg["grid"]
    steps = max(3, int(round((cfg["clearance"] + cfg["pin_stub"]) / grid)) + 1)
    directions = {
        "left": (-1, 0),
        "right": (1, 0),
        "top": (0, -1),
        "bottom": (0, 1),
    }
    def touches_other_body(ref: str, cell: GridPoint) -> bool:
        point = _from_grid(cell, grid)
        for body in bodies.values():
            if body.ref == ref or body.component_ref == ref:
                continue
            if body.contains(point, 0.0):
                return True
        return False

    for ref, point, side in portals:
        dx, dy = directions.get(side, (1, 0))
        start = _to_grid(point, grid)
        for step in range(steps + 1):
            cell = (start[0] + dx * step, start[1] + dy * step)
            if not touches_other_body(ref, cell):
                blocked.discard(cell)
            if dx:
                for adjacent in ((cell[0], cell[1] - 1), (cell[0], cell[1] + 1)):
                    if not touches_other_body(ref, adjacent):
                        blocked.discard(adjacent)
            else:
                for adjacent in ((cell[0] - 1, cell[1]), (cell[0] + 1, cell[1])):
                    if not touches_other_body(ref, adjacent):
                        blocked.discard(adjacent)


def _portal_point(point: Point, side: str, cfg: dict[str, float]) -> Point:
    directions = {
        "left": (-1.0, 0.0),
        "right": (1.0, 0.0),
        "top": (0.0, -1.0),
        "bottom": (0.0, 1.0),
    }
    dx, dy = directions.get(side, (1.0, 0.0))
    return (
        _snap(point[0] + dx * cfg["pin_stub"], cfg["grid"]),
        _snap(point[1] + dy * cfg["pin_stub"], cfg["grid"]),
    )


def _neighbors(point: GridPoint) -> tuple[GridPoint, GridPoint, GridPoint, GridPoint]:
    x, y = point
    return ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))


def _direction(a: GridPoint, b: GridPoint) -> str:
    if b[0] > a[0]:
        return "R"
    if b[0] < a[0]:
        return "L"
    if b[1] > a[1]:
        return "D"
    return "U"


def _astar(
    start: Point,
    goal: Point,
    bodies: dict[str, Body],
    cfg: dict[str, float],
    occupied: dict[GridPoint, str],
    *,
    net: str,
    ignore_refs: set[str],
    portals: list[tuple[str, Point, str]] | None = None,
) -> tuple[list[Point], list[str]]:
    grid = cfg["grid"]
    width, height = _sheet_bounds(bodies, cfg)
    max_x = round(width / grid)
    max_y = round(height / grid)
    start_cell = _to_grid(start, grid)
    goal_cell = _to_grid(goal, grid)
    blocked = _blocked_cells(bodies, cfg, ignore_refs=ignore_refs)
    blocked.discard(start_cell)
    blocked.discard(goal_cell)
    _open_pin_portals(blocked, bodies, portals or [], cfg)

    def heuristic(cell: GridPoint) -> float:
        return abs(cell[0] - goal_cell[0]) + abs(cell[1] - goal_cell[1])

    queue: list[tuple[float, float, GridPoint, str]] = [(heuristic(start_cell), 0.0, start_cell, "")]
    came_from: dict[tuple[GridPoint, str], tuple[GridPoint, str]] = {}
    best: dict[tuple[GridPoint, str], float] = {(start_cell, ""): 0.0}
    end_state: tuple[GridPoint, str] | None = None
    warnings: list[str] = []
    expansions = 0
    max_expansions = max(1, int(cfg.get("max_astar_expansions", 50_000.0)))

    while queue:
        _priority, cost, cell, direction = heapq.heappop(queue)
        expansions += 1
        if expansions > max_expansions:
            warnings.append(f"astar_unroutable_expansion_limit: {net} exceeded {max_expansions} explored grid states.")
            return [], warnings
        if cell == goal_cell:
            end_state = (cell, direction)
            break
        for nxt in _neighbors(cell):
            if nxt[0] < 0 or nxt[1] < 0 or nxt[0] > max_x or nxt[1] > max_y:
                continue
            if nxt in blocked:
                continue
            nxt_direction = _direction(cell, nxt)
            step_cost = 1.0
            if direction and nxt_direction != direction:
                step_cost += cfg["turn_penalty"]
            owner = occupied.get(nxt)
            if owner:
                if cfg.get("block_existing_wires", 1.0) >= 1.0 and nxt not in {start_cell, goal_cell}:
                    continue
                if owner != net:
                    step_cost += 50.0
            for adjacent in _neighbors(nxt):
                adjacent_owner = occupied.get(adjacent)
                if adjacent_owner and adjacent_owner != net:
                    step_cost += cfg["near_wire_penalty"]
            new_cost = cost + step_cost
            state = (nxt, nxt_direction)
            if new_cost < best.get(state, float("inf")):
                best[state] = new_cost
                came_from[state] = (cell, direction)
                heapq.heappush(queue, (new_cost + heuristic(nxt), new_cost, nxt, nxt_direction))

    if end_state is None:
        warnings.append(f"astar_unroutable_no_clear_route: no clear route found for {net}.")
        return [], warnings

    cells: list[GridPoint] = []
    state = end_state
    while True:
        cells.append(state[0])
        if state[0] == start_cell:
            break
        state = came_from[state]
    cells.reverse()
    return [_from_grid(cell, grid) for cell in cells], warnings


def _compress_path(path: list[Point]) -> list[Point]:
    if len(path) <= 2:
        return [_round_point(point) for point in path]
    out = [_round_point(path[0])]
    last_direction: str | None = None
    for left, right in zip(path, path[1:]):
        direction = "H" if left[1] == right[1] else "V"
        if last_direction is None:
            last_direction = direction
            continue
        if direction != last_direction:
            out.append(_round_point(left))
            last_direction = direction
    out.append(_round_point(path[-1]))
    return out


def _segments(path: list[Point]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for start, end in zip(path, path[1:]):
        if start == end:
            continue
        if start[0] == end[0]:
            direction = "down" if end[1] > start[1] else "up"
        elif start[1] == end[1]:
            direction = "right" if end[0] > start[0] else "left"
        else:
            direction = "non_orthogonal"
        out.append(
            {
                "start": [start[0], start[1]],
                "end": [end[0], end[1]],
                "direction": direction,
                "length": round(abs(end[0] - start[0]) + abs(end[1] - start[1]), 3),
            }
        )
    return out


def _point_on_segment(point: Point, start: Point, end: Point, eps: float = 0.001) -> bool:
    if abs(start[1] - end[1]) <= eps:
        low, high = sorted((start[0], end[0]))
        return abs(point[1] - start[1]) <= eps and low - eps <= point[0] <= high + eps
    if abs(start[0] - end[0]) <= eps:
        low, high = sorted((start[1], end[1]))
        return abs(point[0] - start[0]) <= eps and low - eps <= point[1] <= high + eps
    return False


def _is_endpoint(point: Point, start: Point, end: Point, eps: float = 0.001) -> bool:
    return abs(point[0] - start[0]) <= eps and abs(point[1] - start[1]) <= eps or abs(point[0] - end[0]) <= eps and abs(point[1] - end[1]) <= eps


def _strict_between(value: float, left: float, right: float, eps: float = 0.001) -> bool:
    low, high = sorted((left, right))
    return low + eps < value < high - eps


def _segment_contact_kind(a1: Point, a2: Point, b1: Point, b2: Point) -> str:
    """Classify different-net wire contact for schematic routing.

    Returns ``crossing`` for allowed open 90-degree crossings, ``forbidden`` for
    collinear overlap/T-touch/endpoint touch, and ``none`` otherwise.
    """
    eps = 0.001
    a_h = abs(a1[1] - a2[1]) <= eps
    a_v = abs(a1[0] - a2[0]) <= eps
    b_h = abs(b1[1] - b2[1]) <= eps
    b_v = abs(b1[0] - b2[0]) <= eps
    if not (a_h or a_v) or not (b_h or b_v):
        return "forbidden"
    if a_h and b_h:
        if abs(a1[1] - b1[1]) > eps:
            return "none"
        low = max(min(a1[0], a2[0]), min(b1[0], b2[0]))
        high = min(max(a1[0], a2[0]), max(b1[0], b2[0]))
        if low > high + eps:
            return "none"
        return "forbidden"
    if a_v and b_v:
        if abs(a1[0] - b1[0]) > eps:
            return "none"
        low = max(min(a1[1], a2[1]), min(b1[1], b2[1]))
        high = min(max(a1[1], a2[1]), max(b1[1], b2[1]))
        if low > high + eps:
            return "none"
        return "forbidden"
    horizontal = (a1, a2) if a_h else (b1, b2)
    vertical = (b1, b2) if a_h else (a1, a2)
    point = (vertical[0][0], horizontal[0][1])
    if not _point_on_segment(point, horizontal[0], horizontal[1], eps) or not _point_on_segment(point, vertical[0], vertical[1], eps):
        return "none"
    horizontal_interior = _strict_between(point[0], horizontal[0][0], horizontal[1][0], eps)
    vertical_interior = _strict_between(point[1], vertical[0][1], vertical[1][1], eps)
    if horizontal_interior and vertical_interior:
        return "crossing"
    return "forbidden"


def _segment_hits_body(start: Point, end: Point, body: Body, clearance: float) -> bool:
    left = body.left - clearance
    right = body.right + clearance
    top = body.top - clearance
    bottom = body.bottom + clearance
    if abs(start[0] - end[0]) <= 0.001:
        x = start[0]
        if x < left or x > right:
            return False
        low, high = sorted((start[1], end[1]))
        return high > top and low < bottom
    if abs(start[1] - end[1]) <= 0.001:
        y = start[1]
        if y < top or y > bottom:
            return False
        low, high = sorted((start[0], end[0]))
        return high > left and low < right
    return True


def _path_length(path: list[Point]) -> float:
    return sum(_manhattan(left, right) for left, right in zip(path, path[1:]))


def _path_turn_count(path: list[Point]) -> int:
    turns = 0
    previous: str | None = None
    for left, right in zip(path, path[1:]):
        if left == right:
            continue
        direction = "H" if left[1] == right[1] else "V"
        if previous is not None and direction != previous:
            turns += 1
        previous = direction
    return turns


def _path_body_hit_count(
    path: list[Point],
    bodies: dict[str, Body],
    cfg: dict[str, Any],
    *,
    ignore_refs: set[str],
    blocked_cells: set[GridPoint] | None = None,
) -> int:
    if blocked_cells is not None and len(bodies) > int(cfg.get("body_grid_score_component_limit", 80.0)):
        return _path_blocked_cell_count(path, blocked_cells, grid=float(cfg["grid"]))
    hits = 0
    for start, end in zip(path, path[1:]):
        for body in bodies.values():
            if body.ref in ignore_refs or (body.component_ref and body.component_ref in ignore_refs):
                continue
            if _segment_hits_body(start, end, body, float(cfg["clearance"])):
                hits += 1
    return hits


def _path_blocked_cell_count(path: list[Point], blocked_cells: set[GridPoint], *, grid: float) -> int:
    hits: set[GridPoint] = set()
    for start, end in zip(path, path[1:]):
        for cell in _grid_cells_for_segment(start, end, grid):
            if cell in blocked_cells:
                hits.add(cell)
    return len(hits)


def _path_component_shadow_count(
    path: list[Point],
    bodies: dict[str, Body],
    cfg: dict[str, Any],
    *,
    ignore_refs: set[str],
    blocked_cells: set[GridPoint] | None = None,
) -> int:
    if blocked_cells is not None and len(bodies) > int(cfg.get("body_grid_score_component_limit", 80.0)):
        return _path_blocked_cell_count(path, blocked_cells, grid=float(cfg["grid"]))
    shadow_clearance = float(cfg.get("component_shadow_clearance", cfg["clearance"]))
    shadows = 0
    for start, end in zip(path, path[1:]):
        for body in bodies.values():
            if body.ref in ignore_refs or (body.component_ref and body.component_ref in ignore_refs):
                continue
            if _segment_hits_body(start, end, body, shadow_clearance):
                shadows += 1
    return shadows


def _path_outer_channel_cost(path: list[Point], bodies: dict[str, Body], cfg: dict[str, Any]) -> float:
    width, height = _sheet_bounds(bodies, cfg)
    threshold = float(cfg.get("long_lane_threshold", 80.0))
    cost = 0.0
    for start, end in zip(path, path[1:]):
        length = _manhattan(start, end)
        if length < threshold:
            continue
        if abs(start[1] - end[1]) <= 0.001:
            edge_distance = min(start[1], max(0.0, height - start[1]))
        elif abs(start[0] - end[0]) <= 0.001:
            edge_distance = min(start[0], max(0.0, width - start[0]))
        else:
            edge_distance = 0.0
        cost += edge_distance * (length / threshold)
    return cost


def _path_wire_contact_counts(
    path: list[Point],
    existing_segments: list[tuple[str, Point, Point]],
    *,
    net: str,
    cfg: dict[str, Any] | None = None,
    occupied: dict[GridPoint, str] | None = None,
) -> tuple[int, int, int]:
    if (
        cfg is not None
        and occupied is not None
        and len(existing_segments) > int(cfg.get("exact_crossing_score_segment_limit", 700.0))
    ):
        different, same = _path_grid_contact_counts(path, occupied, net=net, grid=float(cfg["grid"]))
        return different, same, 0

    different_net_crossings = 0
    same_net = 0
    forbidden_contacts = 0
    for start, end in zip(path, path[1:]):
        for other_net, other_start, other_end in existing_segments:
            if other_net == net:
                if _point_on_segment(start, other_start, other_end) or _point_on_segment(end, other_start, other_end) or _segments_cross(start, end, other_start, other_end):
                    same_net += 1
            else:
                contact_kind = _segment_contact_kind(start, end, other_start, other_end)
                if contact_kind == "crossing":
                    different_net_crossings += 1
                elif contact_kind == "forbidden":
                    forbidden_contacts += 1
    return different_net_crossings, same_net, forbidden_contacts


def _grid_cells_for_segment(start: Point, end: Point, grid: float) -> list[GridPoint]:
    start_cell = _to_grid(start, grid)
    end_cell = _to_grid(end, grid)
    if start_cell == end_cell:
        return [start_cell]
    cells: list[GridPoint] = []
    if start_cell[0] == end_cell[0]:
        low, high = sorted((start_cell[1], end_cell[1]))
        cells = [(start_cell[0], y) for y in range(low, high + 1)]
    elif start_cell[1] == end_cell[1]:
        low, high = sorted((start_cell[0], end_cell[0]))
        cells = [(x, start_cell[1]) for x in range(low, high + 1)]
    else:
        cells = [start_cell, end_cell]
    return cells


def _path_grid_contact_counts(
    path: list[Point],
    occupied: dict[GridPoint, str],
    *,
    net: str,
    grid: float,
) -> tuple[int, int]:
    different: set[GridPoint] = set()
    same: set[GridPoint] = set()
    for start, end in zip(path, path[1:]):
        for cell in _grid_cells_for_segment(start, end, grid):
            owner = occupied.get(cell)
            if not owner:
                continue
            if owner == net:
                same.add(cell)
            else:
                different.add(cell)
    return len(different), len(same)


def _path_score(
    path: list[Point],
    *,
    bodies: dict[str, Body],
    existing_segments: list[tuple[str, Point, Point]],
    cfg: dict[str, Any],
    net: str,
    ignore_refs: set[str],
    occupied: dict[GridPoint, str] | None = None,
    hard_blocked_cells: set[GridPoint] | None = None,
    shadow_blocked_cells: set[GridPoint] | None = None,
) -> tuple[float, dict[str, Any]]:
    body_hits = _path_body_hit_count(path, bodies, cfg, ignore_refs=ignore_refs, blocked_cells=hard_blocked_cells)
    if body_hits:
        length = _path_length(path)
        turns = _path_turn_count(path)
        score = body_hits * float(cfg["body_crossing_penalty"]) + turns * float(cfg["turn_penalty"]) + length
        return (
            score,
            {
                "body_hits": body_hits,
                "component_shadow_count": 0,
                "outer_channel_cost": 0.0,
                "different_net_crossings": 0,
                "forbidden_contacts": 0,
                "same_net_contacts": 0,
                "length": round(length, 3),
                "turns": turns,
            },
        )
    body_shadows = _path_component_shadow_count(path, bodies, cfg, ignore_refs=ignore_refs, blocked_cells=shadow_blocked_cells)
    outer_channel_cost = _path_outer_channel_cost(path, bodies, cfg)
    crossings, same_net_contacts, forbidden_contacts = _path_wire_contact_counts(path, existing_segments, net=net, cfg=cfg, occupied=occupied)
    length = _path_length(path)
    turns = _path_turn_count(path)
    score = (
        body_hits * float(cfg["body_crossing_penalty"])
        + body_shadows * float(cfg["component_shadow_penalty"])
        + outer_channel_cost * float(cfg["long_lane_outer_penalty"])
        + forbidden_contacts * float(cfg["forbidden_contact_penalty"])
        + crossings * float(cfg["crossing_penalty"])
        + turns * float(cfg["turn_penalty"])
        + length
        + same_net_contacts * float(cfg["same_net_reuse_penalty"])
    )
    return (
        score,
        {
            "body_hits": body_hits,
            "component_shadow_count": body_shadows,
            "outer_channel_cost": round(outer_channel_cost, 3),
            "different_net_crossings": crossings,
            "forbidden_contacts": forbidden_contacts,
            "same_net_contacts": same_net_contacts,
            "length": round(length, 3),
            "turns": turns,
        },
    )


def _dedupe_path(path: list[Point]) -> list[Point]:
    out: list[Point] = []
    for point in path:
        rounded = _round_point(point)
        if out and out[-1] == rounded:
            continue
        out.append(rounded)
    return out


def _lane_values(
    *,
    axis: str,
    start: Point,
    goal: Point,
    bodies: dict[str, Body],
    cfg: dict[str, Any],
    hanan_points: list[Point] | None = None,
) -> list[float]:
    width, height = _sheet_bounds(bodies, cfg)
    grid = float(cfg["grid"])
    margin = float(cfg["margin"])
    clearance = float(cfg["clearance"])
    lane_step = max(grid, float(cfg.get("lane_step", grid * 3)))
    limit = width if axis == "x" else height
    edge_values: set[float] = {
        margin,
        max(margin, limit - margin),
        min(limit - margin, margin + lane_step),
        max(margin, limit - margin - lane_step),
    }
    anchor_values: set[float] = {
        (start[0] if axis == "x" else start[1]),
        (goal[0] if axis == "x" else goal[1]),
    }
    for point in hanan_points or []:
        anchor_values.add(point[0] if axis == "x" else point[1])
    values: set[float] = set(edge_values) | set(anchor_values) | {limit / 2}
    for body in bodies.values():
        if axis == "x":
            values.add(body.left - clearance - lane_step / 2)
            values.add(body.right + clearance + lane_step / 2)
            values.add(body.center[0])
        else:
            values.add(body.top - clearance - lane_step / 2)
            values.add(body.bottom + clearance + lane_step / 2)
            values.add(body.center[1])
    sorted_bodies = sorted(bodies.values(), key=lambda item: item.left if axis == "x" else item.top)
    for left, right in zip(sorted_bodies, sorted_bodies[1:]):
        gap_start = left.right if axis == "x" else left.bottom
        gap_end = right.left if axis == "x" else right.top
        if gap_end - gap_start >= lane_step:
            values.add((gap_start + gap_end) / 2)
    snapped_edges = sorted({_snap(value, grid) for value in edge_values if margin <= value <= limit - margin})
    snapped_anchors = sorted({_snap(value, grid) for value in anchor_values if margin <= value <= limit - margin})
    snapped = sorted({_snap(value, grid) for value in values if margin <= value <= limit - margin})
    origin = (start[0] + goal[0]) / 2 if axis == "x" else (start[1] + goal[1]) / 2
    remaining = [
        value
        for value in snapped
        if value not in set(snapped_edges) and value not in set(snapped_anchors)
    ]
    remaining.sort(key=lambda value: (abs(value - origin), value))
    out: list[float] = []
    for value in [*snapped_anchors, *snapped_edges, *remaining]:
        if value not in out:
            out.append(value)
    return out


def _candidate_lane_paths(
    start: Point,
    goal: Point,
    bodies: dict[str, Body],
    cfg: dict[str, Any],
    *,
    hanan_points: list[Point] | None = None,
) -> list[list[Point]]:
    candidates: list[list[Point]] = []
    if start[0] == goal[0] or start[1] == goal[1]:
        candidates.append(_dedupe_path([start, goal]))
    candidates.append(_dedupe_path([start, (goal[0], start[1]), goal]))
    candidates.append(_dedupe_path([start, (start[0], goal[1]), goal]))

    y_lanes = _lane_values(axis="y", start=start, goal=goal, bodies=bodies, cfg=cfg, hanan_points=hanan_points)
    x_lanes = _lane_values(axis="x", start=start, goal=goal, bodies=bodies, cfg=cfg, hanan_points=hanan_points)
    max_candidates = max(8, int(cfg.get("max_lane_candidates", 160.0)))
    single_budget = max(4, max_candidates // 4)
    pair_width = max(2, min(5, int((max_candidates / 4) ** 0.5) + 2))
    for lane_x in x_lanes[:pair_width]:
        for lane_y in y_lanes[:pair_width]:
            candidates.append(_dedupe_path([start, (lane_x, start[1]), (lane_x, lane_y), (goal[0], lane_y), goal]))
            candidates.append(_dedupe_path([start, (start[0], lane_y), (lane_x, lane_y), (lane_x, goal[1]), goal]))
    for lane_y in y_lanes[:single_budget]:
        candidates.append(_dedupe_path([start, (start[0], lane_y), (goal[0], lane_y), goal]))
    for lane_x in x_lanes[:single_budget]:
        candidates.append(_dedupe_path([start, (lane_x, start[1]), (lane_x, goal[1]), goal]))

    seen: set[tuple[Point, ...]] = set()
    out: list[list[Point]] = []
    for candidate in candidates:
        compressed = _compress_path(candidate)
        key = tuple(compressed)
        if len(compressed) < 2 or key in seen:
            continue
        seen.add(key)
        out.append(compressed)
        if len(out) >= max_candidates:
            break
    return out


def _root_candidate_routeability_score(
    root: dict[str, Any],
    target: dict[str, Any],
    bodies: dict[str, Body],
    cfg: dict[str, Any],
    *,
    net: str,
    hanan_points: list[Point] | None = None,
) -> tuple[int, float, float, str, str]:
    start = (float(root["point"][0]), float(root["point"][1]))
    goal = (float(target["point"][0]), float(target["point"][1]))
    start_route = _portal_point(start, str(root.get("side") or "right"), cfg)
    goal_route = _portal_point(goal, str(target.get("side") or "right"), cfg)
    ignore_refs: set[str] = set()
    if not root.get("exact"):
        ignore_refs.add(str(root["ref"]))
    if not target.get("exact"):
        ignore_refs.add(str(target["ref"]))

    best_hits: int | None = None
    best_length = float("inf")
    best_turns = float("inf")
    for candidate in _candidate_lane_paths(start_route, goal_route, bodies, cfg, hanan_points=hanan_points):
        hits = _path_body_hit_count(candidate, bodies, cfg, ignore_refs=ignore_refs, blocked_cells=None)
        length = _path_length(candidate)
        turns = _path_turn_count(candidate)
        score = (hits, length, turns)
        if best_hits is None or score < (best_hits, best_length, best_turns):
            best_hits = hits
            best_length = length
            best_turns = float(turns)
            if hits == 0:
                break
    if best_hits is None:
        best_hits = 1_000_000
    return (
        int(best_hits),
        float(best_length),
        float(best_turns),
        str(root.get("ref") or ""),
        str(root.get("pin") or ""),
    )


def _best_lane_path(
    start: Point,
    goal: Point,
    bodies: dict[str, Body],
    cfg: dict[str, Any],
    existing_segments: list[tuple[str, Point, Point]],
    occupied: dict[GridPoint, str],
    hard_blocked_cells: set[GridPoint],
    shadow_blocked_cells: set[GridPoint],
    *,
    net: str,
    ignore_refs: set[str],
    hanan_points: list[Point] | None = None,
) -> tuple[list[Point], dict[str, Any] | None]:
    best_path: list[Point] = []
    best_score: float | None = None
    best_report: dict[str, Any] | None = None
    candidate_count = 0
    rejected_body_count = 0
    for candidate in _candidate_lane_paths(start, goal, bodies, cfg, hanan_points=hanan_points):
        candidate_count += 1
        score, report = _path_score(
            candidate,
            bodies=bodies,
            existing_segments=existing_segments,
            cfg=cfg,
            net=net,
            ignore_refs=ignore_refs,
            occupied=occupied,
            hard_blocked_cells=hard_blocked_cells,
            shadow_blocked_cells=shadow_blocked_cells,
        )
        if report["body_hits"]:
            rejected_body_count += 1
            continue
        if best_score is None or score < best_score:
            best_score = score
            best_path = candidate
            best_report = report
    if best_report is not None:
        best_report = dict(best_report)
        best_report["candidate_count"] = candidate_count
        best_report["rejected_body_candidate_count"] = rejected_body_count
        best_report["score"] = round(float(best_score or 0.0), 3)
    return best_path, best_report


def _segment_records(net: str, path: list[Point]) -> list[tuple[str, Point, Point]]:
    return [(net, left, right) for left, right in zip(path, path[1:]) if left != right]


def _orthogonal_escape_path(start: Point, end: Point) -> list[Point]:
    start = _round_point(start)
    end = _round_point(end)
    if start == end:
        return [start]
    if start[0] == end[0] or start[1] == end[1]:
        return [start, end]
    return [start, (end[0], start[1]), end]


def _join_paths(*paths: list[Point]) -> list[Point]:
    out: list[Point] = []
    for path in paths:
        for point in path:
            rounded = _round_point(point)
            if out and out[-1] == rounded:
                continue
            out.append(rounded)
    return out


def _manhattan(left: Point, right: Point) -> float:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def _local_label_net(net: str, endpoints: list[dict[str, Any]], routing_mode: str) -> bool:
    if routing_mode == "wire":
        return False
    if routing_mode == "terminal":
        return True
    upper = net.upper()
    return upper in POWER_NETS or upper in GROUND_NETS or len(endpoints) >= 7


def _endpoint_span(endpoints: list[dict[str, Any]]) -> float:
    if not endpoints:
        return 0.0
    xs = [float(endpoint["point"][0]) for endpoint in endpoints]
    ys = [float(endpoint["point"][1]) for endpoint in endpoints]
    return (max(xs) - min(xs)) + (max(ys) - min(ys))


def _root_endpoint_index(endpoints: list[dict[str, Any]], net: str) -> int:
    if len(endpoints) <= 2:
        return 0
    xs = sorted(float(endpoint["point"][0]) for endpoint in endpoints)
    ys = sorted(float(endpoint["point"][1]) for endpoint in endpoints)
    median = (xs[len(xs) // 2], ys[len(ys) // 2])
    upper = net.upper()
    prefer_power_side = upper in POWER_NETS or upper in GROUND_NETS

    def score(index: int) -> tuple[float, float, str, str]:
        endpoint = endpoints[index]
        point = (float(endpoint["point"][0]), float(endpoint["point"][1]))
        side = str(endpoint.get("side") or "")
        side_penalty = 0.0
        if prefer_power_side:
            if upper in POWER_NETS and side != "top":
                side_penalty = 1_000.0
            elif upper in GROUND_NETS and side != "bottom":
                side_penalty = 1_000.0
        return (
            side_penalty + _manhattan(point, median),
            _endpoint_span([endpoint]),
            str(endpoint.get("ref") or ""),
            str(endpoint.get("pin") or ""),
        )

    return min(range(len(endpoints)), key=score)


def _rectilinear_mst_edges(endpoints: list[dict[str, Any]]) -> list[tuple[int, int, float]]:
    if len(endpoints) < 2:
        return []
    connected = {0}
    remaining = set(range(1, len(endpoints)))
    edges: list[tuple[int, int, float]] = []
    while remaining:
        best: tuple[float, int, int] | None = None
        for left in connected:
            left_point = (float(endpoints[left]["point"][0]), float(endpoints[left]["point"][1]))
            for right in remaining:
                right_point = (float(endpoints[right]["point"][0]), float(endpoints[right]["point"][1]))
                distance = _manhattan(left_point, right_point)
                candidate = (distance, left, right)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            break
        distance, left, right = best
        connected.add(right)
        remaining.remove(right)
        edges.append((left, right, round(distance, 3)))
    return edges


def _route_segments(routes: list[dict[str, Any]]) -> list[tuple[str, Point, Point]]:
    segments: list[tuple[str, Point, Point]] = []
    for route in routes:
        net = str(route["net"])
        for segment in route["segments"]:
            start = tuple(segment["start"])  # type: ignore[arg-type]
            end = tuple(segment["end"])  # type: ignore[arg-type]
            segments.append((net, (float(start[0]), float(start[1])), (float(end[0]), float(end[1]))))
    return segments


def _count_crossings(routes: list[dict[str, Any]]) -> int:
    segments = _route_segments(routes)
    horizontal: dict[float, list[tuple[str, float, float]]] = defaultdict(list)
    vertical: dict[float, list[tuple[str, float, float]]] = defaultdict(list)
    for net, start, end in segments:
        if start[1] == end[1]:
            low, high = sorted((start[0], end[0]))
            horizontal[start[1]].append((net, low, high))
        elif start[0] == end[0]:
            low, high = sorted((start[1], end[1]))
            vertical[start[0]].append((net, low, high))
    count = 0
    for y, h_segments in horizontal.items():
        for x, v_segments in vertical.items():
            for h_net, h_low, h_high in h_segments:
                if not _between(x, h_low, h_high):
                    continue
                for v_net, v_low, v_high in v_segments:
                    if h_net == v_net:
                        continue
                    if _between(y, v_low, v_high):
                        count += 1
    return count


def _crossing_density_metrics(routes: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    tile_size = max(float(cfg.get("density_tile_size", 25.4)), float(cfg.get("grid", 2.54)))
    max_soft = int(cfg.get("max_crossings_per_tile_soft", 6.0))
    segments = _route_segments(routes)
    horizontal: list[tuple[str, Point, Point]] = []
    vertical: list[tuple[str, Point, Point]] = []
    for item in segments:
        if item[1][1] == item[2][1]:
            horizontal.append(item)
        elif item[1][0] == item[2][0]:
            vertical.append(item)
    by_tile: Counter[tuple[int, int]] = Counter()
    near_pin_like_count = 0
    for h_net, h_start, h_end in horizontal:
        h_low, h_high = sorted((h_start[0], h_end[0]))
        for v_net, v_start, v_end in vertical:
            if h_net == v_net:
                continue
            x = v_start[0]
            y = h_start[1]
            v_low, v_high = sorted((v_start[1], v_end[1]))
            if not (_between(x, h_low, h_high) and _between(y, v_low, v_high)):
                continue
            by_tile[(int(x // tile_size), int(y // tile_size))] += 1
            if any(_manhattan((x, y), endpoint) <= float(cfg.get("pin_stub", 5.08)) for endpoint in (h_start, h_end, v_start, v_end)):
                near_pin_like_count += 1
    overflow = sum(max(0, count - max_soft) for count in by_tile.values())
    return {
        "crossing_density_tile_size": round(tile_size, 3),
        "crossing_density_tile_count": len(by_tile),
        "crossing_density_max_tile_crossings": max(by_tile.values(), default=0),
        "crossing_density_overflow": overflow,
        "near_endpoint_crossing_count": near_pin_like_count,
    }


def _between(value: float, a: float, b: float) -> bool:
    low, high = sorted((a, b))
    return low < value < high


def _segments_cross(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    a_horizontal = a1[1] == a2[1]
    b_horizontal = b1[1] == b2[1]
    if a_horizontal == b_horizontal:
        return False
    horizontal = (a1, a2) if a_horizontal else (b1, b2)
    vertical = (b1, b2) if a_horizontal else (a1, a2)
    x = vertical[0][0]
    y = horizontal[0][1]
    return _between(x, horizontal[0][0], horizontal[1][0]) and _between(y, vertical[0][1], vertical[1][1])


def plan_wire_routes(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = _wire_config(config, circuit)
    routing_mode = str(cfg["routing_mode"])

    bodies = _bodies(placement)
    endpoints_by_net = _endpoint_points(placement, circuit, cfg)
    dense_design = len(bodies) >= int(cfg.get("dense_design_component_limit", 90.0))
    if dense_design:
        cfg = dict(cfg)
        cfg["max_lane_candidates"] = min(
            float(cfg.get("max_lane_candidates", 160.0)),
            float(cfg.get("dense_max_lane_candidates", 48.0)),
        )
        cfg["max_astar_expansions"] = min(
            float(cfg.get("max_astar_expansions", 50_000.0)),
            float(cfg.get("dense_max_astar_expansions", 1500.0)),
        )
        cfg["strict_fallback_max_astar_expansions"] = min(
            float(cfg.get("strict_fallback_max_astar_expansions", cfg["max_astar_expansions"])),
            float(cfg.get("dense_max_astar_expansions", 1500.0)),
        )
        cfg["max_failed_endpoints_per_net"] = min(
            float(cfg.get("max_failed_endpoints_per_net", 1000.0)),
            float(cfg.get("dense_max_failed_endpoints_per_net", 3.0)),
        )
        if cfg.get("dense_force_grid_contact_scoring", 1.0) >= 1.0:
            cfg["exact_crossing_score_segment_limit"] = 0.0
    reserved_pin_occupied: dict[GridPoint, str] = {}
    for net, endpoints in endpoints_by_net.items():
        for endpoint in endpoints:
            if not endpoint.get("exact"):
                continue
            point = (float(endpoint["point"][0]), float(endpoint["point"][1]))
            cell = _to_grid(point, cfg["grid"])
            owner = reserved_pin_occupied.get(cell)
            if owner and owner != net:
                reserved_pin_occupied[cell] = f"{owner}|{net}"
            else:
                reserved_pin_occupied[cell] = net
    occupied: dict[GridPoint, str] = {}
    existing_segments: list[tuple[str, Point, Point]] = []
    blocked_cell_cache: dict[tuple[tuple[str, ...], float], set[GridPoint]] = {}
    routes: list[dict[str, Any]] = []
    nets_out: dict[str, Any] = {}
    warnings: list[str] = []
    max_wired_routes = max(1, int(cfg.get("max_wired_routes", 10_000.0)))
    max_failed_endpoints_per_net = max(1, int(cfg.get("max_failed_endpoints_per_net", 1000.0)))
    lane_route_count = 0
    astar_route_count = 0
    salvage_astar_route_count = 0
    crossing_risk_route_count = 0
    salvage_astar_attempt_count = 0

    def net_priority(item: tuple[str, list[dict[str, Any]]]) -> tuple[int, str]:
        net, endpoints = item
        upper = net.upper()
        if any(token in upper for token in ("CLK", "CLOCK", "CK", "CP")):
            return (0, net)
        if routing_mode != "wire" and (upper in POWER_NETS or upper in GROUND_NETS):
            return (2, net)
        if routing_mode == "wire":
            if upper in POWER_NETS or upper in GROUND_NETS:
                return (4, net)
            if any(token in upper for token in ("I2C", "SPI", "BCD", "SEG", "SHIFT", "CAN", "RS485", "UART")):
                return (1, net)
            if len(endpoints) >= 4 or _endpoint_span(endpoints) >= 120.0:
                return (2, net)
            return (3, net)
        return (1 if len(endpoints) <= 6 else 3, net)

    def blocked_cells_for(ignore_refs: set[str], clearance: float) -> set[GridPoint]:
        key = (tuple(sorted(ignore_refs)), round(float(clearance), 3))
        cached = blocked_cell_cache.get(key)
        if cached is None:
            cached = _blocked_cells(bodies, cfg, ignore_refs=ignore_refs, clearance=clearance)
            blocked_cell_cache[key] = cached
        return cached

    for net, endpoints in sorted(endpoints_by_net.items(), key=net_priority):
        if len(endpoints) < 2:
            if routing_mode == "wire":
                warning = f"strict_wire_single_endpoint: {net} has fewer than two endpoints."
                warnings.append(warning)
                nets_out[net] = {
                    "strategy": "unroutable_single_endpoint",
                    "endpoints": endpoints,
                    "routes": [],
                    "failure_warnings": [warning],
                }
            else:
                nets_out[net] = {"strategy": "single_endpoint_label", "endpoints": endpoints, "routes": []}
            continue
        if _local_label_net(net, endpoints, routing_mode):
            nets_out[net] = {"strategy": "local_labels", "endpoints": endpoints, "routes": []}
            continue
        if len(routes) >= max_wired_routes:
            warnings.append(f"wire_route_limit_deferred: {net} skipped after {max_wired_routes} routed connections.")
            strategy = "unroutable_after_route_limit" if routing_mode == "wire" else "deferred_after_route_limit"
            nets_out[net] = {"strategy": strategy, "endpoints": endpoints, "routes": [], "failure_warnings": ["wire_route_limit_deferred"]}
            continue

        endpoints = sorted(endpoints, key=lambda item: (item["point"][0], item["point"][1], item["ref"], item["pin"]))
        net_hanan_points = [
            (
                _snap(float(endpoint["point"][0]), cfg["grid"]),
                _snap(float(endpoint["point"][1]), cfg["grid"]),
            )
            for endpoint in endpoints
        ]
        mst_edges = _rectilinear_mst_edges(endpoints)
        mst_length = round(sum(edge[2] for edge in mst_edges), 3)
        root_index = _root_endpoint_index(endpoints, net)
        initial_root = endpoints[root_index]
        target_endpoints = [endpoint for index, endpoint in enumerate(endpoints) if index != root_index]
        target_endpoints.sort(
            key=lambda item: _manhattan(
                (float(initial_root["point"][0]), float(initial_root["point"][1])),
                (float(item["point"][0]), float(item["point"][1])),
            )
        )
        net_routes: list[dict[str, Any]] = []
        net_occupied: dict[GridPoint, str] = {}
        pending_net_segments: list[tuple[str, Point, Point]] = []
        net_lane_route_count = 0
        net_astar_route_count = 0
        net_salvage_astar_route_count = 0
        net_crossing_risk_route_count = 0
        net_failed = False
        net_failed_endpoint_count = 0
        net_failure_warnings: list[str] = []
        connected_endpoints = [initial_root]
        remaining_targets = list(target_endpoints)
        deferred_targets: list[dict[str, Any]] = []
        target_attempts: dict[tuple[str, str], int] = {}
        target_index = 0
        max_endpoint_retry_attempts = max(1, int(cfg.get("max_endpoint_retry_attempts", 4.0)))

        def target_tree_distance(target_item: dict[str, Any]) -> float:
            target_point = (float(target_item["point"][0]), float(target_item["point"][1]))
            return min(
                _manhattan((float(item["point"][0]), float(item["point"][1])), target_point)
                for item in connected_endpoints
            )

        while remaining_targets:
            target = min(
                remaining_targets,
                key=lambda item: (
                    target_tree_distance(item),
                    float(item["point"][0]),
                    float(item["point"][1]),
                    str(item.get("ref") or ""),
                    str(item.get("pin") or ""),
                ),
            )
            remaining_targets.remove(target)
            target_index += 1
            if len(routes) + len(net_routes) >= max_wired_routes:
                warnings.append(f"wire_route_limit_deferred: remaining endpoints of {net} skipped after {max_wired_routes} routed connections.")
                net_failed = True
                net_failure_warnings.append("wire_route_limit_deferred")
                break
            target_side = str(target.get("side") or "")
            same_side_roots = [item for item in connected_endpoints if str(item.get("side") or "") == target_side]
            root_pool = same_side_roots or connected_endpoints
            root_pool = sorted(
                root_pool,
                key=lambda item: _manhattan(
                    (float(item["point"][0]), float(item["point"][1])),
                    (float(target["point"][0]), float(target["point"][1])),
                ),
            )
            root_candidates = root_pool[: max(1, int(cfg.get("max_root_candidates_per_endpoint", 10.0)))]
            root = min(
                root_candidates,
                key=lambda item: _root_candidate_routeability_score(item, target, bodies, cfg, net=net, hanan_points=net_hanan_points),
            )
            start = (float(root["point"][0]), float(root["point"][1]))
            goal = (float(target["point"][0]), float(target["point"][1]))
            start_route = _portal_point(start, str(root.get("side") or "right"), cfg)
            goal_route = _portal_point(goal, str(target.get("side") or "right"), cfg)
            ignore_refs = set()
            if not root.get("exact"):
                ignore_refs.add(str(root["ref"]))
            if not target.get("exact"):
                ignore_refs.add(str(target["ref"]))
            routed_occupied = dict(reserved_pin_occupied)
            routed_occupied.update(occupied)
            routed_occupied.update(net_occupied)
            portals = []
            if root.get("exact"):
                portals.append((str(root["ref"]), start, str(root.get("side") or "right")))
            if target.get("exact"):
                portals.append((str(target["ref"]), goal, str(target.get("side") or "right")))
            route_warnings: list[str] = []
            route_candidates: list[tuple[str, list[Point], dict[str, Any], list[str]]] = []
            scoring_segments = existing_segments + pending_net_segments
            hard_blocked_cells = blocked_cells_for(ignore_refs, float(cfg["clearance"]))
            shadow_blocked_cells = blocked_cells_for(ignore_refs, float(cfg.get("component_shadow_clearance", cfg["clearance"])))

            if cfg.get("lane_router", 1.0) >= 1.0:
                lane_path, lane_report = _best_lane_path(
                    start_route,
                    goal_route,
                    bodies,
                    cfg,
                    scoring_segments,
                    routed_occupied,
                    hard_blocked_cells,
                    shadow_blocked_cells,
                    net=net,
                    ignore_refs=ignore_refs,
                    hanan_points=net_hanan_points,
                )
                if lane_path and lane_report:
                    route_candidates.append(("lane_candidate", lane_path, lane_report, []))

            clean_lane_available = any(
                algorithm == "lane_candidate"
                and int(report.get("forbidden_contacts", 0)) == 0
                and int(report.get("different_net_crossings", 0)) == 0
                for algorithm, _path, report, _warnings in route_candidates
            )
            lane_candidate_available = any(algorithm == "lane_candidate" for algorithm, _path, _report, _warnings in route_candidates)
            dense_skip_astar = (
                dense_design
                and lane_candidate_available
                and cfg.get("dense_skip_astar_when_lane_candidate", 1.0) >= 1.0
            )
            if (
                not dense_skip_astar
                and (not clean_lane_available or cfg.get("lane_zero_crossing_fast_accept", 1.0) < 1.0)
            ):
                astar_path, astar_warnings = _astar(
                    start_route,
                    goal_route,
                    bodies,
                    cfg,
                    routed_occupied,
                    net=net,
                    ignore_refs=ignore_refs,
                    portals=portals,
                )
                route_warnings.extend(astar_warnings)
                if astar_path:
                    astar_score, astar_report = _path_score(
                        astar_path,
                        bodies=bodies,
                        existing_segments=scoring_segments,
                        cfg=cfg,
                        net=net,
                        ignore_refs=ignore_refs,
                        occupied=routed_occupied,
                        hard_blocked_cells=hard_blocked_cells,
                        shadow_blocked_cells=shadow_blocked_cells,
                    )
                    astar_report["score"] = round(astar_score, 3)
                    route_candidates.append(("grid_astar", astar_path, astar_report, astar_warnings))

            best_preliminary_forbidden = min(
                (int(candidate[2].get("forbidden_contacts", 0)) for candidate in route_candidates),
                default=1_000_000,
            )
            best_preliminary_crossings = min(
                (int(candidate[2].get("different_net_crossings", 0)) for candidate in route_candidates),
                default=1_000_000,
            )
            if routing_mode == "wire" and (
                best_preliminary_forbidden > 0
                or (best_preliminary_crossings > 0 and cfg.get("crossing_risk_astar", 0.0) >= 1.0)
            ):
                fallback_cfg = dict(cfg)
                if best_preliminary_forbidden > 0:
                    fallback_cfg["block_existing_wires"] = 1.0
                    fallback_cfg["near_wire_penalty"] = max(float(cfg.get("near_wire_penalty", 1.25)), 50.0)
                else:
                    fallback_cfg["block_existing_wires"] = 0.0
                    fallback_cfg["near_wire_penalty"] = max(float(cfg.get("near_wire_penalty", 1.25)), 10.0)
                fallback_cfg["max_astar_expansions"] = float(
                    cfg.get("strict_fallback_max_astar_expansions", cfg.get("max_astar_expansions", 50_000.0))
                )
                fallback_path, fallback_warnings = _astar(
                    start_route,
                    goal_route,
                    bodies,
                    fallback_cfg,
                    routed_occupied,
                    net=net,
                    ignore_refs=ignore_refs,
                    portals=portals,
                )
                if fallback_path:
                    fallback_score, fallback_report = _path_score(
                        fallback_path,
                        bodies=bodies,
                        existing_segments=scoring_segments,
                        cfg=cfg,
                        net=net,
                        ignore_refs=ignore_refs,
                        occupied=routed_occupied,
                        hard_blocked_cells=hard_blocked_cells,
                        shadow_blocked_cells=shadow_blocked_cells,
                    )
                    fallback_report["score"] = round(fallback_score, 3)
                    route_candidates.append(
                        (
                            "crossing_risk_astar",
                            fallback_path,
                            fallback_report,
                            [
                                (
                                    "strict_forbidden_contact_fallback: existing different-net wire cells were treated as hard blocks."
                                    if best_preliminary_forbidden > 0
                                    else "strict_crossing_risk_fallback: existing wires were treated as high-cost lanes instead of hard blocks."
                                ),
                                *fallback_warnings,
                            ],
                        )
                    )
                elif fallback_warnings:
                    route_warnings.extend(fallback_warnings)
            route_candidates = [candidate for candidate in route_candidates if not candidate[2].get("body_hits")]
            route_candidates.sort(
                key=lambda item: (
                    int(item[2].get("forbidden_contacts", 0)),
                    float(item[2].get("score", 0.0)),
                    int(item[2].get("turns", 0)),
                    int(item[2].get("different_net_crossings", 0)),
                    str(item[0]),
                )
            )
            selected_algorithm = ""
            selected_report: dict[str, Any] = {}
            raw_path: list[Point] = []
            if route_candidates:
                selected_algorithm, raw_path, selected_report, selected_warnings = route_candidates[0]
                route_warnings.extend(selected_warnings)
                if selected_report.get("forbidden_contacts"):
                    route_warnings.append(
                        f"minimum_forbidden_contact_route: {net} accepted {selected_report['forbidden_contacts']} forbidden wire contact risk(s)."
                    )
                if selected_report.get("different_net_crossings"):
                    route_warnings.append(
                        f"minimum_crossing_route: {net} accepted {selected_report['different_net_crossings']} different-net crossing/touch risks."
                    )
            if (
                not raw_path
                and routing_mode == "wire"
                and salvage_astar_attempt_count < max(0, int(cfg.get("max_salvage_astar_attempts", 0.0)))
                and float(cfg.get("salvage_astar_expansions", 0.0)) > float(cfg.get("max_astar_expansions", 0.0))
            ):
                salvage_astar_attempt_count += 1
                salvage_cfg = dict(cfg)
                salvage_cfg["max_astar_expansions"] = float(cfg.get("salvage_astar_expansions", cfg["max_astar_expansions"]))
                salvage_cfg["block_existing_wires"] = 0.0
                salvage_path, salvage_warnings = _astar(
                    start_route,
                    goal_route,
                    bodies,
                    salvage_cfg,
                    routed_occupied,
                    net=net,
                    ignore_refs=ignore_refs,
                    portals=portals,
                )
                if salvage_path:
                    salvage_score, salvage_report = _path_score(
                        salvage_path,
                        bodies=bodies,
                        existing_segments=scoring_segments,
                        cfg=cfg,
                        net=net,
                        ignore_refs=ignore_refs,
                        occupied=routed_occupied,
                        hard_blocked_cells=hard_blocked_cells,
                        shadow_blocked_cells=shadow_blocked_cells,
                    )
                    salvage_report["score"] = round(salvage_score, 3)
                    if salvage_report.get("body_hits"):
                        route_warnings.extend(
                            [
                                f"salvage_astar_rejected_body_hit: {net} still touched component bodies.",
                                *salvage_warnings,
                            ]
                        )
                    else:
                        selected_algorithm = "salvage_grid_astar"
                        raw_path = salvage_path
                        selected_report = salvage_report
                        route_warnings.append(
                            f"salvage_astar_routed: {net} used {int(salvage_cfg['max_astar_expansions'])} expansion retry after bounded router failure."
                        )
                        route_warnings.extend(salvage_warnings)
                elif salvage_warnings:
                    route_warnings.extend(salvage_warnings)
            warnings.extend(route_warnings)
            if not raw_path:
                target_key = (str(target.get("ref") or ""), str(target.get("pin") or ""))
                target_attempts[target_key] = target_attempts.get(target_key, 0) + 1
                if target_attempts[target_key] < max_endpoint_retry_attempts and (remaining_targets or deferred_targets):
                    deferred_targets.append(target)
                    if not remaining_targets:
                        remaining_targets = deferred_targets
                        deferred_targets = []
                    continue
                net_failed = True
                net_failed_endpoint_count += 1
                endpoint_name = f"{target.get('ref')}.{target.get('pin')}"
                net_failure_warnings.extend(route_warnings or [f"unroutable_endpoint: {net} {endpoint_name}"])
                if net_failed_endpoint_count >= max_failed_endpoints_per_net:
                    remaining_endpoint_count = max(0, len(remaining_targets) + len(deferred_targets))
                    net_failed_endpoint_count += remaining_endpoint_count
                    net_failure_warnings.append(
                        f"endpoint_failure_budget_reached: stopped retrying {net} with {remaining_endpoint_count} endpoint(s) left unattempted."
                    )
                    break
                continue
            full_raw_path = _join_paths(
                _orthogonal_escape_path(start, start_route),
                raw_path,
                _orthogonal_escape_path(goal_route, goal),
            )
            path = _compress_path(full_raw_path)
            for point in full_raw_path:
                net_occupied[_to_grid(point, cfg["grid"])] = net
            route_segment_records = _segment_records(net, full_raw_path)
            pending_net_segments.extend(route_segment_records)
            if selected_algorithm == "lane_candidate":
                net_lane_route_count += 1
            elif selected_algorithm == "crossing_risk_astar":
                net_astar_route_count += 1
            elif selected_algorithm == "salvage_grid_astar":
                net_astar_route_count += 1
                net_salvage_astar_route_count += 1
            else:
                net_astar_route_count += 1
            if selected_report.get("different_net_crossings"):
                net_crossing_risk_route_count += 1
            route = {
                "net": net,
                "router": selected_algorithm or "unknown",
                "route_quality": selected_report,
                "from": {
                    "ref": root["ref"],
                    "pin": root["pin"],
                    "point": root["point"],
                    "exact": bool(root.get("exact")),
                    "source": root.get("source"),
                },
                "to": {
                    "ref": target["ref"],
                    "pin": target["pin"],
                    "point": target["point"],
                    "exact": bool(target.get("exact")),
                    "source": target.get("source"),
                },
                "path": [[point[0], point[1]] for point in path],
                "segments": _segments(path),
            }
            net_routes.append(route)
            connected_endpoints.append(target)
            if not remaining_targets and deferred_targets:
                remaining_targets = deferred_targets
                deferred_targets = []
        if net_failed:
            if routing_mode == "wire":
                warnings.append(f"strict_wire_unroutable: {net} could not be routed without labels.")
                if net_routes:
                    occupied.update(net_occupied)
                    existing_segments.extend(pending_net_segments)
                    routes.extend(net_routes)
                    lane_route_count += net_lane_route_count
                    astar_route_count += net_astar_route_count
                    salvage_astar_route_count += net_salvage_astar_route_count
                    crossing_risk_route_count += net_crossing_risk_route_count
                    nets_out[net] = {
                        "strategy": "partial_wire",
                        "endpoints": endpoints,
                        "routes": net_routes,
                        "mst": {"edges": mst_edges, "length": mst_length},
                        "unrouted_endpoint_count": net_failed_endpoint_count,
                        "failure_warnings": net_failure_warnings[:20],
                    }
                    continue
                nets_out[net] = {
                    "strategy": "unroutable",
                    "endpoints": endpoints,
                    "routes": [],
                    "partial_routes": net_routes,
                    "mst": {"edges": mst_edges, "length": mst_length},
                    "failure_warnings": net_failure_warnings[:20],
                }
            else:
                warnings.append(f"wire_net_label_fallback: {net} converted to local labels after router failure.")
                nets_out[net] = {
                    "strategy": "local_labels_after_router_failure",
                    "endpoints": endpoints,
                    "routes": [],
                    "failure_warnings": net_failure_warnings[:20],
                }
            continue
        occupied.update(net_occupied)
        existing_segments.extend(pending_net_segments)
        routes.extend(net_routes)
        lane_route_count += net_lane_route_count
        astar_route_count += net_astar_route_count
        salvage_astar_route_count += net_salvage_astar_route_count
        crossing_risk_route_count += net_crossing_risk_route_count
        nets_out[net] = {"strategy": "wire", "endpoints": endpoints, "routes": net_routes, "mst": {"edges": mst_edges, "length": mst_length}}

    crossing_count = _count_crossings(routes)
    crossing_density = _crossing_density_metrics(routes, cfg)
    if crossing_count:
        warnings.append(f"different_net_crossings_detected: {crossing_count}")
    if crossing_density.get("crossing_density_overflow"):
        warnings.append(f"crossing_density_overflow: {crossing_density['crossing_density_overflow']}")
    mst_total_length = round(
        sum(
            float(item.get("mst", {}).get("length", 0.0))
            for item in nets_out.values()
            if isinstance(item, dict) and isinstance(item.get("mst"), dict)
        ),
        3,
    )

    width, height = _sheet_bounds(bodies, cfg)
    return {
        "schema": "progen-kicad-wire-plan/v0.1",
        "stage": "wire_planner",
        "routing_mode": routing_mode,
        "input_contract": {
            "placement": "components plus obstacles JSON; no EDA file required",
            "connections": "CircuitIR components[].pins and/or nets endpoint lists",
        },
        "algorithm": {
            "router": "lane_candidates_then_grid_astar",
            "routing_engine": "hanan_lane_candidates_rectilinear_mst_then_grid_astar",
            "hanan_grid_lanes": True,
            "rectilinear_mst_tree": True,
            "astar_manhattan_fallback": True,
            "segment_indexed_crossing_metrics": True,
            "dense_design_mode": dense_design,
            "routing_order": "clock/control, bus, local/ordinary, display, power, ground; terminal/combination mode may label selected nets",
            "multi_terminal_policy": "rectilinear MST / nearest connected tree; each branch uses net-wide Hanan lanes plus A* fallback",
            "component_avoidance": "inflated_obstacle_grid",
            "wire_collision_policy": "wire-wire crossings are allowed; existing wire grid cells are congestion hints, not hard obstacles",
            "pin_collision_policy": "exact pin cells are reserved so routes do not pass through other nets' pins",
            "failure_policy": "wire mode records unroutable nets as failures; terminal/combination mode may convert selected failures to local-label terminal plans",
            "pin_point_policy": "uses placement.pin_points when supplied; otherwise estimates endpoint stubs from component body edges",
        },
        "sheet": {"width": width, "height": height, "grid": cfg["grid"], "clearance": cfg["clearance"]},
        "nets": nets_out,
        "routes": routes,
        "metrics": {
            "net_count": len(endpoints_by_net),
            "wired_route_count": len(routes),
            "lane_route_count": lane_route_count,
            "astar_route_count": astar_route_count,
            "salvage_astar_route_count": salvage_astar_route_count,
            "salvage_astar_attempt_count": salvage_astar_attempt_count,
            "crossing_risk_route_count": crossing_risk_route_count,
            "dense_design_mode": dense_design,
            "segment_count": sum(len(route["segments"]) for route in routes),
            "different_net_crossing_count": crossing_count,
            "mst_total_length": mst_total_length,
            **crossing_density,
            "label_strategy_count": sum(1 for item in nets_out.values() if isinstance(item, dict) and item.get("strategy") in LABEL_STRATEGIES),
            "partial_wire_net_count": sum(
                1 for item in nets_out.values() if isinstance(item, dict) and item.get("strategy") == "partial_wire"
            ),
            "unroutable_net_count": sum(
                1 for item in nets_out.values() if isinstance(item, dict) and str(item.get("strategy", "")).startswith("unroutable")
            ),
        },
        "warnings": warnings,
    }


def _placement_component_count(placement: dict[str, Any], circuit: dict[str, Any]) -> int:
    components = placement.get("components")
    if isinstance(components, dict):
        return len(components)
    raw = circuit.get("components")
    return len(raw) if isinstance(raw, list) else 0


def _arrangement_base_config(config: dict[str, float] | None) -> dict[str, float]:
    cfg = dict(DEFAULT_ARRANGEMENT_CONFIG)
    if config:
        cfg.update({key: float(value) for key, value in config.items()})
    return cfg


def _arrangement_variant_specs(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    arrangement_config: dict[str, float] | None,
    wire_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    base = _arrangement_base_config(arrangement_config)
    component_count = _placement_component_count(placement, circuit)
    nets = extract_connection_nets(circuit)
    max_fanout = max((len(endpoints) for endpoints in nets.values()), default=0)
    dense = component_count >= int(wire_cfg.get("dense_design_component_limit", 90.0)) or max_fanout >= 8
    profiles: list[tuple[str, dict[str, float]]] = [
        ("base", {}),
        ("wide_columns", {"column_gap": 1.45, "row_gap": 1.0, "component_clearance": 1.15}),
        ("tall_rows", {"column_gap": 1.0, "row_gap": 1.65, "component_clearance": 1.25}),
        ("loose_grid", {"column_gap": 1.35, "row_gap": 1.45, "component_clearance": 1.6}),
        ("compact_flow", {"column_gap": 1.15, "row_gap": 1.25, "component_clearance": 1.2}),
    ]
    if dense:
        profiles.extend(
            [
                ("dense_escape_channels", {"column_gap": 1.75, "row_gap": 2.0, "component_clearance": 2.0}),
                ("bus_corridors", {"column_gap": 1.35, "row_gap": 2.35, "component_clearance": 1.8}),
                ("wide_dense_blocks", {"column_gap": 2.1, "row_gap": 1.55, "component_clearance": 1.9}),
            ]
        )

    limit = max(1, int(wire_cfg.get("max_arrangement_variants", 8.0)))
    specs: list[dict[str, Any]] = []
    seen: set[tuple[float, float, float, float]] = set()
    for name, multipliers in profiles:
        cfg = dict(base)
        for key in ("column_gap", "row_gap", "component_clearance", "margin"):
            if key in cfg and key in multipliers:
                cfg[key] = round(float(cfg[key]) * float(multipliers[key]), 3)
        key = (
            round(float(cfg.get("column_gap", 0.0)), 3),
            round(float(cfg.get("row_gap", 0.0)), 3),
            round(float(cfg.get("component_clearance", 0.0)), 3),
            round(float(cfg.get("margin", 0.0)), 3),
        )
        if key in seen:
            continue
        seen.add(key)
        specs.append({"name": name, "arrangement_config": cfg})
        if len(specs) >= limit:
            break
    return specs


def _wire_plan_routeability_score(wire_plan: dict[str, Any]) -> dict[str, Any]:
    metrics = wire_plan.get("metrics", {}) if isinstance(wire_plan.get("metrics"), dict) else {}
    nets = wire_plan.get("nets", {}) if isinstance(wire_plan.get("nets"), dict) else {}
    complete_wire_nets = sum(1 for item in nets.values() if isinstance(item, dict) and item.get("strategy") == "wire")
    route_quality = [route.get("route_quality", {}) for route in wire_plan.get("routes", []) if isinstance(route, dict)]
    body_hits = sum(int(item.get("body_hits", 0)) for item in route_quality if isinstance(item, dict))
    forbidden_contacts = sum(int(item.get("forbidden_contacts", 0)) for item in route_quality if isinstance(item, dict))
    component_shadows = sum(int(item.get("component_shadow_count", 0)) for item in route_quality if isinstance(item, dict))
    route_length = sum(float(item.get("length", 0.0)) for item in route_quality if isinstance(item, dict))
    turns = sum(int(item.get("turns", 0)) for item in route_quality if isinstance(item, dict))
    unroutable = int(metrics.get("unroutable_net_count", 0))
    partial = int(metrics.get("partial_wire_net_count", 0))
    labels = int(metrics.get("label_strategy_count", 0))
    crossing_metric = int(metrics.get("different_net_crossing_count", 0))
    score = (
        unroutable * 1_000_000_000
        + partial * 100_000_000
        + labels * 10_000_000
        + body_hits * 1_000_000
        + forbidden_contacts * 500_000
        + component_shadows * 10_000
        - complete_wire_nets * 1_000
        + turns * 10
        + route_length
        + crossing_metric * 0.001
    )
    return {
        "score": round(score, 3),
        "complete_wire_net_count": complete_wire_nets,
        "unroutable_net_count": unroutable,
        "partial_wire_net_count": partial,
        "label_strategy_count": labels,
        "route_body_hit_count": body_hits,
        "route_forbidden_contact_count": forbidden_contacts,
        "component_shadow_count": component_shadows,
        "route_turn_count": turns,
        "route_length": round(route_length, 3),
        "different_net_crossing_count": crossing_metric,
    }


def _component_body_groups(bodies: dict[str, Body]) -> dict[str, list[Body]]:
    groups: dict[str, list[Body]] = defaultdict(list)
    for body in bodies.values():
        groups[body.component_ref or body.ref].append(body)
    return groups


def _translated_body(body: Body, dx: float, dy: float) -> Body:
    return Body(
        body.ref,
        round(body.left + dx, 3),
        round(body.top + dy, 3),
        round(body.right + dx, 3),
        round(body.bottom + dy, 3),
        body.component_ref,
    )


def _bodies_overlap(left: Body, right: Body, clearance: float = 0.0) -> bool:
    return (
        left.left - clearance < right.right + clearance
        and left.right + clearance > right.left - clearance
        and left.top - clearance < right.bottom + clearance
        and left.bottom + clearance > right.top - clearance
    )


def _component_move_overlaps(
    *,
    ref: str,
    moved_bodies: list[Body],
    bodies: dict[str, Body],
    clearance: float,
) -> bool:
    for moved in moved_bodies:
        for other in bodies.values():
            other_ref = other.component_ref or other.ref
            if other_ref == ref:
                continue
            if _bodies_overlap(moved, other, clearance):
                return True
    return False


def _partial_route_move_candidates(
    *,
    current_at: Point,
    pin_offset: Point,
    anchor: Point,
    grid: float,
    search_steps: int,
) -> list[Point]:
    base = (_snap(anchor[0] - pin_offset[0], grid), _snap(anchor[1] - pin_offset[1], grid))
    candidates: list[Point] = [base]
    seen = {base}
    directions = [
        (1, 0),
        (-1, 0),
        (0, 1),
        (0, -1),
        (1, 1),
        (1, -1),
        (-1, 1),
        (-1, -1),
        (2, 0),
        (-2, 0),
        (0, 2),
        (0, -2),
    ]
    for step in range(1, search_steps + 1):
        for dx, dy in directions:
            point = (_snap(base[0] + dx * step * grid, grid), _snap(base[1] + dy * step * grid, grid))
            if point in seen:
                continue
            seen.add(point)
            candidates.append(point)
    candidates.sort(key=lambda point: (_manhattan(point, base), _manhattan(point, current_at), point[1], point[0]))
    return candidates


def plan_partial_route_component_moves(
    placement: dict[str, Any],
    wire_plan: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build coordinate edits that pull failed partial-route endpoints toward their wired neighbor.

    This stays pure JSON: it reads the current routing placement and wire-plan
    failure report, then emits coordinate edits for the beautifier. It does not
    inspect or mutate an EDA file.
    """

    cfg = _wire_config(config)
    grid = float(cfg["grid"])
    bodies = _bodies(placement)
    body_groups = _component_body_groups(bodies)
    components = placement.get("components", {})
    if not isinstance(components, dict):
        components = {}
    max_moves = max(0, int(cfg.get("max_partial_route_component_moves", 8.0)))
    search_steps = max(2, int(cfg.get("partial_route_move_search_steps", 14.0)))
    move_clearance = float(cfg.get("partial_route_move_body_clearance", 0.0))
    min_pin_gap = float(cfg.get("partial_route_move_min_pin_gap", grid * 4))

    coordinate_edits: list[dict[str, Any]] = []
    move_records: list[dict[str, Any]] = []
    moved_refs: set[str] = set()
    working = json.loads(json.dumps(placement))

    nets = wire_plan.get("nets", {})
    if not isinstance(nets, dict):
        nets = {}

    for net, net_data in sorted(nets.items()):
        if len(coordinate_edits) >= max_moves:
            break
        if not isinstance(net_data, dict) or net_data.get("strategy") != "partial_wire":
            continue
        endpoints = [item for item in net_data.get("endpoints", []) if isinstance(item, dict)]
        routes = [item for item in net_data.get("routes", []) if isinstance(item, dict)]
        routed_keys: set[tuple[str, str]] = set()
        for route in routes:
            for key in ("from", "to"):
                endpoint = route.get(key)
                if isinstance(endpoint, dict):
                    routed_keys.add((str(endpoint.get("ref") or ""), str(endpoint.get("pin") or "")))
        connected = [
            endpoint
            for endpoint in endpoints
            if (str(endpoint.get("ref") or ""), str(endpoint.get("pin") or "")) in routed_keys
        ]
        if not connected:
            connected = endpoints
        for failed in endpoints:
            if len(coordinate_edits) >= max_moves:
                break
            ref = str(failed.get("ref") or "")
            pin = str(failed.get("pin") or "")
            if not ref or ref in moved_refs or (ref, pin) in routed_keys:
                continue
            component = components.get(ref)
            if not isinstance(component, dict):
                continue
            at_raw = component.get("at", [0.0, 0.0])
            if not isinstance(at_raw, (list, tuple)) or len(at_raw) < 2:
                continue
            current_at = (float(at_raw[0]), float(at_raw[1]))
            failed_point_raw = failed.get("point", current_at)
            if not isinstance(failed_point_raw, (list, tuple)) or len(failed_point_raw) < 2:
                continue
            failed_point = (float(failed_point_raw[0]), float(failed_point_raw[1]))
            anchors = []
            for endpoint in connected:
                point_raw = endpoint.get("point")
                if isinstance(point_raw, (list, tuple)) and len(point_raw) >= 2:
                    anchors.append((float(point_raw[0]), float(point_raw[1]), endpoint))
            if not anchors:
                continue
            anchor_x, anchor_y, anchor_endpoint = min(
                anchors,
                key=lambda item: (_manhattan(failed_point, (item[0], item[1])), str(item[2].get("ref") or ""), str(item[2].get("pin") or "")),
            )
            anchor = (anchor_x, anchor_y)
            pin_offset = (failed_point[0] - current_at[0], failed_point[1] - current_at[1])
            ref_bodies = body_groups.get(ref)
            if not ref_bodies:
                continue

            best: tuple[float, Point, list[Body]] | None = None
            for candidate_at in _partial_route_move_candidates(
                current_at=current_at,
                pin_offset=pin_offset,
                anchor=anchor,
                grid=grid,
                search_steps=search_steps,
            ):
                dx = round(candidate_at[0] - current_at[0], 3)
                dy = round(candidate_at[1] - current_at[1], 3)
                moved_bodies = [_translated_body(body, dx, dy) for body in ref_bodies]
                if _component_move_overlaps(ref=ref, moved_bodies=moved_bodies, bodies=bodies, clearance=move_clearance):
                    continue
                moved_pin = (round(failed_point[0] + dx, 3), round(failed_point[1] + dy, 3))
                pin_gap = _manhattan(moved_pin, anchor)
                pin_gap_penalty = max(0.0, min_pin_gap - pin_gap) * 10_000.0
                score = pin_gap_penalty + pin_gap + _manhattan(candidate_at, current_at) * 0.02
                if best is None or score < best[0]:
                    best = (score, candidate_at, moved_bodies)
                    if pin_gap_penalty == 0.0 and pin_gap <= min_pin_gap + grid * 2:
                        break
            if best is None:
                move_records.append(
                    {
                        "net": str(net),
                        "ref": ref,
                        "pin": pin,
                        "status": "no_clear_candidate",
                        "anchor": [anchor[0], anchor[1]],
                    }
                )
                continue

            _score, to_at, moved_bodies = best
            edit = {
                "ref": ref,
                "from": [round(current_at[0], 3), round(current_at[1], 3)],
                "to": [round(to_at[0], 3), round(to_at[1], 3)],
                "delta": [round(to_at[0] - current_at[0], 3), round(to_at[1] - current_at[1], 3)],
                "reason": "partial_wire_endpoint_local_move",
                "net": str(net),
                "pin": pin,
                "anchor": {
                    "ref": str(anchor_endpoint.get("ref") or ""),
                    "pin": str(anchor_endpoint.get("pin") or ""),
                    "point": [anchor[0], anchor[1]],
                },
            }
            coordinate_edits.append(edit)
            move_records.append(
                {
                    "net": str(net),
                    "ref": ref,
                    "pin": pin,
                    "status": "moved",
                    "from": edit["from"],
                    "to": edit["to"],
                    "anchor": edit["anchor"],
                }
            )
            moved_refs.add(ref)
            bodies = {key: body for key, body in bodies.items() if (body.component_ref or body.ref) != ref}
            for moved_body in moved_bodies:
                bodies[moved_body.ref] = moved_body
            body_groups = _component_body_groups(bodies)
            working = apply_coordinate_edits(working, {"coordinate_edits": [edit]})
            components = working.get("components", {}) if isinstance(working.get("components"), dict) else components

    return {
        "schema": "progen-kicad-partial-route-component-motion/v0.1",
        "stage": "partial_route_component_motion_decider",
        "algorithm": {
            "primary": "move_failed_partial_endpoint_toward_nearest_wired_same_net_endpoint",
            "input_contract": "routing placement JSON plus wire_plan partial-wire net reports",
            "output_contract": "coordinate edits for beautifier.py",
        },
        "coordinate_edits": coordinate_edits,
        "move_count": len(coordinate_edits),
        "moves": move_records,
    }


def _variant_scoring_wire_config(wire_cfg: dict[str, Any]) -> dict[str, Any]:
    cfg = dict(wire_cfg)
    cfg["max_astar_expansions"] = min(
        float(cfg.get("max_astar_expansions", 50_000.0)),
        float(cfg.get("arrangement_variant_max_astar_expansions", 600.0)),
    )
    cfg["strict_fallback_max_astar_expansions"] = min(
        float(cfg.get("strict_fallback_max_astar_expansions", cfg["max_astar_expansions"])),
        float(cfg.get("arrangement_variant_max_astar_expansions", 600.0)),
    )
    cfg["dense_max_astar_expansions"] = min(
        float(cfg.get("dense_max_astar_expansions", 1500.0)),
        float(cfg.get("arrangement_variant_max_astar_expansions", 600.0)),
    )
    cfg["max_lane_candidates"] = min(
        float(cfg.get("max_lane_candidates", 160.0)),
        float(cfg.get("arrangement_variant_max_lane_candidates", 32.0)),
    )
    cfg["dense_max_lane_candidates"] = min(
        float(cfg.get("dense_max_lane_candidates", 80.0)),
        float(cfg.get("arrangement_variant_max_lane_candidates", 32.0)),
    )
    cfg["max_failed_endpoints_per_net"] = min(
        float(cfg.get("max_failed_endpoints_per_net", 1000.0)),
        float(cfg.get("arrangement_variant_max_failed_endpoints_per_net", 1.0)),
    )
    cfg["dense_max_failed_endpoints_per_net"] = min(
        float(cfg.get("dense_max_failed_endpoints_per_net", 2.0)),
        float(cfg.get("arrangement_variant_max_failed_endpoints_per_net", 1.0)),
    )
    cfg["max_root_candidates_per_endpoint"] = min(
        float(cfg.get("max_root_candidates_per_endpoint", 3.0)),
        float(cfg.get("arrangement_variant_max_root_candidates", 1.0)),
    )
    cfg["crossing_risk_astar"] = 0.0
    return cfg


def _body_overlap_count(bodies: dict[str, Body]) -> int:
    items = list(bodies.values())
    count = 0
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            left_ref = left.component_ref or left.ref
            right_ref = right.component_ref or right.ref
            if left_ref == right_ref:
                continue
            if left.right <= right.left or right.right <= left.left or left.bottom <= right.top or right.bottom <= left.top:
                continue
            count += 1
    return count


def _estimate_candidate_paths(start: Point, goal: Point, bodies: dict[str, Body], cfg: dict[str, Any]) -> list[list[Point]]:
    width, height = _sheet_bounds(bodies, cfg)
    margin = float(cfg["margin"])
    grid = float(cfg["grid"])
    x_mid = _snap((start[0] + goal[0]) / 2, grid)
    y_mid = _snap((start[1] + goal[1]) / 2, grid)
    left_lane = _snap(margin, grid)
    right_lane = _snap(max(margin, width - margin), grid)
    top_lane = _snap(margin, grid)
    bottom_lane = _snap(max(margin, height - margin), grid)
    candidates = [
        [start, (goal[0], start[1]), goal],
        [start, (start[0], goal[1]), goal],
        [start, (x_mid, start[1]), (x_mid, goal[1]), goal],
        [start, (start[0], y_mid), (goal[0], y_mid), goal],
        [start, (left_lane, start[1]), (left_lane, goal[1]), goal],
        [start, (right_lane, start[1]), (right_lane, goal[1]), goal],
        [start, (start[0], top_lane), (goal[0], top_lane), goal],
        [start, (start[0], bottom_lane), (goal[0], bottom_lane), goal],
    ]
    if start[0] == goal[0] or start[1] == goal[1]:
        candidates.insert(0, [start, goal])
    out: list[list[Point]] = []
    seen: set[tuple[Point, ...]] = set()
    for candidate in candidates:
        compressed = _compress_path(_dedupe_path(candidate))
        key = tuple(compressed)
        if len(compressed) < 2 or key in seen:
            continue
        seen.add(key)
        out.append(compressed)
    return out


def _estimate_variant_routeability(routing_placement: dict[str, Any], circuit: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    bodies = _bodies(routing_placement)
    endpoints_by_net = _endpoint_points(routing_placement, circuit, cfg)
    blocked_endpoint_count = 0
    routable_branch_count = 0
    estimated_body_hits = 0
    estimated_length = 0.0
    estimated_turns = 0

    for net, endpoints in endpoints_by_net.items():
        if len(endpoints) < 2:
            blocked_endpoint_count += 1
            continue
        endpoints = sorted(endpoints, key=lambda item: (item["point"][0], item["point"][1], item["ref"], item["pin"]))
        net_hanan_points = [
            (
                _snap(float(endpoint["point"][0]), cfg["grid"]),
                _snap(float(endpoint["point"][1]), cfg["grid"]),
            )
            for endpoint in endpoints
        ]
        root_index = _root_endpoint_index(endpoints, net)
        initial_root = endpoints[root_index]
        targets = [endpoint for index, endpoint in enumerate(endpoints) if index != root_index]
        targets.sort(
            key=lambda item: _manhattan(
                (float(initial_root["point"][0]), float(initial_root["point"][1])),
                (float(item["point"][0]), float(item["point"][1])),
            )
        )
        connected = [initial_root]
        for target in targets:
            target_side = str(target.get("side") or "")
            same_side_roots = [item for item in connected if str(item.get("side") or "") == target_side]
            root_pool = same_side_roots or connected
            root_pool = sorted(
                root_pool,
                key=lambda item: _manhattan(
                    (float(item["point"][0]), float(item["point"][1])),
                    (float(target["point"][0]), float(target["point"][1])),
                ),
            )
            root_candidates = root_pool[: max(1, int(cfg.get("max_root_candidates_per_endpoint", 10.0)))]
            root = min(
                root_candidates,
                key=lambda item: _root_candidate_routeability_score(item, target, bodies, cfg, net=net, hanan_points=net_hanan_points),
            )
            start = (float(root["point"][0]), float(root["point"][1]))
            goal = (float(target["point"][0]), float(target["point"][1]))
            start_route = _portal_point(start, str(root.get("side") or "right"), cfg)
            goal_route = _portal_point(goal, str(target.get("side") or "right"), cfg)
            ignore_refs: set[str] = set()
            if not root.get("exact"):
                ignore_refs.add(str(root["ref"]))
            if not target.get("exact"):
                ignore_refs.add(str(target["ref"]))
            best_path: list[Point] = []
            best_hits: int | None = None
            best_score: tuple[int, int, float] | None = None
            for candidate in _estimate_candidate_paths(start_route, goal_route, bodies, cfg):
                body_hits = _path_body_hit_count(candidate, bodies, cfg, ignore_refs=ignore_refs, blocked_cells=None)
                score = (body_hits, _path_turn_count(candidate), _path_length(candidate))
                if best_score is None or score < best_score:
                    best_score = score
                    best_hits = body_hits
                    best_path = candidate
                if body_hits == 0:
                    break
            if not best_path or best_hits:
                blocked_endpoint_count += 1
                estimated_body_hits += int(best_hits or 1)
                continue
            routable_branch_count += 1
            connected.append(target)
            estimated_length += _path_length(best_path)
            estimated_turns += _path_turn_count(best_path)

    partial_like_nets = sum(1 for endpoints in endpoints_by_net.values() if len(endpoints) >= 2) - routable_branch_count
    overlap_count = _body_overlap_count(bodies)
    score = (
        overlap_count * 10_000_000_000
        + blocked_endpoint_count * 1_000_000_000
        + estimated_body_hits * 1_000_000
        + estimated_turns * 10
        + estimated_length
    )
    return {
        "score": round(score, 3),
        "component_body_overlap_count": overlap_count,
        "estimated_blocked_endpoint_count": blocked_endpoint_count,
        "estimated_partial_pressure": max(0, partial_like_nets),
        "estimated_body_hit_count": estimated_body_hits,
        "estimated_routable_branch_count": routable_branch_count,
        "estimated_turn_count": estimated_turns,
        "estimated_route_length": round(estimated_length, 3),
    }


def _evaluate_arrangement_variant_task(args: tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
    placement, circuit, spec, wire_cfg = args
    started = time.perf_counter()
    try:
        coordinate_plan = decide_arrangement(placement, circuit, config=spec["arrangement_config"])
        routing_placement = apply_coordinate_edits(placement, coordinate_plan)
        score = _estimate_variant_routeability(routing_placement, circuit, wire_cfg)
        return {
            "ok": True,
            "name": spec["name"],
            "coordinate_plan": coordinate_plan,
            "routing_placement": routing_placement,
            "wire_plan": {"schema": "progen-kicad-wire-plan/v0.1", "metrics": {}},
            "score": score,
            "elapsed_seconds": round(time.perf_counter() - started, 3),
        }
    except Exception as exc:  # pragma: no cover - defensive report path
        return {
            "ok": False,
            "name": str(spec.get("name") or "unknown"),
            "coordinate_plan": {},
            "routing_placement": {},
            "wire_plan": {"schema": "progen-kicad-wire-plan/v0.1", "metrics": {}},
            "score": {"score": 1.0e99, "error": str(exc)},
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "error": str(exc),
        }


def _variant_workers(wire_cfg: dict[str, Any], variant_count: int, component_count: int) -> int:
    if variant_count <= 1:
        return 1
    if component_count < int(wire_cfg.get("arrangement_variant_parallel_min_components", 40.0)):
        return 1
    configured = int(wire_cfg.get("arrangement_variant_workers", 0.0))
    if configured > 0:
        return max(1, min(configured, variant_count))
    return max(1, min(variant_count, os.cpu_count() or 1, 4))


def select_routeable_arrangement(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    arrangement_config: dict[str, float] | None = None,
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    wire_cfg = _wire_config(wire_config, circuit)
    scoring_wire_cfg = _variant_scoring_wire_config(wire_cfg)
    specs = _arrangement_variant_specs(placement, circuit, arrangement_config=arrangement_config, wire_cfg=wire_cfg)
    if wire_cfg.get("arrangement_variant_search", 1.0) < 1.0:
        specs = specs[:1]
    component_count = _placement_component_count(placement, circuit)
    workers = _variant_workers(wire_cfg, len(specs), component_count)
    tasks = [(placement, circuit, spec, scoring_wire_cfg) for spec in specs]

    results: list[dict[str, Any]] = []
    parallel_error = ""
    if workers > 1:
        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                future_map = {executor.submit(_evaluate_arrangement_variant_task, task): task[2]["name"] for task in tasks}
                for future in as_completed(future_map):
                    results.append(future.result())
        except Exception as exc:  # pragma: no cover - environment-dependent fallback
            parallel_error = str(exc)
            results = []

    if not results:
        results = [_evaluate_arrangement_variant_task(task) for task in tasks]
        workers = 1

    results.sort(key=lambda item: (float(item.get("score", {}).get("score", 1.0e99)), str(item.get("name", ""))))
    selected = results[0]
    if wire_cfg.get("arrangement_final_wire_route", 1.0) >= 1.0:
        final_wire_plan = plan_wire_routes(selected["routing_placement"], circuit, config=wire_cfg)
    else:
        net_count = len(extract_connection_nets(circuit))
        final_wire_plan = {
            "schema": "progen-kicad-wire-plan/v0.1",
            "stage": "wire_planner",
            "routing_mode": str(wire_cfg["routing_mode"]),
            "input_contract": {
                "placement": "components plus obstacles JSON; no EDA file required",
                "connections": "CircuitIR components[].pins and/or nets endpoint lists",
            },
            "algorithm": {
                "router": "arrangement_route_skipped",
                "reason": "caller requested routeability-scored arrangement only; backend exact routing will run after symbol body resolution",
            },
            "sheet": {
                "width": wire_cfg["sheet_width"],
                "height": wire_cfg["sheet_height"],
                "grid": wire_cfg["grid"],
                "clearance": wire_cfg["clearance"],
            },
            "nets": {},
            "routes": [],
            "metrics": {
                "net_count": net_count,
                "wired_route_count": 0,
                "lane_route_count": 0,
                "astar_route_count": 0,
                "salvage_astar_route_count": 0,
                "salvage_astar_attempt_count": 0,
                "crossing_risk_route_count": 0,
                "dense_design_mode": _placement_component_count(selected["routing_placement"], circuit)
                >= int(wire_cfg.get("dense_design_component_limit", 90.0)),
                "segment_count": 0,
                "different_net_crossing_count": 0,
                "label_strategy_count": 0,
                "partial_wire_net_count": 0,
                "unroutable_net_count": 0,
            },
            "warnings": ["arrangement_final_wire_route_skipped"],
        }
    variants = [
        {
            "name": item.get("name"),
            "ok": bool(item.get("ok")),
            "score": item.get("score", {}),
            "elapsed_seconds": item.get("elapsed_seconds"),
            "coordinate_edit_count": len(item.get("coordinate_plan", {}).get("coordinate_edits", []))
            if isinstance(item.get("coordinate_plan"), dict)
            else 0,
            "error": item.get("error"),
        }
        for item in results
    ]
    report = {
        "schema": "progen-kicad-routeable-arrangement-selection/v0.1",
        "stage": "routeable_arrangement_selector",
        "strategy": "parallel_variant_routeability_score",
        "variant_count": len(results),
        "worker_count": workers,
        "parallel_error": parallel_error,
        "scoring_wire_config": {
            "max_astar_expansions": scoring_wire_cfg.get("max_astar_expansions"),
            "max_lane_candidates": scoring_wire_cfg.get("max_lane_candidates"),
            "max_failed_endpoints_per_net": scoring_wire_cfg.get("max_failed_endpoints_per_net"),
        },
        "selected_variant": selected.get("name"),
        "selected_score": selected.get("score", {}),
        "final_score": _wire_plan_routeability_score(final_wire_plan),
        "variants": variants,
    }
    return {
        "coordinate_plan": selected["coordinate_plan"],
        "routing_placement": selected["routing_placement"],
        "wire_plan": final_wire_plan,
        "arrangement_selection": report,
    }


def plan_wiring(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    arrangement_config: dict[str, float] | None = None,
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected = select_routeable_arrangement(placement, circuit, arrangement_config=arrangement_config, wire_config=wire_config)
    coordinate_plan = selected["coordinate_plan"]
    routing_placement = selected["routing_placement"]
    wire_plan = selected["wire_plan"]
    return {
        "schema": "progen-kicad-wire-planner-output/v0.1",
        "component_motion_policy": {
            "phase": "before_route_search",
            "coordinate_source": "routeability_scored_arrangement_variants",
            "applied_by": "beautifier",
            "purpose": "move components first so route planning starts from a wiring-aware placement",
        },
        "arrangement_selection": selected["arrangement_selection"],
        "coordinate_plan": coordinate_plan,
        "routing_placement": routing_placement,
        "wire_plan": wire_plan,
    }


def write_wire_planner_jsons(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    out_dir: str | Path,
    *,
    arrangement_config: dict[str, float] | None = None,
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    planned = plan_wiring(placement, circuit, arrangement_config=arrangement_config, wire_config=wire_config)
    coordinate_path = out_path / "wire_coordinate_plan.json"
    routing_placement_path = out_path / "wire_routing_placement.json"
    arrangement_selection_path = out_path / "wire_arrangement_selection.json"
    wire_path = out_path / "wire_plan.json"
    coordinate_path.write_text(json.dumps(planned["coordinate_plan"], indent=2), encoding="utf-8")
    routing_placement_path.write_text(json.dumps(planned["routing_placement"], indent=2), encoding="utf-8")
    arrangement_selection_path.write_text(json.dumps(planned["arrangement_selection"], indent=2), encoding="utf-8")
    wire_path.write_text(json.dumps(planned["wire_plan"], indent=2), encoding="utf-8")
    return {
        "coordinate_plan": coordinate_path,
        "routing_placement": routing_placement_path,
        "arrangement_selection": arrangement_selection_path,
        "wire_plan": wire_path,
    }
