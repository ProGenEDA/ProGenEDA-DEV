"""Canonical circuit JSON preflight for the independent Altium backend.

This module intentionally has no imports from any other ProGenEDA backend.
It captures logical circuit intent only; native symbol, footprint, and pad
resolution is deferred until an Altium donor catalogue has been audited.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Mapping


IR_SCHEMA = "progen-altium-circuit-ir/v1"
ROUTING_MODES = frozenset({"wire", "terminal", "combination"})
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.+-]+")


class CircuitInputError(ValueError):
    """The canonical input is internally inconsistent or incomplete."""


@dataclass(frozen=True)
class AltiumComponent:
    """One logical component prior to Altium source-record resolution."""

    identifier: str
    reference: str
    kind: str
    value: str
    role: str
    block: str
    pins: dict[str, str]


@dataclass(frozen=True)
class AltiumCircuit:
    """Normalized circuit intent shared by future Altium stages."""

    name: str
    title: str
    routing_mode: str
    components: tuple[AltiumComponent, ...]
    nets: dict[str, tuple[str, ...]]
    source: dict[str, Any]

    def normalized_json(self) -> dict[str, Any]:
        return {
            "schema_version": IR_SCHEMA,
            "project": {"name": self.name, "title": self.title, "target": "altium"},
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


def _slug(value: object) -> str:
    text = _SAFE_NAME.sub("_", str(value or "").strip()).strip("_.")
    return text or "altium_project"


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


def _pins(raw: Mapping[str, Any]) -> dict[str, str]:
    value = raw.get("pins", raw.get("connections", {}))
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, list):
        collected: list[tuple[object, object]] = []
        for item in value:
            if not isinstance(item, Mapping):
                raise CircuitInputError("Component pin lists must contain objects.")
            collected.append(
                (
                    item.get("pin") or item.get("number") or item.get("name"),
                    item.get("net") or item.get("node"),
                )
            )
        items = collected
    else:
        raise CircuitInputError("Component pins must be an object or list.")

    result: dict[str, str] = {}
    for pin, net in items:
        pin_text = str(pin or "").strip()
        net_text = str(net or "").strip()
        if not pin_text or not net_text:
            raise CircuitInputError("Every component pin binding needs a non-empty pin and net.")
        prior = result.setdefault(pin_text, net_text)
        if prior != net_text:
            raise CircuitInputError(f"Pin {pin_text!r} is assigned to multiple nets.")
    return result


def _top_level_nets(raw: Mapping[str, Any]) -> dict[str, set[str]]:
    value = raw.get("nets", [])
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, list):
        collected: list[tuple[object, object]] = []
        for item in value:
            if not isinstance(item, Mapping):
                raise CircuitInputError("Top-level nets must contain objects.")
            collected.append(
                (
                    item.get("name") or item.get("net"),
                    item.get("members") or item.get("nodes") or item.get("connections") or [],
                )
            )
        items = collected
    else:
        raise CircuitInputError("Top-level nets must be an object or list.")

    result: dict[str, set[str]] = {}
    for name, members in items:
        net_name = str(name or "").strip()
        if not net_name:
            continue
        if isinstance(members, str):
            members = [members]
        if not isinstance(members, list):
            raise CircuitInputError(f"Net {net_name!r} members must be a list.")
        result.setdefault(net_name, set()).update(
            str(member).strip() for member in members if str(member).strip()
        )
    return result


def load_circuit(
    value: Path | str | Mapping[str, Any],
    *,
    routing_mode: str | None = None,
) -> AltiumCircuit:
    """Normalize the common JSON shape without inferring electrical intent."""

    raw = _load(value)
    project = raw.get("project") if isinstance(raw.get("project"), Mapping) else {}
    name = _slug(project.get("name") or raw.get("circuit_id") or raw.get("name") or "altium_project")
    title = str(project.get("title") or raw.get("circuit_name") or name).strip() or name
    routing = raw.get("routing") if isinstance(raw.get("routing"), Mapping) else {}
    selected_mode = str(
        routing_mode or routing.get("mode") or raw.get("routing_mode") or "combination"
    ).lower()
    if selected_mode not in ROUTING_MODES:
        raise CircuitInputError(f"Routing mode must be one of {sorted(ROUTING_MODES)}.")

    raw_components = raw.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        raise CircuitInputError("Circuit input needs a non-empty components list.")

    components: list[AltiumComponent] = []
    seen_ids: set[str] = set()
    seen_refs: set[str] = set()
    for index, item in enumerate(raw_components, start=1):
        if not isinstance(item, Mapping):
            raise CircuitInputError(f"Component {index} must be an object.")
        kind = str(
            item.get("kind")
            or item.get("type")
            or item.get("component")
            or item.get("family")
            or item.get("name")
            or ""
        ).strip()
        if not kind:
            raise CircuitInputError(f"Component {index} has no kind.")
        identifier = str(item.get("id") or item.get("ref") or f"C{index}").strip()
        reference = str(item.get("ref") or item.get("reference") or identifier).strip()
        if not identifier or identifier in seen_ids:
            raise CircuitInputError(f"Component id {identifier!r} is empty or duplicated.")
        if not reference or reference in seen_refs:
            raise CircuitInputError(f"Component reference {reference!r} is empty or duplicated.")
        seen_ids.add(identifier)
        seen_refs.add(reference)
        components.append(
            AltiumComponent(
                identifier=identifier,
                reference=reference,
                kind=kind,
                value=str(item.get("value") or item.get("name") or kind),
                role=str(item.get("role") or ""),
                block=str(item.get("block") or "main"),
                pins=_pins(item),
            )
        )

    nets = _top_level_nets(raw)
    endpoint_to_net: dict[str, str] = {}
    for component in components:
        for pin, net in component.pins.items():
            endpoint = f"{component.reference}.{pin}"
            prior = endpoint_to_net.setdefault(endpoint, net)
            if prior != net:
                raise CircuitInputError(
                    f"Endpoint {endpoint!r} is assigned to both {prior!r} and {net!r}."
                )
            nets.setdefault(net, set()).add(endpoint)

    for net_name, members in nets.items():
        for endpoint in members:
            declared = endpoint_to_net.get(endpoint)
            if declared is None:
                raise CircuitInputError(
                    f"Top-level net {net_name!r} references undeclared endpoint {endpoint!r}; "
                    "declare the pin in the matching component's pins object."
                )
            if declared != net_name:
                raise CircuitInputError(
                    f"Top-level net {net_name!r} conflicts with component pin assignment "
                    f"{endpoint} -> {declared!r}."
                )

    expected = raw.get("expected_netlist")
    if isinstance(expected, Mapping):
        for net_name, members in expected.items():
            if isinstance(members, Mapping):
                members = members.get("members", [])
            if not isinstance(members, list):
                raise CircuitInputError(f"expected_netlist for {net_name!r} must be a list.")
            expected_members = {str(member).strip() for member in members if str(member).strip()}
            actual_members = nets.get(str(net_name), set())
            if expected_members != actual_members:
                raise CircuitInputError(
                    f"expected_netlist disagrees with component pins for {net_name!r}: "
                    f"{sorted(expected_members)} != {sorted(actual_members)}."
                )

    return AltiumCircuit(
        name=name,
        title=title,
        routing_mode=selected_mode,
        components=tuple(components),
        nets={name: tuple(sorted(members)) for name, members in sorted(nets.items())},
        source=raw,
    )
