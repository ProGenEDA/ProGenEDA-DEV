from __future__ import annotations

import unittest

from kicad.pipeline.wire_geometry_validator import (
    AllowedTouch,
    ComponentBody,
    WireGeometrySegment,
    validate_wire_geometry,
)


class WireGeometryValidatorTests(unittest.TestCase):
    def test_different_net_crossing_is_allowed(self) -> None:
        report = validate_wire_geometry(
            [
                WireGeometrySegment("A", (0.0, 5.0), (10.0, 5.0)),
                WireGeometrySegment("B", (5.0, 0.0), (5.0, 10.0)),
            ],
            [],
        )
        self.assertTrue(report["ok"])
        self.assertTrue(report["rule_set"]["wire_wire_crossings_allowed"])

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

    def test_short_entry_into_intended_pin_body_edge_is_allowed(self) -> None:
        report = validate_wire_geometry(
            [
                WireGeometrySegment(
                    "A",
                    (3.0, 5.0),
                    (4.8, 5.0),
                    allowed_touches=(AllowedTouch("U1", (4.0, 5.0)),),
                )
            ],
            [ComponentBody("U1", 4.0, 4.0, 6.0, 6.0)],
        )
        self.assertTrue(report["ok"])

    def test_long_wire_crossing_body_after_pin_is_still_a_violation(self) -> None:
        report = validate_wire_geometry(
            [
                WireGeometrySegment(
                    "A",
                    (3.0, 5.0),
                    (10.0, 5.0),
                    allowed_touches=(AllowedTouch("U1", (4.0, 5.0)),),
                )
            ],
            [ComponentBody("U1", 4.0, 4.0, 8.0, 6.0)],
        )
        self.assertFalse(report["ok"])
        self.assertEqual(report["violations_by_rule"]["wire_must_not_touch_component_except_intended_pin"], 1)


if __name__ == "__main__":
    unittest.main()
