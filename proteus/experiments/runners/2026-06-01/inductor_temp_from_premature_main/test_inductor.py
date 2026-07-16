import tempfile
import unittest
from pathlib import Path

from proteusgen.inductor import InductorGenerationBlocked, generate_inductor_project_from_payload
from proteusgen.inductor_examples import predefined_inductor_cases
from proteusgen.inductor_ir import validate_inductor_payload
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


class InductorTests(unittest.TestCase):
    def test_predefined_inductor_cases_validate(self) -> None:
        cases = predefined_inductor_cases()
        self.assertEqual(len(cases), 2)
        for payload in cases:
            with self.subTest(payload["project"]["output_basename"]):
                report = validate_inductor_payload(payload)
                self.assertTrue(report.valid, report.as_dict())

    def test_predefined_inductor_cases_generate_static_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for payload in predefined_inductor_cases():
                basename = payload["project"]["output_basename"]
                with self.subTest(basename):
                    result = generate_inductor_project_from_payload(payload, root / basename)
                    self.assertEqual(result.manifest["static_validation_issues"], [])
                    self.assertEqual(result.manifest["component_count_emitted_cdb"], len(payload["components"]))
                    dsn = read_internal_file(result.output_path, "ROOT.DSN")
                    cdb = read_internal_file(result.output_path, "ROOT.CDB")
                    chunk = _extract_object_chunk(dsn)
                    self.assertEqual(chunk.count(b"REALIND"), len(payload["components"]) * 3)
                    self.assertEqual(cdb.count(b"MODFILE=REALIND"), len(payload["components"]))

    def test_single_power_ground_uses_donor04_order(self) -> None:
        payload = predefined_inductor_cases()[1]
        with tempfile.TemporaryDirectory() as directory:
            result = generate_inductor_project_from_payload(payload, directory)
            chunk = _extract_object_chunk(read_internal_file(result.output_path, "ROOT.DSN"))
            self.assertEqual(result.manifest["donor_fixture_id"], "inductor_04_power_ground")
            self.assertEqual(result.manifest["object_chunk_len"], 947)
            self.assertEqual(chunk.count(b"$TERPOWER"), 1)
            self.assertEqual(chunk.count(b"$TERGROUND"), 1)
            self.assertIn("donor04", result.manifest["topology"][0]["method"])

    def test_multi_power_ground_inductor_is_rejected(self) -> None:
        payload = predefined_inductor_cases()[1]
        payload["nodes"].append({"id": "N1", "kind": "internal"})
        payload["components"] = [
            {"ref": "L1", "type": "INDUCTOR", "value": "1mH", "nodes": ["V0", "N1"], "visual": {}},
            {"ref": "L2", "type": "INDUCTOR", "value": "2mH", "nodes": ["N1", "G0"], "visual": {}},
        ]
        payload["layout"]["component_positions"] = {
            "L1": {"x": -7366000, "y": 1270000},
            "L2": {"x": -4826000, "y": 1270000},
        }
        report = validate_inductor_payload(payload)
        self.assertTrue(any(issue.code == "INDUCTOR_POWER_GROUND_MULTI_UNVALIDATED" for issue in report.errors))
        with self.assertRaises(InductorGenerationBlocked):
            generate_inductor_project_from_payload(payload, Path(tempfile.gettempdir()) / "blocked_inductor_case")


if __name__ == "__main__":
    unittest.main()
