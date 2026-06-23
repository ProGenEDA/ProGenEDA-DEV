"""Mega-display acceptance pack after V8 Proteus feedback.

V8 user result:
- Every cathode "replace final byte" case failed.
- All remaining V8 cases worked.

Accepted paths under test here:
- Common-anode rows from the mega donor use the true donor-final anode row.
  If a 399-byte anode block-final row is selected as a middle row, trim its
  final two bytes to convert it to a normal 397-byte middle row.
- Common-cathode rows from the mega donor have no cathode-final row. Keep them
  as middle rows and terminate the stream with the true donor-final anode row
  as a sentinel.
- 4027 pair tests preserve original mega refs and full mega ROOT.CDB. No
  renumbering and no synthesized CDB rows.

This pack intentionally avoids every rejected final-byte replacement and
standalone display-repeat path.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


HELPER_PATH = ROOT / "tools/proteus_generation/2026-06-16/generate_mega_bare_separation_v1_temp.py"
DONOR_DIR = ROOT / "proteus_ic/donors/manual_downloads_20260616/mega_component_placer"
OUT_DIR = ROOT / "experiments/bare_display_mega_acceptance_v9_temp_2026_06_18"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_MEGA_ACCEPTANCE_V9_TEMP_2026_06_18.zip"

MEGA_NO_SOURCE = (
    DONOR_DIR
    / "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)

COUNT_CHOICES = (1, 3, 5, 15, 23)
PAIR_CHOICES = (
    (1, 1),
    (3, 3),
    (5, 5),
    (15, 15),
    (23, 23),
)
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
DISPLAY_RECORD_START = b"\x00\x08\xff\x00"
NORMAL_RECORD_START_RE = re.compile(
    rb"\xff[\x02-\x08]((?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+)|(?:Q\d+)|(?:D\d+)|(?:V\d+)|(?:I\d+))"
)


def load_helper():
    spec = importlib.util.spec_from_file_location("mega_bare_v1_for_v9", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper script: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mega_bare_v1_for_v9"] = module
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
    display_starts = [
        start
        for start in all_starts
        if chunk[start : start + 4] == DISPLAY_RECORD_START and b"7SEG" in chunk[start : start + 520]
    ]
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


def anode_block_final_as_middle(row: bytes) -> bytes:
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


def anode_rows_trim_rule(count: int) -> tuple[list[bytes], dict[str, object]]:
    rows = mega_display_records("anode")
    if count < 1 or len(rows) < count:
        raise ValueError(f"Need {count} anode rows, found {len(rows)}.")
    selected: list[bytes] = []
    selected_indexes: list[int | str] = []
    for index in range(count - 1):
        row = rows[index]
        if len(row) == 399 and not row.endswith(b"\xff"):
            selected.append(anode_block_final_as_middle(row))
            selected_indexes.append(f"{index}:trim2")
        else:
            selected.append(row)
            selected_indexes.append(index)
    selected.append(rows[-1])
    selected_indexes.append(f"{len(rows) - 1}:true_final")
    return selected, {
        "method": "accepted mega anode trim rule: trim any 399-byte middle block-final rows, then use true donor-final anode row",
        "selected_indexes": selected_indexes,
        "selected_count": count,
    }


def cathode_rows_with_anode_sentinel(count: int) -> tuple[list[bytes], dict[str, object]]:
    cathode_rows = mega_display_records("cathode")
    anode_rows = mega_display_records("anode")
    if count < 1 or len(cathode_rows) < count:
        raise ValueError(f"Need {count} cathode rows, found {len(cathode_rows)}.")
    selected = cathode_rows[:count] + [anode_rows[-1]]
    return selected, {
        "method": "accepted mega cathode rule candidate: cathode middle rows plus true donor-final anode sentinel",
        "selected_indexes": list(range(count)) + [f"anode:{len(anode_rows) - 1}:true_final"],
        "selected_count": count + 1,
        "requested_cathode_count": count,
        "sentinel_anode_count": 1,
    }


def cathode_anode_pair_rows(cathode_count: int, anode_count: int) -> tuple[list[bytes], dict[str, object]]:
    cathode_rows = mega_display_records("cathode")
    anode_rows, anode_meta = anode_rows_trim_rule(anode_count)
    if len(cathode_rows) < cathode_count:
        raise ValueError(f"Need {cathode_count} cathode rows, found {len(cathode_rows)}.")
    selected = cathode_rows[:cathode_count] + anode_rows
    return selected, {
        "method": "accepted display pair rule: cathode middle rows followed by accepted anode trim-rule rows",
        "requested_cathode_count": cathode_count,
        "requested_anode_count": anode_count,
        "cathode_selected_indexes": list(range(cathode_count)),
        "anode": anode_meta,
    }


def complete_4027_groups(helper):
    state = helper.load_donor(MEGA_NO_SOURCE)
    return [group for group in state.groups_by_family["4027"] if len(group.refs) == 2]


def rows_after_4027(helper, count: int, display_rows: list[bytes]) -> tuple[bytes, dict[str, object]]:
    groups = complete_4027_groups(helper)
    if len(groups) < count:
        raise ValueError(f"Need {count} complete 4027 groups, found {len(groups)}.")
    prefix = b"\x00\x00" + b"".join(group.data for group in groups[:count])
    chunk = prefix + build_display_chunk(display_rows)
    if not chunk.endswith(b"\xff"):
        raise ValueError("4027/display combined chunk does not end in FF.")
    return chunk, {
        "method": "4027/display pair: original-ref complete 4027 groups as middle records, followed by accepted display finalization",
        "selected_4027_group_keys": [group.key for group in groups[:count]],
        "requested_4027_count": count,
    }


def build_4027_mega_direct(helper, count: int) -> tuple[bytes, dict[str, object]]:
    groups = complete_4027_groups(helper)
    if len(groups) < count:
        raise ValueError(f"Need {count} complete 4027 groups, found {len(groups)}.")
    chunk, meta = helper.object_chunk_for(tuple(groups[:count]))
    return chunk, {
        "method": "accepted direct 4027 rule: complete mega 4027 package groups with original refs and full mega CDB",
        "selected_4027_group_keys": [group.key for group in groups[:count]],
        **meta,
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
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "pointers": pointers,
        "errors": errors,
    }
    if extra:
        result.update(extra)
    return result


def build_cases() -> dict[str, object]:
    helper = load_helper()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    mega_dsn = read_internal_file(MEGA_NO_SOURCE, "ROOT.DSN")
    mega_cdb = read_internal_file(MEGA_NO_SOURCE, "ROOT.CDB")
    cases: list[dict[str, object]] = []

    for count in COUNT_CHOICES:
        rows, meta = anode_rows_trim_rule(count)
        cases.append(
            write_case(
                f"AN9_{count:02d}_MEGA_ANODE_TRIM_RULE",
                MEGA_NO_SOURCE,
                mega_cdb,
                mega_dsn,
                build_display_chunk(rows),
                f"{count} common-anode displays from the mega donor using the accepted trim rule.",
                {"requested_anode_count": count, **meta},
            )
        )

    for count in COUNT_CHOICES:
        rows, meta = cathode_rows_with_anode_sentinel(count)
        cases.append(
            write_case(
                f"CC9_{count:02d}_MEGA_CATHODE_ANODE_SENTINEL",
                MEGA_NO_SOURCE,
                mega_cdb,
                mega_dsn,
                build_display_chunk(rows),
                f"{count} common-cathode blue displays from mega, terminated by the true donor-final anode sentinel.",
                {"requested_cathode_count": count, **meta},
            )
        )

    for cathode_count, anode_count in PAIR_CHOICES:
        rows, meta = cathode_anode_pair_rows(cathode_count, anode_count)
        cases.append(
            write_case(
                f"PAIR9_CC{cathode_count:02d}_AN{anode_count:02d}_DISPLAY_PAIR",
                MEGA_NO_SOURCE,
                mega_cdb,
                mega_dsn,
                build_display_chunk(rows),
                f"{cathode_count} common-cathode blue displays plus {anode_count} common-anode displays from mega.",
                meta,
            )
        )

    for count in COUNT_CHOICES:
        chunk, meta = build_4027_mega_direct(helper, count)
        cases.append(
            write_case(
                f"K9_{count:02d}_4027_DIRECT_CONTROL",
                MEGA_NO_SOURCE,
                mega_cdb,
                mega_dsn,
                chunk,
                f"{count} accepted direct 4027 mega groups, included as pair baseline.",
                {"requested_4027_count": count, **meta},
            )
        )

    for display_count, k_count in PAIR_CHOICES:
        rows, display_meta = anode_rows_trim_rule(display_count)
        chunk, k_meta = rows_after_4027(helper, k_count, rows)
        cases.append(
            write_case(
                f"PAIR9_K{k_count:02d}_AN{display_count:02d}_4027_ANODE",
                MEGA_NO_SOURCE,
                mega_cdb,
                mega_dsn,
                chunk,
                f"{k_count} accepted 4027 groups paired with {display_count} common-anode displays.",
                {"display": display_meta, **k_meta},
            )
        )

    for display_count, k_count in PAIR_CHOICES:
        rows, display_meta = cathode_rows_with_anode_sentinel(display_count)
        chunk, k_meta = rows_after_4027(helper, k_count, rows)
        cases.append(
            write_case(
                f"PAIR9_K{k_count:02d}_CC{display_count:02d}_4027_CATHODE",
                MEGA_NO_SOURCE,
                mega_cdb,
                mega_dsn,
                chunk,
                f"{k_count} accepted 4027 groups paired with {display_count} common-cathode blue displays and one anode sentinel.",
                {"display": display_meta, **k_meta},
            )
        )

    rows, display_meta = cathode_anode_pair_rows(23, 23)
    chunk, k_meta = rows_after_4027(helper, 23, rows)
    cases.append(
        write_case(
            "PAIR9_K23_CC23_AN23_STRESS",
            MEGA_NO_SOURCE,
            mega_cdb,
            mega_dsn,
            chunk,
            "Stress pair-style case: 23 accepted 4027 groups plus 23 cathode and 23 anode displays.",
            {"display": display_meta, **k_meta},
        )
    )

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_mega_acceptance_v9_temp_2026_06_18",
        "purpose": "Accepted mega-only display rules and focused pair tests after V8 rejected cathode final-byte replacement.",
        "rejected_paths_removed": [
            "cathode final-byte replacement",
            "cathode append-FF",
            "standalone display donor repetition",
            "4027 renumbering",
            "4027 synthesized CDB",
        ],
        "case_count": len(cases),
        "static_issue_cases": issue_cases,
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
