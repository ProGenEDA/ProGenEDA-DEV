"""Generate the five requested mixed DC-source R/C/L circuits with V13 rules.

V13 is the currently accepted temp method for one mixed VSOURCE/CSOURCE donor:

* source and R/C/L device metadata comes from the working mixed-source donor
* generated R/C/L prefixes use donor suffix remapping
* source blocks are coordinate-relocated, with V0 local to the source
* generated lower-row WIRE coordinate high-byte corruption is repaired

V14 applies those rules to the user's five requested DC mixed-source circuits.
The new variable is source multiplicity: some requested circuits need multiple
voltage sources and/or multiple current sources, so this pack duplicates source
records from the accepted mixed-source donor family.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import MixedRclCircuitIR, MixedRclGroup  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V9_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v9_donor_tail_temp.py"
V13_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v13_v0_source_geometry_temp.py"
OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v14_requested5_v13_method_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V14_REQUESTED5_V13_METHOD_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"

SourceKind = Literal["dc_voltage", "dc_current"]


@dataclass(frozen=True)
class SourcePlan:
    kind: SourceKind
    ref: str
    cdb_value: str
    positive: str
    negative: str = "D0"

    @property
    def model(self) -> str:
        return "VSOURCE" if self.kind == "dc_voltage" else "CSOURCE"

    @property
    def prop_text(self) -> bytes:
        return b"{PRIMITIVE=ANALOG}\n\x00" if self.kind == "dc_voltage" else b"{PRIMITIVE=ANALOGUE}\n\x00"


@dataclass(frozen=True)
class RequestedCase:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    sources: tuple[SourcePlan, ...]
    visible_values: dict[str, str]
    exact_values: dict[str, str]


@dataclass(frozen=True)
class SourceRow:
    idx: int
    ref: str
    value: str
    model: str
    prop_text: bytes


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v9 = _load_module("dc_mixed_sources_v9_for_v14", V9_PATH)
v13 = _load_module("dc_mixed_sources_v13_for_v14", V13_PATH)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _source_suffixes(source_index: int) -> tuple[int, int]:
    base = 0x7000 + (source_index - 1) * 0x80
    return base, base + 0x32


def _patch_terminal_label_suffix(record: bytes, kind: str, label: str, suffix: int) -> bytes:
    raw = label.encode("ascii")
    if not (2 <= len(raw) <= 3) or not raw.isascii():
        raise ValueError(f"Source terminal label must be 2 or 3 ASCII chars, got {label!r}.")
    out = bytearray(record)
    if kind == "OUT":
        length_offset = 31
        label_start = 32
    elif kind == "IN":
        length_offset = 30
        label_start = 31
    else:
        raise ValueError(kind)
    old_len = out[length_offset]
    out = out[:length_offset] + bytearray([len(raw)]) + bytearray(raw) + out[label_start + old_len :]
    out[-4:-2] = rv9._u16(suffix)
    out[-2:] = b"\x01\x00"
    return bytes(out)


def _translate_terminal_record(record: bytes, kind: str, dx: int, dy: int) -> bytes:
    out = bytearray(record)
    v13._translate_terminal(out, 0, len(out), kind, dx, dy)
    return bytes(out)


def _source_templates(donor_chunk: bytes) -> dict[str, bytes]:
    terms = v9._terminal_events(donor_chunk)
    leading_v0 = next(start for start, kind, label in terms if kind == "OUT" and label == "V0")
    next_after_v0 = min(start for start, _kind, _label in terms if start > leading_v0)
    bounds = v13._source_block_bounds(donor_chunk)
    return {
        "v_out": donor_chunk[leading_v0:next_after_v0],
        "v_tail": donor_chunk[bounds["vsource"][0] : bounds["vsource"][1]],
        "c_block": donor_chunk[bounds["csource"][0] : bounds["csource"][1]],
    }


def _split_vsource_tail(block: bytes) -> tuple[bytes, bytes, bytes]:
    ref_pos = block.find(b"\xff\x02V1")
    first_wire = block.find(b"WIRE")
    if ref_pos < 0 or first_wire < 0:
        raise RuntimeError("VSOURCE tail template is missing V1 or WIRE markers.")
    source_start = ref_pos - 1
    return block[:source_start], block[source_start:first_wire], block[first_wire:]


def _split_csource_block(block: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    terms = v9._terminal_events(block)
    if len(terms) != 2 or terms[0][1] != "IN" or terms[1][1] != "OUT":
        raise RuntimeError(f"Unexpected CSOURCE terminal layout: {terms}")
    in_start = terms[0][0]
    out_start = terms[1][0]
    ref_pos = block.find(b"\xff\x02I1")
    first_wire = block.find(b"WIRE")
    if in_start != 0 or ref_pos < 0 or first_wire < 0:
        raise RuntimeError("CSOURCE block template is missing expected markers.")
    source_start = ref_pos - 1
    return block[in_start:out_start], block[out_start:source_start], block[source_start:first_wire], block[first_wire:]


def _patch_source_record(
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
    if len(old_ref) != len(source.ref):
        raise ValueError("Source refs must remain the donor-tested two-character length.")
    if old_ref_pat not in out:
        raise RuntimeError(f"Could not find source ref {old_ref!r}.")
    out = bytearray(bytes(out).replace(old_ref_pat, new_ref_pat, 1))

    final_model = b"\x02\x00\x07" + source.model.encode("ascii")
    model_pos = bytes(out).find(final_model)
    if model_pos < 0:
        raise RuntimeError(f"Could not find final model marker {source.model}.")
    body_coord = model_pos + len(final_model)
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)

    old_value = b"1V" if source.kind == "dc_voltage" else b"1A"
    old_value_pat = b"\xff" + bytes([len(old_value)]) + old_value
    new_value = source.cdb_value.encode("ascii")
    if not new_value.isascii() or len(new_value) > 255:
        raise ValueError(f"Unsupported visible source value {source.cdb_value!r}.")
    new_value_pat = b"\xff" + bytes([len(new_value)]) + new_value
    if old_value_pat not in out:
        raise RuntimeError(f"Could not find source value marker {old_value.decode('ascii')!r}.")
    out = bytearray(bytes(out).replace(old_value_pat, new_value_pat, 1))

    old_in = rv9._u16(old_in_suffix) + b"\x01\x00"
    old_out = rv9._u16(old_out_suffix) + b"\x01\x00"
    new_in = rv9._u16(new_in_suffix) + b"\x01\x00"
    new_out = rv9._u16(new_out_suffix) + b"\x01\x00"
    data = bytes(out)
    if old_in not in data or old_out not in data:
        raise RuntimeError("Source record does not contain donor terminal suffix links.")
    data = data.replace(old_in, new_in, 1).replace(old_out, new_out, 1)
    return data


def _translate_block(block: bytes, dx: int, dy: int) -> bytes:
    out = bytearray(block)
    v13._translate_wires(out, 0, len(out), dx, dy)
    v13._translate_source_text_fields(out, 0, len(out), dx, dy)
    for start, end, kind, _label in v13._terminal_bounds(block):
        v13._translate_terminal(out, start, end, kind, dx, dy)
    return bytes(out)


def _terminal_symbol(record: bytes) -> tuple[int, int]:
    return v13._s32(record, 1), v13._s32(record, 5)


def _body_terminal_positions(chunk: bytes) -> dict[str, list[tuple[int, int]]]:
    positions: dict[str, list[tuple[int, int]]] = {}
    for start, kind, label in v9._terminal_events(chunk):
        if kind not in {"IN", "OUT"}:
            continue
        positions.setdefault(label, []).append((v13._s32(chunk, start + 1), v13._s32(chunk, start + 5)))
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

    output = _translate_terminal_record(output, "OUT", dx, dy)
    input_record = _translate_terminal_record(input_record, "IN", dx, dy)
    source_record = _translate_block(source_record, dx, dy)
    wires = _translate_block(wires, dx, dy)

    output = _patch_terminal_label_suffix(output, "OUT", source.positive, out_suffix)
    input_record = _patch_terminal_label_suffix(input_record, "IN", source.negative, in_suffix)
    source_record = _patch_source_record(
        source_record,
        old_ref="V1",
        source=source,
        global_id=global_id,
        old_in_suffix=old_in_suffix,
        new_in_suffix=in_suffix,
        old_out_suffix=old_out_suffix,
        new_out_suffix=out_suffix,
    )
    return output, input_record + source_record + wires, {
        "kind": source.kind,
        "ref": source.ref,
        "model": source.model,
        "positive": source.positive,
        "negative": source.negative,
        "global_id": global_id,
        "out_suffix": f"{out_suffix:04x}",
        "in_suffix": f"{in_suffix:04x}",
        "target": list(target),
    }


def _build_csource_block(
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

    in_record = _translate_terminal_record(in_record, "IN", dx, dy)
    out_record = _translate_terminal_record(out_record, "OUT", dx, dy)
    source_record = _translate_block(source_record, dx, dy)
    wires = _translate_block(wires, dx, dy)

    in_record = _patch_terminal_label_suffix(in_record, "IN", source.negative, in_suffix)
    out_record = _patch_terminal_label_suffix(out_record, "OUT", source.positive, out_suffix)
    source_record = _patch_source_record(
        source_record,
        old_ref="I1",
        source=source,
        global_id=global_id,
        old_in_suffix=old_in_suffix,
        new_in_suffix=in_suffix,
        old_out_suffix=old_out_suffix,
        new_out_suffix=out_suffix,
    )
    return in_record + out_record + source_record + wires, {
        "kind": source.kind,
        "ref": source.ref,
        "model": source.model,
        "positive": source.positive,
        "negative": source.negative,
        "global_id": global_id,
        "out_suffix": f"{out_suffix:04x}",
        "in_suffix": f"{in_suffix:04x}",
        "target": list(target),
    }


def _source_net_rcl_with_values(
    templates: Any,
    groups: tuple[tuple[str, str, str], ...],
    visible_values: dict[str, str],
) -> tuple[bytes, list[Any], list[dict[str, Any]], dict[str, Any]]:
    ir = MixedRclCircuitIR(
        schema_version=v9.rcl.SCHEMA_VERSION,
        generator_target=v9.rcl.GENERATOR_TARGET,
        name="DCMS_V14_REQUESTED_SOURCE_NET_RCL",
        output_basename="DCMS_V14_REQUESTED_SOURCE_NET_RCL",
        groups=tuple(MixedRclGroup(mode=mode, start=start, end=end) for mode, start, end in groups),
        component_values=visible_values,
        metadata={},
    )
    chunk_with_bridge, specs, topology, counts = v9.rcl.build_object_chunk(ir, templates)
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE
    body = bytearray(chunk_with_bridge[bridge_end:])
    if body.count(b"$TERPOWER") or body.count(b"$TERGROUND"):
        raise RuntimeError("Requested source-net body must not contain power/ground terminal records.")
    body[-1] = 0xFF
    return bytes(b"\x00" + body), specs, topology, {**counts, "power_bridge_count": 0, "source_net_negative": "D0"}


def _build_source_units(
    donor_chunk: bytes,
    source_net_chunk: bytes,
    sources: tuple[SourcePlan, ...],
    first_source_id: int,
) -> tuple[bytes, bytes, list[dict[str, Any]]]:
    templates = _source_templates(donor_chunk)
    positions = _body_terminal_positions(source_net_chunk)
    positive_counts: dict[str, int] = {}
    output_terms: list[bytes] = []
    tail_blocks: list[bytes] = []
    metadata: list[dict[str, Any]] = []
    for source_index, source in enumerate(sources, start=1):
        duplicate_index = positive_counts.get(source.positive, 0)
        positive_counts[source.positive] = duplicate_index + 1
        target = _source_target(source, positions, duplicate_index)
        global_id = first_source_id + source_index - 1
        if source.kind == "dc_voltage":
            output, tail, info = _build_vsource_unit(
                templates,
                source,
                source_index=source_index,
                global_id=global_id,
                target=target,
            )
            output_terms.append(output)
            tail_blocks.append(tail)
            metadata.append(info)
        else:
            block, info = _build_csource_block(
                templates,
                source,
                source_index=source_index,
                global_id=global_id,
                target=target,
            )
            tail_blocks.append(block)
            metadata.append(info)
    return b"".join(output_terms), b"".join(tail_blocks), metadata


def _build_cdb(rcl_specs: list[Any], sources: tuple[SourcePlan, ...], first_source_id: int) -> bytes:
    source_rows = [
        SourceRow(
            idx=first_source_id + index,
            ref=source.ref,
            value=source.cdb_value,
            model=source.model,
            prop_text=source.prop_text,
        )
        for index, source in enumerate(sources)
    ]
    ordered: list[Any] = [*sorted(rcl_specs, key=lambda item: item.idx), *[row for row in source_rows if row.model == "CSOURCE"], *[row for row in source_rows if row.model == "VSOURCE"]]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + v9.v5._enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + v9.v5._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + v9.v5._enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + v9.v5._enc_str(spec.ref)
        if getattr(spec, "kind", "") == "CAPACITOR":
            out += rv9._u32(2) + v9.v5._enc_str("2") + v9.v5._enc_str("2") + v9.v5._enc_str("1") + v9.v5._enc_str("1")
        else:
            out += rv9._u32(2) + v9.v5._enc_str("1") + b"\x00" + v9.v5._enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + v9.v5._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, SourceRow):
            out += v9.v5._enc_str(spec.ref) + v9.v5._enc_str(spec.value) + v9.v5._enc_str(spec.model) + v9.v5._enc_str("") + v9.v5._enc_text(spec.prop_text)
        elif spec.kind == "CAPACITOR":
            out += v9.v5._enc_str(spec.ref) + v9.v5._enc_str(spec.value) + v9.v5._enc_str("CAP") + v9.v5._enc_str("CAP10") + v9.v5._enc_text(v9.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += v9.v5._enc_str(spec.ref) + v9.v5._enc_str(spec.value) + v9.v5._enc_str("REALIND") + v9.v5._enc_str("") + v9.v5._enc_text(v9.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += v9.v5._enc_str(spec.ref) + v9.v5._enc_str(spec.value) + v9.v5._enc_str("RESISTOR") + v9.v5._enc_str("") + v9.v5._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _case_definitions() -> list[RequestedCase]:
    return [
        RequestedCase(
            case_id="DCMS_V14_T01_CIRCUIT_1_12V_2A",
            description="Circuit 1: 12V voltage source, 2A current source, R/C/L branches around nodes B0-C0-D1.",
            sources=(SourcePlan("dc_voltage", "V1", "12V", "DV"), SourcePlan("dc_current", "I1", "2A", "D1")),
            groups=(("R", "DV", "B0"), ("C", "B0", "D0"), ("L", "B0", "C0"), ("R", "C0", "D0"), ("L", "C0", "D1"), ("RC", "D1", "D0")),
            visible_values={"R1": "1k0", "C1": "10u", "L1": "100", "R2": "470", "L2": "220", "C2": "22u", "R3": "100"},
            exact_values={"R1": "1k", "C1": "10uF", "L1": "100mH", "R2": "470", "L2": "220mH", "C2": "22uF", "R3": "100"},
        ),
        RequestedCase(
            case_id="DCMS_V14_T02_CIRCUIT_2_TWO_5V_1A",
            description="Circuit 2: two 5V voltage sources and one 1A current source feeding B0/C0/D1 branch network.",
            sources=(SourcePlan("dc_voltage", "V1", "5V", "DV"), SourcePlan("dc_voltage", "V2", "5V", "D1"), SourcePlan("dc_current", "I1", "1A", "D1")),
            groups=(("R", "DV", "B0"), ("C", "B0", "D0"), ("RC", "B0", "D0"), ("L", "B0", "C0"), ("L", "C0", "D0"), ("R", "C0", "D1"), ("C", "D1", "D0")),
            visible_values={"R1": "050", "C1": "47u", "C2": "10u", "R2": "220", "L1": "50m", "L2": "150", "R3": "330", "C3": "100"},
            exact_values={"R1": "50", "C1": "47uF", "C2": "10uF", "R2": "220", "L1": "50mH", "L2": "150mH", "R3": "330", "C3": "100uF"},
        ),
        RequestedCase(
            case_id="DCMS_V14_T03_CIRCUIT_3_24V_TWO_0A5",
            description="Circuit 3: one 24V voltage source and two 0.5A current sources across an RLC ladder.",
            sources=(SourcePlan("dc_voltage", "V1", "24V", "DV"), SourcePlan("dc_current", "I1", "0.5A", "C0"), SourcePlan("dc_current", "I2", "0.5A", "D1")),
            groups=(("RL", "DV", "B0"), ("C", "B0", "D0"), ("L", "B0", "C0"), ("R", "C0", "D0"), ("C", "C0", "D1"), ("RL", "D1", "D0")),
            visible_values={"R1": "150", "L1": "82m", "C1": "4u7", "L2": "1H0", "R2": "500", "C2": "2u2", "R3": "1k0", "L3": "470"},
            exact_values={"R1": "150", "L1": "82mH", "C1": "4.7uF", "L2": "1H", "R2": "500", "C2": "2.2uF", "R3": "1k", "L3": "470mH"},
        ),
        RequestedCase(
            case_id="DCMS_V14_T04_CIRCUIT_4_TWO_15V_TWO_3A",
            description="Circuit 4: two 15V voltage sources and two 3A current sources across a six-node RLC network.",
            sources=(SourcePlan("dc_voltage", "V1", "15V", "DV"), SourcePlan("dc_voltage", "V2", "15V", "E0"), SourcePlan("dc_current", "I1", "3A", "C0"), SourcePlan("dc_current", "I2", "3A", "E0")),
            groups=(("R", "DV", "B0"), ("RL", "B0", "D0"), ("C", "B0", "C0"), ("C", "C0", "D0"), ("L", "C0", "D1"), ("R", "D1", "D0"), ("C", "D1", "E0")),
            visible_values={"R1": "010", "L1": "330", "R2": "047", "C1": "10u", "C2": "22u", "L2": "100", "R3": "220", "C3": "4u7"},
            exact_values={"R1": "10", "L1": "330mH", "R2": "47", "C1": "10uF", "C2": "22uF", "L2": "100mH", "R3": "220", "C3": "4.7uF"},
        ),
        RequestedCase(
            case_id="DCMS_V14_T05_CIRCUIT_5_THREE_9V_1A5",
            description="Circuit 5: three 9V voltage sources and one 1.5A current source with B0/D1 source nodes.",
            sources=(SourcePlan("dc_voltage", "V1", "9V", "DV"), SourcePlan("dc_voltage", "V2", "9V", "B0"), SourcePlan("dc_voltage", "V3", "9V", "D1"), SourcePlan("dc_current", "I1", "1.5A", "D1")),
            groups=(("L", "DV", "B0"), ("C", "B0", "D0"), ("R", "B0", "C0"), ("LC", "C0", "D0"), ("R", "C0", "D1"), ("C", "D1", "D0")),
            visible_values={"L1": "150", "C1": "10u", "R1": "100", "L2": "470", "C2": "22u", "R2": "470", "C3": "1uF"},
            exact_values={"L1": "150mH", "C1": "10uF", "R1": "100", "L2": "470mH", "C2": "22uF", "R2": "470", "C3": "1uF"},
        ),
    ]


def _make_case(
    case: RequestedCase,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    donor_chunk: bytes,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = _source_net_rcl_with_values(templates, case.groups, case.visible_values)
    first_source_id = len(specs) + 1
    source_outputs, source_tails, source_metadata = _build_source_units(
        donor_chunk,
        source_net_chunk,
        case.sources,
        first_source_id,
    )
    object_chunk = bytearray(b"\x00" + source_outputs + source_net_chunk[1:-1] + source_tails)
    object_chunk[-1] = 0xFF
    object_chunk, wire_repair = v13._repair_generated_negative_wire_high_bytes(bytes(object_chunk))

    cdb_specs = [replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    cdb = _build_cdb(cdb_specs, case.sources, first_source_id)

    manifest = v9._write_case(
        case.case_id,
        case.description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=cdb,
        devices=devices,
        input_payload={
            "description": case.description,
            "sources": source_metadata,
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "rcl_counts": rcl_counts,
            "topology": topology,
            "wire_repair": wire_repair,
        },
    )
    manifest["source_count"] = len(case.sources)
    manifest["rcl_component_count"] = len(specs)
    manifest["source_metadata"] = source_metadata
    (OUT_ROOT / case.case_id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    v9.OUT_ROOT = OUT_ROOT
    v9.ARCHIVE_BASE = ARCHIVE_BASE
    v9.DONOR_ROOT = DONOR_ROOT
    donor = v9._copy_donor()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v9.rcl._load_rcl_unit_templates(rcl_donor)

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_chunk = rv9._extract_object_chunk(donor_dsn)
    devices = v9.v5._device_section_from_dsn(donor_dsn)

    accepted_control = REPO_ROOT / "experiments" / "dc_mixed_sources_v13_v0_source_geometry_temp_2026_06_05" / "DCMS_V13_T05_GROUP4_SOURCES_AND_V0_LOCAL" / "DCMS_V13_T05_GROUP4_SOURCES_AND_V0_LOCAL.pdsprj"
    cases: list[dict[str, Any]] = []
    if accepted_control.exists():
        cases.append(v9._copy_control("DCMS_V14_T00_V13_ACCEPTED_CONTROL", "Accepted V13 group-4 sources+V0-local control.", accepted_control))
    cases.extend(
        _make_case(
            item,
            templates=templates,
            base_project=base_project,
            donor_project=donor,
            donor_chunk=donor_chunk,
            devices=devices,
        )
        for item in _case_definitions()
    )

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V14_REQUESTED5_V13_METHOD_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "User confirmed V13 opens and visuals are good enough.",
        "method": "Requested five circuits using V13 mixed-source donor records, duplicated voltage/current source units, ordinary source-net terminal labels, CDB exact source/component values, and WIRE high-byte repair.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "source_count": item.get("source_count"),
                "rcl_component_count": item.get("rcl_component_count"),
                "marker_counts": item.get("marker_counts"),
                "object_chunk_len": item.get("object_chunk_len"),
                "root_cdb_len": item.get("root_cdb_len"),
                "static_validation_issues": item.get("static_validation_issues"),
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V14_REQUESTED5_V13_METHOD_TEMP_2026_06_05\n\n"
        "Open in order:\n"
        + "\n".join(
            f"{index}. {case_id}.pdsprj" if index == 1 else f"{index}. {case_id}/{case_id}.pdsprj"
            for index, case_id in enumerate(summary["test_order"], start=1)
        )
        + "\n\nT00 is the accepted V13 control. T01-T05 are the five requested mixed DC-source R/C/L circuits.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
