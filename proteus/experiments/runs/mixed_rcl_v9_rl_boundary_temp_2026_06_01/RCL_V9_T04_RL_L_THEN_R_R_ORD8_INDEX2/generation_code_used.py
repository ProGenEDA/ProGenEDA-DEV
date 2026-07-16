"""Generate R/L boundary diagnostics after V8 only T01 worked.

V8 showed:

- free L/C donor records + final terminal R works;
- terminal C/L before final terminal R fails, even with no power/ground.

The remaining narrow boundary is terminal-attached RESISTOR plus
terminal-attached REALIND. This pack avoids large topology noise and varies:

- R/L object order,
- resistor component index and suffix range,
- global visual component indices for R and L,
- adding C only after the R/L hypotheses are isolated.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_passive as mp
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "mixed_rcl_v9_rl_boundary_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V3_PATH = Path(__file__).with_name("generate_mixed_rcl_v3_isolation_temp.py")
V7_PATH = Path(__file__).with_name("generate_mixed_rcl_v7_resistor_suffix_order_temp.py")
V8_IND_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")

BASE_X = -7366000
BASE_Y = 5080000
SAFE_X_STEP = 3810000


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
        "CAPACITOR",
        "CAP10",
        "REALIND",
        "COMPONENT ID",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _zero_last(record: bytes) -> bytes:
    return record[:-1] + b"\x00" if record else record


def _specs(v2: Any, mode: str) -> list[Any]:
    if mode == "rl_disconnected":
        return [
            v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", "R1", "R2", BASE_X, BASE_Y, {}),
            v2.RclSpec(2, "L1", "L1", "INDUCTOR", "1mH", "1mH", "L1", "L2", BASE_X + SAFE_X_STEP, BASE_Y, {}),
        ]
    if mode == "rl_connected":
        return [
            v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", "N1", "N2", BASE_X, BASE_Y, {}),
            v2.RclSpec(2, "L1", "L1", "INDUCTOR", "1mH", "1mH", "N2", "N3", BASE_X + SAFE_X_STEP, BASE_Y, {}),
        ]
    if mode == "clr_disconnected":
        return [
            v2.RclSpec(1, "C1", "C1", "CAPACITOR", "1nF", "1nF", "C1", "C2", BASE_X, BASE_Y, {}),
            v2.RclSpec(2, "L1", "L1", "INDUCTOR", "1mH", "1mH", "L1", "L2", BASE_X + SAFE_X_STEP, BASE_Y, {}),
            v2.RclSpec(3, "R1", "R1", "RESISTOR", "1k", "1k", "R1", "R2", BASE_X + 2 * SAFE_X_STEP, BASE_Y, {}),
        ]
    if mode == "rcl_power_series":
        return [
            v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", "V0", "N1", BASE_X, BASE_Y, {}),
            v2.RclSpec(2, "C1", "C1", "CAPACITOR", "1uF", "1uF", "N1", "N2", BASE_X + SAFE_X_STEP, BASE_Y, {}),
            v2.RclSpec(3, "L1", "L1", "INDUCTOR", "1mH", "1mH", "N2", "G0", BASE_X + 2 * SAFE_X_STEP, BASE_Y, {}),
        ]
    raise ValueError(f"Unknown mode {mode}.")


def _records(v3: Any, v8_ind: Any, specs: list[Any], *, cap_templates: Any, res_templates: Any, ind_templates: Any) -> dict[str, Any]:
    return v3._records(
        specs,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
        v8=v8_ind,
    )


def _patch_inductor_record(
    record: dict[str, Any],
    *,
    component_index: int | None = None,
    suffixes: tuple[int, int] | None = None,
) -> dict[str, Any]:
    patched = dict(record)
    inp = bytearray(record["input"])
    out = bytearray(record["output"])
    ind = bytearray(record["inductor"])
    topo = dict(record["map"])
    if component_index is not None:
        ind[352:356] = rv9._u32(component_index)
        topo["component_index_override"] = component_index
    if suffixes is not None:
        in_suffix, out_suffix = suffixes
        inp[-4:-2] = rv9._u16(in_suffix)
        out[-4:-2] = rv9._u16(out_suffix)
        ind[365:367] = rv9._u16(in_suffix)
        ind[367:369] = b"\x01\x00"
        ind[369:371] = rv9._u16(out_suffix)
        ind[371:373] = b"\x01\x00"
        topo["in_suffix"] = f"{in_suffix:04x}"
        topo["out_suffix"] = f"{out_suffix:04x}"
        topo["suffix_override"] = True
    patched["input"] = bytes(inp)
    patched["output"] = bytes(out)
    patched["inductor"] = bytes(ind)
    patched["map"] = topo
    return patched


def _ind_block(record: dict[str, Any], *, final: bool) -> bytes:
    wire_right = record["wire_right"]
    if final:
        wire_right = wire_right[:-1] + b"\xff" if len(wire_right) == 50 else wire_right + b"\xff"
    else:
        wire_right = _zero_last(wire_right)
    return record["input"] + record["output"] + record["inductor"] + record["wire_left"] + wire_right


def _cap_block(records: dict[str, Any], *, final: bool) -> bytes:
    if not records["cap_outputs"]:
        return b""
    parts = list(records["cap_groups"])
    if final:
        parts[-1] = parts[-1] + b"\xff" if len(parts[-1]) == mp.TRIMMED_WIRE_SIZE else parts[-1][:-1] + b"\xff"
    return b"".join(records["cap_outputs"]) + b"".join(parts)


def _res_block(
    v7: Any,
    spec: Any,
    *,
    res_templates: Any,
    ordinal: int,
    component_index: int | None = None,
    suffixes: tuple[int, int] | None = None,
    final: bool,
) -> tuple[bytes, dict[str, Any]]:
    return v7._custom_resistor_block(
        spec,
        ordinal=ordinal,
        component_index=component_index,
        suffixes=suffixes,
        final=final,
        res_templates=res_templates,
    )


def _validate(chunk: bytes, expected: dict[str, int], topology: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    counts = _marker_counts(chunk)
    for marker, want in expected.items():
        if counts[marker] != want:
            issues.append(f"{marker} count {counts[marker]} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if len({item["in_suffix"] for item in topology}) != len(topology):
        issues.append("input suffixes are not globally unique")
    if len({item["out_suffix"] for item in topology}) != len(topology):
        issues.append("output suffixes are not globally unique")
    return issues


def _expected_counts(*, r: int, l: int, c: int, power: int = 0, ground: int = 0) -> dict[str, int]:
    terminal = r + l + c
    return {
        "$TERPOWER": power,
        "$TERINPUT": terminal,
        "$TEROUTPUT": terminal - ground + power,
        "$TERGROUND": ground,
        "WIRE": terminal * 2 + power,
        "RESISTOR": r * 2,
        "CAPACITOR": c,
        "CAP10": c,
        "REALIND": l * 3,
        "COMPONENT ID": terminal,
    }


def _nodes(specs: list[Any]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_header_project: Path,
    cdb: bytes,
    object_chunk: bytes,
    specs: list[Any],
    topology: list[dict[str, Any]],
    object_order: str,
    issues: list[str],
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
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
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues = [*issues, "ROOT.DSN object chunk differs from requested chunk"]
    payload = {
        "schema_version": "mixed-rcl-temp/v9-rl-boundary",
        "generator_target": "proteus-8.13-mixed-rcl-rl-boundary-diagnostic",
        "case_id": case_id,
        "nodes": [{"id": node, "kind": "power" if node == "V0" else "ground" if node == "G0" else "internal"} for node in _nodes(specs)],
        "components": [
            {"idx": spec.idx, "ref": spec.ref, "type": spec.kind, "value": spec.value, "nodes": [spec.left, spec.right], "visual": {"x": spec.x, "y": spec.y}}
            for spec in specs
        ],
        "metadata": {"object_order": object_order, "topology": topology},
    }
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v9_rl_boundary_not_locked",
        "description": description,
        "donor_header_project": str(donor_header_project),
        "object_order": object_order,
        "component_count": len(specs),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "topology": topology,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
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
    (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nOrder: {object_order}\n\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_temp_for_v9", V2_PATH)
    v3 = _load_module("mixed_rcl_v3_temp_for_v9", V3_PATH)
    v7 = _load_module("mixed_rcl_v7_temp_for_v9", V7_PATH)
    v8_ind = _load_module("inductor_v8_temp_for_rcl_v9", V8_IND_PATH)

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
    inductor_donor = registry.get("inductor_05_six_terminal").path
    bridge_donor = registry.get("power_terminal_bridge_donor").path

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ind_templates = v8_ind._load_six_templates(inductor_donor)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")

    cases: list[dict[str, Any]] = []

    def add_rl(
        case_id: str,
        description: str,
        *,
        mode: str,
        order: str,
        r_ordinal: int,
        r_component_index: int | None = None,
        r_suffixes: tuple[int, int] | None = None,
        l_component_index: int | None = None,
        l_suffixes: tuple[int, int] | None = None,
    ) -> None:
        specs = _specs(v2, mode)
        records = _records(v3, v8_ind, specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates)
        r_spec = next(spec for spec in specs if spec.kind == "RESISTOR")
        l_record = _patch_inductor_record(records["ind_records"][0], component_index=l_component_index, suffixes=l_suffixes)
        r_final, r_info_final = _res_block(v7, r_spec, res_templates=res_templates, ordinal=r_ordinal, component_index=r_component_index, suffixes=r_suffixes, final=True)
        r_nonfinal, r_info_nonfinal = _res_block(v7, r_spec, res_templates=res_templates, ordinal=r_ordinal, component_index=r_component_index, suffixes=r_suffixes, final=False)
        if order == "L_THEN_R":
            body = _ind_block(l_record, final=False) + r_final
            topology = [l_record["map"], r_info_final]
            order_desc = "terminal inductor non-final, terminal resistor final"
        elif order == "R_THEN_L":
            body = r_nonfinal + _ind_block(l_record, final=True)
            topology = [r_info_nonfinal, l_record["map"]]
            order_desc = "terminal resistor non-final, terminal inductor final"
        else:
            raise ValueError(order)
        chunk = bytearray(cap_templates.header + body)
        chunk[-1] = 0xFF
        cdb = v2._build_rcl_cdb(specs, v8_ind)
        issues = _validate(bytes(chunk), _expected_counts(r=1, l=1, c=0), topology)
        cases.append(
            _write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_header_project=resistor_donor,
                cdb=cdb,
                object_chunk=bytes(chunk),
                specs=specs,
                topology=topology,
                object_order=order_desc,
                issues=issues,
            )
        )

    add_rl(
        "RCL_V9_T01_RL_L_THEN_R_DEFAULT",
        "Minimal no-power R+L boundary: terminal L first, terminal R final, default per-family indices/suffixes. Expected to reproduce the V8 failure.",
        mode="rl_disconnected",
        order="L_THEN_R",
        r_ordinal=1,
    )
    add_rl(
        "RCL_V9_T02_RL_R_THEN_L_DEFAULT",
        "Minimal no-power R+L boundary: terminal R first, terminal L final, default per-family indices/suffixes.",
        mode="rl_disconnected",
        order="R_THEN_L",
        r_ordinal=1,
    )
    add_rl(
        "RCL_V9_T03_RL_L_THEN_R_R_ORD2_INDEX2",
        "Terminal L first, terminal R final with resistor ordinal/index moved after L.",
        mode="rl_disconnected",
        order="L_THEN_R",
        r_ordinal=2,
        r_component_index=2,
    )
    add_rl(
        "RCL_V9_T04_RL_L_THEN_R_R_ORD8_INDEX2",
        "Terminal L first, terminal R final using the V7 passing ORD8/index2 resistor policy.",
        mode="rl_disconnected",
        order="L_THEN_R",
        r_ordinal=8,
        r_component_index=2,
    )
    add_rl(
        "RCL_V9_T05_RL_L_THEN_R_R_HIGH_SUFFIX_INDEX2",
        "Terminal L first, terminal R final with high resistor suffixes and component index 2.",
        mode="rl_disconnected",
        order="L_THEN_R",
        r_ordinal=1,
        r_component_index=2,
        r_suffixes=(0x7100, 0x7200),
    )
    add_rl(
        "RCL_V9_T06_RL_GLOBAL_INDEX_SUFFIX_L1_R2",
        "Terminal L first, terminal R final with explicit global-style L index 1 and R index/suffix 2.",
        mode="rl_disconnected",
        order="L_THEN_R",
        r_ordinal=2,
        r_component_index=2,
        l_component_index=1,
    )
    add_rl(
        "RCL_V9_T07_RL_R1_L2_GLOBAL_INDEX_SUFFIX",
        "Terminal R first, terminal L final with explicit global-style R index 1 and L index/suffix 2.",
        mode="rl_disconnected",
        order="R_THEN_L",
        r_ordinal=1,
        r_component_index=1,
        l_component_index=2,
        l_suffixes=(0x0370, 0x03A2),
    )
    add_rl(
        "RCL_V9_T08_RL_CONNECTED_L_THEN_R_ORD2_INDEX2",
        "Connected-label R+L series, no power, terminal L first and terminal R final with R ordinal/index 2.",
        mode="rl_connected",
        order="L_THEN_R",
        r_ordinal=2,
        r_component_index=2,
    )

    def add_clr(
        case_id: str,
        description: str,
        *,
        power: bool,
        r_ordinal: int,
        r_component_index: int,
        r_suffixes: tuple[int, int] | None = None,
        l_component_index: int | None = None,
        l_suffixes: tuple[int, int] | None = None,
    ) -> None:
        specs = _specs(v2, "rcl_power_series" if power else "clr_disconnected")
        records = _records(v3, v8_ind, specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates)
        r_spec = next(spec for spec in specs if spec.kind == "RESISTOR")
        l_record = _patch_inductor_record(records["ind_records"][0], component_index=l_component_index, suffixes=l_suffixes)
        r_block, r_info = _res_block(v7, r_spec, res_templates=res_templates, ordinal=r_ordinal, component_index=r_component_index, suffixes=r_suffixes, final=True)
        cap = _cap_block(records, final=False)
        body = cap + _ind_block(l_record, final=False) + r_block
        prefix = cap_templates.header + (bridge_core if power else b"")
        chunk = bytearray(prefix + body)
        chunk[-1] = 0xFF
        topology = [item for item in records["topology"] if item["kind"] == "CAPACITOR"] + [l_record["map"], r_info]
        ground = sum(1 for item in topology if item["output_marker"] == "$TERGROUND")
        cdb = v2._build_rcl_cdb(specs, v8_ind)
        issues = _validate(bytes(chunk), _expected_counts(r=1, l=1, c=1, power=1 if power else 0, ground=ground), topology)
        cases.append(
            _write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_header_project=resistor_donor,
                cdb=cdb,
                object_chunk=bytes(chunk),
                specs=specs,
                topology=topology,
                object_order=("power bridge, " if power else "") + "terminal capacitor block, terminal inductor non-final, terminal resistor final",
                issues=issues,
            )
        )

    add_clr(
        "RCL_V9_T09_CLR_R_ORD2_INDEX3",
        "All-terminal C/L/R disconnected labels with R final and R component index moved to 3.",
        power=False,
        r_ordinal=2,
        r_component_index=3,
        l_component_index=2,
    )
    add_clr(
        "RCL_V9_T10_CLR_R_HIGH_SUFFIX_INDEX3",
        "All-terminal C/L/R disconnected labels with high resistor suffixes and global-style indices.",
        power=False,
        r_ordinal=1,
        r_component_index=3,
        r_suffixes=(0x7100, 0x7200),
        l_component_index=2,
    )
    add_clr(
        "RCL_V9_T11_POWER_RCL_R_ORD2_INDEX3",
        "Small V0/G0 R/C/L series using terminal C/L before final R with global-style indices.",
        power=True,
        r_ordinal=2,
        r_component_index=3,
        l_component_index=2,
    )

    summary = {
        "batch_id": "MIXED_RCL_V9_RL_BOUNDARY_STATIC_20260601",
        "status": "static_generated_awaiting_user_proteus_test",
        "source_feedback": "V8 only T01 worked. Therefore the next boundary is terminal-attached R plus terminal-attached L, not power/ground or large topology scale.",
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "object_order": item["object_order"],
                "marker_counts": item["marker_counts"],
                "topology": item["topology"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "MIXED_RCL_V9_RL_BOUNDARY_TEMP_2026_06_01\n\n"
        "Open in order and stop at the first case that works after a failing control:\n"
        "1. T01-T02: minimal R+L no-power order controls.\n"
        "2. T03-T07: R+L no-power index/suffix hypotheses.\n"
        "3. T08: connected-label R+L no-power check.\n"
        "4. T09-T10: add capacitor only after R+L hypotheses.\n"
        "5. T11: add V0/G0 only after an all-terminal R+L/C result works.\n\n"
        "If T01-T08 all fail, the next required evidence is a Proteus-created manual donor containing a terminal-attached resistor and terminal-attached inductor in the same project.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "experiments" / "MIXED_RCL_V9_RL_BOUNDARY_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
