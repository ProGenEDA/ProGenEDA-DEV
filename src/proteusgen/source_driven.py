"""Locked source-driven R/C/L generator.

This module promotes the user-confirmed source methods into production:

* one or more DC voltage/current sources use the accepted V15 donor-derived
  source units and the V13 wire-coordinate repair;
* one AC voltage source uses the accepted V2 non-final VSINE unit;
* passive loads use the locked mixed-RCL whole-group renderer.

AC current sources are intentionally unsupported.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .layout import (
    LayoutError,
    LayoutPlan,
    actual_layout_plan,
    apply_layout_to_payload,
    plan_with_actual_positions,
)
from . import mixed_rcl as rcl
from . import resistor_v9 as rv9
from .pdsprj import read_internal_file, write_project_from_parts
from .templates import FixtureRegistry
from .versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

SourceKind = Literal["dc_voltage", "dc_current", "ac_voltage"]

SCHEMA_VERSION = "source-driven-rcl-circuit-ir/v0.1"
GENERATOR_TARGET = "proteus-8.13-source-driven-rcl-locked"
BASE_PROJECT = "E001_EMPTY_BASE"


@dataclass(frozen=True)
class SourcePlan:
    kind: SourceKind
    ref: str
    value: str
    positive: str
    negative: str

    @property
    def model(self) -> str:
        if self.kind == "dc_voltage":
            return "VSOURCE"
        if self.kind == "dc_current":
            return "CSOURCE"
        return "VSINE"

    @property
    def prop_text(self) -> bytes:
        if self.kind == "dc_voltage":
            return b"{PRIMITIVE=ANALOG}\n\x00"
        if self.kind == "dc_current":
            return b"{PRIMITIVE=ANALOGUE}\n\x00"
        raise ValueError("AC voltage property text comes from the accepted donor.")


@dataclass(frozen=True)
class SourceDrivenCircuitIR:
    schema_version: str
    generator_target: str
    name: str
    output_basename: str
    groups: tuple[rcl.MixedRclGroup, ...]
    sources: tuple[SourcePlan, ...]
    component_values: dict[str, str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class SourceDrivenValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    circuit: SourceDrivenCircuitIR | None = None

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "circuit": None
            if self.circuit is None
            else {
                "schema_version": self.circuit.schema_version,
                "generator_target": self.circuit.generator_target,
                "name": self.circuit.name,
                "output_basename": self.circuit.output_basename,
                "groups": [
                    {"mode": item.mode, "start": item.start, "end": item.end}
                    for item in self.circuit.groups
                ],
                "sources": [
                    {
                        "kind": item.kind,
                        "ref": item.ref,
                        "value": item.value,
                        "positive": item.positive,
                        "negative": item.negative,
                    }
                    for item in self.circuit.sources
                ],
                "component_values": self.circuit.component_values,
            },
        }


@dataclass(frozen=True)
class SourceDrivenGenerationResult:
    output_path: Path
    cdb_path: Path
    dsn_path: Path
    chunk_path: Path
    layout_path: Path
    manifest_path: Path
    readme_path: Path
    version_path: Path
    manifest: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "root_cdb_path": str(self.cdb_path),
            "root_dsn_path": str(self.dsn_path),
            "object_chunk_path": str(self.chunk_path),
            "layout_plan_path": str(self.layout_path),
            "manifest_path": str(self.manifest_path),
            "readme_path": str(self.readme_path),
            "generator_version_path": str(self.version_path),
            "static_validation_issues": self.manifest["static_validation_issues"],
            "output_hashes": self.manifest["output_hashes"],
        }


class SourceDrivenGenerationBlocked(Exception):
    def __init__(self, report: SourceDrivenValidationReport) -> None:
        super().__init__("Source-driven CircuitIR cannot be emitted.")
        self.report = report


@dataclass(frozen=True)
class SourceRow:
    idx: int
    ref: str
    value: str
    model: str
    prop_text: bytes
    ac_voltage: bool = False


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _label_is_supported(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 2 and value.isascii()


def parse_source_driven_ir(payload: Any) -> tuple[SourceDrivenCircuitIR | None, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return None, ["Payload must be a JSON object."]

    project = payload.get("project", {})
    if not isinstance(project, dict):
        errors.append("project must be an object.")
        project = {}

    groups_raw = payload.get("groups")
    if not isinstance(groups_raw, list) or not groups_raw:
        errors.append("groups must be a non-empty array.")
        groups_raw = []
    groups: list[rcl.MixedRclGroup] = []
    for index, raw in enumerate(groups_raw, start=1):
        if not isinstance(raw, dict):
            errors.append(f"groups[{index}] must be an object.")
            continue
        mode = raw.get("mode")
        start = raw.get("start")
        end = raw.get("end")
        if mode not in rcl.VALID_MODES:
            errors.append(f"groups[{index}].mode must be one of {sorted(rcl.VALID_MODES)}.")
            continue
        if not _label_is_supported(start) or not _label_is_supported(end):
            errors.append(f"groups[{index}] start/end must be exactly two ASCII characters.")
            continue
        groups.append(rcl.MixedRclGroup(mode=mode, start=start, end=end))  # type: ignore[arg-type]
    if len(groups) > 35:
        errors.append("The locked source-driven generator supports at most 35 passive groups.")

    sources_raw = payload.get("sources")
    if not isinstance(sources_raw, list) or not sources_raw:
        errors.append("sources must be a non-empty array.")
        sources_raw = []
    sources: list[SourcePlan] = []
    for index, raw in enumerate(sources_raw, start=1):
        if not isinstance(raw, dict):
            errors.append(f"sources[{index}] must be an object.")
            continue
        kind = raw.get("kind")
        ref = raw.get("ref")
        value = raw.get("value")
        positive = raw.get("positive")
        negative = raw.get("negative")
        if kind not in {"dc_voltage", "dc_current", "ac_voltage"}:
            errors.append(f"sources[{index}].kind is unsupported; AC current is not available.")
            continue
        expected_prefix = "I" if kind == "dc_current" else "V"
        if not _label_is_supported(ref) or not ref.startswith(expected_prefix):
            errors.append(f"sources[{index}].ref must be a two-character {expected_prefix}-reference.")
            continue
        if not isinstance(value, str) or not value or len(value) > 12 or not value.isascii():
            errors.append(f"sources[{index}].value must be 1..12 ASCII characters.")
            continue
        if not _label_is_supported(positive) or not _label_is_supported(negative):
            errors.append(f"sources[{index}] positive/negative labels must be exactly two ASCII characters.")
            continue
        if positive == negative:
            errors.append(f"sources[{index}] positive and negative labels must differ.")
            continue
        sources.append(
            SourcePlan(
                kind=kind,  # type: ignore[arg-type]
                ref=ref,
                value=value,
                positive=positive,
                negative=negative,
            )
        )
    if len(sources) > 9:
        errors.append("The locked source-driven generator supports at most nine sources.")
    if len({item.ref for item in sources}) != len(sources):
        errors.append("Source references must be unique.")

    ac_sources = [item for item in sources if item.kind == "ac_voltage"]
    if ac_sources and (len(ac_sources) != 1 or len(sources) != 1):
        errors.append("The accepted AC-voltage path supports exactly one AC voltage source and no mixed source types.")
    if ac_sources and (ac_sources[0].ref != "V1" or ac_sources[0].value != "VSINE"):
        errors.append("The accepted AC-voltage source must use ref V1 and value VSINE.")

    endpoints = {label for item in groups for label in (item.start, item.end)}
    for source in sources:
        if source.positive not in endpoints:
            errors.append(f"Source positive net {source.positive!r} is not used by a passive group.")
        if source.negative not in endpoints:
            errors.append(f"Source negative net {source.negative!r} is not used by a passive group.")

    component_values_raw = payload.get("component_values", {})
    component_values: dict[str, str] = {}
    if component_values_raw is None:
        component_values_raw = {}
    if not isinstance(component_values_raw, dict):
        errors.append("component_values must be an object.")
    else:
        for ref, value in component_values_raw.items():
            if not _label_is_supported(ref):
                errors.append(f"component_values key {ref!r} must be a two-character reference.")
            elif not isinstance(value, str) or not rcl._value_is_supported(ref, value):
                errors.append(f"component_values[{ref!r}] must be exactly three safe ASCII characters.")
            else:
                component_values[ref] = value

    schema_version = payload.get("schema_version", SCHEMA_VERSION)
    generator_target = payload.get("generator_target", GENERATOR_TARGET)
    name = project.get("name", "SOURCE_DRIVEN_PROJECT")
    output_basename = project.get("output_basename", name)
    metadata = payload.get("metadata", {})
    if not isinstance(schema_version, str):
        errors.append("schema_version must be a string.")
        schema_version = SCHEMA_VERSION
    if not isinstance(generator_target, str):
        errors.append("generator_target must be a string.")
        generator_target = GENERATOR_TARGET
    if not isinstance(name, str) or not name:
        errors.append("project.name must be a non-empty string.")
        name = "SOURCE_DRIVEN_PROJECT"
    if not isinstance(output_basename, str) or not output_basename:
        errors.append("project.output_basename must be a non-empty string.")
        output_basename = name
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object.")
        metadata = {}

    if errors:
        return None, errors
    return (
        SourceDrivenCircuitIR(
            schema_version=schema_version,
            generator_target=generator_target,
            name=name,
            output_basename=output_basename,
            groups=tuple(groups),
            sources=tuple(sources),
            component_values=component_values,
            metadata=metadata,
        ),
        [],
    )


def validate_source_driven_circuit(ir: SourceDrivenCircuitIR) -> SourceDrivenValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    if ir.generator_target != GENERATOR_TARGET:
        warnings.append(f"generator_target is {ir.generator_target!r}; locked target is {GENERATOR_TARGET!r}.")
    if any(item.kind == "ac_voltage" for item in ir.sources) and len(ir.sources) != 1:
        errors.append("AC voltage cannot currently be combined with another source.")
    return SourceDrivenValidationReport(tuple(errors), tuple(warnings), ir)


def validate_source_driven_payload(payload: Any) -> SourceDrivenValidationReport:
    ir, issues = parse_source_driven_ir(payload)
    if issues:
        return SourceDrivenValidationReport(tuple(issues), (), None)
    assert ir is not None
    return validate_source_driven_circuit(ir)


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(4 + len(value)) + value


def _device_section_from_dsn(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise RuntimeError("ROOT.DSN does not match the accepted device-section model.")
    insert += len(marker)
    return dsn[insert:first]


def _build_dsn_with_devices(
    base_dsn: bytes,
    donor_dsn: bytes,
    object_chunk: bytes,
    devices: bytes,
) -> tuple[bytes, dict[str, int]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise RuntimeError("Base or source donor ROOT.DSN does not match the accepted section model.")
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


def _source_net_rcl(
    ir: SourceDrivenCircuitIR,
    templates: rcl.RclUnitTemplates,
    layout_plan: LayoutPlan | None = None,
) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, Any]], dict[str, Any]]:
    passive_ir = rcl.MixedRclCircuitIR(
        schema_version=rcl.SCHEMA_VERSION,
        generator_target=rcl.GENERATOR_TARGET,
        name=ir.name,
        output_basename=ir.output_basename,
        groups=ir.groups,
        component_values=ir.component_values,
        metadata=ir.metadata,
    )
    chunk_with_bridge, specs, topology, counts = rcl.build_object_chunk(
        passive_ir,
        templates,
        layout_plan,
    )
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE
    body = bytearray(chunk_with_bridge[bridge_end:])
    if body.count(b"$TERPOWER") or body.count(b"$TERGROUND"):
        raise RuntimeError("Source-net passive body contains forbidden power/ground terminals.")
    body[-1] = 0xFF
    return bytes(b"\x00" + body), specs, topology, {**counts, "power_bridge_count": 0}


def _terminal_events(chunk: bytes) -> list[tuple[int, str, str]]:
    events: list[tuple[int, str, str]] = []
    for marker, kind in ((b"$TEROUTPUT", "OUT"), (b"$TERINPUT", "IN")):
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            start = marker_pos - 14
            length_offset = start + (31 if kind == "OUT" else 30)
            label_start = length_offset + 1
            label_len = chunk[length_offset]
            label = chunk[label_start : label_start + label_len].decode("ascii")
            events.append((start, kind, label))
            pos = marker_pos + 1
    return sorted(events)


def _terminal_bounds(chunk: bytes) -> list[tuple[int, int, str, str]]:
    events = _terminal_events(chunk)
    return [
        (start, events[index + 1][0] if index + 1 < len(events) else len(chunk), kind, label)
        for index, (start, kind, label) in enumerate(events)
    ]


def _s32(data: bytes | bytearray, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little", signed=True)


def _put_s32(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 4] = rv9._i32(value)


def _add_s32(data: bytearray, offset: int, delta: int) -> None:
    _put_s32(data, offset, _s32(data, offset) + delta)


def _translate_terminal(out: bytearray, start: int, end: int, kind: str, dx: int, dy: int) -> None:
    record = bytes(out[start:end])
    length_offset = 31 if kind == "OUT" else 30
    label_start = length_offset + 1
    label_len = record[length_offset]
    label_x = label_start + label_len
    label_y = label_x + 4
    _add_s32(out, start + 1, dx)
    _add_s32(out, start + 5, dy)
    _add_s32(out, start + label_x, dx)
    _add_s32(out, start + label_y, dy)


def _translate_wires(out: bytearray, start: int, end: int, dx: int, dy: int) -> None:
    pos = start
    while True:
        marker = bytes(out).find(b"WIRE", pos, end)
        if marker < 0:
            return
        coord = marker + 9
        if coord + 16 <= end:
            _add_s32(out, coord, dx)
            _add_s32(out, coord + 4, dy)
            _add_s32(out, coord + 8, dx)
            _add_s32(out, coord + 12, dy)
        pos = marker + 1


def _translate_source_text_fields(out: bytearray, start: int, end: int, dx: int, dy: int) -> None:
    patterns = (
        (b"\xff\x02V1", 4),
        (b"\xff\x021V", 4),
        (b"\xff\x07VSOURCE", 9),
        (b"\x02\x00\x07VSOURCE", 10),
        (b"{PRIMITIVE=ANALOG}\n", len(b"{PRIMITIVE=ANALOG}\n")),
        (b"\xff\x02I1", 4),
        (b"\xff\x021A", 4),
        (b"\xff\x07CSOURCE", 9),
        (b"\x02\x00\x07CSOURCE", 10),
        (b"{PRIMITIVE=ANALOGUE}\n", len(b"{PRIMITIVE=ANALOGUE}\n")),
        (b"\xff\x05VSINE", 7),
        (b"\x02\x00\x05VSINE", 8),
    )
    data = bytes(out)
    for pattern, coord_delta in patterns:
        pos = start
        while True:
            found = data.find(pattern, pos, end)
            if found < 0:
                break
            coord = found + coord_delta
            if coord + 8 <= end:
                _add_s32(out, coord, dx)
                _add_s32(out, coord + 4, dy)
            pos = found + 1


def _translate_block(block: bytes, dx: int, dy: int) -> bytes:
    out = bytearray(block)
    _translate_wires(out, 0, len(out), dx, dy)
    _translate_source_text_fields(out, 0, len(out), dx, dy)
    for start, end, kind, _label in _terminal_bounds(block):
        _translate_terminal(out, start, end, kind, dx, dy)
    return bytes(out)


def _patch_terminal_label_suffix(record: bytes, kind: str, label: str, suffix: int) -> bytes:
    raw = label.encode("ascii")
    out = bytearray(record)
    length_offset = 31 if kind == "OUT" else 30
    label_start = length_offset + 1
    old_len = out[length_offset]
    out = out[:length_offset] + bytearray([len(raw)]) + bytearray(raw) + out[label_start + old_len :]
    out[-4:-2] = rv9._u16(suffix)
    out[-2:] = b"\x01\x00"
    return bytes(out)


def _translate_terminal_record(record: bytes, kind: str, dx: int, dy: int) -> bytes:
    out = bytearray(record)
    _translate_terminal(out, 0, len(out), kind, dx, dy)
    return bytes(out)


def _source_templates(donor_chunk: bytes) -> dict[str, bytes]:
    events = _terminal_events(donor_chunk)
    leading_v0 = next(start for start, kind, label in events if kind == "OUT" and label == "V0")
    next_after_v0 = min(start for start, _kind, _label in events if start > leading_v0)
    vsource_start = next(start for start, kind, label in events if kind == "IN" and label == "DVO")
    csource_start = next(start for start, kind, label in events if kind == "IN" and label == "A7" and start > vsource_start)
    return {
        "v_out": donor_chunk[leading_v0:next_after_v0],
        "v_tail": donor_chunk[vsource_start:csource_start],
        "c_block": donor_chunk[csource_start:],
    }


def _split_vsource_tail(block: bytes) -> tuple[bytes, bytes, bytes]:
    ref_pos = block.find(b"\xff\x02V1")
    first_wire = block.find(b"WIRE")
    if ref_pos < 0 or first_wire < 0:
        raise RuntimeError("VSOURCE template is missing V1 or WIRE markers.")
    source_start = ref_pos - 1
    return block[:source_start], block[source_start:first_wire], block[first_wire:]


def _split_csource_block(block: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    events = _terminal_events(block)
    if len(events) != 2 or events[0][1] != "IN" or events[1][1] != "OUT":
        raise RuntimeError(f"Unexpected CSOURCE terminal layout: {events}")
    in_start = events[0][0]
    out_start = events[1][0]
    ref_pos = block.find(b"\xff\x02I1")
    first_wire = block.find(b"WIRE")
    if in_start != 0 or ref_pos < 0 or first_wire < 0:
        raise RuntimeError("CSOURCE template is missing expected markers.")
    source_start = ref_pos - 1
    return block[in_start:out_start], block[out_start:source_start], block[source_start:first_wire], block[first_wire:]


def _source_suffixes(source_index: int) -> tuple[int, int]:
    base = 0x7000 + (source_index - 1) * 0x80
    return base, base + 0x32


def _patch_dc_source_record(
    record: bytes,
    *,
    old_ref: str,
    source: SourcePlan,
    global_id: int,
    old_in_suffix: int,
    new_in_suffix: int,
    old_out_suffix: int,
    new_out_suffix: int,
) -> bytes:
    out = bytearray(record)
    old_ref_pat = b"\xff" + bytes([len(old_ref)]) + old_ref.encode("ascii")
    new_ref_pat = b"\xff" + bytes([len(source.ref)]) + source.ref.encode("ascii")
    if len(old_ref) != len(source.ref) or old_ref_pat not in out:
        raise RuntimeError("Source reference does not fit the accepted donor record.")
    out = bytearray(bytes(out).replace(old_ref_pat, new_ref_pat, 1))

    final_model = b"\x02\x00\x07" + source.model.encode("ascii")
    model_pos = bytes(out).find(final_model)
    if model_pos < 0:
        raise RuntimeError(f"Could not find source model marker {source.model}.")
    body_coord = model_pos + len(final_model)
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)

    old_value = b"1V" if source.kind == "dc_voltage" else b"1A"
    old_value_pat = b"\xff" + bytes([len(old_value)]) + old_value
    new_value = source.value.encode("ascii")
    if old_value_pat not in out:
        raise RuntimeError("Could not find the donor source value field.")
    out = bytearray(bytes(out).replace(old_value_pat, b"\xff" + bytes([len(new_value)]) + new_value, 1))

    data = bytes(out)
    old_in = rv9._u16(old_in_suffix) + b"\x01\x00"
    old_out = rv9._u16(old_out_suffix) + b"\x01\x00"
    if old_in not in data or old_out not in data:
        raise RuntimeError("Source record does not contain donor terminal links.")
    return data.replace(old_in, rv9._u16(new_in_suffix) + b"\x01\x00", 1).replace(
        old_out, rv9._u16(new_out_suffix) + b"\x01\x00", 1
    )


def _terminal_symbol(record: bytes) -> tuple[int, int]:
    return _s32(record, 1), _s32(record, 5)


def _body_terminal_positions(chunk: bytes) -> dict[str, list[tuple[int, int]]]:
    positions: dict[str, list[tuple[int, int]]] = {}
    for start, kind, label in _terminal_events(chunk):
        if kind in {"IN", "OUT"}:
            positions.setdefault(label, []).append((_s32(chunk, start + 1), _s32(chunk, start + 5)))
    return positions


def _source_target(
    source: SourcePlan,
    positions: dict[str, list[tuple[int, int]]],
    duplicate_index: int,
) -> tuple[int, int]:
    base_positions = positions.get(source.positive) or [(-10_160_000, 5_080_000)]
    base_x, base_y = base_positions[min(duplicate_index, len(base_positions) - 1)]
    return base_x - 1_524_000, base_y - 1_016_000 - duplicate_index * 1_270_000


def _build_vsource_unit(
    templates: dict[str, bytes],
    source: SourcePlan,
    *,
    source_index: int,
    global_id: int,
    target: tuple[int, int],
) -> tuple[bytes, bytes, dict[str, Any]]:
    out_suffix, in_suffix = _source_suffixes(source_index)
    output = templates["v_out"]
    input_record, source_record, wires = _split_vsource_tail(templates["v_tail"])
    old_out_suffix = int.from_bytes(output[-4:-2], "little")
    old_in_suffix = int.from_bytes(input_record[-4:-2], "little")
    old_x, old_y = _terminal_symbol(output)
    dx, dy = target[0] - old_x, target[1] - old_y

    output = _patch_terminal_label_suffix(_translate_terminal_record(output, "OUT", dx, dy), "OUT", source.positive, out_suffix)
    input_record = _patch_terminal_label_suffix(
        _translate_terminal_record(input_record, "IN", dx, dy), "IN", source.negative, in_suffix
    )
    source_record = _patch_dc_source_record(
        _translate_block(source_record, dx, dy),
        old_ref="V1",
        source=source,
        global_id=global_id,
        old_in_suffix=old_in_suffix,
        new_in_suffix=in_suffix,
        old_out_suffix=old_out_suffix,
        new_out_suffix=out_suffix,
    )
    return output, input_record + source_record + _translate_block(wires, dx, dy), {
        "kind": source.kind,
        "ref": source.ref,
        "value": source.value,
        "positive": source.positive,
        "negative": source.negative,
        "global_id": global_id,
        "target": list(target),
    }


def _build_csource_unit(
    templates: dict[str, bytes],
    source: SourcePlan,
    *,
    source_index: int,
    global_id: int,
    target: tuple[int, int],
) -> tuple[bytes, dict[str, Any]]:
    out_suffix, in_suffix = _source_suffixes(source_index)
    in_record, out_record, source_record, wires = _split_csource_block(templates["c_block"])
    old_in_suffix = int.from_bytes(in_record[-4:-2], "little")
    old_out_suffix = int.from_bytes(out_record[-4:-2], "little")
    old_x, old_y = _terminal_symbol(out_record)
    dx, dy = target[0] - old_x, target[1] - old_y

    in_record = _patch_terminal_label_suffix(
        _translate_terminal_record(in_record, "IN", dx, dy), "IN", source.negative, in_suffix
    )
    out_record = _patch_terminal_label_suffix(
        _translate_terminal_record(out_record, "OUT", dx, dy), "OUT", source.positive, out_suffix
    )
    source_record = _patch_dc_source_record(
        _translate_block(source_record, dx, dy),
        old_ref="I1",
        source=source,
        global_id=global_id,
        old_in_suffix=old_in_suffix,
        new_in_suffix=in_suffix,
        old_out_suffix=old_out_suffix,
        new_out_suffix=out_suffix,
    )
    return in_record + out_record + source_record + _translate_block(wires, dx, dy), {
        "kind": source.kind,
        "ref": source.ref,
        "value": source.value,
        "positive": source.positive,
        "negative": source.negative,
        "global_id": global_id,
        "target": list(target),
    }


def _repair_negative_wire_high_bytes(chunk: bytes) -> tuple[bytes, list[dict[str, int]]]:
    out = bytearray(chunk)
    repairs: list[dict[str, int]] = []
    pos = 0
    while True:
        marker = bytes(out).find(b"WIRE", pos)
        if marker < 0:
            break
        y1_offset = marker + 13
        y2_offset = marker + 21
        if y2_offset + 4 <= len(out):
            y1 = _s32(out, y1_offset)
            y2 = _s32(out, y2_offset)
            if y1 < 0 and y2 - y1 == 0x01000000:
                _put_s32(out, y2_offset, y1)
                repairs.append({"wire_marker": marker, "old_y2": y2, "new_y2": y1})
        pos = marker + 1
    return bytes(out), repairs


def _build_dc_object_chunk(
    ir: SourceDrivenCircuitIR,
    source_net_chunk: bytes,
    specs: list[rcl.RclSpec],
    donor_chunk: bytes,
    layout_plan: LayoutPlan | None = None,
) -> tuple[bytes, list[dict[str, Any]], list[dict[str, int]]]:
    templates = _source_templates(donor_chunk)
    positions = _body_terminal_positions(source_net_chunk)
    positive_counts: dict[str, int] = {}
    output_terms: list[bytes] = []
    tail_blocks: list[bytes] = []
    metadata: list[dict[str, Any]] = []
    first_source_id = len(specs) + 1

    for source_index, source in enumerate(ir.sources, start=1):
        duplicate_index = positive_counts.get(source.positive, 0)
        positive_counts[source.positive] = duplicate_index + 1
        target_position = (
            layout_plan.source_positions.get(source.ref)
            if layout_plan is not None
            else None
        )
        target = (
            (target_position.x, target_position.y)
            if target_position is not None
            else _source_target(source, positions, duplicate_index)
        )
        global_id = first_source_id + source_index - 1
        if source.kind == "dc_voltage":
            output, tail, info = _build_vsource_unit(
                templates, source, source_index=source_index, global_id=global_id, target=target
            )
            output_terms.append(output)
            tail_blocks.append(tail)
        else:
            tail, info = _build_csource_unit(
                templates, source, source_index=source_index, global_id=global_id, target=target
            )
            tail_blocks.append(tail)
        metadata.append(info)

    object_chunk = bytearray(b"\x00" + b"".join(output_terms) + source_net_chunk[1:-1] + b"".join(tail_blocks))
    object_chunk[-1] = 0xFF
    repaired, repairs = _repair_negative_wire_high_bytes(bytes(object_chunk))
    return repaired, metadata, repairs


def _source_prop_text(project_path: Path, ref: str = "V1") -> bytes:
    cdb = read_internal_file(project_path, "ROOT.CDB")
    marker = _enc_str(ref) + _enc_str("VSINE") + _enc_str("VSINE") + _enc_str("")
    pos = cdb.find(marker)
    if pos < 0:
        raise RuntimeError("Cannot find VSINE property text in accepted donor.")
    text_len_pos = pos + len(marker)
    total_len = struct.unpack("<I", cdb[text_len_pos : text_len_pos + 4])[0]
    return cdb[text_len_pos + 4 : text_len_pos + total_len]


def _patch_ac_source_global_id(source_record: bytes, global_id: int) -> bytes:
    out = bytearray(source_record)
    model_pos = out.rfind(b"VSINE")
    if model_pos < 0:
        raise RuntimeError("VSINE model marker not found.")
    out[model_pos + len(b"VSINE") + 12 : model_pos + len(b"VSINE") + 16] = rv9._u32(global_id)
    return bytes(out)


def _patch_ac_terminal_labels(block: bytes, source: SourcePlan) -> bytes:
    out = bytearray(block)
    for start, _end, kind, label in _terminal_bounds(block):
        replacement = source.positive if kind == "OUT" and label == "AV" else source.negative if kind == "IN" and label == "A0" else None
        if replacement is None:
            continue
        length_offset = start + (31 if kind == "OUT" else 30)
        label_start = length_offset + 1
        old_len = out[length_offset]
        raw = replacement.encode("ascii")
        if len(raw) != old_len:
            raise RuntimeError("AC source net labels must preserve the donor-tested two-character size.")
        out[label_start : label_start + old_len] = raw
    return bytes(out)


def _build_ac_object_chunk(
    source_net_chunk: bytes,
    specs: list[rcl.RclSpec],
    source: SourcePlan,
    two_source_project: Path,
    layout_plan: LayoutPlan | None = None,
) -> tuple[bytes, list[dict[str, Any]]]:
    body = rv9._extract_object_chunk(read_internal_file(two_source_project, "ROOT.DSN"))[1:]
    block = bytearray(body[105:778])
    if len(block) != 673 or block.count(b"VSINE") != 3:
        raise RuntimeError("Accepted non-final AC source unit shape changed.")
    target_position = (
        layout_plan.source_positions.get(source.ref)
        if layout_plan is not None
        else None
    )
    if target_position is not None:
        events = _terminal_events(bytes(block))
        output_start = next(start for start, kind, _label in events if kind == "OUT")
        dx = target_position.x - _s32(block, output_start + 1)
        dy = target_position.y - _s32(block, output_start + 5)
        block = bytearray(_translate_block(bytes(block), dx, dy))
    global_id = len(specs) + 1
    block[207:573] = _patch_ac_source_global_id(bytes(block[207:573]), global_id)
    block[-1] = 0x00
    patched = _patch_ac_terminal_labels(bytes(block), source)
    object_chunk = bytearray(b"\x00" + patched + source_net_chunk[1:])
    object_chunk[-1] = 0xFF
    metadata = {
            "kind": source.kind,
            "ref": source.ref,
            "value": source.value,
            "positive": source.positive,
            "negative": source.negative,
            "global_id": global_id,
        }
    if target_position is not None:
        metadata["target"] = [target_position.x, target_position.y]
    return bytes(object_chunk), [metadata]


def _build_cdb(
    passive_specs: list[rcl.RclSpec],
    sources: tuple[SourcePlan, ...],
    *,
    ac_prop_text: bytes | None = None,
) -> bytes:
    first_source_id = len(passive_specs) + 1
    source_rows = [
        SourceRow(
            idx=first_source_id + index,
            ref=source.ref,
            value=source.value,
            model=source.model,
            prop_text=ac_prop_text if source.kind == "ac_voltage" and ac_prop_text is not None else source.prop_text,
            ac_voltage=source.kind == "ac_voltage",
        )
        for index, source in enumerate(sources)
    ]
    if any(row.ac_voltage for row in source_rows):
        ordered: list[Any] = [*source_rows, *sorted(passive_specs, key=lambda item: item.idx)]
    else:
        ordered = [
            *sorted(passive_specs, key=lambda item: item.idx),
            *[row for row in source_rows if row.model == "CSOURCE"],
            *[row for row in source_rows if row.model == "VSOURCE"],
        ]

    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + _enc_str(spec.ref)
        if isinstance(spec, SourceRow) and spec.ac_voltage:
            out += rv9._u32(2) + _enc_str("+") + _enc_str("1") + _enc_str("-") + _enc_str("2")
        elif getattr(spec, "kind", "") == "CAPACITOR":
            out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, SourceRow):
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
        "$TERGROUND",
        "$TERINPUT",
        "$TEROUTPUT",
        "VSOURCE",
        "CSOURCE",
        "VSINE",
        "CAPACITOR",
        "REALIND",
        "RESISTOR",
        "WIRE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _validate_object_chunk(
    chunk: bytes,
    passive_specs: list[rcl.RclSpec],
    sources: tuple[SourcePlan, ...],
) -> list[str]:
    issues = rcl._scan_wire_issues(chunk)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("source-driven object chunk boundary bytes are invalid")
    if chunk.count(b"$TERPOWER") or chunk.count(b"$TERGROUND"):
        issues.append("source-driven object chunk contains power/ground terminal records")
    expected_components = len(passive_specs) + len(sources)
    if chunk.count(b"COMPONENT ID") != expected_components:
        issues.append("component ID count does not match passive plus source count")
    return issues


def generate_source_driven_project(
    ir: SourceDrivenCircuitIR,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
    layout_plan: LayoutPlan | None = None,
) -> SourceDrivenGenerationResult:
    registry = registry or FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {', '.join(failed_hashes)}")
    report = validate_source_driven_circuit(ir)
    if not report.valid:
        raise SourceDrivenGenerationBlocked(report)

    base = registry.get("e001_empty")
    rcl_donor = registry.get("rcl_4x_t07_unit_donor")
    templates = rcl._load_rcl_unit_templates(rcl_donor.path)
    source_net_chunk, specs, topology, generation_counts = _source_net_rcl(
        ir,
        templates,
        layout_plan,
    )

    ac_source = next((item for item in ir.sources if item.kind == "ac_voltage"), None)
    wire_repairs: list[dict[str, int]] = []
    if ac_source is not None:
        ac_two = registry.get("source_acv_two_source_donor")
        ac_variant = registry.get("source_acv_variant_donor")
        dsn_donor = registry.get("source_acv_load_donor")
        object_chunk, source_metadata = _build_ac_object_chunk(
            source_net_chunk,
            specs,
            ac_source,
            ac_two.path,
            layout_plan,
        )
        ac_prop_text = _source_prop_text(ac_variant.path)
        cdb = _build_cdb(specs, ir.sources, ac_prop_text=ac_prop_text)
    else:
        dsn_donor = registry.get("source_dc_mixed_v15_donor")
        donor_dsn = read_internal_file(dsn_donor.path, "ROOT.DSN")
        donor_chunk = rv9._extract_object_chunk(donor_dsn)
        object_chunk, source_metadata, wire_repairs = _build_dc_object_chunk(
            ir,
            source_net_chunk,
            specs,
            donor_chunk,
            layout_plan,
        )
        cdb = _build_cdb(specs, ir.sources)

    donor_dsn = read_internal_file(dsn_donor.path, "ROOT.DSN")
    devices = _device_section_from_dsn(donor_dsn)
    dsn, section_pointers = _build_dsn_with_devices(
        read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        object_chunk,
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    chunk_issues = _validate_object_chunk(object_chunk, specs, ir.sources)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        chunk_issues.append("ROOT.DSN object chunk differs from requested chunk")

    output_dir = Path(outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    basename = ir.output_basename
    output_path = output_dir / f"{basename}.pdsprj"
    cdb_path = output_dir / f"{basename}.ROOT.CDB.bin"
    dsn_path = output_dir / f"{basename}.ROOT.DSN.bin"
    chunk_path = output_dir / f"{basename}.OBJECT_CHUNK.bin"
    layout_path = output_dir / "layout_plan.json"
    manifest_path = output_dir / "manifest.json"
    readme_path = output_dir / "README_TEST_FIRST.txt"
    version_path = output_dir / "generator_version.txt"

    write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    final_layout = (
        plan_with_actual_positions(layout_plan, topology, source_metadata)
        if layout_plan is not None
        else actual_layout_plan("source-driven", topology, source_metadata)
    )
    layout_path.write_text(json.dumps(final_layout.as_dict(), indent=2) + "\n", encoding="utf-8")
    version_path.write_text(
        "proteusgen source_driven locked method\n"
        "base_fixture=e001_empty\n"
        f"source_donor_fixture={dsn_donor.id}\n"
        "method=accepted V15 multi-DC units or accepted V2 non-final AC-voltage unit\n",
        encoding="utf-8",
    )

    manifest = {
        "schema_version": ir.schema_version,
        "generator_target": ir.generator_target,
        "status": "locked_current_scope",
        "project_name": ir.name,
        "output_basename": basename,
        "base_project": BASE_PROJECT,
        "base_fixture_id": base.id,
        "rcl_unit_donor_fixture_id": rcl_donor.id,
        "source_donor_fixture_id": dsn_donor.id,
        "source_count": len(ir.sources),
        "sources": source_metadata,
        "component_count_requested": generation_counts["component_count"],
        "component_count_emitted_cdb": len(specs),
        "component_count_emitted_dsn": len(specs),
        "group_count": generation_counts["group_count"],
        "group_modes": generation_counts["group_modes"],
        "topology": sorted(topology, key=lambda item: item["idx"]),
        "layout": final_layout.as_dict(),
        "wire_repairs": wire_repairs,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": section_pointers,
        "static_validation_issues": chunk_issues,
        "metadata": ir.metadata,
        "component_value_overrides": ir.component_values,
        "known_limitations": [
            "AC current sources are unsupported.",
            "The accepted AC-voltage path supports one VSINE source.",
            "DC voltage and DC current sources may be combined within the accepted nine-source limit.",
            "Source and passive net labels are exactly two ASCII characters.",
            "Passive geometry remains donor-derived horizontal terminal/component groups.",
        ],
        "output_files": [
            output_path.name,
            cdb_path.name,
            dsn_path.name,
            chunk_path.name,
            layout_path.name,
            manifest_path.name,
            readme_path.name,
            version_path.name,
        ],
        "output_hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            chunk_path.name: _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "base_project": _sha256_file(base.path),
            "source_donor": _sha256_file(dsn_donor.path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        f"{basename}\n\n"
        "Open this generated source-driven project in Proteus 8.13.\n\n"
        f"Project: {output_path.name}\n"
        f"Sources: {len(ir.sources)}\n"
        f"Passive groups: {len(ir.groups)}\n"
        f"Static validation issues: {chunk_issues}\n",
        encoding="utf-8",
    )
    return SourceDrivenGenerationResult(
        output_path,
        cdb_path,
        dsn_path,
        chunk_path,
        layout_path,
        manifest_path,
        readme_path,
        version_path,
        manifest,
    )


def generate_source_driven_project_from_payload(
    payload: Any,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
    layout_strategy: str | None = None,
) -> SourceDrivenGenerationResult:
    try:
        application = apply_layout_to_payload(payload, layout_strategy)
    except LayoutError as exc:
        raise SourceDrivenGenerationBlocked(
            SourceDrivenValidationReport((str(exc),), (), None)
        ) from exc
    ir, issues = parse_source_driven_ir(application.payload)
    if issues:
        raise SourceDrivenGenerationBlocked(SourceDrivenValidationReport(tuple(issues), (), None))
    assert ir is not None
    return generate_source_driven_project(
        ir,
        outdir,
        registry=registry,
        layout_plan=application.plan,
    )
