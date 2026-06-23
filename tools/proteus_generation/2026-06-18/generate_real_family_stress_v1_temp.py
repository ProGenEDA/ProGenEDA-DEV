"""Scaled realistic mega component-family stress pack.

This replaces the single "everything at once" stress sheet with real circuit
families. It is a thin temp pack builder over the already accepted component
placement helpers: complete donor-native packets only, no generated
connectivity, no freehand CDB synthesis.

Rules:
- source-bearing cases use the source-capable mega donor;
- source-less cases use the no-source mega donor;
- 7-segment rows use the accepted V9/V11 display route with the D20 bridge;
- a donor-derived power/ground overlay is added after placement:
  $TERPOWER -> $TERBIDIR(V0), plus $TERGROUND(G0) beside $TERBIDIR(G0);
- VSINE is included only when a numeric count is specified in the case table;
- counts beyond donor inventory are clipped and recorded in the manifest.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.proteusgen.pdsprj import read_internal_file, write_project_from_parts
from src.proteusgen.resistor_v9 import _extract_object_chunk, build_dsn
from src.proteusgen import resistor_v9 as rv9
from src.proteusgen.bidirectional import ORIENTATION_BY_TERMINAL_ROLE
from src.proteusgen.templates import FixtureRegistry


HELPER_PATH = ROOT / "tools/proteus_generation/2026-06-16/generate_mega_bare_separation_v1_temp.py"
V9_PATH = ROOT / "tools/proteus_generation/2026-06-18/generate_bare_display_mega_acceptance_v9_temp.py"
V11_PATH = ROOT / "tools/proteus_generation/2026-06-18/generate_bare_display_4027_bridge_v11_temp.py"
BIDIR_PATH = ROOT / "tools/proteus_generation/2026-06-07/bidirectional_temp.py"
DONOR_DIR = ROOT / "proteus_ic/donors/main_mega_20260618"
SOURCE_DONOR = (
    DONOR_DIR
    / "15xsemimega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistorandsources.pdsprj"
)
NO_SOURCE_DONOR = (
    DONOR_DIR
    / "Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj"
)
OUT_DIR = ROOT / "experiments/real_family_stress_v2_scaled_temp_2026_06_18"
ZIP_OUT = ROOT / "experiments/REAL_FAMILY_STRESS_V2_SCALED_TEMP_2026_06_18.zip"
BIDIR_DONORS = ROOT / "experiments/bidirectional_v1_temp_2026_06_07/donors"

DISPLAY_FAMILIES = {"7SEGCOMA", "7SEGCOMK"}
SOURCE_FAMILIES = {"VSOURCE", "CSOURCE", "VSINE"}
ADD_TERMINALS = True
SCALE_DIVISOR = 10

CASES: tuple[tuple[str, str, dict[str, int]], ...] = (
    (
        "F01_NE555_PWM_OSCILLATOR_RACK",
        "60-channel NE555 PWM / oscillator rack.",
        {"NE555": 60, "RESISTOR": 360, "CAP": 120, "CAP-ELEC": 60, "DIODE": 120, "NPN": 60, "VSOURCE": 6},
    ),
    (
        "F02_LM741_ACTIVE_FILTER_BANK",
        "60-channel LM741 active filter / comparator bank.",
        {"LM741": 60, "RESISTOR": 420, "CAP": 240, "DIODE": 120, "NPN": 60, "PNP": 60, "VSOURCE": 8, "VSINE": 60},
    ),
    (
        "F03_TRANSISTOR_DRIVER_MATRIX",
        "32-channel transistor driver matrix.",
        {"NPN": 128, "PNP": 128, "DIODE": 256, "RESISTOR": 384, "CAP": 64, "VSOURCE": 8, "CSOURCE": 32},
    ),
    (
        "F04_MIXED_7SEG_DISPLAY_WALL",
        "Maximum mixed seven-segment display wall.",
        {
            "7SEGCOMA": 23,
            "7SEGCOMK": 23,
            "7447": 23,
            "4511": 23,
            "7490": 23,
            "74HC192": 23,
            "74HC04": 12,
            "74HC08": 16,
            "74HC32": 12,
            "RESISTOR": 368,
            "DIODE": 92,
            "CAP": 46,
            "VSOURCE": 10,
        },
    ),
    (
        "F05_DIGITAL_CLOCK_ALARM_STOPWATCH",
        "24-hour digital clock plus alarm and stopwatch board.",
        {
            "NE555": 2,
            "7490": 8,
            "74HC192": 6,
            "74HC85": 6,
            "7447": 6,
            "7SEGCOMA": 6,
            "74HC00": 10,
            "74HC04": 8,
            "74HC08": 12,
            "74HC32": 10,
            "74HC86": 6,
            "74HC74": 8,
            "RESISTOR": 96,
            "CAP": 36,
            "CAP-ELEC": 8,
            "DIODE": 48,
            "VSOURCE": 4,
        },
    ),
    (
        "F06_FREQUENCY_COUNTER_DISPLAY",
        "16-bit frequency counter with display output.",
        {
            "7490": 16,
            "74HC160": 8,
            "74HC192": 8,
            "4511": 8,
            "7SEGCOMK": 8,
            "74HC74": 8,
            "74HC00": 10,
            "74HC04": 8,
            "74HC08": 12,
            "74HC32": 8,
            "74HC86": 4,
            "NE555": 1,
            "RESISTOR": 128,
            "CAP": 48,
            "CAP-ELEC": 8,
            "DIODE": 64,
            "VSOURCE": 4,
            "VSINE": 4,
        },
    ),
    (
        "F07_ALU_COMPARATOR_REGISTER_BOARD",
        "32-bit ALU / comparator / register board.",
        {
            "74HC283": 8,
            "74HC85": 8,
            "74HC86": 16,
            "74HC266": 8,
            "74HC157": 16,
            "74HC151": 8,
            "74HC174": 12,
            "74HC74": 8,
            "74HC00": 16,
            "74HC02": 8,
            "74HC04": 12,
            "74HC08": 16,
            "74HC32": 16,
            "RESISTOR": 160,
            "CAP": 64,
            "DIODE": 80,
            "VSOURCE": 4,
        },
    ),
    (
        "F08_REGISTER_BUS_ROUTING_FABRIC",
        "64-bit register / bus routing fabric.",
        {
            "74HC174": 24,
            "74HC157": 24,
            "74HC151": 16,
            "74HC74": 16,
            "4027": 12,
            "74HC00": 20,
            "74HC02": 12,
            "74HC04": 16,
            "74HC08": 20,
            "74HC32": 20,
            "74HC86": 16,
            "RESISTOR": 220,
            "CAP": 96,
            "DIODE": 96,
            "VSOURCE": 6,
        },
    ),
    (
        "F09_GATE_LEVEL_LOGIC_MAZE",
        "Gate-level Boolean logic maze / decoder board.",
        {
            "74HC00": 48,
            "74HC02": 36,
            "74HC04": 32,
            "74HC08": 48,
            "74HC32": 48,
            "74HC86": 32,
            "74HC266": 24,
            "RESISTOR": 300,
            "CAP": 96,
            "DIODE": 180,
            "VSOURCE": 4,
        },
    ),
    (
        "F10_TRAFFIC_LIGHT_CONTROLLER_SYSTEM",
        "16-intersection traffic light controller system.",
        {
            "NE555": 16,
            "4027": 16,
            "74HC74": 16,
            "74HC76": 16,
            "7490": 16,
            "74HC00": 24,
            "74HC04": 16,
            "74HC08": 24,
            "74HC32": 24,
            "74HC86": 8,
            "NPN": 96,
            "PNP": 48,
            "DIODE": 192,
            "RESISTOR": 320,
            "CAP": 96,
            "CAP-ELEC": 32,
            "VSOURCE": 8,
        },
    ),
    (
        "F11_WAVEFORM_GENERATOR_MEASUREMENT_BENCH",
        "Mixed waveform generator plus digital measurement bench.",
        {
            "NE555": 12,
            "LM741": 24,
            "7490": 8,
            "74HC192": 8,
            "4511": 6,
            "7SEGCOMK": 6,
            "74HC04": 8,
            "74HC08": 8,
            "74HC32": 8,
            "74HC86": 8,
            "RESISTOR": 260,
            "CAP": 180,
            "CAP-ELEC": 48,
            "REALIND": 24,
            "DIODE": 120,
            "NPN": 48,
            "PNP": 48,
            "VSOURCE": 16,
            "CSOURCE": 12,
            "VSINE": 24,
        },
    ),
    (
        "F12_ANALOG_LAB_MEGA_SHEET",
        "RLC, diode, and op-amp analog lab mega sheet.",
        {
            "LM741": 40,
            "RESISTOR": 595,
            "CAP": 360,
            "CAP-ELEC": 160,
            "REALIND": 160,
            "DIODE": 320,
            "NPN": 80,
            "PNP": 80,
            "VSOURCE": 20,
            "CSOURCE": 20,
            "VSINE": 40,
        },
    ),
    (
        "F13_BCD_CALCULATOR_DISPLAY_SYSTEM",
        "BCD calculator / arithmetic display system.",
        {
            "74HC283": 12,
            "74HC85": 8,
            "74HC157": 12,
            "74HC151": 8,
            "74HC86": 12,
            "74HC266": 6,
            "4511": 12,
            "7SEGCOMK": 12,
            "74HC174": 8,
            "74HC74": 8,
            "74HC00": 16,
            "74HC02": 8,
            "74HC04": 12,
            "74HC08": 16,
            "74HC32": 16,
            "RESISTOR": 220,
            "CAP": 80,
            "DIODE": 120,
            "VSOURCE": 6,
        },
    ),
    (
        "F14_ELECTRONICS_TRAINER_BOARD",
        "Low-count high-variety electronics trainer board.",
        {
            "RESISTOR": 180,
            "CAP": 96,
            "CAP-ELEC": 32,
            "REALIND": 24,
            "DIODE": 72,
            "NPN": 32,
            "PNP": 32,
            "LM741": 8,
            "NE555": 8,
            "VSOURCE": 12,
            "CSOURCE": 8,
            "VSINE": 8,
            "4027": 4,
            "4511": 4,
            "7447": 4,
            "7490": 4,
            "74HC00": 4,
            "74HC02": 4,
            "74HC04": 4,
            "74HC08": 4,
            "74HC32": 4,
            "74HC74": 4,
            "74HC76": 4,
            "74HC85": 4,
            "74HC86": 4,
            "74HC151": 4,
            "74HC157": 4,
            "74HC160": 4,
            "74HC174": 4,
            "74HC192": 4,
            "74HC266": 4,
            "74HC283": 4,
            "7SEGCOMA": 4,
            "7SEGCOMK": 4,
        },
    ),
    (
        "F15_NO_SOURCE_DIGITAL_DATAPATH",
        "No-source mega digital datapath sheet.",
        {
            "74HC00": 118,
            "74HC02": 96,
            "74HC04": 96,
            "74HC08": 118,
            "74HC32": 118,
            "74HC86": 96,
            "74HC266": 72,
            "74HC157": 80,
            "74HC151": 64,
            "74HC174": 80,
            "74HC74": 64,
            "4027": 48,
            "74HC283": 48,
            "74HC85": 48,
            "74HC160": 40,
            "74HC192": 40,
            "7490": 32,
            "RESISTOR": 595,
            "CAP": 240,
            "DIODE": 300,
        },
    ),
)

MARKERS = tuple(
    sorted(
        {
            "7SEGCOMA",
            "7SEGCOMK",
            "7SEG-COM-ANODE",
            "7SEG-COM-CAT-BLUE",
            "4027",
            "4511",
            "7447",
            "7490",
            "74HC00",
            "74HC02",
            "74HC04",
            "74HC08",
            "74HC32",
            "74HC74",
            "74HC76",
            "74HC85",
            "74HC86",
            "74HC151",
            "74HC157",
            "74HC160",
            "74HC174",
            "74HC192",
            "74HC266",
            "74HC283",
            "RESISTOR",
            "CAP-ELEC",
            "CAP",
            "REALIND",
            "DIODE",
            "NPN",
            "PNP",
            "LM741",
            "NE555",
            "VSOURCE",
            "CSOURCE",
            "VSINE",
            "$TERBIDIR",
            "$TERPOWER",
            "$TERGROUND",
            "WIRE",
        },
        key=len,
        reverse=True,
    )
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def configure_helper(helper) -> None:
    """Add source-family markers missing from the older generic helper."""
    if "VSINE" not in helper.FAMILY_MARKERS:
        helper.FAMILY_MARKERS = tuple(sorted(("VSINE", *helper.FAMILY_MARKERS), key=len, reverse=True))


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def zip_dir(src: Path, output: Path) -> None:
    if output.exists():
        output.unlink()
    with ZipFile(output, "w") as zf:
        for path in sorted(src.rglob("*")):
            if not path.is_file():
                continue
            info = ZipInfo(path.relative_to(src).as_posix())
            info.compress_type = ZIP_DEFLATED
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.external_attr = 0o600 << 16
            zf.writestr(info, path.read_bytes())


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker: data.count(marker.encode("ascii")) for marker in MARKERS if data.count(marker.encode("ascii"))}


def build_terminal_overlay(bidir_module) -> tuple[bytes, dict[str, object]]:
    templates = bidir_module.load_templates(
        BIDIR_DONORS / "bider_empty.pdsprj",
        BIDIR_DONORS / "180bider_empty.pdsprj",
    )
    registry = FixtureRegistry.load()
    bridge_donor = registry.get("power_terminal_bridge_donor").path
    resistor_donor = registry.get("r21_v9_resistor_terminal_donor").path
    raw_bridge = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")
    power_bridge, replacements = bidir_module.replace_ordinary_terminals(
        raw_bridge,
        templates,
        orientation_policy=ORIENTATION_BY_TERMINAL_ROLE,
    )
    power_bridge = power_bridge[:-1] + b"\x00"
    resistor_templates = rv9._load_templates(read_internal_file(resistor_donor, "ROOT.DSN"), resistor_donor)
    ground_record, ground_suffix = rv9._patch_output(
        resistor_templates.output_terminals[0],
        "G0",
        -13_462_000,
        -10_160_000,
        -13_081_000,
        -10_160_000,
        409,
        marker=b"$TERGROUND",
    )
    ground_bider = bidir_module.build_bidir_record(
        templates,
        label="G0",
        symbol_x=-13_970_000,
        symbol_y=-10_160_000,
        angle_tenths=0,
        suffix=0x9101,
        active_link=False,
    )
    records = [power_bridge, ground_bider, ground_record]
    return b"".join(records), {
        "terminal_overlay": "locked power bridge converted to $TERPOWER->$TERBIDIR(V0), plus $TERBIDIR(G0) beside $TERGROUND(G0)",
        "labels": ["V0", "G0"],
        "power_bridge_fixture": "power_terminal_bridge_donor",
        "ground_template_fixture": "r21_v9_resistor_terminal_donor",
        "power_bridge_replacements": [item.as_dict() for item in replacements],
        "ground_suffix": f"{ground_suffix:04x}",
        "bider_suffixes": ["from_power_bridge", "9101"],
        "record_sizes": [len(record) for record in records],
        "record_sha256": [sha256_bytes(record) for record in records],
        "expected_markers": {"$TERPOWER": 1, "$TERBIDIR": 2, "$TERGROUND": 1, "WIRE": 1},
    }


def add_terminal_overlay(object_chunk: bytes, terminal_records: bytes) -> bytes:
    if not ADD_TERMINALS:
        return object_chunk
    if not object_chunk.startswith(b"\x00"):
        raise ValueError(f"Object chunk must start with 00 before terminal overlay, got {object_chunk[:8].hex()}")
    if not object_chunk.endswith(b"\xff"):
        raise ValueError("Object chunk must already be finalized before terminal overlay.")
    return b"\x00" + terminal_records + object_chunk[1:]


def scaled_counts(counts: dict[str, int]) -> dict[str, int]:
    return {family: max(1, (count + SCALE_DIVISOR - 1) // SCALE_DIVISOR) for family, count in counts.items() if count > 0}


def host_for(counts: dict[str, int]):
    if SOURCE_FAMILIES & {family for family, count in counts.items() if count > 0}:
        return SOURCE_DONOR, "source_capable"
    return NO_SOURCE_DONOR, "no_source"


def display_chunk(v9, counts: dict[str, int]) -> tuple[bytes, dict[str, object]]:
    anode = counts.get("7SEGCOMA", 0)
    cathode = counts.get("7SEGCOMK", 0)
    if anode and cathode:
        rows, meta = v9.cathode_anode_pair_rows(cathode, anode)
    elif anode:
        rows, meta = v9.anode_rows_trim_rule(anode)
    elif cathode:
        rows, meta = v9.cathode_rows_with_anode_sentinel(cathode)
    else:
        return b"", {"display_route": None}
    return v9.build_display_chunk(rows), {"display_route": meta}


def select_groups(state, requested: dict[str, int], bridge_ref: str | None) -> tuple[tuple[object, ...], dict[str, object], dict[str, int]]:
    selected: list[object] = []
    requested_generic = {
        family: count
        for family, count in requested.items()
        if count > 0 and family not in DISPLAY_FAMILIES
    }
    effective: dict[str, int] = {}
    clipped: dict[str, dict[str, int]] = {}
    selected_keys: dict[str, list[str]] = {}

    display_present = any(requested.get(family, 0) for family in DISPLAY_FAMILIES)
    for family, requested_count in requested_generic.items():
        available = list(state.groups_by_family.get(family, ()))
        if not available and requested_count:
            clipped[family] = {"requested": requested_count, "generated": 0, "available": 0}
            effective[family] = 0
            continue
        target = requested_count
        if display_present and family == "DIODE" and bridge_ref:
            available = [group for group in available if group.key != bridge_ref]
            target = max(0, requested_count - 1)
        generated = min(target, len(available))
        groups = available[:generated]
        selected.extend(groups)
        effective[family] = generated + (1 if display_present and family == "DIODE" and bridge_ref and requested_count > 0 else 0)
        selected_keys[family] = [group.key for group in groups]
        if effective[family] != requested_count:
            clipped[family] = {
                "requested": requested_count,
                "generated": effective[family],
                "available": len(available) + (1 if display_present and family == "DIODE" and bridge_ref else 0),
            }

    for family in DISPLAY_FAMILIES:
        if requested.get(family, 0):
            effective[family] = requested[family]

    ordered = tuple(sorted(selected, key=lambda group: group.start))
    return ordered, {"selected_keys": selected_keys, "clipped_counts": clipped}, effective


def write_case(
    case_id: str,
    description: str,
    original_counts: dict[str, int],
    counts: dict[str, int],
    helper,
    v9,
    v11,
    terminal_records: bytes,
    terminal_meta: dict[str, object],
) -> dict[str, object]:
    donor_path, route = host_for(counts)
    state = helper.load_donor(donor_path)
    donor_dsn = read_internal_file(donor_path, "ROOT.DSN")
    donor_cdb = read_internal_file(donor_path, "ROOT.CDB")

    display_present = any(counts.get(family, 0) for family in DISPLAY_FAMILIES)
    bridge = b""
    bridge_meta: dict[str, object] = {"d20_bridge": None}
    bridge_ref: str | None = None
    if display_present:
        bridge, bridge_meta = v11.load_d20_bridge(v9)
        bridge_ref = str(bridge_meta["bridge_ref"])

    selected, selection_meta, generated_counts = select_groups(state, counts, bridge_ref)
    display, display_meta = display_chunk(v9, counts)

    if display_present:
        bad_final = [group.key for group in selected if group.source_is_final]
        if bad_final:
            raise ValueError(f"{case_id}: selected donor-final groups before display block: {bad_final[:12]}")
        if any(not group.data.endswith(b"\x00") for group in selected):
            bad = [group.key for group in selected if not group.data.endswith(b"\x00")]
            raise ValueError(f"{case_id}: selected non-final groups do not end in 00: {bad[:12]}")
        object_chunk = b"\x00\x00" + b"".join(group.data for group in selected) + bridge + display
        finalization = {"method": "display_finalizes_stream"}
    else:
        object_chunk, finalization = helper.object_chunk_for(selected)

    object_chunk = add_terminal_overlay(object_chunk, terminal_records)

    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    dsn, pointers = build_dsn(donor_dsn, donor_dsn, object_chunk)
    write_project_from_parts(donor_path, output, {"ROOT.DSN": dsn, "ROOT.CDB": donor_cdb}, compression=ZIP_DEFLATED)
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    final_cdb = read_internal_file(output, "ROOT.CDB")
    errors: list[str] = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs from requested chunk")
    if final_cdb != donor_cdb:
        errors.append("ROOT.CDB differs from selected donor")
    if ADD_TERMINALS:
        expected_terms = {"$TERPOWER": 1, "$TERBIDIR": 2, "$TERGROUND": 1}
        observed_terms = marker_counts(final_chunk)
        for marker, expected in expected_terms.items():
            if observed_terms.get(marker, 0) != expected:
                errors.append(f"{marker} count {observed_terms.get(marker, 0)} != {expected}")
        if observed_terms.get("WIRE", 0) < 1:
            errors.append("WIRE count is zero; power bridge wire marker is missing")
    for source in SOURCE_FAMILIES:
        if counts.get(source, 0) == 0 and final_chunk.count(source.encode("ascii")):
            errors.append(f"{source} marker present even though count is zero")
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "description": description,
        "route": route,
        "donor": str(donor_path.relative_to(ROOT)),
        "scale_divisor": SCALE_DIVISOR,
        "original_counts": original_counts,
        "requested_counts": counts,
        "generated_counts": generated_counts,
        "selection": selection_meta,
        "display": display_meta,
        "d20_bridge": bridge_meta,
        "terminals": terminal_meta if ADD_TERMINALS else None,
        "finalization": finalization,
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": sha256_bytes(final_chunk),
        "root_cdb_size": len(final_cdb),
        "root_cdb_sha256": sha256_bytes(final_cdb),
        "marker_counts": marker_counts(final_chunk),
        "pointers": pointers,
        "errors": errors,
    }


def build_cases() -> dict[str, object]:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    helper = load_module("mega_bare_helper_for_real_family_v1", HELPER_PATH)
    configure_helper(helper)
    v9 = load_module("display_v9_for_real_family_v1", V9_PATH)
    v11 = load_module("display_v11_for_real_family_v1", V11_PATH)
    bidir = load_module("bidir_for_real_family_v1", BIDIR_PATH)
    terminal_records, terminal_meta = build_terminal_overlay(bidir)

    source_state = helper.load_donor(SOURCE_DONOR)
    no_source_state = helper.load_donor(NO_SOURCE_DONOR)
    cases = [
        write_case(case_id, description, counts, scaled_counts(counts), helper, v9, v11, terminal_records, terminal_meta)
        for case_id, description, counts in CASES
    ]
    return {
        "experiment": "real_family_stress_v2_scaled_temp_2026_06_18",
        "purpose": "Scaled-by-10 realistic component-family stress circuits from the user-provided table, generated through the accepted raw component placer plus power/ground terminal overlay.",
        "scale_divisor": SCALE_DIVISOR,
        "source_donor_counts": source_state.counts(),
        "no_source_donor_counts": no_source_state.counts(),
        "terminal_layer_enabled": ADD_TERMINALS,
        "terminal_layer": terminal_meta,
        "case_count": len(cases),
        "case_errors": {case["case_id"]: case["errors"] for case in cases if case["errors"]},
        "cases": cases,
    }


def main() -> None:
    manifest = build_cases()
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "REAL FAMILY STRESS V2 SCALED TEMP\n\n"
        "Suggested test order from the request: F14, F05, F11, F04, F01, F02, F03, F07, F08, F15.\n"
        "Counts are divided by 10 and rounded up for nonzero families.\n"
        "All files are raw component-placement tests with no generated wiring.\n"
        "Every case includes a donor-derived power/ground overlay: $TERPOWER->$TERBIDIR(V0), plus $TERBIDIR(G0) beside $TERGROUND(G0).\n"
        "Counts that exceeded the selected donor inventory are clipped and recorded in manifest.json.\n",
        encoding="utf-8",
    )
    zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "case_errors": manifest["case_errors"]}, indent=2))


if __name__ == "__main__":
    main()
