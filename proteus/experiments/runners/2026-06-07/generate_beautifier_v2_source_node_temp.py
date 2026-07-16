"""Generate focused V2 beautifier diagnostics after the first visual review."""

from __future__ import annotations

import copy
import json
import shutil
import zipfile
from pathlib import Path
from typing import Any, Callable

from proteusgen import source_driven as sd
from proteusgen.layout import SOURCE_Y_SPACING
from proteusgen.mixed_rcl import generate_mixed_rcl_project_from_payload
from proteusgen.mixed_rcl_examples import mixed_rcl_15_cases
from proteusgen.source_driven import generate_source_driven_project_from_payload

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "proteus" / "experiments" / "runs" / "beautifier_v2_source_node_temp_2026_06_07"
ARCHIVE = ROOT / "proteus" / "experiments" / "runs" / "BEAUTIFIER_V2_SOURCE_NODE_TEMP_2026_06_07.zip"


def _renamed(payload: dict[str, Any], name: str) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    project = out.setdefault("project", {})
    project["name"] = name
    project["output_basename"] = name
    return out


def _mixed_sources() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "V2_MIXED_SOURCES", "output_basename": "V2_MIXED_SOURCES"},
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
        "project": {"name": "V2_AC_SOURCE", "output_basename": "V2_AC_SOURCE"},
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
        ("T01_DOUBLE_SOURCE_CLEARANCE", _mixed_sources(), "source"),
        ("T02_AC_SOURCE_COMPACT", _ac_source(), "source"),
        ("T03_SERIES_PARALLEL_SAME_NODE", topologies[3], "rcl"),
        ("T04_DELTA_CYCLE_LANE", topologies[7], "rcl"),
        ("T05_WHEATSTONE_SHARED_NODES", topologies[10], "rcl"),
    ]


def _generator(route: str) -> Callable[..., Any]:
    return (
        generate_source_driven_project_from_payload
        if route == "source"
        else generate_mixed_rcl_project_from_payload
    )


def _identity_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    topology = [
        {
            key: item.get(key)
            for key in (
                "idx",
                "unit",
                "kind",
                "ref",
                "value",
                "left",
                "right",
                "global_id",
                "in_suffix",
                "out_suffix",
            )
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


def _shared_node_alignment(manifest: dict[str, Any]) -> dict[str, Any]:
    ys_by_node: dict[str, list[int]] = {}
    for component in manifest["topology"]:
        for node in (component["left"], component["right"]):
            ys_by_node.setdefault(node, []).append(component["y"])
    repeated = {
        node: sorted(set(values))
        for node, values in sorted(ys_by_node.items())
        if len(values) > 1
    }
    return {
        "repeated_nodes": repeated,
        "single_lane_nodes": [
            node for node, lanes in repeated.items() if len(lanes) == 1
        ],
    }


def _ac_body_offset(result: Any) -> dict[str, int] | None:
    if not result.manifest.get("sources") or result.manifest["sources"][0]["kind"] != "ac_voltage":
        return None
    chunk = result.chunk_path.read_bytes()
    marker = b"\x02\x00\x05VSINE"
    model_pos = chunk.find(marker)
    if model_pos < 0:
        raise RuntimeError("Generated AC project is missing the VSINE body marker.")
    coord = model_pos + len(marker)
    body_x = sd._s32(chunk, coord)
    body_y = sd._s32(chunk, coord + 4)
    target_x, target_y = result.manifest["sources"][0]["target"]
    return {
        "body_x": body_x,
        "body_y": body_y,
        "target_x": target_x,
        "target_y": target_y,
        "dx": body_x - target_x,
        "dy": body_y - target_y,
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
        beautified = generator(
            _renamed(source_payload, f"BEAUTIFIER_V2_{test_id}_BEAUTIFY"),
            OUT / test_id / "BEAUTIFY",
            layout_strategy="beautify",
        )
        legacy = generator(
            _renamed(source_payload, f"BEAUTIFIER_V2_{test_id}_LEGACY"),
            OUT / test_id / "LEGACY",
            layout_strategy="legacy",
        )
        if beautified.manifest["static_validation_issues"] or legacy.manifest["static_validation_issues"]:
            raise RuntimeError(f"{test_id} generated static validation issues.")
        if beautified.cdb_path.read_bytes() != legacy.cdb_path.read_bytes():
            raise RuntimeError(f"{test_id} changed ROOT.CDB while changing placement.")
        if _identity_projection(beautified.manifest) != _identity_projection(legacy.manifest):
            raise RuntimeError(f"{test_id} changed record identities while changing placement.")
        if beautified.manifest["layout"]["overlap_count"]:
            raise RuntimeError(f"{test_id} retained placement overlaps.")

        source_positions = list(beautified.manifest["layout"]["source_positions"].values())
        source_clearance = None
        if len(source_positions) > 1:
            source_clearance = min(
                abs(left["y"] - right["y"])
                for index, left in enumerate(source_positions)
                for right in source_positions[index + 1 :]
            )
            if source_clearance < SOURCE_Y_SPACING:
                raise RuntimeError(f"{test_id} source clearance is too small.")

        ac_offset = _ac_body_offset(beautified)
        if ac_offset is not None and (
            abs(ac_offset["dx"]) >= 1_270_000 or abs(ac_offset["dy"]) >= 1_270_000
        ):
            raise RuntimeError(f"{test_id} AC body was not translated with its terminals.")

        summary.append(
            {
                "test_id": test_id,
                "route": route,
                "beautified_project": str(beautified.output_path.relative_to(OUT)),
                "legacy_project": str(legacy.output_path.relative_to(OUT)),
                "cdb_equal": True,
                "record_identities_equal": True,
                "source_clearance": source_clearance,
                "ac_body_offset": ac_offset,
                "shared_node_alignment": _shared_node_alignment(beautified.manifest),
                "beautified_layout": beautified.manifest["layout"],
                "beautified_static_validation_issues": [],
                "legacy_static_validation_issues": [],
            }
        )

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT / "README_TEST_ORDER.txt").write_text(
        "BEAUTIFIER V2 SOURCE AND NODE TEST PACK\n\n"
        "Open LEGACY first and then BEAUTIFY in each folder.\n"
        "T01: confirm the two DC sources no longer overlap.\n"
        "T02: confirm the AC source body, terminals, and short wires stay together.\n"
        "T03: confirm repeated series node labels follow one horizontal lane.\n"
        "T04: confirm the delta closure uses a separate understandable lane.\n"
        "T05: confirm Wheatstone branches and shared labels are easy to follow.\n"
        "All projects must still open and simulate as before.\n",
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
