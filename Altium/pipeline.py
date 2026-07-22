"""Full deterministic pipeline for direct source-backed Altium schematic generation.

Each stage produces a discrete JSON artifact under ``internal/stages``.  The
normal generator runs the full chain, but the contracts are ordinary Python
objects with no writer state, so placement, arrangement, routing, terminal,
value, or validation work can be reproduced and repaired independently.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Mapping

from .arrangement_decider import choose_route_informed_arrangement
from .beautifier import apply_coordinate_edits
from .beautifier_validator import validate_beautifier_result
from .component_placer import place_components
from .component_selector import resolve_components
from .file_name_decider import decide_file_names
from .final_validator import validate_final_output
from .input_fixer import repair_input
from .input_validator import validate_resolved_input
from .ir import CircuitInputError, load_circuit
from .native_writer import write_native_project
from .output_packager import package_internal_evidence, package_project
from .pcb_decider import decide_pcb_output
from .pipeline_contracts import PIPELINE_SCHEMA, PipelineError, PipelineResult, as_json
from .placement_validator import validate_placement
from .project_descriptor import project_template_provenance
from .routing_decider import decide_routing
from .routing_validator import validate_routing
from .source_catalogue import SourceCatalogue, load_source_catalogue
from .terminal_placer import combine_plans, place_terminals
from .user_spec_validator import validate_user_specification
from .value_editor import apply_value_edits
from .value_validator import validate_component_values
from .wire_planner import plan_wires
from .wire_maker import make_native_route_records


ProgressCallback = Callable[[dict[str, Any]], None]
_STAGE_PROGRESS = {
    "input_fixer": 4,
    "value_editor": 8,
    "value_validator": 11,
    "file_name_decider": 14,
    "component_selector": 18,
    "user_spec_validator": 22,
    "input_validator": 26,
    "component_placer": 30,
    "placement_validator_initial": 34,
    "arrangement_decider": 40,
    "beautifier": 44,
    "beautifier_validator": 48,
    "routing_decider": 52,
    "wire_planner": 58,
    "terminal_placer": 64,
    "routing_plan": 68,
    "routing_validator": 72,
    "wire_maker": 77,
    "native_writer": 82,
    "output_packager": 86,
    "pcb_decision": 90,
    "final_validator": 96,
}


class PipelineRunError(PipelineError):
    """A full pipeline run failed after creating a diagnostic run directory."""

    def __init__(self, message: str, run_directory: Path | None = None) -> None:
        super().__init__(message)
        self.run_directory = run_directory


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(as_json(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_mapping(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(dict(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _new_run_directory(root: Path, name: str, normalized_input: Mapping[str, Any]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(
        json.dumps(normalized_input, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:10]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    candidate = root / f"{name}_{timestamp}_{digest}"
    suffix = 1
    while candidate.exists():
        candidate = root / f"{name}_{timestamp}_{digest}_v{suffix}"
        suffix += 1
    candidate.mkdir()
    return candidate


def validate_and_fix_input(
    input_value: Path | str | Mapping[str, Any],
    *,
    routing_mode: str | None = None,
    catalogue: SourceCatalogue | None = None,
) -> dict[str, Any]:
    """Run the front stages without writing an Altium project."""

    source = catalogue or load_source_catalogue()
    fixed = repair_input(input_value, catalogue=source, routing_mode=routing_mode)
    circuit = load_circuit(fixed.fixed)
    values = apply_value_edits(circuit)
    selection = resolve_components(values.circuit, catalogue=source)
    validation = validate_resolved_input(selection)
    if not validation.passed:
        raise PipelineError("; ".join(validation.errors))
    value_validation = validate_component_values(values.circuit)
    if not value_validation.passed:
        raise PipelineError("; ".join(value_validation.errors))
    names = decide_file_names(values.circuit)
    user_spec = validate_user_specification(selection)
    if not user_spec.passed:
        raise PipelineError("; ".join(user_spec.errors))
    routing = decide_routing(selection)
    return {
        "schema": "progen-altium-input-preflight/v1",
        "normalized_input": values.circuit.normalized_json(),
        "input_fixer": fixed.report,
        "value_editor": values.json(),
        "value_validator": value_validation.json(),
        "file_name_decider": names.json(),
        "input_validator": validation.json(),
        "user_spec_validator": user_spec.json(),
        "component_selection": selection.json(),
        "routing_decider": routing.json(),
    }


def generate_pipeline(
    input_value: Path | str | Mapping[str, Any],
    *,
    output_root: Path | str,
    routing_mode: str | None = None,
    on_progress: ProgressCallback | None = None,
) -> PipelineResult:
    """Execute every direct-Altium schematic stage and retain every artifact."""

    def progress(stage: str, message: str, percent: int) -> None:
        if on_progress is not None:
            on_progress({"event": "stage", "stage": stage, "message": message, "percent": percent})

    source = load_source_catalogue()
    fixed = repair_input(input_value, catalogue=source, routing_mode=routing_mode)
    try:
        initial_circuit = load_circuit(fixed.fixed)
    except CircuitInputError as exc:
        raise PipelineRunError(str(exc)) from exc
    values = apply_value_edits(initial_circuit)
    circuit = values.circuit
    names = decide_file_names(circuit)
    run_directory = _new_run_directory(Path(output_root).expanduser().resolve(), circuit.name, circuit.normalized_json())
    internal_directory = run_directory / "internal"
    stages_directory = internal_directory / "stages"
    internal_directory.mkdir()
    stages_directory.mkdir()
    reports: dict[str, Path] = {}

    def record(number: int, name: str, value: Any) -> Path:
        path = stages_directory / f"{number:02d}_{name}.json"
        _write_json(path, value)
        reports[name] = path
        progress(name, name.replace("_", " ").capitalize(), _STAGE_PROGRESS[name])
        return path

    def fail(stage: str, errors: tuple[str, ...] | list[str] | str) -> None:
        messages = [errors] if isinstance(errors, str) else list(errors)
        report = {
            "schema": PIPELINE_SCHEMA,
            "passed": False,
            "failed_stage": stage,
            "errors": messages,
            "run_directory": str(run_directory),
        }
        _write_mapping(internal_directory / "pipeline_report.json", report)
        reports["pipeline_report"] = internal_directory / "pipeline_report.json"
        package_internal_evidence(run_directory, internal_directory, circuit.name)
        raise PipelineRunError("; ".join(messages), run_directory)

    _write_mapping(internal_directory / "normalized_input.json", circuit.normalized_json())
    _write_mapping(
        internal_directory / "source_provenance.json",
        {
            "schema": PIPELINE_SCHEMA,
            "source_catalogue": source.json(),
            "project_descriptor_donor": project_template_provenance(),
            "generation_path": (
                "canonical_json -> input_fixer -> value_editor -> value_validator -> "
                "file_name_decider -> component_selector -> user_spec_validator -> input_validator -> "
                "component_placer -> placement_validator_initial -> arrangement_decider -> beautifier -> "
                "beautifier_validator -> routing_decider -> wire_planner -> terminal_placer -> "
                "routing_plan -> routing_validator -> wire_maker -> native_altium_writer -> output_packager -> "
                "pcb_decision -> final_validator"
            ),
            "easyeda_conversion_used": False,
        },
    )
    record(1, "input_fixer", fixed.report)
    record(2, "value_editor", values)
    value_validation = validate_component_values(circuit)
    record(3, "value_validator", value_validation)
    if not value_validation.passed:
        fail("value_validator", value_validation.errors)

    record(4, "file_name_decider", names)
    selection = resolve_components(circuit, catalogue=source)
    record(5, "component_selector", selection)
    user_spec = validate_user_specification(selection)
    record(6, "user_spec_validator", user_spec)
    if not user_spec.passed:
        fail("user_spec_validator", user_spec.errors)
    input_validation = validate_resolved_input(selection)
    record(7, "input_validator", input_validation)
    if not input_validation.passed:
        fail("input_validator", input_validation.errors)

    initial_design = place_components(selection)
    record(8, "component_placer", initial_design)
    initial_placement = validate_placement(initial_design)
    record(9, "placement_validator_initial", initial_placement)
    if not initial_placement.passed:
        fail("placement_validator_initial", initial_placement.errors)

    routing_decision = decide_routing(selection)
    arrangement = choose_route_informed_arrangement(
        initial_design,
        routing_decision.routing_mode,
        forced_terminal_nets=routing_decision.forced_terminal_nets,
    )
    record(10, "arrangement_decider", arrangement)
    beautified = apply_coordinate_edits(initial_design, arrangement.plan)
    record(11, "beautifier", beautified)
    design = beautified.design
    beautifier_validation = validate_beautifier_result(beautified)
    record(12, "beautifier_validator", beautifier_validation)
    if not beautifier_validation.passed:
        fail("beautifier_validator", beautifier_validation.placement.errors)
    _write_mapping(internal_directory / "placement.json", design.json())

    record(13, "routing_decider", routing_decision)
    wire_plan = plan_wires(
        design,
        routing_decision.routing_mode,
        forced_terminal_nets=routing_decision.forced_terminal_nets,
    )
    record(14, "wire_planner", wire_plan)
    terminal_plan = place_terminals(design, wire_plan)
    record(15, "terminal_placer", terminal_plan)
    routing = combine_plans(wire_plan, terminal_plan)
    record(16, "routing_plan", routing)
    routing_validation = validate_routing(design, routing)
    record(17, "routing_validator", routing_validation)
    _write_mapping(internal_directory / "routing.json", routing.json())
    if not routing_validation.passed:
        fail("routing_validator", routing_validation.errors)

    route_records = make_native_route_records(routing, source)
    record(18, "wire_maker", route_records)

    project_directory = run_directory / names.project_directory
    native = write_native_project(
        circuit,
        selection,
        design,
        routing,
        route_records,
        catalogue=source,
        project_directory=project_directory,
    )
    record(19, "native_writer", native)
    _write_mapping(internal_directory / "expected_physical_contract.json", native.expected_contract)

    project_archive = package_project(project_directory, run_directory, circuit.name)
    record(20, "output_packager", {"project_archive": str(project_archive)})
    pcb = decide_pcb_output(selection, design)
    record(21, "pcb_decision", pcb)
    final = validate_final_output(native, project_archive)
    record(22, "final_validator", final)
    _write_mapping(internal_directory / "validation_report.json", final.json())
    if not final.passed:
        fail("final_validator", final.errors)

    pipeline_report = {
        "schema": PIPELINE_SCHEMA,
        "passed": True,
        "routing_mode": circuit.routing_mode,
        "component_count": len(design.components),
        "net_count": len(design.nets),
        "wire_count": len(routing.wires),
        "terminal_net_count": len(routing.terminalized_nets),
        "guessed_terminal_net_count": len(selection.guessed_terminal_nets),
        "pcb": pcb.json(),
        "project_archive": str(project_archive),
        "stage_reports": {name: str(path) for name, path in sorted(reports.items())},
    }
    _write_mapping(internal_directory / "pipeline_report.json", pipeline_report)
    reports["pipeline_report"] = internal_directory / "pipeline_report.json"
    internal_archive = package_internal_evidence(run_directory, internal_directory, circuit.name)
    progress("complete", "User project and private pipeline evidence packaged", 100)
    return PipelineResult(
        run_directory=run_directory,
        project_directory=project_directory,
        project_file=native.project_file,
        schematic_file=native.schematic_file,
        project_archive=project_archive,
        internal_archive=internal_archive,
        internal_directory=internal_directory,
        validation=final.schematic,
        components=design.components,
        wires=routing.wires,
        terminalized_nets=routing.terminalized_nets,
        terminal_labels=routing.labels,
        stage_reports=dict(reports),
    )
