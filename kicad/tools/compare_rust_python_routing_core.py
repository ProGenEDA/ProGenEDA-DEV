"""Compare the temp Rust routing core against Python LiveRoutingState.

This is intentionally a comparison harness, not a production switch. It can
load the maturin-built wheel from a temporary extraction directory and compare
the implemented Rust phase-1 state math against the current Python state.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import plan_placement
from kicad.pipeline.catelogues import load_component_catalogue
from kicad.pipeline.routing.python.live_routing_state import build_live_routing_state
from kicad.pipeline.routing.python.routing_orchestrator import _placement_fallbacks_for_rust


def _load_rust_module(wheel: Path | None) -> Any:
    if wheel is None:
        return importlib.import_module("progen_routing_core")
    temp_dir = tempfile.TemporaryDirectory(prefix="progen_routing_core_")
    with zipfile.ZipFile(wheel) as archive:
        archive.extractall(temp_dir.name)
    sys.path.insert(0, temp_dir.name)
    module = importlib.import_module("progen_routing_core")
    module.__progen_temp_dir = temp_dir
    return module


def _canonical_component_state(state: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for ref, component in sorted((state.get("components") or {}).items()):
        out[ref] = {
            "at": component.get("at"),
            "rotation": component.get("rotation"),
            "body": component.get("body"),
            "keepout": component.get("keepout"),
            "pins": {
                pin: {
                    "number": pin_data.get("number"),
                    "point": pin_data.get("point"),
                    "side": pin_data.get("side"),
                    "type": pin_data.get("type"),
                    "roles": pin_data.get("roles", []),
                }
                for pin, pin_data in sorted((component.get("pins") or {}).items())
            },
        }
    return out


def compare(circuit_path: Path, placement_path: Path | None, wheel: Path | None) -> dict[str, Any]:
    circuit = json.loads(circuit_path.read_text(encoding="utf-8"))
    placement = json.loads(placement_path.read_text(encoding="utf-8")) if placement_path else plan_placement(circuit).as_dict()
    catalogue = load_component_catalogue()
    payload = {
        "catalogue": catalogue.as_dict(),
        "placement_fallbacks": _placement_fallbacks_for_rust(placement, circuit),
        "placement": placement,
        "circuit": circuit,
        "config": {},
    }
    python_state = build_live_routing_state(placement, circuit, component_catalogue=catalogue).as_dict()
    rust = _load_rust_module(wheel)
    rust_state = json.loads(rust.build_live_state(json.dumps(payload)))
    python_components = _canonical_component_state(python_state)
    rust_components = _canonical_component_state(rust_state)
    mismatches = []
    for ref in sorted(set(python_components) | set(rust_components)):
        if python_components.get(ref) != rust_components.get(ref):
            mismatches.append(
                {
                    "ref": ref,
                    "python": python_components.get(ref),
                    "rust": rust_components.get(ref),
                }
            )
    return {
        "schema": "progen-rust-python-routing-core-comparison/v0.1",
        "phase": "live_state_geometry_and_pins",
        "circuit": str(circuit_path),
        "placement": str(placement_path) if placement_path else "generated_by_python_plan_placement",
        "wheel": str(wheel) if wheel else "import_from_pythonpath",
        "ok": not mismatches,
        "component_count": len(set(python_components) | set(rust_components)),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:50],
        "rust_engine": rust_state.get("engine"),
        "rust_implemented": rust_state.get("implemented"),
        "python_metrics": python_state.get("metrics", {}),
        "rust_metrics": rust_state.get("metrics", {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("circuit_json", type=Path)
    parser.add_argument("--placement-json", type=Path)
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = compare(args.circuit_json, args.placement_json, args.wheel)
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
