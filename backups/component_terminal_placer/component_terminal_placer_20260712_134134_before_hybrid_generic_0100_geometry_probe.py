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
DONOR_TERMINAL_WIRE_ENDPOINT_TOLERANCE = PROTEUS_TERMINAL_GRID
LEFT_SIDE_ANGLE = 1800
RIGHT_SIDE_ANGLE = 0
COMPONENT_PIN_LINK_TRAILERS = (b"\x01\x00", b"\x02\x00")
RESISTOR_PIN_SPAN = 1_270_000
CAP_PIN_HALF_SPAN = 508_000
CAP_TERMINAL_SYMBOL_TO_PIN = 254_000
CAP_ELEC_PIN_HALF_SPAN = 508_000
CAP_ELEC_TERMINAL_SYMBOL_TO_PIN = 254_000
INDUCTOR_PIN_HALF_SPAN = 762_000
INDUCTOR_TERMINAL_SYMBOL_TO_PIN = 254_000
GENERIC_TWO_PIN_HALF_SPAN = 508_000
GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN = 254_000
GENERIC_TWO_PIN_DEFAULT_GEOMETRY = {
    # Derived from the actual Proteus Ctrl+S oracle for the accepted all-native
    # mixed file.  The symbol contact remains one half-grid left/right of the
    # body while common diode-family left pins sit another half-grid inward.
    "left_pin_offset": (-254_000, 0),
    "right_pin_offset": (508_000, 0),
    "left_terminal_contact_offset": (-508_000, 0),
    "right_terminal_contact_offset": (508_000, 0),
}
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
        "pin_geometry": {
            "left_pin_offset": (0, -254_000),
            "right_pin_offset": (0, 508_000),
            "left_terminal_contact_offset": (-508_000, 0),
            "right_terminal_contact_offset": (508_000, 0),
        },
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
        "pin_geometry": {
            "left_pin_offset": (0, 508_000),
            "right_pin_offset": (0, -508_000),
            "left_terminal_contact_offset": (-508_000, 0),
            "right_terminal_contact_offset": (508_000, 0),
        },
    },
    "FUSE": {
        "label_prefix": "F",
        "suffix_base": 0x6600,
        "left_pin_hint": "pin:1",
        "right_pin_hint": "pin:2",
        "terminal_contact_outward_grid_steps": 1,
        "pin_geometry": {
            "left_pin_offset": (762_000, 0),
            "right_pin_offset": (-762_000, 0),
            "left_terminal_contact_offset": (-508_000, 0),
            "right_terminal_contact_offset": (508_000, 0),
        },
    },
    "SWITCH": {
        "label_prefix": "W",
        "suffix_base": 0x6800,
        "left_pin_hint": "pin:1",
        "right_pin_hint": "pin:2",
        "terminal_contact_outward_grid_steps": 1,
        "pin_geometry": {
            "left_pin_offset": (-508_000, 0),
            "right_pin_offset": (762_000, 0),
            "left_terminal_contact_offset": (-508_000, 0),
            "right_terminal_contact_offset": (508_000, 0),
        },
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
    "SWITCH",
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
    "SWITCH",
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


def _terminal_at_explicit_grid_contact(
    terminal: TerminalSpec,
    *,
    contact_x: int,
    contact_y: int,
) -> tuple[TerminalSpec, int, int]:
    """Place a terminal from donor-derived contact coordinates.

    Catalogue multi-pin donors may prove a terminal contact that is not the
    nearest generic outward contact from the exact pin endpoint.  Keep the
    contact on the Proteus grid, derive the symbol from the terminal angle, and
    let the short WIRE run from that proven contact to the exact pin.
    """

    contact_x = snap_to_proteus_terminal_grid(contact_x)
    contact_y = snap_to_proteus_terminal_grid(contact_y)
    if terminal.angle_tenths == LEFT_SIDE_ANGLE:
        symbol_x = contact_x - TERMINAL_CONTACT_TO_PIN
    elif terminal.angle_tenths == RIGHT_SIDE_ANGLE:
        symbol_x = contact_x + TERMINAL_CONTACT_TO_PIN
    else:
        raise ValueError(
            f"Explicit grid terminal placement does not support angle "
            f"{terminal.angle_tenths}."
        )
    return (
        replace(
            terminal,
            symbol_x=symbol_x,
            symbol_y=contact_y,
            attachment_policy=(
                "donor_contact_grid_with_short_wire_to_exact_pin"
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
    role_aliases = (
        ("NONINVERTINGINPUT", "INP"),
        ("INVERTINGINPUT", "INN"),
        ("ADJUST", "ADJ"),
        ("OUTPUT", "OUT"),
        ("INPUT", "IN"),
        ("GROUND", "GND"),
        ("COMMON", "COM"),
        ("RESET", "RST"),
        ("CLOCK", "CLK"),
        ("ENABLE", "EN"),
    )
    if role_token and role_token != "UNKNOWN":
        compact_role = next(
            (alias for token, alias in role_aliases if token in role_token),
            role_token[:4],
        )
        return f"{key_token}{compact_role}"[:16]
    return f"{key_token}PIN{pin_token}"[:60]


def _catalogue_donor_label(
    component_key: str,
    pin: str,
    role: str,
    raw_pin_geometry: dict[str, Any],
    *,
    use_donor_terminal_labels: bool = True,
) -> str:
    if use_donor_terminal_labels:
        for key in ("terminal_label", "donor_terminal_label"):
            value = raw_pin_geometry.get(key)
            if value:
                return str(value)
    return _catalogue_terminal_label(component_key, pin, role)


def _catalogue_link_trailer(raw_pin_geometry: dict[str, Any]) -> bytes:
    trailer_hex = str(
        raw_pin_geometry.get("terminal_link_trailer")
        or raw_pin_geometry.get("component_link_trailer")
        or COMPONENT_PIN_LINK_TRAILERS[0].hex()
    )
    trailer = bytes.fromhex(trailer_hex)
    if trailer not in COMPONENT_PIN_LINK_TRAILERS:
        raise ValueError(f"Unsupported catalogue terminal link trailer {trailer_hex!r}.")
    return trailer


def _transform_catalogue_wire_coordinates(
    raw_pin_geometry: dict[str, Any],
    *,
    component_anchor: dict[str, Any] | None,
    donor_anchor: dict[str, Any] | None,
) -> tuple[tuple[int, ...], tuple[int, int] | None] | None:
    raw_coordinates = raw_pin_geometry.get("wire_unit_coordinates")
    if raw_coordinates is None:
        raw_coordinates = raw_pin_geometry.get("wire_coordinates")
    if (
        not isinstance(raw_coordinates, (list, tuple))
        or len(raw_coordinates) < 4
        or len(raw_coordinates) % 2 != 0
        or component_anchor is None
        or not isinstance(donor_anchor, dict)
        or donor_anchor.get("x") is None
        or donor_anchor.get("y") is None
    ):
        return None
    dx = int(component_anchor["x"]) - int(donor_anchor["x"])
    dy = int(component_anchor["y"]) - int(donor_anchor["y"])
    coordinates = tuple(
        int(value) + (dx if index % 2 == 0 else dy)
        for index, value in enumerate(raw_coordinates)
    )
    matched_x = raw_pin_geometry.get("matched_wire_endpoint_x")
    matched_y = raw_pin_geometry.get("matched_wire_endpoint_y")
    matched = (
        (int(matched_x) + dx, int(matched_y) + dy)
        if matched_x is not None and matched_y is not None
        else None
    )
    return coordinates, matched


def _retarget_catalogue_wire_coordinates(
    coordinates: Iterable[int],
    *,
    transformed_terminal_contact: tuple[int, int],
    target_terminal_contact: tuple[int, int],
    target_pin_contact: tuple[int, int],
) -> tuple[tuple[int, ...], tuple[int, int]]:
    """Keep donor polyline topology while fitting current terminal and pin contacts."""

    points = list(_wire_coordinate_points(coordinates))
    if len(points) < 2:
        raise ValueError("Catalogue WIRE retargeting requires at least two points.")
    first_distance = abs(points[0][0] - transformed_terminal_contact[0]) + abs(
        points[0][1] - transformed_terminal_contact[1]
    )
    last_distance = abs(points[-1][0] - transformed_terminal_contact[0]) + abs(
        points[-1][1] - transformed_terminal_contact[1]
    )
    terminal_index = 0 if first_distance <= last_distance else len(points) - 1
    pin_index = len(points) - 1 if terminal_index == 0 else 0
    old_terminal = points[terminal_index]
    old_pin = points[pin_index]
    retargeted: list[tuple[int, int]] = []
    for index, (x, y) in enumerate(points):
        if index == terminal_index:
            retargeted.append(target_terminal_contact)
            continue
        if index == pin_index:
            retargeted.append(target_pin_contact)
            continue
        if old_pin[0] != old_terminal[0]:
            if x == old_pin[0]:
                x = target_pin_contact[0]
            elif x == old_terminal[0]:
                x = target_terminal_contact[0]
        if old_pin[1] != old_terminal[1]:
            if y == old_pin[1]:
                y = target_pin_contact[1]
            elif y == old_terminal[1]:
                y = target_terminal_contact[1]
        retargeted.append((x, y))
    flattened = tuple(value for point in retargeted for value in point)
    return flattened, target_terminal_contact


def _wire_coordinate_points(coordinates: Iterable[int]) -> tuple[tuple[int, int], ...]:
    values = tuple(int(value) for value in coordinates)
    if len(values) < 4 or len(values) % 2 != 0:
        raise ValueError("WIRE coordinate list must contain at least two points.")
    return tuple(
        (values[index], values[index + 1])
        for index in range(0, len(values), 2)
    )


def _opposite_polyline_endpoint(
    coordinates: Iterable[int],
    matched_endpoint: tuple[int, int],
) -> tuple[int, int]:
    """Return the component-side endpoint opposite a terminal contact.

    Proteus donor WIRE records are not always single-segment lines.  POT-HG
    ground and LM317T adjust use routed polylines.  The terminal contact is
    normally one end of that polyline, so the component pin is the opposite
    end.  If donor evidence ever points at a middle vertex, fall back to the
    farther outer endpoint instead of selecting a neighbouring segment vertex.
    """

    points = _wire_coordinate_points(coordinates)
    matched = (int(matched_endpoint[0]), int(matched_endpoint[1]))
    if matched == points[0]:
        return points[-1]
    if matched == points[-1]:
        return points[0]
    first_distance = abs(points[0][0] - matched[0]) + abs(points[0][1] - matched[1])
    last_distance = abs(points[-1][0] - matched[0]) + abs(points[-1][1] - matched[1])
    return points[0] if first_distance >= last_distance else points[-1]


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


def _is_length_prefixed_text_marker(
    data: bytes,
    marker_offset: int,
    marker_length: int,
) -> bool:
    return (
        marker_offset >= 2
        and data[marker_offset - 2] == 0xFF
        and data[marker_offset - 1] == marker_length
    )


def _is_embedded_ascii_marker(
    data: bytes,
    marker_offset: int,
    marker_length: int,
) -> bool:
    before = data[marker_offset - 1] if marker_offset > 0 else 0
    return 48 <= before <= 57 or 65 <= before <= 90 or 97 <= before <= 122


def _component_marker_anchors_for_catalogue(
    data: bytes,
    family: str,
) -> list[dict[str, Any]]:
    """Return strict marker-body coordinates for a placed component.

    Several multi-pin native packets contain off-body length-prefixed text and
    stale donor coordinates.  A broad bbox over all parsed coordinate pairs can
    therefore select the wrong origin.  The component marker followed by two
    signed coordinates is a narrower symbol/body anchor, but the same marker
    text can also appear inside visible labels.  This helper rejects those
    label/embedded occurrences and returns only body-marker anchors.
    """

    marker = str(family).encode("ascii", errors="ignore")
    if not marker:
        return []
    anchors: list[dict[str, Any]] = []
    offset = 0
    while True:
        marker_offset = data.find(marker, offset)
        if marker_offset < 0:
            break
        x_offset = marker_offset + len(marker)
        y_offset = x_offset + 4
        if (
            y_offset + 4 <= len(data)
            and not _is_length_prefixed_text_marker(data, marker_offset, len(marker))
            and not _is_embedded_ascii_marker(data, marker_offset, len(marker))
        ):
            x_value = struct.unpack("<i", data[x_offset : x_offset + 4])[0]
            y_value = struct.unpack("<i", data[y_offset : y_offset + 4])[0]
            if (
                -700_000_000 <= x_value <= 700_000_000
                and -700_000_000 <= y_value <= 700_000_000
                and x_value % 10 == 0
                and y_value % 10 == 0
                and (abs(x_value) >= 1_000_000 or abs(y_value) >= 1_000_000)
            ):
                anchors.append(
                    {
                        "marker": str(family),
                        "marker_offset": marker_offset,
                        "x_offset": x_offset,
                        "y_offset": y_offset,
                        "x": x_value,
                        "y": y_value,
                    }
                )
        offset = marker_offset + 1
    return anchors


def _component_marker_anchor_for_catalogue(
    data: bytes,
    family: str,
) -> dict[str, Any] | None:
    """Return the last strict marker-body coordinate for a placed component."""

    anchors = _component_marker_anchors_for_catalogue(data, family)
    return anchors[-1] if anchors else None


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
    use_donor_terminal_labels: bool = True,
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
        component_data = _component_only_chunk_from_terminalized_chunk(data)
        anchor_cache: dict[str, list[dict[str, Any]]] = {}
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
            anchor_family = str(
                raw_pin_geometry.get("anchor_family")
                or geometry.get("anchor_family")
                or family
            )
            if anchor_family not in anchor_cache:
                anchor_cache[anchor_family] = _component_marker_anchors_for_catalogue(
                    component_data,
                    anchor_family,
                )
            component_anchors = anchor_cache[anchor_family]
            component_anchor: dict[str, Any] | None
            anchor_index = raw_pin_geometry.get("component_anchor_index")
            if anchor_index is None:
                anchor_index = raw_pin_geometry.get("subpart_anchor_index")
            if isinstance(anchor_index, int):
                if 0 <= anchor_index < len(component_anchors):
                    component_anchor = component_anchors[anchor_index]
                else:
                    missing_geometry.append(
                        {
                            "component_key": key,
                            "component_family": family,
                            "pin": pin.name,
                            "reason": "component_anchor_index_out_of_range",
                        }
                    )
                    continue
            else:
                component_anchor = component_anchors[-1] if component_anchors else None
            if (
                component_anchor is not None
                and "x_offset_from_component_anchor" in raw_pin_geometry
                and "y_offset_from_component_anchor" in raw_pin_geometry
            ):
                pin_x = int(component_anchor["x"]) + int(
                    raw_pin_geometry["x_offset_from_component_anchor"]
                )
                pin_y = int(component_anchor["y"]) + int(
                    raw_pin_geometry["y_offset_from_component_anchor"]
                )
                coordinate_source = (
                    "component_marker_anchor_offset_existing_wire_identity"
                    if existing_wire is not None
                    else "component_marker_anchor_offset"
                )
            else:
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
            snap_axes_raw = raw_pin_geometry.get("pin_endpoint_snap_axes", ())
            if isinstance(snap_axes_raw, str):
                snap_axes = {snap_axes_raw.lower()}
            else:
                snap_axes = {str(axis).lower() for axis in snap_axes_raw}
            snapped_axes: list[str] = []
            if "x" in snap_axes:
                pin_x = snap_to_proteus_terminal_grid(pin_x)
                snapped_axes.append("x")
            if "y" in snap_axes:
                pin_y = snap_to_proteus_terminal_grid(pin_y)
                snapped_axes.append("y")
            if snapped_axes:
                coordinate_source += "_pin_endpoint_snap_" + "".join(snapped_axes)
            explicit_contact: tuple[int, int] | None = None
            terminal_contact_source = "generic_grid_contact"
            donor_anchor = geometry.get("component_anchor")
            if (
                component_anchor is not None
                and isinstance(donor_anchor, dict)
                and raw_pin_geometry.get("terminal_contact_x") is not None
                and raw_pin_geometry.get("terminal_contact_y") is not None
                and donor_anchor.get("x") is not None
                and donor_anchor.get("y") is not None
            ):
                explicit_contact = (
                    int(component_anchor["x"])
                    + int(raw_pin_geometry["terminal_contact_x"])
                    - int(donor_anchor["x"]),
                    int(component_anchor["y"])
                    + int(raw_pin_geometry["terminal_contact_y"])
                    - int(donor_anchor["y"]),
                )
                terminal_contact_source = "donor_terminal_contact_anchor_offset"
            terminal = TerminalSpec(
                label=_catalogue_donor_label(
                    key,
                    pin.name,
                    pin.role,
                    raw_pin_geometry,
                    use_donor_terminal_labels=use_donor_terminal_labels,
                ),
                symbol_x=pin_x,
                symbol_y=pin_y,
                angle_tenths=angle,
                suffix=suffix & 0xFFFF,
                component_key=key,
                component_family=family,
                pin_hint=f"{pin.name}:{pin.role}",
                attachment_policy="catalogue_pin_geometry_grid_short_wire",
            )
            if explicit_contact is not None:
                terminal, wire_start_x, wire_start_y = (
                    _terminal_at_explicit_grid_contact(
                        terminal,
                        contact_x=explicit_contact[0],
                        contact_y=explicit_contact[1],
                    )
                )
            else:
                terminal, wire_start_x, wire_start_y = _terminal_at_grid_contact(
                    terminal,
                    pin_x=pin_x,
                    pin_y=pin_y,
                    outward_grid_steps=int(
                        raw_pin_geometry.get(
                            "terminal_contact_outward_grid_steps",
                            geometry.get("terminal_contact_outward_grid_steps", 1),
                        )
                    ),
                )
            wire_end_x = pin_x
            wire_end_y = pin_y
            wire_terminal_contact = {"x": wire_start_x, "y": wire_start_y}
            wire_pin_contact = {"x": pin_x, "y": pin_y}
            wire_coordinates_policy = str(
                raw_pin_geometry.get(
                    "wire_coordinates_policy",
                    geometry.get("wire_coordinates_policy", "donor_coordinates"),
                )
            )
            if wire_coordinates_policy == "computed_terminal_contact_to_pin":
                transformed_wire = None
                terminal_contact_source = (
                    f"{terminal_contact_source}_computed_wire_to_pin"
                )
            else:
                transformed_wire = _transform_catalogue_wire_coordinates(
                    raw_pin_geometry,
                    component_anchor=component_anchor,
                    donor_anchor=donor_anchor if isinstance(donor_anchor, dict) else None,
                )
            if transformed_wire is not None:
                wire_coordinates, matched_wire_endpoint = transformed_wire
                if bool(
                    raw_pin_geometry.get(
                        "wire_coordinates_retarget_to_current_contacts",
                        geometry.get(
                            "wire_coordinates_retarget_to_current_contacts",
                            False,
                        ),
                    )
                ):
                    transformed_terminal_contact = (
                        int(explicit_contact[0]),
                        int(explicit_contact[1]),
                    ) if explicit_contact is not None else (
                        int(wire_start_x),
                        int(wire_start_y),
                    )
                    wire_coordinates, matched_wire_endpoint = (
                        _retarget_catalogue_wire_coordinates(
                            wire_coordinates,
                            transformed_terminal_contact=transformed_terminal_contact,
                            target_terminal_contact=(
                                int(wire_start_x),
                                int(wire_start_y),
                            ),
                            target_pin_contact=(int(pin_x), int(pin_y)),
                        )
                    )
                endpoints = _wire_coordinate_points(wire_coordinates)
                wire_start_x, wire_start_y = endpoints[0]
                wire_end_x, wire_end_y = endpoints[-1]
                if matched_wire_endpoint in endpoints:
                    wire_terminal_contact = {
                        "x": matched_wire_endpoint[0],
                        "y": matched_wire_endpoint[1],
                    }
                    opposite_endpoint = _opposite_polyline_endpoint(
                        wire_coordinates,
                        matched_wire_endpoint,
                    )
                    wire_pin_contact = {
                        "x": opposite_endpoint[0],
                        "y": opposite_endpoint[1],
                    }
                else:
                    wire_pin_contact = {"x": pin_x, "y": pin_y}
                wire_record = _build_catalogue_wire_unit(wire_coordinates)
            else:
                wire_coordinates = (wire_start_x, wire_start_y, wire_end_x, wire_end_y)
                wire_record = _build_native_short_wire(
                    wire_start_x,
                    wire_start_y,
                    wire_end_x,
                    wire_end_y,
                )
            terminal_dict = terminal.as_dict()
            terminal_dict["link_trailer"] = _catalogue_link_trailer(
                raw_pin_geometry
            ).hex()
            terminal_plans.append(
                {
                    "terminal": terminal_dict,
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
                        "end": {"x": wire_end_x, "y": wire_end_y},
                        "coordinates": list(wire_coordinates),
                        "terminal_contact": wire_terminal_contact,
                        "pin_contact": wire_pin_contact,
                        "record": wire_record.hex(),
                    },
                    "catalogue_geometry": dict(raw_pin_geometry),
                    "component_bbox": dict(bbox),
                    "component_anchor": (
                        dict(component_anchor) if component_anchor is not None else None
                    ),
                    "coordinate_source": coordinate_source,
                    "terminal_contact_source": terminal_contact_source,
                    "existing_wire": (
                        {
                            "wire_order_index": wire_order_index,
                            "marker_offset": int(existing_wire["marker_offset"]),
                            "coordinates": list(existing_wire["coordinates"]),
                        }
                        if existing_wire is not None
                        else None
                    ),
                    "wire_order_index": (
                        int(wire_order_index)
                        if isinstance(wire_order_index, int)
                        else None
                    ),
                }
            )
            suffix += 1
    terminal_plans.sort(
        key=lambda row: (
            1_000_000
            if row.get("wire_order_index") is None
            else int(row["wire_order_index"]),
            str(row.get("component_key", "")),
            str(row.get("pin", {}).get("name", "")),
        )
    )
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
    candidates: list[int] = []
    suffix = struct.pack("<H", old_suffix & 0xFFFF)
    for trailer in COMPONENT_PIN_LINK_TRAILERS:
        pattern = suffix + trailer
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
            f"WIRE offset {before_offset} using known link trailers."
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
    for trailer in COMPONENT_PIN_LINK_TRAILERS:
        cursor = 0
        while True:
            position = data.find(trailer, cursor)
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


def _patch_component_link_from_catalogue_offset(
    data: bytes,
    *,
    new_suffix: int,
    offset_from_component_end: int,
    trailer_hex: str | None = None,
) -> tuple[bytes, int, int, bytes]:
    """Patch a donor-proven bare-packet link slot.

    Some main/component-placer donor packets contain the same reserved pin-link
    slots as the terminalized donor evidence, but they do not carry old terminal
    suffixes or WIRE records.  The catalogue stores those slots as offsets from
    the end of the bare component packet so reference-length shifts do not make
    the absolute positions brittle.
    """

    position = len(data) + int(offset_from_component_end)
    return _patch_component_link_at_position(
        data,
        new_suffix=new_suffix,
        position=position,
        trailer_hex=trailer_hex,
    )


def _patch_component_link_at_position(
    data: bytes,
    *,
    new_suffix: int,
    position: int,
    trailer_hex: str | None = None,
) -> tuple[bytes, int, int, bytes]:
    """Patch a component pin-link field at an absolute packet/block offset."""

    trailer = (
        bytes.fromhex(str(trailer_hex))
        if trailer_hex is not None
        else COMPONENT_PIN_LINK_TRAILERS[0]
    )
    if trailer not in COMPONENT_PIN_LINK_TRAILERS:
        raise ValueError(
            f"Unsupported component pin-link trailer {trailer.hex()} from catalogue."
        )
    if position < 0 or position + 4 > len(data):
        raise ValueError(
            "Catalogue component pin-link position is outside the component packet: "
            f"position={position}, packet_size={len(data)}."
        )
    old_suffix = struct.unpack("<H", data[position : position + 2])[0]
    patched = bytearray(data)
    patched[position : position + 4] = (
        struct.pack("<H", new_suffix & 0xFFFF) + trailer
    )
    return bytes(patched), position, old_suffix, trailer


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
    use_donor_terminal_labels: bool = True,
    allow_progressive_scaling: bool = False,
) -> dict[str, Any]:
    """Attach catalogue-backed multi-pin terminals using placed WIRE skeletons.

    The component placer may emit multi-pin native packets that already contain
    donor-derived component pin-link fields and zero-length WIRE records, but no
    `$TERBIDIR` records.  This shared path rewrites those WIRE records into the
    accepted grid-contact short-wire geometry, inserts active terminal records
    immediately before each component packet, and then rebases both terminal and
    component pin links from final ROOT.DSN WIRE addresses.

    ``allow_progressive_scaling`` is intentionally opt-in.  A profile's
    donor-proven component count remains the default safety boundary; a larger
    catalogue-declared progressive-validation cap is available only for a
    user-requested, independently gated scaling experiment.
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
    trailing_attachment_records: list[bytes] = []
    object_stream_finalizers: set[str] = set()
    clean_packet_attachment_orders: set[str] = set()
    terminal_leading_block_count = 0
    family_reports: list[dict[str, Any]] = []
    preserved_rows: list[dict[str, Any]] = []
    suffix = suffix_start
    terminalized_count = 0
    skipped_group_indices: set[int] = set()
    for group_index, group in enumerate(ordered_groups):
        if group_index in skipped_group_indices:
            continue
        family = _group_family(group)
        key = _group_key(group)
        if (
            family == "7SEG-COM-CAT-BLUE"
            and (requested is None or family in requested)
        ):
            raise ValueError(
                "7SEG catalogue display terminalization is disabled at this "
                "checkpoint. The V10 display/link-offset emitter generated "
                "Proteus-rejected files; D20/display grouping needs a "
                "donor-native accepted route before re-enabling."
            )
            cathode_groups: list[Any] = []
            block_group_indices: list[int] = []
            cursor = group_index
            while (
                cursor < len(ordered_groups)
                and _group_family(ordered_groups[cursor]) == "7SEG-COM-CAT-BLUE"
            ):
                cathode_groups.append(ordered_groups[cursor])
                block_group_indices.append(cursor)
                cursor += 1
            anode_groups: list[Any] = []
            while (
                cursor < len(ordered_groups)
                and _group_family(ordered_groups[cursor]) == "7SEG-COM-AN-BLUE"
                and _group_key(ordered_groups[cursor]) != "DISPLAY_ANODE_SENTINEL"
            ):
                anode_groups.append(ordered_groups[cursor])
                block_group_indices.append(cursor)
                cursor += 1
            sentinel_group = (
                ordered_groups[cursor]
                if cursor < len(ordered_groups)
                and _group_key(ordered_groups[cursor]) == "DISPLAY_ANODE_SENTINEL"
                else None
            )
            if sentinel_group is not None:
                block_group_indices.append(cursor)
            if cathode_groups and (sentinel_group is not None or anode_groups):
                block_groups = [
                    *cathode_groups,
                    *anode_groups,
                    *([sentinel_group] if sentinel_group is not None else []),
                ]
                block_data = b"".join(bytes(getattr(item, "data", b"")) for item in block_groups)
                patched_block = block_data
                terminal_records: list[bytes] = []
                appended_wire_records: list[bytes] = []
                block_family_reports: list[dict[str, Any]] = []
                base_offset = 0
                block_terminalized_count = 0
                for display_group in block_groups:
                    display_key = _group_key(display_group)
                    display_family = _group_family(display_group)
                    display_data = bytes(getattr(display_group, "data", b""))
                    terminalize_display = (
                        display_key != "DISPLAY_ANODE_SENTINEL"
                        and display_family in {"7SEG-COM-CAT-BLUE", "7SEG-COM-AN-BLUE"}
                        and (requested is None or display_family in requested)
                    )
                    if not terminalize_display:
                        base_offset += len(display_data)
                        continue
                    profile = catalog.get_profile(display_family)
                    geometry = (
                        profile.proteus.get("pin_geometry", {})
                        if profile is not None
                        else {}
                    )
                    pins = geometry.get("pins", {}) if isinstance(geometry, dict) else {}
                    if profile is None or not isinstance(pins, dict) or not pins:
                        raise ValueError(
                            f"{display_family} display block lacks catalogue pin geometry."
                        )
                    planning_data = _strip_bidir_records_from_chunk(display_data)
                    planning_group = replace(display_group, data=planning_data)
                    plan = plan_catalogue_pin_bidir_terminals(
                        [planning_group],
                        catalog=catalog,
                        suffix_start=suffix,
                        use_donor_terminal_labels=use_donor_terminal_labels,
                    )
                    if not plan["valid"]:
                        raise ValueError(
                            f"Catalogue terminal plan for {display_family} {display_key} "
                            f"is incomplete: {plan['missing_geometry']}."
                        )
                    terminal_pins: list[dict[str, Any]] = []
                    group_wire_count = 0
                    for row in plan["terminal_plans"]:
                        pin_name = str(row["pin"]["name"])
                        raw_geometry = pins[pin_name]
                        raw_link_offset = raw_geometry.get(
                            "component_link_offset_from_component_end"
                        )
                        if raw_link_offset is None:
                            raise ValueError(
                                f"{display_family} {display_key} pin {pin_name} lacks "
                                "catalogue component-link offset."
                            )
                        component_link_position = (
                            base_offset + len(planning_data) + int(raw_link_offset)
                        )
                        temporary_suffix = suffix & 0xFFFF
                        suffix += 1
                        patched_block, component_link_position, old_suffix, trailer = (
                            _patch_component_link_at_position(
                                patched_block,
                                new_suffix=temporary_suffix,
                                position=component_link_position,
                                trailer_hex=raw_geometry.get("component_link_trailer"),
                            )
                        )
                        short_wire = row["short_wire"]
                        start = short_wire["start"]
                        end = short_wire["end"]
                        appended_wire_records.append(bytes.fromhex(short_wire["record"]))
                        group_wire_count += 1
                        terminal_dict = dict(row["terminal"])
                        terminal_dict["suffix"] = f"{temporary_suffix:04x}"
                        terminal_link_trailer = bytes.fromhex(
                            str(
                                terminal_dict.get(
                                    "link_trailer",
                                    COMPONENT_PIN_LINK_TRAILERS[0].hex(),
                                )
                            )
                        )
                        if terminal_link_trailer not in COMPONENT_PIN_LINK_TRAILERS:
                            raise ValueError(
                                f"{display_family} {display_key} pin {pin_name} "
                                f"uses unsupported terminal link trailer "
                                f"{terminal_link_trailer.hex()}."
                            )
                        terminal_records.append(
                            build_bidir_record(
                                terminal_templates,
                                label=str(terminal_dict["label"]),
                                symbol_x=int(terminal_dict["symbol_x"]),
                                symbol_y=int(terminal_dict["symbol_y"]),
                                angle_tenths=int(terminal_dict["angle_tenths"]),
                                suffix=temporary_suffix,
                                active_link=True,
                            )[:-2]
                            + terminal_link_trailer
                        )
                        terminal_pins.append(
                            {
                                "component_key": display_key,
                                "component_family": display_family,
                                "pin": row["pin"],
                                "terminal": terminal_dict,
                                "short_wire": {
                                    "start": dict(start),
                                    "end": dict(end),
                                    **(
                                        {"coordinates": list(short_wire["coordinates"])}
                                        if isinstance(
                                            short_wire.get("coordinates"),
                                            (list, tuple),
                                        )
                                        else {}
                                    ),
                                    **(
                                        {
                                            "terminal_contact": dict(
                                                short_wire["terminal_contact"]
                                            )
                                        }
                                        if isinstance(
                                            short_wire.get("terminal_contact"),
                                            dict,
                                        )
                                        else {}
                                    ),
                                    **(
                                        {"pin_contact": dict(short_wire["pin_contact"])}
                                        if isinstance(
                                            short_wire.get("pin_contact"),
                                            dict,
                                        )
                                        else {}
                                    ),
                                },
                                "catalogue_geometry": dict(raw_geometry),
                                "component_bbox": dict(row.get("component_bbox", {})),
                                "component_anchor": (
                                    dict(row["component_anchor"])
                                    if isinstance(row.get("component_anchor"), dict)
                                    else None
                                ),
                                "existing_wire": None,
                                "old_suffix": f"{old_suffix:04x}",
                                "temporary_suffix": f"{temporary_suffix:04x}",
                                "component_link_position": component_link_position,
                                "existing_wire_marker_offset": None,
                                "component_link_trailer": trailer.hex(),
                                "coordinate_source": row["coordinate_source"],
                                "terminal_contact_source": row.get(
                                    "terminal_contact_source",
                                    "generic_grid_contact",
                                ),
                            }
                        )
                    block_family_reports.append(
                        {
                            "family_handler": f"{display_family}/catalogue-display-block-link-offset-wire-v1",
                            "component_key": display_key,
                            "component_family": display_family,
                            "component_count": 1,
                            "combined_infrastructure": {
                                "block_group_keys": [
                                    _group_key(item) for item in block_groups
                                ],
                                "reason": (
                                    "common-cathode display link fields can cross "
                                    "the following display/sentinel packet boundary; "
                                    "immediately following anode display packets are "
                                    "kept in the same block when present"
                                ),
                            },
                            "terminal_count": len(terminal_pins),
                            "wire_count": group_wire_count,
                            "wire_count_added": group_wire_count,
                            "wire_count_rewritten": 0,
                            "stripped_existing_terminal_count": 0,
                            "terminal_pins": terminal_pins,
                        }
                    )
                    block_terminalized_count += 1
                    base_offset += len(display_data)
                local_records.extend(terminal_records)
                local_records.append(b"\x00")
                local_records.append(patched_block + b"".join(appended_wire_records))
                terminalized_count += block_terminalized_count
                family_reports.extend(block_family_reports)
                if sentinel_group is not None:
                    preserved_rows.append(
                        {
                            "component_key": _group_key(sentinel_group),
                            "component_family": _group_family(sentinel_group),
                            "reason": "combined_common_cathode_display_sentinel",
                            "byte_preserved": True,
                        }
                    )
                skipped_group_indices.update(
                    index
                    for index in block_group_indices
                    if index != group_index
                )
                continue
        original_group_data = bytes(getattr(group, "data", b""))
        planning_group_data = original_group_data
        combined_infrastructure: dict[str, Any] | None = None
        if (
            family == "7SEG-COM-CAT-BLUE"
            and group_index + 1 < len(ordered_groups)
            and _group_key(ordered_groups[group_index + 1])
            == "DISPLAY_ANODE_SENTINEL"
        ):
            sentinel = ordered_groups[group_index + 1]
            original_group_data += bytes(getattr(sentinel, "data", b""))
            skipped_group_indices.add(group_index + 1)
            combined_infrastructure = {
                "key": _group_key(sentinel),
                "family": _group_family(sentinel),
                "reason": (
                    "common-cathode display pin-link table crosses the "
                    "required anode sentinel boundary; sentinel packet is "
                    "preserved inside the patched display stream"
                ),
            }
        data = _strip_bidir_records_from_chunk(original_group_data)
        planning_data = _strip_bidir_records_from_chunk(planning_group_data)
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

        clean_packet_attachment_order = str(
            geometry.get(
                "clean_packet_attachment_order",
                "component_stream_then_attachment_units",
            )
        )
        if clean_packet_attachment_order not in {
            "component_stream_then_attachment_units",
            "terminal_leading_component_then_wires",
        }:
            raise ValueError(
                f"{family} {key} uses unsupported clean packet attachment order "
                f"{clean_packet_attachment_order!r}."
            )
        object_stream_finalizer = str(
            geometry.get("object_stream_finalizer", "double_ff")
        )
        if object_stream_finalizer not in {
            "single_ff",
            "double_ff",
            "append_explicit_single_ff",
        }:
            raise ValueError(
                f"{family} {key} uses unsupported object stream finalizer "
                f"{object_stream_finalizer!r}."
            )
        object_stream_finalizers.add(object_stream_finalizer)
        clean_packet_attachment_orders.add(clean_packet_attachment_order)

        current_suffix_by_pin = _current_bidir_suffixes_by_pin(
            original_group_data,
            profile,
        )
        planning_group = replace(group, data=planning_data)
        plan = plan_catalogue_pin_bidir_terminals(
            [planning_group],
            catalog=catalog,
            suffix_start=suffix,
            use_donor_terminal_labels=use_donor_terminal_labels,
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
        appended_wire_records: list[bytes] = []
        wire_count_added = 0
        wire_count_rewritten = 0
        for row in plan["terminal_plans"]:
            pin_name = str(row["pin"]["name"])
            raw_geometry = pins[pin_name]
            existing_wire = row.get("existing_wire")
            raw_donor_old_suffix = raw_geometry.get("donor_terminal_suffix")
            donor_old_suffix = (
                int(raw_donor_old_suffix)
                if raw_donor_old_suffix is not None
                else None
            )
            preferred_old_suffix = current_suffix_by_pin.get(
                pin_name,
                donor_old_suffix,
            )
            temporary_suffix = suffix & 0xFFFF
            suffix += 1
            short_wire = row["short_wire"]
            start = short_wire["start"]
            end = short_wire["end"]
            component_link_trailer: bytes | None = None
            existing_wire_marker_offset: int | None = None
            if isinstance(existing_wire, dict):
                wire_order_index = int(existing_wire["wire_order_index"])
                after_offset = (
                    0
                    if wire_order_index <= 0
                    else wire_marker_offsets[wire_order_index - 1] + 27
                )
                patched_data, component_link_position, old_suffix = (
                    _patch_component_link_before_wire(
                        patched_data,
                        new_suffix=temporary_suffix,
                        before_offset=int(existing_wire["marker_offset"]),
                        after_offset=after_offset,
                        preferred_old_suffix=preferred_old_suffix,
                        preferred_old_suffixes=(
                            value
                            for value in (preferred_old_suffix, donor_old_suffix)
                            if value is not None
                        ),
                    )
                )
                component_link_trailer = patched_data[
                    component_link_position + 2 : component_link_position + 4
                ]
                patched_data = _patch_wire_record_coordinates(
                    patched_data,
                    marker_offset=int(existing_wire["marker_offset"]),
                    start_x=int(start["x"]),
                    start_y=int(start["y"]),
                    end_x=int(end["x"]),
                    end_y=int(end["y"]),
                )
                existing_wire_marker_offset = int(existing_wire["marker_offset"])
                wire_count_rewritten += 1
            else:
                if original_group_data.count(BIDIR_MARKER) or data_wire_rows:
                    raise ValueError(
                        f"{family} {key} pin {pin_name} has no matched "
                        "donor-native WIRE anchor, but the placed packet still "
                        "contains terminal/WIRE infrastructure. Refusing to mix "
                        "existing-anchor and clean bare-packet emission."
                    )
                raw_link_offset = raw_geometry.get(
                    "component_link_offset_from_component_end"
                )
                if raw_link_offset is None:
                    raise ValueError(
                        f"{family} {key} pin {pin_name} lacks catalogue "
                        "component-link offset for clean bare-packet emission."
                    )
                patched_data, component_link_position, old_suffix, trailer = (
                    _patch_component_link_from_catalogue_offset(
                        patched_data,
                        new_suffix=temporary_suffix,
                        offset_from_component_end=int(raw_link_offset),
                        trailer_hex=raw_geometry.get("component_link_trailer"),
                    )
                )
                component_link_trailer = trailer
                appended_wire_records.append(bytes.fromhex(short_wire["record"]))
                wire_count_added += 1
            terminal_dict = dict(row["terminal"])
            terminal_dict["suffix"] = f"{temporary_suffix:04x}"
            terminal_link_trailer = bytes.fromhex(
                str(
                    terminal_dict.get(
                        "link_trailer",
                        COMPONENT_PIN_LINK_TRAILERS[0].hex(),
                    )
                )
            )
            if terminal_link_trailer not in COMPONENT_PIN_LINK_TRAILERS:
                raise ValueError(
                    f"{family} {key} pin {pin_name} uses unsupported terminal "
                    f"link trailer {terminal_link_trailer.hex()}."
                )
            terminal_records.append(
                build_bidir_record(
                    terminal_templates,
                    label=str(terminal_dict["label"]),
                    symbol_x=int(terminal_dict["symbol_x"]),
                    symbol_y=int(terminal_dict["symbol_y"]),
                    angle_tenths=int(terminal_dict["angle_tenths"]),
                    suffix=temporary_suffix,
                    active_link=True,
                )[:-2]
                + terminal_link_trailer
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
                        **(
                            {"coordinates": list(short_wire["coordinates"])}
                            if isinstance(short_wire.get("coordinates"), (list, tuple))
                            else {}
                        ),
                        **(
                            {"terminal_contact": dict(short_wire["terminal_contact"])}
                            if isinstance(short_wire.get("terminal_contact"), dict)
                            else {}
                        ),
                        **(
                            {"pin_contact": dict(short_wire["pin_contact"])}
                            if isinstance(short_wire.get("pin_contact"), dict)
                            else {}
                        ),
                    },
                    "catalogue_geometry": dict(raw_geometry),
                    "component_bbox": dict(row.get("component_bbox", {})),
                    "component_anchor": (
                        dict(row["component_anchor"])
                        if isinstance(row.get("component_anchor"), dict)
                        else None
                    ),
                    "existing_wire": dict(existing_wire)
                    if isinstance(existing_wire, dict)
                    else None,
                    "old_suffix": f"{old_suffix:04x}",
                    "temporary_suffix": f"{temporary_suffix:04x}",
                    "component_link_position": component_link_position,
                    "existing_wire_marker_offset": existing_wire_marker_offset,
                    "component_link_trailer": (
                        component_link_trailer.hex()
                        if component_link_trailer is not None
                        else None
                    ),
                    "coordinate_source": row["coordinate_source"],
                    "terminal_contact_source": row.get(
                        "terminal_contact_source",
                        "generic_grid_contact",
                    ),
                }
            )
        if wire_count_added:
            if wire_count_rewritten:
                raise ValueError(
                    f"{family} {key} mixed existing-WIRE rewriting and appended "
                    "WIRE emission in one packet; refusing unsafe object order."
                )
            if len(appended_wire_records) != len(terminal_records):
                raise ValueError(
                    f"{family} {key} has {len(terminal_records)} terminals but "
                    f"{len(appended_wire_records)} appended WIRE records."
                )
            raw_max_proven_components = geometry.get(
                "clean_packet_max_proven_components"
            )
            raw_progressive_validation_cap = geometry.get(
                "clean_packet_progressive_validation_cap"
            )
            max_allowed_components: int | None = None
            if raw_max_proven_components is not None:
                max_allowed_components = int(raw_max_proven_components)
            if allow_progressive_scaling and raw_progressive_validation_cap is not None:
                progressive_validation_cap = int(raw_progressive_validation_cap)
                if progressive_validation_cap < (max_allowed_components or 0):
                    raise ValueError(
                        f"{family} progressive validation cap "
                        f"{progressive_validation_cap} is lower than its donor-proven "
                        f"component count {max_allowed_components}."
                    )
                max_allowed_components = progressive_validation_cap
            if max_allowed_components is not None:
                family_component_count = sum(
                    1 for item in groups if _group_family(item) == family
                )
                if family_component_count > max_allowed_components:
                    progressive_note = (
                        " Enable allow_progressive_scaling only for the "
                        "catalogue-declared progressive-validation cap."
                        if (
                            raw_progressive_validation_cap is not None
                            and not allow_progressive_scaling
                        )
                        else ""
                    )
                    raise ValueError(
                        f"{family} clean-packet terminal emission is proven for "
                        f"at most {raw_max_proven_components} component(s), not "
                        f"{family_component_count}.{progressive_note}"
                    )
            if clean_packet_attachment_order == "terminal_leading_component_then_wires":
                if trailing_attachment_records:
                    raise ValueError(
                        f"{family} terminal-leading clean-packet order cannot be mixed "
                        "with trailing attachment units before a combined donor proves "
                        "that hybrid stream."
                    )
                if local_records and terminal_leading_block_count == 0:
                    raise ValueError(
                        f"{family} terminal-leading clean-packet order cannot follow "
                        "a preserved or differently ordered component stream."
                    )
                if clean_packet_attachment_orders != {
                    "terminal_leading_component_then_wires"
                }:
                    raise ValueError(
                        "Catalogue terminal-leading blocks cannot be combined with "
                        f"other attachment orders: {sorted(clean_packet_attachment_orders)}."
                    )
                raw_terminal_record_order = geometry.get(
                    "donor_terminal_record_order"
                )
                if not isinstance(raw_terminal_record_order, (list, tuple)):
                    raise ValueError(
                        f"{family} terminal-leading emission requires "
                        "donor_terminal_record_order catalogue evidence."
                    )
                terminal_record_order = [
                    str(pin_name) for pin_name in raw_terminal_record_order
                ]
                terminal_records_by_pin = {
                    str(pin_row["pin"]["name"]): terminal_record
                    for pin_row, terminal_record in zip(
                        terminal_pins,
                        terminal_records,
                        strict=True,
                    )
                }
                if (
                    len(terminal_record_order)
                    != len(set(terminal_record_order))
                    or set(terminal_record_order) != set(terminal_records_by_pin)
                ):
                    raise ValueError(
                        f"{family} donor_terminal_record_order "
                        f"{terminal_record_order} does not exactly cover emitted "
                        f"catalogue pins {sorted(terminal_records_by_pin)}."
                    )
                ordered_terminal_records = [
                    terminal_records_by_pin[pin_name]
                    for pin_name in terminal_record_order
                ]
                wire_tail_policy = str(
                    geometry.get("last_appended_wire_tail_policy", "preserve")
                )
                ordered_wire_records = list(appended_wire_records)
                if wire_tail_policy == "trim_trailing_zero_before_finalizer":
                    if not ordered_wire_records[-1].endswith(b"\x00"):
                        raise ValueError(
                            f"{family} final WIRE record lacks the donor-proven "
                            "trailing zero required by the trim policy."
                        )
                    ordered_wire_records[-1] = ordered_wire_records[-1][:-1]
                elif wire_tail_policy != "preserve":
                    raise ValueError(
                        f"{family} uses unsupported final WIRE tail policy "
                        f"{wire_tail_policy!r}."
                    )
                local_records.extend(ordered_terminal_records)
                local_records.append(b"\x00")
                local_records.append(
                    patched_data + b"".join(ordered_wire_records)
                )
                terminal_leading_block_count += 1
            else:
                if clean_packet_attachment_orders == {
                    "component_stream_then_attachment_units",
                    "terminal_leading_component_then_wires",
                }:
                    raise ValueError(
                        "Catalogue clean-packet attachment orders cannot be mixed "
                        "before each order has a Proteus-accepted combined oracle."
                    )
                local_records.append(patched_data)
                for terminal_record, wire_record in zip(
                    terminal_records,
                    appended_wire_records,
                ):
                    trailing_attachment_records.append(terminal_record)
                    trailing_attachment_records.append(wire_record)
        else:
            local_records.extend(terminal_records)
            local_records.append(b"\x00")
            local_records.append(patched_data)
        terminalized_count += 1
        family_handler = (
            f"{family}/catalogue-existing-wire-v1"
            if wire_count_added == 0
            else f"{family}/catalogue-link-offset-wire-v1"
        )
        family_reports.append(
            {
                "family_handler": family_handler,
                "component_key": key,
                "component_family": family,
                "catalogue_source_project": geometry.get("source_project"),
                "component_count": 1,
                "combined_infrastructure": combined_infrastructure,
                "terminal_count": len(terminal_records),
                "wire_count": len(terminal_records),
                "wire_count_added": wire_count_added,
                "wire_count_rewritten": wire_count_rewritten,
                "clean_packet_attachment_order": clean_packet_attachment_order,
                "donor_terminal_record_order": (
                    list(geometry.get("donor_terminal_record_order", ()))
                    if clean_packet_attachment_order
                    == "terminal_leading_component_then_wires"
                    else None
                ),
                "last_appended_wire_tail_policy": geometry.get(
                    "last_appended_wire_tail_policy",
                    "preserve",
                ),
                "object_stream_finalizer": object_stream_finalizer,
                "allow_zero_length_wire_units": bool(
                    geometry.get("allow_zero_length_wire_units", False)
                ),
                "stripped_existing_terminal_count": stripped_existing_terminals,
                "terminal_pins": terminal_pins,
            }
        )

    if not family_reports:
        raise ValueError("No catalogue-backed terminalized component was emitted.")
    if len(object_stream_finalizers) != 1:
        raise ValueError(
            "Catalogue terminal attachment requires one proven object-stream "
            f"finalizer per output, got {sorted(object_stream_finalizers)}."
        )
    object_stream_finalizer = next(iter(object_stream_finalizers))
    if object_stream_finalizer == "single_ff":
        finalize_object_stream = _ensure_single_ff_object_stream_terminator
    elif object_stream_finalizer == "double_ff":
        finalize_object_stream = _ensure_double_ff_object_stream_terminator
    else:
        finalize_object_stream = _append_explicit_single_ff_object_stream_terminator
    if trailing_attachment_records:
        if not local_records or not all(record.startswith(b"\xff") for record in local_records):
            raise ValueError(
                "Catalogue clean-packet trailing attachment emission requires "
                "a complete component stream before terminal/WIRE units."
            )
        object_component_prefix = original_chunk[1:2]
        if not object_component_prefix:
            raise ValueError(
                "Catalogue clean-packet trailing attachment emission could not "
                "recover the original component stream prefix."
            )
        component_stream = (
            original_chunk[:1]
            + object_component_prefix
            + b"".join(local_records[:-1])
            + local_records[-1][:-1]
        )
        new_chunk = finalize_object_stream(
            component_stream + b"".join(trailing_attachment_records)
        )
    elif local_records and not local_records[0].startswith(b"\xff"):
        # Terminal-leading object streams use the same initial shape as the
        # accepted native two-pin route: the stream starts with the first byte
        # of the original object chunk, then terminal records, then the
        # component packet separator and component packet.  Re-inserting the
        # original component-prefix byte before the first component would
        # create a Proteus-rejected hybrid stream.
        new_chunk = finalize_object_stream(
            original_chunk[:1] + b"".join(local_records)
        )
    else:
        rebuilt_records: list[bytes] = []
        object_component_prefix = original_chunk[1:2]
        component_prefix_inserted = not bool(object_component_prefix)
        for record in local_records:
            if (
                not component_prefix_inserted
                and record.startswith(b"\xff")
            ):
                rebuilt_records.append(object_component_prefix + record)
                component_prefix_inserted = True
            else:
                rebuilt_records.append(record)
        if not component_prefix_inserted:
            raise ValueError(
                "Catalogue terminal attachment did not emit a component packet "
                "that can receive the original object-stream component prefix."
            )
        new_chunk = finalize_object_stream(
            original_chunk[:1] + b"".join(rebuilt_records)
        )
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    # The locked mega donor intentionally keeps its complete ROOT.CDB during
    # component placement.  Once this stage emits active terminal/component
    # links, however, Proteus 8.13 normalizes ROOT.CDB to the packages that are
    # actually present.  Keeping all 4,520 mega-donor rows caused the NPN Bad
    # Object Record/LXLCORE failures even though ROOT.DSN was donor-isomorphic.
    # Build the same selected-package CDB here, through the shared component
    # placer parser/builder, so terminal output is byte-equivalent to Proteus's
    # own Ctrl+S normalization rather than depending on a family-specific fix.
    from .component_placer import (
        build_component_placer_cdb_subset,
        parse_component_placer_cdb,
    )

    source_cdb = read_internal_file(source, "ROOT.CDB")
    cdb_keep_packages = sorted(
        {
            _group_key(group)
            for group in groups
            if _group_key(group) and not _group_key(group).startswith("ANON")
        }
    )
    if not cdb_keep_packages:
        raise ValueError(
            "Catalogue terminal attachment could not identify any package "
            "references for ROOT.CDB normalization."
        )
    normalized_cdb = build_component_placer_cdb_subset(
        parse_component_placer_cdb(source_cdb),
        cdb_keep_packages,
    )
    write_project_from_parts(
        source,
        destination,
        {"ROOT.DSN": new_dsn, "ROOT.CDB": normalized_cdb},
    )
    final_chunk = _extract_object_chunk(read_internal_file(destination, "ROOT.DSN"))

    terminal_count = sum(report["terminal_count"] for report in family_reports)
    wire_count = sum(report["wire_count"] for report in family_reports)
    wire_count_added = sum(
        int(report.get("wire_count_added", 0)) for report in family_reports
    )
    wire_count_rewritten = sum(
        int(report.get("wire_count_rewritten", 0)) for report in family_reports
    )
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
            wire_start = (int(wire["start"]["x"]), int(wire["start"]["y"]))
            wire_end = (int(wire["end"]["x"]), int(wire["end"]["y"]))
            raw_coordinates = wire.get("coordinates")
            if (
                isinstance(raw_coordinates, (list, tuple))
                and len(raw_coordinates) >= 4
                and len(raw_coordinates) % 2 == 0
            ):
                wire_points = set(_wire_coordinate_points(raw_coordinates))
            else:
                wire_points = {wire_start, wire_end}
            actual_terminal_contact_xy = (
                contact_x,
                int(terminal["symbol_y"]),
            )
            actual_pin_contact_xy = (
                int(row["pin"]["x"]),
                int(row["pin"]["y"]),
            )
            planned_terminal_contact = wire.get(
                "terminal_contact",
                {"x": contact_x, "y": int(terminal["symbol_y"])},
            )
            planned_pin_contact = wire.get(
                "pin_contact",
                {"x": int(row["pin"]["x"]), "y": int(row["pin"]["y"])},
            )
            planned_terminal_contact_xy = (
                int(planned_terminal_contact["x"]),
                int(planned_terminal_contact["y"]),
            )
            planned_pin_contact_xy = (
                int(planned_pin_contact["x"]),
                int(planned_pin_contact["y"]),
            )
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
                        actual_terminal_contact_xy in wire_points
                        and planned_terminal_contact_xy in wire_points
                    ),
                    "wire_to_pin": (
                        actual_pin_contact_xy in wire_points
                        and planned_pin_contact_xy in wire_points
                    ),
                    "wire_is_nonzero": len(wire_points) > 1,
                    "zero_length_wire_allowed": bool(
                        report.get("allow_zero_length_wire_units", False)
                    ),
                }
            )
    report = {
        "stage": "terminal_placer",
        "family_handler": (
            "CATALOGUE/link-offset-wire-v1"
            if wire_count_added
            else "CATALOGUE/existing-wire-v1"
        ),
        "status": "pending_proteus_user_acceptance",
        "attachment_policy": (
            "catalogue_pin_identity_component_link_offset_grid_short_wire"
        ),
        "progressive_scaling_enabled": allow_progressive_scaling,
        "runtime_circuit_donor_dependency": False,
        "component_coordinate_mutation": False,
        "terminal_record_encoder": "embedded_proteus_813_schema",
        "wire_record_encoder": "rewrite_existing_or_append_catalogue_short_wire_records",
        "terminal_count_added": terminal_count,
        "wire_count_added": wire_count_added,
        "wire_count_rewritten": wire_count_rewritten,
        "terminalized_component_count": terminalized_count,
        "preserved_component_count": len(preserved_rows),
        "preserved_groups": preserved_rows,
        "family_reports": family_reports,
        "wire_path_contact_checks": wire_path_checks,
        "wire_path_contacts_valid": all(
            row["terminal_contact_grid_aligned"]
            and row["terminal_to_wire"]
            and row["wire_to_pin"]
            and (
                row["wire_is_nonzero"]
                or row["zero_length_wire_allowed"]
            )
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
        "object_stream_finalizer": object_stream_finalizer,
        "base_component_stream_covered": True,
        "cdb_normalization": {
            "policy": "selected_package_rows_matching_proteus_ctrl_s",
            "keep_packages": cdb_keep_packages,
            "size_before": len(source_cdb),
            "size_after": len(normalized_cdb),
        },
    }
    return _rebase_terminal_links_to_final_wire_addresses(destination, report)


def attach_mixed_component_and_catalogue_bidir_terminals_to_project(
    project: str | Path,
    output: str | Path,
    selected_groups: Iterable[Any],
    *,
    native_terminal_families: Iterable[str] | None = None,
    catalogue_terminal_families: Iterable[str] | None = None,
    catalog: Any | None = None,
    catalogue_suffix_start: int = 0x7A00,
    use_donor_terminal_labels: bool = False,
) -> dict[str, Any]:
    """Attach accepted two-pin and catalogue multi-pin terminals in one stream.

    The public two-pin mixed writer and the catalogue writer both expect a bare
    component stream.  They cannot safely be chained after each other.  This
    shared writer consumes the bare component-placer project once, reuses the
    accepted two-pin family planners and the catalogue pin/link-offset planner,
    patches every component packet in the preserved component stream, appends
    the terminal/WIRE units once, then performs the same final WIRE-address
    rebasing used by the accepted terminal paths.
    """

    if catalog is None:
        from .component_catalog import load_component_catalog

        catalog = load_component_catalog()
    groups = tuple(selected_groups)
    if not groups:
        raise ValueError("Mixed native/catalogue attachment requires selected groups.")
    source = Path(project)
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    dsn = read_internal_file(source, "ROOT.DSN")
    original_chunk = _extract_object_chunk(dsn)
    if BIDIR_MARKER in original_chunk or b"\x7fWIRE" in original_chunk:
        raise ValueError(
            "Mixed native/catalogue terminal attachment requires a bare "
            "component-placer project."
        )
    ordered_groups = _covered_component_stream_with_optional_final_ff(
        original_chunk,
        groups,
    )
    families = {_group_family(group) for group in ordered_groups}
    native_accepted = set(ACCEPTED_TERMINAL_FAMILY_ORDER)
    native_available = tuple(
        dict.fromkeys(
            family
            for group in ordered_groups
            for family in (_terminal_eligible_family(group, native_accepted),)
            if family is not None
        )
    )
    if native_terminal_families is None:
        requested_native = native_available
    else:
        requested_native = tuple(
            dict.fromkeys(str(item) for item in native_terminal_families)
        )
        unknown_native = sorted(set(requested_native) - native_accepted)
        missing_native = sorted(set(requested_native) - set(native_available))
        if unknown_native:
            raise ValueError(
                "No accepted native terminal handler exists for requested "
                f"families: {unknown_native}."
            )
        if missing_native:
            raise ValueError(
                "Requested native terminal families are absent from selected "
                f"groups: {missing_native}."
            )
    if catalogue_terminal_families is None:
        requested_catalogue = tuple(
            family
            for family in families
            if family not in set(requested_native)
            and catalog.get_profile(family) is not None
        )
    else:
        requested_catalogue = tuple(
            dict.fromkeys(str(item) for item in catalogue_terminal_families)
        )
        missing_catalogue = sorted(set(requested_catalogue) - families)
        if missing_catalogue:
            raise ValueError(
                "Requested catalogue terminal families are absent from selected "
                f"groups: {missing_catalogue}."
            )
    if not requested_native or not requested_catalogue:
        raise ValueError(
            "Mixed native/catalogue attachment requires at least one accepted "
            "native family and one catalogue family."
        )

    terminal_templates = load_production_templates(FixtureRegistry.load())
    patched_by_id: dict[int, bytes] = {}
    native_leading_records: list[bytes] = []
    native_terminal_by_group_id: dict[int, tuple[bytes, ...]] = {}
    native_wire_by_group_id: dict[int, tuple[bytes, bytes]] = {}
    catalogue_attachment_records: list[bytes] = []
    catalogue_component_stream_by_group_id: dict[int, bytes] = {}
    catalogue_leading_by_group_id: dict[int, tuple[bytes, ...]] = {}
    catalogue_leading_finalizers: set[str] = set()
    family_reports: list[dict[str, Any]] = []
    terminalized_count = 0
    reserved_temporary_suffixes: set[int] = set()

    source_index_start = 1
    for family in requested_native:
        family_groups = tuple(
            group
            for group in ordered_groups
            if _terminal_eligible_family(group, {family}) == family
        )
        if not family_groups:
            continue
        pairs, family_terminals, family_wires, family_patches = (
            _mixed_overlay_family_parts(
                family,
                family_groups,
                terminal_templates=terminal_templates,
                source_index_start=source_index_start,
                active_links=True,
                # The terminal-leading BJT hybrid uses the same active-link
                # class as its catalogue attachments.  P002's Ctrl+S oracle
                # established this for native RESISTOR/CAP; the full-stream
                # probe applies that shared hybrid class consistently before
                # promotion of the wider family matrix.
                active_link_trailer=b"\x02\x00",
                snap_terminal_contacts_to_grid=False,
            )
        )
        if family in SOURCE_COMPONENT_BARE_BASE_SIZES:
            source_index_start += len(family_groups)
        if family == "RESISTOR":
            native_leading_records.extend(family_terminals)
            for group, wires in zip(family_groups, family_wires, strict=True):
                native_terminal_by_group_id[id(group)] = ()
                native_wire_by_group_id[id(group)] = wires
        elif family == "CAP":
            component_count = len(family_groups)
            native_leading_records.extend(family_terminals[:component_count])
            for index, (group, wires) in enumerate(
                zip(family_groups, family_wires, strict=True)
            ):
                native_terminal_by_group_id[id(group)] = (
                    family_terminals[component_count + index],
                )
                native_wire_by_group_id[id(group)] = wires
        else:
            for index, (group, wires) in enumerate(
                zip(family_groups, family_wires, strict=True)
            ):
                native_terminal_by_group_id[id(group)] = tuple(
                    family_terminals[index * 2 : index * 2 + 2]
                )
                native_wire_by_group_id[id(group)] = wires
        overlap = set(patched_by_id) & set(family_patches)
        if overlap:
            raise ValueError(f"Duplicate native patch target for {family}.")
        patched_by_id.update(family_patches)
        for pair in pairs:
            pair_dict = pair.as_dict()
            roles = ("left", "right") if "left" in pair_dict else ("input", "output")
            for role in roles:
                reserved_temporary_suffixes.add(
                    int(pair_dict[role]["suffix"], 16)
                )
        family_reports.append(
            {
                "family_handler": f"{family}/mixed-native-catalogue-v1",
                "component_count": len(family_groups),
                "terminal_count": len(pairs) * 2,
                "wire_count": len(pairs) * 2,
                "wire_count_added": len(pairs) * 2,
                "wire_count_rewritten": 0,
                "terminal_pairs": [pair.as_dict() for pair in pairs],
            }
        )
        terminalized_count += len(family_groups)

    suffix = catalogue_suffix_start
    for group in ordered_groups:
        family = _group_family(group)
        if family not in requested_catalogue:
            continue
        key = _group_key(group)
        profile = catalog.get_profile(family)
        geometry = profile.proteus.get("pin_geometry", {}) if profile is not None else {}
        pins = geometry.get("pins", {}) if isinstance(geometry, dict) else {}
        if profile is None or not isinstance(pins, dict) or not pins:
            raise ValueError(f"{family} {key} lacks catalogue pin geometry.")
        clean_packet_attachment_order = str(
            geometry.get(
                "clean_packet_attachment_order",
                "component_stream_then_attachment_units",
            )
        )
        if clean_packet_attachment_order not in {
            "component_stream_then_attachment_units",
            "terminal_leading_component_then_wires",
        }:
            raise ValueError(
                f"{family} {key} uses unsupported clean packet attachment order "
                f"{clean_packet_attachment_order!r} in mixed emission."
            )
        object_stream_finalizer = str(
            geometry.get("object_stream_finalizer", "double_ff")
        )
        if object_stream_finalizer not in {
            "single_ff",
            "double_ff",
            "append_explicit_single_ff",
        }:
            raise ValueError(
                f"{family} {key} uses unsupported object stream finalizer "
                f"{object_stream_finalizer!r} in mixed emission."
            )
        original_group_data = bytes(getattr(group, "data", b""))
        if BIDIR_MARKER in original_group_data or b"\x7fWIRE" in original_group_data:
            raise ValueError(
                f"{family} {key} mixed catalogue emission requires a clean "
                "bare component packet."
            )
        plan = plan_catalogue_pin_bidir_terminals(
            [group],
            catalog=catalog,
            suffix_start=suffix,
            use_donor_terminal_labels=use_donor_terminal_labels,
        )
        if not plan["valid"]:
            raise ValueError(
                f"Catalogue terminal plan for {family} {key} is incomplete: "
                f"{plan['missing_geometry']}."
        )
        patched_data = original_group_data
        terminal_pins: list[dict[str, Any]] = []
        terminal_records: list[bytes] = []
        appended_wire_records: list[bytes] = []
        terminal_count = 0
        for row in plan["terminal_plans"]:
            pin_name = str(row["pin"]["name"])
            raw_geometry = pins[pin_name]
            if row.get("existing_wire") is not None:
                raise ValueError(
                    f"{family} {key} pin {pin_name} unexpectedly used an "
                    "existing WIRE anchor in mixed clean-packet emission."
                )
            raw_link_offset = raw_geometry.get(
                "component_link_offset_from_component_end"
            )
            if raw_link_offset is None:
                raise ValueError(
                    f"{family} {key} pin {pin_name} lacks catalogue "
                    "component-link offset."
                )
            while suffix & 0xFFFF in reserved_temporary_suffixes:
                suffix += 1
            temporary_suffix = suffix & 0xFFFF
            reserved_temporary_suffixes.add(temporary_suffix)
            suffix += 1
            patched_data, component_link_position, old_suffix, trailer = (
                _patch_component_link_from_catalogue_offset(
                    patched_data,
                    new_suffix=temporary_suffix,
                    offset_from_component_end=int(raw_link_offset),
                    trailer_hex=raw_geometry.get("component_link_trailer"),
                )
            )
            terminal_dict = dict(row["terminal"])
            terminal_dict["suffix"] = f"{temporary_suffix:04x}"
            terminal_link_trailer = bytes.fromhex(
                str(
                    terminal_dict.get(
                        "link_trailer",
                        COMPONENT_PIN_LINK_TRAILERS[0].hex(),
                    )
                )
            )
            if terminal_link_trailer not in COMPONENT_PIN_LINK_TRAILERS:
                raise ValueError(
                    f"{family} {key} pin {pin_name} uses unsupported terminal "
                    f"link trailer {terminal_link_trailer.hex()}."
                )
            terminal_records.append(
                build_bidir_record(
                    terminal_templates,
                    label=str(terminal_dict["label"]),
                    symbol_x=int(terminal_dict["symbol_x"]),
                    symbol_y=int(terminal_dict["symbol_y"]),
                    angle_tenths=int(terminal_dict["angle_tenths"]),
                    suffix=temporary_suffix,
                    active_link=True,
                )[:-2]
                + terminal_link_trailer
            )
            short_wire = row["short_wire"]
            appended_wire_records.append(bytes.fromhex(short_wire["record"]))
            start = short_wire["start"]
            end = short_wire["end"]
            terminal_pins.append(
                {
                    "component_key": key,
                    "component_family": family,
                    "pin": row["pin"],
                    "terminal": terminal_dict,
                    "short_wire": {
                        "start": dict(start),
                        "end": dict(end),
                        **(
                            {"coordinates": list(short_wire["coordinates"])}
                            if isinstance(short_wire.get("coordinates"), (list, tuple))
                            else {}
                        ),
                        **(
                            {"terminal_contact": dict(short_wire["terminal_contact"])}
                            if isinstance(short_wire.get("terminal_contact"), dict)
                            else {}
                        ),
                        **(
                            {"pin_contact": dict(short_wire["pin_contact"])}
                            if isinstance(short_wire.get("pin_contact"), dict)
                            else {}
                        ),
                    },
                    "catalogue_geometry": dict(raw_geometry),
                    "component_bbox": dict(row.get("component_bbox", {})),
                    "component_anchor": (
                        dict(row["component_anchor"])
                        if isinstance(row.get("component_anchor"), dict)
                        else None
                    ),
                    "existing_wire": None,
                    "old_suffix": f"{old_suffix:04x}",
                    "temporary_suffix": f"{temporary_suffix:04x}",
                    "component_link_position": component_link_position,
                    "existing_wire_marker_offset": None,
                    "component_link_trailer": trailer.hex(),
                    "coordinate_source": row["coordinate_source"],
                    "terminal_contact_source": row.get(
                        "terminal_contact_source",
                        "generic_grid_contact",
                    ),
                }
            )
            terminal_count += 1
        if len(terminal_records) != len(appended_wire_records):
            raise ValueError(
                f"{family} {key} emitted {len(terminal_records)} terminals but "
                f"{len(appended_wire_records)} short WIRE records in mixed emission."
            )
        if clean_packet_attachment_order == "terminal_leading_component_then_wires":
            if object_stream_finalizer != "append_explicit_single_ff":
                raise ValueError(
                    f"{family} {key} terminal-leading mixed emission requires "
                    "append_explicit_single_ff finalizer evidence."
                )
            raw_terminal_record_order = geometry.get("donor_terminal_record_order")
            if not isinstance(raw_terminal_record_order, (list, tuple)):
                raise ValueError(
                    f"{family} {key} lacks donor_terminal_record_order for "
                    "terminal-leading mixed emission."
                )
            terminal_records_by_pin = {
                str(pin_row["pin"]["name"]): terminal_record
                for pin_row, terminal_record in zip(
                    terminal_pins,
                    terminal_records,
                    strict=True,
                )
            }
            terminal_record_order = [
                str(pin_name) for pin_name in raw_terminal_record_order
            ]
            if (
                len(terminal_record_order) != len(set(terminal_record_order))
                or set(terminal_record_order) != set(terminal_records_by_pin)
            ):
                raise ValueError(
                    f"{family} {key} donor_terminal_record_order "
                    f"{terminal_record_order} does not cover emitted pins "
                    f"{sorted(terminal_records_by_pin)}."
                )
            ordered_terminal_records = [
                terminal_records_by_pin[pin_name]
                for pin_name in terminal_record_order
            ]
            ordered_wire_records = list(appended_wire_records)
            wire_tail_policy = str(
                geometry.get("last_appended_wire_tail_policy", "preserve")
            )
            if wire_tail_policy == "trim_trailing_zero_before_finalizer":
                if not ordered_wire_records[-1].endswith(b"\x00"):
                    raise ValueError(
                        f"{family} {key} final WIRE lacks the donor-proven "
                        "trailing zero required by its terminal-leading policy."
                    )
                ordered_wire_records[-1] = ordered_wire_records[-1][:-1]
            elif wire_tail_policy != "preserve":
                raise ValueError(
                    f"{family} {key} uses unsupported terminal-leading WIRE "
                    f"tail policy {wire_tail_policy!r}."
                )
            catalogue_leading_by_group_id[id(group)] = tuple(
                ordered_terminal_records
                + [b"\x00", patched_data + b"".join(ordered_wire_records)]
            )
            catalogue_leading_finalizers.add(object_stream_finalizer)
        else:
            # Keep component-stream catalogue packets together in one trailing
            # zone.  A terminal-leading BJT block cannot safely begin directly
            # after a native two-pin WIRE, while the accepted P002/T02 mixed
            # oracles prove the catalogue component stream -> attachment units
            # -> BJT final-zone sequence.
            catalogue_component_stream_by_group_id[id(group)] = patched_data
            for terminal_record, wire_record in zip(
                terminal_records,
                appended_wire_records,
                strict=True,
            ):
                catalogue_attachment_records.append(terminal_record)
                catalogue_attachment_records.append(wire_record)
        if id(group) in patched_by_id:
            raise ValueError(f"Duplicate catalogue patch target for {family} {key}.")
        patched_by_id[id(group)] = patched_data
        family_reports.append(
            {
                "family_handler": f"{family}/catalogue-mixed-link-offset-wire-v1",
                "component_key": key,
                "component_family": family,
                "component_count": 1,
                "terminal_count": terminal_count,
                "wire_count": terminal_count,
                "wire_count_added": terminal_count,
                "wire_count_rewritten": 0,
                "stripped_existing_terminal_count": 0,
                "clean_packet_attachment_order": clean_packet_attachment_order,
                "object_stream_finalizer": object_stream_finalizer,
                "donor_terminal_record_order": (
                    list(geometry.get("donor_terminal_record_order", ()))
                    if clean_packet_attachment_order
                    == "terminal_leading_component_then_wires"
                    else None
                ),
                "allow_zero_length_wire_units": bool(
                    geometry.get("allow_zero_length_wire_units", False)
                ),
                "terminal_pins": terminal_pins,
            }
        )
        terminalized_count += 1

    local_starts_with_terminal = [
        bool(native_terminal_by_group_id.get(id(group), ()))
        for group in ordered_groups
    ]
    nonleading_group_indices = [
        index
        for index, group in enumerate(ordered_groups)
        if id(group) not in catalogue_leading_by_group_id
    ]
    if not nonleading_group_indices:
        raise ValueError(
            "Mixed terminal-leading emission requires a non-leading component "
            "stream before the final BJT serialization zone."
        )
    last_nonleading_group_index = nonleading_group_indices[-1]
    local_records: list[bytes] = []
    preserved_rows: list[dict[str, Any]] = []
    boundary_normalizations = 0
    terminalized_ids = set(patched_by_id)
    for index, group in enumerate(ordered_groups):
        group_id = id(group)
        family = _group_family(group)
        next_starts_with_terminal = (
            index + 1 < len(local_starts_with_terminal)
            and local_starts_with_terminal[index + 1]
        )
        terminal_units_follow_stream = (
            index == last_nonleading_group_index
            and bool(
                catalogue_attachment_records or catalogue_leading_by_group_id
            )
        )
        trim_component_tail_before_terminal = (
            next_starts_with_terminal or terminal_units_follow_stream
        )
        if group_id in catalogue_leading_by_group_id:
            # Terminal-leading BJT blocks are serialized together at the very
            # end of the stream.  A following ordinary component packet starts
            # with FF03 and Proteus treats that as the BJT block terminator.
            # Their design identity/coordinates stay intact; only the backend
            # serialization zone is moved to satisfy the donor grammar.
            continue
        if group_id in catalogue_component_stream_by_group_id:
            # This profile is serialized after the native stream and immediately
            # before its terminal/WIRE attachment units.  Retain its design
            # identity and packet bytes; only its backend stream position moves.
            continue
        if group_id in native_wire_by_group_id:
            terminals = native_terminal_by_group_id[group_id]
            patched = patched_by_id[group_id]
            first_wire, second_wire = native_wire_by_group_id[group_id]
            if len(first_wire) != 50 or len(second_wire) != 50:
                raise ValueError(
                    f"{family} {getattr(group, 'key', '')} lacks full native "
                    "wire records."
                )
            local_records.extend(terminals)
            if family != "RESISTOR":
                local_records.append(b"\x00")
            local_records.extend((patched, first_wire))
            local_records.append(
                # V29 donor/PDS evidence: a complete native WIRE must retain
                # its separator when catalogue attachment units or the final
                # terminal-leading BJT zone follow.  Only an immediately
                # following local native terminal record consumes that byte.
                second_wire[:-1] if next_starts_with_terminal else second_wire
            )
            if next_starts_with_terminal:
                boundary_normalizations += 1
            continue

        data = patched_by_id.get(group_id, bytes(getattr(group, "data", b"")))
        emitted = data[:-1] if trim_component_tail_before_terminal else data
        if not emitted:
            raise ValueError(
                f"{family} {getattr(group, 'key', '')} has no payload bytes "
                "before an active terminal unit."
            )
        local_records.append(emitted)
        if trim_component_tail_before_terminal:
            boundary_normalizations += 1
        if group_id not in terminalized_ids:
            preserved_rows.append(
                {
                    "component_key": _group_key(group),
                    "component_family": family,
                    "packet_size": len(bytes(getattr(group, "data", b""))),
                    "emitted_packet_size": len(emitted),
                    "byte_preserved": emitted == bytes(getattr(group, "data", b""))
                    or emitted == bytes(getattr(group, "data", b""))[:-1],
                    "boundary_tail_normalized": trim_component_tail_before_terminal,
                }
            )
    if not original_chunk[:1]:
        raise ValueError(
            "Mixed native/catalogue attachment could not recover the original "
            "component stream prefix."
        )
    catalogue_component_stream_records = [
        catalogue_component_stream_by_group_id[id(group)]
        for group in ordered_groups
        if id(group) in catalogue_component_stream_by_group_id
    ]
    if catalogue_component_stream_records:
        if not catalogue_attachment_records:
            raise ValueError(
                "Catalogue component-stream zone has no attachment units to "
                "terminate its final packet."
            )
        final_catalogue_packet = catalogue_component_stream_records[-1]
        if len(final_catalogue_packet) < 2:
            raise ValueError(
                "Final catalogue component packet is too short for donor-proven "
                "tail normalization."
            )
        # Standalone control/FET routes drop this stale final packet byte before
        # their attachment units.  Preserve the same grammar in the hybrid
        # stream instead of letting it bleed into the BJT final zone.
        catalogue_component_stream_records[-1] = final_catalogue_packet[:-1]
        boundary_normalizations += 1
    component_stream_records = local_records + catalogue_component_stream_records
    if not component_stream_records:
        raise ValueError("Mixed native/catalogue attachment produced no component records.")
    first_local_starts_with_terminal = local_starts_with_terminal[0]
    separator = b"" if first_local_starts_with_terminal else b"\x00"
    accepted_native_order_stream = (
        original_chunk[:1]
        + b"".join(native_leading_records)
        + separator
        + b"".join(component_stream_records)
    )
    catalogue_terminal_leading_records = [
        record
        for group in ordered_groups
        if id(group) in catalogue_leading_by_group_id
        for record in catalogue_leading_by_group_id[id(group)]
    ]
    if catalogue_leading_by_group_id:
        if catalogue_leading_finalizers != {"append_explicit_single_ff"}:
            raise ValueError(
                "Mixed terminal-leading catalogue blocks require one "
                "append_explicit_single_ff finalizer policy, got "
                f"{sorted(catalogue_leading_finalizers)}."
            )
        object_stream_finalizer = "append_explicit_single_ff"
        new_chunk = _append_explicit_single_ff_object_stream_terminator(
            accepted_native_order_stream
            + b"".join(catalogue_attachment_records)
            + b"".join(catalogue_terminal_leading_records)
        )
    else:
        object_stream_finalizer = "double_ff"
        new_chunk = _ensure_double_ff_object_stream_terminator(
            accepted_native_order_stream + b"".join(catalogue_attachment_records)
        )
    new_dsn, _pointers = build_dsn(dsn, dsn, new_chunk)
    # Active mixed terminal links need the same selected-package CDB
    # normalization as standalone catalogue emission.  In particular, Proteus
    # Ctrl+S proved that retaining the full mega CDB alongside BJT link records
    # can produce Bad Object Record/LXLCORE failures.
    from .component_placer import (
        build_component_placer_cdb_subset,
        parse_component_placer_cdb,
    )

    source_cdb = read_internal_file(source, "ROOT.CDB")
    cdb_keep_packages = sorted(
        {
            _group_key(group)
            for group in groups
            if _group_key(group) and not _group_key(group).startswith("ANON")
        }
    )
    if not cdb_keep_packages:
        raise ValueError(
            "Mixed terminal attachment could not identify package references "
            "for ROOT.CDB normalization."
        )
    normalized_cdb = build_component_placer_cdb_subset(
        parse_component_placer_cdb(source_cdb),
        cdb_keep_packages,
    )
    write_project_from_parts(
        source,
        destination,
        {"ROOT.DSN": new_dsn, "ROOT.CDB": normalized_cdb},
    )
    final_chunk = _extract_object_chunk(read_internal_file(destination, "ROOT.DSN"))
    native_wire_boundary_checks: list[dict[str, Any]] = []
    for start, end in _wire_record_spans(final_chunk):
        if start < len(final_chunk) and final_chunk[start] == 0x1D:
            native_wire_boundary_checks.append(
                {
                    "start": start,
                    "end": end,
                    "separator": final_chunk[end - 1],
                    "valid": final_chunk[end - 1] in (0x00, 0xFF),
                }
            )

    expected_terminals = sum(int(report["terminal_count"]) for report in family_reports)
    expected_wires = sum(int(report["wire_count"]) for report in family_reports)
    catalogue_contact_checks = []
    for report_row in family_reports:
        for row in report_row.get("terminal_pins", []):
            terminal = row["terminal"]
            wire = row["short_wire"]
            angle = int(terminal["angle_tenths"])
            if angle == LEFT_SIDE_ANGLE:
                contact_x = int(terminal["symbol_x"]) + TERMINAL_CONTACT_TO_PIN
            elif angle == RIGHT_SIDE_ANGLE:
                contact_x = int(terminal["symbol_x"]) - TERMINAL_CONTACT_TO_PIN
            else:
                contact_x = int(terminal["symbol_x"])
            raw_coordinates = wire.get("coordinates")
            if (
                isinstance(raw_coordinates, (list, tuple))
                and len(raw_coordinates) >= 4
                and len(raw_coordinates) % 2 == 0
            ):
                wire_points = set(_wire_coordinate_points(raw_coordinates))
            else:
                wire_points = {
                    (int(wire["start"]["x"]), int(wire["start"]["y"])),
                    (int(wire["end"]["x"]), int(wire["end"]["y"])),
                }
            terminal_contact = wire.get(
                "terminal_contact",
                {"x": contact_x, "y": int(terminal["symbol_y"])},
            )
            pin_contact = wire.get(
                "pin_contact",
                {"x": int(row["pin"]["x"]), "y": int(row["pin"]["y"])},
            )
            catalogue_contact_checks.append(
                {
                    "component_key": row["component_key"],
                    "component_family": row["component_family"],
                    "pin": row["pin"]["name"],
                    "terminal_contact_grid_aligned": (
                        contact_x % PROTEUS_TERMINAL_GRID == 0
                        and int(terminal["symbol_y"]) % PROTEUS_TERMINAL_GRID == 0
                    ),
                    "terminal_to_wire": (
                        (contact_x, int(terminal["symbol_y"])) in wire_points
                        and (
                            int(terminal_contact["x"]),
                            int(terminal_contact["y"]),
                        )
                        in wire_points
                    ),
                    "wire_to_pin": (
                        (int(row["pin"]["x"]), int(row["pin"]["y"])) in wire_points
                        and (int(pin_contact["x"]), int(pin_contact["y"]))
                        in wire_points
                    ),
                    "wire_is_nonzero": len(wire_points) > 1,
                    "zero_length_wire_allowed": bool(
                        report_row.get("allow_zero_length_wire_units", False)
                    ),
                }
            )
    report = {
        "stage": "terminal_placer",
        "family_handler": "MIXED/native-two-pin-plus-catalogue-v1",
        "status": "pending_proteus_user_acceptance",
        "attachment_policy": (
            "preserve_native_stream_with_profile-driven_catalogue_terminal_units"
        ),
        "object_order": (
            "accepted_two_pin_native_order_with_hybrid_component_stream_"
            "attachment_zone_then_contiguous_final_terminal-leading_zone"
        ),
        "runtime_circuit_donor_dependency": False,
        "component_coordinate_mutation": False,
        "native_terminal_families": list(requested_native),
        "catalogue_terminal_families": list(requested_catalogue),
        "catalogue_terminal_leading_component_count": len(
            catalogue_leading_by_group_id
        ),
        "catalogue_component_stream_component_count": len(
            catalogue_component_stream_by_group_id
        ),
        "catalogue_component_stream_component_keys": [
            _group_key(group)
            for group in ordered_groups
            if id(group) in catalogue_component_stream_by_group_id
        ],
        "catalogue_terminal_leading_component_keys": [
            _group_key(group)
            for group in ordered_groups
            if id(group) in catalogue_leading_by_group_id
        ],
        "object_stream_finalizer": object_stream_finalizer,
        "family_reports": family_reports,
        "terminal_count_added": expected_terminals,
        "wire_count_added": expected_wires,
        "wire_count_rewritten": 0,
        "terminalized_component_count": terminalized_count,
        "preserved_component_count": len(preserved_rows),
        "preserved_groups": preserved_rows,
        "native_terminal_pair_count": sum(
            int(report["terminal_count"])
            for report in family_reports
            if report.get("terminal_pairs")
        ),
        "wire_path_contact_checks": catalogue_contact_checks,
        "wire_path_contacts_valid": all(
            (
                row.get("wire_is_nonzero", True)
                or row.get("zero_length_wire_allowed", False)
            )
            and row.get("terminal_to_wire", False)
            and row.get("wire_to_pin", False)
            for row in catalogue_contact_checks
        ),
        "terminal_grid_alignment_valid": all(
            row.get("terminal_contact_grid_aligned", True)
            for row in catalogue_contact_checks
        ),
        "component_stream_prefix_preserved": final_chunk.startswith(
            accepted_native_order_stream
        ),
        "accepted_native_order_stream_preserved": final_chunk.startswith(
            accepted_native_order_stream
        ),
        "component_record_order_mutation": bool(
            catalogue_leading_by_group_id
            or catalogue_component_stream_by_group_id
        ),
        "boundary_tail_normalizations": boundary_normalizations,
        "native_wire_boundary_checks": native_wire_boundary_checks,
        "native_wire_boundaries_valid": all(
            row["valid"] for row in native_wire_boundary_checks
        ),
        "bidir_count_before": original_chunk.count(BIDIR_MARKER),
        "bidir_count_after": final_chunk.count(BIDIR_MARKER),
        "wire_count_before": original_chunk.count(b"\x7fWIRE"),
        "wire_count_after": final_chunk.count(b"\x7fWIRE"),
        "object_chunk_size_before": len(original_chunk),
        "object_chunk_size_after": len(final_chunk),
        "object_chunk_double_ff_valid": final_chunk.endswith(b"\xff\xff"),
        "object_chunk_finalizer_valid": (
            final_chunk.endswith(b"\xff\xff")
            if object_stream_finalizer == "double_ff"
            else final_chunk.endswith(b"\xff")
        ),
        "base_component_stream_covered": True,
        "cdb_normalization": {
            "policy": "selected_package_rows_matching_proteus_ctrl_s",
            "keep_packages": cdb_keep_packages,
            "size_before": len(source_cdb),
            "size_after": len(normalized_cdb),
        },
        "valid": (
            final_chunk == new_chunk
            and final_chunk.count(BIDIR_MARKER) == expected_terminals
            and final_chunk.count(b"\x7fWIRE") == expected_wires
            and final_chunk.startswith(accepted_native_order_stream)
            and (
                final_chunk.endswith(b"\xff\xff")
                if object_stream_finalizer == "double_ff"
                else final_chunk.endswith(b"\xff")
            )
            and all(row["valid"] for row in native_wire_boundary_checks)
        ),
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
    """Plan donor-oracle two-pin terminals from body-relative pin geometry."""

    groups = tuple(selected_groups)
    families = {str(getattr(group, "family", "")) for group in groups}
    if len(families) != 1 or next(iter(families), "") not in GENERIC_TWO_PIN_PROFILES:
        raise ValueError(
            "The generic two-pin terminal handler requires one profiled family; "
            f"received {sorted(families)}."
        )
    family = next(iter(families))
    profile = GENERIC_TWO_PIN_PROFILES[family]
    geometry = _generic_two_pin_geometry_offsets(profile)
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
        left_pin_x = body_x + geometry["left_pin_offset"][0]
        left_pin_y = body_y + geometry["left_pin_offset"][1]
        right_pin_x = body_x + geometry["right_pin_offset"][0]
        right_pin_y = body_y + geometry["right_pin_offset"][1]
        left_contact_x = body_x + geometry["left_terminal_contact_offset"][0]
        left_contact_y = body_y + geometry["left_terminal_contact_offset"][1]
        right_contact_x = body_x + geometry["right_terminal_contact_offset"][0]
        right_contact_y = body_y + geometry["right_terminal_contact_offset"][1]
        left_suffix = (suffix_base + (index - 1) * 2 + 1) & 0xFFFF
        right_suffix = (suffix_base + (index - 1) * 2 + 2) & 0xFFFF
        left = TerminalSpec(
            label=_compact_terminal_label(
                prefix,
                (index - 1) * 2,
                min_digits=label_min_digits,
            ),
            symbol_x=left_contact_x - GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=left_contact_y,
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
            symbol_x=right_contact_x + GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN,
            symbol_y=right_contact_y,
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
                left_pin_y=left_pin_y,
                right_pin_x=right_pin_x,
                right_pin_y=right_pin_y,
                left_wire_start_x=left_contact_x,
                left_wire_start_y=left_contact_y,
                right_wire_start_x=right_contact_x,
                right_wire_start_y=right_contact_y,
                component_x_offset=x_offset,
                component_y_offset=y_offset,
                input_link_offset=input_link_offset,
                output_link_offset=output_link_offset,
            )
        )
    return tuple(pairs)


def _generic_two_pin_geometry_offsets(
    profile: dict[str, Any],
) -> dict[str, tuple[int, int]]:
    """Read validated body-relative pins/contact offsets for one two-pin family."""

    raw_geometry = profile.get("pin_geometry", {})
    if not isinstance(raw_geometry, dict):
        raise ValueError("Generic two-pin profile pin_geometry must be a mapping.")
    values: dict[str, tuple[int, int]] = {}
    for name, default in GENERIC_TWO_PIN_DEFAULT_GEOMETRY.items():
        raw = raw_geometry.get(name, default)
        if not isinstance(raw, (list, tuple)) or len(raw) != 2:
            raise ValueError(
                f"Generic two-pin profile {name} must contain exactly two offsets."
            )
        values[name] = (int(raw[0]), int(raw[1]))
    return values


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


def _patch_pair_link_trailer(
    data: bytes,
    pair: ResistorTerminalPair | CapacitorTerminalPair | SourceTerminalPair,
    *,
    trailer: bytes,
) -> bytes:
    """Set a donor-proven active-link trailer without changing its suffixes.

    The normal standalone two-pin writers retain their historically accepted
    ``0100`` field.  Proteus 8.13 canonicalizes active native links to
    ``0200`` when they share the hybrid mixed stream with catalogue terminal
    units.  Keeping this narrowly scoped helper lets the mixed writer emit the
    already-canonical form without changing the accepted standalone routes.
    """

    if trailer not in COMPONENT_PIN_LINK_TRAILERS:
        raise ValueError(f"Unsupported active component-link trailer {trailer.hex()}.")
    out = bytearray(data)
    for offset in (pair.input_link_offset, pair.output_link_offset):
        if offset + 4 > len(out):
            raise ValueError(
                f"{pair.component_family} {pair.component_key} packet ends before "
                "its active component-link trailer."
            )
        current = bytes(out[offset + 2 : offset + 4])
        if current not in COMPONENT_PIN_LINK_TRAILERS:
            raise ValueError(
                f"{pair.component_family} {pair.component_key} has unsupported "
                f"component-link trailer {current.hex()}."
            )
        out[offset + 2 : offset + 4] = trailer
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


def _build_catalogue_wire_unit(coordinates: Iterable[int]) -> bytes:
    values = tuple(int(value) for value in coordinates)
    if len(values) < 4 or len(values) % 2 != 0:
        raise ValueError(
            "Catalogue WIRE coordinates must contain at least two x/y points."
        )
    point_count = len(values) // 2
    if not 2 <= point_count <= 255:
        raise ValueError(f"Unsupported catalogue WIRE point count {point_count}.")
    prefix = NATIVE_WIRE_PREFIX[:-2] + struct.pack("<H", point_count)
    record = b"\x00" + prefix + struct.pack("<" + "i" * len(values), *values)
    if record.find(b"\x7fWIRE") != 24:
        raise AssertionError("Catalogue WIRE unit has an invalid marker position.")
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
    active_link_trailer: bytes = b"\x01\x00",
) -> bytes:
    record = build_bidir_record(
        templates,
        label=terminal.label,
        symbol_x=terminal.symbol_x,
        symbol_y=terminal.symbol_y,
        angle_tenths=terminal.angle_tenths,
        suffix=terminal.suffix if active_link else 0,
        active_link=active_link,
    )
    if not active_link:
        return record
    if active_link_trailer not in COMPONENT_PIN_LINK_TRAILERS:
        raise ValueError(
            f"Unsupported active terminal-link trailer {active_link_trailer.hex()}."
        )
    if record[-2:] != b"\x01\x00":
        raise ValueError("Base bidirectional terminal record lacks the active link trailer.")
    return record[:-2] + active_link_trailer


def _mixed_overlay_family_parts(
    family: str,
    groups: tuple[Any, ...],
    *,
    terminal_templates: Any,
    source_index_start: int,
    active_links: bool,
    active_link_trailer: bytes = b"\x01\x00",
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

    for group, pair in zip(groups, pairs, strict=True):
        if active_links and active_link_trailer != b"\x01\x00":
            patched_by_id[id(group)] = _patch_pair_link_trailer(
                patched_by_id[id(group)],
                pair,
                trailer=active_link_trailer,
            )

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
        elif family == "CAP":
            # The accepted capacitor stream is right terminal, left terminal,
            # component, right WIRE, left WIRE.  In a hybrid stream Proteus
            # rewrites a left/right WIRE order into this donor order on Ctrl+S.
            # Emit the donor order directly so the saved project is stable.
            wire_pairs.append(
                (
                    _build_native_short_wire(
                        pair.right_wire_start_x,
                        pair.right_wire_start_y,
                        pair.right_pin_x,
                        pair.right_pin_y,
                    ),
                    _build_native_short_wire(
                        pair.left_wire_start_x,
                        pair.left_wire_start_y,
                        pair.left_pin_x,
                        pair.left_pin_y,
                    ),
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
            active_link_trailer=active_link_trailer,
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
        point_count = int.from_bytes(chunk[marker + 8 : marker + 10], "little")
        full_coordinate_end = coordinate_start + point_count * 8
        if point_count < 2 or full_coordinate_end > len(chunk):
            raise ValueError(f"WIRE at object offset {marker} has invalid point count.")
        rows.append(
            {
                "marker_offset": marker,
                "coordinates": struct.unpack(
                    "<iiii",
                    chunk[coordinate_start : coordinate_start + 16],
                ),
                "point_count": point_count,
                "full_coordinates": struct.unpack(
                    "<" + "i" * (point_count * 2),
                    chunk[coordinate_start:full_coordinate_end],
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


def _ensure_single_ff_object_stream_terminator(chunk: bytes) -> bytes:
    """Return the donor-proven single-FF ending used by selected families."""

    if chunk.endswith(b"\xff\xff"):
        return chunk[:-1]
    if chunk.endswith(b"\xff"):
        return chunk
    return chunk + b"\xff"


def _append_explicit_single_ff_object_stream_terminator(chunk: bytes) -> bytes:
    """Append one structural FF without interpreting the final data byte.

    Proteus-opened NPN evidence proves that the high byte of the last WIRE
    coordinate may itself be ``0xff``.  Suffix-based de-duplication therefore
    cannot distinguish coordinate data from the object-stream terminator.
    This policy appends the one explicit terminator required by the donor
    grammar after the final WIRE record has been trimmed to its coordinate
    payload.
    """

    return chunk + b"\xff"


def _insert_attachment_units_before_packet_terminator(
    component_packet: bytes,
    attachment_units: Iterable[bytes],
    *,
    family: str,
    key: str,
) -> bytes:
    """Splice terminal/WIRE units at the donor-proven packet boundary.

    Accepted catalogue donors keep the component packet first, but the short
    terminal/WIRE attachment units replace the selected packet's final byte.
    The component placer's final ROOT.DSN stream overwrites that selected byte
    with the object-stream ``FF`` terminator, so preserving or moving the stale
    selected byte creates a malformed object tail that Proteus can open as an
    empty/faulty sheet.
    """

    if not component_packet:
        raise ValueError(
            f"{family} {key} component packet is empty; cannot perform "
            "terminal attachment splicing."
        )
    return component_packet[:-1] + b"".join(attachment_units)


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
    object order.  Pin coordinates are recorded relative to both the historic
    terminal-stripped component bbox minimum and, when available, the narrower
    component marker-body anchor.
    """

    source = Path(project)
    dsn = read_internal_file(source, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wire_rows = _wire_rows_from_chunk(chunk, chunk_start=0)
    wires_by_endpoint: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in wire_rows:
        for endpoint in _wire_coordinate_points(row["full_coordinates"]):
            wires_by_endpoint.setdefault(endpoint, []).append(row)
    wire_order_by_marker = {
        int(row["marker_offset"]): index
        for index, row in enumerate(
            sorted(wire_rows, key=lambda item: int(item["marker_offset"]))
        )
    }

    component_chunk = _component_only_chunk_from_terminalized_chunk(chunk)
    try:
        pairs = layout_coordinate_pairs(component_chunk, family)
    except ValueError:
        if component_chunk.startswith(b"\x00\x08\xff"):
            pairs = layout_coordinate_pairs(component_chunk[2:], family)
        else:
            raise
    bbox = coordinate_bbox(component_chunk, pairs) if pairs else {
        "min_x": 0,
        "min_y": 0,
        "max_x": 0,
        "max_y": 0,
        "width": 0,
        "height": 0,
    }
    component_anchor = _component_marker_anchor_for_catalogue(component_chunk, family)
    pin_rows: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for terminal in terminals:
        contact = _terminal_contact_xy(terminal)
        exact_candidates = [
            (0, row, contact) for row in wires_by_endpoint.get(contact, [])
        ]
        candidates: list[tuple[int, dict[str, Any], tuple[int, int]]] = exact_candidates
        if not candidates:
            nearby_candidates: list[tuple[int, dict[str, Any], tuple[int, int]]] = []
            for row in wire_rows:
                for endpoint in _wire_coordinate_points(row["full_coordinates"]):
                    distance = abs(contact[0] - endpoint[0]) + abs(contact[1] - endpoint[1])
                    if distance <= DONOR_TERMINAL_WIRE_ENDPOINT_TOLERANCE:
                        nearby_candidates.append((distance, row, endpoint))
            nearby_candidates.sort(
                key=lambda item: (
                    int(item[0]),
                    int(item[1]["marker_offset"]),
                    item[2][0],
                    item[2][1],
                )
            )
            candidates = nearby_candidates[:1]
        if not candidates:
            unmatched.append(
                {
                    "label": terminal["label"],
                    "terminal_contact": {"x": contact[0], "y": contact[1]},
                }
            )
            continue
        _distance, wire, matched_endpoint = candidates[0]
        x1, y1, x2, y2 = wire["coordinates"]
        other = _opposite_polyline_endpoint(
            wire["full_coordinates"],
            matched_endpoint,
        )
        pin, signal = _pin_label_parts(str(terminal["label"]))
        pin_key = pin or signal
        if not pin_key:
            pin_key = str(len(pin_rows) + 1)
        side = "left" if int(terminal["angle_tenths"]) == LEFT_SIDE_ANGLE else "right"
        pin_row = {
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
            "matched_wire_endpoint_x": matched_endpoint[0],
            "matched_wire_endpoint_y": matched_endpoint[1],
            "matched_wire_endpoint_distance": int(_distance),
            "wire_coordinates": [int(x1), int(y1), int(x2), int(y2)],
            "wire_unit_coordinates": [
                int(value) for value in wire["full_coordinates"]
            ],
            "wire_marker_offset": int(wire["marker_offset"]),
            "wire_order_index": wire_order_by_marker[int(wire["marker_offset"])],
            "evidence": "terminalized_donor_wire_endpoint",
        }
        if component_anchor is not None:
            pin_row.update(
                {
                    "x_offset_from_component_anchor": other[0]
                    - int(component_anchor["x"]),
                    "y_offset_from_component_anchor": other[1]
                    - int(component_anchor["y"]),
                }
            )
        pin_rows[pin_key] = pin_row

    return {
        "source_project": str(source),
        "family": family,
        "coordinate_frame": (
            "component_marker_anchor_from_terminal_stripped_donor_packet"
            if component_anchor is not None
            else "component_bbox_min_from_terminal_stripped_donor_packet"
        ),
        "component_bbox": bbox,
        "component_anchor": component_anchor,
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
    updated = False
    for family_report in report.get("family_reports", []):
        for row in family_report.get("terminal_pins", []):
            terminal = row.get("terminal")
            if isinstance(terminal, dict) and terminal.get("label") == old_label:
                terminal["label"] = new_label
                updated = True
        for pair in family_report.get("terminal_pairs", []):
            roles = ("left", "right") if "left" in pair else ("input", "output")
            for role in roles:
                terminal = pair.get(role)
                if isinstance(terminal, dict) and terminal.get("label") == old_label:
                    terminal["label"] = new_label
                    updated = True
    return updated


def _wire_record_spans(chunk: bytes) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", cursor)
        if marker < 0:
            return spans
        if marker >= 24 and chunk[marker - 24] == 0 and chunk[marker - 23] == 0x1D:
            start = marker - 24
            trailing_bytes = 0
        else:
            start = marker - 23
            trailing_bytes = 1
        if start < 0 or marker + 10 > len(chunk):
            raise ValueError(f"WIRE marker at {marker} starts before object chunk.")
        point_count = int.from_bytes(chunk[marker + 8 : marker + 10], "little")
        if point_count < 2:
            raise ValueError(f"WIRE marker at {marker} has invalid point count.")
        end = marker + 10 + point_count * 8 + trailing_bytes
        if end > len(chunk):
            raise ValueError(f"WIRE marker at {marker} ends after object chunk.")
        spans.append((start, end))
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
        active = (
            chunk[suffix_position + 2 : suffix_position + 4]
            in COMPONENT_PIN_LINK_TRAILERS
        )
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
            raw_coordinates = wire.get("coordinates")
            if (
                isinstance(raw_coordinates, (list, tuple))
                and len(raw_coordinates) >= 4
                and len(raw_coordinates) % 2 == 0
            ):
                coordinates = tuple(int(value) for value in raw_coordinates)
            else:
                coordinates = (
                    int(start["x"]),
                    int(start["y"]),
                    int(end["x"]),
                    int(end["y"]),
                )
            bindings.append(
                {
                    "component_key": row.get("component_key"),
                    "component_family": row.get("component_family"),
                    "role": row.get("pin", {}).get("name"),
                    "old_suffix": int(terminal["suffix"], 16),
                    "coordinates": coordinates,
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
                raw_coordinates = wire.get("coordinates")
                if (
                    isinstance(raw_coordinates, (list, tuple))
                    and len(raw_coordinates) >= 4
                    and len(raw_coordinates) % 2 == 0
                ):
                    coordinates = tuple(int(value) for value in raw_coordinates)
                else:
                    coordinates = (
                        int(start["x"]),
                        int(start["y"]),
                        int(end["x"]),
                        int(end["y"]),
                    )
                bindings.append(
                    {
                        "component_key": pair.get("component_key"),
                        "component_family": pair.get("component_family"),
                        "role": role,
                        "old_suffix": int(terminal["suffix"], 16),
                        "coordinates": coordinates,
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
    if label_jitter_events:
        bindings = _terminal_wire_bindings(report)

    available_by_coordinates: dict[
        tuple[int, int, int, int],
        list[dict[str, Any]],
    ] = {}
    for row in wire_rows:
        full_coordinates = row.get("full_coordinates", row["coordinates"])
        available_by_coordinates.setdefault(
            tuple(int(value) for value in full_coordinates),
            [],
        ).append(row)

    old_suffixes = [binding["old_suffix"] for binding in bindings]
    if len(old_suffixes) != len(set(old_suffixes)):
        duplicates = sorted(
            {
                suffix
                for suffix in old_suffixes
                if old_suffixes.count(suffix) > 1
            }
        )
        duplicate_context = [
            {
                "suffix": f"{binding['old_suffix']:04x}",
                "component_key": binding.get("component_key"),
                "component_family": binding.get("component_family"),
                "role": binding.get("role"),
                "label": binding.get("terminal", {}).get("label"),
            }
            for binding in bindings
            if binding["old_suffix"] in set(duplicates)
        ][:32]
        raise ValueError(
            "Family-local terminal suffixes collide before final rebasing: "
            f"{[f'{suffix:04x}' for suffix in duplicates[:16]]}; "
            f"context={duplicate_context}."
        )

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
        positions: list[int] = []
        suffix = struct.pack("<H", old_suffix)
        for trailer in COMPONENT_PIN_LINK_TRAILERS:
            pattern = suffix + trailer
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
    suffix_link_checks: list[dict[str, Any]] = []
    for allocation in allocations:
        terminal_position, component_position = patch_positions[allocation["old_suffix"]]
        suffix_bytes = struct.pack("<H", allocation["new_suffix"])
        terminal_field = written_chunk[terminal_position : terminal_position + 4]
        component_field = written_chunk[component_position : component_position + 4]
        terminal_valid = (
            terminal_field[:2] == suffix_bytes
            and terminal_field[2:4] in COMPONENT_PIN_LINK_TRAILERS
        )
        component_valid = (
            component_field[:2] == suffix_bytes
            and component_field[2:4] in COMPONENT_PIN_LINK_TRAILERS
        )
        suffix_link_checks.append(
            {
                "component_key": allocation["component_key"],
                "component_family": allocation["component_family"],
                "role": allocation["role"],
                "suffix": f"{allocation['new_suffix']:04x}",
                "terminal_suffix_position": terminal_position,
                "component_link_position": component_position,
                "terminal_trailer": terminal_field[2:4].hex(),
                "component_trailer": component_field[2:4].hex(),
                "terminal_valid": terminal_valid,
                "component_valid": component_valid,
            }
        )
    report["terminal_suffix_link_checks"] = suffix_link_checks
    report["terminal_suffix_links_valid"] = all(
        row["terminal_valid"] and row["component_valid"]
        for row in suffix_link_checks
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
                "component_link_trailer": written_chunk[
                    allocation["component_link_position"] + 2
                    : allocation["component_link_position"] + 4
                ].hex(),
                "coordinates": list(allocation["coordinates"]),
            }
            for allocation in allocations
        ],
        "valid": (
            report["terminal_suffixes_unique"]
            and report["terminal_suffix_links_valid"]
        ),
    }
    expected_wire_count = int(report.get("wire_count_added") or 0) + int(
        report.get("wire_count_rewritten") or 0
    )
    require_double_ff = (
        str(report.get("family_handler", "")).startswith("CATALOGUE/")
        and report.get("object_stream_finalizer", "double_ff") == "double_ff"
    )
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
