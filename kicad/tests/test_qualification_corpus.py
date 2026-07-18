from __future__ import annotations

import json
from pathlib import Path

from kicad.pipeline.input_json_validator_fixer import fix_json_file
from kicad.qualification.corpus import (
    APPLICATION_PROFILES,
    ARCHETYPES,
    build_circuit,
    build_corpus,
)


def test_locked_qualification_dimensions_and_unique_names() -> None:
    assert len(ARCHETYPES) == 40
    assert len(APPLICATION_PROFILES) == 10
    assert len({item.slug for item in ARCHETYPES}) == 40
    assert len({item.slug for item in APPLICATION_PROFILES}) == 10
    assert all(item.blocks for item in ARCHETYPES)


def test_each_archetype_compiles_as_canonical_combination_json() -> None:
    for archetype_index, archetype in enumerate(ARCHETYPES, 1):
        circuit = build_circuit(
            archetype,
            APPLICATION_PROFILES[0],
            archetype_index=archetype_index,
            profile_index=1,
        )
        assert circuit["validation"]["status"] == "pass"
        assert circuit["routing"]["mode"] == "combination"
        assert circuit["components"]
        assert circuit["nets"]
        expected = {
            item["name"]: item["members"]
            for item in circuit["expected_netlist"]["nets"]
        }
        assert expected == circuit["nets"]


def test_build_corpus_emits_400_fixer_accepted_inputs(tmp_path: Path) -> None:
    output = tmp_path / "common_400"
    manifest = build_corpus(output)
    files = sorted((output / "final_json").glob("*.json"))
    assert manifest["circuit_count"] == 400
    assert manifest["electrical_archetype_count"] == 40
    assert manifest["unique_electrical_fingerprint_count"] == 40
    assert manifest["all_canonical_json_valid"]
    assert manifest["all_circuit_ids_unique"]
    assert manifest["all_archetypes_have_ten_profiles"]
    assert manifest["all_profiles_have_forty_archetypes"]
    assert len(files) == 400

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["validation"]["status"] == "pass"
        fixed = tmp_path / "fixed" / path.name
        report = fix_json_file(path, output=fixed, routing_mode="combination")
        assert report["ok"], path.name
        assert fixed.is_file()
