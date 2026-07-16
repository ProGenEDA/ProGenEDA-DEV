from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from proteusgen.ic_native import (
    NativeRegistry,
    analyze_donor,
    bidir_events,
    generate_ic_native_project_from_payload,
    patch_bidir_suffixes,
)
from proteusgen.pdsprj import read_internal_file
from proteusgen.resistor_v9 import _extract_object_chunk


ROOT = Path(__file__).resolve().parents[1]


def load_native_bider_v2_module():
    script = ROOT / "tools" / "proteus_generation" / "2026-06-12" / "generate_ic_native_bider_pairs_v2_cdb_idfix_temp.py"
    spec = importlib.util.spec_from_file_location("ic_native_bider_pairs_v2_for_tests", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_7490_real_circuits_module():
    script = ROOT / "tools" / "proteus_generation" / "2026-06-12" / "generate_ic_7490_real_circuits_v1_temp.py"
    spec = importlib.util.spec_from_file_location("ic_7490_real_circuits_v1_for_tests", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_7490_full_integration_module():
    script = ROOT / "tools" / "proteus_generation" / "2026-06-12" / "generate_ic_7490_full_integration_v1_temp.py"
    spec = importlib.util.spec_from_file_location("ic_7490_full_integration_v1_for_tests", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_native_registry_paths_exist() -> None:
    registry = NativeRegistry.load()
    missing = [
        f"{component.key}:{kind}:{path}"
        for component in registry.components.values()
        for kind, path in component.donors.items()
        if not path.exists()
    ]
    assert not missing
    assert registry.normalize("74HC90") == "7490"
    assert registry.normalize("7segcomanode") == "7SEG_COM_ANODE"
    assert registry.normalize("7447") == "74HC47"


def test_generate_single_native_counter_with_bidir_labels(tmp_path: Path) -> None:
    result = generate_ic_native_project_from_payload(
        {
            "schema": "ic-native-circuit-ir/v0.1",
            "case_id": "native_single_74hc160",
            "components": [
                {
                    "ref": "U1",
                    "part": "74HC160",
                    "connections": {"CLK": "CLK0", "MR": "RST0"},
                }
            ],
        },
        tmp_path,
    )
    assert result.manifest["static_validation_issues"] == []
    chunk = _extract_object_chunk(read_internal_file(result.output_path, "ROOT.DSN"))
    assert b"74HC160" in chunk
    assert b"$TERBIDIR" in chunk
    assert b"$TERINPUT" not in chunk
    assert b"$TEROUTPUT" not in chunk
    assert b"CLK0" in chunk
    assert b"RST0" in chunk


def test_generate_7seg_common_anode_from_bider_donor(tmp_path: Path) -> None:
    result = generate_ic_native_project_from_payload(
        {
            "schema": "ic-native-circuit-ir/v0.1",
            "case_id": "native_7seg_common_anode",
            "components": [{"ref": "D1", "part": "7segcomanode"}],
        },
        tmp_path,
    )
    assert result.manifest["static_validation_issues"] == []
    chunk = _extract_object_chunk(read_internal_file(result.output_path, "ROOT.DSN"))
    assert b"7SEG-COM-AN-BLUE" in chunk
    assert len(bidir_events(chunk)) == 8


def test_exact_rezip_7447_plus_7seg_control(tmp_path: Path) -> None:
    result = generate_ic_native_project_from_payload(
        {
            "schema": "ic-native-circuit-ir/v0.1",
            "case_id": "native_7447_7seg_exact",
            "donor": "squence/4_7segcomanodewithbiderand4_7447.pdsprj",
            "exact_rezip": True,
        },
        tmp_path,
    )
    assert result.manifest["static_validation_issues"] == []
    chunk = _extract_object_chunk(read_internal_file(result.output_path, "ROOT.DSN"))
    assert b"7447" in chunk
    assert b"7SEG-COM-AN-BLUE" in chunk


def test_generate_manual_pair_donor(tmp_path: Path) -> None:
    result = generate_ic_native_project_from_payload(
        {
            "schema": "ic-native-circuit-ir/v0.1",
            "case_id": "native_pair_7490_4017",
            "components": [
                {"ref": "U1", "part": "74HC90"},
                {"ref": "U2", "part": "4017"},
            ],
        },
        tmp_path,
    )
    assert result.manifest["static_validation_issues"] == []
    chunk = _extract_object_chunk(read_internal_file(result.output_path, "ROOT.DSN"))
    assert b"7490" in chunk
    assert b"4017" in chunk


def test_analyze_donor_reports_native_terminal_inventory() -> None:
    registry = NativeRegistry.load()
    donor = registry.component("7SEG_COM_ANODE").donors["single"]
    report = analyze_donor(donor)
    assert report["hashes"]["ROOT.DSN"]
    assert report["marker_counts"]["7SEG-COM-AN-BLUE"] >= 1
    assert len(report["bidir_terminals"]) == 8


def test_native_bider_v2_renumbers_duplicate_cdb_ids(tmp_path: Path) -> None:
    module = load_native_bider_v2_module()
    module.OUT_ROOT = tmp_path
    manifest = module.build_case(
        "M000_TIMING_CHAIN_NE555_7490_4017_4020",
        ("NE555", "7490", "4017", "4020"),
        "Timing chain regression for duplicate native donor CDB IDs.",
        "test",
        0,
    )

    assert manifest["static_validation_issues"] == []
    id_plan = manifest["cdb_plan"]["cdb_id_plan"]
    assert id_plan["mode"] == "renumbered_duplicate_cdb_ids"
    assert id_plan["duplicates_before"] == {"pin_primary": [1], "pin_secondary": [1], "property": [1]}

    output = tmp_path / "M000_TIMING_CHAIN_NE555_7490_4017_4020" / "M000_TIMING_CHAIN_NE555_7490_4017_4020.pdsprj"
    parsed = module.pairwise.split_cdb_generic(read_internal_file(output, "ROOT.CDB"))
    assert [int.from_bytes(row[:4], "little") for _ref, row in parsed.pin_rows] == [1, 2, 3, 4]
    assert [int.from_bytes(row[12:16], "little") for _ref, row in parsed.pin_rows] == [1, 2, 3, 4]
    assert [int.from_bytes(row[:4], "little") for _ref, row, _is_last in parsed.property_rows] == [1, 2, 3, 4]


def test_7490_real_circuits_use_compact_same_name_layout() -> None:
    module = load_7490_real_circuits_module()
    case = next(item for item in module.CASES if item["case_id"] == "T03_FOUR_DECADE_RIPPLE_CHAIN")
    assert case["donor"] == module.DONOR
    assert len(case["components"]) == 4
    labels = [
        label
        for component in case["components"]
        for label in component["connections"].values()
    ]
    assert max(len(label) for label in labels) <= 4
    assert labels.count("G0") >= 8
    assert "C1D" in labels and "C2D" in labels and "C3D" in labels and "AOUT" in labels


def test_7490_full_integration_pack_is_not_toy_loads() -> None:
    module = load_7490_full_integration_module()
    families = {gate.family for case in module.CASES for gate in case.gates}
    assert families == {"74hc00", "74hc02", "74hc04", "74hc08", "74hc32", "74hc86", "74hc266"}
    assert min(len(case.passives) for case in module.CASES) >= 8
    assert max(len(case.passives) for case in module.CASES) >= 11
    for case in module.CASES:
        kinds = {passive.kind for passive in case.passives}
        assert kinds == {"R", "C", "L"}
        assert len(case.counters) == 4
        assert len(case.gates) == 5


def test_native_composed_clone_route_supports_7490_logic_and_rcl(tmp_path: Path) -> None:
    donor = ROOT / "evidence" / "donors" / "manual_downloads_20260612" / "ICcombinationfinal" / "7490" / "7490.pdsprj"
    result = generate_ic_native_project_from_payload(
        {
            "schema": "ic-native-circuit-ir/v0.1",
            "case_id": "native_composed_7490_regression",
            "compose": True,
            "clone_from_donor": str(donor.relative_to(ROOT)),
            "components": [
                {
                    "ref": "A1",
                    "part": "74HC90",
                    "connections": {
                        "CKA": "S0",
                        "CKB": "S1",
                        "R01": "H0",
                        "R02": "H0",
                        "R91": "L0",
                        "R92": "L0",
                        "Q0": "A0",
                        "Q1": "A2",
                        "Q2": "A3",
                        "Q3": "A4",
                    },
                },
                {
                    "ref": "A2",
                    "part": "74HC90",
                    "connections": {
                        "CKA": "D0",
                        "CKB": "D1",
                        "R01": "H1",
                        "R02": "H1",
                        "R91": "L1",
                        "R92": "L1",
                        "Q0": "B0",
                        "Q1": "B1",
                        "Q2": "B2",
                        "Q3": "B3",
                    },
                },
                {
                    "ref": "A3",
                    "part": "74HC90",
                    "connections": {
                        "CKA": "D2",
                        "CKB": "D3",
                        "R01": "H2",
                        "R02": "H2",
                        "R91": "L2",
                        "R92": "L2",
                        "Q0": "C0",
                        "Q1": "C1",
                        "Q2": "C2",
                        "Q3": "C3",
                    },
                },
            ],
            "logic_gates": [
                {"family": "74hc08", "gate": "A", "left": "A0", "right": "A2", "output": "D0"},
                {"family": "74hc08", "gate": "B", "left": "A3", "right": "A4", "output": "D1"},
                {"family": "74hc08", "gate": "C", "left": "B0", "right": "B1", "output": "D2"},
                {"family": "74hc08", "gate": "D", "left": "B2", "right": "B3", "output": "D3"},
            ],
            "passives": [
                {"ref": "R1", "kind": "R", "value": "10k", "left": "V0", "right": "H0"},
                {"ref": "R2", "kind": "R", "value": "10k", "left": "V0", "right": "H1"},
                {"ref": "R3", "kind": "R", "value": "10k", "left": "V0", "right": "H2"},
                {"ref": "C1", "kind": "C", "value": "1uF", "left": "L0", "right": "G0"},
                {"ref": "L1", "kind": "L", "value": "5mH", "left": "L1", "right": "G0"},
                {"ref": "C2", "kind": "C", "value": "1uF", "left": "L2", "right": "G0"},
            ],
        },
        tmp_path,
    )

    assert result.manifest["static_validation_issues"] == []
    assert result.manifest["method"] == "native_single_packet_clone_composition_with_optional_locked_logic_and_rcl"
    assert len(result.manifest["components"]) == 3
    assert len(result.manifest["generated_plan"]["gates"]) == 4
    assert len(result.manifest["generated_plan"]["passives"]) == 6
    assert result.manifest["cdb_plan"]["cdb_id_plan"]["duplicates_after"] == {
        "pin_primary_ids": [],
        "pin_secondary_ids": [],
        "property_ids": [],
    }
    chunk = _extract_object_chunk(read_internal_file(result.output_path, "ROOT.DSN"))
    assert chunk.count(b"7490") >= 3
    assert chunk.count(b"74AND2") == 4
    assert chunk.count(b"$TERINPUT") == 8
    assert chunk.count(b"$TEROUTPUT") == 4


def test_native_bidir_suffix_patch_updates_body_association_tokens() -> None:
    donor = ROOT / "evidence" / "donors" / "manual_downloads_20260612" / "ICcombinationfinal" / "7490" / "7490.pdsprj"
    chunk = _extract_object_chunk(read_internal_file(donor, "ROOT.DSN"))
    original_events = bidir_events(chunk)

    patched, plan = patch_bidir_suffixes(chunk, 0x5100)
    patched_events = bidir_events(patched)

    assert len(patched_events) == len(original_events)
    assert len(plan) == len(original_events)
    for original, updated, entry in zip(original_events, patched_events, plan):
        old_token = int(original.suffix, 16).to_bytes(2, "little") + bytes([original.active_link, 0])
        new_token = int(updated.suffix, 16).to_bytes(2, "little") + bytes([updated.active_link, 0])
        assert old_token not in patched
        assert patched.count(new_token) == chunk.count(old_token)
        assert entry["patched_link_token_occurrences"] >= 2
