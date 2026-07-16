"""Regenerate the requested five mixed DC-source circuits with stricter CDB rules.

V1 failed in Proteus with ISIS.dll on every requested mixed-source circuit.
Byte comparison against user-made 2x/4x DC source donors showed a concrete
V1 violation: source entries in ROOT.CDB must use source pin names ``+`` and
``-``. V1 wrote passive-style pin names ``1`` and ``2`` for source rows.

This V2 keeps the V1 object-stream method unchanged and changes only the
source CDB pin map, so user testing can isolate whether the CDB source-row
shape was the fatal error.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402

V1_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-04" / "generate_dc_mixed_sources_v1_requested5_temp.py"


def _load_v1() -> Any:
    spec = importlib.util.spec_from_file_location("dc_mixed_sources_v1_for_v2", V1_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V1 helper module from {V1_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_v1()

v1.OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v2_strict_cdb_temp_2026_06_04"
v1.ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V2_STRICT_CDB_TEMP_2026_06_04"
v1.DONOR_ROOT = v1.OUT_ROOT / "donors"
v1.TEST_BATCH = v1.OUT_ROOT / "DC_MIXED_SOURCES_V2_STRICT_CDB_TEST_BATCH"
_ORIGINAL_CASE_DEFINITIONS = v1._case_definitions


def _source_pin_map() -> bytes:
    return v1._enc_str("+") + v1._enc_str("1") + v1._enc_str("-") + v1._enc_str("2")


def _passive_pin_map(kind: str) -> bytes:
    if kind == "CAPACITOR":
        return v1._enc_str("2") + v1._enc_str("2") + v1._enc_str("1") + v1._enc_str("1")
    return v1._enc_str("1") + b"\x00" + v1._enc_str("2") + b"\x00"


def _build_cdb_strict_source_pins(rcl_specs: list[Any], sources: list[Any], first_source_id: int) -> bytes:
    source_rows = [
        {
            "idx": first_source_id + index,
            "ref": source.ref,
            "value": source.cdb_value,
            "model": source.model,
            "prop_text": source.prop_text,
        }
        for index, source in enumerate(sources)
    ]
    ordered: list[Any] = [*source_rows, *rcl_specs]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + v1._enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + v1._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + v1._enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        if isinstance(spec, dict):
            idx = spec["idx"]
            ref = spec["ref"]
            pin_map = _source_pin_map()
        else:
            idx = spec.idx
            ref = spec.ref
            pin_map = _passive_pin_map(spec.kind)
        out += rv9._u32(idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(idx) + v1._enc_str(ref)
        out += rv9._u32(2) + pin_map
        out += rv9._u32(0) + rv9._u32(idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + v1._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        if isinstance(spec, dict):
            out += rv9._u32(spec["idx"]) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += (
                v1._enc_str(spec["ref"])
                + v1._enc_str(spec["value"])
                + v1._enc_str(spec["model"])
                + v1._enc_str("")
                + v1._enc_text(spec["prop_text"])
            )
        elif spec.kind == "CAPACITOR":
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("CAP") + v1._enc_str("CAP10") + v1._enc_text(v1.v5.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("REALIND") + v1._enc_str("") + v1._enc_text(v1.v5.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += v1._enc_str(spec.ref) + v1._enc_str(spec.value) + v1._enc_str("RESISTOR") + v1._enc_str("") + v1._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _case_definitions_v2() -> list[Any]:
    cases = []
    for case in _ORIGINAL_CASE_DEFINITIONS():
        cases.append(replace(case, case_id=case.case_id.replace("DCMS_V1", "DCMS_V2")))
    return cases


v1._build_cdb = _build_cdb_strict_source_pins
v1._case_definitions = _case_definitions_v2


def main() -> int:
    if v1.OUT_ROOT.exists():
        shutil.rmtree(v1.OUT_ROOT)
    v1.TEST_BATCH.mkdir(parents=True)
    donors = v1._copy_donors()

    registry = v1.FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v1.v5.rcl._load_rcl_unit_templates(rcl_donor)

    dci_devices = v1.v5._device_section_from_dsn(v1.read_internal_file(donors["dci_manual_testing"], "ROOT.DSN"))
    dcv_devices = v1.v5._device_section_from_dsn(v1.read_internal_file(donors["dc_voltage_01_default_10v"], "ROOT.DSN"))
    combined_devices = v1._combine_device_sections(dci_devices, dcv_devices)

    cases = [
        v1._make_case(
            item,
            templates=templates,
            base_project=base_project,
            donor_project=donors["dci_manual_testing"],
            source_donor_4x=donors["4x_dc_voltage_10v"],
            devices=combined_devices,
        )
        for item in _case_definitions_v2()
    ]
    for item in cases:
        item["status"] = "temporary_dc_mixed_sources_v2_strict_cdb_not_locked"
        item["strict_cdb_rule"] = "source rows use +/- pin names mapped to pins 1/2"
        manifest_path = v1.TEST_BATCH / item["case_id"] / "manifest.json"
        if manifest_path.exists():
            manifest_path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V2_STRICT_CDB_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V1 user feedback: all five requested mixed-source circuits gave ISIS.dll.",
        "method": (
            "Same object-stream method as V1, but source ROOT.CDB rows now use donor-style +/- "
            "pin names mapped to package pins 1/2 instead of passive-style 1/2 names."
        ),
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "source_count": item["source_count"],
                "rcl_component_count": item["rcl_component_count"],
                "marker_counts": item["marker_counts"],
                "device_marker_counts": item["device_marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
                "strict_cdb_rule": item["strict_cdb_rule"],
            }
            for item in cases
        ],
    }
    (v1.TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (v1.TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V2_STRICT_CDB_TEMP_2026_06_04\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nExpected: all five open and netlist. This V2 changes only source ROOT.CDB pin maps relative to V1.\n",
        encoding="utf-8",
    )
    archive = shutil.make_archive(str(v1.ARCHIVE_BASE), "zip", v1.OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": v1._sha256_file(Path(archive)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
