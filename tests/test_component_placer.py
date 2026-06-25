from __future__ import annotations

import json
from pathlib import Path

import pytest

from proteusgen.component_placer import (
    ComponentPlacerBlocked,
    NEW_COMPONENT_MEGA_DONOR,
    TrustedDonor,
    _generation_markers,
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
                "RESISTOR": {"count": 1, "value": "4.7k"},
                "CAP": 1,
            },
            "values": {"C1": "10uF"},
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
    assert {"family": "RESISTOR", "target": "R1", "value": "4.7k", "source": "components.value"} in value_requests
    assert any(row["family"] == "CAP" and row["target"] == "C1" and row["value"] == "10uF" for row in value_requests)
    assert result.value_plan["binary_mutation"]["applied"] is False
    assert result.wiring_plan["same_net_groups"] == [
        {
            "net": "N_FILTER",
            "endpoints": [
                {"component": "R1", "pin": "2"},
                {"component": "C1", "pin": "1"},
            ],
        }
    ]
