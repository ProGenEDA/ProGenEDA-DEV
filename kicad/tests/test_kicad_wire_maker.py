from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kicad.pipeline.arrangement_decider import decide_arrangement
from kicad.pipeline.beautifier import apply_coordinate_edits
from kicad.pipeline.final_circuit_builder import STAGE_REPORT_WIRE_CONFIG, build_final_test_circuits, placer_ready_circuit
from kicad.pipeline.kicad_wire_maker import generate_wired_projects_from_final_json, make_kicad_wires
from kicad.pipeline.placer_pipeline import run_placer_pipeline
from kicad.pipeline.wire_planner import plan_wire_routes


class KiCadWireMakerTests(unittest.TestCase):
    def test_wire_maker_emits_kicad_wire_and_label_objects(self) -> None:
        circuit = build_final_test_circuits()[0]
        ctx = run_placer_pipeline(placer_ready_circuit(circuit), write_trace=False)
        placement = ctx.placement_plan
        placement_dict = placement.as_dict()
        beautified = apply_coordinate_edits(placement_dict, decide_arrangement(placement_dict, circuit))
        wire_plan = plan_wire_routes(beautified, circuit, config=STAGE_REPORT_WIRE_CONFIG)
        result = make_kicad_wires(circuit, placement, wire_plan)
        self.assertIn("(wire (pts", result.schematic_objects)
        self.assertIn("(label \"GND\"", result.schematic_objects)
        self.assertGreater(result.report["wire_object_count"], 0)
        self.assertGreater(result.report["pin_resolved_count"], 0)

    def test_generate_wired_projects_from_final_json_writes_projects(self) -> None:
        circuits = build_final_test_circuits()[:2]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "final_json"
            source.mkdir()
            for circuit in circuits:
                (source / f"{circuit['circuit_id']}.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
            summary = generate_wired_projects_from_final_json(
                source,
                examples_root=root,
                label="unit_test_wired",
                run_dir=root / "wired_run",
            )
            self.assertEqual(summary["project_count"], 2)
            self.assertTrue(summary["all_static_checks_ok"])
            self.assertGreater(summary["total_wire_objects"], 0)
            for result in summary["results"]:
                schematic = root / "wired_run" / result["schematic_file"]
                self.assertTrue((root / "wired_run" / result["open_this"]).exists())
                self.assertIn("wires, labels, and junctions are generated", schematic.read_text(encoding="utf-8"))
                self.assertGreater(result["wire_object_count"], 0)


if __name__ == "__main__":
    unittest.main()
