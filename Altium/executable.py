"""Command line for direct native Altium generation and research oracles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .direct_generator import DirectGenerationError, generate_direct_project
from .direct_validator import DirectValidationError, validate_direct_schematic
from .ir import CircuitInputError, load_circuit
from .project_package import ProjectPackageError, inspect_project_package
from .source_catalogue import SourceCatalogueError, load_source_catalogue


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="progen-altium")
    commands = parser.add_subparsers(dest="command", required=True)

    validate_input = commands.add_parser(
        "validate-input", help="Normalize canonical JSON before source-record resolution."
    )
    validate_input.add_argument("input", type=Path)
    validate_input.add_argument("--routing-mode", choices=("wire", "terminal", "combination"))

    generate = commands.add_parser(
        "generate", help="Generate a fresh source-backed native Altium project directly from JSON."
    )
    generate.add_argument("input", type=Path)
    generate.add_argument("--output-root", type=Path, required=True)
    generate.add_argument("--routing-mode", choices=("wire", "terminal", "combination"))

    supported = commands.add_parser(
        "supported-components", help="Print the source-audited direct Altium component catalogue."
    )
    supported.add_argument("--compact", action="store_true")

    probe = commands.add_parser(
        "probe-engine", help="Report actual formats exposed by the local conversion engine."
    )
    probe.add_argument("--converter", type=Path)
    probe.add_argument("--node", type=Path)

    validate_package = commands.add_parser(
        "validate-package", help="Inspect an Altium ZIP project package without Altium Designer."
    )
    validate_package.add_argument("package", type=Path)

    validate_schematic = commands.add_parser(
        "validate-schematic", help="Validate saved direct SchDoc pins/wires against its expected contract."
    )
    validate_schematic.add_argument("schematic", type=Path)
    validate_schematic.add_argument("--expected", type=Path, required=True)

    bridge = commands.add_parser(
        "research-bridge", help="Research-only conversion oracle; never used by direct generation."
    )
    bridge.add_argument("source", type=Path)
    bridge.add_argument("--source-type", default="easyeda-pro-2")
    bridge.add_argument("--output-root", type=Path, required=True)
    bridge.add_argument("--project-name")
    bridge.add_argument("--converter", type=Path)
    bridge.add_argument("--node", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate-input":
            circuit = load_circuit(args.input, routing_mode=args.routing_mode)
            print(json.dumps(circuit.normalized_json(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "generate":
            result = generate_direct_project(
                args.input,
                output_root=args.output_root,
                routing_mode=args.routing_mode,
            )
            print(json.dumps(result.json(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "supported-components":
            catalogue = load_source_catalogue().json()
            if args.compact:
                catalogue = {
                    "schema": catalogue["schema"],
                    "aliases": catalogue["aliases"],
                    "components": {
                        name: {
                            "library_reference": item["library_reference"],
                            "pins": sorted(item["pins"]),
                        }
                        for name, item in catalogue["components"].items()
                    },
                }
            print(json.dumps(catalogue, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        if args.command == "probe-engine":
            from .conversion_engine import probe_converter

            print(
                json.dumps(
                    probe_converter(
                        converter_script=args.converter,
                        node_executable=args.node,
                    ).json(),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "validate-package":
            report = inspect_project_package(args.package)
            print(json.dumps(report.json(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if report.passed else 2
        if args.command == "validate-schematic":
            expected = json.loads(args.expected.read_text(encoding="utf-8"))
            if not isinstance(expected, dict):
                raise DirectValidationError("Expected direct schematic contract must be a JSON object.")
            report = validate_direct_schematic(args.schematic, expected)
            print(json.dumps(report.json(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if report.passed else 2
        if args.command == "research-bridge":
            from .conversion_engine import convert_with_local_engine

            result = convert_with_local_engine(
                args.source,
                output_directory=args.output_root,
                source_type=args.source_type,
                project_name=args.project_name,
                converter_script=args.converter,
                node_executable=args.node,
            )
            print(json.dumps(result.json(), ensure_ascii=False, indent=2, sort_keys=True))
            return 0
    except (
        CircuitInputError,
        DirectGenerationError,
        DirectValidationError,
        ProjectPackageError,
        SourceCatalogueError,
        OSError,
        ValueError,
    ) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}), file=sys.stderr)
        return 2
    except RuntimeError as exc:
        if args.command in {"probe-engine", "research-bridge"}:
            print(json.dumps({"passed": False, "error": str(exc)}), file=sys.stderr)
            return 2
        raise
    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
