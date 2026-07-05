"""Final Validator stage for generated KiCad projects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


FINAL_VALIDATOR_SCHEMA = "progen-kicad-final-validator/v0.1"


def _json_load(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "missing_file": str(path)}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {"ok": False, "wrong_json_type": str(type(data).__name__)}


def _manifest_report(project_dir: Path, manifest: dict[str, Any], section: str, default_name: str) -> dict[str, Any]:
    raw = manifest.get(section, {})
    report_name = raw.get("report") if isinstance(raw, dict) else None
    path = project_dir / str(report_name or default_name)
    return _json_load(path)


def _check_ok(report: dict[str, Any], *path: str, default: bool = False) -> bool:
    current: Any = report
    for key in path:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return bool(current)


def _required_files(project_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    required = []
    for key in ("open_this", "schematic_file"):
        value = manifest.get(key)
        if value:
            required.append(str(value))
    missing = [name for name in required if not (project_dir / name).exists()]
    static_checks = manifest.get("static_checks", {}) if isinstance(manifest.get("static_checks"), dict) else {}
    return {
        "ok": not missing and bool(static_checks.get("ok")),
        "required_files": required,
        "missing_files": missing,
        "static_checks_ok": bool(static_checks.get("ok")),
        "static_check_errors": static_checks.get("errors", []),
    }


def validate_final_project(
    *,
    circuit: dict[str, Any],
    project_dir: Path | str,
    manifest: dict[str, Any] | None = None,
    output_report: Path | str | None = None,
) -> dict[str, Any]:
    project_path = Path(project_dir)
    if manifest is None:
        manifest = _json_load(project_path / "manifest.json")

    local_netlist = _manifest_report(project_path, manifest, "local_netlist_validation", "local_netlist_validation_report.json")
    value_report = _manifest_report(project_path, manifest, "value_validator", "value_validation_report.json")
    body_report = _manifest_report(project_path, manifest, "component_body_overlap_report", "component_body_overlap_report.json")
    wire_report = manifest.get("wire_maker", {}) if isinstance(manifest.get("wire_maker"), dict) else {}

    routing_mode = str(wire_report.get("routing_mode") or circuit.get("routing", {}).get("mode") or "wire")
    expected_net_check = local_netlist.get("checks", {}).get("expected_net_comparison", {})
    pin_check = local_netlist.get("checks", {}).get("pin_existence", {})
    component_value_check = local_netlist.get("checks", {}).get("component_count_reference_value", {})
    erc_report = local_netlist.get("erc", {}) if isinstance(local_netlist.get("erc"), dict) else {}

    checks = {
        "file_validity": _required_files(project_path, manifest),
        "component_count_reference_value": {
            "ok": bool(component_value_check.get("ok")) and bool(value_report.get("ok")),
            "local_netlist_check": component_value_check,
            "value_validator": {
                "ok": bool(value_report.get("ok")),
                "missing_ref_count": int(value_report.get("missing_ref_count", 0)),
                "value_mismatch_count": int(value_report.get("value_mismatch_count", 0)),
                "duplicate_actual_value_count": int(value_report.get("duplicate_actual_value_count", 0)),
            },
        },
        "pin_existence": {
            "ok": bool(pin_check.get("ok")),
            "missing_pin_count": int(pin_check.get("missing_pin_count", 0)),
            "resolved_expected_endpoint_count": int(pin_check.get("resolved_expected_endpoint_count", 0)),
        },
        "netlist_export": {
            "ok": bool(local_netlist.get("schema")),
            "kicad_cli_required": bool(local_netlist.get("kicad_cli_required", True)),
            "comparison_basis": local_netlist.get("comparison_basis"),
        },
        "expected_net_comparison": {
            "ok": bool(expected_net_check.get("ok")),
            "failed_net_count": int(expected_net_check.get("failed_net_count", 0)),
            "merged_net_count": int(expected_net_check.get("merged_net_count", 0)),
            "power_ground_short_count": int(expected_net_check.get("power_ground_short_count", 0)),
            "floating_expected_pin_count": int(expected_net_check.get("floating_expected_pin_count", 0)),
        },
        "erc": {
            "ok": True if erc_report.get("skipped", True) else bool(erc_report.get("ok")),
            "available": bool(erc_report.get("available")),
            "skipped": bool(erc_report.get("skipped", True)),
            "violation_count": int(erc_report.get("violation_count", 0)),
        },
        "wire_geometry": {
            "ok": bool(wire_report.get("geometry_ok", True)),
            "violation_count": int(wire_report.get("geometry_violation_count", 0)),
        },
        "component_body_overlap": {
            "ok": bool(body_report.get("ok")),
            "overlap_count": int(body_report.get("component_body_overlap_count", body_report.get("overlap_count", 0))),
        },
        "routing_contract": {
            "ok": routing_mode != "wire" or bool(wire_report.get("strict_wire_ok")),
            "routing_mode": routing_mode,
            "strict_wire_ok": bool(wire_report.get("strict_wire_ok", routing_mode != "wire")),
            "strict_wire_violation_count": int(wire_report.get("strict_wire_violation_count", 0)),
            "unrouted_net_count": int(wire_report.get("unrouted_net_count", 0)),
            "partial_wire_net_count": int(wire_report.get("partial_wire_net_count", 0)),
        },
    }
    blocking_failures = [
        {"check": name, "detail": detail}
        for name, detail in checks.items()
        if isinstance(detail, dict) and not detail.get("ok")
    ]
    report = {
        "schema": FINAL_VALIDATOR_SCHEMA,
        "stage": "final_validator",
        "ok": not blocking_failures,
        "ready_for_output": not blocking_failures,
        "project_dir": str(project_path),
        "routing_mode": routing_mode,
        "kicad_cli_required": False,
        "checks": checks,
        "blocking_failure_count": len(blocking_failures),
        "blocking_failures": blocking_failures,
    }
    if output_report is not None:
        Path(output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run final validation over a generated KiCad project folder.")
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("circuit_json", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    circuit = json.loads(args.circuit_json.read_text(encoding="utf-8"))
    manifest = _json_load(args.manifest) if args.manifest else None
    report = validate_final_project(circuit=circuit, project_dir=args.project_dir, manifest=manifest, output_report=args.output)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
