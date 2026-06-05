"""Generate DC-current diagnostics with donor anchor terminals after CSOURCE.

V9 feedback:

* T03 and onward failed with ISIS/VG... dll errors.
* T00/T01/T02 were not reported as failing, so the donor controls and
  generated DI/I0 source-net body are still treated as safe controls.

The connected current-load donor places an extra load-side terminal pair
immediately after the source block:

* DI as $TERINPUT
* I0 as $TEROUTPUT

V10 preserves that donor terminal pair before appending generated body records.
It also isolates a resistor-only load before trying mixed R/C/L again.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_6_case, mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "experiments" / "dc_current_v10_anchor_terminals_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_CURRENT_V10_ANCHOR_TERMINALS_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DCI_V10_TEST_BATCH"
USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
V5_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"


@dataclass(frozen=True)
class SourceSpec:
    idx: int
    ref: str
    value: str
    model: str = "CSOURCE"
    prop_text: bytes = b"{PRIMITIVE=ANALOGUE}\n\x00"


def _load_v5() -> Any:
    spec = importlib.util.spec_from_file_location("dc_sources_v5_for_current_v10", V5_PATH)
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


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(4 + len(value)) + value


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "dc_current_03_resistor_load": USER_DONOR_ROOT / "dc_current_03_resistor_load.pdsprj",
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _combine_device_sections(*sections: bytes) -> bytes:
    out = bytearray()
    for section in sections[:-1]:
        out += section[:-4]
    out += sections[-1]
    return bytes(out)


def _patch_source_global_id_only(source_record: bytes, global_id: int) -> bytes:
    out = bytearray(source_record)
    model_pos = out.rfind(b"CSOURCE")
    if model_pos < 0:
        raise RuntimeError("CSOURCE not found in source record.")
    body_coord = model_pos + len(b"CSOURCE")
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    return bytes(out)


def _patch_visible_source_ref_len2(source_record: bytes, new_ref: str) -> bytes:
    if len(new_ref.encode("ascii")) != 2:
        raise ValueError("V10 only patches two-character visible source refs.")
    old = b"\x02I4"
    new = bytes([2]) + new_ref.encode("ascii")
    if old not in source_record:
        raise RuntimeError("Connected current source record does not contain visible ref I4.")
    return source_record.replace(old, new, 1)


def _connected_source_block(source_donor: Path, *, global_id: int, visible_ref: str = "I4") -> bytes:
    chunk = v5._object_chunk(source_donor)
    if len(chunk) != 1310:
        raise RuntimeError(f"Unexpected connected current donor chunk length: {len(chunk)}")
    block = bytearray(chunk[1:655])
    source_start = 207
    source_end = 554
    source = bytes(block[source_start:source_end])
    if visible_ref != "I4":
        source = _patch_visible_source_ref_len2(source, visible_ref)
    block[source_start:source_end] = _patch_source_global_id_only(source, global_id)
    return bytes(block)


def _anchor_terminal_pair(source_donor: Path) -> bytes:
    chunk = v5._object_chunk(source_donor)
    if len(chunk) != 1310:
        raise RuntimeError(f"Unexpected connected current donor chunk length: {len(chunk)}")
    anchor = chunk[655:858]
    if anchor.count(b"$TERINPUT") != 1 or anchor.count(b"$TEROUTPUT") != 1:
        raise RuntimeError("Connected current donor anchor pair bounds are wrong.")
    if b"\x02DI" not in anchor or b"\x02I0" not in anchor:
        raise RuntimeError("Connected current donor anchor pair is missing DI/I0 labels.")
    return anchor


def _map_groups_to_current_nets(groups: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
    mapped = []
    for mode, start, end in groups:
        mapped_start = "DI" if start == "V0" else "I0" if start == "G0" else start
        mapped_end = "DI" if end == "V0" else "I0" if end == "G0" else end
        mapped.append((mode, mapped_start, mapped_end))
    return mapped


def _payload_groups(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    return [(item["mode"], item["start"], item["end"]) for item in payload["groups"]]


def _build_cdb(rcl_specs: list[Any], source: SourceSpec) -> bytes:
    ordered: list[Any] = [*rcl_specs, source]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + _enc_str(spec.ref)
        if getattr(spec, "kind", "") == "CAPACITOR":
            out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, SourceSpec):
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str(spec.model) + _enc_str("") + _enc_text(spec.prop_text)
        elif spec.kind == "CAPACITOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(v5.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(v5.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _source_anchor_body_chunk(source_block: bytes, anchor_pair: bytes, source_net_chunk: bytes) -> bytes:
    out = bytearray(b"\x00" + source_block + anchor_pair + source_net_chunk[1:])
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
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if object_chunk.count(marker):
            issues.append(f"source-net case unexpectedly contains {marker.decode('ascii')}")
    for label in (b"\x02V0", b"\x02G0"):
        if label in object_chunk:
            issues.append(f"source-net case still contains terminal label {label[1:].decode('ascii')}")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_current_v10_anchor_terminals_not_locked",
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


def _make_generated_case(
    *,
    case_id: str,
    description: str,
    groups: list[tuple[str, str, str]],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    current_donor: Path,
    devices: bytes,
    source_ref_mode: str = "fixed_i4",
) -> dict[str, Any]:
    mapped_groups = _map_groups_to_current_nets(groups)
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, mapped_groups)
    source_id = len(specs) + 1
    source_ref = "I4" if source_ref_mode == "fixed_i4" else f"I{source_id}"
    source_block = _connected_source_block(current_donor, global_id=source_id, visible_ref=source_ref)
    anchor_pair = _anchor_terminal_pair(current_donor)
    source = SourceSpec(idx=source_id, ref=source_ref, value="500mA")
    return _write_case(
        case_id,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=_source_anchor_body_chunk(source_block, anchor_pair, source_net_chunk),
        cdb=_build_cdb(specs, source),
        devices=devices,
        input_payload={
            "source_kind": "dc_current",
            "source_block": "connected_current_load_donor_chunk_1_655",
            "anchor_pair": "connected_current_load_donor_chunk_655_858",
            "source": {"idx": source.idx, "ref": source.ref, "value": source.value, "model": source.model},
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in mapped_groups],
            "rcl_counts": rcl_counts,
            "topology": topology,
        },
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

    current_donor = donors["dc_current_03_resistor_load"]
    current_devices = v5._device_section_from_dsn(read_internal_file(current_donor, "ROOT.DSN"))
    rcl_devices = v5._device_section_from_dsn(read_internal_file(rcl_donor, "ROOT.DSN"))
    combined_devices = _combine_device_sections(rcl_devices, current_devices)

    simple_payload = mixed_rcl_15_cases()[0]
    six_payload = mixed_rcl_6_case()

    cases: list[dict[str, Any]] = []
    cases.append(
        _write_case(
            "DCI_V10_T00_CONN_DONOR",
            "Control: exact connected current-source plus resistor-load donor transplanted into E001.",
            base_project=base_project,
            donor_project=current_donor,
            object_chunk=v5._object_chunk(current_donor),
            cdb=read_internal_file(current_donor, "ROOT.CDB"),
            devices=current_devices,
            input_payload={"control": "connected_current_resistor_load_donor"},
        )
    )
    cases.append(
        _make_generated_case(
            case_id="DCI_V10_T01_R_ONLY_ANCHOR",
            description="Generated resistor-only load with connected CSOURCE block plus donor DI/I0 anchor terminals.",
            groups=[("R", "V0", "G0")],
            templates=templates,
            base_project=base_project,
            donor_project=current_donor,
            current_donor=current_donor,
            devices=current_devices,
        )
    )
    cases.append(
        _make_generated_case(
            case_id="DCI_V10_T02_RCL_SIMPLE_ANCHOR",
            description="Generated simple R/C/L load with connected CSOURCE block plus donor DI/I0 anchor terminals.",
            groups=_payload_groups(simple_payload),
            templates=templates,
            base_project=base_project,
            donor_project=current_donor,
            current_donor=current_donor,
            devices=combined_devices,
        )
    )
    cases.append(
        _make_generated_case(
            case_id="DCI_V10_T03_6COMP_ANCHOR_I4",
            description="Generated six-component R/C/L load with donor anchor terminals and fixed visible source ref I4.",
            groups=_payload_groups(six_payload),
            templates=templates,
            base_project=base_project,
            donor_project=current_donor,
            current_donor=current_donor,
            devices=combined_devices,
        )
    )
    cases.append(
        _make_generated_case(
            case_id="DCI_V10_T04_6COMP_ANCHOR_ID",
            description="Generated six-component R/C/L load with donor anchor terminals and visible source ref patched to source ID.",
            groups=_payload_groups(six_payload),
            templates=templates,
            base_project=base_project,
            donor_project=current_donor,
            current_donor=current_donor,
            devices=combined_devices,
            source_ref_mode="id_ref",
        )
    )

    summary = {
        "batch_id": "DC_CURRENT_V10_ANCHOR_TERMINALS_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V9 feedback: T03 and onward failed with ISIS/VG dll errors; T00/T01/T02 not reported as failing.",
        "method": "Connected current-load donor source block plus donor DI/I0 anchor terminal pair before generated body.",
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
        "DC current V10 anchor-terminal diagnostic pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT01 isolates a generated resistor-only load. T02 is the first generated R/C/L anchor candidate. T03/T04 check six-component scale and visible source-reference behavior.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
