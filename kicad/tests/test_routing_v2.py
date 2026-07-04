from __future__ import annotations

import json
import sys
import types
import unittest

from kicad.generator.kicad_json_to_project import plan_placement
from kicad.pipeline.catelogues import load_component_catalogue
from kicad.pipeline.routing.python import (
    build_live_routing_state,
    plan_wiring_v2,
    rotate_point,
    rotate_side,
)
from kicad.pipeline.routing.python.routing_config import routing_v2_config
from kicad.pipeline.routing.python.routing_orchestrator import _route_final_states, _try_rust_plan
from kicad.pipeline.wire_planner import _endpoint_points, _wire_config


def simple_vdc_resistor() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": "routing_v2_vdc_resistor"},
        "components": [
            {"id": "V1", "kind": "VDC", "value": "5", "pins": {"1": "VIN", "2": "GND"}},
            {"id": "R1", "kind": "R", "value": "1k", "pins": {"1": "VIN", "2": "GND"}},
            {"id": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {"VIN": ["V1.1", "R1.1"], "GND": ["V1.2", "R1.2", "G1.1"]},
    }


class RoutingV2Tests(unittest.TestCase):
    def test_catalogue_resolves_aliases(self) -> None:
        catalogue = load_component_catalogue()
        self.assertEqual(catalogue.resolve_type_id("74HC595_SHIFT_REGISTER"), "74HC595_DIP16")
        self.assertEqual(catalogue.resolve_type_id("CAP-ELEC"), "Capacitor_Electrolytic")

    def test_rotation_math_matches_refactor_plan(self) -> None:
        self.assertEqual(rotate_point((-10.16, -2.54), 90), (2.54, -10.16))
        self.assertEqual(rotate_point((-10.16, -2.54), 180), (10.16, 2.54))
        self.assertEqual(rotate_side("left", 90), "top")
        self.assertEqual(rotate_side("left", 180), "right")
        self.assertEqual(rotate_side("left", 270), "bottom")

    def test_live_state_recomputes_pin_after_rotation(self) -> None:
        circuit = {
            "components": [{"id": "U1", "kind": "74HC595_SHIFT_REGISTER", "pins": {"SER": "DATA"}}],
            "nets": {"DATA": ["U1.SER"]},
        }
        placement = {"components": {"U1": {"kind": "74HC595_SHIFT_REGISTER", "at": [100.0, 100.0]}}, "obstacles": []}
        state = build_live_routing_state(placement, circuit)
        state.apply_rotation("U1", 90)
        pin = state.components["U1"]["pins"]["SER"]
        self.assertEqual(pin["side"], "top")
        self.assertEqual(pin["point"], [101.6, 88.9])
        self.assertAlmostEqual(state.components["U1"]["body"]["right"] - state.components["U1"]["body"]["left"], 7.62)

    def test_unsupported_multipin_live_state_does_not_keep_generic_two_pin_anchors(self) -> None:
        circuit = {
            "components": [{"id": "U1", "kind": "4511", "pins": {"1": "A", "2": "B", "6": "C", "7": "D"}}],
            "nets": {"A": ["U1.1"], "B": ["U1.2"], "C": ["U1.6"], "D": ["U1.7"]},
        }
        placement = {"components": {"U1": {"kind": "4511", "at": [100.0, 100.0]}}, "obstacles": []}
        state = build_live_routing_state(placement, circuit)
        points = {tuple(pin["point"]) for pin in state.components["U1"]["pins"].values()}
        self.assertEqual(len(points), 4)

    def test_wire_planner_even_side_bucket_pins_use_distinct_grid_lanes(self) -> None:
        circuit = {
            "components": [
                {"id": "U1", "kind": "4511", "pins": {"1": "N1", "2": "N2", "3": "N3", "4": "N4"}},
                {"id": "J1", "kind": "PROGRAMMING_HEADER", "pins": {"1": "N1", "2": "N2", "3": "N3", "4": "N4"}},
            ],
            "nets": {"N1": ["U1.1", "J1.1"], "N2": ["U1.2", "J1.2"], "N3": ["U1.3", "J1.3"], "N4": ["U1.4", "J1.4"]},
        }
        placement = {
            "components": {
                "U1": {"kind": "4511", "at": [100.0, 100.0]},
                "J1": {"kind": "PROGRAMMING_HEADER", "at": [40.0, 100.0]},
            },
            "obstacles": [
                {"owner": "U1", "left": 89.0, "top": 86.0, "right": 111.0, "bottom": 114.0},
                {"owner": "J1", "left": 34.0, "top": 98.5, "right": 46.0, "bottom": 101.5},
            ],
        }
        endpoints = _endpoint_points(placement, circuit, _wire_config({}, circuit))
        u1_points = [tuple(endpoint["point"]) for net in sorted(endpoints) for endpoint in endpoints[net] if endpoint["ref"] == "U1"]
        self.assertEqual(len(set(u1_points)), 4)

    def test_priority_legalization_pushes_lower_priority_blocker(self) -> None:
        circuit = {
            "components": [
                {"id": "R1", "kind": "RES", "pins": {"1": "A", "2": "B"}},
                {"id": "R2", "kind": "RES", "pins": {"1": "C", "2": "D"}},
            ],
            "nets": {"A": ["R1.1"], "B": ["R1.2"], "C": ["R2.1"], "D": ["R2.2"]},
        }
        placement = {
            "components": {
                "R1": {"kind": "RES", "at": [50.0, 50.0]},
                "R2": {"kind": "RES", "at": [50.0, 50.0]},
            },
            "obstacles": [],
        }
        state = build_live_routing_state(placement, circuit)
        state.components["R1"]["priority"] = 100.0
        state.components["R2"]["priority"] = 1.0
        report = state.legalize_after_move("R1")
        self.assertTrue(report["ok"])
        self.assertEqual(state.components["R1"]["at"], [50.8, 50.8])
        self.assertNotEqual(state.components["R2"]["at"], [50.8, 50.8])
        self.assertEqual(state.find_overlaps(), [])

    def test_plan_wiring_v2_keeps_output_contract(self) -> None:
        circuit = simple_vdc_resistor()
        placement = plan_placement(circuit).as_dict()
        planned = plan_wiring_v2(
            placement,
            circuit,
            config={"placement": {"enable_python_live_state_placement": False}},
            wire_config={"max_astar_expansions": 2000.0},
        )
        self.assertEqual(planned["schema"], "progen-kicad-wire-planner-output/v0.2")
        self.assertIn("coordinate_plan", planned)
        self.assertIn("routing_placement", planned)
        self.assertIn("wire_plan", planned)
        self.assertIn("arrangement_selection", planned)
        self.assertIn("validation_report", planned)
        self.assertEqual(planned["validation_report"]["schema"], "progen-routing-validation-report/v0.2")
        self.assertEqual(planned["wire_plan"]["schema"], "progen-kicad-wire-plan/v0.2")
        self.assertTrue(planned["wire_plan"]["algorithm"]["hanan_grid_lanes"])
        self.assertTrue(planned["wire_plan"]["algorithm"]["rectilinear_mst_tree"])

    def test_temp_rust_core_does_not_replace_python_planner(self) -> None:
        original = sys.modules.get("progen_routing_core")

        fake = types.SimpleNamespace(
            plan_full=lambda payload: json.dumps(
                {
                    "schema": "progen-routing-core-result/v0.1",
                    "engine": "rust_core_v0.1_temp_geometry",
                    "implemented": False,
                }
            )
        )
        sys.modules["progen_routing_core"] = fake
        try:
            self.assertIsNone(_try_rust_plan({"placement": {}, "circuit": {}, "catalogue": {}}))
        finally:
            if original is None:
                sys.modules.pop("progen_routing_core", None)
            else:
                sys.modules["progen_routing_core"] = original

    def test_live_state_selects_weighted_pivot(self) -> None:
        circuit = {
            "components": [
                {"id": "U1", "kind": "74HC595", "pins": {"SER": "DATA", "SHCP": "CLK", "STCP": "LATCH", "Q0": "LED0"}},
                {"id": "R1", "kind": "RES", "pins": {"1": "LED0", "2": "GND"}},
                {"id": "D1", "kind": "LED", "pins": {"A": "LED0", "K": "GND"}},
            ],
            "nets": {
                "DATA": ["U1.SER"],
                "CLK": ["U1.SHCP"],
                "LATCH": ["U1.STCP"],
                "LED0": ["U1.Q0", "R1.1", "D1.A"],
                "GND": ["R1.2", "D1.K"],
            },
        }
        placement = {
            "components": {
                "U1": {"kind": "74HC595", "at": [80.0, 80.0]},
                "R1": {"kind": "RES", "at": [120.0, 80.0]},
                "D1": {"kind": "LED", "at": [140.0, 80.0]},
            },
            "obstacles": [],
        }
        state = build_live_routing_state(placement, circuit)
        self.assertEqual(state.select_pivot(), "U1")

    def test_locked_blocker_cannot_be_pushed(self) -> None:
        circuit = {
            "components": [
                {"id": "R1", "kind": "RES", "pins": {"1": "A", "2": "B"}},
                {"id": "R2", "kind": "RES", "locked": True, "pins": {"1": "C", "2": "D"}},
            ],
            "nets": {"A": ["R1.1"], "B": ["R1.2"], "C": ["R2.1"], "D": ["R2.2"]},
        }
        placement = {
            "components": {
                "R1": {"kind": "RES", "at": [50.0, 50.0]},
                "R2": {"kind": "RES", "at": [50.0, 50.0]},
            },
            "obstacles": [],
        }
        state = build_live_routing_state(placement, circuit)
        candidate, report = state.legalize_candidate("R1", (50.8, 50.8), 0, routing_v2_config())
        self.assertIsNone(candidate)
        self.assertFalse(report["ok"])
        self.assertIn("R2", report["failed"])

    def test_beam_search_reports_cluster_growth_variants(self) -> None:
        circuit = simple_vdc_resistor()
        placement = plan_placement(circuit).as_dict()
        state = build_live_routing_state(placement, circuit)
        report = state.beam_search_cluster_growth(routing_v2_config({"placement": {"beam_width": 2, "deep_route_top_n": 2}}))
        self.assertEqual(report["report"]["schema"], "progen-kicad-live-state-beam-search/v0.2")
        self.assertTrue(report["report"]["pivot"])
        self.assertGreaterEqual(len(report["report"]["pivot_rotation_candidates"]), 1)
        self.assertGreaterEqual(len(report["final_states"]), 1)
        self.assertLessEqual(len(report["final_states"]), 2)

    def test_square_fill_law_prefers_compact_square_layout(self) -> None:
        circuit = {
            "components": [
                {"id": "R1", "kind": "RES", "pins": {"1": "A1", "2": "A2"}},
                {"id": "R2", "kind": "RES", "pins": {"1": "B1", "2": "B2"}},
                {"id": "R3", "kind": "RES", "pins": {"1": "C1", "2": "C2"}},
                {"id": "R4", "kind": "RES", "pins": {"1": "D1", "2": "D2"}},
            ],
            "nets": {"A1": ["R1.1"], "A2": ["R1.2"], "B1": ["R2.1"], "B2": ["R2.2"], "C1": ["R3.1"], "C2": ["R3.2"], "D1": ["R4.1"], "D2": ["R4.2"]},
        }
        row = {
            "components": {
                "R1": {"kind": "RES", "at": [40.0, 40.0]},
                "R2": {"kind": "RES", "at": [80.0, 40.0]},
                "R3": {"kind": "RES", "at": [120.0, 40.0]},
                "R4": {"kind": "RES", "at": [160.0, 40.0]},
            },
            "obstacles": [],
        }
        square = {
            "components": {
                "R1": {"kind": "RES", "at": [40.0, 40.0]},
                "R2": {"kind": "RES", "at": [80.0, 40.0]},
                "R3": {"kind": "RES", "at": [40.0, 80.0]},
                "R4": {"kind": "RES", "at": [80.0, 80.0]},
            },
            "obstacles": [],
        }
        row_state = build_live_routing_state(row, circuit)
        square_state = build_live_routing_state(square, circuit)
        self.assertGreater(row_state.score_square_fill()["score"], square_state.score_square_fill()["score"])

    def test_final_route_variants_can_run_in_parallel(self) -> None:
        circuit = simple_vdc_resistor()
        placement = plan_placement(circuit).as_dict()
        state = build_live_routing_state(placement, circuit)
        other = state.clone_state()
        other.apply_move("R1", other.component_center("R1")[0] + 2.54, other.component_center("R1")[1])
        result = _route_final_states(
            [state, other],
            circuit,
            engine="unit_test_parallel_variants",
            config=routing_v2_config({"parallel": {"threads": 2, "final_state_route_workers": 2, "final_state_parallel_min_variants": 2}}),
            wire_config={"max_astar_expansions": 500.0},
            state_names=["state_a", "state_b"],
        )
        self.assertEqual(result["worker_count"], 2)
        self.assertEqual(len(result["variants"]), 2)


if __name__ == "__main__":
    unittest.main()
