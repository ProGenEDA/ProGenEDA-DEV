"""Locked mixed resistor/capacitor/inductor terminal generator.

This module promotes the user-confirmed R/C/L method into main code for the
current scope. It uses E001 as the clean base and the accepted 4x RCL donor as
the record schema. The generator accepts a conservative group recipe where each
group is one proven donor-derived block:

``RCL``, ``RC``, ``LC``, ``RL``, ``C``, ``R``, or ``L``.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from . import mixed_passive as mp
from . import resistor_v9 as rv9
from .pdsprj import read_internal_file, write_project_from_parts
from .templates import FixtureRegistry
from .versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

Mode = Literal["RCL", "RC", "LC", "RL", "C", "R", "L"]
VALID_MODES: set[str] = {"RCL", "RC", "LC", "RL", "C", "R", "L"}

SCHEMA_VERSION = "mixed-rcl-circuit-ir/v0.1"
GENERATOR_TARGET = "proteus-8.13-mixed-rcl-locked"
BASE_PROJECT = "E001_EMPTY_BASE"

CAP_SIZE = 366
IN_SIZE = 103
IND_SIZE = 374
OUT_SIZE = 104
RES_SIZE = 346
WIRE_SIZE = 50
WIRE_TRIMMED_SIZE = 49
UNIT_SIZE_NONFINAL = 2006
SUFFIX_STEP = 0x07D6

BASE_X = -7366000
BASE_Y = 5080000
SAFE_X_STEP = 3810000
SAFE_Y_STEP = 2540000
GROUP_X_STEP = 10160000
GROUP_Y_STEP = 6096000

CAP_OUT_SUFFIX_BASE = 0x07FA
CAP_IN_SUFFIX_BASE = 0x082C
L_IN_SUFFIX_BASE = 0x0B09
L_OUT_SUFFIX_BASE = 0x0B3B
R_IN_SUFFIX_BASE = 0x0D30
R_OUT_SUFFIX_BASE = 0x0D62

INDUCTOR_PROP_TEXT = b"{MODFILE=REALIND}\n{RP=1M}\n{ESR=0.2}\n{CP=0.2pF}\n\n\n\x00"


@dataclass(frozen=True)
class MixedRclGroup:
    mode: Mode
    start: str
    end: str


@dataclass(frozen=True)
class MixedRclCircuitIR:
    schema_version: str
    generator_target: str
    name: str
    output_basename: str
    groups: tuple[MixedRclGroup, ...]
    component_values: dict[str, str]
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MixedRclValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    circuit: MixedRclCircuitIR | None = None

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
                "group_count": len(self.circuit.groups),
                "groups": [
                    {"mode": group.mode, "start": group.start, "end": group.end}
                    for group in self.circuit.groups
                ],
                "component_values": self.circuit.component_values,
            },
        }


@dataclass(frozen=True)
class MixedRclGenerationResult:
    output_path: Path
    cdb_path: Path
    dsn_path: Path
    chunk_path: Path
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
            "manifest_path": str(self.manifest_path),
            "readme_path": str(self.readme_path),
            "generator_version_path": str(self.version_path),
            "static_validation_issues": self.manifest["static_validation_issues"],
            "output_hashes": self.manifest["output_hashes"],
        }


class MixedRclGenerationBlocked(Exception):
    def __init__(self, report: MixedRclValidationReport) -> None:
        super().__init__("Mixed R/C/L CircuitIR cannot be emitted.")
        self.report = report


@dataclass(frozen=True)
class RclSpec:
    idx: int
    source_ref: str
    ref: str
    kind: str
    value: str
    visible_value: str
    left: str
    right: str
    x: int
    y: int
    visual_data: dict[str, Any]

    @property
    def type(self) -> str:
        return self.kind

    @property
    def nodes(self) -> tuple[str, str]:
        return (self.left, self.right)

    @property
    def visual(self) -> dict[str, Any]:
        out = dict(self.visual_data)
        out.setdefault("visible_value", self.visible_value)
        return out


@dataclass(frozen=True)
class UnitTemplates:
    cap_output: bytes
    cap_input: bytes
    cap_record: bytes
    cap_wire_left: bytes
    cap_wire_right: bytes
    l_input: bytes
    r_input: bytes
    l_output: bytes
    l_inductor: bytes
    l_wire_left: bytes
    l_wire_right: bytes
    r_output: bytes
    r_resistor_prefix: bytes
    r_resistor: bytes
    r_wire_left: bytes
    r_wire_right: bytes


@dataclass(frozen=True)
class RclUnitTemplates:
    donor_chunk: bytes
    header: bytes
    bridge_core: bytes
    units: tuple[UnitTemplates, ...]


def group(mode: str, start: str, end: str) -> MixedRclGroup:
    if mode not in VALID_MODES:
        raise ValueError(f"Unsupported R/C/L group mode {mode!r}.")
    return MixedRclGroup(mode=mode, start=start, end=end)  # type: ignore[arg-type]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _s32(record: bytes, offset: int) -> int:
    return struct.unpack("<i", record[offset : offset + 4])[0]


def _i32(value: int) -> bytes:
    return struct.pack("<i", value)


def _u16(value: int) -> bytes:
    return struct.pack("<H", value & 0xFFFF)


def _angle_tenths(value: int) -> bytes:
    return _u16(value) + b"\x00\x00"


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return rv9._u32(4 + len(data)) + data


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "WIRE",
        "RESISTOR",
        "REALIND",
        "CAPACITOR",
        "CAP10",
        "COMPONENT ID",
        "COMPONENT VALUE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _split_unit(unit: bytes) -> UnitTemplates:
    cursor = 0
    cap_output = unit[cursor : cursor + OUT_SIZE]
    cursor += OUT_SIZE
    cap_input = unit[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    cap_record = unit[cursor : cursor + CAP_SIZE]
    cursor += CAP_SIZE
    cap_wire_left = unit[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    cap_wire_right = unit[cursor : cursor + WIRE_TRIMMED_SIZE]
    cursor += WIRE_TRIMMED_SIZE
    l_input = unit[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    r_input = unit[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    l_output = unit[cursor : cursor + OUT_SIZE]
    cursor += OUT_SIZE
    l_inductor = unit[cursor : cursor + IND_SIZE]
    cursor += IND_SIZE
    l_wire_left = unit[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    l_wire_right = unit[cursor : cursor + WIRE_TRIMMED_SIZE]
    cursor += WIRE_TRIMMED_SIZE
    r_output = unit[cursor : cursor + OUT_SIZE]
    cursor += OUT_SIZE
    r_resistor_prefix = unit[cursor : cursor + 1]
    cursor += 1
    r_resistor = unit[cursor : cursor + RES_SIZE]
    cursor += RES_SIZE
    r_wire_left = unit[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    r_wire_right = unit[cursor:]

    if cap_output.count(b"$TEROUTPUT") != 1:
        raise RuntimeError("RCL unit cap output marker mismatch.")
    if cap_input.count(b"$TERINPUT") != 1 or l_input.count(b"$TERINPUT") != 1 or r_input.count(b"$TERINPUT") != 1:
        raise RuntimeError("RCL unit input marker mismatch.")
    if l_output.count(b"$TERGROUND") != 1 or r_output.count(b"$TEROUTPUT") != 1:
        raise RuntimeError("RCL unit output marker mismatch.")
    if cap_record.count(b"CAPACITOR") != 1 or l_inductor.count(b"REALIND") != 3 or r_resistor.count(b"RESISTOR") != 2:
        raise RuntimeError("RCL unit component marker mismatch.")
    if len(r_wire_right) not in (WIRE_SIZE, WIRE_SIZE + 1):
        raise RuntimeError(f"Unexpected RCL final right-wire length {len(r_wire_right)}.")

    return UnitTemplates(
        cap_output=cap_output,
        cap_input=cap_input,
        cap_record=cap_record,
        cap_wire_left=cap_wire_left,
        cap_wire_right=cap_wire_right,
        l_input=l_input,
        r_input=r_input,
        l_output=l_output,
        l_inductor=l_inductor,
        l_wire_left=l_wire_left,
        l_wire_right=l_wire_right,
        r_output=r_output,
        r_resistor_prefix=r_resistor_prefix,
        r_resistor=r_resistor,
        r_wire_left=r_wire_left,
        r_wire_right=r_wire_right,
    )


def _load_rcl_unit_templates(project_path: Path) -> RclUnitTemplates:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    expected_min = 1 + rv9.POWER_BRIDGE_CORE_SIZE + 4 * UNIT_SIZE_NONFINAL
    if len(chunk) not in (expected_min, expected_min + 1):
        raise RuntimeError(f"Unexpected 4x RCL donor chunk length {len(chunk)}.")
    if chunk.count(b"$TERPOWER") != 1 or chunk.count(b"$TERINPUT") != 12:
        raise RuntimeError("4x RCL donor marker counts do not match expected unit donor shape.")
    header = chunk[:1]
    bridge_core = chunk[1 : 1 + rv9.POWER_BRIDGE_CORE_SIZE]
    units_start = 1 + rv9.POWER_BRIDGE_CORE_SIZE
    starts = [units_start + index * UNIT_SIZE_NONFINAL for index in range(4)]
    starts.append(len(chunk))
    units = tuple(_split_unit(chunk[starts[index] : starts[index + 1]]) for index in range(4))
    if header != b"\x00" or bridge_core[-1] != 0 or chunk[-1] != 0xFF:
        raise RuntimeError("4x RCL donor stream boundary bytes are unexpected.")
    return RclUnitTemplates(donor_chunk=chunk, header=header, bridge_core=bridge_core, units=units)


def _two_char(prefix: str, index: int) -> str:
    if not (1 <= index <= 35):
        raise ValueError("Two-character labels support indexes 1..35 in the locked R/C/L generator.")
    if index <= 9:
        return f"{prefix}{index}"
    return f"{prefix}{chr(ord('A') + index - 10)}"


def _unit_specs(unit_index: int, *, global_ids: tuple[int, int, int]) -> tuple[RclSpec, RclSpec, RclSpec]:
    col = (unit_index - 1) % 3
    row = (unit_index - 1) // 3
    x = BASE_X + col * GROUP_X_STEP
    y = BASE_Y - row * GROUP_Y_STEP
    node_a = _two_char("A", unit_index)
    node_b = _two_char("B", unit_index)
    c_global_id, l_global_id, r_global_id = global_ids
    cap = RclSpec(
        idx=c_global_id,
        source_ref=f"C{unit_index}",
        ref=_two_char("C", unit_index),
        kind="CAPACITOR",
        value="1uF",
        visible_value="1uF",
        left=node_a,
        right=node_b,
        x=x,
        y=y - SAFE_Y_STEP,
        visual_data={},
    )
    ind = RclSpec(
        idx=l_global_id,
        source_ref=f"L{unit_index}",
        ref=_two_char("L", unit_index),
        kind="INDUCTOR",
        value="5mH",
        visible_value="5mH",
        left=node_b,
        right="G0",
        x=x + SAFE_X_STEP,
        y=y - SAFE_Y_STEP,
        visual_data={},
    )
    res = RclSpec(
        idx=r_global_id,
        source_ref=f"R{unit_index}",
        ref=_two_char("R", unit_index),
        kind="RESISTOR",
        value="10k",
        visible_value="10k",
        left="V0",
        right=node_a,
        x=x,
        y=y,
        visual_data={},
    )
    return cap, ind, res


def _suffixes(unit_index: int) -> dict[str, int]:
    offset = (unit_index - 1) * SUFFIX_STEP
    return {
        "cap_out": (CAP_OUT_SUFFIX_BASE + offset) & 0xFFFF,
        "cap_in": (CAP_IN_SUFFIX_BASE + offset) & 0xFFFF,
        "l_in": (L_IN_SUFFIX_BASE + offset) & 0xFFFF,
        "l_out": (L_OUT_SUFFIX_BASE + offset) & 0xFFFF,
        "r_in": (R_IN_SUFFIX_BASE + offset) & 0xFFFF,
        "r_out": (R_OUT_SUFFIX_BASE + offset) & 0xFFFF,
    }


def _included_components(mode: Mode) -> tuple[str, ...]:
    if mode == "RCL":
        return ("C", "L", "R")
    if mode == "RC":
        return ("C", "R")
    if mode == "LC":
        return ("C", "L")
    if mode == "RL":
        return ("L", "R")
    if mode == "C":
        return ("C",)
    if mode == "R":
        return ("R",)
    if mode == "L":
        return ("L",)
    raise ValueError(mode)


def _last_emitted_group(mode: Mode) -> str:
    if "R" in _included_components(mode):
        return "R"
    if "L" in _included_components(mode):
        return "L"
    return "C"


def _ids_for_groups(groups: tuple[MixedRclGroup, ...]) -> list[dict[str, int]]:
    next_id = 1
    out: list[dict[str, int]] = []
    for item in groups:
        ids: dict[str, int] = {}
        for kind in _included_components(item.mode):
            ids[kind] = next_id
            next_id += 1
        out.append(ids)
    return out


def _label_is_supported(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 2 and value.isascii()


def _value_is_supported(ref: str, value: str) -> bool:
    if not value.isascii():
        return False
    if ref.startswith("R"):
        return len(value) == 3
    if ref.startswith("C"):
        return len(value) == 3
    if ref.startswith("L"):
        return len(value) == 3
    return False


def parse_mixed_rcl_ir(payload: Any) -> tuple[MixedRclCircuitIR | None, list[str]]:
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

    parsed_groups: list[MixedRclGroup] = []
    for index, raw in enumerate(groups_raw, start=1):
        if not isinstance(raw, dict):
            errors.append(f"groups[{index}] must be an object.")
            continue
        mode = raw.get("mode")
        start = raw.get("start")
        end = raw.get("end")
        if mode not in VALID_MODES:
            errors.append(f"groups[{index}].mode must be one of {sorted(VALID_MODES)}.")
            continue
        if not _label_is_supported(start):
            errors.append(f"groups[{index}].start must be exactly two ASCII characters.")
            continue
        if not _label_is_supported(end):
            errors.append(f"groups[{index}].end must be exactly two ASCII characters.")
            continue
        parsed_groups.append(MixedRclGroup(mode=mode, start=start, end=end))  # type: ignore[arg-type]

    if len(parsed_groups) > 35:
        errors.append("The locked R/C/L generator currently supports at most 35 groups.")
    if not any(group.start == "V0" or group.end == "V0" for group in parsed_groups):
        errors.append("At least one group must connect to V0.")
    if not any(group.start == "G0" or group.end == "G0" for group in parsed_groups):
        errors.append("At least one group must connect to G0.")

    schema_version = payload.get("schema_version", SCHEMA_VERSION)
    generator_target = payload.get("generator_target", GENERATOR_TARGET)
    name = project.get("name", "MIXED_RCL_PROJECT")
    output_basename = project.get("output_basename", name)
    component_values_raw = payload.get("component_values", {})
    metadata = payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(schema_version, str):
        errors.append("schema_version must be a string.")
        schema_version = SCHEMA_VERSION
    if not isinstance(generator_target, str):
        errors.append("generator_target must be a string.")
        generator_target = GENERATOR_TARGET
    if not isinstance(name, str) or not name:
        errors.append("project.name must be a non-empty string.")
        name = "MIXED_RCL_PROJECT"
    if not isinstance(output_basename, str) or not output_basename:
        errors.append("project.output_basename must be a non-empty string.")
        output_basename = name
    component_values: dict[str, str] = {}
    if not isinstance(component_values_raw, dict):
        errors.append("component_values must be an object when supplied.")
    else:
        for ref, value in component_values_raw.items():
            if not _label_is_supported(ref):
                errors.append(f"component_values key {ref!r} must be a two-character component reference.")
                continue
            if not isinstance(value, str):
                errors.append(f"component_values[{ref!r}] must be a string.")
                continue
            if not _value_is_supported(ref, value):
                errors.append(
                    f"component_values[{ref!r}]={value!r} is not safe for the current donor record. "
                    "Use exactly 3 ASCII chars for resistors, capacitors, and inductors."
                )
                continue
            component_values[ref] = value
    if not isinstance(metadata, dict):
        errors.append("metadata must be an object.")
        metadata = {}

    if errors:
        return None, errors
    return (
        MixedRclCircuitIR(
            schema_version=schema_version,
            generator_target=generator_target,
            name=name,
            output_basename=output_basename,
            groups=tuple(parsed_groups),
            component_values=component_values,
            metadata=metadata,
        ),
        [],
    )


def validate_mixed_rcl_circuit(ir: MixedRclCircuitIR) -> MixedRclValidationReport:
    errors: list[str] = []
    warnings: list[str] = []
    seen_labels = {node for item in ir.groups for node in (item.start, item.end)}
    for label in seen_labels:
        if not _label_is_supported(label):
            errors.append(f"Unsupported two-character terminal label {label!r}.")
    if any(item.mode not in VALID_MODES for item in ir.groups):
        errors.append("Unsupported group mode found.")
    if len(ir.groups) > 35:
        errors.append("The locked R/C/L generator currently supports at most 35 groups.")
    for ref, value in ir.component_values.items():
        if not _label_is_supported(ref) or not _value_is_supported(ref, value):
            errors.append(f"Unsupported value override {ref}={value!r}.")
    if ir.generator_target != GENERATOR_TARGET:
        warnings.append(f"generator_target is {ir.generator_target!r}; locked target is {GENERATOR_TARGET!r}.")
    return MixedRclValidationReport(errors=tuple(errors), warnings=tuple(warnings), circuit=ir)


def validate_mixed_rcl_payload(payload: Any) -> MixedRclValidationReport:
    ir, issues = parse_mixed_rcl_ir(payload)
    if issues:
        return MixedRclValidationReport(errors=tuple(issues), warnings=(), circuit=None)
    assert ir is not None
    return validate_mixed_rcl_circuit(ir)


def _patch_wire_keep_length(template: bytes, x1: int, y1: int, x2: int, y2: int, *, final: bool) -> bytes:
    record = bytearray(template)
    marker_pos = record.find(b"WIRE")
    if marker_pos < 0:
        raise ValueError("WIRE marker not found in wire template.")
    coord_start = marker_pos + 9
    if coord_start + 16 > len(record):
        raise ValueError(f"WIRE coordinate window exceeds record length: marker={marker_pos} len={len(record)}.")
    record[coord_start : coord_start + 4] = _i32(x1)
    record[coord_start + 4 : coord_start + 8] = _i32(y1)
    record[coord_start + 8 : coord_start + 12] = _i32(x2)
    record[coord_start + 12 : coord_start + 16] = _i32(y2)
    if len(record) == WIRE_SIZE:
        record[-1] = 0xFF if final else 0x00
    elif len(record) == WIRE_SIZE + 1:
        record[-2] = 0x00
        record[-1] = 0xFF if final else 0x00
    return bytes(record)


def _wire_with_optional_final(template: bytes, x1: int, y1: int, x2: int, y2: int, *, final: bool) -> bytes:
    record = template
    if final and len(record) == WIRE_TRIMMED_SIZE:
        record += b"\x00"
    if not final and len(record) == WIRE_SIZE + 1:
        record = record[:-1]
    return _patch_wire_keep_length(record, x1, y1, x2, y2, final=final)


def _patch_native_resistor(template: bytes, spec: RclSpec, global_id: int, in_suffix: int, out_suffix: int) -> bytes:
    raw_ref = spec.ref.encode("ascii")
    raw_value = spec.visible_value.encode("ascii")
    if len(raw_ref) != 2 or not raw_ref.isascii():
        raise ValueError(f"Unsupported resistor ref {spec.ref!r}.")
    if len(raw_value) != 3 or not raw_value.isascii():
        raise ValueError(f"Unsupported resistor visible value {spec.visible_value!r}.")

    record = bytearray(template)
    record[1] = len(raw_ref)
    record[2 : 2 + len(raw_ref)] = raw_ref
    record[69] = len(raw_value)
    record[70 : 70 + len(raw_value)] = raw_value

    value_off = 70 + len(raw_value)
    ref_x, ref_y, value_x, value_y, hidden_x, hidden_y = rv9._label_positions(spec.x, spec.y, 0)
    record[4:8] = _i32(ref_x)
    record[8:12] = _i32(ref_y)
    record[value_off : value_off + 4] = _i32(value_x)
    record[value_off + 4 : value_off + 8] = _i32(value_y)
    record[value_off + 77 : value_off + 81] = _i32(hidden_x)
    record[value_off + 81 : value_off + 85] = _i32(hidden_y)
    record[value_off + 163 : value_off + 167] = _i32(hidden_x)
    record[value_off + 167 : value_off + 171] = _i32(hidden_y)
    record[value_off + 240 : value_off + 244] = _i32(spec.x)
    record[value_off + 244 : value_off + 248] = _i32(spec.y)
    record[value_off + 248 : value_off + 252] = _angle_tenths(0)
    record[value_off + 252 : value_off + 256] = rv9._u32(global_id)
    record[value_off + 265 : value_off + 267] = _u16(in_suffix)
    record[value_off + 267 : value_off + 269] = b"\x01\x00"
    record[value_off + 269 : value_off + 271] = _u16(out_suffix)
    record[value_off + 271 : value_off + 273] = b"\x01\x00"
    record[-1] = 0x00
    return bytes(record)


def _patch_ind_input(template: bytes, label: str, index: int, x: int, y: int, suffix: int) -> bytes:
    left_pin_x = x - 762000
    record, _ = rv9._patch_input(
        template,
        label,
        left_pin_x - 254000,
        y,
        left_pin_x - 635000,
        y,
        index,
        marker=b"$TERINPUT",
    )
    out = bytearray(record)
    out[-4:-2] = _u16(suffix)
    out[-2:] = b"\x01\x00"
    return bytes(out)


def _patch_ind_output(template: bytes, label: str, index: int, x: int, y: int, marker: bytes, suffix: int) -> bytes:
    right_pin_x = x + 762000
    out = bytearray(template)
    marker_pos = out.find(b"$TEROUTPUT")
    old_marker = b"$TEROUTPUT"
    if marker_pos < 0:
        marker_pos = out.find(b"$TERGROUND")
        old_marker = b"$TERGROUND"
    if marker_pos < 0:
        raise ValueError("Output terminal template marker not found.")
    out[marker_pos : marker_pos + len(old_marker)] = marker
    raw_label = label.encode("ascii")
    if len(raw_label) != 2:
        raise ValueError("Output terminal labels must be exactly two ASCII characters.")
    out[1:5] = _i32(right_pin_x + 508000)
    out[5:9] = _i32(y)
    out[31] = 2
    out[32:34] = raw_label
    out[34:38] = _i32(right_pin_x + 889000)
    out[38:42] = _i32(y)
    out[-4:-2] = _u16(suffix)
    out[-2:] = b"\x01\x00"
    return bytes(out)


def _patch_inductor(template: bytes, spec: RclSpec, index: int, in_suffix: int, out_suffix: int) -> bytes:
    raw_ref = spec.ref.encode("ascii")
    raw_value = spec.visible_value.encode("ascii")
    if len(raw_ref) != 2 or len(raw_value) != template[70]:
        raise ValueError(f"Unsupported inductor ref/value for template: {spec.ref} {spec.visible_value}")
    record = bytearray(template)
    record[2] = 2
    record[3:5] = raw_ref
    record[70] = len(raw_value)
    record[71 : 71 + len(raw_value)] = raw_value
    ref_x = spec.x - 528320
    ref_y = spec.y + 274320
    value_x = spec.x - 528320
    value_y = spec.y - 20320
    hidden_x = spec.x - 528320
    hidden_y = spec.y - 274320
    record[5:9] = _i32(ref_x)
    record[9:13] = _i32(ref_y)
    record[74:78] = _i32(value_x)
    record[78:82] = _i32(value_y)
    record[150:154] = _i32(hidden_x)
    record[154:158] = _i32(hidden_y)
    record[264:268] = _i32(hidden_x)
    record[268:272] = _i32(hidden_y)
    record[340:344] = _i32(spec.x)
    record[344:348] = _i32(spec.y)
    record[352:356] = rv9._u32(index)
    record[365:367] = _u16(in_suffix)
    record[367:369] = b"\x01\x00"
    record[369:371] = _u16(out_suffix)
    record[371:373] = b"\x01\x00"
    record[-1] = 0x00
    return bytes(record)


def _make_specs(
    group_item: MixedRclGroup,
    unit_index: int,
    ids: dict[str, int],
    ref_counts: dict[str, int],
    component_values: dict[str, str],
) -> dict[str, RclSpec]:
    dummy = {kind: ids.get(kind, 240 + "CLR".index(kind)) for kind in "CLR"}
    cap, ind, res = _unit_specs(unit_index, global_ids=(dummy["C"], dummy["L"], dummy["R"]))
    internal_1 = _two_char("A", unit_index)
    internal_2 = _two_char("B", unit_index)

    def with_ref(spec: RclSpec, kind: str, left: str, right: str) -> RclSpec:
        ref_counts[kind] += 1
        ref = _two_char(kind, ref_counts[kind])
        value = component_values.get(ref, spec.value)
        return replace(spec, idx=ids[kind], ref=ref, source_ref=ref, value=value, visible_value=value, left=left, right=right)

    if group_item.mode == "RCL":
        return {
            "R": with_ref(res, "R", group_item.start, internal_1),
            "C": with_ref(cap, "C", internal_1, internal_2),
            "L": with_ref(ind, "L", internal_2, group_item.end),
        }
    if group_item.mode == "RC":
        return {
            "R": with_ref(res, "R", group_item.start, internal_1),
            "C": with_ref(cap, "C", internal_1, group_item.end),
        }
    if group_item.mode == "LC":
        return {
            "C": with_ref(cap, "C", group_item.start, internal_1),
            "L": with_ref(ind, "L", internal_1, group_item.end),
        }
    if group_item.mode == "RL":
        return {
            "R": with_ref(res, "R", group_item.start, internal_1),
            "L": with_ref(ind, "L", internal_1, group_item.end),
        }
    if group_item.mode == "C":
        return {"C": with_ref(cap, "C", group_item.start, group_item.end)}
    if group_item.mode == "R":
        return {"R": with_ref(res, "R", group_item.start, group_item.end)}
    if group_item.mode == "L":
        return {"L": with_ref(ind, "L", group_item.start, group_item.end)}
    raise ValueError(group_item.mode)


def _patch_cap(slot: UnitTemplates, spec: RclSpec, suffixes: dict[str, int], *, final: bool) -> bytes:
    cap_dx = spec.x - _s32(slot.cap_record, 332)
    cap_dy = spec.y - _s32(slot.cap_record, 336)
    marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    cap_output = mp._patch_cap_output(slot.cap_output, spec.right, cap_dx, cap_dy, suffixes["cap_out"], marker)
    cap_input = mp._patch_cap_input(slot.cap_input, spec.left, cap_dx, cap_dy, suffixes["cap_in"])
    cap_record = mp._patch_cap_record(
        slot.cap_record,
        spec,
        spec.visible_value,
        spec.x,
        spec.y,
        spec.idx,
        suffixes["cap_in"],
        suffixes["cap_out"],
    )
    cap_wire_left = _wire_with_optional_final(
        slot.cap_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    cap_wire_right = _wire_with_optional_final(
        slot.cap_wire_right,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return cap_output + cap_input + cap_record + cap_wire_left + cap_wire_right


def _patch_l_body(slot: UnitTemplates, spec: RclSpec, suffixes: dict[str, int], *, final: bool) -> bytes:
    marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    l_output = _patch_ind_output(slot.l_output, spec.right, spec.idx, spec.x, spec.y, marker, suffixes["l_out"])
    l_inductor = _patch_inductor(slot.l_inductor, spec, spec.idx, suffixes["l_in"], suffixes["l_out"])
    l_wire_left = _wire_with_optional_final(
        slot.l_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    l_wire_right = _wire_with_optional_final(
        slot.l_wire_right,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return l_output + l_inductor + l_wire_left + l_wire_right


def _patch_r_body(
    slot: UnitTemplates,
    spec: RclSpec,
    templates: RclUnitTemplates,
    suffixes: dict[str, int],
    *,
    final: bool,
) -> bytes:
    marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    r_output = _patch_ind_output(slot.r_output, spec.right, spec.idx, spec.x, spec.y, marker, suffixes["r_out"])
    r_resistor = _patch_native_resistor(slot.r_resistor, spec, spec.idx, suffixes["r_in"], suffixes["r_out"])
    final_wire_template = templates.units[-1].r_wire_right if final else slot.r_wire_right
    if not final and len(final_wire_template) == WIRE_SIZE + 1:
        final_wire_template = final_wire_template[:-1]
    if final and len(final_wire_template) == WIRE_SIZE:
        final_wire_template += b"\x00"
    r_wire_left = _wire_with_optional_final(
        slot.r_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    r_wire_right = _wire_with_optional_final(
        final_wire_template,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return r_output + slot.r_resistor_prefix + r_resistor + r_wire_left + r_wire_right


def _topology_row(kind: str, unit_index: int, spec: RclSpec, suffixes: dict[str, int]) -> dict[str, Any]:
    in_key = {"C": "cap_in", "L": "l_in", "R": "r_in"}[kind]
    out_key = {"C": "cap_out", "L": "l_out", "R": "r_out"}[kind]
    return {
        "idx": spec.idx,
        "unit": unit_index,
        "kind": spec.kind,
        "ref": spec.ref,
        "value": spec.value,
        "left": spec.left,
        "right": spec.right,
        "global_id": spec.idx,
        "in_suffix": f"{suffixes[in_key]:04x}",
        "out_suffix": f"{suffixes[out_key]:04x}",
        "x": spec.x,
        "y": spec.y,
    }


def _patch_group(
    *,
    group_item: MixedRclGroup,
    unit_index: int,
    is_final: bool,
    templates: RclUnitTemplates,
    ids: dict[str, int],
    ref_counts: dict[str, int],
    component_values: dict[str, str],
) -> tuple[bytes, list[RclSpec], list[dict[str, Any]]]:
    slot = templates.units[(unit_index - 1) % len(templates.units)]
    suffixes = _suffixes(unit_index)
    specs = _make_specs(group_item, unit_index, ids, ref_counts, component_values)
    final_kind = _last_emitted_group(group_item.mode) if is_final else ""
    parts: list[bytes] = []
    emitted: list[RclSpec] = []
    topology: list[dict[str, Any]] = []

    if "C" in specs:
        parts.append(_patch_cap(slot, specs["C"], suffixes, final=final_kind == "C"))
        emitted.append(specs["C"])
        topology.append(_topology_row("C", unit_index, specs["C"], suffixes))
    if "L" in specs:
        parts.append(_patch_ind_input(slot.l_input, specs["L"].left, specs["L"].idx, specs["L"].x, specs["L"].y, suffixes["l_in"]))
    if "R" in specs:
        parts.append(_patch_ind_input(slot.r_input, specs["R"].left, specs["R"].idx, specs["R"].x, specs["R"].y, suffixes["r_in"]))
    if "L" in specs:
        parts.append(_patch_l_body(slot, specs["L"], suffixes, final=final_kind == "L"))
        emitted.append(specs["L"])
        topology.append(_topology_row("L", unit_index, specs["L"], suffixes))
    if "R" in specs:
        parts.append(_patch_r_body(slot, specs["R"], templates, suffixes, final=final_kind == "R"))
        emitted.append(specs["R"])
        topology.append(_topology_row("R", unit_index, specs["R"], suffixes))
    return b"".join(parts), emitted, topology


def build_object_chunk(ir: MixedRclCircuitIR, templates: RclUnitTemplates) -> tuple[bytes, list[RclSpec], list[dict[str, Any]], dict[str, Any]]:
    ids_by_group = _ids_for_groups(ir.groups)
    ref_counts = {"C": 0, "L": 0, "R": 0}
    chunks: list[bytes] = []
    specs: list[RclSpec] = []
    topology: list[dict[str, Any]] = []
    for unit_index, (group_item, ids) in enumerate(zip(ir.groups, ids_by_group, strict=True), start=1):
        chunk, group_specs, group_topology = _patch_group(
            group_item=group_item,
            unit_index=unit_index,
            is_final=unit_index == len(ir.groups),
            templates=templates,
            ids=ids,
            ref_counts=ref_counts,
            component_values=ir.component_values,
        )
        chunks.append(chunk)
        specs.extend(group_specs)
        topology.extend(group_topology)
    object_chunk = bytearray(templates.header + templates.bridge_core + b"".join(chunks))
    object_chunk[-1] = 0xFF
    counts = {
        "object_order": "header, V0 bridge, accepted RCL subgroup-removal groups",
        "group_modes": [group_item.mode for group_item in ir.groups],
        "group_count": len(ir.groups),
        "component_count": len(specs),
        "capacitor_count": sum(1 for item in specs if item.kind == "CAPACITOR"),
        "inductor_count": sum(1 for item in specs if item.kind == "INDUCTOR"),
        "resistor_count": sum(1 for item in specs if item.kind == "RESISTOR"),
        "power_bridge_count": 1,
        "ground_terminal_count": _marker_counts(bytes(object_chunk))["$TERGROUND"],
    }
    return bytes(object_chunk), specs, topology, counts


def build_cdb(specs: list[RclSpec]) -> bytes:
    ordered = sorted(specs, key=lambda spec: spec.idx)
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + _enc_str(spec.ref)
        if spec.kind == "CAPACITOR":
            out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if spec.kind == "CAPACITOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _scan_wire_issues(chunk: bytes) -> list[str]:
    issues: list[str] = []
    pos = 0
    while True:
        marker = chunk.find(b"WIRE", pos)
        if marker < 0:
            return issues
        coord_start = marker + 9
        if coord_start + 16 > len(chunk):
            issues.append(f"WIRE coordinate window exceeds stream at marker {marker}")
            return issues
        for offset in range(coord_start, coord_start + 16, 4):
            value = int.from_bytes(chunk[offset : offset + 4], "little", signed=True)
            if abs(value) > 80_000_000:
                issues.append(f"implausible WIRE coordinate {value} at offset {offset}")
        pos = marker + 4


def validate_object_chunk(chunk: bytes, specs: list[RclSpec], topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues = _scan_wire_issues(chunk)
    actual = _marker_counts(chunk)
    expected = {
        "$TERPOWER": counts["power_bridge_count"],
        "CAPACITOR": counts["capacitor_count"],
        "CAP10": counts["capacitor_count"],
        "REALIND": counts["inductor_count"] * 3,
        "RESISTOR": counts["resistor_count"] * 2,
        "COMPONENT ID": counts["component_count"],
        "COMPONENT VALUE": counts["component_count"],
    }
    for marker, want in expected.items():
        if actual[marker] != want:
            issues.append(f"{marker} count {actual[marker]} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if len({spec.ref for spec in specs}) != len(specs):
        issues.append("component refs are not unique")
    if len({spec.idx for spec in specs}) != len(specs):
        issues.append("component global IDs are not unique")
    if len({item["in_suffix"] for item in topology}) != len(topology):
        issues.append("input suffixes are not unique")
    if len({item["out_suffix"] for item in topology}) != len(topology):
        issues.append("output suffixes are not unique")
    return issues


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _component_payload(specs: list[RclSpec]) -> list[dict[str, Any]]:
    return [
        {
            "idx": spec.idx,
            "ref": spec.ref,
            "type": spec.kind,
            "value": spec.value,
            "nodes": [spec.left, spec.right],
            "visual": {"x": spec.x, "y": spec.y},
        }
        for spec in sorted(specs, key=lambda item: item.idx)
    ]


def generate_mixed_rcl_project(
    ir: MixedRclCircuitIR,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> MixedRclGenerationResult:
    registry = registry or FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {', '.join(failed_hashes)}")
    report = validate_mixed_rcl_circuit(ir)
    if not report.valid:
        raise MixedRclGenerationBlocked(report)

    base = registry.get("e001_empty")
    donor = registry.get("rcl_4x_t07_unit_donor")
    templates = _load_rcl_unit_templates(donor.path)
    object_chunk, specs, topology, generation_counts = build_object_chunk(ir, templates)
    cdb = build_cdb(specs)
    dsn, section_pointers = rv9.build_dsn(read_internal_file(base.path, "ROOT.DSN"), read_internal_file(donor.path, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    chunk_issues = validate_object_chunk(object_chunk, specs, topology, generation_counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        chunk_issues.append("ROOT.DSN object chunk differs from requested chunk")

    output_dir = Path(outdir)
    output_dir.mkdir(parents=True, exist_ok=True)
    basename = ir.output_basename
    output_path = output_dir / f"{basename}.pdsprj"
    cdb_path = output_dir / f"{basename}.ROOT.CDB.bin"
    dsn_path = output_dir / f"{basename}.ROOT.DSN.bin"
    chunk_path = output_dir / f"{basename}.OBJECT_CHUNK.bin"
    manifest_path = output_dir / "manifest.json"
    readme_path = output_dir / "README_TEST_FIRST.txt"
    version_path = output_dir / "generator_version.txt"

    write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    version_path.write_text(
        "proteusgen mixed_rcl locked method\n"
        "base_fixture=e001_empty\n"
        "rcl_unit_donor_fixture=rcl_4x_t07_unit_donor\n"
        "method=accepted V16 wire-offset fix + accepted V17 subgroup removal + V19 corrected 21 topology\n",
        encoding="utf-8",
    )

    nodes = list(dict.fromkeys(node for spec in specs for node in (spec.left, spec.right)))
    manifest = {
        "schema_version": ir.schema_version,
        "generator_target": ir.generator_target,
        "status": "locked_current_scope",
        "project_name": ir.name,
        "output_basename": basename,
        "base_project": BASE_PROJECT,
        "base_fixture_id": base.id,
        "rcl_unit_donor_fixture_id": donor.id,
        "component_count_requested": generation_counts["component_count"],
        "component_count_emitted_cdb": len(specs),
        "component_count_emitted_dsn": len(specs),
        "resistor_count": generation_counts["resistor_count"],
        "capacitor_count": generation_counts["capacitor_count"],
        "inductor_count": generation_counts["inductor_count"],
        "node_count_emitted": len(nodes),
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in nodes],
        "group_count": generation_counts["group_count"],
        "group_modes": generation_counts["group_modes"],
        "power_bridge_count": generation_counts["power_bridge_count"],
        "ground_terminal_count": generation_counts["ground_terminal_count"],
        "object_order": generation_counts["object_order"],
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": section_pointers,
        "topology": sorted(topology, key=lambda item: item["idx"]),
        "components": _component_payload(specs),
        "static_validation_issues": chunk_issues,
        "metadata": ir.metadata,
        "component_value_overrides": ir.component_values,
        "known_limitations": [
            "Current main R/C/L generation is group-based and limited to donor-removal blocks.",
            "Terminal labels and generated refs are two ASCII characters.",
            "Current visible value overrides must fit the existing donor record sizes.",
            "The V0 power terminal is emitted through the donor-derived output bridge. Component endpoints use input/output/ground terminals.",
            "Geometry is donor-derived horizontal component blocks; topology is encoded by repeated terminal labels.",
        ],
        "output_files": [
            output_path.name,
            cdb_path.name,
            dsn_path.name,
            chunk_path.name,
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
            "rcl_unit_donor": _sha256_file(donor.path),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    readme_path.write_text(
        f"{basename}\n\n"
        "Open this generated mixed R/C/L project in Proteus 8.13.\n\n"
        f"Project: {output_path.name}\n"
        f"Groups: {generation_counts['group_count']} ({', '.join(generation_counts['group_modes'])})\n"
        f"Components: {len(specs)} ({generation_counts['resistor_count']}R, "
        f"{generation_counts['capacitor_count']}C, {generation_counts['inductor_count']}L)\n"
        f"Static validation issues: {chunk_issues}\n\n"
        "Locked endpoint rules:\n"
        "- V0/power uses the accepted donor-derived $TERPOWER -> $TEROUTPUT bridge.\n"
        "- Component starts use $TERINPUT terminals.\n"
        "- Component ends use $TEROUTPUT, except G0 endpoints use $TERGROUND.\n"
        "- R/C/L, RC, LC, RL, and C-only blocks are made by removing whole subgroups from accepted donor units.\n",
        encoding="utf-8",
    )
    return MixedRclGenerationResult(output_path, cdb_path, dsn_path, chunk_path, manifest_path, readme_path, version_path, manifest)


def generate_mixed_rcl_project_from_payload(
    payload: Any,
    outdir: str | Path,
    *,
    registry: FixtureRegistry | None = None,
) -> MixedRclGenerationResult:
    ir, issues = parse_mixed_rcl_ir(payload)
    if issues:
        raise MixedRclGenerationBlocked(MixedRclValidationReport(errors=tuple(issues), warnings=(), circuit=None))
    assert ir is not None
    return generate_mixed_rcl_project(ir, outdir, registry=registry)


def validate_mixed_rcl_json_file(path: str | Path) -> MixedRclValidationReport:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_mixed_rcl_payload(payload)
