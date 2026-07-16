"""Executable donor-native LTspice pipeline.

This is the active rebuild path: shared main JSON becomes stock LTspice
symbols, catalogue-approved attributes, and body-safe physical wires. It is
separate from the retained legacy prototype executable so existing historical
fixtures stay reproducible while the new native coverage grows.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any, Callable

from .donor_asc_parser import parse_donor_asc
from .donor_native_asc_writer import write_donor_native_asc
from .input_adapter import canonicalize_source, write_json
from .native_canonical_adapter import NativeCanonicalAdapterError, adapt_canonical_native_circuit
from .native_beautifier import beautify_native_placement
from .native_placer import native_live_state, place_native_components
from .native_wire_router import NativeWireRouterError, donor_native_recipe, route_native_wires
from .output_packager import package_output
from .timing_contract import (
    AnimationBudgetExceeded,
    AnimationTimingWatchdog,
    HARD_FAILURE_MESSAGE,
    OVERDUE_MESSAGE,
    validate_animation_budget_seconds,
)


DONOR_NATIVE_EXECUTABLE_SCHEMA = "progen-ltspice-donor-native-executable/v1"
DONOR_NATIVE_STAGES = (
    ("canonicalize_input", 10),
    ("resolve_donor_catalogue", 25),
    ("place_stock_symbols", 38),
    ("beautify_layout", 50),
    ("route_physical_wires", 64),
    ("write_native_asc", 78),
    ("validate_native_asc", 90),
    ("package_artifacts", 100),
)
DONOR_NATIVE_PROGRESS_POLICY = {
    "schema": "progen-ltspice-progress-policy/v0.1",
    "download_visibility": "only_after_package_artifacts_completed",
    "overdue_notice_at_animation_multiplier": 1,
    "hard_failure_at_animation_multiplier": 2,
    "overdue_message": OVERDUE_MESSAGE,
    "hard_failure_message": HARD_FAILURE_MESSAGE,
}


class DonorNativeStageFailure(RuntimeError):
    """A deterministic native stage failed before an artifact could be released."""

    def __init__(self, stage: str, cause: Exception):
        self.stage = stage
        self.cause = cause
        super().__init__(str(cause))


def _slug(value: object) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", str(value).lower()).strip("._") or "ltspice_native"


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y_%m_%d_%H%M%S")


def _run_dir(root: Path, label: str) -> Path:
    base = root / f"progen_ltspice_donor_native_run_{_stamp()}_{_slug(label)}"
    candidate = base
    index = 2
    while candidate.exists():
        candidate = base.with_name(f"{base.name}_{index}")
        index += 1
    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _sources(source: Path) -> list[Path]:
    if source.is_file() and source.suffix.lower() == ".json":
        return [source]
    if source.is_dir():
        files = sorted(path for path in source.rglob("*.json") if path.is_file())
        if files:
            return files
    raise ValueError(f"No JSON input found at {source}.")


def _event(callback: Callable[[dict[str, Any]], None] | None, **payload: Any) -> None:
    if callback is not None:
        callback(payload)


def _stage(
    callback: Callable[[dict[str, Any]], None] | None,
    circuit_id: str,
    stage: str,
    percent: int,
    state: str,
    message: str,
    *,
    timing: AnimationTimingWatchdog | None = None,
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
        message=message,
        timestamp=datetime.now(timezone.utc).isoformat(),
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
    """Persist a deterministic failure without exposing a user download."""

    failure_dir = run_dir / "failures" / _slug(source.stem)
    failure_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": DONOR_NATIVE_EXECUTABLE_SCHEMA,
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
    """Remove a just-written downloadable ZIP if release approval fails.

    ``package_output`` deliberately writes the user ZIP before returning its
    manifest.  The timing release gate therefore needs a fallback path for an
    exception that arrives after that write but before an artifact manifest is
    available to this caller.
    """

    root = run_dir.resolve()
    raw_path: str | None = None
    if artifacts:
        user_project = artifacts.get("user_project")
        if isinstance(user_project, dict) and isinstance(user_project.get("path"), str):
            raw_path = user_project["path"]
    if raw_path is None and output_id:
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
    manifest.unlink(missing_ok=True)


def _timing_failed_stage(timing: AnimationTimingWatchdog) -> str:
    """Recover the active deterministic stage from serializable watchdog data."""

    evidence = timing.evidence()
    events = evidence.get("events")
    if isinstance(events, list):
        for event in reversed(events):
            if isinstance(event, dict) and event.get("state") == "hard_failure" and event.get("stage"):
                return str(event["stage"])
    return "pipeline"


def _validate_written_native_asc(path: Path, recipe: dict[str, Any]) -> dict[str, Any]:
    """Independently parse the file and prove the stock-only output boundary."""

    document = parse_donor_asc(path)
    errors: list[str] = []
    expected_symbols = [str(item["type"]) for item in recipe["components"]]
    actual_refs = [symbol.ref for symbol in document.symbols]
    expected_refs = [str(item["ref"]) for item in recipe["components"]]
    if document.version != "4.1":
        errors.append(f"ASC version is {document.version!r}, not donor Version 4.1.")
    if [flag.name for flag in document.flags if flag.name != "0"]:
        errors.append("ASC contains a non-ground FLAG terminal.")
    if any("progeneda" in symbol.name.casefold() for symbol in document.symbols):
        errors.append("ASC contains a legacy progeneda custom symbol.")
    if actual_refs != expected_refs:
        errors.append(f"ASC symbol reference sequence differs: {actual_refs!r} vs {expected_refs!r}.")
    if len(document.wires) != len(recipe["wires"]):
        errors.append("ASC wire count differs from the physical router recipe.")
    if len(document.flags) != len(recipe["ground_flags"]):
        errors.append("ASC ground flag count differs from the physical router recipe.")
    return {
        "schema": DONOR_NATIVE_EXECUTABLE_SCHEMA,
        "stage": "donor_native_written_asc_validator",
        "ok": not errors,
        "errors": errors,
        "encoding": document.encoding,
        "symbol_count": len(document.symbols),
        "symbol_type_ids": expected_symbols,
        "wire_count": len(document.wires),
        "ground_flag_count": len(document.flags),
        "directive_count": len(document.directives),
        "terminal_fallback": "forbidden",
        "custom_symbols": "forbidden",
    }


def _generate_one(
    source: Path,
    run_dir: Path,
    *,
    event_callback: Callable[[dict[str, Any]], None] | None,
    timing: AnimationTimingWatchdog | None = None,
) -> dict[str, Any]:
    start = time.monotonic()
    temporary_id = source.stem
    _stage(
        event_callback,
        temporary_id,
        "canonicalize_input",
        1,
        "started",
        "Repairing and validating the shared ProGenEDA JSON.",
        timing=timing,
    )
    try:
        canonical, adapter_report, original = canonicalize_source(source, routing_mode="wire")
    except Exception as exc:
        raise DonorNativeStageFailure("canonicalize_input", exc) from exc
    circuit_id = str(canonical.get("circuit_id") or temporary_id)
    if timing is not None:
        timing.set_circuit_id(circuit_id)
    artifact_id = _slug(circuit_id)
    base = run_dir / "generation" / artifact_id
    internal = base / "internal"
    project = base / "project"
    internal.mkdir(parents=True, exist_ok=True)
    project.mkdir(parents=True, exist_ok=True)
    write_json(internal / "main-input-canonical.json", canonical)
    write_json(internal / "input-adapter-report.json", adapter_report)
    _stage(
        event_callback,
        circuit_id,
        "canonicalize_input",
        10,
        "completed",
        "Shared main JSON is ready.",
        timing=timing,
    )

    _stage(
        event_callback,
        circuit_id,
        "resolve_donor_catalogue",
        12,
        "started",
        "Resolving only donor-proven stock symbols and properties.",
        timing=timing,
    )
    try:
        native, native_adapter_report = adapt_canonical_native_circuit(canonical)
    except Exception as exc:
        raise DonorNativeStageFailure("resolve_donor_catalogue", exc) from exc
    write_json(internal / "donor-native-adapter-report.json", native_adapter_report)
    write_json(internal / "main-input-donor-native.json", native)
    _stage(
        event_callback,
        circuit_id,
        "resolve_donor_catalogue",
        25,
        "completed",
        "Donor catalogue resolution is complete.",
        timing=timing,
    )

    _stage(
        event_callback,
        circuit_id,
        "place_stock_symbols",
        28,
        "started",
        "Placing installed LTspice stock symbols on their exact pin grid.",
        timing=timing,
    )
    try:
        initial_placement, initial_placement_report = place_native_components(native, arrange=False)
    except Exception as exc:
        raise DonorNativeStageFailure("place_stock_symbols", exc) from exc
    write_json(internal / "native-initial-placement.json", initial_placement)
    write_json(internal / "native-initial-placement-report.json", initial_placement_report)
    _stage(
        event_callback,
        circuit_id,
        "place_stock_symbols",
        38,
        "completed",
        "Initial stock symbol placement is collision-free.",
        timing=timing,
    )

    _stage(
        event_callback,
        circuit_id,
        "beautify_layout",
        41,
        "started",
        "Applying topology-aware coordinate and rotation edits without changing circuit facts.",
        timing=timing,
    )
    try:
        placement, beautifier_report = beautify_native_placement(native, initial_placement)
        placement_report = beautifier_report["placement_report"]
    except Exception as exc:
        raise DonorNativeStageFailure("beautify_layout", exc) from exc
    write_json(internal / "native-placement.json", placement)
    write_json(internal / "native-placement-report.json", placement_report)
    write_json(internal / "native-beautifier-report.json", beautifier_report)
    _stage(
        event_callback,
        circuit_id,
        "beautify_layout",
        50,
        "completed",
        "Graph-layered layout is ready for physical routing.",
        timing=timing,
    )

    _stage(
        event_callback,
        circuit_id,
        "route_physical_wires",
        53,
        "started",
        "Routing every endpoint through direct body-safe LTspice wires.",
        timing=timing,
    )
    try:
        routes, routing_report = route_native_wires(native, placement)
        recipe = donor_native_recipe(native, placement, routes)
    except Exception as exc:
        raise DonorNativeStageFailure("route_physical_wires", exc) from exc
    live_state = native_live_state(native, placement, routes=routes)
    write_json(internal / "native-wire-routes.json", routes)
    write_json(internal / "native-routing-report.json", routing_report)
    write_json(internal / "native-live-catalogue.json", live_state)
    write_json(internal / "native-asc-recipe.json", recipe)
    _stage(
        event_callback,
        circuit_id,
        "route_physical_wires",
        64,
        "completed",
        "Every logical endpoint has a physical wire tree; no labels were used.",
        timing=timing,
    )

    _stage(
        event_callback,
        circuit_id,
        "write_native_asc",
        67,
        "started",
        "Writing one CP1252 donor-native ASC file with no ASY or model library.",
        timing=timing,
    )
    asc_path = project / f"{_slug(circuit_id)}.asc"
    try:
        writer = write_donor_native_asc(recipe, asc_path)
    except Exception as exc:
        raise DonorNativeStageFailure("write_native_asc", exc) from exc
    writer_report = {
        "schema": DONOR_NATIVE_EXECUTABLE_SCHEMA,
        "stage": "donor_native_asc_writer",
        "asc": asc_path.name,
        "sha256": writer.sha256,
        "size_bytes": writer.size_bytes,
        "component_count": writer.component_count,
        "wire_count": writer.wire_count,
        "ground_count": writer.ground_count,
        "directive_count": writer.directive_count,
        "generated_assets": [asc_path.name],
        "custom_asy": False,
        "model_library": False,
    }
    write_json(internal / "native-writer-report.json", writer_report)
    _stage(
        event_callback,
        circuit_id,
        "write_native_asc",
        78,
        "completed",
        "The stock-symbol ASC is written.",
        timing=timing,
    )

    _stage(
        event_callback,
        circuit_id,
        "validate_native_asc",
        81,
        "started",
        "Reparsing the written ASC and enforcing the no-terminal boundary.",
        timing=timing,
    )
    written_report = _validate_written_native_asc(asc_path, recipe)
    write_json(internal / "written-asc-validation.json", written_report)
    if not written_report["ok"]:
        raise DonorNativeStageFailure("validate_native_asc", ValueError("; ".join(written_report["errors"])))
    _stage(
        event_callback,
        circuit_id,
        "validate_native_asc",
        90,
        "completed",
        "Independent native ASC validation passed.",
        timing=timing,
    )

    _stage(
        event_callback,
        circuit_id,
        "package_artifacts",
        91,
        "started",
        "Packaging the openable stock-symbol ASC.",
        timing=timing,
    )
    stage_json = {
        "main-input-canonical": canonical,
        "input-adapter-report": adapter_report,
        "donor-native-adapter-report": native_adapter_report,
        "main-input-donor-native": native,
        "native-initial-placement": initial_placement,
        "native-initial-placement-report": initial_placement_report,
        "native-placement": placement,
        "native-placement-report": placement_report,
        "native-beautifier-report": beautifier_report,
        "native-wire-routes": routes,
        "native-routing-report": routing_report,
        "native-live-catalogue": live_state,
        "native-asc-recipe": recipe,
        "native-writer-report": writer_report,
        "written-asc-validation": written_report,
    }
    timing_report = timing.evidence() if timing is not None and timing.enabled else None
    if timing_report is not None:
        write_json(internal / "timing-contract-report.json", timing_report)
    if timing_report is not None:
        stage_json["timing-contract"] = timing_report
    artifacts: dict[str, Any] | None = None
    try:
        artifacts = package_output(
            run_dir=run_dir,
            circuit_id=circuit_id,
            output_id=artifact_id,
            project_dir=project,
            asc_path=asc_path,
            original_input=original,
            stage_json=stage_json,
        )
        write_json(internal / "output-artifacts.json", artifacts)
        if timing is not None:
            timing.approve_artifact_release("package_artifacts:release_gate")
    except AnimationBudgetExceeded:
        _retract_user_artifact(run_dir, artifacts, output_id=artifact_id)
        (internal / "output-artifacts.json").unlink(missing_ok=True)
        raise
    except Exception as exc:
        _retract_user_artifact(run_dir, artifacts, output_id=artifact_id)
        (internal / "output-artifacts.json").unlink(missing_ok=True)
        raise DonorNativeStageFailure("package_artifacts", exc) from exc
    _stage(event_callback, circuit_id, "package_artifacts", 100, "completed", "Validated native project archive is ready.")

    timing_report = None
    if timing is not None and timing.enabled:
        timing.stop()
        timing_report = timing.evidence()
        write_json(internal / "timing-contract-report.json", timing_report)

    result = {
        "schema": DONOR_NATIVE_EXECUTABLE_SCHEMA,
        "ok": True,
        "circuit_id": circuit_id,
        "artifact_id": artifact_id,
        "source": str(source),
        "elapsed_seconds": round(time.monotonic() - start, 3),
        "generation_dir": str(base.relative_to(run_dir)),
        "asc_path": str(asc_path.relative_to(run_dir)),
        "output_artifacts": artifacts,
        "final_validation": written_report,
    }
    if timing_report is not None:
        result["timing"] = timing_report
    write_json(base / "result.json", result)
    return result


def run_donor_native_executable(
    source: Path,
    *,
    output_root: Path,
    label: str = "ltspice_native",
    event_callback: Callable[[dict[str, Any]], None] | None = None,
    animation_budget_seconds: float | None = None,
    timing_clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Generate a run where any unsupported fact fails deterministically."""

    animation_budget_seconds = validate_animation_budget_seconds(animation_budget_seconds)
    run_dir = _run_dir(output_root, label)
    _event(
        event_callback,
        event="progress_policy",
        policy=DONOR_NATIVE_PROGRESS_POLICY,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
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
    results: list[dict[str, Any]] = []
    try:
        files = _sources(source)
    except Exception as exc:
        failure = _write_failure(run_dir, source, exc, failed_stage="source_discovery")
        files = []
        results.append(failure)
        _event(
            event_callback,
            event="stage",
            circuit_id=source.stem,
            stage="pipeline",
            percent=100,
            state="failed",
            message=str(exc),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
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
            result = _generate_one(file, run_dir, event_callback=event_callback, timing=timing)
        except AnimationBudgetExceeded as exc:
            timing.stop()
            timing_evidence = timing.evidence()
            result = _write_failure(
                run_dir,
                file,
                exc,
                timing_evidence=timing_evidence,
                failed_stage=_timing_failed_stage(timing),
            )
            _stage(event_callback, file.stem, "pipeline", 100, "failed", str(exc))
        except DonorNativeStageFailure as exc:
            timing.stop()
            result = _write_failure(
                run_dir,
                file,
                exc.cause,
                timing_evidence=timing.evidence() if timing.enabled else None,
                failed_stage=exc.stage,
            )
            _stage(event_callback, file.stem, exc.stage, dict(DONOR_NATIVE_STAGES).get(exc.stage, 100), "failed", str(exc.cause))
            _stage(event_callback, file.stem, "pipeline", 100, "failed", str(exc.cause))
        except Exception as exc:
            timing.stop()
            result = _write_failure(
                run_dir,
                file,
                exc,
                timing_evidence=timing.evidence() if timing.enabled else None,
                failed_stage="pipeline",
            )
            _stage(event_callback, file.stem, "pipeline", 100, "failed", str(exc))
        else:
            timing.stop()
        results.append(result)
    summary = {
        "schema": DONOR_NATIVE_EXECUTABLE_SCHEMA,
        "engine": "donor_native",
        "run_dir": str(run_dir),
        "source": str(source),
        "routing_mode": "wire",
        "progress_policy": DONOR_NATIVE_PROGRESS_POLICY,
        "input_count": len(results),
        "accepted_count": sum(bool(item.get("ok")) for item in results),
        "rejected_count": sum(not bool(item.get("ok")) for item in results),
        "ok": bool(results) and all(bool(item.get("ok")) for item in results),
        "results": results,
        "terminal_fallback": "forbidden",
        "custom_symbol_fallback": "forbidden",
    }
    if animation_budget_seconds is not None:
        summary["animation_timing"] = {
            "enabled": True,
            "animation_budget_seconds": animation_budget_seconds,
            "hard_failure_after_seconds": animation_budget_seconds * 2,
        }
    write_json(run_dir / "run_manifest.json", summary)
    (run_dir / "README.md").write_text(
        "# Donor-native LTspice run\n\n"
        "Accepted projects contain a stock-library ASC with direct physical wires only. "
        "No custom ASY, generated model library, named terminal, or user download is created for a failed stage.\n",
        encoding="utf-8",
    )
    return summary
