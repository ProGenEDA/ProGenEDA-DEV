"""Packet-safe component coordinate helpers.

This module owns experimental binary coordinate movement for complete
donor-derived component packets. The default is intentionally no mutation:
Proteus coordinate bytes are fragile, and packet movement must be enabled only
inside focused tests until user acceptance.
"""

from __future__ import annotations

HIDDEN_COORD_DX = 1_500_000_000
HIDDEN_COORD_DY = 1_500_000_000
HIDDEN_ABSOLUTE_X = 1_500_000_000
HIDDEN_ABSOLUTE_Y = 1_500_000_000
HIDDEN_PACKET_START = -1_000_000_000
DEFAULT_HIDDEN_COORDINATE_MODE = "none"

LINKED_COORDINATE_PLANS: dict[str, tuple[tuple[int, int], ...]] = {
    "SWITCH": ((2, 6), (68, 72), (143, 147), (208, 212), (359, 363)),
    "POT-HG": ((5, 9), (73, 77), (148, 152), (213, 217), (393, 397)),
    "DISPLAY_BRIDGE": ((5, 9), (76, 80), (150, 154), (215, 219), (343, 347)),
}

RELATIVE_MODES = {"relative", "linked_relative", "runaway_relative"}
ABSOLUTE_MODES = {"absolute", "linked_absolute", "runaway_absolute"}
NOOP_MODES = {"", "none", "off", "metadata_only", "disabled"}


def _s32_at(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32_at(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = int(value).to_bytes(4, "little", signed=True)


def coordinate_plan_for_family(family: str) -> tuple[tuple[int, int], ...]:
    try:
        return LINKED_COORDINATE_PLANS[family]
    except KeyError as exc:
        raise ValueError(f"No packet coordinate plan is proven for {family}.") from exc


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
        f"expected one of {sorted(NOOP_MODES | RELATIVE_MODES | ABSOLUTE_MODES)}."
    )


def hide_packet(
    family: str,
    data: bytes,
    *,
    mode: str = DEFAULT_HIDDEN_COORDINATE_MODE,
) -> bytes:
    return move_packet_coordinates(family, data, mode=mode)
