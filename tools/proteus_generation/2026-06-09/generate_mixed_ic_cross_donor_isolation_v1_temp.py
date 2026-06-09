"""Generate stepwise isolation probes for failed cross-donor IC mixing.

V1/V2/V3 cross-donor packs all failed with the same user-visible pattern. That
means the broad metadata retries did not touch the real failing surface. This
pack deliberately changes one axis at a time:

- same-donor subset controls with full same-donor metadata;
- extra foreign CDB/device metadata without foreign visible objects;
- one small foreign visible-object insertion with either sparse or contiguous
  CDB rows;
- the same small insertion with different first-header donors.

The goal is to identify the first failing step, not to produce a final circuit.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
V3_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_v3_filtered_device_temp.py"
OUT_ROOT = REPO / "experiments" / "mixed_ic_cross_donor_isolation_v1_temp_2026_06_09"
ARCHIVE_PATH = REPO / "experiments" / "MIXED_IC_CROSS_DONOR_ISOLATION_V1_TEMP_2026_06_09.zip"


def load_v3_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_v3_for_isolation", V3_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load V3 helper from {V3_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v3 = load_v3_module()
v2 = v3.v2
v1 = v3.v1
seq = v3.seq
mixed = v3.mixed


@dataclass(frozen=True)
class IsolationCase:
    case_id: str
    description: str
    selections: tuple[object, ...]
    header_donor_key: str
    cdb_mode: str
    device_mode: str
    cdb_row_sources: tuple[tuple[str, str], ...] = ()
    expected_markers: tuple[str, ...] = ()


def refs_in(data: bytes) -> list[str]:
    return sorted(set(match.group().decode("ascii") for match in re.finditer(rb"U\d+", data)), key=lambda item: int(item[1:]))


def donor_dsn(donor_key: str) -> bytes:
    return seq.read_internal_file(v1.donor_by_key(donor_key).path, "ROOT.DSN")


def donor_cdb(donor_key: str) -> bytes:
    return seq.read_internal_file(v1.donor_by_key(donor_key).path, "ROOT.CDB")


def object_chunk_for(selections: tuple[object, ...]) -> tuple[bytes, list[dict[str, object]]]:
    fragments: list[bytes] = []
    region_plan: list[dict[str, object]] = []
    for selection in selections:
        selected, metadata = v1.selected_fragments(selection)
        fragments.extend(selected)
        region_plan.extend(metadata)
    return b"\x00" + b"".join(fragments) + b"\xff", region_plan


def build_cdb_from_sources(header_donor_key: str, row_sources: tuple[tuple[str, str], ...]) -> tuple[bytes, list[dict[str, object]]]:
    if not row_sources:
        return donor_cdb(header_donor_key), []
    if len({ref for _donor_key, ref in row_sources}) != len(row_sources):
        raise ValueError(f"Duplicate CDB refs in isolation row plan: {row_sources}")

    parts_by_donor = {
        donor_key: v1.cdb_parts(donor_cdb(donor_key))
        for donor_key, _ref in row_sources
    }
    header_parts = v1.cdb_parts(donor_cdb(header_donor_key))
    header = bytearray(header_parts.header)
    if len(header) <= 92:
        raise ValueError("CDB header is too short for the observed count byte.")
    header[92] = len(row_sources)

    ordered_sources = sorted(row_sources, key=lambda item: int(item[1][1:]))
    pin_rows: list[bytes] = []
    prop_rows: list[bytes] = []
    row_plan: list[dict[str, object]] = []
    for donor_key, ref in ordered_sources:
        parts = parts_by_donor[donor_key]
        if ref not in parts.pin_rows or ref not in parts.prop_rows:
            raise ValueError(f"{donor_key} ROOT.CDB does not contain {ref}")
        pin_rows.append(parts.pin_rows[ref])
        prop_rows.append(parts.prop_rows[ref])
        row_plan.append(
            {
                "donor_key": donor_key,
                "ref": ref,
                "pin_row_size": len(parts.pin_rows[ref]),
                "prop_row_size": len(parts.prop_rows[ref]),
            }
        )
    return bytes(header) + b"".join(pin_rows) + header_parts.post_pin_header + b"".join(prop_rows), row_plan


def filtered_device_section_for(selections: tuple[object, ...]) -> tuple[bytes, list[dict[str, object]]]:
    fake_case = type("FakeCase", (), {"selections": selections})()
    return v3.build_filtered_device_section(fake_case)


def write_dsn(
    output: Path,
    *,
    object_chunk: bytes,
    cdb: bytes,
    header_donor_key: str,
    device_mode: str,
    selections: tuple[object, ...],
) -> tuple[dict[str, object], list[dict[str, object]]]:
    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = seq.read_internal_file(base.path, "ROOT.DSN")
    header_dsn = donor_dsn(header_donor_key)
    device_plan: list[dict[str, object]] = []

    if device_mode == "full_header_donor":
        dsn, pointers = seq.build_dsn_with_device_section(base_dsn, header_dsn, object_chunk, seq._device_section(header_dsn))
    elif device_mode == "filtered_visible":
        device_section, device_plan = filtered_device_section_for(selections)
        dsn, pointers = seq.build_dsn_with_device_section(base_dsn, header_dsn, object_chunk, device_section)
    elif device_mode == "full_multi":
        sections = v2.device_sections_for(selections)
        dsn, pointers = v2.build_dsn_with_multi_device_sections(base_dsn, header_dsn, object_chunk, sections)
        device_plan = [
            {
                "donor_key": item["donor_key"],
                "size": item["size"],
                "old_tail_pointer": item["old_tail_pointer"],
            }
            for item in sections
        ]
    else:
        raise ValueError(f"Unknown device mode {device_mode!r}")

    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )
    return pointers, device_plan


def static_issues(output: Path, expected_markers: tuple[str, ...]) -> list[str]:
    issues: list[str] = []
    info = seq.inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("isolation IC object chunk should use only $TERBIDIR visible pin terminals")
    if chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    chunk_refs = set(refs_in(chunk))
    cdb_refs = set(refs_in(cdb))
    missing_refs = sorted(chunk_refs - cdb_refs, key=lambda item: int(item[1:]))
    if missing_refs:
        issues.append(f"visible object refs missing from CDB: {missing_refs}")
    for marker in expected_markers:
        raw = marker.encode("ascii")
        if raw not in chunk:
            issues.append(f"expected DSN marker {marker} missing")
        if raw not in cdb:
            issues.append(f"expected CDB marker {marker} missing")
    return issues


def write_case(case: IsolationCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    object_chunk, region_plan = object_chunk_for(case.selections)
    if case.cdb_mode == "full_header_donor":
        cdb, cdb_row_plan = donor_cdb(case.header_donor_key), []
    elif case.cdb_mode == "row_sources":
        cdb, cdb_row_plan = build_cdb_from_sources(case.header_donor_key, case.cdb_row_sources)
    else:
        raise ValueError(f"Unknown CDB mode {case.cdb_mode!r}")

    pointers, device_plan = write_dsn(
        output,
        object_chunk=object_chunk,
        cdb=cdb,
        header_donor_key=case.header_donor_key,
        device_mode=case.device_mode,
        selections=case.selections,
    )
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    device_section = seq._device_section(dsn)
    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "method": "cross_donor_stepwise_isolation",
        "status": "temporary_pending_user_proteus_testing",
        "header_donor_key": case.header_donor_key,
        "cdb_mode": case.cdb_mode,
        "device_mode": case.device_mode,
        "selections": [
            {
                "donor_key": selection.donor_key,
                "markers": selection.markers,
                "cdb_refs": selection.cdb_refs,
                "label_prefix": selection.label_prefix,
            }
            for selection in case.selections
        ],
        "expected_markers": case.expected_markers,
        "region_plan": region_plan,
        "cdb_row_plan": cdb_row_plan,
        "device_plan": device_plan,
        "section_pointers": pointers,
        "object_refs": refs_in(chunk),
        "cdb_refs": refs_in(cdb),
        "object_ref_subset_of_cdb": set(refs_in(chunk)).issubset(set(refs_in(cdb))),
        "marker_counts": mixed.marker_counts(chunk) | {"7447": chunk.count(b"7447")},
        "cdb_marker_counts": mixed.marker_counts(cdb) | {"7447": cdb.count(b"7447")},
        "object_chunk_size": len(chunk),
        "device_section_size": len(device_section),
        "static_validation_issues": static_issues(output, case.expected_markers),
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
            "device_section": seq._sha256_bytes(device_section),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(seq.bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


MISC_SHIFT = v1.RegionSelection("misc_logic_analog", ("74HC595", "74HC165"), ("U2", "U3"), "A")
SEQ_DIVIDERS = v1.RegionSelection("seq_counters_all", ("4017", "4020", "74HC4024"), ("U4", "U5", "U6"), "B")
MISC_7447 = v1.RegionSelection("misc_logic_analog", ("7447",), ("U4",), "C")
SEQ_SYNC = v1.RegionSelection("seq_counters_all", ("74HC160", "74HC161", "74HC163"), ("U12", "U13", "U14"), "D")


CASES: tuple[IsolationCase, ...] = (
    IsolationCase(
        "T00_MISC_SHIFT_SUBSET_FULL_MISC_METADATA",
        "Control: 74HC595 + 74HC165 subset from the misc donor with full misc CDB/device metadata.",
        (MISC_SHIFT,),
        "misc_logic_analog",
        "full_header_donor",
        "full_header_donor",
        expected_markers=("74HC595", "74HC165"),
    ),
    IsolationCase(
        "T01_SEQ_DIVIDER_SUBSET_FULL_SEQ_METADATA",
        "Control: 4017 + 4020 + 74HC4024 subset from the counter donor with full counter CDB/device metadata.",
        (SEQ_DIVIDERS,),
        "seq_counters_all",
        "full_header_donor",
        "full_header_donor",
        expected_markers=("4017", "4020", "74HC4024"),
    ),
    IsolationCase(
        "T02_MISC_SHIFT_WITH_FOREIGN_DEVICE_ONLY",
        "T02-shape visible mix with full misc CDB only, but full multi donor device sections.",
        (MISC_SHIFT, SEQ_DIVIDERS),
        "misc_logic_analog",
        "full_header_donor",
        "full_multi",
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    IsolationCase(
        "T03_MISC_SHIFT_WITH_FOREIGN_CDB_ONLY",
        "No foreign device-section filtering: T02 visible mix but sparse cross CDB and only misc device metadata.",
        (MISC_SHIFT, SEQ_DIVIDERS),
        "misc_logic_analog",
        "row_sources",
        "full_header_donor",
        (("misc_logic_analog", "U2"), ("misc_logic_analog", "U3"), ("seq_counters_all", "U4"), ("seq_counters_all", "U5"), ("seq_counters_all", "U6")),
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    IsolationCase(
        "T04_T02_SPARSE_CDB_FILTERED_DEVICE_HEADER_MISC",
        "Small cross visible mix matching failed T02 shape: sparse U2-U6 CDB, filtered visible device definitions, misc first header.",
        (MISC_SHIFT, SEQ_DIVIDERS),
        "misc_logic_analog",
        "row_sources",
        "filtered_visible",
        (("misc_logic_analog", "U2"), ("misc_logic_analog", "U3"), ("seq_counters_all", "U4"), ("seq_counters_all", "U5"), ("seq_counters_all", "U6")),
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    IsolationCase(
        "T05_T02_CONTIGUOUS_CDB_FILTERED_DEVICE_HEADER_MISC",
        "Same T02 visible mix, but CDB is contiguous U1-U7 with foreign U4-U6 rows replacing misc rows.",
        (MISC_SHIFT, SEQ_DIVIDERS),
        "misc_logic_analog",
        "row_sources",
        "filtered_visible",
        (
            ("misc_logic_analog", "U1"),
            ("misc_logic_analog", "U2"),
            ("misc_logic_analog", "U3"),
            ("seq_counters_all", "U4"),
            ("seq_counters_all", "U5"),
            ("seq_counters_all", "U6"),
            ("misc_logic_analog", "U7"),
        ),
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    IsolationCase(
        "T06_T02_CONTIGUOUS_CDB_FILTERED_DEVICE_HEADER_SEQ",
        "Same T02 visible mix and contiguous CDB, but use the counter donor first-header bytes.",
        (MISC_SHIFT, SEQ_DIVIDERS),
        "seq_counters_all",
        "row_sources",
        "filtered_visible",
        (
            ("misc_logic_analog", "U1"),
            ("misc_logic_analog", "U2"),
            ("misc_logic_analog", "U3"),
            ("seq_counters_all", "U4"),
            ("seq_counters_all", "U5"),
            ("seq_counters_all", "U6"),
            ("misc_logic_analog", "U7"),
        ),
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    IsolationCase(
        "T07_T04_SPARSE_CDB_FILTERED_DEVICE_HEADER_MISC",
        "Small 7447 plus sync-counter mix matching failed T04 shape: sparse U4/U12/U13/U14 CDB.",
        (MISC_7447, SEQ_SYNC),
        "misc_logic_analog",
        "row_sources",
        "filtered_visible",
        (("misc_logic_analog", "U4"), ("seq_counters_all", "U12"), ("seq_counters_all", "U13"), ("seq_counters_all", "U14")),
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
    IsolationCase(
        "T08_T04_CONTIGUOUS_CDB_FILTERED_DEVICE_HEADER_SEQ",
        "Same T04 visible mix, but CDB is contiguous U1-U14 and the counter donor provides first-header bytes.",
        (MISC_7447, SEQ_SYNC),
        "seq_counters_all",
        "row_sources",
        "filtered_visible",
        (
            ("seq_counters_all", "U1"),
            ("seq_counters_all", "U2"),
            ("seq_counters_all", "U3"),
            ("misc_logic_analog", "U4"),
            ("seq_counters_all", "U5"),
            ("seq_counters_all", "U6"),
            ("seq_counters_all", "U7"),
            ("seq_counters_all", "U8"),
            ("seq_counters_all", "U9"),
            ("seq_counters_all", "U10"),
            ("seq_counters_all", "U11"),
            ("seq_counters_all", "U12"),
            ("seq_counters_all", "U13"),
            ("seq_counters_all", "U14"),
        ),
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
    IsolationCase(
        "T09_T04_CONTIGUOUS_CDB_FULL_MULTI_HEADER_SEQ",
        "Same T04 visible mix and contiguous CDB, but keep full donor device sections instead of filtered device definitions.",
        (MISC_7447, SEQ_SYNC),
        "seq_counters_all",
        "row_sources",
        "full_multi",
        (
            ("seq_counters_all", "U1"),
            ("seq_counters_all", "U2"),
            ("seq_counters_all", "U3"),
            ("misc_logic_analog", "U4"),
            ("seq_counters_all", "U5"),
            ("seq_counters_all", "U6"),
            ("seq_counters_all", "U7"),
            ("seq_counters_all", "U8"),
            ("seq_counters_all", "U9"),
            ("seq_counters_all", "U10"),
            ("seq_counters_all", "U11"),
            ("seq_counters_all", "U12"),
            ("seq_counters_all", "U13"),
            ("seq_counters_all", "U14"),
        ),
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
)


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
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    previous_ref_audit = {}
    for case in v1.CASES:
        object_chunk, _region_plan = object_chunk_for(case.selections)
        cdb, _row_plan = v2.build_cross_cdb_sorted(case.selections)
        previous_ref_audit[case.case_id] = {
            "object_refs": refs_in(object_chunk),
            "cdb_refs": refs_in(cdb),
            "object_ref_subset_of_cdb": set(refs_in(object_chunk)).issubset(set(refs_in(cdb))),
            "missing_from_cdb": sorted(set(refs_in(object_chunk)) - set(refs_in(cdb)), key=lambda item: int(item[1:])),
        }
    (OUT_ROOT / "previous_v1_v2_v3_ref_audit.json").write_text(json.dumps(previous_ref_audit, indent=2) + "\n", encoding="utf-8")

    manifests = [write_case(case) for case in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_CROSS_DONOR_ISOLATION_V1_TEMP_2026_06_09",
        "purpose": "Pinpoint the first failing section after V1/V2/V3 all reproduced the same cross-donor failure pattern.",
        "status": "temporary_pending_user_proteus_testing",
        "testing_order": [
            "T00 and T01 should pass. If not, fragment extraction is bad.",
            "T02 and T03 intentionally keep one incomplete metadata side to show whether the loader fails as soon as the foreign visible object appears.",
            "T04 through T06 isolate sparse-vs-contiguous CDB and first-header donor for the failed T02 shape.",
            "T07 through T09 isolate the failed T04 shape with sparse/contiguous CDB and filtered/full device metadata.",
        ],
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "previous_ref_audit": "previous_v1_v2_v3_ref_audit.json",
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
