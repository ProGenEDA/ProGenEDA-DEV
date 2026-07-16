"""Generate AC-voltage V2 diagnostics using the exact non-final source unit.

V1 proved exact AC source donors, E001 transplants, and generated AV/A0 R/C/L
with no source all work, but every generated source insertion failed with
VGDVC.dll. The most likely V1 fault is source block final/non-final shape:
the standalone variant donor has a 51-byte final second wire, while the
two-source donor shows the first non-final VSINE unit uses a 50-byte second
wire and different terminal link suffixes.

This batch tests source-first insertion using the exact first non-final
AV/A0 VSINE unit from 2xac_voltage_02_variant.pdsprj.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen.mixed_rcl_examples import mixed_rcl_21_case, mixed_rcl_6_case, mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen import resistor_v9 as rv9  # noqa: E402

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "ac_voltage_v2_nonfinal_source_unit_temp_2026_06_04"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "AC_VOLTAGE_V2_NONFINAL_SOURCE_UNIT_TEMP_2026_06_04"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "ACV_V2_NONFINAL_SOURCE_UNIT_TEST_BATCH"
V1_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-04" / "generate_ac_voltage_v1_source_diagnostics_temp.py"


def _load_v1() -> Any:
    spec = importlib.util.spec_from_file_location("ac_voltage_v1_for_v2", V1_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import ACV V1 helper module from {V1_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUT_ROOT = OUT_ROOT
    module.ARCHIVE_BASE = ARCHIVE_BASE
    module.DONOR_ROOT = DONOR_ROOT
    module.TEST_BATCH = TEST_BATCH
    return module


v1 = _load_v1()
rcl = v1.rcl


def _nonfinal_two_source_av_a0_block(two_source_project: Path, *, global_id: int) -> bytes:
    body = v1._object_chunk(two_source_project)[1:]
    # In 2xac_voltage_02_variant:
    #   output AV1: body[0:105]
    #   output AV:  body[105:209]
    #   input A0 + V1 VSINE + two non-final wires: body[209:778]
    block = bytearray(body[105:778])
    if len(block) != 673:
        raise RuntimeError(f"Unexpected non-final AC source unit length: {len(block)}")
    if block.count(b"$TEROUTPUT") != 1 or block.count(b"$TERINPUT") != 1 or block.count(b"VSINE") != 3:
        raise RuntimeError("Extracted two-source block does not look like one AV/A0 VSINE unit.")
    block[207:573] = v1._patch_source_global_id_only(bytes(block[207:573]), global_id)
    block[-1] = 0x00
    return bytes(block)


def _standalone_trimmed_variant_block(variant_project: Path, *, global_id: int) -> bytes:
    block = bytearray(v1._object_chunk(variant_project)[1:-1])
    if len(block) != 673:
        raise RuntimeError(f"Unexpected trimmed standalone source unit length: {len(block)}")
    block[207:573] = v1._patch_source_global_id_only(bytes(block[207:573]), global_id)
    block[-1] = 0x00
    return bytes(block)


def _make_source_first_case(
    *,
    case_id: str,
    description: str,
    payload: dict[str, Any],
    source_block_kind: str,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    variant_project: Path,
    two_source_project: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts, groups = v1._source_net_rcl(templates, payload)
    source = v1.AcVoltageSpec(idx=len(specs) + 1, ref="V1", value="VSINE", prop_text=v1._source_prop_text(variant_project))
    if source_block_kind == "two_source_nonfinal_av_a0":
        source_block = _nonfinal_two_source_av_a0_block(two_source_project, global_id=source.idx)
    elif source_block_kind == "standalone_variant_trimmed":
        source_block = _standalone_trimmed_variant_block(variant_project, global_id=source.idx)
    else:
        raise ValueError(source_block_kind)
    return v1._write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=v1._source_first_chunk(source_block, source_net_chunk),
        cdb=v1._build_cdb(specs, [source], "before_rcl"),
        devices=devices,
        input_payload={
            "base_payload_name": payload["project"]["name"],
            "source_kind": "ac_voltage",
            "source_model": "VSINE",
            "source_position": "before_rcl",
            "source_block_kind": source_block_kind,
            "source": {"idx": source.idx, "ref": source.ref, "value": source.value, "properties": source.prop_text.decode("ascii", "replace")},
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
            "rcl_counts": rcl_counts,
            "topology": topology,
        },
    )


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)
    donors = v1._copy_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = rcl._load_rcl_unit_templates(rcl_donor)

    variant_source = donors["ac_voltage_02_variant"]
    two_source = donors["2xac_voltage_02_variant"]
    source_load = donors["ac_voltage_03_resistor_load"]
    acv_devices = v1.v5._device_section_from_dsn(read_internal_file(source_load, "ROOT.DSN"))
    rcl_devices = v1.v5._device_section_from_dsn(read_internal_file(rcl_donor, "ROOT.DSN"))

    simple_loop = mixed_rcl_15_cases()[0]
    six_case = mixed_rcl_6_case()
    twenty_one_case = mixed_rcl_21_case()

    cases: list[dict[str, Any]] = []
    cases.append(
        v1._write_transplant_case(
            "ACV_V2_T00_TWO_SOURCE_TRANSPLANT_CONTROL",
            "Known-good two-source AC voltage donor transplant into E001.",
            base_project=base_project,
            donor_project=two_source,
        )
    )
    no_source_chunk, no_source_specs, no_source_topology, no_source_counts, no_source_groups = v1._source_net_rcl(templates, six_case)
    cases.append(
        v1._write_case(
            "ACV_V2_T01_RCL_AV_A0_NO_SOURCE_CONTROL",
            "Known-good generated six-component R/C/L body on AV/A0 labels with no source object.",
            base_project=base_project,
            donor_project=rcl_donor,
            object_chunk=no_source_chunk,
            cdb=rcl.build_cdb(no_source_specs),
            devices=rcl_devices,
            input_payload={
                "base_payload_name": six_case["project"]["name"],
                "source_kind": "none",
                "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in no_source_groups],
                "rcl_counts": no_source_counts,
                "topology": no_source_topology,
            },
        )
    )
    for case_id, description, payload in (
        (
            "ACV_V2_T02_SIMPLE_LOOP_TWO_SOURCE_NONFINAL",
            "Simple-loop R/C/L with source-first exact non-final AV/A0 VSINE unit extracted from two-source donor.",
            simple_loop,
        ),
        (
            "ACV_V2_T03_SIX_COMPONENT_TWO_SOURCE_NONFINAL",
            "Six-component R/C/L with source-first exact non-final AV/A0 VSINE unit extracted from two-source donor.",
            six_case,
        ),
        (
            "ACV_V2_T04_21_RULE_TWO_SOURCE_NONFINAL",
            "Corrected 21-rule R/C/L with source-first exact non-final AV/A0 VSINE unit extracted from two-source donor.",
            twenty_one_case,
        ),
    ):
        cases.append(
            _make_source_first_case(
                case_id=case_id,
                description=description,
                payload=payload,
                source_block_kind="two_source_nonfinal_av_a0",
                templates=templates,
                base_project=base_project,
                donor_project=source_load,
                variant_project=variant_source,
                two_source_project=two_source,
                devices=acv_devices,
            )
        )
    for case_id, description, payload in (
        (
            "ACV_V2_T05_SIMPLE_LOOP_STANDALONE_TRIMMED",
            "Simple-loop R/C/L with source-first standalone variant VSINE block trimmed to the two-source non-final length.",
            simple_loop,
        ),
        (
            "ACV_V2_T06_SIX_COMPONENT_STANDALONE_TRIMMED",
            "Six-component R/C/L with source-first standalone variant VSINE block trimmed to the two-source non-final length.",
            six_case,
        ),
    ):
        cases.append(
            _make_source_first_case(
                case_id=case_id,
                description=description,
                payload=payload,
                source_block_kind="standalone_variant_trimmed",
                templates=templates,
                base_project=base_project,
                donor_project=source_load,
                variant_project=variant_source,
                two_source_project=two_source,
                devices=acv_devices,
            )
        )

    summary = {
        "batch_id": "AC_VOLTAGE_V2_NONFINAL_SOURCE_UNIT_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "ACV V1 user feedback: T00-T04 worked; T05 and onwards failed with VGDVC.dll.",
        "method": "Test exact two-source non-final AV/A0 VSINE source unit and trimmed standalone variant source unit.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item["marker_counts"],
                "device_marker_counts": item.get("device_marker_counts"),
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "AC voltage V2 non-final source-unit diagnostics.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT02-T04 are the primary candidates: exact non-final AV/A0 source unit from the two-source donor.\n"
        + "T05-T06 isolate whether length trimming alone is sufficient with standalone suffixes.\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(
        json.dumps(
            {
                "out_root": str(OUT_ROOT),
                "archive": archive,
                "archive_sha256": v1._sha256_file(Path(archive)),
                "test_order": summary["test_order"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
