"""Placement Validator stage."""

from __future__ import annotations

from kicad.generator.kicad_json_to_project import PlacementPlan

from .context import PipelineContext, StageResult


def _overlaps(a: object, b: object) -> bool:
    return bool(a.left < b.right and a.right > b.left and a.top < b.bottom and a.bottom > b.top)


def validate_placement(circuit: dict[str, Any], placement_plan: PlacementPlan) -> dict[str, Any]:
    placed = {comp.ref for comp in placement_plan.components}
    requested = {
        str(item.get("id") or item.get("ref"))
        for item in circuit.get("components", [])
        if isinstance(item, dict) and (item.get("id") or item.get("ref"))
    }
    missing = sorted(ref for ref in requested if ref and ref not in placed)
    overlaps = []
    obstacles = list(placement_plan.obstacles)
    for index, left in enumerate(obstacles):
        for right in obstacles[index + 1 :]:
            if _overlaps(left, right):
                overlaps.append({"left": left.owner, "right": right.owner})
    return {"valid": not missing and not overlaps, "missing": missing, "overlaps": overlaps}


def run(ctx: PipelineContext) -> StageResult:
    if ctx.placement_plan is None:
        return StageResult("placement_validator", ok=False, errors=["No placement plan exists."])
    ctx.placement_report = validate_placement(ctx.circuit, ctx.placement_plan)
    errors = []
    if ctx.placement_report["missing"]:
        errors.append(f"Missing placements for {ctx.placement_report['missing']}")
    if ctx.placement_report["overlaps"]:
        errors.append(f"Component body overlaps detected: {ctx.placement_report['overlaps']}")
    warnings = []
    return StageResult(
        "placement_validator",
        ok=not errors,
        summary="Checked requested components against generated placements.",
        data=ctx.placement_report,
        warnings=warnings,
        errors=errors,
    )
