"""Aggregate explicit LTspice stage reports into one user-safe decision."""

from __future__ import annotations

from typing import Any


FINAL_VALIDATOR_SCHEMA = "progen-ltspice-final-validator/v0.1"


def build_final_validation(
    *,
    input_report: dict[str, Any],
    selection_report: dict[str, Any],
    placement_report: dict[str, Any],
    native_report: dict[str, Any],
    simulation_report: dict[str, Any],
) -> dict[str, Any]:
    reports = {
        "input": input_report,
        "component_selection": selection_report,
        "placement": placement_report,
        "native_connectivity": native_report,
        "simulation": simulation_report,
    }
    errors: list[str] = []
    warnings: list[str] = []
    required = ("input", "component_selection", "placement", "native_connectivity")
    for name, report in reports.items():
        if isinstance(report.get("warnings"), list):
            warnings.extend(str(item) for item in report["warnings"])
        if name in required and not report.get("ok", False):
            errors.extend(f"{name}: {item}" for item in report.get("errors", ["stage did not pass"]))
    if simulation_report.get("status") in {"failed", "timeout"}:
        errors.extend(f"simulation: {item}" for item in simulation_report.get("errors", [simulation_report.get("status")]))
    return {
        "schema": FINAL_VALIDATOR_SCHEMA,
        "stage": "ltspice_final_validator",
        "ok": not errors,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "warnings": sorted(set(warnings)),
        "stage_status": {name: report.get("status", "pass" if report.get("ok") else "fail") for name, report in reports.items()},
        "simulation_is_additional_evidence": True,
    }
