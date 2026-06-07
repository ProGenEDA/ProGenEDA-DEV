"""Generate the first expression-driven 74HC32 logic test pack.

This temporary generator maps an OR-only Boolean expression onto donor-derived
74HC32 gate subpart records. IC signal pins remain $TERINPUT/$TEROUTPUT
records. IC supply pins 14 and 7 are hidden by Proteus for this family and are
ignored in the user-facing pin map.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.logic_expression import LogicGateStep, build_or2_tree, compact_net_label, parse_or_expression
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _i32, _sha256_bytes, _u32, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "experiments" / "ic_hc32_logic_v1_temp_2026_06_08"
ARCHIVE_PATH = REPO / "experiments" / "IC_HC32_LOGIC_V1_TEMP_2026_06_08.zip"

HC32_ALL4_DONOR = REPO / "proteus_ic" / "donors" / "74hc32" / "IC_HC32_M02_ALL4_IO.pdsprj"
DEVICE_SECTION_DONOR = HC32_ALL4_DONOR

EXPRESSION = (
    r"Y = X_1 + X_2 + X_3 + X_4 + X_5 + X_6 + "
    r"X_7 + X_8 + X_9 + X_{10} + X_{11} + X_{12} "
    r"+ X_{13} + X_{14} + X_{15}"
)

GATE_LETTERS = "ABCD"
GATE_PINS = {
    "A": {"index": 1, "pins": (("A", "1"), ("B", "2"), ("Y", "3"))},
    "B": {"index": 2, "pins": (("A", "4"), ("B", "5"), ("Y", "6"))},
    "C": {"index": 3, "pins": (("A", "9"), ("B", "10"), ("Y", "8"))},
    "D": {"index": 4, "pins": (("A", "12"), ("B", "13"), ("Y", "11"))},
}

IC_PROP_TEXT = b"{MODFILE=74OR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00"

GATE_RECORD_SIZE = 842
COMPONENT_OBJECT_ID_OFFSET = 357
INPUT_A_START = 382
INPUT_B_START = 535
OUTPUT_START = 688
INPUT_SIZE = 153
OUTPUT_SIZE = 154
PIN_ID_BASE = 0x000100D6
PIN_ID_STEP = GATE_RECORD_SIZE
PIN_ID_B_OFFSET = INPUT_SIZE
PIN_ID_Y_OFFSET = INPUT_SIZE + OUTPUT_SIZE
PIN_ID_OFFSETS = {
    "in1": (370, 481),
    "in2": (374, 634),
    "out": (378, 788),
}

COORD_Y_OFFSETS = (11, 83, 158, 223, 349, 387, 419, 523, 531, 540, 572, 676, 684, 693, 726, 830, 838)
COORD_X_OFFSETS = tuple(offset - 4 for offset in COORD_Y_OFFSETS)
COLUMN_SPACING = 5_080_000

MARKERS = (
    b"74HC32",
    b"74OR2",
    b"74HC08",
    b"74AND2",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERBIDIR",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"RESISTOR",
    b"CAPACITOR",
    b"REALIND",
    b"VSOURCE",
    b"CSOURCE",
    b"LOGICSTATE",
    b"LOGICPROBE",
)


@dataclass(frozen=True)
class GateInstance:
    step: LogicGateStep
    package_number: int
    gate_letter: str
    object_id: int
    dx: int
    dy: int

    @property
    def package_ref(self) -> str:
        return f"U{self.package_number}"

    @property
    def subpart_ref(self) -> str:
        return f"{self.package_ref}:{self.gate_letter}"

    @property
    def chip_alias(self) -> str:
        return f"IC{self.package_number}"


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def _all4_chunk() -> bytes:
    return _extract_object_chunk(read_internal_file(HC32_ALL4_DONOR, "ROOT.DSN"))


def _gate_combo(gate_letter: str) -> bytes:
    gate_index = GATE_LETTERS.index(gate_letter)
    start = 1 + gate_index * GATE_RECORD_SIZE
    combo = _all4_chunk()[start : start + GATE_RECORD_SIZE]
    if len(combo) != GATE_RECORD_SIZE:
        raise RuntimeError(f"Unexpected HC32 gate combo size for {gate_letter}: {len(combo)}")
    if combo.count(b"COMPONENT ID") != 1 or combo.count(b"$TERINPUT") != 2 or combo.count(b"$TEROUTPUT") != 1:
        raise RuntimeError(f"HC32 gate combo {gate_letter} does not match the locked marker pattern.")
    if combo.count(f"U1:{gate_letter}".encode("ascii")) != 1:
        raise RuntimeError(f"HC32 gate combo {gate_letter} does not contain the expected donor subpart ref.")
    return combo


def _patch_two_char_label(record: bytearray, start: int, *, output_terminal: bool, label: str) -> None:
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError(f"HC32 logic pack labels must be exactly two ASCII characters: {label!r}")
    length_offset = start + (31 if output_terminal else 30)
    label_start = length_offset + 1
    record[length_offset] = 2
    record[label_start : label_start + 2] = raw


def _patch_coords(record: bytearray, dx: int, dy: int) -> None:
    for offset in COORD_X_OFFSETS:
        value = int.from_bytes(record[offset : offset + 4], "little", signed=True)
        record[offset : offset + 4] = _i32(value + dx)
    for offset in COORD_Y_OFFSETS:
        value = int.from_bytes(record[offset : offset + 4], "little", signed=True)
        record[offset : offset + 4] = _i32(value + dy)


def _pin_ids(object_id: int) -> tuple[int, int, int]:
    base = PIN_ID_BASE + (object_id - 1) * PIN_ID_STEP
    return base, base + PIN_ID_B_OFFSET, base + PIN_ID_Y_OFFSET


def _patch_ids(record: bytearray, object_id: int) -> dict[str, str]:
    record[COMPONENT_OBJECT_ID_OFFSET : COMPONENT_OBJECT_ID_OFFSET + 4] = _u32(object_id)
    pin_a, pin_b, pin_y = _pin_ids(object_id)
    for key, value in (("in1", pin_a), ("in2", pin_b), ("out", pin_y)):
        raw = _u32(value)
        for offset in PIN_ID_OFFSETS[key]:
            record[offset : offset + 4] = raw
    return {"in1": f"{pin_a:08x}", "in2": f"{pin_b:08x}", "out": f"{pin_y:08x}"}


def _patch_package_ref(record: bytearray, gate_letter: str, package_ref: str) -> None:
    old = f"U1:{gate_letter}".encode("ascii")
    new = f"{package_ref}:{gate_letter}".encode("ascii")
    if len(new) != len(old):
        raise ValueError("Only U1..U9 package refs are supported in this temporary patcher.")
    count = bytes(record).count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {old!r} marker in gate record, found {count}.")
    pos = bytes(record).find(old)
    record[pos : pos + len(old)] = new


def build_gate_record(instance: GateInstance, *, final: bool) -> tuple[bytes, dict[str, object]]:
    record = bytearray(_gate_combo(instance.gate_letter))
    _patch_two_char_label(record, INPUT_A_START, output_terminal=False, label=instance.step.left)
    _patch_two_char_label(record, INPUT_B_START, output_terminal=False, label=instance.step.right)
    _patch_two_char_label(record, OUTPUT_START, output_terminal=True, label=instance.step.output)
    _patch_package_ref(record, instance.gate_letter, instance.package_ref)
    pin_ids = _patch_ids(record, instance.object_id)
    _patch_coords(record, instance.dx, instance.dy)
    if final:
        record.append(0xFF)
    pin_info = GATE_PINS[instance.gate_letter]["pins"]
    return bytes(record), {
        "object_id": instance.object_id,
        "chip_alias": instance.chip_alias,
        "package_ref": instance.package_ref,
        "subpart_ref": instance.subpart_ref,
        "gate_letter": instance.gate_letter,
        "left_net": instance.step.left,
        "right_net": instance.step.right,
        "output_net": instance.step.output,
        "physical_pins": {"left": pin_info[0][1], "right": pin_info[1][1], "output": pin_info[2][1]},
        "pin_ids": pin_ids,
    }


def allocate_gates(steps: tuple[LogicGateStep, ...]) -> tuple[GateInstance, ...]:
    instances: list[GateInstance] = []
    for zero_index, step in enumerate(steps):
        package_number = zero_index // 4 + 1
        gate_index = zero_index % 4 + 1
        gate_letter = GATE_LETTERS[gate_index - 1]
        object_id = (package_number - 1) * 4 + gate_index
        instances.append(
            GateInstance(
                step=step,
                package_number=package_number,
                gate_letter=gate_letter,
                object_id=object_id,
                dx=(package_number - 1) * COLUMN_SPACING,
                dy=0,
            )
        )
    return tuple(instances)


def build_object_chunk(instances: tuple[GateInstance, ...]) -> tuple[bytes, list[dict[str, object]]]:
    parts: list[bytes] = []
    topology: list[dict[str, object]] = []
    for index, instance in enumerate(instances):
        record, row = build_gate_record(instance, final=index == len(instances) - 1)
        parts.append(record)
        topology.append(row)
    return b"\x00" + b"".join(parts), topology


def build_cdb(instances: tuple[GateInstance, ...]) -> bytes:
    package_count = max(instance.package_number for instance in instances)
    out = bytearray()
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + _enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + _enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + _enc_str("Master Sheet") + _u32(10) + _u32(0)

    out += _u32(len(instances))
    for instance in instances:
        gate_info = GATE_PINS[instance.gate_letter]
        out += _u32(instance.object_id) + _u32(1) + _u32(0) + _u32(instance.object_id)
        out += _enc_str(instance.subpart_ref) + _u32(3)
        for logical, physical in gate_info["pins"]:
            out += _enc_str(logical) + _enc_str(physical)
        out += _u32(0) + _u32(instance.package_number) + _u32(gate_info["index"] - 1)

    out += _u32(1) + _u32(1) + b"\x00" + _enc_str("") + _u32(1)
    out += _u32(package_count)
    for package_number in range(1, package_count + 1):
        package_ref = f"U{package_number}"
        out += _u32(package_number) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        out += _enc_str(package_ref) + _enc_str("74HC32") + _enc_str("74HC32") + _enc_str("DIL14")
        out += _enc_text(IC_PROP_TEXT)
    out += _u32(0)
    return bytes(out)


def static_issues(output: Path, instances: tuple[GateInstance, ...]) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    forbidden = (b"74HC08", b"74AND2", b"$TERBIDIR", b"$TERPOWER", b"$TERGROUND", b"VSOURCE", b"CSOURCE", b"LOGICSTATE", b"LOGICPROBE")
    for marker in forbidden:
        if chunk.count(marker):
            issues.append(f"unexpected marker in pure HC32 logic pack: {marker.decode('ascii')}")
    if chunk.count(b"$TERINPUT") != 2 * len(instances):
        issues.append("$TERINPUT count does not match two inputs per gate")
    if chunk.count(b"$TEROUTPUT") != len(instances):
        issues.append("$TEROUTPUT count does not match one output per gate")
    if chunk.count(b"COMPONENT ID") != len(instances):
        issues.append("COMPONENT ID count does not match gate count")
    if chunk.count(b"74HC32") != 3 * len(instances):
        issues.append("74HC32 marker count does not match donor-derived gate records")
    if chunk.count(b"74OR2") != len(instances):
        issues.append("74OR2 model marker count does not match gate count")
    for instance in instances:
        if cdb.count(instance.subpart_ref.encode("ascii")) != 1:
            issues.append(f"CDB missing subpart row {instance.subpart_ref}")
    return issues


def write_case() -> dict[str, object]:
    parsed = parse_or_expression(EXPRESSION)
    input_label_map = {name: compact_net_label(name) for name in parsed.inputs}
    steps = build_or2_tree(parsed.inputs, final_output=compact_net_label(parsed.output))
    instances = allocate_gates(steps)
    object_chunk, topology = build_object_chunk(instances)
    cdb = build_cdb(instances)

    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(DEVICE_SECTION_DONOR, "ROOT.DSN")
    dsn, pointers = build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)

    case_dir = OUT_ROOT / "T01_HC32_15_INPUT_OR_EXPR"
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / "T01_HC32_15_INPUT_OR_EXPR.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    (case_dir / "logic_plan.json").write_text(
        json.dumps(
            {
                "expression": EXPRESSION,
                "parsed": {"output": parsed.output, "operation": parsed.operation, "inputs": parsed.inputs},
                "terminal_label_map": input_label_map | {parsed.output: compact_net_label(parsed.output)},
                "gate_count": len(instances),
                "package_count": max(instance.package_number for instance in instances),
                "tree_steps": [step.__dict__ for step in steps],
                "gate_topology": topology,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (case_dir / "circuit_input.json").write_text(
        json.dumps(
            {
                "mode": "logic_expression_to_74hc32",
                "expression": EXPRESSION,
                "hidden_supply_policy": "Ignore physical pin 14/VCC/+5V and pin 7/GND/0V for each 74HC32 package.",
                "terminal_policy": "Only IC signal pins use input/output terminals. Passive, power, and ground endpoints use bidirectional/special terminal policy in mixed IC packs.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "case_id": "T01_HC32_15_INPUT_OR_EXPR",
        "description": "Expression-driven 15-input OR tree using four 74HC32 packages and fourteen OR2 gates.",
        "method": "or_expression_parser_plus_hc32_component_first_gate_slice_allocator",
        "hidden_supply_policy": "Pins 14 and 7 on U1-U4 are ignored as hidden Proteus 74HC32 supply.",
        "terminal_policy": "IC signal pins are ordinary input/output terminals; non-IC endpoints are not present in this pure logic case.",
        "static_validation_issues": static_issues(output, instances),
        "section_pointers": pointers,
        "marker_counts": marker_counts(object_chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(object_chunk),
        },
        "proteus_result_pending": True,
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


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
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifest = write_case()
    summary = {
        "batch": "IC_HC32_LOGIC_V1_TEMP_2026_06_08",
        "purpose": "First Boolean-expression interpreter pack for 74HC32 OR-only synthesis.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "test_order": [manifest["case_id"]],
        "terminal_policy": {
            "ic_signal_pins": "$TERINPUT/$TEROUTPUT",
            "passive_power_ground_endpoints": "bidirectional/special terminal policy in mixed IC packs",
            "ic_supply": "hidden; pin 14 and pin 7 are ignored for 74HC32 supply",
        },
        "cases": [manifest],
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": 1}, indent=2))


if __name__ == "__main__":
    main()
