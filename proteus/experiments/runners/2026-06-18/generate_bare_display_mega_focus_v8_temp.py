"""Mega-display-only diagnostics after V7 user feedback.

V7 user results:
- All direct 4027 original-ref/full-mega-CDB cases worked. Do not retest 4027
  here.
- ANF_21, ANF_22, ANF_23, and ANP_23 failed with a DLL error.
- ANP_15 and all CCB cathode cases opened/simulated with bad-object-record
  warnings.
- CCR donor-repeat cases above four displays showed only four displays. Donor
  repetition is therefore removed from this path.

This V8 pack only mutates records selected from the mega donor. It does not use
the standalone 1x/4x display donors except as exact controls.

New display findings under test:
- Mega anode records are organized in 20-row blocks. Normal rows are 397 bytes;
  rows 19, 39, 59... are 399-byte block-final rows; the true donor-final row
  also ends in FF.
- V7 failed when a 399-byte anode block-final row was used as a middle row.
  V8 tests converting that block-final row into a middle row by trimming its
  final two bytes, and separately tests skipping the block-final row.
- Mega cathode records have no true cathode-final row because the cathode block
  is followed by anode rows in the donor. V8 tests replacing the final byte
  with FF instead of appending FF, plus one cathode+anode sentinel diagnostic.

This is a narrow diagnostic pack, not a component matrix.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


DONOR_DIR = ROOT / "proteus/archive/donors/manual_downloads_20260616/mega_component_placer"
OUT_DIR = ROOT / "experiments/bare_display_mega_focus_v8_temp_2026_06_18"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_MEGA_FOCUS_V8_TEMP_2026_06_18.zip"

MEGA_NO_SOURCE = (
    DONOR_DIR
    / "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)

TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
DISPLAY_RECORD_START = b"\x00\x08\xff\x00"
NORMAL_RECORD_START_RE = re.compile(
    rb"\xff[\x02-\x08]((?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+)|(?:Q\d+)|(?:D\d+)|(?:V\d+)|(?:I\d+))"
)


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
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def display_kind(record: bytes) -> str | None:
    if b"7SEGCOMA" in record or b"7SEG-COM-ANODE" in record or b"7SEG-COM-AN-BLUE" in record:
        return "anode"
    if b"7SEGCOMK" in record or b"7SEG-COM-CAT" in record or b"7SEG-COM-CATHODE" in record:
        return "cathode"
    return None


def all_object_starts(chunk: bytes) -> list[int]:
    starts: set[int] = set()
    pos = 0
    while True:
        pos = chunk.find(DISPLAY_RECORD_START, pos)
        if pos < 0:
            break
        if b"7SEG" in chunk[pos : pos + 520]:
            starts.add(pos)
        pos += 1
    for match in NORMAL_RECORD_START_RE.finditer(chunk):
        start = match.start()
        if b"COMPONENT ID" in chunk[start : start + 240]:
            starts.add(start)
    return sorted(starts)


def split_display_records(path: Path) -> list[bytes]:
    chunk = _extract_object_chunk(read_internal_file(path, "ROOT.DSN"))
    all_starts = all_object_starts(chunk)
    display_starts = [start for start in all_starts if chunk[start : start + 4] == DISPLAY_RECORD_START and b"7SEG" in chunk[start : start + 520]]
    if not display_starts:
        return []
    boundaries = all_starts + [len(chunk)]
    rows: list[bytes] = []
    for start in display_starts:
        next_start = next(boundary for boundary in boundaries if boundary > start)
        rows.append(chunk[start:next_start])
    return rows


def mega_display_records(kind: str) -> list[bytes]:
    records = split_display_records(MEGA_NO_SOURCE)
    selected = [record for record in records if display_kind(record) == kind]
    if not selected:
        raise ValueError(f"No mega display records found for {kind}.")
    return selected


def display_chunk_mega_anode(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("anode")
    if len(rows) < count:
        raise ValueError(f"Need {count} anode rows, found {len(rows)}.")
    # Use the donor-final anode row as the final row, matching 4x display donor behavior.
    chosen = rows[: max(0, count - 1)] + [rows[-1]]
    return b"".join(chosen), {
        "method": "prefixless mega display rows; selected last row is donor-final anode record",
        "source_rows": len(rows),
        "selected_count": len(chosen),
    }


def display_chunk_mega_anode_append_ff(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("anode")
    if len(rows) < count:
        raise ValueError(f"Need {count} anode rows, found {len(rows)}.")
    body = b"".join(rows[:count])
    if not body.endswith(b"\xff"):
        body += b"\xff"
    return body, {
        "method": "prefixless mega anode rows with explicit FF terminator; threshold diagnostic only",
        "source_rows": len(rows),
        "selected_count": count,
    }


def display_chunk_mega_cathode_with_append_ff(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("cathode")
    if len(rows) < count:
        raise ValueError(f"Need {count} cathode rows, found {len(rows)}.")
    body = b"".join(rows[:count])
    if not body.endswith(b"\xff"):
        body += b"\xff"
    return body, {
        "method": "prefixless mega cathode rows with explicit FF terminator",
        "source_rows": len(rows),
        "selected_count": count,
    }


def display_chunk_mega_cathode_blue_final(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("cathode")
    if len(rows) < count:
        raise ValueError(f"Need {count} cathode rows, found {len(rows)}.")
    chosen = rows[: max(0, count - 1)] + [rows[-1]]
    return b"".join(chosen), {
        "method": "prefixless mega cathode rows; selected last row is donor-final blue cathode record",
        "source_rows": len(rows),
        "selected_count": len(chosen),
        "all_red": False,
    }


def row_with_final_ff(row: bytes) -> bytes:
    if row.endswith(b"\xff"):
        return row
    if not row.endswith(b"\x00"):
        raise ValueError("Expected display row to end in 00 before final-byte conversion.")
    return row[:-1] + b"\xff"


def anode_block_final_as_middle(row: bytes) -> bytes:
    # Mega anode block-final rows are 399 bytes. Normal middle rows are 397 bytes.
    if len(row) != 399 or row.endswith(b"\xff"):
        raise ValueError("Expected a non-final 399-byte anode block-final row.")
    if not row.endswith(b"\x00\x00"):
        raise ValueError("Expected block-final anode row to end in 00 00.")
    return row[:-2]


def build_display_chunk(rows: list[bytes]) -> bytes:
    chunk = b"".join(rows)
    if not chunk.endswith(b"\xff"):
        raise ValueError("Generated display object chunk does not end in FF.")
    return chunk


def anode_global_final(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("anode")
    chosen = rows[: count - 1] + [rows[-1]]
    return build_display_chunk(chosen), {
        "method": "V7 mega anode control: first count-1 rows plus true donor-final anode row",
        "selected_indexes": list(range(count - 1)) + [len(rows) - 1],
        "selected_count": count,
    }


def anode_local_block0_final(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("anode")
    if count > 20:
        raise ValueError("Local block0 final is defined only up to 20 displays.")
    chosen = rows[: count - 1] + [row_with_final_ff(rows[19])]
    return build_display_chunk(chosen), {
        "method": "mega anode block0 only; row 19 converted to stream-final by replacing final byte with FF",
        "selected_indexes": list(range(count - 1)) + [19],
        "selected_count": count,
    }


def anode_trim_block_final(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("anode")
    if count <= 20:
        raise ValueError("Trim-block-final diagnostic is for counts above 20.")
    middle_needed = count - 1
    selected: list[bytes] = []
    selected_indexes: list[int | str] = []
    for index in range(middle_needed):
        row = rows[index]
        if (index + 1) % 20 == 0 and len(row) == 399:
            selected.append(anode_block_final_as_middle(row))
            selected_indexes.append(f"{index}:trim2")
        else:
            selected.append(row)
            selected_indexes.append(index)
    selected.append(rows[-1])
    selected_indexes.append(len(rows) - 1)
    return build_display_chunk(selected), {
        "method": "mega anode rows with any 399-byte block-final middle row trimmed by two bytes, then true donor-final row",
        "selected_indexes": selected_indexes,
        "selected_count": count,
    }


def anode_skip_block_final(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("anode")
    selected: list[bytes] = []
    selected_indexes: list[int] = []
    index = 0
    while len(selected) < count - 1:
        if (index + 1) % 20 == 0:
            index += 1
            continue
        selected.append(rows[index])
        selected_indexes.append(index)
        index += 1
    selected.append(rows[-1])
    selected_indexes.append(len(rows) - 1)
    return build_display_chunk(selected), {
        "method": "mega anode rows skipping 399-byte block-final middle rows, then true donor-final row",
        "selected_indexes": selected_indexes,
        "selected_count": count,
    }


def cathode_replace_final_byte(count: int) -> tuple[bytes, dict[str, object]]:
    rows = mega_display_records("cathode")
    chosen = rows[: count - 1] + [row_with_final_ff(rows[count - 1])]
    return build_display_chunk(chosen), {
        "method": "mega cathode rows with selected last cathode row made final by replacing last byte with FF",
        "selected_indexes": list(range(count)),
        "selected_count": count,
    }


def cathode_with_anode_sentinel(count: int) -> tuple[bytes, dict[str, object]]:
    cathode_rows = mega_display_records("cathode")
    anode_rows = mega_display_records("anode")
    chosen = cathode_rows[:count] + [anode_rows[-1]]
    return build_display_chunk(chosen), {
        "method": "mega cathode diagnostic with true donor-final anode sentinel; visually includes one extra anode display",
        "selected_indexes": list(range(count)) + [f"anode:{len(anode_rows)-1}"],
        "selected_count": count + 1,
        "requested_cathode_count": count,
    }


def write_case(
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


def build_cases() -> dict[str, object]:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    cases: list[dict[str, object]] = []
    mega_dsn = read_internal_file(MEGA_NO_SOURCE, "ROOT.DSN")
    mega_cdb = read_internal_file(MEGA_NO_SOURCE, "ROOT.CDB")

    for count in (15, 20):
        chunk, meta = anode_global_final(count)
        cases.append(write_case(f"AN8_G{count:02d}_GLOBAL_FINAL_CONTROL", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} mega anode control using the previously accepted global donor-final row.", {"requested_count": count, **meta}))

    for count in (15, 20):
        chunk, meta = anode_local_block0_final(count)
        cases.append(write_case(f"AN8_L{count:02d}_LOCAL_BLOCK0_FINAL", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} mega anode rows from first 20-row block with local row-19 finalization.", {"requested_count": count, **meta}))

    for count in (21, 22, 23):
        chunk, meta = anode_trim_block_final(count)
        cases.append(write_case(f"AN8_T{count:02d}_TRIM_BLOCK_FINAL", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} mega anode rows with block-final middle rows trimmed to normal middle-row length.", {"requested_count": count, **meta}))

    for count in (21, 23):
        chunk, meta = anode_skip_block_final(count)
        cases.append(write_case(f"AN8_S{count:02d}_SKIP_BLOCK_FINAL", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} mega anode rows skipping 399-byte block-final middle records.", {"requested_count": count, **meta}))

    for count in (1, 3, 5, 15, 23):
        chunk, meta = cathode_replace_final_byte(count)
        cases.append(write_case(f"CC8_R{count:02d}_REPLACE_FINAL_BYTE", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} mega cathode blue rows with final byte replaced by FF.", {"requested_count": count, **meta}))

    chunk, meta = cathode_with_anode_sentinel(23)
    cases.append(write_case("CC8_A23_CATHODE_WITH_ANODE_SENTINEL", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, "23 mega cathode blue rows followed by the true donor-final anode row as a sentinel.", {"requested_count": 23, **meta}))

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_mega_focus_v8_temp_2026_06_18",
        "purpose": "Mega-display-only diagnostics after V7: anode 20-row block-final conversion and cathode final-byte replacement.",
        "case_count": len(cases),
        "static_issue_cases": issue_cases,
        "cases": cases,
    }


def main() -> None:
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": summary["case_count"], "static_issue_cases": summary["static_issue_cases"], "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
