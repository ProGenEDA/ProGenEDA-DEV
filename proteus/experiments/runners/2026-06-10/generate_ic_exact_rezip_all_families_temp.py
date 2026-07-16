"""Generate exact donor-content rezips for every currently supplied IC family.

This diagnostic deliberately performs no topology edits, no label edits, no
coordinate edits, no CDB synthesis, and no DSN version patching. Each output is
a deterministic ZIP container whose internal file payloads are byte-identical
to the selected donor project.

Use this to separate Proteus/library/model corruption from generator mutation
bugs. If an exact rezip fails, the donor/model/install is the boundary for that
family. If exact rezips pass, later failures belong to our mutation/composition
logic.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


REPO = Path(__file__).resolve().parents[4]
SEQ_HELPER = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_ic_sequential_counters_v2_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_exact_rezip_all_families_temp_2026_06_10"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_EXACT_REZIP_ALL_FAMILIES_TEMP_2026_06_10.zip"


def _load_seq_helper():
    spec = importlib.util.spec_from_file_location("seq_helper_for_exact_rezip_all", SEQ_HELPER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load sequential helper from {SEQ_HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


seq = _load_seq_helper()


@dataclass(frozen=True)
class ExactRezipCase:
    case_id: str
    family: str
    donor: Path
    proteus_marker: str
    notes: str = ""


def donor(relative: str) -> Path:
    return REPO / "proteus" / "active" / "evidence" / "donors" / relative


CASES: tuple[ExactRezipCase, ...] = (
    ExactRezipCase("T001_74HC00_NAND_EXACT_REZIP", "74HC00", donor("74hc00/IC_74HC00_M01_ONE_GATE_IO.pdsprj"), "74HC00"),
    ExactRezipCase("T002_74HC02_NOR_EXACT_REZIP", "74HC02", donor("74hc02/IC_74HC02_M01_ONE_GATE_IO.pdsprj"), "74HC02"),
    ExactRezipCase("T003_74HC04_NOT_EXACT_REZIP", "74HC04", donor("74hc04/IC_74HC04_M01_ONE_GATE_IO.pdsprj"), "74HC04"),
    ExactRezipCase("T004_74HC08_AND_EXACT_REZIP", "74HC08", donor("74hc08/IC_HC08_M01_ALL4_IO.pdsprj"), "74HC08"),
    ExactRezipCase("T005_74HC32_OR_EXACT_REZIP", "74HC32", donor("74hc32/IC_HC32_M02_ALL4_IO.pdsprj"), "74HC32", "The supplied M01 file contains HC08 metadata, so the exact family rezip uses the correct M02 all-four OR donor."),
    ExactRezipCase("T006_74HC86_XOR_EXACT_REZIP", "74HC86", donor("74hc86/IC_74HC86_M01_ONE_GATE_IO.pdsprj"), "74HC86"),
    ExactRezipCase("T007_74HC266_XNOR_EXACT_REZIP", "74HC266", donor("74hc266/IC_74HC266_M01_ONE_GATE_IO.pdsprj"), "74HC266"),
    ExactRezipCase("T008_74HC90_7490_EXACT_REZIP", "74HC90/7490", donor("sequential_counters/7490.pdsprj"), "7490", "User-facing 74HC90 uses Proteus 7490 donor."),
    ExactRezipCase("T009_74HC160_EXACT_REZIP", "74HC160", donor("sequential_counters/74HC160.pdsprj"), "74HC160"),
    ExactRezipCase("T010_74HC161_EXACT_REZIP", "74HC161", donor("sequential_counters/74HC161.pdsprj"), "74HC161"),
    ExactRezipCase("T011_74HC163_EXACT_REZIP", "74HC163", donor("sequential_counters/74HC163.pdsprj"), "74HC163"),
    ExactRezipCase("T012_74HC192_EXACT_REZIP", "74HC192", donor("sequential_counters/74HC192.pdsprj"), "74HC192"),
    ExactRezipCase("T013_74HC193_EXACT_REZIP", "74HC193", donor("sequential_counters/74HC193.pdsprj"), "74HC193"),
    ExactRezipCase("T014_4017_EXACT_REZIP", "4017", donor("sequential_counters/4017.pdsprj"), "4017"),
    ExactRezipCase("T015_4020_EXACT_REZIP", "4020", donor("sequential_counters/4020.pdsprj"), "4020"),
    ExactRezipCase("T016_74HC4024_EXACT_REZIP", "74HC4024", donor("sequential_counters/74HC4024.pdsprj"), "74HC4024"),
    ExactRezipCase("T017_74HC4040_EXACT_REZIP", "74HC4040", donor("sequential_ics_batch3/74HC4040.pdsprj"), "74HC4040"),
    ExactRezipCase("T018_74HC4060_REPO_SINGLE_EXACT_REZIP", "74HC4060 legacy repo single", donor("sequential_ics_4060_legacy_bad_20260610/74HC4060.pdsprj"), "74HC4060", "Legacy repo donor retained only as rejected comparison evidence; user testing said T018 did not work."),
    ExactRezipCase("T019_4518_EXACT_REZIP", "4518", donor("sequential_ics_batch3/4518.pdsprj"), "4518"),
    ExactRezipCase("T020_74HC4520_EXACT_REZIP", "74HC4520", donor("sequential_ics_batch3/74HC4520.pdsprj"), "74HC4520"),
    ExactRezipCase("T021_74HC74_EXACT_REZIP", "74HC74", donor("sequential_ics_batch3/74HC74.pdsprj"), "74HC74"),
    ExactRezipCase("T022_74HC76_EXACT_REZIP", "74HC76", donor("sequential_ics_batch3/74HC76.pdsprj"), "74HC76"),
    ExactRezipCase("T023_74HC174_EXACT_REZIP", "74HC174", donor("sequential_ics_batch3/74HC174.pdsprj"), "74HC174", "This is the supplied 74HC174 donor, not 74HC175."),
    ExactRezipCase("T024_74HC273_EXACT_REZIP", "74HC273", donor("sequential_ics_batch3/74HC273.pdsprj"), "74HC273"),
    ExactRezipCase("T025_4027_EXACT_REZIP", "4027", donor("sequential_ics_batch3/4027.pdsprj"), "4027"),
    ExactRezipCase("T026_74HC85_EXACT_REZIP", "74HC85", donor("sequential_ics_batch4/74HC85.pdsprj"), "74HC85"),
    ExactRezipCase("T027_74HC283_EXACT_REZIP", "74HC283", donor("sequential_ics_batch4/74HC283.pdsprj"), "74HC283"),
    ExactRezipCase("T028_74HC157_EXACT_REZIP", "74HC157", donor("sequential_ics_batch4/74HC157.pdsprj"), "74HC157"),
    ExactRezipCase("T029_74HC47_7447_EXACT_REZIP", "74HC47/7447", donor("sequential_ics_batch4/74HC47.pdsprj"), "7447", "User-facing 74HC47 donor uses Proteus marker 7447."),
    ExactRezipCase("T030_74HC165_EXACT_REZIP", "74HC165", donor("sequential_ics_batch4/74HC165.pdsprj"), "74HC165"),
    ExactRezipCase("T031_74HC595_EXACT_REZIP", "74HC595", donor("sequential_ics_batch4/74HC595.pdsprj"), "74HC595"),
    ExactRezipCase("T032_NE555_EXACT_REZIP", "NE555", donor("analog_misc_batch1/NE555.pdsprj"), "NE555"),
    ExactRezipCase("T033_LM741_EXACT_REZIP", "LM741", donor("analog_misc_batch1/LM741.pdsprj"), "LM741"),
    ExactRezipCase("T034_74HC4060_REFRESH_SINGLE_EXACT_REZIP", "74HC4060 refreshed single", donor("sequential_ics_4060_refresh_20260610/74HC4060.pdsprj"), "74HC4060", "Fresh user-supplied 4060 donor from Downloads on 2026-06-10."),
    ExactRezipCase("T035_74HC4060_REFRESH_2X_EXACT_REZIP", "74HC4060 refreshed 2x", donor("sequential_ics_4060_refresh_20260610/2_74HC4060.pdsprj"), "74HC4060", "Fresh user-supplied 2x 4060 donor from Downloads on 2026-06-10."),
    ExactRezipCase("T036_74HC4060_REFRESH_4X_EXACT_REZIP", "74HC4060 refreshed 4x", donor("sequential_ics_4060_refresh_20260610/4_74HC4060.pdsprj"), "74HC4060", "Fresh user-supplied 4x 4060 donor from Downloads on 2026-06-10."),
    ExactRezipCase("T037_74HC4060_REFRESH_4X_RLC_EXACT_REZIP", "74HC4060 refreshed 4x RLC", donor("sequential_ics_4060_refresh_20260610/4_74HC4060withRLC.pdsprj"), "74HC4060", "Fresh user-supplied 4x 4060+RLC donor from Downloads on 2026-06-10."),
    ExactRezipCase("T038_74HC4520_REFRESH_SINGLE_EXACT_REZIP", "74HC4520 refreshed single", donor("sequential_ics_4520_refresh_20260610/74HC4520.pdsprj"), "74HC4520", "Fresh user-supplied 4520 donor from Downloads on 2026-06-10; added after old T020 failed."),
    ExactRezipCase("T039_74HC4520_REFRESH_2X_EXACT_REZIP", "74HC4520 refreshed 2x", donor("sequential_ics_4520_refresh_20260610/2_74HC4520.pdsprj"), "74HC4520", "Fresh user-supplied 2x 4520 donor from Downloads on 2026-06-10; pending manual Proteus test."),
    ExactRezipCase("T040_74HC4520_REFRESH_4X_EXACT_REZIP", "74HC4520 refreshed 4x", donor("sequential_ics_4520_refresh_20260610/4_74HC4520.pdsprj"), "74HC4520", "Fresh user-supplied 4x 4520 donor from Downloads on 2026-06-10; pending manual Proteus test."),
    ExactRezipCase("T041_74HC4520_REFRESH_4X_RLC_EXACT_REZIP", "74HC4520 refreshed 4x RLC", donor("sequential_ics_4520_refresh_20260610/4_74HC4520withRLC.pdsprj"), "74HC4520", "Fresh user-supplied 4x 4520+RLC donor from Downloads on 2026-06-10; pending manual Proteus test."),
)


MISSING_DONOR_FAMILIES = (
    "NE555 is included; 74HC175, 4013, 4063, 74HC151, 74HC153, 4051, 4511, 74HC48, 4008, and 74HC175-family donors are not present yet.",
)


def _sha256(data: bytes) -> str:
    return seq._sha256_bytes(data)


def _zip_payloads(path: Path) -> dict[str, bytes]:
    with ZipFile(path, "r") as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def _write_exact_rezip(donor_path: Path, output_path: Path) -> None:
    payloads = _zip_payloads(donor_path)
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as zf:
        for name in sorted(payloads):
            info = ZipInfo(name)
            info.date_time = (2026, 6, 10, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, payloads[name])


def _marker_counts(data: bytes, markers: tuple[bytes, ...]) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in markers}


def _write_case(case: ExactRezipCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    _write_exact_rezip(case.donor, output)

    donor_payloads = _zip_payloads(case.donor)
    output_payloads = _zip_payloads(output)
    payload_mismatches = [
        name for name, payload in donor_payloads.items() if output_payloads.get(name) != payload
    ]
    extra_output_members = sorted(set(output_payloads) - set(donor_payloads))
    missing_output_members = sorted(set(donor_payloads) - set(output_payloads))

    dsn = output_payloads.get("ROOT.DSN", b"")
    cdb = output_payloads.get("ROOT.CDB", b"")
    chunk = b""
    chunk_error = ""
    try:
        chunk = seq._extract_object_chunk(dsn)
    except Exception as exc:  # pragma: no cover - diagnostic manifest path
        chunk_error = str(exc)

    marker = case.proteus_marker.encode("ascii")
    issues: list[str] = []
    for required in ("PROJECT.XML", "ROOT.DSN", "ROOT.CDB", "SCRIPTS/PWRRAILS.DAT"):
        if required not in output_payloads:
            issues.append(f"missing {required}")
    if payload_mismatches or extra_output_members or missing_output_members:
        issues.append("output internal payloads are not byte-identical to donor")
    if marker not in dsn and marker not in cdb:
        issues.append(f"marker {case.proteus_marker} not found in ROOT.DSN or ROOT.CDB")
    if chunk_error:
        issues.append(f"object chunk extraction failed: {chunk_error}")

    terminal_counts = {
        "$TERINPUT": chunk.count(b"$TERINPUT"),
        "$TEROUTPUT": chunk.count(b"$TEROUTPUT"),
        "$TERBIDIR": chunk.count(b"$TERBIDIR"),
        "$TERPOWER": chunk.count(b"$TERPOWER"),
        "$TERGROUND": chunk.count(b"$TERGROUND"),
        "WIRE": chunk.count(b"WIRE"),
    }
    terminal_events = []
    if terminal_counts["$TERBIDIR"]:
        try:
            terminal_events = seq.bidir_events(chunk)
        except Exception:
            terminal_events = []

    manifest = {
        "case_id": case.case_id,
        "family": case.family,
        "proteus_marker": case.proteus_marker,
        "notes": case.notes,
        "method": "exact_donor_content_rezip_no_payload_mutation",
        "status": "temporary_pending_user_proteus_testing",
        "donor": str(case.donor.relative_to(REPO)),
        "payload_policy": "all internal ZIP member payloads are byte-identical to donor; only outer ZIP container metadata/order is deterministic",
        "member_order": sorted(output_payloads),
        "payload_mismatches": payload_mismatches,
        "extra_output_members": extra_output_members,
        "missing_output_members": missing_output_members,
        "marker_counts": _marker_counts(dsn + cdb, (marker, b"$TERINPUT", b"$TEROUTPUT", b"$TERBIDIR", b"WIRE")),
        "terminal_counts": terminal_counts,
        "bidir_terminal_events": terminal_events,
        "object_chunk_size": len(chunk),
        "static_validation_issues": issues,
        "hashes": {
            "donor_project": _sha256(case.donor.read_bytes()),
            "rezip_project": _sha256(output.read_bytes()),
            "donor_ROOT.DSN": _sha256(donor_payloads.get("ROOT.DSN", b"")),
            "rezip_ROOT.DSN": _sha256(output_payloads.get("ROOT.DSN", b"")),
            "donor_ROOT.CDB": _sha256(donor_payloads.get("ROOT.CDB", b"")),
            "rezip_ROOT.CDB": _sha256(output_payloads.get("ROOT.CDB", b"")),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


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
    return _sha256(ARCHIVE_PATH.read_bytes())


def main() -> None:
    missing = [str(case.donor) for case in CASES if not case.donor.exists()]
    if missing:
        raise FileNotFoundError("\n".join(missing))
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifests = [_write_case(case) for case in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_EXACT_REZIP_ALL_FAMILIES_TEMP_2026_06_10",
        "purpose": "Exact donor-content rezip for every currently supplied IC family; no generator mutations.",
        "status": "temporary_pending_user_proteus_testing",
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "missing_donor_families": MISSING_DONOR_FAMILIES,
        "archive": str(ARCHIVE_PATH.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = _write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE_PATH),
                "archive_sha256": archive_hash,
                "case_count": len(manifests),
                "static_issue_cases": summary_issues,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
