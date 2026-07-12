"""Translate shared logical endpoint identities to LTspice SpiceOrder pins.

Canonical ProGenEDA pin numbers are backend-neutral identities, not an
invitation to reuse a KiCad package number as an LTspice symbol SpiceOrder.
The LTspice profile catalogue owns every translation.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .component_selector import SelectedComponent


PIN_MAPPER_SCHEMA = "progen-ltspice-native-pin-mapper/v0.1"


def _translate_endpoint(endpoint: object, selected_by_ref: dict[str, SelectedComponent]) -> tuple[str, dict[str, str]]:
    text = str(endpoint).strip()
    if "." not in text:
        raise ValueError(f"Canonical endpoint {text!r} has no REF.PIN separator.")
    ref, canonical_pin = text.rsplit(".", 1)
    selected = selected_by_ref.get(ref)
    if selected is None:
        raise ValueError(f"Canonical endpoint {text!r} refers to an unselected component.")
    native_pin = selected.profile.native_pin_for_canonical(canonical_pin)
    if native_pin is None:
        raise ValueError(f"{text}: {selected.profile.kind} has no LTspice mapping for canonical pin {canonical_pin!r}.")
    translated = f"{ref}.{native_pin}"
    return translated, {"canonical": text, "native": translated}


def translate_circuit_pins(circuit: dict[str, Any], selected: list[SelectedComponent]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a native-endpoint view of one canonical circuit and its audit map."""

    result = deepcopy(circuit)
    selected_by_ref = {item.ref: item for item in selected}
    component_audit: dict[str, dict[str, str]] = {}
    components = result.get("components")
    if not isinstance(components, list):
        raise ValueError("Canonical circuit has no components array for LTspice pin translation.")
    for component in components:
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or component.get("id") or "")
        selected_component = selected_by_ref.get(ref)
        if selected_component is None:
            continue
        component["pins"] = dict(selected_component.pins)
        component_audit[ref] = dict(selected_component.canonical_to_native)

    endpoint_audit: list[dict[str, str]] = []
    nets = result.get("nets")
    if not isinstance(nets, dict):
        raise ValueError("Canonical circuit has no nets object for LTspice pin translation.")
    translated_nets: dict[str, list[str]] = {}
    for net, members in nets.items():
        if not isinstance(members, list):
            raise ValueError(f"Canonical net {net!r} is not an endpoint list.")
        translated_members: list[str] = []
        for endpoint in members:
            translated, audit = _translate_endpoint(endpoint, selected_by_ref)
            endpoint_audit.append(audit)
            if translated not in translated_members:
                translated_members.append(translated)
        translated_nets[str(net)] = translated_members
    result["nets"] = translated_nets

    expected = result.get("expected_netlist")
    if isinstance(expected, dict) and isinstance(expected.get("nets"), list):
        for net in expected["nets"]:
            if not isinstance(net, dict) or not isinstance(net.get("members"), list):
                continue
            translated_members: list[str] = []
            for endpoint in net["members"]:
                translated, audit = _translate_endpoint(endpoint, selected_by_ref)
                endpoint_audit.append(audit)
                if translated not in translated_members:
                    translated_members.append(translated)
            net["members"] = translated_members

    return result, {
        "schema": PIN_MAPPER_SCHEMA,
        "stage": "ltspice_native_pin_mapper",
        "ok": True,
        "component_pin_maps": component_audit,
        "endpoint_translations": endpoint_audit,
    }
