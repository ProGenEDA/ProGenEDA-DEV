#!/usr/bin/env python3
"""Mine KiCad source-pack files for embedded lib_symbols blocks.

This is the start of the hard/ideal route: scripts inspect KiCad source/test
schematics and build a symbol-cache index instead of guessing symbol format.
"""
from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def balanced_blocks(text: str, token: str) -> list[str]:
    blocks = []
    start = 0
    while True:
        i = text.find(token, start)
        if i == -1:
            return blocks
        depth = 0; in_s = False; esc = False
        for j in range(i, len(text)):
            ch = text[j]
            if in_s:
                if esc: esc = False
                elif ch == "\\": esc = True
                elif ch == '"': in_s = False
            else:
                if ch == '"': in_s = True
                elif ch == '(': depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        blocks.append(text[i:j+1])
                        start = j + 1
                        break
        else:
            return blocks


def mine(path: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    files: list[tuple[str, str]] = []
    if path.suffix == ".zip":
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith((".kicad_sch", ".kicad_sym")):
                    try:
                        files.append((name, z.read(name).decode("utf-8", "replace")))
                    except Exception:
                        pass
    else:
        for p in path.rglob("*"):
            if p.suffix in {".kicad_sch", ".kicad_sym"}:
                files.append((str(p), p.read_text(encoding="utf-8", errors="replace")))
    for filename, text in files:
        for block in balanced_blocks(text, "(symbol "):
            m = re.match(r'\(symbol\s+"([^"]+)"', block)
            if m and ":" in m.group(1):
                found.setdefault(m.group(1), block)
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(REPO_ROOT / "kicad/source_pack/KiCad_Source_Files_Needed_20260612_030305.zip"))
    ap.add_argument("--out", default=str(REPO_ROOT / "kicad/experiments/symbol_cache_index.json"))
    args = ap.parse_args()
    source = Path(args.source)
    if not source.exists():
        # Try decoding b64 pack.
        import sys
        sys.path.insert(0, str(REPO_ROOT))
        from kicad.source_pack.source_pack_loader import ensure_source_zip
        source = ensure_source_zip()
    index = mine(source)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(json.dumps({"source": str(source), "symbols_found": len(index), "out": str(out)}, indent=2))


if __name__ == "__main__":
    main()
