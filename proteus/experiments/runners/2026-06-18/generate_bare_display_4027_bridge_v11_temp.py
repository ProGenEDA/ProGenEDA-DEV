"""4027/display bridge candidate pack after V10 user result.

V10 user result:
- Only T08 and T09 worked.
- Both working cases preserve the original D20 diode packet immediately before
  the display row.

This pack tests whether that D20 bridge scales to display counts, cathode
sentinel cases, and 4027/display pairs. The bridge is visible, so this is still
diagnostic and not a locked pure display-pair rule.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


V9_PATH = ROOT / "proteus/experiments/runners/2026-06-18/generate_bare_display_mega_acceptance_v9_temp.py"
OUT_DIR = ROOT / "experiments/bare_display_4027_bridge_v11_temp_2026_06_18"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_4027_BRIDGE_V11_TEMP_2026_06_18.zip"

COUNTS = (1, 3, 5, 15, 23)
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")


def load_v9():
    spec = importlib.util.spec_from_file_location("display_v9_for_bridge_v11", V9_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load V9 generator: {V9_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["display_v9_for_bridge_v11"] = module
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


def marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "7SEGCOMA",
        "7SEGCOMK",
        "7SEG-COM-ANODE",
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


def previous_object_start(starts: list[int], pos: int) -> int:
    previous = [start for start in starts if start < pos]
    if not previous:
        raise ValueError(f"No object start before {pos}.")
    return previous[-1]


def load_d20_bridge(v9) -> tuple[bytes, dict[str, object]]:
    chunk = _extract_object_chunk(read_internal_file(v9.MEGA_NO_SOURCE, "ROOT.DSN"))
    cathode0 = v9.mega_display_records("cathode")[0]
    cathode_pos = chunk.find(cathode0)
    if cathode_pos < 0:
        raise ValueError("Could not find first cathode row in mega donor.")
    starts = v9.all_object_starts(chunk)
    start = previous_object_start(starts, cathode_pos)
    data = chunk[start:cathode_pos]
    if b"COMPONENT ID" not in data or b"D20" not in data or b"DIODE" not in data:
        raise ValueError("Expected pre-display bridge to be the D20 diode packet.")
    if not data.endswith(b"\x00"):
        raise ValueError("D20 pre-display bridge must remain a middle packet ending in 00.")
    return data, {
        "bridge_ref": "D20",
        "bridge_marker": "DIODE",
        "bridge_start": start,
        "bridge_size": len(data),
        "bridge_sha256": sha256_bytes(data),
    }


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
    donor_dsn = read_internal_file(v9.MEGA_NO_SOURCE, "ROOT.DSN")
    cdb = read_internal_file(v9.MEGA_NO_SOURCE, "ROOT.CDB")
    groups_4027 = v9.complete_4027_groups(helper)
    if len(groups_4027) < max(COUNTS):
        raise ValueError(f"Need {max(COUNTS)} complete 4027 groups, found {len(groups_4027)}.")
    bridge, bridge_meta = load_d20_bridge(v9)

    cases: list[dict[str, object]] = []

    def add(case_id: str, object_chunk: bytes, description: str, extra: dict[str, object] | None = None) -> None:
        cases.append(write_case(case_id, v9.MEGA_NO_SOURCE, donor_dsn, cdb, object_chunk, description, extra))

    def k_prefix(count: int) -> bytes:
        return b"".join(group.data for group in groups_4027[:count])

    for count in COUNTS:
        rows, display_meta = v9.anode_rows_trim_rule(count)
        display_chunk = v9.build_display_chunk(rows)
        add(
            f"A11_{count:02d}_D20_ANODE",
            b"\x00\x00" + bridge + display_chunk,
            f"D20 bridge plus {count} common-anode display row(s).",
            {"requested_anode_count": count, "display": display_meta, **bridge_meta},
        )

    for count in COUNTS:
        rows, display_meta = v9.cathode_rows_with_anode_sentinel(count)
        display_chunk = v9.build_display_chunk(rows)
        add(
            f"C11_{count:02d}_D20_CATHODE_SENTINEL",
            b"\x00\x00" + bridge + display_chunk,
            f"D20 bridge plus {count} common-cathode display row(s), terminated by the true final anode sentinel.",
            {"requested_cathode_count": count, "display": display_meta, **bridge_meta},
        )

    for count in COUNTS:
        rows, display_meta = v9.anode_rows_trim_rule(count)
        display_chunk = v9.build_display_chunk(rows)
        add(
            f"KA11_K{count:02d}_AN{count:02d}_D20",
            b"\x00\x00" + k_prefix(count) + bridge + display_chunk,
            f"{count} 4027 package(s), D20 bridge, and {count} common-anode display row(s).",
            {
                "requested_4027_count": count,
                "requested_anode_count": count,
                "display": display_meta,
                "selected_4027_group_keys": [group.key for group in groups_4027[:count]],
                **bridge_meta,
            },
        )

    for count in COUNTS:
        rows, display_meta = v9.cathode_rows_with_anode_sentinel(count)
        display_chunk = v9.build_display_chunk(rows)
        add(
            f"KC11_K{count:02d}_CC{count:02d}_D20",
            b"\x00\x00" + k_prefix(count) + bridge + display_chunk,
            f"{count} 4027 package(s), D20 bridge, and {count} common-cathode row(s) plus anode sentinel.",
            {
                "requested_4027_count": count,
                "requested_cathode_count": count,
                "display": display_meta,
                "selected_4027_group_keys": [group.key for group in groups_4027[:count]],
                **bridge_meta,
            },
        )

    for count in COUNTS:
        rows, display_meta = v9.cathode_anode_pair_rows(count, count)
        display_chunk = v9.build_display_chunk(rows)
        add(
            f"DPAIR11_CC{count:02d}_AN{count:02d}_D20",
            b"\x00\x00" + bridge + display_chunk,
            f"D20 bridge plus {count} cathode and {count} anode display rows.",
            {
                "requested_cathode_count": count,
                "requested_anode_count": count,
                "display": display_meta,
                **bridge_meta,
            },
        )

    rows, display_meta = v9.cathode_anode_pair_rows(23, 23)
    display_chunk = v9.build_display_chunk(rows)
    add(
        "STRESS11_K23_CC23_AN23_D20",
        b"\x00\x00" + k_prefix(23) + bridge + display_chunk,
        "Stress case: 23 4027 packages, D20 bridge, 23 cathode rows, and 23 anode rows.",
        {
            "requested_4027_count": 23,
            "requested_cathode_count": 23,
            "requested_anode_count": 23,
            "display": display_meta,
            "selected_4027_group_keys": [group.key for group in groups_4027[:23]],
            **bridge_meta,
        },
    )

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_4027_bridge_v11_temp_2026_06_18",
        "purpose": "Scale the V10-confirmed D20 pre-display bridge for displays and 4027/display pairs.",
        "known_caveat": "The D20 bridge is a visible diode packet. This pack tests a working boundary candidate, not a pure final display-pair rule.",
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
