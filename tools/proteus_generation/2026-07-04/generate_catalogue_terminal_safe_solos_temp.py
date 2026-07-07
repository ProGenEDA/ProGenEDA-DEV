"""Generate the Proteus terminal recovery 1x solo evidence pack.

This is intentionally a runner, not a terminal-placement implementation.  It
feeds JSON requests into the component placer and then calls only the shared
terminal-placement APIs:

* accepted two-pin families -> ``attach_component_bidir_terminals_to_project``
* V9-safe multi-pin existing-anchor families ->
  ``attach_catalogue_pin_bidir_terminals_to_project``

The V10 catalogue link-offset/bare-WIRE path is excluded because user Proteus
testing rejected every generated V10 file.  This pack rebuilds a small, testable
1x baseline before any count scaling or mixed packs are attempted again.
"""

from __future__ import annotations

import hashlib
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

from proteusgen.bidirectional import BIDIR_MARKER  # noqa: E402
from proteusgen.component_placer import (  # noqa: E402
    NEW_COMPONENT_MEGA_DONOR,
    _repo_path,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    _extract_object_chunk,
    attach_catalogue_pin_bidir_terminals_to_project,
    attach_component_bidir_terminals_to_project,
)
from proteusgen.pdsprj import read_internal_file  # noqa: E402


OUTPUT_ROOT = REPO / "experiments" / "terminal_recovery_solo_1x_temp_2026_07_08"
ARCHIVE = REPO / "experiments" / "TERMINAL_RECOVERY_SOLO_1X_TEMP_2026_07_08.zip"

DONOR_BASE = REPO / "experiments" / "multi_pin_missing_terminal_donor_bases_v1_temp_2026_07_04"
TWO_PIN_DONOR = _repo_path(NEW_COMPONENT_MEGA_DONOR)

ACCEPTED_TWO_PIN_FAMILIES = (
    "RESISTOR",
    "CAP",
    "DIODE",
    "VSINE",
    "VSOURCE",
    "CSOURCE",
    "VPULSE",
    "LED-RED",
    "1N4733A",
    "40EPS08",
    "BZY88C",
    "1N4007",
    "1N4148",
    "1N6000B",
    "BZX55C5V1",
    "BZX79C5V1",
    "FUSE",
    "REALIND",
    "CAP-ELEC",
)

# These are the V9 families that used donor-native existing WIRE/terminal
# anchors.  They are kept separate from the V10 link-offset promoted list.
V9_EXISTING_ANCHOR_MULTI_PIN_FAMILIES = (
    "4511",
    "74HC151",
    "BRIDGE",
    "LM317T",
    "NMOSFET",
    "OPAMP",
    "POT-HG",
    "TRAN-2P2S",
)

BLOCKED_TERMINAL_FAMILIES = {
    "4518": "no accepted existing-anchor terminal evidence; ignored previously",
    "74HC00": "V10 bare link-offset promotion rejected by Proteus",
    "74HC02": "V10 bare link-offset promotion rejected by Proteus",
    "74HC04": "V10 bare link-offset promotion rejected by Proteus",
    "74HC08": "V10 bare link-offset promotion rejected by Proteus",
    "74HC266": "V10 bare link-offset promotion rejected by Proteus",
    "74HC32": "V10 bare link-offset promotion rejected by Proteus",
    "74HC4520": "no accepted existing-anchor terminal evidence; ignored previously",
    "74HC86": "V10 bare link-offset promotion rejected by Proteus",
    "7SEG-COM-AN-BLUE": "display V10 link-offset path rejected; needs accepted donor-native route",
    "7SEG-COM-CAT-BLUE": "display V10 link-offset path rejected; D20/display grouping still needs accepted route",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _clean_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "_", value.upper())


def _case_name(prefix: str, index: int, family: str, suffix: str) -> str:
    return f"{prefix}{index:03d}_{_clean_token(family)}_1X_{suffix}"


def _payload(
    family: str,
    *,
    donor: Path | None = None,
    force_two_pin_donor: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "components": {family: 1},
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        },
    }
    if force_two_pin_donor:
        payload["donor"] = str(TWO_PIN_DONOR.relative_to(REPO))
        if family == "CAP-ELEC":
            payload["component_offsets"] = {"CAP-ELEC": 21}
    if donor is not None:
        payload["evidence_donor"] = str(donor.relative_to(REPO))
    return payload


def _donor_cases() -> dict[str, Path]:
    cases: dict[str, Path] = {}
    if not DONOR_BASE.exists():
        return cases
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


def _donor_is_clean_no_terminal_source(donor: Path) -> bool:
    chunk = _extract_object_chunk(read_internal_file(donor, "ROOT.DSN"))
    return chunk.count(BIDIR_MARKER) == 0 and chunk.count(b"\x7fWIRE") == 0


def _generate_two_pin_terminal_case(
    *,
    family: str,
    case_dir: Path,
) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = _payload(family, force_two_pin_donor=True)
    placed = case_dir / f"{case_dir.name}_placed.pdsprj"
    final = case_dir / f"{case_dir.name}_sa.pdsprj"

    placement = generate_component_placement_project(payload, placed, donor_path=TWO_PIN_DONOR)
    terminal_report = attach_component_bidir_terminals_to_project(
        placed,
        final,
        placement.selected_groups,
        terminal_families=[family],
    )

    _write_json(case_dir / "input.json", payload)
    _write_json(case_dir / "placement_manifest.json", placement.as_dict())
    _write_json(case_dir / "terminal_report.json", terminal_report)
    return {
        "case": case_dir.name,
        "family": family,
        "kind": "accepted_two_pin",
        "input_json": str((case_dir / "input.json").relative_to(REPO)),
        "placed_project": str(placed.relative_to(REPO)),
        "final_project": str(final.relative_to(REPO)),
        "placement_valid": placement.valid,
        "terminal_valid": bool(terminal_report["valid"]),
        "terminal_count_added": terminal_report["terminal_count_added"],
        "wire_count_added": terminal_report["wire_count_added"],
        "wire_count_after": terminal_report["wire_count_after"],
        "terminal_suffix_links_valid": terminal_report["terminal_suffix_links_valid"],
        "wire_path_contacts_valid": terminal_report["wire_path_contacts_valid"],
        "terminal_grid_alignment_valid": terminal_report["terminal_grid_alignment_valid"],
        "donor": str(placement.donor.relative_to(REPO)),
        "status": "generated",
    }


def _generate_existing_anchor_terminal_case(
    *,
    family: str,
    donor: Path,
    case_dir: Path,
) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = _payload(family, donor=donor)
    placed = case_dir / f"{case_dir.name}_placed.pdsprj"
    final = case_dir / f"{case_dir.name}_sa.pdsprj"

    placement = generate_component_placement_project(payload, placed, donor_path=donor)
    terminal_report = attach_catalogue_pin_bidir_terminals_to_project(
        placed,
        final,
        placement.selected_groups,
        terminal_families=[family],
    )

    _write_json(case_dir / "input.json", payload)
    _write_json(case_dir / "placement_manifest.json", placement.as_dict())
    _write_json(case_dir / "terminal_report.json", terminal_report)
    return {
        "case": case_dir.name,
        "family": family,
        "kind": "v9_existing_anchor_multi_pin",
        "input_json": str((case_dir / "input.json").relative_to(REPO)),
        "placed_project": str(placed.relative_to(REPO)),
        "final_project": str(final.relative_to(REPO)),
        "placement_valid": placement.valid,
        "terminal_valid": bool(terminal_report["valid"]),
        "terminal_count_added": terminal_report["terminal_count_added"],
        "wire_count_added": terminal_report["wire_count_added"],
        "wire_count_rewritten": terminal_report["wire_count_rewritten"],
        "wire_count_after": terminal_report["wire_count_after"],
        "terminal_suffix_links_valid": terminal_report["terminal_suffix_links_valid"],
        "wire_path_contacts_valid": terminal_report["wire_path_contacts_valid"],
        "terminal_grid_alignment_valid": terminal_report["terminal_grid_alignment_valid"],
        "donor": str(donor.relative_to(REPO)),
        "status": "generated",
    }


def _generate_no_terminal_control(
    *,
    family: str,
    case_dir: Path,
    donor: Path | None = None,
) -> dict[str, object]:
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = _payload(family, donor=donor)
    output = case_dir / f"{case_dir.name}.pdsprj"
    attempts: list[tuple[str, Path | None]] = [("default_component_placer", None)]
    if donor is not None and _donor_is_clean_no_terminal_source(donor):
        attempts.insert(0, ("clean_donor_base", donor))

    last_error: Exception | None = None
    for source_label, donor_path in attempts:
        try:
            placement = generate_component_placement_project(
                payload,
                output,
                donor_path=donor_path,
            )
        except Exception as exc:  # noqa: BLE001 - evidence runner records blockers.
            last_error = exc
            continue
        _write_json(case_dir / "input.json", payload)
        _write_json(case_dir / "placement_manifest.json", placement.as_dict())
        return {
            "case": case_dir.name,
            "family": family,
            "kind": "no_terminal_control",
            "source": source_label,
            "input_json": str((case_dir / "input.json").relative_to(REPO)),
            "project": str(output.relative_to(REPO)),
            "placement_valid": placement.valid,
            "donor": str(placement.donor.relative_to(REPO)),
            "status": "generated",
        }
    return {
        "case": case_dir.name,
        "family": family,
        "kind": "no_terminal_control",
        "status": "blocked",
        "error": (
            "no generation attempt succeeded"
            if last_error is None
            else f"{type(last_error).__name__}: {last_error}"
        ),
    }


def _readme(summary: dict[str, object]) -> str:
    terminal_cases = list(summary["terminal_cases"])  # type: ignore[index]
    blocked = dict(summary["blocked_terminal_families"])  # type: ignore[index]
    return (
        "# Terminal recovery solo 1x - 2026-07-08\n\n"
        "This pack is a rollback-style recovery baseline after user Proteus "
        "testing rejected the V10 catalogue link-offset pack.\n\n"
        "Every terminalized case is a 1x solo. No multi-count and no mixed pack "
        "is generated here.\n\n"
        f"- Terminalized 1x cases: {len(terminal_cases)}\n"
        "- Final terminalized projects end with `_sa.pdsprj`.\n"
        "- Every case folder includes the exact `input.json` passed into the generator.\n\n"
        "## Terminalized cases\n\n"
        + "\n".join(
            f"- `{case['case']}`: `{case['family']}` via {case['kind']}, "
            f"valid={case['terminal_valid']}, terminals={case['terminal_count_added']}"
            for case in terminal_cases
        )
        + "\n\n## Blocked terminalized families\n\n"
        + "\n".join(f"- `{family}`: {reason}" for family, reason in sorted(blocked.items()))
        + "\n\n## Proteus check\n\n"
        "Open only the `*_sa.pdsprj` files first. If any fail, report the case "
        "folder name and whether the no-terminal control for the same family opens.\n"
    )


def main() -> None:
    if OUTPUT_ROOT.exists():
        shutil.rmtree(OUTPUT_ROOT)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()

    donor_cases = _donor_cases()
    terminal_cases: list[dict[str, object]] = []
    terminal_errors: list[dict[str, object]] = []
    controls: list[dict[str, object]] = []

    index = 1
    for family in ACCEPTED_TWO_PIN_FAMILIES:
        case_dir = OUTPUT_ROOT / _case_name("S", index, family, "ACCEPTED_TERMINAL")
        try:
            terminal_cases.append(
                _generate_two_pin_terminal_case(family=family, case_dir=case_dir)
            )
        except Exception as exc:  # noqa: BLE001 - evidence runner records blockers.
            terminal_errors.append(
                {
                    "case": case_dir.name,
                    "family": family,
                    "kind": "accepted_two_pin",
                    "status": "blocked",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
        index += 1

    for family in V9_EXISTING_ANCHOR_MULTI_PIN_FAMILIES:
        case_dir = OUTPUT_ROOT / _case_name("S", index, family, "EXISTING_ANCHOR_TERMINAL")
        donor = donor_cases.get(family)
        if donor is None:
            terminal_errors.append(
                {
                    "case": case_dir.name,
                    "family": family,
                    "kind": "v9_existing_anchor_multi_pin",
                    "status": "blocked",
                    "error": "donor-base project missing",
                }
            )
        else:
            try:
                terminal_cases.append(
                    _generate_existing_anchor_terminal_case(
                        family=family,
                        donor=donor,
                        case_dir=case_dir,
                    )
                )
            except Exception as exc:  # noqa: BLE001 - evidence runner records blockers.
                terminal_errors.append(
                    {
                        "case": case_dir.name,
                        "family": family,
                        "kind": "v9_existing_anchor_multi_pin",
                        "status": "blocked",
                        "error": f"{type(exc).__name__}: {exc}",
                        "donor": str(donor.relative_to(REPO)),
                    }
                )
        index += 1

    control_families = sorted(
        set(ACCEPTED_TWO_PIN_FAMILIES)
        | set(V9_EXISTING_ANCHOR_MULTI_PIN_FAMILIES)
        | set(BLOCKED_TERMINAL_FAMILIES)
        | set(donor_cases)
    )
    for control_index, family in enumerate(control_families, start=1):
        controls.append(
            _generate_no_terminal_control(
                family=family,
                donor=donor_cases.get(family),
                case_dir=OUTPUT_ROOT / _case_name("E", control_index, family, "NO_TERMINAL_CONTROL"),
            )
        )

    blocked = {
        family: reason
        for family, reason in BLOCKED_TERMINAL_FAMILIES.items()
        if family not in ACCEPTED_TWO_PIN_FAMILIES
        and family not in V9_EXISTING_ANCHOR_MULTI_PIN_FAMILIES
    }
    for row in terminal_errors:
        blocked.setdefault(str(row["family"]), str(row["error"]))

    summary: dict[str, object] = {
        "experiment": OUTPUT_ROOT.name,
        "purpose": "1x-only Proteus terminal recovery baseline after V10 rejection",
        "accepted_two_pin_families": list(ACCEPTED_TWO_PIN_FAMILIES),
        "v9_existing_anchor_multi_pin_families": list(V9_EXISTING_ANCHOR_MULTI_PIN_FAMILIES),
        "terminal_cases": terminal_cases,
        "terminal_errors": terminal_errors,
        "no_terminal_controls": controls,
        "blocked_terminal_families": blocked,
        "notes": [
            "V10 catalogue link-offset/bare-WIRE generation is disabled.",
            "No mixed pack and no count scaling is generated in this recovery checkpoint.",
            "This runner contains no terminal-placement logic.",
            "Every case stores input.json beside the generated project.",
        ],
    }
    _write_json(OUTPUT_ROOT / "summary.json", summary)
    (OUTPUT_ROOT / "README.md").write_text(_readme(summary), encoding="utf-8")
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUTPUT_ROOT)
    summary["archive"] = str(ARCHIVE.relative_to(REPO))
    summary["archive_sha256"] = _sha256(ARCHIVE)
    _write_json(OUTPUT_ROOT / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
