from __future__ import annotations

import hashlib
import json
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
    _raw_groups_from_chunk,
    generate_component_placement_project,
    read_internal_file,
)


OUT_DIR = ROOT / "experiments" / "beautifier_resistor_coordinate_probe_v2_temp_2026_06_24"
ARCHIVE = ROOT / "experiments" / "BEAUTIFIER_RESISTOR_COORDINATE_PROBE_V2_TEMP_2026_06_24.zip"


CASES: list[dict[str, Any]] = [
    {
        "name": "R00_RESISTOR_1X_BASELINE_NO_BEAUTIFY",
        "components": {"RESISTOR": 1},
        "layout": {"strategy": "legacy", "binary_coordinate_mutation": False},
        "what_to_check": (
            "Baseline control. One resistor should open in the original donor-selected position. "
            "This proves the placer/donor path is still sound before coordinate mutation."
        ),
    },
    {
        "name": "R01_RESISTOR_1X_PARSED_COORDS",
        "components": {"RESISTOR": 1},
        "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        "what_to_check": (
            "One resistor should move to the beautifier grid. Ref text, value text, model text, "
            "property text, and symbol body should stay together. No LXLCORE.dll."
        ),
    },
    {
        "name": "R02_RESISTOR_3X_PARSED_COORDS",
        "components": {"RESISTOR": 3},
        "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        "what_to_check": (
            "Three resistors should be separated on one row. This checks repeated parsed-coordinate "
            "movement without touching the old fixed offsets."
        ),
    },
    {
        "name": "R03_RESISTOR_5X_PARSED_COORDS",
        "components": {"RESISTOR": 5},
        "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        "what_to_check": (
            "Five resistors should be separated on the grid, with all visible labels still attached "
            "to their matching resistor bodies."
        ),
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_byte_probe() -> dict[str, Any]:
    chunk = _extract_object_chunk(read_internal_file(ROOT / MAIN_MEGA_NO_SOURCE_DONOR, "ROOT.DSN"))
    groups = _raw_groups_from_chunk(chunk, _generation_markers())
    probe: dict[str, Any] = {
        "donor": str(MAIN_MEGA_NO_SOURCE_DONOR),
        "purpose": (
            "Record the parsed coordinate fields used by the V2 resistor beautifier probe. "
            "These replace the rejected V1 fixed offset table."
        ),
        "rejected_v1_offsets": ["12/16", "22/26", "91/95", "168/172", "254/258"],
    }
    for family in ("RESISTOR", "CAP", "REALIND", "CAP-ELEC", "DIODE"):
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
        "Focused resistor-only beautifier probe after V1 passive-family coordinate movement failed with `LXLCORE.dll`.",
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


def write_root_readme(records: list[dict[str, Any]], byte_probe: dict[str, Any]) -> None:
    resistor_pairs = byte_probe["RESISTOR"]["parsed_coordinate_pairs"]
    lines = [
        "# Beautifier Resistor Coordinate Probe V2",
        "",
        "Generated on 2026-06-24.",
        "",
        "This pack replaces the rejected V1 fixed passive offset table with parsed coordinate fields.",
        "It intentionally tests only `RESISTOR` movement first.",
        "",
        "## Why This Exists",
        "",
        "User reported all `BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23` cases failed with `LXLCORE.dll`.",
        "Byte inspection showed V1 moved packet constants, not true coordinates.",
        "",
        "## Parsed Resistor Coordinates Under Test",
        "",
    ]
    for pair in resistor_pairs:
        lines.append(
            f"- `{pair['x_offset']}/{pair['y_offset']}` -> "
            f"({pair['x_value']}, {pair['y_value']}), `{pair['reason']}`"
        )
    lines.extend(
        [
            "",
            "## Test Files",
            "",
        ]
    )
    for record in records:
        lines.append(f"- `{record['case_folder']}/{record['output_name']}`: {record['what_to_check']}")
    lines.extend(
        [
            "",
            "## User Results",
            "",
            "Pending.",
            "",
            "## Next Step",
            "",
            "If R00 opens and R01-R03 also open without `LXLCORE.dll`, widen to CAP/REALIND/CAP-ELEC/DIODE one family at a time.",
            "If any parsed-coordinate resistor case fails, stop and inspect the emitted packet diff before trying another family.",
            "",
        ]
    )
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    byte_probe = build_byte_probe()
    (OUT_DIR / "byte_probe.json").write_text(json.dumps(byte_probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    records: list[dict[str, Any]] = []
    for index, case in enumerate(CASES):
        case_dir = OUT_DIR / f"{index:02d}_{case['name']}"
        case_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "component-placement/v0.1",
            "components": case["components"],
            "layout": case["layout"],
        }
        payload_path = case_dir / "payload.json"
        payload_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
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
        "test_id": "BEAUTIFIER_RESISTOR_COORDINATE_PROBE_V2_TEMP_2026_06_24",
        "case_count": len(records),
        "records": records,
        "byte_probe": "byte_probe.json",
        "policy": {
            "actual_generator": "proteusgen.component_placer.generate_component_placement_project",
            "explicit_donor": str(MAIN_MEGA_NO_SOURCE_DONOR),
            "focus": "resistor-only parsed coordinate fields",
            "rejected_previous_pack": "BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23",
            "full_cdb": True,
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_root_readme(records, byte_probe)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    summary["archive"] = str(ARCHIVE.relative_to(ROOT))
    summary["archive_sha256"] = sha256(ARCHIVE)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "archive": str(ARCHIVE), "sha256": summary["archive_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
