"""Regenerate the requested five mixed DC-source R/C/L circuits after V9 acceptance.

This is a thin wrapper around the accepted V14 requested-five generator. It
keeps the same V13/V14 source-duplication method, writes a fresh V15 output
folder/archive, and renames the case ids so the test pack is traceable after
the pure DCV+DCV V9 wire/source-boundary acceptance.
"""

from __future__ import annotations

import hashlib
import importlib.util
import contextlib
import io
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
V14_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v14_requested5_v13_method_temp.py"
OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v15_requested5_after_v9_acceptance_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V15_REQUESTED5_AFTER_V9_ACCEPTANCE_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    v14 = _load_module("dc_mixed_sources_v14_for_v15", V14_PATH)

    original_case_definitions = v14._case_definitions

    def _case_definitions_v15() -> list[Any]:
        cases = []
        for case in original_case_definitions():
            cases.append(replace(case, case_id=case.case_id.replace("DCMS_V14", "DCMS_V15", 1)))
        return cases

    v14.OUT_ROOT = OUT_ROOT
    v14.ARCHIVE_BASE = ARCHIVE_BASE
    v14.DONOR_ROOT = DONOR_ROOT
    v14._case_definitions = _case_definitions_v15

    with contextlib.redirect_stdout(io.StringIO()):
        v14.main()

    control_dir = OUT_ROOT / "DCMS_V14_T00_V13_ACCEPTED_CONTROL"
    if control_dir.exists():
        shutil.rmtree(control_dir)
    for control_file in OUT_ROOT.glob("DCMS_V14_T00_V13_ACCEPTED_CONTROL*"):
        if control_file.is_file():
            control_file.unlink()

    manifest_path = OUT_ROOT / "batch_manifest.json"
    summary = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary["test_order"] = [case_id for case_id in summary["test_order"] if case_id != "DCMS_V14_T00_V13_ACCEPTED_CONTROL"]
    summary["cases"] = [case for case in summary["cases"] if case["case_id"] != "DCMS_V14_T00_V13_ACCEPTED_CONTROL"]
    summary["batch_id"] = "DC_MIXED_SOURCES_V15_REQUESTED5_AFTER_V9_ACCEPTANCE_STATIC_20260605"
    summary["status"] = "static_generated_awaiting_user_proteus_open_netlist_test"
    summary["source_feedback"] = "User confirmed Source Passive V9 T00-T03 all worked."
    summary["method"] = (
        "Fresh five-circuit requested mixed DC source pack. It reuses the accepted V13/V14 "
        "multi-source R/C/L source-duplication method after the separate V9 pure DCV+DCV "
        "wire/source-boundary fix was confirmed."
    )
    manifest_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    readme = OUT_ROOT / "README_TEST_ORDER.txt"
    readme.write_text(
        "DC_MIXED_SOURCES_V15_REQUESTED5_AFTER_V9_ACCEPTANCE_TEMP_2026_06_05\n\n"
        "Open in order:\n"
        + "\n".join(
            f"{index}. {case_id}/{case_id}.pdsprj"
            for index, case_id in enumerate(summary["test_order"], start=1)
        )
        + "\n\nThese are the five requested mixed DC-source R/C/L circuits only.\n",
        encoding="utf-8",
    )

    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used_v15_wrapper.py")
    archive_path = Path(str(ARCHIVE_BASE) + ".zip")
    if archive_path.exists():
        archive_path.unlink()
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
