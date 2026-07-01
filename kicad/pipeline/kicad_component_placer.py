"""Canonical KiCad Component Placer stage and reusable runner."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import PlacementPlan, slugify

from .context import PipelineContext, StageResult
from .placement_catalog import CatalogPlacementPlan, place_catalog_components, resolve_placement_spec


def _pin_aware(circuit: dict[str, Any]) -> bool:
    raw_components = circuit.get("components", [])
    return isinstance(raw_components, list) and bool(raw_components) and all(
        isinstance(item, dict) and isinstance(item.get("pins"), dict) and bool(item.get("pins"))
        for item in raw_components
    )


def _catalog_supported(circuit: dict[str, Any]) -> bool:
    raw_components = circuit.get("components", [])
    return isinstance(raw_components, list) and all(
        isinstance(item, dict) and resolve_placement_spec(str(item.get("kind") or item.get("name") or "")) is not None
        for item in raw_components
    )


def place_components(circuit: dict[str, Any]) -> PlacementPlan | CatalogPlacementPlan:
    """Return a placement-only plan without invoking routing or schematic writing."""
    from kicad.generator.kicad_json_to_project import plan_placement

    circuit_copy = deepcopy(circuit)
    if _pin_aware(circuit_copy):
        return plan_placement(circuit_copy)
    if _catalog_supported(circuit_copy):
        return place_catalog_components(circuit_copy)
    return plan_placement(circuit_copy)


def run(ctx: PipelineContext) -> StageResult:
    try:
        ctx.placement_plan = place_components(ctx.circuit)
    except Exception as exc:  # pragma: no cover - message is asserted through pipeline errors.
        return StageResult("component_placer", ok=False, errors=[str(exc)])
    placement = ctx.placement_plan.as_dict()
    return StageResult(
        "component_placer",
        summary="Placed components with the canonical KiCad component placer.",
        data={
            "component_count": len(placement["components"]),
            "components": placement["components"],
            "obstacles": placement["obstacles"],
        },
    )


def _fresh_run_dir(examples_root: Path, label: str) -> Path:
    stamp = dt.datetime.now().strftime("%Y_%m_%d_%H%M%S")
    base_name = f"placer_run_{stamp}_{slugify(label).lower()}"
    candidate = examples_root / base_name
    suffix = 2
    while candidate.exists():
        candidate = examples_root / f"{base_name}_{suffix}"
        suffix += 1
    return candidate


def _input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    if input_path.is_dir():
        return sorted(path for path in input_path.glob("*.json") if path.name != "manifest.json")
    raise FileNotFoundError(f"placer input path does not exist: {input_path}")


def run_placer_pack(
    input_path: Path,
    *,
    examples_root: Path,
    run_label: str,
    run_dir: Path | None = None,
) -> dict[str, Any]:
    """Place one input file or a directory of input files into a fresh examples run."""
    from .placer_pipeline import run_placer_pipeline

    files = _input_files(input_path)
    if not files:
        raise ValueError(f"No placer JSON files found in {input_path}")

    run_dir = run_dir or _fresh_run_dir(examples_root, run_label)
    if run_dir.exists() and (run_dir / "projects").exists():
        raise FileExistsError(f"Refusing to reuse existing placer projects folder: {run_dir / 'projects'}")
    inputs_dir = run_dir / "inputs"
    projects_dir = run_dir / "projects"
    inputs_dir.mkdir(parents=True, exist_ok=True)
    projects_dir.mkdir(parents=True)

    results: list[dict[str, Any]] = []
    for source in files:
        copied_input = inputs_dir / source.name
        if source.resolve() != copied_input.resolve():
            if copied_input.exists():
                raise FileExistsError(f"Refusing to overwrite existing placer input: {copied_input}")
            shutil.copy2(source, copied_input)
        circuit = json.loads(copied_input.read_text(encoding="utf-8"))
        project_name = str(circuit.get("project", {}).get("name") or source.stem)
        out_dir = projects_dir / slugify(project_name).lower()
        ctx = run_placer_pipeline(circuit, out_dir=out_dir)
        manifest_path = out_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        results.append(
            {
                "input": str(copied_input.relative_to(run_dir)),
                "project_dir": str(out_dir.relative_to(run_dir)),
                "open_this": str((out_dir / manifest["open_this"]).relative_to(run_dir)),
                "component_count": manifest["component_count"],
                "symbol_instance_count": manifest["symbol_instance_count"],
                "ok": ctx.pipeline_summary()["ok"],
            }
        )

    summary = {
        "schema": "progen-kicad-component-placer-run/v1",
        "run_dir": str(run_dir),
        "input_path": str(input_path),
        "run_label": run_label,
        "input_count": len(files),
        "project_count": len(results),
        "results": results,
        "note": "Fresh examples run. Generated project folders are immutable records.",
    }
    (run_dir / "README.md").write_text(
        "# KiCad Component Placer Run\n\n"
        f"Run label: `{run_label}`\n\n"
        "This folder was generated by `kicad.pipeline.kicad_component_placer`.\n"
        "Generated project subfolders are immutable records; create a new run for any changed output.\n",
        encoding="utf-8",
    )
    (run_dir / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the canonical KiCad component placer into a fresh examples folder.")
    parser.add_argument("input", help="Input JSON file or directory of JSON files.")
    parser.add_argument("--examples-root", default="kicad/examples", help="Root where a fresh placer_run_* folder will be created.")
    parser.add_argument("--run-label", default="manual", help="Short label for the fresh run folder.")
    parser.add_argument("--run-dir", help="Optional fresh run folder to use. It must not already contain projects/.")
    args = parser.parse_args()

    summary = run_placer_pack(
        Path(args.input),
        examples_root=Path(args.examples_root),
        run_label=args.run_label,
        run_dir=Path(args.run_dir) if args.run_dir else None,
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
