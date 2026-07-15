"""Single executable LTspice pipeline with structured stage events."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shlex
import sys
import time
from typing import Any, Callable, Iterable

from .component_placer import place_components
from .component_selector import select_components
from .donor_native_executable import run_donor_native_executable
from .directive_validator import analysis_voltage_trace_nodes, translate_voltage_trace_labels, validate_analysis_references
from .final_validator import build_final_validation
from .input_adapter import canonicalize_source, write_json
from .ltspice_asc_writer import write_asc
from .ltspice_wire_maker import build_wire_plan
from .native_pin_mapper import translate_circuit_pins
from .netlist_validator import validate_native_netlist
from .output_packager import package_output
from .simulation_validator import OracleCommand, run_external_oracle, simulation_not_requested
from .timing_contract import (
    AnimationBudgetExceeded,
    AnimationTimingWatchdog,
    HARD_FAILURE_MESSAGE,
    OVERDUE_MESSAGE,
    validate_animation_budget_seconds,
)


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
    "overdue_message": OVERDUE_MESSAGE,
    "hard_failure_message": HARD_FAILURE_MESSAGE,
}


class PipelineStageFailure(RuntimeError):
    """Attach one deterministic pipeline stage to a user-safe failure."""

    def __init__(self, stage: str, cause: Exception):
        self.stage = stage
        self.cause = cause
        super().__init__(str(cause))


def _stage_failure(stage: str, cause: Exception) -> PipelineStageFailure:
    return PipelineStageFailure(stage, cause)


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


def parse_oracle_command(value: str) -> list[str]:
    """Parse the CLI oracle prefix with safe environment/home expansion.

    The command is passed directly to ``subprocess`` (never through a shell),
    so documented values such as ``WINEPREFIX=$HOME/...`` need deterministic
    expansion here.  Expand only token values; shell operators remain inert.
    """

    expanded: list[str] = []
    for token in shlex.split(value):
        token = os.path.expandvars(token)
        assignment = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", token)
        if assignment:
            token = f"{assignment.group(1)}={os.path.expanduser(assignment.group(2))}"
        else:
            token = os.path.expanduser(token)
        expanded.append(token)
    return expanded


def parse_animation_budget_seconds(value: str) -> float:
    """Argparse adapter for the explicitly supplied frontend animation budget."""

    try:
        budget = validate_animation_budget_seconds(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc
    assert budget is not None
    return budget


def _event(callback: Callable[[dict[str, Any]], None] | None, **payload: Any) -> None:
    if callback is not None:
        callback(payload)


def _stage(
    callback: Callable[[dict[str, Any]], None] | None,
    circuit_id: str,
    stage: str,
    percent: int,
    state: str,
    *,
    timing: AnimationTimingWatchdog | None = None,
    **extra: Any,
) -> None:
    if timing is not None:
        timing.set_active_stage(stage, percent)
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
    if timing is not None:
        timing.checkpoint(f"{stage}:{state}")


def _write_failure(
    run_dir: Path,
    source: Path,
    error: Exception,
    *,
    timing_evidence: dict[str, Any] | None = None,
    failed_stage: str = "pipeline",
) -> dict[str, Any]:
    failure_dir = run_dir / "failures" / _slug(source.stem)
    failure_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": EXECUTABLE_SCHEMA,
        "source": str(source),
        "ok": False,
        "failed_stage": failed_stage,
        "error": str(error),
    }
    if timing_evidence is not None:
        report["timing"] = timing_evidence
    write_json(failure_dir / "failure.json", report)
    return report


def _retract_user_artifact(
    run_dir: Path,
    artifacts: dict[str, Any] | None,
    *,
    output_id: str | None = None,
) -> None:
    """Remove a just-written download if its budget expires during packaging."""

    root = run_dir.resolve()
    raw_path: str | None = None
    if artifacts:
        user_project = artifacts.get("user_project")
        if isinstance(user_project, dict) and isinstance(user_project.get("path"), str):
            raw_path = user_project["path"]
    if raw_path is None and output_id:
        # ``output_id`` is reserved by this executable via ``_slug``. This
        # fallback covers package_output failing after its user ZIP is written
        # but before it can return a manifest to the caller.
        raw_path = f"outputs/{_slug(output_id)}/user_project/PROGEN_LTSPICE_PROJECT.zip"
    if raw_path is None:
        return
    candidate = (root / raw_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return
    candidate.unlink(missing_ok=True)
    manifest = candidate.parent.parent / "output_manifest.json"
    if manifest.is_file():
        manifest.unlink()


def _oracle_with_timing_deadline(
    oracle: OracleCommand | None,
    timing: AnimationTimingWatchdog | None,
) -> OracleCommand | None:
    """Cap every optional oracle subprocess at the remaining 2× budget."""

    if oracle is None or timing is None or not timing.enabled:
        return oracle
    timing.checkpoint("optional_simulation:before_oracle")
    remaining = timing.remaining_until_hard_failure()
    if remaining is None:
        return oracle
    if remaining <= 0:
        # ``checkpoint`` above raises once 2× has elapsed. This defensive
        # branch keeps the contract intact if a custom clock changes between
        # the two calls.
        timing.checkpoint("optional_simulation:hard_deadline")
        raise AnimationBudgetExceeded(timing.evidence())
    return OracleCommand(
        command=oracle.command,
        timeout_seconds=oracle.timeout_seconds,
        path_style=oracle.path_style,
        deadline_monotonic=time.monotonic() + remaining,
    )


def generate_one(
    source: Path,
    *,
    run_dir: Path,
    routing_mode: str | None,
    oracle: OracleCommand | None,
    reserved_artifact_ids: set[str] | None = None,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
    timing: AnimationTimingWatchdog | None = None,
) -> dict[str, Any]:
    """Run the whole deterministic backend for one canonical/loose JSON file."""

    start = time.monotonic()
    temporary_id = source.stem
    _stage(
        event_callback,
        temporary_id,
        "canonicalize_input",
        1,
        "started",
        timing=timing,
        message="Validating shared ProGenEDA JSON.",
    )
    try:
        circuit, input_report, original = canonicalize_source(source, routing_mode=routing_mode)
    except Exception as exc:
        raise _stage_failure("canonicalize_input", exc) from exc
    circuit_id = str(circuit.get("circuit_id") or temporary_id)
    if timing is not None:
        timing.set_circuit_id(circuit_id)
    artifact_id = _reserve_artifact_id(circuit_id, source, reserved_artifact_ids if reserved_artifact_ids is not None else set())
    base_dir = run_dir / "generation" / artifact_id
    stage_dir = base_dir / "internal"
    project_dir = base_dir / "project"
    stage_dir.mkdir(parents=True, exist_ok=True)
    project_dir.mkdir(parents=True, exist_ok=True)
    write_json(stage_dir / "main-input-canonical.json", circuit)
    write_json(stage_dir / "input-adapter-report.json", input_report)
    _stage(
        event_callback,
        circuit_id,
        "canonicalize_input",
        8,
        "completed",
        timing=timing,
        message="Canonical circuit JSON is ready.",
    )

    _stage(
        event_callback,
        circuit_id,
        "select_components",
        10,
        "started",
        timing=timing,
        message="Resolving LTspice symbols, pins, models, and safe fields.",
    )
    try:
        selected, selection_report = select_components(circuit)
    except Exception as exc:
        raise _stage_failure("select_components", exc) from exc
    write_json(stage_dir / "component-selection.json", selection_report)
    _stage(
        event_callback,
        circuit_id,
        "select_components",
        20,
        "completed",
        timing=timing,
        message="Component profiles resolved.",
    )

    raw_directives = list(circuit.get("spice_directives", [])) if isinstance(circuit.get("spice_directives"), list) else []
    project = circuit.get("project")
    if isinstance(project, dict) and isinstance(project.get("analysis"), list):
        raw_directives.extend(project["analysis"])
    directives = [str(item.get("text") or "") if isinstance(item, dict) else str(item) for item in raw_directives]
    try:
        analysis_reference_report = validate_analysis_references(
            directives,
            component_refs=[item.ref for item in selected],
            sweepable_refs=[item.ref for item in selected if item.profile.reference_prefix in {"V", "I"}],
            net_names=[str(name) for name in circuit.get("nets", {})] if isinstance(circuit.get("nets"), dict) else [],
        )
    except Exception as exc:
        raise _stage_failure("select_components", exc) from exc
    write_json(stage_dir / "analysis-reference-validation.json", analysis_reference_report)

    try:
        native_circuit, pin_mapper_report = translate_circuit_pins(circuit, selected)
    except Exception as exc:
        raise _stage_failure("select_components", exc) from exc
    write_json(stage_dir / "native-pin-translation.json", pin_mapper_report)
    write_json(stage_dir / "main-input-native-pins.json", native_circuit)

    _stage(
        event_callback,
        circuit_id,
        "place_components",
        22,
        "started",
        timing=timing,
        message="Placing native LTspice symbols on the 16-unit grid.",
    )
    try:
        placed, placement_report = place_components(native_circuit, selected)
    except Exception as exc:
        raise _stage_failure("place_components", exc) from exc
    write_json(stage_dir / "placement.json", placement_report)
    _stage(
        event_callback,
        circuit_id,
        "place_components",
        34,
        "completed",
        timing=timing,
        message="Placement contract generated.",
    )

    _stage(
        event_callback,
        circuit_id,
        "plan_connectivity",
        36,
        "started",
        timing=timing,
        message="Planning orthogonal wires and safe terminal labels.",
    )
    try:
        wire_plan = build_wire_plan(
            native_circuit,
            placed,
            force_terminal_nets=analysis_voltage_trace_nodes(directives),
        )
    except Exception as exc:
        raise _stage_failure("plan_connectivity", exc) from exc
    wire_plan_data = wire_plan.as_dict()
    write_json(stage_dir / "wire-plan.json", wire_plan_data)
    _stage(
        event_callback,
        circuit_id,
        "plan_connectivity",
        48,
        "completed",
        timing=timing,
        message="Native connectivity plan generated.",
    )

    try:
        native_directives, directive_net_report = translate_voltage_trace_labels(directives, wire_plan.label_map)
    except Exception as exc:
        raise _stage_failure("plan_connectivity", exc) from exc
    write_json(stage_dir / "analysis-net-label-translation.json", directive_net_report)

    _stage(
        event_callback,
        circuit_id,
        "write_native_project",
        50,
        "started",
        timing=timing,
        message="Writing deterministic ASC, ASY, and model assets.",
    )
    try:
        writer_result = write_asc(
            project_dir=project_dir,
            project_name=str(native_circuit.get("project", {}).get("name") or native_circuit.get("circuit_name") or circuit_id),
            placed=placed,
            wire_segments=wire_plan.segments,
            flags=wire_plan.flags,
            directives=native_directives,
        )
    except Exception as exc:
        raise _stage_failure("write_native_project", exc) from exc
    writer_report = writer_result.as_dict(project_dir)
    write_json(stage_dir / "native-writer-report.json", writer_report)
    _stage(
        event_callback,
        circuit_id,
        "write_native_project",
        63,
        "completed",
        timing=timing,
        message="Project-local LTspice files written.",
    )

    _stage(
        event_callback,
        circuit_id,
        "validate_native_project",
        65,
        "started",
        timing=timing,
        message="Reparsing ASC and ASY files and checking exact net membership.",
    )
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
        timing=timing,
        message="Native connectivity validation " + ("passed." if native_report.get("ok") else "failed."),
    )

    _stage(
        event_callback,
        circuit_id,
        "optional_simulation",
        81,
        "started",
        timing=timing,
        message="Recording optional LTspice oracle status.",
    )
    timed_oracle = _oracle_with_timing_deadline(oracle, timing)
    try:
        simulation_report = (
            run_external_oracle(writer_result.asc_path, oracle=timed_oracle, selected=selected, wire_plan=wire_plan)
            if timed_oracle
            else simulation_not_requested()
        )
    except Exception as exc:
        raise _stage_failure("optional_simulation", exc) from exc
    write_json(stage_dir / "simulation-report.json", simulation_report)
    simulation_state = "failed" if simulation_report.get("status") in {"failed", "timeout"} else "completed"
    _stage(
        event_callback,
        circuit_id,
        "optional_simulation",
        89,
        simulation_state,
        timing=timing,
        message=str(simulation_report.get("status")),
    )

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
        _stage(
            event_callback,
            circuit_id,
            "package_artifacts",
            91,
            "started",
            timing=timing,
            message="Creating user and internal artifact archives.",
        )
        timing_report = timing.evidence() if timing is not None and timing.enabled else None
        if timing_report is not None:
            write_json(stage_dir / "timing-contract-report.json", timing_report)
        stage_json = {
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
        }
        if timing_report is not None:
            stage_json["timing-contract"] = timing_report
        try:
            output_artifacts = package_output(
                run_dir=run_dir,
                circuit_id=circuit_id,
                output_id=artifact_id,
                project_dir=project_dir,
                asc_path=writer_result.asc_path,
                original_input=original,
                stage_json=stage_json,
            )
            write_json(stage_dir / "output-artifacts.json", output_artifacts)
            if timing is not None:
                timing.approve_artifact_release("package_artifacts:release_gate")
            _stage(
                event_callback,
                circuit_id,
                "package_artifacts",
                100,
                "completed",
                message="Validated user project archive is ready.",
            )
        except Exception as exc:
            _retract_user_artifact(run_dir, output_artifacts, output_id=artifact_id)
            output_artifacts = None
            (stage_dir / "output-artifacts.json").unlink(missing_ok=True)
            raise _stage_failure("package_artifacts", exc) from exc
    else:
        _stage(
            event_callback,
            circuit_id,
            "package_artifacts",
            100,
            "skipped",
            timing=timing,
            message="No user archive is created when deterministic validation fails.",
        )
        _stage(
            event_callback,
            circuit_id,
            "pipeline",
            100,
            "failed",
            timing=timing,
            message="; ".join(final_report.get("errors", [])) or "Deterministic validation failed.",
        )
    timing_report: dict[str, Any] | None = None
    if timing is not None and timing.enabled:
        timing.stop()
        timing_report = timing.evidence()
        write_json(stage_dir / "timing-contract-report.json", timing_report)
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
    if not final_report["ok"]:
        stage_status = final_report.get("stage_status", {})
        failed_stage = next(
            (
                stage
                for stage in ("canonicalize_input", "select_components", "place_components", "validate_native_project", "optional_simulation")
                if stage_status.get(
                    {
                        "canonicalize_input": "input",
                        "select_components": "component_selection",
                        "place_components": "placement",
                        "validate_native_project": "native_connectivity",
                        "optional_simulation": "simulation",
                    }[stage]
                ) in {"fail", "failed", "timeout"}
            ),
            "pipeline",
        )
        result["failed_stage"] = failed_stage
    if timing_report is not None:
        result["timing"] = timing_report
    write_json(base_dir / "result.json", result)
    return result


def run_executable(
    source: Path,
    *,
    output_root: Path,
    label: str = "ltspice",
    routing_mode: str | None = None,
    oracle_command: Iterable[str] | None = None,
    oracle_timeout_seconds: int = 90,
    oracle_path_style: str = "native",
    event_callback: Callable[[dict[str, Any]], None] | None = None,
    animation_budget_seconds: float | None = None,
    timing_clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    animation_budget_seconds = validate_animation_budget_seconds(animation_budget_seconds)
    run_dir = _create_run_dir(output_root, label)
    _event(event_callback, event="progress_policy", policy=PROGRESS_POLICY, timestamp=datetime.now(timezone.utc).isoformat())
    if animation_budget_seconds is not None:
        _event(
            event_callback,
            event="timing_policy",
            schema="progen-ltspice-animation-timing/v0.1",
            animation_budget_seconds=animation_budget_seconds,
            hard_failure_after_seconds=animation_budget_seconds * 2,
            overdue_message=OVERDUE_MESSAGE,
            hard_failure_message=HARD_FAILURE_MESSAGE,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    oracle = OracleCommand(tuple(oracle_command), oracle_timeout_seconds, oracle_path_style) if oracle_command else None
    results: list[dict[str, Any]] = []
    try:
        files = _source_files(source)
    except Exception as exc:
        result = _write_failure(run_dir, source, exc, failed_stage="source_discovery")
        results.append(result)
        _event(event_callback, event="stage", circuit_id=source.stem, stage="pipeline", percent=100, state="failed", message=str(exc))
        files = []
    reserved_artifact_ids: set[str] = set()
    for file in files:
        timing = AnimationTimingWatchdog(
            animation_budget_seconds=animation_budget_seconds,
            circuit_id=file.stem,
            event_callback=event_callback,
            clock=timing_clock or time.monotonic,
            use_background_timers=timing_clock is None,
        )
        timing.start()
        try:
            result = generate_one(
                file,
                run_dir=run_dir,
                routing_mode=routing_mode,
                oracle=oracle,
                reserved_artifact_ids=reserved_artifact_ids,
                event_callback=event_callback,
                timing=timing,
            )
        except AnimationBudgetExceeded as exc:
            timing.stop()
            failed_stage = str(timing.evidence().get("active_stage") or "pipeline")
            result = _write_failure(run_dir, file, exc, timing_evidence=timing.evidence(), failed_stage=failed_stage)
        except PipelineStageFailure as exc:
            timing.stop()
            result = _write_failure(
                run_dir,
                file,
                exc.cause,
                timing_evidence=timing.evidence() if timing.enabled else None,
                failed_stage=exc.stage,
            )
            _event(
                event_callback,
                event="stage",
                circuit_id=file.stem,
                stage=exc.stage,
                percent=dict(STAGES).get(exc.stage, 100),
                state="failed",
                message=str(exc.cause),
            )
            _event(event_callback, event="stage", circuit_id=file.stem, stage="pipeline", percent=100, state="failed", message=str(exc.cause))
        except Exception as exc:
            timing.stop()
            result = _write_failure(
                run_dir,
                file,
                exc,
                timing_evidence=timing.evidence() if timing.enabled else None,
                failed_stage="pipeline",
            )
            _event(event_callback, event="stage", circuit_id=file.stem, stage="pipeline", percent=100, state="failed", message=str(exc))
        else:
            timing.stop()
        results.append(result)
    summary = {
        "schema": EXECUTABLE_SCHEMA,
        "run_dir": str(run_dir),
        "source": str(source),
        "routing_mode": routing_mode or "source_or_combination_default",
        "progress_policy": PROGRESS_POLICY,
        "input_count": len(results),
        "accepted_count": sum(1 for item in results if item.get("ok")),
        "rejected_count": sum(1 for item in results if not item.get("ok")),
        "ok": bool(results) and all(item.get("ok") for item in results),
        "results": results,
    }
    if animation_budget_seconds is not None:
        summary["animation_timing"] = {
            "enabled": True,
            "animation_budget_seconds": animation_budget_seconds,
            "hard_failure_after_seconds": animation_budget_seconds * 2,
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
    parser.add_argument(
        "--engine",
        choices=("donor_native", "legacy_prototype"),
        default="donor_native",
        help="Generation engine. donor_native is the stock-symbol, physical-wire default; legacy_prototype remains only for historical regression work.",
    )
    parser.add_argument(
        "--routing-mode",
        choices=("wire", "terminal", "combination"),
        help="Optional LTspice routing override. Omit to honor routing.mode from the shared JSON.",
    )
    parser.add_argument("--oracle-command", help="Optional shell-style LTspice command prefix; the executable adds -netlist and the ASC path.")
    parser.add_argument("--oracle-timeout", type=int, default=90)
    parser.add_argument("--oracle-path-style", choices=("native", "wine_z"), default="native", help="How the optional oracle receives generated ASC paths.")
    parser.add_argument(
        "--animation-budget-seconds",
        type=parse_animation_budget_seconds,
        help="Optional frontend animation duration. Emits an overdue event at 1× and rejects user artifacts at 2×; no default is assumed.",
    )
    parser.add_argument("--events", choices=("summary", "ndjson"), default="summary", help="Emit structured stage events for UI/API forwarding.")
    args = parser.parse_args()

    def emit(payload: dict[str, Any]) -> None:
        if args.events == "ndjson":
            print(json.dumps(payload, sort_keys=True), flush=True)

    if args.engine == "donor_native":
        if args.routing_mode not in {None, "wire"}:
            parser.error("donor_native uses physical wires only; terminal and combination routing are legacy prototype modes.")
        if args.oracle_command:
            parser.error("The donor_native executable currently records deterministic ASC validation only; use the GUI/netlist verifier for LTspice execution evidence.")
        summary = run_donor_native_executable(
            args.source,
            output_root=args.outdir,
            label=args.label,
            event_callback=emit if args.events == "ndjson" else None,
            animation_budget_seconds=args.animation_budget_seconds,
        )
    else:
        summary = run_executable(
            args.source,
            output_root=args.outdir,
            label=args.label,
            routing_mode=args.routing_mode,
            oracle_command=parse_oracle_command(args.oracle_command) if args.oracle_command else None,
            oracle_timeout_seconds=args.oracle_timeout,
            oracle_path_style=args.oracle_path_style,
            event_callback=emit if args.events == "ndjson" else None,
            animation_budget_seconds=args.animation_budget_seconds,
        )
    if args.events == "ndjson":
        emit({"event": "complete", "summary": summary})
    else:
        print(json.dumps(summary, indent=2, sort_keys=True))
    raise SystemExit(0 if summary["ok"] else 1)
