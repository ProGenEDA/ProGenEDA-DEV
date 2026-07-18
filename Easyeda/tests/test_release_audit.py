from pathlib import Path

from Easyeda.release_audit import audit_corpus


CORPUS = (
    Path(__file__).parents[1]
    / "qualification"
    / "corpora"
    / "2026_07_17_full_pin_300_v1"
)


def test_locked_300_circuit_corpus_passes_shipping_audit() -> None:
    report = audit_corpus(CORPUS)
    assert report["passed"] is True, report["errors"]
    assert report["circuit_count"] == 300
    assert report["archetype_count"] == 30
    assert report["variant_profile_count"] == 10
    assert report["unique_project_name_count"] == 300
    assert report["unique_title_count"] == 300
    assert report["covered_kind_count"] == 59
