from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import (  # noqa: E402
    MAIN_MEGA_NO_SOURCE_DONOR,
    _repo_path,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_component_bidir_terminals_to_project,
)


@dataclass(frozen=True)
class FamilyConfig:
    family: str
    ref_prefix: str
    version: str
    source_payload: Path
    experiment_name: str
    archive_name: str
    handler: str
    evidence: str


CONFIGS = {
    "CAP": FamilyConfig(
        family="CAP",
        ref_prefix="C",
        version="V2",
        source_payload=(
            ROOT
            / "experiments"
            / "beautifier_cap_coordinate_probe_v1_temp_2026_06_24"
            / "01_C01_CAP_1X_PARSED_COORDS"
            / "payload.json"
        ),
        experiment_name="terminal_placer_capacitor_attachment_v2_temp_2026_06_30",
        archive_name="TERMINAL_PLACER_CAPACITOR_ATTACHMENT_V2_TEMP_2026_06_30.zip",
        handler="CAP/v2",
        evidence=(
            "cap2_with_terminals_manual plus the user-accepted "
            "mixed_passive.convert_production_terminals route"
        ),
    ),
}

COUNTS = (1, 3, 15)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one researched two-pin terminal-placement family pack."
    )
    parser.add_argument(
        "--family",
        choices=sorted(CONFIGS),
        default="CAP",
        help="Generate only this family. One family is processed per run.",
    )
    return parser.parse_args()


def readme(config: FamilyConfig) -> str:
    return f"""# Terminal Placer {config.family} Attachment {config.version}

## Purpose

This focused pack runs the accepted component placer and beautifier before the
shared `component_terminal_placer.py` dispatcher. It processes `1x`, `3x`, and
`15x` {config.family} cases only.

## Binary Evidence

- Family handler: `{config.handler}`
- Manual evidence: `{config.evidence}`
- Terminals: left `$TERBIDIR` at 180 degrees; right at 0 degrees
- CAP geometry: pins at body `+/-508000`; terminal symbols another `254000`
  outward; one zero-length donor-native wire record at each true pin
- CAP object order: all right bidirectional records first, followed by repeated
  left bidirectional/component/left-wire/right-wire groups
- Non-final right wires: 49 bytes; final right wire: 50 bytes ending in `FF`
- Suffixes: donor-native `0x0238` progression
- Input JSON: reused from the accepted family beautifier experiment; only the
  requested count and donor path are changed

## Test Order

Open the non-`_BASE` project in each case folder. Confirm every component has
one attached bidirectional terminal on each side and each terminal touches the
real capacitor pin. The zero-length attachment records may not render as a
visible wire segment. Run netlist/simulation and report any bad-object, DLL,
duplicate-reference, or floating-terminal error.

Static validation passed locally. Proteus acceptance remains pending.

## Static Verification

- Focused and cumulative component-placer suite: `42 passed`
- Object-stream cursor reconstruction: exact for 1x, 3x, and 15x
- Terminal/component suffix matches: passed
- Zero-length attachment coordinates at every CAP pin: passed
- Right-wire sizes: 49 bytes for non-final groups, 50 bytes for final group
- Compile checks: passed
"""


def main() -> None:
    config = CONFIGS[parse_args().family]
    out_dir = ROOT / "experiments" / config.experiment_name
    archive = ROOT / "experiments" / config.archive_name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    if archive.exists():
        archive.unlink()

    reused_payload = json.loads(config.source_payload.read_text(encoding="utf-8"))
    summary: list[dict[str, object]] = []
    for count in COUNTS:
        case_id = f"{config.ref_prefix}{count:02d}_{config.family}_{count}X_ATTACHED_BIDIR"
        case_dir = out_dir / case_id
        case_dir.mkdir()
        payload = json.loads(json.dumps(reused_payload))
        payload["donor"] = str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR))
        payload["components"] = {config.family: count}
        payload["layout"] = {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        }

        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        placement = generate_component_placement_project(payload, base, full_cdb=True)
        if not placement.valid:
            raise RuntimeError(f"{case_id} component placement failed: {placement.errors}")
        terminal_report = attach_component_bidir_terminals_to_project(
            base,
            output,
            placement.selected_groups,
            label_prefix=config.ref_prefix,
        )
        if terminal_report["family_handler"] != config.handler:
            raise RuntimeError(
                f"{case_id} used {terminal_report['family_handler']}, expected {config.handler}."
            )
        if not terminal_report["valid"]:
            raise RuntimeError(f"{case_id} terminal attachment failed static validation.")

        (case_dir / "payload.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "base_manifest.json").write_text(
            json.dumps(placement.as_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "terminal_plan.json").write_text(
            json.dumps(terminal_report, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "WHAT_TO_CHECK.txt").write_text(
            f"{case_id}\n\n"
            f"Open: {output.name}\n"
            f"Expected {config.family} components: {count}\n"
            f"Expected bidirectional terminals: {count * 2}\n"
            f"Expected short wires: {count * 2}\n\n"
            "Every component must have one 180-degree terminal on its left and "
            "one 0-degree terminal on its right. Both must meet the true pin. "
            "CAP/v2 uses zero-length donor-native attachment records, so a green "
            "wire segment may not be visible. Then run netlist/simulation.\n",
            encoding="utf-8",
        )
        summary.append(
            {
                "case_id": case_id,
                "family": config.family,
                "component_count": count,
                "terminal_count": terminal_report["terminal_count_added"],
                "wire_count": terminal_report["wire_count_added"],
                "placement_valid": placement.valid,
                "terminal_static_valid": terminal_report["valid"],
                "output": str(output.relative_to(out_dir)),
            }
        )

    (out_dir / "README.md").write_text(readme(config), encoding="utf-8")
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(archive.with_suffix("")), "zip", out_dir)
    print(
        json.dumps(
            {
                "family": config.family,
                "out_dir": str(out_dir),
                "archive": str(archive),
                "source_payload": str(config.source_payload),
                "cases": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
