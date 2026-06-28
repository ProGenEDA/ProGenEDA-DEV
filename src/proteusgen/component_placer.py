"""Removal-only component placer planning, validation, and generation.

This module is intentionally conservative. It does not clone component records.
It selects trusted donors that already contain enough real component packets,
then either builds a deletion/CDB cleanup plan or emits a project from complete
donor packets.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from .cdb import (
    COUNT_OFFSET,
    PIN_ROW_FOOTER_SIZE,
    PIN_ROW_HEADER_SIZE,
    CdbPinRow,
    CdbPropertyRow,
    _read_lp_ascii,
    _read_u32,
    _skip_lp_ascii,
    package_ref,
    parse_cdb,
)
from .ic_native import NativeRegistry
from .pdsprj import read_internal_file, write_project_from_parts
from .resistor_v9 import _extract_object_chunk, build_dsn
from .bidirectional import build_bidir_record, load_production_templates
from .component_pipeline import (
    build_component_pipeline_metadata,
    manifest_path_for_output,
    pipeline_errors,
)
from .component_value_changer import (
    apply_value_mutations_to_groups,
    patch_cdb_property_rows,
)
from .component_beautifier import (
    DEFAULT_HIDDEN_COORDINATE_MODE,
    D20_SMALL_COORD_DX,
    D20_SMALL_COORD_DY,
    HIDDEN_PACKET_START,
    VISIBLE_LAYOUT_COLUMNS,
    VISIBLE_LAYOUT_MARGIN_X,
    VISIBLE_LAYOUT_MARGIN_Y,
    VISIBLE_LAYOUT_ORIGIN_X,
    VISIBLE_LAYOUT_ORIGIN_Y,
    VISIBLE_LAYOUT_SHELF_WIDTH,
    VISIBLE_LAYOUT_SLOT_X,
    VISIBLE_LAYOUT_SLOT_Y,
    coordinate_bbox,
    hide_packet,
    layout_coordinate_pairs,
    translate_packet_by_delta,
    translate_packet_to_position,
)
from .templates import FixtureRegistry, repository_root

TRUSTED_DONOR_MANIFEST_PATH = Path("proteus_ic/registry/trusted_donor_manifest.json")
HISTORY_RULES_PATH = Path("knowledge/validator_history_rules.json")
SCHEMA_VERSION = "component-placer-plan/v0.1"

RECORD_START_RE = re.compile(
    rb"\xff([\x02-\x08])("
    rb"(?:U\d+(?::[A-Z])?)|(?:R\d+)|(?:C\d+)|(?:L\d+)|(?:Q\d+)|(?:D\d+)|"
    rb"(?:V\d+)|(?:I\d+)|(?:BR\d+)|(?:FU\d+)|(?:FUSE)|(?:RV\d+)|(?:TR\d+)"
    rb")"
)
ANON_RECORD_START_RE = re.compile(rb"\xff\x00.{30,80}?Default Font\x00COMPONENT ID", re.S)
CDB_PROPERTY_REF_RE = re.compile(r"^[A-Z]+[0-9]+(?::[A-Z])?$")
RESERVED_NETS = {"V0", "G0", "VCC", "GND", "+5V", "0"}
FORBIDDEN_GENERATION_MODES = {
    "clone",
    "cloning",
    "synthetic",
    "render_from_empty",
    "copy_full_cdb_after_delete",
}
NEW_COMPONENT_MEGA_DONOR = Path("proteus_ic/donors/manual_downloads_20260618/new_component_mega/new_components_5x_mega.pdsprj")
MAIN_MEGA_NO_SOURCE_DONOR = Path(
    "proteus_ic/donors/main_mega_20260618/"
    "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)
MAIN_MEGA_SOURCE_DONOR = Path(
    "proteus_ic/donors/main_mega_20260618/"
    "15xsemimega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistorandsources.pdsprj"
)
CONTROL_STRATEGIES = ("accepted", "switch_precedence", "hidden_dummy_switch", "hidden_dummy_control")
OBJECT_CHUNK_PREFIX = b"\x00\x08"
NO_TERMINAL_OBJECT_CHUNK_PREFIX = b"\x00\x00"
UNSAFE_NONDISPLAY_FINAL_FAMILIES = {"LED-RED"}
PREFERRED_NONDISPLAY_FINAL_FAMILIES = ("RESISTOR",)
COMPLETE_PACKAGE_REF_COUNTS = {
    "74HC00": 4,
    "74HC02": 4,
    "74HC08": 4,
    "74HC32": 4,
    "74HC86": 4,
    "74HC266": 4,
    "74HC04": 6,
}
DONOR_COMPONENT_OFFSET_DEFAULTS = {
    NEW_COMPONENT_MEGA_DONOR.as_posix(): {
        # User Proteus tests on 2026-06-20:
        #   74HC00 offsets 0 and 4 fail/crash, offsets 8 and 12 open/simulate.
        # Keep explicit component_offsets as diagnostics, but production default
        # must skip the poisoned early HC00 donor packets.
        "74HC00": 8,
    }
}
HIDDEN_SWITCH_DX = 254_000_000
HIDDEN_SWITCH_DY = 254_000_000
SWITCH_X_COORD_OFFSETS = (2, 68, 143, 208, 359)
SWITCH_Y_COORD_OFFSETS = (6, 72, 147, 212, 363)
POT_X_COORD_RELATIVE_OFFSETS = (0, 68, 143, 208, 388)
POT_Y_COORD_RELATIVE_OFFSETS = (4, 72, 147, 212, 392)
DISPLAY_RECORD_START = b"\x00\x08\xff\x00"
EXTRA_GENERATION_MARKERS = (
    "7SEG-COM-CAT-BLUE",
    "7SEG-COM-CAT-RED",
    "7SEG-COM-AN-BLUE",
    "TRAN-2P2S",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "40EPS08",
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
    "FUSE",
    "BRIDGE",
    "OPAMP",
    "SWITCH",
    "NMOSFET",
    "VPULSE",
)
GENERIC_FAMILY_MARKERS = {"DIODE", "NMOSFET", "OPAMP"}
DISPLAY_FAMILIES = {"7SEG-COM-AN-BLUE", "7SEG-COM-CAT-BLUE"}
TERMINAL_FAMILIES = {"TERMINAL", "GROUND", "POWER"}
CONTROL_PREFIX_FAMILIES = {"SWITCH", "POT-HG"}
SOURCE_CLEAN_MIN_LENGTHS = {
    "CSOURCE": 344,
    "VPULSE": 347,
    "VSOURCE": 343,
}
SWITCH_PACKET_LENGTH = 393
NEW_COMPONENT_ONLY_FAMILIES = {
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "2N3904",
    "2N4401",
    "2N7000",
    "BRIDGE",
    "BS170",
    "FUSE",
    "IRDIODE",
    "LED-RED",
    "LM317T",
    "NMOSFET",
    "OPAMP",
    "POT-HG",
    "SWITCH",
    "TRAN-2P2S",
    "VPULSE",
}
COMPONENT_PLACER_EXTRA_ALIASES = {
    "7SEGCOMA": "7SEG-COM-AN-BLUE",
    "7SEGCOMANODE": "7SEG-COM-AN-BLUE",
    "7SEGCOMMONANODE": "7SEG-COM-AN-BLUE",
    "7SEGCOMAN": "7SEG-COM-AN-BLUE",
    "7SEGCOMANBLUE": "7SEG-COM-AN-BLUE",
    "7SEGCOMK": "7SEG-COM-CAT-BLUE",
    "7SEGCOMCATHODE": "7SEG-COM-CAT-BLUE",
    "7SEGCOMMONCATHODE": "7SEG-COM-CAT-BLUE",
    "7SEGCOMCAT": "7SEG-COM-CAT-BLUE",
    "7SEGCOMCATBLUE": "7SEG-COM-CAT-BLUE",
    "7SEGCOMANC": "7SEG-COM-AN-BLUE",
    "7SEGCOMCATRED": "7SEG-COM-CAT-BLUE",
    "7SEGCOMCATH": "7SEG-COM-CAT-BLUE",
    "7SEG-COM-CAT": "7SEG-COM-CAT-BLUE",
    "7SEG-COM-ANC": "7SEG-COM-AN-BLUE",
    "7SEG-COM-ANODE": "7SEG-COM-AN-BLUE",
    "7SEG-COM-CATHODE": "7SEG-COM-CAT-BLUE",
    "TRANSFORMER": "TRAN-2P2S",
    "TRAN": "TRAN-2P2S",
    "TRAN2P2S": "TRAN-2P2S",
    "TRAN-2P2S": "TRAN-2P2S",
    "TRAN2P2S5CV1": "TRAN-2P2S",
    "TRAN-2P2S5CV1": "TRAN-2P2S",
    "POTHG": "POT-HG",
    "POT": "POT-HG",
    "POTENTIOMETER": "POT-HG",
    "RES": "RESISTOR",
    "R": "RESISTOR",
    "LED": "LED-RED",
    "VDC": "VSOURCE",
    "DCV": "VSOURCE",
    "DCVOLTAGE": "VSOURCE",
    "DCC": "CSOURCE",
    "DCCURRENT": "CSOURCE",
    "VSIN": "VSINE",
    "VSINE": "VSINE",
    "ACV": "VSINE",
    "PULSE": "VPULSE",
    "VPULSE": "VPULSE",
    "BZX55C5": "BZX55C5V1",
    "BZX55C5V1": "BZX55C5V1",
    "BZX79C5": "BZX79C5V1",
    "BZX79C5V1": "BZX79C5V1",
    "BZX88C": "BZY88C",
    "1N60": "1N6000B",
    "NMOS": "NMOSFET",
    "LM317": "LM317T",
    "BRIDGERECTIFIER": "BRIDGE",
    "OPAMP": "OPAMP",
    "OP_AMP": "OPAMP",
    "TER": "TERMINAL",
    "BIDIR": "TERMINAL",
    "BIDER": "TERMINAL",
    "GND": "GROUND",
    "VCC": "POWER",
}


@dataclass(frozen=True)
class ComponentPacket:
    family: str
    package: str
    refs: tuple[str, ...]
    record_count: int
    raw_start: int
    raw_end: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "package": self.package,
            "refs": list(self.refs),
            "record_count": self.record_count,
            "raw_start": self.raw_start,
            "raw_end": self.raw_end,
        }


@dataclass(frozen=True)
class TrustedDonor:
    donor_id: str
    path: Path
    counts: dict[str, int]
    source: str
    priority: int = 100
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "donor_id": self.donor_id,
            "path": str(self.path),
            "counts": dict(sorted(self.counts.items())),
            "source": self.source,
            "priority": self.priority,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass(frozen=True)
class ComponentPlacerReport:
    errors: tuple[ValidationIssue, ...]
    warnings: tuple[ValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


@dataclass(frozen=True)
class ComponentPlacerCdb:
    prefix: bytes
    count: int
    pin_rows: tuple[CdbPinRow, ...]
    between_sections: bytes
    property_rows: tuple[CdbPropertyRow, ...]
    suffix: bytes
    property_header_size: int

    def pin_package_refs(self) -> tuple[str, ...]:
        return tuple(package_ref(row.ref) for row in self.pin_rows)

    def property_package_refs(self) -> tuple[str, ...]:
        return tuple(package_ref(row.ref) for row in self.property_rows)

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "pin_row_count": len(self.pin_rows),
            "property_row_count": len(self.property_rows),
            "between_sections_size": len(self.between_sections),
            "suffix_size": len(self.suffix),
            "property_header_size": self.property_header_size,
        }


@dataclass(frozen=True)
class DonorSelection:
    request: dict[str, int]
    donor: TrustedDonor
    score: tuple[int, int, int, int, str]
    inspected_counts: dict[str, int]
    warnings: tuple[ValidationIssue, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "request": dict(sorted(self.request.items())),
            "donor": self.donor.as_dict(),
            "score": list(self.score),
            "inspected_counts": dict(sorted(self.inspected_counts.items())),
            "warnings": [issue.as_dict() for issue in self.warnings],
            "requires_cloning": False,
        }


@dataclass(frozen=True)
class DeletionPlan:
    selection: DonorSelection
    keep_packages: dict[str, tuple[str, ...]]
    delete_packages: dict[str, tuple[str, ...]]
    cdb_package_refs_to_keep: tuple[str, ...]
    cdb_package_refs_to_delete: tuple[str, ...]
    device_section_policy: str
    cdb_policy: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA_VERSION,
            "selection": self.selection.as_dict(),
            "keep_packages": {key: list(value) for key, value in sorted(self.keep_packages.items())},
            "delete_packages": {key: list(value) for key, value in sorted(self.delete_packages.items())},
            "cdb_package_refs_to_keep": list(self.cdb_package_refs_to_keep),
            "cdb_package_refs_to_delete": list(self.cdb_package_refs_to_delete),
            "device_section_policy": self.device_section_policy,
            "cdb_policy": self.cdb_policy,
        }


@dataclass(frozen=True)
class RawComponentGroup:
    key: str
    family: str
    start: int
    end: int
    refs: tuple[str, ...]
    data: bytes
    source_is_final: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "family": self.family,
            "start": self.start,
            "end": self.end,
            "refs": list(self.refs),
            "size": len(self.data),
            "source_is_final": self.source_is_final,
            "tail": self.data[-8:].hex(),
        }


@dataclass(frozen=True)
class RawPlacementResult:
    output: Path
    donor: Path
    request: dict[str, int]
    control_strategy: str
    selected_groups: tuple[RawComponentGroup, ...]
    hidden_groups: tuple[RawComponentGroup, ...]
    object_chunk_size: int
    object_chunk_head: str
    object_chunk_tail: str
    cdb_policy: str
    errors: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    value_plan: dict[str, Any] = field(default_factory=dict)
    wiring_plan: dict[str, Any] = field(default_factory=dict)
    layout_plan: dict[str, Any] = field(default_factory=dict)
    hidden_dummy_controls: dict[str, Any] = field(default_factory=dict)
    validation_reports: dict[str, Any] = field(default_factory=dict)
    manifest_path: Path | None = None

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        root = repository_root()
        def render_path(path: Path) -> str:
            try:
                return str(path.relative_to(root) if path.is_absolute() else path)
            except ValueError:
                return str(path)

        return {
            "valid": self.valid,
            "output": render_path(self.output),
            "donor": render_path(self.donor),
            "request": dict(sorted(self.request.items())),
            "control_strategy": self.control_strategy,
            "selected_group_count": len(self.selected_groups),
            "hidden_group_count": len(self.hidden_groups),
            "selected_groups": [group.as_dict() for group in self.selected_groups],
            "hidden_groups": [group.as_dict() for group in self.hidden_groups],
            "object_chunk_size": self.object_chunk_size,
            "object_chunk_head": self.object_chunk_head,
            "object_chunk_tail": self.object_chunk_tail,
            "cdb_policy": self.cdb_policy,
            "manifest": render_path(self.manifest_path) if self.manifest_path else None,
            "value_plan": self.value_plan,
            "wiring_plan": self.wiring_plan,
            "layout_plan": self.layout_plan,
            "hidden_dummy_controls": self.hidden_dummy_controls,
            "validation_reports": self.validation_reports,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


class ComponentPlacerBlocked(Exception):
    def __init__(self, report: ComponentPlacerReport) -> None:
        super().__init__("Component placer request is not safe to plan.")
        self.report = report


def _token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _repo_path(path: str | Path) -> Path:
    raw = Path(path)
    return raw if raw.is_absolute() else repository_root() / raw


def _payload_donor_spec(payload: Any) -> Any | None:
    if not isinstance(payload, dict):
        return None
    for key in ("donor", "donor_path", "placement_donor"):
        if payload.get(key):
            return payload[key]
    return None


def _resolve_explicit_donor(spec: Any) -> Path:
    raw_spec = spec
    if isinstance(spec, dict):
        raw_spec = spec.get("path") or spec.get("id") or spec.get("donor_id")
    if not raw_spec:
        raise ValueError("Explicit donor must be a donor path, manifest id, or object with path/id.")

    raw = str(raw_spec)
    path = _repo_path(raw)
    if path.exists():
        return path

    donors, _aliases = load_trusted_donors()
    matches = [
        donor
        for donor in donors
        if raw in {donor.donor_id, str(donor.path), donor.path.name, donor.path.stem}
    ]
    if len(matches) == 1:
        return _repo_path(matches[0].path)
    if len(matches) > 1:
        raise ValueError(f"Explicit donor {raw!r} is ambiguous: {[donor.donor_id for donor in matches]}")
    raise ValueError(f"Explicit donor {raw!r} was not found as a file path or trusted manifest id.")


def _inspect_donor_counts_for_selection(donor_path: Path, markers: Iterable[str] | None = None) -> dict[str, int]:
    chunk = _extract_object_chunk(read_internal_file(donor_path, "ROOT.DSN"))
    groups = _raw_groups_from_chunk(chunk, markers or _generation_markers())
    counts = {family: len(values) for family, values in groups.items()}
    try:
        counts.update({family: len(records) for family, records in _display_records_from_chunk(chunk).items()})
    except Exception:
        pass
    return dict(sorted(counts.items()))


def _sha_path_fragment(path: Path) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "_", path.stem).strip("_")[:64] or "donor"
    return stem


def _manifest_aliases(data: dict[str, Any]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical, values in data.get("aliases", {}).items():
        aliases[_token(canonical)] = canonical
        for value in values:
            aliases[_token(str(value))] = canonical
    return aliases


def normalize_component(value: str, aliases: dict[str, str] | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Component part must be a non-empty string.")
    alias_map = aliases or load_component_aliases()
    token = _token(value)
    if token in alias_map:
        return alias_map[token]
    return value.strip().upper()


def normalize_request(payload: Any, aliases: dict[str, str] | None = None) -> dict[str, int]:
    alias_map = aliases or load_component_aliases()
    raw: Any
    if isinstance(payload, dict) and "components" in payload:
        raw = payload["components"]
    elif isinstance(payload, dict) and "request" in payload:
        raw = payload["request"]
    else:
        raw = payload

    counts: Counter[str] = Counter()
    if isinstance(raw, dict):
        for part, count in raw.items():
            normalized = normalize_component(str(part), alias_map)
            if isinstance(count, dict):
                amount = int(count.get("count", 1))
            else:
                amount = int(count)
            if amount <= 0:
                raise ValueError(f"Requested count for {part!r} must be positive.")
            counts[normalized] += amount
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                normalized = normalize_component(item, alias_map)
                counts[normalized] += 1
            elif isinstance(item, dict):
                part = item.get("part") or item.get("type") or item.get("family")
                if not part:
                    raise ValueError("Component list entries must include part/type/family.")
                amount = int(item.get("count", 1))
                if amount <= 0:
                    raise ValueError(f"Requested count for {part!r} must be positive.")
                counts[normalize_component(str(part), alias_map)] += amount
            else:
                raise ValueError("Component request list must contain strings or objects.")
    else:
        raise ValueError("Component placer request must be a mapping or component list.")
    return dict(sorted(counts.items()))


def load_component_aliases(path: str | Path | None = None) -> dict[str, str]:
    manifest = json.loads(_repo_path(path or TRUSTED_DONOR_MANIFEST_PATH).read_text(encoding="utf-8"))
    aliases = _manifest_aliases(manifest)
    if manifest.get("include_native_registry_donors", False):
        registry = NativeRegistry.load()
        for key, component in registry.components.items():
            canonical = component.marker if key == "74HC47" or component.marker in DISPLAY_FAMILIES else key
            aliases[_token(key)] = canonical
            aliases[_token(component.marker)] = canonical
            for alias in component.aliases:
                aliases[_token(alias)] = canonical
    aliases.update(COMPONENT_PLACER_EXTRA_ALIASES)
    return aliases


def _known_markers_from_manifest(data: dict[str, Any]) -> tuple[str, ...]:
    markers = set(data.get("component_markers", []))
    if data.get("include_native_registry_donors", False):
        registry = NativeRegistry.load()
        for key, component in registry.components.items():
            markers.add(component.marker if key == "74HC47" else key)
            markers.add(component.marker)
    return tuple(sorted(markers, key=lambda marker: (-len(marker), marker)))


def inspect_component_packets(project: str | Path, markers: Iterable[str] | None = None) -> dict[str, list[ComponentPacket]]:
    marker_list = tuple(
        sorted(
            set(markers or load_component_aliases().values()) - TERMINAL_FAMILIES,
            key=lambda marker: (-len(marker), marker),
        )
    )
    dsn = read_internal_file(_repo_path(project), "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    starts = [(match.start(), match.group(2).decode("ascii")) for match in RECORD_START_RE.finditer(chunk)]
    by_package: dict[str, list[tuple[str, str, int, int]]] = defaultdict(list)
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else max(0, len(chunk) - 1)
        raw = chunk[start:end]
        hits = [marker for marker in marker_list if marker.encode("ascii") in raw]
        if not hits:
            continue
        family = hits[0]
        by_package[package_ref(ref)].append((ref, family, start, end))

    packets: dict[str, list[ComponentPacket]] = defaultdict(list)
    for package, records in by_package.items():
        families = Counter(family for _ref, family, _start, _end in records)
        if not families:
            continue
        family = families.most_common(1)[0][0]
        refs = tuple(ref for ref, _family, _start, _end in records)
        packets[family].append(
            ComponentPacket(
                family=family,
                package=package,
                refs=refs,
                record_count=len(records),
                raw_start=min(start for _ref, _family, start, _end in records),
                raw_end=max(end for _ref, _family, _start, end in records),
            )
        )
    def package_sort_key(packet: ComponentPacket) -> tuple[int, int | str]:
        suffix = packet.package[1:] if packet.package[:1] in {"U", "R", "C", "L", "Q", "D", "V", "I"} else packet.package
        return (0, int(suffix)) if suffix.isdigit() else (1, packet.package)

    return {family: sorted(values, key=package_sort_key) for family, values in packets.items()}


def inspect_component_counts(project: str | Path, markers: Iterable[str] | None = None) -> dict[str, int]:
    return {family: len(packets) for family, packets in inspect_component_packets(project, markers).items()}


def _parse_component_placer_pin_rows(data: bytes) -> tuple[bytes, int, tuple[CdbPinRow, ...], int]:
    if len(data) < COUNT_OFFSET + 4:
        raise ValueError("ROOT.CDB is too short.")
    count = _read_u32(data, COUNT_OFFSET)
    pos = COUNT_OFFSET + 4
    pin_rows: list[CdbPinRow] = []
    for _index in range(count):
        start = pos
        pos += PIN_ROW_HEADER_SIZE
        ref, pos = _read_lp_ascii(data, pos)
        pin_count = _read_u32(data, pos)
        pos += 4
        for _pin_index in range(pin_count):
            pos = _skip_lp_ascii(data, pos)
            pos = _skip_lp_ascii(data, pos)
        pos += PIN_ROW_FOOTER_SIZE
        if pos > len(data):
            raise ValueError("Unexpected end of CDB while reading pin row.")
        pin_rows.append(CdbPinRow(ref=ref, data=data[start:pos]))
    return data[:COUNT_OFFSET], count, tuple(pin_rows), pos


def _try_parse_property_row(data: bytes, row_start: int, header_size: int) -> tuple[str, int] | None:
    if row_start < 0 or row_start + header_size >= len(data):
        return None
    pos = row_start + header_size
    try:
        ref, pos = _read_lp_ascii(data, pos)
        if not CDB_PROPERTY_REF_RE.match(ref):
            return None
        for _field_index in range(3):
            pos = _skip_lp_ascii(data, pos)
        property_length = _read_u32(data, pos)
    except (UnicodeDecodeError, ValueError):
        return None
    computed_end = pos + 4 + property_length
    if computed_end <= row_start + header_size or computed_end > len(data):
        return None
    return ref, computed_end


def _property_row_computed_end_allow_partial(row: CdbPropertyRow, header_size: int) -> int:
    pos = header_size
    ref, pos = _read_lp_ascii(row.data, pos)
    if ref != row.ref:
        raise ValueError(f"CDB property row ref mismatch: expected {row.ref}, found {ref}.")
    for _field_index in range(3):
        pos = _skip_lp_ascii(row.data, pos)
    property_length = _read_u32(row.data, pos)
    return pos + 4 + property_length


def _property_row_chain_length(data: bytes, start: int, header_size: int) -> int:
    count = 0
    pos = start
    while pos < len(data):
        parsed = _try_parse_property_row(data, pos, header_size)
        if parsed is None:
            return count
        _ref, computed_end = parsed
        count += 1
        overlap_next = computed_end - 4
        if _try_parse_property_row(data, overlap_next, header_size) is not None:
            pos = overlap_next
        elif _try_parse_property_row(data, computed_end, header_size) is not None:
            pos = computed_end
        else:
            return count
    return count


def _locate_first_property_row(data: bytes, start: int, header_sizes: tuple[int, ...]) -> tuple[int, int]:
    # In user donors, a short byte bridge can sit between the pin table and
    # property rows. A few false starts can parse one row, so pick the candidate
    # that produces the longest coherent row chain.
    best: tuple[int, int, int] | None = None
    scan_end = min(len(data), start + 2048)
    for candidate in range(start, scan_end):
        for header_size in header_sizes:
            chain_length = _property_row_chain_length(data, candidate, header_size)
            if chain_length <= 0:
                continue
            if best is None or chain_length > best[0] or (chain_length == best[0] and header_size < best[2]):
                best = (chain_length, candidate, header_size)
    if best is None:
        raise ValueError("Could not locate first CDB property row.")
    return best[1], best[2]


def _parse_component_placer_property_rows(
    data: bytes,
    start: int,
    header_size: int,
) -> tuple[tuple[CdbPropertyRow, ...], bytes, int]:
    rows: list[CdbPropertyRow] = []
    pos = start
    while pos < len(data):
        parsed = _try_parse_property_row(data, pos, header_size)
        if parsed is None:
            break
        ref, computed_end = parsed
        overlap_next = computed_end - 4
        if _try_parse_property_row(data, overlap_next, header_size) is not None:
            row_end = overlap_next
            next_pos = overlap_next
        elif _try_parse_property_row(data, computed_end, header_size) is not None:
            row_end = computed_end
            next_pos = computed_end
        else:
            row_end = computed_end
            next_pos = computed_end
            rows.append(CdbPropertyRow(ref=ref, data=data[pos:row_end]))
            pos = next_pos
            break
        rows.append(CdbPropertyRow(ref=ref, data=data[pos:row_end]))
        pos = next_pos
    if not rows:
        raise ValueError("Could not parse any CDB property rows.")
    return tuple(rows), data[pos:], pos


def parse_component_placer_cdb(data: bytes, *, property_header_sizes: tuple[int, ...] = (20, 24, 28, 32, 36, 40)) -> ComponentPlacerCdb:
    prefix, count, pin_rows, pin_end = _parse_component_placer_pin_rows(data)
    property_start, header_size = _locate_first_property_row(data, pin_end, property_header_sizes)
    property_rows, suffix, _property_end = _parse_component_placer_property_rows(data, property_start, header_size)
    return ComponentPlacerCdb(
        prefix=prefix,
        count=count,
        pin_rows=pin_rows,
        between_sections=data[pin_end:property_start],
        property_rows=property_rows,
        suffix=suffix,
        property_header_size=header_size,
    )


def build_component_placer_cdb_subset(parsed: ComponentPlacerCdb, keep_packages: Iterable[str]) -> bytes:
    keep = set(keep_packages)
    pin_rows = [row for row in parsed.pin_rows if package_ref(row.ref) in keep]
    property_rows = [row for row in parsed.property_rows if package_ref(row.ref) in keep]
    property_tail = b""
    if property_rows:
        last_row = property_rows[-1]
        computed_end = _property_row_computed_end_allow_partial(last_row, parsed.property_header_size)
        if computed_end == len(last_row.data) + 4:
            property_tail = b"\x00\x00\x00\x00"
        elif computed_end != len(last_row.data):
            raise ValueError(f"Unexpected CDB property row length for {last_row.ref}: computed_end={computed_end}, row_size={len(last_row.data)}.")
    prefix = bytearray(parsed.prefix)
    prefix.extend(len(pin_rows).to_bytes(4, "little"))
    return (
        bytes(prefix)
        + b"".join(row.data for row in pin_rows)
        + parsed.between_sections
        + b"".join(row.data for row in property_rows)
        + property_tail
        + parsed.suffix
    )


def _generation_markers(markers: Iterable[str] | None = None) -> tuple[str, ...]:
    if markers is not None:
        values = set(markers)
    else:
        try:
            manifest = json.loads(_repo_path(TRUSTED_DONOR_MANIFEST_PATH).read_text(encoding="utf-8"))
            values = set(_known_markers_from_manifest(manifest))
        except Exception:
            values = set()
        values.update(EXTRA_GENERATION_MARKERS)
    return tuple(sorted(values, key=lambda marker: (marker in GENERIC_FAMILY_MARKERS, -len(marker), marker)))


def _family_for_record(raw: bytes, markers: Iterable[str]) -> str | None:
    for marker in markers:
        if marker.encode("ascii") in raw:
            return marker
    return None


def _component_record_starts(chunk: bytes) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    for match in RECORD_START_RE.finditer(chunk):
        start = match.start()
        if b"COMPONENT ID" in chunk[start : start + 240]:
            ref_length = match.group(1)[0]
            ref_start = start + 2
            ref = chunk[ref_start : ref_start + ref_length].decode("ascii", "ignore")
            if ref == "FUSE":
                ref = f"FUSE@{start}"
            starts.append((start, ref))
    for match in ANON_RECORD_START_RE.finditer(chunk):
        starts.append((match.start(), f"ANON{match.start()}"))
    return sorted(set(starts))


def _normal_component_record_starts(chunk: bytes) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    for match in RECORD_START_RE.finditer(chunk):
        start = match.start()
        if b"COMPONENT ID" in chunk[start : start + 240]:
            ref_length = match.group(1)[0]
            ref_start = start + 2
            ref = chunk[ref_start : ref_start + ref_length].decode("ascii", "ignore")
            starts.append((start, ref))
    return sorted(set(starts))


def _display_kind(record: bytes) -> str | None:
    if b"7SEGCOMA" in record or b"7SEG-COM-ANODE" in record or b"7SEG-COM-AN-BLUE" in record:
        return "7SEG-COM-AN-BLUE"
    if b"7SEGCOMK" in record or b"7SEG-COM-CAT" in record or b"7SEG-COM-CATHODE" in record:
        return "7SEG-COM-CAT-BLUE"
    return None


def _display_record_starts(chunk: bytes) -> list[int]:
    starts: list[int] = []
    pos = 0
    while True:
        pos = chunk.find(DISPLAY_RECORD_START, pos)
        if pos < 0:
            break
        if b"7SEG" in chunk[pos : pos + 700]:
            starts.append(pos)
        pos += 1
    return starts


def _display_records_from_chunk(chunk: bytes) -> dict[str, list[bytes]]:
    starts = set(_display_record_starts(chunk))
    if not starts:
        return {}
    for start, _ref in _normal_component_record_starts(chunk):
        starts.add(start)
    boundaries = sorted(starts) + [len(chunk)]
    rows: dict[str, list[bytes]] = {family: [] for family in DISPLAY_FAMILIES}
    for start in sorted(_display_record_starts(chunk)):
        next_start = next(boundary for boundary in boundaries if boundary > start)
        record = chunk[start:next_start]
        family = _display_kind(record)
        if family:
            rows[family].append(record)
    return {family: records for family, records in rows.items() if records}


def _anode_block_final_as_middle(row: bytes) -> bytes:
    if len(row) != 399 or row.endswith(b"\xff") or not row.endswith(b"\x00\x00"):
        raise ValueError("Expected a non-final 399-byte anode block-final row.")
    return row[:-2]


def _true_final_anode(rows: list[bytes]) -> bytes:
    for row in reversed(rows):
        if row.endswith(b"\xff"):
            return row
    raise ValueError("Display generation needs a donor-final common-anode row; selected donor does not contain one.")


def _display_rows_for_request(records: dict[str, list[bytes]], request: dict[str, int]) -> tuple[tuple[RawComponentGroup, ...], tuple[str, ...]]:
    notes: list[str] = []
    anode_rows = records.get("7SEG-COM-AN-BLUE", [])
    cathode_rows = records.get("7SEG-COM-CAT-BLUE", [])
    final_anode = _true_final_anode(anode_rows) if request.keys() & DISPLAY_FAMILIES else b""
    anode_count = request.get("7SEG-COM-AN-BLUE", 0)
    cathode_count = request.get("7SEG-COM-CAT-BLUE", 0)

    if anode_count and len(anode_rows) < anode_count:
        raise ValueError(f"Need {anode_count} common-anode display rows, found {len(anode_rows)}.")
    if cathode_count and len(cathode_rows) < cathode_count:
        raise ValueError(f"Need {cathode_count} common-cathode display rows, found {len(cathode_rows)}.")

    selected: list[RawComponentGroup] = []
    sequence = 0

    def append_row(*, key: str, family: str, ref: str, row: bytes) -> None:
        nonlocal sequence
        sequence += 1
        selected.append(
            RawComponentGroup(
                key=key,
                family=family,
                start=sequence,
                end=sequence + len(row),
                refs=(ref,),
                data=row,
                source_is_final=row.endswith(b"\xff"),
            )
        )

    if cathode_count:
        for index, row in enumerate(cathode_rows[:cathode_count], start=1):
            append_row(
                key=f"DISPLAY_CC_{index:03d}",
                family="7SEG-COM-CAT-BLUE",
                ref=f"CC{index}",
                row=row,
            )
        notes.append("common-cathode displays use individually placeable mega cathode middle rows")

    if anode_count:
        for index in range(anode_count - 1):
            row = anode_rows[index]
            append_row(
                key=f"DISPLAY_AN_{index + 1:03d}",
                family="7SEG-COM-AN-BLUE",
                ref=f"AN{index + 1}",
                row=_anode_block_final_as_middle(row) if len(row) == 399 and not row.endswith(b"\xff") else row,
            )
        append_row(
            key=f"DISPLAY_AN_{anode_count:03d}_TRUE_FINAL",
            family="7SEG-COM-AN-BLUE",
            ref=f"AN{anode_count}:TRUE_FINAL",
            row=final_anode,
        )
        notes.append(
            "common-anode red displays use individually placeable rows plus the true donor-final anode row"
        )
    elif cathode_count:
        append_row(
            key="DISPLAY_ANODE_SENTINEL",
            family="7SEG-COM-AN-BLUE",
            ref="ANODE_SENTINEL",
            row=final_anode,
        )
        notes.append(
            "common-cathode-only displays retain the true donor-final red-anode sentinel as hidden infrastructure"
        )

    if not selected:
        return (), ()
    data = b"".join(group.data for group in selected)
    if not data.endswith(b"\xff"):
        raise ValueError("Display block did not end with a final FF row.")
    return tuple(selected), tuple(notes)


def _load_d20_display_bridge(chunk: bytes) -> RawComponentGroup:
    cathode_rows = _display_records_from_chunk(chunk).get("7SEG-COM-CAT-BLUE", [])
    if not cathode_rows:
        raise ValueError("Cannot locate cathode display rows needed to find the D20 display bridge.")
    cathode_pos = chunk.find(cathode_rows[0])
    if cathode_pos < 0:
        raise ValueError("Cannot locate first cathode row in donor object chunk.")
    starts = [start for start, _ref in _normal_component_record_starts(chunk) if start < cathode_pos]
    if not starts:
        raise ValueError("Cannot locate the object immediately before display rows.")
    start = starts[-1]
    data = chunk[start:cathode_pos]
    if b"D20" not in data or b"DIODE" not in data or not data.endswith(b"\x00"):
        raise ValueError("Expected the accepted D20 diode bridge packet immediately before display rows.")
    return RawComponentGroup(
        key="D20",
        family="DIODE",
        start=start,
        end=cathode_pos,
        refs=("D20",),
        data=data,
        source_is_final=False,
    )


def _raw_groups_from_chunk(chunk: bytes, markers: Iterable[str]) -> dict[str, list[RawComponentGroup]]:
    if not chunk.endswith(b"\xff"):
        raise ValueError("Object chunk must end in FF.")
    starts = _component_record_starts(chunk)
    rows: list[tuple[int, int, str, str, bytes]] = []
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else max(0, len(chunk) - 1)
        raw = chunk[start:end]
        family = _family_for_record(raw, markers)
        if family is None:
            continue
        rows.append((start, end, ref, family, raw))

    grouped: list[RawComponentGroup] = []
    current: list[tuple[int, int, str, str, bytes]] = []
    current_key: str | None = None
    for row in rows:
        key = package_ref(row[2])
        if current and key != current_key:
            grouped.append(_make_raw_group(current, len(chunk)))
            current = []
        current.append(row)
        current_key = key
    if current:
        grouped.append(_make_raw_group(current, len(chunk)))

    by_family: dict[str, list[RawComponentGroup]] = defaultdict(list)
    for group in grouped:
        by_family[group.family].append(group)
    for family in by_family:
        by_family[family].sort(key=lambda item: item.start)
    return dict(by_family)


def _make_raw_group(rows: list[tuple[int, int, str, str, bytes]], chunk_size: int) -> RawComponentGroup:
    families = Counter(row[3] for row in rows)
    if len(families) != 1:
        raise ValueError(f"Contiguous package group matched mixed families: {dict(families)}")
    data = b"".join(row[4] for row in rows)
    return RawComponentGroup(
        key=package_ref(rows[0][2]),
        family=rows[0][3],
        start=min(row[0] for row in rows),
        end=max(row[1] for row in rows),
        refs=tuple(row[2] for row in rows),
        data=data,
        source_is_final=max(row[1] for row in rows) == chunk_size - 1,
    )


def _is_finalizable(group: RawComponentGroup) -> bool:
    return group.source_is_final or bool(group.data and group.data[-1] in (0x00, 0x08))


def _select_window(
    groups_by_family: dict[str, list[RawComponentGroup]],
    family: str,
    count: int,
    *,
    offset: int = 0,
    require_finalizable: bool = True,
) -> tuple[RawComponentGroup, ...]:
    groups = groups_by_family.get(family, [])
    if require_finalizable:
        groups = [group for group in groups if _is_finalizable(group)]
    groups = groups[offset:]
    if len(groups) < count:
        raise ValueError(f"Need {count} {family} groups after offset={offset}, found {len(groups)}.")
    return tuple(groups[:count])


def _cdb_package_set(data: bytes) -> set[str]:
    parsed = parse_component_placer_cdb(data)
    refs = {package_ref(row.ref) for row in parsed.pin_rows}
    refs.update(package_ref(row.ref) for row in parsed.property_rows)
    return {ref for ref in refs if ref}


def _select_cdb_backed(
    groups_by_family: dict[str, list[RawComponentGroup]],
    cdb_refs: set[str],
    family: str,
    count: int,
    *,
    offset: int = 0,
    lengths: set[int] | None = None,
    min_length: int | None = None,
    tail: bytes | None = None,
) -> tuple[RawComponentGroup, ...]:
    groups: list[RawComponentGroup] = []
    for group in groups_by_family.get(family, []):
        if group.key not in cdb_refs or not _is_finalizable(group):
            continue
        if lengths is not None and len(group.data) not in lengths:
            continue
        if min_length is not None and len(group.data) < min_length:
            continue
        if tail is not None and not group.data.endswith(tail):
            continue
        groups.append(group)
    groups = groups[offset:]
    if len(groups) < count:
        raise ValueError(f"Need {count} CDB-backed {family} groups after offset={offset}, found {len(groups)}.")
    return tuple(groups[:count])


def _select_cap_elec_groups(
    groups_by_family: dict[str, list[RawComponentGroup]],
    cdb_refs: set[str],
    count: int,
    *,
    offset: int = 0,
) -> tuple[RawComponentGroup, ...]:
    groups: list[RawComponentGroup] = []
    for group in groups_by_family.get("CAP-ELEC", []):
        if group.key not in cdb_refs:
            continue
        accepted_full_packet = len(group.data) == 379 and _is_finalizable(group) and group.data.endswith(b"\x00")
        accepted_semimega_packet = (
            len(group.data) == 352
            and b"CAP-ELEC" in group.data
            and b"ELEC-RAD10" in group.data
            and b"1uF" in group.data
        )
        if accepted_full_packet or accepted_semimega_packet:
            groups.append(group)
    groups = groups[offset:]
    if len(groups) < count:
        raise ValueError(f"Need {count} clean CAP-ELEC groups after offset={offset}, found {len(groups)}.")
    return tuple(groups[:count])


def _select_switch_groups(
    groups_by_family: dict[str, list[RawComponentGroup]],
    count: int,
    *,
    offset: int = 0,
) -> tuple[RawComponentGroup, ...]:
    groups = [
        group
        for group in groups_by_family.get("SWITCH", [])
        if _is_finalizable(group) and len(group.data) == SWITCH_PACKET_LENGTH
    ]
    groups = groups[offset:]
    if len(groups) < count:
        raise ValueError(
            f"Need {count} clean {SWITCH_PACKET_LENGTH}-byte SWITCH groups after offset={offset}, found {len(groups)}."
        )
    return tuple(groups[:count])


def _select_resistor_groups(
    groups_by_family: dict[str, list[RawComponentGroup]],
    cdb_refs: set[str],
    count: int,
    *,
    offset: int = 0,
) -> tuple[RawComponentGroup, ...]:
    groups = [
        group
        for group in groups_by_family.get("RESISTOR", [])
        if group.key in cdb_refs and _is_finalizable(group)
    ][offset:]
    if len(groups) < count:
        raise ValueError(f"Need {count} clean finalizable RESISTOR groups after offset={offset}, found {len(groups)}.")
    return tuple(groups[:count])


def _select_complete_package_window(
    groups_by_family: dict[str, list[RawComponentGroup]],
    family: str,
    count: int,
    *,
    offset: int = 0,
) -> tuple[RawComponentGroup, ...]:
    expected_refs = COMPLETE_PACKAGE_REF_COUNTS[family]
    candidates: list[RawComponentGroup] = []
    seen: set[str] = set()
    for group in groups_by_family.get(family, []):
        if group.key in seen:
            continue
        if not _is_finalizable(group):
            continue
        if len(group.refs) != expected_refs:
            continue
        seen.add(group.key)
        candidates.append(group)
    selected = candidates[offset : offset + count]
    if len(selected) == count:
        return tuple(selected)
    raise ValueError(
        f"Need {count} complete {family} package groups with {expected_refs} refs after offset={offset}, "
        f"found {len(candidates)}."
    )


def _s32_at(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32_at(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)


def _translate_switch_packet(data: bytes, *, dx: int, dy: int) -> bytes:
    out = bytearray(data)
    for offset in SWITCH_X_COORD_OFFSETS:
        if offset + 4 <= len(out):
            _put_s32_at(out, offset, _s32_at(out, offset) + dx)
    for offset in SWITCH_Y_COORD_OFFSETS:
        if offset + 4 <= len(out):
            _put_s32_at(out, offset, _s32_at(out, offset) + dy)
    return bytes(out)


def _translate_pot_packet(data: bytes, *, dx: int) -> bytes:
    if len(data) < 8 or data[0] != 0xFF:
        raise ValueError("POT-HG packet does not have the expected component-record header.")
    ref_length = data[1]
    base = 2 + ref_length
    out = bytearray(data)
    for relative_offset in POT_X_COORD_RELATIVE_OFFSETS:
        offset = base + relative_offset
        if offset + 4 <= len(out):
            _put_s32_at(out, offset, _s32_at(out, offset) + dx)
    return bytes(out)


def _replace_group_data(group: RawComponentGroup, data: bytes, *, start: int | None = None) -> RawComponentGroup:
    raw_start = group.start if start is None else start
    return RawComponentGroup(
        key=group.key,
        family=group.family,
        start=raw_start,
        end=raw_start + len(data),
        refs=group.refs,
        data=data,
        source_is_final=group.source_is_final,
    )


def _hidden_dummy_group(
    group: RawComponentGroup,
    *,
    hidden_coordinate_mode: str = DEFAULT_HIDDEN_COORDINATE_MODE,
) -> RawComponentGroup:
    if group.family not in CONTROL_PREFIX_FAMILIES:
        raise ValueError(f"Unsupported hidden dummy family: {group.family}")
    data = hide_packet(group.family, group.data, mode=hidden_coordinate_mode)
    return _replace_group_data(group, data, start=HIDDEN_PACKET_START)


def _payload_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _raw_layout_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict) and isinstance(payload.get("layout"), dict):
        return dict(payload["layout"])
    return {}


def _binary_beautifier_enabled(payload: Any) -> bool:
    raw_layout = _raw_layout_payload(payload)
    if str(raw_layout.get("strategy", "")).lower() != "beautify":
        return False
    if raw_layout.get("binary_coordinate_mutation") is not None:
        return _payload_bool(raw_layout.get("binary_coordinate_mutation"))
    if isinstance(payload, dict) and payload.get("binary_coordinate_mutation") is not None:
        return _payload_bool(payload.get("binary_coordinate_mutation"))
    return True


def _apply_binary_beautifier(
    payload: Any,
    groups: tuple[RawComponentGroup, ...],
    hidden_groups: tuple[RawComponentGroup, ...],
    *,
    start_slot: int = 0,
) -> tuple[tuple[RawComponentGroup, ...], list[dict[str, Any]], int]:
    if not _binary_beautifier_enabled(payload):
        return groups, [], start_slot

    hidden_ids = {id(group) for group in hidden_groups}
    translated: list[RawComponentGroup] = []
    layout_entries: list[dict[str, Any]] = []
    slot = start_slot
    cursor_x = VISIBLE_LAYOUT_ORIGIN_X + (start_slot % VISIBLE_LAYOUT_COLUMNS) * VISIBLE_LAYOUT_SLOT_X
    cursor_y = VISIBLE_LAYOUT_ORIGIN_Y + (start_slot // VISIBLE_LAYOUT_COLUMNS) * VISIBLE_LAYOUT_SLOT_Y
    row_height = 0
    row_index = start_slot // VISIBLE_LAYOUT_COLUMNS
    column_index = start_slot % VISIBLE_LAYOUT_COLUMNS
    shelf_right = VISIBLE_LAYOUT_ORIGIN_X + VISIBLE_LAYOUT_SHELF_WIDTH
    for group in groups:
        if id(group) in hidden_ids:
            translated.append(group)
            layout_entries.append(
                {
                    "key": group.key,
                    "family": group.family,
                    "translated": False,
                    "reason": "hidden dummy control kept in accepted donor packet position",
                }
            )
            continue
        pairs = layout_coordinate_pairs(group.data, group.family)
        if pairs:
            before = coordinate_bbox(group.data, pairs)
            allocation_width = max(int(before["width"]), VISIBLE_LAYOUT_SLOT_X) + VISIBLE_LAYOUT_MARGIN_X
            allocation_height = max(int(before["height"]), VISIBLE_LAYOUT_SLOT_Y) + VISIBLE_LAYOUT_MARGIN_Y
        else:
            allocation_width = VISIBLE_LAYOUT_SLOT_X + VISIBLE_LAYOUT_MARGIN_X
            allocation_height = VISIBLE_LAYOUT_SLOT_Y + VISIBLE_LAYOUT_MARGIN_Y
        if cursor_x != VISIBLE_LAYOUT_ORIGIN_X and cursor_x + allocation_width > shelf_right:
            cursor_x = VISIBLE_LAYOUT_ORIGIN_X
            cursor_y += max(row_height, VISIBLE_LAYOUT_SLOT_Y + VISIBLE_LAYOUT_MARGIN_Y)
            row_height = 0
            row_index += 1
            column_index = 0
        data, entry = translate_packet_to_position(
            group.data,
            slot=slot,
            key=group.key,
            family=group.family,
            target_min_x=cursor_x,
            target_min_y=cursor_y,
            row=row_index,
            column=column_index,
            allocation_width=allocation_width,
            allocation_height=allocation_height,
        )
        known_refs_unchanged = all(
            group.data.count(ref.encode("ascii")) == data.count(ref.encode("ascii"))
            for ref in group.refs
        )
        entry["known_refs_unchanged"] = known_refs_unchanged
        entry["refs_unchanged"] = known_refs_unchanged
        if not known_refs_unchanged:
            raise ValueError(f"Beautifier changed references for {group.key}; refusing to emit corrupted packet.")
        translated.append(_replace_group_data(group, data))
        layout_entries.append(entry)
        cursor_x += allocation_width
        row_height = max(row_height, allocation_height)
        column_index += 1
        slot += 1
    return tuple(translated), layout_entries, slot


def _select_raw_groups(
    groups_by_family: dict[str, list[RawComponentGroup]],
    cdb_refs: set[str],
    request: dict[str, int],
    *,
    control_strategy: str,
    switch_offset: int | None = None,
    component_offsets: dict[str, int] | None = None,
    excluded_keys: set[str] | None = None,
    hidden_coordinate_mode: str = DEFAULT_HIDDEN_COORDINATE_MODE,
) -> tuple[tuple[RawComponentGroup, ...], tuple[RawComponentGroup, ...]]:
    if excluded_keys:
        groups_by_family = {
            family: [group for group in groups if group.key not in excluded_keys]
            for family, groups in groups_by_family.items()
        }
    selected: list[RawComponentGroup] = []
    hidden: list[RawComponentGroup] = []
    for family, count in request.items():
        family_offset = int((component_offsets or {}).get(family, 0))
        if family == "SWITCH":
            selected.extend(
                _select_switch_groups(
                    groups_by_family,
                    count,
                    offset=switch_offset if switch_offset is not None else family_offset,
                )
            )
        elif family == "FUSE":
            fuse_groups = [
                group
                for group in groups_by_family.get(family, [])
                if _is_finalizable(group) and len(group.data) == 338 and group.data.endswith(b"\x08")
            ]
            fuse_groups = fuse_groups[family_offset:]
            selected.extend(fuse_groups[:count])
            if len(fuse_groups) < count:
                raise ValueError(f"Need {count} strict 338-byte FUSE groups.")
        elif family == "POT-HG":
            selected.extend(
                _select_cdb_backed(
                    groups_by_family,
                    cdb_refs,
                    family,
                    count,
                    offset=family_offset,
                    lengths={431, 432},
                    tail=b"\x08",
                )
            )
        elif family == "CAP-ELEC":
            selected.extend(
                _select_cap_elec_groups(
                    groups_by_family,
                    cdb_refs,
                    count,
                    offset=family_offset,
                )
            )
        elif family == "PNP":
            selected.extend(_select_cdb_backed(groups_by_family, cdb_refs, family, count, offset=family_offset, min_length=342, tail=b"\x00"))
        elif family in SOURCE_CLEAN_MIN_LENGTHS:
            selected.extend(
                _select_cdb_backed(
                    groups_by_family,
                    cdb_refs,
                    family,
                    count,
                    offset=family_offset,
                    min_length=SOURCE_CLEAN_MIN_LENGTHS[family],
                    tail=b"\x00",
                )
            )
        elif family == "RESISTOR":
            selected.extend(_select_resistor_groups(groups_by_family, cdb_refs, count, offset=family_offset))
        elif family == "BRIDGE" and count > 7:
            selected.extend(_select_cdb_backed(groups_by_family, cdb_refs, family, count, offset=14 + family_offset))
        elif family in COMPLETE_PACKAGE_REF_COUNTS:
            selected.extend(_select_complete_package_window(groups_by_family, family, count, offset=family_offset))
        else:
            selected.extend(_select_window(groups_by_family, family, count, offset=family_offset))
    return tuple(sorted(selected, key=lambda item: item.start)), tuple(hidden)


def _select_generation_donor(request: dict[str, int], donor_path: str | Path | None) -> Path:
    donor_request = {family: count for family, count in request.items() if family not in TERMINAL_FAMILIES}
    if donor_path is not None:
        donor = _resolve_explicit_donor(donor_path)
        counts = _inspect_donor_counts_for_selection(donor, _generation_markers())
        missing = {
            family: {"required": required, "available": counts.get(family, 0)}
            for family, required in donor_request.items()
            if counts.get(family, 0) < required
        }
        if missing:
            raise ValueError(f"Explicit donor {donor} does not contain enough requested packets: {missing}")
        return donor
    if not donor_request:
        return _repo_path(NEW_COMPONENT_MEGA_DONOR)
    requested = set(donor_request)
    if requested & NEW_COMPONENT_ONLY_FAMILIES:
        return _repo_path(NEW_COMPONENT_MEGA_DONOR)
    if "CAP-ELEC" in requested:
        # The semimega CAP-ELEC packets selected by the generic registry have
        # non-final record tails. They work as donor-middle packets but cannot
        # safely terminate a generated object chunk. The full mega donor has
        # the accepted CDB-backed, finalizable CAP-ELEC packet family.
        if requested & {"VSOURCE", "CSOURCE", "VSINE"}:
            return _repo_path(MAIN_MEGA_SOURCE_DONOR)
        return _repo_path(MAIN_MEGA_NO_SOURCE_DONOR)
    if requested & DISPLAY_FAMILIES:
        if requested & {"VSOURCE", "CSOURCE", "VSINE"}:
            return _repo_path(MAIN_MEGA_SOURCE_DONOR)
        return _repo_path(MAIN_MEGA_NO_SOURCE_DONOR)
    try:
        selection = select_removal_only_donor(donor_request)
        return _repo_path(selection.donor.path)
    except ComponentPlacerBlocked:
        return _repo_path(NEW_COMPONENT_MEGA_DONOR)


def _chunk_prefix_for_request(request: dict[str, int], donor_chunk: bytes) -> bytes:
    if set(request) & CONTROL_PREFIX_FAMILIES:
        return OBJECT_CHUNK_PREFIX
    if len(donor_chunk) >= 2:
        return donor_chunk[:2]
    return NO_TERMINAL_OBJECT_CHUNK_PREFIX


def _data_as_middle(group: RawComponentGroup) -> bytes:
    if group.source_is_final:
        raise ValueError(f"Cannot place {group.key} before later display rows because it is donor-final.")
    if group.data.endswith(b"\xff"):
        raise ValueError(f"Cannot place {group.key} before later display rows because it already ends in FF.")
    return group.data


def _object_chunk_from_groups_and_display(
    groups: Iterable[RawComponentGroup],
    *,
    display_bridge: RawComponentGroup,
    display_groups: tuple[RawComponentGroup, ...],
    prefix: bytes,
) -> bytes:
    ordered = tuple(sorted(groups, key=lambda item: item.start))
    display_data = b"".join(group.data for group in display_groups)
    if not display_data.endswith(b"\xff"):
        raise ValueError("Display data must provide the final FF terminator.")
    return prefix + b"".join(_data_as_middle(group) for group in ordered) + display_bridge.data + display_data


def _finalize_group(group: RawComponentGroup) -> bytes:
    if group.source_is_final:
        return group.data
    if not group.data or group.data[-1] not in (0x00, 0x08):
        raise ValueError(f"Cannot finalize {group.key}: unexpected tail {group.data[-8:].hex()}.")
    return group.data[:-1]


def _object_chunk_from_groups(groups: Iterable[RawComponentGroup], *, prefix: bytes = OBJECT_CHUNK_PREFIX) -> bytes:
    ordered = tuple(sorted(groups, key=lambda item: item.start))
    if not ordered:
        return prefix + b"\xff"
    return prefix + b"".join(group.data for group in ordered[:-1]) + _finalize_group(ordered[-1]) + b"\xff"


def _prefer_safe_non_display_finalizer(groups: Iterable[RawComponentGroup]) -> tuple[RawComponentGroup, ...]:
    """Avoid making fragile visual-only packets the final DSN object record."""
    raw_groups = tuple(groups)
    ordered = tuple(sorted(raw_groups, key=lambda item: item.start))
    if len(ordered) < 2 or ordered[-1].family not in UNSAFE_NONDISPLAY_FINAL_FAMILIES:
        return raw_groups

    candidates: list[RawComponentGroup] = []
    for family in PREFERRED_NONDISPLAY_FINAL_FAMILIES:
        candidates = [group for group in ordered[:-1] if group.family == family and _is_finalizable(group)]
        if candidates:
            break
    if not candidates:
        return raw_groups

    chosen = candidates[-1]
    moved = _replace_group_data(chosen, chosen.data, start=ordered[-1].start + 1)
    chosen_id = id(chosen)
    return tuple(moved if id(group) == chosen_id else group for group in raw_groups)


def _terminal_groups_for_request(request: dict[str, int], *, start: int) -> tuple[RawComponentGroup, ...]:
    terminal_count = sum(request.get(family, 0) for family in TERMINAL_FAMILIES)
    if not terminal_count:
        return ()
    templates = load_production_templates(FixtureRegistry.load())
    groups: list[RawComponentGroup] = []
    index = 0
    x0 = -6_350_000
    y0 = -5_080_000
    x_step = 1_270_000
    y_step = 1_270_000
    columns = 7
    for family in ("POWER", "GROUND", "TERMINAL"):
        for local in range(request.get(family, 0)):
            if family == "POWER":
                label = "V0" if local == 0 else f"V{local}"
            elif family == "GROUND":
                label = "G0" if local == 0 else f"G{local}"
            else:
                label = f"N{local + 1:03d}"
            x = x0 + (index % columns) * x_step
            y = y0 + (index // columns) * y_step
            data = build_bidir_record(
                templates,
                label=label,
                symbol_x=x,
                symbol_y=y,
                angle_tenths=0,
                suffix=(0x7000 + index) & 0xFFFF,
                active_link=False,
            )
            groups.append(
                RawComponentGroup(
                    key=f"{family}_{local + 1}",
                    family=family,
                    start=start + index,
                    end=start + index + len(data),
                    refs=(label,),
                    data=data,
                    source_is_final=False,
                )
            )
            index += 1
    return tuple(groups)


def _normal_output_name(request: dict[str, int]) -> str:
    bits = [f"{family}_{count}" for family, count in sorted(request.items())]
    return "component_placement_" + "_".join(bits) + ".pdsprj"


def _apply_component_offset_defaults(
    donor: Path,
    request: dict[str, int],
    component_offsets: dict[str, int],
) -> dict[str, int]:
    repo_root = repository_root()
    donor_key = donor.relative_to(repo_root).as_posix() if donor.is_relative_to(repo_root) else donor.as_posix()
    defaults = DONOR_COMPONENT_OFFSET_DEFAULTS.get(donor_key, {})
    if not defaults:
        return component_offsets
    merged = dict(component_offsets)
    for family, offset in defaults.items():
        if family in request and family not in merged:
            merged[family] = offset
    return merged


def generate_component_placement_project(
    payload: Any,
    output: str | Path,
    *,
    control_strategy: str | None = None,
    donor_path: str | Path | None = None,
    full_cdb: bool = True,
) -> RawPlacementResult:
    request = normalize_request(payload)
    terminal_request = {family: count for family, count in request.items() if family in TERMINAL_FAMILIES}
    if terminal_request:
        raise ValueError(
            "Synthetic POWER/GROUND/TERMINAL placement is disabled for component placement; "
            f"omit these families from the request: {terminal_request}"
        )
    strategy = str(
        control_strategy
        or (payload.get("control_strategy") if isinstance(payload, dict) else None)
        or "accepted"
    )
    if strategy not in CONTROL_STRATEGIES:
        raise ValueError(f"Unsupported control_strategy {strategy!r}; expected one of {CONTROL_STRATEGIES}.")
    if strategy in {"switch_precedence", "hidden_dummy_switch", "hidden_dummy_control"}:
        strategy = "accepted"
    switch_offset = None
    if isinstance(payload, dict) and payload.get("switch_offset") is not None:
        switch_offset = int(payload["switch_offset"])
    component_offsets: dict[str, int] = {}
    if isinstance(payload, dict) and isinstance(payload.get("component_offsets"), dict):
        component_offsets = {
            normalize_component(str(family)): int(offset)
            for family, offset in payload["component_offsets"].items()
        }
    hidden_coordinate_mode = DEFAULT_HIDDEN_COORDINATE_MODE
    display_bridge_coordinate_mode = "preserve_donor"
    if isinstance(payload, dict):
        raw_layout = payload.get("layout") if isinstance(payload.get("layout"), dict) else {}
        hidden_coordinate_mode = str(
            payload.get("hidden_coordinate_mode")
            or raw_layout.get("hidden_coordinate_mode")
            or DEFAULT_HIDDEN_COORDINATE_MODE
        ).lower()
        display_bridge_coordinate_mode = str(
            payload.get("display_bridge_coordinate_mode")
            or payload.get("d20_coordinate_mode")
            or raw_layout.get("display_bridge_coordinate_mode")
            or raw_layout.get("d20_coordinate_mode")
            or "preserve_donor"
        ).lower()
        hide_display_bridge = _payload_bool(
            payload.get("hide_display_bridge")
            if payload.get("hide_display_bridge") is not None
            else raw_layout.get("hide_display_bridge")
        )
    else:
        hide_display_bridge = False

    output_path = Path(output)
    if output_path.suffix.lower() != ".pdsprj":
        output_path.mkdir(parents=True, exist_ok=True)
        output_path = output_path / _normal_output_name(request)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    explicit_donor = donor_path or _payload_donor_spec(payload)
    donor = _select_generation_donor(request, explicit_donor)
    component_offsets = _apply_component_offset_defaults(donor, request, component_offsets)
    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)
    markers = _generation_markers()
    groups_by_family = _raw_groups_from_chunk(donor_chunk, markers)
    cdb_refs = _cdb_package_set(donor_cdb)
    display_request = {family: count for family, count in request.items() if family in DISPLAY_FAMILIES}
    raw_request = {
        family: count
        for family, count in request.items()
        if family not in DISPLAY_FAMILIES and family not in TERMINAL_FAMILIES
    }
    excluded_keys = {"D20"} if display_request else set()
    selected, hidden = _select_raw_groups(
        groups_by_family,
        cdb_refs,
        raw_request,
        control_strategy=strategy,
        switch_offset=switch_offset,
        component_offsets=component_offsets,
        excluded_keys=excluded_keys,
        hidden_coordinate_mode=hidden_coordinate_mode,
    )
    if not hidden:
        hidden_coordinate_mode = DEFAULT_HIDDEN_COORDINATE_MODE
    selected_with_terminals = selected
    selected_with_terminals, value_mutations, value_mutation_report = apply_value_mutations_to_groups(
        payload,
        selected_with_terminals,
        normalize_component,
    )
    prefix = _chunk_prefix_for_request(request, donor_chunk)
    actual_layout_entries: list[dict[str, Any]] = []
    display_groups: tuple[RawComponentGroup, ...] = ()
    display_notes: tuple[str, ...] = ()
    display_bridge: RawComponentGroup | None = None
    if display_request:
        display_donor = donor
        display_chunk_source = donor_chunk
        try:
            display_groups, display_notes = _display_rows_for_request(_display_records_from_chunk(display_chunk_source), display_request)
            display_bridge = _load_d20_display_bridge(display_chunk_source)
        except ValueError:
            display_donor = _repo_path(MAIN_MEGA_NO_SOURCE_DONOR)
            display_chunk_source = _extract_object_chunk(read_internal_file(display_donor, "ROOT.DSN"))
            display_groups, display_notes = _display_rows_for_request(_display_records_from_chunk(display_chunk_source), display_request)
            display_bridge = _load_d20_display_bridge(display_chunk_source)
        display_infrastructure_entries: list[dict[str, Any]] = []
        display_infrastructure_entries.append(
            {
                "key": display_bridge.key,
                "family": display_bridge.family,
                "translated": False,
                "role": "display_infrastructure",
                "coordinate_mode": "preserve_donor",
                "reason": "D20 is an immutable donor bridge and is never moved by the beautifier",
            }
        )
        if hide_display_bridge or display_bridge_coordinate_mode != "preserve_donor":
            display_notes = (
                *display_notes,
                "D20 movement request ignored; the accepted bridge packet keeps donor coordinates",
            )
        selected_with_terminals, selected_layout_entries, next_slot = _apply_binary_beautifier(
            payload,
            selected_with_terminals,
            hidden,
        )
        display_sentinel = next(
            (group for group in display_groups if group.key == "DISPLAY_ANODE_SENTINEL"),
            None,
        )
        visible_display_groups = tuple(
            group for group in display_groups if group.key != "DISPLAY_ANODE_SENTINEL"
        )
        visible_display_groups, display_layout_entries, _next_slot = _apply_binary_beautifier(
            payload,
            visible_display_groups,
            (),
            start_slot=next_slot,
        )
        if display_sentinel is not None:
            if hide_display_bridge:
                moved_sentinel, sentinel_entry = translate_packet_by_delta(
                    display_sentinel.data,
                    key=display_sentinel.key,
                    family="7SEG-COM-AN-BLUE",
                    dx=D20_SMALL_COORD_DX,
                    dy=D20_SMALL_COORD_DY,
                )
                sentinel_entry["role"] = "display_infrastructure"
                display_infrastructure_entries.append(sentinel_entry)
                display_sentinel = _replace_group_data(
                    display_sentinel,
                    moved_sentinel,
                    start=HIDDEN_PACKET_START + 2,
                )
            else:
                display_infrastructure_entries.append(
                    {
                        "key": display_sentinel.key,
                        "family": display_sentinel.family,
                        "translated": False,
                        "role": "display_infrastructure",
                        "reason": "D20-static isolation case keeps the required final-row sentinel unchanged",
                    }
                )
            display_groups = (*visible_display_groups, display_sentinel)
        else:
            display_groups = visible_display_groups
        actual_layout_entries = [
            *selected_layout_entries,
            *display_layout_entries,
            *display_infrastructure_entries,
        ]
        object_chunk = _object_chunk_from_groups_and_display(
            selected_with_terminals,
            display_bridge=display_bridge,
            display_groups=display_groups,
            prefix=prefix,
        )
    else:
        selected_with_terminals = _prefer_safe_non_display_finalizer(selected_with_terminals)
        selected_with_terminals, actual_layout_entries, _next_slot = _apply_binary_beautifier(
            payload,
            selected_with_terminals,
            hidden,
        )
        object_chunk = _object_chunk_from_groups(selected_with_terminals, prefix=prefix)
    if full_cdb:
        cdb = donor_cdb
        cdb_policy = "full_donor_cdb"
    else:
        keep_refs = [group.key for group in selected if not group.key.startswith("ANON")]
        cdb = build_component_placer_cdb_subset(parse_component_placer_cdb(donor_cdb), keep_refs)
        cdb_policy = "pruned_to_selected_package_refs"
    if value_mutations:
        cdb, value_cdb_report = patch_cdb_property_rows(parse_component_placer_cdb(cdb), value_mutations)
    else:
        value_cdb_report = {
            "stage": "value_changer_cdb_patch",
            "applied": False,
            "mode": "same_length_selected_property_rows",
            "mutations": [],
        }
    dsn, _pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(donor, output_path, {"ROOT.DSN": dsn, "ROOT.CDB": cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output_path, "ROOT.DSN"))
    errors: list[ValidationIssue] = []
    if final_chunk != object_chunk:
        errors.append(ValidationIssue("E_OUTPUT_CHUNK_MISMATCH", "Final ROOT.DSN object chunk differs from requested chunk."))
    reported_selected = selected_with_terminals
    if display_bridge is not None:
        reported_selected = (*selected_with_terminals, display_bridge, *display_groups)
    pipeline_metadata = build_component_pipeline_metadata(
        payload=payload,
        request=request,
        selected_groups=reported_selected,
        hidden_groups=hidden,
        control_strategy=strategy,
        normalize_family=normalize_component,
        hidden_coordinate_mode=hidden_coordinate_mode,
    )
    pipeline_metadata["value_plan"]["binary_mutation"] = value_mutation_report["binary_mutation"]
    pipeline_metadata["value_plan"]["packet_mutations"] = value_mutation_report["mutations"]
    pipeline_metadata["value_plan"]["cdb_patch"] = value_cdb_report
    if value_mutation_report["errors"]:
        pipeline_metadata["value_plan"]["valid"] = False
        pipeline_metadata["value_plan"]["errors"] = value_mutation_report["errors"]
    pipeline_metadata["validation_reports"]["value_changer"] = {
        "valid": not value_mutation_report["errors"],
        "errors": value_mutation_report["errors"],
        "warnings": value_mutation_report["warnings"],
        "packet_mutation_count": len(value_mutation_report["mutations"]),
        "cdb_mutation_count": len(value_cdb_report["mutations"]),
    }
    if actual_layout_entries:
        translated_count = sum(1 for entry in actual_layout_entries if entry.get("translated"))
        hidden_applied = bool(pipeline_metadata["layout_plan"]["binary_coordinate_mutation"].get("applied"))
        pipeline_metadata["layout_plan"]["binary_coordinate_mutation"].update(
            {
                "applied": hidden_applied or translated_count > 0,
                "visible_applied": translated_count > 0,
                "visible_translated_count": translated_count,
                "visible_entry_count": len(actual_layout_entries),
            }
        )
        pipeline_metadata["layout_plan"]["actual_binary_placements"] = actual_layout_entries
        pipeline_metadata["layout_plan"]["adjustments"].append(
            {
                "type": "packet_grid_translation",
                "translated_count": translated_count,
                "skipped_count": len(actual_layout_entries) - translated_count,
            }
        )
    output_validation = validate_generated_component_output(
        output_path,
        donor=donor,
        request=request,
        selected_groups=reported_selected,
        layout_entries=actual_layout_entries,
        require_layout_translation=_binary_beautifier_enabled(payload),
        full_cdb=full_cdb,
        allow_full_cdb_mutation=bool(value_mutations),
    )
    pipeline_metadata["validation_reports"]["generated_output_validator"] = output_validation
    for issue in output_validation["errors"]:
        errors.append(
            ValidationIssue(
                code=str(issue.get("code", "E_GENERATED_OUTPUT")),
                message=str(issue.get("message", "Generated output validation failed.")),
                severity=str(issue.get("severity", "error")),
            )
        )
    for issue in pipeline_errors(pipeline_metadata):
        errors.append(
            ValidationIssue(
                code=str(issue.get("code", "E_COMPONENT_PIPELINE")),
                message=str(issue.get("message", "Component pipeline validation failed.")),
                severity=str(issue.get("severity", "error")),
            )
        )
    manifest_path = manifest_path_for_output(output_path)
    result = RawPlacementResult(
        output=output_path,
        donor=donor,
        request=request,
        control_strategy=strategy,
        selected_groups=reported_selected,
        hidden_groups=hidden,
        object_chunk_size=len(final_chunk),
        object_chunk_head=final_chunk[:16].hex(),
        object_chunk_tail=final_chunk[-16:].hex(),
        cdb_policy=cdb_policy + ("; display=" + "; ".join(display_notes) if display_notes else ""),
        errors=tuple(errors),
        value_plan=pipeline_metadata["value_plan"],
        wiring_plan=pipeline_metadata["wiring_plan"],
        layout_plan=pipeline_metadata["layout_plan"],
        hidden_dummy_controls=pipeline_metadata["hidden_dummy_controls"],
        validation_reports=pipeline_metadata["validation_reports"],
        manifest_path=manifest_path,
    )
    manifest_path.write_text(json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def load_trusted_donors(path: str | Path | None = None, *, include_registry: bool = True, verify_file_counts: bool = False) -> tuple[list[TrustedDonor], dict[str, str]]:
    manifest_path = _repo_path(path or TRUSTED_DONOR_MANIFEST_PATH)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    aliases = _manifest_aliases(data)
    markers = _known_markers_from_manifest(data)
    donors: list[TrustedDonor] = []

    for raw in data.get("donors", []):
        donor_path = _repo_path(raw["path"])
        counts = {normalize_component(key, aliases): int(value) for key, value in raw.get("counts", {}).items()}
        if verify_file_counts:
            inspected = inspect_component_counts(donor_path, markers)
            for family, expected in counts.items():
                actual = inspected.get(family, 0)
                if actual != expected:
                    raise ValueError(f"Trusted donor {raw['id']} count mismatch for {family}: manifest={expected}, inspected={actual}.")
        donors.append(
            TrustedDonor(
                donor_id=str(raw["id"]),
                path=donor_path,
                counts=dict(sorted(counts.items())),
                source=str(raw.get("source", "manifest")),
                priority=int(raw.get("priority", 100)),
                notes=str(raw.get("notes", "")),
            )
        )

    if include_registry and data.get("include_native_registry_donors", False):
        registry = NativeRegistry.load()
        seen = {donor.path.resolve() for donor in donors if donor.path.exists()}
        for key, component in registry.components.items():
            canonical = component.marker if key == "74HC47" or component.marker in DISPLAY_FAMILIES else key
            aliases[_token(key)] = canonical
            aliases[_token(component.marker)] = canonical
            for alias in component.aliases:
                aliases[_token(alias)] = canonical
            for kind, donor_path in component.donors.items():
                if not donor_path.exists() or donor_path.resolve() in seen:
                    continue
                inspected = inspect_component_counts(donor_path, markers)
                counts = {family: count for family, count in inspected.items() if count > 0}
                if not counts:
                    continue
                donors.append(
                    TrustedDonor(
                        donor_id=f"native_registry:{canonical}:{kind}:{_sha_path_fragment(donor_path)}",
                        path=donor_path,
                        counts=dict(sorted(counts.items())),
                        source="native_components.json",
                        priority=20 if len(counts) == 1 else 60,
                        notes=f"Auto-indexed trusted IC-wise donor kind={kind}.",
                    )
                )
                seen.add(donor_path.resolve())
    return donors, aliases


def _score_donor(donor: TrustedDonor, request: dict[str, int]) -> tuple[int, int, int, int, str] | None:
    for family, required in request.items():
        if donor.counts.get(family, 0) < required:
            return None
    requested_surplus = sum(donor.counts.get(family, 0) - required for family, required in request.items())
    extra_family_count = sum(1 for family, count in donor.counts.items() if count > 0 and family not in request)
    total_delete_count = requested_surplus + sum(count for family, count in donor.counts.items() if family not in request)
    return (total_delete_count, extra_family_count, requested_surplus, donor.priority, donor.donor_id)


def select_removal_only_donor(
    payload: Any,
    *,
    donors: Iterable[TrustedDonor] | None = None,
    manifest_path: str | Path | None = None,
    verify_file_counts: bool = False,
) -> DonorSelection:
    if donors is None:
        donor_list, aliases = load_trusted_donors(manifest_path, verify_file_counts=verify_file_counts)
    else:
        donor_list = list(donors)
        aliases = load_component_aliases(manifest_path)
    request = normalize_request(payload, aliases)
    candidates: list[tuple[tuple[int, int, int, int, str], TrustedDonor]] = []
    for donor in donor_list:
        score = _score_donor(donor, request)
        if score is not None:
            candidates.append((score, donor))
    if not candidates:
        max_available: dict[str, int] = {}
        for family in request:
            max_available[family] = max((donor.counts.get(family, 0) for donor in donor_list), default=0)
        issue = ValidationIssue(
            "E_DONOR_MISSING_REMOVAL_ONLY",
            "No trusted donor contains the requested component quantities without cloning. "
            f"request={request}; max_available={max_available}",
        )
        raise ComponentPlacerBlocked(ComponentPlacerReport(errors=(issue,)))
    score, donor = sorted(candidates, key=lambda item: item[0])[0]
    inspected_counts: dict[str, int] = {}
    warnings: list[ValidationIssue] = []
    if verify_file_counts:
        inspected_counts = inspect_component_counts(donor.path)
        for family, expected in donor.counts.items():
            actual = inspected_counts.get(family, 0)
            if actual != expected:
                warnings.append(ValidationIssue("W_TRUSTED_COUNT_MISMATCH", f"{donor.donor_id}:{family} manifest={expected}, inspected={actual}", "warning"))
    return DonorSelection(request=request, donor=donor, score=score, inspected_counts=inspected_counts or donor.counts, warnings=tuple(warnings))


def build_deletion_plan(selection: DonorSelection) -> DeletionPlan:
    packets = inspect_component_packets(selection.donor.path)
    keep: dict[str, tuple[str, ...]] = {}
    delete: dict[str, tuple[str, ...]] = {}
    keep_refs: list[str] = []
    delete_refs: list[str] = []
    for family, family_packets in sorted(packets.items()):
        requested = selection.request.get(family, 0)
        family_packages = [packet.package for packet in family_packets]
        keep_packages = tuple(family_packages[:requested])
        delete_packages = tuple(family_packages[requested:])
        if keep_packages:
            keep[family] = keep_packages
            keep_refs.extend(keep_packages)
        if delete_packages:
            delete[family] = delete_packages
            delete_refs.extend(delete_packages)

    plan = DeletionPlan(
        selection=selection,
        keep_packages=keep,
        delete_packages=delete,
        cdb_package_refs_to_keep=tuple(keep_refs),
        cdb_package_refs_to_delete=tuple(delete_refs),
        device_section_policy="prune deleted package/device rows; keep only metadata needed by kept packages",
        cdb_policy="rebuild ROOT.CDB from kept pin/property rows only; full-donor CDB reuse after deletion is forbidden",
    )
    report = validate_deletion_plan(plan)
    if not report.valid:
        raise ComponentPlacerBlocked(report)
    return plan


def validate_deletion_plan(plan: DeletionPlan) -> ComponentPlacerReport:
    errors: list[ValidationIssue] = []
    keep_all = [ref for refs in plan.keep_packages.values() for ref in refs]
    delete_all = [ref for refs in plan.delete_packages.values() for ref in refs]
    if set(keep_all) & set(delete_all):
        errors.append(ValidationIssue("E_DELETE_KEEP_OVERLAP", f"Packages appear in both keep and delete sets: {sorted(set(keep_all) & set(delete_all))}"))
    duplicates = [ref for ref, count in Counter(keep_all).items() if count > 1]
    if duplicates:
        errors.append(ValidationIssue("E_COMPONENT_REF_DUPLICATE", f"Duplicate kept package refs: {duplicates}"))
    for family, required in plan.selection.request.items():
        actual = len(plan.keep_packages.get(family, ()))
        if actual != required:
            errors.append(ValidationIssue("E_DELETION_KEEP_COUNT", f"{family} keep count {actual} != requested {required}"))
    cdb_policy_lower = plan.cdb_policy.lower().strip()
    if cdb_policy_lower.startswith("copy full") or cdb_policy_lower == "copy full donor cdb after deletion":
        errors.append(ValidationIssue("E_CDB_FULL_COPY_FORBIDDEN", "Deletion plans must prune ROOT.CDB rows for deleted components."))
    if not plan.cdb_package_refs_to_delete:
        # Not an error for exact donors, but useful evidence for the caller.
        warning = ValidationIssue("W_NO_DELETIONS_REQUIRED", "Selected donor is exact for this request.", "warning")
        return ComponentPlacerReport(errors=tuple(errors), warnings=(warning,))
    if not plan.cdb_package_refs_to_keep:
        errors.append(ValidationIssue("E_EMPTY_KEEP_SET", "Deletion plan would remove every component."))
    return ComponentPlacerReport(errors=tuple(errors))


def validate_project_placement(project: str | Path, *, markers: Iterable[str] | None = None, strict_cdb_subset: bool = True) -> ComponentPlacerReport:
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    path = _repo_path(project)
    try:
        dsn = read_internal_file(path, "ROOT.DSN")
        cdb = read_internal_file(path, "ROOT.CDB")
        chunk = _extract_object_chunk(dsn)
    except Exception as exc:
        return ComponentPlacerReport(errors=(ValidationIssue("E_PROJECT_READ_FAILED", str(exc)),))

    starts = [(match.start(), match.group(2).decode("ascii")) for match in RECORD_START_RE.finditer(chunk)]
    exact_refs = [ref for _start, ref in starts]
    duplicate_exact_refs = [ref for ref, count in Counter(exact_refs).items() if count > 1]
    if duplicate_exact_refs:
        errors.append(ValidationIssue("E_COMPONENT_REF_DUPLICATE", f"Duplicate DSN component refs: {duplicate_exact_refs}"))
    body_packages = {package_ref(ref) for ref in exact_refs}

    marker_list = tuple(sorted(set(markers or load_component_aliases().values()), key=len, reverse=True))
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else max(0, len(chunk) - 1)
        raw = chunk[start:end]
        if not any(marker.encode("ascii") in raw for marker in marker_list):
            continue
        if not package_ref(ref):
            errors.append(ValidationIssue("E_COMPONENT_MODEL_MISSING", f"Component record at {start} has empty package ref."))

    try:
        try:
            parsed = parse_component_placer_cdb(cdb)
        except ValueError:
            legacy = parse_cdb(cdb)
            parsed = ComponentPlacerCdb(
                prefix=legacy.prefix,
                count=legacy.count,
                pin_rows=legacy.pin_rows,
                between_sections=legacy.between_sections,
                property_rows=legacy.property_rows,
                suffix=legacy.suffix,
                property_header_size=20,
            )
        cdb_pin_packages = [package_ref(row.ref) for row in parsed.pin_rows]
        cdb_property_packages = [package_ref(row.ref) for row in parsed.property_rows]
        for label, values in (("pin", cdb_pin_packages), ("property", cdb_property_packages)):
            duplicates = [ref for ref, count in Counter(values).items() if count > 1]
            if duplicates:
                warnings.append(ValidationIssue("W_CDB_MULTIPLE_ROWS_FOR_PACKAGE", f"CDB {label} rows repeat package refs: {duplicates}", "warning"))
        primary_ids = [int.from_bytes(row.data[:4], "little") for row in parsed.pin_rows if len(row.data) >= 4]
        secondary_ids = [int.from_bytes(row.data[12:16], "little") for row in parsed.pin_rows if len(row.data) >= 16]
        property_ids = [int.from_bytes(row.data[:4], "little") for row in parsed.property_rows if len(row.data) >= 4]
        for label, values in (("pin_primary", primary_ids), ("pin_secondary", secondary_ids), ("property", property_ids)):
            duplicates = [item for item, count in Counter(values).items() if count > 1]
            if duplicates:
                errors.append(ValidationIssue("E_CDB_ID_DUPLICATE", f"Duplicate CDB {label} ids: {duplicates}"))
        if strict_cdb_subset:
            orphan_pin = sorted(set(cdb_pin_packages) - body_packages)
            orphan_property = sorted(set(cdb_property_packages) - body_packages)
            if orphan_pin:
                errors.append(ValidationIssue("E_ORPHAN_CDB_PIN_REFS", f"CDB pin refs absent from DSN body packets: {orphan_pin[:40]}"))
            if orphan_property:
                errors.append(ValidationIssue("E_ORPHAN_CDB_PROPERTY_REFS", f"CDB property refs absent from DSN body packets: {orphan_property[:40]}"))
    except Exception as exc:
        errors.append(ValidationIssue("E_CDB_PARSE_FAILED", str(exc)))
    return ComponentPlacerReport(errors=tuple(errors), warnings=tuple(warnings))


def validate_generated_component_output(
    project: str | Path,
    *,
    donor: str | Path,
    request: dict[str, int],
    selected_groups: Iterable[RawComponentGroup],
    layout_entries: Iterable[dict[str, Any]],
    require_layout_translation: bool,
    full_cdb: bool,
    allow_full_cdb_mutation: bool = False,
) -> dict[str, Any]:
    """Validate one emitted component-placer project against its exact request."""

    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []
    project_path = _repo_path(project)
    donor_path = _repo_path(donor)
    required_members = {"PROJECT.XML", "ROOT.DSN", "ROOT.CDB", "SCRIPTS/PWRRAILS.DAT"}
    try:
        with ZipFile(project_path) as archive:
            members = set(archive.namelist())
        missing_members = sorted(required_members - members)
        if missing_members:
            errors.append(
                ValidationIssue(
                    "E_OUTPUT_CONTAINER_MEMBER_MISSING",
                    f"Generated project is missing required members: {missing_members}",
                )
            )
    except Exception as exc:
        errors.append(ValidationIssue("E_OUTPUT_CONTAINER_READ_FAILED", str(exc)))

    placement = validate_project_placement(project_path, strict_cdb_subset=not full_cdb)
    errors.extend(placement.errors)
    warnings.extend(placement.warnings)

    infrastructure_keys = {"D20", "DISPLAY_ANODE_SENTINEL"}
    visible_groups = tuple(group for group in selected_groups if group.key not in infrastructure_keys)
    actual_counts = Counter(group.family for group in visible_groups)
    for family, required in sorted(request.items()):
        actual = actual_counts.get(family, 0)
        if actual != required:
            errors.append(
                ValidationIssue(
                    "E_OUTPUT_COMPONENT_COUNT",
                    f"{family} emitted group count {actual} != requested {required}.",
                )
            )
    unexpected = {
        family: count
        for family, count in actual_counts.items()
        if family not in request
    }
    if unexpected:
        errors.append(
            ValidationIssue(
                "E_OUTPUT_UNREQUESTED_COMPONENT",
                f"Generated output contains unrequested component groups: {dict(sorted(unexpected.items()))}",
            )
        )

    entries_by_key = {
        str(entry.get("key")): entry
        for entry in layout_entries
        if entry.get("key") is not None
    }
    if require_layout_translation:
        for group in visible_groups:
            entry = entries_by_key.get(group.key)
            if entry is None:
                errors.append(
                    ValidationIssue(
                        "E_OUTPUT_LAYOUT_ENTRY_MISSING",
                        f"{group.key} has no emitted binary layout entry.",
                    )
                )
                continue
            if not entry.get("translated"):
                errors.append(
                    ValidationIssue(
                        "E_OUTPUT_LAYOUT_NOT_TRANSLATED",
                        f"{group.key} was requested under beautify but was not translated.",
                    )
                )
            reasons = entry.get("coordinate_reason_counts", {})
            if isinstance(reasons, dict) and reasons.get("component_text_or_body"):
                errors.append(
                    ValidationIssue(
                        "E_OUTPUT_LAYOUT_BROAD_SCAN",
                        f"{group.key} used the rejected broad component_text_or_body coordinate scanner.",
                    )
                )
            if entry.get("known_refs_unchanged") is False or entry.get("refs_unchanged") is False:
                errors.append(
                    ValidationIssue(
                        "E_OUTPUT_LAYOUT_REF_CHANGED",
                        f"{group.key} reference text changed during coordinate translation.",
                    )
                )
        placed_entries: list[tuple[str, dict[str, Any]]] = []
        visible_keys = {group.key for group in visible_groups}
        for key, entry in entries_by_key.items():
            if key not in visible_keys or not entry.get("translated"):
                continue
            bbox = entry.get("after_bbox")
            if isinstance(bbox, dict) and {"min_x", "min_y", "max_x", "max_y"} <= set(bbox):
                placed_entries.append((key, bbox))
        overlaps: list[tuple[str, str]] = []
        for left_index, (left_key, left_bbox) in enumerate(placed_entries):
            for right_key, right_bbox in placed_entries[left_index + 1 :]:
                separated = (
                    int(left_bbox["max_x"]) <= int(right_bbox["min_x"])
                    or int(right_bbox["max_x"]) <= int(left_bbox["min_x"])
                    or int(left_bbox["max_y"]) <= int(right_bbox["min_y"])
                    or int(right_bbox["max_y"]) <= int(left_bbox["min_y"])
                )
                if not separated:
                    overlaps.append((left_key, right_key))
        if overlaps:
            errors.append(
                ValidationIssue(
                    "E_OUTPUT_LAYOUT_OVERLAP",
                    f"Beautified visible packet bboxes overlap: {overlaps[:20]}",
                )
            )

    d20_entries = [entry for entry in layout_entries if entry.get("key") == "D20"]
    for entry in d20_entries:
        if entry.get("translated"):
            errors.append(
                ValidationIssue(
                    "E_D20_COORDINATE_MUTATION",
                    "D20 is immutable display infrastructure and must retain donor coordinates.",
                )
            )

    if full_cdb and not allow_full_cdb_mutation:
        try:
            if read_internal_file(project_path, "ROOT.CDB") != read_internal_file(donor_path, "ROOT.CDB"):
                errors.append(
                    ValidationIssue(
                        "E_OUTPUT_FULL_CDB_CHANGED",
                        "full_cdb output does not preserve donor ROOT.CDB byte-for-byte.",
                    )
                )
        except Exception as exc:
            errors.append(ValidationIssue("E_OUTPUT_CDB_COMPARE_FAILED", str(exc)))

    return {
        "stage": "generated_output_validator",
        "valid": not errors,
        "request": dict(sorted(request.items())),
        "actual_counts": dict(sorted(actual_counts.items())),
        "layout_translation_required": require_layout_translation,
        "full_cdb": full_cdb,
        "errors": [issue.as_dict() for issue in errors],
        "warnings": [issue.as_dict() for issue in warnings],
    }


def validate_move_linkage(move_report: dict[str, Any]) -> ComponentPlacerReport:
    errors: list[ValidationIssue] = []
    for item in move_report.get("components", []):
        ref = str(item.get("ref", "<unknown>"))
        body_delta = tuple(item.get("body_delta", (None, None)))
        linked = item.get("linked_deltas", {})
        if not isinstance(linked, dict):
            errors.append(ValidationIssue("E_BEAUTIFIER_LINKAGE_MISSING", f"{ref} linked_deltas must be a mapping."))
            continue
        for field in ("reference_text", "model_text", "name_text", "value_text", "pin_anchor"):
            if field not in linked:
                errors.append(ValidationIssue("E_BEAUTIFIER_LINKAGE_MISSING", f"{ref} missing {field} movement evidence."))
                continue
            if tuple(linked[field]) != body_delta:
                errors.append(
                    ValidationIssue(
                        "E_BEAUTIFIER_TEXT_NOT_MOVED",
                        f"{ref} {field} delta {tuple(linked[field])} does not match body delta {body_delta}.",
                    )
                )
    return ComponentPlacerReport(errors=tuple(errors))


def load_history_validator_rules(path: str | Path | None = None) -> list[dict[str, Any]]:
    rules_path = _repo_path(path or HISTORY_RULES_PATH)
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    rules = data.get("rules", data if isinstance(data, list) else [])
    if not isinstance(rules, list):
        raise ValueError("History validator rules must be a list or an object with a rules list.")
    return rules


def plan_component_placement(payload: Any, *, manifest_path: str | Path | None = None, verify_file_counts: bool = False) -> dict[str, Any]:
    selection = select_removal_only_donor(payload, manifest_path=manifest_path, verify_file_counts=verify_file_counts)
    plan = build_deletion_plan(selection)
    return plan.as_dict()
