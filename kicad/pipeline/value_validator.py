"""Value Validator stage for generated KiCad schematics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .kicad_netlist_validator import parse_schematic
from .value_editor import expected_component_values


VALUE_VALIDATOR_SCHEMA = "progen-kicad-value-validator/v0.1"


def validate_component_values(
    *,
    circuit: dict[str, Any],
    schematic_path: Path | str,
    output_report: Path | str | None = None,
) -> dict[str, Any]:
    path = Path(schematic_path)
    parsed = parse_schematic(path)
    expected = expected_component_values(circuit)
    actual = {
        ref: sorted({instance.value for instance in instances})
        for ref, instances in sorted(parsed.instances_by_ref.items())
    }
    missing_refs = sorted(set(expected) - set(actual))
    extra_refs = sorted(set(actual) - set(expected))
    missing_expected_values = sorted(ref for ref, value in expected.items() if value == "")
    value_mismatches: list[dict[str, Any]] = []
    duplicate_actual_values: list[dict[str, Any]] = []
    for ref, expected_value in sorted(expected.items()):
        if ref not in actual:
            continue
        actual_values = actual[ref]
        if len(actual_values) > 1:
            duplicate_actual_values.append({"ref": ref, "actual_values": actual_values})
        if actual_values != [expected_value]:
            value_mismatches.append({"ref": ref, "expected": expected_value, "actual": actual_values})

    report = {
        "schema": VALUE_VALIDATOR_SCHEMA,
        "stage": "value_validator",
        "ok": not (missing_refs or missing_expected_values or value_mismatches or duplicate_actual_values),
        "schematic": str(path),
        "kicad_cli_required": False,
        "expected_component_count": len(expected),
        "actual_component_count": len(actual),
        "missing_ref_count": len(missing_refs),
        "missing_refs": missing_refs,
        "extra_ref_count": len(extra_refs),
        "extra_refs": extra_refs[:100],
        "extra_refs_truncated": len(extra_refs) > 100,
        "missing_expected_value_count": len(missing_expected_values),
        "missing_expected_values": missing_expected_values,
        "value_mismatch_count": len(value_mismatches),
        "value_mismatches": value_mismatches[:100],
        "value_mismatches_truncated": len(value_mismatches) > 100,
        "duplicate_actual_value_count": len(duplicate_actual_values),
        "duplicate_actual_values": duplicate_actual_values[:100],
    }
    if output_report is not None:
        Path(output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate generated KiCad schematic values against CircuitIR.")
    parser.add_argument("schematic", type=Path)
    parser.add_argument("circuit_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    circuit = json.loads(args.circuit_json.read_text(encoding="utf-8"))
    report = validate_component_values(circuit=circuit, schematic_path=args.schematic, output_report=args.output)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
