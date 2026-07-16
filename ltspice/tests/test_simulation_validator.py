from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
import tempfile
import unittest
from unittest.mock import patch

from ltspice.pipeline.simulation_validator import OracleCommand, run_external_oracle


class SimulationValidatorLogDiagnosticTests(unittest.TestCase):
    def _oracle_report_for_log(self, log_text: str) -> dict[str, object]:
        """Run the batch-log branch with deterministic executable stand-ins."""

        with tempfile.TemporaryDirectory() as temporary:
            asc_path = Path(temporary) / "fixture.asc"
            asc_path.write_text("Version 4\nTEXT 0 0 Left 2 !.op\n", encoding="ascii")
            asc_path.with_suffix(".net").write_text("* fixture\n.end\n", encoding="utf-8")
            asc_path.with_suffix(".log").write_text(log_text, encoding="utf-8")
            successful = CompletedProcess(["ltspice"], 0, "", "")
            with patch(
                "ltspice.pipeline.simulation_validator.subprocess.run",
                side_effect=[successful, successful],
            ) as mocked_run:
                report = run_external_oracle(asc_path, oracle=OracleCommand(("ltspice",)))

        self.assertEqual(mocked_run.call_count, 2)
        return report

    def test_floating_node_warning_is_a_blocking_oracle_error(self) -> None:
        report = self._oracle_report_for_log(
            "LTspice 26.0.2 for Windows\nWARNING: Node n004 is floating.\n"
        )

        expected = "LTspice batch log reported floating node(s): n004."
        self.assertFalse(report["ok"], report)
        self.assertEqual(report["status"], "failed")
        self.assertIn(expected, report["errors"])
        batch = report["batch"]
        self.assertIsInstance(batch, dict)
        assert isinstance(batch, dict)
        self.assertFalse(batch["ok"])
        self.assertIn(expected, batch["errors"])

    def test_ignored_pulse_ncycles_warning_is_a_blocking_oracle_error(self) -> None:
        report = self._oracle_report_for_log(
            "C:\\fixture.net(3): WARNING: Ncycles must be a positive number, "
            "will be ignored (using default = infinity).\n"
        )

        expected = "LTspice batch log reported an invalid PULSE Ncycles value that LTspice ignored."
        self.assertFalse(report["ok"], report)
        self.assertEqual(report["status"], "failed")
        self.assertIn(expected, report["errors"])
        batch = report["batch"]
        self.assertIsInstance(batch, dict)
        assert isinstance(batch, dict)
        self.assertFalse(batch["ok"])
        self.assertIn(expected, batch["errors"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
