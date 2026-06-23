"""Focused 4027/display boundary diagnostics after V9 K-pair rejection.

V9 proved that the accepted single-family rules do not automatically compose:
all 4027+display pair cases failed when the stream was built as:

    00 00 + complete 4027 group data + display rows

This script keeps the accepted direct 4027 and display controls intact, then
tests only small boundary variants. Do not scale 4027/display output until one
of these variants is confirmed in Proteus.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


V9_PATH = ROOT / "tools/proteus_generation/2026-06-18/generate_bare_display_mega_acceptance_v9_temp.py"
OUT_DIR = ROOT / "experiments/bare_display_4027_boundary_v10_temp_2026_06_18"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_4027_BOUNDARY_V10_TEMP_2026_06_18.zip"
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")


def load_v9():
    spec = importlib.util.spec_from_file_location("display_v9_for_boundary_v10", V9_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load V9 generator: {V9_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["display_v9_for_boundary_v10"] = module
    spec.loader.exec_module(module)
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


def generic_final_data(group) -> bytes:
    if group.source_is_final:
        return group.data
    if not group.data.endswith(b"\x00"):
        raise ValueError(f"{group.key} does not end with the expected middle-record 00.")
    return group.data[:-1] + b"\xff"


def previous_object_start(starts: list[int], pos: int) -> int:
    previous = [start for start in starts if start < pos]
    if not previous:
        raise ValueError(f"No previous object start before {pos}.")
    return previous[-1]


def marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "7SEGCOMA",
        "7SEGCOMK",
        "7SEG-COM-ANODE",
        "7SEG-COM-AN-BLUE",
        "7SEG-COM-CATHODE",
        "7SEG-COM-CAT-BLUE",
        "4027",
        "COMPONENT ID",
        "DIODE",
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def write_case(
    case_id: str,
    donor_path: Path,
    donor_dsn: bytes,
    cdb: bytes,
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
        errors.append("final object chunk differs from requested object chunk")
    if any(marker in final_chunk for marker in TERM_MARKERS):
        errors.append("terminal marker present")
    if not final_chunk.endswith(b"\xff"):
        errors.append("object chunk does not end with FF")
    result = {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "description": description,
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "errors": errors,
        "pointers": pointers,
    }
    if extra:
        result.update(extra)
    return result


def build_cases() -> dict[str, object]:
    v9 = load_v9()
    helper = v9.load_helper()
    state = helper.load_donor(v9.MEGA_NO_SOURCE)
    donor_dsn = read_internal_file(v9.MEGA_NO_SOURCE, "ROOT.DSN")
    cdb = read_internal_file(v9.MEGA_NO_SOURCE, "ROOT.CDB")
    chunk = _extract_object_chunk(donor_dsn)

    groups_4027 = v9.complete_4027_groups(helper)
    if not groups_4027:
        raise ValueError("No complete 4027 groups found.")
    k01 = groups_4027[0]
    k01_middle = k01.data
    k01_final = generic_final_data(k01)

    anode_rows, anode_meta = v9.anode_rows_trim_rule(1)
    cathode_rows, cathode_meta = v9.cathode_rows_with_anode_sentinel(1)
    anode_single = v9.build_display_chunk(anode_rows)
    cathode_single = v9.build_display_chunk(cathode_rows)

    all_anode_rows = v9.mega_display_records("anode")
    all_cathode_rows = v9.mega_display_records("cathode")
    anode0_middle = all_anode_rows[0]
    cath0_pos = chunk.find(all_cathode_rows[0])
    anode_final_pos = chunk.find(all_anode_rows[-1])
    if cath0_pos < 0 or anode_final_pos < 0:
        raise ValueError("Could not locate display rows in original mega chunk.")
    display_block = chunk[cath0_pos : anode_final_pos + len(all_anode_rows[-1])]

    starts = v9.all_object_starts(chunk)
    pre_display_start = previous_object_start(starts, cath0_pos)
    pre_display_group = chunk[pre_display_start:cath0_pos]
    k_to_display_subrange = chunk[k01.start : anode_final_pos + len(all_anode_rows[-1])]

    cases: list[dict[str, object]] = []

    def add(case_id: str, object_chunk: bytes, description: str, extra: dict[str, object] | None = None) -> None:
        cases.append(write_case(case_id, v9.MEGA_NO_SOURCE, donor_dsn, cdb, object_chunk, description, extra))

    k_direct, k_meta = v9.build_4027_mega_direct(helper, 1)
    add(
        "T00_CONTROL_K01_DIRECT_ACCEPTED",
        k_direct,
        "Accepted direct 1x 4027 control from V7/V9.",
        {"control": True, **k_meta},
    )
    add(
        "T01_CONTROL_AN01_ACCEPTED",
        anode_single,
        "Accepted 1x common-anode display control.",
        {"control": True, "display": anode_meta},
    )
    add(
        "T02_CONTROL_CC01_SENTINEL",
        cathode_single,
        "1x common-cathode display plus true anode-final sentinel control.",
        {"control": True, "display": cathode_meta},
    )
    add(
        "T03_REJECTED_V9_K01_AN01_BASELINE",
        b"\x00\x00" + k01_middle + anode_single,
        "Exact V9 rejected boundary style: 00 00 + 4027 middle group + anode final row.",
        {"expected": "known_bad_from_user_report"},
    )
    add(
        "T04_REJECTED_V9_K01_CC01_BASELINE",
        b"\x00\x00" + k01_middle + cathode_single,
        "Exact V9 rejected boundary style: 00 00 + 4027 middle group + cathode row + anode sentinel.",
        {"expected": "known_bad_from_user_report"},
    )
    add(
        "T05_K01_AN01_ONE_ZERO_SEPARATOR",
        b"\x00\x00" + k01_middle + b"\x00" + anode_single,
        "4027 middle group, one explicit zero separator, then anode final row.",
    )
    add(
        "T06_K01_AN01_TWO_ZERO_SEPARATOR",
        b"\x00\x00" + k01_middle + b"\x00\x00" + anode_single,
        "4027 middle group, two explicit zero separators, then anode final row.",
    )
    add(
        "T07_ANODE0_THEN_K01_FINAL",
        anode0_middle + k01_final,
        "Display middle row first, then finalized 4027 group. Tests display-to-generic order.",
    )
    add(
        "T08_PREDISPLAY_GROUP_THEN_AN01",
        b"\x00\x00" + pre_display_group + anode_single,
        "Original immediate pre-display generic group followed by a single anode row.",
        {"pre_display_start": pre_display_start, "pre_display_size": len(pre_display_group)},
    )
    add(
        "T09_K01_PREDISPLAY_GROUP_THEN_AN01",
        b"\x00\x00" + k01_middle + pre_display_group + anode_single,
        "4027 group plus original immediate pre-display generic bridge, then anode final row.",
        {"pre_display_start": pre_display_start, "pre_display_size": len(pre_display_group)},
    )
    add(
        "T10_K01_FULL_ORIGINAL_DISPLAY_BLOCK",
        b"\x00\x00" + k01_middle + display_block,
        "4027 group followed by the original contiguous mega display block from first cathode through final anode.",
        {"display_block_size": len(display_block)},
    )
    add(
        "T11_ORIGINAL_K01_TO_FINAL_ANODE_SUBRANGE",
        b"\x00\x00" + k_to_display_subrange,
        "Original mega subrange from first 4027 package through true final anode display row, preserving all intervening objects.",
        {"subrange_size": len(k_to_display_subrange), "subrange_start": k01.start},
    )

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_4027_boundary_v10_temp_2026_06_18",
        "purpose": "Find the missing ROOT.DSN object-stream boundary for no-terminal 4027/display composition after V9 K-pair rejection.",
        "case_count": len(cases),
        "static_issue_cases": issue_cases,
        "cases": cases,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(
        json.dumps(
            {
                "out_dir": str(OUT_DIR),
                "zip": str(ZIP_OUT),
                "case_count": summary["case_count"],
                "static_issue_cases": summary["static_issue_cases"],
                "zip_sha256": sha256_file(ZIP_OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
