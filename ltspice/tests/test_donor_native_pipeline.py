"""End-to-end deterministic coverage for the donor-native LTspice path."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ltspice.pipeline.donor_native_asc_writer import render_donor_native_asc
from ltspice.pipeline.donor_native_executable import run_donor_native_executable
from ltspice.pipeline.donor_native_fixture_matrix import (
    FAMILY_IDS,
    PLACEMENT_PROGRESSION,
    build_progression_matrix,
    write_progression_matrix,
)
from ltspice.pipeline.input_adapter import canonicalize_source
from ltspice.pipeline.native_canonical_adapter import (
    NativeCanonicalAdapterError,
    adapt_canonical_native_circuit,
    normal_editable_fields,
)
from ltspice.pipeline.native_beautifier import beautify_native_placement
from ltspice.pipeline.native_placer import native_live_state, place_native_components
from ltspice.pipeline.native_wire_router import donor_native_recipe, route_native_wires
from ltspice.pipeline.timing_contract import HARD_FAILURE_MESSAGE, OVERDUE_MESSAGE


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _rc_circuit() -> dict:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "NATIVE_RC",
        "project": {"name": "native_rc", "analysis": [".tran 1u 5m"]},
        "components": [
            {"ref": "V1", "kind": "VSIN", "value": "SIN(0 1 1k)", "pins": {"1": "IN", "2": "GND"}},
            {"ref": "R1", "kind": "R", "value": "1k", "parameters": {"tol": "1%"}, "pins": {"1": "IN", "2": "OUT"}},
            {"ref": "C1", "kind": "C", "value": "1u", "pins": {"1": "OUT", "2": "GND"}},
            {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
        ],
        "nets": {
            "IN": ["V1.1", "R1.1"],
            "OUT": ["R1.2", "C1.1"],
            "GND": ["V1.2", "C1.2", "G1.1"],
        },
    }


def _forty_three_component_circuit() -> dict:
    """Twenty resistors, twenty-one capacitors, one source, one ground."""

    components = [
        {"ref": "V1", "kind": "VDC", "value": "5", "pins": {"1": "N0", "2": "GND"}},
        {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
    ]
    nets: dict[str, list[str]] = {"N0": ["V1.1"], "GND": ["V1.2", "G1.1"]}
    for index in range(1, 21):
        left, right = f"N{index - 1}", f"N{index}"
        components.append({"ref": f"R{index}", "kind": "R", "value": "1k", "pins": {"1": left, "2": right}})
        nets.setdefault(left, []).append(f"R{index}.1")
        nets.setdefault(right, []).append(f"R{index}.2")
    for index in range(1, 22):
        node = "N0" if index == 21 else f"N{index}"
        components.append({"ref": f"C{index}", "kind": "C", "value": "1u", "pins": {"1": node, "2": "GND"}})
        nets[node].append(f"C{index}.1")
        nets["GND"].append(f"C{index}.2")
    assert len(components) == 43
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "FORTY_THREE_STOCK_COMPONENTS",
        "project": {"name": "forty_three", "analysis": [".op"]},
        "components": components,
        "nets": nets,
    }


class DonorNativePipelineTests(unittest.TestCase):
    def test_shared_rc_json_becomes_stock_symbols_and_physical_wires_only(self) -> None:
        native, adapter_report = adapt_canonical_native_circuit(_rc_circuit())
        placement, placement_report = place_native_components(native)
        routes, routing_report = route_native_wires(native, placement)
        recipe = donor_native_recipe(native, placement, routes)
        payload = render_donor_native_asc(recipe)
        text = payload.decode("cp1252")
        live = native_live_state(native, placement, routes=routes)

        self.assertTrue(adapter_report["ok"])
        self.assertTrue(placement_report["ok"])
        self.assertTrue(routing_report["ok"], routing_report)
        self.assertIn("SYMBOL voltage", text)
        self.assertIn("SYMBOL res", text)
        self.assertIn("SYMBOL cap", text)
        self.assertIn("SYMATTR SpiceLine tol=1%", text)
        self.assertNotIn("progeneda", text.casefold())
        self.assertNotIn("terminal", text.casefold())
        self.assertTrue(all(line.endswith(" 0") for line in text.splitlines() if line.startswith("FLAG ")))
        self.assertEqual(live["schema"], "progen-ltspice-donor-native-live-routing-state/v1")
        self.assertEqual(live["metrics"]["wire_count"], len(routes["wire_segments"]))

    def test_forty_three_logical_components_route_without_terminal_fallback(self) -> None:
        circuit = _forty_three_component_circuit()
        native, _ = adapt_canonical_native_circuit(circuit)
        placement, _ = place_native_components(native)
        routes, report = route_native_wires(native, placement)
        recipe = donor_native_recipe(native, placement, routes)
        text = render_donor_native_asc(recipe).decode("cp1252")

        self.assertEqual(len(circuit["components"]), 43)
        self.assertTrue(report["ok"], report)
        self.assertEqual(text.count("\nSYMBOL "), 42)  # Ground is native FLAG 0, not a custom symbol.
        self.assertGreater(len(routes["wire_segments"]), 43)
        self.assertNotIn("progeneda_", text)
        flags = [line for line in text.splitlines() if line.startswith("FLAG ")]
        self.assertTrue(flags)
        self.assertTrue(all(line.endswith(" 0") for line in flags))

    def test_normal_editor_is_catalogue_bounded_and_unknown_fields_fail(self) -> None:
        fields = normal_editable_fields("R")
        self.assertEqual(sorted(fields["normal_mode"]), ["reference", "spice_line.pwr", "spice_line.tol", "value"])
        unsafe = _rc_circuit()
        unsafe["components"][1]["parameters"]["temperature"] = "25"
        with self.assertRaisesRegex(NativeCanonicalAdapterError, "no donor-proven"):
            adapt_canonical_native_circuit(unsafe)

    def test_declared_expected_netlist_is_a_native_adapter_invariant(self) -> None:
        circuit = _rc_circuit()
        circuit["expected_netlist"] = {
            "schema": "progeneda-expected-netlist/v1",
            "nets": [
                {"name": "IN", "members": ["V1.1", "R1.1"]},
                {"name": "OUT", "members": ["R1.2", "C1.1"]},
                {"name": "GND", "members": ["V1.2", "C1.2", "G1.1"]},
            ],
        }
        _native, report = adapt_canonical_native_circuit(circuit)
        self.assertTrue(report["expected_netlist_checked"])
        circuit["expected_netlist"]["nets"][0]["members"] = ["V1.1", "C1.1"]
        with self.assertRaisesRegex(NativeCanonicalAdapterError, "disagrees with expected_netlist"):
            adapt_canonical_native_circuit(circuit)

    def test_all_donor_observed_source_window_and_misc_signal_ac_fields_reach_native_records(self) -> None:
        circuit = {
            "schema_version": "progen-kicad-circuit-ir/v1",
            "circuit_id": "NATIVE_SOURCE_PROPERTIES",
            "components": [
                {
                    "ref": "V1", "kind": "VDC", "value": "5",
                    "parameters": {"ac": "1", "window_123": "0 0 Left 0", "window_39": "0 0 Left 0"},
                    "pins": {"1": "A", "2": "GND"},
                },
                {
                    "ref": "I1", "kind": "IDC", "value": "1m",
                    "parameters": {"window_123": "0 0 Left 0", "window_39": "0 0 Left 0"},
                    "pins": {"1": "A", "2": "GND"},
                },
                {
                    "ref": "V2", "kind": "MISC_SIGNAL", "parameters": {
                        "ac": "2", "window_123": "24 132 Left 2", "window_39": "0 0 Left 0"
                    }, "pins": {"1": "A", "2": "GND"},
                },
                {"ref": "R1", "kind": "R", "value": "1k", "pins": {"1": "A", "2": "GND"}},
                {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
            ],
            "nets": {
                "A": ["V1.1", "I1.1", "V2.1", "R1.1"],
                "GND": ["V1.2", "I1.2", "V2.2", "R1.2", "G1.1"],
            },
        }
        native, _ = adapt_canonical_native_circuit(circuit)
        placement, _ = place_native_components(native)
        routes, _ = route_native_wires(native, placement)
        text = render_donor_native_asc(donor_native_recipe(native, placement, routes)).decode("cp1252")
        self.assertIn("SYMBOL Misc\\\\signal", text)
        self.assertIn("SYMATTR Value2 AC 2", text)
        self.assertIn("WINDOW 123 24 132 Left 2", text)
        self.assertIn("WINDOW 39 0 0 Left 0", text)

    def test_shared_normalizer_cannot_turn_blank_misc_signal_into_a_connector_value(self) -> None:
        source = {
            "project_name": "blank_misc_signal",
            "components": [
                {"ref": "V1", "kind": "MISC_SIGNAL", "parameters": {"ac": "1"}, "pins": {"1": "N", "2": "GND"}},
                {"ref": "R1", "kind": "R", "value": "1k", "pins": {"1": "N", "2": "GND"}},
                {"ref": "G1", "kind": "GND", "value": "0", "pins": {"1": "GND"}},
            ],
            "nets": {"N": ["V1.1", "R1.1"], "GND": ["V1.2", "R1.2", "G1.1"]},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "blank_misc_signal.json"
            path.write_text(json.dumps(source), encoding="utf-8")
            canonical, _report, _original = canonicalize_source(path, routing_mode="wire")
        native, _report = adapt_canonical_native_circuit(canonical)
        source_component = next(item for item in native["components"] if item["ref"] == "V1")
        self.assertEqual(source_component["type_id"], "SIGNAL_SOURCE")
        self.assertEqual(source_component["properties"]["value"], "")
        self.assertEqual(source_component["properties"]["value2.ac"], "AC 1")

    def test_all_donor_observed_families_have_the_required_bounded_placement_progression(self) -> None:
        matrix = build_progression_matrix()
        self.assertEqual(len(matrix), len(FAMILY_IDS) * len(PLACEMENT_PROGRESSION))
        for circuit_id, circuit in matrix.items():
            self.assertLessEqual(len(circuit["components"]), 43, circuit_id)
            native, adapter_report = adapt_canonical_native_circuit(circuit)
            placement, placement_report = place_native_components(native)
            routes, routing_report = route_native_wires(native, placement)
            self.assertTrue(adapter_report["expected_netlist_checked"], circuit_id)
            self.assertTrue(placement_report["ok"], circuit_id)
            self.assertTrue(routing_report["ok"], (circuit_id, routing_report))
            self.assertTrue(routes["wire_segments"], circuit_id)

    def test_disconnected_source_load_blocks_are_beautified_as_a_grid_not_a_long_strip(self) -> None:
        fixture = build_progression_matrix()["NATIVE_SIGNAL_SOURCE_20"]
        native, _report = adapt_canonical_native_circuit(fixture)
        placement, placement_report = place_native_components(native)
        self.assertTrue(placement_report["ok"])
        # The old global-layer pass stretched twenty 2-part blocks to 7,760
        # ASC units. The topology-aware block packer keeps the exact same
        # circuit facts in a readable compact grid.
        self.assertLess(placement["sheet"]["width"], 3000)
        self.assertGreater(placement["sheet"]["height"], 680)
        _routes, routing_report = route_native_wires(native, placement)
        self.assertTrue(routing_report["ok"], routing_report)

    def test_fixture_matrix_refuses_to_overwrite_existing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "matrix"
            self.assertEqual(len(write_progression_matrix(output)), 36)
            with self.assertRaisesRegex(ValueError, "must be empty"):
                write_progression_matrix(output)

    def test_beautifier_moves_only_coordinates_and_orientations(self) -> None:
        native, _ = adapt_canonical_native_circuit(_forty_three_component_circuit())
        initial, _ = place_native_components(native, arrange=False)
        beautified, report = beautify_native_placement(native, initial)
        self.assertTrue(report["ok"])
        self.assertGreater(report["moved_component_count"], 0)
        for ref, component in beautified["components"].items():
            self.assertEqual(component["properties"], initial["components"][ref]["properties"])
            self.assertEqual(component["type_id"], initial["components"][ref]["type_id"])

    def test_explicit_far_negative_donor_grid_coordinates_route_physically(self) -> None:
        """A legitimate negative ASC placement must not hit a synthetic router wall."""

        circuit = _rc_circuit()
        circuit["components"][0]["ltspice_at"] = [-2048, -512]
        circuit["components"][1]["ltspice_at"] = [-1728, -512]
        circuit["components"][2]["ltspice_at"] = [-1376, -512]

        native, _ = adapt_canonical_native_circuit(circuit)
        placement, _ = place_native_components(native)
        routes, report = route_native_wires(native, placement)
        text = render_donor_native_asc(donor_native_recipe(native, placement, routes)).decode("cp1252")

        self.assertTrue(report["ok"], report)
        self.assertEqual(placement["components"]["V1"]["origin"], [-2048, -512])
        self.assertIn("SYMBOL voltage -2048 -512 R0", text)
        self.assertNotIn("terminal", text.casefold())

    def test_executable_packages_only_stock_native_asc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "native_rc.json"
            source.write_text(json.dumps(_rc_circuit()), encoding="utf-8")
            summary = run_donor_native_executable(source, output_root=root, label="test")
            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            run_dir = Path(summary["run_dir"])
            asc = run_dir / result["asc_path"]
            project = asc.parent
            user_zip = run_dir / result["output_artifacts"]["user_project"]["path"]
            self.assertTrue(asc.is_file())
            self.assertTrue(user_zip.is_file())
            self.assertEqual(sorted(path.suffix for path in project.iterdir()), [".asc"])

    def test_native_timing_hard_limit_retracts_the_user_download(self) -> None:
        clock = FakeClock()
        events: list[dict] = []

        def emit(event: dict) -> None:
            events.append(event)
            if event.get("event") == "stage" and event.get("stage") == "validate_native_asc" and event.get("state") == "completed":
                clock.now = 2.0

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "timed_native.json"
            source.write_text(json.dumps(_rc_circuit()), encoding="utf-8")
            summary = run_donor_native_executable(
                source,
                output_root=root,
                label="timed-native",
                animation_budget_seconds=1,
                timing_clock=clock,
                event_callback=emit,
            )
            run_dir = Path(summary["run_dir"])
            report_path = next((run_dir / "failures").rglob("failure.json"))
            report = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertFalse(summary["ok"], summary)
            self.assertEqual(summary["results"][0]["error"], HARD_FAILURE_MESSAGE)
            self.assertEqual(report["failed_stage"], "validate_native_asc")
            self.assertEqual(report["timing"]["status"], "hard_failure")
            self.assertFalse(list((run_dir / "outputs").rglob("PROGEN_LTSPICE_PROJECT.zip")))

        timing_events = [event for event in events if event.get("event") == "timing"]
        self.assertEqual([event["message"] for event in timing_events], [OVERDUE_MESSAGE, HARD_FAILURE_MESSAGE])
        self.assertFalse(
            any(
                event.get("event") == "stage"
                and event.get("stage") == "package_artifacts"
                and event.get("state") == "completed"
                for event in events
            )
        )

    def test_native_timing_release_gate_seals_download_before_late_clock_change(self) -> None:
        clock = FakeClock()
        events: list[dict] = []

        def emit(event: dict) -> None:
            events.append(event)
            if event.get("event") == "stage" and event.get("stage") == "package_artifacts" and event.get("state") == "started":
                clock.now = 1.9
            if event.get("event") == "stage" and event.get("stage") == "package_artifacts" and event.get("state") == "completed":
                clock.now = 2.1

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "release_gate_native.json"
            source.write_text(json.dumps(_rc_circuit()), encoding="utf-8")
            summary = run_donor_native_executable(
                source,
                output_root=root,
                label="release-gate-native",
                animation_budget_seconds=1,
                timing_clock=clock,
                event_callback=emit,
            )
            result = summary["results"][0]
            self.assertTrue(summary["ok"], summary)
            self.assertTrue(result["output_artifacts"])
            self.assertFalse(result["timing"]["hard_failure_emitted"])
            self.assertTrue(list((Path(summary["run_dir"]) / "outputs").rglob("PROGEN_LTSPICE_PROJECT.zip")))

        completed_index = next(
            index
            for index, event in enumerate(events)
            if event.get("event") == "stage" and event.get("stage") == "package_artifacts" and event.get("state") == "completed"
        )
        self.assertFalse(any(event.get("event") == "timing" and event.get("state") == "hard_failure" for event in events[completed_index + 1 :]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
