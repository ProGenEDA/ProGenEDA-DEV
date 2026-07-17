#!/usr/bin/env python3
"""Apply the EasyEDA website overlay after verifying the audited baseline."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("website_root", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    package = Path(__file__).resolve().parent
    overlay = package / "website_files"
    baseline = json.loads((package / "baseline_hashes.json").read_text())
    target_root = args.website_root.expanduser().resolve()
    conflicts: list[str] = []
    operations: list[tuple[Path, Path]] = []
    for relative, expected in sorted(baseline["files"].items()):
        source = overlay / relative
        target = target_root / relative
        overlay_hash = digest(source)
        if target.exists():
            current = digest(target)
            if current not in {expected, overlay_hash}:
                conflicts.append(relative)
        elif expected is not None:
            conflicts.append(relative)
        operations.append((source, target))

    if conflicts and not args.force:
        print("Baseline conflicts:\n" + "\n".join(f"  {item}" for item in conflicts), file=sys.stderr)
        return 2
    for source, target in operations:
        print(f"{source.relative_to(overlay)} -> {target}")
        if args.dry_run:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
