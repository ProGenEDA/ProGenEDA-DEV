"""Regression coverage for native E/G voltage-controlled source generation."""

from __future__ import annotations

import json
import os
import shlex
import tempfile
import unittest
from pathlib import Path

from ltspice.pipeline.catalogue import resolve_profile
from ltspice.pipeline.input_adapter import canonicalize_source
from ltspice.pipeline.ltspice_asc_parser import parse_asc, parse_asy
from ltspice.pipeline.progen_ltspice_executable import run_executable
from ltspice.pipeline.value_editor import ValueValidationError, validate_component_value


def _controlled_source_circuit() -> dict[str, object]:
    """A complete .op fixture with both native controlled-source primitives."""

    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "CONTROLLED_SOURCES",
        "circuit_name": "VCVS and VCCS static fixture",
        "project": {"name": "controlled_sources", "analysis": [".op"]},
        "components": [
            {"ref": "V1", "kind": "VDC", "value": "2", "pins": {"1": "VIN", "2": "GND"}},
            {"ref": "E1", "kind": "VCVS", "value": "3", "pins": {"1": "V_E", "2": "GND", "3": "VIN", "4": "GND"}},
            {"ref": "G1", "kind": "VCCS", "value": "2mS", "pins": {"1": "V_G", "2": "GND", "3": "VIN", "4": "GND"}},
            {"ref": "RE", "kind": "R", "value": "1k", "pins": {"1": "V_E", "2": "GND"}},
            {"ref": "RG", "kind": "R", "value": "1k", "pins": {"1": "V_G", "2": "GND"}},
            {"ref": "GND1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
        ],
        "nets": {
            "VIN": ["V1.1", "E1.3", "G1.3"],
            "V_E": ["E1.1", "RE.1"],
            "V_G": ["G1.1", "RG.1"],
            "GND": ["V1.2", "E1.2", "E1.4", "G1.2", "G1.4", "RE.2", "RG.2", "GND1.1"],
        },
    }


class ControlledSourceGenerationTests(unittest.TestCase):
    def test_controlled_source_units_and_pin_aliases_are_profile_validated(self) -> None:
        vcvs = resolve_profile("E")
        vccs = resolve_profile("G")

        self.assertEqual(vcvs.kind, "VCVS")
        self.assertEqual(vccs.kind, "VCCS")
        self.assertEqual(vcvs.native_pin_for_canonical("OUT+"), "1")
        self.assertEqual(vcvs.native_pin_for_canonical("CTRL-"), "4")
        self.assertEqual(vccs.native_pin_for_canonical("P"), "3")
        self.assertEqual(vccs.native_pin_for_canonical("N"), "4")
        self.assertEqual(validate_component_value(vcvs, "2"), "2")
        self.assertEqual(validate_component_value(vccs, "2mS"), "2m")
        with self.assertRaises(ValueValidationError):
            validate_component_value(vcvs, "2V")
        with self.assertRaises(ValueValidationError):
            validate_component_value(vccs, "2V")

    def test_native_e_and_g_aliases_survive_shared_canonicalization(self) -> None:
        raw = {
            "components": [
                {"ref": "E1", "kind": "E", "value": "2"},
                {"ref": "G1", "kind": "G", "value": "1m"},
            ]
        }
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "native-aliases.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            fixed, _report, _original = canonicalize_source(source)
        kinds = {item["ref"]: item["kind"] for item in fixed["components"]}
        profiles = {item["ref"]: item["ltspice_profile"] for item in fixed["components"]}
        self.assertEqual(kinds, {"E1": "E", "G1": "G"})
        self.assertEqual(profiles, {"E1": "VCVS", "G1": "VCCS"})

    def test_generator_writes_independently_parseable_native_e_and_g_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "controlled-sources.json"
            source.write_text(json.dumps(_controlled_source_circuit()), encoding="utf-8")

            summary = run_executable(source, output_root=root, label="controlled-sources")

            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            self.assertTrue(result["final_validation"]["ok"], result["final_validation"])
            run_dir = Path(summary["run_dir"])
            project_dir = run_dir / result["generation_dir"] / "project"
            document = parse_asc(run_dir / result["asc_path"])
            by_ref = {symbol.ref: symbol for symbol in document.symbols}
            self.assertEqual(by_ref["E1"].name, "progeneda_vcvs")
            self.assertEqual(by_ref["E1"].attributes, {"INSTNAME": "E1", "VALUE": "3"})
            self.assertEqual(by_ref["G1"].name, "progeneda_vccs")
            self.assertEqual(by_ref["G1"].attributes, {"INSTNAME": "G1", "VALUE": "2m"})

            for filename, prefix in (("progeneda_vcvs.asy", "E"), ("progeneda_vccs.asy", "G")):
                symbol = parse_asy(project_dir / filename)
                self.assertEqual(symbol.attributes["PREFIX"], prefix)
                self.assertEqual([pin.spice_order for pin in symbol.pins], ["1", "2", "3", "4"])
                self.assertEqual([pin.name for pin in symbol.pins], ["OUT+", "OUT-", "CTRL+", "CTRL-"])

    @unittest.skipUnless(
        os.environ.get("PROGEN_LTSPICE_ORACLE_COMMAND"),
        "set PROGEN_LTSPICE_ORACLE_COMMAND to run the installed-LTspice integration check",
    )
    def test_installed_oracle_netlists_and_solves_controlled_sources(self) -> None:
        """Optional local evidence: a real LTspice instance accepts E/G output."""

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "controlled-sources.json"
            source.write_text(json.dumps(_controlled_source_circuit()), encoding="utf-8")
            summary = run_executable(
                source,
                output_root=root,
                label="controlled-sources-oracle",
                oracle_command=shlex.split(os.environ["PROGEN_LTSPICE_ORACLE_COMMAND"]),
                oracle_path_style=os.environ.get("PROGEN_LTSPICE_ORACLE_PATH_STYLE", "native"),
                oracle_timeout_seconds=120,
            )
            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            report_path = Path(summary["run_dir"]) / result["generation_dir"] / "internal" / "simulation-report.json"
            oracle = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(oracle["status"], "passed", oracle)
        self.assertTrue(oracle["exported_netlist_validation"]["ok"], oracle)
        self.assertTrue(oracle["batch"]["ok"], oracle)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
