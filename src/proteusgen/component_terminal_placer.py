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
TERMINAL_SYMBOL_TO_PIN = 508_000
TERMINAL_CONTACT_TO_PIN = 254_000
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


def _s32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _u32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=False)


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
