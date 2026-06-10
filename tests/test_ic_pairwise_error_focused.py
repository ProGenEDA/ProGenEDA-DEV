from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from proteusgen.cdb import parse_cdb
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]


def load_focused_module():
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_ic_pairwise_error_focused_v1_temp.py"
    spec = importlib.util.spec_from_file_location("ic_pairwise_error_focused_v1_temp", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_focused_s01_s02_uses_accepted_combinational_path(tmp_path: Path) -> None:
    focused = load_focused_module()
    assert focused.CASES[0].case_id == "T01_S01_S02_ACCEPTED_COMBINATIONAL"
    assert ("S01", "S02") in focused.FAILED_PAIRS_FROM_V1_USER_NOTES["duplicate_part_reference"]

    out_root = tmp_path / "focused"
    out_root.mkdir()
    manifest = focused.ic.write_case(focused.CASES[0], out_root=out_root)
    output = out_root / focused.CASES[0].case_id / f"{focused.CASES[0].case_id}.pdsprj"
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = read_internal_file(output, "ROOT.CDB")
    parsed = parse_cdb(cdb)

    assert manifest["static_validation_issues"] == []
    assert chunk.count(b"COMPONENT ID") == 2
    assert chunk.count(b"$TERINPUT") == 4
    assert chunk.count(b"$TEROUTPUT") == 2
    assert chunk.count(b"74HC00") == 3
    assert chunk.count(b"74HC02") == 3
    assert [row.ref for row in parsed.pin_rows] == ["U1:A", "U2:A"]
    assert [row.ref for row in parsed.property_rows] == ["U1", "U2"]
    assert cdb.count(b"74NAND2") == 1
    assert cdb.count(b"74NOR2") == 1
