"""Focused safety regressions for multi-endpoint LTspice wire trees."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ltspice.pipeline.component_placer import place_components
from ltspice.pipeline.component_selector import select_components
from ltspice.pipeline.geometry import Point, Segment
from ltspice.pipeline.ltspice_asc_writer import write_asc
from ltspice.pipeline.ltspice_wire_maker import _safe_tree_route, build_wire_plan
from ltspice.pipeline.netlist_validator import validate_native_netlist


def _lca_style_bus() -> dict[str, object]:
    """A compact three-branch fragment derived from the new resistor donors."""

    return {
        "components": [
            {"ref": "R1", "kind": "R", "value": "1k", "ltspice_at": [192, 160], "pins": {"1": "BUS", "2": "GND"}},
            {"ref": "R2", "kind": "R", "value": "2k", "ltspice_at": [480, 160], "pins": {"1": "BUS", "2": "GND"}},
            {"ref": "R3", "kind": "R", "value": "3k", "ltspice_at": [336, 384], "pins": {"1": "BUS", "2": "GND"}},
            {"ref": "G1", "kind": "GND", "value": "0", "ltspice_at": [336, 512], "pins": {"1": "GND"}},
        ],
        "nets": {
            "BUS": ["R1.1", "R2.1", "R3.1"],
            "GND": ["R1.2", "R2.2", "R3.2", "G1.1"],
        },
        "routing": {"mode": "combination"},
    }


def _placed(circuit: dict[str, object]):
    selected, _selection_report = select_components(circuit)
    placed, _placement_report = place_components(circuit, selected)
    return selected, placed


class TreeRouterTests(unittest.TestCase):
    def test_lca_style_multi_branch_bus_writes_a_valid_explicit_tree(self) -> None:
        """A three-pin resistor bus becomes one trunk with an explicit branch."""

        circuit = _lca_style_bus()
        selected, placed = _placed(circuit)
        wire_plan = build_wire_plan(circuit, placed)

        bus_flags = [flag for flag in wire_plan.flags if flag.logical_net == "BUS"]
        self.assertEqual(bus_flags, [])
        self.assertFalse(any(item["net"] == "BUS" for item in wire_plan.rejected_wire_routes))
        segments = {(item.start, item.end) for item in wire_plan.segments}
        self.assertIn((Point(192, 160), Point(480, 160)), segments)
        self.assertIn((Point(336, 160), Point(336, 384)), segments)

        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            writer = write_asc(
                project_dir=project,
                project_name="lca_style_tree",
                placed=placed,
                wire_segments=wire_plan.segments,
                flags=wire_plan.flags,
            )
            report = validate_native_netlist(
                asc_path=writer.asc_path,
                project_dir=project,
                placed=placed,
                wire_plan=wire_plan,
            )

        self.assertTrue(report["ok"], report)
        self.assertEqual(report["expected_nets"]["BUS"], ["R1.1", "R2.1", "R3.1"])
        self.assertIn(["R1.1", "R2.1", "R3.1"], report["actual_component_groups"])

    def test_obstructed_tree_retains_labelled_terminal_fallback(self) -> None:
        """Foreign pins may block a tree, but must never be crossed to force it."""

        circuit: dict[str, object] = {
            "components": [
                # R1's top pin is the left branch endpoint. Its terminal lead
                # exits right (R90), while foreign pins block every tree route
                # into or out of the point.
                {"ref": "R1", "kind": "R", "value": "1k", "ltspice_at": [192, 160], "ltspice_orientation": "R90", "pins": {"1": "BUS", "2": "OPEN1"}},
                {"ref": "R2", "kind": "R", "value": "1k", "ltspice_at": [480, 160], "pins": {"1": "BUS", "2": "OPEN2"}},
                {"ref": "R3", "kind": "R", "value": "1k", "ltspice_at": [336, 384], "pins": {"1": "BUS", "2": "OPEN3"}},
                {"ref": "BLEFT", "kind": "R", "value": "1k", "ltspice_at": [176, 160], "pins": {"1": "BLA", "2": "BLB"}},
                {"ref": "BRIGHT", "kind": "R", "value": "1k", "ltspice_at": [240, 160], "pins": {"1": "BRA", "2": "BRB"}},
                {"ref": "BUP", "kind": "R", "value": "1k", "ltspice_at": [192, 144], "pins": {"1": "BUA", "2": "BUB"}},
                {"ref": "BDOWN", "kind": "R", "value": "1k", "ltspice_at": [192, 80], "pins": {"1": "BDA", "2": "BDB"}},
            ],
            "nets": {"BUS": ["R1.1", "R2.1", "R3.1"]},
            "routing": {"mode": "combination"},
        }
        _selected, placed = _placed(circuit)
        wire_plan = build_wire_plan(circuit, placed)

        self.assertIn(
            {
                "net": "BUS",
                "reason": "safe_tree_router_could_not_prove_route",
                "fallback": "terminal_flags",
            },
            wire_plan.rejected_wire_routes,
        )
        self.assertEqual({flag.endpoint for flag in wire_plan.flags if flag.logical_net == "BUS"}, {"R1.1", "R2.1", "R3.1"})

    def test_tree_router_never_crosses_an_existing_foreign_wire(self) -> None:
        """A long prior-net barrier makes the bounded tree attempt decline."""

        route = _safe_tree_route(
            [Point(192, 160), Point(480, 160), Point(336, 384)],
            [Segment(Point(336, 0), Point(336, 1024))],
            set(),
        )

        self.assertIsNone(route)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
