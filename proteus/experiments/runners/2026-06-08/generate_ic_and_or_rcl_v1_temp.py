"""Generate the first mixed 74HC08 + 74HC32 + R/C/L test pack.

This temporary pack intentionally emits exactly fifteen IC gate subparts:
eight 74HC08 AND2 gates and seven 74HC32 OR2 gates. The OR output then drives
a donor-derived R-C-L branch. IC signal pins remain ordinary input/output
terminals; passive and power/ground endpoints use the accepted bidirectional
production conversion.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
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
from proteusgen.bidirectional import convert_production_terminals
from proteusgen.logic_expression import LogicGateStep
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes, _u32
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "experiments" / "ic_and_or_rcl_v1_temp_2026_06_08"
ARCHIVE_PATH = REPO / "experiments" / "IC_AND_OR_RCL_V1_TEMP_2026_06_08.zip"

HC08_RCL_DEVICE_DONOR = REPO / "proteus_ic" / "donors" / "74hc08" / "IC_HC08_M04_RCL_LOAD.pdsprj"
HC32_DEVICE_DONOR = REPO / "proteus_ic" / "donors" / "74hc32" / "IC_HC32_M02_ALL4_IO.pdsprj"
HC08_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-08" / "generate_ic_hc08_logic_v1_temp.py"
HC32_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-08" / "generate_ic_hc32_logic_v1_temp.py"

AND_PROP_TEXT = b"{MODFILE=74AND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00"
OR_PROP_TEXT = b"{MODFILE=74OR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00"

MARKERS = (
    b"74HC08",
    b"74AND2",
    b"74HC32",
    b"74OR2",
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
class PassiveSpec:
    ref: str
    kind: str
    value: str
    left: str
    right: str
    x: int
    y: int
    object_id: int


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HC08 = _load_module("hc08_logic_temp", HC08_SCRIPT)
HC32 = _load_module("hc32_logic_temp", HC32_SCRIPT)


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


def _device_section(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise ValueError("ROOT.DSN does not contain the expected device section.")
    return dsn[insert + len(marker) : first]


def _merged_device_section() -> bytes:
    hc08_rcl = _device_section(read_internal_file(HC08_RCL_DEVICE_DONOR, "ROOT.DSN"))
    hc32 = _device_section(read_internal_file(HC32_DEVICE_DONOR, "ROOT.DSN"))
    if len(hc08_rcl) < 4 or len(hc32) < 4:
        raise RuntimeError("Device donor section is too small to merge safely.")
    return hc08_rcl[:-4] + hc32[:-4] + b"\x00\x00\x00\x00"


def build_dsn_with_device_section(base_dsn: bytes, donor_dsn: bytes, object_chunk: bytes, device_section: bytes) -> tuple[bytes, dict[str, int]]:
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise ValueError("Base or donor ROOT.DSN does not match the V9 generator section model.")
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


def _gate_steps() -> tuple[list[LogicGateStep], list[LogicGateStep]]:
    and_steps = [
        LogicGateStep(1, 1, "X1", "X2", "A1"),
        LogicGateStep(2, 1, "X3", "X4", "A2"),
        LogicGateStep(3, 1, "X5", "X6", "A3"),
        LogicGateStep(4, 1, "X7", "X8", "A4"),
        LogicGateStep(5, 1, "X9", "XA", "A5"),
        LogicGateStep(6, 1, "XB", "XC", "A6"),
        LogicGateStep(7, 1, "XD", "XE", "A7"),
        LogicGateStep(8, 1, "XF", "V0", "A8"),
    ]
    or_steps = [
        LogicGateStep(9, 2, "A1", "A2", "B1"),
        LogicGateStep(10, 2, "A3", "A4", "B2"),
        LogicGateStep(11, 2, "A5", "A6", "B3"),
        LogicGateStep(12, 2, "A7", "A8", "B4"),
        LogicGateStep(13, 3, "B1", "B2", "C1"),
        LogicGateStep(14, 3, "B3", "B4", "C2"),
        LogicGateStep(15, 4, "C1", "C2", "Y0"),
    ]
    return and_steps, or_steps


def build_ic_records() -> tuple[bytes, list[dict[str, object]]]:
    and_steps, or_steps = _gate_steps()
    records: list[bytes] = []
    topology: list[dict[str, object]] = []
    for zero_index, step in enumerate(and_steps):
        package_number = zero_index // 4 + 1
        gate_letter = "ABCD"[zero_index % 4]
        instance = HC08.GateInstance(
            step=step,
            package_number=package_number,
            gate_letter=gate_letter,
            object_id=zero_index + 1,
            dx=(package_number - 1) * HC08.COLUMN_SPACING,
            dy=0,
        )
        record, row = HC08.build_gate_record(instance, final=False)
        row["family"] = "74HC08"
        row["role"] = "AND2"
        records.append(record)
        topology.append(row)
    for zero_index, step in enumerate(or_steps):
        package_number = zero_index // 4 + 3
        gate_letter = "ABCD"[zero_index % 4]
        instance = HC32.GateInstance(
            step=step,
            package_number=package_number,
            gate_letter=gate_letter,
            object_id=zero_index + 9,
            dx=(package_number - 1) * HC32.COLUMN_SPACING,
            dy=0,
        )
        record, row = HC32.build_gate_record(instance, final=False)
        row["family"] = "74HC32"
        row["role"] = "OR2"
        records.append(record)
        topology.append(row)
    return b"".join(records), topology


def _rcl_spec(index: int, passive: PassiveSpec) -> rcl.RclSpec:
    kind = {"R": "RESISTOR", "C": "CAPACITOR", "L": "INDUCTOR"}[passive.kind]
    return rcl.RclSpec(
        idx=passive.object_id,
        source_ref=passive.ref,
        ref=passive.ref,
        kind=kind,
        value=passive.value,
        visible_value=passive.value,
        left=passive.left,
        right=passive.right,
        x=passive.x,
        y=passive.y,
        visual_data={"x": passive.x, "y": passive.y, "manual_unit_index": index},
    )


def build_passive_chunk(registry: FixtureRegistry) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, object]], list[dict[str, object]], list[str]]:
    donor = registry.get("rcl_4x_t07_unit_donor")
    templates = rcl._load_rcl_unit_templates(donor.path)
    passives = (
        PassiveSpec("R1", "R", "10k", "Y0", "P1", 22_860_000, 4_826_000, 16),
        PassiveSpec("C1", "C", "1uF", "P1", "P2", 22_860_000, 3_048_000, 17),
        PassiveSpec("L1", "L", "5mH", "P2", "G0", 22_860_000, 1_270_000, 18),
    )
    records: list[bytes] = []
    specs: list[rcl.RclSpec] = []
    topology: list[dict[str, object]] = []
    for unit_index, passive in enumerate(passives, start=1):
        spec = _rcl_spec(unit_index, passive)
        slot = templates.units[(unit_index - 1) % len(templates.units)]
        suffixes = rcl._suffixes(unit_index)
        final = unit_index == len(passives)
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


def build_object_chunk(registry: FixtureRegistry) -> tuple[bytes, list[dict[str, object]], list[rcl.RclSpec], list[dict[str, object]], list[dict[str, object]], list[str]]:
    ic_records, ic_topology = build_ic_records()
    passive_chunk, passive_specs, passive_topology, replacements, issues = build_passive_chunk(registry)
    if passive_chunk[0] != 0:
        issues.append("converted passive chunk does not start with object header 00")
    object_chunk = b"\x00" + ic_records + passive_chunk[1:]
    if object_chunk[-1] != 0xFF:
        issues.append("combined object chunk final byte is not FF")
    return object_chunk, ic_topology, passive_specs, passive_topology, replacements, issues


def build_cdb(ic_topology: list[dict[str, object]], passive_specs: list[rcl.RclSpec]) -> bytes:
    out = bytearray()
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + _enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + _enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + _enc_str("Master Sheet") + _u32(10) + _u32(0)

    out += _u32(len(ic_topology) + len(passive_specs))
    for row in ic_topology:
        object_id = int(row["object_id"])
        package_number = int(str(row["package_ref"])[1:])
        gate_letter = str(row["gate_letter"])
        gate_info = (HC08.GATE_PINS if row["family"] == "74HC08" else HC32.GATE_PINS)[gate_letter]
        out += _u32(object_id) + _u32(1) + _u32(0) + _u32(object_id)
        out += _enc_str(str(row["subpart_ref"])) + _u32(3)
        for logical, physical in gate_info["pins"]:
            out += _enc_str(logical) + _enc_str(physical)
        out += _u32(0) + _u32(package_number) + _u32(gate_info["index"] - 1)
    for spec in sorted(passive_specs, key=lambda item: item.idx):
        out += _u32(spec.idx) + _u32(1) + _u32(0) + _u32(spec.idx) + _enc_str(spec.ref)
        if spec.kind == "CAPACITOR":
            out += _u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += _u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += _u32(0) + _u32(spec.idx) + _u32(0)

    out += _u32(1) + _u32(1) + b"\x00" + _enc_str("") + _u32(1)
    out += _u32(4 + len(passive_specs))
    for package_number, part, prop in (
        (1, "74HC08", AND_PROP_TEXT),
        (2, "74HC08", AND_PROP_TEXT),
        (3, "74HC32", OR_PROP_TEXT),
        (4, "74HC32", OR_PROP_TEXT),
    ):
        package_ref = f"U{package_number}"
        out += _u32(package_number) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
        out += _enc_str(package_ref) + _enc_str(part) + _enc_str(part) + _enc_str("DIL14")
        out += _enc_text(prop)
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


def static_issues(output: Path, object_chunk: bytes, cdb: bytes, passive_issues: list[str]) -> list[str]:
    issues = list(passive_issues)
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(output, "ROOT.DSN")
    if _extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from combined object chunk")
    counts = marker_counts(object_chunk)
    expected = {
        "74HC08": 24,
        "74AND2": 8,
        "74HC32": 21,
        "74OR2": 7,
        "$TERINPUT": 30,
        "$TEROUTPUT": 15,
        "$TERBIDIR": 6,
        "$TERPOWER": 1,
        "$TERGROUND": 1,
        "RESISTOR": 2,
        "CAPACITOR": 1,
        "CAP10": 1,
        "REALIND": 3,
        "COMPONENT ID": 18,
    }
    for marker, want in expected.items():
        if counts[marker] != want:
            issues.append(f"{marker} count {counts[marker]} != {want}")
    for forbidden in (b"VSOURCE", b"CSOURCE", b"VSINE", b"LOGICSTATE", b"LOGICPROBE"):
        if object_chunk.count(forbidden):
            issues.append(f"unexpected marker {forbidden.decode('ascii')}")
    for subpart in ("U1:A", "U1:B", "U1:C", "U1:D", "U2:A", "U2:B", "U2:C", "U2:D", "U3:A", "U3:B", "U3:C", "U3:D", "U4:A", "U4:B", "U4:C"):
        if cdb.count(subpart.encode("ascii")) != 1:
            issues.append(f"CDB missing subpart row {subpart}")
    return issues


def write_case() -> dict[str, object]:
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    object_chunk, ic_topology, passive_specs, passive_topology, replacements, passive_issues = build_object_chunk(registry)
    cdb = build_cdb(ic_topology, passive_specs)
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(HC08_RCL_DEVICE_DONOR, "ROOT.DSN")
    dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, object_chunk, _merged_device_section())
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)

    case_id = "T01_15IC_AND_OR_RCL_MIXED"
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    circuit_input = {
        "mode": "mixed_ic_logic_and_or_rcl",
        "ic_gate_count": 15,
        "ic_packages": [
            {"ref": "U1", "part": "74HC08", "gates": ["A", "B", "C", "D"]},
            {"ref": "U2", "part": "74HC08", "gates": ["A", "B", "C", "D"]},
            {"ref": "U3", "part": "74HC32", "gates": ["A", "B", "C", "D"]},
            {"ref": "U4", "part": "74HC32", "gates": ["A", "B", "C"]},
        ],
        "logic": "Eight AND gates create A1..A8 from X1..XF plus V0. Seven OR gates reduce A1..A8 to Y0.",
        "rlc_load": [
            {"ref": "R1", "value": "10k", "nodes": ["Y0", "P1"]},
            {"ref": "C1", "value": "1uF", "nodes": ["P1", "P2"]},
            {"ref": "L1", "value": "5mH", "nodes": ["P2", "G0"]},
        ],
        "terminal_policy": {
            "ic_signal_pins": "$TERINPUT/$TEROUTPUT",
            "passive_endpoints": "$TERBIDIR after production conversion",
            "logic_high": "V0 power terminal bridge",
            "ground": "G0 ground terminal",
            "ic_supply": "hidden; ignore physical pin 14 and pin 7 for both packages/families",
        },
    }
    (case_dir / "circuit_input.json").write_text(json.dumps(circuit_input, indent=2) + "\n", encoding="utf-8")
    plan = {
        "ic_gate_count": len(ic_topology),
        "and_gate_count": sum(1 for row in ic_topology if row["family"] == "74HC08"),
        "or_gate_count": sum(1 for row in ic_topology if row["family"] == "74HC32"),
        "passive_component_count": len(passive_specs),
        "ic_topology": ic_topology,
        "passive_topology": passive_topology,
        "terminal_replacements": replacements,
    }
    (case_dir / "logic_rcl_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    issues = static_issues(output, object_chunk, cdb, passive_issues)
    manifest = {
        "case_id": case_id,
        "description": "Mixed AND/OR/RCL diagnostic with exactly 15 IC gate subparts: 8 AND2 + 7 OR2, then a series R-C-L branch.",
        "method": "accepted_hc08_gate_records_plus_accepted_hc32_component_first_records_plus_bidirectional_converted_rcl_records",
        "status": "temporary_pending_user_proteus_testing",
        "ic_gate_count": len(ic_topology),
        "and_gate_count": 8,
        "or_gate_count": 7,
        "passive_component_count": len(passive_specs),
        "terminal_policy": circuit_input["terminal_policy"],
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
        "batch": "IC_AND_OR_RCL_V1_TEMP_2026_06_08",
        "purpose": "First mixed 74HC08/74HC32/RCL test with exactly fifteen IC gate subparts.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "test_order": [manifest["case_id"]],
        "cases": [manifest],
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": 1}, indent=2))


if __name__ == "__main__":
    main()
