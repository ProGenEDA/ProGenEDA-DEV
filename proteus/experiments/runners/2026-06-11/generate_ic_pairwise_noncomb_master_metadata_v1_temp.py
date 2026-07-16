"""Generate non-combinational IC pair probes from a Proteus-created master donor.

The prior non-combinational pair probe rebuilt CDB rows from two solo donors.
User testing rejected that path for sequential-to-sequential pairs. The new
manual ``alot_of_ics`` donor contains many sequential families in one
Proteus-created project with one coherent CDB/device metadata set.

This diagnostic pack therefore keeps that master metadata whole and emits only
selected master-native object records. It deliberately does not synthesize CDB
rows, rewrite CDB refs, or splice solo sequential IC records.
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

from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes
from proteusgen.templates import FixtureRegistry


REPO = Path(__file__).resolve().parents[3]
CDB_V2_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_v2_metadata_temp.py"
MASTER_DONOR = REPO / "proteus_ic" / "donors" / "mixed_large_20260611" / "alot_of_ics.pdsprj"

OUT_ROOT = REPO / "experiments" / "ic_pairwise_noncomb_master_metadata_v1_temp_2026_06_11"
ARCHIVE_PATH = REPO / "experiments" / "IC_PAIRWISE_NONCOMB_MASTER_METADATA_V1_TEMP_2026_06_11.zip"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


cdb_v2 = _load_module("mixed_ic_cdb_v2_for_noncomb_master_v1", CDB_V2_SCRIPT)
seq = cdb_v2.seq


MASTER_REFS = {
    "74HC00": "U1:A",
    "74HC02": "U2:A",
    "74HC08": "U3:A",
    "74HC32": "U4:A",
    "74HC74": "U5:A",
    "74HC76": "U6:A",
    "74HC85": "U7",
    "74HC86": "U8:A",
    "74HC157": "U9",
    "74HC160": "U10",
    "74HC161": "U11",
    "74HC163": "U12",
    "74HC165": "U13",
    "74HC174": "U14",
    "74HC192": "U15",
    "74HC193": "U16",
    "74HC266": "U17:A",
    "74HC273": "U18",
    "74HC595": "U19",
    "4017": "U20",
    "4020": "U21",
    "74HC4024": "U22",
    "4027": "U23:A",
    "74HC4040": "U24",
    "74HC4060": "U25",
    "4518": "U26:A",
    "74HC4520": "U27:A",
    "7490": "U28",
}

MARKER_FOR_FAMILY = {
    "7490": "7490",
    "74HC160": "74HC160",
    "74HC161": "74HC161",
    "74HC163": "74HC163",
    "74HC192": "74HC192",
    "74HC193": "74HC193",
    "4017": "4017",
    "4020": "4020",
    "74HC4024": "4024",
    "74HC4040": "4040",
    "74HC4060": "4060",
    "4518": "4518",
    "74HC4520": "4520",
    "74HC74": "74HC74",
    "74HC76": "74HC76",
    "74HC174": "74HC174",
    "74HC273": "74HC273",
    "4027": "4027",
    "74HC85": "74HC85",
    "74HC157": "74HC157",
    "74HC165": "74HC165",
    "74HC595": "74HC595",
}


@dataclass(frozen=True)
class MasterCase:
    case_id: str
    description: str
    families: tuple[str, ...]


CASES = (
    MasterCase("T00_EXACT_MASTER_ALOT_OF_ICS_REPACK", "Byte-level donor control copied unchanged.", ()),
    MasterCase("T01_7490_74HC160_MASTER_RECORDS", "Former noncomb probe S08+S09 using master-native records.", ("7490", "74HC160")),
    MasterCase("T02_7490_74HC161_MASTER_RECORDS", "Former noncomb probe S08+S10 using master-native records.", ("7490", "74HC161")),
    MasterCase("T03_7490_74HC192_MASTER_RECORDS", "Former noncomb probe S08+S12 using master-native records.", ("7490", "74HC192")),
    MasterCase("T04_7490_4017_MASTER_RECORDS", "Former noncomb probe S08+S14 using master-native records.", ("7490", "4017")),
    MasterCase("T05_7490_74HC4024_MASTER_RECORDS", "Former noncomb probe S08+S16 using master-native records.", ("7490", "74HC4024")),
    MasterCase("T06_7490_74HC595_MASTER_RECORDS", "Former noncomb probe S08+S29 using master-native records.", ("7490", "74HC595")),
    MasterCase("T07_4020_74HC174_MASTER_RECORDS", "Former noncomb probe S15+S21 using master-native records.", ("4020", "74HC174")),
    MasterCase("T08_74HC174_74HC273_MASTER_RECORDS", "Former noncomb probe S21+S22 using master-native records.", ("74HC174", "74HC273")),
    MasterCase("T09_74HC174_4027_MASTER_RECORDS", "Former noncomb probe S21+S23 using master-native records.", ("74HC174", "4027")),
    MasterCase("T10_74HC174_74HC85_MASTER_RECORDS", "Former noncomb probe S21+S24 using master-native records.", ("74HC174", "74HC85")),
    MasterCase("T11_74HC174_74HC157_MASTER_RECORDS", "Former noncomb probe S21+S26 using master-native records.", ("74HC174", "74HC157")),
    MasterCase("T12_74HC174_74HC595_MASTER_RECORDS", "Former noncomb probe S21+S29 using master-native records.", ("74HC174", "74HC595")),
    MasterCase("T13_74HC273_74HC595_MASTER_RECORDS", "Former noncomb probe S22+S29 using master-native records.", ("74HC273", "74HC595")),
    MasterCase("T14_74HC174_74HC4060_MASTER_RECORDS", "Former noncomb probe S21+S32/S33 using master-native records.", ("74HC174", "74HC4060")),
    MasterCase("T15_74HC273_74HC4060_MASTER_RECORDS", "Former noncomb probe S22+S32/S33 using master-native records.", ("74HC273", "74HC4060")),
    MasterCase("T16_74HC192_74HC193_MASTER_RECORDS", "Up/down counter pair from the master donor.", ("74HC192", "74HC193")),
    MasterCase("T17_4017_4020_MASTER_RECORDS", "Divider pair from the master donor.", ("4017", "4020")),
    MasterCase("T18_74HC4040_74HC4060_MASTER_RECORDS", "Late divider pair from the master donor.", ("74HC4040", "74HC4060")),
    MasterCase("T19_74HC74_74HC76_MASTER_RECORDS", "Flip-flop pair from the master donor.", ("74HC74", "74HC76")),
    MasterCase("T20_4518_74HC4520_MASTER_RECORDS", "Dual-counter family probe from the master donor.", ("4518", "74HC4520")),
    MasterCase("T21_SYNC_COUNTERS_4_MASTER_RECORDS", "Four synchronous counter records from the master donor.", ("74HC160", "74HC161", "74HC163", "74HC192")),
    MasterCase("T22_DIVIDERS_5_MASTER_RECORDS", "Five divider/counter records from the master donor.", ("4017", "4020", "74HC4024", "74HC4040", "74HC4060")),
)

UNSUPPORTED_FROM_OLD_PROBES = (
    ("S08", "S30", "7490 + NE555", "Master all-IC donor has 7490 but no NE555 row."),
    ("S21", "S25", "74HC174 + 74HC283", "Master all-IC donor has 74HC174 but no 74HC283 row."),
    ("S21", "S27", "74HC174 + 7447/74HC47", "Master all-IC donor has 74HC174 but no 7447 row."),
    ("S22", "S27", "74HC273 + 7447/74HC47", "Master all-IC donor has 74HC273 but no 7447 row."),
)


def master_record_slices(chunk: bytes) -> dict[str, bytes]:
    starts: list[tuple[int, str]] = []
    for match in re.finditer(rb"\xff([\x02-\x08])(U\d+(?::[A-F])?)", chunk):
        starts.append((match.start(), match.group(2).decode("ascii")))
    records: dict[str, bytes] = {}
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
        records[ref] = chunk[start:end]
    missing = sorted(set(MASTER_REFS.values()) - set(records))
    if missing:
        raise RuntimeError(f"Master donor did not expose expected component records: {missing}")
    return records


def master_device_section() -> dict[str, object]:
    donor_dsn = read_internal_file(MASTER_DONOR, "ROOT.DSN")
    section = bytearray(seq._device_section(donor_dsn))
    return {
        "donor_key": "mixed_large_20260611_master",
        "donor": str(MASTER_DONOR.relative_to(REPO)),
        "section": section,
        "old_tail_pointer": int.from_bytes(section[-4:], "little") if len(section) >= 4 else None,
        "size": len(section),
    }


def build_project_from_master_records(case: MasterCase, output: Path) -> dict[str, object]:
    master_dsn = read_internal_file(MASTER_DONOR, "ROOT.DSN")
    master_cdb = read_internal_file(MASTER_DONOR, "ROOT.CDB")
    master_chunk = _extract_object_chunk(master_dsn)
    records = master_record_slices(master_chunk)
    selected_records = [records[MASTER_REFS[family]] for family in case.families]
    object_chunk = master_chunk[:2] + b"".join(selected_records) + b"\xff"

    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = cdb_v2.build_dsn_with_multi_device_sections(
        read_internal_file(base.path, "ROOT.DSN"),
        master_dsn,
        object_chunk,
        [master_device_section()],
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": master_cdb,
        },
    )

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_cdb = read_internal_file(output, "ROOT.CDB")
    final_chunk = _extract_object_chunk(final_dsn)
    issues: list[str] = []
    for family in case.families:
        marker = MARKER_FOR_FAMILY[family].encode("ascii")
        if marker not in final_chunk:
            issues.append(f"missing selected marker {MARKER_FOR_FAMILY[family]}")
        if marker not in final_cdb:
            issues.append(f"master CDB missing marker {MARKER_FOR_FAMILY[family]}")
    if not final_chunk.startswith(b"\x00\x00\xff"):
        issues.append("master-record object chunk prefix changed")
    if final_chunk[-1:] != b"\xff":
        issues.append("object chunk final terminator missing")
    if final_cdb != master_cdb:
        issues.append("ROOT.CDB was not copied byte-identical from master donor")
    return {
        "case_id": case.case_id,
        "description": case.description,
        "families": case.families,
        "master_refs": {family: MASTER_REFS[family] for family in case.families},
        "metadata_policy": "copy complete master ROOT.CDB and complete master device section; emit selected master-native object records only",
        "section_pointers": pointers,
        "marker_counts": {
            family: final_chunk.count(MARKER_FOR_FAMILY[family].encode("ascii"))
            for family in case.families
        },
        "cdb_marker_counts": {
            family: final_cdb.count(MARKER_FOR_FAMILY[family].encode("ascii"))
            for family in case.families
        },
        "terminal_counts": {
            "$TERBIDIR": final_chunk.count(b"$TERBIDIR"),
            "$TERINPUT": final_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": final_chunk.count(b"$TEROUTPUT"),
            "$TERPOWER": final_chunk.count(b"$TERPOWER"),
            "$TERGROUND": final_chunk.count(b"$TERGROUND"),
        },
        "object_chunk_size": len(final_chunk),
        "static_validation_issues": issues,
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(final_dsn),
            "ROOT.CDB": _sha256_bytes(final_cdb),
            "object_chunk": _sha256_bytes(final_chunk),
        },
    }


def write_case(case: MasterCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    if not case.families:
        shutil.copy2(MASTER_DONOR, output)
        manifest = {
            "case_id": case.case_id,
            "description": case.description,
            "families": case.families,
            "metadata_policy": "byte-level donor control copied unchanged from mixed_large_20260611/alot_of_ics.pdsprj",
            "static_validation_issues": [],
            "output_hashes": {"project": _sha256_bytes(output.read_bytes())},
        }
    else:
        manifest = build_project_from_master_records(case, output)
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_donor_request_file() -> None:
    lines = [
        "Sequential-pair donor requests if the master-metadata V1 pack still fails",
        "",
        "Reason: mixed_large_20260611/alot_of_ics.pdsprj does not contain these specific family rows.",
        "Please create small manual projects with bidirectional pin terminals for each pair below.",
        "",
    ]
    for left, right, combo, reason in UNSUPPORTED_FROM_OLD_PROBES:
        lines.append(f"- {left}+{right}: {combo}. {reason}")
    lines.extend(
        [
            "",
            "Preferred donor shape:",
            "- one project per pair",
            "- both ICs visible",
            "- bider terminals attached to every visible pin",
            "- no RLC needed unless the pair only opens with a passive load",
            "- save in Proteus 8.13 after opening once",
            "",
        ]
    )
    (OUT_ROOT / "DONOR_REQUESTS_IF_V1_FAILS.txt").write_text("\n".join(lines), encoding="utf-8")


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 11, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests = [write_case(case) for case in CASES]
    write_donor_request_file()
    static_issue_cases = {
        item["case_id"]: item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_PAIRWISE_NONCOMB_MASTER_METADATA_V1_TEMP_2026_06_11",
        "purpose": "Retry failed sequential/non-combinational pairs by using selected records from a Proteus-created all-IC master donor and copying master metadata whole.",
        "status": "temporary_pending_user_proteus_testing",
        "master_donor": str(MASTER_DONOR.relative_to(REPO)),
        "case_count": len(manifests),
        "static_issue_cases": static_issue_cases,
        "unsupported_from_old_probe_count": len(UNSUPPORTED_FROM_OLD_PROBES),
        "cases": manifests,
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
                "case_count": len(manifests),
                "static_issue_cases": static_issue_cases,
                "donor_request_file": str(OUT_ROOT / "DONOR_REQUESTS_IF_V1_FAILS.txt"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
