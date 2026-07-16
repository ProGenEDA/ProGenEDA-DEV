"""Corrected no-terminal focused pack for displays and 4027.

V3 mistakes recorded from user feedback:
- ANB/CCR high display counts were synthesized from 1x/4x donors instead of
  being extracted from the mega donor.
- 4027 high counts were cloned from a 4x donor with rebuilt CDB rows, and
  K05/K15/K23 crashed.

V4 fixes:
- Keep standalone display and 4027 donors only as exact controls.
- Extract 1/3/5/15/23 display records from the user-provided mega donor.
- Extract 1/3/5/15/23 4027 packages from the user-provided mega donor.
- Preserve the full mega ROOT.CDB; do not synthesize CDB for high counts.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


HELPER_PATH = ROOT / "proteus/experiments/runners/2026-06-16/generate_mega_bare_separation_v1_temp.py"
DONOR_DIR = ROOT / "proteus/archive/donors/manual_downloads_20260616/mega_component_placer"
FOLLOWUP_DIR = DONOR_DIR / "display_4027_followup"
OUT_DIR = ROOT / "experiments/bare_display_4027_focus_v4_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_4027_FOCUS_V4_TEMP_2026_06_16.zip"

MEGA_NO_SOURCE = (
    DONOR_DIR
    / "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)

AN_BLUE_1 = FOLLOWUP_DIR / "7segcomANblue.pdsprj"
AN_BLUE_4 = FOLLOWUP_DIR / "4_7segcomANblue.pdsprj"
CC_RED_1 = FOLLOWUP_DIR / "7segcomcathred.pdsprj"
CC_RED_4 = FOLLOWUP_DIR / "4_7segcomcathred.pdsprj"
JK_4027_1 = FOLLOWUP_DIR / "4027.pdsprj"
JK_4027_2 = FOLLOWUP_DIR / "2_4027.pdsprj"
JK_4027_4 = FOLLOWUP_DIR / "4_4027.pdsprj"

COUNT_CHOICES = (1, 3, 5, 15, 23)
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")


@dataclass(frozen=True)
class RawRecord:
    start: int
    end: int
    data: bytes
    display_kind: str | None = None


def load_helper():
    spec = importlib.util.spec_from_file_location("mega_bare_v1_for_v4", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper script: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mega_bare_v1_for_v4"] = module
    spec.loader.exec_module(module)
    module.OUT_DIR = OUT_DIR
    return module


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def zip_dir(src: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with ZipFile(output, "w") as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            info = ZipInfo(path.relative_to(src).as_posix())
            info.compress_type = ZIP_DEFLATED
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o600 << 16
            zf.writestr(info, path.read_bytes())


def marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "7SEGCOMA",
        "7SEGCOMK",
        "7SEG-COM-ANODE",
        "7SEG-COM-AN-BLUE",
        "7SEG-COM-CATHODE",
        "7SEG-COM-CAT-BLUE",
        "7SEG-COM-CAT",
        "4027",
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def component_record_starts(chunk: bytes) -> list[int]:
    starts: list[int] = []
    pos = 0
    while True:
        pos = chunk.find(b"COMPONENT ID", pos)
        if pos < 0:
            break
        starts.append(max(0, pos - 51))
        pos += 1
    return starts


def component_records_from_chunk(chunk: bytes) -> list[RawRecord]:
    starts = component_record_starts(chunk)
    if not starts:
        return []
    final_end = len(chunk) - 1 if chunk.endswith(b"\xff") else len(chunk)
    starts.append(final_end)
    records: list[RawRecord] = []
    for index in range(len(starts) - 1):
        data = chunk[starts[index] : starts[index + 1]]
        records.append(RawRecord(start=starts[index], end=starts[index + 1], data=data))
    return records


def display_kind(data: bytes) -> str | None:
    if b"7SEGCOMA" in data or b"7SEG-COM-ANODE" in data or b"7SEG-COM-AN-BLUE" in data:
        return "common_anode"
    if b"7SEGCOMK" in data or b"7SEG-COM-CAT" in data or b"7SEG-COM-CATHODE" in data:
        return "common_cathode"
    return None


def mega_display_records(kind: str) -> list[RawRecord]:
    chunk = _extract_object_chunk(read_internal_file(MEGA_NO_SOURCE, "ROOT.DSN"))
    rows: list[RawRecord] = []
    for record in component_records_from_chunk(chunk):
        row_kind = display_kind(record.data)
        if row_kind == kind:
            rows.append(RawRecord(record.start, record.end, record.data, row_kind))
    return rows


def finalize_component_record(record: bytes, source_is_final: bool) -> tuple[bytes, bool]:
    if source_is_final:
        return record, False
    if not record.endswith(b"\x00"):
        raise ValueError("Cannot finalize selected display record: middle record does not end in 00.")
    return record[:-1], True


def display_chunk_from_mega(kind: str, count: int) -> tuple[bytes, dict[str, object]]:
    records = mega_display_records(kind)
    if len(records) < count:
        raise ValueError(f"Mega donor has only {len(records)} {kind} display records, need {count}.")
    selected = records[:count]
    # Determine final status against the original object chunk terminator.
    source_chunk = _extract_object_chunk(read_internal_file(MEGA_NO_SOURCE, "ROOT.DSN"))
    source_final_end = len(source_chunk) - 1 if source_chunk.endswith(b"\xff") else len(source_chunk)
    last = selected[-1]
    final_data, trimmed = finalize_component_record(last.data, last.end == source_final_end)
    chunk = b"\x00\x00" + b"".join(row.data for row in selected[:-1]) + final_data + b"\xff"
    return chunk, {
        "method": "mega donor individual display records with selected-last final conversion",
        "display_kind": kind,
        "source_record_count": len(records),
        "selected_record_starts": [row.start for row in selected],
        "trimmed_selected_last_record": trimmed,
    }


def write_forced_case(
    case_id: str,
    donor_path: Path,
    cdb: bytes,
    donor_dsn: bytes,
    object_chunk: bytes,
    description: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(donor_path, output, {"ROOT.DSN": dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs from requested chunk")
    if any(marker in final_chunk for marker in TERM_MARKERS):
        errors.append("terminal marker present")
    result = {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(donor_path.relative_to(ROOT)),
        "description": description,
        "object_chunk_size": len(final_chunk),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "pointers": pointers,
        "errors": errors,
    }
    if extra:
        result.update(extra)
    return result


def copy_exact_case(case_id: str, donor_path: Path, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(donor_path, output)
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(donor_path.relative_to(ROOT)),
        "description": description,
        "copy_exact": True,
        "object_chunk_size": len(chunk),
        "object_chunk_sha256": sha256_bytes(chunk),
        "marker_counts": marker_counts(chunk),
        "errors": [],
    }


def build_4027_from_mega(helper, count: int) -> tuple[bytes, dict[str, object]]:
    state = helper.load_donor(MEGA_NO_SOURCE)
    groups = state.groups_by_family.get("4027", [])
    if len(groups) < count:
        raise ValueError(f"Mega donor has only {len(groups)} 4027 packages, need {count}.")
    chunk, meta = helper.object_chunk_for(tuple(groups[:count]))
    meta = dict(meta)
    meta.update(
        {
            "method": "mega donor complete 4027 package groups, full mega CDB preserved",
            "source_package_count": len(groups),
            "selected_group_keys": [group.key for group in groups[:count]],
        }
    )
    return chunk, meta


def build_cases() -> dict[str, object]:
    helper = load_helper()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    cases: list[dict[str, object]] = []
    for case_id, donor_path, description in [
        ("D00_EXACT_AN_BLUE_1X", AN_BLUE_1, "Exact one standalone common-anode blue 7-segment donor."),
        ("D01_EXACT_AN_BLUE_4X", AN_BLUE_4, "Exact four standalone common-anode blue 7-segment donor."),
        ("D02_EXACT_CC_RED_1X", CC_RED_1, "Exact one standalone common-cathode red 7-segment donor."),
        ("D03_EXACT_CC_RED_4X", CC_RED_4, "Exact four standalone common-cathode red 7-segment donor."),
        ("K00_EXACT_4027_1X", JK_4027_1, "Exact one standalone 4027 donor."),
        ("K01_EXACT_4027_2X", JK_4027_2, "Exact two standalone 4027 donor."),
        ("K02_EXACT_4027_4X", JK_4027_4, "Exact four standalone 4027 donor."),
        ("M00_EXACT_MEGA_NO_SOURCE_COPY", MEGA_NO_SOURCE, "Exact mega no-source donor copy."),
    ]:
        cases.append(copy_exact_case(case_id, donor_path, description))

    mega_dsn = read_internal_file(MEGA_NO_SOURCE, "ROOT.DSN")
    mega_cdb = read_internal_file(MEGA_NO_SOURCE, "ROOT.CDB")

    for prefix, kind, label in [
        ("ANM", "common_anode", "mega common-anode display"),
        ("CCM", "common_cathode", "mega common-cathode display"),
    ]:
        for count in COUNT_CHOICES:
            chunk, meta = display_chunk_from_mega(kind, count)
            cases.append(
                write_forced_case(
                    f"{prefix}_{count:02d}X_DISPLAY_FROM_MEGA",
                    MEGA_NO_SOURCE,
                    mega_cdb,
                    mega_dsn,
                    chunk,
                    f"{count} x {label} records extracted from the mega donor.",
                    {"requested_count": count, **meta},
                )
            )

    for count in COUNT_CHOICES:
        chunk, meta = build_4027_from_mega(helper, count)
        cases.append(
            write_forced_case(
                f"K{count:02d}_4027_{count:02d}X_FROM_MEGA",
                MEGA_NO_SOURCE,
                mega_cdb,
                mega_dsn,
                chunk,
                f"{count} x 4027 packages extracted from the mega donor.",
                {"requested_count": count, **meta},
            )
        )

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_4027_focus_v4_temp_2026_06_16",
        "purpose": "Correct V3 component-specific mistakes by extracting high-count displays and 4027 packages from the mega donor instead of synthetic 4x-donor repetition.",
        "count_choices": list(COUNT_CHOICES),
        "case_count": len(cases),
        "static_issue_cases": issue_cases,
        "notes": [
            "Standalone common-cathode red donors are included as exact controls only.",
            "The mega donor's high-count common-cathode display records identify as 7SEG-COM-CAT-BLUE/7SEGCOMK, not the standalone red 7SEG-COM-CATHODE string.",
            "4027 high counts preserve the full mega ROOT.CDB and do not rebuild CDB rows.",
        ],
        "cases": cases,
    }


def main() -> None:
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(
        json.dumps(
            {
                "out_dir": str(OUT_DIR),
                "zip": str(ZIP_OUT),
                "cases": summary["case_count"],
                "static_issue_cases": summary["static_issue_cases"],
                "zip_sha256": sha256_file(ZIP_OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
