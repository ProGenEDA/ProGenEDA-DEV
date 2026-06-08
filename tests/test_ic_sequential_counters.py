from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_ic_sequential_counters_v1_temp.py"


def load_seq_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v1_temp", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_counter_donors_use_bidirectional_signal_terminals_only() -> None:
    seq = load_seq_module()
    expected_counts = {"7490": 10, "74hc160": 14, "74hc161": 14, "74hc163": 14}
    for family in seq.FAMILIES:
        chunk = _extract_object_chunk(read_internal_file(family.donor("single"), "ROOT.DSN"))
        assert chunk.count(b"$TERBIDIR") == expected_counts[family.key]
        assert chunk.count(b"$TERINPUT") == 0
        assert chunk.count(b"$TEROUTPUT") == 0
        assert chunk.count(family.proteus_device.encode("ascii")) > 0


def test_counter_pin14_is_not_hidden_supply() -> None:
    seq = load_seq_module()
    maps = {item["family"]: item for item in (seq.learned_pin_map(family) for family in seq.FAMILIES)}
    assert maps["74HC90"]["proteus_device"] == "7490"
    assert maps["74HC90"]["pin_aliases"]["14"] == "CKA"
    assert maps["74HC160"]["pin_aliases"]["14"] == "Q0"
    assert maps["74HC161"]["pin_aliases"]["14"] == "Q0"
    assert maps["74HC163"]["pin_aliases"]["14"] == "Q0"


def test_counter_bidir_label_mutation_preserves_marker_class() -> None:
    seq = load_seq_module()
    family = next(item for item in seq.FAMILIES if item.key == "74hc161")
    chunk = _extract_object_chunk(read_internal_file(family.donor("single"), "ROOT.DSN"))
    replacements, plan = seq.sequential_labels(family, "single")
    mutated, mutations = seq.patch_bidir_labels(chunk, replacements)
    assert len(plan) == 14
    assert len(mutations) == 14
    assert mutated.count(b"$TERBIDIR") == chunk.count(b"$TERBIDIR")
    assert mutated.count(b"$TERINPUT") == 0
    assert mutated.count(b"$TEROUTPUT") == 0
    assert mutated[0] == 0
    assert mutated[-1] == 0xFF
