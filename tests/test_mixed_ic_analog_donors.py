from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_analog_batch1_temp.py"


def load_mixed_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_analog_batch1_temp", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_mixed_ic_analog_donors_are_whole_bidir_projects() -> None:
    mixed = load_mixed_module()
    assert len(mixed.DONORS) == 6
    for donor in mixed.DONORS:
        dsn = read_internal_file(donor.path, "ROOT.DSN")
        cdb = read_internal_file(donor.path, "ROOT.CDB")
        chunk = _extract_object_chunk(dsn)
        assert chunk.count(b"$TERBIDIR") > 0
        assert chunk.count(b"$TERBIDIR") == chunk.count(b"WIRE")
        assert chunk.count(b"$TERINPUT") == 0
        assert chunk.count(b"$TEROUTPUT") == 0
        assert chunk.count(b"VSOURCE") == 0
        assert chunk.count(b"CSOURCE") == 0
        assert chunk.count(b"VSINE") == 0
        for marker in donor.required_markers:
            raw = marker.encode("ascii")
            assert raw in chunk
            assert raw in cdb


def test_mixed_ic_analog_label_mutation_preserves_nonblank_groups() -> None:
    mixed = load_mixed_module()
    donor = next(item for item in mixed.DONORS if item.key == "seq_192_193")
    chunk = _extract_object_chunk(read_internal_file(donor.path, "ROOT.DSN"))
    replacements, plan = mixed.topology_preserving_replacements(chunk)
    assert len(replacements) == chunk.count(b"$TERBIDIR")

    old_to_new: dict[str, str] = {}
    for item in plan:
        old = str(item["old_label"])
        new = str(item["new_label"])
        if old:
            old_to_new.setdefault(old, new)
            assert old_to_new[old] == new


def test_large_mixed_donor_covers_counter_analog_scope() -> None:
    mixed = load_mixed_module()
    donor = next(item for item in mixed.DONORS if item.key == "seq_counters_all")
    inventory = mixed.inventory_for(donor)
    markers = inventory["marker_counts"]
    for marker in donor.required_markers:
        assert markers[marker] > 0
    assert inventory["terminal_count"] == 180
    assert inventory["wire_count"] == 180


def test_subset_region_discovery_finds_expected_counter_regions() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_analog_subset_v1_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_analog_subset_v1_temp", script)
    assert spec is not None
    assert spec.loader is not None
    subset = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = subset
    spec.loader.exec_module(subset)

    donor = next(item for item in subset.mixed.DONORS if item.key == "seq_counters_all")
    chunk = _extract_object_chunk(read_internal_file(donor.path, "ROOT.DSN"))
    regions = subset.discover_regions(chunk)
    assert [region.marker for region in regions] == [
        "LM741",
        "CAPACITOR",
        "PNP",
        "NPN",
        "REALIND",
        "RESISTOR",
        "CAP-ELEC",
        "74HC193",
        "74HC192",
        "4017",
        "4020",
        "74HC4024",
        "74HC4520",
        "4518",
        "74HC4060",
        "74HC4040",
        "7490",
        "74HC160",
        "74HC161",
        "74HC163",
    ]
    subset_chunk, kept, removed = subset.build_subset_chunk(
        chunk,
        regions,
        ("74HC160", "74HC161", "74HC163"),
    )
    assert subset_chunk[0] == 0
    assert subset_chunk[-1] == 0xFF
    assert {item["marker"] for item in kept} == {"74HC160", "74HC161", "74HC163"}
    assert any(item["marker"] == "LM741" for item in removed)


def test_cross_donor_region_discovery_splits_7447_from_74hc157() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_v1_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_v1_temp", script)
    assert spec is not None
    assert spec.loader is not None
    cross = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cross
    spec.loader.exec_module(cross)

    donor = cross.donor_by_key("misc_logic_analog")
    chunk = _extract_object_chunk(read_internal_file(donor.path, "ROOT.DSN"))
    regions = cross.discover_regions(chunk)
    markers = [region.marker for region in regions]
    assert "7447" in markers
    assert "74HC157" in markers
    assert markers.index("7447") < markers.index("74HC157")

    cdb, row_plan = cross.build_cross_cdb(cross.CASES[3].selections)
    refs = [item["ref"] for item in row_plan]
    assert refs == ["U4", "U12", "U13", "U14"]
    for ref in refs:
        assert cdb.count(ref.encode("ascii")) == 2
