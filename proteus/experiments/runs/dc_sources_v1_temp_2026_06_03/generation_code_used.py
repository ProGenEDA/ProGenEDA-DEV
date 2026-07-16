"""Temporary DC voltage/current source composition experiment.

This is deliberately not promoted into src/proteusgen. It composes the
user-supplied DC voltage and DC current terminal donors with the already locked
mixed R/C/L group renderer so the generated files can be manually opened in
Proteus before any main-generator work.
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
OUT_ROOT = EXPERIMENT_ROOT / "DC_SOURCES_V1_TEST_BATCH"

SourceKind = Literal["dc_voltage", "dc_current"]


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
        return b"{PRIMITIVE=ANALOG}\n" if self.kind == "dc_voltage" else b"{PRIMITIVE=ANALOGUE}\n"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return rv9._u32(len(raw)) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(len(value)) + value


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


def _combined_device_section(source_kinds: set[SourceKind], rcl_donor: Path) -> bytes:
    sections: list[bytes] = []
    if "dc_voltage" in source_kinds:
        sections.append(_device_section(DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj")[:-4])
    if "dc_current" in source_kinds:
        sections.append(_device_section(DONOR_ROOT / "dc_current_01_default.pdsprj")[:-4])
    sections.append(_device_section(rcl_donor))
    return b"".join(sections)


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


def _build_cdb(rcl_specs: list[rcl.RclSpec], source_specs: list[SourceSpec]) -> bytes:
    all_specs = [*rcl_specs, *source_specs]
    ordered = sorted(all_specs, key=lambda item: item.idx)
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


def _component_payload(rcl_specs: list[rcl.RclSpec], source_specs: list[SourceSpec]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for spec in sorted(source_specs, key=lambda item: item.idx):
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
    items.extend(rcl._component_payload(rcl_specs))
    return sorted(items, key=lambda item: item["idx"])


def _generate_case(
    *,
    case_id: str,
    description: str,
    groups: list[tuple[str, str, str]],
    sources: list[SourceSpec],
    values: dict[str, str] | None = None,
    extra_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    rcl_donor = registry.get("rcl_4x_t07_unit_donor")
    templates = rcl._load_rcl_unit_templates(rcl_donor.path)
    ir = _rcl_ir(case_id, groups, values)
    rcl_chunk_with_bridge, rcl_specs, topology, rcl_counts = rcl.build_object_chunk(ir, templates)
    rcl_chunk = _without_power_bridge(rcl_chunk_with_bridge)

    source_chunks = [
        _source_unit(spec, index, final=False)
        for index, spec in enumerate(sources, start=1)
    ]
    object_chunk = bytearray(b"\x00" + b"".join(source_chunks) + rcl_chunk)
    object_chunk[-1] = 0xFF

    source_kinds = {spec.kind for spec in sources}
    devices = _combined_device_section(source_kinds, rcl_donor.path)
    dsn, section_pointers = _build_dsn_with_devices(
        read_internal_file(base.path, "ROOT.DSN"),
        read_internal_file(rcl_donor.path, "ROOT.DSN"),
        bytes(object_chunk),
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    cdb = _build_cdb(rcl_specs, sources)
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
        "source_experiment_schema": "dc-source-rcl-temp/v0.1",
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
        "metadata": extra_metadata or {},
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
    if markers["$TERPOWER"] != 0:
        chunk_issues.append("source experiment should not emit $TERPOWER")

    manifest = {
        "case_id": case_id,
        "description": description,
        "output": str(output_path.relative_to(EXPERIMENT_ROOT)),
        "donor_method": "prepend patched DC source units, then locked mixed RCL groups with V0 bridge removed",
        "source_terminal_rule": "positive side uses output terminal, negative side uses input terminal",
        "source_terminals_connect_by_label": True,
        "source_specs": input_payload["sources"],
        "rcl_counts": rcl_counts,
        "component_count": len(sources) + len(rcl_specs),
        "components": _component_payload(rcl_specs, sources),
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
    six = rcl_examples.mixed_rcl_6_case()["groups"]
    twenty_one = rcl_examples.mixed_rcl_21_case()["groups"]
    cases: list[dict[str, Any]] = []
    cases.append(
        _generate_case(
            case_id="DCS_V1_T01_DCV_6_COMPONENTS",
            description="Six mixed R/C/L components connected across a default 10V DC voltage source terminal pair DV/D0.",
            groups=_replace_supply(six, "DV", "D0"),
            sources=[_v(1, "10V", "DV", "D0")],
            extra_metadata={"test_order": 1, "requested_batch": "6 component DC voltage source"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V1_T02_DCV_21_COMPONENTS",
            description="Correct 21-component mixed R/C/L topology driven by a default 10V DC voltage source terminal pair DV/D0.",
            groups=_replace_supply(twenty_one, "DV", "D0"),
            sources=[_v(1, "10V", "DV", "D0")],
            extra_metadata={"test_order": 2, "requested_batch": "21 component DC voltage source"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V1_T03_DCI_6_COMPONENTS",
            description="Six mixed R/C/L components connected across a default 1A DC current source terminal pair DI/I0.",
            groups=_replace_supply(six, "DI", "I0"),
            sources=[_i(1, "1A", "DI", "I0")],
            extra_metadata={"test_order": 3, "requested_batch": "6 component DC current source"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V1_T04_DCI_21_COMPONENTS",
            description="Correct 21-component mixed R/C/L topology driven by a default 1A DC current source terminal pair DI/I0.",
            groups=_replace_supply(twenty_one, "DI", "I0"),
            sources=[_i(1, "1A", "DI", "I0")],
            extra_metadata={"test_order": 4, "requested_batch": "21 component DC current source"},
        )
    )

    cases.append(
        _generate_case(
            case_id="DCS_V1_T05_COMPLEX_RLC_01",
            description="Pasted circuit 1: 12V source at A1/G0, 2A current source at D1/G0, mixed branch network.",
            groups=[
                ("R", "A1", "B1"),
                ("C", "B1", "G0"),
                ("L", "B1", "C1"),
                ("R", "C1", "G0"),
                ("L", "C1", "D1"),
                ("C", "D1", "N1"),
                ("R", "N1", "G0"),
            ],
            sources=[_v(1, "12V", "A1", "G0"), _i(1, "2A", "D1", "G0")],
            values={"R1": "1k0", "C1": "10u", "L1": "100", "R2": "470", "L2": "220", "C2": "22u", "R3": "100"},
            extra_metadata={"test_order": 5, "source_text": "Circuit 1 from pasted request"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V1_T06_COMPLEX_RLC_02",
            description="Pasted circuit 2: two 5V voltage sources and one 1A current source with three branches.",
            groups=[
                ("R", "A1", "B1"),
                ("C", "B1", "G0"),
                ("C", "B1", "N1"),
                ("R", "N1", "G0"),
                ("L", "B1", "C1"),
                ("L", "C1", "G0"),
                ("R", "C1", "D1"),
                ("C", "D1", "G0"),
            ],
            sources=[_v(1, "05V", "A1", "G0"), _v(2, "05V", "D1", "G0"), _i(1, "1A", "D1", "G0")],
            values={"R1": "050", "C1": "47u", "C2": "10u", "R2": "220", "L1": "50m", "L2": "150", "R3": "330", "C3": "100"},
            extra_metadata={"test_order": 6, "source_text": "Circuit 2 from pasted request"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V1_T07_COMPLEX_RLC_03",
            description="Pasted circuit 3: 24V source and two 0.5A current sources in a branched RLC network.",
            groups=[
                ("R", "A1", "N1"),
                ("L", "N1", "B1"),
                ("C", "B1", "G0"),
                ("L", "B1", "C1"),
                ("R", "C1", "G0"),
                ("C", "C1", "D1"),
                ("R", "D1", "N2"),
                ("L", "N2", "G0"),
            ],
            sources=[_v(1, "24V", "A1", "G0"), _i(1, "500mA", "C1", "G0"), _i(2, "500mA", "D1", "G0")],
            values={"R1": "150", "L1": "82m", "C1": "4u7", "L2": "1H0", "R2": "500", "C2": "2u2", "R3": "1k0", "L3": "470"},
            extra_metadata={"test_order": 7, "source_text": "Circuit 3 from pasted request"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V1_T08_COMPLEX_RLC_04",
            description="Pasted circuit 4: two 15V voltage sources and two 3A current sources.",
            groups=[
                ("R", "A1", "B1"),
                ("L", "B1", "N1"),
                ("R", "N1", "G0"),
                ("C", "B1", "C1"),
                ("C", "C1", "G0"),
                ("L", "C1", "D1"),
                ("R", "D1", "G0"),
                ("C", "D1", "E1"),
            ],
            sources=[_v(1, "15V", "A1", "G0"), _v(2, "15V", "E1", "G0"), _i(1, "3A", "C1", "G0"), _i(2, "3A", "E1", "G0")],
            values={"R1": "010", "L1": "330", "R2": "047", "C1": "10u", "C2": "22u", "L2": "100", "R3": "220", "C3": "4u7"},
            extra_metadata={"test_order": 8, "source_text": "Circuit 4 from pasted request"},
        )
    )
    cases.append(
        _generate_case(
            case_id="DCS_V1_T09_COMPLEX_RLC_05",
            description="Pasted circuit 5: three 9V voltage sources and one 1.5A current source.",
            groups=[
                ("L", "A1", "B1"),
                ("C", "B1", "G0"),
                ("R", "B1", "C1"),
                ("L", "C1", "N1"),
                ("C", "N1", "G0"),
                ("R", "C1", "D1"),
                ("C", "D1", "G0"),
            ],
            sources=[_v(1, "09V", "A1", "G0"), _v(2, "09V", "B1", "G0"), _v(3, "09V", "D1", "G0"), _i(1, "1500m", "D1", "G0")],
            values={"L1": "150", "C1": "10u", "R1": "100", "L2": "470", "C2": "22u", "R2": "470", "C3": "1u0"},
            extra_metadata={"test_order": 9, "source_text": "Circuit 5 from pasted request"},
        )
    )
    return cases


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    cases = build_cases()
    batch = {
        "batch_id": "DC_SOURCES_V1_TEMP_20260603",
        "status": "temp_experimental_not_main",
        "description": "DC voltage/current source donors composed with locked mixed RCL groups.",
        "test_order": [case["case_id"] for case in cases],
        "case_count": len(cases),
        "cases": cases,
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(batch, indent=2), encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "\n".join(f"{i + 1}. {case['case_id']}/{case['case_id']}.pdsprj" for i, case in enumerate(cases)) + "\n",
        encoding="utf-8",
    )
    archive = shutil.make_archive(str(EXPERIMENT_ROOT / "DC_SOURCES_V1_TEMP_2026_06_03"), "zip", OUT_ROOT)
    print(json.dumps({"generated": len(cases), "out": str(OUT_ROOT), "archive": archive}, indent=2))


if __name__ == "__main__":
    main()
