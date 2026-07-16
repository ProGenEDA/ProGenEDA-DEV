"""Generate structurally changed 7490 mixed circuits from golden donors.

V1 proved the all-in-one donor can survive terminal label mutation. This V2
pack intentionally changes more than labels, while avoiding the rejected broad
cross-donor path:

- remove complete 7490 packages from a Proteus-created all-in-one donor,
- remove complete four-gate family blocks from that same donor,
- use the Proteus-created 6x7490 all-in-one donor for extension cases,
- preserve donor ROOT.CDB and device metadata.

No component packet is synthesized. No partial IC/gate record is removed.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.ic_native import (
    bidir_events,
    build_dsn_with_device_section,
    device_section,
    marker_counts,
    patch_bidir_labels,
)
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

REPO = Path(__file__).resolve().parents[4]
DONOR_ROOT = REPO / "proteus/active/evidence/donors/manual_downloads_20260612/ICcombinationfinal/7490"
DONORS = {
    "2x": DONOR_ROOT / "2_7490_withallcombunationaland21RLC.pdsprj",
    "6x": DONOR_ROOT / "6_7490_withallcombunationaland21RLC.pdsprj",
}
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_7490_structural_v2_temp_2026_06_12"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "IC_7490_STRUCTURAL_V2_TEMP_2026_06_12.zip"

MARKERS = (
    b"7490",
    b"74HC00",
    b"74HC02",
    b"74HC08",
    b"74HC32",
    b"74HC86",
    b"74HC266",
    b"RESISTOR",
    b"CAPACITOR",
    b"REALIND",
    b"$TERBIDIR",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"COMPONENT VALUE",
)

FAMILIES = {
    "xor": {"inputs": range(0, 8), "outputs": range(0, 4), "marker": b"74HC86"},
    "or": {"inputs": range(8, 16), "outputs": range(4, 8), "marker": b"74HC32"},
    "xnor": {"inputs": range(16, 24), "outputs": range(8, 12), "marker": b"74HC266"},
    "and": {"inputs": range(24, 32), "outputs": range(12, 16), "marker": b"74HC08"},
    "nor": {"inputs": range(32, 40), "outputs": range(16, 20), "marker": b"74HC02"},
    "nand": {"inputs": range(40, 48), "outputs": range(20, 24), "marker": b"74HC00"},
}
PIN_NAMES = ("CKA", "CKB", "R01", "R02", "R91", "R92", "Q0", "Q1", "Q2", "Q3")


@dataclass(frozen=True)
class OrdinaryTerminal:
    marker: str
    index: int
    start: int
    marker_pos: int
    length_pos: int
    label_pos: int
    length: int
    label: str
    x: int
    y: int

    def key(self) -> tuple[str, int]:
        return self.marker, self.index

    def as_dict(self) -> dict[str, object]:
        return {
            "marker": self.marker,
            "index": self.index,
            "start": self.start,
            "marker_pos": self.marker_pos,
            "length": self.length,
            "label": self.label,
            "x": self.x,
            "y": self.y,
        }


@dataclass(frozen=True)
class RemovalSpan:
    kind: str
    name: str
    start: int
    end: int

    def as_dict(self) -> dict[str, object]:
        return {"kind": self.kind, "name": self.name, "start": self.start, "end": self.end, "size": self.end - self.start}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def ordinary_terminal_events(chunk: bytes) -> list[OrdinaryTerminal]:
    events: list[OrdinaryTerminal] = []
    specs = ((b"$TERINPUT", False), (b"$TEROUTPUT", True), (b"$TERPOWER", False), (b"$TERGROUND", True))
    for marker, output_terminal in specs:
        index = 0
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            length_pos = marker_pos + (17 if output_terminal else 16)
            label_pos = marker_pos + (18 if output_terminal else 17)
            length = chunk[length_pos]
            label = chunk[label_pos : label_pos + length].decode("ascii", errors="replace")
            start = marker_pos - 14
            x = y = 0
            if start >= 0:
                try:
                    x, y = struct.unpack("<ii", chunk[start + 1 : start + 9])
                except struct.error:
                    pass
            events.append(
                OrdinaryTerminal(
                    marker=marker.decode("ascii"),
                    index=index,
                    start=start,
                    marker_pos=marker_pos,
                    length_pos=length_pos,
                    label_pos=label_pos,
                    length=length,
                    label=label,
                    x=x,
                    y=y,
                )
            )
            index += 1
            pos = marker_pos + 1
    return sorted(events, key=lambda item: item.start)


def rlc_start(chunk: bytes) -> int:
    outputs = [event for event in ordinary_terminal_events(chunk) if event.marker == "$TEROUTPUT"]
    if len(outputs) < 25:
        raise ValueError("Expected at least 25 output terminals so RLC start can be identified.")
    return outputs[24].start


def gate_family_spans(chunk: bytes) -> dict[str, RemovalSpan]:
    starts = sorted({match.start() - 3 for match in re.finditer(rb"U\d+:[A-D]", chunk)})
    end = rlc_start(chunk)
    spans: dict[str, RemovalSpan] = {}
    for group_index in range(0, len(starts), 4):
        group = starts[group_index : group_index + 4]
        if len(group) != 4:
            continue
        start = group[0]
        next_start = starts[group_index + 4] if group_index + 4 < len(starts) else end
        block = chunk[start:next_start]
        for family, info in FAMILIES.items():
            if info["marker"] in block:
                spans[family] = RemovalSpan("gate_family", family, start, next_start)
                break
    return spans


def counter_spans(chunk: bytes, counter_count: int) -> list[RemovalSpan]:
    events = bidir_events(chunk)
    if len(events) < counter_count * 10:
        raise ValueError(f"Donor has {len(events)} bider terminals, not enough for {counter_count} 7490 counters.")
    gate_start = min(gate_family_spans(chunk).values(), key=lambda item: item.start).start
    group_starts = [events[index * 10].start for index in range(counter_count)]
    boundaries = sorted({*group_starts, gate_start, len(chunk) - 1})
    spans: list[RemovalSpan] = []
    for index in range(counter_count):
        start = group_starts[index]
        end = next(boundary for boundary in boundaries if boundary > start)
        spans.append(RemovalSpan("counter_package", f"U{index + 1}", start, end))
    return spans


def remove_complete_spans(chunk: bytes, spans: list[RemovalSpan]) -> bytes:
    if not spans:
        return chunk
    filtered = sorted(spans, key=lambda item: item.start)
    for left, right in zip(filtered, filtered[1:]):
        if left.end > right.start:
            raise ValueError(f"Overlapping removal spans: {left} and {right}")
    out = bytearray(chunk)
    for span in sorted(filtered, key=lambda item: item.start, reverse=True):
        del out[span.start : span.end]
    if out[0] != 0:
        raise ValueError("Object chunk prefix was removed; refusal to write malformed chunk.")
    out[-1] = 0xFF
    return bytes(out)


def patch_ordinary_labels(chunk: bytes, replacements: dict[tuple[str, int], str]) -> tuple[bytes, list[dict[str, object]]]:
    out = bytearray(chunk)
    mutations: list[dict[str, object]] = []
    for event in ordinary_terminal_events(chunk):
        new = replacements.get(event.key())
        if new is None:
            continue
        raw = new.encode("ascii")
        if len(raw) != event.length:
            raise ValueError(f"{event.key()} {event.label}->{new} changes terminal record size.")
        out[event.label_pos : event.label_pos + event.length] = raw
        mutations.append({"marker": event.marker, "index": event.index, "old": event.label, "new": new})
    return bytes(out), mutations


def two_char_tokens() -> list[str]:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return [a + b for a in alphabet for b in alphabet if a + b not in {"G0", "V0"}]


def base_gate_labels() -> tuple[list[str], list[str]]:
    tokens = two_char_tokens()
    gate_inputs = [tokens.pop(0) for _ in range(48)]
    gate_outputs = [tokens.pop(0) for _ in range(24)]
    return gate_inputs, gate_outputs


def set_gate(gate_inputs: list[str], gate_outputs: list[str], family: str, gate: int, a: str, b: str, y: str) -> None:
    info = FAMILIES[family]
    input_indexes = list(info["inputs"])
    output_indexes = list(info["outputs"])
    gate_inputs[input_indexes[gate * 2]] = a
    gate_inputs[input_indexes[gate * 2 + 1]] = b
    gate_outputs[output_indexes[gate]] = y


def ordinary_map(gate_inputs: list[str], gate_outputs: list[str], rlc_updates: dict[tuple[str, int], str] | None = None) -> dict[tuple[str, int], str]:
    mapping: dict[tuple[str, int], str] = {}
    for index, label in enumerate(gate_inputs):
        mapping[("$TERINPUT", index)] = label
    for index, label in enumerate(gate_outputs):
        mapping[("$TEROUTPUT", index)] = label
    for key, value in (rlc_updates or {}).items():
        mapping[key] = value
    for key, value in mapping.items():
        if len(value.encode("ascii")) != 2:
            raise ValueError(f"{key} label {value!r} must be exactly two ASCII characters.")
    return mapping


def counter_outputs(prefix: str) -> tuple[str, str, str, str]:
    if len(prefix) != 2 or not prefix[1].isdigit():
        raise ValueError(f"Counter prefix {prefix!r} must be a letter plus a digit, for example A1.")
    base = prefix[0]
    start = int(prefix[1])
    outputs = tuple(f"{base}{start + offset}" for offset in range(4))
    if any(len(label.encode("ascii")) != 2 for label in outputs):
        raise ValueError(f"Counter prefix {prefix!r} produces non-two-character outputs: {outputs}")
    return outputs  # type: ignore[return-value]


def counter_labels(prefix: str, *, clk: str, ckb: str | None = None, reset: str = "G0") -> dict[str, str]:
    q0, q1, q2, q3 = counter_outputs(prefix)
    ckb_net = ckb or q0
    return {
        "CKA": clk,
        "CKB": ckb_net,
        "R01": reset,
        "R02": reset,
        "R91": "G0",
        "R92": "G0",
        "Q0": q0,
        "Q1": q1,
        "Q2": q2,
        "Q3": q3,
    }


def bider_map(counters: list[dict[str, str]], donor_counter_count: int) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for counter_index in range(donor_counter_count):
        nets = counters[counter_index] if counter_index < len(counters) else counter_labels(f"Z{counter_index}", clk="G0")
        for pin_index, pin in enumerate(PIN_NAMES):
            value = nets.get(pin, "G0")
            if len(value.encode("ascii")) != 2:
                raise ValueError(f"7490 net {pin}={value!r} must be exactly two ASCII characters.")
            mapping[counter_index * 10 + pin_index] = value
    return mapping


def post_removal_bider_map(case: dict[str, object]) -> dict[int, str]:
    donor_counter_count = int(case["donor_counter_count"])
    labels = [str(case["bider_replacements"][index]) for index in range(donor_counter_count * 10)]  # type: ignore[index]
    for counter_index in sorted((int(index) for index in case["remove_counters"]), reverse=True):  # type: ignore[index]
        del labels[counter_index * 10 : (counter_index + 1) * 10]
    return {index: label for index, label in enumerate(labels)}


def build_case(
    *,
    case_id: str,
    title: str,
    description: str,
    donor_key: str,
    counter_count: int,
    counters: list[dict[str, str]],
    configure,
    remove_counters: list[int] | None = None,
    remove_families: list[str] | None = None,
    rlc_updates: dict[tuple[str, int], str] | None = None,
) -> dict[str, object]:
    gate_inputs, gate_outputs = base_gate_labels()
    configure(gate_inputs, gate_outputs)
    return {
        "case_id": case_id,
        "title": title,
        "description": description,
        "donor_key": donor_key,
        "donor": DONORS[donor_key],
        "donor_counter_count": counter_count,
        "bider_replacements": bider_map(counters, counter_count),
        "ordinary_replacements": ordinary_map(gate_inputs, gate_outputs, rlc_updates),
        "remove_counters": remove_counters or [],
        "remove_families": remove_families or [],
    }


def ck_chain(prefixes: list[str]) -> list[dict[str, str]]:
    counters: list[dict[str, str]] = []
    clk = "CK"
    for prefix in prefixes:
        counter = counter_labels(prefix, clk=clk)
        counters.append(counter)
        clk = counter["Q3"]
    return counters


CASES = [
    build_case(
        case_id="T01_SINGLE_7490_MOD6_AND_RLC_RESET",
        title="Single 7490 modulo-6 reset with RLC reset shaping",
        description="Removes the second 7490 and unused XNOR/NOR packets. AND decodes Q1/Q2 into reset; NAND/OR/XOR generate monitor taps into the donor RLC network.",
        donor_key="2x",
        counter_count=2,
        counters=[counter_labels("C1", clk="CK", reset="RS"), counter_labels("C2", clk="G0")],
        remove_counters=[1],
        remove_families=["xnor", "nor"],
        configure=lambda gi, go: (
            set_gate(gi, go, "and", 0, "C1", "C2", "RS"),
            set_gate(gi, go, "nand", 0, "C3", "C4", "N1"),
            set_gate(gi, go, "or", 0, "RS", "N1", "O1"),
            set_gate(gi, go, "xor", 0, "O1", "C4", "F1"),
        ),
        rlc_updates={("$TERINPUT", 65): "F1", ("$TERINPUT", 64): "RS", ("$TEROUTPUT", 44): "C4"},
    ),
    build_case(
        case_id="T02_SINGLE_7490_THREE_FAMILY_CLOCK_FILTER",
        title="Single 7490 clock/filter using only XOR OR AND plus RLC",
        description="Removes the second 7490 plus XNOR/NOR/NAND packets. The remaining three logic families create a compact filtered clock/state monitor network.",
        donor_key="2x",
        counter_count=2,
        counters=[counter_labels("D1", clk="CK", reset="G0"), counter_labels("D2", clk="G0")],
        remove_counters=[1],
        remove_families=["xnor", "nor", "nand"],
        configure=lambda gi, go: (
            set_gate(gi, go, "and", 0, "D1", "D4", "A1"),
            set_gate(gi, go, "or", 0, "D2", "D3", "O1"),
            set_gate(gi, go, "xor", 0, "A1", "O1", "F1"),
        ),
        rlc_updates={("$TERINPUT", 48): "A1", ("$TERINPUT", 65): "F1", ("$TEROUTPUT", 40): "D4"},
    ),
    build_case(
        case_id="T03_DUAL_7490_COMPARE_NO_NAND_NOR",
        title="Dual 7490 BCD compare without NAND/NOR packets",
        description="Keeps both counters but removes the NAND and NOR family packets. XOR/XNOR/AND/OR compare selected counter bits and feed RLC monitor branches.",
        donor_key="2x",
        counter_count=2,
        counters=ck_chain(["A1", "B1"]),
        remove_families=["nand", "nor"],
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "A1", "B1", "X1"),
            set_gate(gi, go, "xor", 1, "A2", "B2", "X2"),
            set_gate(gi, go, "xnor", 0, "A3", "B3", "E1"),
            set_gate(gi, go, "and", 0, "X1", "X2", "K1"),
            set_gate(gi, go, "or", 0, "K1", "E1", "M0"),
        ),
        rlc_updates={("$TERINPUT", 57): "M0", ("$TERINPUT", 59): "E1", ("$TERINPUT", 55): "K1"},
    ),
    build_case(
        case_id="T04_DUAL_7490_WINDOW_RESET_NO_XOR_XNOR",
        title="Dual 7490 window reset using AND OR NOR NAND",
        description="Removes XOR and XNOR packets. AND/OR/NOR/NAND decode a windowed reset and drive several RLC taps.",
        donor_key="2x",
        counter_count=2,
        counters=[counter_labels("E1", clk="CK", reset="R1"), counter_labels("F1", clk="E4", reset="R1")],
        remove_families=["xor", "xnor"],
        configure=lambda gi, go: (
            set_gate(gi, go, "and", 0, "E2", "E3", "A1"),
            set_gate(gi, go, "or", 0, "A1", "F2", "O1"),
            set_gate(gi, go, "nor", 0, "O1", "F3", "R1"),
            set_gate(gi, go, "nand", 0, "R1", "F4", "N1"),
        ),
        rlc_updates={("$TERINPUT", 48): "A1", ("$TERINPUT", 64): "R1", ("$TERINPUT", 65): "N1"},
    ),
    build_case(
        case_id="T05_DUAL_7490_AND_NAND_ONLY_RLC",
        title="Dual 7490 decode with only AND and NAND packets",
        description="Removes XOR/OR/XNOR/NOR packets. This leaves a lean AND/NAND counter decoder with RLC reset and output loading.",
        donor_key="2x",
        counter_count=2,
        counters=[counter_labels("G1", clk="CK", reset="R2"), counter_labels("H1", clk="G4", reset="R2")],
        remove_families=["xor", "or", "xnor", "nor"],
        configure=lambda gi, go: (
            set_gate(gi, go, "and", 0, "G2", "G3", "A1"),
            set_gate(gi, go, "and", 1, "H2", "H3", "A2"),
            set_gate(gi, go, "nand", 0, "A1", "A2", "R2"),
            set_gate(gi, go, "nand", 1, "R2", "G4", "F1"),
        ),
        rlc_updates={("$TERINPUT", 48): "A1", ("$TERINPUT", 51): "A2", ("$TERINPUT", 65): "F1"},
    ),
    build_case(
        case_id="T06_SIX_7490_LONG_RIPPLE_FULL_GATES",
        title="Six 7490 long ripple chain with full gate/RLC status logic",
        description="Uses the Proteus-made 6x7490 all-in-one donor. No counters are added by hand; six native packages are already in the donor.",
        donor_key="6x",
        counter_count=6,
        counters=ck_chain(["J1", "K1", "L1", "M1", "N1", "P1"]),
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "J1", "K1", "X1"),
            set_gate(gi, go, "or", 0, "L1", "M1", "O1"),
            set_gate(gi, go, "xnor", 0, "N1", "P1", "E1"),
            set_gate(gi, go, "and", 0, "X1", "O1", "A1"),
            set_gate(gi, go, "nor", 0, "A1", "E1", "NR"),
            set_gate(gi, go, "nand", 0, "NR", "P1", "F1"),
        ),
        rlc_updates={("$TERINPUT", 55): "A1", ("$TERINPUT", 65): "F1", ("$TEROUTPUT", 44): "P1"},
    ),
    build_case(
        case_id="T07_SIX_7490_TRIMMED_LOGIC_BANK",
        title="Six-counter donor trimmed to four active counters with logic bank",
        description="Starts from the 6x donor, removes two complete counter packages and the NOR family, leaving a four-counter logic/RLC bank.",
        donor_key="6x",
        counter_count=6,
        counters=ck_chain(["A5", "B5", "C5", "D5", "E5", "F5"]),
        remove_counters=[4, 5],
        remove_families=["nor"],
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "A5", "B5", "X1"),
            set_gate(gi, go, "xnor", 0, "C5", "D5", "E1"),
            set_gate(gi, go, "and", 0, "X1", "E1", "A1"),
            set_gate(gi, go, "or", 0, "A1", "D5", "O1"),
            set_gate(gi, go, "nand", 0, "O1", "A5", "F1"),
        ),
        rlc_updates={("$TERINPUT", 48): "A1", ("$TERINPUT", 65): "F1", ("$TEROUTPUT", 31): "O1"},
    ),
    build_case(
        case_id="T08_SIX_7490_TWO_BANK_DECODER",
        title="Six 7490 two-bank decoder without XNOR/NAND packets",
        description="Uses all six counter packages but removes XNOR and NAND packets. XOR/OR/AND/NOR combine two counter banks and drive the donor 21RLC taps.",
        donor_key="6x",
        counter_count=6,
        counters=ck_chain(["L1", "M1", "N1", "P1", "Q1", "R1"]),
        remove_families=["xnor", "nand"],
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "L1", "P1", "X1"),
            set_gate(gi, go, "xor", 1, "M1", "Q1", "X2"),
            set_gate(gi, go, "or", 0, "X1", "X2", "O1"),
            set_gate(gi, go, "and", 0, "O1", "R1", "A1"),
            set_gate(gi, go, "nor", 0, "A1", "N1", "F1"),
        ),
        rlc_updates={("$TERINPUT", 48): "A1", ("$TERINPUT", 65): "F1", ("$TEROUTPUT", 37): "M0"},
    ),
    build_case(
        case_id="T09_TWO_7490_STATE_MACHINE_REDUCED_GATES",
        title="Two 7490 state machine with reduced gate packets",
        description="Keeps both counters, removes OR and XNOR, and builds a state-machine style reset/output network with XOR/AND/NOR/NAND.",
        donor_key="2x",
        counter_count=2,
        counters=[counter_labels("P1", clk="CK", reset="R3"), counter_labels("Q1", clk="P4", reset="R3")],
        remove_families=["or", "xnor"],
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "P1", "Q1", "X1"),
            set_gate(gi, go, "and", 0, "P3", "P4", "A1"),
            set_gate(gi, go, "nor", 0, "X1", "A1", "R3"),
            set_gate(gi, go, "nand", 0, "R3", "Q2", "F1"),
        ),
        rlc_updates={("$TERINPUT", 48): "A1", ("$TERINPUT", 64): "R3", ("$TERINPUT", 65): "F1"},
    ),
    build_case(
        case_id="T10_SIX_7490_SPARSE_COUNTER_MIX",
        title="Six-counter donor with sparse package removal and full RLC monitor",
        description="Starts from the 6x donor, removes two interior counter packages and the NAND family, testing package removal away from the donor tail.",
        donor_key="6x",
        counter_count=6,
        counters=ck_chain(["S1", "T1", "U1", "V1", "W1", "Y1"]),
        remove_counters=[1, 3],
        remove_families=["nand"],
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "S1", "T1", "X1"),
            set_gate(gi, go, "or", 0, "U1", "V1", "O1"),
            set_gate(gi, go, "xnor", 0, "W1", "Y1", "E1"),
            set_gate(gi, go, "and", 0, "X1", "O1", "A1"),
            set_gate(gi, go, "nor", 0, "A1", "E1", "F1"),
        ),
        rlc_updates={("$TERINPUT", 48): "A1", ("$TERINPUT", 65): "F1", ("$TEROUTPUT", 43): "Y1"},
    ),
]


def removal_spans_for_case(chunk: bytes, case: dict[str, object]) -> list[RemovalSpan]:
    spans: list[RemovalSpan] = []
    counters = counter_spans(chunk, int(case["donor_counter_count"]))
    for index in case["remove_counters"]:  # type: ignore[index]
        spans.append(counters[int(index)])
    families = gate_family_spans(chunk)
    for family in case["remove_families"]:  # type: ignore[index]
        spans.append(families[str(family)])
    return spans


def expected_markers_for_case(case: dict[str, object]) -> list[bytes]:
    removed = {str(item) for item in case["remove_families"]}  # type: ignore[index]
    out = [b"7490", b"RESISTOR", b"CAPACITOR", b"REALIND", b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT"]
    for family, info in FAMILIES.items():
        if family not in removed:
            out.append(info["marker"])  # type: ignore[arg-type]
    return out


def build_output(case: dict[str, object], case_dir: Path) -> dict[str, object]:
    donor = Path(case["donor"])
    fixture = FixtureRegistry.load().get("e001_empty")
    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)
    spans = removal_spans_for_case(donor_chunk, case)

    object_chunk, ordinary_mutations = patch_ordinary_labels(donor_chunk, case["ordinary_replacements"])  # type: ignore[arg-type]
    object_chunk = remove_complete_spans(object_chunk, spans)
    object_chunk, bider_mutations = patch_bidir_labels(object_chunk, post_removal_bider_map(case))

    base_dsn = read_internal_file(fixture.path, "ROOT.DSN")
    dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, object_chunk, device_section(donor_dsn))
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    output = case_dir / f"{case['case_id']}.pdsprj"
    write_project_from_parts(
        fixture.path,
        output,
        {
            "PROJECT.XML": patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": donor_cdb,
            "SCRIPTS/PWRRAILS.DAT": read_internal_file(donor, "SCRIPTS/PWRRAILS.DAT"),
        },
    )
    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_cdb = read_internal_file(output, "ROOT.CDB")
    final_chunk = _extract_object_chunk(final_dsn)
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required pdsprj internal member")
    for marker in expected_markers_for_case(case):
        if marker not in final_chunk and marker not in final_cdb:
            issues.append(f"expected marker {marker.decode('ascii', errors='replace')} absent")
    for family in case["remove_families"]:  # type: ignore[index]
        raw = FAMILIES[str(family)]["marker"]  # type: ignore[index]
        if raw in final_chunk:
            issues.append(f"removed family marker {raw.decode('ascii')} still present in ROOT.DSN chunk")

    terminals = [event.as_dict() for event in ordinary_terminal_events(final_chunk)]
    terminals.extend(event.as_dict() | {"marker": "$TERBIDIR", "length": len(event.label)} for event in bidir_events(final_chunk))
    terminals = sorted(terminals, key=lambda item: int(item["start"]))

    manifest = {
        "case_id": case["case_id"],
        "title": case["title"],
        "description": case["description"],
        "status": "temporary_pending_user_proteus_testing",
        "method": "golden_donor_complete_packet_removal_and_terminal_label_mutation",
        "donor": str(donor.relative_to(REPO)),
        "removed_spans": [span.as_dict() for span in spans],
        "structural_changes": {
            "removed_counters": case["remove_counters"],
            "removed_gate_families": case["remove_families"],
            "object_chunk_size_before": len(donor_chunk),
            "object_chunk_size_after": len(final_chunk),
            "bytes_removed": len(donor_chunk) - len(final_chunk),
        },
        "section_pointers": pointers,
        "mutations": {"ordinary": ordinary_mutations, "bider": bider_mutations},
        "terminal_counts": {
            "$TERBIDIR": final_chunk.count(b"$TERBIDIR"),
            "$TERINPUT": final_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": final_chunk.count(b"$TEROUTPUT"),
            "$TERPOWER": final_chunk.count(b"$TERPOWER"),
            "$TERGROUND": final_chunk.count(b"$TERGROUND"),
        },
        "marker_counts": marker_counts(final_chunk, [marker.decode("ascii", errors="replace") for marker in MARKERS]),
        "cdb_marker_counts": marker_counts(final_cdb, [marker.decode("ascii", errors="replace") for marker in MARKERS]),
        "static_validation_issues": issues,
        "hashes": {
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(final_dsn),
            "ROOT.CDB": sha256_bytes(final_cdb),
            "object_chunk": sha256_bytes(final_chunk),
        },
    }
    (case_dir / "ROOT.DSN.bin").write_bytes(final_dsn)
    (case_dir / "ROOT.CDB.bin").write_bytes(final_cdb)
    (case_dir / "object_chunk.bin").write_bytes(final_chunk)
    (case_dir / "terminal_plan.json").write_text(json.dumps(terminals, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> None:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
            info.date_time = (2026, 6, 12, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            zf.writestr(info, file_path.read_bytes())


def main() -> int:
    for donor in DONORS.values():
        if not donor.exists():
            raise SystemExit(f"Missing donor: {donor}")
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for case in CASES:
        case_dir = OUT_ROOT / str(case["case_id"])
        case_dir.mkdir(parents=True)
        try:
            manifests.append(build_output(case, case_dir))
        except Exception as exc:  # noqa: BLE001 - keep all diagnostics in temp pack.
            blocked.append({"case_id": case["case_id"], "error": repr(exc)})
    write_archive()
    summary = {
        "pack": "IC_7490_STRUCTURAL_V2_TEMP_2026_06_12",
        "method": "single_golden_donor_packet_removal_or_6x_extension",
        "generated_case_count": len(manifests),
        "blocked": blocked,
        "static_issue_cases": {m["case_id"]: m["static_validation_issues"] for m in manifests if m["static_validation_issues"]},
        "cases": [m["case_id"] for m in manifests],
        "archive": str(ARCHIVE.relative_to(REPO)),
        "archive_sha256": sha256_file(ARCHIVE),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
