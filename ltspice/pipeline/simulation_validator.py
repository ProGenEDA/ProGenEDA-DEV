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

from .component_selector import SelectedComponent
from .ltspice_wire_maker import WirePlan
from .oracle_netlist_validator import validate_oracle_netlist


SIMULATION_SCHEMA = "progen-ltspice-simulation-validator/v0.1"


@dataclass(frozen=True)
class OracleCommand:
    command: tuple[str, ...]
    timeout_seconds: float = 90
    path_style: str = "native"
    deadline_monotonic: float | None = None


def _oracle_path(asc_path: Path, style: str) -> str:
    if style == "native":
        return str(asc_path)
    if style == "wine_z":
        return "Z:" + asc_path.resolve().as_posix().replace("/", "\\")
    raise ValueError(f"Unsupported oracle path style {style!r}; expected native or wine_z.")


def _process_timeout_seconds(oracle: OracleCommand) -> float | None:
    """Bound each subprocess by its own timeout and an optional hard deadline."""

    timeout = float(oracle.timeout_seconds)
    if oracle.deadline_monotonic is None:
        return timeout
    remaining = oracle.deadline_monotonic - time.monotonic()
    if remaining <= 0:
        return None
    return min(timeout, remaining)


def _deadline_timeout_report(command: list[str], oracle: OracleCommand, *, action: str) -> dict[str, Any]:
    return {
        "schema": SIMULATION_SCHEMA,
        "stage": "optional_ltspice_simulation",
        "status": "timeout",
        "ok": False,
        "command": command,
        "timeout_seconds": 0,
        "deadline_monotonic": oracle.deadline_monotonic,
        "errors": [f"LTspice {action} did not start before the generation hard deadline."],
    }


def simulation_not_requested() -> dict[str, Any]:
    return {
        "schema": SIMULATION_SCHEMA,
        "stage": "optional_ltspice_simulation",
        "status": "not_run",
        "ok": True,
        "reason": "No external LTspice oracle command was supplied. Static ASC/ASY connectivity validation remains mandatory and completed separately.",
        "exported_netlist_validation": {
            "status": "not_run",
            "ok": True,
            "reason": "An external LTspice executable was not requested.",
        },
    }


def run_external_oracle(
    asc_path: Path,
    *,
    oracle: OracleCommand,
    selected: Sequence[SelectedComponent] | None = None,
    wire_plan: WirePlan | None = None,
) -> dict[str, Any]:
    """Run LTspice netlisting, then batch simulation when an analysis exists."""

    if not oracle.command:
        return simulation_not_requested()
    start = time.monotonic()
    oracle_path = _oracle_path(asc_path, oracle.path_style)
    command = [*oracle.command, "-netlist", oracle_path]
    netlist_timeout = _process_timeout_seconds(oracle)
    if netlist_timeout is None:
        return _deadline_timeout_report(command, oracle, action="netlist export")
    try:
        completed = subprocess.run(
            command,
            cwd=asc_path.parent,
            text=True,
            capture_output=True,
            timeout=netlist_timeout,
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
            "timeout_seconds": netlist_timeout,
            "deadline_monotonic": oracle.deadline_monotonic,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
            "errors": [f"LTspice netlist export exceeded the {netlist_timeout}-second oracle timeout."],
        }
    netlist_candidates = [asc_path.with_suffix(".net"), asc_path.with_suffix(".cir")]
    netlist = next((path for path in netlist_candidates if path.is_file()), None)
    netlist_text = netlist.read_text(encoding="utf-8", errors="replace") if netlist else None
    if netlist_text is not None and selected is not None and wire_plan is not None:
        exported_netlist_validation = validate_oracle_netlist(netlist_text, selected=selected, wire_plan=wire_plan)
    elif netlist_text is not None:
        exported_netlist_validation = {
            "status": "not_checked",
            "ok": True,
            "reason": "No selected-component and wire-plan contract was supplied for exported-netlist comparison.",
        }
    else:
        exported_netlist_validation = {
            "status": "not_run",
            "ok": False,
            "reason": "LTspice did not create a .net or .cir file.",
        }
    source_text = asc_path.read_text(encoding="ascii", errors="replace")
    analysis_requested = bool(re.search(r"!\.(?:ac|dc|four|fra|noise|op|tf|tran)\b", source_text, flags=re.IGNORECASE))
    batch: dict[str, Any] | None = None
    if completed.returncode == 0 and netlist and analysis_requested:
        batch_command = [*oracle.command, "-b", oracle_path]
        batch_timeout = _process_timeout_seconds(oracle)
        if batch_timeout is None:
            batch = {
                "command": batch_command,
                "timeout_seconds": 0,
                "deadline_monotonic": oracle.deadline_monotonic,
                "errors": ["LTspice batch simulation did not start before the generation hard deadline."],
                "ok": False,
                "status": "timeout",
            }
        else:
            try:
                batch_completed = subprocess.run(
                    batch_command,
                    cwd=asc_path.parent,
                    text=True,
                    capture_output=True,
                    timeout=batch_timeout,
                    check=False,
                )
                log_path = asc_path.with_suffix(".log")
                raw_path = asc_path.with_suffix(".raw")
                log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path.is_file() else ""
                error_markers = sorted(
                    set(
                        re.findall(
                            r"(?:syntax error|fatal error|error:|could not|unknown parameter|ignoring unknown model parameter)",
                            log_text,
                            flags=re.IGNORECASE,
                        )
                    )
                )
                batch_errors: list[str] = []
                if batch_completed.returncode != 0:
                    batch_errors.append(f"LTspice batch simulation returned code {batch_completed.returncode}.")
                if not log_text:
                    batch_errors.append("LTspice batch simulation did not produce a .log file.")
                if error_markers:
                    batch_errors.append("LTspice batch log reported: " + ", ".join(error_markers) + ".")
                batch = {
                    "command": batch_command,
                    "returncode": batch_completed.returncode,
                    "stdout": batch_completed.stdout,
                    "stderr": batch_completed.stderr,
                    "log_path": str(log_path) if log_path.is_file() else None,
                    "log_text": log_text,
                    "raw_path": str(raw_path) if raw_path.is_file() else None,
                    "raw_size_bytes": raw_path.stat().st_size if raw_path.is_file() else 0,
                    "errors": batch_errors,
                    "ok": not batch_errors,
                }
            except subprocess.TimeoutExpired as exc:
                batch = {
                    "command": batch_command,
                    "timeout_seconds": batch_timeout,
                    "deadline_monotonic": oracle.deadline_monotonic,
                    "stdout": exc.stdout or "",
                    "stderr": exc.stderr or "",
                    "errors": [f"LTspice batch simulation exceeded the {batch_timeout}-second oracle timeout."],
                    "ok": False,
                    "status": "timeout",
                }
    elapsed = round(time.monotonic() - start, 3)
    netlist_ok = completed.returncode == 0 and netlist is not None and bool(exported_netlist_validation.get("ok"))
    oracle_ok = netlist_ok and (batch is None or bool(batch.get("ok")))
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"LTspice netlist export returned code {completed.returncode}.")
    if netlist is None:
        errors.append("LTspice did not create a .net or .cir file.")
    if not exported_netlist_validation.get("ok"):
        validation_errors = exported_netlist_validation.get("errors", [])
        if isinstance(validation_errors, list) and validation_errors:
            errors.extend(str(item) for item in validation_errors)
        else:
            errors.append(str(exported_netlist_validation.get("reason") or "LTspice-exported netlist validation failed."))
    if batch is not None and isinstance(batch.get("errors"), list):
        errors.extend(str(item) for item in batch["errors"])
    return {
        "schema": SIMULATION_SCHEMA,
        "stage": "optional_ltspice_simulation",
        "status": "passed" if oracle_ok else "failed",
        "ok": oracle_ok,
        "errors": errors,
        "command": command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "netlist_path": str(netlist) if netlist else None,
        "netlist_text": netlist_text,
        "exported_netlist_validation": exported_netlist_validation,
        "analysis_requested": analysis_requested,
        "batch": batch,
    }
