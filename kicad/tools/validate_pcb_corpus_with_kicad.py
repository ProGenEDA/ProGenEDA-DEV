#!/usr/bin/env python3
"""Run installed KiCad DRC over every accepted PCB in an immutable corpus run."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ORACLE_SCHEMA = "progen-kicad-pcb-cli-oracle-run/v0.1"


def _accepted_boards(run_dir: Path) -> list[tuple[str, Path]]:
    projects = run_dir / "generation" / "projects"
    accepted: list[tuple[str, Path]] = []
    for report_path in sorted(projects.glob("*/pcb_pipeline_report.json")):
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("reason") != "accepted":
            continue
        board_name = report.get("pcb_file")
        if not board_name:
            raise ValueError(f"Accepted PCB report has no pcb_file: {report_path}")
        board = report_path.parent / str(board_name)
        if not board.is_file():
            raise FileNotFoundError(f"Accepted PCB is missing: {board}")
        accepted.append((report_path.parent.name, board))
    return accepted


def _validate_one(
    circuit_id: str,
    board: Path,
    *,
    output_dir: Path,
    kicad_cli: Path,
    environment: dict[str, str],
) -> dict[str, Any]:
    report_dir = output_dir / "reports"
    report_path = report_dir / f"{circuit_id}.drc.json"
    started = time.perf_counter()
    process = subprocess.run(
        [
            str(kicad_cli),
            "pcb",
            "drc",
            "--format",
            "json",
            "--exit-code-violations",
            "--output",
            str(report_path),
            str(board),
        ],
        cwd=board.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    elapsed = time.perf_counter() - started
    report: dict[str, Any] = {}
    parse_error = ""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parse_error = str(exc)
    violations = report.get("violations", []) if isinstance(report, dict) else []
    unconnected = report.get("unconnected_items", []) if isinstance(report, dict) else []
    return {
        "circuit_id": circuit_id,
        "board": str(board),
        "report": str(report_path.relative_to(output_dir)),
        "return_code": process.returncode,
        "violation_count": len(violations) if isinstance(violations, list) else -1,
        "unconnected_count": len(unconnected) if isinstance(unconnected, list) else -1,
        "parse_error": parse_error,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "elapsed_seconds": round(elapsed, 4),
        "ok": process.returncode == 0 and not parse_error and not violations and not unconnected,
    }


def _load_existing_result(circuit_id: str, board: Path, report_path: Path, output_dir: Path) -> dict[str, Any] | None:
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    violations = report.get("violations", [])
    unconnected = report.get("unconnected_items", [])
    if not isinstance(violations, list) or not isinstance(unconnected, list):
        return None
    return {
        "circuit_id": circuit_id,
        "board": str(board),
        "report": str(report_path.relative_to(output_dir)),
        "return_code": 0 if not violations and not unconnected else 5,
        "violation_count": len(violations),
        "unconnected_count": len(unconnected),
        "parse_error": "",
        "stdout": "",
        "stderr": "",
        "elapsed_seconds": 0.0,
        "resumed_existing_report": True,
        "ok": not violations and not unconnected,
    }


def validate_corpus(
    run_dir: Path,
    *,
    output_dir: Path,
    kicad_cli: Path,
    appdir: Path,
    jobs: int,
    resume: bool = False,
) -> dict[str, Any]:
    if output_dir.exists() and not resume:
        raise FileExistsError(f"Oracle output already exists: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=resume)
    (output_dir / "reports").mkdir(exist_ok=resume)
    boards = _accepted_boards(run_dir)
    environment = dict(os.environ)
    environment.update(
        {
            "SHARUN_DIR": str(appdir),
            "APPDIR": str(appdir),
            "KICAD_STOCK_DATA_HOME": str(appdir / "share" / "kicad"),
        }
    )
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    pending: list[tuple[str, Path]] = []
    for circuit_id, board in boards:
        existing = _load_existing_result(
            circuit_id,
            board,
            output_dir / "reports" / f"{circuit_id}.drc.json",
            output_dir,
        ) if resume else None
        if existing is None:
            pending.append((circuit_id, board))
        else:
            results.append(existing)
    with ThreadPoolExecutor(max_workers=max(1, jobs)) as executor:
        futures = {
            executor.submit(
                _validate_one,
                circuit_id,
                board,
                output_dir=output_dir,
                kicad_cli=kicad_cli,
                environment=environment,
            ): circuit_id
            for circuit_id, board in pending
        }
        for future in as_completed(futures):
            results.append(future.result())
    results.sort(key=lambda item: str(item["circuit_id"]))
    summary = {
        "schema": ORACLE_SCHEMA,
        "source_run": str(run_dir),
        "kicad_cli": str(kicad_cli),
        "appdir": str(appdir),
        "jobs": max(1, jobs),
        "resumed": resume,
        "resumed_report_count": len(boards) - len(pending),
        "accepted_board_count": len(boards),
        "checked_board_count": len(results),
        "passed_board_count": sum(1 for result in results if result["ok"]),
        "failed_board_count": sum(1 for result in results if not result["ok"]),
        "total_violation_count": sum(max(0, int(result["violation_count"])) for result in results),
        "total_unconnected_count": sum(max(0, int(result["unconnected_count"])) for result in results),
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "all_passed": bool(results) and all(result["ok"] for result in results),
        "results": results,
    }
    (output_dir / "oracle_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# KiCad PCB CLI Oracle Run\n\n"
        "This immutable evidence folder runs installed KiCad DRC against every PCB that the hosted "
        "source-backed validator accepted. KiCad CLI is an external release oracle and is not a hosted "
        "generator dependency. See `oracle_summary.json` and `reports/`.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--kicad-cli", type=Path, default=Path("kicad/.local/AppDir/bin/kicad-cli"))
    parser.add_argument("--appdir", type=Path, default=Path("kicad/.local/AppDir"))
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    summary = validate_corpus(
        args.run_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        kicad_cli=args.kicad_cli.resolve(),
        appdir=args.appdir.resolve(),
        jobs=args.jobs,
        resume=args.resume,
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "results"}, indent=2))


if __name__ == "__main__":
    main()
