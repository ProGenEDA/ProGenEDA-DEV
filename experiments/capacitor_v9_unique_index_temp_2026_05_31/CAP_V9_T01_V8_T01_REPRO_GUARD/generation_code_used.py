"""Temporary capacitor V9 diagnostics: unique capacitor visual indexes.

V8 rejected the V9-order hypothesis by itself: only the known free-before-
terminal guard opened. A deeper byte audit then found a concrete bug in every
duplicated terminal-attached capacitor attempt: the capacitor visual record's
hidden instance/index byte at offset 344 remained copied from the one-cap donor
as `01` for every terminal-attached capacitor.

Free multi-cap generation already patches that byte to 1, 2, 3 and is user-
accepted. V9 tests the minimal equivalent fix for terminal-attached capacitors.
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
import generate_capacitor_v8_terminal_order_temp as v8
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "capacitor_v9_unique_index_temp_2026_05_31"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def unique_cap_index(group: dict[str, bytes], index: int) -> dict[str, bytes]:
    if not 1 <= index <= 255:
        raise ValueError("Capacitor visual index must fit in one byte.")
    cap = bytearray(group["cap"])
    cap[344] = index
    updated = dict(group)
    updated["cap"] = bytes(cap)
    return updated


def cap_indexes(groups: list[dict[str, bytes]]) -> list[int]:
    return [group["cap"][344] for group in groups]


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
        "status": "temporary_capacitor_v9_unique_index_not_locked",
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

    cdb2 = v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0)])
    cdb3 = v5.build_cap_cdb(
        [v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0), v5.FreeCap("C3", "1uF", 0, 0)]
    )
    cases: list[dict[str, Any]] = []

    guard_group = unique_cap_index(
        v7.terminal_group(
            templates,
            index=1,
            ref="C1",
            value="1uF",
            left="N1",
            right="N2",
            x=v4.CAP_BASE_X + 2540000,
            y=v4.CAP_BASE_Y - 2540000,
        ),
        1,
    )
    free_c2 = v7.free_record(free_template, "C2", "1uF", -4572000, -508000, 2)
    cases.append(
        write_case(
            case_id="CAP_V9_T01_V8_T01_REPRO_GUARD",
            description="Reproduce the user-working V8 T01 guard: free C2 first, then terminal-attached C1.",
            base_project=base,
            donor_project=cap3,
            object_chunk_bytes=v7.object_chunk_record_last([free_c2] + v7.group_parts(guard_group)),
            cdb=cdb2,
            validations={"cap_visual_indexes": [2, guard_group["cap"][344]]},
        )
    )

    c1_cap = unique_cap_index(
        v7.terminal_group(
            templates,
            index=1,
            ref="C1",
            value="1uF",
            left="N1",
            right="N2",
            x=v4.CAP_BASE_X,
            y=762000,
            suffix_family="cap",
        ),
        1,
    )
    c2_cap = unique_cap_index(
        v7.terminal_group(
            templates,
            index=2,
            ref="C2",
            value="1uF",
            left="N3",
            right="N4",
            x=-4572000,
            y=762000,
            suffix_family="cap",
        ),
        2,
    )
    cases.append(
        write_case(
            case_id="CAP_V9_T02_TWO_TERMINAL_CAP_SUFFIX_SEQ_UNIQUE_INDEX",
            description="V7 T06 minimal fix: two sequential terminal-cap groups with unique capacitor visual indexes 1 and 2.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=v7.object_chunk_record_last(v7.group_parts(c1_cap) + v7.group_parts(c2_cap)),
            cdb=cdb2,
            validations={"cap_visual_indexes": cap_indexes([c1_cap, c2_cap])},
        )
    )

    c1_res = unique_cap_index(
        v7.terminal_group(
            templates,
            index=1,
            ref="C1",
            value="1uF",
            left="N1",
            right="N2",
            x=v4.CAP_BASE_X,
            y=762000,
            suffix_family="resistor",
        ),
        1,
    )
    c2_res = unique_cap_index(
        v7.terminal_group(
            templates,
            index=2,
            ref="C2",
            value="1uF",
            left="N3",
            right="N4",
            x=-4572000,
            y=762000,
            suffix_family="resistor",
        ),
        2,
    )
    terms_first = [
        c1_res["input"],
        c2_res["input"],
        c1_res["output"],
        c2_res["output"],
        c1_res["cap"],
        c2_res["cap"],
        c1_res["wire_left"],
        c1_res["wire_right"],
        c2_res["wire_left"],
        c2_res["wire_right"],
    ]
    cases.append(
        write_case(
            case_id="CAP_V9_T03_TWO_TERMINAL_RES_SUFFIX_TERMS_FIRST_UNIQUE_INDEX",
            description="V7 T07 minimal fix: terms-first order with unique capacitor visual indexes 1 and 2.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=v7.object_chunk_record_last(terms_first),
            cdb=cdb2,
            validations={"cap_visual_indexes": cap_indexes([c1_res, c2_res])},
        )
    )

    cases.append(
        write_case(
            case_id="CAP_V9_T04_TWO_TERMINAL_RES_SUFFIX_V9_ORDER_UNIQUE_INDEX",
            description="V8 T02 minimal fix: V9 object order plus unique capacitor visual indexes 1 and 2.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=v8.terminal_v9_order_chunk([c1_res, c2_res]),
            cdb=cdb2,
            validations={"cap_visual_indexes": cap_indexes([c1_res, c2_res])},
        )
    )

    c3_cap = unique_cap_index(
        v7.terminal_group(
            templates,
            index=3,
            ref="C3",
            value="1uF",
            left="N5",
            right="N6",
            x=-2032000,
            y=-1780000,
            suffix_family="cap",
        ),
        3,
    )
    cases.append(
        write_case(
            case_id="CAP_V9_T05_THREE_TERMINAL_CAP_SUFFIX_SEQ_UNIQUE_INDEX",
            description="Scale test after T02: three sequential terminal-cap groups with unique visual indexes 1, 2, and 3.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=v7.object_chunk_record_last(v7.group_parts(c1_cap) + v7.group_parts(c2_cap) + v7.group_parts(c3_cap)),
            cdb=cdb3,
            validations={"cap_visual_indexes": cap_indexes([c1_cap, c2_cap, c3_cap])},
        )
    )

    summary = {
        "case": "CAPACITOR_V9_UNIQUE_INDEX_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "V8 user feedback: only T01 worked. Deep byte audit found duplicated terminal-attached cap visual index byte 344.",
        "hypothesis": "Terminal-attached multi-cap generation failed because every duplicated cap visual record kept hidden visual index 1; free multi-cap generation works because it patches this byte to 1, 2, 3.",
        "test_order": [case["case_id"] for case in cases],
        "decision_rule": [
            "T01 should reproduce the already-working guard.",
            "If T02 works, byte344 unique visual index was the missing minimal fix for sequential terminal-cap groups.",
            "If T02 fails but T03 or T04 works, unique index was necessary but object order still matters.",
            "If T02-T04 all fail, request a real Proteus-made two-terminal-cap donor.",
            "Test T05 only if T02 works, to check scaling beyond two terminal-attached capacitors.",
        ],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V9 unique-index diagnostics.\n\n"
        "Open in order. T01 should reproduce a working guard. If T02 works, still test T05. If T02 fails, test T03 and T04. T05 is only useful after T02 works.\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
