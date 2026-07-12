"""Single executable pipeline wrapper for ProGenEDA KiCad generation."""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import random
import shutil
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import slugify

from .final_circuit_builder import _final_json_files, _fresh_prefixed_run_dir, validate_final_circuit
from .input_json_validator_fixer import DEFAULT_ROUTING_MODE, fix_json_file
from .kicad_wire_maker import generate_wired_projects_from_final_json


EXECUTABLE_SCHEMA = "progen-kicad-executable-run/v0.1"
PCB_ONLY_SCHEMA = "progen-kicad-pcb-only-run/v0.1"
VARIATION_PROFILES = ("square_compact", "square_loose", "wide_bus", "tall_bus", "loose_channels")


def _generation_passed(summary: dict[str, Any]) -> bool:
    generation = summary.get("generation")
    if not isinstance(generation, dict):
        return True
    if "all_local_netlist_ok" in generation or "all_final_validation_ok" in generation:
        return bool(generation.get("all_local_netlist_ok")) and bool(generation.get("all_final_validation_ok"))
    nested = generation.get("generation")
    if isinstance(nested, dict):
        return bool(nested.get("all_local_netlist_ok")) and bool(nested.get("all_final_validation_ok"))
    return True


def _source_files(source: Path, circuit_ids: set[str] | None = None) -> list[Path]:
    if source.is_file():
        files = [source]
    else:
        files = _final_json_files(source)
    if not circuit_ids:
        return files
    selected: list[Path] = []
    found_ids: set[str] = set()
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        circuit_id = str(data.get("circuit_id") or "").strip()
        if circuit_id in circuit_ids:
            selected.append(path)
            found_ids.add(circuit_id)
    missing = sorted(circuit_ids - found_ids)
    if missing:
        raise ValueError(f"Requested circuit IDs were not found in {source}: {', '.join(missing)}")
    return selected


def run_executable(
    source: Path,
    *,
    output_root: Path,
    label: str = "single_executable",
    routing_mode: str = DEFAULT_ROUTING_MODE,
    terminal_smoke: bool = False,
    max_wired_routes: float | None = None,
    variation_mode: bool = False,
    circuit_ids: set[str] | None = None,
) -> dict[str, Any]:
    run_root = _fresh_prefixed_run_dir(output_root, "progen_kicad_executable_run", label)
    fixed_dir = run_root / "fixed_main_json"
    reports_dir = run_root / "input_fix_reports"
    fixed_dir.mkdir(parents=True)
    reports_dir.mkdir()

    fixed_results: list[dict[str, Any]] = []
    for index, source_file in enumerate(_source_files(source, circuit_ids), 1):
        stem = source_file.stem
        output = fixed_dir / f"{stem}.json"
        report_output = reports_dir / f"{stem}_input_fix_report.json"
        report = fix_json_file(source_file, output=output, report_output=report_output, routing_mode=routing_mode)
        fixed_results.append(
            {
                "index": index,
                "source": str(source_file),
                "fixed_json": str(output.relative_to(run_root)),
                "report": str(report_output.relative_to(run_root)),
                "ok": bool(report["ok"]),
                "repair_count": int(report["repair_count"]),
                "validation": report["validation"],
            }
        )

    generation_dir = run_root / "generation"
    wire_config: dict[str, Any] = {}
    if max_wired_routes is not None:
        wire_config["max_wired_routes"] = max_wired_routes
    if variation_mode:
        wire_config["variation_mode"] = 1.0
    generation_summary = generate_wired_projects_from_final_json(
        fixed_dir,
        examples_root=output_root,
        label=f"{label}_{routing_mode}",
        run_dir=generation_dir,
        routing_mode=routing_mode,
        wire_config=wire_config or None,
    )

    terminal_summary: dict[str, Any] | None = None
    if terminal_smoke:
        terminal_dir = run_root / "terminal_generation"
        terminal_summary = generate_wired_projects_from_final_json(
            fixed_dir,
            examples_root=output_root,
            label=f"{label}_terminal_smoke",
            run_dir=terminal_dir,
            routing_mode="terminal",
        )

    summary = {
        "schema": EXECUTABLE_SCHEMA,
        "run_dir": str(run_root),
        "source": str(source),
        "requested_circuit_ids": sorted(circuit_ids) if circuit_ids else None,
        "routing_mode": routing_mode,
        "terminal_smoke_enabled": terminal_smoke,
        "variation_mode_enabled": variation_mode,
        "input_count": len(fixed_results),
        "all_inputs_fixed": all(item["ok"] for item in fixed_results),
        "fixed_main_json_dir": str(fixed_dir.relative_to(run_root)),
        "input_fix_reports_dir": str(reports_dir.relative_to(run_root)),
        "generation_run_dir": str(generation_dir.relative_to(run_root)),
        "generation": generation_summary,
        "terminal_generation": terminal_summary,
        "results": fixed_results,
    }
    (run_root / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_root / "README.md").write_text(
        "# ProGenEDA KiCad Executable Run\n\n"
        "This immutable folder was produced by the single executable wrapper. It first validates/fixes "
        "input JSON into canonical main JSON, then runs the KiCad combination/terminal/wire project pipeline. "
        "The generated project run contains user-project zips and internal-only bundles.\n",
        encoding="utf-8",
    )
    return summary


def run_pcb_only(
    source: Path,
    *,
    output_root: Path,
    label: str = "pcb_only",
    routing_mode: str = DEFAULT_ROUTING_MODE,
    circuit_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Expose only accepted native boards from the canonical full pipeline.

    A PCB still depends on the source-backed schematic pin contract, therefore
    this command deliberately runs the normal fixer and combined schematic/PCB
    generation first.  It then copies only independently accepted ``.kicad_pcb``
    artifacts into a direct-user folder and records every non-output reason.
    """

    generation_run = run_executable(
        source,
        output_root=output_root,
        label=f"{label}_source_pipeline",
        routing_mode=routing_mode,
        circuit_ids=circuit_ids,
    )
    run_root = Path(str(generation_run["run_dir"]))
    exports_dir = run_root / "pcb_only_exports"
    exports_dir.mkdir()
    generated = generation_run.get("generation", {})
    generation_results = generated.get("results", []) if isinstance(generated, dict) else []
    exports: list[dict[str, Any]] = []
    for result in generation_results:
        if not isinstance(result, dict):
            continue
        circuit_id = str(result.get("circuit_id") or "unknown")
        artifacts = result.get("output_artifacts")
        pcb_artifact = artifacts.get("user_pcb") if isinstance(artifacts, dict) else None
        source_path = (
            run_root / "generation" / str(pcb_artifact["path"])
            if isinstance(pcb_artifact, dict) and pcb_artifact.get("path")
            else None
        )
        ready = bool(result.get("pcb_ready_for_output")) and source_path is not None and source_path.is_file()
        output_path: Path | None = None
        if ready and source_path is not None:
            circuit_dir = exports_dir / slugify(circuit_id).lower()
            circuit_dir.mkdir()
            output_path = circuit_dir / source_path.name
            shutil.copy2(source_path, output_path)
        exports.append(
            {
                "circuit_id": circuit_id,
                "ready_for_output": ready,
                "reason": str(result.get("pcb_reason") or "unknown"),
                "physical_component_count": int(result.get("pcb_supported_component_count", 0)),
                "omitted_component_count": int(result.get("pcb_omitted_component_count", 0)),
                "unrouted_net_count": int(result.get("pcb_unrouted_net_count", 0)),
                "pcb_file": str(output_path.relative_to(run_root)) if output_path is not None else None,
                "artifact": pcb_artifact if ready else None,
            }
        )
    summary = {
        "schema": PCB_ONLY_SCHEMA,
        "run_dir": str(run_root),
        "source": str(source),
        "requested_circuit_ids": sorted(circuit_ids) if circuit_ids else None,
        "routing_mode": routing_mode,
        "input_count": len(exports),
        "accepted_pcb_count": sum(1 for item in exports if item["ready_for_output"]),
        "rejected_pcb_count": sum(1 for item in exports if not item["ready_for_output"]),
        "all_pcb_ready": bool(exports) and all(item["ready_for_output"] for item in exports),
        "pcb_only_exports_dir": str(exports_dir.relative_to(run_root)),
        "generation": generation_run,
        "pcb_exports": exports,
    }
    summary["ok"] = bool(summary["all_pcb_ready"]) and _generation_passed(generation_run)
    (run_root / "pcb_only_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_variation_source(
    source: Path,
    *,
    output_root: Path,
    label: str,
    sample_count: int,
    variations_per_circuit: int,
    seed: int,
    routing_mode: str = DEFAULT_ROUTING_MODE,
    new_500_only: bool = True,
) -> dict[str, Any]:
    files = _source_files(source)
    if new_500_only:
        n_files = [path for path in files if path.stem.upper().startswith("N")]
        if n_files:
            files = n_files
    if sample_count > 0 and sample_count < len(files):
        files = sorted(random.Random(seed).sample(files, sample_count), key=lambda path: path.name)
    else:
        files = sorted(files, key=lambda path: path.name)

    run_root = _fresh_prefixed_run_dir(output_root, "final_json_variation_source_run", label)
    final_json_dir = run_root / "final_json"
    final_json_dir.mkdir(parents=True)
    results: list[dict[str, Any]] = []

    for selected_index, path in enumerate(files, 1):
        base = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(base, dict):
            raise ValueError(f"{path} must contain a JSON object")
        original_id = str(base.get("circuit_id") or path.stem)
        original_name = str(base.get("circuit_name") or base.get("name") or original_id)
        for variation_index in range(1, variations_per_circuit + 1):
            profile = VARIATION_PROFILES[(selected_index + variation_index + seed) % len(VARIATION_PROFILES)]
            data = deepcopy(base)
            data["circuit_id"] = f"{original_id}_V{variation_index:02d}"
            data["circuit_name"] = f"{original_name} Variation {variation_index:02d}"
            if isinstance(data.get("routing"), dict):
                data["routing"]["mode"] = routing_mode
                data["routing"].setdefault("terminal_policy", {})
                data["routing"]["terminal_policy"]["fallback_unroutable_or_invalid_wires_to_terminal"] = routing_mode == "combination"
            data["generation_variation"] = {
                "enabled": True,
                "schema": "progen-kicad-generation-variation/v0.1",
                "source_circuit_id": original_id,
                "source_file": str(path),
                "selected_index": selected_index,
                "variation_index": variation_index,
                "variation_total": variations_per_circuit,
                "profile": profile,
                "seed": seed,
                "disable_adaptive_cap": True,
            }
            data["validation"] = validate_final_circuit(data)
            target = final_json_dir / f"{path.stem}__var{variation_index:02d}_{profile}.json"
            target.write_text(json.dumps(data, indent=2), encoding="utf-8")
            results.append(
                {
                    "source": str(path),
                    "target": str(target.relative_to(run_root)),
                    "source_circuit_id": original_id,
                    "variation_circuit_id": data["circuit_id"],
                    "profile": profile,
                    "validation": data["validation"],
                }
            )

    summary = {
        "schema": "progen-kicad-variation-source/v0.1",
        "run_dir": str(run_root),
        "source": str(source),
        "routing_mode": routing_mode,
        "new_500_only": new_500_only,
        "seed": seed,
        "selected_circuit_count": len(files),
        "variations_per_circuit": variations_per_circuit,
        "variation_count": len(results),
        "all_valid": all(item.get("validation", {}).get("status") == "pass" for item in results),
        "final_json_dir": str(final_json_dir.relative_to(run_root)),
        "final_json_dir_abs": str(final_json_dir),
        "profiles": list(VARIATION_PROFILES),
        "results": results,
    }
    (run_root / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_root / "README.md").write_text(
        "# ProGenEDA KiCad Variation Source\n\n"
        "Fresh immutable source folder containing deterministic layout-variation JSONs. "
        "Each clone keeps the original circuit connectivity and records its selected variation profile.\n",
        encoding="utf-8",
    )
    return summary


def run_variations(
    source: Path,
    *,
    output_root: Path,
    label: str,
    sample_count: int,
    variations_per_circuit: int,
    seed: int,
    routing_mode: str = DEFAULT_ROUTING_MODE,
    new_500_only: bool = True,
) -> dict[str, Any]:
    source_summary = build_variation_source(
        source,
        output_root=output_root,
        label=f"{label}_source",
        sample_count=sample_count,
        variations_per_circuit=variations_per_circuit,
        seed=seed,
        routing_mode=routing_mode,
        new_500_only=new_500_only,
    )
    generation_summary = run_executable(
        Path(source_summary["final_json_dir_abs"]),
        output_root=output_root,
        label=f"{label}_projects",
        routing_mode=routing_mode,
        variation_mode=True,
    )
    summary = {
        "schema": "progen-kicad-executable-variation-run/v0.1",
        "source_variations": source_summary,
        "generation": generation_summary,
        "ok": bool(source_summary["all_valid"])
        and bool(generation_summary.get("all_inputs_fixed"))
        and bool(generation_summary.get("generation", {}).get("all_local_netlist_ok"))
        and bool(generation_summary.get("generation", {}).get("all_final_validation_ok")),
    }
    summary_path = Path(source_summary["run_dir"]) / "variation_generation_manifest.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def build_combined_source(
    *,
    old_100_dir: Path,
    new_500_dir: Path,
    output_root: Path,
    label: str,
    routing_mode: str = DEFAULT_ROUTING_MODE,
) -> dict[str, Any]:
    run_root = _fresh_prefixed_run_dir(output_root, "final_json_run", label)
    final_json_dir = run_root / "final_json"
    final_json_dir.mkdir(parents=True)
    results: list[dict[str, Any]] = []

    for path in _final_json_files(old_100_dir):
        data = json.loads(path.read_text(encoding="utf-8"))
        data["routing"]["mode"] = routing_mode
        data["routing"]["terminal_policy"]["fallback_unroutable_or_invalid_wires_to_terminal"] = routing_mode == "combination"
        data["validation"] = validate_final_circuit(data)
        target = final_json_dir / path.name
        target.write_text(json.dumps(data, indent=2), encoding="utf-8")
        results.append({"source": str(path), "target": str(target.relative_to(run_root)), "validation": data["validation"]})

    for path in _final_json_files(new_500_dir):
        target = final_json_dir / path.name
        shutil.copy2(path, target)
        data = json.loads(target.read_text(encoding="utf-8"))
        results.append({"source": str(path), "target": str(target.relative_to(run_root)), "validation": data.get("validation", {})})

    summary = {
        "schema": "progen-kicad-combined-final-json-source/v0.1",
        "run_dir": str(run_root),
        "old_100_dir": str(old_100_dir),
        "new_500_dir": str(new_500_dir),
        "routing_mode": routing_mode,
        "circuit_count": len(results),
        "all_valid": all(item.get("validation", {}).get("status") == "pass" for item in results),
        "final_json_dir": str(final_json_dir.relative_to(run_root)),
        "results": results,
    }
    (run_root / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (run_root / "README.md").write_text(
        "# Combined 600 Main JSON Source\n\n"
        "Fresh immutable source folder containing the locked 100 plus the generated 500. "
        "The old generated folders are not modified.\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Single ProGenEDA KiCad executable: fixed JSON in, project/internal artifacts out.")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Validate/fix JSON and generate KiCad outputs.")
    run.add_argument("source", type=Path, help="One main JSON file or a folder/run with final_json/*.json.")
    run.add_argument("--output-root", default="kicad/examples", type=Path)
    run.add_argument("--label", default="single_executable")
    run.add_argument("--routing-mode", default=DEFAULT_ROUTING_MODE, choices=("wire", "terminal", "combination"))
    run.add_argument("--terminal-smoke", action="store_true")
    run.add_argument("--max-wired-routes", type=float)
    run.add_argument("--variation-mode", action="store_true", help="Disable combination wire-route cap and honor generation_variation metadata.")
    run.add_argument("--circuit-id", action="append", default=[], help="Generate only this canonical circuit ID; repeat for a reproducible subset.")

    pcb_only = sub.add_parser(
        "run-pcb",
        help="Run the canonical pipeline and expose only independently accepted .kicad_pcb outputs.",
    )
    pcb_only.add_argument("source", type=Path, help="One main JSON file or a folder/run with final_json/*.json.")
    pcb_only.add_argument("--output-root", default="kicad/examples", type=Path)
    pcb_only.add_argument("--label", default="pcb_only")
    pcb_only.add_argument("--routing-mode", default=DEFAULT_ROUTING_MODE, choices=("wire", "terminal", "combination"))
    pcb_only.add_argument("--circuit-id", action="append", default=[], help="Generate only this canonical circuit ID; repeat for a reproducible subset.")

    variations = sub.add_parser("run-variations", help="Create deterministic variation JSONs and run the normal generator on them.")
    variations.add_argument("source", type=Path, help="Folder/run with final_json/*.json.")
    variations.add_argument("--output-root", default="kicad/examples", type=Path)
    variations.add_argument("--label", default="variation_batch")
    variations.add_argument("--routing-mode", default=DEFAULT_ROUTING_MODE, choices=("wire", "terminal", "combination"))
    variations.add_argument("--sample-count", type=int, default=100)
    variations.add_argument("--variations-per-circuit", type=int, default=3)
    variations.add_argument("--seed", type=int, default=20260706)
    variations.add_argument("--all-sources", action="store_true", help="Allow sampling from all source files instead of only N* new-500 files.")

    combine = sub.add_parser("combine-sources", help="Create a fresh 600-circuit final JSON source folder.")
    combine.add_argument("--old-100-dir", required=True, type=Path)
    combine.add_argument("--new-500-dir", required=True, type=Path)
    combine.add_argument("--output-root", default="kicad/examples", type=Path)
    combine.add_argument("--label", default="main_json_catalog_600_combination")
    combine.add_argument("--routing-mode", default=DEFAULT_ROUTING_MODE, choices=("wire", "terminal", "combination"))

    args = parser.parse_args()
    if args.command == "run":
        summary = run_executable(
            args.source,
            output_root=args.output_root,
            label=args.label,
            routing_mode=args.routing_mode,
            terminal_smoke=args.terminal_smoke,
            max_wired_routes=args.max_wired_routes,
            variation_mode=args.variation_mode,
            circuit_ids=set(args.circuit_id) or None,
        )
    elif args.command == "run-pcb":
        summary = run_pcb_only(
            args.source,
            output_root=args.output_root,
            label=args.label,
            routing_mode=args.routing_mode,
            circuit_ids=set(args.circuit_id) or None,
        )
    elif args.command == "run-variations":
        summary = run_variations(
            args.source,
            output_root=args.output_root,
            label=args.label,
            sample_count=args.sample_count,
            variations_per_circuit=args.variations_per_circuit,
            seed=args.seed,
            routing_mode=args.routing_mode,
            new_500_only=not args.all_sources,
        )
    else:
        summary = build_combined_source(
            old_100_dir=args.old_100_dir,
            new_500_dir=args.new_500_dir,
            output_root=args.output_root,
            label=args.label,
            routing_mode=args.routing_mode,
        )
    print(json.dumps(summary, indent=2))
    ok = bool(summary.get("ok", summary.get("all_inputs_fixed", summary.get("all_valid", False))))
    ok = ok and _generation_passed(summary)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
