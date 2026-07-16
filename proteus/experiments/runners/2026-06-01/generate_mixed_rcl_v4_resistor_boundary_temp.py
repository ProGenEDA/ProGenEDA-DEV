"""Generate R/C/L resistor-boundary diagnostics after V3 feedback.

V3 showed C+L can work, but every case containing a resistor and inductor
failed. V4 probes whether the boundary is the visual object stream, the
power/ground bridge, or mixed ROOT.CDB component metadata.
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

from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v4_resistor_boundary_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V3_PATH = Path(__file__).with_name("generate_mixed_rcl_v3_isolation_temp.py")
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {name} from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rl_specs(v2: Any, *, power: bool) -> list[Any]:
    left = "V0" if power else "N1"
    right = "G0" if power else "N3"
    return [
        v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", left, "N2", -7366000, 5080000, {}),
        v2.RclSpec(2, "L1", "L2", "INDUCTOR", "1mH", "1mH", "N2", right, -3556000, 5080000, {}),
    ]


def _rcl_specs(v2: Any) -> list[Any]:
    return [
        v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", "V0", "N1", -7366000, 5080000, {}),
        v2.RclSpec(2, "C1", "C2", "CAPACITOR", "1uF", "1uF", "N1", "N2", -3556000, 5080000, {}),
        v2.RclSpec(3, "L1", "L3", "INDUCTOR", "1mH", "1mH", "N2", "G0", 254000, 5080000, {}),
    ]


def _subset(specs: list[Any], *kinds: str) -> list[Any]:
    want = set(kinds)
    return [spec for spec in specs if spec.kind in want]


def _cdb_for(kind: str, specs: list[Any], *, base_project: Path, v2: Any, v8: Any) -> bytes:
    if kind == "full":
        return v2._build_rcl_cdb(specs, v8)
    if kind == "e001":
        return read_internal_file(base_project, "ROOT.CDB")
    if kind == "resistor_only":
        return v2._build_rcl_cdb(_subset(specs, "RESISTOR"), v8)
    if kind == "inductor_only":
        return v2._build_rcl_cdb(_subset(specs, "INDUCTOR"), v8)
    if kind == "cap_ind_only":
        return v2._build_rcl_cdb(_subset(specs, "CAPACITOR", "INDUCTOR"), v8)
    if kind == "res_cap_only":
        return v2._build_rcl_cdb(_subset(specs, "RESISTOR", "CAPACITOR"), v8)
    raise ValueError(f"Unknown CDB mode {kind}.")


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


def _chunk_for(
    order: str,
    records: dict[str, Any],
    *,
    header: bytes,
    bridge_core: bytes,
    res_templates: Any,
) -> tuple[bytes, str]:
    cap_outputs = b"".join(records["cap_outputs"])
    cap_groups = b"".join(records["cap_groups"])
    res_block = v3_res_block(records, res_templates)
    ind_seq_final = v3_ind_seq_block(records, final=True)
    ind_seq_nonfinal = v3_ind_seq_block(records, final=False)
    ind_outputs, ind_groups_final = v3_ind_outputs_first_block(records, final=True)

    if order == "res_then_ind":
        body = res_block + ind_seq_final
        desc = "resistor block, donor05 sequential inductor block final"
    elif order == "ind_then_res":
        body = ind_seq_nonfinal + res_block
        desc = "donor05 sequential inductor block, resistor block final"
    elif order == "res_then_cap_ind_joined":
        body = res_block + cap_outputs + ind_outputs + cap_groups + ind_groups_final
        desc = "resistor block first, then capacitor+inductor outputs-first block final"
    elif order == "rescap_then_ind":
        body = cap_outputs + cap_groups + res_block + ind_seq_final
        desc = "capacitor block, resistor block, donor05 sequential inductor block final"
    else:
        raise ValueError(f"Unknown order {order}.")
    chunk = bytearray(header + bridge_core + body)
    chunk[-1] = 0xFF
    return bytes(chunk), desc


def _validate(chunk: bytes, records: dict[str, Any], *, bridge_count: int) -> list[str]:
    issues: list[str] = []
    counts = records["counts"]
    ground = counts["ground_terminal_count"]
    topology_len = len(records["topology"])
    expected = {
        "$TERPOWER": bridge_count,
        "$TERINPUT": topology_len,
        "$TEROUTPUT": topology_len - ground + bridge_count,
        "$TERGROUND": ground,
        "WIRE": topology_len * 2 + bridge_count,
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
    return issues


def _payload(case_id: str, specs: list[Any], order_desc: str, cdb_mode: str, records: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v4-resistor-boundary",
        "generator_target": "proteus-8.13-mixed-rcl-resistor-boundary-diagnostic",
        "case_id": case_id,
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _nodes(specs)],
        "components": [
            {"idx": spec.idx, "ref": spec.ref, "type": spec.kind, "value": spec.value, "nodes": [spec.left, spec.right], "visual": {"x": spec.x, "y": spec.y}}
            for spec in specs
        ],
        "metadata": {"object_order": order_desc, "cdb_mode": cdb_mode, "topology": records["topology"]},
    }


def _write_case(
    *,
    case_id: str,
    specs: list[Any],
    order: str,
    cdb_mode: str,
    use_bridge: bool,
    base_project: Path,
    resistor_donor: Path,
    header: bytes,
    bridge_core: bytes,
    res_templates: Any,
    records: dict[str, Any],
    v2: Any,
    v8: Any,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    effective_bridge = bridge_core if use_bridge else b""
    chunk, order_desc = _chunk_for(order, records, header=header, bridge_core=effective_bridge, res_templates=res_templates)
    cdb = _cdb_for(cdb_mode, specs, base_project=base_project, v2=v2, v8=v8)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(resistor_donor, "ROOT.DSN"), chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    issues = _validate(chunk, records, bridge_count=1 if use_bridge else 0)
    if rv9._extract_object_chunk(dsn) != chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v4_resistor_boundary_not_locked",
        "order_key": order,
        "object_order": order_desc,
        "cdb_mode": cdb_mode,
        "uses_power_bridge": use_bridge,
        "component_count": len(specs),
        "resistor_count": records["counts"]["resistor_count"],
        "capacitor_count": records["counts"]["capacitor_count"],
        "inductor_count": records["counts"]["inductor_count"],
        "ground_terminal_count": records["counts"]["ground_terminal_count"],
        "topology": records["topology"],
        "static_validation_issues": issues,
        "section_pointer_values": pointers,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            "object_chunk": rv9._sha256_bytes(chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, specs, order_desc, cdb_mode, records), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\nOrder: {order_desc}\nCDB mode: {cdb_mode}\nPower bridge: {use_bridge}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    global v3_res_block, v3_ind_seq_block, v3_ind_outputs_first_block
    v2 = _load_module("mixed_rcl_v2_temp_for_v4", V2_PATH)
    v3 = _load_module("mixed_rcl_v3_temp_for_v4", V3_PATH)
    v8 = _load_module("inductor_v8_temp_for_v4", V8_PATH)
    v3_res_block = v3._res_block
    v3_ind_seq_block = v3._ind_seq_block
    v3_ind_outputs_first_block = v3._ind_outputs_first_block

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

    cap_templates = v3.mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ind_templates = v8._load_six_templates(inductor_donor)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")
    header = cap_templates.header

    rl_power = _rl_specs(v2, power=True)
    rl_internal = _rl_specs(v2, power=False)
    rcl = _rcl_specs(v2)

    def rec(specs: list[Any]) -> dict[str, Any]:
        return v3._records(specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates, v8=v8)

    case_defs = [
        ("RCL_V4_T01_RL_INTERNAL_NO_POWER_FULL_CDB", rl_internal, "res_then_ind", "full", False),
        ("RCL_V4_T02_RL_POWER_NO_BRIDGE_FULL_CDB", rl_power, "res_then_ind", "full", False),
        ("RCL_V4_T03_RL_POWER_FULL_CDB", rl_power, "res_then_ind", "full", True),
        ("RCL_V4_T04_RL_POWER_E001_CDB", rl_power, "res_then_ind", "e001", True),
        ("RCL_V4_T05_RL_POWER_RES_ONLY_CDB", rl_power, "res_then_ind", "resistor_only", True),
        ("RCL_V4_T06_RL_POWER_IND_ONLY_CDB", rl_power, "res_then_ind", "inductor_only", True),
        ("RCL_V4_T07_RL_POWER_IND_THEN_RES_E001_CDB", rl_power, "ind_then_res", "e001", True),
        ("RCL_V4_T08_RCL_RES_THEN_CAPIND_JOINED_FULL_CDB", rcl, "res_then_cap_ind_joined", "full", True),
        ("RCL_V4_T09_RCL_RES_THEN_CAPIND_JOINED_CAP_IND_CDB", rcl, "res_then_cap_ind_joined", "cap_ind_only", True),
        ("RCL_V4_T10_RCL_RESCAP_THEN_IND_RESCAP_CDB", rcl, "rescap_then_ind", "res_cap_only", True),
    ]

    manifests: list[dict[str, Any]] = []
    for case_id, specs, order, cdb_mode, use_bridge in case_defs:
        manifests.append(
            _write_case(
                case_id=case_id,
                specs=specs,
                order=order,
                cdb_mode=cdb_mode,
                use_bridge=use_bridge,
                base_project=base,
                resistor_donor=resistor_donor,
                header=header,
                bridge_core=bridge_core,
                res_templates=res_templates,
                records=rec(specs),
                v2=v2,
                v8=v8,
            )
        )

    summary = {
        "case": "MIXED_RCL_V4_RESISTOR_BOUNDARY_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "why": "V3 user feedback showed only C+L T03 and T05 worked; every resistor+inductor case failed.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "T01 checks R+L with no V0/G0 bridge at all.",
            "T02 checks R+L with V0/G0 labels but no power bridge.",
            "T03 is the failed-shape full-CDB control.",
            "T04-T07 vary ROOT.CDB content while keeping the same visual R+L records.",
            "T08-T10 test whether resistor records can coexist when the accepted C+L block remains final or CDB omits one family.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V4 resistor-boundary pack.\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport which cases work. T01-T07 are the most important resistor/inductor boundary probes.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V4_RESISTOR_BOUNDARY_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "case_count": len(manifests), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
