"""Predefined resistor-power-ground generator acceptance cases."""

from __future__ import annotations

from typing import Any

REFS = (
    "R1",
    "R2",
    "R3",
    "R4",
    "R5",
    "R6",
    "R7",
    "R8",
    "R9",
    "RA",
    "RB",
    "RC",
    "RD",
    "RE",
    "RF",
    "RG",
    "RH",
    "RI",
    "RJ",
    "RK",
)


CASE_EDGES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    ("pg01_single", (("V0", "G0"),)),
    ("pg02_series2", (("V0", "N1"), ("N1", "G0"))),
    ("pg03_series3", (("V0", "N1"), ("N1", "N2"), ("N2", "G0"))),
    ("pg04_parallel2", (("V0", "G0"), ("V0", "G0"))),
    ("pg05_bridge", (("V0", "A1"), ("V0", "B1"), ("A1", "G0"), ("B1", "G0"), ("A1", "B1"))),
    (
        "pg06_ladder",
        (("V0", "A1"), ("A1", "A2"), ("A2", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "G0"), ("A1", "B1"), ("A2", "B2")),
    ),
    (
        "pg07_star",
        (("V0", "N1"), ("N1", "A1"), ("N1", "A2"), ("N1", "A3"), ("A1", "G0"), ("A2", "G0"), ("A3", "G0")),
    ),
    ("pg08_delta_tail", (("V0", "A1"), ("V0", "B1"), ("A1", "B1"), ("A1", "C1"), ("B1", "C1"), ("C1", "G0"))),
    ("pg09_wheatstone", (("V0", "A1"), ("A1", "G0"), ("V0", "B1"), ("B1", "G0"), ("A1", "B1"))),
    (
        "pg10_double_ladder",
        (("V0", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "B3"), ("B3", "G0"), ("A1", "B1"), ("A2", "B2")),
    ),
    (
        "pg11_t_network",
        (("V0", "N1"), ("N1", "N2"), ("N2", "G0"), ("N1", "A1"), ("A1", "G0"), ("N2", "B1"), ("B1", "G0")),
    ),
    (
        "pg12_pi_network",
        (("V0", "N1"), ("N1", "G0"), ("V0", "N2"), ("N2", "G0"), ("N1", "N2"), ("V0", "A1"), ("A1", "N1")),
    ),
    (
        "pg13_three_branch",
        (("V0", "A1"), ("A1", "A2"), ("A2", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "G0"), ("V0", "C1"), ("C1", "C2"), ("C2", "G0")),
    ),
    (
        "pg14_cross_mesh",
        (("V0", "A1"), ("A1", "A2"), ("A2", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "G0"), ("A1", "B2"), ("B1", "A2")),
    ),
    (
        "pg15_ring_chord",
        (("V0", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "A4"), ("A4", "G0"), ("V0", "B1"), ("B1", "A2"), ("A3", "B2"), ("B2", "G0")),
    ),
    (
        "pg16_dense_10r",
        (("V0", "A1"), ("V0", "B1"), ("A1", "A2"), ("B1", "B2"), ("A2", "G0"), ("B2", "G0"), ("A1", "B1"), ("A2", "B2"), ("A1", "B2"), ("B1", "A2")),
    ),
    (
        "pg17_cascade_bridge",
        (("V0", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "B3"), ("B3", "G0"), ("A1", "B2"), ("B1", "A2"), ("A3", "B3")),
    ),
    (
        "pg18_four_rail",
        (("V0", "A1"), ("A1", "A2"), ("A2", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "G0"), ("V0", "C1"), ("C1", "C2"), ("C2", "G0"), ("A1", "B1"), ("B1", "C1"), ("A2", "B2")),
    ),
    (
        "pg19_mixed_15r",
        (("V0", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "B3"), ("B3", "G0"), ("V0", "C1"), ("C1", "C2"), ("C2", "G0"), ("A1", "B1"), ("A2", "B2"), ("B2", "C2"), ("A3", "B3")),
    ),
    (
        "pg20_twenty_resistor_mesh",
        (("V0", "A1"), ("A1", "A2"), ("A2", "A3"), ("A3", "G0"), ("V0", "B1"), ("B1", "B2"), ("B2", "B3"), ("B3", "G0"), ("V0", "C1"), ("C1", "C2"), ("C2", "C3"), ("C3", "G0"), ("V0", "D1"), ("D1", "D2"), ("D2", "D3"), ("D3", "G0"), ("A1", "B2"), ("B1", "C2"), ("C1", "D2"), ("A3", "D3")),
    ),
)


def predefined_resistor_cases() -> list[dict[str, Any]]:
    return [_build_case(slug, edges) for slug, edges in CASE_EDGES]


def _build_case(slug: str, edges: tuple[tuple[str, str], ...]) -> dict[str, Any]:
    node_ids = _ordered_nodes(edges)
    components = []
    positions: dict[str, dict[str, int]] = {}
    for index, (left, right) in enumerate(edges):
        ref = REFS[index]
        components.append({"ref": ref, "type": "RESISTOR", "value": f"{index + 1}k", "nodes": [left, right]})
        positions[ref] = {"x": -6350000 + (index % 7) * 2540000, "y": 5080000 - (index // 7) * 1524000}
    return {
        "schema_version": "proteus-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-v9-resistor-terminal",
        "project": {
            "name": slug.upper(),
            "output_basename": slug.upper(),
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "nodes": [_node(node_id) for node_id in node_ids],
        "components": components,
        "layout": {
            "mode": "manual_component_positions",
            "coordinate_units": "proteus_internal",
            "component_positions": positions,
        },
        "metadata": {
            "source": "proteusgen predefined resistor acceptance case",
            "case_slug": slug,
            "notes": ["Uses V0/G0 two-character labels with the locked power-bridge and ground-endpoint method."],
        },
    }


def _ordered_nodes(edges: tuple[tuple[str, str], ...]) -> list[str]:
    out: list[str] = []
    for left, right in edges:
        for node_id in (left, right):
            if node_id not in out:
                out.append(node_id)
    return out


def _node(node_id: str) -> dict[str, str]:
    if node_id == "V0":
        return {"id": node_id, "kind": "power"}
    if node_id == "G0":
        return {"id": node_id, "kind": "ground"}
    return {"id": node_id, "kind": "internal"}
