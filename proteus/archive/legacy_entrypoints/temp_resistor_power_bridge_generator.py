"""Temporary resistor generator using the locked power-bridge method.

This is intentionally kept outside the main generator while the method is
being revalidated. It uses:

- E001 as the project base
- R21 V9 as the resistor/terminal/wire record donor
- New Project(1).pdsprj from the handoff ZIP as the power bridge donor
- ordinary V9 input terminals for powered resistor endpoints
- one donor-derived $TERPOWER -> $TEROUTPUT(power-node) bridge
- $TERGROUND short-wire endpoints for grounded right pins
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_ir import (
    ResistorCircuitIR,
    ResistorNode,
    ResistorValidationReport,
    parse_resistor_ir,
    resistor_orientation_angle,
    validate_resistor_circuit,
)
from proteusgen.resistor_v9 import (
    GROUP_SIZE,
    IN_SIZE,
    OUT_SIZE,
    RES_SIZE,
    WIRE_SIZE,
    ResistorGenerationBlocked,
    ResistorGenerationResult,
    V9Templates,
    _direction_for_angle,
    _extract_object_chunk,
    _i32,
    _load_templates,
    _patch_input,
    _patch_output,
    _patch_resistor,
    _patch_wire,
    _sha256_file,
    build_cdb,
    build_dsn,
)
from proteusgen.templates import FixtureRegistry, repository_root
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

HANDOFF_ZIP = "PROTEUS_AI_HANDOFF_ALL_LOCAL_ARTIFACTS_2026_05_30.zip"
BRIDGE_DONOR_INTERNAL = "local_artifacts/New Project(1).pdsprj"
POWER_BRIDGE_CORE_SIZE = 255


def _bridge_donor_root_dsn(repo_root: Path) -> bytes:
    handoff = repo_root / HANDOFF_ZIP
    if not handoff.exists():
        raise FileNotFoundError(f"Missing handoff ZIP with power bridge donor: {handoff}")
    with ZipFile(handoff, "r") as outer:
        donor_project = outer.read(BRIDGE_DONOR_INTERNAL)
    with ZipFile(BytesIO(donor_project), "r") as project:
        return project.read("ROOT.DSN")


def _load_power_bridge_core(repo_root: Path, power_node: str) -> bytes:
    """Return donor bridge bytes after OBJECT DATA header, patched to `power_node`.

    The working clean artifacts use object_chunk[0] as the stream header, then
    exact donor bytes 1..255 as:

        $TEROUTPUT(node), $TERPOWER, WIRE

    Only the two label bytes in the output terminal are patched.
    """

    if len(power_node.encode("ascii")) != 2:
        raise ValueError("Power bridge node labels must be exactly two ASCII characters.")
    donor_chunk = _extract_object_chunk(_bridge_donor_root_dsn(repo_root))
    core = bytearray(donor_chunk[1 : 1 + POWER_BRIDGE_CORE_SIZE])
    if len(core) != POWER_BRIDGE_CORE_SIZE:
        raise ValueError("Power bridge donor does not contain the expected 255-byte bridge core.")
    if core.count(b"$TEROUTPUT") != 1 or core.count(b"$TERPOWER") != 1 or core.count(b"WIRE") != 1:
        raise ValueError("Power bridge donor core does not match the locked marker pattern.")
    core[32:34] = power_node.encode("ascii")
    core[-1] = 0x00
    return bytes(core)


def _power_nodes(ir: ResistorCircuitIR) -> list[str]:
    out: list[str] = []
    for node in ir.nodes:
        if node.kind == "power" or node.id == "V0":
            out.append(node.id)
    return out


def _ground_nodes(ir: ResistorCircuitIR) -> set[str]:
    return {node.id for node in ir.nodes if node.kind == "ground" or node.id == "G0"}


def _visible_resistor_value(value: str, visual: dict[str, Any] | None = None) -> str:
    override = (visual or {}).get("visible_value")
    if isinstance(override, str) and len(override.encode("ascii", errors="ignore")) == 2 and override.isascii():
        return override
    if len(value) == 2 and value.isascii():
        return value
    if len(value) > 2 and value[:2].isascii():
        return value[:2]
    raise ValueError(f"Value `{value}` has no two-character visible representation.")


def _position_for(ir: ResistorCircuitIR, component_ref: str, index: int, visual: dict[str, Any]) -> tuple[int, int, bool]:
    position = ir.layout.component_positions.get(component_ref)
    if position is not None:
        return position.x, position.y, False
    if isinstance(visual.get("col"), int) and isinstance(visual.get("row"), int):
        return -6350000 + int(visual["col"]) * 2540000, 5080000 - int(visual["row"]) * 1524000, True
    col = (index - 1) % 7
    row = (index - 1) // 7
    return -6350000 + col * 2540000, 5080000 - row * 1524000, True


def build_object_chunk_power_bridge(
    ir: ResistorCircuitIR,
    templates: V9Templates,
    repo_root: Path,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    power_nodes = _power_nodes(ir)
    if len(set(power_nodes)) > 1:
        raise ValueError("Temporary power-bridge generator supports exactly one distinct power node.")
    bridge_cores = [_load_power_bridge_core(repo_root, node_id) for node_id in dict.fromkeys(power_nodes)]
    ground_nodes = _ground_nodes(ir)
    inputs: list[bytes] = []
    outputs: list[bytes] = []
    groups: list[bytes] = []
    maps: list[dict[str, Any]] = []
    auto_placed = 0
    ground_count = 0

    for index, component in enumerate(ir.components, start=1):
        left, right = component.nodes
        x, y, was_auto_placed = _position_for(ir, component.ref, index, component.visual)
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
        visible_value = _visible_resistor_value(component.value, component.visual)
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
    visual_wire_template = templates.groups[0][1]
    for wire in ir.layout.visual_wires:
        visual_wires.append(_patch_wire(visual_wire_template, wire.x1, wire.y1, wire.x2, wire.y2))

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
        "power_nodes": list(dict.fromkeys(power_nodes)),
        "ground_terminal_count": ground_count,
        "visual_wire_count": len(visual_wires),
    }
    return bytes(chunk), maps, counts


def validate_object_chunk_power_bridge(
    chunk: bytes,
    resistor_count: int,
    maps: list[dict[str, Any]],
    *,
    power_bridge_count: int,
    visual_wire_count: int = 0,
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


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _without_power_endpoint_markers(ir: ResistorCircuitIR) -> ResistorCircuitIR:
    """Keep validation rules, but make explicit that endpoints stay TERINPUT."""

    nodes = tuple(replace(node, role=(node.role or "power_bridge_source")) if node.kind == "power" else node for node in ir.nodes)
    return replace(ir, nodes=nodes)


def generate_resistor_project_power_bridge_temp(
    ir: ResistorCircuitIR,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> ResistorGenerationResult:
    registry = registry or FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {', '.join(failed_hashes)}")
    report = validate_resistor_circuit(ir)
    if not report.valid:
        raise ResistorGenerationBlocked(report)

    root = repository_root()
    base = registry.get("e001_empty")
    donor = registry.get("r21_v9_resistor_terminal_donor")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(donor.path, "ROOT.DSN")
    templates = _load_templates(donor_dsn, donor.path)
    normalized_ir = _without_power_endpoint_markers(ir)
    object_chunk, maps, generation_counts = build_object_chunk_power_bridge(normalized_ir, templates, root)
    cdb = build_cdb(normalized_ir.components)
    dsn, section_pointers = build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    chunk_issues = validate_object_chunk_power_bridge(
        _extract_object_chunk(dsn),
        len(normalized_ir.components),
        maps,
        power_bridge_count=generation_counts["power_bridge_count"],
        visual_wire_count=generation_counts["visual_wire_count"],
    )

    output_dir = Path(outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    basename = normalized_ir.project.output_basename
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
        "proteusgen temporary resistor_v9 power-bridge method\n"
        "base_fixture=e001_empty\n"
        "donor_fixture=r21_v9_resistor_terminal_donor\n"
        f"power_bridge_donor={HANDOFF_ZIP}:{BRIDGE_DONOR_INTERNAL}\n",
        encoding="utf-8",
    )
    output_hashes = {
        output_path.name: _sha256_file(output_path),
        cdb_path.name: _sha256_file(cdb_path),
        dsn_path.name: _sha256_file(dsn_path),
        "base_project": _sha256_file(base.path),
        "donor_project": _sha256_file(donor.path),
        "bridge_donor_root_dsn": _sha256_bytes(_bridge_donor_root_dsn(root)),
    }
    manifest = {
        "schema_version": normalized_ir.schema_version,
        "generator_target": normalized_ir.generator_target,
        "project_name": normalized_ir.project.name,
        "output_basename": basename,
        "method": "temporary_power_bridge_ground_shortwire",
        "base_project": "E001_EMPTY_BASE",
        "base_fixture_id": base.id,
        "donor_fixture_id": donor.id,
        "power_bridge_donor": f"{HANDOFF_ZIP}:{BRIDGE_DONOR_INTERNAL}",
        "power_bridge_core_len_bytes": POWER_BRIDGE_CORE_SIZE,
        "power_bridge_count": generation_counts["power_bridge_count"],
        "power_nodes": generation_counts["power_nodes"],
        "node_count_requested": len(normalized_ir.nodes),
        "component_count_requested": len(normalized_ir.components),
        "component_count_emitted_cdb": len(normalized_ir.components),
        "component_count_emitted_dsn": len(normalized_ir.components),
        "terminal_count": len(normalized_ir.components) * 2 + generation_counts["power_bridge_count"] * 2,
        "input_terminal_count": len(normalized_ir.components),
        "output_terminal_count": len(normalized_ir.components)
        - generation_counts["ground_terminal_count"]
        + generation_counts["power_bridge_count"],
        "power_terminal_count": generation_counts["power_bridge_count"],
        "ground_terminal_count": generation_counts["ground_terminal_count"],
        "short_wire_count": len(normalized_ir.components) * 2,
        "bridge_wire_count": generation_counts["power_bridge_count"],
        "visual_wire_count": generation_counts["visual_wire_count"],
        "wire_count": len(normalized_ir.components) * 2
        + generation_counts["visual_wire_count"]
        + generation_counts["power_bridge_count"],
        "object_group_count": len(normalized_ir.components),
        "auto_placed_count": generation_counts["auto_placed"],
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
            "Temporary generator; do not promote until Proteus 8.13 open/save evidence is recorded.",
            "Only one two-character power node bridge is currently emitted.",
            "Ground terminals remain supported only on right endpoints.",
        ],
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, manifest_path.name, readme_path.name, version_path.name],
        "output_hashes": output_hashes,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        f"{basename}\n\n"
        "Temporary power-bridge resistor generator output.\n\n"
        "Endpoint rules under test:\n"
        "- Powered resistor endpoints remain normal $TERINPUT(V0) terminals.\n"
        "- One donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge connects the power node.\n"
        "- G0/ground nodes on component.nodes[1] become $TERGROUND endpoints with the normal short wire.\n",
        encoding="utf-8",
    )
    return ResistorGenerationResult(
        output_path=output_path,
        cdb_path=cdb_path,
        dsn_path=dsn_path,
        manifest_path=manifest_path,
        readme_path=readme_path,
        version_path=version_path,
        manifest=manifest,
    )


def generate_resistor_project_from_payload_power_bridge_temp(payload: Any, outdir: str | Path) -> ResistorGenerationResult:
    ir, issues = parse_resistor_ir(payload)
    if issues:
        raise ResistorGenerationBlocked(ResistorValidationReport(errors=tuple(issues), warnings=(), circuit=None))
    assert ir is not None
    return generate_resistor_project_power_bridge_temp(ir, outdir)


def main() -> int:
    parser = argparse.ArgumentParser(description="TEMP: generate V9 resistor project with donor power bridge.")
    parser.add_argument("--input", required=True, help="CircuitIR JSON input")
    parser.add_argument("--outdir", required=True, help="Output directory")
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    try:
        result = generate_resistor_project_from_payload_power_bridge_temp(payload, args.outdir)
    except ResistorGenerationBlocked as exc:
        print(json.dumps(exc.report.as_dict(), indent=2))
        return 2
    print(json.dumps(result.as_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
