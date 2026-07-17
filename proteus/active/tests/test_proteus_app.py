from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from proteusgen.pdsprj import read_internal_file
from proteusgen.proteus_app import (
    EXECUTABLE_CATALOGUE_TERMINAL_FAMILIES,
    EXECUTABLE_TERMINAL_FAMILIES,
    ProteusApplicationError,
    generate_proteus_project,
)
from proteusgen.proteus_cli import build_parser
from proteusgen.resistor_v9 import _extract_object_chunk
from proteusgen.templates import repository_root


def test_executable_pipeline_runs_shared_placement_terminal_and_value_stages(
    tmp_path: Path,
) -> None:
    output = tmp_path / "r_and_c_terminalized_values.pdsprj"

    result = generate_proteus_project(
        {
            "components": {"RESISTOR": 1, "CAP": 1},
            "layout": {"strategy": "beautify"},
            "post_terminal_edits": {
                "values": {"R1": "47k", "C1": "2nF"},
            },
        },
        output,
    )

    assert result.valid
    assert result.output == output
    assert result.output.exists()
    assert result.report_path.exists()
    assert result.terminal_report is not None
    assert result.terminal_report["valid"]
    assert result.terminal_report["terminal_count_added"] == 4
    assert result.terminal_report["wire_count_added"] == 4
    assert all(check["wire_is_nonzero"] for check in result.terminal_report["wire_path_contact_checks"])
    assert result.value_properties is not None
    assert len(result.value_properties.mutations) == 2

    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    assert chunk.count(b"$TERBIDIR") == 4
    assert chunk.count(b"\x7fWIRE") == 4
    assert b"47k" in read_internal_file(output, "ROOT.DSN")
    assert b"2nF" in read_internal_file(output, "ROOT.CDB")

    report = json.loads(result.report_path.read_text(encoding="utf-8"))
    assert report["stage"] == "progen_proteus_application"
    assert report["terminal_placer"]["valid"]
    assert len(report["value_and_properties_editor"]["mutations"]) == 2


def test_executable_refuses_to_claim_wiring_is_complete(tmp_path: Path) -> None:
    with pytest.raises(ProteusApplicationError, match="Physical wiring is not yet available"):
        generate_proteus_project(
            {
                "components": {"RESISTOR": 1},
                "connections": [{"net": "N1", "endpoints": []}],
            },
            tmp_path / "must_not_emit.pdsprj",
        )


def test_executable_terminalizes_catalogue_backed_pdf_families(tmp_path: Path) -> None:
    output = tmp_path / "catalogue_pdf_families.pdsprj"

    result = generate_proteus_project(
        {
            "components": {
                "POT-HG": 1,
                "NMOSFET": 1,
                "OPAMP": 1,
                "LM317T": 1,
            },
            "layout": {"strategy": "beautify"},
        },
        output,
    )

    assert result.valid
    assert result.terminal_report is not None
    assert result.terminal_report["valid"]
    assert result.terminal_report["terminalized_component_count"] == 4
    assert result.terminal_report["terminal_count_added"] == 12
    assert result.terminal_report["wire_count_added"] == 12
    assert all(
        check["wire_is_nonzero"]
        for check in result.terminal_report["wire_path_contact_checks"]
    )
    assert EXECUTABLE_CATALOGUE_TERMINAL_FAMILIES <= EXECUTABLE_TERMINAL_FAMILIES


def test_executable_uses_canonical_node_names_for_native_and_catalogue_terminals(
    tmp_path: Path,
) -> None:
    result = generate_proteus_project(
        {
            "components": {"RESISTOR": 1, "OPAMP": 1},
            "layout": {"strategy": "beautify"},
            "terminal_label_projection": {
                "schema_version": "progen-proteus-terminal-label-projection/v1",
                "families": {
                    "RESISTOR": [
                        {
                            "source_ref": "R1",
                            "pins": {"1": "VIN", "2": "FB"},
                        }
                    ],
                    "OPAMP": [
                        {
                            "source_ref": "U1",
                            "pins": {"IN+": "VIN", "IN-": "G0", "OUT": "VOUT"},
                        }
                    ],
                },
            },
        },
        tmp_path / "semantic_terminal_labels.pdsprj",
    )

    assert result.valid
    assert result.terminal_report is not None
    reports = result.terminal_report["family_reports"]
    resistor = next(
        row for row in reports if str(row["family_handler"]).startswith("RESISTOR/")
    )
    opamp = next(
        row for row in reports if str(row["family_handler"]).startswith("OPAMP/")
    )
    resistor_pair = resistor["terminal_pairs"][0]
    assert resistor_pair["left"]["label"] == "VIN"
    assert resistor_pair["right"]["label"] == "FB"
    opamp_labels = {
        row["pin"]["name"]: row["terminal"]["label"]
        for row in opamp["terminal_pins"]
    }
    assert opamp_labels == {"OUT": "VOUT", "IN+": "VIN", "IN-": "G0"}


def test_executable_uses_node_names_for_catalogue_only_components(tmp_path: Path) -> None:
    result = generate_proteus_project(
        {
            "components": {"OPAMP": 1},
            "layout": {"strategy": "beautify"},
            "terminal_label_projection": {
                "schema_version": "progen-proteus-terminal-label-projection/v1",
                "families": {
                    "OPAMP": [
                        {
                            "source_ref": "U1",
                            "pins": {"IN+": "VIN", "IN-": "G0", "OUT": "VOUT"},
                        }
                    ],
                },
            },
        },
        tmp_path / "catalogue_only_semantic_terminal_labels.pdsprj",
    )

    assert result.valid
    assert result.terminal_report is not None
    opamp = next(
        row
        for row in result.terminal_report["family_reports"]
        if str(row["family_handler"]).startswith("OPAMP/")
    )
    labels = {
        row["pin"]["name"]: row["terminal"]["label"]
        for row in opamp["terminal_pins"]
    }
    assert labels == {"OUT": "VOUT", "IN+": "VIN", "IN-": "G0"}


def test_executable_rejects_zero_length_terminal_wires(tmp_path: Path) -> None:
    with pytest.raises(ProteusApplicationError, match="zero-length terminal-to-pin WIRE"):
        generate_proteus_project(
            {
                "components": {"RESISTOR": 1, "CAP": 1},
                "layout": {"strategy": "beautify", "terminal_grid_alignment": True},
            },
            tmp_path / "zero_wire_must_not_be_emitted.pdsprj",
        )


def test_proteus_cli_exposes_only_the_portable_proteus_commands() -> None:
    parser = build_parser()
    generate_args = parser.parse_args(["generate", "input.json", "--output", "output.pdsprj"])
    edit_args = parser.parse_args(
        ["edit-values", "existing.pdsprj", "--edits", "edits.json", "--output", "edited.pdsprj"]
    )

    assert generate_args.command == "generate"
    assert not generate_args.no_terminals
    assert edit_args.command == "edit-values"


def test_repository_root_accepts_pyinstaller_bundle_data(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.delenv("PROTEUSGEN_REPO_ROOT", raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert repository_root() == tmp_path
