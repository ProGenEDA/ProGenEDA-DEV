"""Generate whole-donor mixed sequential counter retry cases.

V3 proved that unit slicing is unsafe for sequential counters: even the
same-family unit-slice control failed in Proteus. V4 therefore starts from
complete donor object chunks that Proteus already accepts, then mutates only
labels and same-length device identities inside the intact donor structure.

This is still temporary research. It deliberately avoids 74HC4024 in mixed
identity mutations because that donor has a different visible-terminal count
and a longer device marker than 4017/4020.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
SCRIPT_V2 = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_ic_sequential_counters_v2_temp.py"
OUT_ROOT = REPO / "experiments" / "ic_sequential_counters_v4_whole_donor_retry_temp_2026_06_09"
ARCHIVE_PATH = REPO / "experiments" / "IC_SEQUENTIAL_COUNTERS_V4_WHOLE_DONOR_RETRY_TEMP_2026_06_09.zip"


def load_v2_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v2_temp_for_v4", SCRIPT_V2)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load V2 generator from {SCRIPT_V2}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


seq = load_v2_module()


def donor_kind_for_count(count: int) -> str:
    if count == 1:
        return "single"
    if count == 2:
        return "two"
    if count == 4:
        return "four"
    raise ValueError("Whole-donor retry currently supports 1, 2, or 4 packages only.")


def _occurrence_groups(data: bytes, marker: str, group_count: int) -> list[list[int]]:
    raw = marker.encode("ascii")
    positions: list[int] = []
    start = 0
    while True:
        pos = data.find(raw, start)
        if pos < 0:
            break
        positions.append(pos)
        start = pos + 1
    if len(positions) % group_count != 0:
        raise ValueError(f"{marker} occurrence count {len(positions)} cannot be divided into {group_count} packages.")
    per_group = len(positions) // group_count
    return [positions[index * per_group : (index + 1) * per_group] for index in range(group_count)]


def _replace_occurrence_group(data: bytes, old: str, new: str, positions: list[int]) -> bytes:
    if old == new:
        return data
    if len(old) != len(new):
        raise ValueError(f"Cannot patch variable-length device marker {old!r} -> {new!r} in whole-donor V4.")
    old_raw = old.encode("ascii")
    out = bytearray(data)
    for pos in positions:
        if data[pos : pos + len(old_raw)] != old_raw:
            raise ValueError(f"Expected {old} at offset {pos}, but donor bytes changed.")
        out[pos : pos + len(old_raw)] = new.encode("ascii")
    return bytes(out)


def patch_device_groups(data: bytes, base_family, package_families) -> bytes:
    out = data
    group_count = len(package_families)
    groups = _occurrence_groups(data, base_family.proteus_device, group_count)
    for index, family in enumerate(package_families):
        out = _replace_occurrence_group(
            out,
            base_family.proteus_device,
            family.proteus_device,
            groups[index],
        )
    return out


def whole_chunk_labels(base_family, donor_kind: str, package_families) -> tuple[dict[int, str], list[dict[str, object]]]:
    chunk = seq._extract_object_chunk(seq.read_internal_file(base_family.donor(donor_kind), "ROOT.DSN"))
    single_count = len(seq.bidir_events(seq._extract_object_chunk(seq.read_internal_file(base_family.donor("single"), "ROOT.DSN"))))
    events = seq.bidir_events(chunk)
    replacements: dict[int, str] = {}
    plan: list[dict[str, object]] = []
    previous_chain = ""
    for index, event in enumerate(events):
        chip_index = index // single_count
        pin_index = index % single_count
        family = package_families[chip_index]
        parsed = seq.parse_pin_label(str(event["label"]))
        signal = (parsed["signal"] or f"P{pin_index:02d}").upper().replace(" ", "")
        pin = parsed["pin"] or f"X{pin_index:02d}"
        prefix = chr(ord("A") + chip_index)
        label = f"{prefix}{signal[:3]}{pin}"
        if signal == base_family.cascade_source:
            label = f"{prefix}CAS"
        if previous_chain and signal in base_family.clock_inputs:
            label = previous_chain
        replacements[index] = label
        plan.append(
            {
                "terminal_index": index,
                "ref": f"U{chip_index + 1}",
                "base_family": base_family.user_name,
                "intended_family": family.user_name,
                "old_label": event["label"],
                "new_label": label,
                "signal": signal,
                "pin": pin,
            }
        )
        if pin_index == single_count - 1:
            previous_chain = f"{prefix}CAS"
    return replacements, plan


def write_whole_donor_case(
    case_id: str,
    description: str,
    base_key: str,
    package_keys: tuple[str, ...],
) -> dict[str, object]:
    family_lookup = {family.key: family for family in seq.FAMILIES}
    base_family = family_lookup[base_key]
    package_families = [family_lookup[key] for key in package_keys]
    donor_kind = donor_kind_for_count(len(package_families))
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    donor_path = base_family.donor(donor_kind)
    donor_dsn = seq.read_internal_file(donor_path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(donor_path, "ROOT.CDB")
    chunk = seq._extract_object_chunk(donor_dsn)
    replacements, label_plan = whole_chunk_labels(base_family, donor_kind, package_families)
    chunk, mutations = seq.patch_bidir_labels(chunk, replacements)
    chunk = patch_device_groups(chunk, base_family, package_families)
    cdb = patch_device_groups(donor_cdb, base_family, package_families)

    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        chunk,
        seq.combined_device_section(package_families),
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
    out_chunk = seq._extract_object_chunk(dsn)
    static_issues = seq.mixed_static_issues(output, package_families, label_plan)
    expected_terminal_count = len(seq.bidir_events(chunk))
    if out_chunk.count(seq.BIDIR_MARKER) != expected_terminal_count:
        static_issues.append("mutated whole-donor chunk has unexpected bidirectional terminal count")
    manifest = {
        "case_id": case_id,
        "description": description,
        "method": "v4_whole_donor_same_length_identity_mutation",
        "status": "temporary_pending_user_proteus_testing",
        "base_family": base_family.user_name,
        "donor_kind": donor_kind,
        "families": [family.user_name for family in package_families],
        "proteus_devices": [family.proteus_device for family in package_families],
        "terminal_policy": "sequential counter IC visible pins use donor-native $TERBIDIR records",
        "changed_from_v3": "No unit slicing. The complete accepted donor object chunk is kept intact before label/device mutation.",
        "section_pointers": pointers,
        "label_plan": label_plan,
        "mutations": mutations,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": seq.marker_counts(out_chunk),
        "cdb_marker_counts": seq.marker_counts(cdb),
        "object_chunk_size": len(out_chunk),
        "static_validation_issues": static_issues,
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(out_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(seq.bidir_events(out_chunk), indent=2) + "\n", encoding="utf-8")
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
            "T00_CONTROL_74HC193_2X_WHOLE_DONOR_LABELS",
            "Whole 2x 74HC193 donor transplanted from E001 with label mutation only. No unit slicing.",
            "74hc193",
            ("74hc193", "74hc193"),
        ),
        (
            "T01_RETRY_74HC192_74HC193_WHOLE_DONOR",
            "Whole 2x 74HC192 donor with U2 identity mutated to 74HC193 using same-length marker replacement.",
            "74hc192",
            ("74hc192", "74hc193"),
        ),
        (
            "T02_RETRY_4017_4020_WHOLE_DONOR",
            "Whole 2x 4017 donor with U2 identity mutated to 4020 using same-length marker replacement.",
            "4017",
            ("4017", "4020"),
        ),
        (
            "T03_RETRY_74HC161_74HC192_74HC193_74HC163_WHOLE_DONOR",
            "Whole 4x 74HC161 donor with same-length HC counter identity mutations.",
            "74hc161",
            ("74hc161", "74hc192", "74hc193", "74hc163"),
        ),
        (
            "T04_CONTROL_4020_4X_WHOLE_DONOR_LABELS",
            "Whole 4x 4020 donor transplanted from E001 with label mutation only. No unit slicing.",
            "4020",
            ("4020", "4020", "4020", "4020"),
        ),
    ]
    manifests = [write_whole_donor_case(*case) for case in cases]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_SEQUENTIAL_COUNTERS_V4_WHOLE_DONOR_RETRY_TEMP_2026_06_09",
        "purpose": "Retry after V3 unit-slice failure by preserving complete donor object chunks and mutating only labels/same-length device identities.",
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
