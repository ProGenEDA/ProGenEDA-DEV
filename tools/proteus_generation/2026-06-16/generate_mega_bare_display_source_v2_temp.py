"""Generate no-terminal display/source diagnostics from the mega donors.

This pack is intentionally small. It answers two open questions before the
large bare-placement matrix:

- Can a single common-anode 7-segment display be emitted without terminals?
- Can the common-cathode record embedded in the mega donor be isolated?
- Do source-only/source-pair outputs include VSINE as well as VSOURCE/CSOURCE?

The normal component/source cases reuse the already user-confirmed mega V1
object-stream finalization rule. Display records are tested in a few explicit
forms because Proteus stores them differently from normal IC/passive packets.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn

HELPER_PATH = ROOT / "tools/proteus_generation/2026-06-16/generate_mega_bare_separation_v1_temp.py"
OUT_DIR = ROOT / "experiments/mega_bare_display_source_v2_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/MEGA_BARE_DISPLAY_SOURCE_V2_TEMP_2026_06_16.zip"

DISPLAY_ANODE_SINGLE = ROOT / "proteus_ic/donors/manual_downloads_20260611/squence/7segcomanode.pdsprj"
DISPLAY_ANODE_DOUBLE = ROOT / "proteus_ic/donors/manual_downloads_20260611/squence/27segcomanode.pdsprj"


def load_helper():
    spec = importlib.util.spec_from_file_location("mega_bare_v1", HELPER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load helper script: {HELPER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["mega_bare_v1"] = module
    spec.loader.exec_module(module)
    module.OUT_DIR = OUT_DIR
    module.FAMILY_MARKERS = tuple(sorted(set(module.FAMILY_MARKERS + ("VSINE",)), key=len, reverse=True))
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
        "7SEG-COM-CAT-BLUE",
        "7SEG-COM-ANODE",
        "VSOURCE",
        "CSOURCE",
        "VSINE",
        "RESISTOR",
        "CAP",
        "REALIND",
        "7447",
        "4511",
        "$TERBIDIR",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERPOWER",
        "$TERGROUND",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def write_forced_case(case_id: str, donor_path: Path, cdb: bytes, donor_dsn: bytes, object_chunk: bytes, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(donor_path, output, {"ROOT.DSN": dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs from requested chunk")
    if any(term in final_chunk for term in (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")):
        errors.append("terminal marker present")
    return {
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


def copy_exact_display_case(case_id: str, donor_path: Path, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(donor_path, output)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(donor_path.relative_to(ROOT)),
        "description": description,
        "copy_exact": True,
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "errors": [],
    }


def display_record_parts() -> dict[str, bytes]:
    single_final = _extract_object_chunk(read_internal_file(DISPLAY_ANODE_SINGLE, "ROOT.DSN"))
    double_chunk = _extract_object_chunk(read_internal_file(DISPLAY_ANODE_DOUBLE, "ROOT.DSN"))
    offsets: list[int] = []
    pos = 0
    while True:
        pos = double_chunk.find(b"COMPONENT ID", pos)
        if pos < 0:
            break
        offsets.append(max(0, pos - 51))
        pos += 1
    offsets.append(len(double_chunk))
    if len(offsets) != 3:
        raise ValueError("Expected the two-display donor to contain exactly two display records.")
    second_final = double_chunk[offsets[1] : offsets[2]]
    return {
        "single_final": single_final,
        "double_chunk": double_chunk,
        "first_middle": double_chunk[offsets[0] : offsets[1]],
        "second_middle": second_final[:-2],
        "second_final": second_final,
    }


def display_chunk(count: int) -> bytes:
    parts = display_record_parts()
    if count == 1:
        return parts["single_final"]
    if count == 2:
        return parts["double_chunk"]
    return parts["first_middle"] + parts["second_middle"] * (count - 2) + parts["second_final"]


def embedded_display_segments(helper, state) -> tuple[bytes, bytes]:
    outer = state.groups_by_family["7SEG-COM-ANODE"][0].data
    component_offsets: list[int] = []
    pos = 0
    while True:
        pos = outer.find(b"COMPONENT ID", pos)
        if pos < 0:
            break
        component_offsets.append(pos)
        pos += 1
    starts = [max(0, offset - 51) for offset in component_offsets]
    starts.append(len(outer))
    cat_segments: list[bytes] = []
    anode_segments: list[bytes] = []
    for index in range(1, len(starts) - 1):
        segment = outer[starts[index] : starts[index + 1]]
        if b"7SEGCOMK" in segment:
            cat_segments.append(segment)
        elif b"7SEGCOMA" in segment:
            anode_segments.append(segment)
    if not cat_segments or not anode_segments:
        raise ValueError("Could not split embedded display segments from semimega donor.")
    return cat_segments[0], anode_segments[0]


def build_cases() -> dict[str, object]:
    helper = load_helper()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    semi = helper.load_donor(helper.SEMI_NO_SOURCE)
    large = helper.load_donor(helper.FIFTEEN_X_WITH_SOURCE)
    anode_dsn = read_internal_file(DISPLAY_ANODE_SINGLE, "ROOT.DSN")
    anode_cdb = read_internal_file(DISPLAY_ANODE_SINGLE, "ROOT.CDB")
    anode_single = _extract_object_chunk(anode_dsn)
    anode_double = _extract_object_chunk(read_internal_file(DISPLAY_ANODE_DOUBLE, "ROOT.DSN"))
    cat_segment, embedded_anode_segment = embedded_display_segments(helper, semi)

    cases: list[dict[str, object]] = []
    cases.append(copy_exact_display_case("G00_EXACT_SINGLE_ANODE_DONOR", DISPLAY_ANODE_SINGLE, "Exact single common-anode no-terminal display donor."))
    cases.append(
        write_forced_case(
            "G01_REBUILT_SINGLE_ANODE_CHUNK",
            DISPLAY_ANODE_SINGLE,
            anode_cdb,
            anode_dsn,
            anode_single,
            "Rebuild the exact single common-anode display object chunk.",
        )
    )
    cases.append(
        write_forced_case(
            "G02_SYNTH_THREE_COMMON_ANODE",
            DISPLAY_ANODE_SINGLE,
            anode_cdb,
            anode_dsn,
            display_chunk(3),
            "Three common-anode displays synthesized from the verified single/double display record relationship.",
        )
    )
    cases.append(
        write_forced_case(
            "G03_REBUILT_DOUBLE_COMMON_ANODE",
            DISPLAY_ANODE_DOUBLE,
            read_internal_file(DISPLAY_ANODE_DOUBLE, "ROOT.CDB"),
            read_internal_file(DISPLAY_ANODE_DOUBLE, "ROOT.DSN"),
            anode_double,
            "Rebuild exact two common-anode donor chunk.",
        )
    )
    cases.append(
        write_forced_case(
            "G04_ONE_COMMON_CATHODE_EMBED_RAW",
            semi.path,
            semi.cdb,
            semi.dsn,
            cat_segment + b"\xff",
            "Experimental: one embedded common-cathode display segment emitted as display-style object chunk.",
        )
    )
    cases.append(
        write_forced_case(
            "G05_ONE_COMMON_CATHODE_EMBED_TRIM",
            semi.path,
            semi.cdb,
            semi.dsn,
            cat_segment[:-1] + b"\xff",
            "Experimental: one embedded common-cathode display segment with final trailing 00 replaced by FF.",
        )
    )
    cases.append(
        write_forced_case(
            "G06_ONE_EMBED_CAT_ONE_EMBED_ANODE",
            semi.path,
            semi.cdb,
            semi.dsn,
            cat_segment[:-1] + embedded_anode_segment + b"\xff",
            "Experimental: one embedded common-cathode and one embedded common-anode segment.",
        )
    )
    cases.append(
        helper.write_case(
            "G07_SOURCE_ONLY_ONE_EACH_INCLUDES_VSINE",
            large,
            helper.select_groups(large, {"VSOURCE": 1, "CSOURCE": 1, "VSINE": 1}),
            "One VSOURCE, one CSOURCE, and one VSINE record only.",
            extra={"requested_counts": {"VSOURCE": 1, "CSOURCE": 1, "VSINE": 1}},
        )
    )
    cases.append(
        helper.write_case(
            "G08_SOURCE_PAIR_VSOURCE_VSINE",
            large,
            helper.select_groups(large, {"VSOURCE": 3, "VSINE": 3}),
            "Three VSOURCE and three VSINE source records.",
            extra={"requested_counts": {"VSOURCE": 3, "VSINE": 3}},
        )
    )
    cases.append(
        helper.write_case(
            "G09_SOURCE_PAIR_CSOURCE_VSINE",
            large,
            helper.select_groups(large, {"CSOURCE": 3, "VSINE": 3}),
            "Three CSOURCE and three VSINE source records.",
            extra={"requested_counts": {"CSOURCE": 3, "VSINE": 3}},
        )
    )
    cases.append(
        helper.write_case(
            "G10_SOURCE_TRIPLE_FIVE_EACH",
            large,
            helper.select_groups(large, {"VSOURCE": 5, "CSOURCE": 5, "VSINE": 5}),
            "Five each of VSOURCE, CSOURCE, and VSINE.",
            extra={"requested_counts": {"VSOURCE": 5, "CSOURCE": 5, "VSINE": 5}},
        )
    )
    mixed_chunk = b"\x00\x00" + b"".join(group.data for group in helper.select_groups(semi, {"7447": 1, "4511": 1})) + display_record_parts()["single_final"]
    cases.append(
        write_forced_case(
            "G11_7447_4511_ONE_ANODE_DISPLAY",
            semi.path,
            semi.cdb,
            semi.dsn,
            mixed_chunk,
            "One 7447, one 4511, and one standalone common-anode display record, no terminals.",
        )
    )

    return {
        "experiment": "mega_bare_display_source_v2_temp_2026_06_16",
        "purpose": "Small preflight for single display separation and VSINE source-only/source-pair generation.",
        "case_count": len(cases),
        "display_relationship": {
            "single_anode_chunk_size": len(anode_single),
            "double_anode_chunk_size": len(anode_double),
            "double_record_offsets_verified": anode_double == display_record_parts()["double_chunk"],
            "embedded_cat_segment_size": len(cat_segment),
            "embedded_anode_segment_size": len(embedded_anode_segment),
        },
        "large_source_counts": large.counts(),
        "cases": cases,
    }


def main() -> None:
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": summary["case_count"], "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
