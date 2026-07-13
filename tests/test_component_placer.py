from __future__ import annotations

import json
from pathlib import Path
import struct

import pytest
import proteusgen.component_terminal_placer as terminal_placer

from proteusgen.component_placer import (
    ComponentPlacerBlocked,
    NEW_COMPONENT_MEGA_DONOR,
    TrustedDonor,
    _generation_markers,
    _repo_path,
    _raw_groups_from_chunk,
    build_deletion_plan,
    build_component_placer_cdb_subset,
    generate_component_placement_project,
    load_history_validator_rules,
    normalize_component,
    parse_component_placer_cdb,
    plan_component_placement,
    select_removal_only_donor,
    validate_move_linkage,
    validate_project_placement,
)
from proteusgen.component_beautifier import (
    MIXED_LAYOUT_BAND_GAP_Y,
    layout_coordinate_pairs,
)
from proteusgen.beautifier_validator import (
    layout_different_family_spacing_pairs,
    layout_overlap_pairs,
    layout_spacing_pairs,
    validate_beautifier_layout_entries,
)
from proteusgen.component_arrangement import next_start_slot_after_layout_entries
from proteusgen.component_catalog import load_component_catalog
from proteusgen.bidirectional import BIDIR_MARKER, extract_bidir_records, load_production_templates
from proteusgen.component_terminal_placer import (
    CAP_ELEC_PIN_HALF_SPAN,
    CAP_ELEC_TERMINAL_SYMBOL_TO_PIN,
    CAP_PIN_HALF_SPAN,
    CAP_TERMINAL_SYMBOL_TO_PIN,
    GENERIC_TWO_PIN_HALF_SPAN,
    GENERIC_TWO_PIN_PROFILES,
    GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN,
    INDUCTOR_PIN_HALF_SPAN,
    INDUCTOR_TERMINAL_SYMBOL_TO_PIN,
    RESISTOR_PIN_SPAN,
    SOURCE_TERMINAL_SYMBOL_TO_PIN,
    TERMINAL_CONTACT_TO_PIN,
    TERMINAL_SYMBOL_TO_PIN,
    attach_capacitor_bidir_terminals_to_project,
    attach_catalogue_pin_bidir_terminals_to_project,
    attach_component_bidir_terminals_to_project,
    attach_mixed_overlay_bidir_terminals_to_project,
    attach_mixed_native_bidir_terminals_to_project,
    attach_mixed_component_and_catalogue_bidir_terminals_to_project,
    attach_resistor_bidir_terminals_to_project,
    plan_attached_capacitor_terminals,
    plan_attached_electrolytic_capacitor_terminals,
    plan_attached_generic_two_pin_terminals,
    plan_attached_inductor_terminals,
    plan_attached_resistor_terminals,
    plan_attached_source_terminals,
    plan_side_bidir_terminals,
)
from proteusgen.cdb import package_ref
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk
from proteusgen.templates import FixtureRegistry


ROOT = Path(__file__).resolve().parents[1]
CURRENT_GROUP_MIXED_TAIL_ORACLE = (
    ROOT
    / "proteus_ic"
    / "donors"
    / "ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj"
)

CURRENT_GROUP_NATIVE_FAMILIES = (
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
    "CAP",
    "CAP-ELEC",
    "REALIND",
    "RESISTOR",
    "DIODE",
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "LED-RED",
    "FUSE",
    "SWITCH",
)
CURRENT_GROUP_CATALOGUE_TAIL_FAMILIES = (
    "POT-HG",
    "LM317T",
    "OPAMP",
    "NMOSFET",
    "2N7000",
    "BS170",
    "NPN",
    "PNP",
    "2N3904",
    "2N4401",
)
DIL14_QUAD_2INPUT_FAMILIES = (
    "74HC00",
    "74HC02",
    "74HC08",
    "74HC32",
    "74HC86",
    "74HC266",
)
DIL14_LOCKED_MEGA_SCALE_CAPS = {
    "74HC00": 8,
    "74HC02": 12,
    "74HC08": 15,
    "74HC32": 15,
    "74HC86": 15,
    "74HC266": 15,
}
HC04_E04_ATTACHMENT_ORDER = (
    "2",
    "10",
    "6",
    "4",
    "8",
    "12",
    "1",
    "11",
    "5",
    "3",
    "9",
    "13",
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, 0),
        (126_999, 0),
        (127_000, 254_000),
        (-126_999, 0),
        (-127_000, -254_000),
        (321_056, 254_000),
        (3_210_560, 3_302_000),
    ],
)
def test_terminal_grid_snap_is_nearest_with_deterministic_ties(
    value: int,
    expected: int,
) -> None:
    assert terminal_placer.snap_to_proteus_terminal_grid(value) == expected


def test_component_pin_link_patch_accepts_type_02_trailer() -> None:
    data = b"prefix" + struct.pack("<H", 0x3456) + b"\x02\x00" + b"\x7fWIRE"

    patched, position = terminal_placer._patch_component_link_suffix(
        data,
        old_suffix=0x3456,
        new_suffix=0x789A,
        before_offset=data.index(b"\x7fWIRE"),
    )

    assert position == len(b"prefix")
    assert patched[position : position + 4] == struct.pack("<H", 0x789A) + b"\x02\x00"


def test_label_jitter_updates_only_the_matching_duplicate_label_suffix() -> None:
    report = {
        "family_reports": [
            {
                "terminal_pins": [
                    {"terminal": {"label": "BASE", "suffix": "7a00"}},
                    {"terminal": {"label": "BASE", "suffix": "7a01"}},
                ],
                "terminal_pairs": [
                    {
                        "left": {"label": "BASE", "suffix": "7a02"},
                        "right": {"label": "OUT", "suffix": "7a03"},
                    }
                ],
            }
        ]
    }

    assert terminal_placer._update_report_terminal_label(
        report,
        old_label="BASE",
        new_label="BASEX",
        old_suffix=0x7A01,
    )
    pins = report["family_reports"][0]["terminal_pins"]
    pair = report["family_reports"][0]["terminal_pairs"][0]
    assert [row["terminal"]["label"] for row in pins] == ["BASE", "BASEX"]
    assert pair["left"]["label"] == "BASE"


def _active_terminal_suffixes(chunk: bytes) -> list[int]:
    suffixes: list[int] = []
    for marker, length_offset, base_size in (
        (b"$TERINPUT", 30, 101),
        (b"$TEROUTPUT", 31, 102),
        (b"$TERGROUND", 31, 102),
        (b"$TERBIDIR", 30, 101),
    ):
        cursor = 0
        while True:
            marker_offset = chunk.find(marker, cursor)
            if marker_offset < 0:
                break
            start = marker_offset - 14
            size = base_size + chunk[start + length_offset]
            suffixes.append(struct.unpack("<H", chunk[start + size - 4 : start + size - 2])[0])
            cursor = marker_offset + len(marker)
    return suffixes


@pytest.mark.parametrize(
    "project",
    (
        ROOT / "fixtures" / "pdsprj" / "rcl_4x_t07_unit_donor.pdsprj",
        ROOT
        / "proteus_ic"
        / "donors"
        / "mixed_ic_analog_batch1"
        / "MIX_RCL_ANALOG_ONLY.pdsprj",
    ),
)
def test_accepted_terminal_links_are_final_wire_addresses(project: Path) -> None:
    dsn = read_internal_file(project, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    object_start = terminal_placer._object_chunk_absolute_start(dsn)
    suffixes = _active_terminal_suffixes(chunk)
    expected: list[int] = []
    cursor = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", cursor)
        if marker < 0:
            break
        expected.append((object_start + marker - 24) & 0xFFFF)
        cursor = marker + len(b"\x7fWIRE")

    assert len(suffixes) == len(expected)
    assert sorted(suffixes) == sorted(expected)
    assert all(
        chunk[marker - 23 : marker + 10] == terminal_placer.NATIVE_WIRE_PREFIX
        for marker in (
            index
            for index in range(len(chunk))
            if chunk.startswith(b"\x7fWIRE", index)
        )
    )


def test_embedded_bidir_schema_matches_accepted_terminal_records() -> None:
    accepted = load_production_templates(FixtureRegistry.load())

    assert terminal_placer.NATIVE_BIDIR_TEMPLATES == accepted


def test_rejected_v7_mixed_links_are_not_final_wire_addresses() -> None:
    project = (
        ROOT
        / "experiments"
        / "terminal_placer_native_wire_v7_temp_2026_07_01"
        / "N07_MIXED_ALL_1X_WITH_CONTROLS"
        / "N07_MIXED_ALL_1X_WITH_CONTROLS.pdsprj"
    )
    dsn = read_internal_file(project, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    object_start = terminal_placer._object_chunk_absolute_start(dsn)
    actual = set(_active_terminal_suffixes(chunk))
    expected: set[int] = set()
    cursor = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", cursor)
        if marker < 0:
            break
        expected.add((object_start + marker - 24) & 0xFFFF)
        cursor = marker + len(b"\x7fWIRE")

    assert len(actual) == len(expected) == 12
    assert actual.isdisjoint(expected)


def test_component_placer_prefers_ic_wise_donor_for_small_request() -> None:
    selection = select_removal_only_donor({"7490": 3})

    assert selection.donor.counts == {"7490": 4}
    assert "16x_seq_combo_mega" not in selection.donor.donor_id
    assert selection.score[0] == 1


def test_component_placer_uses_mega_for_23x_when_manifest_count_is_64() -> None:
    selection = select_removal_only_donor({"74HC90": 23}, verify_file_counts=True)
    plan = build_deletion_plan(selection)

    assert selection.request == {"7490": 23}
    assert selection.donor.donor_id == "component_placer_16x_seq_combo_mega_20260615"
    assert selection.inspected_counts["7490"] == 64
    assert len(plan.keep_packages["7490"]) == 23
    assert len(plan.delete_packages["7490"]) == 41
    assert "copy full" not in plan.cdb_policy.lower()
    assert "rebuild ROOT.CDB" in plan.cdb_policy


def test_component_placer_blocks_23x_when_true_donor_count_is_16() -> None:
    donor = TrustedDonor(
        donor_id="synthetic_16_count_for_regression",
        path=ROOT / "proteus_ic" / "donors" / "manual_downloads_20260615" / "component_placer" / "16x_seq_combo_mega_donor.pdsprj",
        counts={"7490": 16},
        source="test",
    )

    with pytest.raises(ComponentPlacerBlocked) as blocked:
        select_removal_only_donor({"7490": 23}, donors=[donor])

    report = blocked.value.report.as_dict()
    assert report["errors"][0]["code"] == "E_DONOR_MISSING_REMOVAL_ONLY"
    assert "max_available={'7490': 16}" in report["errors"][0]["message"]


def test_component_placer_plans_without_generating_project() -> None:
    plan = plan_component_placement({"components": [{"part": "74HC160", "count": 5}]})

    assert plan["schema"] == "component-placer-plan/v0.1"
    assert plan["selection"]["request"] == {"74HC160": 5}
    assert plan["selection"]["requires_cloning"] is False
    assert plan["cdb_package_refs_to_keep"]
    assert plan["cdb_package_refs_to_delete"]


def test_placement_validator_catches_old_body_only_full_cdb_output() -> None:
    rejected = (
        ROOT
        / "experiments"
        / "component_placer_seq_16x_v1_temp_2026_06_15"
        / "SAME_7490_01X"
        / "SAME_7490_01X.pdsprj"
    )
    report = validate_project_placement(rejected)
    codes = {issue.code for issue in report.errors}

    assert not report.valid
    assert codes & {"E_ORPHAN_CDB_PIN_REFS", "E_ORPHAN_CDB_PROPERTY_REFS", "E_CDB_ID_DUPLICATE", "E_CDB_PARSE_FAILED"}


def test_component_placer_parses_16x_mega_cdb_property_rows() -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260615" / "component_placer" / "16x_seq_combo_mega_donor.pdsprj"
    parsed = parse_component_placer_cdb(read_internal_file(donor, "ROOT.CDB"))

    assert parsed.count == 1552
    assert len(parsed.pin_rows) == 1552
    assert len(parsed.property_rows) == 1072
    assert parsed.property_header_size == 20
    assert [row.ref for row in parsed.property_rows[:3]] == ["U1", "U2", "U3"]
    assert [row.ref for row in parsed.property_rows[-4:]] == ["U733", "U734", "U735", "U736"]


def test_component_placer_prunes_cdb_to_kept_packages() -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260615" / "component_placer" / "16x_seq_combo_mega_donor.pdsprj"
    parsed = parse_component_placer_cdb(read_internal_file(donor, "ROOT.CDB"))
    keep = [f"U{i}" for i in range(1, 24)]
    subset = parse_component_placer_cdb(build_component_placer_cdb_subset(parsed, keep))
    pin_packages = {package_ref(row.ref) for row in subset.pin_rows}
    property_packages = {package_ref(row.ref) for row in subset.property_rows}

    assert pin_packages <= set(keep)
    assert property_packages <= set(keep)
    assert "U24" not in pin_packages
    assert "U24" not in property_packages
    assert subset.count == len(subset.pin_rows)
    assert int.from_bytes(subset.between_sections[-4:], "little") == len(subset.property_rows)


def test_locked_mega_npn_cdb_subset_matches_proteus_ctrl_s_normalization() -> None:
    source = (
        ROOT
        / "experiments"
        / "bjt_npn_live_proteus_diagnostics_temp_2026_07_11"
        / "H09_CURRENT_COORDS_PROTEUS_NORMALIZED_LINKS_AND_TAIL.pdsprj"
    )
    proteus_saved = (
        ROOT
        / "experiments"
        / "bjt_npn_live_proteus_diagnostics_temp_2026_07_11"
        / "H08_H07_PROTEUS_CTRL_S_NORMALIZATION.pdsprj"
    )
    parsed = parse_component_placer_cdb(read_internal_file(source, "ROOT.CDB"))
    subset = build_component_placer_cdb_subset(parsed, ["Q129"])

    assert subset == read_internal_file(proteus_saved, "ROOT.CDB")


def test_move_linkage_validator_rejects_stale_reference_text() -> None:
    report = validate_move_linkage(
        {
            "components": [
                {
                    "ref": "U1",
                    "body_delta": [100, -50],
                    "linked_deltas": {
                        "reference_text": [0, 0],
                        "model_text": [100, -50],
                        "name_text": [100, -50],
                        "value_text": [100, -50],
                        "pin_anchor": [100, -50],
                    },
                }
            ]
        }
    )

    assert not report.valid
    assert report.errors[0].code == "E_BEAUTIFIER_TEXT_NOT_MOVED"


def test_history_rule_loader_has_camber_rules() -> None:
    rules = load_history_validator_rules()
    ids = {rule["rule_id"] for rule in rules}

    assert "DSEL_REMOVAL_ONLY_001" in ids
    assert "PVAL_REF_001" in ids
    assert "BVAL_D20_IMMUTABLE_003" in ids
    assert "BVAL_IC_REGISTERED_COORDS_004" in ids
    assert "OUTVAL_STAGE_AND_CUMULATIVE_001" in ids


def test_component_placement_generator_uses_real_cli_backend(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"SWITCH": 1, "POT-HG": 1, "FUSE": 1},
            "control_strategy": "switch_precedence",
            "switch_offset": 21,
        },
        tmp_path / "control_strategy.pdsprj",
    )

    assert result.valid
    assert result.output.exists()
    assert result.control_strategy == "accepted"
    assert result.object_chunk_head.startswith("0008")
    assert result.request == {"FUSE": 1, "POT-HG": 1, "SWITCH": 1}
    assert result.hidden_groups == ()
    assert len([group for group in result.selected_groups if group.family == "SWITCH"]) == 1
    assert len([group for group in result.selected_groups if group.family == "POT-HG"]) == 1


def test_component_placement_legacy_dummy_strategy_uses_exact_control_counts(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"SWITCH": 1, "POT-HG": 1},
            "control_strategy": "hidden_dummy_control",
        },
        tmp_path / "hidden_dummy_controls.pdsprj",
    )

    assert result.valid
    assert result.output.exists()
    assert result.control_strategy == "accepted"
    assert result.hidden_groups == ()
    assert len(result.selected_groups) == 2


def test_component_placement_beautifies_exact_control_counts(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"SWITCH": 2, "POT-HG": 2},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "beautified_exact_controls.pdsprj",
    )

    assert result.valid
    assert result.hidden_groups == ()
    assert len(result.selected_groups) == 4
    entries = [
        entry
        for entry in result.layout_plan["actual_binary_placements"]
        if entry["family"] in {"SWITCH", "POT-HG"}
    ]
    assert len(entries) == 4
    assert all(entry["translated"] for entry in entries)
    assert len({entry["slot"] for entry in entries}) == 4


def test_component_placement_ignores_hidden_mode_without_dummy_controls(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"SWITCH": 1, "POT-HG": 1},
            "control_strategy": "hidden_dummy_control",
            "hidden_coordinate_mode": "linked_relative",
        },
        tmp_path / "hidden_dummy_far_zone.pdsprj",
    )

    assert result.valid
    assert result.hidden_groups == ()
    assert result.layout_plan["hidden_dummy_zone"]["groups"] == []
    assert result.hidden_dummy_controls["binary_coordinate_mutation"]["applied"] is False


def test_component_placement_generator_uses_clean_switch_packets(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"SWITCH": 56},
            "control_strategy": "hidden_dummy_control",
        },
        tmp_path / "switch56_clean_packets.pdsprj",
    )

    switch_groups = [group for group in result.selected_groups if group.family == "SWITCH"]
    assert len(switch_groups) == 56
    assert {len(group.data) for group in switch_groups} == {393}
    assert "ANON629645" not in {group.key for group in switch_groups}


def test_raw_component_scanner_uses_encoded_ref_lengths() -> None:
    chunk = _extract_object_chunk(read_internal_file(NEW_COMPONENT_MEGA_DONOR, "ROOT.DSN"))
    groups = _raw_groups_from_chunk(chunk, _generation_markers())

    assert [group.key for group in groups["CAP"][:10]] == [f"C{i}" for i in range(1, 11)]
    assert [group.key for group in groups["NPN"][:10]] == [f"Q{i}" for i in range(1, 11)]
    assert [group.key for group in groups["CSOURCE"][:10]] == [f"I{i}" for i in range(1, 11)]
    assert "C10" not in [group.key for group in groups["CAP"][:9]]
    assert "Q88" not in [group.key for group in groups["NPN"][:10]]
    assert "I88" not in [group.key for group in groups["CSOURCE"][:10]]


def test_component_placer_normalizes_display_aliases_to_raw_markers() -> None:
    assert normalize_component("7segcomanode") == "7SEG-COM-AN-BLUE"
    assert normalize_component("7SEG-COM-AN-RED") == "7SEG-COM-AN-BLUE"
    assert normalize_component("7segcomk") == "7SEG-COM-CAT-BLUE"
    assert normalize_component("7SEG-COM-ANC") == "7SEG-COM-AN-BLUE"
    assert normalize_component("7SEG-COM-CAT") == "7SEG-COM-CAT-BLUE"
    assert normalize_component("pot hg") == "POT-HG"
    assert normalize_component("transformer") == "TRAN-2P2S"
    assert normalize_component("TRAN-2P2S5CV1") == "TRAN-2P2S"
    assert normalize_component("vdc") == "VSOURCE"
    assert normalize_component("vsin") == "VSINE"
    assert normalize_component("res") == "RESISTOR"
    assert normalize_component("led") == "LED-RED"
    assert normalize_component("bzx55c5") == "BZX55C5V1"
    assert normalize_component("bzx88c") == "BZY88C"


def test_component_placement_generator_uses_d20_display_bridge(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"4027": 1, "7segcomanode": 1, "7segcomk": 1},
        },
        tmp_path / "display_bridge.pdsprj",
    )

    assert result.valid
    assert result.output.exists()
    assert result.request == {"4027": 1, "7SEG-COM-AN-BLUE": 1, "7SEG-COM-CAT-BLUE": 1}
    assert any(group.key == "D20" for group in result.selected_groups)
    assert any(group.key.startswith("DISPLAY_AN_") for group in result.selected_groups)
    assert any(group.key.startswith("DISPLAY_CC_") for group in result.selected_groups)
    chunk = _extract_object_chunk(read_internal_file(result.output, "ROOT.DSN"))
    assert b"D20" in chunk
    assert b"7SEGCOMA" in chunk
    assert b"7SEGCOMK" in chunk
    assert not any(marker in chunk for marker in (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT"))


def test_component_placement_display_bridge_is_immutable(tmp_path: Path) -> None:
    baseline = generate_component_placement_project(
        {"components": {"7segcomanode": 1}},
        tmp_path / "display_bridge_default.pdsprj",
    )
    hidden = generate_component_placement_project(
        {
            "components": {"7segcomanode": 1},
            "hide_display_bridge": True,
            "display_bridge_coordinate_mode": "display_small_relative",
        },
        tmp_path / "display_bridge_hidden.pdsprj",
    )

    assert baseline.valid
    assert hidden.valid
    baseline_d20 = next(group for group in baseline.selected_groups if group.key == "D20")
    hidden_d20 = next(group for group in hidden.selected_groups if group.key == "D20")
    assert baseline_d20.data == hidden_d20.data
    d20_entry = next(
        entry
        for entry in hidden.layout_plan["actual_binary_placements"]
        if entry["key"] == "D20"
    )
    assert d20_entry["translated"] is False
    assert d20_entry["coordinate_mode"] == "preserve_donor"
    assert "D20 movement request ignored" in hidden.cdb_policy


def test_terminal_dispatcher_ignores_d20_display_bridge_when_display_only(
    tmp_path: Path,
) -> None:
    base = tmp_path / "display_only_terminal_base.pdsprj"
    output = tmp_path / "display_only_terminal_output.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {
                "7SEG-COM-AN-BLUE": 1,
                "7SEG-COM-CAT-BLUE": 1,
            },
            "layout": {"strategy": "beautify"},
        },
        base,
        full_cdb=True,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
    )

    assert result.valid
    assert any(group.key == "D20" for group in result.selected_groups)
    assert report["valid"] is True
    assert report["eligible_families"] == []
    assert report["terminalized_component_count"] == 0
    assert report["terminal_count_added"] == 0
    assert base.read_bytes() == output.read_bytes()


def test_terminal_dispatcher_preserves_d20_when_real_diode_is_terminalized(
    tmp_path: Path,
) -> None:
    base = tmp_path / "display_diode_terminal_base.pdsprj"
    output = tmp_path / "display_diode_terminal_output.pdsprj"
    result = generate_component_placement_project(
        {
            "components": {
                "DIODE": 1,
                "7SEG-COM-AN-BLUE": 1,
                "7SEG-COM-CAT-BLUE": 1,
            },
            "layout": {"strategy": "beautify"},
        },
        base,
        full_cdb=True,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
    )

    assert result.valid
    assert [group.key for group in result.selected_groups].count("D20") == 1
    assert report["valid"] is True
    assert report["eligible_families"] == ["DIODE"]
    assert report["terminalized_component_count"] == 1
    assert report["terminal_count_added"] == 2
    assert report["wire_count_added"] == 2
    assert any(row["component_key"] == "D20" for row in report["preserved_groups"])
    terminalized_keys = {
        pair["component_key"]
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
    }
    assert "D20" not in terminalized_keys
    assert len(terminalized_keys) == 1


def test_component_placement_beautifies_each_display_row_separately(tmp_path: Path) -> None:
    anode = generate_component_placement_project(
        {
            "components": {"7segcomanode": 3},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
                "hide_display_bridge": True,
                "display_bridge_coordinate_mode": "display_small_relative",
            },
        },
        tmp_path / "anode_rows.pdsprj",
    )
    cathode = generate_component_placement_project(
        {
            "components": {"7segcomk": 3},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
                "hide_display_bridge": True,
                "display_bridge_coordinate_mode": "display_small_relative",
            },
        },
        tmp_path / "cathode_rows.pdsprj",
    )

    assert anode.valid
    assert cathode.valid
    anode_rows = [group for group in anode.selected_groups if group.key.startswith("DISPLAY_AN_")]
    cathode_rows = [group for group in cathode.selected_groups if group.key.startswith("DISPLAY_CC_")]
    assert len(anode_rows) == 3
    assert len(cathode_rows) == 3
    assert not any(group.key == "DISPLAY_ANODE_SENTINEL" for group in cathode.selected_groups)
    assert cathode_rows[-1].data.endswith(b"\xff")

    anode_entries = [
        entry
        for entry in anode.layout_plan["actual_binary_placements"]
        if entry["key"].startswith("DISPLAY_AN_")
    ]
    cathode_entries = [
        entry
        for entry in cathode.layout_plan["actual_binary_placements"]
        if entry["key"].startswith("DISPLAY_CC_")
    ]
    assert len(anode_entries) == 3
    assert len(cathode_entries) == 3
    assert all(entry["translated"] for entry in (*anode_entries, *cathode_entries))
    assert len({entry["slot"] for entry in anode_entries}) == 3
    assert len({entry["slot"] for entry in cathode_entries}) == 3


def test_locked_display_finalizer_matches_proteus_saved_row_tail(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"7SEG-COM-AN-RED": 9},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "anode_red_display_final_tail.pdsprj",
        full_cdb=True,
    )

    final_display = next(
        group
        for group in result.selected_groups
        if group.key.startswith("DISPLAY_AN_") and group.key.endswith("_FINAL")
    )
    chunk = _extract_object_chunk(read_internal_file(result.output, "ROOT.DSN"))

    assert result.valid
    assert result.request == {"7SEG-COM-AN-BLUE": 9}
    assert final_display.data.endswith(b"\x00\xff")
    assert final_display.source_is_final is True
    assert final_display.data in chunk


def test_display_mixed_request_keeps_display_dsn_prefix(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {
                "7SEG-COM-AN-RED": 1,
                "SWITCH": 1,
                "POT-HG": 1,
            },
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "display_with_controls_prefix.pdsprj",
        full_cdb=True,
    )
    chunk = _extract_object_chunk(read_internal_file(result.output, "ROOT.DSN"))

    assert result.valid
    assert chunk[:2] == b"\x00\x00"


def test_display_band_starts_after_actual_mixed_layout_bbox(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {
                "OPAMP": 20,
                "LM317T": 20,
                "TRAN-2P2S": 20,
                "7SEG-COM-AN-RED": 5,
            },
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "display_after_tall_mixed_layout.pdsprj",
        full_cdb=True,
    )
    entries = result.layout_plan["actual_binary_placements"]

    assert result.valid
    assert layout_overlap_pairs(entries) == []
    assert result.validation_reports["generated_output_validator"]["valid"] is True


def test_arrangement_next_start_slot_uses_actual_bbox_max_y() -> None:
    entries = [{"after_bbox": {"max_y": 10_160_000}}]

    next_slot = next_start_slot_after_layout_entries(
        entries,
        fallback_slot=3,
        origin_y=-5_080_000,
        slot_y=2_540_000,
        columns=10,
        gap_y=5_080_000,
    )

    assert next_slot > 3
    assert next_slot % 10 == 0


def test_beautifier_validator_flags_multipart_packet_without_failing_layout() -> None:
    issues = validate_beautifier_layout_entries(
        [
            {
                "key": "U1",
                "translated": True,
                "refs": ["U1:A", "U1:B"],
                "after_bbox": {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1},
            }
        ]
    )

    assert [issue.code for issue in issues] == ["W_BEAUTIFIER_MULTIPART_PACKET_NOT_SPLIT"]
    assert issues[0].severity == "warning"


def test_beautifier_validator_accepts_spread_multipart_packet() -> None:
    issues = validate_beautifier_layout_entries(
        [
            {
                "key": "U1",
                "translated": True,
                "refs": ["U1:A", "U1:B"],
                "multipart_subpart_spread": {"applied": True},
                "after_bbox": {"min_x": 0, "min_y": 0, "max_x": 1, "max_y": 1},
            }
        ]
    )

    assert issues == []


def test_multipart_subparts_are_spread_with_large_internal_gap(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"4027": 1, "74HC266": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "multipart_spread_large_gap.pdsprj",
        full_cdb=True,
    )
    entries = {
        entry["family"]: entry
        for entry in result.layout_plan["actual_binary_placements"]
        if entry["family"] in {"4027", "74HC266"}
    }

    assert result.valid
    assert entries["4027"]["multipart_subpart_spread"]["applied"] is True
    assert entries["74HC266"]["multipart_subpart_spread"]["applied"] is True
    ff_boxes = entries["4027"]["multipart_subpart_spread"]["subpart_bboxes_after"]
    assert ff_boxes["U13:B"]["min_y"] - ff_boxes["U13:A"]["max_y"] >= 5_080_000
    logic_boxes = entries["74HC266"]["multipart_subpart_spread"]["subpart_bboxes_after"]
    assert logic_boxes["U77:B"]["min_x"] - logic_boxes["U77:A"]["max_x"] >= 5_080_000
    assert logic_boxes["U77:C"]["min_y"] - logic_boxes["U77:A"]["max_y"] >= 5_080_000
    assert result.validation_reports["generated_output_validator"]["valid"] is True


def test_mixed_layout_keeps_large_visual_spacing_between_types(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {
                "4027": 3,
                "74HC266": 3,
                "OPAMP": 3,
                "LM317T": 3,
                "TRAN-2P2S": 3,
                "CAP": 3,
            },
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "mixed_large_visual_spacing.pdsprj",
        full_cdb=True,
    )
    entries = result.layout_plan["actual_binary_placements"]

    assert result.valid
    assert layout_overlap_pairs(entries) == []
    assert layout_spacing_pairs(entries, min_spacing=1_524_000) == []
    assert layout_different_family_spacing_pairs(entries, min_spacing=3_810_000) == []
    assert any(entry.get("family_row_break") for entry in entries)
    assert result.validation_reports["generated_output_validator"]["valid"] is True


def test_component_placement_uses_registered_ic_coordinates(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"74HC160": 3},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "hc160_registered_coordinates.pdsprj",
        donor_path=_repo_path(NEW_COMPONENT_MEGA_DONOR),
        full_cdb=True,
    )

    assert result.valid
    entries = [
        entry
        for entry in result.layout_plan["actual_binary_placements"]
        if entry["family"] == "74HC160"
    ]
    assert len(entries) == 3
    assert all(entry["translated"] for entry in entries)
    assert all(entry["coordinate_pair_count"] == 4 for entry in entries)
    assert all("component_text_or_body" not in entry["coordinate_reason_counts"] for entry in entries)
    assert result.validation_reports["generated_output_validator"]["valid"] is True


def test_component_placement_ic_beautifier_reserves_multi_gate_footprints(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"74HC02": 12},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "hc02_footprint_shelf.pdsprj",
        donor_path=_repo_path(NEW_COMPONENT_MEGA_DONOR),
        full_cdb=True,
    )

    assert result.valid
    entries = [
        entry
        for entry in result.layout_plan["actual_binary_placements"]
        if entry["family"] == "74HC02"
    ]
    assert len(entries) == 12
    assert all(entry["layout_mode"] == "footprint_shelf" for entry in entries)
    assert all(entry["allocation_width"] >= entry["before_bbox"]["width"] for entry in entries)
    assert result.validation_reports["generated_output_validator"]["valid"] is True

    bboxes = [(entry["key"], entry["after_bbox"]) for entry in entries]
    for left_index, (left_key, left) in enumerate(bboxes):
        for right_key, right in bboxes[left_index + 1 :]:
            separated = (
                left["max_x"] <= right["min_x"]
                or right["max_x"] <= left["min_x"]
                or left["max_y"] <= right["min_y"]
                or right["max_y"] <= left["min_y"]
            )
            assert separated, f"{left_key} overlaps {right_key}"


def test_component_placement_honors_wider_dil14_mvp_shelf(tmp_path: Path) -> None:
    """A wider normal shelf keeps a 15-package DIL14 project to two rows.

    This is deliberately a placement-stage test.  It establishes the frame
    consumed by the catalogue terminal stage without changing terminal
    geometry, links, or WIRE construction.
    """

    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"74HC08": 15},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
                "shelf_width": 75_000_000,
            },
        },
        tmp_path / "hc08_15x_two_row_mvp_shelf.pdsprj",
        full_cdb=True,
    )
    entries = [
        entry
        for entry in result.layout_plan["actual_binary_placements"]
        if entry["family"] == "74HC08"
    ]

    assert result.valid
    assert len(entries) == 15
    assert max(int(entry["row"]) for entry in entries) == 1
    assert all(entry["layout_shelf_width"] == 75_000_000 for entry in entries)
    assert layout_overlap_pairs(entries) == []
    assert result.validation_reports["generated_output_validator"]["valid"] is True


def test_component_placement_mixed_ic_non_ic_beautifier_uses_separate_bands(
    tmp_path: Path,
) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                "74HC08": 2,
                "RESISTOR": 2,
                "CAP": 2,
                "REALIND": 2,
                "DIODE": 2,
                "NPN": 2,
            },
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "mixed_ic_non_ic_separate_bands.pdsprj",
        full_cdb=True,
    )

    entries = result.layout_plan["actual_binary_placements"]
    ic_entries = [entry for entry in entries if entry["layout_band"] == "ic"]
    non_ic_entries = [
        entry for entry in entries if entry["layout_band"] == "non_ic"
    ]
    ic_max_y = max(int(entry["after_bbox"]["max_y"]) for entry in ic_entries)
    non_ic_min_y = min(
        int(entry["after_bbox"]["min_y"]) for entry in non_ic_entries
    )

    assert result.valid
    assert {entry["family"] for entry in ic_entries} == {"74HC08"}
    assert {entry["family"] for entry in non_ic_entries} == {
        "RESISTOR",
        "CAP",
        "REALIND",
        "DIODE",
        "NPN",
    }
    assert all(entry["mixed_band_separation"] for entry in entries)
    assert non_ic_min_y - ic_max_y >= MIXED_LAYOUT_BAND_GAP_Y
    assert result.validation_reports["generated_output_validator"]["valid"] is True


def test_component_placement_generator_uses_clean_source_packets(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"CSOURCE": 5, "VPULSE": 5, "VSOURCE": 5},
        },
        tmp_path / "clean_sources.pdsprj",
    )

    assert result.valid
    source_groups = [group for group in result.selected_groups if group.family in {"CSOURCE", "VPULSE", "VSOURCE"}]
    assert len(source_groups) == 15
    assert all(group.data.endswith(b"\x00") for group in source_groups)
    assert all(len(group.data) >= 344 for group in source_groups if group.family == "CSOURCE")
    assert all(len(group.data) >= 347 for group in source_groups if group.family == "VPULSE")
    assert all(len(group.data) >= 343 for group in source_groups if group.family == "VSOURCE")


def test_component_placement_generator_accepts_payload_donor_path(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(donor),
            "components": {"FUSE": 1, "SWITCH": 1, "POT-HG": 1},
        },
        tmp_path / "explicit_path.pdsprj",
    )

    assert result.valid
    assert result.donor == donor
    assert result.control_strategy == "accepted"
    assert result.request["FUSE"] == 1


def test_component_placement_generator_rejects_nonlocked_payload_donor_manifest_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="locked to"):
        generate_component_placement_project(
            {
                "donor": "component_placer_main_semimega_sources_20260618",
                "components": {"VSOURCE": 1, "CSOURCE": 1, "VSINE": 1},
            },
            tmp_path / "explicit_manifest_id.pdsprj",
        )


def test_component_placement_generator_accepts_explicit_new_donor_transformer(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": {"path": str(donor)},
            "components": {"TRANSFORMER": 1},
        },
        tmp_path / "explicit_transformer.pdsprj",
    )

    assert result.valid
    assert result.request == {"TRAN-2P2S": 1}
    chunk = _extract_object_chunk(read_internal_file(result.output, "ROOT.DSN"))
    assert b"TRAN-2P2S" in chunk
    assert b"$TERBIDIR" not in chunk


def test_component_placement_generator_avoids_led_final_record(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(donor),
            "components": {"LED-RED": 1, "RESISTOR": 1},
        },
        tmp_path / "led_resistor_safe_finalizer.pdsprj",
    )

    assert result.valid
    final_group = sorted(result.selected_groups, key=lambda group: group.start)[-1]
    assert final_group.family == "RESISTOR"


def test_component_placement_generator_uses_complete_gate_packages(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(donor),
            "components": {"74HC08": 7},
        },
        tmp_path / "complete_hc08_packages.pdsprj",
    )

    hc08_groups = [group for group in result.selected_groups if group.family == "74HC08"]
    assert len(hc08_groups) == 7
    assert len({group.key for group in hc08_groups}) == 7
    assert all(len(group.refs) == 4 for group in hc08_groups)


def test_component_placement_generator_accepts_component_offsets(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(donor),
            "components": {"74HC00": 1},
            "component_offsets": {"74HC00": 4},
        },
        tmp_path / "hc00_offset.pdsprj",
    )

    hc00_groups = [group for group in result.selected_groups if group.family == "74HC00"]
    assert [group.key for group in hc00_groups] == ["U335"]


def test_component_placement_generator_uses_safe_hc00_default_offset(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(donor),
            "components": {"74HC00": 1},
        },
        tmp_path / "hc00_safe_default_offset.pdsprj",
    )

    hc00_groups = [group for group in result.selected_groups if group.family == "74HC00"]
    assert [group.key for group in hc00_groups] == ["U476"]


def test_component_placement_generator_rejects_synthetic_terminals(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    with pytest.raises(ValueError, match="Synthetic POWER/GROUND/TERMINAL placement is disabled"):
        generate_component_placement_project(
            {
                "donor": {"path": str(donor)},
                "components": {"TRANSFORMER": 1, "GROUND": 2, "TERMINAL": 3},
            },
            tmp_path / "terminal_rejected.pdsprj",
        )


def test_component_placement_generator_rejects_nonfinal_resistor_overflow(tmp_path: Path) -> None:
    donor = ROOT / "proteus_ic" / "donors" / "manual_downloads_20260618" / "new_component_mega" / "new_components_5x_mega.pdsprj"
    with pytest.raises(ValueError, match="Need 105 clean finalizable RESISTOR groups"):
        generate_component_placement_project(
            {
                "donor": str(donor),
                "components": {"RESISTOR": 105},
            },
            tmp_path / "resistor_overflow_rejected.pdsprj",
        )


def test_component_placement_manifest_records_next_pipeline_stages(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"SWITCH": 1, "POT-HG": 1, "FUSE": 1},
            "control_strategy": "hidden_dummy_control",
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "pipeline_manifest.pdsprj",
    )

    assert result.valid
    assert result.manifest_path is not None
    assert result.manifest_path.exists()
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["value_plan"]["stage"] == "value_changer"
    assert manifest["wiring_plan"]["wire_record_emission"]["applied"] is False
    assert manifest["layout_plan"]["strategy"] == "beautify"
    assert manifest["hidden_dummy_controls"]["long_term_owner"] == "beautifier"
    assert manifest["hidden_dummy_controls"]["controls"] == []
    assert manifest["validation_reports"]["component_packet_validator"]["valid"] is True
    assert manifest["validation_reports"]["generated_output_validator"]["valid"] is True


def test_component_placement_value_and_wiring_intent_are_planned(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {
                "RESISTOR": {"count": 1, "value": "4k7"},
                "CAP": 1,
            },
            "values": {"C1": "2uF"},
            "connections": [
                {
                    "net": "N_FILTER",
                    "from": {"component": "R1", "pin": "2"},
                    "to": {"component": "C1", "pin": "1"},
                }
            ],
        },
        tmp_path / "value_wiring_plan.pdsprj",
    )

    assert result.valid
    value_requests = result.value_plan["requests"]
    assert {"family": "RESISTOR", "target": "R1", "value": "4k7", "source": "components.value"} in value_requests
    assert any(row["family"] == "CAP" and row["target"] == "C1" and row["value"] == "2uF" for row in value_requests)
    assert result.value_plan["binary_mutation"]["applied"] is True
    assert result.wiring_plan["same_net_groups"] == [
        {
            "net": "N_FILTER",
            "endpoints": [
                {"component": "R1", "pin": "2"},
                {"component": "C1", "pin": "1"},
            ],
        }
    ]
    pin_terminal_plan = result.wiring_plan["pin_terminal_plan"]
    assert pin_terminal_plan["binary_emission"]["applied"] is False
    assert pin_terminal_plan["pin_class_counts"] == {"two_pin": 2}
    assert pin_terminal_plan["terminal_emit_ready_count"] == 2
    assert pin_terminal_plan["blocked_terminal_count"] == 0


def test_cap_elec_selection_uses_strict_cdb_backed_packets(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"CAP-ELEC": 15},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "cap_elec_strict_selection.pdsprj",
    )

    assert result.valid
    cap_elec_groups = [group for group in result.selected_groups if group.family == "CAP-ELEC"]
    assert len(cap_elec_groups) == 15
    assert {len(group.data) for group in cap_elec_groups} <= {352, 379}
    assert all(b"CAP-ELEC" in group.data and b"1uF" in group.data for group in cap_elec_groups)


def test_value_changer_rejects_bad_same_length_cap_elec_value(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"CAP-ELEC": {"count": 1, "value": "10u"}},
        },
        tmp_path / "bad_cap_elec_value_rejected.pdsprj",
    )

    assert not result.valid
    assert result.value_plan["valid"] is False
    assert any("CAP-ELEC value '10u'" in row["message"] for row in result.value_plan["errors"])


def test_terminal_planner_covers_all_selected_families_and_uses_role_angles(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"74HC00": 1, "RESISTOR": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "terminal_orientation_probe_base.pdsprj",
    )

    assert result.valid
    specs = plan_side_bidir_terminals(result.selected_groups, label_prefix="T")
    assert specs
    assert {"74HC00", "RESISTOR"} <= {spec.component_family for spec in specs}
    assert all(spec.angle_tenths == 1800 for spec in specs if spec.pin_hint.startswith("left"))
    assert all(spec.angle_tenths == 0 for spec in specs if spec.pin_hint.startswith("right"))


def test_resistor_terminal_planner_uses_pin_geometry_not_bbox(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"RESISTOR": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "resistor_terminal_geometry_base.pdsprj",
    )

    pairs = plan_attached_resistor_terminals(result.selected_groups, label_prefix="R")

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.right_pin_x - pair.left_pin_x == RESISTOR_PIN_SPAN
    assert pair.left.symbol_x == pair.left_pin_x - TERMINAL_SYMBOL_TO_PIN
    assert pair.right.symbol_x == pair.right_pin_x + TERMINAL_SYMBOL_TO_PIN
    assert pair.left_wire_start_x == pair.left_pin_x - TERMINAL_CONTACT_TO_PIN
    assert pair.right_wire_start_x == pair.right_pin_x + TERMINAL_CONTACT_TO_PIN
    assert pair.left.angle_tenths == 1800
    assert pair.right.angle_tenths == 0


def test_resistor_terminal_attachment_patches_links_and_adds_short_wires(tmp_path: Path) -> None:
    base = tmp_path / "resistor_terminal_attach_base.pdsprj"
    output = tmp_path / "resistor_terminal_attach.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"RESISTOR": 3},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_resistor_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        label_prefix="R",
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    assert report["valid"] is True
    assert report["family_handler"] == "RESISTOR/v3"
    assert report["terminal_count_added"] == 6
    assert report["wire_count_added"] == 6
    assert chunk.count(b"$TERBIDIR") == 6
    assert chunk.count(b"\x7fWIRE") == 6
    assert chunk.endswith(b"\xff")
    for pair in report["terminal_pairs"]:
        for terminal in (pair["left"], pair["right"]):
            suffix = bytes.fromhex(terminal["suffix"])
            little_endian_suffix = suffix[::-1]
            assert chunk.count(little_endian_suffix) >= 2


@pytest.mark.parametrize(
    "family",
    ["NPN", "PNP", "NMOSFET", "2N3904", "2N4401", "2N7000", "BS170"],
)
def test_three_pin_transistor_catalogue_terminal_attachment(
    tmp_path: Path,
    family: str,
) -> None:
    base = tmp_path / f"{family}_catalogue_terminal_base.pdsprj"
    output = tmp_path / f"{family}_catalogue_terminal_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 1},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=[family],
    )
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    assert result.valid
    assert report["valid"] is True
    assert report["terminal_count_added"] == 3
    assert report["wire_count_added"] == 3
    assert report["terminalized_component_count"] == 1
    assert report["wire_path_contacts_valid"] is True
    assert report["terminal_grid_alignment_valid"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert chunk.count(b"\x7fWIRE") == 3
    terminal_offset = chunk.find(b"$TERBIDIR")
    component_offset = chunk.find(family.encode("ascii"))
    wire_offset = chunk.find(b"\x7fWIRE")
    assert min(terminal_offset, component_offset, wire_offset) >= 0
    if family in {"NPN", "PNP", "2N3904", "2N4401"}:
        assert terminal_offset < component_offset < wire_offset
        assert chunk[:2] == b"\x00\x10"
        assert terminal_placer._bidir_label_records(chunk)[0]["start"] == 1
        assert report["object_stream_finalizer"] == "append_explicit_single_ff"
        assert chunk[-1:] == b"\xff"
        assert terminal_placer._wire_record_spans(chunk)[-1][1] == len(chunk) - 1
        wire_rows = terminal_placer._wire_rows_from_chunk(chunk, chunk_start=0)
        if family in {"NPN", "PNP"}:
            assert all(
                tuple(row["coordinates"][:2]) == tuple(row["coordinates"][2:4])
                for row in wire_rows
            )
            assert all(
                not row["wire_is_nonzero"] and row["zero_length_wire_allowed"]
                for row in report["wire_path_contact_checks"]
            )
        else:
            expected_pin_coordinates = {
                "B": (-6_858_000, -4_973_320),
                "C": (-6_096_000, -4_211_320),
                "E": (-6_096_000, -5_735_320),
            }
            terminal_pins = report["family_reports"][0]["terminal_pins"]
            assert {
                str(row["pin"]["name"]): (
                    int(row["pin"]["x"]), int(row["pin"]["y"])
                )
                for row in terminal_pins
            } == expected_pin_coordinates
            assert all(
                row["coordinate_source"].startswith(
                    "component_marker_anchor_offset"
                )
                for row in terminal_pins
            )
            assert all(
                row["wire_is_nonzero"] and not row["zero_length_wire_allowed"]
                for row in report["wire_path_contact_checks"]
            )
            assert all(
                tuple(row["coordinates"][:2]) != tuple(row["coordinates"][2:4])
                for row in wire_rows
            )
            assert all(
                abs(int(row["coordinates"][1]) - int(row["coordinates"][3]))
                == 106_680
                for row in wire_rows
            )
        terminal_labels = [
            row["label"]
            for row in terminal_placer._bidir_label_records(chunk)
        ]
        expected_terminal_labels = (
            ["BASE", "COLLECTOR", "EMITTER"]
            if family == "PNP"
            else ["COLLECTOR", "EMITTER", "BASE"]
        )
        expected_pin_order = (
            ["B", "C", "E"] if family == "PNP" else ["C", "E", "B"]
        )
        assert terminal_labels == expected_terminal_labels
        assert report["family_reports"][0][
            "clean_packet_attachment_order"
        ] == "terminal_leading_component_then_wires"
        assert report["family_reports"][0][
            "donor_terminal_record_order"
        ] == expected_pin_order
        assert report["family_reports"][0][
            "last_appended_wire_tail_policy"
        ] == "trim_trailing_zero_before_finalizer"
        assert Path(report["family_reports"][0]["catalogue_source_project"]).exists()
        assert all(
            row["terminal_trailer"] == "0200"
            and row["component_trailer"] == "0200"
            for row in report["terminal_suffix_link_checks"]
        )
        assert all(
            pin["catalogue_geometry"]["donor_component_link_trailer"] == "0100"
            and pin["catalogue_geometry"]["component_link_trailer"] == "0200"
            for pin in report["family_reports"][0]["terminal_pins"]
        )
        output_cdb = read_internal_file(output, "ROOT.CDB")
        parsed_output_cdb = parse_component_placer_cdb(output_cdb)
        assert parsed_output_cdb.count == len(parsed_output_cdb.pin_rows) == 1
        assert len(parsed_output_cdb.property_rows) == 1
        assert int.from_bytes(
            parsed_output_cdb.between_sections[-4:], "little"
        ) == 1
        assert report["cdb_normalization"]["keep_packages"] == [
            result.selected_groups[0].key
        ]
        if family == "NPN":
            proteus_saved = (
                ROOT
                / "experiments"
                / "bjt_npn_live_proteus_diagnostics_temp_2026_07_11"
                / "H08_H07_PROTEUS_CTRL_S_NORMALIZATION.pdsprj"
            )
            assert output_cdb == read_internal_file(proteus_saved, "ROOT.CDB")
    else:
        assert component_offset < terminal_offset < wire_offset
        assert report["object_stream_finalizer"] == "double_ff"
        assert chunk.endswith(b"\xff\xff")
        wire_coordinate_lengths = sorted(
            len(pin["short_wire"]["coordinates"])
            for family_report in report["family_reports"]
            for pin in family_report["terminal_pins"]
        )
        assert wire_coordinate_lengths == [4, 8, 8]


@pytest.mark.parametrize("family", ["NPN", "PNP"])
@pytest.mark.parametrize("count", [2, 4])
def test_donor_proven_bjt_terminal_leading_scaling(
    tmp_path: Path,
    family: str,
    count: int,
) -> None:
    base = tmp_path / f"{family}_{count}x_bjt_scaling_base.pdsprj"
    output = tmp_path / f"{family}_{count}x_bjt_scaling_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: count},
            "layout": {"strategy": "beautify"},
        },
        base,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=[family],
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = parse_component_placer_cdb(read_internal_file(output, "ROOT.CDB"))

    assert result.valid
    assert report["valid"] is True
    assert report["terminalized_component_count"] == count
    assert report["terminal_count_added"] == count * 3
    assert report["wire_count_added"] == count * 3
    assert chunk.count(BIDIR_MARKER) == count * 3
    assert chunk.count(b"\x7fWIRE") == count * 3
    assert chunk[-1:] == b"\xff"
    assert len(cdb.pin_rows) == count
    assert len(cdb.property_rows) == count
    assert int.from_bytes(cdb.between_sections[-4:], "little") == count
    terminals = terminal_placer._bidir_label_records(chunk)
    labels_per_block = 3
    expected_labels = (
        ["BASE", "COLLECTOR", "EMITTER"]
        if family == "PNP"
        else ["COLLECTOR", "EMITTER", "BASE"]
    )
    assert [row["label"] for row in terminals] == expected_labels * count
    component_markers = [
        chunk.find(group.key.encode("ascii"))
        for group in result.selected_groups
    ]
    assert all(marker >= 0 for marker in component_markers)
    assert terminals[labels_per_block - 1]["start"] < component_markers[0]


def test_bjt_progressive_scaling_is_promoted_through_proven_24x(tmp_path: Path) -> None:
    base = tmp_path / "NPN_9x_progressive_base.pdsprj"
    output = tmp_path / "NPN_9x_progressive_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"NPN": 9},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=["NPN"],
    )

    assert report["valid"] is True
    assert report["progressive_scaling_enabled"] is False
    assert report["terminalized_component_count"] == 9


@pytest.mark.parametrize("family", ["NPN", "PNP", "2N3904", "2N4401"])
@pytest.mark.parametrize("count", [9, 15, 24])
def test_bjt_progressive_scaling_user_requested_counts(
    tmp_path: Path,
    family: str,
    count: int,
) -> None:
    base = tmp_path / f"{family}_{count}x_progressive_base.pdsprj"
    output = tmp_path / f"{family}_{count}x_progressive_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: count},
            "layout": {"strategy": "beautify"},
        },
        base,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=[family],
        allow_progressive_scaling=True,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = parse_component_placer_cdb(read_internal_file(output, "ROOT.CDB"))

    assert result.valid
    assert report["valid"] is True
    assert report["progressive_scaling_enabled"] is True
    assert report["terminalized_component_count"] == count
    assert report["terminal_count_added"] == count * 3
    assert report["wire_count_added"] == count * 3
    assert report["wire_path_contacts_valid"] is True
    assert report["terminal_grid_alignment_valid"] is True
    assert chunk.count(BIDIR_MARKER) == count * 3
    assert chunk.count(b"\x7fWIRE") == count * 3
    assert chunk[-1:] == b"\xff"
    assert len(cdb.pin_rows) == count
    assert len(cdb.property_rows) == count
    assert int.from_bytes(cdb.between_sections[-4:], "little") == count
    expected_labels = (
        ["BASE", "COLLECTOR", "EMITTER"]
        if family == "PNP"
        else ["COLLECTOR", "EMITTER", "BASE"]
    )
    assert [row["label"] for row in terminal_placer._bidir_label_records(chunk)] == (
        expected_labels * count
    )
    if family in {"2N3904", "2N4401"}:
        assert all(
            int(row["short_wire"]["start"]["x"])
            != int(row["short_wire"]["end"]["x"])
            or int(row["short_wire"]["start"]["y"])
            != int(row["short_wire"]["end"]["y"])
            for family_report in report["family_reports"]
            for row in family_report["terminal_pins"]
        )


def test_capacitor_terminal_planner_uses_body_center_plus_half_span(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"CAP": 1},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "capacitor_terminal_geometry_base.pdsprj",
    )

    pairs = plan_attached_capacitor_terminals(result.selected_groups, label_prefix="C")

    assert len(pairs) == 1
    pair = pairs[0]
    assert pair.right_pin_x - pair.left_pin_x == CAP_PIN_HALF_SPAN * 2
    assert pair.left.symbol_x == pair.left_pin_x - CAP_TERMINAL_SYMBOL_TO_PIN
    assert pair.right.symbol_x == pair.right_pin_x + CAP_TERMINAL_SYMBOL_TO_PIN
    assert pair.left_wire_start_x == pair.left_pin_x
    assert pair.right_wire_start_x == pair.right_pin_x
    assert pair.left.angle_tenths == 1800
    assert pair.right.angle_tenths == 0
    assert pair.left.label == "C0"
    assert pair.right.label == "C1"
    assert pair.left.suffix == 0x011A
    assert pair.right.suffix == 0x00E8


def test_capacitor_terminal_attachment_preserves_native_order_and_record_sizes(
    tmp_path: Path,
) -> None:
    base = tmp_path / "capacitor_terminal_attach_base.pdsprj"
    output = tmp_path / "capacitor_terminal_attach.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"CAP": 3},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_capacitor_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        label_prefix="C",
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    bidir_records = extract_bidir_records(chunk)
    bidir_labels = [
        record[31 : 31 + record[30]].decode("ascii")
        for record in bidir_records
    ]
    wire_coordinates: list[tuple[int, int, int, int]] = []
    search_from = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", search_from)
        if marker < 0:
            break
        start = marker - 23
        wire_coordinates.append(
            tuple(
                int.from_bytes(chunk[start + offset : start + offset + 4], "little", signed=True)
                for offset in (33, 37, 41, 45)
            )
        )
        search_from = marker + 1

    assert report["valid"] is True
    assert report["family_handler"] == "CAP/v2"
    assert report["object_order"] == (
        "right_bidir_array_then_left_bidir_component_left_wire_right_wire_groups"
    )
    assert report["terminal_count_added"] == 6
    assert report["wire_count_added"] == 6
    assert chunk.count(b"$TERBIDIR") == 6
    assert chunk.count(b"\x7fWIRE") == 6
    assert chunk.endswith(b"\xff")
    assert bidir_labels == ["C1", "C3", "C5", "C0", "C2", "C4"]
    assert [item["right_wire_size"] for item in report["group_records"]] == [49, 49, 50]
    assert all(item["left_wire_size"] == 50 for item in report["group_records"])
    assert all(
        item["component_record_size"] == item["bare_component_size"] + 1
        for item in report["group_records"]
    )
    assert all(x1 == x2 and y1 == y2 for x1, y1, x2, y2 in wire_coordinates)
    for pair in report["terminal_pairs"]:
        for terminal in (pair["left"], pair["right"]):
            suffix = bytes.fromhex(terminal["suffix"])
            little_endian_suffix = suffix[::-1]
            assert chunk.count(little_endian_suffix) >= 2


def test_inductor_terminal_planner_uses_donor05_geometry_and_suffixes(
    tmp_path: Path,
) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"REALIND": 15},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "inductor_v2_geometry_base.pdsprj",
    )

    pairs = plan_attached_inductor_terminals(result.selected_groups)

    assert len(pairs) == 15
    assert pairs[0].component_key == "L21"
    assert pairs[13].component_key == "L34"
    assert pairs[0].left.label == "L0"
    assert pairs[0].right.label == "L1"
    assert pairs[0].left.suffix == 0x01B2
    assert pairs[0].right.suffix == 0x01E4
    assert pairs[1].left.suffix - pairs[0].left.suffix == 0x02A8
    assert pairs[1].right.suffix - pairs[0].right.suffix == 0x02A8
    for pair in pairs:
        assert pair.right_pin_x - pair.left_pin_x == INDUCTOR_PIN_HALF_SPAN * 2
        assert pair.left.symbol_x == pair.left_pin_x - INDUCTOR_TERMINAL_SYMBOL_TO_PIN
        assert pair.right.symbol_x == pair.right_pin_x + INDUCTOR_TERMINAL_SYMBOL_TO_PIN
        assert pair.left_wire_start_x == pair.left_pin_x
        assert pair.right_wire_start_x == pair.right_pin_x
        assert pair.left.angle_tenths == 1800
        assert pair.right.angle_tenths == 0


def test_inductor_v2_attachment_uses_sequential_groups_and_donor_boundaries(
    tmp_path: Path,
) -> None:
    base = tmp_path / "inductor_v2_base.pdsprj"
    output = tmp_path / "inductor_v2_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"REALIND": 15},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    bidir_records = extract_bidir_records(chunk)
    labels = [
        record[31 : 31 + record[30]].decode("ascii")
        for record in bidir_records
    ]
    cursor = 1
    wire_coordinates: list[tuple[int, int, int, int]] = []
    component_sizes: list[int] = []
    pairs = report["family_reports"][0]["terminal_pairs"]
    right_wire_sizes: list[int] = []
    for index, pair in enumerate(pairs):
        left_record = bidir_records[index * 2]
        right_record = bidir_records[index * 2 + 1]
        assert chunk[cursor : cursor + len(left_record)] == left_record
        cursor += len(left_record)
        assert chunk[cursor : cursor + len(right_record)] == right_record
        cursor += len(right_record)
        wire_marker = chunk.find(b"\x7fWIRE", cursor)
        wire_start = wire_marker - 23
        component = chunk[cursor:wire_start]
        component_sizes.append(len(component))
        assert component.startswith(b"\x00\xff")
        x_offset = pair["packet_offsets"]["component_x"] + 1
        assert component[x_offset + 25 : x_offset + 27] == bytes.fromhex(
            pair["left"]["suffix"]
        )[::-1]
        assert component[x_offset + 29 : x_offset + 31] == bytes.fromhex(
            pair["right"]["suffix"]
        )[::-1]
        cursor = wire_start
        left_wire = chunk[cursor : cursor + 50]
        cursor += 50
        right_size = 50 if index == len(pairs) - 1 else 49
        right_wire_sizes.append(right_size)
        right_wire = chunk[cursor : cursor + right_size]
        cursor += right_size
        for wire in (left_wire, right_wire):
            marker = wire.find(b"\x7fWIRE")
            start = marker - 23
            wire_coordinates.append(
                tuple(
                    int.from_bytes(
                        wire[start + offset : start + offset + 4],
                        "little",
                        signed=True,
                    )
                    for offset in (33, 37, 41, 45)
                )
            )

    assert report["valid"] is True
    assert report["family_handler"] == "MIXED/native-wire-v10-grid-snapped"
    assert report["object_order"] == (
        "native_leading_terminal_arrays_then_original_component_order_with_"
        "family_profile_terminal_component_wire_units"
    )
    assert report["terminal_count_added"] == 30
    assert report["wire_count_added"] == 30
    assert chunk.count(b"$TERBIDIR") == 30
    assert chunk.count(b"\x7fWIRE") == 30
    assert labels == [
        label
        for pair in pairs
        for label in (pair["left"]["label"], pair["right"]["label"])
    ]
    assert right_wire_sizes == [*([49] * 14), 50]
    assert component_sizes[-2:] == [375, 375]
    expected_wire_coordinates = [
        (
            pair["short_wires"][role]["start"]["x"],
            pair["short_wires"][role]["start"]["y"],
            pair["short_wires"][role]["end"]["x"],
            pair["short_wires"][role]["end"]["y"],
        )
        for pair in pairs
        for role in ("left", "right")
    ]
    assert wire_coordinates == expected_wire_coordinates
    assert report["terminal_grid_alignment_valid"] is True
    assert cursor == len(chunk)
    assert chunk.endswith(b"\xff")


def test_cap_elec_terminal_planner_uses_accepted_eight_donor_geometry(
    tmp_path: Path,
) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"CAP-ELEC": 15},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "cap_elec_v3_geometry_base.pdsprj",
    )

    pairs = plan_attached_electrolytic_capacitor_terminals(result.selected_groups)

    assert len(pairs) == 15
    assert pairs[0].component_key == "C62"
    assert pairs[14].component_key == "C76"
    assert "C75" in {pair.component_key for pair in pairs}
    assert pairs[0].left.label == "E0"
    assert pairs[0].right.label == "E1"
    assert pairs[0].left.suffix == 0x0120
    assert pairs[0].right.suffix == 0x0152
    assert pairs[1].left.suffix - pairs[0].left.suffix == 0x02A8
    assert pairs[1].right.suffix - pairs[0].right.suffix == 0x02A8
    for pair in pairs:
        assert pair.right_pin_x - pair.left_pin_x == CAP_ELEC_PIN_HALF_SPAN * 2
        assert (
            pair.left.symbol_x
            == pair.left_pin_x - CAP_ELEC_TERMINAL_SYMBOL_TO_PIN
        )
        assert (
            pair.right.symbol_x
            == pair.right_pin_x + CAP_ELEC_TERMINAL_SYMBOL_TO_PIN
        )
        assert pair.left_wire_start_x == pair.left_pin_x
        assert pair.right_wire_start_x == pair.right_pin_x
        assert pair.left.angle_tenths == 1800
        assert pair.right.angle_tenths == 0


def test_cap_elec_v3_attachment_preserves_right_left_sequential_donor_groups(
    tmp_path: Path,
) -> None:
    base = tmp_path / "cap_elec_v3_base.pdsprj"
    output = tmp_path / "cap_elec_v3_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"CAP-ELEC": 15},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    bidir_records = extract_bidir_records(chunk)
    labels = [
        record[31 : 31 + record[30]].decode("ascii")
        for record in bidir_records
    ]
    cursor = 1
    component_sizes: list[int] = []
    wire_coordinates: list[tuple[int, int, int, int]] = []
    expected_wire_coordinates: list[tuple[int, int, int, int]] = []
    pairs = report["family_reports"][0]["terminal_pairs"]
    right_wire_sizes: list[int] = []
    for index, pair in enumerate(pairs):
        right_record = bidir_records[index * 2]
        left_record = bidir_records[index * 2 + 1]
        assert chunk[cursor : cursor + len(right_record)] == right_record
        cursor += len(right_record)
        assert chunk[cursor : cursor + len(left_record)] == left_record
        cursor += len(left_record)

        wire_marker = chunk.find(b"\x7fWIRE", cursor)
        wire_start = wire_marker - 23
        component = chunk[cursor:wire_start]
        component_sizes.append(len(component))
        assert component.startswith(b"\x00\xff")
        x_offset = pair["packet_offsets"]["component_x"] + 1
        assert component[x_offset + 25 : x_offset + 27] == bytes.fromhex(
            pair["left"]["suffix"]
        )[::-1]
        assert component[x_offset + 29 : x_offset + 31] == bytes.fromhex(
            pair["right"]["suffix"]
        )[::-1]
        cursor = wire_start

        left_wire = chunk[cursor : cursor + 50]
        cursor += 50
        right_size = 50 if index == len(pairs) - 1 else 49
        right_wire_sizes.append(right_size)
        right_wire = chunk[cursor : cursor + right_size]
        cursor += right_size
        for wire in (left_wire, right_wire):
            marker = wire.find(b"\x7fWIRE")
            coordinate_start = marker - 23
            wire_coordinates.append(
                tuple(
                    int.from_bytes(
                        wire[coordinate_start + offset : coordinate_start + offset + 4],
                        "little",
                        signed=True,
                    )
                    for offset in (33, 37, 41, 45)
                )
            )
        expected_wire_coordinates.extend(
            (
                (
                    pair["short_wires"]["left"]["start"]["x"],
                    pair["short_wires"]["left"]["start"]["y"],
                    pair["short_wires"]["left"]["end"]["x"],
                    pair["short_wires"]["left"]["end"]["y"],
                ),
                (
                    pair["short_wires"]["right"]["start"]["x"],
                    pair["short_wires"]["right"]["start"]["y"],
                    pair["short_wires"]["right"]["end"]["x"],
                    pair["short_wires"]["right"]["end"]["y"],
                ),
            )
        )

    assert report["valid"] is True
    assert report["family_handler"] == "MIXED/native-wire-v10-grid-snapped"
    assert report["object_order"] == (
        "native_leading_terminal_arrays_then_original_component_order_with_"
        "family_profile_terminal_component_wire_units"
    )
    assert report["terminal_count_added"] == 30
    assert report["wire_count_added"] == 30
    assert chunk.count(b"$TERBIDIR") == 30
    assert chunk.count(b"\x7fWIRE") == 30
    assert labels == [
        label
        for pair in pairs
        for label in (pair["right"]["label"], pair["left"]["label"])
    ]
    assert right_wire_sizes == [*([49] * 14), 50]
    assert component_sizes == [380] * 15
    assert wire_coordinates == expected_wire_coordinates
    assert report["terminal_grid_alignment_valid"] is True
    assert cursor == len(chunk)
    assert chunk.endswith(b"\xff")


@pytest.mark.parametrize(
    ("family", "prefix", "expected_sizes", "upper_role"),
    [
        ("VSOURCE", "V", {343}, "output"),
        ("CSOURCE", "I", {344, 345}, "input"),
    ],
)
def test_source_terminal_planner_uses_accepted_role_geometry_and_suffixes(
    tmp_path: Path,
    family: str,
    prefix: str,
    expected_sizes: set[int],
    upper_role: str,
) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 15},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / f"{family.lower()}_v4_geometry_base.pdsprj",
    )

    pairs = plan_attached_source_terminals(
        result.selected_groups,
        label_prefix=prefix,
    )

    assert len(pairs) == 15
    assert {len(group.data) for group in result.selected_groups} == expected_sizes
    assert pairs[0].output.suffix == 0x7000
    assert pairs[0].input.suffix == 0x7032
    assert pairs[1].output.suffix - pairs[0].output.suffix == 0x0080
    assert pairs[1].input.suffix - pairs[0].input.suffix == 0x0080
    if family == "VSOURCE":
        assert pairs[0].output.label == "V0"
        assert pairs[0].input.label == "V1"
    else:
        assert pairs[0].input.label == "I0"
        assert pairs[0].output.label == "I1"
    for pair in pairs:
        assert pair.input.angle_tenths == 1800
        assert pair.output.angle_tenths == 0
        assert pair.input.symbol_x == pair.input_pin_x - SOURCE_TERMINAL_SYMBOL_TO_PIN
        assert (
            pair.output.symbol_x
            == pair.output_pin_x + SOURCE_TERMINAL_SYMBOL_TO_PIN
        )
        assert pair.input_pin_x == pair.output_pin_x
        assert abs(pair.input_pin_y - pair.output_pin_y) == 1_524_000
        assert pair.input_wire_start_x == pair.input_pin_x
        assert pair.input_wire_start_y == pair.input_pin_y
        assert pair.output_wire_start_x == pair.output_pin_x
        assert pair.output_wire_start_y == pair.output_pin_y
        upper_y = max(pair.input_pin_y, pair.output_pin_y)
        assert (
            pair.output_pin_y if upper_role == "output" else pair.input_pin_y
        ) == upper_y


@pytest.mark.parametrize(
    (
        "family",
        "prefix",
        "expected_terminal_order",
        "expected_wire_order",
    ),
    [
        ("VSOURCE", "V", ("output", "input"), ("output", "input")),
        ("CSOURCE", "I", ("input", "output"), ("input", "output")),
    ],
)
def test_source_v4_attachment_preserves_role_order_links_and_wire_boundaries(
    tmp_path: Path,
    family: str,
    prefix: str,
    expected_terminal_order: tuple[str, str],
    expected_wire_order: tuple[str, str],
) -> None:
    base = tmp_path / f"{family.lower()}_v4_base.pdsprj"
    output = tmp_path / f"{family.lower()}_v4_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 15},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        label_prefix=prefix,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    bidir_records = extract_bidir_records(chunk)
    cursor = 1
    labels: list[str] = []
    component_sizes: list[int] = []
    wire_coordinates: list[tuple[int, int, int, int]] = []
    expected_wire_coordinates: list[tuple[int, int, int, int]] = []
    for index, pair in enumerate(report["terminal_pairs"]):
        for role, record in zip(
            expected_terminal_order,
            bidir_records[index * 2 : index * 2 + 2],
            strict=True,
        ):
            assert chunk[cursor : cursor + len(record)] == record
            labels.append(record[31 : 31 + record[30]].decode("ascii"))
            assert labels[-1] == pair[role]["label"]
            cursor += len(record)

        wire_marker = chunk.find(b"\x7fWIRE", cursor)
        wire_start = wire_marker - 23
        component = chunk[cursor:wire_start]
        component_sizes.append(len(component))
        assert component.startswith(b"\x00\xff")
        x_offset = pair["packet_offsets"]["component_x"] + 1
        assert component[
            pair["packet_offsets"]["input_link"] + 1 :
            pair["packet_offsets"]["input_link"] + 3
        ] == bytes.fromhex(pair["input"]["suffix"])[::-1]
        assert component[
            pair["packet_offsets"]["output_link"] + 1 :
            pair["packet_offsets"]["output_link"] + 3
        ] == bytes.fromhex(pair["output"]["suffix"])[::-1]
        assert x_offset < len(component)
        cursor = wire_start

        wire_sizes = (50, 50 if index == len(report["terminal_pairs"]) - 1 else 49)
        for role, size in zip(expected_wire_order, wire_sizes, strict=True):
            wire = chunk[cursor : cursor + size]
            marker = wire.find(b"\x7fWIRE")
            coordinate_start = marker - 23
            wire_coordinates.append(
                tuple(
                    int.from_bytes(
                        wire[
                            coordinate_start + offset :
                            coordinate_start + offset + 4
                        ],
                        "little",
                        signed=True,
                    )
                    for offset in (33, 37, 41, 45)
                )
            )
            pin = pair["pins"][role]
            expected_wire_coordinates.append(
                (pin["x"], pin["y"], pin["x"], pin["y"])
            )
            cursor += size

    assert report["valid"] is True
    assert report["family_handler"] == f"{family}/v4"
    assert report["terminal_order"] == list(expected_terminal_order)
    assert report["wire_order"] == list(expected_wire_order)
    assert report["terminal_count_added"] == 30
    assert report["wire_count_added"] == 30
    assert chunk.count(b"$TERBIDIR") == 30
    assert chunk.count(b"\x7fWIRE") == 30
    assert component_sizes == [
        len(group.data) + 1 for group in result.selected_groups
    ]
    assert wire_coordinates == expected_wire_coordinates
    assert cursor == len(chunk)
    assert chunk.endswith(b"\xff")


def test_shared_terminal_dispatcher_routes_to_family_handler(tmp_path: Path) -> None:
    base = tmp_path / "shared_dispatch_cap_base.pdsprj"
    output = tmp_path / "shared_dispatch_cap_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"CAP": 1},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_component_bidir_terminals_to_project(base, output, result.selected_groups)

    assert report["family_handler"] == "MIXED/native-wire-v10-grid-snapped"
    assert report["runtime_circuit_donor_dependency"] is False
    assert report["link_allocation"]["valid"] is True
    assert report["terminal_count_added"] == 2


def test_native_terminal_placer_normalizes_preserved_control_before_terminal_unit(
    tmp_path: Path,
) -> None:
    base = tmp_path / "fuse_before_cap_elec_base.pdsprj"
    output = tmp_path / "fuse_before_cap_elec_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"FUSE": 1, "CAP-ELEC": 3},
            "layout": {
                "strategy": "beautify",
                "direction": "left_to_right",
                "mixed_ic_non_ic_bands": "separate",
            },
        },
        base,
        full_cdb=True,
    )

    assert [group.family for group in result.selected_groups][:2] == [
        "FUSE",
        "CAP-ELEC",
    ]

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=["CAP-ELEC"],
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    first_terminal = extract_bidir_records(chunk)[0]
    fuse_group = next(group for group in result.selected_groups if group.family == "FUSE")
    fuse_row = next(row for row in report["preserved_groups"] if row["component_family"] == "FUSE")

    assert report["valid"] is True
    assert report["component_record_order_mutation"] is False
    assert report["preserved_control_boundary_normalizations"] == 1
    assert fuse_row["boundary_tail_normalized"] is True
    assert fuse_row["emitted_packet_size"] == len(fuse_group.data) - 1
    assert chunk.count(fuse_group.data + first_terminal) == 0
    assert chunk.count(fuse_group.data[:-1] + first_terminal) == 1


def test_shared_terminal_dispatcher_mixed_selection_uses_native_wire_units(
    tmp_path: Path,
) -> None:
    base = tmp_path / "mixed_selective_base.pdsprj"
    output = tmp_path / "mixed_selective_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                "RESISTOR": 1,
                "CAP": 1,
                "CAP-ELEC": 1,
                "REALIND": 1,
                "VSOURCE": 1,
                "CSOURCE": 1,
                "DIODE": 1,
                "NPN": 1,
                "74HC08": 1,
            },
            "layout": {"strategy": "beautify"},
        },
        base,
        full_cdb=True,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=[
            "VSOURCE",
            "CSOURCE",
            "CAP",
            "CAP-ELEC",
            "REALIND",
            "RESISTOR",
        ],
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    preserved_keys = {row["component_key"] for row in report["preserved_groups"]}
    terminal_pair_families = {
        pair["component_family"]
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
    }
    resistor_pair = next(
        pair
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
        if pair["component_family"] == "RESISTOR"
    )
    expected_wire_coordinates = sorted(
        (
            wire["start"]["x"],
            wire["start"]["y"],
            wire["end"]["x"],
            wire["end"]["y"],
        )
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
        for wire in pair["short_wires"].values()
    )
    actual_wire_coordinates: list[tuple[int, int, int, int]] = []
    search_from = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", search_from)
        if marker < 0:
            break
        wire_start = marker - 23
        actual_wire_coordinates.append(
            tuple(
                int.from_bytes(
                    chunk[wire_start + offset : wire_start + offset + 4],
                    "little",
                    signed=True,
                )
                for offset in (33, 37, 41, 45)
            )
        )
        search_from = marker + len(b"\x7fWIRE")

    assert result.valid
    assert result.layout_plan["binary_coordinate_mutation"]["visible_translated_count"] == 9
    assert report["valid"] is True
    assert report["family_handler"] == "MIXED/native-wire-v10-grid-snapped"
    assert report["eligible_families"] == [
        "RESISTOR",
        "CAP",
        "VSOURCE",
        "CSOURCE",
        "REALIND",
        "CAP-ELEC",
    ]
    assert report["available_accepted_families"] == [
        "VSOURCE",
        "CSOURCE",
        "CAP",
        "CAP-ELEC",
        "REALIND",
        "RESISTOR",
        "DIODE",
    ]
    assert report["skipped_families"] == ["74HC08", "DIODE", "NPN"]
    assert report["preserved_component_count"] == 3
    assert preserved_keys == {"U66", "Q129", "D18"}
    assert all(row["byte_preserved"] for row in report["preserved_groups"])
    assert terminal_pair_families == {
        "RESISTOR",
        "CAP",
        "REALIND",
        "CAP-ELEC",
        "VSOURCE",
        "CSOURCE",
    }
    assert terminal_pair_families.isdisjoint({"DIODE", "NPN", "74HC08"})
    assert report["terminal_count_added"] == 12
    assert report["wire_count_added"] == 12
    assert report["patch_component_links"] is True
    assert report["active_terminal_links"] is True
    assert report["terminal_pin_contacts_valid"] is True
    assert report["terminal_direct_pin_contacts_valid"] is False
    assert report["terminal_grid_alignment_valid"] is True
    assert report["wire_path_contacts_valid"] is True
    assert report["allow_unlinked_short_wires"] is False
    assert report["expected_active_suffix_copies"] == 2
    assert report["component_record_order_mutation"] is False
    assert report["runtime_circuit_donor_dependency"] is False
    assert report["link_allocation"]["method"] == "final_root_dsn_wire_address"
    assert report["link_allocation"]["valid"] is True
    assert report["terminal_suffixes_unique"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert (
        resistor_pair["left"]["symbol_x"] + TERMINAL_CONTACT_TO_PIN
        == resistor_pair["short_wires"]["left"]["start"]["x"]
    )
    assert (
        resistor_pair["right"]["symbol_x"] - TERMINAL_CONTACT_TO_PIN
        == resistor_pair["short_wires"]["right"]["start"]["x"]
    )
    assert all(
        terminal[coordinate] % terminal_placer.PROTEUS_TERMINAL_GRID == 0
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
        for role in ("left", "right", "input", "output")
        if role in pair
        for terminal in (pair[role],)
        for coordinate in ("symbol_x", "symbol_y")
    )
    assert chunk.count(b"$TERBIDIR") == 12
    assert chunk.count(b"\x7fWIRE") == 12
    assert all(
        record[-4:-2] != b"\x00\x00" and record[-2:] == b"\x01\x00"
        for record in extract_bidir_records(chunk)
    )
    assert sorted(actual_wire_coordinates) == expected_wire_coordinates


@pytest.mark.parametrize("family", sorted(GENERIC_TWO_PIN_PROFILES))
def test_generic_two_pin_terminal_profiles_attach_solo_components(
    tmp_path: Path,
    family: str,
) -> None:
    base = tmp_path / f"{family}_generic_two_pin_base.pdsprj"
    output = tmp_path / f"{family}_generic_two_pin_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 1},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
            },
        },
        base,
        full_cdb=True,
    )

    pairs = plan_attached_generic_two_pin_terminals(result.selected_groups)
    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    assert result.valid
    assert len(pairs) == 1
    assert pairs[0].right_pin_x - pairs[0].left_pin_x == (
        GENERIC_TWO_PIN_HALF_SPAN * 2
    )
    assert (
        pairs[0].left.symbol_x
        == pairs[0].left_pin_x - GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN
    )
    assert (
        pairs[0].right.symbol_x
        == pairs[0].right_pin_x + GENERIC_TWO_PIN_TERMINAL_SYMBOL_TO_PIN
    )
    assert report["valid"] is True
    assert report["runtime_circuit_donor_dependency"] is False
    assert report["eligible_families"] == [family]
    assert report["skipped_families"] == []
    assert report["terminal_count_added"] == 2
    assert report["wire_count_added"] == 2
    assert report["terminal_suffix_links_valid"] is True
    assert report["link_allocation"]["valid"] is True
    assert report["terminal_grid_alignment_valid"] is True
    assert report["wire_path_contacts_valid"] is True
    assert chunk.count(b"$TERBIDIR") == 2
    assert chunk.count(b"\x7fWIRE") == 2


def test_shared_terminal_dispatcher_terminalizes_all_two_pin_families(
    tmp_path: Path,
) -> None:
    all_two_pin_families = [
        "RESISTOR",
        "CAP",
        "DIODE",
        "VSINE",
        "VSOURCE",
        "CSOURCE",
        "VPULSE",
        "LED-RED",
        "1N4733A",
        "SWITCH",
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
    base = tmp_path / "all_two_pin_base.pdsprj"
    output = tmp_path / "all_two_pin_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 1 for family in all_two_pin_families},
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
            },
        },
        base,
        full_cdb=True,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    terminal_pair_families = {
        pair["component_family"]
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
    }

    assert result.valid
    assert [group.family for group in result.selected_groups] == all_two_pin_families
    assert report["valid"] is True
    assert report["runtime_circuit_donor_dependency"] is False
    assert report["skipped_families"] == []
    assert report["terminalized_component_count"] == len(all_two_pin_families)
    assert report["preserved_component_count"] == 0
    assert report["terminal_count_added"] == len(all_two_pin_families) * 2
    assert report["wire_count_added"] == len(all_two_pin_families) * 2
    assert report["terminal_suffixes_unique"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert report["terminal_grid_alignment_valid"] is True
    assert report["wire_path_contacts_valid"] is True
    assert report["link_allocation"]["allocation_count"] == (
        len(all_two_pin_families) * 2
    )
    assert terminal_pair_families == set(all_two_pin_families)
    assert chunk.count(b"$TERBIDIR") == len(all_two_pin_families) * 2
    assert chunk.count(b"\x7fWIRE") == len(all_two_pin_families) * 2


@pytest.mark.parametrize("count", [1, 9])
def test_mixed_two_pin_and_catalogue_terminalizer_handles_three_control_combo(
    tmp_path: Path,
    count: int,
) -> None:
    all_two_pin_families = [
        "RESISTOR",
        "CAP",
        "DIODE",
        "VSINE",
        "VSOURCE",
        "CSOURCE",
        "VPULSE",
        "LED-RED",
        "1N4733A",
        "SWITCH",
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
    catalogue_families = ["POT-HG", "LM317T", "OPAMP"]
    base = tmp_path / "mixed_two_pin_lm_op_base.pdsprj"
    output = tmp_path / "mixed_two_pin_lm_op_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                **{family: count for family in all_two_pin_families},
                **{family: count for family in catalogue_families},
            },
            "layout": {
                "strategy": "beautify",
                "binary_coordinate_mutation": True,
            },
        },
        base,
        full_cdb=True,
    )

    report = attach_mixed_component_and_catalogue_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        native_terminal_families=all_two_pin_families,
        catalogue_terminal_families=catalogue_families,
        use_donor_terminal_labels=False,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    expected_terminals = count * (
        len(all_two_pin_families) * 2 + len(catalogue_families) * 3
    )

    assert result.valid
    assert report["valid"] is True
    assert report["terminal_count_added"] == expected_terminals
    assert report["wire_count_added"] == expected_terminals
    assert report["terminalized_component_count"] == (
        count * (len(all_two_pin_families) + len(catalogue_families))
    )
    assert report["terminal_suffixes_unique"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert report["wire_path_contacts_valid"] is True
    assert report["terminal_grid_alignment_valid"] is True
    assert report["native_wire_boundaries_valid"] is True
    assert report["object_chunk_double_ff_valid"] is True
    assert report["component_record_order_mutation"] is False
    assert report["catalogue_component_stream_component_count"] == 0
    assert all(
        check["terminal_trailer"] == "0200"
        and check["component_trailer"] == "0200"
        for check in report["terminal_suffix_link_checks"]
    )
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))
    output_component_chunk = terminal_placer._component_only_chunk_from_terminalized_chunk(
        chunk
    )
    base_groups_by_family = _raw_groups_from_chunk(
        base_chunk,
        _generation_markers(),
    )
    output_groups_by_family = _raw_groups_from_chunk(
        output_component_chunk,
        _generation_markers(),
    )
    base_group_order = [
        (
            None if group.key.startswith("ANON") else group.key,
            group.family,
        )
        for group in sorted(
            (group for groups in base_groups_by_family.values() for group in groups),
            key=lambda group: group.start,
        )
    ]
    output_group_order = [
        (
            None if group.key.startswith("ANON") else group.key,
            group.family,
        )
        for group in sorted(
            (group for groups in output_groups_by_family.values() for group in groups),
            key=lambda group: group.start,
        )
    ]
    assert output_group_order == base_group_order
    assert chunk.count(b"$TERBIDIR") == expected_terminals
    assert chunk.count(b"\x7fWIRE") == expected_terminals
    assert chunk.endswith(b"\xff\xff")


def test_mixed_terminalizer_handles_donor_proven_tail_bjt_with_native_and_controls(
    tmp_path: Path,
) -> None:
    native_families = ["RESISTOR", "CAP"]
    trailing_catalogue_families = ["POT-HG", "LM317T", "OPAMP"]
    tail_bjt_families = ["NPN", "PNP", "2N3904", "2N4401"]
    base = tmp_path / "mixed_tail_bjt_base.pdsprj"
    output = tmp_path / "mixed_tail_bjt_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                **{family: 1 for family in native_families},
                **{family: 1 for family in trailing_catalogue_families},
                **{family: 1 for family in tail_bjt_families},
            },
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )

    report = attach_mixed_component_and_catalogue_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        native_terminal_families=native_families,
        catalogue_terminal_families=(
            trailing_catalogue_families + tail_bjt_families
        ),
        use_donor_terminal_labels=False,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = parse_component_placer_cdb(read_internal_file(output, "ROOT.CDB"))
    expected_components = (
        len(native_families)
        + len(trailing_catalogue_families)
        + len(tail_bjt_families)
    )
    expected_terminals = len(native_families) * 2 + (
        len(trailing_catalogue_families) + len(tail_bjt_families)
    ) * 3
    bjt_reports = [
        row
        for row in report["family_reports"]
        if row.get("component_family") in tail_bjt_families
    ]
    cap_report = next(
        row
        for row in report["family_reports"]
        if row["family_handler"].startswith("CAP/")
    )

    assert result.valid
    assert report["valid"] is True
    assert report["terminal_count_added"] == expected_terminals
    assert report["wire_count_added"] == expected_terminals
    assert report["terminalized_component_count"] == expected_components
    assert report["catalogue_terminal_leading_component_count"] == 0
    assert report["native_terminal_families"] == ["RESISTOR", "CAP"]
    assert cap_report["cap_wire_order"] == ["right", "left"]
    assert report["object_stream_finalizer"] == "append_explicit_single_ff"
    assert report["object_chunk_finalizer_valid"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert report["wire_path_contacts_valid"] is True
    assert report["terminal_grid_alignment_valid"] is True
    assert report["cdb_normalization"]["keep_packages"] == sorted(
        group.key for group in result.selected_groups
    )
    assert len(cdb.pin_rows) == expected_components
    assert len(cdb.property_rows) == expected_components
    assert int.from_bytes(cdb.between_sections[-4:], "little") == expected_components
    assert all(
        row["clean_packet_attachment_order"]
        == "terminal_leading_component_then_wires"
        and row["mixed_attachment_order"]
        == "component_stream_then_attachment_units"
        and row["mixed_object_stream_finalizer"]
        == "append_explicit_single_ff"
        for row in bjt_reports
    )
    native_link_trailers = {
        row["component_family"]: (
            row["terminal_trailer"],
            row["component_trailer"],
        )
        for row in report["terminal_suffix_link_checks"]
        if row["component_family"] in native_families
    }
    assert native_link_trailers == {
        "RESISTOR": ("0200", "0200"),
        "CAP": ("0200", "0200"),
    }
    assert [
        row["label"]
        for row in terminal_placer._bidir_label_records(chunk)[:3]
    ] == ["R001A", "R001B", "C1"]
    assert chunk.count(b"$TERBIDIR") == expected_terminals
    assert chunk.count(b"\x7fWIRE") == expected_terminals
    assert chunk.endswith(b"\xff")


def test_donor_proven_tail_bjt_zone_handles_cap_elec_prefix(
    tmp_path: Path,
) -> None:
    """The full user donor proves catalogue tail units after CAP-ELEC."""

    native_families = ["RESISTOR", "CAP-ELEC"]
    bjt_families = ["NPN", "PNP", "2N3904", "2N4401"]
    base = tmp_path / "native_before_bjt_final_zone_base.pdsprj"
    output = tmp_path / "native_before_bjt_final_zone_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                **{family: 1 for family in native_families},
                **{family: 1 for family in bjt_families},
            },
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )

    report = attach_mixed_component_and_catalogue_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        native_terminal_families=native_families,
        catalogue_terminal_families=bjt_families,
        use_donor_terminal_labels=False,
    )

    assert result.valid
    assert report["valid"] is True
    assert report["catalogue_terminal_leading_component_count"] == 0
    assert report["object_stream_finalizer"] == "append_explicit_single_ff"


def test_donor_proven_tail_bjt_mix_preserves_diode_route(
    tmp_path: Path,
) -> None:
    """The combined donor permits DIODE plus BJT tail units without mutation."""

    base = tmp_path / "unproven_diode_bjt_base.pdsprj"
    output = tmp_path / "unproven_diode_bjt_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                "RESISTOR": 1,
                "CAP": 1,
                "DIODE": 1,
                "NPN": 1,
            },
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )

    report = attach_mixed_component_and_catalogue_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        native_terminal_families=("RESISTOR", "CAP", "DIODE"),
        catalogue_terminal_families=("NPN",),
        use_donor_terminal_labels=False,
    )

    assert result.valid
    assert report["valid"] is True
    assert report["native_terminal_families"] == ["RESISTOR", "CAP", "DIODE"]
    assert report["catalogue_terminal_leading_component_count"] == 0
    assert report["object_stream_finalizer"] == "append_explicit_single_ff"


def test_full_current_group_matches_user_accepted_mixed_tail_oracle(
    tmp_path: Path,
) -> None:
    """Keep the accepted 67-unit tail byte-geometry stable before PNP extends it.

    The user-provided combined donor is authoritative for the full native,
    control, FET, and BJT mixture.  It is intentionally compared here against
    a new placement generated from the locked mega donor, rather than copied
    into the output.  PNP follows as three additional units with its own
    direct-donor geometry.
    """

    assert CURRENT_GROUP_MIXED_TAIL_ORACLE.exists()
    base = tmp_path / "current_group_1x_no_terminal.pdsprj"
    output = tmp_path / "current_group_1x_tail_oracle_sa.pdsprj"
    components = {
        family: 1
        for family in (
            *CURRENT_GROUP_NATIVE_FAMILIES,
            *CURRENT_GROUP_CATALOGUE_TAIL_FAMILIES,
        )
    }
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": components,
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    report = attach_mixed_component_and_catalogue_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        native_terminal_families=CURRENT_GROUP_NATIVE_FAMILIES,
        catalogue_terminal_families=CURRENT_GROUP_CATALOGUE_TAIL_FAMILIES,
        use_donor_terminal_labels=False,
    )

    donor_dsn = read_internal_file(CURRENT_GROUP_MIXED_TAIL_ORACLE, "ROOT.DSN")
    output_dsn = read_internal_file(output, "ROOT.DSN")
    donor_chunk = _extract_object_chunk(donor_dsn)
    output_chunk = _extract_object_chunk(output_dsn)
    donor_terminals = terminal_placer._bidir_label_records(donor_chunk)
    output_terminals = terminal_placer._bidir_label_records(output_chunk)
    donor_wires = terminal_placer._wire_rows_from_chunk(
        donor_chunk,
        chunk_start=terminal_placer._object_chunk_absolute_start(donor_dsn),
    )
    output_wires = terminal_placer._wire_rows_from_chunk(
        output_chunk,
        chunk_start=terminal_placer._object_chunk_absolute_start(output_dsn),
    )
    signature = lambda rows: [
        (
            row["label"],
            row["symbol_x"],
            row["symbol_y"],
            row["angle_tenths"],
            row["suffix"],
        )
        for row in rows
    ]

    assert result.valid
    assert report["valid"] is True
    assert report["object_stream_finalizer"] == "append_explicit_single_ff"
    assert report["terminal_count_added"] == 70
    assert report["wire_count_added"] == 70
    assert donor_chunk.count(b"$TERBIDIR") == donor_chunk.count(b"\x7fWIRE") == 67
    assert output_chunk.count(b"$TERBIDIR") == output_chunk.count(b"\x7fWIRE") == 70
    assert signature(output_terminals[:67]) == signature(donor_terminals)
    assert [row["full_coordinates"] for row in output_wires[:67]] == [
        row["full_coordinates"] for row in donor_wires
    ]
    # Proteus Ctrl+S and the accepted donor both require these four stream
    # separators to be 08 rather than the bare component placer's 00. They
    # occur before POT-HG, LED-RED, SWITCH, and FUSE in this mixed grammar.
    separator_offsets = (4957, 5594, 9823, 15511)
    assert [output_chunk[offset] for offset in separator_offsets] == [
        donor_chunk[offset] for offset in separator_offsets
    ] == [0x08, 0x08, 0x08, 0x08]
    assert signature(output_terminals[-3:]) == [
        ("BASE", -7_620_000, 18_542_000, 1800, 0x8966),
        ("COLLECTOR", -6_096_000, 19_304_000, 0, 0x8A06),
        ("EMITTER", -6_096_000, 17_780_000, 0, 0x8AA4),
    ]
    assert output_chunk.endswith(b"\xff")
    assert not output_chunk.endswith(b"\xff\xff")


@pytest.mark.parametrize("family", DIL14_QUAD_2INPUT_FAMILIES)
def test_dil14_quad_2input_solo_retargets_donor_wires_to_grid_contacts(
    tmp_path: Path,
    family: str,
) -> None:
    """Each four-gate package uses the same catalogue-only terminal route."""

    base = tmp_path / f"{family}_1x_no_terminal.pdsprj"
    output = tmp_path / f"{family}_1x_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 1},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
    )

    assert result.valid
    assert report["valid"] is True
    assert report["terminalized_component_count"] == 1
    assert report["terminal_count_added"] == 12
    assert report["wire_count_added"] == 12
    assert report["terminal_grid_alignment_valid"] is True
    assert report["wire_path_contacts_valid"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert report["object_stream_finalizer"] == "single_ff"
    assert report["family_reports"][0]["component_family"] == family
    assert report["family_reports"][0]["terminal_count"] == 12
    assert report["family_reports"][0]["wire_count"] == 12
    assert all(
        row["terminal_to_wire"] and row["wire_to_pin"] and row["wire_is_nonzero"]
        for row in report["wire_path_contact_checks"]
    )
    # The entire terminal attachment must remain a short local connection. A
    # package-wide anchor bug yields multi-million-unit crossing wires even
    # though the terminal contact itself happens to be grid aligned.
    for terminal_pin in report["family_reports"][0]["terminal_pins"]:
        start = terminal_pin["short_wire"]["start"]
        end = terminal_pin["short_wire"]["end"]
        assert (
            abs(start["x"] - end["x"]) + abs(start["y"] - end["y"])
            <= 2 * 254_000
        ), f"{family} emitted a non-local terminal WIRE for pin {terminal_pin['pin']['name']}"
    # A component-link field must remain wholly inside its owning subpart. In
    # particular, `U476`/`U198` have one more reference character than their
    # accepted donor packages; whole-package offsets would overwrite the next
    # `FF <length> U...:<subpart>` marker instead of the current pin-link slot.
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    refs = result.selected_groups[0].refs
    starts = []
    for ref in refs:
        encoded = ref.encode("ascii")
        marker = b"\xff" + bytes([len(encoded)]) + encoded
        start = chunk.find(marker)
        assert start >= 0, f"{family} lost its {ref} component record marker"
        starts.append(start)
    starts.sort()
    terminal_start = chunk.find(b"$TERBIDIR") - 14
    assert terminal_start > starts[-1]
    ends = [*starts[1:], terminal_start]
    for allocation in report["link_allocation"]["allocations"]:
        position = allocation["component_link_position"]
        assert any(
            start <= position and position + 4 <= end
            for start, end in zip(starts, ends, strict=True)
        ), f"{family} link at {position} crosses a component-record boundary"


@pytest.mark.parametrize("family", DIL14_QUAD_2INPUT_FAMILIES)
def test_dil14_catalogues_wide_reference_safe_link_slots(family: str) -> None:
    """A/B/C links must be anchored to their current subpart, not package end."""

    profile = load_component_catalog().get_profile(family)
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    slots = geometry["component_link_subpart_end_offsets"]
    assert geometry["object_stream_finalizer"] == "single_ff"
    assert set(slots) == {"1", "2", "3", "4", "5", "6", "8", "9", "10"}
    assert all(
        slot["subpart"] in {"A", "B", "C"}
        and slot["offset"] in {-13, -9, -5}
        for slot in slots.values()
    )


def test_dil14_hc08_wide_reference_links_use_current_subpart_end(
    tmp_path: Path,
) -> None:
    """Four-character package refs cannot use U66 whole-packet offsets."""

    family = "74HC08"
    base = tmp_path / "74HC08_4x_no_terminal.pdsprj"
    output = tmp_path / "74HC08_4x_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 4},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
    )

    assert result.valid
    assert report["valid"] is True
    assert any(len(ref.split(":", 1)[0]) >= 4 for group in result.selected_groups for ref in group.refs)
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    profile = load_component_catalog().get_profile(family)
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    slots = geometry["component_link_subpart_end_offsets"]
    pin_subparts = geometry["pin_subparts"]

    expected_positions: dict[tuple[str, str], int] = {}
    for group in result.selected_groups:
        starts: dict[str, int] = {}
        for ref in group.refs:
            encoded = ref.encode("ascii")
            start = chunk.find(b"\xff" + bytes([len(encoded)]) + encoded)
            assert start >= 0, f"{family} lost {ref}"
            starts[ref.rsplit(":", 1)[1]] = start
        for pin, slot in slots.items():
            subpart = pin_subparts[pin]
            following = [
                position
                for name, position in starts.items()
                if position > starts[subpart]
            ]
            assert following, f"{group.key} {subpart} lacks a following subpart"
            expected_positions[(group.key, pin)] = min(following) + slot["offset"]

    actual_positions = {
        (str(row["component_key"]), str(row["role"])): int(
            row["component_link_position"]
        )
        for row in report["link_allocation"]["allocations"]
        if str(row["role"]) in slots
    }
    assert actual_positions == expected_positions


def test_hc04_catalogue_uses_complete_e04_attachment_grammar() -> None:
    """HC04 must retain its actual donor's routed WIRE units and order."""

    profile = load_component_catalog().get_profile("74HC04")
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    assert geometry["coordinate_geometry_source_project"].endswith(
        "E04_74HC04_1X_NO_TERMINAL_CONTROL.pdsprj"
    )
    assert tuple(geometry["donor_attachment_unit_order"]) == HC04_E04_ATTACHMENT_ORDER
    assert geometry["subpart_anchor_coordinate_rebase"] is True
    assert geometry["object_stream_finalizer"] == "double_ff"
    assert set(geometry["subpart_anchor_indices"]) == {"A", "B", "C", "D", "E", "F"}
    assert all(
        len(geometry["pins"][pin]["wire_unit_coordinates"]) // 2 in {3, 4}
        for pin in HC04_E04_ATTACHMENT_ORDER
    )
    assert all(
        geometry["pins"][pin]["terminal_contact_x"] % 254_000 == 0
        and geometry["pins"][pin]["terminal_contact_y"] % 254_000 == 0
        for pin in HC04_E04_ATTACHMENT_ORDER
    )


def test_hc04_shared_placer_uses_e04_ordered_routed_units_and_safe_links(
    tmp_path: Path,
) -> None:
    """Four-character HC04 refs must not overwrite later inverter records."""

    family = "74HC04"
    base = tmp_path / "74HC04_1x_no_terminal.pdsprj"
    output = tmp_path / "74HC04_1x_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 1},
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
        result.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
    )

    assert result.valid
    assert report["valid"] is True
    assert report["terminal_count_added"] == 12
    assert report["wire_count_added"] == 12
    assert report["terminal_grid_alignment_valid"] is True
    assert report["wire_path_contacts_valid"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert report["object_stream_finalizer"] == "double_ff"

    dsn = read_internal_file(output, "ROOT.DSN")
    chunk = _extract_object_chunk(dsn)
    terminal_rows = terminal_placer._bidir_label_records(chunk)
    assert [row["label"] for row in terminal_rows] == [
        f"{'OUT' if pin in {'2', '4', '6', '8', '10', '12'} else 'IN'}pin{pin}"
        for pin in HC04_E04_ATTACHMENT_ORDER
    ]
    wire_rows = terminal_placer._wire_rows_from_chunk(
        chunk,
        chunk_start=terminal_placer._object_chunk_absolute_start(dsn),
    )
    assert [row["point_count"] for row in wire_rows] == [
        3, 3, 3, 3, 3, 3, 4, 3, 4, 4, 4, 4
    ]

    profile = load_component_catalog().get_profile(family)
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    slots = geometry["component_link_subpart_end_offsets"]
    refs = result.selected_groups[0].refs
    starts: dict[str, int] = {}
    for ref in refs:
        encoded = ref.encode("ascii")
        start = chunk.find(b"\xff" + bytes([len(encoded)]) + encoded)
        assert start >= 0, f"{family} lost {ref}"
        starts[ref.rsplit(":", 1)[1]] = start
    terminal_start = chunk.find(b"$TERBIDIR") - 14
    actual_positions = {
        str(row["role"]): int(row["component_link_position"])
        for row in report["link_allocation"]["allocations"]
    }
    for pin, slot in slots.items():
        subpart = slot["subpart"]
        following = [position for position in starts.values() if position > starts[subpart]]
        if following:
            subpart_end = min(following)
            expected = subpart_end + int(slot["offset"])
            assert actual_positions[pin] == expected
            assert starts[subpart] <= actual_positions[pin] < subpart_end
        else:
            # The final clean packet's selected terminator is replaced by the
            # first attachment unit during stream rebuild.  Assert its two
            # donor-proven F link fields stay inside the final subpart rather
            # than conflating that one-byte stream boundary normalization with
            # a later-subpart marker.
            assert starts[subpart] <= actual_positions[pin]
            assert actual_positions[pin] + 4 <= terminal_start
    assert actual_positions["13"] + 4 == actual_positions["12"]


def test_hc74_shared_placer_preserves_subpart_native_wire_boundaries(
    tmp_path: Path,
) -> None:
    """HC74's A/B blocks preserve donor component/WIRE boundaries."""

    family = "74HC74"
    donor = (
        ROOT
        / "proteus_ic"
        / "donors"
        / "terminalized_catalogue_evidence"
        / "dil14_dual_d_ff"
        / family
        / "74HC74_terminalized_primary.pdsprj"
    )
    base = tmp_path / "74HC74_1x_no_terminal.pdsprj"
    output = tmp_path / "74HC74_1x_terminalized.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 1},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=True,
    )

    profile = load_component_catalog().get_profile(family)
    assert profile is not None
    geometry = profile.proteus["pin_geometry"]
    assert geometry["clean_packet_attachment_order"] == (
        "subpart_terminal_component_wires"
    )
    assert geometry["subpart_first_wire_separator_policy"] == (
        "strip_first_leading_separator"
    )
    assert geometry["subpart_component_wire_separator_policy"] == (
        "append_single_zero"
    )
    assert geometry["subpart_link_prefix_zero_trim_count"] == 1
    assert result.valid
    assert report["valid"] is True
    assert report["terminal_count_added"] == 12
    assert report["wire_count_added"] == 12

    donor_chunk = _extract_object_chunk(read_internal_file(donor, "ROOT.DSN"))
    output_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))

    def native_wire_starts(chunk: bytes) -> list[int]:
        starts: list[int] = []
        cursor = 0
        while True:
            marker = chunk.find(b"\x7fWIRE", cursor)
            if marker < 0:
                return starts
            start = marker - 23
            assert chunk[start : start + len(terminal_placer.NATIVE_WIRE_PREFIX)] == (
                terminal_placer.NATIVE_WIRE_PREFIX
            )
            starts.append(start)
            cursor = marker + 1

    donor_wires = native_wire_starts(donor_chunk)
    output_wires = native_wire_starts(output_chunk)
    assert len(donor_wires) == len(output_wires) == 12
    assert [right - left for left, right in zip(donor_wires, donor_wires[1:6])] == [50] * 5
    assert [right - left for left, right in zip(donor_wires[6:], donor_wires[7:])] == [50] * 5
    assert [right - left for left, right in zip(output_wires, output_wires[1:6])] == [50] * 5
    assert [right - left for left, right in zip(output_wires[6:], output_wires[7:])] == [50] * 5
    assert all(donor_chunk[start + 49] == 0 for start in (*donor_wires[:5], *donor_wires[6:11]))
    assert all(output_chunk[start + 49] == 0 for start in (*output_wires[:5], *output_wires[6:11]))

    donor_a = donor_chunk.index(b"\xff\x04U1:A")
    donor_b = donor_chunk.index(b"\xff\x04U1:B")
    current_refs = {
        ref.rsplit(":", 1)[1]: ref for ref in result.selected_groups[0].refs
    }
    output_a_ref = current_refs["A"].encode("ascii")
    output_b_ref = current_refs["B"].encode("ascii")
    output_a = output_chunk.index(b"\xff" + bytes([len(output_a_ref)]) + output_a_ref)
    output_b = output_chunk.index(b"\xff" + bytes([len(output_b_ref)]) + output_b_ref)
    # A reference may be wider than U1 in a future component placer. HC74's
    # accepted donor also has one component/WIRE boundary zero after each
    # current subpart record, before its first native WIRE prefix.
    assert output_wires[0] - output_a == donor_wires[0] - donor_a + (
        len(output_a_ref) - len(b"U1:A")
    )
    assert output_wires[6] - output_b == donor_wires[6] - donor_b + (
        len(output_b_ref) - len(b"U1:B")
    )
    assert donor_chunk[donor_wires[0] - 2 : donor_wires[0]] == b"\x00\x00"
    assert donor_chunk[donor_wires[6] - 2 : donor_wires[6]] == b"\x00\x00"
    assert output_chunk[output_wires[0] - 2 : output_wires[0]] == b"\x00\x00"
    assert output_chunk[output_wires[6] - 2 : output_wires[6]] == b"\x00\x00"
    # The source shares separator bytes *between* WIREs only.  Its last WIRE
    # is immediately followed by the next terminal/object record; this catches
    # the malformed leading-separator packet that previously reached VGDVC.DLL.
    assert output_chunk[output_wires[5] + 49] == 0x10
    assert output_chunk[output_wires[11] + 49] == 0xFF


def test_dil14_mixed_baseline_keeps_new_logic_groups_unterminalized(
    tmp_path: Path,
) -> None:
    """The boundary mix must not silently attach DIL14 terminals yet."""

    base = tmp_path / "mixed_two_pin_terminalized_dil14_bare.pdsprj"
    output = tmp_path / "mixed_two_pin_terminalized_dil14_bare_sa.pdsprj"
    components = {
        family: 1
        for family in (*CURRENT_GROUP_NATIVE_FAMILIES, *DIL14_QUAD_2INPUT_FAMILIES)
    }
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": dict(sorted(components.items())),
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )
    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=CURRENT_GROUP_NATIVE_FAMILIES,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    preserved = {
        row["component_family"]
        for row in report["preserved_groups"]
        if row["component_family"] in DIL14_QUAD_2INPUT_FAMILIES
    }

    expected = len(CURRENT_GROUP_NATIVE_FAMILIES) * 2
    assert result.valid
    assert report["valid"]
    assert report["terminal_count_added"] == expected
    assert report["wire_count_added"] == expected
    assert chunk.count(b"$TERBIDIR") == expected
    assert chunk.count(b"\x7fWIRE") == expected
    assert preserved == set(DIL14_QUAD_2INPUT_FAMILIES)


def test_dil14_locked_mega_scale_caps_are_catalogued() -> None:
    catalog = load_component_catalog()
    actual = {
        family: int(
            catalog.get_profile(family).limits[
                "locked_new_components_5x_mega_clean_group_max"
            ]
        )
        for family in DIL14_QUAD_2INPUT_FAMILIES
    }
    assert actual == DIL14_LOCKED_MEGA_SCALE_CAPS


@pytest.mark.parametrize(
    "family",
    ["RESISTOR", "CAP", "CAP-ELEC", "REALIND", "VSOURCE", "CSOURCE"],
)
def test_mixed_native_writer_matches_accepted_single_family_bytes(
    tmp_path: Path,
    family: str,
) -> None:
    base = tmp_path / f"{family}_base.pdsprj"
    accepted = tmp_path / f"{family}_accepted.pdsprj"
    native = tmp_path / f"{family}_native.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 3},
            "layout": {"strategy": "beautify"},
        },
        base,
        full_cdb=True,
    )

    accepted_report = attach_component_bidir_terminals_to_project(
        base,
        accepted,
        result.selected_groups,
    )
    native_report = attach_mixed_native_bidir_terminals_to_project(
        base,
        native,
        result.selected_groups,
        terminal_families=(family,),
    )
    accepted_chunk = _extract_object_chunk(
        read_internal_file(accepted, "ROOT.DSN")
    )
    native_chunk = _extract_object_chunk(read_internal_file(native, "ROOT.DSN"))

    assert result.valid
    assert accepted_report["valid"] is True
    assert native_report["valid"] is True
    assert native_report["single_family_oracle_policy"] == (
        "same_shared_schema_encoder"
    )
    assert native_chunk == accepted_chunk


def test_resistor_terminal_only_stream_is_inactive_under_locked_donor(
    tmp_path: Path,
) -> None:
    base = tmp_path / "resistor_ctrl_s_base.pdsprj"
    output = tmp_path / "resistor_ctrl_s_normalized.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                "RESISTOR": 1,
                "DIODE": 1,
                "NPN": 1,
                "74HC08": 1,
            },
            "layout": {"strategy": "beautify"},
        },
        base,
        full_cdb=True,
    )
    report = attach_mixed_overlay_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=("RESISTOR",),
        patch_component_links=False,
        active_terminal_links=False,
        include_wires=False,
    )
    output_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    terminals = extract_bidir_records(output_chunk)

    assert report["valid"] is True
    assert len(terminals) == 2
    assert all(record[-4:] == b"\x00\x00\x00\x00" for record in terminals)
    assert output_chunk.count(b"\x7fWIRE") == 0


def test_shared_terminal_dispatcher_noneligible_selection_is_exact_copy(
    tmp_path: Path,
) -> None:
    base = tmp_path / "noneligible_base.pdsprj"
    output = tmp_path / "noneligible_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {"NPN": 1, "74HC08": 1},
            "layout": {"strategy": "beautify"},
        },
        base,
        full_cdb=True,
    )

    report = attach_component_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
    )

    assert result.valid
    assert report["valid"] is True
    assert report["family_handler"] == "NONE/selective-copy-v1"
    assert report["eligible_families"] == []
    assert report["skipped_families"] == ["74HC08", "NPN"]
    assert report["terminal_count_added"] == 0
    assert report["wire_count_added"] == 0
    assert base.read_bytes() == output.read_bytes()


@pytest.mark.parametrize(
    ("family", "expected_symbols"),
    [
        (
            "POT-HG",
            {
                "1": (-6604000, -3302000, 1800),
                "2": (-5588000, -4064000, 0),
                "3": (-6604000, -4826000, 1800),
            },
        ),
        (
            "LM317T",
            {
                "1": (-4826000, -6604000, 0),
                "2": (-3302000, -5080000, 0),
                "3": (-7366000, -5080000, 1800),
            },
        ),
        (
            "OPAMP",
            {
                "OUT": (-4572000, -4064000, 0),
                "IN+": (-7112000, -3810000, 1800),
                "IN-": (-7112000, -4572000, 1800),
            },
        ),
    ],
)
def test_catalogue_three_pin_terminals_use_donor_contact_offsets(
    tmp_path: Path,
    family: str,
    expected_symbols: dict[str, tuple[int, int, int]],
) -> None:
    base = tmp_path / f"{family}_donor_contact_base.pdsprj"
    output = tmp_path / f"{family}_donor_contact_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 1},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=(family,),
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))
    terminals_by_pin = {
        row["pin"]["name"]: row
        for family_report in report["family_reports"]
        for row in family_report["terminal_pins"]
    }

    assert result.valid
    assert report["valid"] is True
    assert chunk[:3] == base_chunk[:3]
    assert set(terminals_by_pin) == set(expected_symbols)
    for pin_name, (symbol_x, symbol_y, angle) in expected_symbols.items():
        row = terminals_by_pin[pin_name]
        terminal = row["terminal"]
        catalogue_geometry = row["catalogue_geometry"]
        assert (
            int(terminal["symbol_x"]),
            int(terminal["symbol_y"]),
            int(terminal["angle_tenths"]),
        ) == (symbol_x, symbol_y, angle)
        if catalogue_geometry.get("terminal_label"):
            assert terminal["label"] == catalogue_geometry["terminal_label"]
        if catalogue_geometry.get("component_link_trailer"):
            assert terminal["link_trailer"] == catalogue_geometry["component_link_trailer"]
        assert row["terminal_contact_source"] == "donor_terminal_contact_anchor_offset"
        assert row["short_wire"]["start"] != row["short_wire"]["end"]
    first_component_marker = chunk.find(family.encode("ascii"))
    first_terminal_marker = chunk.find(b"$TERBIDIR")
    first_terminal_start = first_terminal_marker - 14
    assert 0 <= first_component_marker < first_terminal_marker
    assert first_terminal_start == len(base_chunk) - 1
    attachment_events: list[tuple[int, str]] = []
    for marker, label in ((b"$TERBIDIR", "terminal"), (b"\x7fWIRE", "wire")):
        cursor = 0
        while True:
            marker_offset = chunk.find(marker, cursor)
            if marker_offset < 0:
                break
            if marker_offset > first_component_marker:
                attachment_events.append((marker_offset, label))
            cursor = marker_offset + 1
    assert [label for _offset, label in sorted(attachment_events)] == [
        "terminal",
        "wire",
        "terminal",
        "wire",
        "terminal",
        "wire",
    ]


@pytest.mark.parametrize("family", ["POT-HG", "LM317T", "OPAMP"])
def test_catalogue_three_pin_scaled_terminals_append_after_component_stream(
    tmp_path: Path,
    family: str,
) -> None:
    base = tmp_path / f"{family}_scaled_base.pdsprj"
    output = tmp_path / f"{family}_scaled_sa.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {family: 3},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        },
        base,
        full_cdb=True,
    )

    report = attach_catalogue_pin_bidir_terminals_to_project(
        base,
        output,
        result.selected_groups,
        terminal_families=(family,),
        use_donor_terminal_labels=False,
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))

    assert result.valid
    assert report["valid"] is True
    assert chunk[:3] == base_chunk[:3]
    assert chunk.endswith(b"\xff\xff")
    assert chunk.count(b"$TERBIDIR") == 9
    assert chunk.count(b"\x7fWIRE") == 9
    assert chunk.find(b"$TERBIDIR") - 14 == len(base_chunk) - 1
    for group in result.selected_groups:
        key = group.key.encode("ascii")
        component_prefix = b"\xff" + bytes([len(key)]) + key
        assert chunk.find(component_prefix) >= 0
        assert chunk.find(component_prefix) < chunk.find(b"$TERBIDIR")
    labels = [record["label"] for record in terminal_placer._bidir_label_records(chunk)]
    assert max(len(label) for label in labels) <= 16
    first_key = result.selected_groups[0].key
    expected_role_suffixes = {
        "POT-HG": {"VCC", "OUT", "GND"},
        "LM317T": {"OUT", "ADJ", "IN"},
        "OPAMP": {"OUT", "INP", "INN"},
    }[family]
    assert {label for label in labels if label.startswith(first_key)} == {
        f"{first_key}{suffix}" for suffix in expected_role_suffixes
    }
