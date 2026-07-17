"""Create and verify the canonical 200-circuit Proteus JSON corpus."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from proteusgen.pdf_circuit_corpus import (
    DEFAULT_EXPECTED_CIRCUITS,
    parse_pdf_circuit_corpus,
    verify_written_circuit_corpus,
    write_circuit_corpus,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCE = (
    REPOSITORY_ROOT
    / "proteus"
    / "active"
    / "fixtures"
    / "circuit_specs"
    / "Proteus_200_Circuits_Complete_Pin_Wiring.pdf"
)
DEFAULT_OUTPUT = REPOSITORY_ROOT / "proteus" / "active" / "examples" / "proteus_200_circuits"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Verify an existing corpus without rewriting it.")
    parser.add_argument("--expected-circuits", type=int, default=DEFAULT_EXPECTED_CIRCUITS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.check:
            report = verify_written_circuit_corpus(
                source_pdf=args.source,
                output_root=args.output,
                expected_circuit_count=args.expected_circuits,
            )
        else:
            records = parse_pdf_circuit_corpus(
                args.source,
                expected_circuit_count=args.expected_circuits,
            )
            write_circuit_corpus(records, source_pdf=args.source, output_root=args.output)
            report = verify_written_circuit_corpus(
                source_pdf=args.source,
                output_root=args.output,
                expected_circuit_count=args.expected_circuits,
            )
    except Exception as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
