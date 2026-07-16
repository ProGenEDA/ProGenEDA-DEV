"""Generate focused probes for the one failing CDB V2 case.

User testing of CDB V2 reported every case worked except T05, which gave a DLL
error without crashing. T05 replaced U2 and U3 inside the full counter CDB
skeleton with misc shift-register rows. This pack isolates whether U2, U3,
pin rows, or property rows cause that failure.
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
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_cross_donor_cdb_v3_t05_isolation_temp_2026_06_10"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_CROSS_DONOR_CDB_V3_T05_ISOLATION_TEMP_2026_06_10.zip"


def load_cdb_v2_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_cdb_v2_for_t05", CDB_V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load CDB V2 helper from {CDB_V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cdb_v2 = load_cdb_v2_module()
cdb_v1 = cdb_v2.cdb_v1
iso_v2 = cdb_v2.iso_v2
base_iso = cdb_v2.base_iso


@dataclass(frozen=True)
class T05IsolationCase:
    case_id: str
    description: str
    replacement_sources: tuple[tuple[str, str], ...] = ()
    replace_pins: bool = True
    replace_properties: bool = True


def case(
    case_id: str,
    description: str,
    replacement_sources=(),
    *,
    replace_pins: bool = True,
    replace_properties: bool = True,
) -> T05IsolationCase:
    return T05IsolationCase(
        case_id=case_id,
        description=description,
        replacement_sources=tuple(replacement_sources),
        replace_pins=replace_pins,
        replace_properties=replace_properties,
    )


U2 = (("misc_logic_analog", "U2"),)
U3 = (("misc_logic_analog", "U3"),)
U2_U3 = (("misc_logic_analog", "U2"), ("misc_logic_analog", "U3"))


CASES = (
    case(
        "T00_FULL_SEQ_CDB_CONTROL",
        "Known-good control: T02 shape with full counter donor CDB copied whole.",
    ),
    case(
        "T01_REPLACE_U2_FULL",
        "Replace only U2 pin and property rows with the misc 74HC595 row.",
        U2,
    ),
    case(
        "T02_REPLACE_U3_FULL",
        "Replace only U3 pin and property rows with the misc 74HC165 row.",
        U3,
    ),
    case(
        "T03_REPLACE_U2_U3_FULL",
        "Reproduce failing V2 T05: replace U2 and U3 pin/property rows.",
        U2_U3,
    ),
    case(
        "T04_REPLACE_U2_PROPERTIES",
        "Replace only U2 property row with the misc 74HC595 row.",
        U2,
        replace_pins=False,
    ),
    case(
        "T05_REPLACE_U2_PINS",
        "Replace only U2 pin row with the misc 74HC595 row.",
        U2,
        replace_properties=False,
    ),
    case(
        "T06_REPLACE_U3_PROPERTIES",
        "Replace only U3 property row with the misc 74HC165 row.",
        U3,
        replace_pins=False,
    ),
    case(
        "T07_REPLACE_U3_PINS",
        "Replace only U3 pin row with the misc 74HC165 row.",
        U3,
        replace_properties=False,
    ),
    case(
        "T08_REPLACE_U2_U3_PROPERTIES",
        "Replace only U2 and U3 property rows.",
        U2_U3,
        replace_pins=False,
    ),
    case(
        "T09_REPLACE_U2_U3_PINS",
        "Replace only U2 and U3 pin rows.",
        U2_U3,
        replace_properties=False,
    ),
    case(
        "T10_FULL_MISC_SKELETON_REPLACE_U4_U6_CONTROL",
        "Known-good opposite-direction control from V2 T01.",
    ),
)


def write_case(item: T05IsolationCase) -> dict[str, object]:
    case_dir = OUT_ROOT / item.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{item.case_id}.pdsprj"

    object_chunk, region_plan = base_iso.object_chunk_for(iso_v2.T02_SHAPE)
    header_donor_key = "seq_counters_all"
    if item.case_id == "T10_FULL_MISC_SKELETON_REPLACE_U4_U6_CONTROL":
        header_donor_key = "misc_logic_analog"
        cdb, cdb_row_plan = cdb_v2.build_full_skeleton_cdb(
            header_donor_key,
            cdb_v2.T02_REPLACE_MISC_SKELETON,
            replace_pins=True,
            replace_properties=True,
        )
        cdb_mode = "known_good_misc_skeleton_replacement"
    elif item.replacement_sources:
        cdb, cdb_row_plan = cdb_v2.build_full_skeleton_cdb(
            header_donor_key,
            item.replacement_sources,
            replace_pins=item.replace_pins,
            replace_properties=item.replace_properties,
        )
        cdb_mode = "full_counter_skeleton_t05_isolation"
    else:
        cdb, cdb_row_plan = base_iso.donor_cdb(header_donor_key), []
        cdb_mode = "full_header_donor"

    pointers, device_plan = base_iso.write_dsn(
        output,
        object_chunk=object_chunk,
        cdb=cdb,
        header_donor_key=header_donor_key,
        device_mode="full_multi",
        selections=iso_v2.T02_SHAPE,
    )
    dsn = base_iso.seq.read_internal_file(output, "ROOT.DSN")
    cdb = base_iso.seq.read_internal_file(output, "ROOT.CDB")
    chunk = base_iso.seq._extract_object_chunk(dsn)
    device_section = base_iso.seq._device_section(dsn)
    parsed = parse_cdb(cdb)
    manifest = {
        "case_id": item.case_id,
        "description": item.description,
        "method": "cross_donor_cdb_v2_t05_isolation",
        "status": "temporary_pending_user_proteus_testing",
        "header_donor_key": header_donor_key,
        "cdb_mode": cdb_mode,
        "replace_pins": item.replace_pins,
        "replace_properties": item.replace_properties,
        "device_mode": "full_multi",
        "expected_markers": ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
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
        "static_validation_issues": base_iso.static_issues(output, ("74HC595", "74HC165", "4017", "4020", "74HC4024")),
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
        "batch": "MIXED_IC_CROSS_DONOR_CDB_V3_T05_ISOLATION_TEMP_2026_06_10",
        "purpose": "Isolate the only failing CDB V2 full-skeleton case, T05.",
        "status": "temporary_pending_user_proteus_testing",
        "manual_result_basis": "CDB V2 full-skeleton pack: every case worked except T05, which gave a DLL error without crashing.",
        "testing_order": [
            "T00 is the known-good full counter CDB control.",
            "T01-T03 isolate full row replacement for U2, U3, and U2+U3.",
            "T04-T09 split the same replacement by property rows versus pin rows.",
            "T10 is the known-good opposite-direction misc skeleton replacement control.",
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
