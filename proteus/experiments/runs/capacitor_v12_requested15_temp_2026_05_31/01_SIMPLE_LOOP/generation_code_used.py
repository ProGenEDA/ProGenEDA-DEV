"""Temporary capacitor V12 diagnostics: 15 requested networks.

The user accepted V10 and V11. V12 regenerates the same 15 named circuit
topologies previously requested for resistors, but using V10/V11 capacitor
terminal records.

This is still temporary. It intentionally keeps V0/G0 as ordinary two-character
terminal labels so the batch tests capacitor topology scaling without adding
power/ground symbol records as another variable.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR_2026_05_30 = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-30"
TOOL_DIR_2026_05_31 = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-31"
for path in (REPO_ROOT / "src", TOOL_DIR_2026_05_30, TOOL_DIR_2026_05_31):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_capacitor_v10_manual_donor_temp as v10
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

SOURCE_ROOT = REPO_ROOT / "experiments" / "requested_resistor_networks_oriented_2026_05_30"
OUT_ROOT = REPO_ROOT / "experiments" / "capacitor_v12_requested15_temp_2026_05_31"
SAFE_X_STEP = 2540000
SAFE_Y_STEP = 2540000
BASE_X = -6858000
BASE_Y = 5080000


def cap_ref(index: int) -> str:
    if index <= 9:
        return f"C{index}"
    return f"C{chr(ord('A') + index - 10)}"


def cap_value(case_id: str, source_component: dict[str, Any], index: int) -> str:
    """Return a same-width visible capacitor value for topology diagnostics."""

    value = source_component.get("value", "")
    role = source_component.get("visual", {}).get("role", "")
    if case_id == "15_R_2R_LADDER_NETWORK":
        return "2uF" if "shunt" in role or "termination" in role else "1uF"
    if case_id == "12_BALANCED_WHEATSTONE_BRIDGE":
        return "1uF"
    if case_id == "13_UNBALANCED_WHEATSTONE_BRIDGE":
        mapping = {"R1": "1uF", "R2": "3uF", "R3": "2uF", "R4": "4uF", "R5": "1uF"}
        return mapping.get(source_component["ref"], "1uF")
    if case_id == "10_DELTA_TO_STAR_SETUP":
        return "3uF" if index <= 3 else "1uF"
    if value and value[0].isdigit() and value[0] != "0":
        digit = min(int(value[0]), 9)
        return f"{digit}uF"
    return "1uF"


def safe_positions(source: dict[str, Any]) -> dict[str, tuple[int, int]]:
    positions = source.get("layout", {}).get("component_positions", {})
    if not positions:
        return {
            component["ref"]: (BASE_X + (idx % 5) * SAFE_X_STEP, BASE_Y - (idx // 5) * SAFE_Y_STEP)
            for idx, component in enumerate(source["components"])
        }
    xs = sorted({pos["x"] for pos in positions.values()})
    ys = sorted({pos["y"] for pos in positions.values()}, reverse=True)
    x_map = {x: BASE_X + i * SAFE_X_STEP for i, x in enumerate(xs)}
    y_map = {y: BASE_Y - i * SAFE_Y_STEP for i, y in enumerate(ys)}
    used: dict[tuple[int, int], int] = {}
    out: dict[str, tuple[int, int]] = {}
    for idx, component in enumerate(source["components"]):
        raw = positions.get(component["ref"])
        if raw is None:
            x = BASE_X + (idx % 5) * SAFE_X_STEP
            y = BASE_Y - (idx // 5) * SAFE_Y_STEP
        else:
            x = x_map[raw["x"]]
            y = y_map[raw["y"]]
        duplicate_index = used.get((x, y), 0)
        used[(x, y)] = duplicate_index + 1
        if duplicate_index:
            x += duplicate_index * SAFE_X_STEP
        out[component["ref"]] = (x, y)
    return out


def convert_source_case(source_path: Path) -> tuple[str, dict[str, Any], list[v10.TerminalCapSpec]]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    case_id = source_path.parent.name
    positions = safe_positions(source)
    specs: list[v10.TerminalCapSpec] = []
    for index, component in enumerate(source["components"], start=1):
        x, y = positions[component["ref"]]
        left, right = component["nodes"]
        specs.append(v10.TerminalCapSpec(cap_ref(index), cap_value(case_id, component, index), left, right, x, y))
    return case_id, source, specs


def node_list(specs: list[v10.TerminalCapSpec]) -> list[str]:
    nodes: list[str] = []
    for spec in specs:
        nodes.extend([spec.left, spec.right])
    return list(dict.fromkeys(nodes))


def payload_for(case_id: str, source: dict[str, Any], specs: list[v10.TerminalCapSpec]) -> dict[str, Any]:
    return {
        "schema_version": "capacitor-network-temp/v12",
        "generator_target": "proteus-8.13-capacitor-v10-manual-terminal-order",
        "project": {
            "name": case_id,
            "output_basename": case_id,
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "source_resistor_case": source["project"]["output_basename"],
        "nodes": [{"id": node} for node in node_list(specs)],
        "components": [
            {
                "ref": spec.ref,
                "type": "CAPACITOR",
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y, "orientation_hint": "horizontal_v10_only"},
            }
            for spec in specs
        ],
        "metadata": {
            "source": "requested_resistor_networks_oriented_2026_05_30 converted R->C",
            "method": "V10 manual donor outputs-first terminal-capacitor order",
            "known_limitations": [
                "Uses terminal-label topology; no standalone bus/junction wires.",
                "V0 and G0 are ordinary terminal labels in this temp batch, not power/ground symbols.",
            ],
        },
    }


def write_case(
    *,
    case_id: str,
    source: dict[str, Any],
    specs: list[v10.TerminalCapSpec],
    base_project: Path,
    donor_project: Path,
    templates: v10.ManualCapTemplates,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, maps = v10.build_terminal_cap_chunk(templates, specs)
    cdb = v10.build_cap_cdb(specs)
    dsn, pointers = build_dsn(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    input_path = case_dir / "input.json"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    input_path.write_text(json.dumps(payload_for(case_id, source, specs), indent=2) + "\n", encoding="utf-8")

    issues = v10.validate_manual_order_chunk(object_chunk, len(specs))
    if _extract_object_chunk(dsn) != object_chunk:
        issues.append("rebuilt ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v12_requested15_not_locked",
        "description": source.get("project", {}).get("name", case_id) + " converted to capacitors",
        "source_resistor_case": source.get("project", {}).get("output_basename", case_id),
        "base_project": base_project.name,
        "donor_header_project": donor_project.name,
        "capacitor_count": len(specs),
        "node_count": len(node_list(specs)),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "object_chunk": {
                "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
                "$TERINPUT": object_chunk.count(b"$TERINPUT"),
                "CAPACITOR": object_chunk.count(b"CAPACITOR"),
                "CAP10": object_chunk.count(b"CAP10"),
                "WIRE": object_chunk.count(b"WIRE"),
                "1uF": object_chunk.count(b"1uF"),
                "2uF": object_chunk.count(b"2uF"),
                "3uF": object_chunk.count(b"3uF"),
                "4uF": object_chunk.count(b"4uF"),
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
                "1uF": cdb.count(b"1uF"),
                "2uF": cdb.count(b"2uF"),
                "3uF": cdb.count(b"3uF"),
                "4uF": cdb.count(b"4uF"),
            },
        },
        "section_pointer_values": pointers,
        "topology": maps,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: v10.sha256_file(output_path),
            cdb_path.name: v10.sha256_file(cdb_path),
            dsn_path.name: v10.sha256_file(dsn_path),
            "object_chunk": v10.sha256_bytes(object_chunk),
            "ROOT.CDB": v10.sha256_bytes(cdb),
        },
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, input_path.name, "manifest.json", "README_TEST_FIRST.txt"],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n"
        "Capacitor version of the matching requested resistor circuit.\n\n"
        f"Project: {output_path.name}\n"
        f"Capacitors: {len(specs)}\n"
        f"Static validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    base = registry.get("e001_empty").path
    manual = registry.get("cap2_with_terminals_manual").path
    templates = v10.load_manual_templates(manual)
    cases: list[dict[str, Any]] = []
    for source_path in sorted(SOURCE_ROOT.glob("*/input.json")):
        case_id, source, specs = convert_source_case(source_path)
        cases.append(write_case(case_id=case_id, source=source, specs=specs, base_project=base, donor_project=manual, templates=templates))

    summary = {
        "case": "CAPACITOR_V12_REQUESTED15_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "User accepted V11 6C/21C and requested the previous 15 resistor circuits generated with capacitors.",
        "method": "Convert the accepted oriented 15 resistor topology inputs to V10 manual-order capacitor records.",
        "manual_donor": {
            "fixture_id": "cap2_with_terminals_manual",
            "project_sha256": v10.sha256_file(manual),
            "object_order": "all outputs first, then input/cap/left-wire/right-wire groups; non-final right wires are 49 bytes",
        },
        "limitations": [
            "V0 and G0 are ordinary terminal labels, not power/ground symbols, in this temp batch.",
            "Capacitor records are horizontal because capacitor rotation is not yet separately validated.",
            "Standalone bus/junction wires are not emitted.",
        ],
        "test_order": [case["case_id"] for case in cases],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V12 requested 15 network diagnostics.\n\n"
        "Open in order:\n\n"
        + "\n".join(f"{idx:02d}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n\nReport the first failure, any exact Proteus error text, and whether the visible capacitor count matches each case.\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
