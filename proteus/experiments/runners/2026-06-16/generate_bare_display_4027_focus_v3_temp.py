"""Focused no-terminal follow-up for displays and 4027.

User feedback on V2:
- Source-only/source-pair cases worked.
- Synthetic display counts were not trustworthy.
- Embedded display cathode/anode experiments opened with bad-object warnings.
- 4027 x03 worked, while x5/x15/x23 from the broad mega matrix failed.

This pack uses the new user-provided standalone display donors and fresh 4027
1x/2x/4x donors. It keeps display and 4027 learning isolated from the broad
pair matrix.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.cdb import CdbFile, CdbPinRow, CdbPropertyRow, parse_cdb
from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn

HELPER_PATH = ROOT / "tools/proteus_generation/2026-06-16/generate_mega_bare_separation_v1_temp.py"
DONOR_DIR = ROOT / "proteus_ic/donors/manual_downloads_20260616/mega_component_placer/display_4027_followup"
OUT_DIR = ROOT / "experiments/bare_display_4027_focus_v3_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_4027_FOCUS_V3_TEMP_2026_06_16.zip"

AN_BLUE_1 = DONOR_DIR / "7segcomANblue.pdsprj"
AN_BLUE_4 = DONOR_DIR / "4_7segcomANblue.pdsprj"
CC_RED_1 = DONOR_DIR / "7segcomcathred.pdsprj"
CC_RED_4 = DONOR_DIR / "4_7segcomcathred.pdsprj"
JK_4027_1 = DONOR_DIR / "4027.pdsprj"
JK_4027_2 = DONOR_DIR / "2_4027.pdsprj"
JK_4027_4 = DONOR_DIR / "4_4027.pdsprj"

COUNT_CHOICES = (1, 3, 5, 15, 23)


@dataclass(frozen=True)
class DisplayDonor:
    name: str
    single: Path
    four: Path


def load_helper():
    spec = importlib.util.spec_from_file_location("mega_bare_v1", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper script: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mega_bare_v1"] = module
    spec.loader.exec_module(module)
    module.OUT_DIR = OUT_DIR
    module.FAMILY_MARKERS = tuple(sorted(set(module.FAMILY_MARKERS + ("VSINE",)), key=len, reverse=True))
    return module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def zip_dir(src: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with ZipFile(output, "w") as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            info = ZipInfo(path.relative_to(src).as_posix())
            info.compress_type = ZIP_DEFLATED
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o600 << 16
            zf.writestr(info, path.read_bytes())


def marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "7SEGCOMA",
        "7SEGCOMK",
        "7SEG-COM-AN-BLUE",
        "4027",
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def component_starts_by_component_id(chunk: bytes) -> list[int]:
    starts: list[int] = []
    pos = 0
    while True:
        pos = chunk.find(b"COMPONENT ID", pos)
        if pos < 0:
            break
        starts.append(max(0, pos - 51))
        pos += 1
    return starts


def split_display_records(four_path: Path) -> list[bytes]:
    chunk = _extract_object_chunk(read_internal_file(four_path, "ROOT.DSN"))
    starts = component_starts_by_component_id(chunk)
    starts.append(len(chunk))
    if len(starts) != 5:
        raise ValueError(f"{four_path.name}: expected four display records, found {len(starts)-1}.")
    return [chunk[starts[i] : starts[i + 1]] for i in range(4)]


def display_chunk(donor: DisplayDonor, count: int) -> tuple[bytes, str]:
    single = _extract_object_chunk(read_internal_file(donor.single, "ROOT.DSN"))
    records = split_display_records(donor.four)
    if count == 1:
        return single, "single donor exact object chunk"
    if count <= 4:
        return b"".join(records[: count - 1]) + records[-1], "subset of four-display donor with donor-final fourth record"
    middle_cycle = records[:3]
    body = bytearray()
    for index in range(count - 1):
        body.extend(middle_cycle[index % len(middle_cycle)])
    body.extend(records[-1])
    return bytes(body), "synthetic repeat from four-display middle records plus donor-final fourth record"


def write_forced_case(case_id: str, donor_path: Path, cdb: bytes, donor_dsn: bytes, object_chunk: bytes, description: str, extra: dict[str, object] | None = None) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(donor_path, output, {"ROOT.DSN": dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs from requested chunk")
    if any(term in final_chunk for term in (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")):
        errors.append("terminal marker present")
    result = {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(donor_path.relative_to(ROOT)),
        "description": description,
        "object_chunk_size": len(final_chunk),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "pointers": pointers,
        "errors": errors,
    }
    if extra:
        result.update(extra)
    return result


def copy_exact_case(case_id: str, donor_path: Path, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(donor_path, output)
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(donor_path.relative_to(ROOT)),
        "description": description,
        "copy_exact": True,
        "object_chunk_size": len(chunk),
        "object_chunk_sha256": sha256_bytes(chunk),
        "marker_counts": marker_counts(chunk),
        "errors": [],
    }


def replace_lp_ascii(row: bytes, header_size: int, old_ref: str, new_ref: str) -> bytes:
    old = old_ref.encode("ascii")
    new = new_ref.encode("ascii")
    if row[header_size] != len(old) or row[header_size + 1 : header_size + 1 + len(old)] != old:
        raise ValueError(f"CDB row does not start with {old_ref!r}.")
    return row[:header_size] + bytes([len(new)]) + new + row[header_size + 1 + len(old) :]


def patch_pin_row(template: CdbPinRow, old_ref: str, new_ref: str, row_id: int) -> CdbPinRow:
    data = bytearray(replace_lp_ascii(template.data, 16, old_ref, new_ref))
    data[0:4] = row_id.to_bytes(4, "little")
    data[12:16] = row_id.to_bytes(4, "little")
    return CdbPinRow(ref=new_ref, data=bytes(data))


def patch_property_row(template: CdbPropertyRow, old_ref: str, new_ref: str, package_id: int) -> CdbPropertyRow:
    data = bytearray(replace_lp_ascii(template.data, 20, old_ref, new_ref))
    data[0:4] = package_id.to_bytes(4, "little")
    return CdbPropertyRow(ref=new_ref, data=bytes(data))


def build_4027_cdb(count: int) -> bytes:
    parsed = parse_cdb(read_internal_file(JK_4027_4, "ROOT.CDB"))
    pin_templates = {row.ref: row for row in parsed.pin_rows}
    property_templates = {row.ref: row for row in parsed.property_rows}
    pin_rows: list[CdbPinRow] = []
    property_rows: list[CdbPropertyRow] = []
    for package_index in range(1, count + 1):
        package_ref = f"U{package_index}"
        pin_rows.append(patch_pin_row(pin_templates["U1:A"], "U1:A", f"{package_ref}:A", 2 * package_index + 5))
        pin_rows.append(patch_pin_row(pin_templates["U1:B"], "U1:B", f"{package_ref}:B", 2 * package_index + 6))
        prop_template = property_templates["U4"] if package_index == count else property_templates["U1"]
        old_ref = "U4" if package_index == count else "U1"
        property_rows.append(patch_property_row(prop_template, old_ref, package_ref, package_index))
    prefix = bytearray(parsed.prefix)
    prefix.extend(len(pin_rows).to_bytes(4, "little"))
    return bytes(prefix) + b"".join(row.data for row in pin_rows) + parsed.between_sections + b"".join(row.data for row in property_rows) + parsed.suffix


def patch_4027_group(data: bytes, old_package: str, new_package: str) -> bytes:
    return data.replace(f"{old_package}:A".encode("ascii"), f"{new_package}:A".encode("ascii")).replace(
        f"{old_package}:B".encode("ascii"), f"{new_package}:B".encode("ascii")
    )


def build_4027_chunk(helper, count: int) -> tuple[bytes, str]:
    state = helper.load_donor(JK_4027_4)
    groups = state.groups_by_family["4027"]
    if count <= 4:
        return helper.object_chunk_for(tuple(groups[:count]))[0], "tail-delete/subset from exact 4x donor"
    middle_templates = groups[:3]
    final_template = groups[3]
    body = bytearray(b"\x00\x00")
    for index in range(1, count):
        template = middle_templates[(index - 1) % len(middle_templates)]
        body.extend(patch_4027_group(template.data, template.key, f"U{index}"))
    body.extend(patch_4027_group(final_template.data, final_template.key, f"U{count}"))
    body.extend(b"\xff")
    return bytes(body), "experimental cloned 4027 packages with unique U refs and rebuilt CDB"


def build_cases() -> dict[str, object]:
    helper = load_helper()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    cases: list[dict[str, object]] = []
    for case_id, donor_path, description in [
        ("D00_EXACT_AN_BLUE_1X", AN_BLUE_1, "Exact one common-anode blue 7-segment donor."),
        ("D01_EXACT_AN_BLUE_4X", AN_BLUE_4, "Exact four common-anode blue 7-segment donor."),
        ("D02_EXACT_CC_RED_1X", CC_RED_1, "Exact one common-cathode red 7-segment donor."),
        ("D03_EXACT_CC_RED_4X", CC_RED_4, "Exact four common-cathode red 7-segment donor."),
        ("K00_EXACT_4027_1X", JK_4027_1, "Exact one 4027 donor."),
        ("K01_EXACT_4027_2X", JK_4027_2, "Exact two 4027 donor."),
        ("K02_EXACT_4027_4X", JK_4027_4, "Exact four 4027 donor."),
    ]:
        cases.append(copy_exact_case(case_id, donor_path, description))

    for prefix, donor in [
        ("ANB", DisplayDonor("common-anode blue", AN_BLUE_1, AN_BLUE_4)),
        ("CCR", DisplayDonor("common-cathode red", CC_RED_1, CC_RED_4)),
    ]:
        host_dsn = read_internal_file(donor.four, "ROOT.DSN")
        host_cdb = read_internal_file(donor.four, "ROOT.CDB")
        for count in COUNT_CHOICES:
            chunk, method = display_chunk(donor, count)
            cases.append(
                write_forced_case(
                    f"{prefix}_{count:02d}X_DISPLAY",
                    donor.four,
                    host_cdb,
                    host_dsn,
                    chunk,
                    f"{count} x {donor.name} no-terminal display records.",
                    {"requested_count": count, "method": method},
                )
            )

    host_dsn = read_internal_file(JK_4027_4, "ROOT.DSN")
    for count in COUNT_CHOICES:
        chunk, method = build_4027_chunk(helper, count)
        cdb = read_internal_file(JK_4027_4, "ROOT.CDB") if count <= 4 else build_4027_cdb(count)
        cdb_parse = "ok"
        try:
            parse_cdb(cdb)
        except Exception as exc:  # pragma: no cover - captured in summary
            cdb_parse = f"failed: {exc}"
        cases.append(
            write_forced_case(
                f"K{count:02d}_4027_{count:02d}X",
                JK_4027_4,
                cdb,
                host_dsn,
                chunk,
                f"{count} x 4027 focused count test.",
                {"requested_count": count, "method": method, "cdb_parse": cdb_parse},
            )
        )

    return {
        "experiment": "bare_display_4027_focus_v3_temp_2026_06_16",
        "purpose": "Focused retest for standalone common-anode/common-cathode displays and 4027 high counts after user V2 feedback.",
        "case_count": len(cases),
        "cases": cases,
    }


def main() -> None:
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": summary["case_count"], "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
