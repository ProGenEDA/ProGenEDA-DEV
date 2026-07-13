"""Focused regressions for readable automatic LTspice schematic placement."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ltspice.pipeline.component_placer import place_components
from ltspice.pipeline.component_selector import select_components
from ltspice.pipeline.ltspice_asc_writer import asy_text
from ltspice.pipeline.native_pin_mapper import translate_circuit_pins
from ltspice.pipeline.progen_ltspice_executable import run_executable


def _rc_circuit() -> dict[str, object]:
    """A minimal physical source--series--shunt topology with a ground flag."""

    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "RC_VISUAL_PLACEMENT",
        "project": {"name": "rc_visual_placement", "analysis": [".tran 1u 5m"]},
        "components": [
            {"ref": "V1", "kind": "VSIN", "value": "SINE(0 1 1k)", "pins": {"1": "IN", "2": "GND"}},
            {"ref": "R1", "kind": "R", "value": "1k", "pins": {"1": "IN", "2": "OUT"}},
            {"ref": "C1", "kind": "C", "value": "1u", "pins": {"1": "OUT", "2": "GND"}},
            {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
        ],
        "nets": {
            "IN": ["V1.1", "R1.1"],
            "OUT": ["R1.2", "C1.1"],
            "GND": ["V1.2", "C1.2", "G1.1"],
        },
    }


class VisualPlacementTests(unittest.TestCase):
    def test_default_rc_layout_is_readable_and_connectivity_safe(self) -> None:
        """Automatic source/R/C placement is an L, with GND on its terminal anchor."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "rc-visual-placement.json"
            source.write_text(json.dumps(_rc_circuit()), encoding="utf-8")

            summary = run_executable(source, output_root=root, label="rc-visual-placement")

            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            self.assertTrue(result["final_validation"]["ok"], result["final_validation"])
            run_dir = Path(summary["run_dir"])
            internal = run_dir / result["generation_dir"] / "internal"
            placement = json.loads((internal / "placement.json").read_text(encoding="utf-8"))
            wire_plan = json.loads((internal / "wire-plan.json").read_text(encoding="utf-8"))
            asc = (run_dir / result["asc_path"]).read_text(encoding="ascii")

        by_ref = {item["ref"]: item for item in placement["placed_components"]}
        self.assertEqual(
            {ref: item["origin"] for ref, item in by_ref.items()},
            {
                "V1": {"x": 192, "y": 160},
                "R1": {"x": 480, "y": 160},
                "C1": {"x": 480, "y": 384},
                "G1": {"x": 192, "y": 288},
            },
        )
        self.assertEqual({by_ref[ref]["orientation"] for ref in ("V1", "R1", "C1")}, {"R0"})
        self.assertIn("SYMBOL progeneda_voltage 192 160 R0", asc)
        self.assertIn("SYMBOL progeneda_res 480 160 R0", asc)
        self.assertIn("SYMBOL progeneda_cap 480 384 R0", asc)
        self.assertEqual(asc.count("FLAG 192 288 0"), 1)
        self.assertEqual(wire_plan["rejected_wire_routes"], [])
        direct_segments = {
            (segment["start"]["x"], segment["start"]["y"], segment["end"]["x"], segment["end"]["y"])
            for segment in wire_plan["wire_segments"]
        }
        self.assertIn((192, 160, 480, 160), direct_segments)
        self.assertIn((480, 256, 480, 384), direct_segments)

    def test_explicit_ltspice_orientation_remains_authoritative(self) -> None:
        circuit = _rc_circuit()
        components = circuit["components"]
        assert isinstance(components, list)
        components[1]["ltspice_orientation"] = "M90"

        selected, _selection = select_components(circuit)
        native, _translation = translate_circuit_pins(circuit, selected)
        placed, _report = place_components(native, selected)

        by_ref = {item.component.ref: item for item in placed}
        self.assertEqual(by_ref["R1"].orientation, "M90")
        self.assertEqual(by_ref["V1"].orientation, "R0")

    def test_native_symbols_keep_electrical_pin_attributes_without_drawn_pin_labels(self) -> None:
        profile = select_components(_rc_circuit())[0][1].profile
        text = asy_text(profile)

        self.assertIn("PIN 0 0 NONE 0", text)
        self.assertIn("PINATTR PinName A", text)
        self.assertIn("PINATTR SpiceOrder 1", text)
        self.assertNotIn("PIN 0 0 Top 8", text)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
