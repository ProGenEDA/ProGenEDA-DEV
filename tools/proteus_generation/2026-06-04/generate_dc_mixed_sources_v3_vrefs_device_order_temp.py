"""Generate stricter V3 mixed DC voltage/current source diagnostics.

V1 and V2 requested packs both failed with ISIS.dll. The strict issue now under
test is source identity:

* Accepted DC voltage generation uses DCV geometry with ref/value V1/10V.
* Accepted DC current generation also uses DCV geometry with ref/value V1/10V,
  then changes only model identity to CSOURCE.
* V1/V2 changed current-source references to I1/I2 and mixed a new device order.

V3 keeps all source object references V-style (V1, V2, ...), uses passive-style
CDB pin maps like the accepted generated DCV/DCI packs, and emits an explicit
device-family order: CAP, VSOURCE, CSOURCE, REALIND, RESISTOR.
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
DCV_MANUAL = REPO_ROOT / "experiments" / "dc_sources_v7_accepted_source_first_temp_2026_06_03" / "donors" / "manual_combined_testing.pdsprj"
DCI_MANUAL = REPO_ROOT / "experiments" / "dc_current_v12_manual_testing_study_temp_2026_06_03" / "donors" / "manual_testing.pdsprj"


def _load_v1() -> Any:
    spec = importlib.util.spec_from_file_location("dc_mixed_sources_v1_for_v3", V1_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V1 helper module from {V1_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_v1()

v1.OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v3_vrefs_device_order_temp_2026_06_04"
v1.ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V3_VREFS_DEVICE_ORDER_TEMP_2026_06_04"
v1.DONOR_ROOT = v1.OUT_ROOT / "donors"
v1.TEST_BATCH = v1.OUT_ROOT / "DC_MIXED_SOURCES_V3_VREFS_DEVICE_ORDER_TEST_BATCH"


def _family_chunks(section: bytes) -> dict[str, bytes]:
    starts: dict[str, int] = {}
    for name in ("CAP", "VSOURCE", "CSOURCE", "REALIND", "RESISTOR"):
        pos = section.find(name.encode("ascii"))
        if pos >= 0:
            starts[name] = max(0, pos - 1)
    ordered = sorted(starts.items(), key=lambda item: item[1])
    chunks: dict[str, bytes] = {}
    for index, (name, start) in enumerate(ordered):
        end = ordered[index + 1][1] if index + 1 < len(ordered) else len(section) - 4
        chunks[name] = section[start:end]
    return chunks


def _ordered_mixed_device_section(dcv_manual: Path, dci_manual: Path) -> bytes:
    dcv = _family_chunks(v1.v5._device_section_from_dsn(v1.read_internal_file(dcv_manual, "ROOT.DSN")))
    dci_section = v1.v5._device_section_from_dsn(v1.read_internal_file(dci_manual, "ROOT.DSN"))
    dci = _family_chunks(dci_section)
    required = {
        "CAP": dci.get("CAP") or dcv.get("CAP"),
        "VSOURCE": dcv.get("VSOURCE"),
        "CSOURCE": dci.get("CSOURCE"),
        "REALIND": dci.get("REALIND") or dcv.get("REALIND"),
        "RESISTOR": dci.get("RESISTOR") or dcv.get("RESISTOR"),
    }
    missing = [name for name, chunk in required.items() if not chunk]
    if missing:
        raise RuntimeError(f"Missing device families: {missing}")
    return b"".join(required[name] for name in ("CAP", "VSOURCE", "CSOURCE", "REALIND", "RESISTOR")) + dci_section[-4:]


def _case_definitions_v3() -> list[Any]:
    out = []
    for case_index, case in enumerate(v1._case_definitions(), start=1):
        sources = []
        for source_index, source in enumerate(case.sources, start=1):
            sources.append(
                replace(
                    source,
                    ref=f"V{source_index}",
                    visible_value=source.visible_value if len(source.visible_value) == 3 else "10V",
                )
            )
        out.append(
            replace(
                case,
                case_id=case.case_id.replace("DCMS_V1", "DCMS_V3"),
                sources=tuple(sources),
                description=case.description + " V3 uses V-style source refs and ordered source device metadata.",
            )
        )
    return out


def _write_source_only_control(
    *,
    base_project: Path,
    donor_project: Path,
    source_donor_4x: Path,
    devices: bytes,
) -> dict[str, Any]:
    sources = (
        v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
        v1.SourcePlan("dc_current", "V2", "2A", "02A", "D1"),
    )
    source_block, source_rows = v1._source_block(sources, source_donor_4x, 1)
    object_chunk = bytearray(b"\x00" + source_block)
    object_chunk[-1] = 0xFF
    return v1._write_case(
        "DCMS_V3_T00_SOURCE_ONLY_V1_V2_CONTROL",
        "Control: one VSOURCE and one CSOURCE source object only, both using V-style refs and ordered mixed source device metadata.",
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=bytes(object_chunk),
        cdb=v1._build_cdb([], source_rows, 1),
        devices=devices,
        input_payload={
            "control": "source_only_mixed_voltage_current",
            "sources": [
                {
                    "kind": source.kind,
                    "ref": source.ref,
                    "value": source.cdb_value,
                    "visible_value": source.visible_value,
                    "positive": source.positive,
                    "negative": source.negative,
                    "model": source.model,
                    "global_id": index,
                }
                for index, source in enumerate(source_rows, start=1)
            ],
        },
    )


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

    devices = _ordered_mixed_device_section(DCV_MANUAL, DCI_MANUAL)

    cases: list[dict[str, Any]] = [
        _write_source_only_control(
            base_project=base_project,
            donor_project=DCI_MANUAL,
            source_donor_4x=donors["4x_dc_voltage_10v"],
            devices=devices,
        )
    ]
    for item in _case_definitions_v3():
        cases.append(
            v1._make_case(
                item,
                templates=templates,
                base_project=base_project,
                donor_project=DCI_MANUAL,
                source_donor_4x=donors["4x_dc_voltage_10v"],
                devices=devices,
            )
        )
    for item in cases:
        item["status"] = "temporary_dc_mixed_sources_v3_vrefs_device_order_not_locked"
        item["strict_v3_rule"] = "V-style refs for voltage/current source geometry; device order CAP, VSOURCE, CSOURCE, REALIND, RESISTOR; passive CDB source pin maps."
        manifest_path = v1.TEST_BATCH / item["case_id"] / "manifest.json"
        if manifest_path.exists():
            manifest_path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V3_VREFS_DEVICE_ORDER_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V1 and V2 user feedback: all five requested mixed-source circuits gave ISIS.dll.",
        "method": "Keep all source object references V-style and use an explicit CAP, VSOURCE, CSOURCE, REALIND, RESISTOR device-family order.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "source_count": item.get("source_count"),
                "rcl_component_count": item.get("rcl_component_count", 0),
                "marker_counts": item["marker_counts"],
                "device_marker_counts": item["device_marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
                "strict_v3_rule": item["strict_v3_rule"],
            }
            for item in cases
        ],
    }
    (v1.TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (v1.TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V3_VREFS_DEVICE_ORDER_TEMP_2026_06_04\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT00 is a source-only mixed VSOURCE/CSOURCE control. T01-T05 are the requested circuits with V-style source refs.\n",
        encoding="utf-8",
    )
    archive = shutil.make_archive(str(v1.ARCHIVE_BASE), "zip", v1.OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": v1._sha256_file(Path(archive)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
