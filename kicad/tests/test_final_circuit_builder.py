from __future__ import annotations

import unittest
import tempfile
import json
from pathlib import Path

from kicad.pipeline.beautifier import apply_coordinate_edits
from kicad.pipeline.final_circuit_builder import (
    MAIN_JSON_CATALOG_100_SUITE,
    PROTEUS_ALIAS_MIXED_SUITE,
    PROTEUS_ALIAS_ROUTED_SUITE,
    available_final_circuit_suites,
    build_final_circuits,
    build_final_circuits_from_node_spec_text,
    build_final_test_circuits,
    build_proteus_alias_mixed_circuits,
    build_proteus_alias_routed_circuits,
    generate_final_json_run_from_node_spec_text,
    clean_prompt,
    generate_projects_from_final_json,
    placer_ready_circuit,
    raw_specs_from_node_spec_text,
)
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
                self.assertEqual(circuit["routing"]["mode"], "wire")
                self.assertEqual(circuit["validation"]["status"], "pass")
                self.assertEqual(circuit["validation"]["errors"], [])
                self.assertEqual(circuit["validation"]["warnings"], [])
                self.assertTrue(all(component["pins"] for component in circuit["components"]))

    def test_proteus_alias_mixed_suite_compiles_old_and_new_components(self) -> None:
        self.assertIn(PROTEUS_ALIAS_MIXED_SUITE, available_final_circuit_suites())
        circuits = build_proteus_alias_mixed_circuits()
        self.assertEqual([circuit["circuit_id"] for circuit in circuits], ["M01", "M02", "M03"])
        self.assertEqual(build_final_circuits(PROTEUS_ALIAS_MIXED_SUITE), circuits)

        kinds = {str(component["kind"]) for circuit in circuits for component in circuit["components"]}
        for expected in (
            "GROUND",
            "VDC",
            "VSOURCE",
            "CSOURCE",
            "VSIN",
            "VPULSE",
            "POT-HG",
            "BRIDGE RECTIFIER",
            "7SEGCOMA",
            "74HC283",
            "ARDUINO_NANO",
            "ESP32_WROOM",
            "BME280",
            "SSD1306_OLED",
            "MAX485",
        ):
            self.assertIn(expected, kinds)

        for circuit in circuits:
            with self.subTest(cid=circuit["circuit_id"]):
                self.assertEqual(circuit["validation"]["status"], "pass")
                self.assertEqual(circuit["validation"]["errors"], [])
                self.assertEqual(circuit["validation"]["warnings"], [])
                self.assertTrue(all(component["pins"] for component in circuit["components"]))

    def test_proteus_alias_routed_suite_compiles_wire_friendly_circuits(self) -> None:
        self.assertIn(PROTEUS_ALIAS_ROUTED_SUITE, available_final_circuit_suites())
        circuits = build_proteus_alias_routed_circuits()
        self.assertEqual([circuit["circuit_id"] for circuit in circuits], ["R01", "R02", "R03"])
        self.assertEqual(build_final_circuits(PROTEUS_ALIAS_ROUTED_SUITE), circuits)

        kinds = {str(component["kind"]) for circuit in circuits for component in circuit["components"]}
        for expected in ("VDC", "1N4007", "LM317", "74HC00", "4511", "ARDUINO_NANO", "ESP32_WROOM", "MAX485"):
            self.assertIn(expected, kinds)

        for circuit in circuits:
            with self.subTest(cid=circuit["circuit_id"]):
                self.assertEqual(circuit["validation"]["status"], "pass")
                self.assertEqual(circuit["validation"]["errors"], [])
                self.assertEqual(circuit["validation"]["warnings"], [])
                self.assertTrue(all(component["pins"] for component in circuit["components"]))

    def test_main_json_catalog_100_compiles_to_locked_combination_inputs(self) -> None:
        self.assertIn(MAIN_JSON_CATALOG_100_SUITE, available_final_circuit_suites())
        circuits = build_final_circuits(MAIN_JSON_CATALOG_100_SUITE)
        self.assertEqual(len(circuits), 100)
        self.assertEqual(circuits[0]["circuit_id"], "MJ001")
        self.assertEqual(circuits[-1]["circuit_id"], "MJ100")
        self.assertGreaterEqual(sum(len(circuit["components"]) for circuit in circuits), 8000)
        self.assertGreaterEqual(min(len(circuit["components"]) for circuit in circuits), 40)
        for circuit in circuits:
            with self.subTest(cid=circuit["circuit_id"]):
                self.assertEqual(circuit["main_json_contract"]["schema"], "progeneda-main-json-contract/v1")
                self.assertTrue(circuit["main_json_contract"]["single_generator_input"])
                self.assertFalse(circuit["main_json_contract"]["backend_cli_required"])
                self.assertEqual(circuit["routing"]["mode"], "combination")
                self.assertEqual(circuit["routing"]["terminal_policy"]["high_fanout_threshold"], 6)
                self.assertEqual(circuit["validation"]["status"], "pass")
                self.assertEqual(circuit["validation"]["errors"], [])
                self.assertEqual(len(circuit["expected_netlist"]["nets"]), len(circuit["nets"]))
                self.assertTrue(all(component["pins"] for component in circuit["components"]))

    def test_node_spec_text_compiles_to_valid_final_json(self) -> None:
        text = """
        `NET_*` = same wire/node.

        ```text
        CIRCUIT 01: HEADER BUS SAMPLE
        HEADER_CONNECTOR.P1 -> NET_BUS
        HEADER_CONNECTOR.P13 -> NET_BUS
        R_10K_PULLUP_BUS.1 -> NET_BUS
        R_10K_PULLUP_BUS.2 -> NET_5V
        PWR_5V.+ -> NET_5V
        R_LOAD.1 -> NET_BUS
        R_LOAD.2 -> NET_GND
        GROUND.1 -> NET_GND
        ```
        """
        raw = raw_specs_from_node_spec_text(text, source="unit_test")
        self.assertEqual(len(raw), 1)
        circuits = build_final_circuits_from_node_spec_text(text, source="unit_test")
        circuit = circuits[0]
        self.assertEqual(circuit["circuit_id"], "N01")
        self.assertEqual(circuit["validation"]["status"], "pass")
        self.assertEqual(circuit["validation"]["errors"], [])
        self.assertEqual(circuit["validation"]["warnings"], [])
        self.assertEqual(circuit["nets"]["+5V"], ["R_10K_PULLUP_BUS.2", "PWR_5V.+"])
        self.assertEqual(circuit["nets"]["GND"], ["R_LOAD.2", "GROUND.1"])
        kinds = {component["ref"]: component["kind"] for component in circuit["components"]}
        self.assertEqual(kinds["HEADER_CONNECTOR"], "PROGRAMMING_HEADER")
        self.assertEqual(kinds["R_10K_PULLUP_BUS"], "R_10K_PULLUP")

    def test_node_spec_text_run_writes_immutable_final_json_folder(self) -> None:
        text = """
        CIRCUIT 01: SMALL NODE SPEC
        VDC.1 -> NET_5V
        VDC.2 -> NET_GND
        RES_LOAD.1 -> NET_5V
        RES_LOAD.2 -> NET_GND
        GROUND.1 -> NET_GND
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            summary = generate_final_json_run_from_node_spec_text(
                text,
                examples_root=root,
                label="unit_node_spec",
                run_dir=root / "node_spec_run",
                source="unit_test",
            )
            self.assertEqual(summary["schema"], "progen-kicad-final-json-run/v0.1")
            self.assertEqual(summary["suite"], "node_spec_arrow_text")
            self.assertTrue(summary["all_final_json_valid"])
            self.assertTrue((root / "node_spec_run" / "final_json").is_dir())

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

    def test_final_json_project_run_writes_openable_placement_projects(self) -> None:
        circuits = build_final_test_circuits()[:2]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source_final_json"
            source.mkdir()
            for circuit in circuits:
                (source / f"{circuit['circuit_id']}.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
            summary = generate_projects_from_final_json(
                source,
                examples_root=root,
                label="unit_test_projects",
                run_dir=root / "generated_projects",
            )
            self.assertEqual(summary["schema"], "progen-kicad-final-json-project-run/v0.1")
            self.assertEqual(summary["project_count"], 2)
            self.assertTrue(summary["all_projects_ok"])
            for result in summary["results"]:
                self.assertTrue((root / "generated_projects" / result["open_this"]).exists())
                self.assertEqual(result["mode"], "placement_only")


if __name__ == "__main__":
    unittest.main()
