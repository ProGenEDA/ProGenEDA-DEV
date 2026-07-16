"""Donor-native bidirectional DC-voltage source helpers for V2 experiments."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from proteusgen import resistor_v9 as rv9
from proteusgen import source_driven as sd
from proteusgen.pdsprj import read_internal_file

from bidirectional_temp import BidirTemplates, build_bidir_record, extract_bidir_records


@dataclass(frozen=True)
class DcvUnitTemplate:
    positive_terminal: bytes
    negative_terminal: bytes
    source_record: bytes
    wires: bytes
    old_ref: str


def _label(record: bytes) -> str:
    length = record[30]
    return record[31 : 31 + length].decode("ascii")


def _terminal_symbol(record: bytes) -> tuple[int, int]:
    return (
        int.from_bytes(record[1:5], "little", signed=True),
        int.from_bytes(record[5:9], "little", signed=True),
    )


def load_dcv_unit_template(project: Path) -> DcvUnitTemplate:
    chunk = rv9._extract_object_chunk(read_internal_file(project, "ROOT.DSN"))
    terminals = extract_bidir_records(chunk)
    if len(terminals) != 2:
        raise ValueError("The clean one-DCV donor must contain exactly two bidirectional terminals.")
    positive, negative = terminals
    if int.from_bytes(positive[9:13], "little") != 0:
        raise ValueError("The positive DCV donor endpoint must use the 0-degree bidirectional record.")
    if int.from_bytes(negative[9:13], "little") != 1800:
        raise ValueError("The negative DCV donor endpoint must use the 180-degree bidirectional record.")

    ref_position = chunk.find(b"\xff\x02V1")
    first_wire = chunk.find(b"WIRE")
    if ref_position < 0 or first_wire < 0:
        raise ValueError("The clean one-DCV donor is missing its V1 source or wire records.")
    source_start = ref_position - 1
    if source_start != 1 + len(positive) + len(negative):
        raise ValueError("The clean one-DCV donor source unit is not contiguous.")
    return DcvUnitTemplate(
        positive_terminal=positive,
        negative_terminal=negative,
        source_record=chunk[source_start:first_wire],
        wires=chunk[first_wire:-1],
        old_ref="V1",
    )


def _source_suffixes(source_index: int) -> tuple[int, int]:
    base = 0x7000 + (source_index - 1) * 0x80
    return base, base + 0x32


def build_dcv_unit(
    unit: DcvUnitTemplate,
    bidir_templates: BidirTemplates,
    source: sd.SourcePlan,
    *,
    source_index: int,
    global_id: int,
    target: tuple[int, int],
) -> tuple[bytes, dict[str, Any]]:
    out_suffix, in_suffix = _source_suffixes(source_index)
    old_out_suffix = int.from_bytes(unit.positive_terminal[-4:-2], "little")
    old_in_suffix = int.from_bytes(unit.negative_terminal[-4:-2], "little")
    old_positive = _terminal_symbol(unit.positive_terminal)
    old_negative = _terminal_symbol(unit.negative_terminal)
    dx = target[0] - old_positive[0]
    dy = target[1] - old_positive[1]

    positive = build_bidir_record(
        bidir_templates,
        label=source.positive,
        symbol_x=target[0],
        symbol_y=target[1],
        angle_tenths=0,
        suffix=out_suffix,
        active_link=True,
    )
    negative = build_bidir_record(
        bidir_templates,
        label=source.negative,
        symbol_x=old_negative[0] + dx,
        symbol_y=old_negative[1] + dy,
        angle_tenths=1800,
        suffix=in_suffix,
        active_link=True,
    )
    translated_source = sd._translate_block(unit.source_record, dx, dy)
    # The standalone one-source donor stores inactive endpoint-link flags.
    # Generated attached units activate both terminal records and matching
    # source-body links together.
    translated_source = translated_source.replace(
        rv9._u16(old_in_suffix) + b"\x00\x00",
        rv9._u16(old_in_suffix) + b"\x01\x00",
        1,
    ).replace(
        rv9._u16(old_out_suffix) + b"\x00\x00",
        rv9._u16(old_out_suffix) + b"\x01\x00",
        1,
    )
    source_record = sd._patch_dc_source_record(
        translated_source,
        old_ref=unit.old_ref,
        source=source,
        global_id=global_id,
        old_in_suffix=old_in_suffix,
        new_in_suffix=in_suffix,
        old_out_suffix=old_out_suffix,
        new_out_suffix=out_suffix,
    )
    wires = sd._translate_block(unit.wires, dx, dy)
    return positive + negative + source_record + wires, {
        "kind": source.kind,
        "ref": source.ref,
        "value": source.value,
        "positive": source.positive,
        "negative": source.negative,
        "global_id": global_id,
        "target": list(target),
        "positive_angle_tenths": 0,
        "negative_angle_tenths": 1800,
        "donor_native_bidirectional_unit": True,
    }


def build_corrected_dc_cdb(
    passive_specs: list[Any],
    sources: tuple[sd.SourcePlan, ...],
) -> bytes:
    """Build CDB with the DC source pin map observed in manual Proteus donors."""

    first_source_id = len(passive_specs) + 1
    source_rows = [
        sd.SourceRow(
            idx=first_source_id + index,
            ref=source.ref,
            value=source.value,
            model=source.model,
            prop_text=source.prop_text,
        )
        for index, source in enumerate(sources)
    ]
    ordered: list[Any] = [
        *sorted(passive_specs, key=lambda item: item.idx),
        *source_rows,
    ]

    out = bytearray()
    out += rv9._u32(7)
    out += (
        rv9._u32(1)
        + rv9._u32(1)
        + rv9._u32(0)
        + sd._enc_str("ROOT")
        + b"\x00"
        + rv9._u32(0)
        + rv9._u32(1)
        + rv9._u32(1)
    )
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + sd._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += (
        rv9._u32(2)
        + rv9._u32(2)
        + rv9._u32(0)
        + sd._enc_str("Master Sheet")
        + rv9._u32(10)
        + rv9._u32(0)
    )
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + sd._enc_str(spec.ref)
        if isinstance(spec, sd.SourceRow):
            out += rv9._u32(2) + sd._enc_str("+") + sd._enc_str("1") + sd._enc_str("-") + sd._enc_str("2")
        elif spec.kind == "CAPACITOR":
            out += rv9._u32(2) + sd._enc_str("2") + sd._enc_str("2") + sd._enc_str("1") + sd._enc_str("1")
        else:
            out += rv9._u32(2) + sd._enc_str("1") + b"\x00" + sd._enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)

    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + sd._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, sd.SourceRow):
            out += (
                sd._enc_str(spec.ref)
                + sd._enc_str(spec.value)
                + sd._enc_str(spec.model)
                + sd._enc_str("")
                + sd._enc_text(spec.prop_text)
            )
        elif spec.kind == "CAPACITOR":
            out += (
                sd._enc_str(spec.ref)
                + sd._enc_str(spec.value)
                + sd._enc_str("CAP")
                + sd._enc_str("CAP10")
                + sd._enc_text(sd.rcl.mp.CAP_PROP_TEXT)
            )
        elif spec.kind == "INDUCTOR":
            out += (
                sd._enc_str(spec.ref)
                + sd._enc_str(spec.value)
                + sd._enc_str("REALIND")
                + sd._enc_str("")
                + sd._enc_text(sd.rcl.INDUCTOR_PROP_TEXT)
            )
        else:
            out += (
                sd._enc_str(spec.ref)
                + sd._enc_str(spec.value)
                + sd._enc_str("RESISTOR")
                + sd._enc_str("")
                + sd._enc_text(rv9.PROP_TEXT)
            )
    out += rv9._u32(0)
    return bytes(out)
