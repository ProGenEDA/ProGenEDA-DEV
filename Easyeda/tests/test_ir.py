import pytest

from Easyeda.ir import CircuitInputError, load_circuit, resolve_pin


def _resistor(index: int) -> dict[str, object]:
    return {
        "id": f"R{index}",
        "ref": f"R{index}",
        "kind": "R",
        "value": "1k",
        "pins": {"1": f"N{index}", "2": "GND"},
    }


def test_input_cap_is_80() -> None:
    circuit = load_circuit({"project": {"name": "cap"}, "components": [_resistor(i) for i in range(1, 81)]})
    assert len(circuit.components) == 80
    with pytest.raises(CircuitInputError, match="at most 80"):
        load_circuit({"project": {"name": "too_many"}, "components": [_resistor(i) for i in range(1, 82)]})


def test_conflicting_top_level_net_is_rejected() -> None:
    raw = {
        "components": [_resistor(1)],
        "nets": [{"name": "WRONG", "members": ["R1.1"]}],
    }
    with pytest.raises(CircuitInputError, match="conflicts"):
        load_circuit(raw)


def test_combination_is_default() -> None:
    circuit = load_circuit({"components": [_resistor(1)]})
    assert circuit.routing_mode == "combination"
