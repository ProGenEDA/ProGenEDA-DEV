"""Generate pure DCV+DCV passive probes from the accepted V7 controls.

User testing confirmed every V7 fixed-file control worked. That proves:

* the user-fixed V3 T03 file is a valid oracle,
* deterministic repacking is safe,
* E001 ROOT.DSN/ROOT.CDB transplant is safe, and
* source value changes in ROOT.CDB are safe while preserving fixed ROOT.DSN.

V8 now isolates the next mutation surface: source visible value mutation and
generated passive body rebuilds that use the fixed file's compact terminal/link
suffix sequence instead of the normal mixed-RCL suffix bases.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

V5_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_source_passive_v5_fixed_v3_order_temp.py"
USER_FIXED = Path(r"C:\Users\tahab\Downloads\SRCP_V3_DCV2_T03_R_ONLY_D0_WITH_1G_REF.pdsprj")
BASE_FIXTURE_ID = "e001_empty"
RCL_DONOR_ID = "rcl_4x_t07_unit_donor"

OUT_ROOT = REPO_ROOT / "experiments" / "source_passive_v8_compact_fixed_suffix_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "SOURCE_PASSIVE_V8_COMPACT_FIXED_SUFFIX_TEMP_2026_06_05"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V8_COMPACT_FIXED_SUFFIX_TEST_BATCH"
DONOR_ROOT = OUT_ROOT / "donors"

SuffixMode = Literal["standard", "compact_fixed"]


@dataclass(frozen=True)
class RebuildCase:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    visible_values: dict[str, str]
    exact_values: dict[str, str]
    source_values: tuple[str, str]
    suffix_mode: SuffixMode


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v5 = _load_module("source_passive_v5_for_v8_compact_suffix", V5_PATH)
mr = v5.v3.v14.v9.rcl


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _patch_fixed_cdb_source_values(cdb: bytes, source_values: tuple[str, str]) -> bytes:
    marker = b"\x021V"
    if cdb.count(marker) != 2:
        raise RuntimeError(f"Expected exactly two fixed source values, found {cdb.count(marker)}.")
    patched = cdb.replace(marker, bytes([len(source_values[0])]) + source_values[0].encode("ascii"), 1)
    patched = patched.replace(marker, bytes([len(source_values[1])]) + source_values[1].encode("ascii"), 1)
    return patched


def _copy_donors(base_project: Path, rcl_donor: Path) -> None:
    if not USER_FIXED.exists():
        raise FileNotFoundError(USER_FIXED)
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(USER_FIXED, DONOR_ROOT / "user_fixed_v3_t03_d0_1g_ref.pdsprj")
    shutil.copy2(base_project, DONOR_ROOT / "e001_empty_base.pdsprj")
    shutil.copy2(rcl_donor, DONOR_ROOT / "rcl_4x_t07_unit_donor.pdsprj")
    for internal in ("ROOT.DSN", "ROOT.CDB"):
        (DONOR_ROOT / f"user_fixed_v3_t03.{internal}.bin").write_bytes(read_internal_file(USER_FIXED, internal))


def _fixed_source_start(fixed_chunk: bytes) -> int:
    marker = b"\xff\x02V1"
    pos = fixed_chunk.find(marker)
    if pos < 2:
        raise RuntimeError("Could not locate V1 source record in fixed oracle chunk.")
    return pos - 2


def _write_project_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)

    dsn, pointers = v5.v5helper._build_dsn_with_devices(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    dsn_path.write_bytes(dsn)
    cdb_path.write_bytes(cdb)
    chunk_path.write_bytes(object_chunk)
    (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    issues = mr._scan_wire_issues(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    info = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_source_passive_v8_compact_fixed_suffix_pending_user_test",
        "output": f"{case_id}\\{case_id}.pdsprj",
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": mr._marker_counts(object_chunk),
        "device_marker_counts": mr._marker_counts(devices),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "hashes": {
            f"{case_id}.pdsprj": _sha256_file(output_path),
            f"{case_id}.ROOT.DSN.bin": _sha256_file(dsn_path),
            f"{case_id}.ROOT.CDB.bin": _sha256_file(cdb_path),
            f"{case_id}.OBJECT_CHUNK.bin": _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "devices": _sha256_bytes(devices),
        },
        "input": input_payload,
    }
    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open and simulate {case_id}.pdsprj\n", encoding="utf-8")
    return info


def _write_direct_fixed_case(
    *,
    case_id: str,
    description: str,
    source_values: tuple[str, str],
    mutate_dsn_source_values: bool,
) -> dict[str, Any]:
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / f"{case_id}.pdsprj"
    fixed_dsn = read_internal_file(USER_FIXED, "ROOT.DSN")
    fixed_cdb = read_internal_file(USER_FIXED, "ROOT.CDB")
    cdb = _patch_fixed_cdb_source_values(fixed_cdb, source_values)

    if mutate_dsn_source_values:
        fixed_chunk = rv9._extract_object_chunk(fixed_dsn)
        prefix = fixed_chunk[: _fixed_source_start(fixed_chunk)]
        fixed_templates = v5._fixed_source_templates(fixed_chunk)
        sources = (
            v5.SourcePlan("V1", source_values[0], "DV", "D0"),
            v5.SourcePlan("V2", source_values[1], "D1", "D0"),
        )
        source_units, metadata = v5._source_units(fixed_templates, sources, first_source_id=4)
        object_chunk = bytearray(prefix + source_units)
        object_chunk[-1] = 0xFF
        devices = v5.v5helper._device_section_from_dsn(fixed_dsn)
        registry = FixtureRegistry.load()
        base_project = registry.get(BASE_FIXTURE_ID).path
        return _write_project_case(
            case_id=case_id,
            description=description,
            base_project=base_project,
            donor_project=USER_FIXED,
            object_chunk=bytes(object_chunk),
            cdb=cdb,
            devices=devices,
            input_payload={
                "method": "direct_fixed_oracle_source_visible_value_mutation",
                "source_values": list(source_values),
                "sources": metadata,
                "ROOT_DSN_passive_prefix": "byte-for-byte user-fixed passive prefix",
            },
        )

    write_project_from_parts(USER_FIXED, output_path, {"ROOT.CDB": cdb})
    root_dsn = read_internal_file(output_path, "ROOT.DSN")
    root_cdb = read_internal_file(output_path, "ROOT.CDB")
    object_chunk = rv9._extract_object_chunk(root_dsn)
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path.write_bytes(root_dsn)
    cdb_path.write_bytes(root_cdb)
    info = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_source_passive_v8_direct_fixed_cdb_only_control_pending_user_test",
        "output": f"{case_id}\\{case_id}.pdsprj",
        "method": "direct_fixed_oracle_cdb_only",
        "source_values": list(source_values),
        "object_chunk_len": len(object_chunk),
        "root_dsn_len": len(root_dsn),
        "root_cdb_len": len(root_cdb),
        "fixed_root_dsn_preserved": root_dsn == fixed_dsn,
        "marker_counts": mr._marker_counts(object_chunk),
        "static_validation_issues": mr._scan_wire_issues(object_chunk),
        "hashes": {
            f"{case_id}.pdsprj": _sha256_file(output_path),
            f"{case_id}.ROOT.DSN.bin": _sha256_file(dsn_path),
            f"{case_id}.ROOT.CDB.bin": _sha256_file(cdb_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(root_cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open and simulate {case_id}.pdsprj\n", encoding="utf-8")
    return info


def _compact_fixed_suffixes(unit_index: int) -> dict[str, int]:
    """Compact suffix sequence observed in the accepted user-fixed oracle.

    R-only suffixes in the fixed file are:
    unit1 R 0x0bc4/0x0bf6, unit2 R 0x0e51/0x0e83,
    unit3 R 0x10de/0x1110. The C/L values preserve the normal within-unit
    family offsets relative to R while compacting the unit stride.
    """

    r_in = (0x0BC4 + (unit_index - 1) * 0x028D) & 0xFFFF
    return {
        "cap_out": (r_in - 0x0536) & 0xFFFF,
        "cap_in": (r_in - 0x0504) & 0xFFFF,
        "l_in": (r_in - 0x02BB) & 0xFFFF,
        "l_out": (r_in - 0x0289) & 0xFFFF,
        "r_in": r_in,
        "r_out": (r_in + 0x0032) & 0xFFFF,
    }


def _patch_native_resistor_any_value(template: bytes, spec: Any, global_id: int, in_suffix: int, out_suffix: int) -> bytes:
    raw_ref = spec.ref.encode("ascii")
    raw_value = spec.visible_value.encode("ascii")
    if len(raw_ref) != 2 or not raw_ref.isascii():
        raise ValueError(f"Unsupported resistor ref {spec.ref!r}.")
    if len(raw_value) not in (2, 3, 4) or not raw_value.isascii():
        raise ValueError(f"Unsupported resistor visible value {spec.visible_value!r}.")

    record = bytearray(template)
    old_len = record[69]
    old_value_off = 70 + old_len
    record[1] = len(raw_ref)
    record[2 : 2 + len(raw_ref)] = raw_ref
    record[69] = len(raw_value)
    record[70:old_value_off] = raw_value

    value_off = 70 + len(raw_value)
    ref_x, ref_y, value_x, value_y, hidden_x, hidden_y = rv9._label_positions(spec.x, spec.y, 0)
    record[4:8] = mr._i32(ref_x)
    record[8:12] = mr._i32(ref_y)
    record[value_off : value_off + 4] = mr._i32(value_x)
    record[value_off + 4 : value_off + 8] = mr._i32(value_y)
    record[value_off + 77 : value_off + 81] = mr._i32(hidden_x)
    record[value_off + 81 : value_off + 85] = mr._i32(hidden_y)
    record[value_off + 163 : value_off + 167] = mr._i32(hidden_x)
    record[value_off + 167 : value_off + 171] = mr._i32(hidden_y)
    record[value_off + 240 : value_off + 244] = mr._i32(spec.x)
    record[value_off + 244 : value_off + 248] = mr._i32(spec.y)
    record[value_off + 248 : value_off + 252] = mr._angle_tenths(0)
    record[value_off + 252 : value_off + 256] = rv9._u32(global_id)
    record[value_off + 265 : value_off + 267] = mr._u16(in_suffix)
    record[value_off + 267 : value_off + 269] = b"\x01\x00"
    record[value_off + 269 : value_off + 271] = mr._u16(out_suffix)
    record[value_off + 271 : value_off + 273] = b"\x01\x00"
    record[-1] = 0x00
    return bytes(record)


def _build_rebuilt_case(case: RebuildCase, *, templates: Any, base_project: Path, devices: bytes) -> dict[str, Any]:
    old_resistor_patch = mr._patch_native_resistor
    old_suffixes = mr._suffixes
    mr._patch_native_resistor = _patch_native_resistor_any_value
    if case.suffix_mode == "compact_fixed":
        mr._suffixes = _compact_fixed_suffixes
    try:
        source_net_chunk, specs, topology, counts = v5.v3._source_net_rcl_ground_allowed(
            templates,
            case.groups,
            case.visible_values,
        )
    finally:
        mr._patch_native_resistor = old_resistor_patch
        mr._suffixes = old_suffixes

    fixed_chunk = rv9._extract_object_chunk(read_internal_file(USER_FIXED, "ROOT.DSN"))
    fixed_templates = v5._fixed_source_templates(fixed_chunk)
    sources = (
        v5.SourcePlan("V1", case.source_values[0], "DV", "D0"),
        v5.SourcePlan("V2", case.source_values[1], "D1", "D0"),
    )
    source_units, source_metadata = v5._source_units(fixed_templates, sources, first_source_id=len(specs) + 1)
    object_chunk = bytearray(source_net_chunk[:-1] + source_units)
    object_chunk[-1] = 0xFF
    object_chunk, wire_repair = v5.v3.v13._repair_generated_negative_wire_high_bytes(bytes(object_chunk))
    cdb_specs = [v5.v3.v14.replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    cdb = v5._build_cdb_fixed_source_rows(cdb_specs, sources, first_source_id=len(specs) + 1)

    return _write_project_case(
        case_id=case.case_id,
        description=case.description,
        base_project=base_project,
        donor_project=USER_FIXED,
        object_chunk=object_chunk,
        cdb=cdb,
        devices=devices,
        input_payload={
            "schema_version": v5.v3.SCHEMA_VERSION,
            "generator_target": v5.v3.GENERATOR_TARGET,
            "project": {
                "name": case.case_id,
                "output_basename": case.case_id,
                "base": BASE_FIXTURE_ID,
                "units": "proteus_internal",
            },
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
            "source_count": 2,
            "source_rule": "user-fixed component-first VSOURCE units appended after generated passive source-net body",
            "sources": source_metadata,
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "suffix_mode": case.suffix_mode,
            "topology": topology,
            "counts": counts,
            "wire_repair": wire_repair,
        },
    )


def _rebuild_cases() -> list[RebuildCase]:
    r_only_groups = (("R", "DV", "D0"), ("R", "D1", "D0"), ("R", "D0", "G0"))
    rc_rl_groups = (("RC", "DV", "D0"), ("RL", "D1", "D0"), ("R", "D0", "G0"))
    return [
        RebuildCase(
            "SRCP_V8_T02_R_ONLY_STANDARD_SUFFIX_EXACT_VALUES",
            "Generated R-only body using exact two-character resistor visible values but the normal mixed-RCL suffix bases.",
            r_only_groups,
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            ("1V", "1V"),
            "standard",
        ),
        RebuildCase(
            "SRCP_V8_T03_R_ONLY_COMPACT_SUFFIX_EXACT_VALUES",
            "Generated R-only body using exact resistor visible values and the compact suffix sequence from the fixed oracle.",
            r_only_groups,
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            ("1V", "1V"),
            "compact_fixed",
        ),
        RebuildCase(
            "SRCP_V8_T04_RC_RL_STANDARD_SUFFIX_EXACT_VALUES",
            "Generated RC/RL body using exact resistor visible values but the normal mixed-RCL suffix bases.",
            rc_rl_groups,
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            ("1V", "1V"),
            "standard",
        ),
        RebuildCase(
            "SRCP_V8_T05_RC_RL_COMPACT_SUFFIX_EXACT_VALUES",
            "Generated RC/RL body using exact resistor visible values and compact fixed-oracle suffix sequence.",
            rc_rl_groups,
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            ("1V", "1V"),
            "compact_fixed",
        ),
        RebuildCase(
            "SRCP_V8_T06_RC_RL_COMPACT_SUFFIX_10V_5V",
            "Generated RC/RL body using compact fixed-oracle suffixes and visible/CDB source values 10V and 5V.",
            rc_rl_groups,
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            ("10V", "5V"),
            "compact_fixed",
        ),
    ]


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    archive = ARCHIVE_BASE.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    TEST_BATCH.mkdir(parents=True, exist_ok=True)

    registry = FixtureRegistry.load()
    base_project = registry.get(BASE_FIXTURE_ID).path
    rcl_donor = registry.get(RCL_DONOR_ID).path
    _copy_donors(base_project, rcl_donor)
    templates = mr._load_rcl_unit_templates(rcl_donor)
    devices = v5.v5helper._device_section_from_dsn(read_internal_file(USER_FIXED, "ROOT.DSN"))

    manifests = [
        _write_direct_fixed_case(
            case_id="SRCP_V8_T00_FIXED_CDB_ONLY_10V_5V_ACCEPTED_CONTROL",
            description="Accepted V7-style fixed oracle with ROOT.DSN unchanged and only ROOT.CDB source values changed to 10V/5V.",
            source_values=("10V", "5V"),
            mutate_dsn_source_values=False,
        ),
        _write_direct_fixed_case(
            case_id="SRCP_V8_T01_FIXED_DSN_AND_CDB_SOURCE_VALUES_10V_5V",
            description="Fixed oracle passive prefix with source units patched visibly to 10V/5V and matching ROOT.CDB source values.",
            source_values=("10V", "5V"),
            mutate_dsn_source_values=True,
        ),
    ]
    for case in _rebuild_cases():
        manifests.append(_build_rebuilt_case(case, templates=templates, base_project=base_project, devices=devices))

    order = [item["case_id"] for item in manifests]
    summary = {
        "batch_id": "SOURCE_PASSIVE_V8_COMPACT_FIXED_SUFFIX_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_simulation_test",
        "source_feedback": "User reported all V7 fixed-file controls worked.",
        "method": "Keep the fixed source-unit oracle and test direct source-value mutation plus generated passive rebuilds using exact visible values and compact suffixes.",
        "test_order": order,
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in manifests
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V8 compact fixed-suffix probe pack.\n\n"
        "Test in order. T00 is the already accepted V7 CDB-only control. T01 isolates visible source-value mutation. T02/T03 compare standard versus compact suffixes for R-only. T04/T05/T06 are the RC/RL scale-up candidates.\n\n"
        + "\n".join(f"{idx}. {case_id}/{case_id}.pdsprj" for idx, case_id in enumerate(order, start=1))
        + "\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(__file__, OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({**summary, "archive": str(archive), "archive_sha256": _sha256_file(archive)}, indent=2))


if __name__ == "__main__":
    main()
