"""Predefined locked mixed R/C/L acceptance cases."""

from __future__ import annotations

from typing import Any

from .mixed_rcl import BASE_PROJECT, GENERATOR_TARGET, SCHEMA_VERSION


def _node(node_id: str, kind: str = "internal") -> dict[str, str]:
    return {"id": node_id, "kind": kind}


def _group(mode: str, start: str, end: str) -> dict[str, str]:
    return {"mode": mode, "start": start, "end": end}


def _payload(name: str, description: str, groups: list[dict[str, str]], *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    node_ids = list(dict.fromkeys(label for item in groups for label in (item["start"], item["end"])))
    nodes = [_node(node_id, "power" if node_id == "V0" else "ground" if node_id == "G0" else "internal") for node_id in node_ids]
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
        "groups": groups,
        "metadata": {
            "source": "locked mixed R/C/L examples",
            "description": description,
            **(metadata or {}),
        },
    }


def mixed_rcl_6_case() -> dict[str, Any]:
    return _payload(
        "MIXED_RCL_LOCKED_T01_6_COMPONENTS",
        "Six-component mixed R/C/L circuit using one RCL block, one RC block, and one C-only block.",
        [_group("RCL", "V0", "G0"), _group("RC", "V0", "G0"), _group("C", "V0", "G0")],
        metadata={"expected_counts": {"RESISTOR": 2, "CAPACITOR": 3, "INDUCTOR": 1}},
    )


def mixed_rcl_21_case() -> dict[str, Any]:
    groups = [
        _group("RCL", "V0", "D1"),
        _group("RC", "D1", "D2"),
        _group("LC", "D2", "M0"),
        _group("RCL", "V0", "E1"),
        _group("RL", "E1", "E2"),
        _group("RC", "E2", "M0"),
        _group("RCL", "M0", "F1"),
        _group("LC", "F1", "F2"),
        _group("RL", "F2", "G0"),
    ]
    return _payload(
        "MIXED_RCL_LOCKED_T02_21_RULE_TOPOLOGY",
        "Corrected 21-component topology: two seven-component V0-to-M0 series strings feeding one seven-component M0-to-G0 series string.",
        groups,
        metadata={
            "expected_counts": {"RESISTOR": 7, "CAPACITOR": 7, "INDUCTOR": 7},
            "circuit_rule": "Row 1 V0->M0 has 7 components, row 2 V0->M0 has 7 components, row 3 M0->G0 has 7 components.",
            "circuit_rows": [
                {
                    "row": 1,
                    "rule": "seven components in series from V0 to M0",
                    "group_modes": ["RCL", "RC", "LC"],
                    "nodes": ["V0", "D1", "D2", "M0"],
                },
                {
                    "row": 2,
                    "rule": "seven components in series from V0 to M0",
                    "group_modes": ["RCL", "RL", "RC"],
                    "nodes": ["V0", "E1", "E2", "M0"],
                },
                {
                    "row": 3,
                    "rule": "seven components in series from M0 to G0",
                    "group_modes": ["RCL", "LC", "RL"],
                    "nodes": ["M0", "F1", "F2", "G0"],
                },
            ],
        },
    )


def mixed_rcl_15_cases() -> list[dict[str, Any]]:
    cases: list[tuple[str, str, list[dict[str, str]]]] = [
        (
            "MIXED_RCL_LOCKED_T03_01_SIMPLE_LOOP",
            "Simple loop: one RCL path from power to ground.",
            [_group("RCL", "V0", "G0")],
        ),
        (
            "MIXED_RCL_LOCKED_T04_02_SERIES_CIRCUIT",
            "Series circuit: RC section followed by RCL section.",
            [_group("RC", "V0", "N1"), _group("RCL", "N1", "G0")],
        ),
        (
            "MIXED_RCL_LOCKED_T05_03_PARALLEL_CIRCUIT",
            "Parallel circuit: RCL, RC, and LC branches between power and ground.",
            [_group("RCL", "V0", "G0"), _group("RC", "V0", "G0"), _group("LC", "V0", "G0")],
        ),
        (
            "MIXED_RCL_LOCKED_T06_04_SERIES_PARALLEL_COMBO",
            "Series-parallel combo: RC section feeding parallel RCL and LC branches.",
            [_group("RC", "V0", "N1"), _group("RCL", "N1", "G0"), _group("LC", "N1", "G0")],
        ),
        (
            "MIXED_RCL_LOCKED_T07_05_BASIC_VOLTAGE_DIVIDER",
            "Basic divider: RL upper section and RC lower section with midpoint N1.",
            [_group("RL", "V0", "N1"), _group("RC", "N1", "G0")],
        ),
        (
            "MIXED_RCL_LOCKED_T08_06_MULTI_STEP_VOLTAGE_DIVIDER",
            "Multi-step divider: RL, RC, and LC sections creating N1 and N2 taps.",
            [_group("RL", "V0", "N1"), _group("RC", "N1", "N2"), _group("LC", "N2", "G0")],
        ),
        (
            "MIXED_RCL_LOCKED_T09_07_CURRENT_DIVIDER",
            "Current divider: several parallel mixed paths from V0 to G0.",
            [_group("RC", "V0", "G0"), _group("RCL", "V0", "G0"), _group("C", "V0", "G0"), _group("LC", "V0", "G0")],
        ),
        (
            "MIXED_RCL_LOCKED_T10_08_DELTA_NETWORK",
            "Delta network using V0, N1, and G0 as triangle vertices.",
            [_group("RL", "V0", "N1"), _group("RC", "N1", "G0"), _group("LC", "G0", "V0")],
        ),
        (
            "MIXED_RCL_LOCKED_T11_09_STAR_Y_NETWORK",
            "Star network with central node N1 and three mixed outer arms.",
            [_group("RL", "N1", "V0"), _group("RC", "N1", "G0"), _group("LC", "N1", "N2")],
        ),
        (
            "MIXED_RCL_LOCKED_T12_10_DELTA_TO_STAR_SETUP",
            "Delta-to-star setup with mixed delta and star sides for comparison.",
            [
                _group("RL", "V0", "N1"),
                _group("RC", "N1", "G0"),
                _group("LC", "G0", "V0"),
                _group("RL", "N2", "V0"),
                _group("RC", "N2", "G0"),
                _group("LC", "N2", "N1"),
            ],
        ),
        (
            "MIXED_RCL_LOCKED_T13_11_WHEATSTONE_BRIDGE",
            "Wheatstone bridge: two mixed side branches and a bridge between N1 and N2.",
            [_group("RC", "V0", "N1"), _group("LC", "N1", "G0"), _group("RL", "V0", "N2"), _group("RCL", "N2", "G0"), _group("LC", "N1", "N2")],
        ),
        (
            "MIXED_RCL_LOCKED_T14_12_BALANCED_WHEATSTONE_BRIDGE",
            "Balanced Wheatstone bridge with symmetric mixed side branches.",
            [_group("RC", "V0", "N1"), _group("LC", "N1", "G0"), _group("RC", "V0", "N2"), _group("LC", "N2", "G0"), _group("RL", "N1", "N2")],
        ),
        (
            "MIXED_RCL_LOCKED_T15_13_UNBALANCED_WHEATSTONE_BRIDGE",
            "Unbalanced Wheatstone bridge with a heavier lower-right RCL section.",
            [_group("RC", "V0", "N1"), _group("LC", "N1", "G0"), _group("RL", "V0", "N2"), _group("RCL", "N2", "G0"), _group("RC", "N1", "N2")],
        ),
        (
            "MIXED_RCL_LOCKED_T16_14_H_BRIDGE_RESISTOR_VERSION",
            "H-bridge style network with two mixed vertical branches and one cross bridge.",
            [_group("RC", "V0", "N1"), _group("LC", "N1", "G0"), _group("RL", "V0", "N2"), _group("RCL", "N2", "G0"), _group("LC", "N1", "N2")],
        ),
        (
            "MIXED_RCL_LOCKED_T17_15_R_2R_LADDER_NETWORK",
            "R-2R-style ladder topology using repeated mixed series sections and LC shunts.",
            [_group("RL", "V0", "N1"), _group("LC", "N1", "G0"), _group("RC", "N1", "N2"), _group("LC", "N2", "G0"), _group("RL", "N2", "N3"), _group("LC", "N3", "G0"), _group("RC", "N3", "G0")],
        ),
    ]
    return [_payload(name, description, groups) for name, description, groups in cases]


def predefined_mixed_rcl_cases() -> list[dict[str, Any]]:
    return [mixed_rcl_6_case(), mixed_rcl_21_case(), *mixed_rcl_15_cases()]
