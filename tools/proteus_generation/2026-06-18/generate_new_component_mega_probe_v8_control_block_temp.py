"""Generate V8 mixed-control block probes for SWITCH/POT-HG.

V7 user result:
- outputs opened, but mixed M01/M02/M07 still displayed the old uncorrect
  first SWITCH and POT-HG controls;
- byte inventory shows the first SWITCH block has 21 records and the first
  POT-HG block has 20 records.

Rules under test:
- keep the V6 accepted 00 08 chunk header;
- keep accepted FUSE/PNP/VPULSE selectors and full donor ROOT.CDB;
- for mixed outputs only, avoid the first complete SWITCH/POT-HG donor block.
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
from src.proteusgen.component_placer import (
    build_component_placer_cdb_subset,
    package_ref as cdb_package_ref,
    parse_component_placer_cdb,
)


DONOR_DIR = ROOT / "proteus_ic/donors/manual_downloads_20260618/new_component_mega"
SINGLE_DONOR = DONOR_DIR / "new_components_single_mega.pdsprj"
FIVE_X_DONOR = DONOR_DIR / "new_components_5x_mega.pdsprj"

OUT_DIR = ROOT / "experiments/new_component_mega_probe_v8_control_block_temp_2026_06_19"
ZIP_OUT = ROOT / "experiments/NEW_COMPONENT_MEGA_PROBE_V8_CONTROL_BLOCK_TEMP_2026_06_19.zip"
CONTROL_DONOR_DIR = ROOT / "proteus_ic/donors/manual_downloads_20260619/control_components"
SWITCH_CONTROL_DONOR = CONTROL_DONOR_DIR / "switch.pdsprj"
POT_CONTROL_DONOR = CONTROL_DONOR_DIR / "1pot hg.pdsprj"
MAIN_MEGA_DIR = ROOT / "proteus_ic/donors/main_mega_20260618"
MAIN_SOURCE_DONOR = (
    MAIN_MEGA_DIR
    / "15xsemimega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistorandsources.pdsprj"
)
MAIN_NO_SOURCE_DONOR = (
    MAIN_MEGA_DIR
    / "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)

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


def select_family_window(
    state: DonorState,
    family: str,
    count: int,
    *,
    offset: int = 0,
    skip_first_each_block: int | None = None,
) -> tuple[BodyGroup, ...]:
    available = [group for group in state.groups_by_family.get(family, []) if is_finalizable(group)]
    if skip_first_each_block is not None:
        available = [group for index, group in enumerate(available) if index % skip_first_each_block != 0]
    if offset:
        available = available[offset:]
    if len(available) < count:
        raise ValueError(
            f"{state.path.name}: need {count} {family} groups after offset={offset} "
            f"skip_first_each_block={skip_first_each_block}, found {len(available)}."
        )
    return tuple(available[:count])


def select_family_windows(
    state: DonorState,
    specs: dict[str, dict[str, int | None]],
) -> tuple[BodyGroup, ...]:
    selected: list[BodyGroup] = []
    for family, options in specs.items():
        selected.extend(
            select_family_window(
                state,
                family,
                int(options["count"]),
                offset=int(options.get("offset") or 0),
                skip_first_each_block=(
                    int(options["skip_first_each_block"])
                    if options.get("skip_first_each_block") is not None
                    else None
                ),
            )
        )
    return tuple(sorted(selected, key=lambda item: item.start))


def ref_sort_key(ref: str) -> tuple[str, int, str]:
    match = re.match(r"^([A-Z]+)(\d+)$", ref)
    if match:
        return (match.group(1), int(match.group(2)), "")
    return (ref.rstrip("0123456789"), 10**9, ref)


def cdb_package_set(state: DonorState) -> set[str]:
    parsed = parse_component_placer_cdb(state.cdb)
    refs = {cdb_package_ref(row.ref) for row in parsed.pin_rows}
    refs.update(cdb_package_ref(row.ref) for row in parsed.property_rows)
    return {ref for ref in refs if ref}


def cdb_backed_groups(
    state: DonorState,
    family: str,
    *,
    require_zero_tail: bool = False,
    skip_refs: set[str] | None = None,
) -> list[BodyGroup]:
    backed = cdb_package_set(state)
    skip = skip_refs or set()
    groups: list[BodyGroup] = []
    for group in state.groups_by_family.get(family, []):
        if not is_finalizable(group):
            continue
        if group.key in skip:
            continue
        if group.key not in backed:
            continue
        if require_zero_tail and not group.data.endswith(b"\x00"):
            continue
        groups.append(group)
    return sorted(groups, key=lambda item: ref_sort_key(item.key))


def select_cdb_backed(
    state: DonorState,
    family: str,
    count: int,
    *,
    offset: int = 0,
    require_zero_tail: bool = False,
    skip_refs: set[str] | None = None,
) -> tuple[BodyGroup, ...]:
    groups = cdb_backed_groups(state, family, require_zero_tail=require_zero_tail, skip_refs=skip_refs)
    if offset:
        groups = groups[offset:]
    if len(groups) < count:
        raise ValueError(
            f"{state.path.name}: need {count} CDB-backed {family} groups after offset={offset}, "
            f"found {len(groups)}."
        )
    return tuple(sorted(groups[:count], key=lambda item: item.start))


def selected_package_refs(selected: tuple[BodyGroup, ...]) -> tuple[str, ...]:
    refs: list[str] = []
    for group in selected:
        for ref in group.refs or (group.key,):
            package = package_ref(ref)
            if package.startswith("ANON"):
                continue
            if package not in refs:
                refs.append(package)
    return tuple(refs)


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


def object_chunk_for(selected: tuple[BodyGroup, ...], *, prefix: bytes = b"\x00\x00") -> tuple[bytes, dict[str, object]]:
    if prefix not in (b"\x00\x00", b"\x00\x08"):
        raise ValueError(f"Unsupported object chunk prefix: {prefix.hex()}")
    if not selected:
        return prefix + b"\xff", {"last_group": None, "trimmed_last_byte": False, "chunk_prefix": prefix.hex()}
    ordered = tuple(sorted(selected, key=lambda item: item.start))
    final_data, final_meta = finalize_last_group(ordered[-1])
    return (
        prefix + b"".join(group.data for group in ordered[:-1]) + final_data + b"\xff",
        {
            "last_group": ordered[-1].as_dict(),
            "selected_group_count": len(ordered),
            "chunk_prefix": prefix.hex(),
            **final_meta,
        },
    )


def object_chunk_for_keep_final(selected: tuple[BodyGroup, ...]) -> tuple[bytes, dict[str, object]]:
    if not selected:
        return b"\x00\x00\xff", {"last_group": None, "kept_final_byte": False}
    ordered = tuple(sorted(selected, key=lambda item: item.start))
    return (
        b"\x00\x00" + b"".join(group.data for group in ordered) + b"\xff",
        {
            "last_group": ordered[-1].as_dict(),
            "selected_group_count": len(ordered),
            "kept_final_byte": True,
            "kept_byte": f"{ordered[-1].data[-1]:02x}",
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
    return describe_case(case_id, output, state, state.chunk, state.cdb, description, {"copy_exact": True})


def copy_raw_case(case_id: str, donor_path: Path, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(donor_path, output)
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = read_internal_file(output, "ROOT.CDB")
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(donor_path.relative_to(ROOT)),
        "description": description,
        "copy_exact": True,
        "object_chunk_size": len(chunk),
        "object_chunk_head": chunk[:16].hex(),
        "object_chunk_tail": chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(chunk),
        "root_cdb_size": len(cdb),
        "root_cdb_sha256": sha256_bytes(cdb),
        "marker_counts": marker_counts(chunk),
        "errors": [],
    }


def rebuild_raw_chunk_case(case_id: str, donor_path: Path, description: str) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    donor_dsn = read_internal_file(donor_path, "ROOT.DSN")
    donor_cdb = read_internal_file(donor_path, "ROOT.CDB")
    chunk = _extract_object_chunk(donor_dsn)
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, chunk)
    write_project_from_parts(donor_path, output, {"ROOT.DSN": dsn, "ROOT.CDB": donor_cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    final_cdb = read_internal_file(output, "ROOT.CDB")
    errors: list[str] = []
    if final_chunk != chunk:
        errors.append("final object chunk differs from requested raw donor chunk")
    if final_cdb != donor_cdb:
        errors.append("ROOT.CDB differs from donor")
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "donor": str(donor_path.relative_to(ROOT)),
        "description": description,
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "root_cdb_size": len(final_cdb),
        "root_cdb_sha256": sha256_bytes(final_cdb),
        "marker_counts": marker_counts(final_chunk),
        "errors": errors,
        "pointers": pointers,
        "raw_rebuild": True,
    }


def write_case(
    case_id: str,
    state: DonorState,
    selected: tuple[BodyGroup, ...],
    description: str,
    *,
    force_chunk: bytes | None = None,
    prune_cdb: bool = False,
    keep_final_byte: bool = False,
    chunk_prefix: bytes = b"\x00\x00",
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    if force_chunk is not None:
        object_chunk, finalization = force_chunk, {"forced_chunk": True}
    elif keep_final_byte:
        object_chunk, finalization = object_chunk_for_keep_final(selected)
    else:
        object_chunk, finalization = object_chunk_for(selected, prefix=chunk_prefix)
    keep_refs = selected_package_refs(selected)
    if prune_cdb and force_chunk is None:
        parsed_cdb = parse_component_placer_cdb(state.cdb)
        cdb = build_component_placer_cdb_subset(parsed_cdb, keep_refs)
        cdb_policy = "pruned_to_selected_package_refs"
    else:
        cdb = state.cdb
        cdb_policy = "full_donor_cdb_v4_after_v3_rejection"
    dsn, pointers = build_dsn(state.dsn, state.dsn, object_chunk)
    write_project_from_parts(state.path, output, {"ROOT.DSN": dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    merged_extra = {
        "pointers": pointers,
        "finalization": finalization,
        "cdb_policy": cdb_policy,
        "cdb_keep_refs": list(keep_refs),
    }
    if extra:
        merged_extra.update(extra)
    return describe_case(case_id, output, state, object_chunk, cdb, description, merged_extra)


def describe_case(
    case_id: str,
    output: Path,
    state: DonorState,
    requested_chunk: bytes,
    requested_cdb: bytes,
    description: str,
    extra: dict[str, object],
) -> dict[str, object]:
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    final_cdb = read_internal_file(output, "ROOT.CDB")
    errors: list[str] = []
    if final_chunk != requested_chunk:
        errors.append("final object chunk differs from requested chunk")
    if final_cdb != requested_cdb:
        errors.append("ROOT.CDB differs from requested CDB")
    if not (final_chunk.startswith(b"\x00\x00") or final_chunk.startswith(b"\x00\x08")):
        errors.append(f"object chunk does not start with accepted prefix 00 00/00 08: {final_chunk[:8].hex()}")
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
    cdb_backed_families = {
        family
        for family in separated_families
        if family not in {"FUSE", "SWITCH"}
    }

    donor_cdb_refs = cdb_package_set(five)

    def fixed_fuse(count: int) -> tuple[BodyGroup, ...]:
        groups = [
            group
            for group in five.groups_by_family.get("FUSE", [])
            if len(group.data) == 338 and group.data.endswith(b"\x08")
        ]
        if len(groups) < count:
            raise ValueError(f"Need {count} strict 338-byte FUSE groups, found {len(groups)}.")
        return tuple(sorted(groups[:count], key=lambda item: item.start))

    def fixed_pothg(
        count: int,
        *,
        offset: int = 0,
        skip_first_each_block: int | None = None,
    ) -> tuple[BodyGroup, ...]:
        groups = [
            group
            for group in five.groups_by_family.get("POT-HG", [])
            if group.key in donor_cdb_refs and len(group.data) in (431, 432) and group.data.endswith(b"\x08")
        ]
        if skip_first_each_block is not None:
            groups = [group for index, group in enumerate(groups) if index % skip_first_each_block != 0]
        if offset:
            groups = groups[offset:]
        if len(groups) < count:
            raise ValueError(
                f"Need {count} complete POT-HG groups after offset={offset} "
                f"skip_first_each_block={skip_first_each_block}, found {len(groups)}."
            )
        return tuple(sorted(groups[:count], key=lambda item: item.start))

    def fixed_pnp(count: int) -> tuple[BodyGroup, ...]:
        groups = [
            group
            for group in five.groups_by_family.get("PNP", [])
            if group.key in donor_cdb_refs and len(group.data) >= 342 and group.data.endswith(b"\x00")
        ]
        if len(groups) < count:
            raise ValueError(f"Need {count} complete CDB-backed PNP groups, found {len(groups)}.")
        return tuple(sorted(groups[:count], key=lambda item: item.start))

    def safe_select(family: str, count: int) -> tuple[BodyGroup, ...]:
        if family == "FUSE":
            return fixed_fuse(count)
        if family == "POT-HG":
            return fixed_pothg(count)
        if family == "SWITCH":
            return select_family_window(five, family, count)
        if family == "BRIDGE" and count > 7:
            # The first bridge donor block has a bad-object boundary after BR7.
            return select_cdb_backed(five, family, count, offset=14)
        if family == "PNP":
            return fixed_pnp(count)
        if family in cdb_backed_families:
            return select_cdb_backed(five, family, count)
        return select_groups(five, {family: count})

    def safe_select_many(counts: dict[str, int]) -> tuple[BodyGroup, ...]:
        selected: list[BodyGroup] = []
        for family, count in counts.items():
            selected.extend(safe_select(family, count))
        return tuple(sorted(selected, key=lambda item: item.start))

    def mixed_select_block2(family: str, count: int) -> tuple[BodyGroup, ...]:
        if family == "SWITCH":
            return select_family_window(five, family, count, offset=21)
        if family == "POT-HG":
            return fixed_pothg(count, offset=20)
        return safe_select(family, count)

    def mixed_select_skip_each_control_block(family: str, count: int) -> tuple[BodyGroup, ...]:
        if family == "SWITCH":
            return select_family_window(five, family, count, skip_first_each_block=21)
        if family == "POT-HG":
            return fixed_pothg(count, skip_first_each_block=20)
        return safe_select(family, count)

    def mixed_select_many(counts: dict[str, int], selector) -> tuple[BodyGroup, ...]:
        selected: list[BodyGroup] = []
        for family, count in counts.items():
            selected.extend(selector(family, count))
        return tuple(sorted(selected, key=lambda item: item.start))

    cases: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    focused_specs: list[tuple[str, tuple[BodyGroup, ...], str, dict[str, object]]] = []

    mixed_specs = [
        (
            "M01_CONTROL_ONE_EACH",
            {family: 1 for family in separated_families if family != "NE555" or finalizable_count(five, family) >= 1},
            "Mixed M01 using accepted selectors; control selectors are varied per V8 case.",
        ),
        (
            "M02_CONTROL_FIVE_EACH",
            {family: 5 for family in separated_families if family != "NE555" or finalizable_count(five, family) >= 5},
            "Mixed M02 using accepted selectors; control selectors are varied per V8 case.",
        ),
        (
            "M07_CONTROL_LARGE_STRESS",
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
            "Mixed M07 using accepted selectors; control selectors are varied per V8 case.",
        ),
    ]
    for case_id, counts, description in mixed_specs:
        focused_specs.extend(
            [
                (
                    f"B{case_id[1:]}_BLOCK2",
                    mixed_select_many(counts, mixed_select_block2),
                    f"{description} V8 block2 variant skips the first complete SWITCH/POT-HG donor block.",
                    {
                        "requested_counts": counts,
                        "selector": "safe_mixed_cdb_backed_control_block2",
                        "control_offsets": {"SWITCH": 21, "POT-HG": 20},
                        "chunk_prefix": "0008",
                    },
                ),
                (
                    f"E{case_id[1:]}_SKIP_EACH_BLOCK",
                    mixed_select_many(counts, mixed_select_skip_each_control_block),
                    f"{description} V8 skip-each-block variant removes the first SWITCH/POT-HG packet from every donor block.",
                    {
                        "requested_counts": counts,
                        "selector": "safe_mixed_cdb_backed_skip_first_control_in_each_block",
                        "control_skip_first_each_block": {"SWITCH": 21, "POT-HG": 20},
                        "chunk_prefix": "0008",
                    },
                ),
            ]
        )

    for case_id, selected, description, extra in focused_specs:
        case_extra = dict(extra)
        keep_final_byte = bool(case_extra.pop("keep_final_byte", False))
        prefix_text = str(case_extra.pop("chunk_prefix", "0000"))
        chunk_prefix = bytes.fromhex(prefix_text)
        cases.append(write_case(case_id, five, selected, description, keep_final_byte=keep_final_byte, chunk_prefix=chunk_prefix, extra=case_extra))

    return {
        "experiment": "new_component_mega_probe_v8_control_block_temp_2026_06_19",
        "purpose": "Mixed-case correction for V7: avoid the first complete SWITCH/POT-HG donor block while preserving accepted control-header and family selectors.",
        "separated_families": separated_families,
        "skipped_requests": skipped,
        "rule_under_test": "For mixed outputs, use full donor ROOT.CDB, accepted trim rules, a 00 08 object chunk header, and block-aware SWITCH/POT-HG packet selection.",
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
            "switch_control": str(SWITCH_CONTROL_DONOR.relative_to(ROOT)),
            "pot_hg_control": str(POT_CONTROL_DONOR.relative_to(ROOT)),
            "main_source_reference_only": str(MAIN_SOURCE_DONOR.relative_to(ROOT)),
            "main_no_source_reference_only": str(MAIN_NO_SOURCE_DONOR.relative_to(ROOT)),
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
