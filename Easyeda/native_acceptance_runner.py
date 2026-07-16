"""Open qualified EasyEDA projects through the native desktop application."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import signal
import time
from typing import Any

from .gui_acceptance import open_project


RUN_SCHEMA = "progen-easyeda-native-acceptance/v1"
EASYEDA_EXECUTABLE = "/home/zaruka/.local/opt/easyeda-pro/easyeda-pro"


def _json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _easyeda_pids() -> list[int]:
    pids: list[int] = []
    for command_line in Path("/proc").glob("[0-9]*/cmdline"):
        try:
            arguments = command_line.read_bytes().split(b"\0")
        except OSError:
            continue
        if arguments and arguments[0].decode("utf-8", errors="ignore") == EASYEDA_EXECUTABLE:
            pids.append(int(command_line.parent.name))
    return pids


def _stop_easyeda() -> None:
    pids = _easyeda_pids()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 3.0
    while _easyeda_pids() and time.monotonic() < deadline:
        time.sleep(0.1)
    for pid in _easyeda_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    time.sleep(0.5)


def run_native_acceptance(
    qualification_report: Path,
    output_root: Path,
    *,
    variant: int | None,
    wait_seconds: float,
    settle_seconds: float,
    retries: int,
    limit: int | None,
    most_complex: bool,
) -> dict[str, Any]:
    source = json.loads(
        qualification_report.expanduser().resolve().read_text(encoding="utf-8")
    )
    records = [
        record
        for record in source.get("records", [])
        if record.get("passed")
        and (
            variant is None
            or str(record.get("name") or "").endswith(f"_v{variant:02d}")
        )
    ]
    if most_complex:
        records.sort(
            key=lambda record: (
                int(record.get("net_count") or 0),
                int(record.get("component_count") or 0),
                str(record.get("name") or ""),
            ),
            reverse=True,
        )
    if limit is not None:
        records = records[:limit]
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S_%f")
    run_root = (
        output_root.expanduser().resolve()
        / f"{timestamp}_native_acceptance"
    )
    run_root.mkdir(parents=True, exist_ok=False)
    results: list[dict[str, Any]] = []
    started = time.monotonic()
    try:
        for index, record in enumerate(records, start=1):
            attempts: list[dict[str, Any]] = []
            opened: dict[str, Any] = {}
            for attempt in range(1, retries + 2):
                _stop_easyeda()
                opened = open_project(
                    Path(record["project_path"]),
                    wait_seconds=wait_seconds,
                    disposable_copy=True,
                )
                attempts.append(
                    {
                        "attempt": attempt,
                        "opened": opened["opened"],
                        "process_running": opened["process_running"],
                        "native_conversion_completed": opened[
                            "native_conversion_completed"
                        ],
                        "disposable_directory": opened[
                            "disposable_directory"
                        ],
                    }
                )
                if opened["opened"]:
                    time.sleep(settle_seconds)
                    break
                time.sleep(1.0)
            results.append(
                {
                    "name": record["name"],
                    "project_path": record["project_path"],
                    "opened": opened["opened"],
                    "original_unchanged": opened["original_unchanged"],
                    "native_conversion_completed": opened[
                        "native_conversion_completed"
                    ],
                    "disposable_directory": opened["disposable_directory"],
                    "converted_projects": opened["converted_projects"],
                    "attempts": attempts,
                }
            )
            _json(run_root / "results_in_progress.json", results)
    finally:
        _stop_easyeda()
    passed = [item for item in results if item["opened"]]
    report = {
        "schema": RUN_SCHEMA,
        "qualification_report": str(qualification_report.expanduser().resolve()),
        "variant": variant,
        "most_complex": most_complex,
        "settle_seconds": settle_seconds,
        "input_count": len(records),
        "passed_count": len(passed),
        "failed_count": len(results) - len(passed),
        "elapsed_seconds": round(time.monotonic() - started, 4),
        "records": results,
    }
    _json(run_root / "native_acceptance_report.json", report)
    (run_root / "results_in_progress.json").unlink(missing_ok=True)
    return {"run_root": str(run_root), **report}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("qualification_report", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--variant", type=int, choices=range(1, 11), default=1)
    parser.add_argument("--wait-seconds", type=float, default=45.0)
    parser.add_argument("--settle-seconds", type=float, default=12.0)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--most-complex", action="store_true")
    args = parser.parse_args()
    report = run_native_acceptance(
        args.qualification_report,
        args.output_root,
        variant=args.variant,
        wait_seconds=args.wait_seconds,
        settle_seconds=max(0.0, args.settle_seconds),
        retries=max(0, args.retries),
        limit=args.limit,
        most_complex=args.most_complex,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["failed_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
