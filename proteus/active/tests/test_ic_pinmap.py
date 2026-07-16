import pytest

from proteusgen.ic_pinmap import normalize_74hc08_connection, normalize_74hc08_pin
from proteusgen.templates import repository_root
from proteusgen.circuit_ir import load_json


def test_74hc08_supply_pins_are_hidden_and_not_circuit_connections() -> None:
    assert normalize_74hc08_pin("Pin 14").is_hidden_supply
    assert normalize_74hc08_pin("VCC").role == "VCC"
    assert normalize_74hc08_pin("+5V").physical_pin == "14"
    assert normalize_74hc08_connection("U1", "14", "VCC") is None

    assert normalize_74hc08_pin("Pin 7").is_hidden_supply
    assert normalize_74hc08_pin("GND").role == "GND"
    assert normalize_74hc08_pin("0V").physical_pin == "7"
    assert normalize_74hc08_connection("U1", "7", "GND") is None


def test_74hc08_gate1_dip_pins_map_to_proteus_subpart_a() -> None:
    assert normalize_74hc08_pin("1A").proteus_ref == "U1:A"
    assert normalize_74hc08_pin("1B").role == "IN2"
    assert normalize_74hc08_pin("1Y").role == "OUT"
    assert normalize_74hc08_connection("U1", "Pin 1", "A_IN") == {"component": "U1", "pin": "1", "net": "A_IN"}
    assert normalize_74hc08_connection("U1", "Pin 2", "B_IN") == {"component": "U1", "pin": "2", "net": "B_IN"}
    assert normalize_74hc08_connection("U1", "Pin 3", "Y_OUT") == {"component": "U1", "pin": "3", "net": "Y_OUT"}


def test_74hc08_gate2_gate3_gate4_physical_pin_order() -> None:
    assert normalize_74hc08_pin("2A").proteus_ref == "U1:B"
    assert normalize_74hc08_pin("2B").circuit_ir_pin == "5"
    assert normalize_74hc08_pin("2Y").circuit_ir_pin == "6"

    assert normalize_74hc08_pin("3Y").proteus_ref == "U1:C"
    assert normalize_74hc08_pin("3A").circuit_ir_pin == "9"
    assert normalize_74hc08_pin("3B").circuit_ir_pin == "10"

    assert normalize_74hc08_pin("4Y").proteus_ref == "U1:D"
    assert normalize_74hc08_pin("4A").circuit_ir_pin == "12"
    assert normalize_74hc08_pin("4B").circuit_ir_pin == "13"


def test_user_example_rc_delay_gate1_normalizes_to_pin2_node() -> None:
    # User description: R1 leg 2 and C1 positive both meet pin 2 / 1B.
    assert normalize_74hc08_connection("U1", "1B", "B_DELAY") == {"component": "U1", "pin": "2", "net": "B_DELAY"}


def test_user_example_lc_filtered_output_gate2_normalizes_pin6_output() -> None:
    # User description: inductor L1 leg 1 connects directly to pin 6 / 2Y.
    assert normalize_74hc08_connection("U1", "2Y", "GATE2_Y") == {"component": "U1", "pin": "6", "net": "GATE2_Y"}


def test_user_example_rlc_noise_filter_gate3_normalizes_pin10_input_and_pin8_output() -> None:
    assert normalize_74hc08_connection("U1", "3B", "FILTERED_B") == {
        "component": "U1",
        "pin": "10",
        "net": "FILTERED_B",
    }
    assert normalize_74hc08_connection("U1", "3Y", "CLEAN_Y") == {"component": "U1", "pin": "8", "net": "CLEAN_Y"}


def test_user_example_dual_rc_gate4_normalizes_both_inputs_and_output() -> None:
    assert normalize_74hc08_connection("U1", "4A", "FAST_RC") == {"component": "U1", "pin": "12", "net": "FAST_RC"}
    assert normalize_74hc08_connection("U1", "4B", "SLOW_RC") == {"component": "U1", "pin": "13", "net": "SLOW_RC"}
    assert normalize_74hc08_connection("U1", "4Y", "WINDOW_Y") == {"component": "U1", "pin": "11", "net": "WINDOW_Y"}


def test_unknown_74hc08_pin_token_fails_closed() -> None:
    with pytest.raises(ValueError, match="Unsupported 74HC08 pin token"):
        normalize_74hc08_pin("pin 15")


def test_74hc08_registry_user_input_policy_matches_code_pinmap() -> None:
    registry = load_json(repository_root() / "evidence" / "registry" / "74hc08.json")
    assert registry["dip_user_input_policy"]["ignore_supply_pins"] == ["7", "14"]
    for pin, expected in registry["dip_user_input_policy"]["pin_to_subpart"].items():
        mapping = normalize_74hc08_pin(pin)
        assert mapping.subpart == expected["proteus_subpart"]
        assert mapping.role == expected["role"]
        assert normalize_74hc08_pin(expected["alias"]).physical_pin == pin
