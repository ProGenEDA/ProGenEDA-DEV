"""Generate AC-voltage source + mixed R/C/L diagnostics.

The supplied AC-voltage donors show Proteus uses:

* ordinary source-net terminal labels AV/A0
* VSINE as the source model, not VSOURCE
* AC settings stored as properties, for example {VA=20v} and {FREQ=5000hz}
* no default $TERPOWER/$TERGROUND records in the source object chunk

This temp batch tests exact donor controls, E001 transplants, a generated
AV/A0 R/C/L body without a source, and generated source-first/source-last
VSINE cases before any main-code promotion.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_21_case, mixed_rcl_6_case, mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "experiments" / "ac_voltage_v1_source_diagnostics_temp_2026_06_04"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "AC_VOLTAGE_V1_SOURCE_DIAGNOSTICS_TEMP_2026_06_04"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "ACV_V1_SOURCE_DIAGNOSTICS_TEST_BATCH"
USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\Project Backups")
V5_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"

SourcePosition = Literal["before_rcl", "after_rcl"]


@dataclass(frozen=True)
class AcVoltageSpec:
    idx: int
    ref: str
    value: str
    prop_text: bytes

    @property
    def model(self) -> str:
        return "VSINE"


def _load_v5() -> Any:
    spec = importlib.util.spec_from_file_location("dc_sources_v5_for_acv_v1", V5_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V5 helper module from {V5_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v5 = _load_v5()
rcl = v5.rcl


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(4 + len(value)) + value


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "ac_voltage_01_default": USER_DONOR_ROOT / "ac_voltage_01_default.pdsprj",
        "ac_voltage_02_variant": USER_DONOR_ROOT / "ac_voltage_02_variant.pdsprj",
        "2xac_voltage_02_variant": USER_DONOR_ROOT / "2xac_voltage_02_variant.pdsprj",
        "ac_voltage_03_resistor_load": USER_DONOR_ROOT / "ac_voltage_03_resistor_load.pdsprj",
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _object_chunk(project_path: Path) -> bytes:
    return rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))


def _source_prop_text(project_path: Path, ref: str = "V1") -> bytes:
    cdb = read_internal_file(project_path, "ROOT.CDB")
    marker = _enc_str(ref) + _enc_str("VSINE") + _enc_str("VSINE") + _enc_str("")
    pos = cdb.find(marker)
    if pos < 0:
        raise RuntimeError(f"Cannot find VSINE CDB property entry in {project_path}.")
    text_len_pos = pos + len(marker)
    total_len = struct.unpack("<I", cdb[text_len_pos : text_len_pos + 4])[0]
    return cdb[text_len_pos + 4 : text_len_pos + total_len]


def _build_cdb(rcl_specs: list[Any], source_specs: list[AcVoltageSpec], source_position: SourcePosition) -> bytes:
    ordered: list[Any] = [*source_specs, *rcl_specs] if source_position == "before_rcl" else [*rcl_specs, *source_specs]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + _enc_str(spec.ref)
        if isinstance(spec, AcVoltageSpec):
            out += rv9._u32(2) + _enc_str("+") + _enc_str("1") + _enc_str("-") + _enc_str("2")
        elif spec.kind == "CAPACITOR":
            out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, AcVoltageSpec):
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str(spec.model) + _enc_str("") + _enc_text(spec.prop_text)
        elif spec.kind == "CAPACITOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(rcl.INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _patch_source_global_id_only(source_record: bytes, global_id: int) -> bytes:
    out = bytearray(source_record)
    model_pos = out.rfind(b"VSINE")
    if model_pos < 0:
        raise RuntimeError("VSINE model marker not found in source record.")
    body_coord = model_pos + len(b"VSINE")
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    return bytes(out)


def _standalone_source_block(source_project: Path, *, global_id: int, final: bool) -> bytes:
    body = bytearray(_object_chunk(source_project)[1:])
    if len(body) < 623:
        raise RuntimeError("Standalone AC source block is shorter than expected.")
    body[207:573] = _patch_source_global_id_only(bytes(body[207:573]), global_id)
    body[-1] = 0xFF if final else 0x00
    return bytes(body)


def _load_source_last_block(load_project: Path, *, global_id: int, final: bool) -> bytes:
    body = _object_chunk(load_project)[1:]
    marker = body.rfind(b"$TERINPUT")
    if marker < 14:
        raise RuntimeError("Cannot locate source-last AC input terminal in load donor.")
    start = marker - 14
    block = bytearray(body[start:])
    if len(block) < 623:
        raise RuntimeError("Source-last AC source block is shorter than expected.")
    block[207:573] = _patch_source_global_id_only(bytes(block[207:573]), global_id)
    block[-1] = 0xFF if final else 0x00
    return bytes(block)


def _map_groups_to_ac_nets(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    groups = []
    for item in payload["groups"]:
        start = "AV" if item["start"] == "V0" else "A0" if item["start"] == "G0" else item["start"]
        end = "AV" if item["end"] == "V0" else "A0" if item["end"] == "G0" else item["end"]
        groups.append((item["mode"], start, end))
    return groups


def _source_net_rcl(templates: Any, payload: dict[str, Any]) -> tuple[bytes, list[Any], list[dict[str, Any]], dict[str, Any], list[tuple[str, str, str]]]:
    groups = _map_groups_to_ac_nets(payload)
    chunk, specs, topology, counts = v5._source_net_rcl(templates, groups)
    counts = {**counts, "source_net_positive": "AV", "source_net_negative": "A0"}
    return chunk, specs, topology, counts, groups


def _source_first_chunk(source_block_nonfinal: bytes, source_net_chunk: bytes) -> bytes:
    out = bytearray(b"\x00" + source_block_nonfinal + source_net_chunk[1:])
    out[-1] = 0xFF
    return bytes(out)


def _source_last_chunk(source_net_chunk: bytes, source_block_final: bytes) -> bytes:
    body = bytearray(source_net_chunk[1:])
    body[-1] = 0x00
    return bytes(b"\x00" + body + source_block_final)


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "VSINE",
        "VSOURCE",
        "CSOURCE",
        "CAPACITOR",
        "REALIND",
        "RESISTOR",
        "WIRE",
        "COMPONENT ID",
        "COMPONENT VALUE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _write_exact_copy_case(case_id: str, description: str, project: Path) -> dict[str, Any]:
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(project, output_path)
    chunk = _object_chunk(project)
    cdb = read_internal_file(project, "ROOT.CDB")
    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_ac_voltage_v1_exact_copy_control",
        "output": str(output_path.relative_to(OUT_ROOT)),
        "source_project": str(project),
        "object_chunk_len": len(chunk),
        "root_cdb_len": len(cdb),
        "marker_counts": _marker_counts(chunk),
        "static_validation_issues": [],
        "hashes": {
            output_path.name: _sha256_file(output_path),
            "object_chunk": _sha256_bytes(chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _write_case(
    case_id: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any] | None = None,
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

    issues = rcl._scan_wire_issues(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    if object_chunk.count(b"$TERPOWER"):
        issues.append("source-net case unexpectedly contains $TERPOWER")
    if object_chunk.count(b"$TERGROUND"):
        issues.append("source-net case unexpectedly contains $TERGROUND")
    for label in (b"\x02V0", b"\x02G0", b"\x02DV", b"\x02D0"):
        if label in object_chunk:
            issues.append(f"AC source-net case still contains non-AC source label {label[1:].decode('ascii')}")
    if b"\x02AV" not in object_chunk or b"\x02A0" not in object_chunk:
        issues.append("AC source-net case should contain AV/A0 terminals")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_ac_voltage_v1_source_diagnostic_not_locked",
        "output": str(output_path.relative_to(OUT_ROOT)),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "device_marker_counts": _marker_counts(devices),
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
    }
    if input_payload is not None:
        (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")
        manifest["input"] = input_payload
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _write_transplant_case(case_id: str, description: str, *, base_project: Path, donor_project: Path) -> dict[str, Any]:
    chunk = _object_chunk(donor_project)
    cdb = read_internal_file(donor_project, "ROOT.CDB")
    devices = v5._device_section_from_dsn(read_internal_file(donor_project, "ROOT.DSN"))
    return _write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=chunk,
        cdb=cdb,
        devices=devices,
    )


def _make_source_case(
    *,
    case_id: str,
    description: str,
    payload: dict[str, Any],
    source_position: SourcePosition,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_project: Path,
    source_load_project: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts, groups = _source_net_rcl(templates, payload)
    source = AcVoltageSpec(idx=len(specs) + 1, ref="V1", value="VSINE", prop_text=_source_prop_text(source_project))
    if source_position == "before_rcl":
        source_block = _standalone_source_block(source_project, global_id=source.idx, final=False)
        object_chunk = _source_first_chunk(source_block, source_net_chunk)
    else:
        source_block = _load_source_last_block(source_load_project, global_id=source.idx, final=True)
        object_chunk = _source_last_chunk(source_net_chunk, source_block)
    return _write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=_build_cdb(specs, [source], source_position),
        devices=devices,
        input_payload={
            "base_payload_name": payload["project"]["name"],
            "source_kind": "ac_voltage",
            "source_model": "VSINE",
            "source_position": source_position,
            "source": {"idx": source.idx, "ref": source.ref, "value": source.value, "properties": source.prop_text.decode("ascii", "replace")},
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
    templates = rcl._load_rcl_unit_templates(rcl_donor)

    default_source = donors["ac_voltage_01_default"]
    variant_source = donors["ac_voltage_02_variant"]
    two_source = donors["2xac_voltage_02_variant"]
    source_load = donors["ac_voltage_03_resistor_load"]
    acv_devices = v5._device_section_from_dsn(read_internal_file(source_load, "ROOT.DSN"))
    rcl_devices = v5._device_section_from_dsn(read_internal_file(rcl_donor, "ROOT.DSN"))

    simple_loop = mixed_rcl_15_cases()[0]
    six_case = mixed_rcl_6_case()
    twenty_one_case = mixed_rcl_21_case()

    # Sanity: source-only CDB generation should match the user variant donor.
    variant_prop = _source_prop_text(variant_source)
    generated_variant_cdb = _build_cdb([ ], [AcVoltageSpec(1, "V1", "VSINE", variant_prop)], "before_rcl")
    variant_cdb_match = generated_variant_cdb == read_internal_file(variant_source, "ROOT.CDB")

    cases: list[dict[str, Any]] = []
    cases.append(_write_exact_copy_case("ACV_V1_T00_EXACT_DEFAULT_COPY", "Exact supplied default AC voltage source donor copy.", default_source))
    cases.append(_write_transplant_case("ACV_V1_T01_DEFAULT_TRANSPLANT_E001", "Default AC voltage object/CDB/device transplant into E001.", base_project=base_project, donor_project=default_source))
    cases.append(_write_transplant_case("ACV_V1_T02_VARIANT_TRANSPLANT_E001", "Variant AC voltage object/CDB/device transplant into E001.", base_project=base_project, donor_project=variant_source))
    cases.append(_write_transplant_case("ACV_V1_T03_TWO_SOURCE_TRANSPLANT_E001", "Two-source AC voltage donor transplant into E001.", base_project=base_project, donor_project=two_source))

    no_source_chunk, no_source_specs, no_source_topology, no_source_counts, no_source_groups = _source_net_rcl(templates, six_case)
    cases.append(
        _write_case(
            "ACV_V1_T04_RCL_AV_A0_NO_SOURCE_CONTROL",
            "Generated six-component R/C/L body on AV/A0 labels with no source object.",
            base_project=base_project,
            donor_project=rcl_donor,
            object_chunk=no_source_chunk,
            cdb=rcl.build_cdb(no_source_specs),
            devices=rcl_devices,
            input_payload={
                "base_payload_name": six_case["project"]["name"],
                "source_kind": "none",
                "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in no_source_groups],
                "rcl_counts": no_source_counts,
                "topology": no_source_topology,
            },
        )
    )
    cases.append(
        _make_source_case(
            case_id="ACV_V1_T05_SIMPLE_LOOP_SOURCE_FIRST",
            description="Generated simple-loop R/C/L topology with source-first standalone VSINE block.",
            payload=simple_loop,
            source_position="before_rcl",
            templates=templates,
            base_project=base_project,
            donor_project=source_load,
            source_project=variant_source,
            source_load_project=source_load,
            devices=acv_devices,
        )
    )
    cases.append(
        _make_source_case(
            case_id="ACV_V1_T06_SIX_COMPONENT_SOURCE_FIRST",
            description="Generated six-component R/C/L circuit with source-first standalone VSINE block.",
            payload=six_case,
            source_position="before_rcl",
            templates=templates,
            base_project=base_project,
            donor_project=source_load,
            source_project=variant_source,
            source_load_project=source_load,
            devices=acv_devices,
        )
    )
    cases.append(
        _make_source_case(
            case_id="ACV_V1_T07_SIX_COMPONENT_SOURCE_LAST_LOAD_BLOCK",
            description="Generated six-component R/C/L circuit with source-last VSINE block extracted from the load donor.",
            payload=six_case,
            source_position="after_rcl",
            templates=templates,
            base_project=base_project,
            donor_project=source_load,
            source_project=variant_source,
            source_load_project=source_load,
            devices=acv_devices,
        )
    )
    cases.append(
        _make_source_case(
            case_id="ACV_V1_T08_21_RULE_SOURCE_FIRST",
            description="Generated corrected 21-rule R/C/L circuit with source-first standalone VSINE block.",
            payload=twenty_one_case,
            source_position="before_rcl",
            templates=templates,
            base_project=base_project,
            donor_project=source_load,
            source_project=variant_source,
            source_load_project=source_load,
            devices=acv_devices,
        )
    )
    cases.append(
        _make_source_case(
            case_id="ACV_V1_T09_21_RULE_SOURCE_LAST_LOAD_BLOCK",
            description="Generated corrected 21-rule R/C/L circuit with source-last VSINE block extracted from the load donor.",
            payload=twenty_one_case,
            source_position="after_rcl",
            templates=templates,
            base_project=base_project,
            donor_project=source_load,
            source_project=variant_source,
            source_load_project=source_load,
            devices=acv_devices,
        )
    )

    summary = {
        "batch_id": "AC_VOLTAGE_V1_SOURCE_DIAGNOSTICS_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "donor_findings": {
            "source_model": "VSINE",
            "source_nets": ["AV", "A0"],
            "source_cdb_value_field": "VSINE",
            "source_properties": "VA/FREQ/PRIMITIVE",
            "generated_variant_source_only_cdb_matches_user_variant": variant_cdb_match,
            "load_donor_device_section_contains": _marker_counts(acv_devices),
        },
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item["marker_counts"],
                "device_marker_counts": item.get("device_marker_counts"),
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "AC voltage V1 source diagnostics.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT05/T06/T08 test source-first VSINE insertion. T07/T09 test source-last insertion from the load donor.\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(
        json.dumps(
            {
                "out_root": str(OUT_ROOT),
                "archive": archive,
                "archive_sha256": _sha256_file(Path(archive)),
                "variant_source_only_cdb_match": variant_cdb_match,
                "test_order": summary["test_order"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
