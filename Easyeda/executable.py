"""Portable command-line entry point for donor-native EasyEDA generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .catalogue import catalogue_summary
from .donor_source import EasyedaDonorSource, bundled_source_pack
from .input_fixer import repair_circuit_input
from .ir import load_circuit
from .pipeline import PipelineError, generate_project
from .value_editor import apply_value_edits, editable_component_index, load_edits


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="progen-easyeda")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Generate one native .eprj from canonical JSON.")
    run.add_argument("input", type=Path)
    run.add_argument(
        "--source-pack",
        type=Path,
        help="Optional authorized source override; the locked 59-part donor bundle is built in.",
    )
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--routing-mode", choices=("wire", "terminal", "combination"))
    subparsers.add_parser("catalogue", help="Print the locked donor-only component catalogue.")
    editable = subparsers.add_parser(
        "editable", help="Print normal-mode editable fields for one circuit."
    )
    editable.add_argument("input", type=Path)
    edit = subparsers.add_parser(
        "edit", help="Apply deterministic value/reference edits to canonical JSON."
    )
    edit.add_argument("input", type=Path)
    edit.add_argument("edits", type=Path)
    edit.add_argument("--output", type=Path, required=True)
    fix = subparsers.add_parser(
        "fix-input",
        help="Repair and canonicalize input JSON using exact embedded donor pins.",
    )
    fix.add_argument("input", type=Path)
    fix.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser(
        "validate-input",
        help="Validate and report deterministic repairs without generating a project.",
    )
    validate.add_argument("input", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "catalogue":
        print(json.dumps(catalogue_summary(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "editable":
        circuit = load_circuit(args.input)
        print(
            json.dumps(
                editable_component_index(circuit),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "edit":
        edited, report = apply_value_edits(args.input, load_edits(args.edits))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(edited, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command in {"fix-input", "validate-input"}:
        try:
            result = repair_circuit_input(
                args.input,
                EasyedaDonorSource(bundled_source_pack()),
            )
        except (RuntimeError, ValueError, OSError) as exc:
            print(
                json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False),
                file=sys.stderr,
            )
            return 2
        if args.command == "fix-input":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(result.fixed, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n",
                encoding="utf-8",
            )
        print(json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    try:
        result = generate_project(
            args.input,
            source_pack=args.source_pack,
            output_root=args.output_root,
            routing_mode=args.routing_mode,
        )
    except (PipelineError, RuntimeError, ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
