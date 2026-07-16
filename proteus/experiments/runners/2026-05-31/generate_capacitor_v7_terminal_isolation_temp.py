"""Temporary capacitor V7 diagnostics: isolate why V6 terminal reintro failed.

Known results:
- V4 T04: one translated terminal-attached capacitor opened.
- V4 T05: two duplicated terminal-attached capacitor groups failed.
- V5: free multi-cap CDB/object generation worked.
- V6: every terminal reintroduction case failed.

V7 changes one variable at a time around the known-good V4 single terminal
capacitor before trying terminal/free or two-terminal-cap combinations again.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
PREV_TOOL_DIR = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-05-30"
for path in (REPO_ROOT / "proteus" / "active" / "src", PREV_TOOL_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_capacitor_v4_temp as v4
import generate_capacitor_v5_cap3_temp as v5
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "capacitor_v7_terminal_isolation_temp_2026_05_31"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def object_chunk_free_last(parts: list[bytes]) -> bytes:
    """Build a chunk whose final object is a free capacitor core.

    Free capacitor records use an extra stream-level final FF byte after the
    final 365-byte core, matching cap3.
    """

    return b"\x00" + b"".join(parts) + b"\xff"


def object_chunk_record_last(parts: list[bytes]) -> bytes:
    """Build a chunk whose final object already has a terminator byte.

    Terminal-capacitor groups end in a wire record, and the final FF replaces
    that wire record's final byte. Appending an extra FF makes a bad object
    stream and was the V6 bug for terminal-last variants.
    """

    chunk = bytearray(b"\x00" + b"".join(parts))
    chunk[-1] = 0xFF
    return bytes(chunk)


def cap_step_suffixes(index: int) -> tuple[int, int]:
    return 0x00B2 + (index - 1) * 0x40, 0x0080 + (index - 1) * 0x40


def resistor_suffixes(index: int) -> tuple[int, int]:
    return 0x0159 + (index - 1) * 0x01BE, 0x018B + (index - 1) * 0x01BE


def terminal_group(
    templates: v4.CapTemplates,
    *,
    index: int,
    ref: str,
    value: str,
    left: str,
    right: str,
    x: int,
    y: int,
    suffix_family: str = "cap",
) -> dict[str, bytes]:
    dx = x - v4.CAP_BASE_X
    dy = y - v4.CAP_BASE_Y
    if suffix_family == "cap":
        in_suffix, out_suffix = cap_step_suffixes(index)
    elif suffix_family == "resistor":
        in_suffix, out_suffix = resistor_suffixes(index)
    else:
        raise ValueError(suffix_family)
    return {
        "input": v4.patch_input(templates.input_terminal, left, dx, dy, in_suffix),
        "output": v4.patch_output(templates.output_terminal, right, dx, dy, out_suffix),
        "cap": v4.patch_cap(templates.cap_record, ref, value, dx, dy, in_suffix, out_suffix, final=False),
        "wire_left": v4.patch_wire(templates.wire_left, dx, dy, final=False),
        "wire_right": v4.patch_wire(templates.wire_right, dx, dy, final=False),
    }


def group_parts(group: dict[str, bytes]) -> list[bytes]:
    return [group["input"], group["output"], group["cap"], group["wire_left"], group["wire_right"]]


def free_record(template: bytes, ref: str, value: str, x: int, y: int, index: int) -> bytes:
    return v5.patch_free_cap_core(template, v5.FreeCap(ref, value, x, y), index)


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
        "status": "temporary_capacitor_v7_terminal_isolation_not_locked",
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
                "1nF": object_chunk_bytes.count(b"1nF"),
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
                "1uF": cdb.count(b"1uF"),
                "1nF": cdb.count(b"1nF"),
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
    donor_t02_cdb = read_internal_file(t02, "ROOT.CDB")

    cases: list[dict[str, Any]] = []

    base_group = terminal_group(
        templates, index=1, ref="C1", value="1uF", left="N1", right="N2", x=v4.CAP_BASE_X + 2540000, y=v4.CAP_BASE_Y - 2540000
    )
    cases.append(
        write_case(
            case_id="CAP_V7_T01_V4_T04_REPRO_SANITY",
            description="Rebuild the known-opening V4 T04 shape: one translated terminal-attached C1 1uF.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=object_chunk_record_last(group_parts(base_group)),
            cdb=donor_t02_cdb,
            validations={"expected_relation": "Should match the V4 T04 generated method."},
        )
    )

    single_1nf = terminal_group(
        templates, index=1, ref="C1", value="1nF", left="N1", right="N2", x=v4.CAP_BASE_X + 2540000, y=v4.CAP_BASE_Y - 2540000
    )
    cases.append(
        write_case(
            case_id="CAP_V7_T02_SINGLE_TERMINAL_CAP_1NF",
            description="Only change V4 T04 from 1uF to 1nF with a matching one-cap CDB.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=object_chunk_record_last(group_parts(single_1nf)),
            cdb=v5.build_cap_cdb([v5.FreeCap("C1", "1nF", 0, 0)]),
        )
    )

    cases.append(
        write_case(
            case_id="CAP_V7_T03_SINGLE_TERMINAL_CAP_PLUS_EXTRA_CDB_ONLY",
            description="Known-opening C1 1uF terminal group plus an extra C2 CDB record, no C2 visual object.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=object_chunk_record_last(group_parts(base_group)),
            cdb=v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0)]),
        )
    )

    free_c2_1uf = free_record(free_template, "C2", "1uF", -4572000, -508000, 2)
    cases.append(
        write_case(
            case_id="CAP_V7_T04_SINGLE_TERMINAL_CAP_PLUS_FREE_1UF",
            description="Known-opening C1 1uF terminal group plus one free C2 1uF visual record.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=object_chunk_free_last(group_parts(base_group) + [free_c2_1uf]),
            cdb=v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0)]),
        )
    )

    free_first = [free_c2_1uf] + group_parts(base_group)
    cases.append(
        write_case(
            case_id="CAP_V7_T05_FREE_1UF_BEFORE_SINGLE_TERMINAL_CAP",
            description="Same objects as T04, but free C2 appears before terminal-attached C1 in OBJECT DATA.",
            base_project=base,
            donor_project=cap3,
            object_chunk_bytes=object_chunk_record_last(free_first),
            cdb=v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0)]),
        )
    )

    c1_term = terminal_group(templates, index=1, ref="C1", value="1uF", left="N1", right="N2", x=v4.CAP_BASE_X, y=762000)
    c2_term = terminal_group(templates, index=2, ref="C2", value="1uF", left="N3", right="N4", x=-4572000, y=762000)
    cases.append(
        write_case(
            case_id="CAP_V7_T06_TWO_TERMINAL_CAPS_1UF_CAP_SUFFIX",
            description="Two terminal-attached capacitors using 1uF and CAP_T02 suffix family.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=object_chunk_record_last(group_parts(c1_term) + group_parts(c2_term)),
            cdb=v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0xFFFFFFFF)]),
        )
    )

    c1_res = terminal_group(templates, index=1, ref="C1", value="1uF", left="N1", right="N2", x=v4.CAP_BASE_X, y=762000, suffix_family="resistor")
    c2_res = terminal_group(templates, index=2, ref="C2", value="1uF", left="N3", right="N4", x=-4572000, y=762000, suffix_family="resistor")
    terms_first = [c1_res["input"], c2_res["input"], c1_res["output"], c2_res["output"], c1_res["cap"], c2_res["cap"], c1_res["wire_left"], c1_res["wire_right"], c2_res["wire_left"], c2_res["wire_right"]]
    cases.append(
        write_case(
            case_id="CAP_V7_T07_TWO_TERMINAL_CAPS_1UF_RES_SUFFIX_TERMS_FIRST",
            description="Two terminal-attached capacitors using 1uF, resistor suffix family, and terminals-first order.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=object_chunk_record_last(terms_first),
            cdb=v5.build_cap_cdb([v5.FreeCap("C1", "1uF", 0, 0), v5.FreeCap("C2", "1uF", 0, 0xFFFFFFFF)]),
        )
    )

    summary = {
        "case": "CAPACITOR_V7_TERMINAL_ISOLATION_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "method": "One-variable isolation around the known-opening V4 T04 single terminal-cap case after every V6 case failed.",
        "test_order": [case["case_id"] for case in cases],
        "decision_rule": [
            "If T01 fails, the V4 T04 opening report was not reproducible and we must return to exact T02/T04 baseline.",
            "If T01 works but T02 fails, 1nF value mutation breaks terminal-attached capacitor records.",
            "If T03 fails, extra CDB-only capacitor records break terminal-attached cap projects.",
            "If T04/T05 fail, mixing free and terminal-attached capacitor visual records is unsafe.",
            "If T06/T07 fail, multiple terminal-attached caps require a real multi-terminal-cap donor.",
        ],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V7 terminal isolation diagnostics.\n\n"
        "Open in order and stop at the first failure through T05. If T06 fails, still test T07.\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
