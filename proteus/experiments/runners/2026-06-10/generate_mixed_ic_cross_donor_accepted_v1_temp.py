"""Generate practical cross-donor mixed IC projects with the accepted CDB policy.

This pack continues after MIXED_IC_CROSS_DONOR_CDB_V3_T05_ISOLATION passed
user Proteus testing. It avoids the rejected reduced-CDB path and emits:

- full donor device sections for every involved donor family;
- one complete donor ROOT.CDB skeleton;
- parser-built row replacement inside that full skeleton only.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import parse_cdb


REPO = Path(__file__).resolve().parents[4]
CDB_V2_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-10" / "generate_mixed_ic_cross_donor_cdb_v2_full_skeleton_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_cross_donor_accepted_v1_temp_2026_06_10"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_CROSS_DONOR_ACCEPTED_V1_TEMP_2026_06_10.zip"


def load_cdb_v2_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_cdb_v2_for_accepted_v1", CDB_V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load CDB V2 helper from {CDB_V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cdb_v2 = load_cdb_v2_module()
base_iso = cdb_v2.base_iso
RegionSelection = base_iso.v1.RegionSelection


@dataclass(frozen=True)
class AcceptedMixCase:
    case_id: str
    description: str
    selections: tuple[object, ...]
    header_donor_key: str
    expected_markers: tuple[str, ...]
    replacement_sources: tuple[tuple[str, str], ...] = ()


def sel(
    donor_key: str,
    markers: tuple[str, ...],
    cdb_refs: tuple[str, ...],
    label_prefix: str,
) -> object:
    return RegionSelection(donor_key, markers, cdb_refs, label_prefix)


MISC_SHIFT = sel("misc_logic_analog", ("74HC595", "74HC165"), ("U2", "U3"), "A")
MISC_SHIFT_U3 = sel("misc_logic_analog", ("74HC165",), ("U3",), "L")
MISC_DECODER = sel("misc_logic_analog", ("7447",), ("U4",), "B")
MISC_COMPUTE_U3_U6 = sel("misc_logic_analog", ("74HC165", "7447", "74HC283"), ("U3", "U4", "U6"), "C")
MISC_COMPUTE_U4_U6 = sel("misc_logic_analog", ("7447", "74HC283"), ("U4", "U6"), "D")
MISC_COMPUTE_U2_U6 = sel("misc_logic_analog", ("74HC595", "74HC165", "7447", "74HC283"), ("U2", "U3", "U4", "U6"), "E")
MISC_LOGIC_CONTROL_U2_U7 = sel("misc_logic_analog", ("74HC595", "74HC165", "7447", "74HC283", "74HC85"), ("U2", "U3", "U4", "U6", "U7"), "F")

SEQ_UPDOWN_PAIR = sel("seq_counters_all", ("74HC193", "74HC192"), ("U2", "U1"), "G")
SEQ_DIVIDERS = sel("seq_counters_all", ("4017", "4020", "74HC4024"), ("U4", "U5", "U6"), "H")
SEQ_LATE_COUNTERS = sel("seq_counters_all", ("4518", "74HC4060", "74HC4040", "7490", "74HC160", "74HC161", "74HC163"), ("U8", "U9", "U10", "U11", "U12", "U13", "U14"), "J")
SEQ_SYNC = sel("seq_counters_all", ("74HC160", "74HC161", "74HC163"), ("U12", "U13", "U14"), "K")


def replacements_for(header_donor_key: str, selections: tuple[object, ...]) -> tuple[tuple[str, str], ...]:
    replacements: list[tuple[str, str]] = []
    for selection in selections:
        if selection.donor_key == header_donor_key:
            continue
        for ref in selection.cdb_refs:
            replacements.append((selection.donor_key, ref))
    return tuple(replacements)


def accepted_case(
    case_id: str,
    description: str,
    selections: tuple[object, ...],
    header_donor_key: str,
    expected_markers: tuple[str, ...],
) -> AcceptedMixCase:
    return AcceptedMixCase(
        case_id=case_id,
        description=description,
        selections=selections,
        header_donor_key=header_donor_key,
        expected_markers=expected_markers,
        replacement_sources=replacements_for(header_donor_key, selections),
    )


CASES: tuple[AcceptedMixCase, ...] = (
    accepted_case(
        "T01_SHIFT_REGISTERS_WITH_DIVIDERS",
        "Accepted control shape: 74HC595/74HC165 with 4017/4020/74HC4024.",
        (MISC_SHIFT, SEQ_DIVIDERS),
        "misc_logic_analog",
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    accepted_case(
        "T02_DECODER_WITH_SYNC_COUNTERS",
        "Accepted control shape: 7447 decoder/driver with 74HC160/161/163.",
        (MISC_DECODER, SEQ_SYNC),
        "seq_counters_all",
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
    accepted_case(
        "T03_LARGE_MISC_COMPUTE_WITH_LATE_COUNTERS",
        "Larger no-ref-collision mix: shift/decoder/adder with late counter/divider families.",
        (MISC_COMPUTE_U2_U6, SEQ_LATE_COUNTERS),
        "seq_counters_all",
        (
            "74HC595",
            "74HC165",
            "7447",
            "74HC283",
            "4518",
            "74HC4060",
            "74HC4040",
            "7490",
            "74HC160",
            "74HC161",
            "74HC163",
        ),
    ),
    accepted_case(
        "T04_UPDOWN_PAIR_WITH_MISC_COMPUTE",
        "74HC192/74HC193 up/down pair with shift input, 7447, and adder regions.",
        (SEQ_UPDOWN_PAIR, MISC_COMPUTE_U3_U6),
        "seq_counters_all",
        ("74HC193", "74HC192", "74HC165", "7447", "74HC283"),
    ),
    accepted_case(
        "T05_DIVIDERS_WITH_SHIFT_SEQ_SKELETON",
        "Same visible family mix as T01 but using the counter CDB skeleton and replacing U2/U3.",
        (MISC_SHIFT, SEQ_DIVIDERS),
        "seq_counters_all",
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    accepted_case(
        "T06_UPDOWN_DIVIDERS_WITH_SHIFT_INPUT",
        "74HC192/193 plus 4017/4020/74HC4024 with a foreign 74HC165 input region.",
        (SEQ_UPDOWN_PAIR, MISC_SHIFT_U3, SEQ_DIVIDERS),
        "seq_counters_all",
        (
            "74HC193",
            "74HC192",
            "74HC165",
            "4017",
            "4020",
            "74HC4024",
        ),
    ),
    AcceptedMixCase(
        "T07_MISC_LOGIC_CONTROL",
        "Same-donor control with the complete misc logic/decoder/compute/comparator set.",
        (MISC_LOGIC_CONTROL_U2_U7,),
        "misc_logic_analog",
        ("74HC595", "74HC165", "7447", "74HC283", "74HC85"),
    ),
    AcceptedMixCase(
        "T08_SEQ_LATE_COUNTERS_CONTROL",
        "Same-donor control with the later counter/divider families only.",
        (SEQ_LATE_COUNTERS,),
        "seq_counters_all",
        ("4518", "74HC4060", "74HC4040", "7490", "74HC160", "74HC161", "74HC163"),
    ),
)


def cdb_for_case(item: AcceptedMixCase) -> tuple[bytes, list[dict[str, object]], str]:
    if not item.replacement_sources:
        return base_iso.donor_cdb(item.header_donor_key), [], "full_header_donor"
    cdb, row_plan = cdb_v2.build_full_skeleton_cdb(
        item.header_donor_key,
        item.replacement_sources,
        replace_pins=True,
        replace_properties=True,
    )
    return cdb, row_plan, "accepted_full_skeleton_replaced_rows"


def write_case(item: AcceptedMixCase) -> dict[str, object]:
    case_dir = OUT_ROOT / item.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{item.case_id}.pdsprj"

    object_chunk, region_plan = base_iso.object_chunk_for(item.selections)
    cdb, cdb_row_plan, cdb_mode = cdb_for_case(item)
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
        "method": "accepted_cross_donor_full_device_sections_full_cdb_skeleton_replacement",
        "status": "temporary_pending_user_proteus_testing",
        "header_donor_key": item.header_donor_key,
        "cdb_mode": cdb_mode,
        "replacement_sources": item.replacement_sources,
        "replace_pins": True,
        "replace_properties": True,
        "device_mode": "full_multi",
        "terminal_policy": "donor-native bidirectional terminals with topology-preserving unique labels",
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
        "batch": "MIXED_IC_CROSS_DONOR_ACCEPTED_V1_TEMP_2026_06_10",
        "purpose": "Generate practical mixed sequential/misc IC combinations using the accepted full-skeleton CDB route.",
        "status": "temporary_pending_user_proteus_testing",
        "policy_basis": [
            "Use full donor device sections for every involved donor.",
            "Use a complete donor ROOT.CDB skeleton.",
            "Replace selected same-ref rows inside that full skeleton only.",
            "Avoid duplicate visible U references across donor selections.",
        ],
        "testing_order": [
            "T01-T02 are accepted control shapes.",
            "T03-T06 are practical cross-donor expansions with unique refs.",
            "T07-T08 are same-donor controls for the involved region families.",
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
