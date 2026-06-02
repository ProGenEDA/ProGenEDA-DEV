import tempfile
import unittest
from collections import defaultdict
from pathlib import Path

from proteusgen.mixed_rcl import MixedRclGenerationBlocked, generate_mixed_rcl_project_from_payload, validate_mixed_rcl_payload
from proteusgen.mixed_rcl_examples import predefined_mixed_rcl_cases
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


class MixedRclTests(unittest.TestCase):
    def test_predefined_mixed_rcl_cases_validate(self) -> None:
        cases = predefined_mixed_rcl_cases()
        self.assertEqual(len(cases), 17)
        for payload in cases:
            with self.subTest(payload["project"]["output_basename"]):
                report = validate_mixed_rcl_payload(payload)
                self.assertTrue(report.valid, report.as_dict())

    def test_predefined_mixed_rcl_cases_generate_static_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for payload in predefined_mixed_rcl_cases():
                basename = payload["project"]["output_basename"]
                with self.subTest(basename):
                    result = generate_mixed_rcl_project_from_payload(payload, root / basename)
                    manifest = result.manifest
                    self.assertEqual(manifest["static_validation_issues"], [])
                    self.assertEqual(manifest["component_count_emitted_cdb"], manifest["component_count_requested"])
                    self.assertEqual(manifest["power_bridge_count"], 1)
                    dsn = read_internal_file(result.output_path, "ROOT.DSN")
                    cdb = read_internal_file(result.output_path, "ROOT.CDB")
                    chunk = _extract_object_chunk(dsn)
                    self.assertEqual(chunk.count(b"$TERPOWER"), 1)
                    self.assertIn(b"$TERGROUND", chunk)
                    self.assertEqual(cdb.count(b"RESISTOR"), manifest["resistor_count"])
                    self.assertEqual(cdb.count(b"CAPACITOR"), manifest["capacitor_count"])
                    self.assertEqual(chunk.count(b"REALIND"), manifest["inductor_count"] * 3)

    def test_locked_21_case_uses_correct_rule_topology(self) -> None:
        payload = predefined_mixed_rcl_cases()[1]
        with tempfile.TemporaryDirectory() as directory:
            result = generate_mixed_rcl_project_from_payload(payload, directory)
            manifest = result.manifest
            self.assertEqual(manifest["component_count_emitted_dsn"], 21)
            self.assertEqual(manifest["resistor_count"], 7)
            self.assertEqual(manifest["capacitor_count"], 7)
            self.assertEqual(manifest["inductor_count"], 7)
            self.assertEqual(manifest["group_modes"], ["RCL", "RC", "LC", "RCL", "RL", "RC", "RCL", "LC", "RL"])

            refs_by_edge: dict[frozenset[str], str] = {}
            degree: dict[str, int] = defaultdict(int)
            for component in manifest["components"]:
                left, right = component["nodes"]
                refs_by_edge[frozenset((left, right))] = component["ref"]
                degree[left] += 1
                degree[right] += 1

            rows = [
                (["V0", "A1", "B1", "D1", "A2", "D2", "A3", "M0"], ["R1", "C1", "L1", "R2", "C2", "C3", "L2"]),
                (["V0", "A4", "B4", "E1", "A5", "E2", "A6", "M0"], ["R3", "C4", "L3", "R4", "L4", "R5", "C5"]),
                (["M0", "A7", "B7", "F1", "A8", "F2", "A9", "G0"], ["R6", "C6", "L5", "C7", "L6", "R7", "L7"]),
            ]
            used_refs: list[str] = []
            for node_path, expected_refs in rows:
                row_refs = [refs_by_edge[frozenset(edge)] for edge in zip(node_path, node_path[1:])]
                self.assertEqual(row_refs, expected_refs)
                used_refs.extend(row_refs)

            self.assertEqual(len(used_refs), 21)
            self.assertEqual(len(set(used_refs)), 21)
            self.assertEqual(degree["V0"], 2)
            self.assertEqual(degree["M0"], 3)
            self.assertEqual(degree["G0"], 1)

    def test_requested_rcl_filter_uses_explicit_values_and_topology(self) -> None:
        payload = {
            "schema_version": "mixed-rcl-circuit-ir/v0.1",
            "generator_target": "proteus-8.13-mixed-rcl-locked",
            "project": {
                "name": "RCL_REQUESTED_FILTER_VALUES",
                "output_basename": "RCL_REQUESTED_FILTER_VALUES",
                "base": "E001_EMPTY_BASE",
                "units": "proteus_internal",
            },
            "groups": [
                {"mode": "RL", "start": "V0", "end": "B0"},
                {"mode": "C", "start": "A1", "end": "N2"},
                {"mode": "L", "start": "B0", "end": "N3"},
                {"mode": "R", "start": "N2", "end": "N3"},
                {"mode": "L", "start": "N2", "end": "G0"},
                {"mode": "C", "start": "N3", "end": "G0"},
            ],
            "component_values": {
                "R1": "10R",
                "R2": "50R",
                "L1": "2mH",
                "L2": "5mH",
                "L3": "10m",
                "C1": "4u7",
                "C2": "10u",
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            result = generate_mixed_rcl_project_from_payload(payload, directory)
            manifest = result.manifest
            self.assertEqual(manifest["static_validation_issues"], [])
            self.assertEqual(manifest["component_count_emitted_dsn"], 7)
            self.assertEqual(manifest["resistor_count"], 2)
            self.assertEqual(manifest["capacitor_count"], 2)
            self.assertEqual(manifest["inductor_count"], 3)
            self.assertEqual(manifest["group_modes"], ["RL", "C", "L", "R", "L", "C"])

            by_ref = {component["ref"]: component for component in manifest["components"]}
            expected = {
                "R1": ("10R", ("V0", "A1")),
                "L1": ("2mH", ("A1", "B0")),
                "C1": ("4u7", ("A1", "N2")),
                "L2": ("5mH", ("B0", "N3")),
                "R2": ("50R", ("N2", "N3")),
                "L3": ("10m", ("N2", "G0")),
                "C2": ("10u", ("N3", "G0")),
            }
            self.assertEqual(set(by_ref), set(expected))
            for ref, (value, nodes) in expected.items():
                self.assertEqual(by_ref[ref]["value"], value)
                self.assertEqual(tuple(by_ref[ref]["nodes"]), nodes)

    def test_value_override_must_fit_current_donor_record(self) -> None:
        payload = {
            "schema_version": "mixed-rcl-circuit-ir/v0.1",
            "generator_target": "proteus-8.13-mixed-rcl-locked",
            "project": {"name": "BAD_VALUE", "output_basename": "BAD_VALUE"},
            "groups": [{"mode": "C", "start": "V0", "end": "G0"}],
            "component_values": {"C1": "4.7uF"},
        }
        report = validate_mixed_rcl_payload(payload)
        self.assertFalse(report.valid)
        self.assertIn("not safe for the current donor record", " ".join(report.errors))

    def test_short_resistor_value_override_is_rejected(self) -> None:
        payload = {
            "schema_version": "mixed-rcl-circuit-ir/v0.1",
            "generator_target": "proteus-8.13-mixed-rcl-locked",
            "project": {"name": "BAD_R_VALUE", "output_basename": "BAD_R_VALUE"},
            "groups": [{"mode": "R", "start": "V0", "end": "G0"}],
            "component_values": {"R1": "10"},
        }
        report = validate_mixed_rcl_payload(payload)
        self.assertFalse(report.valid)
        self.assertIn("not safe for the current donor record", " ".join(report.errors))

    def test_unsupported_label_is_rejected(self) -> None:
        payload = predefined_mixed_rcl_cases()[0]
        payload["groups"][0]["start"] = "POWER"
        report = validate_mixed_rcl_payload(payload)
        self.assertFalse(report.valid)
        with self.assertRaises(MixedRclGenerationBlocked):
            generate_mixed_rcl_project_from_payload(payload, Path(tempfile.gettempdir()) / "blocked_mixed_rcl_case")


if __name__ == "__main__":
    unittest.main()
