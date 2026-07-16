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

from proteusgen.component_beautifier import MIXED_LAYOUT_BAND_GAP_Y  # noqa: E402
from proteusgen.component_placer import generate_component_placement_project  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_component_bidir_terminals_to_project,
    attach_mixed_overlay_bidir_terminals_to_project,
)
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


EXPERIMENT_NAME = "terminal_placer_mixed_overlay_v3_temp_2026_07_01"
ARCHIVE_NAME = "TERMINAL_PLACER_MIXED_OVERLAY_V3_TEMP_2026_07_01.zip"
DONOR_ID = "component_placer_main_15x_semimega_sources_20260618"
ALL_ACCEPTED = (
    "RESISTOR",
    "CAP",
    "REALIND",
    "CAP-ELEC",
    "VSOURCE",
    "CSOURCE",
)
PASSIVES = ("RESISTOR", "CAP", "REALIND", "CAP-ELEC")
SOURCES = ("VSOURCE", "CSOURCE")
CONTROLS = ("DIODE", "NPN", "74HC08")
COMPONENTS = {
    "RESISTOR": 1,
    "CAP": 1,
    "CAP-ELEC": 1,
    "REALIND": 1,
    "VSOURCE": 1,
    "CSOURCE": 1,
    "DIODE": 1,
    "NPN": 1,
    "74HC08": 1,
}
CASES: tuple[dict[str, Any], ...] = (
    {
        "case_id": "T00_ALL_BARE_SEPARATED_BANDS",
        "families": (),
        "patch_links": False,
        "active_links": False,
        "include_wires": False,
        "route": "shared_copy",
    },
    {
        "case_id": "T01_APPENDED_TERMINALS_OPENING_ORDER",
        "families": ALL_ACCEPTED,
        "patch_links": False,
        "active_links": False,
        "include_wires": False,
        "route": "overlay_diagnostic",
    },
    {
        "case_id": "T02_FULL_ATTACHMENT_OVERLAY",
        "families": ALL_ACCEPTED,
        "patch_links": True,
        "active_links": True,
        "include_wires": True,
        "route": "shared_terminal_placer",
    },
    {
        "case_id": "T03_PASSIVE_ATTACHMENT_OVERLAY",
        "families": PASSIVES,
        "patch_links": True,
        "active_links": True,
        "include_wires": True,
        "route": "shared_terminal_placer",
    },
    {
        "case_id": "T04_SOURCE_ATTACHMENT_OVERLAY",
        "families": SOURCES,
        "patch_links": True,
        "active_links": True,
        "include_wires": True,
        "route": "shared_terminal_placer",
    },
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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
        "schema": "progen-terminal-mixed-overlay-test/v0.3",
        "name": case["case_id"],
        "donor": DONOR_ID,
        "components": COMPONENTS,
        "layout": {
            "strategy": "beautify",
            "direction": "left_to_right",
            "mixed_ic_non_ic_bands": "separate",
        },
        "routing": {
            "mode": "terminal",
            "temporary_mixed_policy": (
                "component_stream_then_terminal_wire_overlay"
            ),
            "terminal_families": list(case["families"]),
            "patch_component_links": case["patch_links"],
            "active_terminal_links": case["active_links"],
            "include_wires": case["include_wires"],
            "route": case["route"],
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
        "ic_keys": [entry["key"] for entry in ic_entries],
        "non_ic_keys": [entry["key"] for entry in non_ic_entries],
        "ic_max_y": ic_max_y,
        "non_ic_min_y": non_ic_min_y,
        "clearance": clearance,
        "required_clearance": MIXED_LAYOUT_BAND_GAP_Y,
    }


def _run_terminal_stage(
    case: dict[str, Any],
    base: Path,
    output: Path,
    selected_groups: tuple[Any, ...],
) -> dict[str, Any]:
    if case["route"] in {"shared_copy", "shared_terminal_placer"}:
        return attach_component_bidir_terminals_to_project(
            base,
            output,
            selected_groups,
            terminal_families=case["families"],
        )
    return attach_mixed_overlay_bidir_terminals_to_project(
        base,
        output,
        selected_groups,
        terminal_families=case["families"],
        patch_component_links=case["patch_links"],
        active_terminal_links=case["active_links"],
        include_wires=case["include_wires"],
    )


def _validate_case(
    *,
    case: dict[str, Any],
    base: Path,
    output: Path,
    placement: Any,
    report: dict[str, Any],
) -> dict[str, Any]:
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    family_count = len(case["families"])
    expected_terminals = family_count * 2
    expected_wires = expected_terminals if case["include_wires"] else 0
    selected_counts = Counter(group.family for group in placement.selected_groups)
    terminal_pair_families = {
        pair["component_family"]
        for family_report in report.get("family_reports", [])
        for pair in family_report.get("terminal_pairs", [])
    }
    layout = _layout_report(placement)
    info = inspect_pdsprj(output)
    errors: list[str] = []

    if not placement.valid:
        errors.append("component placement failed")
    if selected_counts != Counter(COMPONENTS):
        errors.append("selected counts differ from input JSON")
    if not layout["valid"]:
        errors.append(f"IC/non-IC band separation failed: {layout}")
    if base_chunk.count(b"$TERBIDIR") or base_chunk.count(b"\x7fWIRE"):
        errors.append("beautified base is not terminal/wire free")
    if not report.get("valid"):
        errors.append("terminal overlay report failed")
    if set(report.get("eligible_families", [])) != set(case["families"]):
        errors.append("terminal-family allowlist differs from input JSON")
    if terminal_pair_families != set(case["families"]):
        errors.append("terminal pairs were assigned to the wrong families")
    if report.get("terminal_count_added") != expected_terminals:
        errors.append("terminal count differs")
    if report.get("wire_count_added") != expected_wires:
        errors.append("wire count differs")
    if final_chunk.count(b"$TERBIDIR") != expected_terminals:
        errors.append("final terminal marker count differs")
    if final_chunk.count(b"\x7fWIRE") != expected_wires:
        errors.append("final wire marker count differs")
    if report.get("component_record_order_mutation") is True:
        errors.append("component record order changed")
    if report.get("component_stream_prefix_preserved") is False:
        errors.append("component stream is not the output prefix")
    if not all(
        row.get("byte_preserved")
        for row in report.get("preserved_groups", [])
    ):
        errors.append("a non-selected component packet changed")
    if not all(
        (info.has_project_xml, info.has_root_dsn, info.has_root_cdb, info.has_pwrails)
    ):
        errors.append("required project files are missing")
    if not case["families"] and base.read_bytes() != output.read_bytes():
        errors.append("all-bare control is not an exact project copy")

    return {
        "valid": not errors,
        "errors": errors,
        "route": case["route"],
        "terminal_families": list(case["families"]),
        "patch_component_links": case["patch_links"],
        "active_terminal_links": case["active_links"],
        "include_wires": case["include_wires"],
        "layout": layout,
        "terminal_count": report.get("terminal_count_added", 0),
        "wire_count": report.get("wire_count_added", 0),
        "terminal_pair_families": sorted(terminal_pair_families),
        "component_stream_prefix_preserved": report.get(
            "component_stream_prefix_preserved",
            base.read_bytes() == output.read_bytes(),
        ),
        "base_sha256": _sha256(base),
        "output_sha256": _sha256(output),
        "exact_copy": base.read_bytes() == output.read_bytes(),
    }


def _readme() -> str:
    return """# Mixed terminal append-overlay V3 temporary pack

The previous V1 pack failed because it rebuilt independently accepted family
blocks into a new mixed object order. This V3 pack uses the older order that
the user confirmed opened successfully:

`beautified component stream -> appended terminals -> appended wires`

The component stream stays first and keeps its original component order.
Accepted RESISTOR, CAP, REALIND, CAP-ELEC, VSOURCE, and CSOURCE link fields are
patched in place. DIODE, NPN, and 74HC08 remain byte-preserved and terminal-free.

The beautifier now places 74HC08 on an upper IC band and all non-IC components
on a lower band with 5,080,000 internal units of clearance.

## Test in order

1. `T00`: exact-copy all-bare control; inspect IC/non-IC separation.
2. `T01`: appended terminals only. This reproduces the historically opening
   record order but deliberately leaves terminals unattached.
3. `T02`: intended temporary fix: all six accepted families attached with
   donor-derived wire records.
4. `T03`: passive-only attachment ablation.
5. `T04`: source-only attachment ablation.

Report open, render, attachment, and simulation separately for every case.
T01 is a positive order control, not the desired final attachment result.
"""


def main() -> None:
    experiment = ROOT / "proteus" / "experiments" / "runs" / EXPERIMENT_NAME
    archive = ROOT / "proteus" / "experiments" / "runs" / ARCHIVE_NAME
    if experiment.exists():
        resolved = experiment.resolve()
        expected_parent = (ROOT / "proteus" / "experiments" / "runs").resolve()
        if resolved.parent != expected_parent:
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
        shutil.rmtree(resolved)
    experiment.mkdir(parents=True)
    if archive.exists():
        archive.unlink()

    summaries: list[dict[str, Any]] = []
    for case in CASES:
        case_id = case["case_id"]
        case_dir = experiment / case_id
        case_dir.mkdir()
        input_path = case_dir / "input.json"
        input_path.write_text(
            json.dumps(_payload(case), indent=2) + "\n",
            encoding="utf-8",
        )
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        placement = generate_component_placement_project(
            payload,
            base,
            full_cdb=True,
        )
        if not placement.valid:
            raise RuntimeError(
                f"{case_id} placement failed: "
                f"{[issue.as_dict() for issue in placement.errors]}"
            )
        report = _run_terminal_stage(
            case,
            base,
            output,
            placement.selected_groups,
        )
        validation = _validate_case(
            case=case,
            base=base,
            output=output,
            placement=placement,
            report=report,
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
            f"Terminal families: {', '.join(case['families']) or 'NONE'}\n"
            f"Expected terminals: {validation['terminal_count']}\n"
            f"Expected wires: {validation['wire_count']}\n"
            f"IC/non-IC clearance: {validation['layout']['clearance']}\n"
            "Open the project without _BASE in Proteus.\n",
            encoding="utf-8",
        )
        summaries.append({"case": case_id, **validation})

    summary = {
        "schema": "terminal-placer-mixed-overlay-summary/v0.3",
        "experiment": EXPERIMENT_NAME,
        "status": "static_valid_pending_proteus",
        "historical_basis": (
            "all-family V2 appended-terminal projects opened but terminals floated"
        ),
        "rejected_v1_order": "independently_rebuilt_family_blocks",
        "candidate_v3_order": "component_stream_then_terminals_then_wires",
        "case_count": len(summaries),
        "all_static_valid": all(case["valid"] for case in summaries),
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
