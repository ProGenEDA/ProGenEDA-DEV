"""Generate the first temporary 74HC08/74HC32 IC acceptance pack.

This is intentionally not a production generator. It tests the smallest safe
steps first: exact donor repacks, donor object/CDB transplants into E001, and
terminal-label-only mutations. Package/subpart and coordinate mutation are held
back until these cases pass in Proteus.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_hc08_hc32_v1_temp_2026_06_07"
DONOR_ROOT = REPO / "proteus" / "active" / "evidence" / "donors"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_HC08_HC32_V1_TEMP_2026_06_07.zip"

MARKERS = (
    b"74HC08",
    b"74HC32",
    b"LOGICSTATE",
    b"LOGICPROBE",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERBIDIR",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"RESISTOR",
    b"CAPACITOR",
    b"REALIND",
)


@dataclass(frozen=True)
class Donor:
    key: str
    path: Path
    expected_device: str
    notes: str = ""


DONORS = {
    "hc08_d01": Donor(
        "hc08_d01",
        REPO / "proteus" / "active" / "fixtures" / "pdsprj" / "hc08_d01_single_gate.pdsprj",
        "74HC08",
        "Existing single-gate donor with A/B/Y ordinary terminals.",
    ),
    "hc08_m01": Donor(
        "hc08_m01",
        DONOR_ROOT / "74hc08" / "IC_HC08_M01_ALL4_IO.pdsprj",
        "74HC08",
        "User all-four-gate ordinary terminal donor.",
    ),
    "hc08_m02": Donor(
        "hc08_m02",
        DONOR_ROOT / "74hc08" / "IC_HC08_M02_TWO_PACKAGES_IO.pdsprj",
        "74HC08",
        "User two-package ordinary terminal donor.",
    ),
    "hc08_m03": Donor(
        "hc08_m03",
        DONOR_ROOT / "74hc08" / "IC_HC08_M03_TRUTH_TABLE_PG.pdsprj",
        "74HC08",
        "User power/ground logic-constant donor.",
    ),
    "hc08_m04": Donor(
        "hc08_m04",
        DONOR_ROOT / "74hc08" / "IC_HC08_M04_RCL_LOAD.pdsprj",
        "74HC08",
        "Diagnostic only: includes bidirectional passive-load terminals.",
    ),
    "hc32_m01": Donor(
        "hc32_m01",
        DONOR_ROOT / "74hc32" / "IC_HC32_M01_ONE_GATE_IO.pdsprj",
        "74HC32",
        "Rejected as HC32 evidence if internal markers do not match.",
    ),
    "hc32_m02": Donor(
        "hc32_m02",
        DONOR_ROOT / "74hc32" / "IC_HC32_M02_ALL4_IO.pdsprj",
        "74HC32",
        "User all-four-gate ordinary terminal donor.",
    ),
}


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def donor_analysis(donor: Donor) -> dict[str, object]:
    dsn = read_internal_file(donor.path, "ROOT.DSN")
    cdb = read_internal_file(donor.path, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    counts = marker_counts(chunk)
    device_count = counts.get(donor.expected_device, 0)
    rejected = bool(donor.expected_device == "74HC32" and device_count == 0)
    return {
        "key": donor.key,
        "path": str(donor.path.relative_to(REPO)),
        "sha256": _sha256_bytes(donor.path.read_bytes()),
        "size": donor.path.stat().st_size,
        "expected_device": donor.expected_device,
        "rejected": rejected,
        "notes": donor.notes,
        "root_dsn_size": len(dsn),
        "root_dsn_sha256": _sha256_bytes(dsn),
        "root_cdb_size": len(cdb),
        "root_cdb_sha256": _sha256_bytes(cdb),
        "object_chunk_size": len(chunk),
        "object_chunk_sha256": _sha256_bytes(chunk),
        "object_chunk_marker_counts": counts,
        "cdb_marker_counts": marker_counts(cdb),
    }


def patch_terminal_labels(chunk: bytes, replacements: dict[str, str]) -> tuple[bytes, list[dict[str, object]]]:
    out = bytearray(chunk)
    events: list[dict[str, object]] = []
    specs = (
        (b"$TERINPUT", 16, 17),
        (b"$TEROUTPUT", 17, 18),
    )
    for marker, len_delta, label_delta in specs:
        start = 0
        while True:
            pos = chunk.find(marker, start)
            if pos < 0:
                break
            length_pos = pos + len_delta
            label_pos = pos + label_delta
            length = chunk[length_pos]
            if length in (1, 2):
                old = chunk[label_pos : label_pos + length].decode("ascii", errors="replace")
                new = replacements.get(old)
                if new is not None:
                    raw = new.encode("ascii")
                    if len(raw) != length:
                        raise ValueError(
                            f"Replacement label {new!r} must be {length} ASCII byte(s) to keep record size stable."
                        )
                    out[label_pos : label_pos + length] = raw
                    events.append(
                        {
                            "terminal_marker": marker.decode("ascii"),
                            "offset": pos,
                            "old": old,
                            "new": new,
                        }
                    )
            start = pos + 1
    return bytes(out), events


def write_exact_case(case_id: str, donor: Donor, description: str) -> dict[str, object]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(donor.path, output, {})
    return write_case_manifest(case_id, output, donor, description, "exact_repack", None, [])


def write_transplant_case(
    case_id: str,
    donor: Donor,
    description: str,
    *,
    label_replacements: dict[str, str] | None = None,
    allow_bidir: bool = False,
) -> dict[str, object]:
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(donor.path, "ROOT.DSN")
    chunk = _extract_object_chunk(donor_dsn)
    mutation_events: list[dict[str, object]] = []
    method = "e001_transplant"
    if label_replacements:
        chunk, mutation_events = patch_terminal_labels(chunk, label_replacements)
        method = "e001_transplant_label_only"
    dsn, pointers = build_dsn(base_dsn, donor_dsn, chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    cdb = read_internal_file(donor.path, "ROOT.CDB")
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    return write_case_manifest(case_id, output, donor, description, method, pointers, mutation_events, allow_bidir=allow_bidir)


def static_issues(output: Path, *, allow_bidir: bool) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"$TERBIDIR") and not allow_bidir:
        issues.append("unexpected bidirectional terminal marker in IC case")
    if chunk.count(b"LOGICSTATE") or chunk.count(b"LOGICPROBE"):
        issues.append("logicstate/probe visual component present in object chunk")
    return issues


def write_case_manifest(
    case_id: str,
    output: Path,
    donor: Donor,
    description: str,
    method: str,
    pointers: dict[str, int] | None,
    mutation_events: list[dict[str, object]],
    *,
    allow_bidir: bool = False,
) -> dict[str, object]:
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    manifest = {
        "case_id": case_id,
        "description": description,
        "method": method,
        "donor_key": donor.key,
        "donor_path": str(donor.path.relative_to(REPO)),
        "output_path": str(output.relative_to(REPO)),
        "allow_bidir": allow_bidir,
        "mutation_events": mutation_events,
        "section_pointers": pointers or {},
        "static_validation_issues": static_issues(output, allow_bidir=allow_bidir),
        "marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(chunk),
        },
        "proteus_result_pending": True,
    }
    (output.parent / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 7, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    donor_report = {key: donor_analysis(donor) for key, donor in DONORS.items()}
    (DONOR_ROOT / "analysis_v1.json").write_text(json.dumps(donor_report, indent=2) + "\n", encoding="utf-8")

    cases = []
    cases.append(write_exact_case("T00_HC08_D01_EXACT_REPACK", DONORS["hc08_d01"], "Existing single-gate HC08 donor exact deterministic repack."))
    cases.append(write_transplant_case("T01_HC08_D01_E001_TRANSPLANT", DONORS["hc08_d01"], "Single-gate HC08 object chunk and CDB transplanted into E001."))
    cases.append(write_transplant_case("T02_HC08_D01_REPEAT_TRANSPLANT", DONORS["hc08_d01"], "Repeat single-gate HC08 transplant to verify deterministic output and one-gate donor stability."))
    cases.append(write_transplant_case("T03_HC08_M01_ALL4_E001_TRANSPLANT", DONORS["hc08_m01"], "All four HC08 gates with ordinary input/output terminals transplanted into E001."))
    cases.append(
        write_transplant_case(
            "T04_HC08_M01_ALL4_LABEL_ONLY",
            DONORS["hc08_m01"],
            "All four HC08 gates with terminal labels mutated only.",
            label_replacements={
                "A1": "C1",
                "B1": "D1",
                "Y1": "Z1",
                "A2": "C2",
                "B2": "D2",
                "Y2": "Z2",
                "A3": "C3",
                "B3": "D3",
                "Y3": "Z3",
                "A4": "C4",
                "B4": "D4",
                "Y4": "Z4",
            },
        )
    )
    cases.append(write_transplant_case("T05_HC08_M02_TWO_PACKAGES_E001_TRANSPLANT", DONORS["hc08_m02"], "Two HC08 packages, U1:A and U2:A, transplanted into E001."))
    cases.append(
        write_transplant_case(
            "T06_HC08_M02_TWO_PACKAGES_LABEL_ONLY",
            DONORS["hc08_m02"],
            "Two HC08 packages with terminal labels mutated only.",
            label_replacements={"A1": "C1", "B1": "D1", "Y1": "Z1", "A2": "C2", "B2": "D2", "Y2": "Z2"},
        )
    )
    cases.append(write_transplant_case("T07_HC08_M03_TRUTH_TABLE_PG_E001_TRANSPLANT", DONORS["hc08_m03"], "HC08 truth-table power/ground logic-constant donor transplanted into E001."))
    cases.append(write_transplant_case("T08_HC08_M04_RCL_LOAD_DIAGNOSTIC_E001_TRANSPLANT", DONORS["hc08_m04"], "Diagnostic RCL-load donor transplant. Not production-locking because the donor contains bidirectional passive terminals.", allow_bidir=True))
    cases.append(write_transplant_case("T09_HC32_M02_ALL4_E001_TRANSPLANT", DONORS["hc32_m02"], "All four HC32 gates with ordinary input/output terminals transplanted into E001."))
    cases.append(
        write_transplant_case(
            "T10_HC32_M02_ALL4_LABEL_ONLY",
            DONORS["hc32_m02"],
            "All four HC32 gates with terminal labels mutated only.",
            label_replacements={
                "A1": "E1",
                "B1": "F1",
                "Y1": "O1",
                "A2": "E2",
                "B2": "F2",
                "Y2": "O2",
                "A3": "E3",
                "B3": "F3",
                "Y3": "O3",
                "A4": "E4",
                "B4": "F4",
                "Y4": "O4",
            },
        )
    )

    summary = {
        "batch": "IC_HC08_HC32_V1_TEMP_2026_06_07",
        "purpose": "First IC donor reconstruction, E001 transplant, and label-only mutation pack.",
        "do_not_promote": True,
        "user_test_order": [case["case_id"] for case in cases],
        "known_donor_findings": {
            "hc32_m01": "Rejected as HC32 evidence: internal markers show 74HC08/74AND2, not 74HC32/74OR2.",
            "hc08_m04": "Diagnostic only: passive-load section contains $TERBIDIR markers, which conflicts with production IC terminal policy.",
        },
        "cases": cases,
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "archive_sha256": summary["archive_sha256"], "case_count": len(cases)}, indent=2))


if __name__ == "__main__":
    main()
