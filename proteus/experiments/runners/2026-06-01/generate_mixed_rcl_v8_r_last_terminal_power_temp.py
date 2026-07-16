"""Generate R/C/L diagnostics after V7 proved terminal R works when final.

V7 user feedback: T02-T07 opened. Those cases keep free L/C records first and
place the terminal-attached resistor block last. This pack keeps that invariant
and tests the next risky surfaces in small steps:

- terminal C/L blocks before final terminal R,
- power/ground bridge plus G0 endpoints,
- six and twenty-one mixed networks using C/L blocks first and R block last.
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

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v8_r_last_terminal_power_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V3_PATH = Path(__file__).with_name("generate_mixed_rcl_v3_isolation_temp.py")
V6_PATH = Path(__file__).with_name("generate_mixed_rcl_v6_terminal_boundary_temp.py")
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


def _free_slices(rlc_chunk: bytes) -> dict[str, bytes]:
    return {
        "header": rlc_chunk[:1],
        "L": rlc_chunk[1:375],
        "R": rlc_chunk[375:722],
        "C": rlc_chunk[722:],
    }


def _small_specs(v2: Any, mode: str) -> list[Any]:
    if mode == "disconnected":
        return [
            v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", "L1", "L2", BASE_X, BASE_Y, {}),
            v2.RclSpec(2, "R1", "R1", "RESISTOR", "10k", "10k", "R1", "R2", BASE_X + SAFE_X_STEP, BASE_Y, {}),
            v2.RclSpec(3, "C1", "C1", "CAPACITOR", "1nF", "1nF", "C1", "C2", BASE_X + 2 * SAFE_X_STEP, BASE_Y, {}),
        ]
    if mode == "connected":
        return [
            v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", "N2", "N3", BASE_X + SAFE_X_STEP, BASE_Y, {}),
            v2.RclSpec(2, "R1", "R1", "RESISTOR", "10k", "10k", "N1", "N2", BASE_X, BASE_Y, {}),
            v2.RclSpec(3, "C1", "C1", "CAPACITOR", "1nF", "1nF", "N3", "N4", BASE_X + 2 * SAFE_X_STEP, BASE_Y, {}),
        ]
    if mode == "power_series":
        return [
            v2.RclSpec(1, "R1", "R1", "RESISTOR", "1k", "1k", "V0", "N1", BASE_X, BASE_Y, {}),
            v2.RclSpec(2, "C1", "C1", "CAPACITOR", "1uF", "1uF", "N1", "N2", BASE_X + SAFE_X_STEP, BASE_Y, {}),
            v2.RclSpec(3, "L1", "L1", "INDUCTOR", "1mH", "1mH", "N2", "G0", BASE_X + 2 * SAFE_X_STEP, BASE_Y, {}),
        ]
    raise ValueError(f"Unknown small mode {mode}.")


def _records(v3: Any, v8_ind: Any, specs: list[Any], *, cap_templates: Any, res_templates: Any, ind_templates: Any) -> dict[str, Any]:
    return v3._records(
        specs,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
        v8=v8_ind,
    )


def _cap_block(records: dict[str, Any]) -> bytes:
    return b"".join(records["cap_outputs"]) + b"".join(records["cap_groups"])


def _ind_seq_block(v3: Any, records: dict[str, Any]) -> bytes:
    return v3._ind_seq_block(records, final=False)


def _cl_outputs_first_block(v3: Any, records: dict[str, Any]) -> bytes:
    ind_outputs, ind_groups = v3._ind_outputs_first_block(records, final=False)
    return b"".join(records["cap_outputs"]) + ind_outputs + b"".join(records["cap_groups"]) + ind_groups


def _res_block_final(v3: Any, records: dict[str, Any], res_templates: Any) -> bytes:
    return v3._res_block(records, res_templates)


def _res_block_nonfinal(v3: Any, records: dict[str, Any], res_templates: Any) -> bytes:
    return _zero_last(_res_block_final(v3, records, res_templates))


def _r_last_chunk(
    *,
    header: bytes,
    bridge_core: bytes = b"",
    cl_order: str,
    records: dict[str, Any],
    v3: Any,
    res_templates: Any,
) -> tuple[bytes, str]:
    if cl_order == "cap_then_ind_then_res":
        body = _cap_block(records) + _ind_seq_block(v3, records) + _res_block_final(v3, records, res_templates)
        order_desc = "cap outputs/groups, inductor sequential groups, resistor terminal block final"
    elif cl_order == "cl_outputs_first_then_res":
        body = _cl_outputs_first_block(v3, records) + _res_block_final(v3, records, res_templates)
        order_desc = "capacitor+inductor outputs first, capacitor+inductor groups, resistor terminal block final"
    else:
        raise ValueError(f"Unknown C/L order {cl_order}.")
    chunk = bytearray(header + bridge_core + body)
    chunk[-1] = 0xFF
    return bytes(chunk), order_desc


def _free_lc_r_final_chunk(
    *,
    header: bytes,
    free: dict[str, bytes],
    records: dict[str, Any],
    v3: Any,
    res_templates: Any,
) -> tuple[bytes, str]:
    chunk = bytearray(header + free["L"] + free["C"] + _res_block_final(v3, records, res_templates))
    chunk[-1] = 0xFF
    return bytes(chunk), "free L/C donor records first, resistor terminal block final"


def _validate(chunk: bytes, records: dict[str, Any] | None, *, expected: dict[str, int] | None = None) -> list[str]:
    issues: list[str] = []
    counts = _marker_counts(chunk)
    if expected is not None:
        for marker, want in expected.items():
            if counts[marker] != want:
                issues.append(f"{marker} count {counts[marker]} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if records is not None:
        topology = records["topology"]
        if len({item["in_suffix"] for item in topology}) != len(topology):
            issues.append("input suffixes are not globally unique")
        if len({item["out_suffix"] for item in topology}) != len(topology):
            issues.append("output suffixes are not globally unique")
    return issues


def _expected_counts(
    *,
    resistor_count: int,
    capacitor_count: int,
    inductor_count: int,
    power_bridge_count: int,
    ground_terminal_count: int,
    free_resistor_count: int = 0,
    free_capacitor_count: int = 0,
    free_inductor_count: int = 0,
) -> dict[str, int]:
    terminal_count = resistor_count + capacitor_count + inductor_count
    return {
        "$TERPOWER": power_bridge_count,
        "$TERINPUT": terminal_count,
        "$TEROUTPUT": terminal_count - ground_terminal_count + power_bridge_count,
        "$TERGROUND": ground_terminal_count,
        "WIRE": terminal_count * 2 + power_bridge_count,
        "RESISTOR": resistor_count * 2 + free_resistor_count * 2,
        "CAPACITOR": capacitor_count + free_capacitor_count,
        "CAP10": capacitor_count + free_capacitor_count,
        "REALIND": inductor_count * 3 + free_inductor_count * 3,
        "COMPONENT ID": terminal_count + free_resistor_count + free_capacitor_count + free_inductor_count,
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_header_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    specs: list[Any],
    records: dict[str, Any] | None,
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
    topology = [] if records is None else sorted(records["topology"], key=lambda item: item["idx"])
    payload = {
        "schema_version": "mixed-rcl-temp/v8-r-last-terminal-power",
        "generator_target": "proteus-8.13-mixed-rcl-r-last-diagnostic",
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
        "status": "temporary_mixed_rcl_v8_r_last_not_locked",
        "description": description,
        "donor_header_project": str(donor_header_project),
        "component_count": len(specs),
        "resistor_count": sum(1 for spec in specs if spec.kind == "RESISTOR"),
        "capacitor_count": sum(1 for spec in specs if spec.kind == "CAPACITOR"),
        "inductor_count": sum(1 for spec in specs if spec.kind == "INDUCTOR"),
        "object_order": object_order,
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
    (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nOrder: {object_order}\n\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _nodes(specs: list[Any]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_temp_for_v8", V2_PATH)
    v3 = _load_module("mixed_rcl_v3_temp_for_v8", V3_PATH)
    v6 = _load_module("mixed_rcl_v6_temp_for_v8", V6_PATH)
    v8_ind = _load_module("inductor_v8_temp_for_rcl_v8", V8_IND_PATH)

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

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ind_templates = v8_ind._load_six_templates(inductor_donor)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")
    rlc_chunk = rv9._extract_object_chunk(read_internal_file(rlc_donor, "ROOT.DSN"))
    free = _free_slices(rlc_chunk)

    cases: list[dict[str, Any]] = []

    def add(
        case_id: str,
        description: str,
        specs: list[Any],
        *,
        chunk: bytes,
        records: dict[str, Any] | None,
        object_order: str,
        cdb: bytes,
        expected: dict[str, int],
        donor_header_project: Path = resistor_donor,
    ) -> None:
        issues = _validate(chunk, records, expected=expected)
        cases.append(
            _write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_header_project=donor_header_project,
                object_chunk=chunk,
                cdb=cdb,
                specs=specs,
                records=records,
                object_order=object_order,
                issues=issues,
            )
        )

    disconnected_specs = _small_specs(v2, "disconnected")
    disconnected_records = _records(v3, v8_ind, disconnected_specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates)
    chunk, order = _free_lc_r_final_chunk(header=free["header"], free=free, records=disconnected_records, v3=v3, res_templates=res_templates)
    add(
        "RCL_V8_T01_FREE_L_C_THEN_R_FINAL_CONTROL",
        "Reproduce the V7 passing boundary: free L/C donor records first, terminal R final.",
        disconnected_specs,
        chunk=chunk,
        records=None,
        object_order=order,
        cdb=read_internal_file(rlc_donor, "ROOT.CDB"),
        expected=_expected_counts(resistor_count=1, capacitor_count=0, inductor_count=0, power_bridge_count=0, ground_terminal_count=0, free_capacitor_count=1, free_inductor_count=1),
    )

    for index, (mode, cl_order) in enumerate(
        [
            ("disconnected", "cap_then_ind_then_res"),
            ("connected", "cap_then_ind_then_res"),
            ("connected", "cl_outputs_first_then_res"),
        ],
        start=2,
    ):
        specs = _small_specs(v2, mode)
        records = _records(v3, v8_ind, specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates)
        chunk, order = _r_last_chunk(header=cap_templates.header, cl_order=cl_order, records=records, v3=v3, res_templates=res_templates)
        add(
            f"RCL_V8_T{index:02d}_ALL_TERM_{mode.upper()}_{cl_order.upper()}",
            f"All three families are terminal-attached with {mode} labels, C/L before final resistor using {cl_order}.",
            specs,
            chunk=chunk,
            records=records,
            object_order=order,
            cdb=v2._build_rcl_cdb(specs, v8_ind),
            expected=_expected_counts(resistor_count=1, capacitor_count=1, inductor_count=1, power_bridge_count=0, ground_terminal_count=0),
        )

    for index, cl_order in enumerate(["cap_then_ind_then_res", "cl_outputs_first_then_res"], start=5):
        specs = _small_specs(v2, "power_series")
        records = _records(v3, v8_ind, specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates)
        chunk, order = _r_last_chunk(header=cap_templates.header, bridge_core=bridge_core, cl_order=cl_order, records=records, v3=v3, res_templates=res_templates)
        add(
            f"RCL_V8_T{index:02d}_POWER_GROUND_3_SERIES_{cl_order.upper()}",
            f"Three-component R/C/L series path from V0 to G0, C/L block before final resistor using {cl_order}.",
            specs,
            chunk=chunk,
            records=records,
            object_order=f"power bridge, {order}",
            cdb=v2._build_rcl_cdb(specs, v8_ind),
            expected=_expected_counts(resistor_count=1, capacitor_count=1, inductor_count=1, power_bridge_count=1, ground_terminal_count=1),
        )

    for index, (source_path, label) in enumerate([(v2.SOURCE_6R, "6_COMPONENT"), (v2.SOURCE_21R, "21_COMPONENT")], start=7):
        source, specs, notes = v2._convert_source(source_path, require_all_three=False)
        records = _records(v3, v8_ind, specs, cap_templates=cap_templates, res_templates=res_templates, ind_templates=ind_templates)
        chunk, order = _r_last_chunk(header=cap_templates.header, bridge_core=bridge_core, cl_order="cap_then_ind_then_res", records=records, v3=v3, res_templates=res_templates)
        ground_count = sum(1 for item in records["topology"] if item["output_marker"] == "$TERGROUND")
        add(
            f"RCL_V8_T{index:02d}_{label}_RCL_CYCLE_R_LAST",
            f"{label.replace('_', '-').lower()} mixed R/C/L cycle with V0/G0; all C/L records before final resistor block. Conversion notes: {notes}",
            specs,
            chunk=chunk,
            records=records,
            object_order=f"power bridge, {order}",
            cdb=v2._build_rcl_cdb(specs, v8_ind),
            expected=_expected_counts(
                resistor_count=sum(1 for spec in specs if spec.kind == "RESISTOR"),
                capacitor_count=sum(1 for spec in specs if spec.kind == "CAPACITOR"),
                inductor_count=sum(1 for spec in specs if spec.kind == "INDUCTOR"),
                power_bridge_count=1,
                ground_terminal_count=ground_count,
            ),
        )

    summary = {
        "batch_id": "MIXED_RCL_V8_R_LAST_TERMINAL_POWER_STATIC_20260601",
        "status": "static_generated_awaiting_user_proteus_test",
        "source_feedback": "V7 T02-T07 worked: free L/C first plus terminal R final is accepted. V7 T08-T12 remain unrecorded unless user provides results.",
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "object_order": item["object_order"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "MIXED_RCL_V8_R_LAST_TERMINAL_POWER_TEMP_2026_06_01\n\n"
        "Open in order:\n"
        "1. T01 should reproduce the V7 passing control.\n"
        "2. T02-T04 test all-terminal no-power C/L-before-R-final variants.\n"
        "3. T05-T06 add the V0 power bridge and G0 endpoint to the small series case.\n"
        "4. T07-T08 are the 6-component and 21-component mixed R/C/L cycle candidates.\n\n"
        "Report the first failing case, exact error text, and whether any opened file has missing components or wrong labels.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V8_R_LAST_TERMINAL_POWER_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
