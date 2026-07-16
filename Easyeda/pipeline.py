"""End-to-end donor-native EasyEDA generation pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping
import zipfile

from .catalogue import CATALOGUE_VERSION, get_entry
from .donor_source import DonorPacket, EasyedaDonorSource
from .geometry import place_components, route_nets
from .ir import Circuit, load_circuit
from .native import NativeWriteResult, write_project
from .validator import ValidationResult, validate_native_project


PIPELINE_SCHEMA = "progen-easyeda-pipeline/v1"


class PipelineError(RuntimeError):
    """Generation did not satisfy the selected mode's release contract."""


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _new_run_directory(output_root: Path, name: str) -> Path:
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S_%f")
    candidate = output_root / f"{timestamp}_{name}"
    suffix = 1
    while candidate.exists():
        candidate = output_root / f"{timestamp}_{name}_v{suffix}"
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate


def _resolve_packets(
    source: EasyedaDonorSource,
    circuit: Circuit,
) -> dict[str, DonorPacket]:
    unique = {component.kind: get_entry(component.kind) for component in circuit.components}
    workers = min(8, max(1, len(unique)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="easyeda-donor") as executor:
        futures = {
            kind: executor.submit(source.resolve, entry)
            for kind, entry in unique.items()
        }
        by_kind = {kind: future.result() for kind, future in futures.items()}
    return {
        component.identifier: by_kind[component.kind]
        for component in circuit.components
    }


def _placement_report(placed: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "schema": "progen-easyeda-placement/v1",
        "components": [
            {
                "id": item.component.identifier,
                "reference": item.component.reference,
                "kind": item.component.kind,
                "x": item.x,
                "y": item.y,
                "rotation": item.rotation,
                "body": list(item.body),
                "pins": {name: list(point) for name, point in sorted(item.pins.items())},
            }
            for item in placed
        ],
    }


def _routing_report(routed: tuple[Any, ...]) -> dict[str, Any]:
    return {
        "schema": "progen-easyeda-routing/v1",
        "nets": [
            {
                "name": item.name,
                "terminalized": item.terminalized,
                "reason": item.reason,
                "endpoints": list(item.endpoints),
                "segments": [
                    {"start": list(start), "end": list(end)}
                    for start, end in item.segments
                ],
            }
            for item in routed
        ],
    }


def _pcb_report(native: NativeWriteResult) -> dict[str, Any]:
    return {
        "schema": "progen-easyeda-pcb-report/v1",
        "ready": native.pcb.ready,
        "reason": native.pcb.reason,
        "component_count": native.pcb.component_count,
        "track_count": native.pcb.track_count,
        "placements": {
            reference: list(point)
            for reference, point in sorted(native.pcb.placements.items())
        },
        "pad_points": {
            endpoint: list(point)
            for endpoint, point in sorted(native.pcb.pad_points.items())
        },
    }


def _zip_internal(run_directory: Path, project_path: Path) -> Path:
    archive_path = run_directory / f"{project_path.stem}_internal.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(run_directory.rglob("*")):
            if not path.is_file() or path == archive_path:
                continue
            archive.write(path, path.relative_to(run_directory))
    return archive_path


def generate_project(
    input_value: Path | str | Mapping[str, Any],
    *,
    source_pack: Path | str,
    output_root: Path | str,
    routing_mode: str | None = None,
) -> dict[str, Any]:
    """Generate, validate, and package one immutable EasyEDA project run."""

    circuit = load_circuit(input_value, routing_mode=routing_mode)
    source = EasyedaDonorSource(Path(source_pack))
    run_directory = _new_run_directory(Path(output_root).expanduser().resolve(), circuit.name)
    normalized_path = run_directory / "normalized_input.json"
    _json(normalized_path, circuit.normalized_json())
    _json(run_directory / "source_provenance.json", source.provenance())

    packets = _resolve_packets(source, circuit)
    placed = place_components(circuit, packets)
    routed = route_nets(circuit, placed)
    _json(run_directory / "placement.json", _placement_report(placed))
    _json(run_directory / "routing.json", _routing_report(routed))
    wire_failures = [
        net.name
        for net in routed
        if circuit.routing_mode == "wire" and net.reason in {"unroutable", "single_endpoint"}
    ]
    if wire_failures:
        report = {
            "schema": PIPELINE_SCHEMA,
            "passed": False,
            "stage": "wire_planner",
            "errors": [f"strict wire mode failed for nets: {wire_failures}"],
        }
        _json(run_directory / "pipeline_report.json", report)
        _zip_internal(run_directory, normalized_path)
        raise PipelineError(report["errors"][0])

    project_path = run_directory / f"{circuit.name}.eprj"
    native = write_project(project_path, source, circuit, placed, routed, packets)
    _json(run_directory / "donor_manifest.json", native.donor_manifest)
    _json(run_directory / "pcb_report.json", _pcb_report(native))
    validation = validate_native_project(project_path, circuit, native, packets)
    _json(run_directory / "validation_report.json", validation.report)
    pipeline_report = {
        "schema": PIPELINE_SCHEMA,
        "passed": validation.passed,
        "catalogue": CATALOGUE_VERSION,
        "routing_mode": circuit.routing_mode,
        "project_path": str(project_path),
        "component_count": len(circuit.components),
        "net_count": len(circuit.nets),
        "terminal_net_count": sum(1 for net in routed if net.terminalized),
        "wire_net_count": sum(1 for net in routed if not net.terminalized and net.segments),
        "pcb_ready": native.pcb.ready,
        "pcb_reason": native.pcb.reason,
        "validation_errors": validation.report["errors"],
    }
    _json(run_directory / "pipeline_report.json", pipeline_report)
    internal_zip = _zip_internal(run_directory, project_path)
    result = {
        **pipeline_report,
        "run_directory": str(run_directory),
        "project_path": str(project_path),
        "internal_zip": str(internal_zip),
        "normalized_input": str(normalized_path),
        "validation_report": str(run_directory / "validation_report.json"),
        "pcb_report": str(run_directory / "pcb_report.json"),
    }
    if not validation.passed:
        raise PipelineError(
            f"Generated project failed deterministic validation; see {run_directory / 'validation_report.json'}"
        )
    return result


def validate_project(
    project_path: Path | str,
    input_value: Path | str | Mapping[str, Any],
    *,
    source_pack: Path | str,
    routing_mode: str | None = None,
) -> ValidationResult:
    """Regenerate the deterministic model and validate an existing project."""

    circuit = load_circuit(input_value, routing_mode=routing_mode)
    source = EasyedaDonorSource(Path(source_pack))
    packets = _resolve_packets(source, circuit)
    placed = place_components(circuit, packets)
    routed = route_nets(circuit, placed)
    temporary_path = Path(project_path).with_suffix(".validation-model.eprj")
    native = write_project(temporary_path, source, circuit, placed, routed, packets)
    try:
        native_for_target = NativeWriteResult(
            project_path=Path(project_path),
            schematic_document_uuid=native.schematic_document_uuid,
            pcb_document_uuid=native.pcb_document_uuid,
            terminal_instances=native.terminal_instances,
            pcb=native.pcb,
            donor_manifest=native.donor_manifest,
        )
        return validate_native_project(Path(project_path), circuit, native_for_target, packets)
    finally:
        temporary_path.unlink(missing_ok=True)
