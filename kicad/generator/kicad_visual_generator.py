#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, re, uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GENERATOR = "progen-kicad-visual-generator-v0"
SCH_VERSION = "20231120"
ROOT_UUID = "00000000-0000-0000-0000-000000000001"
SUPPORTED = {"R", "C", "L", "D", "LED", "VDC", "VSIN", "VPULSE", "GND"}
LIB_ID = {
    "R": "Device:R", "C": "Device:C", "L": "Device:L", "D": "Device:D", "LED": "Device:LED",
    "VDC": "Simulation_SPICE:VDC", "VSIN": "Simulation_SPICE:VSIN", "VPULSE": "Simulation_SPICE:VPULSE", "GND": "power:GND",
}
SIM_DEVICE = {"R":"R", "C":"C", "L":"L", "D":"D", "LED":"D", "VDC":"V", "VSIN":"V", "VPULSE":"V"}
PINS = {k:["1","2"] for k in ["R","C","L","D","LED","VDC","VSIN","VPULSE"]} | {"GND":["1"]}


def safe_name(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", s.strip()) or "kicad_generated"

def q(s: Any) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"') + '"'

def num(x: float) -> str:
    x = float(x)
    return str(int(x)) if x.is_integer() else f"{x:.6f}".rstrip("0").rstrip(".")

def uid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

@dataclass
class Component:
    ref: str
    kind: str
    value: str
    at: tuple[float, float]
    rotation: float = 0.0
    pins: dict[str, str] = field(default_factory=dict)
    spice_model: str | None = None
    spice_params: str | None = None
    properties: dict[str, str] = field(default_factory=dict)

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Component":
        kind = str(d["kind"]).upper()
        if kind not in SUPPORTED:
            raise ValueError(f"unsupported kind {kind}")
        xy = d.get("at") or d.get("xy") or [0, 0]
        return Component(str(d["ref"]), kind, str(d.get("value", kind)), (float(xy[0]), float(xy[1])), float(d.get("rotation", 0)), {str(k):str(v) for k,v in d.get("pins",{}).items()}, d.get("spice_model"), d.get("spice_params"), {str(k):str(v) for k,v in d.get("properties",{}).items()})

@dataclass
class Wire:
    points: list[tuple[float, float]]
    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Wire":
        pts = d.get("points") or d.get("pts")
        if not pts or len(pts) < 2: raise ValueError("wire needs at least two points")
        return Wire([(float(x), float(y)) for x,y in pts])

@dataclass
class Label:
    text: str
    at: tuple[float, float]
    rotation: float = 0.0
    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Label":
        xy = d.get("at") or d.get("xy")
        return Label(str(d["text"]), (float(xy[0]), float(xy[1])), float(d.get("rotation", 0)))

@dataclass
class Directive:
    text: str
    at: tuple[float, float]
    rotation: float = 0.0
    @staticmethod
    def from_dict(d: dict[str, Any]) -> "Directive":
        xy = d.get("at") or d.get("xy") or [20,20]
        return Directive(str(d["text"]), (float(xy[0]), float(xy[1])), float(d.get("rotation", 0)))

@dataclass
class CircuitIR:
    project_name: str
    components: list[Component]
    wires: list[Wire]
    labels: list[Label]
    directives: list[Directive]
    notes: list[str]
    @staticmethod
    def from_dict(d: dict[str, Any]) -> "CircuitIR":
        return CircuitIR(safe_name(str(d.get("project_name") or d.get("name") or "kicad_generated")), [Component.from_dict(x) for x in d.get("components", [])], [Wire.from_dict(x) for x in d.get("wires", [])], [Label.from_dict(x) for x in d.get("labels", [])], [Directive.from_dict(x) for x in d.get("spice_directives", d.get("texts", []))], [str(x) for x in d.get("notes", [])])


def validate(ir: CircuitIR) -> list[str]:
    errors, refs = [], set()
    for c in ir.components:
        if c.ref in refs: errors.append(f"duplicate ref {c.ref}")
        refs.add(c.ref)
        for p in c.pins:
            if p not in PINS[c.kind]: errors.append(f"invalid pin {c.ref}.{p}; valid {PINS[c.kind]}")
    return errors


def kicad_pro(ir: CircuitIR) -> str:
    return json.dumps({
        "meta":{"filename":f"{ir.project_name}.kicad_pro","version":1},
        "sheets":[[ROOT_UUID,""]],
        "libraries":{"pinned_symbol_libs":[],"pinned_footprint_libs":[]},
        "schematic":{"drawing":{"default_line_thickness":6,"default_text_size":50},"meta":{"version":1},"plot_directory":""},
        "erc":{"erc_exclusions":[],"meta":{"version":0}},
        "net_settings":{"classes":[{"name":"Default","clearance":0.2,"track_width":0.25,"via_diameter":0.8,"via_drill":0.4,"wire_width":6}],"meta":{"version":3}},
        "text_variables":{}, "boards":[], "board":{"design_settings":{"defaults":{},"rules":{}}}
    }, indent=2) + "\n"


def prop(name: str, value: str, x: float, y: float, rot: float = 0, hide: bool = False) -> str:
    return f"    (property {q(name)} {q(value)} (at {num(x)} {num(y)} {num(rot)})\n      (effects (font (size 1.27 1.27)){' hide' if hide else ''})\n    )\n"


def symbol(c: Component, project: str) -> str:
    x,y = c.at; su = uid(f"{project}:{c.ref}:{c.kind}:{x}:{y}:{c.rotation}")
    out = [f"  (symbol (lib_id {q(LIB_ID[c.kind])}) (at {num(x)} {num(y)} {num(c.rotation)}) (unit 1)\n", "    (in_bom yes) (on_board yes) (dnp no)\n", f"    (uuid {su})\n"]
    out += [prop("Reference", c.ref, x+2.54, y-2.54, hide=c.kind=="GND"), prop("Value", c.value, x+2.54, y+2.54), prop("Footprint", c.properties.get("Footprint",""), x, y, hide=True), prop("Datasheet", c.properties.get("Datasheet", "~" if c.kind!="GND" else ""), x, y, hide=True)]
    if c.kind in SIM_DEVICE: out.append(prop("Sim.Device", c.properties.get("Sim.Device", SIM_DEVICE[c.kind]), x, y, hide=True))
    if c.spice_model: out.append(prop("Spice_Model", c.spice_model, x, y+5.08))
    if c.spice_params: out.append(prop("Sim.Params", c.spice_params, x, y, hide=True))
    for p in PINS[c.kind]: out.append(f"    (pin {q(p)} (uuid {uid(f'{su}:pin:{p}')}))\n")
    out += ["    (instances\n", f"      (project {q(project)}\n", f"        (path \"/{ROOT_UUID}\"\n", f"          (reference {q(c.ref)}) (unit 1) (value {q(c.value)}) (footprint {q(c.properties.get('Footprint',''))})\n", "        )\n      )\n    )\n  )\n"]
    return "".join(out)


def wire(w: Wire, project: str, i: int) -> str:
    # KiCad wire objects are line segments. Multi-point CircuitIR wires must be emitted
    # as consecutive two-point wire objects or KiCad 10 reports a schematic parse error.
    segments=[]
    for j,(a,b) in enumerate(zip(w.points, w.points[1:]),1):
        pts=f"(xy {num(a[0])} {num(a[1])}) (xy {num(b[0])} {num(b[1])})"
        segments.append(f"  (wire (pts {pts})\n    (stroke (width 0) (type default))\n    (uuid {uid(f'{project}:wire:{i}:{j}:{a}:{b}')})\n  )\n")
    return "".join(segments)

def label(l: Label, project: str, i: int) -> str:
    x,y=l.at
    return f"  (label {q(l.text)} (at {num(x)} {num(y)} {num(l.rotation)}) (fields_autoplaced)\n    (effects (font (size 1.27 1.27)) (justify left bottom))\n    (uuid {uid(f'{project}:label:{i}:{l.text}:{l.at}')})\n  )\n"

def text(t: Directive, project: str, i: int) -> str:
    x,y=t.at
    return f"  (text {q(t.text)} (at {num(x)} {num(y)} {num(t.rotation)})\n    (effects (font (size 1.27 1.27)) (justify left bottom))\n    (uuid {uid(f'{project}:text:{i}:{t.text}:{t.at}')})\n  )\n"


def kicad_sch(ir: CircuitIR) -> str:
    out = [f"(kicad_sch (version {SCH_VERSION}) (generator {q(GENERATOR)})\n", f"  (uuid {ROOT_UUID})\n", "  (paper \"A4\")\n", "  (lib_symbols\n  )\n"]
    out += [wire(w, ir.project_name, i) for i,w in enumerate(ir.wires,1)]
    out += [text(t, ir.project_name, i) for i,t in enumerate(ir.directives,1)]
    out += [label(l, ir.project_name, i) for i,l in enumerate(ir.labels,1)]
    out += [symbol(c, ir.project_name) for c in ir.components]
    out += ["  (sheet_instances\n", "    (path \"/\" (page \"1\"))\n", "  )\n", ")\n"]
    return "".join(out)


def debug_spice(ir: CircuitIR) -> str:
    lines=[f"* {ir.project_name} debug netlist"]
    for c in ir.components:
        if c.kind=="GND": continue
        a = "0" if c.pins.get("1", "NC1").upper()=="GND" else c.pins.get("1", "NC1")
        b = "0" if c.pins.get("2", "NC2").upper()=="GND" else c.pins.get("2", "NC2")
        if c.kind in {"R","C","L"}: lines.append(f"{c.ref} {a} {b} {c.value}")
        elif c.kind in {"D","LED"}: lines.append(f"{c.ref} {a} {b} {c.spice_model or c.value}")
        elif c.kind=="VDC": lines.append(f"{c.ref} {a} {b} DC {c.value}")
        elif c.kind=="VSIN": lines.append(f"{c.ref} {a} {b} {c.spice_model or 'SIN(0 1 1k)'}")
        elif c.kind=="VPULSE": lines.append(f"{c.ref} {a} {b} {c.spice_model or 'PULSE(0 5 0 1u 1u 1m 2m)'}")
    for d in ir.directives:
        lines += [x.strip() for x in d.text.splitlines() if x.strip().startswith('.')]
    return "\n".join(lines+[".end", ""])


def write_project(ir: CircuitIR, out_dir: Path) -> dict[str, Any]:
    errs=validate(ir)
    if errs: raise SystemExit("CircuitIR validation failed:\n"+"\n".join(errs))
    out_dir.mkdir(parents=True, exist_ok=True)
    files={f"{ir.project_name}.kicad_pro":kicad_pro(ir), f"{ir.project_name}.kicad_sch":kicad_sch(ir), f"{ir.project_name}.cir":debug_spice(ir), "README_OPEN_FIRST.txt":f"Open {ir.project_name}.kicad_pro in KiCad. The .cir file is debug only.\n"}
    for name, content in files.items(): (out_dir/name).write_text(content, encoding="utf-8")
    m={"project_name":ir.project_name,"generator":GENERATOR,"outputs":sorted(files),"component_count":len(ir.components),"wire_count":len(ir.wires),"label_count":len(ir.labels),"spice_directive_count":len(ir.directives),"supported_kinds_used":sorted({c.kind for c in ir.components}),"status":"static_generation_only__run_kicad_cli_or_open_gui_next","notes":ir.notes}
    (out_dir/"manifest.json").write_text(json.dumps(m,indent=2),encoding="utf-8")
    return m


def example(name: str) -> CircuitIR:
    if name == "diode_iv":
        return CircuitIR.from_dict({"project_name":"OPEN_THIS_PROJECT__diode_iv__PROJECT_FILE","components":[{"ref":"V1","kind":"VDC","value":"0","at":[30,40],"pins":{"1":"VIN","2":"GND"}},{"ref":"R1","kind":"R","value":"1k","at":[50,40],"rotation":90,"pins":{"1":"VIN","2":"N1"}},{"ref":"D1","kind":"D","value":"1N4001","at":[70,40],"pins":{"1":"N1","2":"GND"}},{"ref":"#PWR01","kind":"GND","value":"GND","at":[30,55],"pins":{"1":"GND"}},{"ref":"#PWR02","kind":"GND","value":"GND","at":[70,55],"pins":{"1":"GND"}}],"wires":[{"points":[[30,35],[30,30],[50,30],[50,36]]},{"points":[[50,44],[70,40]]},{"points":[[30,45],[30,55]]},{"points":[[70,40],[70,55]]}],"labels":[{"text":"VIN","at":[40,30]},{"text":"VD","at":[72,39]}],"spice_directives":[{"text":".dc V1 0 10 0.1\n.save all","at":[25,75]}],"notes":["EE-215 diode characteristics target"]})
    if name == "rc_lowpass":
        return CircuitIR.from_dict({"project_name":"OPEN_THIS_PROJECT__rc_lowpass__PROJECT_FILE","components":[{"ref":"V1","kind":"VSIN","value":"VSIN","spice_model":"SIN(0 1 1k)","at":[30,45],"pins":{"1":"IN","2":"GND"}},{"ref":"R1","kind":"R","value":"1k","at":[55,35],"rotation":90,"pins":{"1":"IN","2":"OUT"}},{"ref":"C1","kind":"C","value":"1u","at":[75,48],"pins":{"1":"OUT","2":"GND"}},{"ref":"#PWR01","kind":"GND","value":"GND","at":[30,55],"pins":{"1":"GND"}},{"ref":"#PWR02","kind":"GND","value":"GND","at":[75,60],"pins":{"1":"GND"}}],"wires":[{"points":[[30,40],[30,35],[51,35]]},{"points":[[59,35],[75,35],[75,44]]},{"points":[[75,52],[75,60]]},{"points":[[30,50],[30,55]]}],"labels":[{"text":"IN","at":[37,35]},{"text":"OUT","at":[76,35]}],"spice_directives":[{"text":".tran 1u 5m\n.save all","at":[25,75]}],"notes":["Visual RC circuit with transient directive"]})
    raise ValueError("examples: diode_iv, rc_lowpass")


def main() -> None:
    ap=argparse.ArgumentParser()
    g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--input",type=Path)
    g.add_argument("--example",choices=["diode_iv","rc_lowpass"])
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    ir=example(args.example) if args.example else CircuitIR.from_dict(json.loads(args.input.read_text()))
    print(json.dumps(write_project(ir,args.out),indent=2))

if __name__=="__main__":
    main()
