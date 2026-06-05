"""Generate five requested mixed DC-source R/C/L circuits.

Temporary experiment only.

This combines two accepted findings:

* R/C/L bodies use the locked donor-derived subgroup method.
* DC voltage and DC current sources are inserted before the R/C/L body. Voltage
  sources keep VSOURCE metadata. Current sources use the accepted DCV geometry
  shape but patch the final model marker and ROOT.CDB entry to CSOURCE.

The new variable under test is multiple source objects in one project. Source
geometry is taken from the user-made 4x DC voltage donor so source units are
already manually spaced. Terminal labels are patched length-safely to connect
each source to the requested source-net R/C/L topology.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v1_requested5_temp_2026_06_04"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V1_REQUESTED5_TEMP_2026_06_04"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "DC_MIXED_SOURCES_V1_REQUESTED5_TEST_BATCH"

USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
USER_DCI_TESTING = Path(r"C:\Users\tahab\Downloads\testing.pdsprj")
V5_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"

SourceKind = Literal["dc_voltage", "dc_current"]


@dataclass(frozen=True)
class SourcePlan:
    kind: SourceKind
    ref: str
    cdb_value: str
    visible_value: str
    positive: str
    negative: str = "D0"

    @property
    def model(self) -> str:
        return "VSOURCE" if self.kind == "dc_voltage" else "CSOURCE"

    @property
    def prop_text(self) -> bytes:
        return b"{PRIMITIVE=ANALOG}\n\x00" if self.kind == "dc_voltage" else b"{PRIMITIVE=ANALOGUE}\n\x00"


@dataclass(frozen=True)
class RequestedCase:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    sources: tuple[SourcePlan, ...]
    visible_values: dict[str, str]
    exact_values: dict[str, str]


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v5 = _load_module("dc_sources_v5_for_mixed_sources_v1", V5_PATH)


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
        "4x_dc_voltage_10v": USER_DONOR_ROOT / "4x dc_voltage_01_default_10v.pdsprj",
        "dc_voltage_01_default_10v": USER_DONOR_ROOT / "dc_voltage_01_default_10v.pdsprj",
        "dci_manual_testing": USER_DCI_TESTING,
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


def _source_unit_starts(source_chunk: bytes) -> list[int]:
    starts: list[int] = []
    pos = 0
    while True:
        marker = source_chunk.find(b"$TEROUTPUT", pos)
        if marker < 0:
            break
        start = marker - 14
        if start >= 0:
            starts.append(start)
        pos = marker + 1
    if len(starts) < 4:
        raise RuntimeError(f"Expected at least four source starts, got {starts}.")
    return starts


def _source_units_from_4x_dcv(donor: Path, count: int) -> list[bytes]:
    if not 1 <= count <= 4:
        raise ValueError("This temporary batch supports 1..4 source units per project.")
    chunk = v5._object_chunk(donor)
    starts = _source_unit_starts(chunk)
    units: list[bytes] = []
    for index in range(count):
        start = starts[index]
        end = starts[index + 1] if index + 1 < len(starts) else len(chunk)
        unit = bytearray(chunk[start:end])
        if unit[-1] == 0xFF:
            unit = unit[:-1]
        if unit[-1] != 0x00:
            raise RuntimeError(f"Source unit {index + 1} is not in non-final form after trimming.")
        units.append(bytes(unit))
    return units


def _replace_terminal_label(record: bytes, label: str) -> bytes:
    raw = label.encode("ascii")
    if not (2 <= len(raw) <= 3) or not raw.isascii():
        raise ValueError(f"Temporary source terminal labels must be 2 or 3 ASCII chars, got {label!r}.")
    out = bytearray(record)
    if b"$TEROUTPUT" in out:
        len_offset = 31
        label_start = 32
    elif b"$TERINPUT" in out:
        len_offset = 30
        label_start = 31
    else:
        raise RuntimeError("Terminal record marker missing.")
    old_len = out[len_offset]
    return bytes(out[:len_offset] + bytes([len(raw)]) + raw + out[label_start + old_len :])


def _patch_source_record(record: bytes, plan: SourcePlan, global_id: int, original_ref: str) -> bytes:
    out = bytearray(record)
    raw_ref = plan.ref.encode("ascii")
    raw_visible = plan.visible_value.encode("ascii")
    if len(raw_ref) != 2:
        raise ValueError(f"Source ref must stay two characters, got {plan.ref!r}.")
    if len(raw_visible) != out[70]:
        raise ValueError(
            f"Visible source value {plan.visible_value!r} must match donor value length {out[70]}."
        )

    if out[2] != len(original_ref) or out[3 : 3 + len(original_ref)] != original_ref.encode("ascii"):
        raise RuntimeError(f"Source record does not start with expected donor ref {original_ref!r}.")
    out[2] = len(raw_ref)
    out[3 : 3 + len(raw_ref)] = raw_ref
    out[70] = len(raw_visible)
    out[71 : 71 + len(raw_visible)] = raw_visible

    if plan.kind == "dc_current":
        final_model_pos = out.rfind(b"VSOURCE")
        if final_model_pos < 0:
            raise RuntimeError("Expected final VSOURCE marker in DCV source geometry.")
        out[final_model_pos : final_model_pos + len(b"VSOURCE")] = b"CSOURCE"
        model = b"CSOURCE"
    else:
        model = b"VSOURCE"

    model_pos = out.rfind(model)
    if model_pos < 0:
        raise RuntimeError(f"{model.decode('ascii')} marker not found after patching source.")
    body_coord = model_pos + len(model)
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    return bytes(out)


def _patch_source_unit(unit: bytes, plan: SourcePlan, global_id: int, slot_index: int) -> bytes:
    output_marker = unit.find(b"$TEROUTPUT")
    input_marker = unit.find(b"$TERINPUT")
    if output_marker < 0 or input_marker < 0:
        raise RuntimeError("Source unit does not contain one input and one output terminal.")
    output_start = output_marker - 14
    input_start = input_marker - 14
    if output_start != 0 or input_start <= output_start:
        raise RuntimeError(f"Unexpected source terminal boundaries: output={output_start}, input={input_start}.")

    original_ref = f"V{slot_index}"
    ref_len_pos = unit.find(bytes([len(original_ref)]) + original_ref.encode("ascii"), input_start)
    if ref_len_pos < 0:
        raise RuntimeError(f"Could not locate donor source ref {original_ref!r}.")
    source_start = ref_len_pos - 2
    if source_start <= input_start:
        raise RuntimeError("Could not determine source record start.")

    output_record = _replace_terminal_label(unit[output_start:input_start], plan.positive)
    input_record = _replace_terminal_label(unit[input_start:source_start], plan.negative)
    source_record = _patch_source_record(unit[source_start:], plan, global_id, original_ref)
    patched = output_record + input_record + source_record
    if patched[-1] != 0x00:
        raise RuntimeError("Patched source unit must remain non-final.")
    return patched


def _source_block(plans: tuple[SourcePlan, ...], dcv_4x_donor: Path, first_source_id: int) -> tuple[bytes, list[SourcePlan]]:
    raw_units = _source_units_from_4x_dcv(dcv_4x_donor, len(plans))
    patched_units: list[bytes] = []
    for slot_index, (unit, plan) in enumerate(zip(raw_units, plans, strict=True), start=1):
        patched_units.append(_patch_source_unit(unit, plan, first_source_id + slot_index - 1, slot_index))
    return b"".join(patched_units), list(plans)


def _build_cdb(rcl_specs: list[Any], sources: list[SourcePlan], first_source_id: int) -> bytes:
    source_rows = [
        {
            "idx": first_source_id + index,
            "ref": source.ref,
            "value": source.cdb_value,
            "model": source.model,
            "prop_text": source.prop_text,
        }
        for index, source in enumerate(sources)
    ]
    ordered: list[Any] = [*source_rows, *rcl_specs]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        if isinstance(spec, dict):
            idx = spec["idx"]
            ref = spec["ref"]
            kind = "SOURCE"
        else:
            idx = spec.idx
            ref = spec.ref
            kind = spec.kind
        out += rv9._u32(idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(idx) + _enc_str(ref)
        if kind == "CAPACITOR":
            out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        if isinstance(spec, dict):
            out += rv9._u32(spec["idx"]) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += (
                _enc_str(spec["ref"])
                + _enc_str(spec["value"])
                + _enc_str(spec["model"])
                + _enc_str("")
                + _enc_text(spec["prop_text"])
            )
        elif spec.kind == "CAPACITOR":
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(v5.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(v5.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
            out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _case_definitions() -> list[RequestedCase]:
    return [
        RequestedCase(
            case_id="DCMS_V1_T01_CIRCUIT_1_12V_2A",
            description="Circuit 1: 12V source through RLC ladder with one 2A current source at the right node.",
            sources=(
                SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
                SourcePlan("dc_current", "I1", "2A", "02A", "D1"),
            ),
            groups=(
                ("R", "DV", "B0"),
                ("C", "B0", "D0"),
                ("L", "B0", "C0"),
                ("R", "C0", "D0"),
                ("L", "C0", "D1"),
                ("RC", "D1", "D0"),
            ),
            visible_values={"R1": "1k0", "C1": "10u", "L1": "100", "R2": "470", "L2": "220", "C2": "22u", "R3": "100"},
            exact_values={"R1": "1k", "C1": "10uF", "L1": "100mH", "R2": "470", "L2": "220mH", "C2": "22uF", "R3": "100"},
        ),
        RequestedCase(
            case_id="DCMS_V1_T02_CIRCUIT_2_TWO_5V_1A",
            description="Circuit 2: two 5V sources and one 1A current source with B/C/D branch network.",
            sources=(
                SourcePlan("dc_voltage", "V1", "5V", "05V", "DV"),
                SourcePlan("dc_voltage", "V2", "5V", "05V", "D1"),
                SourcePlan("dc_current", "I1", "1A", "01A", "D1"),
            ),
            groups=(
                ("R", "DV", "B0"),
                ("C", "B0", "D0"),
                ("RC", "B0", "D0"),
                ("L", "B0", "C0"),
                ("L", "C0", "D0"),
                ("R", "C0", "D1"),
                ("C", "D1", "D0"),
            ),
            visible_values={"R1": "050", "C1": "47u", "C2": "10u", "R2": "220", "L1": "50m", "L2": "150", "R3": "330", "C3": "100"},
            exact_values={"R1": "50", "C1": "47uF", "C2": "10uF", "R2": "220", "L1": "50mH", "L2": "150mH", "R3": "330", "C3": "100uF"},
        ),
        RequestedCase(
            case_id="DCMS_V1_T03_CIRCUIT_3_24V_TWO_0A5",
            description="Circuit 3: one 24V source and two 0.5A current sources across an RLC ladder.",
            sources=(
                SourcePlan("dc_voltage", "V1", "24V", "24V", "DV"),
                SourcePlan("dc_current", "I1", "0.5A", "0.5", "C0"),
                SourcePlan("dc_current", "I2", "0.5A", "0.5", "D1"),
            ),
            groups=(
                ("RL", "DV", "B0"),
                ("C", "B0", "D0"),
                ("L", "B0", "C0"),
                ("R", "C0", "D0"),
                ("C", "C0", "D1"),
                ("RL", "D1", "D0"),
            ),
            visible_values={"R1": "150", "L1": "82m", "C1": "4u7", "L2": "1H0", "R2": "500", "C2": "2u2", "R3": "1k0", "L3": "470"},
            exact_values={"R1": "150", "L1": "82mH", "C1": "4.7uF", "L2": "1H", "R2": "500", "C2": "2.2uF", "R3": "1k", "L3": "470mH"},
        ),
        RequestedCase(
            case_id="DCMS_V1_T04_CIRCUIT_4_TWO_15V_TWO_3A",
            description="Circuit 4: two 15V sources and two 3A current sources across a six-node RLC network.",
            sources=(
                SourcePlan("dc_voltage", "V1", "15V", "15V", "DV"),
                SourcePlan("dc_voltage", "V2", "15V", "15V", "E0"),
                SourcePlan("dc_current", "I1", "3A", "03A", "C0"),
                SourcePlan("dc_current", "I2", "3A", "03A", "E0"),
            ),
            groups=(
                ("R", "DV", "B0"),
                ("RL", "B0", "D0"),
                ("C", "B0", "C0"),
                ("C", "C0", "D0"),
                ("L", "C0", "D1"),
                ("R", "D1", "D0"),
                ("C", "D1", "E0"),
            ),
            visible_values={"R1": "010", "L1": "330", "R2": "047", "C1": "10u", "C2": "22u", "L2": "100", "R3": "220", "C3": "4u7"},
            exact_values={"R1": "10", "L1": "330mH", "R2": "47", "C1": "10uF", "C2": "22uF", "L2": "100mH", "R3": "220", "C3": "4.7uF"},
        ),
        RequestedCase(
            case_id="DCMS_V1_T05_CIRCUIT_5_THREE_9V_1A5",
            description="Circuit 5: three 9V sources and one 1.5A current source with B/D source nodes.",
            sources=(
                SourcePlan("dc_voltage", "V1", "9V", "09V", "DV"),
                SourcePlan("dc_voltage", "V2", "9V", "09V", "B0"),
                SourcePlan("dc_voltage", "V3", "9V", "09V", "D1"),
                SourcePlan("dc_current", "I1", "1.5A", "1.5", "D1"),
            ),
            groups=(
                ("L", "DV", "B0"),
                ("C", "B0", "D0"),
                ("R", "B0", "C0"),
                ("LC", "C0", "D0"),
                ("R", "C0", "D1"),
                ("C", "D1", "D0"),
            ),
            visible_values={"L1": "150", "C1": "10u", "R1": "100", "L2": "470", "C2": "22u", "R2": "470", "C3": "1uF"},
            exact_values={"L1": "150mH", "C1": "10uF", "R1": "100", "L2": "470mH", "C2": "22uF", "R2": "470", "C3": "1uF"},
        ),
    ]


def _make_case(
    case: RequestedCase,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_donor_4x: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v5._source_net_rcl(templates, list(case.groups))
    first_source_id = len(specs) + 1
    source_block, sources = _source_block(case.sources, source_donor_4x, first_source_id)
    object_chunk = bytearray(b"\x00" + source_block + source_net_chunk[1:])
    object_chunk[-1] = 0xFF

    cdb_specs = [replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    cdb = _build_cdb(cdb_specs, sources, first_source_id)

    case_dir = TEST_BATCH / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = v5._build_dsn_with_devices(
        read_internal_file(base_project, "ROOT.DSN"),
        read_internal_file(donor_project, "ROOT.DSN"),
        bytes(object_chunk),
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)

    output_path = case_dir / f"{case.case_id}.pdsprj"
    cdb_path = case_dir / f"{case.case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case.case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case.case_id}.OBJECT_CHUNK.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(bytes(object_chunk))

    issues = v5.rcl._scan_wire_issues(bytes(object_chunk))
    if rv9._extract_object_chunk(dsn) != bytes(object_chunk):
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if bytes(object_chunk).count(marker):
            issues.append(f"source-net case unexpectedly contains {marker.decode('ascii')}")
    if len({item["idx"] for item in topology}) != len(topology):
        issues.append("R/C/L topology has duplicate component IDs")
    if len({source.ref for source in sources}) != len(sources):
        issues.append("Source refs are not unique")
    source_marker_counts = {
        "VSOURCE": sum(1 for item in sources if item.kind == "dc_voltage"),
        "CSOURCE": sum(1 for item in sources if item.kind == "dc_current"),
    }
    actual_markers = v5._marker_counts(bytes(object_chunk))
    # Each source object contains the visual source name and the final model marker.
    if actual_markers["VSOURCE"] < source_marker_counts["VSOURCE"] + source_marker_counts["CSOURCE"]:
        issues.append("Object chunk has fewer visible source markers than expected.")
    if actual_markers["CSOURCE"] != source_marker_counts["CSOURCE"]:
        issues.append("Object chunk CSOURCE count does not match current source count.")

    input_payload = {
        "description": case.description,
        "sources": [
            {
                "kind": source.kind,
                "ref": source.ref,
                "value": source.cdb_value,
                "visible_value": source.visible_value,
                "positive": source.positive,
                "negative": source.negative,
                "model": source.model,
                "global_id": first_source_id + index,
            }
            for index, source in enumerate(sources)
        ],
        "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
        "visible_values": case.visible_values,
        "exact_cdb_values": case.exact_values,
        "rcl_counts": rcl_counts,
        "topology": topology,
    }
    (case_dir / "input.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "status": "temporary_dc_mixed_sources_v1_requested5_not_locked",
        "output": str(output_path.relative_to(OUT_ROOT)),
        "source_count": len(sources),
        "rcl_component_count": len(specs),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": actual_markers,
        "device_marker_counts": v5._marker_counts(devices),
        "static_validation_issues": issues,
        "section_pointers": pointers,
        "hashes": {
            output_path.name: _sha256_file(output_path),
            cdb_path.name: _sha256_file(cdb_path),
            dsn_path.name: _sha256_file(dsn_path),
            chunk_path.name: _sha256_file(chunk_path),
            "object_chunk": _sha256_bytes(bytes(object_chunk)),
            "ROOT.CDB": _sha256_bytes(cdb),
            "devices": _sha256_bytes(devices),
        },
        "input": input_payload,
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case.case_id}\n\n{case.description}\n\nProject: {output_path.name}\nStatic validation issues: {issues}\n",
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

    dci_devices = v5._device_section_from_dsn(read_internal_file(donors["dci_manual_testing"], "ROOT.DSN"))
    dcv_devices = v5._device_section_from_dsn(read_internal_file(donors["dc_voltage_01_default_10v"], "ROOT.DSN"))
    combined_devices = _combine_device_sections(dci_devices, dcv_devices)

    cases = [
        _make_case(
            item,
            templates=templates,
            base_project=base_project,
            donor_project=donors["dci_manual_testing"],
            source_donor_4x=donors["4x_dc_voltage_10v"],
            devices=combined_devices,
        )
        for item in _case_definitions()
    ]

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V1_REQUESTED5_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "method": (
            "Multiple source units are taken from user-made 4x DC voltage donor; "
            "current sources use accepted DCV geometry with CSOURCE model metadata; "
            "source units are prepended before accepted R/C/L source-net body."
        ),
        "no_ac_current": True,
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "source_count": item["source_count"],
                "rcl_component_count": item["rcl_component_count"],
                "marker_counts": item["marker_counts"],
                "device_marker_counts": item["device_marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V1_REQUESTED5_TEMP_2026_06_04\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nExpected: all five open and netlist. These are temp tests for multiple DC voltage/current sources in one R/C/L circuit.\n",
        encoding="utf-8",
    )
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
