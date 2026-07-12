"""Single executable LTspice pipeline with structured stage events."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shlex
import sys
import time
from typing import Any, Callable, Iterable

from .component_placer import place_components
from .component_selector import select_components
from .directive_validator import translate_voltage_trace_labels, validate_analysis_references
from .final_validator import build_final_validation
from .input_adapter import canonicalize_source, write_json
from .ltspice_asc_writer import write_asc
from .ltspice_wire_maker import build_wire_plan
from .native_pin_mapper import translate_circuit_pins
from .netlist_validator import validate_native_netlist
from .output_packager import package_output
from .simulation_validator import OracleCommand, run_external_oracle, simulation_not_requested


EXECUTABLE_SCHEMA = "progen-ltspice-executable-run/v0.1"
STAGES = (
    ("canonicalize_input", 8),
    ("select_components", 20),
    ("place_components", 34),
    ("plan_connectivity", 48),
    ("write_native_project", 63),
    ("validate_native_project", 79),
    ("optional_simulation", 89),
    ("package_artifacts", 100),
)
PROGRESS_POLICY = {
    "schema": "progen-ltspice-progress-policy/v0.1",
    "download_visibility": "only_after_package_artifacts_completed",
    "overdue_notice_at_animation_multiplier": 1,
    "hard_failure_at_animation_multiplier": 2,
    "overdue_message": "Taking longer than expected—please hold on.",
    "hard_failure_message": "Generation took longer than allowed time. Please try a simpler circuit.",
}


def _slug(value: object) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", str(value).lower()).strip("._") or "run"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")


def _create_run_dir(output_root: Path, label: str) -> Path:
    """Atomically reserve an immutable run directory, even within one second."""

    base = output_root / f"progen_ltspice_executable_run_{_now_stamp()}_{_slug(label)}"
    candidate = base
    suffix = 2
    while True:
        try:
            candidate.mkdir(parents=True, exist_ok=False)
            return candidate
        except FileExistsError:
            candidate = base.with_name(f"{base.name}_{suffix}")
            suffix += 1


def _reserve_artifact_id(circuit_id: str, source: Path, reserved: set[str]) -> str:
    """Keep repeated canonical IDs separate without changing their logical ID."""

    base = _slug(circuit_id)
    candidate = base
    if candidate in reserved:
        candidate = f"{base}_{_slug(source.stem)}"
    suffix = 2
    while candidate in reserved:
        candidate = f"{base}_{_slug(source.stem)}_{suffix}"
        suffix += 1
    reserved.add(candidate)
    return candidate


def _source_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source]
    if source.is_dir():
        files = sorted(path for path in source.rglob("*.json") if path.is_file())
        if files:
            return files
    raise ValueError(f"No JSON source input found at {source}.")


def _event(callback: Callable[[dict[str, Any]], None] | None, **payload: Any) -> None:
    if callback is not None:
        callback(payload)


def _stage(callback: Callable[[dict[str, Any]], None] | None, circuit_id: str, stage: str, percent: int, state: str, **extra: Any) -> None:
    _event(
        callback,
        event="stage",
        circuit_id=circuit_id,
        stage=stage,
        percent=percent,
        state=state,
        timestamp=datetime.now(timezone.utc).isoformat(),
        **extra,
    )


def _write_failure(run_dir: Path, source: Path, error: Exception) -> dict[str, Any]:
    failure_dir = run_dir / "failures" / _slug(source.stem)
    failure_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": EXECUTABLE_SCHEMA,
        "source": str(source),
        "ok": False,
        "error": str(error),
    }
    write_json(failure_dir / "failure.json", report)
    return report


def generate_one(
    source: Path,
    *,
    run_dir: Path,
    routing_mode: str,
    oracle: OracleCommand | None,
    reserved_artifact_ids: set[str] | None = None,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run the whole deterministic backend for one canonical/loose JSON file."""

    start = time.monotonic()
    temporary_id = source.stem
    _stage(event_callback, temporary_id, "canonicalize_input", 1, "started", message="Validating shared ProGenEDA JSON.")
    circuit, input_report, original = canonicalize_source(source, routing_mode=routing_mode)
    circuit_id = str(circuit.get("circuit_id") or temporary_id)
    artifact_id = _reserve_artifact_id(circuit_id, source, reserved_artifact_ids if reserved_artifact_ids is not None else set())
    base_dir = run_dir / "generation" / artifact_id
    stage_dir = base_dir / "internal"
    project_dir = base_dir / "project"
    stage_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    write_json(stage_dir / "main-input-canonical.json", circuit)
    write_json(stage_dir / "input-adapter-report.json", input_report)
    _stage(event_callback, circuit_id, "canonicalize_input", 8, "completed", message="Canonical circuit JSON is ready.")

    _stage(event_callback, circuit_id, "select_components", 10, "started", message="Resolving LTspice symbols, pins, models, and safe fields.")
    selected, selection_report = select_components(circuit)
    write_json(stage_dir / "component-selection.json", selection_report)
    _stage(event_callback, circuit_id, "select_components", 20, "completed", message="Component profiles resolved.")

    raw_directives = list(circuit.get("spice_directives", [])) if isinstance(circuit.get("spice_directives"), list) else []
    project = circuit.get("project")
    if isinstance(project, dict) and isinstance(project.get("analysis"), list):
        raw_directives.extend(project["analysis"])
    directives = [str(item.get("text") or "") if isinstance(item, dict) else str(item) for item in raw_directives]
    analysis_reference_report = validate_analysis_references(
        directives,
        component_refs=[item.ref for item in selected],
        sweepable_refs=[item.ref for item in selected if item.profile.reference_prefix in {"V", "I"}],
        net_names=[str(name) for name in circuit.get("nets", {})] if isinstance(circuit.get("nets"), dict) else [],
    )
    write_json(stage_dir / "analysis-reference-validation.json", analysis_reference_report)

    native_circuit, pin_mapper_report = translate_circuit_pins(circuit, selected)
    write_json(stage_dir / "native-pin-translation.json", pin_mapper_report)
    write_json(stage_dir / "main-input-native-pins.json", native_circuit)

    _stage(event_callback, circuit_id, "place_components", 22, "started", message="Placing native LTspice symbols on the 16-unit grid.")
    placed, placement_report = place_components(native_circuit, selected)
    write_json(stage_dir / "placement.json", placement_report)
    _stage(event_callback, circuit_id, "place_components", 34, "completed", message="Placement contract generated.")

    _stage(event_callback, circuit_id, "plan_connectivity", 36, "started", message="Planning orthogonal wires and safe terminal labels.")
    wire_plan = build_wire_plan(native_circuit, placed)
    wire_plan_data = wire_plan.as_dict()
    write_json(stage_dir / "wire-plan.json", wire_plan_data)
    _stage(event_callback, circuit_id, "plan_connectivity", 48, "completed", message="Native connectivity plan generated.")

    native_directives, directive_net_report = translate_voltage_trace_labels(directives, wire_plan.label_map)
    write_json(stage_dir / "analysis-net-label-translation.json", directive_net_report)

    _stage(event_callback, circuit_id, "write_native_project", 50, "started", message="Writing deterministic ASC, ASY, and model assets.")
    writer_result = write_asc(
        project_dir=project_dir,
        project_name=str(native_circuit.get("project", {}).get("name") or native_circuit.get("circuit_name") or circuit_id),
        placed=placed,
        wire_segments=wire_plan.segments,
        flags=wire_plan.flags,
        directives=native_directives,
    )
    writer_report = writer_result.as_dict(project_dir)
    write_json(stage_dir / "native-writer-report.json", writer_report)
    _stage(event_callback, circuit_id, "write_native_project", 63, "completed", message="Project-local LTspice files written.")

    _stage(event_callback, circuit_id, "validate_native_project", 65, "started", message="Reparsing ASC and ASY files and checking exact net membership.")
    native_report = validate_native_netlist(
        asc_path=writer_result.asc_path,
        project_dir=project_dir,
        placed=placed,
        wire_plan=wire_plan,
        requested_directives=native_directives,
        component_refs=[item.ref for item in selected],
        sweepable_refs=[item.ref for item in selected if item.profile.reference_prefix in {"V", "I"}],
        net_names=wire_plan.label_map.values(),
    )
    write_json(stage_dir / "native-netlist-validation-report.json", native_report)
    _stage(
        event_callback,
        circuit_id,
        "validate_native_project",
        79,
        "completed" if native_report.get("ok") else "failed",
        message="Native connectivity validation " + ("passed." if native_report.get("ok") else "failed."),
    )

    _stage(event_callback, circuit_id, "optional_simulation", 81, "started", message="Recording optional LTspice oracle status.")
    simulation_report = run_external_oracle(writer_result.asc_path, oracle=oracle) if oracle else simulation_not_requested()
    write_json(stage_dir / "simulation-report.json", simulation_report)
    simulation_state = "failed" if simulation_report.get("status") in {"failed", "timeout"} else "completed"
    _stage(event_callback, circuit_id, "optional_simulation", 89, simulation_state, message=str(simulation_report.get("status")))

    final_report = build_final_validation(
        input_report=input_report,
        selection_report=selection_report,
        placement_report=placement_report,
        native_report=native_report,
        simulation_report=simulation_report,
    )
    write_json(stage_dir / "final-validation-report.json", final_report)
    output_artifacts: dict[str, Any] | None = None
    if final_report["ok"]:
        _stage(event_callback, circuit_id, "package_artifacts", 91, "started", message="Creating user and internal artifact archives.")
        output_artifacts = package_output(
            run_dir=run_dir,
            circuit_id=circuit_id,
            output_id=artifact_id,
            project_dir=project_dir,
            asc_path=writer_result.asc_path,
            original_input=original,
            stage_json={
                "main-input-canonical": circuit,
                "main-input-native-pins": native_circuit,
                "input-adapter-report": input_report,
                "component-selection": selection_report,
                "native-pin-translation": pin_mapper_report,
                "analysis-reference-validation": analysis_reference_report,
                "analysis-net-label-translation": directive_net_report,
                "placement": placement_report,
                "wire-plan": wire_plan_data,
                "native-writer-report": writer_report,
                "native-netlist-validation-report": native_report,
                "simulation-report": simulation_report,
                "final-validation-report": final_report,
            },
        )
        write_json(stage_dir / "output-artifacts.json", output_artifacts)
        _stage(event_callback, circuit_id, "package_artifacts", 100, "completed", message="Validated user project archive is ready.")
    else:
        _stage(event_callback, circuit_id, "package_artifacts", 100, "skipped", message="No user archive is created when deterministic validation fails.")
        _stage(
            event_callback,
            circuit_id,
            "pipeline",
            100,
            "failed",
            message="; ".join(final_report.get("errors", [])) or "Deterministic validation failed.",
        )
    result = {
        "schema": EXECUTABLE_SCHEMA,
        "circuit_id": circuit_id,
        "artifact_id": artifact_id,
        "source": str(source),
        "ok": bool(final_report["ok"]),
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "generation_dir": str(base_dir.relative_to(run_dir)),
        "asc_path": str(writer_result.asc_path.relative_to(run_dir)),
        "final_validation": final_report,
        "output_artifacts": output_artifacts,
    }
    write_json(base_dir / "result.json", result)
    return result


def run_executable(
    source: Path,
    *,
    output_root: Path,
    label: str = "ltspice",
    routing_mode: str = "combination",
    oracle_command: Iterable[str] | None = None,
    oracle_timeout_seconds: int = 90,
    oracle_path_style: str = "native",
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    run_dir = _create_run_dir(output_root, label)
    _event(event_callback, event="progress_policy", policy=PROGRESS_POLICY, timestamp=datetime.now(timezone.utc).isoformat())
    oracle = OracleCommand(tuple(oracle_command), oracle_timeout_seconds, oracle_path_style) if oracle_command else None
    results: list[dict[str, Any]] = []
    try:
        files = _source_files(source)
    except Exception as exc:
        result = _write_failure(run_dir, source, exc)
        results.append(result)
        _event(event_callback, event="stage", circuit_id=source.stem, stage="pipeline", percent=100, state="failed", message=str(exc))
        files = []
    reserved_artifact_ids: set[str] = set()
    for file in files:
        try:
            result = generate_one(
                file,
                run_dir=run_dir,
                routing_mode=routing_mode,
                oracle=oracle,
                reserved_artifact_ids=reserved_artifact_ids,
                event_callback=event_callback,
            )
        except Exception as exc:
            result = _write_failure(run_dir, file, exc)
            _event(event_callback, event="stage", circuit_id=file.stem, stage="pipeline", percent=100, state="failed", message=str(exc))
        results.append(result)
    summary = {
        "schema": EXECUTABLE_SCHEMA,
        "run_dir": str(run_dir),
        "source": str(source),
        "routing_mode": routing_mode,
        "progress_policy": PROGRESS_POLICY,
        "input_count": len(results),
        "accepted_count": sum(1 for item in results if item.get("ok")),
        "rejected_count": sum(1 for item in results if not item.get("ok")),
        "ok": bool(results) and all(item.get("ok") for item in results),
        "results": results,
    }
    write_json(run_dir / "run_manifest.json", summary)
    (run_dir / "README.md").write_text(
        "# ProGenEDA LTspice executable run\n\n"
        "Each accepted circuit has a user-only `PROGEN_LTSPICE_PROJECT.zip` and a separate internal evidence bundle. "
        "No user archive is emitted for a failed native validation.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate validated LTspice projects from the shared ProGenEDA circuit JSON.")
    parser.add_argument("source", type=Path, help="One loose/canonical JSON file or a directory of JSON files.")
    parser.add_argument("--outdir", type=Path, default=Path("ltspice/examples"), help="Parent directory for a new immutable run.")
    parser.add_argument("--label", default="ltspice", help="Human-readable immutable run label.")
    parser.add_argument("--routing-mode", choices=("wire", "terminal", "combination"), default="combination")
    parser.add_argument("--oracle-command", help="Optional shell-style LTspice command prefix; the executable adds -netlist and the ASC path.")
    parser.add_argument("--oracle-timeout", type=int, default=90)
    parser.add_argument("--oracle-path-style", choices=("native", "wine_z"), default="native", help="How the optional oracle receives generated ASC paths.")
    parser.add_argument("--events", choices=("summary", "ndjson"), default="summary", help="Emit structured stage events for UI/API forwarding.")
    args = parser.parse_args()

    def emit(payload: dict[str, Any]) -> None:
        if args.events == "ndjson":
            print(json.dumps(payload, sort_keys=True), flush=True)

    summary = run_executable(
        args.source,
        output_root=args.outdir,
        label=args.label,
        routing_mode=args.routing_mode,
        oracle_command=shlex.split(args.oracle_command) if args.oracle_command else None,
        oracle_timeout_seconds=args.oracle_timeout,
        oracle_path_style=args.oracle_path_style,
        event_callback=emit if args.events == "ndjson" else None,
    )
    if args.events == "ndjson":
        emit({"event": "complete", "summary": summary})
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["ok"] else 1)
