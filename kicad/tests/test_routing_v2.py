from __future__ import annotations

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
        self.assertGreaterEqual(len(report["final_states"]), 1)
        self.assertLessEqual(len(report["final_states"]), 2)


if __name__ == "__main__":
    unittest.main()
