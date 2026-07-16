from __future__ import annotations

import json
from pathlib import Path

import pytest

from proteusgen.component_catalog import load_component_catalog
from proteusgen.component_terminal_placer import _bidir_label_records, _wire_record_spans
from proteusgen.component_value_changer import (
    ValuePropertiesEditorError,
    edit_project_values_and_properties,
)
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_TERMINALIZED_CURRENT_GROUP = (
    ROOT
    / "evidence"
    / "donors"
    / "ALL_donorACCEPTED_TERMINALIZED_CURRENT_GROUP_TERMINALIZED_1X_sa.pdsprj"
)


def _attachment_records(project: Path) -> tuple[tuple[bytes, ...], tuple[bytes, ...]]:
    chunk = _extract_object_chunk(read_internal_file(project, "ROOT.DSN"))
    terminals = tuple(
        chunk[record["start"] : record["start"] + 101 + record["label_length"]]
        for record in _bidir_label_records(chunk)
    )
    wires = tuple(chunk[start:end] for start, end in _wire_record_spans(chunk))
    return terminals, wires


def test_catalogue_exposes_the_shared_value_and_properties_policy() -> None:
    policy = load_component_catalog().proteus_value_editor_policy()

    assert policy["stage"] == "value_and_properties_editor"
    assert policy["mode"] == "same_length_numeric_selected_packet_and_matching_cdb_row"
    assert "MODFILE" in policy["immutable_property_names"]


def test_post_terminal_editor_changes_all_normal_visible_values_and_properties(tmp_path: Path) -> None:
    before_terminals, before_wires = _attachment_records(ACCEPTED_TERMINALIZED_CURRENT_GROUP)
    output = tmp_path / "all_values_and_properties_terminalized.pdsprj"

    result = edit_project_values_and_properties(
        ACCEPTED_TERMINALIZED_CURRENT_GROUP,
        output,
        {
            "values": {
                "R1": "47k",
                "C1": "2nF",
                "C62": "2uF",
                "L21": "2mH",
                "RV1": "2k",
                "V23": "2V",
                "I7": "2A",
            },
            "properties": {
                "L21": {"ESR": "0.3"},
                "RV1": {"POS": "75"},
                "U107": {"GAIN": "2E6"},
                "U132": {"RSC": "0.4"},
            },
        },
    )

    assert result.valid
    assert result.terminal_record_count == len(before_terminals) == 67
    assert result.wire_record_count == len(before_wires) == 67
    assert len(result.mutations) == 11
    assert {mutation.family for mutation in result.mutations} >= {
        "RESISTOR",
        "CAP",
        "CAP-ELEC",
        "REALIND",
        "POT-HG",
        "VSOURCE",
        "CSOURCE",
    }
    assert _attachment_records(output) == (before_terminals, before_wires)

    source_dsn = read_internal_file(ACCEPTED_TERMINALIZED_CURRENT_GROUP, "ROOT.DSN")
    source_cdb = read_internal_file(ACCEPTED_TERMINALIZED_CURRENT_GROUP, "ROOT.CDB")
    edited_dsn = read_internal_file(output, "ROOT.DSN")
    edited_cdb = read_internal_file(output, "ROOT.CDB")
    assert len(edited_dsn) == len(source_dsn)
    assert len(edited_cdb) == len(source_cdb)
    for token in (
        b"47k",
        b"2nF",
        b"2uF",
        b"2mH",
        b"2k",
        b"2V",
        b"2A",
        b"{ESR=0.3}",
        b"{POS=75}",
        b"{GAIN=2E6}",
        b"{RSC=0.4}",
    ):
        assert token in edited_dsn
        assert token in edited_cdb

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["stage"] == "value_and_properties_editor"
    assert len(report["mutations"]) == 11


def test_post_terminal_editor_changes_numeric_properties_across_supported_families(
    tmp_path: Path,
) -> None:
    """Every donor-exposed numeric property stays inside its packet/CDB row."""

    before_terminals, before_wires = _attachment_records(ACCEPTED_TERMINALIZED_CURRENT_GROUP)
    output = tmp_path / "cross_family_numeric_properties.pdsprj"
    result = edit_project_values_and_properties(
        ACCEPTED_TERMINALIZED_CURRENT_GROUP,
        output,
        {
            "properties": {
                "D47": {"BV": "6.2"},
                "D21": {"VF": "3.3V"},
                "Q100": {"L": "3.0E-6"},
                "U107": {"VPOS": "12"},
                "U132": {"RSC": "0.4"},
                "D105": {"IBV": "30m"},
                "D171": {"BV": "12.0"},
                "D191": {"BV": "6.2"},
                "D211": {"IBV": "6.0m"},
                "L21": {"CP": "0.3pF"},
                "RV1": {"RMIN": "0.2"},
            },
        },
    )

    assert result.valid
    assert len(result.mutations) == 11
    assert {mutation.family for mutation in result.mutations} >= {
        "DIODE",
        "LED-RED",
        "NMOSFET",
        "OPAMP",
        "LM317T",
        "BZY88C",
        "1N6000B",
        "BZX55C5V1",
        "BZX79C5V1",
        "REALIND",
        "POT-HG",
    }
    assert _attachment_records(output) == (before_terminals, before_wires)
    edited_dsn = read_internal_file(output, "ROOT.DSN")
    edited_cdb = read_internal_file(output, "ROOT.CDB")
    for token in (
        b"{BV=6.2}",
        b"{VF=3.3V}",
        b"{L=3.0E-6}",
        b"{VPOS=12}",
        b"{RSC=0.4}",
        b"{IBV=30m}",
        b"{BV=12.0}",
        b"{IBV=6.0m}",
        b"{CP=0.3pF}",
        b"{RMIN=0.2}",
    ):
        assert token in edited_dsn
        assert token in edited_cdb


@pytest.mark.parametrize("package", ("V1", "V42"))
def test_post_terminal_editor_rejects_unproven_source_value_grammar(
    tmp_path: Path,
    package: str,
) -> None:
    output = tmp_path / f"{package}_unproven_value.pdsprj"

    with pytest.raises(ValuePropertiesEditorError, match="model/name"):
        edit_project_values_and_properties(
            ACCEPTED_TERMINALIZED_CURRENT_GROUP,
            output,
            {"values": {package: "2V"}},
        )
    assert not output.exists()


def test_post_terminal_editor_rejects_variable_length_and_identity_mutations(tmp_path: Path) -> None:
    variable_length_output = tmp_path / "bad_length.pdsprj"
    with pytest.raises(ValuePropertiesEditorError, match="same-length"):
        edit_project_values_and_properties(
            ACCEPTED_TERMINALIZED_CURRENT_GROUP,
            variable_length_output,
            {"values": {"R1": "100k"}},
        )
    assert not variable_length_output.exists()

    identity_output = tmp_path / "bad_model.pdsprj"
    with pytest.raises(ValuePropertiesEditorError, match="immutable"):
        edit_project_values_and_properties(
            ACCEPTED_TERMINALIZED_CURRENT_GROUP,
            identity_output,
            {"properties": {"U132": {"MODFILE": "LM318_1"}}},
        )
    assert not identity_output.exists()
