from __future__ import annotations

import json
from pathlib import Path
import re
import zipfile

import pytest

from Altium.direct_generator import DirectGenerationError, generate_direct_project
from Altium.direct_validator import validate_direct_schematic
from Altium.final_validator import validate_final_output
from Altium.native_writer import NativeWriteResult
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
    assert result.project_file.read_text(encoding="utf-8").startswith("[Design]\n")
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
    text, replacements = re.subn(
        r"(\|RECORD=25[^\r\n]*\|TEXT=)[^|]+",
        r"\1WRONG_NET",
        text,
        count=1,
    )
    assert replacements == 1
    result.schematic_file.write_text(text, encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("not declared as a terminalized" in error for error in report.errors)


def test_validator_rejects_tampered_component_value(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    result.schematic_file.write_text(text.replace("|TEXT=1k|", "|TEXT=999k|", 1), encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("value mismatch" in error for error in report.errors)


def test_validator_rejects_tampered_component_library_identity(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    result.schematic_file.write_text(
        re.sub(r"(\|RECORD=1[^\r\n]*\|LIBREFERENCE=)[^|]+", r"\1WRONG_DEVICE", text, count=1),
        encoding="utf-8",
    )

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("library reference mismatch" in error for error in report.errors)


def test_validator_rejects_tampered_component_root_geometry(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    text, replacements = re.subn(
        r"(\|RECORD=1[^\r\n]*\|LOCATION\.X=)\d+",
        r"\g<1>999",
        text,
        count=1,
    )
    assert replacements == 1
    result.schematic_file.write_text(text, encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("root location mismatch" in error for error in report.errors)


def test_validator_rejects_tampered_native_pin_identity(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    text, direction_replacements = re.subn(
        r"(\|RECORD=2[^\r\n]*\|PINCONGLOMERATE=)\d+",
        r"\g<1>99",
        text,
        count=1,
    )
    text, name_replacements = re.subn(
        r"(\|RECORD=2[^\r\n]*\|NAME=)[^|]*",
        r"\g<1>TAMPERED_PIN",
        text,
        count=1,
    )
    assert direction_replacements == name_replacements == 1
    result.schematic_file.write_text(text, encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("pin direction mismatch" in error for error in report.errors)
    assert any("pin name mismatch" in error for error in report.errors)


def test_validator_rejects_duplicate_native_value_record(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    lines = result.schematic_file.read_text(encoding="utf-8").splitlines()
    value_index = next(index for index, line in enumerate(lines) if "|NAME=Value|" in line)
    duplicate = re.sub(r"(\|INDEXINSHEET=)[^|]+", r"\g<1>99999", lines[value_index])
    lines.insert(value_index + 1, duplicate)
    lines[0] = re.sub(
        r"(\|WEIGHT=)\d+",
        lambda match: f"{match.group(1)}{int(re.search(r'\|WEIGHT=(\d+)', lines[0]).group(1)) + 1}",
        lines[0],
        count=1,
    )
    result.schematic_file.write_text("\r\n".join((*lines, "")), encoding="utf-8", newline="")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("duplicate component Value record" in error for error in report.errors)


def test_validator_rejects_wire_geometry_not_made_by_validated_wire_maker(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    text, replacements = re.subn(
        r"(\|RECORD=27[^\r\n]*\|X2=)(\d+)",
        lambda match: f"{match.group(1)}{int(match.group(2)) + 1}",
        text,
        count=1,
    )
    assert replacements == 1
    result.schematic_file.write_text(text, encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("wire geometry differs" in error for error in report.errors)


def test_validator_rejects_wire_and_label_index_collision(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_74hc04_breakout.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    wire_index = re.search(r"\|RECORD=27[^\r\n]*\|INDEXINSHEET=([^|]+)", text)
    assert wire_index is not None
    text = re.sub(
        r"(\|RECORD=25[^\r\n]*\|INDEXINSHEET=)[^|]+",
        rf"\g<1>{wire_index.group(1)}",
        text,
        count=1,
    )
    result.schematic_file.write_text(text, encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("duplicate wire/label INDEXINSHEET" in error for error in report.errors)


def test_validator_rejects_sheet_smaller_than_emitted_geometry(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_74hc04_breakout.json", output_root=tmp_path)
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    text = result.schematic_file.read_text(encoding="utf-8")
    text = re.sub(r"(\|RECORD=31[^\r\n]*\|CUSTOMX=)\d+", r"\g<1>100", text, count=1)
    text = re.sub(r"(\|RECORD=31[^\r\n]*\|CUSTOMY=)\d+", r"\g<1>100", text, count=1)
    result.schematic_file.write_text(text, encoding="utf-8")

    report = validate_direct_schematic(result.schematic_file, expected)

    assert not report.passed
    assert any("sheet" in error and "geometry" in error for error in report.errors)


def test_final_validator_rejects_archive_payload_that_differs_from_validated_files(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    native_stage = json.loads((result.internal_directory / "stages" / "19_native_writer.json").read_text())
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    native = NativeWriteResult(
        project_directory=result.project_directory,
        project_file=result.project_file,
        schematic_file=result.schematic_file,
        expected_contract=expected,
        emitted_record_count=native_stage["emitted_record_count"],
        sheet_width_ticks=native_stage["sheet_width_ticks"],
        sheet_height_ticks=native_stage["sheet_height_ticks"],
    )
    archive = tmp_path / "tampered.zip"
    with zipfile.ZipFile(result.project_archive) as original, zipfile.ZipFile(archive, "w") as tampered:
        for info in original.infolist():
            data = original.read(info)
            if info.filename.casefold().endswith(".schdoc"):
                data += b"\r\nTAMPERED"
            tampered.writestr(info, data)

    report = validate_final_output(native, archive)

    assert not report.passed
    assert any("archive payload differs" in error for error in report.errors)


def test_final_validator_rejects_unvalidated_extra_archive_file(tmp_path: Path) -> None:
    result = generate_direct_project(_EXAMPLES / "direct_rc_filter.json", output_root=tmp_path)
    native_stage = json.loads((result.internal_directory / "stages" / "19_native_writer.json").read_text())
    expected = json.loads((result.internal_directory / "expected_physical_contract.json").read_text())
    native = NativeWriteResult(
        project_directory=result.project_directory,
        project_file=result.project_file,
        schematic_file=result.schematic_file,
        expected_contract=expected,
        emitted_record_count=native_stage["emitted_record_count"],
        sheet_width_ticks=native_stage["sheet_width_ticks"],
        sheet_height_ticks=native_stage["sheet_height_ticks"],
    )
    archive = tmp_path / "extra-file.zip"
    with zipfile.ZipFile(result.project_archive) as original, zipfile.ZipFile(archive, "w") as altered:
        for info in original.infolist():
            altered.writestr(info, original.read(info))
        altered.writestr("unexpected.txt", "not part of the validated native project")

    report = validate_final_output(native, archive)

    assert not report.passed
    assert any("outside the validated schematic project inventory" in error for error in report.errors)
