"""Generate donor-tail diagnostics for mixed DC sources plus R/C/L.

The user supplied a Proteus-created 21-component R/C/L circuit with both a
VSOURCE and a CSOURCE appended. The important observed structure is:

* no $TERPOWER and no $TERGROUND records
* keep the leading ordinary $TEROUTPUT V0 record from the old power bridge
* R/C/L component records come first
* source records are appended at the tail
* source component IDs are after the 21 R/C/L IDs
* ROOT.CDB rows are all R/C/L rows first, then I1, then V1
* the coherent device section order is CAP, CSOURCE, REALIND, RESISTOR, VSOURCE

V9 keeps this temp-only. It tests whether we can reproduce that structure with
the repo R/C/L body while borrowing the donor source tail and coherent device
metadata.
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

from proteusgen import mixed_rcl as rcl  # noqa: E402
from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import MixedRclCircuitIR, MixedRclGroup  # noqa: E402
from proteusgen.mixed_rcl_examples import mixed_rcl_21_case  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

V5_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-03" / "generate_dc_sources_v5_source_net_temp.py"
OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v9_donor_tail_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V9_DONOR_TAIL_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"

USER_DONOR = Path(r"C:\Users\tahab\Downloads\RCL_V19_T01_CORRECT_21_withVsourcenCsource.pdsprj")


@dataclass(frozen=True)
class SourceRow:
    idx: int
    ref: str
    value: str
    model: str
    prop_text: bytes


def _load_v5() -> Any:
    spec = importlib.util.spec_from_file_location("dc_sources_v5_for_v9_donor_tail", V5_PATH)
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


def _copy_donor() -> Path:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    if not USER_DONOR.exists():
        raise FileNotFoundError(USER_DONOR)
    dst = DONOR_ROOT / "rcl_v19_21_with_vsource_csource.pdsprj"
    shutil.copy2(USER_DONOR, dst)
    return dst


def _terminal_events(chunk: bytes) -> list[tuple[int, str, str]]:
    events: list[tuple[int, str, str]] = []
    for marker, kind in ((b"$TEROUTPUT", "OUT"), (b"$TERINPUT", "IN")):
        pos = 0
        while True:
            marker_pos = chunk.find(marker, pos)
            if marker_pos < 0:
                break
            start = marker_pos - 14
            if start < 0:
                raise RuntimeError(f"Bad terminal record start for {kind} at marker {marker_pos}.")
            if kind == "OUT":
                length_offset = start + 31
                label_start = start + 32
            else:
                length_offset = start + 30
                label_start = start + 31
            label_len = chunk[length_offset]
            label = chunk[label_start : label_start + label_len].decode("ascii")
            events.append((start, kind, label))
            pos = marker_pos + 1
    return sorted(events)


def _find_source_tail_start(donor_chunk: bytes) -> int:
    first_source_ref = donor_chunk.find(b"\xff\x02V1", 14_000)
    if first_source_ref < 0:
        raise RuntimeError("Could not find first donor source record ref V1.")
    prior_terminals = [start for start, _kind, _label in _terminal_events(donor_chunk) if start < first_source_ref]
    if not prior_terminals:
        raise RuntimeError("Could not find terminal before donor source record.")
    tail_start = prior_terminals[-1]
    if donor_chunk[tail_start:].count(b"VSOURCE") != 2 or donor_chunk[tail_start:].count(b"CSOURCE") != 2:
        raise RuntimeError("Donor source tail bounds do not include exactly one VSOURCE and one CSOURCE object.")
    return tail_start


def _patch_terminal_labels(chunk: bytes, replacements: dict[str, str]) -> bytes:
    if not replacements:
        return chunk
    starts = [(start, kind) for start, kind, _label in _terminal_events(chunk)]
    starts.append((len(chunk), "END"))
    out = bytearray()
    cursor = 0
    for index, (start, kind) in enumerate(starts[:-1]):
        if cursor < start:
            out += chunk[cursor:start]
        end = starts[index + 1][0]
        record = bytearray(chunk[start:end])
        if kind == "OUT":
            length_offset = 31
            label_start = 32
        else:
            length_offset = 30
            label_start = 31
        label_len = record[length_offset]
        label = record[label_start : label_start + label_len].decode("ascii")
        replacement = replacements.get(label)
        if replacement is not None:
            raw = replacement.encode("ascii")
            if not (1 <= len(raw) <= 3):
                raise ValueError(f"Replacement terminal label {replacement!r} is outside the donor-tested length range.")
            record = record[:length_offset] + bytes([len(raw)]) + raw + record[label_start + label_len :]
        out += record
        cursor = end
    if cursor < len(chunk):
        out += chunk[cursor:]
    return bytes(out)


def _source_tail(donor_chunk: bytes, *, patch_dvo_to_d0: bool) -> bytes:
    tail = donor_chunk[_find_source_tail_start(donor_chunk) :]
    if patch_dvo_to_d0:
        tail = _patch_terminal_labels(tail, {"DVO": "D0"})
    if tail[-1] != 0xFF:
        raise RuntimeError("Donor source tail must be final.")
    return tail


def _build_rcl_body_keep_v0_output(templates: rcl.RclUnitTemplates, *, negative_label: str) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, Any]], dict[str, Any]]:
    payload = mixed_rcl_21_case()
    groups = []
    for item in payload["groups"]:
        start = negative_label if item["start"] == "G0" else item["start"]
        end = negative_label if item["end"] == "G0" else item["end"]
        groups.append(MixedRclGroup(mode=item["mode"], start=start, end=end))
    ir = MixedRclCircuitIR(
        schema_version=rcl.SCHEMA_VERSION,
        generator_target=rcl.GENERATOR_TARGET,
        name="DCMS_V9_RCL_21_KEEP_V0_OUTPUT",
        output_basename="DCMS_V9_RCL_21_KEEP_V0_OUTPUT",
        groups=tuple(groups),
        component_values={},
        metadata={},
    )
    chunk_with_bridge, specs, topology, counts = rcl.build_object_chunk(ir, templates)
    output_len = 104
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE
    if chunk_with_bridge[1 : 1 + output_len].count(b"$TEROUTPUT") != 1:
        raise RuntimeError("Leading bridge output terminal was not found.")
    if chunk_with_bridge[1 + output_len : bridge_end].count(b"$TERPOWER") != 1:
        raise RuntimeError("Expected bridge power section not found.")
    body = bytearray(chunk_with_bridge[:1] + chunk_with_bridge[1 : 1 + output_len] + chunk_with_bridge[bridge_end:])
    if body.count(b"$TERPOWER") or body.count(b"$TERGROUND"):
        raise RuntimeError("V9 source-net body still contains power/ground terminal records.")
    body[-1] = 0xFF
    return bytes(body), specs, topology, {**counts, "power_bridge_count": 0, "kept_leading_v0_output": True}


def _generated_with_tail(
    templates: rcl.RclUnitTemplates,
    donor_chunk: bytes,
    *,
    patch_tail_dvo_to_d0: bool,
) -> tuple[bytes, list[rcl.RclSpec], list[dict[str, Any]], dict[str, Any]]:
    body, specs, topology, counts = _build_rcl_body_keep_v0_output(templates, negative_label="D0")
    tail = _source_tail(donor_chunk, patch_dvo_to_d0=patch_tail_dvo_to_d0)
    combined = bytearray(body)
    combined[-1] = 0x00
    combined += tail
    combined[-1] = 0xFF
    return bytes(combined), specs, topology, {**counts, "source_tail_len": len(tail), "tail_dvo_to_d0": patch_tail_dvo_to_d0}


def _build_cdb(rcl_specs: list[rcl.RclSpec]) -> bytes:
    source_rows = [
        SourceRow(22, "I1", "1A", "CSOURCE", b"{PRIMITIVE=ANALOGUE}\n\x00"),
        SourceRow(23, "V1", "1V", "VSOURCE", b"{PRIMITIVE=ANALOG}\n\x00"),
    ]
    ordered: list[Any] = [*sorted(rcl_specs, key=lambda item: item.idx), *source_rows]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + v5._enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + v5._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + v5._enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + v5._enc_str(spec.ref)
        if getattr(spec, "kind", "") == "CAPACITOR":
            out += rv9._u32(2) + v5._enc_str("2") + v5._enc_str("2") + v5._enc_str("1") + v5._enc_str("1")
        else:
            out += rv9._u32(2) + v5._enc_str("1") + b"\x00" + v5._enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + v5._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, SourceRow):
            out += v5._enc_str(spec.ref) + v5._enc_str(spec.value) + v5._enc_str(spec.model) + v5._enc_str("") + v5._enc_text(spec.prop_text)
        elif spec.kind == "CAPACITOR":
            out += v5._enc_str(spec.ref) + v5._enc_str(spec.value) + v5._enc_str("CAP") + v5._enc_str("CAP10") + v5._enc_text(rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += v5._enc_str(spec.ref) + v5._enc_str(spec.value) + v5._enc_str("REALIND") + v5._enc_str("") + v5._enc_text(rcl.INDUCTOR_PROP_TEXT)
        else:
            out += v5._enc_str(spec.ref) + v5._enc_str(spec.value) + v5._enc_str("RESISTOR") + v5._enc_str("") + v5._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
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
    case_dir = OUT_ROOT / case_id
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

    issues = rcl._scan_wire_issues(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    for marker in (b"$TERPOWER", b"$TERGROUND"):
        if object_chunk.count(marker):
            issues.append(f"source-tail case unexpectedly contains {marker.decode('ascii')}")

    manifest = {
        "case_id": case_id,
        "description": description,
        "status": "temporary_dc_mixed_sources_v9_donor_tail_not_locked",
        "output": str(output_path.relative_to(OUT_ROOT)),
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": v5._marker_counts(object_chunk),
        "device_marker_counts": v5._marker_counts(devices),
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
    return manifest


def _copy_control(case_id: str, description: str, source_file: Path) -> dict[str, Any]:
    output_path = OUT_ROOT / f"{case_id}.pdsprj"
    shutil.copy2(source_file, output_path)
    manifest = {
        "case_id": case_id,
        "description": description,
        "control": "exact_copy",
        "output": output_path.name,
        "hashes": {output_path.name: _sha256_file(output_path)},
    }
    (OUT_ROOT / f"{case_id}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    donor = _copy_donor()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = rcl._load_rcl_unit_templates(rcl_donor)

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_chunk = rv9._extract_object_chunk(donor_dsn)
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_devices = v5._device_section_from_dsn(donor_dsn)
    generated_tail_exact, generated_specs, generated_topology, generated_counts = _generated_with_tail(
        templates,
        donor_chunk,
        patch_tail_dvo_to_d0=False,
    )
    generated_tail_d0, generated_specs_d0, generated_topology_d0, generated_counts_d0 = _generated_with_tail(
        templates,
        donor_chunk,
        patch_tail_dvo_to_d0=True,
    )
    donor_label_mutation = _patch_terminal_labels(donor_chunk, {"DVO": "D0"})

    cases: list[dict[str, Any]] = [
        _copy_control("DCMS_V9_T00_DONOR_COPY", "Exact copy of the user donor with 21 R/C/L components plus VSOURCE and CSOURCE.", donor),
        _write_case(
            "DCMS_V9_T01_DONOR_TRANSPLANT_E001",
            "User donor object chunk, ROOT.CDB, and coherent device section transplanted into E001.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_chunk,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_object_cdb_devices_transplanted_to_e001"},
        ),
        _write_case(
            "DCMS_V9_T02_DONOR_LABEL_DVO_TO_D0",
            "Exact donor object structure with only terminal label DVO changed to D0.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_label_mutation,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_terminal_label_mutation", "terminal_replacements": {"DVO": "D0"}},
        ),
        _write_case(
            "DCMS_V9_T03_GENERATED_21_DONOR_TAIL_EXACT_LABELS",
            "Generated 21 R/C/L body keeping leading ordinary V0 output, then exact donor source tail.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=generated_tail_exact,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={
                "kind": "generated_rcl_keep_v0_output_plus_exact_donor_tail",
                "generation_counts": generated_counts,
                "topology": generated_topology,
            },
        ),
        _write_case(
            "DCMS_V9_T04_GENERATED_21_DONOR_TAIL_D0_LABEL",
            "Generated 21 R/C/L body keeping leading ordinary V0 output, donor source tail with DVO changed to D0.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=generated_tail_d0,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={
                "kind": "generated_rcl_keep_v0_output_plus_d0_patched_donor_tail",
                "generation_counts": generated_counts_d0,
                "topology": generated_topology_d0,
            },
        ),
        _write_case(
            "DCMS_V9_T05_GENERATED_21_DONOR_TAIL_D0_GENERATED_CDB",
            "Same as T04, but ROOT.CDB is generated from repo specs with R/C/L rows first, then I1, then V1.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=generated_tail_d0,
            cdb=_build_cdb(generated_specs_d0),
            devices=donor_devices,
            input_payload={
                "kind": "generated_rcl_keep_v0_output_plus_d0_patched_tail_generated_cdb",
                "generation_counts": generated_counts_d0,
                "topology": generated_topology_d0,
            },
        ),
    ]

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V9_DONOR_TAIL_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "User supplied RCL_V19_T01_CORRECT_21_withVsourcenCsource.pdsprj and noted ISIS.dll should not be accepted as a normal failure.",
        "method": "Use the user donor as authority for source-tail order, source IDs, CDB row order, and coherent VSOURCE+CSOURCE+R/C/L device section.",
        "donor_source_tail_start": _find_source_tail_start(donor_chunk),
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
        "DC_MIXED_SOURCES_V9_DONOR_TAIL_TEMP_2026_06_05\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" if index > 1 else f"{index}. {case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT00/T01 prove the donor and transplant path. T02 tests whether terminal names can be changed safely. "
        "T03/T04 test generated 21 R/C/L bodies with the donor source tail. T05 tests the generated CDB writer against the donor-tail object structure.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
