"""Generate no-terminal mega-donor component separation tests.

This experiment follows the V5 finding: failed no-terminal subsets were caused
by making a middle object record final without converting it to final-record
form. The pack uses Proteus-created no-terminal mega donors and selects complete
component groups only. If the selected last group was not the donor's original
last object, the final byte of that group is trimmed before appending the object
stream FF terminator.
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

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


OUT_DIR = ROOT / "experiments/mega_bare_separation_v1_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/MEGA_BARE_SEPARATION_V1_TEMP_2026_06_16.zip"
DONOR_DIR = ROOT / "proteus_ic/donors/manual_downloads_20260616/mega_component_placer"

SEMI_NO_SOURCE = (
    DONOR_DIR
    / "semimega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)
SEMI_WITH_SOURCE = (
    DONOR_DIR
    / "semimega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistorandsources.pdsprj"
)
FIFTEEN_X_WITH_SOURCE = (
    DONOR_DIR
    / "15xsemimega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistorandsources.pdsprj"
)

FAMILY_MARKERS = tuple(
    sorted(
        (
            "7SEG-COM-ANODE",
            "CAP-ELEC",
            "74HC266",
            "74HC283",
            "74HC192",
            "74HC174",
            "74HC160",
            "74HC157",
            "74HC151",
            "74HC85",
            "74HC76",
            "74HC74",
            "74HC00",
            "74HC02",
            "74HC04",
            "74HC08",
            "74HC32",
            "74HC86",
            "RESISTOR",
            "REALIND",
            "VSOURCE",
            "CSOURCE",
            "LM741",
            "NE555",
            "DIODE",
            "4027",
            "4511",
            "7447",
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
RECORD_START_RE = re.compile(
    rb"\xff[\x02-\x08]((?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+)|(?:Q\d+)|(?:D\d+)|(?:V\d+)|(?:I\d+))"
)


@dataclass(frozen=True)
class BodyGroup:
    key: str
    family: str
    start: int
    end: int
    refs: tuple[str, ...]
    data: bytes
    source_is_final: bool

    def as_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "family": self.family,
            "start": self.start,
            "end": self.end,
            "refs": list(self.refs),
            "size": len(self.data),
            "source_is_final": self.source_is_final,
            "sha256": sha256_bytes(self.data),
        }


@dataclass(frozen=True)
class DonorState:
    path: Path
    dsn: bytes
    cdb: bytes
    chunk: bytes
    groups_by_family: dict[str, list[BodyGroup]]
    all_groups: tuple[BodyGroup, ...]

    def counts(self) -> dict[str, int]:
        return {family: len(groups) for family, groups in sorted(self.groups_by_family.items())}


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
        if b"COMPONENT ID" not in chunk[start : start + 200]:
            continue
        rows.append((start, match.group(1).decode("ascii", "ignore")))
    return rows


def groups_from_no_terminal_chunk(chunk: bytes) -> tuple[dict[str, list[BodyGroup]], tuple[BodyGroup, ...]]:
    if not chunk.startswith(b"\x00\x00"):
        raise ValueError(f"Expected no-terminal chunk head 00 00, got {chunk[:8].hex()}.")
    if not chunk.endswith(b"\xff"):
        raise ValueError("Expected object chunk to end with FF.")
    if any(marker in chunk for marker in TERM_MARKERS):
        raise ValueError("No-terminal mega donor unexpectedly contains terminal markers.")

    starts = object_record_starts(chunk)
    records: list[tuple[int, int, str, str, bytes]] = []
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
        raw = chunk[start:end]
        family = family_for(raw)
        if family is None:
            continue
        records.append((start, end, ref, family, raw))

    groups: list[BodyGroup] = []
    current: list[tuple[int, int, str, str, bytes]] = []
    current_key: str | None = None
    for row in records:
        key = package_ref(row[2])
        if current and key != current_key:
            groups.append(make_group(current, len(chunk)))
            current = []
        current.append(row)
        current_key = key
    if current:
        groups.append(make_group(current, len(chunk)))

    by_family: dict[str, list[BodyGroup]] = defaultdict(list)
    for group in groups:
        by_family[group.family].append(group)
    for family in by_family:
        by_family[family].sort(key=lambda item: item.start)
    return dict(by_family), tuple(sorted(groups, key=lambda item: item.start))


def make_group(rows: list[tuple[int, int, str, str, bytes]], chunk_size: int) -> BodyGroup:
    families = Counter(row[3] for row in rows)
    if len(families) != 1:
        raise ValueError(f"Contiguous package group matched mixed families: {dict(families)}")
    starts = [row[0] for row in rows]
    ends = [row[1] for row in rows]
    data = b"".join(row[4] for row in rows)
    return BodyGroup(
        key=package_ref(rows[0][2]),
        family=rows[0][3],
        start=min(starts),
        end=max(ends),
        refs=tuple(row[2] for row in rows),
        data=data,
        source_is_final=max(ends) == chunk_size - 1,
    )


def load_donor(path: Path) -> DonorState:
    dsn = read_internal_file(path, "ROOT.DSN")
    cdb = read_internal_file(path, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    groups_by_family, all_groups = groups_from_no_terminal_chunk(chunk)
    return DonorState(path=path, dsn=dsn, cdb=cdb, chunk=chunk, groups_by_family=groups_by_family, all_groups=all_groups)


def select_groups(state: DonorState, counts: dict[str, int]) -> tuple[BodyGroup, ...]:
    selected: list[BodyGroup] = []
    for family, count in counts.items():
        available = state.groups_by_family.get(family, [])
        if len(available) < count:
            raise ValueError(f"{state.path.name}: need {count} {family} groups, found {len(available)}.")
        selected.extend(available[:count])
    return tuple(sorted(selected, key=lambda item: item.start))


def all_groups_except(state: DonorState, excluded_families: set[str]) -> tuple[BodyGroup, ...]:
    return tuple(group for group in state.all_groups if group.family not in excluded_families)


def finalize_last_group(group: BodyGroup) -> tuple[bytes, bool]:
    if group.source_is_final:
        return group.data, False
    if not group.data.endswith(b"\x00"):
        raise ValueError(f"Cannot finalize {group.key}: non-final group does not end in 00.")
    return group.data[:-1], True


def object_chunk_for(selected: tuple[BodyGroup, ...]) -> tuple[bytes, dict[str, object]]:
    if not selected:
        return b"\x00\x00\xff", {"last_group": None, "trimmed_last_byte": False}
    ordered = tuple(sorted(selected, key=lambda item: item.start))
    prefix_groups = ordered[:-1]
    final_data, trimmed = finalize_last_group(ordered[-1])
    return (
        b"\x00\x00" + b"".join(group.data for group in prefix_groups) + final_data + b"\xff",
        {
            "last_group": ordered[-1].as_dict(),
            "trimmed_last_byte": trimmed,
            "selected_group_count": len(ordered),
        },
    )


def copy_exact_case(case_id: str, state: DonorState, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(state.path, output)
    return describe_case(case_id, output, state, state.chunk, description, {"copy_exact": True})


def write_case(
    case_id: str,
    state: DonorState,
    selected: tuple[BodyGroup, ...],
    description: str,
    *,
    force_chunk: bytes | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    object_chunk, finalization = object_chunk_for(selected) if force_chunk is None else (force_chunk, {"forced_chunk": True})
    dsn, pointers = build_dsn(state.dsn, state.dsn, object_chunk)
    write_project_from_parts(state.path, output, {"ROOT.DSN": dsn, "ROOT.CDB": state.cdb}, compression=ZIP_DEFLATED)
    merged_extra = {"pointers": pointers, "finalization": finalization}
    if extra:
        merged_extra.update(extra)
    return describe_case(case_id, output, state, object_chunk, description, merged_extra)


def describe_case(
    case_id: str,
    output: Path,
    state: DonorState,
    requested_chunk: bytes,
    description: str,
    extra: dict[str, object],
) -> dict[str, object]:
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    final_cdb = read_internal_file(output, "ROOT.CDB")
    errors: list[str] = []
    if final_chunk != requested_chunk:
        errors.append("final object chunk differs from requested chunk")
    if final_cdb != state.cdb:
        errors.append("ROOT.CDB differs from donor")
    if not final_chunk.startswith(b"\x00\x00"):
        errors.append(f"object chunk does not start 00 00: {final_chunk[:8].hex()}")
    if any(marker in final_chunk for marker in TERM_MARKERS):
        errors.append("terminal marker present")
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(state.path.relative_to(ROOT)),
        "description": description,
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "root_cdb_size": len(final_cdb),
        "root_cdb_sha256": sha256_bytes(final_cdb),
        "marker_counts": marker_counts(final_chunk),
        "errors": errors,
        **extra,
    }


def count_dict_from_groups(groups: tuple[BodyGroup, ...]) -> dict[str, int]:
    return dict(sorted(Counter(group.family for group in groups).items()))


def build_cases() -> dict[str, object]:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    semi = load_donor(SEMI_NO_SOURCE)
    source = load_donor(SEMI_WITH_SOURCE)
    large = load_donor(FIFTEEN_X_WITH_SOURCE)

    native_one_each = {
        "7447": 1,
        "7490": 1,
        "4511": 1,
        "4027": 1,
        "74HC283": 1,
        "74HC192": 1,
        "74HC174": 1,
        "74HC160": 1,
        "74HC157": 1,
        "74HC85": 1,
        "74HC76": 1,
        "74HC74": 1,
        "74HC151": 1,
    }
    comb_one_each = {
        "74HC00": 1,
        "74HC02": 1,
        "74HC04": 1,
        "74HC08": 1,
        "74HC32": 1,
        "74HC86": 1,
        "74HC266": 1,
    }
    passive_one_each = {
        "RESISTOR": 1,
        "CAP": 1,
        "REALIND": 1,
        "CAP-ELEC": 1,
        "NPN": 1,
        "PNP": 1,
        "LM741": 1,
        "NE555": 1,
        "DIODE": 1,
    }

    cases: list[dict[str, object]] = []
    cases.append(copy_exact_case("M00_EXACT_SEMIMEGA_COPY", semi, "Exact copy of the user-provided no-source semimega donor."))
    cases.append(
        write_case(
            "M01_REBUILT_EXACT_SEMIMEGA_CHUNK",
            semi,
            (),
            "Rebuild the exact no-source semimega object chunk through build_dsn.",
            force_chunk=semi.chunk,
        )
    )
    cases.append(
        write_case(
            "M02_ALL_COMPONENTS_MINUS_FINAL_7SEG",
            semi,
            all_groups_except(semi, {"7SEG-COM-ANODE"}),
            "Remove only the donor-final 7SEG group; final selected DIODE is converted from middle-record form.",
        )
    )
    case_specs = [
        ("M03_ONE_74HC160", {"74HC160": 1}, "Single 74HC160 package from the semimega donor."),
        ("M04_FOUR_74HC160", {"74HC160": 4}, "All four 74HC160 packages from the semimega donor."),
        (
            "M05_NO_RESISTORS_MIXED",
            {"74HC160": 2, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 3, "CAP": 4, "REALIND": 4, "NPN": 2, "PNP": 2, "CAP-ELEC": 2},
            "Mixed IC/analog/passive case with all resistor records removed.",
        ),
        ("M06_NO_RLC_IC_ONLY", {**native_one_each, **comb_one_each}, "IC-only selection with no R/C/L, no analog discretes, and no display."),
        (
            "M07_PASSIVE_ANALOG_ONLY",
            {"RESISTOR": 5, "CAP": 5, "REALIND": 5, "CAP-ELEC": 5, "NPN": 3, "PNP": 3, "LM741": 3, "NE555": 2, "DIODE": 3},
            "Passive/analog-only selection without digital ICs.",
        ),
        ("M08_LOGIC_ONE_EACH", {**native_one_each, **comb_one_each}, "One package of every native and combinational IC family in the semimega donor."),
        ("M09_ALL_SUPPORTED_ONE_EACH", {**native_one_each, **comb_one_each, **passive_one_each, "7SEG-COM-ANODE": 1}, "One of every non-source family, keeping the donor-final display."),
        ("M10_DISPLAY_DRIVER_SET", {"7447": 2, "4511": 2, "7SEG-COM-ANODE": 1, "RESISTOR": 4, "CAP": 2}, "Display-driver set with 7447, 4511, 7SEG common anode, and passive support."),
        ("M11_DIODE_ONLY", {"DIODE": 1}, "Single diode only."),
        ("M12_CAP_ELEC_ONLY", {"CAP-ELEC": 1}, "Single electrolytic capacitor only."),
        ("M13_NPN_PNP_ONLY", {"NPN": 2, "PNP": 2}, "Two NPN and two PNP transistors only."),
        ("M14_NE555_LM741_ANALOG", {"NE555": 4, "LM741": 5, "RESISTOR": 4, "CAP": 4, "CAP-ELEC": 2}, "NE555 and LM741 analog set with several passive records."),
        (
            "M15_RANDOM_30_COMPONENT_MIX",
            {"7447": 1, "7490": 1, "74HC160": 2, "74HC08": 2, "74HC32": 2, "74HC266": 1, "RESISTOR": 5, "CAP": 5, "REALIND": 4, "CAP-ELEC": 3, "NPN": 2, "PNP": 2},
            "Thirty-component mixed selection from the no-source semimega donor.",
        ),
        ("M16_NO_RESISTOR_ONE_EACH_WITH_DISPLAY", {**native_one_each, **comb_one_each, **{k: v for k, v in passive_one_each.items() if k != "RESISTOR"}, "7SEG-COM-ANODE": 1}, "One of every non-source family except RESISTOR."),
    ]
    for case_id, counts, description in case_specs:
        selected = select_groups(semi, counts)
        cases.append(write_case(case_id, semi, selected, description, extra={"requested_counts": counts}))

    cases.append(copy_exact_case("S00_EXACT_SOURCE_SEMIMEGA_COPY", source, "Exact copy of source-enabled semimega donor."))
    cases.append(
        write_case(
            "S01_REBUILT_EXACT_SOURCE_SEMIMEGA_CHUNK",
            source,
            (),
            "Rebuild the exact source-enabled semimega object chunk through build_dsn.",
            force_chunk=source.chunk,
        )
    )
    source_specs = [
        ("S02_SOURCES_ONLY", {"VSOURCE": 4, "CSOURCE": 4}, "Four voltage-source and four current-source records only."),
        ("S03_ALL_SUPPORTED_ONE_EACH_WITH_SOURCES", {**native_one_each, **comb_one_each, **passive_one_each, "7SEG-COM-ANODE": 1, "VSOURCE": 1, "CSOURCE": 1}, "One of every source and non-source family."),
        ("S04_NO_RESISTOR_WITH_SOURCES", {"74HC160": 2, "74HC08": 2, "LM741": 2, "CAP": 4, "REALIND": 4, "VSOURCE": 2, "CSOURCE": 2}, "Source-enabled mixed case with all resistors removed."),
        ("S05_SOURCES_DISPLAY_DRIVERS", {"7447": 2, "4511": 2, "7SEG-COM-ANODE": 1, "VSOURCE": 2, "CSOURCE": 2, "RESISTOR": 4}, "Display drivers plus source records."),
        (
            "S06_LARGE_SOURCE_MIX_FROM_15X",
            {"VSOURCE": 15, "CSOURCE": 10, "74HC160": 10, "7490": 10, "74HC08": 10, "74HC32": 10, "RESISTOR": 20, "CAP": 15, "REALIND": 15, "CAP-ELEC": 10, "NPN": 8, "PNP": 8, "DIODE": 8},
            "Large source-enabled mix selected from the 15x donor.",
        ),
    ]
    for case_id, counts, description in source_specs:
        state = large if case_id == "S06_LARGE_SOURCE_MIX_FROM_15X" else source
        selected = select_groups(state, counts)
        cases.append(write_case(case_id, state, selected, description, extra={"requested_counts": counts}))

    return {
        "experiment": "mega_bare_separation_v1_temp_2026_06_16",
        "purpose": "Test arbitrary no-terminal component separation from user-provided all-supported-component donors.",
        "rule_under_test": "Use Proteus-created no-terminal groups, preserve full donor ROOT.CDB, and convert a selected middle last group to final form by trimming one trailing 00 byte before the FF terminator.",
        "donor_counts": {
            "semimega_no_source": semi.counts(),
            "semimega_with_source": source.counts(),
            "15xsemimega_with_source": large.counts(),
        },
        "source_donors": {
            "semimega_no_source": str(SEMI_NO_SOURCE.relative_to(ROOT)),
            "semimega_with_source": str(SEMI_WITH_SOURCE.relative_to(ROOT)),
            "15xsemimega_with_source": str(FIFTEEN_X_WITH_SOURCE.relative_to(ROOT)),
        },
        "case_count": len(cases),
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
    summary = build_cases()
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": summary["case_count"], "zip_sha256": sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
