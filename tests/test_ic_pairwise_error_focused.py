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


def load_fixed_module():
    script = ROOT / "tools" / "proteus_generation" / "2026-06-10" / "generate_ic_pairwise_error_fixed_v2_temp.py"
    spec = importlib.util.spec_from_file_location("ic_pairwise_error_fixed_v2_temp", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_comb_method_module():
    script = ROOT / "tools" / "proteus_generation" / "2026-06-11" / "generate_ic_pairwise_combinational_method_v1_temp.py"
    spec = importlib.util.spec_from_file_location("ic_pairwise_combinational_method_v1_temp", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _parsed_ids_and_refs(project: Path):
    parsed = load_fixed_module().pairwise_v1.split_cdb_generic(read_internal_file(project, "ROOT.CDB"))
    return (
        [ref for ref, _row in parsed.pin_rows],
        [ref for ref, _row in parsed.property_rows],
        [int.from_bytes(row[:4], "little") for _ref, row in parsed.pin_rows],
    )


def test_error_fixed_pack_generates_only_supported_v1_failures(tmp_path: Path) -> None:
    fixed = load_fixed_module()
    selected, deferred = fixed._supported_error_pairs()
    assert len(selected) == 65
    assert len(deferred) == 44
    assert ("duplicate_part_reference", "S01", "S02") in selected
    assert ("no_model_specified", "S01", "S27") in selected
    assert {"failure_class": "duplicate_part_reference", "pair": ["S15", "S21"], "reason": "no accepted combinational side"} in deferred

    fixed.OUT_ROOT = tmp_path
    original_pure = fixed.PAIR_BY_SHORT[("S01", "S02")]
    pure = fixed.write_accepted_pair_case(original_pure, "S01", "S02")
    assert pure["static_validation_issues"] == []
    pure_path = tmp_path / pure["case_id"] / f"{pure['case_id']}.pdsprj"
    refs, props, ids = _parsed_ids_and_refs(pure_path)
    assert refs == ["U1:A", "U2:A"]
    assert props == ["U1", "U2"]
    assert ids == [1, 2]

    original_mixed = fixed.PAIR_BY_SHORT[("S01", "S08")]
    mixed = fixed.write_mixed_case(original_mixed, "S01", "S08")
    assert mixed["static_validation_issues"] == []
    mixed_path = tmp_path / mixed["case_id"] / f"{mixed['case_id']}.pdsprj"
    refs, props, ids = _parsed_ids_and_refs(mixed_path)
    assert refs == ["U1", "U2:A"]
    assert props == ["U1", "U2"]
    assert ids == [1, 2]

    original_7447 = fixed.PAIR_BY_SHORT[("S01", "S27")]
    with_7447 = fixed.write_mixed_case(original_7447, "S01", "S27")
    assert with_7447["static_validation_issues"] == []
    with_7447_path = tmp_path / with_7447["case_id"] / f"{with_7447['case_id']}.pdsprj"
    refs, props, ids = _parsed_ids_and_refs(with_7447_path)
    assert refs == ["U1", "U2:A"]
    assert props == ["U1", "U2"]
    assert ids == [13, 14]


def test_combinational_method_v1_covers_all_pairs_with_a_combinational_side() -> None:
    module = load_comb_method_module()
    cases = module.all_pairs_with_combinational_side()
    assert len(cases) == 210
    assert all(module._comb_count(case.left.short_id, case.right.short_id) for case in cases)
    assert len(module._supported_noncomb_probe_pairs()) == 21


def test_combinational_method_v1_static_clean_representatives(tmp_path: Path) -> None:
    module = load_comb_method_module()
    module.OUT_ROOT = tmp_path
    module.fixed.OUT_ROOT = tmp_path
    by_pair = {
        tuple(sorted((case.left.short_id, case.right.short_id), key=module._source_order)): case
        for case in module.pairwise_v1.CASES
    }

    pure = module.write_combinational_method_case(by_pair[("S01", "S02")])
    assert pure["static_validation_issues"] == []

    mixed = module.write_combinational_method_case(by_pair[("S01", "S32")])
    assert mixed["static_validation_issues"] == []

    collision_probe = module.write_noncomb_probe_case(by_pair[("S08", "S09")])
    assert collision_probe["static_validation_issues"] == []
    collision_path = tmp_path / collision_probe["case_id"] / f"{collision_probe['case_id']}.pdsprj"
    parsed = module.pairwise_v1.split_cdb_generic(read_internal_file(collision_path, "ROOT.CDB"))
    assert [ref for ref, _row in parsed.pin_rows] == ["U1", "U2"]
    assert [int.from_bytes(row[:4], "little") for _ref, row in parsed.pin_rows] == [1, 2]
    assert [int.from_bytes(row[:4], "little") for _ref, row in parsed.property_rows] == [1, 2]
    assert all(item["changed"] for item in collision_probe["cdb_plan"]["right_id_renumber_plan"])

    unique_probe = module.write_noncomb_probe_case(by_pair[("S21", "S22")])
    assert unique_probe["static_validation_issues"] == []
    unique_path = tmp_path / unique_probe["case_id"] / f"{unique_probe['case_id']}.pdsprj"
    parsed = module.pairwise_v1.split_cdb_generic(read_internal_file(unique_path, "ROOT.CDB"))
    assert [int.from_bytes(row[:4], "little") for _ref, row in parsed.pin_rows] == [27, 33]
    assert [int.from_bytes(row[:4], "little") for _ref, row in parsed.property_rows] == [17, 23]
    assert not any(item["changed"] for item in unique_probe["cdb_plan"]["right_id_renumber_plan"])
