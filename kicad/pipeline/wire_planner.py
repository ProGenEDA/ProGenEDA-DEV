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
    "near_wire_penalty": 1.25,
    "block_existing_wires": 1.0,
    "max_astar_expansions": 50_000.0,
    "strict_fallback_max_astar_expansions": 50_000.0,
    "max_wired_routes": 10_000.0,
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
) -> set[GridPoint]:
    grid = cfg["grid"]
    clearance = cfg["clearance"]
    blocked: set[GridPoint] = set()
    for ref, body in bodies.items():
        if ref in ignore_refs or (body.component_ref and body.component_ref in ignore_refs):
            continue
        left = round((body.left - clearance) / grid)
        right = round((body.right + clearance) / grid)
        top = round((body.top - clearance) / grid)
        bottom = round((body.bottom + clearance) / grid)
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
    routes: list[dict[str, Any]] = []
    nets_out: dict[str, Any] = {}
    warnings: list[str] = []
    max_wired_routes = max(1, int(cfg.get("max_wired_routes", 10_000.0)))

    def net_priority(item: tuple[str, list[dict[str, Any]]]) -> tuple[int, str]:
        net, endpoints = item
        upper = net.upper()
        if any(token in upper for token in ("CLK", "CLOCK", "CK", "CP")):
            return (0, net)
        if routing_mode != "wire" and (upper in POWER_NETS or upper in GROUND_NETS):
            return (2, net)
        return (1 if len(endpoints) <= 6 else 3, net)

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
        net_failed = False
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
            raw_path, route_warnings = _astar(
                start_route,
                goal_route,
                bodies,
                cfg,
                routed_occupied,
                net=net,
                ignore_refs=ignore_refs,
                portals=portals,
            )
            if not raw_path and routing_mode == "wire":
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
                    raw_path = fallback_path
                    route_warnings = [
                        *route_warnings,
                        "strict_crossing_risk_fallback: existing wires were treated as high-cost lanes instead of hard blocks.",
                        *fallback_warnings,
                    ]
            warnings.extend(route_warnings)
            if not raw_path:
                net_failed = True
                net_failure_warnings.extend(route_warnings or [f"unroutable: {net}"])
                break
            full_raw_path = _join_paths(
                _orthogonal_escape_path(start, start_route),
                raw_path,
                _orthogonal_escape_path(goal_route, goal),
            )
            path = _compress_path(full_raw_path)
            for point in full_raw_path:
                net_occupied[_to_grid(point, cfg["grid"])] = net
            route = {
                "net": net,
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
        routes.extend(net_routes)
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
            "router": "grid_astar_orthogonal",
            "routing_order": "clock, ordinary short nets, then remaining nets; terminal/combination mode may label selected nets",
            "component_avoidance": "inflated_obstacle_grid",
            "wire_collision_policy": "existing wire grid cells are blocked; adjacent different-net wires receive penalty",
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
            "segment_count": sum(len(route["segments"]) for route in routes),
            "different_net_crossing_count": crossing_count,
            "label_strategy_count": sum(1 for item in nets_out.values() if isinstance(item, dict) and item.get("strategy") in LABEL_STRATEGIES),
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
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    planned = plan_wiring(placement, circuit, arrangement_config=arrangement_config, wire_config=wire_config)
    coordinate_path = out_path / "wire_coordinate_plan.json"
    wire_path = out_path / "wire_plan.json"
    coordinate_path.write_text(json.dumps(planned["coordinate_plan"], indent=2), encoding="utf-8")
    wire_path.write_text(json.dumps(planned["wire_plan"], indent=2), encoding="utf-8")
    return {"coordinate_plan": coordinate_path, "wire_plan": wire_path}
