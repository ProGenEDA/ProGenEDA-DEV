"""Generate cross-donor mixed IC probes from accepted mixed donor regions.

MIXED_IC_ANALOG_SUBSET_V1 proved that whole balanced regions can be removed
inside one real mixed donor. This V1 cross-donor pack combines whole IC regions
from different accepted mixed donors, choosing only regions whose existing U
references do not collide. It intentionally avoids analog/passive rows in this
first probe and does not rewrite component references.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
SUBSET_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_analog_subset_v1_temp.py"
OUT_ROOT = REPO / "experiments" / "mixed_ic_cross_donor_v1_temp_2026_06_09"
ARCHIVE_PATH = REPO / "experiments" / "MIXED_IC_CROSS_DONOR_V1_TEMP_2026_06_09.zip"


def load_subset_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_analog_subset_v1_for_cross_donor", SUBSET_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load subset helper from {SUBSET_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


subset = load_subset_module()
mixed = subset.mixed
seq = subset.seq


COMPONENT_MARKERS = (
    b"74HC4024",
    b"74HC4040",
    b"74HC4060",
    b"74HC4520",
    b"74HC192",
    b"74HC193",
    b"74HC160",
    b"74HC161",
    b"74HC163",
    b"74HC157",
    b"74HC283",
    b"74HC165",
    b"74HC595",
    b"74HC85",
    b"7447",
    b"CAP-ELEC",
    b"RESISTOR",
    b"CAPACITOR",
    b"REALIND",
    b"LM741",
    b"NPN",
    b"PNP",
    b"7490",
    b"4017",
    b"4020",
    b"4518",
)


@dataclass(frozen=True)
class Region:
    index: int
    marker: str
    start: int
    end: int
    marker_pos: int

    @property
    def size(self) -> int:
        return self.end - self.start

    def as_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "marker": self.marker,
            "start": self.start,
            "end": self.end,
            "size": self.size,
            "marker_pos": self.marker_pos,
        }


@dataclass(frozen=True)
class RegionSelection:
    donor_key: str
    markers: tuple[str, ...]
    cdb_refs: tuple[str, ...]
    label_prefix: str


@dataclass(frozen=True)
class CrossCase:
    case_id: str
    description: str
    selections: tuple[RegionSelection, ...]
    expected_markers: tuple[str, ...]


@dataclass(frozen=True)
class CdbParts:
    header: bytes
    post_pin_header: bytes
    pin_rows: dict[str, bytes]
    prop_rows: dict[str, bytes]


def donor_by_key(key: str):
    return next(donor for donor in mixed.DONORS if donor.key == key)


def marker_occurrences(chunk: bytes) -> list[tuple[int, str]]:
    raw_occurrences: list[tuple[int, str]] = []
    for marker in COMPONENT_MARKERS:
        start = 0
        while True:
            position = chunk.find(marker, start)
            if position < 0:
                break
            raw_occurrences.append((position, marker.decode("ascii")))
            start = position + 1
    raw_occurrences.sort()

    filtered: list[tuple[int, str]] = []
    for position, marker in raw_occurrences:
        raw = marker.encode("ascii")
        contained_in_longer = False
        for other_position, other_marker in raw_occurrences:
            if other_position == position and len(other_marker) <= len(marker):
                continue
            other_raw = other_marker.encode("ascii")
            if (
                len(other_raw) > len(raw)
                and other_position <= position
                and position + len(raw) <= other_position + len(other_raw)
            ):
                contained_in_longer = True
                break
        if not contained_in_longer:
            filtered.append((position, marker))
    return filtered


def discover_regions(chunk: bytes) -> list[Region]:
    terminals = [int(event["start"]) for event in seq.bidir_events(chunk)]
    if not terminals:
        raise ValueError("Cannot discover component regions without bidirectional terminals.")

    region_markers: list[tuple[int, str]] = []
    last_component_marker = -1
    for marker_pos, marker in marker_occurrences(chunk):
        if last_component_marker < 0 or any(last_component_marker < terminal < marker_pos for terminal in terminals):
            region_markers.append((marker_pos, marker))
            last_component_marker = marker_pos

    if not region_markers:
        raise ValueError("No component regions discovered.")

    starts: list[int] = []
    for index, (marker_pos, _marker) in enumerate(region_markers):
        if index == 0:
            starts.append(min(terminal for terminal in terminals if terminal < marker_pos))
        else:
            previous_marker_pos = region_markers[index - 1][0]
            starts.append(min(terminal for terminal in terminals if previous_marker_pos < terminal < marker_pos))
    ends = starts[1:] + [len(chunk) - 1]
    return [
        Region(index=index, marker=marker, start=start, end=end, marker_pos=marker_pos)
        for index, ((marker_pos, marker), start, end) in enumerate(zip(region_markers, starts, ends))
    ]


def cdb_parts(data: bytes) -> CdbParts:
    matches = [(match.group().decode("ascii"), match.start()) for match in re.finditer(rb"U\d+", data)]
    if len(matches) < 2 or len(matches) % 2:
        raise ValueError("CDB U-reference rows are not in the expected pin/property pairs.")
    row_count = len(matches) // 2
    pin_starts = matches[:row_count]
    prop_starts = matches[row_count:]
    header = data[: pin_starts[0][1]]
    last_pin_end = prop_starts[0][1] - 22
    post_pin_header = data[last_pin_end : prop_starts[0][1]]
    pin_rows: dict[str, bytes] = {}
    prop_rows: dict[str, bytes] = {}
    for index, (ref, start) in enumerate(pin_starts):
        end = pin_starts[index + 1][1] if index + 1 < row_count else last_pin_end
        pin_rows[ref] = data[start:end]
    for index, (ref, start) in enumerate(prop_starts):
        end = prop_starts[index + 1][1] if index + 1 < row_count else len(data)
        prop_rows[ref] = data[start:end]
    if set(pin_rows) != set(prop_rows):
        raise ValueError("CDB pin/property reference sets do not match.")
    return CdbParts(header=header, post_pin_header=post_pin_header, pin_rows=pin_rows, prop_rows=prop_rows)


def mutate_fragment_labels(fragment: bytes, prefix: str) -> tuple[bytes, list[dict[str, object]]]:
    replacements: dict[int, str] = {}
    group_names: dict[str, str] = {}
    group_index = 0
    events = seq.bidir_events(fragment)
    for index, event in enumerate(events):
        old_label = str(event["label"])
        if old_label:
            group_names.setdefault(old_label, f"{prefix}{group_index:02d}")
            label = group_names[old_label]
        else:
            label = f"{prefix}{group_index:02d}"
        replacements[index] = label
        group_index += 1
    return seq.patch_bidir_labels(fragment, replacements, force_final=False)


def selected_fragments(selection: RegionSelection) -> tuple[list[bytes], list[dict[str, object]]]:
    donor = donor_by_key(selection.donor_key)
    chunk = seq._extract_object_chunk(seq.read_internal_file(donor.path, "ROOT.DSN"))
    regions = discover_regions(chunk)
    keep = [region for region in regions if region.marker in set(selection.markers)]
    found = tuple(region.marker for region in keep)
    if found != selection.markers:
        raise ValueError(f"{selection.donor_key} expected region markers {selection.markers}, found {found}")
    fragments: list[bytes] = []
    metadata: list[dict[str, object]] = []
    for region_index, region in enumerate(keep):
        raw = chunk[region.start : region.end]
        patched, mutations = mutate_fragment_labels(raw, f"{selection.label_prefix}{region_index}")
        fragments.append(patched)
        metadata.append(
            {
                "donor_key": selection.donor_key,
                "marker": region.marker,
                "region": region.as_dict(),
                "cdb_refs": selection.cdb_refs,
                "label_prefix": selection.label_prefix,
                "terminal_count": patched.count(b"$TERBIDIR"),
                "wire_count": patched.count(b"WIRE"),
                "mutations": mutations,
            }
        )
    return fragments, metadata


def build_cross_cdb(selections: tuple[RegionSelection, ...]) -> tuple[bytes, list[dict[str, object]]]:
    ref_sources: list[tuple[str, str]] = []
    for selection in selections:
        for ref in selection.cdb_refs:
            ref_sources.append((selection.donor_key, ref))
    refs = [ref for _donor_key, ref in ref_sources]
    if len(refs) != len(set(refs)):
        raise ValueError(f"Cross-donor case has duplicate CDB refs: {refs}")

    parts_by_donor: dict[str, CdbParts] = {}
    for donor_key, _ref in ref_sources:
        if donor_key not in parts_by_donor:
            donor = donor_by_key(donor_key)
            parts_by_donor[donor_key] = cdb_parts(seq.read_internal_file(donor.path, "ROOT.CDB"))

    first_parts = parts_by_donor[ref_sources[0][0]]
    header = bytearray(first_parts.header)
    if len(header) <= 92:
        raise ValueError("CDB header is too short for the observed component-count byte.")
    header[92] = len(ref_sources)
    pin_rows: list[bytes] = []
    prop_rows: list[bytes] = []
    row_plan: list[dict[str, object]] = []
    for donor_key, ref in ref_sources:
        parts = parts_by_donor[donor_key]
        if ref not in parts.pin_rows or ref not in parts.prop_rows:
            raise ValueError(f"{donor_key} CDB does not contain ref {ref}")
        pin_rows.append(parts.pin_rows[ref])
        prop_rows.append(parts.prop_rows[ref])
        row_plan.append(
            {
                "donor_key": donor_key,
                "ref": ref,
                "pin_row_size": len(parts.pin_rows[ref]),
                "prop_row_size": len(parts.prop_rows[ref]),
            }
        )
    return bytes(header) + b"".join(pin_rows) + first_parts.post_pin_header + b"".join(prop_rows), row_plan


def build_device_section(selections: tuple[RegionSelection, ...]) -> bytes:
    seen: set[str] = set()
    sections: list[bytes] = []
    for selection in selections:
        if selection.donor_key in seen:
            continue
        seen.add(selection.donor_key)
        donor = donor_by_key(selection.donor_key)
        sections.append(seq._device_section(seq.read_internal_file(donor.path, "ROOT.DSN")))
    return b"".join(sections)


def static_issues(output: Path, case: CrossCase, row_plan: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    info = seq.inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("cross-donor sequential/misc IC output should use $TERBIDIR only")
    if chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    for marker in case.expected_markers:
        raw = marker.encode("ascii")
        if raw not in chunk:
            issues.append(f"expected DSN marker {marker} missing")
        if raw not in cdb:
            issues.append(f"expected CDB marker {marker} missing")
    refs = [str(item["ref"]) for item in row_plan]
    if len(refs) != len(set(refs)):
        issues.append("duplicate CDB refs in row plan")
    for ref in refs:
        if cdb.count(ref.encode("ascii")) != 2:
            issues.append(f"CDB ref {ref} should have exactly two rows")
    return issues


CASES = (
    CrossCase(
        "T01_MISC_WITH_LATE_COUNTERS",
        "Mix misc logic/shift-register regions with later counter/divider regions not supplied together by the user.",
        (
            RegionSelection("misc_logic_analog", ("74HC595", "74HC165", "7447", "74HC157", "74HC283", "74HC85"), ("U2", "U3", "U4", "U5", "U6", "U7"), "A"),
            RegionSelection("seq_counters_all", ("4518", "74HC4060", "74HC4040", "7490", "74HC160", "74HC161", "74HC163"), ("U8", "U9", "U10", "U11", "U12", "U13", "U14"), "B"),
        ),
        ("74HC595", "74HC165", "7447", "74HC157", "74HC283", "74HC85", "4518", "74HC4060", "74HC4040", "7490", "74HC160", "74HC161", "74HC163"),
    ),
    CrossCase(
        "T02_DIVIDERS_WITH_SHIFT_REGISTERS",
        "Mix 4017/4020/74HC4024 divider chain with 74HC595 and 74HC165 shift-register regions.",
        (
            RegionSelection("misc_logic_analog", ("74HC595", "74HC165"), ("U2", "U3"), "C"),
            RegionSelection("seq_counters_all", ("4017", "4020", "74HC4024"), ("U4", "U5", "U6"), "D"),
        ),
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    CrossCase(
        "T03_UPDOWN_WITH_COMPARATOR_MUX_ADDER",
        "Mix 74HC192/74HC193 up/down counters with 74HC157, 74HC283, and 74HC85.",
        (
            RegionSelection("seq_counters_all", ("74HC193", "74HC192"), ("U2", "U1"), "E"),
            RegionSelection("misc_logic_analog", ("74HC157", "74HC283", "74HC85"), ("U5", "U6", "U7"), "F"),
        ),
        ("74HC193", "74HC192", "74HC157", "74HC283", "74HC85"),
    ),
    CrossCase(
        "T04_SEVEN_SEG_WITH_SYNC_COUNTERS",
        "Mix the 7447 seven-segment decoder/driver region with 74HC160/161/163 synchronous counters.",
        (
            RegionSelection("misc_logic_analog", ("7447",), ("U4",), "G"),
            RegionSelection("seq_counters_all", ("74HC160", "74HC161", "74HC163"), ("U12", "U13", "U14"), "H"),
        ),
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
    CrossCase(
        "T05_192_193_WITH_MISC_COMPUTE",
        "Mix 74HC192/74HC193 with 74HC165, 7447, 74HC157, 74HC283, and 74HC85 while preserving unique refs.",
        (
            RegionSelection("seq_counters_all", ("74HC193", "74HC192"), ("U2", "U1"), "J"),
            RegionSelection("misc_logic_analog", ("74HC165", "7447", "74HC157", "74HC283", "74HC85"), ("U3", "U4", "U5", "U6", "U7"), "K"),
        ),
        ("74HC193", "74HC192", "74HC165", "7447", "74HC157", "74HC283", "74HC85"),
    ),
    CrossCase(
        "T06_LARGE_NO_REF_COLLISION",
        "Large no-ref-collision cross-donor mix: shift/register/decoder/adder/comparator with late counters.",
        (
            RegionSelection("misc_logic_analog", ("74HC595", "74HC165", "7447", "74HC157", "74HC283", "74HC85"), ("U2", "U3", "U4", "U5", "U6", "U7"), "L"),
            RegionSelection("seq_counters_all", ("4518", "74HC4060", "74HC4040", "7490", "74HC160", "74HC161", "74HC163"), ("U8", "U9", "U10", "U11", "U12", "U13", "U14"), "M"),
        ),
        ("74HC595", "74HC165", "7447", "74HC157", "74HC283", "74HC85", "4518", "74HC4060", "74HC4040", "7490", "74HC160", "74HC161", "74HC163"),
    ),
)


def write_case(case: CrossCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    fragments: list[bytes] = []
    region_plan: list[dict[str, object]] = []
    for selection in case.selections:
        selected, metadata = selected_fragments(selection)
        fragments.extend(selected)
        region_plan.extend(metadata)
    object_chunk = b"\x00" + b"".join(fragments) + b"\xff"
    cdb, row_plan = build_cross_cdb(case.selections)
    device_section = build_device_section(case.selections)

    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    first_donor = donor_by_key(case.selections[0].donor_key)
    donor_dsn = seq.read_internal_file(first_donor.path, "ROOT.DSN")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        object_chunk,
        device_section,
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "method": "cross_donor_whole_balanced_region_concat_unique_refs_union_cdb_concat_device_sections",
        "status": "temporary_pending_user_proteus_testing",
        "terminal_policy": "all retained visible endpoints use donor-native $TERBIDIR records with generated unique labels",
        "composition_policy": "combine complete IC regions only; no analog/passive regions; no component ref rewriting",
        "selections": [
            {
                "donor_key": selection.donor_key,
                "markers": selection.markers,
                "cdb_refs": selection.cdb_refs,
                "label_prefix": selection.label_prefix,
            }
            for selection in case.selections
        ],
        "expected_markers": case.expected_markers,
        "region_plan": region_plan,
        "cdb_row_plan": row_plan,
        "section_pointers": pointers,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": mixed.marker_counts(chunk) | {"7447": chunk.count(b"7447")},
        "cdb_marker_counts": mixed.marker_counts(cdb) | {"7447": cdb.count(b"7447")},
        "object_chunk_size": len(chunk),
        "static_validation_issues": static_issues(output, case, row_plan),
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(seq.bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 9, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    discovery = {}
    for donor in mixed.DONORS:
        chunk = seq._extract_object_chunk(seq.read_internal_file(donor.path, "ROOT.DSN"))
        discovery[donor.key] = [region.as_dict() for region in discover_regions(chunk)]
    (OUT_ROOT / "region_discovery.json").write_text(json.dumps(discovery, indent=2) + "\n", encoding="utf-8")

    manifests = [write_case(case) for case in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_CROSS_DONOR_V1_TEMP_2026_06_09",
        "purpose": "Test cross-donor whole-IC-region combinations that were not manually supplied together.",
        "status": "temporary_pending_user_proteus_testing",
        "composition_policy": "whole balanced IC regions only; unique existing U refs; union CDB rows; concatenated donor device sections",
        "terminal_policy": "all retained visible endpoints use relabeled $TERBIDIR records",
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "region_discovery": "region_discovery.json",
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
