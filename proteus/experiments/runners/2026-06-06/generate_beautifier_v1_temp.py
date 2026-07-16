"""Generate the first placement-only beautifier acceptance pack."""

from __future__ import annotations

import copy
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable

from proteusgen.mixed_rcl import generate_mixed_rcl_project_from_payload
from proteusgen.mixed_rcl_examples import mixed_rcl_15_cases, mixed_rcl_21_case
from proteusgen.source_driven import generate_source_driven_project_from_payload

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "proteus" / "experiments" / "runs" / "beautifier_v1_temp_2026_06_06"
ARCHIVE = ROOT / "proteus" / "experiments" / "runs" / "BEAUTIFIER_V1_REPRESENTATIVE_TEMP_2026_06_06.zip"


def _renamed(payload: dict[str, Any], name: str) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    project = out.setdefault("project", {})
    project["name"] = name
    project["output_basename"] = name
    return out


def _single_source() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "SOURCE_SINGLE_DCV", "output_basename": "SOURCE_SINGLE_DCV"},
        "groups": [
            {"mode": "RC", "start": "DV", "end": "N1"},
            {"mode": "L", "start": "N1", "end": "D0"},
        ],
        "sources": [
            {
                "kind": "dc_voltage",
                "ref": "V1",
                "value": "10V",
                "positive": "DV",
                "negative": "D0",
            }
        ],
        "component_values": {},
    }


def _mixed_sources() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "SOURCE_MIXED_DC", "output_basename": "SOURCE_MIXED_DC"},
        "groups": [
            {"mode": "RC", "start": "DV", "end": "N1"},
            {"mode": "RL", "start": "N1", "end": "D0"},
        ],
        "sources": [
            {
                "kind": "dc_voltage",
                "ref": "V1",
                "value": "12V",
                "positive": "DV",
                "negative": "D0",
            },
            {
                "kind": "dc_current",
                "ref": "I1",
                "value": "2A",
                "positive": "N1",
                "negative": "D0",
            },
        ],
        "component_values": {},
    }


def _ac_source() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "SOURCE_SINGLE_ACV", "output_basename": "SOURCE_SINGLE_ACV"},
        "groups": [{"mode": "RCL", "start": "AV", "end": "A0"}],
        "sources": [
            {
                "kind": "ac_voltage",
                "ref": "V1",
                "value": "VSINE",
                "positive": "AV",
                "negative": "A0",
            }
        ],
        "component_values": {},
    }


def _cases() -> list[tuple[str, dict[str, Any], str]]:
    topologies = mixed_rcl_15_cases()
    return [
        ("T01_MULTI_STEP_DIVIDER", topologies[5], "rcl"),
        ("T02_PARALLEL_CURRENT_DIVIDER", topologies[6], "rcl"),
        ("T03_SERIES_PARALLEL", topologies[3], "rcl"),
        ("T04_DELTA", topologies[7], "rcl"),
        ("T05_STAR", topologies[8], "rcl"),
        ("T06_WHEATSTONE", topologies[10], "rcl"),
        ("T07_R2R_LADDER", topologies[14], "rcl"),
        ("T08_CORRECTED_21", mixed_rcl_21_case(), "rcl"),
        ("T09_SINGLE_DCV", _single_source(), "source"),
        ("T10_MIXED_DCV_DCI", _mixed_sources(), "source"),
        ("T11_SINGLE_ACV", _ac_source(), "source"),
    ]


def _generator(route: str) -> Callable[..., Any]:
    if route == "rcl":
        return generate_mixed_rcl_project_from_payload
    return generate_source_driven_project_from_payload


def _identity_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    topology = [
        {
            key: item.get(key)
            for key in ("idx", "unit", "kind", "ref", "value", "left", "right", "global_id", "in_suffix", "out_suffix")
        }
        for item in manifest.get("topology", [])
    ]
    sources = [
        {
            key: item.get(key)
            for key in ("kind", "ref", "value", "positive", "negative", "global_id")
        }
        for item in manifest.get("sources", [])
    ]
    return {
        "object_chunk_len": manifest["object_chunk_len"],
        "marker_counts": manifest["marker_counts"],
        "component_count_requested": manifest["component_count_requested"],
        "component_count_emitted_cdb": manifest["component_count_emitted_cdb"],
        "component_count_emitted_dsn": manifest["component_count_emitted_dsn"],
        "topology": topology,
        "sources": sources,
    }


def main() -> None:
    resolved_out = OUT.resolve()
    if ROOT.resolve() not in resolved_out.parents:
        raise RuntimeError("Refusing to clear an output directory outside the repository.")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    summary: list[dict[str, Any]] = []
    for test_id, source_payload, route in _cases():
        generator = _generator(route)
        beautify_payload = _renamed(source_payload, f"BEAUTIFIER_V1_{test_id}_BEAUTIFY")
        legacy_payload = _renamed(source_payload, f"BEAUTIFIER_V1_{test_id}_LEGACY")
        beautified = generator(beautify_payload, OUT / test_id / "BEAUTIFY", layout_strategy="beautify")
        legacy = generator(legacy_payload, OUT / test_id / "LEGACY", layout_strategy="legacy")
        if beautified.manifest["static_validation_issues"] or legacy.manifest["static_validation_issues"]:
            raise RuntimeError(f"{test_id} generated static validation issues.")
        if beautified.cdb_path.read_bytes() != legacy.cdb_path.read_bytes():
            raise RuntimeError(f"{test_id} changed ROOT.CDB while changing placement.")
        if _identity_projection(beautified.manifest) != _identity_projection(legacy.manifest):
            raise RuntimeError(f"{test_id} changed record identities while changing placement.")
        summary.append(
            {
                "test_id": test_id,
                "route": route,
                "beautified_project": str(beautified.output_path.relative_to(OUT)),
                "legacy_project": str(legacy.output_path.relative_to(OUT)),
                "beautified_layout": beautified.manifest["layout"],
                "legacy_layout": legacy.manifest["layout"],
                "cdb_equal": True,
                "record_identities_equal": True,
                "beautified_static_validation_issues": [],
                "legacy_static_validation_issues": [],
            }
        )

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT / "README_TEST_ORDER.txt").write_text(
        "BEAUTIFIER V1 REPRESENTATIVE TEST PACK\n\n"
        "For each T01-T11 folder, open LEGACY first and then BEAUTIFY.\n"
        "Confirm both projects open and simulate the same circuit.\n"
        "Judge only placement: branch separation, source proximity, component overlap, and sheet fit.\n"
        "This pack does not add standalone buses, junctions, or routed wires.\n\n"
        "Recommended order:\n"
        "T01 multi-step divider\n"
        "T02 parallel/current divider\n"
        "T03 series-parallel\n"
        "T04 delta\n"
        "T05 star\n"
        "T06 Wheatstone\n"
        "T07 R-2R ladder\n"
        "T08 corrected 21-component circuit\n"
        "T09 single DC voltage source\n"
        "T10 mixed DC voltage/current sources\n"
        "T11 single AC voltage source\n",
        encoding="utf-8",
    )

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUT.parent).as_posix())
    print(json.dumps({"output": str(OUT), "archive": str(ARCHIVE), "cases": len(summary)}, indent=2))


if __name__ == "__main__":
    main()
