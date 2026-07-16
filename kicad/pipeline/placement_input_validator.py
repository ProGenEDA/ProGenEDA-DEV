"""Source-backed input checks for the placer-only pipeline."""

from __future__ import annotations

from typing import Any

from kicad.generator.kicad_json_to_project import KIND_SPECS, SUPPORTED_KINDS

from .placement_catalog import normalize_kind, resolve_placement_spec

from .context import PipelineContext, StageResult


def validate_placement_input(circuit: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    schema = circuit.get("schema_version")
    if schema not in {
        "progen-kicad-placer-ir/v0.1",
        "progen-kicad-placer-ir/v0.2",
        "progen-kicad-circuit-ir/v1",
        "progen-kicad-circuit-ir/v0.3",
        None,
    }:
        warnings.append(f"Unrecognized placer input schema_version {schema!r}; validating component fields only.")
    if "nets" in circuit and not isinstance(circuit["nets"], dict):
        errors.append("nets must be an object when provided.")
    project = circuit.get("project")
    if not isinstance(project, dict):
        errors.append("project must be an object.")
    elif "analysis" in project and not isinstance(project["analysis"], list):
        errors.append("project.analysis must be an array when provided.")

    components = circuit.get("components")
    if not isinstance(components, list) or not components:
        errors.append("components must be a non-empty array before placement.")
        components = []

    seen_refs: set[str] = set()
    for index, item in enumerate(components, 1):
        if not isinstance(item, dict):
            errors.append(f"component {index} must be an object.")
            continue
        ref = str(item.get("id") or item.get("ref") or f"component {index}")
        if ref in seen_refs:
            errors.append(f"duplicate component id {ref}.")
        seen_refs.add(ref)
        kind = normalize_kind(str(item.get("kind") or item.get("name") or ""))
        placement_spec = resolve_placement_spec(kind)
        if placement_spec is None:
            errors.append(f"{ref} uses unsupported KiCad placement kind {kind!r}.")
            continue
        if not item.get("value") and not item.get("name") and kind != "GND":
            warnings.append(f"{ref}/{kind} has no value; placement catalog default will be used.")
        pins = item.get("pins")
        if pins is None:
            continue
        if not isinstance(pins, dict) or not pins:
            errors.append(f"{ref}/{kind} pins must be a non-empty map when provided.")
            continue
        if kind not in SUPPORTED_KINDS:
            warnings.append(f"{ref}/{kind} is placement-only for now; pin validation will wait for symbol support.")
            continue
        valid_pins = {pin.number for pin in KIND_SPECS[kind].pins}
        unknown_pins = sorted(str(pin) for pin in pins if str(pin) not in valid_pins)
        if unknown_pins:
            errors.append(f"{ref}/{kind} uses pins not present in the source-backed spec: {unknown_pins}.")

    return {
        "valid": not errors,
        "component_count": len(components),
        "errors": errors,
        "warnings": warnings,
        "source": "KIND_SPECS plus kicad.pipeline.placement_catalog.PLACER_COMPONENT_SPECS",
    }


def run(ctx: PipelineContext) -> StageResult:
    report = validate_placement_input(ctx.circuit)
    return StageResult(
        "placement_input_validator",
        ok=bool(report["valid"]),
        summary="Validated placer input against source-backed KiCad kind and pin specs.",
        data=report,
        warnings=list(report["warnings"]),
        errors=list(report["errors"]),
    )
