"""Generate the expanded bidirectional-terminal pre-lock regression pack."""

from __future__ import annotations

import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
HERE = Path(__file__).resolve().parent
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from proteusgen.mixed_passive import generate_mixed_passive_project_from_payload
from proteusgen.mixed_passive_examples import mixed_6_case
from proteusgen.mixed_rcl import generate_mixed_rcl_project_from_payload
from proteusgen.mixed_rcl_examples import mixed_rcl_21_case, mixed_rcl_15_cases
from proteusgen.resistor_examples import predefined_resistor_cases
from proteusgen.resistor_v9 import generate_resistor_project_from_payload
from proteusgen.source_driven import generate_source_driven_project_from_payload
from proteusgen.templates import FixtureRegistry

import generate_bidirectional_v2_orientation_dcv_temp as v2
from bidirectional_dcv_temp import load_dcv_unit_template
from bidirectional_temp import load_templates


OUT = ROOT / "experiments" / "bidirectional_v3_prelock_temp_2026_06_07"
ARCHIVE = ROOT / "experiments" / "BIDIRECTIONAL_V3_PRELOCK_TEMP_2026_06_07.zip"
V1_DONORS = ROOT / "experiments" / "bidirectional_v1_temp_2026_06_07" / "donors"
USER_ONE_DCV = Path(r"C:\Users\tahab\Downloads\1DCV.pdsprj")


def _single_family_payload(mode: str, name: str) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-mixed-rcl-locked",
        "project": {"name": name, "output_basename": name, "base": "E001_EMPTY_BASE"},
        "groups": [
            {"mode": mode, "start": "V0", "end": "N1"},
            {"mode": mode, "start": "N1", "end": "G0"},
            {"mode": mode, "start": "V0", "end": "G0"},
            {"mode": mode, "start": "N1", "end": "N2"},
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _source_payload(
    *,
    name: str,
    kind: str,
    ref: str,
    value: str,
    positive: str,
    negative: str,
    groups: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": name, "output_basename": name, "base": "E001_EMPTY_BASE"},
        "groups": groups,
        "sources": [
            {
                "kind": kind,
                "ref": ref,
                "value": value,
                "positive": positive,
                "negative": negative,
            }
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _one_dcv_bridge() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "BIDIR_V3_DCV_BRIDGE", "output_basename": "BIDIR_V3_DCV_BRIDGE"},
        "groups": [
            {"mode": "RC", "start": "DV", "end": "N1"},
            {"mode": "LC", "start": "N1", "end": "D0"},
            {"mode": "RL", "start": "DV", "end": "N2"},
            {"mode": "RCL", "start": "N2", "end": "D0"},
            {"mode": "LC", "start": "N1", "end": "N2"},
        ],
        "sources": [
            {"kind": "dc_voltage", "ref": "V1", "value": "12V", "positive": "DV", "negative": "D0"}
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _two_dcv_large() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "BIDIR_V3_2DCV_LARGE", "output_basename": "BIDIR_V3_2DCV_LARGE"},
        "groups": [
            {"mode": "RCL", "start": "A1", "end": "N1"},
            {"mode": "RC", "start": "N1", "end": "D0"},
            {"mode": "RL", "start": "B1", "end": "N2"},
            {"mode": "LC", "start": "N2", "end": "D0"},
            {"mode": "R", "start": "N1", "end": "N2"},
        ],
        "sources": [
            {"kind": "dc_voltage", "ref": "V1", "value": "15V", "positive": "A1", "negative": "D0"},
            {"kind": "dc_voltage", "ref": "V2", "value": "5V", "positive": "B1", "negative": "D0"},
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _three_dcv_shared() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "BIDIR_V3_3DCV_SHARED", "output_basename": "BIDIR_V3_3DCV_SHARED"},
        "groups": [
            {"mode": "RCL", "start": "A1", "end": "D0"},
            {"mode": "RC", "start": "B1", "end": "D0"},
            {"mode": "RL", "start": "C1", "end": "D0"},
            {"mode": "LC", "start": "A1", "end": "B1"},
            {"mode": "R", "start": "B1", "end": "C1"},
        ],
        "sources": [
            {"kind": "dc_voltage", "ref": "V1", "value": "12V", "positive": "A1", "negative": "D0"},
            {"kind": "dc_voltage", "ref": "V2", "value": "9V", "positive": "B1", "negative": "D0"},
            {"kind": "dc_voltage", "ref": "V3", "value": "5V", "positive": "C1", "negative": "D0"},
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _write_archive() -> None:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(
                path.relative_to(OUT.parent).as_posix(),
                date_time=(2026, 6, 7, 0, 0, 0),
            )
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> None:
    resolved = OUT.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError("Refusing to clear an output directory outside the repository.")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    v2.OUT = OUT

    registry = FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {failed_hashes}")
    base = registry.get("e001_empty").path
    bidir_templates = load_templates(
        V1_DONORS / "bider_empty.pdsprj",
        V1_DONORS / "180bider_empty.pdsprj",
    )
    dcv_template = load_dcv_unit_template(USER_ONE_DCV)
    resistor_cases = predefined_resistor_cases()
    rcl_cases = mixed_rcl_15_cases()

    results = [
        v2._convert_passive_case(
            "T01_R20_MESH",
            resistor_cases[-1],
            generate_resistor_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._convert_passive_case(
            "T02_RC6_MIXED",
            mixed_6_case(),
            generate_mixed_passive_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._convert_passive_case(
            "T03_CAP4_BRANCHES",
            _single_family_payload("C", "BIDIR_V3_CAP4"),
            generate_mixed_rcl_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._convert_passive_case(
            "T04_IND4_BRANCHES",
            _single_family_payload("L", "BIDIR_V3_IND4"),
            generate_mixed_rcl_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._convert_passive_case(
            "T05_RCL_WHEATSTONE",
            rcl_cases[10],
            generate_mixed_rcl_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._convert_passive_case(
            "T06_RCL21_RULE",
            mixed_rcl_21_case(),
            generate_mixed_rcl_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._convert_passive_case(
            "T07_DCI_PARALLEL_RCL",
            _source_payload(
                name="BIDIR_V3_DCI",
                kind="dc_current",
                ref="I1",
                value="2A",
                positive="DI",
                negative="I0",
                groups=[
                    {"mode": "RCL", "start": "DI", "end": "I0"},
                    {"mode": "RC", "start": "DI", "end": "I0"},
                ],
            ),
            generate_source_driven_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._convert_passive_case(
            "T08_ACV_MULTI_BRANCH",
            _source_payload(
                name="BIDIR_V3_ACV",
                kind="ac_voltage",
                ref="V1",
                value="VSINE",
                positive="AV",
                negative="A0",
                groups=[
                    {"mode": "RC", "start": "AV", "end": "A0"},
                    {"mode": "LC", "start": "AV", "end": "A0"},
                    {"mode": "R", "start": "AV", "end": "A0"},
                ],
            ),
            generate_source_driven_project_from_payload,
            base=base,
            templates=bidir_templates,
            prefix="BIDIR_V3",
        ),
        v2._generate_dcv_case(
            "T09_DCV_BRIDGE",
            _one_dcv_bridge(),
            registry=registry,
            bidir_templates=bidir_templates,
            dcv_template=dcv_template,
            prefix="BIDIR_V3",
        ),
        v2._generate_dcv_case(
            "T10_2DCV_LARGE_SHARED",
            _two_dcv_large(),
            registry=registry,
            bidir_templates=bidir_templates,
            dcv_template=dcv_template,
            prefix="BIDIR_V3",
        ),
        v2._generate_dcv_case(
            "T11_3DCV_SHARED",
            _three_dcv_shared(),
            registry=registry,
            bidir_templates=bidir_templates,
            dcv_template=dcv_template,
            prefix="BIDIR_V3",
        ),
    ]
    summary = {
        "phase": "bidirectional_v3_prelock_expanded_regression",
        "inherits": "accepted bidirectional V2 orientation and donor-native DCV method",
        "case_count": len(results),
        "cases": results,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT / "README_TEST_ORDER.txt").write_text(
        "BIDIRECTIONAL V3 PRE-LOCK REGRESSION PACK\n\n"
        "T01 20-resistor mesh with power/ground\n"
        "T02 six-component resistor/capacitor network\n"
        "T03 four-branch capacitor network\n"
        "T04 four-branch inductor network\n"
        "T05 mixed RCL Wheatstone bridge\n"
        "T06 corrected 21-component RCL topology\n"
        "T07 DC-current source with parallel RCL/RC loads\n"
        "T08 AC-voltage source with RC/LC/R branches\n"
        "T09 one clean DCV source driving an RCL bridge\n"
        "T10 two clean DCV sources driving a larger shared-return network\n"
        "T11 three clean DCV sources sharing D0\n\n"
        "Report for each case: opens without warnings, visual direction, and simulation result.\n",
        encoding="utf-8",
    )
    _write_archive()
    print(json.dumps({"output": str(OUT), "archive": str(ARCHIVE), "cases": len(results)}, indent=2))


if __name__ == "__main__":
    main()
