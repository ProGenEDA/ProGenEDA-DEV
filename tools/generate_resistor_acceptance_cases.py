"""Generate the predefined V9 resistor acceptance pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from proteusgen.resistor_examples import predefined_resistor_cases
from proteusgen.resistor_v9 import ResistorGenerationBlocked, generate_resistor_project_from_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate predefined resistor power/ground acceptance cases.")
    parser.add_argument("--outdir", required=True)
    args = parser.parse_args(argv)
    root = Path(args.outdir)
    root.mkdir(parents=True, exist_ok=True)
    summary: list[dict] = []
    for payload in predefined_resistor_cases():
        basename = payload["project"]["output_basename"]
        case_dir = root / basename
        case_dir.mkdir(parents=True, exist_ok=True)
        input_path = case_dir / "input.json"
        input_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        try:
            result = generate_resistor_project_from_payload(payload, case_dir)
        except ResistorGenerationBlocked as exc:
            summary.append({"case": basename, "generated": False, "report": exc.report.as_dict()})
            continue
        summary.append(
            {
                "case": basename,
                "generated": True,
                "output_path": str(result.output_path),
                "static_validation_issues": result.manifest["static_validation_issues"],
                "resistor_count": result.manifest["component_count_requested"],
                "power_terminal_count": result.manifest["power_terminal_count"],
                "ground_terminal_count": result.manifest["ground_terminal_count"],
            }
        )
    (root / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"outdir": str(root), "cases": len(summary), "failed": [item for item in summary if not item["generated"]]}, indent=2))
    return 0 if all(item["generated"] for item in summary) else 2


if __name__ == "__main__":
    sys.exit(main())
