"""Locked V9 resistor-terminal Proteus project generator.

This module implements the user-confirmed V9 method recorded in the
`memory` repository. It always packs from the clean E001 project and uses
the R21 V9 project only as a byte-record donor.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .circuit_ir import Issue
from .layout import (
    LayoutError,
    LayoutPlan,
    actual_layout_plan,
    apply_layout_to_payload,
    plan_with_actual_positions,
)
from .pdsprj import read_internal_file, write_project_from_parts
from .resistor_ir import (
    ComponentPosition,
    ResistorCircuitIR,
    ResistorComponent,
    ResistorValidationReport,
    parse_resistor_ir,
    resistor_orientation_angle,
    validate_resistor_circuit,
    validate_resistor_payload,
    visible_resistor_value,
)
from .templates import FixtureRegistry
from .versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

IN_SIZE = 103
OUT_SIZE = 104
RES_SIZE = 346
WIRE_SIZE = 50
GROUP_SIZE = RES_SIZE + WIRE_SIZE + WIRE_SIZE
POWER_BRIDGE_CORE_SIZE = 255
SAFE_X_SPACING = 2540000
SAFE_Y_SPACING = 2540000
PROP_TEXT = b"{PRIMITIVE=ANALOGUE}\n\x00"


@dataclass(frozen=True)
class ResistorGenerationResult:
    output_path: Path
    cdb_path: Path
    dsn_path: Path
    layout_path: Path
    manifest_path: Path
    readme_path: Path
    version_path: Path
    manifest: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "root_cdb_path": str(self.cdb_path),
            "root_dsn_path": str(self.dsn_path),
            "layout_plan_path": str(self.layout_path),
            "manifest_path": str(self.manifest_path),
            "readme_path": str(self.readme_path),
            "generator_version_path": str(self.version_path),
            "static_validation_issues": self.manifest["static_validation_issues"],
            "output_hashes": self.manifest["output_hashes"],
        }


class ResistorGenerationBlocked(Exception):
    def __init__(self, report: ResistorValidationReport) -> None:
        super().__init__("Resistor CircuitIR cannot be emitted.")
        self.report = report


@dataclass(frozen=True)
class V9Templates:
    donor_path: Path
    header: bytes
    input_terminals: tuple[bytes, ...]
    output_terminals: tuple[bytes, ...]
    separator: bytes
    groups: tuple[tuple[bytes, bytes, bytes], ...]


def _u32(value: int) -> bytes:
    return struct.pack("<I", value)


def _i32(value: int) -> bytes:
    return struct.pack("<i", value)


def _u16(value: int) -> bytes:
    return struct.pack("<H", value)


def _angle_tenths(value: int) -> bytes:
    return _u16(value & 0xFFFF) + b"\x00\x00"


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _extract_object_chunk(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    obj = dsn.find(b"OBJECT DATA", first)
    second = dsn.find(b"ISIS CIRCUIT FILE", first + 1)
    if first < 0 or obj < 0 or second < 0:
        raise ValueError("ROOT.DSN does not contain the expected V9 object data sections.")
    return dsn[obj + len(b"OBJECT DATA") : second]


def _load_templates(donor_dsn: bytes, donor_path: Path) -> V9Templates:
    chunk = _extract_object_chunk(donor_dsn)
    donor_count = chunk.count(b"$TERINPUT") + chunk.count(b"$TERPOWER")
    if donor_count < 4:
        raise ValueError("V9 donor must contain at least four terminal/resistor groups.")
    header = chunk[:1]
    if header != b"\x00":
        raise ValueError("V9 donor object chunk does not start with object-data prefix 00.")
    inputs_start = 1
    outputs_start = inputs_start + donor_count * IN_SIZE
    separator_offset = outputs_start + donor_count * OUT_SIZE
    groups_start = separator_offset + 1
    separator = chunk[separator_offset:groups_start]
    if separator != b"\x00":
        raise ValueError("V9 donor object chunk separator is not 00.")
    inputs = tuple(chunk[inputs_start + i * IN_SIZE : inputs_start + (i + 1) * IN_SIZE] for i in range(4))
    outputs = tuple(chunk[outputs_start + i * OUT_SIZE : outputs_start + (i + 1) * OUT_SIZE] for i in range(4))
    groups: list[tuple[bytes, bytes, bytes]] = []
    for i in range(4):
        base = groups_start + i * GROUP_SIZE
        groups.append(
            (
                chunk[base : base + RES_SIZE],
                chunk[base + RES_SIZE : base + RES_SIZE + WIRE_SIZE],
                chunk[base + RES_SIZE + WIRE_SIZE : base + GROUP_SIZE],
            )
        )
    return V9Templates(
        donor_path=donor_path,
        header=header,
        input_terminals=inputs,
        output_terminals=outputs,
        separator=separator,
        groups=tuple(groups),
    )


def _load_power_bridge_core(bridge_dsn: bytes, power_node: str) -> bytes:
    if len(power_node.encode("ascii")) != 2:
        raise ValueError("Power bridge node labels must be exactly two ASCII characters.")
    donor_chunk = _extract_object_chunk(bridge_dsn)
    core = bytearray(donor_chunk[1 : 1 + POWER_BRIDGE_CORE_SIZE])
    if len(core) != POWER_BRIDGE_CORE_SIZE:
        raise ValueError("Power bridge donor does not contain the expected 255-byte bridge core.")
    if core.count(b"$TEROUTPUT") != 1 or core.count(b"$TERPOWER") != 1 or core.count(b"WIRE") != 1:
        raise ValueError("Power bridge donor core does not match the locked marker pattern.")
    core[32:34] = power_node.encode("ascii")
    core[-1] = 0x00
    return bytes(core)


def _suffix_for(index: int, kind: str) -> int:
    base = 0x0159 if kind == "in" else 0x018B
    return (base + (index - 1) * 0x01BE) & 0xFFFF


def _patch_input(
    template: bytes,
    label: str,
    symbol_x: int,
    symbol_y: int,
    label_x: int,
    label_y: int,
    index: int,
    *,
    marker: bytes = b"$TERINPUT",
) -> tuple[bytes, int]:
    record = bytearray(template)
    if marker not in (b"$TERINPUT", b"$TERPOWER"):
        raise ValueError("Input endpoint marker must be $TERINPUT or $TERPOWER.")
    marker_pos = record.find(b"$TERINPUT")
    if marker_pos < 0:
        raise ValueError("Input terminal template marker not found.")
    record[marker_pos : marker_pos + len(b"$TERINPUT")] = marker
    raw_label = label.encode("ascii")
    if len(raw_label) != 2:
        raise ValueError("Input terminal labels must be exactly two ASCII characters.")
    record[1:5] = _i32(symbol_x)
    record[5:9] = _i32(symbol_y)
    record[30] = 2
    record[31:33] = raw_label
    record[33:37] = _i32(label_x)
    record[37:41] = _i32(label_y)
    suffix = _suffix_for(index, "in")
    record[-4:-2] = _u16(suffix)
    record[-2] = 0x01
    record[-1] = 0x00
    return bytes(record), suffix


def _patch_output(
    template: bytes,
    label: str,
    symbol_x: int,
    symbol_y: int,
    label_x: int,
    label_y: int,
    index: int,
    *,
    marker: bytes = b"$TEROUTPUT",
) -> tuple[bytes, int]:
    record = bytearray(template)
    if marker not in (b"$TEROUTPUT", b"$TERGROUND"):
        raise ValueError("Output endpoint marker must be $TEROUTPUT or $TERGROUND.")
    marker_pos = record.find(b"$TEROUTPUT")
    if marker_pos < 0:
        raise ValueError("Output terminal template marker not found.")
    record[marker_pos : marker_pos + len(b"$TEROUTPUT")] = marker
    raw_label = label.encode("ascii")
    if len(raw_label) != 2:
        raise ValueError("Output terminal labels must be exactly two ASCII characters.")
    record[1:5] = _i32(symbol_x)
    record[5:9] = _i32(symbol_y)
    record[31] = 2
    record[32:34] = raw_label
    record[34:38] = _i32(label_x)
    record[38:42] = _i32(label_y)
    suffix = _suffix_for(index, "out")
    record[-4:-2] = _u16(suffix)
    record[-2] = 0x01
    record[-1] = 0x00
    return bytes(record), suffix


def _patch_resistor(
    template: bytes,
    index: int,
    ref: str,
    visible_value: str,
    x: int,
    y: int,
    angle_tenths: int,
    in_suffix: int,
    out_suffix: int,
) -> bytes:
    record = bytearray(template)
    raw_ref = ref.encode("ascii")
    raw_value = visible_value.encode("ascii")
    if len(raw_ref) != 2 or len(raw_value) != 2:
        raise ValueError("Resistor ref and visible value must be exactly two ASCII characters.")
    record[1] = 2
    record[2:4] = raw_ref
    ref_x, ref_y, value_x, value_y, hidden_x, hidden_y = _label_positions(x, y, angle_tenths)
    record[4:8] = _i32(ref_x)
    record[8:12] = _i32(ref_y)
    record[69] = 2
    record[70:72] = raw_value
    record[72:76] = _i32(value_x)
    record[76:80] = _i32(value_y)
    record[149:153] = _i32(hidden_x)
    record[153:157] = _i32(hidden_y)
    record[235:239] = _i32(hidden_x)
    record[239:243] = _i32(hidden_y)
    record[312:316] = _i32(x)
    record[316:320] = _i32(y)
    record[320:324] = _angle_tenths(angle_tenths)
    record[324:328] = _u32(index)
    record[337:339] = _u16(in_suffix)
    record[339] = 0x01
    record[340] = 0x00
    record[341:343] = _u16(out_suffix)
    record[343] = 0x01
    record[344] = 0x00
    record[-1] = 0x00
    return bytes(record)


def _patch_wire(template: bytes, x1: int, y1: int, x2: int, y2: int) -> bytes:
    record = bytearray(template)
    record[33:37] = _i32(x1)
    record[37:41] = _i32(y1)
    record[41:45] = _i32(x2)
    record[45:49] = _i32(y2)
    record[-1] = 0x00
    return bytes(record)


def _normalized_angle(angle_tenths: int) -> int:
    return angle_tenths % 3600


def _direction_for_angle(angle_tenths: int) -> tuple[int, int]:
    angle = _normalized_angle(angle_tenths)
    if angle == 0:
        return 1, 0
    if angle == 900:
        return 0, 1
    if angle == 1800:
        return -1, 0
    if angle == 2700:
        return 0, -1
    raise ValueError(f"Unsupported resistor angle `{angle_tenths}`.")


def _label_positions(x: int, y: int, angle_tenths: int) -> tuple[int, int, int, int, int, int]:
    angle = _normalized_angle(angle_tenths)
    if angle == 0:
        return x + 254000, y + 121920, x + 254000, y - 121920, x + 254000, y - 375920
    if angle == 2700:
        return x + 254000, y - 254000, x + 254000, y - 762000, x + 254000, y - 1016000
    if angle == 900:
        return x - 254000, y + 254000, x - 254000, y + 762000, x - 254000, y + 1016000
    if angle == 1800:
        return x - 254000, y - 121920, x - 254000, y + 121920, x - 254000, y + 375920
    raise ValueError(f"Unsupported resistor angle `{angle_tenths}`.")


def _stretch_axis(values: list[int], min_spacing: int, *, descending: bool = False) -> dict[int, int]:
    unique = sorted(set(values), reverse=descending)
    if len(unique) < 2:
        return {value: value for value in unique}
    ordered = sorted(unique)
    if all(b - a >= min_spacing for a, b in zip(ordered, ordered[1:])):
        return {value: value for value in unique}
    anchor = unique[0]
    return {value: anchor - index * min_spacing if descending else anchor + index * min_spacing for index, value in enumerate(unique)}


def _safe_component_positions(ir: ResistorCircuitIR) -> tuple[dict[str, ComponentPosition], int]:
    positions = ir.layout.component_positions
    if not positions:
        return {}, 0
    x_map = _stretch_axis([position.x for position in positions.values()], SAFE_X_SPACING)
    y_map = _stretch_axis([position.y for position in positions.values()], SAFE_Y_SPACING, descending=True)
    safe: dict[str, ComponentPosition] = {}
    adjusted = 0
    for ref, position in positions.items():
        next_position = ComponentPosition(x=x_map[position.x], y=y_map[position.y])
        safe[ref] = next_position
        if next_position != position:
            adjusted += 1
    return safe, adjusted


def _position_for(
    ir: ResistorCircuitIR,
    component: ResistorComponent,
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


def _power_nodes(ir: ResistorCircuitIR) -> list[str]:
    out: list[str] = []
    for node in ir.nodes:
        if node.kind == "power" or node.id == "V0":
            out.append(node.id)
    return list(dict.fromkeys(out))


def _ground_nodes(ir: ResistorCircuitIR) -> set[str]:
    return {node.id for node in ir.nodes if node.kind == "ground" or node.id == "G0"}


def build_cdb(components: tuple[ResistorComponent, ...]) -> bytes:
    out = bytearray()
    count = len(components)
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + _enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + _enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + _enc_str("Master Sheet") + _u32(10) + _u32(0)
    out += _u32(count)
    for index, component in enumerate(components, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(index) + _enc_str(component.ref)
        out += _u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += _u32(0) + _u32(index) + _u32(0)
    out += _u32(1) + _u32(1) + b"\x00" + _enc_str("") + _u32(1)
    out += _u32(count)
    for index, component in enumerate(components, start=1):
        out += _u32(index) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        out += _enc_str(component.ref) + _enc_str(component.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(PROP_TEXT)
    out += _u32(0)
    return bytes(out)


def build_object_chunk(
    ir: ResistorCircuitIR,
    templates: V9Templates,
    bridge_dsn: bytes | None = None,
    layout_plan: LayoutPlan | None = None,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    power_nodes = _power_nodes(ir)
    if len(power_nodes) > 1:
        raise ValueError("The locked power-bridge method supports one distinct power node per generated project.")
    bridge_cores = [_load_power_bridge_core(bridge_dsn, node_id) for node_id in power_nodes] if bridge_dsn else []
    ground_nodes = _ground_nodes(ir)
    inputs: list[bytes] = []
    outputs: list[bytes] = []
    groups: list[bytes] = []
    maps: list[dict[str, Any]] = []
    auto_placed = 0
    ground_count = 0
    if layout_plan is not None and layout_plan.strategy in {"beautify", "manual"}:
        safe_positions = {
            ref: ComponentPosition(position.x, position.y)
            for ref, position in layout_plan.component_positions.items()
        }
        layout_adjusted_count = layout_plan.adjustment_count
    else:
        safe_positions, layout_adjusted_count = _safe_component_positions(ir)

    for index, component in enumerate(ir.components, start=1):
        left, right = component.nodes
        x, y, was_auto_placed = _position_for(ir, component, index, safe_positions)
        angle_tenths = resistor_orientation_angle(component.visual)
        ux, uy = _direction_for_angle(angle_tenths)
        if was_auto_placed:
            auto_placed += 1
        left_pin_x = x
        left_pin_y = y
        right_pin_x = x + ux * 1270000
        right_pin_y = y + uy * 1270000
        in_symbol_x = left_pin_x - ux * 508000
        in_symbol_y = left_pin_y - uy * 508000
        out_symbol_x = right_pin_x + ux * 508000
        out_symbol_y = right_pin_y + uy * 508000
        in_label_x = left_pin_x - ux * 889000
        in_label_y = left_pin_y - uy * 889000
        out_label_x = right_pin_x + ux * 889000
        out_label_y = right_pin_y + uy * 889000
        in_tip_x = left_pin_x - ux * 254000
        in_tip_y = left_pin_y - uy * 254000
        out_tip_x = right_pin_x + ux * 254000
        out_tip_y = right_pin_y + uy * 254000
        output_marker = b"$TERGROUND" if right in ground_nodes else b"$TEROUTPUT"
        if output_marker == b"$TERGROUND":
            ground_count += 1
        input_record, in_suffix = _patch_input(
            templates.input_terminals[(index - 1) % 4],
            left,
            in_symbol_x,
            in_symbol_y,
            in_label_x,
            in_label_y,
            index,
            marker=b"$TERINPUT",
        )
        output_record, out_suffix = _patch_output(
            templates.output_terminals[(index - 1) % 4],
            right,
            out_symbol_x,
            out_symbol_y,
            out_label_x,
            out_label_y,
            index,
            marker=output_marker,
        )
        res_template, wire_left_template, wire_right_template = templates.groups[(index - 1) % 4]
        visible_value = visible_resistor_value(component.value, component.visual)
        inputs.append(input_record)
        outputs.append(output_record)
        groups.append(_patch_resistor(res_template, index, component.ref, visible_value, x, y, angle_tenths, in_suffix, out_suffix))
        groups.append(_patch_wire(wire_left_template, in_tip_x, in_tip_y, left_pin_x, left_pin_y))
        groups.append(_patch_wire(wire_right_template, out_tip_x, out_tip_y, right_pin_x, right_pin_y))
        maps.append(
            {
                "idx": index,
                "ref": component.ref,
                "value": component.value,
                "visible_value": visible_value,
                "left": left,
                "right": right,
                "input_marker": "$TERINPUT",
                "output_marker": output_marker.decode("ascii"),
                "in_suffix": f"{in_suffix:04x}",
                "out_suffix": f"{out_suffix:04x}",
                "angle_tenths": angle_tenths,
                "pin1": {"x": left_pin_x, "y": left_pin_y},
                "pin2": {"x": right_pin_x, "y": right_pin_y},
                "x": x,
                "y": y,
                "auto_placed": was_auto_placed,
            }
        )

    visual_wires: list[bytes] = []
    visual_wire_skipped_count = len(ir.layout.visual_wires)

    chunk = bytearray(
        templates.header
        + b"".join(bridge_cores)
        + b"".join(inputs)
        + b"".join(outputs)
        + templates.separator
        + b"".join(groups)
        + b"".join(visual_wires)
    )
    chunk[-1] = 0xFF
    counts = {
        "auto_placed": auto_placed,
        "power_bridge_count": len(bridge_cores),
        "power_nodes": power_nodes,
        "ground_terminal_count": ground_count,
        "visual_wire_count": len(visual_wires),
        "visual_wire_skipped_count": visual_wire_skipped_count,
        "layout_adjusted_count": layout_adjusted_count,
    }
    return bytes(chunk), maps, counts


def build_dsn(base_dsn: bytes, donor_dsn: bytes, object_chunk: bytes) -> tuple[bytes, dict[str, int]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise ValueError("Base or donor ROOT.DSN does not match the V9 generator section model.")
    insert += len(marker)
    dev = bytearray(donor_dsn[insert:donor_first])
    first_header = donor_dsn[donor_first : donor_obj + len(b"OBJECT DATA")]
    tail = bytearray(base_dsn[e0_second:])
    first_isis = insert + len(dev)
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b"OBJECT DATA")
    object_data_pointer = second_obj + 13
    if len(dev) >= 4:
        dev[-4:] = _u32(object_data_pointer)
    cct = tail.find(b"CCT000")
    if cct != -1:
        tail[cct + len(b"CCT000") + 2 : cct + len(b"CCT000") + 6] = _u32(first_isis)
    default = tail.find(b"__DEFAULT__\x00\x00")
    if default != -1:
        tail[default + len(b"__DEFAULT__\x00\x00") : default + len(b"__DEFAULT__\x00\x00") + 4] = _u32(second_isis)
    dsn = bytes(bytearray(base_dsn[:insert]) + dev + first_header + bytearray(object_chunk) + tail)
    return dsn, {
        "insert": insert,
        "first_isis": first_isis,
        "second_isis": second_isis,
        "second_object_data": second_obj,
        "object_data_pointer": object_data_pointer,
    }


def validate_object_chunk(
    chunk: bytes,
    resistor_count: int,
    maps: list[dict[str, Any]],
    visual_wire_count: int = 0,
    power_bridge_count: int = 0,
) -> list[str]:
    issues: list[str] = []
    ground_count = sum(1 for item in maps if item["output_marker"] == "$TERGROUND")
    expected_len = (
        1
        + power_bridge_count * POWER_BRIDGE_CORE_SIZE
        + resistor_count * IN_SIZE
        + resistor_count * OUT_SIZE
        + 1
        + resistor_count * GROUP_SIZE
        + visual_wire_count * WIRE_SIZE
    )
    if len(chunk) != expected_len:
        issues.append(f"chunk length {len(chunk)} != {expected_len}")
    if not chunk or chunk[0] != 0:
        issues.append("chunk header not 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("final chunk byte not FF")
    counts = {
        "$TERINPUT": chunk.count(b"$TERINPUT"),
        "$TERPOWER": chunk.count(b"$TERPOWER"),
        "$TEROUTPUT": chunk.count(b"$TEROUTPUT"),
        "$TERGROUND": chunk.count(b"$TERGROUND"),
        "COMPONENT ID": chunk.count(b"COMPONENT ID"),
        "WIRE": chunk.count(b"WIRE"),
    }
    expected_counts = {
        "$TERINPUT": resistor_count,
        "$TERPOWER": power_bridge_count,
        "$TEROUTPUT": resistor_count - ground_count + power_bridge_count,
        "$TERGROUND": ground_count,
        "COMPONENT ID": resistor_count,
        "WIRE": 2 * resistor_count + visual_wire_count + power_bridge_count,
    }
    for key, expected in expected_counts.items():
        if counts[key] != expected:
            issues.append(f"{key} count {counts[key]} != {expected}")
    for index in range(power_bridge_count):
        bridge_end = 1 + (index + 1) * POWER_BRIDGE_CORE_SIZE - 1
        if chunk[bridge_end] != 0:
            issues.append(f"power bridge {index + 1} terminator {chunk[bridge_end]:02x}")
    base = 1 + power_bridge_count * POWER_BRIDGE_CORE_SIZE + resistor_count * IN_SIZE + resistor_count * OUT_SIZE + 1
    for index in range(resistor_count):
        group = base + index * GROUP_SIZE
        expected_w2 = 0xFF if index == resistor_count - 1 and visual_wire_count == 0 else 0
        if chunk[group + RES_SIZE - 1] != 0:
            issues.append(f"group {index + 1} resistor terminator {chunk[group + RES_SIZE - 1]:02x}")
        if chunk[group + RES_SIZE + WIRE_SIZE - 1] != 0:
            issues.append(f"group {index + 1} wire1 terminator {chunk[group + RES_SIZE + WIRE_SIZE - 1]:02x}")
        if chunk[group + RES_SIZE + 2 * WIRE_SIZE - 1] != expected_w2:
            issues.append(f"group {index + 1} wire2 terminator {chunk[group + RES_SIZE + 2 * WIRE_SIZE - 1]:02x}")
    visual_start = base + resistor_count * GROUP_SIZE
    for index in range(visual_wire_count):
        wire_end = visual_start + (index + 1) * WIRE_SIZE - 1
        expected = 0xFF if index == visual_wire_count - 1 else 0
        if chunk[wire_end] != expected:
            issues.append(f"visual wire {index + 1} terminator {chunk[wire_end]:02x}")
    for item in maps:
        in_suffix = struct.pack("<H", int(item["in_suffix"], 16))
        out_suffix = struct.pack("<H", int(item["out_suffix"], 16))
        if chunk.count(in_suffix) < 2:
            issues.append(f"input suffix {item['in_suffix']} appears {chunk.count(in_suffix)} times")
        if chunk.count(out_suffix) < 2:
            issues.append(f"output suffix {item['out_suffix']} appears {chunk.count(out_suffix)} times")
    return issues


def generate_resistor_project(
    ir: ResistorCircuitIR,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
    layout_plan: LayoutPlan | None = None,
) -> ResistorGenerationResult:
    registry = registry or FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {', '.join(failed_hashes)}")
    report = validate_resistor_circuit(ir)
    if not report.valid:
        raise ResistorGenerationBlocked(report)

    base = registry.get("e001_empty")
    donor = registry.get("r21_v9_resistor_terminal_donor")
    bridge_donor = registry.get("power_terminal_bridge_donor")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(donor.path, "ROOT.DSN")
    bridge_dsn = read_internal_file(bridge_donor.path, "ROOT.DSN")
    templates = _load_templates(donor_dsn, donor.path)
    object_chunk, maps, generation_counts = build_object_chunk(ir, templates, bridge_dsn, layout_plan)
    cdb = build_cdb(ir.components)
    dsn, section_pointers = build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    chunk_issues = validate_object_chunk(
        _extract_object_chunk(dsn),
        len(ir.components),
        maps,
        generation_counts["visual_wire_count"],
        generation_counts["power_bridge_count"],
    )

    output_dir = Path(outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    basename = ir.project.output_basename
    output_path = output_dir / f"{basename}.pdsprj"
    cdb_path = output_dir / f"{basename}.ROOT.CDB.bin"
    dsn_path = output_dir / f"{basename}.ROOT.DSN.bin"
    layout_path = output_dir / "layout_plan.json"
    manifest_path = output_dir / "manifest.json"
    readme_path = output_dir / "README_TEST_FIRST.txt"
    version_path = output_dir / "generator_version.txt"

    write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    final_layout = (
        plan_with_actual_positions(layout_plan, maps)
        if layout_plan is not None
        else actual_layout_plan("resistor", maps)
    )
    layout_path.write_text(json.dumps(final_layout.as_dict(), indent=2) + "\n", encoding="utf-8")
    version_path.write_text(
        "proteusgen resistor_v9 locked method\n"
        "base_fixture=e001_empty\n"
        "donor_fixture=r21_v9_resistor_terminal_donor\n"
        "power_bridge_fixture=power_terminal_bridge_donor\n",
        encoding="utf-8",
    )
    output_hashes = {
        output_path.name: _sha256_file(output_path),
        cdb_path.name: _sha256_file(cdb_path),
        dsn_path.name: _sha256_file(dsn_path),
        "base_project": _sha256_file(base.path),
        "donor_project": _sha256_file(donor.path),
        "power_bridge_donor": _sha256_file(bridge_donor.path),
    }
    manifest = {
        "schema_version": ir.schema_version,
        "generator_target": ir.generator_target,
        "project_name": ir.project.name,
        "output_basename": basename,
        "base_project": "E001_EMPTY_BASE",
        "base_fixture_id": base.id,
        "donor_fixture_id": donor.id,
        "power_bridge_fixture_id": bridge_donor.id,
        "power_bridge_core_len_bytes": POWER_BRIDGE_CORE_SIZE,
        "power_bridge_count": generation_counts["power_bridge_count"],
        "power_nodes": generation_counts["power_nodes"],
        "node_count_requested": len(ir.nodes),
        "component_count_requested": len(ir.components),
        "component_count_emitted_cdb": len(ir.components),
        "component_count_emitted_dsn": len(ir.components),
        "terminal_count": len(ir.components) * 2 + generation_counts["power_bridge_count"] * 2,
        "input_terminal_count": len(ir.components),
        "output_terminal_count": len(ir.components)
        - generation_counts["ground_terminal_count"]
        + generation_counts["power_bridge_count"],
        "power_terminal_count": generation_counts["power_bridge_count"],
        "ground_terminal_count": generation_counts["ground_terminal_count"],
        "short_wire_count": len(ir.components) * 2,
        "bridge_wire_count": generation_counts["power_bridge_count"],
        "visual_wire_count": generation_counts["visual_wire_count"],
        "visual_wire_skipped_count": generation_counts["visual_wire_skipped_count"],
        "wire_count": len(ir.components) * 2
        + generation_counts["visual_wire_count"]
        + generation_counts["power_bridge_count"],
        "object_group_count": len(ir.components),
        "auto_placed_count": generation_counts["auto_placed"],
        "layout_adjusted_count": generation_counts["layout_adjusted_count"],
        "layout": final_layout.as_dict(),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "terminator_validation": {
            "final_object_has_final_terminator": bool(object_chunk and object_chunk[-1] == 0xFF),
            "premature_terminator_issues": [issue for issue in chunk_issues if "terminator" in issue],
        },
        "link_suffix_validation": {
            "checked": True,
            "issues": [issue for issue in chunk_issues if "suffix" in issue],
        },
        "section_pointer_values": section_pointers,
        "static_validation_issues": chunk_issues,
        "topology": maps,
        "known_limitations": [
            "Two-character node labels only; use V0/G0 instead of VCC/GND.",
            "Power support emits one donor-derived $TERPOWER -> $TEROUTPUT bridge for the power node.",
            "Ground terminals are supported only on right endpoints.",
            "Resistor drawing supports locked 90-degree rotations only; arbitrary diagonal component angles and routed bus/junction geometry are still experimental.",
            "Standalone layout.visual_wires are intentionally skipped in production until VGDVC-safe wire records are validated.",
        ],
        "output_files": [
            output_path.name,
            cdb_path.name,
            dsn_path.name,
            layout_path.name,
            manifest_path.name,
            readme_path.name,
            version_path.name,
        ],
        "output_hashes": output_hashes,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        f"{basename}\n\n"
        "Open this generated project in Proteus 8.13 after checking the E001 base if needed.\n\n"
        f"Project: {output_path.name}\n"
        f"Static validation issues: {chunk_issues}\n\n"
        "Current locked endpoint rules:\n"
        "- V0/power nodes use one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge.\n"
        "- Powered resistor endpoints remain normal $TERINPUT(V0) terminals.\n"
        "- G0/ground nodes on component.nodes[1] become $TERGROUND endpoints.\n"
        "- Other endpoints use V9 input/output terminal labels.\n"
        "Production safety rules:\n"
        "- Dense manual positions may be stretched to the safe V9 grid.\n"
        "- Standalone layout.visual_wires are skipped until VGDVC-safe records are validated.\n",
        encoding="utf-8",
    )
    return ResistorGenerationResult(
        output_path=output_path,
        cdb_path=cdb_path,
        dsn_path=dsn_path,
        layout_path=layout_path,
        manifest_path=manifest_path,
        readme_path=readme_path,
        version_path=version_path,
        manifest=manifest,
    )


def generate_resistor_project_from_payload(
    payload: Any,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
    layout_strategy: str | None = None,
) -> ResistorGenerationResult:
    try:
        application = apply_layout_to_payload(payload, layout_strategy)
    except LayoutError as exc:
        issue = Issue("INVALID_LAYOUT", str(exc), "$.layout")
        raise ResistorGenerationBlocked(ResistorValidationReport(errors=(issue,), warnings=(), circuit=None)) from exc
    ir, issues = parse_resistor_ir(application.payload)
    if issues:
        raise ResistorGenerationBlocked(ResistorValidationReport(errors=tuple(issues), warnings=(), circuit=None))
    assert ir is not None
    return generate_resistor_project(ir, outdir, registry=registry, layout_plan=application.plan)


def validate_resistor_json_file(path: str | Path) -> ResistorValidationReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_resistor_payload(payload)
