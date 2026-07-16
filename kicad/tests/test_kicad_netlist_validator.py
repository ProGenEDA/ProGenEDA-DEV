from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kicad.pipeline.beautifier import apply_coordinate_edits
from kicad.pipeline.kicad_netlist_validator import validate_schematic_netlist
from kicad.pipeline.value_editor import apply_value_edits
from kicad.pipeline.value_validator import validate_component_values


MINIMAL_RESISTOR_SCHEMATIC = """(kicad_sch
  (version 20250114)
  (generator "progen-test")
  (paper "A4")
  (lib_symbols
    (symbol "Device:R"
      (symbol "R_1_1"
        (pin passive line (at -2.54 0 0) (length 2.54)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))
        )
        (pin passive line (at 2.54 0 180) (length 2.54)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))
        )
      )
    )
  )
  (wire (pts (xy 12.54 10) (xy 17.46 10)) (stroke (width 0) (type default)) (uuid "11111111-1111-1111-1111-111111111111"))
  (symbol (lib_id "Device:R") (at 10 10 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid "22222222-2222-2222-2222-222222222222")
    (property "Reference" "R1" (at 10 8 0) (effects (font (size 1.27 1.27))))
    (property "Value" "1k" (at 10 12 0) (effects (font (size 1.27 1.27))))
    (property "Progen.Kind" "RES" (at 10 10 0) (effects (font (size 1.27 1.27)) hide))
    (pin "1" (uuid "33333333-3333-3333-3333-333333333331"))
    (pin "2" (uuid "33333333-3333-3333-3333-333333333332"))
  )
  (symbol (lib_id "Device:R") (at 20 10 0) (unit 1)
    (in_bom yes) (on_board yes) (dnp no)
    (uuid "44444444-4444-4444-4444-444444444444")
    (property "Reference" "R2" (at 20 8 0) (effects (font (size 1.27 1.27))))
    (property "Value" "1k" (at 20 12 0) (effects (font (size 1.27 1.27))))
    (property "Progen.Kind" "RES" (at 20 10 0) (effects (font (size 1.27 1.27)) hide))
    (pin "1" (uuid "55555555-5555-5555-5555-555555555551"))
    (pin "2" (uuid "55555555-5555-5555-5555-555555555552"))
  )
)"""


def resistor_circuit(members: list[str]) -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": "validator_resistor_pair"},
        "components": [
            {"id": "R1", "kind": "RES", "value": "1k", "pins": {"1": "LEFT", "2": "JOINED"}},
            {"id": "R2", "kind": "RES", "value": "1k", "pins": {"1": "JOINED", "2": "RIGHT"}},
        ],
        "nets": {"JOINED": members},
    }


class KiCadNetlistValidatorTests(unittest.TestCase):
    def test_beautifier_rotates_components_obstacles_and_pin_points(self) -> None:
        placement = {
            "components": {"U1": {"kind": "TEST", "at": [10.0, 10.0], "rotation": 0.0}},
            "obstacles": [{"owner": "U1", "left": 8.0, "top": 9.0, "right": 12.0, "bottom": 11.0}],
            "pin_points": {"U1": {"OUT": {"point": [12.0, 10.0], "side": "right"}}},
        }
        plan = {"coordinate_edits": [{"ref": "U1", "to": [20.0, 20.0], "rotation": 90.0}]}

        updated = apply_coordinate_edits(placement, plan)

        self.assertEqual(updated["components"]["U1"]["at"], [20.0, 20.0])
        self.assertEqual(updated["components"]["U1"]["rotation"], 90.0)
        self.assertEqual(updated["pin_points"]["U1"]["OUT"]["point"], [20.0, 22.0])
        self.assertEqual(updated["pin_points"]["U1"]["OUT"]["side"], "bottom")
        self.assertEqual(updated["obstacles"][0], {"owner": "U1", "left": 19.0, "top": 18.0, "right": 21.0, "bottom": 22.0})

    def test_local_netlist_comparison_passes_connected_expected_net(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "pair.kicad_sch"
            schematic.write_text(MINIMAL_RESISTOR_SCHEMATIC, encoding="utf-8")

            report = validate_schematic_netlist(schematic, resistor_circuit(["R1.2", "R2.1"]))

        self.assertTrue(report["ok"], report["blocking_failures"])
        self.assertFalse(report["kicad_cli_required"])
        self.assertEqual(report["checks"]["expected_net_comparison"]["passed_net_count"], 1)

    def test_value_editor_repairs_and_validator_confirms_values(self) -> None:
        circuit = resistor_circuit(["R1.2", "R2.1"])
        circuit["components"][0]["value"] = "4.7k"
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "pair.kicad_sch"
            schematic.write_text(MINIMAL_RESISTOR_SCHEMATIC, encoding="utf-8")

            edit_report = apply_value_edits(circuit=circuit, schematic_path=schematic)
            validation_report = validate_component_values(circuit=circuit, schematic_path=schematic)

        self.assertTrue(edit_report["ok"])
        self.assertTrue(edit_report["changed"])
        self.assertEqual(edit_report["edited_component_count"], 1)
        self.assertTrue(validation_report["ok"], validation_report["value_mismatches"])

    def test_local_netlist_comparison_fails_missing_expected_member(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "pair.kicad_sch"
            schematic.write_text(MINIMAL_RESISTOR_SCHEMATIC, encoding="utf-8")

            report = validate_schematic_netlist(schematic, resistor_circuit(["R1.2", "R2.2"]))

        self.assertFalse(report["ok"])
        failure_types = {item["type"] for item in report["blocking_failures"]}
        self.assertIn("expected_net_mismatch", failure_types)

    def test_local_netlist_comparison_fails_physical_pin_assigned_to_two_nets(self) -> None:
        circuit = resistor_circuit(["R1.2", "R2.1"])
        circuit["nets"] = {"JOINED": ["R1.2", "R2.1"], "BAD_ALIAS": ["R1.2", "R2.2"]}
        with tempfile.TemporaryDirectory() as temp_dir:
            schematic = Path(temp_dir) / "pair.kicad_sch"
            schematic.write_text(MINIMAL_RESISTOR_SCHEMATIC, encoding="utf-8")

            report = validate_schematic_netlist(schematic, circuit)

        self.assertFalse(report["ok"])
        failure_types = {item["type"] for item in report["blocking_failures"]}
        self.assertIn("physical_pin_net_conflict", failure_types)
        self.assertEqual(report["checks"]["physical_pin_assignment"]["conflict_count"], 1)


if __name__ == "__main__":
    unittest.main()
