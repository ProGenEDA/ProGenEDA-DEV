"""Generate V3 no-terminal bare-placement tests around the R/C/L anchor.

V2 user results showed that all working no-terminal bare candidates kept the
full four-row R/C/L support set from `4_alot_of_ics.pdsprj`, while failed
candidates removed R/C/L entirely or kept only two rows. This pack tests that
rule directly.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.component_placer import parse_component_placer_cdb
from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


OUT_DIR = ROOT / "experiments/bare_visibility_rlc_anchor_v3_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_VISIBILITY_RLC_ANCHOR_V3_TEMP_2026_06_16.zip"
DONOR = ROOT / "proteus_ic/donors/mixed_large_20260611/4_alot_of_ics.pdsprj"

FAMILY_MARKERS = tuple(
    sorted(
        (
            "CAP-ELEC",
            "74HC266",
            "74HC160",
            "74HC161",
            "74HC163",
            "74HC192",
            "74HC193",
            "74HC00",
            "74HC02",
            "74HC04",
            "74HC08",
            "74HC32",
            "74HC86",
            "RESISTOR",
            "REALIND",
            "LM741",
            "7490",
            "CAP",
            "NPN",
            "PNP",
        ),
        key=len,
        reverse=True,
    )
)
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
WIRE_MARKER = b"WIRE"
RECORD_START_RE = re.compile(rb"\xff[\x02-\x08]((?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+)|(?:Q\d+))")


@dataclass(frozen=True)
class BodyGroup:
    key: str
    family: str
    start: int
    refs: tuple[str, ...]
    data: bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def family_for(data: bytes) -> str | None:
    for marker in FAMILY_MARKERS:
        if marker.encode("ascii") in data:
            return marker
    return None


def marker_counts(data: bytes) -> dict[str, int]:
    markers = FAMILY_MARKERS + ("$TERBIDIR", "$TERINPUT", "$TEROUTPUT", "$TERPOWER", "$TERGROUND", "WIRE")
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def package_ref(ref: str) -> str:
    return ref.split(":", 1)[0]


def object_record_starts(chunk: bytes) -> list[tuple[int, str]]:
    rows: list[tuple[int, str]] = []
    for match in RECORD_START_RE.finditer(chunk):
        start = match.start()
        if b"COMPONENT ID" not in chunk[start : start + 180]:
            continue
        rows.append((start, match.group(1).decode("ascii", "ignore")))
    return rows


def groups_from_no_terminal_chunk(chunk: bytes) -> dict[str, list[BodyGroup]]:
    if not chunk.startswith(b"\x00\x00"):
        raise ValueError(f"Expected no-terminal chunk head 00 00, got {chunk[:8].hex()}.")
    if any(marker in chunk for marker in TERM_MARKERS) or WIRE_MARKER in chunk:
        raise ValueError("No-terminal donor unexpectedly contains terminals or wires.")
    starts = object_record_starts(chunk)
    by_package: dict[str, list[tuple[str, str, int, bytes]]] = defaultdict(list)
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
        raw = chunk[start:end]
        family = family_for(raw)
        if family is None:
            continue
        by_package[package_ref(ref)].append((ref, family, start, raw))

    by_family: dict[str, list[BodyGroup]] = defaultdict(list)
    for key, rows in by_package.items():
        families = Counter(row[1] for row in rows)
        if len(families) != 1:
            raise ValueError(f"Package {key} matched mixed families: {dict(families)}")
        ordered = sorted(rows, key=lambda row: row[2])
        group = BodyGroup(
            key=key,
            family=ordered[0][1],
            start=ordered[0][2],
            refs=tuple(row[0] for row in ordered),
            data=b"".join(row[3] for row in ordered),
        )
        by_family[group.family].append(group)
    for family in by_family:
        by_family[family].sort(key=lambda item: item.start)
    return dict(by_family)


def select_groups(groups: dict[str, list[BodyGroup]], counts: dict[str, int]) -> tuple[BodyGroup, ...]:
    selected: list[BodyGroup] = []
    for family, count in counts.items():
        available = groups.get(family, [])
        if len(available) < count:
            raise ValueError(f"Need {count} {family} group(s), found {len(available)}.")
        selected.extend(available[:count])
    return tuple(sorted(selected, key=lambda item: item.start))


def chunk_for(groups: tuple[BodyGroup, ...]) -> bytes:
    return b"\x00\x00" + b"".join(group.data for group in sorted(groups, key=lambda item: item.start)) + b"\xff"


def write_case(case_id: str, counts: dict[str, int], description: str, donor_dsn: bytes, donor_cdb: bytes, groups: dict[str, list[BodyGroup]]) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    object_chunk = chunk_for(select_groups(groups, counts))
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(DONOR, output, {"ROOT.DSN": dsn, "ROOT.CDB": donor_cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    final_cdb = read_internal_file(output, "ROOT.CDB")
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs")
    if final_cdb != donor_cdb:
        errors.append("final ROOT.CDB differs")
    if not final_chunk.startswith(b"\x00\x00"):
        errors.append(f"object chunk does not start 00 00: {final_chunk[:8].hex()}")
    if any(marker in final_chunk for marker in TERM_MARKERS):
        errors.append("terminal marker present")
    if WIRE_MARKER in final_chunk:
        errors.append("WIRE marker present")
    try:
        parse_component_placer_cdb(final_cdb)
    except Exception as exc:  # pragma: no cover - summary only
        errors.append(f"CDB parse warning: {exc}")
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "description": f"{description} pointers={pointers}",
        "requested_counts": counts,
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "marker_counts": marker_counts(final_chunk),
        "errors": errors,
    }


def build() -> dict[str, object]:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    groups = groups_from_no_terminal_chunk(_extract_object_chunk(donor_dsn))

    full_rlc = {"RESISTOR": 4, "CAP": 4, "REALIND": 4}
    d15 = {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2, **full_rlc}
    specs: list[tuple[str, dict[str, int], str]] = [
        ("F00_D15_WORKING_CONTROL", d15, "User-confirmed working D15 shape rebuilt as control."),
        ("F01_RLC4_ONLY", full_rlc, "Only the full four-row R/C/L anchor set."),
        ("F02_160_1X_RLC4", {"74HC160": 1, **full_rlc}, "One 74HC160 plus the full R/C/L anchor."),
        ("F03_160_4X_RLC4", {"74HC160": 4, **full_rlc}, "Four 74HC160 plus the full R/C/L anchor."),
        ("F04_160_4X_7490_2X_RLC4", {"74HC160": 4, "7490": 2, **full_rlc}, "E7 working shape rebuilt as control."),
        ("F05_160_2X_161_2X_RLC4", {"74HC160": 2, "74HC161": 2, **full_rlc}, "E9 retry with full four-row R/C/L instead of two rows."),
        ("F06_160_2X_HC08_2X_RLC4", {"74HC160": 2, "74HC08": 2, **full_rlc}, "D12-style retry with full four-row R/C/L."),
        ("F07_160_2X_HC32_2X_RLC4", {"74HC160": 2, "74HC32": 2, **full_rlc}, "74HC160 plus OR gates and full R/C/L anchor."),
        ("F08_160_4X_161_4X_RLC4", {"74HC160": 4, "74HC161": 4, **full_rlc}, "All available 74HC160/74HC161 plus full R/C/L anchor."),
        ("F09_D15_MINUS_RESISTORS", {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2, "CAP": 4, "REALIND": 4}, "D15 support without resistors."),
        ("F10_D15_MINUS_CAPS", {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2, "RESISTOR": 4, "REALIND": 4}, "D15 support without capacitors."),
        ("F11_D15_MINUS_INDUCTORS", {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2, "RESISTOR": 4, "CAP": 4}, "D15 support without inductors."),
        ("F12_D15_RESISTORS_ONLY_SUPPORT", {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2, "RESISTOR": 4}, "D15 digital/analog support plus resistors only."),
        ("F13_D15_CAPS_ONLY_SUPPORT", {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2, "CAP": 4}, "D15 digital/analog support plus capacitors only."),
        ("F14_D15_INDUCTORS_ONLY_SUPPORT", {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2, "REALIND": 4}, "D15 digital/analog support plus inductors only."),
    ]

    cases = [write_case(case_id, counts, description, donor_dsn, donor_cdb, groups) for case_id, counts, description in specs]
    return {
        "experiment": "bare_visibility_rlc_anchor_v3_temp_2026_06_16",
        "purpose": "Test whether the no-terminal component placer requires the full four-row R/C/L support set from the donor.",
        "donor": str(DONOR.relative_to(ROOT)),
        "known_v2_results": {
            "worked": ["E00", "E01", "E02", "E04", "E05", "E07"],
            "failed": ["E03", "E06", "E08", "E09", "E10", "E11", "E12", "E13"],
            "pattern": "All working no-terminal cases kept 4x RESISTOR, 4x CAP groups, and 4x REALIND from the donor; failed cases removed R/C/L or used stripped terminalized records.",
        },
        "cases": cases,
    }


def zip_dir(src: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with ZipFile(output, "w") as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            info = ZipInfo(path.relative_to(src).as_posix())
            info.compress_type = ZIP_DEFLATED
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o600 << 16
            zf.writestr(info, path.read_bytes())


def main() -> None:
    summary = build()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": len(summary["cases"]), "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
