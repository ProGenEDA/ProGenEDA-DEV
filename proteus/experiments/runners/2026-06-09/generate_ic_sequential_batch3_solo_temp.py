"""Generate solo donor-learning cases for the third sequential IC batch.

This batch deliberately avoids mixed-family synthesis. User testing rejected the
V3 unit-slice method and the V4 mixed identity-mutation cases T01-T03 with ISIS
errors. Until a real mixed sequential donor is supplied, this script only emits
whole-donor per-family controls:

- exact donor repack;
- E001 transplant with unchanged donor object/CDB/device section;
- single and multi-package bidirectional-label mutations;
- RLC donor transplant where an RLC donor was supplied.
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
DONOR_ROOT = REPO / "proteus" / "active" / "evidence" / "donors" / "sequential_ics_batch3"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_sequential_batch3_solo_temp_2026_06_09"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_SEQUENTIAL_BATCH3_SOLO_TEMP_2026_06_09.zip"


def load_v2_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v2_temp_for_batch3", SCRIPT_V2)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load sequential helper module from {SCRIPT_V2}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


seq = load_v2_module()


@dataclass(frozen=True)
class SequentialFamily:
    key: str
    user_name: str
    proteus_device: str
    single: str
    two: str
    four: str | None
    rlc: str | None
    rlc_kind: str | None
    notes: str = ""

    def donor(self, kind: str) -> Path:
        filename = {
            "single": self.single,
            "two": self.two,
            "four": self.four,
            "rlc": self.rlc,
        }[kind]
        if filename is None:
            raise FileNotFoundError(f"{self.user_name} has no {kind} donor in batch 3.")
        return DONOR_ROOT / filename


FAMILIES: tuple[SequentialFamily, ...] = (
    SequentialFamily("74hc4040", "74HC4040", "74HC4040", "74HC4040.pdsprj", "2_74HC4040.pdsprj", "4_74HC4040.pdsprj", "4_74HC4040withRLC.pdsprj", "four"),
    SequentialFamily("74hc4060", "74HC4060", "74HC4060", "74HC4060.pdsprj", "2_74HC4060.pdsprj", "4_74HC4060.pdsprj", "4_74HC4060withRLC.pdsprj", "four"),
    SequentialFamily("4518", "4518", "4518", "4518.pdsprj", "2_4518.pdsprj", "4_4518.pdsprj", "4_4518withRLC.pdsprj", "four"),
    SequentialFamily("74hc4520", "74HC4520", "74HC4520", "74HC4520.pdsprj", "2_74HC4520.pdsprj", "4_74HC4520.pdsprj", "4_74HC4520withRLC.pdsprj", "four"),
    SequentialFamily("74hc74", "74HC74", "74HC74", "74HC74.pdsprj", "2_74HC74.pdsprj", "4_74HC74.pdsprj", "4_74HC74withRLC.pdsprj", "four"),
    SequentialFamily("74hc76", "74HC76", "74HC76", "74HC76.pdsprj", "2_74HC76.pdsprj", "4_74HC76.pdsprj", "4_74HC76withRLC.pdsprj", "four"),
    SequentialFamily("74hc174", "74HC174", "74HC174", "74HC174.pdsprj", "2_74HC174.pdsprj", "4_74HC174.pdsprj", "4_74HC174withRLC.pdsprj", "four", "User supplied 74HC174 donors; requested list mentioned 74HC175 earlier, so keep this distinct."),
    SequentialFamily("74hc273", "74HC273", "74HC273", "74HC273.pdsprj", "2_74HC273.pdsprj", "4_74HC273.pdsprj", "4_74HC273withRLC.pdsprj", "four"),
    SequentialFamily("4027", "4027", "4027", "4027.pdsprj", "2_4027.pdsprj", None, "2_4027withRLC.pdsprj", "two", "Only single, 2x, and 2xRLC donors were supplied; no 4x case is generated."),
)


def safe_case_name(text: str) -> str:
    return text.replace("/", "_").replace(" ", "_").replace("-", "_")


def learned_pin_map(family: SequentialFamily) -> dict[str, object]:
    chunk = seq._extract_object_chunk(seq.read_internal_file(family.donor("single"), "ROOT.DSN"))
    terminals: list[dict[str, object]] = []
    for index, event in enumerate(seq.bidir_events(chunk)):
        parsed = seq.parse_pin_label(str(event["label"]))
        terminals.append(
            {
                "index": index,
                "label": event["label"],
                "signal": parsed["signal"],
                "pin": parsed["pin"],
                "angle_tenths": event["angle_tenths"],
                "side": "left" if event["angle_tenths"] == 1800 else "right",
                "suffix": event["suffix"],
            }
        )
    pin_aliases: dict[str, str] = {}
    ambiguous_pins: dict[str, list[str]] = {}
    for item in terminals:
        pin = str(item["pin"])
        signal = str(item["signal"])
        if not pin or not signal:
            continue
        if pin in pin_aliases and pin_aliases[pin] != signal:
            ambiguous_pins.setdefault(pin, [pin_aliases[pin]]).append(signal)
        else:
            pin_aliases[pin] = signal
    for pin in ambiguous_pins:
        pin_aliases.pop(pin, None)
    return {
        "family": family.user_name,
        "proteus_device": family.proteus_device,
        "notes": family.notes,
        "terminal_policy": "sequential IC visible pins use donor-native $TERBIDIR records",
        "terminals": terminals,
        "pin_aliases": pin_aliases,
        "ambiguous_pin_aliases": ambiguous_pins,
        "signal_aliases": {
            str(item["signal"]).upper().replace(" ", ""): item["pin"]
            for item in terminals
            if item["pin"] and item["signal"]
        },
    }


def sequential_labels(family: SequentialFamily, donor_kind: str) -> tuple[dict[int, str], list[dict[str, object]]]:
    chunk = seq._extract_object_chunk(seq.read_internal_file(family.donor(donor_kind), "ROOT.DSN"))
    single_count = len(seq.bidir_events(seq._extract_object_chunk(seq.read_internal_file(family.donor("single"), "ROOT.DSN"))))
    events = seq.bidir_events(chunk)
    replacements: dict[int, str] = {}
    plan: list[dict[str, object]] = []
    for index, event in enumerate(events):
        chip_index = index // single_count
        pin_index = index % single_count
        parsed = seq.parse_pin_label(str(event["label"]))
        pin = parsed["pin"] or f"X{pin_index:02d}"
        signal = parsed["signal"] or f"P{pin_index:02d}"
        safe_signal = "".join(ch for ch in signal.upper() if ch.isalnum())[:4] or "PIN"
        new = f"U{chip_index + 1}{safe_signal}{pin}"
        replacements[index] = new
        plan.append(
            {
                "terminal_index": index,
                "chip_index": chip_index + 1,
                "old_label": event["label"],
                "new_label": new,
                "signal": signal,
                "pin": pin,
            }
        )
    return replacements, plan


def static_issues(output: Path, family: SequentialFamily, mutations: list[dict[str, object]]) -> list[str]:
    issues: list[str] = []
    info = seq.inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    if chunk.count(family.proteus_device.encode("ascii")) == 0:
        issues.append(f"expected DSN device marker {family.proteus_device} missing")
    if cdb.count(family.proteus_device.encode("ascii")) == 0:
        issues.append(f"expected CDB device marker {family.proteus_device} missing")
    if chunk.count(b"$TERINPUT") or chunk.count(b"$TEROUTPUT"):
        issues.append("sequential IC object chunk should not contain ordinary input/output terminal records")
    if chunk.count(b"$TERBIDIR") == 0:
        issues.append("sequential IC output has no bidirectional terminals")
    if chunk.count(b"VSOURCE") or chunk.count(b"CSOURCE") or chunk.count(b"VSINE"):
        issues.append("unexpected source marker in sequential IC diagnostic")
    for mutation in mutations:
        if chunk.count(str(mutation["new"]).encode("ascii")) == 0:
            issues.append(f"mutated label {mutation['new']} not present")
    return issues


def write_case(
    case_id: str,
    family: SequentialFamily,
    donor_kind: str,
    description: str,
    *,
    exact_repack: bool = False,
    replacements: dict[int, str] | None = None,
    label_plan: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    donor = family.donor(donor_kind)
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    donor_dsn = seq.read_internal_file(donor, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(donor, "ROOT.CDB")
    mutations: list[dict[str, object]] = []
    pointers: dict[str, int] = {}
    if exact_repack:
        seq.write_project_from_parts(
            donor,
            output,
            {
                "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(donor, "PROJECT.XML"), seq.PROTEUS_813),
                "ROOT.DSN": seq.patch_root_dsn_version(donor_dsn, seq.PROTEUS_813),
                "ROOT.CDB": donor_cdb,
            },
        )
        method = "deterministic_exact_donor_repack"
    else:
        registry = seq.FixtureRegistry.load()
        base = registry.get("e001_empty")
        chunk = seq._extract_object_chunk(donor_dsn)
        if replacements:
            chunk, mutations = seq.patch_bidir_labels(chunk, replacements)
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
        method = "whole_donor_object_cdb_device_section_inserted_into_e001"

    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    manifest = {
        "case_id": case_id,
        "description": description,
        "method": method,
        "status": "temporary_pending_user_proteus_testing",
        "family": family.user_name,
        "proteus_device": family.proteus_device,
        "donor_kind": donor_kind,
        "donor": str(donor.relative_to(REPO)),
        "family_notes": family.notes,
        "terminal_policy": "all visible sequential IC pins use $TERBIDIR",
        "section_pointers": pointers,
        "label_plan": label_plan or [],
        "mutations": mutations,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": seq.marker_counts(chunk),
        "cdb_marker_counts": seq.marker_counts(cdb),
        "object_chunk_size": len(chunk),
        "static_validation_issues": static_issues(output, family, mutations),
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
    missing = []
    for family in FAMILIES:
        for kind in ("single", "two", "four", "rlc"):
            try:
                path = family.donor(kind)
            except FileNotFoundError:
                continue
            if not path.exists():
                missing.append(str(path))
    if missing:
        raise FileNotFoundError("\n".join(missing))

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifests: list[dict[str, object]] = []
    pin_maps = [learned_pin_map(family) for family in FAMILIES]
    (OUT_ROOT / "learned_pin_maps.json").write_text(json.dumps(pin_maps, indent=2) + "\n", encoding="utf-8")

    for family in FAMILIES:
        prefix = safe_case_name(family.user_name)
        manifests.append(
            write_case(
                f"T00_{prefix}_SINGLE_EXACT_REPACK",
                family,
                "single",
                "Exact deterministic repack of the user donor.",
                exact_repack=True,
            )
        )
        manifests.append(
            write_case(
                f"T01_{prefix}_SINGLE_E001_TRANSPLANT",
                family,
                "single",
                "Single sequential IC donor object chunk, CDB, and device section inserted into E001 unchanged.",
            )
        )
        replacements, plan = sequential_labels(family, "single")
        manifests.append(
            write_case(
                f"T02_{prefix}_SINGLE_LABEL_MUTATION",
                family,
                "single",
                "Single sequential IC with every bidirectional pin terminal relabelled from learned pin metadata.",
                replacements=replacements,
                label_plan=plan,
            )
        )
        replacements, plan = sequential_labels(family, "two")
        manifests.append(
            write_case(
                f"T03_{prefix}_2X_UNIQUE_LABELS",
                family,
                "two",
                "Two same-family sequential IC packages with unique generated labels per package and pin.",
                replacements=replacements,
                label_plan=plan,
            )
        )
        if family.four:
            replacements, plan = sequential_labels(family, "four")
            manifests.append(
                write_case(
                    f"T04_{prefix}_4X_UNIQUE_LABELS",
                    family,
                    "four",
                    "Four same-family sequential IC packages with unique generated labels per package and pin.",
                    replacements=replacements,
                    label_plan=plan,
                )
            )
        if family.rlc:
            manifests.append(
                write_case(
                    f"T05_{prefix}_{family.rlc_kind.upper()}X_RLC_DONOR_TRANSPLANT",
                    family,
                    "rlc",
                    "RLC donor object chunk, CDB, and device section inserted into E001 unchanged.",
                )
            )

    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_SEQUENTIAL_BATCH3_SOLO_TEMP_2026_06_09",
        "purpose": "Solo donor-learning pack for third sequential IC batch. No mixed-family synthesis.",
        "status": "temporary_pending_user_proteus_testing",
        "terminal_policy": "All visible sequential IC pins use $TERBIDIR. This does not alter locked combinational IC policy.",
        "families": [family.user_name for family in FAMILIES],
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "learned_pin_maps": "learned_pin_maps.json",
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
