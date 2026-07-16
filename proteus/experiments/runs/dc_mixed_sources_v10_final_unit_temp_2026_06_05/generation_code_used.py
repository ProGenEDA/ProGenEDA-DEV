"""Generate V10 diagnostics for mixed DC sources plus R/C/L final-unit order.

V9 established a precise failure boundary:

* T00 donor copy worked.
* T01 donor object/CDB/device transplant worked.
* T02 donor terminal-label mutation worked.
* T03 onward failed when the generated R/C/L body replaced the donor body.

The byte-level comparison shows the donor source tail is identical in V9 T03.
The first semantic body mismatch is in the last RL group: the donor emits the
final resistor section before the final inductor section and then connects that
last inductor to DVO. The generated body emits inductor before resistor.

This pack keeps the work temporary. It tests whether restoring only that final
donor unit is enough, and separately checks whether the generated CDB writer is
compatible with the donor-safe object stream.
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

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V9_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v9_donor_tail_temp.py"
OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v10_final_unit_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V10_FINAL_UNIT_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"


def _load_v9() -> Any:
    spec = importlib.util.spec_from_file_location("dc_mixed_sources_v9_for_v10", V9_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V9 helper module from {V9_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v9 = _load_v9()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _combine_body_tail(body: bytes, tail: bytes) -> bytes:
    if body[-1] != 0xFF or tail[-1] != 0xFF:
        raise RuntimeError("Body and tail chunks must be independently final before combining.")
    out = bytearray(body)
    out[-1] = 0x00
    out += tail
    out[-1] = 0xFF
    return bytes(out)


def _last_donor_final_unit_start(donor_chunk: bytes, tail_start: int) -> int:
    """Return the start of the donor's final RL output/body section.

    In the manual donor, the final RL group starts with two input terminals and
    then an OUT A9 terminal for the resistor output. Replacing from that OUT A9
    through the source tail restores the donor's final resistor-before-inductor
    order while leaving the generated prefix in place.
    """

    candidates = [
        start
        for start, kind, label in v9._terminal_events(donor_chunk)
        if start < tail_start and kind == "OUT" and label == "A9"
    ]
    if not candidates:
        raise RuntimeError("Could not locate donor final OUT A9 terminal.")
    final_start = candidates[-1]
    if donor_chunk[final_start:tail_start].count(b"RESISTOR") != 2:
        raise RuntimeError("Donor final section does not contain one resistor object.")
    if donor_chunk[final_start:tail_start].count(b"REALIND") != 3:
        raise RuntimeError("Donor final section does not contain one inductor object.")
    return final_start


def _copy_donor_for_v10() -> Path:
    v9.OUT_ROOT = OUT_ROOT
    v9.ARCHIVE_BASE = ARCHIVE_BASE
    v9.DONOR_ROOT = DONOR_ROOT
    return v9._copy_donor()


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    donor = _copy_donor_for_v10()
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v9.rcl._load_rcl_unit_templates(rcl_donor)

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_chunk = rv9._extract_object_chunk(donor_dsn)
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_devices = v9.v5._device_section_from_dsn(donor_dsn)
    donor_tail_start = v9._find_source_tail_start(donor_chunk)
    donor_tail = donor_chunk[donor_tail_start:]
    donor_body = donor_chunk[:donor_tail_start]
    final_unit_start = _last_donor_final_unit_start(donor_chunk, donor_tail_start)

    generated_body_d0, generated_specs_d0, generated_topology_d0, generated_counts_d0 = v9._build_rcl_body_keep_v0_output(
        templates,
        negative_label="D0",
    )
    generated_cdb = v9._build_cdb(generated_specs_d0)

    donor_d0_chunk = v9._patch_terminal_labels(donor_chunk, {"DVO": "D0"})
    generated_body_dvo = v9._patch_terminal_labels(generated_body_d0, {"D0": "DVO"})
    generated_dvo_chunk = _combine_body_tail(generated_body_dvo, donor_tail)
    generated_prefix_donor_final = generated_body_d0[:final_unit_start] + donor_chunk[final_unit_start:]
    generated_prefix_donor_final_d0 = v9._patch_terminal_labels(generated_prefix_donor_final, {"DVO": "D0"})

    cases: list[dict[str, Any]] = [
        v9._copy_control("DCMS_V10_T00_DONOR_COPY", "Exact copy of the user donor control.", donor),
        v9._write_case(
            "DCMS_V10_T01_DONOR_TRANSPLANT_E001",
            "Donor object chunk, donor ROOT.CDB, and donor device section transplanted to E001.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_chunk,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_object_cdb_devices_transplant"},
        ),
        v9._write_case(
            "DCMS_V10_T02_DONOR_LABEL_DVO_TO_D0",
            "Exact donor object structure with all DVO terminal labels changed to D0.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_d0_chunk,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_terminal_label_mutation", "terminal_replacements": {"DVO": "D0"}},
        ),
        v9._write_case(
            "DCMS_V10_T03_DONOR_OBJECT_GENERATED_CDB",
            "Exact donor object structure and donor device section, but generated CDB rows.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_chunk,
            cdb=generated_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_object_with_generated_cdb", "cdb_order": "RCL passives then I1 then V1"},
        ),
        v9._write_case(
            "DCMS_V10_T04_DONOR_D0_GENERATED_CDB",
            "DVO-to-D0 donor object mutation with generated CDB rows.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_d0_chunk,
            cdb=generated_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_label_mutation_with_generated_cdb", "terminal_replacements": {"DVO": "D0"}},
        ),
        v9._write_case(
            "DCMS_V10_T05_GENERATED_21_DVO_LABEL",
            "Generated 21 R/C/L body using DVO as the final negative net, then exact donor source tail.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=generated_dvo_chunk,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={
                "kind": "generated_rcl_body_dvo_label_exact_donor_tail",
                "generation_counts": {**generated_counts_d0, "source_tail_len": len(donor_tail), "body_d0_to_dvo_patch": True},
                "topology": generated_topology_d0,
            },
        ),
        v9._write_case(
            "DCMS_V10_T06_GENERATED_PREFIX_DONOR_FINAL_UNIT",
            "Generated R/C/L prefix, donor final RL unit order, and exact donor source tail.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=generated_prefix_donor_final,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={
                "kind": "generated_prefix_with_donor_final_unit",
                "final_unit_start": final_unit_start,
                "donor_tail_start": donor_tail_start,
                "generation_counts": {**generated_counts_d0, "source_tail_len": len(donor_tail), "donor_final_unit_spliced": True},
                "topology": generated_topology_d0,
            },
        ),
        v9._write_case(
            "DCMS_V10_T07_GENERATED_PREFIX_DONOR_FINAL_UNIT_D0",
            "Generated R/C/L prefix, donor final RL unit order, and DVO changed to D0.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=generated_prefix_donor_final_d0,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={
                "kind": "generated_prefix_with_donor_final_unit_d0_label",
                "final_unit_start": final_unit_start,
                "donor_tail_start": donor_tail_start,
                "terminal_replacements": {"DVO": "D0"},
            },
        ),
        v9._write_case(
            "DCMS_V10_T08_GENERATED_PREFIX_DONOR_FINAL_UNIT_D0_GENERATED_CDB",
            "Same as T07, but with generated CDB rows.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=generated_prefix_donor_final_d0,
            cdb=generated_cdb,
            devices=donor_devices,
            input_payload={
                "kind": "generated_prefix_with_donor_final_unit_d0_label_generated_cdb",
                "final_unit_start": final_unit_start,
                "donor_tail_start": donor_tail_start,
                "terminal_replacements": {"DVO": "D0"},
                "cdb_order": "RCL passives then I1 then V1",
            },
        ),
    ]

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V10_FINAL_UNIT_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "User reported V9 T03 and onward gave VGDVC.dll. V9 T00-T02 worked.",
        "method": "Keep donor controls, test generated CDB on donor-safe object chunks, then splice the donor final RL unit into the generated prefix.",
        "donor_tail_start": donor_tail_start,
        "donor_final_unit_start": final_unit_start,
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item.get("marker_counts"),
                "device_marker_counts": item.get("device_marker_counts"),
                "object_chunk_len": item.get("object_chunk_len"),
                "root_cdb_len": item.get("root_cdb_len"),
                "static_validation_issues": item.get("static_validation_issues"),
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V10_FINAL_UNIT_TEMP_2026_06_05\n\n"
        "Open in order:\n"
        + "\n".join(
            f"{index}. {case_id}.pdsprj" if index == 1 else f"{index}. {case_id}/{case_id}.pdsprj"
            for index, case_id in enumerate(summary["test_order"], start=1)
        )
        + "\n\nT00-T02 repeat the V9 passing boundary. T03/T04 test the generated CDB on donor-safe objects. "
        "T05 tests whether label matching alone fixes generated body failure. T06-T08 test the generated prefix with the donor final RL unit restored.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
