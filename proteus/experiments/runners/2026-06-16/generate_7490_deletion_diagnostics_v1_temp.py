"""Build focused 7490 deletion diagnostics after the removal ladder crashed.

The goal is not to generate final circuits. It isolates the first operation
that breaks Proteus:

- container repack with unchanged internals
- build_dsn with unchanged object chunk
- CDB pruning with unchanged DSN
- DSN deletion with full CDB
- DSN deletion with pruned/exact CDB
- same-family tail deletion from 4x/2x/1x donors
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
from src.proteusgen.templates import FixtureRegistry


DONOR_DIR = ROOT / "proteus/active/evidence/donors/manual_downloads_20260612/ICcombinationfinal/7490"
HOST6 = DONOR_DIR / "6_7490_withallcombunationaland21RLC.pdsprj"
SOLO1 = DONOR_DIR / "7490.pdsprj"
TWO2 = DONOR_DIR / "2_7490.pdsprj"
FOUR4 = DONOR_DIR / "4_7490.pdsprj"
OUT_DIR = ROOT / "experiments/ic_7490_deletion_diagnostics_v1_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/IC_7490_DELETION_DIAGNOSTICS_V1_TEMP_2026_06_16.zip"

TER = b"$TERBIDIR"
WIRE = b"WIRE"
FAM = b"7490"


@dataclass(frozen=True)
class Packet:
    package: str
    start: int
    end: int


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_dsn(path: Path) -> bytes:
    return read_internal_file(path, "ROOT.DSN")


def read_cdb(path: Path) -> bytes:
    return read_internal_file(path, "ROOT.CDB")


def terminal_clusters(chunk: bytes) -> list[list[int]]:
    starts: list[int] = []
    pos = 0
    while True:
        marker = chunk.find(TER, pos)
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


def detect_7490_packets(project: Path, packages: list[str] | None = None) -> list[Packet]:
    chunk = _extract_object_chunk(read_dsn(project))
    packets: list[Packet] = []
    for cluster in terminal_clusters(chunk):
        if len(cluster) != 10:
            continue
        start = cluster[0]
        search_end = min(len(chunk), start + 2400)
        window = chunk[start:search_end]
        if FAM not in window:
            continue
        wires: list[int] = []
        pos = start
        while True:
            marker = chunk.find(WIRE, pos, search_end)
            if marker < 0:
                break
            wires.append(marker)
            pos = marker + 1
        if len(wires) < 10:
            continue
        end = wires[9] + 25
        raw = chunk[start:end]
        if raw.count(TER) == 10 and raw.count(WIRE) == 10 and raw.count(FAM) == 3:
            packets.append(Packet("", start, end))
    if packages is None:
        packages = [f"U{i}" for i in range(1, len(packets) + 1)]
    if len(packages) != len(packets):
        raise ValueError(f"Package map length {len(packages)} does not match packet count {len(packets)} for {project}.")
    return [Packet(package, packet.start, packet.end) for package, packet in zip(packages, packets)]


def chunk_from(project: Path, keep_count: int, packages: list[str] | None = None) -> tuple[bytes, list[str]]:
    dsn = read_dsn(project)
    chunk = _extract_object_chunk(dsn)
    packets = detect_7490_packets(project, packages)
    kept = packets[:keep_count]
    return b"\x00" + b"".join(chunk[p.start : p.end] for p in kept) + b"\xff", [p.package for p in kept]


def cdb_subset(source_project: Path, packages: list[str]) -> bytes:
    parsed = parse_component_placer_cdb(read_cdb(source_project))
    return build_component_placer_cdb_subset(parsed, packages)


def write_case(case_id: str, template: Path, replacements: dict[str, bytes], note: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(template, output, replacements, compression=ZIP_DEFLATED)
    dsn = read_dsn(output)
    cdb = read_cdb(output)
    chunk = _extract_object_chunk(dsn)
    summary = {
        "case_id": case_id,
        "note": note,
        "template": str(template.relative_to(ROOT)),
        "project": str(output.relative_to(OUT_DIR)),
        "sizes": {"ROOT.DSN": len(dsn), "ROOT.CDB": len(cdb), "object_chunk": len(chunk)},
        "marker_counts": {"$TERBIDIR": chunk.count(TER), "WIRE": chunk.count(WIRE), "7490": chunk.count(FAM)},
        "hashes": {"ROOT.DSN": sha256_bytes(dsn), "ROOT.CDB": sha256_bytes(cdb), "object_chunk": sha256_bytes(chunk)},
    }
    try:
        parsed = parse_component_placer_cdb(cdb)
        summary["cdb_refs"] = {
            "pin": list(parsed.pin_package_refs()),
            "property": list(parsed.property_package_refs()),
        }
    except Exception as exc:
        summary["cdb_parse_error"] = f"{type(exc).__name__}: {exc}"
    (case_dir / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def copy_case(case_id: str, source: Path, note: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(source, output)
    return write_summary_only(case_id, output, note, "exact_copy")


def write_summary_only(case_id: str, output: Path, note: str, kind: str) -> dict[str, object]:
    dsn = read_dsn(output)
    cdb = read_cdb(output)
    chunk = _extract_object_chunk(dsn)
    summary = {
        "case_id": case_id,
        "kind": kind,
        "note": note,
        "project": str(output.relative_to(OUT_DIR)),
        "sizes": {"ROOT.DSN": len(dsn), "ROOT.CDB": len(cdb), "object_chunk": len(chunk)},
        "marker_counts": {"$TERBIDIR": chunk.count(TER), "WIRE": chunk.count(WIRE), "7490": chunk.count(FAM)},
        "hashes": {"ROOT.DSN": sha256_bytes(dsn), "ROOT.CDB": sha256_bytes(cdb), "object_chunk": sha256_bytes(chunk)},
    }
    (output.parent / "manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    host_dsn = read_dsn(HOST6)
    host_cdb = read_cdb(HOST6)
    host_chunk = _extract_object_chunk(host_dsn)
    host_rebuilt_dsn, _ = build_dsn(host_dsn, host_dsn, host_chunk)
    if host_rebuilt_dsn != host_dsn:
        raise ValueError("Host6 original build_dsn roundtrip is not byte identical.")

    exact2_chunk, exact2_refs = chunk_from(TWO2, 2)
    host_first2_chunk, host_first2_refs = chunk_from(HOST6, 2, ["U1", "U2", "U9", "U10", "U11", "U12"])
    host_six_chunk, host_six_refs = chunk_from(HOST6, 6, ["U1", "U2", "U9", "U10", "U11", "U12"])
    four3_chunk, four3_refs = chunk_from(FOUR4, 3)
    two1_chunk, two1_refs = chunk_from(TWO2, 1)
    solo0_chunk, solo0_refs = chunk_from(SOLO1, 0)

    fixture = FixtureRegistry.load().get("e001_empty").path

    cases: list[dict[str, object]] = []
    cases.append(copy_case("D00_HOST6_EXACT_COPY", HOST6, "Baseline: exact mixed 6x host donor copy."))
    cases.append(write_case("D01_HOST6_REPACK_UNCHANGED", HOST6, {}, "Repack host container with unchanged internal files."))
    cases.append(write_case("D02_HOST6_BUILDDN_ORIGINAL_CHUNK", HOST6, {"ROOT.DSN": host_rebuilt_dsn, "ROOT.CDB": host_cdb}, "Rebuild host ROOT.DSN with original object chunk and original CDB."))
    cases.append(write_case("D03_HOST6_ORIGINAL_DSN_PRUNED_CDB_U1_U2", HOST6, {"ROOT.CDB": cdb_subset(HOST6, ["U1", "U2"])}, "CDB-only pruning while original full mixed DSN remains."))

    dsn_host_first2, _ = build_dsn(host_dsn, host_dsn, host_first2_chunk)
    dsn_host_six, _ = build_dsn(host_dsn, host_dsn, host_six_chunk)
    dsn_host_exact2, _ = build_dsn(host_dsn, host_dsn, exact2_chunk)
    cases.append(write_case("D04_HOST_FIRST2_DSN_FULL_HOST_CDB", HOST6, {"ROOT.DSN": dsn_host_first2, "ROOT.CDB": host_cdb}, "Delete DSN to first two 7490 packets but keep full host CDB."))
    cases.append(write_case("D05_HOST_FIRST2_DSN_PRUNED_HOST_CDB", HOST6, {"ROOT.DSN": dsn_host_first2, "ROOT.CDB": cdb_subset(HOST6, host_first2_refs)}, "Delete DSN to first two 7490 packets and prune host CDB to U1/U2."))
    cases.append(write_case("D06_HOST_FIRST2_DSN_EXACT2_CDB", HOST6, {"ROOT.DSN": dsn_host_first2, "ROOT.CDB": read_cdb(TWO2)}, "Host first-two object packets with exact 2x donor CDB."))
    cases.append(write_case("D07_HOST_SIX_DSN_FULL_HOST_CDB", HOST6, {"ROOT.DSN": dsn_host_six, "ROOT.CDB": host_cdb}, "Keep all six 7490 packets from host, remove every non-7490 object, but keep full host CDB."))
    cases.append(write_case("D08_HOST_SIX_DSN_PRUNED_HOST_CDB", HOST6, {"ROOT.DSN": dsn_host_six, "ROOT.CDB": cdb_subset(HOST6, host_six_refs)}, "Keep all six 7490 packets from host and prune host CDB to the six 7490 refs."))
    cases.append(write_case("D09_HOST_DEVICE_WITH_EXACT2_CHUNK_EXACT2_CDB", HOST6, {"ROOT.DSN": dsn_host_exact2, "ROOT.CDB": read_cdb(TWO2)}, "Host device section with exact 2x object chunk and exact 2x CDB."))

    two_dsn = read_dsn(TWO2)
    exact2_in_two_dsn, _ = build_dsn(two_dsn, two_dsn, exact2_chunk)
    host_first2_in_two_dsn, _ = build_dsn(two_dsn, two_dsn, host_first2_chunk)
    cases.append(write_case("D10_EXACT2_REPACK_UNCHANGED", TWO2, {}, "Repack exact 2x donor unchanged."))
    cases.append(write_case("D11_EXACT2_BUILDDN_ORIGINAL_CHUNK", TWO2, {"ROOT.DSN": exact2_in_two_dsn, "ROOT.CDB": read_cdb(TWO2)}, "Rebuild exact 2x donor with original object chunk."))
    cases.append(write_case("D12_TWO_DEVICE_WITH_HOST_FIRST2_CHUNK_EXACT2_CDB", TWO2, {"ROOT.DSN": host_first2_in_two_dsn, "ROOT.CDB": read_cdb(TWO2)}, "Exact 2x donor device section with host first-two object packets and exact 2x CDB."))

    four_dsn = read_dsn(FOUR4)
    four3_dsn, _ = build_dsn(four_dsn, four_dsn, four3_chunk)
    cases.append(write_case("D13_4X_DELETE_TAIL_TO_3X_FULL_CDB", FOUR4, {"ROOT.DSN": four3_dsn, "ROOT.CDB": read_cdb(FOUR4)}, "Same-family 4x donor tail-delete to 3x, full 4x CDB."))
    cases.append(write_case("D14_4X_DELETE_TAIL_TO_3X_PRUNED_CDB", FOUR4, {"ROOT.DSN": four3_dsn, "ROOT.CDB": cdb_subset(FOUR4, four3_refs)}, "Same-family 4x donor tail-delete to 3x, pruned CDB."))

    two1_dsn, _ = build_dsn(two_dsn, two_dsn, two1_chunk)
    cases.append(write_case("D15_2X_DELETE_TAIL_TO_1X_FULL_CDB", TWO2, {"ROOT.DSN": two1_dsn, "ROOT.CDB": read_cdb(TWO2)}, "Same-family 2x donor tail-delete to 1x, full 2x CDB."))
    cases.append(write_case("D16_2X_DELETE_TAIL_TO_1X_PRUNED_CDB", TWO2, {"ROOT.DSN": two1_dsn, "ROOT.CDB": cdb_subset(TWO2, two1_refs)}, "Same-family 2x donor tail-delete to 1x, pruned CDB."))

    solo_dsn = read_dsn(SOLO1)
    solo0_dsn, _ = build_dsn(solo_dsn, solo_dsn, solo0_chunk)
    cases.append(write_case("D17_1X_DELETE_TO_0X_FULL_CDB", SOLO1, {"ROOT.DSN": solo0_dsn, "ROOT.CDB": read_cdb(SOLO1)}, "Same-family 1x donor delete to empty object stream, full 1x CDB."))
    try:
        zero_cdb = cdb_subset(SOLO1, solo0_refs)
    except Exception:
        zero_cdb = cdb_subset(HOST6, [])
    cases.append(write_case("D18_1X_DELETE_TO_0X_ZERO_CDB", SOLO1, {"ROOT.DSN": solo0_dsn, "ROOT.CDB": zero_cdb}, "Same-family 1x donor delete to empty object stream and zero-row CDB."))
    cases.append(copy_case("D19_E001_EMPTY_EXACT_COPY", fixture, "Exact E001 empty project control."))

    manifest = {
        "experiment": "ic_7490_deletion_diagnostics_v1_temp_2026_06_16",
        "status": "static generated; awaiting user Proteus testing",
        "prior_result": "IC_7490_REMOVAL_LADDER_V1: controls opened; all T deletion cases crashed",
        "host_donor": str(HOST6.relative_to(ROOT)),
        "case_count": len(cases),
        "cases": cases,
        "test_order": [
            "D00-D02 first: if these fail, container repack/build_dsn is unsafe.",
            "D03-D09: isolate host CDB pruning vs host DSN deletion vs host device section.",
            "D10-D12: compare exact 2x donor repack/build against host-first2 packets.",
            "D13-D18: test same-family tail deletion from 4x/2x/1x donors.",
            "D19: empty-sheet control.",
        ],
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "7490 deletion diagnostic pack. Test D00-D02 first, then stop at first crash pattern if needed.\n"
        "This pack is intentionally diagnostic, not a final generator output.\n",
        encoding="utf-8",
    )
    if ZIP_OUT.exists():
        ZIP_OUT.unlink()
    shutil.make_archive(str(ZIP_OUT.with_suffix("")), "zip", OUT_DIR)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "case_count": len(cases)}, indent=2))


if __name__ == "__main__":
    main()
