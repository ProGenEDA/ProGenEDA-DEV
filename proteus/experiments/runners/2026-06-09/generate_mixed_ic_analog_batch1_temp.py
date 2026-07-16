"""Generate conservative controls from real mixed IC/analog donors.

These donors were supplied after synthetic mixed sequential assembly failed.
This script deliberately avoids unit slicing, device identity mutation, and
subset removal. It tests only complete mixed donor projects:

- exact deterministic repack;
- whole donor object/CDB/device-section transplant into E001;
- topology-preserving bidirectional terminal label mutation.

If these pass manual Proteus testing, use this donor family as the base for the
next mixed-large-circuit route.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SCRIPT_V2 = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_ic_sequential_counters_v2_temp.py"
DONOR_ROOT = REPO / "proteus" / "active" / "evidence" / "donors" / "mixed_ic_analog_batch1"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_analog_batch1_temp_2026_06_09"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_ANALOG_BATCH1_TEMP_2026_06_09.zip"


def load_seq_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v2_for_mixed_analog", SCRIPT_V2)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load helper module from {SCRIPT_V2}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


seq = load_seq_module()


MARKERS = (
    b"7490",
    b"74HC160",
    b"74HC161",
    b"74HC163",
    b"74HC192",
    b"74HC193",
    b"4017",
    b"4020",
    b"4024",
    b"74HC4024",
    b"74HC4040",
    b"74HC4060",
    b"4518",
    b"74HC4520",
    b"74HC157",
    b"74HC283",
    b"74HC165",
    b"74HC595",
    b"74HC85",
    b"NE555",
    b"NPN",
    b"PNP",
    b"LM741",
    b"CAP-ELEC",
    b"RESISTOR",
    b"CAPACITOR",
    b"REALIND",
    b"$TERBIDIR",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"VSOURCE",
    b"CSOURCE",
    b"VSINE",
)


@dataclass(frozen=True)
class MixedDonor:
    key: str
    filename: str
    description: str
    required_markers: tuple[str, ...]

    @property
    def path(self) -> Path:
        return DONOR_ROOT / self.filename


DONORS = (
    MixedDonor(
        "analog_only",
        "MIX_RCL_ANALOG_ONLY.pdsprj",
        "R/C/L plus NPN, PNP, LM741, and electrolytic capacitor donor.",
        ("RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
    ),
    MixedDonor(
        "seq_192_193",
        "MIX_SEQ_192_193_RCL_ANALOG.pdsprj",
        "74HC192 and 74HC193 mixed with R/C/L and analog donors.",
        ("74HC192", "74HC193", "RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
    ),
    MixedDonor(
        "seq_4017_4020_4024",
        "MIX_SEQ_4017_4020_4024.pdsprj",
        "4017, 4020, and 74HC4024 mixed with R/C/L and analog donors.",
        ("4017", "4020", "74HC4024", "RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
    ),
    MixedDonor(
        "seq_192_193_4017_4020_4024",
        "MIX_SEQ_192_193_4017_4020_4024_RCL_ANALOG.pdsprj",
        "74HC192, 74HC193, 4017, 4020, and 74HC4024 mixed with R/C/L and analog donors.",
        ("74HC192", "74HC193", "4017", "4020", "74HC4024", "RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
    ),
    MixedDonor(
        "seq_counters_all",
        "MIX_SEQ_COUNTERS_ALL_RCL_ANALOG.pdsprj",
        "Large counter/divider donor with all supplied counter families plus R/C/L and analog donors.",
        ("7490", "74HC160", "74HC161", "74HC163", "74HC192", "74HC193", "4017", "4020", "74HC4024", "74HC4040", "74HC4060", "4518", "74HC4520", "RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
    ),
    MixedDonor(
        "misc_logic_analog",
        "MIX_MISC_157_283_165_595_85_RCL_ANALOG.pdsprj",
        "74HC157, 74HC283, 74HC165, 74HC595, and 74HC85 mixed with R/C/L and analog donors.",
        ("74HC157", "74HC283", "74HC165", "74HC595", "74HC85", "RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
    ),
)


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS if data.count(marker)}


def base36(value: int) -> str:
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if value == 0:
        return "00"
    chars: list[str] = []
    while value:
        value, rem = divmod(value, 36)
        chars.append(alphabet[rem])
    return "".join(reversed(chars)).rjust(2, "0")


def inventory_for(donor: MixedDonor) -> dict[str, object]:
    dsn = seq.read_internal_file(donor.path, "ROOT.DSN")
    cdb = seq.read_internal_file(donor.path, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    events = seq.bidir_events(chunk)
    groups: dict[str, list[int]] = {}
    for index, event in enumerate(events):
        groups.setdefault(str(event["label"]), []).append(index)
    return {
        "key": donor.key,
        "file": donor.filename,
        "description": donor.description,
        "required_markers": donor.required_markers,
        "object_chunk_size": len(chunk),
        "terminal_count": len(events),
        "wire_count": chunk.count(b"WIRE"),
        "blank_terminal_count": len(groups.get("", [])),
        "label_group_count": len(groups),
        "duplicate_label_groups": {
            label: indexes for label, indexes in groups.items() if label and len(indexes) > 1
        },
        "marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "hashes": {
            "project": seq._sha256_bytes(donor.path.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
        },
    }


def topology_preserving_replacements(chunk: bytes) -> tuple[dict[int, str], list[dict[str, object]]]:
    events = seq.bidir_events(chunk)
    replacements: dict[int, str] = {}
    group_names: dict[str, str] = {}
    group_index = 0
    plan: list[dict[str, object]] = []
    for index, event in enumerate(events):
        old_label = str(event["label"])
        if old_label:
            if old_label not in group_names:
                group_names[old_label] = f"N{base36(group_index)}"
                group_index += 1
            new_label = group_names[old_label]
            group_key = old_label
        else:
            new_label = f"B{base36(index)}"
            group_key = f"blank:{index}"
        replacements[index] = new_label
        plan.append(
            {
                "terminal_index": index,
                "old_label": old_label,
                "new_label": new_label,
                "group_key": group_key,
                "angle_tenths": event["angle_tenths"],
                "suffix": event["suffix"],
            }
        )
    return replacements, plan


def static_issues(output: Path, donor: MixedDonor, mutations: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    info = seq.inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("mixed IC/analog donor output should not contain ordinary input/output terminals")
    if chunk.count(b"VSOURCE") or chunk.count(b"CSOURCE") or chunk.count(b"VSINE"):
        issues.append("mixed IC/analog donor output unexpectedly contains explicit source markers")
    if chunk.count(b"$TERBIDIR") == 0:
        issues.append("mixed donor output has no bidirectional terminals")
    if chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    for marker in donor.required_markers:
        raw = marker.encode("ascii")
        if chunk.count(raw) == 0:
            issues.append(f"expected DSN marker {marker} missing")
        if cdb.count(raw) == 0:
            issues.append(f"expected CDB marker {marker} missing")
    for mutation in mutations:
        if chunk.count(str(mutation["new"]).encode("ascii")) == 0:
            issues.append(f"mutated label {mutation['new']} not present")
    return issues


def write_case(
    case_id: str,
    donor: MixedDonor,
    description: str,
    *,
    exact_repack: bool = False,
    mutate_labels: bool = False,
) -> dict[str, object]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    donor_dsn = seq.read_internal_file(donor.path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(donor.path, "ROOT.CDB")
    mutations: list[dict[str, object]] = []
    label_plan: list[dict[str, object]] = []
    pointers: dict[str, int] = {}

    if exact_repack:
        seq.write_project_from_parts(
            donor.path,
            output,
            {
                "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(donor.path, "PROJECT.XML"), seq.PROTEUS_813),
                "ROOT.DSN": seq.patch_root_dsn_version(donor_dsn, seq.PROTEUS_813),
                "ROOT.CDB": donor_cdb,
            },
        )
        method = "deterministic_exact_mixed_donor_repack"
    else:
        chunk = seq._extract_object_chunk(donor_dsn)
        if mutate_labels:
            replacements, label_plan = topology_preserving_replacements(chunk)
            chunk, mutations = seq.patch_bidir_labels(chunk, replacements)
        registry = seq.FixtureRegistry.load()
        base = registry.get("e001_empty")
        dsn, pointers = seq.build_dsn_with_device_section(
            seq.read_internal_file(base.path, "ROOT.DSN"),
            donor_dsn,
            chunk,
            seq._device_section(donor_dsn),
        )
        dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
        seq.write_project_from_parts(
            base.path,
            output,
            {
                "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
                "ROOT.DSN": dsn,
                "ROOT.CDB": donor_cdb,
            },
        )
        method = "whole_mixed_donor_object_cdb_device_section_inserted_into_e001"
        if mutate_labels:
            method += "_with_topology_preserving_label_mutation"

    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    manifest = {
        "case_id": case_id,
        "description": description,
        "method": method,
        "status": "temporary_pending_user_proteus_testing",
        "donor_key": donor.key,
        "donor": str(donor.path.relative_to(REPO)),
        "terminal_policy": "all visible endpoints use donor-native $TERBIDIR records",
        "composition_policy": "complete mixed donor only; no unit slicing, identity mutation, or subset removal",
        "section_pointers": pointers,
        "label_plan": label_plan,
        "mutations": mutations,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "object_chunk_size": len(chunk),
        "static_validation_issues": static_issues(output, donor, mutations),
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
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 9, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    missing = [str(donor.path) for donor in DONORS if not donor.path.exists()]
    if missing:
        raise FileNotFoundError("\n".join(missing))
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    inventory = [inventory_for(donor) for donor in DONORS]
    (OUT_ROOT / "learned_mixed_donor_inventory.json").write_text(json.dumps(inventory, indent=2) + "\n", encoding="utf-8")

    manifests: list[dict[str, object]] = []
    for index, donor in enumerate(DONORS, 1):
        prefix = f"T{index:02d}_{donor.key.upper()}"
        manifests.append(write_case(f"{prefix}_EXACT_REPACK", donor, f"Exact repack: {donor.description}", exact_repack=True))
        manifests.append(write_case(f"{prefix}_E001_TRANSPLANT", donor, f"E001 transplant: {donor.description}"))
        manifests.append(
            write_case(
                f"{prefix}_LABEL_MUTATION",
                donor,
                f"Topology-preserving label mutation: {donor.description}",
                mutate_labels=True,
            )
        )

    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_ANALOG_BATCH1_TEMP_2026_06_09",
        "purpose": "Use real mixed IC/analog donors to validate whole-donor mixed projects after synthetic mixed sequential assembly failed.",
        "status": "temporary_pending_user_proteus_testing",
        "composition_policy": "complete mixed donor projects only",
        "terminal_policy": "all visible endpoints use $TERBIDIR",
        "donor_count": len(DONORS),
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "learned_inventory": "learned_mixed_donor_inventory.json",
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
