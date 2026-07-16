"""Generate short-name mixed DC source diagnostics using the all-source donor.

The user supplied ``45454New Project.pdsprj`` containing VSOURCE, CSOURCE, and
VSINE in one manual project. MX6 uses that donor as the source-family metadata
authority instead of synthetic source device sections.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

V1_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-04" / "generate_dc_mixed_sources_v1_requested5_temp.py"
OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mx6"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "MX6"
DONOR_ROOT = OUT_ROOT / "d"

ALL3_DONOR = Path(r"C:\Users\tahab\Downloads\45454New Project.pdsprj")
ARCHIVED_4X_DCV = (
    REPO_ROOT
    / "experiments"
    / "dc_mixed_sources_v1_requested5_temp_2026_06_04"
    / "donors"
    / "4x_dc_voltage_10v.pdsprj"
)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_module("dc_mixed_sources_v1_for_mx6", V1_PATH)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {"all3": ALL3_DONOR, "v4": ARCHIVED_4X_DCV}
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


def _write_direct(
    name: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    dsn, pointers = v1.v5._build_dsn_with_devices(
        v1.read_internal_file(base_project, "ROOT.DSN"),
        v1.read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
        devices,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base_project, "PROJECT.XML"), v1.PROTEUS_813)

    output_path = OUT_ROOT / f"{name}.pdsprj"
    cdb_path = OUT_ROOT / f"{name}.cdb.bin"
    dsn_path = OUT_ROOT / f"{name}.dsn.bin"
    chunk_path = OUT_ROOT / f"{name}.chunk.bin"
    v1.write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    (OUT_ROOT / f"{name}.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    issues = v1.v5.rcl._scan_wire_issues(object_chunk)
    if v1.rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if object_chunk.count(marker):
            issues.append(f"source-net case unexpectedly contains {marker.decode('ascii')}")
    for label in (b"\x02V0", b"\x02G0"):
        if label in object_chunk:
            issues.append(f"source-net case still contains terminal label {label[1:].decode('ascii')}")

    manifest = {
        "name": name,
        "description": description,
        "output": output_path.name,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": v1.v5._marker_counts(object_chunk),
        "device_marker_counts": v1.v5._marker_counts(devices),
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
    (OUT_ROOT / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _copy_control(name: str, description: str, source_file: Path) -> dict[str, Any]:
    output_path = OUT_ROOT / f"{name}.pdsprj"
    shutil.copy2(source_file, output_path)
    manifest = {
        "name": name,
        "description": description,
        "control": "exact_copy_short_path",
        "output": output_path.name,
        "hashes": {output_path.name: _sha256_file(output_path)},
    }
    (OUT_ROOT / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _transplant_control(
    *,
    base_project: Path,
    all3_project: Path,
    all3_devices: bytes,
) -> dict[str, Any]:
    object_chunk = v1.v5._object_chunk(all3_project)
    cdb = v1.read_internal_file(all3_project, "ROOT.CDB")
    return _write_direct(
        "D1",
        "All-source donor object chunk, ROOT.CDB, and source device table transplanted into E001.",
        base_project=base_project,
        donor_project=all3_project,
        object_chunk=object_chunk,
        cdb=cdb,
        devices=all3_devices,
        input_payload={"control": "all3_object_cdb_devices_transplanted_to_e001"},
    )


def _v_style_cases() -> list[Any]:
    cases: list[Any] = []
    for case in v1._case_definitions():
        sources = []
        for index, source in enumerate(case.sources, start=1):
            visible_value = source.visible_value if len(source.visible_value) == 3 else "10V"
            sources.append(replace(source, ref=f"V{index}", visible_value=visible_value))
        cases.append(replace(case, sources=tuple(sources)))
    return cases


def _make_source_only(
    name: str,
    description: str,
    *,
    sources: tuple[Any, ...],
    base_project: Path,
    all3_project: Path,
    source_donor_4x: Path,
    source_devices: bytes,
) -> dict[str, Any]:
    source_block, source_rows = v1._source_block(sources, source_donor_4x, 1)
    object_chunk = bytearray(b"\x00" + source_block)
    object_chunk[-1] = 0xFF
    return _write_direct(
        name,
        description,
        base_project=base_project,
        donor_project=all3_project,
        object_chunk=bytes(object_chunk),
        cdb=v1._build_cdb([], source_rows, 1),
        devices=source_devices,
        input_payload={
            "kind": "source_only_with_all3_source_device_table",
            "sources": [source.__dict__ | {"model": source.model} for source in source_rows],
        },
    )


def _make_requested(
    name: str,
    case: Any,
    *,
    templates: Any,
    base_project: Path,
    all3_project: Path,
    source_donor_4x: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v1.v5._source_net_rcl(templates, list(case.groups))
    first_source_id = len(specs) + 1
    source_block, sources = v1._source_block(case.sources, source_donor_4x, first_source_id)
    object_chunk = bytearray(b"\x00" + source_block + source_net_chunk[1:])
    object_chunk[-1] = 0xFF
    cdb_specs = [replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    return _write_direct(
        name,
        case.description,
        base_project=base_project,
        donor_project=all3_project,
        object_chunk=bytes(object_chunk),
        cdb=v1._build_cdb(cdb_specs, sources, first_source_id),
        devices=devices,
        input_payload={
            "kind": "requested_mixed_source_with_all3_source_device_table",
            "sources": [
                source.__dict__ | {"model": source.model, "global_id": first_source_id + index}
                for index, source in enumerate(sources)
            ],
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
            "rcl_counts": rcl_counts,
            "topology": topology,
            "exact_values": case.exact_values,
        },
    )


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    donors = _copy_donors()

    registry = v1.FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v1.v5.rcl._load_rcl_unit_templates(rcl_donor)

    all3 = donors["all3"]
    source_donor_4x = donors["v4"]
    all3_devices = v1.v5._device_section_from_dsn(v1.read_internal_file(all3, "ROOT.DSN"))
    rcl_devices = v1.v5._device_section_from_dsn(v1.read_internal_file(rcl_donor, "ROOT.DSN"))
    source_then_rcl_devices = _combine_device_sections(all3_devices, rcl_devices)
    rcl_then_source_devices = _combine_device_sections(rcl_devices, all3_devices)

    cases: list[dict[str, Any]] = [
        _copy_control("D0", "Exact copy of the user all-source donor with short name.", all3),
        _transplant_control(base_project=base_project, all3_project=all3, all3_devices=all3_devices),
        _make_source_only(
            "E0",
            "V4-style mixed source-only control using all-source donor device table and actual 2A current value.",
            sources=(
                v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
                v1.SourcePlan("dc_current", "V2", "2A", "02A", "D1"),
            ),
            base_project=base_project,
            all3_project=all3,
            source_donor_4x=source_donor_4x,
            source_devices=all3_devices,
        ),
        _make_source_only(
            "E1",
            "V4-style mixed source-only control using all-source donor device table and strict V2/10V current identity.",
            sources=(
                v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
                v1.SourcePlan("dc_current", "V2", "10V", "10V", "D1"),
            ),
            base_project=base_project,
            all3_project=all3,
            source_donor_4x=source_donor_4x,
            source_devices=all3_devices,
        ),
    ]

    requested = _v_style_cases()
    cases.append(
        _make_requested(
            "F1",
            requested[0],
            templates=templates,
            base_project=base_project,
            all3_project=all3,
            source_donor_4x=source_donor_4x,
            devices=source_then_rcl_devices,
        )
    )
    cases.append(
        _make_requested(
            "G1",
            requested[0],
            templates=templates,
            base_project=base_project,
            all3_project=all3,
            source_donor_4x=source_donor_4x,
            devices=rcl_then_source_devices,
        )
    )
    for index, case in enumerate(requested[1:], start=2):
        cases.append(
            _make_requested(
                f"F{index}",
                case,
                templates=templates,
                base_project=base_project,
                all3_project=all3,
                source_donor_4x=source_donor_4x,
                devices=source_then_rcl_devices,
            )
        )

    summary = {
        "batch_id": "MX6_ALL3_SOURCE_DONOR_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_donor": str(ALL3_DONOR),
        "method": "Use the user all-source donor as source-family device metadata authority; short direct filenames.",
        "test_order": [item["name"] for item in cases],
        "cases": cases,
    }
    (OUT_ROOT / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README.txt").write_text(
        "MX6 all-source donor diagnostics.\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {name}.pdsprj" for index, name in enumerate(summary["test_order"], start=1))
        + "\n\nD0 is the exact donor copy. D1 transplants donor object/CDB/devices into E001. "
        "E0/E1 test mixed DC source-only using the donor source device table. "
        "F1/G1 compare source-device-first vs RCL-device-first for requested circuit 1. "
        "F2-F5 are the remaining requested circuits using source-device-first metadata.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "gen.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
