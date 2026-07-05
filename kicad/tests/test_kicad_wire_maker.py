from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kicad.pipeline.arrangement_decider import decide_arrangement
from kicad.pipeline.beautifier import apply_coordinate_edits
from kicad.pipeline.final_circuit_builder import (
    STAGE_REPORT_WIRE_CONFIG,
    build_final_test_circuits,
    build_proteus_alias_mixed_circuits,
    build_proteus_alias_routed_circuits,
    placer_ready_circuit,
)
from kicad.pipeline.kicad_symbol_library import KiCadSymbolLibrary
from kicad.pipeline.kicad_wire_maker import _pin_geometries, _resolve_pin_geometry, generate_wired_projects_from_final_json, make_kicad_wires
from kicad.pipeline.terminal_placer import place_terminals
from kicad.pipeline.placer_pipeline import run_placer_pipeline
from kicad.pipeline.wire_planner import plan_wire_routes


class KiCadWireMakerTests(unittest.TestCase):
    def test_exact_pin_aliases_preserve_case_and_active_low_identity(self) -> None:
        library = KiCadSymbolLibrary()
        cases = {
            ("MICRO_SD_SOCKET", "Connector:Micro_SD_Card_Det1"): {"CS": "2", "CD": "9"},
            ("4511", "4xxx_IEEE:4511"): {"A": "7", "a": "13"},
            ("74HC151", "74xx:74LS151"): {"Y": "5", "/Y": "6"},
            ("74HC174", "74xx:74LS174"): {"D5": "13", "D6": "14", "Q5": "12", "Q6": "15"},
        }
        for (kind, lib_id), expected in cases.items():
            geometries = _pin_geometries(library.load(lib_id).text)
            with self.subTest(kind=kind):
                for pin, number in expected.items():
                    geometry, status = _resolve_pin_geometry(ref="U1", kind=kind, pin=pin, geometries=geometries)
                    self.assertEqual(status, "resolved")
                    self.assertIsNotNone(geometry)
                    self.assertEqual(geometry.number, number, pin)

    def test_wire_maker_strict_wire_mode_emits_no_terminal_labels(self) -> None:
        circuit = build_final_test_circuits()[0]
        ctx = run_placer_pipeline(placer_ready_circuit(circuit), write_trace=False)
        placement = ctx.placement_plan
        placement_dict = placement.as_dict()
        beautified = apply_coordinate_edits(placement_dict, decide_arrangement(placement_dict, circuit))
        wire_plan = plan_wire_routes(beautified, circuit, config=STAGE_REPORT_WIRE_CONFIG)
        result = make_kicad_wires(circuit, placement, wire_plan)
        self.assertIn("(wire (pts", result.schematic_objects)
        self.assertNotIn("(label \"", result.schematic_objects)
        self.assertEqual(result.report["routing_mode"], "wire")
        self.assertGreater(result.report["wire_object_count"], 0)
        self.assertGreater(result.report["pin_resolved_count"], 0)

    def test_terminal_placer_owns_local_label_behavior(self) -> None:
        circuit = build_final_test_circuits()[0]
        ctx = run_placer_pipeline(placer_ready_circuit(circuit), write_trace=False)
        placement = ctx.placement_plan
        placement_dict = placement.as_dict()
        terminal_plan = place_terminals(placement_dict, circuit, config=STAGE_REPORT_WIRE_CONFIG)
        result = make_kicad_wires(circuit, placement, terminal_plan)
        self.assertEqual(terminal_plan["stage"], "terminal_placer")
        self.assertIn("(label \"GND\"", result.schematic_objects)
        self.assertEqual(result.report["routing_mode"], "terminal")
        self.assertTrue(result.report["strict_wire_ok"])

    def test_wire_mode_terminal_policy_labels_declared_power_ground_nets(self) -> None:
        circuit = build_final_test_circuits()[0]
        ctx = run_placer_pipeline(placer_ready_circuit(circuit), write_trace=False)
        placement = ctx.placement_plan
        placement_dict = placement.as_dict()
        beautified = apply_coordinate_edits(placement_dict, decide_arrangement(placement_dict, circuit))
        cfg = dict(STAGE_REPORT_WIRE_CONFIG)
        cfg["wire_mode_terminal_power_ground"] = 1.0
        wire_plan = plan_wire_routes(beautified, circuit, config=cfg)
        self.assertEqual(wire_plan["routing_mode"], "wire")
        self.assertTrue(wire_plan["wire_mode_terminal_policy"]["enabled"])
        self.assertIn("GND", wire_plan["wire_mode_terminal_policy"]["terminal_nets"])
        self.assertEqual(wire_plan["nets"]["GND"]["strategy"], "wire_mode_terminal_label")
        result = make_kicad_wires(circuit, placement, wire_plan)
        self.assertIn("(label \"GND\"", result.schematic_objects)
        self.assertEqual(result.report["forbidden_label_strategy_count"], 0)
        self.assertEqual(result.report["wire_mode_terminal_label_count"], len(wire_plan["wire_mode_terminal_policy"]["terminal_nets"]))
        self.assertNotIn("wire_mode_forbids_terminal_label_strategy", json.dumps(result.report["strict_wire_validator"]))

    def test_power_terminal_policy_removes_routed_alias_partial_and_unroutable_nets(self) -> None:
        cfg = dict(STAGE_REPORT_WIRE_CONFIG)
        cfg["wire_mode_terminal_power_ground"] = 1.0
        total_terminal_endpoints = 0
        for circuit in build_proteus_alias_routed_circuits():
            ctx = run_placer_pipeline(placer_ready_circuit(circuit), write_trace=False)
            placement_dict = ctx.placement_plan.as_dict()
            beautified = apply_coordinate_edits(placement_dict, decide_arrangement(placement_dict, circuit))
            wire_plan = plan_wire_routes(beautified, circuit, config=cfg)
            self.assertEqual(wire_plan["metrics"]["unroutable_net_count"], 0, circuit["circuit_id"])
            self.assertEqual(wire_plan["metrics"]["partial_wire_net_count"], 0, circuit["circuit_id"])
            total_terminal_endpoints += int(wire_plan["metrics"]["wire_mode_terminal_endpoint_count"])
        self.assertEqual(total_terminal_endpoints, 59)

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
            self.assertTrue(summary["all_component_body_overlap_ok"])
            self.assertEqual(summary["total_component_body_overlaps"], 0)
            self.assertGreater(summary["total_wire_objects"], 0)
            for result in summary["results"]:
                schematic = root / "wired_run" / result["schematic_file"]
                self.assertTrue((root / "wired_run" / result["open_this"]).exists())
                self.assertIn("wires, labels, and junctions are generated", schematic.read_text(encoding="utf-8"))
                self.assertGreater(result["wire_object_count"], 0)

    def test_generate_terminal_projects_from_final_json_uses_terminal_placer_and_passes_netlist(self) -> None:
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
                label="unit_test_terminal",
                run_dir=root / "terminal_run",
                routing_mode="terminal",
            )
            self.assertEqual(summary["project_count"], 2)
            self.assertTrue(summary["all_static_checks_ok"])
            self.assertTrue(summary["all_component_body_overlap_ok"])
            self.assertEqual(summary["total_component_body_overlaps"], 0)
            self.assertTrue(summary["all_local_netlist_ok"])
            self.assertEqual(summary["total_local_netlist_failed_nets"], 0)
            self.assertGreater(summary["total_labels"], 0)
            for result in summary["results"]:
                project_dir = root / "terminal_run" / result["project_dir"]
                wire_plan = next((root / "terminal_run" / "wire_plans").glob(f"{result['circuit_id']}*_wire_plan.json"))
                self.assertEqual(json.loads(wire_plan.read_text(encoding="utf-8"))["stage"], "terminal_placer")
                manifest = json.loads((project_dir / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["wire_maker"]["routing_mode"], "terminal")
                self.assertTrue(manifest["local_netlist_validation"]["ok"])

    def test_proteus_alias_mixed_wired_projects_obey_geometry_rules(self) -> None:
        circuits = build_proteus_alias_mixed_circuits()[:2]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "final_json"
            source.mkdir()
            for circuit in circuits:
                (source / f"{circuit['circuit_id']}.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
            summary = generate_wired_projects_from_final_json(
                source,
                examples_root=root,
                label="unit_test_proteus_alias_wired",
                run_dir=root / "wired_run",
                routing_mode="combination",
            )
            self.assertEqual(summary["project_count"], 2)
            self.assertTrue(summary["all_static_checks_ok"])
            self.assertTrue(summary["all_component_body_overlap_ok"])
            self.assertEqual(summary["total_component_body_overlaps"], 0)
            self.assertTrue(summary["all_geometry_ok"])
            self.assertEqual(summary["total_geometry_violations"], 0)
            self.assertGreater(summary["total_labels"], 0)
            self.assertGreater(summary["total_wire_objects"], 0)
            for result in summary["results"]:
                self.assertTrue(result["geometry_ok"])
                self.assertEqual(result["geometry_violation_count"], 0)

    def test_proteus_alias_routed_projects_have_real_wires_and_clean_geometry(self) -> None:
        circuits = build_proteus_alias_routed_circuits()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "final_json"
            source.mkdir()
            for circuit in circuits:
                (source / f"{circuit['circuit_id']}.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
            summary = generate_wired_projects_from_final_json(
                source,
                examples_root=root,
                label="unit_test_proteus_alias_routed",
                run_dir=root / "wired_run",
                routing_mode="combination",
            )
            self.assertEqual(summary["project_count"], 3)
            self.assertTrue(summary["all_static_checks_ok"])
            self.assertTrue(summary["all_component_body_overlap_ok"])
            self.assertEqual(summary["total_component_body_overlaps"], 0)
            self.assertTrue(summary["all_geometry_ok"])
            self.assertEqual(summary["total_geometry_violations"], 0)
            self.assertGreater(summary["total_labels"], 0)
            self.assertGreaterEqual(summary["total_wire_objects"], 45)
            for result in summary["results"]:
                self.assertTrue(result["geometry_ok"])
                self.assertEqual(result["geometry_violation_count"], 0)
                self.assertGreater(result["wire_object_count"], 0)

    def test_strict_wire_mode_reports_unrouted_nets_without_terminal_labels(self) -> None:
        circuits = build_proteus_alias_routed_circuits()[:1]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "final_json"
            source.mkdir()
            for circuit in circuits:
                (source / f"{circuit['circuit_id']}.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
            summary = generate_wired_projects_from_final_json(
                source,
                examples_root=root,
                label="unit_test_strict_wire",
                run_dir=root / "wired_run",
                routing_mode="wire",
            )
            self.assertEqual(summary["project_count"], 1)
            self.assertEqual(summary["total_labels"], 0)
            self.assertGreater(summary["total_wire_objects"], 0)
            self.assertEqual(summary["total_unrouted_nets"] + summary["total_partial_wire_nets"], 0)
            self.assertTrue(summary["all_geometry_ok"])
            self.assertTrue(summary["all_strict_wire_ok"])


if __name__ == "__main__":
    unittest.main()
