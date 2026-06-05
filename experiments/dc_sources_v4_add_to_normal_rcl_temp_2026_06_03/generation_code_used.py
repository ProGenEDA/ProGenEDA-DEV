"""Temporary DC voltage/current source composition experiment, V4.

This is deliberately not promoted into src/proteusgen. It composes the
user-supplied DC voltage and DC current terminal donors with the already locked
mixed R/C/L group renderer so the generated files can be manually opened in
Proteus before any main-generator work.

V4 responds to the V3 user report: all exact donor controls opened, but all
generated source+R/C/L circuits gave ISIS.dll errors. This batch follows the
user-proposed direction: build the R/C/L circuit in the normal accepted V0/G0
shape first, then add a DC source whose positive terminal is an output named V0
and whose negative terminal is an input named G0. Connection is by matching
terminal labels.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from zipfile import ZipFile


REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from proteusgen import mixed_passive as mp  # noqa: E402
from proteusgen import mixed_rcl as rcl  # noqa: E402
from proteusgen import mixed_rcl_examples as rcl_examples  # noqa: E402
from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import MixedRclCircuitIR, MixedRclGroup  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402


EXPERIMENT_ROOT = Path(__file__).resolve().parent
DONOR_ROOT = EXPERIMENT_ROOT / "donors"
OUT_ROOT = EXPERIMENT_ROOT / "DC_SOURCES_V4_ADD_TO_NORMAL_RCL_TEST_BATCH"

SourceKind = Literal["dc_voltage", "dc_current"]
SourcePosition = Literal["before_rcl", "after_rcl"]
PowerBridgePolicy = Literal["keep_normal_power_ground", "remove_power_bridge_keep_ground"]


@dataclass(frozen=True)
class SourceSpec:
    kind: SourceKind
    global_id: int
    ref: str
    value: str
    positive: str
    negative: str
    x: int
    y: int

    @property
    def idx(self) -> int:
        return self.global_id

    @property
    def model(self) -> str:
        return "VSOURCE" if self.kind == "dc_voltage" else "CSOURCE"

    @property
    def prop_text(self) -> bytes:
        return b"{PRIMITIVE=ANALOG}\n\x00" if self.kind == "dc_voltage" else b"{PRIMITIVE=ANALOGUE}\n\x00"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(4 + len(value)) + value


def _read_dsn(path: Path) -> bytes:
    with ZipFile(path, "r") as zf:
        return zf.read("ROOT.DSN")


def _object_chunk(path: Path) -> bytes:
    return rv9._extract_object_chunk(_read_dsn(path))


def _device_section(path: Path) -> bytes:
    dsn = _read_dsn(path)
    marker = b"{PACKAGE=NULL}\n\x00"
    first = dsn.find(b"ISIS CIRCUIT FILE")
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise RuntimeError(f"Could not locate device section in {path}")
    insert += len(marker)
    return dsn[insert:first]


def _source_device_section(kind: SourceKind, *, final: bool) -> bytes:
    if kind == "dc_voltage":
        section = _device_section(DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj")
    else:
        section = _device_section(DONOR_ROOT / "dc_current_01_default.pdsprj")
    return section if final else section[:-4]


def _source_device_sections(source_kinds: set[SourceKind], *, final_on_last: bool) -> list[bytes]:
    kinds: list[SourceKind] = []
    if "dc_voltage" in source_kinds:
        kinds.append("dc_voltage")
    if "dc_current" in source_kinds:
        kinds.append("dc_current")
    return [
        _source_device_section(kind, final=final_on_last and index == len(kinds) - 1)
        for index, kind in enumerate(kinds)
    ]


def _combined_device_section(source_kinds: set[SourceKind], rcl_donor: Path, source_position: SourcePosition) -> bytes:
    rcl_section = _device_section(rcl_donor)
    if source_position == "before_rcl":
        source_sections = _source_device_sections(source_kinds, final_on_last=False)
        sections = [*source_sections, rcl_section]
    else:
        source_sections = _source_device_sections(source_kinds, final_on_last=True)
        sections = [rcl_section[:-4], *source_sections]
    return b"".join(sections)


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "WIRE",
        "VSOURCE",
        "CSOURCE",
        "RESISTOR",
        "REALIND",
        "CAPACITOR",
        "CAP10",
        "COMPONENT ID",
        "COMPONENT VALUE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _build_dsn_with_devices(base_dsn: bytes, donor_dsn: bytes, object_chunk: bytes, devices: bytes) -> tuple[bytes, dict[str, int]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise RuntimeError("Base or donor ROOT.DSN does not match the known section model.")
    insert += len(marker)

    dev = bytearray(devices)
    first_header = donor_dsn[donor_first : donor_obj + len(b"OBJECT DATA")]
    tail = bytearray(base_dsn[e0_second:])
    first_isis = insert + len(dev)
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b"OBJECT DATA")
    object_data_pointer = second_obj + 13
    if len(dev) >= 4:
        dev[-4:] = rv9._u32(object_data_pointer)
    cct = tail.find(b"CCT000")
    if cct != -1:
        tail[cct + len(b"CCT000") + 2 : cct + len(b"CCT000") + 6] = rv9._u32(first_isis)
    default = tail.find(b"__DEFAULT__\x00\x00")
    if default != -1:
        tail[default + len(b"__DEFAULT__\x00\x00") : default + len(b"__DEFAULT__\x00\x00") + 4] = rv9._u32(second_isis)
    dsn = bytes(bytearray(base_dsn[:insert]) + dev + first_header + bytearray(object_chunk) + tail)
    return dsn, {
        "insert": insert,
        "first_isis": first_isis,
        "second_isis": second_isis,
        "second_object_data": second_obj,
        "object_data_pointer": object_data_pointer,
    }


def _patch_wire(record: bytes, dx: int, dy: int, *, final: bool) -> bytes:
    out = bytearray(record)
    marker = out.find(b"WIRE")
    if marker < 0:
        raise RuntimeError("WIRE marker not found in source donor wire.")
    coord = marker + 9
    for offset, delta in ((coord, dx), (coord + 4, dy), (coord + 8, dx), (coord + 12, dy)):
        value = int.from_bytes(out[offset : offset + 4], "little", signed=True)
        out[offset : offset + 4] = rv9._i32(value + delta)
    out[-1] = 0xFF if final else 0x00
    return bytes(out)


def _patch_source_record(
    record: bytes,
    spec: SourceSpec,
    dx: int,
    dy: int,
    *,
    old_in_suffix: bytes,
    new_in_suffix: bytes,
    old_out_suffix: bytes,
    new_out_suffix: bytes,
) -> bytes:
    out = bytearray(record)
    raw_ref = spec.ref.encode("ascii")
    raw_value = spec.value.encode("ascii")
    if len(raw_ref) != out[2]:
        raise RuntimeError(f"Source ref {spec.ref!r} does not fit donor ref field.")
    if len(raw_value) != out[70]:
        raise RuntimeError(f"Source value {spec.value!r} does not fit donor value field.")

    out[3 : 3 + len(raw_ref)] = raw_ref
    out[71 : 71 + len(raw_value)] = raw_value

    value_coord = 71 + len(raw_value)
    for offset, delta in ((5, dx), (9, dy), (value_coord, dx), (value_coord + 4, dy)):
        value = int.from_bytes(out[offset : offset + 4], "little", signed=True)
        out[offset : offset + 4] = rv9._i32(value + delta)

    model_pos = out.rfind(spec.model.encode("ascii"))
    if model_pos < 0:
        raise RuntimeError(f"{spec.model} model string not found in source record.")
    body_coord = model_pos + len(spec.model)
    out[body_coord : body_coord + 4] = rv9._i32(spec.x)
    out[body_coord + 4 : body_coord + 8] = rv9._i32(spec.y)
    out[body_coord + 8 : body_coord + 12] = rv9._i32(0)
    out[body_coord + 12 : body_coord + 16] = rv9._u32(spec.idx)

    data = bytes(out)
    data = data.replace(old_in_suffix, new_in_suffix, 1)
    data = data.replace(old_out_suffix, new_out_suffix, 1)
    out = bytearray(data)
    out[-1] = 0x00
    return bytes(out)


def _split_source_template(kind: SourceKind, value_len: int) -> tuple[bytes, bytes, bytes, bytes, bytes, str]:
    if kind == "dc_voltage":
        if value_len != 3:
            raise RuntimeError("Temporary DC voltage source support uses three-character visible values.")
        chunk = _object_chunk(DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj")
        body = chunk[1:]
        return body[:104], body[104:207], body[207:551], body[551:601], body[601:651], "voltage"

    if value_len == 2:
        chunk = _object_chunk(DONOR_ROOT / "dc_current_01_default.pdsprj")
        body = chunk[1:]
        return body[103:207], body[:103], body[207:552], body[552:602], body[602:652], "current"

    if value_len == 5:
        chunk = _object_chunk(DONOR_ROOT / "dc_current_03_resistor_load.pdsprj")
        wire1_start = chunk.find(b"WIRE") - 24
        source_start = 1 + 103 + 104
        return (
            chunk[1 + 103 : 1 + 103 + 104],
            chunk[1 : 1 + 103],
            chunk[source_start:wire1_start],
            chunk[wire1_start : wire1_start + 50],
            chunk[wire1_start + 50 : wire1_start + 100],
            "current",
        )

    raise RuntimeError(f"Temporary source support has no {kind} template for value length {value_len}.")


def _source_unit(spec: SourceSpec, unit_index: int, *, final: bool) -> bytes:
    output_template, input_template, source_template, wire1_template, wire2_template, _ = _split_source_template(
        spec.kind, len(spec.value)
    )
    model = spec.model.encode("ascii")
    model_pos = source_template.rfind(model)
    old_x = int.from_bytes(source_template[model_pos + len(model) : model_pos + len(model) + 4], "little", signed=True)
    old_y = int.from_bytes(source_template[model_pos + len(model) + 4 : model_pos + len(model) + 8], "little", signed=True)
    dx = spec.x - old_x
    dy = spec.y - old_y

    output_symbol_x = int.from_bytes(output_template[1:5], "little", signed=True) + dx
    output_symbol_y = int.from_bytes(output_template[5:9], "little", signed=True) + dy
    output_label_x = int.from_bytes(output_template[34:38], "little", signed=True) + dx
    output_label_y = int.from_bytes(output_template[38:42], "little", signed=True) + dy
    input_symbol_x = int.from_bytes(input_template[1:5], "little", signed=True) + dx
    input_symbol_y = int.from_bytes(input_template[5:9], "little", signed=True) + dy
    input_label_x = int.from_bytes(input_template[33:37], "little", signed=True) + dx
    input_label_y = int.from_bytes(input_template[37:41], "little", signed=True) + dy

    patched_output, out_suffix = rv9._patch_output(
        output_template,
        spec.positive,
        output_symbol_x,
        output_symbol_y,
        output_label_x,
        output_label_y,
        100 + unit_index,
    )
    patched_input, in_suffix = rv9._patch_input(
        input_template,
        spec.negative,
        input_symbol_x,
        input_symbol_y,
        input_label_x,
        input_label_y,
        100 + unit_index,
    )

    source_record = _patch_source_record(
        source_template,
        spec,
        dx,
        dy,
        old_in_suffix=input_template[-4:-2],
        new_in_suffix=rv9._u16(in_suffix),
        old_out_suffix=output_template[-4:-2],
        new_out_suffix=rv9._u16(out_suffix),
    )
    wire1 = _patch_wire(wire1_template, dx, dy, final=False)
    wire2 = _patch_wire(wire2_template, dx, dy, final=final)
    return patched_output + patched_input + source_record + wire1 + wire2


def _without_power_bridge(chunk: bytes) -> bytes:
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE
    if chunk[0] != 0 or chunk[1:bridge_end].count(b"$TERPOWER") != 1:
        raise RuntimeError("Unexpected RCL object chunk bridge shape.")
    return chunk[bridge_end:]


def _rcl_ir(name: str, groups: list[tuple[str, str, str]], values: dict[str, str] | None = None) -> MixedRclCircuitIR:
    return MixedRclCircuitIR(
        schema_version=rcl.SCHEMA_VERSION,
        generator_target=rcl.GENERATOR_TARGET,
        name=name,
        output_basename=name,
        groups=tuple(MixedRclGroup(mode=mode, start=start, end=end) for mode, start, end in groups),
        component_values=values or {},
        metadata={},
    )


def _build_cdb(rcl_specs: list[rcl.RclSpec], source_specs: list[SourceSpec], source_position: SourcePosition) -> bytes:
    # This must match the DSN stream exactly. V4 tests source-before and
    # source-after variants, so CDB order follows that choice.
    ordered = [*source_specs, *rcl_specs] if source_position == "before_rcl" else [*rcl_specs, *source_specs]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + _enc_str(spec.ref)
        if getattr(spec, "kind", "") == "CAPACITOR":
            out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, SourceSpec):
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str(spec.model) + _enc_str("") + _enc_text(spec.prop_text)
        elif spec.kind == "CAPACITOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(rcl.INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _component_payload(
    rcl_specs: list[rcl.RclSpec],
    source_specs: list[SourceSpec],
    source_position: SourcePosition,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for spec in source_specs:
        items.append(
            {
                "idx": spec.idx,
                "ref": spec.ref,
                "type": "DC_VOLTAGE_SOURCE" if spec.kind == "dc_voltage" else "DC_CURRENT_SOURCE",
                "value": spec.value,
                "nodes": [spec.positive, spec.negative],
                "visual": {"x": spec.x, "y": spec.y},
            }
        )
    rcl_items = rcl._component_payload(rcl_specs)
    return [*items, *rcl_items] if source_position == "before_rcl" else [*rcl_items, *items]


def _write_repack_case(case_id: str, description: str, source_project: Path, *, test_order: int) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    project_xml = patch_project_xml_version(read_internal_file(source_project, "PROJECT.XML"), PROTEUS_813)
    dsn = patch_root_dsn_version(read_internal_file(source_project, "ROOT.DSN"), PROTEUS_813)
    cdb = read_internal_file(source_project, "ROOT.CDB")
    chunk = rv9._extract_object_chunk(dsn)
    output_path = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(source_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    manifest = {
        "case_id": case_id,
        "description": description,
        "test_order": test_order,
        "control_type": "exact_repack",
        "status": "temporary_dc_source_v3_control",
        "source_project": str(source_project.relative_to(EXPERIMENT_ROOT)),
        "output": str(output_path.relative_to(EXPERIMENT_ROOT)),
        "marker_counts": _marker_counts(chunk),
        "object_chunk_len": len(chunk),
        "root_cdb_len": len(cdb),
        "static_validation_issues": [],
        "hashes": {
            output_path.name: _sha256_file(output_path),
            "object_chunk": _sha256_bytes(chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "ROOT.DSN": _sha256_bytes(dsn),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Project: {output_path.name}\n"
        "Exact donor repack control. Test this before generated source cases.\n",
        encoding="utf-8",
    )
    return manifest


def _write_transplant_control(
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    *,
    test_order: int,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    chunk = rv9._extract_object_chunk(read_internal_file(donor_project, "ROOT.DSN"))
    cdb = read_internal_file(donor_project, "ROOT.CDB")
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_project, "ROOT.DSN"), chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    issues: list[str] = []
    if rv9._extract_object_chunk(dsn) != chunk:
        issues.append("ROOT.DSN object chunk differs from donor chunk")
    manifest = {
        "case_id": case_id,
        "description": description,
        "test_order": test_order,
        "control_type": "donor_chunk_and_cdb_in_e001",
        "status": "temporary_dc_source_v3_control",
        "source_project": str(donor_project.relative_to(EXPERIMENT_ROOT)),
        "base_project": str(base_project.relative_to(REPO_ROOT)),
        "output": str(output_path.relative_to(EXPERIMENT_ROOT)),
        "marker_counts": _marker_counts(chunk),
        "section_pointer_values": pointers,
        "object_chunk_len": len(chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "static_validation_issues": issues,
        "hashes": {
            output_path.name: _sha256_file(output_path),
            "object_chunk": _sha256_bytes(chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "ROOT.DSN": _sha256_bytes(dsn),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Project: {output_path.name}\n"
        "Exact donor object chunk and CDB transplanted into E001. Test this before generated source cases.\n",
        encoding="utf-8",
    )
    return manifest


def _write_normal_rcl_control(
    case_id: str,
    description: str,
    groups: list[tuple[str, str, str]],
    *,
    test_order: int,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    registry = FixtureRegistry.load()
    ir = _rcl_ir(case_id, groups)
    result = rcl.generate_mixed_rcl_project(ir, case_dir, registry=registry)
    manifest = dict(result.manifest)
    manifest.update(
        {
            "case_id": case_id,
            "description": description,
            "test_order": test_order,
            "control_type": "normal_main_mixed_rcl_generation",
            "status": "temporary_dc_source_v4_control",
            "output": str(result.output_path.relative_to(EXPERIMENT_ROOT)),
        }
    )
    result.manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    result.readme_path.write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Project: {result.output_path.name}\n"
        "Normal locked R/C/L output with V0 power bridge and G0 ground endpoints. Test before source-added variants.\n",
        encoding="utf-8",
    )
    return manifest


def _generate_case(
    *,
    case_id: str,
    description: str,
    groups: list[tuple[str, str, str]],
    sources: list[SourceSpec],
    source_position: SourcePosition,
    power_bridge_policy: PowerBridgePolicy,
    values: dict[str, str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    rcl_donor = registry.get("rcl_4x_t07_unit_donor")
    templates = rcl._load_rcl_unit_templates(rcl_donor.path)
    ir = _rcl_ir(case_id, groups, values)
    rcl_chunk_with_bridge, rcl_specs, topology, rcl_counts = rcl.build_object_chunk(ir, templates)
    if power_bridge_policy == "keep_normal_power_ground":
        rcl_body = rcl_chunk_with_bridge[1:]
    else:
        rcl_body = _without_power_bridge(rcl_chunk_with_bridge)

    if source_position == "before_rcl":
        source_chunks = [_source_unit(spec, index, final=False) for index, spec in enumerate(sources, start=1)]
        object_chunk = bytearray(b"\x00" + b"".join(source_chunks) + rcl_body)
        object_chunk[-1] = 0xFF
    else:
        object_chunk = bytearray(b"\x00" + rcl_body)
        object_chunk[-1] = 0x00
        source_chunks = [
            _source_unit(spec, index, final=index == len(sources))
            for index, spec in enumerate(sources, start=1)
        ]
        object_chunk.extend(b"".join(source_chunks))

    source_kinds = {spec.kind for spec in sources}
    devices = _combined_device_section(source_kinds, rcl_donor.path, source_position)
    dsn, section_pointers = _build_dsn_with_devices(
        read_internal_file(base.path, "ROOT.DSN"),
        read_internal_file(rcl_donor.path, "ROOT.DSN"),
        bytes(object_chunk),
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    cdb = _build_cdb(rcl_specs, sources, source_position)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)

    out_dir = OUT_ROOT / case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{case_id}.pdsprj"
    cdb_path = out_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = out_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = out_dir / f"{case_id}.OBJECT_CHUNK.bin"
    input_path = out_dir / "input.json"
    manifest_path = out_dir / "manifest.json"
    readme_path = out_dir / "README_TEST_FIRST.txt"

    write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(bytes(object_chunk))

    input_payload = {
        "case_id": case_id,
        "description": description,
        "source_experiment_schema": "dc-source-rcl-temp/v0.4",
        "sources": [
            {
                "kind": spec.kind,
                "ref": spec.ref,
                "value": spec.value,
                "positive": spec.positive,
                "negative": spec.negative,
            }
            for spec in sources
        ],
        "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
        "component_values": values or {},
        "metadata": {
            "source_position": source_position,
            "power_bridge_policy": power_bridge_policy,
            **(extra_metadata or {}),
        },
    }
    input_path.write_text(json.dumps(input_payload, indent=2), encoding="utf-8")

    markers = {
        "$TERINPUT": bytes(object_chunk).count(b"$TERINPUT"),
        "$TEROUTPUT": bytes(object_chunk).count(b"$TEROUTPUT"),
        "$TERGROUND": bytes(object_chunk).count(b"$TERGROUND"),
        "$TERPOWER": bytes(object_chunk).count(b"$TERPOWER"),
        "VSOURCE": bytes(object_chunk).count(b"VSOURCE"),
        "CSOURCE": bytes(object_chunk).count(b"CSOURCE"),
        "RESISTOR": bytes(object_chunk).count(b"RESISTOR"),
        "CAPACITOR": bytes(object_chunk).count(b"CAPACITOR"),
        "REALIND": bytes(object_chunk).count(b"REALIND"),
        "WIRE": bytes(object_chunk).count(b"WIRE"),
    }
    chunk_issues = rcl._scan_wire_issues(bytes(object_chunk))
    if rv9._extract_object_chunk(dsn) != bytes(object_chunk):
        chunk_issues.append("ROOT.DSN object chunk differs from requested chunk")
    if power_bridge_policy == "remove_power_bridge_keep_ground" and markers["$TERPOWER"] != 0:
        chunk_issues.append("source-replaces-power diagnostic should not emit $TERPOWER")

    manifest = {
        "case_id": case_id,
        "description": description,
        "output": str(output_path.relative_to(EXPERIMENT_ROOT)),
        "donor_method": "normal locked mixed RCL V0/G0 groups first; add DC source terminals named V0/G0 by label",
        "cdb_order_rule": f"ROOT.CDB rows are emitted in DSN object order: {source_position}",
        "source_position": source_position,
        "power_bridge_policy": power_bridge_policy,
        "source_terminal_rule": "positive side uses output terminal, negative side uses input terminal",
        "source_terminals_connect_by_label": True,
        "source_specs": input_payload["sources"],
        "rcl_counts": rcl_counts,
        "component_count": len(sources) + len(rcl_specs),
        "components": _component_payload(rcl_specs, sources, source_position),
        "topology": topology,
        "markers": markers,
        "chunk_issues": chunk_issues,
        "section_pointers": section_pointers,
        "hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            chunk_path.name: _sha256_file(chunk_path),
        },
        **(extra_metadata or {}),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    readme_path.write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Project: {output_path.name}\n"
        "Open this file first in Proteus. This is temp-only DC source composition, not main code.\n",
        encoding="utf-8",
    )
    return manifest


def _replace_supply(groups: list[dict[str, str]], positive: str, negative: str) -> list[tuple[str, str, str]]:
    return [
        (item["mode"], positive if item["start"] == "V0" else negative if item["start"] == "G0" else item["start"], positive if item["end"] == "V0" else negative if item["end"] == "G0" else item["end"])
        for item in groups
    ]


def _v(index: int, value: str, positive: str, negative: str, x: int | None = None, y: int | None = None) -> SourceSpec:
    return SourceSpec("dc_voltage", 200 + index, f"V{index}", value, positive, negative, x if x is not None else -10_160_000 + index * 1_778_000, y if y is not None else 2_032_000)


def _i(index: int, value: str, positive: str, negative: str, x: int | None = None, y: int | None = None) -> SourceSpec:
    return SourceSpec("dc_current", 220 + index, f"I{index}", value, positive, negative, x if x is not None else 1_524_000 + index * 1_778_000, y if y is not None else -1_016_000)


def build_cases() -> list[dict[str, Any]]:
    dcv = DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj"
    dci = DONOR_ROOT / "dc_current_01_default.pdsprj"
    six = _replace_supply(rcl_examples.mixed_rcl_6_case()["groups"], "V0", "G0")
    twenty_one = _replace_supply(rcl_examples.mixed_rcl_21_case()["groups"], "V0", "G0")
    cases: list[dict[str, Any]] = []
    cases.append(
        _write_normal_rcl_control(
            "DCS_V4_T00A_NORMAL_RCL_6_BASELINE",
            "Normal locked main R/C/L 6-component baseline with V0 power bridge and G0 ground endpoints.",
            six,
            test_order=1,
        )
    )
    cases.append(
        _write_repack_case(
            "DCS_V4_T00B_DCV_EXACT_DONOR_REPACK",
            "Exact DC voltage source donor repack control.",
            dcv,
            test_order=2,
        )
    )
    cases.append(
        _write_repack_case(
            "DCS_V4_T00C_DCI_EXACT_DONOR_REPACK",
            "Exact DC current source donor repack control.",
            dci,
            test_order=3,
        )
    )

    cases.append(
        _generate_case(
            case_id="DCS_V4_T01_DCV_6_RCL_FIRST_KEEP_POWER_GROUND",
            description="Normal 6-component R/C/L object stream first, then a 10V DC source with output V0 and input G0; keep normal V0 power bridge and G0 ground endpoints.",
            groups=six,
            sources=[_v(1, "10V", "V0", "G0")],
            source_position="after_rcl",
            power_bridge_policy="keep_normal_power_ground",
            extra_metadata={"test_order": 4, "requested_method": "produce normal RCL, then add source by same labels"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V4_T02_DCV_6_SOURCE_FIRST_KEEP_POWER_GROUND",
            description="10V DC source first with output V0/input G0, then normal 6-component R/C/L stream; keep normal V0 power bridge and G0 ground endpoints.",
            groups=six,
            sources=[_v(1, "10V", "V0", "G0")],
            source_position="before_rcl",
            power_bridge_policy="keep_normal_power_ground",
            extra_metadata={"test_order": 5, "requested_method": "same labels with normal RCL supply shape"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V4_T03_DCV_6_RCL_FIRST_REPLACE_POWER",
            description="Normal 6-component R/C/L stream with V0 power bridge removed but G0 endpoints kept; add 10V DC source after R/C/L using output V0 and input G0.",
            groups=six,
            sources=[_v(1, "10V", "V0", "G0")],
            source_position="after_rcl",
            power_bridge_policy="remove_power_bridge_keep_ground",
            extra_metadata={"test_order": 6, "requested_method": "source replaces power bridge, same labels"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V4_T04_DCV_6_SOURCE_FIRST_REPLACE_POWER",
            description="10V DC source first using output V0/input G0, then 6-component R/C/L stream with V0 power bridge removed and G0 endpoints kept.",
            groups=six,
            sources=[_v(1, "10V", "V0", "G0")],
            source_position="before_rcl",
            power_bridge_policy="remove_power_bridge_keep_ground",
            extra_metadata={"test_order": 7, "requested_method": "source replaces power bridge, same labels"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V4_T05_DCI_6_RCL_FIRST_REPLACE_POWER",
            description="Normal 6-component R/C/L stream with V0 power bridge removed and G0 endpoints kept; add 1A DC current source after R/C/L using output V0 and input G0.",
            groups=six,
            sources=[_i(1, "1A", "V0", "G0")],
            source_position="after_rcl",
            power_bridge_policy="remove_power_bridge_keep_ground",
            extra_metadata={"test_order": 8, "requested_method": "current source replaces power bridge, same labels"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V4_T06_DCI_6_SOURCE_FIRST_REPLACE_POWER",
            description="1A DC current source first using output V0/input G0, then 6-component R/C/L stream with V0 power bridge removed and G0 endpoints kept.",
            groups=six,
            sources=[_i(1, "1A", "V0", "G0")],
            source_position="before_rcl",
            power_bridge_policy="remove_power_bridge_keep_ground",
            extra_metadata={"test_order": 9, "requested_method": "current source replaces power bridge, same labels"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V4_T07_DCV_21_RCL_FIRST_REPLACE_POWER",
            description="Correct 21-component R/C/L topology in normal V0/G0 labels with V0 bridge removed; add 10V DC source after R/C/L using output V0 and input G0.",
            groups=twenty_one,
            sources=[_v(1, "10V", "V0", "G0")],
            source_position="after_rcl",
            power_bridge_policy="remove_power_bridge_keep_ground",
            extra_metadata={"test_order": 10, "requested_batch": "21 component DC voltage source"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V4_T08_DCI_21_RCL_FIRST_REPLACE_POWER",
            description="Correct 21-component R/C/L topology in normal V0/G0 labels with V0 bridge removed; add 1A DC current source after R/C/L using output V0 and input G0.",
            groups=twenty_one,
            sources=[_i(1, "1A", "V0", "G0")],
            source_position="after_rcl",
            power_bridge_policy="remove_power_bridge_keep_ground",
            extra_metadata={"test_order": 11, "requested_batch": "21 component DC current source"},
        )
    )
    return cases


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    cases = build_cases()
    batch = {
        "batch_id": "DC_SOURCES_V4_ADD_TO_NORMAL_RCL_TEMP_20260603",
        "status": "temp_experimental_not_main",
        "description": "Normal locked V0/G0 mixed RCL generated first, then DC source terminals named V0/G0 are added by label.",
        "test_order": [case["case_id"] for case in cases],
        "case_count": len(cases),
        "cases": cases,
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(batch, indent=2), encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "\n".join(f"{i + 1}. {case['case_id']}/{case['case_id']}.pdsprj" for i, case in enumerate(cases)) + "\n",
        encoding="utf-8",
    )
    archive = shutil.make_archive(str(EXPERIMENT_ROOT / "DC_SOURCES_V4_ADD_TO_NORMAL_RCL_TEMP_2026_06_03"), "zip", OUT_ROOT)
    print(json.dumps({"generated": len(cases), "out": str(OUT_ROOT), "archive": archive}, indent=2))


if __name__ == "__main__":
    main()
