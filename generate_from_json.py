"""CLI wrapper for the locked V9 resistor JSON generator."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from proteusgen.circuit_ir import load_json
from proteusgen.resistor_v9 import ResistorGenerationBlocked, generate_resistor_project_from_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Proteus 8.13 resistor-terminal projects from JSON.")
    parser.add_argument("--input", required=True, help="CircuitIR v0.1 JSON file")
    parser.add_argument("--outdir", required=True, help="Output directory")
    args = parser.parse_args(argv)
    try:
        result = generate_resistor_project_from_payload(load_json(args.input), Path(args.outdir))
    except ResistorGenerationBlocked as exc:
        print(json.dumps(exc.report.as_dict(), indent=2, sort_keys=True))
        return 2
    print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
