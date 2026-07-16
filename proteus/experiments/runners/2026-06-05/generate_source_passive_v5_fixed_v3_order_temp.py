"""Generate fixed-order pure DCV2 passive diagnostics from the user-fixed V3 file.

The user-fixed V3 T03 project shows three important differences from generated
V3:

* passive groups appear before source units
* each VSOURCE unit is component-first: source, output terminal, wire, input
  terminal, wire
* ROOT.CDB source rows use +/1 and -/2 pin names with a -1 terminal-side field

This pack keeps the V3 D0-to-G0 high-value reference idea, but uses those
fixed-file source ordering and CDB rules.
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

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import MixedRclGroup  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

V3_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-05" / "generate_source_passive_v3_dcv2_grounded_temp.py"
V5_HELPER_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"
USER_FIXED = Path(r"C:\Users\tahab\Downloads\SRCP_V3_DCV2_T03_R_ONLY_D0_WITH_1G_REF.pdsprj")
BASE_FIXTURE_ID = "e001_empty"
OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "source_passive_v5_fixed_v3_order_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "SOURCE_PASSIVE_V5_FIXED_V3_ORDER_TEMP_2026_06_05"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V5_FIXED_V3_ORDER_TEST_BATCH"
DONOR_ROOT = OUT_ROOT / "donors"


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    visible_values: dict[str, str]
    exact_values: dict[str, str]
    source_values: tuple[str, str]
    diagnostic_rule: str


@dataclass(frozen=True)
class SourcePlan:
    ref: str
    value: str
    positive: str
    negative: str

    @property
    def kind(self) -> str:
        return "dc_voltage"

    @property
    def model(self) -> str:
        return "VSOURCE"

    @property
    def cdb_value(self) -> str:
        return self.value

    @property
    def prop_text(self) -> bytes:
        return b"{PRIMITIVE=ANALOG}\n\x00"


@dataclass(frozen=True)
class SourceRow:
    idx: int
    ref: str
    value: str
    model: str
    prop_text: bytes


@dataclass(frozen=True)
class FixedSourceTemplate:
    old_ref: str
    source_record: bytes
    out_terminal: bytes
    out_wire: bytes
    in_terminal: bytes
    in_wire: bytes
    out_suffix: int
    in_suffix: int


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v3 = _load_module("source_passive_v3_for_v5_fixed_order", V3_PATH)
v5helper = _load_module("dc_sources_v5_helper_for_source_passive_v5", V5_HELPER_PATH)


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(4 + len(value)) + value


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_fixed_donor() -> Path:
    if not USER_FIXED.exists():
        raise FileNotFoundError(USER_FIXED)
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    target = DONOR_ROOT / "user_fixed_v3_t03_d0_1g_ref.pdsprj"
    shutil.copy2(USER_FIXED, target)
    return target


def _fixed_source_templates(fixed_chunk: bytes) -> tuple[FixedSourceTemplate, FixedSourceTemplate]:
    starts = []
    for ref in ("V1", "V2"):
        marker = b"\xff\x02" + ref.encode("ascii")
        pos = fixed_chunk.find(marker)
        if pos < 0:
            raise RuntimeError(f"Fixed donor is missing source ref {ref}.")
        starts.append(pos - 2)
    starts.append(len(fixed_chunk))

    templates: list[FixedSourceTemplate] = []
    for index, ref in enumerate(("V1", "V2")):
        start = starts[index]
        end = starts[index + 1]
        block = fixed_chunk[start:end]
        out_marker = block.find(b"$TEROUTPUT")
        in_marker = block.find(b"$TERINPUT")
        if out_marker < 0 or in_marker < 0:
            raise RuntimeError(f"Fixed source block {ref} does not contain expected terminals.")
        out_start = out_marker - 14
        in_start = in_marker - 14
        if out_start <= 0 or in_start <= out_start:
            raise RuntimeError(f"Fixed source block {ref} terminal order is unexpected.")
        out_end = out_start + rv9.OUT_SIZE
        wire1_end = out_end + rv9.WIRE_SIZE
        in_end = in_start + rv9.IN_SIZE
        if wire1_end != in_start:
            raise RuntimeError(f"Fixed source block {ref} first wire boundary is unexpected.")
        templates.append(
            FixedSourceTemplate(
                old_ref=ref,
                source_record=block[:out_start],
                out_terminal=block[out_start:out_end],
                out_wire=block[out_end:wire1_end],
                in_terminal=block[in_start:in_end],
                in_wire=block[in_end:],
                out_suffix=int.from_bytes(block[out_start + rv9.OUT_SIZE - 4 : out_start + rv9.OUT_SIZE - 2], "little"),
                in_suffix=int.from_bytes(block[in_start + rv9.IN_SIZE - 4 : in_start + rv9.IN_SIZE - 2], "little"),
            )
        )
    return tuple(templates)  # type: ignore[return-value]


def _patch_source_record(template: FixedSourceTemplate, source: SourcePlan, global_id: int) -> bytes:
    return v3.v14._patch_source_record(
        template.source_record,
        old_ref=template.old_ref,
        source=source,
        global_id=global_id,
        old_in_suffix=template.in_suffix,
        new_in_suffix=template.in_suffix,
        old_out_suffix=template.out_suffix,
        new_out_suffix=template.out_suffix,
    )


def _patch_terminal(record: bytes, kind: str, label: str, suffix: int) -> bytes:
    return v3.v14._patch_terminal_label_suffix(record, kind, label, suffix)


def _source_units(
    fixed_templates: tuple[FixedSourceTemplate, FixedSourceTemplate],
    sources: tuple[SourcePlan, SourcePlan],
    first_source_id: int,
) -> tuple[bytes, list[dict[str, Any]]]:
    units: list[bytes] = []
    metadata: list[dict[str, Any]] = []
    for index, (template, source) in enumerate(zip(fixed_templates, sources, strict=True), start=1):
        global_id = first_source_id + index - 1
        source_record = _patch_source_record(template, source, global_id)
        out_terminal = _patch_terminal(template.out_terminal, "OUT", source.positive, template.out_suffix)
        in_terminal = _patch_terminal(template.in_terminal, "IN", source.negative, template.in_suffix)
        in_wire = bytearray(template.in_wire)
        if index == len(sources):
            in_wire[-1] = 0xFF
        else:
            in_wire[-1] = 0x00
        unit = source_record + out_terminal + template.out_wire + in_terminal + bytes(in_wire)
        units.append(unit)
        metadata.append(
            {
                "kind": source.kind,
                "ref": source.ref,
                "model": source.model,
                "positive": source.positive,
                "negative": source.negative,
                "global_id": global_id,
                "out_suffix": f"{template.out_suffix:04x}",
                "in_suffix": f"{template.in_suffix:04x}",
                "value": source.value,
                "fixed_order": "VSOURCE, $TEROUTPUT, WIRE, $TERINPUT, WIRE",
            }
        )
    return b"".join(units), metadata


def _build_cdb_fixed_source_rows(rcl_specs: list[Any], sources: tuple[SourcePlan, ...], first_source_id: int) -> bytes:
    source_rows = [
        SourceRow(
            idx=first_source_id + index,
            ref=source.ref,
            value=source.value,
            model=source.model,
            prop_text=source.prop_text,
        )
        for index, source in enumerate(sources)
    ]
    ordered: list[Any] = [*sorted(rcl_specs, key=lambda item: item.idx), *source_rows]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + _enc_str(spec.ref)
        if isinstance(spec, SourceRow):
            out += rv9._u32(2) + _enc_str("+") + _enc_str("1") + _enc_str("-") + _enc_str("2")
            out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._i32(-1)
        elif spec.kind == "CAPACITOR":
            out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
            out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
            out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, SourceRow):
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str(spec.model) + _enc_str("") + _enc_text(spec.prop_text)
        elif spec.kind == "CAPACITOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(v3.v14.v9.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(v3.v14.v9.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _cases() -> list[Case]:
    return [
        Case(
            "SRCP_V5_T02_R_ONLY_FIXED_ORDER_1V_SOURCE",
            "R-only DCV2 fallback using fixed V3 source order and 1V/1V source values.",
            (("R", "DV", "D0"), ("R", "D1", "D0"), ("R", "D0", "G0")),
            {"R1": "1k0", "R2": "2k0", "R3": "1G0"},
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            ("1V", "1V"),
            "preferred: fixed source order, fixed source CDB rows, source values left at fixed-file default 1V/1V.",
        ),
        Case(
            "SRCP_V5_T03_R_ONLY_FIXED_ORDER_10V_5V",
            "R-only DCV2 fallback using fixed V3 source order while mutating source values to 10V and 5V.",
            (("R", "DV", "D0"), ("R", "D1", "D0"), ("R", "D0", "G0")),
            {"R1": "1k0", "R2": "2k0", "R3": "1G0"},
            {"R1": "1k", "R2": "2k", "R3": "1G"},
            ("10V", "5V"),
            "value-isolation: same fixed source order/CDB rows, but source values are patched back to requested 10V/5V.",
        ),
        Case(
            "SRCP_V5_T04_RC_RL_FIXED_ORDER_1V_SOURCE",
            "RC/RL DCV2 fallback using fixed V3 source order and 1V/1V source values.",
            (("RC", "DV", "D0"), ("RL", "D1", "D0"), ("R", "D0", "G0")),
            {"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH", "R3": "1G0"},
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            ("1V", "1V"),
            "preferred scale-up: fixed source order/CDB rows applied to the RC/RL pure DCV2 case.",
        ),
        Case(
            "SRCP_V5_T05_RC_RL_FIXED_ORDER_10V_5V",
            "RC/RL DCV2 fallback using fixed V3 source order while mutating source values to 10V and 5V.",
            (("RC", "DV", "D0"), ("RL", "D1", "D0"), ("R", "D0", "G0")),
            {"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH", "R3": "1G0"},
            {"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            ("10V", "5V"),
            "value-isolation scale-up: fixed source order/CDB rows with requested 10V/5V source values.",
        ),
    ]


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = v5helper._build_dsn_with_devices(
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

    issues = v3.v14.v9.rcl._scan_wire_issues(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    info = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_source_passive_v5_fixed_v3_order_pending_user_test",
        "output": f"{case_id}\\{case_id}.pdsprj",
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": v3.v14.v9.rcl._marker_counts(object_chunk),
        "device_marker_counts": v3.v14.v9.rcl._marker_counts(devices),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "hashes": {
            f"{case_id}.pdsprj": _sha256_file(output_path),
            f"{case_id}.ROOT.CDB.bin": _sha256_file(cdb_path),
            f"{case_id}.ROOT.DSN.bin": _sha256_file(dsn_path),
            f"{case_id}.OBJECT_CHUNK.bin": _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(cdb),
            "devices": _sha256_bytes(devices),
        },
        "input": input_payload,
    }
    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open and simulate {case_id}.pdsprj\n", encoding="utf-8")
    return info


def _write_control_copy(case_id: str, source_project: Path) -> dict[str, Any]:
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / f"{case_id}.pdsprj"
    shutil.copy2(source_project, output_path)
    root_dsn = read_internal_file(output_path, "ROOT.DSN")
    root_cdb = read_internal_file(output_path, "ROOT.CDB")
    object_chunk = rv9._extract_object_chunk(root_dsn)
    info = {
        "case_id": case_id,
        "description": "User-supplied fixed V3 T03 project copied unchanged as a control.",
        "status": "user_fixed_control_copy",
        "output": f"{case_id}\\{case_id}.pdsprj",
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(root_cdb),
        "root_dsn_len": len(root_dsn),
        "marker_counts": v3.v14.v9.rcl._marker_counts(object_chunk),
        "static_validation_issues": v3.v14.v9.rcl._scan_wire_issues(object_chunk),
        "hashes": {f"{case_id}.pdsprj": _sha256_file(output_path), "object_chunk": _sha256_bytes(object_chunk), "ROOT.CDB": _sha256_bytes(root_cdb)},
    }
    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open and simulate {case_id}.pdsprj\n", encoding="utf-8")
    return info


def _write_transplant_control(case_id: str, base_project: Path, donor_project: Path) -> dict[str, Any]:
    root_dsn = read_internal_file(donor_project, "ROOT.DSN")
    root_cdb = read_internal_file(donor_project, "ROOT.CDB")
    case_dir = TEST_BATCH / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / f"{case_id}.pdsprj"
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": root_dsn, "ROOT.CDB": root_cdb})
    object_chunk = rv9._extract_object_chunk(root_dsn)
    info = {
        "case_id": case_id,
        "description": "User-fixed V3 ROOT.DSN and ROOT.CDB transplanted into the clean E001 base.",
        "status": "user_fixed_transplant_control",
        "output": f"{case_id}\\{case_id}.pdsprj",
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(root_cdb),
        "root_dsn_len": len(root_dsn),
        "marker_counts": v3.v14.v9.rcl._marker_counts(object_chunk),
        "static_validation_issues": v3.v14.v9.rcl._scan_wire_issues(object_chunk),
        "hashes": {f"{case_id}.pdsprj": _sha256_file(output_path), "object_chunk": _sha256_bytes(object_chunk), "ROOT.CDB": _sha256_bytes(root_cdb)},
    }
    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open and simulate {case_id}.pdsprj\n", encoding="utf-8")
    return info


def _make_case(
    case: Case,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    fixed_templates: tuple[FixedSourceTemplate, FixedSourceTemplate],
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v3._source_net_rcl_ground_allowed(
        templates,
        case.groups,
        case.visible_values,
    )
    first_source_id = len(specs) + 1
    sources = (
        SourcePlan("V1", case.source_values[0], "DV", "D0"),
        SourcePlan("V2", case.source_values[1], "D1", "D0"),
    )
    source_units, source_metadata = _source_units(fixed_templates, sources, first_source_id)
    object_chunk = bytearray(source_net_chunk[:-1] + source_units)
    object_chunk[-1] = 0xFF
    object_chunk, wire_repair = v3.v13._repair_generated_negative_wire_high_bytes(bytes(object_chunk))
    cdb_specs = [v3.v14.replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    cdb = _build_cdb_fixed_source_rows(cdb_specs, sources, first_source_id)
    return _write_case(
        case_id=case.case_id,
        description=case.description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=cdb,
        devices=devices,
        input_payload={
            "schema_version": v3.SCHEMA_VERSION,
            "generator_target": v3.GENERATOR_TARGET,
            "project": {
                "name": case.case_id,
                "output_basename": case.case_id,
                "base": BASE_FIXTURE_ID,
                "units": "proteus_internal",
            },
            "nodes": [{"id": node, "kind": "ground" if node == "G0" else "source_net"} for node in ["DV", "D0", "D1", "G0"]],
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
            "metadata": {"description": case.description, "diagnostic_rule": case.diagnostic_rule},
            "source_count": len(sources),
            "source_rule": "User-fixed V3 source order: passive groups first, then component-first VSOURCE units.",
            "sources": source_metadata,
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "rcl_counts": rcl_counts,
            "topology": topology,
            "wire_repair": wire_repair,
        },
    )


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    if ARCHIVE_BASE.with_suffix(".zip").exists():
        ARCHIVE_BASE.with_suffix(".zip").unlink()
    TEST_BATCH.mkdir(parents=True, exist_ok=True)
    fixed_donor = _copy_fixed_donor()

    registry = FixtureRegistry.load()
    base_project = registry.get(BASE_FIXTURE_ID).path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v3.v14.v9.rcl._load_rcl_unit_templates(rcl_donor)
    fixed_dsn = read_internal_file(fixed_donor, "ROOT.DSN")
    fixed_chunk = rv9._extract_object_chunk(fixed_dsn)
    fixed_templates = _fixed_source_templates(fixed_chunk)
    devices = v5helper._device_section_from_dsn(fixed_dsn)

    manifests = [
        _write_control_copy("SRCP_V5_T00_USER_FIXED_COPY", fixed_donor),
        _write_transplant_control("SRCP_V5_T01_USER_FIXED_TRANSPLANT_E001", base_project, fixed_donor),
    ]
    for case in _cases():
        manifests.append(
            _make_case(
                case,
                templates=templates,
                base_project=base_project,
                donor_project=fixed_donor,
                fixed_templates=fixed_templates,
                devices=devices,
            )
        )

    order = [item["case_id"] for item in manifests]
    summary = {
        "batch_id": "SOURCE_PASSIVE_V5_FIXED_V3_ORDER_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_simulation_test",
        "source_feedback": "V4 reportedly moved the failure to VGDVC; user supplied a fixed V3 T03 file for comparison.",
        "method": "Use the fixed V3 component-first VSOURCE unit order and fixed source-style CDB rows.",
        "test_order": order,
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item["marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in manifests
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V5 fixed-V3-order correction pack.\n\n"
        "Test in order. T00/T01 are controls from the user-fixed file. T02/T04 are preferred fixed-order/default-source-value candidates. T03/T05 isolate source value mutation.\n\n"
        + "\n".join(f"{idx}. {case_id}/{case_id}.pdsprj" for idx, case_id in enumerate(order, start=1))
        + "\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(__file__, OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({**summary, "archive": str(ARCHIVE_BASE.with_suffix(".zip")), "archive_sha256": _sha256_file(ARCHIVE_BASE.with_suffix(".zip"))}, indent=2))


if __name__ == "__main__":
    main()
