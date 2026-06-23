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

from proteusgen.component_placer import MAIN_MEGA_NO_SOURCE_DONOR, generate_component_placement_project


OUT_DIR = ROOT / "experiments" / "beautifier_family_passives_v1_temp_2026_06_23"
ARCHIVE = ROOT / "experiments" / "BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23.zip"


CASES: list[dict[str, Any]] = [
    {
        "name": "P01_RESISTOR_5X_FAMILY_PLAN",
        "components": {"RESISTOR": 5},
        "what_to_check": "Five resistors should be visible, separated on the beautifier grid, with names/values staying near their symbols.",
    },
    {
        "name": "P02_CAP_5X_FAMILY_PLAN",
        "components": {"CAP": 5},
        "what_to_check": "Five capacitors should be visible, separated on the beautifier grid, with labels/values attached and no overlap.",
    },
    {
        "name": "P03_REALIND_5X_FAMILY_PLAN",
        "components": {"REALIND": 5},
        "what_to_check": "Five inductors should be visible, separated on the beautifier grid, with labels/values attached and no overlap.",
    },
    {
        "name": "P04_CAP_ELEC_5X_FAMILY_PLAN",
        "components": {"CAP-ELEC": 5},
        "what_to_check": "Five electrolytic capacitors should be visible and separated. This specifically checks that the old false coordinate near 16,384,000 is no longer moved as part of the packet.",
    },
    {
        "name": "P05_DIODE_5X_FAMILY_PLAN",
        "components": {"DIODE": 5},
        "what_to_check": "Five diodes should be visible, separated on the beautifier grid, with labels attached and no overlap.",
    },
    {
        "name": "P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN",
        "components": {"RESISTOR": 3, "CAP": 3, "REALIND": 3, "CAP-ELEC": 3, "DIODE": 3},
        "what_to_check": "Mixed passive pack. All 15 components should be visible on the grid with no strange far-away labels, overlaps, or bad object records.",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_case_note(case_dir: Path, case: dict[str, Any], output_path: Path, manifest_path: Path | None) -> None:
    lines = [
        f"# {case['name']}",
        "",
        "## Purpose",
        "",
        "Focused beautifier test for the first passive-family coordinate plans.",
        "The component placer still performs removal-only donor packet selection; this test only changes coordinate movement.",
        "",
        "## Input",
        "",
        "```json",
        json.dumps({"components": case["components"], "layout": {"strategy": "beautify"}}, indent=2, sort_keys=True),
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
        "Open the project first. If it opens, inspect visual placement. If applicable, run simulation and record any Proteus errors.",
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


def write_root_readme(records: list[dict[str, Any]]) -> None:
    lines = [
        "# Beautifier Family Passives V1",
        "",
        "Generated on 2026-06-23.",
        "",
        "This pack starts the new family-by-family beautifier workflow. It tests only passive-family coordinate movement in the shared component placer/beautifier pipeline.",
        "",
        "## Code Under Test",
        "",
        "- `src/proteusgen/component_beautifier.py`",
        "- `src/proteusgen/component_placer.py` via `generate_component_placement_project`",
        "",
        "## New Coordinate Policy Under Test",
        "",
        "The beautifier now uses explicit coordinate-offset plans for:",
        "",
        "- `RESISTOR`",
        "- `CAP`",
        "- `REALIND`",
        "- `CAP-ELEC`",
        "- `DIODE`",
        "",
        "Other families still use the previous generic coordinate scanner until their family-specific plans are learned.",
        "",
        "## Test Files",
        "",
    ]
    for record in records:
        lines.append(f"- `{record['case']}/{record['output_name']}`: {record['what_to_check']}")
    lines.extend(
        [
            "",
            "## User Results",
            "",
            "Pending.",
            "",
            "## Next Step",
            "",
            "After user confirmation, update each case README and either lock this passive-family coordinate method or record the failing family-specific offset.",
            "",
        ]
    )
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for index, case in enumerate(CASES, start=1):
        case_dir = OUT_DIR / f"{index:02d}_{case['name']}"
        case_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": "component-placement/v0.1",
            "components": case["components"],
            "layout": {"strategy": "beautify"},
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
                "components": case["components"],
                "output": str(output_path.relative_to(ROOT)),
                "output_name": output_path.name,
                "manifest": str(result.manifest_path.relative_to(ROOT)),
                "valid": result.valid,
                "errors": [issue.as_dict() for issue in result.errors],
                "what_to_check": case["what_to_check"],
            }
        )

    summary = {
        "test_id": "BEAUTIFIER_FAMILY_PASSIVES_V1_TEMP_2026_06_23",
        "case_count": len(records),
        "records": records,
        "policy": {
            "actual_generator": "proteusgen.component_placer.generate_component_placement_project",
            "explicit_donor": str(MAIN_MEGA_NO_SOURCE_DONOR),
            "layout_strategy": "beautify",
            "full_cdb": True,
            "focus": "family-specific passive coordinate plans",
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_root_readme(records)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    summary["archive"] = str(ARCHIVE.relative_to(ROOT))
    summary["archive_sha256"] = sha256(ARCHIVE)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "archive": str(ARCHIVE), "sha256": summary["archive_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
