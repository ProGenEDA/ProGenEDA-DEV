"""Generate temporary resistor/capacitor/inductor mixed diagnostics.

This is not a locked generator. It combines already accepted resistor/capacitor
record builders with the temporary inductor V6 records so we can test whether
R/C/L coexist in one E001-based project.
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

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v1_temp_2026_06_01"
SOURCE_6R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_21R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_15_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "requested_resistor_networks_oriented_2026_05_30"
V6_PATH = Path(__file__).with_name("generate_inductor_v6_6_21_temp.py")

SAFE_X_STEP = 3810000
SAFE_Y_STEP = 2540000
BASE_X = -6858000
BASE_Y = 5080000
CAP_VALUE = "1uF"


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

    @property
    def type(self) -> str:
        return self.kind

    @property
    def nodes(self) -> tuple[str, str]:
        return (self.left, self.right)

    @property
    def visual(self) -> dict[str, Any]:
        return {"visible_value": self.visible_value}


def _load_v6() -> Any:
    spec = importlib.util.spec_from_file_location("inductor_v6_temp", V6_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V6 generator from {V6_PATH}.")
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


def _visible_inductor_from_resistor(value: str, target_len: int) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    number = int(digits or "1")
    if target_len == 4:
        if number >= 10:
            return "10mH"
        return f"{number}0uH"
    if number >= 10:
        return "9mH"
    return f"{number}mH"


def _inductor_template_visible_for_ordinal(ordinal: int) -> str:
    slot = (ordinal - 1) % 3
    if slot == 0:
        return "1mH"
    if slot == 1:
        return "2mH"
    return "10uH"


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


def _convert_source(path: Path) -> tuple[dict[str, Any], list[RclSpec]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    positions = _safe_positions(source)
    type_cycle = ("RESISTOR", "CAPACITOR", "INDUCTOR")
    prefix = {"RESISTOR": "R", "CAPACITOR": "C", "INDUCTOR": "L"}
    specs: list[RclSpec] = []
    ind_ordinal = 0
    for idx, component in enumerate(source["components"], start=1):
        kind = type_cycle[(idx - 1) % 3]
        left, right = component["nodes"]
        x, y = positions[component["ref"]]
        if kind == "RESISTOR":
            value = component.get("value", "1k")
            visible = visible_resistor_value(value, {})
        elif kind == "CAPACITOR":
            value = CAP_VALUE
            visible = "1uF"
        else:
            ind_ordinal += 1
            template_visible = _inductor_template_visible_for_ordinal(ind_ordinal)
            value = _visible_inductor_from_resistor(component.get("value", "1k"), len(template_visible))
            visible = value
        specs.append(
            RclSpec(
                idx=idx,
                source_ref=component["ref"],
                ref=_suffix_ref(prefix[kind], idx),
                kind=kind,
                value=value,
                visible_value=visible,
                left=left,
                right=right,
                x=x,
                y=y,
            )
        )
    return source, specs


def _build_rcl_cdb(specs: list[RclSpec], v6: Any) -> bytes:
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
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("REALIND") + rv9._enc_str("") + rv9._enc_text(v6.IND_PROP_TEXT)
        else:
            out += rv9._enc_str(spec.ref) + rv9._enc_str(spec.value) + rv9._enc_str("RESISTOR") + rv9._enc_str("") + rv9._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _zero_terminated(record: bytes) -> bytes:
    return record[:-1] + b"\x00"


def _build_inductor_records(spec: RclSpec, ordinal: int, count: int, templates: Any, v6: Any) -> dict[str, Any]:
    ind_spec = v6.IndSpec(
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
    records = v6._records_for_spec(ind_spec, ordinal, count, templates, "extended", ground_endpoints=True)
    for key in ("input", "output", "inductor", "wire_left", "wire_right"):
        records[key] = _zero_terminated(records[key])
    records["map"]["idx"] = spec.idx
    records["map"]["ordinal"] = ordinal
    records["map"]["kind"] = "INDUCTOR"
    records["map"]["source_ref"] = spec.source_ref
    return records


def _inductor_section_v3_order(inductor_records: list[dict[str, Any]]) -> bytes:
    if not inductor_records:
        return b""
    first = inductor_records[0]
    out = bytearray(first["input"] + first["output"] + first["inductor"] + first["wire_left"] + first["wire_right"])
    out += b"".join(item["output"] for item in inductor_records[1:])
    for item in inductor_records[1:]:
        out += item["input"] + item["inductor"] + item["wire_left"] + item["wire_right"]
    return bytes(out)


def _build_object_chunk(
    specs: list[RclSpec],
    *,
    cap_templates: mp.ManualCapTemplates,
    res_templates: rv9.V9Templates,
    ind_templates: Any,
    bridge_dsn: bytes,
    v6: Any,
    order: str,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    bridge_core = rv9._load_power_bridge_core(bridge_dsn, "V0")
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
            records = _build_inductor_records(spec, ind_ordinal, ind_count, ind_templates, v6)
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

    ind_outputs = b"".join(item["output"] for item in ind_records)
    ind_groups = b"".join(item["input"] + item["inductor"] + item["wire_left"] + item["wire_right"] for item in ind_records)
    if order == "grouped":
        object_order = "header, power bridge, capacitor outputs, inductor outputs, capacitor groups, inductor groups, resistor inputs, resistor outputs, separator, resistor groups"
        chunk = bytearray(
            cap_templates.header
            + bridge_core
            + b"".join(cap_outputs)
            + ind_outputs
            + b"".join(cap_groups)
            + ind_groups
            + b"".join(res_inputs)
            + b"".join(res_outputs)
            + res_templates.separator
            + b"".join(res_groups)
        )
    elif order == "inductor_v3_first":
        object_order = "header, power bridge, inductor V3 section, capacitor outputs, capacitor groups, resistor inputs, resistor outputs, separator, resistor groups"
        chunk = bytearray(
            cap_templates.header
            + bridge_core
            + _inductor_section_v3_order(ind_records)
            + b"".join(cap_outputs)
            + b"".join(cap_groups)
            + b"".join(res_inputs)
            + b"".join(res_outputs)
            + res_templates.separator
            + b"".join(res_groups)
        )
    else:
        raise ValueError(f"Unknown RCL object order {order}.")
    chunk[-1] = 0xFF
    counts = {
        "order": order,
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
    return issues


def _payload(case_id: str, source: dict[str, Any], specs: list[RclSpec], counts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v1",
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
                "visual": {"x": spec.x, "y": spec.y},
            }
            for spec in specs
        ],
        "metadata": {
            "method": "global component cycle RESISTOR, CAPACITOR, INDUCTOR",
            "object_order": counts["object_order"],
            "temporary": True,
        },
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    source: dict[str, Any],
    specs: list[RclSpec],
    order: str,
    base_project: Path,
    resistor_donor: Path,
    cap_templates: mp.ManualCapTemplates,
    res_templates: rv9.V9Templates,
    ind_templates: Any,
    bridge_dsn: bytes,
    v6: Any,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, topology, counts = _build_object_chunk(
        specs,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
        bridge_dsn=bridge_dsn,
        v6=v6,
        order=order,
    )
    cdb = _build_rcl_cdb(specs, v6)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(resistor_donor, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, source, specs, counts), indent=2) + "\n", encoding="utf-8")

    issues = _validate_chunk(object_chunk, topology, counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v1_not_locked",
        "description": description,
        "component_count": len(specs),
        "node_count": len(_node_list(specs)),
        "resistor_count": counts["resistor_count"],
        "capacitor_count": counts["capacitor_count"],
        "inductor_count": counts["inductor_count"],
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_order": counts["object_order"],
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
    v6 = _load_v6()
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
    inductor_donor = registry.get("inductor_03_three_terminal").path

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ind_templates = v6._load_three_templates(inductor_donor)
    bridge_dsn = read_internal_file(bridge_donor, "ROOT.DSN")

    manifests: list[dict[str, Any]] = []
    source6, specs6 = _convert_source(SOURCE_6R)
    source21, specs21 = _convert_source(SOURCE_21R)
    batch_defs: list[tuple[str, str, dict[str, Any], list[RclSpec], str]] = [
        (
            "RCL_V1_T01_6_COMPONENTS_GROUPED_ORDER",
            "Six-component R/C/L cycle using grouped capacitor/inductor outputs before groups.",
            source6,
            specs6,
            "grouped",
        ),
        (
            "RCL_V1_T02_6_COMPONENTS_INDUCTOR_V3_FIRST",
            "Six-component R/C/L cycle using the inductor V3 section immediately after the power bridge.",
            source6,
            specs6,
            "inductor_v3_first",
        ),
        (
            "RCL_V1_T03_21_COMPONENTS_INDUCTOR_V3_FIRST",
            "Twenty-one-component R/C/L cycle using the best current mixed order.",
            source21,
            specs21,
            "inductor_v3_first",
        ),
    ]
    for source_path in _requested15_inputs():
        source, specs = _convert_source(source_path)
        case_id = f"RCL_V1_T{len(batch_defs) + 1:02d}_{source_path.parent.name}"
        batch_defs.append(
            (
                case_id,
                f"R/C/L cycle version of requested topology {source_path.parent.name}.",
                source,
                specs,
                "inductor_v3_first",
            )
        )

    for case_id, description, source, specs, order in batch_defs:
        manifests.append(
            _write_case(
                case_id=case_id,
                description=description,
                source=source,
                specs=specs,
                order=order,
                base_project=base,
                resistor_donor=resistor_donor,
                cap_templates=cap_templates,
                res_templates=res_templates,
                ind_templates=ind_templates,
                bridge_dsn=bridge_dsn,
                v6=v6,
            )
        )

    summary = {
        "case": "MIXED_RCL_V1_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "why": "First R/C/L coexistence batch after resistor/capacitor lock and temporary inductor V6/V7 generation.",
        "method": "Components cycle RESISTOR, CAPACITOR, INDUCTOR while preserving source net labels and using one V0 power bridge plus G0 ground terminals.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "T01 and T02 are the same 6-component topology with different mixed object ordering.",
            "If T01 fails and T02 works, use T02/T03 onwards as the candidate order.",
            "T04-T18 are the 15 requested topology shapes with R/C/L cycling; small topologies with one or two components may not include all three component types.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V1 diagnostic pack.\n\n"
        "Open in this order and stop at the first fatal Proteus error unless collecting extra diagnostics:\n\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport exact errors, missing component types, wrong labels, overlap, or bad-object records.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V1_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "case_count": len(manifests), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
