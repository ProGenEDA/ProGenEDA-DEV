from __future__ import annotations

from pathlib import Path

import pytest

from proteusgen.component_placer import (
    NEW_COMPONENT_MEGA_DONOR,
    generate_component_placement_project,
    load_component_aliases,
)
from proteusgen.component_catalog import load_component_catalog
from proteusgen.component_beautifier import (
    layout_coordinate_pairs,
    translate_packet_by_delta,
)
from proteusgen.pdsprj import read_internal_file
from proteusgen.component_terminal_placer import (
    PROTEUS_TERMINAL_GRID,
    _bidir_label_records,
    _extract_object_chunk,
    _object_chunk_absolute_start,
    _terminal_contact_xy,
    _wire_rows_from_chunk,
    attach_catalogue_pin_bidir_terminals_to_project,
    analyse_terminalized_donor_pin_geometry,
    plan_catalogue_pin_bidir_terminals,
)
from proteusgen.ic_native import NativeRegistry
from proteusgen.node_name_mapping import build_node_name_mapping, terminal_label_for_node
from proteusgen.pin_terminal_planner import (
    build_pin_terminal_plan,
    pin_terminal_test_label,
)
from proteusgen.templates import repository_root
from proteusgen.validation import COMPONENT_PINS, HC08_INPUT_PINS, HC08_OUTPUT_PINS


def test_catalog_covers_all_v12_two_pin_terminal_families() -> None:
    catalog = load_component_catalog()
    families = [
        "RESISTOR",
        "CAP",
        "DIODE",
        "VSINE",
        "VSOURCE",
        "CSOURCE",
        "VPULSE",
        "LED-RED",
        "1N4733A",
        "40EPS08",
        "BZY88C",
        "1N4007",
        "1N4148",
        "1N6000B",
        "BZX55C5V1",
        "BZX79C5V1",
        "FUSE",
        "REALIND",
        "CAP-ELEC",
    ]

    for family in families:
        profile = catalog.profile(family)
        assert profile.terminal_support == "accepted_two_pin_v12"
        assert len(profile.pin_names(include_hidden=True)) == 2


def test_catalog_normalizes_component_and_pin_aliases() -> None:
    catalog = load_component_catalog()

    assert catalog.normalize_part("LED") == "LED-RED"
    assert catalog.normalize_part("74HC90") == "7490"
    assert catalog.normalize_part("7SEG-COM-AN-RED") == "7SEG-COM-AN-BLUE"
    assert catalog.profile("74HC08").normalize_pin("1A").name == "1"
    assert catalog.profile("74HC08").normalize_pin("Pin 14").hidden
    assert catalog.profile("74HC08").normalize_pin("+5V").role == "VCC"
    assert catalog.profile("VSOURCE").normalize_pin("-").name == "2"
    try:
        catalog.profile("VSOURCE").normalize_pin("")
    except ValueError:
        pass
    else:
        raise AssertionError("empty pin token must not normalize to the negative pin")


def test_catalog_includes_more_than_two_pin_components() -> None:
    catalog = load_component_catalog()

    assert len(catalog.profile("74HC283").pin_names(include_hidden=True)) == 16
    assert len(catalog.profile("NE555").pin_names(include_hidden=True)) == 8
    assert len(catalog.profile("LM741").pin_names(include_hidden=True)) == 8
    assert set(catalog.profile("NPN").pin_names(include_hidden=True)) == {"B", "C", "E"}
    assert catalog.profile("NPN").normalize_pin("BASE").name == "B"
    assert catalog.profile("NMOSFET").normalize_pin("DRAIN").name == "D"
    assert catalog.profile("LM317T").normalize_pin("ADJ").name == "1"
    assert catalog.profile("POT-HG").normalize_pin("WIPER").name == "2"


def test_nmosfet_catalogue_requires_active_staged_attachment_units() -> None:
    geometry = load_component_catalog().profile("NMOSFET").proteus["pin_geometry"]

    assert geometry["staged_contact_requires_active_attachment_unit"] is True
    assert geometry["donor_terminalized_project"] == (
        "evidence/donors/terminalized_catalogue_evidence/three_pin_transistor/"
        "NMOSFET/NMOSFET_user_terminalized_july04.pdsprj"
    )
    assert {pin: geometry["pins"][pin]["component_link_trailer"] for pin in ("D", "G", "S")} == {
        "D": "0200",
        "G": "0200",
        "S": "0200",
    }


def test_catalog_has_no_empty_alias_tokens() -> None:
    catalog = load_component_catalog()

    for profile in catalog.components.values():
        assert "" not in profile.pin_aliases


def test_catalog_covers_every_component_placer_family() -> None:
    catalog = load_component_catalog()
    placer_families = set(load_component_aliases().values())

    assert sorted(placer_families - set(catalog.components)) == []


def test_catalog_includes_donor_label_backed_ic_pin_aliases() -> None:
    catalog = load_component_catalog()

    assert catalog.profile("4017").normalize_pin("CLK").name == "14"
    assert catalog.profile("4017").normalize_pin("CLK").role == "CLK"
    assert catalog.profile("74HC595").normalize_pin("SH_CP").name == "11"
    assert catalog.profile("74HC595").normalize_pin("SH_CP").role == "SH_CP"
    assert catalog.profile("74HC151").normalize_pin("D7").name == "12"
    assert catalog.profile("4511").normalize_pin("SEG_A").name == "13"
    assert catalog.profile("7447").normalize_pin("BI/RBO").name == "5"


def test_catalog_records_4017_donor_pin_geometry() -> None:
    profile = load_component_catalog().profile("4017")

    clk = profile.proteus_pin_geometry("CLK")
    q0 = profile.proteus_pin_geometry("Q0")

    assert clk is not None
    assert clk["side"] == "left"
    assert clk["angle_tenths"] == 1800
    assert clk["x_offset_from_component_bbox_min"] == -508000
    assert q0 is not None
    assert q0["side"] == "right"
    assert q0["angle_tenths"] == 0


def test_terminalized_donor_geometry_extracts_4017_pin_coordinates() -> None:
    donor = NativeRegistry.load().components["4017"].donors["single"]

    report = analyse_terminalized_donor_pin_geometry(donor, family="4017")

    assert report["valid"]
    assert report["terminal_count"] == 14
    assert report["wire_count"] == 14
    assert report["pins"]["14"]["signal"] == "CLK"
    assert report["pins"]["14"]["side"] == "left"
    assert report["pins"]["14"]["angle_tenths"] == 1800
    assert report["pins"]["3"]["signal"] == "Q0"
    assert report["pins"]["3"]["side"] == "right"


def test_terminalized_donor_geometry_preserves_three_pin_wire_polylines() -> None:
    pot_report = analyse_terminalized_donor_pin_geometry(
        repository_root()
        / "evidence"
        / "donors"
        / "terminalized_catalogue_evidence"
        / "three_pin_regulator_control_symbol"
        / "POT-HG"
        / "POT-HG_user_terminalized_july04.pdsprj",
        family="POT-HG",
    )
    lm317_report = analyse_terminalized_donor_pin_geometry(
        repository_root()
        / "evidence"
        / "donors"
        / "terminalized_catalogue_evidence"
        / "three_pin_regulator_control_symbol"
        / "LM317T"
        / "LM317T_user_terminalized_july04.pdsprj",
        family="LM317T",
    )

    assert pot_report["valid"]
    assert pot_report["pins"]["gnd"]["wire_unit_coordinates"] == [
        -6350000,
        -4805680,
        -6096000,
        -4805680,
        -6096000,
        -4826000,
        -6350000,
        -4826000,
    ]
    assert pot_report["pins"]["gnd"]["pin_y"] == -4805680
    assert lm317_report["valid"]
    assert lm317_report["pins"]["1"]["wire_unit_coordinates"] == [
        -5313680,
        -6350000,
        -5313680,
        -6604000,
        -5080000,
        -6604000,
    ]
    assert lm317_report["pins"]["1"]["pin_x"] == -5313680


@pytest.mark.xfail(
    reason="4017 is not present in the locked current mega donor; retained as historical catalogue evidence.",
)
def test_catalogue_pin_planner_uses_grid_short_wire_for_4017(tmp_path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"4017": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "catalogue_4017_pin_plan.pdsprj",
        full_cdb=True,
    )

    plan = plan_catalogue_pin_bidir_terminals(result.selected_groups)

    assert plan["valid"]
    assert plan["terminal_count"] == 14
    by_pin = {
        row["pin"]["name"]: row
        for row in plan["terminal_plans"]
    }
    assert by_pin["14"]["terminal"]["angle_tenths"] == 1800
    assert by_pin["3"]["terminal"]["angle_tenths"] == 0
    for row in plan["terminal_plans"]:
        start = row["short_wire"]["start"]
        end = row["short_wire"]["end"]
        assert start["x"] % PROTEUS_TERMINAL_GRID == 0
        assert start["y"] % PROTEUS_TERMINAL_GRID == 0
        assert end["x"] == row["pin"]["x"]
        assert end["y"] == row["pin"]["y"]


def test_catalogue_three_pin_planner_emits_donor_wire_unit_shapes(tmp_path) -> None:
    catalog = load_component_catalog()
    expected = {
        ("POT-HG", "3"): {
            "coordinates": [
                -6350000,
                -4805680,
                -6096000,
                -4805680,
                -6096000,
                -4826000,
                -6350000,
                -4826000,
            ],
            "terminal_contact": {"x": -6350000, "y": -4826000},
            "pin_contact": {"x": -6350000, "y": -4805680},
        },
        ("LM317T", "1"): {
            "coordinates": [
                -5313680,
                -6350000,
                -5313680,
                -6604000,
                -5080000,
                -6604000,
            ],
            "terminal_contact": {"x": -5080000, "y": -6604000},
            "pin_contact": {"x": -5313680, "y": -6350000},
        },
    }

    for (family, pin_name), expectation in expected.items():
        result = generate_component_placement_project(
            {
                "components": {family: 1},
                "layout": {"strategy": "beautify"},
            },
            tmp_path / f"{family}_polyline_wire_unit_plan.pdsprj",
            full_cdb=True,
        )
        plan = plan_catalogue_pin_bidir_terminals(
            result.selected_groups,
            catalog=catalog,
        )
        by_pin = {
            row["pin"]["name"]: row
            for row in plan["terminal_plans"]
        }
        row = by_pin[pin_name]
        record = bytes.fromhex(row["short_wire"]["record"])

        assert plan["valid"]
        assert row["short_wire"]["coordinates"] == expectation["coordinates"]
        assert row["short_wire"]["terminal_contact"] == expectation["terminal_contact"]
        assert row["short_wire"]["pin_contact"] == expectation["pin_contact"]
        assert record.find(b"\x7fWIRE") == 24
        assert int.from_bytes(record[32:34], "little") == len(expectation["coordinates"]) // 2


def test_catalogue_three_pin_planner_can_qualify_scaled_labels(tmp_path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"POT-HG": 2},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "pot_hg_2x_qualified_label_plan.pdsprj",
        full_cdb=True,
    )

    donor_label_plan = plan_catalogue_pin_bidir_terminals(result.selected_groups)
    qualified_plan = plan_catalogue_pin_bidir_terminals(
        result.selected_groups,
        use_donor_terminal_labels=False,
    )

    donor_labels = [
        row["terminal"]["label"]
        for row in donor_label_plan["terminal_plans"]
    ]
    qualified_labels = [
        row["terminal"]["label"]
        for row in qualified_plan["terminal_plans"]
    ]

    assert donor_labels.count("vcc") == 2
    assert len(set(qualified_labels)) == len(qualified_labels)
    assert {"RV1VCC", "RV2VCC"} <= set(qualified_labels)


@pytest.mark.xfail(
    reason="4017 is not present in the locked current mega donor; retained as historical catalogue evidence.",
)
def test_catalogue_pin_planner_coordinates_are_component_relative(tmp_path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"4017": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "catalogue_4017_relative_pin_plan.pdsprj",
        full_cdb=True,
    )
    group = next(group for group in result.selected_groups if group.family == "4017")
    dx = 1_270_000
    dy = -508_000
    moved_data, move_report = translate_packet_by_delta(
        group.data,
        key=group.key,
        family=group.family,
        dx=dx,
        dy=dy,
    )
    moved_group = type(group)(
        key=group.key,
        family=group.family,
        start=group.start,
        end=group.end,
        refs=group.refs,
        data=moved_data,
        source_is_final=group.source_is_final,
    )

    original = plan_catalogue_pin_bidir_terminals([group])
    moved = plan_catalogue_pin_bidir_terminals([moved_group])

    assert move_report["translated"]
    assert original["valid"]
    assert moved["valid"]
    original_by_pin = {
        row["pin"]["name"]: row
        for row in original["terminal_plans"]
    }
    moved_by_pin = {
        row["pin"]["name"]: row
        for row in moved["terminal_plans"]
    }
    for pin, original_row in original_by_pin.items():
        moved_row = moved_by_pin[pin]
        assert moved_row["pin"]["x"] == original_row["pin"]["x"] + dx
        assert moved_row["pin"]["y"] == original_row["pin"]["y"] + dy
        assert moved_row["short_wire"]["end"]["x"] == original_row["short_wire"]["end"]["x"] + dx
        assert moved_row["short_wire"]["end"]["y"] == original_row["short_wire"]["end"]["y"] + dy


def test_catalogue_pin_planner_uses_component_anchor_not_stale_wire_coordinates(
    tmp_path,
) -> None:
    catalog = load_component_catalog()
    result = generate_component_placement_project(
        {
            "components": {"74HC157": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "catalogue_74hc157_relative_pin_plan.pdsprj",
        full_cdb=True,
    )

    plan = plan_catalogue_pin_bidir_terminals(
        result.selected_groups,
        catalog=catalog,
    )

    assert plan["valid"]
    for row in plan["terminal_plans"]:
        assert (
            row["coordinate_source"]
            == "component_marker_anchor_offset"
        )
        profile = catalog.profile(row["terminal"]["component_family"])
        geometry = profile.proteus_pin_geometry(row["pin"]["name"])
        assert geometry is not None
        anchor = row["component_anchor"]
        assert anchor is not None
        assert row["pin"]["x"] == (
            anchor["x"] + geometry["x_offset_from_component_anchor"]
        )
        assert row["pin"]["y"] == (
            anchor["y"] + geometry["y_offset_from_component_anchor"]
        )


@pytest.mark.xfail(
    reason="The historical matrix includes 4017, which is outside the locked mega-donor support set.",
)
def test_catalogue_multi_pin_families_use_parsed_layout_and_marker_anchor(
    tmp_path,
) -> None:
    catalog = load_component_catalog()
    families = [
        "4017",
        "4020",
        "4027",
        "74HC4024",
        "74HC4040",
        "74HC4060",
        "74HC161",
        "74HC163",
        "74HC192",
        "74HC193",
        "74HC273",
        "74HC165",
        "74HC595",
        "7447",
    ]

    for family in families:
        result = generate_component_placement_project(
            {
                "components": {family: 1},
                "layout": {"strategy": "beautify"},
            },
            tmp_path / f"catalogue_{family}_marker_anchor.pdsprj",
            full_cdb=True,
        )
        placement_errors = [
            issue["code"]
            for issue in result.validation_reports["generated_output_validator"][
                "errors"
            ]
        ]
        plan = plan_catalogue_pin_bidir_terminals(
            result.selected_groups,
            catalog=catalog,
        )

        assert result.valid, family
        assert "E_OUTPUT_LAYOUT_BROAD_SCAN" not in placement_errors
        assert plan["valid"], family
        assert {
            row["coordinate_source"] for row in plan["terminal_plans"]
        } == {"component_marker_anchor_offset_existing_wire_identity"}


def test_reported_v5_coordinate_issues_are_fixed_for_locked_4027_and_192(
    tmp_path,
) -> None:
    catalog = load_component_catalog()

    result_4027 = generate_component_placement_project(
        {
            "components": {"4027": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "catalogue_4027_v6_coordinate_fix.pdsprj",
        full_cdb=True,
    )
    plan_4027 = plan_catalogue_pin_bidir_terminals(
        result_4027.selected_groups,
        catalog=catalog,
    )
    by_pin_4027 = {
        row["pin"]["name"]: row
        for row in plan_4027["terminal_plans"]
    }

    assert plan_4027["valid"]
    assert by_pin_4027["6"]["component_anchor"]["marker_offset"] != by_pin_4027["10"]["component_anchor"]["marker_offset"]
    assert by_pin_4027["6"]["pin"]["y"] != by_pin_4027["10"]["pin"]["y"]
    assert by_pin_4027["7"]["pin"]["y"] != by_pin_4027["9"]["pin"]["y"]
    # The locked-mega 4027 packet is clean; its donor WIRE units are catalogue
    # evidence for the later attachment stage, not pre-existing stream records.
    assert {
        row["coordinate_source"] for row in plan_4027["terminal_plans"]
    } == {"component_marker_anchor_offset"}

    result_192 = generate_component_placement_project(
        {
            "components": {"74HC192": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "catalogue_192_v6_coordinate_fix.pdsprj",
        full_cdb=True,
    )
    plan_192 = plan_catalogue_pin_bidir_terminals(
        result_192.selected_groups,
        catalog=catalog,
    )
    by_pin_192 = {
        row["pin"]["name"]: row
        for row in plan_192["terminal_plans"]
    }

    assert plan_192["valid"]
    assert by_pin_192["5"]["pin"]["y"] != by_pin_192["9"]["pin"]["y"]
    assert by_pin_192["5"]["terminal"]["label"] == "UP PIN 5"
    assert by_pin_192["9"]["terminal"]["label"] == "D3 PIN 9"
    assert by_pin_192["5"]["coordinate_source"] == "component_marker_anchor_offset"
    assert by_pin_192["9"]["coordinate_source"] == "component_marker_anchor_offset"


@pytest.mark.xfail(
    reason="4017 is not present in the locked current mega donor; retained as historical catalogue evidence.",
)
def test_catalogue_pin_emitter_attaches_4017_existing_wire_skeleton(tmp_path) -> None:
    source = tmp_path / "catalogue_4017_bare.pdsprj"
    output = tmp_path / "catalogue_4017_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {"4017": 1},
            "layout": {"strategy": "beautify"},
        },
        source,
        full_cdb=True,
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        output,
        result.selected_groups,
        terminal_families=["4017"],
    )

    assert report["valid"]
    assert report["terminal_count_added"] == 14
    assert report["wire_count_added"] == 0
    assert report["wire_count_rewritten"] == 14
    assert report["wire_count_before"] == report["wire_count_after"] == 14
    assert report["terminal_suffix_links_valid"]
    assert report["link_allocation"]["valid"]
    assert report["object_chunk_double_ff_valid"]
    assert all(row["wire_is_nonzero"] for row in report["wire_path_contact_checks"])
    assert _extract_object_chunk(read_internal_file(output, "ROOT.DSN")).endswith(
        b"\xff\xff"
    )


def test_catalogue_pin_emitter_strips_old_partial_terminals_before_74hc74(tmp_path) -> None:
    source = tmp_path / "catalogue_74hc74_bare.pdsprj"
    output = tmp_path / "catalogue_74hc74_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {"74HC74": 1},
            "layout": {"strategy": "beautify"},
        },
        source,
        full_cdb=True,
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        output,
        result.selected_groups,
        terminal_families=["74HC74"],
    )

    assert report["valid"]
    assert report["stripped_existing_terminal_count"] == 0
    assert report["terminal_count_added"] == 12
    assert report["bidir_count_after"] == 12
    assert report["wire_count_before"] == 0
    assert report["wire_count_after"] == 12


def test_catalogue_pin_emitter_uses_clean_bare_component_stream(tmp_path) -> None:
    source = tmp_path / "catalogue_74hc04_main_donor_bare.pdsprj"
    output = tmp_path / "catalogue_74hc04_main_donor_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {"74HC04": 1},
            "layout": {"strategy": "beautify"},
        },
        source,
        full_cdb=True,
    )

    source_chunk = _extract_object_chunk(read_internal_file(source, "ROOT.DSN"))
    assert b"$TERBIDIR" not in source_chunk
    assert b"\x7fWIRE" not in source_chunk

    report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        output,
        result.selected_groups,
        terminal_families=["74HC04"],
    )

    output_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    assert report["valid"]
    assert report["family_handler"] == "CATALOGUE/link-offset-wire-v1"
    assert report["stripped_existing_terminal_count"] == 0
    assert report["wire_count_added"] == 12
    assert report["wire_count_rewritten"] == 0
    assert report["terminal_count_added"] == 12
    assert output_chunk.count(b"$TERBIDIR") == 12
    assert output_chunk.count(b"\x7fWIRE") == 12


@pytest.mark.xfail(
    reason="Historical route expects zero-length donor-contact wires; active policy requires nonzero grid-attached wires.",
)
def test_4027_subpart_route_uses_each_donor_anchor_and_grid_native_wires(
    tmp_path,
) -> None:
    source = tmp_path / "catalogue_4027_grid_bare.pdsprj"
    output = tmp_path / "catalogue_4027_grid_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {"4027": 1},
            "layout": {
                "strategy": "beautify",
                "terminal_grid_alignment": True,
            },
        },
        source,
        full_cdb=True,
    )
    plan = plan_catalogue_pin_bidir_terminals(result.selected_groups)
    by_pin = {row["pin"]["name"]: row for row in plan["terminal_plans"]}

    assert plan["valid"]
    assert len(plan["terminal_plans"]) == 14
    assert by_pin["6"]["component_anchor"]["y"] != by_pin["10"]["component_anchor"]["y"]
    for row in plan["terminal_plans"]:
        pin = row["pin"]
        terminal = row["terminal"]
        wire = row["short_wire"]
        assert pin["x"] % PROTEUS_TERMINAL_GRID == 0
        assert pin["y"] % PROTEUS_TERMINAL_GRID == 0
        assert terminal["symbol_y"] % PROTEUS_TERMINAL_GRID == 0
        assert wire["terminal_contact"]["x"] % PROTEUS_TERMINAL_GRID == 0
        assert wire["terminal_contact"]["y"] % PROTEUS_TERMINAL_GRID == 0
        assert wire["coordinates"] == [
            wire["terminal_contact"]["x"],
            wire["terminal_contact"]["y"],
            pin["x"],
            pin["y"],
        ]
        # The authoritative 4027 donor is a frozen native-contact exception:
        # each active WIRE has equal endpoints at the exact grid pin contact.
        assert wire["terminal_contact"] == wire["pin_contact"]

    # The grid-terminal opt-in also moves the donor-proven non-length-prefixed
    # SUBCKT NAME label pair for each physical flip-flop. The default parsed
    # coordinate route remains frozen and deliberately omits that extra field.
    grid_pairs = layout_coordinate_pairs(
        result.selected_groups[0].data,
        "4027",
        include_subckt_name_coordinates=True,
    )
    subckt_coordinates = [
        tuple(
            int.from_bytes(
                result.selected_groups[0].data[offset : offset + 4],
                "little",
                signed=True,
            )
            for offset in (x_offset, y_offset)
        )
        for x_offset, y_offset, reason in grid_pairs
        if reason == "subckt_name_label"
    ]
    assert subckt_coordinates == [
        (-4_805_670, -5_100_320),
        (-4_805_670, 2_265_680),
    ]
    assert not any(
        reason == "subckt_name_label"
        for _x_offset, _y_offset, reason in layout_coordinate_pairs(
            result.selected_groups[0].data,
            "4027",
        )
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        output,
        result.selected_groups,
        terminal_families=["4027"],
    )
    output_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    assert report["valid"]
    assert report["terminal_count_added"] == 14
    assert report["wire_count_added"] == 14
    assert report["terminal_grid_alignment_valid"]
    assert report["wire_path_contacts_valid"]
    assert all(
        row["zero_length_wire_allowed"]
        and not row["wire_is_nonzero"]
        for row in report["wire_path_contact_checks"]
    )
    assert report["cdb_normalization"] == {
        "policy": "preserve_source_member_uninspected",
        "keep_packages": None,
        "inspected": False,
    }
    assert output_chunk.count(b"$TERBIDIR") == 14
    assert output_chunk.count(b"\x7fWIRE") == 14
    assert output_chunk.endswith(b"\xff")


@pytest.mark.xfail(
    reason="Historical route expects an unchanged zero-length native/grid stage; active policy requires grid attachment behavior.",
)
def test_4027_staged_terminal_contact_gate_is_dsn_only_and_monotonic(tmp_path) -> None:
    source = tmp_path / "catalogue_4027_stage_bare.pdsprj"
    native_output = tmp_path / "catalogue_4027_stage_native.pdsprj"
    grid_output = tmp_path / "catalogue_4027_stage_grid.pdsprj"
    complete_output = tmp_path / "catalogue_4027_stage_complete.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {"4027": 1},
            "layout": {
                "strategy": "beautify",
                "terminal_grid_alignment": True,
            },
        },
        source,
        full_cdb=True,
    )

    native_report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        native_output,
        result.selected_groups,
        terminal_families=["4027"],
        attachment_stage="native_pin_contact",
    )
    grid_report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        grid_output,
        result.selected_groups,
        terminal_families=["4027"],
        attachment_stage="grid_contact",
    )
    complete_report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        complete_output,
        result.selected_groups,
        terminal_families=["4027"],
        attachment_stage="complete",
    )
    native_dsn = read_internal_file(native_output, "ROOT.DSN")
    grid_dsn = read_internal_file(grid_output, "ROOT.DSN")
    complete_chunk = _extract_object_chunk(
        read_internal_file(complete_output, "ROOT.DSN")
    )

    # The accepted native 4027 contacts are already grid intersections, so
    # Stage 2 is byte-identical to Stage 1. Stage 3 adds the active unit.
    assert native_dsn == grid_dsn
    for report in (native_report, grid_report):
        assert report["valid"]
        assert report["terminal_count_added"] == 14
        assert report["wire_count_added"] == 0
        assert report["terminal_grid_alignment_valid"]
        assert report["root_cdb_policy"] == "preserve_source_member_uninspected"
        assert report["cdb_unchanged"] is None
    assert complete_report["valid"]
    assert complete_report["terminal_count_added"] == 14
    assert complete_report["wire_count_added"] == 14
    assert complete_chunk.count(b"$TERBIDIR") == 14
    assert complete_chunk.count(b"\x7fWIRE") == 14
    assert complete_chunk.endswith(b"\xff")


@pytest.mark.parametrize("family", ["74HC160", "74HC192"])
def test_dil16_counter_terminal_leading_stages_preserve_active_pin_links(
    tmp_path: Path,
    family: str,
) -> None:
    """Counter profiles use one shared staged route with nonzero active wires."""

    base = tmp_path / f"{family}_1x_no_terminal.pdsprj"
    native = tmp_path / f"{family}_1x_native_contact.pdsprj"
    grid = tmp_path / f"{family}_1x_grid_contact.pdsprj"
    active = tmp_path / f"{family}_1x_catalogue_terminal.pdsprj"
    placement = generate_component_placement_project(
        {
            "donor": str(NEW_COMPONENT_MEGA_DONOR),
            "components": {family: 1},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    native_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        native,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        attachment_stage="native_pin_contact",
    )
    grid_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        grid,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        attachment_stage="grid_contact",
    )
    active_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        active,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
    )

    catalog = load_component_catalog()
    profile = catalog.get_profile(family)
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    assert geometry["clean_packet_attachment_order"] == (
        "terminal_leading_component_then_wires"
    )
    assert geometry["strip_component_placer_finalizer_before_terminal_leading_wires"]
    assert geometry["wire_record_encoding"] == "catalogue_leading_separator"
    assert geometry["object_stream_finalizer"] == "append_explicit_single_ff"

    assert placement.valid
    for report in (native_report, grid_report):
        assert report["valid"]
        assert report["terminal_count_added"] == 14
        assert report["wire_count_added"] == 0
    assert native_report["terminal_grid_alignment_valid"] is False
    assert grid_report["terminal_grid_alignment_valid"] is True
    assert active_report["valid"]
    assert active_report["terminal_count_added"] == 14
    assert active_report["wire_count_added"] == 14
    assert active_report["terminal_grid_alignment_valid"]
    assert active_report["wire_path_contacts_valid"]
    assert active_report["terminal_suffix_links_valid"]
    assert all(
        row["terminal_to_wire"] and row["wire_to_pin"] and row["wire_is_nonzero"]
        for row in active_report["wire_path_contact_checks"]
    )

    dsn = read_internal_file(active, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wires = _wire_rows_from_chunk(
        chunk,
        chunk_start=_object_chunk_absolute_start(dsn),
    )
    terminal_suffixes = {int(row["suffix"]) for row in terminals}
    expected_labels = [
        geometry["pins"][pin]["donor_terminal_label"]
        for pin in geometry["donor_terminal_record_order"]
    ]
    assert [row["label"] for row in terminals] == expected_labels
    assert len(terminals) == len(wires) == 14
    assert all(
        _terminal_contact_xy(row)[0] % PROTEUS_TERMINAL_GRID == 0
        and _terminal_contact_xy(row)[1] % PROTEUS_TERMINAL_GRID == 0
        for row in terminals
    )
    assert all(
        tuple(row["coordinates"][:2]) != tuple(row["coordinates"][2:4])
        for row in wires
    )
    chunk_start = _object_chunk_absolute_start(dsn)
    assert all(
        int(row["suffix"])
        == (chunk_start + int(row["marker_offset"]) - 24) & 0xFFFF
        for row in wires
    )

    group = placement.selected_groups[0]
    marker = b"\xff" + bytes((len(group.key),)) + group.key.encode("ascii")
    component_start = chunk.index(marker)
    component_end = min(int(row["marker_offset"]) - 24 for row in wires)
    # The original one-byte generator tail is consumed. The retained live
    # packet is exactly donor-width plus the placed reference-width delta.
    assert component_end - component_start == 445 + len(group.key) - len("U1")
    for pin, pin_geometry in geometry["pins"].items():
        position = component_end + int(
            pin_geometry["component_link_offset_from_component_end"]
        )
        suffix = int.from_bytes(chunk[position : position + 2], "little")
        assert suffix in terminal_suffixes, pin
        assert chunk[position + 2 : position + 4] == bytes.fromhex(
            pin_geometry["component_link_trailer"]
        )
    assert chunk.endswith(b"\xff")
    base_cdb = read_internal_file(base, "ROOT.CDB")
    assert read_internal_file(native, "ROOT.CDB") == base_cdb
    assert read_internal_file(grid, "ROOT.CDB") == base_cdb
    assert read_internal_file(active, "ROOT.CDB") == base_cdb


@pytest.mark.parametrize(
    ("family", "count"),
    [
        ("74HC160", 9),
        ("74HC160", 15),
        ("74HC192", 9),
        ("74HC192", 15),
    ],
)
def test_dil16_counter_scales_keep_all_grid_short_wire_attachment_units(
    tmp_path: Path,
    family: str,
    count: int,
) -> None:
    """Every scaled counter stays within its per-component shared profile."""

    base = tmp_path / f"{family}_{count}x_no_terminal.pdsprj"
    output = tmp_path / f"{family}_{count}x_catalogue_terminal.pdsprj"
    placement = generate_component_placement_project(
        {
            "donor": str(NEW_COMPONENT_MEGA_DONOR),
            "components": {family: count},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
                "shelf_width": 75_000_000,
            },
        },
        base,
        full_cdb=True,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        allow_progressive_scaling=True,
    )

    expected = 14 * count
    dsn = read_internal_file(output, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wires = _wire_rows_from_chunk(
        chunk,
        chunk_start=_object_chunk_absolute_start(dsn),
    )
    suffixes = [int(row["suffix"]) for row in wires]
    assert placement.valid
    assert len(placement.selected_groups) == count
    assert report["valid"]
    assert report["terminalized_component_count"] == count
    assert report["terminal_count_added"] == expected
    assert report["wire_count_added"] == expected
    assert report["terminal_grid_alignment_valid"]
    assert report["wire_path_contacts_valid"]
    assert report["terminal_suffix_links_valid"]
    assert len(terminals) == len(wires) == expected
    assert len(set(suffixes)) == expected
    assert all(
        _terminal_contact_xy(row)[0] % PROTEUS_TERMINAL_GRID == 0
        and _terminal_contact_xy(row)[1] % PROTEUS_TERMINAL_GRID == 0
        for row in terminals
    )
    assert all(
        tuple(row["coordinates"][:2]) != tuple(row["coordinates"][2:4])
        for row in wires
    )
    chunk_start = _object_chunk_absolute_start(dsn)
    assert all(
        suffix == (chunk_start + int(row["marker_offset"]) - 24) & 0xFFFF
        for suffix, row in zip(suffixes, wires, strict=True)
    )
    assert all(
        chunk.count(suffix.to_bytes(2, "little") + b"\x01\x00") == 2
        for suffix in suffixes
    )
    assert chunk.endswith(b"\xff")
    assert read_internal_file(output, "ROOT.CDB") == read_internal_file(
        base, "ROOT.CDB"
    )


@pytest.mark.parametrize("family", ["74HC174", "74HC283", "74HC85"])
def test_dil16_terminal_leading_stages_preserve_active_pin_links(
    tmp_path: Path,
    family: str,
) -> None:
    """DIL16 profiles use the shared terminal-leading route without new emitters."""

    base = tmp_path / f"{family}_1x_no_terminal.pdsprj"
    native = tmp_path / f"{family}_1x_native_contact.pdsprj"
    grid = tmp_path / f"{family}_1x_grid_contact.pdsprj"
    active = tmp_path / f"{family}_1x_catalogue_terminal.pdsprj"
    placement = generate_component_placement_project(
        {
            "donor": str(NEW_COMPONENT_MEGA_DONOR),
            "components": {family: 1},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    native_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        native,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        attachment_stage="native_pin_contact",
    )
    grid_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        grid,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        attachment_stage="grid_contact",
    )
    active_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        active,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
    )

    catalog = load_component_catalog()
    profile = catalog.get_profile(family)
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    assert geometry["clean_packet_attachment_order"] == (
        "terminal_leading_component_then_wires"
    )
    assert geometry["strip_component_placer_finalizer_before_terminal_leading_wires"]
    assert geometry["wire_record_encoding"] == "catalogue_leading_separator"
    assert geometry["object_stream_finalizer"] == "append_explicit_single_ff"

    assert placement.valid
    for report in (native_report, grid_report):
        assert report["valid"]
        assert report["terminal_count_added"] == 14
        assert report["wire_count_added"] == 0
    assert native_report["terminal_grid_alignment_valid"] is False
    assert grid_report["terminal_grid_alignment_valid"] is True
    assert active_report["valid"]
    assert active_report["terminal_count_added"] == 14
    assert active_report["wire_count_added"] == 14
    assert active_report["terminal_grid_alignment_valid"]
    assert active_report["wire_path_contacts_valid"]
    assert active_report["terminal_suffix_links_valid"]
    assert all(
        row["terminal_to_wire"] and row["wire_to_pin"] and row["wire_is_nonzero"]
        for row in active_report["wire_path_contact_checks"]
    )

    dsn = read_internal_file(active, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wires = _wire_rows_from_chunk(
        chunk,
        chunk_start=_object_chunk_absolute_start(dsn),
    )
    terminal_suffixes = {int(row["suffix"]) for row in terminals}
    expected_labels = [
        geometry["pins"][pin]["donor_terminal_label"]
        for pin in geometry["donor_terminal_record_order"]
    ]
    assert [row["label"] for row in terminals] == expected_labels
    assert len(terminals) == len(wires) == 14
    assert all(
        _terminal_contact_xy(row)[0] % PROTEUS_TERMINAL_GRID == 0
        and _terminal_contact_xy(row)[1] % PROTEUS_TERMINAL_GRID == 0
        for row in terminals
    )
    assert all(
        tuple(row["coordinates"][:2]) != tuple(row["coordinates"][2:4])
        for row in wires
    )
    chunk_start = _object_chunk_absolute_start(dsn)
    assert all(
        int(row["suffix"])
        == (chunk_start + int(row["marker_offset"]) - 24) & 0xFFFF
        for row in wires
    )

    group = placement.selected_groups[0]
    marker = b"\xff" + bytes((len(group.key),)) + group.key.encode("ascii")
    component_start = chunk.index(marker)
    component_end = min(int(row["marker_offset"]) - 24 for row in wires)
    assert component_end - component_start == int(
        geometry["donor_component_packet_bytes"]
    ) + len(group.key) - len("U1")
    for pin, pin_geometry in geometry["pins"].items():
        position = component_end + int(
            pin_geometry["component_link_offset_from_component_end"]
        )
        suffix = int.from_bytes(chunk[position : position + 2], "little")
        assert suffix in terminal_suffixes, pin
        assert chunk[position + 2 : position + 4] == bytes.fromhex(
            pin_geometry["component_link_trailer"]
        )
    assert chunk.endswith(b"\xff")
    base_cdb = read_internal_file(base, "ROOT.CDB")
    assert read_internal_file(native, "ROOT.CDB") == base_cdb
    assert read_internal_file(grid, "ROOT.CDB") == base_cdb
    assert read_internal_file(active, "ROOT.CDB") == base_cdb


@pytest.mark.parametrize(
    ("family", "expected_terminal_count"),
    [("LM741", 7), ("NE555", 8)],
)
def test_dil8_analog_terminal_stages_preserve_locked_mega_identity_packet(
    tmp_path: Path,
    family: str,
    expected_terminal_count: int,
) -> None:
    """DIL8 analogue parts keep their locked-mega identity record and link tails."""

    base = tmp_path / f"{family}_1x_no_terminal.pdsprj"
    native = tmp_path / f"{family}_1x_native_contact.pdsprj"
    grid = tmp_path / f"{family}_1x_grid_contact.pdsprj"
    active = tmp_path / f"{family}_1x_catalogue_terminal.pdsprj"
    placement = generate_component_placement_project(
        {
            "donor": str(NEW_COMPONENT_MEGA_DONOR),
            "components": {family: 1},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    native_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        native,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        attachment_stage="native_pin_contact",
    )
    grid_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        grid,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        attachment_stage="grid_contact",
    )
    active_report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        active,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
    )

    catalog = load_component_catalog()
    profile = catalog.get_profile(family)
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    assert geometry["clean_packet_attachment_order"] == (
        "terminal_leading_component_then_wires"
    )
    assert geometry["component_identity_record_policy"] == (
        "preserve_locked_mega_component_id_record"
    )
    assert geometry["locked_mega_leading_component_id_record_bytes"] > 0

    assert placement.valid
    for report in (native_report, grid_report):
        assert report["valid"]
        assert report["terminal_count_added"] == expected_terminal_count
        assert report["wire_count_added"] == 0
    assert native_report["terminal_grid_alignment_valid"] is False
    assert grid_report["terminal_grid_alignment_valid"] is True
    assert active_report["valid"]
    assert active_report["terminal_count_added"] == expected_terminal_count
    assert active_report["wire_count_added"] == expected_terminal_count
    assert active_report["terminal_grid_alignment_valid"]
    assert active_report["wire_path_contacts_valid"]
    assert active_report["terminal_suffix_links_valid"]

    dsn = read_internal_file(active, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wires = _wire_rows_from_chunk(
        chunk,
        chunk_start=_object_chunk_absolute_start(dsn),
    )
    suffixes = {int(row["suffix"]) for row in terminals}
    expected_labels = [
        geometry["pins"][pin]["donor_terminal_label"]
        for pin in geometry["donor_terminal_record_order"]
    ]
    assert [row["label"] for row in terminals] == expected_labels
    assert len(terminals) == len(wires) == expected_terminal_count
    assert all(
        _terminal_contact_xy(row)[0] % PROTEUS_TERMINAL_GRID == 0
        and _terminal_contact_xy(row)[1] % PROTEUS_TERMINAL_GRID == 0
        for row in terminals
    )
    assert all(
        tuple(row["coordinates"][:2]) != tuple(row["coordinates"][2:4])
        for row in wires
    )
    group = placement.selected_groups[0]
    marker = b"\xff" + bytes((len(group.key),)) + group.key.encode("ascii")
    component_start = chunk.index(marker)
    component_end = min(int(row["marker_offset"]) - 24 for row in wires)
    assert component_end - component_start == int(
        geometry["locked_mega_component_packet_bytes"]
    )
    for pin, pin_geometry in geometry["pins"].items():
        position = component_end + int(
            pin_geometry["component_link_offset_from_component_end"]
        )
        suffix = int.from_bytes(chunk[position : position + 2], "little")
        assert suffix in suffixes, pin
        assert chunk[position + 2 : position + 4] == bytes.fromhex(
            pin_geometry["component_link_trailer"]
        )
    assert chunk.endswith(b"\xff")
    base_cdb = read_internal_file(base, "ROOT.CDB")
    assert read_internal_file(native, "ROOT.CDB") == base_cdb
    assert read_internal_file(grid, "ROOT.CDB") == base_cdb
    assert read_internal_file(active, "ROOT.CDB") == base_cdb


@pytest.mark.parametrize(
    ("family", "count"),
    [
        ("74HC174", 9),
        ("74HC174", 15),
        ("74HC283", 9),
        ("74HC283", 15),
        ("74HC85", 9),
        ("74HC85", 15),
    ],
)
def test_dil16_terminal_leading_scales_keep_all_grid_short_wire_attachment_units(
    tmp_path: Path,
    family: str,
    count: int,
) -> None:
    """Every requested DIL16 terminal-leading scale stays on the shared path."""

    base = tmp_path / f"{family}_{count}x_no_terminal.pdsprj"
    output = tmp_path / f"{family}_{count}x_catalogue_terminal.pdsprj"
    placement = generate_component_placement_project(
        {
            "donor": str(NEW_COMPONENT_MEGA_DONOR),
            "components": {family: count},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
                "shelf_width": 75_000_000,
            },
        },
        base,
        full_cdb=True,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        allow_progressive_scaling=True,
    )

    expected = 14 * count
    dsn = read_internal_file(output, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wires = _wire_rows_from_chunk(
        chunk,
        chunk_start=_object_chunk_absolute_start(dsn),
    )
    suffixes = [int(row["suffix"]) for row in wires]
    assert placement.valid
    assert len(placement.selected_groups) == count
    assert report["valid"]
    assert report["terminalized_component_count"] == count
    assert report["terminal_count_added"] == expected
    assert report["wire_count_added"] == expected
    assert report["terminal_grid_alignment_valid"]
    assert report["wire_path_contacts_valid"]
    assert report["terminal_suffix_links_valid"]
    assert len(terminals) == len(wires) == expected
    assert len(set(suffixes)) == expected
    assert all(
        _terminal_contact_xy(row)[0] % PROTEUS_TERMINAL_GRID == 0
        and _terminal_contact_xy(row)[1] % PROTEUS_TERMINAL_GRID == 0
        for row in terminals
    )
    assert all(
        tuple(row["coordinates"][:2]) != tuple(row["coordinates"][2:4])
        for row in wires
    )
    chunk_start = _object_chunk_absolute_start(dsn)
    assert all(
        suffix == (chunk_start + int(row["marker_offset"]) - 24) & 0xFFFF
        for suffix, row in zip(suffixes, wires, strict=True)
    )
    assert all(
        chunk.count(suffix.to_bytes(2, "little") + b"\x01\x00") == 2
        for suffix in suffixes
    )
    assert chunk.endswith(b"\xff")
    assert read_internal_file(output, "ROOT.CDB") == read_internal_file(
        base, "ROOT.CDB"
    )


@pytest.mark.parametrize(
    ("family", "count", "pins_per_component"),
    [
        ("LM741", 9, 7),
        ("LM741", 15, 7),
        ("NE555", 9, 8),
        ("NE555", 15, 8),
    ],
)
def test_dil8_analog_scales_keep_all_grid_short_wire_attachment_units(
    tmp_path: Path,
    family: str,
    count: int,
    pins_per_component: int,
) -> None:
    """DIL8 analogue scale packs preserve every complete active attachment unit."""

    base = tmp_path / f"{family}_{count}x_no_terminal.pdsprj"
    output = tmp_path / f"{family}_{count}x_catalogue_terminal.pdsprj"
    placement = generate_component_placement_project(
        {
            "donor": str(NEW_COMPONENT_MEGA_DONOR),
            "components": {family: count},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
                "shelf_width": 75_000_000,
            },
        },
        base,
        full_cdb=True,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        placement.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
        allow_progressive_scaling=True,
    )

    expected = pins_per_component * count
    dsn = read_internal_file(output, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminals = _bidir_label_records(chunk)
    wires = _wire_rows_from_chunk(
        chunk,
        chunk_start=_object_chunk_absolute_start(dsn),
    )
    suffixes = [int(row["suffix"]) for row in wires]
    assert placement.valid
    assert len(placement.selected_groups) == count
    assert report["valid"]
    assert report["terminalized_component_count"] == count
    assert report["terminal_count_added"] == expected
    assert report["wire_count_added"] == expected
    assert report["terminal_grid_alignment_valid"]
    assert report["wire_path_contacts_valid"]
    assert report["terminal_suffix_links_valid"]
    assert len(terminals) == len(wires) == expected
    assert len(set(suffixes)) == expected
    assert all(
        _terminal_contact_xy(row)[0] % PROTEUS_TERMINAL_GRID == 0
        and _terminal_contact_xy(row)[1] % PROTEUS_TERMINAL_GRID == 0
        for row in terminals
    )
    assert all(
        tuple(row["coordinates"][:2]) != tuple(row["coordinates"][2:4])
        for row in wires
    )
    chunk_start = _object_chunk_absolute_start(dsn)
    assert all(
        suffix == (chunk_start + int(row["marker_offset"]) - 24) & 0xFFFF
        for suffix, row in zip(suffixes, wires, strict=True)
    )
    assert all(
        chunk.count(suffix.to_bytes(2, "little") + b"\x01\x00") == 2
        for suffix in suffixes
    )
    assert chunk.endswith(b"\xff")
    assert read_internal_file(output, "ROOT.CDB") == read_internal_file(
        base, "ROOT.CDB"
    )


@pytest.mark.xfail(
    reason="Historical scale route expects zero-length donor-contact wires; active policy requires nonzero grid-attached wires.",
)
@pytest.mark.parametrize("count", [9, 15])
def test_4027_scale_uses_real_complete_packages_and_grid_native_wires(
    tmp_path,
    count: int,
) -> None:
    """The locked mega supplies whole A/B 4027 packages without cloning."""

    source = tmp_path / f"catalogue_4027_{count}x_bare.pdsprj"
    output = tmp_path / f"catalogue_4027_{count}x_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {"4027": count},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
                "terminal_grid_alignment": True,
                "shelf_width": 75_000_000,
            },
        },
        source,
        full_cdb=True,
    )
    assert result.valid
    expected_keys = [
        "U13",
        "U14",
        "U15",
        "U154",
        "U155",
        "U156",
        "U295",
        "U296",
        "U297",
        "U436",
        "U437",
        "U438",
        "U577",
        "U578",
        "U579",
    ][:count]
    assert [group.key for group in result.selected_groups] == expected_keys
    assert all(len(group.refs) == 2 for group in result.selected_groups)

    report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        output,
        result.selected_groups,
        terminal_families=["4027"],
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    wires = _wire_rows_from_chunk(chunk, chunk_start=0)

    assert report["valid"]
    assert report["terminal_count_added"] == count * 14
    assert report["wire_count_added"] == count * 14
    assert report["terminal_grid_alignment_valid"]
    assert report["wire_path_contacts_valid"]
    assert chunk.count(b"$TERBIDIR") == count * 14
    assert len(wires) == count * 14
    assert all(row["coordinates"][:2] == row["coordinates"][2:4] for row in wires)
    assert all(
        row["zero_length_wire_allowed"]
        and not row["wire_is_nonzero"]
        for row in report["wire_path_contact_checks"]
    )
    assert chunk.endswith(b"\xff")


def test_catalogue_display_block_link_offset_generation_remains_blocked(tmp_path) -> None:
    source = tmp_path / "catalogue_display_mixed_bare.pdsprj"
    output = tmp_path / "catalogue_display_mixed_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {
                "7SEG-COM-CAT-BLUE": 3,
                "7SEG-COM-AN-BLUE": 3,
            },
            "layout": {"strategy": "beautify"},
        },
        source,
        full_cdb=True,
    )

    with pytest.raises(ValueError):
        attach_catalogue_pin_bidir_terminals_to_project(
            source,
            output,
            result.selected_groups,
            terminal_families=["7SEG-COM-CAT-BLUE", "7SEG-COM-AN-BLUE"],
        )


def test_catalogue_anode_display_grid_body_route_has_eight_nonzero_wires(
    tmp_path: Path,
) -> None:
    source = tmp_path / "catalogue_anode_display_bare.pdsprj"
    output = tmp_path / "catalogue_anode_display_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {"7SEG-COM-AN-BLUE": 1},
            "layout": {"strategy": "beautify"},
        },
        source,
        full_cdb=True,
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        source,
        output,
        result.selected_groups,
        terminal_families=["7SEG-COM-AN-BLUE"],
    )

    assert report["valid"]
    assert report["terminal_count_added"] == 8
    assert report["terminal_grid_alignment_valid"]
    assert report["wire_path_contacts_valid"]
    pins = report["family_reports"][0]["terminal_pins"]
    assert len(pins) == 8
    assert all(
        pin["short_wire"]["start"] != pin["short_wire"]["end"]
        for pin in pins
    )
    assert all(
        pin["component_key"] != "D20"
        for pin in pins
    )


def test_validation_pin_vocabulary_comes_from_catalogue() -> None:
    assert COMPONENT_PINS["RESISTOR"] == {"1", "2"}
    assert COMPONENT_PINS["74HC08"] == {
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
    }
    assert HC08_INPUT_PINS == {"1", "2", "4", "5", "9", "10", "12", "13"}
    assert HC08_OUTPUT_PINS == {"3", "6", "8", "11"}


def test_node_name_mapping_groups_two_pin_and_ic_endpoints() -> None:
    payload = {
        "version": "0.2",
        "target": {
            "proteus_version": "8.13",
            "style": "terminal_based",
            "sheet_count": 1,
            "mode": "diagnostic_control",
        },
        "circuit": {
            "name": "node_mapping_probe",
            "components": [
                {"ref": "R1", "part": "RESISTOR", "value": "10k"},
                {"ref": "U1", "part": "74HC08"},
                {"ref": "D1", "part": "LED"},
            ],
            "nets": [
                {"name": "VIN", "kind": "internal"},
                {"name": "OUT", "kind": "output"},
                {"name": "VCC", "kind": "power"},
                {"name": "GND", "kind": "ground"},
                {"name": "very long node name with spaces", "kind": "internal"},
            ],
            "connections": [
                {"component": "R1", "pin": "1", "net": "VIN"},
                {"component": "U1", "pin": "1A", "net": "VIN"},
                {"component": "U1", "pin": "1Y", "net": "OUT"},
                {"component": "U1", "pin": "Pin 14", "net": "VCC"},
                {"component": "U1", "pin": "GND", "net": "GND"},
                {"component": "D1", "pin": "ANODE", "net": "very long node name with spaces"},
            ],
        },
    }

    mapping = build_node_name_mapping(payload)

    assert mapping["valid"]
    assert mapping["node_count"] == 5
    assert mapping["terminal_labels"]["VCC"] == "V0"
    assert mapping["terminal_labels"]["GND"] == "G0"
    assert mapping["terminal_labels"]["very long node name with spaces"].startswith("N")
    assert mapping["endpoint_to_node"]["U1.1"] == "VIN"
    assert mapping["endpoint_to_node"]["U1.3"] == "OUT"
    assert mapping["endpoint_to_node"]["D1.1"] == "very long node name with spaces"
    assert mapping["hidden_endpoint_count"] == 2


def test_lightweight_node_name_mapping_handles_multi_pin_aliases() -> None:
    mapping = build_node_name_mapping(
        {
            "components": [{"ref": "U1", "part": "74HC90"}],
            "nets": {"CLK": "input"},
            "connections": [
                {
                    "net": "CLK",
                    "endpoints": [{"component": "U1", "pin": "Pin 1"}],
                }
            ],
        }
    )

    assert mapping["valid"]
    assert mapping["nodes"][0]["endpoints"][0]["part"] == "7490"
    assert mapping["nodes"][0]["endpoints"][0]["pin"] == "1"


def test_node_name_mapping_infers_refs_from_component_count_payload() -> None:
    mapping = build_node_name_mapping(
        {
            "components": {
                "RESISTOR": {"count": 1, "value": "4k7"},
                "CAP": 1,
            },
            "connections": [
                {
                    "net": "N_FILTER",
                    "from": {"component": "R1", "pin": "2"},
                    "to": {"component": "C1", "pin": "1"},
                }
            ],
        }
    )

    assert mapping["valid"]
    assert mapping["endpoint_to_node"] == {"R1.2": "N_FILTER", "C1.1": "N_FILTER"}
    assert mapping["nodes"][0]["endpoint_count"] == 2


def test_terminal_label_for_node_is_deterministic_and_collision_safe() -> None:
    used: set[str] = set()

    assert terminal_label_for_node("VCC", kind="power", index=0, used=used) == "V0"
    assert terminal_label_for_node("GND", kind="ground", index=1, used=used) == "G0"
    assert terminal_label_for_node("VIN", index=2, used=used) == "VIN"
    assert terminal_label_for_node("VIN", index=3, used=used) == "N003"


def test_pin_terminal_plan_separates_two_pin_three_pin_and_ic_work() -> None:
    plan = build_pin_terminal_plan(
        {
            "components": [
                {"ref": "R1", "part": "RESISTOR"},
                {"ref": "Q1", "part": "NPN"},
                {"ref": "U1", "part": "74HC08"},
            ],
            "nets": {
                "N1": "internal",
                "BASE": "input",
                "COL": "internal",
                "EMIT": "ground",
                "A": "input",
                "Y": "output",
            },
            "connections": [
                {"net": "N1", "endpoints": [{"component": "R1", "pin": "1"}]},
                {"net": "BASE", "endpoints": [{"component": "Q1", "pin": "BASE"}]},
                {"net": "COL", "endpoints": [{"component": "Q1", "pin": "COLLECTOR"}]},
                {"net": "EMIT", "endpoints": [{"component": "Q1", "pin": "EMITTER"}]},
                {"net": "A", "endpoints": [{"component": "U1", "pin": "1A"}]},
                {"net": "Y", "endpoints": [{"component": "U1", "pin": "1Y"}]},
            ],
        }
    )

    assert plan["valid"]
    assert plan["pin_class_counts"] == {"multi_pin": 2, "three_pin": 3, "two_pin": 1}
    assert plan["terminal_emit_ready_count"] == 1
    assert plan["blocked_terminal_count"] == 5
    by_endpoint = {
        (row["component"], row["pin"]): row
        for row in plan["terminal_plans"]
    }
    assert by_endpoint[("Q1", "B")]["pin_class"] == "three_pin"
    assert by_endpoint[("U1", "1")]["pin_class"] == "multi_pin"
    assert by_endpoint[("R1", "1")]["terminal_emit_ready"]
    assert by_endpoint[("Q1", "B")]["test_terminal_label"] == "PINBBASE"
    assert by_endpoint[("U1", "1")]["test_terminal_label"] == "PIN1IN1"


def test_pin_terminal_test_labels_include_pin_and_role_when_known() -> None:
    assert pin_terminal_test_label("2", "RESET") == "PIN2RESET"
    assert pin_terminal_test_label("SH_CP", "clock") == "PINSHCPCLOCK"
    assert pin_terminal_test_label("7", "unknown") == "PIN7"


def test_pin_terminal_plan_can_classify_every_catalogue_family() -> None:
    catalog = load_component_catalog()
    components = []
    connections = []
    for index, (part, profile) in enumerate(catalog.components.items(), start=1):
        visible_pins = profile.pin_names()
        if not visible_pins:
            continue
        ref = f"X{index}"
        components.append({"ref": ref, "part": part})
        connections.append(
            {
                "net": f"N{index}",
                "endpoints": [{"component": ref, "pin": visible_pins[0]}],
            }
        )

    plan = build_pin_terminal_plan(
        {
            "components": components,
            "connections": connections,
        }
    )

    assert plan["valid"]
    assert plan["visible_terminal_plan_count"] == len(connections)
    assert plan["blocked_terminal_count"] > 0
    assert all(row["test_terminal_label"].startswith("PIN") for row in plan["terminal_plans"])
