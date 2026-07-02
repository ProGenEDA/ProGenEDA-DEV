from __future__ import annotations

import unittest

from kicad.pipeline.wire_geometry_validator import (
    AllowedTouch,
    ComponentBody,
    WireGeometrySegment,
    validate_wire_geometry,
)


class WireGeometryValidatorTests(unittest.TestCase):
    def test_different_net_crossing_is_a_hard_violation(self) -> None:
        report = validate_wire_geometry(
            [
                WireGeometrySegment("A", (0.0, 5.0), (10.0, 5.0)),
                WireGeometrySegment("B", (5.0, 0.0), (5.0, 10.0)),
            ],
            [],
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["violations_by_rule"]["different_net_wires_must_not_touch_or_cross"], 1)

    def test_wire_touching_component_body_away_from_pin_is_a_violation(self) -> None:
        report = validate_wire_geometry(
            [WireGeometrySegment("A", (0.0, 5.0), (10.0, 5.0))],
            [ComponentBody("U1", 4.0, 4.0, 6.0, 6.0)],
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["violations_by_rule"]["wire_must_not_touch_component_except_intended_pin"], 1)

    def test_wire_touching_intended_pin_point_is_allowed(self) -> None:
        report = validate_wire_geometry(
            [
                WireGeometrySegment(
                    "A",
                    (4.0, 5.0),
                    (0.0, 5.0),
                    allowed_touches=(AllowedTouch("U1", (4.0, 5.0)),),
                )
            ],
            [ComponentBody("U1", 4.0, 4.0, 6.0, 6.0)],
        )
        self.assertTrue(report["ok"])


if __name__ == "__main__":
    unittest.main()
