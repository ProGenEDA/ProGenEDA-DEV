"""Read-only inventory helper for native IC/display donor projects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.ic_native import NativeRegistry, analyze_donor  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze native Proteus donor packets without modifying them.")
    parser.add_argument("projects", nargs="*", help="Specific .pdsprj donors. If omitted, registry donors are analyzed.")
    parser.add_argument("--output", help="Optional JSON output path.")
    args = parser.parse_args(argv)

    if args.projects:
        projects = [Path(item) for item in args.projects]
    else:
        registry = NativeRegistry.load()
        seen: set[Path] = set()
        projects = []
        for component in registry.components.values():
            for donor in component.donors.values():
                if donor.exists() and donor not in seen:
                    seen.add(donor)
                    projects.append(donor)
        for donor in registry.pair_donors.values():
            if donor.exists() and donor not in seen:
                seen.add(donor)
                projects.append(donor)

    report = {"count": len(projects), "donors": [analyze_donor(project) for project in sorted(projects)]}
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
