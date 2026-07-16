"""Temporary capacitor V4 diagnostics.

This is not a production generator. It builds a small ordered test pack from
the capacitor donor projects so Proteus results can tell us which capacitor
piece is safe before any capacitor path is promoted into src/proteusgen.
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
from proteusgen.resistor_v9 import _extract_object_chunk, _i32, _u16, _u32, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "capacitor_v4_temp_2026_05_30"

IN_SIZE = 103
OUT_SIZE = 104
CAP_SIZE = 366
WIRE_SIZE = 50
CAP_BASE_X = -7112000
CAP_BASE_Y = -508000
CAP_PROP_TEXT = b"{PRIMITIVE=ANALOGUE,CAPACITOR}\n\n{PACKAGE=CAP10}\n\n\x00"


@dataclass(frozen=True)
class CapTemplates:
    input_terminal: bytes
    output_terminal: bytes
    cap_record: bytes
    wire_left: bytes
    wire_right: bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def signed_i32(data: bytes, offset: int) -> int:
    return struct.unpack("<i", data[offset : offset + 4])[0]


def patch_i32(record: bytearray, offset: int, value: int) -> None:
    record[offset : offset + 4] = _i32(value)


def load_templates(t02_project: Path) -> CapTemplates:
    chunk = _extract_object_chunk(read_internal_file(t02_project, "ROOT.DSN"))
    expected_len = 1 + IN_SIZE + OUT_SIZE + CAP_SIZE + WIRE_SIZE + WIRE_SIZE
    if len(chunk) != expected_len:
        raise RuntimeError(f"CAP_T02 object chunk length {len(chunk)} != {expected_len}.")
    if chunk[0] != 0 or chunk[-1] != 0xFF:
        raise RuntimeError("CAP_T02 object chunk does not have the expected header/final terminator.")
    return CapTemplates(
        input_terminal=chunk[1 : 1 + IN_SIZE],
        output_terminal=chunk[1 + IN_SIZE : 1 + IN_SIZE + OUT_SIZE],
        cap_record=chunk[1 + IN_SIZE + OUT_SIZE : 1 + IN_SIZE + OUT_SIZE + CAP_SIZE],
        wire_left=chunk[1 + IN_SIZE + OUT_SIZE + CAP_SIZE : 1 + IN_SIZE + OUT_SIZE + CAP_SIZE + WIRE_SIZE],
        wire_right=chunk[1 + IN_SIZE + OUT_SIZE + CAP_SIZE + WIRE_SIZE :],
    )


def cap_suffixes(index: int) -> tuple[int, int]:
    # CAP_T02 uses in=00b2 and out=0080 for C1. Keep the same family and
    # spread generated records far enough to avoid collisions in temp tests.
    step = 0x0040
    in_suffix = 0x00B2 + (index - 1) * step
    out_suffix = 0x0080 + (index - 1) * step
    return in_suffix, out_suffix


def patch_input(template: bytes, label: str, dx: int, dy: int, in_suffix: int) -> bytes:
    if len(label) != 2 or not label.isascii():
        raise ValueError("Capacitor temp terminal labels must be exactly two ASCII characters.")
    record = bytearray(template)
    for offset in (1, 33):
        patch_i32(record, offset, signed_i32(template, offset) + dx)
    for offset in (5, 37):
        patch_i32(record, offset, signed_i32(template, offset) + dy)
    record[30] = 2
    record[31:33] = label.encode("ascii")
    record[-4:-2] = _u16(in_suffix)
    record[-2] = 0x01
    record[-1] = 0x00
    return bytes(record)


def patch_output(template: bytes, label: str, dx: int, dy: int, out_suffix: int) -> bytes:
    if len(label) != 2 or not label.isascii():
        raise ValueError("Capacitor temp terminal labels must be exactly two ASCII characters.")
    record = bytearray(template)
    for offset in (1, 34):
        patch_i32(record, offset, signed_i32(template, offset) + dx)
    for offset in (5, 38):
        patch_i32(record, offset, signed_i32(template, offset) + dy)
    record[31] = 2
    record[32:34] = label.encode("ascii")
    record[-4:-2] = _u16(out_suffix)
    record[-2] = 0x01
    record[-1] = 0x00
    return bytes(record)


def patch_cap(template: bytes, ref: str, value: str, dx: int, dy: int, in_suffix: int, out_suffix: int, final: bool) -> bytes:
    if len(ref) != 2 or not ref.isascii():
        raise ValueError("Capacitor temp refs must be exactly two ASCII characters.")
    if len(value) != 3 or not value.isascii():
        raise ValueError("Capacitor temp visible values must be exactly three ASCII characters.")
    record = bytearray(template)
    record[2] = 2
    record[3:5] = ref.encode("ascii")
    record[70] = 3
    record[71:74] = value.encode("ascii")
    for offset in (5, 74, 146, 260, 332):
        patch_i32(record, offset, signed_i32(template, offset) + dx)
    for offset in (9, 78, 150, 264, 336):
        patch_i32(record, offset, signed_i32(template, offset) + dy)
    record[357:359] = _u16(out_suffix)
    record[359:361] = b"\x01\x00"
    record[361:363] = _u16(in_suffix)
    record[363:365] = b"\x01\x00"
    record[-1] = 0xFF if final else 0x00
    return bytes(record)


def patch_wire(template: bytes, dx: int, dy: int, final: bool) -> bytes:
    record = bytearray(template)
    for offset in (33, 41):
        patch_i32(record, offset, signed_i32(template, offset) + dx)
    for offset in (37, 45):
        patch_i32(record, offset, signed_i32(template, offset) + dy)
    record[-1] = 0xFF if final else 0x00
    return bytes(record)


def build_cap_group(
    templates: CapTemplates,
    *,
    index: int,
    ref: str,
    value: str,
    left: str,
    right: str,
    x: int,
    y: int,
    final: bool,
) -> bytes:
    dx = x - CAP_BASE_X
    dy = y - CAP_BASE_Y
    in_suffix, out_suffix = cap_suffixes(index)
    return b"".join(
        (
            patch_input(templates.input_terminal, left, dx, dy, in_suffix),
            patch_output(templates.output_terminal, right, dx, dy, out_suffix),
            patch_cap(templates.cap_record, ref, value, dx, dy, in_suffix, out_suffix, final=False),
            patch_wire(templates.wire_left, dx, dy, final=False),
            patch_wire(templates.wire_right, dx, dy, final=final),
        )
    )


def build_cap_object_chunk(templates: CapTemplates, caps: list[dict[str, Any]]) -> bytes:
    groups: list[bytes] = []
    for index, cap in enumerate(caps, start=1):
        groups.append(
            build_cap_group(
                templates,
                index=index,
                ref=cap["ref"],
                value=cap["value"],
                left=cap["left"],
                right=cap["right"],
                x=cap["x"],
                y=cap["y"],
                final=index == len(caps),
            )
        )
    return b"\x00" + b"".join(groups)


def build_cap_cdb(caps: list[dict[str, Any]]) -> bytes:
    out = bytearray()
    count = len(caps)
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + enc_str("Master Sheet") + _u32(10) + _u32(0)
    out += _u32(count)
    for index, cap in enumerate(caps, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(index) + enc_str(cap["ref"])
        out += _u32(2) + enc_str("2") + enc_str("2") + enc_str("1") + enc_str("1")
        out += _u32(0) + _u32(index) + _u32(0)
    out += _u32(1) + _u32(1) + b"\x00" + enc_str("") + _u32(1)
    out += _u32(count)
    for index, cap in enumerate(caps, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        out += enc_str(cap["ref"]) + enc_str(cap["value"]) + enc_str("CAP") + enc_str("CAP10") + enc_text(CAP_PROP_TEXT)
    out += _u32(0)
    return bytes(out)


def validate_chunk(
    chunk: bytes,
    cap_count: int,
    *,
    exact_hash: str | None = None,
    expected_counts: dict[str, int] | None = None,
) -> list[str]:
    issues: list[str] = []
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if exact_hash and sha256_bytes(chunk) != exact_hash:
        issues.append("object chunk does not match exact donor hash")
    expected_len = 1 + cap_count * (IN_SIZE + OUT_SIZE + CAP_SIZE + WIRE_SIZE + WIRE_SIZE)
    if exact_hash is None and len(chunk) != expected_len:
        issues.append(f"generated chunk length {len(chunk)} != {expected_len}")
    if expected_counts is None:
        expected_counts = {
            "$TERINPUT": cap_count,
            "$TEROUTPUT": cap_count,
            "CAPACITOR": cap_count,
            "CAP10": cap_count,
            "WIRE": cap_count * 2,
        }
    for marker, expected in expected_counts.items():
        count = chunk.count(marker.encode("ascii"))
        if count != expected:
            issues.append(f"{marker} count {count} != {expected}")
    return issues


def write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    source: str,
    validations: dict[str, Any],
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    donor_dsn = read_internal_file(donor_project, "ROOT.DSN")
    base_dsn = read_internal_file(base_project, "ROOT.DSN")
    dsn, section_pointers = build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    rebuilt_chunk = _extract_object_chunk(dsn)
    static_issues = list(validations.get("static_issues", []))
    if rebuilt_chunk != object_chunk:
        static_issues.append("rebuilt ROOT.DSN object chunk differs from requested object chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v4_diagnostic_not_locked",
        "description": description,
        "source": source,
        "base_project": base_project.name,
        "donor_header_project": donor_project.name,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "object_chunk": {
                "$TERINPUT": object_chunk.count(b"$TERINPUT"),
                "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
                "$TERPOWER": object_chunk.count(b"$TERPOWER"),
                "$TERGROUND": object_chunk.count(b"$TERGROUND"),
                "CAPACITOR": object_chunk.count(b"CAPACITOR"),
                "CAP10": object_chunk.count(b"CAP10"),
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
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, "manifest.json", "README_TEST_FIRST.txt"],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n"
        f"{description}\n\n"
        "Open this project in Proteus and stop at the first error in the ordered test list.\n\n"
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
    templates = load_templates(t02)
    donor_t01_chunk = _extract_object_chunk(read_internal_file(t01, "ROOT.DSN"))
    donor_t02_chunk = _extract_object_chunk(read_internal_file(t02, "ROOT.DSN"))
    donor_t01_cdb = read_internal_file(t01, "ROOT.CDB")
    donor_t02_cdb = read_internal_file(t02, "ROOT.CDB")

    t01_generated_cdb = build_cap_cdb([{"ref": "C1", "value": "1uF"}])
    if t01_generated_cdb != donor_t01_cdb:
        raise RuntimeError("Generated one-cap ROOT.CDB does not exactly match CAP_T01 donor.")
    t02_rebuilt_chunk = build_cap_object_chunk(
        templates,
        [{"ref": "C1", "value": "1uF", "left": "N1", "right": "N2", "x": CAP_BASE_X, "y": CAP_BASE_Y}],
    )
    if t02_rebuilt_chunk != donor_t02_chunk:
        raise RuntimeError("Generated one-cap terminal group does not exactly match CAP_T02 donor.")

    cases: list[dict[str, Any]] = []
    cases.append(
        write_case(
            case_id="CAP_V4_T01_EXACT_T01_SINGLE_CAP",
            description="Exact CAP_T01 object chunk plus exact generated C1 ROOT.CDB, rebuilt from E001.",
            base_project=base,
            donor_project=t01,
            object_chunk=donor_t01_chunk,
            cdb=donor_t01_cdb,
            source="CAP_T01 exact object chunk transplant",
            validations={
                "t01_cdb_exact": True,
                "static_issues": validate_chunk(
                    donor_t01_chunk,
                    1,
                    exact_hash=sha256_bytes(donor_t01_chunk),
                    expected_counts={"$TERINPUT": 0, "$TEROUTPUT": 0, "CAPACITOR": 1, "CAP10": 1, "WIRE": 0},
                ),
            },
        )
    )
    cases.append(
        write_case(
            case_id="CAP_V4_T02_EXACT_T02_TERMINAL_CAP_TERMINAL",
            description="Exact CAP_T02 terminal-capacitor-terminal object chunk plus exact generated C1 ROOT.CDB, rebuilt from E001.",
            base_project=base,
            donor_project=t02,
            object_chunk=donor_t02_chunk,
            cdb=donor_t02_cdb,
            source="CAP_T02 exact object chunk transplant",
            validations={
                "t02_rebuild_exact": True,
                "static_issues": validate_chunk(donor_t02_chunk, 1, exact_hash=sha256_bytes(donor_t02_chunk)),
            },
        )
    )
    c2_chunk = build_cap_object_chunk(
        templates,
        [{"ref": "C2", "value": "1uF", "left": "N3", "right": "N4", "x": CAP_BASE_X, "y": CAP_BASE_Y}],
    )
    cases.append(
        write_case(
            case_id="CAP_V4_T03_PATCHED_C2_SAME_POSITION",
            description="One generated CAP_T02-style group with C2/N3/N4 labels at the donor coordinates.",
            base_project=base,
            donor_project=t02,
            object_chunk=c2_chunk,
            cdb=build_cap_cdb([{"ref": "C2", "value": "1uF"}]),
            source="CAP_T02 group with same-length ref and terminal label patches",
            validations={"static_issues": validate_chunk(c2_chunk, 1)},
        )
    )
    translated_chunk = build_cap_object_chunk(
        templates,
        [{"ref": "C1", "value": "1uF", "left": "N1", "right": "N2", "x": CAP_BASE_X + 2540000, "y": CAP_BASE_Y - 2540000}],
    )
    cases.append(
        write_case(
            case_id="CAP_V4_T04_TRANSLATED_T02_GROUP",
            description="One generated CAP_T02-style group translated by the locked safe spacing.",
            base_project=base,
            donor_project=t02,
            object_chunk=translated_chunk,
            cdb=donor_t02_cdb,
            source="CAP_T02 group with coordinate translation only",
            validations={"static_issues": validate_chunk(translated_chunk, 1)},
        )
    )
    two_cap_chunk = build_cap_object_chunk(
        templates,
        [
            {"ref": "C1", "value": "1uF", "left": "N1", "right": "N2", "x": CAP_BASE_X, "y": CAP_BASE_Y},
            {"ref": "C2", "value": "1uF", "left": "N3", "right": "N4", "x": CAP_BASE_X + 2540000, "y": CAP_BASE_Y - 2540000},
        ],
    )
    cases.append(
        write_case(
            case_id="CAP_V4_T05_TWO_ISOLATED_CAPS",
            description="Two generated CAP_T02-style groups with generated two-cap ROOT.CDB. This is expected to be the first risky case.",
            base_project=base,
            donor_project=t02,
            object_chunk=two_cap_chunk,
            cdb=build_cap_cdb([{"ref": "C1", "value": "1uF"}, {"ref": "C2", "value": "1uF"}]),
            source="CAP_T02 group duplicated sequentially after exact one-cap guards",
            validations={"static_issues": validate_chunk(two_cap_chunk, 2)},
        )
    )

    summary = {
        "case": "CAPACITOR_V4_TEMP_2026_05_30",
        "status": "temporary_diagnostic_not_locked",
        "method": "Exact donor reproduction guards first, then same-length patch, coordinate translation, and only then a two-cap generated case.",
        "important_rule": "Do not promote capacitor until Proteus opens the ordered diagnostics without VGDVC/library errors.",
        "test_order": [case["case_id"] for case in cases],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V4 temporary diagnostics.\n\n"
        "Open in this order and stop at the first failure:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, start=1))
        + "\n\nReport the first failing case and the exact Proteus error.\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
