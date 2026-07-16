"""Generate DC-current source diagnostics using the connected-load donor.

V8 user feedback:

* All 15 DC-voltage source-driven mixed R/C/L cases worked.
* No DC-current source-driven mixed R/C/L cases worked.

The V8 current cases used the standalone current-source donor
``dc_current_01_default``. The user-made current-source-with-resistor-load donor
proves a different connected source shape, so V9 isolates:

* connected-load CSOURCE object block versus standalone CSOURCE object block
* source-first versus source-last CDB ordering
* fixed visible ``I4`` source reference versus ID-matched visible source reference
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_6_case, mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "experiments" / "dc_current_v9_connected_source_diagnostics_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_CURRENT_V9_CONNECTED_SOURCE_DIAGNOSTICS_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DC_CURRENT_V9_CONNECTED_SOURCE_DIAGNOSTICS_TEST_BATCH"
USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
V5_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"


@dataclass(frozen=True)
class SourceSpec:
    idx: int
    ref: str
    value: str
    model: str
    prop_text: bytes


def _load_v5() -> Any:
    spec = importlib.util.spec_from_file_location("dc_sources_v5_for_current_v9", V5_PATH)
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
        "dc_current_01_default": USER_DONOR_ROOT / "dc_current_01_default.pdsprj",
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
    if not sections:
        raise ValueError("At least one device section is required.")
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
        raise ValueError("Only length-preserving two-character visible source refs are supported in V9.")
    old = b"\x02I4"
    new = bytes([2]) + new_ref.encode("ascii")
    if old not in source_record:
        raise RuntimeError("Connected current source record does not contain visible ref I4.")
    return source_record.replace(old, new, 1)


def _connected_source_block(source_donor: Path, *, global_id: int, visible_ref: str = "I4") -> bytes:
    """Return the connected donor's source/terminal/wire block in non-final form."""
    chunk = v5._object_chunk(source_donor)
    if len(chunk) != 1310:
        raise RuntimeError(f"Unexpected connected current donor object chunk length: {len(chunk)}.")
    block = bytearray(chunk[1:655])
    source_start = 207
    source_end = 554
    source = bytes(block[source_start:source_end])
    if visible_ref != "I4":
        source = _patch_visible_source_ref_len2(source, visible_ref)
    source = _patch_source_global_id_only(source, global_id)
    block[source_start:source_end] = source
    return bytes(block)


def _standalone_source_block(source_donor: Path, *, global_id: int) -> bytes:
    """Return the rejected V8 standalone source block for A/B isolation."""
    chunk = v5._object_chunk(source_donor)
    if len(chunk) != 653:
        raise RuntimeError(f"Unexpected standalone current donor object chunk length: {len(chunk)}.")
    b0, b1, b2, b3, b4, b5 = (1, 104, 208, 552, 602, 653)
    source = _patch_source_global_id_only(chunk[b2:b3], global_id)
    return chunk[b0:b1] + chunk[b1:b2] + source + chunk[b3:b4] + chunk[b4:b5][:-1]


def _map_groups_to_current_nets(payload: dict[str, Any]) -> list[tuple[str, str, str]]:
    groups = []
    for item in payload["groups"]:
        start = "DI" if item["start"] == "V0" else "I0" if item["start"] == "G0" else item["start"]
        end = "DI" if item["end"] == "V0" else "I0" if item["end"] == "G0" else item["end"]
        groups.append((item["mode"], start, end))
    return groups


def _build_cdb(rcl_specs: list[Any], source: SourceSpec | None, source_position: Literal["before_rcl", "after_rcl"]) -> bytes:
    ordered: list[Any] = list(rcl_specs)
    if source is not None and source_position == "before_rcl":
        ordered = [source, *ordered]
    elif source is not None:
        ordered = [*ordered, source]

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


def _source_first_chunk(source_block: bytes, source_net_chunk: bytes) -> bytes:
    out = bytearray(b"\x00" + source_block + source_net_chunk[1:])
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
        "status": "temporary_dc_current_v9_connected_source_diagnostics_not_locked",
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


def _make_current_case(
    *,
    case_id: str,
    description: str,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_donor: Path,
    devices: bytes,
    source_block_kind: Literal["connected_i4", "connected_id_ref", "standalone_i1"],
    cdb_source_position: Literal["before_rcl", "after_rcl"],
    source_ref_mode: Literal["fixed_i4", "id_ref", "standalone_i1"],
    source_value: str,
) -> dict[str, Any]:
    groups = _map_groups_to_current_nets(payload)
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, groups)
    source_id = len(specs) + 1

    if source_ref_mode == "fixed_i4":
        source_ref = "I4"
    elif source_ref_mode == "id_ref":
        source_ref = f"I{source_id}"
    else:
        source_ref = "I1"

    if source_block_kind == "connected_i4":
        source_block = _connected_source_block(source_donor, global_id=source_id, visible_ref="I4")
    elif source_block_kind == "connected_id_ref":
        source_block = _connected_source_block(source_donor, global_id=source_id, visible_ref=source_ref)
    else:
        source_block = _standalone_source_block(source_donor, global_id=source_id)

    source = SourceSpec(
        idx=source_id,
        ref=source_ref,
        value=source_value,
        model="CSOURCE",
        prop_text=b"{PRIMITIVE=ANALOGUE}\n\x00",
    )
    input_payload = {
        "base_payload_name": payload["project"]["name"],
        "source_kind": "dc_current",
        "source_position": "before_rcl",
        "source_block_kind": source_block_kind,
        "cdb_source_position": cdb_source_position,
        "source": {
            "idx": source.idx,
            "ref": source.ref,
            "value": source.value,
            "model": source.model,
            "positive_net": "DI",
            "negative_net": "I0",
        },
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
        cdb=_build_cdb(specs, source, cdb_source_position),
        devices=devices,
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

    standalone_current = donors["dc_current_01_default"]
    connected_current = donors["dc_current_03_resistor_load"]
    rcl_devices = v5._device_section_from_dsn(read_internal_file(rcl_donor, "ROOT.DSN"))
    standalone_current_devices = v5._device_section_from_dsn(read_internal_file(standalone_current, "ROOT.DSN"))
    connected_current_devices = v5._device_section_from_dsn(read_internal_file(connected_current, "ROOT.DSN"))
    rcl_plus_standalone_current_devices = _combine_device_sections(rcl_devices, standalone_current_devices)
    rcl_plus_connected_current_devices = _combine_device_sections(rcl_devices, connected_current_devices)

    six_payload = mixed_rcl_6_case()
    simple_payload = mixed_rcl_15_cases()[0]

    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, _map_groups_to_current_nets(simple_payload))
    source_net_no_source_input = {
        "base_payload_name": simple_payload["project"]["name"],
        "source_kind": "dc_current",
        "source_position": "none_control",
        "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in _map_groups_to_current_nets(simple_payload)],
        "rcl_counts": rcl_counts,
        "topology": topology,
    }

    cases: list[dict[str, Any]] = []
    cases.append(
        _write_case(
            "DCI_V9_T00_STANDALONE_CURRENT_DONOR_IN_E001",
            "Control: user-made standalone DC current source donor transplanted into E001.",
            base_project=base_project,
            donor_project=standalone_current,
            object_chunk=v5._object_chunk(standalone_current),
            cdb=read_internal_file(standalone_current, "ROOT.CDB"),
            devices=standalone_current_devices,
            input_payload={"control": "standalone_current_donor_transplant"},
        )
    )
    cases.append(
        _write_case(
            "DCI_V9_T01_CURRENT_RESISTOR_LOAD_DONOR_IN_E001",
            "Control: user-made DC current source plus resistor load donor transplanted into E001.",
            base_project=base_project,
            donor_project=connected_current,
            object_chunk=v5._object_chunk(connected_current),
            cdb=read_internal_file(connected_current, "ROOT.CDB"),
            devices=connected_current_devices,
            input_payload={"control": "current_resistor_load_donor_transplant"},
        )
    )
    cases.append(
        _write_case(
            "DCI_V9_T02_SOURCE_NET_SIMPLE_NO_SOURCE_CONTROL",
            "Control: generated simple source-net R/C/L body using DI/I0, without a current source object.",
            base_project=base_project,
            donor_project=connected_current,
            object_chunk=source_net_chunk,
            cdb=_build_cdb(specs, None, "after_rcl"),
            devices=rcl_devices,
            input_payload=source_net_no_source_input,
        )
    )
    cases.append(
        _make_current_case(
            case_id="DCI_V9_T03_SIMPLE_CONNECTED_I4_CDB_AFTER",
            description="Simple generated R/C/L case using connected CSOURCE block, fixed visible I4 ref, 500mA value, and source-last CDB order.",
            payload=simple_payload,
            templates=templates,
            base_project=base_project,
            donor_project=connected_current,
            source_donor=connected_current,
            devices=rcl_plus_connected_current_devices,
            source_block_kind="connected_i4",
            cdb_source_position="after_rcl",
            source_ref_mode="fixed_i4",
            source_value="500mA",
        )
    )
    cases.append(
        _make_current_case(
            case_id="DCI_V9_T04_SIMPLE_CONNECTED_I4_CDB_BEFORE",
            description="Simple generated R/C/L case using connected CSOURCE block and fixed I4 ref, but source-first CDB order.",
            payload=simple_payload,
            templates=templates,
            base_project=base_project,
            donor_project=connected_current,
            source_donor=connected_current,
            devices=rcl_plus_connected_current_devices,
            source_block_kind="connected_i4",
            cdb_source_position="before_rcl",
            source_ref_mode="fixed_i4",
            source_value="500mA",
        )
    )
    cases.append(
        _make_current_case(
            case_id="DCI_V9_T05_SIMPLE_STANDALONE_I1_CDB_AFTER",
            description="A/B case: V8 standalone CSOURCE block retained, but CDB changed to source-last order.",
            payload=simple_payload,
            templates=templates,
            base_project=base_project,
            donor_project=standalone_current,
            source_donor=standalone_current,
            devices=rcl_plus_standalone_current_devices,
            source_block_kind="standalone_i1",
            cdb_source_position="after_rcl",
            source_ref_mode="standalone_i1",
            source_value="1A",
        )
    )
    cases.append(
        _make_current_case(
            case_id="DCI_V9_T06_6_COMPONENT_CONNECTED_I4_CDB_AFTER",
            description="Six-component generated R/C/L case using connected CSOURCE block, fixed visible I4 ref, 500mA value, and source-last CDB order.",
            payload=six_payload,
            templates=templates,
            base_project=base_project,
            donor_project=connected_current,
            source_donor=connected_current,
            devices=rcl_plus_connected_current_devices,
            source_block_kind="connected_i4",
            cdb_source_position="after_rcl",
            source_ref_mode="fixed_i4",
            source_value="500mA",
        )
    )
    cases.append(
        _make_current_case(
            case_id="DCI_V9_T07_6_COMPONENT_CONNECTED_IDREF_CDB_AFTER",
            description="Six-component generated R/C/L case using connected CSOURCE block with visible source ref patched to its global ID and source-last CDB order.",
            payload=six_payload,
            templates=templates,
            base_project=base_project,
            donor_project=connected_current,
            source_donor=connected_current,
            devices=rcl_plus_connected_current_devices,
            source_block_kind="connected_id_ref",
            cdb_source_position="after_rcl",
            source_ref_mode="id_ref",
            source_value="500mA",
        )
    )

    summary = {
        "batch_id": "DC_CURRENT_V9_CONNECTED_SOURCE_DIAGNOSTICS_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V8 user feedback: all DCV worked; no DCI worked.",
        "method": "DC-current diagnostics from connected current-load donor; positive output DI; negative input I0; no power/ground bridge.",
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
        "DC current V9 connected-source diagnostic pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT03 is the primary fix candidate. T04 isolates CDB order. T05 isolates the rejected V8 standalone current-source block. T06/T07 check the 6-component scale and visible source-reference behavior.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
