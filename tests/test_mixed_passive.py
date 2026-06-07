import tempfile
import unittest
from pathlib import Path

from proteusgen.mixed_passive import MixedPassiveGenerationBlocked, generate_mixed_passive_project_from_payload
from proteusgen.mixed_passive_examples import predefined_mixed_passive_cases
from proteusgen.mixed_passive_ir import validate_mixed_passive_payload
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


class MixedPassiveTests(unittest.TestCase):
    def test_predefined_mixed_cases_validate(self) -> None:
        cases = predefined_mixed_passive_cases()
        self.assertEqual(len(cases), 2)
        for payload in cases:
            with self.subTest(payload["project"]["output_basename"]):
                report = validate_mixed_passive_payload(payload)
                self.assertTrue(report.valid, report.as_dict())

    def test_predefined_mixed_cases_generate_static_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for payload in predefined_mixed_passive_cases():
                basename = payload["project"]["output_basename"]
                with self.subTest(basename):
                    result = generate_mixed_passive_project_from_payload(payload, root / basename)
                    self.assertEqual(result.manifest["static_validation_issues"], [])
                    self.assertEqual(result.manifest["component_count_emitted_cdb"], len(payload["components"]))
                    self.assertEqual(result.manifest["power_bridge_count"], 1)
                    self.assertEqual(result.manifest["visual_wire_count"], 0)
                    dsn = read_internal_file(result.output_path, "ROOT.DSN")
                    cdb = read_internal_file(result.output_path, "ROOT.CDB")
                    chunk = _extract_object_chunk(dsn)
                    self.assertEqual(chunk.count(b"$TERPOWER"), 1)
                    self.assertIn(b"$TERGROUND", chunk)
                    self.assertNotIn(b"$TERINPUT", chunk)
                    self.assertNotIn(b"$TEROUTPUT", chunk)
                    self.assertEqual(
                        chunk.count(b"$TERBIDIR"),
                        result.manifest["bidirectional_terminal_count"],
                    )
                    self.assertEqual(cdb.count(b"RESISTOR"), result.manifest["resistor_count"])
                    self.assertEqual(cdb.count(b"CAPACITOR"), result.manifest["capacitor_count"])

    def test_locked_21_case_uses_compact_safe_row_spacing(self) -> None:
        payload = predefined_mixed_passive_cases()[1]
        payload["layout"]["strategy"] = "legacy"
        with tempfile.TemporaryDirectory() as directory:
            result = generate_mixed_passive_project_from_payload(payload, directory)
            ys = sorted({item["y"] for item in result.manifest["topology"]}, reverse=True)
            self.assertEqual(ys, [5080000, 2540000, 0])
            self.assertEqual(result.manifest["safe_spacing"], {"x": 2540000, "y": 2540000})
            self.assertEqual(result.manifest["layout_adjusted_count"], 14)

    def test_duplicate_positions_are_moved_off_each_other(self) -> None:
        payload = predefined_mixed_passive_cases()[0]
        payload["layout"]["strategy"] = "legacy"
        payload["layout"]["component_positions"]["C2"] = dict(payload["layout"]["component_positions"]["R1"])
        with tempfile.TemporaryDirectory() as directory:
            result = generate_mixed_passive_project_from_payload(payload, directory)
            coords = [(item["x"], item["y"]) for item in result.manifest["topology"]]
            self.assertEqual(len(coords), len(set(coords)))
            self.assertGreater(result.manifest["layout_adjusted_count"], 0)

    def test_ground_on_left_endpoint_is_rejected(self) -> None:
        payload = predefined_mixed_passive_cases()[0]
        payload["components"][0]["nodes"] = ["G0", "N1"]
        report = validate_mixed_passive_payload(payload)
        self.assertTrue(any(issue.code == "GROUND_LEFT_ENDPOINT_UNSUPPORTED" for issue in report.errors))
        with self.assertRaises(MixedPassiveGenerationBlocked):
            generate_mixed_passive_project_from_payload(payload, Path(tempfile.gettempdir()) / "blocked_mixed_case")


if __name__ == "__main__":
    unittest.main()
