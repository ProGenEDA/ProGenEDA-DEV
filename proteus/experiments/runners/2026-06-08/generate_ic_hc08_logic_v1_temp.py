"""Generate the first expression-driven 74HC08 logic test pack.

This temporary generator maps an AND-only Boolean expression onto accepted
74HC08 gate subpart records. IC signal pins remain $TERINPUT/$TEROUTPUT records.
Non-IC passive/power/ground terminals must use the production bidirectional
method in later mixed IC packs; this pure-logic pack has no passive endpoints.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.logic_expression import AndGateStep, build_and2_tree, compact_net_label, parse_and_expression
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _i32, _sha256_bytes, _u32, build_dsn
from proteusgen.source_driven import _terminal_events
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_hc08_logic_v1_temp_2026_06_08"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_HC08_LOGIC_V1_TEMP_2026_06_08.zip"

HC08_ALL4_DONOR = REPO / "proteus" / "active" / "evidence" / "donors" / "74hc08" / "IC_HC08_M01_ALL4_IO.pdsprj"
DEVICE_SECTION_DONOR = REPO / "proteus" / "active" / "evidence" / "donors" / "74hc08" / "IC_HC08_M02_TWO_PACKAGES_IO.pdsprj"

EXPRESSION = (
    r"Y = X_1 \cdot X_2 \cdot X_3 \cdot X_4 \cdot X_5 \cdot X_6 \cdot "
    r"X_7 \cdot X_8 \cdot X_9 \cdot X_{10} \cdot X_{11} \cdot X_{12} "
    r"\cdot X_{13} \cdot X_{14} \cdot X_{15}"
)

GATE_LETTERS = "ABCD"
GATE_PINS = {
    "A": {"index": 1, "donor_labels": ("A1", "B1", "Y1"), "pins": (("A", "1"), ("B", "2"), ("Y", "3"))},
    "B": {"index": 2, "donor_labels": ("A2", "B2", "Y2"), "pins": (("A", "4"), ("B", "5"), ("Y", "6"))},
    "C": {"index": 3, "donor_labels": ("A3", "B3", "Y3"), "pins": (("A", "9"), ("B", "10"), ("Y", "8"))},
    "D": {"index": 4, "donor_labels": ("A4", "B4", "Y4"), "pins": (("A", "12"), ("B", "13"), ("Y", "11"))},
}

IC_PROP_TEXT = b"{MODFILE=74AND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00"

INPUT_A_START = 0
INPUT_B_START = 103
OUTPUT_START = 206
INPUT_SIZE = 103
OUTPUT_TERMINAL_SIZE = 104
GATE_RECORD_SIZE = 843
SUFFIX_BASE = 0x0379
SUFFIX_STEP = 0x027D
SUFFIX_B_OFFSET = 0x32
SUFFIX_Y_OFFSET = 0x64

COORD_X_OFFSETS = (1, 33, 104, 136, 207, 240, 317, 389, 464, 529, 656, 727, 735, 777, 785, 827, 835)
COORD_Y_OFFSETS = (5, 37, 108, 140, 211, 244, 321, 393, 468, 533, 660, 731, 739, 781, 789, 831, 839)
COLUMN_SPACING = 5_080_000

MARKERS = (
    b"74HC08",
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
    step: AndGateStep
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
    return _extract_object_chunk(read_internal_file(HC08_ALL4_DONOR, "ROOT.DSN"))


def _gate_combo(gate_letter: str) -> bytes:
    chunk = _all4_chunk()
    bounds = _terminal_events(chunk)
    starts = {label: start for start, _kind, label in bounds}
    ordered = sorted(bounds)
    start_to_end = {
        start: ordered[index + 1][0] if index + 1 < len(ordered) else len(chunk)
        for index, (start, _kind, _label) in enumerate(ordered)
    }
    parts: list[bytes] = []
    for label in GATE_PINS[gate_letter]["donor_labels"]:
        start = starts[label]
        parts.append(chunk[start : start_to_end[start]])
    combo = b"".join(parts)
    if combo[-1] == 0xFF:
        combo = combo[:-1]
    if len(combo) != GATE_RECORD_SIZE:
        raise RuntimeError(f"Unexpected gate combo size for {gate_letter}: {len(combo)}")
    return combo


def _patch_two_char_label(record: bytearray, start: int, *, output_terminal: bool, label: str) -> None:
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError(f"HC08 logic pack labels must be exactly two ASCII characters: {label!r}")
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


def _suffix_triplet(object_id: int) -> tuple[int, int, int]:
    base = SUFFIX_BASE + (object_id - 1) * SUFFIX_STEP
    return base, base + SUFFIX_B_OFFSET, base + SUFFIX_Y_OFFSET


def _patch_suffixes_and_id(record: bytearray, object_id: int) -> dict[str, str]:
    old_a = bytes(record[INPUT_A_START + INPUT_SIZE - 4 : INPUT_A_START + INPUT_SIZE - 2])
    old_b = bytes(record[INPUT_B_START + INPUT_SIZE - 4 : INPUT_B_START + INPUT_SIZE - 2])
    old_y = bytes(record[OUTPUT_START + OUTPUT_TERMINAL_SIZE - 4 : OUTPUT_START + OUTPUT_TERMINAL_SIZE - 2])
    old_assoc = old_a + b"\x01\x00" + old_b + b"\x01\x00" + old_y + b"\x01\x00"
    assoc_pos = bytes(record).find(old_assoc)
    if assoc_pos < 0:
        raise RuntimeError("Could not find HC08 gate suffix association block.")

    suffix_a, suffix_b, suffix_y = _suffix_triplet(object_id)
    new_a = suffix_a.to_bytes(2, "little")
    new_b = suffix_b.to_bytes(2, "little")
    new_y = suffix_y.to_bytes(2, "little")

    record[INPUT_A_START + INPUT_SIZE - 4 : INPUT_A_START + INPUT_SIZE - 2] = new_a
    record[INPUT_B_START + INPUT_SIZE - 4 : INPUT_B_START + INPUT_SIZE - 2] = new_b
    record[OUTPUT_START + OUTPUT_TERMINAL_SIZE - 4 : OUTPUT_START + OUTPUT_TERMINAL_SIZE - 2] = new_y
    record[assoc_pos : assoc_pos + 2] = new_a
    record[assoc_pos + 4 : assoc_pos + 6] = new_b
    record[assoc_pos + 8 : assoc_pos + 10] = new_y
    record[assoc_pos - 13 : assoc_pos - 9] = _u32(object_id)
    return {"in1": f"{suffix_a:04x}", "in2": f"{suffix_b:04x}", "out": f"{suffix_y:04x}"}


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
    suffixes = _patch_suffixes_and_id(record, instance.object_id)
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
        "suffixes": suffixes,
    }


def allocate_gates(steps: tuple[AndGateStep, ...]) -> tuple[GateInstance, ...]:
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
        out += _enc_str(package_ref) + _enc_str("74HC08") + _enc_str("74HC08") + _enc_str("DIL14")
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
    if chunk.count(b"$TERBIDIR"):
        issues.append("pure IC logic pack must not contain bidirectional terminals")
    for forbidden in (b"$TERPOWER", b"$TERGROUND", b"VSOURCE", b"CSOURCE", b"LOGICSTATE", b"LOGICPROBE"):
        if chunk.count(forbidden):
            issues.append(f"unexpected marker in pure HC08 logic pack: {forbidden.decode('ascii')}")
    if chunk.count(b"$TERINPUT") != 2 * len(instances):
        issues.append("$TERINPUT count does not match two inputs per gate")
    if chunk.count(b"$TEROUTPUT") != len(instances):
        issues.append("$TEROUTPUT count does not match one output per gate")
    if chunk.count(b"COMPONENT ID") != len(instances):
        issues.append("COMPONENT ID count does not match gate count")
    for instance in instances:
        if cdb.count(instance.subpart_ref.encode("ascii")) != 1:
            issues.append(f"CDB missing subpart row {instance.subpart_ref}")
    return issues


def write_case() -> dict[str, object]:
    parsed = parse_and_expression(EXPRESSION)
    input_label_map = {name: compact_net_label(name) for name in parsed.inputs}
    steps = build_and2_tree(parsed.inputs, final_output=compact_net_label(parsed.output))
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

    case_dir = OUT_ROOT / "T01_HC08_15_INPUT_AND_EXPR"
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / "T01_HC08_15_INPUT_AND_EXPR.pdsprj"
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
                "mode": "logic_expression_to_74hc08",
                "expression": EXPRESSION,
                "hidden_supply_policy": "Ignore physical pin 14/VCC/+5V and pin 7/GND/0V for each 74HC08 package.",
                "terminal_policy": "Only IC signal pins use input/output terminals. Passive, power, and ground endpoints use bidirectional/special terminal policy in mixed IC packs.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "case_id": "T01_HC08_15_INPUT_AND_EXPR",
        "description": "Expression-driven 15-input AND tree using four 74HC08 packages and fourteen AND2 gates.",
        "method": "and_expression_parser_plus_hc08_gate_slice_allocator",
        "hidden_supply_policy": "Pins 14 and 7 on U1-U4 are ignored as hidden Proteus 74HC08 supply.",
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
        "batch": "IC_HC08_LOGIC_V1_TEMP_2026_06_08",
        "purpose": "First Boolean-expression interpreter pack for 74HC08 AND-only synthesis.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "test_order": [manifest["case_id"]],
        "terminal_policy": {
            "ic_signal_pins": "$TERINPUT/$TEROUTPUT",
            "passive_power_ground_endpoints": "bidirectional/special terminal policy in mixed IC packs",
            "ic_supply": "hidden; pin 14 and pin 7 are ignored for 74HC08 supply",
        },
        "cases": [manifest],
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": 1}, indent=2))


if __name__ == "__main__":
    main()
