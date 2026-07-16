"""Generate DC-voltage 6/21 cases with the V6 accepted source-first method.

V6 user feedback:

* T00, T01, T03, T05, and T06 opened.
* T02 failed with VGC/VG... dll, so V5-style patched source suffixes are bad.
* T04 failed with VGC/VG... dll, so source-last insertion is bad.

V7 therefore uses only source-first layouts and preserves donor/manual source
suffix/link bytes. It tests the requested 6-component and corrected 21-rule
mixed R/C/L circuits with a DC-voltage source on DV/D0.
"""

from __future__ import annotations

import hashlib
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

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_21_case, mixed_rcl_6_case  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_sources_v7_accepted_source_first_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_SOURCES_V7_ACCEPTED_SOURCE_FIRST_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DC_SOURCES_V7_ACCEPTED_SOURCE_FIRST_TEST_BATCH"
V5_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"


def _load_v5() -> Any:
    spec = importlib.util.spec_from_file_location("dc_sources_v5_for_v7", V5_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V5 helper module from {V5_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v5 = _load_v5()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "manual_combined_testing": v5.USER_COMBINED_DONOR,
        "dc_voltage_01_default_10v": v5.USER_DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj",
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _patch_source_global_id_only(source_record: bytes, global_id: int) -> bytes:
    out = bytearray(source_record)
    model_pos = out.rfind(b"VSOURCE")
    if model_pos < 0:
        raise RuntimeError("VSOURCE not found in source record.")
    body_coord = model_pos + len(b"VSOURCE")
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    return bytes(out)


def _standalone_source_block_preserve_suffix(source_donor: Path, *, global_id: int) -> bytes:
    chunk = v5._object_chunk(source_donor)
    body = chunk[1:]
    output = body[:104]
    input_term = body[104:207]
    source = _patch_source_global_id_only(body[207:551], global_id)
    wire1 = body[551:601]
    wire2_nonfinal = body[601:651][:-1]
    return output + input_term + source + wire1 + wire2_nonfinal


def _manual_source_block_no_anchor(manual_chunk: bytes, *, global_id: int) -> bytes:
    block = bytearray(manual_chunk[2290:2940])
    source_start = 104 + 103
    source_end = source_start + 344
    block[source_start:source_end] = _patch_source_global_id_only(bytes(block[source_start:source_end]), global_id)
    return bytes(block)


def _map_groups_to_source_nets(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    groups = []
    for item in payload["groups"]:
        start = "DV" if item["start"] == "V0" else "D0" if item["start"] == "G0" else item["start"]
        end = "DV" if item["end"] == "V0" else "D0" if item["end"] == "G0" else item["end"]
        groups.append((item["mode"], start, end))
    return groups


def _source_first_chunk(source_block: bytes, source_net_chunk: bytes) -> bytes:
    body = source_net_chunk[1:]
    out = bytearray(b"\x00" + source_block + body)
    out[-1] = 0xFF
    return bytes(out)


def _write_case(
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
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = v5._build_dsn_with_devices(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    issues = v5.rcl._scan_wire_issues(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    if object_chunk.count(b"$TERPOWER"):
        issues.append("source-net case unexpectedly contains $TERPOWER")
    if object_chunk.count(b"$TERGROUND"):
        issues.append("source-net case unexpectedly contains $TERGROUND")
    for label in (b"\x02V0", b"\x02G0"):
        if label in object_chunk:
            issues.append(f"source-net case still contains terminal label {label[1:].decode('ascii')}")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_source_v7_accepted_source_first_not_locked",
        "output": str(output_path.relative_to(OUT_ROOT)),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": v5._marker_counts(object_chunk),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            chunk_path.name: _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
        },
        "input": input_payload,
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _make_source_case(
    *,
    case_id: str,
    description: str,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_donor: Path,
    manual_chunk: bytes,
    manual_devices: bytes,
    source_block_kind: str,
) -> dict[str, Any]:
    groups = _map_groups_to_source_nets(payload)
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, groups)
    source_id = len(specs) + 1
    source = v5.SourceSpec(idx=source_id, ref="V1", value="10V", positive="DV", negative="D0", x=-10_160_000, y=2_032_000)
    if source_block_kind == "standalone_preserve_suffix":
        source_block = _standalone_source_block_preserve_suffix(source_donor, global_id=source_id)
    elif source_block_kind == "manual_source_block":
        source_block = _manual_source_block_no_anchor(manual_chunk, global_id=source_id)
    else:
        raise ValueError(source_block_kind)

    input_payload = {
        "base_payload_name": payload["project"]["name"],
        "source_block_kind": source_block_kind,
        "source_position": "before_rcl",
        "source": source.__dict__,
        "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in groups],
        "rcl_counts": rcl_counts,
        "topology": topology,
    }
    return _write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=_source_first_chunk(source_block, source_net_chunk),
        cdb=v5._build_cdb(specs, [source], "before_rcl"),
        devices=manual_devices,
        input_payload=input_payload,
    )


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)
    donors = _copy_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v5.rcl._load_rcl_unit_templates(rcl_donor)

    manual = donors["manual_combined_testing"]
    source_donor = donors["dc_voltage_01_default_10v"]
    manual_chunk = v5._object_chunk(manual)
    manual_devices = v5._device_section_from_dsn(read_internal_file(manual, "ROOT.DSN"))

    six_payload = mixed_rcl_6_case()
    twenty_one_payload = mixed_rcl_21_case()

    cases = [
        _make_source_case(
            case_id="DCS_V7_T01_DCV_6_COMPONENTS_SOURCE_FIRST",
            description="Six-component mixed R/C/L circuit with accepted source-first DC-voltage source block.",
            payload=six_payload,
            templates=templates,
            base_project=base_project,
            donor_project=manual,
            source_donor=source_donor,
            manual_chunk=manual_chunk,
            manual_devices=manual_devices,
            source_block_kind="standalone_preserve_suffix",
        ),
        _make_source_case(
            case_id="DCS_V7_T02_DCV_21_RULE_SOURCE_FIRST",
            description="Corrected 21-rule mixed R/C/L circuit with accepted source-first DC-voltage source block.",
            payload=twenty_one_payload,
            templates=templates,
            base_project=base_project,
            donor_project=manual,
            source_donor=source_donor,
            manual_chunk=manual_chunk,
            manual_devices=manual_devices,
            source_block_kind="standalone_preserve_suffix",
        ),
        _make_source_case(
            case_id="DCS_V7_T03_DCV_21_RULE_MANUAL_SOURCE_BLOCK",
            description="Corrected 21-rule mixed R/C/L circuit with source-first manual source block fallback.",
            payload=twenty_one_payload,
            templates=templates,
            base_project=base_project,
            donor_project=manual,
            source_donor=source_donor,
            manual_chunk=manual_chunk,
            manual_devices=manual_devices,
            source_block_kind="manual_source_block",
        ),
    ]

    summary = {
        "batch_id": "DC_SOURCES_V7_ACCEPTED_SOURCE_FIRST_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V6 T02 and T04 failed; workspace files indicate T00/T01/T03/T05/T06 opened.",
        "method": "source first only; preserve standalone/manual source suffix bytes; no V5 patched source suffixes; no source-last insertion",
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
        "DC source V7 accepted source-first confirmation pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT01 is the 6-component source-driven circuit. T02 is the corrected 21-rule source-driven circuit using the V6 T01 method. T03 is a 21-rule fallback using the V6 T03 manual source block method.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
