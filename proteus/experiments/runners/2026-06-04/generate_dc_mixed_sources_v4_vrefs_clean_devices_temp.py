"""Generate mixed DC voltage/current source diagnostics after V1/V2 rejection.

User feedback rejected both prior requested packs:

* V1 used four-source DCV donor units, but current sources were renamed I1/I2
  and device metadata was concatenated from donors.
* V2 changed source CDB pin maps to +/-; this also failed. Byte checks of the
  accepted generated DCV/DCI files show those generated files actually used the
  passive-style source pin map, so +/- is not the fix for generated output.

V4 keeps the part of V1 that is still useful, namely the user-made four-source
DCV donor units with unique source-unit suffixes and coordinates. It changes
the risky parts:

* every source uses V-style refs: V1, V2, V3, V4
* DC current keeps the accepted DCV geometry shape and changes only final model
  identity to CSOURCE
* source CDB rows use the accepted generated passive-style pin map
* device metadata is rebuilt in one clean order: CAP, VSOURCE, CSOURCE,
  REALIND, RESISTOR
* all donors are read from archived accepted experiment folders, not live
  Downloads paths

This is still a temporary batch. T00A/T00B are source-only controls. T01-T05
are the five user-requested mixed-source R/C/L circuits.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

V1_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-04" / "generate_dc_mixed_sources_v1_requested5_temp.py"

ARCHIVED_4X_DCV = (
    REPO_ROOT
    / "experiments"
    / "dc_mixed_sources_v1_requested5_temp_2026_06_04"
    / "donors"
    / "4x_dc_voltage_10v.pdsprj"
)
ARCHIVED_DCV_MANUAL = (
    REPO_ROOT
    / "experiments"
    / "dc_sources_v7_accepted_source_first_temp_2026_06_03"
    / "donors"
    / "manual_combined_testing.pdsprj"
)
ARCHIVED_DCI_MANUAL = (
    REPO_ROOT
    / "experiments"
    / "dc_current_v12_manual_testing_study_temp_2026_06_03"
    / "donors"
    / "manual_testing.pdsprj"
)


def _load_v1() -> Any:
    spec = importlib.util.spec_from_file_location("dc_mixed_sources_v1_for_v4", V1_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V1 helper module from {V1_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_v1()

v1.OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_mixed_sources_v4_vrefs_clean_devices_temp_2026_06_04"
v1.ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_MIXED_SOURCES_V4_VREFS_CLEAN_DEVICES_TEMP_2026_06_04"
v1.DONOR_ROOT = v1.OUT_ROOT / "donors"
v1.TEST_BATCH = v1.OUT_ROOT / "DC_MIXED_SOURCES_V4_VREFS_CLEAN_DEVICES_TEST_BATCH"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_archived_donors() -> dict[str, Path]:
    v1.DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "4x_dc_voltage_10v": ARCHIVED_4X_DCV,
        "dcv_manual_combined": ARCHIVED_DCV_MANUAL,
        "dci_manual_testing": ARCHIVED_DCI_MANUAL,
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = v1.DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


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


def _ordered_device_section(dcv_manual: Path, dci_manual: Path) -> bytes:
    dcv_section = v1.v5._device_section_from_dsn(v1.read_internal_file(dcv_manual, "ROOT.DSN"))
    dci_section = v1.v5._device_section_from_dsn(v1.read_internal_file(dci_manual, "ROOT.DSN"))
    dcv = _family_chunks(dcv_section)
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
        raise RuntimeError(f"Missing device families in donors: {missing}")
    return b"".join(required[name] for name in ("CAP", "VSOURCE", "CSOURCE", "REALIND", "RESISTOR")) + dci_section[-4:]


def _case_definitions_v4() -> list[Any]:
    cases: list[Any] = []
    for case in v1._case_definitions():
        sources = []
        for source_index, source in enumerate(case.sources, start=1):
            visible_value = source.visible_value if len(source.visible_value) == 3 else "10V"
            sources.append(replace(source, ref=f"V{source_index}", visible_value=visible_value))
        cases.append(
            replace(
                case,
                case_id=case.case_id.replace("DCMS_V1", "DCMS_V4"),
                sources=tuple(sources),
                description=case.description + " V4 uses V-style refs and clean ordered device metadata.",
            )
        )
    return cases


def _write_case_v4(
    case_id: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    case_dir = v1.TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = v1.v5._build_dsn_with_devices(
        v1.read_internal_file(base_project, "ROOT.DSN"),
        v1.read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
        devices,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base_project, "PROJECT.XML"), v1.PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    v1.write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    issues = v1.v5.rcl._scan_wire_issues(object_chunk)
    if v1.rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if object_chunk.count(marker):
            issues.append(f"source-net case unexpectedly contains {marker.decode('ascii')}")
    for label in (b"\x02V0", b"\x02G0"):
        if label in object_chunk:
            issues.append(f"source-net case still contains terminal label {label[1:].decode('ascii')}")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_mixed_sources_v4_not_locked",
        "output": str(output_path.relative_to(v1.OUT_ROOT)),
        "source_count": input_payload.get("source_count"),
        "rcl_component_count": input_payload.get("rcl_component_count", 0),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": v1.v5._marker_counts(object_chunk),
        "device_marker_counts": v1.v5._marker_counts(devices),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            chunk_path.name: _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "devices": _sha256_bytes(devices),
        },
        "input": input_payload,
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used_v4.py")
    return manifest


def _write_source_only_control(
    case_id: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    source_donor_4x: Path,
    devices: bytes,
    sources: tuple[Any, ...],
    intended_values: dict[str, str],
) -> dict[str, Any]:
    source_block, source_rows = v1._source_block(sources, source_donor_4x, 1)
    object_chunk = bytearray(b"\x00" + source_block)
    object_chunk[-1] = 0xFF
    input_payload = {
        "control": "source_only_mixed_voltage_current",
        "source_count": len(source_rows),
        "rcl_component_count": 0,
        "intended_values": intended_values,
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
    }
    item = _write_case_v4(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=bytes(object_chunk),
        cdb=v1._build_cdb([], source_rows, 1),
        devices=devices,
        input_payload=input_payload,
    )
    item["status"] = "temporary_dc_mixed_sources_v4_source_only_control_not_locked"
    item["strict_v4_rule"] = "archived 4x DCV source units; V-style refs; clean ordered CAP/VSOURCE/CSOURCE/REALIND/RESISTOR device section"
    return item


def _patch_generated_case_manifest(item: dict[str, Any]) -> dict[str, Any]:
    item["status"] = "temporary_dc_mixed_sources_v4_vrefs_clean_devices_not_locked"
    item["strict_v4_rule"] = (
        "archived 4x DCV source units, V-style refs for all source objects, "
        "passive generated-source CDB pin maps, clean ordered mixed source device section"
    )
    case_dir = v1.TEST_BATCH / item["case_id"]
    manifest_path = case_dir / "manifest.json"
    if manifest_path.exists():
        manifest_path.write_text(json.dumps(item, indent=2) + "\n", encoding="utf-8")
    shutil.copy(Path(__file__), case_dir / "generation_code_used_v4.py")
    return item


def main() -> int:
    if v1.OUT_ROOT.exists():
        shutil.rmtree(v1.OUT_ROOT)
    v1.TEST_BATCH.mkdir(parents=True)
    donors = _copy_archived_donors()

    registry = v1.FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v1.v5.rcl._load_rcl_unit_templates(rcl_donor)

    devices = _ordered_device_section(donors["dcv_manual_combined"], donors["dci_manual_testing"])

    actual_source_control = (
        v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
        v1.SourcePlan("dc_current", "V2", "2A", "02A", "D1"),
    )
    strict_source_control = (
        v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
        v1.SourcePlan("dc_current", "V2", "10V", "10V", "D1"),
    )
    cases: list[dict[str, Any]] = [
        _write_source_only_control(
            "DCMS_V4_T00A_SOURCE_ONLY_ACTUAL_CURRENT_VALUE",
            "Control: source-only VSOURCE plus CSOURCE using actual 2A current value and V-style refs.",
            base_project=base_project,
            donor_project=donors["dci_manual_testing"],
            source_donor_4x=donors["4x_dc_voltage_10v"],
            devices=devices,
            sources=actual_source_control,
            intended_values={"V1": "12V", "V2": "2A"},
        ),
        _write_source_only_control(
            "DCMS_V4_T00B_SOURCE_ONLY_STRICT_ACCEPTED_CURRENT_IDENTITY",
            "Control: source-only VSOURCE plus CSOURCE, but current source keeps accepted V2/10V identity.",
            base_project=base_project,
            donor_project=donors["dci_manual_testing"],
            source_donor_4x=donors["4x_dc_voltage_10v"],
            devices=devices,
            sources=strict_source_control,
            intended_values={"V1": "12V", "V2": "2A"},
        ),
    ]

    for item in _case_definitions_v4():
        cases.append(
            _patch_generated_case_manifest(
                v1._make_case(
                    item,
                    templates=templates,
                    base_project=base_project,
                    donor_project=donors["dci_manual_testing"],
                    source_donor_4x=donors["4x_dc_voltage_10v"],
                    devices=devices,
                )
            )
        )

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V4_VREFS_CLEAN_DEVICES_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "rejected_evidence": [
            "DC_MIXED_SOURCES_V1_USER_FEEDBACK_ALL_ISIS_DLL_20260604",
            "DC_MIXED_SOURCES_V2_USER_FEEDBACK_ALL_ISIS_DLL_20260604",
        ],
        "method": (
            "Use archived user-made 4x DC voltage source units for unique source suffixes, "
            "but force all source object refs to V-style and rebuild device metadata as "
            "CAP, VSOURCE, CSOURCE, REALIND, RESISTOR. CDB source rows keep the passive "
            "pin map used by the accepted generated DCV/DCI packs."
        ),
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
                "strict_v4_rule": item.get("strict_v4_rule"),
            }
            for item in cases
        ],
    }
    (v1.TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (v1.TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V4_VREFS_CLEAN_DEVICES_TEMP_2026_06_04\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT00A/T00B isolate mixed-source objects before R/C/L body insertion. "
        "If T00A works, test T01-T05. If T00A fails but T00B works, the current-source value mutation is unsafe.\n",
        encoding="utf-8",
    )
    archive = shutil.make_archive(str(v1.ARCHIVE_BASE), "zip", v1.OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
