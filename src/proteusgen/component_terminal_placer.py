"""Bidirectional terminal placement for component-placer output.

This stage appends complete donor-derived `$TERBIDIR` records to an already
generated component-placement project. It does not emit Proteus wire records.
The first proven mode places terminals at parsed packet-side anchors so later
stages can decide names and real wiring policy without re-learning bider bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .bidirectional import BIDIR_MARKER, build_bidir_record, load_production_templates
from .component_beautifier import coordinate_bbox, layout_coordinate_pairs
from .pdsprj import read_internal_file, write_project_from_parts
from .resistor_v9 import _extract_object_chunk, build_dsn
from .templates import FixtureRegistry


TERMINAL_MARGIN = 0
MAX_TERMINALS_PER_SIDE = 8
LEFT_SIDE_ANGLE = 1800
RIGHT_SIDE_ANGLE = 0
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


def _s32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


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
    """Plan left/right bider terminals for selected component packets.

    This is a side-anchor stage, not final Proteus wiring. It appends real
    donor-derived bidirectional terminals for every user component family so
    the next pin/wire stage has one place that owns terminal naming and side
    orientation.
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
    """Append planned bider terminals to `project` and write `output`."""

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
        "stage": "terminal_placer",
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
