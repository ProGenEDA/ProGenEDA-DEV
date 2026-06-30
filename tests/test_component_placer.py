from __future__ import annotations

import json
from pathlib import Path

import pytest

from proteusgen.component_placer import (
    ComponentPlacerBlocked,
    MAIN_MEGA_NO_SOURCE_DONOR,
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
from proteusgen.component_beautifier import layout_coordinate_pairs
from proteusgen.bidirectional import extract_bidir_records
from proteusgen.component_terminal_placer import (
    CAP_ELEC_PIN_HALF_SPAN,
    CAP_ELEC_TERMINAL_SYMBOL_TO_PIN,
    CAP_PIN_HALF_SPAN,
    CAP_TERMINAL_SYMBOL_TO_PIN,
    INDUCTOR_PIN_HALF_SPAN,
    INDUCTOR_TERMINAL_SYMBOL_TO_PIN,
    RESISTOR_PIN_SPAN,
    SOURCE_TERMINAL_SYMBOL_TO_PIN,
    TERMINAL_CONTACT_TO_PIN,
    TERMINAL_SYMBOL_TO_PIN,
    attach_capacitor_bidir_terminals_to_project,
    attach_component_bidir_terminals_to_project,
    attach_resistor_bidir_terminals_to_project,
    plan_attached_capacitor_terminals,
    plan_attached_electrolytic_capacitor_terminals,
    plan_attached_inductor_terminals,
    plan_attached_resistor_terminals,
    plan_attached_source_terminals,
    plan_side_bidir_terminals,
)
from proteusgen.cdb import package_ref
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]

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
    assert any(group.key == "DISPLAY_ANODE_SENTINEL" for group in cathode.selected_groups)

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
    sentinel_entry = next(
        entry
        for entry in cathode.layout_plan["actual_binary_placements"]
        if entry["key"] == "DISPLAY_ANODE_SENTINEL"
    )
    assert sentinel_entry["role"] == "display_infrastructure"
    assert "slot" not in sentinel_entry


def test_component_placement_uses_registered_ic_coordinates(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "components": {"74HC160": 3},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "hc160_registered_coordinates.pdsprj",
        donor_path=ROOT / "proteus_ic" / "donors" / "main_mega_20260618" / (
            "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160"
            "hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
        ),
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
            "components": {"74HC02": 15},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "hc02_footprint_shelf.pdsprj",
        donor_path=ROOT / "proteus_ic" / "donors" / "main_mega_20260618" / (
            "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160"
            "hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
        ),
        full_cdb=True,
    )

    assert result.valid
    entries = [
        entry
        for entry in result.layout_plan["actual_binary_placements"]
        if entry["family"] == "74HC02"
    ]
    assert len(entries) == 15
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


def test_component_placement_generator_accepts_payload_donor_manifest_id(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "donor": "component_placer_main_semimega_sources_20260618",
            "components": {"VSOURCE": 1, "CSOURCE": 1, "VSINE": 1},
        },
        tmp_path / "explicit_manifest_id.pdsprj",
    )

    assert result.valid
    assert result.donor.name.startswith("semimega_")


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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
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


def test_capacitor_terminal_planner_uses_body_center_plus_half_span(tmp_path: Path) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
            "components": {"REALIND": 15},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "inductor_v2_geometry_base.pdsprj",
    )

    pairs = plan_attached_inductor_terminals(result.selected_groups)

    assert len(pairs) == 15
    assert pairs[0].component_key == "L1"
    assert pairs[13].component_key == "L14"
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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
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
    for index, pair in enumerate(report["terminal_pairs"]):
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
        right_size = 50 if index == len(report["terminal_pairs"]) - 1 else 49
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
    assert report["family_handler"] == "REALIND/v2"
    assert report["object_order"] == (
        "repeated_left_bidir_right_bidir_realind_left_wire_right_wire"
    )
    assert report["terminal_count_added"] == 30
    assert report["wire_count_added"] == 30
    assert chunk.count(b"$TERBIDIR") == 30
    assert chunk.count(b"\x7fWIRE") == 30
    assert labels == [
        label
        for pair in report["terminal_pairs"]
        for label in (pair["left"]["label"], pair["right"]["label"])
    ]
    assert [item["right_wire_size"] for item in report["group_records"]] == [
        *([49] * 14),
        50,
    ]
    assert all(item["left_wire_size"] == 50 for item in report["group_records"])
    assert component_sizes[-2:] == [375, 375]
    assert all(x1 == x2 and y1 == y2 for x1, y1, x2, y2 in wire_coordinates)
    assert cursor == len(chunk)
    assert chunk.endswith(b"\xff")


def test_cap_elec_terminal_planner_uses_accepted_eight_donor_geometry(
    tmp_path: Path,
) -> None:
    result = generate_component_placement_project(
        {
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
            "components": {"CAP-ELEC": 15},
            "layout": {"strategy": "beautify"},
        },
        tmp_path / "cap_elec_v3_geometry_base.pdsprj",
    )

    pairs = plan_attached_electrolytic_capacitor_terminals(result.selected_groups)

    assert len(pairs) == 15
    assert pairs[0].component_key == "C21"
    assert pairs[14].component_key == "C36"
    assert "C35" in {pair.component_key for pair in pairs}
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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
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
    for index, pair in enumerate(report["terminal_pairs"]):
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
        right_size = 50 if index == len(report["terminal_pairs"]) - 1 else 49
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
                    pair["pins"]["left"]["x"],
                    pair["pins"]["left"]["y"],
                    pair["pins"]["left"]["x"],
                    pair["pins"]["left"]["y"],
                ),
                (
                    pair["pins"]["right"]["x"],
                    pair["pins"]["right"]["y"],
                    pair["pins"]["right"]["x"],
                    pair["pins"]["right"]["y"],
                ),
            )
        )

    assert report["valid"] is True
    assert report["family_handler"] == "CAP-ELEC/v3"
    assert report["object_order"] == (
        "repeated_right_bidir_left_bidir_cap_elec_left_wire_right_wire"
    )
    assert report["terminal_count_added"] == 30
    assert report["wire_count_added"] == 30
    assert chunk.count(b"$TERBIDIR") == 30
    assert chunk.count(b"\x7fWIRE") == 30
    assert labels == [
        label
        for pair in report["terminal_pairs"]
        for label in (pair["right"]["label"], pair["left"]["label"])
    ]
    assert [item["right_wire_size"] for item in report["group_records"]] == [
        *([49] * 14),
        50,
    ]
    assert all(item["left_wire_size"] == 50 for item in report["group_records"])
    assert component_sizes == [380] * 15
    assert wire_coordinates == expected_wire_coordinates
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
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
            "components": {"CAP": 1},
            "layout": {"strategy": "beautify"},
        },
        base,
    )

    report = attach_component_bidir_terminals_to_project(base, output, result.selected_groups)

    assert report["family_handler"] == "CAP/v2"
    assert report["terminal_count_added"] == 2


def test_shared_terminal_dispatcher_mixed_selection_terminalizes_only_allowlisted_families(
    tmp_path: Path,
) -> None:
    base = tmp_path / "mixed_selective_base.pdsprj"
    output = tmp_path / "mixed_selective_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": "component_placer_main_15x_semimega_sources_20260618",
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
    )
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    preserved_keys = {row["component_key"] for row in report["preserved_groups"]}
    terminal_pair_families = {
        pair["component_family"]
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
    }

    assert result.valid
    assert result.layout_plan["binary_coordinate_mutation"]["visible_translated_count"] == 9
    assert report["valid"] is True
    assert report["family_handler"] == "MIXED/selective-v1"
    assert report["eligible_families"] == [
        "VSOURCE",
        "CSOURCE",
        "CAP",
        "CAP-ELEC",
        "REALIND",
        "RESISTOR",
    ]
    assert report["skipped_families"] == ["74HC08", "DIODE", "NPN"]
    assert report["terminalized_component_count"] == 6
    assert report["preserved_component_count"] == 3
    assert preserved_keys == {"U66", "D1", "Q1"}
    assert all(row["byte_preserved"] for row in report["preserved_groups"])
    assert terminal_pair_families == {
        "RESISTOR",
        "CAP",
        "CAP-ELEC",
        "REALIND",
        "VSOURCE",
        "CSOURCE",
    }
    assert terminal_pair_families.isdisjoint({"DIODE", "NPN", "74HC08"})
    assert report["terminal_count_added"] == 12
    assert report["wire_count_added"] == 12
    assert report["terminal_suffixes_unique"] is True
    assert report["terminal_suffix_links_valid"] is True
    assert chunk.count(b"$TERBIDIR") == 12
    assert chunk.count(b"\x7fWIRE") == 12


def test_shared_terminal_dispatcher_noneligible_selection_is_exact_copy(
    tmp_path: Path,
) -> None:
    base = tmp_path / "noneligible_base.pdsprj"
    output = tmp_path / "noneligible_output.pdsprj"
    result = generate_component_placement_project(
        {
            "donor": "component_placer_main_15x_semimega_sources_20260618",
            "components": {"DIODE": 2, "NPN": 1, "74HC08": 1},
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
    assert report["skipped_families"] == ["74HC08", "DIODE", "NPN"]
    assert report["terminal_count_added"] == 0
    assert report["wire_count_added"] == 0
    assert base.read_bytes() == output.read_bytes()
