from __future__ import annotations

from pathlib import Path

from proteusgen.pdf_circuit_corpus import (
    DEFAULT_EXPECTED_CIRCUITS,
    PDF_PART_PROJECTIONS,
    parse_pdf_circuit_corpus,
    verify_written_circuit_corpus,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PDF = (
    REPOSITORY_ROOT
    / "proteus"
    / "active"
    / "fixtures"
    / "circuit_specs"
    / "Proteus_200_Circuits_Complete_Pin_Wiring.pdf"
)
CORPUS_ROOT = REPOSITORY_ROOT / "proteus" / "active" / "examples" / "proteus_200_circuits"


def test_pdf_contains_every_canonical_circuit_with_complete_pin_audit() -> None:
    records = parse_pdf_circuit_corpus(SOURCE_PDF)

    assert len(records) == DEFAULT_EXPECTED_CIRCUITS
    assert [record.number for record in records] == list(range(1, 201))
    assert all(record.audit_status == "PASS" for record in records)
    assert all(record.audit_unassigned == 0 for record in records)
    assert all(record.audit_expected == record.pin_count for record in records)


def test_all_pdf_part_labels_have_explicit_placement_projections() -> None:
    records = parse_pdf_circuit_corpus(SOURCE_PDF)

    source_parts = {component.pdf_part for record in records for component in record.components}
    assert source_parts == set(PDF_PART_PROJECTIONS)


def test_written_corpus_matches_the_pinned_pdf_exactly() -> None:
    report = verify_written_circuit_corpus(source_pdf=SOURCE_PDF, output_root=CORPUS_ROOT)

    assert report["valid"] is True
    assert report["circuit_count"] == DEFAULT_EXPECTED_CIRCUITS
    assert len(report["most_complex"]) == 10
