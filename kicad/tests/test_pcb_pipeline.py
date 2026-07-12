from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from kicad.pcb.footprint_catalogue import SOURCE_PACK_PATH, load_footprint_catalogue
from kicad.pcb.footprint_placer import place_footprints
from kicad.pcb.kicad_pcb_parser import parse_kicad_pcb
from kicad.pcb.kicad_pcb_writer import write_kicad_pcb
from kicad.pcb.pcb_router import PCBRoutePlan, _all_pad_endpoints, route_pcb_with_retries
from kicad.pcb.pcb_validator import validate_pcb
from kicad.pcb.physical_design_compiler import compile_physical_design
from kicad.pcb.pipeline import (
    NEAR_COMPLETE_DEFAULT_ORDER_SEEDS,
    _near_complete_rescue_order_seeds,
    _routing_budget,
    generate_pcb_for_project,
)
from kicad.pipeline.progen_kicad_executable import run_pcb_only
from kicad.pipeline.kicad_wire_maker import generate_wired_projects_from_final_json


def _minimal_circuit() -> dict[str, object]:
    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "compatible_schema": "progen-kicad-placer-ir/v0.2",
        "circuit_id": "PCB_UNIT_PARALLEL",
        "project": {
            "name": "pcb_unit_parallel",
            "title": "PCB unit parallel resistors",
            "purpose": "PCB pipeline regression test",
            "target": "kicad_schematic",
            "schematic_only": False,
        },
        "components": [
            {
                "id": "R1",
                "ref": "R1",
                "kind": "RES",
                "type": "RES",
                "value": "1k",
                "role": "passive",
                "block": "",
                "pins": {"1": "INPUT", "2": "OUTPUT"},
            },
            {
                "id": "R2",
                "ref": "R2",
                "kind": "RES",
                "type": "RES",
                "value": "2k",
                "role": "passive",
                "block": "",
                "pins": {"1": "INPUT", "2": "OUTPUT"},
            },
        ],
        "nets": {"INPUT": ["R1.1", "R2.1"], "OUTPUT": ["R1.2", "R2.2"]},
        "expected_netlist": {
            "nets": [
                {"name": "INPUT", "members": ["R1.1", "R2.1"]},
                {"name": "OUTPUT", "members": ["R1.2", "R2.2"]},
            ]
        },
        "routing": {
            "mode": "combination",
            "terminal_policy": {
                "power_and_ground_terminal": True,
                "high_fanout_threshold": 6,
                "fallback_unroutable_or_invalid_wires_to_terminal": True,
                "terminal_stage_runs_after_wiring": True,
            },
        },
        "layout_intent": {
            "arrangement_style": "clustered_blocks_square_fill",
            "square_fill_preferred": True,
            "allow_component_rotation": True,
        },
    }


class KiCadPCBPipelineTests(unittest.TestCase):
    def test_near_complete_seeded_rescue_is_bounded_and_retained(self) -> None:
        circuit = _minimal_circuit()
        design = compile_physical_design(circuit, {})
        placement = place_footprints(design)
        partial = PCBRoutePlan(
            grid=1.27,
            track_width=0.25,
            via_size=0.8,
            via_drill=0.4,
            segments=(),
            vias=(),
            net_results=(
                {
                    "net": "INPUT",
                    "status": "unroutable",
                    "member_count": 2,
                    "routed_member_count": 1,
                    "failed_members": ["R2.1"],
                },
            ),
        )
        complete = PCBRoutePlan(
            grid=1.27,
            track_width=0.25,
            via_size=0.8,
            via_drill=0.4,
            segments=(),
            vias=(),
            net_results=(
                {
                    "net": "INPUT",
                    "status": "routed",
                    "member_count": 2,
                    "routed_member_count": 2,
                    "failed_members": [],
                },
            ),
        )
        with patch("kicad.pcb.pcb_router.route_pcb", side_effect=(partial, complete)) as mocked:
            plan, variants = route_pcb_with_retries(
                design,
                placement,
                max_attempts=1,
                near_complete_order_seeds=(404,),
                near_complete_max_unrouted_nets=2,
            )
        self.assertEqual(plan.unrouted_net_count, 0)
        self.assertEqual(len(variants), 2)
        self.assertEqual(variants[-1]["order_strategy"], "seeded_random")
        self.assertEqual(variants[-1]["order_seed"], 404)
        self.assertEqual(mocked.call_args_list[-1].kwargs["order_seed"], 404)

    def test_variations_select_one_deterministic_near_complete_order(self) -> None:
        self.assertEqual(_near_complete_rescue_order_seeds(_minimal_circuit()), NEAR_COMPLETE_DEFAULT_ORDER_SEEDS)
        variation = _minimal_circuit()
        variation["generation_variation"] = {"enabled": True, "variation_index": 2}
        self.assertEqual(_near_complete_rescue_order_seeds(variation), (101,))

    def test_large_physical_design_uses_adaptive_budget_not_component_rejection(self) -> None:
        budget = _routing_budget(199, 140)
        self.assertEqual(budget["profile"], "extra_large")
        self.assertEqual(budget["grid_mm"], 2.54)
        self.assertGreater(int(budget["max_attempts"]), 0)
        self.assertGreater(int(budget["max_astar_expansions"]), 0)

    def test_embedded_source_pack_is_self_contained_and_digest_checked(self) -> None:
        catalogue = load_footprint_catalogue()
        record = catalogue.record("Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
        self.assertTrue(SOURCE_PACK_PATH.is_file())
        self.assertIn('(footprint "SOIC-8_3.9x4.9mm_P1.27mm"', record.source_text)
        self.assertEqual(hashlib.sha256(record.source_text.encode("utf-8")).hexdigest(), record.sha256)
        self.assertEqual(catalogue.source_metadata["kicad_version"], "10.0.4")
        self.assertGreaterEqual(catalogue.source_metadata["record_count"], 34)

    def test_minimal_board_round_trip_has_exact_nets_and_connectivity(self) -> None:
        circuit = _minimal_circuit()
        design = compile_physical_design(circuit, {})
        self.assertEqual(len(design.components), 2)
        self.assertEqual(design.nets["INPUT"], ("R1.1", "R2.1"))
        placement = place_footprints(design)
        route_plan, variants = route_pcb_with_retries(design, placement, max_astar_expansions=30_000)
        self.assertEqual(route_plan.unrouted_net_count, 0)
        self.assertTrue(any(variant["accepted"] for variant in variants))
        with tempfile.TemporaryDirectory() as temp_dir:
            path = write_kicad_pcb(
                Path(temp_dir),
                "pcb_unit_parallel",
                design,
                placement,
                route_plan,
                schematic_file="pcb_unit_parallel.kicad_sch",
            )
            parsed = parse_kicad_pcb(path)
            report = validate_pcb(path, design, placement, route_plan)
            board_text = path.read_text(encoding="utf-8")
        self.assertTrue(parsed.file_validity["ok"])
        self.assertEqual(len(parsed.footprints), 2)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["disconnected_nets"], [])
        self.assertGreaterEqual(board_text.count("(hide yes)"), 2)

    def test_duplicate_number_source_pads_keep_individual_world_coordinates(self) -> None:
        circuit = {
            "circuit_id": "PCB_UNIT_ESP_DUPLICATE_PADS",
            "project": {"name": "pcb_unit_esp_duplicate_pads"},
            "components": [
                {
                    "ref": "U1",
                    "kind": "ESP32_WROOM",
                    "value": "ESP32-WROOM",
                    "pins": {"1": "GND", "2": "+3V3"},
                }
            ],
        }
        design = compile_physical_design(circuit, {})
        placement = place_footprints(design)
        source_pad_39_records = [
            pad for pad in design.components[0].footprint.pads if str(pad["number"]) == "39"
        ]
        source_pad_39_points = {tuple(float(value) for value in pad["at"]) for pad in source_pad_39_records}
        pad_39_points = {
            endpoint.point for endpoint in _all_pad_endpoints(design, placement) if endpoint.pad == "39"
        }
        self.assertGreater(len(source_pad_39_records), 1)
        self.assertEqual(len(pad_39_points), len(source_pad_39_points))

    def test_nonphysical_design_generates_no_pcb_candidate(self) -> None:
        circuit = {
            "circuit_id": "PCB_UNIT_NONPHYSICAL",
            "project": {"name": "pcb_unit_nonphysical"},
            "components": [{"ref": "#PWR01", "kind": "GROUND", "value": "GND", "pins": {"1": "GND"}}],
            "nets": [{"name": "GND", "nodes": ["#PWR01.1"]}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            (project_dir / "pcb_unit_nonphysical.kicad_pro").write_text(
                json.dumps({"board": {"design_settings": {"defaults": {}, "rules": {}}}}),
                encoding="utf-8",
            )
            report = generate_pcb_for_project(
                circuit=circuit,
                routing_placement={},
                project_dir=project_dir,
                project_name="pcb_unit_nonphysical",
                schematic_file="pcb_unit_nonphysical.kicad_sch",
            )
            self.assertFalse(report["generated"])
            self.assertEqual(report["reason"], "no_supported_physical_components")
            self.assertEqual(list(project_dir.glob("*.kicad_pcb")), [])

    def test_canonical_pipeline_packages_optional_direct_pcb(self) -> None:
        circuit = _minimal_circuit()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "final_json"
            source.mkdir()
            (source / "circuit.json").write_text(json.dumps(circuit, indent=2), encoding="utf-8")
            summary = generate_wired_projects_from_final_json(
                source,
                examples_root=root,
                run_dir=root / "generated",
                routing_mode="combination",
            )
            result = summary["results"][0]
            project_dir = root / "generated" / result["project_dir"]
            pcb_report = json.loads((project_dir / "pcb_pipeline_report.json").read_text(encoding="utf-8"))
            self.assertTrue(pcb_report["generated"], pcb_report)
            process = json.loads((project_dir / "pcb_process_profile.json").read_text(encoding="utf-8"))
            self.assertEqual(process["layer_count"], 2)
            artifacts = result["output_artifacts"]
            self.assertIsNotNone(artifacts["user_pcb"])
            direct_pcb = root / "generated" / artifacts["user_pcb"]["path"]
            self.assertTrue(direct_pcb.is_file())
            user_zip = root / "generated" / artifacts["user_project"]["path"]
            with zipfile.ZipFile(user_zip) as archive:
                names = set(archive.namelist())
                self.assertTrue(any(name.endswith(".kicad_pcb") for name in names))
                self.assertFalse(any("candidate" in name or "pcb_internal" in name for name in names))

    def test_pcb_only_command_exposes_accepted_native_board(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "main.json"
            source.write_text(json.dumps(_minimal_circuit(), indent=2), encoding="utf-8")
            summary = run_pcb_only(
                source,
                output_root=root,
                label="pcb_only_test",
                routing_mode="combination",
            )
            self.assertTrue(summary["ok"], summary)
            self.assertTrue(summary["all_pcb_ready"], summary)
            self.assertEqual(summary["accepted_pcb_count"], 1)
            board = Path(summary["run_dir"]) / str(summary["pcb_exports"][0]["pcb_file"])
            self.assertTrue(board.is_file())
            self.assertEqual(board.suffix, ".kicad_pcb")
            manifest = Path(summary["run_dir"]) / "pcb_only_manifest.json"
            self.assertTrue(manifest.is_file())


if __name__ == "__main__":
    unittest.main()
