"""Generate full-skeleton ROOT.CDB replacement probes for cross-donor IC mixes.

The corrected reduced-CDB pack still crashed in Proteus except for full-CDB
controls. This pack keeps a complete donor CDB skeleton, count, and untouched
rows, then replaces selected matching refs inside that skeleton. It isolates
whether Proteus requires the full header-donor CDB row universe even when
individual rows are generated from other donors.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import CdbPinRow, CdbPropertyRow, build_cdb_from_rows, parse_cdb


REPO = Path(__file__).resolve().parents[3]
CDB_V1_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_cdb_v1_correct_rows_temp.py"
OUT_ROOT = REPO / "experiments" / "mixed_ic_cross_donor_cdb_v2_full_skeleton_temp_2026_06_10"
ARCHIVE_PATH = REPO / "experiments" / "MIXED_IC_CROSS_DONOR_CDB_V2_FULL_SKELETON_TEMP_2026_06_10.zip"


def load_cdb_v1_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_cdb_v1_for_v2", CDB_V1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load CDB V1 helper from {CDB_V1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cdb_v1 = load_cdb_v1_module()
iso_v2 = cdb_v1.iso
base_iso = cdb_v1.base_iso


@dataclass(frozen=True)
class FullSkeletonCase:
    case_id: str
    description: str
    selections: tuple[object, ...]
    header_donor_key: str
    replacement_sources: tuple[tuple[str, str], ...] = ()
    replace_pins: bool = True
    replace_properties: bool = True
    expected_markers: tuple[str, ...] = ()


def _property_for_position(row: CdbPropertyRow, *, is_last: bool) -> CdbPropertyRow:
    return cdb_v1._adapt_property_row_position(row, is_last=is_last)


def build_full_skeleton_cdb(
    header_donor_key: str,
    replacement_sources: tuple[tuple[str, str], ...],
    *,
    replace_pins: bool,
    replace_properties: bool,
) -> tuple[bytes, list[dict[str, object]]]:
    template = cdb_v1.parsed_cdb(header_donor_key)
    pins_by_ref = {row.ref: row for row in template.pin_rows}
    props_by_ref = {row.ref: row for row in template.property_rows}
    row_plan: list[dict[str, object]] = []

    for donor_key, ref in replacement_sources:
        donor = cdb_v1.parsed_cdb(donor_key)
        pin = cdb_v1._pin_row_for(donor, ref)
        prop = cdb_v1._property_row_for(donor, ref)
        if ref not in pins_by_ref and replace_pins:
            raise ValueError(f"Header donor {header_donor_key} has no pin row {ref} to replace.")
        if ref not in props_by_ref and replace_properties:
            raise ValueError(f"Header donor {header_donor_key} has no property row {ref} to replace.")
        if replace_pins:
            pins_by_ref[ref] = CdbPinRow(ref=ref, data=pin.data)
        if replace_properties:
            props_by_ref[ref] = CdbPropertyRow(ref=ref, data=prop.data)
        row_plan.append(
            {
                "ref": ref,
                "donor_key": donor_key,
                "replace_pins": replace_pins,
                "replace_properties": replace_properties,
                "source_pin_ref": pin.ref,
                "source_property_ref": prop.ref,
                "source_pin_size": len(pin.data),
                "source_property_size": len(prop.data),
            }
        )

    rows: list[tuple[str, CdbPinRow, CdbPropertyRow]] = []
    for index, pin in enumerate(template.pin_rows):
        ref = pin.ref
        prop_ref = cdb_v1.package_ref(ref)
        emitted_pin = pins_by_ref[ref]
        emitted_prop = _property_for_position(props_by_ref[prop_ref], is_last=index == len(template.pin_rows) - 1)
        rows.append((ref, emitted_pin, emitted_prop))
    return build_cdb_from_rows(template, rows), row_plan


def case(
    case_id: str,
    description: str,
    selections,
    header_donor_key: str,
    replacement_sources=(),
    *,
    replace_pins: bool = True,
    replace_properties: bool = True,
    expected_markers=(),
) -> FullSkeletonCase:
    return FullSkeletonCase(
        case_id=case_id,
        description=description,
        selections=selections,
        header_donor_key=header_donor_key,
        replacement_sources=tuple(replacement_sources),
        replace_pins=replace_pins,
        replace_properties=replace_properties,
        expected_markers=tuple(expected_markers),
    )


T02_REPLACE_MISC_SKELETON = (
    ("seq_counters_all", "U4"),
    ("seq_counters_all", "U5"),
    ("seq_counters_all", "U6"),
)
T02_REPLACE_SEQ_SKELETON = (
    ("misc_logic_analog", "U2"),
    ("misc_logic_analog", "U3"),
)
T04_REPLACE_SEQ_SKELETON = (("misc_logic_analog", "U4"),)


CASES = (
    case(
        "T00_T02_FULL_MISC_CDB_CONTROL",
        "Known-good control: T02 shape with full misc donor CDB copied whole.",
        iso_v2.T02_SHAPE,
        "misc_logic_analog",
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T01_T02_FULL_MISC_SKELETON_REPLACE_U4_U6_FULL",
        "Full misc CDB skeleton; replace U4/U5/U6 pin and property rows with counter rows.",
        iso_v2.T02_SHAPE,
        "misc_logic_analog",
        T02_REPLACE_MISC_SKELETON,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T02_T02_FULL_MISC_SKELETON_REPLACE_U4_U6_PROPERTIES",
        "Full misc CDB skeleton; replace only U4/U5/U6 property rows with counter rows.",
        iso_v2.T02_SHAPE,
        "misc_logic_analog",
        T02_REPLACE_MISC_SKELETON,
        replace_pins=False,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T03_T02_FULL_MISC_SKELETON_REPLACE_U4_U6_PINS",
        "Full misc CDB skeleton; replace only U4/U5/U6 pin rows with counter rows.",
        iso_v2.T02_SHAPE,
        "misc_logic_analog",
        T02_REPLACE_MISC_SKELETON,
        replace_properties=False,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T04_T02_FULL_SEQ_CDB_CONTROL",
        "Known-good-style control: T02 shape with full counter donor CDB copied whole.",
        iso_v2.T02_SHAPE,
        "seq_counters_all",
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T05_T02_FULL_SEQ_SKELETON_REPLACE_U2_U3_FULL",
        "Full counter CDB skeleton; replace U2/U3 pin and property rows with misc shift-register rows.",
        iso_v2.T02_SHAPE,
        "seq_counters_all",
        T02_REPLACE_SEQ_SKELETON,
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T06_T04_FULL_MISC_CDB_CONTROL",
        "Known-good control: T04 shape with full misc donor CDB copied whole.",
        iso_v2.T04_SHAPE,
        "misc_logic_analog",
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T07_T04_FULL_SEQ_CDB_CONTROL",
        "Known-good-style control: T04 shape with full counter donor CDB copied whole.",
        iso_v2.T04_SHAPE,
        "seq_counters_all",
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T08_T04_FULL_SEQ_SKELETON_REPLACE_U4_FULL",
        "Full counter CDB skeleton; replace U4 pin and property rows with the misc 7447 row.",
        iso_v2.T04_SHAPE,
        "seq_counters_all",
        T04_REPLACE_SEQ_SKELETON,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T09_T04_FULL_SEQ_SKELETON_REPLACE_U4_PROPERTIES",
        "Full counter CDB skeleton; replace only U4 property row with the misc 7447 row.",
        iso_v2.T04_SHAPE,
        "seq_counters_all",
        T04_REPLACE_SEQ_SKELETON,
        replace_pins=False,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T10_T04_FULL_SEQ_SKELETON_REPLACE_U4_PINS",
        "Full counter CDB skeleton; replace only U4 pin row with the misc 7447 row.",
        iso_v2.T04_SHAPE,
        "seq_counters_all",
        T04_REPLACE_SEQ_SKELETON,
        replace_properties=False,
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
)


def write_case(item: FullSkeletonCase) -> dict[str, object]:
    case_dir = OUT_ROOT / item.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{item.case_id}.pdsprj"

    object_chunk, region_plan = base_iso.object_chunk_for(item.selections)
    if item.replacement_sources:
        cdb, cdb_row_plan = build_full_skeleton_cdb(
            item.header_donor_key,
            item.replacement_sources,
            replace_pins=item.replace_pins,
            replace_properties=item.replace_properties,
        )
        cdb_mode = "full_skeleton_replaced_rows"
    else:
        cdb, cdb_row_plan = base_iso.donor_cdb(item.header_donor_key), []
        cdb_mode = "full_header_donor"

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
        "method": "cross_donor_full_cdb_skeleton_row_replacement",
        "status": "temporary_pending_user_proteus_testing",
        "header_donor_key": item.header_donor_key,
        "cdb_mode": cdb_mode,
        "replace_pins": item.replace_pins,
        "replace_properties": item.replace_properties,
        "device_mode": "full_multi",
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
                info.date_time = (2026, 6, 10, 0, 0, 0)
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
        "batch": "MIXED_IC_CROSS_DONOR_CDB_V2_FULL_SKELETON_TEMP_2026_06_10",
        "purpose": "Keep a full known-good donor CDB skeleton while replacing only selected rows, after reduced parser-built CDBs crashed.",
        "status": "temporary_pending_user_proteus_testing",
        "manual_result_basis": "CDB V1 correct-row pack: only T00 and T06 full-CDB controls worked; all reduced generated-CDB cases crashed.",
        "testing_order": [
            "T00/T04/T06/T07 are full-CDB controls.",
            "T01-T03 replace U4-U6 in the full misc skeleton for the T02 shape.",
            "T05 replaces U2-U3 in the full counter skeleton for the T02 shape.",
            "T08-T10 replace U4 in the full counter skeleton for the T04 shape.",
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
