"""EDA-agnostic arrangement decisions for schematic beautification.

This stage decides coordinates. It does not edit files and it does not know how
KiCad writes symbols. The intended consumer is ``beautifier.py``, which applies
the coordinate edits as a separate stage.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from math import ceil
from typing import Any


POWER_NETS = {"VCC", "VDD", "VIN", "+5V", "5V", "+3V3", "3V3", "PWR", "POWER"}
GROUND_NETS = {"GND", "0", "VSS", "GROUND"}
CLOCK_TOKENS = ("CLK", "CLOCK", "CK", "CP")

DEFAULT_ARRANGEMENT_CONFIG: dict[str, float] = {
    "grid": 2.54,
    "sheet_width": 420.0,
    "sheet_height": 297.0,
    "margin": 25.4,
    "column_gap": 25.4,
    "row_gap": 12.7,
    "power_y": 17.78,
    "ground_margin": 17.78,
    "component_clearance": 7.62,
}


@dataclass(frozen=True)
class NetEndpoint:
    net: str
    ref: str
    pin: str = ""


@dataclass(frozen=True)
class ComponentNode:
    ref: str
    kind: str
    name: str
    category: str
    at: tuple[float, float]
    width: float
    height: float
    role: str


def _snap(value: float, grid: float) -> float:
    return round(round(value / grid) * grid, 3)


def _snap_up(value: float, grid: float) -> float:
    return round(ceil(value / grid) * grid, 3)


def _point(value: Any, fallback: tuple[float, float] = (0.0, 0.0)) -> tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return fallback


def _net_name(raw: Any) -> str | None:
    if isinstance(raw, str):
        value = raw.strip()
    elif isinstance(raw, dict):
        value = str(raw.get("net") or raw.get("name") or raw.get("node") or "").strip()
    else:
        value = ""
    if not value or value.upper() in {"NC", "N/C", "NO_CONNECT", "UNCONNECTED"}:
        return None
    return value


def _ref_from_endpoint(raw: Any) -> tuple[str, str] | None:
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if ":" in text:
            ref, pin = text.split(":", 1)
            return (ref.strip(), pin.strip())
        if "." in text:
            ref, pin = text.split(".", 1)
            if ref.strip() and pin.strip():
                return (ref.strip(), pin.strip())
        return (text, "")
    if isinstance(raw, dict):
        ref = str(raw.get("ref") or raw.get("component") or raw.get("id") or "").strip()
        pin = str(raw.get("pin") or raw.get("terminal") or "").strip()
        if ref:
            return (ref, pin)
    return None


def extract_connection_nets(circuit: dict[str, Any]) -> dict[str, list[NetEndpoint]]:
    """Extract net endpoints from CircuitIR-style component pins and net lists."""
    nets: dict[str, list[NetEndpoint]] = defaultdict(list)
    seen: set[tuple[str, str, str]] = set()

    def add(net: str, ref: str, pin: str = "") -> None:
        key = (net, ref, pin)
        if ref and key not in seen:
            seen.add(key)
            nets[net].append(NetEndpoint(net=net, ref=ref, pin=pin))

    components = circuit.get("components", [])
    if isinstance(components, list):
        for item in components:
            if not isinstance(item, dict):
                continue
            ref = str(item.get("id") or item.get("ref") or "").strip()
            pins = item.get("pins")
            if not ref or not isinstance(pins, dict):
                continue
            for pin, raw_net in pins.items():
                net = _net_name(raw_net)
                if net:
                    add(net, ref, str(pin))

    raw_nets = circuit.get("nets")
    if isinstance(raw_nets, dict):
        for net_name, raw_value in raw_nets.items():
            net = _net_name(net_name)
            if not net:
                continue
            endpoints: Any = None
            if isinstance(raw_value, list):
                endpoints = raw_value
            elif isinstance(raw_value, dict):
                endpoints = (
                    raw_value.get("nodes")
                    or raw_value.get("pins")
                    or raw_value.get("connections")
                    or raw_value.get("endpoints")
                )
            if not isinstance(endpoints, list):
                continue
            for endpoint in endpoints:
                parsed = _ref_from_endpoint(endpoint)
                if parsed:
                    add(net, parsed[0], parsed[1])

    return dict(sorted(nets.items()))


def _role(kind: str, category: str, name: str, degree: int) -> str:
    text = f"{kind} {category} {name}".upper()
    kind_token = kind.upper()
    if "GND" in text or category == "ground":
        return "ground"
    if kind_token in {"VDC", "VSOURCE", "BATTERY", "POWER"}:
        return "power"
    if category == "power_symbol" or any(token in text for token in ("VCC", "+5V", "+3V3", "VDD", "PWR")):
        return "power"
    if kind_token in {"R", "RESISTOR", "C", "CAPACITOR", "CP", "L", "INDUCTOR", "D", "DIODE", "LED"}:
        return "passive" if kind_token != "LED" else "load"
    if kind_token in {"Q", "NPN", "PNP", "MOSFET", "SW", "SWITCH", "POT", "POTENTIOMETER"}:
        return "passive"
    if any(token in category for token in ("terminal", "connector", "header", "jack")):
        return "terminal"
    if any(token in category for token in ("microcontroller", "module", "logic", "interface", "opamp", "comparator", "rtc", "memory", "sensor")):
        return "processing"
    if any(token in category for token in ("indicator", "display", "motor", "speaker", "relay")):
        return "load"
    if any(token in category for token in ("resistor", "capacitor", "diode", "inductor", "potentiometer", "crystal", "switch", "protection")):
        return "passive"
    if degree <= 1:
        return "leaf"
    return "processing"


def _role_rank(role: str) -> int:
    return {
        "power": 0,
        "terminal": 0,
        "leaf": 1,
        "passive": 2,
        "processing": 3,
        "load": 4,
        "ground": 5,
    }.get(role, 3)


def _components_from_placement(placement: dict[str, Any], circuit: dict[str, Any], nets: dict[str, list[NetEndpoint]]) -> dict[str, ComponentNode]:
    placement_components = placement.get("components", {})
    if not isinstance(placement_components, dict):
        placement_components = {}

    obstacles: dict[str, dict[str, float]] = {}
    for item in placement.get("obstacles", []):
        if isinstance(item, dict) and item.get("owner"):
            obstacles[str(item["owner"])] = {
                "left": float(item.get("left", 0.0)),
                "right": float(item.get("right", 0.0)),
                "top": float(item.get("top", 0.0)),
                "bottom": float(item.get("bottom", 0.0)),
            }

    degree: dict[str, int] = defaultdict(int)
    for endpoints in nets.values():
        unique_refs = {endpoint.ref for endpoint in endpoints}
        for ref in unique_refs:
            degree[ref] += max(1, len(unique_refs) - 1)

    requested: dict[str, dict[str, Any]] = {}
    for item in circuit.get("components", []):
        if isinstance(item, dict):
            ref = str(item.get("id") or item.get("ref") or "").strip()
            if ref:
                requested[ref] = item

    refs = sorted(set(placement_components) | set(requested))
    out: dict[str, ComponentNode] = {}
    for ref in refs:
        placed = placement_components.get(ref, {})
        requested_item = requested.get(ref, {})
        if not isinstance(placed, dict):
            placed = {}
        at = _point(placed.get("at"), _point(requested_item.get("at"), (0.0, 0.0)))
        obstacle = obstacles.get(ref)
        if obstacle:
            width = abs(obstacle["right"] - obstacle["left"])
            height = abs(obstacle["bottom"] - obstacle["top"])
        else:
            width = float(placed.get("width") or requested_item.get("width") or 10.0)
            height = float(placed.get("height") or requested_item.get("height") or 8.0)
        kind = str(placed.get("kind") or requested_item.get("kind") or requested_item.get("name") or ref)
        name = str(placed.get("name") or requested_item.get("value") or requested_item.get("name") or kind)
        category = str(placed.get("category") or requested_item.get("category") or "")
        role = _role(kind, category, name, degree.get(ref, 0))
        out[ref] = ComponentNode(ref, kind, name, category, at, width, height, role)
    return out


def _directed_edges(components: dict[str, ComponentNode], nets: dict[str, list[NetEndpoint]]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    outgoing: dict[str, set[str]] = {ref: set() for ref in components}
    incoming: dict[str, set[str]] = {ref: set() for ref in components}
    for endpoints in nets.values():
        refs = sorted({endpoint.ref for endpoint in endpoints if endpoint.ref in components})
        if len(refs) < 2:
            continue
        refs.sort(key=lambda ref: (_role_rank(components[ref].role), components[ref].at[0], components[ref].at[1], ref))
        for left, right in zip(refs, refs[1:]):
            if left == right:
                continue
            outgoing[left].add(right)
            incoming[right].add(left)
    return outgoing, incoming


def _assign_layers(components: dict[str, ComponentNode], outgoing: dict[str, set[str]], incoming: dict[str, set[str]]) -> dict[str, int]:
    layers = {ref: 0 for ref in components}
    indegree = {ref: len(incoming[ref]) for ref in components}
    queue = deque(sorted(ref for ref, count in indegree.items() if count == 0))
    visited: set[str] = set()
    while queue:
        ref = queue.popleft()
        visited.add(ref)
        for nxt in sorted(outgoing[ref]):
            layers[nxt] = max(layers[nxt], layers[ref] + 1)
            indegree[nxt] -= 1
            if indegree[nxt] == 0:
                queue.append(nxt)

    for ref, node in components.items():
        if ref not in visited:
            layers[ref] = max(layers[ref], _role_rank(node.role))
        if node.role == "power":
            layers[ref] = max(0, min(layers[ref], 1))
        elif node.role == "ground":
            layers[ref] = max(layers[ref], max(layers.values(), default=0))
    return layers


def _ordered_layers(
    components: dict[str, ComponentNode],
    layers: dict[str, int],
    outgoing: dict[str, set[str]],
    incoming: dict[str, set[str]],
) -> dict[int, list[str]]:
    layer_map: dict[int, list[str]] = defaultdict(list)
    for ref, layer in layers.items():
        layer_map[layer].append(ref)
    for layer in layer_map:
        layer_map[layer].sort(key=lambda ref: (components[ref].at[1], _role_rank(components[ref].role), ref))

    for _pass in range(3):
        order = {ref: idx for refs in layer_map.values() for idx, ref in enumerate(refs)}
        for layer in sorted(layer_map)[1:]:
            layer_map[layer].sort(
                key=lambda ref: (
                    _barycenter(incoming[ref], order),
                    components[ref].at[1],
                    ref,
                )
            )
            order = {ref: idx for refs in layer_map.values() for idx, ref in enumerate(refs)}
        for layer in sorted(layer_map, reverse=True)[1:]:
            layer_map[layer].sort(
                key=lambda ref: (
                    _barycenter(outgoing[ref], order),
                    components[ref].at[1],
                    ref,
                )
            )
    return dict(sorted(layer_map.items()))


def _barycenter(neighbors: set[str], order: dict[str, int]) -> float:
    values = [order[neighbor] for neighbor in neighbors if neighbor in order]
    if not values:
        return 1_000_000.0
    return sum(values) / len(values)


def _clock_nets(nets: dict[str, list[NetEndpoint]]) -> list[str]:
    return sorted(net for net in nets if any(token in net.upper() for token in CLOCK_TOKENS))


def _packed_height(refs: list[str], components: dict[str, ComponentNode], clearance: float) -> float:
    if not refs:
        return 0.0
    return sum(components[ref].height for ref in refs) + max(0, len(refs) - 1) * clearance


def _layer_x_positions(
    layer_map: dict[int, list[str]],
    components: dict[str, ComponentNode],
    cfg: dict[str, float],
) -> tuple[dict[int, float], float]:
    positions: dict[int, float] = {}
    current_right = cfg["margin"]
    for layer in sorted(layer_map):
        refs = layer_map[layer]
        max_width = max((components[ref].width for ref in refs), default=10.0)
        half_width = max_width / 2
        if positions:
            current_right += cfg["column_gap"]
        center = current_right + half_width
        positions[layer] = _snap(center, cfg["grid"])
        current_right = center + half_width
    sheet_width = max(cfg["sheet_width"], current_right + cfg["margin"])
    return positions, _snap_up(sheet_width, cfg["grid"])


def _layer_y_positions(
    refs: list[str],
    components: dict[str, ComponentNode],
    cfg: dict[str, float],
    sheet_height: float,
) -> dict[str, float]:
    if not refs:
        return {}
    clearance = cfg["component_clearance"]
    packed_height = _packed_height(refs, components, clearance)
    roles = {components[ref].role for ref in refs}
    if roles == {"power"}:
        top = max(cfg["power_y"], cfg["margin"] / 2)
        current = top
    elif roles == {"ground"}:
        current = max(cfg["margin"], sheet_height - cfg["ground_margin"] - packed_height)
    else:
        current = max(cfg["margin"], (sheet_height - packed_height) / 2)

    out: dict[str, float] = {}
    for ref in refs:
        node = components[ref]
        current += node.height / 2
        out[ref] = _snap(current, cfg["grid"])
        current += node.height / 2 + clearance
    return out


def decide_arrangement(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    config: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return a coordinate-edit plan using topology-driven schematic rules."""
    cfg = dict(DEFAULT_ARRANGEMENT_CONFIG)
    if config:
        cfg.update({key: float(value) for key, value in config.items()})
    grid = cfg["grid"]
    nets = extract_connection_nets(circuit)
    components = _components_from_placement(placement, circuit, nets)
    outgoing, incoming = _directed_edges(components, nets)
    layers = _assign_layers(components, outgoing, incoming)
    layer_map = _ordered_layers(components, layers, outgoing, incoming)

    layer_x, sheet_width = _layer_x_positions(layer_map, components, cfg)
    max_layer_height = max((_packed_height(refs, components, cfg["component_clearance"]) for refs in layer_map.values()), default=0.0)
    sheet_height = _snap_up(max(cfg["sheet_height"], cfg["margin"] * 2 + max_layer_height), grid)
    layer_y: dict[int, dict[str, float]] = {
        layer: _layer_y_positions(refs, components, cfg, sheet_height) for layer, refs in layer_map.items()
    }

    planned: dict[str, tuple[float, float]] = {}
    edits: list[dict[str, Any]] = []
    for layer, refs in layer_map.items():
        x = layer_x[layer]
        for index, ref in enumerate(refs):
            node = components[ref]
            y = layer_y[layer][ref]
            reasons = ["topology_depth_to_x", "barycenter_row_order"]
            if node.role == "power":
                reasons.append("power_symbols_above_signal_path")
            elif node.role == "ground":
                reasons.append("ground_symbols_below_signal_path")
            planned[ref] = (x, y)
            if (round(node.at[0], 3), round(node.at[1], 3)) != planned[ref]:
                edits.append(
                    {
                        "ref": ref,
                        "from": [round(node.at[0], 3), round(node.at[1], 3)],
                        "to": [planned[ref][0], planned[ref][1]],
                        "delta": [round(planned[ref][0] - node.at[0], 3), round(planned[ref][1] - node.at[1], 3)],
                        "rotation": 0.0,
                        "reason": reasons,
                    }
                )

    warnings: list[str] = []
    if len(components) > 50:
        warnings.append("density_management_recommended: component count exceeds 50; divide into functional blocks before final wiring.")
    if _clock_nets(nets):
        warnings.append("clock_priority_detected: route clock nets before lower-priority signals.")

    return {
        "schema": "progen-kicad-arrangement-decision/v0.1",
        "stage": "arrangement_decider",
        "algorithm": {
            "primary": "sugiyama_layered_layout",
            "ordering": "barycenter_crossing_minimization",
            "rules_source": "topology, signal-flow, power-ground, density, clock-priority rules",
        },
        "sheet": {"width": sheet_width, "height": sheet_height, "grid": grid, "margin": cfg["margin"]},
        "component_count": len(components),
        "net_count": len(nets),
        "clock_nets": _clock_nets(nets),
        "layers": {str(layer): refs for layer, refs in layer_map.items()},
        "components": {
            ref: {
                "kind": node.kind,
                "name": node.name,
                "category": node.category,
                "role": node.role,
                "degree": len(incoming[ref]) + len(outgoing[ref]),
                "layer": layers[ref],
                "original_at": [round(node.at[0], 3), round(node.at[1], 3)],
                "planned_at": [planned.get(ref, node.at)[0], planned.get(ref, node.at)[1]],
                "size": [round(node.width, 3), round(node.height, 3)],
            }
            for ref, node in components.items()
        },
        "nets": {
            net: {
                "endpoint_count": len(endpoints),
                "refs": sorted({endpoint.ref for endpoint in endpoints}),
                "strategy_hint": "local_labels" if net.upper() in POWER_NETS | GROUND_NETS else "wire",
            }
            for net, endpoints in nets.items()
        },
        "coordinate_edits": edits,
        "warnings": warnings,
    }
