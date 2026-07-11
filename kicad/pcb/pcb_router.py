"""Deterministic two-layer grid router for generated KiCad PCBs."""

from __future__ import annotations

import heapq
import math
import random
from dataclasses import dataclass
from itertools import count
from typing import Any, Iterable

from .footprint_placer import PCBPlacement, PlacedFootprint
from .physical_design_compiler import PhysicalDesign


ROUTER_SCHEMA = "progen-kicad-pcb-route-plan/v0.1"
LAYERS = ("F.Cu", "B.Cu")
GridPoint = tuple[int, int]
State = tuple[int, int, int]
Point = tuple[float, float]
Edge = tuple[State, State]


@dataclass(frozen=True)
class PadEndpoint:
    ref: str
    pad: str
    net: str
    point: Point
    route_point: Point
    layers: tuple[str, ...]
    size: tuple[float, float]

    @property
    def identity(self) -> str:
        return f"{self.ref}.{self.pad}"


@dataclass(frozen=True)
class PCBRoutePlan:
    grid: float
    track_width: float
    via_size: float
    via_drill: float
    segments: tuple[dict[str, Any], ...]
    vias: tuple[dict[str, Any], ...]
    net_results: tuple[dict[str, Any], ...]

    @property
    def unrouted_net_count(self) -> int:
        return sum(1 for result in self.net_results if result["status"] not in {"routed", "single_pad"})

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": ROUTER_SCHEMA,
            "grid": self.grid,
            "track_width": self.track_width,
            "via_size": self.via_size,
            "via_drill": self.via_drill,
            "segment_count": len(self.segments),
            "via_count": len(self.vias),
            "unrouted_net_count": self.unrouted_net_count,
            "ok": self.unrouted_net_count == 0,
            "segments": list(self.segments),
            "vias": list(self.vias),
            "net_results": list(self.net_results),
        }


def route_pcb_with_retries(
    design: PhysicalDesign,
    placement: PCBPlacement,
    *,
    max_attempts: int = 8,
    strategy_variants: bool = False,
    **kwargs: Any,
) -> tuple[PCBRoutePlan, list[dict[str, Any]]]:
    """Retry from scratch with failed nets promoted ahead of their blockers."""

    priorities: list[str] = []
    variants: list[dict[str, Any]] = []
    best: PCBRoutePlan | None = None
    seen_priority_sets: set[tuple[str, ...]] = set()
    order_strategies = ("high_fanout_first", "low_fanout_first", "alphabetical")
    for attempt in range(max_attempts):
        if strategy_variants:
            strategy = order_strategies[attempt % len(order_strategies)]
            # Each first-pass ordering must be allowed to stand on its own.
            # After the strategy sweep, promote observed failures for a
            # rip-up-style retry without discarding independent candidates.
            key = tuple(priorities) if attempt >= len(order_strategies) else ()
        else:
            strategy = "high_fanout_first"
            key = tuple(priorities)
        candidate_key = (strategy, *key)
        if candidate_key in seen_priority_sets:
            break
        seen_priority_sets.add(candidate_key)
        plan = route_pcb(design, placement, order_strategy=strategy, priority_nets=key, **kwargs)
        failed = [
            str(result["net"])
            for result in plan.net_results
            if result["status"] not in {"routed", "single_pad"}
        ]
        variants.append(
            {
                "attempt": attempt + 1,
                "order_strategy": strategy,
                "priority_nets": list(key),
                "failed_nets": failed,
                "unrouted_net_count": plan.unrouted_net_count,
                "segment_count": len(plan.segments),
                "via_count": len(plan.vias),
                "accepted": False,
            }
        )
        score = (plan.unrouted_net_count, len(plan.vias), len(plan.segments))
        if best is None or score < (best.unrouted_net_count, len(best.vias), len(best.segments)):
            best = plan
        if not failed:
            best = plan
            break
        priorities = list(dict.fromkeys([*failed, *priorities]))
    if best is None:
        best = route_pcb(design, placement, **kwargs)
    accepted_score = (best.unrouted_net_count, len(best.vias), len(best.segments))
    for variant in variants:
        variant["accepted"] = (
            variant["unrouted_net_count"],
            variant["via_count"],
            variant["segment_count"],
        ) == accepted_score
        if variant["accepted"]:
            break
    return best, variants


def _snap_index(value: float, grid: float) -> int:
    scaled = value / grid
    return math.floor(scaled + 0.5) if scaled >= 0 else math.ceil(scaled - 0.5)


def _point(index: GridPoint, grid: float) -> Point:
    return (round(index[0] * grid, 4), round(index[1] * grid, 4))


def _pad_layers(pad: dict[str, Any]) -> tuple[str, ...]:
    raw = tuple(str(layer) for layer in pad.get("layers", []))
    if "*.Cu" in raw or pad.get("mount_type") in {"thru_hole", "np_thru_hole"}:
        return LAYERS
    layers = tuple(layer for layer in LAYERS if layer in raw)
    return layers or ("F.Cu",)


def _all_pad_endpoints(design: PhysicalDesign, placement: PCBPlacement) -> tuple[PadEndpoint, ...]:
    placed_by_ref = {item.component.ref: item for item in placement.footprints}
    endpoints: list[PadEndpoint] = []
    for component in design.components:
        placed = placed_by_ref[component.ref]
        pad_sides: dict[str, str] = {}
        side_members: dict[str, list[tuple[float, str]]] = {side: [] for side in ("left", "right", "top", "bottom")}
        smd_points = [
            placed.world_pad_record(record)
            for record in component.footprint.pads
            if record.get("mount_type") == "smd"
        ]
        pad_min_x = min((point[0] for point in smd_points), default=placed.bounds[0])
        pad_max_x = max((point[0] for point in smd_points), default=placed.bounds[2])
        pad_min_y = min((point[1] for point in smd_points), default=placed.bounds[1])
        pad_max_y = max((point[1] for point in smd_points), default=placed.bounds[3])
        for pad_record in component.footprint.pads:
            pad = str(pad_record["number"])
            if pad_record.get("mount_type") != "smd":
                continue
            point = placed.world_pad_record(pad_record)
            distances = {
                "left": abs(point[0] - pad_min_x),
                "right": abs(pad_max_x - point[0]),
                "top": abs(point[1] - pad_min_y),
                "bottom": abs(pad_max_y - point[1]),
            }
            side = min(distances, key=distances.get)
            pad_sides[pad] = side
            ordering_coordinate = point[1] if side in {"left", "right"} else point[0]
            side_members[side].append((ordering_coordinate, pad))
        for pad_record in component.footprint.pads:
            pad = str(pad_record["number"])
            net = component.pad_nets.get(pad, "")
            point = placed.world_pad_record(pad_record)
            layers = _pad_layers(pad_record)
            route_point = point
            if pad_record.get("mount_type") == "smd":
                left, top, right, bottom = placed.bounds
                side = pad_sides[pad]
                escape = 2.54 + 1.27 * len(side_members[side])
                if side == "left":
                    route_point = (round(left - escape, 4), point[1])
                elif side == "right":
                    route_point = (round(right + escape, 4), point[1])
                elif side == "top":
                    route_point = (point[0], round(top - escape, 4))
                else:
                    route_point = (point[0], round(bottom + escape, 4))
            endpoints.append(
                PadEndpoint(
                    ref=component.ref,
                    pad=pad,
                    net=net,
                    point=point,
                    route_point=route_point,
                    layers=layers,
                    size=tuple(float(value) for value in pad_record.get("size", (1.0, 1.0)))[:2],
                )
            )
    return tuple(endpoints)


def _pad_obstacles(
    endpoints: Iterable[PadEndpoint],
    *,
    grid: float,
    clearance: float,
) -> dict[tuple[int, int, int], set[str]]:
    blocked: dict[tuple[int, int, int], set[str]] = {}
    for endpoint in endpoints:
        center_x = _snap_index(endpoint.point[0], grid)
        center_y = _snap_index(endpoint.point[1], grid)
        half_x = endpoint.size[0] / 2
        half_y = endpoint.size[1] / 2
        radius_x = max(0, math.ceil((half_x + clearance) / grid) + 1)
        radius_y = max(0, math.ceil((half_y + clearance) / grid) + 1)
        owner = endpoint.net or f"__PAD__{endpoint.identity}"
        for layer in endpoint.layers:
            layer_index = LAYERS.index(layer)
            for dx in range(-radius_x, radius_x + 1):
                for dy in range(-radius_y, radius_y + 1):
                    point = _point((center_x + dx, center_y + dy), grid)
                    distance_x = max(abs(point[0] - endpoint.point[0]) - half_x, 0.0)
                    distance_y = max(abs(point[1] - endpoint.point[1]) - half_y, 0.0)
                    if math.hypot(distance_x, distance_y) < clearance:
                        blocked.setdefault((center_x + dx, center_y + dy, layer_index), set()).add(owner)
    return blocked


def _heuristic(state: State, goals: set[State]) -> float:
    if not goals:
        return 0.0
    xs = [goal[0] for goal in goals]
    ys = [goal[1] for goal in goals]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = 0 if min_x <= state[0] <= max_x else min(abs(state[0] - min_x), abs(state[0] - max_x))
    dy = 0 if min_y <= state[1] <= max_y else min(abs(state[1] - min_y), abs(state[1] - max_y))
    return float(dx + dy)


def _astar(
    starts: set[State],
    goals: set[State],
    *,
    bounds: tuple[int, int, int, int],
    blocked: dict[State, set[str]],
    blocked_edges: dict[Edge, set[str]],
    via_forbidden: dict[GridPoint, set[str]],
    net: str,
    via_cost: float = 8.0,
    max_expansions: int = 20_000,
) -> list[State] | None:
    if starts & goals:
        return [next(iter(starts & goals))]
    min_x, min_y, max_x, max_y = bounds
    serial = count()
    queue: list[tuple[float, float, int, State]] = []
    distance: dict[State, float] = {}
    previous: dict[State, State] = {}
    for start in starts:
        distance[start] = 0.0
        heapq.heappush(queue, (_heuristic(start, goals), 0.0, next(serial), start))
    visited: set[State] = set()
    while queue:
        _, cost, _, state = heapq.heappop(queue)
        if state in visited:
            continue
        visited.add(state)
        if len(visited) > max_expansions:
            return None
        if state in goals:
            path = [state]
            while state in previous:
                state = previous[state]
                path.append(state)
            path.reverse()
            return path
        x, y, layer = state
        neighbors = [
            ((x - 1, y, layer), 1.0),
            ((x + 1, y, layer), 1.0),
            ((x, y - 1, layer), 1.0),
            ((x, y + 1, layer), 1.0),
            ((x, y, 1 - layer), via_cost),
        ]
        for neighbor, step_cost in neighbors:
            nx, ny, _ = neighbor
            if nx < min_x or nx > max_x or ny < min_y or ny > max_y:
                continue
            if neighbor[2] != layer and any(owner != net for owner in via_forbidden.get((x, y), set())):
                continue
            edge = tuple(sorted((state, neighbor)))
            if any(owner != net for owner in blocked_edges.get(edge, set())):
                continue
            owners = blocked.get(neighbor, set())
            if any(owner != net for owner in owners):
                continue
            next_cost = cost + step_cost
            if next_cost >= distance.get(neighbor, float("inf")):
                continue
            distance[neighbor] = next_cost
            previous[neighbor] = state
            heapq.heappush(queue, (next_cost + _heuristic(neighbor, goals), next_cost, next(serial), neighbor))
    return None


def _direct_path(
    starts: set[State],
    goals: set[State],
    *,
    bounds: tuple[int, int, int, int],
    blocked: dict[State, set[str]],
    blocked_edges: dict[Edge, set[str]],
    net: str,
) -> list[State] | None:
    """Return a legal same-layer Manhattan path before invoking A*.

    Most passive-to-IC connections in a generously sized generated board are
    already reachable with one bend.  Testing those two candidates is exact
    with respect to the router's occupancy model and avoids a grid search.
    """

    min_x, min_y, max_x, max_y = bounds

    def line(start: State, end: State) -> list[State]:
        x, y, layer = start
        target_x, target_y, _ = end
        path = [start]
        while x != target_x:
            x += 1 if target_x > x else -1
            path.append((x, y, layer))
        while y != target_y:
            y += 1 if target_y > y else -1
            path.append((x, y, layer))
        return path

    def legal(path: list[State]) -> bool:
        for index, state in enumerate(path):
            x, y, _ = state
            if x < min_x or x > max_x or y < min_y or y > max_y:
                return False
            if index not in {0, len(path) - 1} and any(owner != net for owner in blocked.get(state, set())):
                return False
            if index:
                edge = tuple(sorted((path[index - 1], state)))
                if any(owner != net for owner in blocked_edges.get(edge, set())):
                    return False
        return True

    for start in sorted(starts):
        for goal in sorted(goals):
            if start[2] != goal[2]:
                continue
            corners = ((goal[0], start[1], start[2]), (start[0], goal[1], start[2]))
            for corner in corners:
                candidate = line(start, corner)
                candidate.extend(line(corner, goal)[1:])
                if legal(candidate):
                    return candidate
    return None


def _endpoint_growth_order(endpoints: list[PadEndpoint]) -> list[PadEndpoint]:
    """Choose a compact, deterministic tree order for a multi-pad net."""

    if len(endpoints) <= 2:
        return endpoints
    centre_x = sum(endpoint.route_point[0] for endpoint in endpoints) / len(endpoints)
    centre_y = sum(endpoint.route_point[1] for endpoint in endpoints) / len(endpoints)
    first = min(
        endpoints,
        key=lambda endpoint: (
            abs(endpoint.route_point[0] - centre_x) + abs(endpoint.route_point[1] - centre_y),
            endpoint.identity,
        ),
    )
    ordered = [first]
    remaining = [endpoint for endpoint in endpoints if endpoint is not first]
    while remaining:
        next_endpoint = min(
            remaining,
            key=lambda endpoint: (
                min(
                    abs(endpoint.route_point[0] - placed.route_point[0])
                    + abs(endpoint.route_point[1] - placed.route_point[1])
                    for placed in ordered
                ),
                endpoint.identity,
            ),
        )
        remaining.remove(next_endpoint)
        ordered.append(next_endpoint)
    return ordered


def _states_for_endpoint(endpoint: PadEndpoint, grid: float) -> set[State]:
    x = _snap_index(endpoint.route_point[0], grid)
    y = _snap_index(endpoint.route_point[1], grid)
    return {(x, y, LAYERS.index(layer)) for layer in endpoint.layers}


def _path_objects(path: list[State], net: str, grid: float, track_width: float) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    segments: list[dict[str, Any]] = []
    vias: list[dict[str, Any]] = []
    if len(path) < 2:
        return segments, vias
    run_start = path[0]
    previous = path[0]
    direction: tuple[int, int, int] | None = None

    def flush(end: State) -> None:
        nonlocal run_start
        if run_start[:2] == end[:2] or run_start[2] != end[2]:
            run_start = end
            return
        segments.append(
            {
                "net": net,
                "layer": LAYERS[run_start[2]],
                "start": list(_point(run_start[:2], grid)),
                "end": list(_point(end[:2], grid)),
                "width": track_width,
            }
        )
        run_start = end

    for current in path[1:]:
        if current[2] != previous[2]:
            flush(previous)
            vias.append({"net": net, "at": list(_point(current[:2], grid))})
            run_start = current
            previous = current
            direction = None
            continue
        current_direction = (current[0] - previous[0], current[1] - previous[1], 0)
        if direction is not None and current_direction != direction:
            flush(previous)
            run_start = previous
        direction = current_direction
        previous = current
    flush(previous)
    return segments, vias


def _pad_links(endpoint: PadEndpoint, state: State, net: str, grid: float, track_width: float) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    if endpoint.point != endpoint.route_point:
        links.append(
            {
                "net": net,
                "layer": LAYERS[state[2]],
                "start": list(endpoint.point),
                "end": list(endpoint.route_point),
                "width": track_width,
                "pad_escape": endpoint.identity,
            }
        )
    snapped = _point(state[:2], grid)
    if abs(snapped[0] - endpoint.route_point[0]) >= 1e-6 or abs(snapped[1] - endpoint.route_point[1]) >= 1e-6:
        links.append(
            {
                "net": net,
                "layer": LAYERS[state[2]],
                "start": list(endpoint.route_point),
                "end": list(snapped),
                "width": track_width,
                "pad_escape": endpoint.identity,
            }
        )
    return links


def _rasterized_cells(start: Iterable[float], end: Iterable[float], grid: float) -> set[GridPoint]:
    start_x, start_y = (float(value) for value in start)
    end_x, end_y = (float(value) for value in end)
    distance = max(abs(end_x - start_x), abs(end_y - start_y))
    steps = max(1, int(math.ceil(distance / (grid / 4))))
    return {
        (
            _snap_index(start_x + (end_x - start_x) * index / steps, grid),
            _snap_index(start_y + (end_y - start_y) * index / steps, grid),
        )
        for index in range(steps + 1)
    }


def _cells_near_segment(
    start: Iterable[float],
    end: Iterable[float],
    *,
    grid: float,
    distance: float,
) -> set[GridPoint]:
    start_x, start_y = (float(value) for value in start)
    end_x, end_y = (float(value) for value in end)
    min_x = _snap_index(min(start_x, end_x) - distance - grid, grid)
    max_x = _snap_index(max(start_x, end_x) + distance + grid, grid)
    min_y = _snap_index(min(start_y, end_y) - distance - grid, grid)
    max_y = _snap_index(max(start_y, end_y) + distance + grid, grid)
    dx = end_x - start_x
    dy = end_y - start_y
    denominator = dx * dx + dy * dy
    cells: set[GridPoint] = set()
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            point_x, point_y = _point((x, y), grid)
            if denominator <= 1e-12:
                separation = math.hypot(point_x - start_x, point_y - start_y)
            else:
                ratio = ((point_x - start_x) * dx + (point_y - start_y) * dy) / denominator
                ratio = min(1.0, max(0.0, ratio))
                closest_x = start_x + ratio * dx
                closest_y = start_y + ratio * dy
                separation = math.hypot(point_x - closest_x, point_y - closest_y)
            if separation < distance:
                cells.add((x, y))
    return cells


def _orientation_points(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _point_line_segment_distance(point: Point, start: Point, end: Point) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    denominator = dx * dx + dy * dy
    if denominator <= 1e-12:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / denominator
    ratio = min(1.0, max(0.0, ratio))
    return math.hypot(point[0] - (start[0] + ratio * dx), point[1] - (start[1] + ratio * dy))


def _segments_cross(left_start: Point, left_end: Point, right_start: Point, right_end: Point) -> bool:
    tolerance = 1e-9
    values = (
        _orientation_points(left_start, left_end, right_start),
        _orientation_points(left_start, left_end, right_end),
        _orientation_points(right_start, right_end, left_start),
        _orientation_points(right_start, right_end, left_end),
    )
    if ((values[0] > tolerance and values[1] < -tolerance) or (values[0] < -tolerance and values[1] > tolerance)) and (
        (values[2] > tolerance and values[3] < -tolerance) or (values[2] < -tolerance and values[3] > tolerance)
    ):
        return True
    return min(
        _point_line_segment_distance(left_start, right_start, right_end),
        _point_line_segment_distance(left_end, right_start, right_end),
        _point_line_segment_distance(right_start, left_start, left_end),
        _point_line_segment_distance(right_end, left_start, left_end),
    ) <= tolerance


def _segment_separation(left_start: Point, left_end: Point, right_start: Point, right_end: Point) -> float:
    if _segments_cross(left_start, left_end, right_start, right_end):
        return 0.0
    return min(
        _point_line_segment_distance(left_start, right_start, right_end),
        _point_line_segment_distance(left_end, right_start, right_end),
        _point_line_segment_distance(right_start, left_start, left_end),
        _point_line_segment_distance(right_end, left_start, left_end),
    )


def _edges_near_segment(
    start: Iterable[float],
    end: Iterable[float],
    *,
    grid: float,
    layer_index: int,
    distance: float,
) -> set[Edge]:
    link_start = tuple(float(value) for value in start)
    link_end = tuple(float(value) for value in end)
    min_x = _snap_index(min(link_start[0], link_end[0]) - distance - grid, grid)
    max_x = _snap_index(max(link_start[0], link_end[0]) + distance + grid, grid)
    min_y = _snap_index(min(link_start[1], link_end[1]) - distance - grid, grid)
    max_y = _snap_index(max(link_start[1], link_end[1]) + distance + grid, grid)
    edges: set[Edge] = set()
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            state = (x, y, layer_index)
            for neighbor in ((x + 1, y, layer_index), (x, y + 1, layer_index)):
                if _segment_separation(
                    _point((state[0], state[1]), grid),
                    _point((neighbor[0], neighbor[1]), grid),
                    link_start,
                    link_end,
                ) < distance:
                    edges.add(tuple(sorted((state, neighbor))))
    return edges


def route_pcb(
    design: PhysicalDesign,
    placement: PCBPlacement,
    *,
    grid: float = 1.27,
    track_width: float = 0.25,
    clearance: float = 0.2,
    via_size: float = 0.8,
    via_drill: float = 0.4,
    order_strategy: str = "high_fanout_first",
    order_seed: int | None = None,
    priority_nets: tuple[str, ...] = (),
    max_astar_expansions: int = 20_000,
    enable_direct_paths: bool = False,
    compact_high_fanout_trees: bool = False,
) -> PCBRoutePlan:
    all_pads = _all_pad_endpoints(design, placement)
    connected = [pad for pad in all_pads if pad.net]
    by_net: dict[str, list[PadEndpoint]] = {}
    for endpoint in connected:
        by_net.setdefault(endpoint.net, []).append(endpoint)
    blocked = _pad_obstacles(all_pads, grid=grid, clearance=clearance + via_size / 2)
    blocked_edges: dict[Edge, set[str]] = {}
    via_forbidden: dict[GridPoint, set[str]] = {}
    for endpoint in connected:
        state = min(_states_for_endpoint(endpoint, grid), key=lambda item: item[2])
        for link in _pad_links(endpoint, state, endpoint.net, grid, track_width):
            layer_index = LAYERS.index(str(link["layer"]))
            for edge in _edges_near_segment(
                link["start"],
                link["end"],
                grid=grid,
                layer_index=layer_index,
                distance=track_width + clearance,
            ):
                blocked_edges.setdefault(edge, set()).add(endpoint.net)
            for cell in _cells_near_segment(
                link["start"],
                link["end"],
                grid=grid,
                distance=track_width / 2 + via_size / 2 + clearance,
            ):
                via_forbidden.setdefault(cell, set()).add(endpoint.net)
    board = placement.board_bounds
    bounds = (
        _snap_index(board[0] + 1.27, grid),
        _snap_index(board[1] + 1.27, grid),
        _snap_index(board[2] - 1.27, grid),
        _snap_index(board[3] - 1.27, grid),
    )
    segments: list[dict[str, Any]] = []
    vias: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []

    if priority_nets:
        priority = {name: index for index, name in enumerate(priority_nets)}
        ordered_nets = sorted(
            by_net.items(),
            key=lambda item: (
                0 if item[0] in priority else 1,
                priority.get(item[0], 0),
                -len(item[1]),
                item[0],
            ),
        )
    elif order_seed is not None:
        ordered_nets = sorted(by_net.items())
        random.Random(order_seed).shuffle(ordered_nets)
    elif order_strategy == "low_fanout_first":
        ordered_nets = sorted(by_net.items(), key=lambda item: (len(item[1]), item[0]))
    elif order_strategy == "alphabetical":
        ordered_nets = sorted(by_net.items())
    else:
        ordered_nets = sorted(by_net.items(), key=lambda item: (-len(item[1]), item[0]))
    for net, endpoints in ordered_nets:
        if compact_high_fanout_trees and len(endpoints) > 8:
            endpoints = _endpoint_growth_order(endpoints)
        if len(endpoints) < 2:
            results.append({"net": net, "status": "single_pad", "member_count": len(endpoints), "routed_member_count": len(endpoints)})
            continue
        first = endpoints[0]
        first_states = _states_for_endpoint(first, grid)
        tree: set[State] = set(first_states)
        net_segments: list[dict[str, Any]] = []
        net_vias: list[dict[str, Any]] = []
        for first_state in sorted(first_states, key=lambda state: state[2]):
            net_segments.extend(_pad_links(first, first_state, net, grid, track_width))
        routed_members = 1
        failed_members: list[str] = []
        for endpoint in endpoints[1:]:
            starts = _states_for_endpoint(endpoint, grid)
            path = None
            if enable_direct_paths:
                path = _direct_path(
                    starts,
                    tree,
                    bounds=bounds,
                    blocked=blocked,
                    blocked_edges=blocked_edges,
                    net=net,
                )
            if path is None:
                path = _astar(
                    starts,
                    tree,
                    bounds=bounds,
                    blocked=blocked,
                    blocked_edges=blocked_edges,
                    via_forbidden=via_forbidden,
                    net=net,
                    max_expansions=max_astar_expansions,
                )
            if path is None:
                failed_members.append(endpoint.identity)
                continue
            net_segments.extend(_pad_links(endpoint, path[0], net, grid, track_width))
            path_segments, path_vias = _path_objects(path, net, grid, track_width)
            net_segments.extend(path_segments)
            net_vias.extend(path_vias)
            tree.update(path)
            routed_members += 1
            for state in path:
                blocked.setdefault(state, set()).add(net)
            for via in path_vias:
                vx = _snap_index(float(via["at"][0]), grid)
                vy = _snap_index(float(via["at"][1]), grid)
                blocked.setdefault((vx, vy, 0), set()).add(net)
                blocked.setdefault((vx, vy, 1), set()).add(net)
        status = "routed" if not failed_members else ("partial" if routed_members > 1 else "unroutable")
        segments.extend(net_segments)
        vias.extend(net_vias)
        results.append(
            {
                "net": net,
                "status": status,
                "member_count": len(endpoints),
                "routed_member_count": routed_members,
                "failed_members": failed_members,
                "segment_count": len(net_segments),
                "via_count": len(net_vias),
            }
        )
    through_hole_pads = [endpoint for endpoint in connected if set(endpoint.layers) == set(LAYERS)]
    vias = [
        via
        for via in vias
        if not any(
            endpoint.net == str(via["net"])
            and math.hypot(
                endpoint.point[0] - float(via["at"][0]),
                endpoint.point[1] - float(via["at"][1]),
            )
            < min(endpoint.size) / 2
            for endpoint in through_hole_pads
        )
    ]
    return PCBRoutePlan(
        grid=grid,
        track_width=track_width,
        via_size=via_size,
        via_drill=via_drill,
        segments=tuple(segments),
        vias=tuple(vias),
        net_results=tuple(results),
    )
