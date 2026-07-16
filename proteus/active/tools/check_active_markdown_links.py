"""Verify repository-relative Markdown links under ``proteus/active``."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[3]
ACTIVE = ROOT / "proteus" / "active"
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+['\"][^)]*['\"])?\)")


def main() -> int:
    failures: list[str] = []
    checked = 0
    for document in sorted(ACTIVE.rglob("*.md")):
        text = document.read_text(encoding="utf-8", errors="replace")
        for target in LINK.findall(text):
            target = target.strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            path_part = unquote(target.split("#", 1)[0])
            if not path_part:
                continue
            checked += 1
            candidate = (document.parent / path_part).resolve()
            try:
                candidate.relative_to(ROOT)
            except ValueError:
                failures.append(f"{document.relative_to(ROOT)} -> escapes repository: {target}")
                continue
            if not candidate.exists():
                failures.append(f"{document.relative_to(ROOT)} -> missing: {target}")
    print(f"checked={checked} failures={len(failures)}")
    for failure in failures:
        print(failure)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
