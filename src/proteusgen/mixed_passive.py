"""Locked mixed resistor/capacitor terminal generator.

This module promotes the user-accepted mixed passive method into main code for
the current scope. It packs from E001 and uses donor records only as schemas:

- resistor records from the V9 resistor donor
- capacitor records from the manual two-terminal-capacitor donor
- one power bridge from the locked power-terminal donor
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mixed_passive_ir import (
    MixedPassiveCircuitIR,
    MixedPassiveComponent,
    MixedPassiveValidationReport,
    parse_mixed_passive_ir,
    validate_mixed_passive_circuit,
    visible_capacitor_value,
)
from .pdsprj import read_internal_file, write_project_from_parts
from .resistor_ir import ComponentPosition, resistor_orientation_angle, visible_resistor_value
from . import resistor_v9 as rv9
from .templates import FixtureRegistry
from .versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

IN_SIZE = 103
OUT_SIZE = 104
CAP_SIZE = 366
WIRE_SIZE = 50
TRIMMED_WIRE_SIZE = 49
SAFE_X_SPACING = 2540000
SAFE_Y_SPACING = 2540000
CAP_PROP_TEXT = b"{PRIMITIVE=ANALOGUE,CAPACITOR}\n\n{PACKAGE=CAP10}\n\n\x00"


@dataclass(frozen=True)
class MixedPassiveGenerationResult:
    output_path: Path
    cdb_path: Path
    dsn_path: Path
    manifest_path: Path
    readme_path: Path
    version_path: Path
    manifest: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "root_cdb_path": str(self.cdb_path),
            "root_dsn_path": str(self.dsn_path),
            "manifest_path": str(self.manifest_path),
            "readme_path": str(self.readme_path),
            "generator_version_path": str(self.version_path),
            "static_validation_issues": self.manifest["static_validation_issues"],
            "output_hashes": self.manifest["output_hashes"],
        }


class MixedPassiveGenerationBlocked(Exception):
    def __init__(self, report: MixedPassiveValidationReport) -> None:
        super().__init__("Mixed passive CircuitIR cannot be emitted.")
        self.report = report


@dataclass(frozen=True)
class ManualCapTemplates:
    header: bytes
    outputs: tuple[bytes, bytes]
    inputs: tuple[bytes, bytes]
    caps: tuple[bytes, bytes]
    wire_lefts: tuple[bytes, bytes]
    wire_rights: tuple[bytes, bytes]
    donor_chunk: bytes


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _s32(data: bytes, offset: int) -> int:
    return struct.unpack("<i", data[offset : offset + 4])[0]


def _i32(value: int) -> bytes:
    return struct.pack("<i", value)


def _u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _u16(value: int) -> bytes:
    return struct.pack("<H", value)


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def _load_manual_cap_templates(manual_project: Path) -> ManualCapTemplates:
    donor_chunk = rv9._extract_object_chunk(read_internal_file(manual_project, "ROOT.DSN"))
    expected_len = (
        1
        + 2 * OUT_SIZE
        + IN_SIZE
        + CAP_SIZE
        + WIRE_SIZE
        + TRIMMED_WIRE_SIZE
        + IN_SIZE
        + CAP_SIZE
        + WIRE_SIZE
        + WIRE_SIZE
    )
    if len(donor_chunk) != expected_len:
        raise RuntimeError(f"Manual capacitor donor object chunk length {len(donor_chunk)} != {expected_len}.")
    cursor = 0
    header = donor_chunk[cursor : cursor + 1]
    cursor += 1
    outputs = (donor_chunk[cursor : cursor + OUT_SIZE], donor_chunk[cursor + OUT_SIZE : cursor + 2 * OUT_SIZE])
    cursor += 2 * OUT_SIZE
    input_1 = donor_chunk[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    cap_1 = donor_chunk[cursor : cursor + CAP_SIZE]
    cursor += CAP_SIZE
    wire_left_1 = donor_chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    wire_right_1 = donor_chunk[cursor : cursor + TRIMMED_WIRE_SIZE] + b"\x00"
    cursor += TRIMMED_WIRE_SIZE
    input_2 = donor_chunk[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    cap_2 = donor_chunk[cursor : cursor + CAP_SIZE]
    cursor += CAP_SIZE
    wire_left_2 = donor_chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    wire_right_2 = donor_chunk[cursor : cursor + WIRE_SIZE]
    if header != b"\x00" or donor_chunk[-1] != 0xFF:
        raise RuntimeError("Manual capacitor donor object stream has unexpected boundary bytes.")
    return ManualCapTemplates(
        header=header,
        outputs=outputs,
        inputs=(input_1, input_2),
        caps=(cap_1, cap_2),
        wire_lefts=(wire_left_1, wire_left_2),
        wire_rights=(wire_right_1, wire_right_2),
        donor_chunk=donor_chunk,
    )


def _manual_cap_suffixes(index: int) -> tuple[int, int]:
    step = 0x0238
    return (0x011A + (index - 1) * step) & 0xFFFF, (0x00E8 + (index - 1) * step) & 0xFFFF


def _patch_i32(record: bytearray, offset: int, value: int) -> None:
    record[offset : offset + 4] = _i32(value)


def _patch_cap_input(template: bytes, label: str, dx: int, dy: int, in_suffix: int) -> bytes:
    record = bytearray(template)
    for offset in (1, 33):
        _patch_i32(record, offset, _s32(template, offset) + dx)
    for offset in (5, 37):
        _patch_i32(record, offset, _s32(template, offset) + dy)
    record[30] = 2
    record[31:33] = label.encode("ascii")
    record[-4:-2] = _u16(in_suffix)
    record[-2] = 0x01
    record[-1] = 0x00
    return bytes(record)


def _patch_cap_output(template: bytes, label: str, dx: int, dy: int, out_suffix: int, marker: bytes) -> bytes:
    record = bytearray(template)
    for offset in (1, 34):
        _patch_i32(record, offset, _s32(template, offset) + dx)
    for offset in (5, 38):
        _patch_i32(record, offset, _s32(template, offset) + dy)
    if marker == b"$TERGROUND":
        marker_pos = record.find(b"$TEROUTPUT")
        if marker_pos < 0:
            raise RuntimeError("Capacitor output template marker not found.")
        record[marker_pos : marker_pos + len(b"$TERGROUND")] = b"$TERGROUND"
    record[31] = 2
    record[32:34] = label.encode("ascii")
    record[-4:-2] = _u16(out_suffix)
    record[-2] = 0x01
    record[-1] = 0x00
    return bytes(record)


def _patch_cap_record(
    template: bytes,
    component: MixedPassiveComponent,
    visible_value: str,
    x: int,
    y: int,
    index: int,
    in_suffix: int,
    out_suffix: int,
) -> bytes:
    record = bytearray(template)
    record[2] = 2
    record[3:5] = component.ref.encode("ascii")
    record[70] = 3
    record[71:74] = visible_value.encode("ascii")
    dx = x - _s32(template, 332)
    dy = y - _s32(template, 336)
    for offset in (5, 74, 146, 260, 332):
        _patch_i32(record, offset, _s32(template, offset) + dx)
    for offset in (9, 78, 150, 264, 336):
        _patch_i32(record, offset, _s32(template, offset) + dy)
    record[344] = index
    record[357:359] = _u16(out_suffix)
    record[359:361] = b"\x01\x00"
    record[361:363] = _u16(in_suffix)
    record[363:365] = b"\x01\x00"
    record[-1] = 0x00
    return bytes(record)


def _patch_cap_wire(template: bytes, dx: int, dy: int, final: bool) -> bytes:
    record = bytearray(template)
    for offset in (33, 41):
        _patch_i32(record, offset, _s32(template, offset) + dx)
    for offset in (37, 45):
        _patch_i32(record, offset, _s32(template, offset) + dy)
    record[-1] = 0xFF if final else 0x00
    return bytes(record)


def _stretch_axis(values: list[int], min_spacing: int, *, descending: bool = False) -> dict[int, int]:
    unique = sorted(set(values), reverse=descending)
    if len(unique) < 2:
        return {value: value for value in unique}
    ordered = sorted(unique)
    if all(b - a >= min_spacing for a, b in zip(ordered, ordered[1:])):
        return {value: value for value in unique}
    anchor = unique[0]
    return {value: anchor - index * min_spacing if descending else anchor + index * min_spacing for index, value in enumerate(unique)}


def _safe_component_positions(ir: MixedPassiveCircuitIR) -> tuple[dict[str, ComponentPosition], int]:
    raw_positions = ir.layout.component_positions
    if not raw_positions:
        return {}, 0
    x_map = _stretch_axis([position.x for position in raw_positions.values()], SAFE_X_SPACING)
    y_map = _stretch_axis([position.y for position in raw_positions.values()], SAFE_Y_SPACING, descending=True)
    safe: dict[str, ComponentPosition] = {}
    used: set[tuple[int, int]] = set()
    adjusted = 0
    for ref, position in raw_positions.items():
        x = x_map[position.x]
        y = y_map[position.y]
        while (x, y) in used:
            x += SAFE_X_SPACING
        used.add((x, y))
        next_position = ComponentPosition(x=x, y=y)
        safe[ref] = next_position
        if next_position != position:
            adjusted += 1
    return safe, adjusted


def _position_for(
    ir: MixedPassiveCircuitIR,
    component: MixedPassiveComponent,
    index: int,
    positions: dict[str, ComponentPosition],
) -> tuple[int, int, bool]:
    position = positions.get(component.ref)
    if position is not None:
        return position.x, position.y, False
    visual = component.visual
    if isinstance(visual.get("col"), int) and isinstance(visual.get("row"), int):
        return -6350000 + int(visual["col"]) * SAFE_X_SPACING, 5080000 - int(visual["row"]) * SAFE_Y_SPACING, True
    col = (index - 1) % 7
    row = (index - 1) // 7
    return -6350000 + col * SAFE_X_SPACING, 5080000 - row * SAFE_Y_SPACING, True


def _power_nodes(ir: MixedPassiveCircuitIR) -> list[str]:
    out: list[str] = []
    for node in ir.nodes:
        if node.kind == "power" or node.id == "V0":
            out.append(node.id)
    return list(dict.fromkeys(out))


def _ground_nodes(ir: MixedPassiveCircuitIR) -> set[str]:
    return {node.id for node in ir.nodes if node.kind == "ground" or node.id == "G0"}


def build_cdb(components: tuple[MixedPassiveComponent, ...]) -> bytes:
    out = bytearray()
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + _enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + _enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + _enc_str("Master Sheet") + _u32(10) + _u32(0)
    out += _u32(len(components))
    for index, component in enumerate(components, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(index) + _enc_str(component.ref)
        if component.type == "CAPACITOR":
            out += _u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += _u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += _u32(0) + _u32(index) + _u32(0)
    out += _u32(1) + _u32(1) + b"\x00" + _enc_str("") + _u32(1)
    out += _u32(len(components))
    for index, component in enumerate(components, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        if component.type == "CAPACITOR":
            out += _enc_str(component.ref) + _enc_str(component.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(CAP_PROP_TEXT)
        else:
            out += _enc_str(component.ref) + _enc_str(component.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += _u32(0)
    return bytes(out)


def _build_resistor_records(
    component: MixedPassiveComponent,
    *,
    ordinal: int,
    x: int,
    y: int,
    templates: rv9.V9Templates,
    ground_nodes: set[str],
) -> tuple[bytes, bytes, list[bytes], dict[str, Any]]:
    left, right = component.nodes
    angle_tenths = resistor_orientation_angle(component.visual)
    ux, uy = rv9._direction_for_angle(angle_tenths)
    left_pin_x, left_pin_y = x, y
    right_pin_x, right_pin_y = x + ux * 1270000, y + uy * 1270000
    in_symbol_x, in_symbol_y = left_pin_x - ux * 508000, left_pin_y - uy * 508000
    out_symbol_x, out_symbol_y = right_pin_x + ux * 508000, right_pin_y + uy * 508000
    in_label_x, in_label_y = left_pin_x - ux * 889000, left_pin_y - uy * 889000
    out_label_x, out_label_y = right_pin_x + ux * 889000, right_pin_y + uy * 889000
    in_tip_x, in_tip_y = left_pin_x - ux * 254000, left_pin_y - uy * 254000
    out_tip_x, out_tip_y = right_pin_x + ux * 254000, right_pin_y + uy * 254000
    output_marker = b"$TERGROUND" if right in ground_nodes else b"$TEROUTPUT"
    input_record, in_suffix = rv9._patch_input(
        templates.input_terminals[(ordinal - 1) % 4],
        left,
        in_symbol_x,
        in_symbol_y,
        in_label_x,
        in_label_y,
        ordinal,
        marker=b"$TERINPUT",
    )
    output_record, out_suffix = rv9._patch_output(
        templates.output_terminals[(ordinal - 1) % 4],
        right,
        out_symbol_x,
        out_symbol_y,
        out_label_x,
        out_label_y,
        ordinal,
        marker=output_marker,
    )
    res_template, wire_left_template, wire_right_template = templates.groups[(ordinal - 1) % 4]
    visible_value = visible_resistor_value(component.value, component.visual)
    group = [
        rv9._patch_resistor(res_template, ordinal, component.ref, visible_value, x, y, angle_tenths, in_suffix, out_suffix),
        rv9._patch_wire(wire_left_template, in_tip_x, in_tip_y, left_pin_x, left_pin_y),
        rv9._patch_wire(wire_right_template, out_tip_x, out_tip_y, right_pin_x, right_pin_y),
    ]
    return input_record, output_record, group, {
        "ref": component.ref,
        "kind": component.type,
        "value": component.value,
        "visible_value": visible_value,
        "left": left,
        "right": right,
        "input_marker": "$TERINPUT",
        "output_marker": output_marker.decode("ascii"),
        "in_suffix": f"{in_suffix:04x}",
        "out_suffix": f"{out_suffix:04x}",
        "angle_tenths": angle_tenths,
        "x": x,
        "y": y,
    }


def _build_capacitor_records(
    component: MixedPassiveComponent,
    *,
    ordinal: int,
    x: int,
    y: int,
    templates: ManualCapTemplates,
    ground_nodes: set[str],
) -> tuple[bytes, list[bytes], dict[str, Any]]:
    template_index = (ordinal - 1) % 2
    in_suffix, out_suffix = _manual_cap_suffixes(ordinal)
    cap_template = templates.caps[template_index]
    dx = x - _s32(cap_template, 332)
    dy = y - _s32(cap_template, 336)
    left, right = component.nodes
    output_marker = b"$TERGROUND" if right in ground_nodes else b"$TEROUTPUT"
    visible_value = visible_capacitor_value(component.value, component.visual)
    output_record = _patch_cap_output(templates.outputs[template_index], right, dx, dy, out_suffix, output_marker)
    right_wire = _patch_cap_wire(templates.wire_rights[template_index], dx, dy, final=False)[:-1]
    group = [
        _patch_cap_input(templates.inputs[template_index], left, dx, dy, in_suffix),
        _patch_cap_record(cap_template, component, visible_value, x, y, ordinal, in_suffix, out_suffix),
        _patch_cap_wire(templates.wire_lefts[template_index], dx, dy, final=False),
        right_wire,
    ]
    return output_record, group, {
        "ref": component.ref,
        "kind": component.type,
        "value": component.value,
        "visible_value": visible_value,
        "left": left,
        "right": right,
        "input_marker": "$TERINPUT",
        "output_marker": output_marker.decode("ascii"),
        "in_suffix": f"{in_suffix:04x}",
        "out_suffix": f"{out_suffix:04x}",
        "cap_visual_index_byte_344": ordinal,
        "wire_right_len": len(right_wire),
        "x": x,
        "y": y,
    }


def build_object_chunk(
    ir: MixedPassiveCircuitIR,
    *,
    cap_templates: ManualCapTemplates,
    res_templates: rv9.V9Templates,
    bridge_dsn: bytes,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    power_nodes = _power_nodes(ir)
    if len(power_nodes) > 1:
        raise ValueError("The locked mixed passive method supports one distinct power node per generated project.")
    bridge_cores = [rv9._load_power_bridge_core(bridge_dsn, node_id) for node_id in power_nodes]
    ground_nodes = _ground_nodes(ir)
    safe_positions, layout_adjusted_count = _safe_component_positions(ir)
    cap_outputs: list[bytes] = []
    cap_groups: list[bytes] = []
    res_inputs: list[bytes] = []
    res_outputs: list[bytes] = []
    res_groups: list[bytes] = []
    topology: list[dict[str, Any]] = []
    cap_ordinal = 0
    res_ordinal = 0
    auto_placed = 0
    ground_terminal_count = 0

    for index, component in enumerate(ir.components, start=1):
        x, y, was_auto_placed = _position_for(ir, component, index, safe_positions)
        auto_placed += int(was_auto_placed)
        if component.type == "CAPACITOR":
            cap_ordinal += 1
            output_record, group, info = _build_capacitor_records(
                component,
                ordinal=cap_ordinal,
                x=x,
                y=y,
                templates=cap_templates,
                ground_nodes=ground_nodes,
            )
            cap_outputs.append(output_record)
            cap_groups.extend(group)
        else:
            res_ordinal += 1
            input_record, output_record, group, info = _build_resistor_records(
                component,
                ordinal=res_ordinal,
                x=x,
                y=y,
                templates=res_templates,
                ground_nodes=ground_nodes,
            )
            res_inputs.append(input_record)
            res_outputs.append(output_record)
            res_groups.extend(group)
        info["idx"] = index
        info["ordinal"] = cap_ordinal if component.type == "CAPACITOR" else res_ordinal
        topology.append(info)
        if info["output_marker"] == "$TERGROUND":
            ground_terminal_count += 1

    chunk = bytearray(
        cap_templates.header
        + b"".join(bridge_cores)
        + b"".join(cap_outputs)
        + b"".join(cap_groups)
        + b"".join(res_inputs)
        + b"".join(res_outputs)
        + res_templates.separator
        + b"".join(res_groups)
    )
    chunk[-1] = 0xFF
    counts = {
        "power_bridge_count": len(bridge_cores),
        "power_nodes": power_nodes,
        "resistor_count": res_ordinal,
        "capacitor_count": cap_ordinal,
        "ground_terminal_count": ground_terminal_count,
        "auto_placed": auto_placed,
        "layout_adjusted_count": layout_adjusted_count,
        "visual_wire_count": 0,
        "visual_wire_skipped_count": len(ir.layout.visual_wires),
    }
    return bytes(chunk), topology, counts


def validate_object_chunk(chunk: bytes, topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    resistor_count = counts["resistor_count"]
    capacitor_count = counts["capacitor_count"]
    bridge_count = counts["power_bridge_count"]
    ground_count = counts["ground_terminal_count"]
    expected_len = (
        1
        + bridge_count * rv9.POWER_BRIDGE_CORE_SIZE
        + capacitor_count * OUT_SIZE
        + capacitor_count * (IN_SIZE + CAP_SIZE + WIRE_SIZE + TRIMMED_WIRE_SIZE)
        + resistor_count * rv9.IN_SIZE
        + resistor_count * rv9.OUT_SIZE
        + len(b"\x00")
        + resistor_count * rv9.GROUP_SIZE
    )
    if len(chunk) != expected_len:
        issues.append(f"object chunk length {len(chunk)} != {expected_len}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    expected_counts = {
        "$TERPOWER": bridge_count,
        "$TEROUTPUT": len(topology) - ground_count + bridge_count,
        "$TERGROUND": ground_count,
        "$TERINPUT": len(topology),
        "CAPACITOR": capacitor_count,
        "CAP10": capacitor_count,
        "COMPONENT ID": len(topology),
        "WIRE": len(topology) * 2 + bridge_count,
    }
    for marker, expected in expected_counts.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected:
            issues.append(f"{marker} count {actual} != {expected}")
    for index in range(bridge_count):
        bridge_end = 1 + (index + 1) * rv9.POWER_BRIDGE_CORE_SIZE - 1
        if chunk[bridge_end] != 0:
            issues.append(f"power bridge {index + 1} terminator {chunk[bridge_end]:02x}")
    for item in topology:
        if item["kind"] == "CAPACITOR" and item["wire_right_len"] != TRIMMED_WIRE_SIZE:
            issues.append(f"{item['ref']} capacitor right wire len {item['wire_right_len']} != {TRIMMED_WIRE_SIZE}")
    return issues


def generate_mixed_passive_project(
    ir: MixedPassiveCircuitIR,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> MixedPassiveGenerationResult:
    registry = registry or FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {', '.join(failed_hashes)}")
    report = validate_mixed_passive_circuit(ir)
    if not report.valid:
        raise MixedPassiveGenerationBlocked(report)

    base = registry.get("e001_empty")
    cap_donor = registry.get("cap2_with_terminals_manual")
    resistor_donor = registry.get("r21_v9_resistor_terminal_donor")
    bridge_donor = registry.get("power_terminal_bridge_donor")
    cap_templates = _load_manual_cap_templates(cap_donor.path)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor.path, "ROOT.DSN"), resistor_donor.path)
    bridge_dsn = read_internal_file(bridge_donor.path, "ROOT.DSN")
    object_chunk, topology, generation_counts = build_object_chunk(
        ir,
        cap_templates=cap_templates,
        res_templates=res_templates,
        bridge_dsn=bridge_dsn,
    )
    cdb = build_cdb(ir.components)
    dsn, section_pointers = rv9.build_dsn(read_internal_file(base.path, "ROOT.DSN"), read_internal_file(resistor_donor.path, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    chunk_issues = validate_object_chunk(rv9._extract_object_chunk(dsn), topology, generation_counts)

    output_dir = Path(outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    basename = ir.project.output_basename
    output_path = output_dir / f"{basename}.pdsprj"
    cdb_path = output_dir / f"{basename}.ROOT.CDB.bin"
    dsn_path = output_dir / f"{basename}.ROOT.DSN.bin"
    manifest_path = output_dir / "manifest.json"
    readme_path = output_dir / "README_TEST_FIRST.txt"
    version_path = output_dir / "generator_version.txt"

    write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    version_path.write_text(
        "proteusgen mixed_passive locked method\n"
        "base_fixture=e001_empty\n"
        "resistor_donor_fixture=r21_v9_resistor_terminal_donor\n"
        "capacitor_donor_fixture=cap2_with_terminals_manual\n"
        "power_bridge_fixture=power_terminal_bridge_donor\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": ir.schema_version,
        "generator_target": ir.generator_target,
        "project_name": ir.project.name,
        "output_basename": basename,
        "base_project": "E001_EMPTY_BASE",
        "base_fixture_id": base.id,
        "resistor_donor_fixture_id": resistor_donor.id,
        "capacitor_donor_fixture_id": cap_donor.id,
        "power_bridge_fixture_id": bridge_donor.id,
        "component_count_requested": len(ir.components),
        "component_count_emitted_cdb": len(ir.components),
        "component_count_emitted_dsn": len(ir.components),
        "resistor_count": generation_counts["resistor_count"],
        "capacitor_count": generation_counts["capacitor_count"],
        "node_count_requested": len(ir.nodes),
        "power_bridge_count": generation_counts["power_bridge_count"],
        "power_nodes": generation_counts["power_nodes"],
        "ground_terminal_count": generation_counts["ground_terminal_count"],
        "terminal_count": len(ir.components) * 2 + generation_counts["power_bridge_count"] * 2,
        "wire_count": len(ir.components) * 2 + generation_counts["power_bridge_count"],
        "bridge_wire_count": generation_counts["power_bridge_count"],
        "short_wire_count": len(ir.components) * 2,
        "visual_wire_count": generation_counts["visual_wire_count"],
        "visual_wire_skipped_count": generation_counts["visual_wire_skipped_count"],
        "auto_placed_count": generation_counts["auto_placed"],
        "layout_adjusted_count": generation_counts["layout_adjusted_count"],
        "safe_spacing": {"x": SAFE_X_SPACING, "y": SAFE_Y_SPACING},
        "object_order": "header, power bridge, capacitor output array, capacitor groups, resistor input array, resistor output array, separator, resistor groups",
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "section_pointer_values": section_pointers,
        "static_validation_issues": chunk_issues,
        "topology": topology,
        "known_limitations": [
            "Two-character node and component labels only.",
            "Power support emits one donor-derived $TERPOWER -> $TEROUTPUT bridge for one power node.",
            "Ground terminals are supported only on right endpoints.",
            "Standalone layout.visual_wires are intentionally skipped until VGDVC-safe records are validated.",
        ],
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, manifest_path.name, readme_path.name, version_path.name],
        "output_hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            "base_project": _sha256_file(base.path),
            "resistor_donor_project": _sha256_file(resistor_donor.path),
            "capacitor_donor_project": _sha256_file(cap_donor.path),
            "power_bridge_donor": _sha256_file(bridge_donor.path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        f"{basename}\n\n"
        "Open this generated mixed resistor/capacitor project in Proteus 8.13.\n\n"
        f"Project: {output_path.name}\n"
        f"Components: {len(ir.components)} ({generation_counts['resistor_count']} resistors, {generation_counts['capacitor_count']} capacitors)\n"
        f"Static validation issues: {chunk_issues}\n\n"
        "Locked endpoint rules:\n"
        "- V0/power nodes use one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge.\n"
        "- Powered component endpoints remain normal $TERINPUT(V0) terminals.\n"
        "- G0/ground nodes on component.nodes[1] become $TERGROUND endpoints.\n"
        "- Dense or duplicate manual positions are stretched to the safe grid.\n",
        encoding="utf-8",
    )
    return MixedPassiveGenerationResult(output_path, cdb_path, dsn_path, manifest_path, readme_path, version_path, manifest)


def generate_mixed_passive_project_from_payload(
    payload: Any,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> MixedPassiveGenerationResult:
    ir, issues = parse_mixed_passive_ir(payload)
    if issues:
        raise MixedPassiveGenerationBlocked(MixedPassiveValidationReport(errors=tuple(issues), warnings=(), circuit=None))
    assert ir is not None
    return generate_mixed_passive_project(ir, outdir, registry=registry)


def validate_mixed_passive_json_file(path: str | Path) -> MixedPassiveValidationReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    ir, issues = parse_mixed_passive_ir(payload)
    if issues:
        return MixedPassiveValidationReport(errors=tuple(issues), warnings=(), circuit=None)
    assert ir is not None
    return validate_mixed_passive_circuit(ir)
