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
from collections import defaultdict
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
    "max_lane_candidates": 160.0,
    "crossing_penalty": 0.0,
    "same_net_reuse_penalty": 0.05,
    "body_crossing_penalty": 100_000.0,
    "component_shadow_penalty": 80.0,
    "component_shadow_clearance": 12.7,
    "long_lane_threshold": 80.0,
    "long_lane_outer_penalty": 12.0,
    "exact_crossing_score_segment_limit": 80.0,
    "body_grid_score_component_limit": 80.0,
    "dense_design_component_limit": 90.0,
    "dense_max_lane_candidates": 80.0,
    "dense_max_astar_expansions": 1500.0,
    "max_failed_endpoints_per_net": 1000.0,
    "dense_max_failed_endpoints_per_net": 2.0,
    "dense_force_grid_contact_scoring": 1.0,
    "dense_skip_astar_when_lane_candidate": 1.0,
    "crossing_risk_astar": 0.0,
    "lane_zero_crossing_fast_accept": 1.0,
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
            if ref in bodies or not isinstance(component, dict):
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
    upper = net.upper()
    if upper in POWER_NETS:
        return "top"
    if upper in GROUND_NETS:
        return "bottom"
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


def _segment_touches_or_crosses(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    for point in (a1, a2):
        if _point_on_segment(point, b1, b2):
            return True
    for point in (b1, b2):
        if _point_on_segment(point, a1, a2):
            return True
    return _segments_cross(a1, a2, b1, b2)


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
) -> tuple[int, int]:
    if (
        cfg is not None
        and occupied is not None
        and len(existing_segments) > int(cfg.get("exact_crossing_score_segment_limit", 700.0))
    ):
        return _path_grid_contact_counts(path, occupied, net=net, grid=float(cfg["grid"]))

    different_net = 0
    same_net = 0
    for start, end in zip(path, path[1:]):
        for other_net, other_start, other_end in existing_segments:
            if not _segment_touches_or_crosses(start, end, other_start, other_end):
                continue
            if other_net == net:
                same_net += 1
            else:
                different_net += 1
    return different_net, same_net


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
                "same_net_contacts": 0,
                "length": round(length, 3),
                "turns": turns,
            },
        )
    body_shadows = _path_component_shadow_count(path, bodies, cfg, ignore_refs=ignore_refs, blocked_cells=shadow_blocked_cells)
    outer_channel_cost = _path_outer_channel_cost(path, bodies, cfg)
    crossings, same_net_contacts = _path_wire_contact_counts(path, existing_segments, net=net, cfg=cfg, occupied=occupied)
    length = _path_length(path)
    turns = _path_turn_count(path)
    score = (
        body_hits * float(cfg["body_crossing_penalty"])
        + body_shadows * float(cfg["component_shadow_penalty"])
        + outer_channel_cost * float(cfg["long_lane_outer_penalty"])
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
) -> list[list[Point]]:
    candidates: list[list[Point]] = []
    if start[0] == goal[0] or start[1] == goal[1]:
        candidates.append(_dedupe_path([start, goal]))
    candidates.append(_dedupe_path([start, (goal[0], start[1]), goal]))
    candidates.append(_dedupe_path([start, (start[0], goal[1]), goal]))

    y_lanes = _lane_values(axis="y", start=start, goal=goal, bodies=bodies, cfg=cfg)
    x_lanes = _lane_values(axis="x", start=start, goal=goal, bodies=bodies, cfg=cfg)
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
) -> tuple[list[Point], dict[str, Any] | None]:
    best_path: list[Point] = []
    best_score: float | None = None
    best_report: dict[str, Any] | None = None
    candidate_count = 0
    rejected_body_count = 0
    for candidate in _candidate_lane_paths(start, goal, bodies, cfg):
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


def _count_crossings(routes: list[dict[str, Any]]) -> int:
    segments: list[tuple[str, Point, Point]] = []
    for route in routes:
        net = str(route["net"])
        for segment in route["segments"]:
            start = tuple(segment["start"])  # type: ignore[arg-type]
            end = tuple(segment["end"])  # type: ignore[arg-type]
            segments.append((net, (float(start[0]), float(start[1])), (float(end[0]), float(end[1]))))
    count = 0
    for index, left in enumerate(segments):
        for right in segments[index + 1 :]:
            if left[0] == right[0]:
                continue
            if _segments_cross(left[1], left[2], right[1], right[2]):
                count += 1
    return count


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
    crossing_risk_route_count = 0

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
        net_routes: list[dict[str, Any]] = []
        net_occupied: dict[GridPoint, str] = {}
        pending_net_segments: list[tuple[str, Point, Point]] = []
        net_lane_route_count = 0
        net_astar_route_count = 0
        net_crossing_risk_route_count = 0
        net_failed = False
        net_failed_endpoint_count = 0
        net_failure_warnings: list[str] = []
        root = endpoints[0]
        connected_endpoints = [root]
        for target in endpoints[1:]:
            if len(routes) + len(net_routes) >= max_wired_routes:
                warnings.append(f"wire_route_limit_deferred: remaining endpoints of {net} skipped after {max_wired_routes} routed connections.")
                net_failed = True
                net_failure_warnings.append("wire_route_limit_deferred")
                break
            root = min(
                connected_endpoints,
                key=lambda item: _manhattan(
                    (float(item["point"][0]), float(item["point"][1])),
                    (float(target["point"][0]), float(target["point"][1])),
                ),
            )
            start = (float(root["point"][0]), float(root["point"][1]))
            goal = (float(target["point"][0]), float(target["point"][1]))
            start_route = (
                _portal_point(start, str(root.get("side") or "right"), cfg)
                if root.get("exact")
                else start
            )
            goal_route = (
                _portal_point(goal, str(target.get("side") or "right"), cfg)
                if target.get("exact")
                else goal
            )
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
                )
                if lane_path and lane_report:
                    route_candidates.append(("lane_candidate", lane_path, lane_report, []))

            clean_lane_available = any(
                algorithm == "lane_candidate" and int(report.get("different_net_crossings", 0)) == 0
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

            best_preliminary_crossings = min(
                (int(candidate[2].get("different_net_crossings", 0)) for candidate in route_candidates),
                default=1_000_000,
            )
            if routing_mode == "wire" and best_preliminary_crossings > 0 and cfg.get("crossing_risk_astar", 0.0) >= 1.0:
                fallback_cfg = dict(cfg)
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
                                "strict_crossing_risk_fallback: existing wires were treated as high-cost lanes instead of hard blocks.",
                                *fallback_warnings,
                            ],
                        )
                    )
                elif fallback_warnings:
                    route_warnings.extend(fallback_warnings)
            route_candidates = [candidate for candidate in route_candidates if not candidate[2].get("body_hits")]
            route_candidates.sort(
                key=lambda item: (
                    int(item[2].get("different_net_crossings", 0)),
                    float(item[2].get("score", 0.0)),
                    int(item[2].get("turns", 0)),
                    str(item[0]),
                )
            )
            selected_algorithm = ""
            selected_report: dict[str, Any] = {}
            raw_path: list[Point] = []
            if route_candidates:
                selected_algorithm, raw_path, selected_report, selected_warnings = route_candidates[0]
                route_warnings.extend(selected_warnings)
                if selected_report.get("different_net_crossings"):
                    route_warnings.append(
                        f"minimum_crossing_route: {net} accepted {selected_report['different_net_crossings']} different-net crossing/touch risks."
                    )
            warnings.extend(route_warnings)
            if not raw_path:
                net_failed = True
                net_failed_endpoint_count += 1
                endpoint_name = f"{target.get('ref')}.{target.get('pin')}"
                net_failure_warnings.extend(route_warnings or [f"unroutable_endpoint: {net} {endpoint_name}"])
                if net_failed_endpoint_count >= max_failed_endpoints_per_net:
                    net_failure_warnings.append(
                        f"endpoint_failure_budget_reached: stopped retrying {net} after {net_failed_endpoint_count} failed endpoints."
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
        if net_failed:
            if routing_mode == "wire":
                warnings.append(f"strict_wire_unroutable: {net} could not be routed without labels.")
                if net_routes:
                    occupied.update(net_occupied)
                    existing_segments.extend(pending_net_segments)
                    routes.extend(net_routes)
                    lane_route_count += net_lane_route_count
                    astar_route_count += net_astar_route_count
                    crossing_risk_route_count += net_crossing_risk_route_count
                    nets_out[net] = {
                        "strategy": "partial_wire",
                        "endpoints": endpoints,
                        "routes": net_routes,
                        "unrouted_endpoint_count": net_failed_endpoint_count,
                        "failure_warnings": net_failure_warnings[:20],
                    }
                    continue
                nets_out[net] = {
                    "strategy": "unroutable",
                    "endpoints": endpoints,
                    "routes": [],
                    "partial_routes": net_routes,
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
        crossing_risk_route_count += net_crossing_risk_route_count
        nets_out[net] = {"strategy": "wire", "endpoints": endpoints, "routes": net_routes}

    crossing_count = _count_crossings(routes)
    if crossing_count:
        warnings.append(f"different_net_crossings_detected: {crossing_count}")

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
            "dense_design_mode": dense_design,
            "routing_order": "clock, bus-like/long-span nets, ordinary nets, then power/ground in strict wire mode; terminal/combination mode may label selected nets",
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
            "crossing_risk_route_count": crossing_risk_route_count,
            "dense_design_mode": dense_design,
            "segment_count": sum(len(route["segments"]) for route in routes),
            "different_net_crossing_count": crossing_count,
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


def plan_wiring(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    arrangement_config: dict[str, float] | None = None,
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    coordinate_plan = decide_arrangement(placement, circuit, config=arrangement_config or DEFAULT_ARRANGEMENT_CONFIG)
    routing_placement = apply_coordinate_edits(placement, coordinate_plan)
    wire_plan = plan_wire_routes(routing_placement, circuit, config=wire_config)
    return {
        "schema": "progen-kicad-wire-planner-output/v0.1",
        "component_motion_policy": {
            "phase": "before_route_search",
            "coordinate_source": "arrangement_decider",
            "applied_by": "beautifier",
            "purpose": "move components first so route planning starts from a wiring-aware placement",
        },
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
    wire_path = out_path / "wire_plan.json"
    coordinate_path.write_text(json.dumps(planned["coordinate_plan"], indent=2), encoding="utf-8")
    routing_placement_path.write_text(json.dumps(planned["routing_placement"], indent=2), encoding="utf-8")
    wire_path.write_text(json.dumps(planned["wire_plan"], indent=2), encoding="utf-8")
    return {"coordinate_plan": coordinate_path, "routing_placement": routing_placement_path, "wire_plan": wire_path}
