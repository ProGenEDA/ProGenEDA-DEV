"""Generate DC-current diagnostics using DCV-style clean device metadata.

V10 feedback:

* T02, T03, and T04 failed with ISIS/VG dll errors.
* T00/T01 were not reported as failing, so the connected donor control and
  generated resistor-only load remain accepted controls for this pass.

The important V10 mistake was not source geometry. Its mixed cases combined
the full R/C/L device table with the connected current-load device table,
creating duplicate RESISTOR device definitions:

    CAP + REALIND + RESISTOR + CSOURCE + RESISTOR

The accepted DC-voltage source files use the clean shape:

    CAP + REALIND + RESISTOR + VSOURCE

V11 mirrors that for current:

    CAP + REALIND + RESISTOR + CSOURCE
"""

from __future__ import annotations

import hashlib
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

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_6_case, mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_current_v11_dcv_style_devices_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_CURRENT_V11_DCV_STYLE_DEVICES_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DCI_V11_TEST_BATCH"
USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
V5_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"
V10_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-03" / "generate_dc_current_v10_anchor_terminals_temp.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v5 = _load_module("dc_sources_v5_for_current_v11", V5_PATH)
v10 = _load_module("dc_current_v10_for_v11", V10_PATH)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "dc_current_01_default": USER_DONOR_ROOT / "dc_current_01_default.pdsprj",
        "dc_current_03_resistor_load": USER_DONOR_ROOT / "dc_current_03_resistor_load.pdsprj",
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _combine_device_sections(*sections: bytes) -> bytes:
    out = bytearray()
    for section in sections[:-1]:
        out += section[:-4]
    out += sections[-1]
    return bytes(out)


def _source_first_chunk(source_block: bytes, source_net_chunk: bytes) -> bytes:
    out = bytearray(b"\x00" + source_block + source_net_chunk[1:])
    out[-1] = 0xFF
    return bytes(out)


def _standalone_source_block(source_donor: Path, *, global_id: int) -> bytes:
    chunk = v5._object_chunk(source_donor)
    if len(chunk) != 653:
        raise RuntimeError(f"Unexpected standalone current donor object chunk length: {len(chunk)}.")
    b0, b1, b2, b3, b4, b5 = (1, 104, 208, 552, 602, 653)
    source = v10._patch_source_global_id_only(chunk[b2:b3], global_id)
    return chunk[b0:b1] + chunk[b1:b2] + source + chunk[b3:b4] + chunk[b4:b5][:-1]


def _map_groups_to_current_nets(groups: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    mapped = []
    for mode, start, end in groups:
        mapped_start = "DI" if start == "V0" else "I0" if start == "G0" else start
        mapped_end = "DI" if end == "V0" else "I0" if end == "G0" else end
        mapped.append((mode, mapped_start, mapped_end))
    return mapped


def _payload_groups(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(item["mode"], item["start"], item["end"]) for item in payload["groups"]]


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

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_current_v11_dcv_style_devices_not_locked",
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
    case_id: str,
    description: str,
    groups: list[tuple[str, str, str]],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    current_load_donor: Path,
    current_standalone_donor: Path,
    devices: bytes,
    source_shape: str,
) -> dict[str, Any]:
    mapped_groups = _map_groups_to_current_nets(groups)
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, mapped_groups)
    source_id = len(specs) + 1
    source = v10.SourceSpec(idx=source_id, ref="I4" if source_shape != "standalone" else "I1", value="500mA" if source_shape != "standalone" else "1A")
    if source_shape == "connected_anchor":
        source_block = v10._connected_source_block(current_load_donor, global_id=source_id, visible_ref="I4")
        object_chunk = v10._source_anchor_body_chunk(source_block, v10._anchor_terminal_pair(current_load_donor), source_net_chunk)
    elif source_shape == "connected_no_anchor":
        source_block = v10._connected_source_block(current_load_donor, global_id=source_id, visible_ref="I4")
        object_chunk = _source_first_chunk(source_block, source_net_chunk)
    elif source_shape == "standalone":
        source_block = _standalone_source_block(current_standalone_donor, global_id=source_id)
        object_chunk = _source_first_chunk(source_block, source_net_chunk)
    else:
        raise ValueError(source_shape)

    return _write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=v10._build_cdb(specs, source),
        devices=devices,
        input_payload={
            "source_kind": "dc_current",
            "source_shape": source_shape,
            "device_section": "dcv_style_clean_CAP_REALIND_RESISTOR_CSOURCE",
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

    current_load = donors["dc_current_03_resistor_load"]
    current_standalone = donors["dc_current_01_default"]
    current_load_devices = v5._device_section_from_dsn(read_internal_file(current_load, "ROOT.DSN"))
    rcl_devices = v5._device_section_from_dsn(read_internal_file(rcl_donor, "ROOT.DSN"))
    current_standalone_devices = v5._device_section_from_dsn(read_internal_file(current_standalone, "ROOT.DSN"))
    clean_mixed_current_devices = _combine_device_sections(rcl_devices, current_standalone_devices)

    simple_payload = mixed_rcl_15_cases()[0]
    six_payload = mixed_rcl_6_case()

    cases: list[dict[str, Any]] = []
    cases.append(
        _write_case(
            "DCI_V11_T00_CURRENT_LOAD_DONOR",
            "Control: exact connected current-source plus resistor-load donor transplanted into E001.",
            base_project=base_project,
            donor_project=current_load,
            object_chunk=v5._object_chunk(current_load),
            cdb=read_internal_file(current_load, "ROOT.CDB"),
            devices=current_load_devices,
            input_payload={"control": "connected_current_resistor_load_donor"},
        )
    )
    cases.append(
        _make_case(
            case_id="DCI_V11_T01_R_ONLY_ANCHOR",
            description="Generated resistor-only load with connected current source and current-load donor device section.",
            groups=[("R", "V0", "G0")],
            templates=templates,
            base_project=base_project,
            donor_project=current_load,
            current_load_donor=current_load,
            current_standalone_donor=current_standalone,
            devices=current_load_devices,
            source_shape="connected_anchor",
        )
    )
    cases.append(
        _make_case(
            case_id="DCI_V11_T02_RCL_SIMPLE_ANCHOR_CLEAN_DEVICES",
            description="Generated simple R/C/L load with connected source + anchor terminals and DCV-style clean R/C/L+CSOURCE device section.",
            groups=_payload_groups(simple_payload),
            templates=templates,
            base_project=base_project,
            donor_project=current_load,
            current_load_donor=current_load,
            current_standalone_donor=current_standalone,
            devices=clean_mixed_current_devices,
            source_shape="connected_anchor",
        )
    )
    cases.append(
        _make_case(
            case_id="DCI_V11_T03_6COMP_ANCHOR_CLEAN_DEVICES",
            description="Generated six-component R/C/L load with connected source + anchor terminals and clean R/C/L+CSOURCE device section.",
            groups=_payload_groups(six_payload),
            templates=templates,
            base_project=base_project,
            donor_project=current_load,
            current_load_donor=current_load,
            current_standalone_donor=current_standalone,
            devices=clean_mixed_current_devices,
            source_shape="connected_anchor",
        )
    )
    cases.append(
        _make_case(
            case_id="DCI_V11_T04_RCL_SIMPLE_NO_ANCHOR_CLEAN_DEVICES",
            description="A/B: generated simple R/C/L with connected source but no anchor terminals, using clean R/C/L+CSOURCE device section.",
            groups=_payload_groups(simple_payload),
            templates=templates,
            base_project=base_project,
            donor_project=current_load,
            current_load_donor=current_load,
            current_standalone_donor=current_standalone,
            devices=clean_mixed_current_devices,
            source_shape="connected_no_anchor",
        )
    )
    cases.append(
        _make_case(
            case_id="DCI_V11_T05_RCL_SIMPLE_STANDALONE_DCV_STYLE",
            description="A/B: DCV-style standalone current source block before generated simple R/C/L, using clean R/C/L+CSOURCE device section.",
            groups=_payload_groups(simple_payload),
            templates=templates,
            base_project=base_project,
            donor_project=current_standalone,
            current_load_donor=current_load,
            current_standalone_donor=current_standalone,
            devices=clean_mixed_current_devices,
            source_shape="standalone",
        )
    )

    summary = {
        "batch_id": "DC_CURRENT_V11_DCV_STYLE_DEVICES_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V10 feedback: T02/T03/T04 failed with ISIS dll; T00/T01 not reported as failing.",
        "method": "Keep current source geometry from V10, but use DCV-style clean CAP+REALIND+RESISTOR+CSOURCE device metadata for mixed R/C/L cases.",
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
        "DC current V11 DCV-style clean-device diagnostic pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT02 is the main fix candidate: same source layout as V10 but without duplicate RESISTOR device metadata. T04/T05 are A/B checks against anchor and standalone-source behavior.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
