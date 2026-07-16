"""Generate a deletion-only 7490 removal ladder from a 7490-specific donor.

This is intentionally narrow after the rejected broad mixed-IC component
placer attempts. It uses the 7490-specific donor as the host project, keeps
complete 7490 packets only, prunes ROOT.CDB to matching packages, and does not
rename, translate, clone, or synthesize any IC bytes.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.component_placer import build_component_placer_cdb_subset, parse_component_placer_cdb
from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


DONOR = ROOT / "proteus/active/evidence/donors/manual_downloads_20260612/ICcombinationfinal/7490/6_7490_withallcombunationaland21RLC.pdsprj"
SOLO = ROOT / "proteus/active/evidence/donors/manual_downloads_20260612/ICcombinationfinal/7490/7490.pdsprj"
TWO = ROOT / "proteus/active/evidence/donors/manual_downloads_20260612/ICcombinationfinal/7490/2_7490.pdsprj"
FOUR = ROOT / "proteus/active/evidence/donors/manual_downloads_20260612/ICcombinationfinal/7490/4_7490.pdsprj"
OUT_DIR = ROOT / "experiments/ic_7490_removal_ladder_v1_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/IC_7490_REMOVAL_LADDER_V1_TEMP_2026_06_16.zip"

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
    # The late donor packages are encoded in DSN as U90/U100 hints, while the
    # CDB/package refs are U9/U10. Keep the byte stream unchanged and use the
    # CDB refs Proteus wrote.
    package_refs = ["U1", "U2", "U9", "U10", "U11", "U12"]
    for index, cluster in enumerate(terminal_clusters(chunk)):
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
    if keep_count < 0 or keep_count > len(packets):
        raise ValueError("keep_count outside packet range.")
    kept = packets[:keep_count]
    return b"\x00" + b"".join(chunk[p.start : p.end] for p in kept) + b"\xff", kept


def static_case_summary(project: Path, kept: list[Packet], cdb_packages: list[str]) -> dict[str, object]:
    dsn = read_internal_file(project, "ROOT.DSN")
    cdb = read_internal_file(project, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    expected = len(kept)
    if expected:
        parsed = parse_component_placer_cdb(cdb)
        cdb_pin_refs = list(parsed.pin_package_refs())
        cdb_property_refs = list(parsed.property_package_refs())
    else:
        cdb_count = int.from_bytes(cdb[92:96], "little", signed=False) if len(cdb) >= 96 else -1
        cdb_pin_refs = []
        cdb_property_refs = []
    marker_counts = {
        "$TERBIDIR": chunk.count(TERMINAL_MARKER),
        "WIRE": chunk.count(WIRE_MARKER),
        "7490": chunk.count(FAMILY_MARKER),
        "forbidden": {marker.decode("ascii", "ignore"): chunk.count(marker) for marker in FORBIDDEN_MARKERS if chunk.count(marker)},
    }
    errors: list[str] = []
    if marker_counts["$TERBIDIR"] != expected * 10:
        errors.append("unexpected bidirectional terminal count")
    if marker_counts["WIRE"] != expected * 10:
        errors.append("unexpected wire count")
    if marker_counts["7490"] != expected * 3:
        errors.append("unexpected 7490 marker count")
    if marker_counts["forbidden"]:
        errors.append("non-7490 family markers remain in object stream")
    if not expected and cdb_count != 0:
        errors.append("empty case CDB row count is not zero")
    if tuple(cdb_pin_refs) != tuple(cdb_packages):
        errors.append("CDB pin package refs do not match kept packages")
    if tuple(cdb_property_refs) != tuple(cdb_packages):
        errors.append("CDB property package refs do not match kept packages")
    return {
        "project": str(project.relative_to(OUT_DIR)),
        "valid_static": not errors,
        "errors": errors,
        "kept_packages": [packet.package for packet in kept],
        "kept_dsn_hints": [packet.dsn_hint for packet in kept],
        "cdb_pin_package_refs": cdb_pin_refs,
        "cdb_property_package_refs": cdb_property_refs,
        "marker_counts": marker_counts,
        "hashes": {
            "project": sha256_file(project),
            "ROOT.DSN": sha256_bytes(dsn),
            "ROOT.CDB": sha256_bytes(cdb),
            "object_chunk": sha256_bytes(chunk),
        },
    }


def copy_control(source: Path, case_id: str, title: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(source, output)
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = read_internal_file(output, "ROOT.CDB")
    return {
        "case_id": case_id,
        "title": title,
        "type": "exact_donor_copy",
        "project": str(output.relative_to(OUT_DIR)),
        "marker_counts": {
            "$TERBIDIR": chunk.count(TERMINAL_MARKER),
            "WIRE": chunk.count(WIRE_MARKER),
            "7490": chunk.count(FAMILY_MARKER),
        },
        "hashes": {
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(read_internal_file(output, "ROOT.DSN")),
            "ROOT.CDB": sha256_bytes(cdb),
            "object_chunk": sha256_bytes(chunk),
        },
    }


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
    parsed = parse_component_placer_cdb(donor_cdb)
    keep_packages = [packet.package for packet in kept]
    new_cdb = build_component_placer_cdb_subset(parsed, keep_packages)
    new_dsn, pointers = build_dsn(donor_dsn, donor_dsn, new_chunk)
    write_project_from_parts(DONOR, output, {"ROOT.DSN": new_dsn, "ROOT.CDB": new_cdb}, compression=ZIP_DEFLATED)
    summary = static_case_summary(output, kept, keep_packages)
    summary.update(
        {
            "case_id": case_id,
            "type": "donor_native_deletion_only",
            "host_donor": str(DONOR.relative_to(ROOT)),
            "keep_count": keep_count,
            "dsn_pointer_update": pointers,
            "packet_policy": "concatenate complete donor-native 7490 packets only; no rename, move, clone, or coordinate edit",
        }
    )
    (case_dir / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    original_chunk = _extract_object_chunk(donor_dsn)
    roundtrip_dsn, _ = build_dsn(donor_dsn, donor_dsn, original_chunk)
    if roundtrip_dsn != donor_dsn:
        raise ValueError("Host donor DSN is not byte-stable under build_dsn(donor, donor, original_chunk).")

    packets = detect_7490_packets(original_chunk)
    controls = [
        copy_control(SOLO, "C00_7490_SOLO_EXACT_DONOR_COPY", "Exact 1x 7490 donor control"),
        copy_control(TWO, "C01_7490_2X_EXACT_DONOR_COPY", "Exact 2x 7490 donor control"),
        copy_control(FOUR, "C02_7490_4X_EXACT_DONOR_COPY", "Exact 4x 7490 donor control"),
        copy_control(DONOR, "C03_7490_6X_MIXED_HOST_EXACT_DONOR_COPY", "Exact 6x mixed host donor control"),
    ]
    cases = [
        write_case(donor_dsn, donor_cdb, original_chunk, packets, keep, f"T{6-keep:02d}_7490_ONLY_{keep}X")
        for keep in range(6, -1, -1)
    ]
    manifest = {
        "experiment": "ic_7490_removal_ladder_v1_temp_2026_06_16",
        "status": "static generated; awaiting user Proteus open/simulation confirmation",
        "rejected_prior_path": "component placer V3 full-packet generation from broad 16x mega donor; user reported none worked",
        "strategy": "7490-specific donor-native deletion only",
        "host_donor": str(DONOR.relative_to(ROOT)),
        "detected_packets": [packet.as_dict() for packet in packets],
        "controls": controls,
        "cases": cases,
        "all_static_valid": all(case.get("valid_static", True) for case in cases),
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "Test C00-C03 first as exact donor controls, then T00 down to T06.\n"
        "T00 has six 7490 packets from the 7490-specific mixed donor; each next case removes one complete 7490 packet.\n"
        "T06 is donor-derived empty object data with matching pruned ROOT.CDB.\n"
        "No IC byte mutation, coordinate edit, label edit, or package-ref rewrite is performed.\n",
        encoding="utf-8",
    )

    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    shutil.make_archive(str(ZIP_OUT.with_suffix("")), "zip", OUT_DIR)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "all_static_valid": manifest["all_static_valid"]}, indent=2))


if __name__ == "__main__":
    main()
