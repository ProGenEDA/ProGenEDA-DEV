"""Generate 16x sequential-IC master-sheet probes with full ROOT.CDB.

The accepted 7490 deletion ladder proved that native IC deletion is stable
when complete DSN packets are selected and the donor ROOT.CDB is preserved
whole. Earlier 16x component-placer attempts pruned CDB rows and failed. This
batch applies the accepted rule to the 16x master donor:

    mutate ROOT.DSN object stream only; preserve donor ROOT.CDB and device data.

Generated cases cover 1/3/5/15/23 packages of each supported family plus all
three-component two-family pair mixes.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.component_placer import parse_component_placer_cdb
from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


DONOR = ROOT / "proteus/active/evidence/donors/manual_downloads_20260615/component_placer/16x_seq_combo_mega_donor.pdsprj"
OUT_DIR = ROOT / "experiments/component_placer_seq_16x_v4_full_master_cdb_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/COMPONENT_PLACER_SEQ_16X_V4_FULL_MASTER_CDB_TEMP_2026_06_16.zip"

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
WIRE_MARKER = b"WIRE"


@dataclass(frozen=True)
class Packet:
    package: str
    family: str
    refs: tuple[str, ...]
    packet_start: int
    packet_end: int
    data: bytes

    def as_dict(self) -> dict[str, object]:
        return {
            "package": self.package,
            "family": self.family,
            "refs": list(self.refs),
            "packet_start": self.packet_start,
            "packet_end": self.packet_end,
            "packet_size": len(self.data),
            "terminal_count": self.data.count(b"$TER"),
            "wire_count": self.data.count(WIRE_MARKER),
            "sha256": sha256_bytes(self.data),
        }


@dataclass(frozen=True)
class CaseSpec:
    case_id: str
    description: str
    families: tuple[str, ...]
    selected: tuple[Packet, ...]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("._")[:120] or "case"


def package_ref(ref: str) -> str:
    return ref.split(":", 1)[0]


def component_starts(chunk: bytes) -> list[tuple[int, str]]:
    return [
        (match.start(), match.group(2).decode("ascii"))
        for match in re.finditer(rb"\xff([\x02-\x08])(U\d+(?::[A-F])?)", chunk)
    ]


def family_for_record(data: bytes) -> str | None:
    hits = [family for family in FAMILY_MARKERS if family.encode("ascii") in data]
    return hits[0] if hits else None


def terminal_record_starts(chunk: bytes) -> list[int]:
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


def terminal_block_start_before(term_starts: list[int], component_start: int) -> int | None:
    candidates = [start for start in term_starts if start < component_start]
    if not candidates:
        return None
    index = len(candidates) - 1
    while index > 0 and candidates[index] - candidates[index - 1] <= 180:
        index -= 1
    return candidates[index]


def analyze_packets(chunk: bytes) -> dict[str, list[Packet]]:
    starts = component_starts(chunk)
    term_starts = terminal_record_starts(chunk)
    component_rows: list[dict[str, object]] = []
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
        family = family_for_record(chunk[start:end])
        if family is None:
            continue
        component_rows.append({"start": start, "ref": ref, "package": package_ref(ref), "family": family})

    by_package: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in component_rows:
        by_package[str(row["package"])].append(row)

    packet_meta: list[tuple[str, str, tuple[str, ...], int]] = []
    for package, rows in by_package.items():
        families = Counter(str(row["family"]) for row in rows)
        if len(families) != 1:
            continue
        family = next(iter(families))
        if family not in SEQUENTIAL_FAMILIES:
            continue
        first_component_start = min(int(row["start"]) for row in rows)
        packet_start = terminal_block_start_before(term_starts, first_component_start)
        if packet_start is None:
            packet_start = first_component_start
        refs = tuple(str(row["ref"]) for row in sorted(rows, key=lambda item: int(item["start"])))
        packet_meta.append((package, family, refs, packet_start))

    packet_meta.sort(key=lambda item: item[3])
    packets: dict[str, list[Packet]] = defaultdict(list)
    for index, (package, family, refs, packet_start) in enumerate(packet_meta):
        packet_end = packet_meta[index + 1][3] if index + 1 < len(packet_meta) else len(chunk) - 1
        data = chunk[packet_start:packet_end]
        packets[family].append(Packet(package, family, refs, packet_start, packet_end, data))

    for family in packets:
        packets[family].sort(key=lambda packet: packet.packet_start)
    return dict(packets)


def same_family_cases(packets: dict[str, list[Packet]]) -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    for family in SEQUENTIAL_FAMILIES:
        available = packets.get(family, [])
        for count in SAME_FAMILY_COUNTS:
            if len(available) < count:
                continue
            selected = tuple(sorted(available[:count], key=lambda packet: packet.packet_start))
            cases.append(
                CaseSpec(
                    safe_name(f"SAME_{family}_{count:02d}X_FULL_CDB"),
                    f"{count} complete donor-native {family} packet(s), full master CDB preserved.",
                    (family,),
                    selected,
                )
            )
    return cases


def pair_cases(packets: dict[str, list[Packet]]) -> list[CaseSpec]:
    cases: list[CaseSpec] = []
    for left, right in combinations(SEQUENTIAL_FAMILIES, 2):
        left_packets = packets.get(left, [])
        right_packets = packets.get(right, [])
        if len(left_packets) >= 2 and right_packets:
            selected = tuple(sorted(left_packets[:2] + right_packets[:1], key=lambda packet: packet.packet_start))
            cases.append(
                CaseSpec(
                    safe_name(f"PAIR3_{left}_2X__{right}_1X_FULL_CDB"),
                    f"Three-package pair mix: 2x {left} plus 1x {right}; full master CDB preserved.",
                    (left, right),
                    selected,
                )
            )
        if left_packets and len(right_packets) >= 2:
            selected = tuple(sorted(left_packets[:1] + right_packets[:2], key=lambda packet: packet.packet_start))
            cases.append(
                CaseSpec(
                    safe_name(f"PAIR3_{left}_1X__{right}_2X_FULL_CDB"),
                    f"Three-package pair mix: 1x {left} plus 2x {right}; full master CDB preserved.",
                    (left, right),
                    selected,
                )
            )
    return cases


def object_chunk_for(case: CaseSpec) -> bytes:
    return b"\x00" + b"".join(packet.data for packet in sorted(case.selected, key=lambda packet: packet.packet_start)) + b"\xff"


def marker_counts(data: bytes) -> dict[str, int]:
    markers = FAMILY_MARKERS + ("$TERBIDIR", "$TERINPUT", "$TEROUTPUT", "$TERPOWER", "$TERGROUND", "WIRE")
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def write_case(case: CaseSpec, donor_dsn: bytes, donor_cdb: bytes) -> dict[str, object]:
    case_dir = OUT_DIR / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    object_chunk = object_chunk_for(case)
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(DONOR, output, {"ROOT.DSN": dsn, "ROOT.CDB": donor_cdb}, compression=ZIP_DEFLATED)

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_cdb = read_internal_file(output, "ROOT.CDB")
    final_chunk = _extract_object_chunk(final_dsn)
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk does not match selected packet stream")
    if final_cdb != donor_cdb:
        errors.append("ROOT.CDB was not preserved byte-for-byte")
    selected_packages = [packet.package for packet in case.selected]
    if len(selected_packages) != len(set(selected_packages)):
        errors.append("duplicate selected package refs")
    expected_term = sum(packet.data.count(b"$TER") for packet in case.selected)
    expected_wire = sum(packet.data.count(WIRE_MARKER) for packet in case.selected)
    if final_chunk.count(b"$TER") != expected_term:
        errors.append("terminal marker count changed")
    if final_chunk.count(WIRE_MARKER) != expected_wire:
        errors.append("wire marker count changed")

    parsed_cdb = parse_component_placer_cdb(final_cdb)
    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "families": list(case.families),
        "selected_packets": [packet.as_dict() for packet in case.selected],
        "selected_package_counts": dict(Counter(packet.family for packet in case.selected)),
        "selection_policy": "complete donor-native packets only, sorted by original master-sheet byte order",
        "cdb_policy": "full master ROOT.CDB preserved byte-for-byte; orphan rows intentionally retained after 7490 diagnostics",
        "cdb_summary": {
            "pin_row_count": len(parsed_cdb.pin_rows),
            "property_row_count": len(parsed_cdb.property_rows),
            "pin_package_ref_count": len(set(parsed_cdb.pin_package_refs())),
            "property_package_ref_count": len(set(parsed_cdb.property_package_refs())),
        },
        "section_pointers": pointers,
        "marker_counts": marker_counts(final_chunk),
        "object_chunk_size": len(final_chunk),
        "valid_static": not errors,
        "errors": errors,
        "hashes": {
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(final_dsn),
            "ROOT.CDB": sha256_bytes(final_cdb),
            "object_chunk": sha256_bytes(final_chunk),
        },
        "project": str(output.relative_to(OUT_DIR)),
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def copy_control() -> dict[str, object]:
    case_id = "C00_16X_MASTER_EXACT_DONOR_COPY"
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(DONOR, output)
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    manifest = {
        "case_id": case_id,
        "description": "Exact 16x master donor copy control.",
        "type": "exact_donor_copy",
        "valid_static": True,
        "hashes": {
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(dsn),
            "ROOT.CDB": sha256_bytes(cdb),
            "object_chunk": sha256_bytes(_extract_object_chunk(dsn)),
        },
        "project": str(output.relative_to(OUT_DIR)),
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    with ZipFile(ZIP_OUT, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_DIR.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_DIR.parent).as_posix())
            info.date_time = (2026, 6, 16, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, file_path.read_bytes())
    return sha256_file(ZIP_OUT)


def main() -> int:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)
    rebuilt_dsn, _ = build_dsn(donor_dsn, donor_dsn, donor_chunk)
    if rebuilt_dsn != donor_dsn:
        raise ValueError("16x master donor DSN is not byte-stable under build_dsn.")

    packets = analyze_packets(donor_chunk)
    inventory = {
        family: {
            "package_count": len(items),
            "first_packets": [packet.as_dict() for packet in items[:5]],
        }
        for family, items in sorted(packets.items())
    }
    missing = [family for family in SEQUENTIAL_FAMILIES if family not in packets]
    if missing:
        raise ValueError(f"Missing families in 16x master donor: {missing}")

    controls = [copy_control()]
    cases = same_family_cases(packets) + pair_cases(packets)
    manifests = [write_case(case, donor_dsn, donor_cdb) for case in cases]
    static_issue_cases = {manifest["case_id"]: manifest["errors"] for manifest in manifests if manifest["errors"]}
    summary = {
        "experiment": "component_placer_seq_16x_v4_full_master_cdb_temp_2026_06_16",
        "status": "static generated; awaiting user Proteus confirmation",
        "strategy": "selected complete DSN packets from 16x master; donor ROOT.CDB and non-object sections preserved",
        "donor": str(DONOR.relative_to(ROOT)),
        "target_families": SEQUENTIAL_FAMILIES,
        "same_family_counts": SAME_FAMILY_COUNTS,
        "case_count": len(manifests),
        "control_count": len(controls),
        "same_family_case_count": len([m for m in manifests if len(m["families"]) == 1]),
        "pair_case_count": len([m for m in manifests if len(m["families"]) == 2]),
        "static_issue_cases": static_issue_cases,
        "inventory": inventory,
        "controls": controls,
        "donor_hashes": {
            "project": sha256_file(DONOR),
            "ROOT.DSN": sha256_bytes(donor_dsn),
            "ROOT.CDB": sha256_bytes(donor_cdb),
            "object_chunk": sha256_bytes(donor_chunk),
        },
    }
    (OUT_DIR / "donor_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "16x master-sheet V4 full-CDB component-placer pack.\n"
        "Test C00 first. Then test SAME_* and PAIR3_* cases.\n"
        "This batch intentionally preserves the full donor ROOT.CDB because CDB pruning was confirmed unsafe in the 7490 diagnostics.\n",
        encoding="utf-8",
    )
    archive_hash = write_archive()
    summary["archive"] = str(ZIP_OUT.relative_to(ROOT))
    summary["archive_sha256"] = archive_hash
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "case_count": len(manifests), "static_issue_cases": static_issue_cases, "archive_sha256": archive_hash}, indent=2, sort_keys=True))
    return 0 if not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
