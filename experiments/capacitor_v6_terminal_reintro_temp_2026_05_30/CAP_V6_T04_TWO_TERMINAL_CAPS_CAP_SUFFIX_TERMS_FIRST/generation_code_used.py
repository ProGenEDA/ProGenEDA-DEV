"""Temporary capacitor V6 diagnostics: reintroduce terminals after cap3 success.

V5 confirmed multi-cap CDB/free visual records. V6 tests terminal-attached
capacitor topology cautiously, without promoting anything into main code.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR = Path(__file__).resolve().parent
for path in (REPO_ROOT / "src", TOOL_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_capacitor_v4_temp as v4
import generate_capacitor_v5_cap3_temp as v5
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "capacitor_v6_terminal_reintro_temp_2026_05_30"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def suffixes(index: int, family: str) -> tuple[int, int]:
    if family == "cap_step40":
        return 0x00B2 + (index - 1) * 0x40, 0x0080 + (index - 1) * 0x40
    if family == "resistor_step":
        return 0x0159 + (index - 1) * 0x01BE, 0x018B + (index - 1) * 0x01BE
    if family == "duplicate_donor":
        return 0x00B2, 0x0080
    raise ValueError(f"Unknown suffix family {family!r}.")


def terminal_records(
    templates: v4.CapTemplates,
    *,
    index: int,
    ref: str,
    value: str,
    left: str,
    right: str,
    x: int,
    y: int,
    family: str,
) -> dict[str, bytes]:
    dx = x - v4.CAP_BASE_X
    dy = y - v4.CAP_BASE_Y
    in_suffix, out_suffix = suffixes(index, family)
    return {
        "input": v4.patch_input(templates.input_terminal, left, dx, dy, in_suffix),
        "output": v4.patch_output(templates.output_terminal, right, dx, dy, out_suffix),
        "cap": v4.patch_cap(templates.cap_record, ref, value, dx, dy, in_suffix, out_suffix, final=False),
        "wire_left": v4.patch_wire(templates.wire_left, dx, dy, final=False),
        "wire_right": v4.patch_wire(templates.wire_right, dx, dy, final=False),
    }


def free_core(template: bytes, cap: v5.FreeCap, index: int) -> bytes:
    return v5.patch_free_cap_core(template, cap, index)


def object_chunk(parts: list[bytes]) -> bytes:
    chunk = bytearray(b"\x00" + b"".join(parts) + b"\xff")
    return bytes(chunk)


def write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk_bytes: bytes,
    cdb: bytes,
    validations: dict[str, Any],
) -> dict[str, Any]:
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

    static_issues = []
    if _extract_object_chunk(dsn) != object_chunk_bytes:
        static_issues.append("rebuilt ROOT.DSN object chunk differs from requested chunk")
    if object_chunk_bytes[0] != 0 or object_chunk_bytes[-1] != 0xFF:
        static_issues.append("object chunk start/final terminator invalid")
    static_issues.extend(validations.get("static_issues", []))

    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v6_terminal_reintro_not_locked",
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
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
            },
        },
        "section_pointer_values": pointers,
        "validations": validations,
        "static_validation_issues": static_issues,
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
        f"Static validation issues: {static_issues}\n",
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
    terminal_templates = v4.load_templates(t02)
    free_template = v5.load_free_cap_core(t01)

    cases: list[dict[str, Any]] = []

    c1 = terminal_records(
        terminal_templates, index=1, ref="C1", value="1nF", left="N1", right="N2", x=v4.CAP_BASE_X, y=v4.CAP_BASE_Y, family="cap_step40"
    )
    parts = [c1["input"], c1["output"], c1["cap"], c1["wire_left"], c1["wire_right"], free_core(free_template, v5.FreeCap("C2", "1nF", -4572000, -508000), 2)]
    cdb_caps = [v5.FreeCap("C1", "1nF", v4.CAP_BASE_X, v4.CAP_BASE_Y), v5.FreeCap("C2", "1nF", -4572000, -508000)]
    cases.append(
        write_case(
            case_id="CAP_V6_T01_ONE_TERMINAL_CAP_PLUS_FREE_CAP",
            description="One terminal-attached capacitor plus one free capacitor; tests safe coexistence before duplicated terminal groups.",
            base_project=base,
            donor_project=t02,
            object_chunk_bytes=object_chunk(parts),
            cdb=v5.build_cap_cdb(cdb_caps),
            validations={"static_issues": []},
        )
    )

    c2 = free_core(free_template, v5.FreeCap("C2", "1nF", -4572000, -508000), 2)
    c3 = free_core(free_template, v5.FreeCap("C3", "1nF", -2032000, -508000), 3)
    cdb_caps3 = [
        v5.FreeCap("C1", "1nF", v4.CAP_BASE_X, v4.CAP_BASE_Y),
        v5.FreeCap("C2", "1nF", -4572000, -508000, 0xFFFFFFFF),
        v5.FreeCap("C3", "1nF", -2032000, -508000),
    ]
    cases.append(
        write_case(
            case_id="CAP_V6_T02_ONE_TERMINAL_CAP_PLUS_TWO_FREE_CAPS",
            description="One terminal-attached capacitor plus two free capacitors using the cap3 middle-component flag.",
            base_project=base,
            donor_project=cap3,
            object_chunk_bytes=object_chunk([c1["input"], c1["output"], c1["cap"], c1["wire_left"], c1["wire_right"], c2, c3]),
            cdb=v5.build_cap_cdb(cdb_caps3),
            validations={"static_issues": []},
        )
    )

    def two_terminal_case(family: str, order: str) -> tuple[bytes, bytes]:
        a = terminal_records(
            terminal_templates, index=1, ref="C1", value="1nF", left="N1", right="N2", x=v4.CAP_BASE_X, y=762000, family=family
        )
        b = terminal_records(
            terminal_templates, index=2, ref="C2", value="1nF", left="N3", right="N4", x=-4572000, y=762000, family=family
        )
        if order == "sequential":
            parts2 = [a["input"], a["output"], a["cap"], a["wire_left"], a["wire_right"], b["input"], b["output"], b["cap"], b["wire_left"], b["wire_right"]]
        elif order == "terms_first":
            parts2 = [a["input"], b["input"], a["output"], b["output"], a["cap"], b["cap"], a["wire_left"], a["wire_right"], b["wire_left"], b["wire_right"]]
        elif order == "caps_first":
            parts2 = [a["cap"], b["cap"], a["input"], a["output"], a["wire_left"], a["wire_right"], b["input"], b["output"], b["wire_left"], b["wire_right"]]
        else:
            raise ValueError(order)
        cdb2 = v5.build_cap_cdb([v5.FreeCap("C1", "1nF", v4.CAP_BASE_X, 762000), v5.FreeCap("C2", "1nF", -4572000, 762000, 0xFFFFFFFF)])
        return object_chunk(parts2), cdb2

    for case_id, description, family, order in [
        (
            "CAP_V6_T03_TWO_TERMINAL_CAPS_RES_SUFFIX_SEQUENTIAL",
            "Two terminal-attached capacitors in T02 sequential order but using the resistor-style proven suffix spacing.",
            "resistor_step",
            "sequential",
        ),
        (
            "CAP_V6_T04_TWO_TERMINAL_CAPS_CAP_SUFFIX_TERMS_FIRST",
            "Two terminal-attached capacitors with all terminals before capacitor/wire records, using CAP_T02 suffix family.",
            "cap_step40",
            "terms_first",
        ),
        (
            "CAP_V6_T05_TWO_TERMINAL_CAPS_RES_SUFFIX_TERMS_FIRST",
            "Two terminal-attached capacitors with all terminals before capacitor/wire records, using resistor-style suffix spacing.",
            "resistor_step",
            "terms_first",
        ),
        (
            "CAP_V6_T06_TWO_TERMINAL_CAPS_RES_SUFFIX_CAPS_FIRST",
            "Two terminal-attached capacitors with capacitor records before endpoint terminals and wires, using resistor-style suffix spacing.",
            "resistor_step",
            "caps_first",
        ),
    ]:
        chunk, cdb = two_terminal_case(family, order)
        cases.append(
            write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_project=t02,
                object_chunk_bytes=chunk,
                cdb=cdb,
                validations={"suffix_family": family, "object_order": order, "static_issues": []},
            )
        )

    summary = {
        "case": "CAPACITOR_V6_TERMINAL_REINTRO_TEMP_2026_05_30",
        "status": "temporary_diagnostic_not_locked",
        "method": "Start from V5 cap3 free-cap success and reintroduce terminals in controlled variants. V4 T05 sequential CAP_T02-style duplication remains negative evidence.",
        "test_order": [case["case_id"] for case in cases],
        "paired_notes": [
            "If T01/T02 fail, stop terminal reintroduction and inspect coexistence of free and terminal-attached cap records.",
            "T03-T06 are variants for two terminal-attached capacitors; report every one that opens or errors.",
        ],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V6 terminal reintroduction diagnostics.\n\n"
        "Open in order. If T01/T02 fail, stop and report. For T03-T06, report each case that opens or errors.\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, start=1))
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
