"""Temporary capacitor V13 diagnostics: 15 requested networks with power/ground.

The user asked for wider horizontal/vertical component spacing and real
power/ground terminals after V12. V13 keeps the V10/V11 manual capacitor
terminal record order, but adds the locked resistor power/ground endpoint
method:

- one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
- powered capacitor endpoints remain ordinary $TERINPUT(V0)
- grounded right endpoints become $TERGROUND(G0)
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
TOOL_DIR_2026_05_30 = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-05-30"
TOOL_DIR_2026_05_31 = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-05-31"
for path in (REPO_ROOT / "proteus" / "active" / "src", TOOL_DIR_2026_05_30, TOOL_DIR_2026_05_31):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import generate_capacitor_v10_manual_donor_temp as v10
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import POWER_BRIDGE_CORE_SIZE, _extract_object_chunk, _load_power_bridge_core, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

SOURCE_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "requested_resistor_networks_oriented_2026_05_30"
OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "capacitor_v13_power_ground_spacing_temp_2026_05_31"
SAFE_X_STEP = 3810000
SAFE_Y_STEP = 3810000
BASE_X = -6858000
BASE_Y = 5080000


def cap_ref(index: int) -> str:
    if index <= 9:
        return f"C{index}"
    return f"C{chr(ord('A') + index - 10)}"


def cap_value(case_id: str, source_component: dict[str, Any], index: int) -> str:
    """Return a same-width visible capacitor value for topology diagnostics."""

    value = source_component.get("value", "")
    role = source_component.get("visual", {}).get("role", "")
    if case_id == "15_R_2R_LADDER_NETWORK":
        return "2uF" if "shunt" in role or "termination" in role else "1uF"
    if case_id == "12_BALANCED_WHEATSTONE_BRIDGE":
        return "1uF"
    if case_id == "13_UNBALANCED_WHEATSTONE_BRIDGE":
        mapping = {"R1": "1uF", "R2": "3uF", "R3": "2uF", "R4": "4uF", "R5": "1uF"}
        return mapping.get(source_component["ref"], "1uF")
    if case_id == "10_DELTA_TO_STAR_SETUP":
        return "3uF" if index <= 3 else "1uF"
    if value and value[0].isdigit() and value[0] != "0":
        digit = min(int(value[0]), 9)
        return f"{digit}uF"
    return "1uF"


def safe_positions(source: dict[str, Any]) -> dict[str, tuple[int, int]]:
    positions = source.get("layout", {}).get("component_positions", {})
    if not positions:
        return {
            component["ref"]: (BASE_X + (idx % 5) * SAFE_X_STEP, BASE_Y - (idx // 5) * SAFE_Y_STEP)
            for idx, component in enumerate(source["components"])
        }
    xs = sorted({pos["x"] for pos in positions.values()})
    ys = sorted({pos["y"] for pos in positions.values()}, reverse=True)
    x_map = {x: BASE_X + i * SAFE_X_STEP for i, x in enumerate(xs)}
    y_map = {y: BASE_Y - i * SAFE_Y_STEP for i, y in enumerate(ys)}
    used: dict[tuple[int, int], int] = {}
    out: dict[str, tuple[int, int]] = {}
    for idx, component in enumerate(source["components"]):
        raw = positions.get(component["ref"])
        if raw is None:
            x = BASE_X + (idx % 5) * SAFE_X_STEP
            y = BASE_Y - (idx // 5) * SAFE_Y_STEP
        else:
            x = x_map[raw["x"]]
            y = y_map[raw["y"]]
        duplicate_index = used.get((x, y), 0)
        used[(x, y)] = duplicate_index + 1
        if duplicate_index:
            x += duplicate_index * SAFE_X_STEP
        out[component["ref"]] = (x, y)
    return out


def convert_source_case(source_path: Path) -> tuple[str, dict[str, Any], list[v10.TerminalCapSpec]]:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    case_id = source_path.parent.name
    positions = safe_positions(source)
    specs: list[v10.TerminalCapSpec] = []
    for index, component in enumerate(source["components"], start=1):
        x, y = positions[component["ref"]]
        left, right = component["nodes"]
        specs.append(v10.TerminalCapSpec(cap_ref(index), cap_value(case_id, component, index), left, right, x, y))
    return case_id, source, specs


def node_list(specs: list[v10.TerminalCapSpec]) -> list[str]:
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


def patch_output_terminal(template: bytes, label: str, dx: int, dy: int, out_suffix: int, marker: bytes) -> bytes:
    record = bytearray(v10.v4.patch_output(template, label, dx, dy, out_suffix))
    if marker == b"$TERGROUND":
        marker_pos = record.find(b"$TEROUTPUT")
        if marker_pos < 0:
            raise RuntimeError("Manual capacitor output template does not contain $TEROUTPUT marker.")
        record[marker_pos : marker_pos + len(b"$TERGROUND")] = b"$TERGROUND"
    elif marker != b"$TEROUTPUT":
        raise ValueError("Capacitor output marker must be $TEROUTPUT or $TERGROUND.")
    return bytes(record)


def build_terminal_cap_chunk_power_ground(
    templates: v10.ManualCapTemplates,
    specs: list[v10.TerminalCapSpec],
    bridge_dsn: bytes,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    nodes = node_list(specs)
    power_nodes = [node for node in nodes if node == "V0"]
    if len(power_nodes) > 1:
        raise ValueError("V13 supports one distinct power node per generated project.")
    bridge_cores = [_load_power_bridge_core(bridge_dsn, "V0")] if power_nodes else []

    outputs: list[bytes] = []
    groups: list[bytes] = []
    maps: list[dict[str, Any]] = []
    ground_count = 0
    for index, spec in enumerate(specs, start=1):
        template_index = (index - 1) % 2
        in_suffix, out_suffix = v10.manual_suffixes(index)
        cap_template = templates.caps[template_index]
        dx = spec.x - v10.s32(cap_template, 332)
        dy = spec.y - v10.s32(cap_template, 336)
        output_marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
        if output_marker == b"$TERGROUND":
            ground_count += 1
        input_record = v10.v4.patch_input(templates.inputs[template_index], spec.left, dx, dy, in_suffix)
        output_record = patch_output_terminal(templates.outputs[template_index], spec.right, dx, dy, out_suffix, output_marker)
        cap_record = v10.patch_cap_record(cap_template, spec, index, dx, dy, in_suffix, out_suffix)
        wire_left = v10.v4.patch_wire(templates.wire_lefts[template_index], dx, dy, final=False)
        wire_right_full = v10.v4.patch_wire(templates.wire_rights[template_index], dx, dy, final=index == len(specs))
        wire_right = wire_right_full if index == len(specs) else wire_right_full[:-1]
        outputs.append(output_record)
        groups.extend([input_record, cap_record, wire_left, wire_right])
        maps.append(
            {
                "idx": index,
                "ref": spec.ref,
                "value": spec.value,
                "left": spec.left,
                "right": spec.right,
                "input_marker": "$TERINPUT",
                "output_marker": output_marker.decode("ascii"),
                "x": spec.x,
                "y": spec.y,
                "in_suffix": f"{in_suffix:04x}",
                "out_suffix": f"{out_suffix:04x}",
                "cap_visual_index_byte_344": index,
                "wire_right_len": len(wire_right),
            }
        )
    chunk = templates.header + b"".join(bridge_cores) + b"".join(outputs) + b"".join(groups)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        raise RuntimeError("Built V13 power/ground chunk has invalid start/final bytes.")
    counts = {
        "power_bridge_count": len(bridge_cores),
        "power_nodes": ["V0"] if bridge_cores else [],
        "ground_terminal_count": ground_count,
        "spacing": {"safe_x_step": SAFE_X_STEP, "safe_y_step": SAFE_Y_STEP},
    }
    return chunk, maps, counts


def validate_power_ground_chunk(chunk: bytes, cap_count: int, maps: list[dict[str, Any]], power_bridge_count: int) -> list[str]:
    issues: list[str] = []
    manual_part = chunk[:1] + chunk[1 + power_bridge_count * POWER_BRIDGE_CORE_SIZE :]
    ground_count = sum(1 for item in maps if item["output_marker"] == "$TERGROUND")
    expected_manual_len = (
        1
        + cap_count * v10.OUT_SIZE
        + cap_count * (v10.IN_SIZE + v10.CAP_SIZE + v10.WIRE_SIZE)
        + (cap_count - 1) * v10.TRIMMED_WIRE_SIZE
        + v10.WIRE_SIZE
    )
    if len(manual_part) != expected_manual_len:
        issues.append(f"manual capacitor part length {len(manual_part)} != {expected_manual_len}")
    if not manual_part or manual_part[0] != 0:
        issues.append("manual capacitor part does not start with 00")
    if not manual_part or manual_part[-1] != 0xFF:
        issues.append("manual capacitor part does not end with FF")
    first_input = manual_part.find(b"$TERINPUT")
    first_cap = manual_part.find(b"COMPONENT ID")
    output_positions = [pos for pos in (manual_part.find(b"$TEROUTPUT"), manual_part.find(b"$TERGROUND")) if pos >= 0]
    first_output = min(output_positions) if output_positions else -1
    if first_output < 0 or first_input < 0 or not first_output < first_input < first_cap:
        issues.append("manual capacitor object order is not outputs-first then input/cap groups")
    expected_len = (
        1
        + power_bridge_count * POWER_BRIDGE_CORE_SIZE
        + cap_count * v10.OUT_SIZE
        + cap_count * (v10.IN_SIZE + v10.CAP_SIZE + v10.WIRE_SIZE)
        + (cap_count - 1) * v10.TRIMMED_WIRE_SIZE
        + v10.WIRE_SIZE
    )
    if len(chunk) != expected_len:
        issues.append(f"object chunk length {len(chunk)} != {expected_len}")
    expected_counts = {
        "$TERPOWER": power_bridge_count,
        "$TEROUTPUT": cap_count - ground_count + power_bridge_count,
        "$TERGROUND": ground_count,
        "$TERINPUT": cap_count,
        "CAPACITOR": cap_count,
        "CAP10": cap_count,
        "WIRE": cap_count * 2 + power_bridge_count,
    }
    for marker, expected in expected_counts.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected:
            issues.append(f"{marker} count {actual} != {expected}")
    for index in range(power_bridge_count):
        bridge_end = 1 + (index + 1) * POWER_BRIDGE_CORE_SIZE - 1
        if chunk[bridge_end] != 0:
            issues.append(f"power bridge {index + 1} terminator {chunk[bridge_end]:02x}")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    return issues


def payload_for(case_id: str, source: dict[str, Any], specs: list[v10.TerminalCapSpec]) -> dict[str, Any]:
    return {
        "schema_version": "capacitor-network-temp/v13",
        "generator_target": "proteus-8.13-capacitor-v10-manual-terminal-order-power-ground",
        "project": {
            "name": case_id,
            "output_basename": case_id,
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "source_resistor_case": source["project"]["output_basename"],
        "nodes": [{"id": node, "kind": node_kind(node)} for node in node_list(specs)],
        "components": [
            {
                "ref": spec.ref,
                "type": "CAPACITOR",
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y, "orientation_hint": "horizontal_v10_only"},
            }
            for spec in specs
        ],
        "metadata": {
            "source": "requested_resistor_networks_oriented_2026_05_30 converted R->C",
            "method": "V10 manual donor outputs-first terminal-capacitor order plus locked power bridge and ground endpoint method",
            "spacing": {"safe_x_step": SAFE_X_STEP, "safe_y_step": SAFE_Y_STEP},
            "known_limitations": [
                "Uses terminal-label topology; no standalone bus/junction wires.",
                "Uses a real donor-derived power terminal bridge for V0 and $TERGROUND right endpoints for G0.",
            ],
        },
    }


def write_case(
    *,
    case_id: str,
    source: dict[str, Any],
    specs: list[v10.TerminalCapSpec],
    base_project: Path,
    donor_project: Path,
    bridge_dsn: bytes,
    templates: v10.ManualCapTemplates,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, maps, generation_counts = build_terminal_cap_chunk_power_ground(templates, specs, bridge_dsn)
    cdb = v10.build_cap_cdb(specs)
    dsn, pointers = build_dsn(
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
    input_path.write_text(json.dumps(payload_for(case_id, source, specs), indent=2) + "\n", encoding="utf-8")

    issues = validate_power_ground_chunk(object_chunk, len(specs), maps, generation_counts["power_bridge_count"])
    if _extract_object_chunk(dsn) != object_chunk:
        issues.append("rebuilt ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_capacitor_v13_power_ground_spacing_not_locked",
        "description": source.get("project", {}).get("name", case_id) + " converted to capacitors",
        "source_resistor_case": source.get("project", {}).get("output_basename", case_id),
        "base_project": base_project.name,
        "donor_header_project": donor_project.name,
        "capacitor_count": len(specs),
        "node_count": len(node_list(specs)),
        "power_bridge_count": generation_counts["power_bridge_count"],
        "power_terminal_count": generation_counts["power_bridge_count"],
        "ground_terminal_count": generation_counts["ground_terminal_count"],
        "bridge_wire_count": generation_counts["power_bridge_count"],
        "spacing": generation_counts["spacing"],
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "object_chunk": {
                "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
                "$TERPOWER": object_chunk.count(b"$TERPOWER"),
                "$TERINPUT": object_chunk.count(b"$TERINPUT"),
                "$TERGROUND": object_chunk.count(b"$TERGROUND"),
                "CAPACITOR": object_chunk.count(b"CAPACITOR"),
                "CAP10": object_chunk.count(b"CAP10"),
                "WIRE": object_chunk.count(b"WIRE"),
                "1uF": object_chunk.count(b"1uF"),
                "2uF": object_chunk.count(b"2uF"),
                "3uF": object_chunk.count(b"3uF"),
                "4uF": object_chunk.count(b"4uF"),
            },
            "root_cdb": {
                "CAPACITOR": cdb.count(b"CAPACITOR"),
                "CAP": cdb.count(b"CAP"),
                "CAP10": cdb.count(b"CAP10"),
                "1uF": cdb.count(b"1uF"),
                "2uF": cdb.count(b"2uF"),
                "3uF": cdb.count(b"3uF"),
                "4uF": cdb.count(b"4uF"),
            },
        },
        "section_pointer_values": pointers,
        "topology": maps,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: v10.sha256_file(output_path),
            cdb_path.name: v10.sha256_file(cdb_path),
            dsn_path.name: v10.sha256_file(dsn_path),
            "object_chunk": v10.sha256_bytes(object_chunk),
            "ROOT.CDB": v10.sha256_bytes(cdb),
            "power_bridge_donor": v10.sha256_bytes(bridge_dsn),
        },
        "output_files": [output_path.name, cdb_path.name, dsn_path.name, input_path.name, "manifest.json", "README_TEST_FIRST.txt"],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n"
        "Capacitor version of the matching requested resistor circuit.\n\n"
        "This V13 pack uses wider component spacing, one $TERPOWER -> $TEROUTPUT(V0) bridge, and $TERGROUND(G0) right endpoints.\n\n"
        f"Project: {output_path.name}\n"
        f"Capacitors: {len(specs)}\n"
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
    manual = registry.get("cap2_with_terminals_manual").path
    bridge = registry.get("power_terminal_bridge_donor").path
    templates = v10.load_manual_templates(manual)
    bridge_dsn = read_internal_file(bridge, "ROOT.DSN")
    cases: list[dict[str, Any]] = []
    for source_path in sorted(SOURCE_ROOT.glob("*/input.json")):
        case_id, source, specs = convert_source_case(source_path)
        cases.append(
            write_case(
                case_id=case_id,
                source=source,
                specs=specs,
                base_project=base,
                donor_project=manual,
                bridge_dsn=bridge_dsn,
                templates=templates,
            )
        )

    summary = {
        "case": "CAPACITOR_V13_POWER_GROUND_SPACING_TEMP_2026_05_31",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "User requested wider horizontal/vertical component spacing and power/ground terminal symbols for the 15 capacitor circuits.",
        "method": "Convert the accepted oriented 15 resistor topology inputs to V10 manual-order capacitor records, add the locked $TERPOWER -> $TEROUTPUT(V0) bridge, and emit G0 right endpoints as $TERGROUND.",
        "manual_donor": {
            "fixture_id": "cap2_with_terminals_manual",
            "project_sha256": v10.sha256_file(manual),
            "object_order": "all outputs first, then input/cap/left-wire/right-wire groups; non-final right wires are 49 bytes",
        },
        "power_bridge_donor": {
            "fixture_id": "power_terminal_bridge_donor",
            "project_sha256": v10.sha256_file(bridge),
            "core_len": POWER_BRIDGE_CORE_SIZE,
            "method": "one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge prepended after the object stream header",
        },
        "spacing": {"safe_x_step": SAFE_X_STEP, "safe_y_step": SAFE_Y_STEP},
        "limitations": [
            "Capacitor records are horizontal because capacitor rotation is not yet separately validated.",
            "Standalone bus/junction wires are not emitted.",
        ],
        "test_order": [case["case_id"] for case in cases],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Capacitor V13 power/ground + wider-spacing requested 15 network diagnostics.\n\n"
        "This pack uses one $TERPOWER -> $TEROUTPUT(V0) bridge, $TERGROUND(G0) right endpoints, and a 3810000-unit x/y component grid.\n\n"
        "Open in order:\n\n"
        + "\n".join(f"{idx:02d}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n\nReport the first failure, any exact Proteus error text, and whether the visible capacitor count matches each case.\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
