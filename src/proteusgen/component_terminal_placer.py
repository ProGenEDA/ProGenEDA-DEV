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
import shutil
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
from .templates import FixtureRegistry, repository_root


TERMINAL_MARGIN = 0
MAX_TERMINALS_PER_SIDE = 8
LEFT_SIDE_ANGLE = 1800
RIGHT_SIDE_ANGLE = 0
RESISTOR_PIN_SPAN = 1_270_000
CAP_PIN_HALF_SPAN = 508_000
CAP_TERMINAL_SYMBOL_TO_PIN = 254_000
CAP_ELEC_PIN_HALF_SPAN = 508_000
CAP_ELEC_TERMINAL_SYMBOL_TO_PIN = 254_000
INDUCTOR_PIN_HALF_SPAN = 762_000
INDUCTOR_TERMINAL_SYMBOL_TO_PIN = 254_000
TERMINAL_SYMBOL_TO_PIN = 508_000
TERMINAL_CONTACT_TO_PIN = 254_000
CAP_WIRE_RECORD_SIZE = 50
CAP_TRIMMED_WIRE_RECORD_SIZE = 49
CAP_ELEC_BIDIR_RECORD_SIZE = 101
CAP_ELEC_COMPONENT_RECORD_SIZE = 379
CAP_ELEC_WIRE_RECORD_SIZE = 50
CAP_ELEC_TRIMMED_WIRE_RECORD_SIZE = 49
CAP_ELEC_DONOR_GROUP_SIZE = (
    CAP_ELEC_BIDIR_RECORD_SIZE * 2
    + CAP_ELEC_COMPONENT_RECORD_SIZE
    + CAP_ELEC_WIRE_RECORD_SIZE
    + CAP_ELEC_TRIMMED_WIRE_RECORD_SIZE
)
SOURCE_PIN_X_FROM_BODY = 508_000
SOURCE_UPPER_PIN_Y_FROM_BODY = 254_000
SOURCE_LOWER_PIN_Y_FROM_BODY = -1_270_000
SOURCE_TERMINAL_SYMBOL_TO_PIN = 254_000
SOURCE_COMPONENT_BARE_BASE_SIZES = {
    "VSOURCE": 340,
    "CSOURCE": 342,
}
ACCEPTED_TERMINAL_FAMILY_ORDER = (
    "VSOURCE",
    "CSOURCE",
    "CAP",
    "CAP-ELEC",
    "REALIND",
    "RESISTOR",
)
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
ElectrolyticCapTerminalPair = CapacitorTerminalPair


@dataclass(frozen=True)
class InductorDonorTemplates:
    header: bytes
    wire_lefts: tuple[bytes, ...]
    wire_rights: tuple[bytes, ...]
    donor_chunk: bytes


@dataclass(frozen=True)
class ElectrolyticCapDonorTemplates:
    header: bytes
    wire_lefts: tuple[bytes, ...]
    wire_rights: tuple[bytes, ...]
    donor_chunk: bytes


@dataclass(frozen=True)
class SourceDonorTemplates:
    family: str
    input_wire: bytes
    output_wire: bytes
    donor_chunk: bytes
    donor_path: Path


@dataclass(frozen=True)
class SourceTerminalPair:
    component_key: str
    component_family: str
    input: TerminalSpec
    output: TerminalSpec
    input_pin_x: int
    input_pin_y: int
    output_pin_x: int
    output_pin_y: int
    input_wire_start_x: int
    input_wire_start_y: int
    output_wire_start_x: int
    output_wire_start_y: int
    component_x_offset: int
    component_y_offset: int
    input_link_offset: int
    output_link_offset: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "component_key": self.component_key,
            "component_family": self.component_family,
            "input": self.input.as_dict(),
            "output": self.output.as_dict(),
            "pins": {
                "input": {"x": self.input_pin_x, "y": self.input_pin_y},
                "output": {"x": self.output_pin_x, "y": self.output_pin_y},
            },
            "short_wires": {
                "input": {
                    "start": {
                        "x": self.input_wire_start_x,
                        "y": self.input_wire_start_y,
                    },
                    "end": {"x": self.input_pin_x, "y": self.input_pin_y},
                },
                "output": {
                    "start": {
                        "x": self.output_wire_start_x,
                        "y": self.output_wire_start_y,
                    },
                    "end": {"x": self.output_pin_x, "y": self.output_pin_y},
                },
            },
            "packet_offsets": {
                "component_x": self.component_x_offset,
                "component_y": self.component_y_offset,
                "input_link": self.input_link_offset,
                "output_link": self.output_link_offset,
            },
        }


def _s32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _u32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=False)


def _compact_terminal_label(prefix: str, terminal_index: int) -> str:
    """Return the donor-safe two-character label used by researched families."""

    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(prefix) != 1 or prefix not in alphabet:
        raise ValueError(
            "Terminal label prefix must be one uppercase ASCII letter or digit."
        )
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


def _cap_elec_suffixes(index: int) -> tuple[int, int]:
    step = 0x02A8
    return (
        (0x0120 + (index - 1) * step) & 0xFFFF,
        (0x0152 + (index - 1) * step) & 0xFFFF,
    )


def _source_suffixes(index: int) -> tuple[int, int]:
    output_suffix = 0x7000 + (index - 1) * 0x80
    return output_suffix & 0xFFFF, (output_suffix + 0x32) & 0xFFFF


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


def _cap_elec_body_offsets(data: bytes) -> tuple[int, int]:
    candidates = [
        (x_offset, y_offset)
        for x_offset, y_offset, reason in layout_coordinate_pairs(data, "CAP-ELEC")
        if reason == "marker_body:CAP-ELEC"
    ]
    if not candidates:
        marker_offset = data.rfind(b"CAP-ELEC")
        if marker_offset >= 0:
            x_offset = marker_offset + len(b"CAP-ELEC")
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
            "CAP-ELEC terminal attachment needs exactly one parsed structural body anchor; "
            f"found {len(candidates)}."
        )
    return candidates[0]


def _source_body_offsets(data: bytes, family: str) -> tuple[int, int]:
    candidates = [
        (x_offset, y_offset)
        for x_offset, y_offset, reason in layout_coordinate_pairs(data, family)
        if reason == f"marker_body:{family}"
    ]
    if not candidates:
        marker_offset = data.rfind(family.encode("ascii"))
        if marker_offset >= 0:
            x_offset = marker_offset + len(family)
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
            f"{family} terminal attachment needs exactly one parsed structural body anchor; "
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
                "V2 accepts horizontal donor packets only."
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


def plan_attached_electrolytic_capacitor_terminals(
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "E",
) -> tuple[ElectrolyticCapTerminalPair, ...]:
    """Plan CAP-ELEC/v3 from the accepted eight-component donor geometry."""

    pairs: list[ElectrolyticCapTerminalPair] = []
    for index, group in enumerate(selected_groups, start=1):
        family = str(getattr(group, "family", ""))
        key = str(getattr(group, "key", ""))
        if family != "CAP-ELEC":
            raise ValueError(
                "The attached-terminal CAP-ELEC handler supports CAP-ELEC only; "
                f"received {family or '<unknown>'} ({key or '<unknown>'})."
            )
        data = getattr(group, "data", b"")
        if not isinstance(data, bytes):
            data = bytes(data)
        if len(data) != CAP_ELEC_COMPONENT_RECORD_SIZE:
            raise ValueError(
                f"CAP-ELEC/v3 requires the accepted {CAP_ELEC_COMPONENT_RECORD_SIZE}-byte "
                f"full-mega packet; {key} has {len(data)} bytes."
            )
        x_offset, y_offset = _cap_elec_body_offsets(data)
        angle_tenths = _u32_at(data, x_offset + 8)
        if angle_tenths != 0:
            raise ValueError(
                f"CAP-ELEC {key} uses unproven orientation {angle_tenths}; "
                "V3 accepts horizontal donor packets only."
            )

        body_x = _s32_at(data, x_offset)
        body_y = _s32_at(data, y_offset)
        left_pin_x = body_x - CAP_ELEC_PIN_HALF_SPAN
        right_pin_x = body_x + CAP_ELEC_PIN_HALF_SPAN
        left_suffix, right_suffix = _cap_elec_suffixes(index)
        left = TerminalSpec(
            label=_compact_terminal_label(label_prefix, (index - 1) * 2),
            symbol_x=left_pin_x - CAP_ELEC_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=body_y,
            angle_tenths=LEFT_SIDE_ANGLE,
            suffix=left_suffix,
            component_key=key,
            component_family=family,
            pin_hint="left_pin",
            attachment_policy="cap_elec_native_links_and_zero_length_pin_records",
        )
        right = TerminalSpec(
            label=_compact_terminal_label(label_prefix, (index - 1) * 2 + 1),
            symbol_x=right_pin_x + CAP_ELEC_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=body_y,
            angle_tenths=RIGHT_SIDE_ANGLE,
            suffix=right_suffix,
            component_key=key,
            component_family=family,
            pin_hint="right_pin",
            attachment_policy="cap_elec_native_links_and_zero_length_pin_records",
        )
        pairs.append(
            ElectrolyticCapTerminalPair(
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


def plan_attached_source_terminals(
    selected_groups: Iterable[Any],
    *,
    label_prefix: str | None = None,
    source_index_start: int = 1,
) -> tuple[SourceTerminalPair, ...]:
    """Plan VSOURCE/CSOURCE from the accepted role-correct V3 source routes."""

    groups = tuple(selected_groups)
    families = {str(getattr(group, "family", "")) for group in groups}
    if (
        len(families) != 1
        or next(iter(families), "") not in SOURCE_COMPONENT_BARE_BASE_SIZES
    ):
        raise ValueError(
            "The attached source-terminal handler requires one VSOURCE or CSOURCE family; "
            f"received {sorted(families)}."
        )
    family = next(iter(families))
    prefix = label_prefix or ("V" if family == "VSOURCE" else "I")
    base_size = SOURCE_COMPONENT_BARE_BASE_SIZES[family]
    if source_index_start < 1:
        raise ValueError("source_index_start must be at least 1.")

    pairs: list[SourceTerminalPair] = []
    for local_index, group in enumerate(groups, start=1):
        source_index = source_index_start + local_index - 1
        key = str(getattr(group, "key", ""))
        data = getattr(group, "data", b"")
        if not isinstance(data, bytes):
            data = bytes(data)
        expected_size = base_size + len(key)
        if len(data) != expected_size:
            raise ValueError(
                f"{family}/v4 requires the accepted {expected_size}-byte packet; "
                f"{key} has {len(data)} bytes."
            )
        x_offset, y_offset = _source_body_offsets(data, family)
        angle_tenths = _u32_at(data, x_offset + 8)
        if angle_tenths != 0:
            raise ValueError(
                f"{family} {key} uses unproven orientation {angle_tenths}; "
                "V4 accepts the horizontal donor packet only."
            )

        body_x = _s32_at(data, x_offset)
        body_y = _s32_at(data, y_offset)
        upper_pin = (
            body_x + SOURCE_PIN_X_FROM_BODY,
            body_y + SOURCE_UPPER_PIN_Y_FROM_BODY,
        )
        lower_pin = (
            body_x + SOURCE_PIN_X_FROM_BODY,
            body_y + SOURCE_LOWER_PIN_Y_FROM_BODY,
        )
        output_suffix, input_suffix = _source_suffixes(source_index)
        if family == "VSOURCE":
            output_pin = upper_pin
            input_pin = lower_pin
            output_label_index = (local_index - 1) * 2
            input_label_index = output_label_index + 1
            output_link_offset = x_offset + 25
            input_link_offset = x_offset + 29
        else:
            input_pin = upper_pin
            output_pin = lower_pin
            input_label_index = (local_index - 1) * 2
            output_label_index = input_label_index + 1
            input_link_offset = x_offset + 25
            output_link_offset = x_offset + 29

        input_terminal = TerminalSpec(
            label=_compact_terminal_label(prefix, input_label_index),
            symbol_x=input_pin[0] - SOURCE_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=input_pin[1],
            angle_tenths=LEFT_SIDE_ANGLE,
            suffix=input_suffix,
            component_key=key,
            component_family=family,
            pin_hint="negative/input",
            attachment_policy="source_native_role_links_and_zero_length_pin_records",
        )
        output_terminal = TerminalSpec(
            label=_compact_terminal_label(prefix, output_label_index),
            symbol_x=output_pin[0] + SOURCE_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=output_pin[1],
            angle_tenths=RIGHT_SIDE_ANGLE,
            suffix=output_suffix,
            component_key=key,
            component_family=family,
            pin_hint="positive/output",
            attachment_policy="source_native_role_links_and_zero_length_pin_records",
        )
        pairs.append(
            SourceTerminalPair(
                component_key=key,
                component_family=family,
                input=input_terminal,
                output=output_terminal,
                input_pin_x=input_pin[0],
                input_pin_y=input_pin[1],
                output_pin_x=output_pin[0],
                output_pin_y=output_pin[1],
                input_wire_start_x=input_pin[0],
                input_wire_start_y=input_pin[1],
                output_wire_start_x=output_pin[0],
                output_wire_start_y=output_pin[1],
                component_x_offset=x_offset,
                component_y_offset=y_offset,
                input_link_offset=input_link_offset,
                output_link_offset=output_link_offset,
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


def _patch_cap_elec_terminal_links(
    data: bytes,
    pair: ElectrolyticCapTerminalPair,
) -> bytes:
    out = bytearray(data)
    for offset, terminal in (
        (pair.input_link_offset, pair.left),
        (pair.output_link_offset, pair.right),
    ):
        if offset + 4 > len(out):
            raise ValueError(
                f"CAP-ELEC {pair.component_key} packet ends before its pin-link fields."
            )
        out[offset : offset + 2] = struct.pack("<H", terminal.suffix)
        out[offset + 2] = 0x01
        out[offset + 3] = 0x00
    out[-1] = 0x00
    return bytes(out)


def _patch_source_terminal_links(
    data: bytes,
    pair: SourceTerminalPair,
) -> bytes:
    out = bytearray(data)
    for offset, terminal in (
        (pair.input_link_offset, pair.input),
        (pair.output_link_offset, pair.output),
    ):
        if offset + 4 > len(out):
            raise ValueError(
                f"{pair.component_family} {pair.component_key} packet ends before "
                "its source endpoint-link fields."
            )
        out[offset : offset + 2] = struct.pack("<H", terminal.suffix)
        out[offset + 2] = 0x01
        out[offset + 3] = 0x00
    out[-1] = 0x00
    return bytes(out)


def _wire_coordinates(record: bytes) -> tuple[int, int, int, int]:
    marker = record.find(b"\x7fWIRE")
    if marker < 23:
        raise ValueError("Donor wire record is missing its structural WIRE marker.")
    coordinate_start = marker - 23 + 33
    if coordinate_start + 16 > len(record):
        raise ValueError("Donor wire record ends before its coordinate fields.")
    return struct.unpack("<iiii", record[coordinate_start : coordinate_start + 16])


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


def _load_eight_cap_elec_templates(project: Path) -> ElectrolyticCapDonorTemplates:
    chunk = _extract_object_chunk(read_internal_file(project, "ROOT.DSN"))
    expected_size = 1 + 7 * CAP_ELEC_DONOR_GROUP_SIZE + (
        CAP_ELEC_DONOR_GROUP_SIZE + 1
    )
    if (
        len(chunk) != expected_size
        or chunk[:1] != b"\x00"
        or chunk[-1:] != b"\xff"
        or chunk.count(BIDIR_MARKER) != 16
        or chunk.count(b"$TERINPUT") != 0
        or chunk.count(b"$TEROUTPUT") != 0
        or chunk.count(b"CAP-ELEC") != 16
        or chunk.count(b"\x7fWIRE") != 16
    ):
        raise ValueError(
            "Eight-component CAP-ELEC donor does not match its accepted sequential shape."
        )

    wire_lefts: list[bytes] = []
    wire_rights: list[bytes] = []
    cursor = 1
    for index in range(8):
        right_record = chunk[cursor : cursor + CAP_ELEC_BIDIR_RECORD_SIZE]
        cursor += CAP_ELEC_BIDIR_RECORD_SIZE
        left_record = chunk[cursor : cursor + CAP_ELEC_BIDIR_RECORD_SIZE]
        cursor += CAP_ELEC_BIDIR_RECORD_SIZE
        component = chunk[cursor : cursor + CAP_ELEC_COMPONENT_RECORD_SIZE]
        cursor += CAP_ELEC_COMPONENT_RECORD_SIZE
        left_wire = chunk[cursor : cursor + CAP_ELEC_WIRE_RECORD_SIZE]
        cursor += CAP_ELEC_WIRE_RECORD_SIZE
        right_size = (
            CAP_ELEC_WIRE_RECORD_SIZE
            if index == 7
            else CAP_ELEC_TRIMMED_WIRE_RECORD_SIZE
        )
        right_wire = chunk[cursor : cursor + right_size]
        cursor += right_size

        body_x_offset, body_y_offset = _cap_elec_body_offsets(component)
        body_x = _s32_at(component, body_x_offset)
        body_y = _s32_at(component, body_y_offset)
        left_suffix, right_suffix = _cap_elec_suffixes(index + 1)
        right_symbol = struct.unpack("<ii", right_record[1:9])
        left_symbol = struct.unpack("<ii", left_record[1:9])
        expected_left_pin = body_x - CAP_ELEC_PIN_HALF_SPAN
        expected_right_pin = body_x + CAP_ELEC_PIN_HALF_SPAN
        if (
            len(right_record) != CAP_ELEC_BIDIR_RECORD_SIZE
            or len(left_record) != CAP_ELEC_BIDIR_RECORD_SIZE
            or right_record.count(BIDIR_MARKER) != 1
            or left_record.count(BIDIR_MARKER) != 1
            or right_record[30] != 0
            or left_record[30] != 0
            or _u32_at(right_record, 9) != RIGHT_SIDE_ANGLE
            or _u32_at(left_record, 9) != LEFT_SIDE_ANGLE
            or struct.unpack("<H", right_record[-4:-2])[0] != right_suffix
            or struct.unpack("<H", left_record[-4:-2])[0] != left_suffix
            or right_symbol
            != (
                expected_right_pin + CAP_ELEC_TERMINAL_SYMBOL_TO_PIN,
                body_y,
            )
            or left_symbol
            != (
                expected_left_pin - CAP_ELEC_TERMINAL_SYMBOL_TO_PIN,
                body_y,
            )
            or len(component) != CAP_ELEC_COMPONENT_RECORD_SIZE
            or not component.startswith(b"\x00\xff")
            or component.count(b"CAP-ELEC") != 2
            or component[body_x_offset + 25 : body_x_offset + 27]
            != struct.pack("<H", left_suffix)
            or component[body_x_offset + 29 : body_x_offset + 31]
            != struct.pack("<H", right_suffix)
            or len(left_wire) != CAP_ELEC_WIRE_RECORD_SIZE
            or len(right_wire) != right_size
            or left_wire.count(b"\x7fWIRE") != 1
            or right_wire.count(b"\x7fWIRE") != 1
        ):
            raise ValueError(f"Eight-component CAP-ELEC donor group {index + 1} is malformed.")

        for wire, pin_x in (
            (left_wire, expected_left_pin),
            (right_wire, expected_right_pin),
        ):
            marker = wire.find(b"\x7fWIRE")
            coordinate_start = marker - 23 + 33
            x1, y1, x2, y2 = struct.unpack(
                "<iiii", wire[coordinate_start : coordinate_start + 16]
            )
            if (x1, y1, x2, y2) != (pin_x, body_y, pin_x, body_y):
                raise ValueError(
                    f"Eight-component CAP-ELEC donor group {index + 1} "
                    "does not use zero-length pin attachments."
                )
        wire_lefts.append(left_wire)
        wire_rights.append(right_wire)

    if cursor != len(chunk):
        raise ValueError(
            f"Eight-component CAP-ELEC donor cursor ended at {cursor}, expected {len(chunk)}."
        )
    return ElectrolyticCapDonorTemplates(
        header=chunk[:1],
        wire_lefts=tuple(wire_lefts),
        wire_rights=tuple(wire_rights),
        donor_chunk=chunk,
    )


def _load_vsource_templates(project: Path) -> SourceDonorTemplates:
    chunk = _extract_object_chunk(read_internal_file(project, "ROOT.DSN"))
    output_record = chunk[1:102]
    input_record = chunk[102:203]
    component = chunk[203:546]
    output_wire = chunk[546:596]
    input_wire = chunk[596:646]
    body_x_offset, body_y_offset = _source_body_offsets(component, "VSOURCE")
    body_x = _s32_at(component, body_x_offset)
    body_y = _s32_at(component, body_y_offset)
    output_suffix = struct.unpack("<H", output_record[-4:-2])[0]
    input_suffix = struct.unpack("<H", input_record[-4:-2])[0]
    output_pin = (
        body_x + SOURCE_PIN_X_FROM_BODY,
        body_y + SOURCE_UPPER_PIN_Y_FROM_BODY,
    )
    input_pin = (
        body_x + SOURCE_PIN_X_FROM_BODY,
        body_y + SOURCE_LOWER_PIN_Y_FROM_BODY,
    )
    if (
        len(chunk) != 646
        or chunk[:1] != b"\x00"
        or chunk[-1:] != b"\xff"
        or chunk.count(BIDIR_MARKER) != 2
        or chunk.count(b"VSOURCE") != 2
        or chunk.count(b"\x7fWIRE") != 2
        or len(output_record) != 101
        or len(input_record) != 101
        or output_record.count(BIDIR_MARKER) != 1
        or input_record.count(BIDIR_MARKER) != 1
        or output_record[30] != 0
        or input_record[30] != 0
        or _u32_at(output_record, 9) != RIGHT_SIDE_ANGLE
        or _u32_at(input_record, 9) != LEFT_SIDE_ANGLE
        or struct.unpack("<ii", output_record[1:9])
        != (output_pin[0] + SOURCE_TERMINAL_SYMBOL_TO_PIN, output_pin[1])
        or struct.unpack("<ii", input_record[1:9])
        != (input_pin[0] - SOURCE_TERMINAL_SYMBOL_TO_PIN, input_pin[1])
        or len(component)
        != SOURCE_COMPONENT_BARE_BASE_SIZES["VSOURCE"] + len("V1") + 1
        or not component.startswith(b"\x00\xff")
        or component[body_x_offset + 25 : body_x_offset + 27]
        != struct.pack("<H", output_suffix)
        or component[body_x_offset + 29 : body_x_offset + 31]
        != struct.pack("<H", input_suffix)
        or len(output_wire) != 50
        or len(input_wire) != 50
        or _wire_coordinates(output_wire)
        != (output_pin[0], output_pin[1], output_pin[0], output_pin[1])
        or _wire_coordinates(input_wire)
        != (input_pin[0], input_pin[1], input_pin[0], input_pin[1])
    ):
        raise ValueError("Clean bidirectional VSOURCE donor shape changed.")
    return SourceDonorTemplates(
        family="VSOURCE",
        input_wire=input_wire,
        output_wire=output_wire,
        donor_chunk=chunk,
        donor_path=project,
    )


def _load_csource_templates(project: Path) -> SourceDonorTemplates:
    chunk = _extract_object_chunk(read_internal_file(project, "ROOT.DSN"))
    input_marker = chunk.rfind(b"$TERINPUT")
    if input_marker < 14:
        raise ValueError("Accepted CSOURCE donor is missing its final input terminal.")
    input_start = input_marker - 14
    output_marker = chunk.find(b"$TEROUTPUT", input_marker)
    if output_marker < 14:
        raise ValueError("Accepted CSOURCE donor is missing its final output terminal.")
    output_start = output_marker - 14
    input_record = chunk[input_start:output_start]
    component_start = output_start + 104
    first_wire_marker = chunk.find(b"\x7fWIRE", component_start)
    if first_wire_marker < 23:
        raise ValueError("Accepted CSOURCE donor is missing its source wire records.")
    first_wire_start = first_wire_marker - 23
    output_record = chunk[output_start:component_start]
    component = chunk[component_start:first_wire_start]
    input_wire = chunk[first_wire_start : first_wire_start + 50]
    output_wire = chunk[first_wire_start + 50 : first_wire_start + 100]

    body_x_offset, body_y_offset = _source_body_offsets(component, "CSOURCE")
    body_x = _s32_at(component, body_x_offset)
    body_y = _s32_at(component, body_y_offset)
    input_suffix = struct.unpack("<H", input_record[-4:-2])[0]
    output_suffix = struct.unpack("<H", output_record[-4:-2])[0]
    input_pin = (
        body_x + SOURCE_PIN_X_FROM_BODY,
        body_y + SOURCE_UPPER_PIN_Y_FROM_BODY,
    )
    output_pin = (
        body_x + SOURCE_PIN_X_FROM_BODY,
        body_y + SOURCE_LOWER_PIN_Y_FROM_BODY,
    )
    if (
        input_start + 652 != len(chunk)
        or len(input_record) != 103
        or len(output_record) != 104
        or input_record.count(b"$TERINPUT") != 1
        or output_record.count(b"$TEROUTPUT") != 1
        or len(component)
        != SOURCE_COMPONENT_BARE_BASE_SIZES["CSOURCE"] + len("I1") + 1
        or not component.startswith(b"\x00\xff")
        or component.count(b"CSOURCE") != 2
        or component[body_x_offset + 25 : body_x_offset + 27]
        != struct.pack("<H", input_suffix)
        or component[body_x_offset + 29 : body_x_offset + 31]
        != struct.pack("<H", output_suffix)
        or len(input_wire) != 50
        or len(output_wire) != 50
        or _wire_coordinates(input_wire)
        != (input_pin[0], input_pin[1], input_pin[0], input_pin[1])
        or _wire_coordinates(output_wire)
        != (output_pin[0], output_pin[1], output_pin[0], output_pin[1])
    ):
        raise ValueError("Accepted CSOURCE V15 donor shape changed.")
    return SourceDonorTemplates(
        family="CSOURCE",
        input_wire=input_wire,
        output_wire=output_wire,
        donor_chunk=chunk,
        donor_path=project,
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


def attach_electrolytic_capacitor_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    label_prefix: str = "E",
) -> dict[str, Any]:
    """Attach CAP-ELEC/v3 using the accepted eight-component donor schema."""

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("CAP-ELEC/v3 requires at least one selected electrolytic capacitor.")
    for group in groups:
        data = bytes(getattr(group, "data", b""))
        if BIDIR_MARKER in data or b"\x7fWIRE" in data:
            raise ValueError(
                "CAP-ELEC/v3 requires bare component-placer packets; "
                f"{getattr(group, 'key', '<unknown>')} already contains terminal or wire records."
            )
    pairs = plan_attached_electrolytic_capacitor_terminals(
        groups,
        label_prefix=label_prefix,
    )
    terminal_templates = load_production_templates(FixtureRegistry.load())
    manual_donor = (
        repository_root()
        / "proteus_ic"
        / "donors"
        / "analog_misc_batch1"
        / "8ELEC-CAP.pdsprj"
    )
    donor_templates = _load_eight_cap_elec_templates(manual_donor)

    object_records: list[bytes] = []
    group_reports: list[dict[str, Any]] = []
    for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
        data = bytes(group.data)
        if not data.startswith(b"\xff"):
            raise ValueError(
                f"CAP-ELEC/v3 expected {pair.component_key} to start with its donor FF boundary."
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
        left_record = build_bidir_record(
            terminal_templates,
            label=pair.left.label,
            symbol_x=pair.left.symbol_x,
            symbol_y=pair.left.symbol_y,
            angle_tenths=pair.left.angle_tenths,
            suffix=pair.left.suffix,
            active_link=True,
        )
        component_record = b"\x00" + _patch_cap_elec_terminal_links(data, pair)
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
        if len(right_template) == CAP_ELEC_TRIMMED_WIRE_RECORD_SIZE:
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
            (right_record, left_record, component_record, left_wire, right_wire)
        )
        group_reports.append(
            {
                "component_key": pair.component_key,
                "right_terminal_size": len(right_record),
                "left_terminal_size": len(left_record),
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
            "CAP-ELEC/v3 base project is not bare; choose the main mega donor "
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
            CAP_ELEC_WIRE_RECORD_SIZE
            if index == len(pairs) - 1
            else CAP_ELEC_TRIMMED_WIRE_RECORD_SIZE
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
        "family_handler": "CAP-ELEC/v3",
        "terminal_kind": "$TERBIDIR",
        "wire_record_emission": True,
        "attachment_policy": "cap_elec_eight_donor_sequential_zero_length_pin_records",
        "object_order": "repeated_right_bidir_left_bidir_cap_elec_left_wire_right_wire",
        "label_policy": "two_character_prefix_plus_base36_terminal_index",
        "suffix_policy": "eight_elec_cap_0x02a8_progression",
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
        "manual_cap_elec_donor": str(manual_donor),
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
                item["left_wire_size"] == CAP_ELEC_WIRE_RECORD_SIZE
                for item in group_reports
            )
            and all(pair.left_wire_start_x == pair.left_pin_x for pair in pairs)
            and all(pair.right_wire_start_x == pair.right_pin_x for pair in pairs)
            and suffix_counts_valid
            and final_chunk.endswith(b"\xff")
        ),
    }


def attach_source_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    label_prefix: str | None = None,
    source_index_start: int = 1,
) -> dict[str, Any]:
    """Attach VSOURCE/CSOURCE endpoints using the user-accepted V3 source rules."""

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("Source/v4 attachment requires at least one selected source packet.")
    families = {str(getattr(group, "family", "")) for group in groups}
    if (
        len(families) != 1
        or next(iter(families), "") not in SOURCE_COMPONENT_BARE_BASE_SIZES
    ):
        raise ValueError(
            "Source/v4 attachment requires one VSOURCE or CSOURCE family; "
            f"received {sorted(families)}."
        )
    family = next(iter(families))
    for group in groups:
        data = bytes(getattr(group, "data", b""))
        if BIDIR_MARKER in data or b"\x7fWIRE" in data:
            raise ValueError(
                f"{family}/v4 requires bare component-placer packets; "
                f"{getattr(group, 'key', '<unknown>')} already contains terminal or wire records."
            )
    pairs = plan_attached_source_terminals(
        groups,
        label_prefix=label_prefix,
        source_index_start=source_index_start,
    )

    registry = FixtureRegistry.load()
    terminal_templates = load_production_templates(registry)
    if family == "VSOURCE":
        donor_templates = _load_vsource_templates(
            registry.get("bidirectional_dcv_source_donor").path
        )
        terminal_order = ("output", "input")
        wire_order = ("output", "input")
    else:
        donor_templates = _load_csource_templates(
            registry.get("source_dc_mixed_v15_donor").path
        )
        terminal_order = ("input", "output")
        wire_order = ("input", "output")

    object_records: list[bytes] = []
    group_reports: list[dict[str, Any]] = []
    for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
        data = bytes(group.data)
        if not data.startswith(b"\xff"):
            raise ValueError(
                f"{family}/v4 expected {pair.component_key} to start with its donor FF boundary."
            )
        terminal_records = {
            "input": build_bidir_record(
                terminal_templates,
                label=pair.input.label,
                symbol_x=pair.input.symbol_x,
                symbol_y=pair.input.symbol_y,
                angle_tenths=pair.input.angle_tenths,
                suffix=pair.input.suffix,
                active_link=True,
            ),
            "output": build_bidir_record(
                terminal_templates,
                label=pair.output.label,
                symbol_x=pair.output.symbol_x,
                symbol_y=pair.output.symbol_y,
                angle_tenths=pair.output.angle_tenths,
                suffix=pair.output.suffix,
                active_link=True,
            ),
        }
        component_record = b"\x00" + _patch_source_terminal_links(data, pair)
        wire_templates = {
            "input": donor_templates.input_wire,
            "output": donor_templates.output_wire,
        }
        pins = {
            "input": (pair.input_pin_x, pair.input_pin_y),
            "output": (pair.output_pin_x, pair.output_pin_y),
        }
        first_wire_role, second_wire_role = wire_order
        first_pin = pins[first_wire_role]
        first_wire = _patch_wire(
            wire_templates[first_wire_role],
            first_pin[0],
            first_pin[1],
            first_pin[0],
            first_pin[1],
        )
        second_pin = pins[second_wire_role]
        second_wire = _patch_wire(
            wire_templates[second_wire_role],
            second_pin[0],
            second_pin[1],
            second_pin[0],
            second_pin[1],
        )
        is_final = index == len(groups) - 1
        if not is_final:
            second_wire = second_wire[:-1]
        object_records.extend(
            (
                terminal_records[terminal_order[0]],
                terminal_records[terminal_order[1]],
                component_record,
                first_wire,
                second_wire,
            )
        )
        group_reports.append(
            {
                "component_key": pair.component_key,
                "terminal_sizes": {
                    role: len(terminal_records[role]) for role in terminal_order
                },
                "bare_component_size": len(data),
                "component_record_size": len(component_record),
                "wire_sizes": {
                    first_wire_role: len(first_wire),
                    second_wire_role: len(second_wire),
                },
                "second_wire_final": is_final,
            }
        )

    source = Path(project)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError(
            f"{family}/v4 base project is not bare; choose a component-placer source donor "
            "before applying terminal attachment."
        )
    new_chunk = original_chunk[:1] + b"".join(object_records)
    new_chunk = new_chunk[:-1] + b"\xff"
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, output, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    expected_terminals = len(pairs) * 2
    expected_wires = len(pairs) * 2
    expected_second_wire_sizes = [
        50 if index == len(pairs) - 1 else 49
        for index in range(len(pairs))
    ]
    suffix_links_valid = all(
        final_chunk.count(struct.pack("<H", terminal.suffix) + b"\x01\x00") == 2
        for pair in pairs
        for terminal in (pair.input, pair.output)
    )
    object_order = (
        f"repeated_{terminal_order[0]}_bidir_{terminal_order[1]}_bidir_"
        f"{family.lower()}_{wire_order[0]}_wire_{wire_order[1]}_wire"
    )
    return {
        "stage": "terminal_placer",
        "family_handler": f"{family}/v4",
        "terminal_kind": "$TERBIDIR",
        "wire_record_emission": True,
        "attachment_policy": "accepted_v3_source_role_links_and_zero_length_pin_records",
        "object_order": object_order,
        "terminal_order": list(terminal_order),
        "wire_order": list(wire_order),
        "label_policy": "two_character_prefix_plus_base36_terminal_index",
        "suffix_policy": "accepted_source_0x0080_step_output_plus_0x0032_input",
        "source_index_start": source_index_start,
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
        "manual_source_donor": str(donor_templates.donor_path),
        "valid": (
            final_chunk == new_chunk
            and final_chunk.count(BIDIR_MARKER) == expected_terminals
            and final_chunk.count(b"\x7fWIRE") == expected_wires
            and all(
                item["component_record_size"] == item["bare_component_size"] + 1
                for item in group_reports
            )
            and [
                item["wire_sizes"][wire_order[1]]
                for item in group_reports
            ]
            == expected_second_wire_sizes
            and all(
                item["wire_sizes"][wire_order[0]] == 50
                for item in group_reports
            )
            and all(
                pair.input_wire_start_x == pair.input_pin_x
                and pair.input_wire_start_y == pair.input_pin_y
                and pair.output_wire_start_x == pair.output_pin_x
                and pair.output_wire_start_y == pair.output_pin_y
                for pair in pairs
            )
            and suffix_links_valid
            and final_chunk.endswith(b"\xff")
        ),
    }


def _attach_single_family_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    label_prefix: str | None = None,
    suffix_start: int | None = None,
    source_index_start: int = 1,
) -> dict[str, Any]:
    """Dispatch one already-filtered family to its proven attachment handler."""

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
    if family == "CAP-ELEC":
        if suffix_start is not None:
            raise ValueError(
                "CAP-ELEC/v3 uses donor-native suffix progression; suffix_start is unsupported."
            )
        return attach_electrolytic_capacitor_bidir_terminals_to_project(
            project,
            output,
            groups,
            label_prefix=label_prefix or "E",
        )
    if family in SOURCE_COMPONENT_BARE_BASE_SIZES:
        if suffix_start is not None:
            raise ValueError(
                f"{family}/v4 uses the accepted source suffix progression; "
                "suffix_start is unsupported."
            )
        return attach_source_bidir_terminals_to_project(
            project,
            output,
            groups,
            label_prefix=label_prefix,
            source_index_start=source_index_start,
        )
    raise ValueError(
        "Shared terminal attachment has no accepted handler for "
        f"{family}. Add the family-specific logic to component_terminal_placer.py."
    )


def _terminal_suffixes(report: dict[str, Any]) -> tuple[int, ...]:
    suffixes: list[int] = []
    for pair in report.get("terminal_pairs", []):
        for role in ("left", "right", "input", "output"):
            terminal = pair.get(role)
            if isinstance(terminal, dict) and isinstance(terminal.get("suffix"), str):
                suffixes.append(int(terminal["suffix"], 16))
    return tuple(suffixes)


def _overlay_terminal_record(
    templates: Any,
    terminal: TerminalSpec,
    *,
    active_link: bool,
) -> bytes:
    return build_bidir_record(
        templates,
        label=terminal.label,
        symbol_x=terminal.symbol_x,
        symbol_y=terminal.symbol_y,
        angle_tenths=terminal.angle_tenths,
        suffix=terminal.suffix,
        active_link=active_link,
    )


def _mixed_overlay_family_parts(
    family: str,
    groups: tuple[Any, ...],
    *,
    terminal_templates: Any,
    source_index_start: int,
    active_links: bool,
) -> tuple[
    tuple[Any, ...],
    list[bytes],
    list[tuple[bytes, bytes]],
    dict[int, bytes],
]:
    terminal_records: list[bytes] = []
    wire_pairs: list[tuple[bytes, bytes]] = []
    patched_by_id: dict[int, bytes] = {}

    if family == "RESISTOR":
        pairs = plan_attached_resistor_terminals(groups)
        fixture = FixtureRegistry.load().get("r21_v9_resistor_terminal_donor")
        donor_templates = _load_resistor_templates(
            read_internal_file(fixture.path, "ROOT.DSN"),
            fixture.path,
        )
        terminals = [
            *(pair.left for pair in pairs),
            *(pair.right for pair in pairs),
        ]
        for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
            patched_by_id[id(group)] = _patch_resistor_terminal_links(
                bytes(group.data),
                pair,
            )
            _component, left_template, right_template = donor_templates.groups[
                index % len(donor_templates.groups)
            ]
            wire_pairs.append(
                (
                    _patch_wire(
                        left_template,
                        pair.left_wire_start_x,
                        pair.left_wire_start_y,
                        pair.left_pin_x,
                        pair.left_pin_y,
                    ),
                    _patch_wire(
                        right_template,
                        pair.right_wire_start_x,
                        pair.right_wire_start_y,
                        pair.right_pin_x,
                        pair.right_pin_y,
                    ),
                )
            )
    elif family == "CAP":
        pairs = plan_attached_capacitor_terminals(groups)
        fixture = FixtureRegistry.load().get("cap2_with_terminals_manual")
        donor_templates = _load_manual_cap_templates(fixture.path)
        terminals = [
            *(pair.right for pair in pairs),
            *(pair.left for pair in pairs),
        ]
        for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
            patched_by_id[id(group)] = _patch_capacitor_terminal_links(
                bytes(group.data),
                pair,
            )
            template_index = index % len(donor_templates.wire_lefts)
            wire_pairs.append(
                (
                    _patch_wire(
                        donor_templates.wire_rights[template_index],
                        pair.left_pin_x,
                        pair.left_pin_y,
                        pair.left_pin_x,
                        pair.left_pin_y,
                    ),
                    _patch_wire(
                        donor_templates.wire_lefts[template_index],
                        pair.right_pin_x,
                        pair.right_pin_y,
                        pair.right_pin_x,
                        pair.right_pin_y,
                    ),
                )
            )
    elif family == "REALIND":
        pairs = plan_attached_inductor_terminals(groups)
        fixture = FixtureRegistry.load().get("inductor_05_six_terminal")
        donor_templates = _load_six_inductor_templates(fixture.path)
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.left, pair.right)
        ]
        for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
            patched_by_id[id(group)] = _patch_inductor_terminal_links(
                bytes(group.data),
                pair,
            )
            template_index = index % len(donor_templates.wire_lefts)
            right_template = donor_templates.wire_rights[template_index]
            if len(right_template) == INDUCTOR_TRIMMED_WIRE_RECORD_SIZE:
                right_template += b"\x00"
            wire_pairs.append(
                (
                    _patch_wire(
                        donor_templates.wire_lefts[template_index],
                        pair.left_pin_x,
                        pair.left_pin_y,
                        pair.left_pin_x,
                        pair.left_pin_y,
                    ),
                    _patch_wire(
                        right_template,
                        pair.right_pin_x,
                        pair.right_pin_y,
                        pair.right_pin_x,
                        pair.right_pin_y,
                    ),
                )
            )
    elif family == "CAP-ELEC":
        pairs = plan_attached_electrolytic_capacitor_terminals(groups)
        donor_path = (
            repository_root()
            / "proteus_ic"
            / "donors"
            / "analog_misc_batch1"
            / "8ELEC-CAP.pdsprj"
        )
        donor_templates = _load_eight_cap_elec_templates(donor_path)
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.right, pair.left)
        ]
        for index, (group, pair) in enumerate(zip(groups, pairs, strict=True)):
            patched_by_id[id(group)] = _patch_cap_elec_terminal_links(
                bytes(group.data),
                pair,
            )
            template_index = index % len(donor_templates.wire_lefts)
            right_template = donor_templates.wire_rights[template_index]
            if len(right_template) == CAP_ELEC_TRIMMED_WIRE_RECORD_SIZE:
                right_template += b"\x00"
            wire_pairs.append(
                (
                    _patch_wire(
                        donor_templates.wire_lefts[template_index],
                        pair.left_pin_x,
                        pair.left_pin_y,
                        pair.left_pin_x,
                        pair.left_pin_y,
                    ),
                    _patch_wire(
                        right_template,
                        pair.right_pin_x,
                        pair.right_pin_y,
                        pair.right_pin_x,
                        pair.right_pin_y,
                    ),
                )
            )
    elif family in SOURCE_COMPONENT_BARE_BASE_SIZES:
        pairs = plan_attached_source_terminals(
            groups,
            source_index_start=source_index_start,
        )
        registry = FixtureRegistry.load()
        if family == "VSOURCE":
            donor_templates = _load_vsource_templates(
                registry.get("bidirectional_dcv_source_donor").path
            )
            terminal_order = ("output", "input")
            wire_order = ("output", "input")
        else:
            donor_templates = _load_csource_templates(
                registry.get("source_dc_mixed_v15_donor").path
            )
            terminal_order = ("input", "output")
            wire_order = ("input", "output")
        terminals = [
            getattr(pair, role)
            for pair in pairs
            for role in terminal_order
        ]
        for group, pair in zip(groups, pairs, strict=True):
            patched_by_id[id(group)] = _patch_source_terminal_links(
                bytes(group.data),
                pair,
            )
            pins = {
                "input": (pair.input_pin_x, pair.input_pin_y),
                "output": (pair.output_pin_x, pair.output_pin_y),
            }
            templates = {
                "input": donor_templates.input_wire,
                "output": donor_templates.output_wire,
            }
            first_role, second_role = wire_order
            first_pin = pins[first_role]
            second_pin = pins[second_role]
            wire_pairs.append(
                (
                    _patch_wire(
                        templates[first_role],
                        first_pin[0],
                        first_pin[1],
                        first_pin[0],
                        first_pin[1],
                    ),
                    _patch_wire(
                        templates[second_role],
                        second_pin[0],
                        second_pin[1],
                        second_pin[0],
                        second_pin[1],
                    ),
                )
            )
    else:
        raise ValueError(f"No accepted mixed-overlay handler exists for {family}.")

    terminal_records.extend(
        _overlay_terminal_record(
            terminal_templates,
            terminal,
            active_link=active_links,
        )
        for terminal in terminals
    )
    return tuple(pairs), terminal_records, wire_pairs, patched_by_id


def attach_mixed_overlay_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    terminal_families: Iterable[str] | None = None,
    patch_component_links: bool = True,
    active_terminal_links: bool = True,
    include_wires: bool = True,
) -> dict[str, Any]:
    """Temporary mixed route based on the user-confirmed opening V2 order.

    Complete beautified component packets remain in their component-placer
    order. Known component link fields are patched in place, then all terminal
    records and optional donor-derived wire records are appended as an overlay.
    This is intentionally temporary until a Proteus-created mixed donor proves
    the final production ordering.
    """

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("Mixed terminal overlay requires selected component groups.")
    accepted = set(ACCEPTED_TERMINAL_FAMILY_ORDER)
    available = tuple(
        dict.fromkeys(
            str(getattr(group, "family", ""))
            for group in groups
            if str(getattr(group, "family", "")) in accepted
        )
    )
    requested = available if terminal_families is None else tuple(
        dict.fromkeys(str(item) for item in terminal_families)
    )
    unknown = sorted(set(requested) - accepted)
    missing = sorted(set(requested) - set(available))
    if unknown:
        raise ValueError(f"No accepted mixed-overlay handler exists for {unknown}.")
    if missing:
        raise ValueError(f"Requested mixed-overlay families are absent: {missing}.")
    if not requested:
        raise ValueError(
            "Mixed terminal overlay requires at least one accepted terminal family."
        )
    if include_wires and not (patch_component_links and active_terminal_links):
        raise ValueError(
            "Mixed overlay wires require patched component links and active terminal links."
        )
    if patch_component_links != active_terminal_links:
        raise ValueError(
            "Component link patches and active terminal links must be enabled together."
        )

    source = Path(project)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError("Mixed overlay requires a bare component-placer project.")

    terminal_templates = load_production_templates(FixtureRegistry.load())
    terminal_records: list[bytes] = []
    wire_pairs: list[tuple[bytes, bytes]] = []
    patched_by_id: dict[int, bytes] = {}
    family_reports: list[dict[str, Any]] = []
    source_index_start = 1
    for family in requested:
        family_groups = tuple(
            group
            for group in groups
            if str(getattr(group, "family", "")) == family
        )
        pairs, family_terminals, family_wires, family_patches = (
            _mixed_overlay_family_parts(
                family,
                family_groups,
                terminal_templates=terminal_templates,
                source_index_start=source_index_start,
                active_links=active_terminal_links,
            )
        )
        if family in SOURCE_COMPONENT_BARE_BASE_SIZES:
            source_index_start += len(family_groups)
        terminal_records.extend(family_terminals)
        wire_pairs.extend(family_wires)
        patched_by_id.update(family_patches)
        family_reports.append(
            {
                "family_handler": f"{family}/mixed-overlay-temp",
                "component_count": len(family_groups),
                "terminal_count": len(pairs) * 2,
                "wire_count": len(pairs) * 2 if include_wires else 0,
                "terminal_pairs": [pair.as_dict() for pair in pairs],
            }
        )

    patched_chunk = original_chunk
    if patch_component_links:
        for group in groups:
            patched = patched_by_id.get(id(group))
            if patched is None:
                continue
            original_core = bytes(getattr(group, "data", b""))[:-1]
            patched_core = patched[:-1]
            if len(original_core) != len(patched_core):
                raise ValueError(
                    f"Mixed overlay changed packet size for {getattr(group, 'key', '')}."
                )
            if patched_chunk.count(original_core) != 1:
                raise ValueError(
                    "Mixed overlay cannot uniquely locate component packet "
                    f"{getattr(group, 'key', '')}."
                )
            patched_chunk = patched_chunk.replace(
                original_core,
                patched_core,
                1,
            )

    wire_records: list[bytes] = []
    if include_wires:
        for index, (first_wire, second_wire) in enumerate(wire_pairs):
            if len(first_wire) != 50 or len(second_wire) != 50:
                raise ValueError("Mixed overlay requires full 50-byte wire templates.")
            wire_records.append(first_wire)
            wire_records.append(
                second_wire
                if index == len(wire_pairs) - 1
                else second_wire[:-1]
            )

    new_chunk = (
        patched_chunk[:-1]
        + b"".join(terminal_records)
        + b"".join(wire_records)
    )
    if not new_chunk:
        raise ValueError("Mixed terminal overlay produced an empty object chunk.")
    new_chunk = new_chunk[:-1] + b"\xff"
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, destination, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(destination, "ROOT.DSN"))

    suffixes = tuple(
        suffix
        for report in family_reports
        for suffix in _terminal_suffixes(report)
    )
    suffixes_unique = len(suffixes) == len(set(suffixes))
    suffix_links_valid = (
        not patch_component_links
        or (
            suffixes_unique
            and all(
                final_chunk.count(struct.pack("<H", suffix) + b"\x01\x00") == 2
                for suffix in suffixes
            )
        )
    )
    expected_terminals = len(terminal_records)
    expected_wires = len(wire_pairs) * 2 if include_wires else 0
    preserved_rows = []
    for group in groups:
        family = str(getattr(group, "family", ""))
        if family in requested:
            continue
        core = bytes(getattr(group, "data", b""))[:-1]
        preserved_rows.append(
            {
                "component_key": str(getattr(group, "key", "")),
                "component_family": family,
                "packet_size": len(bytes(getattr(group, "data", b""))),
                "byte_preserved": (
                    original_chunk.count(core) == final_chunk.count(core) == 1
                ),
            }
        )
    return {
        "stage": "terminal_placer",
        "family_handler": "MIXED/append-overlay-v3-temp",
        "status": "temporary_pending_proteus",
        "attachment_policy": "preserve_component_order_then_append_terminal_wire_overlay",
        "object_order": "component_placer_stream_then_all_terminals_then_all_wires",
        "historical_basis": "user_confirmed_all_family_v2_opened_with_unattached_appended_terminals",
        "eligible_families": list(requested),
        "available_accepted_families": [
            family
            for family in ACCEPTED_TERMINAL_FAMILY_ORDER
            if family in available
        ],
        "skipped_families": sorted(
            {
                str(getattr(group, "family", ""))
                for group in groups
            }
            - set(requested)
        ),
        "patch_component_links": patch_component_links,
        "active_terminal_links": active_terminal_links,
        "wire_record_emission": include_wires,
        "component_stream_prefix_preserved": final_chunk.startswith(
            patched_chunk[:-1]
        ),
        "component_record_order_mutation": False,
        "family_reports": family_reports,
        "terminal_suffixes": [f"{suffix:04x}" for suffix in suffixes],
        "terminal_suffixes_unique": suffixes_unique,
        "terminal_suffix_links_valid": suffix_links_valid,
        "terminal_count_added": expected_terminals,
        "wire_count_added": expected_wires,
        "terminalized_component_count": len(groups) - len(preserved_rows),
        "preserved_component_count": len(preserved_rows),
        "preserved_groups": preserved_rows,
        "bidir_count_before": original_chunk.count(BIDIR_MARKER),
        "bidir_count_after": final_chunk.count(BIDIR_MARKER),
        "wire_count_before": original_chunk.count(b"\x7fWIRE"),
        "wire_count_after": final_chunk.count(b"\x7fWIRE"),
        "object_chunk_size_before": len(original_chunk),
        "object_chunk_size_after": len(final_chunk),
        "valid": (
            final_chunk == new_chunk
            and final_chunk.count(BIDIR_MARKER) == expected_terminals
            and final_chunk.count(b"\x7fWIRE") == expected_wires
            and suffix_links_valid
            and final_chunk.startswith(patched_chunk[:-1])
            and all(row["byte_preserved"] for row in preserved_rows)
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
    terminal_families: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Attach accepted families and preserve every unsupported mixed packet.

    Single-family calls retain the exact accepted family writer. Mixed calls
    keep the component-placer stream in place and append terminals and wires
    through the temporary overlay route. This follows the older all-family
    record order that opened in Proteus while applying the accepted per-family
    attachment geometry and link fields.
    """

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("Shared terminal attachment requires selected component groups.")
    families = {str(getattr(group, "family", "")) for group in groups}
    accepted = set(ACCEPTED_TERMINAL_FAMILY_ORDER)
    available_eligible_families = tuple(
        family for family in ACCEPTED_TERMINAL_FAMILY_ORDER if family in families
    )
    if terminal_families is None:
        eligible_families = available_eligible_families
    else:
        requested_terminal_families = tuple(
            dict.fromkeys(str(item) for item in terminal_families)
        )
        unknown = sorted(set(requested_terminal_families) - accepted)
        missing = sorted(set(requested_terminal_families) - families)
        if unknown:
            raise ValueError(
                "No accepted terminal handler exists for requested mixed families: "
                f"{unknown}."
            )
        if missing:
            raise ValueError(
                "Requested terminal families are absent from selected groups: "
                f"{missing}."
            )
        eligible_families = tuple(
            family
            for family in ACCEPTED_TERMINAL_FAMILY_ORDER
            if family in requested_terminal_families
        )
    preserved_groups = tuple(
        sorted(
            (
                group
                for group in groups
                if str(getattr(group, "family", "")) not in eligible_families
            ),
            key=lambda group: int(getattr(group, "start", 0)),
        )
    )

    if len(families) == 1 and eligible_families:
        return _attach_single_family_bidir_terminals_to_project(
            project,
            output,
            groups,
            label_prefix=label_prefix,
            suffix_start=suffix_start,
        )
    if label_prefix is not None or suffix_start is not None:
        raise ValueError(
            "label_prefix and suffix_start are single-family overrides; "
            "mixed selective attachment uses family-safe defaults."
        )

    source = Path(project)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError(
            "Mixed selective terminal attachment requires a bare component-placer project."
        )

    if not eligible_families:
        shutil.copyfile(source, destination)
        final_chunk = _extract_object_chunk(read_internal_file(destination, "ROOT.DSN"))
        return {
            "stage": "terminal_placer",
            "family_handler": "NONE/selective-copy-v1",
            "attachment_policy": "accepted_family_allowlist_preserve_all_others",
            "eligible_families": [],
            "skipped_families": sorted(families),
            "terminalized_component_count": 0,
            "preserved_component_count": len(preserved_groups),
            "preserved_groups": [
                {
                    "component_key": str(getattr(group, "key", "")),
                    "component_family": str(getattr(group, "family", "")),
                    "packet_size": len(bytes(getattr(group, "data", b""))),
                    "byte_preserved": True,
                }
                for group in preserved_groups
            ],
            "terminal_count_added": 0,
            "wire_count_added": 0,
            "bidir_count_before": original_chunk.count(BIDIR_MARKER),
            "bidir_count_after": final_chunk.count(BIDIR_MARKER),
            "wire_count_before": original_chunk.count(b"\x7fWIRE"),
            "wire_count_after": final_chunk.count(b"\x7fWIRE"),
            "object_chunk_size_before": len(original_chunk),
            "object_chunk_size_after": len(final_chunk),
            "valid": final_chunk == original_chunk,
        }

    return attach_mixed_overlay_bidir_terminals_to_project(
        source,
        destination,
        groups,
        terminal_families=(
            None if terminal_families is None else eligible_families
        ),
        patch_component_links=True,
        active_terminal_links=True,
        include_wires=True,
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
