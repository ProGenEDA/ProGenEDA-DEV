"""Regression coverage for the named donor-native common-circuit corpus."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from ltspice.pipeline.common_circuit_corpus import (
    CORPUS_SIZE,
    build_common_circuit_corpus,
    top_complex_circuits,
    validate_common_circuit_corpus,
    write_common_circuit_corpus,
)
from ltspice.pipeline.input_adapter import canonicalize_source


class CommonCircuitCorpusTests(unittest.TestCase):
    def test_all_named_documents_are_canonical_and_component_bounded(self) -> None:
        corpus = build_common_circuit_corpus()
        self.assertEqual(len(corpus), CORPUS_SIZE)
        titles = set()
        for circuit in corpus.values():
            metadata = circuit["common_circuit_corpus"]
            self.assertTrue(circuit["project"]["name"])
            self.assertTrue(metadata["title"])
            self.assertTrue(metadata["description"])
            self.assertTrue(metadata["expected_behavior"])
            self.assertTrue(circuit["spice_directives"])
            self.assertLessEqual(len(circuit["components"]), 43)
            self.assertNotIn("ltspice_at", json.dumps(circuit))
            self.assertEqual(
                {name: set(members) for name, members in circuit["nets"].items()},
                {item["name"]: set(item["members"]) for item in circuit["expected_netlist"]["nets"]},
            )
            titles.add(metadata["title"])
        self.assertEqual(len(titles), CORPUS_SIZE)

    def test_active_adapter_placer_and_direct_wire_router_accept_every_document(self) -> None:
        report = validate_common_circuit_corpus(route=True)
        self.assertTrue(report["ok"], report["failures"])
        self.assertEqual(report["shared_canonicalized"], CORPUS_SIZE)
        self.assertEqual(report["adapter_validated"], CORPUS_SIZE)
        self.assertEqual(report["routed"], CORPUS_SIZE)
        self.assertEqual(len(report["top_10_complex"]), 10)
        self.assertEqual(top_complex_circuits()[0]["title"], "Passive RLC Test Bench Network")

    def test_folder_writer_emits_exactly_one_json_per_named_circuit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "common"
            paths = write_common_circuit_corpus(output)
            self.assertEqual(len(paths), CORPUS_SIZE)
            self.assertEqual(len(list(output.rglob("*.json"))), CORPUS_SIZE)
            self.assertTrue((output / "CORPUS_INDEX.md").is_file())
            for path in paths:
                self.assertEqual(path.name, "circuit.json")
                self.assertTrue((path.parent / "accuracy_check.txt").is_file())
                self.assertTrue(json.loads(path.read_text(encoding="utf-8"))["expected_netlist"])
            with self.assertRaisesRegex(ValueError, "must be empty"):
                write_common_circuit_corpus(output)

    def test_shared_analysis_and_native_directive_aliases_emit_each_card_once(self) -> None:
        """Corpus compatibility aliases must not create duplicate visible directives."""

        circuit = next(iter(build_common_circuit_corpus().values()))
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "common.json"
            source.write_text(json.dumps(circuit), encoding="utf-8")
            canonical, report, _original = canonicalize_source(source, routing_mode="wire")
        self.assertEqual(canonical["spice_directives"], circuit["project"]["analysis"])
        self.assertEqual(
            report["analysis_directives"]["exact_duplicate_cards_removed"],
            circuit["project"]["analysis"],
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
