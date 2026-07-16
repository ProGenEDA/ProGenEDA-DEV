"""Generate focused DC-voltage source block diagnostics after V5 feedback.

User feedback for V5:

* T00 manual combined donor in E001 worked.
* T01 manual label-only mutation worked.
* T02 generated R/C/L source-net body with no source worked.
* T03/T04 generated source + generated R/C/L failed with VGCVC/VG... dll.

This narrows the fault to the generated source block or its CDB/source link
records. V6 tests only that boundary.
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
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_sources_v6_source_block_fix_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_SOURCES_V6_SOURCE_BLOCK_FIX_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DC_SOURCES_V6_SOURCE_BLOCK_FIX_TEST_BATCH"
V5_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"


def _load_v5() -> Any:
    spec = importlib.util.spec_from_file_location("dc_sources_v5_for_v6", V5_PATH)
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


def _standalone_source_block_preserve_suffix(*, global_id: int, nonfinal_trim: bool) -> bytes:
    chunk = v5._object_chunk(DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj")
    body = chunk[1:]
    output = body[:104]
    input_term = body[104:207]
    source = _patch_source_global_id_only(body[207:551], global_id)
    wire1 = body[551:601]
    wire2 = body[601:651]
    if nonfinal_trim:
        wire2 = wire2[:-1]
    return output + input_term + source + wire1 + wire2


def _v5_source_block_with_trim(source: Any) -> bytes:
    # V5's failed T03 used this source unit with patched resistor-style suffixes
    # but left the non-final second source wire at 50 bytes. Trim only that byte.
    block = v5._source_unit(source, final=False)
    return block[:-1]


def _manual_source_block_no_anchor(manual_chunk: bytes, *, final: bool) -> bytes:
    # Manual source region:
    # 2187..2290 extra DV input anchor
    # 2290..2940 output DV, input D0, VSOURCE, wire1, 49-byte non-final wire2
    block = manual_chunk[2290:2940]
    if final:
        block += b"\xff"
    return block


def _manual_source_block_with_anchor(manual_chunk: bytes) -> bytes:
    # Includes the extra ordinary DV input anchor observed before the source
    # output/input pair in the working manual combined donor.
    return manual_chunk[2187:2940]


def _manual_combined_cdb() -> bytes:
    return read_internal_file(DONOR_ROOT / "manual_combined_testing.pdsprj", "ROOT.CDB")


def _write_case(
    case_id: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any] | None = None,
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

    issues = v5.rcl._scan_wire_issues(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    if object_chunk.count(b"$TERPOWER"):
        issues.append("source-net case unexpectedly contains $TERPOWER")
    if object_chunk.count(b"$TERGROUND"):
        issues.append("source-net case unexpectedly contains $TERGROUND")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_source_v6_source_block_fix_not_locked",
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
    }
    if input_payload:
        (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")
        manifest["input"] = input_payload
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


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
    manual_chunk = v5._object_chunk(manual)
    manual_devices = v5._device_section_from_dsn(read_internal_file(manual, "ROOT.DSN"))

    groups = [("RCL", "DV", "D0"), ("RC", "DV", "D0"), ("C", "DV", "D0")]
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, groups)
    rcl_body = source_net_chunk[1:]
    source = v5.SourceSpec(idx=7, ref="V1", value="10V", positive="DV", negative="D0", x=-10_160_000, y=2_032_000)
    cdb_source_first = v5._build_cdb(specs, [source], "before_rcl")
    cdb_source_last = v5._build_cdb(specs, [source], "after_rcl")
    rcl_only_cdb = v5.rcl.build_cdb(specs)
    manual_cdb = _manual_combined_cdb()

    def source_first(block: bytes) -> bytes:
        out = bytearray(b"\x00" + block + rcl_body)
        out[-1] = 0xFF
        return bytes(out)

    def source_last(block: bytes) -> bytes:
        body = bytearray(rcl_body)
        body[-1] = 0x00
        out = bytearray(b"\x00" + body + block)
        out[-1] = 0xFF
        return bytes(out)

    cases: list[dict[str, Any]] = []
    cases.append(
        _write_case(
            "DCS_V6_T00_RCL_SOURCE_NET_NO_SOURCE_CONTROL",
            "Regenerated T02-style source-net RCL body with no source. This already worked in V5 and verifies the V6 packer path.",
            base_project=base_project,
            donor_project=rcl_donor,
            object_chunk=source_net_chunk,
            cdb=rcl_only_cdb,
            devices=v5._device_section_from_dsn(read_internal_file(rcl_donor, "ROOT.DSN")),
            input_payload={"groups": groups, "source": None, "rcl_counts": rcl_counts, "topology": topology},
        )
    )
    cases.append(
        _write_case(
            "DCS_V6_T01_SOURCE_FIRST_PRESERVE_SUFFIX_TRIM49",
            "Source first using standalone source donor terminal/source suffixes unchanged, only source global ID changed to 7, and non-final second source wire trimmed to 49 bytes.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=source_first(_standalone_source_block_preserve_suffix(global_id=7, nonfinal_trim=True)),
            cdb=cdb_source_first,
            devices=manual_devices,
            input_payload={"hypothesis": "V5 failed because it changed source link suffixes and kept a 50-byte non-final source wire."},
        )
    )
    cases.append(
        _write_case(
            "DCS_V6_T02_SOURCE_FIRST_V5_SUFFIX_TRIM49",
            "Source first using the V5 patched source suffixes, but with the non-final second source wire trimmed to 49 bytes. Isolates trim from suffix preservation.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=source_first(_v5_source_block_with_trim(source)),
            cdb=cdb_source_first,
            devices=manual_devices,
            input_payload={"hypothesis": "If this works, V5 failed mainly because the non-final source wire was 50 bytes."},
        )
    )
    cases.append(
        _write_case(
            "DCS_V6_T03_SOURCE_FIRST_MANUAL_SOURCE_BLOCK",
            "Source first using the exact manual combined donor source output/input/VSOURCE/wires block, without the extra DV input anchor.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=source_first(_manual_source_block_no_anchor(manual_chunk, final=False)),
            cdb=cdb_source_first,
            devices=manual_devices,
            input_payload={"hypothesis": "If T01/T02 fail but this works, the standalone source donor block is not safe in mixed source-net projects."},
        )
    )
    cases.append(
        _write_case(
            "DCS_V6_T04_SOURCE_LAST_MANUAL_SOURCE_BLOCK",
            "Generated RCL body first, then manual source output/input/VSOURCE/wires block made final by appending FF.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=source_last(_manual_source_block_no_anchor(manual_chunk, final=True)),
            cdb=cdb_source_last,
            devices=manual_devices,
            input_payload={"hypothesis": "Tests whether source-last is safe when source suffixes come from the working manual combined donor."},
        )
    )
    cases.append(
        _write_case(
            "DCS_V6_T05_SOURCE_FIRST_MANUAL_BLOCK_MANUAL_CDB",
            "Same as T03 but with the full manual combined donor ROOT.CDB. Isolates generated CDB from source object bytes.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=source_first(_manual_source_block_no_anchor(manual_chunk, final=False)),
            cdb=manual_cdb,
            devices=manual_devices,
            input_payload={"hypothesis": "If T03 fails and T05 works, source CDB composition is the active fault."},
        )
    )
    cases.append(
        _write_case(
            "DCS_V6_T06_SOURCE_FIRST_MANUAL_WITH_DV_ANCHOR",
            "Source first with the extra ordinary DV input anchor observed directly before the source in the working manual combined donor.",
            base_project=base_project,
            donor_project=manual,
            object_chunk=source_first(_manual_source_block_with_anchor(manual_chunk)),
            cdb=manual_cdb,
            devices=manual_devices,
            input_payload={"hypothesis": "Tests whether the extra manual DV input terminal is required as a source-net anchor."},
        )
    )

    summary = {
        "batch_id": "DC_SOURCES_V6_SOURCE_BLOCK_FIX_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V5 T00/T01/T02 worked; V5 T03/T04 failed with VGC/VG... dll.",
        "root_cause_hypotheses": [
            "V5 kept a 50-byte source right-wire record where the working manual donor uses a 49-byte non-final source wire.",
            "V5 changed source terminal/component link suffixes instead of preserving source donor/manual suffixes.",
            "Generated source CDB composition may differ from the manual combined donor CDB.",
            "The working manual donor includes an extra ordinary DV input terminal before the source block.",
        ],
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
        "DC source V6 focused source-block diagnostic pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT00 is the known-good no-source generated RCL control. T01 is the most likely fix: preserve source donor suffixes and trim the non-final source wire to 49 bytes. T02 isolates trim only. T03-T06 use source bytes and CDB from the working manual combined donor.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
