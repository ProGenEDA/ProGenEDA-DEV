"""Command-line interface for Proteus project inspection and generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .circuit_ir import load_json, parse_circuit_ir
from .comparison import compare_projects
from .generator import GenerationBlocked, generate_project
from .ic_combinational import (
    IcCombinationalGenerationBlocked,
    generate_ic_combinational_project_from_payload,
)
from .inspectors import find_all
from .layout import LayoutError, plan_payload
from .mixed_passive import MixedPassiveGenerationBlocked, generate_mixed_passive_project_from_payload
from .mixed_rcl import MixedRclGenerationBlocked, generate_mixed_rcl_project_from_payload
from .pdsprj import inspect_pdsprj, read_internal_file
from .reports import summarize_pdsprj
from .results import record_result, validate_result
from .resistor_v9 import ResistorGenerationBlocked, generate_resistor_project_from_payload
from .source_driven import SourceDrivenGenerationBlocked, generate_source_driven_project_from_payload
from .templates import FixtureRegistry
from .validation import validate_payload
from .versioning import read_root_dsn_version


def _print(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def inspect_command(args: argparse.Namespace) -> int:
    path = Path(args.project)
    info = inspect_pdsprj(path)
    dsn = read_internal_file(path, "ROOT.DSN") if info.has_root_dsn else b""
    payload: dict[str, Any] = {
        "path": str(path),
        "required_files": {
            "PROJECT.XML": info.has_project_xml,
            "ROOT.DSN": info.has_root_dsn,
            "ROOT.CDB": info.has_root_cdb,
            "SCRIPTS/PWRRAILS.DAT": info.has_pwrails,
        },
        "members": [
            {"name": row.name, "size": row.size, "sha256": row.sha256}
            for row in summarize_pdsprj(path)
        ],
    }
    if dsn:
        payload["root_dsn_version"] = list(read_root_dsn_version(dsn))
        payload["root_dsn_markers"] = {
            marker.decode("ascii"): len(find_all(dsn, marker))
            for marker in (b"74HC08", b"RESISTOR", b"LOGICSTATE", b"LOGICPROBE", b"$TERINPUT", b"$TEROUTPUT", b"WIRE")
        }
    _print(payload)
    return 0


def validate_command(args: argparse.Namespace) -> int:
    report = validate_payload(load_json(args.circuit), require_generation_ready=not args.structural_only)
    _print(report.as_dict())
    return 0 if report.valid else 2


def generate_command(args: argparse.Namespace) -> int:
    payload = load_json(args.circuit)
    ir, structural_issues = parse_circuit_ir(payload)
    if structural_issues:
        _print({"valid": False, "errors": [issue.as_dict() for issue in structural_issues], "warnings": []})
        return 2
    assert ir is not None
    try:
        result = generate_project(ir, args.output)
    except GenerationBlocked as exc:
        _print(exc.report.as_dict())
        return 2
    _print(result.as_dict())
    return 0


def generate_resistors_command(args: argparse.Namespace) -> int:
    payload = load_json(args.circuit)
    try:
        result = generate_resistor_project_from_payload(
            payload,
            args.outdir,
            layout_strategy=args.layout_strategy,
        )
    except ResistorGenerationBlocked as exc:
        _print(exc.report.as_dict())
        return 2
    _print(result.as_dict())
    return 0


def generate_mixed_passives_command(args: argparse.Namespace) -> int:
    payload = load_json(args.circuit)
    try:
        result = generate_mixed_passive_project_from_payload(
            payload,
            args.outdir,
            layout_strategy=args.layout_strategy,
        )
    except MixedPassiveGenerationBlocked as exc:
        _print(exc.report.as_dict())
        return 2
    _print(result.as_dict())
    return 0


def generate_mixed_rcl_command(args: argparse.Namespace) -> int:
    payload = load_json(args.circuit)
    try:
        result = generate_mixed_rcl_project_from_payload(
            payload,
            args.outdir,
            layout_strategy=args.layout_strategy,
        )
    except MixedRclGenerationBlocked as exc:
        _print(exc.report.as_dict())
        return 2
    _print(result.as_dict())
    return 0


def generate_source_driven_command(args: argparse.Namespace) -> int:
    payload = load_json(args.circuit)
    try:
        result = generate_source_driven_project_from_payload(
            payload,
            args.outdir,
            layout_strategy=args.layout_strategy,
        )
    except SourceDrivenGenerationBlocked as exc:
        _print(exc.report.as_dict())
        return 2
    _print(result.as_dict())
    return 0


def generate_ic_combinational_command(args: argparse.Namespace) -> int:
    payload = load_json(args.circuit)
    try:
        result = generate_ic_combinational_project_from_payload(
            payload,
            args.outdir,
            layout_strategy=args.layout_strategy,
        )
    except IcCombinationalGenerationBlocked as exc:
        _print(exc.report.as_dict())
        return 2
    _print(result.as_dict())
    return 0


def plan_layout_command(args: argparse.Namespace) -> int:
    payload = load_json(args.circuit)
    try:
        plan = plan_payload(payload, args.layout_strategy)
    except LayoutError as exc:
        _print({"valid": False, "errors": [{"code": "INVALID_LAYOUT", "message": str(exc)}]})
        return 2
    rendered = json.dumps(plan.as_dict(), indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


def compare_command(args: argparse.Namespace) -> int:
    result = compare_projects(args.generated, args.reference)
    _print(result)
    return 0 if result["semantic_equal"] else 1


def record_result_command(args: argparse.Namespace) -> int:
    payload = load_json(args.result)
    errors = validate_result(payload)
    if errors:
        _print({"recorded": False, "errors": errors})
        return 2
    destination = record_result(payload, args.output)
    _print({"recorded": True, "path": str(destination), "test_id": payload["test_id"]})
    return 0


def fixtures_command(_: argparse.Namespace) -> int:
    registry = FixtureRegistry.load()
    payload = registry.as_dict()
    payload["valid"] = not registry.verify_all()
    _print(payload)
    return 0 if payload["valid"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proteusgen", description="Deterministic Proteus 8.13 project tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect a .pdsprj container")
    inspect_parser.add_argument("project")
    inspect_parser.set_defaults(function=inspect_command)

    validate_parser = subparsers.add_parser("validate", help="Validate CircuitIR JSON")
    validate_parser.add_argument("circuit")
    validate_parser.add_argument("--structural-only", action="store_true", help="Validate contract/topology without generation readiness gates")
    validate_parser.set_defaults(function=validate_command)

    generate_parser = subparsers.add_parser("generate", help="Generate a .pdsprj from CircuitIR JSON")
    generate_parser.add_argument("circuit")
    generate_parser.add_argument("--output", required=True)
    generate_parser.set_defaults(function=generate_command)

    resistor_parser = subparsers.add_parser("generate-resistors", help="Generate a V9 resistor-terminal project from CircuitIR v0.1")
    resistor_parser.add_argument("circuit")
    resistor_parser.add_argument("--outdir", required=True)
    resistor_parser.add_argument("--layout-strategy", choices=("beautify", "manual", "legacy"))
    resistor_parser.set_defaults(function=generate_resistors_command)

    mixed_parser = subparsers.add_parser("generate-mixed-passives", help="Generate a locked mixed resistor/capacitor terminal project")
    mixed_parser.add_argument("circuit")
    mixed_parser.add_argument("--outdir", required=True)
    mixed_parser.add_argument("--layout-strategy", choices=("beautify", "manual", "legacy"))
    mixed_parser.set_defaults(function=generate_mixed_passives_command)

    mixed_rcl_parser = subparsers.add_parser("generate-mixed-rcl", help="Generate a locked mixed resistor/capacitor/inductor terminal project")
    mixed_rcl_parser.add_argument("circuit")
    mixed_rcl_parser.add_argument("--outdir", required=True)
    mixed_rcl_parser.add_argument("--layout-strategy", choices=("beautify", "manual", "legacy"))
    mixed_rcl_parser.set_defaults(function=generate_mixed_rcl_command)

    source_parser = subparsers.add_parser(
        "generate-source-driven",
        help="Generate a locked DC-voltage, DC-current, or AC-voltage source-driven R/C/L project",
    )
    source_parser.add_argument("circuit")
    source_parser.add_argument("--outdir", required=True)
    source_parser.add_argument("--layout-strategy", choices=("beautify", "manual", "legacy"))
    source_parser.set_defaults(function=generate_source_driven_command)

    ic_parser = subparsers.add_parser(
        "generate-ic-combinational",
        help="Generate a locked 74HC combinational IC project with optional R/C/L passives",
    )
    ic_parser.add_argument("circuit")
    ic_parser.add_argument("--outdir", required=True)
    ic_parser.add_argument("--layout-strategy", choices=("beautify", "manual", "legacy"))
    ic_parser.set_defaults(function=generate_ic_combinational_command)

    layout_parser = subparsers.add_parser(
        "plan-layout",
        help="Preview deterministic component/source coordinates without generating a Proteus project",
    )
    layout_parser.add_argument("circuit")
    layout_parser.add_argument("--layout-strategy", choices=("beautify", "manual", "legacy"))
    layout_parser.add_argument("--output", help="Optional JSON output path")
    layout_parser.set_defaults(function=plan_layout_command)

    compare_parser = subparsers.add_parser("compare", help="Compare generated and resaved/oracle projects")
    compare_parser.add_argument("generated")
    compare_parser.add_argument("reference")
    compare_parser.set_defaults(function=compare_command)

    result_parser = subparsers.add_parser("record-result", help="Append structured Proteus test evidence")
    result_parser.add_argument("result")
    result_parser.add_argument("--output", help="Alternative JSONL destination, useful for dry-run evidence collection")
    result_parser.set_defaults(function=record_result_command)

    fixtures_parser = subparsers.add_parser("fixtures", help="Verify clean fixture integrity and provenance")
    fixtures_parser.set_defaults(function=fixtures_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.function(args))
    except (FileNotFoundError, KeyError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}), file=sys.stderr)
        return 2
