"""Generate scaled mixed R/C/L diagnostics with R/L inputs first.

V12 fixed the single 1C+1L+1R netlist identity case by using global component
IDs and object-order CDB entries. User feedback then narrowed the remaining
failure to circuits with additional R, C, or L components.

V13 keeps V12's global IDs and CDB ordering, but changes the scaled R/L order:
all R/L input terminals are emitted first across every native pair, then each
L/R output/component body is emitted. This tests the hypothesis that repeating
complete one-pair donor blocks is invalid for multi-pair layouts.

The CDB component tables are written in the same component order and with the
same global IDs. This is still temporary; promotion waits for user Proteus
netlist/simulation acceptance.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_passive as mp
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_ir import visible_resistor_value
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v13_rl_inputs_first_temp_2026_06_02"
SOURCE_6R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_21R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_15_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "requested_resistor_networks_oriented_2026_05_30"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")
V10_PATH = Path(__file__).with_name("generate_mixed_rcl_v10_terminal_rl_donor_temp.py")

SAFE_X_STEP = 3810000
SAFE_Y_STEP = 2540000
BASE_X = -7366000
BASE_Y = 5080000
CAP_VALUE = "1uF"


@dataclass(frozen=True)
class RawItem:
    source_ref: str
    kind: str
    source_value: str
    left: str
    right: str
    x: int
    y: int
    visual_data: dict[str, Any]


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {name} from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "WIRE",
        "RESISTOR",
        "REALIND",
        "CAPACITOR",
        "CAP10",
        "COMPONENT ID",
        "COMPONENT VALUE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _safe_positions(source: dict[str, Any]) -> dict[str, tuple[int, int]]:
    positions = source.get("layout", {}).get("component_positions", {})
    xs = sorted({pos["x"] for pos in positions.values()})
    ys = sorted({pos["y"] for pos in positions.values()}, reverse=True)
    x_map = {x: BASE_X + index * SAFE_X_STEP for index, x in enumerate(xs)}
    y_map = {y: BASE_Y - index * SAFE_Y_STEP for index, y in enumerate(ys)}
    used: set[tuple[int, int]] = set()
    out: dict[str, tuple[int, int]] = {}
    for index, component in enumerate(source["components"]):
        raw = positions.get(component["ref"])
        if raw is None:
            x, y = BASE_X + (index % 7) * SAFE_X_STEP, BASE_Y - (index // 7) * SAFE_Y_STEP
        else:
            x, y = x_map[raw["x"]], y_map[raw["y"]]
        while (x, y) in used:
            y -= SAFE_Y_STEP
        used.add((x, y))
        out[component["ref"]] = (x, y)
    return out


def _new_node(used: set[str]) -> str:
    for prefix in ("X", "Y", "Z", "U", "W"):
        for number in range(1, 10):
            node = f"{prefix}{number}"
            if node not in used:
                used.add(node)
                return node
    raise RuntimeError("Ran out of two-character generated node labels.")


def _balanced_kinds(count: int) -> list[str]:
    kinds: list[str] = []
    full = count // 3
    for _ in range(full):
        kinds.extend(["RESISTOR", "CAPACITOR", "INDUCTOR"])
    rem = count % 3
    if rem == 1:
        kinds.append("CAPACITOR")
    elif rem == 2:
        kinds.extend(["RESISTOR", "INDUCTOR"])
    if len(kinds) != count:
        raise AssertionError("balanced kind assignment length mismatch")
    if kinds.count("RESISTOR") != kinds.count("INDUCTOR"):
        raise AssertionError("scaled R/C/L generation requires paired R/L counts")
    return kinds


def _component_raw_item(component: dict[str, Any], kind: str, x: int, y: int) -> RawItem:
    left, right = component["nodes"]
    return RawItem(
        source_ref=component["ref"],
        kind=kind,
        source_value=component.get("value", "1k"),
        left=left,
        right=right,
        x=x,
        y=y,
        visual_data=dict(component.get("visual", {})),
    )


def _raw_items(source: dict[str, Any], *, require_all_three: bool) -> tuple[list[RawItem], list[str]]:
    components = source["components"]
    positions = _safe_positions(source)
    used_nodes = {node for component in components for node in component["nodes"]}
    notes: list[str] = []

    if require_all_three and len(components) == 1:
        component = components[0]
        left, right = component["nodes"]
        mid_1 = _new_node(used_nodes)
        mid_2 = _new_node(used_nodes)
        x, y = positions[component["ref"]]
        notes.append("Expanded the one-component source into R/C/L series so the output exercises all three families.")
        return [
            RawItem(component["ref"], "RESISTOR", component.get("value", "1k"), left, mid_1, x, y, dict(component.get("visual", {}))),
            RawItem(component["ref"], "CAPACITOR", component.get("value", "1k"), mid_1, mid_2, x + SAFE_X_STEP, y, {}),
            RawItem(component["ref"], "INDUCTOR", component.get("value", "1k"), mid_2, right, x + 2 * SAFE_X_STEP, y, {}),
        ], notes

    if require_all_three and len(components) == 2:
        first, second = components
        mid = _new_node(used_nodes)
        x1, y1 = positions[first["ref"]]
        x2, y2 = positions[second["ref"]]
        left_1, right_1 = first["nodes"]
        left_2, right_2 = second["nodes"]
        notes.append("Expanded the two-component source into three mixed components by splitting the second branch into C then L.")
        return [
            RawItem(first["ref"], "RESISTOR", first.get("value", "1k"), left_1, right_1, x1, y1, dict(first.get("visual", {}))),
            RawItem(second["ref"], "CAPACITOR", second.get("value", "1k"), left_2, mid, x2, y2, dict(second.get("visual", {}))),
            RawItem(second["ref"], "INDUCTOR", second.get("value", "1k"), mid, right_2, x2 + SAFE_X_STEP, y2, {}),
        ], notes

    kinds = _balanced_kinds(len(components))
    return [
        _component_raw_item(component, kinds[index], *positions[component["ref"]])
        for index, component in enumerate(components)
    ], notes


def _dedupe_positions(items: list[RawItem]) -> list[RawItem]:
    used: set[tuple[int, int]] = set()
    out: list[RawItem] = []
    for item in items:
        x, y = item.x, item.y
        while (x, y) in used:
            y -= SAFE_Y_STEP
        used.add((x, y))
        out.append(RawItem(item.source_ref, item.kind, item.source_value, item.left, item.right, x, y, item.visual_data))
    return out


def _suffix_ref(prefix: str, index: int) -> str:
    if index <= 9:
        return f"{prefix}{index}"
    return f"{prefix}{chr(ord('A') + index - 10)}"


def _visible_inductor_from_resistor(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    number = int(digits or "1")
    if number >= 10:
        return "9mH"
    return f"{number}mH"


def _value_for_item(item: RawItem) -> tuple[str, str]:
    if item.kind == "RESISTOR":
        value = item.source_value
        return value, visible_resistor_value(value, item.visual_data)
    if item.kind == "CAPACITOR":
        return CAP_VALUE, "1uF"
    value = _visible_inductor_from_resistor(item.source_value)
    return value, value


def _convert_source(v2: Any, path: Path, *, require_all_three: bool) -> tuple[dict[str, Any], list[Any], list[str]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    items, notes = _raw_items(source, require_all_three=require_all_three)
    items = _dedupe_positions(items)
    prefix = {"RESISTOR": "R", "CAPACITOR": "C", "INDUCTOR": "L"}
    counters = {"RESISTOR": 0, "CAPACITOR": 0, "INDUCTOR": 0}
    specs: list[Any] = []
    for index, item in enumerate(items, start=1):
        value, visible = _value_for_item(item)
        counters[item.kind] += 1
        specs.append(
            v2.RclSpec(
                idx=index,
                source_ref=item.source_ref,
                ref=_suffix_ref(prefix[item.kind], counters[item.kind]),
                kind=item.kind,
                value=value,
                visible_value=visible,
                left=item.left,
                right=item.right,
                x=item.x,
                y=item.y,
                visual_data=item.visual_data,
            )
        )
    return source, specs, notes


def _nodes(specs: list[Any]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _emission_order(specs: list[Any]) -> list[tuple[int, Any]]:
    """Return (global_component_id, spec) in DSN object-emission order."""
    caps = [spec for spec in specs if spec.kind == "CAPACITOR"]
    resistors = [spec for spec in specs if spec.kind == "RESISTOR"]
    inductors = [spec for spec in specs if spec.kind == "INDUCTOR"]
    if len(resistors) != len(inductors):
        raise RuntimeError("V13 requires paired resistor/inductor counts.")

    ordered: list[Any] = []
    ordered.extend(caps)
    for r_spec, l_spec in zip(resistors, inductors):
        ordered.extend([l_spec, r_spec])
    return [(index, spec) for index, spec in enumerate(ordered, start=1)]


def _global_ids_by_source_idx(specs: list[Any]) -> dict[int, int]:
    return {spec.idx: global_id for global_id, spec in _emission_order(specs)}


def _build_rcl_cdb_global(specs: list[Any], v8: Any) -> bytes:
    emissions = _emission_order(specs)
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + rv9._enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + rv9._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + rv9._enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(emissions))
    for global_id, spec in emissions:
        out += rv9._u32(global_id) + rv9._u32(1) + rv9._u32(0) + rv9._u32(global_id) + rv9._enc_str(spec.ref)
        if spec.kind == "CAPACITOR":
            out += rv9._u32(2) + rv9._enc_str("2") + rv9._enc_str("2") + rv9._enc_str("1") + rv9._enc_str("1")
        else:
            out += rv9._u32(2) + rv9._enc_str("1") + b"\x00" + rv9._enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(global_id) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + rv9._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(emissions))
    for global_id, spec in emissions:
        out += rv9._u32(global_id) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if spec.kind == "CAPACITOR":
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("CAP") + rv9._enc_str("CAP10") + rv9._enc_text(mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("REALIND") + rv9._enc_str("") + rv9._enc_text(v8.IND_PROP_TEXT)
        else:
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("RESISTOR") + rv9._enc_str("") + rv9._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _terminal_suffix(record: bytes) -> int:
    return int.from_bytes(record[-4:-2], "little")


def _patch_wire(v10: Any, template: bytes, x1: int, y1: int, x2: int, y2: int, *, final: bool) -> bytes:
    return v10._patch_wire(template, x1, y1, x2, y2, final=final)


def _rl_suffixes(templates: Any, pair_index: int) -> tuple[int, int, int, int]:
    l_in_base = _terminal_suffix(templates.l_input)
    l_out_base = _terminal_suffix(templates.l_output)
    r_in_base = _terminal_suffix(templates.r_input)
    r_out_base = _terminal_suffix(templates.r_output)
    component_step = r_in_base - l_in_base
    pair_step = component_step * 2
    offset = (pair_index - 1) * pair_step
    return (
        (l_in_base + offset) & 0xFFFF,
        (l_out_base + offset) & 0xFFFF,
        (r_in_base + offset) & 0xFFFF,
        (r_out_base + offset) & 0xFFFF,
    )


def _build_rl_pair_block(
    *,
    pair_index: int,
    pair_count: int,
    r_global_id: int,
    l_global_id: int,
    r_spec: Any,
    l_spec: Any,
    templates: Any,
    v8: Any,
    v10: Any,
) -> tuple[bytes, list[dict[str, Any]]]:
    l_in_suffix, l_out_suffix, r_in_suffix, r_out_suffix = _rl_suffixes(templates, pair_index)

    l_input = v8._patch_input(templates.l_input, l_spec.left, l_global_id, l_spec.x, l_spec.y, l_in_suffix)
    l_output_marker = b"$TERGROUND" if l_spec.right == "G0" else b"$TEROUTPUT"
    l_output = v8._patch_output(templates.l_output, l_spec.right, l_global_id, l_spec.x, l_spec.y, l_output_marker, l_out_suffix)
    l_ind_spec = v8.IndSpec(
        idx=l_spec.idx,
        source_ref=l_spec.source_ref,
        ref=l_spec.ref,
        value=l_spec.value,
        visible_value=l_spec.visible_value,
        left=l_spec.left,
        right=l_spec.right,
        x=l_spec.x,
        y=l_spec.y,
    )
    l_inductor = v8._patch_inductor(templates.l_inductor, l_ind_spec, l_global_id, l_in_suffix, l_out_suffix)
    l_left_pin_x = l_spec.x - 762000
    l_right_pin_x = l_spec.x + 762000
    l_wire_left = _patch_wire(v10, templates.l_wire_left, l_left_pin_x, l_spec.y, l_left_pin_x, l_spec.y, final=False)
    l_wire_right = _patch_wire(
        v10,
        templates.l_wire_right_trimmed,
        l_right_pin_x + 254000,
        l_spec.y,
        l_right_pin_x,
        l_spec.y,
        final=False,
    )

    r_input = v8._patch_input(templates.r_input, r_spec.left, r_global_id, r_spec.x, r_spec.y, r_in_suffix)
    r_output_marker = b"$TERGROUND" if r_spec.right == "G0" else b"$TEROUTPUT"
    r_output = v8._patch_output(templates.r_output, r_spec.right, r_global_id, r_spec.x, r_spec.y, r_output_marker, r_out_suffix)
    r_resistor = rv9._patch_resistor(
        templates.r_resistor,
        r_global_id,
        r_spec.ref,
        r_spec.visible_value,
        r_spec.x,
        r_spec.y,
        0,
        r_in_suffix,
        r_out_suffix,
    )
    r_left_pin_x = r_spec.x - 762000
    r_right_pin_x = r_spec.x + 762000
    r_wire_left = _patch_wire(v10, templates.r_wire_left, r_left_pin_x, r_spec.y, r_left_pin_x, r_spec.y, final=False)
    r_wire_right = _patch_wire(
        v10,
        templates.r_wire_right,
        r_right_pin_x + 254000,
        r_spec.y,
        r_right_pin_x,
        r_spec.y,
        final=pair_index == pair_count,
    )

    block = (
        l_input
        + r_input
        + l_output
        + l_inductor
        + l_wire_left
        + l_wire_right
        + r_output
        + templates.r_resistor_prefix
        + r_resistor
        + r_wire_left
        + r_wire_right
    )
    maps = [
        {
            "idx": l_spec.idx,
            "kind": "INDUCTOR",
            "ref": l_spec.ref,
            "value": l_spec.value,
            "left": l_spec.left,
            "right": l_spec.right,
            "global_id": l_global_id,
            "input_marker": "$TERINPUT",
            "output_marker": l_output_marker.decode("ascii"),
            "in_suffix": f"{l_in_suffix:04x}",
            "out_suffix": f"{l_out_suffix:04x}",
            "x": l_spec.x,
            "y": l_spec.y,
            "rl_pair_index": pair_index,
        },
        {
            "idx": r_spec.idx,
            "kind": "RESISTOR",
            "ref": r_spec.ref,
            "value": r_spec.value,
            "left": r_spec.left,
            "right": r_spec.right,
            "global_id": r_global_id,
            "input_marker": "$TERINPUT",
            "output_marker": r_output_marker.decode("ascii"),
            "in_suffix": f"{r_in_suffix:04x}",
            "out_suffix": f"{r_out_suffix:04x}",
            "x": r_spec.x,
            "y": r_spec.y,
            "rl_pair_index": pair_index,
        },
    ]
    return block, maps


def _build_object_chunk(
    specs: list[Any],
    *,
    cap_templates: Any,
    rl_templates: Any,
    bridge_core: bytes,
    v8: Any,
    v10: Any,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    cap_outputs: list[bytes] = []
    cap_groups: list[bytes] = []
    topology: list[dict[str, Any]] = []
    global_ids = _global_ids_by_source_idx(specs)
    cap_ordinal = 0
    ground_nodes = {"G0"}
    for spec in specs:
        if spec.kind != "CAPACITOR":
            continue
        cap_ordinal += 1
        global_id = global_ids[spec.idx]
        output_record, group, info = mp._build_capacitor_records(
            spec,
            ordinal=global_id,
            x=spec.x,
            y=spec.y,
            templates=cap_templates,
            ground_nodes=ground_nodes,
        )
        cap_outputs.append(output_record)
        cap_groups.extend(group)
        info.update({"idx": spec.idx, "ordinal": cap_ordinal, "global_id": global_id, "source_ref": spec.source_ref})
        topology.append(info)

    resistors = [spec for spec in specs if spec.kind == "RESISTOR"]
    inductors = [spec for spec in specs if spec.kind == "INDUCTOR"]
    if len(resistors) != len(inductors):
        raise RuntimeError("V13 requires paired resistor/inductor counts.")
    rl_input_blocks: list[bytes] = []
    rl_body_blocks: list[bytes] = []
    for pair_index, (r_spec, l_spec) in enumerate(zip(resistors, inductors), start=1):
        block, maps = _build_rl_pair_block(
            pair_index=pair_index,
            pair_count=len(resistors),
            r_global_id=global_ids[r_spec.idx],
            l_global_id=global_ids[l_spec.idx],
            r_spec=r_spec,
            l_spec=l_spec,
            templates=rl_templates,
            v8=v8,
            v10=v10,
        )
        input_len = 2 * v10.IN_SIZE
        rl_input_blocks.append(block[:input_len])
        rl_body_blocks.append(block[input_len:])
        topology.extend(maps)

    object_order = "header, power bridge, capacitor outputs, capacitor groups, all native R/L inputs, then native L/R output-component bodies with global component IDs"
    chunk = bytearray(
        rl_templates.header
        + bridge_core
        + b"".join(cap_outputs)
        + b"".join(cap_groups)
        + b"".join(rl_input_blocks)
        + b"".join(rl_body_blocks)
    )
    chunk[-1] = 0xFF
    topology = sorted(topology, key=lambda item: item["idx"])
    counts = {
        "object_order": object_order,
        "power_bridge_count": 1,
        "resistor_count": len(resistors),
        "capacitor_count": cap_ordinal,
        "inductor_count": len(inductors),
        "ground_terminal_count": sum(1 for item in topology if item["output_marker"] == "$TERGROUND"),
        "rl_pair_count": len(resistors),
        "emission_order": [
            {"global_id": global_id, "idx": spec.idx, "kind": spec.kind, "ref": spec.ref}
            for global_id, spec in _emission_order(specs)
        ],
    }
    return bytes(chunk), topology, counts


def _validate_chunk(chunk: bytes, topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    ground = counts["ground_terminal_count"]
    expected = {
        "$TERPOWER": counts["power_bridge_count"],
        "$TERINPUT": len(topology),
        "$TEROUTPUT": len(topology) - ground + counts["power_bridge_count"],
        "$TERGROUND": ground,
        "WIRE": len(topology) * 2 + counts["power_bridge_count"],
        "CAPACITOR": counts["capacitor_count"],
        "CAP10": counts["capacitor_count"],
        "REALIND": counts["inductor_count"] * 3,
        "RESISTOR": counts["resistor_count"] * 2,
        "COMPONENT ID": len(topology),
        "COMPONENT VALUE": len(topology),
    }
    actual = _marker_counts(chunk)
    for marker, want in expected.items():
        got = actual[marker]
        if got != want:
            issues.append(f"{marker} count {got} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if len({item["ref"] for item in topology}) != len(topology):
        issues.append("component refs are not unique")
    if len({item["global_id"] for item in topology}) != len(topology):
        issues.append("component global IDs are not unique")
    expected_global_ids = set(range(1, len(topology) + 1))
    actual_global_ids = {item["global_id"] for item in topology}
    if actual_global_ids != expected_global_ids:
        issues.append(f"component global IDs {sorted(actual_global_ids)} != {sorted(expected_global_ids)}")
    emission_global_ids = {item["global_id"] for item in counts["emission_order"]}
    if emission_global_ids != actual_global_ids:
        issues.append("emission order global IDs do not match topology global IDs")
    if len({item["in_suffix"] for item in topology}) != len(topology):
        issues.append("input suffixes are not globally unique")
    if len({item["out_suffix"] for item in topology}) != len(topology):
        issues.append("output suffixes are not globally unique")
    return issues


def _payload(case_id: str, source: dict[str, Any], specs: list[Any], counts: dict[str, Any], notes: list[str], topology: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v13-rl-inputs-first",
        "generator_target": "proteus-8.13-scaled-mixed-rcl-rl-inputs-first-netlist-diagnostic",
        "case_id": case_id,
        "source_resistor_case": source.get("metadata", {}).get("case_id", source.get("project", {}).get("output_basename")),
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _nodes(specs)],
        "components": [
            {
                "idx": spec.idx,
                "source_ref": spec.source_ref,
                "ref": spec.ref,
                "type": spec.kind,
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y, **spec.visual_data},
            }
            for spec in specs
        ],
        "metadata": {
            "method": "mixed R/C/L using accepted capacitor block and V10 native R/L pair records, with all R/L inputs collected before L/R bodies, one global component ID sequence, and object-order CDB",
            "object_order": counts["object_order"],
            "emission_order": counts["emission_order"],
            "temporary": True,
            "conversion_notes": notes,
            "topology": topology,
        },
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    source: dict[str, Any],
    specs: list[Any],
    notes: list[str],
    base_project: Path,
    donor_header_project: Path,
    cap_templates: Any,
    rl_templates: Any,
    bridge_core: bytes,
    v2: Any,
    v8: Any,
    v10: Any,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, topology, counts = _build_object_chunk(
        specs,
        cap_templates=cap_templates,
        rl_templates=rl_templates,
        bridge_core=bridge_core,
        v8=v8,
        v10=v10,
    )
    cdb = _build_rcl_cdb_global(specs, v8)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_header_project, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    issues = _validate_chunk(object_chunk, topology, counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v13_rl_inputs_first_not_locked",
        "description": description,
        "component_count": len(specs),
        "node_count": len(_nodes(specs)),
        "resistor_count": counts["resistor_count"],
        "capacitor_count": counts["capacitor_count"],
        "inductor_count": counts["inductor_count"],
        "rl_pair_count": counts["rl_pair_count"],
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_order": counts["object_order"],
        "emission_order": counts["emission_order"],
        "conversion_notes": notes,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "topology": topology,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            chunk_path.name: rv9._sha256_file(chunk_path),
            "object_chunk": rv9._sha256_bytes(object_chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, source, specs, counts, notes, topology), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Counts: R={counts['resistor_count']} C={counts['capacitor_count']} L={counts['inductor_count']}\n"
        f"Order: {counts['object_order']}\n"
        f"Static validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _requested15_inputs() -> list[Path]:
    paths = sorted(SOURCE_15_ROOT.glob("[0-9][0-9]_*\\input.json"))
    if len(paths) != 15:
        raise RuntimeError(f"Expected 15 requested topology inputs, found {len(paths)}.")
    return paths


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_for_v13", V2_PATH)
    v8 = _load_module("inductor_v8_for_v13", V8_PATH)
    v10 = _load_module("mixed_rcl_v10_for_v13", V10_PATH)
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base = registry.get("e001_empty").path
    cap_donor = registry.get("cap2_with_terminals_manual").path
    rl_donor = registry.get("rl_terminal_disconnected").path
    bridge_donor = registry.get("power_terminal_bridge_donor").path

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    rl_templates = v10._load_rl_native_templates(rl_donor)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")

    batch_defs: list[tuple[str, str, Path, bool]] = [
        ("RCL_V13_T01_6_COMPONENTS_BALANCED_RCL", "Six-component mixed R/C/L circuit with power and ground terminals.", SOURCE_6R, True),
        ("RCL_V13_T02_21_COMPONENTS_BALANCED_RCL", "Twenty-one-component mixed R/C/L circuit with power and ground terminals.", SOURCE_21R, True),
    ]
    for source_path in _requested15_inputs():
        batch_defs.append(
            (
                f"RCL_V13_T{len(batch_defs) + 1:02d}_{source_path.parent.name}",
                f"Mixed R/C/L version of requested topology {source_path.parent.name}.",
                source_path,
                True,
            )
        )

    manifests: list[dict[str, Any]] = []
    for case_id, description, source_path, require_all_three in batch_defs:
        source, specs, notes = _convert_source(v2, source_path, require_all_three=require_all_three)
        manifests.append(
            _write_case(
                case_id=case_id,
                description=description,
                source=source,
                specs=specs,
                notes=notes,
                base_project=base,
                donor_header_project=rl_donor,
                cap_templates=cap_templates,
                rl_templates=rl_templates,
                bridge_core=bridge_core,
                v2=v2,
                v8=v8,
                v10=v10,
            )
        )

    summary = {
        "batch_id": "MIXED_RCL_V13_RL_INPUTS_FIRST_STATIC_20260602",
        "status": "static_generated_awaiting_user_proteus_netlist_test",
        "source_feedback": "V12 fixed the single 1C+1L+1R cases, but user reported cases with additional R/C/L components still failed. V13 keeps global IDs and changes scaled R/L ordering.",
        "method": "Capacitors use the accepted manual cap block. Resistor/inductor components are paired using native V10 L/R records, but all R/L input terminals are emitted before all L/R output-component bodies. All components use one global component ID sequence, and CDB tables are written in DSN object-emission order.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "component_count": item["component_count"],
                "resistor_count": item["resistor_count"],
                "capacitor_count": item["capacitor_count"],
                "inductor_count": item["inductor_count"],
                "rl_pair_count": item["rl_pair_count"],
                "ground_terminal_count": item["ground_terminal_count"],
                "object_chunk_len": item["object_chunk_len"],
                "emission_order": item["emission_order"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in manifests
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V13 R/L-inputs-first netlist diagnostic pack.\n\nOpen and run netlist/simulation in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport the first case that errors or renders wrong.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V13_RL_INPUTS_FIRST_TEMP_2026_06_02"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "case_count": len(manifests), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
