"""Generate focused fixes only for V1 pairwise IC cases that user testing rejected.

This deliberately does not regenerate the full pairwise matrix. The first pass
isolates the clearest failed sample, S01+S02, and emits it through the accepted
combinational IC generator instead of whole-donor object concatenation.

User-reported V1 failure class for S01+S02:

- project opens;
- simulation fails with duplicate part references like U2:A [U1:A] and
  duplicate X000000.. internal refs.

The accepted combinational route avoids that copy/paste failure by constructing
fresh gate records and ROOT.CDB rows from the locked combinational donor slices.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


REPO = Path(__file__).resolve().parents[3]
OUT_ROOT = REPO / "experiments" / "ic_pairwise_error_focused_v1_temp_2026_06_10"
ARCHIVE_PATH = REPO / "experiments" / "IC_PAIRWISE_ERROR_FOCUSED_V1_TEMP_2026_06_10.zip"


def _load_ic_module():
    script = REPO / "src" / "proteusgen" / "ic_combinational.py"
    spec = importlib.util.spec_from_file_location("ic_combinational_pairwise_focus", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ic = _load_ic_module()


FAILED_PAIRS_FROM_V1_USER_NOTES = {
    "duplicate_part_reference": [
        ("S01", "S02"),
        ("S01", "S03"),
        ("S01", "S04"),
        ("S01", "S05"),
        ("S01", "S06"),
        ("S01", "S08"),
        ("S01", "S09"),
        ("S01", "S10"),
        ("S01", "S12"),
        ("S01", "S14"),
        ("S01", "S16"),
        ("S01", "S29"),
        ("S01", "S30"),
        ("S02", "S03"),
        ("S02", "S04"),
        ("S02", "S05"),
        ("S02", "S06"),
        ("S02", "S08"),
        ("S02", "S09"),
        ("S02", "S10"),
        ("S02", "S12"),
        ("S02", "S14"),
        ("S02", "S16"),
        ("S02", "S29"),
        ("S02", "S30"),
        ("S03", "S04"),
        ("S03", "S05"),
        ("S03", "S06"),
        ("S03", "S08"),
        ("S03", "S09"),
        ("S03", "S10"),
        ("S03", "S12"),
        ("S03", "S14"),
        ("S03", "S16"),
        ("S03", "S29"),
        ("S03", "S30"),
        ("S04", "S05"),
        ("S04", "S06"),
        ("S04", "S08"),
        ("S04", "S09"),
        ("S04", "S10"),
        ("S04", "S12"),
        ("S04", "S14"),
        ("S04", "S16"),
        ("S04", "S29"),
        ("S04", "S30"),
        ("S05", "S06"),
        ("S05", "S08"),
        ("S05", "S09"),
        ("S05", "S10"),
        ("S05", "S12"),
        ("S05", "S14"),
        ("S05", "S16"),
        ("S05", "S29"),
        ("S05", "S30"),
        ("S06", "S08"),
        ("S06", "S09"),
        ("S06", "S10"),
        ("S06", "S12"),
        ("S06", "S14"),
        ("S06", "S16"),
        ("S06", "S29"),
        ("S06", "S30"),
        ("S08", "S09"),
        ("S08", "S10"),
        ("S08", "S12"),
        ("S08", "S14"),
        ("S08", "S16"),
        ("S08", "S29"),
        ("S08", "S30"),
        ("S15", "S21"),
    ],
    "no_model_specified": [
        ("S01", "S27"),
        ("S02", "S27"),
        ("S21", "S22"),
        ("S21", "S23"),
        ("S21", "S24"),
        ("S21", "S25"),
        ("S21", "S26"),
        ("S21", "S27"),
        ("S21", "S29"),
        ("S22", "S27"),
        ("S22", "S29"),
    ],
    "coordinate_artifact_only_in_v1": [
        ("S01", "S32"),
        ("S01", "S33"),
        ("S01", "S34"),
        ("S02", "S32"),
        ("S02", "S33"),
        ("S02", "S34"),
        ("S03", "S32"),
        ("S03", "S33"),
        ("S03", "S34"),
        ("S04", "S32"),
        ("S04", "S33"),
        ("S04", "S34"),
        ("S05", "S32"),
        ("S05", "S33"),
        ("S05", "S34"),
        ("S06", "S32"),
        ("S06", "S33"),
        ("S06", "S34"),
        ("S08", "S32"),
        ("S08", "S33"),
        ("S08", "S34"),
        ("S21", "S32"),
        ("S21", "S33"),
        ("S21", "S34"),
        ("S22", "S32"),
        ("S22", "S33"),
        ("S22", "S34"),
    ],
}


CASES = (
    ic.CircuitCase(
        "T01_S01_S02_ACCEPTED_COMBINATIONAL",
        "S01 74HC00 NAND plus S02 74HC02 NOR using accepted combinational path",
        "Y1 = nand(A1, B1); Y2 = nor(A2, B2)",
        (
            "Focused replacement for failed pairwise P001_S01_S02. "
            "Uses fresh accepted gate records and generated CDB rows instead "
            "of whole-donor U2 chunk copying."
        ),
        (
            ic.GateSpec("74hc00", "A", "A1", "B1", "Y1"),
            ic.GateSpec("74hc02", "A", "A2", "B2", "Y2"),
        ),
    ),
)


def _write_archive() -> str:
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
    return ic._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifests = [ic.write_case(case, out_root=OUT_ROOT) for case in CASES]
    failed_pairs_path = OUT_ROOT / "v1_failed_pairs_from_user_notes.json"
    failed_pairs_path.write_text(json.dumps(FAILED_PAIRS_FROM_V1_USER_NOTES, indent=2) + "\n", encoding="utf-8")
    summary = {
        "batch": "IC_PAIRWISE_ERROR_FOCUSED_V1_TEMP_2026_06_10",
        "status": "sample_first_pending_user_proteus_test",
        "purpose": "Do not touch V1 working pairs. Isolate rejected V1 pairs and fix one sample through the accepted generator path first.",
        "do_not_touch": "Pairs omitted from the user failure notes remain on the V1 accepted-by-omission path until a specific failure is reported.",
        "first_sample": "S01+S02 duplicate-reference failure, regenerated as accepted combinational NAND+NOR records.",
        "cases": manifests,
        "failed_pairs_from_user_notes_file": failed_pairs_path.name,
        "failed_pair_counts": {key: len(value) for key, value in FAILED_PAIRS_FROM_V1_USER_NOTES.items()},
        "static_issue_cases": {
            item["case_id"]: item["static_validation_issues"]
            for item in manifests
            if item["static_validation_issues"]
        },
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = _write_archive()
    summary["archive"] = str(ARCHIVE_PATH.relative_to(REPO))
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "archive_sha256": archive_hash}, indent=2))


if __name__ == "__main__":
    main()
