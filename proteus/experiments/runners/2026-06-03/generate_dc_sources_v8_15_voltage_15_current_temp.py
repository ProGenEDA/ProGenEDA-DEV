"""Generate 15 DC-voltage and 15 DC-current source-driven R/C/L topologies.

This is temp-only source work. It applies the user-confirmed V7 source-first
method to the 15 locked mixed R/C/L topology examples.

Source net conventions:

* DC voltage source: positive ``DV`` output terminal, negative ``D0`` input terminal.
* DC current source: positive ``DI`` output terminal, negative ``I0`` input terminal.

Do not promote until the user confirms Proteus open/netlist behavior.
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

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_15_cases  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "dc_sources_v8_15_voltage_15_current_temp_2026_06_03"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "DC_SOURCES_V8_15_VOLTAGE_15_CURRENT_TEMP_2026_06_03"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DC_SOURCES_V8_15_VOLTAGE_15_CURRENT_TEST_BATCH"
USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
USER_COMBINED_DONOR = Path(r"C:\Users\tahab\Downloads\testing.pdsprj")
V5_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"


@dataclass(frozen=True)
class SourceSpec:
    idx: int
    ref: str
    value: str
    model: str
    positive: str
    negative: str
    prop_text: bytes


@dataclass(frozen=True)
class SourceKind:
    kind: Literal["dc_voltage", "dc_current"]
    case_prefix: str
    label: str
    donor_name: str
    source_ref: str
    source_value: str
    model: str
    positive_net: str
    negative_net: str
    prop_text: bytes
    split_bounds: tuple[int, int, int, int, int, int]


DC_VOLTAGE = SourceKind(
    kind="dc_voltage",
    case_prefix="DCV",
    label="DC voltage",
    donor_name="dc_voltage_01_default_10v",
    source_ref="V1",
    source_value="10V",
    model="VSOURCE",
    positive_net="DV",
    negative_net="D0",
    prop_text=b"{PRIMITIVE=ANALOG}\n\x00",
    split_bounds=(1, 105, 208, 552, 602, 652),
)

DC_CURRENT = SourceKind(
    kind="dc_current",
    case_prefix="DCI",
    label="DC current",
    donor_name="dc_current_01_default",
    source_ref="I1",
    source_value="1A",
    model="CSOURCE",
    positive_net="DI",
    negative_net="I0",
    prop_text=b"{PRIMITIVE=ANALOGUE}\n\x00",
    split_bounds=(1, 104, 208, 552, 602, 653),
)


def _load_v5() -> Any:
    spec = importlib.util.spec_from_file_location("dc_sources_v5_for_v8", V5_PATH)
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
        "manual_combined_testing": USER_COMBINED_DONOR,
        "dc_voltage_01_default_10v": USER_DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj",
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


def _patch_source_global_id_only(source_record: bytes, model: str, global_id: int) -> bytes:
    out = bytearray(source_record)
    model_pos = out.rfind(model.encode("ascii"))
    if model_pos < 0:
        raise RuntimeError(f"{model} not found in source record.")
    body_coord = model_pos + len(model)
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    return bytes(out)


def _source_block_preserve_suffix(kind: SourceKind, donor: Path, *, global_id: int) -> bytes:
    chunk = v5._object_chunk(donor)
    b0, b1, b2, b3, b4, b5 = kind.split_bounds
    if len(chunk) != b5:
        raise RuntimeError(f"{kind.donor_name} object chunk length {len(chunk)} != expected {b5}.")
    terminal_a = chunk[b0:b1]
    terminal_b = chunk[b1:b2]
    source = _patch_source_global_id_only(chunk[b2:b3], kind.model, global_id)
    wire1 = chunk[b3:b4]
    wire2_nonfinal = chunk[b4:b5][:-1]
    return terminal_a + terminal_b + source + wire1 + wire2_nonfinal


def _map_groups_to_source_nets(payload: dict[str, Any], kind: SourceKind) -> list[tuple[str, str, str]]:
    groups = []
    for item in payload["groups"]:
        start = kind.positive_net if item["start"] == "V0" else kind.negative_net if item["start"] == "G0" else item["start"]
        end = kind.positive_net if item["end"] == "V0" else kind.negative_net if item["end"] == "G0" else item["end"]
        groups.append((item["mode"], start, end))
    return groups


def _build_cdb(rcl_specs: list[Any], source: SourceSpec) -> bytes:
    ordered: list[Any] = [source, *rcl_specs]
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
        "status": "temporary_dc_source_v8_15_voltage_15_current_not_locked",
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


def _case_suffix(index: int, payload_name: str) -> str:
    parts = payload_name.split("_")
    return f"T{index:02d}_" + "_".join(parts[4:])


def _make_source_case(
    *,
    index: int,
    kind: SourceKind,
    payload: dict[str, Any],
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_donor: Path,
    devices: bytes,
) -> dict[str, Any]:
    groups = _map_groups_to_source_nets(payload, kind)
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, groups)
    source_id = len(specs) + 1
    source = SourceSpec(
        idx=source_id,
        ref=kind.source_ref,
        value=kind.source_value,
        model=kind.model,
        positive=kind.positive_net,
        negative=kind.negative_net,
        prop_text=kind.prop_text,
    )
    source_block = _source_block_preserve_suffix(kind, source_donor, global_id=source_id)
    case_id = f"DCS_V8_{kind.case_prefix}_{_case_suffix(index, payload['project']['name'])}"
    description = f"{kind.label} source-driven {payload['metadata']['description']}"
    input_payload = {
        "base_payload_name": payload["project"]["name"],
        "source_kind": kind.kind,
        "source_position": "before_rcl",
        "source": {
            "idx": source.idx,
            "ref": source.ref,
            "value": source.value,
            "model": source.model,
            "positive_net": kind.positive_net,
            "negative_net": kind.negative_net,
            "prop_text": source.prop_text.decode("ascii", errors="replace").rstrip("\x00"),
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
        cdb=_build_cdb(specs, source),
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

    voltage_devices = v5._device_section_from_dsn(read_internal_file(donors["manual_combined_testing"], "ROOT.DSN"))
    rcl_devices = v5._device_section_from_dsn(read_internal_file(rcl_donor, "ROOT.DSN"))
    current_devices = v5._device_section_from_dsn(read_internal_file(donors["dc_current_01_default"], "ROOT.DSN"))
    combined_current_devices = _combine_device_sections(rcl_devices, current_devices)

    cases: list[dict[str, Any]] = []
    payloads = mixed_rcl_15_cases()
    for index, payload in enumerate(payloads, start=1):
        cases.append(
            _make_source_case(
                index=index,
                kind=DC_VOLTAGE,
                payload=payload,
                templates=templates,
                base_project=base_project,
                donor_project=donors["manual_combined_testing"],
                source_donor=donors[DC_VOLTAGE.donor_name],
                devices=voltage_devices,
            )
        )
    for index, payload in enumerate(payloads, start=1):
        cases.append(
            _make_source_case(
                index=index,
                kind=DC_CURRENT,
                payload=payload,
                templates=templates,
                base_project=base_project,
                donor_project=donors["dc_current_01_default"],
                source_donor=donors[DC_CURRENT.donor_name],
                devices=combined_current_devices,
            )
        )

    summary = {
        "batch_id": "DC_SOURCES_V8_15_VOLTAGE_15_CURRENT_STATIC_20260603",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "V7 6-component and corrected 21-rule DC-voltage source-first cases worked.",
        "method": "source first only; preserve standalone source suffix bytes; voltage uses DV/D0; current uses DI/I0",
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
        "DC source V8 15 voltage + 15 current topology pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT01-T15 are DC-voltage source-driven circuits using DV/D0. T16-T30 are DC-current source-driven circuits using DI/I0.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
