"""Regression coverage for the shared ProGenEDA JSON → LTspice boundary.

These tests deliberately use canonical KiCad-shaped inputs.  They guard the
principle that LTspice chooses a documented backend profile without requiring
an LTspice-only circuit JSON or silently changing a declared logical circuit.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from ltspice.pipeline.component_selector import select_components
from ltspice.pipeline.input_adapter import canonicalize_source
from ltspice.pipeline.ltspice_asc_parser import parse_asc
from ltspice.pipeline.progen_ltspice_executable import run_executable
from ltspice.pipeline.value_editor import normal_mode_fields, validate_parameters
from ltspice.pipeline.catalogue import resolve_profile


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REGULATED_5V = (
    REPOSITORY_ROOT
    / "kicad/examples/portable_power_supply_demo_2026_07_14"
    / "progen_kicad_executable_run_2026_07_14_020605_regulated_5v_reverse_polarity_corrected"
    / "generation/final_json/regulated_5v_reverse_polarity.json"
)
LEGACY_RC = REPOSITORY_ROOT / "kicad/examples/rc_lowpass.json"


def _write_source(root: Path, name: str, circuit: dict[str, Any]) -> Path:
    source = root / name
    source.write_text(json.dumps(circuit, indent=2), encoding="utf-8")
    return source


def _vac_circuit() -> dict[str, Any]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "VAC_COMPATIBILITY",
        "project": {"name": "vac_compatibility", "analysis": [".ac dec 10 10 1k"]},
        "components": [
            {"ref": "V1", "kind": "VAC", "value": "1", "pins": {"1": "IN", "2": "GND"}},
            {"ref": "R1", "kind": "R", "value": "1k", "pins": {"1": "IN", "2": "GND"}},
            {"ref": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {"IN": ["V1.1", "R1.1"], "GND": ["V1.2", "R1.2", "G1.1"]},
        "expected_netlist": {
            "nets": [
                {"name": "IN", "members": ["V1.1", "R1.1"]},
                {"name": "GND", "members": ["V1.2", "R1.2", "G1.1"]},
            ]
        },
    }


class SharedCanonicalContractTests(unittest.TestCase):
    def test_legacy_source_model_and_portable_placement_hints_survive(self) -> None:
        # Exercise the checked-in v1 input itself; it carries VSIN as a
        # display value plus legacy spice_model and generic `at` geometry.
        fixed, report, _original = canonicalize_source(LEGACY_RC)
        v1 = next(item for item in fixed["components"] if item["ref"] == "V1")
        self.assertEqual(v1["kind"], "VSIN")
        self.assertEqual(v1["ltspice_profile"], "VSIN")
        self.assertEqual(v1["value"], "SIN(0 1 1k)")
        self.assertIn("at", v1)
        r1 = next(item for item in fixed["components"] if item["ref"] == "R1")
        self.assertEqual(r1["rotation"], 90)
        self.assertTrue(any(item["action"] == "used_as_source_value" for item in report["canonical_value_adaptations"]))

    def test_declared_expected_netlist_is_an_invariant(self) -> None:
        circuit = _vac_circuit()
        circuit["expected_netlist"]["nets"][0]["members"] = ["V1.1"]
        with tempfile.TemporaryDirectory() as temporary:
            source = _write_source(Path(temporary), "contradictory.json", circuit)
            with self.assertRaisesRegex(ValueError, "disagrees with expected_netlist"):
                canonicalize_source(source)

    def test_source_routing_mode_is_honored_when_no_cli_override_is_given(self) -> None:
        circuit = _vac_circuit()
        circuit["routing"] = {"mode": "terminal"}
        with tempfile.TemporaryDirectory() as temporary:
            source = _write_source(Path(temporary), "terminal.json", circuit)
            fixed, _report, _original = canonicalize_source(source)
        self.assertEqual(fixed["routing"]["mode"], "terminal")

    def test_vac_uses_ltspice_value2_ac_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = _write_source(root, "vac.json", _vac_circuit())
            fixed, _report, _original = canonicalize_source(source)
            v1 = next(item for item in fixed["components"] if item["ref"] == "V1")
            self.assertEqual(v1["kind"], "VAC")
            self.assertEqual(v1["ltspice_profile"], "VAC")
            self.assertEqual(v1["value"], "0")
            self.assertEqual(v1["parameters"], {"ac": "1"})

            summary = run_executable(source, output_root=root, label="vac")
            self.assertTrue(summary["ok"], summary)
            asc = parse_asc(Path(summary["run_dir"]) / summary["results"][0]["asc_path"])
        source_symbol = next(symbol for symbol in asc.symbols if symbol.ref == "V1")
        self.assertEqual(source_symbol.attributes, {"INSTNAME": "V1", "VALUE": "0", "VALUE2": "AC 1"})

    def test_rejection_names_the_actual_failed_stage(self) -> None:
        circuit = _vac_circuit()
        circuit["components"][0]["kind"] = "UNMODELLED_DIGITAL_IC"
        events: list[dict[str, Any]] = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = _write_source(root, "unsupported.json", circuit)
            summary = run_executable(source, output_root=root, label="unsupported", event_callback=events.append)
            failure = summary["results"][0]
            failure_file = Path(summary["run_dir"]) / "failures/unsupported/failure.json"
            persisted = json.loads(failure_file.read_text(encoding="utf-8"))
        self.assertFalse(summary["ok"])
        self.assertEqual(failure["failed_stage"], "select_components")
        self.assertEqual(persisted["failed_stage"], "select_components")
        self.assertTrue(any(event.get("stage") == "select_components" and event.get("state") == "failed" for event in events))


class RealCircuitCompatibilityTests(unittest.TestCase):
    def test_checked_in_kicad_regulated_supply_generates_natively(self) -> None:
        self.assertTrue(REGULATED_5V.is_file(), REGULATED_5V)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            summary = run_executable(REGULATED_5V, output_root=root, label="regulated-5v")
            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            run_dir = Path(summary["run_dir"])
            canonical = json.loads((run_dir / result["generation_dir"] / "internal/main-input-canonical.json").read_text(encoding="utf-8"))
            selection = json.loads((run_dir / result["generation_dir"] / "internal/component-selection.json").read_text(encoding="utf-8"))
            model_text = (run_dir / result["generation_dir"] / "project/progeneda_v1_models.lib").read_text(encoding="ascii")

        by_ref = {item["ref"]: item for item in canonical["components"]}
        self.assertEqual(by_ref["U1"]["kind"], "LM7805")
        self.assertEqual(by_ref["U1"]["ltspice_profile"], "LM7805")
        self.assertEqual(by_ref["C1"]["value"], "100u")
        self.assertEqual(by_ref["C1"]["metadata"]["voltage_rating"], "25V")
        self.assertEqual(by_ref["D2"]["value"], "PROGEN_LED_APPROX")
        self.assertEqual(by_ref["D2"]["metadata"]["color"], "green")
        self.assertIn(".subckt PROGEN_LM7805_APPROX", model_text)
        selected = {item["ref"]: item for item in selection["components"]}
        self.assertEqual(selected["J1"]["profile"]["support_state"], "interface_only")
        self.assertEqual(selected["PWR02"]["profile"]["native_representation"], "virtual_terminal")


class EffectivePropertyBindingTests(unittest.TestCase):
    def test_model_bound_and_subcircuit_properties_are_explicit(self) -> None:
        circuit = {
            "components": [
                {
                    "ref": "S1",
                    "kind": "SW",
                    "value": "SW",
                    "parameters": {"ron": "2", "roff": "10Meg", "vt": "3", "vh": "0.2", "off": "true"},
                    "pins": {"1": "A", "2": "B", "3": "CP", "4": "CN"},
                },
                {
                    "ref": "D1",
                    "kind": "LED",
                    "value": "LED",
                    "parameters": {"forward_voltage": "2.4V"},
                    "metadata": {"color": "green"},
                    "pins": {"1": "A", "2": "B"},
                },
                {
                    "ref": "U1",
                    "kind": "OPAMP",
                    "value": "OPAMP",
                    "parameters": {"a0": "200k", "gain_bandwidth": "2Meg", "slew_rate": "5Meg", "rout": "10"},
                    "pins": {"1": "OUT", "2": "INM", "3": "INP", "4": "VM", "8": "VP"},
                },
            ]
        }
        selected, _report = select_components(circuit)
        by_ref = {item.ref: item for item in selected}
        self.assertRegex(by_ref["S1"].value, r"^PROGEN_SWITCH__S1_[0-9A-F]{10}$")
        self.assertIn("Ron=2", by_ref["S1"].model_text or "")
        self.assertIn("Roff=10meg", by_ref["S1"].model_text or "")
        self.assertRegex(by_ref["D1"].value, r"^PROGEN_LED_APPROX__D1_[0-9A-F]{10}$")
        self.assertIn("Is=", by_ref["D1"].model_text or "")
        self.assertEqual((by_ref["D1"].model_binding or {})["reference_current"], "10mA")
        self.assertIn("params: A0=100k GAIN_BANDWIDTH=1Meg SLEW_RATE=10Meg ROUT=1Meg", by_ref["U1"].model_text or "")
        self.assertEqual(by_ref["U1"].parameters["gain_bandwidth"], "2meg")

    def test_normal_editor_exposes_effect_classification_and_case_insensitive_meg(self) -> None:
        switch_fields = normal_mode_fields(resolve_profile("SW"))
        opamp_fields = normal_mode_fields(resolve_profile("OPAMP"))
        potentiometer_fields = normal_mode_fields(resolve_profile("POT"))
        self.assertEqual(switch_fields["property_effects"]["parameters"]["ron"], "native_model_card")
        self.assertEqual(opamp_fields["property_effects"]["parameters"]["gain_bandwidth"], "native_instance_or_subcircuit")
        self.assertEqual(potentiometer_fields["parameter_constraints"]["wiper"]["maximum"], 1)
        self.assertEqual(validate_parameters(resolve_profile("C"), {"rpar": "10Meg"}), {"rpar": "10meg"})

    def test_normal_mode_rejects_scalar_values_outside_profile_semantics(self) -> None:
        with self.assertRaisesRegex(ValueError, "R.value must be greater than 0"):
            select_components({"components": [{"ref": "R1", "kind": "R", "value": "0", "pins": {"1": "A", "2": "B"}}]})
        with self.assertRaisesRegex(ValueError, "POT.parameters.wiper must be at most 1"):
            validate_parameters(resolve_profile("POT"), {"wiper": "1.1"})
        with self.assertRaisesRegex(ValueError, "SW.parameters.roff must be greater than ron"):
            validate_parameters(resolve_profile("SW"), {"ron": "10", "roff": "10"})
        with self.assertRaisesRegex(ValueError, "OPAMP.parameters.gain_bandwidth must be greater than 0"):
            validate_parameters(resolve_profile("OPAMP"), {"gain_bandwidth": "0"})

    def test_led_forward_voltage_binding_is_monotonic_at_its_declared_reference_point(self) -> None:
        selected, _report = select_components(
            {
                "components": [
                    {"ref": "DLOW", "kind": "LED", "parameters": {"forward_voltage": "1.8"}, "pins": {"1": "A", "2": "K"}},
                    {"ref": "DHIGH", "kind": "LED", "parameters": {"forward_voltage": "3.0"}, "pins": {"1": "A", "2": "K"}},
                ]
            }
        )
        by_ref = {item.ref: item for item in selected}
        # For a fixed Shockley current, lower Is means a higher forward drop.
        low_is = float((by_ref["DLOW"].model_binding or {})["derived_is"])
        high_is = float((by_ref["DHIGH"].model_binding or {})["derived_is"])
        self.assertGreater(low_is, high_is)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
