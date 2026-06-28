from __future__ import annotations

import json
import re
from pathlib import Path

from kicad.generator.kicad_json_to_project import (
    KIND_SPECS,
    plan_layout,
    validate_schematic,
    write_project_from_json,
)
from kicad.automation.quality_check import run_quality_check
from kicad.source_pack.source_reference import load_reference


def vdc_resistor() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": "vdc_resistor_op", "title": "VDC resistor", "analysis": [".op"]},
        "components": [
            {"id": "V1", "kind": "VDC", "value": "10", "pins": {"1": "VIN", "2": "GND"}},
            {"id": "R1", "kind": "R", "value": "1k", "pins": {"1": "VIN", "2": "GND"}},
            {"id": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {"VIN": "input", "GND": "return"},
    }


def four_endpoint_shared_net() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": "shared_node_parallel", "title": "Shared-node router test"},
        "components": [
            {"id": "V1", "kind": "VDC", "value": "10", "pins": {"1": "VIN", "2": "GND"}},
            {"id": "R1", "kind": "R", "value": "1k", "pins": {"1": "VIN", "2": "N1"}},
            {"id": "C1", "kind": "C", "value": "100n", "pins": {"1": "N1", "2": "GND"}},
            {"id": "L1", "kind": "L", "value": "10m", "pins": {"1": "N1", "2": "GND"}},
            {"id": "R2", "kind": "R", "value": "2k", "pins": {"1": "N1", "2": "GND"}},
            {"id": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {"VIN": "input", "N1": "four endpoint shared node", "GND": "return"},
    }


def ic_with_local_labels() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "project": {"name": "ic_local_label_quality", "title": "IC local-label quality"},
        "components": [
            {"id": "U1", "kind": "74HC08", "value": "74HC08", "pins": {"1": "A", "2": "B", "3": "Y"}},
            {"id": "TP1", "kind": "TESTPOINT", "value": "TP", "pins": {"1": "Y"}},
        ],
        "nets": {"A": "logic input", "B": "logic input", "Y": "logic output"},
    }


def wire_points(schematic: str) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    points = []
    for match in re.finditer(r"\(wire \(pts(.*?)\)\s*\n\s*\(stroke", schematic, re.S):
        xy = re.findall(r"\(xy\s+([-0-9.]+)\s+([-0-9.]+)\)", match.group(1))
        assert len(xy) == 2
        a = (float(xy[0][0]), float(xy[0][1]))
        b = (float(xy[1][0]), float(xy[1][1]))
        points.append((a, b))
    return points


def test_kicad_v1_uses_source_mined_core_symbols() -> None:
    assert KIND_SPECS["R"].lib_id == "Device:R"
    assert KIND_SPECS["L"].lib_id == "Device:L"
    assert KIND_SPECS["VDC"].lib_id == "Simulation_SPICE:VDC"
    assert KIND_SPECS["VSIN"].lib_id == "Simulation_SPICE:VSIN"
    assert KIND_SPECS["GND"].lib_id == "power:GND"


def test_kicad_source_reference_is_bundled_and_complete() -> None:
    reference = load_reference()
    logical_names = {item.logical_name for item in reference.files}
    assert "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp" in logical_names
    assert "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp" in logical_names
    assert "common/project/project_file.cpp" in logical_names
    assert "wire" in reference.parser_tokens
    assert "symbol" in reference.parser_tokens


def test_kicad_layout_is_deterministic_and_advances_series_chain() -> None:
    first = plan_layout(vdc_resistor()).as_dict()
    second = plan_layout(vdc_resistor()).as_dict()
    assert first == second
    assert first["components"]["V1"]["at"][0] < first["components"]["R1"]["at"][0]


def test_kicad_router_combines_multidrop_net_with_junctions() -> None:
    plan = plan_layout(four_endpoint_shared_net())
    by_net = {}
    for segment in plan.routing.segments:
        by_net.setdefault(segment.net, []).append(segment)
        assert segment.a[0] == segment.b[0] or segment.a[1] == segment.b[1]
    assert len(by_net["N1"]) >= 4
    assert plan.routing.junctions


def test_kicad_output_files_and_static_shape(tmp_path: Path) -> None:
    manifest = write_project_from_json(four_endpoint_shared_net(), tmp_path)
    assert manifest["open_this"] == "OPEN_THIS_PROJECT__shared_node_parallel__PROJECT_FILE.kicad_pro"
    schematic_path = tmp_path / manifest["schematic_file"]
    schematic = schematic_path.read_text(encoding="utf-8")
    checks = validate_schematic(schematic)
    assert checks["ok"], checks
    assert "OPEN_THIS_PROJECT__OPEN_THIS_PROJECT" not in manifest["open_this"]
    for a, b in wire_points(schematic):
        assert a[0] == b[0] or a[1] == b[1]
    assert (tmp_path / "input.json").exists()
    assert (tmp_path / "manifest.json").exists()
    assert manifest["source_reference"]["conclusions"][-1] == "All required V1 source reference files are present."


def test_project_local_symbols_label_stubs_and_no_connects(tmp_path: Path) -> None:
    manifest = write_project_from_json(ic_with_local_labels(), tmp_path)
    schematic = (tmp_path / manifest["schematic_file"]).read_text(encoding="utf-8")

    assert manifest["project_local_symbol_library"] == "progen_generated.kicad_sym"
    assert manifest["symbol_library_table"] == "sym-lib-table"
    assert (tmp_path / "progen_generated.kicad_sym").exists()
    assert (tmp_path / "sym-lib-table").exists()
    assert manifest["static_checks"]["no_connect_count"] >= 1
    assert manifest["layout"]["local_label_stubs"]
    assert "\n  (no_connect " in schematic

    checks = run_quality_check(tmp_path, output=tmp_path / "quality.json", run_erc_check=False)
    assert checks["schematic_count"] == 1
    assert checks["failure_count"] == 0


def test_manual_positions_are_exact(tmp_path: Path) -> None:
    circuit = vdc_resistor()
    circuit["components"][1]["at"] = [100, 80]  # type: ignore[index]
    manifest = write_project_from_json(circuit, tmp_path)
    assert manifest["layout"]["components"]["R1"]["at"] == [100.0, 80.0]
