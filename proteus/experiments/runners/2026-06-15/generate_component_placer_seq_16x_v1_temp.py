"""Generate sequential/native IC component-placer probes from the 16x mega donor.

This is a temporary experiment for the removal-only component placer plan.
It uses the user-created 16x mega donor as a packet bank, keeps donor CDB and
device metadata whole, and emits selected IC body packets only. External
terminal and wire records are intentionally excluded.
"""

from __future__ import annotations

import json
import re
import shutil
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.ic_native import (  # noqa: E402
    build_dsn_with_device_section,
    device_section,
    marker_counts,
    translate_chunk,
)
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

DONOR = REPO / "proteus_ic" / "donors" / "manual_downloads_20260615" / "component_placer" / "16x_seq_combo_mega_donor.pdsprj"
OUT_ROOT = REPO / "experiments" / "component_placer_seq_16x_v1_temp_2026_06_15"
ARCHIVE = REPO / "experiments" / "COMPONENT_PLACER_SEQ_16X_V1_TEMP_2026_06_15.zip"

SAME_FAMILY_COUNTS = (1, 3, 5, 15, 23)
SEQUENTIAL_FAMILIES = (
    "7490",
    "74HC160",
    "74HC74",
    "74HC76",
    "74HC85",
    "74HC157",
    "74HC174",
    "74HC283",
    "4027",
    "7447",
)
FAMILY_MARKERS = tuple(sorted(SEQUENTIAL_FAMILIES, key=len, reverse=True))
FORBIDDEN_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND", b"WIRE")

GRID_X0 = -55_880_000
GRID_Y0 = 30_480_000
GRID_X_STEP = 7_620_000
GRID_Y_STEP = -7_620_000
GRID_COLUMNS = 8


@dataclass(frozen=True)
class BodyRecord:
    ref: str
    package: str
    family: str
    raw_start: int
    raw_end: int
    clean_size: int
    data: bytes


@dataclass(frozen=True)
class PackagePacket:
    package: str
    family: str
    records: tuple[BodyRecord, ...]


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    description: str
    families: tuple[str, ...]
    selected: tuple[PackagePacket, ...]


def _safe(text: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")
    return safe[:110] or "case"


def _record_starts(chunk: bytes) -> list[tuple[int, str]]:
    return [
        (match.start(), match.group(2).decode("ascii"))
        for match in re.finditer(rb"\xff([\x02-\x08])(U\d+(?::[A-F])?)", chunk)
    ]


def _package_ref(ref: str) -> str:
    return ref.split(":", 1)[0]


def _family_for_record(data: bytes) -> str | None:
    hits = [family for family in FAMILY_MARKERS if family.encode("ascii") in data]
    return hits[0] if hits else None


def _wire_record_start(data: bytes) -> int | None:
    marker = data.find(b"WIRE")
    if marker < 0:
        return None
    # Observed wire records use two header bytes before ASCII "WIRE".
    return max(0, marker - 2)


def _terminal_record_start(data: bytes) -> int | None:
    starts: list[int] = []
    for marker in (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND"):
        pos = data.find(marker)
        if pos >= 0:
            starts.append(max(0, pos - 14))
    return min(starts) if starts else None


def _clean_record(raw: bytes) -> bytes:
    cuts = [len(raw)]
    wire_start = _wire_record_start(raw)
    terminal_start = _terminal_record_start(raw)
    if wire_start is not None:
        cuts.append(wire_start)
    if terminal_start is not None:
        cuts.append(terminal_start)
    clean = raw[: min(cuts)]
    for marker in FORBIDDEN_MARKERS:
        if marker in clean:
            raise RuntimeError(f"trimmed record still contains forbidden marker {marker!r}")
    if not clean.startswith(b"\xff"):
        raise RuntimeError("trimmed component body does not start with a record marker")
    return clean


def _body_anchor(record: bytes) -> tuple[int, int]:
    ref_len = record[1]
    offset = 2 + ref_len
    if offset + 8 > len(record):
        raise RuntimeError("component body record is too short for anchor coordinates")
    return struct.unpack("<ii", record[offset : offset + 8])


def _place_packet(packet: PackagePacket, index: int) -> tuple[bytes, dict[str, object]]:
    col = index % GRID_COLUMNS
    row = index // GRID_COLUMNS
    target_x = GRID_X0 + col * GRID_X_STEP
    target_y = GRID_Y0 + row * GRID_Y_STEP
    anchor_x, anchor_y = _body_anchor(packet.records[0].data)
    dx = target_x - anchor_x
    dy = target_y - anchor_y
    placed_records: list[bytes] = []
    translate_stats: list[dict[str, object]] = []
    for record in packet.records:
        placed, stats = translate_chunk(record.data, dx, dy)
        placed_records.append(placed)
        translate_stats.append({"ref": record.ref, **stats})
    return b"".join(placed_records), {
        "package": packet.package,
        "family": packet.family,
        "target": {"x": target_x, "y": target_y},
        "delta": {"dx": dx, "dy": dy},
        "refs": [record.ref for record in packet.records],
        "record_sizes": [record.clean_size for record in packet.records],
        "translate_stats": translate_stats,
    }


def analyze_packages(chunk: bytes) -> dict[str, list[PackagePacket]]:
    starts = _record_starts(chunk)
    by_package: dict[str, list[BodyRecord]] = defaultdict(list)
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
        raw = chunk[start:end]
        family = _family_for_record(raw)
        if family is None:
            continue
        clean = _clean_record(raw)
        by_package[_package_ref(ref)].append(
            BodyRecord(
                ref=ref,
                package=_package_ref(ref),
                family=family,
                raw_start=start,
                raw_end=end,
                clean_size=len(clean),
                data=clean,
            )
        )

    packets: dict[str, list[PackagePacket]] = defaultdict(list)
    for package, records in by_package.items():
        family_counts = Counter(record.family for record in records)
        if len(family_counts) != 1:
            raise RuntimeError(f"package {package} mixes families: {dict(family_counts)}")
        family = next(iter(family_counts))
        if family not in SEQUENTIAL_FAMILIES:
            continue
        packets[family].append(PackagePacket(package=package, family=family, records=tuple(records)))

    for family in packets:
        packets[family].sort(key=lambda packet: int(packet.package[1:]))
    return dict(packets)


def _same_family_cases(packets: dict[str, list[PackagePacket]]) -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    for family in SEQUENTIAL_FAMILIES:
        available = packets.get(family, [])
        for count in SAME_FAMILY_COUNTS:
            if len(available) < count:
                continue
            case_id = _safe(f"SAME_{family}_{count:02d}X")
            cases.append(
                CaseSpec(
                    case_id=case_id,
                    description=f"{count} package(s) of {family}, body packets only, no external terminals.",
                    families=(family,),
                    selected=tuple(available[:count]),
                )
            )
    return cases


def _pair_cases(packets: dict[str, list[PackagePacket]]) -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    for left, right in combinations(SEQUENTIAL_FAMILIES, 2):
        left_packets = packets.get(left, [])
        right_packets = packets.get(right, [])
        if len(left_packets) >= 2 and right_packets:
            cases.append(
                CaseSpec(
                    case_id=_safe(f"PAIR3_{left}_2X__{right}_1X"),
                    description=f"Three-package pair mix: 2x {left} plus 1x {right}.",
                    families=(left, right),
                    selected=tuple(left_packets[:2] + right_packets[:1]),
                )
            )
        if left_packets and len(right_packets) >= 2:
            cases.append(
                CaseSpec(
                    case_id=_safe(f"PAIR3_{left}_1X__{right}_2X"),
                    description=f"Three-package pair mix: 1x {left} plus 2x {right}.",
                    families=(left, right),
                    selected=tuple(left_packets[:1] + right_packets[:2]),
                )
            )
    return cases


def build_project(case: CaseSpec, donor_dsn: bytes, donor_cdb: bytes, output: Path) -> dict[str, object]:
    placed: list[bytes] = []
    placements: list[dict[str, object]] = []
    for index, packet in enumerate(case.selected):
        packet_bytes, placement = _place_packet(packet, index)
        placed.append(packet_bytes)
        placements.append(placement)
    object_chunk = b"\x00\x00" + b"".join(placed) + b"\xff"
    for marker in FORBIDDEN_MARKERS:
        if marker in object_chunk:
            raise RuntimeError(f"{case.case_id} object chunk contains forbidden marker {marker!r}")

    fixture = FixtureRegistry.load().get("e001_empty")
    base_dsn = read_internal_file(fixture.path, "ROOT.DSN")
    dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, object_chunk, device_section(donor_dsn))
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    write_project_from_parts(
        fixture.path,
        output,
        {
            "PROJECT.XML": patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": donor_cdb,
        },
    )

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_chunk = _extract_object_chunk(final_dsn)
    issues: list[str] = []
    if final_chunk != object_chunk:
        issues.append("final ROOT.DSN object chunk does not match planned object chunk")
    for marker in FORBIDDEN_MARKERS:
        if marker in final_chunk:
            issues.append(f"forbidden marker remains in final chunk: {marker.decode('ascii', errors='replace')}")
    requested_counts = Counter(packet.family for packet in case.selected)
    actual_counts = {
        family: sum(1 for placement in placements if placement["family"] == family)
        for family in sorted(requested_counts)
    }
    for family, expected in requested_counts.items():
        if actual_counts.get(family) != expected:
            issues.append(f"{family} package count {actual_counts.get(family)} != {expected}")
        if family.encode("ascii") not in final_chunk:
            issues.append(f"marker {family} missing from final chunk")
    return {
        "case_id": case.case_id,
        "description": case.description,
        "families": case.families,
        "selected_packages": [
            {"family": packet.family, "package": packet.package, "refs": [record.ref for record in packet.records]}
            for packet in case.selected
        ],
        "package_counts": dict(requested_counts),
        "terminal_policy": "component placer body-only output; no external terminals or wires emitted",
        "metadata_policy": "copy full 16x donor ROOT.CDB and full 16x donor device section; select and move complete IC body packets only",
        "section_pointers": pointers,
        "placements": placements,
        "object_chunk_size": len(final_chunk),
        "marker_counts": marker_counts(final_chunk, FAMILY_MARKERS),
        "terminal_counts": {
            "$TERBIDIR": final_chunk.count(b"$TERBIDIR"),
            "$TERINPUT": final_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": final_chunk.count(b"$TEROUTPUT"),
            "WIRE": final_chunk.count(b"WIRE"),
        },
        "static_validation_issues": issues,
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(final_dsn),
            "ROOT.CDB": _sha256_bytes(read_internal_file(output, "ROOT.CDB")),
            "object_chunk": _sha256_bytes(final_chunk),
        },
    }


def write_case(case: CaseSpec, donor_dsn: bytes, donor_cdb: bytes) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    manifest = build_project(case, donor_dsn, donor_cdb, output)
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "object_chunk.bin").write_bytes(_extract_object_chunk(read_internal_file(output, "ROOT.DSN")))
    return manifest


def write_archive() -> str:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
            info.date_time = (2026, 6, 15, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE.read_bytes())


def main() -> int:
    if not DONOR.exists():
        raise FileNotFoundError(DONOR)
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)
    packets = analyze_packages(donor_chunk)

    inventory = {
        family: {
            "package_count": len(items),
            "subpart_count_distribution": dict(Counter(len(packet.records) for packet in items)),
            "first_packages": [
                {"package": packet.package, "refs": [record.ref for record in packet.records]}
                for packet in items[:5]
            ],
        }
        for family, items in sorted(packets.items())
    }
    (OUT_ROOT / "donor_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cases = _same_family_cases(packets) + _pair_cases(packets)
    manifests = [write_case(case, donor_dsn, donor_cdb) for case in cases]
    static_issue_cases = {
        manifest["case_id"]: manifest["static_validation_issues"]
        for manifest in manifests
        if manifest["static_validation_issues"]
    }
    summary = {
        "batch": "COMPONENT_PLACER_SEQ_16X_V1_TEMP_2026_06_15",
        "status": "temporary_pending_user_proteus_testing",
        "purpose": "Removal-only component placer probes from the 16x sequential/native mega donor.",
        "donor": str(DONOR.relative_to(REPO)),
        "donor_hashes": {
            "project": _sha256_bytes(DONOR.read_bytes()),
            "ROOT.DSN": _sha256_bytes(donor_dsn),
            "ROOT.CDB": _sha256_bytes(donor_cdb),
            "object_chunk": _sha256_bytes(donor_chunk),
        },
        "target_families": SEQUENTIAL_FAMILIES,
        "same_family_counts": SAME_FAMILY_COUNTS,
        "pair_policy": "all unordered family pairs emitted in both 2x-left+1x-right and 1x-left+2x-right forms",
        "case_count": len(manifests),
        "same_family_case_count": len([m for m in manifests if len(m["families"]) == 1]),
        "pair_case_count": len([m for m in manifests if len(m["families"]) == 2]),
        "inventory": inventory,
        "static_issue_cases": static_issue_cases,
        "archive": str(ARCHIVE.relative_to(REPO)),
    }
    (OUT_ROOT / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE),
                "archive_sha256": archive_hash,
                "case_count": len(manifests),
                "static_issue_cases": static_issue_cases,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
