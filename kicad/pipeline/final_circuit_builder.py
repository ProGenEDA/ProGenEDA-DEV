"""Deterministic final CircuitIR builder for connected KiCad tests.

This module is the first non-AI implementation of the "prompt to final JSON"
compiler path. It intentionally keeps AI out of the trusted final JSON:

User prompt -> deterministic prompt cleaner -> raw circuit spec -> compiler
-> validator -> canonical CircuitIR JSON.

The current raw specs are the ten connected test circuits supplied by the user.
They are used to exercise the arrangement decider, beautifier, and wire planner
with real pin-level nets instead of component-only placement inputs.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import slugify

from .arrangement_decider import decide_arrangement
from .beautifier import apply_coordinate_edits
from .placement_catalog import resolve_placement_spec
from .placer_pipeline import run_placer_pipeline
from .wire_planner import plan_wire_routes


SCHEMA_VERSION = "progen-kicad-circuit-ir/v1"
PROMPT_CLEANER_VERSION = "progeneda-prompt-cleaner/v0.1"
COMPILER_VERSION = "progeneda-final-circuit-builder/v0.1"
DEFAULT_FINAL_CIRCUIT_SUITE = "t01_t10"
PROTEUS_ALIAS_MIXED_SUITE = "proteus_alias_mixed"
PROTEUS_ALIAS_ROUTED_SUITE = "proteus_alias_routed"

POWER_NET_PRIORITY = ("GND", "+5V", "+3V3", "VCC", "VDD", "VIN", "VBUS", "VBAT")
POWER_NETS = set(POWER_NET_PRIORITY)
NO_CONNECT = {"NC", "N/C", "NO_CONNECT", "UNCONNECTED"}
STAGE_REPORT_WIRE_CONFIG = {
    "grid": 1.27,
    "wire_spacing": 2.54,
    "clearance": 1.27,
    "max_astar_expansions": 50_000.0,
    "max_wired_routes": 180.0,
}


def clean_prompt(prompt: str) -> dict[str, Any]:
    """Return a deterministic non-AI prompt-enhancement record.

    This is deliberately conservative. It cleans spacing, preserves the user's
    original wording, extracts a few stable hints, and prepares a clean prompt
    string for a future AI intent extractor. It does not invent circuitry.
    """
    original = str(prompt)
    normalized = original.replace("\r\n", "\n").replace("\r", "\n").strip()
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    lower = normalized.lower()
    detected_domains = sorted(
        token
        for token in (
            "arduino",
            "esp32",
            "i2c",
            "spi",
            "can",
            "rs485",
            "mosfet",
            "relay",
            "audio",
            "power",
            "sensor",
            "display",
        )
        if token in lower
    )
    requested_counts = []
    for match in re.finditer(r"\b(\d+)\s*[xX]?\s+([A-Za-z][A-Za-z0-9_\- ]{1,48})", normalized):
        token = re.split(r"\s+(?:with|and|plus|for|using)\s+|[,.;:]", match.group(2), maxsplit=1)[0].strip()
        requested_counts.append({"token": token, "quantity": int(match.group(1))})
    return {
        "schema": PROMPT_CLEANER_VERSION,
        "stage": "prompt_cleaner",
        "original_prompt": original,
        "cleaned_prompt": normalized,
        "detected_domains": detected_domains,
        "requested_counts": requested_counts,
        "next_stage_contract": {
            "ai_allowed": "intent extraction and block choice only",
            "deterministic_required": "component allocation, reference allocation, net compilation, validation, repair, final JSON acceptance",
        },
    }


def _c(ref: str, kind: str, value: str, role: str = "", block: str = "") -> dict[str, str]:
    return {"ref": ref, "kind": kind, "value": value, "role": role, "block": block}


def _refs(prefix: str, count: int, *, start: int = 1) -> list[str]:
    return [f"{prefix}{index}" for index in range(start, start + count)]


def _components_for(refs: list[str], kind: str, value: str, role: str, block: str = "") -> list[dict[str, str]]:
    return [_c(ref, kind, value, role, block) for ref in refs]


def _series(prefix: str, pins: str, count: int) -> list[str]:
    return [f"{prefix}{index}.{pins}" for index in range(1, count + 1)]


def _range_endpoints(prefix: str, pin: str, start: int, end: int) -> list[str]:
    return [f"{prefix}{index}.{pin}" for index in range(start, end + 1)]


def _raw_spec(
    circuit_id: str,
    name: str,
    purpose: str,
    components: list[dict[str, str]],
    nets: dict[str, list[str]],
    blocks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "circuit_id": circuit_id,
        "name": name,
        "purpose": purpose,
        "components": components,
        "nets": nets,
        "blocks": blocks or [],
    }


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def make(self, value: str) -> None:
        if value not in self.parent:
            self.parent[value] = value

    def find(self, value: str) -> str:
        self.make(value)
        parent = self.parent[value]
        if parent != value:
            self.parent[value] = self.find(parent)
        return self.parent[value]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


def _normalize_endpoint(token: str, refs: set[str], repairs: list[dict[str, str]]) -> str:
    text = token.strip()
    if not text or text.upper() in NO_CONNECT:
        return ""
    parts = [part.strip() for part in text.split(".") if part.strip()]
    if len(parts) < 2:
        return text
    if parts[0] in refs and len(parts) > 2:
        repaired = f"{parts[0]}.{parts[-1]}"
        repairs.append({"kind": "hierarchical_endpoint_reduced", "from": text, "to": repaired})
        return repaired
    return f"{parts[0]}.{'.'.join(parts[1:])}"


def _endpoint_ref(endpoint: str) -> str:
    return endpoint.split(".", 1)[0]


def _endpoint_pin(endpoint: str) -> str:
    return endpoint.split(".", 1)[1] if "." in endpoint else ""


def _canonical_group_name(group: set[str], order: dict[str, int]) -> str:
    for name in POWER_NET_PRIORITY:
        if name in group:
            return name
    return min(group, key=lambda item: order.get(item, 10_000))


def _compile_nets(raw_nets: dict[str, list[str]], refs: set[str]) -> tuple[dict[str, list[str]], list[dict[str, str]]]:
    repairs: list[dict[str, str]] = []
    uf = _UnionFind()
    order: dict[str, int] = {}
    raw_members: dict[str, list[str]] = defaultdict(list)

    def remember(net: str) -> None:
        if net not in order:
            order[net] = len(order)
        uf.make(net)

    for net in raw_nets:
        remember(net)
    for net, endpoints in raw_nets.items():
        remember(net)
        for raw_endpoint in endpoints:
            text = str(raw_endpoint).strip()
            if not text:
                continue
            if "=" in text:
                left, right = (part.strip() for part in text.split("=", 1))
                target = right
                remember(target)
                endpoint = _normalize_endpoint(left, refs, repairs)
                if endpoint:
                    raw_members[target].append(endpoint)
                    repairs.append({"kind": "assignment_expanded", "from": text, "to": f"{endpoint} -> {target}"})
                continue
            if text in raw_nets or text in POWER_NETS:
                remember(text)
                uf.union(net, text)
                repairs.append({"kind": "net_alias_merged", "from": net, "to": text})
                continue
            endpoint = _normalize_endpoint(text, refs, repairs)
            if endpoint:
                raw_members[net].append(endpoint)

    endpoint_owner: dict[str, str] = {}
    for net, endpoints in raw_members.items():
        remember(net)
        for endpoint in endpoints:
            owner = endpoint_owner.get(endpoint)
            if owner is None:
                endpoint_owner[endpoint] = net
                continue
            uf.union(owner, net)
            repairs.append({"kind": "shared_endpoint_net_merge", "from": net, "to": owner, "endpoint": endpoint})

    group_names: dict[str, set[str]] = defaultdict(set)
    for net in order:
        group_names[uf.find(net)].add(net)

    group_canonical = {root: _canonical_group_name(names, order) for root, names in group_names.items()}
    final_members: dict[str, list[str]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for net, endpoints in raw_members.items():
        canonical = group_canonical[uf.find(net)]
        for endpoint in endpoints:
            key = (canonical, endpoint)
            if key in seen:
                continue
            seen.add(key)
            final_members[canonical].append(endpoint)

    return dict(sorted(final_members.items(), key=lambda item: order.get(item[0], 10_000))), repairs


def validate_final_circuit(circuit: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    components = circuit.get("components", [])
    nets = circuit.get("nets", {})
    routing = circuit.get("routing", {})
    if not isinstance(components, list) or not components:
        errors.append("components must be a non-empty array.")
        components = []
    if not isinstance(nets, dict) or not nets:
        errors.append("nets must be a non-empty object.")
        nets = {}
    if not isinstance(routing, dict):
        errors.append("routing must be an object.")
    else:
        mode = str(routing.get("mode") or "").strip()
        if mode not in {"wire", "terminal", "combination"}:
            errors.append("routing.mode must be one of: wire, terminal, combination.")

    refs: set[str] = set()
    endpoint_to_net: dict[str, str] = {}
    for index, component in enumerate(components, 1):
        if not isinstance(component, dict):
            errors.append(f"component {index} must be an object.")
            continue
        ref = str(component.get("ref") or component.get("id") or "").strip()
        kind = str(component.get("kind") or "").strip()
        value = str(component.get("value") or "").strip()
        if not ref:
            errors.append(f"component {index} has no ref/id.")
            continue
        if ref in refs:
            errors.append(f"duplicate component ref {ref}.")
        refs.add(ref)
        if not kind:
            errors.append(f"{ref} has no kind.")
        elif resolve_placement_spec(kind) is None:
            errors.append(f"{ref} uses unsupported placement kind {kind}.")
        if not value:
            warnings.append(f"{ref}/{kind} has no value.")

    component_pin_counts: dict[str, int] = defaultdict(int)
    for net, endpoints in nets.items():
        if not isinstance(endpoints, list):
            errors.append(f"net {net} endpoints must be an array.")
            continue
        if len(endpoints) < 2:
            errors.append(f"net {net} has fewer than two endpoints.")
        seen_in_net: set[str] = set()
        for endpoint in endpoints:
            endpoint_text = str(endpoint).strip()
            if endpoint_text in seen_in_net:
                errors.append(f"net {net} repeats endpoint {endpoint_text}.")
            seen_in_net.add(endpoint_text)
            if "." not in endpoint_text:
                errors.append(f"net {net} endpoint {endpoint_text!r} is not REF.PIN format.")
                continue
            ref = _endpoint_ref(endpoint_text)
            pin = _endpoint_pin(endpoint_text)
            if ref not in refs:
                errors.append(f"net {net} references unknown component {ref}.")
            if not pin:
                errors.append(f"net {net} endpoint {endpoint_text!r} has no pin.")
            previous = endpoint_to_net.get(endpoint_text)
            if previous and previous != net:
                errors.append(f"endpoint {endpoint_text} appears on both {previous} and {net}.")
            endpoint_to_net[endpoint_text] = str(net)
            component_pin_counts[ref] += 1

    for component in components:
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or component.get("id") or "").strip()
        if ref and component_pin_counts.get(ref, 0) == 0:
            warnings.append(f"{ref} is placed but has no compiled net endpoints.")

    return {
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": warnings,
        "component_count": len(components),
        "net_count": len(nets),
        "endpoint_count": len(endpoint_to_net),
        "validator": "universal_circuit_validator_v0.1",
        "checked_rules": [
            "json object shape",
            "component ref/kind/value presence",
            "unique component refs",
            "supported placement kinds",
            "routing mode contract",
            "REF.PIN endpoint syntax",
            "known endpoint component refs",
            "net has at least two endpoints",
            "no endpoint on multiple final nets",
        ],
    }


def compile_raw_circuit(raw: dict[str, Any]) -> dict[str, Any]:
    components = deepcopy(raw["components"])
    refs = {str(component["ref"]) for component in components}
    compiled_nets, repairs = _compile_nets(raw["nets"], refs)
    pin_maps: dict[str, dict[str, str]] = {ref: {} for ref in refs}
    for net, endpoints in compiled_nets.items():
        for endpoint in endpoints:
            ref = _endpoint_ref(endpoint)
            pin = _endpoint_pin(endpoint)
            if ref in pin_maps and pin:
                pin_maps[ref][pin] = net

    final_components: list[dict[str, Any]] = []
    for item in components:
        ref = str(item["ref"])
        final_components.append(
            {
                "id": ref,
                "ref": ref,
                "kind": item["kind"],
                "type": item["kind"],
                "value": item["value"],
                "role": item.get("role", ""),
                "block": item.get("block", ""),
                "pins": dict(sorted(pin_maps.get(ref, {}).items())),
            }
        )

    circuit = {
        "schema_version": SCHEMA_VERSION,
        "compatible_schema": "progen-kicad-placer-ir/v0.2",
        "progeneda_circuit_version": "v1",
        "compiler": {
            "name": "final_circuit_builder",
            "version": COMPILER_VERSION,
            "trusted_final_json_rule": "AI may produce intent/block suggestions only; deterministic code compiles and validates final JSON.",
        },
        "project": {
            "name": raw["circuit_id"].lower(),
            "title": raw["name"],
            "purpose": raw["purpose"],
            "target": "kicad_schematic",
            "schematic_only": True,
        },
        "circuit_id": raw["circuit_id"],
        "circuit_name": raw["name"],
        "purpose": raw["purpose"],
        "routing": {
            "mode": str(raw.get("routing_mode") or "wire"),
            "allowed_modes": ["wire", "terminal", "combination"],
            "wire_mode_contract": "Every compiled net endpoint must be connected by physical wire/junction/pin graph; local labels are terminal-stage behavior.",
        },
        "components": final_components,
        "nets": compiled_nets,
        "blocks": raw.get("blocks", []),
        "generation_notes": {
            "source": "user-supplied connected T01-T10 test specification",
            "compiler_repairs": repairs,
            "repair_policy": "expand endpoint assignments, merge explicit net aliases, and merge nets sharing the same endpoint before validation.",
        },
    }
    circuit["validation"] = validate_final_circuit(circuit)
    return circuit


def available_final_circuit_suites() -> tuple[str, ...]:
    return (DEFAULT_FINAL_CIRCUIT_SUITE, PROTEUS_ALIAS_MIXED_SUITE, PROTEUS_ALIAS_ROUTED_SUITE)


def _raw_specs_for_suite(suite: str) -> list[dict[str, Any]]:
    if suite == DEFAULT_FINAL_CIRCUIT_SUITE:
        return _build_raw_test_specs()
    if suite == PROTEUS_ALIAS_MIXED_SUITE:
        return _build_raw_proteus_alias_mixed_specs()
    if suite == PROTEUS_ALIAS_ROUTED_SUITE:
        return _build_raw_proteus_alias_routed_specs()
    known = ", ".join(available_final_circuit_suites())
    raise ValueError(f"Unknown final circuit suite {suite!r}; expected one of: {known}")


def build_final_circuits(suite: str = DEFAULT_FINAL_CIRCUIT_SUITE) -> list[dict[str, Any]]:
    return [compile_raw_circuit(raw) for raw in _raw_specs_for_suite(suite)]


def build_final_test_circuits() -> list[dict[str, Any]]:
    return build_final_circuits(DEFAULT_FINAL_CIRCUIT_SUITE)


def build_proteus_alias_mixed_circuits() -> list[dict[str, Any]]:
    return build_final_circuits(PROTEUS_ALIAS_MIXED_SUITE)


def build_proteus_alias_routed_circuits() -> list[dict[str, Any]]:
    return build_final_circuits(PROTEUS_ALIAS_ROUTED_SUITE)


def placer_ready_circuit(circuit: dict[str, Any]) -> dict[str, Any]:
    """Return the same final circuit in component-only form for the placer stage."""
    out = deepcopy(circuit)
    out["schema_version"] = "progen-kicad-placer-ir/v0.2"
    out["pipeline_stage"] = "component_placer_input_from_final_json"
    for component in out.get("components", []):
        if isinstance(component, dict):
            component.pop("pins", None)
            component.pop("type", None)
            component.pop("role", None)
            component.pop("block", None)
    return out


def _t01() -> dict[str, Any]:
    components = [
        _c("U1", "ARDUINO_NANO", "Arduino Nano", "controller"),
        *_components_for(_refs("D", 3), "LED_INDICATOR", "LED", "indicator"),
        *_components_for(_refs("R", 3), "R_220", "220 ohm", "series_resistor"),
        *_components_for(_refs("SW", 2), "PUSH_BUTTON", "Push Button", "switch"),
        *_components_for(_refs("R", 2, start=4), "R_10K_PULLUP", "10k pulldown", "pulldown"),
        _c("J1", "PIN_HEADER", "Power/IO Header 1x6", "connector"),
        _c("J2", "PIN_HEADER", "Extra IO Header 1x6", "connector"),
    ]
    nets = {
        "+5V": ["U1.5V", "J1.1", "SW1.1", "SW2.1"],
        "GND": ["U1.GND", "J1.2", "J2.6", "D1.K", "D2.K", "D3.K", "R4.2", "R5.2"],
        "LED1_NET": ["U1.D2", "R1.1"],
        "LED1_A": ["R1.2", "D1.A"],
        "LED2_NET": ["U1.D3", "R2.1"],
        "LED2_A": ["R2.2", "D2.A"],
        "LED3_NET": ["U1.D4", "R3.1"],
        "LED3_A": ["R3.2", "D3.A"],
        "BTN1_NET": ["U1.D5", "SW1.2", "R4.1", "J1.3"],
        "BTN2_NET": ["U1.D6", "SW2.2", "R5.1", "J1.4"],
        "IO_D7": ["U1.D7", "J1.5"],
        "IO_D8": ["U1.D8", "J1.6"],
        "IO_D9": ["U1.D9", "J2.1"],
        "IO_D10": ["U1.D10", "J2.2"],
        "IO_D11": ["U1.D11", "J2.3"],
        "IO_D12": ["U1.D12", "J2.4"],
        "IO_D13": ["U1.D13", "J2.5"],
    }
    return _raw_spec("T01", "Arduino LED/Button Demo", "small clean connected placement test", components, nets)


def _t02() -> dict[str, Any]:
    components = [
        _c("J1", "DC_BARREL_JACK", "DC Barrel Jack", "input_connector"),
        _c("F1", "FUSE", "Fuse", "protection"),
        _c("D1", "D_1N4007", "1N4007", "reverse_protection"),
        _c("U1", "LM7805", "LM7805", "regulator"),
        _c("C1", "CP_100UF", "100uF", "input_capacitor"),
        _c("C2", "C_100NF_CERAMIC", "100nF", "input_capacitor"),
        _c("C3", "CP_100UF", "100uF", "output_capacitor"),
        _c("C4", "C_100NF_CERAMIC", "100nF", "output_capacitor"),
        _c("C5", "C_100NF_CERAMIC", "100nF", "bypass_capacitor"),
        _c("D2", "POWER_LED", "Power LED", "indicator"),
        _c("R1", "RESISTOR", "1k", "series_resistor"),
        _c("J2", "SCREW_TERMINAL_2", "5V Output", "output_connector"),
    ]
    nets = {
        "VIN_RAW": ["J1.POS", "F1.1"],
        "GND": ["J1.NEG", "U1.GND", "C1.NEG", "C2.2", "C3.NEG", "C4.2", "C5.2", "D2.K", "J2.2"],
        "VIN_FUSED": ["F1.2", "D1.A"],
        "VIN_PROTECTED": ["D1.K", "U1.IN", "C1.POS", "C2.1", "C5.1"],
        "+5V": ["U1.OUT", "C3.POS", "C4.1", "R1.1", "J2.1"],
        "PWR_LED_A": ["R1.2", "D2.A"],
    }
    return _raw_spec("T02", "5V LM7805 Power Supply", "power-left-to-right connected placement", components, nets)


def _t03() -> dict[str, Any]:
    components = [
        _c("U1", "ESP32_WROOM", "ESP32-WROOM", "wireless_controller"),
        _c("U2", "CP2102", "CP2102", "usb_uart"),
        _c("J1", "USB_C_CONNECTOR", "USB Type-C", "usb_connector"),
        _c("SW1", "EN_PUSH_BUTTON", "EN", "switch"),
        _c("SW2", "BOOT_PUSH_BUTTON", "BOOT", "switch"),
        *_components_for(_refs("R", 2), "R_10K_PULLUP", "10k pullup", "pullup"),
        *_components_for(_refs("R", 2, start=3), "RESISTOR", "10k LED resistor", "series_resistor"),
        *_components_for(_refs("R", 2, start=5), "RESISTOR", "5.1k CC pulldown", "pulldown"),
        *_components_for(_refs("C", 5), "C_100NF_CERAMIC", "100nF", "decoupling"),
        *_components_for(_refs("D", 2), "LED_INDICATOR", "LED", "indicator"),
        *_components_for(_refs("J", 4, start=2), "PIN_HEADER", "Pin Header", "connector"),
    ]
    nets = {
        "USB_VBUS": ["J1.VBUS", "U2.VBUS"],
        "USB_GND": [
            "J1.GND",
            "U2.GND",
            "U1.GND",
            "C1.2",
            "C2.2",
            "C3.2",
            "C4.2",
            "C5.2",
            "SW1.2",
            "SW2.2",
            "D1.K",
            "D2.K",
            "R5.2",
            "R6.2",
            "J2.2",
            "J3.2",
            "J4.2",
            "J5.2",
        ],
        "USB_D_PLUS": ["J1.D+", "U2.D+"],
        "USB_D_MINUS": ["J1.D-", "U2.D-"],
        "USB_CC1": ["J1.CC1", "R5.1"],
        "USB_CC2": ["J1.CC2", "R6.1"],
        "+3V3": [
            "U1.3V3",
            "U2.VDD",
            "R1.1",
            "R2.1",
            "R3.1",
            "R4.1",
            "C1.1",
            "C2.1",
            "C3.1",
            "C4.1",
            "C5.1",
            "J2.1",
            "J3.1",
            "J4.1",
            "J5.1",
        ],
        "ESP_EN": ["U1.EN", "R1.2", "SW1.1"],
        "ESP_BOOT_IO0": ["U1.IO0", "R2.2", "SW2.1"],
        "UART_TX_TO_ESP_RX": ["U2.TXD", "U1.U0RXD"],
        "UART_RX_FROM_ESP_TX": ["U2.RXD", "U1.U0TXD"],
        "ESP_LED1": ["U1.IO2", "R3.2"],
        "ESP_LED1_A": ["R3.2", "D1.A"],
        "ESP_LED2": ["U1.IO4", "R4.2"],
        "ESP_LED2_A": ["R4.2", "D2.A"],
        "ESP_IO5": ["U1.IO5", "J2.3"],
        "ESP_IO18": ["U1.IO18", "J2.4"],
        "ESP_IO19": ["U1.IO19", "J2.5"],
        "ESP_IO21": ["U1.IO21", "J3.3"],
        "ESP_IO22": ["U1.IO22", "J3.4"],
        "ESP_IO23": ["U1.IO23", "J3.5"],
        "ESP_RX_HEADER": ["U1.U0RXD", "J4.3"],
        "ESP_TX_HEADER": ["U1.U0TXD", "J4.4"],
    }
    return _raw_spec("T03", "ESP32 CP2102 USB-UART Support Board", "module plus support parts with many nets", components, nets)


def _t04() -> dict[str, Any]:
    components = [
        *_components_for(_refs("Q", 2), "IRLZ44N", "IRLZ44N", "mosfet"),
        *_components_for(_refs("Q", 2, start=3), "BC547", "BC547", "bjt"),
        *_components_for(_refs("K", 2), "RELAY_5V", "5V relay", "relay"),
        *_components_for(_refs("D", 2), "FLYBACK_DIODE", "Flyback diode", "diode"),
        *_components_for(_refs("D", 2, start=3), "RELAY_FLYBACK_DIODE", "Relay flyback diode", "diode"),
        _c("M1", "DC_MOTOR", "DC Motor", "load"),
        *_components_for(_refs("J", 4), "SCREW_TERMINAL_2", "Screw terminal 2-pin", "connector"),
        *_components_for(_refs("J", 2, start=5), "PWM_HEADER", "PWM/control header", "connector"),
        *_components_for(_refs("D", 4, start=5), "LED_INDICATOR", "Indicator LED", "indicator"),
        *_components_for(_refs("R", 6), "RESISTOR", "Driver resistor", "resistor"),
    ]
    nets = {
        "+5V": [
            "J1.1",
            "J2.1",
            "K1.COIL_PLUS",
            "K2.COIL_PLUS",
            "D1.K",
            "D2.K",
            "D3.K",
            "D4.K",
            "D5.A",
            "D6.A",
            "D7.A",
            "D8.A",
            "J5.1",
            "J6.1",
        ],
        "GND": ["Q1.S", "Q2.S", "Q3.E", "Q4.E", "R2.2", "R4.2", "J5.2", "J6.2"],
        "PWM_MOTOR_1": ["J5.3", "R1.1"],
        "MOSFET1_GATE": ["R1.2", "Q1.G", "R2.1"],
        "MOTOR_LOW": ["Q1.D", "M1.2", "D1.A"],
        "MOTOR_HIGH": ["M1.1", "+5V"],
        "PWM_LOAD_2": ["J6.3", "R3.1"],
        "MOSFET2_GATE": ["R3.2", "Q2.G", "R4.1"],
        "LOAD2_LOW": ["Q2.D", "J2.2", "D2.A"],
        "RELAY1_CTRL": ["J5.4", "R5.1"],
        "RELAY1_BASE": ["R5.2", "Q3.B"],
        "RELAY1_COIL_LOW": ["Q3.C", "K1.COIL_MINUS", "D3.A"],
        "RELAY2_CTRL": ["J6.4", "R6.1"],
        "RELAY2_BASE": ["R6.2", "Q4.B"],
        "RELAY2_COIL_LOW": ["Q4.C", "K2.COIL_MINUS", "D4.A"],
        "RELAY1_COM": ["K1.COM", "J3.1"],
        "RELAY1_NO": ["K1.NO", "J3.2"],
        "RELAY2_COM": ["K2.COM", "J4.1"],
        "RELAY2_NO": ["K2.NO", "J4.2"],
        "LED_MOTOR1": ["D5.K", "MOTOR_LOW"],
        "LED_MOTOR2": ["D6.K", "LOAD2_LOW"],
        "LED_RELAY1": ["D7.K", "RELAY1_COIL_LOW"],
        "LED_RELAY2": ["D8.K", "RELAY2_COIL_LOW"],
    }
    return _raw_spec("T04", "Dual MOSFET And Relay Driver Board", "repeated driver blocks and connector-heavy layout", components, nets)


def _t05() -> dict[str, Any]:
    components = [
        _c("U1", "BME280", "BME280", "sensor"),
        _c("U2", "SSD1306_OLED", "SSD1306 OLED", "display"),
        _c("U3", "DS3231", "DS3231 RTC", "rtc"),
        _c("U4", "W25Q64", "W25Q64", "memory"),
        *_components_for(_refs("R", 2), "R_4K7_PULLUP", "4.7k pullup", "pullup"),
        *_components_for(_refs("R", 2, start=3), "RESISTOR", "SPI pullup", "pullup"),
        *_components_for(_refs("C", 6), "C_100NF_CERAMIC", "100nF", "decoupling"),
        *_components_for(_refs("J", 2), "JST_CONNECTOR", "JST connector", "connector"),
        *_components_for(_refs("J", 2, start=3), "I2C_HEADER", "I2C header", "connector"),
        _c("J5", "SPI_HEADER_FLASH", "SPI header", "connector"),
        _c("BT1", "COIN_CELL_HOLDER", "CR2032 holder", "battery"),
        *_components_for(_refs("TP", 6), "TEST_POINT", "Test point", "testpoint"),
    ]
    nets = {
        "+3V3": [
            "U1.VCC",
            "U2.VCC",
            "U3.VCC",
            "U4.VCC",
            "R1.1",
            "R2.1",
            "R3.1",
            "R4.1",
            "C1.1",
            "C2.1",
            "C3.1",
            "C4.1",
            "C5.1",
            "C6.1",
            "J1.1",
            "J2.1",
            "J3.1",
            "J4.1",
            "J5.1",
            "TP1.1",
        ],
        "GND": [
            "U1.GND",
            "U2.GND",
            "U3.GND",
            "U4.GND",
            "C1.2",
            "C2.2",
            "C3.2",
            "C4.2",
            "C5.2",
            "C6.2",
            "J1.2",
            "J2.2",
            "J3.4",
            "J4.4",
            "J5.6",
            "BT1.NEG",
            "TP2.1",
        ],
        "I2C_SDA": ["U1.SDA", "U2.SDA", "U3.SDA", "R1.2", "J1.3", "J2.3", "J3.2", "J4.2", "TP3.1"],
        "I2C_SCL": ["U1.SCL", "U2.SCL", "U3.SCL", "R2.2", "J1.4", "J2.4", "J3.3", "J4.3", "TP4.1"],
        "RTC_VBAT": ["U3.VBAT", "BT1.POS"],
        "SPI_MOSI": ["U4.DI", "J5.4"],
        "SPI_MISO": ["U4.DO", "J5.5"],
        "SPI_SCK": ["U4.CLK", "J5.3"],
        "SPI_CS_FLASH": ["U4.CS", "R3.2", "J5.2", "TP5.1"],
        "FLASH_WP_HOLD": ["U4.WP", "U4.HOLD", "R4.2"],
        "BME280_CSB": ["U1.CSB", "+3V3"],
        "BME280_SDO": ["U1.SDO", "GND"],
        "SPI_TEST": ["TP6.1", "SPI_SCK"],
    }
    return _raw_spec("T05", "I2C SPI Sensor Hub", "bus-style layout with labels and repeated pullups/caps", components, nets)


def _t06() -> dict[str, Any]:
    components = [
        _c("U1", "MCP2515", "MCP2515", "can_controller"),
        _c("U2", "TJA1050", "TJA1050", "can_transceiver"),
        _c("U3", "MAX485", "MAX485", "rs485_transceiver"),
        _c("Y1", "CRYSTAL_16MHZ", "16MHz crystal", "clock"),
        _c("C1", "C_22PF_X1", "22pF", "crystal_capacitor"),
        _c("C2", "C_22PF_X2", "22pF", "crystal_capacitor"),
        *_components_for(_refs("C", 5, start=3), "C_100NF_CERAMIC", "100nF", "decoupling"),
        _c("R1", "R_120_CAN", "120 ohm CAN termination", "termination"),
        _c("R2", "R_120_RS485", "120 ohm RS485 termination", "termination"),
        *_components_for(_refs("D", 2), "TVS_DIODE_RS485", "TVS diode", "protection"),
        _c("J1", "CAN_TERMINAL", "CAN terminal", "connector"),
        _c("J2", "RS485_TERMINAL", "RS485 terminal", "connector"),
        _c("J3", "SPI_HEADER_FLASH", "SPI header", "connector"),
        _c("J4", "UART_HEADER", "UART/control header", "connector"),
        _c("J5", "PIN_HEADER", "Power header", "connector"),
        *_components_for(_refs("JP", 3), "CHIP_SELECT_JUMPER", "Jumper", "jumper"),
    ]
    nets = {
        "+5V": ["U2.VCC", "U3.VCC", "C4.1", "C5.1", "C6.1", "C7.1", "J5.1"],
        "+3V3": ["U1.VDD", "C3.1", "J3.1"],
        "GND": ["U1.VSS", "U2.GND", "U3.GND", "C1.2", "C2.2", "C3.2", "C4.2", "C5.2", "C6.2", "C7.2", "D1.2", "D2.2", "J3.6", "J4.5", "J5.2"],
        "CAN_SPI_MOSI": ["U1.SI", "J3.4"],
        "CAN_SPI_MISO": ["U1.SO", "J3.5"],
        "CAN_SPI_SCK": ["U1.SCK", "J3.3"],
        "CAN_SPI_CS": ["U1.CS", "J3.2"],
        "CAN_INT": ["U1.INT", "J3.7"],
        "MCP_OSC1": ["U1.OSC1", "Y1.1", "C1.1"],
        "MCP_OSC2": ["U1.OSC2", "Y1.2", "C2.1"],
        "CAN_TXD": ["U1.TXCAN", "U2.TXD"],
        "CAN_RXD": ["U1.RXCAN", "U2.RXD"],
        "CANH": ["U2.CANH", "J1.1", "R1.1", "D1.1", "JP1.1"],
        "CANL": ["U2.CANL", "J1.2", "R1.2", "D2.1", "JP1.2"],
        "RS485_RO": ["U3.RO", "J4.1"],
        "RS485_DI": ["U3.DI", "J4.2"],
        "RS485_DE_RE": ["U3.DE", "U3.RE", "J4.3", "JP3.1"],
        "RS485_A": ["U3.A", "J2.1", "R2.1", "JP2.1"],
        "RS485_B": ["U3.B", "J2.2", "R2.2", "JP2.2"],
    }
    return _raw_spec("T06", "CAN And RS485 Communication Board", "IC clusters with termination and protection", components, nets)


def _t07() -> dict[str, Any]:
    components = [
        _c("U1A", "LM358", "LM358 channel A", "opamp"),
        _c("U1B", "LM358", "LM358 channel B", "opamp"),
        _c("U3", "PAM8403", "PAM8403", "amplifier"),
        _c("J1", "AUDIO_INPUT_JACK", "Stereo input jack", "connector"),
        _c("J2", "AUDIO_JACK", "Aux/test audio jack", "connector"),
        _c("SPK1", "SPEAKER", "Left speaker", "load"),
        _c("SPK2", "SPEAKER", "Right speaker", "load"),
        *_components_for(_refs("RV", 3), "POTENTIOMETER", "Potentiometer", "control"),
        *_components_for(_refs("C", 4), "INPUT_CAPACITOR", "Input capacitor", "capacitor"),
        *_components_for(_refs("C", 4, start=5), "OUTPUT_FILTER_CAPACITOR", "Output/filter capacitor", "capacitor"),
        *_components_for(_refs("R", 8), "RESISTOR", "Audio resistor", "resistor"),
        *_components_for(_refs("D", 2), "LED_INDICATOR", "Status LED", "indicator"),
    ]
    nets = {
        "+5V": ["U1A.VCC", "U1B.VCC", "U3.VCC", "RV3.1", "C5.1", "C6.1", "D1.A", "D2.A"],
        "GND": ["U1A.GND", "U1B.GND", "U3.GND", "J1.GND", "J2.GND", "RV1.1", "RV2.1", "RV3.3", "C5.2", "C6.2", "C7.2", "C8.2", "D1.K", "D2.K"],
        "AUDIO_L_IN_RAW": ["J1.LEFT", "C1.1"],
        "AUDIO_R_IN_RAW": ["J1.RIGHT", "C2.1"],
        "AUDIO_L_AC": ["C1.2", "RV1.3"],
        "AUDIO_R_AC": ["C2.2", "RV2.3"],
        "AUDIO_L_VOL": ["RV1.2", "R1.1"],
        "AUDIO_R_VOL": ["RV2.2", "R3.1"],
        "LM358_L_IN": ["R1.2", "U1A.IN_PLUS"],
        "LM358_R_IN": ["R3.2", "U1B.IN_PLUS"],
        "LM358_L_FEEDBACK": ["U1A.OUT", "U1A.IN_MINUS", "R2.1"],
        "LM358_R_FEEDBACK": ["U1B.OUT", "U1B.IN_MINUS", "R4.1"],
        "AMP_L_IN_COUPLED": ["U1A.OUT", "C3.1"],
        "AMP_R_IN_COUPLED": ["U1B.OUT", "C4.1"],
        "PAM_L_IN": ["C3.2", "U3.LIN"],
        "PAM_R_IN": ["C4.2", "U3.RIN"],
        "MASTER_CTRL": ["RV3.2", "J2.LEFT", "J2.RIGHT"],
        "SPK_L_PLUS": ["U3.LOUT_PLUS", "SPK1.1"],
        "SPK_L_MINUS": ["U3.LOUT_MINUS", "SPK1.2"],
        "SPK_R_PLUS": ["U3.ROUT_PLUS", "SPK2.1"],
        "SPK_R_MINUS": ["U3.ROUT_MINUS", "SPK2.2"],
        "AMP_BYPASS_L": ["C7.1", "U3.LIN"],
        "AMP_BYPASS_R": ["C8.1", "U3.RIN"],
        "AUDIO_L_BIAS_TOP": ["R5.1", "+5V"],
        "AUDIO_L_BIAS": ["R5.2", "R6.1", "U1A.BIAS"],
        "AUDIO_L_BIAS_GND": ["R6.2", "GND"],
        "AUDIO_R_BIAS_TOP": ["R7.1", "+5V"],
        "AUDIO_R_BIAS": ["R7.2", "R8.1", "U1B.BIAS"],
        "AUDIO_R_BIAS_GND": ["R8.2", "GND"],
    }
    return _raw_spec("T07", "Stereo Audio Control PAM8403 Amplifier", "analog-style placement with passives around ICs", components, nets)


def _t08() -> dict[str, Any]:
    components = [
        *_components_for(_refs("U", 3), "74HC595_SHIFT_REGISTER", "74HC595", "logic"),
        *_components_for(_refs("SW", 2), "DIP_SWITCH", "DIP switch", "switch"),
        *_components_for(["DARR1", "DARR2"], "LED_ARRAY", "LED array", "indicator"),
        *_components_for(_refs("RN", 3), "RESISTOR_NETWORK", "Resistor network", "resistor_network"),
        _c("J1", "PROGRAMMING_HEADER", "Programming/control header", "connector"),
        _c("J2", "SPI_HEADER_FLASH", "SPI header", "connector"),
        *_components_for(_refs("C", 4), "C_100NF_CERAMIC", "100nF", "decoupling"),
        *_components_for(_refs("D", 8), "LED_INDICATOR", "LED", "indicator"),
        *_components_for(_refs("R", 8), "RESISTOR", "Pullup resistor", "pullup"),
    ]
    nets = {
        "+5V": [
            "U1.VCC",
            "U2.VCC",
            "U3.VCC",
            "U1.MR",
            "U2.MR",
            "U3.MR",
            "RN1.COM",
            "RN2.COM",
            "RN3.COM",
            *_range_endpoints("R", "1", 1, 8),
            "C1.1",
            "C2.1",
            "C3.1",
            "C4.1",
            "J1.1",
            "J2.1",
        ],
        "GND": [
            "U1.GND",
            "U2.GND",
            "U3.GND",
            "U1.OE",
            "U2.OE",
            "U3.OE",
            "C1.2",
            "C2.2",
            "C3.2",
            "C4.2",
            "J1.2",
            "J2.6",
            "SW1.COM",
            "SW2.COM",
            "DARR1.COM_K",
            "DARR2.COM_K",
            *_range_endpoints("D", "K", 1, 8),
        ],
        "SPI_MOSI": ["J2.4", "J1.3", "U1.SER"],
        "SPI_SCK": ["J2.3", "J1.4", "U1.SHCP", "U2.SHCP", "U3.SHCP"],
        "LATCH": ["J1.5", "U1.STCP", "U2.STCP", "U3.STCP"],
        "SHIFT_CHAIN_1": ["U1.Q7S", "U2.SER"],
        "SHIFT_CHAIN_2": ["U2.Q7S", "U3.SER"],
    }
    for index in range(8):
        nets[f"LED_A{index}"] = [f"U1.Q{index}", f"RN1.{index + 1}", f"DARR1.A{index}"]
    for index in range(4):
        nets[f"LED_B{index}"] = [f"U2.Q{index}", f"RN2.{index + 1}", f"DARR2.A{index}"]
    for index in range(1, 5):
        nets[f"DIP1_{index}"] = [f"SW1.{index}", f"R{index}.2", f"J1.{index + 5}"]
        nets[f"DIP2_{index}"] = [f"SW2.{index}", f"R{index + 4}.2", f"J1.{index + 9}"]
    return _raw_spec("T08", "74HC595 Logic LED Display Board", "repeated IC rows and symmetry", components, nets)


def _t09() -> dict[str, Any]:
    components = [
        _c("U1", "ARDUINO_NANO", "Arduino Nano", "controller"),
        _c("U2", "ESP32_WROOM", "ESP32-WROOM", "wireless_coprocessor"),
        _c("U3", "BME280", "BME280", "sensor"),
        _c("U4", "SSD1306_OLED", "SSD1306 OLED", "display"),
        _c("U5", "DS3231", "DS3231 RTC", "rtc"),
        _c("U6", "W25Q64", "W25Q64", "memory"),
        *_components_for(_refs("Q", 2), "IRLZ44N", "IRLZ44N", "mosfet"),
        _c("Q3", "BC547", "BC547", "bjt"),
        _c("K1", "RELAY_5V", "5V relay", "relay"),
        *_components_for(_refs("D", 3), "FLYBACK_DIODE", "Flyback diode", "diode"),
        *_components_for(_refs("D", 2, start=4), "LED_INDICATOR", "Status LED", "indicator"),
        *_components_for(_refs("R", 15), "RESISTOR", "Resistor", "resistor"),
        *_components_for(_refs("C", 8), "C_100NF_CERAMIC", "100nF", "decoupling"),
        *_components_for(_refs("SW", 4), "PUSH_BUTTON", "Push Button", "switch"),
        _c("J_POWER", "PIN_HEADER", "Power header", "connector"),
        _c("J_3V3", "PIN_HEADER", "3V3 header", "connector"),
        _c("J_I2C", "I2C_HEADER", "I2C header", "connector"),
        _c("J_SPI", "SPI_HEADER_FLASH", "SPI header", "connector"),
        _c("J_LOAD1", "SCREW_TERMINAL_2", "Load 1", "connector"),
        _c("J_LOAD2", "SCREW_TERMINAL_2", "Load 2", "connector"),
        _c("J_RELAY", "SCREW_TERMINAL_2", "Relay contact", "connector"),
        *_components_for(_refs("TP", 8), "TEST_POINT", "Test point", "testpoint"),
    ]
    nets = {
        "+5V": ["U1.5V", "K1.COIL_PLUS", "J_POWER.1", "SW3.2", "SW4.2", "J_LOAD1.1", "J_LOAD2.1", "D1.K", "D2.K", "D3.K", "C1.1", "C2.1", "C3.1", "TP6.1"],
        "+3V3": ["U2.3V3", "U3.VCC", "U4.VCC", "U5.VCC", "U6.VCC", "J_3V3.1", "R1.1", "R2.1", "R3.1", "R4.1", "R5.1", "R6.1", "C4.1", "C5.1", "C6.1", "C7.1", "C8.1", "TP7.1"],
        "GND": ["U1.GND", "U2.GND", "U3.GND", "U4.GND", "U5.GND", "U6.GND", "J_POWER.2", "J_3V3.2", "J_I2C.4", "J_SPI.6", "Q1.S", "Q2.S", "Q3.E", "SW1.2", "SW2.2", "R7.2", "R8.2", "R10.2", "R12.2", "D4.K", "D5.K", "C1.2", "C2.2", "C3.2", "C4.2", "C5.2", "C6.2", "C7.2", "C8.2", "TP8.1"],
        "I2C_SDA": ["U1.A4", "U3.SDA", "U4.SDA", "U5.SDA", "R1.2", "J_I2C.2", "TP1.1"],
        "I2C_SCL": ["U1.A5", "U3.SCL", "U4.SCL", "U5.SCL", "R2.2", "J_I2C.3", "TP2.1"],
        "SPI_MOSI": ["U1.D11", "U6.DI", "J_SPI.4", "TP3.1"],
        "SPI_MISO": ["U1.D12", "U6.DO", "J_SPI.5", "TP4.1"],
        "SPI_SCK": ["U1.D13", "U6.CLK", "J_SPI.3", "TP5.1"],
        "SPI_CS_FLASH": ["U1.D10", "U6.CS", "R3.2", "J_SPI.2"],
        "FLASH_WP_HOLD": ["U6.WP", "U6.HOLD", "R4.2"],
        "ARDUINO_TO_ESP_RX": ["U1.D2", "U2.U0RXD"],
        "ARDUINO_TO_ESP_TX": ["U1.D3", "U2.U0TXD"],
        "ESP_EN": ["U2.EN", "R5.2", "SW1.1"],
        "ESP_BOOT": ["U2.IO0", "R6.2", "SW2.1"],
        "BUTTON_1": ["U1.D4", "SW3.1", "R7.1"],
        "BUTTON_2": ["U1.D5", "SW4.1", "R8.1"],
        "MOSFET1_GATE": ["U1.D6", "R9.1"],
        "MOSFET1_GATE_NODE": ["R9.2", "Q1.G", "R10.1"],
        "MOSFET1_LOAD_LOW": ["Q1.D", "J_LOAD1.2", "D1.A"],
        "MOSFET2_GATE": ["U1.D7", "R11.1"],
        "MOSFET2_GATE_NODE": ["R11.2", "Q2.G", "R12.1"],
        "MOSFET2_LOAD_LOW": ["Q2.D", "J_LOAD2.2", "D2.A"],
        "RELAY_CTRL": ["U1.D8", "R13.1"],
        "RELAY_BASE": ["R13.2", "Q3.B"],
        "RELAY_COIL_LOW": ["Q3.C", "K1.COIL_MINUS", "D3.A"],
        "RELAY_CONTACT_COM": ["K1.COM", "J_RELAY.1"],
        "RELAY_CONTACT_NO": ["K1.NO", "J_RELAY.2"],
        "LED_STATUS_1": ["U1.D9", "R14.1"],
        "LED_STATUS_1_A": ["R14.2", "D4.A"],
        "LED_STATUS_2": ["U2.IO2", "R15.1"],
        "LED_STATUS_2_A": ["R15.2", "D5.A"],
    }
    return _raw_spec("T09", "Full Maker Controller Board", "large integrated maker controller placement test", components, nets)


def _t10() -> dict[str, Any]:
    components = [
        _c("MCU", "ARDUINO_NANO", "Arduino Nano", "controller", "controller"),
        _c("ESP32", "ESP32_WROOM", "ESP32-WROOM", "wireless_coprocessor", "controller"),
        _c("USB_UART1", "CP2102", "CP2102", "usb_uart", "usb"),
        _c("USB_UART2", "CH340", "CH340", "usb_uart", "usb"),
        _c("USB1", "USB_C_CONNECTOR", "USB-C", "usb_connector", "usb"),
        _c("USB2", "USB_CONNECTOR", "USB", "usb_connector", "usb"),
        _c("BME280", "BME280", "BME280", "sensor", "i2c"),
        _c("SSD1306", "SSD1306_OLED", "SSD1306 OLED", "display", "i2c"),
        _c("DS3231", "DS3231", "DS3231 RTC", "rtc", "i2c"),
        _c("W25Q64_1", "W25Q64", "W25Q64", "memory", "spi"),
        _c("W25Q64_2", "W25Q64", "W25Q64", "memory", "spi"),
        *_components_for([f"U595_{index}" for index in range(1, 5)], "74HC595_SHIFT_REGISTER", "74HC595", "logic", "shift_registers"),
        _c("MCP2515", "MCP2515", "MCP2515", "can_controller", "communication"),
        _c("TJA1050", "TJA1050", "TJA1050", "can_transceiver", "communication"),
        _c("MAX485", "MAX485", "MAX485", "rs485_transceiver", "communication"),
        *_components_for([f"Q_MOSFET_{index}" for index in range(1, 5)], "IRLZ44N", "IRLZ44N", "mosfet", "mosfet_outputs"),
        *_components_for([f"Q_NPN_{index}" for index in range(1, 5)], "BC547", "BC547", "bjt", "relay_outputs"),
        *_components_for([f"K_RELAY_{index}" for index in range(1, 5)], "RELAY_5V", "5V relay", "relay", "relay_outputs"),
        *_components_for([f"D_FLYBACK_{index}" for index in range(1, 5)], "FLYBACK_DIODE", "Flyback diode", "diode", "mosfet_outputs"),
        *_components_for([f"D_RELAY_{index}" for index in range(1, 5)], "RELAY_FLYBACK_DIODE", "Relay flyback diode", "diode", "relay_outputs"),
        *_components_for([f"LED{index}" for index in range(1, 17)], "LED_INDICATOR", "LED", "indicator", "led_outputs"),
        *_components_for([f"SW_BTN_{index}" for index in range(1, 7)], "PUSH_BUTTON", "Push Button", "button", "buttons"),
        *_components_for([f"RV{index}" for index in range(1, 5)], "POTENTIOMETER", "Potentiometer", "analog_control", "analog"),
        *_components_for([f"U_LM358_CHANNEL_{index}" for index in range(1, 5)], "LM358", "LM358 channel", "opamp", "analog"),
        *_components_for([f"R_GATE_{index}" for index in range(1, 5)], "RESISTOR", "220 ohm gate resistor", "resistor", "mosfet_outputs"),
        *_components_for([f"R_PULLDOWN_{index}" for index in range(1, 5)], "R_10K_PULLUP", "10k pulldown", "pulldown", "mosfet_outputs"),
        *_components_for([f"R_BASE_{index}" for index in range(1, 5)], "RESISTOR", "2.2k base resistor", "resistor", "relay_outputs"),
        *_components_for([f"R_BTN_PD_{index}" for index in range(1, 7)], "R_10K_PULLUP", "10k pulldown", "pulldown", "buttons"),
        *_components_for([f"R_LED_{index}" for index in range(1, 17)], "R_220", "220 ohm", "series_resistor", "led_outputs"),
        _c("R_I2C_SDA", "R_4K7_PULLUP", "4.7k pullup", "pullup", "i2c"),
        _c("R_I2C_SCL", "R_4K7_PULLUP", "4.7k pullup", "pullup", "i2c"),
        *_components_for([f"C_DECOUPLE_{index}" for index in range(1, 25)], "C_100NF_CERAMIC", "100nF", "decoupling", "power"),
        *_components_for([f"R_PROT_{index}" for index in range(1, 9)], "RESISTOR", "GPIO protection resistor", "resistor", "expansion"),
        *_components_for([f"J_LOAD_{index}" for index in range(1, 5)], "SCREW_TERMINAL_2", "Load terminal", "connector", "mosfet_outputs"),
        *_components_for([f"J_RELAY_{index}" for index in range(1, 5)], "SCREW_TERMINAL_2", "Relay terminal", "connector", "relay_outputs"),
        *_components_for([f"J_HEADER_{index}" for index in range(1, 9)], "HEADER_CONNECTOR", "GPIO expansion header", "connector", "expansion"),
        _c("J_EXP1", "PIN_HEADER", "Expansion header 1", "connector", "shift_registers"),
        _c("J_EXP2", "PIN_HEADER", "Expansion header 2", "connector", "shift_registers"),
        _c("J_ANALOG", "PIN_HEADER", "Analog header", "connector", "analog"),
        _c("J_I2C", "I2C_HEADER", "I2C header", "connector", "i2c"),
        _c("J_SPI", "SPI_HEADER_FLASH", "SPI header", "connector", "spi"),
        _c("J_POWER", "PIN_HEADER", "Power header", "connector", "power"),
        _c("J_CAN", "CAN_TERMINAL", "CAN terminal", "connector", "communication"),
        _c("J_RS485", "RS485_TERMINAL", "RS485 terminal", "connector", "communication"),
        *_components_for([f"JP_MODE_{index}" for index in range(1, 7)], "CHIP_SELECT_JUMPER", "Mode jumper", "jumper", "expansion"),
        *_components_for([f"TP{index}" for index in range(1, 25)], "TEST_POINT", "Test point", "testpoint", "testpoints"),
    ]
    nets: dict[str, list[str]] = {
        "+5V": ["MCU.5V", "USB_UART1.VBUS", "USB_UART2.VBUS", "TJA1050.VCC", "MAX485.VCC", "J_POWER.1", "J_I2C.1", "J_SPI.1", "TP14.1"],
        "+3V3": ["ESP32.3V3", "BME280.VCC", "SSD1306.VCC", "DS3231.VCC", "W25Q64_1.VCC", "W25Q64_2.VCC", "MCP2515.VDD", "R_I2C_SDA.1", "R_I2C_SCL.1", "TP15.1"],
        "GND": ["MCU.GND", "ESP32.GND", "USB_UART1.GND", "USB_UART2.GND", "USB1.GND", "USB2.GND", "BME280.GND", "SSD1306.GND", "DS3231.GND", "W25Q64_1.GND", "W25Q64_2.GND", "MCP2515.VSS", "TJA1050.GND", "MAX485.GND", "J_POWER.2", "J_I2C.4", "J_SPI.6", "J_CAN.3", "J_RS485.3", "TP16.1"],
        "USB1_D_PLUS": ["USB1.D+", "USB_UART1.D+"],
        "USB1_D_MINUS": ["USB1.D-", "USB_UART1.D-"],
        "USB2_D_PLUS": ["USB2.D+", "USB_UART2.D+"],
        "USB2_D_MINUS": ["USB2.D-", "USB_UART2.D-"],
        "ESP_UART_RX": ["USB_UART1.TXD", "ESP32.U0RXD"],
        "ESP_UART_TX": ["USB_UART1.RXD", "ESP32.U0TXD"],
        "ARDUINO_UART_RX": ["USB_UART2.TXD", "MCU.RX0"],
        "ARDUINO_UART_TX": ["USB_UART2.RXD", "MCU.TX0"],
        "I2C_SDA": ["MCU.SDA", "BME280.SDA", "SSD1306.SDA", "DS3231.SDA", "R_I2C_SDA.2", "J_I2C.2", "TP1.1"],
        "I2C_SCL": ["MCU.SCL", "BME280.SCL", "SSD1306.SCL", "DS3231.SCL", "R_I2C_SCL.2", "J_I2C.3", "TP2.1"],
        "SPI_MOSI": ["MCU.MOSI", "W25Q64_1.DI", "W25Q64_2.DI", "MCP2515.SI", "J_SPI.4", "TP3.1"],
        "SPI_MISO": ["MCU.MISO", "W25Q64_1.DO", "W25Q64_2.DO", "MCP2515.SO", "J_SPI.5", "TP4.1"],
        "SPI_SCK": ["MCU.SCK", "W25Q64_1.CLK", "W25Q64_2.CLK", "MCP2515.SCK", "J_SPI.3", "TP5.1"],
        "CS_FLASH1": ["MCU.GPIO_CS1", "W25Q64_1.CS"],
        "CS_FLASH2": ["MCU.GPIO_CS2", "W25Q64_2.CS"],
        "CS_CAN": ["MCU.GPIO_CS_CAN", "MCP2515.CS"],
        "CAN_INT": ["MCU.GPIO_CAN_INT", "MCP2515.INT", "TP6.1"],
        "CAN_TXD": ["MCP2515.TXCAN", "TJA1050.TXD"],
        "CAN_RXD": ["MCP2515.RXCAN", "TJA1050.RXD"],
        "CANH": ["TJA1050.CANH", "J_CAN.1", "TP8.1"],
        "CANL": ["TJA1050.CANL", "J_CAN.2", "TP9.1"],
        "RS485_RO": ["MAX485.RO", "MCU.GPIO_RS485_RX"],
        "RS485_DI": ["MAX485.DI", "MCU.GPIO_RS485_TX"],
        "RS485_DE_RE": ["MAX485.DE", "MAX485.RE", "MCU.GPIO_RS485_DE", "TP7.1"],
        "RS485_A": ["MAX485.A", "J_RS485.1", "TP10.1"],
        "RS485_B": ["MAX485.B", "J_RS485.2", "TP11.1"],
        "SHIFT_MOSI": ["MCU.MOSI", "U595_1.SER"],
        "SHIFT_CLK": ["MCU.SCK", "U595_1.SHCP", "U595_2.SHCP", "U595_3.SHCP", "U595_4.SHCP"],
        "SHIFT_LATCH": ["MCU.GPIO_LATCH", "U595_1.STCP", "U595_2.STCP", "U595_3.STCP", "U595_4.STCP", "TP12.1"],
        "SHIFT_CHAIN_1": ["U595_1.Q7S", "U595_2.SER"],
        "SHIFT_CHAIN_2": ["U595_2.Q7S", "U595_3.SER"],
        "SHIFT_CHAIN_3": ["U595_3.Q7S", "U595_4.SER"],
        "SHIFT_ENABLE": ["U595_1.OE", "U595_2.OE", "U595_3.OE", "U595_4.OE", "GND", "TP13.1"],
        "SHIFT_RESET": ["U595_1.MR", "U595_2.MR", "U595_3.MR", "U595_4.MR", "+5V"],
    }
    for index in range(1, 5):
        nets[f"MOSFET{index}_CTRL"] = [f"MCU.GPIO_PWM_{index}", f"R_GATE_{index}.1"]
        nets[f"MOSFET{index}_GATE"] = [f"R_GATE_{index}.2", f"Q_MOSFET_{index}.G", f"R_PULLDOWN_{index}.1"]
        nets[f"MOSFET{index}_PULLDOWN"] = [f"R_PULLDOWN_{index}.2", "GND"]
        nets[f"MOSFET{index}_LOW"] = [f"Q_MOSFET_{index}.D", f"J_LOAD_{index}.2", f"D_FLYBACK_{index}.A"]
        nets[f"MOSFET{index}_HIGH"] = [f"J_LOAD_{index}.1", f"D_FLYBACK_{index}.K", "+5V"]
        nets[f"MOSFET{index}_SOURCE"] = [f"Q_MOSFET_{index}.S", "GND"]
        nets[f"RELAY{index}_CTRL"] = [f"MCU.GPIO_RELAY_{index}", f"R_BASE_{index}.1"]
        nets[f"RELAY{index}_BASE"] = [f"R_BASE_{index}.2", f"Q_NPN_{index}.B"]
        nets[f"RELAY{index}_EMITTER"] = [f"Q_NPN_{index}.E", "GND"]
        nets[f"RELAY{index}_COIL_LOW"] = [f"Q_NPN_{index}.C", f"K_RELAY_{index}.COIL_MINUS", f"D_RELAY_{index}.A"]
        nets[f"RELAY{index}_COIL_HIGH"] = [f"K_RELAY_{index}.COIL_PLUS", f"D_RELAY_{index}.K", "+5V"]
        nets[f"RELAY{index}_COM"] = [f"K_RELAY_{index}.COM", f"J_RELAY_{index}.1"]
        nets[f"RELAY{index}_NO"] = [f"K_RELAY_{index}.NO", f"J_RELAY_{index}.2"]
    for index in range(1, 17):
        source = f"U595_{1 if index <= 8 else 2}.Q{(index - 1) % 8}"
        nets[f"LED{index}_DRIVE"] = [source, f"R_LED_{index}.1"]
        nets[f"LED{index}_A"] = [f"R_LED_{index}.2", f"LED{index}.A"]
        nets[f"LED{index}_K"] = [f"LED{index}.K", "GND"]
    for index in range(8):
        nets[f"EXP1_Q{index}"] = [f"U595_3.Q{index}", f"J_EXP1.{index + 1}"]
        nets[f"EXP2_Q{index}"] = [f"U595_4.Q{index}", f"J_EXP2.{index + 1}"]
    for index in range(1, 7):
        nets[f"BUTTON{index}_NET"] = [f"MCU.GPIO_BTN_{index}", f"SW_BTN_{index}.1", f"R_BTN_PD_{index}.1"]
        nets[f"BUTTON{index}_GND"] = [f"R_BTN_PD_{index}.2", "GND"]
        nets[f"BUTTON{index}_5V"] = [f"SW_BTN_{index}.2", "+5V"]
    for index in range(1, 5):
        nets[f"ANALOG{index}_INPUT"] = [f"J_ANALOG.{index}", f"RV{index}.3"]
        nets[f"ANALOG{index}_WIPER"] = [f"RV{index}.2", f"U_LM358_CHANNEL_{index}.IN_PLUS"]
        nets[f"ANALOG{index}_GND"] = [f"RV{index}.1", "GND"]
        nets[f"ANALOG{index}_BUFFER"] = [f"U_LM358_CHANNEL_{index}.OUT", f"U_LM358_CHANNEL_{index}.IN_MINUS", f"MCU.ADC{index}"]
    for index in range(1, 25):
        if index % 2:
            nets["+5V"].append(f"C_DECOUPLE_{index}.1")
        else:
            nets["+3V3"].append(f"C_DECOUPLE_{index}.1")
        nets["GND"].append(f"C_DECOUPLE_{index}.2")
    for index in range(1, 9):
        nets[f"GPIO_EXT_{index}_MCU"] = [f"MCU.GPIO_EXT_{index}", f"R_PROT_{index}.1"]
        nets[f"GPIO_EXT_{index}_HEADER"] = [f"R_PROT_{index}.2", f"J_HEADER_{index}.1", f"TP{16 + index}.1"]
        nets["+5V"].append(f"J_HEADER_{index}.2")
        nets["GND"].append(f"J_HEADER_{index}.3")
        nets["+3V3"].append(f"J_HEADER_{index}.4")
    for index in range(1, 7):
        nets[f"MODE{index}_NET"] = [f"MCU.GPIO_MODE_{index}", f"JP_MODE_{index}.1"]
        nets[f"MODE{index}_GND"] = [f"JP_MODE_{index}.2", "GND"]
    return _raw_spec(
        "T10",
        "Near-Limit Mixed Schematic",
        "large repeated block schematic for serious placer and wire-planner stress",
        components,
        nets,
        blocks=[
            {"id": "A", "name": "Power section"},
            {"id": "B", "name": "Arduino + ESP32 + USB-UART"},
            {"id": "C", "name": "I2C sensor/display/RTC"},
            {"id": "D", "name": "SPI flash + shift-register LED expansion"},
            {"id": "E", "name": "CAN + RS485 communication"},
            {"id": "F", "name": "4 MOSFET outputs"},
            {"id": "G", "name": "4 transistor/relay outputs"},
            {"id": "H", "name": "6 buttons + 16 LEDs"},
            {"id": "I", "name": "LM358 analog input"},
            {"id": "J", "name": "headers, test points, connectors"},
        ],
    )


def _build_raw_test_specs() -> list[dict[str, Any]]:
    return [_t01(), _t02(), _t03(), _t04(), _t05(), _t06(), _t07(), _t08(), _t09(), _t10()]


def _m01() -> dict[str, Any]:
    components = [
        _c("G1", "GROUND", "GND", "reference", "power"),
        _c("V1", "VDC", "12V DC source", "source", "power"),
        _c("V2", "VSOURCE", "AC source", "source", "power"),
        _c("I1", "CSOURCE", "Current source", "source", "analog"),
        _c("V3", "VSIN", "Sine source", "source", "analog"),
        _c("V4", "VPULSE", "Pulse source", "source", "analog"),
        _c("F1", "FUSE", "Fuse", "protection", "power"),
        _c("SW1", "SWITCH", "Power switch", "switch", "power"),
        _c("J1", "TERMINAL", "Output terminal", "connector", "power"),
        _c("T1", "TRANSFORMER", "Transformer", "magnetics", "power"),
        _c("BR1", "BRIDGE RECTIFIER", "Bridge rectifier", "rectifier", "power"),
        _c("U1", "LM317", "LM317", "regulator", "power"),
        _c("U2", "LM7805", "LM7805", "regulator", "power"),
        _c("U3", "NE555", "NE555", "timer", "control"),
        _c("U4", "OPAMP", "Generic op-amp", "opamp", "analog"),
        _c("U5", "LM741", "LM741", "opamp", "analog"),
        _c("R1", "RES", "240 ohm", "resistor", "power"),
        _c("R2", "RES", "10k", "resistor", "control"),
        _c("R3", "RESISTOR", "4.7k", "resistor", "analog"),
        _c("R4", "R_220", "220 ohm", "resistor", "indicator"),
        _c("R5", "RES", "1k", "resistor", "control"),
        _c("RV1", "POT-HG", "10k pot", "control", "analog"),
        _c("C1", "CAP", "10nF", "capacitor", "control"),
        _c("C2", "CAP-ELEC", "100uF", "capacitor", "power"),
        _c("C3", "C_100NF_CERAMIC", "100nF", "capacitor", "power"),
        _c("L1", "REALIND", "47uH", "inductor", "power"),
        _c("D1", "DIODE", "Signal diode", "diode", "protection"),
        _c("D2", "1N4007", "1N4007", "diode", "power"),
        _c("D3", "1N4148", "1N4148", "diode", "signal"),
        _c("D4", "1N60", "1N60", "diode", "signal"),
        _c("DZ1", "BZX55C5", "5.1V zener", "zener", "protection"),
        _c("DZ2", "BZX79C5", "5.1V zener", "zener", "protection"),
        _c("LED1", "LED", "Timer LED", "indicator", "control"),
        _c("LED2", "LED_INDICATOR", "Signal LED", "indicator", "analog"),
        _c("Q1", "NPN", "NPN", "transistor", "driver"),
        _c("Q2", "PNP", "PNP", "transistor", "driver"),
        _c("Q3", "NMOS", "NMOS", "mosfet", "driver"),
        _c("Q4", "2N7000", "2N7000", "mosfet", "driver"),
        _c("Q5", "BS170", "BS170", "mosfet", "driver"),
    ]
    nets = {
        "GND": [
            "G1.1",
            "V1.2",
            "V2.2",
            "I1.2",
            "V3.2",
            "V4.2",
            "T1.2",
            "BR1.2",
            "C2.2",
            "C3.2",
            "U1.1",
            "U2.2",
            "U3.1",
            "U4.4",
            "U5.4",
            "RV1.1",
            "Q1.3",
            "Q2.3",
            "Q3.3",
            "Q4.3",
            "Q5.3",
            "DZ1.2",
            "DZ2.2",
            "J1.2",
            "LED2.K",
        ],
        "VIN": ["V1.1", "F1.1"],
        "VIN_FUSED": ["F1.2", "SW1.1"],
        "VIN_SWITCHED": ["SW1.2", "D2.1", "U1.3"],
        "VIN_PROTECTED": ["D2.2", "U2.1", "C2.1", "BR1.1"],
        "+5V": ["U2.3", "U3.8", "U3.4", "U4.7", "U5.7", "RV1.3", "R4.1", "J1.1", "C3.1"],
        "LM317_OUT": ["U1.2", "R1.1", "L1.1"],
        "LC_NODE": ["L1.2", "C1.1", "D1.1"],
        "CLAMP_NODE": ["D1.2", "DZ1.1", "DZ2.1", "R1.2"],
        "TIMER_RC": ["U3.2", "U3.6", "R2.1", "C1.2"],
        "TIMER_DISCH": ["U3.7", "R2.2"],
        "TIMER_CTRL": ["U3.5", "R5.1"],
        "TIMER_OUT": ["U3.3", "LED1.2", "R5.2"],
        "LED_TIMER_A": ["R4.2", "LED1.1"],
        "OPAMP_IN": ["RV1.2", "U4.3"],
        "OPAMP_FB": ["U4.2", "U4.6", "R3.1"],
        "OPAMP_LOAD": ["R3.2", "Q1.1"],
        "LM741_IN": ["V3.1", "U5.3"],
        "LM741_FB": ["U5.2", "U5.6", "Q2.1"],
        "PULSE_GATE": ["V4.1", "Q3.1", "Q4.1", "Q5.1"],
        "CURRENT_NODE": ["I1.1", "Q2.2"],
        "BJT_CHAIN": ["Q1.2", "D3.1"],
        "DIODE_BUS": ["D3.2", "D4.1"],
        "SMALL_DIODE_OUT": ["D4.2", "LED2.A"],
        "MOS_DRAIN_BUS": ["Q3.2", "Q4.2", "Q5.2"],
        "AC_PRIMARY_A": ["V2.1", "T1.1"],
        "AC_SECONDARY_A": ["T1.3", "BR1.3"],
        "AC_SECONDARY_B": ["T1.4", "BR1.4"],
    }
    return _raw_spec(
        "M01",
        "Proteus Alias Analog Power Board",
        "old and new analog, source, protection, and power aliases with pin-level nets",
        components,
        nets,
    )


def _m02() -> dict[str, Any]:
    logic_kinds = [
        ("U4027", "4027", "CD4027"),
        ("U4511", "4511", "CD4511"),
        ("U7447", "7447", "7447"),
        ("U7490", "7490", "7490"),
        ("U00", "74HC00", "74HC00"),
        ("U02", "74HC02", "74HC02"),
        ("U04", "74HC04", "74HC04"),
        ("U08", "74HC08", "74HC08"),
        ("U32", "74HC32", "74HC32"),
        ("U74", "74HC74", "74HC74"),
        ("U76", "74HC76", "74HC76"),
        ("U85", "74HC85", "74HC85"),
        ("U86", "74HC86", "74HC86"),
        ("U151", "74HC151", "74HC151"),
        ("U157", "74HC157", "74HC157"),
        ("U160", "74HC160", "74HC160"),
        ("U174", "74HC174", "74HC174"),
        ("U192", "74HC192", "74HC192"),
        ("U266", "74HC266", "74HC266"),
        ("U283", "74HC283", "74HC283"),
    ]
    components = [
        _c("G1", "GROUND", "GND", "reference", "logic"),
        _c("V1", "VDC", "5V logic supply", "source", "logic"),
        _c("J1", "PROGRAMMING_HEADER", "Control header", "connector", "logic"),
        _c("J2", "SPI_HEADER_FLASH", "SPI/debug header", "connector", "logic"),
        _c("DS1", "7SEGCOMA", "Common-anode display", "display", "display"),
        _c("DS2", "7SEGCOMK", "Common-cathode display", "display", "display"),
        *[_c(ref, kind, value, "logic_ic", "logic") for ref, kind, value in logic_kinds],
        _c("U595", "74HC595_SHIFT_REGISTER", "74HC595", "logic_ic", "logic"),
        _c("SW1", "DIP_SWITCH", "DIP switch", "input", "logic"),
        _c("RN1", "RESISTOR_NETWORK", "Resistor network", "resistor", "logic"),
        _c("DARR1", "LED_ARRAY", "RGB LED array", "indicator", "display"),
        _c("LED1", "LED_INDICATOR", "Logic LED", "indicator", "display"),
        _c("R1", "R_220", "220 ohm", "resistor", "display"),
    ]
    nets = {
        "+5V": [
            "V1.1",
            "J1.1",
            "J2.1",
            "DS1.10",
            "U4027.16",
            "U4511.16",
            "U00.14",
            "U02.14",
            "U04.14",
            "U08.14",
            "U32.14",
            "U74.14",
            "U76.5",
            "U85.16",
            "U86.14",
            "U151.16",
            "U157.16",
            "U160.16",
            "U174.16",
            "U192.16",
            "U266.14",
            "U283.16",
            "U595.16",
            "U595.MR",
            "RN1.COM",
            "R1.1",
        ],
        "GND": [
            "G1.1",
            "V1.2",
            "J1.2",
            "J2.6",
            "DS2.10",
            "U4027.8",
            "U4511.8",
            "U00.7",
            "U02.7",
            "U04.7",
            "U08.7",
            "U32.7",
            "U74.7",
            "U76.13",
            "U85.8",
            "U86.7",
            "U151.8",
            "U157.8",
            "U160.8",
            "U174.8",
            "U192.8",
            "U266.7",
            "U283.8",
            "U595.8",
            "U595.OE",
            "SW1.1",
            "DARR1.4",
            "LED1.K",
        ],
        "CLK": ["J1.3", "U4027.3", "U7490.14", "U160.2", "U192.4", "U74.3", "U76.1", "U595.SHCP"],
        "DATA_A": ["SW1.2", "U00.1", "U02.1", "U04.1", "U08.1", "U32.1", "U86.1", "U266.1", "U151.4", "U157.2", "U283.5"],
        "DATA_B": ["SW1.3", "U00.2", "U02.2", "U08.2", "U32.2", "U86.2", "U266.2", "U151.3", "U157.3", "U283.3"],
        "NAND_OUT": ["U00.3", "U74.2", "RN1.2"],
        "NOR_OUT": ["U02.3", "U76.2", "RN1.3"],
        "INV_OUT": ["U04.2", "U85.10", "RN1.4"],
        "AND_OUT": ["U08.3", "RN1.5"],
        "OR_OUT": ["U32.3", "RN1.6"],
        "XOR_OUT": ["U86.3", "U174.3", "RN1.7"],
        "XNOR_OUT": ["U266.3", "RN1.8"],
        "JK_Q": ["U4027.1", "U595.SER"],
        "SHIFT_LATCH": ["J2.2", "U595.STCP"],
        "BCD_A": ["U160.14", "U4511.7", "U7447.7"],
        "BCD_B": ["U160.13", "U4511.1", "U7447.1"],
        "BCD_C": ["U160.12", "U4511.2", "U7447.2"],
        "BCD_D": ["U160.11", "U4511.6", "U7447.6"],
        "RIPPLE_Q0": ["U7490.12", "J1.5"],
        "RIPPLE_Q1": ["U7490.9", "J1.6"],
        "RIPPLE_Q2": ["U7490.8", "J1.7"],
        "RIPPLE_Q3": ["U7490.11", "J1.8"],
        "SHIFT_Q0": ["U595.Q0", "J1.9"],
        "SHIFT_Q1": ["U595.Q1", "J1.10"],
        "SHIFT_Q2": ["U595.Q2", "J1.11"],
        "SHIFT_Q3": ["U595.Q3", "J1.12"],
        "SEG_CA_A": ["U7447.13", "DS1.1"],
        "SEG_CA_B": ["U7447.12", "DS1.2"],
        "SEG_CA_C": ["U7447.11", "DS1.3"],
        "SEG_CA_D": ["U7447.10", "DS1.4"],
        "SEG_CA_E": ["U7447.9", "DS1.5"],
        "SEG_CA_F": ["U7447.15", "DS1.6"],
        "SEG_CA_G": ["U7447.14", "DS1.7"],
        "SEG_CK_A": ["U4511.13", "DS2.1"],
        "SEG_CK_B": ["U4511.12", "DS2.2"],
        "SEG_CK_C": ["U4511.11", "DS2.3"],
        "SEG_CK_D": ["U4511.10", "DS2.4"],
        "SEG_CK_E": ["U4511.9", "DS2.5"],
        "SEG_CK_F": ["U4511.15", "DS2.6"],
        "SEG_CK_G": ["U4511.14", "DS2.7"],
        "LED_LOGIC_A": ["R1.2", "LED1.A", "U595.Q7"],
        "RGB_R": ["U174.2", "DARR1.1"],
        "RGB_G": ["U174.5", "DARR1.2"],
        "RGB_B": ["U174.6", "DARR1.3"],
        "MUX_OUT": ["U151.6", "J2.3"],
        "MUX_B_OUT": ["U157.7", "J1.13"],
        "COUNTER_LOAD": ["U192.11", "J1.4"],
        "ADDER_SUM0": ["U283.10", "J2.4"],
        "ADDER_SUM1": ["U283.11", "J1.14"],
    }
    return _raw_spec(
        "M02",
        "Proteus Alias Logic Display Board",
        "new logic/display aliases plus existing shift-register, switch, resistor-network, and LED parts",
        components,
        nets,
    )


def _m03() -> dict[str, Any]:
    components = [
        _c("G1", "GROUND", "GND", "reference", "mixed"),
        _c("V1", "VDC", "5V source", "source", "power"),
        _c("MCU", "ARDUINO_NANO", "Arduino Nano", "controller", "control"),
        _c("ESP", "ESP32_WROOM", "ESP32-WROOM", "wireless_controller", "control"),
        _c("BME", "BME280", "BME280", "sensor", "i2c"),
        _c("OLED", "SSD1306_OLED", "SSD1306 OLED", "display", "i2c"),
        _c("RTC", "DS3231", "DS3231", "rtc", "i2c"),
        _c("FLASH", "W25Q64", "W25Q64", "memory", "spi"),
        _c("CAN", "MCP2515", "MCP2515", "can_controller", "comm"),
        _c("CANPHY", "TJA1050", "TJA1050", "can_transceiver", "comm"),
        _c("RS485", "MAX485", "MAX485", "rs485_transceiver", "comm"),
        _c("AMP", "LM358", "LM358", "opamp", "analog"),
        _c("TIMER", "NE555", "NE555", "timer", "control"),
        _c("BUF", "LM741", "LM741", "opamp", "analog"),
        _c("Q1", "2N7000", "2N7000", "mosfet", "driver"),
        _c("Q2", "BS170", "BS170", "mosfet", "driver"),
        _c("D1", "1N4148", "1N4148", "diode", "signal"),
        _c("DZ1", "BZX55C5", "5.1V zener", "zener", "protection"),
        _c("C1", "CAP-ELEC", "47uF", "capacitor", "power"),
        _c("C2", "CAP", "100nF", "capacitor", "power"),
        _c("L1", "REALIND", "10uH", "inductor", "driver"),
        _c("R1", "RES", "10k", "resistor", "control"),
        _c("R2", "RESISTOR", "120 ohm", "resistor", "comm"),
        _c("SW1", "SWITCH", "Mode switch", "switch", "control"),
        _c("J_CAN", "TERMINAL", "CAN terminal", "connector", "comm"),
        _c("J_RS485", "TERMINAL", "RS485 terminal", "connector", "comm"),
        _c("J2", "PIN_HEADER", "Expansion header", "connector", "control"),
        _c("TP1", "TEST_POINT", "Debug test point", "testpoint", "control"),
    ]
    nets = {
        "+5V": ["V1.1", "MCU.5V", "RS485.VCC", "CANPHY.VCC", "AMP.VCC", "TIMER.8", "TIMER.4", "BUF.7", "SW1.1", "J2.1"],
        "+3V3": ["ESP.3V3", "BME.VCC", "OLED.VCC", "RTC.VCC", "FLASH.VCC", "CAN.VDD", "C2.1", "J2.2"],
        "GND": [
            "G1.1",
            "V1.2",
            "MCU.GND",
            "ESP.GND",
            "BME.GND",
            "OLED.GND",
            "RTC.GND",
            "FLASH.GND",
            "CAN.VSS",
            "CANPHY.GND",
            "RS485.GND",
            "AMP.GND",
            "TIMER.1",
            "BUF.4",
            "C1.2",
            "C2.2",
            "Q1.3",
            "Q2.3",
            "DZ1.2",
            "J2.3",
        ],
        "I2C_SDA": ["MCU.SDA", "ESP.IO21", "BME.SDA", "OLED.SDA", "RTC.SDA"],
        "I2C_SCL": ["MCU.SCL", "ESP.IO22", "BME.SCL", "OLED.SCL", "RTC.SCL"],
        "SPI_MOSI": ["MCU.MOSI", "FLASH.DI", "CAN.SI"],
        "SPI_MISO": ["MCU.MISO", "FLASH.DO", "CAN.SO"],
        "SPI_SCK": ["MCU.SCK", "FLASH.CLK", "CAN.SCK"],
        "SPI_CS_FLASH": ["MCU.D10", "FLASH.CS"],
        "SPI_CS_CAN": ["ESP.IO5", "CAN.CS"],
        "CAN_INT": ["ESP.IO4", "CAN.INT", "TP1.1"],
        "CAN_TXD": ["CAN.TXCAN", "CANPHY.TXD"],
        "CAN_RXD": ["CAN.RXCAN", "CANPHY.RXD"],
        "CANH": ["CANPHY.CANH", "J_CAN.1", "R2.1"],
        "CANL": ["CANPHY.CANL", "J_CAN.2", "R2.2"],
        "RS485_RO": ["RS485.RO", "MCU.D2"],
        "RS485_DI": ["RS485.DI", "MCU.D3"],
        "RS485_DE_RE": ["RS485.DE", "RS485.RE", "ESP.IO23"],
        "RS485_A": ["RS485.A", "J_RS485.1"],
        "RS485_B": ["RS485.B", "J_RS485.2"],
        "TIMER_TRIGGER": ["SW1.2", "TIMER.2", "TIMER.6", "R1.2", "C1.1"],
        "TIMER_PULLUP": ["R1.1", "DZ1.1"],
        "TIMER_OUTPUT": ["TIMER.3", "Q1.1", "D1.1"],
        "DIODE_TO_BUFFER": ["D1.2", "BUF.3"],
        "BUFFER_FEEDBACK": ["BUF.2", "BUF.6", "AMP.IN_PLUS"],
        "AMP_FEEDBACK": ["AMP.OUT", "AMP.IN_MINUS", "Q2.1"],
        "LOAD_LOW": ["Q1.2", "Q2.2", "L1.1"],
        "LOAD_OUT": ["L1.2", "J2.4"],
    }
    return _raw_spec(
        "M03",
        "Mixed Embedded Controller With Proteus Aliases",
        "existing embedded components combined with new Proteus-style source, logic, protection, and analog aliases",
        components,
        nets,
    )


def _build_raw_proteus_alias_mixed_specs() -> list[dict[str, Any]]:
    return [_m01(), _m02(), _m03()]


def _r01() -> dict[str, Any]:
    components = [
        _c("G1", "GROUND", "GND", "reference", "power"),
        _c("V1", "VDC", "12V DC source", "source", "power"),
        _c("F1", "FUSE", "Fuse", "protection", "power"),
        _c("SW1", "SWITCH", "Power switch", "switch", "power"),
        _c("D1", "1N4007", "1N4007", "diode", "power"),
        _c("U1", "LM317", "LM317", "regulator", "power"),
        _c("R1", "RES", "240 ohm", "resistor", "power"),
        _c("R2", "RES", "1.2k", "resistor", "power"),
        _c("R3", "R_220", "220 ohm", "resistor", "indicator"),
        _c("C1", "CAP", "100nF", "capacitor", "power"),
        _c("C2", "CAP-ELEC", "100uF", "capacitor", "power"),
        _c("L1", "REALIND", "47uH", "inductor", "power"),
        _c("D2", "DIODE", "Clamp diode", "diode", "protection"),
        _c("LED1", "LED", "Power LED", "indicator", "power"),
        _c("Q1", "2N7000", "2N7000", "mosfet", "driver"),
        _c("Q2", "BS170", "BS170", "mosfet", "driver"),
        _c("J1", "TERMINAL", "Load terminal", "connector", "power"),
    ]
    nets = {
        "GND": ["G1.1", "V1.2", "C1.2", "C2.2", "Q1.3", "Q2.3", "J1.2"],
        "VIN": ["V1.1", "F1.1"],
        "VIN_FUSED": ["F1.2", "SW1.1"],
        "VIN_SWITCHED": ["SW1.2", "D1.1"],
        "REG_IN": ["D1.2", "U1.3", "C2.1"],
        "REG_OUT": ["U1.2", "L1.1", "R1.1", "R3.1"],
        "LC_OUT": ["L1.2", "C1.1", "D2.1"],
        "ADJ": ["U1.1", "R1.2", "R2.1"],
        "ADJ_RETURN": ["R2.2", "D2.2"],
        "LED_A": ["R3.2", "LED1.1"],
        "LED_K": ["LED1.2", "Q1.2"],
        "DRIVE_GATE": ["Q1.1", "Q2.1"],
        "LOAD_OUT": ["Q2.2", "J1.1"],
    }
    return _raw_spec(
        "R01",
        "Routed Proteus Power Driver",
        "wire-heavy old/new alias demo with short power-driver nets",
        components,
        nets,
    )


def _r02() -> dict[str, Any]:
    components = [
        _c("G1", "GROUND", "GND", "reference", "logic"),
        _c("V1", "VDC", "5V logic source", "source", "logic"),
        _c("J1", "PROGRAMMING_HEADER", "Logic input header", "connector", "logic"),
        _c("U1", "74HC00", "74HC00", "logic_ic", "logic"),
        _c("U2", "74HC04", "74HC04", "logic_ic", "logic"),
        _c("U3", "74HC08", "74HC08", "logic_ic", "logic"),
        _c("U4", "74HC32", "74HC32", "logic_ic", "logic"),
        _c("U5", "74HC86", "74HC86", "logic_ic", "logic"),
        _c("U6", "74HC74", "74HC74", "logic_ic", "logic"),
        _c("U7", "4027", "CD4027", "logic_ic", "logic"),
        _c("U8", "4511", "CD4511", "decoder", "display"),
        _c("DS1", "7SEGCOMK", "Common-cathode display", "display", "display"),
        _c("RN1", "RESISTOR_NETWORK", "Pull network", "resistor", "logic"),
        _c("R1", "R_220", "220 ohm", "resistor", "indicator"),
        _c("LED1", "LED", "Logic LED", "indicator", "display"),
    ]
    nets = {
        "+5V": ["V1.1", "J1.1", "U1.14", "U2.14", "U3.14", "U4.14", "U5.14", "U6.14", "U7.16", "U8.16", "RN1.COM"],
        "GND": ["G1.1", "V1.2", "J1.2", "U1.7", "U2.7", "U3.7", "U4.7", "U5.7", "U6.7", "U7.8", "U8.8", "DS1.10", "LED1.2"],
        "IN_A": ["J1.3", "U1.1", "U3.1", "RN1.2"],
        "IN_B": ["J1.4", "U1.2", "U3.2", "RN1.3"],
        "NAND_OUT": ["U1.3", "U2.1"],
        "INV_OUT": ["U2.2", "U4.1"],
        "AND_OUT": ["U3.3", "U4.2"],
        "OR_OUT": ["U4.3", "U5.1"],
        "XOR_IN_B": ["J1.5", "U5.2"],
        "XOR_OUT": ["U5.3", "U6.2"],
        "CLK": ["J1.6", "U6.3", "U7.3"],
        "FF_Q": ["U6.5", "U7.5"],
        "JK_Q": ["U7.1", "R1.1"],
        "LED_A": ["R1.2", "LED1.1"],
        "BCD_A": ["J1.7", "U8.7"],
        "BCD_B": ["J1.8", "U8.1"],
        "BCD_C": ["J1.9", "U8.2"],
        "BCD_D": ["J1.10", "U8.6"],
        "SEG_A": ["U8.13", "DS1.1"],
        "SEG_B": ["U8.12", "DS1.2"],
        "SEG_C": ["U8.11", "DS1.3"],
        "SEG_D": ["U8.10", "DS1.4"],
        "SEG_E": ["U8.9", "DS1.5"],
        "SEG_F": ["U8.15", "DS1.6"],
        "SEG_G": ["U8.14", "DS1.7"],
    }
    return _raw_spec(
        "R02",
        "Routed Proteus Logic Display Chain",
        "wire-heavy logic chain using new Proteus-style logic aliases and existing display/passive parts",
        components,
        nets,
    )


def _r03() -> dict[str, Any]:
    components = [
        _c("G1", "GROUND", "GND", "reference", "embedded"),
        _c("V1", "VDC", "5V source", "source", "embedded"),
        _c("MCU", "ARDUINO_NANO", "Arduino Nano", "controller", "embedded"),
        _c("ESP", "ESP32_WROOM", "ESP32-WROOM", "wireless_controller", "embedded"),
        _c("BME", "BME280", "BME280", "sensor", "i2c"),
        _c("OLED", "SSD1306_OLED", "SSD1306 OLED", "display", "i2c"),
        _c("FLASH", "W25Q64", "W25Q64", "memory", "spi"),
        _c("RS485", "MAX485", "MAX485", "rs485_transceiver", "comm"),
        _c("J1", "TERMINAL", "RS485 terminal", "connector", "comm"),
        _c("SW1", "SWITCH", "Input switch", "switch", "control"),
        _c("D1", "1N4148", "1N4148", "diode", "protection"),
        _c("DZ1", "BZX55C5", "5.1V zener", "zener", "protection"),
        _c("R1", "RES", "10k", "resistor", "control"),
        _c("R2", "RESISTOR", "120 ohm", "resistor", "comm"),
        _c("C1", "CAP", "100nF", "capacitor", "embedded"),
        _c("C2", "C_100NF_CERAMIC", "100nF", "capacitor", "embedded"),
        _c("TP1", "TEST_POINT", "Debug point", "testpoint", "embedded"),
    ]
    nets = {
        "+5V": ["V1.1", "MCU.5V", "RS485.VCC", "SW1.1"],
        "+3V3": ["ESP.3V3", "BME.VCC", "OLED.VCC", "FLASH.VCC", "C1.1", "C2.1"],
        "GND": ["G1.1", "V1.2", "MCU.GND", "ESP.GND", "BME.GND", "OLED.GND", "FLASH.GND", "RS485.GND", "J1.2", "C1.2", "C2.2", "DZ1.2"],
        "I2C_SDA": ["MCU.SDA", "BME.SDA", "OLED.SDA"],
        "I2C_SCL": ["MCU.SCL", "BME.SCL", "OLED.SCL"],
        "SPI_MOSI": ["MCU.MOSI", "FLASH.DI"],
        "SPI_MISO": ["MCU.MISO", "FLASH.DO"],
        "SPI_SCK": ["MCU.SCK", "FLASH.CLK"],
        "SPI_CS": ["MCU.D10", "FLASH.CS"],
        "UART_TX": ["MCU.TX0", "RS485.DI"],
        "UART_RX": ["MCU.RX0", "RS485.RO"],
        "RS485_DE": ["ESP.IO23", "RS485.DE", "RS485.RE"],
        "RS485_A": ["RS485.A", "J1.1", "R2.1"],
        "RS485_B": ["RS485.B", "R2.2"],
        "BUTTON_NET": ["MCU.D2", "SW1.2", "R1.1"],
        "BUTTON_RETURN": ["R1.2", "D1.1"],
        "PROTECT_OUT": ["D1.2", "DZ1.1", "TP1.1"],
    }
    return _raw_spec(
        "R03",
        "Routed Old-New Embedded Mini Board",
        "wire-heavy embedded mini-board using old supported parts plus new protection aliases",
        components,
        nets,
    )


def _build_raw_proteus_alias_routed_specs() -> list[dict[str, Any]]:
    return [_r01(), _r02(), _r03()]


def _overlap_pairs(obstacles: list[dict[str, Any]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index, left in enumerate(obstacles):
        for right in obstacles[index + 1 :]:
            if (
                float(left["left"]) < float(right["right"])
                and float(left["right"]) > float(right["left"])
                and float(left["top"]) < float(right["bottom"])
                and float(left["bottom"]) > float(right["top"])
            ):
                pairs.append((str(left["owner"]), str(right["owner"])))
    return pairs


def _fresh_prefixed_run_dir(examples_root: Path, prefix: str, label: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y_%m_%d_%H%M%S")
    safe_label = slugify(label).lower()
    base = examples_root / f"{prefix}_{stamp}_{safe_label}"
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = examples_root / f"{base.name}_{suffix}"
        suffix += 1
    return candidate


def _fresh_run_dir(examples_root: Path, label: str) -> Path:
    return _fresh_prefixed_run_dir(examples_root, "final_json_run", label)


def _resolve_final_json_dir(source: Path) -> Path:
    if source.is_dir() and source.name == "final_json":
        return source
    nested = source / "final_json"
    if nested.is_dir():
        return nested
    if source.is_dir():
        return source
    raise FileNotFoundError(f"final JSON source does not exist or is not a directory: {source}")


def _final_json_files(source: Path) -> list[Path]:
    final_json_dir = _resolve_final_json_dir(source)
    files = sorted(path for path in final_json_dir.glob("*.json") if path.name != "manifest.json")
    if not files:
        raise ValueError(f"No final JSON files found in {final_json_dir}")
    return files


def generate_final_json_run(
    *,
    examples_root: Path,
    label: str = "t01_t10_connected_v1",
    run_dir: Path | None = None,
    suite: str = DEFAULT_FINAL_CIRCUIT_SUITE,
) -> dict[str, Any]:
    """Generate a fresh immutable final-JSON examples run and stage report."""
    run_path = run_dir or _fresh_run_dir(examples_root, label)
    if run_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing final JSON run folder: {run_path}")

    final_json_dir = run_path / "final_json"
    placer_input_dir = run_path / "placement_inputs"
    stage_report_dir = run_path / "stage_reports"
    final_json_dir.mkdir(parents=True)
    placer_input_dir.mkdir()
    stage_report_dir.mkdir()

    results: list[dict[str, Any]] = []
    for circuit in build_final_circuits(suite):
        cid = str(circuit["circuit_id"])
        stem = f"{cid}_{re.sub(r'[^a-z0-9]+', '_', circuit['circuit_name'].lower()).strip('_')}"
        final_path = final_json_dir / f"{stem}.json"
        placement_input = placer_ready_circuit(circuit)
        placement_path = placer_input_dir / f"{stem}_placement_input.json"
        final_path.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
        placement_path.write_text(json.dumps(placement_input, indent=2), encoding="utf-8")

        ctx = run_placer_pipeline(placement_input, write_trace=False)
        placement = ctx.placement_plan.as_dict()
        coordinate_plan = decide_arrangement(placement, circuit)
        beautified = apply_coordinate_edits(placement, coordinate_plan)
        wire_plan = plan_wire_routes(beautified, circuit, config=STAGE_REPORT_WIRE_CONFIG)
        overlaps = _overlap_pairs(beautified.get("obstacles", []))

        report = {
            "circuit_id": cid,
            "circuit_name": circuit["circuit_name"],
            "final_json": str(final_path.relative_to(run_path)),
            "placement_input": str(placement_path.relative_to(run_path)),
            "validation": circuit["validation"],
            "placement_ok": ctx.pipeline_summary()["ok"],
            "component_count": len(circuit["components"]),
            "net_count": len(circuit["nets"]),
            "endpoint_count": circuit["validation"]["endpoint_count"],
            "coordinate_edit_count": len(coordinate_plan.get("coordinate_edits", [])),
            "post_beautifier_overlap_count": len(overlaps),
            "post_beautifier_overlaps": overlaps,
            "wire_metrics": wire_plan["metrics"],
            "wire_warnings": wire_plan["warnings"],
        }
        (stage_report_dir / f"{stem}_stage_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        results.append(report)

    summary = {
        "schema": "progen-kicad-final-json-run/v0.1",
        "run_dir": str(run_path),
        "label": label,
        "suite": suite,
        "circuit_count": len(results),
        "all_final_json_valid": all(item["validation"]["status"] == "pass" for item in results),
        "all_placements_ok": all(item["placement_ok"] for item in results),
        "all_beautified_without_overlaps": all(item["post_beautifier_overlap_count"] == 0 for item in results),
        "total_components": sum(item["component_count"] for item in results),
        "total_nets": sum(item["net_count"] for item in results),
        "total_wired_routes": sum(item["wire_metrics"]["wired_route_count"] for item in results),
        "results": results,
    }
    (run_path / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_path / "README.md").write_text(
        f"# Connected Final JSON Run: {suite}\n\n"
        "This folder is an immutable generated record. It contains canonical final CircuitIR JSON, "
        "component-only placement inputs derived from that JSON, and per-circuit reports from the "
        "arrangement decider, beautifier, and wire planner.\n\n"
        "The final JSON was compiled by `kicad.pipeline.final_circuit_builder`, not by a one-shot AI prompt. "
        "Compiler repairs are recorded inside each JSON under `generation_notes.compiler_repairs`.\n\n"
        "Do not overwrite this folder. Generate a new `final_json_run_*` folder for any changed component, net, "
        "coordinate, route, value, or schema behavior.\n",
        encoding="utf-8",
    )
    return summary


def generate_projects_from_final_json(
    source: Path,
    *,
    examples_root: Path,
    label: str = "t01_t10_connected_projects_v1",
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate real KiCad placement projects from canonical final JSON files."""
    files = _final_json_files(source)
    final_json_dir = _resolve_final_json_dir(source)
    run_path = run_dir or _fresh_prefixed_run_dir(examples_root, "final_json_project_run", label)
    if run_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing final JSON project run folder: {run_path}")

    copied_final_json_dir = run_path / "final_json"
    placement_input_dir = run_path / "placement_inputs"
    projects_dir = run_path / "projects"
    copied_final_json_dir.mkdir(parents=True)
    placement_input_dir.mkdir()
    projects_dir.mkdir()

    results: list[dict[str, Any]] = []
    for source_file in files:
        circuit = json.loads(source_file.read_text(encoding="utf-8"))
        if not isinstance(circuit, dict):
            raise ValueError(f"{source_file} must contain a final CircuitIR object")
        validation = circuit.get("validation", {})
        if isinstance(validation, dict) and validation.get("status") != "pass":
            raise ValueError(f"{source_file} final JSON validation is not pass: {validation}")

        copied_final_json = copied_final_json_dir / source_file.name
        shutil.copy2(source_file, copied_final_json)

        stem = source_file.stem
        placement_input = placer_ready_circuit(circuit)
        placement_input_path = placement_input_dir / f"{stem}_placement_input.json"
        placement_input_path.write_text(json.dumps(placement_input, indent=2), encoding="utf-8")

        project_name = str(placement_input.get("project", {}).get("name") or stem)
        project_dir = projects_dir / slugify(project_name).lower()
        ctx = run_placer_pipeline(placement_input, out_dir=project_dir)
        manifest_path = project_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        results.append(
            {
                "circuit_id": circuit.get("circuit_id"),
                "circuit_name": circuit.get("circuit_name"),
                "final_json": str(copied_final_json.relative_to(run_path)),
                "placement_input": str(placement_input_path.relative_to(run_path)),
                "project_dir": str(project_dir.relative_to(run_path)),
                "open_this": str((project_dir / manifest["open_this"]).relative_to(run_path)),
                "schematic_file": str((project_dir / manifest["schematic_file"]).relative_to(run_path)),
                "component_count": manifest["component_count"],
                "symbol_instance_count": manifest["symbol_instance_count"],
                "static_checks_ok": bool(manifest["static_checks"]["ok"]),
                "placement_ok": ctx.pipeline_summary()["ok"],
                "mode": manifest["mode"],
                "note": "Project is generated from final JSON through the component placer only. Use kicad.pipeline.kicad_wire_maker for wired KiCad output.",
            }
        )

    summary = {
        "schema": "progen-kicad-final-json-project-run/v0.1",
        "run_dir": str(run_path),
        "source_final_json_dir": str(final_json_dir),
        "label": label,
        "input_count": len(files),
        "project_count": len(results),
        "all_projects_ok": all(item["placement_ok"] and item["static_checks_ok"] for item in results),
        "total_components": sum(int(item["component_count"]) for item in results),
        "total_symbol_instances": sum(int(item["symbol_instance_count"]) for item in results),
        "wire_maker_status": "available_separately; this command intentionally writes placement schematics with real embedded symbols",
        "results": results,
    }
    (run_path / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_path / "README.md").write_text(
        "# Final JSON To KiCad Project Run\n\n"
        "This folder is an immutable generated record. It takes canonical connected final JSON files, "
        "derives component-only placer input from each one, and writes openable KiCad projects using real "
        "embedded KiCad symbols.\n\n"
        "The final JSON files still contain the full connected net information. The `.kicad_sch` files in "
        "`projects/` are placement schematics only by design; use `kicad.pipeline.kicad_wire_maker` for wired output. "
        "Do not overwrite this folder; create a new `final_json_project_run_*` folder for any changed output.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate connected final CircuitIR JSON test circuits.")
    parser.add_argument("--examples-root", default="kicad/examples", help="Examples root for fresh final_json_run_* folders.")
    parser.add_argument("--label", default="t01_t10_connected_v1", help="Label suffix for the fresh generated folder.")
    parser.add_argument("--run-dir", help="Optional explicit fresh run directory.")
    parser.add_argument(
        "--suite",
        default=DEFAULT_FINAL_CIRCUIT_SUITE,
        choices=available_final_circuit_suites(),
        help="Named deterministic final JSON suite to generate.",
    )
    parser.add_argument("--prompt", help="Optional prompt to clean/enhance and print instead of generating files.")
    parser.add_argument(
        "--project-run-from-final-json",
        help="Final JSON folder or run folder containing final_json/; writes a fresh KiCad project run from those JSON files.",
    )
    args = parser.parse_args()

    if args.prompt is not None:
        print(json.dumps(clean_prompt(args.prompt), indent=2))
        return

    if args.project_run_from_final_json is not None:
        summary = generate_projects_from_final_json(
            Path(args.project_run_from_final_json),
            examples_root=Path(args.examples_root),
            label=args.label,
            run_dir=Path(args.run_dir) if args.run_dir else None,
        )
        print(json.dumps(summary, indent=2))
        return

    summary = generate_final_json_run(
        examples_root=Path(args.examples_root),
        label=args.label,
        run_dir=Path(args.run_dir) if args.run_dir else None,
        suite=args.suite,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
