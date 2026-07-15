"""Evidence tests for donor-authored, stock-symbol LTspice schematics."""

from __future__ import annotations

import os
from pathlib import Path
import unittest

from ltspice.catalogues.ltspice_main_catalogue_loader import load_native_catalogue
from ltspice.pipeline.donor_asc_parser import (
    DonorPoint,
    census_donor_root,
    decode_donor_bytes,
    parse_donor_asc,
    transform_catalogue_pin,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DONOR_ROOT = REPOSITORY_ROOT.parent / "Ltspice" / "Donor"
DONOR_ROOT = Path(os.environ.get("LTSPICE_DONOR_ROOT", DEFAULT_DONOR_ROOT))


class DonorNativeParserUnitTests(unittest.TestCase):
    def test_cp1252_micro_value_falls_back_without_corruption(self) -> None:
        text, encoding = decode_donor_bytes(b"1\xb5")

        self.assertEqual(encoding, "cp1252")
        self.assertEqual(text, "1µ")

    def test_catalogue_pin_transform_matches_a_native_r90_resistor(self) -> None:
        catalogue = load_native_catalogue()
        resistor = catalogue.get("R")
        pin_one = resistor["pin_model"]["pins"]["1"]["local"]
        pin_two = resistor["pin_model"]["pins"]["2"]["local"]
        anchor = DonorPoint(160, 48)

        self.assertEqual(
            transform_catalogue_pin(anchor, DonorPoint(*pin_one), "R90"),
            DonorPoint(144, 64),
        )
        self.assertEqual(
            transform_catalogue_pin(anchor, DonorPoint(*pin_two), "R90"),
            DonorPoint(64, 64),
        )


@unittest.skipUnless(DONOR_ROOT.is_dir(), f"LTspice donor root is unavailable: {DONOR_ROOT}")
class DonorNativeCorpusTests(unittest.TestCase):
    def test_corpus_is_stock_symbol_physical_wire_evidence(self) -> None:
        census = census_donor_root(DONOR_ROOT)

        # The current donor corpus is deliberately external to the Git repo, so
        # retain lower bounds while making its native constraints explicit.
        self.assertGreaterEqual(len(census.files), 41)
        self.assertEqual(census.version_counts, {"4.1": len(census.files)})
        self.assertEqual(census.sheet_counts, {(1, 880, 680): len(census.files)})
        self.assertGreater(census.wire_count, 0)
        self.assertGreaterEqual(census.diagonal_wire_count, 2)
        self.assertGreater(census.negative_electrical_point_count, 0)
        self.assertEqual(census.electrical_grid_violation_count, 0)
        self.assertEqual(census.unknown_record_count, 0)
        self.assertGreaterEqual(census.encoding_counts.get("cp1252", 0), 7)

        expected_native_stock_symbols = {"res", "cap", "ind", "voltage", "current", r"Misc\\signal"}
        self.assertEqual(set(census.symbol_counts), expected_native_stock_symbols)
        self.assertTrue({"res", "cap", "ind", "voltage", "current"}.issubset(census.symbol_counts))
        self.assertTrue(census.all_flags_are_ground)
        self.assertEqual(set(census.flag_counts), {"0"})
        self.assertGreater(census.flag_counts["0"], 0)

    def test_lca2_retains_negative_coordinates_and_non_manhattan_wires(self) -> None:
        document = parse_donor_asc(DONOR_ROOT / "lca2.asc")

        self.assertEqual(document.version, "4.1")
        self.assertEqual(document.electrical_grid_violations(), [])
        self.assertTrue(any(point.x < 0 or point.y < 0 for _record, point, _line in document.electrical_points()))
        diagonal_endpoints = {(wire.start, wire.end) for wire in document.diagonal_wires}
        self.assertIn((DonorPoint(272, 208), DonorPoint(336, 48)), diagonal_endpoints)
        self.assertIn((DonorPoint(144, 288), DonorPoint(192, 208)), diagonal_endpoints)

        resistor_two = next(symbol for symbol in document.symbols if symbol.ref == "R2")
        catalogue = load_native_catalogue()
        resistor = catalogue.get("RESISTOR")
        pin_one = DonorPoint(*resistor["pin_model"]["pins"]["1"]["local"])
        pin_two = DonorPoint(*resistor["pin_model"]["pins"]["2"]["local"])
        wire_endpoints = {point for wire in document.wires for point in (wire.start, wire.end)}

        self.assertEqual(resistor_two.origin, DonorPoint(160, 48))
        self.assertEqual(resistor_two.orientation, "R90")
        self.assertIn(transform_catalogue_pin(resistor_two.origin, pin_one, resistor_two.orientation), wire_endpoints)
        self.assertIn(transform_catalogue_pin(resistor_two.origin, pin_two, resistor_two.orientation), wire_endpoints)

    def test_cp1252_donor_value_is_not_lossy(self) -> None:
        document = parse_donor_asc(DONOR_ROOT / "Draft7 lab 4].asc")
        capacitor = next(symbol for symbol in document.symbols if symbol.ref == "C1")

        self.assertEqual(document.encoding, "cp1252")
        self.assertEqual(capacitor.attribute("Value"), "1µ")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
