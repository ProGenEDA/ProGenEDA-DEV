from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from proteusgen.layout import LayoutError, SOURCE_Y_SPACING, X_SPACING, plan_payload
from proteusgen.mixed_passive import (
    generate_mixed_passive_project,
    generate_mixed_passive_project_from_payload,
)
from proteusgen.mixed_passive_ir import parse_mixed_passive_ir, validate_mixed_passive_payload
from proteusgen.mixed_rcl import (
    generate_mixed_rcl_project,
    generate_mixed_rcl_project_from_payload,
    parse_mixed_rcl_ir,
)
from proteusgen.mixed_rcl_examples import mixed_rcl_15_cases, mixed_rcl_21_case
from proteusgen.resistor_examples import predefined_resistor_cases
from proteusgen.resistor_ir import parse_resistor_ir, validate_resistor_payload
from proteusgen.resistor_v9 import (
    generate_resistor_project,
    generate_resistor_project_from_payload,
)
from proteusgen.source_driven import (
    generate_source_driven_project,
    generate_source_driven_project_from_payload,
    parse_source_driven_ir,
)


def _source_payload(kind: str = "dc_voltage") -> dict:
    if kind == "ac_voltage":
        positive, negative, ref, value = "AV", "A0", "V1", "VSINE"
    else:
        positive, negative, ref, value = "DV", "D0", "V1", "10V"
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "LAYOUT_SOURCE", "output_basename": "LAYOUT_SOURCE"},
        "groups": [
            {"mode": "RC", "start": positive, "end": "N1"},
            {"mode": "L", "start": "N1", "end": negative},
        ],
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
    }


def _double_source_payload() -> dict:
    payload = _source_payload()
    payload["groups"] = [
        {"mode": "RC", "start": "DV", "end": "N1"},
        {"mode": "RL", "start": "N1", "end": "D0"},
    ]
    payload["sources"].append(
        {
            "kind": "dc_current",
            "ref": "I1",
            "value": "2A",
            "positive": "N1",
            "negative": "D0",
        }
    )
    return payload


def _series_payload(count: int = 10) -> dict:
    refs = [f"R{index}" if index <= 9 else f"R{chr(ord('A') + index - 10)}" for index in range(1, count + 1)]
    nodes = ["V0", *[f"N{index}" for index in range(1, 10)], "G0"]
    return {
        "schema_version": "proteus-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-v9-resistor-terminal",
        "project": {
            "name": "LONG_SERIES",
            "output_basename": "LONG_SERIES",
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "nodes": [
            {"id": node, "kind": "power" if node == "V0" else "ground" if node == "G0" else "internal"}
            for node in nodes[: count + 1]
        ],
        "components": [
            {
                "ref": refs[index],
                "type": "RESISTOR",
                "value": "1k",
                "nodes": [nodes[index], nodes[index + 1]],
            }
            for index in range(count)
        ],
        "layout": {"strategy": "beautify"},
    }


def test_beautifier_is_deterministic_and_separates_parallel_branches() -> None:
    payload = mixed_rcl_15_cases()[2]
    first = plan_payload(payload, "beautify")
    second = plan_payload(copy.deepcopy(payload), "beautify")
    assert first.as_dict() == second.as_dict()
    assert not first.overlaps
    assert len({position.y for position in first.component_positions.values()}) > 1
    assert any(item["kind"] == "hub" for item in first.motifs)


def test_cycle_edges_receive_a_dedicated_lane() -> None:
    delta = mixed_rcl_15_cases()[7]
    plan = plan_payload(delta, "beautify")
    cycle = next(item for item in plan.motifs if item["kind"] == "cycle")
    cycle_y = {
        plan.component_positions[ref].y
        for ref in cycle["closing_components"]
    }
    other_y = {
        position.y
        for ref, position in plan.component_positions.items()
        if ref not in cycle["closing_components"]
    }
    assert cycle_y
    assert min(cycle_y) < max(other_y)


def test_beautifier_wraps_long_series_after_seven_slots() -> None:
    plan = plan_payload(_series_payload(), "beautify")
    assert plan.wrap_count == 1
    assert plan.component_positions["R1"].x == plan.component_positions["R8"].x
    assert plan.component_positions["R1"].y != plan.component_positions["R8"].y


def test_manual_layout_is_exact_and_requires_every_position() -> None:
    payload = predefined_resistor_cases()[1]
    payload["layout"]["strategy"] = "manual"
    plan = plan_payload(payload)
    assert plan.component_positions["R1"].as_dict() == payload["layout"]["component_positions"]["R1"]

    del payload["layout"]["component_positions"]["R2"]
    with pytest.raises(LayoutError, match="R2"):
        plan_payload(payload)


def test_source_is_placed_left_of_driven_network_without_overlap() -> None:
    plan = plan_payload(_source_payload(), "beautify")
    source = plan.source_positions["V1"]
    first_component_x = min(position.x for position in plan.component_positions.values())
    assert source.x == first_component_x - X_SPACING
    assert not plan.overlaps


def test_multiple_sources_use_a_clear_dedicated_column() -> None:
    plan = plan_payload(_double_source_payload(), "beautify")
    source_positions = list(plan.source_positions.values())
    assert len({position.x for position in source_positions}) == 1
    assert abs(source_positions[0].y - source_positions[1].y) >= SOURCE_Y_SPACING
    assert max(position.x for position in source_positions) < min(
        position.x for position in plan.component_positions.values()
    )
    assert not plan.overlaps


def test_same_node_series_prefers_one_horizontal_lane() -> None:
    plan = plan_payload(_double_source_payload(), "beautify")
    assert len({position.y for position in plan.component_positions.values()}) == 1


def test_manual_source_layout_is_exact_and_required() -> None:
    payload = _source_payload()
    automatic = plan_payload(payload, "beautify")
    payload["layout"] = {
        "strategy": "manual",
        "component_positions": {
            ref: position.as_dict() for ref, position in automatic.component_positions.items()
        },
        "source_positions": {"V1": {"x": -20_000_000, "y": 7_000_000}},
    }
    manual = plan_payload(payload)
    assert manual.source_positions["V1"].as_dict() == {"x": -20_000_000, "y": 7_000_000}

    del payload["layout"]["source_positions"]["V1"]
    with pytest.raises(LayoutError, match="V1"):
        plan_payload(payload)


def test_legacy_strategy_matches_direct_emitters_byte_for_byte(tmp_path: Path) -> None:
    resistor_payload = predefined_resistor_cases()[4]
    resistor_ir, resistor_issues = parse_resistor_ir(resistor_payload)
    assert resistor_ir is not None and not resistor_issues

    mixed_payload = json.loads(
        (Path(__file__).parents[1] / "examples" / "my_test_circuit.json").read_text(encoding="utf-8")
    )
    mixed_ir, mixed_issues = parse_mixed_passive_ir(mixed_payload)
    assert mixed_ir is not None and not mixed_issues

    rcl_payload = mixed_rcl_21_case()
    rcl_ir, rcl_issues = parse_mixed_rcl_ir(rcl_payload)
    assert rcl_ir is not None and not rcl_issues

    source_payload = _source_payload()
    source_ir, source_issues = parse_source_driven_ir(source_payload)
    assert source_ir is not None and not source_issues
    ac_source_payload = _source_payload("ac_voltage")
    ac_source_ir, ac_source_issues = parse_source_driven_ir(ac_source_payload)
    assert ac_source_ir is not None and not ac_source_issues

    pairs = [
        (
            generate_resistor_project(resistor_ir, tmp_path / "resistor_direct"),
            generate_resistor_project_from_payload(
                copy.deepcopy(resistor_payload),
                tmp_path / "resistor_legacy",
                layout_strategy="legacy",
            ),
        ),
        (
            generate_mixed_passive_project(mixed_ir, tmp_path / "mixed_direct"),
            generate_mixed_passive_project_from_payload(
                copy.deepcopy(mixed_payload),
                tmp_path / "mixed_legacy",
                layout_strategy="legacy",
            ),
        ),
        (
            generate_mixed_rcl_project(rcl_ir, tmp_path / "rcl_direct"),
            generate_mixed_rcl_project_from_payload(
                copy.deepcopy(rcl_payload),
                tmp_path / "rcl_legacy",
                layout_strategy="legacy",
            ),
        ),
        (
            generate_source_driven_project(source_ir, tmp_path / "source_direct"),
            generate_source_driven_project_from_payload(
                copy.deepcopy(source_payload),
                tmp_path / "source_legacy",
                layout_strategy="legacy",
            ),
        ),
        (
            generate_source_driven_project(ac_source_ir, tmp_path / "ac_source_direct"),
            generate_source_driven_project_from_payload(
                copy.deepcopy(ac_source_payload),
                tmp_path / "ac_source_legacy",
                layout_strategy="legacy",
            ),
        ),
    ]
    for direct, legacy in pairs:
        assert direct.dsn_path.read_bytes() == legacy.dsn_path.read_bytes()
        assert direct.cdb_path.read_bytes() == legacy.cdb_path.read_bytes()


def test_optional_layout_materializes_legacy_positions(tmp_path: Path) -> None:
    payload = predefined_resistor_cases()[4]
    del payload["layout"]
    result = generate_resistor_project_from_payload(payload, tmp_path / "optional")
    assert result.manifest["layout"]["strategy"] == "legacy"
    assert result.manifest["static_validation_issues"] == []


def test_minimal_beautify_layout_validates_for_component_routes() -> None:
    resistor = predefined_resistor_cases()[4]
    resistor["layout"] = {"strategy": "beautify"}
    resistor_report = validate_resistor_payload(resistor)
    assert resistor_report.valid

    mixed = json.loads(
        (Path(__file__).parents[1] / "examples" / "my_test_circuit.json").read_text(encoding="utf-8")
    )
    mixed["layout"] = {"strategy": "beautify"}
    mixed_report = validate_mixed_passive_payload(mixed)
    assert mixed_report.valid


def test_beautified_generators_emit_layout_plan_and_static_clean_projects(tmp_path: Path) -> None:
    resistor = generate_resistor_project_from_payload(
        predefined_resistor_cases()[4],
        tmp_path / "resistor",
        layout_strategy="beautify",
    )
    mixed_payload = json.loads(
        (Path(__file__).parents[1] / "examples" / "my_test_circuit.json").read_text(encoding="utf-8")
    )
    mixed = generate_mixed_passive_project_from_payload(
        mixed_payload,
        tmp_path / "mixed",
        layout_strategy="beautify",
    )
    rcl = generate_mixed_rcl_project_from_payload(
        mixed_rcl_21_case(),
        tmp_path / "rcl",
        layout_strategy="beautify",
    )
    source = generate_source_driven_project_from_payload(
        _source_payload(),
        tmp_path / "source",
        layout_strategy="beautify",
    )
    ac_source = generate_source_driven_project_from_payload(
        _source_payload("ac_voltage"),
        tmp_path / "ac_source",
        layout_strategy="beautify",
    )

    for result in (resistor, mixed, rcl, source, ac_source):
        assert result.layout_path.exists()
        assert result.manifest["layout"]["strategy"] == "beautify"
        assert result.manifest["layout"]["overlap_count"] == 0
        assert result.manifest["static_validation_issues"] == []


def test_beautified_ac_source_body_moves_with_its_terminals(tmp_path: Path) -> None:
    result = generate_source_driven_project_from_payload(
        _source_payload("ac_voltage"),
        tmp_path / "ac_compact",
        layout_strategy="beautify",
    )
    chunk = result.chunk_path.read_bytes()
    model = b"\x02\x00\x05VSINE"
    model_pos = chunk.find(model)
    assert model_pos >= 0
    coord = model_pos + len(model)
    body_x = int.from_bytes(chunk[coord : coord + 4], "little", signed=True)
    body_y = int.from_bytes(chunk[coord + 4 : coord + 8], "little", signed=True)
    target = result.manifest["sources"][0]["target"]
    assert abs(body_x - target[0]) < 1_270_000
    assert abs(body_y - target[1]) < 1_270_000
