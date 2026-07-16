"""Generate mixed DC source diagnostics from the all-source donor records.

MX6 feedback:

* D0 exact all-source donor copy worked.
* D1 all-source donor object/CDB/device transplant into E001 worked.
* E0/E1 source-only cases using old 4x-DCV source units failed with bad object
  record.
* F/G requested circuits using those old source units failed with ISIS.dll.

V7 therefore stops using the old 4x-DCV source records for mixed DC sources.
It extracts the working VSOURCE and CSOURCE object records from the user all-
source donor and duplicates those records directly. Source connectivity is still
not final in this batch; this isolates whether the donor's own source records
can coexist with generated R/C/L bodies.
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

V1_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-04" / "generate_dc_mixed_sources_v1_requested5_temp.py"
OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_mixed_sources_v7_all3_records_temp_2026_06_04"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_MIXED_SOURCES_V7_ALL3_RECORDS_TEMP_2026_06_04"
DONOR_ROOT = OUT_ROOT / "donors"

ALL3_DONOR = Path(r"C:\Users\tahab\Downloads\45454New Project.pdsprj")

PinStyle = Literal["passive", "source"]


def _load_v1() -> Any:
    spec = importlib.util.spec_from_file_location("dc_mixed_sources_v1_for_v7_all3", V1_PATH)
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
    if not ALL3_DONOR.exists():
        raise FileNotFoundError(ALL3_DONOR)
    dst = DONOR_ROOT / "all3_source_donor.pdsprj"
    shutil.copy2(ALL3_DONOR, dst)
    return {"all3": dst}


def _enc_source_pin_map() -> bytes:
    return v1._enc_str("+") + v1._enc_str("1") + v1._enc_str("-") + v1._enc_str("2")


def _enc_passive_pin_map(kind: str) -> bytes:
    if kind == "CAPACITOR":
        return v1._enc_str("2") + v1._enc_str("2") + v1._enc_str("1") + v1._enc_str("1")
    return v1._enc_str("1") + b"\x00" + v1._enc_str("2") + b"\x00"


def _build_cdb(rcl_specs: list[Any], sources: list[Any], first_source_id: int, *, pin_style: PinStyle) -> bytes:
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
    ordered: list[Any] = [*source_rows, *rcl_specs]
    out = bytearray()
    out += v1.rv9._u32(7)
    out += v1.rv9._u32(1) + v1.rv9._u32(1) + v1.rv9._u32(0) + v1._enc_str("ROOT") + b"\x00" + v1.rv9._u32(0) + v1.rv9._u32(1) + v1.rv9._u32(1)
    out += v1.rv9._u32(2)
    out += v1.rv9._u32(1) + v1.rv9._u32(3) + v1.rv9._u32(1) + v1._enc_str("") + v1.rv9._u32(10) + v1.rv9._u32(0)
    out += v1.rv9._u32(2) + v1.rv9._u32(2) + v1.rv9._u32(0) + v1._enc_str("Master Sheet") + v1.rv9._u32(10) + v1.rv9._u32(0)
    out += v1.rv9._u32(len(ordered))
    for spec in ordered:
        if isinstance(spec, dict):
            idx = spec["idx"]
            ref = spec["ref"]
            pin_map = _enc_source_pin_map() if pin_style == "source" else _enc_passive_pin_map("SOURCE")
        else:
            idx = spec.idx
            ref = spec.ref
            pin_map = _enc_passive_pin_map(spec.kind)
        out += v1.rv9._u32(idx) + v1.rv9._u32(1) + v1.rv9._u32(0) + v1.rv9._u32(idx) + v1._enc_str(ref)
        out += v1.rv9._u32(2) + pin_map
        out += v1.rv9._u32(0) + v1.rv9._u32(idx) + v1.rv9._u32(0)
    out += v1.rv9._u32(1) + v1.rv9._u32(1) + b"\x00" + v1._enc_str("") + v1.rv9._u32(1)
    out += v1.rv9._u32(len(ordered))
    for spec in ordered:
        out += v1.rv9._u32(spec["idx"] if isinstance(spec, dict) else spec.idx)
        out += v1.rv9._u32(1) + v1.rv9._u32(0) + v1.rv9._u32(0) + v1.rv9._u32(0)
        if isinstance(spec, dict):
            out += v1._enc_str(spec["ref"]) + v1._enc_str(spec["value"]) + v1._enc_str(spec["model"]) + v1._enc_str("") + v1._enc_text(spec["prop_text"])
        elif spec.kind == "CAPACITOR":
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("CAP") + v1._enc_str("CAP10") + v1._enc_text(v1.v5.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("REALIND") + v1._enc_str("") + v1._enc_text(v1.v5.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("RESISTOR") + v1._enc_str("") + v1._enc_text(v1.rv9.PROP_TEXT)
    out += v1.rv9._u32(0)
    return bytes(out)


def _split_all3_source_records(all3: Path) -> dict[str, bytes]:
    chunk = v1.v5._object_chunk(all3)
    starts = {
        "VSINE": chunk.find(b"\xff\x02V1") - 1,
        "VSOURCE": chunk.find(b"\xff\x02V2") - 1,
        "CSOURCE": chunk.find(b"\xff\x02I1") - 1,
    }
    if any(offset < 0 for offset in starts.values()):
        raise RuntimeError(f"Could not split all-source donor records: {starts}")
    bounds = [starts["VSINE"], starts["VSOURCE"], starts["CSOURCE"], len(chunk)]
    return {
        "VSINE": chunk[bounds[0] : bounds[1]],
        "VSOURCE": chunk[bounds[1] : bounds[2]],
        "CSOURCE": chunk[bounds[2] : bounds[3]],
    }


def _visible_value_for(source: Any) -> str:
    value = source.visible_value
    expected_len = 2
    if source.kind == "dc_voltage":
        if value.endswith("V") and len(value) >= 2:
            return value[:1] + "V"
        return "1V"
    if value.endswith("A") and len(value) >= 2:
        return value[:1] + "A"
    return "1A"


def _patch_all3_source_record(record: bytes, source: Any, global_id: int) -> bytes:
    out = bytearray(record)
    raw_ref = source.ref.encode("ascii")
    raw_value = _visible_value_for(source).encode("ascii")
    if len(raw_ref) != out[2]:
        raise ValueError(f"All-source ref must stay {out[2]} chars: {source.ref}")
    if len(raw_value) != out[70]:
        raise ValueError(f"All-source visible value must stay {out[70]} chars: {source.visible_value}")
    out[3 : 3 + len(raw_ref)] = raw_ref
    out[71 : 71 + len(raw_value)] = raw_value
    model = source.model.encode("ascii")
    model_pos = out.rfind(model)
    if model_pos < 0:
        raise RuntimeError(f"Model {source.model} not found in source record")
    body_coord = model_pos + len(model)
    out[body_coord + 12 : body_coord + 16] = v1.rv9._u32(global_id)
    out[-1] = 0x00
    return bytes(out)


def _source_block_from_all3(records: dict[str, bytes], sources: tuple[Any, ...], first_source_id: int) -> tuple[bytes, list[Any]]:
    parts: list[bytes] = []
    source_rows: list[Any] = []
    for index, source in enumerate(sources):
        template = records[source.model]
        parts.append(_patch_all3_source_record(template, source, first_source_id + index))
        source_rows.append(source)
    return b"".join(parts), source_rows


def _combine_device_sections(*sections: bytes) -> bytes:
    out = bytearray()
    for section in sections[:-1]:
        out += section[:-4]
    out += sections[-1]
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
    dsn, pointers = v1.v5._build_dsn_with_devices(
        v1.read_internal_file(base_project, "ROOT.DSN"),
        v1.read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
        devices,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base_project, "PROJECT.XML"), v1.PROTEUS_813)
    output_path = OUT_ROOT / f"{case_id}.pdsprj"
    cdb_path = OUT_ROOT / f"{case_id}.ROOT.CDB.bin"
    dsn_path = OUT_ROOT / f"{case_id}.ROOT.DSN.bin"
    chunk_path = OUT_ROOT / f"{case_id}.OBJECT_CHUNK.bin"
    v1.write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    (OUT_ROOT / f"{case_id}.input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    issues = v1.v5.rcl._scan_wire_issues(object_chunk)
    if v1.rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if object_chunk.count(marker):
            issues.append(f"source-net case unexpectedly contains {marker.decode('ascii')}")

    manifest = {
        "case_id": case_id,
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
    (OUT_ROOT / f"{case_id}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _copy_control(case_id: str, description: str, source_file: Path) -> dict[str, Any]:
    output_path = OUT_ROOT / f"{case_id}.pdsprj"
    shutil.copy2(source_file, output_path)
    manifest = {
        "case_id": case_id,
        "description": description,
        "control": "exact_copy",
        "output": output_path.name,
        "hashes": {output_path.name: _sha256_file(output_path)},
    }
    (OUT_ROOT / f"{case_id}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _source_refs_for_case(case: Any) -> Any:
    voltage_index = 0
    current_index = 0
    sources = []
    for source in case.sources:
        if source.kind == "dc_voltage":
            voltage_index += 1
            sources.append(replace(source, ref=f"V{voltage_index}"))
        else:
            current_index += 1
            sources.append(replace(source, ref=f"I{current_index}"))
    return replace(case, sources=tuple(sources))


def _all3_source_only(
    case_id: str,
    *,
    sources: tuple[Any, ...],
    records: dict[str, bytes],
    base_project: Path,
    all3: Path,
    devices: bytes,
    pin_style: PinStyle,
) -> dict[str, Any]:
    source_block, source_rows = _source_block_from_all3(records, sources, 1)
    object_chunk = bytearray(b"\x00" + source_block)
    object_chunk[-1] = 0xFF
    return _write_case(
        case_id,
        f"Source-only all-source donor records with {pin_style} source CDB pin style.",
        base_project=base_project,
        donor_project=all3,
        object_chunk=bytes(object_chunk),
        cdb=_build_cdb([], source_rows, 1, pin_style=pin_style),
        devices=devices,
        input_payload={
            "source_record_family": "all3_donor_records_without_terminal_wires",
            "pin_style": pin_style,
            "sources": [source.__dict__ | {"model": source.model} for source in source_rows],
        },
    )


def _requested_case(
    case_id: str,
    case: Any,
    *,
    records: dict[str, bytes],
    templates: Any,
    base_project: Path,
    all3: Path,
    devices: bytes,
    pin_style: PinStyle,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v1.v5._source_net_rcl(templates, list(case.groups))
    first_source_id = len(specs) + 1
    source_block, sources = _source_block_from_all3(records, case.sources, first_source_id)
    object_chunk = bytearray(b"\x00" + source_block + source_net_chunk[1:])
    object_chunk[-1] = 0xFF
    cdb_specs = [replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    return _write_case(
        case_id,
        case.description + f" Source records come from the all-source donor; CDB pin style={pin_style}.",
        base_project=base_project,
        donor_project=all3,
        object_chunk=bytes(object_chunk),
        cdb=_build_cdb(cdb_specs, sources, first_source_id, pin_style=pin_style),
        devices=devices,
        input_payload={
            "source_record_family": "all3_donor_records_without_terminal_wires",
            "pin_style": pin_style,
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
    all3 = donors["all3"]

    registry = v1.FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v1.v5.rcl._load_rcl_unit_templates(rcl_donor)
    records = _split_all3_source_records(all3)

    all3_devices = v1.v5._device_section_from_dsn(v1.read_internal_file(all3, "ROOT.DSN"))
    rcl_devices = v1.v5._device_section_from_dsn(v1.read_internal_file(rcl_donor, "ROOT.DSN"))
    source_then_rcl_devices = _combine_device_sections(all3_devices, rcl_devices)

    cases: list[dict[str, Any]] = [
        _copy_control("DCMS_V7_T00_ALL3_DONOR_COPY", "Exact all-source donor copy.", all3),
        _write_case(
            "DCMS_V7_T01_ALL3_TRANSPLANT_E001",
            "All-source donor object chunk, ROOT.CDB, and source device table transplanted into E001.",
            base_project=base_project,
            donor_project=all3,
            object_chunk=v1.v5._object_chunk(all3),
            cdb=v1.read_internal_file(all3, "ROOT.CDB"),
            devices=all3_devices,
            input_payload={"control": "all3_object_cdb_devices_transplanted_to_e001"},
        ),
    ]

    source_only_sources = (
        v1.SourcePlan("dc_voltage", "V1", "12V", "1V", "DV"),
        v1.SourcePlan("dc_current", "I1", "2A", "2A", "D1"),
    )
    cases.append(
        _all3_source_only(
            "DCMS_V7_T02_SOURCE_ONLY_PASSIVE_CDB",
            sources=source_only_sources,
            records=records,
            base_project=base_project,
            all3=all3,
            devices=all3_devices,
            pin_style="passive",
        )
    )
    cases.append(
        _all3_source_only(
            "DCMS_V7_T03_SOURCE_ONLY_SOURCEPIN_CDB",
            sources=source_only_sources,
            records=records,
            base_project=base_project,
            all3=all3,
            devices=all3_devices,
            pin_style="source",
        )
    )

    requested = [_source_refs_for_case(case) for case in v1._case_definitions()]
    cases.append(
        _requested_case(
            "DCMS_V7_T04_REQUESTED1_PASSIVE_CDB",
            requested[0],
            records=records,
            templates=templates,
            base_project=base_project,
            all3=all3,
            devices=source_then_rcl_devices,
            pin_style="passive",
        )
    )
    cases.append(
        _requested_case(
            "DCMS_V7_T05_REQUESTED1_SOURCEPIN_CDB",
            requested[0],
            records=records,
            templates=templates,
            base_project=base_project,
            all3=all3,
            devices=source_then_rcl_devices,
            pin_style="source",
        )
    )
    for index, case in enumerate(requested[1:], start=2):
        cases.append(
            _requested_case(
                f"DCMS_V7_T{index + 4:02d}_REQUESTED{index}_SOURCEPIN_CDB",
                case,
                records=records,
                templates=templates,
                base_project=base_project,
                all3=all3,
                devices=source_then_rcl_devices,
                pin_style="source",
            )
        )

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V7_ALL3_RECORDS_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "MX6: D0/D1 worked; E0/E1 bad object record; F/G onward ISIS.dll.",
        "method": "Use donor VSOURCE/CSOURCE object records directly instead of 4x-DCV source units.",
        "test_order": [item["case_id"] for item in cases],
        "cases": cases,
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V7_ALL3_RECORDS_TEMP_2026_06_04\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT02/T03 isolate all-source donor VSOURCE/CSOURCE records without R/C/L. "
        "T04/T05 test requested circuit 1 with passive vs source-pin CDB rows. "
        "T06-T09 are requested circuits 2-5 using source-pin CDB rows.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
