"""Predefined mixed resistor/capacitor acceptance cases."""

from __future__ import annotations

from typing import Any

from .mixed_passive_ir import BASE_PROJECT, GENERATOR_TARGET, SCHEMA_VERSION


def _node(node_id: str, kind: str = "internal") -> dict[str, str]:
    return {"id": node_id, "kind": kind}


def _ref(prefix: str, index: int) -> str:
    if index <= 9:
        return f"{prefix}{index}"
    return f"{prefix}{chr(ord('A') + index - 10)}"


def _component(index: int, left: str, right: str, value: str) -> dict[str, Any]:
    is_resistor = index % 2 == 1
    return {
        "ref": _ref("R" if is_resistor else "C", index),
        "type": "RESISTOR" if is_resistor else "CAPACITOR",
        "value": value if is_resistor else "1uF",
        "nodes": [left, right],
    }


def _payload(name: str, nodes: list[dict[str, str]], components: list[dict[str, Any]], positions: dict[str, dict[str, int]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_target": GENERATOR_TARGET,
        "project": {
            "name": name,
            "output_basename": name,
            "base": BASE_PROJECT,
            "units": "proteus_internal",
        },
        "nodes": nodes,
        "components": components,
        "layout": {
            "mode": "manual_component_positions",
            "coordinate_units": "proteus_internal",
            "component_positions": positions,
        },
        "metadata": {
            "source": "locked mixed passive examples",
            "rule": "odd-indexed components are RESISTOR, even-indexed components are CAPACITOR",
        },
    }


def mixed_6_case() -> dict[str, Any]:
    components = [
        _component(1, "V0", "N1", "1k"),
        _component(2, "N1", "N2", "2k"),
        _component(3, "V0", "N2", "3k"),
        _component(4, "N2", "N3", "4k"),
        _component(5, "N3", "G0", "5k"),
        _component(6, "V0", "G0", "6k"),
    ]
    positions = {
        "R1": {"x": -6350000, "y": 5080000},
        "C2": {"x": -2540000, "y": 4318000},
        "R3": {"x": -6350000, "y": 3556000},
        "C4": {"x": -2540000, "y": 2032000},
        "R5": {"x": -2540000, "y": 508000},
        "C6": {"x": -6350000, "y": -1016000},
    }
    return _payload(
        "MIXED_LOCKED_T01_6_COMPONENTS_ODD_R_EVEN_C",
        [_node("V0", "power"), _node("N1"), _node("N2"), _node("N3"), _node("G0", "ground")],
        components,
        positions,
    )


def mixed_21_case() -> dict[str, Any]:
    node_rows = [
        ["V0", "A1", "A2", "A3", "A4", "A5", "A6", "M0"],
        ["V0", "B1", "B2", "B3", "B4", "B5", "B6", "M0"],
        ["M0", "C1", "C2", "C3", "C4", "C5", "C6", "G0"],
    ]
    components: list[dict[str, Any]] = []
    positions: dict[str, dict[str, int]] = {}
    index = 1
    x0 = -6350000
    y_values = [5080000, 3556000, 2032000]
    values = [f"{value}k" for value in range(1, 22)]
    for row, y in zip(node_rows, y_values):
        for col, (left, right) in enumerate(zip(row, row[1:])):
            component = _component(index, left, right, values[index - 1])
            components.append(component)
            positions[component["ref"]] = {"x": x0 + col * 2540000, "y": y}
            index += 1
    nodes = [
        _node("V0", "power"),
        *[_node(f"A{i}") for i in range(1, 7)],
        _node("M0"),
        *[_node(f"B{i}") for i in range(1, 7)],
        *[_node(f"C{i}") for i in range(1, 7)],
        _node("G0", "ground"),
    ]
    return _payload("MIXED_LOCKED_T02_21_COMPONENTS_ODD_R_EVEN_C", nodes, components, positions)


def predefined_mixed_passive_cases() -> list[dict[str, Any]]:
    return [mixed_6_case(), mixed_21_case()]
