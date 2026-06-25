from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_beautifier import _s32_at, layout_coordinate_pairs
from proteusgen.component_placer import (
    MAIN_MEGA_NO_SOURCE_DONOR,
    NEW_COMPONENT_MEGA_DONOR,
    _display_records_from_chunk,
    _display_rows_for_request,
    _cdb_package_set,
    _extract_object_chunk,
    _generation_markers,
    _inspect_donor_counts_for_selection,
    _raw_groups_from_chunk,
    _select_raw_groups,
    generate_component_placement_project,
    read_internal_file,
)


SUPPORTED_FAMILIES = (
    "RESISTOR",
    "CAP",
    "REALIND",
    "CAP-ELEC",
    "DIODE",
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "NPN",
    "PNP",
    "2N3904",
    "2N4401",
    "2N7000",
    "BS170",
    "NMOSFET",
    "FUSE",
    "LED-RED",
    "BRIDGE",
    "TRAN-2P2S",
    "LM317T",
    "OPAMP",
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
    "7SEG-COM-AN-BLUE",
    "7SEG-COM-CAT-BLUE",
    "SWITCH",
    "POT-HG",
)
DEFAULT_COUNTS = (1, 3, 5)
KNOWN_ACCEPTED_LIMITS = {"RESISTOR": 91}
VARIANT_RE = re.compile(r"[^a-z0-9_]+")
MIXED_BASE135_FAMILIES = (
    "REALIND",
    "CAP-ELEC",
    "DIODE",
    "NPN",
    "PNP",
    "FUSE",
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "LED-RED",
    "2N3904",
    "2N4401",
    "2N7000",
    "BS170",
    "NMOSFET",
)
MIXED_NON_IC_FAMILIES = (
    "RESISTOR",
    "CAP",
    "REALIND",
    "CAP-ELEC",
    "DIODE",
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "NPN",
    "PNP",
    "2N3904",
    "2N4401",
    "2N7000",
    "BS170",
    "NMOSFET",
    "FUSE",
    "LED-RED",
    "BRIDGE",
    "TRAN-2P2S",
    "LM317T",
    "OPAMP",
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
    "7SEG-COM-AN-BLUE",
    "7SEG-COM-CAT-BLUE",
    "SWITCH",
    "POT-HG",
)
CONTROL_DUMMY_FAMILIES = {"SWITCH", "POT-HG"}
DISPLAY_FAMILIES = {"7SEG-COM-AN-BLUE", "7SEG-COM-CAT-BLUE"}
REMAINING_NON_IC_SOLO_FAMILIES = (
    "BRIDGE",
    "TRAN-2P2S",
    "LM317T",
    "OPAMP",
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
    "7SEG-COM-AN-BLUE",
    "7SEG-COM-CAT-BLUE",
    "SWITCH",
    "POT-HG",
)
NEW_COMPONENT_DONOR_FAMILIES = {
    "1N4007",
    "1N4148",
    "1N4733A",
    "1N6000B",
    "40EPS08",
    "BZX55C5V1",
    "BZX79C5V1",
    "BZY88C",
    "2N3904",
    "2N4401",
    "2N7000",
    "BS170",
    "NMOSFET",
    "FUSE",
    "LED-RED",
    "BRIDGE",
    "TRAN-2P2S",
    "LM317T",
    "OPAMP",
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
    "7SEG-COM-AN-BLUE",
    "7SEG-COM-CAT-BLUE",
    "SWITCH",
    "POT-HG",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug_family(family: str) -> str:
    return VARIANT_RE.sub("_", family.lower().replace("-", "_")).strip("_")


def donor_for_family(family: str) -> Path:
    if family in NEW_COMPONENT_DONOR_FAMILIES:
        return NEW_COMPONENT_MEGA_DONOR
    return MAIN_MEGA_NO_SOURCE_DONOR


def slug_variant(variant: str | None) -> str:
    if not variant:
        return ""
    slug = VARIANT_RE.sub("_", variant.lower()).strip("_")
    if not slug:
        raise ValueError("variant must contain at least one letter or digit")
    return slug


def case_prefix(family: str) -> str:
    prefixes = {
        "RESISTOR": "R",
        "CAP": "C",
        "CAP-ELEC": "CE",
        "REALIND": "L",
        "DIODE": "D",
        "NPN": "Q",
        "PNP": "QP",
        "FUSE": "FU",
        "LED-RED": "LED",
        "BRIDGE": "BR",
        "TRAN-2P2S": "TR",
        "LM317T": "LM",
        "OPAMP": "OA",
        "VSOURCE": "VS",
        "CSOURCE": "CS",
        "VSINE": "AC",
        "VPULSE": "VP",
        "7SEG-COM-AN-BLUE": "AN",
        "7SEG-COM-CAT-BLUE": "CC",
        "SWITCH": "SW",
        "POT-HG": "RV",
    }
    if family in prefixes:
        return prefixes[family]
    compact = re.sub(r"[^A-Z0-9]+", "", family.upper())
    return compact[:6] or "X"


def build_byte_probe(family: str, donor_path: Path) -> dict[str, Any]:
    coordinate_donor = MAIN_MEGA_NO_SOURCE_DONOR if family in DISPLAY_FAMILIES else donor_path
    chunk = _extract_object_chunk(read_internal_file(ROOT / coordinate_donor, "ROOT.DSN"))
    probe: dict[str, Any] = {
        "donor": str(donor_path),
        "coordinate_authority": str(coordinate_donor),
        "purpose": (
            "Reusable family coordinate probe. Records parsed coordinate fields "
            "used by beautifier visible-packet translation."
        ),
        "rejected_v1_fixed_offsets": ["12/16", "22/26", "91/95", "168/172", "254/258"],
    }
    if family in DISPLAY_FAMILIES:
        display_groups, display_notes = _display_rows_for_request(
            _display_records_from_chunk(chunk),
            {family: 1},
        )
        group = display_groups[0]
        probe["display_notes"] = list(display_notes)
    else:
        groups = _raw_groups_from_chunk(chunk, _generation_markers())
        cdb_refs = _cdb_package_set(read_internal_file(ROOT / coordinate_donor, "ROOT.CDB"))
        selected, hidden = _select_raw_groups(
            groups,
            cdb_refs,
            {family: 1},
            control_strategy="hidden_dummy_control",
            hidden_coordinate_mode="none",
        )
        hidden_ids = {id(item) for item in hidden}
        group = next(item for item in selected if id(item) not in hidden_ids)
    pairs = []
    for x_offset, y_offset, reason in layout_coordinate_pairs(group.data, family):
        pairs.append(
            {
                "x_offset": x_offset,
                "y_offset": y_offset,
                "x_value": _s32_at(group.data, x_offset),
                "y_value": _s32_at(group.data, y_offset),
                "reason": reason,
            }
        )
    probe[family] = {
        "first_group_key": group.key,
        "packet_size": len(group.data),
        "parsed_coordinate_pairs": pairs,
    }
    return probe


def write_case_note(case_dir: Path, case: dict[str, Any], output_path: Path, manifest_path: Path | None) -> None:
    payload = {
        "schema": "component-placement/v0.1",
        "components": case["components"],
        "layout": case["layout"],
    }
    lines = [
        f"# {case['name']}",
        "",
        "## Purpose",
        "",
        case["purpose"],
        "This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.",
        "",
        "## Input",
        "",
        "```json",
        json.dumps(payload, indent=2, sort_keys=True),
        "```",
        "",
        "## Output",
        "",
        f"- Project: `{output_path.name}`",
        f"- Manifest: `{manifest_path.name if manifest_path else output_path.name + '.manifest.json'}`",
        "",
        "## What To Check In Proteus",
        "",
        case["what_to_check"],
        "",
        "## User Result",
        "",
        "Pending.",
        "",
        "## Codex Observation",
        "",
        "Pending user Proteus result.",
        "",
    ]
    (case_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def write_root_readme(
    out_dir: Path,
    *,
    family: str,
    variant: str,
    records: list[dict[str, Any]],
    byte_probe: dict[str, Any],
    donor_path: Path,
    donor_inventory_count: int,
    accepted_limit: int | None,
    run_date: str,
) -> None:
    pairs = byte_probe[family]["parsed_coordinate_pairs"]
    lines = [
        f"# Beautifier {family} Coordinate Probe",
        "",
        f"Generated on {run_date}.",
        "",
        "This pack uses the reusable passive-family beautifier probe harness.",
        "It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.",
        "",
        "## Family",
        "",
        f"- Family under test: `{family}`",
        f"- Donor: `{donor_path}`",
        f"- Donor inventory count: `{donor_inventory_count}`",
    ]
    if variant:
        lines.append(f"- Probe variant: `{variant}`")
    if accepted_limit is not None:
        lines.append(f"- Accepted test limit used here: `{accepted_limit}`")
    lines.extend(["", "## Parsed Coordinates Under Test", ""])
    for pair in pairs:
        lines.append(
            f"- `{pair['x_offset']}/{pair['y_offset']}` -> "
            f"({pair['x_value']}, {pair['y_value']}), `{pair['reason']}`"
        )
    lines.extend(["", "## Test Files", ""])
    for record in records:
        lines.append(f"- `{record['case_folder']}/{record['output_name']}`: {record['what_to_check']}")
    lines.extend(
        [
            "",
            "## User Results",
            "",
            "Pending.",
            "",
            "## What Success Means",
            "",
            f"If every `{family}` case opens without DLL errors and labels/values stay attached,",
            f"coordinate beautification for `{family}` is accepted for these counts.",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def parse_counts(raw: str) -> tuple[int, ...]:
    counts: list[int] = []
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        count = int(piece)
        if count <= 0:
            raise ValueError("counts must be positive")
        counts.append(count)
    if not counts:
        raise ValueError("at least one count is required")
    return tuple(counts)


def _mutation_layout(family: str, *, hide_display_bridge: bool = True) -> dict[str, Any]:
    layout: dict[str, Any] = {
        "strategy": "beautify",
        "binary_coordinate_mutation": True,
    }
    if family in CONTROL_DUMMY_FAMILIES:
        layout.update(
            {
                "move_visible_controls": True,
                "hidden_coordinate_mode": "none",
            }
        )
    if family in DISPLAY_FAMILIES:
        layout.update(
            {
                "hide_display_bridge": hide_display_bridge,
                "display_bridge_coordinate_mode": "display_small_relative",
            }
        )
    return layout


def build_cases(family: str, counts: tuple[int, ...]) -> list[dict[str, Any]]:
    prefix = case_prefix(family)
    cases: list[dict[str, Any]] = [
        {
            "name": f"{prefix}00_1X_BASELINE",
            "components": {family: 1},
            "layout": {"strategy": "legacy", "binary_coordinate_mutation": False},
            "purpose": f"Baseline donor-selected `{family}` placement before coordinate mutation.",
            "what_to_check": f"Baseline control. One `{family}` should open in the original donor-selected position.",
        }
    ]
    if family in DISPLAY_FAMILIES:
        cases.append(
            {
                "name": f"{prefix}01_1X_MOVE_D20_STATIC",
                "components": {family: 1},
                "layout": _mutation_layout(family, hide_display_bridge=False),
                "purpose": f"Isolate `{family}` row-coordinate mutation while leaving D20 unchanged.",
                "what_to_check": (
                    f"One `{family}` should move onto the grid and remain intact. "
                    "D20 should stay in its donor position. This separates display movement from D20 movement."
                ),
            }
        )
    for index, count in enumerate(counts, start=1):
        case_number = index + (1 if family in DISPLAY_FAMILIES else 0)
        special_note = ""
        if family in DISPLAY_FAMILIES:
            special_note = " D20 should move separately and must not count as a requested diode."
        elif family in CONTROL_DUMMY_FAMILIES:
            special_note = (
                " The requested visible controls should move as complete linked packets; "
                "the extra dummy control remains excluded from the user count."
            )
        cases.append(
            {
                "name": f"{prefix}{case_number:02d}_{count}X_COORDS",
                "components": {family: count},
                "layout": _mutation_layout(family),
                "purpose": f"Focused `{family}` parsed-coordinate beautifier probe.",
                "what_to_check": (
                    f"{count} `{family}` components should move onto the beautifier grid. "
                    "Check for DLL errors, bad object records, detached labels/values, or damaged controls."
                    + special_note
                ),
            }
        )
    return cases


def generate_family_probe(
    family: str,
    counts: tuple[int, ...],
    *,
    accepted_limit: int | None = None,
    variant: str | None = None,
    run_date: str = "2026-06-24",
) -> dict[str, Any]:
    if family not in SUPPORTED_FAMILIES:
        raise ValueError(f"Unsupported family {family!r}; expected one of {', '.join(SUPPORTED_FAMILIES)}")

    donor_path = donor_for_family(family)
    donor_counts = _inspect_donor_counts_for_selection(ROOT / donor_path, _generation_markers())
    donor_inventory_count = int(donor_counts.get(family, 0))
    max_requested = max((1, *counts, accepted_limit or 1))
    if donor_inventory_count < max_requested:
        raise RuntimeError(
            f"Requested {max_requested} {family} packets, but donor only exposes {donor_inventory_count}."
        )

    slug = slug_family(family)
    variant_slug = slug_variant(variant)
    run_date_slug = run_date.replace("-", "_")
    variant_part = f"_{variant_slug}" if variant_slug else ""
    archive_variant_part = f"_{variant_slug.upper()}" if variant_slug else ""
    out_dir = ROOT / "experiments" / f"beautifier_{slug}_coordinate_probe{variant_part}_v1_temp_{run_date_slug}"
    archive = (
        ROOT
        / "experiments"
        / f"BEAUTIFIER_{family.replace('-', '_')}_COORDINATE_PROBE{archive_variant_part}_V1_TEMP_{run_date_slug}.zip"
    )
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    byte_probe = build_byte_probe(family, donor_path)
    (out_dir / "byte_probe.json").write_text(json.dumps(byte_probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cases = build_cases(family, counts)
    if accepted_limit is not None and accepted_limit not in counts:
        cases.append(
            {
                "name": f"{case_prefix(family)}{len(cases):02d}_{accepted_limit}X_LIMIT_COORDS",
                "components": {family: accepted_limit},
                "layout": _mutation_layout(family),
                "purpose": f"Accepted-limit `{family}` parsed-coordinate beautifier probe.",
                "what_to_check": (
                    f"{accepted_limit} `{family}` components should open on the beautifier grid. "
                    "Check for DLL errors and detached labels/values."
                ),
            }
        )

    records: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        case_dir = out_dir / f"{index:02d}_{case['name']}"
        case_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "component-placement/v0.1",
            "components": case["components"],
            "layout": case["layout"],
        }
        (case_dir / "payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_path = case_dir / f"{case['name']}.pdsprj"
        result = generate_component_placement_project(
            payload,
            output_path,
            donor_path=donor_path,
            full_cdb=True,
        )
        write_case_note(case_dir, case, output_path, result.manifest_path)
        records.append(
            {
                "case": case["name"],
                "case_folder": case_dir.name,
                "components": case["components"],
                "layout": case["layout"],
                "output": str(output_path.relative_to(ROOT)),
                "output_name": output_path.name,
                "manifest": str(result.manifest_path.relative_to(ROOT)),
                "valid": result.valid,
                "errors": [issue.as_dict() for issue in result.errors],
                "what_to_check": case["what_to_check"],
            }
        )

    summary = {
        "test_id": f"BEAUTIFIER_{family.replace('-', '_')}_COORDINATE_PROBE{archive_variant_part}_V1_TEMP_{run_date_slug}",
        "family": family,
        "variant": variant_slug,
        "case_count": len(records),
        "counts": list(counts),
        "accepted_limit": accepted_limit,
        "donor_inventory_count": donor_inventory_count,
        "records": records,
        "byte_probe": "byte_probe.json",
        "policy": {
            "actual_generator": "proteusgen.component_placer.generate_component_placement_project",
            "explicit_donor": str(donor_path),
            "full_cdb": True,
            "script": "tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py",
            "reuses_parsed_coordinate_method": True,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_root_readme(
        out_dir,
        family=family,
        variant=variant_slug,
        records=records,
        byte_probe=byte_probe,
        donor_path=donor_path,
        donor_inventory_count=donor_inventory_count,
        accepted_limit=accepted_limit,
        run_date=run_date,
    )
    if archive.exists():
        archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip", out_dir)
    summary["archive"] = str(archive.relative_to(ROOT))
    summary["archive_sha256"] = sha256(archive)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "family": family,
        "variant": variant_slug,
        "out_dir": str(out_dir),
        "archive": str(archive),
        "archive_sha256": summary["archive_sha256"],
        "case_count": len(records),
        "donor_inventory_count": donor_inventory_count,
        "accepted_limit": accepted_limit,
    }


def write_mixed_case_note(case_dir: Path, case: dict[str, Any], output_path: Path, manifest_path: Path | None) -> None:
    payload = {
        "schema": "component-placement/v0.1",
        "components": case["components"],
        "layout": case["layout"],
    }
    lines = [
        f"# {case['name']}",
        "",
        "## Purpose",
        "",
        case["purpose"],
        "This case uses the normal component placer plus the shared parsed-coordinate beautifier.",
        "",
        "## Input",
        "",
        "```json",
        json.dumps(payload, indent=2, sort_keys=True),
        "```",
        "",
        "## Output",
        "",
        f"- Project: `{output_path.name}`",
        f"- Manifest: `{manifest_path.name if manifest_path else output_path.name + '.manifest.json'}`",
        "",
        "## What To Check In Proteus",
        "",
        case["what_to_check"],
        "",
        "## User Result",
        "",
        "Pending.",
        "",
        "## Codex Observation",
        "",
        "Pending user Proteus result.",
        "",
    ]
    (case_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


def generate_mixed_base135_batch(counts: tuple[int, ...], *, variant: str | None = None) -> dict[str, Any]:
    donor_path = NEW_COMPONENT_MEGA_DONOR
    donor_counts = _inspect_donor_counts_for_selection(ROOT / donor_path, _generation_markers())
    variant_slug = slug_variant(variant)
    variant_part = f"_{variant_slug}" if variant_slug else ""
    archive_variant_part = f"_{variant_slug.upper()}" if variant_slug else ""
    out_dir = ROOT / "experiments" / f"beautifier_mixed_base135{variant_part}_v1_temp_2026_06_24"
    archive = ROOT / "experiments" / (
        f"BEAUTIFIER_MIXED_BASE135{archive_variant_part}_V1_TEMP_2026_06_24.zip"
    )
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = {family: int(donor_counts.get(family, 0)) for family in MIXED_BASE135_FAMILIES}
    missing = [family for family, available in inventory.items() if available <= 0]
    if missing:
        raise RuntimeError(f"Selected mixed donor is missing required families: {', '.join(missing)}")

    records: list[dict[str, Any]] = []
    for index, requested_count in enumerate(counts, start=1):
        effective_components: dict[str, int] = {}
        caps: dict[str, dict[str, int]] = {}
        for family in MIXED_BASE135_FAMILIES:
            available = inventory[family]
            effective_count = min(requested_count, available)
            effective_components[family] = effective_count
            if effective_count != requested_count:
                caps[family] = {"requested": requested_count, "used": effective_count, "available": available}

        case = {
            "name": f"MIX{requested_count:02d}X_ALL_BASE135",
            "components": effective_components,
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
            "purpose": (
                f"Mixed-family stress case requesting {requested_count} of every component family "
                "accepted in the 2026-06-24 base135 beautifier tests."
            ),
            "what_to_check": (
                f"All listed families should appear together, arranged by the beautifier grid. "
                f"Requested count per family: {requested_count}. "
                "Check for open crashes, DLL errors, bad object records, and detached labels/values."
            ),
        }
        case_dir = out_dir / f"{index:02d}_MIX_{requested_count:02d}X"
        case_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "component-placement/v0.1",
            "components": case["components"],
            "layout": case["layout"],
        }
        (case_dir / "payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_path = case_dir / f"{case['name']}.pdsprj"
        result = generate_component_placement_project(
            payload,
            output_path,
            donor_path=donor_path,
            full_cdb=True,
        )
        write_mixed_case_note(case_dir, case, output_path, result.manifest_path)
        total_components = sum(effective_components.values())
        records.append(
            {
                "case": case["name"],
                "case_folder": case_dir.name,
                "requested_each": requested_count,
                "components": effective_components,
                "caps": caps,
                "total_components": total_components,
                "layout": case["layout"],
                "output": str(output_path.relative_to(ROOT)),
                "output_name": output_path.name,
                "manifest": str(result.manifest_path.relative_to(ROOT)),
                "valid": result.valid,
                "errors": [issue.as_dict() for issue in result.errors],
                "what_to_check": case["what_to_check"],
            }
        )

    lines = [
        "# Beautifier Mixed Component Family Counts",
        "",
        "Generated on 2026-06-24.",
        "",
        "This pack combines every family that passed the 2026-06-24 base135 component-family tests.",
        "It uses the actual component placer plus the shared parsed-coordinate beautifier path.",
        "",
        "## Donor",
        "",
        f"- `{donor_path}`",
        "",
        "## Families",
        "",
    ]
    for family in MIXED_BASE135_FAMILIES:
        lines.append(f"- `{family}`: donor inventory `{inventory[family]}`")
    lines.extend(["", "## Cases", ""])
    for record in records:
        cap_note = ""
        if record["caps"]:
            cap_note = f" capped: `{json.dumps(record['caps'], sort_keys=True)}`"
        lines.append(
            f"- `{record['case_folder']}/{record['output_name']}`: "
            f"{record['requested_each']} each, total `{record['total_components']}`.{cap_note}"
        )
    lines.extend(
        [
            "",
            "## User Results",
            "",
            "Pending.",
            "",
            "## Codex Observation",
            "",
            "Static generation and manifest validation pending in this run.",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    summary = {
        "test_id": f"BEAUTIFIER_COMPONENT_FAMILY_MIXED_COUNTS{archive_variant_part}_V1_TEMP_2026_06_24",
        "variant": variant_slug,
        "donor": str(donor_path),
        "families": list(MIXED_BASE135_FAMILIES),
        "inventory": inventory,
        "counts": list(counts),
        "records": records,
        "policy": {
            "actual_generator": "proteusgen.component_placer.generate_component_placement_project",
            "explicit_donor": str(donor_path),
            "full_cdb": True,
            "script": "tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py",
            "reuses_parsed_coordinate_method": True,
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if archive.exists():
        archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip", out_dir)
    summary["archive"] = str(archive.relative_to(ROOT))
    summary["archive_sha256"] = sha256(archive)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "out_dir": str(out_dir),
        "archive": str(archive),
        "archive_sha256": summary["archive_sha256"],
        "case_count": len(records),
        "families": list(MIXED_BASE135_FAMILIES),
        "counts": list(counts),
    }


def _effective_count_for_family(family: str, requested_count: int, available: int) -> tuple[int, dict[str, int] | None]:
    usable = available
    if family in CONTROL_DUMMY_FAMILIES:
        usable = max(0, available - 1)
    if family == "BRIDGE" and requested_count > 7:
        # The accepted BRIDGE selector skips the early fragile bridge packets for larger counts.
        usable = max(0, available - 14)
    effective = min(requested_count, usable)
    if effective != requested_count:
        return effective, {"requested": requested_count, "used": effective, "available": available, "usable": usable}
    return effective, None


def generate_mixed_non_ic_batch(counts: tuple[int, ...], *, variant: str | None = None) -> dict[str, Any]:
    donor_path = NEW_COMPONENT_MEGA_DONOR
    donor_counts = _inspect_donor_counts_for_selection(ROOT / donor_path, _generation_markers())
    variant_slug = slug_variant(variant)
    variant_part = f"_{variant_slug}" if variant_slug else ""
    archive_variant_part = f"_{variant_slug.upper()}" if variant_slug else ""
    out_dir = ROOT / "experiments" / f"beautifier_mixed_non_ic{variant_part}_v1_temp_2026_06_24"
    archive = ROOT / "experiments" / (
        f"BEAUTIFIER_MIXED_NON_IC{archive_variant_part}_V1_TEMP_2026_06_24.zip"
    )
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    inventory = {family: int(donor_counts.get(family, 0)) for family in MIXED_NON_IC_FAMILIES}
    missing = [family for family, available in inventory.items() if available <= 0]
    if missing:
        raise RuntimeError(f"Selected non-IC donor is missing required families: {', '.join(missing)}")

    records: list[dict[str, Any]] = []
    for index, requested_count in enumerate(counts, start=1):
        effective_components: dict[str, int] = {}
        caps: dict[str, dict[str, int]] = {}
        for family in MIXED_NON_IC_FAMILIES:
            effective_count, cap = _effective_count_for_family(family, requested_count, inventory[family])
            effective_components[family] = effective_count
            if cap:
                caps[family] = cap

        layout = {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
            "hide_display_bridge": True,
            "display_bridge_coordinate_mode": "display_small_relative",
            "hidden_coordinate_mode": "linked_relative",
        }
        case = {
            "name": f"NIC{requested_count:02d}X_ALL_NON_IC",
            "components": effective_components,
            "layout": layout,
            "purpose": (
                f"Non-IC stress case requesting {requested_count} of every non-IC component family "
                "currently exercised by the component placer."
            ),
            "what_to_check": (
                f"Requested count per family: {requested_count}. Displays should appear without counting "
                "the internal D20 bridge as a user diode. SWITCH and POT-HG should each have the requested "
                "visible count, with the internal dummy control moved by the layout/beautifier stage. "
                "Check for open crashes, DLL errors, bad object records, missing controls, and detached labels."
            ),
        }
        case_dir = out_dir / f"{index:02d}_NIC_{requested_count:02d}X"
        case_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "component-placement/v0.1",
            "components": case["components"],
            "layout": case["layout"],
        }
        (case_dir / "payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_path = case_dir / f"{case['name']}.pdsprj"
        result = generate_component_placement_project(
            payload,
            output_path,
            donor_path=donor_path,
            full_cdb=True,
        )
        write_mixed_case_note(case_dir, case, output_path, result.manifest_path)
        total_user_components = sum(effective_components.values())
        records.append(
            {
                "case": case["name"],
                "case_folder": case_dir.name,
                "requested_each": requested_count,
                "components": effective_components,
                "caps": caps,
                "total_user_components": total_user_components,
                "layout": case["layout"],
                "output": str(output_path.relative_to(ROOT)),
                "output_name": output_path.name,
                "manifest": str(result.manifest_path.relative_to(ROOT)),
                "valid": result.valid,
                "errors": [issue.as_dict() for issue in result.errors],
                "what_to_check": case["what_to_check"],
            }
        )

    lines = [
        "# Beautifier Mixed Non-IC Counts",
        "",
        "Generated on 2026-06-24.",
        "",
        "This pack combines all current non-IC component-placer families from the new-component mega donor.",
        "It includes sources, displays, controls, transformer/bridge/regulator/opamp, and the accepted passive/discrete families.",
        "",
        "## Donor",
        "",
        f"- `{donor_path}`",
        "",
        "## Special Rules Under Test",
        "",
        "- `7SEG-COM-AN-BLUE` and `7SEG-COM-CAT-BLUE` automatically carry the internal `D20` display bridge.",
        "- `D20` is not included in the requested `DIODE` count.",
        "- `hide_display_bridge=true` moves the `D20` bridge by the display-small relative beautifier mode.",
        "- `SWITCH` and `POT-HG` request one extra internal dummy packet; the dummy does not count as a user component.",
        "- `hidden_coordinate_mode=linked_relative` is used for the internal control dummy packets.",
        "",
        "## Families",
        "",
    ]
    for family in MIXED_NON_IC_FAMILIES:
        extra = ""
        if family in CONTROL_DUMMY_FAMILIES:
            extra = " (needs one extra dummy packet internally)"
        lines.append(f"- `{family}`: donor inventory `{inventory[family]}`{extra}")
    lines.extend(["", "## Cases", ""])
    for record in records:
        cap_note = ""
        if record["caps"]:
            cap_note = f" capped: `{json.dumps(record['caps'], sort_keys=True)}`"
        lines.append(
            f"- `{record['case_folder']}/{record['output_name']}`: "
            f"{record['requested_each']} each, user-visible total `{record['total_user_components']}`.{cap_note}"
        )
    lines.extend(
        [
            "",
            "## User Results",
            "",
            "Pending.",
            "",
            "## Codex Observation",
            "",
            "Static generation and manifest validation pending in this run.",
            "",
        ]
    )
    (out_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    summary = {
        "test_id": f"BEAUTIFIER_MIXED_NON_IC{archive_variant_part}_V1_TEMP_2026_06_24",
        "variant": variant_slug,
        "donor": str(donor_path),
        "families": list(MIXED_NON_IC_FAMILIES),
        "inventory": inventory,
        "counts": list(counts),
        "records": records,
        "policy": {
            "actual_generator": "proteusgen.component_placer.generate_component_placement_project",
            "explicit_donor": str(donor_path),
            "full_cdb": True,
            "script": "tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py",
            "hide_display_bridge": True,
            "display_bridge_coordinate_mode": "display_small_relative",
            "hidden_control_dummy_mode": "linked_relative",
        },
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if archive.exists():
        archive.unlink()
    shutil.make_archive(str(archive.with_suffix("")), "zip", out_dir)
    summary["archive"] = str(archive.relative_to(ROOT))
    summary["archive_sha256"] = sha256(archive)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "out_dir": str(out_dir),
        "archive": str(archive),
        "archive_sha256": summary["archive_sha256"],
        "case_count": len(records),
        "families": list(MIXED_NON_IC_FAMILIES),
        "counts": list(counts),
    }


def generate_remaining_non_ic_solo_batch(counts: tuple[int, ...], *, run_date: str) -> dict[str, Any]:
    run_date_slug = run_date.replace("-", "_")
    batch_dir = ROOT / "experiments" / f"beautifier_remaining_non_ic_solo_batch_v1_temp_{run_date_slug}"
    batch_archive = ROOT / "experiments" / f"BEAUTIFIER_REMAINING_NON_IC_SOLO_BATCH_V1_TEMP_{run_date_slug}.zip"
    if batch_dir.exists():
        shutil.rmtree(batch_dir)
    batch_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for family in REMAINING_NON_IC_SOLO_FAMILIES:
        result = generate_family_probe(
            family,
            counts,
            variant="solo",
            run_date=run_date,
        )
        archive = Path(result["archive"])
        shutil.copy2(archive, batch_dir / archive.name)
        results.append(result)

    lines = [
        "# Remaining Non-IC Solo Beautifier Batch",
        "",
        f"Generated on {run_date}.",
        "",
        "This folder is intentionally not an index-only folder. It contains all twelve family ZIP archives.",
        "Test one family at a time. Do not combine families until these coordinate mutations pass in Proteus.",
        "",
        "## Root Cause Being Tested",
        "",
        "The rejected mixed non-IC pack allowed unproven families to use the broad coordinate scanner.",
        "These solo packs instead use family-specific parsed or linked coordinate fields.",
        "",
        "## Test Order",
        "",
    ]
    for index, result in enumerate(results, start=1):
        family = result["family"]
        extra = ""
        if family in DISPLAY_FAMILIES:
            extra = " Display pack also isolates display movement with D20 unchanged before moving D20 separately."
        elif family in CONTROL_DUMMY_FAMILIES:
            extra = " Check that every visible control remains interactive; one internal dummy is excluded from the user count."
        lines.append(f"{index}. `{Path(result['archive']).name}` - `{family}`.{extra}")
    lines.extend(
        [
            "",
            "## Cases Inside Each Family ZIP",
            "",
            "- `00`: unchanged donor-position baseline",
            "- `01`: one component with family-specific coordinate mutation",
            "- next cases: 3, 15, and 25 components with the same mutation path",
            "- display packs include an additional one-display D20-unchanged isolation case",
            "",
            "## Report",
            "",
            "For each family, report the first failing case and whether the failure is:",
            "",
            "- crash before open",
            "- DLL error",
            "- bad object record",
            "- detached label/value",
            "- wrong count",
            "- damaged SWITCH/POT-HG controls",
            "- incorrect D20/display placement",
            "",
        ]
    )
    (batch_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")
    summary = {
        "test_id": f"BEAUTIFIER_REMAINING_NON_IC_SOLO_BATCH_V1_TEMP_{run_date_slug}",
        "run_date": run_date,
        "families": list(REMAINING_NON_IC_SOLO_FAMILIES),
        "counts": list(counts),
        "results": results,
        "policy": {
            "single_reusable_harness": "tools/proteus_generation/2026-06-24/generate_beautifier_passive_family_probe_temp.py",
            "no_mixed_family_generation": True,
            "family_specific_coordinate_parsing": True,
        },
    }
    (batch_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if batch_archive.exists():
        batch_archive.unlink()
    shutil.make_archive(str(batch_archive.with_suffix("")), "zip", batch_dir)
    summary["archive"] = str(batch_archive.relative_to(ROOT))
    summary["archive_sha256"] = sha256(batch_archive)
    (batch_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "out_dir": str(batch_dir),
        "archive": str(batch_archive),
        "archive_sha256": summary["archive_sha256"],
        "families": list(REMAINING_NON_IC_SOLO_FAMILIES),
        "counts": list(counts),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reusable passive-family beautifier coordinate probes.")
    parser.add_argument("--family", choices=SUPPORTED_FAMILIES)
    parser.add_argument(
        "--mixed-base135",
        action="store_true",
        help="Generate mixed 2026-06-24 accepted base135 families in one project per count.",
    )
    parser.add_argument(
        "--mixed-non-ic",
        action="store_true",
        help="Generate all current non-IC component-placer families in one project per count.",
    )
    parser.add_argument(
        "--remaining-non-ic-solo",
        action="store_true",
        help="Generate and bundle solo coordinate probes for every remaining non-IC family.",
    )
    parser.add_argument("--counts", default=",".join(str(count) for count in DEFAULT_COUNTS))
    parser.add_argument("--accepted-limit", type=int, default=None)
    parser.add_argument("--variant", default="", help="Optional output-name suffix, e.g. stress100.")
    parser.add_argument("--run-date", default="2026-06-24", help="Output date in YYYY-MM-DD form.")
    args = parser.parse_args()

    if args.mixed_base135:
        result = generate_mixed_base135_batch(parse_counts(args.counts), variant=args.variant)
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if args.mixed_non_ic:
        result = generate_mixed_non_ic_batch(parse_counts(args.counts), variant=args.variant)
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    if args.remaining_non_ic_solo:
        result = generate_remaining_non_ic_solo_batch(parse_counts(args.counts), run_date=args.run_date)
        print(json.dumps(result, indent=2, sort_keys=True))
        return

    if not args.family:
        parser.error(
            "--family is required unless --mixed-base135, --mixed-non-ic, "
            "or --remaining-non-ic-solo is used"
        )

    accepted_limit = args.accepted_limit
    if accepted_limit is None and args.family in KNOWN_ACCEPTED_LIMITS:
        accepted_limit = KNOWN_ACCEPTED_LIMITS[args.family]

    result = generate_family_probe(
        args.family,
        parse_counts(args.counts),
        accepted_limit=accepted_limit,
        variant=args.variant,
        run_date=args.run_date,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
