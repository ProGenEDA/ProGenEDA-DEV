"""Generate source-driven single-family and two-family passive probes.

This temp batch answers whether source-driven output is limited to full R/C/L
loads. It deliberately uses archived accepted donors instead of live Downloads
paths, and emits focused cases for:

* single passive family: R, C, L
* two passive families: R+C, R+L, C+L
* source families: DC voltage, DC current, AC voltage

Do not lock this support surface until the user confirms Proteus open/netlist
results for these generated projects.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen.mixed_rcl import BASE_PROJECT, GENERATOR_TARGET, SCHEMA_VERSION  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

DCV_V15_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_voltage_v15_15_rcl_topologies_temp.py"
DCI_V13_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-04" / "generate_dc_current_v13_15_topologies_temp.py"
ACV_V2_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-04" / "generate_ac_voltage_v2_nonfinal_source_unit_temp.py"

OUT_ROOT = REPO_ROOT / "experiments" / "source_passive_v1_single_two_family_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "SOURCE_PASSIVE_V1_SINGLE_TWO_FAMILY_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V1_SINGLE_TWO_FAMILY_TEST_BATCH"

ARCHIVED_DONORS = {
    "dcv_manual_combined_testing": REPO_ROOT
    / "experiments"
    / "dc_voltage_v15_15_rcl_topologies_temp_2026_06_05"
    / "donors"
    / "manual_combined_testing.pdsprj",
    "dcv_source_10v": REPO_ROOT
    / "experiments"
    / "dc_voltage_v15_15_rcl_topologies_temp_2026_06_05"
    / "donors"
    / "dc_voltage_01_default_10v.pdsprj",
    "dci_manual_testing": REPO_ROOT
    / "experiments"
    / "dc_current_v13_15_topologies_temp_2026_06_04"
    / "donors"
    / "manual_testing.pdsprj",
    "dci_dcv_source_10v": REPO_ROOT
    / "experiments"
    / "dc_current_v13_15_topologies_temp_2026_06_04"
    / "donors"
    / "dc_voltage_01_default_10v.pdsprj",
    "acv_variant_source": REPO_ROOT
    / "experiments"
    / "ac_voltage_v2_nonfinal_source_unit_temp_2026_06_04"
    / "donors"
    / "ac_voltage_02_variant.pdsprj",
    "acv_two_source": REPO_ROOT
    / "experiments"
    / "ac_voltage_v2_nonfinal_source_unit_temp_2026_06_04"
    / "donors"
    / "2xac_voltage_02_variant.pdsprj",
    "acv_source_load": REPO_ROOT
    / "experiments"
    / "ac_voltage_v2_nonfinal_source_unit_temp_2026_06_04"
    / "donors"
    / "ac_voltage_03_resistor_load.pdsprj",
}


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


dcv15 = _load_module("dcv15_for_source_passive_v1", DCV_V15_PATH)
dci13 = _load_module("dci13_for_source_passive_v1", DCI_V13_PATH)
acv2 = _load_module("acv2_for_source_passive_v1", ACV_V2_PATH)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _group(mode: str, start: str = "V0", end: str = "G0") -> dict[str, str]:
    return {"mode": mode, "start": start, "end": end}


def _payload(name: str, description: str, mode: str, family_combo: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_target": GENERATOR_TARGET,
        "project": {
            "name": name,
            "output_basename": name,
            "base": BASE_PROJECT,
            "units": "proteus_internal",
        },
        "nodes": [{"id": "V0", "kind": "power"}, {"id": "G0", "kind": "ground"}],
        "groups": [_group(mode)],
        "metadata": {
            "source": "source-passive single/two-family probe",
            "description": description,
            "family_combo": family_combo,
            "mode": mode,
        },
    }


def passive_probe_payloads() -> list[dict[str, Any]]:
    return [
        _payload("SOURCE_PASSIVE_V1_T01_R_ONLY", "R-only load: one resistor path from source positive to source negative.", "R", "R"),
        _payload("SOURCE_PASSIVE_V1_T02_C_ONLY", "C-only load: one capacitor path from source positive to source negative.", "C", "C"),
        _payload("SOURCE_PASSIVE_V1_T03_L_ONLY", "L-only load: one inductor path from source positive to source negative.", "L", "L"),
        _payload("SOURCE_PASSIVE_V1_T04_RC_ONLY", "R+C load: one accepted RC subgroup path from source positive to source negative.", "RC", "R+C"),
        _payload("SOURCE_PASSIVE_V1_T05_RL_ONLY", "R+L load: one accepted RL subgroup path from source positive to source negative.", "RL", "R+L"),
        _payload("SOURCE_PASSIVE_V1_T06_CL_ONLY", "C+L load: one accepted LC subgroup path from source positive to source negative.", "LC", "C+L"),
    ]


def _set_module_paths() -> None:
    for module in (dcv15, dcv15.v8, dci13, acv2, acv2.v1):
        if hasattr(module, "OUT_ROOT"):
            module.OUT_ROOT = OUT_ROOT
        if hasattr(module, "ARCHIVE_BASE"):
            module.ARCHIVE_BASE = ARCHIVE_BASE
        if hasattr(module, "DONOR_ROOT"):
            module.DONOR_ROOT = DONOR_ROOT
        if hasattr(module, "TEST_BATCH"):
            module.TEST_BATCH = TEST_BATCH


def _copy_archived_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for name, source in ARCHIVED_DONORS.items():
        if not source.exists():
            raise FileNotFoundError(source)
        target = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(source, target)
        copied[name] = target
    return copied


def _suffix(payload: dict[str, Any]) -> str:
    return "_".join(payload["project"]["name"].split("_")[4:])


def _make_dcv_case(
    *,
    index: int,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_donor: Path,
    devices: bytes,
) -> dict[str, Any]:
    kind = dcv15.v8.DC_VOLTAGE
    groups = dcv15.v8._map_groups_to_source_nets(payload, kind)
    source_net_chunk, specs, topology, rcl_counts = dcv15.v8.v5._source_net_rcl(templates, groups)
    source_id = len(specs) + 1
    source = dcv15.v8.SourceSpec(
        idx=source_id,
        ref=kind.source_ref,
        value=kind.source_value,
        model=kind.model,
        positive=kind.positive_net,
        negative=kind.negative_net,
        prop_text=kind.prop_text,
    )
    source_block = dcv15.v8._source_block_preserve_suffix(kind, source_donor, global_id=source_id)
    object_chunk, wire_repair = dcv15.v13._repair_generated_negative_wire_high_bytes(
        dcv15.v8._source_first_chunk(source_block, source_net_chunk)
    )
    case_id = f"SRCP_V1_DCV_T{index:02d}_{_suffix(payload)}"
    description = f"DC-voltage source-driven {payload['metadata']['description']}"
    manifest = dcv15.v8._write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=dcv15.v8._build_cdb(specs, source),
        devices=devices,
        input_payload={
            "base_payload_name": payload["project"]["name"],
            "source_kind": "dc_voltage",
            "source_rule": "V15 accepted DCV path: source-first VSOURCE block, DV/D0 labels, V13 WIRE repair.",
            "passive_family_combo": payload["metadata"]["family_combo"],
            "source": {"idx": source.idx, "ref": source.ref, "value": source.value, "model": source.model},
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
            "rcl_counts": rcl_counts,
            "wire_repair": wire_repair,
            "topology": topology,
        },
    )
    manifest["status"] = "temporary_source_passive_v1_dcv_pending_user_test"
    (TEST_BATCH / case_id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _make_dci_case(
    *,
    index: int,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    dcv_source_project: Path,
    devices: bytes,
) -> dict[str, Any]:
    groups = dci13.v12._map_groups_to_dv_d0(dci13.v12._payload_groups(payload))
    source_net_chunk, specs, topology, rcl_counts = dci13.v5._source_net_rcl(templates, groups)
    source = dci13.v10.SourceSpec(idx=len(specs) + 1, ref="V1", value="10V")
    source_block = dci13.v12._dcv_geometry_csource_block(dcv_source_project, global_id=source.idx)
    object_chunk, wire_repair = dcv15.v13._repair_generated_negative_wire_high_bytes(
        dci13.v12._source_first_chunk(source_block, source_net_chunk)
    )
    case_id = f"SRCP_V1_DCI_T{index:02d}_{_suffix(payload)}"
    description = f"DC-current source-driven {payload['metadata']['description']} using V13 accepted DCI identity."
    manifest = dci13._write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=dci13.v10._build_cdb(specs, source),
        devices=devices,
        input_payload={
            "base_payload_name": payload["project"]["name"],
            "source_kind": "dc_current",
            "source_rule": "V13 accepted DCI path: DCV source geometry, DV/D0 labels, final/CDB/device CSOURCE identity.",
            "passive_family_combo": payload["metadata"]["family_combo"],
            "source": {"idx": source.idx, "ref": source.ref, "value": source.value, "model": source.model},
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
            "rcl_counts": rcl_counts,
            "wire_repair": wire_repair,
            "topology": topology,
        },
    )
    manifest["status"] = "temporary_source_passive_v1_dci_pending_user_test"
    (TEST_BATCH / case_id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _make_acv_case(
    *,
    index: int,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    variant_project: Path,
    two_source_project: Path,
    devices: bytes,
) -> dict[str, Any]:
    case_id = f"SRCP_V1_ACV_T{index:02d}_{_suffix(payload)}"
    manifest = acv2._make_source_first_case(
        case_id=case_id,
        description=f"AC-voltage source-driven {payload['metadata']['description']} using accepted V2 non-final AV/A0 unit.",
        payload=payload,
        source_block_kind="two_source_nonfinal_av_a0",
        templates=templates,
        base_project=base_project,
        donor_project=donor_project,
        variant_project=variant_project,
        two_source_project=two_source_project,
        devices=devices,
    )
    manifest["status"] = "temporary_source_passive_v1_acv_pending_user_test"
    manifest["input"]["passive_family_combo"] = payload["metadata"]["family_combo"]
    manifest["input"]["source_rule"] = "V2 accepted ACV path: source-first exact non-final AV/A0 VSINE unit from two-source donor."
    (TEST_BATCH / case_id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _summarize_case(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": manifest["case_id"],
        "description": manifest["description"],
        "marker_counts": manifest["marker_counts"],
        "device_marker_counts": manifest.get("device_marker_counts"),
        "object_chunk_len": manifest["object_chunk_len"],
        "root_cdb_len": manifest["root_cdb_len"],
        "static_validation_issues": manifest["static_validation_issues"],
        "passive_family_combo": manifest.get("input", {}).get("passive_family_combo"),
        "source_kind": manifest.get("input", {}).get("source_kind"),
    }


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)
    _set_module_paths()
    donors = _copy_archived_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = dcv15.v8.v5.rcl._load_rcl_unit_templates(rcl_donor)

    dcv_devices = dcv15.v8.v5._device_section_from_dsn(read_internal_file(donors["dcv_manual_combined_testing"], "ROOT.DSN"))
    dci_devices = dci13.v5._device_section_from_dsn(read_internal_file(donors["dci_manual_testing"], "ROOT.DSN"))
    acv_devices = acv2.v1.v5._device_section_from_dsn(read_internal_file(donors["acv_source_load"], "ROOT.DSN"))

    payloads = passive_probe_payloads()
    cases: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads, start=1):
        cases.append(
            _make_dcv_case(
                index=index,
                payload=payload,
                templates=templates,
                base_project=base_project,
                donor_project=donors["dcv_manual_combined_testing"],
                source_donor=donors["dcv_source_10v"],
                devices=dcv_devices,
            )
        )
    for index, payload in enumerate(payloads, start=1):
        cases.append(
            _make_dci_case(
                index=index,
                payload=payload,
                templates=templates,
                base_project=base_project,
                donor_project=donors["dci_manual_testing"],
                dcv_source_project=donors["dci_dcv_source_10v"],
                devices=dci_devices,
            )
        )
    for index, payload in enumerate(payloads, start=1):
        cases.append(
            _make_acv_case(
                index=index,
                payload=payload,
                templates=templates,
                base_project=base_project,
                donor_project=donors["acv_source_load"],
                variant_project=donors["acv_variant_source"],
                two_source_project=donors["acv_two_source"],
                devices=acv_devices,
            )
        )

    summary = {
        "batch_id": "SOURCE_PASSIVE_V1_SINGLE_TWO_FAMILY_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "purpose": "Test source-driven single-family and two-family passive loads, not full R/C/L loads.",
        "method": {
            "dc_voltage": "V15 accepted source-first VSOURCE block with DV/D0 and V13 WIRE repair.",
            "dc_current": "V13 accepted DCV geometry patched to CSOURCE identity with DV/D0 and V13 WIRE repair.",
            "ac_voltage": "V2 accepted exact non-final AV/A0 VSINE unit from two-source donor.",
            "passive_body": "Accepted mixed_rcl subgroup-removal modes R, C, L, RC, RL, and LC.",
        },
        "supported_surface_under_test": {
            "single_family": ["R", "C", "L"],
            "two_family": ["R+C", "R+L", "C+L"],
            "sources": ["DC voltage", "DC current", "AC voltage"],
        },
        "test_order": [item["case_id"] for item in cases],
        "cases": [_summarize_case(item) for item in cases],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V1 single/two-family probe pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT01-T06 are DC voltage, T07-T12 are DC current, and T13-T18 are AC voltage.\n"
        + "Each source family tests R, C, L, RC, RL, and LC/C+L loads.\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")

    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
