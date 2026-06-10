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


def test_cross_donor_v2_patches_every_device_section_tail_pointer() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_v2_metadata_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_v2_metadata_temp", script)
    assert spec is not None
    assert spec.loader is not None
    cross_v2 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cross_v2
    spec.loader.exec_module(cross_v2)

    case = cross_v2.v1.CASES[1]
    fragments = []
    for selection in case.selections:
        selected, _metadata = cross_v2.v1.selected_fragments(selection)
        fragments.extend(selected)
    object_chunk = b"\x00" + b"".join(fragments) + b"\xff"
    sections = cross_v2.device_sections_for(case.selections)
    registry = cross_v2.seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    first_donor = cross_v2.v1.donor_by_key(case.selections[0].donor_key)
    _dsn, pointers = cross_v2.build_dsn_with_multi_device_sections(
        read_internal_file(base.path, "ROOT.DSN"),
        read_internal_file(first_donor.path, "ROOT.DSN"),
        object_chunk,
        sections,
    )
    assert len(pointers["device_sections"]) == 2
    assert all(
        item["new_tail_pointer"] == pointers["object_data_pointer"]
        for item in pointers["device_sections"]
    )


def test_cross_donor_v3_filtered_device_definitions_drop_analog_tail() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_v3_filtered_device_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_v3_filtered_device_temp", script)
    assert spec is not None
    assert spec.loader is not None
    cross_v3 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cross_v3
    spec.loader.exec_module(cross_v3)

    misc_defs = cross_v3.device_definitions_for("misc_logic_analog")
    counter_defs = cross_v3.device_definitions_for("seq_counters_all")
    assert b"CAP-ELEC" not in misc_defs["7447"]
    assert b"LM741" not in misc_defs["7447"]
    assert b"CAP-ELEC" not in counter_defs["7490"]
    assert b"RESISTOR" not in counter_defs["7490"]

    section, plan = cross_v3.build_filtered_device_section(cross_v3.v1.CASES[0])
    assert section.endswith(b"\x00\x00\x00\x00")
    assert any(item["device"] == "7447" for item in plan)
    assert b"CAP-ELEC" not in section
    assert b"LM741" not in section


def test_cross_donor_isolation_audits_previous_u50_ref_mismatch() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_isolation_v1_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_isolation_v1_temp", script)
    assert spec is not None
    assert spec.loader is not None
    isolation = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = isolation
    spec.loader.exec_module(isolation)

    previous_large_case = isolation.v1.CASES[0]
    object_chunk, _region_plan = isolation.object_chunk_for(previous_large_case.selections)
    cdb, _row_plan = isolation.v2.build_cross_cdb_sorted(previous_large_case.selections)
    object_refs = set(isolation.refs_in(object_chunk))
    cdb_refs = set(isolation.refs_in(cdb))
    assert "U50" in object_refs
    assert "U5" in cdb_refs
    assert not object_refs.issubset(cdb_refs)


def test_cross_donor_isolation_contiguous_cdb_plan_keeps_t02_refs_covered() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_isolation_v1_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_isolation_v1_temp_for_cdb", script)
    assert spec is not None
    assert spec.loader is not None
    isolation = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = isolation
    spec.loader.exec_module(isolation)

    cdb, row_plan = isolation.build_cdb_from_sources(
        "misc_logic_analog",
        (
            ("misc_logic_analog", "U1"),
            ("misc_logic_analog", "U2"),
            ("misc_logic_analog", "U3"),
            ("seq_counters_all", "U4"),
            ("seq_counters_all", "U5"),
            ("seq_counters_all", "U6"),
            ("misc_logic_analog", "U7"),
        ),
    )
    assert isolation.refs_in(cdb) == ["U1", "U2", "U3", "U4", "U5", "U6", "U7"]
    assert next(item for item in row_plan if item["ref"] == "U4")["donor_key"] == "seq_counters_all"


def test_cross_donor_isolation_v2_keeps_full_multi_device_metadata() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_isolation_v2_full_device_cdb_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_isolation_v2_temp", script)
    assert spec is not None
    assert spec.loader is not None
    isolation_v2 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = isolation_v2
    spec.loader.exec_module(isolation_v2)

    assert len(isolation_v2.CASES) == 12
    assert all(item.device_mode == "full_multi" for item in isolation_v2.CASES)
    assert isolation_v2.CASES[0].case_id == "T00_T02_SHAPE_FULL_MISC_CDB_HEADER_MISC"
    assert isolation_v2.CASES[0].cdb_mode == "full_header_donor"
    assert isolation_v2.CASES[1].cdb_mode == "row_sources"
    assert isolation_v2.CASES[4].case_id == "T04_T02_SHAPE_CONTIGUOUS_CDB_HEADER_SEQ"
    assert isolation_v2.CASES[11].case_id == "T11_T04_SHAPE_CONTIGUOUS_CDB_HEADER_SEQ"


def test_cross_donor_cdb_v1_uses_correct_row_parser_variants() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_cdb_v1_correct_rows_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_cdb_v1_correct_rows_temp", script)
    assert spec is not None
    assert spec.loader is not None
    cdb_v1 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cdb_v1
    spec.loader.exec_module(cdb_v1)

    assert len(cdb_v1.CASES) == 12
    assert cdb_v1.CASES[0].cdb_mode == "full_header_donor"
    assert cdb_v1.CASES[1].cdb_mode == "correct_rows"
    assert cdb_v1.CASES[1].renumber_rows is False
    assert cdb_v1.CASES[4].renumber_rows is True

    cdb, row_plan = cdb_v1.build_correct_cdb(
        "misc_logic_analog",
        cdb_v1.iso.T02_SPARSE,
        renumber_rows=True,
    )
    parsed = cdb_v1.parse_cdb(cdb)
    assert parsed.count == 5
    assert [row.ref for row in parsed.pin_rows] == ["U2", "U3", "U4", "U5", "U6"]
    assert [item["emitted_ordinal"] for item in row_plan] == [1, 2, 3, 4, 5]


def test_cross_donor_cdb_v2_uses_full_skeleton_replacement() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_cross_donor_cdb_v2_full_skeleton_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_cdb_v2_full_skeleton_temp", script)
    assert spec is not None
    assert spec.loader is not None
    cdb_v2 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cdb_v2
    spec.loader.exec_module(cdb_v2)

    assert len(cdb_v2.CASES) == 11
    assert cdb_v2.CASES[0].replacement_sources == ()
    assert cdb_v2.CASES[1].replacement_sources == cdb_v2.T02_REPLACE_MISC_SKELETON
    assert cdb_v2.CASES[2].replace_pins is False
    assert cdb_v2.CASES[3].replace_properties is False

    cdb, row_plan = cdb_v2.build_full_skeleton_cdb(
        "misc_logic_analog",
        cdb_v2.T02_REPLACE_MISC_SKELETON,
        replace_pins=True,
        replace_properties=True,
    )
    parsed = cdb_v2.parse_cdb(cdb)
    assert parsed.count == cdb_v2.cdb_v1.parsed_cdb("misc_logic_analog").count
    assert [row.ref for row in parsed.property_rows][9:12] == ["U4", "U5", "U6"]
    assert [item["ref"] for item in row_plan] == ["U4", "U5", "U6"]
    assert b"4017" in cdb and b"74HC4024" in cdb


def test_cross_donor_cdb_v3_isolates_t05_replacements() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_cross_donor_cdb_v3_t05_isolation_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_cdb_v3_t05_isolation_temp", script)
    assert spec is not None
    assert spec.loader is not None
    cdb_v3 = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = cdb_v3
    spec.loader.exec_module(cdb_v3)

    assert len(cdb_v3.CASES) == 11
    assert cdb_v3.CASES[0].replacement_sources == ()
    assert cdb_v3.CASES[1].replacement_sources == cdb_v3.U2
    assert cdb_v3.CASES[2].replacement_sources == cdb_v3.U3
    assert cdb_v3.CASES[3].replacement_sources == cdb_v3.U2_U3
    assert cdb_v3.CASES[4].replace_pins is False
    assert cdb_v3.CASES[5].replace_properties is False

    cdb, row_plan = cdb_v3.cdb_v2.build_full_skeleton_cdb(
        "seq_counters_all",
        cdb_v3.U2,
        replace_pins=True,
        replace_properties=True,
    )
    parsed = cdb_v3.parse_cdb(cdb)
    assert parsed.count == cdb_v3.cdb_v1.parsed_cdb("seq_counters_all").count
    assert [item["ref"] for item in row_plan] == ["U2"]
    assert b"74HC595" in cdb


def test_cross_donor_accepted_v1_uses_full_skeleton_policy_without_u50() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_cross_donor_accepted_v1_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_accepted_v1_temp", script)
    assert spec is not None
    assert spec.loader is not None
    accepted = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = accepted
    spec.loader.exec_module(accepted)

    assert len(accepted.CASES) == 8
    assert accepted.CASES[2].case_id == "T03_LARGE_MISC_COMPUTE_WITH_LATE_COUNTERS"
    assert accepted.CASES[2].replacement_sources == (
        ("misc_logic_analog", "U2"),
        ("misc_logic_analog", "U3"),
        ("misc_logic_analog", "U4"),
        ("misc_logic_analog", "U6"),
    )

    for case in accepted.CASES:
        object_chunk, _region_plan = accepted.base_iso.object_chunk_for(case.selections)
        object_refs = accepted.base_iso.refs_in(object_chunk)
        assert "U50" not in object_refs
        assert len(object_refs) == len(set(object_refs))

        cdb, _row_plan, _mode = accepted.cdb_for_case(case)
        parsed = accepted.parse_cdb(cdb)
        expected_count = accepted.cdb_v2.cdb_v1.parsed_cdb(case.header_donor_key).count
        assert parsed.count == expected_count
        assert set(object_refs).issubset(set(accepted.base_iso.refs_in(cdb)))
        for marker in case.expected_markers:
            assert marker.encode("ascii") in object_chunk
            assert marker.encode("ascii") in cdb


def test_cross_donor_accepted_v2_layout_separates_regions_and_excludes_4060() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_cross_donor_accepted_v2_layout_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_accepted_v2_layout_temp", script)
    assert spec is not None
    assert spec.loader is not None
    accepted = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = accepted
    spec.loader.exec_module(accepted)

    assert len(accepted.CASES) == 8
    assert accepted.CASES[2].case_id == "T03_LARGE_MISC_COMPUTE_WITH_LATE_COUNTERS"
    assert "74HC4060" not in accepted.CASES[2].expected_markers
    assert "74HC4060" not in accepted.CASES[7].expected_markers

    for case in accepted.CASES:
        object_chunk, _region_plan, layout_plan = accepted.object_chunk_for_layout(case.selections)
        object_refs = accepted.base_iso.refs_in(object_chunk)
        assert "U50" not in object_refs
        assert len(object_refs) == len(set(object_refs))
        assert b"74HC4060" not in object_chunk
        assert layout_plan
        assert all(entry["refs_unchanged"] for entry in layout_plan)
        assert all(entry["marker_count_before"] == entry["marker_count_after"] for entry in layout_plan)

        x_lanes = [entry["after_bbox"]["min_x"] for entry in layout_plan if entry["translated"]]
        assert x_lanes == sorted(x_lanes) or len(x_lanes) > accepted.IC_SLOT_COLUMNS

        cdb, _row_plan, _mode = accepted.cdb_for_case(case)
        parsed = accepted.parse_cdb(cdb)
        expected_count = accepted.cdb_v2.cdb_v1.parsed_cdb(case.header_donor_key).count
        assert parsed.count == expected_count
        assert set(object_refs).issubset(set(accepted.base_iso.refs_in(cdb)))


def test_mixed_ic_focused_v3_moves_text_and_covers_analog_controls() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_focused_v3_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_focused_v3_temp", script)
    assert spec is not None
    assert spec.loader is not None
    focused = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = focused
    spec.loader.exec_module(focused)

    assert len(focused.LAYOUT_CASES) == 2
    assert len(focused.ANALOG_CASES) == 3
    assert len(focused.WHOLE_DONOR_CASES) == 2

    object_chunk, _region_plan, layout_plan = focused.object_chunk_for_text_aligned_layout(
        focused.LAYOUT_CASES[0].selections
    )
    assert object_chunk.count(b"$TERBIDIR") == object_chunk.count(b"WIRE")
    assert all(entry["refs_unchanged"] for entry in layout_plan)
    assert all(entry["marker_count_before"] == entry["marker_count_after"] for entry in layout_plan)
    assert any("terminal_label:A000" in entry["coordinate_reason_counts"] for entry in layout_plan)
    assert all(entry["coordinate_reason_counts"]["component_text_or_body"] >= 1 for entry in layout_plan)

    analog_case = focused.ANALOG_CASES[0]
    donor = focused.subset_v1.donor_by_key(analog_case.donor_key)
    donor_dsn = focused.seq.read_internal_file(donor.path, "ROOT.DSN")
    original_chunk = focused.seq._extract_object_chunk(donor_dsn)
    regions = focused.subset_v1.discover_regions(original_chunk)
    subset_chunk, _kept, _removed = focused.subset_v1.build_subset_chunk(
        original_chunk,
        regions,
        analog_case.keep_markers,
    )
    for marker in (b"RESISTOR", b"CAPACITOR", b"REALIND", b"NPN", b"PNP", b"LM741", b"CAP-ELEC"):
        assert marker in subset_chunk

    assert any("4060" in case.case_id for case in focused.ANALOG_CASES)
    assert any("4060" in case.case_id for case in focused.WHOLE_DONOR_CASES)


def test_mixed_ic_focused_v5_keeps_4060_donor_native() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_focused_v5_donor_native_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_focused_v5_temp", script)
    assert spec is not None
    assert spec.loader is not None
    focused = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = focused
    spec.loader.exec_module(focused)

    assert len(focused.CASES) == 6
    assert focused.cdb_4060_voltage_refs(read_internal_file(focused.DONOR_4060_RLC, "ROOT.CDB")) == []

    replacements = focused.replacements_4060_q3_to_existing_rlc(focused.DONOR_4060_RLC)
    assert replacements[0] == "L0"
    assert replacements[58] == "L0"
    for index in (56, 57, 59, 60, 61, 62, 63):
        assert index not in replacements

    ne555_replacements = focused.replacements_ne555_q_to_existing_rlc(focused.DONOR_NE555_RLC)
    assert ne555_replacements[0] == "NQ0"
    assert ne555_replacements[18] == "NQ0"
    for index in (17, 19, 20, 21, 22, 23):
        assert index not in ne555_replacements


def test_mixed_ic_focused_v6_excludes_4060_and_extends_accepted_routes() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_focused_v6_no4060_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_focused_v6_temp", script)
    assert spec is not None
    assert spec.loader is not None
    focused = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = focused
    spec.loader.exec_module(focused)

    assert len(focused.CASES) == 4
    assert all("4060" not in case.case_id for case in focused.CASES)
    assert all("74HC4060" not in case.required_markers for case in focused.CASES)

    analog_replacements = focused.analog_lm741_output_to_rlc_node_replacements()
    assert analog_replacements[0] == "AO0"
    assert analog_replacements[5] == "AO0"

    ne555_u2_replacements = focused.ne555_u2_q_to_rlc_replacements()
    assert ne555_u2_replacements[8] == "NQ2"
    assert ne555_u2_replacements[18] == "NQ2"
    assert ne555_u2_replacements[0] != "NQ2"


def test_ic_exact_rezip_all_families_includes_refreshed_4060_and_no_payload_edits() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_ic_exact_rezip_all_families_temp.py"
    spec = importlib.util.spec_from_file_location("ic_exact_rezip_all_families_temp", script)
    assert spec is not None
    assert spec.loader is not None
    rezip = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = rezip
    spec.loader.exec_module(rezip)

    assert len(rezip.CASES) == 37
    ids = {case.case_id for case in rezip.CASES}
    assert "T005_74HC32_OR_EXACT_REZIP" in ids
    assert "M02_ALL4" in str(next(case.donor for case in rezip.CASES if case.case_id == "T005_74HC32_OR_EXACT_REZIP"))
    assert "T018_74HC4060_REPO_SINGLE_EXACT_REZIP" in ids
    assert "T034_74HC4060_REFRESH_SINGLE_EXACT_REZIP" in ids
    assert "T037_74HC4060_REFRESH_4X_RLC_EXACT_REZIP" in ids

    sample = next(case for case in rezip.CASES if case.case_id == "T034_74HC4060_REFRESH_SINGLE_EXACT_REZIP")
    donor_payloads = rezip._zip_payloads(sample.donor)
    assert "ROOT.DSN" in donor_payloads
    assert "ROOT.CDB" in donor_payloads
    assert b"74HC4060" in donor_payloads["ROOT.DSN"] + donor_payloads["ROOT.CDB"]


def test_mixed_ic_focused_v4_patches_4060_without_coordinate_scan() -> None:
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_mixed_ic_focused_v4_temp.py"
    spec = importlib.util.spec_from_file_location("mixed_ic_focused_v4_temp", script)
    assert spec is not None
    assert spec.loader is not None
    focused = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = focused
    spec.loader.exec_module(focused)

    assert len(focused.CROSS_BASELINE_CASES) == 2
    assert len(focused.ANALOG_CASES) == 4
    assert len(focused.WHOLE_DONOR_CASES) == 3
    assert not hasattr(focused, "_text_and_body_coord_pairs")

    donor = ROOT / "proteus_ic" / "donors" / "sequential_ics_batch3" / "4_74HC4060withRLC.pdsprj"
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    patched_cdb, cdb_plan = focused._patch_4060_cdb(donor_cdb, modfile="4060.MDF")
    assert [item["ref"] for item in cdb_plan] == ["U1", "U2", "U3", "U4"]
    parsed = focused.parse_cdb(patched_cdb)
    for row in parsed.property_rows:
        if row.ref in {"U1", "U2", "U3", "U4"}:
            assert b"74HC4060" in row.data
            assert b"{MODFILE=4060.MDF}" in row.data
            assert b"{VOLTAGE=4.5V}" in row.data

    donor_chunk = _extract_object_chunk(read_internal_file(donor, "ROOT.DSN"))
    patched_chunk, dsn_plan = focused._patch_4060_dsn_chunk(donor_chunk, modfile="4060.MDF")
    assert dsn_plan["patched_dsn_property_records"] == 4
    assert patched_chunk.count(b"{MODFILE=4060.MDF}") == 4
    assert patched_chunk.count(b"{VOLTAGE=4.5V}") == 4
    assert patched_chunk.count(focused.OLD_4060_PROPS) == 0

    analog_case = next(case for case in focused.ANALOG_CASES if case.case_id.startswith("T08_"))
    donor_obj = focused.subset_v1.donor_by_key(analog_case.donor_key)
    original_chunk = focused.seq._extract_object_chunk(read_internal_file(donor_obj.path, "ROOT.DSN"))
    regions = focused.subset_v1.discover_regions(original_chunk)
    subset_chunk, _kept, _removed = focused.subset_v1.build_subset_chunk(
        original_chunk,
        regions,
        analog_case.keep_markers,
    )
    for marker in (b"RESISTOR", b"CAPACITOR", b"REALIND", b"NPN", b"PNP", b"LM741", b"CAP-ELEC"):
        assert marker in subset_chunk
