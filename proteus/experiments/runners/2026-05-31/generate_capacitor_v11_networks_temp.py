"""Temporary capacitor V11 network diagnostics.

User accepted every V10 manual-donor case. V11 scales that accepted record shape
to the two older resistor topology stress cases:

* 6C: capacitor version of the corrected hand-drawn 6R topology.
* 21C: capacitor version of the R21 7+7+7 topology.

This stays temporary until Proteus confirms the larger generated networks.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
TOOL_DIR_2026_05_30 = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-05-30"
TOOL_DIR_2026_05_31 = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-05-31"
for path in (REPO_ROOT / "proteus" / "active" / "src", TOOL_DIR_2026_05_30, TOOL_DIR_2026_05_31):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_capacitor_v10_manual_donor_temp as v10
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "capacitor_v11_networks_temp_2026_05_31"
SAFE_X_STEP = 2540000


def cap_ref(index: int) -> str:
    if index <= 9:
        return f"C{index}"
    return f"C{chr(ord('A') + index - 10)}"


def specs_6c() -> list[v10.TerminalCapSpec]:
    topology = [
        ("N0", "N1"),
        ("N1", "N2"),
        ("N0", "N2"),
        ("N2", "N3"),
        ("N3", "N4"),
        ("N0", "N4"),
    ]
    positions = [
        (-6858000, 5080000),
        (-4318000, 5080000),
        (-1778000, 5080000),
        (-6858000, 2540000),
        (-4318000, 2540000),
        (-1778000, 2540000),
    ]
    return [
        v10.TerminalCapSpec(cap_ref(index), "1uF", left, right, x, y)
        for index, ((left, right), (x, y)) in enumerate(zip(topology, positions), 1)
    ]


def specs_21c() -> list[v10.TerminalCapSpec]:
    specs: list[v10.TerminalCapSpec] = []
    x0 = -6858000
    rows = [
        ("branch_a", 5080000, ["N0", "A1", "A2", "A3", "A4", "A5", "A6", "M0"]),
        ("branch_b", 2540000, ["N0", "B1", "B2", "B3", "B4", "B5", "B6", "M0"]),
        ("tail", 0, ["M0", "T1", "T2", "T3", "T4", "T5", "T6", "Z0"]),
    ]
    index = 1
    for _name, y, nodes in rows:
        for col, (left, right) in enumerate(zip(nodes, nodes[1:])):
            specs.append(v10.TerminalCapSpec(cap_ref(index), "1uF", left, right, x0 + col * SAFE_X_STEP, y))
            index += 1
    return specs


def node_list(specs: list[v10.TerminalCapSpec]) -> list[str]:
    nodes: list[str] = []
    for spec in specs:
        nodes.extend([spec.left, spec.right])
    return list(dict.fromkeys(nodes))


def topology_payload(case_id: str, specs: list[v10.TerminalCapSpec], source: str) -> dict[str, Any]:
    return {
        "schema_version": "capacitor-network-temp/v11",
        "generator_target": "proteus-8.13-capacitor-v10-manual-terminal-order",
        "project": {
            "name": case_id,
            "output_basename": case_id,
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
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
            "source": source,
            "method": "V10 manual donor outputs-first terminal-capacitor order",
            "known_limitations": [
                "Uses terminal-label topology; does not add standalone bus/junction wires.",
                "Uses normal input/output terminal labels only; power/ground terminal symbols are not introduced in this V11 stress test.",
            ],
        },
    }


def write_case(
    *,
    case_id: str,
    description: str,
    source: str,
    base_project: Path,
    donor_project: Path,
    templates: v10.ManualCapTemplates,
    specs: list[v10.TerminalCapSpec],
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
    input_path.write_text(json.dumps(topology_payload(case_id, specs, source), indent=2) + "\n", encoding="utf-8")

    issues = v10.validate_manual_order_chunk(object_chunk, len(specs))
    if _extract_object_chunk(dsn) != object_chunk:
        issues.append("rebuilt ROOT.DSN object chunk differs from requested chunk")

    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v11_network_not_locked",
        "description": description,
        "source": source,
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
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
                "1uF": cdb.count(b"1uF"),
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
        f"{description}\n\n"
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
    cases = [
        write_case(
            case_id="CAP_V11_T01_6C_SAME_TOPOLOGY_AS_6R",
            description="Six-capacitor version of the corrected hand-drawn 6R topology.",
            source="memory final/examples/handdrawn_6r_corrected.json topology, converted R->C",
            base_project=base,
            donor_project=manual,
            templates=templates,
            specs=specs_6c(),
        ),
        write_case(
            case_id="CAP_V11_T02_21C_SAME_TOPOLOGY_AS_R21",
            description="Twenty-one-capacitor version of the R21 7+7+7 topology.",
            source="memory capacitor_network_attempts_2026-05-29 R21 topology, regenerated with V10 manual donor order",
            base_project=base,
            donor_project=manual,
            templates=templates,
            specs=specs_21c(),
        ),
    ]

    summary = {
        "case": "CAPACITOR_V11_NETWORKS_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "User accepted all V10 manual-donor cases and requested the old 21R and 6R circuits with capacitors.",
        "method": "Scale V10 manual donor output-array then input/cap/wire groups to 6 and 21 terminal-attached capacitors.",
        "manual_donor": {
            "fixture_id": "cap2_with_terminals_manual",
            "project_sha256": v10.sha256_file(manual),
            "object_order": "all outputs first, then input/cap/left-wire/right-wire groups; non-final right wires are 49 bytes",
        },
        "test_order": [case["case_id"] for case in cases],
        "decision_rule": [
            "T01 checks whether the accepted V10 method scales from 3 to 6 capacitors.",
            "T02 checks whether the same method scales to the 21-component R21 topology.",
            "If both open and render all capacitors, capacitor generation can be promoted from temporary toward main.",
        ],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V11 network diagnostics.\n\n"
        "Open in order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n\nReport whether each opens, whether all capacitors are visible, and any exact Proteus error text.\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
