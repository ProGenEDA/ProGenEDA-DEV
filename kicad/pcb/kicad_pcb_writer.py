"""Source-backed KiCad `.kicad_pcb` writer."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import num, q, uid
from kicad.pipeline.kicad_symbol_library import _child_head, _direct_child_blocks

from .footprint_placer import PCBPlacement, PlacedFootprint
from .pcb_router import PCBRoutePlan
from .physical_design_compiler import PhysicalDesign


PCB_VERSION = 20260206
PCB_GENERATOR = "progen-kicad-pcb"


def _append_child_field(block: str, field: str) -> str:
    index = block.rfind(")")
    if index < 0:
        raise ValueError("Unbalanced KiCad footprint child")
    first_indent = re.match(r"\s*", block).group(0)
    child_indent = first_indent + "\t"
    return block[:index].rstrip() + f"\n{child_indent}{field}\n{first_indent}" + block[index:]


def _ensure_uuid(block: str, seed: str) -> str:
    if re.search(r"\(uuid\s+\"?[0-9a-fA-F-]+\"?\)", block):
        return block
    return _append_child_field(block, f'(uuid {q(uid(seed))})')


def _property_name(block: str) -> str:
    match = re.match(r'\s*\(property\s+"((?:\\.|[^\"])*)"', block, re.S)
    return bytes(match.group(1), "utf-8").decode("unicode_escape") if match else ""


def _replace_property_value(block: str, value: str) -> str:
    return re.sub(
        r'^(\s*\(property\s+"(?:\\.|[^\"])*"\s+)"(?:\\.|[^\"])*"',
        lambda match: match.group(1) + q(value),
        block,
        count=1,
        flags=re.S,
    )


def _hide_property(block: str) -> str:
    if re.search(r"\(hide\s+(?:yes|no)\)", block):
        return re.sub(r"\(hide\s+(?:yes|no)\)", "(hide yes)", block, count=1)
    return _append_child_field(block, "(hide yes)")


def _pad_number(block: str) -> str:
    match = re.match(r'\s*\(pad\s+"((?:\\.|[^\"])*)"', block, re.S)
    return bytes(match.group(1), "utf-8").decode("unicode_escape") if match else ""


def _embedded_footprint(
    placed: PlacedFootprint,
    *,
    project_name: str,
    schematic_file: str,
    net_codes: dict[str, int],
) -> str:
    component = placed.component
    text = component.footprint.source_text
    text = re.sub(
        r'^(\s*\(footprint\s+)"(?:\\.|[^\"])*"',
        lambda match: match.group(1) + q(component.footprint_id),
        text,
        count=1,
        flags=re.S,
    )
    insertion = (
        f'\n\t(uuid {q(uid(project_name + ":pcb:footprint:" + component.ref))})'
        f'\n\t(at {num(placed.at[0])} {num(placed.at[1])} {num(placed.rotation)})'
        f'\n\t(path {q("/" + uid(project_name + ":pcb:path:" + component.ref))})'
        '\n\t(sheetname "/")'
        f'\n\t(sheetfile {q(schematic_file)})'
    )
    layer_match = re.search(r'\n(\s*)\(layer\s+"F\.Cu"\)', text)
    if not layer_match:
        raise ValueError(f"Footprint source has no F.Cu layer: {component.footprint_id}")
    layer_end = layer_match.end()
    text = text[:layer_end] + insertion + text[layer_end:]

    uuid_heads = {
        "property",
        "fp_line",
        "fp_rect",
        "fp_arc",
        "fp_circle",
        "fp_poly",
        "fp_text",
        "fp_text_box",
        "pad",
        "zone",
    }
    for index, block in enumerate(_direct_child_blocks(text)):
        head = _child_head(block)
        updated = block
        if head == "property":
            name = _property_name(block)
            if name == "Reference":
                updated = _replace_property_value(updated, component.ref)
                updated = _hide_property(updated)
            elif name == "Value":
                updated = _replace_property_value(updated, component.value)
        if head == "pad":
            pad = _pad_number(block)
            net = component.pad_nets.get(pad)
            if net:
                updated = _append_child_field(updated, f'(net {net_codes[net]} {q(net)})')
        if head in uuid_heads:
            updated = _ensure_uuid(updated, f"{project_name}:pcb:{component.ref}:{head}:{index}")
        if updated != block:
            text = text.replace(block, updated, 1)
    return text


def _layers() -> str:
    return """\t(layers
\t\t(0 "F.Cu" signal)
\t\t(2 "B.Cu" signal)
\t\t(9 "F.Adhes" user "F.Adhesive")
\t\t(11 "B.Adhes" user "B.Adhesive")
\t\t(13 "F.Paste" user)
\t\t(15 "B.Paste" user)
\t\t(5 "F.SilkS" user "F.Silkscreen")
\t\t(7 "B.SilkS" user "B.Silkscreen")
\t\t(1 "F.Mask" user)
\t\t(3 "B.Mask" user)
\t\t(17 "Dwgs.User" user "User.Drawings")
\t\t(19 "Cmts.User" user "User.Comments")
\t\t(21 "Eco1.User" user "User.Eco1")
\t\t(23 "Eco2.User" user "User.Eco2")
\t\t(25 "Edge.Cuts" user)
\t\t(27 "Margin" user)
\t\t(31 "F.CrtYd" user "F.Courtyard")
\t\t(29 "B.CrtYd" user "B.Courtyard")
\t\t(35 "F.Fab" user)
\t\t(33 "B.Fab" user)
\t)\n"""


def pcb_text(
    project_name: str,
    design: PhysicalDesign,
    placement: PCBPlacement,
    route_plan: PCBRoutePlan,
    *,
    schematic_file: str,
) -> str:
    net_names = sorted(design.nets)
    net_codes = {name: index for index, name in enumerate(net_names, 1)}
    out = [
        "(kicad_pcb\n",
        f"\t(version {PCB_VERSION})\n",
        f"\t(generator {q(PCB_GENERATOR)})\n",
        '\t(generator_version "v0.1")\n',
        "\t(general\n\t\t(thickness 1.6)\n\t\t(legacy_teardrops no)\n\t)\n",
        '\t(paper "A4")\n',
        _layers(),
        "\t(setup\n\t\t(pad_to_mask_clearance 0)\n\t\t(allow_soldermask_bridges_in_footprints no)\n\t)\n",
        '\t(net 0 "")\n',
    ]
    out.extend(f"\t(net {net_codes[name]} {q(name)})\n" for name in net_names)
    for placed in placement.footprints:
        out.append(
            _embedded_footprint(
                placed,
                project_name=project_name,
                schematic_file=schematic_file,
                net_codes=net_codes,
            )
        )
    left, top, right, bottom = placement.board_bounds
    out.append(
        "\t(gr_rect\n"
        f"\t\t(start {num(left)} {num(top)})\n"
        f"\t\t(end {num(right)} {num(bottom)})\n"
        "\t\t(stroke (width 0.05) (type default))\n"
        "\t\t(fill none)\n"
        '\t\t(layer "Edge.Cuts")\n'
        f"\t\t(uuid {q(uid(project_name + ':pcb:outline'))})\n"
        "\t)\n"
    )
    for index, segment in enumerate(route_plan.segments):
        net = str(segment["net"])
        start = segment["start"]
        end = segment["end"]
        out.append(
            "\t(segment\n"
            f"\t\t(start {num(start[0])} {num(start[1])})\n"
            f"\t\t(end {num(end[0])} {num(end[1])})\n"
            f"\t\t(width {num(segment.get('width', route_plan.track_width))})\n"
            f"\t\t(layer {q(str(segment['layer']))})\n"
            f"\t\t(net {net_codes[net]})\n"
            f"\t\t(uuid {q(uid(project_name + ':pcb:segment:' + str(index)))})\n"
            "\t)\n"
        )
    for index, via in enumerate(route_plan.vias):
        net = str(via["net"])
        at = via["at"]
        out.append(
            "\t(via\n"
            f"\t\t(at {num(at[0])} {num(at[1])})\n"
            f"\t\t(size {num(route_plan.via_size)})\n"
            f"\t\t(drill {num(route_plan.via_drill)})\n"
            '\t\t(layers "F.Cu" "B.Cu")\n'
            f"\t\t(net {net_codes[net]})\n"
            f"\t\t(uuid {q(uid(project_name + ':pcb:via:' + str(index)))})\n"
            "\t)\n"
        )
    out.append("\t(embedded_fonts no)\n)\n")
    return "".join(out)


def write_kicad_pcb(
    project_dir: Path,
    project_name: str,
    design: PhysicalDesign,
    placement: PCBPlacement,
    route_plan: PCBRoutePlan,
    *,
    schematic_file: str,
) -> Path:
    output = project_dir / f"{project_name}.kicad_pcb"
    output.write_text(
        pcb_text(project_name, design, placement, route_plan, schematic_file=schematic_file),
        encoding="utf-8",
    )
    return output
