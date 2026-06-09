"""Generate corrected ROOT.CDB synthesis probes for cross-donor IC mixes.

Earlier generated-CDB probes used ad hoc string slices and invalid row
boundaries. This pack uses the shared CDB parser/builder so we can isolate the
next real question: whether Proteus accepts correctly sliced donor rows as-is,
or whether row ordinal fields must be normalized to the emitted row order.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import (
    CdbFile,
    CdbPinRow,
    CdbPropertyRow,
    build_cdb_from_rows,
    package_ref,
    parse_cdb,
    _read_lp_ascii,
    _read_u32,
    _skip_lp_ascii,
)


REPO = Path(__file__).resolve().parents[3]
ISO_V2_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_isolation_v2_full_device_cdb_temp.py"
OUT_ROOT = REPO / "experiments" / "mixed_ic_cross_donor_cdb_v1_correct_rows_temp_2026_06_09"
ARCHIVE_PATH = REPO / "experiments" / "MIXED_IC_CROSS_DONOR_CDB_V1_CORRECT_ROWS_TEMP_2026_06_09.zip"


def load_iso_v2_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_isolation_v2_for_cdb_v1", ISO_V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load isolation V2 helper from {ISO_V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


iso = load_iso_v2_module()
base_iso = iso.iso


@dataclass(frozen=True)
class CorrectCdbCase:
    case_id: str
    description: str
    selections: tuple[object, ...]
    header_donor_key: str
    cdb_mode: str
    cdb_row_sources: tuple[tuple[str, str], ...] = ()
    renumber_rows: bool = False
    expected_markers: tuple[str, ...] = ()


@lru_cache(maxsize=None)
def parsed_cdb(donor_key: str) -> CdbFile:
    return parse_cdb(base_iso.donor_cdb(donor_key))


def _u32_at(row: bytes, offset: int) -> int:
    return int.from_bytes(row[offset : offset + 4], "little", signed=False)


def _set_u32(row: bytearray, offset: int, value: int) -> None:
    row[offset : offset + 4] = value.to_bytes(4, "little", signed=False)


def _pin_row_for(cdb: CdbFile, ref: str) -> CdbPinRow:
    by_ref = cdb.pin_by_ref()
    if ref in by_ref:
        return by_ref[ref]
    matches = [row for row in cdb.pin_rows if package_ref(row.ref) == package_ref(ref)]
    if len(matches) != 1:
        raise ValueError(f"Could not uniquely resolve CDB pin row for {ref!r}; matches={len(matches)}")
    return matches[0]


def _property_row_for(cdb: CdbFile, ref: str) -> CdbPropertyRow:
    by_ref = cdb.property_by_ref()
    key = package_ref(ref)
    if key in by_ref:
        return by_ref[key]
    raise ValueError(f"Could not resolve CDB property row for {ref!r}")


def _renumber_pin_row(row: CdbPinRow, ordinal: int) -> CdbPinRow:
    data = bytearray(row.data)
    _set_u32(data, 0, ordinal)
    _set_u32(data, 12, ordinal)
    _set_u32(data, len(data) - 8, ordinal)
    return CdbPinRow(ref=row.ref, data=bytes(data))


def _renumber_property_row(row: CdbPropertyRow, ordinal: int) -> CdbPropertyRow:
    data = bytearray(row.data)
    _set_u32(data, 0, ordinal)
    return CdbPropertyRow(ref=row.ref, data=bytes(data))


def _property_row_expected_end(row: bytes) -> int:
    pos = 20
    _ref, pos = _read_lp_ascii(row, pos)
    for _field_index in range(3):
        pos = _skip_lp_ascii(row, pos)
    property_length = _read_u32(row, pos)
    return pos + 4 + property_length


def _adapt_property_row_position(row: CdbPropertyRow, *, is_last: bool) -> CdbPropertyRow:
    expected_end = _property_row_expected_end(row.data)
    actual_end = len(row.data)
    if is_last:
        if expected_end == actual_end:
            return row
        if expected_end == actual_end + 4:
            return CdbPropertyRow(ref=row.ref, data=row.data + b"\x00\x00\x00\x00")
    else:
        if expected_end == actual_end + 4:
            return row
        if expected_end == actual_end and actual_end >= 4:
            return CdbPropertyRow(ref=row.ref, data=row.data[:-4])
    raise ValueError(
        f"Unsupported CDB property row overlap for {row.ref}: "
        f"expected_end={expected_end}, actual_end={actual_end}, is_last={is_last}"
    )


def build_correct_cdb(
    header_donor_key: str,
    row_sources: tuple[tuple[str, str], ...],
    *,
    renumber_rows: bool,
) -> tuple[bytes, list[dict[str, object]]]:
    if not row_sources:
        return base_iso.donor_cdb(header_donor_key), []
    if len({package_ref(ref) for _donor_key, ref in row_sources}) != len(row_sources):
        raise ValueError(f"Duplicate CDB package refs in row plan: {row_sources}")

    template = parsed_cdb(header_donor_key)
    rows: list[tuple[str, CdbPinRow, CdbPropertyRow]] = []
    row_plan: list[dict[str, object]] = []
    for ordinal, (donor_key, ref) in enumerate(row_sources, start=1):
        donor = parsed_cdb(donor_key)
        pin = _pin_row_for(donor, ref)
        prop = _property_row_for(donor, ref)
        source_property_size = len(prop.data)
        prop = _adapt_property_row_position(prop, is_last=ordinal == len(row_sources))
        source_pin_ordinal = _u32_at(pin.data, 0)
        source_property_ordinal = _u32_at(prop.data, 0)
        if renumber_rows:
            pin = _renumber_pin_row(pin, ordinal)
            prop = _renumber_property_row(prop, ordinal)
        rows.append((ref, pin, prop))
        row_plan.append(
            {
                "donor_key": donor_key,
                "requested_ref": ref,
                "pin_ref": pin.ref,
                "property_ref": prop.ref,
                "source_pin_ordinal": source_pin_ordinal,
                "source_property_ordinal": source_property_ordinal,
                "emitted_ordinal": ordinal if renumber_rows else source_pin_ordinal,
                "renumbered": renumber_rows,
                "pin_row_size": len(pin.data),
                "source_property_row_size": source_property_size,
                "property_row_size": len(prop.data),
            }
        )
    return build_cdb_from_rows(template, rows), row_plan


def case(
    case_id: str,
    description: str,
    selections,
    header_donor_key: str,
    cdb_mode: str,
    cdb_row_sources=(),
    *,
    renumber_rows: bool = False,
    expected_markers=(),
) -> CorrectCdbCase:
    return CorrectCdbCase(
        case_id=case_id,
        description=description,
        selections=selections,
        header_donor_key=header_donor_key,
        cdb_mode=cdb_mode,
        cdb_row_sources=tuple(cdb_row_sources),
        renumber_rows=renumber_rows,
        expected_markers=tuple(expected_markers),
    )


CASES = (
    case(
        "T00_T02_SHAPE_FULL_MISC_CDB_CONTROL",
        "Control for the T02 visible shape: full multi device metadata plus complete misc donor CDB.",
        iso.T02_SHAPE,
        "misc_logic_analog",
        "full_header_donor",
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T01_T02_SPARSE_CORRECT_CDB_AS_IS",
        "T02 shape with correctly sliced sparse U2-U6 CDB rows, preserving donor row ordinals.",
        iso.T02_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T02_SPARSE,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T02_T02_CONTIGUOUS_CORRECT_CDB_AS_IS",
        "T02 shape with correctly sliced contiguous U1-U7 CDB rows, preserving donor row ordinals.",
        iso.T02_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T02_CONTIGUOUS,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T03_T02_CONTIGUOUS_CORRECT_CDB_SEQ_HEADER_AS_IS",
        "T02 shape with correctly sliced contiguous CDB rows and counter donor first-header bytes.",
        iso.T02_SHAPE,
        "seq_counters_all",
        "correct_rows",
        iso.T02_CONTIGUOUS,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T04_T02_SPARSE_CORRECT_CDB_RENUMBERED",
        "T02 shape with sparse U2-U6 CDB rows renumbered to emitted row order 1..5.",
        iso.T02_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T02_SPARSE,
        renumber_rows=True,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T05_T02_CONTIGUOUS_CORRECT_CDB_RENUMBERED",
        "T02 shape with contiguous U1-U7 CDB rows renumbered to emitted row order 1..7.",
        iso.T02_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T02_CONTIGUOUS,
        renumber_rows=True,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T06_T04_SHAPE_FULL_MISC_CDB_CONTROL",
        "Control for the T04 visible shape: 7447 plus sync counters with complete misc donor CDB.",
        iso.T04_SHAPE,
        "misc_logic_analog",
        "full_header_donor",
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T07_T04_SPARSE_CORRECT_CDB_AS_IS",
        "T04 shape with correctly sliced sparse U4/U12/U13/U14 CDB rows, preserving donor row ordinals.",
        iso.T04_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T04_SPARSE,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T08_T04_CONTIGUOUS_CORRECT_CDB_AS_IS",
        "T04 shape with correctly sliced contiguous U1-U14 CDB rows, preserving donor row ordinals.",
        iso.T04_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T04_CONTIGUOUS,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T09_T04_CONTIGUOUS_CORRECT_CDB_SEQ_HEADER_AS_IS",
        "T04 shape with correctly sliced contiguous CDB rows and counter donor first-header bytes.",
        iso.T04_SHAPE,
        "seq_counters_all",
        "correct_rows",
        iso.T04_CONTIGUOUS,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T10_T04_SPARSE_CORRECT_CDB_RENUMBERED",
        "T04 shape with sparse U4/U12/U13/U14 CDB rows renumbered to emitted row order 1..4.",
        iso.T04_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T04_SPARSE,
        renumber_rows=True,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T11_T04_CONTIGUOUS_CORRECT_CDB_RENUMBERED",
        "T04 shape with contiguous U1-U14 CDB rows renumbered to emitted row order 1..14.",
        iso.T04_SHAPE,
        "misc_logic_analog",
        "correct_rows",
        iso.T04_CONTIGUOUS,
        renumber_rows=True,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
)


def write_case(item: CorrectCdbCase) -> dict[str, object]:
    case_dir = OUT_ROOT / item.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{item.case_id}.pdsprj"

    object_chunk, region_plan = base_iso.object_chunk_for(item.selections)
    if item.cdb_mode == "full_header_donor":
        cdb, cdb_row_plan = base_iso.donor_cdb(item.header_donor_key), []
    elif item.cdb_mode == "correct_rows":
        cdb, cdb_row_plan = build_correct_cdb(
            item.header_donor_key,
            item.cdb_row_sources,
            renumber_rows=item.renumber_rows,
        )
    else:
        raise ValueError(f"Unknown CDB mode {item.cdb_mode!r}")

    pointers, device_plan = base_iso.write_dsn(
        output,
        object_chunk=object_chunk,
        cdb=cdb,
        header_donor_key=item.header_donor_key,
        device_mode="full_multi",
        selections=item.selections,
    )
    dsn = base_iso.seq.read_internal_file(output, "ROOT.DSN")
    cdb = base_iso.seq.read_internal_file(output, "ROOT.CDB")
    chunk = base_iso.seq._extract_object_chunk(dsn)
    device_section = base_iso.seq._device_section(dsn)
    parsed = parse_cdb(cdb)
    manifest = {
        "case_id": item.case_id,
        "description": item.description,
        "method": "cross_donor_correct_cdb_row_synthesis",
        "status": "temporary_pending_user_proteus_testing",
        "header_donor_key": item.header_donor_key,
        "cdb_mode": item.cdb_mode,
        "renumber_rows": item.renumber_rows,
        "device_mode": "full_multi",
        "selections": [
            {
                "donor_key": selection.donor_key,
                "markers": selection.markers,
                "cdb_refs": selection.cdb_refs,
                "label_prefix": selection.label_prefix,
            }
            for selection in item.selections
        ],
        "expected_markers": item.expected_markers,
        "region_plan": region_plan,
        "cdb_row_plan": cdb_row_plan,
        "parsed_cdb": {
            "count": parsed.count,
            "pin_refs": [row.ref for row in parsed.pin_rows],
            "property_refs": [row.ref for row in parsed.property_rows],
        },
        "device_plan": device_plan,
        "section_pointers": pointers,
        "object_refs": base_iso.refs_in(chunk),
        "cdb_refs": base_iso.refs_in(cdb),
        "object_ref_subset_of_cdb": set(base_iso.refs_in(chunk)).issubset(set(base_iso.refs_in(cdb))),
        "marker_counts": base_iso.mixed.marker_counts(chunk) | {"7447": chunk.count(b"7447")},
        "cdb_marker_counts": base_iso.mixed.marker_counts(cdb) | {"7447": cdb.count(b"7447")},
        "object_chunk_size": len(chunk),
        "device_section_size": len(device_section),
        "static_validation_issues": base_iso.static_issues(output, item.expected_markers),
        "output_hashes": {
            "project": base_iso.seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": base_iso.seq._sha256_bytes(dsn),
            "ROOT.CDB": base_iso.seq._sha256_bytes(cdb),
            "object_chunk": base_iso.seq._sha256_bytes(chunk),
            "device_section": base_iso.seq._sha256_bytes(device_section),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(base_iso.seq.bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 9, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return base_iso.seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    manifests = [write_case(item) for item in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_CROSS_DONOR_CDB_V1_CORRECT_ROWS_TEMP_2026_06_09",
        "purpose": "Use the decoded CDB parser/builder to test generated ROOT.CDB rows with and without row ordinal normalization.",
        "status": "temporary_pending_user_proteus_testing",
        "manual_result_basis": "Isolation V2 proved full donor CDB copies can open, while the old generated row-slice CDB crashes. This pack replaces the bad slicer.",
        "testing_order": [
            "T00 and T06 are full-CDB controls that should behave like the already passing V2 controls.",
            "T01-T03 and T07-T09 test correctly sliced generated rows with original donor ordinals.",
            "T04-T05 and T10-T11 test the same generated rows with internal CDB ordinals normalized to emitted row order.",
        ],
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "archive": str(ARCHIVE_PATH.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE_PATH),
                "archive_sha256": archive_hash,
                "static_issue_cases": summary_issues,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
