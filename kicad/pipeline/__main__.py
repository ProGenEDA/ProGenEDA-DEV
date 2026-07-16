"""Command line entrypoint for the KiCad placer pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .placer_pipeline import run_placer_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the placer-only Progen KiCad pipeline.")
    parser.add_argument("input", help="CircuitIR JSON file.")
    parser.add_argument("--out", required=True, help="Output project directory.")
    parser.add_argument("--no-write", action="store_true", help="Run stages without writing placement trace files.")
    args = parser.parse_args()

    path = Path(args.input)
    input_data = path if path.exists() else args.input
    ctx = run_placer_pipeline(input_data, out_dir=args.out, write_trace=not args.no_write)
    print(json.dumps(ctx.pipeline_summary(), indent=2))


if __name__ == "__main__":
    main()
