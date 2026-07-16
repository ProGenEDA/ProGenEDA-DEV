"""Packet-safe component coordinate helpers.

This module owns experimental binary coordinate movement for complete
donor-derived component packets. The default is intentionally no mutation:
Proteus coordinate bytes are fragile, and packet movement must be enabled only
inside focused tests until user acceptance.
"""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .ic_native import bidir_events

HIDDEN_COORD_DX = 350_000
HIDDEN_COORD_DY = 350_000
HIDDEN_ABSOLUTE_X = 350_000
HIDDEN_ABSOLUTE_Y = 350_000
HIDDEN_PACKET_START = -1_000_000_000
DEFAULT_HIDDEN_COORDINATE_MODE = "none"
D20_SMALL_COORD_DX = 350_000
D20_SMALL_COORD_DY = 350_000

VISIBLE_LAYOUT_ORIGIN_X = -6_350_000
VISIBLE_LAYOUT_ORIGIN_Y = -5_080_000
VISIBLE_LAYOUT_SLOT_X = 3_810_000
VISIBLE_LAYOUT_SLOT_Y = 2_540_000
VISIBLE_LAYOUT_COLUMNS = 10
VISIBLE_LAYOUT_MARGIN_X = 3_810_000
VISIBLE_LAYOUT_MARGIN_Y = 3_810_000
VISIBLE_LAYOUT_SHELF_WIDTH = VISIBLE_LAYOUT_SLOT_X * 16
MIXED_LAYOUT_BAND_GAP_Y = 5_080_000
DIFFERENT_FAMILY_LAYOUT_GAP_Y = 5_080_000
DIFFERENT_FAMILY_LAYOUT_MIN_SPACING = 3_810_000
MULTIPART_SUBPART_GAP_X = 5_080_000
MULTIPART_SUBPART_GAP_Y = 5_080_000
# Proteus terminal contacts use a 10-thou schematic grid.  This stays local to
# the beautifier so it can preserve native component pin frames without taking
# a dependency on the terminal emitter.
PROTEUS_TERMINAL_GRID = 254_000
SCAN_COORD_LIMIT = 30_000_000
MIN_COORD_ABS = 50_000
# General packet scanning remains intentionally conservative.  Its 700M
# ceiling prevents arbitrary binary payload from being mistaken for a moveable
# coordinate pair.
SAFE_PACKET_COORD_LIMIT = 700_000_000
SAFE_PACKET_MIN_COORD_ABS = 1_000_000
# A direct body marker is substantially narrower than the generic scanner: it
# is a family marker in the native component packet followed immediately by
# signed X/Y coordinates.  The locked mega's valid 30x native two-pin layout
# reaches 912,134,320, so this separate bound must cover the signed 32-bit
# working area without loosening the general scanner.  Keep headroom below
# INT32_MAX for the next scale probe while rejecting overflow-like payload.
STRICT_MARKER_BODY_COORD_LIMIT = 2_000_000_000

LINKED_COORDINATE_PLANS: dict[str, tuple[tuple[int, int], ...]] = {
    "SWITCH": ((2, 6), (68, 72), (143, 147), (208, 212), (359, 363)),
    "POT-HG": ((5, 9), (73, 77), (148, 152), (213, 217), (393, 397)),
    "DISPLAY_BRIDGE": ((5, 9), (76, 80), (150, 154), (215, 219), (343, 347)),
}

# Rejected by user Proteus testing on 2026-06-23:
# BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23 moved these fixed offsets and
# every case failed with LXLCORE.dll. Byte inspection showed the offsets were
# font/body constants, not the real mega-donor coordinate fields. Keep this
# table only as negative evidence so the same mistake is not repeated.
REJECTED_FAMILY_LAYOUT_COORDINATE_PLANS: dict[str, tuple[tuple[int, int], ...]] = {
    "RESISTOR": ((12, 16), (22, 26), (91, 95), (168, 172), (254, 258)),
    "CAP": ((12, 16), (22, 26), (91, 95), (163, 167), (277, 281)),
    "REALIND": ((12, 16), (22, 26), (91, 95), (167, 171), (281, 285)),
    "CAP-ELEC": ((13, 17), (23, 27), (92, 96), (169, 173), (234, 238)),
    "DIODE": ((12, 16), (22, 26), (93, 97), (167, 171), (232, 236)),
}
PARSED_PASSIVE_LAYOUT_FAMILIES = {
    "RESISTOR",
    "CAP",
    "REALIND",
    "CAP-ELEC",
    "DIODE",
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "NPN",
    "PNP",
    "2N3904",
    "2N4401",
    "2N7000",
    "BS170",
    "NMOSFET",
    "FUSE",
    "LED-RED",
    "BRIDGE",
    "TRAN-2P2S",
    "LM317T",
    "OPAMP",
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
}
PARSED_IC_LAYOUT_FAMILIES = {
    "4017",
    "4020",
    "74HC4024",
    "74HC4040",
    "74HC4060",
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC32",
    "74HC74",
    "74HC76",
    "74HC85",
    "74HC86",
    "74HC151",
    "74HC157",
    "74HC160",
    "74HC161",
    "74HC163",
    "74HC165",
    "74HC174",
    "74HC192",
    "74HC193",
    "74HC266",
    "74HC273",
    "74HC283",
    "74HC595",
    "4027",
    "4511",
    "7447",
    "7490",
    "LM741",
    "NE555",
}
BODY_MARKER_ALIASES: dict[str, tuple[str, ...]] = {
    # Refreshed 74HC4060 packets use 74HC4060 for text/model fields, but the
    # visible symbol body marker is the shorter Proteus marker "4060".  Moving
    # only the text fields strands the body at its donor-native coordinate.
    "74HC4060": ("4060",),
}
IC_LAYOUT_FAMILY_RE = re.compile(r"^(?:74HC\d+|\d{4})$")
DISPLAY_LAYOUT_FAMILIES = {
    "7SEG-COM-AN-BLUE",
    "7SEG-COM-CAT-BLUE",
    "7SEG-COM-MIXED",
}
DISPLAY_LAYOUT_MARKERS = (
    "7SEG-COM-ANODE",
    "7SEG-COM-CAT-BLUE",
)
LINKED_VISIBLE_LAYOUT_FAMILIES = {"SWITCH", "POT-HG"}
POT_HG_RELATIVE_COORDINATE_PAIRS = (
    (0, 4),
    (68, 72),
    (143, 147),
    (208, 212),
    (388, 392),
)

RELATIVE_MODES = {"relative", "linked_relative", "runaway_relative"}
ABSOLUTE_MODES = {"absolute", "linked_absolute", "runaway_absolute"}
DISPLAY_SMALL_RELATIVE_MODES = {"display_small_relative", "d20_small_relative"}
NOOP_MODES = {"", "none", "off", "metadata_only", "disabled"}
REF_RE = re.compile(
    rb"(?:U\d+(?::[A-Z])?|R\d+|C\d+|L\d+|Q\d+|D\d+|V\d+|I\d+|BR\d+|FU\d+|RV\d+|TR\d+)"
)


def _s32_at(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32_at(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)


def coordinate_plan_for_family(family: str) -> tuple[tuple[int, int], ...]:
    try:
        return LINKED_COORDINATE_PLANS[family]
    except KeyError as exc:
        raise ValueError(f"No packet coordinate plan is proven for {family}.") from exc


def is_ic_layout_family(family: str) -> bool:
    """Return whether a family belongs on the IC-only beautifier band."""

    return family in PARSED_IC_LAYOUT_FAMILIES or bool(
        IC_LAYOUT_FAMILY_RE.fullmatch(family)
    )


def _validate_pair_bounds(data: bytes, family: str, pairs: tuple[tuple[int, int], ...]) -> None:
    for x_offset, y_offset in pairs:
        if x_offset + 4 > len(data) or y_offset + 4 > len(data):
            raise ValueError(
                f"{family} coordinate pair ({x_offset}, {y_offset}) is outside packet size {len(data)}."
            )


def move_packet_coordinates(
    family: str,
    data: bytes,
    *,
    mode: str = DEFAULT_HIDDEN_COORDINATE_MODE,
    dx: int = HIDDEN_COORD_DX,
    dy: int = HIDDEN_COORD_DY,
    x: int = HIDDEN_ABSOLUTE_X,
    y: int = HIDDEN_ABSOLUTE_Y,
) -> bytes:
    """Return a packet with linked coordinate fields moved together.

    ``mode='none'`` returns the original bytes. Other modes are intentionally
    narrow and require a family-specific coordinate plan.
    """

    normalized = mode.lower()
    if normalized in NOOP_MODES:
        return data

    pairs = coordinate_plan_for_family(family)
    _validate_pair_bounds(data, family, pairs)
    out = bytearray(data)

    if normalized in DISPLAY_SMALL_RELATIVE_MODES:
        if family != "DISPLAY_BRIDGE":
            raise ValueError(f"{mode!r} is only proven for DISPLAY_BRIDGE packets.")
        for x_offset, y_offset in pairs:
            _put_s32_at(out, x_offset, _s32_at(out, x_offset) + D20_SMALL_COORD_DX)
            _put_s32_at(out, y_offset, _s32_at(out, y_offset) + D20_SMALL_COORD_DY)
        return bytes(out)

    if normalized in RELATIVE_MODES:
        for x_offset, y_offset in pairs:
            _put_s32_at(out, x_offset, _s32_at(out, x_offset) + dx)
            _put_s32_at(out, y_offset, _s32_at(out, y_offset) + dy)
        return bytes(out)

    if normalized in ABSOLUTE_MODES:
        for x_offset, y_offset in pairs:
            _put_s32_at(out, x_offset, x)
            _put_s32_at(out, y_offset, y)
        return bytes(out)

    raise ValueError(
        f"Unsupported hidden coordinate mode {mode!r}; "
        f"expected one of {sorted(NOOP_MODES | RELATIVE_MODES | ABSOLUTE_MODES | DISPLAY_SMALL_RELATIVE_MODES)}."
    )


def hide_packet(
    family: str,
    data: bytes,
    *,
    mode: str = DEFAULT_HIDDEN_COORDINATE_MODE,
) -> bytes:
    return move_packet_coordinates(family, data, mode=mode)


def _coord_ok(value: int) -> bool:
    return -SCAN_COORD_LIMIT <= value <= SCAN_COORD_LIMIT and value % 100 == 0


def _packet_coord_ok(value: int) -> bool:
    return -SAFE_PACKET_COORD_LIMIT <= value <= SAFE_PACKET_COORD_LIMIT and value % 10 == 0


def _packet_coord_pair_ok(x_value: int, y_value: int) -> bool:
    return (
        _packet_coord_ok(x_value)
        and _packet_coord_ok(y_value)
        and (abs(x_value) >= SAFE_PACKET_MIN_COORD_ABS or abs(y_value) >= SAFE_PACKET_MIN_COORD_ABS)
    )


def _strict_marker_body_coord_pair_ok(x_value: int, y_value: int) -> bool:
    """Return whether a direct component-body marker coordinate is valid.

    The general packet scanner deliberately ignores small integer pairs because
    arbitrary binary payload can resemble coordinates.  A strict marker-body
    record is narrower: the family marker is not a length-prefixed label or an
    embedded identifier, and its two following fields are the native body
    anchor.  Multipart spreading can legitimately move one subpart through
    the small-coordinate area before the whole packet is translated to its
    visible shelf.  Keep the general scanner conservative while preserving
    that real anchor for the second placement pass.
    """

    return (
        -STRICT_MARKER_BODY_COORD_LIMIT <= x_value <= STRICT_MARKER_BODY_COORD_LIMIT
        and -STRICT_MARKER_BODY_COORD_LIMIT <= y_value <= STRICT_MARKER_BODY_COORD_LIMIT
        and x_value % 10 == 0
        and y_value % 10 == 0
        and (x_value != 0 or y_value != 0)
    )


def _is_ascii_payload(data: bytes) -> bool:
    return bool(data) and all(byte in (9, 10, 13) or 32 <= byte < 127 for byte in data)


def _bidir_terminal_records(fragment: bytes) -> list[tuple[int, int, dict[str, Any]]]:
    records: list[tuple[int, int, dict[str, Any]]] = []
    try:
        events = bidir_events(b"\x00" + fragment + b"\xff")
    except ValueError:
        return records
    for event in events:
        start = int(event.start) - 1
        size = int(event.size)
        if start >= 0 and start + size <= len(fragment):
            records.append((start, start + size, event.as_dict()))
    return records


def _terminal_coord_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    for start, _end, event in _bidir_terminal_records(fragment):
        label_len = fragment[start + 30]
        label_x = start + 31 + label_len
        label_y = label_x + 4
        label = str(event.get("label", ""))
        pairs.append((start + 1, start + 5, f"terminal_symbol:{label}"))
        if label_y + 4 <= len(fragment):
            pairs.append((label_x, label_y, f"terminal_label:{label}"))
    return pairs


def _wire_coord_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    pos = 0
    while True:
        marker = fragment.find(b"WIRE", pos)
        if marker < 0:
            return pairs
        coord = marker + 9
        if coord + 16 <= len(fragment):
            pairs.append((coord, coord + 4, "wire_start"))
            pairs.append((coord + 8, coord + 12, "wire_end"))
        pos = marker + 1


def _masked_ranges(fragment: bytes) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    ranges.extend((start, end) for start, end, _event in _bidir_terminal_records(fragment))
    pos = 0
    while True:
        marker = fragment.find(b"WIRE", pos)
        if marker < 0:
            break
        ranges.append((marker + 9, marker + 25))
        pos = marker + 1
    return ranges


def _is_masked(offset: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= offset < end or start < offset + 8 <= end for start, end in ranges)


def _text_and_body_coord_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    ranges = _masked_ranges(fragment)
    offset = 0
    while offset <= len(fragment) - 8:
        if _is_masked(offset, ranges):
            offset += 1
            continue
        x_value = _s32_at(fragment, offset)
        y_value = _s32_at(fragment, offset + 4)
        if (
            _coord_ok(x_value)
            and _coord_ok(y_value)
            and not (x_value == 0 and y_value == 0)
            and (abs(x_value) >= MIN_COORD_ABS or abs(y_value) >= MIN_COORD_ABS)
        ):
            pairs.append((offset, offset + 4, "component_text_or_body"))
            offset += 8
            continue
        offset += 1
    return pairs


def _length_prefixed_text_coordinate_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    offset = 0
    while offset < len(fragment) - 10:
        if fragment[offset] != 0xFF:
            offset += 1
            continue
        text_length = fragment[offset + 1]
        text_start = offset + 2
        text_end = text_start + text_length
        x_offset = text_end
        y_offset = x_offset + 4
        if y_offset + 4 > len(fragment):
            offset += 1
            continue
        text = fragment[text_start:text_end]
        if _is_ascii_payload(text):
            x_value = _s32_at(fragment, x_offset)
            y_value = _s32_at(fragment, y_offset)
            if _packet_coord_pair_ok(x_value, y_value):
                label = text.decode("ascii", "ignore").strip().replace("\n", "\\n")
                pairs.append((x_offset, y_offset, f"length_prefixed_text:{label[:32]}"))
        offset += 1
    return pairs


def _subckt_name_coordinate_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    """Return the donor-proven non-length-prefixed ``SUBCKT NAME`` label pairs.

    Proteus IC packets store this text label as a literal followed by five zero
    bytes and ``FF 00`` before its signed X/Y pair.  It is not a normal
    length-prefixed text record, so the regular parsed coordinate scan must not
    accidentally infer it.  Callers opt in only when their family evidence
    proves this field belongs to the translated visible packet frame.
    """

    marker = b"SUBCKT NAME"
    prefix = b"\x00\x00\x00\x00\x00\xff\x00"
    pairs: list[tuple[int, int, str]] = []
    offset = 0
    while True:
        marker_offset = fragment.find(marker, offset)
        if marker_offset < 0:
            return pairs
        coordinate_offset = marker_offset + len(marker) + len(prefix)
        if (
            coordinate_offset + 8 <= len(fragment)
            and fragment[
                marker_offset + len(marker) : coordinate_offset
            ] == prefix
        ):
            x_value = _s32_at(fragment, coordinate_offset)
            y_value = _s32_at(fragment, coordinate_offset + 4)
            if _packet_coord_pair_ok(x_value, y_value):
                pairs.append(
                    (
                        coordinate_offset,
                        coordinate_offset + 4,
                        "subckt_name_label",
                    )
                )
        offset = marker_offset + 1


def _marker_body_coordinate_pairs(fragment: bytes, family: str) -> list[tuple[int, int, str]]:
    marker = family.encode("ascii", errors="ignore")
    if not marker:
        return []
    pairs: list[tuple[int, int, str]] = []
    offset = 0
    while True:
        marker_offset = fragment.find(marker, offset)
        if marker_offset < 0:
            return pairs
        x_offset = marker_offset + len(marker)
        y_offset = x_offset + 4
        if y_offset + 4 <= len(fragment):
            x_value = _s32_at(fragment, x_offset)
            y_value = _s32_at(fragment, y_offset)
            if _packet_coord_pair_ok(x_value, y_value):
                pairs.append((x_offset, y_offset, f"marker_body:{family}"))
        offset = marker_offset + 1
    return pairs


def _is_length_prefixed_text_marker(
    fragment: bytes,
    marker_offset: int,
    marker_length: int,
) -> bool:
    return (
        marker_offset >= 2
        and fragment[marker_offset - 2] == 0xFF
        and fragment[marker_offset - 1] == marker_length
    )


def _is_embedded_ascii_marker(
    fragment: bytes,
    marker_offset: int,
    marker_length: int,
) -> bool:
    before = fragment[marker_offset - 1] if marker_offset > 0 else 0
    return 48 <= before <= 57 or 65 <= before <= 90 or 97 <= before <= 122


def _strict_marker_body_coordinate_pairs(
    fragment: bytes,
    marker_text: str,
) -> list[tuple[int, int, str]]:
    marker = marker_text.encode("ascii", errors="ignore")
    if not marker:
        return []
    pairs: list[tuple[int, int, str]] = []
    offset = 0
    while True:
        marker_offset = fragment.find(marker, offset)
        if marker_offset < 0:
            return pairs
        x_offset = marker_offset + len(marker)
        y_offset = x_offset + 4
        if (
            y_offset + 4 <= len(fragment)
            and not _is_length_prefixed_text_marker(
                fragment,
                marker_offset,
                len(marker),
            )
            and not _is_embedded_ascii_marker(fragment, marker_offset, len(marker))
        ):
            x_value = _s32_at(fragment, x_offset)
            y_value = _s32_at(fragment, y_offset)
            if _strict_marker_body_coord_pair_ok(x_value, y_value):
                pairs.append((x_offset, y_offset, f"marker_body:{marker_text}"))
        offset = marker_offset + 1


def _parsed_family_coordinate_pairs(
    fragment: bytes,
    family: str,
    *,
    include_subckt_name_coordinates: bool = False,
) -> list[tuple[int, int, str]]:
    marker_pairs: list[tuple[int, int, str]] = []
    for marker_text in (family, *BODY_MARKER_ALIASES.get(family, ())):
        marker_pairs.extend(_strict_marker_body_coordinate_pairs(fragment, marker_text))
    pairs = _length_prefixed_text_coordinate_pairs(fragment) + marker_pairs
    if include_subckt_name_coordinates:
        pairs.extend(_subckt_name_coordinate_pairs(fragment))
    return _dedupe_coordinate_pairs(pairs)


def _display_coordinate_pairs(fragment: bytes) -> list[tuple[int, int, str]]:
    pairs: list[tuple[int, int, str]] = []
    # Display rows are anonymous records. These two coordinate pairs hold the
    # row anchor and Proteus-generated component-ID text (for example D103).
    # Leaving them behind moves the symbol but strands its generated name.
    for x_offset, y_offset, reason in (
        (4, 8, "display_row_anchor"),
        (70, 74, "display_component_id"),
    ):
        if y_offset + 4 <= len(fragment):
            x_value = _s32_at(fragment, x_offset)
            y_value = _s32_at(fragment, y_offset)
            if _packet_coord_pair_ok(x_value, y_value):
                pairs.append((x_offset, y_offset, reason))
    pairs.extend(_length_prefixed_text_coordinate_pairs(fragment))
    for marker in DISPLAY_LAYOUT_MARKERS:
        pairs.extend(_marker_body_coordinate_pairs(fragment, marker))
    return _dedupe_coordinate_pairs(pairs)


def _linked_visible_coordinate_pairs(fragment: bytes, family: str) -> list[tuple[int, int, str]]:
    if family == "POT-HG":
        if len(fragment) < 2 or fragment[0] != 0xFF:
            raise ValueError("POT-HG packet does not have the expected component-record header.")
        base = 2 + fragment[1]
        pairs = tuple((base + x_offset, base + y_offset) for x_offset, y_offset in POT_HG_RELATIVE_COORDINATE_PAIRS)
    else:
        pairs = coordinate_plan_for_family(family)
    _validate_pair_bounds(fragment, family, pairs)
    return [(x_offset, y_offset, f"linked_packet:{family}") for x_offset, y_offset in pairs]


def _dedupe_coordinate_pairs(pairs: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    seen: set[tuple[int, int]] = set()
    ordered: list[tuple[int, int, str]] = []
    for x_offset, y_offset, reason in pairs:
        key = (x_offset, y_offset)
        if key in seen:
            continue
        seen.add(key)
        ordered.append((x_offset, y_offset, reason))
    return ordered


def layout_coordinate_pairs(
    fragment: bytes,
    family: str | None = None,
    *,
    include_subckt_name_coordinates: bool = False,
) -> list[tuple[int, int, str]]:
    if family:
        if family in PARSED_PASSIVE_LAYOUT_FAMILIES or family in PARSED_IC_LAYOUT_FAMILIES:
            return _parsed_family_coordinate_pairs(
                fragment,
                family,
                include_subckt_name_coordinates=include_subckt_name_coordinates,
            )
        if family in DISPLAY_LAYOUT_FAMILIES:
            return _display_coordinate_pairs(fragment)
        if family in LINKED_VISIBLE_LAYOUT_FAMILIES:
            return _linked_visible_coordinate_pairs(fragment, family)
    pairs = _terminal_coord_pairs(fragment) + _wire_coord_pairs(fragment) + _text_and_body_coord_pairs(fragment)
    return _dedupe_coordinate_pairs(pairs)


def coordinate_bbox(fragment: bytes, pairs: list[tuple[int, int, str]]) -> dict[str, int]:
    xs = [_s32_at(fragment, x_offset) for x_offset, _y_offset, _reason in pairs]
    ys = [_s32_at(fragment, y_offset) for _x_offset, y_offset, _reason in pairs]
    return {
        "min_x": min(xs),
        "min_y": min(ys),
        "max_x": max(xs),
        "max_y": max(ys),
        "width": max(xs) - min(xs),
        "height": max(ys) - min(ys),
    }


def _subpart_refs(refs: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    if not refs:
        return ()
    out: list[str] = []
    for ref in refs:
        text = str(ref)
        if ":" in text and text not in out:
            out.append(text)
    return tuple(out)


def _multipart_columns(count: int) -> int:
    if count <= 1:
        return 1
    if count == 2:
        return 1
    if count <= 4:
        return 2
    return 3


def _snap_translation_delta_to_terminal_grid(delta: int) -> int:
    """Return the nearest signed translation that preserves terminal-grid pins."""

    half_grid = PROTEUS_TERMINAL_GRID // 2
    if delta >= 0:
        return ((delta + half_grid) // PROTEUS_TERMINAL_GRID) * PROTEUS_TERMINAL_GRID
    return -(((-delta + half_grid) // PROTEUS_TERMINAL_GRID) * PROTEUS_TERMINAL_GRID)


def spread_multipart_subpart_coordinates(
    data: bytes,
    family: str,
    refs: tuple[str, ...] | list[str] | None,
    *,
    gap_x: int = MULTIPART_SUBPART_GAP_X,
    gap_y: int = MULTIPART_SUBPART_GAP_Y,
    snap_translation_to_terminal_grid: bool = False,
    include_subckt_name_coordinates: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """Spread native A/B/C subpart clusters inside one Proteus packet.

    The component placer currently receives several logic/FF packages as one
    donor-native packet containing refs like ``U1:A`` and ``U1:B``.  Moving the
    whole packet preserves bytes but leaves the subparts at donor-native spacing.
    This helper keeps each subpart's internal text/body offsets together while
    increasing the spacing between subpart clusters.  It only edits coordinate
    fields already accepted by the parsed-coordinate beautifier.
    """

    subpart_refs = _subpart_refs(refs)
    if len(subpart_refs) < 2:
        return data, {"applied": False, "reason": "not_multipart"}

    pairs = layout_coordinate_pairs(
        data,
        family,
        include_subckt_name_coordinates=include_subckt_name_coordinates,
    )
    if not pairs:
        return data, {"applied": False, "reason": "no_layout_coordinate_pairs"}

    label_starts: list[tuple[int, str]] = []
    wanted = set(subpart_refs)
    for x_offset, _y_offset, reason in pairs:
        if not reason.startswith("length_prefixed_text:"):
            continue
        label = reason.removeprefix("length_prefixed_text:")
        if label in wanted:
            label_starts.append((x_offset, label))
    label_starts.sort()
    if len(label_starts) < len(subpart_refs):
        return data, {
            "applied": False,
            "reason": "missing_subpart_label_coordinate",
            "subpart_refs": list(subpart_refs),
            "found_labels": [label for _offset, label in label_starts],
        }

    clusters: dict[str, list[tuple[int, int, str]]] = {label: [] for _offset, label in label_starts}
    unassigned: list[tuple[int, int, str]] = []
    sorted_starts = list(label_starts)
    for pair in pairs:
        x_offset = pair[0]
        selected_label: str | None = None
        for index, (start, label) in enumerate(sorted_starts):
            next_start = sorted_starts[index + 1][0] if index + 1 < len(sorted_starts) else None
            if x_offset >= start and (next_start is None or x_offset < next_start):
                selected_label = label
                break
        if selected_label is None:
            unassigned.append(pair)
        else:
            clusters[selected_label].append(pair)

    if any(not cluster for cluster in clusters.values()):
        return data, {
            "applied": False,
            "reason": "empty_subpart_cluster",
            "subpart_refs": list(subpart_refs),
        }

    before_all = coordinate_bbox(data, pairs)
    cluster_before = {
        label: coordinate_bbox(data, cluster)
        for label, cluster in clusters.items()
    }
    max_width = max(int(bbox["width"]) for bbox in cluster_before.values())
    max_height = max(int(bbox["height"]) for bbox in cluster_before.values())
    columns = _multipart_columns(len(clusters))
    out = bytearray(data)
    cluster_after: dict[str, dict[str, int]] = {}
    for cluster_index, (label, cluster) in enumerate(clusters.items()):
        row = cluster_index // columns
        column = cluster_index % columns
        bbox = cluster_before[label]
        target_min_x = before_all["min_x"] + column * (max_width + gap_x)
        target_min_y = before_all["min_y"] + row * (max_height + gap_y)
        dx = target_min_x - int(bbox["min_x"])
        dy = target_min_y - int(bbox["min_y"])
        requested_target_min_x = target_min_x
        requested_target_min_y = target_min_y
        if snap_translation_to_terminal_grid:
            dx = _snap_translation_delta_to_terminal_grid(dx)
            dy = _snap_translation_delta_to_terminal_grid(dy)
            target_min_x = int(bbox["min_x"]) + dx
            target_min_y = int(bbox["min_y"]) + dy
        for x_offset, y_offset, _reason in cluster:
            _put_s32_at(out, x_offset, _s32_at(out, x_offset) + dx)
            _put_s32_at(out, y_offset, _s32_at(out, y_offset) + dy)
        cluster_after[label] = {
            "min_x": target_min_x,
            "min_y": target_min_y,
            "max_x": target_min_x + int(bbox["width"]),
            "max_y": target_min_y + int(bbox["height"]),
            "width": int(bbox["width"]),
            "height": int(bbox["height"]),
            "dx": dx,
            "dy": dy,
            "terminal_grid_translation": snap_translation_to_terminal_grid,
            "requested_target_min_x": requested_target_min_x,
            "requested_target_min_y": requested_target_min_y,
            "row": row,
            "column": column,
        }

    translated = bytes(out)
    after_pairs = layout_coordinate_pairs(
        translated,
        family,
        include_subckt_name_coordinates=include_subckt_name_coordinates,
    )
    return translated, {
        "applied": translated != data,
        "method": "subpart_label_offset_clusters",
        "subpart_refs": list(clusters),
        "columns": columns,
        "gap_x": gap_x,
        "gap_y": gap_y,
        "before_bbox": before_all,
        "after_bbox": coordinate_bbox(translated, after_pairs),
        "subpart_bboxes_before": cluster_before,
        "subpart_bboxes_after": cluster_after,
        "unassigned_coordinate_pair_count": len(unassigned),
    }


def refs_in_packet(data: bytes) -> tuple[str, ...]:
    return tuple(sorted(set(match.group().decode("ascii") for match in REF_RE.finditer(data))))


def translate_packet_to_slot(
    data: bytes,
    *,
    slot: int,
    key: str,
    family: str,
    columns: int = VISIBLE_LAYOUT_COLUMNS,
    origin_x: int = VISIBLE_LAYOUT_ORIGIN_X,
    origin_y: int = VISIBLE_LAYOUT_ORIGIN_Y,
    slot_x: int = VISIBLE_LAYOUT_SLOT_X,
    slot_y: int = VISIBLE_LAYOUT_SLOT_Y,
) -> tuple[bytes, dict[str, Any]]:
    pairs = layout_coordinate_pairs(data, family)
    if not pairs:
        return data, {
            "key": key,
            "family": family,
            "slot": slot,
            "translated": False,
            "reason": "no layout coordinate pairs found",
        }

    before = coordinate_bbox(data, pairs)
    col = slot % columns
    row = slot // columns
    dx = origin_x + col * slot_x - before["min_x"]
    dy = origin_y + row * slot_y - before["min_y"]
    out = bytearray(data)
    for x_offset, y_offset, _reason in pairs:
        _put_s32_at(out, x_offset, _s32_at(out, x_offset) + dx)
        _put_s32_at(out, y_offset, _s32_at(out, y_offset) + dy)
    translated = bytes(out)
    reason_counts = Counter(reason for _x_offset, _y_offset, reason in pairs)
    marker = family.encode("ascii", errors="ignore")
    return translated, {
        "key": key,
        "family": family,
        "slot": slot,
        "layout_mode": "fixed_slot_grid",
        "translated": translated != data,
        "dx": dx,
        "dy": dy,
        "coordinate_pair_count": len(pairs),
        "coordinate_reason_counts": dict(sorted(reason_counts.items())),
        "before_bbox": before,
        "after_bbox": coordinate_bbox(translated, pairs),
        "refs_unchanged": refs_in_packet(data) == refs_in_packet(translated),
        "marker_count_before": data.count(marker) if marker else 0,
        "marker_count_after": translated.count(marker) if marker else 0,
    }


def translate_packet_to_position(
    data: bytes,
    *,
    key: str,
    family: str,
    target_min_x: int,
    target_min_y: int,
    slot: int | None = None,
    row: int | None = None,
    column: int | None = None,
    allocation_width: int | None = None,
    allocation_height: int | None = None,
    snap_translation_to_terminal_grid: bool = False,
    include_subckt_name_coordinates: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    """Move a complete packet so its parsed bbox begins at an explicit point."""

    pairs = layout_coordinate_pairs(
        data,
        family,
        include_subckt_name_coordinates=include_subckt_name_coordinates,
    )
    if not pairs:
        entry: dict[str, Any] = {
            "key": key,
            "family": family,
            "translated": False,
            "layout_mode": "footprint_shelf",
            "reason": "no layout coordinate pairs found",
            "target_min_x": target_min_x,
            "target_min_y": target_min_y,
        }
        if slot is not None:
            entry["slot"] = slot
        if row is not None:
            entry["row"] = row
        if column is not None:
            entry["column"] = column
        return data, entry

    before = coordinate_bbox(data, pairs)
    dx = target_min_x - before["min_x"]
    dy = target_min_y - before["min_y"]
    requested_target_min_x = target_min_x
    requested_target_min_y = target_min_y
    if snap_translation_to_terminal_grid:
        dx = _snap_translation_delta_to_terminal_grid(dx)
        dy = _snap_translation_delta_to_terminal_grid(dy)
        target_min_x = int(before["min_x"]) + dx
        target_min_y = int(before["min_y"]) + dy
    out = bytearray(data)
    for x_offset, y_offset, _reason in pairs:
        _put_s32_at(out, x_offset, _s32_at(out, x_offset) + dx)
        _put_s32_at(out, y_offset, _s32_at(out, y_offset) + dy)
    translated = bytes(out)
    reason_counts = Counter(reason for _x_offset, _y_offset, reason in pairs)
    marker = family.encode("ascii", errors="ignore")
    entry = {
        "key": key,
        "family": family,
        "layout_mode": "footprint_shelf",
        "translated": translated != data,
        "dx": dx,
        "dy": dy,
        "target_min_x": target_min_x,
        "target_min_y": target_min_y,
        "requested_target_min_x": requested_target_min_x,
        "requested_target_min_y": requested_target_min_y,
        "terminal_grid_translation": snap_translation_to_terminal_grid,
        "coordinate_pair_count": len(pairs),
        "coordinate_reason_counts": dict(sorted(reason_counts.items())),
        "before_bbox": before,
        "after_bbox": coordinate_bbox(translated, pairs),
        "refs_unchanged": refs_in_packet(data) == refs_in_packet(translated),
        "marker_count_before": data.count(marker) if marker else 0,
        "marker_count_after": translated.count(marker) if marker else 0,
    }
    if slot is not None:
        entry["slot"] = slot
    if row is not None:
        entry["row"] = row
    if column is not None:
        entry["column"] = column
    if allocation_width is not None:
        entry["allocation_width"] = allocation_width
    if allocation_height is not None:
        entry["allocation_height"] = allocation_height
    return translated, entry


def translate_packet_by_delta(
    data: bytes,
    *,
    key: str,
    family: str,
    dx: int,
    dy: int,
) -> tuple[bytes, dict[str, Any]]:
    """Move every parsed coordinate field in one complete packet by a delta."""

    pairs = layout_coordinate_pairs(data, family)
    if not pairs:
        return data, {
            "key": key,
            "family": family,
            "translated": False,
            "reason": "no layout coordinate pairs found",
        }

    before = coordinate_bbox(data, pairs)
    out = bytearray(data)
    for x_offset, y_offset, _reason in pairs:
        _put_s32_at(out, x_offset, _s32_at(out, x_offset) + dx)
        _put_s32_at(out, y_offset, _s32_at(out, y_offset) + dy)
    translated = bytes(out)
    reason_counts = Counter(reason for _x_offset, _y_offset, reason in pairs)
    return translated, {
        "key": key,
        "family": family,
        "translated": translated != data,
        "dx": dx,
        "dy": dy,
        "coordinate_pair_count": len(pairs),
        "coordinate_reason_counts": dict(sorted(reason_counts.items())),
        "before_bbox": before,
        "after_bbox": coordinate_bbox(translated, pairs),
        "refs_unchanged": refs_in_packet(data) == refs_in_packet(translated),
    }
