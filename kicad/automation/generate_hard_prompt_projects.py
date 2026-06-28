#!/usr/bin/env python3
"""Generate KiCad projects from the user's structured hard-test text.

The input format is intentionally narrow: sections containing "Place ..." and
"Connect ..." statements.  It is deterministic and exists to stress the KiCad
writer/router on large pin-level digital projects without relying on an LLM.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from kicad.generator.kicad_json_to_project import KIND_SPECS, slugify, write_project_from_json  # noqa: E402


Component = dict[str, Any]
Circuit = dict[str, Any]

POWER_NETS = {"+5V": "VCC", "5V": "VCC", "VCC": "VCC", "GND": "GND", "0V": "GND", "0": "GND"}
PROJECT_RANGES = {
    "PROJECT_1": ("PROJECT_1_LEVEL_1_4BIT_ALU", "PROJECT_2_LEVEL_1_PASSWORD_INPUT_AND_MEMORY"),
    "PROJECT_2": ("PROJECT_2_LEVEL_1_PASSWORD_INPUT_AND_MEMORY", "PROJECT_3_LEVEL_1_DIGITAL_CLOCK_COUNTERS"),
    "PROJECT_3": ("PROJECT_3_LEVEL_1_DIGITAL_CLOCK_COUNTERS", None),
}


def clean_net(raw: str) -> str:
    value = raw.strip().strip(".").strip()
    value = re.sub(r"^net\s+", "", value, flags=re.I)
    value = value.replace("+5V", "VCC").replace("0V", "GND")
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return POWER_NETS.get(value.upper(), value.upper() if value.upper() in {"VCC", "GND"} else value)


def normalize_ref(raw: str) -> str:
    value = raw.strip().strip(".").strip()
    value = re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")
    return value or "X"


def infer_kind(ref: str) -> str:
    upper = ref.upper()
    for kind in sorted(KIND_SPECS, key=len, reverse=True):
        if upper == kind or upper.endswith("_" + kind):
            return kind
    if upper.endswith("_2N2222") or "2N2222" in upper:
        return "2N2222"
    if "7447" in upper:
        return "7447"
    if "74HC14" in upper:
        return "74HC14"
    if "DIP" in upper or "SWITCH" in upper or "BUTTON" in upper:
        return "SW_DIP"
    if "BUZZER" in upper:
        return "LED"
    if "DISPLAY" in upper and "7447" not in upper:
        return "7SEG_CA"
    if "DETECT_GATES" in upper:
        return "74HC08"
    return "TESTPOINT"


def strip_kind_suffix(ref: str) -> tuple[str, str] | None:
    upper = ref.upper()
    for kind in sorted(KIND_SPECS, key=len, reverse=True):
        suffix = "_" + kind
        if upper.endswith(suffix):
            return ref[: -len(suffix)], kind
    if upper.endswith("_2N2222"):
        return ref[: -len("_2N2222")], "2N2222"
    return None


def resolve_component_key(components: dict[str, Component], ref: str) -> str | None:
    if ref in components:
        return ref
    stripped = strip_kind_suffix(ref)
    if stripped and stripped[0] in components:
        return stripped[0]
    for existing, comp in components.items():
        if existing.startswith(ref + "_") and str(comp.get("kind", "")).upper() != "TESTPOINT":
            return existing
    return None


def default_pin_for(kind: str, ref: str, net: str) -> dict[str, str]:
    if kind == "TESTPOINT":
        return {"1": net}
    if kind == "SW_DIP":
        return {"1": net, "2": "VCC"}
    if kind == "SW_PUSH":
        return {"1": net, "2": "VCC"}
    if kind == "LED":
        return {"1": net, "2": "GND"}
    if kind == "7SEG_CA":
        return {"1": net, "10": "VCC"}
    return {"1": net}


def ensure_component(components: dict[str, Component], ref: str, kind: str | None = None, net: str | None = None) -> Component:
    ref = normalize_ref(ref)
    existing_key = resolve_component_key(components, ref)
    if existing_key:
        return components[existing_key]
    stripped = strip_kind_suffix(ref)
    if stripped and kind is None:
        ref, kind = stripped
    kind = kind or infer_kind(ref)
    if kind not in KIND_SPECS:
        kind = "TESTPOINT"
    if ref not in components:
        components[ref] = {
            "id": ref,
            "kind": kind,
            "value": kind,
            "pins": default_pin_for(kind, ref, clean_net(net or ref)),
        }
    else:
        components[ref]["kind"] = components[ref].get("kind") or kind
    return components[ref]


def set_pin(components: dict[str, Component], ref: str, pin: str, net: str) -> None:
    comp = ensure_component(components, ref)
    comp.setdefault("pins", {})[str(pin)] = clean_net(net)


def add_component(components: dict[str, Component], ref: str, kind: str | None = None) -> None:
    ensure_component(components, ref, kind)


def add_two_pin(components: dict[str, Component], ref: str, kind: str, a: str, b: str, value: str) -> None:
    ref = normalize_ref(ref)
    components[ref] = {"id": ref, "kind": kind, "value": value, "pins": {"1": clean_net(a), "2": clean_net(b)}}


def project_block(text: str, project_key: str) -> str:
    start_marker, end_marker = PROJECT_RANGES[project_key]
    start = text.index(start_marker)
    end = text.index(end_marker) if end_marker else len(text)
    prefix = text[: text.index("PROJECT_1_LEVEL_1_4BIT_ALU")]
    return prefix + "\n" + text[start:end]


def parse_place(line: str, components: dict[str, Component]) -> None:
    body = line.removeprefix("Place ").strip().strip(".")
    if body.startswith("100nF capacitor"):
        return
    if body.startswith("one 7447"):
        return
    if body.startswith("four DIP switches named "):
        names = [normalize_ref(part) for part in body.split("named ", 1)[1].split(",")]
        for name in names:
            add_component(components, name, "SW_DIP")
        return
    if body.startswith("four 4-bit DIP switch groups named "):
        groups = [normalize_ref(part) for part in body.split("named ", 1)[1].split(",")]
        for group in groups:
            for bit in range(4):
                add_component(components, f"{group}_B{bit}", "SW_DIP")
        return
    body = re.sub(r"\s+wired same as .*$", "", body)
    if " and connect " in body:
        body = body.split(" and connect ", 1)[0]
    refs = [normalize_ref(part) for part in re.split(r",\s*", body)]
    for ref in refs:
        if ref:
            add_component(components, ref)


def parse_direct_connect(line: str, components: dict[str, Component]) -> bool:
    patterns = [
        (r"^Connect\s+([A-Za-z0-9_]+)\s+pin(\d+)\s+to\s+(.+?)\.$", "pin_to_net"),
        (r"^Connect\s+(.+?)\s+to\s+([A-Za-z0-9_]+)\s+pin(\d+)\.$", "net_to_pin"),
    ]
    for pattern, kind in patterns:
        match = re.match(pattern, line, re.I)
        if not match:
            continue
        if kind == "pin_to_net":
            ref, pin, net = match.groups()
        else:
            net, ref, pin = match.groups()
        if "unconnected" in net.lower():
            return True
        set_pin(components, ref, pin, net)
        return True
    return False


def parse_output_to_net(line: str, components: dict[str, Component]) -> bool:
    match = re.match(r"^Connect\s+([A-Za-z0-9_]+)\s+output\s+to\s+(?:net\s+)?([A-Za-z0-9_+]+)\.$", line, re.I)
    if not match:
        return False
    ref, net = match.groups()
    comp = ensure_component(components, ref, net=net)
    comp.setdefault("pins", {})["1"] = clean_net(net)
    return True


def parse_multi_to_pins(line: str, components: dict[str, Component]) -> bool:
    match = re.match(r"^Connect\s+(.+?)\s+to\s+([A-Za-z0-9_]+)\s+pins?([0-9,\s]+)\.$", line, re.I)
    if not match:
        return False
    nets_raw, ref, pins_raw = match.groups()
    nets = [clean_net(part) for part in re.split(r",\s*", nets_raw) if part.strip()]
    pins = [part.strip() for part in pins_raw.split(",") if part.strip()]
    for net, pin in zip(nets, pins):
        set_pin(components, ref, pin, net)
    return True


def parse_res_cap_between(line: str, components: dict[str, Component], counters: dict[str, int]) -> bool:
    lower = line.lower()
    kind = None
    value = None
    if " resistor " in lower or lower.startswith("connect 10k resistor") or lower.startswith("connect 68k resistor"):
        kind = "R"
        value = re.search(r"Connect\s+([0-9.]+[kKmMuUnNpP]?)\s+resistor", line)
    elif " capacitor " in lower or " capacitor " in lower:
        kind = "C"
        value = re.search(r"Connect\s+([0-9.]+[uUnNpPfFmM]+)\s+capacitor", line)
    if not kind:
        return False
    match = re.match(r"^Connect\s+([0-9.]+[A-Za-z]*)\s+(?:resistor|capacitor)(?:\s+positive|\s+negative)?\s+from\s+(.+?)\s+to\s+(.+?)\.$", line, re.I)
    if not match:
        match = re.match(r"^Connect\s+([0-9.]+[A-Za-z]*)\s+(?:resistor|capacitor)(?:\s+positive|\s+negative)?\s+between\s+(.+?)\s+and\s+(.+?)\.$", line, re.I)
    if not match:
        return False
    value_text, a, b = match.groups()
    counters[kind] = counters.get(kind, 0) + 1
    add_two_pin(components, f"{kind}_AUTO_{counters[kind]:03d}", kind, a, b, value_text)
    return True


def parse_switch_between(line: str, components: dict[str, Component], counters: dict[str, int]) -> bool:
    match = re.match(r"^Connect\s+(?:switch|pushbutton)\s+(?:one side|from)\s+to\s+(.+?),?\s*(?:other side|to)\s+(?:to\s+)?(.+?)\.$", line, re.I)
    if not match:
        return False
    a, b = match.groups()
    counters["SW"] = counters.get("SW", 0) + 1
    add_two_pin(components, f"SW_AUTO_{counters['SW']:03d}", "SW_PUSH", a, b, "SW")
    return True


def parse_line(line: str, components: dict[str, Component], counters: dict[str, int]) -> None:
    line = line.strip()
    if not line:
        return
    if line.startswith("Place "):
        parse_place(line, components)
        return
    if not line.startswith("Connect "):
        return
    for parser in (parse_multi_to_pins, parse_direct_connect, parse_output_to_net):
        if parser(line, components):
            return
    for parser in (parse_res_cap_between, parse_switch_between):
        if parser(line, components, counters):
            return


def apply_global_quality(components: dict[str, Component]) -> None:
    if "V1" not in components:
        components["V1"] = {"id": "V1", "kind": "VDC", "value": "5", "pins": {"1": "VCC", "2": "GND"}}
    components["GND1"] = {"id": "GND1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}}
    decouple_index = 1
    display_index = 1
    for ref, comp in list(components.items()):
        kind = str(comp["kind"]).upper()
        pins = comp.setdefault("pins", {})
        if kind.startswith("74") or kind in {"NE555", "4008", "4013", "4017", "4020", "4024", "4027", "4040", "4051", "4060", "4063", "4093", "4511", "4518", "4520"}:
            count = len(KIND_SPECS[kind].pins)
            pins.setdefault(str(count), "VCC")
            pins.setdefault("8" if count in {16, 20} else "7", "GND")
            components[f"CDEC_{decouple_index:03d}_{ref}"] = {
                "id": f"CDEC_{decouple_index:03d}_{ref}",
                "kind": "C",
                "value": "100n",
                "pins": {"1": "VCC", "2": "GND"},
            }
            decouple_index += 1
        if kind in {"7447", "74LS47", "74HC47", "74HC48", "4511"}:
            seg_map = {"13": "A", "12": "B", "11": "C", "10": "D", "9": "E", "15": "F", "14": "G"}
            display_ref = f"DS_{display_index:03d}_{ref}"
            display_pins = {"10": "VCC"}
            for pin, seg in seg_map.items():
                net = pins.setdefault(pin, f"{ref}_SEG_{seg}")
                components[f"RSEG_{display_index:03d}_{seg}_{ref}"] = {
                    "id": f"RSEG_{display_index:03d}_{seg}_{ref}",
                    "kind": "R",
                    "value": "330",
                    "pins": {"1": net, "2": f"{display_ref}_{seg}"},
                }
                display_pins[str(len(display_pins))] = f"{display_ref}_{seg}"
            components[display_ref] = {"id": display_ref, "kind": "7SEG_CA", "value": "7SEG_CA", "pins": display_pins}
            display_index += 1


def build_project(text: str, key: str) -> Circuit:
    block = project_block(text, key)
    components: dict[str, Component] = {}
    counters: dict[str, int] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("-"):
            continue
        parse_line(line, components, counters)
    apply_global_quality(components)
    title = {
        "PROJECT_1": "Level 1-4 four-bit ALU with display and operation counter",
        "PROJECT_2": "Password memory, compare, key add/xor, decrypt display",
        "PROJECT_3": "Digital clock with alarm, timezone mux, and calendar display",
    }[key]
    ordered = sorted(components.values(), key=lambda item: item["id"])
    nets = sorted({net for item in ordered for net in item.get("pins", {}).values()})
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": key.lower() + "_hard_test", "title": title, "analysis": [".save all"]},
        "components": ordered,
        "nets": {net: f"{net} net" for net in nets},
        "notes": [
            "Generated deterministically from structured hard-test text.",
            "Local labels plus short stubs are used for rails and broad digital buses.",
        ],
    }


def generate(input_text: Path, outdir: Path, *, clean: bool = True) -> dict[str, Any]:
    if clean and outdir.exists():
        shutil.rmtree(outdir)
    json_dir = outdir / "json"
    project_dir = outdir / "projects"
    json_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    text = input_text.read_text(encoding="utf-8", errors="replace")
    results: list[dict[str, Any]] = []
    for key in ("PROJECT_1", "PROJECT_2", "PROJECT_3"):
        circuit = build_project(text, key)
        slug = slugify(circuit["project"]["name"])
        input_path = json_dir / f"{slug}.json"
        input_path.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
        manifest = write_project_from_json(circuit, project_dir / slug)
        results.append(
            {
                "id": key,
                "name": slug,
                "ok": bool(manifest["static_checks"]["ok"]),
                "component_count": manifest["component_count"],
                "wire_count": manifest["static_checks"]["wire_count"],
                "label_count": manifest["static_checks"]["label_count"],
                "no_connect_count": manifest["static_checks"]["no_connect_count"],
                "router_warning_count": len(manifest["static_checks"]["router_warnings"]),
                "open_this": str((project_dir / slug / manifest["open_this"]).relative_to(outdir)),
                "manifest": str((project_dir / slug / "manifest.json").relative_to(outdir)),
                "input": str(input_path.relative_to(outdir)),
            }
        )
    run_manifest = {
        "run_id": outdir.name,
        "generated_at_utc": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "schema_version": "progen-kicad-hard-prompt/v1",
        "input_text": str(input_text),
        "target_count": 3,
        "ok_count": sum(1 for row in results if row["ok"]),
        "failure_count": sum(1 for row in results if not row["ok"]),
        "results": results,
    }
    (outdir / "run_manifest.json").write_text(json.dumps(run_manifest, indent=2), encoding="utf-8")
    return run_manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate the three hard-test KiCad projects from structured text.")
    parser.add_argument("--input-text", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, default=REPO_ROOT / "kicad" / "experiments" / "runs" / "hard_prompt_latest")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args(argv)
    manifest = generate(args.input_text, args.outdir, clean=not args.no_clean)
    print(json.dumps(manifest, indent=2))
    return 0 if manifest["failure_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
