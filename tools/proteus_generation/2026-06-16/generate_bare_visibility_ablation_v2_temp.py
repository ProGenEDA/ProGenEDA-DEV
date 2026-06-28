"""Generate V2 no-terminal bare-placement ablations from the working D15 shape.

User testing of BARE_VISIBILITY_DIAGNOSTIC_V1 showed:

- D04 worked: no-terminal donor records can live inside the terminalized master
  container.
- D15 worked: a larger no-terminal subset from 4_alot_of_ics can render.
- D02/D03/D09-D14 failed: arbitrary small bare subsets are not safe yet.

This pack takes the known-working D15 family mix as the control and removes or
swaps one ingredient at a time. It also adds explicit controls for the user's
question: whether terminalized donor records can simply have terminals/wires
removed and be emitted as no-terminal body records.
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


OUT_DIR = ROOT / "experiments/bare_visibility_ablation_v2_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_VISIBILITY_ABLATION_V2_TEMP_2026_06_16.zip"

MIXED_4X = ROOT / "proteus_ic/donors/mixed_large_20260611/4_alot_of_ics.pdsprj"
TERMINALIZED_MASTER = ROOT / "proteus_ic/donors/manual_downloads_20260615/component_placer/16x_seq_combo_mega_donor.pdsprj"

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
    end: int
    refs: tuple[str, ...]
    data: bytes

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "family": self.family,
            "start": self.start,
            "end": self.end,
            "refs": list(self.refs),
            "size": len(self.data),
            "sha256": sha256_bytes(self.data),
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def marker_counts(data: bytes) -> dict[str, int]:
    markers = FAMILY_MARKERS + ("$TERBIDIR", "$TERINPUT", "$TEROUTPUT", "$TERPOWER", "$TERGROUND", "WIRE")
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


def family_for(data: bytes) -> str | None:
    for marker in FAMILY_MARKERS:
        if marker.encode("ascii") in data:
            return marker
    return None


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


def terminal_starts(chunk: bytes) -> list[int]:
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


def wire_starts(chunk: bytes) -> list[int]:
    starts: list[int] = []
    pos = 0
    while True:
        found = chunk.find(WIRE_MARKER, pos)
        if found < 0:
            break
        starts.append(max(0, found - 14))
        pos = found + 1
    return starts


def groups_from_no_terminal_chunk(chunk: bytes) -> dict[str, list[BodyGroup]]:
    if not chunk.startswith(b"\x00\x00"):
        raise ValueError(f"Expected no-terminal chunk head 00 00, got {chunk[:8].hex()}.")
    if not chunk.endswith(b"\xff"):
        raise ValueError("Object chunk does not end FF.")
    if any(marker in chunk for marker in TERM_MARKERS) or WIRE_MARKER in chunk:
        raise ValueError("No-terminal source contains terminal or wire markers.")

    starts = object_record_starts(chunk)
    return _groups_from_starts(chunk, starts, [start for start, _ref in starts] + [len(chunk) - 1])


def groups_from_terminalized_body_records(chunk: bytes) -> dict[str, list[BodyGroup]]:
    starts = object_record_starts(chunk)
    breakpoints = sorted(set([start for start, _ref in starts] + terminal_starts(chunk) + wire_starts(chunk) + [len(chunk) - 1]))
    groups = _groups_from_starts(chunk, starts, breakpoints)
    for family_groups in groups.values():
        for group in family_groups:
            if any(marker in group.data for marker in TERM_MARKERS) or WIRE_MARKER in group.data:
                raise ValueError(f"Terminalized stripped group {group.key} still contains terminal or wire bytes.")
    return groups


def _groups_from_starts(chunk: bytes, starts: list[tuple[int, str]], breakpoints: list[int]) -> dict[str, list[BodyGroup]]:
    by_package: dict[str, list[tuple[str, str, int, int, bytes]]] = defaultdict(list)
    for start, ref in starts:
        end_candidates = [point for point in breakpoints if point > start]
        if not end_candidates:
            continue
        end = end_candidates[0]
        raw = chunk[start:end]
        family = family_for(raw)
        if family is None:
            continue
        by_package[package_ref(ref)].append((ref, family, start, end, raw))

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
            end=ordered[-1][3],
            refs=tuple(row[0] for row in ordered),
            data=b"".join(row[4] for row in ordered),
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


def write_case(case_id: str, template: Path, cdb: bytes, object_chunk: bytes, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    template_dsn = read_internal_file(template, "ROOT.DSN")
    dsn, pointers = build_dsn(template_dsn, template_dsn, object_chunk)
    write_project_from_parts(template, output, {"ROOT.DSN": dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    final_cdb = read_internal_file(output, "ROOT.CDB")
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs")
    if final_cdb != cdb:
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
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "root_cdb_size": len(final_cdb),
        "root_cdb_sha256": sha256_bytes(final_cdb),
        "marker_counts": marker_counts(final_chunk),
        "errors": errors,
    }


def build() -> dict[str, object]:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    mixed_dsn = read_internal_file(MIXED_4X, "ROOT.DSN")
    mixed_cdb = read_internal_file(MIXED_4X, "ROOT.CDB")
    mixed_groups = groups_from_no_terminal_chunk(_extract_object_chunk(mixed_dsn))

    terminalized_dsn = read_internal_file(TERMINALIZED_MASTER, "ROOT.DSN")
    terminalized_cdb = read_internal_file(TERMINALIZED_MASTER, "ROOT.CDB")
    terminalized_groups = groups_from_terminalized_body_records(_extract_object_chunk(terminalized_dsn))

    working_d15 = {
        "74HC160": 4,
        "7490": 2,
        "74HC08": 2,
        "74HC32": 2,
        "RESISTOR": 4,
        "CAP": 4,
        "REALIND": 4,
        "LM741": 2,
    }
    cases: list[dict[str, object]] = []
    specs: list[tuple[str, dict[str, int], str]] = [
        ("E00_D15_REBUILD_WORKING_CONTROL", working_d15, "Rebuild the user-confirmed working D15 family mix."),
        (
            "E01_D15_MINUS_7490",
            {k: v for k, v in working_d15.items() if k != "7490"},
            "Remove only 7490 from the working D15 shape.",
        ),
        (
            "E02_D15_MINUS_LM741",
            {k: v for k, v in working_d15.items() if k != "LM741"},
            "Remove only LM741 from the working D15 shape.",
        ),
        (
            "E03_D15_MINUS_RCL",
            {k: v for k, v in working_d15.items() if k not in {"RESISTOR", "CAP", "REALIND"}},
            "Remove R/C/L passives from the working D15 shape.",
        ),
        (
            "E04_D15_MINUS_COMB",
            {k: v for k, v in working_d15.items() if k not in {"74HC08", "74HC32"}},
            "Remove combinational 74HC08/74HC32 from the working D15 shape.",
        ),
        (
            "E05_ONE_160_KEEP_D15_SUPPORT",
            {**working_d15, "74HC160": 1},
            "Keep all D15 support families but reduce 74HC160 to one package.",
        ),
        (
            "E06_FOUR_160_TWO_7490_ONLY",
            {"74HC160": 4, "7490": 2},
            "Test whether 7490 is the critical companion for bare 74HC160.",
        ),
        (
            "E07_FOUR_160_TWO_7490_RCL",
            {"74HC160": 4, "7490": 2, "RESISTOR": 4, "CAP": 4, "REALIND": 4},
            "74HC160 plus 7490 plus R/C/L, without LM741 or combinational gates.",
        ),
        (
            "E08_FOUR_160_TWO_161_ONLY",
            {"74HC160": 4, "74HC161": 2},
            "Test 74HC161 as the native companion instead of 7490.",
        ),
        (
            "E09_TWO_160_TWO_161_RCL",
            {"74HC160": 2, "74HC161": 2, "RESISTOR": 2, "CAP": 2, "REALIND": 2},
            "74HC160 plus 74HC161 and R/C/L from the no-terminal mixed donor.",
        ),
        (
            "E10_SEQ_COMB_NO_ANALOG_NO_RCL",
            {"74HC160": 2, "7490": 2, "74HC08": 2, "74HC32": 2},
            "Sequential plus combinational only, no analog/RCL support records.",
        ),
    ]
    for case_id, counts, description in specs:
        cases.append(write_case(case_id, MIXED_4X, mixed_cdb, chunk_for(select_groups(mixed_groups, counts)), description))

    stripped_specs: list[tuple[str, dict[str, int], str]] = [
        (
            "E11_STRIPPED_TERMINALIZED_ONE_160",
            {"74HC160": 1},
            "Terminalized master component body records only: 1x 74HC160, no terminals/wires.",
        ),
        (
            "E12_STRIPPED_TERMINALIZED_FOUR_160_TWO_7490",
            {"74HC160": 4, "7490": 2},
            "Terminalized master body records only: 4x 74HC160 plus 2x 7490, no terminals/wires.",
        ),
        (
            "E13_STRIPPED_TERMINALIZED_SEQ_COMB_RCL",
            {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "RESISTOR": 4, "CAP": 4, "REALIND": 4},
            "Terminalized master body records only: D15-like without LM741, no terminals/wires.",
        ),
    ]
    for case_id, counts, description in stripped_specs:
        cases.append(write_case(case_id, TERMINALIZED_MASTER, terminalized_cdb, chunk_for(select_groups(terminalized_groups, counts)), description))

    return {
        "experiment": "bare_visibility_ablation_v2_temp_2026_06_16",
        "purpose": "Ablate from user-confirmed working D15 and test terminalized-record stripping.",
        "known_user_results_from_v1": {
            "worked": ["D04_PAIR_NOTERM_RECORDS_IN_TERMINALIZED_MASTER_CONTAINER", "D15_MIX8_SEQ_COMB_ANALOG_RLC_NOTERM"],
            "failed": [
                "D02_74HC160_1X_NOTERM_SUBSET_FROM_PAIR",
                "D03_FAILED_B00_WITH_EXTRA_NOTERM_PREFIX",
                "D09_74HC160_1X_FROM_MIXED_NOTERM",
                "D10_74HC160_3X_FROM_MIXED_NOTERM",
                "D11_74HC160_4X_FROM_MIXED_NOTERM",
                "D12_MIX5_160_HC08_R_C_L_NOTERM",
                "D13_MIX5_160_HC32_HC00_NPN_PNP_NOTERM",
                "D14_MIX5_160_HC86_HC266_LM741_ECAP_NOTERM",
            ],
        },
        "donors": {
            "no_terminal_mixed_4x": str(MIXED_4X.relative_to(ROOT)),
            "terminalized_master_strip_control": str(TERMINALIZED_MASTER.relative_to(ROOT)),
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
