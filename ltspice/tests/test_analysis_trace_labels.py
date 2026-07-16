from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ltspice.pipeline.progen_ltspice_executable import run_executable


def _diode_sweep_with_logical_trace() -> dict[str, object]:
    """A two-terminal diode node would otherwise be rendered as bare wire."""

    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "TRACE_LABEL_DIODE",
        "project": {"name": "trace_label_diode", "analysis": [".dc V1 0 1 .1", ".save V(DIODE-NODE)"]},
        "components": [
            {"ref": "V1", "kind": "VDC", "value": "0", "pins": {"1": "VIN", "2": "GND"}},
            {"ref": "R1", "kind": "R", "value": "1k", "pins": {"1": "VIN", "2": "DIODE-NODE"}},
            {"ref": "D1", "kind": "1N4148", "value": "1N4148", "pins": {"1": "DIODE-NODE", "2": "GND"}},
            {"ref": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {
            "VIN": ["V1.1", "R1.1"],
            "DIODE-NODE": ["R1.2", "D1.1"],
            "GND": ["V1.2", "D1.2", "G1.1"],
        },
    }


class AnalysisTraceLabelTests(unittest.TestCase):
    def test_voltage_trace_forces_native_terminal_labels_before_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "diode-trace.json"
            source.write_text(json.dumps(_diode_sweep_with_logical_trace()), encoding="utf-8")
            summary = run_executable(source, output_root=root, label="trace-label")

            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            run_dir = Path(summary["run_dir"])
            asc = (run_dir / result["asc_path"]).read_text(encoding="ascii")
            wire_plan = json.loads(
                (run_dir / result["generation_dir"] / "internal" / "wire-plan.json").read_text(encoding="utf-8")
            )

        self.assertIn("!.save V(DIODE_NODE)", asc)
        trace_flags = [flag for flag in wire_plan["flags"] if flag["logical_net"] == "DIODE-NODE"]
        self.assertEqual({flag["name"] for flag in trace_flags}, {"DIODE_NODE"})
        self.assertEqual({flag["endpoint"] for flag in trace_flags}, {"R1.2", "D1.1"})
        self.assertEqual(wire_plan["forced_terminal_nets"], ["DIODE-NODE"])
        self.assertIn(
            {
                "net": "DIODE-NODE",
                "reason": "analysis_voltage_trace_requires_stable_native_label",
                "fallback": "terminal_flags",
            },
            wire_plan["rejected_wire_routes"],
        )


if __name__ == "__main__":
    unittest.main()
