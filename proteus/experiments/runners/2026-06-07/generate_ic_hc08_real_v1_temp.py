"""Generate the first real 74HC08 circuit test pack.

This is a temporary experiment generator. It composes already accepted 74HC08
gate slices with already accepted R/C/L passive records, then writes complete
Proteus projects from E001. IC supply pins 14 and 7 are intentionally ignored:
Proteus handles 74HC08 power internally for these gate subparts.
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

from proteusgen import mixed_rcl as rcl
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes, build_dsn
from proteusgen.source_driven import _terminal_bounds
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_hc08_real_v1_temp_2026_06_07"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_HC08_REAL_V1_TEMP_2026_06_07.zip"

HC08_DONOR = REPO / "proteus" / "active" / "evidence" / "donors" / "74hc08" / "IC_HC08_M01_ALL4_IO.pdsprj"
DEVICE_SECTION_DONOR = REPO / "proteus" / "active" / "evidence" / "donors" / "74hc08" / "IC_HC08_M04_RCL_LOAD.pdsprj"
RCL_UNIT_DONOR = REPO / "proteus" / "active" / "fixtures" / "pdsprj" / "rcl_4x_t07_unit_donor.pdsprj"

MARKERS = (
    b"74HC08",
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
    b"LOGICSTATE",
    b"LOGICPROBE",
)

GATE_PINS = {
    "A": {"index": 1, "inputs": ("A1", "B1"), "output": "Y1", "pins": (("A", "1"), ("B", "2"), ("Y", "3"))},
    "B": {"index": 2, "inputs": ("A2", "B2"), "output": "Y2", "pins": (("A", "4"), ("B", "5"), ("Y", "6"))},
    "C": {"index": 3, "inputs": ("A3", "B3"), "output": "Y3", "pins": (("A", "9"), ("B", "10"), ("Y", "8"))},
    "D": {"index": 4, "inputs": ("A4", "B4"), "output": "Y4", "pins": (("A", "12"), ("B", "13"), ("Y", "11"))},
}

IC_PROP_TEXT = b"{MODFILE=74AND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00"


@dataclass(frozen=True)
class PassiveSpec:
    ref: str
    kind: str
    value: str
    left: str
    right: str
    x: int
    y: int


@dataclass(frozen=True)
class CircuitCase:
    case_id: str
    title: str
    gate: str
    description: str
    normalized_input: dict[str, object]
    passives: tuple[PassiveSpec, ...] = ()


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return rcl.rv9._u32(4 + len(data)) + data


def _gate_records(gate: str, *, final: bool) -> bytes:
    donor_chunk = _extract_object_chunk(read_internal_file(HC08_DONOR, "ROOT.DSN"))
    bounds = _terminal_bounds(donor_chunk)
    by_label = {label: donor_chunk[start:end] for start, end, _kind, label in bounds}
    gate_info = GATE_PINS[gate]
    input_a, input_b = gate_info["inputs"]
    output = gate_info["output"]
    try:
        records = [by_label[input_a], by_label[input_b], by_label[output]]
    except KeyError as exc:
        raise RuntimeError(f"HC08 donor is missing terminal slice {exc.args[0]!r}.") from exc
    records[-1] = _finalized_record(records[-1], final=final)
    return b"".join(records)


def _finalized_record(record: bytes, *, final: bool) -> bytes:
    if final:
        return record if record[-1] == 0xFF else record + b"\xFF"
    return record[:-1] if record[-1] == 0xFF else record


def _rcl_spec(index: int, spec: PassiveSpec) -> rcl.RclSpec:
    kind = {
        "R": "RESISTOR",
        "C": "CAPACITOR",
        "L": "INDUCTOR",
    }[spec.kind]
    return rcl.RclSpec(
        idx=index,
        source_ref=spec.ref,
        ref=spec.ref,
        kind=kind,
        value=spec.value,
        visible_value=spec.value,
        left=spec.left,
        right=spec.right,
        x=spec.x,
        y=spec.y,
        visual_data={"x": spec.x, "y": spec.y},
    )


def build_passive_records(passives: tuple[PassiveSpec, ...]) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, object]]]:
    if not passives:
        return b"", [], []
    templates = rcl._load_rcl_unit_templates(RCL_UNIT_DONOR)
    records: list[bytes] = []
    specs: list[rcl.RclSpec] = []
    topology: list[dict[str, object]] = []
    for unit_index, passive in enumerate(passives, start=1):
        spec = _rcl_spec(unit_index + 4, passive)
        slot = templates.units[(unit_index - 1) % len(templates.units)]
        suffixes = rcl._suffixes(unit_index)
        final = unit_index == len(passives)
        if passive.kind == "C":
            records.append(rcl._patch_cap(slot, spec, suffixes, final=final))
            in_key, out_key = "cap_in", "cap_out"
        elif passive.kind == "L":
            records.append(
                rcl._patch_ind_input(slot.l_input, spec.left, spec.idx, spec.x, spec.y, suffixes["l_in"])
                + rcl._patch_l_body(slot, spec, suffixes, final=final)
            )
            in_key, out_key = "l_in", "l_out"
        elif passive.kind == "R":
            records.append(
                rcl._patch_ind_input(slot.r_input, spec.left, spec.idx, spec.x, spec.y, suffixes["r_in"])
                + rcl._patch_r_body(slot, spec, templates, suffixes, final=final)
            )
            in_key, out_key = "r_in", "r_out"
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
    return b"".join(records), specs, topology


def build_cdb(gate: str, passive_specs: list[rcl.RclSpec]) -> bytes:
    gate_info = GATE_PINS[gate]
    ordered = sorted(passive_specs, key=lambda spec: spec.idx)
    out = bytearray()
    out += rcl.rv9._u32(7)
    out += rcl.rv9._u32(1) + rcl.rv9._u32(1) + rcl.rv9._u32(0) + _enc_str("ROOT") + b"\x00"
    out += rcl.rv9._u32(0) + rcl.rv9._u32(1) + rcl.rv9._u32(1)
    out += rcl.rv9._u32(2)
    out += rcl.rv9._u32(1) + rcl.rv9._u32(3) + rcl.rv9._u32(1) + _enc_str("") + rcl.rv9._u32(10) + rcl.rv9._u32(0)
    out += rcl.rv9._u32(2) + rcl.rv9._u32(2) + rcl.rv9._u32(0) + _enc_str("Master Sheet") + rcl.rv9._u32(10) + rcl.rv9._u32(0)

    out += rcl.rv9._u32(1 + len(ordered))
    gate_index = int(gate_info["index"])
    out += rcl.rv9._u32(gate_index) + rcl.rv9._u32(1) + rcl.rv9._u32(0) + rcl.rv9._u32(gate_index)
    out += _enc_str(f"U1:{gate}") + rcl.rv9._u32(3)
    for logical, physical in gate_info["pins"]:
        out += _enc_str(logical) + _enc_str(physical)
    out += rcl.rv9._u32(0) + rcl.rv9._u32(1) + rcl.rv9._u32(gate_index - 1)
    for spec in ordered:
        out += rcl.rv9._u32(spec.idx) + rcl.rv9._u32(1) + rcl.rv9._u32(0) + rcl.rv9._u32(spec.idx) + _enc_str(spec.ref)
        if spec.kind == "CAPACITOR":
            out += rcl.rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += rcl.rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rcl.rv9._u32(0) + rcl.rv9._u32(spec.idx) + rcl.rv9._u32(0)

    out += rcl.rv9._u32(1) + rcl.rv9._u32(1) + b"\x00" + _enc_str("") + rcl.rv9._u32(1)
    out += rcl.rv9._u32(1 + len(ordered))
    out += rcl.rv9._u32(1) + rcl.rv9._u32(1) + rcl.rv9._u32(0) + rcl.rv9._u32(0) + rcl.rv9._u32(0)
    out += _enc_str("U1") + _enc_str("74HC08") + _enc_str("74HC08") + _enc_str("DIL14") + _enc_text(IC_PROP_TEXT)
    for spec in ordered:
        out += rcl.rv9._u32(spec.idx) + rcl.rv9._u32(1) + rcl.rv9._u32(0) + rcl.rv9._u32(0) + rcl.rv9._u32(0)
        if spec.kind == "CAPACITOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10")
            out += _enc_text(rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("")
            out += _enc_text(rcl.INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("")
            out += _enc_text(rcl.rv9.PROP_TEXT)
    out += rcl.rv9._u32(0)
    return bytes(out)


def build_object_chunk(case: CircuitCase) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, object]]]:
    passive_records, specs, topology = build_passive_records(case.passives)
    gate_records = _gate_records(case.gate, final=not passive_records)
    chunk = b"\x00" + gate_records + passive_records
    return chunk, specs, topology


def static_issues(path: Path, case: CircuitCase, passive_specs: list[rcl.RclSpec]) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(path)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(path, "ROOT.DSN")
    cdb = read_internal_file(path, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"$TERBIDIR"):
        issues.append("bidirectional terminals are not allowed in IC tests")
    if chunk.count(b"VSOURCE") or chunk.count(b"CSOURCE"):
        issues.append("source records are not allowed in IC tests")
    if chunk.count(b"LOGICSTATE") or chunk.count(b"LOGICPROBE"):
        issues.append("logic state/probe components are not allowed in this pack")
    if chunk.count(b"$TERPOWER"):
        issues.append("unexpected power terminal; HC08 supply pins 14 and 7 must stay hidden")
    if cdb.count(f"U1:{case.gate}".encode("ascii")) != 1:
        issues.append(f"CDB does not contain exactly one U1:{case.gate} subpart row")
    if cdb.count(b"VCC") or cdb.count(b"GND"):
        issues.append("CDB contains explicit VCC/GND supply labels")
    expected_components = 1 + len(passive_specs)
    if chunk.count(b"COMPONENT ID") != expected_components:
        issues.append(f"COMPONENT ID count {chunk.count(b'COMPONENT ID')} != {expected_components}")
    scan_issues = rcl._scan_wire_issues(chunk)
    issues.extend(scan_issues)
    return issues


def write_case(case: CircuitCase) -> dict[str, object]:
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    device_donor_dsn = read_internal_file(DEVICE_SECTION_DONOR, "ROOT.DSN")
    object_chunk, passive_specs, topology = build_object_chunk(case)
    dsn, pointers = build_dsn(base_dsn, device_donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    cdb = build_cdb(case.gate, passive_specs)

    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "circuit_input.json").write_text(json.dumps(case.normalized_input, indent=2) + "\n", encoding="utf-8")
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)

    counts = marker_counts(object_chunk)
    manifest = {
        "case_id": case.case_id,
        "title": case.title,
        "description": case.description,
        "method": "hc08_m01_gate_slice_plus_locked_rcl_units",
        "hidden_supply_policy": "Ignore user pin 14/VCC/+5V and pin 7/GND/0V for 74HC08 package supply.",
        "gate": case.gate,
        "gate_subpart": f"U1:{case.gate}",
        "gate_pin_mapping": GATE_PINS[case.gate],
        "passive_topology": topology,
        "section_pointers": pointers,
        "static_validation_issues": static_issues(output, case, passive_specs),
        "marker_counts": counts,
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


def cases() -> list[CircuitCase]:
    return [
        CircuitCase(
            case_id="T01_HC08_GATE1_PURE_AND",
            title="Pure Digital AND Gate, Gate 1",
            gate="A",
            description="U1:A with input terminals A1/B1 and output terminal Y1. Package supply pins 14 and 7 are ignored.",
            normalized_input={
                "ic": {"part": "74HC08", "package_ref": "U1", "gate": "A", "ignored_supply_pins": [14, 7]},
                "connections": [
                    {"pin": 1, "maps_to": "U1:A.A", "net": "A1"},
                    {"pin": 2, "maps_to": "U1:A.B", "net": "B1"},
                    {"pin": 3, "maps_to": "U1:A.Y", "net": "Y1"},
                ],
            },
        ),
        CircuitCase(
            case_id="T02_HC08_GATE1_RC_TURN_ON_DELAY",
            title="RC Turn-On Delay, Gate 1",
            gate="A",
            description="Signal A goes direct to A1. Signal B passes through R1 to B1, with C1 from B1 to ground.",
            normalized_input={
                "ic": {"part": "74HC08", "package_ref": "U1", "gate": "A", "ignored_supply_pins": [14, 7]},
                "passives": [
                    {"ref": "R1", "type": "R", "value": "10k", "nodes": ["B0", "B1"]},
                    {"ref": "C1", "type": "C", "value": "1uF", "nodes": ["B1", "G0"]},
                ],
            },
            passives=(
                PassiveSpec("R1", "R", "10k", "B0", "B1", -10_160_000, 4_826_000),
                PassiveSpec("C1", "C", "1uF", "B1", "G0", -10_160_000, 3_810_000),
            ),
        ),
        CircuitCase(
            case_id="T03_HC08_GATE2_LC_OUTPUT_FILTER",
            title="LC Low-Pass Filtered Output, Gate 2",
            gate="B",
            description="U1:B output Y2 feeds L1 to node N2, then C1 goes from N2 to ground.",
            normalized_input={
                "ic": {"part": "74HC08", "package_ref": "U1", "gate": "B", "ignored_supply_pins": [14, 7]},
                "passives": [
                    {"ref": "L1", "type": "L", "value": "5mH", "nodes": ["Y2", "N2"]},
                    {"ref": "C1", "type": "C", "value": "1uF", "nodes": ["N2", "G0"]},
                ],
            },
            passives=(
                PassiveSpec("L1", "L", "5mH", "Y2", "N2", -4_064_000, 3_302_000),
                PassiveSpec("C1", "C", "1uF", "N2", "G0", -2_286_000, 2_286_000),
            ),
        ),
        CircuitCase(
            case_id="T04_HC08_GATE3_RLC_INPUT_FILTER",
            title="RLC Damped Noise Filter on Input, Gate 3",
            gate="C",
            description="A3 is direct. Noisy B0 passes through L1 and R1 to B3, with C1 from B3 to ground.",
            normalized_input={
                "ic": {"part": "74HC08", "package_ref": "U1", "gate": "C", "ignored_supply_pins": [14, 7]},
                "passives": [
                    {"ref": "L1", "type": "L", "value": "5mH", "nodes": ["B0", "M3"]},
                    {"ref": "R1", "type": "R", "value": "10k", "nodes": ["M3", "B3"]},
                    {"ref": "C1", "type": "C", "value": "1uF", "nodes": ["B3", "G0"]},
                ],
            },
            passives=(
                PassiveSpec("L1", "L", "5mH", "B0", "M3", -12_192_000, 1_270_000),
                PassiveSpec("R1", "R", "10k", "M3", "B3", -10_160_000, 1_270_000),
                PassiveSpec("C1", "C", "1uF", "B3", "G0", -10_160_000, 254_000),
            ),
        ),
        CircuitCase(
            case_id="T05_HC08_GATE4_DUAL_RC_WINDOW",
            title="Dual-RC Coincidence Timing Window, Gate 4",
            gate="D",
            description="Master trigger T0 feeds R1/C1 to A4 and R2/C2 to B4. Output is Y4.",
            normalized_input={
                "ic": {"part": "74HC08", "package_ref": "U1", "gate": "D", "ignored_supply_pins": [14, 7]},
                "passives": [
                    {"ref": "R1", "type": "R", "value": "10k", "nodes": ["T0", "A4"]},
                    {"ref": "C1", "type": "C", "value": "1uF", "nodes": ["A4", "G0"]},
                    {"ref": "R2", "type": "R", "value": "47k", "nodes": ["T0", "B4"]},
                    {"ref": "C2", "type": "C", "value": "1uF", "nodes": ["B4", "G0"]},
                ],
            },
            passives=(
                PassiveSpec("R1", "R", "10k", "T0", "A4", -10_160_000, 0),
                PassiveSpec("C1", "C", "1uF", "A4", "G0", -10_160_000, -762_000),
                PassiveSpec("R2", "R", "47k", "T0", "B4", -10_160_000, -1_524_000),
                PassiveSpec("C2", "C", "1uF", "B4", "G0", -10_160_000, -2_286_000),
            ),
        ),
    ]


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 7, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests = [write_case(case) for case in cases()]
    summary = {
        "batch": "IC_HC08_REAL_V1_TEMP_2026_06_07",
        "purpose": "First real 74HC08 user-circuit pack using gate subpart slices and locked passive R/C/L fragments.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "test_order": [manifest["case_id"] for manifest in manifests],
        "shared_rules": [
            "Ignore 74HC08 supply pins 14/VCC/+5V and 7/GND/0V; do not generate explicit IC supply pins.",
            "Use U1:A/B/C/D subparts for gates 1..4.",
            "Use ordinary input and output terminals for IC signal pins.",
            "Use ground terminals only where the user ties a signal/passive branch to ground.",
            "Do not use bidirectional terminals, DCV/DCC/ACV/ACC source records, LOGICSTATE, or LOGICPROBE in this IC pack.",
        ],
        "cases": manifests,
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": len(manifests)}, indent=2))


if __name__ == "__main__":
    main()
