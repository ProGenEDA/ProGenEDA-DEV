"""Bidirectional terminal placement for component-placer output.

This stage adds schema-encoded `$TERBIDIR` and short-WIRE records to an already
generated, beautified component-placement project.

Terminal attachment is family-profile specific. The rejected V2 bounding-box
helper is retained for diagnostic compatibility, but the shared production
route consumes placed component packets, patches their pin-link fields, emits
generic terminal/WIRE records, and allocates links from final ROOT.DSN
addresses. It does not select a circuit donor at runtime.

The rejected V6 mixed route is retained only for reproducing its terminal-only
Ctrl+S control. Production mixed attachment uses the same active terminal
links, component pin-link patches, component-adjacent short-wire records, and
record boundaries as the accepted single-family writers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import shutil
import struct
from typing import Any, Iterable

from .bidirectional import (
    BIDIR_MARKER,
    BidirTemplates,
    build_bidir_record,
    load_production_templates,
)
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
PROTEUS_TERMINAL_GRID = 254_000
LEFT_SIDE_ANGLE = 1800
RIGHT_SIDE_ANGLE = 0
RESISTOR_PIN_SPAN = 1_270_000
CAP_PIN_HALF_SPAN = 508_000
CAP_TERMINAL_SYMBOL_TO_PIN = 254_000
CAP_ELEC_PIN_HALF_SPAN = 508_000
CAP_ELEC_TERMINAL_SYMBOL_TO_PIN = 254_000
INDUCTOR_PIN_HALF_SPAN = 762_000
INDUCTOR_TERMINAL_SYMBOL_TO_PIN = 254_000
GENERIC_TWO_PIN_HALF_SPAN = 508_000
GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN = 254_000
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
    "VSINE": 341,
    "VPULSE": 344,
}
SOURCE_TERMINAL_LABEL_PREFIXES = {
    "VSOURCE": "V",
    "CSOURCE": "I",
    "VSINE": "S",
    "VPULSE": "P",
}
SOURCE_OUTPUT_UPPER_PIN_FAMILIES = {"VSOURCE", "VSINE", "VPULSE"}
GENERIC_TWO_PIN_PROFILES = {
    "DIODE": {
        "label_prefix": "D",
        "suffix_base": 0x5200,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "1N4007": {
        "label_prefix": "A",
        "suffix_base": 0x5400,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "1N4148": {
        "label_prefix": "B",
        "suffix_base": 0x5600,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "1N4733A": {
        "label_prefix": "J",
        "suffix_base": 0x5800,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "1N6000B": {
        "label_prefix": "K",
        "suffix_base": 0x5A00,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "40EPS08": {
        "label_prefix": "M",
        "suffix_base": 0x5C00,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
        "terminal_contact_outward_grid_steps": 1,
    },
    "BZX55C5V1": {
        "label_prefix": "N",
        "suffix_base": 0x5E00,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "BZX79C5V1": {
        "label_prefix": "O",
        "suffix_base": 0x6000,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "BZY88C": {
        "label_prefix": "Q",
        "suffix_base": 0x6200,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
    },
    "LED-RED": {
        "label_prefix": "G",
        "suffix_base": 0x6400,
        "left_pin_hint": "anode/left_pin",
        "right_pin_hint": "cathode/right_pin",
        "terminal_contact_outward_grid_steps": 1,
    },
    "FUSE": {
        "label_prefix": "F",
        "suffix_base": 0x6600,
        "left_pin_hint": "pin:1",
        "right_pin_hint": "pin:2",
        "terminal_contact_outward_grid_steps": 1,
    },
}
# Dispatcher allow-list for the shared native terminal route.  The R/C/L/source
# families are user-accepted checkpoints; the generic diode/fuse/LED/signal
# source profiles added for V11 remain Proteus-pending until the generated pack
# is opened and reported by the user.
ACCEPTED_TERMINAL_FAMILY_ORDER = (
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
    "CAP",
    "CAP-ELEC",
    "REALIND",
    "RESISTOR",
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
)
NATIVE_WIRE_PREFIX = bytes.fromhex(
    "1d00000000c09e00000040000001ffffff00ffffff00027f"
    "574952450000000200"
)
NATIVE_BIDIR_TEMPLATES = BidirTemplates(
    zero=bytes.fromhex(
        "10d01cbeffc0800f0000000000092454455242494449520c0000000000ff"
        "05626964657218edc3ffc0800f000000000008003400000030e00300c019"
        "0300000000000120ff0144656661756c7420466f6e74005445524d494e41"
        "4c204c4142454c000000000000000000"
    ),
    one_eighty=bytes.fromhex(
        "1080fba2ffc0800f0008070000092454455242494449520c0000000000ff"
        "086269646572313830382b9dffc0800f000000000009003400000030e003"
        "00c0190300000000000120ff0144656661756c7420466f6e74005445524d"
        "494e414c204c4142454c000000000000000000"
    ),
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


def _group_family(group: Any) -> str:
    return str(getattr(group, "family", ""))


def _group_key(group: Any) -> str:
    return str(getattr(group, "key", ""))


def _is_terminal_infrastructure_group(group: Any) -> bool:
    """Return true for placement infrastructure that must never get terminals."""

    return (
        _group_family(group) in INFRASTRUCTURE_FAMILIES
        or _group_key(group) in INFRASTRUCTURE_KEYS
    )


def _terminal_eligible_family(group: Any, accepted: set[str]) -> str | None:
    family = _group_family(group)
    if family in accepted and not _is_terminal_infrastructure_group(group):
        return family
    return None


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


def snap_to_proteus_terminal_grid(
    value: int,
    *,
    grid: int = PROTEUS_TERMINAL_GRID,
) -> int:
    """Snap one internal-unit coordinate to the nearest Proteus grid line.

    Half-grid ties are rounded away from zero so the result is deterministic
    for positive and negative schematic coordinates.
    """

    if grid <= 0:
        raise ValueError("Proteus terminal grid must be positive.")
    magnitude = abs(value)
    snapped = ((magnitude + grid // 2) // grid) * grid
    return snapped if value >= 0 else -snapped


def _terminal_at_grid_contact(
    terminal: TerminalSpec,
    *,
    pin_x: int,
    pin_y: int,
    outward_grid_steps: int = 0,
) -> tuple[TerminalSpec, int, int]:
    if outward_grid_steps < 0:
        raise ValueError("Terminal outward grid steps must be non-negative.")
    contact_x = snap_to_proteus_terminal_grid(pin_x)
    contact_y = snap_to_proteus_terminal_grid(pin_y)
    if terminal.angle_tenths == LEFT_SIDE_ANGLE:
        contact_x -= outward_grid_steps * PROTEUS_TERMINAL_GRID
        symbol_x = contact_x - TERMINAL_CONTACT_TO_PIN
    elif terminal.angle_tenths == RIGHT_SIDE_ANGLE:
        contact_x += outward_grid_steps * PROTEUS_TERMINAL_GRID
        symbol_x = contact_x + TERMINAL_CONTACT_TO_PIN
    else:
        raise ValueError(
            f"Grid terminal placement does not support angle "
            f"{terminal.angle_tenths}."
        )
    return (
        replace(
            terminal,
            symbol_x=symbol_x,
            symbol_y=contact_y,
            attachment_policy=(
                "grid_snapped_terminal_contact_with_short_wire_to_exact_pin"
                if outward_grid_steps == 0
                else "outward_grid_snapped_terminal_contact_with_short_wire_to_exact_pin"
            ),
        ),
        contact_x,
        contact_y,
    )


def _snap_terminal_pair_to_grid(
    pair: ResistorTerminalPair | CapacitorTerminalPair | SourceTerminalPair,
) -> ResistorTerminalPair | CapacitorTerminalPair | SourceTerminalPair:
    profile = GENERIC_TWO_PIN_PROFILES.get(pair.component_family, {})
    outward_grid_steps = int(profile.get("terminal_contact_outward_grid_steps", 0))
    if isinstance(pair, SourceTerminalPair):
        input_terminal, input_x, input_y = _terminal_at_grid_contact(
            pair.input,
            pin_x=pair.input_pin_x,
            pin_y=pair.input_pin_y,
        )
        output_terminal, output_x, output_y = _terminal_at_grid_contact(
            pair.output,
            pin_x=pair.output_pin_x,
            pin_y=pair.output_pin_y,
        )
        return replace(
            pair,
            input=input_terminal,
            output=output_terminal,
            input_wire_start_x=input_x,
            input_wire_start_y=input_y,
            output_wire_start_x=output_x,
            output_wire_start_y=output_y,
        )

    left_terminal, left_x, left_y = _terminal_at_grid_contact(
        pair.left,
        pin_x=pair.left_pin_x,
        pin_y=pair.left_pin_y,
        outward_grid_steps=outward_grid_steps,
    )
    right_terminal, right_x, right_y = _terminal_at_grid_contact(
        pair.right,
        pin_x=pair.right_pin_x,
        pin_y=pair.right_pin_y,
        outward_grid_steps=outward_grid_steps,
    )
    return replace(
        pair,
        left=left_terminal,
        right=right_terminal,
        left_wire_start_x=left_x,
        left_wire_start_y=left_y,
        right_wire_start_x=right_x,
        right_wire_start_y=right_y,
    )


def _catalogue_terminal_label(component_key: str, pin: str, role: str) -> str:
    import re

    key_token = re.sub(r"[^A-Z0-9]", "", str(component_key).upper()) or "X"
    pin_token = re.sub(r"[^A-Z0-9]", "", str(pin).upper()) or "X"
    role_token = re.sub(r"[^A-Z0-9]", "", str(role).upper())
    if role_token and role_token != "UNKNOWN":
        return f"{key_token}PIN{pin_token}{role_token}"[:60]
    return f"{key_token}PIN{pin_token}"[:60]


def _component_body_bbox_for_catalogue(data: bytes, family: str) -> dict[str, int]:
    """Return the bbox for the component packet without terminal/WIRE stubs.

    Multi-pin native donors often keep zero-length WIRE records in the placed
    component packet after `$TERBIDIR` records are removed.  Those wires are pin
    evidence, but they are not the component body.  Catalogue offsets therefore
    use the terminal/WIRE-stripped packet as their fallback coordinate frame.
    """

    component_data = _component_only_chunk_from_terminalized_chunk(data)
    pairs = layout_coordinate_pairs(component_data, family)
    if not pairs:
        pairs = layout_coordinate_pairs(data, family)
        component_data = data
    if not pairs:
        raise ValueError(f"{family} packet has no catalogue coordinate pairs.")
    return coordinate_bbox(component_data, pairs)


def _pin_coordinate_from_wire_row(
    row: dict[str, Any],
    *,
    side: str,
) -> tuple[int, int]:
    x1, y1, x2, y2 = (int(value) for value in row["coordinates"])
    if (x1, y1) == (x2, y2):
        return x1, y1
    if side == "left":
        return ((x1, y1) if x1 >= x2 else (x2, y2))
    if side == "right":
        return ((x1, y1) if x1 <= x2 else (x2, y2))
    return x2, y2


def plan_catalogue_pin_bidir_terminals(
    selected_groups: Iterable[Any],
    *,
    catalog: Any | None = None,
    suffix_start: int = 0x7300,
) -> dict[str, Any]:
    """Plan multi-pin terminals from catalogue Proteus pin geometry.

    This is the unified expansion path for IC/three-pin/display work.  It uses
    the same grid-contact + short-wire geometry as the accepted two-pin route,
    but only for components whose catalogue entry already contains donor-
    derived Proteus pin geometry.
    """

    if catalog is None:
        from .component_catalog import load_component_catalog

        catalog = load_component_catalog()
    terminal_plans: list[dict[str, Any]] = []
    missing_geometry: list[dict[str, str]] = []
    suffix = suffix_start
    for group in selected_groups:
        family = _group_family(group)
        key = _group_key(group)
        if _is_terminal_infrastructure_group(group):
            continue
        profile = catalog.get_profile(family)
        if profile is None:
            missing_geometry.append({"component_key": key, "component_family": family})
            continue
        geometry = profile.proteus.get("pin_geometry", {})
        pins = geometry.get("pins", {}) if isinstance(geometry, dict) else {}
        if not isinstance(pins, dict) or not pins:
            missing_geometry.append({"component_key": key, "component_family": family})
            continue
        data = bytes(getattr(group, "data", b""))
        try:
            bbox = _component_body_bbox_for_catalogue(data, family)
        except ValueError:
            missing_geometry.append({"component_key": key, "component_family": family})
            continue
        wire_rows = _wire_rows_from_chunk(data, chunk_start=0)
        for pin in profile.pins:
            if pin.hidden:
                continue
            raw_pin_geometry = pins.get(pin.name)
            if not isinstance(raw_pin_geometry, dict):
                missing_geometry.append(
                    {
                        "component_key": key,
                        "component_family": family,
                        "pin": pin.name,
                    }
                )
                continue
            side = str(raw_pin_geometry.get("side", "")).lower()
            if side == "left":
                angle = LEFT_SIDE_ANGLE
            elif side == "right":
                angle = RIGHT_SIDE_ANGLE
            else:
                missing_geometry.append(
                    {
                        "component_key": key,
                        "component_family": family,
                        "pin": pin.name,
                    }
                )
                continue
            wire_order_index = raw_pin_geometry.get("wire_order_index")
            existing_wire: dict[str, Any] | None = None
            if isinstance(wire_order_index, int) and 0 <= wire_order_index < len(wire_rows):
                existing_wire = wire_rows[wire_order_index]
            pin_x = int(bbox["min_x"]) + int(
                raw_pin_geometry["x_offset_from_component_bbox_min"]
            )
            pin_y = int(bbox["min_y"]) + int(
                raw_pin_geometry["y_offset_from_component_bbox_min"]
            )
            coordinate_source = (
                "component_bbox_min_offset_existing_wire_identity"
                if existing_wire is not None
                else "component_bbox_min_offset"
            )
            terminal = TerminalSpec(
                label=_catalogue_terminal_label(key, pin.name, pin.role),
                symbol_x=pin_x,
                symbol_y=pin_y,
                angle_tenths=angle,
                suffix=suffix & 0xFFFF,
                component_key=key,
                component_family=family,
                pin_hint=f"{pin.name}:{pin.role}",
                attachment_policy="catalogue_pin_geometry_grid_short_wire",
            )
            terminal, wire_start_x, wire_start_y = _terminal_at_grid_contact(
                terminal,
                pin_x=pin_x,
                pin_y=pin_y,
                outward_grid_steps=int(
                    raw_pin_geometry.get("terminal_contact_outward_grid_steps", 1)
                ),
            )
            terminal_plans.append(
                {
                    "terminal": terminal.as_dict(),
                    "pin": {
                        "name": pin.name,
                        "role": pin.role,
                        "electrical_type": pin.electrical_type,
                        "x": pin_x,
                        "y": pin_y,
                        "side": side,
                    },
                    "short_wire": {
                        "start": {"x": wire_start_x, "y": wire_start_y},
                        "end": {"x": pin_x, "y": pin_y},
                        "record": _build_native_short_wire(
                            wire_start_x,
                            wire_start_y,
                            pin_x,
                            pin_y,
                        ).hex(),
                    },
                    "catalogue_geometry": dict(raw_pin_geometry),
                    "component_bbox": dict(bbox),
                    "coordinate_source": coordinate_source,
                    "existing_wire": (
                        {
                            "wire_order_index": wire_order_index,
                            "marker_offset": int(existing_wire["marker_offset"]),
                            "coordinates": list(existing_wire["coordinates"]),
                        }
                        if existing_wire is not None
                        else None
                    ),
                }
            )
            suffix += 1
    return {
        "stage": "catalogue_pin_terminal_planner",
        "terminal_count": len(terminal_plans),
        "terminal_plans": terminal_plans,
        "missing_geometry": missing_geometry,
        "valid": not missing_geometry and bool(terminal_plans),
        "binary_emission": {
            "applied": False,
            "reason": (
                "Planner only. Multi-pin component pin-link byte offsets must be "
                "mapped before shared terminal placer emits active ROOT.DSN records."
            ),
        },
    }


def _patch_wire_record_coordinates(
    data: bytes,
    *,
    marker_offset: int,
    start_x: int,
    start_y: int,
    end_x: int,
    end_y: int,
) -> bytes:
    if data[marker_offset : marker_offset + len(b"\x7fWIRE")] != b"\x7fWIRE":
        raise ValueError(f"WIRE marker missing at offset {marker_offset}.")
    coordinate_start = marker_offset + 10
    if coordinate_start + 16 > len(data):
        raise ValueError(f"WIRE coordinates at offset {marker_offset} are truncated.")
    patched = bytearray(data)
    patched[coordinate_start : coordinate_start + 16] = struct.pack(
        "<iiii",
        int(start_x),
        int(start_y),
        int(end_x),
        int(end_y),
    )
    return bytes(patched)


def _patch_component_link_suffix(
    data: bytes,
    *,
    old_suffix: int,
    new_suffix: int,
    before_offset: int,
    after_offset: int = 0,
) -> tuple[bytes, int]:
    pattern = struct.pack("<H", old_suffix & 0xFFFF) + b"\x01\x00"
    candidates: list[int] = []
    cursor = 0
    while True:
        position = data.find(pattern, cursor)
        if position < 0:
            break
        if after_offset <= position < before_offset:
            candidates.append(position)
        cursor = position + 1
    if not candidates:
        raise ValueError(
            f"Could not find component pin-link field {old_suffix:04x} before "
            f"WIRE offset {before_offset}."
        )
    position = max(candidates)
    patched = bytearray(data)
    patched[position : position + 2] = struct.pack("<H", new_suffix & 0xFFFF)
    return bytes(patched), position


def _patch_component_link_before_wire(
    data: bytes,
    *,
    new_suffix: int,
    before_offset: int,
    after_offset: int = 0,
    preferred_old_suffix: int | None = None,
    preferred_old_suffixes: Iterable[int] = (),
) -> tuple[bytes, int, int]:
    candidates_to_try = list(preferred_old_suffixes)
    if preferred_old_suffix is not None:
        candidates_to_try.insert(0, preferred_old_suffix)
    for candidate_suffix in dict.fromkeys(int(item) for item in candidates_to_try):
        try:
            patched, position = _patch_component_link_suffix(
                data,
                old_suffix=candidate_suffix,
                new_suffix=new_suffix,
                before_offset=before_offset,
            )
            return patched, position, candidate_suffix & 0xFFFF
        except ValueError:
            continue

    wire_spans = _wire_record_spans(data)
    candidates: list[int] = []
    cursor = 0
    while True:
        position = data.find(b"\x01\x00", cursor)
        if position < 0:
            break
        suffix_position = position - 2
        if (
            suffix_position >= 0
            and suffix_position >= after_offset
            and suffix_position < before_offset
            and not _position_in_spans(suffix_position, wire_spans)
        ):
            candidates.append(suffix_position)
        cursor = position + 1
    if not candidates:
        raise ValueError(
            f"Could not locate a component pin-link field before WIRE offset "
            f"{before_offset}."
        )
    suffix_position = max(candidates)
    old_suffix = struct.unpack("<H", data[suffix_position : suffix_position + 2])[0]
    patched = bytearray(data)
    patched[suffix_position : suffix_position + 2] = struct.pack(
        "<H",
        new_suffix & 0xFFFF,
    )
    return bytes(patched), suffix_position, old_suffix


def _current_bidir_suffixes_by_pin(
    data: bytes,
    profile: Any,
) -> dict[str, int]:
    suffixes: dict[str, int] = {}
    for record in _bidir_label_records(data):
        raw_pin, signal = _pin_label_parts(str(record["label"]))
        candidates = [value for value in (raw_pin, signal) if value]
        for candidate in candidates:
            try:
                pin_name = profile.normalize_pin(candidate).name
            except Exception:
                continue
            suffixes.setdefault(pin_name, int(record["suffix"]))
            break
    return suffixes


def attach_catalogue_pin_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    catalog: Any | None = None,
    terminal_families: Iterable[str] | None = None,
    suffix_start: int = 0x7300,
) -> dict[str, Any]:
    """Attach catalogue-backed multi-pin terminals using placed WIRE skeletons.

    The component placer may emit multi-pin native packets that already contain
    donor-derived component pin-link fields and zero-length WIRE records, but no
    `$TERBIDIR` records.  This shared path rewrites those WIRE records into the
    accepted grid-contact short-wire geometry, inserts active terminal records
    immediately before each component packet, and then rebases both terminal and
    component pin links from final ROOT.DSN WIRE addresses.
    """

    if catalog is None:
        from .component_catalog import load_component_catalog

        catalog = load_component_catalog()
    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("Catalogue terminal attachment requires selected groups.")
    requested = (
        None
        if terminal_families is None
        else set(dict.fromkeys(str(item) for item in terminal_families))
    )
    source = Path(project)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    ordered_groups = _covered_component_stream_with_optional_final_ff(
        original_chunk,
        groups,
    )
    terminal_templates = NATIVE_BIDIR_TEMPLATES

    local_records: list[bytes] = []
    family_reports: list[dict[str, Any]] = []
    preserved_rows: list[dict[str, Any]] = []
    suffix = suffix_start
    terminalized_count = 0
    for group in ordered_groups:
        family = _group_family(group)
        key = _group_key(group)
        original_group_data = bytes(getattr(group, "data", b""))
        data = _strip_bidir_records_from_chunk(original_group_data)
        stripped_existing_terminals = (
            original_group_data.count(BIDIR_MARKER) - data.count(BIDIR_MARKER)
        )
        if _is_terminal_infrastructure_group(group):
            local_records.append(data)
            preserved_rows.append(
                {
                    "component_key": key,
                    "component_family": family,
                    "reason": "terminal_infrastructure",
                    "byte_preserved": True,
                }
            )
            continue
        if requested is not None and family not in requested:
            local_records.append(data)
            preserved_rows.append(
                {
                    "component_key": key,
                    "component_family": family,
                    "reason": "not_requested",
                    "byte_preserved": True,
                }
            )
            continue
        profile = catalog.get_profile(family)
        geometry = profile.proteus.get("pin_geometry", {}) if profile is not None else {}
        pins = geometry.get("pins", {}) if isinstance(geometry, dict) else {}
        if profile is None or not isinstance(pins, dict) or not pins:
            local_records.append(data)
            preserved_rows.append(
                {
                    "component_key": key,
                    "component_family": family,
                    "reason": "missing_catalogue_pin_geometry",
                    "byte_preserved": True,
                }
            )
            continue

        current_suffix_by_pin = _current_bidir_suffixes_by_pin(
            original_group_data,
            profile,
        )
        planning_group = replace(group, data=data)
        plan = plan_catalogue_pin_bidir_terminals(
            [planning_group],
            catalog=catalog,
            suffix_start=suffix,
        )
        if not plan["valid"]:
            raise ValueError(
                f"Catalogue terminal plan for {family} {key} is incomplete: "
                f"{plan['missing_geometry']}."
            )
        patched_data = data
        data_wire_rows = _wire_rows_from_chunk(data, chunk_start=0)
        wire_marker_offsets = [
            int(row["marker_offset"])
            for row in sorted(data_wire_rows, key=lambda item: int(item["marker_offset"]))
        ]
        terminal_records: list[bytes] = []
        terminal_pins: list[dict[str, Any]] = []
        for row in plan["terminal_plans"]:
            pin_name = str(row["pin"]["name"])
            raw_geometry = pins[pin_name]
            existing_wire = row.get("existing_wire")
            if not isinstance(existing_wire, dict):
                raise ValueError(
                    f"{family} {key} pin {pin_name} lacks an existing WIRE anchor."
                )
            wire_order_index = int(existing_wire["wire_order_index"])
            after_offset = (
                0
                if wire_order_index <= 0
                else wire_marker_offsets[wire_order_index - 1] + 27
            )
            donor_old_suffix = int(raw_geometry.get("donor_terminal_suffix"))
            preferred_old_suffix = current_suffix_by_pin.get(
                pin_name,
                donor_old_suffix,
            )
            temporary_suffix = suffix & 0xFFFF
            suffix += 1
            patched_data, component_link_position, old_suffix = (
                _patch_component_link_before_wire(
                patched_data,
                new_suffix=temporary_suffix,
                before_offset=int(existing_wire["marker_offset"]),
                after_offset=after_offset,
                preferred_old_suffix=preferred_old_suffix,
                preferred_old_suffixes=(preferred_old_suffix, donor_old_suffix),
            )
            )
            short_wire = row["short_wire"]
            start = short_wire["start"]
            end = short_wire["end"]
            patched_data = _patch_wire_record_coordinates(
                patched_data,
                marker_offset=int(existing_wire["marker_offset"]),
                start_x=int(start["x"]),
                start_y=int(start["y"]),
                end_x=int(end["x"]),
                end_y=int(end["y"]),
            )
            terminal_dict = dict(row["terminal"])
            terminal_dict["suffix"] = f"{temporary_suffix:04x}"
            terminal_records.append(
                build_bidir_record(
                    terminal_templates,
                    label=str(terminal_dict["label"]),
                    symbol_x=int(terminal_dict["symbol_x"]),
                    symbol_y=int(terminal_dict["symbol_y"]),
                    angle_tenths=int(terminal_dict["angle_tenths"]),
                    suffix=temporary_suffix,
                    active_link=True,
                )
            )
            terminal_pins.append(
                {
                    "component_key": key,
                    "component_family": family,
                    "pin": row["pin"],
                    "terminal": terminal_dict,
                    "short_wire": {
                        "start": dict(start),
                        "end": dict(end),
                    },
                    "catalogue_geometry": dict(raw_geometry),
                    "component_bbox": dict(row.get("component_bbox", {})),
                    "existing_wire": dict(existing_wire),
                    "old_suffix": f"{old_suffix:04x}",
                    "temporary_suffix": f"{temporary_suffix:04x}",
                    "component_link_position": component_link_position,
                    "existing_wire_marker_offset": int(existing_wire["marker_offset"]),
                    "coordinate_source": row["coordinate_source"],
                }
            )
        local_records.extend(terminal_records)
        local_records.append(b"\x00")
        local_records.append(patched_data)
        terminalized_count += 1
        family_reports.append(
            {
                "family_handler": f"{family}/catalogue-existing-wire-v1",
                "component_key": key,
                "component_family": family,
                "component_count": 1,
                "terminal_count": len(terminal_records),
                "wire_count": len(terminal_records),
                "stripped_existing_terminal_count": stripped_existing_terminals,
                "terminal_pins": terminal_pins,
            }
        )

    if not family_reports:
        raise ValueError("No catalogue-backed terminalized component was emitted.")
    new_chunk = _ensure_double_ff_object_stream_terminator(
        original_chunk[:1] + b"".join(local_records)
    )
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, destination, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(destination, "ROOT.DSN"))

    terminal_count = sum(report["terminal_count"] for report in family_reports)
    wire_count = sum(report["wire_count"] for report in family_reports)
    wire_path_checks: list[dict[str, Any]] = []
    for report in family_reports:
        for row in report["terminal_pins"]:
            terminal = row["terminal"]
            wire = row["short_wire"]
            angle = int(terminal["angle_tenths"])
            if angle == LEFT_SIDE_ANGLE:
                contact_x = int(terminal["symbol_x"]) + TERMINAL_CONTACT_TO_PIN
            elif angle == RIGHT_SIDE_ANGLE:
                contact_x = int(terminal["symbol_x"]) - TERMINAL_CONTACT_TO_PIN
            else:
                contact_x = int(terminal["symbol_x"])
            wire_path_checks.append(
                {
                    "component_key": row["component_key"],
                    "component_family": row["component_family"],
                    "pin": row["pin"]["name"],
                    "terminal_contact_grid_aligned": (
                        contact_x % PROTEUS_TERMINAL_GRID == 0
                        and int(terminal["symbol_y"]) % PROTEUS_TERMINAL_GRID == 0
                    ),
                    "terminal_to_wire": (
                        contact_x == int(wire["start"]["x"])
                        and int(terminal["symbol_y"]) == int(wire["start"]["y"])
                    ),
                    "wire_to_pin": (
                        int(wire["end"]["x"]) == int(row["pin"]["x"])
                        and int(wire["end"]["y"]) == int(row["pin"]["y"])
                    ),
                    "wire_is_nonzero": (
                        int(wire["start"]["x"]) != int(wire["end"]["x"])
                        or int(wire["start"]["y"]) != int(wire["end"]["y"])
                    ),
                }
            )
    report = {
        "stage": "terminal_placer",
        "family_handler": "CATALOGUE/existing-wire-v1",
        "status": "pending_proteus_user_acceptance",
        "attachment_policy": (
            "catalogue_pin_identity_existing_wire_anchor_grid_short_wire"
        ),
        "runtime_circuit_donor_dependency": False,
        "component_coordinate_mutation": False,
        "terminal_record_encoder": "embedded_proteus_813_schema",
        "wire_record_encoder": "rewrite_existing_donor_wire_records",
        "terminal_count_added": terminal_count,
        "wire_count_added": 0,
        "wire_count_rewritten": wire_count,
        "terminalized_component_count": terminalized_count,
        "preserved_component_count": len(preserved_rows),
        "preserved_groups": preserved_rows,
        "family_reports": family_reports,
        "wire_path_contact_checks": wire_path_checks,
        "wire_path_contacts_valid": all(
            row["terminal_contact_grid_aligned"]
            and row["terminal_to_wire"]
            and row["wire_to_pin"]
            and row["wire_is_nonzero"]
            for row in wire_path_checks
        ),
        "terminal_grid_alignment_valid": all(
            row["terminal_contact_grid_aligned"] for row in wire_path_checks
        ),
        "bidir_count_before": original_chunk.count(BIDIR_MARKER),
        "bidir_count_after": final_chunk.count(BIDIR_MARKER),
        "wire_count_before": original_chunk.count(b"\x7fWIRE"),
        "wire_count_after": final_chunk.count(b"\x7fWIRE"),
        "stripped_existing_terminal_count": sum(
            report["stripped_existing_terminal_count"]
            for report in family_reports
        ),
        "object_chunk_size_before": len(original_chunk),
        "object_chunk_size_after": len(final_chunk),
        "object_chunk_double_ff_valid": final_chunk.endswith(b"\xff\xff"),
        "base_component_stream_covered": True,
    }
    return _rebase_terminal_links_to_final_wire_addresses(destination, report)


def _s32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _u32_at(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=False)


def _compact_terminal_label(
    prefix: str,
    terminal_index: int,
    *,
    min_digits: int = 1,
) -> str:
    """Return a compact deterministic terminal label for researched families."""

    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if len(prefix) != 1 or prefix not in alphabet:
        raise ValueError(
            "Terminal label prefix must be one uppercase ASCII letter or digit."
        )
    if terminal_index < 0:
        raise ValueError(
            "Terminal label index must be non-negative."
        )
    if min_digits <= 1 and terminal_index < len(alphabet):
        return prefix + alphabet[terminal_index]
    digits: list[str] = []
    value = terminal_index
    while value or len(digits) < min_digits:
        digits.append(alphabet[value % len(alphabet)])
        value //= len(alphabet)
    return prefix + "".join(reversed(digits))


def _compact_label_min_digits(component_count: int) -> int:
    return 3 if component_count * 2 > 36 else 1


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


def _generic_two_pin_body_offsets(data: bytes, family: str) -> tuple[int, int]:
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
            f"{family} terminal attachment needs exactly one parsed structural "
            f"body anchor; found {len(candidates)}."
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

    groups = tuple(selected_groups)
    label_min_digits = _compact_label_min_digits(len(groups))
    pairs: list[CapacitorTerminalPair] = []
    for index, group in enumerate(groups, start=1):
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
            label=_compact_terminal_label(
                label_prefix,
                (index - 1) * 2,
                min_digits=label_min_digits,
            ),
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
            label=_compact_terminal_label(
                label_prefix,
                (index - 1) * 2 + 1,
                min_digits=label_min_digits,
            ),
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

    groups = tuple(selected_groups)
    label_min_digits = _compact_label_min_digits(len(groups))
    pairs: list[InductorTerminalPair] = []
    for index, group in enumerate(groups, start=1):
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
            label=_compact_terminal_label(
                label_prefix,
                (index - 1) * 2,
                min_digits=label_min_digits,
            ),
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
            label=_compact_terminal_label(
                label_prefix,
                (index - 1) * 2 + 1,
                min_digits=label_min_digits,
            ),
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

    groups = tuple(selected_groups)
    label_min_digits = _compact_label_min_digits(len(groups))
    pairs: list[ElectrolyticCapTerminalPair] = []
    for index, group in enumerate(groups, start=1):
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
            label=_compact_terminal_label(
                label_prefix,
                (index - 1) * 2,
                min_digits=label_min_digits,
            ),
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
            label=_compact_terminal_label(
                label_prefix,
                (index - 1) * 2 + 1,
                min_digits=label_min_digits,
            ),
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


def plan_attached_generic_two_pin_terminals(
    selected_groups: Iterable[Any],
    *,
    label_prefix: str | None = None,
    suffix_start: int | None = None,
) -> tuple[CapacitorTerminalPair, ...]:
    """Plan profile-based horizontal terminals for simple remaining 2-pin parts.

    These families share the donor packet pattern decoded from the fixed
    2026-06-18 new-component mega donor: one body anchor near the packet tail,
    two clear endpoint-link fields at ``body_x_offset+25`` and ``+29``, and a
    horizontal one-grid pin span on each side of the body.
    """

    groups = tuple(selected_groups)
    families = {str(getattr(group, "family", "")) for group in groups}
    if len(families) != 1 or next(iter(families), "") not in GENERIC_TWO_PIN_PROFILES:
        raise ValueError(
            "The generic two-pin terminal handler requires one profiled family; "
            f"received {sorted(families)}."
        )
    family = next(iter(families))
    profile = GENERIC_TWO_PIN_PROFILES[family]
    prefix = label_prefix or str(profile["label_prefix"])
    label_min_digits = _compact_label_min_digits(len(groups))
    suffix_base = (
        int(profile["suffix_base"]) if suffix_start is None else suffix_start
    )

    pairs: list[CapacitorTerminalPair] = []
    for index, group in enumerate(groups, start=1):
        key = str(getattr(group, "key", ""))
        data = getattr(group, "data", b"")
        if not isinstance(data, bytes):
            data = bytes(data)
        x_offset, y_offset = _generic_two_pin_body_offsets(data, family)
        angle_tenths = _u32_at(data, x_offset + 8)
        if angle_tenths != 0:
            raise ValueError(
                f"{family} {key} uses unproven orientation {angle_tenths}; "
                "the V11 generic two-pin route accepts horizontal donor packets only."
            )
        input_link_offset = x_offset + 25
        output_link_offset = x_offset + 29
        if output_link_offset + 4 > len(data):
            raise ValueError(
                f"{family} {key} packet ends before its two endpoint-link fields."
            )

        body_x = _s32_at(data, x_offset)
        body_y = _s32_at(data, y_offset)
        left_pin_x = body_x - GENERIC_TWO_PIN_HALF_SPAN
        right_pin_x = body_x + GENERIC_TWO_PIN_HALF_SPAN
        left_suffix = (suffix_base + (index - 1) * 2 + 1) & 0xFFFF
        right_suffix = (suffix_base + (index - 1) * 2 + 2) & 0xFFFF
        left = TerminalSpec(
            label=_compact_terminal_label(
                prefix,
                (index - 1) * 2,
                min_digits=label_min_digits,
            ),
            symbol_x=left_pin_x - GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=body_y,
            angle_tenths=LEFT_SIDE_ANGLE,
            suffix=left_suffix,
            component_key=key,
            component_family=family,
            pin_hint=str(profile["left_pin_hint"]),
            attachment_policy="generic_two_pin_profile_link_suffix_and_short_wire",
        )
        right = TerminalSpec(
            label=_compact_terminal_label(
                prefix,
                (index - 1) * 2 + 1,
                min_digits=label_min_digits,
            ),
            symbol_x=right_pin_x + GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=body_y,
            angle_tenths=RIGHT_SIDE_ANGLE,
            suffix=right_suffix,
            component_key=key,
            component_family=family,
            pin_hint=str(profile["right_pin_hint"]),
            attachment_policy="generic_two_pin_profile_link_suffix_and_short_wire",
        )
        pairs.append(
            CapacitorTerminalPair(
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
                input_link_offset=input_link_offset,
                output_link_offset=output_link_offset,
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
            "The attached source-terminal handler requires one profiled source family; "
            f"received {sorted(families)}."
        )
    family = next(iter(families))
    prefix = label_prefix or SOURCE_TERMINAL_LABEL_PREFIXES[family]
    label_min_digits = _compact_label_min_digits(len(groups))
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
        if family in SOURCE_OUTPUT_UPPER_PIN_FAMILIES:
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
            label=_compact_terminal_label(
                prefix,
                input_label_index,
                min_digits=label_min_digits,
            ),
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
            label=_compact_terminal_label(
                prefix,
                output_label_index,
                min_digits=label_min_digits,
            ),
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


def _patch_generic_two_pin_terminal_links(
    data: bytes,
    pair: CapacitorTerminalPair,
) -> bytes:
    out = bytearray(data)
    for offset, terminal in (
        (pair.input_link_offset, pair.left),
        (pair.output_link_offset, pair.right),
    ):
        if offset + 4 > len(out):
            raise ValueError(
                f"{pair.component_family} {pair.component_key} packet ends before "
                "its two endpoint-link fields."
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


def _build_native_short_wire(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
) -> bytes:
    """Encode one canonical 50-byte Proteus WIRE record.

    The prefix is invariant across the accepted R/C/L and mixed-analog corpus;
    coordinates occupy bytes 33..48 and byte 49 is the stream separator.
    """

    record = NATIVE_WIRE_PREFIX + struct.pack("<iiii", x1, y1, x2, y2) + b"\x00"
    if len(record) != 50 or record.find(b"\x7fWIRE") != 23:
        raise AssertionError("Canonical short-WIRE encoder produced an invalid record.")
    return record


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
    if family in GENERIC_TWO_PIN_PROFILES:
        if label_prefix is not None or suffix_start is not None:
            raise ValueError(
                f"{family}/generic-v11 uses its family-safe profile defaults; "
                "custom label_prefix and suffix_start are unsupported here."
            )
        return attach_mixed_native_bidir_terminals_to_project(
            project,
            output,
            groups,
            terminal_families=(family,),
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


def _terminal_pin_contact_checks(
    family_reports: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Describe terminal-grid and direct-pin contact for every attachment."""

    checks: list[dict[str, Any]] = []
    for family_report in family_reports:
        for pair in family_report.get("terminal_pairs", []):
            pins = pair.get("pins", {})
            roles = ("left", "right") if pair.get("left") else ("input", "output")
            for role in roles:
                terminal = pair.get(role, {})
                pin = pins.get(role, {})
                angle = terminal.get("angle_tenths")
                if angle == LEFT_SIDE_ANGLE:
                    contact_x = terminal.get("symbol_x", 0) + TERMINAL_CONTACT_TO_PIN
                elif angle == RIGHT_SIDE_ANGLE:
                    contact_x = terminal.get("symbol_x", 0) - TERMINAL_CONTACT_TO_PIN
                else:
                    contact_x = None
                checks.append(
                    {
                        "component_key": pair.get("component_key"),
                        "component_family": pair.get("component_family"),
                        "role": role,
                        "terminal_symbol_x": terminal.get("symbol_x"),
                        "terminal_symbol_y": terminal.get("symbol_y"),
                        "terminal_contact_x": contact_x,
                        "terminal_contact_y": terminal.get("symbol_y"),
                        "pin_x": pin.get("x"),
                        "pin_y": pin.get("y"),
                        "terminal_symbol_grid_aligned": (
                            terminal.get("symbol_x", 0) % PROTEUS_TERMINAL_GRID == 0
                            and terminal.get("symbol_y", 0)
                            % PROTEUS_TERMINAL_GRID
                            == 0
                        ),
                        "terminal_contact_grid_aligned": (
                            isinstance(contact_x, int)
                            and contact_x % PROTEUS_TERMINAL_GRID == 0
                            and terminal.get("symbol_y", 0)
                            % PROTEUS_TERMINAL_GRID
                            == 0
                        ),
                        "coincident": (
                            contact_x == pin.get("x")
                            and terminal.get("symbol_y") == pin.get("y")
                        ),
                    }
                )
    return checks


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
        suffix=terminal.suffix if active_link else 0,
        active_link=active_link,
    )


def _mixed_overlay_family_parts(
    family: str,
    groups: tuple[Any, ...],
    *,
    terminal_templates: Any,
    source_index_start: int,
    active_links: bool,
    snap_terminal_contacts_to_grid: bool = False,
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
        terminals = [
            *(pair.left for pair in pairs),
            *(pair.right for pair in pairs),
        ]
        for group, pair in zip(groups, pairs, strict=True):
            patched_by_id[id(group)] = _patch_resistor_terminal_links(
                bytes(group.data),
                pair,
            )
    elif family == "CAP":
        pairs = plan_attached_capacitor_terminals(groups)
        terminals = [
            *(pair.right for pair in pairs),
            *(pair.left for pair in pairs),
        ]
        for group, pair in zip(groups, pairs, strict=True):
            patched_by_id[id(group)] = _patch_capacitor_terminal_links(
                bytes(group.data),
                pair,
            )
    elif family == "REALIND":
        pairs = plan_attached_inductor_terminals(groups)
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.left, pair.right)
        ]
        for group, pair in zip(groups, pairs, strict=True):
            patched_by_id[id(group)] = _patch_inductor_terminal_links(
                bytes(group.data),
                pair,
            )
    elif family == "CAP-ELEC":
        pairs = plan_attached_electrolytic_capacitor_terminals(groups)
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.right, pair.left)
        ]
        for group, pair in zip(groups, pairs, strict=True):
            patched_by_id[id(group)] = _patch_cap_elec_terminal_links(
                bytes(group.data),
                pair,
            )
    elif family in GENERIC_TWO_PIN_PROFILES:
        pairs = plan_attached_generic_two_pin_terminals(groups)
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.left, pair.right)
        ]
        for group, pair in zip(groups, pairs, strict=True):
            patched_by_id[id(group)] = _patch_generic_two_pin_terminal_links(
                bytes(group.data),
                pair,
            )
    elif family in SOURCE_COMPONENT_BARE_BASE_SIZES:
        pairs = plan_attached_source_terminals(
            groups,
            source_index_start=source_index_start,
        )
        if family in SOURCE_OUTPUT_UPPER_PIN_FAMILIES:
            terminal_order = ("output", "input")
            wire_order = ("output", "input")
        else:
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
    else:
        raise ValueError(f"No accepted mixed-overlay handler exists for {family}.")

    if snap_terminal_contacts_to_grid:
        pairs = tuple(_snap_terminal_pair_to_grid(pair) for pair in pairs)
    if family == "RESISTOR":
        terminals = [
            *(pair.left for pair in pairs),
            *(pair.right for pair in pairs),
        ]
    elif family == "CAP":
        terminals = [
            *(pair.right for pair in pairs),
            *(pair.left for pair in pairs),
        ]
    elif family == "REALIND":
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.left, pair.right)
        ]
    elif family == "CAP-ELEC":
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.right, pair.left)
        ]
    elif family in GENERIC_TWO_PIN_PROFILES:
        terminals = [
            terminal
            for pair in pairs
            for terminal in (pair.left, pair.right)
        ]
    elif family in SOURCE_COMPONENT_BARE_BASE_SIZES:
        terminals = [
            getattr(pair, role)
            for pair in pairs
            for role in terminal_order
        ]
    else:
        raise ValueError(f"No accepted mixed-overlay handler exists for {family}.")

    for pair in pairs:
        if isinstance(pair, SourceTerminalPair):
            pins = {
                "input": (pair.input_pin_x, pair.input_pin_y),
                "output": (pair.output_pin_x, pair.output_pin_y),
            }
            starts = {
                "input": (
                    pair.input_wire_start_x,
                    pair.input_wire_start_y,
                ),
                "output": (
                    pair.output_wire_start_x,
                    pair.output_wire_start_y,
                ),
            }
            first_start = starts[wire_order[0]]
            first_pin = pins[wire_order[0]]
            second_start = starts[wire_order[1]]
            second_pin = pins[wire_order[1]]
            wire_pairs.append(
                (
                    _build_native_short_wire(*first_start, *first_pin),
                    _build_native_short_wire(*second_start, *second_pin),
                )
            )
        else:
            wire_pairs.append(
                (
                    _build_native_short_wire(
                        pair.left_wire_start_x,
                        pair.left_wire_start_y,
                        pair.left_pin_x,
                        pair.left_pin_y,
                    ),
                    _build_native_short_wire(
                        pair.right_wire_start_x,
                        pair.right_wire_start_y,
                        pair.right_pin_x,
                        pair.right_pin_y,
                    ),
                )
            )

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
    allow_unlinked_short_wires: bool = False,
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
            family
            for group in groups
            for family in (_terminal_eligible_family(group, accepted),)
            if family is not None
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
    if (
        include_wires
        and not (patch_component_links and active_terminal_links)
        and not (
            allow_unlinked_short_wires
            and not patch_component_links
            and not active_terminal_links
        )
    ):
        raise ValueError(
            "Unlinked mixed wires require allow_unlinked_short_wires=True "
            "with both component and terminal link state disabled."
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
            if _terminal_eligible_family(group, {family}) == family
        )
        pairs, family_terminals, family_wires, family_patches = (
            _mixed_overlay_family_parts(
                family,
                family_groups,
                terminal_templates=terminal_templates,
                source_index_start=source_index_start,
                active_links=active_terminal_links,
                snap_terminal_contacts_to_grid=False,
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
    if wire_records:
        new_chunk = new_chunk[:-1] + b"\xff"
    else:
        new_chunk += b"\xff"
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    write_project_from_parts(source, destination, {"ROOT.DSN": new_dsn})
    final_chunk = _extract_object_chunk(read_internal_file(destination, "ROOT.DSN"))

    suffixes = tuple(
        suffix
        for report in family_reports
        for suffix in _terminal_suffixes(report)
    )
    suffixes_unique = len(suffixes) == len(set(suffixes))
    expected_active_suffix_copies = int(patch_component_links) + int(
        active_terminal_links
    )
    suffix_links_valid = (
        suffixes_unique
        and all(
            final_chunk.count(struct.pack("<H", suffix) + b"\x01\x00")
            == expected_active_suffix_copies
            for suffix in suffixes
        )
    )
    expected_terminals = len(terminal_records)
    expected_wires = len(wire_pairs) * 2 if include_wires else 0
    terminal_pin_contact_checks = _terminal_pin_contact_checks(family_reports)
    terminal_pin_contacts_valid = all(
        row["coincident"] for row in terminal_pin_contact_checks
    )
    if (
        include_wires
        and not patch_component_links
        and not active_terminal_links
    ):
        family_handler = "MIXED/short-wire-v6-temp"
    else:
        family_handler = "MIXED/append-overlay-v3-temp"
    preserved_rows = []
    for group in groups:
        family = _group_family(group)
        if _terminal_eligible_family(group, set(requested)) is not None:
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
        "family_handler": family_handler,
        "status": "temporary_pending_proteus",
        "attachment_policy": "preserve_component_order_then_append_terminal_wire_overlay",
        "object_order": "component_placer_stream_then_all_terminals_then_all_wires",
        "historical_basis": (
            "user_ctrl_s_normalized_t01_terminal_stream_then_short_wires"
            if family_handler == "MIXED/short-wire-v6-temp"
            else "user_confirmed_all_family_v2_opened_with_unattached_appended_terminals"
        ),
        "wire_requirement_basis": "user_confirmed_terminal_to_pin_wires_are_mandatory",
        "terminal_array_order_policy": "selected_component_stream_order",
        "terminal_family_order": list(requested),
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
        "inactive_terminal_suffix_policy": (
            "not_applicable"
            if active_terminal_links
            else "zero_as_proteus_ctrl_s_normalized"
        ),
        "wire_record_emission": include_wires,
        "allow_unlinked_short_wires": allow_unlinked_short_wires,
        "expected_active_suffix_copies": expected_active_suffix_copies,
        "terminal_pin_contacts_valid": terminal_pin_contacts_valid,
        "terminal_pin_contact_checks": terminal_pin_contact_checks,
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
        "terminalized_component_count": sum(
            report["component_count"] for report in family_reports
        ),
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


def _covered_bare_component_stream(
    original_chunk: bytes,
    groups: tuple[Any, ...],
) -> tuple[Any, ...]:
    """Require the supplied groups to describe the complete bare object stream."""

    remaining = list(groups)
    if not remaining:
        raise ValueError("Native mixed attachment requires at least one component group.")
    ordered: list[Any] = []
    offset = 2
    while remaining:
        match: tuple[int, int] | None = None
        for index, group in enumerate(remaining):
            data = bytes(getattr(group, "data", b""))
            if not data:
                continue
            if original_chunk.startswith(data, offset):
                match = (index, len(data))
                break
            final_data = data[:-1] + b"\xff"
            if (
                final_data != data
                and offset + len(final_data) == len(original_chunk)
                and original_chunk.startswith(final_data, offset)
            ):
                match = (index, len(final_data))
                break
        if match is None:
            break
        index, span = match
        ordered.append(remaining.pop(index))
        offset += span
    if remaining or offset != len(original_chunk):
        raise ValueError(
            "Native mixed attachment cannot account for the complete bare object "
            "stream from the supplied component groups. Pass every placed group; "
            "hidden or synthetic records must be exposed by the component placer."
        )
    return tuple(ordered)


def _covered_component_stream_with_optional_final_ff(
    original_chunk: bytes,
    groups: tuple[Any, ...],
) -> tuple[Any, ...]:
    """Like `_covered_bare_component_stream`, but allow the final FF outside groups."""

    remaining = list(groups)
    if not remaining:
        raise ValueError("Component stream coverage requires at least one group.")
    ordered: list[Any] = []
    offset = 2
    while remaining:
        match: tuple[int, int] | None = None
        for index, group in enumerate(remaining):
            data = bytes(getattr(group, "data", b""))
            if data and original_chunk.startswith(data, offset):
                match = (index, len(data))
                break
            final_data = data[:-1] + b"\xff"
            if (
                final_data != data
                and offset + len(final_data) == len(original_chunk)
                and original_chunk.startswith(final_data, offset)
            ):
                match = (index, len(final_data))
                break
        if match is None:
            break
        index, span = match
        ordered.append(remaining.pop(index))
        offset += span
    covered = offset == len(original_chunk) or (
        offset + 1 == len(original_chunk) and original_chunk[offset] == 0xFF
    )
    if remaining or not covered:
        raise ValueError(
            "Catalogue terminal attachment cannot account for the complete "
            "component stream from the supplied groups."
        )
    return tuple(ordered)


def _wire_path_contact_checks(
    family_reports: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Verify grid terminal tip -> short wire -> exact component pin continuity."""

    checks: list[dict[str, Any]] = []
    for family_report in family_reports:
        for pair in family_report.get("terminal_pairs", []):
            roles = ("left", "right") if pair.get("left") else ("input", "output")
            for role in roles:
                terminal = pair[role]
                pin = pair["pins"][role]
                wire = pair["short_wires"][role]
                angle = terminal["angle_tenths"]
                if angle == LEFT_SIDE_ANGLE:
                    contact_x = terminal["symbol_x"] + TERMINAL_CONTACT_TO_PIN
                elif angle == RIGHT_SIDE_ANGLE:
                    contact_x = terminal["symbol_x"] - TERMINAL_CONTACT_TO_PIN
                else:
                    contact_x = None
                terminal_to_wire = (
                    contact_x == wire["start"]["x"]
                    and terminal["symbol_y"] == wire["start"]["y"]
                )
                wire_to_pin = (
                    wire["end"]["x"] == pin["x"]
                    and wire["end"]["y"] == pin["y"]
                )
                symbol_grid_aligned = (
                    terminal["symbol_x"] % PROTEUS_TERMINAL_GRID == 0
                    and terminal["symbol_y"] % PROTEUS_TERMINAL_GRID == 0
                )
                contact_grid_aligned = (
                    isinstance(contact_x, int)
                    and contact_x % PROTEUS_TERMINAL_GRID == 0
                    and terminal["symbol_y"] % PROTEUS_TERMINAL_GRID == 0
                )
                checks.append(
                    {
                        "component_key": pair["component_key"],
                        "component_family": pair["component_family"],
                        "role": role,
                        "terminal_symbol_grid_aligned": symbol_grid_aligned,
                        "terminal_contact_grid_aligned": contact_grid_aligned,
                        "terminal_to_wire": terminal_to_wire,
                        "wire_to_pin": wire_to_pin,
                        "wire_is_nonzero": (
                            wire["start"]["x"] != wire["end"]["x"]
                            or wire["start"]["y"] != wire["end"]["y"]
                        ),
                        "valid": (
                            symbol_grid_aligned
                            and contact_grid_aligned
                            and terminal_to_wire
                            and wire_to_pin
                        ),
                    }
                )
    return checks


def attach_mixed_native_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    terminal_families: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Attach researched families to the beautified component stream.

    Proteus wires are serialized as part of an active attachment unit, not as
    a trailing geometry overlay. The unit consists of active terminal records,
    matching component pin-link fields, and two schema-encoded WIRE records
    immediately following the patched component. The component placer's order
    is preserved; final link values are normalized by the public stage after
    ROOT.DSN serialization.
    """

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("Native mixed attachment requires selected component groups.")
    accepted = set(ACCEPTED_TERMINAL_FAMILY_ORDER)
    available = tuple(
        dict.fromkeys(
            family
            for group in groups
            for family in (_terminal_eligible_family(group, accepted),)
            if family is not None
        )
    )
    requested = available if terminal_families is None else tuple(
        dict.fromkeys(str(item) for item in terminal_families)
    )
    unknown = sorted(set(requested) - accepted)
    missing = sorted(set(requested) - set(available))
    if unknown:
        raise ValueError(f"No accepted native-wire handler exists for {unknown}.")
    if missing:
        raise ValueError(f"Requested native-wire families are absent: {missing}.")
    if not requested:
        raise ValueError(
            "Native mixed attachment requires at least one researched terminal family."
        )
    source = Path(project)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError("Native mixed attachment requires a bare component-placer project.")
    ordered_groups = _covered_bare_component_stream(original_chunk, groups)

    terminal_templates = NATIVE_BIDIR_TEMPLATES
    family_parts: dict[
        str,
        tuple[
            tuple[Any, ...],
            list[bytes],
            list[tuple[bytes, bytes]],
            dict[int, bytes],
        ],
    ] = {}
    family_reports: list[dict[str, Any]] = []
    source_index_start = 1
    for family in requested:
        family_groups = tuple(
            group
            for group in ordered_groups
            if _terminal_eligible_family(group, {family}) == family
        )
        parts = _mixed_overlay_family_parts(
            family,
            family_groups,
            terminal_templates=terminal_templates,
            source_index_start=source_index_start,
            active_links=True,
            snap_terminal_contacts_to_grid=True,
        )
        if family in SOURCE_COMPONENT_BARE_BASE_SIZES:
            source_index_start += len(family_groups)
        family_parts[family] = parts
        pairs, terminal_records, wire_pairs, _patches = parts
        family_reports.append(
            {
                "family_handler": f"{family}/accepted-native-unit",
                "component_count": len(family_groups),
                "terminal_count": len(terminal_records),
                "wire_count": len(wire_pairs) * 2,
                "terminal_pairs": [pair.as_dict() for pair in pairs],
            }
        )

    leading_records: list[bytes] = []
    terminal_by_group_id: dict[int, tuple[bytes, ...]] = {}
    wire_by_group_id: dict[int, tuple[bytes, bytes]] = {}
    patched_by_group_id: dict[int, bytes] = {}
    for family in requested:
        family_groups = tuple(
            group
            for group in ordered_groups
            if _terminal_eligible_family(group, {family}) == family
        )
        _pairs, terminal_records, wire_pairs, patches = family_parts[family]
        patched_by_group_id.update(patches)
        if family == "RESISTOR":
            leading_records.extend(terminal_records)
            for group, wires in zip(family_groups, wire_pairs, strict=True):
                terminal_by_group_id[id(group)] = ()
                wire_by_group_id[id(group)] = wires
        elif family == "CAP":
            component_count = len(family_groups)
            leading_records.extend(terminal_records[:component_count])
            for index, (group, wires) in enumerate(
                zip(family_groups, wire_pairs, strict=True)
            ):
                terminal_by_group_id[id(group)] = (
                    terminal_records[component_count + index],
                )
                wire_by_group_id[id(group)] = wires
        else:
            for index, (group, wires) in enumerate(
                zip(family_groups, wire_pairs, strict=True)
            ):
                terminal_by_group_id[id(group)] = tuple(
                    terminal_records[index * 2 : index * 2 + 2]
                )
                wire_by_group_id[id(group)] = wires

    local_starts_with_terminal = [
        bool(terminal_by_group_id.get(id(group), ()))
        for group in ordered_groups
    ]
    local_records: list[bytes] = []
    preserved_rows: list[dict[str, Any]] = []
    preserved_boundary_normalizations = 0
    for index, group in enumerate(ordered_groups):
        group_id = id(group)
        family = _group_family(group)
        if _terminal_eligible_family(group, set(requested)) is None:
            data = bytes(getattr(group, "data", b""))
            next_starts_with_terminal = (
                index + 1 < len(local_starts_with_terminal)
                and local_starts_with_terminal[index + 1]
            )
            emitted = data[:-1] if next_starts_with_terminal else data
            if not emitted:
                raise ValueError(
                    f"Preserved {family} {getattr(group, 'key', '')} has no "
                    "payload bytes before an active terminal unit."
                )
            if next_starts_with_terminal:
                preserved_boundary_normalizations += 1
            local_records.append(emitted)
            preserved_rows.append(
                {
                    "component_key": str(getattr(group, "key", "")),
                    "component_family": family,
                    "packet_size": len(data),
                    "emitted_packet_size": len(emitted),
                    "byte_preserved": emitted == data or emitted == data[:-1],
                    "boundary_tail_normalized": next_starts_with_terminal,
                    "normalized_tail_byte": (
                        f"{data[-1]:02x}" if next_starts_with_terminal else None
                    ),
                }
            )
            continue

        terminals = terminal_by_group_id[group_id]
        patched = patched_by_group_id[group_id]
        first_wire, second_wire = wire_by_group_id[group_id]
        if len(first_wire) != 50 or len(second_wire) != 50:
            raise ValueError(
                f"{family} {getattr(group, 'key', '')} lacks full native wire records."
            )
        local_records.extend(terminals)
        if family != "RESISTOR":
            local_records.append(b"\x00")
        local_records.extend((patched, first_wire))
        next_starts_with_terminal = (
            index + 1 < len(local_starts_with_terminal)
            and local_starts_with_terminal[index + 1]
        )
        local_records.append(
            second_wire[:-1] if next_starts_with_terminal else second_wire
        )

    if not local_records:
        raise ValueError("Native mixed attachment produced no component records.")
    first_local_starts_with_terminal = local_starts_with_terminal[0]
    separator = b"" if first_local_starts_with_terminal else b"\x00"
    new_chunk = (
        original_chunk[:1]
        + b"".join(leading_records)
        + separator
        + b"".join(local_records)
    )
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
    suffix_links_valid = suffixes_unique and all(
        final_chunk.count(struct.pack("<H", suffix) + b"\x01\x00") == 2
        for suffix in suffixes
    )
    terminal_contact_checks = _terminal_pin_contact_checks(family_reports)
    wire_path_checks = _wire_path_contact_checks(family_reports)
    terminal_grid_alignment_valid = all(
        row["terminal_symbol_grid_aligned"]
        and row["terminal_contact_grid_aligned"]
        for row in terminal_contact_checks
    )
    wire_path_contacts_valid = all(row["valid"] for row in wire_path_checks)
    expected_terminals = sum(report["terminal_count"] for report in family_reports)
    expected_wires = sum(report["wire_count"] for report in family_reports)
    preserved_valid = all(
        final_chunk.count(bytes(getattr(group, "data", b""))[:-1]) == 1
        for group in ordered_groups
        if _terminal_eligible_family(group, set(requested)) is None
    )
    report = {
        "stage": "terminal_placer",
        "family_handler": "MIXED/native-wire-v10-grid-snapped",
        "status": "temporary_pending_proteus",
        "attachment_policy": (
            "nearest_grid_terminal_contact_then_wire_to_untouched_exact_pin"
        ),
        "object_order": (
            "native_leading_terminal_arrays_then_original_component_order_with_"
            "family_profile_terminal_component_wire_units"
        ),
        "historical_basis": (
            "accepted_single_family_geometry_plus_absolute_wire_link_rule_"
            "decoded_from_user_accepted_mixed_and_scaled_projects"
        ),
        "wire_requirement_basis": "user_confirmed_terminal_to_pin_wires_are_mandatory",
        "terminal_grid_internal_units": PROTEUS_TERMINAL_GRID,
        "terminal_grid_policy": "nearest_grid_intersection_ties_away_from_zero",
        "component_coordinate_mutation": False,
        "terminal_array_order_policy": "family_profile_order",
        "runtime_circuit_donor_dependency": False,
        "terminal_record_encoder": "embedded_proteus_813_schema",
        "wire_record_encoder": "canonical_50_byte_schema",
        "preserved_control_boundary_policy": (
            "preserve component order and trim only the donor tail byte when "
            "an unsupported preserved packet is immediately followed by an "
            "active terminal unit"
        ),
        "terminal_family_order": list(requested),
        "eligible_families": list(requested),
        "available_accepted_families": [
            family
            for family in ACCEPTED_TERMINAL_FAMILY_ORDER
            if family in available
        ],
        "skipped_families": sorted(
            {
                str(getattr(group, "family", ""))
                for group in ordered_groups
            }
            - set(requested)
        ),
        "patch_component_links": True,
        "active_terminal_links": True,
        "wire_record_emission": True,
        "allow_unlinked_short_wires": False,
        "expected_active_suffix_copies": 2,
        "base_component_stream_covered": True,
        "component_record_order_mutation": False,
        "preserved_control_boundary_normalizations": (
            preserved_boundary_normalizations
        ),
        "single_family_oracle_policy": "same_shared_schema_encoder",
        "terminal_pin_contacts_valid": (
            terminal_grid_alignment_valid and wire_path_contacts_valid
        ),
        "terminal_direct_pin_contacts_valid": all(
            row["coincident"] for row in terminal_contact_checks
        ),
        "terminal_grid_alignment_valid": terminal_grid_alignment_valid,
        "terminal_pin_contact_checks": terminal_contact_checks,
        "wire_path_contacts_valid": wire_path_contacts_valid,
        "wire_path_contact_checks": wire_path_checks,
        "family_reports": family_reports,
        "terminal_suffixes": [f"{suffix:04x}" for suffix in suffixes],
        "terminal_suffixes_unique": suffixes_unique,
        "terminal_suffix_links_valid": suffix_links_valid,
        "terminal_count_added": expected_terminals,
        "wire_count_added": expected_wires,
        "terminalized_component_count": sum(
            report["component_count"] for report in family_reports
        ),
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
            and terminal_grid_alignment_valid
            and wire_path_contacts_valid
            and preserved_valid
            and final_chunk.endswith(b"\xff")
        ),
    }
    return _rebase_terminal_links_to_final_wire_addresses(destination, report)


def _object_chunk_absolute_start(dsn: bytes) -> int:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    object_marker = dsn.find(b"OBJECT DATA", first)
    second = dsn.find(b"ISIS CIRCUIT FILE", first + 1)
    if first < 0 or object_marker < 0 or second < 0:
        raise ValueError("ROOT.DSN does not contain the expected object-data sections.")
    start = object_marker + len(b"OBJECT DATA")
    if start >= second:
        raise ValueError("ROOT.DSN object-data boundaries are reversed.")
    return start


def _wire_rows_from_chunk(
    chunk: bytes,
    *,
    chunk_start: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    cursor = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", cursor)
        if marker < 0:
            return rows
        coordinate_start = marker + 10
        if coordinate_start + 16 > len(chunk):
            raise ValueError(f"WIRE at object offset {marker} is truncated.")
        rows.append(
            {
                "marker_offset": marker,
                "coordinates": struct.unpack(
                    "<iiii",
                    chunk[coordinate_start : coordinate_start + 16],
                ),
                "suffix": (chunk_start + marker - 24) & 0xFFFF,
            }
        )
        cursor = marker + len(b"\x7fWIRE")


def _duplicate_wire_suffix_rows(
    wire_rows: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_suffix: dict[int, list[dict[str, Any]]] = {}
    for row in wire_rows:
        by_suffix.setdefault(int(row["suffix"]), []).append(row)
    return [
        row
        for _suffix, rows in sorted(by_suffix.items())
        if len(rows) > 1
        for row in sorted(rows, key=lambda item: int(item["marker_offset"]))[1:]
    ]


def _bidir_label_records(chunk: bytes) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    cursor = 0
    while True:
        marker = chunk.find(BIDIR_MARKER, cursor)
        if marker < 0:
            return records
        start = marker - 14
        if start < 0 or chunk[start] != 0x10:
            raise ValueError(f"Invalid bidirectional terminal start at marker {marker}.")
        label_length = chunk[start + 30]
        label_start = start + 31
        label_end = label_start + label_length
        if label_end > len(chunk):
            raise ValueError(f"Truncated bidirectional terminal label at {start}.")
        records.append(
            {
                "start": start,
                "marker_offset": marker,
                "label_start": label_start,
                "label_end": label_end,
                "label_length": label_length,
                "label": chunk[label_start:label_end].decode("ascii"),
                "symbol_x": struct.unpack("<i", chunk[start + 1 : start + 5])[0],
                "symbol_y": struct.unpack("<i", chunk[start + 5 : start + 9])[0],
                "angle_tenths": struct.unpack("<I", chunk[start + 9 : start + 13])[0],
                "suffix": struct.unpack("<H", chunk[start + label_length + 97 : start + label_length + 99])[0],
            }
        )
        cursor = marker + 1


def _terminal_contact_xy(record: dict[str, Any]) -> tuple[int, int]:
    angle = int(record["angle_tenths"])
    symbol_x = int(record["symbol_x"])
    symbol_y = int(record["symbol_y"])
    if angle == LEFT_SIDE_ANGLE:
        return symbol_x + TERMINAL_CONTACT_TO_PIN, symbol_y
    if angle == RIGHT_SIDE_ANGLE:
        return symbol_x - TERMINAL_CONTACT_TO_PIN, symbol_y
    return symbol_x, symbol_y


def _component_only_chunk_from_terminalized_chunk(chunk: bytes) -> bytes:
    spans = [
        (int(record["start"]), int(record["start"]) + 101 + int(record["label_length"]))
        for record in _bidir_label_records(chunk)
    ]
    spans.extend(_wire_record_spans(chunk))
    spans = sorted(spans)
    out = bytearray()
    cursor = 0
    for start, end in spans:
        if start < cursor:
            continue
        out.extend(chunk[cursor:start])
        cursor = end
    out.extend(chunk[cursor:])
    if out:
        out[-1] = 0xFF
    return bytes(out)


def _strip_bidir_records_from_chunk(chunk: bytes) -> bytes:
    spans = [
        (int(record["start"]), int(record["start"]) + 101 + int(record["label_length"]))
        for record in _bidir_label_records(chunk)
    ]
    if not spans:
        return chunk
    out = bytearray()
    cursor = 0
    for start, end in sorted(spans):
        if start < cursor:
            continue
        out.extend(chunk[cursor:start])
        cursor = end
    out.extend(chunk[cursor:])
    return bytes(out)


def _ensure_double_ff_object_stream_terminator(chunk: bytes) -> bytes:
    """Return a Proteus object stream with an explicit final FF terminator.

    A component packet may naturally end in byte ``0xff`` because its final
    field is binary data.  That byte is not a reliable object-stream terminator.
    Proteus normalizes the catalogue multi-pin output to an additional final
    ``0xff`` on save, so the shared emitter must write the explicit ``ff ff``
    ending itself to avoid the Bad Object Record warning.
    """

    if chunk.endswith(b"\xff\xff"):
        return chunk
    if chunk.endswith(b"\xff"):
        return chunk + b"\xff"
    return chunk + b"\xff\xff"


def _pin_label_parts(label: str) -> tuple[str, str]:
    normalized = " ".join(label.replace("(", "").replace(")", "").split())
    match = struct_pin_label_match(normalized)
    if match is None:
        return "", normalized
    before = (match.group("before") or "").strip()
    after = (match.group("after") or "").strip()
    return str(match.group("pin")), before or after


def struct_pin_label_match(label: str):
    import re

    return re.match(
        r"^(?:(?P<before>.*?)\s*)?PIN\s*(?P<pin>\d+)(?:\s*(?P<after>.*))?$",
        label,
        flags=re.IGNORECASE,
    )


def analyse_terminalized_donor_pin_geometry(
    project: str | Path,
    *,
    family: str,
) -> dict[str, Any]:
    """Extract component-relative Proteus pin geometry from a terminalized donor.

    Terminals are matched to WIRE records by terminal-contact coordinate, not by
    object order.  The resulting pin coordinates are relative to the
    terminal-stripped component packet bounding-box minimum.
    """

    source = Path(project)
    dsn = read_internal_file(source, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wire_rows = _wire_rows_from_chunk(chunk, chunk_start=0)
    wires_by_endpoint: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in wire_rows:
        x1, y1, x2, y2 = row["coordinates"]
        wires_by_endpoint.setdefault((int(x1), int(y1)), []).append(row)
        wires_by_endpoint.setdefault((int(x2), int(y2)), []).append(row)
    wire_order_by_marker = {
        int(row["marker_offset"]): index
        for index, row in enumerate(
            sorted(wire_rows, key=lambda item: int(item["marker_offset"]))
        )
    }

    component_chunk = _component_only_chunk_from_terminalized_chunk(chunk)
    pairs = layout_coordinate_pairs(component_chunk, family)
    bbox = coordinate_bbox(component_chunk, pairs) if pairs else {
        "min_x": 0,
        "min_y": 0,
        "max_x": 0,
        "max_y": 0,
        "width": 0,
        "height": 0,
    }
    pin_rows: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for terminal in terminals:
        contact = _terminal_contact_xy(terminal)
        candidates = wires_by_endpoint.get(contact, [])
        if not candidates:
            unmatched.append(
                {
                    "label": terminal["label"],
                    "terminal_contact": {"x": contact[0], "y": contact[1]},
                }
            )
            continue
        wire = candidates[0]
        x1, y1, x2, y2 = wire["coordinates"]
        other = (int(x2), int(y2)) if (int(x1), int(y1)) == contact else (int(x1), int(y1))
        pin, signal = _pin_label_parts(str(terminal["label"]))
        pin_key = pin or signal
        if not pin_key:
            pin_key = str(len(pin_rows) + 1)
        side = "left" if int(terminal["angle_tenths"]) == LEFT_SIDE_ANGLE else "right"
        pin_rows[pin_key] = {
            "pin": pin_key,
            "signal": signal,
            "side": side,
            "angle_tenths": int(terminal["angle_tenths"]),
            "pin_x": other[0],
            "pin_y": other[1],
            "x_offset_from_component_bbox_min": other[0] - int(bbox["min_x"]),
            "y_offset_from_component_bbox_min": other[1] - int(bbox["min_y"]),
            "terminal_label": str(terminal["label"]),
            "donor_terminal_suffix": int(terminal["suffix"]),
            "terminal_contact_x": contact[0],
            "terminal_contact_y": contact[1],
            "wire_coordinates": [int(x1), int(y1), int(x2), int(y2)],
            "wire_marker_offset": int(wire["marker_offset"]),
            "wire_order_index": wire_order_by_marker[int(wire["marker_offset"])],
            "evidence": "terminalized_donor_wire_endpoint",
        }

    return {
        "source_project": str(source),
        "family": family,
        "coordinate_frame": "component_bbox_min_from_terminal_stripped_donor_packet",
        "component_bbox": bbox,
        "terminal_count": len(terminals),
        "wire_count": len(wire_rows),
        "pins": dict(sorted(pin_rows.items(), key=lambda item: item[0])),
        "unmatched_terminals": unmatched,
        "valid": not unmatched and bool(pin_rows),
    }


def _pad_bidir_label_before_offset(
    chunk: bytes,
    *,
    before_offset: int,
    pad_char: str = "X",
) -> tuple[bytes, dict[str, Any]]:
    pad = pad_char.encode("ascii")
    if len(pad) != 1:
        raise ValueError("Bidirectional label padding must be one ASCII byte.")
    candidates = [
        record
        for record in _bidir_label_records(chunk)
        if int(record["start"]) < before_offset and int(record["label_length"]) < 255
    ]
    if not candidates:
        raise ValueError(
            "No bidirectional terminal label can be safely lengthened before "
            f"WIRE offset {before_offset}."
        )
    record = max(candidates, key=lambda item: int(item["start"]))
    label_end = int(record["label_end"])
    new_length = int(record["label_length"]) + 1
    old_label = str(record["label"])
    new_label = old_label + pad_char
    patched = (
        chunk[: int(record["start"]) + 30]
        + bytes([new_length])
        + chunk[int(record["label_start"]) : label_end]
        + pad
        + chunk[label_end:]
    )
    return patched, {
        "terminal_start": int(record["start"]),
        "old_label": old_label,
        "new_label": new_label,
        "wire_marker_offset_before_padding": before_offset,
    }


def _update_report_terminal_label(
    report: dict[str, Any],
    *,
    old_label: str,
    new_label: str,
) -> bool:
    for family_report in report.get("family_reports", []):
        for pair in family_report.get("terminal_pairs", []):
            roles = ("left", "right") if "left" in pair else ("input", "output")
            for role in roles:
                terminal = pair.get(role)
                if isinstance(terminal, dict) and terminal.get("label") == old_label:
                    terminal["label"] = new_label
                    return True
    return False


def _wire_record_spans(chunk: bytes) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", cursor)
        if marker < 0:
            return spans
        start = marker - 23
        if start < 0:
            raise ValueError(f"WIRE marker at {marker} starts before object chunk.")
        spans.append((start, marker + 27))
        cursor = marker + len(b"\x7fWIRE")


def _position_in_spans(position: int, spans: Iterable[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in spans)


def _bidir_terminal_suffix_positions(chunk: bytes) -> dict[tuple[str, int], list[int]]:
    positions: dict[tuple[str, int], list[int]] = {}
    for record in _bidir_label_records(chunk):
        size = 101 + int(record["label_length"])
        suffix_position = int(record["start"]) + size - 4
        if suffix_position + 4 > len(chunk):
            raise ValueError(
                f"Truncated bidirectional terminal suffix for {record['label']}."
            )
        suffix = struct.unpack("<H", chunk[suffix_position : suffix_position + 2])[0]
        active = chunk[suffix_position + 2 : suffix_position + 4] == b"\x01\x00"
        if active:
            positions.setdefault((str(record["label"]), suffix), []).append(
                suffix_position
            )
    return positions


def _ensure_unique_final_wire_suffixes(
    destination: Path,
    dsn: bytes,
    chunk: bytes,
    *,
    expected_wire_count: int,
    report: dict[str, Any],
) -> tuple[bytes, bytes, int, list[dict[str, Any]], list[dict[str, Any]]]:
    """Lengthen terminal labels when large object streams alias low-16 WIRE links."""

    label_jitter_events: list[dict[str, Any]] = []
    for iteration in range(1, 4097):
        chunk_start = _object_chunk_absolute_start(dsn)
        wire_rows = _wire_rows_from_chunk(chunk, chunk_start=chunk_start)
        if len(wire_rows) != expected_wire_count:
            raise ValueError(
                f"Terminal/WIRE count mismatch: {expected_wire_count} bindings for "
                f"{len(wire_rows)} WIRE records."
            )
        duplicates = _duplicate_wire_suffix_rows(wire_rows)
        if not duplicates:
            return dsn, chunk, chunk_start, wire_rows, label_jitter_events

        target = max(duplicates, key=lambda row: int(row["marker_offset"]))
        chunk, event = _pad_bidir_label_before_offset(
            chunk,
            before_offset=int(target["marker_offset"]),
        )
        event["iteration"] = iteration
        event["duplicate_suffix"] = f"{int(target['suffix']):04x}"
        event["report_label_updated"] = _update_report_terminal_label(
            report,
            old_label=str(event["old_label"]),
            new_label=str(event["new_label"]),
        )
        label_jitter_events.append(event)
        dsn, _pointers = build_dsn(dsn, dsn, chunk)
        write_project_from_parts(
            destination,
            destination,
            {"ROOT.DSN": dsn},
        )
        dsn = read_internal_file(destination, "ROOT.DSN")
        chunk = _extract_object_chunk(dsn)

    raise ValueError(
        "Could not resolve low-16 WIRE-address collisions after 4096 label jitters."
    )


def _terminal_wire_bindings(report: dict[str, Any]) -> list[dict[str, Any]]:
    family_reports = report.get("family_reports")
    reports = family_reports if isinstance(family_reports, list) else [report]
    bindings: list[dict[str, Any]] = []
    for family_report in reports:
        for row in family_report.get("terminal_pins", []):
            terminal = row.get("terminal")
            wire = row.get("short_wire")
            if not isinstance(terminal, dict) or not isinstance(wire, dict):
                raise ValueError(
                    "Catalogue terminal report lacks terminal/WIRE geometry."
                )
            start = wire.get("start", {})
            end = wire.get("end", {})
            bindings.append(
                {
                    "component_key": row.get("component_key"),
                    "component_family": row.get("component_family"),
                    "role": row.get("pin", {}).get("name"),
                    "old_suffix": int(terminal["suffix"], 16),
                    "coordinates": (
                        int(start["x"]),
                        int(start["y"]),
                        int(end["x"]),
                        int(end["y"]),
                    ),
                    "terminal": terminal,
                }
            )
        for pair in family_report.get("terminal_pairs", []):
            roles = ("left", "right") if "left" in pair else ("input", "output")
            wires = pair.get("short_wires", {})
            for role in roles:
                terminal = pair.get(role)
                wire = wires.get(role)
                if not isinstance(terminal, dict) or not isinstance(wire, dict):
                    raise ValueError(
                        "Terminal report lacks the terminal/WIRE geometry required "
                        "for final link allocation."
                    )
                start = wire.get("start", {})
                end = wire.get("end", {})
                bindings.append(
                    {
                        "component_key": pair.get("component_key"),
                        "component_family": pair.get("component_family"),
                        "role": role,
                        "old_suffix": int(terminal["suffix"], 16),
                        "coordinates": (
                            int(start["x"]),
                            int(start["y"]),
                            int(end["x"]),
                            int(end["y"]),
                        ),
                        "terminal": terminal,
                    }
                )
    return bindings


def _rebase_terminal_links_to_final_wire_addresses(
    output: str | Path,
    report: dict[str, Any],
) -> dict[str, Any]:
    """Allocate active terminal links from final WIRE addresses.

    Proteus 8.13 stores the low 16 bits of the absolute byte immediately before
    the linked 50-byte WIRE record. Since ``\x7fWIRE`` begins at record byte 23,
    the link is ``absolute_object_start + marker_offset - 24``.
    """

    destination = Path(output)
    dsn = read_internal_file(destination, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    bindings = _terminal_wire_bindings(report)
    dsn, chunk, chunk_start, wire_rows, label_jitter_events = (
        _ensure_unique_final_wire_suffixes(
            destination,
            dsn,
            chunk,
            expected_wire_count=len(bindings),
            report=report,
        )
    )

    available_by_coordinates: dict[
        tuple[int, int, int, int],
        list[dict[str, Any]],
    ] = {}
    for row in wire_rows:
        available_by_coordinates.setdefault(row["coordinates"], []).append(row)

    old_suffixes = [binding["old_suffix"] for binding in bindings]
    if len(old_suffixes) != len(set(old_suffixes)):
        raise ValueError("Family-local terminal suffixes collide before final rebasing.")

    allocations: list[dict[str, Any]] = []
    for binding in bindings:
        candidates = available_by_coordinates.get(binding["coordinates"], [])
        if not candidates:
            raise ValueError(
                "No emitted WIRE matches terminal geometry for "
                f"{binding['component_family']} {binding['component_key']} "
                f"{binding['role']}: {binding['coordinates']}."
            )
        wire = candidates.pop(0)
        new_suffix = int(wire["suffix"])
        allocations.append(
            {
                **binding,
                "wire_marker_offset": wire["marker_offset"],
                "wire_absolute_marker": chunk_start + wire["marker_offset"],
                "new_suffix": new_suffix,
            }
        )
    unused_wires = sum(len(rows) for rows in available_by_coordinates.values())
    if unused_wires:
        raise ValueError(f"{unused_wires} emitted WIRE records were not allocated.")
    new_suffixes = [allocation["new_suffix"] for allocation in allocations]
    if len(new_suffixes) != len(set(new_suffixes)):
        raise ValueError("Final WIRE-address terminal suffixes are not unique.")

    terminal_suffix_positions = _bidir_terminal_suffix_positions(chunk)
    all_terminal_suffix_positions = {
        position
        for positions in terminal_suffix_positions.values()
        for position in positions
    }
    wire_spans = _wire_record_spans(chunk)
    patch_positions: dict[int, tuple[int, int]] = {}
    for allocation in allocations:
        old_suffix = allocation["old_suffix"]
        pattern = struct.pack("<H", old_suffix) + b"\x01\x00"
        positions: list[int] = []
        cursor = 0
        while True:
            position = chunk.find(pattern, cursor)
            if position < 0:
                break
            positions.append(position)
            cursor = position + 1
        terminal_label = str(allocation["terminal"]["label"])
        terminal_positions = terminal_suffix_positions.get(
            (terminal_label, old_suffix),
            [],
        )
        if len(terminal_positions) != 1:
            raise ValueError(
                f"Active link {old_suffix:04x} for terminal {terminal_label} has "
                f"{len(terminal_positions)} matching terminal suffix fields; "
                "expected exactly one."
            )
        terminal_position = terminal_positions[0]
        component_candidates = [
            position
            for position in positions
            if position != terminal_position
            and position not in all_terminal_suffix_positions
            and not _position_in_spans(position, wire_spans)
            and position < int(allocation["wire_marker_offset"])
        ]
        if not component_candidates:
            raise ValueError(
                f"Active link {old_suffix:04x} for terminal {terminal_label} has no "
                "structured component pin-link field before its WIRE record."
            )
        component_position = max(component_candidates)
        patch_positions[old_suffix] = (terminal_position, component_position)
        allocation["terminal_suffix_position"] = terminal_position
        allocation["component_link_position"] = component_position

    rebased = bytearray(chunk)
    for allocation in allocations:
        new_value = struct.pack("<H", allocation["new_suffix"])
        for position in patch_positions[allocation["old_suffix"]]:
            rebased[position : position + 2] = new_value
        allocation["terminal"]["suffix"] = f"{allocation['new_suffix']:04x}"

    rebased_chunk = bytes(rebased)
    dsn_chunk_start = _object_chunk_absolute_start(dsn)
    dsn_chunk_end = dsn_chunk_start + len(chunk)
    if dsn[dsn_chunk_start:dsn_chunk_end] != chunk:
        raise ValueError("ROOT.DSN object chunk is not at the decoded absolute offset.")
    rebased_dsn = (
        dsn[:dsn_chunk_start]
        + rebased_chunk
        + dsn[dsn_chunk_end:]
    )
    write_project_from_parts(
        destination,
        destination,
        {"ROOT.DSN": rebased_dsn},
    )
    written_dsn = read_internal_file(destination, "ROOT.DSN")
    written_chunk = _extract_object_chunk(written_dsn)
    if written_chunk != rebased_chunk:
        raise ValueError("Written ROOT.DSN differs from the rebased object stream.")

    report["terminal_suffixes"] = [
        f"{suffix:04x}"
        for suffix in new_suffixes
    ]
    report["terminal_suffixes_unique"] = len(new_suffixes) == len(set(new_suffixes))
    report["terminal_suffix_links_valid"] = all(
        written_chunk[position : position + 4]
        == struct.pack("<H", allocation["new_suffix"]) + b"\x01\x00"
        for allocation in allocations
        for position in patch_positions[allocation["old_suffix"]]
    )
    report["wire_address_label_jitter"] = {
        "applied": bool(label_jitter_events),
        "event_count": len(label_jitter_events),
        "events": label_jitter_events,
    }
    report["object_chunk_size_after"] = len(written_chunk)
    report["object_chunk_double_ff_valid"] = written_chunk.endswith(b"\xff\xff")
    report["bidir_count_after"] = written_chunk.count(BIDIR_MARKER)
    report["wire_count_after"] = written_chunk.count(b"\x7fWIRE")
    report["link_allocation"] = {
        "method": "final_root_dsn_wire_address",
        "formula": "(absolute_object_start + wire_marker_offset - 24) & 0xffff",
        "object_chunk_absolute_start": chunk_start,
        "runtime_donor_dependency": False,
        "allocation_count": len(allocations),
        "allocations": [
            {
                "component_key": allocation["component_key"],
                "component_family": allocation["component_family"],
                "role": allocation["role"],
                "old_suffix": f"{allocation['old_suffix']:04x}",
                "suffix": f"{allocation['new_suffix']:04x}",
                "wire_marker_offset": allocation["wire_marker_offset"],
                "wire_absolute_marker": allocation["wire_absolute_marker"],
                "terminal_suffix_position": allocation["terminal_suffix_position"],
                "component_link_position": allocation["component_link_position"],
                "coordinates": list(allocation["coordinates"]),
            }
            for allocation in allocations
        ],
        "valid": (
            report["terminal_suffixes_unique"]
            and report["terminal_suffix_links_valid"]
        ),
    }
    expected_wire_count = report.get("wire_count_added")
    if not expected_wire_count and report.get("wire_count_rewritten") is not None:
        expected_wire_count = report.get("wire_count_rewritten")
    require_double_ff = report.get("family_handler") == "CATALOGUE/existing-wire-v1"
    report["valid"] = bool(
        report["terminal_suffixes_unique"]
        and report["terminal_suffix_links_valid"]
        and report.get("terminal_grid_alignment_valid", True)
        and report.get("wire_path_contacts_valid", True)
        and report.get("base_component_stream_covered", True)
        and report.get("bidir_count_after") == report.get("terminal_count_added")
        and report.get("wire_count_after") == expected_wire_count
        and written_chunk.endswith(b"\xff")
        and (
            not require_double_ff
            or report.get("object_chunk_double_ff_valid", False)
        )
    )
    return report


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

    The same schema encoder handles single and mixed calls. It consumes the
    beautified packets in their supplied order, then rebases terminal links
    from the final ROOT.DSN WIRE addresses.
    """

    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("Shared terminal attachment requires selected component groups.")
    families = {_group_family(group) for group in groups}
    accepted = set(ACCEPTED_TERMINAL_FAMILY_ORDER)
    available_eligible_families = tuple(
        dict.fromkeys(
            family
            for group in groups
            for family in (_terminal_eligible_family(group, accepted),)
            if family is not None
        )
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
            for family in available_eligible_families
            if family in requested_terminal_families
        )
    preserved_groups = tuple(
        sorted(
            (
                group
                for group in groups
                if _terminal_eligible_family(group, set(eligible_families)) is None
            ),
            key=lambda group: int(getattr(group, "start", 0)),
        )
    )

    if len(families) == 1 and eligible_families and not preserved_groups:
        if label_prefix is not None or suffix_start is not None:
            report = _attach_single_family_bidir_terminals_to_project(
                project,
                output,
                groups,
                label_prefix=label_prefix,
                suffix_start=suffix_start,
            )
        else:
            report = attach_mixed_native_bidir_terminals_to_project(
                project,
                output,
                groups,
                terminal_families=eligible_families,
            )
            return report
        return _rebase_terminal_links_to_final_wire_addresses(output, report)
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
                    "component_family": _group_family(group),
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

    return attach_mixed_native_bidir_terminals_to_project(
        source,
        destination,
        groups,
        terminal_families=eligible_families,
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
