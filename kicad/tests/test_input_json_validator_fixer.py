from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kicad.pipeline.progen_kicad_executable import build_variation_source
from kicad.pipeline.input_json_validator_fixer import validate_and_fix_main_json
from kicad.pipeline.kicad_symbol_library import KiCadSymbolLibrary
from kicad.pipeline.kicad_wire_maker import _pin_geometries, _resolve_pin_geometry
from kicad.pipeline.placement_catalog import resolve_placement_spec
from kicad.pipeline.wire_planner import plan_wire_routes


class InputJsonValidatorFixerTests(unittest.TestCase):
    def test_fixer_adds_catalogue_based_guessed_terminal_rails(self) -> None:
        loose = {
            "circuit_id": "LOOSE001",
            "project": {"name": "loose sensor"},
            "components": [
                {"ref": "U1", "kind": "ESP32_WROOM"},
                {"ref": "U2", "kind": "BME280"},
            ],
            "nets": {"I2C_SDA": ["U1.GPIO21", "U2.SDA"]},
        }

        fixed, report = validate_and_fix_main_json(loose)

        self.assertTrue(report["ok"], report["validation"]["errors"])
        guessed = set(report["guessed_terminal_nets"])
        self.assertIn("GUESS_TERMINAL_GND", guessed)
        self.assertIn("GUESS_TERMINAL_3V3", guessed)
        self.assertIn("GUESS_TERMINAL_GND", fixed["nets"])
        self.assertIn("GUESS_TERMINAL_3V3", fixed["nets"])
        terminal_nets = set(fixed["routing"]["terminal_policy"]["terminal_nets"])
        self.assertGreaterEqual(guessed, guessed & terminal_nets)
        self.assertTrue(all(net.startswith("GUESS_TERMINAL_") for net in guessed))

    def test_generation_variation_metadata_survives_fixer(self) -> None:
        loose = {
            "circuit_id": "NVAR001",
            "components": [
                {"ref": "R1", "kind": "RES", "value": "1k"},
                {"ref": "R2", "kind": "RES", "value": "2k"},
            ],
            "nets": {"SIG": ["R1.1", "R2.1"]},
            "generation_variation": {
                "enabled": True,
                "profile": "wide_bus",
                "variation_index": 2,
                "disable_adaptive_cap": True,
            },
        }

        fixed, report = validate_and_fix_main_json(loose)

        self.assertTrue(report["ok"], report["validation"]["errors"])
        self.assertEqual(fixed["generation_variation"]["profile"], "wide_bus")
        self.assertEqual(fixed["generation_variation"]["variation_index"], 2)

    def test_variation_source_defaults_to_new_500_style_n_files(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            source = root / "source"
            output_root = root / "out"
            source.mkdir()
            base = {
                "schema_version": "progen-kicad-circuit-ir/v1",
                "circuit_id": "N001",
                "circuit_name": "New corpus circuit",
                "routing": {"mode": "combination", "terminal_policy": {}},
                "components": [
                    {"id": "R1", "ref": "R1", "kind": "RES", "value": "1k", "pins": {"1": "SIG"}},
                    {"id": "R2", "ref": "R2", "kind": "RES", "value": "2k", "pins": {"1": "SIG"}},
                ],
                "nets": {"SIG": ["R1.1", "R2.1"]},
            }
            old = dict(base)
            old["circuit_id"] = "MJ001"
            (source / "N001_new.json").write_text(json.dumps(base), encoding="utf-8")
            (source / "MJ001_old.json").write_text(json.dumps(old), encoding="utf-8")

            summary = build_variation_source(
                source,
                output_root=output_root,
                label="unit_variations",
                sample_count=10,
                variations_per_circuit=2,
                seed=7,
                routing_mode="combination",
                new_500_only=True,
            )

            self.assertTrue(summary["all_valid"])
            self.assertEqual(summary["selected_circuit_count"], 1)
            self.assertEqual(summary["variation_count"], 2)
            self.assertTrue(all(item["source_circuit_id"] == "N001" for item in summary["results"]))

    def test_fixer_merges_named_rails_into_guessed_terminal_rails(self) -> None:
        loose = {
            "circuit_id": "LOOSE002",
            "components": [
                {"ref": "U1", "kind": "ESP32_WROOM"},
                {"ref": "U2", "kind": "BME280"},
                {"ref": "U3", "kind": "MAX485"},
                {"ref": "U4", "kind": "MCP2515"},
                {"ref": "K1", "kind": "RELAY"},
                {"ref": "J1", "kind": "TERMINAL_BLOCK"},
            ],
            "nets": {
                "NET_SENSOR_GND": ["U3.GND", "U4.GND"],
                "NET_RELAY_COM": ["K1.COM", "J1.PLUS"],
                "SENSOR_SDA": ["U1.GPIO21", "U2.SDA"],
            },
        }

        fixed, report = validate_and_fix_main_json(loose)

        self.assertTrue(report["ok"], report["validation"]["errors"])
        self.assertNotIn("NET_SENSOR_GND", fixed["nets"])
        self.assertIn("NET_RELAY_COM", fixed["nets"])
        self.assertIn("GUESS_TERMINAL_GND", fixed["nets"])
        gnd_members = set(fixed["nets"]["GUESS_TERMINAL_GND"])
        self.assertIn("U3.GND", gnd_members)
        self.assertIn("U4.GND", gnd_members)
        self.assertNotIn("K1.COM", gnd_members)
        self.assertIn("GUESS_TERMINAL_GND", set(fixed["routing"]["terminal_policy"]["terminal_nets"]))
        self.assertTrue(
            any(
                repair["kind"] == "equivalent_rail_merged_into_guessed_terminal_net"
                and repair["from"] == "NET_SENSOR_GND"
                and repair["to"] == "GUESS_TERMINAL_GND"
                for repair in report["repairs"]
            )
        )

    def test_combination_router_terminalizes_declared_guess_nets(self) -> None:
        circuit = {
            "schema_version": "progen-kicad-circuit-ir/v1",
            "routing": {"mode": "combination"},
            "components": [
                {"id": "U1", "ref": "U1", "kind": "ESP32_WROOM", "value": "ESP32", "pins": {"GND": "GUESS_TERMINAL_GND"}},
                {"id": "U2", "ref": "U2", "kind": "BME280", "value": "BME280", "pins": {"GND": "GUESS_TERMINAL_GND"}},
            ],
            "nets": {"GUESS_TERMINAL_GND": ["U1.GND", "U2.GND"]},
        }
        placement = {
            "components": {
                "U1": {"kind": "ESP32_WROOM", "at": [20.0, 20.0], "rotation": 0.0},
                "U2": {"kind": "BME280", "at": [60.0, 20.0], "rotation": 0.0},
            },
            "pin_points": {
                "U1": {"GND": {"point": [20.0, 30.0], "side": "bottom"}},
                "U2": {"GND": {"point": [60.0, 30.0], "side": "bottom"}},
            },
            "obstacles": [],
        }

        plan = plan_wire_routes(
            placement,
            circuit,
            config={"routing_mode": "combination", "terminal_nets": ["GUESS_TERMINAL_GND"]},
        )

        self.assertEqual(plan["nets"]["GUESS_TERMINAL_GND"]["strategy"], "local_labels")
        self.assertEqual(plan["nets"]["GUESS_TERMINAL_GND"]["terminal_reason"], "combination_declared_terminal_net")
        self.assertEqual(plan["nets"]["GUESS_TERMINAL_GND"]["routes"], [])

    def test_guessed_terminal_endpoint_loses_to_explicit_same_physical_pin(self) -> None:
        loose = {
            "circuit_id": "LOOSE003",
            "components": [
                {"ref": "Q1", "kind": "IRLZ44N"},
                {"ref": "U1", "kind": "MAX485"},
                {"ref": "U2", "kind": "MCP2515"},
                {"ref": "R1", "kind": "RES"},
            ],
            "nets": {
                "GUESS_TERMINAL_GND": ["Q1.S", "U1.GND", "U2.GND"],
                "BAT_OUT": ["Q1.SOURCE", "R1.1"],
            },
        }

        fixed, report = validate_and_fix_main_json(loose)

        self.assertTrue(report["ok"], report["validation"]["errors"])
        self.assertIn("Q1.SOURCE", fixed["nets"]["BAT_OUT"])
        self.assertIn("GUESS_TERMINAL_GND", fixed["nets"])
        self.assertNotIn("Q1.S", fixed["nets"]["GUESS_TERMINAL_GND"])
        self.assertTrue(
            any(repair["kind"] == "physical_pin_conflict_guessed_endpoint_dropped" for repair in report["repairs"])
        )

    def test_7447_case_sensitive_input_and_segment_pins_stay_distinct(self) -> None:
        symbol = KiCadSymbolLibrary().flattened("74xx_IEEE:7447")
        geometries = _pin_geometries(symbol.text)

        bcd_a, bcd_status = _resolve_pin_geometry(ref="U1", kind="7447", pin="A", geometries=geometries)
        segment_a, segment_status = _resolve_pin_geometry(ref="U1", kind="7447", pin="a", geometries=geometries)

        self.assertEqual(bcd_status, "resolved")
        self.assertEqual(segment_status, "resolved")
        assert bcd_a is not None
        assert segment_a is not None
        self.assertEqual(bcd_a.number, "7")
        self.assertEqual(segment_a.number, "13")

    def test_generator_fallback_kinds_resolve_to_source_backed_symbols(self) -> None:
        spec = resolve_placement_spec("SCHOTTKY")

        self.assertIsNotNone(spec)
        assert spec is not None
        self.assertEqual(spec.lib_id, "Device:D_Schottky")
        symbol = KiCadSymbolLibrary().load(spec.lib_id)
        self.assertEqual(symbol.pin_numbers, ("1", "2"))


if __name__ == "__main__":
    unittest.main()
