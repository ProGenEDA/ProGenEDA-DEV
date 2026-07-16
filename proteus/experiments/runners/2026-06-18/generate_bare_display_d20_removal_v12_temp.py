"""D20 removal/minimization diagnostics after V11 acceptance.

V11 user result:
- All D20-bridged display and 4027/display cases worked.

This pack tests whether the visible D20 bridge can be deleted after generation,
deleted with correct pointer rebuilding, or reduced to a smaller subrecord. The
controls preserve D20 exactly. Do not promote any D20-removal rule until the
user verifies these files in Proteus.
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


V11_PATH = ROOT / "tools/proteus_generation/2026-06-18/generate_bare_display_4027_bridge_v11_temp.py"
OUT_DIR = ROOT / "experiments/bare_display_d20_removal_v12_temp_2026_06_18"
ZIP_OUT = ROOT / "experiments/BARE_DISPLAY_D20_REMOVAL_V12_TEMP_2026_06_18.zip"
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")


def load_v11():
    spec = importlib.util.spec_from_file_location("display_v11_for_d20_removal_v12", V11_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load V11 generator: {V11_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["display_v11_for_d20_removal_v12"] = module
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
        "D20",
        "DIODE",
        "COMPONENT ID",
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def split_d20_records(bridge: bytes) -> list[bytes]:
    starts = [match.start() for match in re.finditer(rb"\xff[\x02-\x08]", bridge)]
    if starts != [0, 69, 143]:
        raise ValueError(f"Unexpected D20 subrecord starts: {starts}")
    records: list[bytes] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(bridge)
        records.append(bridge[start:end])
    return records


def blank_d20_text(bridge: bytes) -> bytes:
    # Same-length text neutralization only. The primitive bytes remain untouched.
    out = bytearray(bridge)
    for old, new in (
        (b"D20", b"   "),
        (b"DIODE", b"     "),
        (b"COMPONENT ID", b"            "),
        (b"COMPONENT VALUE", b"               "),
        (b"SUBCKT NAME", b"          "),
    ):
        start = 0
        while True:
            pos = bytes(out).find(old, start)
            if pos < 0:
                break
            out[pos : pos + len(old)] = new
            start = pos + len(old)
    return bytes(out)


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


def write_stale_pointer_case(
    case_id: str,
    donor_path: Path,
    donor_dsn: bytes,
    cdb: bytes,
    working_chunk: bytes,
    stripped_chunk: bytes,
    description: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    working_dsn, pointers = build_dsn(donor_dsn, donor_dsn, working_chunk)
    stale_dsn = working_dsn.replace(working_chunk, stripped_chunk, 1)
    if stale_dsn == working_dsn:
        raise ValueError(f"{case_id}: stale-pointer replacement did not change ROOT.DSN.")
    write_project_from_parts(donor_path, output, {"ROOT.DSN": stale_dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    errors: list[str] = []
    if final_chunk != stripped_chunk:
        errors.append("final object chunk differs from stripped object chunk")
    if any(marker in final_chunk for marker in TERM_MARKERS):
        errors.append("terminal marker present")
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
        "pointers_before_stale_deletion": pointers,
        "postbuild_stale_pointer_removal": True,
    }
    if extra:
        result.update(extra)
    return result


def build_cases() -> dict[str, object]:
    v11 = load_v11()
    v9 = v11.load_v9()
    helper = v9.load_helper()
    donor_dsn = read_internal_file(v9.MEGA_NO_SOURCE, "ROOT.DSN")
    cdb = read_internal_file(v9.MEGA_NO_SOURCE, "ROOT.CDB")
    groups_4027 = v9.complete_4027_groups(helper)
    if not groups_4027:
        raise ValueError("No complete 4027 groups found.")
    k01 = groups_4027[0].data
    bridge, bridge_meta = v11.load_d20_bridge(v9)
    d20_records = split_d20_records(bridge)
    blank_bridge = blank_d20_text(bridge)

    anode_rows, anode_meta = v9.anode_rows_trim_rule(1)
    anode_single = v9.build_display_chunk(anode_rows)

    working_an = b"\x00\x00" + bridge + anode_single
    working_k_an = b"\x00\x00" + k01 + bridge + anode_single
    stripped_an = b"\x00\x00" + anode_single
    stripped_k_an = b"\x00\x00" + k01 + anode_single

    cases: list[dict[str, object]] = []

    def add(case_id: str, object_chunk: bytes, description: str, extra: dict[str, object] | None = None) -> None:
        cases.append(write_case(case_id, v9.MEGA_NO_SOURCE, donor_dsn, cdb, object_chunk, description, extra))

    add(
        "T00_CONTROL_D20_AN01",
        working_an,
        "Accepted V11-style control: D20 bridge plus one common-anode display row.",
        {"control": True, "display": anode_meta, **bridge_meta},
    )
    add(
        "T01_CONTROL_K01_D20_AN01",
        working_k_an,
        "Accepted V11-style control: one 4027 package, D20 bridge, and one common-anode display row.",
        {
            "control": True,
            "selected_4027_group_key": groups_4027[0].key,
            "display": anode_meta,
            **bridge_meta,
        },
    )
    add(
        "T02_AN01_DELETE_D20_ADJUSTED_POINTERS",
        stripped_an,
        "Delete D20 and rebuild ROOT.DSN pointers cleanly: 00 00 plus one anode row.",
        {"d20_removed": True, "pointer_policy": "rebuilt"},
    )
    add(
        "T03_K01_AN01_DELETE_D20_ADJUSTED_POINTERS",
        stripped_k_an,
        "Delete D20 between 4027 and anode display, then rebuild ROOT.DSN pointers cleanly.",
        {"d20_removed": True, "pointer_policy": "rebuilt", "selected_4027_group_key": groups_4027[0].key},
    )
    add(
        "T04_AN01_NO_PREFIX_NO_D20",
        anode_single,
        "One common-anode row with no 00 00 prefix and no D20. This isolates prefix dependence.",
        {"d20_removed": True, "prefix": "none"},
    )
    add(
        "T05_D20_RECORD0_ONLY_AN01",
        b"\x00\x00" + d20_records[0] + anode_single,
        "Keep only D20 subrecord 0 (component-id text) before one anode row.",
        {"d20_subrecords_kept": [0], **bridge_meta},
    )
    add(
        "T06_D20_RECORD01_ONLY_AN01",
        b"\x00\x00" + d20_records[0] + d20_records[1] + anode_single,
        "Keep D20 subrecords 0 and 1 before one anode row.",
        {"d20_subrecords_kept": [0, 1], **bridge_meta},
    )
    add(
        "T07_D20_RECORD2_ONLY_AN01",
        b"\x00\x00" + d20_records[2] + anode_single,
        "Keep only D20 subrecord 2, which includes the later D20 text/primitive bytes, before one anode row.",
        {"d20_subrecords_kept": [2], **bridge_meta},
    )
    add(
        "T08_K01_D20_RECORD0_ONLY_AN01",
        b"\x00\x00" + k01 + d20_records[0] + anode_single,
        "4027 plus only D20 subrecord 0 before one anode row.",
        {"d20_subrecords_kept": [0], "selected_4027_group_key": groups_4027[0].key, **bridge_meta},
    )
    add(
        "T09_K01_D20_RECORD01_ONLY_AN01",
        b"\x00\x00" + k01 + d20_records[0] + d20_records[1] + anode_single,
        "4027 plus D20 subrecords 0 and 1 before one anode row.",
        {"d20_subrecords_kept": [0, 1], "selected_4027_group_key": groups_4027[0].key, **bridge_meta},
    )
    add(
        "T10_K01_D20_RECORD2_ONLY_AN01",
        b"\x00\x00" + k01 + d20_records[2] + anode_single,
        "4027 plus only D20 subrecord 2 before one anode row.",
        {"d20_subrecords_kept": [2], "selected_4027_group_key": groups_4027[0].key, **bridge_meta},
    )
    add(
        "T11_D20_TEXT_BLANKED_AN01",
        b"\x00\x00" + blank_bridge + anode_single,
        "Same-length D20 neutralization attempt: blank visible D20/DIODE text but keep primitive bytes.",
        {"d20_text_blanked": True, "blank_bridge_sha256": sha256_bytes(blank_bridge), **bridge_meta},
    )
    cases.append(
        write_stale_pointer_case(
            "T12_POSTBUILD_REMOVE_D20_AN01_STALE_POINTERS",
            v9.MEGA_NO_SOURCE,
            donor_dsn,
            cdb,
            working_an,
            stripped_an,
            "Build accepted D20+anode output first, then remove the D20 bytes without rebuilding ROOT.DSN pointers.",
            {"d20_removed": True, "display": anode_meta, **bridge_meta},
        )
    )
    cases.append(
        write_stale_pointer_case(
            "T13_POSTBUILD_REMOVE_D20_K01_AN01_STALE_POINTERS",
            v9.MEGA_NO_SOURCE,
            donor_dsn,
            cdb,
            working_k_an,
            stripped_k_an,
            "Build accepted 4027+D20+anode output first, then remove the D20 bytes without rebuilding ROOT.DSN pointers.",
            {"d20_removed": True, "selected_4027_group_key": groups_4027[0].key, "display": anode_meta, **bridge_meta},
        )
    )

    issue_cases = [case["case_id"] for case in cases if case.get("errors")]
    return {
        "experiment": "bare_display_d20_removal_v12_temp_2026_06_18",
        "purpose": "Test whether the accepted visible D20 display bridge can be deleted, minimized, or text-neutralized.",
        "case_count": len(cases),
        "static_issue_cases": issue_cases,
        "d20_records": [
            {
                "index": index,
                "size": len(record),
                "head": record[:16].hex(),
                "tail": record[-16:].hex(),
                "sha256": sha256_bytes(record),
            }
            for index, record in enumerate(d20_records)
        ],
        "bridge": bridge_meta,
        "cases": cases,
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    summary = build_cases()
    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    readme = (
        "BARE_DISPLAY_D20_REMOVAL_V12_TEMP_2026_06_18\n\n"
        "Test T00 and T01 first. They are accepted V11 controls.\n"
        "Then test T02-T13. If a no-D20 or partial-D20 case works, report the exact case id.\n"
        "T12/T13 intentionally simulate postbuild byte deletion with stale ROOT.DSN pointers; they may fail.\n\n"
        f"Archive: {ZIP_OUT.relative_to(ROOT)}\n"
    )
    (OUT_DIR / "README.txt").write_text(readme, encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    summary["archive"] = str(ZIP_OUT.relative_to(ROOT))
    summary["archive_sha256"] = sha256_file(ZIP_OUT)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "archive": str(ZIP_OUT), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
