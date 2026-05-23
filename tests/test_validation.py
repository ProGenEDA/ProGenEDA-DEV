import unittest

from proteusgen.circuit_ir import load_json
from proteusgen.templates import repository_root
from proteusgen.validation import validate_payload


def example(name: str) -> dict:
    return load_json(repository_root() / "examples" / name)


class ValidationTests(unittest.TestCase):
    def test_passive_fixture_recipe_is_generation_ready(self) -> None:
        report = validate_payload(example("single_resistor_vcc_gnd.json"))
        self.assertTrue(report.valid)

    def test_hc08_control_is_allowed_only_as_diagnostic(self) -> None:
        report = validate_payload(example("hc08_d02_diagnostic_control.json"))
        self.assertTrue(report.valid)

    def test_reference_and_circuit_is_well_formed_but_not_generation_ready(self) -> None:
        structural_report = validate_payload(example("and_reference_pending_d05.json"), require_generation_ready=False)
        readiness_report = validate_payload(example("and_reference_pending_d05.json"), require_generation_ready=True)
        self.assertTrue(structural_report.valid)
        self.assertFalse(readiness_report.valid)
        codes = {issue.code for issue in readiness_report.errors}
        self.assertIn("COMPONENT_NOT_GENERATION_READY", codes)
        self.assertIn("LAYOUT_RENDERING_UNVALIDATED", codes)

    def test_more_than_one_hc08_package_is_rejected(self) -> None:
        payload = example("and_reference_pending_d05.json")
        payload["circuit"]["components"].append({"ref": "U2", "part": "74HC08"})
        report = validate_payload(payload, require_generation_ready=False)
        self.assertTrue(any(issue.code == "MULTIPLE_74HC08_PACKAGES_UNSUPPORTED" for issue in report.errors))

    def test_unknown_contract_version_is_rejected(self) -> None:
        payload = example("single_resistor_vcc_gnd.json")
        payload["version"] = "9.9"
        report = validate_payload(payload)
        self.assertTrue(any(issue.code == "UNSUPPORTED_IR_VERSION" for issue in report.errors))


if __name__ == "__main__":
    unittest.main()
