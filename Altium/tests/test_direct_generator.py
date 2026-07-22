from __future__ import annotations

import json
from pathlib import Path

import pytest

from Altium.direct_generator import DirectGenerationError, generate_direct_project
from Altium.direct_validator import validate_direct_schematic
from Altium.project_package import inspect_project_package
from Altium.source_catalogue import load_source_catalogue


_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_direct_rc_filter_is_fully_wired_and_packaged(tmp_path: Path) -> None:
    result = generate_direct_project(
        _EXAMPLES / "direct_rc_filter.json",
        output_root=tmp_path,
    )

    assert result.validation.passed
    assert result.terminalized_nets == ()
    assert result.terminal_labels == ()
    assert result.validation.label_count == 0
    assert inspect_project_package(result.project_archive).passed
    assert result.project_file.read_text(encoding="utf-8").startswith("[Project]\n")
    assert "|UNIQUEID=pge1" in result.schematic_file.read_text(encoding="utf-8")
    provenance = json.loads((result.internal_directory / "source_provenance.json").read_text())
    assert provenance["easyeda_conversion_used"] is False
    assert provenance["generation_path"].startswith(
        "canonical_json -> input_fixer -> value_editor -> value_validator"
    )
    assert provenance["generation_path"].endswith("pcb_decision -> final_validator")


def test_direct_led_aliases_resolve_to_source_pin_designators(tmp_path: Path) -> None:
    result = generate_direct_project(
        _EXAMPLES / "direct_led_indicator.json",
        output_root=tmp_path,
    )

    led = next(component for component in result.components if component.reference == "D1")
    assert led.logical_pin_map == {"A": "1", "C": "2"}
    assert result.validation.passed


def test_every_locked_source_template_emits_with_explicit_no_connect_pins(tmp_path: Path) -> None:
    catalogue = load_source_catalogue()
    components = []
    for index, (kind, template) in enumerate(sorted(catalogue.templates.items()), start=1):
        reference = f"X{index}"
        components.append(
            {
                "id": reference,
                "ref": reference,
                "kind": kind,
                "value": template.library_reference,
                "pins": {pin: f"NC_{reference}_{pin}" for pin in template.pins},
            }
        )

    result = generate_direct_project(
        {
            "project": {"name": "all_catalogue_nc", "title": "All Catalogue NC Smoke"},
            "components": components,
        },
        output_root=tmp_path,
    )

    assert result.validation.passed
    assert len(result.components) == len(catalogue.templates)
    assert result.validation.wire_count == 0
    assert result.validation.label_count == 0
    assert inspect_project_package(result.project_archive).passed


def test_combination_mode_uses_native_labels_only_for_unroutable_nets(tmp_path: Path) -> None:
    result = generate_direct_project(
        _EXAMPLES / "direct_74hc04_breakout.json",
        output_root=tmp_path,
    )

    assert result.validation.passed
    assert result.terminalized_nets
    assert len(result.terminal_labels) == 2 * len(result.terminalized_nets)
    assert result.validation.label_count == len(result.terminal_labels)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    report = validate_direct_schematic(result.schematic_file, expected)
    assert report.passed
    assert report.terminalized_nets == result.terminalized_nets


def test_strict_wire_mode_refuses_dense_breakout_instead_of_hiding_it(tmp_path: Path) -> None:
    with pytest.raises(DirectGenerationError, match="Strict wire mode"):
        generate_direct_project(
            _EXAMPLES / "direct_74hc04_breakout.json",
            output_root=tmp_path,
            routing_mode="wire",
        )


def test_validator_rejects_tampered_terminal_label(tmp_path: Path) -> None:
    result = generate_direct_project(
        _EXAMPLES / "direct_74hc04_breakout.json",
        output_root=tmp_path,
    )
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    result.schematic_file.write_text(text.replace("|TEXT=IO_02|", "|TEXT=WRONG_NET|", 1), encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("not declared as a terminalized" in error for error in report.errors)
