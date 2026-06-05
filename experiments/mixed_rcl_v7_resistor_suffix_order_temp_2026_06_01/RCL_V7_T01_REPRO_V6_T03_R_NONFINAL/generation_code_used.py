"""Generate resistor-terminal diagnostics after V6 user feedback.

V6 results:

- T01, T02, T04, T05, T10 worked.
- Every case containing a terminal-attached resistor failed.

This pack keeps L/C evidence stable and varies only the resistor terminal
record: final ordering, record ordinal/index, suffix/link bytes, and DSN header.
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
from proteusgen.resistor_ir import resistor_orientation_angle, visible_resistor_value
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "mixed_rcl_v7_resistor_suffix_order_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V3_PATH = Path(__file__).with_name("generate_mixed_rcl_v3_isolation_temp.py")
V6_PATH = Path(__file__).with_name("generate_mixed_rcl_v6_terminal_boundary_temp.py")
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")


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


def _patch_resistor_suffixes(input_record: bytes, output_record: bytes, group: list[bytes], in_suffix: int, out_suffix: int) -> tuple[bytes, bytes, list[bytes]]:
    inp = bytearray(input_record)
    out = bytearray(output_record)
    res = bytearray(group[0])
    inp[-4:-2] = rv9._u16(in_suffix)
    out[-4:-2] = rv9._u16(out_suffix)
    res[337:339] = rv9._u16(in_suffix)
    res[341:343] = rv9._u16(out_suffix)
    return bytes(inp), bytes(out), [bytes(res), group[1], group[2]]


def _patch_resistor_index(group: list[bytes], component_index: int) -> list[bytes]:
    res = bytearray(group[0])
    res[324:328] = rv9._u32(component_index)
    return [bytes(res), group[1], group[2]]


def _custom_resistor_block(
    spec: Any,
    *,
    ordinal: int,
    component_index: int | None,
    suffixes: tuple[int, int] | None,
    final: bool,
    res_templates: Any,
) -> tuple[bytes, dict[str, Any]]:
    input_record, output_record, group, info = mp._build_resistor_records(
        spec,
        ordinal=ordinal,
        x=spec.x,
        y=spec.y,
        templates=res_templates,
        ground_nodes=set(),
    )
    if component_index is not None:
        group = _patch_resistor_index(group, component_index)
        info["component_index_override"] = component_index
    if suffixes is not None:
        input_record, output_record, group = _patch_resistor_suffixes(input_record, output_record, group, suffixes[0], suffixes[1])
        info["in_suffix"] = f"{suffixes[0]:04x}"
        info["out_suffix"] = f"{suffixes[1]:04x}"
        info["suffix_override"] = True
    block = input_record + output_record + res_templates.separator + b"".join(group)
    if not final:
        block = _zero_last(block)
    info["ordinal_used"] = ordinal
    info["block_final"] = final
    return block, info


def _build_chunk(header: bytes, parts: list[bytes]) -> bytes:
    chunk = bytearray(header + b"".join(parts))
    chunk[-1] = 0xFF
    return bytes(chunk)


def _validate(chunk: bytes, expected: dict[str, int]) -> list[str]:
    issues: list[str] = []
    counts = _marker_counts(chunk)
    for marker, want in expected.items():
        if counts[marker] != want:
            issues.append(f"{marker} count {counts[marker]} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    return issues


def _expected_counts(*, terminal_r: bool, terminal_c: bool, terminal_l: bool, free_r: bool, free_c: bool, free_l: bool) -> dict[str, int]:
    terminal_count = int(terminal_r) + int(terminal_c) + int(terminal_l)
    return {
        "$TERPOWER": 0,
        "$TERINPUT": terminal_count,
        "$TEROUTPUT": terminal_count,
        "$TERGROUND": 0,
        "WIRE": terminal_count * 2,
        "RESISTOR": (2 if terminal_r else 0) + (2 if free_r else 0),
        "CAPACITOR": (1 if terminal_c else 0) + (1 if free_c else 0),
        "CAP10": (1 if terminal_c else 0) + (1 if free_c else 0),
        "REALIND": (3 if terminal_l else 0) + (3 if free_l else 0),
        "COMPONENT ID": terminal_count + int(free_r) + int(free_c) + int(free_l),
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_header_project: Path,
    cdb: bytes,
    object_chunk: bytes,
    issues: list[str],
    res_info: dict[str, Any] | None,
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
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v7_resistor_suffix_order_not_locked",
        "description": description,
        "donor_header_project": str(donor_header_project),
        "resistor_record_info": res_info,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            chunk_path.name: rv9._sha256_file(chunk_path),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
            "object_chunk": rv9._sha256_bytes(object_chunk),
        },
    }
    payload = {
        "schema_version": "mixed-rcl-temp/v7-resistor-suffix-order",
        "generator_target": "proteus-8.13-mixed-rcl-resistor-terminal-diagnostic",
        "case_id": case_id,
        "description": description,
        "resistor_record_info": res_info,
    }
    (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_temp_for_v7", V2_PATH)
    v3 = _load_module("mixed_rcl_v3_temp_for_v7", V3_PATH)
    v6 = _load_module("mixed_rcl_v6_temp_for_v7", V6_PATH)
    v8 = _load_module("inductor_v8_temp_for_v7", V8_PATH)

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
    rlc_donor = registry.get("rlc_manual_donor").path
    rlc_cdb = read_internal_file(rlc_donor, "ROOT.CDB")
    rlc_chunk = rv9._extract_object_chunk(read_internal_file(rlc_donor, "ROOT.DSN"))
    free = v6._free_slices(rlc_chunk)

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    res_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ind_templates = v8._load_six_templates(inductor_donor)

    specs_disconnected = v6._specs(v2, connected=False)
    specs_connected = v6._specs(v2, connected=True)
    records_connected = v6._records_for(
        v3,
        v8,
        specs_connected,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
    )
    records_disconnected = v6._records_for(
        v3,
        v8,
        specs_disconnected,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
    )
    blocks_connected = v6._terminal_blocks(v3, records_connected, res_templates)
    blocks_disconnected = v6._terminal_blocks(v3, records_disconnected, res_templates)
    r_spec_disconnected = specs_disconnected[1]
    r_spec_connected = specs_connected[1]

    cases: list[dict[str, Any]] = []

    def add(
        case_id: str,
        description: str,
        parts: list[bytes],
        expected: dict[str, int],
        *,
        donor_header_project: Path = resistor_donor,
        res_info: dict[str, Any] | None = None,
    ) -> None:
        chunk = _build_chunk(free["header"], parts)
        issues = _validate(chunk, expected)
        cases.append(
            _write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_header_project=donor_header_project,
                cdb=rlc_cdb,
                object_chunk=chunk,
                issues=issues,
                res_info=res_info,
            )
        )

    expected_free_lc_term_r = _expected_counts(terminal_r=True, terminal_c=False, terminal_l=False, free_r=False, free_c=True, free_l=True)
    expected_cl_term_r = _expected_counts(terminal_r=True, terminal_c=True, terminal_l=True, free_r=False, free_c=False, free_l=False)

    r_default_nonfinal, info_default_nonfinal = _custom_resistor_block(
        r_spec_disconnected, ordinal=1, component_index=None, suffixes=None, final=False, res_templates=res_templates
    )
    add(
        "RCL_V7_T01_REPRO_V6_T03_R_NONFINAL",
        "Reproduce V6 T03: free L, terminal R non-final, free C. Expected to fail; control.",
        [free["L"], r_default_nonfinal, free["C"]],
        expected_free_lc_term_r,
        res_info=info_default_nonfinal,
    )

    suffix_policies = [
        ("DEFAULT_ORD1", 1, None, None),
        ("ORD2_INDEX2", 2, 2, None),
        ("ORD8_INDEX2", 8, 2, None),
        ("HIGH_7100_7200", 1, 2, (0x7100, 0x7200)),
        ("CAP_RANGE_011A_00E8", 1, 2, (0x011A, 0x00E8)),
        ("IND_RANGE_01B2_01E4", 1, 2, (0x01B2, 0x01E4)),
    ]

    for offset, (name, ordinal, component_index, suffixes) in enumerate(suffix_policies, start=2):
        block, info = _custom_resistor_block(
            r_spec_disconnected,
            ordinal=ordinal,
            component_index=component_index,
            suffixes=suffixes,
            final=True,
            res_templates=res_templates,
        )
        add(
            f"RCL_V7_T{offset:02d}_FREE_L_C_R_FINAL_{name}",
            f"Free L and C first, terminal R final, suffix policy {name}.",
            [free["L"], free["C"], block],
            expected_free_lc_term_r,
            res_info=info,
        )

    for offset, (name, ordinal, component_index, suffixes) in enumerate(
        [
            ("ORD8_INDEX2", 8, 2, None),
            ("HIGH_7100_7200", 1, 2, (0x7100, 0x7200)),
            ("CAP_RANGE_011A_00E8", 1, 2, (0x011A, 0x00E8)),
        ],
        start=8,
    ):
        block, info = _custom_resistor_block(
            r_spec_connected,
            ordinal=ordinal,
            component_index=component_index,
            suffixes=suffixes,
            final=True,
            res_templates=res_templates,
        )
        add(
            f"RCL_V7_T{offset:02d}_CONNECTED_CL_THEN_R_{name}",
            f"Use the known-good connected C+L terminal block, then terminal R final with suffix policy {name}.",
            [blocks_connected["C_nonfinal"], blocks_connected["L_nonfinal"], block],
            expected_cl_term_r,
            res_info=info,
        )

    block_ord8_disc, info_ord8_disc = _custom_resistor_block(
        r_spec_disconnected,
        ordinal=8,
        component_index=2,
        suffixes=None,
        final=True,
        res_templates=res_templates,
    )
    add(
        "RCL_V7_T11_ALL_TERM_DISCONNECTED_R_FINAL_ORD8_RLC_HEADER",
        "All terminal-attached disconnected labels, R final ordinal 8/index 2, inserted with manual RLC donor header.",
        [blocks_disconnected["C_nonfinal"], blocks_disconnected["L_nonfinal"], block_ord8_disc],
        expected_cl_term_r,
        donor_header_project=rlc_donor,
        res_info=info_ord8_disc,
    )

    block_ord8_conn, info_ord8_conn = _custom_resistor_block(
        r_spec_connected,
        ordinal=8,
        component_index=2,
        suffixes=None,
        final=True,
        res_templates=res_templates,
    )
    add(
        "RCL_V7_T12_ALL_TERM_CONNECTED_R_FINAL_ORD8_RLC_HEADER",
        "All terminal-attached connected labels, R final ordinal 8/index 2, inserted with manual RLC donor header.",
        [blocks_connected["C_nonfinal"], blocks_connected["L_nonfinal"], block_ord8_conn],
        expected_cl_term_r,
        donor_header_project=rlc_donor,
        res_info=info_ord8_conn,
    )

    summary = {
        "batch_id": "MIXED_RCL_V7_RESISTOR_SUFFIX_ORDER_STATIC_20260601",
        "status": "static_generated_awaiting_user_proteus_test",
        "source_feedback": "V6 worked for T01,T02,T04,T05,T10; every case with a terminal-attached resistor failed.",
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "resistor_record_info": item["resistor_record_info"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "MIXED_RCL_V7_RESISTOR_SUFFIX_ORDER_TEMP_2026_06_01\n\n"
        "Test in order:\n"
        "1. T01 is the V6 T03 reproduction control and is expected to fail.\n"
        "2. T02-T07 keep L and C as exact free donor records and put terminal R last with different ordinal/suffix policies.\n"
        "3. T08-T10 use the known-good terminal C+L block, then terminal R last with different suffix policies.\n"
        "4. T11-T12 repeat all-terminal cases with the manual RLC donor header.\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(OUT_ROOT).replace("mixed_rcl_v7_resistor_suffix_order_temp_2026_06_01", "MIXED_RCL_V7_RESISTOR_SUFFIX_ORDER_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
