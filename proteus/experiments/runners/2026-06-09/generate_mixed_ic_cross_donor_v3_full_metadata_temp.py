"""Generate large cross-donor IC probes with full donor metadata.

Isolation V2 showed that every generated/stitched CDB variant crashed, while
complete donor CDB copies opened when full multi-donor device sections were
also preserved. This pack retries the original large V1 cross-donor shapes with
that newly observed safe metadata policy:

- whole visible IC regions from each donor;
- complete device sections from every involved donor;
- one complete ROOT.CDB copied from the first/header donor;
- no CDB row synthesis, trimming, sorting, or ref rewriting.
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
OUT_ROOT = REPO / "experiments" / "mixed_ic_cross_donor_v3_full_metadata_temp_2026_06_09"
ARCHIVE_PATH = REPO / "experiments" / "MIXED_IC_CROSS_DONOR_V3_FULL_METADATA_TEMP_2026_06_09.zip"


def load_iso_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_isolation_v1_for_full_metadata_v3", ISO_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load isolation helper from {ISO_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


iso = load_iso_module()


def full_metadata_case(cross_case):
    header_donor_key = cross_case.selections[0].donor_key
    return iso.IsolationCase(
        case_id=cross_case.case_id,
        description=(
            f"Full-metadata retry of original {cross_case.case_id}: "
            f"{cross_case.description}"
        ),
        selections=cross_case.selections,
        header_donor_key=header_donor_key,
        cdb_mode="full_header_donor",
        device_mode="full_multi",
        expected_markers=cross_case.expected_markers,
    )


CASES = tuple(full_metadata_case(item) for item in iso.v1.CASES)


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
        "batch": "MIXED_IC_CROSS_DONOR_V3_FULL_METADATA_TEMP_2026_06_09",
        "purpose": "Retry original large cross-donor IC shapes after isolation V2 proved full donor CDB copies work but generated CDB rows crash.",
        "status": "temporary_pending_user_proteus_testing",
        "metadata_policy": "complete first-donor ROOT.CDB plus complete device sections from every involved donor",
        "cdb_policy": "copy one donor ROOT.CDB whole; do not synthesize, trim, sort, or rewrite CDB rows",
        "device_policy": "preserve complete donor device sections from every involved donor",
        "manual_v2_result_basis": "Isolation V2 worked only for T00/T03/T05/T06/T07/T10, which are the complete-donor-CDB cases.",
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
