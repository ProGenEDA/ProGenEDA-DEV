"""Temporary capacitor V8 diagnostics: terminal object ordering.

V7 results from Proteus:
- T01, T02, T03, and T05 opened.
- T04 and T06 failed.
- T07 opened but displayed only a partial two-terminal-cap circuit.

V8 keeps capacitor work in the temporary lane and tests the hypothesis that
multiple terminal-attached capacitors need the accepted resistor V9 ordering:
all input terminals, all output terminals, one separator byte, then
component/wire groups.
"""

from __future__ import annotations

import hashlib
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

import generate_capacitor_v4_temp as v4
import generate_capacitor_v5_cap3_temp as v5
import generate_capacitor_v7_terminal_isolation_temp as v7
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "capacitor_v8_terminal_order_temp_2026_05_31"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def terminal_v9_order_chunk(groups: list[dict[str, bytes]]) -> bytes:
    chunk = bytearray(
        b"\x00"
        + b"".join(group["input"] for group in groups)
        + b"".join(group["output"] for group in groups)
        + b"\x00"
        + b"".join(
            part
            for group in groups
            for part in (group["cap"], group["wire_left"], group["wire_right"])
        )
    )
    chunk[-1] = 0xFF
    return bytes(chunk)


def write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk_bytes: bytes,
    cdb: bytes,
    validations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validations = validations or {}
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = build_dsn(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk_bytes,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)

    issues: list[str] = []
    if _extract_object_chunk(dsn) != object_chunk_bytes:
        issues.append("rebuilt ROOT.DSN object chunk differs from requested chunk")
    if object_chunk_bytes[0] != 0 or object_chunk_bytes[-1] != 0xFF:
        issues.append("object chunk start/final terminator invalid")
    issues.extend(validations.get("static_issues", []))

    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v8_terminal_order_not_locked",
        "description": description,
        "base_project": base_project.name,
        "donor_header_project": donor_project.name,
        "object_chunk_len": len(object_chunk_bytes),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "object_chunk": {
                "CAPACITOR": object_chunk_bytes.count(b"CAPACITOR"),
                "CAP10": object_chunk_bytes.count(b"CAP10"),
                "$TERINPUT": object_chunk_bytes.count(b"$TERINPUT"),
                "$TEROUTPUT": object_chunk_bytes.count(b"$TEROUTPUT"),
                "WIRE": object_chunk_bytes.count(b"WIRE"),
                "1uF": object_chunk_bytes.count(b"1uF"),
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
                "1uF": cdb.count(b"1uF"),
            },
        },
        "section_pointer_values": pointers,
        "validations": validations,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: sha256_file(output_path),
            cdb_path.name: sha256_file(cdb_path),
            dsn_path.name: sha256_file(dsn_path),
            "object_chunk": sha256_bytes(object_chunk_bytes),
            "ROOT.CDB": sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Project: {output_path.name}\n"
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
    t01 = registry.get("cap_t01_single_capacitor_1uf").path
    t02 = registry.get("cap_t02_capacitor_between_two_terminals").path
    cap3 = registry.get("cap3_three_capacitors").path
    templates = v4.load_templates(t02)
    free_template = v5.load_free_cap_core(t01)

    cases: list[dict[str, Any]] = []

    base_group = v7.terminal_group(
        templates,
        index=1,
        ref="C1",
        value="1uF",
        left="N1",
        right="N2",
        x=v4.CAP_BASE_X + 2540000,
        y=v4.CAP_BASE_Y - 2540000,
    )
    free_c2 = v7.free_record(free_template, "C2", "1uF", -4572000, -508000, 2)
    cases.append(
        write_case(
            case_id="CAP_V8_T01_V7_T05_REPRO_FREE_FIRST_TERMINAL_LAST",
            description="Reproduce the V7 T05 shape that the user reported as working: free C2 first, then terminal-attached C1.",
            base_project=base,
            donor_project=cap3,
            object_chunk_bytes=v7.object_chunk_record_last([free_c2] + v7.group_parts(base_group)),
            cdb=v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0)]),
        )
    )

    c1_res = v7.terminal_group(
        templates,
        index=1,
        ref="C1",
        value="1uF",
        left="N1",
        right="N2",
        x=v4.CAP_BASE_X,
        y=762000,
        suffix_family="resistor",
    )
    c2_res = v7.terminal_group(
        templates,
        index=2,
        ref="C2",
        value="1uF",
        left="N3",
        right="N4",
        x=-4572000,
        y=762000,
        suffix_family="resistor",
    )
    res_v9_order = terminal_v9_order_chunk([c1_res, c2_res])
    zero_flag_cdb = v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0)])
    donor_flag_cdb = v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0xFFFFFFFF)])
    cases.append(
        write_case(
            case_id="CAP_V8_T02_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_ZERO_FLAGS",
            description="Two terminal-attached capacitors using resistor/V9 suffix spacing, V9 terminal order, separator byte, and zero CDB flags.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=res_v9_order,
            cdb=zero_flag_cdb,
        )
    )
    cases.append(
        write_case(
            case_id="CAP_V8_T03_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_DONOR_FLAG",
            description="Same object bytes as T02, but C2 uses the cap3 donor FFFFFFFF component-table flag.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=res_v9_order,
            cdb=donor_flag_cdb,
        )
    )

    c1_cap = v7.terminal_group(
        templates,
        index=1,
        ref="C1",
        value="1uF",
        left="N1",
        right="N2",
        x=v4.CAP_BASE_X,
        y=762000,
        suffix_family="cap",
    )
    c2_cap = v7.terminal_group(
        templates,
        index=2,
        ref="C2",
        value="1uF",
        left="N3",
        right="N4",
        x=-4572000,
        y=762000,
        suffix_family="cap",
    )
    cap_v9_order = terminal_v9_order_chunk([c1_cap, c2_cap])
    cases.append(
        write_case(
            case_id="CAP_V8_T04_TWO_TERMINAL_CAP_SUFFIX_V9_ORDER_ZERO_FLAGS",
            description="Two terminal-attached capacitors using CAP_T02-style suffix spacing, V9 terminal order, separator byte, and zero CDB flags.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=cap_v9_order,
            cdb=zero_flag_cdb,
        )
    )
    cases.append(
        write_case(
            case_id="CAP_V8_T05_TWO_TERMINAL_CAP_SUFFIX_V9_ORDER_DONOR_FLAG",
            description="Same object bytes as T04, but C2 uses the cap3 donor FFFFFFFF component-table flag.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=cap_v9_order,
            cdb=donor_flag_cdb,
        )
    )

    c1_res_stagger = v7.terminal_group(
        templates,
        index=1,
        ref="C1",
        value="1uF",
        left="N1",
        right="N2",
        x=v4.CAP_BASE_X,
        y=762000,
        suffix_family="resistor",
    )
    c2_res_stagger = v7.terminal_group(
        templates,
        index=2,
        ref="C2",
        value="1uF",
        left="N3",
        right="N4",
        x=v4.CAP_BASE_X,
        y=-1780000,
        suffix_family="resistor",
    )
    cases.append(
        write_case(
            case_id="CAP_V8_T06_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_VERTICAL_STAGGER",
            description="Same method as T02 with C2 placed on a separate row to isolate visual overlap from object ordering.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=terminal_v9_order_chunk([c1_res_stagger, c2_res_stagger]),
            cdb=zero_flag_cdb,
        )
    )

    summary = {
        "case": "CAPACITOR_V8_TERMINAL_ORDER_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "V7 user feedback: T04 and T06 failed; T07 opened but showed only a partial two-terminal-cap circuit; T01/T02/T03/T05 worked.",
        "hypothesis": "Multiple terminal-attached capacitors need resistor V9 object order: input terminal array, output terminal array, separator byte, component/wire groups.",
        "test_order": [case["case_id"] for case in cases],
        "decision_rule": [
            "T01 is the known-working V7 T05 repro guard.",
            "If T02 displays two capacitors correctly, V9 ordering plus zero CDB flags is the candidate terminal-cap method.",
            "If T02 fails but T03 works, the C2 CDB FFFFFFFF flag matters for terminal caps.",
            "If T02/T03 fail but T04/T05 work, CAP_T02 suffix spacing is required.",
            "If T06 works while T02 is visually wrong, placement/staggering is required even with V9 ordering.",
        ],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V8 terminal order diagnostics.\n\n"
        "Open in order. T01 should reproduce a case you already saw working. For T02-T06, report whether the file opens and whether it shows two capacitors with N1/N2 and N3/N4 terminals.\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
