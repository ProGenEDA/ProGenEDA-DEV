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
    _extract_object_chunk,
    _generation_markers,
    _inspect_donor_counts_for_selection,
    _raw_groups_from_chunk,
    generate_component_placement_project,
    read_internal_file,
)


SUPPORTED_FAMILIES = ("RESISTOR", "CAP", "REALIND", "CAP-ELEC", "DIODE")
DEFAULT_COUNTS = (1, 3, 5)
KNOWN_ACCEPTED_LIMITS = {"RESISTOR": 91}
VARIANT_RE = re.compile(r"[^a-z0-9_]+")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def slug_family(family: str) -> str:
    return family.lower().replace("-", "_")


def slug_variant(variant: str | None) -> str:
    if not variant:
        return ""
    slug = VARIANT_RE.sub("_", variant.lower()).strip("_")
    if not slug:
        raise ValueError("variant must contain at least one letter or digit")
    return slug


def case_prefix(family: str) -> str:
    return {
        "RESISTOR": "R",
        "CAP": "C",
        "CAP-ELEC": "CE",
        "REALIND": "L",
        "DIODE": "D",
    }[family]


def build_byte_probe() -> dict[str, Any]:
    chunk = _extract_object_chunk(read_internal_file(ROOT / MAIN_MEGA_NO_SOURCE_DONOR, "ROOT.DSN"))
    groups = _raw_groups_from_chunk(chunk, _generation_markers())
    probe: dict[str, Any] = {
        "donor": str(MAIN_MEGA_NO_SOURCE_DONOR),
        "purpose": (
            "Reusable passive-family coordinate probe. Records parsed coordinate fields "
            "used by beautifier visible-packet translation."
        ),
        "rejected_v1_fixed_offsets": ["12/16", "22/26", "91/95", "168/172", "254/258"],
    }
    for family in SUPPORTED_FAMILIES:
        group = groups[family][0]
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
    donor_inventory_count: int,
    accepted_limit: int | None,
) -> None:
    pairs = byte_probe[family]["parsed_coordinate_pairs"]
    lines = [
        f"# Beautifier {family} Coordinate Probe",
        "",
        "Generated on 2026-06-24.",
        "",
        "This pack uses the reusable passive-family beautifier probe harness.",
        "It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.",
        "",
        "## Family",
        "",
        f"- Family under test: `{family}`",
        f"- Donor: `{MAIN_MEGA_NO_SOURCE_DONOR}`",
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


def build_cases(family: str, counts: tuple[int, ...]) -> list[dict[str, Any]]:
    prefix = case_prefix(family)
    cases: list[dict[str, Any]] = [
        {
            "name": f"{prefix}00_{family}_1X_BASELINE_NO_BEAUTIFY",
            "components": {family: 1},
            "layout": {"strategy": "legacy", "binary_coordinate_mutation": False},
            "purpose": f"Baseline donor-selected `{family}` placement before coordinate mutation.",
            "what_to_check": f"Baseline control. One `{family}` should open in the original donor-selected position.",
        }
    ]
    for index, count in enumerate(counts, start=1):
        cases.append(
            {
                "name": f"{prefix}{index:02d}_{family}_{count}X_PARSED_COORDS",
                "components": {family: count},
                "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
                "purpose": f"Focused `{family}` parsed-coordinate beautifier probe.",
                "what_to_check": (
                    f"{count} `{family}` components should move onto the beautifier grid. "
                    "Check for DLL errors, bad object records, and detached labels/values."
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
) -> dict[str, Any]:
    if family not in SUPPORTED_FAMILIES:
        raise ValueError(f"Unsupported family {family!r}; expected one of {', '.join(SUPPORTED_FAMILIES)}")

    donor_counts = _inspect_donor_counts_for_selection(ROOT / MAIN_MEGA_NO_SOURCE_DONOR, _generation_markers())
    donor_inventory_count = int(donor_counts.get(family, 0))
    max_requested = max((1, *counts, accepted_limit or 1))
    if donor_inventory_count < max_requested:
        raise RuntimeError(
            f"Requested {max_requested} {family} packets, but donor only exposes {donor_inventory_count}."
        )

    slug = slug_family(family)
    variant_slug = slug_variant(variant)
    variant_part = f"_{variant_slug}" if variant_slug else ""
    archive_variant_part = f"_{variant_slug.upper()}" if variant_slug else ""
    out_dir = ROOT / "experiments" / f"beautifier_{slug}_coordinate_probe{variant_part}_v1_temp_2026_06_24"
    archive = (
        ROOT
        / "experiments"
        / f"BEAUTIFIER_{family.replace('-', '_')}_COORDINATE_PROBE{archive_variant_part}_V1_TEMP_2026_06_24.zip"
    )
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    byte_probe = build_byte_probe()
    (out_dir / "byte_probe.json").write_text(json.dumps(byte_probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cases = build_cases(family, counts)
    if accepted_limit is not None and accepted_limit not in counts:
        cases.append(
            {
                "name": f"{case_prefix(family)}{len(cases):02d}_{family}_{accepted_limit}X_ACCEPTED_LIMIT_PARSED_COORDS",
                "components": {family: accepted_limit},
                "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
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
            donor_path=MAIN_MEGA_NO_SOURCE_DONOR,
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
        "test_id": f"BEAUTIFIER_{family.replace('-', '_')}_COORDINATE_PROBE{archive_variant_part}_V1_TEMP_2026_06_24",
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
            "explicit_donor": str(MAIN_MEGA_NO_SOURCE_DONOR),
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
        donor_inventory_count=donor_inventory_count,
        accepted_limit=accepted_limit,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reusable passive-family beautifier coordinate probes.")
    parser.add_argument("--family", required=True, choices=SUPPORTED_FAMILIES)
    parser.add_argument("--counts", default=",".join(str(count) for count in DEFAULT_COUNTS))
    parser.add_argument("--accepted-limit", type=int, default=None)
    parser.add_argument("--variant", default="", help="Optional output-name suffix, e.g. stress100.")
    args = parser.parse_args()

    accepted_limit = args.accepted_limit
    if accepted_limit is None and args.family in KNOWN_ACCEPTED_LIMITS:
        accepted_limit = KNOWN_ACCEPTED_LIMITS[args.family]

    result = generate_family_probe(
        args.family,
        parse_counts(args.counts),
        accepted_limit=accepted_limit,
        variant=args.variant,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
