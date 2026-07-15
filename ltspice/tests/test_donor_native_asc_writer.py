"""Contract tests for the isolated donor-native LTspice ASC writer."""

from __future__ import annotations

from copy import deepcopy
import json
import tempfile
import unittest
from pathlib import Path

from ltspice.catalogues.ltspice_main_catalogue_loader import load_native_catalogue
from ltspice.pipeline.donor_native_asc_writer import (
    DonorNativeAscError,
    donor_native_rc_pulse_recipe,
    render_donor_native_asc,
    write_donor_native_asc,
)
from ltspice.pipeline.ltspice_asc_parser import parse_asc
from ltspice.pipeline.native_gui_verifier import NativeGuiVerificationError, inspect_native_asc_candidate


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
RC_RECIPE_PATH = REPOSITORY_ROOT / "ltspice/examples/native_rc_pulse.recipe.json"


class DonorNativeAscWriterTests(unittest.TestCase):
    def test_rc_pulse_recipe_emits_only_stock_native_records_and_cp1252(self) -> None:
        recipe = donor_native_rc_pulse_recipe()
        payload = render_donor_native_asc(recipe)
        text = payload.decode("cp1252")

        self.assertTrue(payload.endswith(b"\n"))
        self.assertIn(b"1\xb5", payload)
        self.assertEqual(text.splitlines()[:2], ["Version 4.1", "SHEET 1 880 680"])
        self.assertIn("SYMBOL voltage 208 -16 R0", text)
        self.assertIn("SYMBOL res 432 -16 R90", text)
        self.assertIn("SYMBOL cap 448 0 R0", text)
        self.assertIn("SYMATTR Value PULSE(0 5 0 1u 1u 0.5m 1m 0)", text)
        self.assertIn("SYMATTR Value 1µ", text)
        self.assertIn("TEXT 224 128 Left 2 !.tran 0 10ms 0.1u 1", text)

        # Exact native-mode boundary: no owned symbols/models and no virtual
        # net / terminal flags can leak in from the older writer.
        self.assertNotIn("progeneda", text.lower())
        self.assertNotIn(".asy", text.lower())
        self.assertNotIn(".lib", text.lower())
        self.assertNotIn("terminal", text.lower())
        flags = [line for line in text.splitlines() if line.startswith("FLAG ")]
        self.assertEqual(flags, ["FLAG 208 96 0"])
        allowed = {"Version", "SHEET", "WIRE", "FLAG", "SYMBOL", "WINDOW", "SYMATTR", "TEXT"}
        self.assertTrue(all(line.split(maxsplit=1)[0] in allowed for line in text.splitlines()))

    def test_recipe_file_and_python_fixture_have_identical_native_bytes(self) -> None:
        from_file = json.loads(RC_RECIPE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(render_donor_native_asc(from_file), render_donor_native_asc(donor_native_rc_pulse_recipe()))

    def test_writer_creates_only_the_requested_asc_and_independent_parser_reads_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = write_donor_native_asc(donor_native_rc_pulse_recipe(), root / "native_rc_pulse.asc")
            document = parse_asc(result.asc_path)
            extra_assets = sorted(path.name for path in root.iterdir() if path != result.asc_path)

        self.assertEqual(extra_assets, [])
        self.assertEqual(result.component_count, 3)
        self.assertEqual(result.wire_count, 5)
        self.assertEqual(result.ground_count, 1)
        self.assertEqual(result.directive_count, 1)
        self.assertEqual(document.encoding, "cp1252")
        self.assertEqual(document.version, "4.1")
        self.assertEqual(document.sheet, (1, 880, 680))
        self.assertEqual([symbol.name for symbol in document.symbols], ["voltage", "res", "cap"])
        self.assertEqual([symbol.ref for symbol in document.symbols], ["V1", "R1", "C1"])
        self.assertEqual([flag.name for flag in document.flags], ["0"])
        self.assertEqual(len(document.wires), 5)

    def test_catalogue_aliases_and_registered_pin_offsets_drive_physical_wiring(self) -> None:
        catalogue = load_native_catalogue()
        recipe = donor_native_rc_pulse_recipe()
        recipe["components"][1]["type"] = "R"
        recipe["components"][2]["type"] = "CAP"
        text = render_donor_native_asc(recipe, catalogue=catalogue).decode("cp1252")
        self.assertIn("SYMBOL res 432 -16 R90", text)
        self.assertIn("SYMBOL cap 448 0 R0", text)

    def test_donor_proven_spice_line_properties_and_direct_diagonal_wires_are_preserved(self) -> None:
        property_recipe = donor_native_rc_pulse_recipe()
        property_recipe["components"][1]["properties"].update(
            {"spice_line.tol": "1%", "spice_line.pwr": "120W"}
        )
        property_text = render_donor_native_asc(property_recipe).decode("cp1252")
        self.assertIn("SYMATTR SpiceLine tol=1% pwr=120W", property_text)

        # lca2.asc contains diagonal WIRE records.  The writer must preserve
        # them as direct segments rather than rejecting or terminalizing them.
        diagonal_recipe = {
            "schema": "progen-ltspice-native-recipe/v1",
            "components": [
                {"type": "V", "ref": "V1", "at": [0, 0], "properties": {"value.dc": "1"}},
                {"type": "R", "ref": "R1", "at": [48, 48], "properties": {"value": "1k"}},
            ],
            "wires": [[0, 16, 64, 64], [0, 96, 64, 144]],
            "ground_flags": [[0, 96]],
            "directives": [{"at": [0, 176], "text": ".op"}],
        }
        diagonal_text = render_donor_native_asc(diagonal_recipe).decode("cp1252")
        self.assertIn("WIRE 0 16 64 64", diagonal_text)
        self.assertIn("WIRE 0 96 64 144", diagonal_text)

    def test_rejects_unsupported_property_and_unwired_pin_instead_of_creating_a_terminal(self) -> None:
        unsupported = donor_native_rc_pulse_recipe()
        unsupported["components"][1]["properties"]["tolerance"] = "1%"
        with self.assertRaisesRegex(DonorNativeAscError, "not a donor-supported property"):
            render_donor_native_asc(unsupported)

        unwired = donor_native_rc_pulse_recipe()
        unwired["wires"] = unwired["wires"][1:]
        with self.assertRaisesRegex(DonorNativeAscError, r"V1\.1.*no physical WIRE endpoint"):
            render_donor_native_asc(unwired)

    def test_serializes_only_ground_zero_and_rejects_external_model_directives(self) -> None:
        recipe = donor_native_rc_pulse_recipe()
        recipe["ground_flags"] = [[208, 96], [464, 64]]
        text = render_donor_native_asc(recipe).decode("cp1252")
        # The recipe API has no flag name field; even two legal physical ground
        # anchors can only serialize as the native global node zero.
        flags = [line for line in text.splitlines() if line.startswith("FLAG ")]
        self.assertEqual(flags, ["FLAG 208 96 0", "FLAG 464 64 0"])

        model = donor_native_rc_pulse_recipe()
        model["directives"] = [{"at": [224, 128], "text": ".include added_model.lib"}]
        with self.assertRaisesRegex(DonorNativeAscError, "non-donor-native model/library"):
            render_donor_native_asc(model)

    def test_gui_verifier_static_gate_rejects_legacy_terminal_and_custom_symbol_records(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / "native.asc"
            write_donor_native_asc(donor_native_rc_pulse_recipe(), valid)
            report = inspect_native_asc_candidate(valid)
            self.assertTrue(report["static_boundary_ok"])
            self.assertEqual(report["terminal_fallback"], "forbidden")

            legacy = root / "legacy.asc"
            legacy.write_text("Version 4.1\nSHEET 1 880 680\nFLAG 0 0 VOUT\nSYMBOL progeneda_resistor 0 0 R0\n", encoding="cp1252")
            with self.assertRaisesRegex(NativeGuiVerificationError, "Expected an existing .asc"):
                inspect_native_asc_candidate(root / "missing.asc")
            rejected = inspect_native_asc_candidate(legacy)
            self.assertFalse(rejected["static_boundary_ok"])
            self.assertIn("legacy ProGenEDA", " ".join(rejected["static_boundary_errors"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
