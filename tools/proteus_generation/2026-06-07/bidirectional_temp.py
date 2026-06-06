"""Experimental donor-derived bidirectional terminal conversion helpers."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file

BIDIR_MARKER = b"$TERBIDIR"
INPUT_MARKER = b"$TERINPUT"
OUTPUT_MARKER = b"$TEROUTPUT"
INPUT_SIZE = 103
OUTPUT_SIZE = 104
TERMINAL_LABEL_X_OFFSET = 381000


@dataclass(frozen=True)
class BidirTemplates:
    zero: bytes
    one_eighty: bytes


@dataclass(frozen=True)
class TerminalReplacement:
    kind: str
    label: str
    angle_tenths: int
    suffix: int
    old_start: int
    old_size: int
    new_size: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "angle_tenths": self.angle_tenths,
            "suffix": f"{self.suffix:04x}",
            "old_start": self.old_start,
            "old_size": self.old_size,
            "new_size": self.new_size,
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_bidir_records(chunk: bytes) -> list[bytes]:
    records: list[bytes] = []
    position = 0
    while True:
        marker = chunk.find(BIDIR_MARKER, position)
        if marker < 0:
            return records
        start = marker - 14
        if start < 0 or chunk[start] != 0x10:
            raise ValueError(f"Invalid bidirectional terminal start at marker {marker}.")
        label_length = chunk[start + 30]
        size = 101 + label_length
        records.append(chunk[start : start + size])
        position = marker + 1


def load_templates(zero_project: Path, one_eighty_project: Path) -> BidirTemplates:
    zero_records = extract_bidir_records(rv9._extract_object_chunk(read_internal_file(zero_project, "ROOT.DSN")))
    one_eighty_records = extract_bidir_records(
        rv9._extract_object_chunk(read_internal_file(one_eighty_project, "ROOT.DSN"))
    )
    if len(zero_records) != 1 or len(one_eighty_records) != 1:
        raise ValueError("Empty bidirectional donors must contain exactly one terminal record.")
    if struct.unpack("<I", zero_records[0][9:13])[0] != 0:
        raise ValueError("Zero-degree bidirectional donor has the wrong angle.")
    if struct.unpack("<I", one_eighty_records[0][9:13])[0] != 1800:
        raise ValueError("180-degree bidirectional donor has the wrong angle.")
    return BidirTemplates(zero=zero_records[0], one_eighty=one_eighty_records[0])


def build_bidir_record(
    templates: BidirTemplates,
    *,
    label: str,
    symbol_x: int,
    symbol_y: int,
    angle_tenths: int,
    suffix: int,
    active_link: bool,
) -> bytes:
    raw_label = label.encode("ascii")
    if not raw_label or len(raw_label) > 255:
        raise ValueError("Bidirectional terminal labels must be 1..255 ASCII bytes.")
    if angle_tenths == 0:
        template = templates.zero
        label_x = symbol_x + TERMINAL_LABEL_X_OFFSET
    elif angle_tenths == 1800:
        template = templates.one_eighty
        label_x = symbol_x - TERMINAL_LABEL_X_OFFSET
    else:
        raise ValueError(f"Unsupported bidirectional terminal angle {angle_tenths}.")

    old_length = template[30]
    record = bytearray(
        template[:30]
        + bytes([len(raw_label)])
        + raw_label
        + template[31 + old_length :]
    )
    record[1:5] = struct.pack("<i", symbol_x)
    record[5:9] = struct.pack("<i", symbol_y)
    label_offset = 31 + len(raw_label)
    record[label_offset : label_offset + 4] = struct.pack("<i", label_x)
    record[label_offset + 4 : label_offset + 8] = struct.pack("<i", symbol_y)
    record[-4:-2] = struct.pack("<H", suffix & 0xFFFF)
    record[-2:] = bytes([1 if active_link else 0, 0])
    return bytes(record)


def rebuild_existing_bidir_records(chunk: bytes, templates: BidirTemplates) -> bytes:
    rebuilt = bytearray(chunk)
    records = extract_bidir_records(chunk)
    starts: list[int] = []
    position = 0
    for record in records:
        marker = chunk.find(BIDIR_MARKER, position)
        start = marker - 14
        starts.append(start)
        position = start + len(record)

    for start, record in reversed(list(zip(starts, records, strict=True))):
        label_length = record[30]
        label = record[31 : 31 + label_length].decode("ascii")
        symbol_x, symbol_y = struct.unpack("<ii", record[1:9])
        angle_tenths = struct.unpack("<I", record[9:13])[0]
        suffix = struct.unpack("<H", record[-4:-2])[0]
        replacement = build_bidir_record(
            templates,
            label=label,
            symbol_x=symbol_x,
            symbol_y=symbol_y,
            angle_tenths=angle_tenths,
            suffix=suffix,
            active_link=record[-2] == 1,
        )
        rebuilt[start : start + len(record)] = replacement
    return bytes(rebuilt)


def _ordinary_terminal_events(chunk: bytes) -> list[tuple[int, str, int]]:
    events: list[tuple[int, str, int]] = []
    for marker, kind, size in (
        (INPUT_MARKER, "input", INPUT_SIZE),
        (OUTPUT_MARKER, "output", OUTPUT_SIZE),
    ):
        position = 0
        while True:
            marker_position = chunk.find(marker, position)
            if marker_position < 0:
                break
            start = marker_position - 14
            if start < 0 or chunk[start] != 0x10:
                raise ValueError(f"Invalid {kind} terminal start at marker {marker_position}.")
            events.append((start, kind, size))
            position = marker_position + 1
    return sorted(events)


def replace_ordinary_terminals(
    chunk: bytes,
    templates: BidirTemplates,
) -> tuple[bytes, list[TerminalReplacement]]:
    events = _ordinary_terminal_events(chunk)
    converted = bytearray(chunk)
    metadata: list[TerminalReplacement] = []
    for start, kind, size in reversed(events):
        record = chunk[start : start + size]
        length_offset = 30 if kind == "input" else 31
        label_length = record[length_offset]
        label_start = length_offset + 1
        label = record[label_start : label_start + label_length].decode("ascii")
        symbol_x, symbol_y = struct.unpack("<ii", record[1:9])
        angle_tenths = struct.unpack("<I", record[9:13])[0]
        suffix = struct.unpack("<H", record[-4:-2])[0]
        replacement = build_bidir_record(
            templates,
            label=label,
            symbol_x=symbol_x,
            symbol_y=symbol_y,
            angle_tenths=angle_tenths,
            suffix=suffix,
            active_link=record[-2] == 1,
        )
        converted[start : start + size] = replacement
        metadata.append(
            TerminalReplacement(
                kind=kind,
                label=label,
                angle_tenths=angle_tenths,
                suffix=suffix,
                old_start=start,
                old_size=size,
                new_size=len(replacement),
            )
        )
    converted[-1] = 0xFF
    return bytes(converted), sorted(metadata, key=lambda item: item.old_start)


def validate_conversion(
    original: bytes,
    converted: bytes,
    replacements: list[TerminalReplacement],
) -> list[str]:
    issues: list[str] = []
    expected = original.count(INPUT_MARKER) + original.count(OUTPUT_MARKER)
    if len(replacements) != expected:
        issues.append(f"replacement count {len(replacements)} != {expected}")
    if converted.count(INPUT_MARKER) or converted.count(OUTPUT_MARKER):
        issues.append("ordinary input/output terminal markers remain")
    if converted.count(BIDIR_MARKER) != expected:
        issues.append(f"$TERBIDIR count {converted.count(BIDIR_MARKER)} != {expected}")
    for marker in (b"$TERPOWER", b"$TERGROUND", b"WIRE", b"COMPONENT ID"):
        if converted.count(marker) != original.count(marker):
            issues.append(f"{marker.decode('ascii')} count changed")
    for marker in (b"RESISTOR", b"CAPACITOR", b"REALIND", b"VSOURCE", b"CSOURCE", b"VSINE"):
        if converted.count(marker) != original.count(marker):
            issues.append(f"{marker.decode('ascii')} count changed")
    if not converted or converted[0] != 0 or converted[-1] != 0xFF:
        issues.append("converted object chunk boundary is invalid")
    for item in replacements:
        suffix_bytes = struct.pack("<H", item.suffix)
        if item.suffix and converted.count(suffix_bytes) != original.count(suffix_bytes):
            issues.append(f"suffix {item.suffix:04x} occurrence count changed")
    return issues
