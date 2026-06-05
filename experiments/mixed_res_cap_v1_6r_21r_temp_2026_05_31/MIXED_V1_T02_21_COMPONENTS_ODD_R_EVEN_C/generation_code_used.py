"""Temporary mixed resistor/capacitor diagnostics for 6R and R21 topologies.

Odd-numbered components stay resistors. Even-numbered components become
capacitors. The pack uses the locked power/ground method:

- one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
- V0 component endpoints stay ordinary $TERINPUT(V0)
- G0 right endpoints become $TERGROUND(G0)

This is temporary because mixed resistor/capacitor terminal object ordering has
not yet been Proteus-accepted.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_DIR_2026_05_30 = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-30"
TOOL_DIR_2026_05_31 = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-31"
for path in (REPO_ROOT / "src", TOOL_DIR_2026_05_30, TOOL_DIR_2026_05_31):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_capacitor_v10_manual_donor_temp as v10
import generate_capacitor_v13_power_ground_spacing_temp as v13
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen import resistor_v9 as rv9
from proteusgen.resistor_ir import visible_resistor_value
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "mixed_res_cap_v1_6r_21r_temp_2026_05_31"
SOURCE_6R = REPO_ROOT / "experiments" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_21R = REPO_ROOT / "experiments" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SAFE_X_STEP = 3810000
SAFE_Y_STEP = 3810000
BASE_X = -6858000
BASE_Y = 5080000
CAP_VALUE = "1uF"


@dataclass(frozen=True)
class MixedSpec:
    idx: int
    source_ref: str
    ref: str
    kind: str
    value: str
    left: str
    right: str
    x: int
    y: int


def suffix_ref(prefix: str, index: int) -> str:
    if index <= 9:
        return f"{prefix}{index}"
    return f"{prefix}{chr(ord('A') + index - 10)}"


def safe_positions(source: dict[str, Any]) -> dict[str, tuple[int, int]]:
    positions = source.get("layout", {}).get("component_positions", {})
    xs = sorted({pos["x"] for pos in positions.values()})
    ys = sorted({pos["y"] for pos in positions.values()}, reverse=True)
    x_map = {x: BASE_X + index * SAFE_X_STEP for index, x in enumerate(xs)}
    y_map = {y: BASE_Y - index * SAFE_Y_STEP for index, y in enumerate(ys)}
    out: dict[str, tuple[int, int]] = {}
    for index, component in enumerate(source["components"]):
        raw = positions.get(component["ref"])
        if raw is None:
            out[component["ref"]] = (BASE_X + (index % 7) * SAFE_X_STEP, BASE_Y - (index // 7) * SAFE_Y_STEP)
        else:
            out[component["ref"]] = (x_map[raw["x"]], y_map[raw["y"]])
    return out


def convert_source(path: Path, output_basename: str) -> tuple[dict[str, Any], list[MixedSpec]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    positions = safe_positions(source)
    specs: list[MixedSpec] = []
    for idx, component in enumerate(source["components"], start=1):
        x, y = positions[component["ref"]]
        left, right = component["nodes"]
        is_resistor = idx % 2 == 1
        specs.append(
            MixedSpec(
                idx=idx,
                source_ref=component["ref"],
                ref=suffix_ref("R" if is_resistor else "C", idx),
                kind="RESISTOR" if is_resistor else "CAPACITOR",
                value=component["value"] if is_resistor else CAP_VALUE,
                left=left,
                right=right,
                x=x,
                y=y,
            )
        )
    source["project"]["name"] = output_basename
    source["project"]["output_basename"] = output_basename
    return source, specs


def node_list(specs: list[MixedSpec]) -> list[str]:
    nodes: list[str] = []
    for spec in specs:
        nodes.extend([spec.left, spec.right])
    return list(dict.fromkeys(nodes))


def node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def build_mixed_cdb(specs: list[MixedSpec]) -> bytes:
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + rv9._enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + rv9._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + rv9._enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(specs))
    for index, spec in enumerate(specs, start=1):
        out += rv9._u32(index) + rv9._u32(1) + rv9._u32(0) + rv9._u32(index) + rv9._enc_str(spec.ref)
        if spec.kind == "CAPACITOR":
            out += rv9._u32(2) + rv9._enc_str("2") + rv9._enc_str("2") + rv9._enc_str("1") + rv9._enc_str("1")
        else:
            out += rv9._u32(2) + rv9._enc_str("1") + b"\x00" + rv9._enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(index) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + rv9._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(specs))
    for index, spec in enumerate(specs, start=1):
        out += rv9._u32(index) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if spec.kind == "CAPACITOR":
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("CAP") + rv9._enc_str("CAP10") + rv9._enc_text(v10.v5.CAP_PROP_TEXT)
        else:
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("RESISTOR") + rv9._enc_str("") + rv9._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def build_resistor_records(
    *,
    spec: MixedSpec,
    ordinal: int,
    templates: rv9.V9Templates,
) -> tuple[bytes, bytes, bytes, bytes, bytes, dict[str, Any]]:
    left_pin_x, left_pin_y = spec.x, spec.y
    right_pin_x, right_pin_y = spec.x + 1270000, spec.y
    in_symbol_x, in_symbol_y = left_pin_x - 508000, left_pin_y
    out_symbol_x, out_symbol_y = right_pin_x + 508000, right_pin_y
    in_label_x, in_label_y = left_pin_x - 889000, left_pin_y
    out_label_x, out_label_y = right_pin_x + 889000, right_pin_y
    in_tip_x, in_tip_y = left_pin_x - 254000, left_pin_y
    out_tip_x, out_tip_y = right_pin_x + 254000, right_pin_y
    output_marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    input_record, in_suffix = rv9._patch_input(
        templates.input_terminals[(ordinal - 1) % 4],
        spec.left,
        in_symbol_x,
        in_symbol_y,
        in_label_x,
        in_label_y,
        ordinal,
        marker=b"$TERINPUT",
    )
    output_record, out_suffix = rv9._patch_output(
        templates.output_terminals[(ordinal - 1) % 4],
        spec.right,
        out_symbol_x,
        out_symbol_y,
        out_label_x,
        out_label_y,
        ordinal,
        marker=output_marker,
    )
    res_template, wire_left_template, wire_right_template = templates.groups[(ordinal - 1) % 4]
    visible = visible_resistor_value(spec.value, {})
    resistor_record = rv9._patch_resistor(res_template, ordinal, spec.ref, visible, spec.x, spec.y, 0, in_suffix, out_suffix)
    wire_left = rv9._patch_wire(wire_left_template, in_tip_x, in_tip_y, left_pin_x, left_pin_y)
    wire_right = rv9._patch_wire(wire_right_template, out_tip_x, out_tip_y, right_pin_x, right_pin_y)
    info = {
        "idx": spec.idx,
        "ordinal": ordinal,
        "ref": spec.ref,
        "source_ref": spec.source_ref,
        "kind": spec.kind,
        "value": spec.value,
        "visible_value": visible,
        "left": spec.left,
        "right": spec.right,
        "input_marker": "$TERINPUT",
        "output_marker": output_marker.decode("ascii"),
        "in_suffix": f"{in_suffix:04x}",
        "out_suffix": f"{out_suffix:04x}",
        "x": spec.x,
        "y": spec.y,
    }
    return input_record, output_record, resistor_record, wire_left, wire_right, info


def build_capacitor_records(
    *,
    spec: MixedSpec,
    ordinal: int,
    templates: v10.ManualCapTemplates,
    final_cap_in_cap_block: bool = False,
) -> tuple[bytes, bytes, bytes, bytes, bytes, dict[str, Any]]:
    template_index = (ordinal - 1) % 2
    in_suffix, out_suffix = v10.manual_suffixes(ordinal)
    cap_template = templates.caps[template_index]
    dx = spec.x - v10.s32(cap_template, 332)
    dy = spec.y - v10.s32(cap_template, 336)
    output_marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    input_record = v10.v4.patch_input(templates.inputs[template_index], spec.left, dx, dy, in_suffix)
    output_record = v13.patch_output_terminal(templates.outputs[template_index], spec.right, dx, dy, out_suffix, output_marker)
    cap_record = v10.patch_cap_record(
        cap_template,
        v10.TerminalCapSpec(spec.ref, spec.value, spec.left, spec.right, spec.x, spec.y),
        ordinal,
        dx,
        dy,
        in_suffix,
        out_suffix,
    )
    wire_left = v10.v4.patch_wire(templates.wire_lefts[template_index], dx, dy, final=False)
    wire_right_full = v10.v4.patch_wire(templates.wire_rights[template_index], dx, dy, final=final_cap_in_cap_block)
    wire_right = wire_right_full if final_cap_in_cap_block else wire_right_full[:-1]
    info = {
        "idx": spec.idx,
        "ordinal": ordinal,
        "ref": spec.ref,
        "source_ref": spec.source_ref,
        "kind": spec.kind,
        "value": spec.value,
        "left": spec.left,
        "right": spec.right,
        "input_marker": "$TERINPUT",
        "output_marker": output_marker.decode("ascii"),
        "in_suffix": f"{in_suffix:04x}",
        "out_suffix": f"{out_suffix:04x}",
        "cap_visual_index_byte_344": ordinal,
        "wire_right_len": len(wire_right),
        "x": spec.x,
        "y": spec.y,
    }
    return output_record, input_record, cap_record, wire_left, wire_right, info


def build_mixed_object_chunk(
    specs: list[MixedSpec],
    *,
    cap_templates: v10.ManualCapTemplates,
    res_templates: rv9.V9Templates,
    bridge_dsn: bytes,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    bridge_core = rv9._load_power_bridge_core(bridge_dsn, "V0")
    cap_outputs: list[bytes] = []
    cap_groups: list[bytes] = []
    res_inputs: list[bytes] = []
    res_outputs: list[bytes] = []
    res_groups: list[bytes] = []
    topology: list[dict[str, Any]] = []
    cap_ordinal = 0
    res_ordinal = 0

    for spec in specs:
        if spec.kind == "CAPACITOR":
            cap_ordinal += 1
            output_record, input_record, cap_record, wire_left, wire_right, info = build_capacitor_records(
                spec=spec,
                ordinal=cap_ordinal,
                templates=cap_templates,
                final_cap_in_cap_block=False,
            )
            cap_outputs.append(output_record)
            cap_groups.extend([input_record, cap_record, wire_left, wire_right])
            topology.append(info)
        else:
            res_ordinal += 1
            input_record, output_record, resistor_record, wire_left, wire_right, info = build_resistor_records(
                spec=spec,
                ordinal=res_ordinal,
                templates=res_templates,
            )
            res_inputs.append(input_record)
            res_outputs.append(output_record)
            res_groups.extend([resistor_record, wire_left, wire_right])
            topology.append(info)

    chunk = bytearray(
        cap_templates.header
        + bridge_core
        + b"".join(cap_outputs)
        + b"".join(cap_groups)
        + b"".join(res_inputs)
        + b"".join(res_outputs)
        + res_templates.separator
        + b"".join(res_groups)
    )
    chunk[-1] = 0xFF
    counts = {
        "power_bridge_count": 1,
        "resistor_count": res_ordinal,
        "capacitor_count": cap_ordinal,
        "ground_terminal_count": sum(1 for item in topology if item["output_marker"] == "$TERGROUND"),
        "spacing": {"safe_x_step": SAFE_X_STEP, "safe_y_step": SAFE_Y_STEP},
        "object_order": "header, power bridge, capacitor output array, capacitor groups, resistor input array, resistor output array, separator, resistor groups",
    }
    return bytes(chunk), topology, counts


def validate_mixed_chunk(chunk: bytes, topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    resistor_count = counts["resistor_count"]
    capacitor_count = counts["capacitor_count"]
    ground_count = counts["ground_terminal_count"]
    expected_len = (
        1
        + rv9.POWER_BRIDGE_CORE_SIZE
        + capacitor_count * v10.OUT_SIZE
        + capacitor_count * (v10.IN_SIZE + v10.CAP_SIZE + v10.WIRE_SIZE + v10.TRIMMED_WIRE_SIZE)
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
        "$TERPOWER": 1,
        "$TEROUTPUT": len(topology) - ground_count + 1,
        "$TERGROUND": ground_count,
        "$TERINPUT": len(topology),
        "CAPACITOR": capacitor_count,
        "CAP10": capacitor_count,
        "COMPONENT ID": len(topology),
        "WIRE": len(topology) * 2 + 1,
    }
    for marker, expected in expected_counts.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected:
            issues.append(f"{marker} count {actual} != {expected}")
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE - 1
    if chunk[bridge_end] != 0:
        issues.append(f"power bridge terminator {chunk[bridge_end]:02x}")
    for item in topology:
        if item["kind"] == "CAPACITOR" and item["wire_right_len"] != v10.TRIMMED_WIRE_SIZE:
            issues.append(f"{item['ref']} non-final capacitor right wire len {item['wire_right_len']}")
    return issues


def payload_for(case_id: str, source: dict[str, Any], specs: list[MixedSpec], counts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-passive-temp/v1",
        "generator_target": "proteus-8.13-mixed-resistor-capacitor-terminal-power-ground",
        "project": {
            "name": case_id,
            "output_basename": case_id,
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "source_resistor_case": source["metadata"]["case_id"],
        "nodes": [{"id": node, "kind": node_kind(node)} for node in node_list(specs)],
        "components": [
            {
                "idx": spec.idx,
                "source_ref": spec.source_ref,
                "ref": spec.ref,
                "type": spec.kind,
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y, "orientation_hint": "horizontal"},
            }
            for spec in specs
        ],
        "metadata": {
            "method": "odd components use resistor V9 records; even components use V10/V13 capacitor terminal records; one power bridge and G0 ground endpoints",
            "object_order": counts["object_order"],
            "spacing": counts["spacing"],
        },
    }


def write_case(
    *,
    case_id: str,
    description: str,
    source: dict[str, Any],
    specs: list[MixedSpec],
    base_project: Path,
    donor_project: Path,
    cap_templates: v10.ManualCapTemplates,
    res_templates: rv9.V9Templates,
    bridge_dsn: bytes,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, topology, counts = build_mixed_object_chunk(
        specs,
        cap_templates=cap_templates,
        res_templates=res_templates,
        bridge_dsn=bridge_dsn,
    )
    cdb = build_mixed_cdb(specs)
    dsn, pointers = rv9.build_dsn(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    input_path = case_dir / "input.json"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    input_path.write_text(json.dumps(payload_for(case_id, source, specs, counts), indent=2) + "\n", encoding="utf-8")

    issues = validate_mixed_chunk(object_chunk, topology, counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("rebuilt ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_res_cap_v1_not_locked",
        "description": description,
        "base_project": base_project.name,
        "donor_header_project": donor_project.name,
        "resistor_count": counts["resistor_count"],
        "capacitor_count": counts["capacitor_count"],
        "component_count": len(specs),
        "node_count": len(node_list(specs)),
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "spacing": counts["spacing"],
        "object_order": counts["object_order"],
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "object_chunk": {
                "$TERPOWER": object_chunk.count(b"$TERPOWER"),
                "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
                "$TERINPUT": object_chunk.count(b"$TERINPUT"),
                "$TERGROUND": object_chunk.count(b"$TERGROUND"),
                "COMPONENT ID": object_chunk.count(b"COMPONENT ID"),
                "RESISTOR": object_chunk.count(b"RESISTOR"),
                "CAPACITOR": object_chunk.count(b"CAPACITOR"),
                "CAP10": object_chunk.count(b"CAP10"),
                "WIRE": object_chunk.count(b"WIRE"),
                "1uF": object_chunk.count(b"1uF"),
            },
            "root_cdb": {
                "RESISTOR": cdb.count(b"RESISTOR"),
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP10": cdb.count(b"CAP10"),
                "1uF": cdb.count(b"1uF"),
            },
        },
        "section_pointer_values": pointers,
        "topology": sorted(topology, key=lambda item: item["idx"]),
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: v10.sha256_file(output_path),
            cdb_path.name: v10.sha256_file(cdb_path),
            dsn_path.name: v10.sha256_file(dsn_path),
            "object_chunk": v10.sha256_bytes(object_chunk),
            "ROOT.CDB": v10.sha256_bytes(cdb),
        },
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, input_path.name, "manifest.json", "README_TEST_FIRST.txt", "generation_code_used.py"],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n"
        f"{description}\n\n"
        f"Project: {output_path.name}\n"
        f"Components: {len(specs)} ({counts['resistor_count']} resistors, {counts['capacitor_count']} capacitors)\n"
        f"Static validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    base = registry.get("e001_empty").path
    cap_manual = registry.get("cap2_with_terminals_manual").path
    resistor_donor = registry.get("r21_v9_resistor_terminal_donor").path
    bridge = registry.get("power_terminal_bridge_donor").path
    cap_templates = v10.load_manual_templates(cap_manual)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    bridge_dsn = read_internal_file(bridge, "ROOT.DSN")

    source_6, specs_6 = convert_source(SOURCE_6R, "MIXED_V1_T01_6_COMPONENTS_ODD_R_EVEN_C")
    source_21, specs_21 = convert_source(SOURCE_21R, "MIXED_V1_T02_21_COMPONENTS_ODD_R_EVEN_C")
    cases = [
        write_case(
            case_id="MIXED_V1_T01_6_COMPONENTS_ODD_R_EVEN_C",
            description="Six-component 6R topology with odd components as resistors and even components as capacitors.",
            source=source_6,
            specs=specs_6,
            base_project=base,
            donor_project=resistor_donor,
            cap_templates=cap_templates,
            res_templates=res_templates,
            bridge_dsn=bridge_dsn,
        ),
        write_case(
            case_id="MIXED_V1_T02_21_COMPONENTS_ODD_R_EVEN_C",
            description="Twenty-one-component R21 topology with odd components as resistors and even components as capacitors.",
            source=source_21,
            specs=specs_21,
            base_project=base,
            donor_project=resistor_donor,
            cap_templates=cap_templates,
            res_templates=res_templates,
            bridge_dsn=bridge_dsn,
        ),
    ]

    summary = {
        "case": "MIXED_RES_CAP_V1_6R_21R_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "User requested the 6R and 21R circuits with odd components as resistors and even components as capacitors, with power and ground terminals.",
        "method": "Use resistor V9 records for odd-indexed components, capacitor V10/V13 manual-order records for even-indexed components, one power bridge, and G0 ground endpoints.",
        "object_order": cases[0]["object_order"],
        "spacing": {"safe_x_step": SAFE_X_STEP, "safe_y_step": SAFE_Y_STEP},
        "limitations": [
            "Mixed resistor/capacitor terminal object order is new and not yet user-accepted.",
            "Capacitor records are horizontal; resistor records are horizontal for these source topologies.",
            "Standalone bus/junction wires are not emitted.",
        ],
        "test_order": [case["case_id"] for case in cases],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed resistor/capacitor V1 diagnostics.\n\n"
        "Odd-numbered components are resistors; even-numbered components are capacitors. Both use one $TERPOWER -> $TEROUTPUT(V0) bridge and $TERGROUND(G0) right endpoints.\n\n"
        "Open in order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n\nReport the first failure, any exact Proteus error text, and whether the visible odd/even R/C counts match each case.\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
