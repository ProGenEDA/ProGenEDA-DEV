from __future__ import annotations

import pytest

from Altium.ir import CircuitInputError, load_circuit


def _resistor() -> dict[str, object]:
    return {
        "id": "R1",
        "ref": "R1",
        "kind": "R",
        "value": "1k",
        "pins": {"1": "VIN", "2": "GND"},
    }


def test_loads_common_canonical_input_without_backend_imports() -> None:
    circuit = load_circuit(
        {
            "project": {"name": "bridge_check", "title": "Bridge Check"},
            "components": [_resistor()],
            "nets": [
                {"name": "VIN", "members": ["R1.1"]},
                {"name": "GND", "members": ["R1.2"]},
            ],
            "expected_netlist": {"VIN": ["R1.1"], "GND": ["R1.2"]},
        }
    )

    assert circuit.name == "bridge_check"
    assert circuit.routing_mode == "combination"
    assert circuit.nets == {"GND": ("R1.2",), "VIN": ("R1.1",)}
    assert circuit.normalized_json()["project"]["target"] == "altium"


def test_rejects_net_that_disagrees_with_component_pin_binding() -> None:
    with pytest.raises(CircuitInputError, match="conflicts"):
        load_circuit(
            {
                "components": [_resistor()],
                "nets": [{"name": "WRONG", "members": ["R1.1"]}],
            }
        )


def test_rejects_noncanonical_routing_mode() -> None:
    with pytest.raises(CircuitInputError, match="Routing mode"):
        load_circuit({"components": [_resistor()], "routing": {"mode": "automatic"}})
