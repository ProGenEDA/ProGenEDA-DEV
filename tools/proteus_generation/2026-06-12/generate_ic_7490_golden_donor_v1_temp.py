"""Generate 7490 mixed circuits from the 2026-06-12 golden all-in-one donor.

This pack deliberately avoids the rejected cross-donor composition path.
Each output is built from a single Proteus-created donor that already contains:

- two 7490 native ICs with bidirectional pin terminals,
- all six supported binary combinational gate families,
- a 21-component R/C/L network,
- the matching ROOT.CDB and ROOT.DSN device metadata.

Only terminal labels are changed. Native 7490 labels are resized through the
known donor-native bider path; directional combinational and passive labels are
kept at their original two-character size and patched in place.
"""

from __future__ import annotations

import hashlib
import json
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

REPO = Path(__file__).resolve().parents[3]
DONOR = REPO / (
    "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal/7490/"
    "2_7490_withallcombunationaland21RLC.pdsprj"
)
OUT_ROOT = REPO / "experiments" / "ic_7490_golden_donor_v1_temp_2026_06_12"
ARCHIVE = REPO / "experiments" / "IC_7490_GOLDEN_DONOR_V1_TEMP_2026_06_12.zip"

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
    "xor": {"inputs": range(0, 8), "outputs": range(0, 4), "marker": "74HC86"},
    "or": {"inputs": range(8, 16), "outputs": range(4, 8), "marker": "74HC32"},
    "xnor": {"inputs": range(16, 24), "outputs": range(8, 12), "marker": "74HC266"},
    "and": {"inputs": range(24, 32), "outputs": range(12, 16), "marker": "74HC08"},
    "nor": {"inputs": range(32, 40), "outputs": range(16, 20), "marker": "74HC02"},
    "nand": {"inputs": range(40, 48), "outputs": range(20, 24), "marker": "74HC00"},
}

PIN_NAMES = ("CKA", "CKB", "R01", "R02", "R91", "R92", "Q0", "Q1", "Q2", "Q3")


@dataclass(frozen=True)
class OrdinaryTerminal:
    marker: str
    index: int
    marker_pos: int
    start: int
    length_pos: int
    label_pos: int
    length: int
    label: str
    x: int
    y: int

    def key(self) -> tuple[str, int]:
        return (self.marker, self.index)

    def as_dict(self) -> dict[str, object]:
        return {
            "marker": self.marker,
            "index": self.index,
            "marker_pos": self.marker_pos,
            "start": self.start,
            "label": self.label,
            "length": self.length,
            "x": self.x,
            "y": self.y,
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def ordinary_terminal_events(chunk: bytes) -> list[OrdinaryTerminal]:
    events: list[OrdinaryTerminal] = []
    for marker, output_terminal in ((b"$TERINPUT", False), (b"$TEROUTPUT", True), (b"$TERPOWER", False), (b"$TERGROUND", True)):
        pos = 0
        index = 0
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
                    marker_pos=marker_pos,
                    start=start,
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


def two_char_tokens() -> list[str]:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return [a + b for a in alphabet for b in alphabet]


def base_gate_labels() -> tuple[list[str], list[str]]:
    tokens = [token for token in two_char_tokens() if token not in {"G0", "V0"}]
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


def bider_map_for_two_7490(
    *,
    u1: dict[str, str],
    u2: dict[str, str],
) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for offset, nets in ((0, u1), (10, u2)):
        for pin_index, pin in enumerate(PIN_NAMES):
            value = nets.get(pin, "G0")
            if len(value.encode("ascii")) != 2:
                raise ValueError(f"7490 net {pin}={value!r} must be two ASCII characters.")
            mapping[offset + pin_index] = value
    return mapping


def ordinary_map(gate_inputs: list[str], gate_outputs: list[str], rlc_updates: dict[tuple[str, int], str] | None = None) -> dict[tuple[str, int], str]:
    mapping: dict[tuple[str, int], str] = {}
    for index, label in enumerate(gate_inputs):
        mapping[("$TERINPUT", index)] = label
    for index, label in enumerate(gate_outputs):
        mapping[("$TEROUTPUT", index)] = label
    for key, label in (rlc_updates or {}).items():
        mapping[key] = label
    for key, value in mapping.items():
        if len(value.encode("ascii")) != 2:
            raise ValueError(f"Terminal {key} label {value!r} must stay two ASCII characters.")
    return mapping


def patch_ordinary_labels(chunk: bytes, replacements: dict[tuple[str, int], str]) -> tuple[bytes, list[dict[str, object]]]:
    out = bytearray(chunk)
    mutations: list[dict[str, object]] = []
    for event in ordinary_terminal_events(chunk):
        new = replacements.get(event.key())
        if new is None:
            continue
        raw = new.encode("ascii")
        if len(raw) != event.length:
            raise ValueError(f"{event.key()} {event.label!r}->{new!r} changes record size.")
        old = chunk[event.label_pos : event.label_pos + event.length].decode("ascii", errors="replace")
        out[event.label_pos : event.label_pos + event.length] = raw
        mutations.append({"marker": event.marker, "index": event.index, "old": old, "new": new})
    return bytes(out), mutations


def validate_new_labels(chunk: bytes, labels: list[str]) -> list[str]:
    issues: list[str] = []
    for label in labels:
        if label.encode("ascii") not in chunk:
            issues.append(f"label {label!r} missing from patched object chunk")
    return issues


def count_duplicate_terminal_labels(chunk: bytes) -> dict[str, int]:
    labels: list[str] = [event.label for event in ordinary_terminal_events(chunk)]
    labels.extend(event.label for event in bidir_events(chunk))
    counts = {label: labels.count(label) for label in sorted(set(labels))}
    return {label: count for label, count in counts.items() if count > 1}


def build_case(
    *,
    case_id: str,
    title: str,
    description: str,
    u1: dict[str, str],
    u2: dict[str, str],
    configure,
    rlc_updates: dict[tuple[str, int], str] | None = None,
) -> dict[str, object]:
    gate_inputs, gate_outputs = base_gate_labels()
    configure(gate_inputs, gate_outputs)
    return {
        "case_id": case_id,
        "title": title,
        "description": description,
        "bider_replacements": bider_map_for_two_7490(u1=u1, u2=u2),
        "ordinary_replacements": ordinary_map(gate_inputs, gate_outputs, rlc_updates),
    }


def counter_u1(*, clk: str = "CK", reset: str = "G0") -> dict[str, str]:
    return {
        "CKA": clk,
        "CKB": "QA",
        "R01": reset,
        "R02": reset,
        "R91": "G0",
        "R92": "G0",
        "Q0": "QA",
        "Q1": "QB",
        "Q2": "QC",
        "Q3": "QD",
    }


def counter_u2(*, clk: str = "QD", reset: str = "G0") -> dict[str, str]:
    return {
        "CKA": clk,
        "CKB": "RA",
        "R01": reset,
        "R02": reset,
        "R91": "G0",
        "R92": "G0",
        "Q0": "RA",
        "Q1": "RB",
        "Q2": "RC",
        "Q3": "RD",
    }


CASES = [
    build_case(
        case_id="T01_7490_MOD6_DECODE_FULL_GATE_RLC",
        title="7490 modulo-6 decode with all gate families and 21RLC monitor",
        description=(
            "U1 is a 7490 decade counter. 74HC08 decodes Q1/Q2 into reset, "
            "then XOR/OR/XNOR/NOR/NAND stages derive monitor/control nets that feed the existing 21RLC network."
        ),
        u1=counter_u1(reset="RS"),
        u2=counter_u2(clk="QD", reset="RS"),
        configure=lambda gi, go: (
            set_gate(gi, go, "and", 0, "QB", "QC", "RS"),
            set_gate(gi, go, "xor", 0, "QA", "RB", "X1"),
            set_gate(gi, go, "or", 0, "QD", "RD", "O1"),
            set_gate(gi, go, "xnor", 0, "X1", "O1", "E1"),
            set_gate(gi, go, "nor", 0, "RS", "E1", "N1"),
            set_gate(gi, go, "nand", 0, "N1", "QC", "A1"),
            set_gate(gi, go, "and", 1, "RA", "RB", "D1"),
            set_gate(gi, go, "xor", 1, "RC", "RD", "A2"),
        ),
        rlc_updates={
            ("$TERINPUT", 50): "A1",
            ("$TERINPUT", 52): "D1",
            ("$TERINPUT", 59): "E1",
            ("$TEROUTPUT", 31): "M0",
            ("$TERGROUND", 0): "G0",
        },
    ),
    build_case(
        case_id="T02_DUAL_7490_BCD_COMPARE_RLC_LOADS",
        title="Dual 7490 BCD compare and equality output with RLC loads",
        description=(
            "Two cascaded 7490 counters expose BCD taps. XOR/XNOR gates compare selected bits; "
            "AND/NAND/NOR/OR combine the result into filtered RLC monitor nets."
        ),
        u1=counter_u1(),
        u2=counter_u2(clk="QD"),
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "QA", "RA", "X1"),
            set_gate(gi, go, "xor", 1, "QB", "RB", "X2"),
            set_gate(gi, go, "or", 0, "X1", "X2", "O1"),
            set_gate(gi, go, "nor", 0, "O1", "G0", "EQ"),
            set_gate(gi, go, "xnor", 0, "QC", "RC", "E1"),
            set_gate(gi, go, "and", 0, "EQ", "E1", "A4"),
            set_gate(gi, go, "nand", 0, "A4", "RD", "B4"),
            set_gate(gi, go, "or", 1, "B4", "QD", "A5"),
        ),
        rlc_updates={
            ("$TERINPUT", 55): "A4",
            ("$TERINPUT", 56): "B4",
            ("$TERINPUT", 58): "A5",
            ("$TEROUTPUT", 34): "A4",
            ("$TEROUTPUT", 36): "A5",
        },
    ),
    build_case(
        case_id="T03_RLC_CONDITIONED_CLOCK_AND_GATED_COUNTER",
        title="RLC-conditioned clock with combinational gate enable for 7490 pair",
        description=(
            "The donor 21RLC chain provides a conditioned clock/control node. Logic gates combine it with 7490 taps "
            "to create reset and enable-like signals for a two-counter block."
        ),
        u1=counter_u1(clk="F1", reset="R1"),
        u2=counter_u2(clk="QD", reset="R1"),
        configure=lambda gi, go: (
            set_gate(gi, go, "and", 0, "QA", "QB", "A1"),
            set_gate(gi, go, "or", 0, "A1", "QC", "O1"),
            set_gate(gi, go, "nand", 0, "O1", "QD", "R1"),
            set_gate(gi, go, "xor", 0, "RA", "RB", "F1"),
            set_gate(gi, go, "xnor", 0, "RC", "RD", "E2"),
            set_gate(gi, go, "nor", 0, "E2", "R1", "F2"),
            set_gate(gi, go, "and", 1, "F1", "F2", "A8"),
            set_gate(gi, go, "nand", 1, "A8", "G0", "A9"),
        ),
        rlc_updates={
            ("$TERINPUT", 65): "F1",
            ("$TERINPUT", 68): "F2",
            ("$TEROUTPUT", 42): "A8",
            ("$TEROUTPUT", 44): "A9",
        },
    ),
    build_case(
        case_id="T04_WINDOWED_RESET_AND_PARALLEL_RLC_TAPS",
        title="Windowed counter reset with multiple RLC measurement taps",
        description=(
            "Selected U1 and U2 counter bits are decoded through all gate families. Several outputs are tied to "
            "different 21RLC tap names so the passive network has multiple measurement points."
        ),
        u1=counter_u1(reset="R2"),
        u2=counter_u2(clk="QD", reset="R2"),
        configure=lambda gi, go: (
            set_gate(gi, go, "xor", 0, "QA", "QC", "X1"),
            set_gate(gi, go, "and", 0, "QB", "QD", "A1"),
            set_gate(gi, go, "or", 0, "X1", "A1", "D1"),
            set_gate(gi, go, "nor", 0, "D1", "RA", "R2"),
            set_gate(gi, go, "xnor", 0, "RB", "RC", "E1"),
            set_gate(gi, go, "nand", 0, "E1", "RD", "B7"),
            set_gate(gi, go, "and", 1, "R2", "E1", "F1"),
            set_gate(gi, go, "or", 1, "F1", "B7", "F2"),
        ),
        rlc_updates={
            ("$TERINPUT", 48): "A1",
            ("$TERINPUT", 52): "D1",
            ("$TERINPUT", 59): "E1",
            ("$TERINPUT", 63): "B7",
            ("$TERINPUT", 65): "F1",
            ("$TERINPUT", 68): "F2",
        },
    ),
    build_case(
        case_id="T05_CASCADED_7490_LOGIC_STATE_DECODER",
        title="Cascaded 7490 state decoder using every binary gate family",
        description=(
            "A two-stage 7490 chain generates BCD-like state taps. All six binary gate families decode different "
            "state relationships and drive existing RLC monitor branches."
        ),
        u1=counter_u1(),
        u2=counter_u2(clk="QD"),
        configure=lambda gi, go: (
            set_gate(gi, go, "and", 0, "QA", "QB", "A1"),
            set_gate(gi, go, "and", 1, "QC", "QD", "A2"),
            set_gate(gi, go, "or", 0, "A1", "A2", "D1"),
            set_gate(gi, go, "xor", 0, "RA", "RB", "D2"),
            set_gate(gi, go, "xnor", 0, "RC", "RD", "E1"),
            set_gate(gi, go, "nor", 0, "D1", "D2", "M0"),
            set_gate(gi, go, "nand", 0, "M0", "E1", "F1"),
            set_gate(gi, go, "or", 1, "F1", "A2", "A9"),
        ),
        rlc_updates={
            ("$TERINPUT", 48): "A1",
            ("$TERINPUT", 51): "A2",
            ("$TERINPUT", 52): "D1",
            ("$TERINPUT", 53): "D2",
            ("$TERINPUT", 64): "M0",
            ("$TERINPUT", 65): "F1",
            ("$TEROUTPUT", 44): "A9",
        },
    ),
]


def build_output(case: dict[str, object], case_dir: Path) -> dict[str, object]:
    fixture = FixtureRegistry.load().get("e001_empty")
    donor_project = read_internal_file(DONOR, "PROJECT.XML")
    donor_dsn = read_internal_file(DONOR, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR, "ROOT.CDB")
    donor_chunk = _extract_object_chunk(donor_dsn)

    object_chunk, ordinary_mutations = patch_ordinary_labels(
        donor_chunk,
        case["ordinary_replacements"],  # type: ignore[arg-type]
    )
    object_chunk, bider_mutations = patch_bidir_labels(
        object_chunk,
        case["bider_replacements"],  # type: ignore[arg-type]
    )

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
            "SCRIPTS/PWRRAILS.DAT": read_internal_file(DONOR, "SCRIPTS/PWRRAILS.DAT"),
        },
    )

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_cdb = read_internal_file(output, "ROOT.CDB")
    final_chunk = _extract_object_chunk(final_dsn)
    labels_to_check = [m["new"] for m in ordinary_mutations]
    labels_to_check.extend(m["new"] for m in bider_mutations)
    static_issues = validate_new_labels(final_chunk, labels_to_check)
    for marker in MARKERS:
        if marker not in final_chunk and marker not in final_cdb:
            static_issues.append(f"expected marker {marker.decode('ascii', errors='replace')} absent")
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        static_issues.append("missing required pdsprj internal member")

    ordered_terminals = [
        event.as_dict()
        for event in ordinary_terminal_events(final_chunk)
    ] + [
        event.as_dict() | {"marker": "$TERBIDIR", "length": len(event.label)}
        for event in bidir_events(final_chunk)
    ]
    ordered_terminals = sorted(ordered_terminals, key=lambda item: int(item["start"]))

    manifest = {
        "case_id": case["case_id"],
        "title": case["title"],
        "description": case["description"],
        "status": "temporary_pending_user_proteus_testing",
        "method": "golden_all_in_one_donor_terminal_label_mutation_only",
        "donor": str(DONOR.relative_to(REPO)),
        "source_policy": {
            "7490_native_pins": "$TERBIDIR labels resized through accepted native helper",
            "combinational_gates": "$TERINPUT/$TEROUTPUT labels patched in place, two characters only",
            "passive_network": "donor 21RLC records preserved; selected labels tied to logic nets",
            "records": "no IC, passive, CDB, or device-section packets are synthesized or deleted",
        },
        "section_pointers": pointers,
        "mutations": {
            "ordinary": ordinary_mutations,
            "bider": bider_mutations,
        },
        "marker_counts": marker_counts(final_chunk, [m.decode("ascii", errors="replace") for m in MARKERS]),
        "cdb_marker_counts": marker_counts(final_cdb, [m.decode("ascii", errors="replace") for m in MARKERS]),
        "duplicate_terminal_labels_intentional": count_duplicate_terminal_labels(final_chunk),
        "static_validation_issues": static_issues,
        "hashes": {
            "donor_project": sha256_bytes(donor_project),
            "project": sha256_file(output),
            "ROOT.DSN": sha256_bytes(final_dsn),
            "ROOT.CDB": sha256_bytes(final_cdb),
            "object_chunk": sha256_bytes(final_chunk),
        },
    }
    (case_dir / "ROOT.DSN.bin").write_bytes(final_dsn)
    (case_dir / "ROOT.CDB.bin").write_bytes(final_cdb)
    (case_dir / "object_chunk.bin").write_bytes(final_chunk)
    (case_dir / "terminal_plan.json").write_text(json.dumps(ordered_terminals, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def write_inventory() -> dict[str, object]:
    root = REPO / "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal"
    rows: list[dict[str, object]] = []
    for donor in sorted(root.rglob("*.pdsprj")):
        try:
            dsn = read_internal_file(donor, "ROOT.DSN")
            cdb = read_internal_file(donor, "ROOT.CDB")
            chunk = _extract_object_chunk(dsn)
            rows.append(
                {
                    "path": str(donor.relative_to(REPO)),
                    "size": donor.stat().st_size,
                    "sha256": sha256_file(donor),
                    "object_chunk_size": len(chunk),
                    "device_section_size": len(device_section(dsn)),
                    "bidir_count": len(bidir_events(chunk)),
                    "terminal_counts": {
                        "$TERBIDIR": chunk.count(b"$TERBIDIR"),
                        "$TERINPUT": chunk.count(b"$TERINPUT"),
                        "$TEROUTPUT": chunk.count(b"$TEROUTPUT"),
                        "$TERPOWER": chunk.count(b"$TERPOWER"),
                        "$TERGROUND": chunk.count(b"$TERGROUND"),
                    },
                    "marker_counts": {marker.decode("ascii", errors="replace"): chunk.count(marker) + cdb.count(marker) for marker in MARKERS},
                }
            )
        except Exception as exc:  # noqa: BLE001 - inventory should preserve bad donor diagnostics.
            rows.append({"path": str(donor.relative_to(REPO)), "error": repr(exc)})
    inventory = {
        "schema": "proteus-donor-inventory/v0.1",
        "source": "C:/Users/tahab/Downloads/ICcombinationfinal",
        "repo_copy": "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal",
        "donor_count": len(rows),
        "donors": rows,
    }
    path = REPO / "proteus_ic/donors/manual_downloads_20260612/ICcombinationfinal_inventory.json"
    path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return inventory


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
    if not DONOR.exists():
        raise SystemExit(f"Missing golden donor: {DONOR}")
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    inventory = write_inventory()
    manifests = []
    blocked = []
    for case in CASES:
        case_dir = OUT_ROOT / str(case["case_id"])
        case_dir.mkdir(parents=True)
        try:
            manifests.append(build_output(case, case_dir))
        except Exception as exc:  # noqa: BLE001 - temporary pack must report every blocked case.
            blocked.append({"case_id": case["case_id"], "error": repr(exc)})
    summary = {
        "pack": "IC_7490_GOLDEN_DONOR_V1_TEMP_2026_06_12",
        "donor": str(DONOR.relative_to(REPO)),
        "method": "single_golden_donor_complete_packet_terminal_label_mutation",
        "generated_case_count": len(manifests),
        "blocked": blocked,
        "static_issue_cases": {m["case_id"]: m["static_validation_issues"] for m in manifests if m["static_validation_issues"]},
        "cases": [m["case_id"] for m in manifests],
        "inventory_donor_count": inventory["donor_count"],
        "archive": str(ARCHIVE.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_archive()
    summary["archive_sha256"] = sha256_file(ARCHIVE)
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
