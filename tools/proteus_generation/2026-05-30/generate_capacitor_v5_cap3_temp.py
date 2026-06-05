"""Temporary capacitor V5 diagnostics based on user-supplied cap3.pdsprj.

V4 proved that one patched/translated capacitor can open, while duplicated
terminal-cap-terminal groups still fail. V5 therefore isolates multi-capacitor
component/CDB generation without terminal endpoint groups.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _i32, _u32, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "capacitor_v5_cap3_temp_2026_05_30"

FREE_CAP_CORE_SIZE = 365
CAP_PROP_TEXT = b"{PRIMITIVE=ANALOGUE,CAPACITOR}\n\n{PACKAGE=CAP10}\n\n\x00"


@dataclass(frozen=True)
class FreeCap:
    ref: str
    value: str
    x: int
    y: int
    cdb_flag: int = 0


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def s32(data: bytes, offset: int) -> int:
    return struct.unpack("<i", data[offset : offset + 4])[0]


def load_free_cap_core(t01_project: Path) -> bytes:
    chunk = _extract_object_chunk(read_internal_file(t01_project, "ROOT.DSN"))
    core = chunk[1:-1]
    if len(core) != FREE_CAP_CORE_SIZE:
        raise RuntimeError(f"CAP_T01 free capacitor core length {len(core)} != {FREE_CAP_CORE_SIZE}.")
    if core.count(b"CAPACITOR") != 1 or core.count(b"CAP10") != 1:
        raise RuntimeError("CAP_T01 free capacitor core does not contain the expected markers.")
    return core


def patch_free_cap_core(template: bytes, cap: FreeCap, index: int) -> bytes:
    if len(cap.ref) != 2 or not cap.ref.isascii():
        raise ValueError("V5 temp capacitor refs must be exactly two ASCII characters.")
    if len(cap.value) != 3 or not cap.value.isascii():
        raise ValueError("V5 temp capacitor visible values must be exactly three ASCII characters.")
    record = bytearray(template)
    base_x = s32(template, 332)
    base_y = s32(template, 336)
    dx = cap.x - base_x
    dy = cap.y - base_y

    record[2] = 2
    record[3:5] = cap.ref.encode("ascii")
    record[70] = 3
    record[71:74] = cap.value.encode("ascii")
    for offset in (5, 74, 146, 260, 332):
        record[offset : offset + 4] = _i32(s32(template, offset) + dx)
    for offset in (9, 78, 150, 264, 336):
        record[offset : offset + 4] = _i32(s32(template, offset) + dy)
    if not 0 <= index <= 255:
        raise ValueError("V5 temp free-cap visual index must fit in one byte.")
    record[344] = index
    return bytes(record)


def build_free_cap_chunk(template: bytes, caps: list[FreeCap]) -> bytes:
    return b"\x00" + b"".join(patch_free_cap_core(template, cap, index) for index, cap in enumerate(caps, 1)) + b"\xff"


def build_cap_cdb(caps: list[FreeCap]) -> bytes:
    out = bytearray()
    count = len(caps)
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + enc_str("Master Sheet") + _u32(10) + _u32(0)
    out += _u32(count)
    for index, cap in enumerate(caps, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(index) + enc_str(cap.ref)
        out += _u32(2) + enc_str("2") + enc_str("2") + enc_str("1") + enc_str("1")
        out += _u32(0) + _u32(index) + _u32(cap.cdb_flag)
    out += _u32(1) + _u32(1) + b"\x00" + enc_str("") + _u32(1)
    out += _u32(count)
    for index, cap in enumerate(caps, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        out += enc_str(cap.ref) + enc_str(cap.value) + enc_str("CAP") + enc_str("CAP10") + enc_text(CAP_PROP_TEXT)
    out += _u32(0)
    return bytes(out)


def validate_free_cap_chunk(chunk: bytes, expected_count: int, *, exact_hash: str | None = None) -> list[str]:
    issues: list[str] = []
    expected_len = 2 + expected_count * FREE_CAP_CORE_SIZE
    if len(chunk) != expected_len:
        issues.append(f"object chunk length {len(chunk)} != {expected_len}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if exact_hash and sha256_bytes(chunk) != exact_hash:
        issues.append("object chunk does not match exact donor hash")
    counts = {
        "CAPACITOR": chunk.count(b"CAPACITOR"),
        "CAP10": chunk.count(b"CAP10"),
        "$TERINPUT": chunk.count(b"$TERINPUT"),
        "$TEROUTPUT": chunk.count(b"$TEROUTPUT"),
        "WIRE": chunk.count(b"WIRE"),
    }
    expected_counts = {"CAPACITOR": expected_count, "CAP10": expected_count, "$TERINPUT": 0, "$TEROUTPUT": 0, "WIRE": 0}
    for marker, expected in expected_counts.items():
        if counts[marker] != expected:
            issues.append(f"{marker} count {counts[marker]} != {expected}")
    return issues


def write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    validations: dict[str, Any],
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    base_dsn = read_internal_file(base_project, "ROOT.DSN")
    donor_dsn = read_internal_file(donor_project, "ROOT.DSN")
    dsn, section_pointers = build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)

    static_issues = list(validations.get("static_issues", []))
    if _extract_object_chunk(dsn) != object_chunk:
        static_issues.append("rebuilt ROOT.DSN object chunk differs from requested object chunk")

    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v5_diagnostic_not_locked",
        "description": description,
        "base_project": base_project.name,
        "donor_header_project": donor_project.name,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "object_chunk": {
                "CAPACITOR": object_chunk.count(b"CAPACITOR"),
                "CAP10": object_chunk.count(b"CAP10"),
                "$TERINPUT": object_chunk.count(b"$TERINPUT"),
                "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
                "WIRE": object_chunk.count(b"WIRE"),
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
            },
        },
        "section_pointer_values": section_pointers,
        "validations": validations,
        "static_validation_issues": static_issues,
        "output_hashes": {
            output_path.name: sha256_file(output_path),
            cdb_path.name: sha256_file(cdb_path),
            dsn_path.name: sha256_file(dsn_path),
            "object_chunk": sha256_bytes(object_chunk),
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
    cap3 = registry.get("cap3_three_capacitors").path
    free_template = load_free_cap_core(t01)
    donor_cap3_chunk = _extract_object_chunk(read_internal_file(cap3, "ROOT.DSN"))
    donor_cap3_cdb = read_internal_file(cap3, "ROOT.CDB")

    exact_caps = [
        FreeCap("C1", "1nF", -8636000, 2794000, 0),
        FreeCap("C2", "1nF", -8636000, 762000, 0xFFFFFFFF),
        FreeCap("C3", "1nF", -6350000, 1778000, 0),
    ]
    generated_cap3_chunk = build_free_cap_chunk(free_template, exact_caps)
    generated_cap3_cdb = build_cap_cdb(exact_caps)
    if generated_cap3_chunk != donor_cap3_chunk:
        raise RuntimeError("Generated cap3 object chunk does not exactly match the user donor.")
    if generated_cap3_cdb != donor_cap3_cdb:
        raise RuntimeError("Generated cap3 ROOT.CDB does not exactly match the user donor.")

    cases: list[dict[str, Any]] = []
    cases.append(
        write_case(
            case_id="CAP_V5_T01_EXACT_CAP3_TRANSPLANT",
            description="Exact user cap3 ROOT.CDB and exact cap3 object chunk rebuilt from E001.",
            base_project=base,
            donor_project=cap3,
            object_chunk=donor_cap3_chunk,
            cdb=donor_cap3_cdb,
            validations={
                "cap3_source_hash": sha256_file(cap3),
                "static_issues": validate_free_cap_chunk(donor_cap3_chunk, 3, exact_hash=sha256_bytes(donor_cap3_chunk)),
            },
        )
    )
    cases.append(
        write_case(
            case_id="CAP_V5_T02_REGENERATED_CAP3_EXACT",
            description="Generated three-cap ROOT.CDB and object chunk; both are byte-exact to user cap3.",
            base_project=base,
            donor_project=cap3,
            object_chunk=generated_cap3_chunk,
            cdb=generated_cap3_cdb,
            validations={
                "generated_object_exact_to_cap3": True,
                "generated_cdb_exact_to_cap3": True,
                "static_issues": validate_free_cap_chunk(generated_cap3_chunk, 3, exact_hash=sha256_bytes(donor_cap3_chunk)),
            },
        )
    )

    two_zero = [
        FreeCap("C1", "1nF", -8636000, 2794000, 0),
        FreeCap("C2", "1nF", -8636000, 762000, 0),
    ]
    two_donor_flag = [
        FreeCap("C1", "1nF", -8636000, 2794000, 0),
        FreeCap("C2", "1nF", -8636000, 762000, 0xFFFFFFFF),
    ]
    translated = [
        FreeCap("C1", "1nF", -7366000, 254000, 0),
        FreeCap("C2", "1nF", -4826000, 254000, 0xFFFFFFFF),
        FreeCap("C3", "1nF", -2286000, 254000, 0),
    ]
    renamed = [
        FreeCap("C4", "1nF", -7366000, -2286000, 0),
        FreeCap("C5", "1nF", -4826000, -2286000, 0xFFFFFFFF),
        FreeCap("C6", "1nF", -2286000, -2286000, 0),
    ]

    for case_id, description, caps in [
        (
            "CAP_V5_T03_TWO_FREE_CAPS_ZERO_FLAGS",
            "Two generated free capacitor records with all component-table flags set to zero.",
            two_zero,
        ),
        (
            "CAP_V5_T04_TWO_FREE_CAPS_DONOR_FLAG",
            "Two generated free capacitor records with the second component-table flag matching cap3's FFFFFFFF value.",
            two_donor_flag,
        ),
        (
            "CAP_V5_T05_THREE_FREE_CAPS_TRANSLATED",
            "Three generated free capacitor records translated onto one safe horizontal row.",
            translated,
        ),
        (
            "CAP_V5_T06_THREE_FREE_CAPS_RENAMED",
            "Three generated free capacitor records translated and renamed C4/C5/C6.",
            renamed,
        ),
    ]:
        chunk = build_free_cap_chunk(free_template, caps)
        cdb = build_cap_cdb(caps)
        cases.append(
            write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_project=cap3,
                object_chunk=chunk,
                cdb=cdb,
                validations={"static_issues": validate_free_cap_chunk(chunk, len(caps))},
            )
        )

    summary = {
        "case": "CAPACITOR_V5_CAP3_TEMP_2026_05_30",
        "status": "temporary_diagnostic_not_locked",
        "source_donor": {
            "path": str(cap3),
            "sha256": sha256_file(cap3),
            "root_cdb_sha256": sha256_bytes(donor_cap3_cdb),
            "object_chunk_sha256": sha256_bytes(donor_cap3_chunk),
        },
        "method": "Use user cap3 as the multi-cap free-component donor. Avoid terminal endpoint groups; test free capacitor records and CDB expansion first.",
        "test_order": [case["case_id"] for case in cases],
        "paired_note": "T03/T04 are a pair. If T03 fails, still try T04 to isolate whether the cap3 FFFFFFFF component-table flag matters.",
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V5 cap3 temporary diagnostics.\n\n"
        "Open in order. T03/T04 are paired; if T03 fails, still test T04.\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, start=1))
        + "\n\nReport which cases open, which case first errors, and the exact Proteus error text.\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
