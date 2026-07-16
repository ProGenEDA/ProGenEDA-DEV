from pathlib import Path

from Easyeda.donor_source import EasyedaDonorSource, bundled_source_pack
from Easyeda.input_fixer import repair_circuit_input


def test_fixer_repairs_shape_and_accounts_for_every_unique_donor_pin() -> None:
    source = EasyedaDonorSource(bundled_source_pack())
    result = repair_circuit_input(
        {
            "name": "rough input",
            "routing_mode": "unexpected",
            "parts": {
                "U1": {
                    "type": "LM358",
                    "connections": [{"pin": "OUT1", "node": "SIGNAL_OUT"}],
                },
                "R1": "resistor",
            },
        },
        source,
    )
    assert result.report["passed"] is True
    assert result.fixed["routing"]["mode"] == "combination"
    assert result.report["guessed_net_count"] == 9
    coverage = {
        item["reference"]: item
        for item in result.report["pin_coverage"]
    }
    assert coverage["U1"]["unique_electrical_pin_count"] == 8
    assert coverage["U1"]["missing_after_fix"] == []
    assert coverage["R1"]["unique_electrical_pin_count"] == 2
    assert all(
        guessed["net"].startswith("GUESS_")
        and guessed["routing"] == "terminal"
        for guessed in result.report["guessed_nets"]
    )


def test_usb_duplicate_shield_drawing_pins_count_as_one_electrical_pin() -> None:
    source = EasyedaDonorSource(bundled_source_pack())
    result = repair_circuit_input(
        {
            "components": [
                {
                    "ref": "J1",
                    "kind": "USB_C_RECEPTACLE",
                    "pins": {},
                }
            ]
        },
        source,
    )
    coverage = result.report["pin_coverage"][0]
    assert coverage["raw_symbol_pin_count"] == 20
    assert coverage["unique_electrical_pin_count"] == 17
    assert coverage["complete"] is True


def test_fixer_repairs_comments_and_trailing_commas(tmp_path: Path) -> None:
    path = tmp_path / "rough.json"
    path.write_text(
        """
        {
          // ordinary user note
          "components": [
            {"ref": "R1", "kind": "R", "pins": {"1": "A", "2": "B",},},
          ],
        }
        """,
        encoding="utf-8",
    )
    result = repair_circuit_input(
        path,
        EasyedaDonorSource(bundled_source_pack()),
    )
    assert result.report["passed"] is True
    assert result.report["guessed_net_count"] == 0
    assert any(
        change["code"] == "REPAIRED_JSON_SYNTAX"
        for change in result.report["changes"]
    )
