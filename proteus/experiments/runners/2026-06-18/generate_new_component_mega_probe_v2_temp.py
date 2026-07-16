"""Generate V2 separated-component circuits for the updated new-component mega donors.

This is an experimental, no-terminal component-placement pack. It is based on
the updated 2026-06-18 donors where the faulty 4007 package was removed, the
fuse donor changed, VPULSE was added, and diode/MOSFET variants must be kept as
separate families.
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

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn


DONOR_DIR = ROOT / "proteus/active/evidence/donors/manual_downloads_20260618/new_component_mega"
SINGLE_DONOR = DONOR_DIR / "new_components_single_mega.pdsprj"
FIVE_X_DONOR = DONOR_DIR / "new_components_5x_mega.pdsprj"

OUT_DIR = ROOT / "experiments/new_component_mega_probe_v2_temp_2026_06_18"
ZIP_OUT = ROOT / "experiments/NEW_COMPONENT_MEGA_PROBE_V2_TEMP_2026_06_18.zip"

# Specific part strings must precede generic family markers. For example,
# 2N7000 and BS170 records also contain MOSFET/NMOS text, and potentiometers
# contain a TSWITCH property even though they are not switch components.
FAMILY_MARKERS = (
    "7SEG-COM-CAT-RED",
    "7SEG-COM-AN-BLUE",
    "1N4007",
    "1N4148",
    "1N6000B",
    "IRDIODE",
    "POT-HG",
    "1N4733A",
    "2N3904",
    "2N4401",
    "2N7000",
    "BS170",
    "LED-RED",
    "LM317T",
    "LM741",
    "FUSE",
    "BRIDGE",
    "OPAMP",
    "SWITCH",
    "NMOSFET",
    "CAP-ELEC",
    "VPULSE",
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
    "VSINE",
    "NE555",
    "DIODE",
    "4027",
    "4511",
    "7447",
    "7490",
    "CAP",
    "NPN",
    "PNP",
)
TERM_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
NAMED_RECORD_START_RE = re.compile(
    rb"\xff[\x02-\x08]("
    rb"(?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+)|(?:Q\d+)|(?:D\d+)|"
    rb"(?:V\d+)|(?:I\d+)|(?:BR\d+)|(?:FU\d+)|(?:RV\d+)|(?:TR\d+)"
    rb")"
)
ANON_RECORD_START_RE = re.compile(rb"\xff\x00.{30,80}?Default Font\x00COMPONENT ID", re.S)


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
            "tail": self.data[-8:].hex(),
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


def package_ref(ref: str) -> str:
    if ref.startswith("ANON"):
        return ref
    return ref.split(":", 1)[0]


def object_record_starts(chunk: bytes) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    for match in NAMED_RECORD_START_RE.finditer(chunk):
        start = match.start()
        if b"COMPONENT ID" in chunk[start : start + 220]:
            starts.append((start, match.group(1).decode("ascii", "ignore")))
    for match in ANON_RECORD_START_RE.finditer(chunk):
        starts.append((match.start(), f"ANON{match.start()}"))
    return sorted(set(starts))


def groups_from_chunk(chunk: bytes) -> tuple[dict[str, list[BodyGroup]], tuple[BodyGroup, ...]]:
    if not chunk.startswith(b"\x00\x00"):
        raise ValueError(f"Expected no-terminal chunk head 00 00, got {chunk[:8].hex()}.")
    if not chunk.endswith(b"\xff"):
        raise ValueError("Expected object chunk to end with FF.")
    if any(marker in chunk for marker in TERM_MARKERS):
        raise ValueError("New-component mega donor unexpectedly contains terminal markers.")

    starts = object_record_starts(chunk)
    rows: list[tuple[int, int, str, str, bytes]] = []
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(chunk) - 1
        raw = chunk[start:end]
        family = family_for(raw)
        if family is None:
            continue
        rows.append((start, end, ref, family, raw))

    groups: list[BodyGroup] = []
    current: list[tuple[int, int, str, str, bytes]] = []
    current_key: str | None = None
    for row in rows:
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
    groups_by_family, all_groups = groups_from_chunk(chunk)
    return DonorState(path=path, dsn=dsn, cdb=cdb, chunk=chunk, groups_by_family=groups_by_family, all_groups=all_groups)


def select_groups(state: DonorState, counts: dict[str, int]) -> tuple[BodyGroup, ...]:
    selected: list[BodyGroup] = []
    for family, count in counts.items():
        available = [group for group in state.groups_by_family.get(family, []) if is_finalizable(group)]
        if len(available) < count:
            raise ValueError(f"{state.path.name}: need {count} finalizable {family} groups, found {len(available)}.")
        selected.extend(available[:count])
    return tuple(sorted(selected, key=lambda item: item.start))


def finalizable_count(state: DonorState, family: str) -> int:
    return sum(1 for group in state.groups_by_family.get(family, []) if is_finalizable(group))


def state_for_count(single: DonorState, five: DonorState, counts: dict[str, int]) -> DonorState:
    if all(finalizable_count(single, family) >= count for family, count in counts.items()):
        return single
    if all(finalizable_count(five, family) >= count for family, count in counts.items()):
        return five
    missing = {
        family: {
            "requested": count,
            "single_finalizable": finalizable_count(single, family),
            "five_x_finalizable": finalizable_count(five, family),
        }
        for family, count in counts.items()
        if finalizable_count(five, family) < count
    }
    raise ValueError(f"Not enough finalizable packets for {counts}: {missing}")


def safe_case_name(family: str) -> str:
    return (
        family.replace("-", "_")
        .replace("+", "PLUS")
        .replace("/", "_")
        .replace(" ", "_")
        .replace("(", "")
        .replace(")", "")
    )


def is_finalizable(group: BodyGroup) -> bool:
    return group.source_is_final or bool(group.data and group.data[-1] in (0x00, 0x08))


def finalize_last_group(group: BodyGroup) -> tuple[bytes, dict[str, object]]:
    if group.source_is_final:
        return group.data, {"trimmed_last_byte": False, "trimmed_byte": None}
    if not group.data or group.data[-1] not in (0x00, 0x08):
        raise ValueError(f"Cannot finalize {group.key}: unexpected tail {group.data[-8:].hex()}.")
    return group.data[:-1], {"trimmed_last_byte": True, "trimmed_byte": f"{group.data[-1]:02x}"}


def object_chunk_for(selected: tuple[BodyGroup, ...]) -> tuple[bytes, dict[str, object]]:
    if not selected:
        return b"\x00\x00\xff", {"last_group": None, "trimmed_last_byte": False}
    ordered = tuple(sorted(selected, key=lambda item: item.start))
    final_data, final_meta = finalize_last_group(ordered[-1])
    return (
        b"\x00\x00" + b"".join(group.data for group in ordered[:-1]) + final_data + b"\xff",
        {
            "last_group": ordered[-1].as_dict(),
            "selected_group_count": len(ordered),
            **final_meta,
        },
    )


def marker_counts(data: bytes) -> dict[str, int]:
    markers = FAMILY_MARKERS + ("$TERBIDIR", "$TERINPUT", "$TEROUTPUT", "$TERPOWER", "$TERGROUND", "WIRE")
    return {marker: data.count(marker.encode("ascii")) for marker in markers if data.count(marker.encode("ascii"))}


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


def build_cases() -> dict[str, object]:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    single = load_donor(SINGLE_DONOR)
    five = load_donor(FIVE_X_DONOR)
    separated_families = [
        "VPULSE",
        "VSOURCE",
        "CSOURCE",
        "VSINE",
        "SWITCH",
        "FUSE",
        "BRIDGE",
        "1N4007",
        "1N4148",
        "1N4733A",
        "1N6000B",
        "IRDIODE",
        "DIODE",
        "LED-RED",
        "2N3904",
        "2N4401",
        "NPN",
        "PNP",
        "NMOSFET",
        "2N7000",
        "BS170",
        "LM317T",
        "LM741",
        "OPAMP",
        "NE555",
        "POT-HG",
        "RESISTOR",
        "CAP",
        "CAP-ELEC",
        "REALIND",
    ]
    separated_counts = (1, 5, 15, 23)

    cases: list[dict[str, object]] = []
    cases.append(copy_exact_case("N00_EXACT_SINGLE_MEGA_COPY", single, "Exact copy of the user-provided new-component single mega donor."))
    cases.append(write_case("N01_REBUILT_SINGLE_MEGA_CHUNK", single, (), "Rebuild the exact single mega object chunk through build_dsn.", force_chunk=single.chunk))
    cases.append(copy_exact_case("N02_EXACT_5X_MEGA_COPY", five, "Exact copy of the user-provided new-component 5x mega donor."))
    cases.append(write_case("N03_REBUILT_5X_MEGA_CHUNK", five, (), "Rebuild the exact 5x mega object chunk through build_dsn.", force_chunk=five.chunk))

    skipped: list[dict[str, object]] = []
    seq = 1
    for family in separated_families:
        for count in separated_counts:
            counts = {family: count}
            if finalizable_count(five, family) < count:
                skipped.append(
                    {
                        "family": family,
                        "requested": count,
                        "single_finalizable": finalizable_count(single, family),
                        "five_x_finalizable": finalizable_count(five, family),
                    }
                )
                continue
            state = state_for_count(single, five, counts)
            cases.append(
                write_case(
                    f"S{seq:03d}_{count:02d}X_{safe_case_name(family)}",
                    state,
                    select_groups(state, counts),
                    f"{count} separated no-terminal {family} packet(s) selected from the updated new-component mega donor.",
                    extra={"requested_counts": counts},
                )
            )
            seq += 1

    multiple_specs = [
        (
            "M01_NEW_FAMILIES_ONE_EACH",
            {family: 1 for family in separated_families if finalizable_count(five, family) >= 1},
            "One packet of every supported family in the updated new-component donors.",
        ),
        (
            "M02_NEW_FAMILIES_FIVE_EACH",
            {family: 5 for family in separated_families if finalizable_count(five, family) >= 5},
            "Five packets of every supported family with at least five safe donor packets.",
        ),
        (
            "M03_SWITCH_FUSE_BRIDGE_POWER_PATH",
            {"SWITCH": 5, "FUSE": 5, "BRIDGE": 5, "1N4007": 5, "1N4148": 5, "LED-RED": 5, "VPULSE": 5},
            "Power-path style group: switches, fuses, bridge rectifiers, diode variants, LEDs, and VPULSE.",
        ),
        ("M04_REGULATOR_DRIVER_ANALOG_SET", {"LM317T": 5, "OPAMP": 5, "NMOSFET": 5, "2N7000": 5, "BS170": 5, "POT-HG": 5}, "Regulator/driver style group: LM317, op-amp, MOSFETs, potentiometers."),
        ("M05_TRANSISTOR_DIODE_VARIANTS", {"2N3904": 5, "2N4401": 5, "1N4733A": 5, "1N6000B": 5, "IRDIODE": 5, "LED-RED": 5}, "Discrete transistor and diode variants."),
        (
            "M06_NEW_PLUS_EXISTING_MIX",
            {
                "SWITCH": 3,
                "FUSE": 3,
                "BRIDGE": 3,
                "VPULSE": 3,
                "LM317T": 3,
                "OPAMP": 3,
                "2N7000": 3,
                "BS170": 3,
                "RESISTOR": 5,
                "CAP": 5,
                "CAP-ELEC": 5,
                "REALIND": 5,
                "VSOURCE": 3,
                "CSOURCE": 3,
                "VSINE": 3,
            },
            "New families mixed with passive and source packets from the same donor.",
        ),
        (
            "M07_LARGE_NEW_COMPONENT_STRESS",
            {
                "SWITCH": 15,
                "FUSE": 15,
                "BRIDGE": 15,
                "LED-RED": 15,
                "VPULSE": 15,
                "POT-HG": 15,
                "LM317T": 10,
                "OPAMP": 10,
                "NMOSFET": 10,
                "2N3904": 10,
                "2N4401": 10,
                "2N7000": 10,
                "BS170": 10,
                "1N4733A": 10,
                "1N4007": 10,
                "1N4148": 10,
                "1N6000B": 10,
                "IRDIODE": 10,
            },
            "Larger no-terminal stress case selected from the 5x mega donor.",
        ),
    ]
    for case_id, counts, description in multiple_specs:
        state = state_for_count(single, five, counts)
        cases.append(write_case(case_id, state, select_groups(state, counts), description, extra={"requested_counts": counts}))

    return {
        "experiment": "new_component_mega_probe_v2_temp_2026_06_18",
        "purpose": "Generate separated no-terminal components from the updated new-component donors, including VPULSE and diode/MOSFET variants while excluding the old faulty 4007 IC package.",
        "separated_families": separated_families,
        "separated_counts": list(separated_counts),
        "skipped_requests": skipped,
        "rule_under_test": "Named and anonymous COMPONENT ID records are complete packets; selected middle packets are finalized by dropping one trailing 00 or 08 byte before the FF stream terminator.",
        "donor_counts": {
            "single": single.counts(),
            "five_x": five.counts(),
        },
        "finalizable_donor_counts": {
            "single": {
                family: sum(1 for group in groups if is_finalizable(group))
                for family, groups in sorted(single.groups_by_family.items())
            },
            "five_x": {
                family: sum(1 for group in groups if is_finalizable(group))
                for family, groups in sorted(five.groups_by_family.items())
            },
        },
        "source_donors": {
            "single": str(SINGLE_DONOR.relative_to(ROOT)),
            "five_x": str(FIVE_X_DONOR.relative_to(ROOT)),
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
    print(
        json.dumps(
            {
                "out_dir": str(OUT_DIR),
                "zip": str(ZIP_OUT),
                "cases": summary["case_count"],
                "case_errors": {case["case_id"]: case["errors"] for case in summary["cases"] if case["errors"]},
                "zip_sha256": sha256_file(ZIP_OUT),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
