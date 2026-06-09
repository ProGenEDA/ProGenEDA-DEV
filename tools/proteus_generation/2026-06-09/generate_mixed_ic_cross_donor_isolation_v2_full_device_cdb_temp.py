"""Generate CDB/header probes after isolation V1.

User testing of isolation V1 showed:

- T00/T01 same-donor subset controls worked;
- T02 cross-donor visible objects worked when full donor device sections were
  present, even with the misc donor CDB copied whole;
- T03 and onward crashed, so missing/filtered device metadata and/or generated
  cross-donor CDB rows are unsafe.

This V2 keeps full multi-donor device sections for every cross-donor case and
varies only CDB and first-header donor choices.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
ISO_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_isolation_v1_temp.py"
OUT_ROOT = REPO / "experiments" / "mixed_ic_cross_donor_isolation_v2_full_device_cdb_temp_2026_06_09"
ARCHIVE_PATH = REPO / "experiments" / "MIXED_IC_CROSS_DONOR_ISOLATION_V2_FULL_DEVICE_CDB_TEMP_2026_06_09.zip"


def load_iso_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_isolation_v1_for_v2", ISO_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load isolation V1 helper from {ISO_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


iso = load_iso_module()


def case(
    case_id: str,
    description: str,
    selections,
    header_donor_key: str,
    cdb_mode: str,
    cdb_row_sources=(),
    expected_markers=(),
):
    return iso.IsolationCase(
        case_id=case_id,
        description=description,
        selections=selections,
        header_donor_key=header_donor_key,
        cdb_mode=cdb_mode,
        device_mode="full_multi",
        cdb_row_sources=tuple(cdb_row_sources),
        expected_markers=tuple(expected_markers),
    )


T02_SHAPE = (iso.MISC_SHIFT, iso.SEQ_DIVIDERS)
T04_SHAPE = (iso.MISC_7447, iso.SEQ_SYNC)

T02_SPARSE = (
    ("misc_logic_analog", "U2"),
    ("misc_logic_analog", "U3"),
    ("seq_counters_all", "U4"),
    ("seq_counters_all", "U5"),
    ("seq_counters_all", "U6"),
)
T02_CONTIGUOUS = (
    ("misc_logic_analog", "U1"),
    ("misc_logic_analog", "U2"),
    ("misc_logic_analog", "U3"),
    ("seq_counters_all", "U4"),
    ("seq_counters_all", "U5"),
    ("seq_counters_all", "U6"),
    ("misc_logic_analog", "U7"),
)
T04_SPARSE = (
    ("misc_logic_analog", "U4"),
    ("seq_counters_all", "U12"),
    ("seq_counters_all", "U13"),
    ("seq_counters_all", "U14"),
)
T04_CONTIGUOUS = (
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
)


CASES = (
    case(
        "T00_T02_SHAPE_FULL_MISC_CDB_HEADER_MISC",
        "Known-good V1 T02 shape repeated: misc shift-registers plus dividers, full multi device metadata, full misc donor CDB.",
        T02_SHAPE,
        "misc_logic_analog",
        "full_header_donor",
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T01_T02_SHAPE_SPARSE_CDB_HEADER_MISC",
        "Same visible/device metadata as T00, but CDB is generated only from the five visible U2-U6 rows.",
        T02_SHAPE,
        "misc_logic_analog",
        "row_sources",
        T02_SPARSE,
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T02_T02_SHAPE_CONTIGUOUS_CDB_HEADER_MISC",
        "Same visible/device metadata as T00, but CDB is contiguous U1-U7 with U4-U6 from the counter donor.",
        T02_SHAPE,
        "misc_logic_analog",
        "row_sources",
        T02_CONTIGUOUS,
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T03_T02_SHAPE_FULL_SEQ_CDB_HEADER_SEQ",
        "Same T02 visible mix, but the counter donor provides first-header bytes and full CDB.",
        T02_SHAPE,
        "seq_counters_all",
        "full_header_donor",
        expected_markers=("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T04_T02_SHAPE_CONTIGUOUS_CDB_HEADER_SEQ",
        "Same T02 visible mix, but use counter first-header bytes with generated contiguous CDB.",
        T02_SHAPE,
        "seq_counters_all",
        "row_sources",
        T02_CONTIGUOUS,
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    case(
        "T05_7447_ONLY_FULL_MISC_METADATA",
        "Control: 7447 region alone from misc donor with full misc metadata.",
        (iso.MISC_7447,),
        "misc_logic_analog",
        "full_header_donor",
        expected_markers=("7447",),
    ),
    case(
        "T06_SYNC_COUNTERS_ONLY_FULL_SEQ_METADATA",
        "Control: 74HC160/161/163 regions alone from counter donor with full counter metadata.",
        (iso.SEQ_SYNC,),
        "seq_counters_all",
        "full_header_donor",
        expected_markers=("74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T07_T04_SHAPE_FULL_MISC_CDB_HEADER_MISC",
        "7447 plus sync counters, full multi device metadata, full misc donor CDB.",
        T04_SHAPE,
        "misc_logic_analog",
        "full_header_donor",
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T08_T04_SHAPE_SPARSE_CDB_HEADER_MISC",
        "Same T04 visible/device metadata as T07, but CDB only has U4/U12/U13/U14 visible rows.",
        T04_SHAPE,
        "misc_logic_analog",
        "row_sources",
        T04_SPARSE,
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T09_T04_SHAPE_CONTIGUOUS_CDB_HEADER_MISC",
        "Same T04 visible/device metadata as T07, but CDB is contiguous U1-U14 with U4 from misc donor.",
        T04_SHAPE,
        "misc_logic_analog",
        "row_sources",
        T04_CONTIGUOUS,
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T10_T04_SHAPE_FULL_SEQ_CDB_HEADER_SEQ",
        "Same T04 visible mix, but counter donor provides first-header bytes and full CDB.",
        T04_SHAPE,
        "seq_counters_all",
        "full_header_donor",
        expected_markers=("7447", "74HC160", "74HC161", "74HC163"),
    ),
    case(
        "T11_T04_SHAPE_CONTIGUOUS_CDB_HEADER_SEQ",
        "Same T04 visible mix, but use counter first-header bytes with generated contiguous CDB.",
        T04_SHAPE,
        "seq_counters_all",
        "row_sources",
        T04_CONTIGUOUS,
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
    return iso.seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    iso.OUT_ROOT = OUT_ROOT
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    manifests = [iso.write_case(item) for item in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_CROSS_DONOR_ISOLATION_V2_FULL_DEVICE_CDB_TEMP_2026_06_09",
        "purpose": "Keep full multi-donor device sections after V1 T02 worked, and isolate CDB/header choices.",
        "status": "temporary_pending_user_proteus_testing",
        "manual_v1_result_basis": "Isolation V1 T00/T01/T02 worked; T03 onward crashed before open.",
        "testing_order": [
            "T00 repeats the known-good T02 shape from V1.",
            "T01/T02 test whether generated sparse/contiguous CDB rows poison the otherwise-good T02 shape.",
            "T03/T04 test whether first-header donor bytes or full CDB donor choice matter for the same T02 shape.",
            "T05/T06 are same-donor controls for the T04 shape pieces.",
            "T07-T11 repeat the same CDB/header tests for the 7447 plus 74HC160/161/163 shape.",
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
