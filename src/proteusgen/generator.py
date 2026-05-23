"""Conservative fixture-backed generation of Proteus projects."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .circuit_ir import CircuitIR, Issue
from .pdsprj import read_internal_file, write_project_from_parts
from .templates import Fixture, FixtureRegistry
from .validation import ValidationReport, validate_circuit
from .versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version


@dataclass(frozen=True)
class GenerationResult:
    output_path: Path
    result_template_path: Path
    fixture_id: str
    recipe: str

    def as_dict(self) -> dict[str, str]:
        return {
            "output_path": str(self.output_path),
            "result_template_path": str(self.result_template_path),
            "fixture_id": self.fixture_id,
            "recipe": self.recipe,
            "target_version": "8.13",
        }


class GenerationBlocked(Exception):
    def __init__(self, report: ValidationReport) -> None:
        super().__init__("CircuitIR cannot be emitted from a validated template.")
        self.report = report


def _components(ir: CircuitIR) -> set[tuple[str, str, str | None]]:
    return {(component.ref, component.part, component.value) for component in ir.circuit.components}


def _connections(ir: CircuitIR) -> set[tuple[str, str, str]]:
    return {(connection.component, connection.pin, connection.net) for connection in ir.circuit.connections}


def _nets(ir: CircuitIR) -> set[tuple[str, str]]:
    return {(net.name, net.kind) for net in ir.circuit.nets}


def select_validated_fixture(ir: CircuitIR, registry: FixtureRegistry) -> tuple[Fixture, str] | None:
    """Map a circuit to a whole-project fixture with equivalent validated semantics."""

    if (
        ir.target.mode == "production"
        and not ir.circuit.components
        and not ir.circuit.nets
        and not ir.circuit.connections
        and not ir.circuit.layout.has_rendered_geometry
    ):
        return registry.get("e001_empty"), "empty_single_sheet"

    if (
        ir.target.mode == "production"
        and _components(ir) == {("R1", "RESISTOR", "1k")}
        and _nets(ir) == {("VCC", "power"), ("GND", "ground")}
        and _connections(ir) == {("R1", "1", "VCC"), ("R1", "2", "GND")}
        and not ir.circuit.layout.has_rendered_geometry
    ):
        return registry.get("e020_resistor_vcc_gnd_1k"), "single_r1_1k_vcc_gnd"

    if (
        ir.target.mode == "diagnostic_control"
        and _components(ir) == {("U1", "74HC08", None)}
        and not ir.circuit.nets
        and not ir.circuit.connections
        and not ir.circuit.layout.has_rendered_geometry
    ):
        return registry.get("hc08_d02_four_gates_unwired"), "hc08_d02_unwired_control"
    return None


def _blocked_no_recipe(ir: CircuitIR) -> ValidationReport:
    if any(component.part == "74HC08" for component in ir.circuit.components):
        issue = Issue(
            "D05_ORACLE_REQUIRED",
            "Composed 74HC08 output is blocked until a clean D05 reference project validates rail, terminal, and resistor rendering.",
            "$.circuit",
            "Provide HC08_D05_exact_picture_manual_control.pdsprj created in Proteus 8.13.",
        )
    else:
        issue = Issue(
            "NO_VALIDATED_TEMPLATE_RECIPE",
            "No whole validated template currently represents this circuit.",
            "$.circuit",
            "Add a clean Proteus 8.13 oracle for this topology before enabling generation.",
        )
    return ValidationReport(errors=(issue,), warnings=(), circuit=ir)


def generate_project(
    ir: CircuitIR,
    output_path: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> GenerationResult:
    """Emit only projects covered by a full clean fixture recipe."""

    registry = registry or FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {', '.join(failed_hashes)}")
    report = validate_circuit(ir, require_generation_ready=True)
    if not report.valid:
        raise GenerationBlocked(report)
    selected = select_validated_fixture(ir, registry)
    if selected is None:
        raise GenerationBlocked(_blocked_no_recipe(ir))
    fixture, recipe = selected
    project_xml = patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813)
    root_dsn = patch_root_dsn_version(read_internal_file(fixture.path, "ROOT.DSN"), PROTEUS_813)
    out = Path(output_path)
    write_project_from_parts(fixture.path, out, {"PROJECT.XML": project_xml, "ROOT.DSN": root_dsn})
    result_template_path = out.with_suffix(".result-template.json")
    result_template = {
        "test_id": f"GEN_{ir.circuit.name}",
        "generated_file": str(out),
        "proteus_version": "8.13",
        "opened": False,
        "fatal_error": False,
        "warnings": [],
        "visual_result": {"correct_component_count": False, "wrong_components": [], "missing_components": [], "notes": ""},
        "properties_checked": [],
        "simulation_result": {"ran": False, "worked": False, "notes": "Not yet tested."},
        "human_notes": f"Generated from validated fixture `{fixture.id}` using recipe `{recipe}`. Fill after Proteus testing.",
        "result_summary": "Pending Proteus 8.13 test."
    }
    result_template_path.write_text(json.dumps(result_template, indent=2) + "\n", encoding="utf-8")
    return GenerationResult(output_path=out, result_template_path=result_template_path, fixture_id=fixture.id, recipe=recipe)
