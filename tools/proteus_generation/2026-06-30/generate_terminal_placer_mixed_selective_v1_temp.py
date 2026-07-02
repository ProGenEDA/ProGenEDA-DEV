from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import generate_component_placement_project  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    ACCEPTED_TERMINAL_FAMILY_ORDER,
    attach_component_bidir_terminals_to_project,
)
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


EXPERIMENT_NAME = "terminal_placer_mixed_selective_v1_temp_2026_06_30"
ARCHIVE_NAME = "TERMINAL_PLACER_MIXED_SELECTIVE_V1_TEMP_2026_06_30.zip"
DONOR_ID = "component_placer_main_15x_semimega_sources_20260618"
ACCEPTED_FAMILIES = tuple(ACCEPTED_TERMINAL_FAMILY_ORDER)
CONTROL_FAMILIES = ("DIODE", "NPN", "74HC08")

CASES: tuple[tuple[str, dict[str, int]], ...] = (
    (
        "T01_ALL_ACCEPTED_1X_WITH_CONTROLS",
        {
            "RESISTOR": 1,
            "CAP": 1,
            "CAP-ELEC": 1,
            "REALIND": 1,
            "VSOURCE": 1,
            "CSOURCE": 1,
            "DIODE": 1,
            "NPN": 1,
            "74HC08": 1,
        },
    ),
    (
        "T02_ALL_ACCEPTED_3X_WITH_CONTROLS",
        {
            "RESISTOR": 3,
            "CAP": 3,
            "CAP-ELEC": 3,
            "REALIND": 3,
            "VSOURCE": 3,
            "CSOURCE": 3,
            "DIODE": 3,
            "NPN": 2,
            "74HC08": 2,
        },
    ),
    (
        "T03_NONTERMINAL_CONTROLS_ONLY",
        {
            "DIODE": 3,
            "NPN": 2,
            "74HC08": 2,
        },
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _payload(case_id: str, components: dict[str, int]) -> dict[str, Any]:
    return {
        "schema": "progen-terminal-mixed-selective-test/v0.1",
        "name": case_id,
        "donor": DONOR_ID,
        "components": components,
        "layout": {
            "strategy": "beautify",
            "direction": "left_to_right",
        },
        "routing": {
            "mode": "terminal",
            "terminal_policy": "accepted_family_handlers_only",
        },
    }


def _validate_case(
    *,
    payload: dict[str, Any],
    base: Path,
    output: Path,
    placement: Any,
    terminal_report: dict[str, Any],
) -> dict[str, Any]:
    requested = payload["components"]
    accepted_count = sum(requested.get(family, 0) for family in ACCEPTED_FAMILIES)
    control_count = sum(requested.get(family, 0) for family in CONTROL_FAMILIES)
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))
    final_chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    selected_counts = Counter(group.family for group in placement.selected_groups)
    actual_layout = placement.layout_plan["binary_coordinate_mutation"]
    family_reports = terminal_report.get("family_reports", [])
    terminal_pair_families = {
        pair["component_family"]
        for report in family_reports
        for pair in report.get("terminal_pairs", [])
    }
    expected_eligible = [
        family for family in ACCEPTED_FAMILIES if requested.get(family, 0)
    ]
    expected_skipped = sorted(
        family for family in CONTROL_FAMILIES if requested.get(family, 0)
    )
    errors: list[str] = []

    if not placement.valid:
        errors.append("component placement failed")
    if selected_counts != Counter(requested):
        errors.append(
            f"selected counts differ: actual={dict(selected_counts)} expected={requested}"
        )
    if actual_layout.get("visible_translated_count") != sum(requested.values()):
        errors.append("beautifier did not translate every selected component packet")
    if base_chunk.count(b"$TERBIDIR") != 0 or base_chunk.count(b"\x7fWIRE") != 0:
        errors.append("component-placer base is not terminal/wire free")
    if not terminal_report.get("valid"):
        errors.append("terminal report failed")
    if terminal_report.get("eligible_families") != expected_eligible:
        errors.append("eligible-family dispatch differs from the accepted allowlist")
    if terminal_report.get("skipped_families") != expected_skipped:
        errors.append("non-terminal control-family list differs")
    if terminal_report.get("terminal_count_added") != accepted_count * 2:
        errors.append("terminal count does not equal two per accepted component")
    if terminal_report.get("wire_count_added") != accepted_count * 2:
        errors.append("wire count does not equal two per accepted component")
    if terminal_pair_families - set(ACCEPTED_FAMILIES):
        errors.append("a non-accepted component received terminals")
    if terminal_pair_families & set(CONTROL_FAMILIES):
        errors.append("a negative-control family received terminals")
    if terminal_report.get("preserved_component_count") != control_count:
        errors.append("not every negative-control component was preserved")
    if not all(
        row.get("byte_preserved")
        for row in terminal_report.get("preserved_groups", [])
    ):
        errors.append("a negative-control packet changed")
    if accepted_count:
        if not terminal_report.get("terminal_suffixes_unique"):
            errors.append("terminal suffixes are not globally unique")
        if not terminal_report.get("terminal_suffix_links_valid"):
            errors.append("terminal suffix links are not globally paired")
        if final_chunk.count(b"$TERBIDIR") != accepted_count * 2:
            errors.append("final object terminal marker count differs")
        if final_chunk.count(b"\x7fWIRE") != accepted_count * 2:
            errors.append("final object wire marker count differs")
    elif base.read_bytes() != output.read_bytes():
        errors.append("control-only terminal stage was not an exact project copy")

    return {
        "valid": not errors,
        "errors": errors,
        "requested_components": requested,
        "selected_counts": dict(sorted(selected_counts.items())),
        "accepted_component_count": accepted_count,
        "negative_control_component_count": control_count,
        "terminal_count": terminal_report.get("terminal_count_added", 0),
        "wire_count": terminal_report.get("wire_count_added", 0),
        "eligible_families": terminal_report.get("eligible_families", []),
        "skipped_families": terminal_report.get("skipped_families", []),
        "terminal_pair_families": sorted(terminal_pair_families),
        "base_object_chunk_size": len(base_chunk),
        "final_object_chunk_size": len(final_chunk),
        "base_sha256": _sha256(base),
        "output_sha256": _sha256(output),
        "control_only_exact_copy": (
            base.read_bytes() == output.read_bytes() if not accepted_count else None
        ),
    }


def _readme() -> str:
    return """# Mixed selective terminal placer V1

This pack exercises the actual reusable pipeline:

`input.json -> component placer -> binary beautifier -> shared terminal placer`

The accepted terminal allowlist is:

- RESISTOR/v3
- CAP/v2
- CAP-ELEC/v3
- REALIND/v2
- VSOURCE/v4
- CSOURCE/v4

DIODE, NPN, and 74HC08 are deliberate negative controls. Their complete
beautified component packets must remain byte-identical and must receive no
terminal or short-wire records.

## Proteus checks

Open the non-`_BASE` project in each case.

1. T01: one of every accepted family plus one of each negative control.
2. T02: three of every accepted family plus repeated negative controls.
3. T03: negative controls only. Its final project is byte-identical to `_BASE`.

For T01/T02, verify that each accepted two-pin component has exactly two
attached bidirectional terminals. Verify that DIODE, NPN, and all four units of
each 74HC08 package remain terminal-free. Report open, render, and simulation
results separately because static validation is not Proteus acceptance.
"""


def main() -> None:
    experiment = ROOT / "experiments" / EXPERIMENT_NAME
    archive = ROOT / "experiments" / ARCHIVE_NAME
    if experiment.exists():
        resolved = experiment.resolve()
        expected_parent = (ROOT / "experiments").resolve()
        if resolved.parent != expected_parent:
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
        shutil.rmtree(resolved)
    experiment.mkdir(parents=True)
    if archive.exists():
        archive.unlink()

    summaries: list[dict[str, Any]] = []
    for case_id, components in CASES:
        case_dir = experiment / case_id
        case_dir.mkdir()
        payload_path = case_dir / "input.json"
        payload_path.write_text(
            json.dumps(_payload(case_id, components), indent=2) + "\n",
            encoding="utf-8",
        )
        payload = json.loads(payload_path.read_text(encoding="utf-8"))

        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        placement = generate_component_placement_project(
            payload,
            base,
            full_cdb=True,
        )
        if not placement.valid:
            raise RuntimeError(
                f"{case_id} component placement failed: "
                f"{[issue.as_dict() for issue in placement.errors]}"
            )
        terminal_report = attach_component_bidir_terminals_to_project(
            base,
            output,
            placement.selected_groups,
        )
        validation = _validate_case(
            payload=payload,
            base=base,
            output=output,
            placement=placement,
            terminal_report=terminal_report,
        )
        if not validation["valid"]:
            raise RuntimeError(f"{case_id} failed: {validation['errors']}")

        (case_dir / "terminal_plan.json").write_text(
            json.dumps(terminal_report, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "validation.json").write_text(
            json.dumps(validation, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "TEST.txt").write_text(
            f"Case: {case_id}\n"
            f"Accepted components: {validation['accepted_component_count']}\n"
            f"Negative controls: {validation['negative_control_component_count']}\n"
            f"Expected terminals: {validation['terminal_count']}\n"
            f"Expected short wires: {validation['wire_count']}\n"
            "Open the project without _BASE for Proteus testing.\n",
            encoding="utf-8",
        )
        summaries.append({"case": case_id, **validation})

    summary = {
        "schema": "terminal-placer-mixed-selective-summary/v0.1",
        "experiment": EXPERIMENT_NAME,
        "pipeline": [
            "json_input",
            "component_placer",
            "component_beautifier",
            "component_terminal_placer",
        ],
        "accepted_terminal_families": list(ACCEPTED_FAMILIES),
        "negative_control_families": list(CONTROL_FAMILIES),
        "case_count": len(summaries),
        "all_static_valid": all(case["valid"] for case in summaries),
        "cases": summaries,
    }
    (experiment / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    (experiment / "README.md").write_text(_readme(), encoding="utf-8")

    shutil.make_archive(
        str(archive.with_suffix("")),
        "zip",
        root_dir=experiment.parent,
        base_dir=experiment.name,
    )
    print(json.dumps({**summary, "archive": str(archive), "archive_sha256": _sha256(archive)}, indent=2))


if __name__ == "__main__":
    main()
