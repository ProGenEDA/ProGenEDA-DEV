"""Generate DC-current diagnostics from the new manual testing.pdsprj.

The user supplied ``C:\\Users\\tahab\\Downloads\\testing.pdsprj`` after V11
failed. Byte-level inspection shows a different current-source pattern:

* source nets are still DV/D0, not DI/I0
* source reference/value are V1/10V
* the visible source subckt text remains VSOURCE
* the final model marker, ROOT.CDB model, and device table use CSOURCE
* the device table order is CAP, CSOURCE, REALIND, RESISTOR

V12 therefore treats DCI as "DCV geometry with CSOURCE metadata" and stops using
the standalone/connected current-source geometry from earlier V9-V11 attempts.
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

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_6_case, mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "experiments" / "dc_current_v12_manual_testing_study_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_CURRENT_V12_MANUAL_TESTING_STUDY_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DCI_V12_TEST_BATCH"
USER_TESTING = Path(r"C:\Users\tahab\Downloads\testing.pdsprj")
USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
V5_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"
V10_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_current_v10_anchor_terminals_temp.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v5 = _load_module("dc_sources_v5_for_current_v12", V5_PATH)
v10 = _load_module("dc_current_v10_for_v12", V10_PATH)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "manual_testing": USER_TESTING,
        "dc_voltage_01_default_10v": USER_DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj",
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _map_groups_to_dv_d0(groups: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    mapped = []
    for mode, start, end in groups:
        mapped_start = "DV" if start == "V0" else "D0" if start == "G0" else start
        mapped_end = "DV" if end == "V0" else "D0" if end == "G0" else end
        mapped.append((mode, mapped_start, mapped_end))
    return mapped


def _payload_groups(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(item["mode"], item["start"], item["end"]) for item in payload["groups"]]


def _patch_source_global_id_and_model(source_record: bytes, global_id: int) -> bytes:
    out = bytearray(source_record)
    model_pos = out.rfind(b"VSOURCE")
    if model_pos < 0:
        raise RuntimeError("Expected final VSOURCE marker in DCV source record.")
    out[model_pos : model_pos + len(b"VSOURCE")] = b"CSOURCE"
    body_coord = model_pos + len(b"CSOURCE")
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    return bytes(out)


def _dcv_geometry_csource_block(source_donor: Path, *, global_id: int) -> bytes:
    """Use the accepted DCV source geometry, but change the final model to CSOURCE."""
    chunk = v5._object_chunk(source_donor)
    if len(chunk) != 652:
        raise RuntimeError(f"Unexpected DCV donor source chunk length: {len(chunk)}")
    body = chunk[1:]
    output = body[:104]
    input_term = body[104:207]
    source = _patch_source_global_id_and_model(body[207:551], global_id)
    wire1 = body[551:601]
    wire2_nonfinal = body[601:651][:-1]
    return output + input_term + source + wire1 + wire2_nonfinal


def _manual_source_unit(manual_project: Path) -> bytes:
    """Extract the source unit from the new manual testing donor.

    Bounds are marker-derived from the supplied file:
    chunk[2187:2942] includes DV input, DV output, D0 input, the V1/10V source
    record whose model marker is CSOURCE, and D0 output.
    """
    chunk = v5._object_chunk(manual_project)
    unit = chunk[2187:2942]
    if unit.count(b"$TERINPUT") != 2 or unit.count(b"$TEROUTPUT") != 2:
        raise RuntimeError("Manual DCI source unit terminal count changed.")
    if unit.count(b"VSOURCE") != 1 or unit.count(b"CSOURCE") != 1:
        raise RuntimeError("Manual DCI source unit does not contain VSOURCE visual and CSOURCE model markers.")
    if b"\x02DV" not in unit or b"\x02D0" not in unit:
        raise RuntimeError("Manual DCI source unit is missing DV/D0 terminal labels.")
    return unit


def _source_first_chunk(source_block: bytes, source_net_chunk: bytes) -> bytes:
    out = bytearray(b"\x00" + source_block + source_net_chunk[1:])
    out[-1] = 0xFF
    return bytes(out)


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
    direct_project_copy: Path | None = None,
) -> dict[str, Any]:
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    if direct_project_copy is not None:
        output_path = case_dir / f"{case_id}.pdsprj"
        shutil.copy2(direct_project_copy, output_path)
        dsn = read_internal_file(output_path, "ROOT.DSN")
        cdb = read_internal_file(output_path, "ROOT.CDB")
        object_chunk = rv9._extract_object_chunk(dsn)
        pointers: dict[str, int] = {}
    else:
        dsn, pointers = v5._build_dsn_with_devices(
            read_internal_file(base_project, "ROOT.DSN"),
            read_internal_file(donor_project, "ROOT.DSN"),
            object_chunk,
            devices,
        )
        dsn = patch_root_dsn_version(dsn, PROTEUS_813)
        project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
        output_path = case_dir / f"{case_id}.pdsprj"
        write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})

    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    issues = v5.rcl._scan_wire_issues(object_chunk)
    if direct_project_copy is None and rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if object_chunk.count(marker):
            issues.append(f"source-net case unexpectedly contains {marker.decode('ascii')}")
    for label in (b"\x02V0", b"\x02G0"):
        if label in object_chunk:
            issues.append(f"source-net case still contains terminal label {label[1:].decode('ascii')}")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_current_v12_manual_testing_study_not_locked",
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


def _make_generated_case(
    *,
    case_id: str,
    description: str,
    groups: list[tuple[str, str, str]],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    manual_project: Path,
    dcv_source_project: Path,
    devices: bytes,
    source_shape: str,
) -> dict[str, Any]:
    mapped_groups = _map_groups_to_dv_d0(groups)
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, mapped_groups)
    source_id = len(specs) + 1
    source = v10.SourceSpec(idx=source_id, ref="V1", value="10V")
    if source_shape == "dcv_geometry_csource":
        source_block = _dcv_geometry_csource_block(dcv_source_project, global_id=source_id)
    elif source_shape == "manual_source_unit":
        if source_id != 7:
            raise RuntimeError("Manual source unit currently preserves source global ID 7; use six-component cases.")
        source_block = _manual_source_unit(manual_project)
    else:
        raise ValueError(source_shape)
    return _write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=_source_first_chunk(source_block, source_net_chunk),
        cdb=v10._build_cdb(specs, source),
        devices=devices,
        input_payload={
            "source_kind": "dc_current",
            "source_shape": source_shape,
            "source_rule": "DV/D0 terminals, V1/10V source ref/value, visible VSOURCE geometry, CSOURCE model metadata",
            "source": {"idx": source.idx, "ref": source.ref, "value": source.value, "model": source.model},
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in mapped_groups],
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
    manual_chunk = v5._object_chunk(manual)
    manual_cdb = read_internal_file(manual, "ROOT.CDB")
    manual_devices = v5._device_section_from_dsn(read_internal_file(manual, "ROOT.DSN"))

    simple_payload = mixed_rcl_15_cases()[0]
    six_payload = mixed_rcl_6_case()

    cases: list[dict[str, Any]] = []
    cases.append(
        _write_case(
            "DCI_V12_T00_ORIGINAL_MANUAL_TESTING_COPY",
            "Control: exact user-supplied testing.pdsprj copied without repacking.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=manual_chunk,
            cdb=manual_cdb,
            devices=manual_devices,
            input_payload={"control": "direct_copy_of_user_testing_pdsprj"},
            direct_project_copy=manual,
        )
    )
    cases.append(
        _write_case(
            "DCI_V12_T01_MANUAL_TESTING_TRANSPLANT_E001",
            "Control: user-supplied manual object chunk, CDB, and device table transplanted into E001.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=manual_chunk,
            cdb=manual_cdb,
            devices=manual_devices,
            input_payload={"control": "manual_testing_object_cdb_devices_transplanted_to_e001"},
        )
    )
    cases.append(
        _make_generated_case(
            case_id="DCI_V12_T02_DCV_GEOMETRY_CSOURCE_SIMPLE",
            description="Generated simple R/C/L using accepted DCV source geometry, final model marker patched to CSOURCE, DV/D0 nets, and manual testing device table.",
            groups=_payload_groups(simple_payload),
            templates=templates,
            base_project=base_project,
            donor_project=manual,
            manual_project=manual,
            dcv_source_project=dcv_source,
            devices=manual_devices,
            source_shape="dcv_geometry_csource",
        )
    )
    cases.append(
        _make_generated_case(
            case_id="DCI_V12_T03_DCV_GEOMETRY_CSOURCE_6COMP",
            description="Generated six-component R/C/L using accepted DCV source geometry, final model marker patched to CSOURCE, DV/D0 nets, and manual testing device table.",
            groups=_payload_groups(six_payload),
            templates=templates,
            base_project=base_project,
            donor_project=manual,
            manual_project=manual,
            dcv_source_project=dcv_source,
            devices=manual_devices,
            source_shape="dcv_geometry_csource",
        )
    )
    cases.append(
        _make_generated_case(
            case_id="DCI_V12_T04_MANUAL_SOURCE_UNIT_6COMP",
            description="Generated six-component R/C/L using the source unit extracted from manual testing.pdsprj and the manual testing device table.",
            groups=_payload_groups(six_payload),
            templates=templates,
            base_project=base_project,
            donor_project=manual,
            manual_project=manual,
            dcv_source_project=dcv_source,
            devices=manual_devices,
            source_shape="manual_source_unit",
        )
    )

    summary = {
        "batch_id": "DC_CURRENT_V12_MANUAL_TESTING_STUDY_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V11 feedback: all V11 cases gave ISIS dll errors; user supplied a new testing.pdsprj for study.",
        "manual_findings": "testing.pdsprj uses DV/D0, V1/10V, visible VSOURCE geometry, CSOURCE model/CDB/device metadata, and device order CAP+CSOURCE+REALIND+RESISTOR.",
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
        "DC current V12 manual-testing study pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT00 is the exact supplied manual file. T01 tests whether that file can be transplanted into E001. T02/T03 test the likely rule: DCV source geometry with CSOURCE metadata. T04 tests the exact source unit extracted from the manual file.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
