"""Generate temporary resistor/capacitor/inductor mixed diagnostics.

V1 failed because it used the rejected V6 inductor path. V2 keeps the locked
resistor/capacitor record builders and swaps in the user-accepted V8 donor05
sequential inductor records.
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

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v2_v8_temp_2026_06_01"
SOURCE_6R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_21R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_15_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "requested_resistor_networks_oriented_2026_05_30"
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")

SAFE_X_STEP = 3810000
SAFE_Y_STEP = 2540000
BASE_X = -7366000
BASE_Y = 5080000
CAP_VALUE = "1uF"
TYPE_CYCLE = ("RESISTOR", "CAPACITOR", "INDUCTOR")


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


@dataclass(frozen=True)
class RclSpec:
    idx: int
    source_ref: str
    ref: str
    kind: str
    value: str
    visible_value: str
    left: str
    right: str
    x: int
    y: int
    visual_data: dict[str, Any]

    @property
    def type(self) -> str:
        return self.kind

    @property
    def nodes(self) -> tuple[str, str]:
        return (self.left, self.right)

    @property
    def visual(self) -> dict[str, Any]:
        out = dict(self.visual_data)
        out.setdefault("visible_value", self.visible_value)
        return out


def _load_v8() -> Any:
    spec = importlib.util.spec_from_file_location("inductor_v8_temp", V8_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V8 generator from {V8_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _suffix_ref(prefix: str, index: int) -> str:
    if index <= 9:
        return f"{prefix}{index}"
    return f"{prefix}{chr(ord('A') + index - 10)}"


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

    if not require_all_three or len(components) >= 3:
        return [
            _component_raw_item(component, TYPE_CYCLE[(index - 1) % 3], *positions[component["ref"]])
            for index, component in enumerate(components, start=1)
        ], notes

    if len(components) == 1:
        component = components[0]
        left, right = component["nodes"]
        mid_1 = _new_node(used_nodes)
        mid_2 = _new_node(used_nodes)
        x, y = positions[component["ref"]]
        notes.append("Expanded the one-component source topology into an R/C/L series chain so the file exercises all three passive families.")
        return [
            RawItem(component["ref"], "RESISTOR", component.get("value", "1k"), left, mid_1, x, y, dict(component.get("visual", {}))),
            RawItem(component["ref"], "CAPACITOR", component.get("value", "1k"), mid_1, mid_2, x + SAFE_X_STEP, y, {}),
            RawItem(component["ref"], "INDUCTOR", component.get("value", "1k"), mid_2, right, x + 2 * SAFE_X_STEP, y, {}),
        ], notes

    if len(components) == 2:
        first, second = components
        mid = _new_node(used_nodes)
        x1, y1 = positions[first["ref"]]
        x2, y2 = positions[second["ref"]]
        left_1, right_1 = first["nodes"]
        left_2, right_2 = second["nodes"]
        notes.append("Expanded the two-component source topology into three mixed components by splitting the second branch into C then L.")
        return [
            RawItem(first["ref"], "RESISTOR", first.get("value", "1k"), left_1, right_1, x1, y1, dict(first.get("visual", {}))),
            RawItem(second["ref"], "CAPACITOR", second.get("value", "1k"), left_2, mid, x2, y2, dict(second.get("visual", {}))),
            RawItem(second["ref"], "INDUCTOR", second.get("value", "1k"), mid, right_2, x2 + SAFE_X_STEP, y2, {}),
        ], notes

    raise RuntimeError("Unsupported source with zero components.")


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


def _convert_source(path: Path, *, require_all_three: bool) -> tuple[dict[str, Any], list[RclSpec], list[str]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    items, notes = _raw_items(source, require_all_three=require_all_three)
    items = _dedupe_positions(items)
    prefix = {"RESISTOR": "R", "CAPACITOR": "C", "INDUCTOR": "L"}
    specs: list[RclSpec] = []
    for index, item in enumerate(items, start=1):
        value, visible = _value_for_item(item)
        specs.append(
            RclSpec(
                idx=index,
                source_ref=item.source_ref,
                ref=_suffix_ref(prefix[item.kind], index),
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


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _node_list(specs: list[RclSpec]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _build_rcl_cdb(specs: list[RclSpec], v8: Any) -> bytes:
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
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("CAP") + rv9._enc_str("CAP10") + rv9._enc_text(mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("REALIND") + rv9._enc_str("") + rv9._enc_text(v8.IND_PROP_TEXT)
        else:
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("RESISTOR") + rv9._enc_str("") + rv9._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _build_inductor_records(spec: RclSpec, ordinal: int, count: int, templates: Any, v8: Any) -> dict[str, Any]:
    ind_spec = v8.IndSpec(
        idx=spec.idx,
        source_ref=spec.source_ref,
        ref=spec.ref,
        value=spec.value,
        visible_value=spec.visible_value,
        left=spec.left,
        right=spec.right,
        x=spec.x,
        y=spec.y,
    )
    records = v8._records_for_spec(ind_spec, ordinal, count, templates, "extend_from_donor05", ground_endpoints=True)
    records["map"]["idx"] = spec.idx
    records["map"]["ordinal"] = ordinal
    records["map"]["kind"] = "INDUCTOR"
    records["map"]["source_ref"] = spec.source_ref
    return records


def _build_object_chunk(
    specs: list[RclSpec],
    *,
    cap_templates: mp.ManualCapTemplates,
    res_templates: rv9.V9Templates,
    ind_templates: Any,
    bridge_core: bytes,
    v8: Any,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    ground_nodes = {"G0"}
    cap_outputs: list[bytes] = []
    cap_groups: list[bytes] = []
    res_inputs: list[bytes] = []
    res_outputs: list[bytes] = []
    res_groups: list[bytes] = []
    ind_records: list[dict[str, Any]] = []
    topology: list[dict[str, Any]] = []
    cap_ordinal = 0
    res_ordinal = 0
    ind_ordinal = 0
    ind_count = sum(1 for spec in specs if spec.kind == "INDUCTOR")

    for spec in specs:
        if spec.kind == "CAPACITOR":
            cap_ordinal += 1
            output_record, group, info = mp._build_capacitor_records(
                spec,
                ordinal=cap_ordinal,
                x=spec.x,
                y=spec.y,
                templates=cap_templates,
                ground_nodes=ground_nodes,
            )
            cap_outputs.append(output_record)
            cap_groups.extend(group)
            info.update({"idx": spec.idx, "ordinal": cap_ordinal, "source_ref": spec.source_ref})
            topology.append(info)
        elif spec.kind == "INDUCTOR":
            ind_ordinal += 1
            records = _build_inductor_records(spec, ind_ordinal, ind_count, ind_templates, v8)
            ind_records.append(records)
            topology.append(records["map"])
        else:
            res_ordinal += 1
            input_record, output_record, group, info = mp._build_resistor_records(
                spec,
                ordinal=res_ordinal,
                x=spec.x,
                y=spec.y,
                templates=res_templates,
                ground_nodes=ground_nodes,
            )
            res_inputs.append(input_record)
            res_outputs.append(output_record)
            res_groups.extend(group)
            info.update({"idx": spec.idx, "ordinal": res_ordinal, "source_ref": spec.source_ref})
            topology.append(info)

    ind_groups = b"".join(
        item["input"] + item["output"] + item["inductor"] + item["wire_left"] + item["wire_right"]
        for item in ind_records
    )
    object_order = (
        "header, power bridge, capacitor outputs, capacitor groups, "
        "resistor inputs, resistor outputs, resistor separator, resistor groups, "
        "donor05 sequential inductor groups"
    )
    chunk = bytearray(
        cap_templates.header
        + bridge_core
        + b"".join(cap_outputs)
        + b"".join(cap_groups)
        + b"".join(res_inputs)
        + b"".join(res_outputs)
        + res_templates.separator
        + b"".join(res_groups)
        + ind_groups
    )
    chunk[-1] = 0xFF
    counts = {
        "order": "r_c_then_l_last",
        "object_order": object_order,
        "power_bridge_count": 1,
        "resistor_count": res_ordinal,
        "capacitor_count": cap_ordinal,
        "inductor_count": ind_ordinal,
        "ground_terminal_count": sum(1 for item in topology if item["output_marker"] == "$TERGROUND"),
    }
    return bytes(chunk), sorted(topology, key=lambda item: item["idx"]), counts


def _validate_chunk(chunk: bytes, topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    ground_count = counts["ground_terminal_count"]
    expected_counts = {
        "$TERPOWER": 1,
        "$TERINPUT": len(topology),
        "$TEROUTPUT": len(topology) - ground_count + 1,
        "$TERGROUND": ground_count,
        "WIRE": len(topology) * 2 + 1,
        "CAPACITOR": counts["capacitor_count"],
        "CAP10": counts["capacitor_count"],
        "REALIND": counts["inductor_count"] * 3,
        "RESISTOR": counts["resistor_count"] * 2,
    }
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    for marker, expected in expected_counts.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected:
            issues.append(f"{marker} count {actual} != {expected}")
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE - 1
    if len(chunk) > bridge_end and chunk[bridge_end] != 0:
        issues.append(f"power bridge terminator {chunk[bridge_end]:02x}")
    all_maps = [item for item in topology if item["kind"] in {"RESISTOR", "CAPACITOR", "INDUCTOR"}]
    if len({item["ref"] for item in all_maps}) != len(all_maps):
        issues.append("component refs are not unique")
    if len({item["in_suffix"] for item in all_maps}) != len(all_maps):
        issues.append("input suffixes are not globally unique")
    if len({item["out_suffix"] for item in all_maps}) != len(all_maps):
        issues.append("output suffixes are not globally unique")
    return issues


def _payload(case_id: str, source: dict[str, Any], specs: list[RclSpec], counts: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v2",
        "generator_target": "proteus-8.13-mixed-rcl-terminal-power-ground-diagnostic",
        "case_id": case_id,
        "source_resistor_case": source.get("metadata", {}).get("case_id", source.get("project", {}).get("output_basename")),
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _node_list(specs)],
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
            "method": "mixed R/C/L with all three passive families present in each requested case",
            "object_order": counts["object_order"],
            "temporary": True,
            "conversion_notes": notes,
        },
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    source: dict[str, Any],
    specs: list[RclSpec],
    notes: list[str],
    base_project: Path,
    resistor_donor: Path,
    cap_templates: mp.ManualCapTemplates,
    res_templates: rv9.V9Templates,
    ind_templates: Any,
    bridge_core: bytes,
    v8: Any,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, topology, counts = _build_object_chunk(
        specs,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
        bridge_core=bridge_core,
        v8=v8,
    )
    cdb = _build_rcl_cdb(specs, v8)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(resistor_donor, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, source, specs, counts, notes), indent=2) + "\n", encoding="utf-8")

    issues = _validate_chunk(object_chunk, topology, counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v2_not_locked",
        "description": description,
        "component_count": len(specs),
        "node_count": len(_node_list(specs)),
        "resistor_count": counts["resistor_count"],
        "capacitor_count": counts["capacitor_count"],
        "inductor_count": counts["inductor_count"],
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_order": counts["object_order"],
        "conversion_notes": notes,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "$TERPOWER": object_chunk.count(b"$TERPOWER"),
            "$TERINPUT": object_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
            "$TERGROUND": object_chunk.count(b"$TERGROUND"),
            "WIRE": object_chunk.count(b"WIRE"),
            "CAPACITOR": object_chunk.count(b"CAPACITOR"),
            "REALIND": object_chunk.count(b"REALIND"),
            "RESISTOR": object_chunk.count(b"RESISTOR"),
        },
        "section_pointer_values": pointers,
        "topology": topology,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            "object_chunk": rv9._sha256_bytes(object_chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Project: {output_path.name}\n"
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
    v8 = _load_v8()
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base = registry.get("e001_empty").path
    cap_donor = registry.get("cap2_with_terminals_manual").path
    resistor_donor = registry.get("r21_v9_resistor_terminal_donor").path
    bridge_donor = registry.get("power_terminal_bridge_donor").path
    inductor_donor = registry.get("inductor_05_six_terminal").path

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ind_templates = v8._load_six_templates(inductor_donor)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")

    manifests: list[dict[str, Any]] = []
    batch_defs: list[tuple[str, str, Path, bool]] = [
        ("RCL_V2_T01_6_COMPONENTS_RCL_CYCLE", "Six-component mixed R/C/L cycle with power and ground terminals.", SOURCE_6R, False),
        ("RCL_V2_T02_21_COMPONENTS_RCL_CYCLE", "Twenty-one-component mixed R/C/L cycle with power and ground terminals.", SOURCE_21R, False),
    ]
    for source_path in _requested15_inputs():
        batch_defs.append(
            (
                f"RCL_V2_T{len(batch_defs) + 1:02d}_{source_path.parent.name}",
                f"Mixed R/C/L version of requested topology {source_path.parent.name}.",
                source_path,
                True,
            )
        )

    for case_id, description, source_path, require_all_three in batch_defs:
        source, specs, notes = _convert_source(source_path, require_all_three=require_all_three)
        manifests.append(
            _write_case(
                case_id=case_id,
                description=description,
                source=source,
                specs=specs,
                notes=notes,
                base_project=base,
                resistor_donor=resistor_donor,
                cap_templates=cap_templates,
                res_templates=res_templates,
                ind_templates=ind_templates,
                bridge_core=bridge_core,
                v8=v8,
            )
        )

    summary = {
        "case": "MIXED_RCL_V2_V8_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "why": "R/C/L V1 failed with rejected inductor V6 records; V2 uses the accepted V8 donor05 sequential inductor method.",
        "method": "Components cycle RESISTOR, CAPACITOR, INDUCTOR while preserving source net labels where possible. One V0 power bridge is emitted. Grounded right endpoints become $TERGROUND(G0). Inductor records are kept in a donor05 sequential block at the end of the object stream.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "T01 is the six-component R/C/L cycle and T02 is the twenty-one-component R/C/L cycle.",
            "T03-T17 are the 15 requested topology shapes.",
            "One- and two-component source topologies are expanded into three mixed components so every requested case includes R, C, and L.",
            "Stop at the first fatal Proteus error and report the exact case id and error text.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V2 diagnostic pack using accepted V8 inductors.\n\n"
        "Open in this order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport exact errors, missing component types, wrong labels, overlap, or bad-object records.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V2_V8_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "case_count": len(manifests), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
