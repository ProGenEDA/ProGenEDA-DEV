from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import (  # noqa: E402
    NEW_COMPONENT_MEGA_DONOR,
    _repo_path,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_component_bidir_terminals_to_project,
)


EXPERIMENT_NAME = "terminal_placer_all_two_pin_v12_visual_stress_temp_2026_07_03"
ARCHIVE_NAME = "TERMINAL_PLACER_ALL_TWO_PIN_V12_VISUAL_STRESS_TEMP_2026_07_03.zip"
DONOR = _repo_path(NEW_COMPONENT_MEGA_DONOR)
EXPECTED_DONOR_SHA256 = (
    "1222561d29622193d4eaa34aa830a341dee47abe376d1b971390dd6baad7958c"
)
CASE_ID = "M01_ALL_TWO_PIN_20X_EACH_NATIVE_V12_VISUAL_STRESS"
ALL_TWO_PIN_FAMILIES = [
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
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _payload() -> dict[str, Any]:
    return {
        "donor": str(DONOR.relative_to(ROOT)),
        "components": {family: 20 for family in ALL_TWO_PIN_FAMILIES},
        "component_offsets": {"CAP-ELEC": 21},
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
            "mixed_ic_non_ic_bands": "separate",
        },
    }


def _readme(
    *,
    donor_sha: str,
    case_summary: dict[str, Any],
) -> str:
    families = ", ".join(ALL_TWO_PIN_FAMILIES)
    return f"""# Terminal Placer All Two-Pin V12 Visual Stress Temp

## Scope

This pack contains one requested stress circuit: 20 of every currently profiled
two-pin family, passed through component placement, beautification, and the
shared terminal placer.

- Donor: `{DONOR.relative_to(ROOT).as_posix()}`
- Donor SHA256: `{donor_sha}`
- Runtime circuit donor dependency: false
- Component count: {case_summary["component_count"]}
- Bidirectional terminals: {case_summary["terminal_count"]}
- Short WIRE records: {case_summary["wire_count"]}
- Final WIRE-address link allocations: {case_summary["link_allocation_count"]}
- Label jitters for low-16 WIRE-address uniqueness: {case_summary["label_jitter_count"]}
- Proteus status: static checks passed locally; manual Proteus open/render/sim
  check pending

## Families

{families}

## V12 Focus

- LED-RED, 40EPS08, and FUSE now place terminal contacts one extra Proteus grid
  step outward while still using short WIRE records back to the exact component
  pins. This addresses the three crowded visuals reported after V11.
- Large mixed projects use deterministic final WIRE-address allocation with
  collision-safe terminal-label jitter. This keeps active terminal suffixes
  unique even when the serialized object stream exceeds 64 KiB.
- DIODE repeated selection skips the donor infrastructure key `D20`.
- FUSE repeated selection keeps the donor-native anonymous packets; validation
  no longer treats the repeated anonymous `FUSE` marker as a duplicate visible
  component reference.

## Proteus Check

Open:

`{CASE_ID}/{CASE_ID}.pdsprj`

Check for:

1. No Bad Object Record.
2. Exactly 20 components for each listed family.
3. Every component has two nearby bidirectional terminals.
4. LED-RED, 40EPS08, and FUSE terminals are visually less crowded than V11.
5. Every terminal has a short wire from the grid contact to the exact pin.
6. Netlist/simulation does not report detached terminal links.
"""


def main() -> None:
    donor_sha = _sha256(DONOR)
    if donor_sha != EXPECTED_DONOR_SHA256:
        raise RuntimeError(
            f"Unexpected donor SHA for {DONOR}: {donor_sha}; "
            f"expected {EXPECTED_DONOR_SHA256}."
        )

    out_dir = ROOT / "experiments" / EXPERIMENT_NAME
    archive = ROOT / "experiments" / ARCHIVE_NAME
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    if archive.exists():
        archive.unlink()

    case_dir = out_dir / CASE_ID
    case_dir.mkdir(parents=True)
    payload = _payload()
    base = case_dir / f"{CASE_ID}_BASE.pdsprj"
    output = case_dir / f"{CASE_ID}.pdsprj"

    placement = generate_component_placement_project(payload, base, full_cdb=True)
    if not placement.valid:
        raise RuntimeError(f"{CASE_ID} placement failed: {placement.errors}")
    terminal_report = attach_component_bidir_terminals_to_project(
        base,
        output,
        placement.selected_groups,
    )
    if not terminal_report["valid"]:
        raise RuntimeError(f"{CASE_ID} terminal placement failed static validation.")

    _write_json(case_dir / "input.json", payload)
    _write_json(case_dir / "placement_report.json", placement.as_dict())
    _write_json(case_dir / "terminal_plan.json", terminal_report)
    (case_dir / "WHAT_TO_CHECK.txt").write_text(
        f"{CASE_ID}\n\n"
        "Open the PDS project in Proteus and check the V12 stress criteria from "
        "the top-level README.\n",
        encoding="utf-8",
    )

    case_summary = {
        "case_id": CASE_ID,
        "component_count": len(placement.selected_groups),
        "components": payload["components"],
        "output": str(output.relative_to(out_dir)),
        "base": str(base.relative_to(out_dir)),
        "placement_valid": placement.valid,
        "terminal_static_valid": terminal_report["valid"],
        "terminal_count": terminal_report["terminal_count_added"],
        "wire_count": terminal_report["wire_count_added"],
        "eligible_families": terminal_report["eligible_families"],
        "skipped_families": terminal_report["skipped_families"],
        "link_allocation_valid": terminal_report["link_allocation"]["valid"],
        "link_allocation_count": terminal_report["link_allocation"]["allocation_count"],
        "label_jitter_count": terminal_report["wire_address_label_jitter"][
            "event_count"
        ],
    }
    _write_json(out_dir / "summary.json", case_summary)
    (out_dir / "README.md").write_text(
        _readme(
            donor_sha=donor_sha,
            case_summary=case_summary,
        ),
        encoding="utf-8",
    )
    shutil.make_archive(str(archive.with_suffix("")), "zip", out_dir)
    archive_sha = _sha256(archive)
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "archive": str(archive),
                "archive_sha256": archive_sha,
                "donor": str(DONOR),
                "donor_sha256": donor_sha,
                **case_summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
