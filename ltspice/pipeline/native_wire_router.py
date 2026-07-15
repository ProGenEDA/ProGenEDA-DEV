"""Wire-only LTspice router adapted from the KiCad planner principles.

The implementation keeps the useful KiCad ideas: grid routing, explicit body
obstacles, deterministic retry ordering, a temporary live state, and strict
post-route geometry checks. It deliberately removes terminal/label fallback.
Every non-ground endpoint must be a real direct WIRE endpoint in the output.
"""

from __future__ import annotations

from collections import defaultdict
import heapq
import math
from typing import Any, Iterable, Mapping


NATIVE_ROUTER_SCHEMA = "progen-ltspice-donor-native-wire-router/v1"


class NativeWireRouterError(ValueError):
    """A physical route cannot be proven without touching a body or foreign net."""


_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_SIDE_VECTORS = {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}

# ``FLAG X Y 0`` has a fixed stock LTspice ground glyph; it is not a rotatable
# symbol.  Give its native connection pin a vertical lead from above, then
# keep the glyph well below every stock body.  The conservative source band
# also avoids the nearby reference/value text which LTspice renders around a
# source body.
_GROUND_DROP_GRIDS = 5
_GROUND_COMPONENT_CLEARANCE_GRIDS = 3
_GROUND_SOURCE_CLEARANCE_GRIDS = 5


def _key(point: Iterable[int]) -> tuple[int, int]:
    values = list(point)
    return int(values[0]), int(values[1])


def _nodes(start: tuple[int, int], end: tuple[int, int], grid: int) -> list[tuple[int, int]]:
    """Return all grid nodes on an orthogonal direct wire, inclusive."""

    if start[0] != end[0] and start[1] != end[1]:
        raise NativeWireRouterError(f"Router emitted diagonal segment {start} -> {end}; beautifier routes orthogonally.")
    dx = 0 if start[0] == end[0] else (grid if end[0] > start[0] else -grid)
    dy = 0 if start[1] == end[1] else (grid if end[1] > start[1] else -grid)
    points = [start]
    current = start
    while current != end:
        current = (current[0] + dx, current[1] + dy)
        points.append(current)
    return points


def _segment_nodes(segment: Mapping[str, Any], grid: int) -> list[tuple[int, int]]:
    return _nodes(_key(segment["start"]), _key(segment["end"]), grid)


def _rect_points(rect: Mapping[str, Any], grid: int) -> set[tuple[int, int]]:
    left = int(math.floor(int(rect["left"]) / grid)) * grid
    right = int(math.ceil(int(rect["right"]) / grid)) * grid
    top = int(math.floor(int(rect["top"]) / grid)) * grid
    bottom = int(math.ceil(int(rect["bottom"]) / grid)) * grid
    return {
        (x, y)
        for x in range(left, right + grid, grid)
        for y in range(top, bottom + grid, grid)
        if int(rect["left"]) <= x <= int(rect["right"]) and int(rect["top"]) <= y <= int(rect["bottom"])
    }


def _outside_body(point: tuple[int, int], body: Mapping[str, Any]) -> bool:
    return not (
        int(body["left"]) <= point[0] <= int(body["right"])
        and int(body["top"]) <= point[1] <= int(body["bottom"])
    )


def _exit_point(pin: Mapping[str, Any], body: Mapping[str, Any], grid: int) -> tuple[int, int]:
    start = _key(pin["point"])
    dx, dy = _SIDE_VECTORS.get(str(pin.get("side") or "top").lower(), (0, -1))
    point = start
    for _ in range(8):
        point = (point[0] + dx * grid, point[1] + dy * grid)
        if _outside_body(point, body):
            return point
    raise NativeWireRouterError(f"Could not find a clear pin exit for {start}.")


def _ground_drop_x_positions(
    *,
    rail_left: int,
    rail_right: int,
    wanted: int,
    components: Mapping[str, Any],
    grid: int,
) -> list[int]:
    """Choose clear rail positions for native ground drops.

    The previous implementation put every ``FLAG 0`` on the first endpoint of
    the ground net.  With the common source-first layout that was typically a
    voltage source's negative pin, visually drawing the native ground triangle
    into the source.  A FLAG is allowed only for ground, so put it on a real
    wire endpoint below the return rail and prefer an x coordinate outside a
    generous source body/text band.
    """

    if rail_left > rail_right:
        raise NativeWireRouterError("Ground rail has invalid horizontal bounds.")
    source_bands: list[tuple[int, int]] = []
    for component in components.values():
        if not isinstance(component, Mapping):
            continue
        if str(component.get("type_id") or "") not in {"VOLTAGE_SOURCE", "CURRENT_SOURCE", "SIGNAL_SOURCE"}:
            continue
        body = component.get("body")
        if not isinstance(body, Mapping):
            continue
        clearance = grid * _GROUND_SOURCE_CLEARANCE_GRIDS
        source_bands.append((int(body["left"]) - clearance, int(body["right"]) + clearance))

    # Keep an end margin so a flag never hangs off the rail.  All generated
    # rail coordinates are grid aligned, but round defensively for explicit
    # donor-coordinate placements.
    lower = int(math.ceil((rail_left + grid * 2) / grid)) * grid
    upper = int(math.floor((rail_right - grid * 2) / grid)) * grid
    if lower > upper:
        lower, upper = rail_left, rail_right
    candidates = list(range(lower, upper + grid, grid))
    if not candidates:
        candidates = [rail_left]

    def source_clear(x: int) -> bool:
        return all(not left <= x <= right for left, right in source_bands)

    clear_candidates = [x for x in candidates if source_clear(x)]
    pool = clear_candidates or candidates
    chosen: list[int] = []
    for index in range(max(1, wanted)):
        # Even targets make multiple explicit ground components deterministic
        # without stacking their glyphs.  Pick a clear location closest to the
        # target and maintain at least four native grids between drops where
        # the rail has sufficient room.
        target = rail_left + (rail_right - rail_left) * (index + 1) / (max(1, wanted) + 1)
        separated = [x for x in pool if all(abs(x - existing) >= grid * 4 for existing in chosen)]
        ranked = separated or [x for x in pool if x not in chosen] or pool
        point = min(ranked, key=lambda x: (abs(x - target), x))
        chosen.append(point)
    return chosen


def _flag_is_visually_clear(
    point: tuple[int, int], component: Mapping[str, Any], *, grid: int
) -> bool:
    """Check FLAG 0 against the stock glyph's conservative visual envelope."""

    body = component.get("body")
    if not isinstance(body, Mapping):
        return True
    type_id = str(component.get("type_id") or "")
    clearance_grids = (
        _GROUND_SOURCE_CLEARANCE_GRIDS
        if type_id in {"VOLTAGE_SOURCE", "CURRENT_SOURCE", "SIGNAL_SOURCE"}
        else _GROUND_COMPONENT_CLEARANCE_GRIDS
    )
    clearance = grid * clearance_grids
    return not (
        int(body["left"]) - clearance <= point[0] <= int(body["right"]) + clearance
        and int(body["top"]) - clearance <= point[1] <= int(body["bottom"]) + clearance
    )


def _compress_path(points: list[tuple[int, int]], *, net: str, kind: str) -> list[dict[str, Any]]:
    if len(points) < 2:
        return []
    result: list[dict[str, Any]] = []
    start = points[0]
    previous = points[0]
    direction: tuple[int, int] | None = None
    for point in points[1:]:
        candidate = (0 if point[0] == previous[0] else (1 if point[0] > previous[0] else -1),
                     0 if point[1] == previous[1] else (1 if point[1] > previous[1] else -1))
        if direction is not None and candidate != direction:
            result.append({"net": net, "start": list(start), "end": list(previous), "kind": kind})
            start = previous
        direction = candidate
        previous = point
    result.append({"net": net, "start": list(start), "end": list(previous), "kind": kind})
    return [item for item in result if item["start"] != item["end"]]


def _axis(segment: Mapping[str, Any]) -> str:
    start, end = _key(segment["start"]), _key(segment["end"])
    if start[1] == end[1]:
        return "horizontal"
    if start[0] == end[0]:
        return "vertical"
    return "diagonal"


def _on_segment(point: tuple[int, int], segment: Mapping[str, Any]) -> bool:
    start, end = _key(segment["start"]), _key(segment["end"])
    axis = _axis(segment)
    if axis == "horizontal":
        return point[1] == start[1] and min(start[0], end[0]) <= point[0] <= max(start[0], end[0])
    if axis == "vertical":
        return point[0] == start[0] and min(start[1], end[1]) <= point[1] <= max(start[1], end[1])
    return False


def _strict_interior(point: tuple[int, int], segment: Mapping[str, Any]) -> bool:
    return _on_segment(point, segment) and point not in {_key(segment["start"]), _key(segment["end"])}


def _cross_allowed(point: tuple[int, int], direction: tuple[int, int], foreign: Mapping[str, Any]) -> bool:
    """Allow only donor-verified no-junction crosses, never a T or overlap.

    LTspice 26 netlist evidence confirms that a strict interior crossing of a
    horizontal and a vertical WIRE remains electrically separate. A WIRE
    endpoint touching another WIRE is a real junction, so it remains blocked.
    """

    if not _strict_interior(point, foreign):
        return False
    axis = _axis(foreign)
    candidate_axis = "horizontal" if direction[0] else "vertical"
    return axis in {"horizontal", "vertical"} and axis != candidate_axis


def _foreign_segment_index(
    foreign_segments: Iterable[Mapping[str, Any]], *, grid: int
) -> dict[tuple[int, int], list[Mapping[str, Any]]]:
    """Index already-routed foreign wire geometry by native grid point.

    A multi-terminal 43-component circuit may ask A* to inspect tens of
    thousands of candidate points.  Scanning every earlier segment at each
    candidate made a valid, dense circuit needlessly quadratic in route
    history.  The index preserves the exact crossing rules below while making
    a candidate's foreign-wire lookup local to that point.
    """

    indexed: dict[tuple[int, int], list[Mapping[str, Any]]] = defaultdict(list)
    for segment in foreign_segments:
        for point in _segment_nodes(segment, grid):
            indexed[point].append(segment)
    return indexed


def _astar(
    start: tuple[int, int],
    targets: set[tuple[int, int]],
    *,
    blocked: set[tuple[int, int]],
    foreign_segments_at: Mapping[tuple[int, int], list[Mapping[str, Any]]],
    bounds: tuple[int, int, int, int],
    grid: int,
    maximum_expansions: int,
) -> list[tuple[int, int]]:
    """Bounded Manhattan A-star adapted from the KiCad wire-planner strategy."""

    if start in targets:
        return [start]
    min_x, max_x, min_y, max_y = bounds
    frontier: list[tuple[int, int, int, int, tuple[int, int], tuple[int, int] | None]] = []
    serial = 0
    # cost, heuristic tie-break, serial, path length, point, incoming direction
    heapq.heappush(frontier, (0, 0, serial, 0, start, None))
    start_state = (start, None)
    came_from: dict[
        tuple[tuple[int, int], tuple[int, int] | None],
        tuple[tuple[int, int], tuple[int, int] | None] | None,
    ] = {start_state: None}
    best_cost: dict[tuple[tuple[int, int], tuple[int, int] | None], int] = {start_state: 0}
    expansions = 0

    def heuristic(point: tuple[int, int]) -> int:
        return min(abs(point[0] - goal[0]) + abs(point[1] - goal[1]) for goal in targets)

    while frontier:
        _, _, _, cost, current, incoming = heapq.heappop(frontier)
        if current in targets:
            path: list[tuple[int, int]] = []
            node: tuple[tuple[int, int], tuple[int, int] | None] | None = (current, incoming)
            while node is not None:
                path.append(node[0])
                node = came_from[node]
            return list(reversed(path))
        expansions += 1
        if expansions > maximum_expansions:
            break
        for dx, dy in _DIRECTIONS:
            direction = (dx, dy)
            foreign_at_current = foreign_segments_at.get(current, [])
            if incoming is not None and foreign_at_current:
                # Once a route enters a strict cross, force it straight
                # through. Turning there would serialize a WIRE endpoint on
                # another net and create a real LTspice junction.
                if any(_cross_allowed(current, incoming, segment) for segment in foreign_at_current) and direction != incoming:
                    continue
            next_point = (current[0] + dx * grid, current[1] + dy * grid)
            if not (min_x <= next_point[0] <= max_x and min_y <= next_point[1] <= max_y):
                continue
            if next_point in blocked and next_point not in targets:
                continue
            foreign_at_next = foreign_segments_at.get(next_point, [])
            if foreign_at_next and not all(_cross_allowed(next_point, direction, segment) for segment in foreign_at_next):
                continue
            turn_cost = grid // 4 if incoming is not None and direction != incoming else 0
            candidate_cost = cost + grid + turn_cost
            next_state = (next_point, direction)
            if candidate_cost >= best_cost.get(next_state, 10**18):
                continue
            best_cost[next_state] = candidate_cost
            came_from[next_state] = (current, incoming)
            serial += 1
            score = candidate_cost + heuristic(next_point)
            heapq.heappush(frontier, (score, heuristic(next_point), serial, candidate_cost, next_point, direction))
    raise NativeWireRouterError(
        f"No body-safe physical route from {start} to its same-net wire tree "
        f"after {expansions} A-star expansions (limit {maximum_expansions})."
    )


def _contact(segment: Mapping[str, Any], body: Mapping[str, Any]) -> tuple[str, tuple[int, int] | None] | None:
    start = _key(segment["start"])
    end = _key(segment["end"])
    left, right = int(body["left"]), int(body["right"])
    top, bottom = int(body["top"]), int(body["bottom"])
    if start[1] == end[1]:
        y = start[1]
        if not top <= y <= bottom:
            return None
        low, high = max(min(start[0], end[0]), left), min(max(start[0], end[0]), right)
        if low > high:
            return None
        return ("point", (low, y)) if low == high else ("overlap", None)
    if start[0] == end[0]:
        x = start[0]
        if not left <= x <= right:
            return None
        low, high = max(min(start[1], end[1]), top), min(max(start[1], end[1]), bottom)
        if low > high:
            return None
        return ("point", (x, low)) if low == high else ("overlap", None)
    return ("diagonal", None)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[tuple[int, int], tuple[int, int]] = {}

    def find(self, point: tuple[int, int]) -> tuple[int, int]:
        self.parent.setdefault(point, point)
        if self.parent[point] != point:
            self.parent[point] = self.find(self.parent[point])
        return self.parent[point]

    def union(self, left: tuple[int, int], right: tuple[int, int]) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def validate_native_wire_routes(
    native_circuit: Mapping[str, Any], placement: Mapping[str, Any], routes: Mapping[str, Any]
) -> dict[str, Any]:
    """Prove every endpoint joins its intended physical tree without body contact."""

    grid = int(placement["grid"])
    components = placement.get("components")
    if not isinstance(components, Mapping):
        raise NativeWireRouterError("placement.components must be an object.")
    wires = routes.get("wire_segments")
    if not isinstance(wires, list):
        raise NativeWireRouterError("routes.wire_segments must be an array.")
    by_net: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    violations: list[str] = []
    for raw in wires:
        if not isinstance(raw, Mapping):
            violations.append("Wire record is not an object.")
            continue
        net = str(raw.get("net") or "")
        try:
            points = _segment_nodes(raw, grid)
        except NativeWireRouterError as exc:
            violations.append(str(exc))
            continue
        if len(points) < 2:
            violations.append(f"{net} has a zero-length wire.")
            continue
        by_net[net].append(raw)

    # A strict horizontal/vertical interior crossing is intentionally allowed:
    # LTspice 26 netlist evidence shows it does not form a junction. Every
    # endpoint touch, T, or collinear overlap remains a forbidden short.
    for index, first in enumerate(wires):
        if not isinstance(first, Mapping):
            continue
        for second in wires[index + 1 :]:
            if not isinstance(second, Mapping) or str(first.get("net")) == str(second.get("net")):
                continue
            first_axis, second_axis = _axis(first), _axis(second)
            if first_axis == "horizontal" and second_axis == "vertical":
                point = (_key(second["start"])[0], _key(first["start"])[1])
            elif first_axis == "vertical" and second_axis == "horizontal":
                point = (_key(first["start"])[0], _key(second["start"])[1])
            else:
                point = None
            if point is not None and _on_segment(point, first) and _on_segment(point, second):
                if _strict_interior(point, first) and _strict_interior(point, second):
                    continue
                violations.append(f"Different-net wire endpoint touches at {point}: {first.get('net')}, {second.get('net')}.")
                continue
            if first_axis == second_axis and first_axis in {"horizontal", "vertical"}:
                shared = set(_segment_nodes(first, grid)) & set(_segment_nodes(second, grid))
                if shared:
                    violations.append(
                        f"Different-net {first_axis} wires overlap/touch at {sorted(shared)[0]}: "
                        f"{first.get('net')}, {second.get('net')}."
                    )

    # A horizontal return rail is structural routing, not decoration.  Both
    # ends must terminate at an actual same-net branch or a ground drop.  This
    # prevents the otherwise harmless-but-ugly stubs that used to extend past
    # the outermost return connection in generated screenshots.
    for rail in wires:
        if not isinstance(rail, Mapping) or str(rail.get("kind") or "") != "ground_rail":
            continue
        net = str(rail.get("net") or "")
        for point in (_key(rail["start"]), _key(rail["end"])):
            attached = any(
                other is not rail
                and isinstance(other, Mapping)
                and str(other.get("net") or "") == net
                and point in {_key(other["start"]), _key(other["end"])}
                for other in wires
            )
            if not attached:
                violations.append(f"Ground rail endpoint {point} has no physical same-net attachment.")

    for ref, component in components.items():
        if not isinstance(component, Mapping):
            continue
        pins = component.get("pins")
        allowed = {
            _key(pin["point"])
            for pin in pins.values()
            if isinstance(pins, Mapping) and isinstance(pin, Mapping)
        }
        for wire in wires:
            if not isinstance(wire, Mapping):
                continue
            found = _contact(wire, component["body"])
            if found is None:
                continue
            kind, point = found
            start, end = _key(wire["start"]), _key(wire["end"])
            if kind == "point" and point in allowed and point in {start, end}:
                continue
            violations.append(f"{wire.get('net')} wire touches {ref} body ({kind}).")

    nets = native_circuit.get("nets")
    if not isinstance(nets, Mapping):
        raise NativeWireRouterError("native circuit.nets must be an object.")
    connected: dict[str, list[str]] = {}
    for net, raw_net in nets.items():
        details = raw_net if isinstance(raw_net, Mapping) else {}
        members = list(details.get("members") or [])
        union = _UnionFind()
        points: set[tuple[int, int]] = set()
        for wire in by_net.get(str(net), []):
            nodes = _segment_nodes(wire, grid)
            points.update(nodes)
            for left, right in zip(nodes, nodes[1:]):
                union.union(left, right)
        endpoint_points: list[tuple[int, int]] = []
        for endpoint in members:
            ref, pin = str(endpoint).rsplit(".", 1)
            component = components.get(ref)
            if not isinstance(component, Mapping) or pin not in component.get("pins", {}):
                violations.append(f"{net} cannot resolve placed endpoint {endpoint}.")
                continue
            point = _key(component["pins"][pin]["point"])
            endpoint_points.append(point)
            if point not in points:
                violations.append(f"{endpoint} has no direct physical WIRE endpoint.")
        if endpoint_points:
            root = union.find(endpoint_points[0])
            if any(union.find(point) != root for point in endpoint_points[1:]):
                violations.append(f"{net} does not form one physical connected wire tree.")
        connected[str(net)] = [f"{point[0]},{point[1]}" for point in endpoint_points]

    flags = routes.get("ground_flags") or []
    for flag in flags:
        point = _key(flag["point"] if isinstance(flag, Mapping) else flag)
        if isinstance(flag, Mapping) and str(flag.get("name") or "0") != "0":
            violations.append(f"Non-ground FLAG {flag.get('name')!r} is forbidden.")
        if not any(point in {_key(wire["start"]), _key(wire["end"])} for wire in wires if isinstance(wire, Mapping)):
            violations.append(f"Ground FLAG at {point} has no physical wire endpoint.")
        if any(
            isinstance(component, Mapping) and not _flag_is_visually_clear(point, component, grid=grid)
            for component in components.values()
        ):
            violations.append(
                f"Ground FLAG at {point} is too close to a stock component body or source attribute band."
            )
    return {
        "schema": NATIVE_ROUTER_SCHEMA,
        "stage": "donor_native_wire_validator",
        "ok": not violations,
        "errors": violations,
        "net_endpoints": connected,
        "wire_count": len(wires),
        "ground_flag_count": len(flags),
        "terminal_fallback": "forbidden",
    }


def route_native_wires(
    native_circuit: Mapping[str, Any],
    placement: Mapping[str, Any],
    *,
    max_astar_expansions: int = 250000,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Route every canonical net through physical body-safe ASC wire segments."""

    grid = int(placement["grid"])
    components = placement.get("components")
    nets = native_circuit.get("nets")
    if not isinstance(components, Mapping) or not isinstance(nets, Mapping):
        raise NativeWireRouterError("Native placement and circuit must contain components/nets.")
    sheet = placement.get("sheet") if isinstance(placement.get("sheet"), Mapping) else {}
    blocked: set[tuple[int, int]] = set()
    all_pin_points: set[tuple[int, int]] = set()
    all_exit_points: set[tuple[int, int]] = set()
    for component in components.values():
        if not isinstance(component, Mapping):
            continue
        blocked.update(_rect_points(component["body"], grid))
        pins = component.get("pins")
        if isinstance(pins, Mapping):
            for pin in pins.values():
                if not isinstance(pin, Mapping):
                    continue
                all_pin_points.add(_key(pin["point"]))
                all_exit_points.add(_exit_point(pin, component["body"], grid))

    bodies = [item["body"] for item in components.values() if isinstance(item, Mapping)]
    if not bodies:
        raise NativeWireRouterError("Native placement has no physical stock-symbol bodies to route.")
    # Do not impose a synthetic left/top limit on an ASC. Donors prove that
    # negative coordinates are legal, and an explicit ``ltspice_at`` may be
    # farther left/up than the small baseline sheet. Derive the A* field from
    # real placed geometry instead; the sheet remains a useful lower bound on
    # the visible positive side, while the physical geometry owns all other
    # limits. This retains a finite search field without silently rejecting a
    # valid donor-grid placement before routing begins.
    margin = grid * 64
    min_x = min(-margin, min(int(body["left"]) for body in bodies) - margin)
    max_x = max(int(sheet.get("width", 880)) + margin, max(int(body["right"]) for body in bodies) + margin)
    min_y = min(-margin, min(int(body["top"]) for body in bodies) - margin)
    max_y = max(int(sheet.get("height", 680)) + margin, max(int(body["bottom"]) for body in bodies) + margin)
    rail_y = max(int(body["bottom"]) for body in bodies) + grid * 4
    rail_left = min(int(body["left"]) for body in bodies) - grid * 4
    rail_right = max(int(body["right"]) for body in bodies) + grid * 4
    max_y = max(max_y, rail_y + margin)

    occupied: dict[str, set[tuple[int, int]]] = defaultdict(set)
    all_segments: list[dict[str, Any]] = []
    ground_flags: list[dict[str, Any]] = []
    net_reports: dict[str, Any] = {}
    # Build the dedicated return rail first. Signal routing reserves all pin
    # exits and treats that rail as a foreign obstacle, so it cannot later
    # turn a ground branch into a trapped terminal-shaped gap.
    ordered_nets = sorted(nets, key=lambda item: (0 if bool(nets[item].get("is_ground")) else 1, str(item)))
    for net in ordered_nets:
        details = nets[net] if isinstance(nets[net], Mapping) else {}
        members = list(details.get("members") or [])
        endpoint_data: list[tuple[str, tuple[int, int], tuple[int, int]]] = []
        for endpoint in members:
            ref, pin = str(endpoint).rsplit(".", 1)
            component = components.get(ref)
            if not isinstance(component, Mapping):
                raise NativeWireRouterError(f"{net} references unplaced component {ref}.")
            pin_data = component.get("pins", {}).get(pin)
            if not isinstance(pin_data, Mapping):
                raise NativeWireRouterError(f"{net} references unplaced pin {endpoint}.")
            pin_point = _key(pin_data["point"])
            exit_point = _exit_point(pin_data, component["body"], grid)
            endpoint_data.append((str(endpoint), pin_point, exit_point))
        if not endpoint_data:
            continue

        segments: list[dict[str, Any]] = []
        for endpoint, pin_point, exit_point in endpoint_data:
            segments.append({"net": str(net), "start": list(pin_point), "end": list(exit_point), "kind": "pin_exit", "endpoint": endpoint})
        foreign_segments = [
            segment for segment in all_segments
            if str(segment.get("net") or "") != str(net)
        ]
        foreign_segments_at = _foreign_segment_index(foreign_segments, grid=grid)
        own_pin_points = {item[1] for item in endpoint_data}
        own_exit_points = {item[2] for item in endpoint_data}
        # A pin exit is reserved even before its net is routed. Otherwise a
        # signal tree can consume the one clear grid point a later ground
        # stub needs, creating a hidden short at a component boundary.
        blocked_for_net = (blocked | (all_pin_points - own_pin_points) | (all_exit_points - own_exit_points)) - own_exit_points
        is_ground = bool(details.get("is_ground"))
        rail_contacts: set[tuple[int, int]] = set()
        if is_ground:
            # This initial span is only an A* target field.  Once all return
            # branches have joined it, trim it to real connection points so
            # the emitted ASC never contains visual rail overhangs.
            rail = {"net": str(net), "start": [rail_left, rail_y], "end": [rail_right, rail_y], "kind": "ground_rail"}
            segments.append(rail)
            tree_nodes = set(_segment_nodes(rail, grid))
            endpoint_routes = endpoint_data
            route_bounds = (min_x, max_x, min_y, max(max_y, rail_y + grid * 8))
        else:
            tree_nodes = {endpoint_data[0][2]}
            endpoint_routes = endpoint_data[1:]
            # Signals cannot consume the reserved ground corridor.
            route_bounds = (min_x, max_x, min_y, min(max_y, rail_y - grid * 2))
        for endpoint, _pin_point, exit_point in endpoint_routes:
            path = _astar(
                exit_point,
                tree_nodes,
                blocked=blocked_for_net,
                foreign_segments_at=foreign_segments_at,
                bounds=route_bounds,
                grid=grid,
                maximum_expansions=max_astar_expansions,
            )
            tree_nodes.update(path)
            segments.extend(_compress_path(path, net=str(net), kind="tree"))
            if is_ground and path[-1][1] == rail_y:
                rail_contacts.add(path[-1])

        if bool(details.get("is_ground")):
            # A native FLAG has no orientation record.  Its connection pin is
            # therefore deliberately fed from above through a long enough
            # physical return lead, instead of being stamped directly on a
            # component pin (especially a source's negative pin).
            ground_refs = list(details.get("ground_refs") or [])
            wanted = max(1, len(ground_refs))
            flag_y = rail_y + grid * _GROUND_DROP_GRIDS
            for index, x in enumerate(
                _ground_drop_x_positions(
                    rail_left=rail_left,
                    rail_right=rail_right,
                    wanted=wanted,
                    components=components,
                    grid=grid,
                )
            ):
                flag_point = (x, flag_y)
                drop = {
                    "net": str(net),
                    "start": [x, rail_y],
                    "end": list(flag_point),
                    "kind": "ground_drop",
                }
                segments.append(drop)
                tree_nodes.update(_segment_nodes(drop, grid))
                rail_contacts.add((x, rail_y))
                flag = {
                    "point": list(flag_point),
                    "name": "0",
                    "source_ref": ground_refs[index % len(ground_refs)] if ground_refs else None,
                    "attachment": "return_rail_downward_drop",
                }
                if flag["point"] not in [existing["point"] for existing in ground_flags]:
                    ground_flags.append(flag)
            if not rail_contacts:
                raise NativeWireRouterError(f"Ground net {net} has no physical return-rail connection.")
            rail_xs = sorted(point[0] for point in rail_contacts)
            if rail_xs[0] == rail_xs[-1]:
                # A single return branch and the ground drop meet at one
                # physical junction, so a horizontal rail would be a zero
                # length/dangling decorative record.  Omit it entirely.
                segments.remove(rail)
            else:
                rail["start"] = [rail_xs[0], rail_y]
                rail["end"] = [rail_xs[-1], rail_y]
        all_segments.extend(segments)
        for segment in segments:
            occupied[str(net)].update(_segment_nodes(segment, grid))
        net_reports[str(net)] = {
            "members": members,
            "segment_count": len(segments),
            "junction_count": len(tree_nodes),
            "mode": "physical_wire_tree",
        }

    routes = {
        "schema": NATIVE_ROUTER_SCHEMA,
        "stage": "donor_native_wire_router",
        "wire_segments": all_segments,
        "ground_flags": ground_flags,
        "nets": net_reports,
        "terminal_fallback": "forbidden",
        "label_fallback": "forbidden",
    }
    validation = validate_native_wire_routes(native_circuit, placement, routes)
    if not validation["ok"]:
        raise NativeWireRouterError("; ".join(validation["errors"]))
    report = dict(validation)
    report["stage"] = "donor_native_wire_router"
    report["net_reports"] = net_reports
    return routes, report


def donor_native_recipe(
    native_circuit: Mapping[str, Any], placement: Mapping[str, Any], routes: Mapping[str, Any]
) -> dict[str, Any]:
    """Create the writer's internal recipe from placed/routed shared JSON facts."""

    components = placement.get("components")
    if not isinstance(components, Mapping):
        raise NativeWireRouterError("placement.components must be an object.")
    recipe_components = [
        {
            "type": item["type_id"],
            "ref": item["ref"],
            "at": list(item["origin"]),
            "orientation": item["orientation"],
            "properties": dict(item.get("properties") or {}),
        }
        for item in components.values()
        if isinstance(item, Mapping)
    ]
    raw_directives = list(native_circuit.get("directives") or [])
    sheet = dict(placement.get("sheet") or {"number": 1, "width": 880, "height": 680})
    grid = int(placement.get("grid") or 16)
    route_segments = list(routes.get("wire_segments") or [])
    occupied_x = [
        int(point)
        for segment in route_segments if isinstance(segment, Mapping)
        for point in (segment.get("start", [0, 0])[0], segment.get("end", [0, 0])[0])
    ]
    occupied_y = [
        int(point)
        for segment in route_segments if isinstance(segment, Mapping)
        for point in (segment.get("start", [0, 0])[1], segment.get("end", [0, 0])[1])
    ]
    body_bottom = [int(item["body"]["bottom"]) for item in components.values() if isinstance(item, Mapping)]
    directive_y = max(body_bottom + occupied_y + [grid * 8]) + grid * 4
    directives = []
    for index, text in enumerate(raw_directives):
        directives.append({"at": [grid * 4, directive_y + index * grid * 2], "text": str(text)})
    if directives:
        sheet["height"] = max(int(sheet["height"]), directive_y + len(directives) * grid * 3)
    if occupied_x:
        sheet["width"] = max(int(sheet["width"]), max(occupied_x) + grid * 8)
    if occupied_y:
        sheet["height"] = max(int(sheet["height"]), max(occupied_y) + grid * 8)
    return {
        "schema": "progen-ltspice-native-recipe/v1",
        "circuit_id": str(native_circuit.get("circuit_id") or "ltspice_native"),
        "sheet": sheet,
        "components": recipe_components,
        "wires": [[*item["start"], *item["end"]] for item in routes.get("wire_segments") or []],
        "ground_flags": [list(item["point"]) for item in routes.get("ground_flags") or []],
        "directives": directives,
    }
