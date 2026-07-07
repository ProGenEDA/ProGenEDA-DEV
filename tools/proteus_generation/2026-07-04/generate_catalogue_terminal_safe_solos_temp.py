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

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.component_placer import generate_component_placement_project  # noqa: E402
from proteusgen.bidirectional import BIDIR_MARKER  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    _extract_object_chunk,
    attach_catalogue_pin_bidir_terminals_to_project,
)
from proteusgen.pdsprj import read_internal_file  # noqa: E402


OUTPUT_ROOT = REPO / "experiments" / "new_catalogue_terminal_solo_v9_validated_temp_2026_07_04"
ARCHIVE = REPO / "experiments" / "NEW_CATALOGUE_TERMINAL_SOLO_V9_VALIDATED_TEMP_2026_07_04.zip"

DONOR_BASE = REPO / "experiments" / "multi_pin_missing_terminal_donor_bases_v1_temp_2026_07_04"
REQUESTED_COUNTS = (1, 9, 15, 23)

SAFE_TERMINAL_FAMILIES = (
    "4511",
    "74HC151",
    "BRIDGE",
    "LM317T",
    "NMOSFET",
    "OPAMP",
    "POT-HG",
    "TRAN-2P2S",
)

BLOCKED_CASES = {
    "4518": "no catalogue pin geometry or active terminal evidence in the current donor-base file",
    "74HC00": "saved donor has 12 terminals/WIREs but only partial active component pin-link fields",
    "74HC02": "saved donor has 12 terminals/WIREs but only partial active component pin-link fields",
    "74HC04": "current donor-base has no terminal/WIRE skeleton; old HC04 route still needs clean shared-placeable evidence",
    "74HC08": "saved donor has 12 terminals/WIREs but only partial active component pin-link fields",
    "74HC266": "saved donor has 12 terminals/WIREs but only partial active component pin-link fields",
    "74HC32": "saved donor has 12 terminals/WIREs but only partial active component pin-link fields",
    "74HC4520": "no catalogue pin geometry or active terminal evidence in the current donor-base file",
    "74HC86": "saved donor has 12 terminals/WIREs but only partial active component pin-link fields",
    "7SEG-COM-AN-BLUE": "display terminal evidence is not integrated with the D20/display grouping path yet",
    "7SEG-COM-CAT-BLUE": "display terminal evidence is not integrated with the D20/display grouping path yet",
}


def _donor_cases() -> dict[str, Path]:
    cases: dict[str, Path] = {}
    for directory in sorted(DONOR_BASE.iterdir()):
        if not directory.is_dir():
            continue
        match = re.match(r"M\d+_(.+?)_\d+X_NO_TERMINAL_DONOR_BASE$", directory.name)
        if match is None:
            continue
        project = directory / f"{directory.name}.pdsprj"
        if project.exists():
            cases[match.group(1)] = project
    return cases


def _clean_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "_", value.upper())


def _terminal_case_name(index: int, family: str, count: int) -> str:
    return f"S{index:02d}_{_clean_token(family)}_{count}X_CATALOGUE_TERMINAL"


def _empty_case_name(index: int, family: str, count: int) -> str:
    return f"E{index:02d}_{_clean_token(family)}_{count}X_NO_TERMINAL_EMPTY"


def _payload(family: str, count: int) -> dict[str, object]:
    return {
        "components": {family: count},
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        },
    }


def _donor_is_clean_no_terminal_source(donor: Path) -> bool:
    chunk = _extract_object_chunk(read_internal_file(donor, "ROOT.DSN"))
    return chunk.count(BIDIR_MARKER) == 0 and chunk.count(b"\x7fWIRE") == 0


def _generate_empty_control(
    *,
    family: str,
    count: int,
    case_dir: Path,
    donor: Path | None = None,
) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_dir.name}.pdsprj"

    attempts: list[tuple[str, Path | None]] = [("default_registry", None)]
    if donor is not None and _donor_is_clean_no_terminal_source(donor):
        attempts.insert(0, ("clean_donor_base", donor))

    last_error: Exception | None = None
    for source_label, donor_path in attempts:
        if output.exists():
            output.unlink()
        try:
            placement = generate_component_placement_project(
                _payload(family, count),
                output,
                donor_path=donor_path,
            )
        except Exception as exc:  # noqa: BLE001 - evidence runner records blocked controls.
            last_error = exc
            continue
        (case_dir / "placement_manifest.json").write_text(
            json.dumps(placement.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "family": family,
            "count": count,
            "case": case_dir.name,
            "project": str(output.relative_to(REPO)),
            "placement_valid": placement.valid,
            "source": source_label,
            "status": "generated",
        }
    if last_error is None:
        return {
            "family": family,
            "count": count,
            "case": case_dir.name,
            "status": "blocked",
            "error": "no empty-control generation attempt was available",
        }
    return {
        "family": family,
        "count": count,
        "case": case_dir.name,
        "status": "blocked",
        "error": f"{type(last_error).__name__}: {last_error}",
    }


def _generate_terminal_case(
    *,
    family: str,
    donor: Path,
    count: int,
    case_dir: Path,
    build_root: Path,
) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    placed = build_root / f"{case_dir.name}_placed.pdsprj"
    final = case_dir / f"{case_dir.name}_sa.pdsprj"

    placement = generate_component_placement_project(
        _payload(family, count),
        placed,
        donor_path=donor,
    )
    terminal_report = attach_catalogue_pin_bidir_terminals_to_project(
        placed,
        final,
        placement.selected_groups,
        terminal_families=[family],
    )

    (case_dir / "placement_manifest.json").write_text(
        json.dumps(placement.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (case_dir / "terminal_report.json").write_text(
        json.dumps(terminal_report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
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
        "component_link_trailers": sorted(
            {
                row.get("component_trailer")
                for row in terminal_report.get("terminal_suffix_link_checks", [])
            }
        ),
        "donor": str(donor.relative_to(REPO)),
        "status": "generated",
    }


def main() -> None:
    donor_cases = _donor_cases()
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    build_root = OUTPUT_ROOT / "_build_intermediate"
    build_root.mkdir(parents=True, exist_ok=True)

    terminal_cases: list[dict[str, object]] = []
    terminal_errors: list[dict[str, object]] = []
    empty_controls: list[dict[str, object]] = []
    scaled_requests: list[dict[str, object]] = []

    safe_donors = {
        family: donor_cases[family]
        for family in SAFE_TERMINAL_FAMILIES
        if family in donor_cases
    }
    missing_safe = sorted(set(SAFE_TERMINAL_FAMILIES) - set(safe_donors))
    for family in missing_safe:
        terminal_errors.append(
            {
                "family": family,
                "count": 1,
                "status": "blocked",
                "error": "safe family donor file is missing from donor-base folder",
            }
        )

    for index, family in enumerate(SAFE_TERMINAL_FAMILIES, start=1):
        donor = safe_donors.get(family)
        if donor is None:
            continue
        case_dir = OUTPUT_ROOT / _terminal_case_name(index, family, 1)
        try:
            terminal_cases.append(
                _generate_terminal_case(
                    family=family,
                    donor=donor,
                    count=1,
                    case_dir=case_dir,
                    build_root=build_root,
                )
            )
        except Exception as exc:  # noqa: BLE001 - evidence runner records failures.
            terminal_errors.append(
                {
                    "family": family,
                    "count": 1,
                    "case": case_dir.name,
                    "status": "blocked",
                    "error": f"{type(exc).__name__}: {exc}",
                    "donor": str(donor.relative_to(REPO)),
                }
            )
        for requested_count in REQUESTED_COUNTS:
            if requested_count == 1:
                continue
            scaled_requests.append(
                {
                    "family": family,
                    "requested_count": requested_count,
                    "generated_count": 1,
                    "status": "not_generated_source_limit_1",
                    "reason": (
                        "the current terminalized donor-base folder provides only "
                        "one active WIRE/link skeleton for this family; cloning "
                        "component packets is intentionally not used"
                    ),
                }
            )

    for index, family in enumerate(sorted(donor_cases), start=1):
        empty_controls.append(
            _generate_empty_control(
                family=family,
                count=1,
                case_dir=OUTPUT_ROOT / _empty_case_name(index, family, 1),
                donor=donor_cases[family],
            )
        )

    blocked = {
        family: reason
        for family, reason in BLOCKED_CASES.items()
        if family in donor_cases
    }
    for family in sorted(set(donor_cases) - set(SAFE_TERMINAL_FAMILIES) - set(blocked)):
        blocked[family] = "not promoted by the static active-link probe at this checkpoint"

    if build_root.exists():
        shutil.rmtree(build_root)

    summary = {
        "experiment": OUTPUT_ROOT.name,
        "purpose": (
            "Catalogue-backed terminal solos generated through the component placer "
            "and shared component_terminal_placer.py, with no-terminal controls."
        ),
        "requested_counts": list(REQUESTED_COUNTS),
        "terminal_cases": terminal_cases,
        "terminal_errors": terminal_errors,
        "empty_no_terminal_controls": empty_controls,
        "scaled_terminal_requests": scaled_requests,
        "mixed_3x_request": {
            "status": "not_generated_source_limit_1",
            "reason": (
                "mixed 3x requires at least three active terminalized WIRE/link "
                "skeletons per family or a proven non-cloning emitter; current "
                "safe donors provide one skeleton per family"
            ),
        },
        "blocked_terminal_cases": blocked,
        "notes": [
            "Generated through component placer plus shared component_terminal_placer.py.",
            "No component-specific terminal-placement script or alternate terminal workflow was used.",
            "The generated terminalized projects are final *_sa.pdsprj files.",
            "No-terminal controls are generated separately so Proteus open errors can be isolated from terminal placement.",
        ],
    }
    (OUTPUT_ROOT / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUTPUT_ROOT / "README.md").write_text(
        "# New catalogue terminal solo V9 validated - 2026-07-04\n\n"
        "Generated through the shared component placer and "
        "`src/proteusgen/component_terminal_placer.py`.\n\n"
        "Terminalized cases generated:\n\n"
        + "\n".join(
            f"- `{case['case']}`: `{case['family']}`, {case['terminal_count_added']} "
            f"terminals, terminal report valid = {case['terminal_valid']}"
            for case in terminal_cases
        )
        + "\n\nNo-terminal controls are in the `E##_..._NO_TERMINAL_EMPTY` folders.\n\n"
        "Counts above 1 and the mixed 3x pack were not generated because the "
        "current donor evidence provides only one active WIRE/link skeleton per "
        "safe family. This runner does not clone component packets.\n\n"
        "Blocked terminal cases:\n\n"
        + "\n".join(f"- `{family}`: {reason}" for family, reason in sorted(blocked.items()))
        + "\n",
        encoding="utf-8",
    )

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUTPUT_ROOT)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
