#!/usr/bin/env python3
"""Build the repo-local KiCad symbol subset used by the placer writer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from kicad.pipeline.kicad_symbol_library import DEFAULT_SUBSET_PATH, KiCadSymbolLibrary
from kicad.pipeline.placement_catalog import PLACER_KIND_LIB_IDS


def _unindent_symbol_block(text: str) -> str:
    lines = text.rstrip().splitlines()
    return "\n".join(line[4:] if line.startswith("    ") else line for line in lines) + "\n"


def build_subset(out_path: Path = DEFAULT_SUBSET_PATH, *, symbol_root: Path | None = None) -> dict[str, Any]:
    library = KiCadSymbolLibrary(
        symbol_root=symbol_root or KiCadSymbolLibrary().symbol_root,
        subset_path=out_path,
        prefer_subset=False,
    )
    requested_lib_ids = tuple(dict.fromkeys(PLACER_KIND_LIB_IDS.values()))
    resolved = library.resolve(requested_lib_ids)
    payload: dict[str, Any] = {
        "schema": "progen-kicad-symbol-subset/v1",
        "kicad_version": "10.0.4",
        "source": str(library.symbol_root),
        "requested_lib_ids": sorted(requested_lib_ids),
        "resolved_symbol_count": len(resolved.symbols),
        "symbols": {
            symbol.lib_id: {
                "block": _unindent_symbol_block(symbol.text),
                "source": symbol.source,
                "extends": symbol.extends,
                "pin_numbers": list(symbol.pin_numbers),
                "unit_pin_numbers": {
                    str(unit): list(pins) for unit, pins in sorted(symbol.unit_pin_numbers.items())
                },
                "properties": symbol.properties,
            }
            for symbol in resolved.symbols
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the bundled KiCad symbol subset for placer projects.")
    parser.add_argument("--out", default=str(DEFAULT_SUBSET_PATH), help="Output JSON path.")
    parser.add_argument("--symbol-root", help="KiCad symbols directory to mine.")
    args = parser.parse_args()
    payload = build_subset(
        Path(args.out),
        symbol_root=Path(args.symbol_root) if args.symbol_root else None,
    )
    print(json.dumps({"out": args.out, "resolved_symbol_count": payload["resolved_symbol_count"]}, indent=2))


if __name__ == "__main__":
    main()
