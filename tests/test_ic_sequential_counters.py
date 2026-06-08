from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_ic_sequential_counters_v1_temp.py"
SCRIPT_V2 = ROOT / "tools" / "proteus_generation" / "2026-06-09" / "generate_ic_sequential_counters_v2_temp.py"
SCRIPT_V3 = (
    ROOT
    / "tools"
    / "proteus_generation"
    / "2026-06-09"
    / "generate_ic_sequential_counters_v3_mixed_retry_temp.py"
)
SCRIPT_V4 = (
    ROOT
    / "tools"
    / "proteus_generation"
    / "2026-06-09"
    / "generate_ic_sequential_counters_v4_whole_donor_retry_temp.py"
)
SCRIPT_BATCH3 = (
    ROOT
    / "tools"
    / "proteus_generation"
    / "2026-06-09"
    / "generate_ic_sequential_batch3_solo_temp.py"
)


def load_seq_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v1_temp", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_seq_v2_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v2_temp", SCRIPT_V2)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_seq_v3_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v3_mixed_retry_temp", SCRIPT_V3)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_seq_v4_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_counters_v4_whole_donor_retry_temp", SCRIPT_V4)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_seq_batch3_module():
    spec = importlib.util.spec_from_file_location("ic_sequential_batch3_solo_temp", SCRIPT_BATCH3)
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


def test_counter_v2_expands_counter_families_and_preserves_bidir_policy() -> None:
    seq = load_seq_v2_module()
    expected_counts = {
        "7490": 10,
        "74hc160": 14,
        "74hc161": 14,
        "74hc163": 14,
        "74hc192": 14,
        "74hc193": 14,
        "4017": 14,
        "4020": 14,
        "74hc4024": 9,
    }
    assert {family.key for family in seq.FAMILIES} == set(expected_counts)
    for family in seq.FAMILIES:
        chunk = _extract_object_chunk(read_internal_file(family.donor("single"), "ROOT.DSN"))
        assert chunk.count(b"$TERBIDIR") == expected_counts[family.key]
        assert chunk.count(b"$TERINPUT") == 0
        assert chunk.count(b"$TEROUTPUT") == 0


def test_counter_v2_marks_74hc192_duplicate_pin_as_ambiguous() -> None:
    seq = load_seq_v2_module()
    family = next(item for item in seq.FAMILIES if item.key == "74hc192")
    pin_map = seq.learned_pin_map(family)
    assert pin_map["ambiguous_pin_aliases"]["9"] == ["D3", "UP"]
    assert "9" not in pin_map["pin_aliases"]
    assert pin_map["signal_aliases"]["D3"] == "9"
    assert pin_map["signal_aliases"]["UP"] == "9"


def test_counter_v2_builds_mixed_cdb_for_cross_family_case() -> None:
    seq = load_seq_v2_module()
    families = {family.key: family for family in seq.FAMILIES}
    components = [
        (families["74hc192"], "U1"),
        (families["74hc193"], "U2"),
        (families["4017"], "U3"),
        (families["4020"], "U4"),
    ]
    cdb = seq.build_mixed_cdb(components)
    assert cdb.count(b"74HC192") >= 2
    assert cdb.count(b"74HC193") >= 2
    assert cdb.count(b"4017") >= 2
    assert cdb.count(b"4020") >= 2
    for ref in (b"U1", b"U2", b"U3", b"U4"):
        assert cdb.count(ref) >= 2


def test_counter_v3_mixed_retry_uses_final_donor_slot_for_last_package() -> None:
    seq = load_seq_v3_module()
    assert seq.source_slots_for_component_count(1) == [3]
    assert seq.source_slots_for_component_count(2) == [0, 3]
    assert seq.source_slots_for_component_count(3) == [0, 1, 3]
    assert seq.source_slots_for_component_count(4) == [0, 1, 2, 3]


def test_counter_v3_patch_unit_records_source_slot_in_plan() -> None:
    seq = load_seq_v3_module()
    family = next(item for item in seq.seq.FAMILIES if item.key == "4017")
    unit, plan = seq.patch_unit_final_aware(family, source_slot=3, ref="U1", label_prefix="A")
    assert unit.count(b"$TERBIDIR") == 14
    assert unit.count(b"$TERINPUT") == 0
    assert unit.count(b"$TEROUTPUT") == 0
    assert {item["source_slot"] for item in plan} == {4}


def test_counter_v4_whole_donor_retry_supports_only_whole_donor_counts() -> None:
    seq = load_seq_v4_module()
    assert seq.donor_kind_for_count(1) == "single"
    assert seq.donor_kind_for_count(2) == "two"
    assert seq.donor_kind_for_count(4) == "four"


def test_counter_v4_same_length_device_patch_preserves_terminal_count() -> None:
    seq = load_seq_v4_module()
    family_lookup = {family.key: family for family in seq.seq.FAMILIES}
    base = family_lookup["74hc192"]
    packages = [family_lookup["74hc192"], family_lookup["74hc193"]]
    chunk = _extract_object_chunk(read_internal_file(base.donor("two"), "ROOT.DSN"))
    patched = seq.patch_device_groups(chunk, base, packages)
    assert patched.count(b"$TERBIDIR") == chunk.count(b"$TERBIDIR")
    assert patched.count(b"74HC192") == chunk.count(b"74HC192") // 2
    assert patched.count(b"74HC193") == chunk.count(b"74HC192") // 2


def test_sequential_batch3_donors_preserve_bidir_policy() -> None:
    seq = load_seq_batch3_module()
    expected_counts = {
        "74hc4040": 14,
        "74hc4060": 14,
        "4518": 7,
        "74hc4520": 7,
        "74hc74": 12,
        "74hc76": 14,
        "74hc174": 14,
        "74hc273": 18,
        "4027": 14,
    }
    assert {family.key for family in seq.FAMILIES} == set(expected_counts)
    for family in seq.FAMILIES:
        chunk = _extract_object_chunk(read_internal_file(family.donor("single"), "ROOT.DSN"))
        assert chunk.count(b"$TERBIDIR") == expected_counts[family.key]
        assert chunk.count(b"$TERINPUT") == 0
        assert chunk.count(b"$TEROUTPUT") == 0
        assert chunk.count(family.proteus_device.encode("ascii")) > 0


def test_sequential_batch3_4027_is_two_package_only_for_rlc() -> None:
    seq = load_seq_batch3_module()
    family = next(item for item in seq.FAMILIES if item.key == "4027")
    assert family.four is None
    assert family.rlc_kind == "two"
    assert family.donor("rlc").name == "2_4027withRLC.pdsprj"
