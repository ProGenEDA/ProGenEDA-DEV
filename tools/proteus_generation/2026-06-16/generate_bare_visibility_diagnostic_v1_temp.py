"""Generate no-terminal component visibility diagnostics.

The first bare-component attempt used body records lifted from a terminalized
master donor and emitted an object stream shaped as:

    00 + selected_records + FF

User testing showed those files opened as empty sheets. Proteus-created
no-terminal donors in the manual corpus use a different object stream envelope:

    00 00 + component_records + FF

This experiment isolates that rule without touching the locked generators:

- exact copies of manual no-terminal donors
- rebuilds of the exact same no-terminal object streams
- subset outputs using no-terminal donor records with the observed envelope
- one corrected-envelope control around the previously empty output
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


OUT_DIR = ROOT / "experiments/bare_visibility_diagnostic_v1_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_VISIBILITY_DIAGNOSTIC_V1_TEMP_2026_06_16.zip"

PAIR_160_161 = ROOT / "proteus_ic/donors/manual_downloads_20260611/squence/PAIR_74HC160_74HC161.pdsprj"
MIXED_1X = ROOT / "proteus_ic/donors/mixed_large_20260611/alot_of_ics.pdsprj"
MIXED_4X = ROOT / "proteus_ic/donors/mixed_large_20260611/4_alot_of_ics.pdsprj"
MASTER_TERMINALIZED = ROOT / "proteus_ic/donors/manual_downloads_20260615/component_placer/16x_seq_combo_mega_donor.pdsprj"
FAILED_B00 = (
    ROOT
    / "experiments/74hc160_bare_mixed_v1_temp_2026_06_16/B00_74HC160_1X_BARE/B00_74HC160_1X_BARE.pdsprj"
)

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


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    output: Path
    source: str
    description: str
    object_chunk: bytes
    cdb: bytes
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "output": str(self.output.relative_to(ROOT)),
            "source": self.source,
            "description": self.description,
            "object_chunk_size": len(self.object_chunk),
            "object_chunk_head": self.object_chunk[:16].hex(),
            "object_chunk_tail": self.object_chunk[-16:].hex(),
            "object_chunk_sha256": sha256_bytes(self.object_chunk),
            "root_cdb_size": len(self.cdb),
            "root_cdb_sha256": sha256_bytes(self.cdb),
            "marker_counts": marker_counts(self.object_chunk),
            "errors": list(self.errors),
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
        window = chunk[start : start + 160]
        if b"COMPONENT ID" not in window:
            continue
        rows.append((start, match.group(1).decode("ascii", "ignore")))
    return rows


def groups_from_no_terminal_chunk(chunk: bytes) -> dict[str, list[BodyGroup]]:
    if not chunk.startswith(b"\x00\x00"):
        raise ValueError(f"Expected Proteus no-terminal chunk to start 00 00, got {chunk[:8].hex()}.")
    if not chunk.endswith(b"\xff"):
        raise ValueError("Expected object chunk to end with FF.")
    if any(marker in chunk for marker in TERM_MARKERS) or WIRE_MARKER in chunk:
        raise ValueError("This analyzer is only for no-terminal/no-wire donors.")

    starts = object_record_starts(chunk)
    by_package: dict[str, list[tuple[str, str, int, int, bytes]]] = defaultdict(list)
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
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


def no_terminal_object_chunk(groups: tuple[BodyGroup, ...]) -> bytes:
    return b"\x00\x00" + b"".join(group.data for group in sorted(groups, key=lambda item: item.start)) + b"\xff"


def write_exact_copy(case_id: str, source: Path, description: str) -> CaseResult:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(source, output)
    object_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = read_internal_file(output, "ROOT.CDB")
    return CaseResult(case_id, output, str(source.relative_to(ROOT)), description, object_chunk, cdb, ())


def write_rebuilt(
    case_id: str,
    template: Path,
    object_chunk: bytes,
    cdb: bytes,
    description: str,
    *,
    source_label: str | None = None,
) -> CaseResult:
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
        errors.append("final ROOT.DSN object chunk differs from requested chunk")
    if final_cdb != cdb:
        errors.append("final ROOT.CDB differs from requested bytes")
    if not final_chunk.startswith(b"\x00\x00"):
        errors.append(f"no-terminal object chunk does not start 00 00: {final_chunk[:8].hex()}")
    if any(marker in final_chunk for marker in TERM_MARKERS):
        errors.append("terminal marker present in no-terminal diagnostic output")
    if WIRE_MARKER in final_chunk:
        errors.append("WIRE marker present in no-terminal diagnostic output")
    if "parse_component_placer_cdb" in globals():
        try:
            parse_component_placer_cdb(final_cdb)
        except Exception as exc:  # pragma: no cover - manifest-only diagnostic
            errors.append(f"ROOT.CDB parse warning: {exc}")
    return CaseResult(
        case_id,
        output,
        source_label or str(template.relative_to(ROOT)),
        f"{description} pointers={pointers}",
        final_chunk,
        final_cdb,
        tuple(errors),
    )


def build_cases() -> list[CaseResult]:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    pair_dsn = read_internal_file(PAIR_160_161, "ROOT.DSN")
    pair_cdb = read_internal_file(PAIR_160_161, "ROOT.CDB")
    pair_chunk = _extract_object_chunk(pair_dsn)
    pair_groups = groups_from_no_terminal_chunk(pair_chunk)

    mixed_dsn = read_internal_file(MIXED_4X, "ROOT.DSN")
    mixed_cdb = read_internal_file(MIXED_4X, "ROOT.CDB")
    mixed_chunk = _extract_object_chunk(mixed_dsn)
    mixed_groups = groups_from_no_terminal_chunk(mixed_chunk)

    mixed_1x_dsn = read_internal_file(MIXED_1X, "ROOT.DSN")
    mixed_1x_cdb = read_internal_file(MIXED_1X, "ROOT.CDB")
    mixed_1x_chunk = _extract_object_chunk(mixed_1x_dsn)

    master_cdb = read_internal_file(MASTER_TERMINALIZED, "ROOT.CDB")

    cases: list[CaseResult] = []
    cases.append(
        write_exact_copy(
            "D00_PAIR_160_161_EXACT_NOTERM_COPY",
            PAIR_160_161,
            "Exact copy of Proteus-created no-terminal 74HC160+74HC161 donor.",
        )
    )
    cases.append(
        write_rebuilt(
            "D01_PAIR_160_161_REBUILT_SAME_CHUNK",
            PAIR_160_161,
            pair_chunk,
            pair_cdb,
            "Rebuild exact no-terminal pair donor chunk through build_dsn.",
        )
    )
    cases.append(
        write_rebuilt(
            "D02_74HC160_1X_NOTERM_SUBSET_FROM_PAIR",
            PAIR_160_161,
            no_terminal_object_chunk(select_groups(pair_groups, {"74HC160": 1})),
            pair_cdb,
            "Single 74HC160 selected from a Proteus-created no-terminal pair donor.",
        )
    )

    if FAILED_B00.exists():
        failed_chunk = _extract_object_chunk(read_internal_file(FAILED_B00, "ROOT.DSN"))
        corrected_chunk = b"\x00" + failed_chunk if failed_chunk.startswith(b"\x00") else b"\x00\x00" + failed_chunk
        cases.append(
            write_rebuilt(
                "D03_FAILED_B00_WITH_EXTRA_NOTERM_PREFIX",
                MASTER_TERMINALIZED,
                corrected_chunk,
                master_cdb,
                "Previously empty B00 output with only the missing leading 00 prefix added.",
                source_label=str(FAILED_B00.relative_to(ROOT)),
            )
        )

    cases.append(
        write_rebuilt(
            "D04_PAIR_NOTERM_RECORDS_IN_TERMINALIZED_MASTER_CONTAINER",
            MASTER_TERMINALIZED,
            pair_chunk,
            master_cdb,
            "Exact no-terminal pair object chunk placed in the terminalized master DSN/CDB container.",
        )
    )
    cases.append(
        write_exact_copy(
            "D05_MIXED_1X_EXACT_NOTERM_COPY",
            MIXED_1X,
            "Exact copy of manual no-terminal mixed 1x donor.",
        )
    )
    cases.append(
        write_rebuilt(
            "D06_MIXED_1X_REBUILT_SAME_CHUNK",
            MIXED_1X,
            mixed_1x_chunk,
            mixed_1x_cdb,
            "Rebuild exact manual no-terminal mixed 1x donor chunk.",
        )
    )
    cases.append(
        write_exact_copy(
            "D07_MIXED_4X_EXACT_NOTERM_COPY",
            MIXED_4X,
            "Exact copy of manual no-terminal mixed 4x donor.",
        )
    )
    cases.append(
        write_rebuilt(
            "D08_MIXED_4X_REBUILT_SAME_CHUNK",
            MIXED_4X,
            mixed_chunk,
            mixed_cdb,
            "Rebuild exact manual no-terminal mixed 4x donor chunk.",
        )
    )

    subset_specs = [
        (
            "D09_74HC160_1X_FROM_MIXED_NOTERM",
            {"74HC160": 1},
            "One 74HC160 from the no-terminal mixed donor.",
        ),
        (
            "D10_74HC160_3X_FROM_MIXED_NOTERM",
            {"74HC160": 3},
            "Three 74HC160 packages from the no-terminal mixed donor.",
        ),
        (
            "D11_74HC160_4X_FROM_MIXED_NOTERM",
            {"74HC160": 4},
            "All four available 74HC160 packages from the no-terminal mixed donor.",
        ),
        (
            "D12_MIX5_160_HC08_R_C_L_NOTERM",
            {"74HC160": 2, "74HC08": 2, "RESISTOR": 2, "CAP": 2, "REALIND": 2},
            "Bare five-family mix: 74HC160, 74HC08, resistor, capacitor, inductor.",
        ),
        (
            "D13_MIX5_160_HC32_HC00_NPN_PNP_NOTERM",
            {"74HC160": 2, "74HC32": 2, "74HC00": 2, "NPN": 2, "PNP": 2},
            "Bare five-family mix: 74HC160, 74HC32, 74HC00, NPN, PNP.",
        ),
        (
            "D14_MIX5_160_HC86_HC266_LM741_ECAP_NOTERM",
            {"74HC160": 2, "74HC86": 2, "74HC266": 2, "LM741": 2, "CAP-ELEC": 2},
            "Bare five-family mix: 74HC160, 74HC86, 74HC266, LM741, electrolytic capacitor.",
        ),
        (
            "D15_MIX8_SEQ_COMB_ANALOG_RLC_NOTERM",
            {
                "74HC160": 4,
                "7490": 2,
                "74HC08": 2,
                "74HC32": 2,
                "RESISTOR": 4,
                "CAP": 4,
                "REALIND": 4,
                "LM741": 2,
            },
            "Larger bare mix from one no-terminal donor: sequential, combinational, R/C/L, and LM741.",
        ),
    ]
    for case_id, counts, description in subset_specs:
        selected = select_groups(mixed_groups, counts)
        chunk = no_terminal_object_chunk(selected)
        cases.append(write_rebuilt(case_id, MIXED_4X, chunk, mixed_cdb, description))

    return cases


def zip_dir(src: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with ZipFile(output, "w") as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            arcname = path.relative_to(src).as_posix()
            info = ZipInfo(arcname)
            info.compress_type = ZIP_DEFLATED
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o600 << 16
            zf.writestr(info, path.read_bytes())


def main() -> None:
    cases = build_cases()
    summary = {
        "experiment": "bare_visibility_diagnostic_v1_temp_2026_06_16",
        "purpose": "Diagnose empty no-terminal bare-component outputs and test Proteus-created no-terminal donor subsets.",
        "rule_under_test": "No-terminal object streams use 00 00 + records + FF, and records should come from Proteus-created no-terminal donors.",
        "donors": {
            "pair_160_161": str(PAIR_160_161.relative_to(ROOT)),
            "mixed_1x": str(MIXED_1X.relative_to(ROOT)),
            "mixed_4x": str(MIXED_4X.relative_to(ROOT)),
            "terminalized_master_control": str(MASTER_TERMINALIZED.relative_to(ROOT)),
            "failed_b00_control": str(FAILED_B00.relative_to(ROOT)) if FAILED_B00.exists() else None,
        },
        "cases": [case.as_dict() for case in cases],
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": len(cases), "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
