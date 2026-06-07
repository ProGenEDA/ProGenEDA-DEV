import tempfile
import unittest
import struct
from pathlib import Path

from proteusgen.resistor_examples import predefined_resistor_cases
from proteusgen.resistor_ir import validate_resistor_payload, visible_resistor_value
from proteusgen.resistor_v9 import ResistorGenerationBlocked, _extract_object_chunk, generate_resistor_project_from_payload
from proteusgen.pdsprj import read_internal_file


class ResistorV9Tests(unittest.TestCase):
    def test_predefined_cases_validate(self) -> None:
        cases = predefined_resistor_cases()
        self.assertEqual(len(cases), 20)
        for payload in cases:
            with self.subTest(payload["project"]["output_basename"]):
                report = validate_resistor_payload(payload)
                self.assertTrue(report.valid, report.as_dict())

    def test_predefined_cases_generate_static_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for payload in predefined_resistor_cases():
                basename = payload["project"]["output_basename"]
                with self.subTest(basename):
                    result = generate_resistor_project_from_payload(payload, root / basename)
                    self.assertTrue(result.output_path.exists())
                    self.assertTrue(result.cdb_path.exists())
                    self.assertTrue(result.dsn_path.exists())
                    self.assertEqual(result.manifest["static_validation_issues"], [])
                    self.assertEqual(result.manifest["component_count_emitted_cdb"], len(payload["components"]))
                    self.assertEqual(result.manifest["power_bridge_count"], 1)
                    self.assertEqual(result.manifest["terminal_count"], len(payload["components"]) * 2 + 2)
                    self.assertEqual(result.manifest["visual_wire_count"], 0)
                    self.assertEqual(result.manifest["wire_count"], len(payload["components"]) * 2 + 1)
                    dsn = read_internal_file(result.output_path, "ROOT.DSN")
                    chunk = _extract_object_chunk(dsn)
                    self.assertEqual(chunk.count(b"$TERPOWER"), 1)
                    self.assertIn(b"$TERGROUND", chunk)

    def test_power_nodes_use_one_bridge_not_resistor_endpoint_power_markers(self) -> None:
        payload = predefined_resistor_cases()[0]
        with tempfile.TemporaryDirectory() as directory:
            result = generate_resistor_project_from_payload(payload, directory)
            self.assertEqual(result.manifest["power_bridge_count"], 1)
            self.assertEqual(result.manifest["topology"][0]["input_marker"], "$TERINPUT")
            self.assertEqual(result.manifest["topology"][0]["output_marker"], "$TERGROUND")
            dsn = read_internal_file(result.output_path, "ROOT.DSN")
            chunk = _extract_object_chunk(dsn)
            self.assertEqual(chunk.count(b"$TERPOWER"), 1)
            self.assertEqual(chunk.count(b"$TERINPUT"), 0)
            self.assertEqual(chunk.count(b"$TEROUTPUT"), 0)
            self.assertEqual(chunk.count(b"$TERBIDIR"), 2)

    def test_invalid_long_node_label_is_rejected(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["nodes"][0]["id"] = "VCC"
        payload["components"][0]["nodes"][0] = "VCC"
        report = validate_resistor_payload(payload)
        self.assertTrue(any(issue.code == "INVALID_NODE_ID" for issue in report.errors))

    def test_invalid_long_ref_is_rejected(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["components"][0]["ref"] = "R10"
        report = validate_resistor_payload(payload)
        self.assertTrue(any(issue.code == "INVALID_COMPONENT_REF" for issue in report.errors))

    def test_unknown_component_type_is_rejected(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["components"][0]["type"] = "CAPACITOR"
        report = validate_resistor_payload(payload)
        self.assertTrue(any(issue.code == "UNSUPPORTED_COMPONENT_TYPE" for issue in report.errors))

    def test_invalid_orientation_hint_is_rejected(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["components"][0]["visual"] = {"orientation_hint": "diagonal"}
        report = validate_resistor_payload(payload)
        self.assertTrue(any(issue.code == "UNSUPPORTED_ORIENTATION_HINT" for issue in report.errors))

    def test_vertical_orientation_emits_real_rotation_and_vertical_wires(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["components"][0]["visual"] = {"orientation_hint": "vertical"}
        with tempfile.TemporaryDirectory() as directory:
            result = generate_resistor_project_from_payload(payload, directory)
            dsn = read_internal_file(result.output_path, "ROOT.DSN")
            model = dsn.find(b"\x02\x00\x08RESISTOR")
            self.assertNotEqual(model, -1)
            resistor_text = model + 3
            angle = struct.unpack("<h", dsn[resistor_text + 16 : resistor_text + 18])[0]
            self.assertEqual(angle, -900)
            topology = result.manifest["topology"][0]
            self.assertEqual(topology["pin1"], {"x": -6350000, "y": 5080000})
            self.assertEqual(topology["pin2"], {"x": -6350000, "y": 3810000})
            self.assertEqual(topology["angle_tenths"], -900)

    def test_visual_wires_are_skipped_until_validated(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["layout"]["visual_wires"] = [{"x1": -6350000, "y1": 5080000, "x2": -5080000, "y2": 5080000}]
        with tempfile.TemporaryDirectory() as directory:
            result = generate_resistor_project_from_payload(payload, directory)
            self.assertEqual(result.manifest["short_wire_count"], 2)
            self.assertEqual(result.manifest["bridge_wire_count"], 1)
            self.assertEqual(result.manifest["visual_wire_count"], 0)
            self.assertEqual(result.manifest["visual_wire_skipped_count"], 1)
            self.assertEqual(result.manifest["wire_count"], 3)
            self.assertEqual(result.manifest["static_validation_issues"], [])

    def test_longer_values_use_clean_two_character_visible_prefix(self) -> None:
        self.assertEqual(visible_resistor_value("10k"), "10")
        self.assertEqual(visible_resistor_value("21k"), "21")

    def test_dense_manual_positions_are_stretched_to_safe_grid(self) -> None:
        payload = predefined_resistor_cases()[1]
        payload["layout"]["strategy"] = "legacy"
        payload["layout"]["component_positions"]["R2"] = {"x": -5080000, "y": 5080000}
        with tempfile.TemporaryDirectory() as directory:
            result = generate_resistor_project_from_payload(payload, directory)
            self.assertGreater(result.manifest["layout_adjusted_count"], 0)
            self.assertEqual(result.manifest["topology"][0]["x"], -6350000)
            self.assertEqual(result.manifest["topology"][1]["x"], -3810000)

    def test_vertical_stack_positions_use_larger_row_spacing(self) -> None:
        payload = predefined_resistor_cases()[2]
        payload["layout"]["strategy"] = "legacy"
        for component in payload["components"]:
            component["visual"] = {"orientation_hint": "vertical"}
        payload["layout"]["component_positions"] = {
            "R1": {"x": -6350000, "y": 5080000},
            "R2": {"x": -6350000, "y": 3810000},
            "R3": {"x": -6350000, "y": 2540000},
        }
        with tempfile.TemporaryDirectory() as directory:
            result = generate_resistor_project_from_payload(payload, directory)
            ys = [item["y"] for item in result.manifest["topology"]]
            self.assertEqual(ys, [5080000, 2540000, 0])

    def test_missing_endpoint_node_is_rejected(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["components"][0]["nodes"][1] = "NX"
        report = validate_resistor_payload(payload)
        self.assertTrue(any(issue.code == "UNKNOWN_ENDPOINT_NODE" for issue in report.errors))

    def test_missing_position_is_rejected_without_auto_place(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["layout"]["strategy"] = "legacy"
        payload["layout"]["component_positions"] = {}
        report = validate_resistor_payload(payload)
        self.assertTrue(any(issue.code == "MISSING_COMPONENT_POSITION" for issue in report.errors))
        with self.assertRaises(ResistorGenerationBlocked):
            generate_resistor_project_from_payload(payload, Path(tempfile.gettempdir()) / "blocked_resistor_case")

    def test_missing_position_is_allowed_with_auto_place(self) -> None:
        payload = predefined_resistor_cases()[0]
        payload["layout"]["strategy"] = "legacy"
        payload["layout"]["component_positions"] = {}
        payload["layout"]["auto_place"] = True
        with tempfile.TemporaryDirectory() as directory:
            result = generate_resistor_project_from_payload(payload, directory)
            self.assertEqual(result.manifest["auto_placed_count"], 1)


if __name__ == "__main__":
    unittest.main()
