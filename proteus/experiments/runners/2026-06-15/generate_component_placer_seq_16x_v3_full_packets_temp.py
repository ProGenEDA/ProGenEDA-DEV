"""Generate component-placer probes using complete donor-native packets.

V2 proved that CDB pruning alone is not enough: native IC packets cannot be
made by stripping every terminal/wire record from a donor span. This V3 keeps
the complete packet boundary observed in Proteus-created IC donors:

    object stream = 00 + [terminal block + component body + wires ...] + FF

The package packet starts at the terminal block immediately before the first
component body for that package, and ends immediately before the next package's
terminal block. CDB rows are still pruned to the selected packages.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
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

from proteusgen.component_placer import (  # noqa: E402
    build_component_placer_cdb_subset,
    parse_component_placer_cdb,
    validate_project_placement,
)
from proteusgen.ic_native import build_dsn_with_device_section, device_section, marker_counts  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

V1_SCRIPT = Path(__file__).with_name("generate_component_placer_seq_16x_v1_temp.py")
DONOR = REPO / "proteus_ic" / "donors" / "manual_downloads_20260615" / "component_placer" / "16x_seq_combo_mega_donor.pdsprj"
OUT_ROOT = REPO / "experiments" / "component_placer_seq_16x_v3_full_packets_temp_2026_06_15"
ARCHIVE = REPO / "experiments" / "COMPONENT_PLACER_SEQ_16X_V3_FULL_PACKETS_TEMP_2026_06_15.zip"

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
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")


def _load_v1():
    spec = importlib.util.spec_from_file_location("component_placer_seq_16x_v1_temp", V1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {V1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_v1()


@dataclass(frozen=True)
class FullPacket:
    package: str
    family: str
    refs: tuple[str, ...]
    packet_start: int
    packet_end: int
    data: bytes


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    description: str
    families: tuple[str, ...]
    selected: tuple[FullPacket, ...]


def _safe(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")[:110] or "case"


def _package_ref(ref: str) -> str:
    return ref.split(":", 1)[0]


def _component_starts(chunk: bytes) -> list[tuple[int, str]]:
    return [
        (match.start(), match.group(2).decode("ascii"))
        for match in re.finditer(rb"\xff([\x02-\x08])(U\d+(?::[A-F])?)", chunk)
    ]


def _family_for_record(data: bytes) -> str | None:
    hits = [family for family in FAMILY_MARKERS if family.encode("ascii") in data]
    return hits[0] if hits else None


def _terminal_record_starts(chunk: bytes) -> list[int]:
    starts: set[int] = set()
    for marker in TERM_MARKERS:
        pos = 0
        while True:
            found = chunk.find(marker, pos)
            if found < 0:
                break
            starts.add(max(0, found - 14))
            pos = found + 1
    return sorted(starts)


def _terminal_block_start_before(term_starts: list[int], component_start: int) -> int | None:
    candidates = [start for start in term_starts if start < component_start]
    if not candidates:
        return None
    index = len(candidates) - 1
    while index > 0 and candidates[index] - candidates[index - 1] <= 180:
        index -= 1
    return candidates[index]


def analyze_full_packets(chunk: bytes) -> dict[str, list[FullPacket]]:
    starts = _component_starts(chunk)
    term_starts = _terminal_record_starts(chunk)
    component_rows: list[dict[str, object]] = []
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
        raw = chunk[start:end]
        family = _family_for_record(raw)
        if family is None:
            continue
        component_rows.append({"start": start, "ref": ref, "package": _package_ref(ref), "family": family})

    by_package: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in component_rows:
        by_package[str(row["package"])].append(row)

    packet_meta: list[tuple[str, str, tuple[str, ...], int, int]] = []
    for package, rows in by_package.items():
        families = Counter(str(row["family"]) for row in rows)
        if len(families) != 1:
            continue
        family = next(iter(families))
        if family not in SEQUENTIAL_FAMILIES:
            continue
        first_component_start = min(int(row["start"]) for row in rows)
        packet_start = _terminal_block_start_before(term_starts, first_component_start)
        if packet_start is None:
            packet_start = first_component_start
        refs = tuple(str(row["ref"]) for row in sorted(rows, key=lambda item: int(item["start"])))
        packet_meta.append((package, family, refs, packet_start, first_component_start))

    packet_meta.sort(key=lambda item: item[3])
    packets: dict[str, list[FullPacket]] = defaultdict(list)
    for index, (package, family, refs, packet_start, _first_component_start) in enumerate(packet_meta):
        packet_end = packet_meta[index + 1][3] if index + 1 < len(packet_meta) else len(chunk) - 1
        data = chunk[packet_start:packet_end]
        packets[family].append(
            FullPacket(
                package=package,
                family=family,
                refs=refs,
                packet_start=packet_start,
                packet_end=packet_end,
                data=data,
            )
        )

    for family in packets:
        packets[family].sort(key=lambda packet: int(packet.package[1:]))
    return dict(packets)


def _same_family_cases(packets: dict[str, list[FullPacket]]) -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    for family in SEQUENTIAL_FAMILIES:
        available = packets.get(family, [])
        for count in SAME_FAMILY_COUNTS:
            if len(available) < count:
                continue
            cases.append(
                CaseSpec(
                    case_id=_safe(f"SAME_{family}_{count:02d}X"),
                    description=f"{count} complete donor-native packet(s) of {family}.",
                    families=(family,),
                    selected=tuple(available[:count]),
                )
            )
    return cases


def _pair_cases(packets: dict[str, list[FullPacket]]) -> list[CaseSpec]:
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


def build_project(case: CaseSpec, donor_dsn: bytes, donor_cdb, output: Path) -> dict[str, object]:
    object_records = b"".join(packet.data for packet in case.selected)
    object_chunk = b"\x00" + object_records + b"\xff"
    keep_packages = tuple(packet.package for packet in case.selected)
    cdb = build_component_placer_cdb_subset(donor_cdb, keep_packages)
    parsed_subset = parse_component_placer_cdb(cdb)

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
            "ROOT.CDB": cdb,
        },
    )

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_chunk = _extract_object_chunk(final_dsn)
    validation = validate_project_placement(output)
    issues = [issue.as_dict() for issue in validation.errors]
    warnings = [issue.as_dict() for issue in validation.warnings]
    if final_chunk != object_chunk:
        issues.append({"code": "E_OBJECT_CHUNK_MISMATCH", "message": "final object chunk does not match planned chunk", "severity": "error"})

    requested_counts = Counter(packet.family for packet in case.selected)
    return {
        "case_id": case.case_id,
        "description": case.description,
        "families": case.families,
        "selected_packages": [
            {
                "family": packet.family,
                "package": packet.package,
                "refs": list(packet.refs),
                "packet_start": packet.packet_start,
                "packet_end": packet.packet_end,
                "packet_size": len(packet.data),
            }
            for packet in case.selected
        ],
        "package_counts": dict(requested_counts),
        "terminal_policy": "complete donor-native packet output; original linked bider terminals and wires are preserved because stripping them was rejected by V2",
        "metadata_policy": "pruned donor ROOT.CDB: keep only selected package pin/property rows; full donor device section preserved",
        "section_pointers": pointers,
        "object_chunk_size": len(final_chunk),
        "object_stream_header": final_chunk[:8].hex(),
        "marker_counts": marker_counts(final_chunk, FAMILY_MARKERS + ("$TERBIDIR", "$TERINPUT", "$TEROUTPUT", "WIRE")),
        "terminal_counts": {
            "$TERBIDIR": final_chunk.count(b"$TERBIDIR"),
            "$TERINPUT": final_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": final_chunk.count(b"$TEROUTPUT"),
            "WIRE": final_chunk.count(b"WIRE"),
        },
        "cdb_subset": {
            "pin_row_count": len(parsed_subset.pin_rows),
            "property_row_count": len(parsed_subset.property_rows),
            "pin_packages": sorted({row.ref.split(":", 1)[0] for row in parsed_subset.pin_rows}),
            "property_packages": sorted({row.ref.split(":", 1)[0] for row in parsed_subset.property_rows}),
            "property_header_size": parsed_subset.property_header_size,
        },
        "static_validation_issues": issues,
        "static_validation_warnings": warnings,
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(final_dsn),
            "ROOT.CDB": _sha256_bytes(read_internal_file(output, "ROOT.CDB")),
            "object_chunk": _sha256_bytes(final_chunk),
        },
    }


def write_case(case: CaseSpec, donor_dsn: bytes, donor_cdb) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    manifest = build_project(case, donor_dsn, donor_cdb, output)
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "object_chunk.bin").write_bytes(_extract_object_chunk(read_internal_file(output, "ROOT.DSN")))
    (case_dir / "ROOT.CDB.bin").write_bytes(read_internal_file(output, "ROOT.CDB"))
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
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = parse_component_placer_cdb(read_internal_file(DONOR, "ROOT.CDB"))
    donor_chunk = _extract_object_chunk(donor_dsn)
    packets = analyze_full_packets(donor_chunk)
    inventory = {
        family: {
            "package_count": len(items),
            "first_packets": [
                {
                    "package": packet.package,
                    "refs": list(packet.refs),
                    "packet_start": packet.packet_start,
                    "packet_end": packet.packet_end,
                    "packet_size": len(packet.data),
                    "terminal_count": packet.data.count(b"$TER"),
                    "wire_count": packet.data.count(b"WIRE"),
                }
                for packet in items[:5]
            ],
        }
        for family, items in sorted(packets.items())
    }
    (OUT_ROOT / "donor_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    cases = _same_family_cases(packets) + _pair_cases(packets)
    manifests = [write_case(case, donor_dsn, donor_cdb) for case in cases]
    static_issue_cases = {m["case_id"]: m["static_validation_issues"] for m in manifests if m["static_validation_issues"]}
    summary = {
        "batch": "COMPONENT_PLACER_SEQ_16X_V3_FULL_PACKETS_TEMP_2026_06_15",
        "status": "temporary_pending_user_proteus_testing",
        "purpose": "Full donor-native packet component placer probes after V2 body-only stripping failed.",
        "donor": str(DONOR.relative_to(REPO)),
        "target_families": SEQUENTIAL_FAMILIES,
        "same_family_counts": SAME_FAMILY_COUNTS,
        "case_count": len(manifests),
        "same_family_case_count": len([m for m in manifests if len(m["families"]) == 1]),
        "pair_case_count": len([m for m in manifests if len(m["families"]) == 2]),
        "inventory": inventory,
        "static_issue_cases": static_issue_cases,
        "archive": str(ARCHIVE.relative_to(REPO)),
        "donor_cdb": donor_cdb.as_dict(),
        "donor_hashes": {
            "project": _sha256_bytes(DONOR.read_bytes()),
            "ROOT.DSN": _sha256_bytes(donor_dsn),
            "ROOT.CDB": _sha256_bytes(read_internal_file(DONOR, "ROOT.CDB")),
            "object_chunk": _sha256_bytes(donor_chunk),
        },
    }
    (OUT_ROOT / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(OUT_ROOT), "archive": str(ARCHIVE), "archive_sha256": archive_hash, "case_count": len(manifests), "static_issue_cases": static_issue_cases}, indent=2, sort_keys=True))
    return 0 if not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
