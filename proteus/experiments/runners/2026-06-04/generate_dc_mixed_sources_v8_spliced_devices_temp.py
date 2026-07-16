"""Generate mixed DC-source diagnostics with entry-level device splicing.

V7 feedback:

* T00-T03 worked.
* T04 onward gave ISIS.dll.

That means the all-source donor records are safe when used alone, but the
requested R/C/L cases are unsafe after joining source metadata with R/C/L
metadata. The accepted single-source packs did not concatenate whole device
sections; they used one coherent donor device section that already contained
the needed device families. V8 therefore splices only the missing CSOURCE
device entry into the accepted VSOURCE+R/C/L device section.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

V1_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-04" / "generate_dc_mixed_sources_v1_requested5_temp.py"
OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_mixed_sources_v8_spliced_devices_temp_2026_06_04"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_MIXED_SOURCES_V8_SPLICED_DEVICES_TEMP_2026_06_04"
DONOR_ROOT = OUT_ROOT / "donors"

USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
USER_CURRENT_RCL_DONOR = Path(r"C:\Users\tahab\Downloads\testing.pdsprj")
VOLTAGE_RCL_DONOR = (
    REPO_ROOT
    / "experiments"
    / "dc_sources_v7_accepted_source_first_temp_2026_06_03"
    / "donors"
    / "manual_combined_testing.pdsprj"
)

CdbOrder = Literal["sources_first", "sources_last"]
CurrentIdentity = Literal["actual_i_ref", "strict_v_ref_10v"]


def _load_v1() -> Any:
    spec = importlib.util.spec_from_file_location("dc_mixed_sources_v1_for_v8_spliced", V1_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V1 helper module from {V1_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_v1()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "4x_dc_voltage_10v": USER_DONOR_ROOT / "4x dc_voltage_01_default_10v.pdsprj",
        "voltage_rcl": VOLTAGE_RCL_DONOR,
        "current_rcl": USER_CURRENT_RCL_DONOR,
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _device_entries(section: bytes, names: tuple[str, ...]) -> dict[str, bytes]:
    starts: dict[str, int] = {}
    for name in names:
        marker = bytes([len(name)]) + name.encode("ascii")
        start = section.find(marker)
        if start < 0:
            raise RuntimeError(f"Device entry {name} not found.")
        starts[name] = start
    ordered = sorted(starts.items(), key=lambda item: item[1])
    out: dict[str, bytes] = {}
    for index, (name, start) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else len(section) - 4
        if start >= end:
            raise RuntimeError(f"Bad device entry bounds for {name}: {start}:{end}")
        out[name] = section[start:end]
    return out


def _spliced_device_section(voltage_rcl_devices: bytes, current_rcl_devices: bytes, *, order: str) -> bytes:
    voltage_entries = _device_entries(voltage_rcl_devices, ("CAP", "REALIND", "RESISTOR", "VSOURCE"))
    current_entries = _device_entries(current_rcl_devices, ("CAP", "CSOURCE", "REALIND", "RESISTOR"))
    if order == "cap_real_res_vsrc_csrc":
        entries = [
            voltage_entries["CAP"],
            voltage_entries["REALIND"],
            voltage_entries["RESISTOR"],
            voltage_entries["VSOURCE"],
            current_entries["CSOURCE"],
        ]
    elif order == "cap_csrc_real_res_vsrc":
        entries = [
            voltage_entries["CAP"],
            current_entries["CSOURCE"],
            voltage_entries["REALIND"],
            voltage_entries["RESISTOR"],
            voltage_entries["VSOURCE"],
        ]
    else:
        raise ValueError(order)
    return b"".join(entries) + voltage_rcl_devices[-4:]


def _build_cdb(
    rcl_specs: list[Any],
    sources: list[Any],
    first_source_id: int,
    *,
    cdb_order: CdbOrder,
) -> bytes:
    source_rows = [
        {
            "idx": first_source_id + index,
            "ref": source.ref,
            "value": source.cdb_value,
            "model": source.model,
            "prop_text": source.prop_text,
        }
        for index, source in enumerate(sources)
    ]
    ordered: list[Any] = [*source_rows, *rcl_specs] if cdb_order == "sources_first" else [*rcl_specs, *source_rows]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + v1._enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + v1._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + v1._enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        if isinstance(spec, dict):
            idx = spec["idx"]
            ref = spec["ref"]
            kind = "SOURCE"
        else:
            idx = spec.idx
            ref = spec.ref
            kind = spec.kind
        out += rv9._u32(idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(idx) + v1._enc_str(ref)
        if kind == "CAPACITOR":
            out += rv9._u32(2) + v1._enc_str("2") + v1._enc_str("2") + v1._enc_str("1") + v1._enc_str("1")
        else:
            out += rv9._u32(2) + v1._enc_str("1") + b"\x00" + v1._enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + v1._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        if isinstance(spec, dict):
            out += rv9._u32(spec["idx"]) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += (
                v1._enc_str(spec["ref"])
                + v1._enc_str(spec["value"])
                + v1._enc_str(spec["model"])
                + v1._enc_str("")
                + v1._enc_text(spec["prop_text"])
            )
        elif spec.kind == "CAPACITOR":
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("CAP") + v1._enc_str("CAP10") + v1._enc_text(v1.v5.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("REALIND") + v1._enc_str("") + v1._enc_text(v1.v5.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("RESISTOR") + v1._enc_str("") + v1._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


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
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = v1.v5._build_dsn_with_devices(
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

    issues = v1.v5.rcl._scan_wire_issues(object_chunk)
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
        "status": "temporary_dc_mixed_sources_v8_spliced_devices_not_locked",
        "output": str(output_path.relative_to(OUT_ROOT)),
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
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    return manifest


def _current_identity_case(case: Any, identity: CurrentIdentity) -> Any:
    if identity == "actual_i_ref":
        return case
    source_index = 0
    sources = []
    for source in case.sources:
        source_index += 1
        if source.kind == "dc_current":
            sources.append(replace(source, ref=f"V{source_index}", cdb_value="10V", visible_value="10V"))
        else:
            sources.append(replace(source, ref=f"V{source_index}"))
    return replace(case, sources=tuple(sources))


def _source_only_case(
    case_id: str,
    *,
    sources: tuple[Any, ...],
    source_donor_4x: Path,
    base_project: Path,
    donor_project: Path,
    devices: bytes,
    cdb_order: CdbOrder,
) -> dict[str, Any]:
    source_block, source_rows = v1._source_block(sources, source_donor_4x, 1)
    object_chunk = bytearray(b"\x00" + source_block)
    object_chunk[-1] = 0xFF
    return _write_case(
        case_id,
        f"Source-only V1-style source units using spliced VSOURCE+CSOURCE+R/C/L devices; CDB order={cdb_order}.",
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=bytes(object_chunk),
        cdb=_build_cdb([], source_rows, 1, cdb_order=cdb_order),
        devices=devices,
        input_payload={
            "kind": "source_only_v1_style_source_units",
            "cdb_order": cdb_order,
            "sources": [source.__dict__ | {"model": source.model} for source in source_rows],
        },
    )


def _rcl_only_case(
    case_id: str,
    case: Any,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v1.v5._source_net_rcl(templates, list(case.groups))
    cdb_specs = [replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    return _write_case(
        case_id,
        "R/C/L body only, but with the spliced mixed-source device section. This isolates device-section safety.",
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=source_net_chunk,
        cdb=_build_cdb(cdb_specs, [], len(specs) + 1, cdb_order="sources_last"),
        devices=devices,
        input_payload={
            "kind": "rcl_only_with_spliced_device_section",
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
            "rcl_counts": rcl_counts,
            "topology": topology,
        },
    )


def _requested_case(
    case_id: str,
    case: Any,
    *,
    templates: Any,
    source_donor_4x: Path,
    base_project: Path,
    donor_project: Path,
    devices: bytes,
    cdb_order: CdbOrder,
    identity: CurrentIdentity,
) -> dict[str, Any]:
    adjusted = _current_identity_case(case, identity)
    source_net_chunk, specs, topology, rcl_counts = v1.v5._source_net_rcl(templates, list(adjusted.groups))
    first_source_id = len(specs) + 1
    source_block, sources = v1._source_block(adjusted.sources, source_donor_4x, first_source_id)
    cdb_specs = [replace(spec, value=adjusted.exact_values.get(spec.ref, spec.value)) for spec in specs]
    return _write_case(
        case_id,
        adjusted.description
        + f" Uses V1-style source units, spliced source/RCL devices, current identity={identity}, CDB order={cdb_order}.",
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=_source_first_chunk(source_block, source_net_chunk),
        cdb=_build_cdb(cdb_specs, sources, first_source_id, cdb_order=cdb_order),
        devices=devices,
        input_payload={
            "kind": "requested_mixed_dc_sources_v8_spliced_devices",
            "current_identity": identity,
            "cdb_order": cdb_order,
            "sources": [
                source.__dict__ | {"model": source.model, "global_id": first_source_id + index}
                for index, source in enumerate(sources)
            ],
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in adjusted.groups],
            "exact_values": adjusted.exact_values,
            "rcl_counts": rcl_counts,
            "topology": topology,
        },
    )


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    donors = _copy_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v1.v5.rcl._load_rcl_unit_templates(rcl_donor)

    voltage_rcl = donors["voltage_rcl"]
    current_rcl = donors["current_rcl"]
    source_donor_4x = donors["4x_dc_voltage_10v"]
    voltage_rcl_devices = v1.v5._device_section_from_dsn(read_internal_file(voltage_rcl, "ROOT.DSN"))
    current_rcl_devices = v1.v5._device_section_from_dsn(read_internal_file(current_rcl, "ROOT.DSN"))
    devices_a = _spliced_device_section(voltage_rcl_devices, current_rcl_devices, order="cap_real_res_vsrc_csrc")
    devices_b = _spliced_device_section(voltage_rcl_devices, current_rcl_devices, order="cap_csrc_real_res_vsrc")
    requested = v1._case_definitions()

    cases: list[dict[str, Any]] = [
        _rcl_only_case(
            "DCMS_V8_T00_RCL_ONLY_SPLICED_DEVICES_A",
            requested[0],
            templates=templates,
            base_project=base_project,
            donor_project=voltage_rcl,
            devices=devices_a,
        ),
        _source_only_case(
            "DCMS_V8_T01_SOURCE_ONLY_ACTUAL_SPLICED_DEVICES_A",
            sources=requested[0].sources,
            source_donor_4x=source_donor_4x,
            base_project=base_project,
            donor_project=voltage_rcl,
            devices=devices_a,
            cdb_order="sources_first",
        ),
        _source_only_case(
            "DCMS_V8_T02_SOURCE_ONLY_STRICT_SPLICED_DEVICES_A",
            sources=_current_identity_case(requested[0], "strict_v_ref_10v").sources,
            source_donor_4x=source_donor_4x,
            base_project=base_project,
            donor_project=voltage_rcl,
            devices=devices_a,
            cdb_order="sources_last",
        ),
        _requested_case(
            "DCMS_V8_T03_REQUESTED1_ACTUAL_CDB_LAST_DEVICES_A",
            requested[0],
            templates=templates,
            source_donor_4x=source_donor_4x,
            base_project=base_project,
            donor_project=voltage_rcl,
            devices=devices_a,
            cdb_order="sources_last",
            identity="actual_i_ref",
        ),
        _requested_case(
            "DCMS_V8_T04_REQUESTED1_STRICT_CDB_LAST_DEVICES_A",
            requested[0],
            templates=templates,
            source_donor_4x=source_donor_4x,
            base_project=base_project,
            donor_project=voltage_rcl,
            devices=devices_a,
            cdb_order="sources_last",
            identity="strict_v_ref_10v",
        ),
        _requested_case(
            "DCMS_V8_T05_REQUESTED1_STRICT_CDB_FIRST_DEVICES_A",
            requested[0],
            templates=templates,
            source_donor_4x=source_donor_4x,
            base_project=base_project,
            donor_project=voltage_rcl,
            devices=devices_a,
            cdb_order="sources_first",
            identity="strict_v_ref_10v",
        ),
        _requested_case(
            "DCMS_V8_T06_REQUESTED1_STRICT_CDB_LAST_DEVICES_B",
            requested[0],
            templates=templates,
            source_donor_4x=source_donor_4x,
            base_project=base_project,
            donor_project=voltage_rcl,
            devices=devices_b,
            cdb_order="sources_last",
            identity="strict_v_ref_10v",
        ),
    ]

    for index, case in enumerate(requested[1:], start=2):
        cases.append(
            _requested_case(
                f"DCMS_V8_T{index + 5:02d}_REQUESTED{index}_STRICT_CDB_LAST_DEVICES_A",
                case,
                templates=templates,
                source_donor_4x=source_donor_4x,
                base_project=base_project,
                donor_project=voltage_rcl,
                devices=devices_a,
                cdb_order="sources_last",
                identity="strict_v_ref_10v",
            )
        )

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V8_SPLICED_DEVICES_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V7 T00-T03 worked; T04 onward ISIS.dll.",
        "method": (
            "Splice one CSOURCE device entry from the accepted current+RCL donor into "
            "the accepted VSOURCE+RCL device section. Use V1-style source-first units "
            "instead of whole-section device concatenation."
        ),
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
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V8_SPLICED_DEVICES_TEMP_2026_06_04\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT00 isolates the spliced device section with only R/C/L records. "
        "T01/T02 isolate source-only records. T03-T06 compare current identity, CDB order, and device-entry order on requested circuit 1. "
        "T07-T10 are requested circuits 2-5 using the strict current identity if T04/T06 open.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
