import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from proteusgen.templates import FixtureRegistry, repository_root


class TemplateLocationTests(unittest.TestCase):
    def test_explicit_repo_root_environment_is_supported(self) -> None:
        expected = repository_root()
        with patch.dict(os.environ, {"PROTEUSGEN_REPO_ROOT": str(expected)}):
            self.assertEqual(repository_root(), expected)
            self.assertEqual(FixtureRegistry.load().verify_all(), [])

    def test_invalid_repo_root_environment_fails_clearly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"PROTEUSGEN_REPO_ROOT": directory}):
                with self.assertRaises(FileNotFoundError):
                    FixtureRegistry.load()


if __name__ == "__main__":
    unittest.main()
