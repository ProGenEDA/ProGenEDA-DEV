"""Generate R/C/L diagnostics from the user-supplied manual RLC donor.

V3 showed capacitor+inductor can work, while every generated case containing
both resistor and inductor failed. The user then supplied ``rlc.pdsprj``. This
pack keeps the first tests donor-controlled before trying generated terminal
topologies again.
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

OUT_ROOT = REPO_ROOT / "experiments" / "mixed_rcl_v5_manual_donor_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V3_PATH = Path(__file__).with_name("generate_mixed_rcl_v3_isolation_temp.py")
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")

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


def _positions(data: bytes, marker: bytes) -> list[int]:
    out: list[int] = []
    start = 0
    while True:
        pos = data.find(marker, start)
        if pos < 0:
            return out
        out.append(pos)
        start = pos + 1


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


def _donor_analysis(dsn: bytes, cdb: bytes) -> dict[str, Any]:
    chunk = rv9._extract_object_chunk(dsn)
    return {
        "root_dsn_len": len(dsn),
        "root_cdb_len": len(cdb),
        "object_chunk_len": len(chunk),
        "object_chunk_sha256": rv9._sha256_bytes(chunk),
        "root_cdb_sha256": rv9._sha256_bytes(cdb),
        "marker_counts": _marker_counts(chunk),
        "chunk_marker_positions": {
            "L1": _positions(chunk, b"L1"),
            "R1": _positions(chunk, b"R1"),
            "C1": _positions(chunk, b"C1"),
            "REALIND": _positions(chunk, b"REALIND"),
            "RESISTOR": _positions(chunk, b"RESISTOR"),
            "CAPACITOR": _positions(chunk, b"CAPACITOR"),
            "COMPONENT ID": _positions(chunk, b"COMPONENT ID"),
        },
        "observed_free_component_order": [
            {"kind": "INDUCTOR", "ref": "L1", "record_start_guess": 1},
            {"kind": "RESISTOR", "ref": "R1", "record_start_guess": 375},
            {"kind": "CAPACITOR", "ref": "C1", "record_start_guess": 722},
        ],
        "note": "The manual donor contains free L/R/C component records and matching CDB entries, but no terminal or WIRE records.",
    }


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _nodes(specs: list[Any]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _lrc_specs(v2: Any) -> list[Any]:
    return [
        v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", "V0", "N1", BASE_X, BASE_Y, {}),
        v2.RclSpec(2, "R1", "R1", "RESISTOR", "10k", "10k", "N1", "N2", BASE_X + SAFE_X_STEP, BASE_Y, {}),
        v2.RclSpec(3, "C1", "C1", "CAPACITOR", "1nF", "1nF", "N2", "G0", BASE_X + 2 * SAFE_X_STEP, BASE_Y, {}),
    ]


def _zero_last(record: bytes) -> bytes:
    return record[:-1] + b"\x00" if record else record


def _res_block(records: dict[str, Any], res_templates: Any) -> bytes:
    if not records["res_inputs"]:
        return b""
    return b"".join(records["res_inputs"]) + b"".join(records["res_outputs"]) + res_templates.separator + b"".join(records["res_groups"])


def _cap_block(records: dict[str, Any]) -> bytes:
    return b"".join(records["cap_outputs"]) + b"".join(records["cap_groups"])


def _ind_seq_block(v3: Any, records: dict[str, Any], *, final: bool) -> bytes:
    return v3._ind_seq_block(records, final=final)


def _ind_outputs_first_block(v3: Any, records: dict[str, Any], *, final: bool) -> tuple[bytes, bytes]:
    return v3._ind_outputs_first_block(records, final=final)


def _chunk_for_order(order: str, records: dict[str, Any], *, header: bytes, bridge_core: bytes, res_templates: Any, v3: Any) -> tuple[bytes, str]:
    cap = _cap_block(records)
    res = _res_block(records, res_templates)

    if order == "donor_lrc_ind_res_cap":
        body = _ind_seq_block(v3, records, final=False) + _zero_last(res) + cap
        desc = "power bridge, inductor block, resistor block, capacitor block; matches manual donor L/R/C family order"
    elif order == "donor_lrc_ind_cap_res":
        body = _ind_seq_block(v3, records, final=False) + cap + res
        desc = "power bridge, inductor block, capacitor block, resistor block"
    elif order == "known_cl_joined_then_res":
        ind_outputs, ind_groups = _ind_outputs_first_block(v3, records, final=False)
        body = b"".join(records["cap_outputs"]) + ind_outputs + b"".join(records["cap_groups"]) + ind_groups + res
        desc = "power bridge, known-good capacitor+inductor outputs-first block, then resistor block"
    elif order == "v2_cap_res_ind":
        body = cap + _zero_last(res) + _ind_seq_block(v3, records, final=True)
        desc = "power bridge, capacitor block, resistor block, inductor block; V2 order retested with manual donor CDB"
    elif order == "donor_lrc_no_power":
        body = _ind_seq_block(v3, records, final=False) + _zero_last(res) + cap
        desc = "no power bridge, inductor block, resistor block, capacitor block"
        bridge_core = b""
    else:
        raise ValueError(f"Unknown order {order}.")

    chunk = bytearray(header + bridge_core + body)
    chunk[-1] = 0xFF
    return bytes(chunk), desc


def _validate_generated_chunk(chunk: bytes, records: dict[str, Any], *, bridge_count: int) -> list[str]:
    issues: list[str] = []
    counts = records["counts"]
    topology_len = len(records["topology"])
    ground = counts["ground_terminal_count"]
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
        "COMPONENT ID": topology_len,
    }
    marker_counts = _marker_counts(chunk)
    for marker, want in expected.items():
        got = marker_counts[marker]
        if got != want:
            issues.append(f"{marker} count {got} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    suffixes_in = {item["in_suffix"] for item in records["topology"]}
    suffixes_out = {item["out_suffix"] for item in records["topology"]}
    if len(suffixes_in) != topology_len:
        issues.append("input suffixes are not globally unique")
    if len(suffixes_out) != topology_len:
        issues.append("output suffixes are not globally unique")
    return issues


def _payload(case_id: str, description: str, specs: list[Any], records: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v5-manual-donor",
        "generator_target": "proteus-8.13-mixed-rcl-manual-donor-diagnostic",
        "case_id": case_id,
        "description": description,
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _nodes(specs)] if specs else [],
        "components": [
            {"idx": spec.idx, "ref": spec.ref, "type": spec.kind, "value": spec.value, "nodes": [spec.left, spec.right], "visual": {"x": spec.x, "y": spec.y}}
            for spec in specs
        ],
        "metadata": {"topology": records["topology"] if records else []},
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    output_dsn: bytes,
    output_cdb: bytes,
    donor_template_project: Path,
    donor_object_chunk: bytes,
    specs: list[Any] | None = None,
    records: dict[str, Any] | None = None,
    static_issues: list[str] | None = None,
    extra_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"

    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": output_cdb, "ROOT.DSN": output_dsn})
    cdb_path.write_bytes(output_cdb)
    dsn_path.write_bytes(output_dsn)
    chunk_path.write_bytes(donor_object_chunk)

    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v5_manual_donor_not_locked",
        "description": description,
        "base_project": str(base_project),
        "donor_template_project": str(donor_template_project),
        "object_chunk_len": len(donor_object_chunk),
        "root_cdb_len": len(output_cdb),
        "root_dsn_len": len(output_dsn),
        "marker_counts": _marker_counts(donor_object_chunk),
        "static_validation_issues": static_issues or [],
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            chunk_path.name: rv9._sha256_file(chunk_path),
            "ROOT.CDB": rv9._sha256_bytes(output_cdb),
            "object_chunk": rv9._sha256_bytes(donor_object_chunk),
        },
    }
    if extra_manifest:
        manifest.update(extra_manifest)

    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, description, specs or [], records), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nStatic validation issues: {manifest['static_validation_issues']}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _write_deterministic_repack(case_id: str, donor_project: Path, donor_dsn: bytes, donor_cdb: bytes) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(donor_project, output_path, {})
    chunk = rv9._extract_object_chunk(donor_dsn)
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v5_manual_donor_not_locked",
        "description": "Deterministic repack of the supplied RLC donor with no internal file changes.",
        "base_project": str(donor_project),
        "object_chunk_len": len(chunk),
        "root_cdb_len": len(donor_cdb),
        "root_dsn_len": len(donor_dsn),
        "marker_counts": _marker_counts(chunk),
        "static_validation_issues": [],
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            "ROOT.CDB": rv9._sha256_bytes(donor_cdb),
            "object_chunk": rv9._sha256_bytes(chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, manifest["description"], [], None), indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\nDeterministic repack of the supplied RLC donor. If this fails, stop and report the exact Proteus error.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_temp_for_v5", V2_PATH)
    v3 = _load_module("mixed_rcl_v3_temp_for_v5", V3_PATH)
    v8 = _load_module("inductor_v8_temp_for_v5", V8_PATH)

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
    rlc_donor = registry.get("rlc_manual_donor").path

    base_dsn = read_internal_file(base, "ROOT.DSN")
    rlc_dsn = read_internal_file(rlc_donor, "ROOT.DSN")
    rlc_cdb = read_internal_file(rlc_donor, "ROOT.CDB")
    rlc_chunk = rv9._extract_object_chunk(rlc_dsn)
    resistor_dsn = read_internal_file(resistor_donor, "ROOT.DSN")

    donor_analysis = _donor_analysis(rlc_dsn, rlc_cdb)
    (OUT_ROOT / "manual_donor_analysis.json").write_text(json.dumps(donor_analysis, indent=2) + "\n", encoding="utf-8")

    manifests: list[dict[str, Any]] = []
    manifests.append(_write_deterministic_repack("RCL_V5_T01_EXACT_DONOR_REPACK", rlc_donor, rlc_dsn, rlc_cdb))

    donor_on_e001_dsn = patch_root_dsn_version(rlc_dsn, PROTEUS_813)
    manifests.append(
        _write_case(
            case_id="RCL_V5_T02_DONOR_DSN_CDB_ON_E001_CONTAINER",
            description="E001 container/project XML with the manual donor ROOT.DSN and ROOT.CDB copied intact.",
            base_project=base,
            output_dsn=donor_on_e001_dsn,
            output_cdb=rlc_cdb,
            donor_template_project=rlc_donor,
            donor_object_chunk=rlc_chunk,
        )
    )

    rebuilt_with_rlc_header, rlc_header_pointers = rv9.build_dsn(base_dsn, rlc_dsn, rlc_chunk)
    rebuilt_with_rlc_header = patch_root_dsn_version(rebuilt_with_rlc_header, PROTEUS_813)
    manifests.append(
        _write_case(
            case_id="RCL_V5_T03_DONOR_CHUNK_DONOR_HEADER_E001",
            description="Manual donor object chunk and CDB inserted into E001 using the manual donor DSN device/header section.",
            base_project=base,
            output_dsn=rebuilt_with_rlc_header,
            output_cdb=rlc_cdb,
            donor_template_project=rlc_donor,
            donor_object_chunk=rlc_chunk,
            extra_manifest={"section_pointer_values": rlc_header_pointers},
        )
    )

    rebuilt_with_res_header, res_header_pointers = rv9.build_dsn(base_dsn, resistor_dsn, rlc_chunk)
    rebuilt_with_res_header = patch_root_dsn_version(rebuilt_with_res_header, PROTEUS_813)
    manifests.append(
        _write_case(
            case_id="RCL_V5_T04_DONOR_CHUNK_RESISTOR_HEADER_E001",
            description="Manual donor object chunk and CDB inserted into E001 using the locked resistor donor DSN device/header section.",
            base_project=base,
            output_dsn=rebuilt_with_res_header,
            output_cdb=rlc_cdb,
            donor_template_project=resistor_donor,
            donor_object_chunk=rlc_chunk,
            extra_manifest={"section_pointer_values": res_header_pointers},
        )
    )

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(resistor_dsn, resistor_donor)
    ind_templates = v8._load_six_templates(inductor_donor)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")
    specs = _lrc_specs(v2)
    records = v3._records(
        specs,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
        v8=v8,
    )

    generated_cases = [
        ("RCL_V5_T05_LRC_ORDER_DONOR_CDB", "donor_lrc_ind_res_cap", rlc_cdb, "manual donor CDB"),
        ("RCL_V5_T06_LRC_ORDER_GENERATED_CDB", "donor_lrc_ind_res_cap", v2._build_rcl_cdb(specs, v8), "generated CDB in L/R/C spec order"),
        ("RCL_V5_T07_IND_CAP_RES_DONOR_CDB", "donor_lrc_ind_cap_res", rlc_cdb, "manual donor CDB"),
        ("RCL_V5_T08_CL_JOINED_THEN_RES_DONOR_CDB", "known_cl_joined_then_res", rlc_cdb, "manual donor CDB"),
        ("RCL_V5_T09_V2_ORDER_DONOR_CDB", "v2_cap_res_ind", rlc_cdb, "manual donor CDB"),
        ("RCL_V5_T10_LRC_NO_POWER_DONOR_CDB", "donor_lrc_no_power", rlc_cdb, "manual donor CDB; no power bridge isolation"),
    ]

    for case_id, order, cdb, cdb_desc in generated_cases:
        chunk, order_desc = _chunk_for_order(order, records, header=cap_templates.header, bridge_core=bridge_core, res_templates=res_templates, v3=v3)
        bridge_count = 0 if order == "donor_lrc_no_power" else 1
        dsn, pointers = rv9.build_dsn(base_dsn, resistor_dsn, chunk)
        dsn = patch_root_dsn_version(dsn, PROTEUS_813)
        issues = _validate_generated_chunk(chunk, records, bridge_count=bridge_count)
        if rv9._extract_object_chunk(dsn) != chunk:
            issues.append("ROOT.DSN object chunk differs from requested chunk")
        manifests.append(
            _write_case(
                case_id=case_id,
                description=f"{order_desc}. CDB mode: {cdb_desc}.",
                base_project=base,
                output_dsn=dsn,
                output_cdb=cdb,
                donor_template_project=resistor_donor,
                donor_object_chunk=chunk,
                specs=specs,
                records=records,
                static_issues=issues,
                extra_manifest={
                    "order_key": order,
                    "object_order": order_desc,
                    "cdb_mode": cdb_desc,
                    "section_pointer_values": pointers,
                    "topology": records["topology"],
                },
            )
        )

    summary = {
        "batch_id": "MIXED_RCL_V5_MANUAL_DONOR_STATIC_20260601",
        "status": "static_generated_awaiting_user_proteus_test",
        "source_fixture": "rlc_manual_donor",
        "donor_analysis": donor_analysis,
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "static_validation_issues": item["static_validation_issues"],
                "marker_counts": item["marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
            }
            for item in manifests
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "MIXED_RCL_V5_MANUAL_DONOR_TEMP_2026_06_01\n\n"
        "Test in order:\n"
        "1. T01, T02, T03, T04 first. These are donor controls.\n"
        "2. If T01 fails, the supplied donor/repack path is bad; stop.\n"
        "3. If T01 works but T02-T04 fail, report which E001 insertion variant fails first.\n"
        "4. Only then test T05-T10. These reintroduce generated terminal topology around L/R/C.\n\n"
        "T05 and T06 are the key resistor/inductor boundary checks: same L/R/C object order, donor CDB vs generated CDB.\n",
        encoding="utf-8",
    )

    shutil.make_archive(str(OUT_ROOT).replace("mixed_rcl_v5_manual_donor_temp_2026_06_01", "MIXED_RCL_V5_MANUAL_DONOR_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
