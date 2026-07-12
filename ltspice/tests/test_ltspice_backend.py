from __future__ import annotations

import copy
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any

from ltspice.pipeline.catalogue import load_catalogue, normalize_kind, resolve_profile
from ltspice.pipeline.component_placer import place_components
from ltspice.pipeline.component_selector import select_components
from ltspice.pipeline.directive_validator import DirectiveValidationError, translate_voltage_trace_labels, validate_analysis_directives
from ltspice.pipeline.geometry import Point, Segment, normalize_orientation, transform_offset, transform_point
from ltspice.pipeline.input_adapter import canonicalize_source
from ltspice.pipeline.ltspice_asc_parser import decode_lts_text, parse_asc
from ltspice.pipeline.ltspice_asc_writer import write_asc
from ltspice.pipeline.ltspice_wire_maker import _route_is_safe, build_wire_plan
from ltspice.pipeline.native_pin_mapper import translate_circuit_pins
from ltspice.pipeline.netlist_validator import validate_native_netlist
from ltspice.pipeline.progen_ltspice_executable import PROGRESS_POLICY, STAGES, run_executable
from ltspice.pipeline.value_editor import (
    ValueValidationError,
    apply_normal_mode_edits,
    rename_component_reference,
    validate_component_value,
    validate_metadata,
    validate_parameters,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DONOR_ROOT = REPOSITORY_ROOT.parent / "Ltspice" / "Donor"


def _static_circuit() -> dict[str, Any]:
    """A source-independent fixture accepted by the shared JSON fixer."""

    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "compatible_schema": "progen-kicad-placer-ir/v0.2",
        "circuit_id": "LTSPICE_STATIC_TEST",
        "circuit_name": "Static LTspice test fixture",
        "project": {
            "name": "ltspice_static_test",
            "title": "Static LTspice test fixture",
            "purpose": "native writer/reparser regression coverage",
            "target": "ltspice",
        },
        "components": [
            {
                "id": "R1",
                "ref": "R1",
                "kind": "RES",
                "type": "RES",
                "value": "1k",
                "pins": {"1": "VIN", "2": "VOUT"},
            },
            {
                "id": "R2",
                "ref": "R2",
                "kind": "RES",
                "type": "RES",
                "value": "2k",
                "pins": {"1": "VIN", "2": "VOUT"},
            },
        ],
        "nets": {
            "VIN": ["R1.1", "R2.1"],
            "VOUT": ["R1.2", "R2.2"],
        },
        "expected_netlist": {
            "nets": [
                {"name": "VIN", "members": ["R1.1", "R2.1"]},
                {"name": "VOUT", "members": ["R1.2", "R2.2"]},
            ]
        },
        "routing": {"mode": "combination"},
    }


def _mapped_model_circuit() -> dict[str, Any]:
    """Canonical KiCad pin numbering intentionally differs from LTspice order."""

    return {
        "schema_version": "progen-kicad-circuit-ir/v1",
        "circuit_id": "MAPPED_MODEL_TEST",
        "project": {"name": "mapped_model_test", "analysis": [".op"]},
        "components": [
            {"ref": "V1", "kind": "VDC", "value": 5, "pins": {"1": "VCC", "2": "GND"}},
            {"ref": "R1", "kind": "R", "value": "10k", "pins": {"1": "VCC", "2": "BASE"}},
            # Shared/KiCad NPN: 1=B, 2=C, 3=E. Native LTspice: 1=C, 2=B, 3=E.
            {"ref": "Q1", "kind": "NPN", "value": "NPN", "pins": {"1": "BASE", "2": "COL", "3": "GND"}},
            # Shared/KiCad NMOS: 1=G, 2=D, 3=S. Native LTspice: 1=D, 2=G, 3=S.
            {"ref": "M1", "kind": "NMOS", "value": "NMOS", "pins": {"1": "BASE", "2": "COL", "3": "GND"}},
            {"ref": "G1", "kind": "GND", "value": "GND", "pins": {"1": "GND"}},
        ],
        "nets": {
            "VCC": ["V1.1", "R1.1"],
            "BASE": ["R1.2", "Q1.1", "M1.1"],
            "COL": ["Q1.2", "M1.2"],
            "GND": ["V1.2", "Q1.3", "M1.3", "G1.1"],
        },
    }


class DonorDecoderAndParserTests(unittest.TestCase):
    def test_legacy_cp1252_micro_sign_decodes_and_parses(self) -> None:
        # LTspice donors can use a one-byte CP1252 micro sign instead of UTF-8.
        raw = (
            b"Version 4.1\n"
            b"SHEET 1 880 680\n"
            b"SYMBOL cap 256 16 R0\n"
            b"SYMATTR InstName Cdonor\n"
            b"SYMATTR Value 12\xb5\n"
        )
        text, encoding = decode_lts_text(raw)
        self.assertEqual(encoding, "cp1252")
        self.assertIn("12\u00b5", text)
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "legacy-cap.asc"
            source.write_bytes(raw)
            document = parse_asc(source)
        self.assertEqual(document.encoding, "cp1252")
        self.assertEqual(document.version, "4.1")
        self.assertEqual(document.sheet, (1, 880, 680))
        self.assertEqual(document.symbols[0].name, "cap")
        self.assertEqual(document.symbols[0].attributes["INSTNAME"], "Cdonor")
        self.assertEqual(document.symbols[0].attributes["VALUE"], "12\u00b5")

    @unittest.skipUnless(DONOR_ROOT.is_dir(), "The supplied LTspice donor directory is unavailable.")
    def test_supplied_donors_preserve_native_records(self) -> None:
        cases = {
            "empty.asc": {"encoding": "utf-8", "symbols": 0},
            "resis_13k_namechanged.asc": {
                "encoding": "utf-8",
                "symbols": 1,
                "ref": "gdgdgd",
                "value": "13k",
            },
            "cap_12u_namechange.asc": {
                "encoding": "cp1252",
                "symbols": 1,
                "ref": "name",
                "value": "12\u00b5",
            },
            "inducto_12H_peakcurrent2A_seriesresistance43_parralresistance21parralcap12F.asc": {
                "encoding": "utf-8",
                "symbols": 1,
                "ref": "L1",
                "value": "12H",
                "spice_line": "Ipk=2A Rser=43m Rpar=21m Cpar=12F",
            },
            "currentsource_13A.asc": {
                "encoding": "utf-8",
                "symbols": 1,
                "ref": "I1",
                "value": "13A",
                "windows": 2,
            },
        }
        for filename, expected in cases.items():
            with self.subTest(filename=filename):
                document = parse_asc(DONOR_ROOT / filename)
                self.assertEqual(document.version, "4.1")
                self.assertEqual(document.sheet, (1, 880, 680))
                self.assertEqual(document.encoding, expected["encoding"])
                self.assertEqual(len(document.symbols), expected["symbols"])
                if document.symbols:
                    symbol = document.symbols[0]
                    self.assertEqual(symbol.ref, expected["ref"])
                    self.assertEqual(symbol.attributes["VALUE"], expected["value"])
                    self.assertEqual(symbol.attributes.get("SPICELINE"), expected.get("spice_line"))
                    self.assertEqual(len(symbol.windows), expected.get("windows", 0))


class OrientationTransformTests(unittest.TestCase):
    def test_all_ltspice_orientations_transform_offsets_and_points(self) -> None:
        local = Point(16, 32)
        origin = Point(160, 320)
        expected_offsets = {
            "R0": Point(16, 32),
            "R90": Point(-32, 16),
            "R180": Point(-16, -32),
            "R270": Point(32, -16),
            "M0": Point(-16, 32),
            "M90": Point(32, 16),
            "M180": Point(16, -32),
            "M270": Point(-32, -16),
        }
        self.assertEqual(set(expected_offsets), {"R0", "R90", "R180", "R270", "M0", "M90", "M180", "M270"})
        for orientation, expected in expected_offsets.items():
            with self.subTest(orientation=orientation):
                self.assertEqual(normalize_orientation(orientation.lower()), orientation)
                self.assertEqual(transform_offset(local, orientation), expected)
                self.assertEqual(transform_point(origin, local, orientation), origin.translate(expected.x, expected.y))

    def test_unknown_orientation_is_rejected_before_geometry_is_written(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported LTspice orientation"):
            normalize_orientation("rotate_45")

    def test_route_planner_rejects_t_junctions_and_shared_endpoints(self) -> None:
        existing = [Segment(Point(16, -16), Point(16, 16))]
        self.assertFalse(_route_is_safe([Segment(Point(0, 0), Point(32, 0))], existing, set()))
        self.assertFalse(_route_is_safe([Segment(Point(16, 16), Point(48, 16))], existing, set()))


class SafeNormalModeEditorTests(unittest.TestCase):
    def test_values_and_whitelisted_parameters_are_normalized(self) -> None:
        resistor = resolve_profile("RES")
        capacitor = resolve_profile("CAP")
        voltage = resolve_profile("VOLTAGE")

        self.assertEqual(validate_component_value(resistor, "13kOhm"), "13k")
        self.assertEqual(validate_component_value(capacitor, "12uF"), "12u")
        self.assertEqual(validate_component_value(capacitor, "12µF"), "12u")
        self.assertEqual(validate_component_value(voltage, "pulse(0 5 0 1n 1n 1m 2m)"), "PULSE(0 5 0 1n 1n 1m 2m)")
        self.assertEqual(validate_parameters(resistor, {"M": "2", "temp": "25"}), {"m": "2", "temp": "25"})

    def test_unsafe_or_ambiguous_edits_are_refused(self) -> None:
        resistor = resolve_profile("RES")
        capacitor = resolve_profile("CAP")
        with self.assertRaises(ValueValidationError):
            validate_component_value(resistor, "1k\n.op")
        with self.assertRaises(ValueValidationError):
            validate_component_value(capacitor, "12F")
        with self.assertRaises(ValueValidationError):
            validate_parameters(resistor, {"SpiceLine": ".include untrusted.lib"})
        with self.assertRaises(ValueValidationError):
            validate_parameters(resistor, {"m": "1; .op"})

    def test_reference_rename_is_endpoint_aware_and_non_mutating(self) -> None:
        circuit = _static_circuit()
        circuit["components"].append(
            {
                "id": "R10",
                "ref": "R10",
                "kind": "RES",
                "value": "10k",
                "pins": {"1": "VIN", "2": "VOUT"},
            }
        )
        circuit["nets"]["VIN"].append("R10.1")
        circuit["nets"]["VOUT"].append("R10.2")
        circuit["expected_netlist"]["nets"][0]["members"].append("R10.1")
        circuit["expected_netlist"]["nets"][1]["members"].append("R10.2")
        original = copy.deepcopy(circuit)

        renamed = rename_component_reference(circuit, "R1", "RINPUT")

        self.assertEqual(circuit, original)
        self.assertEqual(renamed["components"][0]["ref"], "RINPUT")
        self.assertEqual(renamed["components"][0]["id"], "RINPUT")
        self.assertIn("RINPUT.1", renamed["nets"]["VIN"])
        self.assertIn("RINPUT.2", renamed["expected_netlist"]["nets"][1]["members"])
        self.assertIn("R10.1", renamed["nets"]["VIN"])
        self.assertNotIn("RINPUT0.1", renamed["nets"]["VIN"])
        with self.assertRaises(ValueValidationError):
            rename_component_reference(circuit, "R1", "R2")
        with self.assertRaises(ValueValidationError):
            rename_component_reference(circuit, "R1", "R_BAD\n.op")

    def test_reference_rename_refuses_to_orphan_an_analysis_card(self) -> None:
        circuit = _static_circuit()
        circuit["spice_directives"] = [".dc R1 0 5 1"]
        with self.assertRaisesRegex(ValueValidationError, "analysis directive"):
            rename_component_reference(circuit, "R1", "RINPUT")

    def test_audited_edits_can_continue_after_a_reference_rename(self) -> None:
        circuit = _static_circuit()
        profiles = {"R1": resolve_profile("RES"), "R2": resolve_profile("RES")}
        edited, audit = apply_normal_mode_edits(
            circuit,
            profiles,
            [
                {"ref": "R1", "field": "reference", "value": "RINPUT"},
                {"ref": "RINPUT", "field": "value", "value": "13kOhm"},
                {"ref": "RINPUT", "field": "parameters.m", "value": "2"},
            ],
        )
        component = next(item for item in edited["components"] if item["ref"] == "RINPUT")
        self.assertEqual(component["value"], "13k")
        self.assertEqual(component["parameters"], {"m": "2"})
        self.assertEqual([entry["ref"] for entry in audit["edits"]], ["R1", "RINPUT", "RINPUT"])
        self.assertEqual(edited["nets"]["VIN"][0], "RINPUT.1")


class StaticPipelineAndPackagingTests(unittest.TestCase):
    def test_static_pipeline_reparses_native_assets_and_separates_archives(self) -> None:
        circuit = _static_circuit()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "static-source.json"
            original = json.dumps(circuit, indent=2).encode("utf-8")
            source.write_bytes(original)
            events: list[dict[str, Any]] = []

            summary = run_executable(source, output_root=root, label="unittest", event_callback=events.append)

            self.assertTrue(summary["ok"], summary)
            self.assertEqual(summary["progress_policy"], PROGRESS_POLICY)
            self.assertEqual(summary["input_count"], 1)
            self.assertEqual(summary["accepted_count"], 1)
            result = summary["results"][0]
            self.assertTrue(result["final_validation"]["ok"], result["final_validation"])
            self.assertEqual(result["final_validation"]["stage_status"]["simulation"], "not_run")

            stage_events = [event for event in events if event.get("event") == "stage"]
            expected_stage_states = [
                (stage, state)
                for stage, _percent in STAGES
                for state in ("started", "completed")
            ]
            self.assertEqual(
                [(event["stage"], event["state"]) for event in stage_events],
                expected_stage_states,
            )

            run_dir = Path(summary["run_dir"])
            asc_path = run_dir / result["asc_path"]
            native_report = json.loads(
                (run_dir / result["generation_dir"] / "internal" / "native-netlist-validation-report.json").read_text(encoding="utf-8")
            )
            self.assertTrue(asc_path.is_file())
            self.assertTrue(native_report["ok"], native_report)
            self.assertEqual(parse_asc(asc_path).encoding, "utf-8")

            artifacts = result["output_artifacts"]
            self.assertIsNotNone(artifacts)
            assert artifacts is not None
            self.assertEqual(artifacts["user_project"]["visibility"], "user_downloadable")
            self.assertEqual(artifacts["internal_bundle"]["visibility"], "internal_only")
            user_zip = run_dir / artifacts["user_project"]["path"]
            internal_zip = run_dir / artifacts["internal_bundle"]["path"]
            self.assertTrue(user_zip.is_file())
            self.assertTrue(internal_zip.is_file())

            with zipfile.ZipFile(user_zip) as archive:
                user_names = set(archive.namelist())
            with zipfile.ZipFile(internal_zip) as archive:
                internal_names = set(archive.namelist())
                packaged_original = archive.read("internal/main-input-original.json")

        self.assertIn("project/ltspice_static_test.asc", user_names)
        self.assertIn("project/progeneda_res.asy", user_names)
        self.assertIn("project/README_OPEN_IN_LTSPICE.txt", user_names)
        self.assertFalse(any(name.startswith("internal/") or name.endswith(".json") for name in user_names))
        self.assertIn("internal/main-input-original.json", internal_names)
        self.assertIn("internal/native-netlist-validation-report.json", internal_names)
        self.assertIn("reconstruction/ltspice_static_test.asc", internal_names)
        self.assertFalse(any(name.endswith(".asy") for name in internal_names))
        self.assertEqual(packaged_original, original)


class CanonicalMappingAndSafetyTests(unittest.TestCase):
    def test_zero_sin_micro_and_source_conflicts_are_handled_deterministically(self) -> None:
        voltage = resolve_profile("VDC")
        capacitor = resolve_profile("C")
        inductor = resolve_profile("L")
        self.assertEqual(validate_component_value(voltage, 0), "0")
        self.assertEqual(validate_component_value(voltage, "SIN(0 1 1k)"), "SINE(0 1 1k)")
        self.assertEqual(validate_component_value(capacitor, "12µF"), "12u")
        self.assertEqual(validate_parameters(inductor, {"ipk": "2A"}), {"ipk": "2"})
        self.assertEqual(validate_parameters(resolve_profile("I"), {"load": True}), {"load": "True"})
        with self.assertRaises(ValueValidationError):
            validate_component_value(voltage, "SINE(not_a_number)")
        with self.assertRaises(ValueValidationError):
            validate_parameters(voltage, {"pulse": "0 5 0 1n 1n 1m 2m", "sine": "0 1 1k"})
        with self.assertRaises(ValueValidationError):
            validate_parameters(voltage, {"dc": "5", "pulse": "0 5 0 1n 1n 1m 2m"})
        with self.assertRaises(ValueValidationError):
            validate_parameters(capacitor, {"ic": "(1 2)"})

    def test_named_model_and_metadata_whitelist_do_not_silently_fall_back(self) -> None:
        selected, report = select_components(
            {
                "components": [
                    {"ref": "D1", "kind": "D", "value": "1N4148", "pins": {"1": "A", "2": "K"}},
                ]
            }
        )
        self.assertEqual(selected[0].kind, "1N4148")
        self.assertEqual(selected[0].value, "PROGEN_1N4148_APPROX")
        self.assertFalse(any("generic model" in item for item in report["warnings"]))
        resistor = resolve_profile("R")
        self.assertEqual(validate_metadata(resistor, {"tolerance": "1%"}), {"tolerance": "1%"})
        with self.assertRaises(ValueValidationError):
            validate_metadata(resistor, {"spiceline": ".include outside.lib"})

    def test_extensions_are_rehydrated_only_after_shared_canonicalization(self) -> None:
        circuit = _static_circuit()
        circuit["components"][0].update(
            {
                "parameters": {"m": "2"},
                "metadata": {"tolerance": "1%"},
                "ltspice_at": [320, 480],
                "ltspice_orientation": "M90",
            }
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "extensions.json"
            source.write_text(json.dumps(circuit), encoding="utf-8")
            fixed, report, _original = canonicalize_source(source)
        r1 = next(item for item in fixed["components"] if item["ref"] == "R1")
        self.assertEqual(r1["parameters"], {"m": "2"})
        self.assertEqual(r1["metadata"], {"tolerance": "1%"})
        self.assertEqual(r1["ltspice_at"], [320, 480])
        self.assertEqual(r1["ltspice_orientation"], "M90")
        self.assertIn("R1.parameters", report["ltspice_component_extensions_restored"])

    def test_all_supported_backend_aliases_survive_the_shared_fixer_by_stable_ref(self) -> None:
        aliases = ["I", "CURRENT", "POT", "C_ELEC", "V", "VOLTAGE", "INDUCTOR", "SINE_VOLTAGE", "PULSE_VOLTAGE", "F", "0"]
        raw = {
            "components": [
                {"ref": f"X{index}", "kind": alias, "value": "1"}
                for index, alias in enumerate(aliases, 1)
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "aliases.json"
            source.write_text(json.dumps(raw), encoding="utf-8")
            fixed, report, _original = canonicalize_source(source)
        by_ref = {item["ref"]: item["kind"] for item in fixed["components"]}
        self.assertEqual([by_ref[f"X{index}"] for index in range(1, len(aliases) + 1)], [normalize_kind(alias) for alias in aliases])
        self.assertTrue(any(entry.endswith(".kind") for entry in report["ltspice_component_extensions_restored"]))

    def test_cross_backend_pin_numbers_translate_before_native_wiring(self) -> None:
        circuit = _mapped_model_circuit()
        selected, _report = select_components(circuit)
        native, translation = translate_circuit_pins(circuit, selected)
        self.assertEqual(native["nets"]["BASE"], ["R1.2", "Q1.2", "M1.2"])
        self.assertEqual(native["nets"]["COL"], ["Q1.1", "M1.1"])
        self.assertEqual(translation["component_pin_maps"]["Q1"], {"1": "2", "2": "1", "3": "3"})
        self.assertEqual(translation["component_pin_maps"]["M1"], {"1": "2", "2": "1", "3": "3"})

    def test_model_wrappers_and_native_validator_round_trip(self) -> None:
        circuit = _mapped_model_circuit()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "mapped.json"
            source.write_text(json.dumps(circuit), encoding="utf-8")
            summary = run_executable(source, output_root=root, label="mapped")
            self.assertTrue(summary["ok"], summary)
            result = summary["results"][0]
            run_dir = Path(summary["run_dir"])
            native_report = json.loads(
                (run_dir / result["generation_dir"] / "internal" / "native-netlist-validation-report.json").read_text(encoding="utf-8")
            )
            asc = (run_dir / result["asc_path"]).read_text(encoding="ascii")
        self.assertTrue(native_report["ok"], native_report)
        self.assertEqual(native_report["model_definitions"]["PROGEN_NMOS"]["kind"], "subckt")
        self.assertEqual(native_report["model_definitions"]["PROGEN_NPN"]["pins"], ["C", "B", "E"])
        self.assertIn("SYMBOL progeneda_npn", asc)
        self.assertIn("SYMBOL progeneda_nmos", asc)

    def test_validator_rejects_altered_semantic_attribute_and_directive(self) -> None:
        circuit = _mapped_model_circuit()
        selected, _selection = select_components(circuit)
        native, _translation = translate_circuit_pins(circuit, selected)
        placed, _placement = place_components(native, selected)
        wire_plan = build_wire_plan(native, placed)
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            writer = write_asc(
                project_dir=project,
                project_name="tamper",
                placed=placed,
                wire_segments=wire_plan.segments,
                flags=wire_plan.flags,
                directives=[".op"],
            )
            clean = validate_native_netlist(
                asc_path=writer.asc_path,
                project_dir=project,
                placed=placed,
                wire_plan=wire_plan,
                requested_directives=[".op"],
            )
            self.assertTrue(clean["ok"], clean)
            text = writer.asc_path.read_text(encoding="ascii")
            writer.asc_path.write_text(text.replace("SYMATTR Value 5\n", "SYMATTR Value 5\nSYMATTR SpiceLine2 injected=1\n", 1), encoding="ascii")
            altered_attribute = validate_native_netlist(
                asc_path=writer.asc_path,
                project_dir=project,
                placed=placed,
                wire_plan=wire_plan,
                requested_directives=[".op"],
            )
            self.assertFalse(altered_attribute["ok"])
            self.assertTrue(any("semantic SYMATTR mismatch" in error for error in altered_attribute["errors"]))
            writer.asc_path.write_text(text.replace("!.op", "!.tran 1u 1m"), encoding="ascii")
            altered_directive = validate_native_netlist(
                asc_path=writer.asc_path,
                project_dir=project,
                placed=placed,
                wire_plan=wire_plan,
                requested_directives=[".op"],
            )
        self.assertFalse(altered_directive["ok"])
        self.assertTrue(any("Native directives mismatch" in error for error in altered_directive["errors"]))

    def test_duplicate_default_ids_and_unsafe_ids_never_overwrite_or_escape(self) -> None:
        first = _static_circuit()
        second = _static_circuit()
        first.pop("circuit_id")
        second.pop("circuit_id")
        second["components"][0]["value"] = "3k"
        unsafe = _static_circuit()
        unsafe["circuit_id"] = "../../outside"
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "inputs"
            source_dir.mkdir()
            (source_dir / "first.json").write_text(json.dumps(first), encoding="utf-8")
            (source_dir / "second.json").write_text(json.dumps(second), encoding="utf-8")
            summary = run_executable(source_dir, output_root=root, label="duplicate")
            self.assertTrue(summary["ok"], summary)
            self.assertEqual([result["circuit_id"] for result in summary["results"]], ["FIXED001", "FIXED001"])
            artifact_ids = [result["artifact_id"] for result in summary["results"]]
            self.assertEqual(len(set(artifact_ids)), 2)
            self.assertTrue(all((Path(summary["run_dir"]) / result["generation_dir"]).is_dir() for result in summary["results"]))
            unsafe_source = root / "unsafe.json"
            unsafe_source.write_text(json.dumps(unsafe), encoding="utf-8")
            unsafe_summary = run_executable(unsafe_source, output_root=root, label="unsafe")
        self.assertTrue(unsafe_summary["ok"], unsafe_summary)
        artifact = unsafe_summary["results"][0]["output_artifacts"]
        assert artifact is not None
        self.assertEqual(artifact["safe_output_id"], "outside")
        self.assertNotIn("..", artifact["user_project"]["path"])

    def test_unknown_analysis_source_is_rejected_without_an_oracle(self) -> None:
        circuit = _static_circuit()
        circuit["spice_directives"] = [".dc DOES_NOT_EXIST 0 1 0.1"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "bad-analysis.json"
            source.write_text(json.dumps(circuit), encoding="utf-8")
            summary = run_executable(source, output_root=root, label="bad-analysis")
        self.assertFalse(summary["ok"])
        self.assertIn("unknown source", summary["results"][0]["error"])

    def test_analysis_cards_have_complete_numeric_grammar_and_multi_dc_reference_checks(self) -> None:
        invalid = [
            ".ac nonsense",
            ".tran nonsense",
            ".dc V1 nope 1 .1",
            ".tf V(VIN)",
            ".noise V(VIN) V1",
            ".tf POTATO V1",
            ".noise POTATO V1 dec 10 1 1k",
            ".four 1k POTATO",
            ".save POTATO",
            ".dc V1 0 1 0",
            ".tran 0 1m",
            ".ac dec 10 0 1k",
            ".noise V(VIN) V1 dec 10 0 1k",
        ]
        for card in invalid:
            with self.subTest(card=card), self.assertRaises(DirectiveValidationError):
                validate_analysis_directives([card])
        circuit = _mapped_model_circuit()
        circuit["spice_directives"] = [".dc V1 0 1 .1 V_DOES_NOT_EXIST 0 1 .1"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "bad-multi-dc.json"
            source.write_text(json.dumps(circuit), encoding="utf-8")
            summary = run_executable(source, output_root=root, label="bad-multi-dc")
        self.assertFalse(summary["ok"])
        self.assertIn("unknown source", summary["results"][0]["error"])

    def test_analysis_voltage_traces_follow_native_label_sanitization(self) -> None:
        directives, report = translate_voltage_trace_labels([".save V(NET-A) V(GND)"], {"NET-A": "NET_A", "GND": "0"})
        self.assertEqual(directives, [".save V(NET_A) V(0)"])
        self.assertEqual(report["voltage_trace_replacements"], [{"from": "NET-A", "to": "NET_A"}, {"from": "GND", "to": "0"}])

    def test_writer_grows_sheet_for_large_placed_designs(self) -> None:
        circuit = {
            "components": [
                {"ref": f"R{index}", "kind": "R", "value": "1k", "pins": {"1": f"N{index}A", "2": f"N{index}B"}}
                for index in range(1, 50)
            ]
        }
        selected, _report = select_components(circuit)
        placed, _placement = place_components(circuit, selected)
        with tempfile.TemporaryDirectory() as temp_dir:
            result = write_asc(
                project_dir=Path(temp_dir),
                project_name="large",
                placed=placed,
                wire_segments=[],
                flags=[],
            )
            parsed = parse_asc(result.asc_path)
        assert parsed.sheet is not None
        self.assertGreater(parsed.sheet[1], 1760)
        self.assertGreater(parsed.sheet[2], 1360)

    def test_every_catalogue_default_has_a_complete_canonical_pin_mapping(self) -> None:
        for kind, profile in sorted(load_catalogue().items()):
            with self.subTest(kind=kind):
                pins: dict[str, str] = {}
                for pin in profile.pins:
                    aliases = [alias for alias, native in (profile.canonical_pin_map or {}).items() if native == pin.number]
                    canonical_pin = next((alias for alias in aliases if not alias.isdigit()), aliases[0] if aliases else pin.number)
                    pins[canonical_pin] = f"N_{pin.number}"
                selected, _report = select_components(
                    {"components": [{"ref": f"X_{kind}", "kind": kind, "value": profile.default_value, "pins": pins}]}
                )
                self.assertEqual(selected[0].profile.kind, kind)


if __name__ == "__main__":
    unittest.main()
