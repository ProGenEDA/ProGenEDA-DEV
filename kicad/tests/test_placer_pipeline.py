from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from kicad.automation.generate_practical_placer_examples import CIRCUITS, build_circuit, build_count_circuit, suite_specs
from kicad.generator.kicad_json_to_project import plan_placement
from kicad.pipeline.kicad_symbol_library import KiCadSymbolLibrary
from kicad.pipeline.placement_catalog import resolve_placement_spec
from kicad.pipeline.arrangement_decider import extract_connection_nets
from kicad.pipeline import (
    PipelineError,
    apply_coordinate_edits,
    decide_arrangement,
    place_terminals,
    plan_wire_routes,
    plan_wiring,
    run_placer_pipeline,
    validate_placement_input,
)


PROTEUS_STYLE_COMPONENT_KINDS = (
    "GROUND",
    "VDC",
    "VSOURCE",
    "CSOURCE",
    "VSIN",
    "VPULSE",
    "RES",
    "POT-HG",
    "CAP",
    "CAP-ELEC",
    "REALIND",
    "DIODE",
    "1N4007",
    "1N4148",
    "1N60",
    "BZX55C5",
    "BZX79C5",
    "LED",
    "NPN",
    "PNP",
    "NMOS",
    "2N7000",
    "BS170",
    "OPAMP",
    "LM741",
    "NE555",
    "CD4007",
    "LM317",
    "TRANSFORMER",
    "BRIDGE RECTIFIER",
    "FUSE",
    "SWITCH",
    "TERMINAL",
    "7SEGCOMA",
    "7SEGCOMK",
    "4027",
    "4511",
    "7447",
    "7490",
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC32",
    "74HC74",
    "74HC76",
    "74HC85",
    "74HC86",
    "74HC151",
    "74HC157",
    "74HC160",
    "74HC174",
    "74HC192",
    "74HC266",
    "74HC283",
)


def vdc_resistor() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": "vdc_resistor_placer", "title": "VDC resistor placement"},
        "components": [
            {"id": "V1", "kind": "VDC", "value": "10", "pins": {"1": "VIN", "2": "GND"}},
            {"id": "R1", "kind": "R", "value": "1k", "pins": {"1": "VIN", "2": "GND"}},
            {"id": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {"VIN": "input", "GND": "return"},
    }


def vdc_resistor_led() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": "vdc_resistor_led", "title": "VDC resistor LED wiring"},
        "components": [
            {"id": "V1", "kind": "VDC", "value": "5V", "pins": {"1": "SRC", "2": "GND"}},
            {"id": "R1", "kind": "R", "value": "220", "pins": {"1": "SRC", "2": "LED_A"}},
            {"id": "D1", "kind": "LED", "value": "LED", "pins": {"1": "LED_A", "2": "GND"}},
            {"id": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {"SRC": "source signal", "LED_A": "series node", "GND": "return"},
    }


def segment_crosses_body(segment: dict[str, object], body: dict[str, float]) -> bool:
    start = segment["start"]  # type: ignore[index]
    end = segment["end"]  # type: ignore[index]
    sx, sy = float(start[0]), float(start[1])  # type: ignore[index]
    ex, ey = float(end[0]), float(end[1])  # type: ignore[index]
    if sx == ex:
        low, high = sorted((sy, ey))
        return body["left"] < sx < body["right"] and low < body["bottom"] and high > body["top"]
    if sy == ey:
        low, high = sorted((sx, ex))
        return body["top"] < sy < body["bottom"] and low < body["right"] and high > body["left"]
    return True


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


class PlacerPipelineTests(unittest.TestCase):
    def test_connection_net_extractor_accepts_dot_pin_endpoint_notation(self) -> None:
        circuit = {
            "components": [{"id": "U1", "kind": "IC", "pins": {"A": "SIG"}}],
            "nets": {"SIG": ["U1.A"]},
        }
        nets = extract_connection_nets(circuit)
        self.assertEqual([(endpoint.ref, endpoint.pin) for endpoint in nets["SIG"]], [("U1", "A")])

    def test_plan_placement_is_deterministic_and_does_not_route(self) -> None:
        first = plan_placement(vdc_resistor()).as_dict()
        second = plan_placement(vdc_resistor()).as_dict()
        self.assertEqual(first, second)
        self.assertEqual(set(first), {"components", "obstacles"})
        self.assertLess(first["components"]["V1"]["at"][0], first["components"]["R1"]["at"][0])

    def test_placer_pipeline_writes_placement_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            ctx = run_placer_pipeline(vdc_resistor(), out_dir=out_dir)
            self.assertEqual(ctx.pipeline_summary()["schema"], "progen-kicad-placer-pipeline/v0.1")
            self.assertEqual(
                [row["stage"] for row in ctx.trace_dict()],
                ["placement_input_validator", "component_placer", "placement_validator"],
            )
            placement = json.loads((out_dir / "placement.json").read_text(encoding="utf-8"))
            trace = json.loads((out_dir / "placement_trace.json").read_text(encoding="utf-8"))
            self.assertEqual(sorted(placement["components"]), ["G1", "R1", "V1"])
            self.assertIs(trace["ok"], True)

    def test_manual_position_is_preserved(self) -> None:
        circuit = vdc_resistor()
        circuit["components"][1]["at"] = [100, 80]  # type: ignore[index]
        ctx = run_placer_pipeline(circuit, write_trace=False)
        placement = ctx.placement_plan.as_dict()
        self.assertEqual(placement["components"]["R1"]["at"], [100.0, 80.0])
        self.assertIs(placement["components"]["R1"]["manual"], True)

    def test_input_validator_uses_source_backed_pin_specs(self) -> None:
        circuit = vdc_resistor()
        circuit["components"][1]["pins"] = {"99": "VIN"}  # type: ignore[index]
        report = validate_placement_input(circuit)
        self.assertIs(report["valid"], False)
        self.assertIn("source-backed spec", report["errors"][0])
        with self.assertRaises(PipelineError):
            run_placer_pipeline(circuit, write_trace=False)

    def test_component_only_named_practical_circuit_places_without_pins(self) -> None:
        cid, title, components = CIRCUITS[0]
        circuit = build_circuit(cid, title, components)
        self.assertEqual(circuit["schema_version"], "progen-kicad-placer-ir/v0.2")
        self.assertEqual(circuit["compatible_schema"], "progen-kicad-circuit-ir/v1")
        self.assertEqual(circuit["nets"], {})
        self.assertEqual(circuit["project"]["analysis"], [])  # type: ignore[index]
        self.assertTrue(all("value" in item and "name" not in item and "pins" not in item for item in circuit["components"]))  # type: ignore[index]
        report = validate_placement_input(circuit)
        self.assertIs(report["valid"], True)
        ctx = run_placer_pipeline(circuit, write_trace=False)
        placement = ctx.placement_plan.as_dict()
        self.assertEqual(len(placement["components"]), 5)
        self.assertEqual(placement["components"]["X1"]["name"], "Arduino Nano")
        self.assertEqual(placement["components"]["X5"]["kind"], "USB_C_CONNECTOR")

    def test_component_only_placer_writes_openable_kicad_project(self) -> None:
        cid, title, components = CIRCUITS[0]
        circuit = build_circuit(cid, title, components)
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            run_placer_pipeline(circuit, out_dir=out_dir)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue((out_dir / manifest["open_this"]).exists())
            self.assertTrue((out_dir / manifest["schematic_file"]).exists())
            self.assertEqual(manifest["component_count"], 5)
            self.assertEqual(manifest["static_checks"]["symbol_instances"], 5)
            self.assertTrue(manifest["static_checks"]["ok"])
            schematic = (out_dir / manifest["schematic_file"]).read_text(encoding="utf-8")
            self.assertNotIn("ProgenPlace:", schematic)
            self.assertNotIn("(extends ", schematic)
            for lib_id in (
                "MCU_Module:Arduino_Nano_v3.x",
                "Device:LED",
                "Device:R",
                "Switch:SW_Push",
                "Connector:USB_C_Receptacle_USB2.0_16P",
            ):
                self.assertIn(f'(lib_id "{lib_id}")', schematic)
                self.assertIn(f'(symbol "{lib_id}"', schematic)
            self.assertEqual(
                sorted(manifest["lib_ids"]),
                [
                    "Connector:USB_C_Receptacle_USB2.0_16P",
                    "Device:LED",
                    "Device:R",
                    "MCU_Module:Arduino_Nano_v3.x",
                    "Switch:SW_Push",
                ],
            )

    def test_generated_project_folder_is_immutable(self) -> None:
        cid, title, components = CIRCUITS[0]
        circuit = build_circuit(cid, title, components)
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir) / "generated"
            run_placer_pipeline(circuit, out_dir=out_dir)
            with self.assertRaises(FileExistsError):
                run_placer_pipeline(circuit, out_dir=out_dir)

    def test_c11_spacing_regression_keeps_usb_and_protection_ic_apart(self) -> None:
        circuits = {cid: (title, components) for cid, title, components in CIRCUITS}
        title, components = circuits["C11"]
        ctx = run_placer_pipeline(build_circuit("C11", title, components), write_trace=False)
        placement = ctx.placement_plan.as_dict()["components"]
        usb = placement["X4"]["at"]
        protection = placement["X5"]["at"]
        self.assertGreater(abs(usb[0] - protection[0]) + abs(usb[1] - protection[1]), 100.0)

    def test_derived_and_multi_unit_symbols_are_self_contained(self) -> None:
        cases = {
            "C09": ("LM358_", '(symbol (lib_id "Amplifier_Operational:LM358")', 7),
            "C20": ("ACS712xLCTR-20A_", '(symbol (lib_id "Comparator:LM393")', 7),
        }
        circuits = {cid: (title, components) for cid, title, components in CIRCUITS}
        with tempfile.TemporaryDirectory() as temp_dir:
            for cid, (nested_symbol_prefix, multi_unit_lib, expected_instances) in cases.items():
                title, components = circuits[cid]
                out_dir = Path(temp_dir) / cid
                run_placer_pipeline(build_circuit(cid, title, components), out_dir=out_dir)
                manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
                schematic = (out_dir / manifest["schematic_file"]).read_text(encoding="utf-8")
                self.assertNotIn("(extends ", schematic)
                self.assertIn(nested_symbol_prefix, schematic)
                self.assertEqual(manifest["symbol_instance_count"], expected_instances)
                self.assertIn(multi_unit_lib, schematic)
                self.assertIn("(unit 2)", schematic)
                self.assertIn("(unit 3)", schematic)

    def test_practical_pack_contains_twenty_circuits_and_one_hundred_components(self) -> None:
        self.assertEqual(len(CIRCUITS), 20)
        self.assertEqual(sum(len(components) for _cid, _title, components in CIRCUITS), 100)
        cid, title, components = CIRCUITS[0]
        circuit = build_circuit(cid, title, components)
        self.assertEqual(set(circuit), {"schema_version", "compatible_schema", "pipeline_stage", "project", "components", "nets", "constraints", "notes"})

    def test_stress_suite_contains_requested_limit_tests(self) -> None:
        stress = suite_specs("stress")
        self.assertEqual(len(stress), 22)
        totals = {cid: sum(count for _kind, _value, count in components) for cid, _title, _purpose, components in stress}
        self.assertEqual(totals["T01"], 18)
        self.assertEqual(totals["T10"], 186)
        self.assertEqual(totals["LIMA"], 250)
        self.assertEqual(totals["LIMB"], 240)
        self.assertEqual(totals["LIMC"], 240)
        self.assertEqual(totals["LIMD"], 180)
        self.assertEqual(totals["LIME400"], 400)
        self.assertEqual(sum(totals.values()), 2747)

    def test_arrangement_decider_emits_topology_coordinate_plan(self) -> None:
        circuit = vdc_resistor_led()
        ctx = run_placer_pipeline(circuit, write_trace=False)
        arrangement = decide_arrangement(ctx.placement_plan.as_dict(), circuit)
        self.assertEqual(arrangement["schema"], "progen-kicad-arrangement-decision/v0.1")
        self.assertEqual(arrangement["algorithm"]["primary"], "sugiyama_layered_layout")
        self.assertGreaterEqual(len(arrangement["coordinate_edits"]), 1)
        planned = arrangement["components"]
        self.assertLessEqual(planned["V1"]["planned_at"][0], planned["R1"]["planned_at"][0])
        self.assertLessEqual(planned["R1"]["planned_at"][0], planned["D1"]["planned_at"][0])
        self.assertGreater(planned["G1"]["planned_at"][1], planned["R1"]["planned_at"][1])

    def test_beautifier_only_applies_coordinate_edits(self) -> None:
        circuit = vdc_resistor_led()
        ctx = run_placer_pipeline(circuit, write_trace=False)
        placement = ctx.placement_plan.as_dict()
        arrangement = decide_arrangement(placement, circuit)
        beautified = apply_coordinate_edits(placement, arrangement)
        self.assertEqual(beautified["schema"], "progen-kicad-beautified-placement/v0.1")
        edit_by_ref = {edit["ref"]: edit for edit in arrangement["coordinate_edits"]}
        for ref, edit in edit_by_ref.items():
            self.assertEqual(beautified["components"][ref]["at"], edit["to"])
        old_obstacles = {item["owner"]: item for item in placement["obstacles"]}
        new_obstacles = {item["owner"]: item for item in beautified["obstacles"]}
        for ref, edit in edit_by_ref.items():
            old_width = old_obstacles[ref]["right"] - old_obstacles[ref]["left"]
            new_width = new_obstacles[ref]["right"] - new_obstacles[ref]["left"]
            self.assertAlmostEqual(old_width, new_width)

    def test_wire_planner_emits_coordinate_and_lane_astar_wire_json(self) -> None:
        circuit = vdc_resistor_led()
        ctx = run_placer_pipeline(circuit, write_trace=False)
        planned = plan_wiring(ctx.placement_plan.as_dict(), circuit)
        self.assertEqual(planned["schema"], "progen-kicad-wire-planner-output/v0.1")
        self.assertEqual(planned["coordinate_plan"]["schema"], "progen-kicad-arrangement-decision/v0.1")
        self.assertEqual(planned["component_motion_policy"]["phase"], "before_route_search")
        expected_routing_placement = apply_coordinate_edits(ctx.placement_plan.as_dict(), planned["coordinate_plan"])
        self.assertEqual(planned["routing_placement"]["components"], expected_routing_placement["components"])
        self.assertGreater(len(planned["routing_placement"].get("applied_edits", [])), 0)
        wire_plan = planned["wire_plan"]
        self.assertEqual(wire_plan["schema"], "progen-kicad-wire-plan/v0.1")
        self.assertEqual(wire_plan["algorithm"]["router"], "lane_candidates_then_grid_astar")
        self.assertEqual(wire_plan["routing_mode"], "wire")
        self.assertNotEqual(wire_plan["nets"]["GND"]["strategy"], "local_labels")
        self.assertGreaterEqual(wire_plan["metrics"]["wired_route_count"], 2)
        self.assertIn("wire-wire crossings are allowed", wire_plan["algorithm"]["wire_collision_policy"])
        bodies = {item["owner"]: item for item in planned["routing_placement"]["obstacles"]}
        for route in wire_plan["routes"]:
            for segment in route["segments"]:
                self.assertIn(segment["direction"], {"up", "down", "left", "right"})
                for ref, body in bodies.items():
                    if ref in {route["from"]["ref"], route["to"]["ref"]}:
                        continue
                    self.assertFalse(segment_crosses_body(segment, body), f"{route['net']} crosses {ref}")

    def test_terminal_placer_emits_label_plan_independently_from_wire_mode(self) -> None:
        circuit = vdc_resistor_led()
        ctx = run_placer_pipeline(circuit, write_trace=False)
        terminal_plan = place_terminals(ctx.placement_plan.as_dict(), circuit)
        self.assertEqual(terminal_plan["schema"], "progen-kicad-terminal-plan/v0.1")
        self.assertEqual(terminal_plan["routing_mode"], "terminal")
        self.assertEqual(terminal_plan["nets"]["GND"]["strategy"], "local_labels")

    def test_wire_planner_prefers_exact_pin_points_when_provided(self) -> None:
        circuit = {
            "components": [
                {"id": "U1", "kind": "IC", "pins": {"A": "SIG"}},
                {"id": "U2", "kind": "IC", "pins": {"B": "SIG"}},
            ]
        }
        placement = {
            "components": {
                "U1": {"at": [10.0, 20.0], "width": 10.0, "height": 8.0},
                "U2": {"at": [50.0, 20.0], "width": 10.0, "height": 8.0},
            },
            "obstacles": [
                {"owner": "U1::body1", "component_ref": "U1", "left": 5.0, "top": 16.0, "right": 15.0, "bottom": 24.0},
                {"owner": "U2::body1", "component_ref": "U2", "left": 45.0, "top": 16.0, "right": 55.0, "bottom": 24.0},
            ],
            "pin_points": {
                "U1": {"A": {"point": [16.0, 20.0], "source": "unit_test_pin"}},
                "U2": {"B": {"point": [44.0, 20.0], "source": "unit_test_pin"}},
            },
        }
        wire_plan = plan_wire_routes(placement, circuit, config={"grid": 1.0, "clearance": 1.0})
        route = wire_plan["routes"][0]
        self.assertEqual(route["from"]["point"], [16.0, 20.0])
        self.assertEqual(route["to"]["point"], [44.0, 20.0])
        self.assertTrue(route["from"]["exact"])
        self.assertEqual(wire_plan["nets"]["SIG"]["endpoints"][0]["source"], "unit_test_pin")

    def test_arrangement_and_beautifier_handle_t01_to_t10_stress_without_overlaps(self) -> None:
        stress = [spec for spec in suite_specs("stress") if spec[0].startswith("T")]
        self.assertEqual(len(stress), 10)
        for cid, title, purpose, components in stress:
            with self.subTest(cid=cid):
                circuit = build_count_circuit(cid, title, purpose, components)
                ctx = run_placer_pipeline(circuit, write_trace=False)
                placement = ctx.placement_plan.as_dict()
                arrangement = decide_arrangement(placement, circuit)
                beautified = apply_coordinate_edits(placement, arrangement)
                wire_plan = plan_wiring(placement, circuit)["wire_plan"]
                self.assertEqual(len(beautified["components"]), len(placement["components"]))
                self.assertEqual(obstacle_overlap_pairs(beautified["obstacles"]), [])
                self.assertEqual(wire_plan["metrics"]["net_count"], 0)
                self.assertEqual(wire_plan["metrics"]["wired_route_count"], 0)

    def test_all_practical_pack_circuits_place_five_components_without_overlaps(self) -> None:
        for cid, title, components in CIRCUITS:
            with self.subTest(cid=cid):
                circuit = build_circuit(cid, title, components)
                ctx = run_placer_pipeline(circuit, write_trace=False)
                placement = ctx.placement_plan.as_dict()
                self.assertEqual(len(placement["components"]), 5)
                self.assertEqual(ctx.placement_report["overlaps"], [])
                self.assertTrue(ctx.pipeline_summary()["ok"])

    def test_proteus_style_component_kinds_resolve_to_real_kicad_symbols(self) -> None:
        symbol_library = KiCadSymbolLibrary(prefer_subset=False)
        missing: list[str] = []
        for kind in PROTEUS_STYLE_COMPONENT_KINDS:
            spec = resolve_placement_spec(kind)
            if spec is None or spec.lib_id is None:
                missing.append(kind)
                continue
            symbol = symbol_library.flattened(spec.lib_id)
            self.assertNotIn("ProgenPlace:", symbol.text)
            self.assertNotIn("(extends ", symbol.text)
            self.assertGreater(len(symbol.pin_numbers), 0, kind)
        self.assertEqual(missing, [])

    def test_proteus_style_component_kind_pack_writes_openable_project(self) -> None:
        circuit = {
            "schema_version": "progen-kicad-placer-ir/v0.2",
            "compatible_schema": "progen-kicad-circuit-ir/v1",
            "pipeline_stage": "component_placement",
            "project": {
                "name": "proteus_style_component_kind_smoke",
                "title": "Proteus-style component kind smoke test",
                "analysis": ["requested Proteus-style aliases mapped to real KiCad symbols"],
            },
            "components": [
                {"id": f"X{index:02d}", "kind": kind, "value": kind}
                for index, kind in enumerate(PROTEUS_STYLE_COMPONENT_KINDS, 1)
            ],
            "nets": {},
            "constraints": {},
            "notes": ["placement-only smoke circuit for expanded supported component aliases"],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            run_placer_pipeline(circuit, out_dir=out_dir)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
            schematic = (out_dir / manifest["schematic_file"]).read_text(encoding="utf-8")
            self.assertTrue(manifest["static_checks"]["ok"])
            self.assertEqual(manifest["component_count"], len(PROTEUS_STYLE_COMPONENT_KINDS))
            self.assertGreaterEqual(manifest["symbol_instance_count"], len(PROTEUS_STYLE_COMPONENT_KINDS))
            self.assertNotIn("ProgenPlace:", schematic)
            self.assertNotIn("(extends ", schematic)
            self.assertIn('(lib_id "Timer:NE555P")', schematic)
            self.assertIn('(lib_id "4xxx_IEEE:4511")', schematic)
            self.assertIn('(lib_id "74xx:74LS08")', schematic)
            self.assertIn('(lib_id "4xxx:4077")', schematic)


if __name__ == "__main__":
    unittest.main()
