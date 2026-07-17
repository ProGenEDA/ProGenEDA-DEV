"""Build website registry and frontend payloads from the EasyEDA catalogue."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from Easyeda.catalogue import CATALOGUE, CATALOGUE_VERSION


_DIGITS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _base36(value: int) -> str:
    if value == 0:
        return "0"
    result = ""
    while value:
        value, remainder = divmod(value, 36)
        result = _DIGITS[remainder] + result
    return result


def build_payloads(output_root: Path) -> dict[str, Path]:
    output_root = output_root.expanduser().resolve()
    registry_path = output_root / "packages/component-registry/registries/EA-A.json"
    frontend_path = output_root / "src/generation/easyedaSupportedComponents.json"
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    frontend_path.parent.mkdir(parents=True, exist_ok=True)

    ordered = sorted(CATALOGUE)
    codes = {kind: _base36(index).rjust(2, "0") for index, kind in enumerate(ordered)}
    aliases = {
        alias: kind
        for kind in ordered
        for alias in sorted(CATALOGUE[kind].aliases)
    }
    metadata = {
        codes[kind]: {
            "canonicalName": kind,
            "displayName": kind.replace("_", " "),
            "category": CATALOGUE[kind].category,
            "referencePrefix": CATALOGUE[kind].reference_prefix,
            "valueRule": CATALOGUE[kind].value_rule,
            "defaultValue": CATALOGUE[kind].default_value,
            "terminal": CATALOGUE[kind].selector.terminal,
            "pcbRequired": CATALOGUE[kind].selector.pcb_required,
            "visible": True,
            "isIntegratedCircuit": CATALOGUE[kind].reference_prefix in {"U", "DS"},
            "maxPerCircuit": None,
        }
        for kind in ordered
    }
    registry = {
        "service": "EA",
        "version": "A",
        "base62Alphabet": _DIGITS,
        "source": {
            "repo_path": "Easyeda/catalogue.py",
            "catalogue_schema": CATALOGUE_VERSION,
            "scope": "donor-native EasyEDA Pro schematic and bounded PCB backend",
            "max_components_per_circuit": 80,
            "max_physical_pcb_components": 32,
            "append_only_required": True,
        },
        "components": {codes[kind]: kind for kind in ordered},
        "aliases": aliases,
        "componentMetadata": metadata,
    }

    categories: dict[str, list[str]] = {}
    for kind in ordered:
        categories.setdefault(CATALOGUE[kind].category, []).append(kind)
    frontend = {
        "schema": "progen-easyeda-website-components/v1",
        "catalogue": CATALOGUE_VERSION,
        "total_supported_families": len(ordered),
        "physical_source_families": sum(
            not entry.selector.terminal for entry in CATALOGUE.values()
        ),
        "native_terminal_families": sorted(
            kind for kind, entry in CATALOGUE.items() if entry.selector.terminal
        ),
        "groups": {category: kinds for category, kinds in sorted(categories.items())},
        "aliases": aliases,
        "limits": {
            "max_schematic_input_components": 80,
            "max_physical_pcb_components": 32,
        },
        "routing_modes": ["wire", "terminal", "combination"],
        "default_routing_mode": "combination",
        "output": "One native EasyEDA Pro .eprj plus a private internal audit ZIP.",
        "validation": [
            "SQLite integrity and native document checks",
            "exact donor symbol and footprint hash checks",
            "complete source-pin accounting",
            "expected-versus-actual netlist comparison",
            "component, wire, terminal, and compactness geometry checks",
            "bounded PCB footprint, pad-net, track, via, outline, and connectivity checks",
        ],
    }

    for path, value in ((registry_path, registry), (frontend_path, frontend)):
        path.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {"registry": registry_path, "frontend": frontend_path}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            {name: str(path) for name, path in build_payloads(args.output_root).items()},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
