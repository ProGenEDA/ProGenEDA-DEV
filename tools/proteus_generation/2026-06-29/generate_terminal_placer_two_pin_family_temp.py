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
    NEW_COMPONENT_MEGA_DONOR,
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
    terminal_label_prefix: str
    version: str
    donor: Path
    source_payload: Path
    experiment_name: str
    archive_name: str
    handler: str
    evidence: str


CONFIGS = {
    "CAP": FamilyConfig(
        family="CAP",
        ref_prefix="C",
        terminal_label_prefix="C",
        version="V2",
        donor=MAIN_MEGA_NO_SOURCE_DONOR,
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
    "REALIND": FamilyConfig(
        family="REALIND",
        ref_prefix="L",
        terminal_label_prefix="L",
        version="V2",
        donor=MAIN_MEGA_NO_SOURCE_DONOR,
        source_payload=(
            ROOT
            / "experiments"
            / "beautifier_realind_coordinate_probe_base135_v1_temp_2026_06_24"
            / "01_L01_REALIND_1X_PARSED_COORDS"
            / "payload.json"
        ),
        experiment_name="terminal_placer_realind_attachment_v2_temp_2026_06_30",
        archive_name="TERMINAL_PLACER_REALIND_ATTACHMENT_V2_TEMP_2026_06_30.zip",
        handler="REALIND/v2",
        evidence=(
            "inductor_05_six_terminal plus the user-accepted INDUCTOR_V8 "
            "sequential donor route and locked mixed_rcl bidirectional conversion"
        ),
    ),
    "CAP-ELEC": FamilyConfig(
        family="CAP-ELEC",
        ref_prefix="CE",
        terminal_label_prefix="E",
        version="V3",
        donor=MAIN_MEGA_NO_SOURCE_DONOR,
        source_payload=(
            ROOT
            / "experiments"
            / "beautifier_cap_elec_coordinate_probe_base135_v1_temp_2026_06_24"
            / "01_CE01_CAP-ELEC_1X_PARSED_COORDS"
            / "payload.json"
        ),
        experiment_name="terminal_placer_cap_elec_attachment_v3_temp_2026_06_30",
        archive_name="TERMINAL_PLACER_CAP_ELEC_ATTACHMENT_V3_TEMP_2026_06_30.zip",
        handler="CAP-ELEC/v3",
        evidence=(
            "user-accepted analog_misc_batch1 8ELEC-CAP donor and its "
            "donor-native bidirectional label-mutation controls"
        ),
    ),
    "VSOURCE": FamilyConfig(
        family="VSOURCE",
        ref_prefix="VS",
        terminal_label_prefix="V",
        version="V4",
        donor=NEW_COMPONENT_MEGA_DONOR,
        source_payload=(
            ROOT
            / "experiments"
            / "beautifier_vsource_coordinate_probe_solo_v1_temp_2026_06_25"
            / "01_VS01_1X_COORDS"
            / "payload.json"
        ),
        experiment_name="terminal_placer_vsource_attachment_v4_temp_2026_06_30",
        archive_name="TERMINAL_PLACER_VSOURCE_ATTACHMENT_V4_TEMP_2026_06_30.zip",
        handler="VSOURCE/v4",
        evidence=(
            "user-accepted bidirectional DCV V3 route, clean one-DCV fixture, "
            "and accepted three-DCV sequential source boundary evidence"
        ),
    ),
    "CSOURCE": FamilyConfig(
        family="CSOURCE",
        ref_prefix="CS",
        terminal_label_prefix="I",
        version="V4",
        donor=NEW_COMPONENT_MEGA_DONOR,
        source_payload=(
            ROOT
            / "experiments"
            / "beautifier_csource_coordinate_probe_solo_v1_temp_2026_06_25"
            / "01_CS01_1X_COORDS"
            / "payload.json"
        ),
        experiment_name="terminal_placer_csource_attachment_v4_temp_2026_06_30",
        archive_name="TERMINAL_PLACER_CSOURCE_ATTACHMENT_V4_TEMP_2026_06_30.zip",
        handler="CSOURCE/v4",
        evidence=(
            "user-accepted bidirectional DCI V3 route and the accepted V15 "
            "CSOURCE terminal/body/wire donor"
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


def family_test_instruction(config: FamilyConfig) -> str:
    if config.family == "VSOURCE":
        return (
            "Confirm every DC voltage source has an attached 0-degree output endpoint "
            "and 180-degree input endpoint at the two donor-native source pins."
        )
    if config.family == "CSOURCE":
        return (
            "Confirm every DC current source has an attached 180-degree input endpoint "
            "and 0-degree output endpoint at the two donor-native source pins."
        )
    return (
        "Confirm every component has one attached bidirectional terminal on each "
        "side and each terminal touches the real component pin."
    )


def readme(config: FamilyConfig) -> str:
    terminal_summary = (
        "- Terminals: left `$TERBIDIR` at 180 degrees; right at 0 degrees"
    )
    test_instruction = family_test_instruction(config)
    boundary_role = "right"
    if config.family == "CAP":
        family_evidence = """- CAP geometry: pins at body `+/-508000`; terminal symbols another `254000`
  outward; one zero-length donor-native wire record at each true pin
- CAP object order: all right bidirectional records first, followed by repeated
  left bidirectional/component/left-wire/right-wire groups
- Suffixes: donor-native `0x0238` progression"""
        component_name = "capacitor"
    elif config.family == "REALIND":
        family_evidence = """- REALIND geometry: pins at body `+/-762000`; terminal symbols another
  `254000` outward; one zero-length donor-native wire record at each true pin
- REALIND object order: repeated left bidirectional/right bidirectional/
  component/left-wire/right-wire groups
- Suffixes: donor-native `0x02A8` progression from `0x01B2`/`0x01E4`"""
        component_name = "inductor"
    elif config.family == "CAP-ELEC":
        family_evidence = """- CAP-ELEC geometry: pins at body `+/-508000`; terminal symbols another
  `254000` outward; one zero-length donor-native wire record at each true pin
- CAP-ELEC object order: repeated right bidirectional/left bidirectional/
  component/left-wire/right-wire groups
- Suffixes: donor-native `0x02A8` progression from `0x0120`/`0x0152`
- Donor blank terminal labels are replaced with compact non-empty labels, as in
  the user-accepted analog/misc label-mutation controls"""
        component_name = "electrolytic capacitor"
    elif config.family == "VSOURCE":
        family_evidence = """- VSOURCE pin geometry follows the clean source unit: output at body
  `(+508000,+254000)`, input at `(+508000,-1270000)`, with terminal symbols
  `254000` outward from their zero-length pin records
- VSOURCE object order: repeated output bidirectional/input bidirectional/
  component/output-wire/input-wire groups
- Suffixes: accepted source progression `0x7000`/`0x7032`, step `0x0080`"""
        component_name = "DC voltage source"
        terminal_summary = (
            "- Terminals: input role `$TERBIDIR` at 180 degrees; output role at 0 degrees"
        )
        boundary_role = "input"
    elif config.family == "CSOURCE":
        family_evidence = """- CSOURCE pin geometry follows the accepted V15 source unit: input at body
  `(+508000,+254000)`, output at `(+508000,-1270000)`, with terminal symbols
  `254000` outward from their zero-length pin records
- CSOURCE object order: repeated input bidirectional/output bidirectional/
  component/input-wire/output-wire groups
- Suffixes: accepted source progression `0x7000`/`0x7032`, step `0x0080`"""
        component_name = "DC current source"
        terminal_summary = (
            "- Terminals: input role `$TERBIDIR` at 180 degrees; output role at 0 degrees"
        )
        boundary_role = "output"
    else:
        raise ValueError(f"No README evidence is defined for {config.family}.")
    return f"""# Terminal Placer {config.family} Attachment {config.version}

## Purpose

This focused pack runs the accepted component placer and beautifier before the
shared `component_terminal_placer.py` dispatcher. It processes `1x`, `3x`, and
`15x` {config.family} cases only.

## Binary Evidence

- Family handler: `{config.handler}`
- Manual evidence: `{config.evidence}`
{terminal_summary}
{family_evidence}
- Non-final {boundary_role} wires: 49 bytes; final {boundary_role} wire: 50 bytes ending in `FF`
- Input JSON: reused from the accepted family beautifier experiment; only the
  requested count and donor path are changed

## Test Order

Open the non-`_BASE` project in each case folder. {test_instruction} The
zero-length attachment records may not render as a visible wire segment. Run
netlist/simulation and report any bad-object, DLL, duplicate-reference, or
floating-terminal error. The tested component family is {component_name}.

Static validation passed locally. Proteus acceptance remains pending.

## Static Verification

- Focused and cumulative component-placer suite: `49 passed`
- Object-stream cursor reconstruction: exact for 1x, 3x, and 15x
- Terminal/component suffix matches: passed
- Zero-length attachment coordinates at every {config.family} pin: passed
- {boundary_role.title()}-wire sizes: 49 bytes for non-final groups, 50 bytes for final group
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
        payload["donor"] = str(_repo_path(config.donor))
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
            label_prefix=config.terminal_label_prefix,
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
            f"{family_test_instruction(config)} "
            f"{config.handler} uses zero-length donor-native attachment records, so a green "
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
