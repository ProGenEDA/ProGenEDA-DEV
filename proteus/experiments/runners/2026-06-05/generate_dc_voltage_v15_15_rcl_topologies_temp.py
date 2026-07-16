"""Generate the 15 mixed R/C/L topologies with a DC voltage source.

This is a current-date, DC-voltage-only pack. It reuses the user-confirmed V8
DCV source-first method:

* source block is first
* source positive net is DV
* source negative net is D0
* generated R/C/L topology is ordinary terminal-label topology
* no $TERPOWER or $TERGROUND records are emitted

V8 also generated a DCI half, but the user rejected that old DCI path. V15
keeps only the accepted DC voltage source family.
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

from proteusgen.mixed_rcl_examples import mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V8_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_sources_v8_15_voltage_15_current_temp.py"
V13_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v13_v0_source_geometry_temp.py"
OUT_ROOT = REPO_ROOT / "experiments" / "dc_voltage_v15_15_rcl_topologies_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_VOLTAGE_V15_15_RCL_TOPOLOGIES_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DCV_V15_15_RCL_TOPOLOGIES_TEST_BATCH"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v8 = _load_module("dc_sources_v8_for_dcv_v15", V8_PATH)
v13 = _load_module("dc_mixed_sources_v13_for_dcv_v15", V13_PATH)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _case_suffix(index: int, payload_name: str) -> str:
    parts = payload_name.split("_")
    return f"T{index:02d}_" + "_".join(parts[4:])


def _make_voltage_case(
    *,
    index: int,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_donor: Path,
    devices: bytes,
) -> dict[str, Any]:
    kind = v8.DC_VOLTAGE
    groups = v8._map_groups_to_source_nets(payload, kind)
    source_net_chunk, specs, topology, rcl_counts = v8.v5._source_net_rcl(templates, groups)
    source_id = len(specs) + 1
    source = v8.SourceSpec(
        idx=source_id,
        ref=kind.source_ref,
        value=kind.source_value,
        model=kind.model,
        positive=kind.positive_net,
        negative=kind.negative_net,
        prop_text=kind.prop_text,
    )
    source_block = v8._source_block_preserve_suffix(kind, source_donor, global_id=source_id)
    object_chunk, wire_repair = v13._repair_generated_negative_wire_high_bytes(v8._source_first_chunk(source_block, source_net_chunk))
    case_id = f"DCV_V15_{_case_suffix(index, payload['project']['name'])}"
    description = f"DC-voltage source-driven {payload['metadata']['description']}"
    manifest = v8._write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=v8._build_cdb(specs, source),
        devices=devices,
        input_payload={
            "base_payload_name": payload["project"]["name"],
            "source_kind": "dc_voltage",
            "source_position": "before_rcl",
            "source_rule": "V8/V15 accepted DCV source-first method: DV positive net, D0 negative net, VSOURCE model.",
            "source": {
                "idx": source.idx,
                "ref": source.ref,
                "value": source.value,
                "model": source.model,
                "positive_net": kind.positive_net,
                "negative_net": kind.negative_net,
            },
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
            "rcl_counts": rcl_counts,
            "wire_repair": wire_repair,
            "topology": topology,
        },
    )
    manifest["status"] = "temporary_dc_voltage_v15_15_rcl_topologies_awaiting_user_test"
    manifest_path = TEST_BATCH / case_id / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)

    v8.OUT_ROOT = OUT_ROOT
    v8.ARCHIVE_BASE = ARCHIVE_BASE
    v8.DONOR_ROOT = DONOR_ROOT
    v8.TEST_BATCH = TEST_BATCH
    donors = v8._copy_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v8.v5.rcl._load_rcl_unit_templates(rcl_donor)

    voltage_devices = v8.v5._device_section_from_dsn(read_internal_file(donors["manual_combined_testing"], "ROOT.DSN"))
    payloads = mixed_rcl_15_cases()
    cases = [
        _make_voltage_case(
            index=index,
            payload=payload,
            templates=templates,
            base_project=base_project,
            donor_project=donors["manual_combined_testing"],
            source_donor=donors[v8.DC_VOLTAGE.donor_name],
            devices=voltage_devices,
        )
        for index, payload in enumerate(payloads, start=1)
    ]

    summary = {
        "batch_id": "DC_VOLTAGE_V15_15_RCL_TOPOLOGIES_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "User previously confirmed all V8 DC-voltage source-driven 15 topology cases worked. User rejected the old V8 DC-current half.",
        "method": "DC voltage only; source-first standalone VSOURCE block; DV/D0 source-net labels; no $TERPOWER/$TERGROUND; V13 negative-row WIRE high-byte repair; 15 locked mixed R/C/L topology payloads.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item["marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "DC voltage V15 15-R/C/L-topology pack using the accepted V8 DCV method plus the V13 WIRE high-byte repair.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nEach case uses a 10V VSOURCE, DV as the positive source net, and D0 as the negative source net.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
