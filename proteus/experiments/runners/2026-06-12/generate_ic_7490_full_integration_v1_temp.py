"""Generate stronger 7490 integration circuits with combinational logic and RCL.

This pack replaces the earlier weak 7490 "real circuit" probe. It keeps the
accepted native 4x7490 donor path, then adds fresh locked combinational gate
records and multiple R/C/L passive records. The point is to test the new 7490
family against already accepted components in useful circuits, not just beside
one resistor/capacitor/inductor load.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import CdbPropertyRow, build_cdb_from_rows, package_ref, parse_cdb
from proteusgen.ic_native import NativeRegistry, _components_from_payload, _connection_map, _labels_for_events, _single_terminal_counts, bidir_events, device_section, patch_bidir_labels
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version


REPO = Path(__file__).resolve().parents[4]
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_7490_full_integration_v1_temp_2026_06_12"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "IC_7490_FULL_INTEGRATION_V1_TEMP_2026_06_12.zip"
DONOR_7490 = REPO / "proteus" / "active" / "evidence" / "donors" / "manual_downloads_20260611" / "SQU" / "4_7490.pdsprj"
PAIRWISE_CDB_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_cross_donor_v2_metadata_temp.py"

GATE_X = 11_430_000
GATE_Y = 2_540_000
GATE_X_STEP = 4_572_000
GATE_Y_STEP = -1_778_000


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ic = _load_module("ic_combinational_for_7490_full_integration", REPO / "proteus" / "active" / "src" / "proteusgen" / "ic_combinational.py")
cdb_v2 = _load_module("mixed_cdb_v2_for_7490_full_integration", PAIRWISE_CDB_SCRIPT)


@dataclass(frozen=True)
class FullIntegrationCase:
    case_id: str
    title: str
    description: str
    counters: tuple[dict[str, str], ...]
    gates: tuple[ic.GateSpec, ...]
    passives: tuple[ic.PassiveSpec, ...]


def counter(clk: str, ckb: str, *, rst_a: str = "G0", rst_b: str = "G0", prefix: str) -> dict[str, str]:
    return {
        "CKA": clk,
        "CKB": ckb,
        "R01": rst_a,
        "R02": rst_b,
        "R91": "G0",
        "R92": "G0",
        "Q0": f"{prefix}0",
        "Q1": f"{prefix}1",
        "Q2": f"{prefix}2",
        "Q3": f"{prefix}3",
    }


def components_for_counters(connections: tuple[dict[str, str], ...]) -> list[dict[str, object]]:
    return [
        {"ref": f"U{index}", "part": "74HC90", "connections": conn}
        for index, conn in enumerate(connections, start=1)
    ]


def donor_7490_chunk(connections: tuple[dict[str, str], ...]) -> tuple[bytes, list[dict[str, object]], dict[str, int]]:
    registry = NativeRegistry.load()
    donor_dsn = read_internal_file(DONOR_7490, "ROOT.DSN")
    donor_chunk = _extract_object_chunk(donor_dsn)
    components = _components_from_payload({"components": components_for_counters(connections)}, registry)
    connection_map = _connection_map({"components": components_for_counters(connections)}, components)
    counts = _single_terminal_counts(registry, [str(component["part"]) for component in components])
    replacements, terminal_plan = _labels_for_events(
        donor_chunk=donor_chunk,
        components=components,
        component_single_counts=counts,
        connection_map=connection_map,
    )
    chunk, mutations = patch_bidir_labels(donor_chunk, replacements)
    for event in bidir_events(chunk):
        if len(event.label) > 4:
            raise ValueError(f"7490 integration labels should stay compact, got {event.label!r}")
    return chunk, terminal_plan + mutations, counts


def _gate_position(index: int) -> tuple[int, int]:
    col = index // 4
    row = index % 4
    return GATE_X + col * GATE_X_STEP, GATE_Y + row * GATE_Y_STEP


def generated_logic_and_passive_records(
    gates: tuple[ic.GateSpec, ...],
    passives: tuple[ic.PassiveSpec, ...],
    *,
    first_object_id: int,
    first_package_number: int,
) -> tuple[bytes, bytes, list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[str]]:
    records: list[bytes] = []
    topology: list[dict[str, object]] = []
    package_rows: list[dict[str, object]] = []
    for gate_index, gate in enumerate(gates):
        object_id = first_object_id + gate_index
        package_number = first_package_number + gate_index
        if package_number > 9:
            raise ValueError("This temporary pack keeps generated combinational packages in U1..U9.")
        package_ref = f"U{package_number}"
        dx, dy = _gate_position(gate_index)
        config = ic.FAMILIES[gate.family]
        if config.shape in {"hc08_script", "hc32_script"}:
            record, row = ic._script_gate_record(
                config,
                gate,
                package_ref=package_ref,
                package_number=package_number,
                object_id=object_id,
                dx=dx,
                dy=dy,
            )
        else:
            record, row = ic._generic_gate_record(
                config,
                gate,
                package_ref=package_ref,
                object_id=object_id,
                dx=dx,
                dy=dy,
            )
        records.append(record)
        topology.append(row)
        package_rows.append(
            {
                "family": gate.family,
                "device": config.device,
                "package_ref": package_ref,
                "package_number": package_number,
            }
        )

    first_passive_id = first_object_id + len(gates)
    passive_chunk, passive_specs, passive_topology, replacements, passive_issues = ic.build_passive_chunk(
        ic.CircuitCase("TMP", "tmp", "", "", (), passives),
        first_passive_id,
    )
    passive_payload = passive_chunk[1:-1] if passive_chunk else b""
    generated_payload = b"".join(records) + passive_payload
    generated_cdb = ic.build_cdb(topology, package_rows, passive_specs)
    return generated_payload, generated_cdb, topology, package_rows, passive_topology, passive_issues


def combine_cdbs(donor_cdb: bytes, generated_cdb: bytes) -> bytes:
    donor = parse_cdb(donor_cdb)
    generated = parse_cdb(generated_cdb)
    donor_props = donor.property_by_ref()
    generated_props = generated.property_by_ref()
    rows = []
    donor_last_property_ref = donor.property_rows[-1].ref
    for pin in donor.pin_rows:
        prop_ref = package_ref(pin.ref)
        prop = donor_props[prop_ref]
        if prop.ref == donor_last_property_ref:
            prop = CdbPropertyRow(ref=prop.ref, data=prop.data[:-4])
        rows.append((pin.ref, pin, prop))
    for pin in generated.pin_rows:
        prop_ref = package_ref(pin.ref)
        rows.append((pin.ref, pin, generated_props[prop_ref]))
    ids = [int.from_bytes(pin.data[:4], "little") for _ref, pin, _prop in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate CDB pin object IDs after combine: {ids}")
    prop_ids = [int.from_bytes(prop.data[:4], "little") for _ref, _pin, prop in rows]
    if len(prop_ids) != len(set(prop_ids)):
        raise ValueError(f"Duplicate CDB property object IDs after combine: {prop_ids}")
    return build_cdb_from_rows(donor, rows)


def build_project(case: FullIntegrationCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    donor_dsn = read_internal_file(DONOR_7490, "ROOT.DSN")
    donor_cdb = read_internal_file(DONOR_7490, "ROOT.CDB")
    donor_chunk, terminal_plan, terminal_counts = donor_7490_chunk(case.counters)
    donor_parsed = parse_cdb(donor_cdb)
    max_id = max(int.from_bytes(row.data[:4], "little") for row in (*donor_parsed.pin_rows, *donor_parsed.property_rows))

    generated_payload, generated_cdb, gate_topology, package_rows, passive_topology, passive_issues = generated_logic_and_passive_records(
        case.gates,
        case.passives,
        first_object_id=max_id + 1,
        first_package_number=5,
    )
    object_chunk = b"\x00" + donor_chunk[1:-1] + generated_payload + b"\xff"
    cdb = combine_cdbs(donor_cdb, generated_cdb)

    fixture = FixtureRegistry.load().get("e001_empty")
    sections = [
        {
            "donor_key": "native_7490_4x",
            "donor": str(DONOR_7490.relative_to(REPO)),
            "section": bytearray(device_section(donor_dsn)),
            "old_tail_pointer": None,
            "size": len(device_section(donor_dsn)),
        },
        {
            "donor_key": "accepted_combinational_and_passive",
            "donor": str(ic.COMBINED_DEVICE_DONOR.relative_to(REPO)),
            "section": bytearray(ic._combined_device_section()),
            "old_tail_pointer": None,
            "size": len(ic._combined_device_section()),
        },
    ]
    dsn, pointers = cdb_v2.build_dsn_with_multi_device_sections(
        read_internal_file(fixture.path, "ROOT.DSN"),
        donor_dsn,
        object_chunk,
        sections,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    write_project_from_parts(
        fixture.path,
        output,
        {
            "PROJECT.XML": patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_cdb = read_internal_file(output, "ROOT.CDB")
    final_chunk = _extract_object_chunk(final_dsn)
    issues = static_issues(output, case, final_chunk, final_cdb, passive_issues)
    layout_plan = {
        "layout_version": "native-plus-combinational-compact/v0.1",
        "strategy": "7490_native_grid_plus_compact_logic_decode_and_grouped_passives",
        "7490_policy": "native 4x donor grid preserved; bidirectional pin labels compacted to semantic nets",
        "logic_policy": "fresh accepted combinational gate slices placed beside the counter bank",
        "passive_policy": "multiple R/C/L components grouped as reset, clock-conditioner, decode-load, and output-filter networks",
        "gate_positions": [
            {
                "package_ref": package_rows[index]["package_ref"],
                "family": gate.family,
                "role": ic.FAMILIES[gate.family].role,
                "x": _gate_position(index)[0],
                "y": _gate_position(index)[1],
            }
            for index, gate in enumerate(case.gates)
        ],
    }
    manifest = {
        "case_id": case.case_id,
        "title": case.title,
        "description": case.description,
        "method": "native_4x7490_donor_plus_fresh_locked_combinational_gate_slices_and_multi_rcl_passives",
        "status": "temporary_pending_user_proteus_testing",
        "donor": str(DONOR_7490.relative_to(REPO)),
        "counter_count": 4,
        "gate_count": len(case.gates),
        "gate_families": [gate.family for gate in case.gates],
        "passive_count": len(case.passives),
        "passives": [passive.__dict__ for passive in case.passives],
        "terminal_policy": {
            "7490": "$TERBIDIR donor-native physical pins",
            "combinational": "$TERINPUT/$TEROUTPUT directional IC pins",
            "RCL": "$TERBIDIR endpoints, with donor power/ground terminals for V0/G0",
        },
        "counter_terminal_single_counts": terminal_counts,
        "terminal_plan": terminal_plan,
        "logic_topology": gate_topology,
        "logic_package_rows": package_rows,
        "passive_topology": passive_topology,
        "layout": layout_plan,
        "section_pointers": pointers,
        "marker_counts": {
            marker: final_chunk.count(marker.encode("ascii"))
            for marker in ("7490", "74HC00", "74HC02", "74HC04", "74HC08", "74HC32", "74HC86", "74HC266", "RESISTOR", "CAPACITOR", "REALIND")
        },
        "static_validation_issues": issues,
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(final_dsn),
            "ROOT.CDB": _sha256_bytes(final_cdb),
            "object_chunk": _sha256_bytes(final_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "circuit_input.json").write_text(
        json.dumps(
            {
                "case_id": case.case_id,
                "title": case.title,
                "description": case.description,
                "counters": case.counters,
                "gates": [gate.__dict__ for gate in case.gates],
                "passives": [passive.__dict__ for passive in case.passives],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (case_dir / "ic_layout_plan.json").write_text(json.dumps(layout_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "object_chunk.bin").write_bytes(final_chunk)
    (case_dir / "ROOT.DSN.bin").write_bytes(final_dsn)
    (case_dir / "ROOT.CDB.bin").write_bytes(final_cdb)
    return manifest


def static_issues(output: Path, case: FullIntegrationCase, chunk: bytes, cdb: bytes, build_issues: list[str]) -> list[str]:
    issues = list(build_issues)
    info = inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required project member")
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"7490") < 4:
        issues.append("expected four 7490 markers")
    for family in sorted({gate.family for gate in case.gates}):
        marker = ic.FAMILIES[family].device.encode("ascii")
        if marker not in chunk and marker not in cdb:
            issues.append(f"missing combinational marker {marker.decode('ascii')}")
    if chunk.count(b"COMPONENT ID") != 4 + len(case.gates) + len(case.passives):
        issues.append("component count mismatch for 4 counters + gates + passives")
    passive_bidir_endpoints = sum(
        1
        for passive in case.passives
        for endpoint in (passive.left, passive.right)
        if endpoint not in {"V0", "G0"}
    )
    if chunk.count(b"$TERBIDIR") < 40 + passive_bidir_endpoints:
        issues.append("too few bidirectional terminals for 7490 pins plus passive endpoints")
    parsed = parse_cdb(cdb)
    pin_ids = [int.from_bytes(row.data[:4], "little") for row in parsed.pin_rows]
    prop_ids = [int.from_bytes(row.data[:4], "little") for row in parsed.property_rows]
    if len(pin_ids) != len(set(pin_ids)):
        issues.append(f"duplicate CDB pin IDs: {pin_ids}")
    if len(prop_ids) != len(set(prop_ids)):
        issues.append(f"duplicate CDB property IDs: {prop_ids}")
    return issues


CASES = (
    FullIntegrationCase(
        "T01_7490_BCD_DECODE_RESET_FILTER_BANK",
        "7490 BCD decode with AND/OR/NAND control and reset filtering",
        "U1 and U2 form a divide-by-100 counter. Q taps are decoded with AND/OR/NAND logic; the reset and output monitor use RC and LC filtering.",
        (
            counter("CK", "A0", prefix="A"),
            counter("A3", "B0", prefix="B"),
            counter("EN", "C0", rst_a="RS", rst_b="RS", prefix="C"),
            counter("B3", "D0", rst_a="RS", rst_b="RS", prefix="D"),
        ),
        (
            ic.GateSpec("74hc08", "A", "A1", "A2", "N1", "Decode count-6 style tap"),
            ic.GateSpec("74hc32", "A", "N1", "B3", "N2", "Combine decoded carry with upper decade"),
            ic.GateSpec("74hc00", "A", "N2", "EN", "RS", "Generate active reset window"),
            ic.GateSpec("74hc04", "A", "RS", "", "NR", "Inverted reset monitor"),
            ic.GateSpec("74hc86", "A", "A3", "B3", "XO", "Rate-change edge monitor"),
        ),
        (
            ic.PassiveSpec("R1", "R", "4k7", "CK", "CF"),
            ic.PassiveSpec("C1", "C", "100", "CF", "G0"),
            ic.PassiveSpec("R2", "R", "10k", "V0", "EN"),
            ic.PassiveSpec("R3", "R", "1k0", "RS", "G0"),
            ic.PassiveSpec("C2", "C", "1uF", "RS", "G0"),
            ic.PassiveSpec("L1", "L", "5mH", "XO", "LF"),
            ic.PassiveSpec("C3", "C", "1uF", "LF", "G0"),
            ic.PassiveSpec("R4", "R", "330", "NR", "Y0"),
        ),
    ),
    FullIntegrationCase(
        "T02_7490_DIGITAL_WINDOW_WITH_XNOR_NOR_LOADS",
        "7490 window detector using XOR/XNOR/NOR and heavy passive loading",
        "Two counter stages create coarse and fine timing taps. XOR/XNOR/NOR gates compare taps, while RCL branches provide clock shaping and analog monitor loads.",
        (
            counter("CK", "A0", prefix="A"),
            counter("A3", "B0", prefix="B"),
            counter("B3", "C0", prefix="C"),
            counter("CK2", "D0", prefix="D"),
        ),
        (
            ic.GateSpec("74hc86", "A", "A2", "B1", "X1", "Difference between low/high decade taps"),
            ic.GateSpec("74hc266", "A", "B2", "C2", "EQ", "Equality window"),
            ic.GateSpec("74hc02", "A", "X1", "EQ", "NW", "Window reject output"),
            ic.GateSpec("74hc08", "A", "EQ", "EN", "GO", "Enable-qualified equality"),
            ic.GateSpec("74hc32", "A", "GO", "D3", "Y0", "Final observable event"),
        ),
        (
            ic.PassiveSpec("R1", "R", "2k2", "CK", "C1"),
            ic.PassiveSpec("C1", "C", "220", "C1", "G0"),
            ic.PassiveSpec("R2", "R", "10k", "V0", "EN"),
            ic.PassiveSpec("R3", "R", "4k7", "X1", "G0"),
            ic.PassiveSpec("C2", "C", "1uF", "EQ", "G0"),
            ic.PassiveSpec("L1", "L", "5mH", "NW", "N2"),
            ic.PassiveSpec("C3", "C", "470", "N2", "G0"),
            ic.PassiveSpec("R4", "R", "330", "Y0", "LD"),
            ic.PassiveSpec("C4", "C", "100", "LD", "G0"),
        ),
    ),
    FullIntegrationCase(
        "T03_7490_MOD60_PULSE_STRETCHER",
        "Modulo-60 counter decode with pulse-stretcher passives",
        "A pair of 7490 stages is decoded as a seconds-style counter. NAND, AND, NOT, XOR, and XNOR gates generate reset and status nodes with multiple RC timing legs.",
        (
            counter("CK", "A0", rst_a="RS", rst_b="RS", prefix="A"),
            counter("A3", "B0", rst_a="RS", rst_b="RS", prefix="B"),
            counter("B3", "C0", rst_a="RS", rst_b="RS", prefix="C"),
            counter("CK2", "D0", prefix="D"),
        ),
        (
            ic.GateSpec("74hc08", "A", "A1", "A2", "S6", "Units digit equals six"),
            ic.GateSpec("74hc00", "A", "S6", "B2", "RS", "Modulo reset pulse"),
            ic.GateSpec("74hc04", "A", "RS", "", "OK", "Reset inverted for status"),
            ic.GateSpec("74hc86", "A", "B0", "C0", "XT", "Phase tap edge"),
            ic.GateSpec("74hc266", "A", "OK", "XT", "Y0", "Final equality status"),
        ),
        (
            ic.PassiveSpec("R1", "R", "10k", "V0", "CK"),
            ic.PassiveSpec("C1", "C", "100", "CK", "G0"),
            ic.PassiveSpec("R2", "R", "1k0", "RS", "PR"),
            ic.PassiveSpec("C2", "C", "2u2", "PR", "G0"),
            ic.PassiveSpec("R3", "R", "4k7", "OK", "G0"),
            ic.PassiveSpec("L1", "L", "5mH", "XT", "XF"),
            ic.PassiveSpec("C3", "C", "1uF", "XF", "G0"),
            ic.PassiveSpec("R4", "R", "330", "Y0", "LD"),
            ic.PassiveSpec("C4", "C", "100", "LD", "G0"),
            ic.PassiveSpec("L2", "L", "2mH", "LD", "OU"),
        ),
    ),
    FullIntegrationCase(
        "T04_7490_DEBOUNCED_CLOCK_AND_ALARM_DECODE",
        "Debounced clock input with alarm decode logic",
        "A debounced clock feeds four 7490 stages. OR/NOR/NAND/AND/NOT gates form a simple alarm compare and reset inhibit path, with multiple passive filters.",
        (
            counter("CB", "A0", prefix="A"),
            counter("A3", "B0", prefix="B"),
            counter("B3", "C0", prefix="C"),
            counter("C3", "D0", prefix="D"),
        ),
        (
            ic.GateSpec("74hc32", "A", "A3", "B3", "H1", "High-count coarse alarm"),
            ic.GateSpec("74hc02", "A", "A0", "B0", "L0", "Low-count inhibit"),
            ic.GateSpec("74hc00", "A", "H1", "L0", "AL", "Alarm decode"),
            ic.GateSpec("74hc08", "A", "AL", "EN", "Y0", "Enable-qualified alarm"),
            ic.GateSpec("74hc04", "A", "AL", "", "NA", "Alarm complement"),
        ),
        (
            ic.PassiveSpec("R1", "R", "22k", "CK", "CB"),
            ic.PassiveSpec("C1", "C", "470", "CB", "G0"),
            ic.PassiveSpec("R2", "R", "10k", "V0", "EN"),
            ic.PassiveSpec("C2", "C", "100", "EN", "G0"),
            ic.PassiveSpec("R3", "R", "1k0", "AL", "G0"),
            ic.PassiveSpec("C3", "C", "1uF", "AL", "G0"),
            ic.PassiveSpec("L1", "L", "5mH", "NA", "NF"),
            ic.PassiveSpec("R4", "R", "330", "Y0", "LD"),
            ic.PassiveSpec("C4", "C", "220", "LD", "G0"),
        ),
    ),
    FullIntegrationCase(
        "T05_7490_CASCADE_WITH_MULTI_FAMILY_STATUS_BUS",
        "7490 cascade with multi-family status bus and RCL output network",
        "This stress case runs a four-decade ripple chain and uses five different logic families to create status, error, and filtered output nodes.",
        (
            counter("CK", "A0", prefix="A"),
            counter("A3", "B0", prefix="B"),
            counter("B3", "C0", prefix="C"),
            counter("C3", "D0", prefix="D"),
        ),
        (
            ic.GateSpec("74hc08", "A", "A3", "B3", "D1", "Main carry detect"),
            ic.GateSpec("74hc32", "A", "C3", "D3", "D2", "Upper-stage active detect"),
            ic.GateSpec("74hc86", "A", "D1", "D2", "ER", "Mismatch/error flag"),
            ic.GateSpec("74hc02", "A", "ER", "G0", "NO", "Error clear/inhibit node"),
            ic.GateSpec("74hc00", "A", "NO", "EN", "Y0", "Final gated output"),
        ),
        (
            ic.PassiveSpec("R1", "R", "4k7", "CK", "CI"),
            ic.PassiveSpec("C1", "C", "100", "CI", "G0"),
            ic.PassiveSpec("R2", "R", "10k", "V0", "EN"),
            ic.PassiveSpec("R3", "R", "2k2", "D1", "G0"),
            ic.PassiveSpec("R4", "R", "2k2", "D2", "G0"),
            ic.PassiveSpec("C2", "C", "1uF", "ER", "G0"),
            ic.PassiveSpec("L1", "L", "5mH", "NO", "NF"),
            ic.PassiveSpec("C3", "C", "470", "NF", "G0"),
            ic.PassiveSpec("R5", "R", "330", "Y0", "OU"),
            ic.PassiveSpec("C4", "C", "100", "OU", "G0"),
            ic.PassiveSpec("L2", "L", "2mH", "OU", "MN"),
        ),
    ),
)


def write_archive() -> str:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 12, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE.read_bytes())


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    manifests = [build_project(case) for case in CASES]
    issue_cases = {
        manifest["case_id"]: manifest["static_validation_issues"]
        for manifest in manifests
        if manifest["static_validation_issues"]
    }
    summary = {
        "pack": "IC_7490_FULL_INTEGRATION_V1_TEMP_2026_06_12",
        "purpose": "Proper 7490 integration tests with combinational ICs and multi-component R/C/L networks.",
        "status": "temporary_pending_user_proteus_testing",
        "case_count": len(manifests),
        "cases": [manifest["case_id"] for manifest in manifests],
        "static_issue_cases": issue_cases,
        "coverage": {
            "native_ic": ["7490/74HC90"],
            "combinational_families_across_pack": sorted({family for manifest in manifests for family in manifest["gate_families"]}),
            "passive_min_count": min(manifest["passive_count"] for manifest in manifests),
            "passive_max_count": max(manifest["passive_count"] for manifest in manifests),
        },
        "archive": str(ARCHIVE),
    }
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
