"""Generate donor-learning diagnostics for remaining combinational ICs.

This pack covers 74HC00, 74HC02, 74HC86, and the supplied XNOR-family 74HC266.
It intentionally starts with donor transplants and label-only mutations before
expression synthesis. IC signal pins remain directional; passive endpoints and
logic constant bridges may use the accepted bidirectional terminal records.
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

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_remaining_combinational_v1_temp_2026_06_08"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_REMAINING_COMBINATIONAL_V1_TEMP_2026_06_08.zip"
DONOR_ROOT = REPO / "proteus" / "active" / "evidence" / "donors"

MARKERS = (
    b"74HC00",
    b"74NAND2",
    b"74HC02",
    b"74NOR2",
    b"74HC86",
    b"74XOR2",
    b"74HC266",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERBIDIR",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"COMPONENT VALUE",
    b"RESISTOR",
    b"CAPACITOR",
    b"CAP10",
    b"REALIND",
    b"VSOURCE",
    b"CSOURCE",
    b"VSINE",
    b"LOGICSTATE",
    b"LOGICPROBE",
)


@dataclass(frozen=True)
class Donor:
    key: str
    family: str
    path: Path
    expected_device: str
    logic_role: str
    allow_bidir: bool = False
    notes: str = ""


FAMILY_INFO = {
    "74hc00": {"device": "74HC00", "role": "NAND2"},
    "74hc02": {"device": "74HC02", "role": "NOR2"},
    "74hc86": {"device": "74HC86", "role": "XOR2"},
    "74hc266": {"device": "74HC266", "role": "XNOR2 donor uses 74XOR2.MDF markers in Proteus"},
}


def donor(family: str, suffix: str, *, allow_bidir: bool = False, notes: str = "") -> Donor:
    info = FAMILY_INFO[family]
    filename = f"IC_{info['device']}_{suffix}.pdsprj"
    return Donor(
        key=f"{family}_{suffix.lower()}",
        family=family,
        path=DONOR_ROOT / family / filename,
        expected_device=info["device"],
        logic_role=info["role"],
        allow_bidir=allow_bidir,
        notes=notes,
    )


DONORS: dict[str, Donor] = {}
for fam in FAMILY_INFO:
    DONORS[f"{fam}_m02"] = donor(fam, "M02_ALL4_IO")
    two_package_has_pg = fam in {"74hc86", "74hc266"}
    DONORS[f"{fam}_m03"] = donor(
        fam,
        "M03_TWO_PACKAGES_IO",
        allow_bidir=two_package_has_pg,
        notes="Donor includes power/ground bridge records despite IO filename." if two_package_has_pg else "",
    )
    DONORS[f"{fam}_m04"] = donor(fam, "M04_LOGIC_CONSTANTS_PG", allow_bidir=True)
    DONORS[f"{fam}_m05"] = donor(fam, "M05_RCL_LOAD", allow_bidir=True)

COMBINED_DONORS = {
    "all4": Donor(
        "combined_all4",
        "combined",
        DONOR_ROOT / "combined" / "ALLL_ICS_ALL4.pdsprj",
        "74HC00",
        "all families all4",
    ),
    "all4_2x": Donor(
        "combined_2x_all4",
        "combined",
        DONOR_ROOT / "combined" / "2X_ALLL_ICS_ALL4.pdsprj",
        "74HC00",
        "all families all4 two package",
    ),
    "all4_rlc": Donor(
        "combined_all4_rlc",
        "combined",
        DONOR_ROOT / "combined" / "ALLL_ICS_ALL4_RLC.pdsprj",
        "74HC00",
        "all families all4 with RCL",
        allow_bidir=True,
    ),
    "all4_rlc_2x": Donor(
        "combined_2x_all4_rlc",
        "combined",
        DONOR_ROOT / "combined" / "2X_ALLL_ICS_ALL4_RLC.pdsprj",
        "74HC00",
        "all families all4 with RCL two package",
        allow_bidir=True,
    ),
}


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def terminal_events(chunk: bytes) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True), (b"$TERBIDIR", False)):
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            length_pos = marker_pos + (17 if output_terminal else 16)
            label_pos = marker_pos + (18 if output_terminal else 17)
            length = chunk[length_pos]
            label = chunk[label_pos : label_pos + length].decode("ascii", errors="replace")
            events.append({"offset": marker_pos, "marker": marker.decode("ascii"), "label": label})
            pos = marker_pos + 1
    return sorted(events, key=lambda item: int(item["offset"]))


def donor_analysis(item: Donor) -> dict[str, object]:
    dsn = read_internal_file(item.path, "ROOT.DSN")
    cdb = read_internal_file(item.path, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    return {
        "key": item.key,
        "family": item.family,
        "path": str(item.path.relative_to(REPO)),
        "sha256": _sha256_bytes(item.path.read_bytes()),
        "size": item.path.stat().st_size,
        "expected_device": item.expected_device,
        "logic_role": item.logic_role,
        "notes": item.notes,
        "root_dsn_size": len(dsn),
        "root_dsn_sha256": _sha256_bytes(dsn),
        "root_cdb_size": len(cdb),
        "root_cdb_sha256": _sha256_bytes(cdb),
        "object_chunk_size": len(chunk),
        "object_chunk_sha256": _sha256_bytes(chunk),
        "object_chunk_marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "terminal_events": terminal_events(chunk),
    }


def patch_terminal_labels(chunk: bytes, replacements: dict[str, str]) -> tuple[bytes, list[dict[str, object]]]:
    out = bytearray(chunk)
    events: list[dict[str, object]] = []
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True), (b"$TERBIDIR", False)):
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            length_pos = marker_pos + (17 if output_terminal else 16)
            label_pos = marker_pos + (18 if output_terminal else 17)
            length = chunk[length_pos]
            old = chunk[label_pos : label_pos + length].decode("ascii", errors="replace")
            new = replacements.get(old)
            if new is not None:
                raw = new.encode("ascii")
                if len(raw) != length:
                    raise ValueError(f"Replacement {old!r}->{new!r} changes record size.")
                out[label_pos : label_pos + length] = raw
                events.append({"terminal_marker": marker.decode("ascii"), "offset": marker_pos, "old": old, "new": new})
            pos = marker_pos + 1
    return bytes(out), events


def label_replacements() -> dict[str, str]:
    replacements = {}
    for idx in range(4):
        replacements[f"A{idx}"] = f"C{idx}"
        replacements[f"B{idx}"] = f"D{idx}"
        replacements[f"Y{idx}"] = f"Z{idx}"
    return replacements


def static_issues(output: Path, *, expected: Donor, allow_bidir: bool, mutation_events: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if expected.family != "combined" and chunk.count(expected.expected_device.encode("ascii")) == 0:
        issues.append(f"expected device marker {expected.expected_device} missing")
    if expected.family == "74hc266" and chunk.count(b"74XOR2") == 0:
        issues.append("74HC266 donor expected to retain Proteus 74XOR2 function marker")
    if chunk.count(b"$TERBIDIR") and not allow_bidir:
        issues.append("unexpected bidirectional terminal marker in pure IC IO case")
    if chunk.count(b"VSOURCE") or chunk.count(b"CSOURCE") or chunk.count(b"VSINE"):
        issues.append("unexpected source marker in IC donor diagnostic")
    if chunk.count(b"LOGICSTATE") or chunk.count(b"LOGICPROBE"):
        issues.append("logicstate/probe visual component present")
    if mutation_events:
        for item in mutation_events:
            if chunk.count(str(item["new"]).encode("ascii")) == 0:
                issues.append(f"mutated label {item['new']} not present")
    if not cdb:
        issues.append("ROOT.CDB is empty")
    return issues


def write_transplant_case(
    case_id: str,
    item: Donor,
    description: str,
    *,
    replacements: dict[str, str] | None = None,
) -> dict[str, object]:
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(item.path, "ROOT.DSN")
    chunk = _extract_object_chunk(donor_dsn)
    mutation_events: list[dict[str, object]] = []
    method = "e001_transplant"
    if replacements:
        chunk, mutation_events = patch_terminal_labels(chunk, replacements)
        method = "e001_transplant_label_only"
    dsn, pointers = build_dsn(base_dsn, donor_dsn, chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    cdb = read_internal_file(item.path, "ROOT.CDB")
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    manifest = {
        "case_id": case_id,
        "description": description,
        "method": method,
        "family": item.family,
        "logic_role": item.logic_role,
        "donor_key": item.key,
        "donor_path": str(item.path.relative_to(REPO)),
        "allow_bidir": item.allow_bidir,
        "mutation_events": mutation_events,
        "section_pointers": pointers,
        "static_validation_issues": static_issues(
            output,
            expected=item,
            allow_bidir=item.allow_bidir,
            mutation_events=mutation_events,
        ),
        "marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "terminal_events": terminal_events(chunk),
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 8, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    all_donors = {**DONORS, **COMBINED_DONORS}
    for item in all_donors.values():
        if not item.path.exists():
            raise FileNotFoundError(item.path)
    analysis = {key: donor_analysis(item) for key, item in sorted(all_donors.items())}
    (DONOR_ROOT / "analysis_remaining_combinational_v1.json").write_text(
        json.dumps(analysis, indent=2) + "\n",
        encoding="utf-8",
    )

    cases: list[dict[str, object]] = []
    cases.append(write_transplant_case("T00_COMBINED_ALL4_E001", COMBINED_DONORS["all4"], "All four new families, one package each, transplanted into E001."))
    cases.append(write_transplant_case("T01_COMBINED_2X_ALL4_E001", COMBINED_DONORS["all4_2x"], "All four new families, two packages each, transplanted into E001."))
    cases.append(write_transplant_case("T02_COMBINED_ALL4_RLC_E001", COMBINED_DONORS["all4_rlc"], "All four new families plus RCL load, transplanted into E001."))
    cases.append(write_transplant_case("T03_COMBINED_2X_ALL4_RLC_E001", COMBINED_DONORS["all4_rlc_2x"], "All four new families with two-package scale and RCL load, transplanted into E001."))

    case_no = 10
    for family in ("74hc00", "74hc02", "74hc86", "74hc266"):
        role = FAMILY_INFO[family]["role"]
        cases.append(write_transplant_case(f"T{case_no:02d}_{family.upper()}_ALL4_E001", DONORS[f"{family}_m02"], f"{role} all-four donor transplanted into E001."))
        case_no += 1
        cases.append(write_transplant_case(f"T{case_no:02d}_{family.upper()}_ALL4_LABEL_ONLY", DONORS[f"{family}_m02"], f"{role} all-four donor with same-size terminal label mutation.", replacements=label_replacements()))
        case_no += 1
        cases.append(write_transplant_case(f"T{case_no:02d}_{family.upper()}_TWO_PACKAGES_E001", DONORS[f"{family}_m03"], f"{role} two-package donor transplanted into E001."))
        case_no += 1
        cases.append(write_transplant_case(f"T{case_no:02d}_{family.upper()}_LOGIC_CONSTANTS_PG", DONORS[f"{family}_m04"], f"{role} logic-constant power/ground donor transplanted into E001."))
        case_no += 1
        cases.append(write_transplant_case(f"T{case_no:02d}_{family.upper()}_RCL_LOAD", DONORS[f"{family}_m05"], f"{role} RCL load donor transplanted into E001."))
        case_no += 1

    summary = {
        "batch": "IC_REMAINING_COMBINATIONAL_V1_TEMP_2026_06_08",
        "purpose": "Donor reconstruction, E001 transplant, and label-only mutation diagnostics for 74HC00, 74HC02, 74HC86, and 74HC266.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "families": FAMILY_INFO,
        "user_test_order": [case["case_id"] for case in cases],
        "cases": cases,
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": len(cases)}, indent=2))


if __name__ == "__main__":
    main()
