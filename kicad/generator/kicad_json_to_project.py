#!/usr/bin/env python3
"""CircuitIR JSON -> self-contained KiCad visual project writer."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .orthogonal_router import Obstacle, Point, RoutingResult, route_nets
from .symbol_cache import V1_KIND_LIB_IDS, extract_pin_defs, load_source_symbols
from kicad.source_pack.source_reference import load_reference

ROOT_UUID = "00000000-0000-0000-0000-000000000001"
SCH_VERSION = 20241201
GENERATOR = "progen-kicad-v1"
SOURCE_KINDS = {"VDC", "IDC", "VAC", "VSIN", "VPULSE", "ISIN", "IPULSE"}
RAIL_NETS = {"GND", "0", "VSS", "VCC", "VDD", "VIN", "+5V", "5V"}
GRID = 2.54
_LOCAL_LABEL_STUB_CACHE: dict[int, list[dict[str, Any]]] = {}


def q(value: Any) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"') + '"'


def num(value: float) -> str:
    value = round(float(value), 6)
    return str(int(value)) if value.is_integer() else f"{value:.6f}".rstrip("0").rstrip(".")


def uid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_\-]+", "_", str(name).strip())
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "generated_kicad_project"


def snap(value: float, grid: float = GRID) -> float:
    return round(round(float(value) / grid) * grid, 3)


def snap_point(point: Point, grid: float = GRID) -> Point:
    return (snap(point[0], grid), snap(point[1], grid))


def grid_remainder(value: float, grid: float = GRID) -> float:
    remainder = round(float(value) % grid, 3)
    return 0.0 if abs(remainder - grid) < 1e-6 else remainder


def shared_axis_offset(values: list[float], grid: float = GRID) -> float:
    remainders = {grid_remainder(value, grid) for value in values}
    if len(remainders) != 1:
        return 0.0
    remainder = next(iter(remainders))
    if abs(remainder) < 1e-6:
        return 0.0
    return round(grid - remainder, 3)


@dataclass(frozen=True)
class PinDef:
    number: str
    x: float
    y: float
    side: str


@dataclass(frozen=True)
class KindSpec:
    kind: str
    lib_id: str
    ref_prefix: str
    default_value: str
    pins: tuple[PinDef, ...]
    default_rotation: float
    description: str


@dataclass(frozen=True)
class Component:
    ref: str
    kind: str
    value: str
    at: Point
    rotation: float
    pins: dict[str, str]
    manual_position: bool


@dataclass(frozen=True)
class LayoutPlan:
    components: tuple[Component, ...]
    routing: RoutingResult
    obstacles: tuple[Obstacle, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "components": {
                c.ref: {"kind": c.kind, "at": list(c.at), "rotation": c.rotation, "manual": c.manual_position}
                for c in self.components
            },
            "wire_segments": [
                {"net": seg.net, "from": list(seg.a), "to": list(seg.b)} for seg in self.routing.segments
            ],
            "junctions": [list(point) for point in self.routing.junctions],
            "label_points": {net: list(point) for net, point in self.routing.label_points.items()},
            "local_label_points": [
                {"net": net, "at": list(point)} for net, point in self.routing.local_label_points
            ],
            "local_label_stubs": [
                {
                    "net": stub["net"],
                    "component": stub["component"],
                    "pin": stub["pin"],
                    "from": list(stub["from"]),
                    "to": list(stub["to"]),
                    "segments": [[list(a), list(b)] for a, b in stub["segments"]],
                }
                for stub in local_label_stubs(self)
            ],
            "no_connect_points": [
                {"component": item["component"], "pin": item["pin"], "at": list(item["at"])}
                for item in no_connect_points(self)
            ],
            "warnings": list(self.routing.warnings),
        }


def _pin_tuple(pins: dict[str, tuple[float, float]], fallback: tuple[PinDef, ...]) -> tuple[PinDef, ...]:
    if not pins:
        return fallback
    out: list[PinDef] = []
    for number in sorted(pins, key=lambda item: (len(item), item)):
        x, y = pins[number]
        if abs(x) >= abs(y):
            side = "right" if x >= 0 else "left"
        else:
            side = "bottom" if y >= 0 else "top"
        out.append(PinDef(number, x, y, side))
    return tuple(out)


def _generic_two_pin(kind: str, lib_id: str, prefix: str, value: str, desc: str, *, vertical: bool) -> KindSpec:
    pins = (
        (PinDef("1", 0, 5.08, "bottom"), PinDef("2", 0, -5.08, "top"))
        if vertical
        else (PinDef("1", -5.08, 0, "left"), PinDef("2", 5.08, 0, "right"))
    )
    return KindSpec(kind, lib_id, prefix, value, pins, 0 if vertical else 0, desc)


def _generic_three_pin(kind: str, prefix: str, value: str, desc: str) -> KindSpec:
    pins = (PinDef("1", -10.16, 0, "left"), PinDef("2", 10.16, 5.08, "right"), PinDef("3", 10.16, -5.08, "right"))
    return KindSpec(kind, f"Progen:{kind}", prefix, value, pins, 0, desc)


def _generic_multi_pin(kind: str, prefix: str, value: str, count: int, desc: str) -> KindSpec:
    left = math.ceil(count / 2)
    right = count - left
    spacing = 2.54
    pins: list[PinDef] = []
    for index in range(1, left + 1):
        y = round(((left + 1) / 2 - index) * spacing, 3)
        pins.append(PinDef(str(index), -10.16, y, "left"))
    for index in range(1, right + 1):
        y = round(((right + 1) / 2 - index) * spacing, 3)
        pins.append(PinDef(str(left + index), 10.16, y, "right"))
    return KindSpec(kind, f"Progen:{kind}", prefix, value, tuple(pins), 0, desc)


def build_kind_specs() -> tuple[dict[str, KindSpec], dict[str, str]]:
    source_symbols = load_source_symbols()
    exact_pins = {lib_id: extract_pin_defs(block.text) for lib_id, block in source_symbols.items()}
    r_fallback = (PinDef("1", 0, 3.81, "bottom"), PinDef("2", 0, -3.81, "top"))
    l_fallback = r_fallback
    source_fallback = (PinDef("1", 0, 5.08, "bottom"), PinDef("2", 0, -5.08, "top"))
    gnd_fallback = (PinDef("1", 0, 0, "center"),)

    specs = {
        "R": KindSpec(
            "R",
            V1_KIND_LIB_IDS["R"],
            "R",
            "1k",
            _pin_tuple(exact_pins.get(V1_KIND_LIB_IDS["R"], {}), r_fallback),
            90,
            "resistor",
        ),
        "L": KindSpec(
            "L",
            V1_KIND_LIB_IDS["L"],
            "L",
            "10m",
            _pin_tuple(exact_pins.get(V1_KIND_LIB_IDS["L"], {}), l_fallback),
            90,
            "inductor",
        ),
        "VDC": KindSpec(
            "VDC",
            V1_KIND_LIB_IDS["VDC"],
            "V",
            "10",
            _pin_tuple(exact_pins.get(V1_KIND_LIB_IDS["VDC"], {}), source_fallback),
            0,
            "DC voltage source",
        ),
        "VSIN": KindSpec(
            "VSIN",
            V1_KIND_LIB_IDS["VSIN"],
            "V",
            "SIN(0 1 1k)",
            _pin_tuple(exact_pins.get(V1_KIND_LIB_IDS["VSIN"], {}), source_fallback),
            0,
            "sine voltage source",
        ),
        "GND": KindSpec(
            "GND",
            V1_KIND_LIB_IDS["GND"],
            "#PWR",
            "GND",
            _pin_tuple(exact_pins.get(V1_KIND_LIB_IDS["GND"], {}), gnd_fallback),
            0,
            "ground",
        ),
        "C": KindSpec(
            "C",
            "Progen:C",
            "C",
            "100n",
            (PinDef("1", 0, 5.08, "top"), PinDef("2", 0, -5.08, "bottom")),
            0,
            "capacitor",
        ),
        "IDC": KindSpec(
            "IDC",
            "Progen:IDC",
            "I",
            "1m",
            (PinDef("1", 0, 5.08, "bottom"), PinDef("2", 0, -5.08, "top")),
            0,
            "DC current source",
        ),
        "VAC": KindSpec(
            "VAC",
            "Progen:VAC",
            "V",
            "AC 1",
            (PinDef("1", 0, 5.08, "bottom"), PinDef("2", 0, -5.08, "top")),
            0,
            "AC voltage source",
        ),
    }
    for kind, prefix, value, desc in (
        ("CP", "C", "10u", "polarized capacitor"),
        ("VPULSE", "V", "PULSE(0 5 0 1n 1n 1u 2u)", "pulse voltage source"),
        ("ISIN", "I", "SIN(0 1m 1k)", "sine current source"),
        ("IPULSE", "I", "PULSE(0 1m 0 1n 1n 1u 2u)", "pulse current source"),
        ("D", "D", "1N4148", "diode"),
        ("LED", "D", "LED", "LED"),
        ("ZENER", "D", "5V1", "zener diode"),
        ("SCHOTTKY", "D", "1N5819", "schottky diode"),
        ("FERRITE", "FB", "FB", "ferrite bead"),
        ("FUSE", "F", "Fuse", "fuse"),
        ("PTC", "F", "PTC", "polyfuse"),
        ("MOV", "RV", "MOV", "varistor"),
        ("TVS", "D", "TVS", "TVS diode"),
        ("SW_PUSH", "SW", "SW_Push", "push switch"),
    ):
        specs[kind] = _generic_two_pin(kind, f"Progen:{kind}", prefix, value, desc, vertical=False)
    for kind, prefix, value, desc in (
        ("R_POT", "RV", "10k", "potentiometer"),
        ("NPN", "Q", "2N3904", "NPN transistor"),
        ("PNP", "Q", "2N3906", "PNP transistor"),
        ("2N2222", "Q", "2N2222", "NPN transistor"),
        ("NMOS", "Q", "NMOS", "NMOS transistor"),
        ("PMOS", "Q", "PMOS", "PMOS transistor"),
        ("JFET_N", "J", "J310", "N-JFET"),
        ("JFET_P", "J", "PJFET", "P-JFET"),
        ("L7805", "U", "L7805", "7805 regulator"),
        ("LM317", "U", "LM317", "LM317 regulator"),
    ):
        specs[kind] = _generic_three_pin(kind, prefix, value, desc)
    for kind, prefix, value, count, desc in (
        ("BRIDGE", "BR", "Bridge", 4, "bridge rectifier"),
        ("OPAMP", "U", "OPAMP", 5, "generic op-amp"),
        ("LM741", "U", "LM741", 8, "LM741 op-amp"),
        ("LM358", "U", "LM358", 8, "LM358 op-amp"),
        ("LM393", "U", "LM393", 8, "LM393 comparator"),
        ("NE555", "U", "NE555", 8, "555 timer"),
        ("74HC14", "U", "74HC14", 14, "hex Schmitt inverter"),
        ("74LS14", "U", "74LS14", 14, "hex Schmitt inverter"),
        ("74HC00", "U", "74HC00", 14, "quad NAND"),
        ("74HC02", "U", "74HC02", 14, "quad NOR"),
        ("74HC04", "U", "74HC04", 14, "hex inverter"),
        ("74HC08", "U", "74HC08", 14, "quad AND"),
        ("74HC32", "U", "74HC32", 14, "quad OR"),
        ("74HC86", "U", "74HC86", 14, "quad XOR"),
        ("74HC266", "U", "74HC266", 14, "quad XNOR/open-drain"),
        ("74HC74", "U", "74HC74", 14, "dual D flip-flop"),
        ("74HC76", "U", "74HC76", 16, "dual JK flip-flop"),
        ("74HC90", "U", "74HC90", 14, "decade counter"),
        ("7490", "U", "7490", 14, "decade counter"),
        ("74HC160", "U", "74HC160", 16, "synchronous BCD counter"),
        ("74HC161", "U", "74HC161", 16, "synchronous binary counter"),
        ("74HC163", "U", "74HC163", 16, "synchronous binary counter"),
        ("74HC174", "U", "74HC174", 16, "hex D flip-flop"),
        ("74HC175", "U", "74HC175", 16, "quad D flip-flop"),
        ("74HC192", "U", "74HC192", 16, "up/down BCD counter"),
        ("74HC193", "U", "74HC193", 16, "up/down binary counter"),
        ("74HC273", "U", "74HC273", 20, "octal D flip-flop"),
        ("74HC151", "U", "74HC151", 16, "8-channel mux"),
        ("74HC153", "U", "74HC153", 16, "dual mux"),
        ("74HC157", "U", "74HC157", 16, "quad mux"),
        ("74HC47", "U", "74HC47", 16, "BCD seven-segment driver"),
        ("74HC48", "U", "74HC48", 16, "BCD seven-segment driver"),
        ("7447", "U", "7447", 16, "BCD common-anode seven-segment driver"),
        ("74LS47", "U", "74LS47", 16, "BCD common-anode seven-segment driver"),
        ("74HC85", "U", "74HC85", 16, "magnitude comparator"),
        ("74HC165", "U", "74HC165", 16, "parallel-in serial-out shift register"),
        ("74HC283", "U", "74HC283", 16, "4-bit adder"),
        ("74HC595", "U", "74HC595", 16, "serial-in parallel-out shift register"),
        ("4008", "U", "4008", 16, "CMOS adder"),
        ("4013", "U", "4013", 14, "dual D flip-flop"),
        ("4017", "U", "4017", 16, "decade counter"),
        ("4020", "U", "4020", 16, "binary counter"),
        ("4024", "U", "4024", 14, "binary counter"),
        ("4027", "U", "4027", 16, "dual JK flip-flop"),
        ("4040", "U", "4040", 16, "binary counter"),
        ("4051", "U", "4051", 16, "analog mux"),
        ("4060", "U", "4060", 16, "oscillator/counter"),
        ("4063", "U", "4063", 16, "magnitude comparator"),
        ("4093", "U", "4093", 14, "Schmitt NAND"),
        ("4511", "U", "4511", 16, "BCD seven-segment latch/driver"),
        ("4518", "U", "4518", 16, "dual BCD counter"),
        ("4520", "U", "4520", 16, "dual binary counter"),
        ("CONN_2", "J", "Conn_01x02", 2, "2-pin connector"),
        ("CONN_3", "J", "Conn_01x03", 3, "3-pin connector"),
        ("CONN_4", "J", "Conn_01x04", 4, "4-pin connector"),
        ("7SEG_CA", "DS", "7SEG_CA", 10, "common-anode seven-segment display"),
        ("SW_DIP", "SW", "SW_DIP", 8, "DIP switch"),
        ("TESTPOINT", "TP", "TP", 1, "testpoint"),
    ):
        specs[kind] = _generic_multi_pin(kind, prefix, value, count, desc)
    specs["TESTPOINT"] = KindSpec(
        "TESTPOINT",
        "Progen:TESTPOINT",
        "TP",
        "TP",
        (PinDef("1", 0, 0, "bottom"),),
        0,
        "testpoint",
    )
    symbol_sources = {kind: "project_local" for kind in specs}
    for kind, lib_id in V1_KIND_LIB_IDS.items():
        if lib_id in source_symbols:
            symbol_sources[kind] = f"mined_exact:{source_symbols[lib_id].source}"
    return specs, symbol_sources


KIND_SPECS, SYMBOL_SOURCES = build_kind_specs()
SUPPORTED_KINDS = set(KIND_SPECS)


def pin_orientation(side: str) -> int:
    return {"left": 0, "right": 180, "top": 270, "bottom": 90, "center": 0}.get(side, 0)


def generic_symbol_block(spec: KindSpec) -> str:
    h = max(10.16, max((abs(p.y) for p in spec.pins), default=0) * 2 + 5.08)
    w = max(12.7, max((abs(p.x) for p in spec.pins), default=0) * 2 + 5.08)
    safe = spec.kind.replace("+", "P").replace("-", "M").replace("/", "_")
    lines = [f"    (symbol {q(spec.lib_id)} (pin_names (offset 1.016)) (in_bom yes) (on_board yes)\n"]
    properties = [
        ("Reference", spec.ref_prefix, -h / 2 - 2.54, False),
        ("Value", spec.default_value, h / 2 + 2.54, False),
        ("Footprint", "", 0, True),
        ("Datasheet", "~", 0, True),
    ]
    for key, value, dy, hidden in properties:
        hide = " hide" if hidden else ""
        lines.append(
            f"      (property {q(key)} {q(value)} (at 0 {num(dy)} 0)\n"
            f"        (effects (font (size 1.27 1.27)){hide})\n"
            "      )\n"
        )
    lines.append(
        f"      (property {q('ki_description')} {q('Progen generated symbol: ' + spec.description)} (at 0 0 0)\n"
        "        (effects (font (size 1.27 1.27)) hide)\n"
        "      )\n"
    )
    lines.append(f"      (symbol {q(safe + '_0_1')}\n")
    if spec.kind == "TESTPOINT":
        lines.append("        (circle (center 0 3.302) (radius 0.762) (stroke (width 0.254) (type default)) (fill (type none)))\n")
    elif spec.kind == "C":
        lines.append("        (polyline (pts (xy -2.032 0.762) (xy 2.032 0.762)) (stroke (width 0.508) (type default)) (fill (type none)))\n")
        lines.append("        (polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762)) (stroke (width 0.508) (type default)) (fill (type none)))\n")
    elif spec.kind == "CP":
        lines.append("        (polyline (pts (xy -1.27 -3.81) (xy -1.27 3.81)) (stroke (width 0.254) (type default)) (fill (type none)))\n")
        lines.append("        (polyline (pts (xy 1.27 -3.81) (xy 1.27 3.81)) (stroke (width 0.254) (type default)) (fill (type none)))\n")
    elif spec.kind in SOURCE_KINDS:
        lines.append("        (circle (center 0 0) (radius 2.54) (stroke (width 0.254) (type default)) (fill (type background)))\n")
        label = "I" if spec.kind in {"IDC", "ISIN", "IPULSE"} else "~"
        lines.append(f"        (text {q(label)} (at 0 0 0) (effects (font (size 1.27 1.27))))\n")
    else:
        lines.append(
            f"        (rectangle (start {num(-w / 2)} {num(-h / 2)}) (end {num(w / 2)} {num(h / 2)}) "
            "(stroke (width 0.254) (type default)) (fill (type none)))\n"
        )
        lines.append(f"        (text {q(spec.kind)} (at 0 0 0) (effects (font (size 1.27 1.27))))\n")
    lines.append("      )\n")
    lines.append(f"      (symbol {q(safe + '_1_1')}\n")
    for pin in spec.pins:
        lines.append(
            f"        (pin passive line (at {num(pin.x)} {num(pin.y)} {pin_orientation(pin.side)}) (length 2.54)\n"
            f"          (name {q(pin.number)} (effects (font (size 1.27 1.27))))\n"
            f"          (number {q(pin.number)} (effects (font (size 1.27 1.27))))\n"
            "        )\n"
        )
    lines.append("      )\n    )\n")
    return "".join(lines)


def _library_symbol_name(lib_id: str) -> str:
    return lib_id.split(":", 1)[1] if ":" in lib_id else lib_id


def generic_project_library_symbol_block(spec: KindSpec) -> str:
    block = generic_symbol_block(spec)
    symbol_name = _library_symbol_name(spec.lib_id)
    block = re.sub(r'\(symbol\s+"[^"]+"', f"(symbol {q(symbol_name)}", block, count=1)
    return "\n".join(line[4:] if line.startswith("    ") else line for line in block.splitlines()) + "\n"


def project_local_symbol_library(kinds: set[str]) -> str:
    local_kinds = [kind for kind in sorted(kinds) if SYMBOL_SOURCES.get(kind) == "project_local"]
    if not local_kinds:
        return ""
    out = [
        f"(kicad_symbol_lib (version {SCH_VERSION}) (generator {q(GENERATOR)}) (generator_version {q('v1')})\n"
    ]
    for kind in local_kinds:
        out.append(generic_project_library_symbol_block(KIND_SPECS[kind]))
    out.append(")\n")
    return "".join(out)


def sym_lib_table_text() -> str:
    return (
        "(sym_lib_table\n"
        "  (version 7)\n"
        "  (lib (name \"Progen\") (type \"KiCad\") (uri \"${KIPRJMOD}/progen_generated.kicad_sym\") "
        "(options \"\") (descr \"Progen project-local generated symbols\"))\n"
        ")\n"
    )


def symbol_blocks_for(kinds: set[str]) -> list[str]:
    source_symbols = load_source_symbols()
    blocks: list[str] = []
    for kind in sorted(kinds):
        spec = KIND_SPECS[kind]
        exact = source_symbols.get(spec.lib_id)
        blocks.append(exact.text if exact else generic_symbol_block(spec))
    return blocks


def pin_world(comp: Component, pin_no: str) -> Point:
    spec = KIND_SPECS[comp.kind]
    pin = next((item for item in spec.pins if item.number == pin_no), None)
    if pin is None:
        raise ValueError(f"{comp.ref}/{comp.kind} has no pin {pin_no}")
    angle = math.radians(comp.rotation % 360)
    local_y = -pin.y
    x = pin.x * math.cos(angle) - local_y * math.sin(angle)
    y = pin.x * math.sin(angle) + local_y * math.cos(angle)
    return (round(comp.at[0] + x, 3), round(comp.at[1] + y, 3))


def _pin_vector_from_component(comp: Component, pin_no: str) -> Point:
    point = pin_world(comp, pin_no)
    dx = round(point[0] - comp.at[0], 3)
    dy = round(point[1] - comp.at[1], 3)
    if abs(dx) >= abs(dy) and abs(dx) > 1e-6:
        return (1.0 if dx > 0 else -1.0, 0.0)
    if abs(dy) > 1e-6:
        return (0.0, 1.0 if dy > 0 else -1.0)
    return (0.0, 1.0)


def _stub_end(comp: Component, pin_no: str, *, length: float = 10.16) -> Point:
    start = pin_world(comp, pin_no)
    vx, vy = _pin_vector_from_component(comp, pin_no)
    return (round(start[0] + vx * length, 3), round(start[1] + vy * length, 3))


def _stub_length(pin_no: str) -> float:
    digits = re.sub(r"\D+", "", str(pin_no))
    if not digits:
        return 12.7
    return 10.16 + (int(digits) % 4) * 2.54


def _segment_vector(start: Point, end: Point) -> Point:
    dx = round(end[0] - start[0], 3)
    dy = round(end[1] - start[1], 3)
    if abs(dx) >= abs(dy) and abs(dx) > 1e-6:
        return (1.0 if dx > 0 else -1.0, 0.0)
    if abs(dy) > 1e-6:
        return (0.0, 1.0 if dy > 0 else -1.0)
    return (1.0, 0.0)


def _stub_route(comp: Component, pin_no: str, net: str) -> tuple[Point, Point, tuple[tuple[Point, Point], ...]]:
    start = pin_world(comp, pin_no)
    net_name = net.upper()
    if comp.kind == "C" and net_name in RAIL_NETS:
        length = _stub_length(pin_no)
        direction = -1.0 if net_name in {"GND", "0", "VSS"} else 1.0
        end = (round(start[0] + direction * length, 3), start[1])
        return start, end, ((start, end),)
    if len(KIND_SPECS[comp.kind].pins) <= 3 and net_name not in RAIL_NETS:
        length = 5.08
    else:
        length = _stub_length(pin_no)
    end = _stub_end(comp, pin_no, length=length)
    return start, end, ((start, end),)


def local_label_stubs(plan: LayoutPlan) -> list[dict[str, Any]]:
    cache_key = id(plan)
    if cache_key in _LOCAL_LABEL_STUB_CACHE:
        return _LOCAL_LABEL_STUB_CACHE[cache_key]
    label_endpoint_clearance = 2 * GRID
    local_label_nets = {net for net, _ in plan.routing.local_label_points}
    candidates: list[dict[str, Any]] = []
    index = 0
    for comp in plan.components:
        for pin_no, net in sorted(comp.pins.items(), key=lambda item: (len(item[0]), item[0])):
            if net not in local_label_nets:
                continue
            start, end, segments = _stub_route(comp, pin_no, net)
            vx, vy = _segment_vector(start, end)
            candidate = {
                "index": index,
                "net": net,
                "component": comp.ref,
                "pin": pin_no,
                "from": start,
                "to": end,
                "segments": segments,
                "vector": (vx, vy),
            }
            candidates.append(candidate)
            index += 1

    stubs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, Point, Point]] = set()
    occupied: dict[Point, str] = {}
    pin_points: list[tuple[str, Point]] = []
    for comp in plan.components:
        for pin_no, net in comp.pins.items():
            point = pin_world(comp, pin_no)
            occupied.setdefault(point, net)
            pin_points.append((net, point))
    placed_segments: list[tuple[str, Point, Point]] = []
    route_segments: list[tuple[str, Point, Point]] = [(seg.net, seg.a, seg.b) for seg in plan.routing.segments]

    def vectors_for(vx: float, vy: float) -> list[Point]:
        if abs(vx) >= abs(vy) and abs(vx) > 1e-6:
            return [(vx, 0.0), (0.0, -1.0), (0.0, 1.0), (-vx, 0.0)]
        direction = 1.0 if vy >= 0 else -1.0
        return [(0.0, direction), (-1.0, 0.0), (1.0, 0.0), (0.0, -direction)]

    def blocked(
        *,
        net: str,
        own_index: int,
        end: Point,
        segments: tuple[tuple[Point, Point], ...],
    ) -> bool:
        if end in occupied and occupied[end] != net:
            return True
        for point, other_net in occupied.items():
            if other_net == net:
                continue
            text_clearance = max(label_endpoint_clearance, min(50.8, 2.54 * max(len(net), len(other_net))))
            if abs(end[0] - point[0]) <= text_clearance and abs(end[1] - point[1]) <= label_endpoint_clearance:
                return True
        if any(_point_on_segment(end, a, b) for _other_net, a, b in route_segments + placed_segments):
            return True
        for seg_start, seg_end in segments:
            if any(
                other_net != net and _segments_intersect(seg_start, seg_end, a, b)
                for other_net, a, b in route_segments + placed_segments
            ):
                return True
        for other_net, point in pin_points:
            if other_net == net:
                continue
            if any(_point_on_segment(point, a, b) for a, b in segments):
                return True
        return False

    for candidate in candidates:
        net = str(candidate["net"])
        comp_ref = str(candidate["component"])
        pin_no = str(candidate["pin"])
        start = candidate["from"]
        end = candidate["to"]
        segments = candidate["segments"]
        vx, vy = candidate["vector"]
        own_index = int(candidate["index"])
        base_length = max(abs(end[0] - start[0]), abs(end[1] - start[1]), GRID)
        if blocked(net=net, own_index=own_index, end=end, segments=segments):
            chosen: tuple[Point, tuple[tuple[Point, Point], ...]] | None = None
            for avx, avy in vectors_for(vx, vy):
                for step in range(0, 101):
                    length = base_length + step * GRID
                    trial_end = (round(start[0] + avx * length, 3), round(start[1] + avy * length, 3))
                    trial_segments = ((start, trial_end),)
                    if not blocked(net=net, own_index=own_index, end=trial_end, segments=trial_segments):
                        chosen = (trial_end, trial_segments)
                        break
                if chosen is not None:
                    break
            if chosen is not None:
                end, segments = chosen
            else:
                segments = ()
        key = (net, comp_ref, pin_no, start, end)
        if key in seen or not segments:
            continue
        seen.add(key)
        occupied.setdefault(end, net)
        placed_segments.extend((net, a, b) for a, b in segments)
        stubs.append({"net": net, "component": comp_ref, "pin": pin_no, "from": start, "to": end, "segments": segments})
    _LOCAL_LABEL_STUB_CACHE[cache_key] = stubs
    return stubs


def _point_on_segment(point: Point, a: Point, b: Point, *, eps: float = 1e-6) -> bool:
    px, py = point
    ax, ay = a
    bx, by = b
    if ax == bx:
        return abs(px - ax) <= eps and min(ay, by) - eps <= py <= max(ay, by) + eps
    if ay == by:
        return abs(py - ay) <= eps and min(ax, bx) - eps <= px <= max(ax, bx) + eps
    return False


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point, *, eps: float = 1e-6) -> bool:
    if a1 == a2 or b1 == b2:
        return False
    a_horizontal = abs(a1[1] - a2[1]) <= eps
    b_horizontal = abs(b1[1] - b2[1]) <= eps
    if a_horizontal and b_horizontal:
        if abs(a1[1] - b1[1]) > eps:
            return False
        return max(min(a1[0], a2[0]), min(b1[0], b2[0])) <= min(max(a1[0], a2[0]), max(b1[0], b2[0])) + eps
    if not a_horizontal and not b_horizontal:
        if abs(a1[0] - b1[0]) > eps:
            return False
        return max(min(a1[1], a2[1]), min(b1[1], b2[1])) <= min(max(a1[1], a2[1]), max(b1[1], b2[1])) + eps

    horizontal = (a1, a2) if a_horizontal else (b1, b2)
    vertical = (b1, b2) if a_horizontal else (a1, a2)
    h1, h2 = horizontal
    v1, v2 = vertical
    return (
        min(h1[0], h2[0]) - eps <= v1[0] <= max(h1[0], h2[0]) + eps
        and min(v1[1], v2[1]) - eps <= h1[1] <= max(v1[1], v2[1]) + eps
    )


def no_connect_points(plan: LayoutPlan) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    seen: set[tuple[str, str, Point]] = set()
    generated_segments: list[tuple[Point, Point]] = [(seg.a, seg.b) for seg in plan.routing.segments]
    for stub in local_label_stubs(plan):
        generated_segments.extend(stub["segments"])
    for comp in plan.components:
        assigned = set(comp.pins)
        for pin in KIND_SPECS[comp.kind].pins:
            if pin.number in assigned:
                continue
            point = pin_world(comp, pin.number)
            if any(_point_on_segment(point, a, b) for a, b in generated_segments):
                continue
            key = (comp.ref, pin.number, point)
            if key in seen:
                continue
            seen.add(key)
            points.append({"component": comp.ref, "pin": pin.number, "at": point})
    return points


def _component_size(comp: Component) -> tuple[float, float]:
    if comp.kind in {"R", "C", "L"}:
        width, height = 5.08, 7.62
    elif comp.kind in SOURCE_KINDS:
        width, height = 7.62, 7.62
    elif comp.kind == "GND":
        width, height = 7.62, 5.08
    else:
        spec = KIND_SPECS[comp.kind]
        xs = [pin.x for pin in spec.pins] + [-7.62, 7.62]
        ys = [pin.y for pin in spec.pins] + [-7.62, 7.62]
        width = max(xs) - min(xs) + 5.08
        height = max(ys) - min(ys) + 5.08
    if int(comp.rotation) % 180:
        return height, width
    return width, height


def _pin_grid_offset(kind: str, rotation: float) -> Point:
    spec = KIND_SPECS[kind]
    angle = math.radians(rotation % 360)
    xs: list[float] = []
    ys: list[float] = []
    for pin in spec.pins:
        local_y = -pin.y
        xs.append(pin.x * math.cos(angle) - local_y * math.sin(angle))
        ys.append(pin.x * math.sin(angle) + local_y * math.cos(angle))
    return (shared_axis_offset(xs), shared_axis_offset(ys))


def _obstacles(comps: tuple[Component, ...]) -> tuple[Obstacle, ...]:
    out: list[Obstacle] = []
    for comp in comps:
        width, height = _component_size(comp)
        out.append(
            Obstacle(
                comp.ref,
                round(comp.at[0] - width / 2, 3),
                round(comp.at[1] - height / 2, 3),
                round(comp.at[0] + width / 2, 3),
                round(comp.at[1] + height / 2, 3),
            )
        )
    return tuple(out)


def _all_net_names(raw_components: list[dict[str, Any]]) -> set[str]:
    nets: set[str] = set()
    for item in raw_components:
        pins = item.get("pins") or {}
        if isinstance(pins, dict):
            nets.update(str(value) for value in pins.values())
    return nets


def _root_nets(raw_components: list[dict[str, Any]]) -> set[str]:
    roots: set[str] = set()
    for item in raw_components:
        kind = str(item.get("kind", "")).upper()
        pins = item.get("pins") or {}
        if kind in SOURCE_KINDS and isinstance(pins, dict) and "1" in pins:
            roots.add(str(pins["1"]))
    if roots:
        return roots
    nets = sorted(net for net in _all_net_names(raw_components) if net.upper() not in {"GND", "0", "VSS"})
    return {nets[0]} if nets else set()


def _net_levels(raw_components: list[dict[str, Any]]) -> dict[str, int]:
    levels = {net: 0 for net in _root_nets(raw_components)}
    if not levels:
        levels["N1"] = 0
    changed = True
    while changed:
        changed = False
        for item in raw_components:
            pins_raw = item.get("pins") or {}
            if not isinstance(pins_raw, dict) or len(pins_raw) < 2:
                continue
            nets = [str(value) for _, value in sorted(pins_raw.items())]
            known = [levels[net] for net in nets if net in levels]
            if not known:
                continue
            next_level = min(known) + 1
            for net in nets:
                if net not in levels or levels[net] > next_level:
                    levels[net] = next_level
                    changed = True
    for net in _all_net_names(raw_components):
        levels.setdefault(net, max(levels.values(), default=0) + 1)
    for ground in ("GND", "0", "VSS"):
        if ground in levels:
            levels[ground] = max(levels.values(), default=0) + 1
    return levels


def _normalize_raw_components(circuit: dict[str, Any]) -> list[dict[str, Any]]:
    raw_components = circuit.get("components")
    if not isinstance(raw_components, list):
        raise ValueError("CircuitIR requires components as an array.")
    return [dict(item) for item in raw_components]


def _ref_for(item: dict[str, Any], counts: dict[str, int], kind: str) -> str:
    if item.get("id"):
        return str(item["id"])
    spec = KIND_SPECS[kind]
    counts[kind] = counts.get(kind, 0) + 1
    return f"{spec.ref_prefix}{counts[kind]}"


def autoplace(circuit: dict[str, Any]) -> tuple[Component, ...]:
    raw_components = _normalize_raw_components(circuit)
    levels = _net_levels(raw_components)
    counts: dict[str, int] = {}
    provisional: list[dict[str, Any]] = []
    for index, item in enumerate(raw_components):
        kind = str(item.get("kind", "")).upper()
        if kind not in SUPPORTED_KINDS:
            raise ValueError(f"Unsupported KiCad V1 component kind: {kind}")
        pins = {str(key): str(value) for key, value in dict(item.get("pins") or {}).items()}
        if not pins:
            raise ValueError(f"{item.get('id', kind)} requires a pins map.")
        ref = _ref_for(item, counts, kind)
        spec = KIND_SPECS[kind]
        manual = isinstance(item.get("at"), list) and len(item["at"]) == 2
        value = str(item.get("value") or spec.default_value)
        rotation = float(item.get("rotation", spec.default_rotation))
        connected_levels = [levels.get(net, 0) for net in pins.values()]
        if kind in SOURCE_KINDS:
            level = min(connected_levels, default=0)
        elif kind == "GND":
            level = max(connected_levels, default=0)
        else:
            level = max(0, min(connected_levels, default=0) + 1)
        provisional.append(
            {
                "index": index,
                "item": item,
                "kind": kind,
                "ref": ref,
                "value": value,
                "rotation": rotation,
                "pins": pins,
                "manual": manual,
                "level": level,
            }
        )

    lane_by_net: dict[str, int] = {}
    next_lane = 0
    components: list[Component] = []
    by_level: dict[int, int] = {}
    placed_non_ground: list[Component] = []

    for row in sorted(provisional, key=lambda r: (r["kind"] == "GND", r["level"], r["index"])):
        item = row["item"]
        kind = row["kind"]
        pins = row["pins"]
        if row["manual"]:
            at = (float(item["at"][0]), float(item["at"][1]))
        elif kind == "GND":
            gnd_net = next(iter(pins.values()))
            points = [pin_world(comp, pin_no) for comp in placed_non_ground for pin_no, net in comp.pins.items() if net == gnd_net]
            if points:
                at = snap_point((sum(p[0] for p in points) / len(points), max(p[1] for p in points) + 20.32))
            else:
                at = snap_point((50.8, 121.92 + 20.32 * len(components)))
        else:
            primary_net = pins.get("1") or next(iter(pins.values()))
            for connected_net in pins.values():
                if connected_net in lane_by_net:
                    primary_net = connected_net
                    break
            if primary_net not in lane_by_net:
                lane_by_net[primary_net] = next_lane
                next_lane += 1
            lane = lane_by_net[primary_net]
            by_level[row["level"]] = by_level.get(row["level"], 0) + 1
            extra = by_level[row["level"]] - 1
            x = 35.56 + row["level"] * 35.56
            if kind in SOURCE_KINDS:
                x = max(20.32, x - 25.4)
            y = 45.72 + (lane + extra) * 25.4
            at = snap_point((x, y))
            for connected_net in pins.values():
                lane_by_net.setdefault(connected_net, lane)
        if not row["manual"]:
            ox, oy = _pin_grid_offset(kind, row["rotation"])
            at = (round(at[0] + ox, 3), round(at[1] + oy, 3))
        comp = Component(row["ref"], kind, row["value"], at, row["rotation"], pins, row["manual"])
        components.append(comp)
        if kind != "GND":
            placed_non_ground.append(comp)
    return tuple(sorted(components, key=lambda c: c.ref.replace("#", "~")))


def points_by_net(comps: tuple[Component, ...]) -> dict[str, list[Point]]:
    out: dict[str, list[Point]] = {}
    for comp in comps:
        for pin_no, net in comp.pins.items():
            out.setdefault(net, []).append(pin_world(comp, pin_no))
    return out


def plan_layout(circuit: dict[str, Any]) -> LayoutPlan:
    comps = autoplace(circuit)
    obstacles = _obstacles(comps)
    routing = route_nets(points_by_net(comps), obstacles, grid=GRID, clearance=0.8)
    return LayoutPlan(comps, routing, obstacles)


def project_json(project_name: str) -> str:
    return json.dumps(
        {
            "meta": {"filename": f"{project_name}.kicad_pro", "version": 1},
            "sheets": [[ROOT_UUID, ""]],
            "libraries": {"pinned_symbol_libs": [], "pinned_footprint_libs": []},
            "text_variables": {},
            "boards": [],
            "board": {"design_settings": {"defaults": {}, "rules": {}}},
            "schematic": {
                "drawing": {"default_line_thickness": 6, "default_text_size": 50},
                "meta": {"version": 1},
                "plot_directory": "",
            },
            "erc": {"erc_exclusions": [], "meta": {"version": 0}},
            "net_settings": {
                "classes": [
                    {
                        "name": "Default",
                        "clearance": 0.2,
                        "track_width": 0.25,
                        "via_diameter": 0.8,
                        "via_drill": 0.4,
                        "wire_width": 6,
                    }
                ],
                "meta": {"version": 3},
            },
        },
        indent=2,
    ) + "\n"


def wire_obj(a: Point, b: Point, project_name: str, index: int) -> str:
    return (
        f"  (wire (pts (xy {num(a[0])} {num(a[1])}) (xy {num(b[0])} {num(b[1])}))\n"
        "    (stroke (width 0) (type default))\n"
        f"    (uuid {uid(project_name + ':wire:' + str(index) + str(a) + str(b))})\n"
        "  )\n"
    )


def junction_obj(point: Point, project_name: str, index: int) -> str:
    return (
        f"  (junction (at {num(point[0])} {num(point[1])}) (diameter 0) (color 0 0 0 0)\n"
        f"    (uuid {uid(project_name + ':junction:' + str(index) + str(point))})\n"
        "  )\n"
    )


def no_connect_obj(point: Point, project_name: str, index: int) -> str:
    return (
        f"  (no_connect (at {num(point[0])} {num(point[1])})\n"
        f"    (uuid {uid(project_name + ':no_connect:' + str(index) + str(point))})\n"
        "  )\n"
    )


def text_obj(
    text: str,
    at: Point,
    project_name: str,
    index: int,
    kind: str = "text",
    justify: str = "left bottom",
) -> str:
    token = "label" if kind == "label" else "text"
    extra = " (exclude_from_sim no)" if token == "text" else ""
    return (
        f"  ({token} {q(text)}{extra} (at {num(at[0])} {num(at[1])} 0) (fields_autoplaced)\n"
        f"    (effects (font (size 1.27 1.27)) (justify {justify}))\n"
        f"    (uuid {uid(project_name + ':' + token + ':' + str(index) + text + str(at))})\n"
        "  )\n"
    )


def label_justify_for_stub(stub: dict[str, Any]) -> str:
    dx = round(float(stub["to"][0]) - float(stub["from"][0]), 3)
    dy = round(float(stub["to"][1]) - float(stub["from"][1]), 3)
    if abs(dx) >= abs(dy) and dx < 0:
        return "right bottom"
    if abs(dx) >= abs(dy):
        return "left bottom"
    return "left bottom"


def symbol_instance(comp: Component, project_name: str) -> str:
    spec = KIND_SPECS[comp.kind]
    x, y = comp.at
    su = uid(f"{project_name}:{comp.ref}:{comp.kind}:{x}:{y}:{comp.rotation}")
    lines = [
        f"  (symbol (lib_id {q(spec.lib_id)}) (at {num(x)} {num(y)} {num(comp.rotation)}) (unit 1)\n",
        "    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)\n",
        f"    (uuid {su})\n",
        f"    (property {q('Reference')} {q(comp.ref)} (at {num(x + 4)} {num(y - 5)} 0) (effects (font (size 1.27 1.27)) (justify left)))\n",
        f"    (property {q('Value')} {q(comp.value)} (at {num(x + 4)} {num(y + 5)} 0) (effects (font (size 1.27 1.27)) (justify left)))\n",
        f"    (property {q('Footprint')} {q('')} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
        f"    (property {q('Datasheet')} {q('~')} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
        f"    (property {q('Progen.Kind')} {q(comp.kind)} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
    ]
    if comp.kind in SOURCE_KINDS:
        lines.append(
            f"    (property {q('Spice_Model')} {q(comp.value)} (at {num(x + 4)} {num(y + 8)} 0) "
            "(effects (font (size 1.27 1.27)) (justify left)))\n"
        )
    for pin in spec.pins:
        lines.append(f"    (pin {q(pin.number)} (uuid {uid(su + ':pin:' + pin.number)}))\n")
    lines.append("    (instances\n")
    lines.append(
        f"      (project {q(project_name)}\n"
        f"        (path {q('/' + ROOT_UUID)}\n"
        f"          (reference {q(comp.ref)}) (unit 1) (value {q(comp.value)}) (footprint {q('')})\n"
        "        )\n"
        "      )\n"
        "    )\n"
        "  )\n"
    )
    return "".join(lines)


def schematic_text(project_name: str, circuit: dict[str, Any], plan: LayoutPlan) -> str:
    used_kinds = {comp.kind for comp in plan.components}
    out = [
        f"(kicad_sch (version {SCH_VERSION}) (generator {q(GENERATOR)}) (generator_version {q('v1')})\n",
        f"  (uuid {ROOT_UUID})\n",
        "  (paper \"A2\")\n",
        "  (lib_symbols\n",
    ]
    out.extend(symbol_blocks_for(used_kinds))
    out.append("  )\n")
    for index, point in enumerate(plan.routing.junctions, 1):
        out.append(junction_obj(point, project_name, index))
    for index, item in enumerate(no_connect_points(plan), 1):
        out.append(no_connect_obj(item["at"], project_name, index))
    wire_index = 1
    for seg in plan.routing.segments:
        out.append(wire_obj(seg.a, seg.b, project_name, wire_index))
        wire_index += 1
    stubs = local_label_stubs(plan)
    for stub in stubs:
        for a, b in stub["segments"]:
            out.append(wire_obj(a, b, project_name, wire_index))
            wire_index += 1
    label_index = 1
    for stub in sorted(stubs, key=lambda item: (item["net"], item["to"][1], item["to"][0], item["component"], item["pin"])):
        out.append(text_obj(str(stub["net"]), stub["to"], project_name, label_index, "label", label_justify_for_stub(stub)))
        label_index += 1
    for index, line in enumerate(circuit.get("project", {}).get("analysis", []) or [], 1):
        out.append(text_obj(str(line), (20, 170 + index * 5.08), project_name, index))
    for comp in plan.components:
        out.append(symbol_instance(comp, project_name))
    out.append("  (sheet_instances\n    (path \"/\" (page \"1\"))\n  )\n)\n")
    return "".join(out)


def validate_schematic(text: str) -> dict[str, Any]:
    depth = 0
    in_string = False
    escaped = False
    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth < 0:
            return {"ok": False, "error": f"extra right paren at offset {index}"}

    bad_wires = 0
    diagonal_wires = 0
    wire_count = 0
    for match in re.finditer(r"\(wire \(pts(.*?)\)\s*\n\s*\(stroke", text, re.S):
        pts = re.findall(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)", match.group(1))
        wire_count += 1
        if len(pts) != 2:
            bad_wires += 1
            continue
        a = (float(pts[0][0]), float(pts[0][1]))
        b = (float(pts[1][0]), float(pts[1][1]))
        if a[0] != b[0] and a[1] != b[1]:
            diagonal_wires += 1
    ok = depth == 0 and not in_string and bad_wires == 0 and diagonal_wires == 0
    return {
        "ok": ok,
        "depth": depth,
        "in_string": in_string,
        "wire_count": wire_count,
        "label_count": text.count("\n  (label "),
        "no_connect_count": text.count("\n  (no_connect "),
        "bad_wire_objects": bad_wires,
        "diagonal_wire_objects": diagonal_wires,
        "symbol_instances": text.count("\n  (symbol (lib_id"),
    }


def _schema_warnings(circuit: dict[str, Any]) -> list[str]:
    schema = str(circuit.get("schema_version", ""))
    warnings: list[str] = []
    if schema and schema not in {"progen-kicad-circuit-ir/v1", "progen-kicad-circuit-ir/v0.3"}:
        warnings.append(f"Unrecognized schema_version {schema}; attempting V1-compatible generation.")
    return warnings


def write_project_from_json(circuit: dict[str, Any], out_dir: Path, clean: bool = True) -> dict[str, Any]:
    name = slugify(circuit.get("project", {}).get("name", "generated_kicad_project"))
    project_name = f"OPEN_THIS_PROJECT__{name}__PROJECT_FILE"
    if clean and out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    plan = plan_layout(circuit)
    schematic = schematic_text(project_name, circuit, plan)
    checks = validate_schematic(schematic)
    symbol_sources = {kind: SYMBOL_SOURCES.get(kind, "project_local") for kind in sorted({c.kind for c in plan.components})}
    local_library = project_local_symbol_library({c.kind for c in plan.components})
    checks["router_warnings"] = list(plan.routing.warnings)
    checks["schema_warnings"] = _schema_warnings(circuit)

    (out_dir / f"{project_name}.kicad_pro").write_text(project_json(project_name), encoding="utf-8")
    (out_dir / f"{project_name}.kicad_sch").write_text(schematic, encoding="utf-8")
    if local_library:
        (out_dir / "progen_generated.kicad_sym").write_text(local_library, encoding="utf-8")
        (out_dir / "sym-lib-table").write_text(sym_lib_table_text(), encoding="utf-8")
    (out_dir / "input.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
    manifest = {
        "project_name": project_name,
        "open_this": f"{project_name}.kicad_pro",
        "schematic_file": f"{project_name}.kicad_sch",
        "project_local_symbol_library": "progen_generated.kicad_sym" if local_library else None,
        "symbol_library_table": "sym-lib-table" if local_library else None,
        "component_count": len(plan.components),
        "kinds": sorted({comp.kind for comp in plan.components}),
        "symbol_sources": symbol_sources,
        "source_reference": load_reference().as_dict(),
        "layout": plan.as_dict(),
        "static_checks": checks,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a KiCad project from Progen KiCad CircuitIR JSON.")
    parser.add_argument("--json", required=True, help="CircuitIR JSON input")
    parser.add_argument("--out", required=True, help="Output folder")
    args = parser.parse_args()
    circuit = json.loads(Path(args.json).read_text(encoding="utf-8"))
    manifest = write_project_from_json(circuit, Path(args.out))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
