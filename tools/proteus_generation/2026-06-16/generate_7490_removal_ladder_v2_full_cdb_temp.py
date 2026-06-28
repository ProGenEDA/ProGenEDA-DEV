"""Generate 7490 deletion ladder V2 with full donor ROOT.CDB preserved.

V1 pruned ROOT.CDB to match kept packages and Proteus crashed for every
deletion case. The diagnostic pack showed the failing cases were exactly the
pruned-CDB cases (D03, D05, D08, D14, D16, D18), while the full-CDB variants
opened. This V2 keeps the donor ROOT.CDB whole and mutates only ROOT.DSN object
data by deleting complete 7490 packets.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.component_placer import parse_component_placer_cdb
from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


DONOR = ROOT / "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal/7490/6_7490_withallcombunationaland21RLC.pdsprj"
SOLO = ROOT / "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal/7490/7490.pdsprj"
TWO = ROOT / "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal/7490/2_7490.pdsprj"
FOUR = ROOT / "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal/7490/4_7490.pdsprj"
OUT_DIR = ROOT / "experiments/ic_7490_removal_ladder_v2_full_cdb_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/IC_7490_REMOVAL_LADDER_V2_FULL_CDB_TEMP_2026_06_16.zip"

TERMINAL_MARKER = b"$TERBIDIR"
WIRE_MARKER = b"WIRE"
FAMILY_MARKER = b"7490"
FORBIDDEN_MARKERS = (
    b"74HC00",
    b"74HC02",
    b"74HC08",
    b"74HC32",
    b"74HC86",
    b"74HC266",
    b"RESISTOR",
    b"REALIND",
    b"CAP",
)


@dataclass(frozen=True)
class Packet:
    package: str
    dsn_hint: str
    start: int
    end: int
    sha256: str

    def as_dict(self) -> dict[str, object]:
        return {
            "package": self.package,
            "dsn_hint": self.dsn_hint,
            "raw_start": self.start,
            "raw_end": self.end,
            "raw_size": self.end - self.start,
            "sha256": self.sha256,
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def terminal_clusters(chunk: bytes) -> list[list[int]]:
    starts: list[int] = []
    pos = 0
    while True:
        marker = chunk.find(TERMINAL_MARKER, pos)
        if marker < 0:
            break
        starts.append(marker - 14)
        pos = marker + 1

    clusters: list[list[int]] = []
    current: list[int] = []
    for start in starts:
        if not current or start - current[-1] < 300:
            current.append(start)
        else:
            clusters.append(current)
            current = [start]
    if current:
        clusters.append(current)
    return clusters


def detect_7490_packets(chunk: bytes) -> list[Packet]:
    packets: list[Packet] = []
    package_refs = ["U1", "U2", "U9", "U10", "U11", "U12"]
    for cluster in terminal_clusters(chunk):
        if len(cluster) != 10:
            continue
        start = cluster[0]
        window_end = min(len(chunk), start + 2400)
        window = chunk[start:window_end]
        if FAMILY_MARKER not in window or window.count(TERMINAL_MARKER) < 10:
            continue
        wire_positions: list[int] = []
        pos = start
        while True:
            marker = chunk.find(WIRE_MARKER, pos, window_end)
            if marker < 0:
                break
            wire_positions.append(marker)
            pos = marker + 1
        if len(wire_positions) < 10:
            raise ValueError(f"7490 packet at {start} has only {len(wire_positions)} WIRE records.")
        end = wire_positions[9] + 25
        raw = chunk[start:end]
        if raw.count(TERMINAL_MARKER) != 10 or raw.count(WIRE_MARKER) != 10 or raw.count(FAMILY_MARKER) != 3:
            raise ValueError(f"7490 packet at {start} does not match the solo packet marker pattern.")
        dsn_hint = "unknown"
        for candidate in (b"U100", b"U90", b"U12", b"U11", b"U2", b"U1"):
            if candidate in raw:
                dsn_hint = candidate.decode("ascii")
                break
        if len(packets) >= len(package_refs):
            raise ValueError("Detected more 7490 packets than expected from this donor.")
        packets.append(Packet(package_refs[len(packets)], dsn_hint, start, end, sha256_bytes(raw)))
    if len(packets) != 6:
        raise ValueError(f"Expected six 7490 packets in host donor, found {len(packets)}.")
    return packets


def build_chunk(chunk: bytes, packets: list[Packet], keep_count: int) -> tuple[bytes, list[Packet]]:
    kept = packets[:keep_count]
    return b"\x00" + b"".join(chunk[p.start : p.end] for p in kept) + b"\xff", kept


def copy_control(source: Path, case_id: str, title: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(source, output)
    return summarize_project(output, case_id, title, "exact_donor_copy", [])


def summarize_project(
    output: Path,
    case_id: str,
    title: str,
    case_type: str,
    kept: list[Packet],
    dsn_pointer_update: dict[str, int] | None = None,
) -> dict[str, object]:
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    parsed = parse_component_placer_cdb(cdb)
    forbidden = {marker.decode("ascii", "ignore"): chunk.count(marker) for marker in FORBIDDEN_MARKERS if chunk.count(marker)}
    summary = {
        "case_id": case_id,
        "title": title,
        "type": case_type,
        "project": str(output.relative_to(OUT_DIR)),
        "kept_packages": [packet.package for packet in kept],
        "kept_dsn_hints": [packet.dsn_hint for packet in kept],
        "cdb_policy": "full donor ROOT.CDB preserved; orphan rows are intentional because pruning crashed Proteus",
        "cdb_pin_package_refs": list(parsed.pin_package_refs()),
        "cdb_property_package_refs": list(parsed.property_package_refs()),
        "marker_counts": {
            "$TERBIDIR": chunk.count(TERMINAL_MARKER),
            "WIRE": chunk.count(WIRE_MARKER),
            "7490": chunk.count(FAMILY_MARKER),
            "forbidden_non_7490_object_markers": forbidden,
        },
        "hashes": {
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(dsn),
            "ROOT.CDB": sha256_bytes(cdb),
            "object_chunk": sha256_bytes(chunk),
        },
    }
    if dsn_pointer_update:
        summary["dsn_pointer_update"] = dsn_pointer_update
    return summary


def write_case(
    donor_dsn: bytes,
    donor_cdb: bytes,
    original_chunk: bytes,
    packets: list[Packet],
    keep_count: int,
    case_id: str,
) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    new_chunk, kept = build_chunk(original_chunk, packets, keep_count)
    new_dsn, pointers = build_dsn(donor_dsn, donor_dsn, new_chunk)
    write_project_from_parts(DONOR, output, {"ROOT.DSN": new_dsn, "ROOT.CDB": donor_cdb}, compression=ZIP_DEFLATED)
    summary = summarize_project(
        output,
        case_id,
        f"7490-only deletion ladder with {keep_count} package(s), full host CDB",
        "donor_native_deletion_only_full_cdb",
        kept,
        pointers,
    )
    expected = keep_count
    errors: list[str] = []
    markers = summary["marker_counts"]
    if markers["$TERBIDIR"] != expected * 10:
        errors.append("unexpected bidirectional terminal count")
    if markers["WIRE"] != expected * 10:
        errors.append("unexpected wire count")
    if markers["7490"] != expected * 3:
        errors.append("unexpected 7490 marker count")
    if markers["forbidden_non_7490_object_markers"]:
        errors.append("non-7490 object markers remain in ROOT.DSN object stream")
    summary["valid_static"] = not errors
    summary["errors"] = errors
    (case_dir / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    original_chunk = _extract_object_chunk(donor_dsn)
    rebuilt_dsn, _ = build_dsn(donor_dsn, donor_dsn, original_chunk)
    if rebuilt_dsn != donor_dsn:
        raise ValueError("Host donor DSN is not byte-stable under build_dsn(donor, donor, original_chunk).")
    packets = detect_7490_packets(original_chunk)

    controls = [
        copy_control(SOLO, "C00_7490_SOLO_EXACT_DONOR_COPY", "Exact 1x 7490 donor control"),
        copy_control(TWO, "C01_7490_2X_EXACT_DONOR_COPY", "Exact 2x 7490 donor control"),
        copy_control(FOUR, "C02_7490_4X_EXACT_DONOR_COPY", "Exact 4x 7490 donor control"),
        copy_control(DONOR, "C03_7490_6X_MIXED_HOST_EXACT_DONOR_COPY", "Exact 6x mixed host donor control"),
    ]
    cases = [
        write_case(donor_dsn, donor_cdb, original_chunk, packets, keep, f"T{6-keep:02d}_7490_ONLY_{keep}X_FULL_CDB")
        for keep in range(6, -1, -1)
    ]
    manifest = {
        "experiment": "ic_7490_removal_ladder_v2_full_cdb_temp_2026_06_16",
        "status": "static generated; awaiting user Proteus confirmation",
        "prior_evidence": "Diagnostic failures 3,5,8,14,16,18 were all CDB-pruned cases; full-CDB counterparts were not reported failed.",
        "strategy": "delete complete 7490 packets from ROOT.DSN only; preserve full host ROOT.CDB",
        "host_donor": str(DONOR.relative_to(ROOT)),
        "detected_packets": [packet.as_dict() for packet in packets],
        "controls": controls,
        "cases": cases,
        "all_static_valid": all(case.get("valid_static", True) for case in cases),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "7490 V2 full-CDB deletion ladder. Test C00-C03 as controls, then T00-T06.\n"
        "Unlike V1, every T case preserves the full host ROOT.CDB because pruning was the failing operation.\n",
        encoding="utf-8",
    )
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    shutil.make_archive(str(ZIP_OUT.with_suffix("")), "zip", OUT_DIR)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "all_static_valid": manifest["all_static_valid"]}, indent=2))


if __name__ == "__main__":
    main()
