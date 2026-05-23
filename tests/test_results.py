import json
import tempfile
import unittest
from pathlib import Path

from proteusgen.results import record_result


class ResultsTests(unittest.TestCase):
    def test_record_result_appends_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "results.jsonl"
            payload = {
                "test_id": "GEN_TEST_TEMP",
                "proteus_version": "8.13",
                "opened": True,
                "result_summary": "Pass.",
            }
            record_result(payload, output)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["test_id"], "GEN_TEST_TEMP")
            with self.assertRaisesRegex(ValueError, "already exists"):
                record_result(payload, output)

    def test_816_smoke_cannot_be_marked_authoritative(self) -> None:
        payload = {
            "test_id": "GEN_BAD_PROMOTION",
            "proteus_version": "8.16 SP3",
            "runtime_role": "proteus_8_16_smoke",
            "acceptance_authoritative": True,
            "opened": True,
            "result_summary": "Should fail.",
        }
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Authoritative acceptance"):
                record_result(payload, Path(directory) / "results.jsonl")


if __name__ == "__main__":
    unittest.main()
