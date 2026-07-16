"""Generate the compact last-two combinational IC acceptance patch pack.

This temporary pack reuses the accepted donor-derived gate records for:

- 74HC08 AND
- 74HC32 OR
- 74HC00 NAND
- 74HC02 NOR
- 74HC86 XOR
- 74HC266 XNOR candidate

IC signal pins remain directional. Passive endpoints use the accepted
bidirectional terminal conversion. G0 passive endpoints are converted from
the donor ground symbol to a bidirectional G0 terminal for the new IC mixed
policy. IC package supply pins are hidden by Proteus and are not emitted as
explicit pin 14 / pin 7 wiring.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen import mixed_rcl as rcl
from proteusgen.bidirectional import build_bidir_record, convert_production_terminals, load_production_templates
from proteusgen.logic_expression import LogicGateStep
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _i32, _sha256_bytes, _u32
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "experiments" / "ic_final_last2_layout_ground_v2_temp_2026_06_08"
ARCHIVE_PATH = REPO / "experiments" / "IC_FINAL_LAST2_LAYOUT_GROUND_V2_TEMP_2026_06_08.zip"

COMBINED_DEVICE_DONOR = REPO / "proteus_ic" / "donors" / "combined" / "ALLL_ICS_ALL4_RLC.pdsprj"
HC08_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-08" / "generate_ic_hc08_logic_v1_temp.py"
HC32_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-08" / "generate_ic_hc32_logic_v1_temp.py"

GATE_LETTERS = "ABCD"
COLUMN_SPACING = 3_810_000
PASSIVE_X_BASE = 8_890_000
PASSIVE_Y_BASE = 3_556_000
PASSIVE_Y_STEP = -1_016_000

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
    pins: dict[str, tuple[tuple[str, str], tuple[str, str], tuple[str, str]]]


@dataclass(frozen=True)
class GateSpec:
    family: str
    gate: str
    left: str
    right: str
    output: str
    note: str = ""


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

FAMILIES = {
    "74hc08": FamilyConfig(
        "74hc08",
        "74HC08",
        "AND2",
        REPO / "proteus_ic" / "donors" / "74hc08" / "IC_HC08_M01_ALL4_IO.pdsprj",
        "hc08_script",
        b"{MODFILE=74AND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        STANDARD_PINS,
    ),
    "74hc32": FamilyConfig(
        "74hc32",
        "74HC32",
        "OR2",
        REPO / "proteus_ic" / "donors" / "74hc32" / "IC_HC32_M02_ALL4_IO.pdsprj",
        "hc32_script",
        b"{MODFILE=74OR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        STANDARD_PINS,
    ),
    "74hc00": FamilyConfig(
        "74hc00",
        "74HC00",
        "NAND2",
        REPO / "proteus_ic" / "donors" / "74hc00" / "IC_74HC00_M02_ALL4_IO.pdsprj",
        "terminal_first",
        b"{MODFILE=74NAND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        NAND_PINS,
    ),
    "74hc02": FamilyConfig(
        "74hc02",
        "74HC02",
        "NOR2",
        REPO / "proteus_ic" / "donors" / "74hc02" / "IC_74HC02_M02_ALL4_IO.pdsprj",
        "component_first",
        b"{MODFILE=74NOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        NOR_PINS,
    ),
    "74hc86": FamilyConfig(
        "74hc86",
        "74HC86",
        "XOR2",
        REPO / "proteus_ic" / "donors" / "74hc86" / "IC_74HC86_M02_ALL4_IO.pdsprj",
        "component_first",
        b"{MODFILE=74XOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        STANDARD_PINS,
    ),
    "74hc266": FamilyConfig(
        "74hc266",
        "74HC266",
        "XNOR2 candidate using observed 74XOR2 marker",
        REPO / "proteus_ic" / "donors" / "74hc266" / "IC_74HC266_M02_ALL4_IO.pdsprj",
        "component_first",
        b"{MODFILE=74XOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        XNOR_PINS,
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
    gate_index = GATE_LETTERS.index(gate_letter)
    if config.shape == "terminal_first":
        labels = (f"A{gate_index}", f"B{gate_index}", f"Y{gate_index}")
        starts = _terminal_starts(chunk)
        start = min(starts[label] for label in labels)
        if gate_index + 1 < len(GATE_LETTERS):
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
        if gate_index + 1 < len(GATE_LETTERS):
            next_ref = f"U1:{GATE_LETTERS[gate_index + 1]}".encode("ascii")
            next_ref_pos = chunk.find(next_ref)
            if next_ref_pos < 0:
                raise RuntimeError(f"Could not find {next_ref!r} in {config.donor}.")
            end = next_ref_pos - 3
        else:
            end = len(chunk) - 1
    record = chunk[start:end]
    if record.count(b"$TERINPUT") != 2 or record.count(b"$TEROUTPUT") != 1 or record.count(b"COMPONENT ID") != 1:
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


def _generic_gate_record(
    config: FamilyConfig,
    gate: GateSpec,
    *,
    package_ref: str,
    object_id: int,
    dx: int,
    dy: int,
) -> tuple[bytes, dict[str, object]]:
    gate_index = GATE_LETTERS.index(gate.gate)
    record = bytearray(_gate_record_slice(config, gate.gate))
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


def _package_order(gates: tuple[GateSpec, ...]) -> dict[str, tuple[str, int]]:
    order: dict[str, tuple[str, int]] = {}
    for gate in gates:
        if gate.family not in order:
            package_number = len(order) + 1
            order[gate.family] = (f"U{package_number}", package_number)
    return order


def build_ic_records(case: CircuitCase) -> tuple[bytes, list[dict[str, object]], list[dict[str, object]]]:
    packages = _package_order(case.gates)
    records: list[bytes] = []
    topology: list[dict[str, object]] = []
    for object_id, gate in enumerate(case.gates, start=1):
        config = FAMILIES[gate.family]
        package_ref, package_number = packages[gate.family]
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
    package_rows = [
        {"family": family, "device": FAMILIES[family].device, "package_ref": package_ref, "package_number": package_number}
        for family, (package_ref, package_number) in packages.items()
    ]
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


def replace_ground_terminals_with_bidir(chunk: bytes, registry: FixtureRegistry) -> tuple[bytes, list[dict[str, object]], list[str]]:
    templates = load_production_templates(registry)
    events: list[tuple[int, int, bytes]] = []
    position = 0
    while True:
        marker_position = chunk.find(b"$TERGROUND", position)
        if marker_position < 0:
            break
        start = marker_position - 14
        if start < 0 or chunk[start] != 0x10:
            raise ValueError(f"Invalid ground terminal start at marker {marker_position}.")
        label_length = chunk[start + 31]
        size = 101 + label_length
        events.append((start, size, chunk[start : start + size]))
        position = marker_position + 1

    converted = bytearray(chunk)
    metadata: list[dict[str, object]] = []
    issues: list[str] = []
    for start, size, record in reversed(events):
        label_length = record[31]
        label = record[32 : 32 + label_length].decode("ascii")
        symbol_x, symbol_y = struct.unpack("<ii", record[1:9])
        angle_tenths = struct.unpack("<I", record[9:13])[0]
        if angle_tenths not in {0, 1800}:
            issues.append(f"unsupported ground angle {angle_tenths} for {label}")
            continue
        suffix = struct.unpack("<H", record[-4:-2])[0]
        replacement = build_bidir_record(
            templates,
            label=label,
            symbol_x=symbol_x,
            symbol_y=symbol_y,
            angle_tenths=angle_tenths,
            suffix=suffix,
            active_link=record[-2] == 1,
        )
        converted[start : start + size] = replacement
        metadata.append(
            {
                "kind": "ground_to_bidir",
                "label": label,
                "angle_tenths": angle_tenths,
                "suffix": f"{suffix:04x}",
                "old_start": start,
                "old_size": size,
                "new_size": len(replacement),
            }
        )
    converted[-1] = 0xFF
    if converted.count(b"$TERGROUND"):
        issues.append("ground-to-bidir conversion left $TERGROUND marker(s)")
    return bytes(converted), sorted(metadata, key=lambda item: int(item["old_start"])), issues


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
    converted, ground_replacements, ground_issues = replace_ground_terminals_with_bidir(converted, registry)
    return (
        converted,
        specs,
        topology,
        [item.__dict__ for item in replacements] + ground_replacements,
        chunk_issues + conversion_issues + ground_issues,
    )


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
        pins = FAMILIES[str(row["family"])].pins[gate_letter]
        out += _u32(object_id) + _u32(1) + _u32(0) + _u32(object_id)
        out += _enc_str(str(row["subpart_ref"])) + _u32(3)
        for logical, physical in pins:
            out += _enc_str(logical) + _enc_str(physical)
        out += _u32(0) + _u32(package_number) + _u32(GATE_LETTERS.index(gate_letter))
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
    if object_chunk.count(b"$TERINPUT") != 2 * len(case.gates):
        issues.append("$TERINPUT count does not match two inputs per gate")
    if object_chunk.count(b"$TEROUTPUT") != len(case.gates):
        issues.append("$TEROUTPUT count does not match one output per gate")
    if object_chunk.count(b"COMPONENT ID") != len(case.gates) + len(passive_specs):
        issues.append("COMPONENT ID count does not match gate plus passive component count")
    if case.passives:
        min_bidir = 2 * len(case.passives)
        if object_chunk.count(b"$TERBIDIR") < min_bidir:
            issues.append("$TERBIDIR count is below two passive endpoints per passive component")
        if object_chunk.count(b"$TERPOWER") != 1:
            issues.append("mixed passive case should contain one donor-derived power bridge")
        uses_ground = any(passive.left == "G0" or passive.right == "G0" for passive in case.passives)
        if object_chunk.count(b"$TERGROUND") != 0:
            issues.append("$TERGROUND must not remain in the compact ground-bidir V2 pack")
        if uses_ground and object_chunk.count(b"G0") < 1:
            issues.append("passive topology uses G0 but the object chunk has no G0 label")
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
    packages = _package_order(case.gates)
    rows: list[dict[str, str]] = []
    for gate in case.gates:
        package_ref, _package_number = packages[gate.family]
        rows.append({"package_ref": package_ref, "gate_letter": gate.gate})
    return rows


def write_case(case: CircuitCase) -> dict[str, object]:
    object_chunk, ic_topology, package_rows, passive_specs, passive_topology, replacements, build_issues = build_object_chunk(case)
    cdb = build_cdb(ic_topology, package_rows, passive_specs)
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(COMBINED_DEVICE_DONOR, "ROOT.DSN")
    dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, object_chunk, _combined_device_section())
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)

    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    circuit_input = {
        "case_id": case.case_id,
        "title": case.title,
        "logical_expression": case.expression,
        "description": case.description,
        "normalizations": {
            "74HC7266": "74HC266",
            "hidden_supply": "Ignore user pin 14/VCC/+5V and pin 7/GND/0V for every 74HCxx package.",
            "terminal_policy": "IC signal pins use $TERINPUT/$TEROUTPUT. R/C/L endpoints use $TERBIDIR. Passive G0 uses same-name $TERBIDIR; an IC pin tied to ground would use a same-name $TERINPUT(G0), not a bidirectional IC terminal.",
            "layout_policy": "Compact last-two V2: IC package spacing is 3,810,000 and nearby passive columns start at x=8,890,000.",
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
        "layout_policy": circuit_input["normalizations"]["layout_policy"],
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


def cases() -> list[CircuitCase]:
    return [
        CircuitCase("T01_AND2_74HC08", "Pure 2-Input Logical AND", "Y = A . B", "74HC08 U1:A input A0/B0, output Y0.", (GateSpec("74hc08", "A", "A0", "B0", "Y0"),)),
        CircuitCase("T02_OR2_74HC32", "Pure 2-Input Logical OR", "Y = A + B", "74HC32 U1:A input A0/B0, output Y0.", (GateSpec("74hc32", "A", "A0", "B0", "Y0"),)),
        CircuitCase("T03_NAND2_74HC00", "Pure 2-Input Logical NAND", "Y = not(A . B)", "74HC00 U1:A input A0/B0, output Y0.", (GateSpec("74hc00", "A", "A0", "B0", "Y0"),)),
        CircuitCase("T04_NOR2_74HC02", "Pure 2-Input Logical NOR", "Y = not(A + B)", "74HC02 U1:A input A0/B0, output Y0. User DIP pins 2/3 feed inputs and pin 1 is output.", (GateSpec("74hc02", "A", "A0", "B0", "Y0"),)),
        CircuitCase("T05_XOR2_74HC86", "Pure 2-Input Logical XOR", "Y = A xor B", "74HC86 U1:A input A0/B0, output Y0.", (GateSpec("74hc86", "A", "A0", "B0", "Y0"),)),
        CircuitCase("T06_XNOR2_74HC266", "Pure 2-Input Logical XNOR", "Y = not(A xor B)", "74HC7266 from prompt normalized to accepted 74HC266 U1:A.", (GateSpec("74hc266", "A", "A0", "B0", "Y0"),)),
        CircuitCase("T07_HALF_ADDER", "Half Adder", "Sum = A xor B; Carry = A . B", "XOR and AND outputs share input labels A0/B0.", (GateSpec("74hc86", "A", "A0", "B0", "SU"), GateSpec("74hc08", "A", "A0", "B0", "CA"))),
        CircuitCase("T08_HALF_SUBTRACTOR", "Half Subtractor", "Difference = A xor B; Borrow = not(A) . B", "NAND self-input inverts A before ANDing with B.", (GateSpec("74hc86", "A", "A0", "B0", "DI"), GateSpec("74hc00", "A", "A0", "A0", "NA"), GateSpec("74hc08", "A", "NA", "B0", "BO"))),
        CircuitCase("T09_MUX_2_TO_1", "2-to-1 Multiplexer", "Y = (D0 . not(S)) + (D1 . S)", "Select is inverted by NAND self-input, two AND products feed OR.", (GateSpec("74hc00", "A", "S0", "S0", "NS"), GateSpec("74hc08", "A", "D1", "S0", "P1"), GateSpec("74hc08", "B", "D0", "NS", "P0"), GateSpec("74hc32", "A", "P1", "P0", "Y0"))),
        CircuitCase("T10_DEMUX_1_TO_2", "1-to-2 Demultiplexer", "Y0 = D . not(S); Y1 = D . S", "Shared data input feeds two AND gates; NAND self-input creates not(S).", (GateSpec("74hc00", "A", "S0", "S0", "NS"), GateSpec("74hc08", "A", "D0", "S0", "Y1"), GateSpec("74hc08", "B", "D0", "NS", "Y0"))),
        CircuitCase("T11_MAJORITY3", "3-Input Majority Gate", "Y = (A.B) + (B.C) + (A.C)", "Three AND products reduce through two OR gates.", (GateSpec("74hc08", "A", "A0", "B0", "P1"), GateSpec("74hc08", "B", "B0", "C0", "P2"), GateSpec("74hc08", "C", "A0", "C0", "P3"), GateSpec("74hc32", "A", "P1", "P2", "S1"), GateSpec("74hc32", "B", "S1", "P3", "Y0"))),
        CircuitCase("T12_EQUALITY2", "2-Bit Equality Comparator", "Y = XNOR(A0,B0) . XNOR(A1,B1)", "Two 74HC266 XNOR candidate gates feed one AND gate.", (GateSpec("74hc266", "A", "A0", "B0", "E0"), GateSpec("74hc266", "B", "A1", "B1", "E1"), GateSpec("74hc08", "A", "E0", "E1", "Y0"))),
        CircuitCase("T13_INHIBIT", "Inhibit Gate", "Y = A . not(B)", "NAND self-input inverts B, then ANDs with A.", (GateSpec("74hc00", "A", "B0", "B0", "NB"), GateSpec("74hc08", "A", "A0", "NB", "Y0"))),
        CircuitCase("T14_IMPLICATION", "Implication Gate", "Y = not(A) + B", "NAND self-input inverts A, then ORs with B.", (GateSpec("74hc00", "A", "A0", "A0", "NA"), GateSpec("74hc32", "A", "NA", "B0", "Y0"))),
        CircuitCase("T15_XOR_FROM_NAND", "XOR from 4 NAND Gates", "Y = nand(nand(A,nand(A,B)), nand(B,nand(A,B)))", "Classic four-NAND XOR equivalent.", (GateSpec("74hc00", "A", "A0", "B0", "N1"), GateSpec("74hc00", "B", "A0", "N1", "N2"), GateSpec("74hc00", "C", "B0", "N1", "N3"), GateSpec("74hc00", "D", "N2", "N3", "Y0"))),
        CircuitCase("T16_AND_FROM_NOR", "AND from 3 NOR Gates", "Y = not(not(A+A) + not(B+B))", "Two NOR self-input inverters feed a third NOR.", (GateSpec("74hc02", "A", "A0", "A0", "NA"), GateSpec("74hc02", "B", "B0", "B0", "NB"), GateSpec("74hc02", "C", "NA", "NB", "Y0"))),
        CircuitCase("T17_OR_FROM_NAND", "OR from 3 NAND Gates", "Y = nand(not(A), not(B))", "Two NAND self-input inverters feed a third NAND.", (GateSpec("74hc00", "A", "A0", "A0", "NA"), GateSpec("74hc00", "B", "B0", "B0", "NB"), GateSpec("74hc00", "C", "NA", "NB", "Y0"))),
        CircuitCase("T18_SR_LATCH_NOR", "SR Latch / Memory Cell", "Q = not(R + Qbar); Qbar = not(S + Q)", "Two cross-coupled NOR gates.", (GateSpec("74hc02", "A", "R0", "QB", "Q0"), GateSpec("74hc02", "B", "S0", "Q0", "QB"))),
        CircuitCase("T19_EVEN_PARITY3", "3-Bit Even Parity Generator", "Y = (A xor B) xor C", "Two cascaded XOR gates.", (GateSpec("74hc86", "A", "A0", "B0", "P1"), GateSpec("74hc86", "B", "P1", "C0", "Y0"))),
        CircuitCase("T20_ODD_PARITY3", "3-Bit Odd Parity Generator", "Y = not((A xor B) xor C)", "XOR output feeds 74HC266 XNOR candidate with C.", (GateSpec("74hc86", "A", "A0", "B0", "P1"), GateSpec("74hc266", "A", "P1", "C0", "Y0"))),
        CircuitCase("T21_BINARY_TO_GRAY2", "2-Bit Binary to Gray Converter", "G1 = B1; G0 = B1 xor B0", "G1 is direct pass-through on net B1; G0 comes from XOR.", (GateSpec("74hc86", "A", "B1", "B0", "G0"),), direct_outputs=({"output": "G1", "net": "B1", "note": "Direct pass-through output uses the B1 net label."},)),
        CircuitCase("T22_GRAY_TO_BINARY2", "2-Bit Gray to Binary Converter", "B1 = G1; B0 = G1 xor G0", "B1 is direct pass-through on net G1; B0 comes from XOR.", (GateSpec("74hc86", "A", "G1", "G0", "B0"),), direct_outputs=({"output": "B1", "net": "G1", "note": "Direct pass-through output uses the G1 net label."},)),
        CircuitCase("T23_SUM_OF_PRODUCTS_BLOCK", "Sum of Products Sub-Block", "Y = (A + B) . (C + D)", "Two OR terms feed one AND gate.", (GateSpec("74hc32", "A", "A0", "B0", "S1"), GateSpec("74hc32", "B", "C0", "D0", "S2"), GateSpec("74hc08", "A", "S1", "S2", "Y0"))),
        CircuitCase("T24_PRODUCT_OF_SUMS_BLOCK", "Product of Sums Sub-Block", "Y = (A.B) + (C.D)", "Two AND terms feed one OR gate.", (GateSpec("74hc08", "A", "A0", "B0", "P1"), GateSpec("74hc08", "B", "C0", "D0", "P2"), GateSpec("74hc32", "A", "P1", "P2", "Y0"))),
        CircuitCase("T25_CASCADED_AND4", "4-Input Cascaded AND", "Y = A.B.C.D", "Two first-stage AND gates feed a third AND.", (GateSpec("74hc08", "A", "A0", "B0", "P1"), GateSpec("74hc08", "B", "C0", "D0", "P2"), GateSpec("74hc08", "C", "P1", "P2", "Y0"))),
        CircuitCase("T26_CASCADED_OR4", "4-Input Cascaded OR", "Y = A+B+C+D", "Two first-stage OR gates feed a third OR.", (GateSpec("74hc32", "A", "A0", "B0", "P1"), GateSpec("74hc32", "B", "C0", "D0", "P2"), GateSpec("74hc32", "C", "P1", "P2", "Y0"))),
        CircuitCase("T27_FILTERED_MUX_RC", "Glitch-Filtered Multiplexer Switch", "Y = (D0 . not(Sf)) + (D1 . Sf)", "RC filters select node SF before the MUX logic. Requested 10uF is normalized to donor-safe 1uF visible text.", (GateSpec("74hc00", "A", "SF", "SF", "NS"), GateSpec("74hc08", "A", "D1", "SF", "P1"), GateSpec("74hc08", "B", "D0", "NS", "P0"), GateSpec("74hc32", "A", "P1", "P0", "Y0")), (PassiveSpec("R1", "R", "10k", "S0", "SF"), PassiveSpec("C1", "C", "1uF", "SF", "G0"))),
        CircuitCase("T28_XOR_LC_FILTER", "Phase Difference Detector with LC Smoothing", "Vanalog = filter(A xor B)", "XOR output feeds L then C to ground. Requested 10mH/100n are normalized to donor-safe 5mH/1uF visible text.", (GateSpec("74hc86", "A", "A0", "B0", "Y0"),), (PassiveSpec("L1", "L", "5mH", "Y0", "AN"), PassiveSpec("C1", "C", "1uF", "AN", "G0"))),
        CircuitCase("T29_NOR_RESET_AND_ENABLE", "NOR Power-On Reset driving AND Enable", "Y = Data . not(PowerOn + PowerOn)", "V0 charges timing node through R/C; NOR output enables data through AND.", (GateSpec("74hc02", "A", "TN", "TN", "NR"), GateSpec("74hc08", "A", "NR", "DA", "Y0")), (PassiveSpec("R1", "R", "10k", "V0", "TN"), PassiveSpec("C1", "C", "1uF", "TN", "G0"))),
        CircuitCase("T30_AND_RELAY_SNUBBER_NO_MOSFET", "AND-Controlled Relay Snubber Interface", "RelayControl = A . B", "MOSFET is not generated; AND output exposes gate-control net GT and the relay/snubber passives are shown as accepted R/L/C records. Requested 100mH/100n are normalized to donor-safe 5mH/1uF visible text.", (GateSpec("74hc08", "A", "A0", "B0", "GT"),), (PassiveSpec("L1", "L", "5mH", "V0", "DR"), PassiveSpec("R1", "R", "100", "DR", "SN"), PassiveSpec("C1", "C", "1uF", "SN", "V0")), warning="MOSFET donor is not yet accepted; this case exposes GT/DR/SN interface nodes instead of emitting an N-channel MOSFET component."),
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
    manifests = [write_case(case) for case in cases()[-2:]]
    summary = {
        "batch": "IC_FINAL_LAST2_LAYOUT_GROUND_V2_TEMP_2026_06_08",
        "purpose": "Targeted compact-layout and bidirectional-G0 retest for the last two final combinational IC circuits.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "test_order": [manifest["case_id"] for manifest in manifests],
        "shared_rules": [
            "74HC7266 in the prompt is normalized to the accepted Proteus donor family 74HC266.",
            "Pin 14 and pin 7 supply instructions are accepted as user metadata but not emitted for IC packages.",
            "IC signal pins use $TERINPUT/$TEROUTPUT only.",
            "R/C/L endpoints use $TERBIDIR. G0 passive endpoints are converted to $TERBIDIR instead of emitting $TERGROUND.",
            "Small IC/passive cases use a compact nearby passive column so the last-two layouts are not spread across the sheet.",
            "Circuit 30 does not emit a MOSFET because no MOSFET donor has been accepted yet.",
        ],
        "cases": manifests,
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": len(manifests)}, indent=2))


if __name__ == "__main__":
    main()
