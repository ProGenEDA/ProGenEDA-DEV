from __future__ import annotations

from proteusgen.component_catalog import load_component_catalog
from proteusgen.node_name_mapping import build_node_name_mapping, terminal_label_for_node
from proteusgen.pin_terminal_planner import build_pin_terminal_plan
from proteusgen.validation import COMPONENT_PINS, HC08_INPUT_PINS, HC08_OUTPUT_PINS


def test_catalog_covers_all_v12_two_pin_terminal_families() -> None:
    catalog = load_component_catalog()
    families = [
        "RESISTOR",
        "CAP",
        "DIODE",
        "VSINE",
        "VSOURCE",
        "CSOURCE",
        "VPULSE",
        "LED-RED",
        "1N4733A",
        "40EPS08",
        "BZY88C",
        "1N4007",
        "1N4148",
        "1N6000B",
        "BZX55C5V1",
        "BZX79C5V1",
        "FUSE",
        "REALIND",
        "CAP-ELEC",
    ]

    for family in families:
        profile = catalog.profile(family)
        assert profile.terminal_support == "accepted_two_pin_v12"
        assert len(profile.pin_names(include_hidden=True)) == 2


def test_catalog_normalizes_component_and_pin_aliases() -> None:
    catalog = load_component_catalog()

    assert catalog.normalize_part("LED") == "LED-RED"
    assert catalog.normalize_part("74HC90") == "7490"
    assert catalog.profile("74HC08").normalize_pin("1A").name == "1"
    assert catalog.profile("74HC08").normalize_pin("Pin 14").hidden
    assert catalog.profile("74HC08").normalize_pin("+5V").role == "VCC"
    assert catalog.profile("VSOURCE").normalize_pin("-").name == "2"
    try:
        catalog.profile("VSOURCE").normalize_pin("")
    except ValueError:
        pass
    else:
        raise AssertionError("empty pin token must not normalize to the negative pin")


def test_catalog_includes_more_than_two_pin_components() -> None:
    catalog = load_component_catalog()

    assert len(catalog.profile("74HC283").pin_names(include_hidden=True)) == 16
    assert len(catalog.profile("NE555").pin_names(include_hidden=True)) == 8
    assert len(catalog.profile("LM741").pin_names(include_hidden=True)) == 8
    assert set(catalog.profile("NPN").pin_names(include_hidden=True)) == {"B", "C", "E"}
    assert catalog.profile("NPN").normalize_pin("BASE").name == "B"
    assert catalog.profile("NMOSFET").normalize_pin("DRAIN").name == "D"
    assert catalog.profile("LM317T").normalize_pin("ADJ").name == "1"
    assert catalog.profile("POT-HG").normalize_pin("WIPER").name == "2"


def test_catalog_has_no_empty_alias_tokens() -> None:
    catalog = load_component_catalog()

    for profile in catalog.components.values():
        assert "" not in profile.pin_aliases


def test_validation_pin_vocabulary_comes_from_catalogue() -> None:
    assert COMPONENT_PINS["RESISTOR"] == {"1", "2"}
    assert COMPONENT_PINS["74HC08"] == {
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
    }
    assert HC08_INPUT_PINS == {"1", "2", "4", "5", "9", "10", "12", "13"}
    assert HC08_OUTPUT_PINS == {"3", "6", "8", "11"}


def test_node_name_mapping_groups_two_pin_and_ic_endpoints() -> None:
    payload = {
        "version": "0.2",
        "target": {
            "proteus_version": "8.13",
            "style": "terminal_based",
            "sheet_count": 1,
            "mode": "diagnostic_control",
        },
        "circuit": {
            "name": "node_mapping_probe",
            "components": [
                {"ref": "R1", "part": "RESISTOR", "value": "10k"},
                {"ref": "U1", "part": "74HC08"},
                {"ref": "D1", "part": "LED"},
            ],
            "nets": [
                {"name": "VIN", "kind": "internal"},
                {"name": "OUT", "kind": "output"},
                {"name": "VCC", "kind": "power"},
                {"name": "GND", "kind": "ground"},
                {"name": "very long node name with spaces", "kind": "internal"},
            ],
            "connections": [
                {"component": "R1", "pin": "1", "net": "VIN"},
                {"component": "U1", "pin": "1A", "net": "VIN"},
                {"component": "U1", "pin": "1Y", "net": "OUT"},
                {"component": "U1", "pin": "Pin 14", "net": "VCC"},
                {"component": "U1", "pin": "GND", "net": "GND"},
                {"component": "D1", "pin": "ANODE", "net": "very long node name with spaces"},
            ],
        },
    }

    mapping = build_node_name_mapping(payload)

    assert mapping["valid"]
    assert mapping["node_count"] == 5
    assert mapping["terminal_labels"]["VCC"] == "V0"
    assert mapping["terminal_labels"]["GND"] == "G0"
    assert mapping["terminal_labels"]["very long node name with spaces"].startswith("N")
    assert mapping["endpoint_to_node"]["U1.1"] == "VIN"
    assert mapping["endpoint_to_node"]["U1.3"] == "OUT"
    assert mapping["endpoint_to_node"]["D1.1"] == "very long node name with spaces"
    assert mapping["hidden_endpoint_count"] == 2


def test_lightweight_node_name_mapping_handles_multi_pin_aliases() -> None:
    mapping = build_node_name_mapping(
        {
            "components": [{"ref": "U1", "part": "74HC90"}],
            "nets": {"CLK": "input"},
            "connections": [
                {
                    "net": "CLK",
                    "endpoints": [{"component": "U1", "pin": "Pin 1"}],
                }
            ],
        }
    )

    assert mapping["valid"]
    assert mapping["nodes"][0]["endpoints"][0]["part"] == "7490"
    assert mapping["nodes"][0]["endpoints"][0]["pin"] == "1"


def test_node_name_mapping_infers_refs_from_component_count_payload() -> None:
    mapping = build_node_name_mapping(
        {
            "components": {
                "RESISTOR": {"count": 1, "value": "4k7"},
                "CAP": 1,
            },
            "connections": [
                {
                    "net": "N_FILTER",
                    "from": {"component": "R1", "pin": "2"},
                    "to": {"component": "C1", "pin": "1"},
                }
            ],
        }
    )

    assert mapping["valid"]
    assert mapping["endpoint_to_node"] == {"R1.2": "N_FILTER", "C1.1": "N_FILTER"}
    assert mapping["nodes"][0]["endpoint_count"] == 2


def test_terminal_label_for_node_is_deterministic_and_collision_safe() -> None:
    used: set[str] = set()

    assert terminal_label_for_node("VCC", kind="power", index=0, used=used) == "V0"
    assert terminal_label_for_node("GND", kind="ground", index=1, used=used) == "G0"
    assert terminal_label_for_node("VIN", index=2, used=used) == "VIN"
    assert terminal_label_for_node("VIN", index=3, used=used) == "N003"


def test_pin_terminal_plan_separates_two_pin_three_pin_and_ic_work() -> None:
    plan = build_pin_terminal_plan(
        {
            "components": [
                {"ref": "R1", "part": "RESISTOR"},
                {"ref": "Q1", "part": "NPN"},
                {"ref": "U1", "part": "74HC08"},
            ],
            "nets": {
                "N1": "internal",
                "BASE": "input",
                "COL": "internal",
                "EMIT": "ground",
                "A": "input",
                "Y": "output",
            },
            "connections": [
                {"net": "N1", "endpoints": [{"component": "R1", "pin": "1"}]},
                {"net": "BASE", "endpoints": [{"component": "Q1", "pin": "BASE"}]},
                {"net": "COL", "endpoints": [{"component": "Q1", "pin": "COLLECTOR"}]},
                {"net": "EMIT", "endpoints": [{"component": "Q1", "pin": "EMITTER"}]},
                {"net": "A", "endpoints": [{"component": "U1", "pin": "1A"}]},
                {"net": "Y", "endpoints": [{"component": "U1", "pin": "1Y"}]},
            ],
        }
    )

    assert plan["valid"]
    assert plan["pin_class_counts"] == {"multi_pin": 2, "three_pin": 3, "two_pin": 1}
    assert plan["terminal_emit_ready_count"] == 1
    assert plan["blocked_terminal_count"] == 5
    by_endpoint = {
        (row["component"], row["pin"]): row
        for row in plan["terminal_plans"]
    }
    assert by_endpoint[("Q1", "B")]["pin_class"] == "three_pin"
    assert by_endpoint[("U1", "1")]["pin_class"] == "multi_pin"
    assert by_endpoint[("R1", "1")]["terminal_emit_ready"]
