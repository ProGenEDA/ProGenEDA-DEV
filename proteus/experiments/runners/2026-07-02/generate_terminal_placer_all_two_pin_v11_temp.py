from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "proteus" / "active" / "src"))

from proteusgen.component_placer import (  # noqa: E402
    NEW_COMPONENT_MEGA_DONOR,
    _repo_path,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_component_bidir_terminals_to_project,
)


EXPERIMENT_NAME = "terminal_placer_all_two_pin_v11_temp_2026_07_02"
ARCHIVE_NAME = "TERMINAL_PLACER_ALL_TWO_PIN_V11_TEMP_2026_07_02.zip"
DONOR = _repo_path(NEW_COMPONENT_MEGA_DONOR)
EXPECTED_DONOR_SHA256 = (
    "1222561d29622193d4eaa34aa830a341dee47abe376d1b971390dd6baad7958c"
)
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
SCALED_SOLO_FAMILIES = [
    family for family in ALL_TWO_PIN_FAMILIES if family not in {"DIODE", "FUSE"}
]
KNOWN_COMPONENT_PLACER_SCALE_LIMITS = {
    "DIODE": (
        "3x selection reaches D20, which is a display bridge/sentinel packet; "
        "1x/2x remain valid from this donor."
    ),
    "FUSE": (
        "Repeated FUSE packets are anonymous in the donor, so repeated refs are "
        "not a valid terminal-placer checkpoint until the component catalogue "
        "exposes stable unique FUSE identities."
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _payload(components: dict[str, int]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "donor": str(DONOR.relative_to(ROOT)),
        "components": components,
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
            "mixed_ic_non_ic_bands": "separate",
        },
    }
    if "CAP-ELEC" in components:
        payload["component_offsets"] = {"CAP-ELEC": 21}
    return payload


def _case_name(prefix: str, family: str | None, counts: dict[str, int]) -> str:
    if family is not None:
        count = counts[family]
        return f"{prefix}_{family.replace('-', '_')}_{count}X_NATIVE_V11"
    total = sum(counts.values())
    return f"{prefix}_MIXED_ALL_TWO_PIN_{total}C_NATIVE_V11"


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _generate_case(
    root: Path,
    *,
    case_id: str,
    components: dict[str, int],
    description: str,
) -> dict[str, Any]:
    case_dir = root / case_id
    case_dir.mkdir(parents=True)
    payload = _payload(components)
    base = case_dir / f"{case_id}_BASE.pdsprj"
    output = case_dir / f"{case_id}.pdsprj"

    placement = generate_component_placement_project(payload, base, full_cdb=True)
    if not placement.valid:
        raise RuntimeError(f"{case_id} placement failed: {placement.errors}")
    terminal_report = attach_component_bidir_terminals_to_project(
        base,
        output,
        placement.selected_groups,
    )
    if not terminal_report["valid"]:
        raise RuntimeError(f"{case_id} terminal placement failed static validation.")

    _write_json(case_dir / "input.json", payload)
    _write_json(case_dir / "placement_report.json", placement.as_dict())
    _write_json(case_dir / "terminal_plan.json", terminal_report)
    (case_dir / "WHAT_TO_CHECK.txt").write_text(
        f"{case_id}\n\n"
        f"{description}\n\n"
        f"Open `{output.name}` in Proteus.\n"
        f"Expected components: {sum(components.values())}\n"
        f"Expected bidirectional terminals: {terminal_report['terminal_count_added']}\n"
        f"Expected short wires: {terminal_report['wire_count_added']}\n\n"
        "Check: no Bad Object Record, every terminal is on a Proteus grid contact, "
        "every terminal has a short wire from that contact to the component pin, "
        "and simulation/netlist does not report floating terminal attachment errors.\n",
        encoding="utf-8",
    )
    return {
        "case_id": case_id,
        "description": description,
        "components": components,
        "output": str(output.relative_to(root)),
        "base": str(base.relative_to(root)),
        "placement_valid": placement.valid,
        "terminal_static_valid": terminal_report["valid"],
        "terminal_count": terminal_report["terminal_count_added"],
        "wire_count": terminal_report["wire_count_added"],
        "eligible_families": terminal_report["eligible_families"],
        "skipped_families": terminal_report["skipped_families"],
        "link_allocation_valid": terminal_report["link_allocation"]["valid"],
    }


def _readme(summary: list[dict[str, Any]], donor_sha: str) -> str:
    solo_cases = [row for row in summary if row["case_id"].startswith("S")]
    mixed_cases = [row for row in summary if row["case_id"].startswith("M")]
    scaled_skips = "\n".join(
        f"- {family}: {reason}"
        for family, reason in KNOWN_COMPONENT_PLACER_SCALE_LIMITS.items()
    )
    return f"""# Terminal Placer All Two-Pin V11 Temp

## Scope

This pack uses the shared `src/proteusgen/component_terminal_placer.py` native
unit route for every currently profiled two-pin family.

- Donor: `{DONOR.relative_to(ROOT).as_posix()}`
- Donor SHA256: `{donor_sha}`
- Terminal route: active `$TERBIDIR` + patched component pin-link field + donor
  schema 50-byte short `WIRE`, rebased from final `ROOT.DSN` addresses
- Runtime circuit donor dependency: false
- Component coordinate mutation in terminal stage: false
- Status: static validation passed locally; Proteus acceptance pending

## Families

{", ".join(ALL_TWO_PIN_FAMILIES)}

## Cases

- Solo cases: {len(solo_cases)}
- Mixed cases: {len(mixed_cases)}
- Total generated cases: {len(summary)}

## Scaled Solo Limits

Two families are intentionally 1x-only in this checkpoint because their repeated
selection is blocked before terminal placement:

{scaled_skips}

## Proteus Test Order

1. Open every `S*_1X_NATIVE_V11.pdsprj` solo first.
2. Open the `S*_3X_NATIVE_V11.pdsprj` scaled solos next.
3. Open `M01_MIXED_ALL_TWO_PIN_19C_NATIVE_V11.pdsprj`.
4. Open `M02_MIXED_ALL_TWO_PIN_SAFE_SCALE_NATIVE_V11.pdsprj`.

For each case, check for Bad Object Record, missing rendered wires, detached
terminals, wrong endpoint orientation, and netlist/simulation terminal errors.
"""


def main() -> None:
    donor_sha = _sha256(DONOR)
    if donor_sha != EXPECTED_DONOR_SHA256:
        raise RuntimeError(
            f"Unexpected donor SHA for {DONOR}: {donor_sha}; "
            f"expected {EXPECTED_DONOR_SHA256}."
        )

    out_dir = ROOT / "proteus" / "experiments" / "runs" / EXPERIMENT_NAME
    archive = ROOT / "proteus" / "experiments" / "runs" / ARCHIVE_NAME
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    if archive.exists():
        archive.unlink()

    summary: list[dict[str, Any]] = []
    for index, family in enumerate(ALL_TWO_PIN_FAMILIES, start=1):
        summary.append(
            _generate_case(
                out_dir,
                case_id=_case_name(f"S{index:02d}", family, {family: 1}),
                components={family: 1},
                description=f"Solo 1x checkpoint for {family}.",
            )
        )
    for index, family in enumerate(SCALED_SOLO_FAMILIES, start=1):
        summary.append(
            _generate_case(
                out_dir,
                case_id=_case_name(f"T{index:02d}", family, {family: 3}),
                components={family: 3},
                description=f"Solo 3x scaled checkpoint for {family}.",
            )
        )

    mixed_1x = {family: 1 for family in ALL_TWO_PIN_FAMILIES}
    summary.append(
        _generate_case(
            out_dir,
            case_id="M01_MIXED_ALL_TWO_PIN_19C_NATIVE_V11",
            components=mixed_1x,
            description="Mixed 1x project containing every two-pin family.",
        )
    )

    mixed_safe_scale = {
        family: (1 if family in KNOWN_COMPONENT_PLACER_SCALE_LIMITS else 3)
        for family in ALL_TWO_PIN_FAMILIES
    }
    summary.append(
        _generate_case(
            out_dir,
            case_id="M02_MIXED_ALL_TWO_PIN_SAFE_SCALE_NATIVE_V11",
            components=mixed_safe_scale,
            description=(
                "Mixed scaled project: clean families at 3x, DIODE/FUSE at 1x "
                "because their repeated donor selection is not a terminal-stage "
                "checkpoint yet."
            ),
        )
    )

    _write_json(out_dir / "summary.json", summary)
    (out_dir / "README.md").write_text(_readme(summary, donor_sha), encoding="utf-8")
    shutil.make_archive(str(archive.with_suffix("")), "zip", out_dir)
    print(
        json.dumps(
            {
                "out_dir": str(out_dir),
                "archive": str(archive),
                "donor": str(DONOR),
                "donor_sha256": donor_sha,
                "case_count": len(summary),
                "cases": [
                    {
                        "case_id": row["case_id"],
                        "terminal_count": row["terminal_count"],
                        "wire_count": row["wire_count"],
                        "output": row["output"],
                    }
                    for row in summary
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
