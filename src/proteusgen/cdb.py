from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


COUNT_OFFSET = 92
PIN_ROW_HEADER_SIZE = 16
PIN_ROW_FOOTER_SIZE = 12
PROPERTY_ROW_HEADER_SIZE = 20


@dataclass(frozen=True)
class CdbPinRow:
    ref: str
    data: bytes


@dataclass(frozen=True)
class CdbPropertyRow:
    ref: str
    data: bytes


@dataclass(frozen=True)
class CdbFile:
    prefix: bytes
    count: int
    pin_rows: tuple[CdbPinRow, ...]
    between_sections: bytes
    property_rows: tuple[CdbPropertyRow, ...]
    suffix: bytes

    def pin_by_ref(self) -> dict[str, CdbPinRow]:
        return {row.ref: row for row in self.pin_rows}

    def property_by_ref(self) -> dict[str, CdbPropertyRow]:
        return {row.ref: row for row in self.property_rows}


def _read_u32(data: bytes, offset: int) -> int:
    if offset + 4 > len(data):
        raise ValueError("Unexpected end of CDB while reading u32.")
    return int.from_bytes(data[offset : offset + 4], "little", signed=False)


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


def package_ref(ref: str) -> str:
    return ref.split(":", 1)[0]


def _parse_property_rows(
    data: bytes,
    start: int,
    expected_refs: tuple[str, ...],
) -> tuple[list[CdbPropertyRow], int] | None:
    rows: list[CdbPropertyRow] = []
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
            # Proteus property lengths include the first dword of the next row.
            # Keep that dword only in the next row to preserve the byte stream.
            row_end = computed_end - 4
            if row_end <= row_start:
                return None
            pos = row_end

        rows.append(CdbPropertyRow(ref=ref, data=data[row_start:row_end]))
    return rows, pos


def parse_cdb(data: bytes) -> CdbFile:
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

    expected_refs = tuple(package_ref(row.ref) for row in pin_rows)
    first_property_start = None
    property_rows: list[CdbPropertyRow] | None = None
    property_end = None
    for candidate in range(pos, len(data)):
        parsed = _parse_property_rows(data, candidate, expected_refs)
        if parsed is None:
            continue
        rows, end = parsed
        first_property_start = candidate
        property_rows = rows
        property_end = end
        break
    if first_property_start is None:
        raise ValueError("Could not locate first CDB property row.")

    between_sections = data[pos:first_property_start]

    return CdbFile(
        prefix=data[:COUNT_OFFSET],
        count=count,
        pin_rows=tuple(pin_rows),
        between_sections=between_sections,
        property_rows=tuple(property_rows or []),
        suffix=data[property_end or len(data) :],
    )


def patch_row_ref(row: bytes, old_ref: str, new_ref: str, *, header_size: int) -> bytes:
    old = old_ref.encode("ascii")
    new = new_ref.encode("ascii")
    if len(old) != len(new):
        raise ValueError("CDB row ref patching currently requires same-length references.")
    pos = header_size
    if row[pos] != len(old) or row[pos + 1 : pos + 1 + len(old)] != old:
        raise ValueError(f"CDB row does not start with expected reference {old_ref!r}.")
    out = bytearray(row)
    out[pos + 1 : pos + 1 + len(old)] = new
    return bytes(out)


def build_cdb_from_rows(template: CdbFile, refs: Iterable[tuple[str, CdbPinRow, CdbPropertyRow]]) -> bytes:
    rows = list(refs)
    prefix = bytearray(template.prefix)
    prefix.extend(len(rows).to_bytes(4, "little"))
    return (
        bytes(prefix)
        + b"".join(pin_row.data for _ref, pin_row, _property_row in rows)
        + template.between_sections
        + b"".join(property_row.data for _ref, _pin_row, property_row in rows)
        + template.suffix
    )
