"""Generate subset-removal probes from accepted real mixed IC/analog donors.

The previous mixed donor pack proved exact repack, E001 transplant, and
topology-preserving label mutation for complete mixed donors. This V1 subset
pack removes complete contiguous object regions discovered from the donor object
stream. It intentionally keeps the donor ROOT.CDB and device section whole so
the first test isolates whether ROOT.DSN object-region removal is safe.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
MIXED_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_analog_batch1_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_analog_subset_v1_temp_2026_06_09"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_ANALOG_SUBSET_V1_TEMP_2026_06_09.zip"


def load_mixed_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_analog_batch1_for_subset_v1", MIXED_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load mixed donor module from {MIXED_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


mixed = load_mixed_module()
seq = mixed.seq


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
class SubsetCase:
    case_id: str
    donor_key: str
    description: str
    keep_markers: tuple[str, ...]
    mutate_labels: bool = False


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


def donor_by_key(key: str):
    return next(donor for donor in mixed.DONORS if donor.key == key)


def build_subset_chunk(original_chunk: bytes, regions: list[Region], keep_markers: tuple[str, ...]) -> tuple[bytes, list[dict[str, object]], list[dict[str, object]]]:
    keep_set = set(keep_markers)
    kept = [region for region in regions if region.marker in keep_set]
    removed = [region for region in regions if region.marker not in keep_set]
    if not kept:
        raise ValueError("Subset case would remove every object region.")
    subset = b"\x00" + b"".join(original_chunk[region.start : region.end] for region in kept) + b"\xff"
    return subset, [region.as_dict() for region in kept], [region.as_dict() for region in removed]


def static_issues(output: Path, keep_markers: tuple[str, ...], removed_markers: tuple[str, ...], mutations: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    info = seq.inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    chunk = seq._extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("subset output should not contain ordinary input/output terminals")
    if chunk.count(b"$TERBIDIR") == 0:
        issues.append("subset output has no bidirectional terminals")
    if chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    for marker in keep_markers:
        if marker.encode("ascii") not in chunk:
            issues.append(f"kept marker {marker} missing from DSN object chunk")
    for marker in removed_markers:
        raw = marker.encode("ascii")
        if marker == "4020":
            # 4020 is a substring of 74HC4020-style names in other contexts; none
            # of these donors uses that exact larger marker, but keep this guard.
            pass
        if raw in chunk:
            issues.append(f"removed marker {marker} still present in DSN object chunk")
    for mutation in mutations:
        if chunk.count(str(mutation["new"]).encode("ascii")) == 0:
            issues.append(f"mutated label {mutation['new']} not present")
    return issues


def write_subset_case(case: SubsetCase) -> dict[str, object]:
    donor = donor_by_key(case.donor_key)
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    donor_dsn = seq.read_internal_file(donor.path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(donor.path, "ROOT.CDB")
    original_chunk = seq._extract_object_chunk(donor_dsn)
    regions = discover_regions(original_chunk)
    subset_chunk, kept_regions, removed_regions = build_subset_chunk(original_chunk, regions, case.keep_markers)
    label_plan: list[dict[str, object]] = []
    mutations: list[dict[str, object]] = []
    if case.mutate_labels:
        replacements, label_plan = mixed.topology_preserving_replacements(subset_chunk)
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
    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "method": "complete_region_subset_removal_with_full_donor_cdb_device_section",
        "status": "temporary_pending_user_proteus_testing",
        "donor_key": donor.key,
        "donor": str(donor.path.relative_to(REPO)),
        "keep_markers": case.keep_markers,
        "removed_markers": removed_markers,
        "terminal_policy": "all retained visible endpoints use donor-native $TERBIDIR records",
        "composition_policy": "remove complete contiguous object regions only; keep donor ROOT.CDB and device section whole",
        "label_mutation": case.mutate_labels,
        "kept_regions": kept_regions,
        "removed_regions": removed_regions,
        "all_regions": [region.as_dict() for region in regions],
        "section_pointers": pointers,
        "label_plan": label_plan,
        "mutations": mutations,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": mixed.marker_counts(chunk),
        "cdb_marker_counts": mixed.marker_counts(cdb),
        "object_chunk_size": len(chunk),
        "static_validation_issues": static_issues(output, case.keep_markers, removed_markers, mutations),
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


CASES = (
    SubsetCase(
        "T01_SEQ_192_193_REMOVE_COUNTERS",
        "seq_192_193",
        "Remove both sequential counter IC regions, leaving the analog/RCL prefix from the mixed donor.",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC"),
    ),
    SubsetCase(
        "T02_SEQ_192_193_KEEP_COUNTER_PAIR_ONLY",
        "seq_192_193",
        "Remove the analog/RCL prefix and keep the balanced 74HC193 plus 74HC192 counter pair.",
        ("74HC193", "74HC192"),
    ),
    SubsetCase(
        "T03_SEQ_192_193_KEEP_ALL_LABELS",
        "seq_192_193",
        "Keep the full 74HC193/74HC192 mixed donor shape but relabel after region reconstruction.",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "74HC193", "74HC192"),
        mutate_labels=True,
    ),
    SubsetCase(
        "T04_DIVIDER_KEEP_4017_4020_ANALOG",
        "seq_4017_4020_4024",
        "Keep analog/RCL plus 4017 and 4020 regions, removing 74HC4024.",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "4017", "4020"),
    ),
    SubsetCase(
        "T05_DIVIDER_KEEP_4017_ONLY",
        "seq_4017_4020_4024",
        "Keep only the balanced 4017 region from the mixed divider donor.",
        ("4017",),
    ),
    SubsetCase(
        "T06_DIVIDER_KEEP_IC_CHAIN_ONLY_LABELS",
        "seq_4017_4020_4024",
        "Remove analog/RCL and keep the 4017/4020/74HC4024 chain with topology-preserving label mutation.",
        ("4017", "4020", "74HC4024"),
        mutate_labels=True,
    ),
    SubsetCase(
        "T07_FIVE_SEQ_REMOVE_192_193",
        "seq_192_193_4017_4020_4024",
        "Remove middle 74HC193/74HC192 regions but keep analog/RCL and the 4017/4020/74HC4024 divider chain.",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "4017", "4020", "74HC4024"),
    ),
    SubsetCase(
        "T08_FIVE_SEQ_KEEP_192_193_ONLY",
        "seq_192_193_4017_4020_4024",
        "Keep only the balanced 74HC193 plus 74HC192 pair from the five-sequential donor.",
        ("74HC193", "74HC192"),
    ),
    SubsetCase(
        "T09_COUNTERS_ALL_KEEP_HC_SYNC_COUNTERS",
        "seq_counters_all",
        "Keep analog/RCL plus 74HC160/161/163 synchronous counter regions from the all-counter donor.",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "74HC160", "74HC161", "74HC163"),
    ),
    SubsetCase(
        "T10_COUNTERS_ALL_KEEP_COUNTERS_ONLY_LABELS",
        "seq_counters_all",
        "Remove analog/RCL regions and keep every counter/divider IC region, with topology-preserving label mutation.",
        ("74HC193", "74HC192", "4017", "4020", "74HC4024", "74HC4520", "4518", "74HC4060", "74HC4040", "7490", "74HC160", "74HC161", "74HC163"),
        mutate_labels=True,
    ),
    SubsetCase(
        "T11_COUNTERS_ALL_KEEP_LOW_COMPLEXITY_COUNTERS",
        "seq_counters_all",
        "Keep 7490, 4518, 74HC4520, and the HC synchronous counters from the all-counter donor.",
        ("7490", "4518", "74HC4520", "74HC160", "74HC161", "74HC163"),
    ),
    SubsetCase(
        "T12_MISC_KEEP_SHIFT_REGISTER_PAIR",
        "misc_logic_analog",
        "Keep analog/RCL plus 74HC595 and 74HC165 regions from the misc logic donor.",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "74HC595", "74HC165"),
    ),
    SubsetCase(
        "T13_MISC_KEEP_157_283_85_ONLY_LABELS",
        "misc_logic_analog",
        "Keep only 74HC157, 74HC283, and 74HC85 regions with topology-preserving label mutation.",
        ("74HC157", "74HC283", "74HC85"),
        mutate_labels=True,
    ),
    SubsetCase(
        "T14_MISC_KEEP_LOGIC_ONLY",
        "misc_logic_analog",
        "Remove analog/RCL and keep every misc logic IC region.",
        ("74HC595", "74HC165", "74HC157", "74HC283", "74HC85"),
    ),
)


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

    manifests = [write_subset_case(case) for case in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_ANALOG_SUBSET_V1_TEMP_2026_06_09",
        "purpose": "Test complete object-region removal from accepted real mixed IC/analog donors.",
        "status": "temporary_pending_user_proteus_testing",
        "composition_policy": "complete contiguous object-region subset removal; full donor CDB/device section preserved",
        "terminal_policy": "all retained visible endpoints use $TERBIDIR",
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
