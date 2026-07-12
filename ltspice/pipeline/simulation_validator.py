"""Optional external LTspice oracle stage.

Static native parsing is mandatory and self-contained. This module only runs an
explicitly supplied external LTspice command; it never treats a simulation as a
substitute for net-membership validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
import time
import re
from typing import Any, Sequence


SIMULATION_SCHEMA = "progen-ltspice-simulation-validator/v0.1"


@dataclass(frozen=True)
class OracleCommand:
    command: tuple[str, ...]
    timeout_seconds: int = 90
    path_style: str = "native"


def _oracle_path(asc_path: Path, style: str) -> str:
    if style == "native":
        return str(asc_path)
    if style == "wine_z":
        return "Z:" + asc_path.resolve().as_posix().replace("/", "\\")
    raise ValueError(f"Unsupported oracle path style {style!r}; expected native or wine_z.")


def simulation_not_requested() -> dict[str, Any]:
    return {
        "schema": SIMULATION_SCHEMA,
        "stage": "optional_ltspice_simulation",
        "status": "not_run",
        "ok": True,
        "reason": "No external LTspice oracle command was supplied. Static ASC/ASY connectivity validation remains mandatory and completed separately.",
    }


def run_external_oracle(asc_path: Path, *, oracle: OracleCommand) -> dict[str, Any]:
    """Run LTspice netlisting, then batch simulation when an analysis exists."""

    if not oracle.command:
        return simulation_not_requested()
    start = time.monotonic()
    oracle_path = _oracle_path(asc_path, oracle.path_style)
    command = [*oracle.command, "-netlist", oracle_path]
    try:
        completed = subprocess.run(
            command,
            cwd=asc_path.parent,
            text=True,
            capture_output=True,
            timeout=oracle.timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        return {
            "schema": SIMULATION_SCHEMA,
            "stage": "optional_ltspice_simulation",
            "status": "unavailable",
            "ok": True,
            "reason": f"External LTspice command is unavailable: {exc}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "schema": SIMULATION_SCHEMA,
            "stage": "optional_ltspice_simulation",
            "status": "timeout",
            "ok": False,
            "command": command,
            "timeout_seconds": oracle.timeout_seconds,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    netlist_candidates = [asc_path.with_suffix(".net"), asc_path.with_suffix(".cir")]
    netlist = next((path for path in netlist_candidates if path.is_file()), None)
    source_text = asc_path.read_text(encoding="ascii", errors="replace")
    analysis_requested = bool(re.search(r"!\.(?:ac|dc|four|fra|noise|op|tf|tran)\b", source_text, flags=re.IGNORECASE))
    batch: dict[str, Any] | None = None
    if completed.returncode == 0 and netlist and analysis_requested:
        batch_command = [*oracle.command, "-b", oracle_path]
        try:
            batch_completed = subprocess.run(
                batch_command,
                cwd=asc_path.parent,
                text=True,
                capture_output=True,
                timeout=oracle.timeout_seconds,
                check=False,
            )
            log_path = asc_path.with_suffix(".log")
            raw_path = asc_path.with_suffix(".raw")
            log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
            log_error = bool(
                re.search(
                    r"(?:syntax error|fatal error|error:|could not|unknown parameter|ignoring unknown model parameter)",
                    log_text,
                    flags=re.IGNORECASE,
                )
            )
            batch = {
                "command": batch_command,
                "returncode": batch_completed.returncode,
                "stdout": batch_completed.stdout,
                "stderr": batch_completed.stderr,
                "log_path": str(log_path) if log_path.is_file() else None,
                "log_text": log_text,
                "raw_path": str(raw_path) if raw_path.is_file() else None,
                "raw_size_bytes": raw_path.stat().st_size if raw_path.is_file() else 0,
                "ok": batch_completed.returncode == 0 and bool(log_text) and not log_error,
            }
        except subprocess.TimeoutExpired as exc:
            batch = {
                "command": batch_command,
                "timeout_seconds": oracle.timeout_seconds,
                "stdout": exc.stdout or "",
                "stderr": exc.stderr or "",
                "ok": False,
                "status": "timeout",
            }
    elapsed = round(time.monotonic() - start, 3)
    netlist_ok = completed.returncode == 0 and netlist is not None
    oracle_ok = netlist_ok and (batch is None or bool(batch.get("ok")))
    return {
        "schema": SIMULATION_SCHEMA,
        "stage": "optional_ltspice_simulation",
        "status": "passed" if oracle_ok else "failed",
        "ok": oracle_ok,
        "command": command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "netlist_path": str(netlist) if netlist else None,
        "netlist_text": netlist.read_text(encoding="utf-8", errors="replace") if netlist else None,
        "analysis_requested": analysis_requested,
        "batch": batch,
    }
