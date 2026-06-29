#!/usr/bin/env python3
"""Generate a true V8 KiCad 50-unique-component visual smoke-test pack.

This is not the final stock-symbol implementation for every component.  It is the
first real all-together coverage project: one schematic contains 50 unique
component kinds, and each component has wires/stubs landing on its declared pin
endpoints.

Design rule:
- verified KiCad stock symbol-cache blocks are used for the already proven set:
  VDC, VSIN, R, L.
- every other component uses a project-local `Progen50:<kind>` symbol.  These
  generic symbols are intentionally embedded in the schematic so the output is
  portable and does not depend on the user's KiCad library table.
- exact KiCad stock art/symbols are promoted only after donor extraction proves
  the correct symbol-cache block and pin endpoint model.
"""

from __future__ import annotations

import json
import math
import shutil
import uuid
import zipfile
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

ROOT_UUID = "00000000-0000-0000-0000-000000000001"
GENERATOR = "progen-kicad-source-driven-v8-50-component-zoo"
SCH_VERSION = 20241201


def q(value: object) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"') + '"'


def num(value: float) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.6f}".rstrip("0").rstrip(".")


def stable_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def write_project_json(project_name: str) -> str:
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


# Import the already verified V5/V6/V7 cache blocks from the backend when run in
# the repo.  The generator fails loudly if this package is missing, because those
# blocks are the proven source-driven foundation.
from kicad_backend.symbol_cache import SYMBOL_CACHE as VERIFIED_CACHE


@dataclass(frozen=True)
class PinDef:
    number: str
    x: float
    y: float
    side: str


@dataclass(frozen=True)
class KindSpec:
    kind: str
    ref_prefix: str
    value: str
    pins: List[PinDef]
    lib_id: str
    verified: bool = False
    description: str = ""


def two_pin(kind: str, ref: str, value: str, desc: str = "") -> KindSpec:
    return KindSpec(kind, ref, value, [PinDef("1", -10.16, 0, "left"), PinDef("2", 10.16, 0, "right")], f"Progen50:{kind}", False, desc)


def three_pin(kind: str, ref: str, value: str, desc: str = "") -> KindSpec:
    return KindSpec(kind, ref, value, [PinDef("1", -10.16, 0, "left"), PinDef("2", 10.16, 2.54, "right"), PinDef("3", 10.16, -2.54, "right")], f"Progen50:{kind}", False, desc)


def multi_pin(kind: str, ref: str, value: str, n: int, desc: str = "") -> KindSpec:
    left = math.ceil(n / 2)
    right = n - left
    spacing = 2.54
    pins: List[PinDef] = []
    for i in range(1, left + 1):
        y = (left + 1) / 2 * spacing - i * spacing
        pins.append(PinDef(str(i), -10.16, y, "left"))
    for j in range(1, right + 1):
        pin_no = left + j
        y = (right + 1) / 2 * spacing - j * spacing
        pins.append(PinDef(str(pin_no), 10.16, y, "right"))
    return KindSpec(kind, ref, value, pins, f"Progen50:{kind}", False, desc)


KIND_SPECS: List[KindSpec] = [
    KindSpec("VDC", "V", "5", [PinDef("1", 0, 5.08, "top"), PinDef("2", 0, -5.08, "bottom")], "Simulation_SPICE:VDC", True, "DC voltage source"),
    KindSpec("VSIN", "V", "VSIN", [PinDef("1", 0, 5.08, "top"), PinDef("2", 0, -5.08, "bottom")], "Simulation_SPICE:VSIN", True, "sine voltage source"),
    KindSpec("R", "R", "1k", [PinDef("1", 0, 3.81, "top"), PinDef("2", 0, -3.81, "bottom")], "Device:R", True, "resistor"),
    KindSpec("L", "L", "10m", [PinDef("1", 0, 3.81, "top"), PinDef("2", 0, -3.81, "bottom")], "Device:L", True, "inductor"),
    two_pin("C", "C", "100n", "capacitor"),
    two_pin("CP", "C", "10u", "polarized capacitor"),
    three_pin("R_POT", "RV", "10k", "potentiometer"),
    two_pin("FERRITE", "FB", "FB", "ferrite bead"),
    two_pin("FUSE", "F", "Fuse", "fuse"),
    two_pin("PTC", "F", "PTC", "polyfuse/PTC"),
    two_pin("MOV", "RV", "MOV", "varistor/MOV"),
    two_pin("TVS", "D", "TVS", "TVS diode"),
    two_pin("D", "D", "1N4148", "diode"),
    two_pin("LED", "D", "LED", "LED"),
    two_pin("ZENER", "D", "5V1", "zener diode"),
    two_pin("SCHOTTKY", "D", "1N5819", "schottky diode"),
    multi_pin("BRIDGE", "BR", "Bridge", 4, "diode bridge"),
    two_pin("VPULSE", "V", "VPULSE", "pulse voltage source"),
    two_pin("VAC", "V", "VAC", "AC voltage source"),
    two_pin("IDC", "I", "1m", "DC current source"),
    two_pin("ISIN", "I", "ISIN", "sine current source"),
    two_pin("IPULSE", "I", "IPULSE", "pulse current source"),
    three_pin("NPN", "Q", "2N3904", "NPN transistor"),
    three_pin("PNP", "Q", "2N3906", "PNP transistor"),
    three_pin("NMOS", "Q", "NMOS", "N-channel MOSFET"),
    three_pin("PMOS", "Q", "PMOS", "P-channel MOSFET"),
    three_pin("JFET_N", "J", "J310", "N-JFET"),
    three_pin("JFET_P", "J", "PJFET", "P-JFET"),
    multi_pin("OPAMP", "U", "OPAMP", 5, "generic op-amp"),
    multi_pin("LM741", "U", "LM741", 8, "LM741 op-amp"),
    multi_pin("LM358", "U", "LM358", 8, "LM358 dual op-amp"),
    multi_pin("LM393", "U", "LM393", 8, "LM393 comparator"),
    multi_pin("NE555", "U", "NE555", 8, "555 timer"),
    multi_pin("L7805", "U", "L7805", 3, "7805 regulator"),
    multi_pin("LM317", "U", "LM317", 3, "LM317 regulator"),
    multi_pin("74HC00", "U", "74HC00", 14, "quad NAND"),
    multi_pin("74HC04", "U", "74HC04", 14, "hex inverter"),
    multi_pin("74HC08", "U", "74HC08", 14, "quad AND"),
    multi_pin("74HC32", "U", "74HC32", 14, "quad OR"),
    multi_pin("74HC86", "U", "74HC86", 14, "quad XOR"),
    multi_pin("74HC74", "U", "74HC74", 14, "dual D flip-flop"),
    multi_pin("74HC76", "U", "74HC76", 16, "dual JK flip-flop"),
    multi_pin("74HC90", "U", "74HC90", 14, "decade counter"),
    multi_pin("74HC157", "U", "74HC157", 16, "quad 2-to-1 mux"),
    multi_pin("74HC192", "U", "74HC192", 16, "up/down counter"),
    multi_pin("4511", "U", "4511", 16, "BCD to seven-segment driver"),
    multi_pin("4017", "U", "4017", 16, "decade counter/divider"),
    multi_pin("CONN_2", "J", "Conn_01x02", 2, "2-pin connector"),
    multi_pin("CONN_3", "J", "Conn_01x03", 3, "3-pin connector"),
    multi_pin("CONN_4", "J", "Conn_01x04", 4, "4-pin connector"),
]

assert len(KIND_SPECS) == 50


def pin_orientation(side: str) -> int:
    return {"left": 0, "right": 180, "top": 270, "bottom": 90, "center": 0}.get(side, 0)


def custom_symbol_block(spec: KindSpec) -> str:
    ys = [p.y for p in spec.pins] or [0]
    h = max(7.62, max(abs(y) for y in ys) * 2 + 5.08)
    w = 15.24
    base = spec.kind.replace("+", "P").replace("-", "M")
    out: List[str] = []
    out.append(f"    (symbol {q(spec.lib_id)} (pin_names (offset 1.016)) (in_bom yes) (on_board yes)\n")
    out.append(f"      (property {q('Reference')} {q(spec.ref_prefix)} (at 0 {num(-h/2-2.54)} 0)\n        (effects (font (size 1.27 1.27)))\n      )\n")
    out.append(f"      (property {q('Value')} {q(spec.value)} (at 0 {num(h/2+2.54)} 0)\n        (effects (font (size 1.27 1.27)))\n      )\n")
    out.append(f"      (property {q('Footprint')} {q('')} (at 0 0 0)\n        (effects (font (size 1.27 1.27)) hide)\n      )\n")
    out.append(f"      (property {q('Datasheet')} {q('~')} (at 0 0 0)\n        (effects (font (size 1.27 1.27)) hide)\n      )\n")
    out.append(f"      (property {q('ki_description')} {q('Progen V8 generic smoke-test symbol: ' + spec.description)} (at 0 0 0)\n        (effects (font (size 1.27 1.27)) hide)\n      )\n")
    out.append(f"      (symbol {q(base + '_0_1')}\n")
    if spec.kind in {"C", "CP"}:
        out.append("        (polyline (pts (xy -1.27 -3.81) (xy -1.27 3.81)) (stroke (width 0.254) (type default)) (fill (type none)))\n")
        out.append("        (polyline (pts (xy 1.27 -3.81) (xy 1.27 3.81)) (stroke (width 0.254) (type default)) (fill (type none)))\n")
        if spec.kind == "CP":
            out.append("        (text \"+\" (at -3.81 2.54 0) (effects (font (size 1.27 1.27))))\n")
    elif spec.kind in {"D", "LED", "ZENER", "SCHOTTKY", "TVS"}:
        out.append("        (polyline (pts (xy -3.81 -3.81) (xy -3.81 3.81) (xy 2.54 0) (xy -3.81 -3.81)) (stroke (width 0.254) (type default)) (fill (type none)))\n")
        out.append("        (polyline (pts (xy 3.81 -3.81) (xy 3.81 3.81)) (stroke (width 0.254) (type default)) (fill (type none)))\n")
    elif spec.kind in {"FUSE", "PTC"}:
        out.append("        (rectangle (start -5.08 -1.27) (end 5.08 1.27) (stroke (width 0.254) (type default)) (fill (type none)))\n")
    else:
        out.append(f"        (rectangle (start {num(-w/2)} {num(-h/2)}) (end {num(w/2)} {num(h/2)})\n          (stroke (width 0.254) (type default))\n          (fill (type none))\n        )\n")
        out.append(f"        (text {q(spec.kind)} (at 0 0 0)\n          (effects (font (size 1.27 1.27)))\n        )\n")
    out.append("      )\n")
    out.append(f"      (symbol {q(base + '_1_1')}\n")
    for pin in spec.pins:
        out.append(f"        (pin passive line (at {num(pin.x)} {num(pin.y)} {pin_orientation(pin.side)}) (length 2.54)\n")
        out.append(f"          (name {q(pin.number)} (effects (font (size 1.27 1.27))))\n")
        out.append(f"          (number {q(pin.number)} (effects (font (size 1.27 1.27))))\n")
        out.append("        )\n")
    out.append("      )\n")
    out.append("    )\n")
    return "".join(out)


def lib_symbols_block(used_specs: List[KindSpec]) -> str:
    out = ["  (lib_symbols\n"]
    for spec in used_specs:
        if spec.verified:
            out.append("    " + VERIFIED_CACHE[spec.lib_id].replace("\n", "\n    ").rstrip() + "\n")
        else:
            out.append(custom_symbol_block(spec))
    out.append("  )\n")
    return "".join(out)


@dataclass
class Component:
    ref: str
    spec: KindSpec
    at: Tuple[float, float]
    pins: Dict[str, str]
    value: str
    rotation: float = 0.0


def pin_world(comp: Component, pin_no: str) -> Tuple[float, float]:
    pin = next(p for p in comp.spec.pins if p.number == pin_no)
    r = math.radians(comp.rotation % 360)
    x = pin.x * math.cos(r) - pin.y * math.sin(r)
    y = pin.x * math.sin(r) + pin.y * math.cos(r)
    return (round(comp.at[0] + x, 3), round(comp.at[1] + y, 3))


def symbol_instance(comp: Component, project_name: str) -> str:
    x, y = comp.at
    su = stable_uuid(f"{project_name}:{comp.ref}:{comp.spec.kind}:{x}:{y}")
    out = [
        f"  (symbol (lib_id {q(comp.spec.lib_id)}) (at {num(x)} {num(y)} {num(comp.rotation)}) (unit 1)\n",
        "    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)\n",
        f"    (uuid {su})\n",
    ]
    out.append(f"    (property {q('Reference')} {q(comp.ref)} (at {num(x + 5)} {num(y - 3)} 0)\n      (effects (font (size 1.27 1.27)) (justify left))\n    )\n")
    out.append(f"    (property {q('Value')} {q(comp.value)} (at {num(x + 5)} {num(y + 1)} 0)\n      (effects (font (size 1.27 1.27)) (justify left))\n    )\n")
    out.append(f"    (property {q('Footprint')} {q('')} (at {num(x)} {num(y)} 0)\n      (effects (font (size 1.27 1.27)) hide)\n    )\n")
    out.append(f"    (property {q('Datasheet')} {q('~')} (at {num(x)} {num(y)} 0)\n      (effects (font (size 1.27 1.27)) hide)\n    )\n")
    out.append(f"    (property {q('Progen.Kind')} {q(comp.spec.kind)} (at {num(x)} {num(y)} 0)\n      (effects (font (size 1.27 1.27)) hide)\n    )\n")
    for pin in comp.spec.pins:
        out.append(f"    (pin {q(pin.number)} (uuid {stable_uuid(su + ':pin:' + pin.number)}))\n")
    out.append("    (instances\n")
    out.append(f"      (project {q(project_name)}\n")
    out.append(f"        (path {q('/' + ROOT_UUID)}\n")
    out.append(f"          (reference {q(comp.ref)}) (unit 1) (value {q(comp.value)}) (footprint {q('')})\n")
    out.append("        )\n      )\n    )\n  )\n")
    return "".join(out)


def wire(a: Tuple[float, float], b: Tuple[float, float], project_name: str, i: int) -> str:
    if a == b:
        return ""
    return f"  (wire (pts (xy {num(a[0])} {num(a[1])}) (xy {num(b[0])} {num(b[1])}))\n    (stroke (width 0) (type default))\n    (uuid {stable_uuid(project_name + ':wire:' + str(i) + str(a) + str(b))})\n  )\n"


def label(text: str, at: Tuple[float, float], project_name: str, i: int) -> str:
    return f"  (label {q(text)} (at {num(at[0])} {num(at[1])} 0) (fields_autoplaced)\n    (effects (font (size 1.27 1.27)) (justify left bottom))\n    (uuid {stable_uuid(project_name + ':label:' + str(i) + text)})\n  )\n"


def text_obj(text: str, at: Tuple[float, float], project_name: str, i: int) -> str:
    return f"  (text {q(text)} (exclude_from_sim no) (at {num(at[0])} {num(at[1])} 0)\n    (effects (font (size 1.27 1.27)) (justify left bottom))\n    (uuid {stable_uuid(project_name + ':text:' + str(i) + text)})\n  )\n"


def pin_stub(pin: PinDef, pin_xy: Tuple[float, float], length: float = 5.08) -> Tuple[float, float]:
    if pin.side == "left":
        return (pin_xy[0] - length, pin_xy[1])
    if pin.side == "right":
        return (pin_xy[0] + length, pin_xy[1])
    if pin.side == "top":
        return (pin_xy[0], pin_xy[1] - length)
    return (pin_xy[0], pin_xy[1] + length)


def build_50_zoo() -> tuple[str, list[Component], list[tuple[tuple[float, float], tuple[float, float]]], list[tuple[str, tuple[float, float]]], list[tuple[str, tuple[float, float]]]]:
    project_name = "OPEN_THIS_PROJECT__v8_50_unique_components_together__PROJECT_FILE"
    comps: List[Component] = []
    wires: List[tuple[tuple[float, float], tuple[float, float]]] = []
    labels: List[tuple[str, tuple[float, float]]] = []
    texts: List[tuple[str, tuple[float, float]]] = []
    refs: Dict[str, int] = {}

    def next_ref(prefix: str) -> str:
        refs[prefix] = refs.get(prefix, 0) + 1
        return f"{prefix}{refs[prefix]}"

    start_x, start_y, dx, dy = 30, 35, 42, 34
    for idx, spec in enumerate(KIND_SPECS):
        row, col = divmod(idx, 10)
        cx, cy = start_x + col * dx, start_y + row * dy
        comp = Component(next_ref(spec.ref_prefix), spec, (cx, cy), {}, spec.value)
        comps.append(comp)
        for pin in spec.pins:
            pxy = pin_world(comp, pin.number)
            wires.append((pxy, pin_stub(pin, pxy)))
        labels.append((spec.kind, (cx - 12, cy - 12)))

    texts.append(("V8 50-unique-component KiCad visual smoke sheet\nEach component has connected pin stubs. Generic symbols are used for unverified stock KiCad symbols until donor extraction promotes them.", (20, 212)))
    return project_name, comps, wires, labels, texts


def write_sch(project_name: str, comps: list[Component], wires_data, labels_data, texts_data) -> str:
    used: List[KindSpec] = []
    seen: set[str] = set()
    for comp in comps:
        if comp.spec.lib_id not in seen:
            seen.add(comp.spec.lib_id)
            used.append(comp.spec)

    out = [
        f"(kicad_sch (version {SCH_VERSION}) (generator {q(GENERATOR)}) (generator_version {q('v8')})\n",
        f"  (uuid {ROOT_UUID})\n",
        "  (paper \"A2\")\n",
        lib_symbols_block(used),
    ]
    for i, (a, b) in enumerate(wires_data, 1):
        out.append(wire(a, b, project_name, i))
    for i, (txt, at) in enumerate(texts_data, 1):
        out.append(text_obj(txt, at, project_name, i))
    for i, (txt, at) in enumerate(labels_data, 1):
        out.append(label(txt, at, project_name, i))
    for comp in comps:
        out.append(symbol_instance(comp, project_name))
    out.append("  (sheet_instances\n    (path \"/\" (page \"1\"))\n  )\n)\n")
    return "".join(out)


def validate_schematic_text(text: str) -> dict[str, object]:
    depth = 0
    in_string = False
    escaped = False
    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth < 0:
                return {"ok": False, "error": f"extra right paren at {i}"}

    import re

    bad_wires = 0
    for match in re.finditer(r"\(wire \(pts(.*?)\)\s*\n\s*\(stroke", text, re.S):
        if match.group(1).count("(xy ") != 2:
            bad_wires += 1

    return {
        "ok": depth == 0 and not in_string and bad_wires == 0,
        "depth": depth,
        "in_string": in_string,
        "bad_wire_objects": bad_wires,
        "symbol_instances": text.count("\n  (symbol (lib_id"),
        "lib_symbols": text.count("\n    (symbol "),
    }


def write_project(out_dir: Path, project_name: str, comps, wires_data, labels_data, texts_data, purpose: str) -> dict[str, object]:
    out_dir.mkdir(parents=True, exist_ok=True)
    sch = write_sch(project_name, comps, wires_data, labels_data, texts_data)
    pro = write_project_json(project_name)

    outputs = {
        f"{project_name}.kicad_pro": pro,
        f"{project_name}.kicad_sch": sch,
        f"OPEN_THIS_FIRST__{project_name}__PROJECT_FILE.kicad_pro": pro,
        f"OPEN_THIS_FIRST__{project_name}__SCHEMATIC_FILE.kicad_sch": sch,
        "README_OPEN_FIRST.txt": f"Open OPEN_THIS_FIRST__{project_name}__PROJECT_FILE.kicad_pro in KiCad.\nV8 true 50-component visual smoke-test generator.\n",
    }
    for name, content in outputs.items():
        (out_dir / name).write_text(content, encoding="utf-8")

    manifest = {
        "project_name": project_name,
        "generator": GENERATOR,
        "purpose": purpose,
        "component_count": len(comps),
        "unique_kind_count": len({c.spec.kind for c in comps}),
        "kinds": [c.spec.kind for c in comps],
        "verified_stock_symbol_count": sum(1 for c in comps if c.spec.verified),
        "generic_project_local_symbol_count": sum(1 for c in comps if not c.spec.verified),
        "static_checks": validate_schematic_text(sch),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Generate KiCad V8 50-unique-component visual smoke-test projects.")
    parser.add_argument("--out", type=Path, default=Path("out/kicad_v8_50_component_zoo"))
    parser.add_argument("--zip", type=Path, default=None)
    args = parser.parse_args()

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)

    project_name, comps, wires, labels, texts = build_50_zoo()
    all_manifest = write_project(args.out / "all_50_unique_components_together", project_name, comps, wires, labels, texts, "one schematic containing 50 unique component kinds together")

    report = {
        "summary": "V8 produces one all-together schematic containing 50 unique component kinds.",
        "all_together_manifest": all_manifest,
        "important_honesty": "Only R/L/VDC/VSIN are verified upstream stock symbols here; the remaining component shapes are project-local Progen50 generic symbols to prove parsing, placement and pin-endpoint wiring before exact donor symbol promotion.",
    }
    (args.out / "V8_REPORT.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.zip:
        if args.zip.exists():
            args.zip.unlink()
        with zipfile.ZipFile(args.zip, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in args.out.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(args.out))
        print(f"wrote {args.zip}")
        print("sha256", hashlib.sha256(args.zip.read_bytes()).hexdigest())
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
