"""Focused tests for the ordinary-executable common-circuit bundle layer."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from ltspice.pipeline.common_circuit_bundle import (
    BUNDLE_SCHEMA,
    CommonCircuitBundleError,
    build_common_circuit_bundle,
    record_installed_netlist_validation,
)
from ltspice.pipeline.common_circuit_corpus import CORPUS_SIZE


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fake_ordinary_native_executor(source: Path, *, output_root: Path, label: str) -> dict:
    """Test double with the ordinary executor's result shape, no ASC hand-edit.

    The bundle code is tested against an injected result producer so unit tests
    do not spend time packaging 100 real executable runs.  Production defaults
    to ``run_donor_native_executable`` and has no injection through its CLI.
    """

    sources = sorted(source.rglob("circuit.json"))
    run_dir = output_root / "fixed_native_run"
    results = []
    for path in sources:
        document = json.loads(path.read_text(encoding="utf-8"))
        circuit_id = document["circuit_id"]
        target = run_dir / "generation" / circuit_id.lower() / "project" / f"{circuit_id.lower()}.asc"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Deliberately deterministic stand-in output: the bundle does not
        # inspect or mutate it, it only receives/copies validated executor ASC.
        target.write_text(f"Version 4\nSHEET 1 880 680\nTEXT 0 0 Left 2 !{circuit_id}\n", encoding="cp1252")
        results.append(
            {
                "ok": True,
                "circuit_id": circuit_id,
                "asc_path": str(target.relative_to(run_dir)),
                "final_validation": {
                    "ok": True,
                    "symbol_count": len(document["components"]) - 1,
                    "wire_count": len(document["nets"]),
                    "ground_flag_count": 1,
                    "directive_count": len(document["spice_directives"]),
                    "terminal_fallback": "forbidden",
                    "custom_symbols": "forbidden",
                },
            }
        )
    return {
        "schema": "fake-ordinary-native/v1",
        "ok": True,
        "run_dir": str(run_dir),
        "input_count": len(results),
        "accepted_count": len(results),
        "rejected_count": 0,
        "results": results,
        "label": label,
    }


class CommonCircuitBundleTests(unittest.TestCase):
    def test_bundle_contains_100_inputs_100_generated_ascs_and_stable_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first_bundle = root / "first"
            second_bundle = root / "second"
            first_zip = root / "first.zip"
            second_zip = root / "second.zip"
            first = build_common_circuit_bundle(
                first_bundle,
                archive_path=first_zip,
                executor=_fake_ordinary_native_executor,
            )
            second = build_common_circuit_bundle(
                second_bundle,
                archive_path=second_zip,
                executor=_fake_ordinary_native_executor,
            )

            self.assertEqual(first["schema"], BUNDLE_SCHEMA)
            self.assertTrue(first["ok"])
            self.assertEqual(first["circuit_count"], CORPUS_SIZE)
            self.assertEqual(first["generated_asc_count"], CORPUS_SIZE)
            self.assertEqual(len(list(first_bundle.rglob("circuit.json"))), CORPUS_SIZE)
            self.assertEqual(len(list(first_bundle.rglob("*.asc"))), CORPUS_SIZE)
            self.assertFalse((first_bundle / ".native_run").exists())
            self.assertTrue((first_bundle / "BUNDLE_MANIFEST.md").is_file())
            checklists = sorted(first_bundle.rglob("accuracy_check.txt"))
            self.assertEqual(len(checklists), CORPUS_SIZE)
            self.assertTrue(all("Deterministic donor-native generation facts:" in item.read_text(encoding="utf-8") for item in checklists))
            self.assertTrue(all("asc_sha256:" in item.read_text(encoding="utf-8") for item in checklists))
            self.assertEqual(first["items"], second["items"])
            self.assertEqual(_sha256(first_zip), _sha256(second_zip))

            with zipfile.ZipFile(first_zip) as archive:
                names = archive.namelist()
            self.assertTrue(all(name.startswith("ltspice_common_circuit_bundle/") for name in names))
            self.assertFalse(any(".native_run" in name for name in names))
            self.assertEqual(sum(name.endswith("/circuit.json") for name in names), CORPUS_SIZE)
            self.assertEqual(sum(name.endswith(".asc") for name in names), CORPUS_SIZE)

            # External LTspice evidence can be recorded after the ordinary
            # generator finishes. It must update every checklist and refresh
            # the portable ZIP without leaking machine-local .net sidecars.
            for asc in first_bundle.rglob("*.asc"):
                asc.with_suffix(".net").write_text(
                    f"* {asc.name}\n* Generated by LTspice 26.0.2 for Windows.\n.end\n",
                    encoding="utf-8",
                )
            netlisting = record_installed_netlist_validation(first_bundle, archive_path=first_zip)
            self.assertTrue(netlisting["ok"])
            self.assertEqual(netlisting["netlisted_count"], CORPUS_SIZE)
            self.assertEqual(netlisting["ltspice_exporter_versions"], ["26.0.2 for Windows."])
            self.assertTrue((first_bundle / "LTSPICE_26_NETLIST_VALIDATION.txt").is_file())
            self.assertTrue(
                all("Installed LTspice netlist validation:" in item.read_text(encoding="utf-8") for item in checklists)
            )
            with zipfile.ZipFile(first_zip) as archive:
                refreshed_names = archive.namelist()
            self.assertIn("ltspice_common_circuit_bundle/LTSPICE_26_NETLIST_VALIDATION.txt", refreshed_names)
            self.assertFalse(any(name.endswith(".net") for name in refreshed_names))

            retained_bundle = root / "retained"
            retained_zip = root / "retained.zip"
            build_common_circuit_bundle(
                retained_bundle,
                archive_path=retained_zip,
                retain_native_work=True,
                executor=_fake_ordinary_native_executor,
            )
            self.assertTrue((retained_bundle / ".native_run").is_dir())
            with zipfile.ZipFile(retained_zip) as archive:
                retained_names = archive.namelist()
            self.assertFalse(any(".native_run" in name for name in retained_names))

    def test_refuses_repository_output_or_archive_overwrite(self) -> None:
        repository_output = Path(__file__).resolve().parents[2] / "generated-common-circuit-bundle-test"
        with self.assertRaisesRegex(CommonCircuitBundleError, "outside repository"):
            build_common_circuit_bundle(repository_output, executor=_fake_ordinary_native_executor)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "existing.zip"
            archive.write_bytes(b"existing")
            with self.assertRaisesRegex(CommonCircuitBundleError, "overwrite"):
                build_common_circuit_bundle(
                    root / "bundle",
                    archive_path=archive,
                    executor=_fake_ordinary_native_executor,
                )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
