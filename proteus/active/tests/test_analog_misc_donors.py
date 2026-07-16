from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT.parent / "experiments" / "runners" / "2026-06-09" / "generate_analog_misc_batch1_solo_temp.py"


def load_analog_module():
    spec = importlib.util.spec_from_file_location("analog_misc_batch1_solo_temp", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_analog_misc_donors_preserve_bidir_policy() -> None:
    analog = load_analog_module()
    expected_counts = {
        "ne555": 8,
        "npn": 3,
        "pnp": 3,
        "lm741": 7,
        "elec_cap": 2,
    }
    assert {family.key for family in analog.FAMILIES} == set(expected_counts)
    for family in analog.FAMILIES:
        chunk = _extract_object_chunk(read_internal_file(family.donor("single"), "ROOT.DSN"))
        assert chunk.count(b"$TERBIDIR") == expected_counts[family.key]
        assert chunk.count(b"$TERINPUT") == 0
        assert chunk.count(b"$TEROUTPUT") == 0
        assert chunk.count(family.proteus_device.encode("ascii")) > 0


def test_electrolytic_cap_uses_cap_elec_marker_and_blank_donor_labels() -> None:
    analog = load_analog_module()
    family = next(item for item in analog.FAMILIES if item.key == "elec_cap")
    assert family.proteus_device == "CAP-ELEC"
    pin_map = analog.learned_pin_map(family)
    assert [terminal["label"] for terminal in pin_map["terminals"]] == ["", ""]


def test_analog_misc_family_scale_donor_constraints() -> None:
    analog = load_analog_module()
    families = {family.key: family for family in analog.FAMILIES}
    assert families["ne555"].four is None
    assert families["ne555"].rlc_kind == "two"
    assert families["elec_cap"].eight == "8ELEC-CAP.pdsprj"
    assert families["elec_cap"].rlc_kind == "eight"
    assert families["npn"].rlc_kind == "four"
    assert families["pnp"].rlc_kind == "four"
    assert families["lm741"].rlc_kind == "four"
