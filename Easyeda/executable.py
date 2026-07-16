"""Portable command-line entry point for donor-native EasyEDA generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .catalogue import catalogue_summary
from .pipeline import PipelineError, generate_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="progen-easyeda")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="Generate one native .eprj from canonical JSON.")
    run.add_argument("input", type=Path)
    run.add_argument("--source-pack", type=Path, required=True)
    run.add_argument("--output-root", type=Path, required=True)
    run.add_argument("--routing-mode", choices=("wire", "terminal", "combination"))
    subparsers.add_parser("catalogue", help="Print the locked 40-component catalogue.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "catalogue":
        print(json.dumps(catalogue_summary(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    try:
        result = generate_project(
            args.input,
            source_pack=args.source_pack,
            output_root=args.output_root,
            routing_mode=args.routing_mode,
        )
    except (PipelineError, ValueError, OSError) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
