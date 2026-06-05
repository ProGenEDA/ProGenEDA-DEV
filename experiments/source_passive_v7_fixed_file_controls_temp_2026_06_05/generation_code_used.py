"""Generate fixed-file controls for pure DCV+DCV passive debugging.

V6 showed that CDB-only changes over generated V3 still produce bad object
records. This batch stops mutating generated source objects and instead uses
the user-fixed V3 T03 project as the oracle surface.

The test isolates three questions in order:

1. Does the exact user-fixed file still work after being copied into the batch?
2. Does deterministic repacking alone change Proteus behavior?
3. Does E001 container context or CDB-only source value mutation change behavior
   when ROOT.DSN is copied directly from the fixed file?
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_rcl as rcl  # noqa: E402
from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402

OUT_ROOT = REPO_ROOT / "experiments" / "source_passive_v7_fixed_file_controls_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "SOURCE_PASSIVE_V7_FIXED_FILE_CONTROLS_TEMP_2026_06_05"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V7_FIXED_FILE_CONTROLS_TEST_BATCH"
DONOR_ROOT = OUT_ROOT / "donors"

USER_FIXED = Path(r"C:\Users\tahab\Downloads\SRCP_V3_DCV2_T03_R_ONLY_D0_WITH_1G_REF.pdsprj")
E001_BASE = REPO_ROOT / "fixtures" / "pdsprj" / "control_e001_empty_base.pdsprj"
REQUIRED_INTERNALS = ("PROJECT.XML", "ROOT.DSN", "ROOT.CDB", "SCRIPTS/PWRRAILS.DAT")


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    mode: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _zip_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path, "r") as zf:
        return zf.namelist()


def _patch_fixed_cdb_source_values(cdb: bytes) -> bytes:
    """Patch only source value strings in the fixed CDB: V1=10V, V2=5V."""

    marker = b"\x021V"
    if cdb.count(marker) != 2:
        raise RuntimeError(f"Expected exactly two fixed source value records, found {cdb.count(marker)}.")
    patched = cdb.replace(marker, b"\x0310V", 1)
    patched = patched.replace(marker, b"\x025V", 1)
    return patched


def _copy_fixed_donor() -> None:
    if not USER_FIXED.exists():
        raise FileNotFoundError(USER_FIXED)
    if not E001_BASE.exists():
        raise FileNotFoundError(E001_BASE)
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(USER_FIXED, DONOR_ROOT / "user_fixed_v3_t03_d0_1g_ref.pdsprj")
    shutil.copy2(E001_BASE, DONOR_ROOT / "e001_empty_base.pdsprj")
    for internal in ("ROOT.DSN", "ROOT.CDB"):
        (DONOR_ROOT / f"user_fixed_v3_t03.{internal}.bin").write_bytes(read_internal_file(USER_FIXED, internal))


def _cases() -> list[Case]:
    return [
        Case(
            "SRCP_V7_T00_USER_FIXED_EXACT_COPY",
            "Exact byte-for-byte copy of the user-fixed V3 T03 project. If this fails, the supplied fixed project is not a valid oracle in this environment.",
            "exact_copy",
        ),
        Case(
            "SRCP_V7_T01_USER_FIXED_REPACK_DEFLATED_NO_CHANGES",
            "Same internal files from the user-fixed project, repacked with the repository deterministic deflated writer and no ROOT changes.",
            "fixed_repack_deflated",
        ),
        Case(
            "SRCP_V7_T02_USER_FIXED_REPACK_STORED_NO_CHANGES",
            "Same internal files from the user-fixed project, repacked with ZIP_STORED and no ROOT changes.",
            "fixed_repack_stored",
        ),
        Case(
            "SRCP_V7_T03_USER_FIXED_DSN_CDB_IN_E001",
            "E001 base container with only ROOT.DSN and ROOT.CDB copied directly from the user-fixed project.",
            "fixed_dsn_cdb_in_e001",
        ),
        Case(
            "SRCP_V7_T04_USER_FIXED_CDB_ONLY_10V_5V",
            "User-fixed project repacked with fixed ROOT.DSN unchanged and only ROOT.CDB source values changed from 1V/1V to 10V/5V.",
            "fixed_cdb_values_10v_5v",
        ),
    ]


def _write_case(case: Case) -> dict:
    case_dir = TEST_BATCH / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / f"{case.case_id}.pdsprj"

    if case.mode == "exact_copy":
        shutil.copy2(USER_FIXED, output_path)
    elif case.mode == "fixed_repack_deflated":
        write_project_from_parts(USER_FIXED, output_path, {})
    elif case.mode == "fixed_repack_stored":
        write_project_from_parts(USER_FIXED, output_path, {}, compression=zipfile.ZIP_STORED)
    elif case.mode == "fixed_dsn_cdb_in_e001":
        write_project_from_parts(
            E001_BASE,
            output_path,
            {
                "ROOT.DSN": read_internal_file(USER_FIXED, "ROOT.DSN"),
                "ROOT.CDB": read_internal_file(USER_FIXED, "ROOT.CDB"),
            },
        )
    elif case.mode == "fixed_cdb_values_10v_5v":
        patched_cdb = _patch_fixed_cdb_source_values(read_internal_file(USER_FIXED, "ROOT.CDB"))
        write_project_from_parts(USER_FIXED, output_path, {"ROOT.CDB": patched_cdb})
    else:
        raise ValueError(case.mode)

    missing = [name for name in REQUIRED_INTERNALS if name not in _zip_names(output_path)]
    if missing:
        raise RuntimeError(f"{case.case_id} missing required internals: {missing}")

    root_dsn = read_internal_file(output_path, "ROOT.DSN")
    root_cdb = read_internal_file(output_path, "ROOT.CDB")
    object_chunk = rv9._extract_object_chunk(root_dsn)
    dsn_path = case_dir / f"{case.case_id}.ROOT.DSN.bin"
    cdb_path = case_dir / f"{case.case_id}.ROOT.CDB.bin"
    dsn_path.write_bytes(root_dsn)
    cdb_path.write_bytes(root_cdb)

    info = {
        "case_id": case.case_id,
        "description": case.description,
        "status": "temporary_source_passive_v7_fixed_file_control_pending_user_test",
        "output": f"{case.case_id}\\{case.case_id}.pdsprj",
        "mode": case.mode,
        "zip_names": _zip_names(output_path),
        "object_chunk_len": len(object_chunk),
        "root_dsn_len": len(root_dsn),
        "root_cdb_len": len(root_cdb),
        "marker_counts": rcl._marker_counts(object_chunk),
        "static_validation_issues": rcl._scan_wire_issues(object_chunk),
        "fixed_root_dsn_preserved": root_dsn == read_internal_file(USER_FIXED, "ROOT.DSN"),
        "fixed_root_cdb_preserved": root_cdb == read_internal_file(USER_FIXED, "ROOT.CDB"),
        "hashes": {
            f"{case.case_id}.pdsprj": _sha256_file(output_path),
            f"{case.case_id}.ROOT.DSN.bin": _sha256_file(dsn_path),
            f"{case.case_id}.ROOT.CDB.bin": _sha256_file(cdb_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(root_cdb),
        },
    }
    if case.mode == "exact_copy":
        info["exact_user_fixed_bytes_preserved"] = output_path.read_bytes() == USER_FIXED.read_bytes()
    if case.mode == "fixed_cdb_values_10v_5v":
        info["source_value_patch"] = "ROOT.CDB only: first source value 1V->10V, second source value 1V->5V; ROOT.DSN unchanged."

    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"Open and simulate {case.case_id}.pdsprj\n\n{case.description}\n",
        encoding="utf-8",
    )
    return info


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    archive = ARCHIVE_BASE.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    TEST_BATCH.mkdir(parents=True, exist_ok=True)
    _copy_fixed_donor()

    manifests = [_write_case(case) for case in _cases()]
    order = [item["case_id"] for item in manifests]
    summary = {
        "batch_id": "SOURCE_PASSIVE_V7_FIXED_FILE_CONTROLS_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_simulation_test",
        "source_feedback": "V6 CDB-only variants over generated V3 all gave bad object record.",
        "method": "Use the user-fixed V3 T03 project as the oracle and isolate exact-copy, no-change repack, E001 transplant, and CDB-only value mutation.",
        "test_order": order,
        "important_test_instruction": "Test T00 first. If T00 fails, stop and report it because the fixed oracle copy itself is not accepted.",
        "cases": [
            {
                "case_id": item["case_id"],
                "mode": item["mode"],
                "description": item["description"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "fixed_root_dsn_preserved": item["fixed_root_dsn_preserved"],
                "fixed_root_cdb_preserved": item["fixed_root_cdb_preserved"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in manifests
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V7 fixed-file control pack.\n\n"
        "Test in order. T00 is an exact byte-for-byte copy of your fixed file; if T00 fails, stop and report T00 specifically.\n\n"
        + "\n".join(f"{idx}. {case_id}/{case_id}.pdsprj" for idx, case_id in enumerate(order, start=1))
        + "\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(__file__, OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({**summary, "archive": str(archive), "archive_sha256": _sha256_file(archive)}, indent=2))


if __name__ == "__main__":
    main()
