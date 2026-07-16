"""Generate focused mixed-IC/analog diagnostics after V2 layout artifacts.

V2 moved IC bodies and pin terminals but left terminal-label and component-text
coordinates behind. This pack is intentionally smaller and slower:

- two text-aligned layout retries for previously simulating mixed IC cases;
- two accepted real mixed IC/analog subset cases with RLC, NPN, PNP, LM741,
  and CAP-ELEC present;
- two focused 74HC4060 controls that keep the device visible instead of
  removing it;
- one NE555/RLC whole-donor control for the coming timer path.

No broad lock-in is implied by this pack.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import parse_cdb


REPO = Path(__file__).resolve().parents[4]
ACCEPTED_V1_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-10" / "generate_mixed_ic_cross_donor_accepted_v1_temp.py"
SUBSET_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_analog_subset_v1_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_focused_v3_temp_2026_06_10"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_FOCUSED_V3_TEMP_2026_06_10.zip"

IC_SLOT_COLUMNS = 3
IC_SLOT_X = 6_096_000
IC_SLOT_Y = 5_080_000
IC_LAYOUT_ORIGIN_X = -8_890_000
IC_LAYOUT_ORIGIN_Y = -3_810_000
SCAN_COORD_LIMIT = 15_000_000


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


accepted_v1 = _load_module("mixed_ic_cross_donor_accepted_v1_for_focused_v3", ACCEPTED_V1_SCRIPT)
subset_v1 = _load_module("mixed_ic_analog_subset_v1_for_focused_v3", SUBSET_SCRIPT)
seq = accepted_v1.base_iso.seq


@dataclass(frozen=True)
class LayoutCase:
    case_id: str
    description: str
    selections: tuple[object, ...]
    header_donor_key: str
    expected_markers: tuple[str, ...]


@dataclass(frozen=True)
class AnalogSubsetCase:
    case_id: str
    description: str
    donor_key: str
    keep_markers: tuple[str, ...]
    mutate_labels: bool = True


@dataclass(frozen=True)
class WholeDonorCase:
    case_id: str
    description: str
    donor_path: Path
    required_markers: tuple[str, ...]
    mutate_labels: bool = True


def _s32(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)


def _add_s32(data: bytearray, offset: int, delta: int) -> None:
    _put_s32(data, offset, _s32(data, offset) + delta)


def _coord_ok(value: int) -> bool:
    return -SCAN_COORD_LIMIT <= value <= SCAN_COORD_LIMIT and value % 100 == 0


def _bidir_terminal_records(fragment: bytes) -> list[tuple[int, int, dict[str, object]]]:
    records: list[tuple[int, int, dict[str, object]]] = []
    chunk = b"\x00" + fragment + b"\xff"
    for event in seq.bidir_events(chunk):
        start = int(event["start"]) - 1
        size = int(event["size"])
        if start >= 0 and start + size <= len(fragment):
            records.append((start, start + size, event))
    return records


def _terminal_coord_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    for start, _end, event in _bidir_terminal_records(fragment):
        label_len = fragment[start + 30]
        label_x = start + 31 + label_len
        label_y = label_x + 4
        pairs.append((start + 1, start + 5, f"terminal_symbol:{event['label']}"))
        if label_y + 4 <= len(fragment):
            pairs.append((label_x, label_y, f"terminal_label:{event['label']}"))
    return pairs


def _wire_coord_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    pos = 0
    while True:
        marker = fragment.find(b"WIRE", pos)
        if marker < 0:
            return pairs
        coord = marker + 9
        if coord + 16 <= len(fragment):
            pairs.append((coord, coord + 4, "wire_start"))
            pairs.append((coord + 8, coord + 12, "wire_end"))
        pos = marker + 1


def _masked_ranges(fragment: bytes) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    ranges.extend((start, end) for start, end, _event in _bidir_terminal_records(fragment))
    pos = 0
    while True:
        marker = fragment.find(b"WIRE", pos)
        if marker < 0:
            break
        ranges.append((marker + 9, marker + 25))
        pos = marker + 1
    return ranges


def _is_masked(offset: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end or start < offset + 8 <= end for start, end in ranges)


def _text_and_body_coord_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    ranges = _masked_ranges(fragment)
    offset = 0
    while offset <= len(fragment) - 8:
        if _is_masked(offset, ranges):
            offset += 1
            continue
        x = _s32(fragment, offset)
        y = _s32(fragment, offset + 4)
        if _coord_ok(x) and _coord_ok(y) and not (x == 0 and y == 0) and (
            abs(x) >= 50_000 or abs(y) >= 50_000
        ):
            pairs.append((offset, offset + 4, "component_text_or_body"))
            offset += 8
            continue
        offset += 1
    return pairs


def _layout_coord_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs = _terminal_coord_pairs(fragment) + _wire_coord_pairs(fragment) + _text_and_body_coord_pairs(fragment)
    seen: set[tuple[int, int]] = set()
    ordered: list[tuple[int, int, str]] = []
    for x_offset, y_offset, reason in pairs:
        key = (x_offset, y_offset)
        if key not in seen:
            seen.add(key)
            ordered.append((x_offset, y_offset, reason))
    return ordered


def _bbox(fragment: bytes, pairs: list[tuple[int, int, str]]) -> dict[str, int]:
    xs = [_s32(fragment, x_offset) for x_offset, _y_offset, _reason in pairs]
    ys = [_s32(fragment, y_offset) for _x_offset, y_offset, _reason in pairs]
    return {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def _translate_fragment_to_slot(fragment: bytes, marker: str, slot: int) -> tuple[bytes, dict[str, object]]:
    pairs = _layout_coord_pairs(fragment)
    if not pairs:
        return fragment, {"slot": slot, "marker": marker, "translated": False, "reason": "no coordinate pairs"}
    before = _bbox(fragment, pairs)
    col = slot % IC_SLOT_COLUMNS
    row = slot // IC_SLOT_COLUMNS
    dx = IC_LAYOUT_ORIGIN_X + col * IC_SLOT_X - before["min_x"]
    dy = IC_LAYOUT_ORIGIN_Y + row * IC_SLOT_Y - before["min_y"]
    out = bytearray(fragment)
    for x_offset, y_offset, _reason in pairs:
        _add_s32(out, x_offset, dx)
        _add_s32(out, y_offset, dy)
    translated = bytes(out)
    reason_counts: dict[str, int] = {}
    for _x_offset, _y_offset, reason in pairs:
        reason_counts[reason] = reason_counts.get(reason, 0) + 1
    return translated, {
        "slot": slot,
        "marker": marker,
        "translated": True,
        "dx": dx,
        "dy": dy,
        "coordinate_pair_count": len(pairs),
        "coordinate_reason_counts": reason_counts,
        "before_bbox": before,
        "after_bbox": _bbox(translated, pairs),
    }


def object_chunk_for_text_aligned_layout(
    selections: tuple[object, ...],
) -> tuple[bytes, list[dict[str, object]], list[dict[str, object]]]:
    fragments: list[bytes] = []
    region_plan: list[dict[str, object]] = []
    layout_plan: list[dict[str, object]] = []
    slot = 0
    for selection in selections:
        selected, metadata = accepted_v1.base_iso.v1.selected_fragments(selection)
        for fragment, entry in zip(selected, metadata):
            marker = str(entry["marker"])
            translated, layout_entry = _translate_fragment_to_slot(fragment, marker, slot)
            layout_entry["refs_unchanged"] = accepted_v1.base_iso.refs_in(fragment) == accepted_v1.base_iso.refs_in(translated)
            layout_entry["marker_count_before"] = fragment.count(marker.encode("ascii"))
            layout_entry["marker_count_after"] = translated.count(marker.encode("ascii"))
            layout_plan.append(layout_entry)
            entry = dict(entry)
            entry["layout_slot"] = slot
            fragments.append(translated)
            region_plan.append(entry)
            slot += 1
    return b"\x00" + b"".join(fragments) + b"\xff", region_plan, layout_plan


def replacements_for(header_donor_key: str, selections: tuple[object, ...]) -> tuple[tuple[str, str], ...]:
    replacements: list[tuple[str, str]] = []
    for selection in selections:
        if selection.donor_key == header_donor_key:
            continue
        replacements.extend((selection.donor_key, ref) for ref in selection.cdb_refs)
    return tuple(replacements)


def cdb_for_layout_case(case: LayoutCase) -> tuple[bytes, list[dict[str, object]], str]:
    replacement_sources = replacements_for(case.header_donor_key, case.selections)
    if not replacement_sources:
        return accepted_v1.base_iso.donor_cdb(case.header_donor_key), [], "full_header_donor"
    cdb, row_plan = accepted_v1.cdb_v2.build_full_skeleton_cdb(
        case.header_donor_key,
        replacement_sources,
        replace_pins=True,
        replace_properties=True,
    )
    return cdb, row_plan, "accepted_full_skeleton_replaced_rows"


def write_layout_case(case: LayoutCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    object_chunk, region_plan, layout_plan = object_chunk_for_text_aligned_layout(case.selections)
    cdb, cdb_row_plan, cdb_mode = cdb_for_layout_case(case)
    pointers, device_plan = accepted_v1.base_iso.write_dsn(
        output,
        object_chunk=object_chunk,
        cdb=cdb,
        header_donor_key=case.header_donor_key,
        device_mode="full_multi",
        selections=case.selections,
    )
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    parsed = parse_cdb(cdb)
    return _write_manifest(
        case_dir,
        output,
        {
            "case_id": case.case_id,
            "description": case.description,
            "method": "focused_cross_donor_text_aligned_whole_region_layout",
            "status": "temporary_pending_user_proteus_testing",
            "header_donor_key": case.header_donor_key,
            "cdb_mode": cdb_mode,
            "expected_markers": case.expected_markers,
            "region_plan": region_plan,
            "layout_plan": layout_plan,
            "layout_refs_unchanged": all(bool(entry["refs_unchanged"]) for entry in layout_plan),
            "layout_markers_unchanged": all(
                entry["marker_count_before"] == entry["marker_count_after"] for entry in layout_plan
            ),
            "cdb_row_plan": cdb_row_plan,
            "parsed_cdb": {
                "count": parsed.count,
                "pin_refs": [row.ref for row in parsed.pin_rows],
                "property_refs": [row.ref for row in parsed.property_rows],
            },
            "device_plan": device_plan,
            "section_pointers": pointers,
            "object_refs": accepted_v1.base_iso.refs_in(chunk),
            "cdb_refs": accepted_v1.base_iso.refs_in(cdb),
            "object_ref_subset_of_cdb": set(accepted_v1.base_iso.refs_in(chunk)).issubset(
                set(accepted_v1.base_iso.refs_in(cdb))
            ),
            "marker_counts": accepted_v1.base_iso.mixed.marker_counts(chunk) | {"7447": chunk.count(b"7447")},
            "cdb_marker_counts": accepted_v1.base_iso.mixed.marker_counts(cdb) | {"7447": cdb.count(b"7447")},
            "static_validation_issues": accepted_v1.base_iso.static_issues(output, case.expected_markers),
        },
    )


def write_analog_subset_case(case: AnalogSubsetCase) -> dict[str, object]:
    donor = subset_v1.donor_by_key(case.donor_key)
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    donor_dsn = seq.read_internal_file(donor.path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(donor.path, "ROOT.CDB")
    original_chunk = seq._extract_object_chunk(donor_dsn)
    regions = subset_v1.discover_regions(original_chunk)
    subset_chunk, kept_regions, removed_regions = subset_v1.build_subset_chunk(original_chunk, regions, case.keep_markers)
    label_plan: list[dict[str, object]] = []
    mutations: list[dict[str, object]] = []
    if case.mutate_labels:
        replacements, label_plan = subset_v1.mixed.topology_preserving_replacements(subset_chunk)
        subset_chunk, mutations = seq.patch_bidir_labels(subset_chunk, replacements)
    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        subset_chunk,
        seq._device_section(donor_dsn),
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": donor_cdb,
        },
    )
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    removed_markers = tuple(sorted({str(region["marker"]) for region in removed_regions}))
    return _write_manifest(
        case_dir,
        output,
        {
            "case_id": case.case_id,
            "description": case.description,
            "method": "accepted_real_mixed_ic_analog_subset_with_full_donor_cdb_device_section",
            "status": "temporary_pending_user_proteus_testing",
            "donor_key": donor.key,
            "donor": str(donor.path.relative_to(REPO)),
            "keep_markers": case.keep_markers,
            "removed_markers": removed_markers,
            "terminal_policy": "all retained visible endpoints use donor-native $TERBIDIR records",
            "composition_policy": "remove complete contiguous object regions only; keep donor ROOT.CDB and device section whole",
            "label_plan": label_plan,
            "mutations": mutations,
            "kept_regions": kept_regions,
            "removed_regions": removed_regions,
            "section_pointers": pointers,
            "marker_counts": subset_v1.mixed.marker_counts(chunk),
            "cdb_marker_counts": subset_v1.mixed.marker_counts(cdb),
            "static_validation_issues": subset_v1.static_issues(output, case.keep_markers, removed_markers, mutations),
        },
    )


def write_whole_donor_case(case: WholeDonorCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    donor_dsn = seq.read_internal_file(case.donor_path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(case.donor_path, "ROOT.CDB")
    chunk = seq._extract_object_chunk(donor_dsn)
    label_plan: list[dict[str, object]] = []
    mutations: list[dict[str, object]] = []
    if case.mutate_labels and chunk.count(b"$TERBIDIR"):
        replacements, label_plan = subset_v1.mixed.topology_preserving_replacements(chunk)
        chunk, mutations = seq.patch_bidir_labels(chunk, replacements)
    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        chunk,
        seq._device_section(donor_dsn),
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": donor_cdb,
        },
    )
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    issues: list[str] = []
    for marker in case.required_markers:
        raw = marker.encode("ascii")
        if raw not in chunk:
            issues.append(f"expected DSN marker {marker} missing")
        if raw not in cdb:
            issues.append(f"expected CDB marker {marker} missing")
    if chunk.count(b"$TERBIDIR") and chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    return _write_manifest(
        case_dir,
        output,
        {
            "case_id": case.case_id,
            "description": case.description,
            "method": "whole_donor_object_cdb_device_section_inserted_into_e001",
            "status": "temporary_pending_user_proteus_testing",
            "donor": str(case.donor_path.relative_to(REPO)),
            "required_markers": case.required_markers,
            "terminal_policy": "donor-native visible endpoints retained; bidirectional labels optionally mutated topology-preservingly",
            "label_plan": label_plan,
            "mutations": mutations,
            "section_pointers": pointers,
            "marker_counts": subset_v1.mixed.marker_counts(chunk),
            "cdb_marker_counts": subset_v1.mixed.marker_counts(cdb),
            "static_validation_issues": issues,
        },
    )


def _write_manifest(case_dir: Path, output: Path, manifest: dict[str, object]) -> dict[str, object]:
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    manifest = dict(manifest)
    manifest["container"] = {
        key: (str(value) if key == "path" else value)
        for key, value in seq.inspect_pdsprj(output).__dict__.items()
    }
    manifest["object_chunk_size"] = len(chunk)
    manifest["terminal_count"] = chunk.count(b"$TERBIDIR") + chunk.count(b"$TERINPUT") + chunk.count(b"$TEROUTPUT")
    manifest["wire_count"] = chunk.count(b"WIRE")
    manifest["output_hashes"] = {
        "project": seq._sha256_bytes(output.read_bytes()),
        "ROOT.DSN": seq._sha256_bytes(dsn),
        "ROOT.CDB": seq._sha256_bytes(cdb),
        "object_chunk": seq._sha256_bytes(chunk),
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(seq.bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


LAYOUT_CASES: tuple[LayoutCase, ...] = (
    LayoutCase(
        "T01_TEXTFIX_SHIFT_REGISTERS_WITH_DIVIDERS",
        "Text-aligned retry for V2 T01: 74HC595/74HC165 with 4017/4020/74HC4024.",
        (accepted_v1.MISC_SHIFT, accepted_v1.SEQ_DIVIDERS),
        "misc_logic_analog",
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    LayoutCase(
        "T02_TEXTFIX_DECODER_WITH_SYNC_COUNTERS",
        "Text-aligned retry for V2 T02: 7447 with 74HC160/161/163.",
        (accepted_v1.MISC_DECODER, accepted_v1.SEQ_SYNC),
        "seq_counters_all",
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
)

ANALOG_CASES: tuple[AnalogSubsetCase, ...] = (
    AnalogSubsetCase(
        "T03_ANALOG_RCL_SHIFT_REGISTERS",
        "Accepted real mixed donor subset: RLC, NPN, PNP, LM741, CAP-ELEC plus 74HC595/74HC165.",
        "misc_logic_analog",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "74HC595", "74HC165"),
    ),
    AnalogSubsetCase(
        "T04_ANALOG_RCL_DIVIDERS",
        "Accepted real mixed donor subset: RLC, NPN, PNP, LM741, CAP-ELEC plus 4017/4020/74HC4024.",
        "seq_4017_4020_4024",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "4017", "4020", "74HC4024"),
    ),
    AnalogSubsetCase(
        "T06_4060_WITH_ANALOG_RCL_PREFIX",
        "Focused 74HC4060 isolation from accepted mixed donor with analog/RLC prefix retained.",
        "seq_counters_all",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "74HC4060"),
    ),
)

WHOLE_DONOR_CASES: tuple[WholeDonorCase, ...] = (
    WholeDonorCase(
        "T05_4060_RLC_SOLO_CONTROL",
        "Accepted solo donor control for 74HC4060 with RLC present; keeps visible 74HC4060 instead of removing it.",
        REPO / "proteus" / "active" / "evidence" / "donors" / "sequential_ics_batch3" / "4_74HC4060withRLC.pdsprj",
        ("74HC4060", "RESISTOR", "CAPACITOR", "REALIND"),
    ),
    WholeDonorCase(
        "T07_NE555_RLC_SOLO_CONTROL",
        "Whole-donor NE555 with RLC control for the upcoming timer path.",
        REPO / "proteus" / "active" / "evidence" / "donors" / "analog_misc_batch1" / "2_NE555WITHRLC.pdsprj",
        ("NE555", "RESISTOR", "CAPACITOR", "REALIND"),
    ),
)


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 10, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests: list[dict[str, object]] = []
    manifests.extend(write_layout_case(case) for case in LAYOUT_CASES)
    manifests.extend(write_analog_subset_case(case) for case in ANALOG_CASES)
    manifests.extend(write_whole_donor_case(case) for case in WHOLE_DONOR_CASES)
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_FOCUSED_V3_TEMP_2026_06_10",
        "purpose": "Small focused retry after V2 layout artifacts. Fix text/terminal-label coordinate movement and re-center on accepted RLC/analog donors.",
        "status": "temporary_pending_user_proteus_testing",
        "testing_order": [
            "T01-T02 verify the artifact fix on known practical IC cases.",
            "T03-T04 verify RLC/NPN/PNP/LM741/CAP-ELEC remain in the active sample set.",
            "T05-T06 isolate visible 74HC4060 with RLC/analog context instead of removing it.",
            "T07 is a NE555/RLC control for the future timer route.",
        ],
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
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
                "static_issue_cases": summary_issues,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
