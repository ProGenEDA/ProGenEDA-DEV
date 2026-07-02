"""KiCad-specific wire maker stage.

The wire planner stays EDA-agnostic and emits JSON. This module consumes that
JSON plus a KiCad placement plan and writes actual KiCad schematic wire/label
objects. It uses source-backed KiCad symbol pin geometry when the final JSON pin
names can be resolved, and records every fallback in the project manifest.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import re
import shutil
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import junction_obj, num, slugify, text_obj, uid, validate_schematic, wire_obj
from kicad.generator.orthogonal_router import Obstacle

from .arrangement_decider import decide_arrangement
from .beautifier import apply_coordinate_edits
from .final_circuit_builder import STAGE_REPORT_WIRE_CONFIG, _final_json_files, placer_ready_circuit
from .kicad_symbol_library import KiCadSymbolLibrary, _balanced_block, _child_head, _direct_child_blocks
from .placement_catalog import CatalogPlacementPlan, PlacedCatalogComponent, resolve_placement_spec
from .placement_project_writer import write_placement_project
from .placer_pipeline import run_placer_pipeline
from .wire_geometry_validator import AllowedTouch, ComponentBody, WireGeometrySegment, validate_wire_geometry
from .wire_planner import plan_wire_routes


WIRE_MAKER_VERSION = "progen-kicad-wire-maker/v0.1"
POWER_LABEL_NETS = {"GND", "0", "VSS", "+5V", "5V", "+3V3", "3V3", "VCC", "VDD", "VIN", "VBUS"}


@dataclass(frozen=True)
class PinGeometry:
    unit: int
    number: str
    name: str
    x: float
    y: float
    rotation: float


@dataclass(frozen=True)
class BodyBounds:
    left: float
    top: float
    right: float
    bottom: float


@dataclass(frozen=True)
class WireMakerResult:
    schematic_objects: str
    report: dict[str, Any]


PIN_ALIAS_BY_KIND: dict[str, dict[str, tuple[str, ...]]] = {
    "LM7805": {"IN": ("VI", "1"), "OUT": ("VO", "3"), "GND": ("GND", "2")},
    "CP_100UF": {"POS": ("1",), "NEG": ("2",)},
    "OUTPUT_CAPACITOR_BUCK": {"POS": ("1",), "NEG": ("2",)},
    "INPUT_CAPACITOR_BUCK": {"POS": ("1",), "NEG": ("2",)},
    "BME280": {"VCC": ("VDD", "VDDIO", "8", "6"), "SDA": ("SDI", "3"), "SCL": ("SCK", "4")},
    "SSD1306_OLED": {"VCC": ("VCC", "VDD", "28", "9"), "SDA": ("D1", "19"), "SCL": ("D0", "18"), "GND": ("GND", "VSS", "1", "8")},
    "ESP32_WROOM": {"3V3": ("VDD", "2"), "U0RXD": ("RXD0", "IO3", "34"), "U0TXD": ("TXD0", "IO1", "35")},
    "ARDUINO_NANO": {
        "5V": ("+5V", "27"),
        "ADC1": ("A1", "20"),
        "ADC2": ("A2", "21"),
        "ADC3": ("A3", "22"),
        "ADC4": ("A4", "23"),
        "GPIO_BTN_1": ("D4", "7"),
        "GPIO_BTN_2": ("D5", "8"),
        "GPIO_BTN_3": ("D6", "9"),
        "GPIO_BTN_4": ("D7", "10"),
        "GPIO_BTN_5": ("D8", "11"),
        "GPIO_BTN_6": ("D9", "12"),
        "GPIO_PWM_1": ("D6", "9"),
        "GPIO_PWM_2": ("D7", "10"),
        "GPIO_PWM_3": ("D8", "11"),
        "GPIO_PWM_4": ("D9", "12"),
        "GPIO_RELAY_1": ("D10", "13"),
        "GPIO_RELAY_2": ("D11", "14"),
        "GPIO_RELAY_3": ("D12", "15"),
        "GPIO_RELAY_4": ("D13", "16"),
        "GPIO_CS1": ("D10", "13"),
        "GPIO_CS2": ("D9", "12"),
        "GPIO_CS_CAN": ("D8", "11"),
        "GPIO_CAN_INT": ("D7", "10"),
        "GPIO_LATCH": ("D6", "9"),
        "GPIO_RS485_RX": ("D2", "5"),
        "GPIO_RS485_TX": ("D3", "6"),
        "GPIO_RS485_DE": ("D4", "7"),
        "GPIO_EXT_1": ("A0", "19"),
        "GPIO_EXT_2": ("A1", "20"),
        "GPIO_EXT_3": ("A2", "21"),
        "GPIO_EXT_4": ("A3", "22"),
        "GPIO_EXT_5": ("A4", "23"),
        "GPIO_EXT_6": ("A5", "24"),
        "GPIO_EXT_7": ("A6", "25"),
        "GPIO_EXT_8": ("A7", "26"),
        "GPIO_MODE_1": ("D2", "5"),
        "GPIO_MODE_2": ("D3", "6"),
        "GPIO_MODE_3": ("D4", "7"),
        "GPIO_MODE_4": ("D5", "8"),
        "GPIO_MODE_5": ("D6", "9"),
        "GPIO_MODE_6": ("D7", "10"),
        "MOSI": ("D11", "14"),
        "MISO": ("D12", "15"),
        "SCK": ("D13", "16"),
        "SDA": ("A4", "23"),
        "SCL": ("A5", "24"),
        "RX0": ("D0/RX", "2"),
        "TX0": ("D1/TX", "1"),
    },
    "W25Q64": {"CS": ("CS", "1"), "DI": ("DI", "IO0", "5"), "DO": ("DO", "IO1", "2"), "WP": ("WP", "IO2", "3"), "HOLD": ("HOLD", "RESET", "IO3", "7")},
    "RELAY_5V": {"COIL_PLUS": ("A1",), "COIL_MINUS": ("A2",), "COM": ("11",), "NC": ("12",), "NO": ("14",)},
    "RELAY": {"COIL_PLUS": ("A1",), "COIL_MINUS": ("A2",), "COM": ("11",), "NC": ("12",), "NO": ("14",)},
    "COIN_CELL_HOLDER": {"POS": ("1",), "NEG": ("2",)},
    "CR2032_BATTERY": {"POS": ("1",), "NEG": ("2",)},
    "DC_BARREL_JACK": {"POS": ("1",), "NEG": ("2",)},
    "AUDIO_INPUT_JACK": {"LEFT": ("T",), "RIGHT": ("R",), "GND": ("S",)},
    "AUDIO_JACK": {"LEFT": ("T",), "RIGHT": ("R",), "GND": ("S",)},
    "PAM8403": {
        "LIN": ("INL", "7"),
        "RIN": ("INR", "10"),
        "LOUTPLUS": ("LOUT+", "1"),
        "LOUTMINUS": ("LOUT-", "3"),
        "ROUTPLUS": ("ROUT+", "16"),
        "ROUTMINUS": ("ROUT-", "14"),
        "VCC": ("VDD", "PVDD", "4", "6", "13"),
        "GND": ("GND", "PGND", "2", "11", "15"),
    },
    "74HC595_SHIFT_REGISTER": {
        "Q0": ("QA", "15"),
        "Q1": ("QB", "1"),
        "Q2": ("QC", "2"),
        "Q3": ("QD", "3"),
        "Q4": ("QE", "4"),
        "Q5": ("QF", "5"),
        "Q6": ("QG", "6"),
        "Q7": ("QH", "7"),
        "Q7S": ("QH'", "9"),
        "SHCP": ("SRCLK", "11"),
        "STCP": ("RCLK", "12"),
        "MR": ("SRCLR", "10"),
        "OE": ("OE", "13"),
    },
    "LM358": {"IN_PLUS": ("+", "3", "5"), "IN_MINUS": ("-", "2", "6"), "OUT": ("1", "7"), "VCC": ("V+", "8"), "GND": ("V-", "4")},
    "RESISTOR_NETWORK": {"COM": ("common", "1")},
    "CH340": {"DPLUS": ("UD+", "5"), "DMINUS": ("UD-", "6"), "VDD": ("VCC", "16"), "VBUS": ("VCC", "16")},
}


def _norm_pin(value: str) -> str:
    text = str(value).upper()
    text = text.replace("+", "PLUS").replace("-", "MINUS").replace("'", "PRIME")
    text = text.replace("~", "")
    text = re.sub(r"\{|\}", "", text)
    return re.sub(r"[^A-Z0-9]+", "", text)


def _parse_pin_block(block: str, unit: int) -> PinGeometry | None:
    number = re.search(r'\(number\s+"([^"]*)"', block)
    at = re.search(r"\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)", block)
    if not number or not at:
        return None
    name = re.search(r'\(name\s+"([^"]*)"', block)
    return PinGeometry(
        unit=unit,
        number=number.group(1),
        name=name.group(1) if name else "",
        x=float(at.group(1)),
        y=float(at.group(2)),
        rotation=float(at.group(3)),
    )


def _pin_blocks(block: str) -> list[str]:
    pins: list[str] = []
    start = 0
    while True:
        index = block.find("(pin ", start)
        if index < 0:
            return pins
        pin_block = _balanced_block(block, index)
        if pin_block is None:
            start = index + 5
            continue
        pins.append(pin_block)
        start = index + len(pin_block)


def _pin_geometries(symbol_text: str) -> tuple[PinGeometry, ...]:
    geometries: list[PinGeometry] = []
    for child in _direct_child_blocks(symbol_text):
        if _child_head(child) != "symbol":
            continue
        match = re.match(r'\s*\(symbol\s+"[^"]+_(\d+)_[^"]+"', child)
        if not match:
            continue
        unit = int(match.group(1))
        for pin_block in _pin_blocks(child):
            geometry = _parse_pin_block(pin_block, unit)
            if geometry:
                geometries.append(geometry)
    if geometries:
        return tuple(geometries)
    return tuple(geometry for pin_block in _pin_blocks(symbol_text) if (geometry := _parse_pin_block(pin_block, 1)))


def _merge_bounds(left: BodyBounds | None, right: BodyBounds | None) -> BodyBounds | None:
    if left is None:
        return right
    if right is None:
        return left
    return BodyBounds(
        min(left.left, right.left),
        min(left.top, right.top),
        max(left.right, right.right),
        max(left.bottom, right.bottom),
    )


def _bounds_from_points(points: list[tuple[float, float]]) -> BodyBounds | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return BodyBounds(min(xs), min(ys), max(xs), max(ys))


def _shape_bounds(block: str) -> BodyBounds | None:
    points: list[tuple[float, float]] = []
    head = _child_head(block)
    if head == "circle":
        center = re.search(r"\(center\s+([-0-9.]+)\s+([-0-9.]+)", block)
        radius = re.search(r"\(radius\s+([-0-9.]+)", block)
        if center and radius:
            cx = float(center.group(1))
            cy = float(center.group(2))
            r = float(radius.group(1))
            points.extend([(cx - r, cy - r), (cx + r, cy + r)])
    elif head in {"rectangle", "arc"}:
        for match in re.finditer(r"\((?:start|mid|end)\s+([-0-9.]+)\s+([-0-9.]+)", block):
            points.append((float(match.group(1)), float(match.group(2))))
    elif head in {"polyline", "bezier"}:
        for match in re.finditer(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)", block):
            points.append((float(match.group(1)), float(match.group(2))))
    return _bounds_from_points(points)


def _symbol_body_bounds(symbol_text: str) -> dict[int, BodyBounds]:
    raw: dict[int, BodyBounds] = {}
    for child in _direct_child_blocks(symbol_text):
        if _child_head(child) != "symbol":
            continue
        match = re.match(r'\s*\(symbol\s+"[^"]+_(\d+)_[^"]+"', child)
        if not match:
            continue
        unit = int(match.group(1))
        bounds: BodyBounds | None = None
        for grandchild in _direct_child_blocks(child):
            bounds = _merge_bounds(bounds, _shape_bounds(grandchild))
        if bounds is not None:
            raw[unit] = bounds
    if raw:
        return raw
    bounds = None
    for child in _direct_child_blocks(symbol_text):
        bounds = _merge_bounds(bounds, _shape_bounds(child))
    return {1: bounds} if bounds is not None else {}


def _geometry_aliases(geometry: PinGeometry) -> set[str]:
    aliases = {_norm_pin(geometry.number), _norm_pin(geometry.name)}
    for piece in re.split(r"[/\\\s]+", geometry.name):
        if piece:
            aliases.add(_norm_pin(piece))
    return {alias for alias in aliases if alias}


def _unit_hint(ref: str, pin: str, geometries: tuple[PinGeometry, ...]) -> int | None:
    units = sorted({geometry.unit for geometry in geometries})
    if len(units) <= 1:
        return units[0] if units else None
    upper_ref = ref.upper()
    if upper_ref.endswith("A"):
        return 1
    if upper_ref.endswith("B"):
        return 2
    match = re.search(r"CHANNEL_?(\d+)", upper_ref)
    if match:
        index = int(match.group(1))
        return 1 if index % 2 else 2
    upper_pin = pin.upper()
    if upper_pin.startswith("U1A") or upper_pin.startswith("A."):
        return 1
    if upper_pin.startswith("U1B") or upper_pin.startswith("B."):
        return 2
    return units[0]


def _resolve_pin_geometry(
    *,
    ref: str,
    kind: str,
    pin: str,
    geometries: tuple[PinGeometry, ...],
) -> tuple[PinGeometry | None, str]:
    desired = _norm_pin(pin)
    candidates = [desired]
    for raw_key, aliases in PIN_ALIAS_BY_KIND.get(kind, {}).items():
        if _norm_pin(raw_key) == desired:
            candidates.extend(_norm_pin(alias) for alias in aliases)
            break
    unit_hint = _unit_hint(ref, pin, geometries)
    scored: list[tuple[int, PinGeometry]] = []
    for geometry in geometries:
        aliases = _geometry_aliases(geometry)
        for index, candidate in enumerate(candidates):
            if candidate in aliases:
                unit_penalty = 0 if unit_hint is None or geometry.unit == unit_hint else 10
                scored.append((unit_penalty + index, geometry))
                break
    if not scored:
        return None, "unresolved"
    scored.sort(key=lambda item: (item[0], item[1].unit, item[1].number))
    return scored[0][1], "resolved"


def _component_lookup(placement: CatalogPlacementPlan) -> dict[str, PlacedCatalogComponent]:
    return {component.ref: component for component in placement.components}


def _catalog_plan_from_placement_dict(circuit: dict[str, Any], placement: dict[str, Any]) -> CatalogPlacementPlan:
    requested: dict[str, dict[str, Any]] = {}
    for component in circuit.get("components", []):
        if isinstance(component, dict):
            ref = str(component.get("id") or component.get("ref") or "")
            if ref:
                requested[ref] = component

    placed_components: list[PlacedCatalogComponent] = []
    obstacles: list[Obstacle] = []
    raw_components = placement.get("components", {})
    if not isinstance(raw_components, dict):
        raise ValueError("placement.components must be an object")
    for ref, raw in raw_components.items():
        if not isinstance(raw, dict):
            continue
        kind = str(raw.get("kind") or requested.get(ref, {}).get("kind") or "")
        spec = resolve_placement_spec(kind)
        if spec is None:
            raise ValueError(f"{ref} uses unsupported placement kind {kind!r}")
        at = raw.get("at", [0.0, 0.0])
        x = float(at[0])
        y = float(at[1])
        component = PlacedCatalogComponent(
            ref=str(ref),
            kind=spec.kind,
            name=str(requested.get(ref, {}).get("value") or raw.get("name") or spec.name),
            at=(x, y),
            rotation=float(raw.get("rotation", 0.0)),
            manual_position=bool(raw.get("manual", False)),
            spec=spec,
        )
        placed_components.append(component)
        obstacles.append(
            Obstacle(
                str(ref),
                round(x - spec.width / 2, 3),
                round(y - spec.height / 2, 3),
                round(x + spec.width / 2, 3),
                round(y + spec.height / 2, 3),
            )
        )
    return CatalogPlacementPlan(tuple(placed_components), tuple(obstacles))


def _unit_origin(component: PlacedCatalogComponent, unit: int, unit_count: int) -> tuple[float, float]:
    x, y = component.at
    if unit_count <= 1:
        return x, y
    index = max(0, unit - 1)
    return x, round(y + index * 12.7, 3)


def _unit_position(component: PlacedCatalogComponent, geometry: PinGeometry, unit_count: int) -> tuple[float, float]:
    return _unit_origin(component, geometry.unit, unit_count)


def _local_point_to_world(
    component: PlacedCatalogComponent,
    origin: tuple[float, float],
    local: tuple[float, float],
) -> tuple[float, float]:
    angle = math.radians(component.rotation % 360)
    local_y = -local[1]
    x = local[0] * math.cos(angle) - local_y * math.sin(angle)
    y = local[0] * math.sin(angle) + local_y * math.cos(angle)
    return (round(origin[0] + x, 3), round(origin[1] + y, 3))


def _pin_world(component: PlacedCatalogComponent, geometry: PinGeometry, unit_count: int) -> tuple[float, float]:
    origin_x, origin_y = _unit_position(component, geometry, unit_count)
    return _local_point_to_world(component, (origin_x, origin_y), (geometry.x, geometry.y))


def _component_body_bounds_for_unit(raw_bounds: dict[int, BodyBounds], unit: int) -> BodyBounds | None:
    return _merge_bounds(raw_bounds.get(0), raw_bounds.get(unit))


def _fallback_component_body(component: PlacedCatalogComponent) -> ComponentBody:
    x, y = component.at
    width = max(2.54, min(component.spec.width, 25.4))
    height = max(2.54, min(component.spec.height, 25.4))
    return ComponentBody(
        component.ref,
        round(x - width / 2, 3),
        round(y - height / 2, 3),
        round(x + width / 2, 3),
        round(y + height / 2, 3),
        "fallback_placement_spec_body",
    )


def _world_component_body(
    component: PlacedCatalogComponent,
    bounds: BodyBounds,
    unit: int,
    unit_count: int,
    source: str,
) -> ComponentBody:
    origin = _unit_origin(component, unit, unit_count)
    corners = [
        _local_point_to_world(component, origin, (bounds.left, bounds.top)),
        _local_point_to_world(component, origin, (bounds.left, bounds.bottom)),
        _local_point_to_world(component, origin, (bounds.right, bounds.top)),
        _local_point_to_world(component, origin, (bounds.right, bounds.bottom)),
    ]
    xs = [point[0] for point in corners]
    ys = [point[1] for point in corners]
    return ComponentBody(
        component.ref,
        round(min(xs), 3),
        round(min(ys), 3),
        round(max(xs), 3),
        round(max(ys), 3),
        source,
    )


def _component_bodies(
    placement: CatalogPlacementPlan,
    library: KiCadSymbolLibrary,
) -> tuple[ComponentBody, ...]:
    bodies: list[ComponentBody] = []
    for component in placement.components:
        lib_id = component.spec.lib_id
        if not lib_id:
            bodies.append(_fallback_component_body(component))
            continue
        symbol = library.load(lib_id)
        raw_bounds = _symbol_body_bounds(symbol.text)
        units = tuple(sorted(symbol.unit_pin_numbers)) or (1,)
        unit_count = len(units)
        added = False
        for unit in units:
            bounds = _component_body_bounds_for_unit(raw_bounds, unit)
            if bounds is None:
                continue
            bodies.append(_world_component_body(component, bounds, unit, unit_count, f"{lib_id}:unit{unit}"))
            added = True
        if not added:
            bodies.append(_fallback_component_body(component))
    return tuple(bodies)


def _orthogonal_points(start: tuple[float, float], end: tuple[float, float]) -> list[tuple[float, float]]:
    if start == end:
        return [start]
    if start[0] == end[0] or start[1] == end[1]:
        return [start, end]
    return [start, (end[0], start[1]), end]


def _segments_from_points(points: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return [(a, b) for a, b in zip(points, points[1:]) if a != b]


def _path_with_actual_ends(
    start: tuple[float, float],
    planned: list[list[float]],
    end: tuple[float, float],
) -> list[tuple[float, float]]:
    if not planned:
        return _orthogonal_points(start, end)
    planned_points = [(round(float(point[0]), 3), round(float(point[1]), 3)) for point in planned]
    out: list[tuple[float, float]] = []
    for point in _orthogonal_points(start, planned_points[0])[:-1]:
        out.append(point)
    out.extend(planned_points)
    for point in _orthogonal_points(planned_points[-1], end)[1:]:
        out.append(point)
    deduped: list[tuple[float, float]] = []
    for point in out:
        if not deduped or point != deduped[-1]:
            deduped.append(point)
    return deduped


def _label_justify(anchor: tuple[float, float], label: tuple[float, float]) -> str:
    return "right bottom" if label[0] < anchor[0] else "left bottom"


def _insert_junctions(segments: list[tuple[tuple[float, float], tuple[float, float]]]) -> list[tuple[float, float]]:
    counts: dict[tuple[float, float], int] = {}
    for a, b in segments:
        counts[a] = counts.get(a, 0) + 1
        counts[b] = counts.get(b, 0) + 1
    return sorted((point for point, count in counts.items() if count >= 3), key=lambda item: (item[1], item[0]))


def make_kicad_wires(
    circuit: dict[str, Any],
    placement: CatalogPlacementPlan,
    wire_plan: dict[str, Any],
) -> WireMakerResult:
    library = KiCadSymbolLibrary()
    components = _component_lookup(placement)
    pin_cache: dict[str, tuple[PinGeometry, ...]] = {}
    unit_count_cache: dict[str, int] = {}
    unresolved: list[dict[str, Any]] = []
    resolved_count = 0

    def endpoint_point(endpoint: dict[str, Any]) -> tuple[float, float]:
        nonlocal resolved_count
        ref = str(endpoint.get("ref") or "")
        pin = str(endpoint.get("pin") or "")
        component = components.get(ref)
        if component is None or not component.spec.lib_id:
            unresolved.append({"ref": ref, "pin": pin, "reason": "component_or_lib_id_missing", "fallback_point": endpoint.get("point")})
            raw_point = endpoint.get("point", [0.0, 0.0])
            return (round(float(raw_point[0]), 3), round(float(raw_point[1]), 3))
        lib_id = component.spec.lib_id
        geometries = pin_cache.get(lib_id)
        if geometries is None:
            symbol = library.load(lib_id)
            geometries = _pin_geometries(symbol.text)
            pin_cache[lib_id] = geometries
            unit_pins = symbol.unit_pin_numbers
            unit_count_cache[lib_id] = len(unit_pins) if unit_pins else 1
        geometry, status = _resolve_pin_geometry(ref=ref, kind=component.kind, pin=pin, geometries=geometries)
        if geometry is None:
            unresolved.append({"ref": ref, "kind": component.kind, "pin": pin, "reason": status, "fallback_point": endpoint.get("point")})
            raw_point = endpoint.get("point", [0.0, 0.0])
            return (round(float(raw_point[0]), 3), round(float(raw_point[1]), 3))
        resolved_count += 1
        return _pin_world(component, geometry, unit_count_cache.get(lib_id, 1))

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    geometry_segments: list[WireGeometrySegment] = []
    labels: list[dict[str, Any]] = []
    route_count = 0
    fallback_route_count = 0
    deferred_nets: list[str] = []

    def add_segments(
        *,
        net: str,
        points: list[tuple[float, float]],
        allowed_touches: tuple[AllowedTouch, ...],
        source: str,
    ) -> None:
        for a, b in _segments_from_points(points):
            segments.append((a, b))
            geometry_segments.append(
                WireGeometrySegment(
                    net=net,
                    start=a,
                    end=b,
                    allowed_touches=allowed_touches,
                    source=source,
                )
            )

    for net, net_data in wire_plan.get("nets", {}).items():
        if not isinstance(net_data, dict):
            continue
        net_name = str(net)
        strategy = str(net_data.get("strategy") or "")
        endpoints = [item for item in net_data.get("endpoints", []) if isinstance(item, dict)]
        if strategy == "deferred_after_route_limit":
            deferred_nets.append(net_name)
            continue
        if strategy in {"local_labels", "single_endpoint_label"}:
            for endpoint in endpoints:
                pin_point = endpoint_point(endpoint)
                raw_label = endpoint.get("point", [pin_point[0] + 5.08, pin_point[1]])
                label_point = (round(float(raw_label[0]), 3), round(float(raw_label[1]), 3))
                label_path = _orthogonal_points(pin_point, label_point)
                add_segments(
                    net=net_name,
                    points=label_path,
                    allowed_touches=(AllowedTouch(str(endpoint.get("ref") or ""), pin_point),),
                    source=f"{net_name}:local_label:{endpoint.get('ref')}.{endpoint.get('pin')}",
                )
                labels.append({"net": net_name, "at": label_point, "anchor": pin_point})
            continue
        for route in net_data.get("routes", []):
            if not isinstance(route, dict):
                continue
            raw_from = route.get("from", {})
            raw_to = route.get("to", {})
            start = endpoint_point(raw_from)
            end = endpoint_point(raw_to)
            path = _path_with_actual_ends(start, route.get("path", []), end)
            from_ref = str(raw_from.get("ref") or "") if isinstance(raw_from, dict) else ""
            to_ref = str(raw_to.get("ref") or "") if isinstance(raw_to, dict) else ""
            add_segments(
                net=net_name,
                points=path,
                allowed_touches=(AllowedTouch(from_ref, start), AllowedTouch(to_ref, end)),
                source=f"{net_name}:{from_ref}->{to_ref}",
            )
            route_count += 1
            if len(path) >= 3 and route.get("path"):
                planned_start = tuple(route["path"][0])
                planned_end = tuple(route["path"][-1])
                if start != planned_start or end != planned_end:
                    fallback_route_count += 1

    junctions = _insert_junctions(segments)
    geometry_report = validate_wire_geometry(geometry_segments, _component_bodies(placement, library))
    project_name = str(circuit.get("project", {}).get("name") or circuit.get("circuit_id") or "wired")
    objects: list[str] = []
    for index, (a, b) in enumerate(segments, 1):
        objects.append(wire_obj(a, b, project_name, index))
    for index, point in enumerate(junctions, 1):
        objects.append(junction_obj(point, project_name, index))
    for index, label in enumerate(labels, 1):
        objects.append(text_obj(str(label["net"]), label["at"], project_name, index, "label", _label_justify(label["anchor"], label["at"])))

    report = {
        "schema": "progen-kicad-wire-maker-report/v0.1",
        "stage": "kicad_wire_maker",
        "version": WIRE_MAKER_VERSION,
        "wire_object_count": len(segments),
        "label_count": len(labels),
        "junction_count": len(junctions),
        "routed_connection_count": route_count,
        "pin_resolved_count": resolved_count,
        "unresolved_pin_count": len(unresolved),
        "unresolved_pins": unresolved[:200],
        "unresolved_pin_report_truncated": len(unresolved) > 200,
        "fallback_route_count": fallback_route_count,
        "deferred_net_count": len(deferred_nets),
        "deferred_nets": deferred_nets,
        "geometry_ok": bool(geometry_report["ok"]),
        "geometry_violation_count": int(geometry_report["violation_count"]),
        "wire_geometry_validator": geometry_report,
        "wire_planner_metrics": wire_plan.get("metrics", {}),
        "wire_planner_warning_count": len(wire_plan.get("warnings", [])),
    }
    return WireMakerResult("".join(objects), report)


def write_wired_project(
    circuit: dict[str, Any],
    placement: CatalogPlacementPlan,
    wire_plan: dict[str, Any],
    out_dir: Path,
) -> dict[str, Any]:
    result = make_kicad_wires(circuit, placement, wire_plan)
    manifest = write_placement_project(
        circuit,
        placement,
        out_dir,
        project_suffix="WIRED",
        mode="wired_by_kicad_wire_maker",
        note="This KiCad schematic was generated from final JSON with real embedded symbols and wire/label objects produced by kicad_wire_maker. Unresolved pin aliases and deferred route limits are recorded in this manifest.",
        extra_schematic_objects=result.schematic_objects,
        extra_manifest={"wire_maker": result.report},
    )
    schematic = (out_dir / manifest["schematic_file"]).read_text(encoding="utf-8")
    manifest["static_checks"] = validate_schematic(schematic)
    manifest["static_checks"]["wire_maker"] = True
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def _fresh_run_dir(examples_root: Path, label: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y_%m_%d_%H%M%S")
    base = examples_root / f"final_json_wired_project_run_{stamp}_{slugify(label).lower()}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = examples_root / f"{base.name}_{suffix}"
        suffix += 1
    return candidate


def generate_wired_projects_from_final_json(
    source: Path,
    *,
    examples_root: Path,
    label: str = "t01_t10_connected_wired_v1",
    run_dir: Path | None = None,
    wire_config: dict[str, float] | None = None,
) -> dict[str, Any]:
    files = _final_json_files(source)
    run_path = run_dir or _fresh_run_dir(examples_root, label)
    if run_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing wired project run folder: {run_path}")

    final_json_dir = run_path / "final_json"
    placement_input_dir = run_path / "placement_inputs"
    projects_dir = run_path / "projects"
    wire_plan_dir = run_path / "wire_plans"
    final_json_dir.mkdir(parents=True)
    placement_input_dir.mkdir()
    projects_dir.mkdir()
    wire_plan_dir.mkdir()

    cfg = dict(STAGE_REPORT_WIRE_CONFIG)
    if wire_config:
        cfg.update(wire_config)

    results: list[dict[str, Any]] = []
    for source_file in files:
        circuit = json.loads(source_file.read_text(encoding="utf-8"))
        if not isinstance(circuit, dict):
            raise ValueError(f"{source_file} must contain a final CircuitIR object")
        cid = str(circuit.get("circuit_id") or source_file.stem)
        stem = source_file.stem
        shutil.copy2(source_file, final_json_dir / source_file.name)

        placement_input = placer_ready_circuit(circuit)
        placement_input_path = placement_input_dir / f"{stem}_placement_input.json"
        placement_input_path.write_text(json.dumps(placement_input, indent=2), encoding="utf-8")

        ctx = run_placer_pipeline(placement_input, write_trace=False)
        placement_dict = ctx.placement_plan.as_dict()
        coordinate_plan = decide_arrangement(placement_dict, circuit)
        beautified = apply_coordinate_edits(placement_dict, coordinate_plan)
        wire_plan = plan_wire_routes(beautified, circuit, config=cfg)
        (wire_plan_dir / f"{stem}_wire_plan.json").write_text(json.dumps(wire_plan, indent=2), encoding="utf-8")
        placement = _catalog_plan_from_placement_dict(circuit, beautified)

        project_dir = projects_dir / slugify(cid).lower()
        manifest = write_wired_project(circuit, placement, wire_plan, project_dir)
        results.append(
            {
                "circuit_id": cid,
                "circuit_name": circuit.get("circuit_name"),
                "project_dir": str(project_dir.relative_to(run_path)),
                "open_this": str((project_dir / manifest["open_this"]).relative_to(run_path)),
                "schematic_file": str((project_dir / manifest["schematic_file"]).relative_to(run_path)),
                "component_count": manifest["component_count"],
                "symbol_instance_count": manifest["symbol_instance_count"],
                "wire_object_count": manifest["wire_maker"]["wire_object_count"],
                "label_count": manifest["wire_maker"]["label_count"],
                "unresolved_pin_count": manifest["wire_maker"]["unresolved_pin_count"],
                "deferred_net_count": manifest["wire_maker"]["deferred_net_count"],
                "geometry_ok": bool(manifest["wire_maker"]["geometry_ok"]),
                "geometry_violation_count": manifest["wire_maker"]["geometry_violation_count"],
                "static_checks_ok": bool(manifest["static_checks"]["ok"]),
            }
        )

    summary = {
        "schema": "progen-kicad-final-json-wired-project-run/v0.1",
        "run_dir": str(run_path),
        "label": label,
        "input_count": len(files),
        "project_count": len(results),
        "all_static_checks_ok": all(item["static_checks_ok"] for item in results),
        "total_components": sum(int(item["component_count"]) for item in results),
        "total_symbol_instances": sum(int(item["symbol_instance_count"]) for item in results),
        "total_wire_objects": sum(int(item["wire_object_count"]) for item in results),
        "total_labels": sum(int(item["label_count"]) for item in results),
        "total_unresolved_pins": sum(int(item["unresolved_pin_count"]) for item in results),
        "total_deferred_nets": sum(int(item["deferred_net_count"]) for item in results),
        "all_geometry_ok": all(item["geometry_ok"] for item in results),
        "total_geometry_violations": sum(int(item["geometry_violation_count"]) for item in results),
        "wire_config": cfg,
        "results": results,
    }
    (run_path / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_path / "README.md").write_text(
        "# Final JSON To KiCad Wired Project Run\n\n"
        "This folder is an immutable generated record. It takes connected final JSON files, "
        "runs the arrangement decider, beautifier, wire planner, and KiCad wire maker, then "
        "writes openable KiCad projects with real embedded symbols plus wire/label objects.\n\n"
        "The wire maker uses source-backed KiCad pin geometry when possible. Any unresolved "
        "pin aliases, deferred route-limit nets, wire crossings, and wire/component body "
        "contacts are recorded in each project manifest.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate KiCad wired projects from final CircuitIR JSON.")
    parser.add_argument("source", help="Final JSON folder or run folder containing final_json/.")
    parser.add_argument("--examples-root", default="kicad/examples", help="Examples root for fresh wired run folders.")
    parser.add_argument("--label", default="t01_t10_connected_wired_v1", help="Label suffix for the fresh generated folder.")
    parser.add_argument("--run-dir", help="Optional explicit fresh run directory.")
    parser.add_argument("--max-wired-routes", type=float, help="Optional route count cap passed to the wire planner.")
    parser.add_argument("--max-astar-expansions", type=float, help="Optional A* expansion cap passed to the wire planner.")
    args = parser.parse_args()
    wire_config: dict[str, float] = {}
    if args.max_wired_routes is not None:
        wire_config["max_wired_routes"] = args.max_wired_routes
    if args.max_astar_expansions is not None:
        wire_config["max_astar_expansions"] = args.max_astar_expansions
    summary = generate_wired_projects_from_final_json(
        Path(args.source),
        examples_root=Path(args.examples_root),
        label=args.label,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        wire_config=wire_config or None,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
