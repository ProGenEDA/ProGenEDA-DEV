"""Regression coverage distilled from the newly supplied LTspice donors.

These fixtures intentionally use canonical ProGenEDA JSON rather than
depending on the donor directory.  They protect the generator's supported
semantics while leaving a future ASC importer free to handle raw donor layout
and symbol-library details separately.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from ltspice.pipeline.catalogue import resolve_profile
from ltspice.pipeline.ltspice_asc_parser import decode_lts_text, parse_asc
from ltspice.pipeline.progen_ltspice_executable import run_executable
from ltspice.pipeline.value_editor import ValueValidationError, validate_component_value


def _ac_source_fixture() -> dict[str, Any]:
    """Canonical form of an LTspice small-signal source with ``Value2 AC 1``."""

    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "DONOR_STYLE_AC_SOURCE",
        "project": {"name": "donor_style_ac_source", "analysis": [".ac dec 100 10 300"]},
        "components": [
            {
                "ref": "V1",
                "kind": "VDC",
                "value": "0",
                "parameters": {"ac": "1"},
                "pins": {"1": "IN", "2": "GND"},
            },
            {"ref": "R1", "kind": "R", "value": "1k", "pins": {"1": "IN", "2": "GND"}},
            {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
        ],
        "nets": {
            "IN": ["V1.1", "R1.1"],
            "GND": ["V1.2", "R1.2", "G1.1"],
        },
    }


def _twenty_passive_ladder_fixture() -> dict[str, Any]:
    """A 20-passive R/L series and C-shunt ladder with a valid ground path."""

    components: list[dict[str, Any]] = [
        {"ref": "V1", "kind": "VDC", "value": "5", "pins": {"1": "N0", "2": "GND"}},
        {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
    ]
    nets: dict[str, list[str]] = {"N0": ["V1.1"], "GND": ["V1.2", "G1.1"]}
    series: list[tuple[str, str, str, str, str]] = []
    for index in range(1, 8):
        series.append((f"R{index}", "R", f"N{2 * index - 2}", f"N{2 * index - 1}", "1k"))
        if index <= 6:
            series.append((f"L{index}", "L", f"N{2 * index - 1}", f"N{2 * index}", "10m"))

    for ref, kind, left, right, value in series:
        components.append({"ref": ref, "kind": kind, "value": value, "pins": {"1": left, "2": right}})
        nets.setdefault(left, []).append(f"{ref}.1")
        nets.setdefault(right, []).append(f"{ref}.2")

    for index in range(1, 8):
        ref = f"C{index}"
        node = f"N{2 * index - 1}"
        components.append({"ref": ref, "kind": "C", "value": "1u", "pins": {"1": node, "2": "GND"}})
        nets[node].append(f"{ref}.1")
        nets["GND"].append(f"{ref}.2")

    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "TWENTY_PASSIVE_DONOR_LADDER",
        "project": {"name": "twenty_passive_donor_ladder", "analysis": [".op"]},
        "components": components,
        "nets": nets,
    }


class DonorRegressionTests(unittest.TestCase):
    def test_ac_source_value_zero_and_ac_parameter_emit_native_value2(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "ac-source.json"
            source.write_text(json.dumps(_ac_source_fixture()), encoding="utf-8")

            summary = run_executable(source, output_root=root, label="donor-ac-source")

            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            document = parse_asc(Path(summary["run_dir"]) / result["asc_path"])
            source_symbol = next(symbol for symbol in document.symbols if symbol.ref == "V1")

        self.assertTrue(result["final_validation"]["ok"], result["final_validation"])
        self.assertEqual(
            source_symbol.attributes,
            {"INSTNAME": "V1", "VALUE": "0", "VALUE2": "AC 1"},
        )

    def test_donor_style_waveforms_and_formatted_passives_normalize_safely(self) -> None:
        pulse = resolve_profile("VPULSE")
        sine = resolve_profile("VSIN")
        resistor = resolve_profile("R")
        capacitor = resolve_profile("C")
        inductor = resolve_profile("L")

        self.assertEqual(
            validate_component_value(pulse, "pulse(0 5 0 1u 1u 0.5m 1m 3)"),
            "PULSE(0 5 0 1u 1u 0.5m 1m 3)",
        )
        with self.assertRaisesRegex(ValueValidationError, "Ncycles"):
            validate_component_value(pulse, "pulse(0 5 0 1u 1u 0.5m 1m 0)")
        self.assertEqual(validate_component_value(sine, "sine(0 5 250)"), "SINE(0 5 250)")

        micro_value, encoding = decode_lts_text(b"1\xb5")
        self.assertEqual(encoding, "cp1252")
        self.assertEqual(validate_component_value(capacitor, micro_value), "1u")
        self.assertEqual(validate_component_value(capacitor, "0.1"), "0.1")
        with self.assertRaisesRegex(ValueValidationError, "ambiguous"):
            validate_component_value(capacitor, "0.1F")
        self.assertEqual(validate_component_value(resistor, "1.1R"), "1.1")
        self.assertEqual(validate_component_value(inductor, "100mH"), "100m")

    def test_twenty_passive_ladder_validates_and_releases_user_artifact(self) -> None:
        circuit = _twenty_passive_ladder_fixture()
        passives = [item for item in circuit["components"] if item["kind"] in {"R", "C", "L"}]
        self.assertEqual(len(passives), 20)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "twenty-passive-ladder.json"
            source.write_text(json.dumps(circuit), encoding="utf-8")

            summary = run_executable(source, output_root=root, label="twenty-passive-ladder")

            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            self.assertTrue(result["final_validation"]["ok"], result["final_validation"])
            artifacts = result["output_artifacts"]
            self.assertIsNotNone(artifacts)
            assert artifacts is not None
            user_zip = Path(summary["run_dir"]) / artifacts["user_project"]["path"]
            user_zip_exists = user_zip.is_file()
            document = parse_asc(Path(summary["run_dir"]) / result["asc_path"])

        generated_passives = [
            symbol
            for symbol in document.symbols
            if symbol.name in {"progeneda_res", "progeneda_cap", "progeneda_ind"}
        ]
        self.assertEqual(len(generated_passives), 20)
        self.assertEqual(artifacts["user_project"]["visibility"], "user_downloadable")
        self.assertTrue(user_zip_exists)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
