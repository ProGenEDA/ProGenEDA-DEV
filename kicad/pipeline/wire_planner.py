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


Point = tuple[float, float]
GridPoint = tuple[int, int]


@dataclass(frozen=True)
class Body:
    ref: str
    left: float
    top: float
    right: float
    bottom: float

    @property
    def center(self) -> Point:
        return ((self.left + self.right) / 2, (self.top + self.bottom) / 2)

    def contains(self, point: Point, clearance: float = 0.0) -> bool:
        x, y = point
        return self.left - clearance <= x <= self.right + clearance and self.top - clearance <= y <= self.bottom + clearance


DEFAULT_WIRE_CONFIG: dict[str, float] = {
    "grid": 2.54,
    "sheet_width": 420.0,
    "sheet_height": 297.0,
    "margin": 15.24,
    "clearance": 2.54,
    "pin_stub": 5.08,
    "wire_spacing": 2.54,
    "turn_penalty": 0.15,
    "near_wire_penalty": 1.25,
    "max_astar_expansions": 50_000.0,
    "max_wired_routes": 10_000.0,
}


def _snap(value: float, grid: float) -> float:
    return round(round(value / grid) * grid, 3)


def _round_point(point: Point) -> Point:
    return (round(point[0], 3), round(point[1], 3))


def _bodies(placement: dict[str, Any]) -> dict[str, Body]:
    bodies: dict[str, Body] = {}
    for item in placement.get("obstacles", []):
        if isinstance(item, dict) and item.get("owner"):
            bodies[str(item["owner"])] = Body(
                str(item["owner"]),
                float(item.get("left", 0.0)),
                float(item.get("top", 0.0)),
                float(item.get("right", 0.0)),
                float(item.get("bottom", 0.0)),
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
            bodies[str(ref)] = Body(str(ref), x - width / 2, y - height / 2, x + width / 2, y + height / 2)
    return bodies


def _sheet_bounds(bodies: dict[str, Body], cfg: dict[str, float]) -> tuple[float, float]:
    max_right = max((body.right for body in bodies.values()), default=cfg["sheet_width"])
    max_bottom = max((body.bottom for body in bodies.values()), default=cfg["sheet_height"])
    return (max(cfg["sheet_width"], max_right + cfg["margin"]), max(cfg["sheet_height"], max_bottom + cfg["margin"]))


def _side_for_endpoint(net: str, ref: str, refs: list[str], bodies: dict[str, Body]) -> str:
    upper = net.upper()
    if upper in POWER_NETS:
        return "top"
    if upper in GROUND_NETS:
        return "bottom"
    body = bodies[ref]
    others = [bodies[other].center[0] for other in refs if other in bodies and other != ref]
    if not others:
        return "right"
    return "right" if sum(others) / len(others) >= body.center[0] else "left"


def _endpoint_points(placement: dict[str, Any], circuit: dict[str, Any], cfg: dict[str, float]) -> dict[str, list[dict[str, Any]]]:
    bodies = _bodies(placement)
    nets = extract_connection_nets(circuit)
    side_buckets: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    endpoint_meta: dict[tuple[str, str, str], str] = {}
    for net, endpoints in nets.items():
        refs = sorted({endpoint.ref for endpoint in endpoints if endpoint.ref in bodies})
        for endpoint in endpoints:
            if endpoint.ref not in bodies:
                continue
            side = _side_for_endpoint(net, endpoint.ref, refs, bodies)
            key = (endpoint.ref, side)
            side_buckets[key].append((net, endpoint.pin))
            endpoint_meta[(net, endpoint.ref, endpoint.pin)] = side

    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for net, endpoints in nets.items():
        refs = sorted({endpoint.ref for endpoint in endpoints if endpoint.ref in bodies})
        for endpoint in endpoints:
            if endpoint.ref not in bodies:
                continue
            body = bodies[endpoint.ref]
            side = endpoint_meta[(net, endpoint.ref, endpoint.pin)]
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
            out[net].append(
                {
                    "ref": endpoint.ref,
                    "pin": endpoint.pin,
                    "side": side,
                    "point": [point[0], point[1]],
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
) -> set[GridPoint]:
    grid = cfg["grid"]
    clearance = cfg["clearance"]
    blocked: set[GridPoint] = set()
    for ref, body in bodies.items():
        if ref in ignore_refs:
            continue
        left = round((body.left - clearance) / grid)
        right = round((body.right + clearance) / grid)
        top = round((body.top - clearance) / grid)
        bottom = round((body.bottom + clearance) / grid)
        for x in range(left, right + 1):
            for y in range(top, bottom + 1):
                blocked.add((x, y))
    return blocked


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
            warnings.append(f"astar_fallback_expansion_limit: {net} exceeded {max_expansions} explored grid states.")
            return [
                _round_point(start),
                _round_point((goal[0], start[1])),
                _round_point(goal),
            ], warnings
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
            if owner and owner != net:
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
        warnings.append(f"astar_fallback_manhattan: no clear route found for {net}.")
        return [
            _round_point(start),
            _round_point((goal[0], start[1])),
            _round_point(goal),
        ], warnings

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


def _local_label_net(net: str, endpoints: list[dict[str, Any]]) -> bool:
    upper = net.upper()
    return upper in POWER_NETS or upper in GROUND_NETS or len(endpoints) >= 7


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
    config: dict[str, float] | None = None,
) -> dict[str, Any]:
    cfg = dict(DEFAULT_WIRE_CONFIG)
    if config:
        cfg.update({key: float(value) for key, value in config.items()})

    bodies = _bodies(placement)
    endpoints_by_net = _endpoint_points(placement, circuit, cfg)
    occupied: dict[GridPoint, str] = {}
    routes: list[dict[str, Any]] = []
    nets_out: dict[str, Any] = {}
    warnings: list[str] = []
    max_wired_routes = max(1, int(cfg.get("max_wired_routes", 10_000.0)))

    def net_priority(item: tuple[str, list[dict[str, Any]]]) -> tuple[int, str]:
        net, endpoints = item
        upper = net.upper()
        if any(token in upper for token in ("CLK", "CLOCK", "CK", "CP")):
            return (0, net)
        if upper in POWER_NETS or upper in GROUND_NETS:
            return (2, net)
        return (1 if len(endpoints) <= 6 else 3, net)

    for net, endpoints in sorted(endpoints_by_net.items(), key=net_priority):
        if len(endpoints) < 2:
            nets_out[net] = {"strategy": "single_endpoint_label", "endpoints": endpoints, "routes": []}
            continue
        if _local_label_net(net, endpoints):
            nets_out[net] = {"strategy": "local_labels", "endpoints": endpoints, "routes": []}
            continue
        if len(routes) >= max_wired_routes:
            warnings.append(f"wire_route_limit_deferred: {net} skipped after {max_wired_routes} routed connections.")
            nets_out[net] = {"strategy": "deferred_after_route_limit", "endpoints": endpoints, "routes": []}
            continue

        endpoints = sorted(endpoints, key=lambda item: (item["point"][0], item["point"][1], item["ref"], item["pin"]))
        net_routes: list[dict[str, Any]] = []
        root = endpoints[0]
        for target in endpoints[1:]:
            if len(routes) >= max_wired_routes:
                warnings.append(f"wire_route_limit_deferred: remaining endpoints of {net} skipped after {max_wired_routes} routed connections.")
                break
            start = (float(root["point"][0]), float(root["point"][1]))
            goal = (float(target["point"][0]), float(target["point"][1]))
            ignore_refs = {str(root["ref"]), str(target["ref"])}
            raw_path, route_warnings = _astar(start, goal, bodies, cfg, occupied, net=net, ignore_refs=ignore_refs)
            warnings.extend(route_warnings)
            path = _compress_path(raw_path)
            for point in raw_path:
                occupied[_to_grid(point, cfg["grid"])] = net
            route = {
                "net": net,
                "from": {"ref": root["ref"], "pin": root["pin"], "point": root["point"]},
                "to": {"ref": target["ref"], "pin": target["pin"], "point": target["point"]},
                "path": [[point[0], point[1]] for point in path],
                "segments": _segments(path),
            }
            routes.append(route)
            net_routes.append(route)
        nets_out[net] = {"strategy": "wire", "endpoints": endpoints, "routes": net_routes}

    crossing_count = _count_crossings(routes)
    if crossing_count:
        warnings.append(f"different_net_crossings_detected: {crossing_count}")

    width, height = _sheet_bounds(bodies, cfg)
    return {
        "schema": "progen-kicad-wire-plan/v0.1",
        "stage": "wire_planner",
        "input_contract": {
            "placement": "components plus obstacles JSON; no EDA file required",
            "connections": "CircuitIR components[].pins and/or nets endpoint lists",
        },
        "algorithm": {
            "router": "grid_astar_orthogonal",
            "routing_order": "clock, ordinary short nets, power/ground labels, high-fanout labels",
            "component_avoidance": "inflated_obstacle_grid",
            "wire_collision_policy": "different-net existing wires receive high cost plus adjacency penalty",
        },
        "sheet": {"width": width, "height": height, "grid": cfg["grid"], "clearance": cfg["clearance"]},
        "nets": nets_out,
        "routes": routes,
        "metrics": {
            "net_count": len(endpoints_by_net),
            "wired_route_count": len(routes),
            "segment_count": sum(len(route["segments"]) for route in routes),
            "different_net_crossing_count": crossing_count,
        },
        "warnings": warnings,
    }


def plan_wiring(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    arrangement_config: dict[str, float] | None = None,
    wire_config: dict[str, float] | None = None,
) -> dict[str, Any]:
    coordinate_plan = decide_arrangement(placement, circuit, config=arrangement_config or DEFAULT_ARRANGEMENT_CONFIG)
    wire_plan = plan_wire_routes(placement, circuit, config=wire_config)
    return {
        "schema": "progen-kicad-wire-planner-output/v0.1",
        "coordinate_plan": coordinate_plan,
        "wire_plan": wire_plan,
    }


def write_wire_planner_jsons(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    out_dir: str | Path,
    *,
    arrangement_config: dict[str, float] | None = None,
    wire_config: dict[str, float] | None = None,
) -> dict[str, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    planned = plan_wiring(placement, circuit, arrangement_config=arrangement_config, wire_config=wire_config)
    coordinate_path = out_path / "wire_coordinate_plan.json"
    wire_path = out_path / "wire_plan.json"
    coordinate_path.write_text(json.dumps(planned["coordinate_plan"], indent=2), encoding="utf-8")
    wire_path.write_text(json.dumps(planned["wire_plan"], indent=2), encoding="utf-8")
    return {"coordinate_plan": coordinate_path, "wire_plan": wire_path}
