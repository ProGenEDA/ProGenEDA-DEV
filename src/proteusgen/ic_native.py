"""Donor-native generator for sequential/native IC and display packets.

This route is deliberately separate from the locked combinational IC route.
Native/sequential ICs, analog ICs, transistors, electrolytic capacitors, and
7-segment displays are emitted from complete user-created donor packets. The
module does not synthesize partial IC records or strip donor CDB/device data.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .cdb import package_ref
from .pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from .reports import summarize_pdsprj
from .resistor_v9 import _extract_object_chunk, _u32
from .templates import FixtureRegistry, repository_root
from .versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

SCHEMA_VERSION = "ic-native-circuit-ir/v0.1"
REGISTRY_PATH = Path("proteus_ic/registry/native_components.json")
BIDIR_MARKER = b"$TERBIDIR"
TERMINAL_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
COMMON_MARKERS = (
    b"$TERBIDIR",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"COMPONENT VALUE",
    b"RESISTOR",
    b"CAPACITOR",
    b"CAP-ELEC",
    b"REALIND",
    b"NPN",
    b"PNP",
    b"LM741",
    b"NE555",
    b"7SEG-COM-AN-BLUE",
    b"7447",
)
PIN_PATTERN = re.compile(r"^(?:(?P<before>.*?)\s*)?PIN\s*(?P<pin>\d+)(?:\s*(?P<after>.*))?$", re.IGNORECASE)
COUNT_OFFSET = 92
PIN_ROW_HEADER_SIZE = 16
PIN_ROW_FOOTER_SIZE = 12
PROPERTY_ROW_HEADER_SIZE = 20
COMPOSE_NATIVE_X_STEP = 5_080_000
COMPOSE_NATIVE_Y_STEP = -5_080_000
COMPOSE_NATIVE_COLUMNS = 6
COMPOSE_LOGIC_X = 33_020_000
COMPOSE_LOGIC_Y = 2_540_000
COMPOSE_LOGIC_X_STEP = 4_572_000
COMPOSE_LOGIC_Y_STEP = -4_064_000
COMPOSE_LOGIC_COLUMNS = 3
COMPOSE_PASSIVE_DX = -2_540_000
COMPOSE_PASSIVE_DY = -20_320_000
COMPONENT_TEXT_FIELDS = (b"COMPONENT ID", b"COMPONENT VALUE", b"SUBCKT NAME")


@dataclass(frozen=True)
class NativeComponent:
    key: str
    aliases: tuple[str, ...]
    marker: str
    terminal_policy: str
    donors: dict[str, Path]
    notes: str = ""
    cdb_rows: str = "normal"


@dataclass(frozen=True)
class BidirEvent:
    index: int
    start: int
    size: int
    label: str
    symbol_x: int
    symbol_y: int
    angle_tenths: int
    suffix: str
    active_link: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "start": self.start,
            "size": self.size,
            "label": self.label,
            "symbol_x": self.symbol_x,
            "symbol_y": self.symbol_y,
            "angle_tenths": self.angle_tenths,
            "suffix": self.suffix,
            "active_link": self.active_link,
        }


@dataclass(frozen=True)
class GenericCdb:
    prefix: bytes
    pin_rows: tuple[tuple[str, bytes], ...]
    between_sections: bytes
    property_rows: tuple[tuple[str, bytes, bool], ...]
    suffix: bytes = b""

    @property
    def count(self) -> int:
        return len(self.pin_rows)

    def pin_package_refs(self) -> list[str]:
        refs: list[str] = []
        for ref, _row in self.pin_rows:
            pkg = package_ref(ref)
            if pkg not in refs:
                refs.append(pkg)
        return refs

    def property_package_refs(self) -> list[str]:
        refs: list[str] = []
        for ref, _row, _original_is_last in self.property_rows:
            pkg = package_ref(ref)
            if pkg not in refs:
                refs.append(pkg)
        return refs


@dataclass(frozen=True)
class NativeValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [{"code": "IC_NATIVE_BLOCKED", "message": item} for item in self.errors],
            "warnings": [{"code": "IC_NATIVE_WARNING", "message": item} for item in self.warnings],
        }


@dataclass(frozen=True)
class NativeGenerationResult:
    output_path: Path
    cdb_path: Path
    dsn_path: Path
    chunk_path: Path
    terminal_plan_path: Path
    manifest_path: Path
    circuit_input_path: Path
    manifest: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "root_cdb_path": str(self.cdb_path),
            "root_dsn_path": str(self.dsn_path),
            "object_chunk_path": str(self.chunk_path),
            "terminal_plan_path": str(self.terminal_plan_path),
            "manifest_path": str(self.manifest_path),
            "circuit_input_path": str(self.circuit_input_path),
            "static_validation_issues": self.manifest["static_validation_issues"],
            "output_hashes": self.manifest["output_hashes"],
        }


class IcNativeGenerationBlocked(Exception):
    def __init__(self, report: NativeValidationReport) -> None:
        super().__init__("Native IC CircuitIR cannot be emitted.")
        self.report = report


class NativeRegistry:
    def __init__(
        self,
        *,
        root: Path,
        components: dict[str, NativeComponent],
        alias_to_key: dict[str, str],
        pair_donors: dict[tuple[str, str], Path],
    ) -> None:
        self.root = root
        self.components = components
        self.alias_to_key = alias_to_key
        self.pair_donors = pair_donors

    @classmethod
    def load(cls, path: str | Path | None = None) -> "NativeRegistry":
        repo = repository_root()
        registry_path = repo / (Path(path) if path is not None else REGISTRY_PATH)
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        donor_root = repo / data["donor_root"]
        components: dict[str, NativeComponent] = {}
        alias_to_key: dict[str, str] = {}
        for key, raw in data["components"].items():
            donors = {kind: donor_root / rel for kind, rel in raw.get("donors", {}).items()}
            component = NativeComponent(
                key=key,
                aliases=tuple(raw.get("aliases", [])),
                marker=raw["marker"],
                terminal_policy=raw.get("terminal_policy", "bidir"),
                donors=donors,
                notes=raw.get("notes", ""),
                cdb_rows=raw.get("cdb_rows", "normal"),
            )
            components[key] = component
            for alias in (key, component.marker, *component.aliases):
                alias_to_key[_token(alias)] = key

        pair_donors: dict[tuple[str, str], Path] = {}
        for pattern in data.get("pair_scan_globs", []):
            for donor in donor_root.glob(pattern):
                parts = _pair_parts_from_name(donor.stem)
                if parts is None:
                    continue
                try:
                    key_a = alias_to_key[_token(parts[0])]
                    key_b = alias_to_key[_token(parts[1])]
                except KeyError:
                    continue
                pair_donors[_pair_key(key_a, key_b)] = donor
        return cls(root=donor_root, components=components, alias_to_key=alias_to_key, pair_donors=pair_donors)

    def normalize(self, value: Any) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Native component part must be a non-empty string.")
        token = _token(value)
        try:
            return self.alias_to_key[token]
        except KeyError as exc:
            raise ValueError(f"Unsupported native component `{value}`.") from exc

    def component(self, value: Any) -> NativeComponent:
        return self.components[self.normalize(value)]

    def pair_donor(self, left: str, right: str) -> Path | None:
        return self.pair_donors.get(_pair_key(left, right))

    def resolve_donor_locator(self, value: Any) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("Native donor locator must be a non-empty string.")
        text = value.strip()
        candidates: list[Path] = []
        if text.lower().endswith(".pdsprj"):
            candidates.extend((self.root / text, repository_root() / text, Path(text)))
        else:
            candidates.append(self.root / "squence" / f"{text}.pdsprj")
            candidates.append(self.root / "squence" / f"PAIR_{text}.pdsprj")
            candidates.append(self.root / f"{text}.pdsprj")
        for candidate in candidates:
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Unknown native donor `{value}`.")


def _token(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _pair_key(left: str, right: str) -> tuple[str, str]:
    return tuple(sorted((left, right)))


def _pair_parts_from_name(stem: str) -> tuple[str, str] | None:
    if not stem.upper().startswith("PAIR_"):
        return None
    body = stem[5:]
    parts = body.rsplit("_", 1)
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def marker_counts(data: bytes, extra_markers: Iterable[str] = ()) -> dict[str, int]:
    markers = {marker for marker in COMMON_MARKERS}
    for marker in extra_markers:
        try:
            markers.add(marker.encode("ascii"))
        except UnicodeEncodeError:
            continue
    return {marker.decode("ascii", errors="replace"): data.count(marker) for marker in sorted(markers)}


def device_section(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise ValueError("ROOT.DSN does not contain the expected device section.")
    return dsn[insert + len(marker) : first]


def build_dsn_with_device_section(
    base_dsn: bytes,
    donor_dsn: bytes,
    object_chunk: bytes,
    donor_device_section: bytes,
) -> tuple[bytes, dict[str, int]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise ValueError("Base or donor ROOT.DSN does not match the accepted section model.")
    insert += len(marker)
    dev = bytearray(donor_device_section)
    first_header = donor_dsn[donor_first : donor_obj + len(b"OBJECT DATA")]
    tail = bytearray(base_dsn[e0_second:])
    first_isis = insert + len(dev)
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b"OBJECT DATA")
    object_data_pointer = second_obj + 13
    if len(dev) >= 4:
        dev[-4:] = _u32(object_data_pointer)
    cct = tail.find(b"CCT000")
    if cct != -1:
        tail[cct + len(b"CCT000") + 2 : cct + len(b"CCT000") + 6] = _u32(first_isis)
    default = tail.find(b"__DEFAULT__\x00\x00")
    if default != -1:
        tail[default + len(b"__DEFAULT__\x00\x00") : default + len(b"__DEFAULT__\x00\x00") + 4] = _u32(second_isis)
    dsn = bytes(bytearray(base_dsn[:insert]) + dev + first_header + bytearray(object_chunk) + tail)
    return dsn, {
        "insert": insert,
        "first_isis": first_isis,
        "second_isis": second_isis,
        "second_object_data": second_obj,
        "object_data_pointer": object_data_pointer,
        "device_section_size": len(dev),
    }


def bidir_events(chunk: bytes) -> list[BidirEvent]:
    events: list[BidirEvent] = []
    position = 0
    while True:
        marker = chunk.find(BIDIR_MARKER, position)
        if marker < 0:
            return events
        start = marker - 14
        if start < 0 or chunk[start] != 0x10:
            raise ValueError(f"Invalid bidirectional terminal start at marker {marker}.")
        label_length = chunk[start + 30]
        size = 101 + label_length
        record = chunk[start : start + size]
        label = record[31 : 31 + label_length].decode("ascii", errors="replace")
        symbol_x, symbol_y = struct.unpack("<ii", record[1:9])
        angle = struct.unpack("<I", record[9:13])[0]
        suffix = struct.unpack("<H", record[-4:-2])[0]
        events.append(
            BidirEvent(
                index=len(events),
                start=start,
                size=size,
                label=label,
                symbol_x=symbol_x,
                symbol_y=symbol_y,
                angle_tenths=angle,
                suffix=f"{suffix:04x}",
                active_link=record[-2],
            )
        )
        position = marker + 1


def rebuild_bidir_record(record: bytes, new_label: str) -> bytes:
    raw = new_label.encode("ascii")
    if not raw or len(raw) > 255:
        raise ValueError(f"Invalid bidirectional terminal label {new_label!r}.")
    old_length = record[30]
    old_label_offset = 31 + old_length
    old_label_coords = record[old_label_offset : old_label_offset + 8]
    rebuilt = bytearray(record[:30] + bytes([len(raw)]) + raw + record[31 + old_length :])
    new_label_offset = 31 + len(raw)
    rebuilt[new_label_offset : new_label_offset + 8] = old_label_coords
    return bytes(rebuilt)


def patch_bidir_labels(chunk: bytes, replacements_by_index: dict[int, str]) -> tuple[bytes, list[dict[str, Any]]]:
    if not replacements_by_index:
        return chunk, []
    events = bidir_events(chunk)
    out = bytearray(chunk)
    mutations: list[dict[str, Any]] = []
    for index, event in reversed(list(enumerate(events))):
        new_label = replacements_by_index.get(index)
        if new_label is None:
            continue
        start = event.start
        size = event.size
        old_record = chunk[start : start + size]
        new_record = rebuild_bidir_record(old_record, new_label)
        out[start : start + size] = new_record
        mutations.append(
            {
                "index": index,
                "old": event.label,
                "new": new_label,
                "old_size": size,
                "new_size": len(new_record),
            }
        )
    out[-1] = 0xFF
    return bytes(out), sorted(mutations, key=lambda item: int(item["index"]))


def build_dsn_with_device_sections(
    base_dsn: bytes,
    donor_dsn: bytes,
    object_chunk: bytes,
    sections: list[dict[str, Any]],
) -> tuple[bytes, dict[str, Any]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise ValueError("Base or donor ROOT.DSN does not match the accepted section model.")
    insert += len(marker)
    first_header = donor_dsn[donor_first : donor_obj + len(b"OBJECT DATA")]
    tail = bytearray(base_dsn[e0_second:])
    device_payload = bytearray()
    first_isis = insert
    section_pointers: list[dict[str, Any]] = []
    for section_index, section in enumerate(sections):
        section_bytes = bytearray(section["section"])
        section_start = insert + len(device_payload)
        first_isis += len(section_bytes)
        section_pointers.append(
            {
                "index": section_index,
                "donor_key": section.get("donor_key"),
                "donor": section.get("donor"),
                "section_start": section_start,
                "section_size": len(section_bytes),
            }
        )
        device_payload.extend(section_bytes)
    first_isis = insert + len(device_payload)
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b"OBJECT DATA")
    object_data_pointer = second_obj + 13
    cursor = 0
    for pointer in section_pointers:
        section_size = int(pointer["section_size"])
        if section_size >= 4:
            device_payload[cursor + section_size - 4 : cursor + section_size] = _u32(object_data_pointer)
            pointer["patched_tail_pointer"] = object_data_pointer
        cursor += section_size
    cct = tail.find(b"CCT000")
    if cct != -1:
        tail[cct + len(b"CCT000") + 2 : cct + len(b"CCT000") + 6] = _u32(first_isis)
    default = tail.find(b"__DEFAULT__\x00\x00")
    if default != -1:
        tail[default + len(b"__DEFAULT__\x00\x00") : default + len(b"__DEFAULT__\x00\x00") + 4] = _u32(second_isis)
    dsn = bytes(bytearray(base_dsn[:insert]) + device_payload + first_header + bytearray(object_chunk) + tail)
    return dsn, {
        "insert": insert,
        "first_isis": first_isis,
        "second_isis": second_isis,
        "second_object_data": second_obj,
        "object_data_pointer": object_data_pointer,
        "device_section_size": len(device_payload),
        "sections": section_pointers,
    }


def _s32(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)


def _add_s32(data: bytearray, offset: int, delta: int) -> None:
    _put_s32(data, offset, _s32(data, offset) + delta)


def _coord_pairs_for_terminal_records(chunk: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True), (b"$TERBIDIR", False)):
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            start = marker_pos - 14
            if start >= 0:
                pairs.append((start + 1, start + 5))
                length_pos = marker_pos + (17 if output_terminal else 16)
                label_pos = marker_pos + (18 if output_terminal else 17)
                if length_pos < len(chunk):
                    label_length = chunk[length_pos]
                    label_coord = label_pos + label_length
                    if label_coord + 8 <= len(chunk):
                        pairs.append((label_coord, label_coord + 4))
            pos = marker_pos + 1
    return pairs


def _coord_pairs_for_wires(chunk: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    pos = 0
    while True:
        marker = chunk.find(b"WIRE", pos)
        if marker < 0:
            return pairs
        coord = marker + 9
        if coord + 16 <= len(chunk):
            pairs.append((coord, coord + 4))
            pairs.append((coord + 8, coord + 12))
        pos = marker + 1


def _coord_pairs_for_bodies(chunk: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for raw_marker in sorted({marker for marker in COMMON_MARKERS if marker.isascii() and marker}):
        needle = bytes([len(raw_marker)]) + raw_marker
        pos = 0
        while True:
            found = chunk.find(needle, pos)
            if found < 0:
                break
            if found >= 2 and chunk[found - 1] == 0 and chunk[found - 2] != 0xFF:
                x_offset = found + len(needle)
                y_offset = x_offset + 4
                if y_offset + 4 <= len(chunk):
                    pairs.append((x_offset, y_offset))
            pos = found + 1
    return pairs


def _coord_pairs_for_component_text_records(chunk: bytes) -> list[tuple[int, int]]:
    pairs: list[tuple[int, int]] = []
    for field in COMPONENT_TEXT_FIELDS:
        marker = field + b"\x00\x00\x00\x00\x00\xff"
        pos = 0
        while True:
            found = chunk.find(marker, pos)
            if found < 0:
                break
            length_pos = found + len(marker)
            if length_pos < len(chunk):
                value_length = chunk[length_pos]
                x_offset = length_pos + 1 + value_length
                y_offset = x_offset + 4
                if y_offset + 4 <= len(chunk):
                    pairs.append((x_offset, y_offset))
            pos = found + 1
    return pairs


def translate_chunk(chunk: bytes, dx: int, dy: int) -> tuple[bytes, dict[str, Any]]:
    if not dx and not dy:
        return chunk, {"dx": dx, "dy": dy, "coordinate_pair_count": 0}
    out = bytearray(chunk)
    pairs = (
        _coord_pairs_for_terminal_records(chunk)
        + _coord_pairs_for_wires(chunk)
        + _coord_pairs_for_bodies(chunk)
        + _coord_pairs_for_component_text_records(chunk)
    )
    seen: set[tuple[int, int]] = set()
    unique_pairs: list[tuple[int, int]] = []
    for pair in pairs:
        if pair in seen:
            continue
        seen.add(pair)
        unique_pairs.append(pair)
    for x_offset, y_offset in unique_pairs:
        _add_s32(out, x_offset, dx)
        _add_s32(out, y_offset, dy)
    return bytes(out), {"dx": dx, "dy": dy, "coordinate_pair_count": len(unique_pairs)}


def _read_u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ValueError("Unexpected end of CDB while reading u32.")
    return int.from_bytes(data[offset : offset + 4], "little")


def _read_lp_ascii(data: bytes, offset: int) -> tuple[str, int]:
    if offset >= len(data):
        raise ValueError("Unexpected end of CDB while reading string length.")
    length = data[offset]
    start = offset + 1
    end = start + length
    if end > len(data):
        raise ValueError("Unexpected end of CDB while reading string body.")
    return data[start:end].decode("ascii", errors="replace"), end


def _skip_lp_ascii(data: bytes, offset: int) -> int:
    _value, end = _read_lp_ascii(data, offset)
    return end


def _ordered_unique_package_refs_from_pin_rows(pin_rows: list[tuple[str, bytes]]) -> tuple[str, ...]:
    refs: list[str] = []
    for ref, _row in pin_rows:
        pkg = package_ref(ref)
        if pkg not in refs:
            refs.append(pkg)
    return tuple(refs)


def _parse_property_rows_at(
    data: bytes,
    start: int,
    expected_refs: tuple[str, ...],
) -> tuple[list[tuple[str, bytes, bool]], int] | None:
    rows: list[tuple[str, bytes, bool]] = []
    pos = start
    for index, expected_ref in enumerate(expected_refs):
        row_start = pos
        if row_start + PROPERTY_ROW_HEADER_SIZE > len(data):
            return None
        pos += PROPERTY_ROW_HEADER_SIZE
        try:
            ref, pos = _read_lp_ascii(data, pos)
        except ValueError:
            return None
        if ref != expected_ref:
            return None
        try:
            for _field_index in range(3):
                pos = _skip_lp_ascii(data, pos)
            property_length = _read_u32(data, pos)
        except ValueError:
            return None
        computed_end = pos + 4 + property_length
        if computed_end > len(data):
            return None
        if index == len(expected_refs) - 1:
            row_end = computed_end
            pos = row_end
        else:
            row_end = computed_end - 4
            if row_end <= row_start:
                return None
            pos = row_end
        rows.append((ref, data[row_start:row_end], index == len(expected_refs) - 1))
    return rows, pos


def split_cdb_generic(data: bytes) -> GenericCdb:
    if len(data) < COUNT_OFFSET + 4:
        raise ValueError("ROOT.CDB is too short.")
    count = _read_u32(data, COUNT_OFFSET)
    pos = COUNT_OFFSET + 4
    pin_rows: list[tuple[str, bytes]] = []
    for _index in range(count):
        row_start = pos
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
        pin_rows.append((ref, data[row_start:pos]))
    pin_end = pos
    expected_refs = _ordered_unique_package_refs_from_pin_rows(pin_rows)
    property_rows: list[tuple[str, bytes, bool]] | None = None
    property_start = None
    property_end = None
    for candidate in range(pin_end, len(data)):
        parsed = _parse_property_rows_at(data, candidate, expected_refs)
        if parsed is None:
            continue
        property_rows, property_end = parsed
        property_start = candidate
        break
    if property_start is None:
        raise ValueError("Could not locate CDB property row.")
    return GenericCdb(
        prefix=data[:COUNT_OFFSET],
        pin_rows=tuple(pin_rows),
        between_sections=data[pin_end:property_start],
        property_rows=tuple(property_rows or []),
        suffix=data[property_end or len(data) :],
    )


def patch_refs(data: bytes, ref_map: dict[str, str]) -> bytes:
    if not ref_map:
        return data

    def repl(match: re.Match[bytes]) -> bytes:
        old = match.group().decode("ascii")
        pkg = package_ref(old)
        new_pkg = ref_map.get(pkg, pkg)
        return (new_pkg + old[len(pkg) :]).encode("ascii")

    return re.sub(rb"U\d+(?::[A-Z])?", repl, data)


def _u32_at(row: bytes, offset: int) -> int | None:
    if len(row) < offset + 4:
        return None
    return int.from_bytes(row[offset : offset + 4], "little")


def _patch_u32(row: bytes, offset: int, value: int) -> bytes:
    if len(row) < offset + 4:
        return row
    out = bytearray(row)
    out[offset : offset + 4] = value.to_bytes(4, "little")
    return bytes(out)


def _duplicates(values: list[int]) -> list[int]:
    seen: set[int] = set()
    dupes: set[int] = set()
    for value in values:
        if value in seen:
            dupes.add(value)
        seen.add(value)
    return sorted(dupes)


def renumber_cdb_ids(pin_rows, property_rows):
    before = {
        "pin_primary_ids": [item for _ref, row in pin_rows if (item := _u32_at(row, 0)) is not None],
        "pin_secondary_ids": [item for _ref, row in pin_rows if len(row) >= 16 and (item := _u32_at(row, 12)) is not None],
        "property_ids": [item for _ref, row, _last in property_rows if (item := _u32_at(row, 0)) is not None],
    }
    new_pin_rows = []
    package_first_ids: dict[str, int] = {}
    row_plan: list[dict[str, Any]] = []
    for new_id, (ref, row) in enumerate(pin_rows, start=1):
        old_primary = _u32_at(row, 0)
        old_secondary = _u32_at(row, 12) if len(row) >= 16 else None
        updated = _patch_u32(row, 0, new_id)
        if len(updated) >= 16:
            updated = _patch_u32(updated, 12, new_id)
        new_pin_rows.append((ref, updated))
        package_first_ids.setdefault(package_ref(ref), new_id)
        row_plan.append(
            {
                "row_type": "pin",
                "ref": ref,
                "old_primary_id": old_primary,
                "old_secondary_id": old_secondary,
                "new_id": new_id,
                "changed": old_primary != new_id or (old_secondary is not None and old_secondary != new_id),
            }
        )
    used_property_ids: set[int] = set()
    next_property_id = 1
    new_property_rows = []
    for ref, row, original_is_last in property_rows:
        old_id = _u32_at(row, 0)
        new_id = package_first_ids.get(package_ref(ref))
        if new_id is None or new_id in used_property_ids:
            while next_property_id in used_property_ids:
                next_property_id += 1
            new_id = next_property_id
        used_property_ids.add(new_id)
        new_property_rows.append((ref, _patch_u32(row, 0, new_id), original_is_last))
        row_plan.append({"row_type": "property", "ref": ref, "old_id": old_id, "new_id": new_id, "changed": old_id != new_id})
    after = {
        "pin_primary_ids": [_u32_at(row, 0) for _ref, row in new_pin_rows],
        "pin_secondary_ids": [_u32_at(row, 12) for _ref, row in new_pin_rows if len(row) >= 16],
        "property_ids": [_u32_at(row, 0) for _ref, row, _last in new_property_rows],
    }
    after_clean = {key: [item for item in values if item is not None] for key, values in after.items()}
    return new_pin_rows, new_property_rows, {
        "mode": "renumbered_all_cdb_ids_for_composed_native_output",
        "duplicates_before": {key: _duplicates(values) for key, values in before.items()},
        "duplicates_after": {key: _duplicates(values) for key, values in after_clean.items()},
        "before": before,
        "after": after_clean,
        "row_plan": row_plan,
    }


def build_cdb_from_generic_parts(parts: list[GenericCdb]) -> tuple[bytes, dict[str, Any]]:
    if not parts:
        raise ValueError("Cannot build ROOT.CDB without at least one CDB source.")
    template = parts[0]
    pin_rows = [row for part in parts for row in part.pin_rows]
    property_rows = [row for part in parts for row in part.property_rows]
    pin_rows, property_rows, id_plan = renumber_cdb_ids(pin_rows, property_rows)
    prefix = bytearray(template.prefix)
    prefix.extend(len(pin_rows).to_bytes(4, "little"))
    property_payloads: list[bytes] = []
    for index, (_ref, row, original_is_last) in enumerate(property_rows):
        if original_is_last and index != len(property_rows) - 1:
            if len(row) < 4:
                raise ValueError("Cannot trim donor-final CDB property row shorter than 4 bytes.")
            property_payloads.append(row[:-4])
        else:
            property_payloads.append(row)
    cdb = bytes(prefix) + b"".join(row for _ref, row in pin_rows) + template.between_sections + b"".join(property_payloads) + template.suffix
    return cdb, {
        "count": len(pin_rows),
        "pin_refs": [ref for ref, _row in pin_rows],
        "property_refs": [ref for ref, _row, _last in property_rows],
        "cdb_id_plan": id_plan,
    }


def patch_bidir_suffixes(chunk: bytes, suffix_start: int) -> tuple[bytes, list[dict[str, Any]]]:
    original = bytes(chunk)
    out = bytearray(chunk)
    plan: list[dict[str, Any]] = []
    events = bidir_events(original)
    for local_index, event in enumerate(events):
        new_suffix = suffix_start + local_index
        if new_suffix > 0xFFFF:
            raise ValueError("Bidirectional suffix allocation overflowed 16-bit field.")
        old_suffix = int(event.suffix, 16)
        old_token = old_suffix.to_bytes(2, "little") + bytes([event.active_link, 0])
        new_token = new_suffix.to_bytes(2, "little") + bytes([event.active_link, 0])
        positions: list[int] = []
        cursor = 0
        while True:
            found = original.find(old_token, cursor)
            if found < 0:
                break
            positions.append(found)
            cursor = found + 1
        if not positions:
            record_end = event.start + event.size
            positions = [record_end - 4]
        for offset in positions:
            out[offset : offset + 4] = new_token
        plan.append(
            {
                "index": event.index,
                "old_suffix": event.suffix,
                "new_suffix": f"{new_suffix:04x}",
                "label": event.label,
                "patched_link_token_occurrences": len(positions),
                "patched_offsets": positions,
            }
        )
    out[-1] = 0xFF
    return bytes(out), plan


def parse_pin_label(label: str) -> dict[str, str]:
    normalized = " ".join(label.replace("(", "").replace(")", "").split())
    match = PIN_PATTERN.match(normalized)
    if not match:
        return {"signal": normalized, "pin": "", "normalized": normalized}
    before = (match.group("before") or "").strip()
    after = (match.group("after") or "").strip()
    signal = before or after
    return {"signal": signal, "pin": match.group("pin"), "normalized": normalized}


def analyze_donor(path: str | Path) -> dict[str, Any]:
    donor = Path(path)
    dsn = read_internal_file(donor, "ROOT.DSN")
    cdb = read_internal_file(donor, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    terminals = [event.as_dict() | parse_pin_label(event.label) for event in bidir_events(chunk)]
    return {
        "path": str(donor),
        "members": [
            {"name": row.name, "size": row.size, "sha256": row.sha256}
            for row in summarize_pdsprj(donor)
        ],
        "hashes": {
            "PROJECT.XML": _sha256_bytes(read_internal_file(donor, "PROJECT.XML")),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "SCRIPTS/PWRRAILS.DAT": _sha256_bytes(read_internal_file(donor, "SCRIPTS/PWRRAILS.DAT")),
            "object_chunk": _sha256_bytes(chunk),
        },
        "object_chunk_size": len(chunk),
        "marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "device_section_size": len(device_section(dsn)),
        "bidir_terminals": terminals,
    }


def _components_from_payload(payload: dict[str, Any], registry: NativeRegistry) -> list[dict[str, Any]]:
    raw_components = payload.get("components", [])
    if not isinstance(raw_components, list):
        raise ValueError("`components` must be a list.")
    components: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_components):
        if not isinstance(raw, dict):
            raise ValueError(f"`components[{index}]` must be an object.")
        part = registry.normalize(raw.get("part") or raw.get("type") or raw.get("family"))
        ref = raw.get("ref") or raw.get("id") or f"U{index + 1}"
        if not isinstance(ref, str) or not ref:
            raise ValueError(f"`components[{index}].ref` must be a non-empty string.")
        components.append({"ref": ref, "part": part, "raw": raw})
    return components


def _connection_map(payload: dict[str, Any], components: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    by_ref: dict[str, dict[str, str]] = {str(component["ref"]): {} for component in components}
    for component in components:
        raw_connections = component["raw"].get("connections", {})
        if isinstance(raw_connections, dict):
            for pin, net in raw_connections.items():
                by_ref[str(component["ref"])][_pin_key(pin)] = _net_label(net)
        elif raw_connections:
            raise ValueError(f"`components[{component['ref']}].connections` must be an object.")
    raw_global = payload.get("connections", [])
    if not isinstance(raw_global, list):
        raise ValueError("`connections` must be a list when provided.")
    for index, item in enumerate(raw_global):
        if not isinstance(item, dict):
            raise ValueError(f"`connections[{index}]` must be an object.")
        ref = item.get("component") or item.get("ref") or item.get("id")
        pin = item.get("pin") or item.get("signal")
        net = item.get("net") or item.get("node") or item.get("label")
        if not isinstance(ref, str) or ref not in by_ref:
            raise ValueError(f"`connections[{index}]` references unknown component {ref!r}.")
        by_ref[ref][_pin_key(pin)] = _net_label(net)
    return by_ref


def _pin_key(value: Any) -> str:
    if value is None:
        raise ValueError("Connection pin/signal must be provided.")
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _net_label(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Connection net label must be a non-empty string.")
    value.encode("ascii")
    if len(value) > 255:
        raise ValueError("Connection net label is too long for a Proteus terminal label.")
    return value


def _safe_signal(value: str, fallback: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]", "", value.upper())[:8]
    return safe or fallback


def _labels_for_events(
    *,
    donor_chunk: bytes,
    components: list[dict[str, Any]],
    component_single_counts: dict[str, int],
    connection_map: dict[str, dict[str, str]],
) -> tuple[dict[int, str], list[dict[str, Any]]]:
    if not components:
        return {}, []
    events = bidir_events(donor_chunk)
    if not events:
        return {}, []
    replacements: dict[int, str] = {}
    plan: list[dict[str, Any]] = []
    if len({str(component["part"]) for component in components}) == 1:
        single_count = component_single_counts.get(str(components[0]["part"])) or len(events)
        component_for_index = lambda index: components[min(index // single_count, len(components) - 1)]
    else:
        # Pair donors in the manual corpus usually store complete IC packets in
        # order. Without trustworthy unit slicing, divide terminals by known
        # single donor counts only for label assignment; object bytes stay whole.
        ranges: list[tuple[int, int, dict[str, Any]]] = []
        cursor = 0
        for component in components:
            count = component_single_counts.get(str(component["part"]), 0)
            if count <= 0:
                count = max(1, len(events) // len(components))
            ranges.append((cursor, cursor + count, component))
            cursor += count

        def component_for_index(index: int) -> dict[str, Any]:
            for start, end, component in ranges:
                if start <= index < end:
                    return component
            return components[-1]

    for event in events:
        component = component_for_index(event.index)
        ref = str(component["ref"])
        parsed = parse_pin_label(event.label)
        signal = parsed["signal"] or f"P{event.index:02d}"
        pin = parsed["pin"]
        mapping = connection_map.get(ref, {})
        explicit = None
        for key in (_pin_key(pin) if pin else "", _pin_key(signal), _pin_key(event.label)):
            if key and key in mapping:
                explicit = mapping[key]
                break
        if explicit is None:
            signal_part = _safe_signal(signal, f"P{event.index:02d}")
            pin_part = pin or f"X{event.index:02d}"
            explicit = f"{ref}{signal_part}{pin_part}"
        replacements[event.index] = explicit
        plan.append(
            {
                "terminal_index": event.index,
                "component_ref": ref,
                "component_part": component["part"],
                "old_label": event.label,
                "new_label": explicit,
                "signal": signal,
                "pin": pin,
                "source": "connection" if explicit in mapping.values() else "generated_unique",
            }
        )
    return replacements, plan


def _donor_for_components(
    payload: dict[str, Any],
    registry: NativeRegistry,
    components: list[dict[str, Any]],
) -> tuple[Path, str, list[str]]:
    donor_locator = payload.get("donor") or payload.get("donor_key")
    if donor_locator:
        donor = registry.resolve_donor_locator(donor_locator)
        return donor, "explicit_donor", [str(component["part"]) for component in components]
    if not components:
        raise ValueError("Native generation requires `components` or an explicit `donor`.")
    parts = [str(component["part"]) for component in components]
    if len(set(parts)) == 1:
        component = registry.components[parts[0]]
        requested_kind = payload.get("donor_kind")
        if requested_kind is not None:
            if not isinstance(requested_kind, str):
                raise ValueError("`donor_kind` must be a string.")
            kind = requested_kind
        else:
            kind = {1: "single", 2: "two", 4: "four", 8: "eight"}.get(len(components), "")
        if kind and kind in component.donors:
            return component.donors[kind], f"same_family_{kind}_donor", parts
        raise ValueError(f"No complete donor kind `{kind or len(components)}` for {component.key}.")
    if len(components) == 2:
        donor = registry.pair_donor(parts[0], parts[1])
        if donor is not None:
            return donor, "manual_pair_donor", parts
    raise ValueError(
        "No complete manual donor covers this native component set. "
        "Provide a `donor`/`donor_key` from manual_downloads_20260611 or add a clean pair donor first."
    )


def _single_terminal_counts(registry: NativeRegistry, parts: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for part in set(parts):
        component = registry.components.get(part)
        if component is None or "single" not in component.donors or not component.donors["single"].exists():
            counts[part] = 0
            continue
        chunk = _extract_object_chunk(read_internal_file(component.donors["single"], "ROOT.DSN"))
        counts[part] = len(bidir_events(chunk))
    return counts


def _has_direct_same_family_donor(payload: dict[str, Any], registry: NativeRegistry, components: list[dict[str, Any]]) -> bool:
    if not components:
        return False
    parts = [str(component["part"]) for component in components]
    if len(set(parts)) != 1:
        return False
    component = registry.components[parts[0]]
    requested_kind = payload.get("donor_kind")
    if requested_kind is not None:
        return isinstance(requested_kind, str) and requested_kind in component.donors
    kind = {1: "single", 2: "two", 4: "four", 8: "eight"}.get(len(components), "")
    return bool(kind and kind in component.donors)


def _direct_same_family_donor(
    payload: dict[str, Any],
    registry: NativeRegistry,
    components: list[dict[str, Any]],
) -> tuple[Path, str, list[str]] | None:
    if not components:
        return None
    parts = [str(component["part"]) for component in components]
    if len(set(parts)) != 1:
        return None
    component = registry.components[parts[0]]
    requested_kind = payload.get("donor_kind")
    if requested_kind is not None:
        if not isinstance(requested_kind, str):
            raise ValueError("`donor_kind` must be a string.")
        kind = requested_kind
    else:
        kind = {1: "single", 2: "two", 4: "four", 8: "eight"}.get(len(components), "")
    if kind and kind in component.donors:
        return component.donors[kind], f"same_family_{kind}_donor", parts
    return None


def _requires_composed_generation(payload: dict[str, Any], registry: NativeRegistry, components: list[dict[str, Any]]) -> bool:
    if payload.get("compose") or payload.get("clone_from_donor") or payload.get("logic_gates") or payload.get("passives"):
        return True
    if not components or payload.get("donor") or payload.get("donor_key"):
        return False
    parts = [str(component["part"]) for component in components]
    if len(set(parts)) == 1 and not _has_direct_same_family_donor(payload, registry, components):
        return True
    return False


def _internal_ref_allocator(reserved: set[str]):
    tokens = [f"{letter}{digit}" for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" for digit in "123456789"]
    for token in tokens:
        if token in reserved:
            continue
        reserved.add(token)
        yield token


def _refs_in_bytes(data: bytes) -> list[str]:
    return sorted(set(match.group().decode("ascii") for match in re.finditer(rb"U\d+(?::[A-Z])?", data)))


def _clone_internal_refs(components: list[dict[str, Any]], *, reserve_u_refs: bool) -> dict[str, str]:
    reserved = {f"U{index}" for index in range(1, 10)} if reserve_u_refs else set()
    allocator = _internal_ref_allocator(reserved)
    result: dict[str, str] = {}
    for component in components:
        requested = str(component["ref"])
        if len(requested) == 2 and requested not in reserved and requested not in result.values():
            internal = requested
            reserved.add(internal)
        else:
            internal = next(allocator)
        result[requested] = internal
    return result


def _single_donor_for_component(payload: dict[str, Any], registry: NativeRegistry, component: dict[str, Any]) -> Path:
    explicit = component["raw"].get("clone_from_donor") or component["raw"].get("donor")
    if explicit:
        return registry.resolve_donor_locator(explicit)
    global_clone = payload.get("clone_from_donor")
    if global_clone:
        return registry.resolve_donor_locator(global_clone)
    native = registry.components[str(component["part"])]
    donor = native.donors.get("single")
    if donor is None:
        raise ValueError(f"{native.key} has no clean single donor for composed generation.")
    return donor


def _component_connection_label(
    *,
    event: BidirEvent,
    component: dict[str, Any],
    connection_map: dict[str, dict[str, str]],
) -> tuple[str, str, str, str]:
    parsed = parse_pin_label(event.label)
    signal = parsed["signal"] or f"P{event.index:02d}"
    pin = parsed["pin"]
    mapping = connection_map.get(str(component["ref"]), {})
    for key in (_pin_key(pin) if pin else "", _pin_key(signal), _pin_key(event.label)):
        if key and key in mapping:
            return mapping[key], signal, pin, "connection"
    signal_part = _safe_signal(signal, f"P{event.index:02d}")
    pin_part = pin or f"X{event.index:02d}"
    return f"{component['ref']}{signal_part}{pin_part}", signal, pin, "generated_unique"


def _component_grid_offset(index: int, payload: dict[str, Any], ref: str) -> tuple[int, int]:
    layout = payload.get("layout", {})
    if isinstance(layout, dict):
        positions = layout.get("component_positions", {})
        if isinstance(positions, dict) and ref in positions and isinstance(positions[ref], dict):
            raw = positions[ref]
            return int(raw.get("x", 0)), int(raw.get("y", 0))
    col = index % COMPOSE_NATIVE_COLUMNS
    row = index // COMPOSE_NATIVE_COLUMNS
    return col * COMPOSE_NATIVE_X_STEP, row * COMPOSE_NATIVE_Y_STEP


def _logic_package_position(package_number: int) -> tuple[int, int]:
    zero = package_number - 1
    return (
        COMPOSE_LOGIC_X + (zero % COMPOSE_LOGIC_COLUMNS) * COMPOSE_LOGIC_X_STEP,
        COMPOSE_LOGIC_Y + (zero // COMPOSE_LOGIC_COLUMNS) * COMPOSE_LOGIC_Y_STEP,
    )


def _parse_logic_gates(payload: dict[str, Any]):
    from . import ic_combinational as ic

    raw_gates = payload.get("logic_gates") or payload.get("gates") or []
    if not isinstance(raw_gates, list):
        raise ValueError("`logic_gates` must be a list.")
    gates = []
    family_counts: dict[str, int] = {}
    for index, raw in enumerate(raw_gates):
        if not isinstance(raw, dict):
            raise ValueError(f"`logic_gates[{index}]` must be an object.")
        family = str(raw.get("family") or raw.get("part") or raw.get("type") or "").lower()
        if family not in ic.FAMILIES:
            raise ValueError(f"Unsupported combinational gate family `{family}`.")
        config = ic.FAMILIES[family]
        count = family_counts.get(family, 0)
        family_counts[family] = count + 1
        gate = str(raw.get("gate") or config.letters[count % len(config.letters)]).upper()
        if gate not in config.letters:
            raise ValueError(f"Unsupported gate letter `{gate}` for {family}.")
        left = _net_label(raw.get("left") or raw.get("a") or raw.get("in1"))
        right = "" if config.input_count == 1 else _net_label(raw.get("right") or raw.get("b") or raw.get("in2"))
        output = _net_label(raw.get("output") or raw.get("out") or raw.get("y"))
        gates.append(ic.GateSpec(family, gate, left, right, output, str(raw.get("note", "")), str(raw.get("package", ""))))
    return tuple(gates)


def _parse_passives(payload: dict[str, Any]):
    from . import ic_combinational as ic

    raw_passives = payload.get("passives") or []
    if not isinstance(raw_passives, list):
        raise ValueError("`passives` must be a list.")
    passives = []
    counters = {"R": 0, "C": 0, "L": 0}
    for index, raw in enumerate(raw_passives):
        if not isinstance(raw, dict):
            raise ValueError(f"`passives[{index}]` must be an object.")
        kind = str(raw.get("kind") or raw.get("type") or "").upper()
        kind = {"RESISTOR": "R", "CAPACITOR": "C", "INDUCTOR": "L"}.get(kind, kind)
        if kind not in counters:
            raise ValueError(f"Unsupported passive kind `{kind}`.")
        counters[kind] += 1
        ref = str(raw.get("ref") or f"{kind}{counters[kind]}")
        value = str(raw.get("value") or {"R": "10k", "C": "1uF", "L": "5mH"}[kind])
        left = _net_label(raw.get("left") or raw.get("from") or raw.get("a"))
        right = _net_label(raw.get("right") or raw.get("to") or raw.get("b"))
        passives.append(ic.PassiveSpec(ref, kind, value, left, right))
    return tuple(passives)


def _generated_logic_and_passive_records(
    payload: dict[str, Any],
    first_object_id: int,
    *,
    first_package_number: int = 1,
):
    from . import ic_combinational as ic

    gates = _parse_logic_gates(payload)
    passives = _parse_passives(payload)
    records: list[bytes] = []
    topology: list[dict[str, Any]] = []
    if first_package_number == 1:
        assignments, package_rows = ic._package_assignments(gates)
    else:
        assignments = []
        package_rows = []
        explicit: dict[tuple[str, str], int] = {}
        state: dict[str, list[dict[str, Any]]] = {}

        def next_package(family: str, package_ref: str | None = None) -> dict[str, Any]:
            if package_ref is None:
                package_number = first_package_number + len(package_rows)
                package_ref = f"U{package_number}"
            else:
                if not package_ref.startswith("U") or not package_ref[1:].isdigit():
                    raise ValueError(f"IC package refs must be U1..U9: {package_ref!r}")
                package_number = int(package_ref[1:])
                if package_number < first_package_number:
                    raise ValueError(
                        f"Generated package {package_ref} collides with native donor packages below U{first_package_number}."
                    )
            if package_number > 9 or len(package_ref) != 2:
                raise ValueError(
                    "Native-plus-combinational generation currently supports generated gate packages only through U9."
                )
            row = {
                "family": family,
                "device": ic.FAMILIES[family].device,
                "package_ref": package_ref,
                "package_number": package_number,
                "used_gates": set(),
            }
            package_rows.append(row)
            return row

        for gate in gates:
            config = ic.FAMILIES[gate.family]
            if gate.package:
                key = (gate.family, gate.package)
                if key not in explicit:
                    explicit[key] = len(package_rows)
                    state.setdefault(gate.family, []).append(next_package(gate.family, gate.package))
                row = package_rows[explicit[key]]
                used = row["used_gates"]
                assert isinstance(used, set)
                if gate.gate in used:
                    raise ValueError(f"Duplicate gate {gate.package}:{gate.gate} in {gate.family}.")
                used.add(gate.gate)
            else:
                family_rows = state.setdefault(gate.family, [])
                if not family_rows:
                    family_rows.append(next_package(gate.family))
                row = family_rows[-1]
                used = row["used_gates"]
                assert isinstance(used, set)
                if gate.gate in used or len(used) >= len(config.letters):
                    row = next_package(gate.family)
                    family_rows.append(row)
                    used = row["used_gates"]
                    assert isinstance(used, set)
                used.add(gate.gate)
            assignments.append((str(row["package_ref"]), int(row["package_number"])))
        package_rows = [
            {
                "family": str(row["family"]),
                "device": ic.FAMILIES[str(row["family"])].device,
                "package_ref": str(row["package_ref"]),
                "package_number": int(row["package_number"]),
            }
            for row in package_rows
        ]
    for offset, (gate, (package_ref_value, package_number)) in enumerate(zip(gates, assignments)):
        config = ic.FAMILIES[gate.family]
        object_id = first_object_id + offset
        dx, dy = _logic_package_position(package_number)
        if config.shape in {"hc08_script", "hc32_script"}:
            record, row = ic._script_gate_record(
                config,
                gate,
                package_ref=package_ref_value,
                package_number=package_number,
                object_id=object_id,
                dx=dx,
                dy=dy,
            )
        else:
            record, row = ic._generic_gate_record(
                config,
                gate,
                package_ref=package_ref_value,
                object_id=object_id,
                dx=dx,
                dy=dy,
            )
        records.append(record)
        topology.append(row)
    passive_first_object_id = first_object_id + len(gates)
    passive_case = ic.CircuitCase("native_composed_passives", "native composed passives", "", "", gates, passives)
    passive_chunk, passive_specs, passive_topology, passive_replacements, passive_issues = ic.build_passive_chunk(
        passive_case,
        passive_first_object_id,
    )
    if passive_chunk:
        passive_chunk, passive_translation = translate_chunk(passive_chunk, COMPOSE_PASSIVE_DX, COMPOSE_PASSIVE_DY)
        passive_payload = passive_chunk[1:-1]
    else:
        passive_translation = {}
        passive_payload = b""
    if gates or passives:
        generated_cdb = ic.build_cdb(topology, package_rows, passive_specs)
        generated_parsed = split_cdb_generic(generated_cdb)
    else:
        generated_parsed = None
    return b"".join(records) + passive_payload, generated_parsed, {
        "gates": [gate.__dict__ for gate in gates],
        "gate_topology": topology,
        "package_rows": package_rows,
        "passives": [passive.__dict__ for passive in passives],
        "passive_topology": passive_topology,
        "passive_replacements": passive_replacements,
        "passive_issues": passive_issues,
        "passive_translation": passive_translation,
        "gate_positions": [
            {
                "package_ref": row["package_ref"],
                "package_number": row["package_number"],
                "x": _logic_package_position(int(row["package_number"]))[0],
                "y": _logic_package_position(int(row["package_number"]))[1],
            }
            for row in package_rows
        ],
    }


def _device_sections_for_composed(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    seen: set[str] = set()
    for part in parts:
        section = device_section(part["donor_dsn"])
        digest = _sha256_bytes(section)
        if digest in seen:
            continue
        seen.add(digest)
        donor = part["donor"]
        sections.append(
            {
                "donor_key": str(part["component"]["part"]),
                "donor": str(donor.relative_to(repository_root()) if donor.is_relative_to(repository_root()) else donor),
                "section": bytearray(section),
                "old_tail_pointer": int.from_bytes(section[-4:], "little") if len(section) >= 4 else None,
                "size": len(section),
            }
        )
    return sections


def _compose_static_validation_issues(
    output: Path,
    object_chunk: bytes,
    cdb: bytes,
    cdb_plan: dict[str, Any],
    build_issues: list[str],
) -> list[str]:
    issues = list(build_issues)
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    if not object_chunk or object_chunk[0] != 0 or object_chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    try:
        parsed = split_cdb_generic(cdb)
        if parsed.count != int(cdb_plan["count"]):
            issues.append(f"CDB parsed count {parsed.count} differs from build plan {cdb_plan['count']}")
        pin_refs = [ref for ref, _row in parsed.pin_rows]
        if len(pin_refs) != len(set(pin_refs)):
            issues.append(f"duplicate CDB pin refs: {sorted({ref for ref in pin_refs if pin_refs.count(ref) > 1})}")
        package_props = parsed.property_package_refs()
        if len(package_props) != len(set(package_props)):
            issues.append(f"duplicate CDB property refs: {sorted({ref for ref in package_props if package_props.count(ref) > 1})}")
        pin_ids = [int.from_bytes(row[:4], "little") for _ref, row in parsed.pin_rows]
        if len(pin_ids) != len(set(pin_ids)):
            issues.append(f"duplicate CDB pin IDs: {_duplicates(pin_ids)}")
        prop_ids = [int.from_bytes(row[:4], "little") for _ref, row, _last in parsed.property_rows]
        if len(prop_ids) != len(set(prop_ids)):
            issues.append(f"duplicate CDB property IDs: {_duplicates(prop_ids)}")
    except Exception as exc:
        issues.append(f"CDB parse failed: {exc}")
    return issues


def _max_cdb_object_id(parsed: GenericCdb) -> int:
    values: list[int] = []
    for _ref, row in parsed.pin_rows:
        value = _u32_at(row, 0)
        if value is not None:
            values.append(value)
    for _ref, row, _last in parsed.property_rows:
        value = _u32_at(row, 0)
        if value is not None:
            values.append(value)
    return max(values, default=0)


def _next_generated_package_number(parsed: GenericCdb) -> int:
    numbers: list[int] = []
    for ref in parsed.pin_package_refs():
        if ref.startswith("U") and ref[1:].isdigit():
            numbers.append(int(ref[1:]))
    return max(numbers, default=0) + 1


def generate_ic_native_direct_donor_plus_generated_project_from_payload(
    payload: dict[str, Any],
    outdir: str | Path,
    *,
    registry: NativeRegistry,
    components: list[dict[str, Any]],
    connection_map: dict[str, dict[str, str]],
    direct_donor: tuple[Path, str, list[str]],
    layout_strategy: str | None = None,
) -> NativeGenerationResult:
    donor, method, donor_parts = direct_donor
    case_id = _safe_case_id(str(payload.get("case_id") or payload.get("title") or donor.stem))
    case_dir = Path(outdir)
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)
    donor_parsed = split_cdb_generic(donor_cdb)
    donor_bidir_events = bidir_events(donor_chunk)
    component_single_counts = _single_terminal_counts(registry, donor_parts)
    replacements, terminal_plan = _labels_for_events(
        donor_chunk=donor_chunk,
        components=components,
        component_single_counts=component_single_counts,
        connection_map=connection_map,
    )
    native_chunk, mutations = patch_bidir_labels(donor_chunk, replacements)

    first_object_id = _max_cdb_object_id(donor_parsed) + 1
    first_package_number = _next_generated_package_number(donor_parsed)
    generated_payload, generated_cdb, generated_plan = _generated_logic_and_passive_records(
        payload,
        first_object_id,
        first_package_number=first_package_number,
    )
    cdb_parts = [donor_parsed]
    if generated_cdb is not None:
        cdb_parts.append(generated_cdb)
        cdb, cdb_plan = build_cdb_from_generic_parts(cdb_parts)
    else:
        cdb = donor_cdb
        cdb_plan = {
            "count": donor_parsed.count,
            "pin_refs": [ref for ref, _row in donor_parsed.pin_rows],
            "property_refs": [ref for ref, _row, _last in donor_parsed.property_rows],
            "cdb_id_plan": {
                "mode": "preserved_complete_native_donor_cdb",
                "duplicates_before": {},
                "duplicates_after": {},
                "before": {},
                "after": {},
                "row_plan": [],
            },
        }
    object_chunk = b"\x00" + native_chunk[1:-1] + generated_payload + b"\xff"

    sections = [
        {
            "donor_key": method,
            "donor": str(donor.relative_to(repository_root()) if donor.is_relative_to(repository_root()) else donor),
            "section": bytearray(device_section(donor_dsn)),
            "old_tail_pointer": int.from_bytes(device_section(donor_dsn)[-4:], "little") if len(device_section(donor_dsn)) >= 4 else None,
            "size": len(device_section(donor_dsn)),
        }
    ]
    if generated_payload:
        from . import ic_combinational as ic

        combo_section = ic._combined_device_section()
        sections.append(
            {
                "donor_key": "accepted_combinational_and_passive",
                "donor": str(ic.COMBINED_DEVICE_DONOR.relative_to(repository_root())),
                "section": bytearray(combo_section),
                "old_tail_pointer": int.from_bytes(combo_section[-4:], "little") if len(combo_section) >= 4 else None,
                "size": len(combo_section),
            }
        )

    fixture = FixtureRegistry.load().get("e001_empty")
    base_dsn = read_internal_file(fixture.path, "ROOT.DSN")
    dsn, pointers = build_dsn_with_device_sections(base_dsn, donor_dsn, object_chunk, sections)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    write_project_from_parts(
        fixture.path,
        output,
        {
            "PROJECT.XML": patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    object_chunk = _extract_object_chunk(dsn)
    marker_list = [registry.components[str(component["part"])].marker for component in components]
    manifest = {
        "schema": SCHEMA_VERSION,
        "case_id": case_id,
        "title": payload.get("title", case_id),
        "generator": "proteusgen.ic_native",
        "method": "native_complete_same_family_donor_plus_optional_locked_logic_and_rcl",
        "selection_method": method,
        "status": "temporary_pending_user_proteus_testing",
        "layout_strategy": layout_strategy or payload.get("layout", {}).get("strategy", "beautify"),
        "donor": str(donor.relative_to(repository_root()) if donor.is_relative_to(repository_root()) else donor),
        "components": [
            {
                "ref": component["ref"],
                "part": component["part"],
                "marker": registry.components[str(component["part"])].marker,
            }
            for component in components
        ],
        "terminal_policy": "native pins use donor-native $TERBIDIR; generated combinational gates keep directional IC terminals; generated RCL uses bidirectional endpoints",
        "terminal_plan": terminal_plan,
        "mutations": mutations,
        "generated_plan": generated_plan,
        "cdb_plan": cdb_plan,
        "first_generated_object_id": first_object_id,
        "first_generated_package_number": first_package_number,
        "section_pointers": pointers,
        "device_sections": [{key: value for key, value in section.items() if key != "section"} for section in sections],
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": marker_counts(object_chunk, marker_list),
        "cdb_marker_counts": marker_counts(cdb, marker_list),
        "object_chunk_size": len(object_chunk),
        "device_section_size": len(device_section(dsn)),
        "static_validation_issues": _compose_static_validation_issues(
            output,
            object_chunk,
            cdb,
            cdb_plan,
            generated_plan["passive_issues"],
        ),
        "output_hashes": {
            "project": _sha256_file(output),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(object_chunk),
        },
    }

    dsn_path = case_dir / "ROOT.DSN.bin"
    cdb_path = case_dir / "ROOT.CDB.bin"
    chunk_path = case_dir / "object_chunk.bin"
    manifest_path = case_dir / "manifest.json"
    terminal_plan_path = case_dir / "terminal_plan.json"
    input_path = case_dir / "circuit_input.json"
    dsn_path.write_bytes(dsn)
    cdb_path.write_bytes(cdb)
    chunk_path.write_bytes(object_chunk)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    terminal_plan_path.write_text(json.dumps(terminal_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    input_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return NativeGenerationResult(
        output_path=output,
        cdb_path=cdb_path,
        dsn_path=dsn_path,
        chunk_path=chunk_path,
        terminal_plan_path=terminal_plan_path,
        manifest_path=manifest_path,
        circuit_input_path=input_path,
        manifest=manifest,
    )


def generate_ic_native_composed_project_from_payload(
    payload: dict[str, Any],
    outdir: str | Path,
    *,
    registry: NativeRegistry,
    components: list[dict[str, Any]],
    connection_map: dict[str, dict[str, str]],
    layout_strategy: str | None = None,
) -> NativeGenerationResult:
    reserve_u_refs = bool(payload.get("logic_gates") or payload.get("gates"))
    internal_refs = _clone_internal_refs(components, reserve_u_refs=reserve_u_refs)
    case_id = _safe_case_id(str(payload.get("case_id") or payload.get("title") or "ic_native_composed"))
    case_dir = Path(outdir)
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    native_payloads: list[bytes] = []
    cdb_parts: list[GenericCdb] = []
    donor_parts: list[dict[str, Any]] = []
    terminal_plan: list[dict[str, Any]] = []
    mutation_plan: list[dict[str, Any]] = []
    suffix_plan: list[dict[str, Any]] = []
    translation_plan: list[dict[str, Any]] = []
    build_issues: list[str] = []

    for index, component in enumerate(components):
        donor = _single_donor_for_component(payload, registry, component)
        donor_dsn = read_internal_file(donor, "ROOT.DSN")
        donor_cdb = read_internal_file(donor, "ROOT.CDB")
        donor_chunk = _extract_object_chunk(donor_dsn)
        old_refs = _refs_in_bytes(donor_chunk) or _refs_in_bytes(donor_cdb)
        old_pkgs: list[str] = []
        for ref in old_refs:
            pkg = package_ref(ref)
            if pkg not in old_pkgs:
                old_pkgs.append(pkg)
        if len(old_pkgs) > 1:
            raise IcNativeGenerationBlocked(
                NativeValidationReport((f"Composed native cloning expects a single package donor for {component['part']}, found {old_pkgs}.",))
            )
        if not old_pkgs:
            old_pkgs = ["U1"]
        internal_ref = internal_refs[str(component["ref"])]
        if len(internal_ref) != len(old_pkgs[0]):
            raise IcNativeGenerationBlocked(
                NativeValidationReport((f"Internal ref {internal_ref} is not same length as donor ref {old_pkgs[0]}.",))
            )
        clone = patch_refs(donor_chunk, {old_pkgs[0]: internal_ref})
        replacements: dict[int, str] = {}
        per_component_plan: list[dict[str, Any]] = []
        for event in bidir_events(clone):
            label, signal, pin, source = _component_connection_label(event=event, component=component, connection_map=connection_map)
            replacements[event.index] = label
            per_component_plan.append(
                {
                    "terminal_index": event.index,
                    "component_ref": component["ref"],
                    "internal_ref": internal_ref,
                    "component_part": component["part"],
                    "old_label": event.label,
                    "new_label": label,
                    "signal": signal,
                    "pin": pin,
                    "source": source,
                }
            )
        clone, mutations = patch_bidir_labels(clone, replacements)
        clone, suffix_mutations = patch_bidir_suffixes(clone, 0x3000 + index * 0x0100)
        dx, dy = _component_grid_offset(index, payload, str(component["ref"]))
        clone, translation = translate_chunk(clone, dx, dy)
        native_payloads.append(clone[1:-1])
        terminal_plan.extend(per_component_plan)
        mutation_plan.append({"component_ref": component["ref"], "internal_ref": internal_ref, "mutations": mutations})
        suffix_plan.append({"component_ref": component["ref"], "internal_ref": internal_ref, "mutations": suffix_mutations})
        translation_plan.append({"component_ref": component["ref"], "internal_ref": internal_ref, **translation})
        donor_parts.append({"component": component, "donor": donor, "donor_dsn": donor_dsn})
        try:
            cdb_parts.append(split_cdb_generic(patch_refs(donor_cdb, {old_pkgs[0]: internal_ref})))
        except ValueError as exc:
            native = registry.components[str(component["part"])]
            if native.cdb_rows != "none_observed":
                raise
            build_issues.append(f"{component['part']} contributed no parsed CDB rows: {exc}")

    generated_payload, generated_cdb, generated_plan = _generated_logic_and_passive_records(payload, len(cdb_parts) + 1)
    if generated_cdb is not None:
        cdb_parts.append(generated_cdb)
    cdb, cdb_plan = build_cdb_from_generic_parts(cdb_parts)
    object_chunk = b"\x00" + b"".join(native_payloads) + generated_payload + b"\xff"
    global_suffix_plan: list[dict[str, Any]] = []

    sections = _device_sections_for_composed(donor_parts)
    if generated_payload:
        from . import ic_combinational as ic

        combo_section = ic._combined_device_section()
        sections.append(
            {
                "donor_key": "accepted_combinational_and_passive",
                "donor": str(ic.COMBINED_DEVICE_DONOR.relative_to(repository_root())),
                "section": bytearray(combo_section),
                "old_tail_pointer": int.from_bytes(combo_section[-4:], "little") if len(combo_section) >= 4 else None,
                "size": len(combo_section),
            }
        )
    fixture = FixtureRegistry.load().get("e001_empty")
    base_dsn = read_internal_file(fixture.path, "ROOT.DSN")
    first_donor_dsn = donor_parts[0]["donor_dsn"] if donor_parts else base_dsn
    dsn, pointers = build_dsn_with_device_sections(base_dsn, first_donor_dsn, object_chunk, sections)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    write_project_from_parts(
        fixture.path,
        output,
        {
            "PROJECT.XML": patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    object_chunk = _extract_object_chunk(dsn)
    marker_list = [registry.components[str(component["part"])].marker for component in components]
    manifest = {
        "schema": SCHEMA_VERSION,
        "case_id": case_id,
        "title": payload.get("title", case_id),
        "generator": "proteusgen.ic_native",
        "method": "native_single_packet_clone_composition_with_optional_locked_logic_and_rcl",
        "selection_method": "composed_native_clone",
        "status": "temporary_pending_user_proteus_testing",
        "layout_strategy": layout_strategy or payload.get("layout", {}).get("strategy", "beautify"),
        "components": [
            {
                "ref": component["ref"],
                "internal_ref": internal_refs[str(component["ref"])],
                "part": component["part"],
                "marker": registry.components[str(component["part"])].marker,
            }
            for component in components
        ],
        "terminal_policy": "native pins use $TERBIDIR; generated combinational gates keep directional IC terminals; generated RCL uses bidirectional endpoints",
        "terminal_plan": terminal_plan,
        "mutations": mutation_plan,
        "suffix_plan": suffix_plan,
        "global_suffix_plan": global_suffix_plan,
        "translation_plan": translation_plan,
        "generated_plan": generated_plan,
        "cdb_plan": cdb_plan,
        "section_pointers": pointers,
        "device_sections": [{key: value for key, value in section.items() if key != "section"} for section in sections],
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": marker_counts(object_chunk, marker_list),
        "cdb_marker_counts": marker_counts(cdb, marker_list),
        "object_chunk_size": len(object_chunk),
        "device_section_size": len(device_section(dsn)),
        "static_validation_issues": _compose_static_validation_issues(output, object_chunk, cdb, cdb_plan, build_issues + generated_plan["passive_issues"]),
        "output_hashes": {
            "project": _sha256_file(output),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(object_chunk),
        },
    }

    dsn_path = case_dir / "ROOT.DSN.bin"
    cdb_path = case_dir / "ROOT.CDB.bin"
    chunk_path = case_dir / "object_chunk.bin"
    manifest_path = case_dir / "manifest.json"
    terminal_plan_path = case_dir / "terminal_plan.json"
    input_path = case_dir / "circuit_input.json"
    dsn_path.write_bytes(dsn)
    cdb_path.write_bytes(cdb)
    chunk_path.write_bytes(object_chunk)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    terminal_plan_path.write_text(json.dumps(terminal_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    input_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return NativeGenerationResult(
        output_path=output,
        cdb_path=cdb_path,
        dsn_path=dsn_path,
        chunk_path=chunk_path,
        terminal_plan_path=terminal_plan_path,
        manifest_path=manifest_path,
        circuit_input_path=input_path,
        manifest=manifest,
    )


def static_validation_issues(
    output: Path,
    *,
    expected_markers: Iterable[str],
    require_bidir: bool,
    mutations: list[dict[str, Any]],
) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
        return issues
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    for marker in expected_markers:
        raw = marker.encode("ascii")
        if raw not in chunk and raw not in cdb:
            issues.append(f"expected native marker {marker} missing from output")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("native route should not emit ordinary input/output terminal records")
    if require_bidir and not chunk.count(BIDIR_MARKER):
        issues.append("native output has no bidirectional terminals")
    labels = [str(mutation["new"]).encode("ascii") for mutation in mutations]
    for raw in labels:
        if raw not in chunk:
            issues.append(f"mutated label {raw.decode('ascii', errors='replace')} not present")
    return issues


def generate_ic_native_project_from_payload(
    payload: dict[str, Any],
    outdir: str | Path,
    *,
    layout_strategy: str | None = None,
) -> NativeGenerationResult:
    if not isinstance(payload, dict):
        raise IcNativeGenerationBlocked(NativeValidationReport(("Native CircuitIR payload must be an object.",)))
    schema = payload.get("schema") or payload.get("schema_version")
    if schema not in (None, SCHEMA_VERSION):
        raise IcNativeGenerationBlocked(NativeValidationReport((f"Unsupported native schema `{schema}`.",)))
    try:
        registry = NativeRegistry.load()
        components = _components_from_payload(payload, registry)
        connection_map = _connection_map(payload, components)
    except (FileNotFoundError, ValueError) as exc:
        raise IcNativeGenerationBlocked(NativeValidationReport((str(exc),))) from exc
    try:
        direct_same_family = _direct_same_family_donor(payload, registry, components)
    except ValueError as exc:
        raise IcNativeGenerationBlocked(NativeValidationReport((str(exc),))) from exc
    if direct_same_family is not None and (
        payload.get("compose") or payload.get("clone_from_donor") or payload.get("logic_gates") or payload.get("passives")
    ) and not payload.get("force_clone"):
        if (payload.get("logic_gates") or payload.get("passives")) and not payload.get("allow_generated_append"):
            raise IcNativeGenerationBlocked(
                NativeValidationReport(
                    (
                        "Generated AND/RCL append into native same-family donors is rejected by Proteus testing. "
                        "Use a single donor-host file that already contains the requested native+gate/RCL metadata, "
                        "or set allow_generated_append only for controlled experiments.",
                    )
                )
            )
        try:
            return generate_ic_native_direct_donor_plus_generated_project_from_payload(
                payload,
                outdir,
                registry=registry,
                components=components,
                connection_map=connection_map,
                direct_donor=direct_same_family,
                layout_strategy=layout_strategy,
            )
        except IcNativeGenerationBlocked:
            raise
        except (FileNotFoundError, ValueError) as exc:
            raise IcNativeGenerationBlocked(NativeValidationReport((str(exc),))) from exc
    if _requires_composed_generation(payload, registry, components):
        try:
            return generate_ic_native_composed_project_from_payload(
                payload,
                outdir,
                registry=registry,
                components=components,
                connection_map=connection_map,
                layout_strategy=layout_strategy,
            )
        except IcNativeGenerationBlocked:
            raise
        except (FileNotFoundError, ValueError) as exc:
            raise IcNativeGenerationBlocked(NativeValidationReport((str(exc),))) from exc
    try:
        donor, method, donor_parts = _donor_for_components(payload, registry, components)
    except (FileNotFoundError, ValueError) as exc:
        raise IcNativeGenerationBlocked(NativeValidationReport((str(exc),))) from exc

    case_id = _safe_case_id(str(payload.get("case_id") or payload.get("title") or donor.stem))
    case_dir = Path(outdir)
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)
    donor_bidir_events = bidir_events(donor_chunk)
    if any(connection_map.values()) and not donor_bidir_events:
        raise IcNativeGenerationBlocked(
            NativeValidationReport(
                (
                    "Selected native donor has no bidirectional terminal anchors, "
                    "so explicit pin/net connections cannot be applied safely.",
                )
            )
        )
    component_markers = [registry.components[part].marker for part in donor_parts if part in registry.components]
    donor_record_markers = _markers_in_donor_records(registry, donor_chunk, donor_cdb)
    if component_markers:
        expected_markers = [
            marker for marker in component_markers if marker.encode("ascii") in donor_chunk or marker.encode("ascii") in donor_cdb
        ]
    else:
        expected_markers = donor_record_markers
    marker_expectation_warnings = [
        f"Registry marker {marker} was requested but is absent from the selected donor object/CDB records."
        for marker in component_markers
        if marker not in expected_markers
    ]
    component_single_counts = _single_terminal_counts(registry, donor_parts)
    replacements, terminal_plan = _labels_for_events(
        donor_chunk=donor_chunk,
        components=components,
        component_single_counts=component_single_counts,
        connection_map=connection_map,
    )

    exact_rezip = bool(payload.get("exact_rezip"))
    mutations: list[dict[str, Any]] = []
    pointers: dict[str, Any] = {}
    if exact_rezip:
        dsn = patch_root_dsn_version(donor_dsn, PROTEUS_813)
        write_project_from_parts(
            donor,
            output,
            {
                "PROJECT.XML": patch_project_xml_version(read_internal_file(donor, "PROJECT.XML"), PROTEUS_813),
                "ROOT.DSN": dsn,
                "ROOT.CDB": donor_cdb,
            },
        )
        object_chunk = _extract_object_chunk(dsn)
        emit_method = "deterministic_exact_native_donor_rezip"
    else:
        object_chunk, mutations = patch_bidir_labels(donor_chunk, replacements)
        fixture = FixtureRegistry.load().get("e001_empty")
        base_dsn = read_internal_file(fixture.path, "ROOT.DSN")
        dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, object_chunk, device_section(donor_dsn))
        dsn = patch_root_dsn_version(dsn, PROTEUS_813)
        write_project_from_parts(
            fixture.path,
            output,
            {
                "PROJECT.XML": patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813),
                "ROOT.DSN": dsn,
                "ROOT.CDB": donor_cdb,
            },
        )
        emit_method = "native_complete_donor_packet_inserted_into_e001"

    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    object_chunk = _extract_object_chunk(dsn)
    require_bidir = bool(donor_bidir_events) and any(
        registry.components[part].terminal_policy == "bidir" for part in donor_parts if part in registry.components
    )
    manifest = {
        "schema": SCHEMA_VERSION,
        "case_id": case_id,
        "title": payload.get("title", case_id),
        "generator": "proteusgen.ic_native",
        "method": emit_method,
        "selection_method": method,
        "status": "temporary_pending_user_proteus_testing",
        "layout_strategy": layout_strategy or payload.get("layout", {}).get("strategy", "beautify"),
        "donor": str(donor.relative_to(repository_root()) if donor.is_relative_to(repository_root()) else donor),
        "components": [
            {
                "ref": component["ref"],
                "part": component["part"],
                "marker": registry.components[str(component["part"])].marker,
                "notes": registry.components[str(component["part"])].notes,
            }
            for component in components
        ],
        "terminal_policy": "native/sequential visible pins use donor-native $TERBIDIR records",
        "pin_policy": {
            "sequential_native": "physical pins are real signals; pin 14/pin 7 are not hidden by this route",
            "combinational": "not handled here; use generate-ic-combinational",
        },
        "section_pointers": pointers,
        "component_single_terminal_counts": component_single_counts,
        "terminal_plan": terminal_plan,
        "mutations": mutations,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": marker_counts(object_chunk, component_markers),
        "cdb_marker_counts": marker_counts(cdb, component_markers),
        "marker_expectation_warnings": marker_expectation_warnings,
        "object_chunk_size": len(object_chunk),
        "device_section_size": len(device_section(dsn)),
        "static_validation_issues": static_validation_issues(
            output,
            expected_markers=expected_markers,
            require_bidir=require_bidir,
            mutations=mutations,
        ),
        "output_hashes": {
            "project": _sha256_file(output),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(object_chunk),
        },
    }

    dsn_path = case_dir / "ROOT.DSN.bin"
    cdb_path = case_dir / "ROOT.CDB.bin"
    chunk_path = case_dir / "object_chunk.bin"
    manifest_path = case_dir / "manifest.json"
    terminal_plan_path = case_dir / "terminal_plan.json"
    input_path = case_dir / "circuit_input.json"
    dsn_path.write_bytes(dsn)
    cdb_path.write_bytes(cdb)
    chunk_path.write_bytes(object_chunk)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    terminal_plan_path.write_text(
        json.dumps([event.as_dict() | parse_pin_label(event.label) for event in bidir_events(object_chunk)], indent=2)
        + "\n",
        encoding="utf-8",
    )
    input_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return NativeGenerationResult(
        output_path=output,
        cdb_path=cdb_path,
        dsn_path=dsn_path,
        chunk_path=chunk_path,
        terminal_plan_path=terminal_plan_path,
        manifest_path=manifest_path,
        circuit_input_path=input_path,
        manifest=manifest,
    )


def _markers_in_donor_records(registry: NativeRegistry, donor_chunk: bytes, donor_cdb: bytes) -> list[str]:
    markers: list[str] = []
    for component in registry.components.values():
        raw = component.marker.encode("ascii")
        if raw in donor_chunk or raw in donor_cdb:
            markers.append(component.marker)
    return sorted(set(markers))


def _safe_case_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()).strip("._")
    return safe[:96] or "ic_native_case"
