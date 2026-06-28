"""Generate V4 no-terminal bare-placement tests around resistor anchors.

User testing of V3 reported only F09, F13, and F14 failed. Those were the
cases with all RESISTOR records removed. This pack keeps the same donor and
parser as V3, then isolates whether one, two, three, or all four resistor
records are needed and whether resistor-only support is enough for IC mixes.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V3_SCRIPT = ROOT / "tools/proteus_generation/2026-06-16/generate_bare_visibility_rlc_anchor_v3_temp.py"
OUT_DIR = ROOT / "experiments/bare_visibility_resistor_anchor_v4_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_VISIBILITY_RESISTOR_ANCHOR_V4_TEMP_2026_06_16.zip"


def load_v3_module():
    spec = importlib.util.spec_from_file_location("bare_visibility_rlc_anchor_v3_temp", V3_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {V3_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUT_DIR = OUT_DIR
    module.ZIP_OUT = ZIP_OUT
    return module


def main() -> None:
    v3 = load_v3_module()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    donor_dsn = v3.read_internal_file(v3.DONOR, "ROOT.DSN")
    donor_cdb = v3.read_internal_file(v3.DONOR, "ROOT.CDB")
    groups = v3.groups_from_no_terminal_chunk(v3._extract_object_chunk(donor_dsn))

    full_r = {"RESISTOR": 4}
    full_c = {"CAP": 4}
    full_l = {"REALIND": 4}
    support_digital = {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2}
    specs = [
        ("G00_D15_WORKING_CONTROL", {**support_digital, **full_r, **full_c, **full_l}, "Known working D15 shape rebuilt as control."),
        ("G01_R1_ONLY", {"RESISTOR": 1}, "One resistor only."),
        ("G02_R2_ONLY", {"RESISTOR": 2}, "Two resistors only."),
        ("G03_R3_ONLY", {"RESISTOR": 3}, "Three resistors only."),
        ("G04_R4_ONLY", {"RESISTOR": 4}, "All four donor resistors only."),
        ("G05_160_1X_R1", {"74HC160": 1, "RESISTOR": 1}, "One 74HC160 plus one resistor."),
        ("G06_160_1X_R2", {"74HC160": 1, "RESISTOR": 2}, "One 74HC160 plus two resistors."),
        ("G07_160_1X_R4", {"74HC160": 1, "RESISTOR": 4}, "One 74HC160 plus all four resistors."),
        ("G08_160_4X_R1", {"74HC160": 4, "RESISTOR": 1}, "Four 74HC160 plus one resistor."),
        ("G09_160_4X_R2", {"74HC160": 4, "RESISTOR": 2}, "Four 74HC160 plus two resistors."),
        ("G10_160_4X_R4", {"74HC160": 4, "RESISTOR": 4}, "Four 74HC160 plus all four resistors."),
        ("G11_160_4X_7490_2X_R1", {"74HC160": 4, "7490": 2, "RESISTOR": 1}, "74HC160 plus 7490 with one resistor anchor."),
        ("G12_160_4X_7490_2X_R2", {"74HC160": 4, "7490": 2, "RESISTOR": 2}, "74HC160 plus 7490 with two resistor anchors."),
        ("G13_160_4X_7490_2X_R4", {"74HC160": 4, "7490": 2, "RESISTOR": 4}, "74HC160 plus 7490 with all four resistor anchors."),
        ("G14_160_2X_161_2X_R4", {"74HC160": 2, "74HC161": 2, "RESISTOR": 4}, "Retry 160+161 with resistor anchor only."),
        ("G15_160_2X_HC08_2X_R4", {"74HC160": 2, "74HC08": 2, "RESISTOR": 4}, "Retry 160+HC08 with resistor anchor only."),
        ("G16_160_2X_HC32_2X_R4", {"74HC160": 2, "74HC32": 2, "RESISTOR": 4}, "Retry 160+HC32 with resistor anchor only."),
        ("G17_D15_RESISTOR_SUPPORT_ONLY", {**support_digital, **full_r}, "Known F12-style digital/analog mix with resistor support only."),
        ("G18_D15_RESISTOR_CAP_SUPPORT", {**support_digital, **full_r, **full_c}, "Known F11-style mix with resistors and capacitors."),
        ("G19_D15_RESISTOR_IND_SUPPORT", {**support_digital, **full_r, **full_l}, "Known F10-style mix with resistors and inductors."),
    ]

    cases = [
        v3.write_case(case_id, counts, description, donor_dsn, donor_cdb, groups)
        for case_id, counts, description in specs
    ]
    summary = {
        "experiment": "bare_visibility_resistor_anchor_v4_temp_2026_06_16",
        "purpose": "Determine whether the current no-terminal donor requires any resistor record or the full resistor set.",
        "donor": str(v3.DONOR.relative_to(ROOT)),
        "known_v3_results": {
            "failed": ["F09_D15_MINUS_RESISTORS", "F13_D15_CAPS_ONLY_SUPPORT", "F14_D15_INDUCTORS_ONLY_SUPPORT"],
            "pattern": "All failed V3 cases removed every RESISTOR record; cases with resistor records were not reported failed.",
        },
        "cases": cases,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    v3.zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": len(cases), "zip_sha256": v3.sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
