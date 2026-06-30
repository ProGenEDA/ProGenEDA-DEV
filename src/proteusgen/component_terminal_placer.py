"""Bidirectional terminal placement for component-placer output.

This stage appends complete donor-derived `$TERBIDIR` records to an already
generated component-placement project.

Terminal attachment is family-specific. The rejected V2 bounding-box helper is
retained for diagnostic compatibility, but production experiments must use a
researched family handler that patches pin-link suffixes and emits any
donor-proven short-wire records required by that family.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Any, Iterable

from .bidirectional import BIDIR_MARKER, build_bidir_record, load_production_templates
from .component_beautifier import coordinate_bbox, layout_coordinate_pairs
from .pdsprj import read_internal_file, write_project_from_parts
from .mixed_passive import _load_manual_cap_templates, _manual_cap_suffixes
from .resistor_v9 import (
    _extract_object_chunk,
    _load_templates as _load_resistor_templates,
    _patch_wire,
    build_dsn,
)
from .templates import FixtureRegistry


TERMINAL_MARGIN = 0
MAX_TERMINALS_PER_SIDE = 8
LEFT_SIDE_ANGLE = 1800
RIGHT_SIDE_ANGLE = 0
RESISTOR_PIN_SPAN = 1_270_000
CAP_PIN_HALF_SPAN = 508_000
CAP_TERMINAL_SYMBOL_TO_PIN = 254_000
INDUCTOR_PIN_HALF_SPAN = 762_000
INDUCTOR_TERMINAL_SYMBOL_TO_PIN = 254_000
TERMINAL_SYMBOL_TO_PIN = 508_000
TERMINAL_CONTACT_TO_PIN = 254_000
CAP_WIRE_RECORD_SIZE = 50
CAP_TRIMMED_WIRE_RECORD_SIZE = 49
INDUCTOR_INPUT_RECORD_SIZE = 103
INDUCTOR_OUTPUT_RECORD_SIZE = 104
INDUCTOR_COMPONENT_RECORD_SIZE = 374
INDUCTOR_WIRE_RECORD_SIZE = 50
INDUCTOR_TRIMMED_WIRE_RECORD_SIZE = 49
INDUCTOR_DONOR_GROUP_SIZE = (
    INDUCTOR_INPUT_RECORD_SIZE
    + INDUCTOR_OUTPUT_RECORD_SIZE
    + INDUCTOR_COMPONENT_RECORD_SIZE
    + INDUCTOR_WIRE_RECORD_SIZE
    + INDUCTOR_TRIMMED_WIRE_RECORD_SIZE
)
TWO_PIN_FAMILIES = {
    "RESISTOR",
    "CAP",
    "CAP-ELEC",
    "REALIND",
    "DIODE",
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "LED-RED",
    "FUSE",
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
}
INFRASTRUCTURE_FAMILIES = {"DISPLAY_BRIDGE"}
INFRASTRUCTURE_KEYS = {"D20", "DISPLAY_ANODE_SENTINEL"}


@dataclass(frozen=True)
class TerminalSpec:
    label: str
    symbol_x: int
    symbol_y: int
    angle_tenths: int
    suffix: int
    component_key: str
    component_family: str
    pin_hint: str
    attachment_policy: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "symbol_x": self.symbol_x,
            "symbol_y": self.symbol_y,
            "angle_tenths": self.angle_tenths,
            "suffix": f"{self.suffix:04x}",
            "component_key": self.component_key,
            "component_family": self.component_family,
            "pin_hint": self.pin_hint,
            "attachment_policy": self.attachment_policy,
        }


@dataclass(frozen=True)
class ResistorTerminalPair:
    component_key: str
    component_family: str
    left: TerminalSpec
    right: TerminalSpec
    left_pin_x: int
    left_pin_y: int
    right_pin_x: int
    right_pin_y: int
    left_wire_start_x: int
    left_wire_start_y: int
    right_wire_start_x: int
    right_wire_start_y: int
    component_x_offset: int
    component_y_offset: int
    input_link_offset: int
    output_link_offset: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_key": self.component_key,
            "component_family": self.component_family,
            "left": self.left.as_dict(),
            "right": self.right.as_dict(),
            "pins": {
                "left": {"x": self.left_pin_x, "y": self.left_pin_y},
                "right": {"x": self.right_pin_x, "y": self.right_pin_y},
            },
            "short_wires": {
                "left": {
                    "start": {"x": self.left_wire_start_x, "y": self.left_wire_start_y},
                    "end": {"x": self.left_pin_x, "y": self.left_pin_y},
                },
                "right": {
                    "start": {"x": self.right_wire_start_x, "y": self.right_wire_start_y},
                    "end": {"x": self.right_pin_x, "y": self.right_pin_y},
                },
            },
            "packet_offsets": {
                "component_x": self.component_x_offset,
                "component_y": self.component_y_offset,
                "input_link": self.input_link_offset,
                "output_link": self.output_link_offset,
            },
        }


@dataclass(frozen=True)
class CapacitorTerminalPair:
    component_key: str
    component_family: str
    left: TerminalSpec
    right: TerminalSpec
    left_pin_x: int
    left_pin_y: int
    right_pin_x: int
    right_pin_y: int
    left_wire_start_x: int
    left_wire_start_y: int
    right_wire_start_x: int
    right_wire_start_y: int
    component_x_offset: int
    component_y_offset: int
    input_link_offset: int
    output_link_offset: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_key": self.component_key,
            "component_family": self.component_family,
            "left": self.left.as_dict(),
            "right": self.right.as_dict(),
            "pins": {
                "left": {"x": self.left_pin_x, "y": self.left_pin_y},
                "right": {"x": self.right_pin_x, "y": self.right_pin_y},
            },
            "short_wires": {
                "left": {
                    "start": {"x": self.left_wire_start_x, "y": self.left_wire_start_y},
                    "end": {"x": self.left_pin_x, "y": self.left_pin_y},
                },
                "right": {
                    "start": {"x": self.right_wire_start_x, "y": self.right_wire_start_y},
                    "end": {"x": self.right_pin_x, "y": self.right_pin_y},
                },
            },
            "packet_offsets": {
                "component_x": self.component_x_offset,
                "component_y": self.component_y_offset,
                "input_link": self.input_link_offset,
                "output_link": self.output_link_offset,
            },
        }


InductorTerminalPair = CapacitorTerminalPair


@dataclass(frozen=True)
class InductorDonorTemplates:
    header: bytes
    wire_lefts: tuple[bytes, ...]
    wire_rights: tuple[bytes, ...]
    donor_chunk: bytes


def _s32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _u32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=False)


def _compact_terminal_label(prefix: str, terminal_index: int) -> str:
    """Return the donor-safe two-character label used by researched families."""

    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(prefix) != 1 or prefix not in alphabet:
        raise ValueError("CAP/v2 label prefix must be one uppercase ASCII letter or digit.")
    if not 0 <= terminal_index < len(alphabet):
        raise ValueError(
            "This terminal handler currently supports at most 18 components because its accepted "
            "donor path uses two-character terminal labels."
        )
    return prefix + alphabet[terminal_index]


def _inductor_suffixes(index: int) -> tuple[int, int]:
    step = 0x02A8
    return (
        (0x01B2 + (index - 1) * step) & 0xFFFF,
        (0x01E4 + (index - 1) * step) & 0xFFFF,
    )


def _resistor_body_offsets(data: bytes) -> tuple[int, int]:
    candidates = [
        (x_offset, y_offset)
        for x_offset, y_offset, reason in layout_coordinate_pairs(data, "RESISTOR")
        if reason == "marker_body:RESISTOR"
    ]
    if len(candidates) != 1:
        raise ValueError(
            "RESISTOR terminal attachment needs exactly one parsed structural body anchor; "
            f"found {len(candidates)}."
        )
    return candidates[0]


def _cap_body_offsets(data: bytes) -> tuple[int, int]:
    candidates = [
        (x_offset, y_offset)
        for x_offset, y_offset, reason in layout_coordinate_pairs(data, "CAP")
        if reason == "marker_body:CAP"
    ]
    if not candidates:
        marker = b"CAP"
        search_from = len(data)
        while True:
            marker_offset = data.rfind(marker, 0, search_from)
            if marker_offset < 0:
                break
            x_offset = marker_offset + len(marker)
            y_offset = x_offset + 4
            if y_offset + 4 <= len(data):
                x_value = _s32_at(data, x_offset)
                y_value = _s32_at(data, y_offset)
                if (
                    -700_000_000 <= x_value <= 700_000_000
                    and -700_000_000 <= y_value <= 700_000_000
                    and x_value % 10 == 0
                    and y_value % 10 == 0
                    and not (x_value == 0 and y_value == 0)
                ):
                    candidates.append((x_offset, y_offset))
                    break
            search_from = marker_offset
    if len(candidates) != 1:
        raise ValueError(
            "CAP terminal attachment needs exactly one parsed structural body anchor; "
            f"found {len(candidates)}."
        )
    return candidates[0]


def _realind_body_offsets(data: bytes) -> tuple[int, int]:
    candidates = [
        (x_offset, y_offset)
        for x_offset, y_offset, reason in layout_coordinate_pairs(data, "REALIND")
        if reason == "marker_body:REALIND"
    ]
    if not candidates:
        marker_offset = data.rfind(b"REALIND")
        if marker_offset >= 0:
            x_offset = marker_offset + len(b"REALIND")
            y_offset = x_offset + 4
            if y_offset + 4 <= len(data):
                x_value = _s32_at(data, x_offset)
                y_value = _s32_at(data, y_offset)
                if (
                    -700_000_000 <= x_value <= 700_000_000
                    and -700_000_000 <= y_value <= 700_000_000
                    and x_value % 10 == 0
                    and y_value % 10 == 0
                    and not (x_value == 0 and y_value == 0)
                ):
                    candidates.append((x_offset, y_offset))
    if len(candidates) != 1:
        raise ValueError(
            "REALIND terminal attachment needs exactly one parsed structural body anchor; "
            f"found {len(candidates)}."
        )
    return candidates[0]


def plan_attached_resistor_terminals(
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "R",
    suffix_start: int = 0x7100,
) -> tuple[ResistorTerminalPair, ...]:
    """Plan donor-proven terminals and short wires for horizontal resistors."""

    pairs: list[ResistorTerminalPair] = []
    for index, group in enumerate(selected_groups, start=1):
        family = str(getattr(group, "family", ""))
        key = str(getattr(group, "key", ""))
        if family != "RESISTOR":
            raise ValueError(
                "The attached-terminal V3 handler currently supports RESISTOR only; "
                f"received {family or '<unknown>'} ({key or '<unknown>'})."
            )
        data = getattr(group, "data", b"")
        if not isinstance(data, bytes):
            data = bytes(data)
        x_offset, y_offset = _resistor_body_offsets(data)
        angle_tenths = _u32_at(data, x_offset + 8)
        if angle_tenths != 0:
            raise ValueError(
                f"RESISTOR {key} uses unproven orientation {angle_tenths}; "
                "V3 accepts horizontal donor packets only."
            )

        left_pin_x = _s32_at(data, x_offset)
        left_pin_y = _s32_at(data, y_offset)
        right_pin_x = left_pin_x + RESISTOR_PIN_SPAN
        right_pin_y = left_pin_y
        left_suffix = (suffix_start + (index - 1) * 2 + 1) & 0xFFFF
        right_suffix = (suffix_start + (index - 1) * 2 + 2) & 0xFFFF
        left = TerminalSpec(
            label=f"{label_prefix}{index:03d}A",
            symbol_x=left_pin_x - TERMINAL_SYMBOL_TO_PIN,
            symbol_y=left_pin_y,
            angle_tenths=LEFT_SIDE_ANGLE,
            suffix=left_suffix,
            component_key=key,
            component_family=family,
            pin_hint="pin:1",
            attachment_policy="resistor_link_suffix_and_short_wire",
        )
        right = TerminalSpec(
            label=f"{label_prefix}{index:03d}B",
            symbol_x=right_pin_x + TERMINAL_SYMBOL_TO_PIN,
            symbol_y=right_pin_y,
            angle_tenths=RIGHT_SIDE_ANGLE,
            suffix=right_suffix,
            component_key=key,
            component_family=family,
            pin_hint="pin:2",
            attachment_policy="resistor_link_suffix_and_short_wire",
        )
        input_link_offset = x_offset + 25
        output_link_offset = x_offset + 29
        if output_link_offset + 4 > len(data):
            raise ValueError(f"RESISTOR {key} packet ends before its pin-link fields.")
        pairs.append(
            ResistorTerminalPair(
                component_key=key,
                component_family=family,
                left=left,
                right=right,
                left_pin_x=left_pin_x,
                left_pin_y=left_pin_y,
                right_pin_x=right_pin_x,
                right_pin_y=right_pin_y,
                left_wire_start_x=left_pin_x - TERMINAL_CONTACT_TO_PIN,
                left_wire_start_y=left_pin_y,
                right_wire_start_x=right_pin_x + TERMINAL_CONTACT_TO_PIN,
                right_wire_start_y=right_pin_y,
                component_x_offset=x_offset,
                component_y_offset=y_offset,
                input_link_offset=input_link_offset,
                output_link_offset=output_link_offset,
            )
        )
    return tuple(pairs)


def plan_attached_capacitor_terminals(
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "C",
) -> tuple[CapacitorTerminalPair, ...]:
    """Plan CAP/v2 using the accepted manual capacitor donor geometry."""

    pairs: list[CapacitorTerminalPair] = []
    for index, group in enumerate(selected_groups, start=1):
        family = str(getattr(group, "family", ""))
        key = str(getattr(group, "key", ""))
        if family != "CAP":
            raise ValueError(
                "The attached-terminal CAP handler currently supports CAP only; "
                f"received {family or '<unknown>'} ({key or '<unknown>'})."
            )
        data = getattr(group, "data", b"")
        if not isinstance(data, bytes):
            data = bytes(data)
        x_offset, y_offset = _cap_body_offsets(data)
        body_x = _s32_at(data, x_offset)
        body_y = _s32_at(data, y_offset)
        left_pin_x = body_x - CAP_PIN_HALF_SPAN
        left_pin_y = body_y
        right_pin_x = body_x + CAP_PIN_HALF_SPAN
        right_pin_y = body_y
        left_suffix, right_suffix = _manual_cap_suffixes(index)
        left = TerminalSpec(
            label=_compact_terminal_label(label_prefix, (index - 1) * 2),
            symbol_x=left_pin_x - CAP_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=left_pin_y,
            angle_tenths=LEFT_SIDE_ANGLE,
            suffix=left_suffix,
            component_key=key,
            component_family=family,
            pin_hint="pin:1",
            attachment_policy="cap_link_suffix_and_short_wire",
        )
        right = TerminalSpec(
            label=_compact_terminal_label(label_prefix, (index - 1) * 2 + 1),
            symbol_x=right_pin_x + CAP_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=right_pin_y,
            angle_tenths=RIGHT_SIDE_ANGLE,
            suffix=right_suffix,
            component_key=key,
            component_family=family,
            pin_hint="pin:2",
            attachment_policy="cap_link_suffix_and_short_wire",
        )
        pairs.append(
            CapacitorTerminalPair(
                component_key=key,
                component_family=family,
                left=left,
                right=right,
                left_pin_x=left_pin_x,
                left_pin_y=left_pin_y,
                right_pin_x=right_pin_x,
                right_pin_y=right_pin_y,
                left_wire_start_x=left_pin_x,
                left_wire_start_y=left_pin_y,
                right_wire_start_x=right_pin_x,
                right_wire_start_y=right_pin_y,
                component_x_offset=x_offset,
                component_y_offset=y_offset,
                input_link_offset=x_offset + 29,
                output_link_offset=x_offset + 25,
            )
        )
    return tuple(pairs)


def plan_attached_inductor_terminals(
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "L",
) -> tuple[InductorTerminalPair, ...]:
    """Plan REALIND/v2 from the accepted six-inductor donor geometry."""

    pairs: list[InductorTerminalPair] = []
    for index, group in enumerate(selected_groups, start=1):
        family = str(getattr(group, "family", ""))
        key = str(getattr(group, "key", ""))
        if family != "REALIND":
            raise ValueError(
                "The attached-terminal REALIND handler currently supports REALIND only; "
                f"received {family or '<unknown>'} ({key or '<unknown>'})."
            )
        data = getattr(group, "data", b"")
        if not isinstance(data, bytes):
            data = bytes(data)
        x_offset, y_offset = _realind_body_offsets(data)
        angle_tenths = _u32_at(data, x_offset + 8)
        if angle_tenths != 0:
            raise ValueError(
                f"REALIND {key} uses unproven orientation {angle_tenths}; "
                "V1 accepts horizontal donor packets only."
            )

        body_x = _s32_at(data, x_offset)
        body_y = _s32_at(data, y_offset)
        left_pin_x = body_x - INDUCTOR_PIN_HALF_SPAN
        right_pin_x = body_x + INDUCTOR_PIN_HALF_SPAN
        left_suffix, right_suffix = _inductor_suffixes(index)
        left = TerminalSpec(
            label=_compact_terminal_label(label_prefix, (index - 1) * 2),
            symbol_x=left_pin_x - INDUCTOR_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=body_y,
            angle_tenths=LEFT_SIDE_ANGLE,
            suffix=left_suffix,
            component_key=key,
            component_family=family,
            pin_hint="pin:1",
            attachment_policy="realind_link_suffix_and_short_wire",
        )
        right = TerminalSpec(
            label=_compact_terminal_label(label_prefix, (index - 1) * 2 + 1),
            symbol_x=right_pin_x + INDUCTOR_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=body_y,
            angle_tenths=RIGHT_SIDE_ANGLE,
            suffix=right_suffix,
            component_key=key,
            component_family=family,
            pin_hint="pin:2",
            attachment_policy="realind_link_suffix_and_short_wire",
        )
        pairs.append(
            InductorTerminalPair(
                component_key=key,
                component_family=family,
                left=left,
                right=right,
                left_pin_x=left_pin_x,
                left_pin_y=body_y,
                right_pin_x=right_pin_x,
                right_pin_y=body_y,
                left_wire_start_x=left_pin_x,
                left_wire_start_y=body_y,
                right_wire_start_x=right_pin_x,
                right_wire_start_y=body_y,
                component_x_offset=x_offset,
                component_y_offset=y_offset,
                input_link_offset=x_offset + 25,
                output_link_offset=x_offset + 29,
            )
        )
    return tuple(pairs)


def _patch_resistor_terminal_links(
    data: bytes,
    pair: ResistorTerminalPair,
) -> bytes:
    out = bytearray(data)
    for offset, terminal in (
        (pair.input_link_offset, pair.left),
        (pair.output_link_offset, pair.right),
    ):
        out[offset : offset + 2] = struct.pack("<H", terminal.suffix)
        out[offset + 2] = 0x01
        out[offset + 3] = 0x00
    out[-1] = 0x00
    return bytes(out)


def _patch_capacitor_terminal_links(
    data: bytes,
    pair: CapacitorTerminalPair,
) -> bytes:
    out = bytearray(data)
    for offset, terminal in (
        (pair.output_link_offset, pair.right),
        (pair.input_link_offset, pair.left),
    ):
        out[offset : offset + 2] = struct.pack("<H", terminal.suffix)
        out[offset + 2] = 0x01
        out[offset + 3] = 0x00
    out[-1] = 0x00
    return bytes(out)


def _patch_inductor_terminal_links(
    data: bytes,
    pair: InductorTerminalPair,
) -> bytes:
    out = bytearray(data)
    for offset, terminal in (
        (pair.input_link_offset, pair.left),
        (pair.output_link_offset, pair.right),
    ):
        if offset + 4 > len(out):
            raise ValueError(f"REALIND {pair.component_key} packet ends before its pin-link fields.")
        out[offset : offset + 2] = struct.pack("<H", terminal.suffix)
        out[offset + 2] = 0x01
        out[offset + 3] = 0x00
    out[-1] = 0x00
    return bytes(out)


def _load_six_inductor_templates(project: Path) -> InductorDonorTemplates:
    chunk = _extract_object_chunk(read_internal_file(project, "ROOT.DSN"))
    expected_size = 1 + 5 * INDUCTOR_DONOR_GROUP_SIZE + (
        INDUCTOR_DONOR_GROUP_SIZE + 1
    )
    if (
        len(chunk) != expected_size
        or chunk[:1] != b"\x00"
        or chunk[-1:] != b"\xff"
        or chunk.count(b"$TERINPUT") != 6
        or chunk.count(b"$TEROUTPUT") != 6
        or chunk.count(b"REALIND") != 18
        or chunk.count(b"\x7fWIRE") != 12
    ):
        raise ValueError("Six-inductor donor does not match its accepted sequential shape.")

    wire_lefts: list[bytes] = []
    wire_rights: list[bytes] = []
    cursor = 1
    for index in range(6):
        cursor += INDUCTOR_INPUT_RECORD_SIZE + INDUCTOR_OUTPUT_RECORD_SIZE
        component = chunk[cursor : cursor + INDUCTOR_COMPONENT_RECORD_SIZE]
        cursor += INDUCTOR_COMPONENT_RECORD_SIZE
        left_wire = chunk[cursor : cursor + INDUCTOR_WIRE_RECORD_SIZE]
        cursor += INDUCTOR_WIRE_RECORD_SIZE
        right_size = (
            INDUCTOR_WIRE_RECORD_SIZE
            if index == 5
            else INDUCTOR_TRIMMED_WIRE_RECORD_SIZE
        )
        right_wire = chunk[cursor : cursor + right_size]
        cursor += right_size
        body_x_offset, _body_y_offset = _realind_body_offsets(component)
        if (
            len(component) != INDUCTOR_COMPONENT_RECORD_SIZE
            or component.count(b"REALIND") != 3
            or component[body_x_offset + 25 : body_x_offset + 27] == b"\x00\x00"
            or component[body_x_offset + 29 : body_x_offset + 31] == b"\x00\x00"
            or len(left_wire) != INDUCTOR_WIRE_RECORD_SIZE
            or len(right_wire) != right_size
            or left_wire.count(b"\x7fWIRE") != 1
            or right_wire.count(b"\x7fWIRE") != 1
        ):
            raise ValueError(f"Six-inductor donor group {index + 1} is malformed.")
        wire_lefts.append(left_wire)
        wire_rights.append(right_wire)
    if cursor != len(chunk):
        raise ValueError(
            f"Six-inductor donor cursor ended at {cursor}, expected {len(chunk)}."
        )
    return InductorDonorTemplates(
        header=chunk[:1],
        wire_lefts=tuple(wire_lefts),
        wire_rights=tuple(wire_rights),
        donor_chunk=chunk,
    )


def attach_resistor_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "R",
    suffix_start: int = 0x7100,
) -> dict[str, Any]:
    """Attach bidirectional terminals to bare resistor packets.

    The emitted object order follows the accepted locked resistor route:
    left terminals, right terminals, separator, then each resistor followed by
    two donor-derived short-wire records.
    """

    groups = tuple(selected_groups)
    for group in groups:
        data = bytes(getattr(group, "data", b""))
        if BIDIR_MARKER in data or b"\x7fWIRE" in data:
            raise ValueError(
                "RESISTOR/v3 requires bare component-placer packets; "
                f"{getattr(group, 'key', '<unknown>')} already contains terminal or wire records."
            )
    pairs = plan_attached_resistor_terminals(
        groups,
        label_prefix=label_prefix,
        suffix_start=suffix_start,
    )
    registry = FixtureRegistry.load()
    terminal_templates = load_production_templates(registry)
    resistor_fixture = registry.get("r21_v9_resistor_terminal_donor")
    resistor_templates = _load_resistor_templates(
        read_internal_file(resistor_fixture.path, "ROOT.DSN"),
        resistor_fixture.path,
    )

    left_records = [
        build_bidir_record(
            terminal_templates,
            label=pair.left.label,
            symbol_x=pair.left.symbol_x,
            symbol_y=pair.left.symbol_y,
            angle_tenths=pair.left.angle_tenths,
            suffix=pair.left.suffix,
            active_link=True,
        )
        for pair in pairs
    ]
    right_records = [
        build_bidir_record(
            terminal_templates,
            label=pair.right.label,
            symbol_x=pair.right.symbol_x,
            symbol_y=pair.right.symbol_y,
            angle_tenths=pair.right.angle_tenths,
            suffix=pair.right.suffix,
            active_link=True,
        )
        for pair in pairs
    ]
    component_records: list[bytes] = []
    for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
        component_records.append(_patch_resistor_terminal_links(bytes(group.data), pair))
        _resistor, left_wire_template, right_wire_template = resistor_templates.groups[
            index % len(resistor_templates.groups)
        ]
        component_records.append(
            _patch_wire(
                left_wire_template,
                pair.left_wire_start_x,
                pair.left_wire_start_y,
                pair.left_pin_x,
                pair.left_pin_y,
            )
        )
        component_records.append(
            _patch_wire(
                right_wire_template,
                pair.right_wire_start_x,
                pair.right_wire_start_y,
                pair.right_pin_x,
                pair.right_pin_y,
            )
        )

    source = Path(project)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError(
            "RESISTOR/v3 base project is not bare; choose the main mega donor "
            "before applying terminal attachment."
        )
    new_chunk = (
        original_chunk[:1]
        + b"".join(left_records)
        + b"".join(right_records)
        + b"\x00"
        + b"".join(component_records)
    )
    if not new_chunk:
        raise ValueError("RESISTOR terminal attachment produced an empty object chunk.")
    new_chunk = new_chunk[:-1] + b"\xff"
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, output, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    expected_terminals = len(pairs) * 2
    expected_wires = len(pairs) * 2
    return {
        "stage": "terminal_placer",
        "family_handler": "RESISTOR/v3",
        "terminal_kind": "$TERBIDIR",
        "wire_record_emission": True,
        "attachment_policy": "resistor_link_suffix_and_short_wire",
        "terminal_count_added": expected_terminals,
        "wire_count_added": expected_wires,
        "terminal_pairs": [pair.as_dict() for pair in pairs],
        "bidir_count_before": original_chunk.count(BIDIR_MARKER),
        "bidir_count_after": final_chunk.count(BIDIR_MARKER),
        "wire_count_before": original_chunk.count(b"\x7fWIRE"),
        "wire_count_after": final_chunk.count(b"\x7fWIRE"),
        "object_chunk_size_before": len(original_chunk),
        "object_chunk_size_after": len(final_chunk),
        "valid": (
            final_chunk.count(BIDIR_MARKER) == expected_terminals
            and final_chunk.count(b"\x7fWIRE") == expected_wires
            and final_chunk.endswith(b"\xff")
        ),
    }


def attach_capacitor_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "C",
) -> dict[str, Any]:
    """Attach CAP/v2 terminals using the accepted capacitor-native object order."""

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("CAP/v2 requires at least one selected capacitor packet.")
    for group in groups:
        data = bytes(getattr(group, "data", b""))
        if BIDIR_MARKER in data or b"\x7fWIRE" in data:
            raise ValueError(
                "CAP/v2 requires bare component-placer packets; "
                f"{getattr(group, 'key', '<unknown>')} already contains terminal or wire records."
            )
    pairs = plan_attached_capacitor_terminals(
        groups,
        label_prefix=label_prefix,
    )
    registry = FixtureRegistry.load()
    terminal_templates = load_production_templates(registry)
    manual_cap_fixture = registry.get("cap2_with_terminals_manual")
    manual_cap_templates = _load_manual_cap_templates(manual_cap_fixture.path)

    right_records = [
        build_bidir_record(
            terminal_templates,
            label=pair.right.label,
            symbol_x=pair.right.symbol_x,
            symbol_y=pair.right.symbol_y,
            angle_tenths=pair.right.angle_tenths,
            suffix=pair.right.suffix,
            active_link=True,
        )
        for pair in pairs
    ]
    cap_groups: list[bytes] = []
    group_reports: list[dict[str, Any]] = []
    for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
        data = bytes(group.data)
        if not data.startswith(b"\xff"):
            raise ValueError(
                f"CAP/v2 expected {pair.component_key} to start with its donor FF boundary."
            )
        left_record = build_bidir_record(
            terminal_templates,
            label=pair.left.label,
            symbol_x=pair.left.symbol_x,
            symbol_y=pair.left.symbol_y,
            angle_tenths=pair.left.angle_tenths,
            suffix=pair.left.suffix,
            active_link=True,
        )
        component_record = b"\x00" + _patch_capacitor_terminal_links(data, pair)
        template_index = index % len(manual_cap_templates.wire_lefts)
        left_wire = _patch_wire(
            manual_cap_templates.wire_rights[template_index],
            pair.left_wire_start_x,
            pair.left_wire_start_y,
            pair.left_pin_x,
            pair.left_pin_y,
        )
        right_wire = _patch_wire(
            manual_cap_templates.wire_lefts[template_index],
            pair.right_wire_start_x,
            pair.right_wire_start_y,
            pair.right_pin_x,
            pair.right_pin_y,
        )
        is_final = index == len(groups) - 1
        if not is_final:
            right_wire = right_wire[:-1]
        cap_groups.extend((left_record, component_record, left_wire, right_wire))
        group_reports.append(
            {
                "component_key": pair.component_key,
                "left_terminal_size": len(left_record),
                "bare_component_size": len(data),
                "component_record_size": len(component_record),
                "left_wire_size": len(left_wire),
                "right_wire_size": len(right_wire),
                "right_wire_final": is_final,
            }
        )

    source = Path(project)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError(
            "CAP/v2 base project is not bare; choose the main mega donor "
            "before applying terminal attachment."
        )
    new_chunk = (
        original_chunk[:1]
        + b"".join(right_records)
        + b"".join(cap_groups)
    )
    if not new_chunk:
        raise ValueError("CAP terminal attachment produced an empty object chunk.")
    new_chunk = new_chunk[:-1] + b"\xff"
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, output, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    expected_terminals = len(pairs) * 2
    expected_wires = len(pairs) * 2
    expected_right_wire_sizes = [
        CAP_WIRE_RECORD_SIZE if index == len(pairs) - 1 else CAP_TRIMMED_WIRE_RECORD_SIZE
        for index in range(len(pairs))
    ]
    suffix_counts_valid = all(
        final_chunk.count(struct.pack("<H", terminal.suffix)) >= 2
        for pair in pairs
        for terminal in (pair.left, pair.right)
    )
    return {
        "stage": "terminal_placer",
        "family_handler": "CAP/v2",
        "terminal_kind": "$TERBIDIR",
        "wire_record_emission": True,
        "attachment_policy": "cap_native_order_links_and_zero_length_pin_records",
        "object_order": "right_bidir_array_then_left_bidir_component_left_wire_right_wire_groups",
        "label_policy": "two_character_prefix_plus_base36_terminal_index",
        "suffix_policy": "cap2_with_terminals_manual_0x0238_progression",
        "terminal_count_added": expected_terminals,
        "wire_count_added": expected_wires,
        "terminal_pairs": [pair.as_dict() for pair in pairs],
        "group_records": group_reports,
        "bidir_count_before": original_chunk.count(BIDIR_MARKER),
        "bidir_count_after": final_chunk.count(BIDIR_MARKER),
        "wire_count_before": original_chunk.count(b"\x7fWIRE"),
        "wire_count_after": final_chunk.count(b"\x7fWIRE"),
        "object_chunk_size_before": len(original_chunk),
        "object_chunk_size_after": len(final_chunk),
        "manual_cap_donor": str(manual_cap_fixture.path),
        "valid": (
            final_chunk == new_chunk
            and final_chunk.count(BIDIR_MARKER) == expected_terminals
            and final_chunk.count(b"\x7fWIRE") == expected_wires
            and all(
                item["component_record_size"] == item["bare_component_size"] + 1
                for item in group_reports
            )
            and [item["right_wire_size"] for item in group_reports]
            == expected_right_wire_sizes
            and all(item["left_wire_size"] == CAP_WIRE_RECORD_SIZE for item in group_reports)
            and all(pair.left_wire_start_x == pair.left_pin_x for pair in pairs)
            and all(pair.right_wire_start_x == pair.right_pin_x for pair in pairs)
            and suffix_counts_valid
            and final_chunk.endswith(b"\xff")
        ),
    }


def attach_inductor_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "L",
) -> dict[str, Any]:
    """Attach REALIND/v2 using the accepted six-inductor sequential schema."""

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("REALIND/v2 requires at least one selected inductor packet.")
    for group in groups:
        data = bytes(getattr(group, "data", b""))
        if BIDIR_MARKER in data or b"\x7fWIRE" in data:
            raise ValueError(
                "REALIND/v2 requires bare component-placer packets; "
                f"{getattr(group, 'key', '<unknown>')} already contains terminal or wire records."
            )
    pairs = plan_attached_inductor_terminals(groups, label_prefix=label_prefix)
    registry = FixtureRegistry.load()
    terminal_templates = load_production_templates(registry)
    manual_fixture = registry.get("inductor_05_six_terminal")
    donor_templates = _load_six_inductor_templates(manual_fixture.path)

    object_records: list[bytes] = []
    group_reports: list[dict[str, Any]] = []
    for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
        data = bytes(group.data)
        if not data.startswith(b"\xff"):
            raise ValueError(
                f"REALIND/v2 expected {pair.component_key} to start with its donor FF boundary."
            )
        left_record = build_bidir_record(
            terminal_templates,
            label=pair.left.label,
            symbol_x=pair.left.symbol_x,
            symbol_y=pair.left.symbol_y,
            angle_tenths=pair.left.angle_tenths,
            suffix=pair.left.suffix,
            active_link=True,
        )
        right_record = build_bidir_record(
            terminal_templates,
            label=pair.right.label,
            symbol_x=pair.right.symbol_x,
            symbol_y=pair.right.symbol_y,
            angle_tenths=pair.right.angle_tenths,
            suffix=pair.right.suffix,
            active_link=True,
        )
        component_record = b"\x00" + _patch_inductor_terminal_links(data, pair)
        template_index = index % len(donor_templates.wire_lefts)
        left_wire = _patch_wire(
            donor_templates.wire_lefts[template_index],
            pair.left_pin_x,
            pair.left_pin_y,
            pair.left_pin_x,
            pair.left_pin_y,
        )
        right_template = donor_templates.wire_rights[template_index]
        is_final = index == len(groups) - 1
        if len(right_template) == INDUCTOR_TRIMMED_WIRE_RECORD_SIZE:
            right_template += b"\x00"
        right_wire = _patch_wire(
            right_template,
            pair.right_pin_x,
            pair.right_pin_y,
            pair.right_pin_x,
            pair.right_pin_y,
        )
        if not is_final:
            right_wire = right_wire[:-1]
        object_records.extend(
            (left_record, right_record, component_record, left_wire, right_wire)
        )
        group_reports.append(
            {
                "component_key": pair.component_key,
                "left_terminal_size": len(left_record),
                "right_terminal_size": len(right_record),
                "bare_component_size": len(data),
                "component_record_size": len(component_record),
                "left_wire_size": len(left_wire),
                "right_wire_size": len(right_wire),
                "right_wire_final": is_final,
                "donor_slot": template_index + 1,
            }
        )

    source = Path(project)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError(
            "REALIND/v2 base project is not bare; choose the main mega donor "
            "before applying terminal attachment."
        )
    new_chunk = original_chunk[:1] + b"".join(object_records)
    new_chunk = new_chunk[:-1] + b"\xff"
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, output, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    expected_terminals = len(pairs) * 2
    expected_wires = len(pairs) * 2
    expected_right_wire_sizes = [
        (
            INDUCTOR_WIRE_RECORD_SIZE
            if index == len(pairs) - 1
            else INDUCTOR_TRIMMED_WIRE_RECORD_SIZE
        )
        for index in range(len(pairs))
    ]
    suffix_counts_valid = all(
        final_chunk.count(struct.pack("<H", terminal.suffix)) >= 2
        for pair in pairs
        for terminal in (pair.left, pair.right)
    )
    return {
        "stage": "terminal_placer",
        "family_handler": "REALIND/v2",
        "terminal_kind": "$TERBIDIR",
        "wire_record_emission": True,
        "attachment_policy": "realind_donor05_sequential_zero_length_pin_records",
        "object_order": "repeated_left_bidir_right_bidir_realind_left_wire_right_wire",
        "label_policy": "two_character_prefix_plus_base36_terminal_index",
        "suffix_policy": "inductor_05_six_terminal_0x02a8_progression",
        "terminal_count_added": expected_terminals,
        "wire_count_added": expected_wires,
        "terminal_pairs": [pair.as_dict() for pair in pairs],
        "group_records": group_reports,
        "bidir_count_before": original_chunk.count(BIDIR_MARKER),
        "bidir_count_after": final_chunk.count(BIDIR_MARKER),
        "wire_count_before": original_chunk.count(b"\x7fWIRE"),
        "wire_count_after": final_chunk.count(b"\x7fWIRE"),
        "object_chunk_size_before": len(original_chunk),
        "object_chunk_size_after": len(final_chunk),
        "manual_inductor_donor": str(manual_fixture.path),
        "valid": (
            final_chunk == new_chunk
            and final_chunk.count(BIDIR_MARKER) == expected_terminals
            and final_chunk.count(b"\x7fWIRE") == expected_wires
            and all(
                item["component_record_size"] == item["bare_component_size"] + 1
                for item in group_reports
            )
            and [item["right_wire_size"] for item in group_reports]
            == expected_right_wire_sizes
            and all(
                item["left_wire_size"] == INDUCTOR_WIRE_RECORD_SIZE
                for item in group_reports
            )
            and all(pair.left_wire_start_x == pair.left_pin_x for pair in pairs)
            and all(pair.right_wire_start_x == pair.right_pin_x for pair in pairs)
            and suffix_counts_valid
            and final_chunk.endswith(b"\xff")
        ),
    }


def attach_component_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    label_prefix: str | None = None,
    suffix_start: int | None = None,
) -> dict[str, Any]:
    """Shared entrypoint that dispatches to the proven family handler."""

    groups = tuple(selected_groups)
    families = {str(getattr(group, "family", "")) for group in groups}
    if len(families) != 1:
        raise ValueError(
            "Shared terminal attachment currently requires a single-family selection; "
            f"received {sorted(families)}."
        )
    family = next(iter(families))
    if family == "RESISTOR":
        return attach_resistor_bidir_terminals_to_project(
            project,
            output,
            groups,
            label_prefix=label_prefix or "R",
            suffix_start=0x7100 if suffix_start is None else suffix_start,
        )
    if family == "CAP":
        if suffix_start is not None:
            raise ValueError("CAP/v2 uses donor-native suffix progression; suffix_start is unsupported.")
        return attach_capacitor_bidir_terminals_to_project(
            project,
            output,
            groups,
            label_prefix=label_prefix or "C",
        )
    if family == "REALIND":
        if suffix_start is not None:
            raise ValueError(
                "REALIND/v2 uses donor-native suffix progression; suffix_start is unsupported."
            )
        return attach_inductor_bidir_terminals_to_project(
            project,
            output,
            groups,
            label_prefix=label_prefix or "L",
        )
    raise ValueError(
        "Shared terminal attachment has no accepted handler for "
        f"{family}. Add the family-specific logic to component_terminal_placer.py."
    )


def _side_y_candidates(
    data: bytes,
    pairs: Iterable[tuple[int, int] | tuple[int, int, str]],
    *,
    side: str,
    min_x: int,
    max_x: int,
    max_count: int,
) -> tuple[int, ...]:
    coords: list[tuple[int, int]] = []
    for pair in pairs:
        x_offset, y_offset = pair[:2]
        if x_offset + 4 <= len(data) and y_offset + 4 <= len(data):
            coords.append((_s32_at(data, x_offset), _s32_at(data, y_offset)))
    if not coords:
        return ()
    width = max(1, max_x - min_x)
    tolerance = max(254_000, width // 4)
    edge_x = min_x if side == "left" else max_x
    candidates = sorted(
        y for x, y in coords
        if abs(x - edge_x) <= tolerance
    )
    if not candidates:
        candidates = sorted(y for _x, y in coords)
    deduped: list[int] = []
    for y in candidates:
        if not deduped or abs(y - deduped[-1]) >= 127_000:
            deduped.append(y)
    if len(deduped) <= max_count:
        return tuple(deduped)
    if max_count <= 1:
        return (deduped[len(deduped) // 2],)
    step = (len(deduped) - 1) / (max_count - 1)
    return tuple(deduped[round(i * step)] for i in range(max_count))


def plan_side_bidir_terminals(
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "N",
    suffix_start: int = 0x7100,
    max_terminals_per_side: int = MAX_TERMINALS_PER_SIDE,
) -> tuple[TerminalSpec, ...]:
    """Plan unattached left/right diagnostic terminals for component packets.

    This rejected V2 compatibility helper must not be used as attachment proof.
    """

    specs: list[TerminalSpec] = []
    index = 0
    for group in selected_groups:
        family = str(getattr(group, "family", ""))
        key = str(getattr(group, "key", ""))
        if family in INFRASTRUCTURE_FAMILIES or key in INFRASTRUCTURE_KEYS:
            continue
        data = getattr(group, "data", b"")
        if not isinstance(data, bytes):
            data = bytes(data)
        pairs = layout_coordinate_pairs(data, family)
        if not pairs:
            continue
        bbox = coordinate_bbox(data, pairs)
        min_x = int(bbox["min_x"])
        max_x = int(bbox["max_x"])
        mid_y = int((int(bbox["min_y"]) + int(bbox["max_y"])) // 2)
        if family in TWO_PIN_FAMILIES:
            left_ys = (mid_y,)
            right_ys = (mid_y,)
        else:
            left_ys = _side_y_candidates(
                data,
                pairs,
                side="left",
                min_x=min_x,
                max_x=max_x,
                max_count=max_terminals_per_side,
            ) or (mid_y,)
            right_ys = _side_y_candidates(
                data,
                pairs,
                side="right",
                min_x=min_x,
                max_x=max_x,
                max_count=max_terminals_per_side,
            ) or (mid_y,)
        anchors = [
            *(
                (min_x - TERMINAL_MARGIN, y, LEFT_SIDE_ANGLE, f"left:{slot}")
                for slot, y in enumerate(left_ys, start=1)
            ),
            *(
                (max_x + TERMINAL_MARGIN, y, RIGHT_SIDE_ANGLE, f"right:{slot}")
                for slot, y in enumerate(right_ys, start=1)
            ),
        ]
        for x, y, angle, pin_hint in anchors:
            index += 1
            specs.append(
                TerminalSpec(
                    label=f"{label_prefix}{index:03d}",
                    symbol_x=x,
                    symbol_y=y,
                    angle_tenths=angle,
                    suffix=(suffix_start + index) & 0xFFFF,
                    component_key=key,
                    component_family=family,
                    pin_hint=pin_hint,
                    attachment_policy="bbox_side_anchor_no_wire",
                )
            )
    return tuple(specs)


def append_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    terminal_specs: Iterable[TerminalSpec],
) -> dict[str, Any]:
    """Append unattached V2 diagnostic terminals to `project` and write `output`."""

    specs = tuple(terminal_specs)
    templates = load_production_templates(FixtureRegistry.load())
    records = [
        build_bidir_record(
            templates,
            label=spec.label,
            symbol_x=spec.symbol_x,
            symbol_y=spec.symbol_y,
            angle_tenths=spec.angle_tenths,
            suffix=spec.suffix,
            active_link=False,
        )
        for spec in specs
    ]

    source = Path(project)
    dsn = read_internal_file(source, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[-1] != 0xFF:
        raise ValueError("Cannot append terminals: object chunk has no final FF terminator.")
    new_chunk = chunk[:-1] + b"".join(records) + b"\xff"
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, output, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    return {
        "stage": "terminal_placer_diagnostic_v2",
        "status": "rejected_unattached",
        "terminal_kind": "$TERBIDIR",
        "wire_record_emission": False,
        "attachment_policy": "bbox_side_anchor_no_wire",
        "terminal_count_added": len(specs),
        "terminal_specs": [spec.as_dict() for spec in specs],
        "bidir_count_before": chunk.count(BIDIR_MARKER),
        "bidir_count_after": final_chunk.count(BIDIR_MARKER),
        "object_chunk_size_before": len(chunk),
        "object_chunk_size_after": len(final_chunk),
        "valid": final_chunk.count(BIDIR_MARKER) == chunk.count(BIDIR_MARKER) + len(specs),
    }
