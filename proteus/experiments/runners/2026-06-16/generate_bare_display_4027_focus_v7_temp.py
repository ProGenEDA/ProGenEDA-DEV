"""Display and 4027 component-specific diagnostics after V6 user feedback.

V4 failures reported by user:
- All ANM/CCM generated display cases failed.
- K03 and later generated 4027 cases failed.

Confirmed V4 mistakes:
- Display records were wrapped in the generic 00 00 + records + FF envelope.
  Pure display donors use direct 00 08 FF 00... records instead.
- Display splitting used COMPONENT-ID offsets; this is unsafe at family/block
  boundaries. Use the real display record signature 00 08 FF 00.
- 4027 selection used contiguous helper groups as if every group were a full
  package. In mega donors, some 4027 A/B subparts are split; use package-aware
  complete groups and skip split packages for this focused pack.

V6 correction over V5:
- Display row end boundaries are now taken from the next object start of any
  component family, not from the next display start only. V5's display-only
  boundary scan could swallow non-display objects between display blocks.

V7 correction over V6:
- Drop every 4027 renumbered-CDB candidate. User reported all renumbered cases
  crash on open; direct original-ref/full-mega-CDB candidates were not rejected.
- Keep the accepted anode method for known counts and add high-count threshold
  probes around 23.
- Do not claim all-red common-cathode output from the mega donor. The mega
  cathode records are blue, so V7 adds red-only donor-repeat diagnostics from
  the user-provided red 1x/4x cathode donors and marks them as non-mega.

This pack deliberately contains controls plus narrow candidates. It is not a
general matrix.
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
FOLLOWUP_DIR = DONOR_DIR / "display_4027_followup"
OUT_DIR = ROOT / "experiments/bare_display_4027_focus_v7_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_4027_FOCUS_V7_TEMP_2026_06_16.zip"

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
DISPLAY_RECORD_START = b"\x00\x08\xff\x00"
NORMAL_RECORD_START_RE = re.compile(
    rb"\xff[\x02-\x08]((?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+)|(?:Q\d+)|(?:D\d+)|(?:V\d+)|(?:I\d+))"
)


def load_helper():
    spec = importlib.util.spec_from_file_location("mega_bare_v1_for_v7", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper script: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mega_bare_v1_for_v7"] = module
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


def display_chunk_red_cathode_repeat(count: int) -> tuple[bytes, dict[str, object]]:
    rows = split_display_records(CC_RED_4)
    if len(rows) < 4:
        raise ValueError(f"Need the 4x red cathode donor rows, found {len(rows)}.")
    nonfinal_rows = rows[:-1]
    final_row = rows[-1]
    if count == 1:
        chosen = [final_row]
    else:
        chosen = [nonfinal_rows[i % len(nonfinal_rows)] for i in range(count - 1)] + [final_row]
    return b"".join(chosen), {
        "method": "red-only common-cathode donor-repeat diagnostic from 4x red donor; not mega extracted",
        "source_rows": len(rows),
        "selected_count": len(chosen),
        "all_red": True,
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


def complete_4027_groups(helper):
    state = helper.load_donor(MEGA_NO_SOURCE)
    return [group for group in state.groups_by_family["4027"] if len(group.refs) == 2]


def build_4027_mega_direct(helper, count: int) -> tuple[bytes, dict[str, object]]:
    groups = complete_4027_groups(helper)
    if len(groups) < count:
        raise ValueError(f"Need {count} complete 4027 groups, found {len(groups)}.")
    chunk, meta = helper.object_chunk_for(tuple(groups[:count]))
    return chunk, {"method": "complete contiguous mega 4027 package groups with original refs and full mega CDB", "selected_group_keys": [g.key for g in groups[:count]], **meta}


def build_4027_standalone_subset(helper, count: int) -> tuple[bytes, dict[str, object]]:
    state = helper.load_donor(JK_4027_4)
    groups = state.groups_by_family["4027"]
    chunk, meta = helper.object_chunk_for(tuple(groups[:count]))
    return chunk, {"method": "standalone 4x donor subset control", "selected_group_keys": [g.key for g in groups[:count]], **meta}


def build_cases() -> dict[str, object]:
    helper = load_helper()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    cases: list[dict[str, object]] = []
    for case_id, donor_path, description in [
        ("D00_EXACT_AN_BLUE_1X", AN_BLUE_1, "Exact one standalone common-anode blue display donor."),
        ("D01_EXACT_AN_BLUE_4X", AN_BLUE_4, "Exact four standalone common-anode blue display donor."),
        ("D02_EXACT_CC_RED_1X", CC_RED_1, "Exact one standalone common-cathode red display donor."),
        ("D03_EXACT_CC_RED_4X", CC_RED_4, "Exact four standalone common-cathode red display donor."),
        ("K00_EXACT_4027_1X", JK_4027_1, "Exact one standalone 4027 donor."),
        ("K01_EXACT_4027_2X", JK_4027_2, "Exact two standalone 4027 donor."),
        ("K02_EXACT_4027_4X", JK_4027_4, "Exact four standalone 4027 donor."),
    ]:
        cases.append(copy_exact_case(case_id, donor_path, description))

    mega_dsn = read_internal_file(MEGA_NO_SOURCE, "ROOT.DSN")
    mega_cdb = read_internal_file(MEGA_NO_SOURCE, "ROOT.CDB")
    jk4_dsn = read_internal_file(JK_4027_4, "ROOT.DSN")
    jk4_cdb = read_internal_file(JK_4027_4, "ROOT.CDB")
    cc4_dsn = read_internal_file(CC_RED_4, "ROOT.DSN")
    cc4_cdb = read_internal_file(CC_RED_4, "ROOT.CDB")

    for count in (1, 3, 5, 15, 16, 18, 20, 21, 22, 23):
        chunk, meta = display_chunk_mega_anode(count)
        cases.append(write_case(f"ANF_{count:02d}X_MEGA_ANODE_FINALROW", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} anode display records from mega, using donor-final anode row.", {"requested_count": count, **meta}))

    for count in (15, 23):
        chunk, meta = display_chunk_mega_anode_append_ff(count)
        cases.append(write_case(f"ANP_{count:02d}X_MEGA_ANODE_APPEND_FF", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} anode display records from mega with explicit FF terminator.", {"requested_count": count, **meta}))

    for count in COUNT_CHOICES:
        chunk, meta = display_chunk_mega_cathode_blue_final(count)
        cases.append(write_case(f"CCB_{count:02d}X_MEGA_CATHODE_BLUE_FINALROW", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} common-cathode records from mega, all blue, using donor-final cathode row.", {"requested_count": count, **meta}))

    for count in COUNT_CHOICES:
        chunk, meta = display_chunk_red_cathode_repeat(count)
        cases.append(write_case(f"CCR_{count:02d}X_RED4_REPEAT_FINALROW", CC_RED_4, cc4_cdb, cc4_dsn, chunk, f"{count} red common-cathode records from 4x red donor repeat; diagnostic because mega cathode records are blue.", {"requested_count": count, **meta}))

    # 4027 controls and candidates.
    chunk, meta = build_4027_standalone_subset(helper, 3)
    cases.append(write_case("K03A_4027_STANDALONE4_SUBSET_CONTROL", JK_4027_4, jk4_cdb, jk4_dsn, chunk, "Known-style 3x subset from standalone 4x 4027 donor.", {"requested_count": 3, **meta}))

    for count in COUNT_CHOICES:
        chunk, meta = build_4027_mega_direct(helper, count)
        cases.append(write_case(f"K{count:02d}D_4027_MEGA_DIRECT_FULL_CDB", MEGA_NO_SOURCE, mega_cdb, mega_dsn, chunk, f"{count} complete 4027 groups from mega with original refs/full mega CDB. No renumbering.", {"requested_count": count, **meta}))

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_4027_focus_v7_temp_2026_06_16",
        "purpose": "Component-specific diagnostics/fixes for V6 user feedback: no 4027 renumbering, anode threshold probes, cathode blue-clean and cathode red-only probes.",
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
