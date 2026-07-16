from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import generate_component_placement_project


OUT_DIR = ROOT / "experiments" / "beautifier_coordinate_stage_v2_temp_2026_06_22"
ARCHIVE = ROOT / "experiments" / "BEAUTIFIER_COORDINATE_STAGE_V2_TEMP_2026_06_22.zip"


CASES = [
    {
        "name": "B00_CONTROL_METADATA_ONLY",
        "payload": {
            "components": {"SWITCH": 1, "POT-HG": 1},
            "control_strategy": "hidden_dummy_control",
            "layout": {"strategy": "beautify"},
        },
        "note": (
            "Baseline control case. It should open/simulate. The manifest should mark one extra "
            "SWITCH and one extra POT-HG as hidden dummy controls, but this case does not move "
            "their binary coordinates."
        ),
    },
    {
        "name": "B01_SWITCH_DUMMY_LINKED_RELATIVE",
        "payload": {
            "components": {"SWITCH": 1},
            "control_strategy": "hidden_dummy_control",
            "hidden_coordinate_mode": "linked_relative",
            "layout": {"strategy": "beautify"},
        },
        "note": (
            "SWITCH-only hiding check. One requested switch should remain usable/visible; the extra "
            "dummy switch should be moved away by the beautifier coordinate stage."
        ),
    },
    {
        "name": "B02_POTHG_DUMMY_LINKED_RELATIVE",
        "payload": {
            "components": {"POT-HG": 1},
            "control_strategy": "hidden_dummy_control",
            "hidden_coordinate_mode": "linked_relative",
            "layout": {"strategy": "beautify"},
        },
        "note": (
            "POT-HG-only hiding check. One requested potentiometer should remain usable/visible; "
            "the extra dummy POT-HG should be moved away by the beautifier coordinate stage."
        ),
    },
    {
        "name": "B03_SWITCH_AND_POTHG_DUMMIES_LINKED_RELATIVE",
        "payload": {
            "components": {"SWITCH": 1, "POT-HG": 1},
            "control_strategy": "hidden_dummy_control",
            "hidden_coordinate_mode": "linked_relative",
            "layout": {"strategy": "beautify"},
        },
        "note": (
            "Combined control hiding check. Both requested controls should remain visible/usable, "
            "while the first extra SWITCH and first extra POT-HG are moved away."
        ),
    },
    {
        "name": "B04_DISPLAY_D20_VISIBLE_CONTROL",
        "payload": {
            "components": {"7segcomanode": 1, "7segcomk": 1, "DIODE": 1},
            "layout": {"strategy": "beautify"},
        },
        "note": (
            "Display bridge control. This intentionally keeps the D20 bridge visible. You should see "
            "one user-requested diode plus the D20 display bridge infrastructure, and one anode plus "
            "one cathode 7-segment display."
        ),
    },
    {
        "name": "B05_DISPLAY_D20_HIDDEN_LINKED_RELATIVE",
        "payload": {
            "components": {"7segcomanode": 1, "7segcomk": 1, "DIODE": 1},
            "hide_display_bridge": True,
            "hidden_coordinate_mode": "linked_relative",
            "layout": {"strategy": "beautify", "hide_display_bridge": True},
        },
        "note": (
            "D20 hiding check. The requested diode and both displays should remain visible. The D20 "
            "bridge should be moved away by the beautifier coordinate stage."
        ),
    },
    {
        "name": "B06_CONTROLS_AND_DISPLAY_HIDDEN_LINKED_RELATIVE",
        "payload": {
            "components": {"SWITCH": 1, "POT-HG": 1, "7segcomanode": 1, "7segcomk": 1, "DIODE": 1},
            "control_strategy": "hidden_dummy_control",
            "hide_display_bridge": True,
            "hidden_coordinate_mode": "linked_relative",
            "layout": {"strategy": "beautify", "hide_display_bridge": True},
        },
        "note": (
            "Full hidden-infrastructure check. The requested SWITCH, POT-HG, diode, and displays "
            "should remain visible. The extra SWITCH/POT-HG and D20 bridge should be moved away."
        ),
    },
    {
        "name": "B07_WIRING_PLAN_LAYOUT_ONLY_NO_BINARY_MOVE",
        "payload": {
            "components": {"74HC00": 1, "74HC08": 1, "RESISTOR": 3, "CAP": 2, "LED-RED": 2},
            "layout": {"strategy": "beautify"},
            "connections": [
                {"net": "A", "endpoints": [{"component": "U1:A", "pin": "A"}, {"component": "U2:A", "pin": "A"}]},
                {"net": "Y1", "from": {"component": "U1:A", "pin": "Y"}, "to": {"component": "R1", "pin": "1"}},
                {"net": "LOAD", "from": {"component": "R1", "pin": "2"}, "to": {"component": "LED1", "pin": "A"}},
            ],
        },
        "note": (
            "Layout-plan-only case. This does not move binary coordinates. Check the manifest "
            "wiring_plan and layout_plan: same-net groups should list A/Y1/LOAD and the beautifier "
            "should produce deterministic placements."
        ),
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for index, case in enumerate(CASES):
        case_dir = OUT_DIR / f"{index:02d}_{case['name']}"
        case_dir.mkdir(parents=True, exist_ok=True)
        payload_path = case_dir / "payload.json"
        payload_path.write_text(json.dumps(case["payload"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (case_dir / "WHAT_TO_CHECK.txt").write_text(case["note"] + "\n", encoding="utf-8")
        output_path = case_dir / f"{case['name']}.pdsprj"
        result = generate_component_placement_project(case["payload"], output_path, full_cdb=True)
        results.append(
            {
                "case": case["name"],
                "output": str(output_path.relative_to(ROOT)),
                "manifest": str(result.manifest_path.relative_to(ROOT)),
                "valid": result.valid,
                "errors": [issue.as_dict() for issue in result.errors],
                "request": result.request,
                "hidden_coordinate_mode": case["payload"].get("hidden_coordinate_mode", "none"),
                "note": case["note"],
            }
        )

    summary = {
        "test_id": "BEAUTIFIER_COORDINATE_STAGE_V2_STATIC_20260622",
        "case_count": len(results),
        "cases": results,
        "policy": {
            "uses_actual_generator": "src.proteusgen.component_placer.generate_component_placement_project",
            "full_cdb": True,
            "pruned_cdb_cases": "omitted because the previous CDB-slice coordinate test was rejected",
            "coordinate_mutation_default": "none",
            "coordinate_mutation_test_mode": "linked_relative only",
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "\n".join(
            [
                "Beautifier coordinate stage V2 test pack",
                "",
                "Open each .pdsprj in order. Each case folder has WHAT_TO_CHECK.txt.",
                "The rejected pruned-CDB/CDB-slice variant is intentionally not included.",
                "If a hidden case opens, verify the requested components remain visible while only the infrastructure dummy is moved away.",
                "",
                "Cases:",
                *[f"- {item['case']}: {item['note']}" for item in results],
                "",
            ]
        ),
        encoding="utf-8",
    )
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    summary["archive"] = str(ARCHIVE.relative_to(ROOT))
    summary["archive_sha256"] = sha256(ARCHIVE)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "archive": str(ARCHIVE), "sha256": summary["archive_sha256"]}, indent=2))


if __name__ == "__main__":
    main()
