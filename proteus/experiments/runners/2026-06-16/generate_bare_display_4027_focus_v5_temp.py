"""Display and 4027 component-specific diagnostics after V4 rejection.

V4 failures reported by user:
- All ANM/CCM generated display cases failed.
- K03 and later generated 4027 cases failed.

Confirmed V4 mistakes:
- Display records were wrapped in the generic 00 00 + records + FF envelope.
  Pure display donors use direct 00 08 FF 00... records instead.
- Display splitting used COMPONENT-ID offsets; this is unsafe at family/block
  boundaries. Use the real display record signature 00 08 FF 00.
- 4027 selection used contiguous helper groups as if every group were a full
  package. In mega donors, some 4027 A/B subparts are split; use package-aware
  complete groups and skip split packages for this focused pack.

This pack deliberately contains controls plus narrow candidates. It is not a
general matrix.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.cdb import CdbFile, CdbPinRow, CdbPropertyRow, parse_cdb
from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


HELPER_PATH = ROOT / "tools/proteus_generation/2026-06-16/generate_mega_bare_separation_v1_temp.py"
DONOR_DIR = ROOT / "proteus_ic/donors/manual_downloads_20260616/mega_component_placer"
FOLLOWUP_DIR = DONOR_DIR / "display_4027_followup"
OUT_DIR = ROOT / "experiments/bare_display_4027_focus_v5_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_4027_FOCUS_V5_TEMP_2026_06_16.zip"

MEGA_NO_SOURCE = (
    DONOR_DIR
    / "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)

AN_BLUE_1 = FOLLOWUP_DIR / "7segcomANblue.pdsprj"
AN_BLUE_4 = FOLLOWUP_DIR / "4_7segcomANblue.pdsprj"
CC_RED_1 = FOLLOWUP_DIR / "7segcomcathred.pdsprj"
CC_RED_4 = FOLLOWUP_DIR / "4_7segcomcathred.pdsprj"
JK_4027_1 = FOLLOWUP_DIR / "4027.pdsprj"
JK_4027_2 = FOLLOWUP_DIR / "2_4027.pdsprj"
JK_4027_4 = FOLLOWUP_DIR / "4_4027.pdsprj"

COUNT_CHOICES = (1, 3, 5, 15, 23)
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
DISPLAY_RECORD_START = b"\x00\x08\xff\x00"


def load_helper():
    spec = importlib.util.spec_from_file_location("mega_bare_v1_for_v5", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper script: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mega_bare_v1_for_v5"] = module
    spec.loader.exec_module(module)
    module.OUT_DIR = OUT_DIR
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
        "7SEG-COM-ANODE",
        "7SEG-COM-AN-BLUE",
        "7SEG-COM-CATHODE",
        "7SEG-COM-CAT-BLUE",
        "7SEG-COM-CAT",
        "4027",
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def display_kind(record: bytes) -> str | None:
    if b"7SEGCOMA" in record or b"7SEG-COM-ANODE" in record or b"7SEG-COM-AN-BLUE" in record:
        return "anode"
    if b"7SEGCOMK" in record or b"7SEG-COM-CAT" in record or b"7SEG-COM-CATHODE" in record:
        return "cathode"
    return None


def split_display_records(path: Path) -> list[bytes]:
    chunk = _extract_object_chunk(read_internal_file(path, "ROOT.DSN"))
    starts: list[int] = []
    pos = 0
    while True:
        pos = chunk.find(DISPLAY_RECORD_START, pos)
        if pos < 0:
            break
        if b"7SEG" in chunk[pos : pos + 520]:
            starts.append(pos)
        pos += 1
    if not starts:
        return []
    starts.append(len(chunk))
    return [chunk[starts[i] : starts[i + 1]] for i in range(len(starts) - 1)]


def mega_display_records(kind: str) -> list[bytes]:
    records = split_display_records(MEGA_NO_SOURCE)
    selected = [record for record in records if display_kind(record) == kind]
    if not selected:
        raise ValueError(f"No mega display records found for {kind}.")
    return selected


def display_chunk_mega_anode(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("anode")
    if len(rows) < count:
        raise ValueError(f"Need {count} anode rows, found {len(rows)}.")
    # Use the donor-final anode row as the final row, matching 4x display donor behavior.
    chosen = rows[: max(0, count - 1)] + [rows[-1]]
    return b"".join(chosen), {
        "method": "prefixless mega display rows; selected last row is donor-final anode record",
        "source_rows": len(rows),
        "selected_count": len(chosen),
    }


def display_chunk_mega_cathode_with_append_ff(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("cathode")
    if len(rows) < count:
        raise ValueError(f"Need {count} cathode rows, found {len(rows)}.")
    body = b"".join(rows[:count])
    if not body.endswith(b"\xff"):
        body += b"\xff"
    return body, {
        "method": "prefixless mega cathode rows with explicit FF terminator",
        "source_rows": len(rows),
        "selected_count": count,
    }


def display_chunk_mega_cathode_hybrid_final(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("cathode")
    if len(rows) < count:
        raise ValueError(f"Need {count} cathode rows, found {len(rows)}.")
    final_red = _extract_object_chunk(read_internal_file(CC_RED_1, "ROOT.DSN"))
    chosen = rows[: max(0, count - 1)] + [final_red]
    return b"".join(chosen), {
        "method": "mega cathode rows with standalone red cathode donor-final row",
        "source_rows": len(rows),
        "selected_count": len(chosen),
        "hybrid_final_row": True,
    }


def write_case(
    case_id: str,
    donor_path: Path,
    cdb: bytes,
    donor_dsn: bytes,
    object_chunk: bytes,
    description: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(donor_path, output, {"ROOT.DSN": dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs from requested chunk")
    if any(marker in final_chunk for marker in TERM_MARKERS):
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


def patch_dsn_ref(data: bytes, old_ref: str, new_ref: str) -> bytes:
    old = old_ref.encode("ascii")
    new = new_ref.encode("ascii")
    pattern = b"\xff" + bytes([len(old)]) + old
    replacement = b"\xff" + bytes([len(new)]) + new
    if pattern not in data:
        raise ValueError(f"Could not find DSN record-start ref {old_ref!r}.")
    data = data.replace(pattern, replacement, 1)
    return data.replace(old, new)


def patch_4027_group_refs(data: bytes, old_package: str, new_package: str) -> bytes:
    for suffix in ("A", "B"):
        old_ref = f"{old_package}:{suffix}"
        if old_ref.encode("ascii") in data:
            data = patch_dsn_ref(data, old_ref, f"{new_package}:{suffix}")
    return data


def complete_4027_groups(helper):
    state = helper.load_donor(MEGA_NO_SOURCE)
    return [group for group in state.groups_by_family["4027"] if len(group.refs) == 2]


def build_4027_mega_direct(helper, count: int) -> tuple[bytes, dict[str, object]]:
    groups = complete_4027_groups(helper)
    if len(groups) < count:
        raise ValueError(f"Need {count} complete 4027 groups, found {len(groups)}.")
    chunk, meta = helper.object_chunk_for(tuple(groups[:count]))
    return chunk, {"method": "complete contiguous mega 4027 package groups with original refs and full mega CDB", "selected_group_keys": [g.key for g in groups[:count]], **meta}


def build_4027_mega_renumbered(helper, count: int) -> tuple[bytes, dict[str, object]]:
    groups = complete_4027_groups(helper)
    if len(groups) < count:
        raise ValueError(f"Need {count} complete 4027 groups, found {len(groups)}.")
    selected = groups[:count]
    body = bytearray(b"\x00\x00")
    for index, group in enumerate(selected[:-1], start=1):
        body.extend(patch_4027_group_refs(group.data, group.key, f"U{index}"))
    final_group = selected[-1]
    final_data, trimmed = helper.finalize_last_group(final_group)
    body.extend(patch_4027_group_refs(final_data, final_group.key, f"U{count}"))
    body.extend(b"\xff")
    return bytes(body), {
        "method": "complete mega 4027 package groups renumbered to U1..Un with generated standalone-style CDB",
        "selected_group_keys": [g.key for g in selected],
        "trimmed_last_byte": trimmed,
    }


def build_4027_standalone_subset(helper, count: int) -> tuple[bytes, dict[str, object]]:
    state = helper.load_donor(JK_4027_4)
    groups = state.groups_by_family["4027"]
    chunk, meta = helper.object_chunk_for(tuple(groups[:count]))
    return chunk, {"method": "standalone 4x donor subset control", "selected_group_keys": [g.key for g in groups[:count]], **meta}


def build_cases() -> dict[str, object]:
    helper = load_helper()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    cases: list[dict[str, object]] = []
    for case_id, donor_path, description in [
        ("D00_EXACT_AN_BLUE_1X", AN_BLUE_1, "Exact one standalone common-anode blue display donor."),
        ("D01_EXACT_AN_BLUE_4X", AN_BLUE_4, "Exact four standalone common-anode blue display donor."),
        ("D02_EXACT_CC_RED_1X", CC_RED_1, "Exact one standalone common-cathode red display donor."),
        ("D03_EXACT_CC_RED_4X", CC_RED_4, "Exact four standalone common-cathode red display donor."),
        ("K00_EXACT_4027_1X", JK_4027_1, "Exact one standalone 4027 donor."),
        ("K01_EXACT_4027_2X", JK_4027_2, "Exact two standalone 4027 donor."),
        ("K02_EXACT_4027_4X", JK_4027_4, "Exact four standalone 4027 donor."),
    ]:
        cases.append(copy_exact_case(case_id, donor_path, description))

    mega_dsn = read_internal_file(MEGA_NO_SOURCE, "ROOT.DSN")
    mega_cdb = read_internal_file(MEGA_NO_SOURCE, "ROOT.CDB")
    jk4_dsn = read_internal_file(JK_4027_4, "ROOT.DSN")
    jk4_cdb = read_internal_file(JK_4027_4, "ROOT.CDB")

    for count in COUNT_CHOICES:
        chunk, meta = display_chunk_mega_anode(count)
        cases.append(write_case(f"ANF_{count:02d}X_MEGA_ANODE_FINALROW", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} anode display records from mega, using donor-final anode row.", {"requested_count": count, **meta}))

    for count in COUNT_CHOICES:
        chunk, meta = display_chunk_mega_cathode_with_append_ff(count)
        cases.append(write_case(f"CCF_{count:02d}X_MEGA_CATHODE_APPEND_FF", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} cathode display records from mega with explicit FF terminator.", {"requested_count": count, **meta}))

    for count in (1, 3, 5, 15):
        chunk, meta = display_chunk_mega_cathode_hybrid_final(count)
        cases.append(write_case(f"CCH_{count:02d}X_MEGA_CATHODE_RED_FINAL", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} cathode displays using mega rows plus red donor-final row.", {"requested_count": count, **meta}))

    # 4027 controls and candidates.
    chunk, meta = build_4027_standalone_subset(helper, 3)
    cases.append(write_case("K03A_4027_STANDALONE4_SUBSET_CONTROL", JK_4027_4, jk4_cdb, jk4_dsn, chunk, "Known-style 3x subset from standalone 4x 4027 donor.", {"requested_count": 3, **meta}))

    for count in (3, 5):
        chunk, meta = build_4027_mega_direct(helper, count)
        cases.append(write_case(f"K{count:02d}B_4027_MEGA_DIRECT_FULL_CDB", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} complete 4027 groups from mega with original refs/full mega CDB.", {"requested_count": count, **meta}))

    for count in COUNT_CHOICES:
        chunk, meta = build_4027_mega_renumbered(helper, count)
        cases.append(write_case(f"K{count:02d}C_4027_MEGA_RENUMBERED_CDB", MEGA_NO_SOURCE, build_4027_cdb(count), mega_dsn, chunk, f"{count} complete 4027 groups from mega, renumbered to U1..U{count}, generated standalone-style CDB.", {"requested_count": count, **meta}))

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_4027_focus_v5_temp_2026_06_16",
        "purpose": "Component-specific diagnostics/fixes for display and 4027 after V4 user rejection.",
        "case_count": len(cases),
        "static_issue_cases": issue_cases,
        "cases": cases,
    }


def main() -> None:
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": summary["case_count"], "static_issue_cases": summary["static_issue_cases"], "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
