from pathlib import Path

import pytest

from Easyeda.value_editor import (
    ValueEditorError,
    apply_value_edits,
    normalize_value,
)


EXAMPLE = Path(__file__).parents[1] / "examples" / "regulated_5v_supply.json"


def test_passive_values_are_normalized_without_changing_the_donor_kind() -> None:
    assert normalize_value("R", "4.7kΩ") == "4.7kohm"
    assert normalize_value("C", "100µF") == "100uF"
    assert normalize_value("PTC_FUSE", "500mA") == "500mA"


def test_zero_or_expression_values_are_rejected() -> None:
    with pytest.raises(ValueEditorError):
        normalize_value("R", "0")
    with pytest.raises(ValueEditorError):
        normalize_value("C", "1k; rm -rf")


def test_reference_edit_updates_expected_net_members() -> None:
    edited, report = apply_value_edits(
        EXAMPLE,
        {"components": {"R1": {"reference": "R10", "value": "2.2k"}}},
    )
    resistor = next(item for item in edited["components"] if item["id"] == "R1")
    assert resistor["ref"] == "R10"
    assert resistor["value"] == "2.2k"
    assert any("R10." in member for net in edited["nets"] for member in net["members"])
    assert report["passed"] is True
