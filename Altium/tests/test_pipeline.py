from __future__ import annotations

import json
from pathlib import Path

import pytest

from Altium.arrangement_decider import decide_arrangement
from Altium.beautifier import apply_coordinate_edits
from Altium.component_placer import place_components
from Altium.component_selector import resolve_components
from Altium.input_fixer import repair_input
from Altium.input_validator import validate_resolved_input
from Altium.ir import load_circuit
from Altium.pipeline import PipelineRunError, generate_pipeline, validate_and_fix_input
from Altium.placement_validator import validate_placement
from Altium.routing_validator import validate_routing
from Altium.terminal_placer import combine_plans, place_terminals
from Altium.value_editor import apply_value_edits
from Altium.value_validator import validate_component_values
from Altium.wire_planner import plan_wires


_EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_input_fixer_marks_missing_native_pin_as_guess_terminal() -> None:
    fixed = repair_input(
        {
            "project": {"name": "partial_resistor"},
            "components": [{"ref": "R1", "kind": "R", "pins": {"1": "VIN"}}],
        }
    )

    assert fixed.report["guessed_terminal_nets"] == ["GUESS_TERMINAL_R1_2"]
    component = fixed.fixed["components"][0]
    assert component["pins"]["2"] == "GUESS_TERMINAL_R1_2"
    assert fixed.fixed["expected_netlist"]["GUESS_TERMINAL_R1_2"] == ["R1.2"]


def test_stage_contracts_compose_without_native_file_writing() -> None:
    fixed = repair_input(_EXAMPLES / "direct_rc_filter.json")
    circuit = apply_value_edits(load_circuit(fixed.fixed)).circuit
    assert validate_component_values(circuit).passed
    selection = resolve_components(circuit)
    assert validate_resolved_input(selection).passed
    initial = place_components(selection)
    assert validate_placement(initial).passed
    arrangement = decide_arrangement(initial)
    design = apply_coordinate_edits(initial, arrangement).design
    assert validate_placement(design).passed
    wires = plan_wires(design, circuit.routing_mode)
    terminals = place_terminals(design, wires)
    routing = combine_plans(wires, terminals)
    assert validate_routing(design, routing).passed
    assert not routing.terminalized_nets


def test_arrangement_prioritizes_connected_components_without_changing_nets() -> None:
    fixed = repair_input(
        {
            "project": {"name": "topology_order"},
            "components": [
                {"ref": "R2", "kind": "R", "pins": {"1": "NET_A", "2": "NC_R2_2"}},
                {"ref": "R3", "kind": "R", "pins": {"1": "NET_B", "2": "NC_R3_2"}},
                {"ref": "R1", "kind": "R", "pins": {"1": "NET_A", "2": "NET_B"}},
            ],
        }
    )
    selection = resolve_components(load_circuit(fixed.fixed))
    initial = place_components(selection)
    arrangement = decide_arrangement(initial)
    beautified = apply_coordinate_edits(initial, arrangement)

    assert arrangement.component_order[0] == "R1"
    assert "R1" in beautified.moved_references
    assert beautified.design.nets == initial.nets
    assert validate_placement(beautified.design).passed


def test_full_pipeline_preserves_each_stage_and_private_archive(tmp_path: Path) -> None:
    events: list[dict[str, object]] = []
    result = generate_pipeline(
        _EXAMPLES / "direct_74hc04_breakout.json",
        output_root=tmp_path,
        on_progress=events.append,
    )

    expected_stages = {
        "01_input_fixer.json",
        "02_value_editor.json",
        "03_value_validator.json",
        "04_file_name_decider.json",
        "05_component_selector.json",
        "06_user_spec_validator.json",
        "07_input_validator.json",
        "08_component_placer.json",
        "09_placement_validator_initial.json",
        "10_arrangement_decider.json",
        "11_beautifier.json",
        "12_beautifier_validator.json",
        "13_routing_decider.json",
        "14_wire_planner.json",
        "15_terminal_placer.json",
        "16_routing_plan.json",
        "17_routing_validator.json",
        "18_native_writer.json",
        "19_output_packager.json",
        "20_pcb_decision.json",
        "21_final_validator.json",
    }
    assert {path.name for path in (result.internal_directory / "stages").glob("*.json")} == expected_stages
    assert result.internal_archive.is_file()
    assert result.project_archive.is_file()
    assert result.validation.passed
    assert result.terminalized_nets
    assert events[0]["stage"] == "input_fixer"
    assert events[-1]["stage"] == "output_packager"
    pcb = json.loads((result.internal_directory / "stages" / "20_pcb_decision.json").read_text())
    assert pcb["status"] == "not_generated"


def test_strict_wire_run_records_failure_without_terminalizing(tmp_path: Path) -> None:
    with pytest.raises(PipelineRunError, match="Strict wire mode does not terminalize failures") as raised:
        generate_pipeline(
            _EXAMPLES / "direct_74hc04_breakout.json",
            output_root=tmp_path,
            routing_mode="wire",
        )

    assert raised.value.run_directory is not None
    routing = json.loads(
        (raised.value.run_directory / "internal" / "stages" / "16_routing_plan.json").read_text()
    )
    assert routing["terminalized_nets"] == []
    assert routing["unresolved_nets"]


def test_preflight_reports_source_resolved_input_without_generation() -> None:
    report = validate_and_fix_input(_EXAMPLES / "direct_led_indicator.json")

    assert report["input_validator"]["passed"] is True
    assert report["file_name_decider"]["project_file"] == "direct_led_indicator.PrjPcb"
    assert report["user_spec_validator"]["passed"] is True
    assert report["component_selection"]["components"][2]["logical_pin_map"] == {"A": "1", "C": "2"}
