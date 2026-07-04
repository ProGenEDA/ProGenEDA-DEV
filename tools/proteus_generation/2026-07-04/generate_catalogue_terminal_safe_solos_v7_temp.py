"""Generate safe catalogue-backed multi-pin terminal solo evidence.

This runner intentionally contains no terminal-placement logic.  It uses the
shared component placer and the shared catalogue terminal placer only.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.component_placer import generate_component_placement_project  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_catalogue_pin_bidir_terminals_to_project,
)


OUTPUT_ROOT = REPO / "experiments" / "new_catalogue_terminal_solo_v7_temp_2026_07_04"
ARCHIVE = REPO / "experiments" / "NEW_CATALOGUE_TERMINAL_SOLO_V7_TEMP_2026_07_04.zip"

DONOR_BASE = REPO / "experiments" / "multi_pin_missing_terminal_donor_bases_v1_temp_2026_07_04"

SAFE_CASES: tuple[tuple[str, Path], ...] = (
    (
        "4511",
        DONOR_BASE
        / "M01_4511_1X_NO_TERMINAL_DONOR_BASE"
        / "M01_4511_1X_NO_TERMINAL_DONOR_BASE.pdsprj",
    ),
    (
        "74HC151",
        DONOR_BASE
        / "M07_74HC151_1X_NO_TERMINAL_DONOR_BASE"
        / "M07_74HC151_1X_NO_TERMINAL_DONOR_BASE.pdsprj",
    ),
    (
        "74HC04",
        REPO
        / "experiments"
        / "ic_hc04_all7_v1_temp_2026_06_08"
        / "T02_74HC04_ALL6_NOT"
        / "T02_74HC04_ALL6_NOT.pdsprj",
    ),
)

BLOCKED_CASES = {
    "74HC00": "saved donor has 12 terminals/WIREs but only three active component pin-link fields",
    "74HC02": "saved donor has terminals/WIREs but lacks a complete active pin-link table",
    "74HC08": "saved donor has terminals/WIREs but lacks a complete active pin-link table",
    "74HC266": "saved donor has terminals/WIREs, plus one corrected label typo, but lacks a complete active pin-link table",
    "74HC32": "saved donor has terminals/WIREs but lacks a complete active pin-link table",
    "74HC86": "saved donor has terminals/WIREs but lacks a complete active pin-link table",
    "BRIDGE": "saved donor has terminals/WIREs but no active component pin-link fields",
    "LM317T": "saved donor has terminals/WIREs but no active component pin-link fields",
    "7SEG-COM-AN-BLUE": "display terminal evidence is not yet integrated with the D20/display grouping path",
    "7SEG-COM-CAT-BLUE": "display terminal evidence is not yet integrated with the D20/display grouping path",
}


def _case_name(index: int, family: str) -> str:
    return f"S{index:02d}_{family.replace('/', '_')}_1X_CATALOGUE_TERMINAL"


def main() -> None:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    cases: list[dict[str, object]] = []
    for index, (family, donor) in enumerate(SAFE_CASES, start=1):
        case_dir = OUTPUT_ROOT / _case_name(index, family)
        case_dir.mkdir(parents=True, exist_ok=True)
        placed = case_dir / f"{case_dir.name}_placed.pdsprj"
        final = case_dir / f"{case_dir.name}_sa.pdsprj"

        placement = generate_component_placement_project(
            {
                "components": {family: 1},
                "layout": {
                    "strategy": "beautify",
                    "binary_coordinate_mutation": True,
                },
            },
            placed,
            donor_path=donor,
        )
        terminal_report = attach_catalogue_pin_bidir_terminals_to_project(
            placed,
            final,
            placement.selected_groups,
            terminal_families=[family],
        )

        placement_manifest = placement.as_dict()
        (case_dir / "placement_manifest.json").write_text(
            json.dumps(placement_manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (case_dir / "terminal_report.json").write_text(
            json.dumps(terminal_report, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        cases.append(
            {
                "family": family,
                "case": case_dir.name,
                "final_project": str(final.relative_to(REPO)),
                "placement_valid": placement.valid,
                "terminal_valid": bool(terminal_report["valid"]),
                "terminal_count_added": terminal_report["terminal_count_added"],
                "wire_count_after": terminal_report["wire_count_after"],
                "donor": str(donor.relative_to(REPO)),
            }
        )

    summary = {
        "experiment": OUTPUT_ROOT.name,
        "purpose": "Safe catalogue-backed terminal solos for newly promoted multi-pin evidence.",
        "safe_cases": cases,
        "blocked_cases": BLOCKED_CASES,
        "notes": [
            "Generated through component placer plus shared component_terminal_placer.py.",
            "No component-specific terminal-placement script or alternate terminal workflow was used.",
            "Blocked cases have terminal geometry in the catalogue but lack complete active component pin-link evidence.",
        ],
    }
    (OUTPUT_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_ROOT / "README.md").write_text(
        "# New catalogue terminal solo V7 - 2026-07-04\n\n"
        "Generated through the shared component placer and "
        "`src/proteusgen/component_terminal_placer.py`.\n\n"
        "Safe generated cases:\n\n"
        + "\n".join(
            f"- `{case['case']}`: `{case['family']}`, "
            f"{case['terminal_count_added']} terminals, terminal report valid = "
            f"{case['terminal_valid']}"
            for case in cases
        )
        + "\n\nBlocked at this checkpoint:\n\n"
        + "\n".join(f"- `{family}`: {reason}" for family, reason in BLOCKED_CASES.items())
        + "\n",
        encoding="utf-8",
    )

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUTPUT_ROOT)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
