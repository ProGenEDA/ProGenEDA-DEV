"""Generate V12 diagnostics for mixed DC sources plus R/C/L.

V11 established a strong boundary:

* T03 and T05, the suffix-map variants, opened.
* T02, T04, T06, and T07 failed with VGDVC.dll.

So V12 removes the plain unsafe splice variants, adds the missing group-4
suffix-map case, and tests visual coordinate relocation for the donor source
sub-blocks. The relocation is length-preserving and does not alter terminal
suffix/link bytes.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V9_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-05" / "generate_dc_mixed_sources_v9_donor_tail_temp.py"
V11_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-05" / "generate_dc_mixed_sources_v11_group_boundary_temp.py"
OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_mixed_sources_v12_suffixmap_coords_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_MIXED_SOURCES_V12_SUFFIXMAP_COORDS_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"

SOURCE_GAP = 1_524_000


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v9 = _load_module("dc_mixed_sources_v9_for_v12", V9_PATH)
v11 = _load_module("dc_mixed_sources_v11_for_v12", V11_PATH)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _s32(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = rv9._i32(value)


def _add_s32(data: bytearray, offset: int, delta: int) -> None:
    _put_s32(data, offset, _s32(data, offset) + delta)


def _terminal_symbol(chunk: bytes, start: int) -> tuple[int, int]:
    return _s32(chunk, start + 1), _s32(chunk, start + 5)


def _terminal_label(kind: str, record: bytes) -> str:
    if kind == "OUT":
        length_offset = 31
        label_start = 32
    else:
        length_offset = 30
        label_start = 31
    label_len = record[length_offset]
    return record[label_start : label_start + label_len].decode("ascii")


def _translate_terminal(out: bytearray, start: int, end: int, kind: str, dx: int, dy: int) -> None:
    record = bytes(out[start:end])
    if kind == "OUT":
        length_offset = 31
        label_start = 32
    else:
        length_offset = 30
        label_start = 31
    label_len = record[length_offset]
    label_x = label_start + label_len
    label_y = label_x + 4
    _add_s32(out, start + 1, dx)
    _add_s32(out, start + 5, dy)
    _add_s32(out, start + label_x, dx)
    _add_s32(out, start + label_y, dy)


def _terminal_bounds(chunk: bytes) -> list[tuple[int, int, str, str]]:
    starts = v9._terminal_events(chunk)
    starts_with_end = [(start, kind, label) for start, kind, label in starts]
    bounds: list[tuple[int, int, str, str]] = []
    for index, (start, kind, label) in enumerate(starts_with_end):
        if index + 1 < len(starts_with_end):
            end = starts_with_end[index + 1][0]
        else:
            end = len(chunk)
        bounds.append((start, end, kind, label))
    return bounds


def _find_terminal(
    chunk: bytes,
    *,
    kind: str,
    label: str,
    before: int | None = None,
    after: int | None = None,
) -> int:
    matches = []
    for start, term_kind, term_label in v9._terminal_events(chunk):
        if term_kind != kind or term_label != label:
            continue
        if before is not None and start >= before:
            continue
        if after is not None and start < after:
            continue
        matches.append(start)
    if not matches:
        raise RuntimeError(f"Could not find terminal {kind} {label} before={before} after={after}.")
    return matches[-1]


def _source_block_bounds(chunk: bytes) -> dict[str, tuple[int, int]]:
    tail_start = v11.GROUP_STARTS["source_tail_start"]
    vsource_start = _find_terminal(chunk, kind="IN", label="DVO", after=tail_start)
    csource_start = _find_terminal(chunk, kind="IN", label="A7", after=vsource_start)
    out_d2 = _find_terminal(chunk, kind="OUT", label="D2", after=csource_start)
    if not (vsource_start == tail_start and csource_start > vsource_start and out_d2 > csource_start):
        raise RuntimeError("Unexpected source-tail terminal order.")
    return {"vsource": (vsource_start, csource_start), "csource": (csource_start, len(chunk))}


def _translate_wires(out: bytearray, start: int, end: int, dx: int, dy: int) -> int:
    count = 0
    pos = start
    while True:
        marker = bytes(out).find(b"WIRE", pos, end)
        if marker < 0:
            break
        coord = marker + 9
        if coord + 16 <= end:
            _add_s32(out, coord, dx)
            _add_s32(out, coord + 4, dy)
            _add_s32(out, coord + 8, dx)
            _add_s32(out, coord + 12, dy)
            count += 1
        pos = marker + 1
    return count


def _translate_source_text_fields(out: bytearray, start: int, end: int, dx: int, dy: int) -> int:
    count = 0
    patterns = [
        (b"\xff\x02V1", 4),
        (b"\xff\x021V", 4),
        (b"\xff\x07VSOURCE", 9),
        (b"\x02\x00\x07VSOURCE", 10),
        (b"{PRIMITIVE=ANALOG}\n", len(b"{PRIMITIVE=ANALOG}\n")),
        (b"\xff\x02I1", 4),
        (b"\xff\x021A", 4),
        (b"\xff\x07CSOURCE", 9),
        (b"\x02\x00\x07CSOURCE", 10),
        (b"{PRIMITIVE=ANALOGUE}\n", len(b"{PRIMITIVE=ANALOGUE}\n")),
    ]
    data = bytes(out)
    for pattern, coord_delta in patterns:
        pos = start
        while True:
            found = data.find(pattern, pos, end)
            if found < 0:
                break
            coord = found + coord_delta
            if coord + 8 <= end:
                _add_s32(out, coord, dx)
                _add_s32(out, coord + 4, dy)
                count += 1
            pos = found + 1
    return count


def _translate_source_block(chunk: bytes, block_start: int, block_end: int, dx: int, dy: int) -> tuple[bytes, dict[str, Any]]:
    out = bytearray(chunk)
    terminal_count = 0
    for start, end, kind, label in _terminal_bounds(chunk):
        if block_start <= start < block_end:
            _translate_terminal(out, start, end, kind, dx, dy)
            terminal_count += 1
    wire_count = _translate_wires(out, block_start, block_end, dx, dy)
    source_field_count = _translate_source_text_fields(out, block_start, block_end, dx, dy)
    return bytes(out), {
        "block_start": block_start,
        "block_end": block_end,
        "dx": dx,
        "dy": dy,
        "terminal_count": terminal_count,
        "wire_count": wire_count,
        "source_field_count": source_field_count,
    }


def _relocate_sources_near_terminals(chunk: bytes, *, include_csource: bool) -> tuple[bytes, list[dict[str, Any]]]:
    out = chunk
    stats: list[dict[str, Any]] = []
    bounds = _source_block_bounds(out)

    source_tail = v11.GROUP_STARTS["source_tail_start"]
    out_dvo = _find_terminal(out, kind="OUT", label="DVO", before=source_tail)
    in_dvo = _find_terminal(out, kind="IN", label="DVO", after=source_tail)
    out_x, out_y = _terminal_symbol(out, out_dvo)
    in_x, in_y = _terminal_symbol(out, in_dvo)
    target_x, target_y = out_x, out_y + SOURCE_GAP
    out, stat = _translate_source_block(out, bounds["vsource"][0], bounds["vsource"][1], target_x - in_x, target_y - in_y)
    stat["source"] = "VSOURCE"
    stat["target_relation"] = "IN DVO source terminal placed one source gap above final OUT DVO terminal."
    stats.append(stat)

    if include_csource:
        bounds = _source_block_bounds(out)
        out_a7 = _find_terminal(out, kind="OUT", label="A7", before=source_tail)
        in_a7 = _find_terminal(out, kind="IN", label="A7", after=source_tail)
        out_x, out_y = _terminal_symbol(out, out_a7)
        in_x, in_y = _terminal_symbol(out, in_a7)
        target_x, target_y = out_x, out_y + SOURCE_GAP
        out, stat = _translate_source_block(out, bounds["csource"][0], bounds["csource"][1], target_x - in_x, target_y - in_y)
        stat["source"] = "CSOURCE"
        stat["target_relation"] = "IN A7 source terminal placed one source gap above the donor OUT A7 terminal cluster."
        stats.append(stat)
    return out, stats


def _suffix_mapped_splice(
    generated_body: bytes,
    donor_chunk: bytes,
    splice_start: int,
    *,
    relocate_sources: str,
) -> tuple[bytes, dict[str, Any]]:
    spliced = v11._splice_generated_prefix(generated_body, donor_chunk, splice_start)
    suffix_map = v11._suffix_map_by_terminal_order(donor_chunk, spliced, before=splice_start)
    mapped, map_stats = v11._apply_suffix_map_prefix(spliced, suffix_map, before=splice_start)
    source_stats: list[dict[str, Any]] = []
    if relocate_sources == "vsource_only":
        mapped, source_stats = _relocate_sources_near_terminals(mapped, include_csource=False)
    elif relocate_sources == "both":
        mapped, source_stats = _relocate_sources_near_terminals(mapped, include_csource=True)
    return mapped, {
        "splice_start": splice_start,
        "suffix_map_stats": map_stats,
        "source_relocation": source_stats,
        "relocate_sources": relocate_sources,
    }


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    v9.OUT_ROOT = OUT_ROOT
    v9.ARCHIVE_BASE = ARCHIVE_BASE
    v9.DONOR_ROOT = DONOR_ROOT
    donor = v9._copy_donor()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v9.rcl._load_rcl_unit_templates(rcl_donor)

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_chunk = rv9._extract_object_chunk(donor_dsn)
    v11._validate_boundary_constants(donor_chunk)
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_devices = v9.v5._device_section_from_dsn(donor_dsn)
    generated_body, generated_specs, generated_topology, generated_counts = v9._build_rcl_body_keep_v0_output(
        templates,
        negative_label="D0",
    )
    generated_cdb = v9._build_cdb(generated_specs)

    group9_plain, group9_plain_stats = _suffix_mapped_splice(
        generated_body,
        donor_chunk,
        v11.GROUP_STARTS["group_9_start"],
        relocate_sources="none",
    )
    group9_vsource_coords, group9_vsource_coords_stats = _suffix_mapped_splice(
        generated_body,
        donor_chunk,
        v11.GROUP_STARTS["group_9_start"],
        relocate_sources="vsource_only",
    )
    group9_both_coords, group9_both_coords_stats = _suffix_mapped_splice(
        generated_body,
        donor_chunk,
        v11.GROUP_STARTS["group_9_start"],
        relocate_sources="both",
    )
    group7_coords, group7_coords_stats = _suffix_mapped_splice(
        generated_body,
        donor_chunk,
        v11.GROUP_STARTS["group_7_start"],
        relocate_sources="both",
    )
    group4_coords, group4_coords_stats = _suffix_mapped_splice(
        generated_body,
        donor_chunk,
        v11.GROUP_STARTS["group_4_start"],
        relocate_sources="both",
    )

    cases: list[dict[str, Any]] = [
        v9._copy_control("DCMS_V12_T00_DONOR_COPY", "Exact copy of the user donor control.", donor),
        v9._write_case(
            "DCMS_V12_T01_DONOR_OBJECT_GENERATED_CDB",
            "Exact donor object structure and donor device section, but generated CDB rows.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_chunk,
            cdb=generated_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_object_with_generated_cdb"},
        ),
        v9._write_case(
            "DCMS_V12_T02_GROUP9_SUFFIXMAP_CONTROL",
            "Known-open V11 style: generated groups 1-8, donor group 9/source tail, suffix-mapped prefix, no coordinate relocation.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=group9_plain,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "group9_suffixmap_control", **group9_plain_stats},
        ),
        v9._write_case(
            "DCMS_V12_T03_GROUP9_SUFFIXMAP_VSOURCE_COORDS",
            "Group-9 suffix-map case with only the VSOURCE visual block moved close to its matching DVO terminal cluster.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=group9_vsource_coords,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "group9_suffixmap_with_vsource_coordinate_relocation", **group9_vsource_coords_stats},
        ),
        v9._write_case(
            "DCMS_V12_T04_GROUP9_SUFFIXMAP_BOTH_COORDS",
            "Group-9 suffix-map case with VSOURCE and CSOURCE visual blocks moved close to their matching terminal clusters.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=group9_both_coords,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "group9_suffixmap_with_both_source_coordinate_relocation", **group9_both_coords_stats},
        ),
        v9._write_case(
            "DCMS_V12_T05_GROUP7_SUFFIXMAP_BOTH_COORDS",
            "Group-7-to-tail suffix-map case with source visual blocks moved close to their matching terminal clusters.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=group7_coords,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "group7_suffixmap_with_source_coordinate_relocation", **group7_coords_stats},
        ),
        v9._write_case(
            "DCMS_V12_T06_GROUP4_SUFFIXMAP_BOTH_COORDS",
            "New group-4-to-tail suffix-map case with source visual blocks moved close to their matching terminal clusters.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=group4_coords,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "group4_suffixmap_with_source_coordinate_relocation", **group4_coords_stats},
        ),
    ]

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V12_SUFFIXMAP_COORDS_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "User reported V11 T02/T04/T06/T07 VGDVC.dll; the other cases opened but source blocks were too far from connected terminals.",
        "method": "Use suffix-map variants only, add missing group-4 suffix-map, and test source-block coordinate relocation without changing lengths or suffix bytes.",
        "group_starts": v11.GROUP_STARTS,
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item.get("marker_counts"),
                "object_chunk_len": item.get("object_chunk_len"),
                "root_cdb_len": item.get("root_cdb_len"),
                "static_validation_issues": item.get("static_validation_issues"),
            }
            for item in cases
        ],
        "generated_counts": generated_counts,
        "generated_topology": generated_topology,
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V12_SUFFIXMAP_COORDS_TEMP_2026_06_05\n\n"
        "Open in order:\n"
        + "\n".join(
            f"{index}. {case_id}.pdsprj" if index == 1 else f"{index}. {case_id}/{case_id}.pdsprj"
            for index, case_id in enumerate(summary["test_order"], start=1)
        )
        + "\n\nT00/T01 are controls. T02 repeats the known-open suffix-map boundary without coordinate changes. "
        "T03 moves only the voltage source. T04/T05/T06 keep suffix mapping and move both source blocks closer to their connected terminal clusters.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
