"""Generate the HC04 NOT and all-seven combinational IC acceptance pack.

This temporary pack uses the accepted donor-derived gate records for:

- 74HC08 AND
- 74HC32 OR
- 74HC00 NAND
- 74HC02 NOR
- 74HC86 XOR
- 74HC266 XNOR candidate
- 74HC04 NOT / inverter

IC signal pins remain directional. Passive endpoints use the accepted
bidirectional terminal conversion. IC package supply pins are hidden by
Proteus and are not emitted as explicit pin 14 / pin 7 wiring.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(os.environ.get("PROTEUSGEN_REPO_ROOT", Path(__file__).resolve().parents[2]))
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen import mixed_rcl as rcl
from proteusgen.bidirectional import convert_production_terminals
from proteusgen.logic_expression import LogicGateStep
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _i32, _sha256_bytes, _u32
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "experiments" / "ic_hc04_all7_v1_temp_2026_06_08"
ARCHIVE_PATH = REPO / "experiments" / "IC_HC04_ALL7_V1_TEMP_2026_06_08.zip"

SCHEMA_VERSION = "ic-combinational-circuit-ir/v0.1"
GENERATOR_TARGET = "proteus-8.13-combinational-ic-locked"

COMBINED_DEVICE_DONOR = REPO / "proteus_ic" / "donors" / "combined" / "ALLL_ICS_ALL4_RLC_HC04_20260608.pdsprj"
HC08_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-08" / "generate_ic_hc08_logic_v1_temp.py"
HC32_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-08" / "generate_ic_hc32_logic_v1_temp.py"

QUAD_GATE_LETTERS = "ABCD"
HEX_GATE_LETTERS = "ABCDEF"
COLUMN_SPACING = 5_080_000
PASSIVE_X_BASE = 22_860_000
PASSIVE_Y_BASE = 4_826_000
PASSIVE_Y_STEP = -1_270_000
HC04_COORD_X_OFFSETS = (1, 32, 103, 136, 213, 285, 360, 425, 551, 618, 626, 668)
HC04_COORD_Y_OFFSETS = tuple(offset + 4 for offset in HC04_COORD_X_OFFSETS)

MARKERS = (
    b"74HC08",
    b"74AND2",
    b"74HC32",
    b"74OR2",
    b"74HC00",
    b"74NAND2",
    b"74HC02",
    b"74NOR2",
    b"74HC86",
    b"74XOR2",
    b"74HC266",
    b"74HC04",
    b"74INV",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERBIDIR",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"COMPONENT VALUE",
    b"RESISTOR",
    b"CAPACITOR",
    b"CAP10",
    b"REALIND",
    b"VSOURCE",
    b"CSOURCE",
    b"VSINE",
    b"LOGICSTATE",
    b"LOGICPROBE",
)


@dataclass(frozen=True)
class FamilyConfig:
    key: str
    device: str
    role: str
    donor: Path
    shape: str
    prop_text: bytes
    pins: dict[str, tuple[tuple[str, str], ...]]
    letters: str
    input_count: int


@dataclass(frozen=True)
class GateSpec:
    family: str
    gate: str
    left: str
    right: str
    output: str
    note: str = ""
    package: str = ""


@dataclass(frozen=True)
class PassiveSpec:
    ref: str
    kind: str
    value: str
    left: str
    right: str


@dataclass(frozen=True)
class CircuitCase:
    case_id: str
    title: str
    expression: str
    description: str
    gates: tuple[GateSpec, ...]
    passives: tuple[PassiveSpec, ...] = ()
    direct_outputs: tuple[dict[str, str], ...] = ()
    warning: str = ""


@dataclass(frozen=True)
class IcCombinationalValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    circuit: CircuitCase | None = None

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
                "case_id": self.circuit.case_id,
                "title": self.circuit.title,
                "gate_count": len(self.circuit.gates),
                "passive_count": len(self.circuit.passives),
                "families": sorted({gate.family for gate in self.circuit.gates}),
            },
        }


@dataclass(frozen=True)
class IcCombinationalGenerationResult:
    output_path: Path
    cdb_path: Path
    dsn_path: Path
    chunk_path: Path
    manifest_path: Path
    plan_path: Path
    circuit_input_path: Path
    manifest: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "output_path": str(self.output_path),
            "root_cdb_path": str(self.cdb_path),
            "root_dsn_path": str(self.dsn_path),
            "object_chunk_path": str(self.chunk_path),
            "manifest_path": str(self.manifest_path),
            "logic_plan_path": str(self.plan_path),
            "circuit_input_path": str(self.circuit_input_path),
            "static_validation_issues": self.manifest["static_validation_issues"],
            "output_hashes": self.manifest["output_hashes"],
        }


class IcCombinationalGenerationBlocked(Exception):
    def __init__(self, report: IcCombinationalValidationReport) -> None:
        super().__init__("Combinational IC CircuitIR cannot be emitted.")
        self.report = report


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HC08 = _load_module("ic_final_hc08_logic_temp", HC08_SCRIPT)
HC32 = _load_module("ic_final_hc32_logic_temp", HC32_SCRIPT)


STANDARD_PINS = {
    "A": (("A", "1"), ("B", "2"), ("Y", "3")),
    "B": (("A", "4"), ("B", "5"), ("Y", "6")),
    "C": (("A", "9"), ("B", "10"), ("Y", "8")),
    "D": (("A", "12"), ("B", "13"), ("Y", "11")),
}
NAND_PINS = {
    "A": (("A", "1"), ("B", "2"), ("Y", "3")),
    "B": (("A", "4"), ("B", "5"), ("Y", "6")),
    "C": (("A", "10"), ("B", "9"), ("Y", "8")),
    "D": (("A", "13"), ("B", "12"), ("Y", "11")),
}
NOR_PINS = {
    "A": (("A", "2"), ("B", "3"), ("Y", "1")),
    "B": (("A", "5"), ("B", "6"), ("Y", "4")),
    "C": (("A", "8"), ("B", "9"), ("Y", "10")),
    "D": (("A", "11"), ("B", "12"), ("Y", "13")),
}
XNOR_PINS = {
    "A": (("A", "1"), ("B", "2"), ("Y", "3")),
    "B": (("A", "5"), ("B", "6"), ("Y", "4")),
    "C": (("A", "8"), ("B", "9"), ("Y", "10")),
    "D": (("A", "12"), ("B", "13"), ("Y", "11")),
}
NOT_PINS = {
    "A": (("A", "1"), ("Y", "2")),
    "B": (("A", "3"), ("Y", "4")),
    "C": (("A", "5"), ("Y", "6")),
    "D": (("A", "9"), ("Y", "8")),
    "E": (("A", "11"), ("Y", "10")),
    "F": (("A", "13"), ("Y", "12")),
}

FAMILIES = {
    "74hc08": FamilyConfig(
        "74hc08",
        "74HC08",
        "AND2",
        REPO / "proteus_ic" / "donors" / "74hc08" / "IC_HC08_M01_ALL4_IO.pdsprj",
        "hc08_script",
        b"{MODFILE=74AND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        STANDARD_PINS,
        QUAD_GATE_LETTERS,
        2,
    ),
    "74hc32": FamilyConfig(
        "74hc32",
        "74HC32",
        "OR2",
        REPO / "proteus_ic" / "donors" / "74hc32" / "IC_HC32_M02_ALL4_IO.pdsprj",
        "hc32_script",
        b"{MODFILE=74OR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        STANDARD_PINS,
        QUAD_GATE_LETTERS,
        2,
    ),
    "74hc00": FamilyConfig(
        "74hc00",
        "74HC00",
        "NAND2",
        REPO / "proteus_ic" / "donors" / "74hc00" / "IC_74HC00_M02_ALL4_IO.pdsprj",
        "terminal_first",
        b"{MODFILE=74NAND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        NAND_PINS,
        QUAD_GATE_LETTERS,
        2,
    ),
    "74hc02": FamilyConfig(
        "74hc02",
        "74HC02",
        "NOR2",
        REPO / "proteus_ic" / "donors" / "74hc02" / "IC_74HC02_M02_ALL4_IO.pdsprj",
        "component_first",
        b"{MODFILE=74NOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        NOR_PINS,
        QUAD_GATE_LETTERS,
        2,
    ),
    "74hc86": FamilyConfig(
        "74hc86",
        "74HC86",
        "XOR2",
        REPO / "proteus_ic" / "donors" / "74hc86" / "IC_74HC86_M02_ALL4_IO.pdsprj",
        "component_first",
        b"{MODFILE=74XOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        STANDARD_PINS,
        QUAD_GATE_LETTERS,
        2,
    ),
    "74hc266": FamilyConfig(
        "74hc266",
        "74HC266",
        "XNOR2 candidate using observed 74XOR2 marker",
        REPO / "proteus_ic" / "donors" / "74hc266" / "IC_74HC266_M02_ALL4_IO.pdsprj",
        "component_first",
        b"{MODFILE=74XOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        XNOR_PINS,
        QUAD_GATE_LETTERS,
        2,
    ),
    "74hc04": FamilyConfig(
        "74hc04",
        "74HC04",
        "NOT1",
        REPO / "proteus_ic" / "donors" / "74hc04" / "IC_74HC04_M04_LOGIC_CONSTANTS_PG.pdsprj",
        "hc04_unary",
        b"{MODFILE=74INV.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        NOT_PINS,
        HEX_GATE_LETTERS,
        1,
    ),
}


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def _validate_label(label: str) -> None:
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError(f"Temporary IC final pack labels must be exactly two ASCII characters: {label!r}")


def _device_section(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise ValueError("ROOT.DSN does not contain the expected device section.")
    return dsn[insert + len(marker) : first]


def _combined_device_section() -> bytes:
    return _device_section(read_internal_file(COMBINED_DEVICE_DONOR, "ROOT.DSN"))


def build_dsn_with_device_section(
    base_dsn: bytes,
    donor_dsn: bytes,
    object_chunk: bytes,
    device_section: bytes,
) -> tuple[bytes, dict[str, int]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise ValueError("Base or donor ROOT.DSN does not match the accepted section model.")
    insert += len(marker)
    dev = bytearray(device_section)
    first_header = donor_dsn[donor_first : donor_obj + len(b"OBJECT DATA")]
    tail = bytearray(base_dsn[e0_second:])
    first_isis = insert + len(dev)
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b"OBJECT DATA")
    object_data_pointer = second_obj + 13
    if len(dev) >= 4:
        dev[-4:] = _u32(object_data_pointer)
    cct = tail.find(b"CCT000")
    if cct != -1:
        tail[cct + len(b"CCT000") + 2 : cct + len(b"CCT000") + 6] = _u32(first_isis)
    default = tail.find(b"__DEFAULT__\x00\x00")
    if default != -1:
        tail[default + len(b"__DEFAULT__\x00\x00") : default + len(b"__DEFAULT__\x00\x00") + 4] = _u32(second_isis)
    dsn = bytes(bytearray(base_dsn[:insert]) + dev + first_header + bytearray(object_chunk) + tail)
    return dsn, {
        "insert": insert,
        "first_isis": first_isis,
        "second_isis": second_isis,
        "second_object_data": second_obj,
        "object_data_pointer": object_data_pointer,
    }


def _donor_chunk(config: FamilyConfig) -> bytes:
    return _extract_object_chunk(read_internal_file(config.donor, "ROOT.DSN"))


def _terminal_starts(chunk: bytes) -> dict[str, int]:
    starts: dict[str, int] = {}
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True)):
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            start = marker_pos - 14
            length_pos = marker_pos + (17 if output_terminal else 16)
            label_pos = marker_pos + (18 if output_terminal else 17)
            length = chunk[length_pos]
            label = chunk[label_pos : label_pos + length].decode("ascii", errors="replace")
            starts[label] = start
            pos = marker_pos + 1
    return starts


def _gate_record_slice(config: FamilyConfig, gate_letter: str) -> bytes:
    chunk = _donor_chunk(config)
    gate_index = config.letters.index(gate_letter)
    if config.shape == "hc04_unary":
        input_starts: list[int] = []
        output_starts: list[int] = []
        pos = 0
        while True:
            marker_pos = chunk.find(b"$TERINPUT", pos)
            if marker_pos < 0:
                break
            input_starts.append(marker_pos - 14)
            pos = marker_pos + 1
        pos = 0
        while True:
            marker_pos = chunk.find(b"$TEROUTPUT", pos)
            if marker_pos < 0:
                break
            output_starts.append(marker_pos - 14)
            pos = marker_pos + 1
        if len(input_starts) < len(config.letters) or len(output_starts) < len(config.letters):
            raise RuntimeError(f"{config.key} donor does not contain all expected unary gate terminals.")
        input_end = input_starts[gate_index + 1] if gate_index + 1 < len(config.letters) else output_starts[0]
        output_end = output_starts[gate_index + 1] if gate_index + 1 < len(config.letters) else len(chunk) - 1
        record = chunk[input_starts[gate_index] : input_end] + chunk[output_starts[gate_index] : output_end]
        if record.count(b"$TERINPUT") != 1 or record.count(b"$TEROUTPUT") != 1 or record.count(b"COMPONENT ID") != 1:
            raise RuntimeError(f"{config.key} gate {gate_letter} slice has unexpected marker counts.")
        return record
    if config.shape == "terminal_first":
        labels = (f"A{gate_index}", f"B{gate_index}", f"Y{gate_index}")
        starts = _terminal_starts(chunk)
        start = min(starts[label] for label in labels)
        if gate_index + 1 < len(config.letters):
            next_labels = (f"A{gate_index + 1}", f"B{gate_index + 1}", f"Y{gate_index + 1}")
            end = min(starts[label] for label in next_labels)
        else:
            end = len(chunk) - 1
    else:
        ref = f"U1:{gate_letter}".encode("ascii")
        ref_pos = chunk.find(ref)
        if ref_pos < 0:
            raise RuntimeError(f"Could not find {ref!r} in {config.donor}.")
        start = ref_pos - 3
        if gate_index + 1 < len(config.letters):
            next_ref = f"U1:{config.letters[gate_index + 1]}".encode("ascii")
            next_ref_pos = chunk.find(next_ref)
            if next_ref_pos < 0:
                raise RuntimeError(f"Could not find {next_ref!r} in {config.donor}.")
            end = next_ref_pos - 3
        else:
            end = len(chunk) - 1
    record = chunk[start:end]
    if record.count(b"$TERINPUT") != config.input_count or record.count(b"$TEROUTPUT") != 1 or record.count(b"COMPONENT ID") != 1:
        raise RuntimeError(f"{config.key} gate {gate_letter} slice has unexpected marker counts.")
    return record


def _patch_terminal_labels(record: bytearray, replacements: dict[str, str]) -> None:
    original = bytes(record)
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True)):
        pos = 0
        while True:
            marker_pos = original.find(marker, pos)
            if marker_pos < 0:
                break
            length_pos = marker_pos + (17 if output_terminal else 16)
            label_pos = marker_pos + (18 if output_terminal else 17)
            length = original[length_pos]
            old = original[label_pos : label_pos + length].decode("ascii", errors="replace")
            new = replacements.get(old)
            if new is not None:
                _validate_label(new)
                raw = new.encode("ascii")
                if len(raw) != length:
                    raise ValueError(f"Label mutation {old}->{new} changes record size.")
                record[label_pos : label_pos + length] = raw
            pos = marker_pos + 1


def _patch_terminal_labels_resizable(record: bytearray, replacements: dict[str, str]) -> None:
    pos = 0
    while True:
        next_input = bytes(record).find(b"$TERINPUT", pos)
        next_output = bytes(record).find(b"$TEROUTPUT", pos)
        marker_positions = [item for item in (next_input, next_output) if item >= 0]
        if not marker_positions:
            break
        marker_pos = min(marker_positions)
        output_terminal = bytes(record)[marker_pos : marker_pos + 10] == b"$TEROUTPUT"
        length_pos = marker_pos + (17 if output_terminal else 16)
        label_pos = marker_pos + (18 if output_terminal else 17)
        length = record[length_pos]
        old = bytes(record[label_pos : label_pos + length]).decode("ascii", errors="replace")
        new = replacements.get(old)
        if new is not None:
            raw = new.encode("ascii")
            if not 1 <= len(raw) <= 8:
                raise ValueError(f"HC04 terminal label must be 1..8 ASCII characters: {new!r}")
            record[length_pos] = len(raw)
            record[label_pos : label_pos + length] = raw
            pos = label_pos + len(raw)
        else:
            pos = marker_pos + 1


def _patch_package_ref(record: bytearray, gate_letter: str, package_ref: str) -> None:
    old = f"U1:{gate_letter}".encode("ascii")
    new = f"{package_ref}:{gate_letter}".encode("ascii")
    if len(old) != len(new):
        raise ValueError("Only U1..U9 package refs are supported in this temporary pack.")
    count = bytes(record).count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {old!r} marker, found {count}.")
    pos = bytes(record).find(old)
    record[pos : pos + len(old)] = new


def _patch_coords(record: bytearray, x_offsets: tuple[int, ...], y_offsets: tuple[int, ...], dx: int, dy: int) -> None:
    for offset in x_offsets:
        if offset + 4 <= len(record):
            value = int.from_bytes(record[offset : offset + 4], "little", signed=True)
            record[offset : offset + 4] = _i32(value + dx)
    for offset in y_offsets:
        if offset + 4 <= len(record):
            value = int.from_bytes(record[offset : offset + 4], "little", signed=True)
            record[offset : offset + 4] = _i32(value + dy)


def _terminal_suffixes(record: bytes) -> tuple[int, int, int]:
    starts: list[int] = []
    marker_positions: list[int] = []
    for marker in (b"$TERINPUT", b"$TERINPUT", b"$TEROUTPUT"):
        search_from = marker_positions[-1] + 1 if marker_positions else 0
        marker_pos = record.find(marker, search_from)
        if marker_pos < 0:
            raise RuntimeError("Could not find terminal marker for suffix patching.")
        marker_positions.append(marker_pos)
        starts.append(marker_pos - 14)
    end_points = [starts[1], starts[2], record.find(b"COMPONENT ID")]
    suffixes: list[int] = []
    for start, end in zip(starts, end_points):
        suffixes.append(int.from_bytes(record[end - 4 : end - 2], "little"))
    return suffixes[0], suffixes[1], suffixes[2]


def _new_suffixes(object_id: int) -> tuple[int, int, int]:
    base = 0x5000 + (object_id - 1) * 0x90
    return base, base + 0x32, base + 0x64


def _patch_terminal_first_ids(record: bytearray, object_id: int) -> dict[str, str]:
    original = bytes(record)
    old_a, old_b, _unused_tail = _terminal_suffixes(original)
    assoc_prefix = old_a.to_bytes(2, "little") + b"\x01\x00" + old_b.to_bytes(2, "little") + b"\x01\x00"
    assoc_pos = original.find(assoc_prefix)
    if assoc_pos < 0:
        raise RuntimeError("Could not find terminal-first suffix association block.")
    old_y_bytes = original[assoc_pos + 8 : assoc_pos + 10]
    new_a, new_b, new_y = _new_suffixes(object_id)
    terminal_starts = []
    marker_positions = []
    for marker in (b"$TERINPUT", b"$TERINPUT", b"$TEROUTPUT"):
        search_from = marker_positions[-1] + 1 if marker_positions else 0
        marker_pos = original.find(marker, search_from)
        marker_positions.append(marker_pos)
        terminal_starts.append(marker_pos - 14)
    terminal_ends = [terminal_starts[1], terminal_starts[2]]
    for end, value in zip(terminal_ends, (new_a, new_b)):
        record[end - 4 : end - 2] = value.to_bytes(2, "little")
    output_search_end = original.find(b"COMPONENT ID")
    output_suffix_pos = original.find(old_y_bytes, terminal_starts[2], output_search_end)
    if output_suffix_pos >= 0:
        record[output_suffix_pos : output_suffix_pos + 2] = new_y.to_bytes(2, "little")
    record[assoc_pos : assoc_pos + 2] = new_a.to_bytes(2, "little")
    record[assoc_pos + 4 : assoc_pos + 6] = new_b.to_bytes(2, "little")
    record[assoc_pos + 8 : assoc_pos + 10] = new_y.to_bytes(2, "little")
    record[assoc_pos - 13 : assoc_pos - 9] = _u32(object_id)
    return {"in1": f"{new_a:04x}", "in2": f"{new_b:04x}", "out": f"{new_y:04x}"}


def _component_shift(record: bytes) -> int:
    first_input = record.find(b"$TERINPUT")
    if first_input < 0:
        return 0
    # HC32 accepted component-first baseline has first $TERINPUT at rel 396.
    return first_input - 396


def _patch_component_first_ids(record: bytearray, object_id: int) -> dict[str, str]:
    shift = _component_shift(bytes(record))
    component_id_offset = 357 + shift
    pin_offsets = {
        "in1": (370 + shift, 481 + shift),
        "in2": (374 + shift, 634 + shift),
        "out": (378 + shift, 788 + shift),
    }
    record[component_id_offset : component_id_offset + 4] = _u32(object_id)
    pin_base = 0x00020000 + (object_id - 1) * 0x400
    pins = {"in1": pin_base, "in2": pin_base + 0x99, "out": pin_base + 0x133}
    for key, value in pins.items():
        raw = _u32(value)
        for offset in pin_offsets[key]:
            if offset + 4 <= len(record):
                record[offset : offset + 4] = raw
    return {key: f"{value:08x}" for key, value in pins.items()}


def _patch_hc04_unary_ids(record: bytearray, object_id: int, gate_letter: str) -> dict[str, str]:
    original = bytes(record)
    input_marker = original.find(b"$TERINPUT")
    output_marker = original.find(b"$TEROUTPUT")
    ref_pos = original.find(f"U1:{gate_letter}".encode("ascii"))
    if min(input_marker, output_marker, ref_pos) < 0:
        raise RuntimeError("Could not find HC04 input/output/component markers for ID patching.")
    output_start = output_marker - 14
    component_start = ref_pos - 3
    old_input = original[output_start - 4 : output_start - 2]
    old_output = original[component_start - 4 : component_start - 2]
    assoc_prefix = old_input + b"\x01\x00" + old_output + b"\x01\x00"
    assoc_pos = original.find(assoc_prefix)
    if assoc_pos < 0:
        raise RuntimeError("Could not find HC04 unary suffix association block.")
    new_input, _unused, new_output = _new_suffixes(object_id)
    record[output_start - 4 : output_start - 2] = new_input.to_bytes(2, "little")
    record[component_start - 4 : component_start - 2] = new_output.to_bytes(2, "little")
    record[assoc_pos : assoc_pos + 2] = new_input.to_bytes(2, "little")
    record[assoc_pos + 4 : assoc_pos + 6] = new_output.to_bytes(2, "little")
    record[assoc_pos - 13 : assoc_pos - 9] = _u32(object_id)
    return {"in": f"{new_input:04x}", "out": f"{new_output:04x}"}


def _generic_gate_record(
    config: FamilyConfig,
    gate: GateSpec,
    *,
    package_ref: str,
    object_id: int,
    dx: int,
    dy: int,
) -> tuple[bytes, dict[str, object]]:
    gate_index = config.letters.index(gate.gate)
    record = bytearray(_gate_record_slice(config, gate.gate))
    if config.shape == "hc04_unary":
        replacements = {config.letters[gate_index] : gate.left, f"Y{gate_index}": gate.output}
        original_len = len(record)
        input_marker = bytes(record).find(b"$TERINPUT")
        input_length_pos = input_marker + 16
        input_label_pos = input_marker + 17
        input_shift_from = input_label_pos + record[input_length_pos]
        _patch_terminal_labels_resizable(record, replacements)
        label_delta = len(record) - original_len
        suffixes = _patch_hc04_unary_ids(record, object_id, gate.gate)
        _patch_package_ref(record, gate.gate, package_ref)
        x_offsets = tuple(offset + label_delta if offset >= input_shift_from else offset for offset in HC04_COORD_X_OFFSETS)
        y_offsets = tuple(offset + label_delta if offset >= input_shift_from else offset for offset in HC04_COORD_Y_OFFSETS)
        _patch_coords(record, x_offsets, y_offsets, dx, dy)
        pin_info = config.pins[gate.gate]
        return bytes(record), {
            "object_id": object_id,
            "family": config.key,
            "role": config.role,
            "device": config.device,
            "package_ref": package_ref,
            "subpart_ref": f"{package_ref}:{gate.gate}",
            "gate_letter": gate.gate,
            "left_net": gate.left,
            "right_net": "",
            "output_net": gate.output,
            "physical_pins": {"input": pin_info[0][1], "output": pin_info[1][1]},
            "ids": suffixes,
            "note": gate.note,
        }
    replacements = {f"A{gate_index}": gate.left, f"B{gate_index}": gate.right, f"Y{gate_index}": gate.output}
    _patch_terminal_labels(record, replacements)
    _patch_package_ref(record, gate.gate, package_ref)
    if config.shape == "terminal_first":
        suffixes = _patch_terminal_first_ids(record, object_id)
        x_offsets = tuple(offset if offset < 313 else offset + 1 for offset in HC08.COORD_X_OFFSETS)
        y_offsets = tuple(offset if offset < 313 else offset + 1 for offset in HC08.COORD_Y_OFFSETS)
    else:
        suffixes = _patch_component_first_ids(record, object_id)
        shift = _component_shift(bytes(record))
        x_offsets = tuple(offset + shift for offset in HC32.COORD_X_OFFSETS)
        y_offsets = tuple(offset + shift for offset in HC32.COORD_Y_OFFSETS)
    _patch_coords(record, x_offsets, y_offsets, dx, dy)
    pin_info = config.pins[gate.gate]
    return bytes(record), {
        "object_id": object_id,
        "family": config.key,
        "role": config.role,
        "device": config.device,
        "package_ref": package_ref,
        "subpart_ref": f"{package_ref}:{gate.gate}",
        "gate_letter": gate.gate,
        "left_net": gate.left,
        "right_net": gate.right,
        "output_net": gate.output,
        "physical_pins": {"left": pin_info[0][1], "right": pin_info[1][1], "output": pin_info[2][1]},
        "ids": suffixes,
        "note": gate.note,
    }


def _script_gate_record(
    config: FamilyConfig,
    gate: GateSpec,
    *,
    package_ref: str,
    package_number: int,
    object_id: int,
    dx: int,
    dy: int,
) -> tuple[bytes, dict[str, object]]:
    step = LogicGateStep(object_id, package_number, gate.left, gate.right, gate.output)
    module = HC08 if config.key == "74hc08" else HC32
    instance = module.GateInstance(
        step=step,
        package_number=package_number,
        gate_letter=gate.gate,
        object_id=object_id,
        dx=dx,
        dy=dy,
    )
    record, row = module.build_gate_record(instance, final=False)
    row["family"] = config.key
    row["role"] = config.role
    row["device"] = config.device
    row["note"] = gate.note
    return record, row


def _package_assignments(gates: tuple[GateSpec, ...]) -> tuple[list[tuple[str, int]], list[dict[str, object]]]:
    assignments: list[tuple[str, int]] = []
    rows: list[dict[str, object]] = []
    explicit: dict[tuple[str, str], int] = {}
    state: dict[str, list[dict[str, object]]] = {}

    def next_package(family: str, package_ref: str | None = None) -> dict[str, object]:
        if package_ref is None:
            package_number = len(rows) + 1
            package_ref = f"U{package_number}"
        else:
            if not package_ref.startswith("U") or not package_ref[1:].isdigit():
                raise ValueError(f"IC package refs must be U1..U9: {package_ref!r}")
            package_number = int(package_ref[1:])
            if package_number > 9:
                raise ValueError("The accepted IC package patcher supports U1..U9.")
        if len(package_ref) != 2:
            raise ValueError("The accepted IC package patcher supports U1..U9.")
        row = {
            "family": family,
            "device": FAMILIES[family].device,
            "package_ref": package_ref,
            "package_number": package_number,
            "used_gates": set(),
        }
        rows.append(row)
        return row

    for gate in gates:
        config = FAMILIES[gate.family]
        if gate.package:
            key = (gate.family, gate.package)
            if key not in explicit:
                explicit[key] = len(rows)
                state.setdefault(gate.family, []).append(next_package(gate.family, gate.package))
            row = rows[explicit[key]]
            used = row["used_gates"]
            assert isinstance(used, set)
            if gate.gate in used:
                raise ValueError(f"Duplicate gate {gate.package}:{gate.gate} in {gate.family}.")
            used.add(gate.gate)
        else:
            family_rows = state.setdefault(gate.family, [])
            if not family_rows:
                family_rows.append(next_package(gate.family))
            row = family_rows[-1]
            used = row["used_gates"]
            assert isinstance(used, set)
            if gate.gate in used or len(used) >= len(config.letters):
                row = next_package(gate.family)
                family_rows.append(row)
                used = row["used_gates"]
                assert isinstance(used, set)
            used.add(gate.gate)
        assignments.append((str(row["package_ref"]), int(row["package_number"])))

    public_rows: list[dict[str, object]] = []
    for row in rows:
        public_rows.append(
            {
                "family": row["family"],
                "device": FAMILIES[str(row["family"])].device,
                "package_ref": row["package_ref"],
                "package_number": row["package_number"],
            }
        )
    return assignments, public_rows


def build_ic_records(case: CircuitCase) -> tuple[bytes, list[dict[str, object]], list[dict[str, object]]]:
    assignments, package_rows = _package_assignments(case.gates)
    records: list[bytes] = []
    topology: list[dict[str, object]] = []
    for object_id, (gate, (package_ref, package_number)) in enumerate(zip(case.gates, assignments), start=1):
        config = FAMILIES[gate.family]
        dx = (package_number - 1) * COLUMN_SPACING
        dy = 0
        if config.shape == "hc08_script" or config.shape == "hc32_script":
            record, row = _script_gate_record(
                config,
                gate,
                package_ref=package_ref,
                package_number=package_number,
                object_id=object_id,
                dx=dx,
                dy=dy,
            )
        else:
            record, row = _generic_gate_record(
                config,
                gate,
                package_ref=package_ref,
                object_id=object_id,
                dx=dx,
                dy=dy,
            )
        records.append(record)
        topology.append(row)
    return b"".join(records), topology, package_rows


def _rcl_spec(index: int, passive: PassiveSpec, object_id: int) -> rcl.RclSpec:
    kind = {"R": "RESISTOR", "C": "CAPACITOR", "L": "INDUCTOR"}[passive.kind]
    return rcl.RclSpec(
        idx=object_id,
        source_ref=passive.ref,
        ref=passive.ref,
        kind=kind,
        value=passive.value,
        visible_value=passive.value,
        left=passive.left,
        right=passive.right,
        x=PASSIVE_X_BASE,
        y=PASSIVE_Y_BASE + (index - 1) * PASSIVE_Y_STEP,
        visual_data={"x": PASSIVE_X_BASE, "y": PASSIVE_Y_BASE + (index - 1) * PASSIVE_Y_STEP},
    )


def build_passive_chunk(case: CircuitCase, first_object_id: int) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, object]], list[dict[str, object]], list[str]]:
    if not case.passives:
        return b"", [], [], [], []
    registry = FixtureRegistry.load()
    donor = registry.get("rcl_4x_t07_unit_donor")
    templates = rcl._load_rcl_unit_templates(donor.path)
    records: list[bytes] = []
    specs: list[rcl.RclSpec] = []
    topology: list[dict[str, object]] = []
    for unit_index, passive in enumerate(case.passives, start=1):
        spec = _rcl_spec(unit_index, passive, first_object_id + unit_index - 1)
        slot = templates.units[(unit_index - 1) % len(templates.units)]
        suffixes = rcl._suffixes(unit_index)
        final = unit_index == len(case.passives)
        if passive.kind == "R":
            records.append(
                rcl._patch_ind_input(slot.r_input, spec.left, spec.idx, spec.x, spec.y, suffixes["r_in"])
                + rcl._patch_r_body(slot, spec, templates, suffixes, final=final)
            )
            in_key, out_key = "r_in", "r_out"
        elif passive.kind == "C":
            records.append(rcl._patch_cap(slot, spec, suffixes, final=final))
            in_key, out_key = "cap_in", "cap_out"
        elif passive.kind == "L":
            records.append(
                rcl._patch_ind_input(slot.l_input, spec.left, spec.idx, spec.x, spec.y, suffixes["l_in"])
                + rcl._patch_l_body(slot, spec, suffixes, final=final)
            )
            in_key, out_key = "l_in", "l_out"
        else:
            raise ValueError(passive.kind)
        specs.append(spec)
        topology.append(
            {
                "idx": spec.idx,
                "unit": unit_index,
                "kind": spec.kind,
                "ref": spec.ref,
                "value": spec.value,
                "left": spec.left,
                "right": spec.right,
                "in_suffix": f"{suffixes[in_key]:04x}",
                "out_suffix": f"{suffixes[out_key]:04x}",
                "x": spec.x,
                "y": spec.y,
            }
        )
    original_chunk = bytearray(templates.header + templates.bridge_core + b"".join(records))
    original_chunk[-1] = 0xFF
    chunk_issues = rcl._scan_wire_issues(bytes(original_chunk))
    converted, replacements, conversion_issues = convert_production_terminals(bytes(original_chunk), registry)
    return converted, specs, topology, [item.__dict__ for item in replacements], chunk_issues + conversion_issues


def build_object_chunk(case: CircuitCase) -> tuple[bytes, list[dict[str, object]], list[dict[str, object]], list[rcl.RclSpec], list[dict[str, object]], list[dict[str, object]], list[str]]:
    ic_records, ic_topology, package_rows = build_ic_records(case)
    passive_chunk, passive_specs, passive_topology, replacements, issues = build_passive_chunk(case, len(case.gates) + 1)
    if passive_chunk:
        if passive_chunk[0] != 0:
            issues.append("converted passive chunk does not start with object header 00")
        object_chunk = b"\x00" + ic_records + passive_chunk[1:]
    else:
        object_chunk = b"\x00" + ic_records + b"\xff"
    if object_chunk[-1] != 0xFF:
        issues.append("combined object chunk final byte is not FF")
    return object_chunk, ic_topology, package_rows, passive_specs, passive_topology, replacements, issues


def build_cdb(ic_topology: list[dict[str, object]], package_rows: list[dict[str, object]], passive_specs: list[rcl.RclSpec]) -> bytes:
    out = bytearray()
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + _enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + _enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + _enc_str("Master Sheet") + _u32(10) + _u32(0)

    out += _u32(len(ic_topology) + len(passive_specs))
    for row in ic_topology:
        object_id = int(row["object_id"])
        package_number = int(row["package_ref"][1:])
        gate_letter = str(row["gate_letter"])
        config = FAMILIES[str(row["family"])]
        pins = config.pins[gate_letter]
        out += _u32(object_id) + _u32(1) + _u32(0) + _u32(object_id)
        out += _enc_str(str(row["subpart_ref"])) + _u32(len(pins))
        for logical, physical in pins:
            out += _enc_str(logical) + _enc_str(physical)
        out += _u32(0) + _u32(package_number) + _u32(config.letters.index(gate_letter))
    for spec in sorted(passive_specs, key=lambda item: item.idx):
        out += _u32(spec.idx) + _u32(1) + _u32(0) + _u32(spec.idx) + _enc_str(spec.ref)
        if spec.kind == "CAPACITOR":
            out += _u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += _u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += _u32(0) + _u32(spec.idx) + _u32(0)

    out += _u32(1) + _u32(1) + b"\x00" + _enc_str("") + _u32(1)
    out += _u32(len(package_rows) + len(passive_specs))
    for row in package_rows:
        config = FAMILIES[str(row["family"])]
        package_number = int(row["package_number"])
        package_ref = str(row["package_ref"])
        out += _u32(package_number) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        out += _enc_str(package_ref) + _enc_str(config.device) + _enc_str(config.device) + _enc_str("DIL14")
        out += _enc_text(config.prop_text)
    for spec in sorted(passive_specs, key=lambda item: item.idx):
        out += _u32(spec.idx) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        if spec.kind == "CAPACITOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(rcl.INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rcl.rv9.PROP_TEXT)
    out += _u32(0)
    return bytes(out)


def static_issues(
    output: Path,
    case: CircuitCase,
    object_chunk: bytes,
    cdb: bytes,
    passive_specs: list[rcl.RclSpec],
    build_issues: list[str],
) -> list[str]:
    issues = list(build_issues)
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(output, "ROOT.DSN")
    if _extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from generated chunk")
    if not object_chunk or object_chunk[0] != 0 or object_chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    expected_inputs = sum(FAMILIES[gate.family].input_count for gate in case.gates)
    if object_chunk.count(b"$TERINPUT") != expected_inputs:
        issues.append("$TERINPUT count does not match expected IC input pins")
    if object_chunk.count(b"$TEROUTPUT") != len(case.gates):
        issues.append("$TEROUTPUT count does not match one output per gate")
    if object_chunk.count(b"COMPONENT ID") != len(case.gates) + len(passive_specs):
        issues.append("COMPONENT ID count does not match gate plus passive component count")
    if case.passives:
        endpoint_labels = [label for passive in case.passives for label in (passive.left, passive.right)]
        min_bidir = sum(1 for label in endpoint_labels if label not in {"V0", "G0"})
        if object_chunk.count(b"$TERBIDIR") < min_bidir:
            issues.append("$TERBIDIR count is below expected non-special passive endpoints")
        if object_chunk.count(b"$TERPOWER") != 1:
            issues.append("mixed passive case should contain one donor-derived power bridge")
        expected_ground = endpoint_labels.count("G0")
        if object_chunk.count(b"$TERGROUND") != expected_ground:
            issues.append("$TERGROUND count does not match G0 passive endpoint count")
    else:
        for marker in (b"$TERBIDIR", b"$TERPOWER", b"$TERGROUND"):
            if object_chunk.count(marker):
                issues.append(f"pure IC case contains unexpected {marker.decode('ascii')} marker")
    for forbidden in (b"VSOURCE", b"CSOURCE", b"VSINE", b"LOGICSTATE", b"LOGICPROBE"):
        if object_chunk.count(forbidden):
            issues.append(f"unexpected marker {forbidden.decode('ascii')}")
    for row in set(f"{item['package_ref']}:{item['gate_letter']}" for item in _gate_refs_from_chunk_plan(case)):
        if cdb.count(row.encode("ascii")) != 1:
            issues.append(f"CDB missing subpart row {row}")
    return issues


def _gate_refs_from_chunk_plan(case: CircuitCase) -> list[dict[str, str]]:
    assignments, _package_rows = _package_assignments(case.gates)
    rows: list[dict[str, str]] = []
    for gate, (package_ref, _package_number) in zip(case.gates, assignments):
        rows.append({"package_ref": package_ref, "gate_letter": gate.gate})
    return rows


def write_case(case: CircuitCase, out_root: Path | None = None) -> dict[str, object]:
    object_chunk, ic_topology, package_rows, passive_specs, passive_topology, replacements, build_issues = build_object_chunk(case)
    cdb = build_cdb(ic_topology, package_rows, passive_specs)
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(COMBINED_DEVICE_DONOR, "ROOT.DSN")
    dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, object_chunk, _combined_device_section())
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)

    root = OUT_ROOT if out_root is None else out_root
    case_dir = root / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.DSN.bin").write_bytes(dsn)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    circuit_input = {
        "case_id": case.case_id,
        "title": case.title,
        "logical_expression": case.expression,
        "description": case.description,
        "normalizations": {
            "74HC7266": "74HC266",
            "hidden_supply": "Ignore user pin 14/VCC/+5V and pin 7/GND/0V for every 74HCxx package.",
            "terminal_policy": "IC signal pins use $TERINPUT/$TEROUTPUT. R/C/L endpoints use $TERBIDIR. Power/ground terminals only appear when passive branches need V0/G0.",
        },
        "gates": [gate.__dict__ for gate in case.gates],
        "passives": [passive.__dict__ for passive in case.passives],
        "direct_outputs": list(case.direct_outputs),
        "warning": case.warning,
    }
    (case_dir / "circuit_input.json").write_text(json.dumps(circuit_input, indent=2) + "\n", encoding="utf-8")
    plan = {
        "package_rows": package_rows,
        "ic_topology": ic_topology,
        "passive_topology": passive_topology,
        "passive_terminal_replacements": replacements,
    }
    (case_dir / "logic_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    issues = static_issues(output, case, object_chunk, cdb, passive_specs, build_issues)
    manifest = {
        "case_id": case.case_id,
        "title": case.title,
        "description": case.description,
        "expression": case.expression,
        "method": "accepted_donor_gate_slices_with_directional_ic_terminals_and_bidirectional_passive_endpoints",
        "hidden_supply_policy": "Pin 14 and pin 7 are user-input-only metadata for 74HCxx gates; no explicit IC supply pins are emitted.",
        "terminal_policy": circuit_input["normalizations"]["terminal_policy"],
        "normalizations": circuit_input["normalizations"],
        "gate_count": len(case.gates),
        "passive_component_count": len(case.passives),
        "direct_outputs": list(case.direct_outputs),
        "section_pointers": pointers,
        "static_validation_issues": issues,
        "marker_counts": marker_counts(object_chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(object_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _as_str(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"`{field}` must be a non-empty string.")
    value.encode("ascii")
    return value


def _normalize_family(value: Any) -> str:
    raw = _as_str(value, field="family").lower().replace("-", "").replace("_", "")
    aliases = {
        "74hc7266": "74hc266",
        "hc7266": "74hc266",
        "hc266": "74hc266",
        "hc08": "74hc08",
        "hc32": "74hc32",
        "hc00": "74hc00",
        "hc02": "74hc02",
        "hc86": "74hc86",
        "hc04": "74hc04",
    }
    family = aliases.get(raw, raw)
    if family not in FAMILIES:
        raise ValueError(f"Unsupported combinational IC family `{value}`.")
    return family


def _normalize_gate(payload: Any, index: int) -> GateSpec:
    if not isinstance(payload, dict):
        raise ValueError(f"`gates[{index}]` must be an object.")
    family = _normalize_family(payload.get("family"))
    config = FAMILIES[family]
    gate_letter = _as_str(payload.get("gate", config.letters[index % len(config.letters)]), field=f"gates[{index}].gate").upper()
    if gate_letter not in config.letters:
        raise ValueError(f"`gates[{index}].gate` must be one of {config.letters} for {family}.")
    if config.input_count == 1:
        if "input" in payload:
            left = _as_str(payload["input"], field=f"gates[{index}].input")
        elif "left" in payload:
            left = _as_str(payload["left"], field=f"gates[{index}].left")
        else:
            inputs = payload.get("inputs")
            if not isinstance(inputs, list) or len(inputs) != 1:
                raise ValueError(f"`gates[{index}]` for 74HC04 must provide one input.")
            left = _as_str(inputs[0], field=f"gates[{index}].inputs[0]")
        right = ""
    else:
        if "left" in payload and "right" in payload:
            left = _as_str(payload["left"], field=f"gates[{index}].left")
            right = _as_str(payload["right"], field=f"gates[{index}].right")
        else:
            inputs = payload.get("inputs")
            if not isinstance(inputs, list) or len(inputs) != 2:
                raise ValueError(f"`gates[{index}]` must provide exactly two inputs.")
            left = _as_str(inputs[0], field=f"gates[{index}].inputs[0]")
            right = _as_str(inputs[1], field=f"gates[{index}].inputs[1]")
    output = _as_str(payload.get("output"), field=f"gates[{index}].output")
    note = str(payload.get("note", ""))
    package = str(payload.get("package", "") or "")
    if package:
        package.encode("ascii")
    return GateSpec(family, gate_letter, left, right, output, note, package)


def _normalize_passive(payload: Any, index: int) -> PassiveSpec:
    if not isinstance(payload, dict):
        raise ValueError(f"`passives[{index}]` must be an object.")
    kind = _as_str(payload.get("kind"), field=f"passives[{index}].kind").upper()
    aliases = {"RESISTOR": "R", "CAPACITOR": "C", "INDUCTOR": "L"}
    kind = aliases.get(kind, kind)
    if kind not in {"R", "C", "L"}:
        raise ValueError(f"`passives[{index}].kind` must be R, C, or L.")
    default_value = {"R": "330", "C": "1uF", "L": "5mH"}[kind]
    return PassiveSpec(
        _as_str(payload.get("ref", f"{kind}{index + 1}"), field=f"passives[{index}].ref"),
        kind,
        _as_str(payload.get("value", default_value), field=f"passives[{index}].value"),
        _as_str(payload.get("left"), field=f"passives[{index}].left"),
        _as_str(payload.get("right"), field=f"passives[{index}].right"),
    )


def parse_ic_combinational_payload(payload: Any) -> tuple[CircuitCase | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return None, ["Payload must be a JSON object."], warnings
    gates_raw = payload.get("gates")
    if not isinstance(gates_raw, list) or not gates_raw:
        return None, ["`gates` must be a non-empty array."], warnings
    try:
        gates = tuple(_normalize_gate(item, index) for index, item in enumerate(gates_raw))
        passives_raw = payload.get("passives", [])
        if not isinstance(passives_raw, list):
            raise ValueError("`passives` must be an array when present.")
        passives = tuple(_normalize_passive(item, index) for index, item in enumerate(passives_raw))
        _package_assignments(gates)
    except (UnicodeError, ValueError) as exc:
        errors.append(str(exc))
        return None, errors, warnings
    project = payload.get("project") if isinstance(payload.get("project"), dict) else {}
    case_id = str(project.get("output_basename") or payload.get("case_id") or "IC_COMBINATIONAL_OUTPUT")
    title = str(project.get("name") or payload.get("title") or case_id)
    expression = str(payload.get("logical_expression") or payload.get("expression") or "")
    description = str(payload.get("description") or "")
    if payload.get("sources"):
        warnings.append("IC combinational generation ignores DC/AC sources; use V0/G0 logic constants only when needed.")
    case = CircuitCase(
        case_id=case_id,
        title=title,
        expression=expression,
        description=description,
        gates=gates,
        passives=passives,
        direct_outputs=tuple(payload.get("direct_outputs", ())) if isinstance(payload.get("direct_outputs", ()), list) else (),
        warning=str(payload.get("warning", "")),
    )
    return case, errors, warnings


def generate_ic_combinational_project_from_payload(
    payload: Any,
    outdir: str | Path,
    *,
    layout_strategy: str | None = None,
) -> IcCombinationalGenerationResult:
    _unused_layout_strategy = layout_strategy
    case, errors, warnings = parse_ic_combinational_payload(payload)
    if errors or case is None:
        raise IcCombinationalGenerationBlocked(
            IcCombinationalValidationReport(errors=tuple(errors), warnings=tuple(warnings), circuit=case)
        )
    root = Path(outdir)
    root.mkdir(parents=True, exist_ok=True)
    manifest = write_case(case, out_root=root)
    case_dir = root / case.case_id
    issues = tuple(str(item) for item in manifest["static_validation_issues"])
    if issues:
        raise IcCombinationalGenerationBlocked(
            IcCombinationalValidationReport(errors=issues, warnings=tuple(warnings), circuit=case)
        )
    return IcCombinationalGenerationResult(
        output_path=case_dir / f"{case.case_id}.pdsprj",
        cdb_path=case_dir / "ROOT.CDB.bin",
        dsn_path=case_dir / "ROOT.DSN.bin",
        chunk_path=case_dir / "object_chunk.bin",
        manifest_path=case_dir / "manifest.json",
        plan_path=case_dir / "logic_plan.json",
        circuit_input_path=case_dir / "circuit_input.json",
        manifest=manifest,
    )


def cases() -> list[CircuitCase]:
    return [
        CircuitCase(
            "T01_74HC04_ONE_GATE_NOT",
            "Pure NOT Gate",
            "Y = not(A)",
            "74HC04 U1:A input A0, output Y0. User DIP pin 1 maps to input and pin 2 maps to output; pins 14/7 are hidden supply metadata.",
            (GateSpec("74hc04", "A", "A0", "", "Y0"),),
        ),
        CircuitCase(
            "T02_74HC04_ALL6_NOT",
            "All Six 74HC04 Inverters",
            "Y0..Y5 = not(A0..F0)",
            "One 74HC04 package uses U1:A through U1:F with independent directional input/output terminal pairs.",
            (
                GateSpec("74hc04", "A", "A0", "", "Y0"),
                GateSpec("74hc04", "B", "B0", "", "Y1"),
                GateSpec("74hc04", "C", "C0", "", "Y2"),
                GateSpec("74hc04", "D", "D0", "", "Y3"),
                GateSpec("74hc04", "E", "E0", "", "Y4"),
                GateSpec("74hc04", "F", "F0", "", "Y5"),
            ),
        ),
        CircuitCase(
            "T03_74HC04_LOGIC_CONSTANT_INPUTS",
            "NOT Gates with Logic Constants",
            "Y0 = not(V0); Y1 = not(G0)",
            "Power and ground labels are used as logic constants for input pins only; the HC04 package supply remains hidden.",
            (
                GateSpec("74hc04", "A", "V0", "", "Y0"),
                GateSpec("74hc04", "B", "G0", "", "Y1"),
            ),
        ),
        CircuitCase(
            "T04_74HC04_RCL_LOAD",
            "NOT Gate with RCL Load",
            "Y0 = not(A0), then Y0 drives R/C/L load labels",
            "The IC pins are directional; resistor, capacitor, and inductor endpoint terminals are donor-converted bidirectional terminals.",
            (GateSpec("74hc04", "A", "A0", "", "Y0"),),
            (
                PassiveSpec("R1", "R", "330", "Y0", "N1"),
                PassiveSpec("C1", "C", "1uF", "N1", "G0"),
                PassiveSpec("L1", "L", "5mH", "N1", "Y1"),
            ),
        ),
        CircuitCase(
            "T05_ALL7_LOGIC_WITH_RCL_FILTERS",
            "All Seven Combinational Families with R/C Filters",
            "N1=A.B; N2=C+D; N3=B xor C; N4=not(N1.N2); N5=not(N2+N3); N6=not(N3); Y=not(N4 xor N6)",
            "Final user blueprint normalized to Proteus 74HC266 for XNOR and two-character signal labels. Every logic stage output passes through a current-limiting resistor before becoming the next named node.",
            (
                GateSpec("74hc08", "A", "A0", "B0", "G1", "AND stage: A and B"),
                GateSpec("74hc32", "A", "C0", "D0", "G2", "OR stage: C or D"),
                GateSpec("74hc86", "A", "B0", "C0", "G3", "XOR stage: B xor C"),
                GateSpec("74hc00", "A", "N1", "N2", "G4", "NAND compression from resistor-limited Node 1 and Node 2"),
                GateSpec("74hc02", "A", "N2", "N3", "G5", "NOR measurement/expansion node"),
                GateSpec("74hc04", "A", "N3", "", "G6", "NOT stage from resistor-limited XOR node"),
                GateSpec("74hc266", "A", "N4", "N6", "G7", "Final XNOR decision"),
            ),
            (
                PassiveSpec("C1", "C", "1uF", "V0", "G0"),
                PassiveSpec("C2", "C", "1uF", "V0", "G0"),
                PassiveSpec("C3", "C", "1uF", "A0", "G0"),
                PassiveSpec("R1", "R", "330", "G1", "N1"),
                PassiveSpec("R2", "R", "330", "G2", "N2"),
                PassiveSpec("R3", "R", "330", "G3", "N3"),
                PassiveSpec("R4", "R", "330", "G4", "N4"),
                PassiveSpec("R5", "R", "330", "G5", "N5"),
                PassiveSpec("R6", "R", "10k", "G6", "N6"),
                PassiveSpec("C4", "C", "1uF", "N6", "G0"),
                PassiveSpec("R7", "R", "330", "G7", "Y0"),
            ),
            warning="Requested capacitance values 10uF/100nF/10nF/1uF and R6=1k are represented with donor-safe visible text in this temporary pack; topology and component count are preserved.",
        ),
    ]


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 8, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    for config in FAMILIES.values():
        if not config.donor.exists():
            raise FileNotFoundError(config.donor)
    if not COMBINED_DEVICE_DONOR.exists():
        raise FileNotFoundError(COMBINED_DEVICE_DONOR)
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests = [write_case(case) for case in cases()]
    summary = {
        "batch": "IC_HC04_ALL7_V1_TEMP_2026_06_08",
        "purpose": "HC04 NOT support and one final all-seven combinational IC circuit generated from accepted donor-derived gate/passive records.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "test_order": [manifest["case_id"] for manifest in manifests],
        "shared_rules": [
            "74HC7266 in the prompt is normalized to the accepted Proteus donor family 74HC266.",
            "74HC04 is generated as six unary subparts U1:A through U1:F using the observed 74INV.MDF model.",
            "Pin 14 and pin 7 supply instructions are accepted as user metadata but not emitted for IC packages.",
            "IC signal pins use $TERINPUT/$TEROUTPUT only.",
            "R/C/L endpoints use $TERBIDIR; the passive G0 endpoint keeps the previously accepted $TERGROUND donor terminal.",
            "The final all-seven circuit keeps every logic-stage output behind a resistor before it becomes a downstream logic node.",
        ],
        "cases": manifests,
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": len(manifests)}, indent=2))


if __name__ == "__main__":
    main()
