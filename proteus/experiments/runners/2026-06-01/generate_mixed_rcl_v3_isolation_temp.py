"""Generate R/C/L mixed isolation diagnostics after V2 all failed.

The goal is to identify whether Proteus rejects:

- resistor + inductor coexistence,
- capacitor + inductor coexistence, or
- only all three families together,

and whether donor05 sequential or outputs-first inductor ordering is safer when
mixed with the locked resistor/capacitor object blocks.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_passive as mp
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v3_isolation_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {name} from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _base_specs(v2: Any, mode: str) -> list[Any]:
    if mode == "RL":
        return [
            v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", "V0", "N1", -7366000, 5080000, {}),
            v2.RclSpec(2, "L1", "L2", "INDUCTOR", "1mH", "1mH", "N1", "G0", -3556000, 5080000, {}),
        ]
    if mode == "CL":
        return [
            v2.RclSpec(1, "C1", "C1", "CAPACITOR", "1uF", "1uF", "V0", "N1", -7366000, 5080000, {}),
            v2.RclSpec(2, "L1", "L2", "INDUCTOR", "1mH", "1mH", "N1", "G0", -3556000, 5080000, {}),
        ]
    if mode == "RCL":
        return [
            v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", "V0", "N1", -7366000, 5080000, {}),
            v2.RclSpec(2, "C1", "C2", "CAPACITOR", "1uF", "1uF", "N1", "N2", -3556000, 5080000, {}),
            v2.RclSpec(3, "L1", "L3", "INDUCTOR", "1mH", "1mH", "N2", "G0", 254000, 5080000, {}),
        ]
    raise ValueError(f"Unknown mode {mode}.")


def _nodes(specs: list[Any]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _zero_last(record: bytes) -> bytes:
    return record[:-1] + b"\x00" if record else record


def _records(
    specs: list[Any],
    *,
    cap_templates: Any,
    res_templates: Any,
    ind_templates: Any,
    v8: Any,
) -> dict[str, Any]:
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
        elif spec.kind == "RESISTOR":
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
        else:
            ind_ordinal += 1
            ind_spec = v8.IndSpec(spec.idx, spec.source_ref, spec.ref, spec.value, spec.visible_value, spec.left, spec.right, spec.x, spec.y)
            record = v8._records_for_spec(ind_spec, ind_ordinal, ind_count, ind_templates, "extend_from_donor05", ground_endpoints=True)
            record["map"].update({"idx": spec.idx, "ordinal": ind_ordinal, "kind": "INDUCTOR", "source_ref": spec.source_ref})
            ind_records.append(record)
            topology.append(record["map"])

    return {
        "cap_outputs": cap_outputs,
        "cap_groups": cap_groups,
        "res_inputs": res_inputs,
        "res_outputs": res_outputs,
        "res_groups": res_groups,
        "ind_records": ind_records,
        "topology": sorted(topology, key=lambda item: item["idx"]),
        "counts": {
            "resistor_count": res_ordinal,
            "capacitor_count": cap_ordinal,
            "inductor_count": ind_ordinal,
            "ground_terminal_count": sum(1 for item in topology if item["output_marker"] == "$TERGROUND"),
        },
    }


def _res_block(records: dict[str, Any], res_templates: Any) -> bytes:
    if not records["res_inputs"]:
        return b""
    return b"".join(records["res_inputs"]) + b"".join(records["res_outputs"]) + res_templates.separator + b"".join(records["res_groups"])


def _cap_block(records: dict[str, Any]) -> bytes:
    return b"".join(records["cap_outputs"]) + b"".join(records["cap_groups"])


def _ind_seq_block(records: dict[str, Any], *, final: bool) -> bytes:
    chunks: list[bytes] = []
    ind_records = records["ind_records"]
    for index, item in enumerate(ind_records, start=1):
        wire_right = item["wire_right"]
        if not (final and index == len(ind_records)):
            wire_right = _zero_last(wire_right)
        chunks.append(item["input"] + item["output"] + item["inductor"] + item["wire_left"] + wire_right)
    return b"".join(chunks)


def _ind_outputs_first_block(records: dict[str, Any], *, final: bool) -> tuple[bytes, bytes]:
    ind_records = records["ind_records"]
    outputs = b"".join(item["output"] for item in ind_records)
    groups: list[bytes] = []
    for index, item in enumerate(ind_records, start=1):
        wire_right = item["wire_right"]
        if not (final and index == len(ind_records)):
            wire_right = _zero_last(wire_right)
        groups.append(item["input"] + item["inductor"] + item["wire_left"] + wire_right)
    return outputs, b"".join(groups)


def _chunk_for_order(order: str, records: dict[str, Any], header: bytes, bridge_core: bytes, res_templates: Any) -> tuple[bytes, str]:
    cap = _cap_block(records)
    res = _res_block(records, res_templates)

    if order == "rl_res_then_ind":
        body = res + _ind_seq_block(records, final=True)
        desc = "power bridge, resistor block, donor05 sequential inductor block"
    elif order == "rl_ind_then_res":
        body = _ind_seq_block(records, final=False) + res
        desc = "power bridge, donor05 sequential inductor block, resistor block"
    elif order == "cl_cap_then_ind":
        body = cap + _ind_seq_block(records, final=True)
        desc = "power bridge, capacitor block, donor05 sequential inductor block"
    elif order == "cl_ind_then_cap":
        body = _ind_seq_block(records, final=False) + cap
        desc = "power bridge, donor05 sequential inductor block, capacitor block"
    elif order == "cl_outputs_first_joined":
        ind_outputs, ind_groups = _ind_outputs_first_block(records, final=True)
        body = b"".join(records["cap_outputs"]) + ind_outputs + b"".join(records["cap_groups"]) + ind_groups
        desc = "power bridge, capacitor+inductor outputs first, then capacitor groups, then inductor groups"
    elif order == "rcl_v2_current":
        body = cap + res + _ind_seq_block(records, final=True)
        desc = "power bridge, capacitor block, resistor block, donor05 sequential inductor block"
    elif order == "rcl_ind_first":
        body = _ind_seq_block(records, final=False) + cap + res
        desc = "power bridge, donor05 sequential inductor block, capacitor block, resistor block"
    elif order == "rcl_cap_ind_outputs_then_res":
        ind_outputs, ind_groups = _ind_outputs_first_block(records, final=False)
        body = b"".join(records["cap_outputs"]) + ind_outputs + b"".join(records["cap_groups"]) + ind_groups + res
        desc = "power bridge, capacitor+inductor outputs first, capacitor+inductor groups, resistor block"
    elif order == "rcl_all_outputs_then_groups":
        ind_outputs, ind_groups = _ind_outputs_first_block(records, final=False)
        body = (
            b"".join(records["cap_outputs"])
            + ind_outputs
            + b"".join(records["res_inputs"])
            + b"".join(records["res_outputs"])
            + b"".join(records["cap_groups"])
            + ind_groups
            + (res_templates.separator if records["res_groups"] else b"")
            + b"".join(records["res_groups"])
        )
        desc = "power bridge, cap+ind outputs and resistor terminal arrays first, then cap/ind groups, separator, resistor groups"
    else:
        raise ValueError(f"Unknown order {order}.")

    chunk = bytearray(header + bridge_core + body)
    chunk[-1] = 0xFF
    return bytes(chunk), desc


def _validate(chunk: bytes, records: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    counts = records["counts"]
    ground = counts["ground_terminal_count"]
    topology_len = len(records["topology"])
    expected = {
        "$TERPOWER": 1,
        "$TERINPUT": topology_len,
        "$TEROUTPUT": topology_len - ground + 1,
        "$TERGROUND": ground,
        "WIRE": topology_len * 2 + 1,
        "CAPACITOR": counts["capacitor_count"],
        "CAP10": counts["capacitor_count"],
        "REALIND": counts["inductor_count"] * 3,
        "RESISTOR": counts["resistor_count"] * 2,
    }
    for marker, want in expected.items():
        got = chunk.count(marker.encode("ascii"))
        if got != want:
            issues.append(f"{marker} count {got} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if len({item["in_suffix"] for item in records["topology"]}) != topology_len:
        issues.append("input suffixes are not globally unique")
    if len({item["out_suffix"] for item in records["topology"]}) != topology_len:
        issues.append("output suffixes are not globally unique")
    return issues


def _payload(case_id: str, mode: str, order_desc: str, specs: list[Any], records: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v3-isolation",
        "generator_target": "proteus-8.13-mixed-rcl-isolation-diagnostic",
        "case_id": case_id,
        "mode": mode,
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _nodes(specs)],
        "components": [
            {"idx": spec.idx, "ref": spec.ref, "type": spec.kind, "value": spec.value, "nodes": [spec.left, spec.right], "visual": {"x": spec.x, "y": spec.y}}
            for spec in specs
        ],
        "metadata": {"object_order": order_desc, "topology": records["topology"]},
    }


def _write_case(
    *,
    case_id: str,
    mode: str,
    order: str,
    base_project: Path,
    resistor_donor: Path,
    header: bytes,
    bridge_core: bytes,
    res_templates: Any,
    records: dict[str, Any],
    specs: list[Any],
    v2: Any,
    v8: Any,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    chunk, order_desc = _chunk_for_order(order, records, header, bridge_core, res_templates)
    cdb = v2._build_rcl_cdb(specs, v8)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(resistor_donor, "ROOT.DSN"), chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    issues = _validate(chunk, records)
    if rv9._extract_object_chunk(dsn) != chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v3_isolation_not_locked",
        "mode": mode,
        "order_key": order,
        "object_order": order_desc,
        "component_count": len(specs),
        "resistor_count": records["counts"]["resistor_count"],
        "capacitor_count": records["counts"]["capacitor_count"],
        "inductor_count": records["counts"]["inductor_count"],
        "ground_terminal_count": records["counts"]["ground_terminal_count"],
        "marker_counts": {
            "$TERPOWER": chunk.count(b"$TERPOWER"),
            "$TERINPUT": chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": chunk.count(b"$TEROUTPUT"),
            "$TERGROUND": chunk.count(b"$TERGROUND"),
            "WIRE": chunk.count(b"WIRE"),
            "CAPACITOR": chunk.count(b"CAPACITOR"),
            "REALIND": chunk.count(b"REALIND"),
            "RESISTOR": chunk.count(b"RESISTOR"),
        },
        "section_pointer_values": pointers,
        "topology": records["topology"],
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            "object_chunk": rv9._sha256_bytes(chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, mode, order_desc, specs, records), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\nMode: {mode}\nOrder: {order_desc}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_temp", V2_PATH)
    v8 = _load_module("inductor_v8_temp_for_rcl_v3", V8_PATH)
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")

    base = registry.get("e001_empty").path
    resistor_donor = registry.get("r21_v9_resistor_terminal_donor").path
    cap_donor = registry.get("cap2_with_terminals_manual").path
    bridge_donor = registry.get("power_terminal_bridge_donor").path
    inductor_donor = registry.get("inductor_05_six_terminal").path

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ind_templates = v8._load_six_templates(inductor_donor)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")
    header = cap_templates.header

    case_defs = [
        ("RCL_V3_T01_RL_RES_THEN_IND", "RL", "rl_res_then_ind"),
        ("RCL_V3_T02_RL_IND_THEN_RES", "RL", "rl_ind_then_res"),
        ("RCL_V3_T03_CL_CAP_THEN_IND", "CL", "cl_cap_then_ind"),
        ("RCL_V3_T04_CL_IND_THEN_CAP", "CL", "cl_ind_then_cap"),
        ("RCL_V3_T05_CL_OUTPUTS_FIRST_JOINED", "CL", "cl_outputs_first_joined"),
        ("RCL_V3_T06_RCL_V2_CURRENT_MINIMAL", "RCL", "rcl_v2_current"),
        ("RCL_V3_T07_RCL_IND_FIRST", "RCL", "rcl_ind_first"),
        ("RCL_V3_T08_RCL_CAP_IND_OUTPUTS_THEN_RES", "RCL", "rcl_cap_ind_outputs_then_res"),
        ("RCL_V3_T09_RCL_ALL_OUTPUTS_THEN_GROUPS", "RCL", "rcl_all_outputs_then_groups"),
    ]

    manifests: list[dict[str, Any]] = []
    for case_id, mode, order in case_defs:
        specs = _base_specs(v2, mode)
        records = _records(specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates, v8=v8)
        manifests.append(
            _write_case(
                case_id=case_id,
                mode=mode,
                order=order,
                base_project=base,
                resistor_donor=resistor_donor,
                header=header,
                bridge_core=bridge_core,
                res_templates=res_templates,
                records=records,
                specs=specs,
                v2=v2,
                v8=v8,
            )
        )

    summary = {
        "case": "MIXED_RCL_V3_ISOLATION_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "why": "User reported every R/C/L V2 output failed with VGCVC.dll. V3 isolates pairwise and order variables.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "Start with T01/T02 to determine whether resistor+inductor can coexist.",
            "Then test T03-T05 for capacitor+inductor coexistence and outputs-first behavior.",
            "Only test T06-T09 if at least one pairwise case works.",
            "Report exact first failing case and whether any pairwise case opens.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V3 isolation pack.\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport which pairwise cases work or fail before testing the full R/C/L cases.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V3_ISOLATION_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "case_count": len(manifests), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
