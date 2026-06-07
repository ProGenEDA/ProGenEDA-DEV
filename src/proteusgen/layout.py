"""Deterministic topology-aware placement for donor-safe Proteus generators.

The planner operates on CircuitIR-like JSON and returns coordinates only. It
does not parse or mutate Proteus binary records and it never creates routed
wire or junction objects.
"""

from __future__ import annotations

import copy
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Literal

LayoutStrategy = Literal["beautify", "manual", "legacy"]

# The accepted donor records remain comfortably separated at this denser grid.
# Source stacking keeps its larger independent clearance below.
X_SPACING = 3_175_000
Y_SPACING = 2_032_000
SOURCE_Y_SPACING = 5_080_000
LEGACY_SPACING = 2_540_000
WRAP_SLOTS = 7
ORIGIN_X = -7_366_000
ORIGIN_Y = 5_080_000


class LayoutError(ValueError):
    """Raised when a requested layout cannot be planned safely."""


@dataclass(frozen=True)
class Position:
    x: int
    y: int

    def as_dict(self) -> dict[str, int]:
        return {"x": self.x, "y": self.y}


@dataclass(frozen=True)
class LayoutEdge:
    ref: str
    kind: str
    left: str
    right: str
    order: int
    group: int | None = None
    legacy_position: Position | None = None


@dataclass(frozen=True)
class LayoutSource:
    ref: str
    kind: str
    positive: str
    negative: str
    order: int


@dataclass(frozen=True)
class LayoutConfig:
    strategy: LayoutStrategy
    direction: str
    component_positions: dict[str, Position]
    source_positions: dict[str, Position]
    inferred: bool = False


@dataclass(frozen=True)
class LayoutPlan:
    route: str
    strategy: LayoutStrategy
    direction: str
    component_positions: dict[str, Position]
    source_positions: dict[str, Position]
    node_positions: dict[str, Position]
    node_levels: dict[str, int]
    bounds: dict[str, int]
    wrap_count: int
    adjustment_count: int
    overlaps: tuple[dict[str, Any], ...]
    motifs: tuple[dict[str, Any], ...]
    experimental: bool
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "layout_version": "proteusgen-layout/v0.2",
            "route": self.route,
            "strategy": self.strategy,
            "direction": self.direction,
            "experimental": self.experimental,
            "component_positions": {
                ref: position.as_dict() for ref, position in sorted(self.component_positions.items())
            },
            "source_positions": {
                ref: position.as_dict() for ref, position in sorted(self.source_positions.items())
            },
            "node_positions": {
                node: position.as_dict() for node, position in sorted(self.node_positions.items())
            },
            "node_levels": dict(sorted(self.node_levels.items())),
            "bounds": self.bounds,
            "wrap_count": self.wrap_count,
            "adjustment_count": self.adjustment_count,
            "overlap_count": len(self.overlaps),
            "overlaps": list(self.overlaps),
            "motifs": list(self.motifs),
            "notes": list(self.notes),
        }


@dataclass(frozen=True)
class LayoutApplication:
    payload: dict[str, Any]
    plan: LayoutPlan


def _position_map(raw: Any, field: str) -> dict[str, Position]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise LayoutError(f"{field} must be an object.")
    out: dict[str, Position] = {}
    for ref, value in raw.items():
        if not isinstance(ref, str) or not isinstance(value, dict):
            raise LayoutError(f"{field} entries must map string references to coordinate objects.")
        x = value.get("x")
        y = value.get("y")
        if type(x) is not int or type(y) is not int:
            raise LayoutError(f"{field}.{ref} requires integer x and y coordinates.")
        out[ref] = Position(x, y)
    return out


def parse_layout_config(payload: dict[str, Any], override: str | None = None) -> LayoutConfig:
    raw = payload.get("layout", {})
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise LayoutError("layout must be an object.")

    requested = override or raw.get("strategy")
    inferred = requested is None
    if requested is None:
        has_positions = bool(raw.get("component_positions")) or bool(raw.get("source_positions"))
        strategy = "manual" if has_positions else "beautify"
    else:
        strategy = requested
    if strategy not in {"beautify", "manual", "legacy"}:
        raise LayoutError("layout.strategy must be beautify, manual, or legacy.")
    direction = raw.get("direction", "left_to_right")
    if direction != "left_to_right":
        raise LayoutError("The beautifier currently supports direction=left_to_right only.")
    return LayoutConfig(
        strategy=strategy,
        direction=direction,
        component_positions=_position_map(raw.get("component_positions"), "layout.component_positions"),
        source_positions=_position_map(raw.get("source_positions"), "layout.source_positions"),
        inferred=inferred,
    )


def detect_route(payload: dict[str, Any]) -> str:
    schema = payload.get("schema_version")
    if schema == "proteus-circuit-ir/v0.1":
        return "resistor"
    if schema == "proteus-mixed-passive-ir/v0.1":
        return "mixed-passive"
    if schema == "mixed-rcl-circuit-ir/v0.1":
        return "mixed-rcl"
    if schema == "source-driven-rcl-circuit-ir/v0.1":
        return "source-driven"
    raise LayoutError(f"Unsupported CircuitIR schema for layout planning: {schema!r}.")


def _two_char(prefix: str, index: int) -> str:
    if not 1 <= index <= 35:
        raise LayoutError("The current two-character reference range supports indexes 1..35.")
    return f"{prefix}{index}" if index <= 9 else f"{prefix}{chr(ord('A') + index - 10)}"


def _raw_component_edges(payload: dict[str, Any]) -> list[LayoutEdge]:
    edges: list[LayoutEdge] = []
    for order, component in enumerate(payload.get("components", []), start=1):
        if not isinstance(component, dict):
            continue
        nodes = component.get("nodes", [])
        if not isinstance(nodes, list) or len(nodes) != 2:
            continue
        ref = component.get("ref")
        kind = component.get("type")
        if all(isinstance(value, str) for value in (ref, kind, nodes[0], nodes[1])):
            edges.append(LayoutEdge(ref, kind, nodes[0], nodes[1], order))
    return edges


def _group_edges(payload: dict[str, Any]) -> list[LayoutEdge]:
    edges: list[LayoutEdge] = []
    ref_counts = {"R": 0, "C": 0, "L": 0}
    order = 0
    for unit_index, group in enumerate(payload.get("groups", []), start=1):
        if not isinstance(group, dict):
            continue
        mode = group.get("mode")
        start = group.get("start")
        end = group.get("end")
        if not all(isinstance(value, str) for value in (mode, start, end)):
            continue
        internal_a = _two_char("A", unit_index)
        internal_b = _two_char("B", unit_index)
        if mode == "RCL":
            logical = (("R", start, internal_a), ("C", internal_a, internal_b), ("L", internal_b, end))
        elif mode == "RC":
            logical = (("R", start, internal_a), ("C", internal_a, end))
        elif mode == "LC":
            logical = (("C", start, internal_a), ("L", internal_a, end))
        elif mode == "RL":
            logical = (("R", start, internal_a), ("L", internal_a, end))
        elif mode in {"R", "C", "L"}:
            logical = ((mode, start, end),)
        else:
            continue

        col = (unit_index - 1) % 3
        row = (unit_index - 1) // 3
        base_x = -7_366_000 + col * 10_160_000
        base_y = 5_080_000 - row * 6_096_000
        legacy_by_kind = {
            "R": Position(base_x, base_y),
            "C": Position(base_x, base_y - 2_540_000),
            "L": Position(base_x + 3_810_000, base_y - 2_540_000),
        }
        for kind, left, right in logical:
            ref_counts[kind] += 1
            order += 1
            ref = _two_char(kind, ref_counts[kind])
            edges.append(
                LayoutEdge(
                    ref=ref,
                    kind={"R": "RESISTOR", "C": "CAPACITOR", "L": "INDUCTOR"}[kind],
                    left=left,
                    right=right,
                    order=order,
                    group=unit_index,
                    legacy_position=legacy_by_kind[kind],
                )
            )
    return edges


def _sources(payload: dict[str, Any]) -> list[LayoutSource]:
    out: list[LayoutSource] = []
    for order, source in enumerate(payload.get("sources", []), start=1):
        if not isinstance(source, dict):
            continue
        values = (source.get("ref"), source.get("kind"), source.get("positive"), source.get("negative"))
        if all(isinstance(value, str) for value in values):
            out.append(LayoutSource(values[0], values[1], values[2], values[3], order))
    return out


def normalize_payload(payload: dict[str, Any]) -> tuple[str, list[LayoutEdge], list[LayoutSource], list[str], list[str]]:
    route = detect_route(payload)
    edges = _raw_component_edges(payload) if route in {"resistor", "mixed-passive"} else _group_edges(payload)
    sources = _sources(payload)

    roots: list[str] = []
    sinks: list[str] = []
    for node in payload.get("nodes", []):
        if not isinstance(node, dict) or not isinstance(node.get("id"), str):
            continue
        if node.get("kind") == "power" or node["id"] == "V0":
            roots.append(node["id"])
        if node.get("kind") == "ground" or node["id"] == "G0":
            sinks.append(node["id"])
    roots.extend(source.positive for source in sources)
    sinks.extend(source.negative for source in sources)
    if not roots and edges:
        roots.append(edges[0].left)
    if not sinks and edges:
        sinks.append(edges[-1].right)
    return route, edges, sources, list(dict.fromkeys(roots)), list(dict.fromkeys(sinks))


def _stretch_axis(values: list[int], minimum: int, *, descending: bool = False) -> dict[int, int]:
    unique = sorted(set(values), reverse=descending)
    if len(unique) < 2:
        return {value: value for value in unique}
    ordered = sorted(unique)
    if all(right - left >= minimum for left, right in zip(ordered, ordered[1:])):
        return {value: value for value in unique}
    anchor = unique[0]
    return {
        value: anchor - index * minimum if descending else anchor + index * minimum
        for index, value in enumerate(unique)
    }


def _legacy_positions(
    route: str,
    edges: list[LayoutEdge],
    requested: dict[str, Position],
) -> dict[str, Position]:
    if edges and all(edge.legacy_position is not None for edge in edges):
        return {edge.ref: edge.legacy_position for edge in edges if edge.legacy_position is not None}
    raw = {
        edge.ref: requested.get(
            edge.ref,
            Position(-6_350_000 + ((edge.order - 1) % WRAP_SLOTS) * LEGACY_SPACING, 5_080_000 - ((edge.order - 1) // WRAP_SLOTS) * LEGACY_SPACING),
        )
        for edge in edges
    }
    x_map = _stretch_axis([position.x for position in raw.values()], LEGACY_SPACING)
    y_map = _stretch_axis([position.y for position in raw.values()], LEGACY_SPACING, descending=True)
    out: dict[str, Position] = {}
    used: set[tuple[int, int]] = set()
    for edge in edges:
        position = raw[edge.ref]
        x = x_map[position.x]
        y = y_map[position.y]
        if route == "mixed-passive":
            while (x, y) in used:
                x += LEGACY_SPACING
        used.add((x, y))
        out[edge.ref] = Position(x, y)
    return out


def _node_levels(edges: list[LayoutEdge], roots: list[str]) -> dict[str, int]:
    outgoing: dict[str, list[str]] = defaultdict(list)
    adjacency: dict[str, list[str]] = defaultdict(list)
    indegree: dict[str, int] = defaultdict(int)
    node_order: dict[str, int] = {}
    for edge in edges:
        node_order.setdefault(edge.left, len(node_order))
        node_order.setdefault(edge.right, len(node_order))
        outgoing[edge.left].append(edge.right)
        adjacency[edge.left].append(edge.right)
        adjacency[edge.right].append(edge.left)
        indegree[edge.right] += 1
        indegree.setdefault(edge.left, 0)

    levels: dict[str, int] = {}
    queue: deque[str] = deque()
    for index, root in enumerate(roots):
        # Always preserve the primary power/source root. Additional source
        # positives start a lane only when they are not already downstream of
        # another passive path.
        if index > 0 and indegree.get(root, 0) > 0:
            continue
        if root in adjacency and root not in levels:
            levels[root] = 0
            queue.append(root)
    if not queue and node_order:
        first = min(node_order, key=node_order.get)
        levels[first] = 0
        queue.append(first)

    def expand() -> None:
        while queue:
            node = queue.popleft()
            for neighbor in sorted(outgoing[node], key=lambda item: node_order[item]):
                if neighbor not in levels:
                    levels[neighbor] = levels[node] + 1
                    queue.append(neighbor)

    expand()
    while len(levels) < len(node_order):
        remaining = [node for node in node_order if node not in levels]
        attached = [
            node
            for node in remaining
            if any(neighbor in levels for neighbor in adjacency[node])
        ]
        node = min(attached or remaining, key=node_order.get)
        neighbor_levels = [levels[neighbor] for neighbor in adjacency[node] if neighbor in levels]
        levels[node] = min(neighbor_levels) + 1 if neighbor_levels else max(levels.values(), default=-1) + 1
        queue.append(node)
        expand()
    return levels


def _node_lanes(edges: list[LayoutEdge], levels: dict[str, int]) -> dict[str, int]:
    first_seen: dict[str, int] = {}
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        first_seen.setdefault(edge.left, edge.order)
        first_seen.setdefault(edge.right, edge.order)
        adjacency[edge.left].append(edge.right)
        adjacency[edge.right].append(edge.left)
    by_level: dict[int, list[str]] = defaultdict(list)
    for node, level in levels.items():
        by_level[level].append(node)

    lanes: dict[str, int] = {}
    for level in sorted(by_level):
        nodes = by_level[level]

        def key(node: str) -> tuple[float, int, str]:
            previous = [lanes[item] for item in adjacency[node] if levels[item] < level and item in lanes]
            barycenter = sum(previous) / len(previous) if previous else float(first_seen[node])
            return barycenter, first_seen[node], node

        for rank, node in enumerate(sorted(nodes, key=key)):
            lanes[node] = rank
    return lanes


def _nearest_free(candidate: int, occupied: set[int]) -> int:
    if candidate not in occupied:
        return candidate
    distance = 1
    while True:
        for option in (candidate + distance, candidate - distance):
            if option >= 0 and option not in occupied:
                return option
        distance += 1


def _cycle_edge_refs(edges: list[LayoutEdge]) -> tuple[str, ...]:
    parent: dict[str, str] = {}

    def find(node: str) -> str:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: str, right: str) -> bool:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return False
        if left_root < right_root:
            parent[right_root] = left_root
        else:
            parent[left_root] = right_root
        return True

    cycle_refs: list[str] = []
    for edge in sorted(edges, key=lambda item: (item.order, item.ref)):
        if not union(edge.left, edge.right):
            cycle_refs.append(edge.ref)
    return tuple(cycle_refs)


def _beautified_positions(
    edges: list[LayoutEdge],
    roots: list[str],
) -> tuple[dict[str, Position], dict[str, Position], dict[str, int], int]:
    levels = _node_levels(edges, roots)
    node_lanes = _node_lanes(edges, levels)
    cycle_rank = {
        ref: rank
        for rank, ref in enumerate(_cycle_edge_refs(edges))
    }
    cycle_lane_base = max(node_lanes.values(), default=0) + 1
    by_column: dict[int, list[tuple[LayoutEdge, int]]] = defaultdict(list)
    max_column = 0
    for edge in edges:
        left_level = levels.get(edge.left, 0)
        right_level = levels.get(edge.right, left_level + 1)
        column = min(left_level, right_level)
        max_column = max(max_column, column)
        # CircuitIR endpoint order is the strongest available indication of
        # intended visual flow. Using the left-node lane keeps consecutive
        # components that share the same net label horizontally aligned.
        candidate_lane = node_lanes.get(edge.left, node_lanes.get(edge.right, 0))
        if edge.ref in cycle_rank:
            candidate_lane = cycle_lane_base + cycle_rank[edge.ref]
        by_column[column].append((edge, candidate_lane))

    lane_by_ref: dict[str, int] = {}
    max_lanes = max((len(items) for items in by_column.values()), default=1)
    wrap_height = max(3, max_lanes + 2)
    for column in sorted(by_column):
        occupied: set[int] = set()
        for edge, candidate in sorted(by_column[column], key=lambda item: (item[1], item[0].order, item[0].ref)):
            lane = _nearest_free(candidate, occupied)
            occupied.add(lane)
            lane_by_ref[edge.ref] = lane

    positions: dict[str, Position] = {}
    for edge in edges:
        left_level = levels.get(edge.left, 0)
        right_level = levels.get(edge.right, left_level + 1)
        slot = min(left_level, right_level)
        wrap_row, local_column = divmod(slot, WRAP_SLOTS)
        x = ORIGIN_X + local_column * X_SPACING
        y = ORIGIN_Y - (wrap_row * wrap_height + lane_by_ref[edge.ref]) * Y_SPACING
        positions[edge.ref] = Position(x, y)

    node_positions: dict[str, Position] = {}
    for node, level in levels.items():
        wrap_row, local_column = divmod(level, WRAP_SLOTS)
        node_positions[node] = Position(
            ORIGIN_X + local_column * X_SPACING,
            ORIGIN_Y - (wrap_row * wrap_height + node_lanes.get(node, 0)) * Y_SPACING,
        )
    return positions, node_positions, levels, max_column // WRAP_SLOTS


def _source_positions(
    sources: list[LayoutSource],
    config: LayoutConfig,
    node_positions: dict[str, Position],
) -> dict[str, Position]:
    if config.strategy == "manual":
        missing = [source.ref for source in sources if source.ref not in config.source_positions]
        if missing:
            raise LayoutError(f"Manual layout is missing source positions for: {', '.join(missing)}.")
        return {source.ref: config.source_positions[source.ref] for source in sources}
    if config.strategy == "legacy":
        return dict(config.source_positions)

    out: dict[str, Position] = {}
    positive_counts: dict[str, int] = defaultdict(int)
    occupied: list[Position] = []
    source_column_x = min(
        (position.x for position in node_positions.values()),
        default=ORIGIN_X,
    ) - X_SPACING
    for source in sources:
        duplicate_index = positive_counts[source.positive]
        positive_counts[source.positive] += 1
        anchor = node_positions.get(source.positive, Position(ORIGIN_X, ORIGIN_Y))
        position = Position(
            source_column_x,
            anchor.y - duplicate_index * SOURCE_Y_SPACING,
        )
        while any(
            abs(position.x - other.x) < X_SPACING
            and abs(position.y - other.y) < SOURCE_Y_SPACING
            for other in occupied
        ):
            lowest_in_column = min(
                other.y
                for other in occupied
                if abs(position.x - other.x) < X_SPACING
            )
            position = Position(position.x, lowest_in_column - SOURCE_Y_SPACING)
        out[source.ref] = position
        occupied.append(position)
    return out


def _overlaps(component_positions: dict[str, Position], source_positions: dict[str, Position]) -> tuple[dict[str, Any], ...]:
    items = [(ref, "component", position) for ref, position in component_positions.items()]
    items.extend((ref, "source", position) for ref, position in source_positions.items())
    found: list[dict[str, Any]] = []
    for index, (left_ref, left_kind, left) in enumerate(items):
        for right_ref, right_kind, right in items[index + 1 :]:
            y_clearance = SOURCE_Y_SPACING if left_kind == right_kind == "source" else 1_270_000
            if abs(left.x - right.x) < 2_540_000 and abs(left.y - right.y) < y_clearance:
                found.append(
                    {
                        "first": left_ref,
                        "first_kind": left_kind,
                        "second": right_ref,
                        "second_kind": right_kind,
                    }
                )
    return tuple(found)


def _bounds(component_positions: dict[str, Position], source_positions: dict[str, Position]) -> dict[str, int]:
    positions = [*component_positions.values(), *source_positions.values()]
    if not positions:
        return {"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0}
    min_x = min(position.x for position in positions) - 1_016_000
    max_x = max(position.x for position in positions) + 2_286_000
    min_y = min(position.y for position in positions) - 1_270_000
    max_y = max(position.y for position in positions) + 1_270_000
    return {
        "min_x": min_x,
        "min_y": min_y,
        "max_x": max_x,
        "max_y": max_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }


def _motifs(edges: list[LayoutEdge], levels: dict[str, int]) -> tuple[dict[str, Any], ...]:
    degree: dict[str, int] = defaultdict(int)
    pair_counts: dict[tuple[str, str], int] = defaultdict(int)
    for edge in edges:
        degree[edge.left] += 1
        degree[edge.right] += 1
        pair_counts[tuple(sorted((edge.left, edge.right)))] += 1
    motifs: list[dict[str, Any]] = []
    cycle_refs = _cycle_edge_refs(edges)
    if cycle_refs:
        motifs.append({"kind": "cycle", "closing_components": list(cycle_refs)})
    for node, value in sorted(degree.items()):
        if value >= 3:
            motifs.append({"kind": "hub", "node": node, "degree": value})
    for pair, count in sorted(pair_counts.items()):
        if count > 1:
            motifs.append({"kind": "parallel", "nodes": list(pair), "edge_count": count})
    bridge_refs = [
        edge.ref
        for edge in edges
        if levels.get(edge.left) == levels.get(edge.right) and edge.left != edge.right
    ]
    if bridge_refs:
        motifs.append({"kind": "bridge_or_chord", "components": bridge_refs})
    return tuple(motifs)


def plan_payload(payload: Any, strategy_override: str | None = None) -> LayoutPlan:
    if not isinstance(payload, dict):
        raise LayoutError("CircuitIR payload must be an object.")
    route, edges, sources, roots, _sinks = normalize_payload(payload)
    if not edges:
        raise LayoutError("At least one supported passive edge is required for layout planning.")
    config = parse_layout_config(payload, strategy_override)

    if config.strategy == "manual":
        missing = [edge.ref for edge in edges if edge.ref not in config.component_positions]
        if missing:
            raise LayoutError(f"Manual layout is missing component positions for: {', '.join(missing)}.")
        component_positions = {edge.ref: config.component_positions[edge.ref] for edge in edges}
        levels = _node_levels(edges, roots)
        node_positions: dict[str, Position] = {}
        wrap_count = 0
    elif config.strategy == "legacy":
        component_positions = _legacy_positions(route, edges, config.component_positions)
        levels = _node_levels(edges, roots)
        node_positions = {}
        wrap_count = 0
    else:
        component_positions, node_positions, levels, wrap_count = _beautified_positions(edges, roots)

    source_positions = _source_positions(sources, config, node_positions)
    overlaps = _overlaps(component_positions, source_positions)
    requested = config.component_positions
    adjustment_count = sum(
        1 for ref, position in component_positions.items() if ref in requested and requested[ref] != position
    )
    notes = [
        "Placement-only layout: no standalone routed wires or junction records are emitted.",
        "Omitted layout strategy defaults to beautify unless explicit positions require manual placement.",
    ]
    if config.strategy == "beautify":
        notes.extend(
            [
                "Directed endpoint order and repeated node labels guide horizontal continuity.",
                "Sources use a dedicated left column with source-sized vertical clearance.",
            ]
        )
    if config.inferred:
        notes.append(f"Layout strategy was inferred as {config.strategy}.")
    return LayoutPlan(
        route=route,
        strategy=config.strategy,
        direction=config.direction,
        component_positions=component_positions,
        source_positions=source_positions,
        node_positions=node_positions,
        node_levels=levels,
        bounds=_bounds(component_positions, source_positions),
        wrap_count=wrap_count,
        adjustment_count=adjustment_count,
        overlaps=overlaps,
        motifs=_motifs(edges, levels),
        experimental=False,
        notes=tuple(notes),
    )


def apply_layout_to_payload(payload: Any, strategy_override: str | None = None) -> LayoutApplication:
    if not isinstance(payload, dict):
        raise LayoutError("CircuitIR payload must be an object.")
    copied = copy.deepcopy(payload)
    had_layout = isinstance(copied.get("layout"), dict)
    plan = plan_payload(copied, strategy_override)
    layout = copied.setdefault("layout", {})
    if not isinstance(layout, dict):
        raise LayoutError("layout must be an object.")
    layout["strategy"] = plan.strategy
    layout["direction"] = plan.direction
    if plan.strategy == "legacy":
        # Keep established payloads byte-compatible. For the newly optional
        # layout field, materialize the legacy plan so downstream validators
        # still receive a complete placement contract.
        if not had_layout:
            layout["component_positions"] = {
                ref: position.as_dict() for ref, position in plan.component_positions.items()
            }
            layout["source_positions"] = {
                ref: position.as_dict() for ref, position in plan.source_positions.items()
            }
            if plan.route in {"resistor", "mixed-passive"}:
                layout["mode"] = "manual_component_positions"
                layout["coordinate_units"] = "proteus_internal"
                layout["auto_place"] = False
        return LayoutApplication(payload=copied, plan=plan)
    layout["component_positions"] = {
        ref: position.as_dict() for ref, position in plan.component_positions.items()
    }
    layout["source_positions"] = {
        ref: position.as_dict() for ref, position in plan.source_positions.items()
    }
    if plan.route in {"resistor", "mixed-passive"} and plan.strategy in {"beautify", "manual"}:
        layout["mode"] = "manual_component_positions"
        layout["coordinate_units"] = "proteus_internal"
        layout["auto_place"] = False
    return LayoutApplication(payload=copied, plan=plan)


def plan_with_actual_positions(
    plan: LayoutPlan,
    topology: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
) -> LayoutPlan:
    component_positions = {
        item["ref"]: Position(int(item["x"]), int(item["y"]))
        for item in topology
        if isinstance(item.get("ref"), str) and isinstance(item.get("x"), int) and isinstance(item.get("y"), int)
    }
    source_positions = dict(plan.source_positions)
    for item in sources or []:
        target = item.get("target")
        if isinstance(item.get("ref"), str) and isinstance(target, list) and len(target) == 2:
            source_positions[item["ref"]] = Position(int(target[0]), int(target[1]))
    return LayoutPlan(
        route=plan.route,
        strategy=plan.strategy,
        direction=plan.direction,
        component_positions=component_positions or plan.component_positions,
        source_positions=source_positions,
        node_positions=plan.node_positions,
        node_levels=plan.node_levels,
        bounds=_bounds(component_positions or plan.component_positions, source_positions),
        wrap_count=plan.wrap_count,
        adjustment_count=plan.adjustment_count,
        overlaps=_overlaps(component_positions or plan.component_positions, source_positions),
        motifs=plan.motifs,
        experimental=plan.experimental,
        notes=plan.notes,
    )


def actual_layout_plan(
    route: str,
    topology: list[dict[str, Any]],
    sources: list[dict[str, Any]] | None = None,
) -> LayoutPlan:
    """Create a legacy plan for callers that provide an already-parsed IR."""

    base = LayoutPlan(
        route=route,
        strategy="legacy",
        direction="left_to_right",
        component_positions={},
        source_positions={},
        node_positions={},
        node_levels={},
        bounds={"min_x": 0, "min_y": 0, "max_x": 0, "max_y": 0, "width": 0, "height": 0},
        wrap_count=0,
        adjustment_count=0,
        overlaps=(),
        motifs=(),
        experimental=False,
        notes=("Layout plan reconstructed from legacy emitter coordinates.",),
    )
    return plan_with_actual_positions(base, topology, sources)
