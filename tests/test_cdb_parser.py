from __future__ import annotations

from pathlib import Path

from proteusgen.cdb import build_cdb_from_rows, parse_cdb
from proteusgen.pdsprj import read_internal_file


ROOT = Path(__file__).resolve().parents[1]


def roundtrip(path: Path) -> None:
    data = read_internal_file(path, "ROOT.CDB")
    parsed = parse_cdb(data)
    rebuilt = build_cdb_from_rows(
        parsed,
        (
            (pin.ref, pin, prop)
            for pin, prop in zip(parsed.pin_rows, parsed.property_rows)
        ),
    )
    assert rebuilt == data


def test_cdb_parser_roundtrips_counter_donors() -> None:
    for name in [
        "74HC160.pdsprj",
        "2_74HC160.pdsprj",
        "4_74HC160.pdsprj",
        "74HC192.pdsprj",
        "4_74HC193.pdsprj",
        "4_4017withRLC.pdsprj",
    ]:
        roundtrip(ROOT / "proteus_ic" / "donors" / "sequential_counters" / name)


def test_cdb_parser_roundtrips_mixed_ic_donors() -> None:
    for name in [
        "MIX_MISC_157_283_165_595_85_RCL_ANALOG.pdsprj",
        "MIX_SEQ_COUNTERS_ALL_RCL_ANALOG.pdsprj",
        "MIX_SEQ_4017_4020_4024.pdsprj",
    ]:
        roundtrip(ROOT / "proteus_ic" / "donors" / "mixed_ic_analog_batch1" / name)


def test_cdb_parser_preserves_real_row_boundaries() -> None:
    data = read_internal_file(
        ROOT / "proteus_ic" / "donors" / "sequential_counters" / "2_74HC160.pdsprj",
        "ROOT.CDB",
    )
    parsed = parse_cdb(data)
    assert parsed.count == 2
    assert [row.ref for row in parsed.pin_rows] == ["U1", "U2"]
    assert [row.ref for row in parsed.property_rows] == ["U1", "U2"]
    assert parsed.pin_rows[0].data[:4] == (1).to_bytes(4, "little")
    assert parsed.pin_rows[1].data[:4] == (2).to_bytes(4, "little")
    assert parsed.property_rows[0].data[:4] == (1).to_bytes(4, "little")
    assert parsed.property_rows[1].data[:4] == (2).to_bytes(4, "little")
