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

from .arrangement_decider import decide_arrangement, extract_connection_nets
from .beautifier import apply_coordinate_edits
from .final_circuit_builder import STAGE_REPORT_WIRE_CONFIG, _final_json_files, placer_ready_circuit
from .kicad_symbol_library import KiCadSymbolLibrary, _balanced_block, _child_head, _direct_child_blocks
from .placement_catalog import CatalogPlacementPlan, PlacedCatalogComponent, resolve_placement_spec
from .placement_project_writer import write_placement_project
from .placer_pipeline import run_placer_pipeline
from .wire_geometry_validator import AllowedTouch, ComponentBody, WireGeometrySegment, validate_wire_geometry
from .wire_planner import LABEL_STRATEGIES, normalize_routing_mode, plan_partial_route_component_moves, plan_wire_routes, plan_wiring


WIRE_MAKER_VERSION = "progen-kicad-wire-maker/v0.1"
POWER_LABEL_NETS = {"GND", "0", "VSS", "+5V", "5V", "+3V3", "3V3", "VCC", "VDD", "VIN", "VBUS"}
UNROUTED_STRATEGY_PREFIXES = ("unroutable", "deferred")
MAX_ACTUAL_PATH_CANDIDATES = 160


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


def _resolve_component_pin_point(
    *,
    ref: str,
    pin: str,
    component: PlacedCatalogComponent | None,
    library: KiCadSymbolLibrary,
    pin_cache: dict[str, tuple[PinGeometry, ...]],
    unit_count_cache: dict[str, int],
) -> tuple[tuple[float, float] | None, str, PinGeometry | None]:
    if component is None or not component.spec.lib_id:
        return None, "component_or_lib_id_missing", None
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
        return None, status, None
    return _pin_world(component, geometry, unit_count_cache.get(lib_id, 1)), "resolved", geometry


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


def _pin_side_from_rotation(rotation: float) -> str:
    angle = round(float(rotation)) % 360
    if angle == 0:
        return "left"
    if angle == 90:
        return "bottom"
    if angle == 180:
        return "right"
    if angle == 270:
        return "top"
    return ""


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


def _catalog_plan_as_routing_placement(circuit: dict[str, Any], placement: CatalogPlacementPlan) -> dict[str, Any]:
    """Build a pure-JSON routing input with KiCad-resolved pins and bodies."""
    library = KiCadSymbolLibrary()
    components = _component_lookup(placement)
    pin_cache: dict[str, tuple[PinGeometry, ...]] = {}
    unit_count_cache: dict[str, int] = {}
    pin_points: dict[str, dict[str, dict[str, Any]]] = {}
    unresolved: list[dict[str, Any]] = []
    resolved_count = 0

    for _net, endpoints in extract_connection_nets(circuit).items():
        for endpoint in endpoints:
            ref = str(endpoint.ref)
            pin = str(endpoint.pin)
            point, status, geometry = _resolve_component_pin_point(
                ref=ref,
                pin=pin,
                component=components.get(ref),
                library=library,
                pin_cache=pin_cache,
                unit_count_cache=unit_count_cache,
            )
            if point is None:
                unresolved.append({"ref": ref, "pin": pin, "reason": status})
                continue
            component = components[ref]
            source = f"{component.spec.lib_id}:unit{geometry.unit}:pin{geometry.number}" if geometry else "kicad_symbol_pin"
            pin_points.setdefault(ref, {})[pin] = {
                "point": [round(point[0], 3), round(point[1], 3)],
                "source": source,
                "side": _pin_side_from_rotation(geometry.rotation) if geometry else "",
                "resolved_pin_number": geometry.number if geometry else "",
                "resolved_pin_name": geometry.name if geometry else "",
            }
            resolved_count += 1

    body_items = []
    for index, body in enumerate(_component_bodies(placement, library), 1):
        body_items.append(
            {
                "owner": f"{body.ref}::body{index}",
                "component_ref": body.ref,
                "left": body.left,
                "top": body.top,
                "right": body.right,
                "bottom": body.bottom,
                "source": body.source,
            }
        )
    overlap_report = component_body_overlap_report(body_items)

    component_items = {
        component.ref: {
            "kind": component.kind,
            "name": component.name,
            "at": [component.at[0], component.at[1]],
            "rotation": component.rotation,
            "width": component.spec.width,
            "height": component.spec.height,
        }
        for component in placement.components
    }
    return {
        "schema": "progen-kicad-routing-placement/v0.1",
        "stage": "kicad_routing_input_builder",
        "components": component_items,
        "obstacles": body_items,
        "pin_points": pin_points,
        "routing_metadata": {
            "pin_point_source": "KiCad embedded/source symbol library pin coordinates",
            "body_source": "KiCad symbol graphics bounds with fallback placement specs",
            "pin_resolved_count": resolved_count,
            "unresolved_pin_count": len(unresolved),
            "unresolved_pins": unresolved[:200],
            "unresolved_pin_report_truncated": len(unresolved) > 200,
            "component_body_overlap_ok": bool(overlap_report["ok"]),
            "component_body_overlap_count": int(overlap_report["overlap_count"]),
            "component_body_overlaps": overlap_report["overlaps"],
        },
    }


def _orthogonal_points(start: tuple[float, float], end: tuple[float, float]) -> list[tuple[float, float]]:
    if start == end:
        return [start]
    if start[0] == end[0] or start[1] == end[1]:
        return [start, end]
    return [start, (end[0], start[1]), end]


def _segments_from_points(points: list[tuple[float, float]]) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    return [(a, b) for a, b in zip(points, points[1:]) if a != b]


def _segment_axis(segment: WireGeometrySegment, eps: float = 0.001) -> tuple[str, float, float, float] | None:
    if abs(segment.start[1] - segment.end[1]) <= eps:
        low, high = sorted((segment.start[0], segment.end[0]))
        return ("h", round(segment.start[1], 3), round(low, 3), round(high, 3))
    if abs(segment.start[0] - segment.end[0]) <= eps:
        low, high = sorted((segment.start[1], segment.end[1]))
        return ("v", round(segment.start[0], 3), round(low, 3), round(high, 3))
    return None


def _unique_allowed_touches(items: list[AllowedTouch]) -> tuple[AllowedTouch, ...]:
    seen: set[tuple[str, tuple[float, float]]] = set()
    out: list[AllowedTouch] = []
    for item in items:
        key = (item.ref, (round(item.point[0], 3), round(item.point[1], 3)))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return tuple(out)


def _merged_segment(
    *,
    net: str,
    orientation: str,
    fixed: float,
    low: float,
    high: float,
    allowed_touches: tuple[AllowedTouch, ...],
    source: str,
) -> WireGeometrySegment:
    if orientation == "h":
        start = (round(low, 3), fixed)
        end = (round(high, 3), fixed)
    else:
        start = (fixed, round(low, 3))
        end = (fixed, round(high, 3))
    return WireGeometrySegment(net=net, start=start, end=end, allowed_touches=allowed_touches, source=source)


def _merge_same_net_collinear_segments(segments: list[WireGeometrySegment]) -> list[WireGeometrySegment]:
    buckets: dict[tuple[str, str, float], list[tuple[float, float, WireGeometrySegment]]] = {}
    passthrough: list[WireGeometrySegment] = []
    for segment in segments:
        axis = _segment_axis(segment)
        if axis is None:
            passthrough.append(segment)
            continue
        orientation, fixed, low, high = axis
        if abs(high - low) <= 0.001:
            continue
        buckets.setdefault((segment.net, orientation, fixed), []).append((low, high, segment))

    merged = list(passthrough)
    for (net, orientation, fixed), records in sorted(buckets.items(), key=lambda item: item[0]):
        records.sort(key=lambda item: (item[0], item[1], item[2].source))
        current_low: float | None = None
        current_high: float | None = None
        current_touches: list[AllowedTouch] = []
        current_sources: list[str] = []

        def flush() -> None:
            if current_low is None or current_high is None:
                return
            source = current_sources[0] if len(set(current_sources)) == 1 else "merged_same_net_collinear"
            merged.append(
                _merged_segment(
                    net=net,
                    orientation=orientation,
                    fixed=fixed,
                    low=current_low,
                    high=current_high,
                    allowed_touches=_unique_allowed_touches(current_touches),
                    source=source,
                )
            )

        for low, high, segment in records:
            if current_low is None or current_high is None:
                current_low = low
                current_high = high
                current_touches = list(segment.allowed_touches)
                current_sources = [segment.source]
                continue
            if low < current_high - 0.001:
                current_high = max(current_high, high)
                current_touches.extend(segment.allowed_touches)
                current_sources.append(segment.source)
                continue
            flush()
            current_low = low
            current_high = high
            current_touches = list(segment.allowed_touches)
            current_sources = [segment.source]
        flush()
    return sorted(merged, key=lambda item: (item.net, item.start[1], item.start[0], item.end[1], item.end[0], item.source))


def _point_on_wire_segment(point: tuple[float, float], segment: WireGeometrySegment, eps: float = 0.001) -> bool:
    if abs(segment.start[1] - segment.end[1]) <= eps:
        low, high = sorted((segment.start[0], segment.end[0]))
        return abs(point[1] - segment.start[1]) <= eps and low - eps <= point[0] <= high + eps
    if abs(segment.start[0] - segment.end[0]) <= eps:
        low, high = sorted((segment.start[1], segment.end[1]))
        return abs(point[0] - segment.start[0]) <= eps and low - eps <= point[1] <= high + eps
    return False


def _point_distance_on_segment(origin: tuple[float, float], point: tuple[float, float]) -> float:
    return abs(origin[0] - point[0]) + abs(origin[1] - point[1])


def _segment_endpoint(point: tuple[float, float], segment: WireGeometrySegment) -> bool:
    rounded = _round_wire_point(point)
    return rounded == _round_wire_point(segment.start) or rounded == _round_wire_point(segment.end)


def _segment_pin_touch(point: tuple[float, float], segment: WireGeometrySegment) -> bool:
    rounded = _round_wire_point(point)
    return any(rounded == _round_wire_point(allowed.point) for allowed in segment.allowed_touches)


def _cross_net_hard_contacts(
    left: WireGeometrySegment,
    right: WireGeometrySegment,
) -> list[tuple[float, float] | tuple[tuple[float, float], tuple[float, float]]]:
    if left.net == right.net:
        return []
    left_axis = _segment_axis(left)
    right_axis = _segment_axis(right)
    if left_axis is None or right_axis is None:
        return []

    left_orientation, left_fixed, left_low, left_high = left_axis
    right_orientation, right_fixed, right_low, right_high = right_axis
    if left_orientation == right_orientation:
        if abs(left_fixed - right_fixed) > 0.001:
            return []
        low = max(left_low, right_low)
        high = min(left_high, right_high)
        if low > high + 0.001:
            return []
        if abs(low - high) <= 0.001:
            point = (round(low, 3), left_fixed) if left_orientation == "h" else (left_fixed, round(low, 3))
            return [point]
        start = (round(low, 3), left_fixed) if left_orientation == "h" else (left_fixed, round(low, 3))
        end = (round(high, 3), left_fixed) if left_orientation == "h" else (left_fixed, round(high, 3))
        return [(start, end)]

    horizontal = left if left_orientation == "h" else right
    vertical = right if left_orientation == "h" else left
    point = (round(vertical.start[0], 3), round(horizontal.start[1], 3))
    if not _point_on_wire_segment(point, horizontal) or not _point_on_wire_segment(point, vertical):
        return []

    horizontal_interior = not _segment_endpoint(point, horizontal)
    vertical_interior = not _segment_endpoint(point, vertical)
    if horizontal_interior and vertical_interior and not (
        _segment_pin_touch(point, horizontal) or _segment_pin_touch(point, vertical)
    ):
        return []
    return [point]


def _candidate_creates_cross_net_endpoint_touch(
    candidate_segments: list[WireGeometrySegment],
    existing_segments: list[WireGeometrySegment],
) -> bool:
    for candidate in candidate_segments:
        for existing in existing_segments:
            if _cross_net_hard_contacts(candidate, existing):
                return True
    return False


def _trim_dangling_wire_tails(
    segments: list[WireGeometrySegment],
    protected_points: set[tuple[float, float]],
) -> tuple[list[WireGeometrySegment], int]:
    trimmed: list[WireGeometrySegment] = []
    trim_count = 0
    rounded_protected = {(round(point[0], 3), round(point[1], 3)) for point in protected_points}

    def is_protected(point: tuple[float, float]) -> bool:
        return (round(point[0], 3), round(point[1], 3)) in rounded_protected

    for index, segment in enumerate(segments):
        start = segment.start
        end = segment.end
        for endpoint_name in ("start", "end"):
            endpoint = start if endpoint_name == "start" else end
            if is_protected(endpoint):
                continue
            touches_other = any(
                other_index != index
                and other.net == segment.net
                and _point_on_wire_segment(endpoint, other)
                for other_index, other in enumerate(segments)
            )
            if touches_other:
                continue
            candidates: set[tuple[float, float]] = set()
            for other_index, other in enumerate(segments):
                if other_index == index or other.net != segment.net:
                    continue
                for point in (other.start, other.end):
                    rounded = (round(point[0], 3), round(point[1], 3))
                    if rounded != endpoint and _point_on_wire_segment(rounded, segment):
                        candidates.add(rounded)
            for point in rounded_protected:
                if point != endpoint and _point_on_wire_segment(point, segment):
                    candidates.add(point)
            if not candidates:
                continue
            replacement = min(candidates, key=lambda point: _point_distance_on_segment(endpoint, point))
            if endpoint_name == "start":
                start = replacement
            else:
                end = replacement
            trim_count += 1
        if start != end:
            trimmed.append(
                WireGeometrySegment(
                    net=segment.net,
                    start=start,
                    end=end,
                    allowed_touches=segment.allowed_touches,
                    source=segment.source,
                )
            )
    return trimmed, trim_count


def component_body_overlap_report(
    obstacles: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    clearance: float = 0.0,
) -> dict[str, Any]:
    """Report cross-component body overlaps from placement/routing obstacle JSON."""
    pairs: list[dict[str, Any]] = []
    normalized: list[dict[str, Any]] = []
    for item in obstacles:
        if not isinstance(item, dict):
            continue
        owner = str(item.get("owner") or "")
        ref = str(item.get("component_ref") or owner)
        if "::" in ref:
            ref = ref.split("::", 1)[0]
        if not owner or not ref:
            continue
        normalized.append(
            {
                "owner": owner,
                "component_ref": ref,
                "left": float(item.get("left", 0.0)) - clearance,
                "top": float(item.get("top", 0.0)) - clearance,
                "right": float(item.get("right", 0.0)) + clearance,
                "bottom": float(item.get("bottom", 0.0)) + clearance,
            }
        )

    for index, left in enumerate(normalized):
        for right in normalized[index + 1 :]:
            if left["component_ref"] == right["component_ref"]:
                continue
            if (
                left["left"] < right["right"]
                and left["right"] > right["left"]
                and left["top"] < right["bottom"]
                and left["bottom"] > right["top"]
            ):
                pairs.append(
                    {
                        "left": left["owner"],
                        "right": right["owner"],
                        "left_component": left["component_ref"],
                        "right_component": right["component_ref"],
                    }
                )
    return {
        "schema": "progen-kicad-component-body-overlap-report/v0.1",
        "ok": not pairs,
        "clearance": clearance,
        "body_count": len(normalized),
        "overlap_count": len(pairs),
        "overlaps": pairs[:200],
        "overlaps_truncated": len(pairs) > 200,
    }


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


def _compress_wire_path(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        rounded = _round_wire_point(point)
        if deduped and rounded == deduped[-1]:
            continue
        deduped.append(rounded)
    changed = True
    while changed:
        changed = False
        compressed: list[tuple[float, float]] = []
        for point in deduped:
            compressed.append(point)
            while len(compressed) >= 3:
                a, b, c = compressed[-3], compressed[-2], compressed[-1]
                if (a[0] == b[0] == c[0]) or (a[1] == b[1] == c[1]):
                    compressed.pop(-2)
                    changed = True
                else:
                    break
        deduped = compressed
    return deduped


def _dedupe_wire_path(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for point in points:
        rounded = _round_wire_point(point)
        if not out or out[-1] != rounded:
            out.append(rounded)
    return out


def _routing_axis_limits(
    *,
    axis: str,
    start: tuple[float, float],
    end: tuple[float, float],
    existing_segments: list[WireGeometrySegment],
    component_bodies: tuple[ComponentBody, ...],
    margin: float = 76.2,
) -> tuple[float, float]:
    values = [start[0], end[0]] if axis == "x" else [start[1], end[1]]
    for body in component_bodies:
        values.extend([body.left, body.right] if axis == "x" else [body.top, body.bottom])
    for segment in existing_segments:
        values.extend([segment.start[0], segment.end[0]] if axis == "x" else [segment.start[1], segment.end[1]])
    return min(values) - margin, max(values) + margin


def _exact_lane_values(
    *,
    axis: str,
    start: tuple[float, float],
    end: tuple[float, float],
    existing_segments: list[WireGeometrySegment],
    component_bodies: tuple[ComponentBody, ...],
) -> list[float]:
    base = start[0] if axis == "x" else start[1]
    target = end[0] if axis == "x" else end[1]
    values: set[float] = {base, target, (base + target) / 2}
    for delta in (2.54, 5.08, 7.62, 10.16, 15.24, -2.54, -5.08, -7.62, -10.16, -15.24):
        values.add(base + delta)
        values.add(target + delta)
    for body in component_bodies:
        if axis == "x":
            for value in (body.left - 5.08, body.right + 5.08, body.left - 10.16, body.right + 10.16):
                values.add(value)
        else:
            for value in (body.top - 5.08, body.bottom + 5.08, body.top - 10.16, body.bottom + 10.16):
                values.add(value)
    for segment in existing_segments:
        value = segment.start[0] if axis == "x" else segment.start[1]
        for delta in (2.54, -2.54, 5.08, -5.08):
            values.add(value + delta)
    low_limit, high_limit = _routing_axis_limits(
        axis=axis,
        start=start,
        end=end,
        existing_segments=existing_segments,
        component_bodies=component_bodies,
    )
    return sorted(
        {round(round(value / 2.54) * 2.54, 3) for value in values if low_limit <= value <= high_limit},
        key=lambda item: (abs(item - (base + target) / 2), item),
    )


def _touch_body_candidates(touch: AllowedTouch, component_bodies: tuple[ComponentBody, ...]) -> list[ComponentBody]:
    point = _round_wire_point(touch.point)
    bodies = [body for body in component_bodies if body.ref == touch.ref]
    if not bodies:
        return []
    containing = [
        body
        for body in bodies
        if body.left - 2.54 <= point[0] <= body.right + 2.54 and body.top - 2.54 <= point[1] <= body.bottom + 2.54
    ]
    return containing or bodies


def _escape_points_for_touch(
    touch: AllowedTouch,
    target: tuple[float, float],
    component_bodies: tuple[ComponentBody, ...],
) -> list[tuple[float, float]]:
    point = _round_wire_point(touch.point)
    out: list[tuple[float, float]] = [point]
    for body in _touch_body_candidates(touch, component_bodies):
        body_center = ((body.left + body.right) / 2, (body.top + body.bottom) / 2)
        preferred = [
            (body.right + 5.08, point[1]) if point[0] >= body_center[0] else (body.left - 5.08, point[1]),
            (point[0], body.bottom + 5.08) if point[1] >= body_center[1] else (point[0], body.top - 5.08),
        ]
        candidates = preferred + [
            (body.left - 5.08, point[1]),
            (body.right + 5.08, point[1]),
            (point[0], body.top - 5.08),
            (point[0], body.bottom + 5.08),
        ]
        candidates.sort(key=lambda candidate: (abs(candidate[0] - target[0]) + abs(candidate[1] - target[1]), candidate[1], candidate[0]))
        for candidate in candidates:
            rounded = _round_wire_point(candidate)
            if rounded not in out:
                out.append(rounded)
    return out[:5]


def _core_candidate_actual_paths(
    start: tuple[float, float],
    end: tuple[float, float],
    existing_segments: list[WireGeometrySegment],
    component_bodies: tuple[ComponentBody, ...],
) -> list[list[tuple[float, float]]]:
    candidates: list[list[tuple[float, float]]] = [
        _compress_wire_path(_orthogonal_points(start, end)),
        _compress_wire_path([start, (end[0], start[1]), end]),
        _compress_wire_path([start, (start[0], end[1]), end]),
    ]
    x_lanes = _exact_lane_values(axis="x", start=start, end=end, existing_segments=existing_segments, component_bodies=component_bodies)
    y_lanes = _exact_lane_values(axis="y", start=start, end=end, existing_segments=existing_segments, component_bodies=component_bodies)
    for lane_y in y_lanes[:32]:
        candidates.append(_compress_wire_path([start, (start[0], lane_y), (end[0], lane_y), end]))
    for lane_x in x_lanes[:32]:
        candidates.append(_compress_wire_path([start, (lane_x, start[1]), (lane_x, end[1]), end]))
    for lane_x in x_lanes[:12]:
        for lane_y in y_lanes[:12]:
            candidates.append(_compress_wire_path([start, (lane_x, start[1]), (lane_x, lane_y), (end[0], lane_y), end]))
            candidates.append(_compress_wire_path([start, (start[0], lane_y), (lane_x, lane_y), (lane_x, end[1]), end]))
    return candidates


def _candidate_actual_paths(
    original: list[tuple[float, float]],
    start: tuple[float, float],
    end: tuple[float, float],
    allowed_touches: tuple[AllowedTouch, ...],
    existing_segments: list[WireGeometrySegment],
    component_bodies: tuple[ComponentBody, ...],
) -> list[list[tuple[float, float]]]:
    candidates: list[list[tuple[float, float]]] = [_compress_wire_path(original)]
    start_touch = allowed_touches[0] if allowed_touches else AllowedTouch("", start)
    end_touch = allowed_touches[1] if len(allowed_touches) > 1 else AllowedTouch("", end)
    start_exits = _escape_points_for_touch(start_touch, end, component_bodies)[:3]
    end_exits = _escape_points_for_touch(end_touch, start, component_bodies)[:3]
    for start_exit in start_exits:
        for end_exit in end_exits:
            for core in _core_candidate_actual_paths(start_exit, end_exit, existing_segments, component_bodies):
                prefix = [start] if start_exit == start else [start, start_exit]
                suffix = [end] if end_exit == end else [end_exit, end]
                candidates.append(_dedupe_wire_path(prefix + core[1:-1] + suffix))
                if len(candidates) >= MAX_ACTUAL_PATH_CANDIDATES:
                    break
            if len(candidates) >= MAX_ACTUAL_PATH_CANDIDATES:
                break
        if len(candidates) >= MAX_ACTUAL_PATH_CANDIDATES:
            break

    seen: set[tuple[tuple[float, float], ...]] = set()
    out: list[list[tuple[float, float]]] = []
    for candidate in candidates:
        key = tuple(candidate)
        if len(candidate) < 2 or key in seen:
            continue
        seen.add(key)
        out.append(candidate)
        if len(out) >= MAX_ACTUAL_PATH_CANDIDATES:
            break
    return out


def _validated_actual_path(
    *,
    net: str,
    original: list[tuple[float, float]],
    start: tuple[float, float],
    end: tuple[float, float],
    allowed_touches: tuple[AllowedTouch, ...],
    existing_segments: list[WireGeometrySegment],
    component_bodies: tuple[ComponentBody, ...],
    protected_pin_points: dict[tuple[float, float], set[str]],
    source: str,
) -> tuple[list[tuple[float, float]], bool, bool]:
    best_path = _compress_wire_path(original)
    best_violation_count: int | None = None
    best_length = float("inf")
    for candidate in _candidate_actual_paths(best_path, start, end, allowed_touches, existing_segments, component_bodies):
        candidate_allowed_points = {(round(allowed.point[0], 3), round(allowed.point[1], 3)) for allowed in allowed_touches}
        touches_wrong_pin = False
        for a, b in _segments_from_points(candidate):
            probe_segment = WireGeometrySegment(net=net, start=a, end=b, allowed_touches=allowed_touches, source=source)
            for pin_point, pin_nets in protected_pin_points.items():
                if net in pin_nets or pin_point in candidate_allowed_points:
                    continue
                if _point_on_wire_segment(pin_point, probe_segment):
                    touches_wrong_pin = True
                    break
            if touches_wrong_pin:
                break
        if touches_wrong_pin:
            continue
        candidate_segments = [
            WireGeometrySegment(net=net, start=a, end=b, allowed_touches=allowed_touches, source=source)
            for a, b in _segments_from_points(candidate)
        ]
        if _candidate_creates_cross_net_endpoint_touch(candidate_segments, existing_segments):
            continue
        report = validate_wire_geometry(candidate_segments, component_bodies)
        length = sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in _segments_from_points(candidate))
        violation_count = int(report.get("violation_count", 0))
        if report["ok"]:
            return candidate, candidate != best_path, True
        if best_violation_count is None or (violation_count, length) < (best_violation_count, best_length):
            best_path = candidate
            best_violation_count = violation_count
            best_length = length
    return best_path, best_path != _compress_wire_path(original), False


def _label_justify(anchor: tuple[float, float], label: tuple[float, float]) -> str:
    return "right bottom" if label[0] < anchor[0] else "left bottom"


def _side_vector(side: str) -> tuple[float, float]:
    normalized = side.lower().strip()
    if normalized == "left":
        return (-1.0, 0.0)
    if normalized == "right":
        return (1.0, 0.0)
    if normalized == "top":
        return (0.0, -1.0)
    if normalized == "bottom":
        return (0.0, 1.0)
    return (1.0, 0.0)


def _label_direction(
    pin_point: tuple[float, float],
    label_point: tuple[float, float],
    side: str,
) -> tuple[float, float]:
    dx = round(label_point[0] - pin_point[0], 3)
    dy = round(label_point[1] - pin_point[1], 3)
    if dx == 0.0 and dy == 0.0:
        return _side_vector(side)
    if abs(dx) >= abs(dy) and dx != 0.0:
        return (1.0 if dx > 0 else -1.0, 0.0)
    if dy != 0.0:
        return (0.0, 1.0 if dy > 0 else -1.0)
    return _side_vector(side)


def _reserved_label_point(
    *,
    net: str,
    ref: str,
    pin_point: tuple[float, float],
    raw_label: tuple[float, float],
    side: str,
    used_label_points: dict[tuple[float, float], str],
    existing_segments: list[WireGeometrySegment],
    component_bodies: tuple[ComponentBody, ...],
) -> tuple[tuple[float, float], bool]:
    candidate = raw_label
    owner = used_label_points.get(candidate)
    if owner in (None, net):
        used_label_points[candidate] = net
        return candidate, False

    primary = _label_direction(pin_point, raw_label, side)
    directions = [primary, (1.0, 0.0), (-1.0, 0.0), (0.0, -1.0), (0.0, 1.0)]
    unique_directions: list[tuple[float, float]] = []
    for direction in directions:
        if direction not in unique_directions:
            unique_directions.append(direction)

    for step in range(1, 9):
        for direction in unique_directions:
            candidate = (
                round(pin_point[0] + direction[0] * 2.54 * step, 3),
                round(pin_point[1] + direction[1] * 2.54 * step, 3),
            )
            if used_label_points.get(candidate) not in (None, net):
                continue
            candidate_segment = WireGeometrySegment(
                net=net,
                start=pin_point,
                end=candidate,
                allowed_touches=(AllowedTouch(ref, pin_point),),
                source=f"{net}:reserved_label_candidate:{ref}",
            )
            report = validate_wire_geometry([candidate_segment], component_bodies)
            if report["ok"]:
                used_label_points[candidate] = net
                return candidate, True

    used_label_points[raw_label] = net
    return raw_label, False


def _point_on_visual_segment(point: tuple[float, float], segment: tuple[tuple[float, float], tuple[float, float]]) -> bool:
    a, b = segment
    if abs(a[1] - b[1]) <= 0.001:
        low, high = sorted((a[0], b[0]))
        return abs(point[1] - a[1]) <= 0.001 and low - 0.001 <= point[0] <= high + 0.001
    if abs(a[0] - b[0]) <= 0.001:
        low, high = sorted((a[1], b[1]))
        return abs(point[0] - a[0]) <= 0.001 and low - 0.001 <= point[1] <= high + 0.001
    return False


def _insert_junctions(segments: list[WireGeometrySegment]) -> list[tuple[float, float]]:
    junctions: set[tuple[float, float]] = set()
    segments_by_net: dict[str, list[WireGeometrySegment]] = {}
    for segment in segments:
        segments_by_net.setdefault(segment.net, []).append(segment)

    for net_segments in segments_by_net.values():
        endpoint_counts: dict[tuple[float, float], int] = {}
        endpoints: set[tuple[float, float]] = set()
        visual_segments = [(segment.start, segment.end) for segment in net_segments]
        for segment in net_segments:
            endpoint_counts[segment.start] = endpoint_counts.get(segment.start, 0) + 1
            endpoint_counts[segment.end] = endpoint_counts.get(segment.end, 0) + 1
            endpoints.add(segment.start)
            endpoints.add(segment.end)

        for point in endpoints:
            touching_count = 0
            interior_touch = False
            for visual_segment in visual_segments:
                if not _point_on_visual_segment(point, visual_segment):
                    continue
                touching_count += 1
                a, b = visual_segment
                if point != a and point != b:
                    interior_touch = True
            if endpoint_counts.get(point, 0) >= 3 or touching_count >= 3 or interior_touch:
                if not any(
                    other.net != net_segments[0].net and _point_on_wire_segment(point, other)
                    for other in segments
                ):
                    junctions.add(point)
    return sorted(junctions, key=lambda item: (item[1], item[0]))


class _PointUnionFind:
    def __init__(self) -> None:
        self.parent: dict[tuple[float, float], tuple[float, float]] = {}

    def make(self, point: tuple[float, float]) -> None:
        rounded = _round_wire_point(point)
        if rounded not in self.parent:
            self.parent[rounded] = rounded

    def find(self, point: tuple[float, float]) -> tuple[float, float]:
        rounded = _round_wire_point(point)
        self.make(rounded)
        parent = self.parent[rounded]
        if parent != rounded:
            self.parent[rounded] = self.find(parent)
        return self.parent[rounded]

    def union(self, left: tuple[float, float], right: tuple[float, float]) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _round_wire_point(point: tuple[float, float]) -> tuple[float, float]:
    return (round(point[0], 3), round(point[1], 3))


def _wire_plan_routing_mode(wire_plan: dict[str, Any]) -> str:
    raw = wire_plan.get("routing_mode")
    if raw is None:
        raw = wire_plan.get("decision", {}).get("routing_mode") if isinstance(wire_plan.get("decision"), dict) else None
    return normalize_routing_mode(raw or "wire")


def _strict_wire_connectivity_report(
    wire_plan: dict[str, Any],
    geometry_segments: list[WireGeometrySegment],
    endpoint_point: Any,
) -> dict[str, Any]:
    violations: list[dict[str, Any]] = []
    checked_nets = 0
    connected_nets = 0
    routing_mode = _wire_plan_routing_mode(wire_plan)
    label_strategy_count = 0
    unrouted_net_count = 0
    partial_wire_net_count = 0

    segments_by_net: dict[str, list[WireGeometrySegment]] = {}
    for segment in geometry_segments:
        segments_by_net.setdefault(segment.net, []).append(segment)

    for net, net_data in wire_plan.get("nets", {}).items():
        if not isinstance(net_data, dict):
            continue
        net_name = str(net)
        strategy = str(net_data.get("strategy") or "")
        endpoints = [item for item in net_data.get("endpoints", []) if isinstance(item, dict)]
        if strategy in LABEL_STRATEGIES:
            label_strategy_count += 1
            if routing_mode == "wire":
                violations.append(
                    {
                        "rule": "wire_mode_forbids_terminal_label_strategy",
                        "net": net_name,
                        "strategy": strategy,
                    }
                )
        if strategy.startswith(UNROUTED_STRATEGY_PREFIXES):
            unrouted_net_count += 1
            violations.append(
                {
                    "rule": "expected_net_has_no_complete_wire_route",
                    "net": net_name,
                    "strategy": strategy,
                    "failure_warnings": net_data.get("failure_warnings", []),
                }
            )
            continue
        if len(endpoints) < 2:
            violations.append({"rule": "expected_net_has_fewer_than_two_endpoints", "net": net_name, "strategy": strategy})
            continue
        if strategy == "partial_wire":
            partial_wire_net_count += 1
            violations.append(
                {
                    "rule": "expected_net_has_partial_wire_route",
                    "net": net_name,
                    "strategy": strategy,
                    "unrouted_endpoint_count": net_data.get("unrouted_endpoint_count"),
                    "failure_warnings": net_data.get("failure_warnings", []),
                }
            )
        elif strategy != "wire":
            if routing_mode == "wire":
                violations.append({"rule": "wire_mode_requires_wire_strategy", "net": net_name, "strategy": strategy})
            continue

        checked_nets += 1
        net_segments = segments_by_net.get(net_name, [])
        if not net_segments:
            violations.append({"rule": "expected_net_has_no_wire_segments", "net": net_name})
            continue

        uf = _PointUnionFind()
        for segment in net_segments:
            uf.union(segment.start, segment.end)
        for index, left in enumerate(net_segments):
            for right in net_segments[index + 1 :]:
                for point in _same_net_touch_points(left, right):
                    uf.union(point, left.start)
                    uf.union(point, left.end)
                    uf.union(point, right.start)
                    uf.union(point, right.end)

        endpoint_points: list[tuple[str, tuple[float, float]]] = []
        for endpoint in endpoints:
            point = endpoint_point(endpoint)
            rounded = _round_wire_point(point)
            endpoint_points.append((f"{endpoint.get('ref')}.{endpoint.get('pin')}", rounded))
            touches = [segment for segment in net_segments if _point_on_wire_segment(rounded, segment)]
            if not touches:
                violations.append(
                    {
                        "rule": "endpoint_pin_not_on_any_wire_segment",
                        "net": net_name,
                        "endpoint": endpoint_points[-1][0],
                        "point": [rounded[0], rounded[1]],
                    }
                )
                continue
            for segment in touches:
                uf.union(rounded, segment.start)
                uf.union(rounded, segment.end)

        if endpoint_points:
            roots = {uf.find(point) for _name, point in endpoint_points}
            if len(roots) == 1:
                connected_nets += 1
            else:
                violations.append(
                    {
                        "rule": "net_endpoints_not_connected_by_wire_graph",
                        "net": net_name,
                        "strategy": strategy,
                        "endpoint_count": len(endpoint_points),
                        "component_groups": len(roots),
                        "endpoints": [{"endpoint": name, "point": [point[0], point[1]]} for name, point in endpoint_points[:24]],
                        "endpoints_truncated": len(endpoint_points) > 24,
                    }
                )

    return {
        "schema": "progen-kicad-strict-wire-connectivity-validation/v0.1",
        "stage": "strict_wire_connectivity_validator",
        "routing_mode": routing_mode,
        "ok": not violations,
        "checked_net_count": checked_nets,
        "connected_net_count": connected_nets,
        "label_strategy_count": label_strategy_count,
        "unrouted_net_count": unrouted_net_count,
        "partial_wire_net_count": partial_wire_net_count,
        "violation_count": len(violations),
        "violations": violations[:200],
        "violations_truncated": len(violations) > 200,
    }


def _same_net_touch_points(left: WireGeometrySegment, right: WireGeometrySegment) -> list[tuple[float, float]]:
    points: set[tuple[float, float]] = set()
    for point in (left.start, left.end):
        if _point_on_wire_segment(point, right):
            points.add(_round_wire_point(point))
    for point in (right.start, right.end):
        if _point_on_wire_segment(point, left):
            points.add(_round_wire_point(point))

    left_horizontal = abs(left.start[1] - left.end[1]) <= 0.001
    right_horizontal = abs(right.start[1] - right.end[1]) <= 0.001
    if left_horizontal != right_horizontal:
        horizontal = left if left_horizontal else right
        vertical = right if left_horizontal else left
        candidate = (round(vertical.start[0], 3), round(horizontal.start[1], 3))
        if _point_on_wire_segment(candidate, horizontal) and _point_on_wire_segment(candidate, vertical):
            points.add(candidate)
    return sorted(points, key=lambda item: (item[1], item[0]))


def make_kicad_wires(
    circuit: dict[str, Any],
    placement: CatalogPlacementPlan,
    wire_plan: dict[str, Any],
) -> WireMakerResult:
    routing_mode = _wire_plan_routing_mode(wire_plan)
    library = KiCadSymbolLibrary()
    components = _component_lookup(placement)
    pin_cache: dict[str, tuple[PinGeometry, ...]] = {}
    unit_count_cache: dict[str, int] = {}
    unresolved: list[dict[str, Any]] = []
    endpoint_point_cache: dict[tuple[str, str], tuple[float, float]] = {}
    resolved_count = 0

    def endpoint_point(endpoint: dict[str, Any]) -> tuple[float, float]:
        nonlocal resolved_count
        ref = str(endpoint.get("ref") or "")
        pin = str(endpoint.get("pin") or "")
        key = (ref, pin)
        if key in endpoint_point_cache:
            return endpoint_point_cache[key]
        point, status, _geometry = _resolve_component_pin_point(
            ref=ref,
            pin=pin,
            component=components.get(ref),
            library=library,
            pin_cache=pin_cache,
            unit_count_cache=unit_count_cache,
        )
        if point is None:
            unresolved.append({"ref": ref, "pin": pin, "reason": "component_or_lib_id_missing", "fallback_point": endpoint.get("point")})
            if status != "component_or_lib_id_missing":
                unresolved[-1]["reason"] = status
                component = components.get(ref)
                if component is not None:
                    unresolved[-1]["kind"] = component.kind
            raw_point = endpoint.get("point", [0.0, 0.0])
            fallback = (round(float(raw_point[0]), 3), round(float(raw_point[1]), 3))
            endpoint_point_cache[key] = fallback
            return fallback
        resolved_count += 1
        endpoint_point_cache[key] = point
        return point

    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    geometry_segments: list[WireGeometrySegment] = []
    labels: list[dict[str, Any]] = []
    used_label_points: dict[tuple[float, float], str] = {}
    route_count = 0
    fallback_route_count = 0
    exact_path_repair_count = 0
    invalid_actual_routes: list[dict[str, Any]] = []
    label_collision_avoidance_count = 0
    deferred_nets: list[str] = []
    unrouted_nets: list[str] = []
    forbidden_label_strategy_nets: list[dict[str, str]] = []

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

    component_bodies = _component_bodies(placement, library)
    protected_pin_points: dict[tuple[float, float], set[str]] = {}
    for net, net_data in wire_plan.get("nets", {}).items():
        if not isinstance(net_data, dict):
            continue
        for endpoint in net_data.get("endpoints", []):
            if not isinstance(endpoint, dict):
                continue
            point = endpoint_point(endpoint)
            protected_pin_points.setdefault((round(point[0], 3), round(point[1], 3)), set()).add(str(net))

    for net, net_data in wire_plan.get("nets", {}).items():
        if not isinstance(net_data, dict):
            continue
        net_name = str(net)
        strategy = str(net_data.get("strategy") or "")
        endpoints = [item for item in net_data.get("endpoints", []) if isinstance(item, dict)]
        if strategy == "deferred_after_route_limit":
            deferred_nets.append(net_name)
            continue
        if strategy.startswith(UNROUTED_STRATEGY_PREFIXES):
            unrouted_nets.append(net_name)
            continue
        if strategy in LABEL_STRATEGIES:
            if routing_mode == "wire":
                forbidden_label_strategy_nets.append({"net": net_name, "strategy": strategy})
                continue
            for endpoint in endpoints:
                pin_point = endpoint_point(endpoint)
                raw_label = endpoint.get("point", [pin_point[0] + 5.08, pin_point[1]])
                ref = str(endpoint.get("ref") or "")
                label_point, label_moved = _reserved_label_point(
                    net=net_name,
                    ref=ref,
                    pin_point=pin_point,
                    raw_label=(round(float(raw_label[0]), 3), round(float(raw_label[1]), 3)),
                    side=str(endpoint.get("side") or ""),
                    used_label_points=used_label_points,
                    existing_segments=geometry_segments,
                    component_bodies=component_bodies,
                )
                if label_moved:
                    label_collision_avoidance_count += 1
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
            allowed_touches = (AllowedTouch(from_ref, start), AllowedTouch(to_ref, end))
            path, path_repaired, path_valid = _validated_actual_path(
                net=net_name,
                original=path,
                start=start,
                end=end,
                allowed_touches=allowed_touches,
                existing_segments=geometry_segments,
                component_bodies=component_bodies,
                protected_pin_points=protected_pin_points,
                source=f"{net_name}:{from_ref}->{to_ref}",
            )
            if not path_valid:
                invalid_actual_routes.append(
                    {
                        "net": net_name,
                        "from": f"{from_ref}.{raw_from.get('pin')}" if isinstance(raw_from, dict) else from_ref,
                        "to": f"{to_ref}.{raw_to.get('pin')}" if isinstance(raw_to, dict) else to_ref,
                        "reason": "no_geometry_clean_actual_path_candidate",
                    }
                )
                continue
            if path_repaired:
                exact_path_repair_count += 1
            add_segments(
                net=net_name,
                points=path,
                allowed_touches=allowed_touches,
                source=f"{net_name}:{from_ref}->{to_ref}",
            )
            route_count += 1
            if len(path) >= 3 and route.get("path"):
                planned_start = tuple(route["path"][0])
                planned_end = tuple(route["path"][-1])
                if start != planned_start or end != planned_end:
                    fallback_route_count += 1

    raw_segment_count = len(geometry_segments)
    # Do not collapse same-net collinear pieces yet. A naive merge can create a
    # long span through component bodies or across other nets even when the
    # original routed pieces were valid.
    protected_points = {
        (round(allowed.point[0], 3), round(allowed.point[1], 3))
        for segment in geometry_segments
        for allowed in segment.allowed_touches
    }
    protected_points.update((round(float(label["at"][0]), 3), round(float(label["at"][1]), 3)) for label in labels)
    geometry_segments, trimmed_wire_tail_count = _trim_dangling_wire_tails(geometry_segments, protected_points)
    segments = [(segment.start, segment.end) for segment in geometry_segments]
    merged_segment_count = 0
    junctions = _insert_junctions(geometry_segments)
    geometry_report = validate_wire_geometry(geometry_segments, component_bodies)
    strict_wire_report = _strict_wire_connectivity_report(wire_plan, geometry_segments, endpoint_point)
    if invalid_actual_routes:
        strict_wire_report = dict(strict_wire_report)
        violations = list(strict_wire_report.get("violations", []))
        violations.extend(
            {
                "rule": "wire_maker_rejected_invalid_actual_route",
                "net": item["net"],
                "from": item["from"],
                "to": item["to"],
                "reason": item["reason"],
            }
            for item in invalid_actual_routes[: max(0, 200 - len(violations))]
        )
        strict_wire_report["ok"] = False
        strict_wire_report["violation_count"] = int(strict_wire_report.get("violation_count", 0)) + len(invalid_actual_routes)
        strict_wire_report["violations"] = violations[:200]
        strict_wire_report["violations_truncated"] = bool(strict_wire_report.get("violations_truncated")) or len(violations) > 200
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
        "routing_mode": routing_mode,
        "wire_object_count": len(segments),
        "raw_wire_segment_count": raw_segment_count,
        "merged_wire_segment_count": merged_segment_count,
        "trimmed_wire_tail_count": trimmed_wire_tail_count,
        "label_count": len(labels),
        "junction_count": len(junctions),
        "routed_connection_count": route_count,
        "pin_resolved_count": resolved_count,
        "unresolved_pin_count": len(unresolved),
        "unresolved_pins": unresolved[:200],
        "unresolved_pin_report_truncated": len(unresolved) > 200,
        "fallback_route_count": fallback_route_count,
        "exact_path_repair_count": exact_path_repair_count,
        "invalid_actual_route_count": len(invalid_actual_routes),
        "invalid_actual_routes": invalid_actual_routes[:200],
        "invalid_actual_routes_truncated": len(invalid_actual_routes) > 200,
        "forbidden_label_strategy_count": len(forbidden_label_strategy_nets),
        "forbidden_label_strategy_nets": forbidden_label_strategy_nets[:200],
        "forbidden_label_strategy_report_truncated": len(forbidden_label_strategy_nets) > 200,
        "label_collision_avoidance_count": label_collision_avoidance_count,
        "deferred_net_count": len(deferred_nets),
        "deferred_nets": deferred_nets,
        "unrouted_net_count": len(unrouted_nets),
        "unrouted_nets": unrouted_nets,
        "partial_wire_net_count": int(strict_wire_report.get("partial_wire_net_count", 0)),
        "geometry_ok": bool(geometry_report["ok"]),
        "geometry_violation_count": int(geometry_report["violation_count"]),
        "wire_geometry_validator": geometry_report,
        "strict_wire_ok": bool(strict_wire_report["ok"]) if routing_mode == "wire" else True,
        "strict_wire_violation_count": int(strict_wire_report["violation_count"]),
        "strict_wire_validator": strict_wire_report,
        "partial_route_motion_repair": wire_plan.get("partial_route_motion_repair", {}),
        "wire_planner_metrics": wire_plan.get("metrics", {}),
        "wire_planner_warning_count": len(wire_plan.get("warnings", [])),
    }
    return WireMakerResult("".join(objects), report)


def _geometry_violation_net_sets(report: dict[str, Any]) -> list[set[str]]:
    groups: list[set[str]] = []
    for violation in report.get("wire_geometry_validator", {}).get("violations", []):
        if not isinstance(violation, dict):
            continue
        nets: set[str] = set()
        for key in ("segment", "left", "right", "left_segment", "right_segment"):
            segment = violation.get(key)
            if isinstance(segment, dict) and segment.get("net"):
                nets.add(str(segment["net"]))
        if nets:
            groups.append(nets)
    return groups


def _geometry_violation_nets(report: dict[str, Any]) -> set[str]:
    remaining = _geometry_violation_net_sets(report)
    chosen: set[str] = set()
    while remaining:
        counts: dict[str, int] = {}
        for group in remaining:
            for net in group:
                counts[net] = counts.get(net, 0) + 1
        if not counts:
            break
        best = sorted(counts, key=lambda net: (-counts[net], net))[0]
        chosen.add(best)
        remaining = [group for group in remaining if best not in group]
    return chosen


def _wire_plan_with_geometry_fallbacks(wire_plan: dict[str, Any], fallback_nets: set[str]) -> dict[str, Any]:
    repaired = deepcopy(wire_plan)
    nets = repaired.get("nets", {})
    if not isinstance(nets, dict):
        return repaired
    for net in sorted(fallback_nets):
        net_data = nets.get(net)
        if not isinstance(net_data, dict):
            continue
        endpoints = net_data.get("endpoints", [])
        failure_warnings = list(net_data.get("failure_warnings", [])) if isinstance(net_data.get("failure_warnings"), list) else []
        failure_warnings.append("geometry_violation_fallback: net converted to local labels after wire/body or wire/wire validation failure.")
        nets[net] = {
            "strategy": "local_labels_after_geometry_violation",
            "endpoints": endpoints if isinstance(endpoints, list) else [],
            "routes": [],
            "failure_warnings": failure_warnings[:20],
        }

    routes = [route for route in repaired.get("routes", []) if isinstance(route, dict) and str(route.get("net")) not in fallback_nets]
    repaired["routes"] = routes
    repaired.setdefault("warnings", [])
    if isinstance(repaired["warnings"], list):
        repaired["warnings"].append(
            "geometry_repair_fallback: converted nets to local labels: " + ", ".join(sorted(fallback_nets))
        )
    metrics = repaired.setdefault("metrics", {})
    if isinstance(metrics, dict):
        metrics["wired_route_count"] = len(routes)
        metrics["segment_count"] = sum(len(route.get("segments", [])) for route in routes if isinstance(route, dict))
    return repaired


def repair_wire_plan_geometry(
    circuit: dict[str, Any],
    placement: CatalogPlacementPlan,
    wire_plan: dict[str, Any],
    *,
    max_passes: int = 6,
) -> tuple[dict[str, Any], WireMakerResult]:
    repaired_plan = deepcopy(wire_plan)
    repair_passes: list[dict[str, Any]] = []
    already_fallback: set[str] = set()
    result = make_kicad_wires(circuit, placement, repaired_plan)
    if _wire_plan_routing_mode(wire_plan) == "wire":
        result.report["geometry_repair_pass_count"] = 0
        result.report["geometry_repair_passes"] = []
        result.report["geometry_repair_fallback_nets"] = []
        result.report["geometry_repair_fallback_disabled"] = "strict wire mode forbids conversion of failed wires to terminal/local-label strategy"
        return repaired_plan, result
    for pass_index in range(1, max_passes + 1):
        if result.report["geometry_ok"]:
            break
        fallback_nets = _geometry_violation_nets(result.report) - already_fallback
        if not fallback_nets:
            break
        repair_passes.append(
            {
                "pass": pass_index,
                "fallback_nets": sorted(fallback_nets),
                "geometry_violation_count_before": result.report["geometry_violation_count"],
            }
        )
        already_fallback.update(fallback_nets)
        repaired_plan = _wire_plan_with_geometry_fallbacks(repaired_plan, fallback_nets)
        result = make_kicad_wires(circuit, placement, repaired_plan)
    result.report["geometry_repair_pass_count"] = len(repair_passes)
    result.report["geometry_repair_passes"] = repair_passes
    result.report["geometry_repair_fallback_nets"] = sorted(already_fallback)
    return repaired_plan, result


def _settle_actual_symbol_body_placement(
    circuit: dict[str, Any],
    placement_dict: dict[str, Any],
    *,
    max_passes: int = 4,
) -> tuple[dict[str, Any], CatalogPlacementPlan, dict[str, Any], dict[str, Any]]:
    current = deepcopy(placement_dict)
    passes: list[dict[str, Any]] = []
    final_placement = _catalog_plan_from_placement_dict(circuit, current)
    final_routing_placement = _catalog_plan_as_routing_placement(circuit, final_placement)
    final_report = component_body_overlap_report(final_routing_placement.get("obstacles", []))

    for pass_index in range(1, max_passes + 1):
        final_placement = _catalog_plan_from_placement_dict(circuit, current)
        final_routing_placement = _catalog_plan_as_routing_placement(circuit, final_placement)
        final_report = component_body_overlap_report(final_routing_placement.get("obstacles", []))
        passes.append(
            {
                "pass": pass_index,
                "component_body_overlap_count": final_report["overlap_count"],
                "component_body_overlaps": final_report["overlaps"],
            }
        )
        if final_report["ok"]:
            break

        coordinate_plan = decide_arrangement(
            final_routing_placement,
            circuit,
            config={"component_clearance": 25.4, "column_gap": 35.56, "row_gap": 20.32},
        )
        if not coordinate_plan.get("coordinate_edits"):
            break
        current = apply_coordinate_edits(current, coordinate_plan)

    report = {
        "schema": "progen-kicad-actual-symbol-body-placement-report/v0.1",
        "ok": bool(final_report["ok"]),
        "pass_count": len(passes),
        "component_body_overlap_count": int(final_report["overlap_count"]),
        "component_body_overlaps": final_report["overlaps"],
        "passes": passes,
    }
    return current, final_placement, final_routing_placement, report


def _incomplete_wire_net_count(wire_plan: dict[str, Any]) -> int:
    metrics = wire_plan.get("metrics", {}) if isinstance(wire_plan.get("metrics"), dict) else {}
    return int(metrics.get("partial_wire_net_count", 0)) + int(metrics.get("unroutable_net_count", 0))


def _repair_strict_partial_routes_by_motion(
    circuit: dict[str, Any],
    routing_placement: dict[str, Any],
    placement: CatalogPlacementPlan,
    wire_plan: dict[str, Any],
    cfg: dict[str, Any],
    *,
    max_passes: int = 3,
) -> tuple[dict[str, Any], CatalogPlacementPlan, dict[str, Any], dict[str, Any]]:
    routing_mode = _wire_plan_routing_mode(wire_plan)
    passes: list[dict[str, Any]] = []
    current_routing_placement = routing_placement
    current_placement = placement
    current_wire_plan = wire_plan

    if routing_mode != "wire":
        report = {
            "schema": "progen-kicad-partial-route-motion-repair/v0.1",
            "stage": "partial_route_motion_repair",
            "enabled": False,
            "reason": "only strict wire mode uses partial-route component motion repair",
            "pass_count": 0,
            "passes": [],
        }
        current_wire_plan["partial_route_motion_repair"] = report
        return current_wire_plan, current_placement, current_routing_placement, report

    for pass_index in range(1, max_passes + 1):
        before_metrics = current_wire_plan.get("metrics", {}) if isinstance(current_wire_plan.get("metrics"), dict) else {}
        if _incomplete_wire_net_count(current_wire_plan) <= 0:
            break
        move_plan = plan_partial_route_component_moves(current_routing_placement, current_wire_plan, config=cfg)
        if not move_plan.get("coordinate_edits"):
            passes.append(
                {
                    "pass": pass_index,
                    "status": "no_coordinate_edits",
                    "metrics_before": before_metrics,
                    "move_plan": move_plan,
                }
            )
            break

        moved_placement = apply_coordinate_edits(current_routing_placement, move_plan)
        next_placement = _catalog_plan_from_placement_dict(circuit, moved_placement)
        next_routing_placement = _catalog_plan_as_routing_placement(circuit, next_placement)
        overlap_report = component_body_overlap_report(next_routing_placement.get("obstacles", []))
        if not overlap_report["ok"]:
            passes.append(
                {
                    "pass": pass_index,
                    "status": "rejected_component_body_overlap",
                    "metrics_before": before_metrics,
                    "move_plan": move_plan,
                    "component_body_overlap_report": overlap_report,
                }
            )
            break

        next_wire_plan = plan_wire_routes(next_routing_placement, circuit, config=cfg)
        after_metrics = next_wire_plan.get("metrics", {}) if isinstance(next_wire_plan.get("metrics"), dict) else {}
        passes.append(
            {
                "pass": pass_index,
                "status": "rerouted_after_coordinate_edits",
                "metrics_before": before_metrics,
                "metrics_after": after_metrics,
                "move_plan": move_plan,
                "component_body_overlap_report": overlap_report,
            }
        )
        current_placement = next_placement
        current_routing_placement = next_routing_placement
        current_wire_plan = next_wire_plan

    report = {
        "schema": "progen-kicad-partial-route-motion-repair/v0.1",
        "stage": "partial_route_motion_repair",
        "enabled": True,
        "pass_count": len(passes),
        "passes": passes,
        "final_metrics": current_wire_plan.get("metrics", {}),
    }
    current_wire_plan["partial_route_motion_repair"] = report
    return current_wire_plan, current_placement, current_routing_placement, report


def write_wired_project(
    circuit: dict[str, Any],
    placement: CatalogPlacementPlan,
    wire_plan: dict[str, Any],
    out_dir: Path,
    *,
    wire_result: WireMakerResult | None = None,
) -> dict[str, Any]:
    result = wire_result or make_kicad_wires(circuit, placement, wire_plan)
    manifest = write_placement_project(
        circuit,
        placement,
        out_dir,
        project_suffix="WIRED",
        mode="wired_by_kicad_wire_maker",
        note="This KiCad schematic was generated from final JSON with real embedded symbols and connection objects produced by kicad_wire_maker. In strict wire mode, local labels are forbidden and any unroutable nets are recorded in this manifest.",
        extra_schematic_objects=result.schematic_objects,
        extra_manifest={"wire_maker": result.report},
    )
    schematic = (out_dir / manifest["schematic_file"]).read_text(encoding="utf-8")
    manifest["static_checks"] = validate_schematic(schematic)
    manifest["static_checks"]["wire_maker"] = True
    from .kicad_netlist_validator import validate_schematic_netlist, write_validation_report

    local_netlist_report = validate_schematic_netlist(
        out_dir / manifest["schematic_file"],
        circuit,
        routing_mode=_wire_plan_routing_mode(wire_plan),
        run_erc=False,
    )
    local_netlist_report_path = out_dir / "local_netlist_validation_report.json"
    write_validation_report(local_netlist_report, local_netlist_report_path)
    expected_net_check = local_netlist_report.get("checks", {}).get("expected_net_comparison", {})
    physical_pin_check = local_netlist_report.get("checks", {}).get("physical_pin_assignment", {})
    manifest["local_netlist_validation"] = {
        "schema": local_netlist_report.get("schema"),
        "ok": bool(local_netlist_report.get("ok")),
        "report": local_netlist_report_path.name,
        "kicad_cli_required": bool(local_netlist_report.get("kicad_cli_required", True)),
        "blocking_failure_count": int(local_netlist_report.get("metrics", {}).get("blocking_failure_count", 0)),
        "physical_pin_conflict_count": int(physical_pin_check.get("conflict_count", 0)),
        "failed_net_count": int(expected_net_check.get("failed_net_count", 0)),
        "merged_net_count": int(expected_net_check.get("merged_net_count", 0)),
        "power_ground_short_count": int(expected_net_check.get("power_ground_short_count", 0)),
        "floating_expected_pin_count": int(expected_net_check.get("floating_expected_pin_count", 0)),
    }
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
    wire_config: dict[str, Any] | None = None,
    routing_mode: str | None = None,
) -> dict[str, Any]:
    files = _final_json_files(source)
    run_path = run_dir or _fresh_run_dir(examples_root, label)
    if run_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing wired project run folder: {run_path}")

    final_json_dir = run_path / "final_json"
    placement_input_dir = run_path / "placement_inputs"
    projects_dir = run_path / "projects"
    routing_input_dir = run_path / "routing_inputs"
    wire_plan_dir = run_path / "wire_plans"
    final_json_dir.mkdir(parents=True)
    placement_input_dir.mkdir()
    projects_dir.mkdir()
    routing_input_dir.mkdir()
    wire_plan_dir.mkdir()

    cfg: dict[str, Any] = dict(STAGE_REPORT_WIRE_CONFIG)
    if wire_config:
        cfg.update(wire_config)
    if routing_mode:
        cfg["routing_mode"] = normalize_routing_mode(routing_mode)
    cfg.setdefault("strict_forbidden_contact_filter", 0.0)

    results: list[dict[str, Any]] = []
    for source_file in files:
        circuit = json.loads(source_file.read_text(encoding="utf-8"))
        if not isinstance(circuit, dict):
            raise ValueError(f"{source_file} must contain a final CircuitIR object")
        circuit_routing = circuit.get("routing")
        if routing_mode is None and isinstance(circuit_routing, dict) and circuit_routing.get("mode"):
            cfg["routing_mode"] = normalize_routing_mode(circuit_routing.get("mode"))
        cid = str(circuit.get("circuit_id") or source_file.stem)
        stem = source_file.stem
        shutil.copy2(source_file, final_json_dir / source_file.name)

        placement_input = placer_ready_circuit(circuit)
        placement_input_path = placement_input_dir / f"{stem}_placement_input.json"
        placement_input_path.write_text(json.dumps(placement_input, indent=2), encoding="utf-8")

        ctx = run_placer_pipeline(placement_input, write_trace=False)
        placement_dict = ctx.placement_plan.as_dict()
        arrangement_cfg = dict(cfg)
        arrangement_cfg["arrangement_final_wire_route"] = 0.0
        arrangement_cfg["max_arrangement_variants"] = min(float(arrangement_cfg.get("max_arrangement_variants", 5.0)), 3.0)
        planned = plan_wiring(placement_dict, circuit, wire_config=arrangement_cfg)
        beautified = planned["routing_placement"]
        beautified, placement, routing_placement, body_overlap_report = _settle_actual_symbol_body_placement(circuit, beautified)
        wire_plan = plan_wire_routes(routing_placement, circuit, config=cfg)
        wire_plan, placement, routing_placement, partial_motion_report = _repair_strict_partial_routes_by_motion(
            circuit,
            routing_placement,
            placement,
            wire_plan,
            cfg,
        )
        final_body_overlap_report = component_body_overlap_report(routing_placement.get("obstacles", []))
        body_overlap_report = dict(body_overlap_report)
        body_overlap_report["ok"] = bool(final_body_overlap_report["ok"])
        body_overlap_report["component_body_overlap_count"] = int(final_body_overlap_report["overlap_count"])
        body_overlap_report["component_body_overlaps"] = final_body_overlap_report["overlaps"]
        (routing_input_dir / f"{stem}_routing_input.json").write_text(json.dumps(routing_placement, indent=2), encoding="utf-8")
        wire_plan["arrangement_selection"] = planned.get("arrangement_selection", {})
        wire_plan["partial_route_motion_repair"] = partial_motion_report
        wire_plan, wire_result = repair_wire_plan_geometry(circuit, placement, wire_plan)
        (wire_plan_dir / f"{stem}_wire_plan.json").write_text(json.dumps(wire_plan, indent=2), encoding="utf-8")

        project_dir = projects_dir / slugify(cid).lower()
        manifest = write_wired_project(circuit, placement, wire_plan, project_dir, wire_result=wire_result)
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
                "routing_pin_resolved_count": routing_placement["routing_metadata"]["pin_resolved_count"],
                "routing_unresolved_pin_count": routing_placement["routing_metadata"]["unresolved_pin_count"],
                "component_body_overlap_ok": bool(body_overlap_report["ok"]),
                "component_body_overlap_count": body_overlap_report["component_body_overlap_count"],
                "component_body_overlap_pass_count": body_overlap_report["pass_count"],
                "deferred_net_count": manifest["wire_maker"]["deferred_net_count"],
                "unrouted_net_count": manifest["wire_maker"]["unrouted_net_count"],
                "partial_wire_net_count": manifest["wire_maker"]["partial_wire_net_count"],
                "partial_route_motion_pass_count": int(
                    manifest["wire_maker"].get("partial_route_motion_repair", {}).get("pass_count", 0)
                )
                if isinstance(manifest["wire_maker"].get("partial_route_motion_repair"), dict)
                else 0,
                "geometry_ok": bool(manifest["wire_maker"]["geometry_ok"]),
                "geometry_violation_count": manifest["wire_maker"]["geometry_violation_count"],
                "strict_wire_ok": bool(manifest["wire_maker"]["strict_wire_ok"]),
                "strict_wire_violation_count": manifest["wire_maker"]["strict_wire_violation_count"],
                "local_netlist_ok": bool(manifest["local_netlist_validation"]["ok"]),
                "local_netlist_blocking_failure_count": manifest["local_netlist_validation"]["blocking_failure_count"],
                "local_netlist_physical_pin_conflict_count": manifest["local_netlist_validation"].get(
                    "physical_pin_conflict_count", 0
                ),
                "local_netlist_failed_net_count": manifest["local_netlist_validation"]["failed_net_count"],
                "local_netlist_merged_net_count": manifest["local_netlist_validation"]["merged_net_count"],
                "local_netlist_power_ground_short_count": manifest["local_netlist_validation"]["power_ground_short_count"],
                "local_netlist_floating_expected_pin_count": manifest["local_netlist_validation"]["floating_expected_pin_count"],
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
        "total_routing_pin_resolved": sum(int(item["routing_pin_resolved_count"]) for item in results),
        "total_routing_unresolved_pins": sum(int(item["routing_unresolved_pin_count"]) for item in results),
        "all_component_body_overlap_ok": all(item["component_body_overlap_ok"] for item in results),
        "total_component_body_overlaps": sum(int(item["component_body_overlap_count"]) for item in results),
        "total_deferred_nets": sum(int(item["deferred_net_count"]) for item in results),
        "total_unrouted_nets": sum(int(item["unrouted_net_count"]) for item in results),
        "total_partial_wire_nets": sum(int(item["partial_wire_net_count"]) for item in results),
        "total_partial_route_motion_passes": sum(int(item["partial_route_motion_pass_count"]) for item in results),
        "all_geometry_ok": all(item["geometry_ok"] for item in results),
        "total_geometry_violations": sum(int(item["geometry_violation_count"]) for item in results),
        "all_strict_wire_ok": all(item["strict_wire_ok"] for item in results),
        "total_strict_wire_violations": sum(int(item["strict_wire_violation_count"]) for item in results),
        "all_local_netlist_ok": all(item["local_netlist_ok"] for item in results),
        "total_local_netlist_blocking_failures": sum(int(item["local_netlist_blocking_failure_count"]) for item in results),
        "total_local_netlist_physical_pin_conflicts": sum(
            int(item["local_netlist_physical_pin_conflict_count"]) for item in results
        ),
        "total_local_netlist_failed_nets": sum(int(item["local_netlist_failed_net_count"]) for item in results),
        "total_local_netlist_merged_nets": sum(int(item["local_netlist_merged_net_count"]) for item in results),
        "total_local_netlist_power_ground_shorts": sum(
            int(item["local_netlist_power_ground_short_count"]) for item in results
        ),
        "total_local_netlist_floating_expected_pins": sum(
            int(item["local_netlist_floating_expected_pin_count"]) for item in results
        ),
        "wire_config": cfg,
        "results": results,
    }
    (run_path / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_path / "README.md").write_text(
        "# Final JSON To KiCad Wired Project Run\n\n"
        "This folder is an immutable generated record. It takes connected final JSON files, "
        "runs the arrangement decider, beautifier, wire planner, and KiCad wire maker, then "
        "writes openable KiCad projects with real embedded symbols plus wire objects. Terminal/local-label "
        "objects are only valid when the run is generated in terminal or combination mode.\n\n"
        "The wire planner is fed exact KiCad source-symbol pin points through `routing_inputs/` "
        "when those pins can be resolved. The wire maker uses the same source-backed KiCad pin "
        "geometry when possible. Any unresolved "
        "pin aliases, unroutable nets, strict-wire connectivity violations, local expected-net "
        "comparison failures, wire crossings, and wire/component body contacts are recorded in "
        "each project manifest.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate KiCad wired projects from final CircuitIR JSON.")
    parser.add_argument("source", help="Final JSON folder or run folder containing final_json/.")
    parser.add_argument("--examples-root", default="kicad/examples", help="Examples root for fresh wired run folders.")
    parser.add_argument("--label", default="t01_t10_connected_wired_v1", help="Label suffix for the fresh generated folder.")
    parser.add_argument("--run-dir", help="Optional explicit fresh run directory.")
    parser.add_argument("--routing-mode", choices=("wire", "terminal", "combination"), help="Override final JSON routing.mode for this run.")
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
        routing_mode=args.routing_mode,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
