from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "proteus" / "active" / "src"))

from proteusgen.bidirectional import extract_bidir_records  # noqa: E402
from proteusgen.component_beautifier import MIXED_LAYOUT_BAND_GAP_Y  # noqa: E402
from proteusgen.component_placer import generate_component_placement_project  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_component_bidir_terminals_to_project,
    attach_mixed_overlay_bidir_terminals_to_project,
)
from proteusgen.pdsprj import (  # noqa: E402
    inspect_pdsprj,
    read_internal_file,
)
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


EXPERIMENT_NAME = "terminal_placer_short_wire_v6_temp_2026_07_01"
ARCHIVE_NAME = "TERMINAL_PLACER_SHORT_WIRE_V6_TEMP_2026_07_01.zip"
DONOR_ID = "component_placer_main_15x_semimega_sources_20260618"
CTRL_S_FIXTURE = (
    ROOT / "proteus" / "active" / "fixtures" / "pdsprj" / "t06_resistor_ctrl_s_repair_20260701.pdsprj"
)
ACCEPTED_FAMILIES = (
    "RESISTOR",
    "CAP",
    "REALIND",
    "CAP-ELEC",
    "VSOURCE",
    "CSOURCE",
)
CONTROLS = ("DIODE", "NPN", "74HC08")


def _components(count: int, *, mixed: bool) -> dict[str, int]:
    components = (
        {family: count for family in ACCEPTED_FAMILIES}
        if mixed
        else {"RESISTOR": count}
    )
    components.update({family: 1 for family in CONTROLS})
    return components


CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "T01_GENERATED_CTRL_S_EQUIVALENT",
        "components": _components(1, mixed=False),
        "terminal_families": ("RESISTOR",),
        "include_wires": False,
        "expected_ctrl_s_object_match": True,
    },
    {
        "case_id": "T02_RESISTOR_1X_SHORT_WIRE",
        "components": _components(1, mixed=False),
        "terminal_families": ("RESISTOR",),
        "include_wires": True,
    },
    {
        "case_id": "T03_RESISTOR_3X_SHORT_WIRE",
        "components": _components(3, mixed=False),
        "terminal_families": ("RESISTOR",),
        "include_wires": True,
    },
    {
        "case_id": "T04_RESISTOR_15X_SHORT_WIRE",
        "components": _components(15, mixed=False),
        "terminal_families": ("RESISTOR",),
        "include_wires": True,
    },
    {
        "case_id": "T05_MIXED_1X_SHORT_WIRE",
        "components": _components(1, mixed=True),
        "terminal_families": ACCEPTED_FAMILIES,
        "include_wires": True,
    },
    {
        "case_id": "T06_MIXED_3X_SHORT_WIRE",
        "components": _components(3, mixed=True),
        "terminal_families": ACCEPTED_FAMILIES,
        "include_wires": True,
    },
    {
        "case_id": "T07_MIXED_15X_SHORT_WIRE",
        "components": _components(15, mixed=True),
        "terminal_families": ACCEPTED_FAMILIES,
        "include_wires": True,
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_deterministic_archive(experiment: Path, archive: Path) -> None:
    if archive.exists():
        archive.unlink()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
        for file_path in sorted(experiment.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(
                file_path.relative_to(experiment.parent).as_posix(),
                date_time=(2026, 7, 1, 0, 0, 0),
            )
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            output.writestr(info, file_path.read_bytes())


def _payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "progen-terminal-short-wire-test/v0.6",
        "name": case["case_id"],
        "donor": DONOR_ID,
        "components": case["components"],
        "layout": {
            "strategy": "beautify",
            "direction": "left_to_right",
            "mixed_ic_non_ic_bands": "separate",
        },
        "routing": {
            "mode": "terminal",
            "method": "t01_terminal_placement_then_short_wire_only",
            "terminal_families": list(case["terminal_families"]),
            "patch_component_links": False,
            "active_terminal_links": False,
            "inactive_terminal_suffix": 0,
            "include_wires": case["include_wires"],
        },
    }


def _layout_report(placement: Any) -> dict[str, Any]:
    entries = placement.layout_plan["actual_binary_placements"]
    ic_entries = [entry for entry in entries if entry.get("layout_band") == "ic"]
    non_ic_entries = [
        entry for entry in entries if entry.get("layout_band") == "non_ic"
    ]
    if not ic_entries or not non_ic_entries:
        return {"valid": False, "error": "missing IC or non-IC layout band"}
    ic_max_y = max(int(entry["after_bbox"]["max_y"]) for entry in ic_entries)
    non_ic_min_y = min(
        int(entry["after_bbox"]["min_y"]) for entry in non_ic_entries
    )
    clearance = non_ic_min_y - ic_max_y
    return {
        "valid": clearance >= MIXED_LAYOUT_BAND_GAP_Y,
        "clearance": clearance,
        "required_clearance": MIXED_LAYOUT_BAND_GAP_Y,
    }


def _terminal_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "component_key": pair["component_key"],
            "component_family": pair["component_family"],
            "role": role,
            **pair[role],
        }
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
        for role in (
            ("left", "right")
            if pair.get("left")
            else ("input", "output")
        )
    ]


def _expected_wire_coordinates(
    report: dict[str, Any],
) -> list[tuple[int, int, int, int]]:
    return sorted(
        (
            wire["start"]["x"],
            wire["start"]["y"],
            wire["end"]["x"],
            wire["end"]["y"],
        )
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
        for wire in pair["short_wires"].values()
    )


def _actual_wire_coordinates(
    chunk: bytes,
    wire_count: int,
) -> tuple[list[tuple[int, int, int, int]], int]:
    if wire_count == 0:
        return [], len(chunk)
    coordinates: list[tuple[int, int, int, int]] = []
    cursor = chunk.find(b"\x7fWIRE") - 23
    if cursor < 0:
        raise RuntimeError("WIRE marker count is nonzero but no wire start was found.")
    for pair_index in range(wire_count // 2):
        sizes = (50, 50 if pair_index == wire_count // 2 - 1 else 49)
        for size in sizes:
            record = chunk[cursor : cursor + size]
            marker = record.find(b"\x7fWIRE")
            coordinate_start = marker - 23
            coordinates.append(
                tuple(
                    int.from_bytes(
                        record[
                            coordinate_start + offset :
                            coordinate_start + offset + 4
                        ],
                        "little",
                        signed=True,
                    )
                    for offset in (33, 37, 41, 45)
                )
            )
            cursor += size
    return sorted(coordinates), cursor


def _validate_case(
    case: dict[str, Any],
    base: Path,
    output: Path,
    placement: Any,
    report: dict[str, Any],
) -> dict[str, Any]:
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    terminals = extract_bidir_records(chunk)
    terminal_rows = _terminal_rows(report)
    expected_terminal_count = sum(
        count
        for family, count in Counter(
            group.family for group in placement.selected_groups
        ).items()
        if family in case["terminal_families"]
    ) * 2
    expected_wire_count = (
        expected_terminal_count if case["include_wires"] else 0
    )
    actual_wires, wire_cursor = _actual_wire_coordinates(
        chunk,
        expected_wire_count,
    )
    expected_wires = (
        _expected_wire_coordinates(report)
        if case["include_wires"]
        else []
    )
    left_roles = [
        row for row in terminal_rows if row["role"] in {"left", "input"}
    ]
    right_roles = [
        row for row in terminal_rows if row["role"] in {"right", "output"}
    ]
    info = inspect_pdsprj(output)
    errors: list[str] = []

    if not placement.valid:
        errors.append("component placement failed")
    if Counter(group.family for group in placement.selected_groups) != Counter(
        case["components"]
    ):
        errors.append("selected component counts differ from input")
    if not _layout_report(placement)["valid"]:
        errors.append("mixed layout-band clearance failed")
    if base_chunk.count(b"$TERBIDIR") or base_chunk.count(b"\x7fWIRE"):
        errors.append("base is not terminal/wire free")
    if not report["valid"]:
        errors.append("terminal report failed")
    if len(terminals) != expected_terminal_count:
        errors.append("terminal record count differs")
    if chunk.count(b"\x7fWIRE") != expected_wire_count:
        errors.append("wire record count differs")
    if not all(record[-4:] == b"\x00\x00\x00\x00" for record in terminals):
        errors.append("an inactive terminal has a nonzero suffix/link tail")
    if not all(row["angle_tenths"] == 1800 for row in left_roles):
        errors.append("a left/input terminal is not 180 degrees")
    if not all(row["angle_tenths"] == 0 for row in right_roles):
        errors.append("a right/output terminal is not 0 degrees")
    if case["include_wires"] and actual_wires != expected_wires:
        errors.append("actual short-wire coordinates differ from the plan")
    if case["include_wires"] and wire_cursor != len(chunk):
        errors.append("wire cursor did not consume the complete object stream")
    if not all(row["byte_preserved"] for row in report["preserved_groups"]):
        errors.append("an unsupported control packet changed")
    if report["patch_component_links"] or report["active_terminal_links"]:
        errors.append("a non-wire attachment method was enabled")
    if not all(
        (info.has_project_xml, info.has_root_dsn, info.has_root_cdb, info.has_pwrails)
    ):
        errors.append("required project files are missing")
    ctrl_s_match = None
    if case.get("expected_ctrl_s_object_match"):
        ctrl_s_chunk = _extract_object_chunk(
            read_internal_file(CTRL_S_FIXTURE, "ROOT.DSN")
        )
        ctrl_s_match = chunk == ctrl_s_chunk
        if not ctrl_s_match:
            errors.append("generated terminal-only chunk differs from Ctrl+S repair")

    resistor_wires = [
        coordinates
        for family_report in report["family_reports"]
        for pair in family_report["terminal_pairs"]
        if pair["component_family"] == "RESISTOR"
        for coordinates in (
            (
                wire["start"]["x"],
                wire["start"]["y"],
                wire["end"]["x"],
                wire["end"]["y"],
            )
            for wire in pair["short_wires"].values()
        )
    ]
    return {
        "valid": not errors,
        "errors": errors,
        "terminal_count": len(terminals),
        "wire_count": chunk.count(b"\x7fWIRE"),
        "inactive_terminal_tails_zero": all(
            record[-4:] == b"\x00\x00\x00\x00" for record in terminals
        ),
        "left_input_angles_1800": all(
            row["angle_tenths"] == 1800 for row in left_roles
        ),
        "right_output_angles_0": all(
            row["angle_tenths"] == 0 for row in right_roles
        ),
        "actual_wires_match_plan": actual_wires == expected_wires,
        "resistor_wire_lengths": [
            {
                "x": abs(x2 - x1),
                "y": abs(y2 - y1),
            }
            for x1, y1, x2, y2 in resistor_wires
        ],
        "ctrl_s_object_chunk_match": ctrl_s_match,
        "layout": _layout_report(placement),
        "base_sha256": _sha256(base),
        "output_sha256": _sha256(output),
        "object_chunk_sha256": hashlib.sha256(chunk).hexdigest(),
    }


def _readme() -> str:
    return """# Short-wire-only terminal V6 temporary pack

This pack uses one attachment method only:

`T01 terminal coordinates/orientation/labels -> donor-derived short WIRE -> pin`

Inactive terminal suffix/link tails are all zero. This matches the supplied
Proteus Ctrl+S repair. Terminal-only streams retain the complete last terminal
record and use a separate final FF sentinel.

RESISTOR uses 254,000-unit contact-to-pin wires. CAP, REALIND, CAP-ELEC,
VSOURCE, and CSOURCE retain their accepted zero-length pin-coincident WIRE
records. Left/input bidirectional terminals remain 180 degrees; right/output
terminals remain 0 degrees. DIODE, NPN, and 74HC08 controls are byte-preserved
and terminal-free.

## Test in order

0. `T00_USER_CTRL_S_EXACT`: exact copy of the supplied saved repair.
1. `T01_GENERATED_CTRL_S_EQUIVALENT`: generated terminal-only control whose
   object chunk is byte-identical to T00; verify Bad Object Record is gone.
2. `T02_RESISTOR_1X_SHORT_WIRE`
3. `T03_RESISTOR_3X_SHORT_WIRE`
4. `T04_RESISTOR_15X_SHORT_WIRE`
5. `T05_MIXED_1X_SHORT_WIRE`
6. `T06_MIXED_3X_SHORT_WIRE`
7. `T07_MIXED_15X_SHORT_WIRE`

For T02-T07 report: Bad Object Record, open/render, short-wire appearance,
terminal orientation, electrical attachment, and simulation.
"""


def main() -> None:
    if not CTRL_S_FIXTURE.exists():
        raise FileNotFoundError(CTRL_S_FIXTURE)
    experiment = ROOT / "proteus" / "experiments" / "runs" / EXPERIMENT_NAME
    archive = ROOT / "proteus" / "experiments" / "runs" / ARCHIVE_NAME
    if experiment.exists():
        resolved = experiment.resolve()
        experiments_root = (ROOT / "proteus" / "experiments" / "runs").resolve()
        if experiments_root not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
        shutil.rmtree(resolved)
    experiment.mkdir(parents=True)

    ctrl_dir = experiment / "T00_USER_CTRL_S_EXACT"
    ctrl_dir.mkdir()
    ctrl_output = ctrl_dir / "T00_USER_CTRL_S_EXACT.pdsprj"
    shutil.copyfile(CTRL_S_FIXTURE, ctrl_output)
    (ctrl_dir / "TEST.txt").write_text(
        "Exact user Ctrl+S repair. Open first and confirm no Bad Object Record.\n",
        encoding="utf-8",
    )
    summaries: list[dict[str, Any]] = [
        {
            "case": "T00_USER_CTRL_S_EXACT",
            "valid": True,
            "source": "user_ctrl_s_repair",
            "output_sha256": _sha256(ctrl_output),
            "object_chunk_sha256": hashlib.sha256(
                _extract_object_chunk(read_internal_file(ctrl_output, "ROOT.DSN"))
            ).hexdigest(),
        }
    ]

    for case in CASES:
        case_id = case["case_id"]
        case_dir = experiment / case_id
        case_dir.mkdir()
        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        payload = _payload(case)
        (case_dir / "input.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        placement = generate_component_placement_project(
            payload,
            base,
            full_cdb=True,
        )
        if not placement.valid:
            raise RuntimeError(f"{case_id} placement failed.")
        if case["include_wires"]:
            report = attach_component_bidir_terminals_to_project(
                base,
                output,
                placement.selected_groups,
                terminal_families=case["terminal_families"],
            )
        else:
            report = attach_mixed_overlay_bidir_terminals_to_project(
                base,
                output,
                placement.selected_groups,
                terminal_families=case["terminal_families"],
                patch_component_links=False,
                active_terminal_links=False,
                include_wires=False,
            )
        validation = _validate_case(
            case,
            base,
            output,
            placement,
            report,
        )
        if not validation["valid"]:
            raise RuntimeError(f"{case_id} failed: {validation['errors']}")
        (case_dir / "terminal_plan.json").write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "validation.json").write_text(
            json.dumps(validation, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "TEST.txt").write_text(
            f"Case: {case_id}\n"
            f"Terminals: {validation['terminal_count']}\n"
            f"Wires: {validation['wire_count']}\n"
            "Connection method: short WIRE only\n"
            "Check Bad Object Record, render, orientation, attachment, and simulation.\n",
            encoding="utf-8",
        )
        summaries.append({"case": case_id, **validation})

    generated_ctrl = next(
        row
        for row in summaries
        if row["case"] == "T01_GENERATED_CTRL_S_EQUIVALENT"
    )
    if (
        generated_ctrl["object_chunk_sha256"]
        != summaries[0]["object_chunk_sha256"]
    ):
        raise RuntimeError("Generated Ctrl+S-equivalent control hash differs.")
    summary = {
        "schema": "terminal-placer-short-wire-summary/v0.6",
        "experiment": EXPERIMENT_NAME,
        "status": "static_valid_pending_proteus",
        "attachment_method": "t01_terminals_then_short_wire_only",
        "bad_object_repairs": [
            "inactive terminal suffix/link tail is 00000000",
            "terminal-only stream appends a separate final FF sentinel",
        ],
        "ctrl_s_fixture_sha256": _sha256(CTRL_S_FIXTURE),
        "case_count": len(summaries),
        "all_static_valid": all(case["valid"] for case in summaries),
        "generated_ctrl_s_object_match": True,
        "cases": summaries,
    }
    (experiment / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    (experiment / "README.md").write_text(_readme(), encoding="utf-8")
    _write_deterministic_archive(experiment, archive)
    print(
        json.dumps(
            {
                **summary,
                "archive": str(archive),
                "archive_sha256": _sha256(archive),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
