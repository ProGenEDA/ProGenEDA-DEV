"""Generate first composed logic tests for accepted remaining combinational ICs.

This is the step after donor transplants passed. It builds fresh object chunks
and CDB rows from donor gate slices:

- 74HC00: generated three-input NAND using three NAND gates.
- 74HC02: generated three-input NOR using three NOR gates.
- 74HC86: generated four-input XOR using three XOR gates.
- 74HC266: generated binary XNOR-chain diagnostic using three donated 74HC266 gates.

The XNOR case is deliberately a chain diagnostic, not a normalized n-input
Boolean expression, because Proteus stores the supplied 74HC266 with a 74XOR2
function marker and its exact semantic behavior must be visually/simulation
tested before promotion.
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

from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes, _u32, build_dsn
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_remaining_generated_logic_v1_temp_2026_06_08"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_REMAINING_GENERATED_LOGIC_V1_TEMP_2026_06_08.zip"

GATE_LETTERS = "ABCD"
GATE_PINS = {
    "A": {"index": 1, "pins": (("A", "1"), ("B", "2"), ("Y", "3"))},
    "B": {"index": 2, "pins": (("A", "4"), ("B", "5"), ("Y", "6"))},
    "C": {"index": 3, "pins": (("A", "9"), ("B", "10"), ("Y", "8"))},
    "D": {"index": 4, "pins": (("A", "12"), ("B", "13"), ("Y", "11"))},
}

MARKERS = (
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
    function_marker: str
    donor: Path
    record_shape: str
    prop_text: bytes
    description: str


@dataclass(frozen=True)
class GateStep:
    gate_letter: str
    left: str
    right: str
    output: str
    semantic_note: str


CONFIGS = {
    "74hc00": FamilyConfig(
        key="74hc00",
        device="74HC00",
        function_marker="74NAND2",
        donor=REPO / "proteus" / "active" / "evidence" / "donors" / "74hc00" / "IC_74HC00_M02_ALL4_IO.pdsprj",
        record_shape="terminal_first",
        prop_text=b"{MODFILE=74NAND2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        description="Generated three-input NAND: Y0 = NAND(X1, X2, X3).",
    ),
    "74hc02": FamilyConfig(
        key="74hc02",
        device="74HC02",
        function_marker="74NOR2",
        donor=REPO / "proteus" / "active" / "evidence" / "donors" / "74hc02" / "IC_74HC02_M02_ALL4_IO.pdsprj",
        record_shape="component_first",
        prop_text=b"{MODFILE=74NOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        description="Generated three-input NOR: Y0 = NOR(X1, X2, X3).",
    ),
    "74hc86": FamilyConfig(
        key="74hc86",
        device="74HC86",
        function_marker="74XOR2",
        donor=REPO / "proteus" / "active" / "evidence" / "donors" / "74hc86" / "IC_74HC86_M02_ALL4_IO.pdsprj",
        record_shape="component_first",
        prop_text=b"{MODFILE=74XOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        description="Generated four-input XOR: Y0 = X1 XOR X2 XOR X3 XOR X4.",
    ),
    "74hc266": FamilyConfig(
        key="74hc266",
        device="74HC266",
        function_marker="74XOR2",
        donor=REPO / "proteus" / "active" / "evidence" / "donors" / "74hc266" / "IC_74HC266_M02_ALL4_IO.pdsprj",
        record_shape="component_first",
        prop_text=b"{MODFILE=74XOR2.MDF}\n{PACKAGE=DIL14}\n{ITFMOD=TTLHC}\n\x00",
        description="Generated 74HC266 XNOR-chain diagnostic preserving observed 74XOR2 function marker.",
    ),
}


STEPS = {
    "74hc00": (
        GateStep("A", "X1", "X2", "N1", "N1 = NAND(X1, X2)"),
        GateStep("B", "N1", "N1", "A1", "A1 = AND(X1, X2) by NAND self-inversion"),
        GateStep("C", "A1", "X3", "Y0", "Y0 = NAND(X1 AND X2, X3)"),
    ),
    "74hc02": (
        GateStep("A", "X1", "X2", "N1", "N1 = NOR(X1, X2)"),
        GateStep("B", "N1", "N1", "O1", "O1 = OR(X1, X2) by NOR self-inversion"),
        GateStep("C", "O1", "X3", "Y0", "Y0 = NOR((X1 OR X2), X3)"),
    ),
    "74hc86": (
        GateStep("A", "X1", "X2", "P1", "P1 = XOR(X1, X2)"),
        GateStep("B", "X3", "X4", "P2", "P2 = XOR(X3, X4)"),
        GateStep("C", "P1", "P2", "Y0", "Y0 = XOR(P1, P2)"),
    ),
    "74hc266": (
        GateStep("A", "X1", "X2", "E1", "E1 = donated 74HC266 gate output for X1/X2"),
        GateStep("B", "X3", "X4", "E2", "E2 = donated 74HC266 gate output for X3/X4"),
        GateStep("C", "E1", "E2", "Y0", "Y0 = donated 74HC266 gate output for E1/E2"),
    ),
}


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return _u32(4 + len(data)) + data


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


def gate_record(config: FamilyConfig, gate_letter: str) -> bytes:
    chunk = _donor_chunk(config)
    gate_index = GATE_LETTERS.index(gate_letter)
    if config.record_shape == "terminal_first":
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


def patch_terminal_labels(record: bytes, replacements: dict[str, str]) -> bytes:
    out = bytearray(record)
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True)):
        pos = 0
        while True:
            marker_pos = record.find(marker, pos)
            if marker_pos < 0:
                break
            length_pos = marker_pos + (17 if output_terminal else 16)
            label_pos = marker_pos + (18 if output_terminal else 17)
            length = record[length_pos]
            old = record[label_pos : label_pos + length].decode("ascii", errors="replace")
            new = replacements.get(old)
            if new is not None:
                raw = new.encode("ascii")
                if len(raw) != length:
                    raise ValueError(f"Label mutation {old}->{new} changes record size.")
                out[label_pos : label_pos + length] = raw
            pos = marker_pos + 1
    return bytes(out)


def build_object_chunk(config: FamilyConfig, steps: tuple[GateStep, ...]) -> tuple[bytes, list[dict[str, object]]]:
    records: list[bytes] = []
    topology: list[dict[str, object]] = []
    for index, step in enumerate(steps, start=1):
        donor_labels = {
            f"A{GATE_LETTERS.index(step.gate_letter)}": step.left,
            f"B{GATE_LETTERS.index(step.gate_letter)}": step.right,
            f"Y{GATE_LETTERS.index(step.gate_letter)}": step.output,
        }
        record = patch_terminal_labels(gate_record(config, step.gate_letter), donor_labels)
        records.append(record)
        topology.append(
            {
                "object_id": index,
                "package_ref": "U1",
                "subpart_ref": f"U1:{step.gate_letter}",
                "gate_letter": step.gate_letter,
                "left_net": step.left,
                "right_net": step.right,
                "output_net": step.output,
                "semantic_note": step.semantic_note,
                "physical_pins": {
                    "left": GATE_PINS[step.gate_letter]["pins"][0][1],
                    "right": GATE_PINS[step.gate_letter]["pins"][1][1],
                    "output": GATE_PINS[step.gate_letter]["pins"][2][1],
                },
            }
        )
    return b"\x00" + b"".join(records) + b"\xff", topology


def build_cdb(config: FamilyConfig, steps: tuple[GateStep, ...]) -> bytes:
    out = bytearray()
    out += _u32(7)
    out += _u32(1) + _u32(1) + _u32(0) + _enc_str("ROOT") + b"\x00" + _u32(0) + _u32(1) + _u32(1)
    out += _u32(2)
    out += _u32(1) + _u32(3) + _u32(1) + _enc_str("") + _u32(10) + _u32(0)
    out += _u32(2) + _u32(2) + _u32(0) + _enc_str("Master Sheet") + _u32(10) + _u32(0)

    out += _u32(len(steps))
    for object_id, step in enumerate(steps, start=1):
        gate_info = GATE_PINS[step.gate_letter]
        out += _u32(object_id) + _u32(1) + _u32(0) + _u32(object_id)
        out += _enc_str(f"U1:{step.gate_letter}") + _u32(3)
        for logical, physical in gate_info["pins"]:
            out += _enc_str(logical) + _enc_str(physical)
        out += _u32(0) + _u32(1) + _u32(gate_info["index"] - 1)

    out += _u32(1) + _u32(1) + b"\x00" + _enc_str("") + _u32(1)
    out += _u32(1)
    out += _u32(1) + _u32(1) + _u32(0) + _u32(0) + _u32(0)
    out += _enc_str("U1") + _enc_str(config.device) + _enc_str(config.device) + _enc_str("DIL14")
    out += _enc_text(config.prop_text)
    out += _u32(0)
    return bytes(out)


def static_issues(output: Path, config: FamilyConfig, steps: tuple[GateStep, ...], object_chunk: bytes) -> list[str]:
    issues: list[str] = []
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    if _extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from generated chunk")
    if object_chunk.count(config.device.encode("ascii")) != 3 * len(steps):
        issues.append(f"{config.device} marker count does not match gate count")
    if object_chunk.count(config.function_marker.encode("ascii")) != len(steps):
        issues.append(f"{config.function_marker} marker count does not match gate count")
    if object_chunk.count(b"$TERINPUT") != 2 * len(steps):
        issues.append("$TERINPUT count does not match two inputs per gate")
    if object_chunk.count(b"$TEROUTPUT") != len(steps):
        issues.append("$TEROUTPUT count does not match one output per gate")
    if object_chunk.count(b"COMPONENT ID") != len(steps):
        issues.append("COMPONENT ID count does not match gate count")
    for marker in (b"$TERBIDIR", b"$TERPOWER", b"$TERGROUND", b"VSOURCE", b"CSOURCE", b"VSINE", b"LOGICSTATE", b"LOGICPROBE"):
        if object_chunk.count(marker):
            issues.append(f"unexpected marker in generated pure IC logic case: {marker.decode('ascii')}")
    for step in steps:
        if cdb.count(f"U1:{step.gate_letter}".encode("ascii")) != 1:
            issues.append(f"CDB missing subpart U1:{step.gate_letter}")
    return issues


def write_case(case_id: str, config: FamilyConfig, steps: tuple[GateStep, ...]) -> dict[str, object]:
    object_chunk, topology = build_object_chunk(config, steps)
    cdb = build_cdb(config, steps)
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    base_dsn = read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = read_internal_file(config.donor, "ROOT.DSN")
    dsn, pointers = build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)

    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    (case_dir / "logic_plan.json").write_text(
        json.dumps(
            {
                "device": config.device,
                "function_marker": config.function_marker,
                "record_shape": config.record_shape,
                "description": config.description,
                "gate_count": len(steps),
                "package_count": 1,
                "steps": [step.__dict__ for step in steps],
                "gate_topology": topology,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    manifest = {
        "case_id": case_id,
        "description": config.description,
        "method": "generated_object_chunk_from_accepted_all4_donor_gate_slices",
        "device": config.device,
        "function_marker": config.function_marker,
        "record_shape": config.record_shape,
        "terminal_policy": "IC signal pins are $TERINPUT/$TEROUTPUT only; no passive endpoints in this generated logic pack.",
        "static_validation_issues": static_issues(output, config, steps, object_chunk),
        "section_pointers": pointers,
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
    cases = [
        write_case("T01_74HC00_GENERATED_NAND3", CONFIGS["74hc00"], STEPS["74hc00"]),
        write_case("T02_74HC02_GENERATED_NOR3", CONFIGS["74hc02"], STEPS["74hc02"]),
        write_case("T03_74HC86_GENERATED_XOR4", CONFIGS["74hc86"], STEPS["74hc86"]),
        write_case("T04_74HC266_GENERATED_XNOR_CHAIN", CONFIGS["74hc266"], STEPS["74hc266"]),
    ]
    summary = {
        "batch": "IC_REMAINING_GENERATED_LOGIC_V1_TEMP_2026_06_08",
        "purpose": "First generated-object logic pack after remaining combinational donor acceptance.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "test_order": [case["case_id"] for case in cases],
        "cases": cases,
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": len(cases)}, indent=2))


if __name__ == "__main__":
    main()
