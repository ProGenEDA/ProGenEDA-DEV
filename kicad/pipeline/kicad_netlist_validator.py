"""Hosted KiCad schematic netlist comparison.

This validator intentionally does not require ``kicad-cli``. It reads the
generated ``.kicad_sch`` file directly, using the same embedded symbol pin
geometry rules as the KiCad wire maker, then compares the physical
wire/junction/pin graph against the expected CircuitIR nets.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from kicad.generator.kicad_backend.sexpr import paren_balance
from kicad.source_pack.source_reference import load_reference

from .kicad_symbol_library import _balanced_block, _child_head, _direct_child_blocks
from .kicad_wire_maker import PinGeometry, _pin_geometries, _resolve_pin_geometry


Point = tuple[float, float]
EndpointMap = dict[str, list[str]]

POWER_NET_NAMES = {
    "+1V8",
    "+3V3",
    "+5V",
    "+9V",
    "+12V",
    "1V8",
    "3V3",
    "5V",
    "9V",
    "12V",
    "VBAT",
    "VBUS",
    "VCC",
    "VDD",
    "VIN",
}
GROUND_NET_NAMES = {"0", "AGND", "COM", "DGND", "GND", "GNDA", "GNDD", "VEE", "VSS"}


@dataclass(frozen=True)
class SymbolInstance:
    ref: str
    value: str
    kind: str
    lib_id: str
    at: Point
    rotation: float
    unit: int


@dataclass(frozen=True)
class WireSegment:
    start: Point
    end: Point


@dataclass(frozen=True)
class ActualPin:
    ref: str
    lib_id: str
    kind: str
    unit: int
    number: str
    name: str
    point: Point

    @property
    def identities(self) -> tuple[str, ...]:
        values = [f"{self.ref}.{self.number}"]
        if self.name:
            values.append(f"{self.ref}.{self.name}")
        return tuple(values)


@dataclass(frozen=True)
class ResolvedExpectedEndpoint:
    endpoint: str
    net: str
    ref: str
    logical_pin: str
    resolved_number: str
    resolved_name: str
    point: Point
    lib_id: str
    unit: int


@dataclass(frozen=True)
class ParsedSchematic:
    schematic_path: Path
    lib_symbols: dict[str, str]
    lib_geometries: dict[str, tuple[PinGeometry, ...]]
    instances_by_ref: dict[str, list[SymbolInstance]]
    wires: tuple[WireSegment, ...]
    junctions: tuple[Point, ...]
    labels_by_text: dict[str, list[Point]]
    actual_pins_by_point: dict[Point, list[ActualPin]]
    file_validity: dict[str, Any]


class _PointUnionFind:
    def __init__(self) -> None:
        self.parent: dict[Point, Point] = {}

    def add(self, point: Point) -> Point:
        self.parent.setdefault(point, point)
        return point

    def find(self, point: Point) -> Point:
        self.add(point)
        parent = self.parent[point]
        if parent != point:
            self.parent[point] = self.find(parent)
        return self.parent[point]

    def union(self, left: Point, right: Point) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _round_point(point: Iterable[float]) -> Point:
    x, y = tuple(point)[:2]
    return (round(float(x), 3), round(float(y), 3))


def _unescape(value: str) -> str:
    return bytes(value, "utf-8").decode("unicode_escape")


def _quoted_pattern() -> str:
    return r'"((?:\\.|[^"])*)"'


def _root_block(text: str) -> str:
    start = text.find("(kicad_sch")
    if start < 0:
        raise ValueError("schematic does not contain a kicad_sch root block")
    block = _balanced_block(text, start)
    if block is None:
        raise ValueError("schematic kicad_sch root block is not balanced")
    return block


def _symbol_name(block: str) -> str | None:
    match = re.match(rf"\s*\(symbol\s+{_quoted_pattern()}", block, re.S)
    return _unescape(match.group(1)) if match else None


def _properties(block: str) -> dict[str, str]:
    pattern = re.compile(rf"\(property\s+{_quoted_pattern()}\s+{_quoted_pattern()}", re.S)
    return {_unescape(match.group(1)): _unescape(match.group(2)) for match in pattern.finditer(block)}


def _instance_from_block(block: str) -> SymbolInstance | None:
    lib_match = re.match(rf"\s*\(symbol\s+\(lib_id\s+{_quoted_pattern()}\)", block, re.S)
    at_match = re.search(r"\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?", block)
    if not lib_match or not at_match:
        return None
    props = _properties(block)
    ref = props.get("Reference", "")
    if not ref:
        return None
    unit_match = re.search(r"\(unit\s+([0-9]+)", block)
    return SymbolInstance(
        ref=ref,
        value=props.get("Value", ""),
        kind=props.get("Progen.Kind", ""),
        lib_id=_unescape(lib_match.group(1)),
        at=_round_point((at_match.group(1), at_match.group(2))),
        rotation=float(at_match.group(3) or 0.0),
        unit=int(unit_match.group(1)) if unit_match else 1,
    )


def _label_from_block(block: str) -> tuple[str, Point] | None:
    match = re.match(rf"\s*\((?:label|global_label|hierarchical_label)\s+{_quoted_pattern()}", block, re.S)
    at_match = re.search(r"\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+[-0-9.]+)?", block)
    if not match or not at_match:
        return None
    return (_unescape(match.group(1)), _round_point((at_match.group(1), at_match.group(2))))


def _parse_lib_symbols(top_blocks: list[str]) -> tuple[dict[str, str], dict[str, tuple[PinGeometry, ...]]]:
    symbols: dict[str, str] = {}
    geometries: dict[str, tuple[PinGeometry, ...]] = {}
    for block in top_blocks:
        if _child_head(block) != "lib_symbols":
            continue
        for child in _direct_child_blocks(block):
            if _child_head(child) != "symbol":
                continue
            name = _symbol_name(child)
            if not name:
                continue
            symbols[name] = child
            geometries[name] = _pin_geometries(child)
    return symbols, geometries


def _parse_wires(text: str) -> tuple[WireSegment, ...]:
    wires: list[WireSegment] = []
    start = 0
    while True:
        index = text.find("(wire ", start)
        if index < 0:
            break
        block = _balanced_block(text, index)
        if block is None:
            start = index + 6
            continue
        points = [
            _round_point((match.group(1), match.group(2)))
            for match in re.finditer(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)", block)
        ]
        for left, right in zip(points, points[1:]):
            if left != right:
                wires.append(WireSegment(left, right))
        start = index + len(block)
    return tuple(wires)


def _parse_junctions(text: str) -> tuple[Point, ...]:
    return tuple(
        _round_point((match.group(1), match.group(2)))
        for match in re.finditer(r"\(junction\s+\(at\s+([-0-9.]+)\s+([-0-9.]+)", text)
    )


def _world_pin(instance: SymbolInstance, geometry: PinGeometry) -> Point:
    angle = math.radians(instance.rotation % 360.0)
    local_y = -geometry.y
    x = geometry.x * math.cos(angle) - local_y * math.sin(angle)
    y = geometry.x * math.sin(angle) + local_y * math.cos(angle)
    return _round_point((instance.at[0] + x, instance.at[1] + y))


def _parse_actual_pins(
    instances_by_ref: dict[str, list[SymbolInstance]],
    lib_geometries: dict[str, tuple[PinGeometry, ...]],
) -> dict[Point, list[ActualPin]]:
    pins: dict[Point, list[ActualPin]] = defaultdict(list)
    for instances in instances_by_ref.values():
        for instance in instances:
            for geometry in lib_geometries.get(instance.lib_id, ()):
                if geometry.unit != instance.unit:
                    continue
                point = _world_pin(instance, geometry)
                pins[point].append(
                    ActualPin(
                        ref=instance.ref,
                        lib_id=instance.lib_id,
                        kind=instance.kind,
                        unit=instance.unit,
                        number=geometry.number,
                        name=geometry.name,
                        point=point,
                    )
                )
    return dict(pins)


def parse_schematic(schematic_path: Path | str) -> ParsedSchematic:
    path = Path(schematic_path)
    text = path.read_text(encoding="utf-8")
    balance_ok, balance_reason = paren_balance(text)
    root = _root_block(text)
    top_blocks = _direct_child_blocks(root)
    lib_symbols, lib_geometries = _parse_lib_symbols(top_blocks)
    instances_by_ref: dict[str, list[SymbolInstance]] = defaultdict(list)
    labels_by_text: dict[str, list[Point]] = defaultdict(list)
    for block in top_blocks:
        head = _child_head(block)
        if head == "symbol":
            instance = _instance_from_block(block)
            if instance:
                instances_by_ref[instance.ref].append(instance)
        elif head in {"label", "global_label", "hierarchical_label"}:
            label = _label_from_block(block)
            if label:
                labels_by_text[label[0]].append(label[1])
    return ParsedSchematic(
        schematic_path=path,
        lib_symbols=lib_symbols,
        lib_geometries=lib_geometries,
        instances_by_ref={ref: sorted(instances, key=lambda item: item.unit) for ref, instances in instances_by_ref.items()},
        wires=_parse_wires(text),
        junctions=_parse_junctions(text),
        labels_by_text=dict(labels_by_text),
        actual_pins_by_point=_parse_actual_pins(dict(instances_by_ref), lib_geometries),
        file_validity={"ok": balance_ok, "reason": balance_reason},
    )


def _component_ref(component: dict[str, Any]) -> str:
    return str(component.get("ref") or component.get("id") or "")


def _expected_components(circuit: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    raw = circuit.get("components", [])
    if not isinstance(raw, list):
        return out
    for component in raw:
        if not isinstance(component, dict):
            continue
        ref = _component_ref(component)
        if ref:
            out[ref] = component
    return out


def _endpoint_text(item: Any) -> str | None:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if isinstance(item.get("endpoint"), str):
            return item["endpoint"]
        ref = item.get("ref") or item.get("component") or item.get("component_ref")
        pin = item.get("pin") or item.get("pin_name") or item.get("pin_number")
        if ref is not None and pin is not None:
            return f"{ref}.{pin}"
    return None


def expected_nets_from_circuit(circuit: dict[str, Any]) -> EndpointMap:
    nets: EndpointMap = {}
    raw_nets = circuit.get("nets")
    if isinstance(raw_nets, dict):
        for net, raw_members in raw_nets.items():
            members = raw_members.get("members") if isinstance(raw_members, dict) else raw_members
            if not isinstance(members, list):
                continue
            endpoints = [endpoint for item in members if (endpoint := _endpoint_text(item))]
            if endpoints:
                nets[str(net)] = sorted(dict.fromkeys(endpoints))
    if nets:
        return nets

    for component in circuit.get("components", []):
        if not isinstance(component, dict):
            continue
        ref = _component_ref(component)
        pins = component.get("pins", {})
        if not ref or not isinstance(pins, dict):
            continue
        for pin, net in pins.items():
            nets.setdefault(str(net), []).append(f"{ref}.{pin}")
    return {net: sorted(dict.fromkeys(endpoints)) for net, endpoints in nets.items()}


def _split_endpoint(endpoint: str) -> tuple[str, str] | None:
    if "." not in endpoint:
        return None
    ref, pin = endpoint.rsplit(".", 1)
    if not ref or not pin:
        return None
    return ref, pin


def _instance_for_unit(instances: list[SymbolInstance], unit: int) -> SymbolInstance:
    for instance in instances:
        if instance.unit == unit:
            return instance
    return instances[0]


def _resolve_expected_endpoint(
    *,
    endpoint: str,
    net: str,
    circuit_components: dict[str, dict[str, Any]],
    parsed: ParsedSchematic,
) -> tuple[ResolvedExpectedEndpoint | None, dict[str, Any] | None]:
    split = _split_endpoint(endpoint)
    if split is None:
        return None, {"endpoint": endpoint, "net": net, "reason": "bad_endpoint_format"}
    ref, logical_pin = split
    instances = parsed.instances_by_ref.get(ref)
    if not instances:
        return None, {"endpoint": endpoint, "net": net, "ref": ref, "pin": logical_pin, "reason": "missing_component"}
    lib_id = instances[0].lib_id
    geometries = parsed.lib_geometries.get(lib_id, ())
    if not geometries:
        return None, {"endpoint": endpoint, "net": net, "ref": ref, "pin": logical_pin, "reason": "missing_lib_symbol_pins"}
    kind = str(circuit_components.get(ref, {}).get("kind") or instances[0].kind)
    geometry, status = _resolve_pin_geometry(ref=ref, kind=kind, pin=logical_pin, geometries=geometries)
    if geometry is None:
        return None, {
            "endpoint": endpoint,
            "net": net,
            "ref": ref,
            "pin": logical_pin,
            "kind": kind,
            "lib_id": lib_id,
            "reason": status,
        }
    instance = _instance_for_unit(instances, geometry.unit)
    return (
        ResolvedExpectedEndpoint(
            endpoint=endpoint,
            net=net,
            ref=ref,
            logical_pin=logical_pin,
            resolved_number=geometry.number,
            resolved_name=geometry.name,
            point=_world_pin(instance, geometry),
            lib_id=lib_id,
            unit=geometry.unit,
        ),
        None,
    )


def _point_on_segment(point: Point, segment: WireSegment, eps: float = 0.001) -> bool:
    if abs(segment.start[1] - segment.end[1]) <= eps:
        low, high = sorted((segment.start[0], segment.end[0]))
        return abs(point[1] - segment.start[1]) <= eps and low - eps <= point[0] <= high + eps
    if abs(segment.start[0] - segment.end[0]) <= eps:
        low, high = sorted((segment.start[1], segment.end[1]))
        return abs(point[0] - segment.start[0]) <= eps and low - eps <= point[1] <= high + eps
    return False


def _segment_sort_key(segment: WireSegment, point: Point) -> float:
    if abs(segment.start[1] - segment.end[1]) <= 0.001:
        return point[0]
    if abs(segment.start[0] - segment.end[0]) <= 0.001:
        return point[1]
    return abs(point[0] - segment.start[0]) + abs(point[1] - segment.start[1])


def build_schematic_connectivity_graph(parsed: ParsedSchematic) -> _PointUnionFind:
    graph = _PointUnionFind()
    breakpoints: set[Point] = set(parsed.junctions)
    for wire in parsed.wires:
        breakpoints.add(wire.start)
        breakpoints.add(wire.end)
    for points in parsed.labels_by_text.values():
        breakpoints.update(points)
    breakpoints.update(parsed.actual_pins_by_point.keys())

    by_x: dict[float, set[Point]] = defaultdict(set)
    by_y: dict[float, set[Point]] = defaultdict(set)
    for point in breakpoints:
        graph.add(point)
        by_x[point[0]].add(point)
        by_y[point[1]].add(point)

    for segment in parsed.wires:
        graph.add(segment.start)
        graph.add(segment.end)
        if abs(segment.start[1] - segment.end[1]) <= 0.001:
            candidates = by_y.get(segment.start[1], set())
        elif abs(segment.start[0] - segment.end[0]) <= 0.001:
            candidates = by_x.get(segment.start[0], set())
        else:
            candidates = breakpoints
        segment_points = sorted(
            (point for point in candidates if _point_on_segment(point, segment)),
            key=lambda point: _segment_sort_key(segment, point),
        )
        if not segment_points:
            graph.union(segment.start, segment.end)
            continue
        for left, right in zip(segment_points, segment_points[1:]):
            graph.union(left, right)

    for _label, points in parsed.labels_by_text.items():
        if len(points) < 2:
            continue
        first = points[0]
        for point in points[1:]:
            graph.union(first, point)
    return graph


def _net_category(net: str) -> str:
    normalized = net.strip().upper()
    if normalized in GROUND_NET_NAMES:
        return "ground"
    if normalized in POWER_NET_NAMES or normalized.startswith("+"):
        return "power"
    return "signal"


def _source_reference_report() -> dict[str, Any]:
    try:
        return load_reference().as_dict()
    except Exception as exc:  # pragma: no cover - defensive hosted packaging guard.
        return {"available": False, "error": str(exc)}


def compare_expected_netlist(
    *,
    schematic_path: Path | str,
    circuit: dict[str, Any],
    routing_mode: str = "wire",
    wire_mode_terminal_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    parsed = parse_schematic(schematic_path)
    graph = build_schematic_connectivity_graph(parsed)
    expected_components = _expected_components(circuit)
    expected_nets = expected_nets_from_circuit(circuit)

    actual_refs = set(parsed.instances_by_ref)
    expected_refs = set(expected_components)
    missing_refs = sorted(expected_refs - actual_refs)
    extra_refs = sorted(actual_refs - expected_refs)

    value_mismatches: list[dict[str, Any]] = []
    for ref, component in expected_components.items():
        expected_value = component.get("value")
        if expected_value in (None, "") or ref not in parsed.instances_by_ref:
            continue
        actual_values = sorted({instance.value for instance in parsed.instances_by_ref[ref]})
        if str(expected_value) not in actual_values:
            value_mismatches.append({"ref": ref, "expected": str(expected_value), "actual": actual_values})

    resolved: dict[str, ResolvedExpectedEndpoint] = {}
    missing_pins: list[dict[str, Any]] = []
    for net, members in expected_nets.items():
        for endpoint in members:
            if endpoint in resolved:
                continue
            endpoint_result, failure = _resolve_expected_endpoint(
                endpoint=endpoint,
                net=net,
                circuit_components=expected_components,
                parsed=parsed,
            )
            if endpoint_result is None:
                if failure:
                    missing_pins.append(failure)
                continue
            resolved[endpoint] = endpoint_result

    endpoint_roots: dict[str, Point] = {endpoint: graph.find(item.point) for endpoint, item in resolved.items()}
    physical_pin_assignments: dict[tuple[str, int, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for net, members in expected_nets.items():
        for endpoint in members:
            item = resolved.get(endpoint)
            if item is None:
                continue
            physical_pin_assignments[(item.ref, item.unit, item.resolved_number)][net].add(endpoint)
    physical_pin_conflicts = [
        {
            "ref": ref,
            "unit": unit,
            "pin_number": number,
            "nets": sorted(nets),
            "endpoints_by_net": {net: sorted(endpoints) for net, endpoints in sorted(net_map.items())},
        }
        for (ref, unit, number), net_map in sorted(physical_pin_assignments.items())
        if len(nets := set(net_map)) > 1
    ]
    nets_by_root: dict[Point, set[str]] = defaultdict(set)
    endpoints_by_root: dict[Point, set[str]] = defaultdict(set)
    for net, members in expected_nets.items():
        for endpoint in members:
            root = endpoint_roots.get(endpoint)
            if root is None:
                continue
            nets_by_root[root].add(net)
            endpoints_by_root[root].add(endpoint)

    net_failures: list[dict[str, Any]] = []
    passed_nets: list[str] = []
    floating_pins: list[dict[str, Any]] = []
    for net, members in expected_nets.items():
        missing_members = [endpoint for endpoint in members if endpoint not in resolved]
        groups: dict[Point, list[str]] = defaultdict(list)
        for endpoint in members:
            root = endpoint_roots.get(endpoint)
            if root is not None:
                groups[root].append(endpoint)
        if missing_members or len(groups) != 1:
            net_failures.append(
                {
                    "net": net,
                    "expected_member_count": len(members),
                    "missing_members": missing_members,
                    "connected_groups": [sorted(group) for _root, group in sorted(groups.items(), key=lambda item: item[0])],
                }
            )
        else:
            passed_nets.append(net)
        if len(members) > 1:
            for endpoint in members:
                root = endpoint_roots.get(endpoint)
                if root is not None and len(groups.get(root, [])) == 1:
                    floating_pins.append({"net": net, "endpoint": endpoint, "point": list(resolved[endpoint].point)})

    merged_nets: list[dict[str, Any]] = []
    power_ground_shorts: list[dict[str, Any]] = []
    for root, nets in nets_by_root.items():
        if len(nets) <= 1:
            continue
        categories = {_net_category(net) for net in nets}
        item = {
            "root": list(root),
            "nets": sorted(nets),
            "expected_endpoints": sorted(endpoints_by_root[root]),
        }
        merged_nets.append(item)
        if "power" in categories and "ground" in categories:
            power_ground_shorts.append(item)

    actual_pin_warnings: list[dict[str, Any]] = []
    expected_endpoint_identity_by_root: dict[Point, set[str]] = defaultdict(set)
    for endpoint, item in resolved.items():
        root = endpoint_roots[endpoint]
        expected_endpoint_identity_by_root[root].update(
            identity
            for identity in (
                endpoint,
                f"{item.ref}.{item.logical_pin}",
                f"{item.ref}.{item.resolved_number}",
                f"{item.ref}.{item.resolved_name}" if item.resolved_name else "",
            )
            if identity
        )
    for point, actual_pins in parsed.actual_pins_by_point.items():
        root = graph.find(point)
        if root not in nets_by_root:
            continue
        allowed = expected_endpoint_identity_by_root[root]
        for pin in actual_pins:
            if any(identity in allowed for identity in pin.identities):
                continue
            actual_pin_warnings.append(
                {
                    "point": list(point),
                    "nets": sorted(nets_by_root[root]),
                    "actual_pin": {"ref": pin.ref, "number": pin.number, "name": pin.name, "unit": pin.unit},
                    "reason": "actual_pin_on_expected_net_not_named_by_circuit_json",
                }
            )
            if len(actual_pin_warnings) >= 100:
                break
        if len(actual_pin_warnings) >= 100:
            break

    label_count = sum(len(points) for points in parsed.labels_by_text.values())
    terminal_policy = wire_mode_terminal_policy if isinstance(wire_mode_terminal_policy, dict) else {}
    raw_allowed_label_nets = terminal_policy.get("terminal_nets") or ()
    if isinstance(raw_allowed_label_nets, str):
        raw_allowed_label_nets = [raw_allowed_label_nets]
    if not isinstance(raw_allowed_label_nets, (list, tuple, set)):
        raw_allowed_label_nets = []
    allowed_label_nets = {str(net).strip().upper() for net in raw_allowed_label_nets if str(net).strip()}
    label_nets = {str(label).strip().upper() for label in parsed.labels_by_text if str(label).strip()}
    unexpected_label_nets = sorted(label_nets - allowed_label_nets)
    wire_mode_label_failure = routing_mode == "wire" and label_count > 0 and (not terminal_policy.get("enabled") or bool(unexpected_label_nets))
    blocking_failures: list[dict[str, Any]] = []
    if not parsed.file_validity["ok"]:
        blocking_failures.append({"type": "file_validity", "detail": parsed.file_validity})
    if missing_refs:
        blocking_failures.append({"type": "missing_components", "refs": missing_refs})
    if value_mismatches:
        blocking_failures.append({"type": "value_mismatch", "items": value_mismatches[:50]})
    if missing_pins:
        blocking_failures.append({"type": "missing_pins", "items": missing_pins[:100], "count": len(missing_pins)})
    if physical_pin_conflicts:
        blocking_failures.append(
            {"type": "physical_pin_net_conflict", "items": physical_pin_conflicts[:100], "count": len(physical_pin_conflicts)}
        )
    if net_failures:
        blocking_failures.append({"type": "expected_net_mismatch", "items": net_failures[:100], "count": len(net_failures)})
    if merged_nets:
        blocking_failures.append({"type": "merged_expected_nets", "items": merged_nets[:100], "count": len(merged_nets)})
    if power_ground_shorts:
        blocking_failures.append({"type": "power_ground_short", "items": power_ground_shorts[:20], "count": len(power_ground_shorts)})
    if floating_pins:
        blocking_failures.append({"type": "floating_expected_pins", "items": floating_pins[:100], "count": len(floating_pins)})
    if wire_mode_label_failure:
        blocking_failures.append(
            {
                "type": "wire_mode_label_used",
                "label_count": label_count,
                "unexpected_label_nets": unexpected_label_nets,
                "allowed_label_nets": sorted(allowed_label_nets),
            }
        )

    checks = {
        "file_validity": parsed.file_validity,
        "component_count_reference_value": {
            "ok": not missing_refs and not value_mismatches,
            "expected_component_count": len(expected_refs),
            "actual_component_count": len(actual_refs),
            "actual_symbol_instance_count": sum(len(items) for items in parsed.instances_by_ref.values()),
            "missing_refs": missing_refs,
            "extra_refs": extra_refs[:100],
            "extra_refs_truncated": len(extra_refs) > 100,
            "value_mismatches": value_mismatches[:100],
            "value_mismatch_count": len(value_mismatches),
        },
        "pin_existence": {
            "ok": not missing_pins,
            "expected_endpoint_count": sum(len(members) for members in expected_nets.values()),
            "resolved_expected_endpoint_count": len(resolved),
            "missing_pin_count": len(missing_pins),
            "missing_pins": missing_pins[:100],
        },
        "physical_pin_assignment": {
            "ok": not physical_pin_conflicts,
            "conflict_count": len(physical_pin_conflicts),
            "conflicts": physical_pin_conflicts[:100],
            "conflicts_truncated": len(physical_pin_conflicts) > 100,
        },
        "expected_net_comparison": {
            "ok": not net_failures and not merged_nets and not power_ground_shorts and not floating_pins,
            "expected_net_count": len(expected_nets),
            "passed_net_count": len(passed_nets),
            "failed_net_count": len(net_failures),
            "failed_nets": net_failures[:100],
            "merged_net_count": len(merged_nets),
            "merged_nets": merged_nets[:100],
            "power_ground_short_count": len(power_ground_shorts),
            "power_ground_shorts": power_ground_shorts[:20],
            "floating_expected_pin_count": len(floating_pins),
            "floating_expected_pins": floating_pins[:100],
        },
        "wire_mode_policy": {
            "ok": not wire_mode_label_failure,
            "routing_mode": routing_mode,
            "label_count": label_count,
            "allowed_label_nets": sorted(allowed_label_nets),
            "unexpected_label_nets": unexpected_label_nets,
        },
    }
    return {
        "schema": "progen-kicad-local-netlist-comparison/v0.1",
        "ok": not blocking_failures,
        "schematic": str(parsed.schematic_path),
        "kicad_cli_required": False,
        "comparison_basis": "local_kicad_sch_wire_junction_pin_graph",
        "source_reference": _source_reference_report(),
        "metrics": {
            "lib_symbol_count": len(parsed.lib_symbols),
            "wire_object_count": len(parsed.wires),
            "junction_count": len(parsed.junctions),
            "label_count": label_count,
            "actual_pin_point_count": len(parsed.actual_pins_by_point),
            "expected_component_count": len(expected_refs),
            "actual_component_count": len(actual_refs),
            "expected_net_count": len(expected_nets),
            "resolved_expected_endpoint_count": len(resolved),
            "blocking_failure_count": len(blocking_failures),
            "actual_pin_warning_count": len(actual_pin_warnings),
        },
        "checks": checks,
        "blocking_failures": blocking_failures,
        "warnings": {"actual_pins_on_expected_nets": actual_pin_warnings, "truncated": len(actual_pin_warnings) >= 100},
    }


def run_optional_kicad_erc(
    schematic_path: Path | str,
    *,
    output_json: Path | str | None = None,
    kicad_cli: str | None = None,
) -> dict[str, Any]:
    cli = kicad_cli or shutil.which("kicad-cli")
    if not cli:
        return {"available": False, "skipped": True, "reason": "kicad-cli not found"}
    schematic = Path(schematic_path)
    output = Path(output_json) if output_json else schematic.with_suffix(".erc.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        [
            cli,
            "sch",
            "erc",
            "--format",
            "json",
            "--output",
            str(output),
            "--exit-code-violations",
            str(schematic),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {}
    violations = list(report.get("violations") or [])
    for sheet in report.get("sheets") or []:
        violations.extend(sheet.get("violations") or [])
    return {
        "available": True,
        "skipped": False,
        "exit_code": process.returncode,
        "ok": process.returncode == 0,
        "stdout": process.stdout.strip(),
        "report": str(output),
        "violation_count": len(violations),
    }


def validate_schematic_netlist(
    schematic_path: Path | str,
    circuit: dict[str, Any],
    *,
    routing_mode: str = "wire",
    run_erc: bool = False,
    erc_output: Path | str | None = None,
    kicad_cli: str | None = None,
    wire_mode_terminal_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = compare_expected_netlist(
        schematic_path=schematic_path,
        circuit=circuit,
        routing_mode=routing_mode,
        wire_mode_terminal_policy=wire_mode_terminal_policy,
    )
    report["erc"] = (
        run_optional_kicad_erc(schematic_path, output_json=erc_output, kicad_cli=kicad_cli)
        if run_erc
        else {"available": bool(kicad_cli or shutil.which("kicad-cli")), "skipped": True}
    )
    return report


def write_validation_report(report: dict[str, Any], output: Path | str) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare a generated KiCad schematic against expected CircuitIR nets.")
    parser.add_argument("schematic", type=Path)
    parser.add_argument("circuit_json", type=Path)
    parser.add_argument("--routing-mode", default="wire", choices=("wire", "terminal", "combination"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-erc", action="store_true")
    parser.add_argument("--erc-output", type=Path)
    parser.add_argument("--kicad-cli")
    args = parser.parse_args()

    circuit = json.loads(args.circuit_json.read_text(encoding="utf-8"))
    report = validate_schematic_netlist(
        args.schematic,
        circuit,
        routing_mode=args.routing_mode,
        run_erc=args.run_erc,
        erc_output=args.erc_output,
        kicad_cli=args.kicad_cli,
    )
    if args.output:
        write_validation_report(report, args.output)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
