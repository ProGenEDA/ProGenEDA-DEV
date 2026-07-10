"""Main input JSON validator and fixer.

This stage is intentionally deterministic. It accepts loose user/main JSON,
repairs the parts that can be repaired safely, then emits the canonical
CircuitIR JSON consumed by the KiCad generator.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import slugify

from .final_circuit_builder import (
    _c,
    _compile_nets,
    _endpoint_pin,
    _endpoint_ref,
    _infer_node_component_kind,
    _infer_node_component_value,
    _normalize_endpoint,
    build_final_circuits_from_node_spec_text,
    compile_raw_circuit,
    validate_final_circuit,
)
from .placement_catalog import resolve_placement_spec


INPUT_FIXER_SCHEMA = "progeneda-main-json-validator-fixer/v0.1"
DEFAULT_ROUTING_MODE = "combination"
CATALOGUE_PATH = Path(__file__).resolve().parent / "catelogues" / "component_catalogue.json"
GROUND_PIN_NAMES = {"0", "AGND", "COM", "DGND", "GND", "GNDA", "GNDD", "MINUS", "NEG", "VEE", "VSS"}
POWER_3V3_PIN_NAMES = {"3V3", "PLUS_3V3", "VDD", "VDDIO"}
POWER_5V_PIN_NAMES = {"5V", "PLUS_5V", "VCC", "VBUS", "USB_5V"}
POWER_INPUT_PIN_NAMES = {"IN", "PLUS", "VIN", "VI", "VRAW", "BAT", "VBAT", "VS", "VPLUS", "+"}
POWER_OUTPUT_PIN_NAMES = {"OUT", "VO", "VOUT"}
SIGNAL_ROLE_TOKENS = {
    "address",
    "analog_input",
    "bidirectional",
    "boot",
    "chip_select",
    "clock",
    "control",
    "data",
    "differential_bus",
    "enable",
    "feedback",
    "gpio",
    "i2c",
    "input",
    "load",
    "output",
    "reset",
    "serial_data_in",
    "spi",
    "uart",
}
LOW_VOLTAGE_KINDS = {
    "BME280",
    "CP2102",
    "DS3231",
    "ESP32_WROOM",
    "MICRO_SD_SOCKET",
    "SSD1306_OLED",
    "W25Q64",
}
FIVE_VOLT_KINDS = {
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC32",
    "74HC74",
    "74HC76",
    "74HC85",
    "74HC86",
    "74HC151",
    "74HC157",
    "74HC160",
    "74HC174",
    "74HC192",
    "74HC266",
    "74HC283",
    "7447",
    "7490",
    "ARDUINO_NANO",
    "LM358",
    "LM393_COMPARATOR",
    "MAX485",
    "MCP2515",
    "NE555",
    "TJA1050",
}
EXTRA_PIN_GROUPS_BY_KIND: dict[str, list[tuple[list[str], set[str]]]] = {
    "BME280": [(["VCC", "VDD"], {"power"}), (["GND"], {"ground"})],
    "SSD1306_OLED": [(["VCC", "VDD"], {"power"}), (["GND", "VSS"], {"ground"})],
    "DS3231": [(["VCC"], {"power"}), (["GND"], {"ground"}), (["BAT", "VBAT"], {"power_input"})],
    "W25Q64": [(["VCC", "8"], {"power"}), (["GND", "4"], {"ground"})],
    "CP2102": [(["VDD", "VIO"], {"power"}), (["VBUS"], {"power_input"}), (["GND"], {"ground"})],
    "CH340": [(["VCC"], {"power"}), (["GND"], {"ground"})],
    "MAX485": [(["VCC", "8"], {"power"}), (["GND", "5"], {"ground"})],
    "MCP2515": [(["VDD", "VCC"], {"power"}), (["VSS", "GND"], {"ground"})],
    "TJA1050": [(["VCC"], {"power"}), (["GND"], {"ground"})],
    "LM358": [(["VCC", "V+"], {"power"}), (["GND", "V-"], {"ground"})],
    "LM741": [(["V+", "VCC", "7"], {"power"}), (["V-", "GND", "4"], {"ground"})],
    "OPAMP": [(["V+", "VCC", "7"], {"power"}), (["V-", "GND", "4"], {"ground"})],
    "LM393_COMPARATOR": [(["VCC"], {"power"}), (["GND"], {"ground"})],
    "PAM8403": [(["VCC", "PVDD"], {"power"}), (["GND", "PGND"], {"ground"})],
    "ACS712": [(["VCC"], {"power"}), (["GND"], {"ground"})],
    "74HC595": [(["VCC", "16"], {"power"}), (["GND", "8"], {"ground"})],
    "74HC595_SHIFT_REGISTER": [(["VCC", "16"], {"power"}), (["GND", "8"], {"ground"})],
    "4027": [(["VDD", "VCC"], {"power"}), (["VSS", "GND"], {"ground"})],
    "4511": [(["VDD", "VCC"], {"power"}), (["VSS", "GND"], {"ground"})],
    "7447": [(["VCC"], {"power"}), (["GND"], {"ground"})],
    "7490": [(["VCC"], {"power"}), (["GND"], {"ground"})],
    "NE555": [(["VCC", "8"], {"power"}), (["GND", "1"], {"ground"})],
    "MICRO_SD_SOCKET": [(["VCC"], {"power"}), (["GND"], {"ground"})],
    "USB_C_CONNECTOR": [(["VBUS"], {"power_input"}), (["GND"], {"ground"})],
    "PROTECTION_IC": [(["B+", "VCC", "5"], {"power_input"}), (["B-", "GND", "6"], {"ground"})],
    "ARDUINO_NANO": [(["5V", "+5V", "27"], {"power"}), (["GND", "GND1", "GND2", "4", "29"], {"ground"}), (["VIN", "30"], {"power_input"})],
}
for _logic_kind in (
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC32",
    "74HC86",
    "74HC266",
):
    EXTRA_PIN_GROUPS_BY_KIND.setdefault(_logic_kind, [(["VCC", "14"], {"power"}), (["GND", "7"], {"ground"})])
for _logic_kind in ("74HC85", "74HC151", "74HC157", "74HC160", "74HC174", "74HC192", "74HC283"):
    EXTRA_PIN_GROUPS_BY_KIND.setdefault(_logic_kind, [(["VCC", "16"], {"power"}), (["GND", "8"], {"ground"})])
EXTRA_PIN_GROUPS_BY_KIND.setdefault("74HC74", [(["VCC", "14"], {"power"}), (["GND", "7"], {"ground"})])
EXTRA_PIN_GROUPS_BY_KIND.setdefault("74HC76", [(["VCC", "5"], {"power"}), (["GND", "13"], {"ground"})])
EXTRA_PIN_GROUPS_BY_KIND.setdefault("7447", [(["VCC", "16"], {"power"}), (["GND", "8"], {"ground"})])
EXTRA_PIN_GROUPS_BY_KIND.setdefault("7490", [(["VCC", "5"], {"power"}), (["GND", "10"], {"ground"})])
EXTRA_PIN_GROUPS_BY_KIND["4027"] = [(["VDD", "VCC", "16"], {"power"}), (["VSS", "GND", "8"], {"ground"})]
EXTRA_PIN_GROUPS_BY_KIND["4511"] = [(["VDD", "VCC", "16"], {"power"}), (["VSS", "GND", "8"], {"ground"})]
for _source_kind in ("VDC", "VSOURCE", "CSOURCE", "VSIN", "VPULSE", "VAC", "IDC"):
    EXTRA_PIN_GROUPS_BY_KIND.setdefault(_source_kind, [(["PLUS", "+", "1"], {"power_input"}), (["MINUS", "-", "2"], {"ground"})])
for _mosfet_kind in ("IRLZ44N", "MOSFET", "NMOS", "2N7000", "BS170"):
    EXTRA_PIN_GROUPS_BY_KIND.setdefault(
        _mosfet_kind,
        [
            (["G", "GATE", "1"], {"input", "control", "gate"}),
            (["D", "DRAIN", "2"], {"load", "passive", "drain"}),
            (["S", "SOURCE", "3"], {"return", "passive", "source"}),
        ],
    )
for _bjt_kind in ("BC547", "NPN", "PNP"):
    EXTRA_PIN_GROUPS_BY_KIND.setdefault(
        _bjt_kind,
        [
            (["B", "BASE"], {"input", "control", "base"}),
            (["C", "COLLECTOR"], {"load", "passive", "collector"}),
            (["E", "EMITTER"], {"return", "passive", "emitter"}),
        ],
    )
EXTRA_PIN_GROUPS_BY_KIND["PROTECTION_IC"] = [
    (["B+", "B_PLUS", "VCC", "5"], {"power_input"}),
    (["B-", "B_MINUS", "GND", "6"], {"ground"}),
    (["P+", "P_PLUS", "3"], {"power_output"}),
    (["P-", "P_MINUS", "1"], {"ground"}),
]

DROP_ENDPOINT_PINS_BY_KIND: dict[str, set[str]] = {
    "LM317": {"GND"},
    "TP4056": {"OUT+", "OUT-"},
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _string(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _normalized_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", str(value).strip().upper()).strip("_")


def _normalized_pin_token(value: str) -> str:
    text = str(value).strip().upper()
    text = text.replace("+", " PLUS ").replace("-", " MINUS ").replace("~", "")
    text = re.sub(r"\{|\}", "", text)
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


def _catalogue_components() -> dict[str, Any]:
    data = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    components = data.get("components", {})
    return components if isinstance(components, dict) else {}


def _catalogue_alias_map() -> dict[str, dict[str, Any]]:
    aliases: dict[str, dict[str, Any]] = {}
    for canonical, spec in _catalogue_components().items():
        if not isinstance(spec, dict):
            continue
        keys = [canonical, *[alias for alias in spec.get("aliases", []) if isinstance(alias, str)]]
        for key in keys:
            aliases[_normalized_token(key)] = spec
    return aliases


def _pin_role_map_for_kind(kind: str) -> dict[str, set[str]]:
    spec = _catalogue_alias_map().get(_normalized_token(kind), {})
    pins = spec.get("pin_model", {}).get("pins", {}) if isinstance(spec, dict) else {}
    out: dict[str, set[str]] = {}
    if isinstance(pins, dict):
        for pin_name, pin_spec in pins.items():
            if not isinstance(pin_spec, dict):
                continue
            roles = {str(role).strip().lower() for role in pin_spec.get("roles", []) if str(role).strip()}
            pin_type = str(pin_spec.get("type") or "").strip().lower()
            if pin_type:
                roles.add(pin_type)
            number = str(pin_spec.get("number") or "").strip()
            out[_normalized_pin_token(str(pin_name))] = roles
            if number:
                out[_normalized_pin_token(number)] = roles
    return out


def _pin_alias_groups_for_kind(kind: str) -> list[tuple[list[str], set[str]]]:
    spec = _catalogue_alias_map().get(_normalized_token(kind), {})
    pins = spec.get("pin_model", {}).get("pins", {}) if isinstance(spec, dict) else {}
    raw_groups: list[tuple[list[str], set[str]]] = []
    if isinstance(pins, dict):
        for pin_name, pin_spec in pins.items():
            if not isinstance(pin_spec, dict):
                continue
            roles = {str(role).strip().lower() for role in pin_spec.get("roles", []) if str(role).strip()}
            pin_type = str(pin_spec.get("type") or "").strip().lower()
            if pin_type:
                roles.add(pin_type)
            aliases = [_normalized_pin_token(str(pin_name))]
            number = str(pin_spec.get("number") or "").strip()
            if number:
                aliases.append(_normalized_pin_token(number))
            raw_groups.append((list(dict.fromkeys(alias for alias in aliases if alias)), roles))
    for aliases, roles in EXTRA_PIN_GROUPS_BY_KIND.get(_normalized_token(kind), []):
        raw_groups.append((list(dict.fromkeys(_normalized_pin_token(alias) for alias in aliases if _normalized_pin_token(alias))), roles))
    groups: list[tuple[list[str], set[str]]] = []
    for aliases, roles in raw_groups:
        alias_set = set(aliases)
        if not alias_set:
            continue
        merged = False
        for index, (existing_aliases, existing_roles) in enumerate(groups):
            if alias_set.isdisjoint(existing_aliases):
                continue
            groups[index] = (list(dict.fromkeys([*existing_aliases, *aliases])), {*existing_roles, *roles})
            merged = True
            break
        if not merged:
            groups.append((aliases, set(roles)))
    return groups


def _known_catalogue_pins(kind: str) -> set[str]:
    spec = _catalogue_alias_map().get(_normalized_token(kind), {})
    pins = spec.get("pin_model", {}).get("pins", {}) if isinstance(spec, dict) else {}
    out: set[str] = set()
    if isinstance(pins, dict):
        for pin_name, pin_spec in pins.items():
            out.add(_normalized_pin_token(str(pin_name)))
            if isinstance(pin_spec, dict) and pin_spec.get("number") is not None:
                out.add(_normalized_pin_token(str(pin_spec["number"])))
    return out


def _endpoint_text(item: Any) -> str | None:
    if isinstance(item, str):
        text = item.strip()
        return text or None
    if isinstance(item, dict):
        endpoint = item.get("endpoint")
        if isinstance(endpoint, str) and endpoint.strip():
            return endpoint.strip()
        ref = item.get("ref") or item.get("component") or item.get("component_ref")
        pin = item.get("pin") or item.get("pin_name") or item.get("pin_number")
        if ref is not None and pin is not None:
            return f"{ref}.{pin}"
    return None


def _safe_ref(value: Any, fallback: str) -> str:
    text = re.sub(r"[^A-Za-z0-9_]+", "_", _string(value)).strip("_")
    return text or fallback


def _pins_from_raw_components(raw_components: list[Any]) -> dict[str, dict[str, str]]:
    pins_by_ref: dict[str, dict[str, str]] = {}
    for index, component in enumerate(raw_components, 1):
        if not isinstance(component, dict):
            continue
        ref = _safe_ref(component.get("ref") or component.get("id"), f"U{index}")
        raw_pins = component.get("pins", {})
        if not isinstance(raw_pins, dict):
            continue
        pins_by_ref.setdefault(ref, {})
        for pin, net in raw_pins.items():
            pin_text = _string(pin)
            net_text = _string(net)
            if pin_text and net_text:
                pins_by_ref[ref][pin_text] = net_text
    return pins_by_ref


def _nets_from_any(data: dict[str, Any], repairs: list[dict[str, Any]]) -> dict[str, list[str]]:
    nets: dict[str, list[str]] = defaultdict(list)
    raw_nets = data.get("nets")
    if isinstance(raw_nets, dict):
        for net, raw_members in raw_nets.items():
            members = raw_members.get("members") if isinstance(raw_members, dict) else raw_members
            for member in _as_list(members):
                endpoint = _endpoint_text(member)
                if endpoint:
                    nets[str(net)].append(endpoint)
                else:
                    repairs.append({"kind": "dropped_bad_net_member", "net": str(net), "member": member})

    expected = data.get("expected_netlist", {})
    if isinstance(expected, dict):
        raw_expected_nets = expected.get("nets", [])
        if isinstance(raw_expected_nets, list):
            for item in raw_expected_nets:
                if not isinstance(item, dict):
                    continue
                name = _string(item.get("name"))
                if not name:
                    continue
                for member in _as_list(item.get("members")):
                    endpoint = _endpoint_text(member)
                    if endpoint and endpoint not in nets[name]:
                        nets[name].append(endpoint)

    for ref, pin_map in _pins_from_raw_components(_as_list(data.get("components"))).items():
        for pin, net in pin_map.items():
            endpoint = f"{ref}.{pin}"
            if endpoint not in nets[net]:
                nets[net].append(endpoint)
    return dict(nets)


def _pins_by_endpoint(nets: dict[str, list[str]]) -> dict[str, set[str]]:
    pins_by_ref: dict[str, set[str]] = defaultdict(set)
    for endpoints in nets.values():
        for endpoint in endpoints:
            if "." not in str(endpoint):
                continue
            ref = _endpoint_ref(str(endpoint))
            pin = _endpoint_pin(str(endpoint))
            if ref and pin:
                pins_by_ref[ref].add(pin)
    return pins_by_ref


def _assigned_pins_by_ref(nets: dict[str, list[str]]) -> dict[str, set[str]]:
    assigned: dict[str, set[str]] = defaultdict(set)
    for endpoints in nets.values():
        for endpoint in endpoints:
            if "." not in str(endpoint):
                continue
            assigned[_endpoint_ref(str(endpoint))].add(_normalized_pin_token(_endpoint_pin(str(endpoint))))
    return assigned


def _component_ref_candidates(component: dict[str, Any], index: int) -> str:
    return _safe_ref(component.get("ref") or component.get("id") or component.get("reference"), f"U{index}")


def _component_kind(component: dict[str, Any], ref: str, pins: set[str], repairs: list[dict[str, Any]]) -> str:
    raw_kind = _string(component.get("kind") or component.get("type") or component.get("name"))
    if raw_kind and resolve_placement_spec(raw_kind) is not None:
        return raw_kind
    inferred, reason = _infer_node_component_kind(raw_kind or ref, pins)
    repairs.append(
        {
            "kind": "component_kind_inferred" if not raw_kind else "component_kind_repaired",
            "ref": ref,
            "from": raw_kind,
            "to": inferred,
            "reason": reason,
        }
    )
    return inferred


def _raw_components_from_any(
    data: dict[str, Any],
    nets: dict[str, list[str]],
    repairs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    pins_by_ref = _pins_by_endpoint(nets)
    raw_components = [item for item in _as_list(data.get("components")) if isinstance(item, dict)]
    refs_seen: set[str] = set()
    components: list[dict[str, Any]] = []
    ref_counters: dict[str, int] = defaultdict(int)

    for index, component in enumerate(raw_components, 1):
        ref = _component_ref_candidates(component, index)
        if ref in refs_seen:
            base = ref
            ref_counters[base] += 1
            ref = f"{base}_{ref_counters[base] + 1}"
            repairs.append({"kind": "duplicate_ref_renamed", "from": base, "to": ref})
        refs_seen.add(ref)
        kind = _component_kind(component, ref, pins_by_ref.get(ref, set()), repairs)
        spec = resolve_placement_spec(kind)
        value = _string(component.get("value") or component.get("display_value"))
        if not value:
            value = _infer_node_component_value(ref, kind)
            repairs.append({"kind": "component_value_filled", "ref": ref, "value": value})
        components.append(_c(ref, kind, value, _string(component.get("role"), spec.category if spec else ""), _string(component.get("block"))))

    for ref in sorted(set(pins_by_ref) - refs_seen):
        kind, reason = _infer_node_component_kind(ref, pins_by_ref[ref])
        spec = resolve_placement_spec(kind)
        value = _infer_node_component_value(ref, kind)
        components.append(_c(ref, kind, value, spec.category if spec else "", "auto_added"))
        repairs.append(
            {
                "kind": "missing_component_added_from_net_endpoint",
                "ref": ref,
                "component_kind": kind,
                "reason": reason,
                "pin_count": len(pins_by_ref[ref]),
            }
        )
    return components


def _guess_terminal_net_for_pin(kind: str, pin: str, roles: set[str]) -> str | None:
    pin_token = _normalized_pin_token(pin)
    kind_token = _normalized_token(kind)
    role_tokens = {str(role).lower() for role in roles}
    if pin_token in GROUND_PIN_NAMES or "ground" in role_tokens or "negative" in role_tokens or "return" in role_tokens:
        return "GUESS_TERMINAL_GND"
    if pin_token in POWER_3V3_PIN_NAMES or kind_token in LOW_VOLTAGE_KINDS and ("power" in role_tokens or pin_token in {"VCC", "VDD"}):
        return "GUESS_TERMINAL_3V3"
    if pin_token in POWER_5V_PIN_NAMES or kind_token in FIVE_VOLT_KINDS and ("power" in role_tokens or pin_token in {"VCC", "VDD"}):
        return "GUESS_TERMINAL_5V"
    if pin_token in POWER_INPUT_PIN_NAMES or "power_input" in role_tokens or "source" in role_tokens and "positive" in role_tokens:
        return "GUESS_TERMINAL_VIN"
    if pin_token in POWER_OUTPUT_PIN_NAMES or "power_output" in role_tokens:
        return "GUESS_TERMINAL_VOUT"
    if role_tokens and not role_tokens.isdisjoint(SIGNAL_ROLE_TOKENS):
        return None
    return None


def _add_guessed_terminal_nets(
    *,
    components: list[dict[str, Any]],
    nets: dict[str, list[str]],
    repairs: list[dict[str, Any]],
) -> set[str]:
    assigned = _assigned_pins_by_ref(nets)
    guessed: dict[str, list[str]] = defaultdict(list)
    for component in components:
        ref = str(component.get("ref") or "")
        kind = str(component.get("kind") or "")
        if not ref or not kind:
            continue
        assigned_for_ref = assigned.get(ref, set())
        for aliases, roles in _pin_alias_groups_for_kind(kind):
            if not aliases:
                continue
            if any(alias in assigned_for_ref for alias in aliases):
                continue
            pin = aliases[0]
            guess_net = _guess_terminal_net_for_pin(kind, pin, roles)
            if not guess_net:
                continue
            guessed[guess_net].append(f"{ref}.{pin}")
    kept: set[str] = set()
    for net, endpoints in sorted(guessed.items()):
        unique = list(dict.fromkeys(endpoints))
        if len(unique) < 2:
            repairs.append({"kind": "guessed_terminal_net_dropped_single_endpoint", "net": net, "endpoints": unique})
            continue
        nets.setdefault(net, [])
        for endpoint in unique:
            if endpoint not in nets[net]:
                nets[net].append(endpoint)
        kept.add(net)
        repairs.append(
            {
                "kind": "guessed_terminal_net_added",
                "net": net,
                "endpoint_count": len(unique),
                "terminal_required": True,
                "reason": "catalogue_pin_roles_and_common_power_ground_rules",
            }
        )
    return kept


def _force_guess_names_for_repaired_nets(
    nets: dict[str, list[str]],
    repairs: list[dict[str, Any]],
) -> tuple[dict[str, list[str]], set[str]]:
    guessed_terminal_nets: set[str] = set()
    out: dict[str, list[str]] = {}
    for net, endpoints in nets.items():
        net_name = str(net).strip() or "UNNAMED"
        upper = net_name.upper()
        repaired = upper.startswith("GUESS") or upper.startswith("FIXED") or upper.startswith("AUTO")
        if repaired:
            target = upper if upper.startswith("GUESS_TERMINAL_") else f"GUESS_TERMINAL_{_normalized_token(net_name)}"
            guessed_terminal_nets.add(target)
            repairs.append({"kind": "repaired_net_marked_terminal_guess", "from": net_name, "to": target})
        else:
            target = net_name
        out.setdefault(target, [])
        for endpoint in endpoints:
            if endpoint not in out[target]:
                out[target].append(endpoint)
    return out, guessed_terminal_nets


EQUIVALENT_RAILS_BY_GUESS_NET: dict[str, set[str]] = {
    "GUESS_TERMINAL_GND": {"0", "AGND", "COM", "DGND", "GND", "GNDA", "GNDD", "VEE", "VSS"},
    "GUESS_TERMINAL_3V3": {"+3V3", "3V3", "VDDIO"},
    "GUESS_TERMINAL_5V": {"+5V", "5V", "USB_5V", "VBUS", "VCC"},
    "GUESS_TERMINAL_VIN": {"BAT", "VBAT", "VIN", "VRAW", "VS"},
    "GUESS_TERMINAL_VOUT": {"OUT", "VOUT"},
}


def _net_token_parts(net_name: str) -> set[str]:
    token = _normalized_token(net_name)
    parts = {part for part in token.split("_") if part}
    parts.add(token)
    return parts


def _net_matches_rail_family(net_name: str, guess_net: str) -> bool:
    token = _normalized_token(net_name)
    parts = _net_token_parts(net_name)
    rail_tokens = {_normalized_token(rail) for rail in EQUIVALENT_RAILS_BY_GUESS_NET.get(guess_net, set())}
    if token in rail_tokens:
        return True
    if guess_net == "GUESS_TERMINAL_GND":
        return bool({"GND", "GROUND", "DGND", "AGND", "VSS"} & parts) or token.endswith("_GND")
    if not parts.isdisjoint(rail_tokens):
        return True
    if guess_net == "GUESS_TERMINAL_3V3":
        return "3V3" in parts or token.endswith("_3V3")
    if guess_net == "GUESS_TERMINAL_5V":
        return bool({"5V", "VCC", "VBUS"} & parts) or token.endswith("_5V")
    if guess_net == "GUESS_TERMINAL_VIN":
        return bool({"VIN", "VBAT", "BAT", "VRAW"} & parts) or token.endswith("_VIN")
    if guess_net == "GUESS_TERMINAL_VOUT":
        return "VOUT" in parts or token.endswith("_VOUT")
    return False


def _merge_equivalent_rails_into_guesses(
    nets: dict[str, list[str]],
    guessed_terminal_nets: set[str],
    repairs: list[dict[str, Any]],
) -> dict[str, list[str]]:
    if not guessed_terminal_nets:
        return nets
    target_by_rail: dict[str, str] = {}
    for guess_net in guessed_terminal_nets:
        for rail in EQUIVALENT_RAILS_BY_GUESS_NET.get(guess_net, set()):
            target_by_rail[_normalized_token(rail)] = guess_net
    if not target_by_rail:
        return nets

    out: dict[str, list[str]] = {}
    for net, endpoints in nets.items():
        net_text = str(net)
        target = target_by_rail.get(_normalized_token(net_text), net_text)
        if target == net_text:
            for guess_net in sorted(guessed_terminal_nets):
                if _net_matches_rail_family(net_text, guess_net):
                    target = guess_net
                    break
        if target != net_text:
            repairs.append(
                {
                    "kind": "equivalent_rail_merged_into_guessed_terminal_net",
                    "from": net_text,
                    "to": target,
                    "endpoint_count": len(endpoints),
                }
            )
            guessed_terminal_nets.add(target)
        out.setdefault(target, [])
        for endpoint in endpoints:
            if endpoint not in out[target]:
                out[target].append(endpoint)
    return out


def _drop_known_invalid_endpoint(kind: str, pin: str) -> str | None:
    kind_token = _normalized_token(kind)
    pin_token = _normalized_pin_token(pin)
    for bad_pin in DROP_ENDPOINT_PINS_BY_KIND.get(kind_token, set()):
        if pin_token == _normalized_pin_token(bad_pin):
            return f"{kind_token}.{bad_pin}"
    return None


def _is_guessed_terminal_net(net_name: str) -> bool:
    return str(net_name).upper().startswith("GUESS_TERMINAL_")


def _physical_pin_group_map(kind: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for index, (aliases, _roles) in enumerate(_pin_alias_groups_for_kind(kind)):
        normalized_aliases = [alias for alias in aliases if alias]
        if not normalized_aliases:
            continue
        group_id = f"group_{index}_{'_'.join(sorted(normalized_aliases)[:4])}"
        for alias in normalized_aliases:
            out[alias] = group_id
    return out


def _dedupe_physical_pin_net_conflicts(
    nets: dict[str, list[str]],
    kind_by_ref: dict[str, str],
    repairs: list[dict[str, Any]],
) -> dict[str, list[str]]:
    assignments: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    group_maps = {ref: _physical_pin_group_map(kind) for ref, kind in kind_by_ref.items()}
    for net, endpoints in nets.items():
        for endpoint in endpoints:
            ref = _endpoint_ref(endpoint)
            pin = _endpoint_pin(endpoint)
            group_id = group_maps.get(ref, {}).get(_normalized_pin_token(pin))
            if group_id:
                assignments[(ref, group_id)].append((net, endpoint))

    endpoints_to_drop: set[tuple[str, str]] = set()
    nets_to_merge: dict[str, str] = {}
    for (ref, group_id), items in assignments.items():
        nets_for_group = sorted({net for net, _endpoint in items})
        if len(nets_for_group) < 2:
            continue
        guessed = [net for net in nets_for_group if _is_guessed_terminal_net(net)]
        explicit = [net for net in nets_for_group if not _is_guessed_terminal_net(net)]
        if guessed and explicit:
            for net, endpoint in items:
                if net in guessed:
                    endpoints_to_drop.add((net, endpoint))
            repairs.append(
                {
                    "kind": "physical_pin_conflict_guessed_endpoint_dropped",
                    "ref": ref,
                    "pin_group": group_id,
                    "guessed_nets": guessed,
                    "explicit_nets": explicit,
                    "dropped_endpoint_count": sum(1 for net, _endpoint in items if net in guessed),
                    "reason": "explicit user/input nets outrank inferred GUESS_TERMINAL_* endpoint ownership for the same physical pin",
                }
            )
        elif len(guessed) > 1 and not explicit:
            target = guessed[0]
            for net in guessed[1:]:
                nets_to_merge[net] = target
            repairs.append(
                {
                    "kind": "physical_pin_conflict_guessed_nets_merged",
                    "ref": ref,
                    "pin_group": group_id,
                    "from": guessed[1:],
                    "to": target,
                    "terminal_required": True,
                }
            )
        else:
            repairs.append(
                {
                    "kind": "physical_pin_conflict_left_unfixed",
                    "ref": ref,
                    "pin_group": group_id,
                    "nets": nets_for_group,
                    "reason": "multiple explicit nets claim aliases for the same physical pin; fixer cannot choose safely",
                }
            )

    out: dict[str, list[str]] = {}
    for net, endpoints in nets.items():
        target = nets_to_merge.get(net, net)
        for endpoint in endpoints:
            if (net, endpoint) in endpoints_to_drop:
                continue
            out.setdefault(target, [])
            if endpoint not in out[target]:
                out[target].append(endpoint)

    cleaned: dict[str, list[str]] = {}
    for net, endpoints in out.items():
        unique = list(dict.fromkeys(endpoints))
        if len(unique) < 2:
            repairs.append(
                {
                    "kind": "dropped_single_endpoint_net_after_physical_pin_repair",
                    "net": net,
                    "endpoint_count": len(unique),
                }
            )
            continue
        cleaned[net] = unique
    return cleaned


def _project_name(data: dict[str, Any], fallback: str) -> str:
    project = data.get("project", {})
    if isinstance(project, dict):
        return _string(project.get("name") or project.get("title"), fallback)
    return fallback


def validate_and_fix_main_json(
    data: dict[str, Any],
    *,
    routing_mode: str = DEFAULT_ROUTING_MODE,
    source: str = "main_json_validator_fixer",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object")
    repairs: list[dict[str, Any]] = []
    nets = _nets_from_any(data, repairs)
    components = _raw_components_from_any(data, nets, repairs)
    guessed_terminal_nets = _add_guessed_terminal_nets(components=components, nets=nets, repairs=repairs)
    nets, repaired_guess_nets = _force_guess_names_for_repaired_nets(nets, repairs)
    guessed_terminal_nets.update(repaired_guess_nets)
    nets = _merge_equivalent_rails_into_guesses(nets, guessed_terminal_nets, repairs)
    refs = {str(component["ref"]) for component in components}
    kind_by_ref = {str(component["ref"]): str(component.get("kind") or "") for component in components}
    normalized_nets: dict[str, list[str]] = {}
    for net, endpoints in nets.items():
        fixed_endpoints: list[str] = []
        for endpoint in endpoints:
            endpoint_text = _normalize_endpoint(str(endpoint), refs, repairs)
            if "." not in endpoint_text:
                repairs.append({"kind": "dropped_non_endpoint_net_member", "net": net, "member": endpoint})
                continue
            if _endpoint_ref(endpoint_text) not in refs:
                repairs.append({"kind": "dropped_unknown_ref_endpoint", "net": net, "endpoint": endpoint_text})
                continue
            bad_endpoint = _drop_known_invalid_endpoint(kind_by_ref.get(_endpoint_ref(endpoint_text), ""), _endpoint_pin(endpoint_text))
            if bad_endpoint:
                repairs.append(
                    {
                        "kind": "dropped_known_invalid_component_endpoint",
                        "net": str(net),
                        "endpoint": endpoint_text,
                        "reason": f"{bad_endpoint} is a board-level or non-existent pin for the selected KiCad symbol",
                    }
                )
                continue
            fixed_endpoints.append(endpoint_text)
        if len(dict.fromkeys(fixed_endpoints)) >= 2:
            normalized_nets[str(net)] = list(dict.fromkeys(fixed_endpoints))
        else:
            repairs.append({"kind": "dropped_single_endpoint_net", "net": str(net), "endpoint_count": len(set(fixed_endpoints))})

    normalized_nets = _dedupe_physical_pin_net_conflicts(normalized_nets, kind_by_ref, repairs)
    guessed_terminal_nets.intersection_update(normalized_nets)

    if isinstance(data.get("routing"), dict):
        raw_requested_mode = routing_mode or data["routing"].get("mode")
    else:
        raw_requested_mode = routing_mode
    requested_mode = _string(raw_requested_mode, DEFAULT_ROUTING_MODE)
    if requested_mode not in {"wire", "terminal", "combination"}:
        repairs.append({"kind": "routing_mode_repaired", "from": requested_mode, "to": DEFAULT_ROUTING_MODE})
        requested_mode = DEFAULT_ROUTING_MODE

    circuit_id = _string(data.get("circuit_id"), "FIXED001")
    raw = {
        "circuit_id": circuit_id,
        "name": _string(data.get("circuit_name") or data.get("name"), _project_name(data, circuit_id)),
        "purpose": _string(data.get("purpose"), "validated and repaired main JSON input"),
        "components": components,
        "nets": normalized_nets,
        "routing_mode": requested_mode,
        "routing_decision_source": "main_json_validator_fixer",
        "source": source,
        "source_format": "loose_or_canonical_main_json",
        "blocks": data.get("blocks", [] if not isinstance(data.get("blocks"), list) else data.get("blocks")),
    }
    fixed = compile_raw_circuit(raw)
    if isinstance(data.get("generation_variation"), dict):
        fixed["generation_variation"] = deepcopy(data["generation_variation"])
    if guessed_terminal_nets:
        fixed["routing"].setdefault("terminal_policy", {})
        policy = fixed["routing"]["terminal_policy"]
        existing = policy.get("terminal_nets", [])
        if isinstance(existing, str):
            existing = [existing]
        if not isinstance(existing, list):
            existing = []
        policy["terminal_nets"] = sorted({*map(str, existing), *guessed_terminal_nets})
        policy["guessed_terminal_nets"] = sorted(guessed_terminal_nets)
        policy["guessed_terminal_net_rule"] = "Every net invented or renamed by the fixer is named GUESS_TERMINAL_* and must be terminalized."
        policy["fallback_unroutable_or_invalid_wires_to_terminal"] = True
    fixed_notes = fixed.setdefault("generation_notes", {})
    fixed_notes["input_validator_fixer"] = {
        "schema": INPUT_FIXER_SCHEMA,
        "source": source,
        "repair_count": len(repairs),
        "repairs": repairs,
        "guessed_terminal_nets": sorted(guessed_terminal_nets),
    }
    fixed["validation"] = validate_final_circuit(fixed)
    report = {
        "schema": INPUT_FIXER_SCHEMA,
        "stage": "input_json_validator_fixer",
        "ok": fixed["validation"]["status"] == "pass",
        "source": source,
        "repair_count": len(repairs),
        "repairs": repairs,
        "guessed_terminal_nets": sorted(guessed_terminal_nets),
        "validation": fixed["validation"],
        "component_count": len(fixed["components"]),
        "net_count": len(fixed["nets"]),
        "endpoint_count": fixed["validation"].get("endpoint_count", 0),
    }
    return fixed, report


def load_json_lenient(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def fix_json_file(
    source: Path,
    *,
    output: Path,
    report_output: Path | None = None,
    routing_mode: str = DEFAULT_ROUTING_MODE,
) -> dict[str, Any]:
    fixed, report = validate_and_fix_main_json(load_json_lenient(source), routing_mode=routing_mode, source=str(source))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(fixed, indent=2), encoding="utf-8")
    if report_output is not None:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def compile_node_spec_file(
    source: Path,
    *,
    output_dir: Path,
    report_output: Path | None = None,
    routing_mode: str = DEFAULT_ROUTING_MODE,
) -> dict[str, Any]:
    circuits = build_final_circuits_from_node_spec_text(source.read_text(encoding="utf-8"), source=str(source))
    output_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict[str, Any]] = []
    for circuit in circuits:
        circuit = deepcopy(circuit)
        circuit["routing"]["mode"] = routing_mode
        circuit["routing"]["terminal_policy"]["fallback_unroutable_or_invalid_wires_to_terminal"] = routing_mode == "combination"
        circuit["validation"] = validate_final_circuit(circuit)
        stem = f"{circuit['circuit_id']}_{slugify(circuit['circuit_name']).lower()}"
        output_path = output_dir / f"{stem}.json"
        output_path.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
        reports.append(
            {
                "circuit_id": circuit["circuit_id"],
                "output": str(output_path),
                "validation": circuit["validation"],
                "component_count": len(circuit["components"]),
                "net_count": len(circuit["nets"]),
            }
        )
    summary = {
        "schema": INPUT_FIXER_SCHEMA,
        "stage": "node_spec_to_main_json_compiler",
        "source": str(source),
        "routing_mode": routing_mode,
        "circuit_count": len(circuits),
        "all_valid": all(item["validation"]["status"] == "pass" for item in reports),
        "total_components": sum(item["component_count"] for item in reports),
        "total_nets": sum(item["net_count"] for item in reports),
        "results": reports,
    }
    if report_output is not None:
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/fix ProGenEDA main JSON or compile node-spec text into fixed JSON.")
    sub = parser.add_subparsers(dest="command", required=True)

    fix = sub.add_parser("fix-json", help="Fix one loose/canonical main JSON file.")
    fix.add_argument("input", type=Path)
    fix.add_argument("--output", required=True, type=Path)
    fix.add_argument("--report", type=Path)
    fix.add_argument("--routing-mode", default=DEFAULT_ROUTING_MODE, choices=("wire", "terminal", "combination"))

    node = sub.add_parser("compile-node-spec", help="Compile CIRCUIT/REF.PIN -> NET text into fixed main JSON files.")
    node.add_argument("input", type=Path)
    node.add_argument("--output-dir", required=True, type=Path)
    node.add_argument("--report", type=Path)
    node.add_argument("--routing-mode", default=DEFAULT_ROUTING_MODE, choices=("wire", "terminal", "combination"))

    args = parser.parse_args()
    if args.command == "fix-json":
        report = fix_json_file(args.input, output=args.output, report_output=args.report, routing_mode=args.routing_mode)
    else:
        report = compile_node_spec_file(args.input, output_dir=args.output_dir, report_output=args.report, routing_mode=args.routing_mode)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report.get("ok", report.get("all_valid", False)) else 1)


if __name__ == "__main__":
    main()
