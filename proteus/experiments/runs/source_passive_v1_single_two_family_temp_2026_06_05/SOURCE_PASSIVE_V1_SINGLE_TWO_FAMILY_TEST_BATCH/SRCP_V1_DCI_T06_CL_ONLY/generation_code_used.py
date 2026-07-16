"""Generate the 15 DC-current source-driven R/C/L topologies using V12.

User feedback confirmed all V12 manual-testing study cases worked. The accepted
temporary DC-current rule is therefore:

* use DV/D0 source nets, same as the accepted DC-voltage source path
* keep source ref/value V1/10V
* use DCV source object geometry and visible VSOURCE text
* patch only the final source model marker to CSOURCE and the global component ID
* write ROOT.CDB source entry as CSOURCE, source last
* use the user manual testing device table containing CAP + CSOURCE + REALIND + RESISTOR

This pack applies that rule to the 15 locked mixed R/C/L topology examples.
"""

from __future__ import annotations

import hashlib
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

from proteusgen.mixed_rcl_examples import mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402
from proteusgen import resistor_v9 as rv9  # noqa: E402

OUT_ROOT = REPO_ROOT / "experiments" / "dc_current_v13_15_topologies_temp_2026_06_04"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_CURRENT_V13_15_TOPOLOGIES_TEMP_2026_06_04"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DCI_V13_15_TOPOLOGIES_TEST_BATCH"
V12_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_current_v12_manual_testing_study_temp.py"
V10_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_current_v10_anchor_terminals_temp.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v12 = _load_module("dc_current_v12_for_v13", V12_PATH)
v10 = _load_module("dc_current_v10_for_v13", V10_PATH)
v5 = v12.v5


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "manual_testing": v12.USER_TESTING,
        "dc_voltage_01_default_10v": v12.USER_DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj",
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _case_suffix(index: int, payload_name: str) -> str:
    parts = payload_name.split("_")
    return f"T{index:02d}_" + "_".join(parts[4:])


def _write_case(
    case_id: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = v5._build_dsn_with_devices(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    issues = v5.rcl._scan_wire_issues(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if object_chunk.count(marker):
            issues.append(f"source-net case unexpectedly contains {marker.decode('ascii')}")
    for label in (b"\x02V0", b"\x02G0"):
        if label in object_chunk:
            issues.append(f"source-net case still contains terminal label {label[1:].decode('ascii')}")
    if object_chunk.count(b"VSOURCE") != 1 or object_chunk.count(b"CSOURCE") != 1:
        issues.append("DC-current V13 object chunk should contain one visible VSOURCE and one final CSOURCE marker")
    if b"\x02DV" not in object_chunk or b"\x02D0" not in object_chunk:
        issues.append("DC-current V13 object chunk should contain DV/D0 source terminals")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_current_v13_15_topologies_not_locked",
        "output": str(output_path.relative_to(OUT_ROOT)),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": v5._marker_counts(object_chunk),
        "device_marker_counts": v5._marker_counts(devices),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            chunk_path.name: _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "devices": _sha256_bytes(devices),
        },
        "input": input_payload,
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _make_case(
    *,
    index: int,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    dcv_source_project: Path,
    devices: bytes,
) -> dict[str, Any]:
    groups = v12._map_groups_to_dv_d0(v12._payload_groups(payload))
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, groups)
    source_id = len(specs) + 1
    source = v10.SourceSpec(idx=source_id, ref="V1", value="10V")
    source_block = v12._dcv_geometry_csource_block(dcv_source_project, global_id=source_id)
    object_chunk = v12._source_first_chunk(source_block, source_net_chunk)
    case_id = f"DCI_V13_{_case_suffix(index, payload['project']['name'])}"
    description = f"DC-current source-driven {payload['metadata']['description']} using V12 accepted DCV-geometry/CSOURCE method."
    return _write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=v10._build_cdb(specs, source),
        devices=devices,
        input_payload={
            "base_payload_name": payload["project"]["name"],
            "source_kind": "dc_current",
            "source_rule": "V12 accepted: DV/D0 terminals, V1/10V source ref/value, visible VSOURCE geometry, final model CSOURCE",
            "source": {"idx": source.idx, "ref": source.ref, "value": source.value, "model": source.model},
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
            "rcl_counts": rcl_counts,
            "topology": topology,
        },
    )


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)
    donors = _copy_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v5.rcl._load_rcl_unit_templates(rcl_donor)

    manual = donors["manual_testing"]
    dcv_source = donors["dc_voltage_01_default_10v"]
    manual_devices = v5._device_section_from_dsn(read_internal_file(manual, "ROOT.DSN"))

    cases = [
        _make_case(
            index=index,
            payload=payload,
            templates=templates,
            base_project=base_project,
            donor_project=manual,
            dcv_source_project=dcv_source,
            devices=manual_devices,
        )
        for index, payload in enumerate(mixed_rcl_15_cases(), start=1)
    ]

    summary = {
        "batch_id": "DC_CURRENT_V13_15_TOPOLOGIES_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V12 user feedback: all V12 cases worked.",
        "method": "Apply V12 accepted DC-current method to the 15 locked mixed R/C/L topology examples.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item["marker_counts"],
                "device_marker_counts": item["device_marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "DC current V13 15-topology pack using the V12 accepted method.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nEach case uses DV/D0 terminals, V1/10V source ref/value, visible VSOURCE source geometry, and final CSOURCE model metadata.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
