"""Write placer-only KiCad projects with embedded real KiCad symbols."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import (
    ROOT_UUID,
    SCH_VERSION,
    num,
    project_json,
    q,
    slugify,
    text_obj,
    uid,
    validate_schematic,
)
from kicad.source_pack.source_reference import load_reference

from .kicad_symbol_library import ResolvedKiCadSymbols, resolve_kicad_symbols
from .placement_catalog import CatalogPlacementPlan

PLACER_GENERATOR = "progen-kicad-placer-v0"
# A 12.7 mm stack pitch can put a power-unit pin inside the preceding gate for
# common 74xx/4xxx symbols.  This leaves no legal escape for a wire or local
# terminal label.  Keep every emitted unit on a conservative, KiCad-grid-aligned
# 25.4 mm pitch; wire geometry uses this same constant.
MULTI_UNIT_VERTICAL_PITCH_MM = 25.4


def _assert_fresh_output_dir(out_dir: Path) -> None:
    if not out_dir.exists():
        return
    if any(out_dir.iterdir()):
        raise FileExistsError(
            f"Refusing to overwrite existing generated KiCad project folder: {out_dir}. "
            "Create a new examples/placer_run_* folder for changed output."
        )


def _placement_lib_ids(placement: CatalogPlacementPlan) -> tuple[str, ...]:
    lib_ids: list[str] = []
    for component in placement.components:
        if not component.spec.lib_id:
            raise ValueError(f"No KiCad lib_id mapped for placement kind {component.kind}")
        lib_ids.append(component.spec.lib_id)
    return tuple(dict.fromkeys(lib_ids))


def _library_property(defaults: dict[str, str], name: str, fallback: str = "") -> str:
    value = defaults.get(name)
    return fallback if value is None else value


def _unit_position(component: Any, unit_index: int, unit_count: int) -> tuple[float, float]:
    x, y = component.at
    if unit_count <= 1:
        return x, y
    return x, round(y + unit_index * MULTI_UNIT_VERTICAL_PITCH_MM, 3)


def _symbol_instance(
    ref: str,
    project_name: str,
    component: Any,
    symbols: ResolvedKiCadSymbols,
    *,
    unit: int = 1,
    unit_index: int = 0,
    unit_count: int = 1,
) -> str:
    x, y = _unit_position(component, unit_index, unit_count)
    lib_id = component.spec.lib_id
    if not lib_id:
        raise ValueError(f"No KiCad lib_id mapped for placement kind {component.kind}")

    defaults = symbols.properties_for(lib_id)
    footprint = _library_property(defaults, "Footprint")
    datasheet = _library_property(defaults, "Datasheet", "~")
    su = uid(f"{project_name}:{ref}:{component.kind}:{component.name}:unit{unit}:{x}:{y}:{component.rotation}")
    lines = [
        f"  (symbol (lib_id {q(lib_id)}) (at {num(x)} {num(y)} {num(component.rotation)}) (unit {unit})\n",
        "    (in_bom yes) (on_board yes) (dnp no) (fields_autoplaced)\n",
        f"    (uuid {su})\n",
        f"    (property {q('Reference')} {q(ref)} (at {num(x + 4)} {num(y - 5)} 0) (effects (font (size 1.27 1.27)) (justify left)))\n",
        f"    (property {q('Value')} {q(component.name)} (at {num(x + 4)} {num(y + 5)} 0) (effects (font (size 1.27 1.27)) (justify left)))\n",
        f"    (property {q('Footprint')} {q(footprint)} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
        f"    (property {q('Datasheet')} {q(datasheet)} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
        f"    (property {q('Progen.Kind')} {q(component.kind)} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
        f"    (property {q('Progen.Category')} {q(component.spec.category)} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
        f"    (property {q('Progen.LibId')} {q(lib_id)} (at {num(x)} {num(y)} 0) (effects (font (size 1.27 1.27)) hide))\n",
    ]
    for pin_number in symbols.unit_pin_numbers_for(lib_id, unit):
        lines.append(f"    (pin {q(pin_number)} (uuid {uid(su + ':pin:' + pin_number)}))\n")
    lines.extend(
        [
            "    (instances\n",
            f"      (project {q(project_name)}\n",
            f"        (path {q('/' + ROOT_UUID)}\n",
            f"          (reference {q(ref)}) (unit {unit}) (value {q(component.name)}) (footprint {q(footprint)})\n",
            "        )\n",
            "      )\n",
            "    )\n",
            "  )\n",
        ]
    )
    return "".join(lines)


def _component_symbol_instances(ref: str, project_name: str, component: Any, symbols: ResolvedKiCadSymbols) -> str:
    lib_id = component.spec.lib_id
    if not lib_id:
        raise ValueError(f"No KiCad lib_id mapped for placement kind {component.kind}")
    units = symbols.units_for(lib_id)
    return "".join(
        _symbol_instance(
            ref,
            project_name,
            component,
            symbols,
            unit=unit,
            unit_index=index,
            unit_count=len(units),
        )
        for index, unit in enumerate(units)
    )


def _paper_declaration(placement: CatalogPlacementPlan, symbols: ResolvedKiCadSymbols) -> str:
    """Use a source-backed custom sheet when a dense design exceeds A3."""

    width = 420.0
    height = 297.0
    for component in placement.components:
        lib_id = component.spec.lib_id
        unit_count = len(symbols.units_for(lib_id)) if lib_id else 1
        x, y = component.at
        width = max(width, x + max(component.spec.width / 2, 12.7) + 50.8)
        height = max(
            height,
            y + (unit_count - 1) * MULTI_UNIT_VERTICAL_PITCH_MM + max(component.spec.height / 2, 12.7) + 50.8,
        )
    if width <= 420.0 and height <= 297.0:
        return '  (paper "A3")\n'
    return f'  (paper "User" {num(width)} {num(height)})\n'


def placement_schematic_text(
    project_name: str,
    circuit: dict[str, Any],
    placement: CatalogPlacementPlan,
    symbols: ResolvedKiCadSymbols,
    *,
    extra_schematic_objects: str = "",
    sheet_note: str | None = None,
) -> str:
    title = str(circuit.get("project", {}).get("title") or project_name)
    out = [
        f"(kicad_sch (version {SCH_VERSION}) (generator {q(PLACER_GENERATOR)}) (generator_version {q('v0.1')})\n",
        f"  (uuid {ROOT_UUID})\n",
        _paper_declaration(placement, symbols),
        "  (lib_symbols\n",
    ]
    for symbol in symbols.symbols:
        out.append(symbol.text)
    out.append("  )\n")
    out.append(text_obj(title, (20, 18), project_name, 1))
    out.append(
        text_obj(
            sheet_note
            or "Placement-only schematic: real KiCad library symbols are embedded; wires/simulation models come in later stages.",
            (20, 24),
            project_name,
            2,
        )
    )
    for component in placement.components:
        out.append(_component_symbol_instances(component.ref, project_name, component, symbols))
    if extra_schematic_objects:
        out.append(extra_schematic_objects)
    out.append("  (sheet_instances\n    (path \"/\" (page \"1\"))\n  )\n)\n")
    return "".join(out)


def write_placement_project(
    circuit: dict[str, Any],
    placement: CatalogPlacementPlan,
    out_dir: Path,
    *,
    clean: bool = True,
    project_suffix: str = "PLACER",
    mode: str = "placement_only",
    note: str | None = None,
    extra_schematic_objects: str = "",
    extra_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    name = slugify(circuit.get("project", {}).get("name", "placement_project"))
    project_name = f"OPEN_THIS_PROJECT__{name}__{project_suffix}"
    _assert_fresh_output_dir(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lib_ids = _placement_lib_ids(placement)
    symbols = resolve_kicad_symbols(lib_ids)
    schematic = placement_schematic_text(
        project_name,
        circuit,
        placement,
        symbols,
        extra_schematic_objects=extra_schematic_objects,
        sheet_note=(
            "Placement-only schematic: real KiCad library symbols are embedded; wires/simulation models come in later stages."
            if mode == "placement_only"
            else "Generated KiCad schematic: real KiCad library symbols are embedded; wires, labels, and junctions are generated by kicad_wire_maker."
        ),
    )
    checks = validate_schematic(schematic)
    checks["placement_only"] = mode == "placement_only"
    checks["placer_generator"] = PLACER_GENERATOR
    symbol_instance_count = schematic.count("\n  (symbol (lib_id")

    (out_dir / f"{project_name}.kicad_pro").write_text(project_json(project_name), encoding="utf-8")
    (out_dir / f"{project_name}.kicad_sch").write_text(schematic, encoding="utf-8")
    (out_dir / "input.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
    manifest = {
        "project_name": project_name,
        "open_this": f"{project_name}.kicad_pro",
        "schematic_file": f"{project_name}.kicad_sch",
        "component_count": len(placement.components),
        "symbol_instance_count": symbol_instance_count,
        "kinds": sorted({component.kind for component in placement.components}),
        "lib_ids": sorted(lib_ids),
        "symbol_sources": symbols.source_map(),
        "source_reference": load_reference().as_dict(),
        "placement": placement.as_dict(),
        "static_checks": checks,
        "mode": mode,
        "note": note
        or "This is an openable KiCad placement schematic using real embedded KiCad library symbols. Wires and simulation models are later stages.",
    }
    if extra_manifest:
        manifest.update(extra_manifest)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
