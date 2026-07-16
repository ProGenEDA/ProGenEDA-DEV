"""Canonical JSON adapter for the independent EasyEDA backend."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .catalogue import get_entry, normalize_kind
from .donor_source import DonorPacket, PinDescriptor


IR_SCHEMA = "progen-easyeda-circuit-ir/v1"
MAX_COMPONENTS = 80
ROUTING_MODES = {"wire", "terminal", "combination"}


class CircuitInputError(ValueError):
    """The input cannot be normalized without changing circuit meaning."""


@dataclass(frozen=True)
class CircuitComponent:
    identifier: str
    reference: str
    kind: str
    value: str
    role: str
    block: str
    pins: dict[str, str]


@dataclass(frozen=True)
class Circuit:
    name: str
    title: str
    routing_mode: str
    components: tuple[CircuitComponent, ...]
    nets: dict[str, tuple[str, ...]]
    source: dict[str, Any]

    def normalized_json(self) -> dict[str, Any]:
        return {
            "schema_version": IR_SCHEMA,
            "project": {"name": self.name, "title": self.title, "target": "easyeda_pro"},
            "routing": {"mode": self.routing_mode},
            "components": [
                {
                    "id": component.identifier,
                    "ref": component.reference,
                    "kind": component.kind,
                    "value": component.value,
                    "role": component.role,
                    "block": component.block,
                    "pins": dict(sorted(component.pins.items())),
                }
                for component in self.components
            ],
            "nets": [
                {"name": name, "members": list(members)}
                for name, members in sorted(self.nets.items())
            ],
        }


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.+-]+")


def _slug(value: object) -> str:
    text = _SAFE_NAME.sub("_", str(value or "").strip()).strip("_.")
    return text or "easyeda_project"


def _load(value: Path | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    path = Path(value).expanduser().resolve()
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CircuitInputError(f"Cannot read circuit JSON {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise CircuitInputError("Circuit input must be one JSON object.")
    return parsed


def _component_kind(raw: Mapping[str, Any]) -> str:
    for key in ("kind", "type", "component", "family", "name"):
        if raw.get(key):
            try:
                return normalize_kind(raw[key])
            except ValueError:
                continue
    offered = raw.get("kind") or raw.get("type") or raw.get("component") or raw.get("name")
    raise CircuitInputError(f"Unsupported EasyEDA component kind {offered!r}.")


def _pins(raw: Mapping[str, Any]) -> dict[str, str]:
    pins_value = raw.get("pins", raw.get("connections", {}))
    result: dict[str, str] = {}
    if isinstance(pins_value, Mapping):
        iterable = pins_value.items()
    elif isinstance(pins_value, list):
        iterable = []
        for item in pins_value:
            if not isinstance(item, Mapping):
                raise CircuitInputError("Component pin lists must contain objects.")
            pin = item.get("pin") or item.get("number") or item.get("name")
            net = item.get("net") or item.get("node")
            iterable.append((pin, net))
    else:
        raise CircuitInputError("Component pins must be an object or list.")
    for pin, net in iterable:
        pin_text = str(pin or "").strip()
        net_text = str(net or "").strip()
        if not pin_text or not net_text:
            raise CircuitInputError("Every component pin binding needs a non-empty pin and net.")
        if pin_text in result and result[pin_text] != net_text:
            raise CircuitInputError(f"Pin {pin_text!r} is assigned to multiple nets.")
        result[pin_text] = net_text
    return result


def _top_level_nets(raw: Mapping[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    value = raw.get("nets", [])
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, list):
        items = []
        for item in value:
            if not isinstance(item, Mapping):
                continue
            name = item.get("name") or item.get("net")
            members = item.get("members") or item.get("nodes") or item.get("connections") or []
            items.append((name, members))
    else:
        raise CircuitInputError("Top-level nets must be an object or list.")
    for name, members in items:
        net_name = str(name or "").strip()
        if not net_name:
            continue
        if isinstance(members, str):
            members = [members]
        if not isinstance(members, list):
            raise CircuitInputError(f"Net {net_name!r} members must be a list.")
        result.setdefault(net_name, set()).update(str(member).strip() for member in members if str(member).strip())
    return result


def load_circuit(
    value: Path | str | Mapping[str, Any],
    *,
    routing_mode: str | None = None,
) -> Circuit:
    """Normalize the shared JSON contract without importing another backend."""

    raw = _load(value)
    project = raw.get("project") if isinstance(raw.get("project"), Mapping) else {}
    name = _slug(project.get("name") or raw.get("circuit_id") or raw.get("name") or "easyeda_project")
    title = str(project.get("title") or raw.get("circuit_name") or name).strip() or name
    routing = raw.get("routing") if isinstance(raw.get("routing"), Mapping) else {}
    selected_mode = str(routing_mode or routing.get("mode") or raw.get("routing_mode") or "combination").lower()
    if selected_mode not in ROUTING_MODES:
        raise CircuitInputError(f"Routing mode must be one of {sorted(ROUTING_MODES)}.")

    raw_components = raw.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        raise CircuitInputError("Circuit input needs a non-empty components list.")
    if len(raw_components) > MAX_COMPONENTS:
        raise CircuitInputError(f"EasyEDA supports at most {MAX_COMPONENTS} input components; received {len(raw_components)}.")

    components: list[CircuitComponent] = []
    seen_ids: set[str] = set()
    seen_refs: set[str] = set()
    for index, item in enumerate(raw_components, start=1):
        if not isinstance(item, Mapping):
            raise CircuitInputError(f"Component {index} must be an object.")
        kind = _component_kind(item)
        entry = get_entry(kind)
        identifier = str(item.get("id") or item.get("ref") or f"{entry.reference_prefix}{index}").strip()
        reference = str(item.get("ref") or item.get("reference") or identifier).strip()
        if not identifier or identifier in seen_ids:
            raise CircuitInputError(f"Component id {identifier!r} is empty or duplicated.")
        if not reference or reference in seen_refs:
            raise CircuitInputError(f"Component reference {reference!r} is empty or duplicated.")
        seen_ids.add(identifier)
        seen_refs.add(reference)
        pins = _pins(item)
        if kind == "GND" and not pins:
            pins = {"1": "GND"}
        elif kind == "VCC" and not pins:
            pins = {"1": str(item.get("value") or item.get("net") or "VCC")}
        components.append(
            CircuitComponent(
                identifier=identifier,
                reference=reference,
                kind=kind,
                value=str(item.get("value") or item.get("name") or kind),
                role=str(item.get("role") or ""),
                block=str(item.get("block") or "main"),
                pins=pins,
            )
        )

    nets: dict[str, set[str]] = _top_level_nets(raw)
    endpoint_to_net: dict[str, str] = {}
    for component in components:
        for pin, net in component.pins.items():
            endpoint = f"{component.reference}.{pin}"
            previous = endpoint_to_net.setdefault(endpoint, net)
            if previous != net:
                raise CircuitInputError(f"Endpoint {endpoint} is assigned to both {previous!r} and {net!r}.")
            nets.setdefault(net, set()).add(endpoint)
    for net_name, members in nets.items():
        for endpoint in members:
            previous = endpoint_to_net.get(endpoint)
            if previous is not None and previous != net_name:
                raise CircuitInputError(
                    f"Top-level net {net_name!r} conflicts with component pin assignment {endpoint} -> {previous!r}."
                )
    expected = raw.get("expected_netlist")
    if isinstance(expected, Mapping):
        for net_name, members in expected.items():
            if isinstance(members, Mapping):
                members = members.get("members", [])
            if isinstance(members, list):
                expected_set = {str(member).strip() for member in members if str(member).strip()}
                actual_set = nets.get(str(net_name), set())
                if actual_set and expected_set and actual_set != expected_set:
                    raise CircuitInputError(
                        f"expected_netlist disagrees with component pins for {net_name!r}: "
                        f"{sorted(expected_set)} != {sorted(actual_set)}"
                    )
                nets.setdefault(str(net_name), set()).update(expected_set)
    return Circuit(
        name=name,
        title=title,
        routing_mode=selected_mode,
        components=tuple(components),
        nets={name: tuple(sorted(members)) for name, members in nets.items()},
        source=raw,
    )


def _pin_token(value: object) -> str:
    return re.sub(r"[^A-Za-z0-9+-]+", "", str(value or "").upper().lstrip("/"))


_PIN_ALIASES: dict[str, tuple[str, ...]] = {
    "K": ("K", "C", "CATHODE"),
    "CATHODE": ("K", "C", "CATHODE"),
    "A": ("A", "ANODE"),
    "ANODE": ("A", "ANODE"),
    "POS": ("POS", "+"),
    "+": ("+", "POS"),
    "NEG": ("NEG", "-"),
    "-": ("-", "NEG"),
    "VIN": ("VIN", "IN"),
    "VOUT": ("VOUT", "OUT"),
    "GROUND": ("GROUND", "GND", "VSS"),
    "GND": ("GND", "GROUND", "VSS"),
    "VCC": ("VCC", "VDD", "+5V", "5V", "3V3"),
}

_PROFILE_PIN_NUMBERS: dict[str, dict[str, str]] = {
    "DIODE": {"K": "1", "CATHODE": "1", "A": "2", "ANODE": "2"},
    "1N4007": {"K": "1", "CATHODE": "1", "A": "2", "ANODE": "2"},
    "1N4148": {"K": "1", "CATHODE": "1", "A": "2", "ANODE": "2"},
    "LED": {"A": "1", "ANODE": "1", "K": "2", "CATHODE": "2"},
    "CAP_ELEC": {"POS": "1", "+": "1", "NEG": "2", "-": "2"},
    "SPST_SWITCH": {"1": "A", "A": "A", "2": "B", "B": "B"},
    "NPN": {"E": "1", "B": "2", "C": "3"},
    "PNP": {"E": "1", "B": "2", "C": "3"},
    "NMOS": {"S": "1", "G": "2", "D": "3"},
    "LM7805": {"IN": "1", "VIN": "1", "VCC": "1", "GND": "2", "OUT": "3", "VOUT": "3", "TAB": "4"},
    "LM317": {"ADJ": "1", "OUT": "2", "VOUT": "2", "IN": "3", "VIN": "3", "TAB": "4"},
    "BRIDGE_RECTIFIER": {"AC1": "1", "POS": "2", "+": "2", "AC2": "3", "NEG": "4", "-": "4"},
    "ESP32_WROOM": {"GND": "1", "GND2": "15", "GND3": "38", "GND4": "39"},
    "BME280": {"GND": "1", "GND2": "7"},
    "CP2102": {"GND": "3", "EP": "29"},
}


def resolve_pin(packet: DonorPacket, requested: str) -> PinDescriptor:
    """Resolve a logical pin only through donor number/name descriptors."""

    requested_token = _pin_token(requested)
    profiled_number = _PROFILE_PIN_NUMBERS.get(packet.kind, {}).get(requested_token)
    if profiled_number is not None:
        profiled = [pin for pin in packet.pins if pin.number == profiled_number]
        if len(profiled) == 1:
            return profiled[0]
    candidates = (requested_token,) + _PIN_ALIASES.get(requested_token, ())
    candidate_tokens = {_pin_token(candidate) for candidate in candidates}
    exact: list[PinDescriptor] = []
    for pin in packet.pins:
        if _pin_token(pin.number) in candidate_tokens or _pin_token(pin.name) in candidate_tokens:
            exact.append(pin)
    unique = {(pin.number, pin.name): pin for pin in exact}
    if len(unique) == 1:
        return next(iter(unique.values()))
    if not unique and requested_token.isdigit():
        numeric = [pin for pin in packet.pins if pin.number == requested_token]
        if len(numeric) == 1:
            return numeric[0]
    available = ", ".join(f"{pin.number}:{pin.name}" for pin in packet.pins)
    if not unique:
        raise CircuitInputError(
            f"{packet.kind} donor {packet.resolved_title!r} has no pin matching {requested!r}; available: {available}."
        )
    matches = ", ".join(f"{pin.number}:{pin.name}" for pin in unique.values())
    raise CircuitInputError(
        f"{packet.kind} pin {requested!r} is ambiguous in donor {packet.resolved_title!r}: {matches}."
    )
