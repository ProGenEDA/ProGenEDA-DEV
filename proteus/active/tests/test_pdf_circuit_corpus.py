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


def test_executable_projection_carries_canonical_terminal_labels_without_wiring() -> None:
    records = parse_pdf_circuit_corpus(SOURCE_PDF)
    circuit_180 = next(record for record in records if record.number == 180)

    projection = circuit_180.executable_payload()
    labels = projection["terminal_label_projection"]

    assert not ({"connections", "wires", "nets", "netlist"} & set(projection))
    assert labels["node_labels"]["GND"] == "G0"
    assert labels["families"]["OPAMP"][0]["pins"] == {
        "IN+": "VIN",
        "IN-": "G0",
        "OUT": "O1",
    }
    assert {
        (row["source_ref"], row["source_pin"])
        for row in labels["omitted_source_pins"]
    } >= {("U1", "V+"), ("U1", "V-")}


def test_written_corpus_matches_the_pinned_pdf_exactly() -> None:
    report = verify_written_circuit_corpus(source_pdf=SOURCE_PDF, output_root=CORPUS_ROOT)

    assert report["valid"] is True
    assert report["circuit_count"] == DEFAULT_EXPECTED_CIRCUITS
    assert len(report["most_complex"]) == 10
