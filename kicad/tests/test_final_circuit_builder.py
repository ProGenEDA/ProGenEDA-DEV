from __future__ import annotations

import unittest

from kicad.pipeline.beautifier import apply_coordinate_edits
from kicad.pipeline.final_circuit_builder import build_final_test_circuits, clean_prompt, placer_ready_circuit
from kicad.pipeline.arrangement_decider import decide_arrangement
from kicad.pipeline.placer_pipeline import run_placer_pipeline
from kicad.pipeline.wire_planner import plan_wire_routes


def obstacle_overlap_pairs(obstacles: list[dict[str, object]]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index, left in enumerate(obstacles):
        for right in obstacles[index + 1 :]:
            if (
                float(left["left"]) < float(right["right"])
                and float(left["right"]) > float(right["left"])
                and float(left["top"]) < float(right["bottom"])
                and float(left["bottom"]) > float(right["top"])
            ):
                pairs.append((str(left["owner"]), str(right["owner"])))
    return pairs


class FinalCircuitBuilderTests(unittest.TestCase):
    def test_clean_prompt_is_non_ai_enhancement_record(self) -> None:
        record = clean_prompt("  Make 2 MOSFET outputs with ESP32, I2C OLED, and RS485.  ")
        self.assertEqual(record["schema"], "progeneda-prompt-cleaner/v0.1")
        self.assertIn("esp32", record["detected_domains"])
        self.assertIn("i2c", record["detected_domains"])
        self.assertEqual(record["requested_counts"][0]["quantity"], 2)
        self.assertIn("deterministic_required", record["next_stage_contract"])

    def test_connected_t01_to_t10_compile_to_valid_final_json(self) -> None:
        circuits = build_final_test_circuits()
        self.assertEqual(len(circuits), 10)
        self.assertEqual(circuits[-1]["circuit_id"], "T10")
        self.assertEqual(len(circuits[-1]["components"]), 190)
        self.assertGreaterEqual(len(circuits[-1]["nets"]), 150)
        for circuit in circuits:
            with self.subTest(cid=circuit["circuit_id"]):
                self.assertEqual(circuit["schema_version"], "progen-kicad-circuit-ir/v1")
                self.assertEqual(circuit["validation"]["status"], "pass")
                self.assertEqual(circuit["validation"]["errors"], [])
                self.assertEqual(circuit["validation"]["warnings"], [])
                self.assertTrue(all(component["pins"] for component in circuit["components"]))

    def test_final_json_drives_arrangement_beautifier_and_wire_planner(self) -> None:
        for circuit in build_final_test_circuits():
            with self.subTest(cid=circuit["circuit_id"]):
                ctx = run_placer_pipeline(placer_ready_circuit(circuit), write_trace=False)
                placement = ctx.placement_plan.as_dict()
                coordinate_plan = decide_arrangement(placement, circuit)
                beautified = apply_coordinate_edits(placement, coordinate_plan)
                wire_plan = plan_wire_routes(
                    beautified,
                    circuit,
                    config={"grid": 5.08, "wire_spacing": 5.08, "max_astar_expansions": 1_500.0, "max_wired_routes": 180.0},
                )
                self.assertEqual(obstacle_overlap_pairs(beautified["obstacles"]), [])
                self.assertGreater(wire_plan["metrics"]["net_count"], 0)
                self.assertGreater(wire_plan["metrics"]["wired_route_count"], 0)


if __name__ == "__main__":
    unittest.main()
