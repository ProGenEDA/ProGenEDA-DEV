"""Run canonical EasyEDA qualification JSONs through the untouched executable."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


RUN_SCHEMA = "progen-easyeda-qualification-run/v1"


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _command(executable: Path | None, input_path: Path, output_root: Path) -> list[str]:
    prefix = (
        [str(executable.expanduser().resolve())]
        if executable is not None
        else [sys.executable, "-m", "Easyeda.executable"]
    )
    return [
        *prefix,
        "run",
        str(input_path),
        "--output-root",
        str(output_root),
    ]


def _run_one(
    input_path: Path,
    *,
    executable: Path | None,
    output_root: Path,
    timeout: float,
) -> dict[str, Any]:
    started = time.monotonic()
    command = _command(executable, input_path, output_root)
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "input": str(input_path),
            "passed": False,
            "timed_out": True,
            "elapsed_seconds": round(time.monotonic() - started, 4),
            "error": f"generation exceeded {timeout} seconds",
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    elapsed = round(time.monotonic() - started, 4)
    if process.returncode != 0:
        return {
            "input": str(input_path),
            "passed": False,
            "timed_out": False,
            "elapsed_seconds": elapsed,
            "returncode": process.returncode,
            "error": process.stderr.strip() or process.stdout.strip(),
        }
    try:
        result = json.loads(process.stdout)
        validation = json.loads(
            Path(result["validation_report"]).read_text(encoding="utf-8")
        )
        pcb = json.loads(Path(result["pcb_report"]).read_text(encoding="utf-8"))
        fixer = json.loads(
            (Path(result["run_directory"]) / "input_fixer.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        return {
            "input": str(input_path),
            "passed": False,
            "timed_out": False,
            "elapsed_seconds": elapsed,
            "returncode": process.returncode,
            "error": f"cannot audit executable output: {exc}",
            "stdout": process.stdout,
        }
    pin_coverage = validation.get("checks", {}).get("pin_coverage", {})
    complete_pins = bool(pin_coverage) and all(
        item.get("complete") for item in pin_coverage.values()
    )
    expected_members = validation.get("checks", {}).get("expected_net_members", {})
    actual_members = validation.get("checks", {}).get("actual_net_members", {})
    netlist_match = expected_members == actual_members
    return {
        "input": str(input_path),
        "name": input_path.stem,
        "passed": bool(result.get("passed"))
        and bool(validation.get("passed"))
        and complete_pins
        and netlist_match,
        "timed_out": False,
        "elapsed_seconds": elapsed,
        "returncode": process.returncode,
        "component_count": result.get("component_count"),
        "net_count": result.get("net_count"),
        "guessed_net_count": fixer.get("guessed_net_count"),
        "input_change_count": fixer.get("change_count"),
        "complete_pin_coverage": complete_pins,
        "netlist_match": netlist_match,
        "pcb_ready": pcb.get("ready"),
        "pcb_reason": pcb.get("reason"),
        "pcb_variations": pcb.get("variations", []),
        "project_path": result.get("project_path"),
        "run_directory": result.get("run_directory"),
        "validation_errors": validation.get("errors", []),
    }


def run_corpus(
    corpus: Path,
    output_root: Path,
    *,
    executable: Path | None,
    workers: int,
    timeout: float,
    variant: int | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    corpus = corpus.expanduser().resolve()
    inputs = sorted(
        path
        for path in corpus.glob("*.json")
        if path.name != "manifest.json"
        and (
            variant is None
            or path.stem.endswith(f"_v{variant:02d}")
        )
    )
    if limit is not None:
        inputs = inputs[:limit]
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S_%f")
    run_root = output_root.expanduser().resolve() / f"{timestamp}_qualification"
    generated_root = run_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=False)
    records: list[dict[str, Any]] = []
    started = time.monotonic()
    with ThreadPoolExecutor(
        max_workers=max(1, workers),
        thread_name_prefix="easyeda-qualification",
    ) as executor:
        futures = {
            executor.submit(
                _run_one,
                path,
                executable=executable,
                output_root=generated_root,
                timeout=timeout,
            ): path
            for path in inputs
        }
        for future in as_completed(futures):
            records.append(future.result())
            records.sort(key=lambda item: item.get("name") or item["input"])
            _json(run_root / "results_in_progress.json", records)
    elapsed = round(time.monotonic() - started, 4)
    passed = [record for record in records if record["passed"]]
    pcb_ready = [record for record in records if record.get("pcb_ready")]
    report = {
        "schema": RUN_SCHEMA,
        "corpus": str(corpus),
        "executable": str(executable.expanduser().resolve()) if executable else "python-module",
        "workers": workers,
        "timeout_seconds": timeout,
        "input_count": len(inputs),
        "passed_count": len(passed),
        "failed_count": len(records) - len(passed),
        "pcb_ready_count": len(pcb_ready),
        "pcb_withheld_count": len(records) - len(pcb_ready),
        "elapsed_seconds": elapsed,
        "average_seconds": round(
            sum(record["elapsed_seconds"] for record in records) / len(records),
            4,
        ) if records else 0.0,
        "max_seconds": max(
            (record["elapsed_seconds"] for record in records),
            default=0.0,
        ),
        "records": records,
    }
    _json(run_root / "qualification_report.json", report)
    (run_root / "results_in_progress.json").unlink(missing_ok=True)
    return {"run_root": str(run_root), **report}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--executable", type=Path)
    parser.add_argument(
        "--workers",
        type=int,
        default=max(1, min(4, (os.cpu_count() or 2) // 2)),
    )
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--variant", type=int, choices=range(1, 11))
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    report = run_corpus(
        args.corpus,
        args.output_root,
        executable=args.executable,
        workers=args.workers,
        timeout=args.timeout,
        variant=args.variant,
        limit=args.limit,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
