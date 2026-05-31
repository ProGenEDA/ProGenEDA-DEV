"""Predefined locked inductor CircuitIR cases."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .inductor_ir import BASE_PROJECT, GENERATOR_TARGET, SCHEMA_VERSION


def _base_payload(name: str, basename: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_target": GENERATOR_TARGET,
        "project": {
            "name": name,
            "output_basename": basename,
            "base": BASE_PROJECT,
            "units": "proteus_internal",
        },
        "nodes": [],
        "components": [],
        "layout": {
            "mode": "manual_component_positions",
            "coordinate_units": "proteus_internal",
            "component_positions": {},
            "visual_wires": [],
            "auto_place": False,
        },
        "metadata": {
            "component_family": "INDUCTOR",
            "source": "locked main inductor examples",
        },
    }


def three_terminal_inductors_case() -> dict[str, Any]:
    payload = _base_payload("Three terminal inductors", "inductor_locked_t01_three_terminal")
    payload["nodes"] = [{"id": node, "kind": "internal"} for node in ("N1", "N2", "N3", "N4", "N5", "N6")]
    payload["components"] = [
        {"ref": "L1", "type": "INDUCTOR", "value": "1mH", "nodes": ["N1", "N2"], "visual": {}},
        {"ref": "L2", "type": "INDUCTOR", "value": "2mH", "nodes": ["N3", "N4"], "visual": {}},
        {"ref": "L3", "type": "INDUCTOR", "value": "10uH", "nodes": ["N5", "N6"], "visual": {}},
    ]
    payload["layout"]["component_positions"] = {
        "L1": {"x": -7366000, "y": 1270000},
        "L2": {"x": -7366000, "y": 0},
        "L3": {"x": -7366000, "y": -1270000},
    }
    return payload


def single_power_ground_inductor_case() -> dict[str, Any]:
    payload = _base_payload("Single V0 G0 inductor", "inductor_locked_t02_single_power_ground")
    payload["nodes"] = [
        {"id": "V0", "kind": "power"},
        {"id": "G0", "kind": "ground"},
    ]
    payload["components"] = [
        {"ref": "LA", "type": "INDUCTOR", "value": "2mH", "nodes": ["V0", "G0"], "visual": {"internal_power_node": "B1"}},
    ]
    payload["layout"]["component_positions"] = {"LA": {"x": -7366000, "y": 1270000}}
    return payload


def predefined_inductor_cases() -> list[dict[str, Any]]:
    return [deepcopy(three_terminal_inductors_case()), deepcopy(single_power_ground_inductor_case())]
