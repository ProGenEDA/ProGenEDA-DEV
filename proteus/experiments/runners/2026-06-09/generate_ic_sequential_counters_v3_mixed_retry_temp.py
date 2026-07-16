"""Generate safer mixed sequential counter/divider retry cases.

V2 single-family counter/divider cases were accepted by user testing, but the
three heterogeneous mixed-family cases crashed Proteus before open. This retry
keeps the working single-family path untouched and changes only the mixed
assembly experiment:

- final generated package always comes from donor slot 4, preserving final-unit
  record shape instead of appending FF to an arbitrary middle unit;
- small same-family and two-family controls are emitted before the requested
  T06/T07/T08 mixed retries;
- the batch remains temporary until user Proteus open/sim testing passes.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SCRIPT_V2 = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_ic_sequential_counters_v2_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_sequential_counters_v3_mixed_retry_temp_2026_06_09"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_SEQUENTIAL_COUNTERS_V3_MIXED_RETRY_TEMP_2026_06_09.zip"


def load_v2_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v2_temp_for_v3", SCRIPT_V2)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load V2 generator from {SCRIPT_V2}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


seq = load_v2_module()


def source_slots_for_component_count(count: int) -> list[int]:
    if count < 1 or count > 4:
        raise ValueError("Mixed retry cases support one to four IC packages.")
    if count == 1:
        return [3]
    if count == 2:
        return [0, 3]
    if count == 3:
        return [0, 1, 3]
    return [0, 1, 2, 3]


def case_prefix(index: int) -> str:
    return chr(ord("A") + index)


def patch_unit_final_aware(
    family,
    *,
    source_slot: int,
    ref: str,
    label_prefix: str,
    chain_from_previous: str = "",
):
    source_ref = f"U{source_slot + 1}"
    unit = seq.unit_slices_from_four(family)[source_slot]
    local_events = seq.bidir_events(unit)
    replacements: dict[int, str] = {}
    plan: list[dict[str, object]] = []
    for index, event in enumerate(local_events):
        parsed = seq.parse_pin_label(str(event["label"]))
        signal = (parsed["signal"] or f"P{index:02d}").upper().replace(" ", "")
        pin = parsed["pin"] or f"X{index:02d}"
        label = f"{label_prefix}{signal[:3]}{pin}"
        if signal == family.cascade_source:
            label = f"{label_prefix}CAS"
        if chain_from_previous and signal in family.clock_inputs:
            label = chain_from_previous
        replacements[index] = label
        plan.append(
            {
                "ref": ref,
                "family": family.user_name,
                "source_slot": source_slot + 1,
                "local_terminal_index": index,
                "old_label": event["label"],
                "new_label": label,
                "signal": signal,
                "pin": pin,
            }
        )
    patched, _mutations = seq.patch_bidir_labels(unit, replacements, force_final=False)
    return seq.patch_ascii_same_length(patched, source_ref, ref), plan


def write_mixed_retry_case(
    case_id: str,
    description: str,
    family_keys: tuple[str, ...],
    *,
    chain: bool = True,
) -> dict[str, object]:
    family_lookup = {family.key: family for family in seq.FAMILIES}
    families = [family_lookup[key] for key in family_keys]
    components = [(family, f"U{index + 1}") for index, family in enumerate(families)]
    slots = source_slots_for_component_count(len(components))
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    units: list[bytes] = []
    label_plan: list[dict[str, object]] = []
    previous_chain = ""
    for index, ((family, ref), source_slot) in enumerate(zip(components, slots, strict=True)):
        prefix = case_prefix(index)
        unit, plan = patch_unit_final_aware(
            family,
            source_slot=source_slot,
            ref=ref,
            label_prefix=prefix,
            chain_from_previous=previous_chain if chain else "",
        )
        units.append(unit)
        label_plan.extend(plan)
        previous_chain = f"{prefix}CAS" if chain else ""

    object_chunk = b"\x00" + b"".join(units) + b"\xff"
    cdb = seq.build_mixed_cdb(components)
    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    donor_dsn = seq.read_internal_file(components[0][0].donor("single"), "ROOT.DSN")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        object_chunk,
        seq.combined_device_section(families),
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    static_issues = seq.mixed_static_issues(output, families, label_plan)
    manifest = {
        "case_id": case_id,
        "description": description,
        "method": "v3_mixed_family_final_slot_retry",
        "status": "temporary_pending_user_proteus_testing",
        "families": [family.user_name for family in families],
        "proteus_devices": [family.proteus_device for family in families],
        "source_slots": [slot + 1 for slot in slots],
        "changed_from_v2": "The last generated IC package uses donor slot 4 so final object-record shape is donor-native.",
        "terminal_policy": "sequential counter IC visible pins use donor-native $TERBIDIR records",
        "topology_policy": "same-name bidirectional labels connect cascade outputs to downstream clock inputs",
        "section_pointers": pointers,
        "label_plan": label_plan,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": seq.marker_counts(chunk),
        "cdb_marker_counts": seq.marker_counts(cdb),
        "object_chunk_size": len(chunk),
        "static_validation_issues": static_issues,
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


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    fixed_time = (2026, 6, 9, 0, 0, 0)
    with ZipFile(ARCHIVE_PATH, "w", ZIP_DEFLATED) as archive:
        for path in sorted(OUT_ROOT.rglob("*")):
            if path.is_file():
                info = ZipInfo(str(path.relative_to(OUT_ROOT)).replace("\\", "/"), fixed_time)
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    cases = [
        (
            "T00_CONTROL_74HC193_2X_UNIT_SLICES_FINAL_SLOT",
            "Same-family 74HC193 two-package control assembled from donor unit slices [slot 1, slot 4].",
            ("74hc193", "74hc193"),
        ),
        (
            "T01_CONTROL_4017_4020_2FAMILY_FINAL_SLOT",
            "Small two-family divider chain using final-aware donor slot selection.",
            ("4017", "4020"),
        ),
        (
            "T06_RETRY_74HC192_74HC193_UPDOWN_CHAIN_FINAL_SLOT",
            "Retry of V2 T06 using 74HC192 then 74HC193 with final package sourced from donor slot 4.",
            ("74hc192", "74hc193"),
        ),
        (
            "T07_RETRY_4017_4020_74HC4024_DIVIDER_CHAIN_FINAL_SLOT",
            "Retry of V2 T07 using 4017, 4020, and 74HC4024 with final package sourced from donor slot 4.",
            ("4017", "4020", "74hc4024"),
        ),
        (
            "T08_RETRY_74HC161_74HC192_4017_4020_CHAIN_FINAL_SLOT",
            "Retry of V2 T08, retained as four packages so donor slot order is already [1,2,3,4].",
            ("74hc161", "74hc192", "4017", "4020"),
        ),
    ]
    manifests = [write_mixed_retry_case(*case) for case in cases]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_SEQUENTIAL_COUNTERS_V3_MIXED_RETRY_TEMP_2026_06_09",
        "purpose": "Retry only the V2 heterogeneous mixed sequential-counter crash cases with final-slot-aware unit assembly.",
        "status": "temporary_pending_user_proteus_testing",
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
