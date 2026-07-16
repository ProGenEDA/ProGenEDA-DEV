import unittest

from proteusgen.templates import FixtureRegistry


class FixtureTests(unittest.TestCase):
    def test_clean_fixture_manifest_hashes_are_valid(self) -> None:
        registry = FixtureRegistry.load()
        self.assertEqual(registry.verify_all(), [])
        self.assertEqual(registry.get("e001_empty").recipe, "empty_single_sheet")
        self.assertEqual(registry.get("hc08_d02_four_gates_unwired").role, "diagnostic_template")

    def test_d05_is_explicitly_pending(self) -> None:
        registry = FixtureRegistry.load()
        self.assertTrue(any(item["id"] == "hc08_d05_exact_picture_oracle" for item in registry.pending))


if __name__ == "__main__":
    unittest.main()
