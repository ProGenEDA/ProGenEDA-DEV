import tempfile
import unittest
from pathlib import Path

from proteusgen.circuit_ir import load_json, parse_circuit_ir
from proteusgen.comparison import compare_projects
from proteusgen.generator import GenerationBlocked, generate_project
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import repository_root
from proteusgen.versioning import read_root_dsn_version


def ir_for(name: str):
    ir, issues = parse_circuit_ir(load_json(repository_root() / "examples" / name))
    assert not issues
    assert ir is not None
    return ir


class GeneratorTests(unittest.TestCase):
    def test_known_passive_recipe_generates_deterministic_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            first = path / "first.pdsprj"
            second = path / "second.pdsprj"
            first_result = generate_project(ir_for("single_resistor_vcc_gnd.json"), first)
            generate_project(ir_for("single_resistor_vcc_gnd.json"), second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertTrue(first_result.result_template_path.exists())
            self.assertEqual(read_root_dsn_version(read_internal_file(first, "ROOT.DSN")), (813, 830))

    def test_hc08_d02_control_generates_without_composition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "d02_control.pdsprj"
            result = generate_project(ir_for("hc08_d02_diagnostic_control.json"), output)
            self.assertEqual(result.fixture_id, "hc08_d02_four_gates_unwired")
            self.assertIn(b"74HC08", read_internal_file(output, "ROOT.DSN"))

    def test_and_reference_is_blocked_pending_d05(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "and.pdsprj"
            result = generate_project(ir_for("and_reference_pending_d05.json"), output)
            self.assertEqual(result.fixture_id, "e001_empty")
            self.assertEqual(result.recipe, "experimental_and_reference_from_fresh_e001_base")
            self.assertTrue(output.exists())
            self.assertIn(b"74HC08", read_internal_file(output, "ROOT.DSN"))
            self.assertFalse(compare_projects(output, repository_root() / "fixtures" / "pdsprj" / "e001_empty_project.pdsprj")["semantic_equal"])

    def test_semantic_comparison_ignores_known_save_noise(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            original = path / "original.pdsprj"
            altered = path / "altered.pdsprj"
            generate_project(ir_for("empty_project.json"), original)
            dsn = bytearray(read_internal_file(original, "ROOT.DSN"))
            dsn[177:179] = b"\xAB\xCD"
            xml = read_internal_file(original, "PROJECT.XML").replace(
                b'MODIFIED="1779447143"', b'MODIFIED="1779447999"'
            )
            write_project_from_parts(original, altered, {"ROOT.DSN": bytes(dsn), "PROJECT.XML": xml})
            report = compare_projects(original, altered)
            self.assertTrue(report["semantic_equal"])


if __name__ == "__main__":
    unittest.main()
