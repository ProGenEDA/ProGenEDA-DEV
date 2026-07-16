"""Generate DC-voltage source + mixed R/C/L source-net diagnostics.

This is temp-only source work. It uses the locked mixed R/C/L generator from
``src/proteusgen/mixed_rcl.py`` for passive component bodies, then tests the
source-driven net model observed in the user-made combined donor:

* DC-voltage positive net: ``DV``
* DC-voltage negative net: ``D0``
* no ``$TERPOWER`` records
* no ``$TERGROUND`` records
* source positive side is an output terminal
* source negative side is an input terminal

Do not promote this file into main code until the Proteus open/netlist results
identify which source-insertion order is safe.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_rcl as rcl  # noqa: E402
from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import MixedRclCircuitIR, MixedRclGroup  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_sources_v5_source_net_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_SOURCES_V5_SOURCE_NET_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"

USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
USER_COMBINED_DONOR = Path(r"C:\Users\tahab\Downloads\testing.pdsprj")

SourcePosition = Literal["before_rcl", "after_rcl"]


@dataclass(frozen=True)
class SourceSpec:
    idx: int
    ref: str
    value: str
    positive: str
    negative: str
    x: int
    y: int

    @property
    def model(self) -> str:
        return "VSOURCE"

    @property
    def prop_text(self) -> bytes:
        return b"{PRIMITIVE=ANALOG}\n\x00"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(4 + len(value)) + value


def _object_chunk(project_path: Path) -> bytes:
    return rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))


def _device_section_from_dsn(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise RuntimeError("ROOT.DSN does not match the known device-section model.")
    insert += len(marker)
    return dsn[insert:first]


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


def _split_voltage_source_template() -> tuple[bytes, bytes, bytes, bytes, bytes]:
    chunk = _object_chunk(DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj")
    body = chunk[1:]
    return body[:104], body[104:207], body[207:551], body[551:601], body[601:651]


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
        raise RuntimeError("VSOURCE model string not found in source record.")
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


def _source_unit(spec: SourceSpec, *, final: bool) -> bytes:
    output_template, input_template, source_template, wire1_template, wire2_template = _split_voltage_source_template()
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
        101,
    )
    patched_input, in_suffix = rv9._patch_input(
        input_template,
        spec.negative,
        input_symbol_x,
        input_symbol_y,
        input_label_x,
        input_label_y,
        101,
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
    return (
        patched_output
        + patched_input
        + source_record
        + _patch_wire(wire1_template, dx, dy, final=False)
        + _patch_wire(wire2_template, dx, dy, final=final)
    )


def _source_net_rcl(
    templates: rcl.RclUnitTemplates,
    groups: list[tuple[str, str, str]],
) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, Any]], dict[str, Any]]:
    ir = MixedRclCircuitIR(
        schema_version=rcl.SCHEMA_VERSION,
        generator_target=rcl.GENERATOR_TARGET,
        name="DCS_V5_SOURCE_NET_RCL",
        output_basename="DCS_V5_SOURCE_NET_RCL",
        groups=tuple(MixedRclGroup(mode=mode, start=start, end=end) for mode, start, end in groups),
        component_values={},
        metadata={},
    )
    chunk_with_bridge, specs, topology, counts = rcl.build_object_chunk(ir, templates)
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE
    if chunk_with_bridge[0] != 0 or chunk_with_bridge[1:bridge_end].count(b"$TERPOWER") != 1:
        raise RuntimeError("Accepted RCL chunk does not have the expected leading power bridge.")
    body = bytearray(chunk_with_bridge[bridge_end:])
    if body.count(b"$TERPOWER") or body.count(b"$TERGROUND"):
        raise RuntimeError("Source-net RCL body must not contain power/ground terminal records.")
    body[-1] = 0xFF
    counts = {**counts, "power_bridge_count": 0, "source_net_positive": "DV", "source_net_negative": "D0"}
    return bytes(b"\x00" + body), specs, topology, counts


def _build_cdb(rcl_specs: list[rcl.RclSpec], source_specs: list[SourceSpec], source_position: SourcePosition) -> bytes:
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
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(rcl.INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "VSOURCE",
        "CSOURCE",
        "CAPACITOR",
        "REALIND",
        "RESISTOR",
        "WIRE",
        "COMPONENT ID",
        "COMPONENT VALUE",
        "CAP10",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _write_case(
    case_id: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes | None = None,
    input_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / "DC_SOURCES_V5_SOURCE_NET_TEST_BATCH" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    base_dsn = read_internal_file(base_project, "ROOT.DSN")
    donor_dsn = read_internal_file(donor_project, "ROOT.DSN")
    device_section = devices if devices is not None else _device_section_from_dsn(donor_dsn)
    dsn, pointers = _build_dsn_with_devices(base_dsn, donor_dsn, object_chunk, device_section)
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

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_source_v5_source_net_not_locked",
        "output": str(output_path.relative_to(OUT_ROOT)),
        "base_project": str(base_project),
        "donor_project": str(donor_project),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            chunk_path.name: _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
        },
    }
    if input_payload:
        (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")
        manifest["input"] = input_payload
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "manual_combined_testing": USER_COMBINED_DONOR,
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


def _manual_label_mutation(chunk: bytes) -> bytes:
    # Narrow, length-preserving diagnostic: only two-character terminal labels.
    out = bytearray(chunk)
    replacements = [(b"\x02DV", b"\x02P0"), (b"\x02D0", b"\x02N0")]
    data = bytes(out)
    for old, new in replacements:
        data = data.replace(old, new)
    return data


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    (OUT_ROOT / "DC_SOURCES_V5_SOURCE_NET_TEST_BATCH").mkdir(parents=True)
    donors = _copy_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = rcl._load_rcl_unit_templates(rcl_donor)

    manual = donors["manual_combined_testing"]
    manual_chunk = _object_chunk(manual)
    manual_cdb = read_internal_file(manual, "ROOT.CDB")
    manual_devices = _device_section_from_dsn(read_internal_file(manual, "ROOT.DSN"))

    groups = [("RCL", "DV", "D0"), ("RC", "DV", "D0"), ("C", "DV", "D0")]
    source_net_chunk, specs, topology, rcl_counts = _source_net_rcl(templates, groups)
    rcl_cdb = rcl.build_cdb(specs)
    source = SourceSpec(idx=7, ref="V1", value="10V", positive="DV", negative="D0", x=-10_160_000, y=2_032_000)
    source_block_nonfinal = _source_unit(source, final=False)
    source_block_final = _source_unit(source, final=True)

    before_chunk = bytearray(b"\x00" + source_block_nonfinal + source_net_chunk[1:])
    before_chunk[-1] = 0xFF
    after_body = bytearray(source_net_chunk[1:])
    after_body[-1] = 0x00
    after_chunk = bytes(b"\x00" + after_body + source_block_final)

    cases: list[dict[str, Any]] = []
    cases.append(
        _write_case(
            "DCS_V5_T00_MANUAL_COMBINED_DONOR_IN_E001",
            "User-made combined DC-voltage + 6-component RCL donor object chunk and CDB transplanted into E001. Expected to open if the E001 transplant path is valid.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=manual_chunk,
            cdb=manual_cdb,
            devices=manual_devices,
        )
    )
    cases.append(
        _write_case(
            "DCS_V5_T01_MANUAL_LABEL_ONLY_P0_N0",
            "Same manual combined object chunk, only terminal labels DV->P0 and D0->N0. Expected to open if source net labels are mutable.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=_manual_label_mutation(manual_chunk),
            cdb=manual_cdb,
            devices=manual_devices,
        )
    )
    cases.append(
        _write_case(
            "DCS_V5_T02_GENERATED_RCL_SOURCE_NET_NO_SOURCE",
            "Current protuesgen locked RCL 6-component body generated with source nets DV/D0, no power bridge, no ground terminal, and no source object.",
            base_project=base_project,
            donor_project=rcl_donor,
            object_chunk=source_net_chunk,
            cdb=rcl_cdb,
            input_payload={
                "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
                "source": None,
                "rcl_counts": rcl_counts,
                "topology": topology,
            },
        )
    )
    cases.append(
        _write_case(
            "DCS_V5_T03_GENERATED_DCV_FIRST_DV_D0",
            "Generated DC source first, followed by current protuesgen locked RCL 6-component source-net body. Tests source-before-RCL object order.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=bytes(before_chunk),
            cdb=_build_cdb(specs, [source], "before_rcl"),
            devices=manual_devices,
            input_payload={
                "source_position": "before_rcl",
                "source": source.__dict__,
                "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
                "rcl_counts": rcl_counts,
                "topology": topology,
            },
        )
    )
    cases.append(
        _write_case(
            "DCS_V5_T04_GENERATED_DCV_LAST_DV_D0",
            "Generated current protuesgen locked RCL 6-component source-net body first, then DC source last. Tests source-after-RCL object order.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=after_chunk,
            cdb=_build_cdb(specs, [source], "after_rcl"),
            devices=manual_devices,
            input_payload={
                "source_position": "after_rcl",
                "source": source.__dict__,
                "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
                "rcl_counts": rcl_counts,
                "topology": topology,
            },
        )
    )

    summary = {
        "batch_id": "DC_SOURCES_V5_SOURCE_NET_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "scope": "DC voltage source only, temp diagnostics based on user-made combined donor and protuesgen locked RCL generator.",
        "key_finding_from_manual_donor": "Use source nets DV/D0 and ordinary input/output terminals; do not keep $TERPOWER or $TERGROUND in source-driven circuits.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item["marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    batch_dir = OUT_ROOT / "DC_SOURCES_V5_SOURCE_NET_TEST_BATCH"
    (batch_dir / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (batch_dir / "README_TEST_ORDER.txt").write_text(
        "DC source V5 source-net diagnostic pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT00/T01 are manual-donor controls. T02 isolates generated source-net RCL without a source. T03/T04 test source first vs source last.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
