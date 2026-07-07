"""Generate catalogue-backed multi-pin terminal evidence packs.

This runner intentionally contains no terminal-placement logic.  It uses the
shared component placer and the shared catalogue terminal placer only.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.component_placer import generate_component_placement_project  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_catalogue_pin_bidir_terminals_to_project,
)


OUTPUT_ROOT = (
    REPO
    / "experiments"
    / "catalogue_terminal_main_donor_v10_temp_2026_07_07"
)
ARCHIVE = (
    REPO
    / "experiments"
    / "CATALOGUE_TERMINAL_MAIN_DONOR_V10_TEMP_2026_07_07.zip"
)

REQUESTED_COUNTS = (1, 9, 15, 23)

PROMOTED_TERMINAL_FAMILIES = (
    "4511",
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC151",
    "74HC266",
    "74HC32",
    "74HC86",
    "7SEG-COM-AN-BLUE",
    "7SEG-COM-CAT-BLUE",
    "BRIDGE",
    "LM317T",
    "NMOSFET",
    "OPAMP",
    "POT-HG",
    "TRAN-2P2S",
)

KNOWN_NOT_PROMOTED = {
    "4518": "user requested ignore until better evidence; no accepted terminal catalogue profile",
    "74HC4520": "user requested ignore until better evidence; no accepted terminal catalogue profile",
}


def _clean_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "_", value.upper())


def _case_name(prefix: str, index: int, family: str, count: int, suffix: str) -> str:
    return f"{prefix}{index:02d}_{_clean_token(family)}_{count}X_{suffix}"


def _payload(family_or_components: str | dict[str, int], count: int | None = None) -> dict[str, object]:
    components = (
        {family_or_components: count}
        if isinstance(family_or_components, str)
        else dict(family_or_components)
    )
    return {
        "components": components,
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        },
    }


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _generate_empty_control(*, family: str, count: int, case_dir: Path) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_dir.name}.pdsprj"
    try:
        placement = generate_component_placement_project(_payload(family, count), output)
    except Exception as exc:  # noqa: BLE001 - evidence runner records failures.
        return {
            "family": family,
            "count": count,
            "case": case_dir.name,
            "status": "blocked",
            "error": f"{type(exc).__name__}: {exc}",
        }
    _write_json(case_dir / "placement_manifest.json", placement.as_dict())
    return {
        "family": family,
        "count": count,
        "case": case_dir.name,
        "project": str(output.relative_to(REPO)),
        "placement_valid": placement.valid,
        "donor": str(placement.donor.relative_to(REPO)),
        "status": "generated",
    }


def _generate_terminal_case(
    *,
    family: str,
    count: int,
    case_dir: Path,
    build_root: Path,
) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    placed = build_root / f"{case_dir.name}_placed.pdsprj"
    final = case_dir / f"{case_dir.name}_sa.pdsprj"

    placement = generate_component_placement_project(_payload(family, count), placed)
    terminal_report = attach_catalogue_pin_bidir_terminals_to_project(
        placed,
        final,
        placement.selected_groups,
        terminal_families=[family],
    )

    _write_json(case_dir / "placement_manifest.json", placement.as_dict())
    _write_json(case_dir / "terminal_report.json", terminal_report)
    return {
        "family": family,
        "count": count,
        "case": case_dir.name,
        "final_project": str(final.relative_to(REPO)),
        "placement_valid": placement.valid,
        "terminal_valid": bool(terminal_report["valid"]),
        "terminal_count_added": terminal_report["terminal_count_added"],
        "wire_count_after": terminal_report["wire_count_after"],
        "wire_contacts_valid": terminal_report["wire_path_contacts_valid"],
        "terminal_suffix_links_valid": terminal_report["terminal_suffix_links_valid"],
        "terminal_grid_alignment_valid": terminal_report["terminal_grid_alignment_valid"],
        "donor": str(placement.donor.relative_to(REPO)),
        "status": "generated",
    }


def _generate_mixed_case(*, case_dir: Path, build_root: Path) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    components = {family: 3 for family in PROMOTED_TERMINAL_FAMILIES}
    placed = build_root / f"{case_dir.name}_placed.pdsprj"
    final = case_dir / f"{case_dir.name}_sa.pdsprj"

    placement = generate_component_placement_project(_payload(components), placed)
    terminal_report = attach_catalogue_pin_bidir_terminals_to_project(
        placed,
        final,
        placement.selected_groups,
        terminal_families=PROMOTED_TERMINAL_FAMILIES,
    )

    _write_json(case_dir / "placement_manifest.json", placement.as_dict())
    _write_json(case_dir / "terminal_report.json", terminal_report)
    return {
        "case": case_dir.name,
        "components": components,
        "final_project": str(final.relative_to(REPO)),
        "placement_valid": placement.valid,
        "terminal_valid": bool(terminal_report["valid"]),
        "terminal_count_added": terminal_report["terminal_count_added"],
        "wire_count_after": terminal_report["wire_count_after"],
        "wire_contacts_valid": terminal_report["wire_path_contacts_valid"],
        "terminal_suffix_links_valid": terminal_report["terminal_suffix_links_valid"],
        "terminal_grid_alignment_valid": terminal_report["terminal_grid_alignment_valid"],
        "donor": str(placement.donor.relative_to(REPO)),
        "status": "generated",
    }


def main() -> None:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    build_root = OUTPUT_ROOT / "_build_intermediate"
    build_root.mkdir(parents=True, exist_ok=True)

    terminal_cases: list[dict[str, object]] = []
    terminal_errors: list[dict[str, object]] = []
    empty_controls: list[dict[str, object]] = []

    for index, family in enumerate(PROMOTED_TERMINAL_FAMILIES, start=1):
        for count in REQUESTED_COUNTS:
            terminal_dir = OUTPUT_ROOT / _case_name(
                "S",
                index,
                family,
                count,
                "CATALOGUE_TERMINAL",
            )
            try:
                terminal_cases.append(
                    _generate_terminal_case(
                        family=family,
                        count=count,
                        case_dir=terminal_dir,
                        build_root=build_root,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - evidence runner records failures.
                terminal_errors.append(
                    {
                        "family": family,
                        "count": count,
                        "case": terminal_dir.name,
                        "status": "blocked",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )

            empty_controls.append(
                _generate_empty_control(
                    family=family,
                    count=count,
                    case_dir=OUTPUT_ROOT
                    / _case_name("E", index, family, count, "NO_TERMINAL_CONTROL"),
                )
            )

    mixed_case: dict[str, object]
    try:
        mixed_case = _generate_mixed_case(
            case_dir=OUTPUT_ROOT / "MIXED_3X_ALL_PROMOTED_CATALOGUE_TERMINAL",
            build_root=build_root,
        )
    except Exception as exc:  # noqa: BLE001 - evidence runner records failures.
        mixed_case = {
            "case": "MIXED_3X_ALL_PROMOTED_CATALOGUE_TERMINAL",
            "status": "blocked",
            "error": f"{type(exc).__name__}: {exc}",
        }

    if build_root.exists():
        shutil.rmtree(build_root)

    summary = {
        "experiment": OUTPUT_ROOT.name,
        "purpose": (
            "Scalable catalogue-backed terminal packs generated through the "
            "component placer and shared component_terminal_placer.py."
        ),
        "requested_counts": list(REQUESTED_COUNTS),
        "promoted_terminal_families": list(PROMOTED_TERMINAL_FAMILIES),
        "known_not_promoted": KNOWN_NOT_PROMOTED,
        "terminal_cases": terminal_cases,
        "terminal_errors": terminal_errors,
        "empty_no_terminal_controls": empty_controls,
        "mixed_3x": mixed_case,
        "notes": [
            "No terminal-placement logic exists in this runner.",
            "No alternate donor path is passed to the component placer.",
            "Donor-base files are catalogue evidence only; generated projects use the component placer default donor selection.",
            "Final terminalized projects are *_sa.pdsprj files.",
            "No-terminal controls are generated for the same family/count pairs.",
        ],
    }
    _write_json(OUTPUT_ROOT / "summary.json", summary)
    (OUTPUT_ROOT / "README.md").write_text(
        "# Catalogue terminal main-donor V10 - 2026-07-07\n\n"
        "Generated through the shared component placer and "
        "`src/proteusgen/component_terminal_placer.py`.\n\n"
        "Terminalized cases:\n\n"
        + "\n".join(
            f"- `{case['case']}`: `{case['family']}` x{case['count']}, "
            f"terminals={case['terminal_count_added']}, valid={case['terminal_valid']}"
            for case in terminal_cases
        )
        + "\n\nMixed 3x:\n\n"
        + f"- `{mixed_case.get('case')}`: status={mixed_case.get('status')}, "
        + f"valid={mixed_case.get('terminal_valid')}\n\n"
        + "No-terminal controls are in the `E##_..._NO_TERMINAL_CONTROL` folders.\n\n"
        + "Known not promoted:\n\n"
        + "\n".join(
            f"- `{family}`: {reason}" for family, reason in sorted(KNOWN_NOT_PROMOTED.items())
        )
        + "\n",
        encoding="utf-8",
    )

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUTPUT_ROOT)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
