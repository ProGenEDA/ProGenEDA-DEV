"""Generate repeated-unit mixed R/C/L diagnostics with fixed wire offsets.

V15 user feedback proved that full-donor terminal-label mutation works, while
V14 generated-coordinate/body mutation causes Bad Object Record and corrupt
pink wire rendering.

The byte-level cause found after V15 is that RCL resistor wire templates place
the WIRE marker one byte later than the capacitor/inductor wire templates:

* C/L wires: WIRE marker at byte 24, coordinates at byte 33
* R wires:   WIRE marker at byte 25, coordinates at byte 34

V14 used a fixed byte-33 coordinate offset for every wire record, corrupting
R wire records. This temporary pack repeats V14 with wire coordinate offsets
derived from the WIRE marker position.
"""

from __future__ import annotations

import json
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_passive as mp
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v16_wire_offset_fix_temp_2026_06_02"

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
    starts = [units_start + i * UNIT_SIZE_NONFINAL for i in range(4)]
    starts.append(len(chunk))
    units = tuple(_split_unit(chunk[starts[i] : starts[i + 1]]) for i in range(4))
    if header != b"\x00" or bridge_core[-1] != 0 or chunk[-1] != 0xFF:
        raise RuntimeError("4x RCL donor stream boundary bytes are unexpected.")
    return RclUnitTemplates(donor_chunk=chunk, header=header, bridge_core=bridge_core, units=units)


def _two_char(prefix: str, index: int) -> str:
    if not (1 <= index <= 35):
        raise ValueError("Two-character labels support indexes 1..35 in this diagnostic.")
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


def _contiguous_global_ids(unit_count: int) -> list[tuple[int, int, int]]:
    return [(3 * index - 2, 3 * index - 1, 3 * index) for index in range(1, unit_count + 1)]


def _supplied_gap_global_ids(unit_count: int) -> list[tuple[int, int, int]]:
    if unit_count != 4:
        raise ValueError("The supplied ID-gap policy is observed only for the 4x donor.")
    return [(1, 2, 3), (6, 7, 8), (9, 10, 11), (12, 13, 14)]


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


def _patch_native_resistor(
    template: bytes,
    spec: RclSpec,
    global_id: int,
    in_suffix: int,
    out_suffix: int,
) -> bytes:
    raw_ref = spec.ref.encode("ascii")
    raw_value = spec.visible_value.encode("ascii")
    if len(raw_ref) != 2 or not raw_ref.isascii():
        raise ValueError(f"Unsupported resistor ref {spec.ref!r}.")
    if len(raw_value) not in (2, 3) or not raw_value.isascii():
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


def _patch_rcl_unit(
    *,
    unit_index: int,
    unit_count: int,
    templates: RclUnitTemplates,
    global_ids: tuple[int, int, int],
) -> tuple[bytes, list[dict[str, Any]]]:
    slot_template = templates.units[(unit_index - 1) % len(templates.units)]
    cap_spec, l_spec, r_spec = _unit_specs(unit_index, global_ids=global_ids)
    c_global_id, l_global_id, r_global_id = global_ids
    suffixes = _suffixes(unit_index)

    cap_dx = cap_spec.x - _s32(slot_template.cap_record, 332)
    cap_dy = cap_spec.y - _s32(slot_template.cap_record, 336)
    cap_output = mp._patch_cap_output(
        slot_template.cap_output,
        cap_spec.right,
        cap_dx,
        cap_dy,
        suffixes["cap_out"],
        b"$TEROUTPUT",
    )
    cap_input = mp._patch_cap_input(slot_template.cap_input, cap_spec.left, cap_dx, cap_dy, suffixes["cap_in"])
    cap_record = mp._patch_cap_record(
        slot_template.cap_record,
        cap_spec,
        cap_spec.visible_value,
        cap_spec.x,
        cap_spec.y,
        c_global_id,
        suffixes["cap_in"],
        suffixes["cap_out"],
    )
    cap_wire_left = _patch_wire_keep_length(
        slot_template.cap_wire_left,
        cap_spec.x - 762000,
        cap_spec.y,
        cap_spec.x - 762000,
        cap_spec.y,
        final=False,
    )
    cap_wire_right = _patch_wire_keep_length(
        slot_template.cap_wire_right,
        cap_spec.x + 1016000,
        cap_spec.y,
        cap_spec.x + 762000,
        cap_spec.y,
        final=False,
    )

    l_input = _patch_ind_input(slot_template.l_input, l_spec.left, l_global_id, l_spec.x, l_spec.y, suffixes["l_in"])
    l_output = _patch_ind_output(
        slot_template.l_output,
        l_spec.right,
        l_global_id,
        l_spec.x,
        l_spec.y,
        b"$TERGROUND",
        suffixes["l_out"],
    )
    l_inductor = _patch_inductor(slot_template.l_inductor, l_spec, l_global_id, suffixes["l_in"], suffixes["l_out"])
    l_wire_left = _patch_wire_keep_length(
        slot_template.l_wire_left,
        l_spec.x - 762000,
        l_spec.y,
        l_spec.x - 762000,
        l_spec.y,
        final=False,
    )
    l_wire_right = _patch_wire_keep_length(
        slot_template.l_wire_right,
        l_spec.x + 1016000,
        l_spec.y,
        l_spec.x + 762000,
        l_spec.y,
        final=False,
    )

    r_input = _patch_ind_input(slot_template.r_input, r_spec.left, r_global_id, r_spec.x, r_spec.y, suffixes["r_in"])
    r_output = _patch_ind_output(
        slot_template.r_output,
        r_spec.right,
        r_global_id,
        r_spec.x,
        r_spec.y,
        b"$TEROUTPUT",
        suffixes["r_out"],
    )
    r_resistor = _patch_native_resistor(slot_template.r_resistor, r_spec, r_global_id, suffixes["r_in"], suffixes["r_out"])
    final_unit = unit_index == unit_count
    final_wire_template = templates.units[-1].r_wire_right if final_unit else slot_template.r_wire_right
    if not final_unit and len(final_wire_template) == WIRE_SIZE + 1:
        final_wire_template = final_wire_template[:-1]
    if final_unit and len(final_wire_template) == WIRE_SIZE:
        final_wire_template += b"\x00"
    r_wire_left = _patch_wire_keep_length(
        slot_template.r_wire_left,
        r_spec.x - 762000,
        r_spec.y,
        r_spec.x - 762000,
        r_spec.y,
        final=False,
    )
    r_wire_right = _patch_wire_keep_length(
        final_wire_template,
        r_spec.x + 1016000,
        r_spec.y,
        r_spec.x + 762000,
        r_spec.y,
        final=final_unit,
    )

    chunk = (
        cap_output
        + cap_input
        + cap_record
        + cap_wire_left
        + cap_wire_right
        + l_input
        + r_input
        + l_output
        + l_inductor
        + l_wire_left
        + l_wire_right
        + r_output
        + slot_template.r_resistor_prefix
        + r_resistor
        + r_wire_left
        + r_wire_right
    )
    maps = [
        {
            "idx": c_global_id,
            "unit": unit_index,
            "kind": cap_spec.kind,
            "ref": cap_spec.ref,
            "value": cap_spec.value,
            "left": cap_spec.left,
            "right": cap_spec.right,
            "global_id": c_global_id,
            "input_marker": "$TERINPUT",
            "output_marker": "$TEROUTPUT",
            "in_suffix": f"{suffixes['cap_in']:04x}",
            "out_suffix": f"{suffixes['cap_out']:04x}",
            "x": cap_spec.x,
            "y": cap_spec.y,
        },
        {
            "idx": l_global_id,
            "unit": unit_index,
            "kind": l_spec.kind,
            "ref": l_spec.ref,
            "value": l_spec.value,
            "left": l_spec.left,
            "right": l_spec.right,
            "global_id": l_global_id,
            "input_marker": "$TERINPUT",
            "output_marker": "$TERGROUND",
            "in_suffix": f"{suffixes['l_in']:04x}",
            "out_suffix": f"{suffixes['l_out']:04x}",
            "x": l_spec.x,
            "y": l_spec.y,
        },
        {
            "idx": r_global_id,
            "unit": unit_index,
            "kind": r_spec.kind,
            "ref": r_spec.ref,
            "value": r_spec.value,
            "left": r_spec.left,
            "right": r_spec.right,
            "global_id": r_global_id,
            "input_marker": "$TERINPUT",
            "output_marker": "$TEROUTPUT",
            "in_suffix": f"{suffixes['r_in']:04x}",
            "out_suffix": f"{suffixes['r_out']:04x}",
            "x": r_spec.x,
            "y": r_spec.y,
        },
    ]
    return chunk, maps


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


def _build_rcl_cdb(specs: list[RclSpec]) -> bytes:
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
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(
                b"{MODFILE=REALIND}\n{RP=1M}\n{ESR=0.2}\n{CP=0.2pF}\n\n\n\x00"
            )
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _build_repeated_unit_chunk(templates: RclUnitTemplates, unit_ids: list[tuple[int, int, int]]) -> tuple[bytes, list[RclSpec], list[dict[str, Any]], dict[str, Any]]:
    chunks: list[bytes] = []
    topology: list[dict[str, Any]] = []
    specs: list[RclSpec] = []
    for unit_index, global_ids in enumerate(unit_ids, start=1):
        unit_chunk, unit_topology = _patch_rcl_unit(
            unit_index=unit_index,
            unit_count=len(unit_ids),
            templates=templates,
            global_ids=global_ids,
        )
        chunks.append(unit_chunk)
        topology.extend(unit_topology)
        specs.extend(_unit_specs(unit_index, global_ids=global_ids))
    object_chunk = bytearray(templates.header + templates.bridge_core + b"".join(chunks))
    object_chunk[-1] = 0xFF
    counts = {
        "object_order": "header, V0 bridge, repeated full C/L/R terminal units from supplied 4x donor",
        "power_bridge_count": 1,
        "unit_count": len(unit_ids),
        "capacitor_count": len(unit_ids),
        "inductor_count": len(unit_ids),
        "resistor_count": len(unit_ids),
        "ground_terminal_count": len(unit_ids),
        "component_count": len(unit_ids) * 3,
    }
    return bytes(object_chunk), specs, topology, counts


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _nodes(specs: list[RclSpec]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _validate_chunk(chunk: bytes, topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    n = counts["unit_count"]
    expected = {
        "$TERPOWER": 1,
        "$TERINPUT": n * 3,
        "$TEROUTPUT": n * 2 + 1,
        "$TERGROUND": n,
        "WIRE": n * 6 + 1,
        "CAPACITOR": n,
        "CAP10": n,
        "REALIND": n * 3,
        "RESISTOR": n * 2,
        "COMPONENT ID": n * 3,
        "COMPONENT VALUE": n * 3,
    }
    actual = _marker_counts(chunk)
    for marker, want in expected.items():
        got = actual[marker]
        if got != want:
            issues.append(f"{marker} count {got} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if len({item["ref"] for item in topology}) != len(topology):
        issues.append("component refs are not unique")
    if len({item["global_id"] for item in topology}) != len(topology):
        issues.append("component global IDs are not unique")
    if len({item["in_suffix"] for item in topology}) != len(topology):
        issues.append("input suffixes are not unique")
    if len({item["out_suffix"] for item in topology}) != len(topology):
        issues.append("output suffixes are not unique")
    return issues


def _payload(case_id: str, specs: list[RclSpec], counts: dict[str, Any], topology: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v16-wire-offset-fix",
        "generator_target": "proteus-8.13-scaled-mixed-rcl-wire-offset-fix-diagnostic",
        "case_id": case_id,
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _nodes(specs)],
        "components": [
            {
                "idx": spec.idx,
                "source_ref": spec.source_ref,
                "ref": spec.ref,
                "type": spec.kind,
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y},
            }
            for spec in sorted(specs, key=lambda item: item.idx)
        ],
        "metadata": {
            "temporary": True,
            "object_order": counts["object_order"],
            "topology": sorted(topology, key=lambda item: item["idx"]),
        },
    }


def _write_repack_case(case_id: str, description: str, source_project: Path) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    project_xml = patch_project_xml_version(read_internal_file(source_project, "PROJECT.XML"), PROTEUS_813)
    dsn = patch_root_dsn_version(read_internal_file(source_project, "ROOT.DSN"), PROTEUS_813)
    cdb = read_internal_file(source_project, "ROOT.CDB")
    output_path = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(source_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    chunk = rv9._extract_object_chunk(dsn)
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v16_control",
        "description": description,
        "source_project": str(source_project.relative_to(REPO_ROOT)),
        "marker_counts": _marker_counts(chunk),
        "object_chunk_len": len(chunk),
        "root_cdb_len": len(cdb),
        "static_validation_issues": [],
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            "object_chunk": rv9._sha256_bytes(chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"{case_id}\n\n{description}\n", encoding="utf-8")
    return manifest


def _write_transplant_control(case_id: str, description: str, base_project: Path, donor_project: Path) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    chunk = rv9._extract_object_chunk(read_internal_file(donor_project, "ROOT.DSN"))
    cdb = read_internal_file(donor_project, "ROOT.CDB")
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_project, "ROOT.DSN"), chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v16_control",
        "description": description,
        "source_project": str(donor_project.relative_to(REPO_ROOT)),
        "marker_counts": _marker_counts(chunk),
        "section_pointer_values": pointers,
        "object_chunk_len": len(chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "static_validation_issues": [],
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            "object_chunk": rv9._sha256_bytes(chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"{case_id}\n\n{description}\n", encoding="utf-8")
    return manifest


def _write_generated_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    templates: RclUnitTemplates,
    unit_ids: list[tuple[int, int, int]],
    id_policy: str,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, specs, topology, counts = _build_repeated_unit_chunk(templates, unit_ids)
    counts["id_policy"] = id_policy
    cdb = _build_rcl_cdb(specs)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_project, "ROOT.DSN"), object_chunk)
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
    issues = _validate_chunk(object_chunk, topology, counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v16_wire_offset_fix_not_locked",
        "description": description,
        "unit_count": counts["unit_count"],
        "component_count": counts["component_count"],
        "resistor_count": counts["resistor_count"],
        "capacitor_count": counts["capacitor_count"],
        "inductor_count": counts["inductor_count"],
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_order": counts["object_order"],
        "id_policy": id_policy,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "topology": sorted(topology, key=lambda item: item["idx"]),
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            chunk_path.name: rv9._sha256_file(chunk_path),
            "object_chunk": rv9._sha256_bytes(object_chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, specs, counts, topology), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Units: {counts['unit_count']} repeated V0-R-C-L-G0 branches\n"
        f"Order: {counts['object_order']}\n"
        f"ID policy: {id_policy}\n"
        f"Static validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _donor_analysis(project_path: Path) -> dict[str, Any]:
    dsn = read_internal_file(project_path, "ROOT.DSN")
    cdb = read_internal_file(project_path, "ROOT.CDB")
    chunk = rv9._extract_object_chunk(dsn)
    return {
        "project": str(project_path.relative_to(REPO_ROOT)),
        "pdsprj_sha256": rv9._sha256_file(project_path),
        "root_dsn_len": len(dsn),
        "root_cdb_len": len(cdb),
        "object_chunk_len": len(chunk),
        "object_chunk_sha256": rv9._sha256_bytes(chunk),
        "root_cdb_sha256": rv9._sha256_bytes(cdb),
        "marker_counts": _marker_counts(chunk),
        "observed_unit_order": "C output, C input+CAP+wires, L input, R input, L ground output+REALIND+wires, R output+RESISTOR+wires",
        "observed_suffix_step_hex": f"{SUFFIX_STEP:04x}",
        "observed_global_ids": [
            {"unit": 1, "C": 1, "L": 2, "R": 3},
            {"unit": 2, "C": 6, "L": 7, "R": 8},
            {"unit": 3, "C": 9, "L": 10, "R": 11},
            {"unit": 4, "C": 12, "L": 13, "R": 14},
        ],
        "final_unit_right_wire_len": len(_load_rcl_unit_templates(project_path).units[-1].r_wire_right),
    }


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")

    base = registry.get("e001_empty").path
    donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = _load_rcl_unit_templates(donor)

    cases: list[dict[str, Any]] = []
    cases.append(_write_repack_case("RCL_V16_T00_EXACT_4X_DONOR_REPACK", "Exact deterministic repack of the user-supplied 4x repeated C/L/R donor.", donor))
    cases.append(_write_transplant_control("RCL_V16_T00B_4X_DONOR_CHUNK_IN_E001", "User-supplied 4x donor object chunk and CDB inserted into the clean E001 base.", base, donor))

    generated_defs: list[tuple[str, str, list[tuple[int, int, int]], str]] = [
        ("RCL_V16_T01_1X_UNIT_CONTIGUOUS_IDS", "One repeated C/L/R unit using donor unit order and marker-derived wire coordinate offsets.", _contiguous_global_ids(1), "contiguous"),
        ("RCL_V16_T02_2X_UNIT_CONTIGUOUS_IDS", "Two repeated C/L/R units using donor unit order and marker-derived wire coordinate offsets.", _contiguous_global_ids(2), "contiguous"),
        ("RCL_V16_T03_3X_UNIT_CONTIGUOUS_IDS", "Three repeated C/L/R units using donor unit order and marker-derived wire coordinate offsets.", _contiguous_global_ids(3), "contiguous"),
        ("RCL_V16_T04_4X_UNIT_CONTIGUOUS_IDS", "Four repeated C/L/R units using contiguous IDs and marker-derived wire coordinate offsets.", _contiguous_global_ids(4), "contiguous"),
        ("RCL_V16_T05_4X_UNIT_SUPPLIED_ID_GAPS", "Four repeated C/L/R units using the exact global ID gaps observed in the supplied donor plus marker-derived wire coordinate offsets.", _supplied_gap_global_ids(4), "supplied_4x_gaps"),
        ("RCL_V16_T06_6X_UNIT_CONTIGUOUS_IDS", "Six repeated C/L/R units using donor unit order and marker-derived wire coordinate offsets.", _contiguous_global_ids(6), "contiguous"),
        ("RCL_V16_T07_7X_UNIT_CONTIGUOUS_IDS", "Seven repeated C/L/R units using donor unit order and marker-derived wire coordinate offsets.", _contiguous_global_ids(7), "contiguous"),
        ("RCL_V16_T08_21X_UNIT_CONTIGUOUS_IDS", "Twenty-one repeated C/L/R units using donor unit order and marker-derived wire coordinate offsets.", _contiguous_global_ids(21), "contiguous"),
    ]
    for case_id, description, unit_ids, id_policy in generated_defs:
        cases.append(
            _write_generated_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_project=donor,
                templates=templates,
                unit_ids=unit_ids,
                id_policy=id_policy,
            )
        )

    summary = {
        "batch_id": "MIXED_RCL_V16_WIRE_OFFSET_FIX_STATIC_20260602",
        "status": "static_generated_awaiting_user_proteus_netlist_test",
        "source_feedback": "V15 showed full-donor label-only mutations work, V14 generated coordinate/body mutation fails, and 1x shortening requires an appended final FF terminator. Byte inspection found V14 patched resistor wire coordinates one byte early.",
        "method": "Use the supplied 4x donor as the repeated-unit record schema. Emit one V0 power bridge, then complete C/L/R terminal units. Patch wire coordinates at WIRE-marker+9 so both C/L marker-byte-24 wires and R marker-byte-25 wires stay structurally valid.",
        "donor_analysis": _donor_analysis(donor),
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "unit_count": item.get("unit_count"),
                "component_count": item.get("component_count"),
                "object_chunk_len": item["object_chunk_len"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "DONOR_ANALYSIS.json").write_text(json.dumps(summary["donor_analysis"], indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V16 wire-offset-fix diagnostic pack.\n\nOpen and run netlist/simulation in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(cases, 1))
        + "\n\nT00 and T00B are controls. If those fail, report that before testing generated cases.\n"
        + "T01-T05 test the corrected wire coordinate offset within the observed 4x donor scale. T06-T08 test extrapolation beyond the observed 4x donor.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V16_WIRE_OFFSET_FIX_TEMP_2026_06_02"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "case_count": len(cases), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
