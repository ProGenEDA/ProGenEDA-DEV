from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import (  # noqa: E402
    MAIN_MEGA_NO_SOURCE_DONOR,
    NEW_COMPONENT_MEGA_DONOR,
    _repo_path,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    append_bidir_terminals_to_project,
    plan_side_bidir_terminals,
)


OUT_DIR = ROOT / "experiments" / "terminal_placer_bidir_probe_v2_all_families_temp_2026_06_26"
ARCHIVE = ROOT / "experiments" / "TERMINAL_PLACER_BIDIR_PROBE_V2_ALL_FAMILIES_TEMP_2026_06_26.zip"


CASES = [
    {
        "case_id": "T01_PASSIVE_DISCRETE_BIDIR_SIDE_ANCHORS",
        "payload": {
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
            "components": {
                "RESISTOR": 2,
                "CAP": 2,
                "CAP-ELEC": 2,
                "REALIND": 2,
                "DIODE": 2,
                "NPN": 1,
                "PNP": 1,
            },
            "layout": {"strategy": "beautify"},
        },
    },
    {
        "case_id": "T02_IC_DISPLAY_BIDIR_SIDE_ANCHORS",
        "payload": {
            "donor": str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR)),
            "components": {
                "74HC00": 1,
                "74HC04": 1,
                "74HC08": 1,
                "74HC32": 1,
                "74HC74": 1,
                "74HC76": 1,
                "74HC85": 1,
                "74HC86": 1,
                "74HC151": 1,
                "74HC157": 1,
                "74HC160": 1,
                "74HC174": 1,
                "74HC192": 1,
                "74HC266": 1,
                "74HC283": 1,
                "7490": 1,
                "4027": 1,
                "4511": 1,
                "7447": 1,
                "LM741": 1,
                "NE555": 1,
                "7SEGCOMA": 1,
                "7SEGCOMK": 1,
            },
            "layout": {"strategy": "legacy"},
        },
    },
    {
        "case_id": "T03_SOURCE_CONTROL_BIDIR_SIDE_ANCHORS",
        "payload": {
            "donor": str(_repo_path(NEW_COMPONENT_MEGA_DONOR)),
            "components": {
                "VSOURCE": 2,
                "CSOURCE": 2,
                "VSINE": 1,
                "VPULSE": 1,
                "SWITCH": 2,
                "POT-HG": 2,
                "OPAMP": 1,
                "LM317T": 1,
                "FUSE": 1,
                "LED-RED": 1,
                "BRIDGE": 1,
                "TRANSFORMER": 1,
                "1N4007": 1,
                "1N4148": 1,
                "1N4733A": 1,
                "1N6000B": 1,
                "40EPS08": 1,
                "BZX55C5V1": 1,
                "BZX79C5V1": 1,
                "BZY88C": 1,
                "2N3904": 1,
                "2N4401": 1,
                "2N7000": 1,
                "BS170": 1,
                "NMOSFET": 1,
            },
            "layout": {"strategy": "beautify"},
        },
    },
]


def clean() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()


def main() -> None:
    clean()
    summary = []
    for index, case in enumerate(CASES, start=1):
        case_id = case["case_id"]
        case_dir = OUT_DIR / f"{index:02d}_{case_id}"
        case_dir.mkdir()
        payload = case["payload"]
        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        result = generate_component_placement_project(payload, base, full_cdb=True)
        specs = plan_side_bidir_terminals(result.selected_groups, label_prefix=f"N{index}", max_terminals_per_side=4)
        terminal_report = append_bidir_terminals_to_project(base, output, specs)
        (case_dir / "payload.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (case_dir / "base_manifest.json").write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
        (case_dir / "terminal_plan.json").write_text(json.dumps(terminal_report, indent=2) + "\n", encoding="utf-8")
        summary.append(
            {
                "case_id": case_id,
                "base_valid": result.valid,
                "terminal_valid": terminal_report["valid"],
                "terminal_count_added": terminal_report["terminal_count_added"],
                "output": str(output.relative_to(OUT_DIR)),
            }
        )
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "README.md").write_text(
        "# Terminal Placer Bidir Probe V2\n\n"
        "These cases use the accepted component placer first, then append donor-derived `$TERBIDIR` records.\n"
        "V2 covers every selected user component family in the case, not only passives.\n"
        "No Proteus wire records are emitted yet; this is a side-anchor probe, not final wire-backed pin attachment.\n"
        "Inspect whether left-side terminals are 180-degree bidirs and right-side terminals are 0-degree bidirs.\n"
        "D20/display sentinel infrastructure is intentionally skipped because it is not a user-requested component pin.\n"
        "The labels are generated by this stage so future wiring/naming work stays in one owner.\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    print(json.dumps({"out_dir": str(OUT_DIR), "archive": str(ARCHIVE), "cases": len(summary)}, indent=2))


if __name__ == "__main__":
    main()
