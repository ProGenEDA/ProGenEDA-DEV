"""Generate focused mixed IC/analog V5 donor-native diagnostics.

User testing accepted V4 T01-T04/T08/T09 and rejected V4 T05-T07. The rejected
cases added VOLTAGE to 74HC4060 instance metadata, producing netlist linker
errors such as VALUE+VOLTAGE not found in the parameter mapping table.

This pack deliberately avoids E001 transplant for 74HC4060 and avoids adding
MODFILE/VOLTAGE to 4060 instance rows. It tests donor-native object edits:

- exact 4060 donor repack;
- 4060 terminal relabels inside the original donor project;
- 4060 output tied to the existing RLC load by same-name bidirectional labels;
- mixed analog/IC donor-native label mutation;
- analog-only and NE555 donor-native edited controls.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import parse_cdb


REPO = Path(__file__).resolve().parents[4]
SEQ_HELPER = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_ic_sequential_counters_v2_temp.py"
MIXED_HELPER = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_analog_batch1_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_focused_v5_donor_native_temp_2026_06_10"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_FOCUSED_V5_DONOR_NATIVE_TEMP_2026_06_10.zip"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


seq = _load_module("seq_helper_for_focused_v5", SEQ_HELPER)
mixed = _load_module("mixed_helper_for_focused_v5", MIXED_HELPER)


@dataclass(frozen=True)
class DonorNativeCase:
    case_id: str
    description: str
    donor_path: Path
    required_markers: tuple[str, ...]
    replacements_by_index: dict[int, str] | None = None
    exact_repack: bool = False


def _safe_signal(label: str, fallback: str) -> str:
    parsed = seq.parse_pin_label(label)
    signal = parsed["signal"] or fallback
    pin = parsed["pin"]
    raw = "".join(ch for ch in f"{signal}{pin}".upper() if ch.isalnum())
    return raw[:6] or fallback


def sequential_unique_replacements(donor_path: Path, *, max_index: int | None = None) -> dict[int, str]:
    chunk = seq._extract_object_chunk(seq.read_internal_file(donor_path, "ROOT.DSN"))
    events = seq.bidir_events(chunk)
    replacements: dict[int, str] = {}
    group_seen: dict[str, int] = {}
    for index, event in enumerate(events):
        if max_index is not None and index > max_index:
            continue
        old = str(event["label"])
        group_seen[old] = group_seen.get(old, 0) + 1
        chip = group_seen[old]
        replacements[index] = f"U{chip}{_safe_signal(old, f'P{index:02d}')}"
    return replacements


def topology_preserving_replacements(donor_path: Path) -> dict[int, str]:
    chunk = seq._extract_object_chunk(seq.read_internal_file(donor_path, "ROOT.DSN"))
    replacements, _plan = mixed.topology_preserving_replacements(chunk)
    return replacements


def replacements_4060_q3_to_existing_rlc(donor_path: Path) -> dict[int, str]:
    """Tie U1 Q3 to the donor RLC chain without touching ground/power labels.

    The 4x 4060+RLC donor terminal order is learned from the user donor:
    indexes 0..55 are 4060 pin terminals, index 58 is the RLC input terminal
    originally labelled Y0, and indexes 59..63 keep the donor RLC/ground nets.
    """

    replacements = sequential_unique_replacements(donor_path, max_index=55)
    replacements[0] = "L0"
    replacements[58] = "L0"
    return replacements


def replacements_ne555_q_to_existing_rlc(donor_path: Path) -> dict[int, str]:
    """Tie the first NE555 Q output to the donor RLC input terminal."""

    replacements = sequential_unique_replacements(donor_path, max_index=15)
    replacements[0] = "NQ0"
    replacements[18] = "NQ0"
    return replacements


def rebuild_donor_native_dsn(donor_dsn: bytes, chunk: bytes) -> tuple[bytes, dict[str, int]]:
    dsn, pointers = seq.build_dsn_with_device_section(
        donor_dsn,
        donor_dsn,
        chunk,
        seq._device_section(donor_dsn),
    )
    return seq.patch_root_dsn_version(dsn, seq.PROTEUS_813), pointers


def _read_lp_ascii(data: bytes, offset: int) -> tuple[str, int]:
    length = data[offset]
    start = offset + 1
    end = start + length
    return data[start:end].decode("ascii", errors="replace"), end


def cdb_4060_voltage_refs(cdb: bytes) -> list[str]:
    refs: list[str] = []
    parsed = parse_cdb(cdb)
    for row in parsed.property_rows:
        pos = 20
        ref, pos = _read_lp_ascii(row.data, pos)
        fields = []
        for _index in range(3):
            field, pos = _read_lp_ascii(row.data, pos)
            fields.append(field)
        property_length = int.from_bytes(row.data[pos : pos + 4], "little")
        text = row.data[pos + 4 : pos + 4 + property_length]
        if "74HC4060" in fields and b"VOLTAGE=4.5V" in text:
            refs.append(ref)
    return refs


def write_case(case: DonorNativeCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    donor_dsn = seq.read_internal_file(case.donor_path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(case.donor_path, "ROOT.CDB")
    donor_project = seq.read_internal_file(case.donor_path, "PROJECT.XML")
    label_plan: list[dict[str, object]] = []
    mutations: list[dict[str, object]] = []
    pointers: dict[str, int] = {}

    if case.exact_repack:
        dsn = seq.patch_root_dsn_version(donor_dsn, seq.PROTEUS_813)
        method = "deterministic_exact_donor_repack_no_e001_transplant"
    else:
        chunk = seq._extract_object_chunk(donor_dsn)
        if case.replacements_by_index:
            events = seq.bidir_events(chunk)
            label_plan = [
                {
                    "terminal_index": index,
                    "old_label": events[index]["label"],
                    "new_label": new_label,
                    "angle_tenths": events[index]["angle_tenths"],
                    "suffix": events[index]["suffix"],
                }
                for index, new_label in sorted(case.replacements_by_index.items())
            ]
            chunk, mutations = seq.patch_bidir_labels(chunk, case.replacements_by_index)
        dsn, pointers = rebuild_donor_native_dsn(donor_dsn, chunk)
        method = "donor_native_device_section_rebuild_with_object_chunk_label_edits"

    seq.write_project_from_parts(
        case.donor_path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(donor_project, seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": donor_cdb,
        },
    )

    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    issues: list[str] = []
    for marker in case.required_markers:
        raw = marker.encode("ascii")
        if raw not in chunk:
            issues.append(f"expected DSN marker {marker} missing")
        if raw not in cdb:
            issues.append(f"expected CDB marker {marker} missing")
    bad_4060_voltage_refs = cdb_4060_voltage_refs(cdb)
    if bad_4060_voltage_refs:
        issues.append(f"4060 CDB rows must not add VOLTAGE=4.5V: {bad_4060_voltage_refs}")
    if chunk.count(b"$TERBIDIR") and chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    for mutation in mutations:
        if chunk.count(str(mutation["new"]).encode("ascii")) == 0:
            issues.append(f"mutated label {mutation['new']} not present")

    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "method": method,
        "status": "temporary_pending_user_proteus_testing",
        "donor": str(case.donor_path.relative_to(REPO)),
        "required_markers": case.required_markers,
        "terminal_policy": "sequential/misc IC and analog visible pins use donor-native bidirectional terminals",
        "model_policy": "74HC4060 keeps donor-native metadata; V4 VOLTAGE/MODFILE instance patch is intentionally absent",
        "section_pointers": pointers,
        "label_plan": label_plan,
        "mutations": mutations,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": mixed.marker_counts(chunk),
        "cdb_marker_counts": mixed.marker_counts(cdb),
        "metadata_counts": {
            "dsn_modfile": dsn.count(b"MODFILE"),
            "dsn_voltage": dsn.count(b"VOLTAGE"),
            "cdb_modfile": cdb.count(b"MODFILE"),
            "cdb_voltage": cdb.count(b"VOLTAGE"),
            "cdb_4060_voltage_45": cdb.count(b"VOLTAGE=4.5V"),
            "cdb_4060_voltage_refs": bad_4060_voltage_refs,
        },
        "object_chunk_size": len(chunk),
        "terminal_count": chunk.count(b"$TERBIDIR") + chunk.count(b"$TERINPUT") + chunk.count(b"$TEROUTPUT"),
        "wire_count": chunk.count(b"WIRE"),
        "static_validation_issues": issues,
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(seq.bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


DONOR_4060_RLC = REPO / "proteus" / "active" / "evidence" / "donors" / "sequential_ics_batch3" / "4_74HC4060withRLC.pdsprj"
DONOR_MIXED_COUNTERS = REPO / "proteus" / "active" / "evidence" / "donors" / "mixed_ic_analog_batch1" / "MIX_SEQ_COUNTERS_ALL_RCL_ANALOG.pdsprj"
DONOR_ANALOG_ONLY = REPO / "proteus" / "active" / "evidence" / "donors" / "mixed_ic_analog_batch1" / "MIX_RCL_ANALOG_ONLY.pdsprj"
DONOR_NE555_RLC = REPO / "proteus" / "active" / "evidence" / "donors" / "analog_misc_batch1" / "2_NE555WITHRLC.pdsprj"


CASES: tuple[DonorNativeCase, ...] = (
    DonorNativeCase(
        "T01_4060_RLC_EXACT_DONOR_NATIVE",
        "Exact 4x 74HC4060+RLC donor-native repack; verifies whether the donor itself simulates.",
        DONOR_4060_RLC,
        ("74HC4060", "RESISTOR", "CAPACITOR", "REALIND"),
        exact_repack=True,
    ),
    DonorNativeCase(
        "T02_4060_RLC_UNIQUE_PIN_LABELS_NATIVE",
        "Donor-native 4060+RLC project with 4060 pin terminals uniquely relabelled; no E001 transplant.",
        DONOR_4060_RLC,
        ("74HC4060", "RESISTOR", "CAPACITOR", "REALIND"),
        replacements_by_index=sequential_unique_replacements(DONOR_4060_RLC, max_index=55),
    ),
    DonorNativeCase(
        "T03_4060_Q3_DRIVES_RLC_LOAD_NATIVE",
        "Donor-native 4060 edit: U1 Q3 terminal and existing RLC input share L0, so the output drives the R-C-L chain to the donor ground net.",
        DONOR_4060_RLC,
        ("74HC4060", "RESISTOR", "CAPACITOR", "REALIND"),
        replacements_by_index=replacements_4060_q3_to_existing_rlc(DONOR_4060_RLC),
    ),
    DonorNativeCase(
        "T04_MIXED_COUNTERS_ANALOG_LABEL_MUTATION_NATIVE",
        "Large mixed donor-native edit retaining counters, 4060, RLC, NPN, PNP, LM741, and CAP-ELEC with topology-preserving labels.",
        DONOR_MIXED_COUNTERS,
        ("74HC4060", "74HC4040", "74HC160", "74HC161", "74HC163", "RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
        replacements_by_index=topology_preserving_replacements(DONOR_MIXED_COUNTERS),
    ),
    DonorNativeCase(
        "T05_ANALOG_ONLY_RLC_BJT_OPAMP_ECAP_NATIVE",
        "Analog/basic donor-native edit covering RLC, NPN, PNP, LM741, and electrolytic capacitor.",
        DONOR_ANALOG_ONLY,
        ("RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
        replacements_by_index=topology_preserving_replacements(DONOR_ANALOG_ONLY),
    ),
    DonorNativeCase(
        "T06_NE555_Q_DRIVES_RLC_LOAD_NATIVE",
        "NE555 donor-native edit: the first Q output shares NQ0 with the existing RLC input terminal.",
        DONOR_NE555_RLC,
        ("NE555", "RESISTOR", "CAPACITOR", "REALIND"),
        replacements_by_index=replacements_ne555_q_to_existing_rlc(DONOR_NE555_RLC),
    ),
)


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 10, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    missing = [str(case.donor_path) for case in CASES if not case.donor_path.exists()]
    if missing:
        raise FileNotFoundError("\n".join(missing))
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifests = [write_case(case) for case in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_FOCUSED_V5_DONOR_NATIVE_TEMP_2026_06_10",
        "purpose": "Follow-up after V4 T05-T07 74HC4060 linker failures. Keep 4060 donor-native metadata and test label/topology edits without E001 transplant.",
        "status": "temporary_pending_user_proteus_testing",
        "v4_user_result": "T01-T04/T08/T09 opened; T05-T07 failed with VALUE+VOLTAGE linker errors.",
        "rules_under_test": [
            "Do not add VOLTAGE=4.5V to 74HC4060 instance metadata.",
            "For 74HC4060, preserve the donor-native DSN/device metadata until a safer transplant rule is proven.",
            "Use same-name bidirectional terminals to connect IC outputs to existing RLC loads.",
        ],
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "archive": str(ARCHIVE_PATH.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE_PATH),
                "archive_sha256": archive_hash,
                "static_issue_cases": summary_issues,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
