"""Orchestrate integrated PCB generation from a validated schematic run."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .footprint_placer import place_footprints
from .kicad_pcb_writer import write_kicad_pcb
from .pcb_router import route_pcb_with_retries
from .pcb_validator import validate_pcb
from .physical_design_compiler import compile_physical_design


PCB_PIPELINE_SCHEMA = "progen-kicad-pcb-pipeline/v0.1"
MIN_SUPPORTED_DRILL_MM = 0.2


def _routing_budget(component_count: int, multi_pad_net_count: int) -> dict[str, int | float | str]:
    """Scale search effort without rejecting otherwise compilable boards."""

    load = max(component_count, multi_pad_net_count)
    if load <= 40:
        return {"profile": "small", "grid_mm": 1.27, "max_attempts": 6, "max_astar_expansions": 30_000}
    if load <= 80:
        return {"profile": "medium", "grid_mm": 1.27, "max_attempts": 6, "max_astar_expansions": 45_000}
    if load <= 140:
        return {"profile": "large", "grid_mm": 1.27, "max_attempts": 5, "max_astar_expansions": 70_000}
    return {"profile": "extra_large", "grid_mm": 2.54, "max_attempts": 3, "max_astar_expansions": 12_000}


def _source_minimum_drill(design: Any) -> float:
    drills = [
        float(value)
        for component in design.components
        for pad in component.footprint.pads
        for value in pad.get("drill", [])[:1]
        if float(value) > 0
    ]
    return min(drills, default=0.4)


def _update_project_pcb_settings(project_file: Path, design: Any) -> dict[str, Any]:
    """Persist the manufacturing constraints required by embedded footprints."""

    project = json.loads(project_file.read_text(encoding="utf-8"))
    board = project.setdefault("board", {})
    settings = board.setdefault("design_settings", {})
    source_minimum = _source_minimum_drill(design)
    minimum_hole = min(0.3, source_minimum)
    if minimum_hole < MIN_SUPPORTED_DRILL_MM:
        raise ValueError(
            f"Embedded footprint requires {minimum_hole:.3f} mm drill; "
            f"minimum supported process is {MIN_SUPPORTED_DRILL_MM:.3f} mm"
        )
    rules = settings.setdefault("rules", {})
    rules.update(
        {
            "allow_blind_buried_vias": False,
            "allow_microvias": False,
            "max_error": 0.005,
            "min_clearance": 0.2,
            "min_connection": 0.0,
            "min_copper_edge_clearance": 0.3,
            "min_groove_width": 0.0,
            "min_hole_clearance": 0.2,
            "min_hole_to_hole": 0.25,
            "min_microvia_diameter": 0.2,
            "min_microvia_drill": 0.1,
            "min_resolved_spokes": 1,
            "min_silk_clearance": 0.0,
            "min_text_height": 0.8,
            "min_text_thickness": 0.08,
            "min_through_hole_diameter": minimum_hole,
            "min_track_width": 0.2,
            "min_via_annular_width": 0.1,
            "min_via_diameter": 0.5,
            "solder_mask_clearance": 0.0,
            "solder_mask_min_width": 0.0,
            "solder_mask_to_copper_clearance": 0.0,
            "use_height_for_length_calcs": True,
        }
    )
    severities = settings.setdefault("rule_severities", {})
    severities["lib_footprint_mismatch"] = "ignore"
    project_file.write_text(json.dumps(project, indent=2), encoding="utf-8")
    return {
        "schema": "progen-kicad-pcb-process-profile/v0.1",
        "minimum_track_width_mm": 0.2,
        "minimum_clearance_mm": 0.2,
        "minimum_through_hole_drill_mm": minimum_hole,
        "generated_via_diameter_mm": 0.8,
        "generated_via_drill_mm": 0.4,
        "source_minimum_drill_mm": source_minimum,
        "layer_count": 2,
    }


def generate_pcb_for_project(
    *,
    circuit: dict[str, Any],
    routing_placement: dict[str, Any],
    project_dir: Path,
    project_name: str,
    schematic_file: str,
) -> dict[str, Any]:
    """Generate a PCB only when the independently validated physical subset passes."""

    internal_dir = project_dir / "pcb_internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    design = compile_physical_design(circuit, routing_placement)
    design_path = project_dir / "pcb_physical_design.json"
    design_path.write_text(json.dumps(design.as_dict(), indent=2), encoding="utf-8")
    if not design.generated:
        report = {
            "schema": PCB_PIPELINE_SCHEMA,
            "generated": False,
            "ready_for_output": False,
            "reason": "no_supported_physical_components",
            "physical_design": design_path.name,
            "supported_component_count": 0,
            "omitted_component_count": len(design.omitted_components),
        }
        (project_dir / "pcb_pipeline_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    project_file = project_dir / f"{project_name}.kicad_pro"
    process_profile = _update_project_pcb_settings(project_file, design)
    process_profile_path = project_dir / "pcb_process_profile.json"
    process_profile_path.write_text(json.dumps(process_profile, indent=2), encoding="utf-8")

    multi_pad_net_count = sum(1 for members in design.nets.values() if len(members) >= 2)
    placement = place_footprints(design)
    placement_path = project_dir / "pcb_placement.json"
    placement_path.write_text(json.dumps(placement.as_dict(), indent=2), encoding="utf-8")
    routing_budget = _routing_budget(len(design.components), multi_pad_net_count)
    route_plan, route_variants = route_pcb_with_retries(
        design,
        placement,
        grid=float(routing_budget["grid_mm"]),
        max_attempts=int(routing_budget["max_attempts"]),
        max_astar_expansions=int(routing_budget["max_astar_expansions"]),
        enable_direct_paths=float(routing_budget["grid_mm"]) >= 2.0,
        compact_high_fanout_trees=float(routing_budget["grid_mm"]) >= 2.0,
        strategy_variants=float(routing_budget["grid_mm"]) >= 2.0,
    )
    route_path = project_dir / "pcb_route_plan.json"
    route_path.write_text(json.dumps(route_plan.as_dict(), indent=2), encoding="utf-8")
    variants_path = project_dir / "pcb_route_variants.json"
    variants_path.write_text(
        json.dumps(
            {
                "schema": "progen-kicad-pcb-route-variants/v0.1",
                "variant_count": len(route_variants),
                "variants": route_variants,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    candidate_path = write_kicad_pcb(
        internal_dir,
        f"{project_name}.candidate",
        design,
        placement,
        route_plan,
        schematic_file=schematic_file,
    )
    validation_path = project_dir / "pcb_validation_report.json"
    validation = validate_pcb(candidate_path, design, placement, route_plan, output_report=validation_path)
    ready = bool(validation["ready_for_output"])
    final_path = project_dir / f"{project_name}.kicad_pcb"
    if ready:
        shutil.copyfile(candidate_path, final_path)
    elif final_path.exists():
        final_path.unlink()
    if ready:
        reason = "accepted"
    elif route_plan.unrouted_net_count:
        reason = "pcb_routing_limit"
    else:
        reason = "pcb_validation_failed"
    report = {
        "schema": PCB_PIPELINE_SCHEMA,
        "generated": ready,
        "candidate_generated": True,
        "ready_for_output": ready,
        "reason": reason,
        "pcb_file": final_path.name if ready else None,
        "candidate_file": str(candidate_path.relative_to(project_dir)),
        "physical_design": design_path.name,
        "placement": placement_path.name,
        "route_plan": route_path.name,
        "route_variants": variants_path.name,
        "validation": validation_path.name,
        "process_profile": process_profile_path.name,
        "routing_budget": routing_budget,
        "supported_component_count": len(design.components),
        "omitted_component_count": len(design.omitted_components),
        "physical_net_count": len(design.nets),
        "segment_count": len(route_plan.segments),
        "via_count": len(route_plan.vias),
        "unrouted_net_count": route_plan.unrouted_net_count,
        "validation_ok": bool(validation["ok"]),
    }
    (project_dir / "pcb_pipeline_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
