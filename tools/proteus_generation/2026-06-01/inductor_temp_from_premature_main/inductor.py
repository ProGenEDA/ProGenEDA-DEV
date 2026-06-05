"""Locked inductor terminal generator.

This module promotes only the user-confirmed inductor methods:

- V3 terminal-only inductors using per-index REALIND templates.
- V5 single V0/G0 inductor using the donor04 power/ground object order.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import resistor_v9 as rv9
from .inductor_ir import (
    InductorCircuitIR,
    InductorComponent,
    InductorValidationReport,
    parse_inductor_ir,
    validate_inductor_circuit,
    visible_inductor_value,
)
from .pdsprj import read_internal_file, write_project_from_parts
from .resistor_ir import ComponentPosition
from .templates import FixtureRegistry
from .versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

IN_SIZE = 103
OUT_SIZE = 104
WIRE_SIZE = 50
WIRE_TRIMMED_SIZE = 49
IND_PROP_TEXT = b"{MODFILE=REALIND}\n{RP=1M}\n{ESR=0.2}\n{CP=0.2pF}\n\n\n\x00"
SAFE_X_SPACING = 2540000
SAFE_Y_SPACING = 2540000
POWER_GROUND_DONOR_X = -7366000
POWER_GROUND_DONOR_Y = 1270000


@dataclass(frozen=True)
class InductorGenerationResult:
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


class InductorGenerationBlocked(Exception):
    def __init__(self, report: InductorValidationReport) -> None:
        super().__init__("Inductor CircuitIR cannot be emitted.")
        self.report = report


@dataclass(frozen=True)
class ThreeInductorTemplates:
    donor_chunk: bytes
    header: bytes
    inputs: tuple[bytes, bytes, bytes]
    outputs: tuple[bytes, bytes, bytes]
    inductors: tuple[bytes, bytes, bytes]
    wire_lefts: tuple[bytes, bytes, bytes]
    wire_rights: tuple[bytes, bytes, bytes]


@dataclass(frozen=True)
class Donor04Templates:
    donor_chunk: bytes
    header: bytes
    input_terminal: bytes
    inductor: bytes
    wire_left_trimmed: bytes
    power_terminal: bytes
    power_output: bytes
    power_wire: bytes
    ground_terminal: bytes
    ground_wire_final: bytes


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


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def _load_three_templates(project_path: Path) -> ThreeInductorTemplates:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    if chunk.count(b"$TERINPUT") != 3 or chunk.count(b"$TEROUTPUT") != 3:
        raise RuntimeError("Inductor donor03 must contain three terminal-attached inductors.")
    if chunk.count(b"REALIND") != 9 or chunk.count(b"WIRE") != 6:
        raise RuntimeError("Inductor donor03 marker counts do not match the accepted V3 shape.")
    return ThreeInductorTemplates(
        donor_chunk=chunk,
        header=chunk[:1],
        inputs=(chunk[1:104], chunk[889:992], chunk[1465:1568]),
        outputs=(chunk[104:208], chunk[681:785], chunk[785:889]),
        inductors=(chunk[208:582], chunk[992:1366], chunk[1568:1943]),
        wire_lefts=(chunk[582:632], chunk[1366:1416], chunk[1943:1993]),
        wire_rights=(chunk[632:681] + b"\x00", chunk[1416:1465] + b"\x00", chunk[1993:2043]),
    )


def _load_donor04_templates(project_path: Path) -> Donor04Templates:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    if len(chunk) != 947:
        raise RuntimeError(f"Expected donor04 object chunk length 947, got {len(chunk)}.")
    if chunk.count(b"$TERPOWER") != 1 or chunk.count(b"$TERGROUND") != 1 or chunk.count(b"REALIND") != 3:
        raise RuntimeError("Inductor donor04 marker counts do not match the accepted V5 shape.")
    return Donor04Templates(
        donor_chunk=chunk,
        header=chunk[0:1],
        input_terminal=chunk[1:104],
        inductor=chunk[104:478],
        wire_left_trimmed=chunk[478:527],
        power_terminal=chunk[527:630],
        power_output=chunk[630:734],
        power_wire=chunk[734:784],
        ground_terminal=chunk[784:888],
        ground_wire_final=chunk[888:947],
    )


def _stretch_axis(values: list[int], min_spacing: int, *, descending: bool = False) -> dict[int, int]:
    unique = sorted(set(values), reverse=descending)
    if len(unique) < 2:
        return {value: value for value in unique}
    ordered = sorted(unique)
    if all(b - a >= min_spacing for a, b in zip(ordered, ordered[1:])):
        return {value: value for value in unique}
    anchor = unique[0]
    return {value: anchor - index * min_spacing if descending else anchor + index * min_spacing for index, value in enumerate(unique)}


def _safe_component_positions(ir: InductorCircuitIR) -> tuple[dict[str, ComponentPosition], int]:
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


def _position_for(component: InductorComponent, index: int, positions: dict[str, ComponentPosition]) -> tuple[int, int, bool]:
    position = positions.get(component.ref)
    if position is not None:
        return position.x, position.y, False
    visual = component.visual
    if isinstance(visual.get("col"), int) and isinstance(visual.get("row"), int):
        return -6350000 + int(visual["col"]) * SAFE_X_SPACING, 5080000 - int(visual["row"]) * SAFE_Y_SPACING, True
    col = (index - 1) % 3
    row = (index - 1) // 3
    return -6350000 + col * SAFE_X_SPACING, 5080000 - row * SAFE_Y_SPACING, True


def _patch_input_preserving_suffix(template: bytes, label: str, index: int, symbol_x: int, symbol_y: int, label_x: int, label_y: int) -> bytes:
    record, _ = rv9._patch_input(template, label, symbol_x, symbol_y, label_x, label_y, index, marker=b"$TERINPUT")
    return record[:-4] + template[-4:]


def _patch_output_preserving_suffix(template: bytes, label: str, index: int, symbol_x: int, symbol_y: int, label_x: int, label_y: int) -> bytes:
    record, _ = rv9._patch_output(template, label, symbol_x, symbol_y, label_x, label_y, index, marker=b"$TEROUTPUT")
    return record[:-4] + template[-4:]


def _patch_inductor_preserving_suffix(template: bytes, index: int, component: InductorComponent, visible_value: str, x: int, y: int) -> bytes:
    raw_ref = component.ref.encode("ascii")
    raw_value = visible_value.encode("ascii")
    if len(raw_ref) != 2:
        raise ValueError("Inductor refs must be exactly two ASCII characters.")
    if len(raw_value) != template[70]:
        raise ValueError("Inductor REALIND text mutation keeps value byte length identical to its donor slot.")
    delta = len(raw_value) - 3
    record = bytearray(template)
    record[2] = 2
    record[3:5] = raw_ref
    record[70] = len(raw_value)
    record[71 : 71 + len(raw_value)] = raw_value

    ref_x = x - 528320
    ref_y = y + 274320
    value_x = x - 528320
    value_y = y - 20320
    hidden_x = x - 528320
    hidden_y = y - 274320

    record[5:9] = _i32(ref_x)
    record[9:13] = _i32(ref_y)
    record[74 + delta : 78 + delta] = _i32(value_x)
    record[78 + delta : 82 + delta] = _i32(value_y)
    record[150 + delta : 154 + delta] = _i32(hidden_x)
    record[154 + delta : 158 + delta] = _i32(hidden_y)
    record[264 + delta : 268 + delta] = _i32(hidden_x)
    record[268 + delta : 272 + delta] = _i32(hidden_y)
    record[340 + delta : 344 + delta] = _i32(x)
    record[344 + delta : 348 + delta] = _i32(y)
    record[352 + delta : 356 + delta] = _u32(index)
    record[364 + delta : 372 + delta] = template[364 + delta : 372 + delta]
    record[-1] = 0x00
    return bytes(record)


def _patch_power_terminal(template: bytes, label: str) -> bytes:
    record = bytearray(template)
    if record.find(b"$TERPOWER") < 0:
        raise RuntimeError("Power terminal template marker not found.")
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError("Power label must be exactly two ASCII characters.")
    record[30] = 2
    record[31:33] = raw
    record[-4:] = template[-4:]
    return bytes(record)


def _patch_output_or_ground_preserving_suffix(template: bytes, label: str, marker: bytes) -> bytes:
    record = bytearray(template)
    marker_pos = record.find(b"$TEROUTPUT")
    current_marker = b"$TEROUTPUT"
    if marker_pos < 0:
        marker_pos = record.find(b"$TERGROUND")
        current_marker = b"$TERGROUND"
    if marker_pos < 0:
        raise RuntimeError("Output/ground terminal template marker not found.")
    if current_marker != marker:
        record[marker_pos : marker_pos + len(current_marker)] = marker
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError("Output label must be exactly two ASCII characters.")
    record[31] = 2
    record[32:34] = raw
    record[-4:] = template[-4:]
    return bytes(record)


def _patch_input_same_position(template: bytes, label: str) -> bytes:
    return _patch_input_preserving_suffix(
        template,
        label,
        1,
        _s32(template, 1),
        _s32(template, 5),
        _s32(template, 33),
        _s32(template, 37),
    )


def build_cdb(components: tuple[InductorComponent, ...]) -> bytes:
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
        out += _enc_str(component.ref) + _enc_str(component.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(IND_PROP_TEXT)
    out += _u32(0)
    return bytes(out)


def _power_nodes(ir: InductorCircuitIR) -> set[str]:
    return {node.id for node in ir.nodes if node.kind == "power" or node.id == "V0"}


def _ground_nodes(ir: InductorCircuitIR) -> set[str]:
    return {node.id for node in ir.nodes if node.kind == "ground" or node.id == "G0"}


def _uses_power_ground(ir: InductorCircuitIR) -> bool:
    power_nodes = _power_nodes(ir)
    ground_nodes = _ground_nodes(ir)
    return any(endpoint in power_nodes or endpoint in ground_nodes for component in ir.components for endpoint in component.nodes)


def build_terminal_object_chunk(ir: InductorCircuitIR, templates: ThreeInductorTemplates) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    positions, adjusted = _safe_component_positions(ir)
    groups: list[dict[str, Any]] = []
    auto_placed = 0
    for index, component in enumerate(ir.components, start=1):
        x, y, was_auto_placed = _position_for(component, index, positions)
        auto_placed += int(was_auto_placed)
        visible_value = visible_inductor_value(component.value, component.visual)
        left, right = component.nodes
        left_pin_x = x - 762000
        right_pin_x = x + 762000
        input_record = _patch_input_preserving_suffix(
            templates.inputs[index - 1],
            left,
            index,
            left_pin_x - 254000,
            y,
            left_pin_x - 635000,
            y,
        )
        output_record = _patch_output_preserving_suffix(
            templates.outputs[index - 1],
            right,
            index,
            right_pin_x + 508000,
            y,
            right_pin_x + 889000,
            y,
        )
        inductor = _patch_inductor_preserving_suffix(templates.inductors[index - 1], index, component, visible_value, x, y)
        wire_left = rv9._patch_wire(templates.wire_lefts[index - 1], left_pin_x, y, left_pin_x, y)
        wire_right = rv9._patch_wire(templates.wire_rights[2], right_pin_x + 254000, y, right_pin_x, y)
        if index != len(ir.components):
            wire_right = wire_right[:-1]
        groups.append(
            {
                "input": input_record,
                "output": output_record,
                "inductor": inductor,
                "wire_left": wire_left,
                "wire_right": wire_right,
                "map": {
                    "idx": index,
                    "ref": component.ref,
                    "value": component.value,
                    "visible_value": visible_value,
                    "left": left,
                    "right": right,
                    "input_marker": "$TERINPUT",
                    "output_marker": "$TEROUTPUT",
                    "x": x,
                    "y": y,
                    "method": "v3_formula_coordinates_with_per_index_realind_template",
                },
            }
        )

    out = bytearray(templates.header)
    if len(groups) == 1:
        group = groups[0]
        out += group["input"] + group["output"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    else:
        first = groups[0]
        out += first["input"] + first["output"] + first["inductor"] + first["wire_left"] + first["wire_right"]
        out += b"".join(group["output"] for group in groups[1:])
        for group in groups[1:]:
            out += group["input"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    counts = {
        "mode": "terminal_only",
        "inductor_count": len(ir.components),
        "power_bridge_count": 0,
        "ground_terminal_count": 0,
        "auto_placed": auto_placed,
        "layout_adjusted_count": adjusted,
        "visual_wire_count": 0,
        "visual_wire_skipped_count": len(ir.layout.visual_wires),
    }
    return bytes(out), [group["map"] for group in groups], counts


def build_power_ground_object_chunk(ir: InductorCircuitIR, templates: Donor04Templates) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    component = ir.components[0]
    internal_power_node = component.visual.get("internal_power_node", "N1")
    if not isinstance(internal_power_node, str) or len(internal_power_node.encode("ascii", errors="ignore")) != 2:
        raise ValueError("visual.internal_power_node must be exactly two ASCII characters.")
    if internal_power_node in {"V0", "G0"}:
        raise ValueError("visual.internal_power_node must be distinct from V0 and G0.")
    visible_value = visible_inductor_value(component.value, component.visual)
    x = POWER_GROUND_DONOR_X
    y = POWER_GROUND_DONOR_Y
    inductor = _patch_inductor_preserving_suffix(templates.inductor, 1, component, visible_value, x, y)
    out = bytearray(
        templates.header
        + _patch_input_same_position(templates.input_terminal, internal_power_node)
        + inductor
        + templates.wire_left_trimmed
        + _patch_power_terminal(templates.power_terminal, "V0")
        + _patch_output_or_ground_preserving_suffix(templates.power_output, internal_power_node, b"$TEROUTPUT")
        + templates.power_wire
        + _patch_output_or_ground_preserving_suffix(templates.ground_terminal, "G0", b"$TERGROUND")
        + templates.ground_wire_final
    )
    out[-1] = 0xFF
    requested_position = ir.layout.component_positions.get(component.ref)
    position_normalized = requested_position is not None and (requested_position.x != x or requested_position.y != y)
    topology = [
        {
            "idx": 1,
            "ref": component.ref,
            "value": component.value,
            "visible_value": visible_value,
            "left": "V0",
            "right": "G0",
            "input_marker": "$TERINPUT",
            "output_marker": "$TERGROUND",
            "internal_power_node": internal_power_node,
            "x": x,
            "y": y,
            "position_normalized_to_donor04": position_normalized,
            "method": "v5_donor04_power_ground_order",
        }
    ]
    counts = {
        "mode": "single_power_ground",
        "inductor_count": 1,
        "power_bridge_count": 1,
        "ground_terminal_count": 1,
        "auto_placed": 0,
        "layout_adjusted_count": 0,
        "visual_wire_count": 0,
        "visual_wire_skipped_count": len(ir.layout.visual_wires),
    }
    return bytes(out), topology, counts


def validate_object_chunk(chunk: bytes, topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    inductor_count = counts["inductor_count"]
    if counts["mode"] == "single_power_ground":
        expected_len = 947
        expected_counts = {
            "$TERINPUT": 1,
            "$TEROUTPUT": 1,
            "$TERPOWER": 1,
            "$TERGROUND": 1,
            "REALIND": 3,
            "WIRE": 3,
        }
    else:
        expected_len = 1 + inductor_count * IN_SIZE + inductor_count * OUT_SIZE
        for index, item in enumerate(topology, start=1):
            right_wire_len = WIRE_SIZE if index == inductor_count else WIRE_TRIMMED_SIZE
            expected_len += 371 + len(item["visible_value"]) + WIRE_SIZE + right_wire_len
        expected_counts = {
            "$TERINPUT": inductor_count,
            "$TEROUTPUT": inductor_count,
            "$TERPOWER": 0,
            "$TERGROUND": 0,
            "REALIND": inductor_count * 3,
            "WIRE": inductor_count * 2,
        }
    if len(chunk) != expected_len:
        issues.append(f"object chunk length {len(chunk)} != {expected_len}")
    for marker, expected in expected_counts.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected:
            issues.append(f"{marker} count {actual} != {expected}")
    if len(topology) != inductor_count:
        issues.append(f"topology entries {len(topology)} != inductor count {inductor_count}")
    return issues


def generate_inductor_project(
    ir: InductorCircuitIR,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> InductorGenerationResult:
    registry = registry or FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {', '.join(failed_hashes)}")
    report = validate_inductor_circuit(ir)
    if not report.valid:
        raise InductorGenerationBlocked(report)

    base = registry.get("e001_empty")
    mode_is_power_ground = _uses_power_ground(ir)
    if mode_is_power_ground:
        donor = registry.get("inductor_04_power_ground")
        templates = _load_donor04_templates(donor.path)
        object_chunk, topology, generation_counts = build_power_ground_object_chunk(ir, templates)
        object_order = "header, input internal node, REALIND, trimmed left wire, $TERPOWER, $TEROUTPUT internal node, bridge wire, $TERGROUND, final ground wire"
    else:
        donor = registry.get("inductor_03_three_terminal")
        templates = _load_three_templates(donor.path)
        object_chunk, topology, generation_counts = build_terminal_object_chunk(ir, templates)
        object_order = "header, first full inductor group, remaining outputs, remaining input/REALIND/wire groups"
    cdb = build_cdb(ir.components)
    donor_dsn = read_internal_file(donor.path, "ROOT.DSN")
    dsn, section_pointers = rv9.build_dsn(read_internal_file(base.path, "ROOT.DSN"), donor_dsn, object_chunk)
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
        "proteusgen inductor locked method\n"
        "base_fixture=e001_empty\n"
        f"donor_fixture={donor.id}\n"
        f"mode={generation_counts['mode']}\n",
        encoding="utf-8",
    )
    manifest = {
        "schema_version": ir.schema_version,
        "generator_target": ir.generator_target,
        "project_name": ir.project.name,
        "output_basename": basename,
        "base_project": "E001_EMPTY_BASE",
        "base_fixture_id": base.id,
        "donor_fixture_id": donor.id,
        "component_count_requested": len(ir.components),
        "component_count_emitted_cdb": len(ir.components),
        "component_count_emitted_dsn": generation_counts["inductor_count"],
        "inductor_count": generation_counts["inductor_count"],
        "node_count_requested": len(ir.nodes),
        "power_bridge_count": generation_counts["power_bridge_count"],
        "ground_terminal_count": generation_counts["ground_terminal_count"],
        "terminal_count": object_chunk.count(b"$TERINPUT") + object_chunk.count(b"$TEROUTPUT") + object_chunk.count(b"$TERPOWER") + object_chunk.count(b"$TERGROUND"),
        "wire_count": object_chunk.count(b"WIRE"),
        "visual_wire_count": generation_counts["visual_wire_count"],
        "visual_wire_skipped_count": generation_counts["visual_wire_skipped_count"],
        "auto_placed_count": generation_counts["auto_placed"],
        "layout_adjusted_count": generation_counts["layout_adjusted_count"],
        "safe_spacing": {"x": SAFE_X_SPACING, "y": SAFE_Y_SPACING},
        "object_order": object_order,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "section_pointer_values": section_pointers,
        "static_validation_issues": chunk_issues,
        "topology": topology,
        "known_limitations": [
            "Two-character node and component labels only.",
            "Terminal-only inductor generation is validated for one to three components only.",
            "Power/ground inductor generation is validated only for one V0-to-G0 inductor using donor04 order.",
            "The rejected generic passive power bridge must not be used for inductors.",
            "Standalone layout.visual_wires are intentionally skipped until VGDVC-safe records are validated.",
        ],
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, manifest_path.name, readme_path.name, version_path.name],
        "output_hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            "base_project": _sha256_file(base.path),
            "donor_project": _sha256_file(donor.path),
            "object_chunk_sha256": _sha256_bytes(object_chunk),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        f"{basename}\n\n"
        "Open this generated inductor project in Proteus 8.13.\n\n"
        f"Project: {output_path.name}\n"
        f"Components: {len(ir.components)} inductors\n"
        f"Mode: {generation_counts['mode']}\n"
        f"Static validation issues: {chunk_issues}\n\n"
        "Locked endpoint rules:\n"
        "- Terminal-only inductors use $TERINPUT/$TEROUTPUT label topology.\n"
        "- V0/G0 inductors use the donor04 object order, not the generic passive power bridge.\n",
        encoding="utf-8",
    )
    return InductorGenerationResult(output_path, cdb_path, dsn_path, manifest_path, readme_path, version_path, manifest)


def generate_inductor_project_from_payload(
    payload: Any,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> InductorGenerationResult:
    ir, issues = parse_inductor_ir(payload)
    if issues:
        raise InductorGenerationBlocked(InductorValidationReport(errors=tuple(issues), warnings=(), circuit=None))
    assert ir is not None
    return generate_inductor_project(ir, outdir, registry=registry)


def validate_inductor_json_file(path: str | Path) -> InductorValidationReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    ir, issues = parse_inductor_ir(payload)
    if issues:
        return InductorValidationReport(errors=tuple(issues), warnings=(), circuit=None)
    assert ir is not None
    return validate_inductor_circuit(ir)
