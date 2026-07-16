"""Generate V9 pure DCV+DCV probes with fixed resistor wires/source boundary.

V8 feedback: T02 and onward gave VGDVC.dll. A byte-level comparison showed two
actual generator bugs, not just suffix mismatch:

* generated resistor left/right WIRE records used wrong endpoints;
* the source-unit helper wrote a terminator byte into a non-final source wire,
  corrupting a coordinate byte.

This batch fixes only those byte surfaces. The first rebuilt case is required
to be byte-identical to the user-fixed oracle ROOT.DSN object chunk.
"""

from __future__ import annotations

import hashlib
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

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

V8_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-05" / "generate_source_passive_v8_compact_fixed_suffix_temp.py"
USER_FIXED = Path(r"C:\Users\tahab\Downloads\SRCP_V3_DCV2_T03_R_ONLY_D0_WITH_1G_REF.pdsprj")
BASE_FIXTURE_ID = "e001_empty"
RCL_DONOR_ID = "rcl_4x_t07_unit_donor"

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "source_passive_v9_fixed_wire_source_boundary_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "SOURCE_PASSIVE_V9_FIXED_WIRE_SOURCE_BOUNDARY_TEMP_2026_06_05"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V9_FIXED_WIRE_SOURCE_BOUNDARY_TEST_BATCH"
DONOR_ROOT = OUT_ROOT / "donors"


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    visible_values: dict[str, str]
    exact_values: dict[str, str]
    source_values: tuple[str, str]
    require_fixed_chunk_match: bool = False


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v8 = _load_module("source_passive_v8_for_v9_fixed_wire", V8_PATH)
v5 = v8.v5
mr = v8.mr


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors(base_project: Path, rcl_donor: Path) -> None:
    if not USER_FIXED.exists():
        raise FileNotFoundError(USER_FIXED)
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(USER_FIXED, DONOR_ROOT / "user_fixed_v3_t03_d0_1g_ref.pdsprj")
    shutil.copy2(base_project, DONOR_ROOT / "e001_empty_base.pdsprj")
    shutil.copy2(rcl_donor, DONOR_ROOT / "rcl_4x_t07_unit_donor.pdsprj")
    for internal in ("ROOT.DSN", "ROOT.CDB"):
        (DONOR_ROOT / f"user_fixed_v3_t03.{internal}.bin").write_bytes(read_internal_file(USER_FIXED, internal))


def _patch_r_body_fixed_wire(slot: Any, spec: Any, templates: Any, suffixes: dict[str, int], *, final: bool) -> bytes:
    marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    r_output = mr._patch_ind_output(slot.r_output, spec.right, spec.idx, spec.x, spec.y, marker, suffixes["r_out"])
    r_resistor = v8._patch_native_resistor_any_value(slot.r_resistor, spec, spec.idx, suffixes["r_in"], suffixes["r_out"])
    final_wire_template = templates.units[-1].r_wire_right if final else slot.r_wire_right
    if not final and len(final_wire_template) == mr.WIRE_SIZE + 1:
        final_wire_template = final_wire_template[:-1]
    if final and len(final_wire_template) == mr.WIRE_SIZE:
        final_wire_template += b"\x00"

    left_wire = mr._wire_with_optional_final(
        slot.r_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x,
        spec.y,
        final=False,
    )
    if spec.right == "G0":
        right_wire = mr._wire_with_optional_final(
            final_wire_template,
            spec.x + 1270000,
            spec.y + 254000,
            spec.x + 1270000,
            spec.y,
            final=final,
        )
    else:
        right_wire = mr._wire_with_optional_final(
            final_wire_template,
            spec.x + 1016000,
            spec.y,
            spec.x + 1270000,
            spec.y,
            final=final,
        )
    return r_output + slot.r_resistor_prefix + r_resistor + left_wire + right_wire


def _source_units_preserve_nonfinal_wire(
    fixed_templates: tuple[Any, Any],
    sources: tuple[Any, Any],
    first_source_id: int,
) -> tuple[bytes, list[dict[str, Any]]]:
    units: list[bytes] = []
    metadata: list[dict[str, Any]] = []
    for index, (template, source) in enumerate(zip(fixed_templates, sources, strict=True), start=1):
        global_id = first_source_id + index - 1
        source_record = v5._patch_source_record(template, source, global_id)
        out_terminal = v5._patch_terminal(template.out_terminal, "OUT", source.positive, template.out_suffix)
        in_terminal = v5._patch_terminal(template.in_terminal, "IN", source.negative, template.in_suffix)
        in_wire = bytearray(template.in_wire)
        if index == len(sources):
            in_wire[-1] = 0xFF
        units.append(source_record + out_terminal + template.out_wire + in_terminal + bytes(in_wire))
        metadata.append(
            {
                "kind": source.kind,
                "ref": source.ref,
                "model": source.model,
                "positive": source.positive,
                "negative": source.negative,
                "global_id": global_id,
                "out_suffix": f"{template.out_suffix:04x}",
                "in_suffix": f"{template.in_suffix:04x}",
                "value": source.value,
                "fixed_order": "VSOURCE, $TEROUTPUT, WIRE, $TERINPUT, WIRE",
                "nonfinal_source_wire_rule": "preserve trimmed non-final in-wire bytes exactly; do not overwrite last coordinate byte",
            }
        )
    return b"".join(units), metadata


def _build_body_with_fixed_r_wires(
    *,
    templates: Any,
    groups: tuple[tuple[str, str, str], ...],
    visible_values: dict[str, str],
) -> tuple[bytes, list[Any], list[dict[str, Any]], dict[str, Any]]:
    old_r_body = mr._patch_r_body
    old_resistor_patch = mr._patch_native_resistor
    old_suffixes = mr._suffixes
    mr._patch_r_body = _patch_r_body_fixed_wire
    mr._patch_native_resistor = v8._patch_native_resistor_any_value
    mr._suffixes = v8._compact_fixed_suffixes
    try:
        return v5.v3._source_net_rcl_ground_allowed(templates, groups, visible_values)
    finally:
        mr._patch_r_body = old_r_body
        mr._patch_native_resistor = old_resistor_patch
        mr._suffixes = old_suffixes


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
    fixed_chunk: bytes,
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
        "status": "temporary_source_passive_v9_fixed_wire_source_boundary_pending_user_test",
        "output": f"{case_id}\\{case_id}.pdsprj",
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": mr._marker_counts(object_chunk),
        "device_marker_counts": mr._marker_counts(devices),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "fixed_oracle_object_chunk_match": object_chunk == fixed_chunk,
        "hashes": {
            f"{case_id}.pdsprj": _sha256_file(output_path),
            f"{case_id}.ROOT.DSN.bin": _sha256_file(dsn_path),
            f"{case_id}.ROOT.CDB.bin": _sha256_file(cdb_path),
            f"{case_id}.OBJECT_CHUNK.bin": _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "fixed_oracle_object_chunk": _sha256_bytes(fixed_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "devices": _sha256_bytes(devices),
        },
        "input": input_payload,
    }
    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open and simulate {case_id}.pdsprj\n", encoding="utf-8")
    return info


def _build_case(case: Case, *, templates: Any, base_project: Path, devices: bytes, fixed_chunk: bytes) -> dict[str, Any]:
    source_net_chunk, specs, topology, counts = _build_body_with_fixed_r_wires(
        templates=templates,
        groups=case.groups,
        visible_values=case.visible_values,
    )
    fixed_templates = v5._fixed_source_templates(fixed_chunk)
    sources = (
        v5.SourcePlan("V1", case.source_values[0], "DV", "D0"),
        v5.SourcePlan("V2", case.source_values[1], "D1", "D0"),
    )
    source_units, source_metadata = _source_units_preserve_nonfinal_wire(fixed_templates, sources, len(specs) + 1)
    object_chunk = bytearray(source_net_chunk[:-2] + source_units)
    object_chunk[-1] = 0xFF

    if case.require_fixed_chunk_match and bytes(object_chunk) != fixed_chunk:
        raise RuntimeError(f"{case.case_id} did not rebuild the fixed oracle object chunk exactly.")

    cdb_specs = [v5.v3.v14.replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    cdb = v5._build_cdb_fixed_source_rows(cdb_specs, sources, first_source_id=len(specs) + 1)

    return _write_project_case(
        case_id=case.case_id,
        description=case.description,
        base_project=base_project,
        donor_project=USER_FIXED,
        object_chunk=bytes(object_chunk),
        cdb=cdb,
        devices=devices,
        fixed_chunk=fixed_chunk,
        input_payload={
            "schema_version": v5.v3.SCHEMA_VERSION,
            "generator_target": v5.v3.GENERATOR_TARGET,
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
            "source_count": 2,
            "source_rule": "user-fixed component-first VSOURCE units; preserve nonfinal source wire bytes",
            "passive_rule": "fixed resistor wire spans plus compact fixed-oracle suffixes; trim passive final byte before source units",
            "sources": source_metadata,
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "topology": topology,
            "counts": counts,
            "required_fixed_chunk_match": case.require_fixed_chunk_match,
        },
    )


def _cases() -> list[Case]:
    r_only = (("R", "DV", "D0"), ("R", "D1", "D0"), ("R", "D0", "G0"))
    rc_rl = (("RC", "DV", "D0"), ("RL", "D1", "D0"), ("R", "D0", "G0"))
    return [
        Case(
            "SRCP_V9_T00_R_ONLY_REBUILT_BYTE_EXACT_FIXED_ORACLE",
            "R-only pure DCV2 rebuilt through the generator; must be byte-identical to the accepted fixed oracle object chunk.",
            r_only,
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            ("1V", "1V"),
            True,
        ),
        Case(
            "SRCP_V9_T01_R_ONLY_FIXED_WIRES_10V_5V",
            "R-only pure DCV2 rebuilt with fixed resistor wires/source-boundary rules and source values 10V/5V.",
            r_only,
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            ("10V", "5V"),
        ),
        Case(
            "SRCP_V9_T02_RC_RL_FIXED_R_WIRES_1V",
            "RC/RL pure DCV2 scale-up using fixed resistor wires and preserved source-boundary rules.",
            rc_rl,
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            ("1V", "1V"),
        ),
        Case(
            "SRCP_V9_T03_RC_RL_FIXED_R_WIRES_10V_5V",
            "RC/RL pure DCV2 scale-up using fixed resistor wires/source-boundary rules and source values 10V/5V.",
            rc_rl,
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            ("10V", "5V"),
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
    fixed_dsn = read_internal_file(USER_FIXED, "ROOT.DSN")
    fixed_chunk = rv9._extract_object_chunk(fixed_dsn)
    devices = v5.v5helper._device_section_from_dsn(fixed_dsn)

    manifests = [_build_case(case, templates=templates, base_project=base_project, devices=devices, fixed_chunk=fixed_chunk) for case in _cases()]
    order = [item["case_id"] for item in manifests]
    summary = {
        "batch_id": "SOURCE_PASSIVE_V9_FIXED_WIRE_SOURCE_BOUNDARY_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_simulation_test",
        "source_feedback": "V8 T02 and onward gave VGDVC.dll.",
        "method": "Fix resistor wire endpoints, preserve non-final source wire bytes, and trim the passive-source boundary. T00 must be byte-identical to the fixed oracle object chunk.",
        "test_order": order,
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "fixed_oracle_object_chunk_match": item["fixed_oracle_object_chunk_match"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in manifests
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V9 fixed-wire/source-boundary probe pack.\n\n"
        "T00 is a generator rebuild that must be byte-identical to the accepted fixed oracle object chunk. Test in order.\n\n"
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
