"""Deterministic pin normalization rules for Proteus 74-series IC input.

This module does not emit Proteus records. It normalizes user-facing DIP pin
language into the Proteus subpart model used by the accepted IC donors.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ICPinMapping:
    device: str
    physical_pin: str
    action: str
    proteus_ref: str | None
    subpart: str | None
    role: str
    circuit_ir_pin: str | None

    @property
    def is_hidden_supply(self) -> bool:
        return self.action == "ignore_hidden_supply"


HC08_PIN_MAP: Mapping[str, ICPinMapping] = {
    "1": ICPinMapping("74HC08", "1", "connect", "U1:A", "A", "IN1", "1"),
    "2": ICPinMapping("74HC08", "2", "connect", "U1:A", "A", "IN2", "2"),
    "3": ICPinMapping("74HC08", "3", "connect", "U1:A", "A", "OUT", "3"),
    "4": ICPinMapping("74HC08", "4", "connect", "U1:B", "B", "IN1", "4"),
    "5": ICPinMapping("74HC08", "5", "connect", "U1:B", "B", "IN2", "5"),
    "6": ICPinMapping("74HC08", "6", "connect", "U1:B", "B", "OUT", "6"),
    "7": ICPinMapping("74HC08", "7", "ignore_hidden_supply", None, None, "GND", None),
    "8": ICPinMapping("74HC08", "8", "connect", "U1:C", "C", "OUT", "8"),
    "9": ICPinMapping("74HC08", "9", "connect", "U1:C", "C", "IN1", "9"),
    "10": ICPinMapping("74HC08", "10", "connect", "U1:C", "C", "IN2", "10"),
    "11": ICPinMapping("74HC08", "11", "connect", "U1:D", "D", "OUT", "11"),
    "12": ICPinMapping("74HC08", "12", "connect", "U1:D", "D", "IN1", "12"),
    "13": ICPinMapping("74HC08", "13", "connect", "U1:D", "D", "IN2", "13"),
    "14": ICPinMapping("74HC08", "14", "ignore_hidden_supply", None, None, "VCC", None),
}

HC08_PIN_ALIASES: Mapping[str, str] = {
    "1A": "1",
    "G1A": "1",
    "GATE1A": "1",
    "GATE1IN1": "1",
    "2": "2",
    "1B": "2",
    "G1B": "2",
    "GATE1B": "2",
    "GATE1IN2": "2",
    "1Y": "3",
    "G1Y": "3",
    "GATE1Y": "3",
    "GATE1OUT": "3",
    "2A": "4",
    "G2A": "4",
    "GATE2A": "4",
    "GATE2IN1": "4",
    "2B": "5",
    "G2B": "5",
    "GATE2B": "5",
    "GATE2IN2": "5",
    "2Y": "6",
    "G2Y": "6",
    "GATE2Y": "6",
    "GATE2OUT": "6",
    "GND": "7",
    "0V": "7",
    "VSS": "7",
    "3Y": "8",
    "G3Y": "8",
    "GATE3Y": "8",
    "GATE3OUT": "8",
    "3A": "9",
    "G3A": "9",
    "GATE3A": "9",
    "GATE3IN1": "9",
    "3B": "10",
    "G3B": "10",
    "GATE3B": "10",
    "GATE3IN2": "10",
    "4Y": "11",
    "G4Y": "11",
    "GATE4Y": "11",
    "GATE4OUT": "11",
    "4A": "12",
    "G4A": "12",
    "GATE4A": "12",
    "GATE4IN1": "12",
    "4B": "13",
    "G4B": "13",
    "GATE4B": "13",
    "GATE4IN2": "13",
    "VCC": "14",
    "+5V": "14",
    "5V": "14",
    "VDD": "14",
}


def _normalize_pin_token(pin: str | int) -> str:
    token = str(pin).strip().upper()
    for prefix in ("PIN", "P"):
        if token.startswith(prefix):
            token = token[len(prefix) :].strip()
            break
    return "".join(ch for ch in token if ch.isalnum() or ch in "+")


def normalize_74hc08_pin(pin: str | int) -> ICPinMapping:
    """Return the accepted Proteus subpart mapping for a 74HC08 DIP pin token."""

    token = _normalize_pin_token(pin)
    physical_pin = HC08_PIN_ALIASES.get(token, token)
    try:
        return HC08_PIN_MAP[physical_pin]
    except KeyError as exc:
        raise ValueError(f"Unsupported 74HC08 pin token: {pin!r}") from exc


def normalize_74hc08_connection(component_ref: str, pin: str | int, net: str) -> dict[str, str] | None:
    """Normalize a user DIP-pin connection to a CircuitIR connection.

    Hidden supply pins 14/VCC and 7/GND return ``None`` because Proteus handles
    combinational 74HC08 power internally in the accepted donor path.
    """

    mapping = normalize_74hc08_pin(pin)
    if mapping.is_hidden_supply:
        return None
    assert mapping.circuit_ir_pin is not None
    return {"component": component_ref, "pin": mapping.circuit_ir_pin, "net": net}
