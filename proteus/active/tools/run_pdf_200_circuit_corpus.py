"""Run every PDF-derived circuit through the portable Proteus executable.

Each input is a safe placement-only projection of its complete canonical
pin-wiring specification.  The command intentionally passes ``--no-terminals``
because the current executable does not yet emit arbitrary physical nets or
multi-pin attachment units for this corpus.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Mapping
from zipfile import BadZipFile, ZipFile


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_ROOT = REPOSITORY_ROOT / "proteus" / "active" / "examples" / "proteus_200_circuits"
DEFAULT_EXECUTABLE = REPOSITORY_ROOT / "proteus" / "active" / "release" / "ProgenProteus.exe"
DEFAULT_OUTPUT = REPOSITORY_ROOT / "proteus" / "experiments" / "runs" / "2026-07-17_pdf_200_circuit_placement_controls"
LOCAL_GATE_SCRIPT = REPOSITORY_ROOT / "proteus" / "active" / "tools" / "invoke_local_proteus_gate.ps1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_manifest(root: Path) -> dict[str, Any]:
    path = root / "corpus_manifest.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing corpus manifest: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    circuits = payload.get("circuits")
    if not isinstance(circuits, list) or len(circuits) != 200:
        raise ValueError("The canonical corpus manifest must contain exactly 200 circuits.")
    return payload


def _parse_application_output(stdout: str) -> tuple[bool, str | None]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return False, "Executable did not return a JSON application report."
    if not isinstance(payload, dict):
        return False, "Executable report is not a JSON object."
    if not payload.get("valid"):
        return False, str(payload.get("error") or "Executable reported valid=false.")
    return True, None


def _run_one(
    *,
    executable: Path,
    corpus_root: Path,
    project_directory: Path,
    entry: Mapping[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    circuit_id = int(entry["id"])
    relative_input = str(entry["executable_input_json"])
    input_path = corpus_root / relative_input
    output_path = project_directory / f"circuit_{circuit_id:03d}.pdsprj"
    command = [
        str(executable),
        "generate",
        str(input_path),
        "--no-terminals",
        "--output",
        str(output_path),
    ]
    started = time.monotonic()
    try:
        process = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "id": circuit_id,
            "name": entry["name"],
            "valid": False,
            "error": f"Timed out after {timeout_seconds} seconds.",
            "duration_seconds": round(time.monotonic() - started, 3),
            "input": relative_input,
        }
    valid, report_error = _parse_application_output(process.stdout)
    if process.returncode != 0:
        valid = False
        report_error = report_error or f"Executable exited with code {process.returncode}."
    if valid and not output_path.is_file():
        valid = False
        report_error = "Executable reported success but did not create the output project."
    result: dict[str, Any] = {
        "id": circuit_id,
        "name": entry["name"],
        "valid": valid,
        "input": relative_input,
        "output": str(output_path.relative_to(project_directory.parent)),
        "component_count": int(entry["component_count"]),
        "pin_count": int(entry["pin_count"]),
        "net_count": int(entry["net_count"]),
        "complexity_score": int(entry["complexity_score"]),
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    if valid:
        result["output_sha256"] = _sha256(output_path)
    else:
        result["error"] = report_error or "Unknown executable failure."
        result["stdout"] = process.stdout[-4_000:]
        result["stderr"] = process.stderr[-4_000:]
    return result


def _cold_open_candidates(results: list[Mapping[str, Any]], *, count: int = 10) -> list[dict[str, Any]]:
    successful = [dict(result) for result in results if result.get("valid")]
    return sorted(
        successful,
        key=lambda item: (-int(item["complexity_score"]), int(item["id"])),
    )[:count]


def _load_execution_report(output_root: Path) -> dict[str, Any]:
    path = output_root / "execution_report.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing execution report: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("total", 0)) != 200:
        raise ValueError("The execution report must contain all 200 circuit results.")
    if int(payload.get("failed", -1)) != 0:
        raise ValueError("Cold-open gating requires a fully passing 200-circuit executable run.")
    return payload


def _parse_gate_output(stdout: str) -> tuple[bool, dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return False, None, "Local Proteus gate did not return JSON."
    if not isinstance(payload, dict):
        return False, None, "Local Proteus gate returned a non-object JSON value."
    if not payload.get("passed"):
        return False, payload, "Local Proteus gate reported passed=false."
    return True, payload, None


def run_cold_open_candidates(
    *,
    output_root: Path,
    wait_seconds: int,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Cold-open the ten most complex successfully generated projects.

    This uses the repository's existing disposable-copy local Proteus gate.
    It runs strictly sequentially because Proteus may only have one PDS/ISIS
    process while the gate verifies a candidate.
    """

    if not LOCAL_GATE_SCRIPT.is_file():
        raise FileNotFoundError(f"Missing local gate script: {LOCAL_GATE_SCRIPT}")
    execution = _load_execution_report(output_root)
    candidates_path = output_root / "cold_open_candidates.json"
    if not candidates_path.is_file():
        raise FileNotFoundError(f"Missing cold-open candidate selection: {candidates_path}")
    candidates_payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    candidates = list(candidates_payload.get("candidates", []))
    if len(candidates) != 10:
        raise ValueError("Cold-open candidate selection must contain exactly ten circuits.")
    gate_root = output_root / "cold_open_gate_copies"
    gate_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for candidate in candidates:
        circuit_id = int(candidate["id"])
        source_project = output_root / str(candidate["output"])
        gate_copy = gate_root / f"circuit_{circuit_id:03d}_gate_copy.pdsprj"
        command = [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(LOCAL_GATE_SCRIPT),
            "-Project",
            str(source_project),
            "-GateCopy",
            str(gate_copy),
            "-WaitSeconds",
            str(wait_seconds),
        ]
        started = time.monotonic()
        try:
            process = subprocess.run(
                command,
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            results.append(
                {
                    "id": circuit_id,
                    "name": candidate["name"],
                    "valid": False,
                    "error": f"Gate timed out after {timeout_seconds} seconds.",
                    "duration_seconds": round(time.monotonic() - started, 3),
                }
            )
            continue
        valid, gate, error = _parse_gate_output(process.stdout)
        if process.returncode != 0:
            valid = False
            error = error or f"Gate exited with code {process.returncode}."
        result: dict[str, Any] = {
            "id": circuit_id,
            "name": candidate["name"],
            "source_project": str(source_project.relative_to(output_root)),
            "gate_copy": str(gate_copy.relative_to(output_root)),
            "valid": valid,
            "duration_seconds": round(time.monotonic() - started, 3),
        }
        if gate is not None:
            result["gate"] = gate
        if not valid:
            result["error"] = error or "Unknown local Proteus gate failure."
            result["stdout"] = process.stdout[-4_000:]
            result["stderr"] = process.stderr[-4_000:]
        results.append(result)
    report = {
        "schema_version": "progen-proteus-pdf-corpus-cold-open/v1",
        "selection_policy": candidates_payload.get("selection_policy"),
        "wait_seconds": wait_seconds,
        "total": len(results),
        "passed": sum(1 for result in results if result["valid"]),
        "failed": sum(1 for result in results if not result["valid"]),
        "results": results,
    }
    _write_json(output_root / "cold_open_results.json", report)
    return report


def verify_execution_artifacts(*, output_root: Path, require_cold_open: bool) -> dict[str, Any]:
    """Independently recheck all generated containers and recorded gate results."""

    execution = _load_execution_report(output_root)
    errors: list[str] = []
    results = list(execution.get("results", []))
    ids = [int(result.get("id", -1)) for result in results]
    if ids != list(range(1, 201)):
        errors.append("Execution report results are not the complete ordered circuit range 1..200.")
    required_members = {"PROJECT.XML", "ROOT.DSN", "ROOT.CDB", "SCRIPTS/PWRRAILS.DAT"}
    checked_projects = 0
    for result in results:
        circuit_id = int(result.get("id", -1))
        if not result.get("valid"):
            errors.append(f"Circuit {circuit_id}: execution report is invalid.")
            continue
        project = output_root / str(result.get("output", ""))
        if not project.is_file():
            errors.append(f"Circuit {circuit_id}: missing generated project {project}.")
            continue
        expected_hash = str(result.get("output_sha256", "")).lower()
        if _sha256(project) != expected_hash:
            errors.append(f"Circuit {circuit_id}: generated project SHA-256 changed.")
        try:
            with ZipFile(project) as archive:
                members = set(archive.namelist())
        except (BadZipFile, OSError) as exc:
            errors.append(f"Circuit {circuit_id}: invalid .pdsprj container ({exc}).")
            continue
        missing = sorted(required_members - members)
        if missing:
            errors.append(f"Circuit {circuit_id}: missing project members {missing}.")
        checked_projects += 1

    cold_summary: dict[str, Any] | None = None
    if require_cold_open:
        cold_path = output_root / "cold_open_results.json"
        if not cold_path.is_file():
            errors.append("Missing cold_open_results.json.")
        else:
            cold_summary = json.loads(cold_path.read_text(encoding="utf-8"))
            cold_results = list(cold_summary.get("results", []))
            if int(cold_summary.get("total", 0)) != 10 or len(cold_results) != 10:
                errors.append("Cold-open report does not contain exactly ten candidates.")
            for result in cold_results:
                circuit_id = int(result.get("id", -1))
                gate = result.get("gate") if isinstance(result.get("gate"), dict) else {}
                if not result.get("valid") or not gate.get("passed"):
                    errors.append(f"Circuit {circuit_id}: cold-open gate did not pass.")
                    continue
                if not gate.get("gate_copy_hash_unchanged"):
                    errors.append(f"Circuit {circuit_id}: gate copy hash changed.")
                for phase in ("first", "second"):
                    phase_result = gate.get(phase) if isinstance(gate.get(phase), dict) else {}
                    if not phase_result.get("schematic_title_seen"):
                        errors.append(f"Circuit {circuit_id}: {phase} did not show a schematic title.")
                    if phase_result.get("error_dialog_text_seen"):
                        errors.append(f"Circuit {circuit_id}: {phase} showed a loader-error dialog.")
    report = {
        "schema_version": "progen-proteus-pdf-corpus-artifact-verification/v1",
        "valid": not errors,
        "projects_checked": checked_projects,
        "cold_open_required": require_cold_open,
        "cold_open_checked": 0 if cold_summary is None else len(cold_summary.get("results", [])),
        "errors": errors,
    }
    _write_json(output_root / "artifact_verification.json", report)
    return report


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--executable", type=Path, default=DEFAULT_EXECUTABLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--cold-open",
        action="store_true",
        help="Gate the ten highest-complexity successful outputs from an existing full run.",
    )
    parser.add_argument(
        "--gate-wait-seconds",
        type=int,
        default=20,
        help="Per-open Proteus stability wait used by --cold-open.",
    )
    parser.add_argument(
        "--gate-timeout-seconds",
        type=int,
        default=180,
        help="Maximum wall time per candidate during --cold-open.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Recheck all generated .pdsprj containers and cold-open evidence without regenerating.",
    )
    parser.add_argument(
        "--require-cold-open",
        action="store_true",
        help="With --check, require and validate the ten saved cold-open gate records.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive.")
    if args.check:
        report = verify_execution_artifacts(
            output_root=args.output,
            require_cold_open=args.require_cold_open,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["valid"] else 2
    if args.cold_open:
        report = run_cold_open_candidates(
            output_root=args.output,
            wait_seconds=args.gate_wait_seconds,
            timeout_seconds=args.gate_timeout_seconds,
        )
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0 if report["failed"] == 0 else 2
    if not args.executable.is_file():
        raise SystemExit(f"Missing portable executable: {args.executable}")
    manifest = _load_manifest(args.corpus)
    entries = [dict(entry) for entry in manifest["circuits"]]
    project_directory = args.output / "generated_projects"
    project_directory.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = {
            executor.submit(
                _run_one,
                executable=args.executable,
                corpus_root=args.corpus,
                project_directory=project_directory,
                entry=entry,
                timeout_seconds=args.timeout_seconds,
            ): int(entry["id"])
            for entry in entries
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: int(item["id"]))
    candidates = _cold_open_candidates(results)
    report = {
        "schema_version": "progen-proteus-pdf-corpus-execution/v1",
        "mode": "placement_only_no_terminals",
        "source_corpus_manifest": str((args.corpus / "corpus_manifest.json").resolve()),
        "source_pdf": manifest["source_pdf"],
        "executable": {
            "path": str(args.executable.resolve()),
            "sha256": _sha256(args.executable),
        },
        "jobs": args.jobs,
        "total": len(results),
        "passed": sum(1 for result in results if result["valid"]),
        "failed": sum(1 for result in results if not result["valid"]),
        "duration_seconds": round(time.monotonic() - started, 3),
        "results": results,
    }
    _write_json(args.output / "execution_report.json", report)
    _write_json(
        args.output / "cold_open_candidates.json",
        {
            "selection_policy": "successful outputs ranked by pin count, then component count, then net count",
            "candidates": candidates,
        },
    )
    print(
        json.dumps(
            {
                "valid": report["failed"] == 0,
                "total": report["total"],
                "passed": report["passed"],
                "failed": report["failed"],
                "cold_open_candidates": [
                    {"id": item["id"], "name": item["name"]} for item in candidates
                ],
                "report": str(args.output / "execution_report.json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["failed"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
