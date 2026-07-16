"""Generate short-path diagnostics for mixed DC voltage/current sources.

V4 failed all cases with ISIS.dll and also used long case/file names. MX5 keeps
paths deliberately short and adds known-good controls so feedback can separate:

* path/name length failure
* mixed VSOURCE+CSOURCE metadata failure
* mixed-source plus R/C/L body failure

Outputs are written directly to ``experiments/mx5`` as A0.pdsprj, A1.pdsprj,
B0.pdsprj, B1.pdsprj, B2.pdsprj, and C1..C5.pdsprj.
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
V12_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-03" / "generate_dc_current_v12_manual_testing_study_temp.py"

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mx5"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "MX5"
DONOR_ROOT = OUT_ROOT / "d"

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
KNOWN_GOOD_DCV = (
    REPO_ROOT
    / "experiments"
    / "dc_sources_v7_accepted_source_first_temp_2026_06_03"
    / "DC_SOURCES_V7_ACCEPTED_SOURCE_FIRST_TEST_BATCH"
    / "DCS_V7_T01_DCV_6_COMPONENTS_SOURCE_FIRST"
    / "DCS_V7_T01_DCV_6_COMPONENTS_SOURCE_FIRST.pdsprj"
)
KNOWN_GOOD_DCI = (
    REPO_ROOT
    / "experiments"
    / "dc_current_v13_15_topologies_temp_2026_06_04"
    / "DCI_V13_15_TOPOLOGIES_TEST_BATCH"
    / "DCI_V13_T01_01_SIMPLE_LOOP"
    / "DCI_V13_T01_01_SIMPLE_LOOP.pdsprj"
)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_module("dc_mixed_sources_v1_for_mx5", V1_PATH)
v12 = _load_module("dc_current_v12_for_mx5", V12_PATH)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "v4": ARCHIVED_4X_DCV,
        "dcv": ARCHIVED_DCV_MANUAL,
        "dci": ARCHIVED_DCI_MANUAL,
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
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
        raise RuntimeError(f"Missing device families: {missing}")
    return b"".join(required[name] for name in ("CAP", "VSOURCE", "CSOURCE", "REALIND", "RESISTOR")) + dci_section[-4:]


def _patch_manual_dci_unit(manual_project: Path, *, global_id: int, ref: str, positive: str, negative: str) -> bytes:
    unit = v12._manual_source_unit(manual_project)
    if len(ref) != 2:
        raise ValueError("Manual DCI ref patch must stay two ASCII chars.")

    input_starts: list[int] = []
    output_starts: list[int] = []
    for marker, starts in ((b"$TERINPUT", input_starts), (b"$TEROUTPUT", output_starts)):
        pos = 0
        while True:
            found = unit.find(marker, pos)
            if found < 0:
                break
            starts.append(found - 14)
            pos = found + 1
    if input_starts != [0, 207] or output_starts != [103, 655]:
        raise RuntimeError(f"Unexpected manual DCI source terminal starts: {input_starts=} {output_starts=}")

    ref_pos = unit.find(b"\x02V1")
    if ref_pos < 0:
        raise RuntimeError("Manual DCI source ref V1 not found.")
    source_start = ref_pos - 2
    output2_start = output_starts[-1]
    source_record = bytearray(unit[source_start:output2_start])
    source_record[2] = len(ref)
    source_record[3 : 3 + len(ref)] = ref.encode("ascii")
    model_pos = source_record.rfind(b"CSOURCE")
    if model_pos < 0:
        raise RuntimeError("Manual DCI CSOURCE marker not found.")
    body_coord = model_pos + len(b"CSOURCE")
    source_record[body_coord + 12 : body_coord + 16] = v1.rv9._u32(global_id)

    patched = (
        v1._replace_terminal_label(unit[0:103], positive)
        + v1._replace_terminal_label(unit[103:207], positive)
        + v1._replace_terminal_label(unit[207:source_start], negative)
        + bytes(source_record)
        + v1._replace_terminal_label(unit[output2_start:], negative)
    )
    if patched[-1] != 0x00:
        raise RuntimeError("Patched manual DCI unit must remain non-final.")
    return patched


def _write_direct(
    name: str,
    description: str,
    *,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    devices: bytes,
    input_payload: dict[str, Any],
) -> dict[str, Any]:
    dsn, pointers = v1.v5._build_dsn_with_devices(
        v1.read_internal_file(base_project, "ROOT.DSN"),
        v1.read_internal_file(donor_project, "ROOT.DSN"),
        object_chunk,
        devices,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base_project, "PROJECT.XML"), v1.PROTEUS_813)

    output_path = OUT_ROOT / f"{name}.pdsprj"
    cdb_path = OUT_ROOT / f"{name}.cdb.bin"
    dsn_path = OUT_ROOT / f"{name}.dsn.bin"
    chunk_path = OUT_ROOT / f"{name}.chunk.bin"
    v1.write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    (OUT_ROOT / f"{name}.json").write_text(json.dumps(input_payload, indent=2) + "\n", encoding="utf-8")

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
        "name": name,
        "description": description,
        "output": output_path.name,
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
    (OUT_ROOT / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _copy_control(name: str, description: str, source_file: Path) -> dict[str, Any]:
    if not source_file.exists():
        raise FileNotFoundError(source_file)
    output_path = OUT_ROOT / f"{name}.pdsprj"
    shutil.copy2(source_file, output_path)
    manifest = {
        "name": name,
        "description": description,
        "control": "exact_copy_known_good_project_short_path",
        "source_file": str(source_file.relative_to(REPO_ROOT)),
        "output": output_path.name,
        "hashes": {output_path.name: _sha256_file(output_path)},
    }
    (OUT_ROOT / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _v_style_cases() -> list[Any]:
    cases: list[Any] = []
    for case in v1._case_definitions():
        sources = []
        for index, source in enumerate(case.sources, start=1):
            visible_value = source.visible_value if len(source.visible_value) == 3 else "10V"
            sources.append(replace(source, ref=f"V{index}", visible_value=visible_value))
        cases.append(replace(case, sources=tuple(sources)))
    return cases


def _make_source_only_4x(
    name: str,
    description: str,
    *,
    sources: tuple[Any, ...],
    base_project: Path,
    donor_project: Path,
    source_donor_4x: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_block, source_rows = v1._source_block(sources, source_donor_4x, 1)
    object_chunk = bytearray(b"\x00" + source_block)
    object_chunk[-1] = 0xFF
    return _write_direct(
        name,
        description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=bytes(object_chunk),
        cdb=v1._build_cdb([], source_rows, 1),
        devices=devices,
        input_payload={
            "kind": "source_only_4x_dcv_units",
            "sources": [source.__dict__ | {"model": source.model} for source in source_rows],
        },
    )


def _make_manual_dci_mix(
    *,
    base_project: Path,
    donor_project: Path,
    source_donor_4x: Path,
    manual_dci: Path,
    devices: bytes,
) -> dict[str, Any]:
    v_source = v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV")
    i_source = v1.SourcePlan("dc_current", "V2", "10V", "10V", "D1")
    v_block, v_rows = v1._source_block((v_source,), source_donor_4x, 1)
    i_block = _patch_manual_dci_unit(manual_dci, global_id=2, ref="V2", positive="D1", negative="D0")
    object_chunk = bytearray(b"\x00" + v_block + i_block)
    object_chunk[-1] = 0xFF
    return _write_direct(
        "B2",
        "Mixed source-only control using one 4x-DCV VSOURCE unit plus one patched manual DCI source unit.",
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=bytes(object_chunk),
        cdb=v1._build_cdb([], [*v_rows, i_source], 1),
        devices=devices,
        input_payload={
            "kind": "source_only_4x_dcv_plus_patched_manual_dci_unit",
            "sources": [
                v_source.__dict__ | {"model": v_source.model, "global_id": 1},
                i_source.__dict__ | {"model": i_source.model, "global_id": 2},
            ],
        },
    )


def _make_requested(
    name: str,
    case: Any,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    source_donor_4x: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v1.v5._source_net_rcl(templates, list(case.groups))
    first_source_id = len(specs) + 1
    source_block, sources = v1._source_block(case.sources, source_donor_4x, first_source_id)
    object_chunk = bytearray(b"\x00" + source_block + source_net_chunk[1:])
    object_chunk[-1] = 0xFF
    cdb_specs = [replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    return _write_direct(
        name,
        case.description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=bytes(object_chunk),
        cdb=v1._build_cdb(cdb_specs, sources, first_source_id),
        devices=devices,
        input_payload={
            "kind": "requested_mixed_source_short_name_v4_method",
            "sources": [
                source.__dict__ | {"model": source.model, "global_id": first_source_id + index}
                for index, source in enumerate(sources)
            ],
            "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
            "rcl_counts": rcl_counts,
            "topology": topology,
            "exact_values": case.exact_values,
        },
    )


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    donors = _copy_donors()

    registry = v1.FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v1.v5.rcl._load_rcl_unit_templates(rcl_donor)
    devices = _ordered_device_section(donors["dcv"], donors["dci"])

    cases: list[dict[str, Any]] = [
        _copy_control("A0", "Known-good accepted DCV source-driven project copied to short path.", KNOWN_GOOD_DCV),
        _copy_control("A1", "Known-good accepted DCI source-driven project copied to short path.", KNOWN_GOOD_DCI),
        _make_source_only_4x(
            "B0",
            "V4-style mixed source-only control with actual 2A current value, short path.",
            sources=(
                v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
                v1.SourcePlan("dc_current", "V2", "2A", "02A", "D1"),
            ),
            base_project=base_project,
            donor_project=donors["dci"],
            source_donor_4x=donors["v4"],
            devices=devices,
        ),
        _make_source_only_4x(
            "B1",
            "V4-style mixed source-only control with strict accepted V2/10V current identity, short path.",
            sources=(
                v1.SourcePlan("dc_voltage", "V1", "12V", "12V", "DV"),
                v1.SourcePlan("dc_current", "V2", "10V", "10V", "D1"),
            ),
            base_project=base_project,
            donor_project=donors["dci"],
            source_donor_4x=donors["v4"],
            devices=devices,
        ),
        _make_manual_dci_mix(
            base_project=base_project,
            donor_project=donors["dci"],
            source_donor_4x=donors["v4"],
            manual_dci=donors["dci"],
            devices=devices,
        ),
    ]

    for index, case in enumerate(_v_style_cases(), start=1):
        cases.append(
            _make_requested(
                f"C{index}",
                case,
                templates=templates,
                base_project=base_project,
                donor_project=donors["dci"],
                source_donor_4x=donors["v4"],
                devices=devices,
            )
        )

    summary = {
        "batch_id": "MX5_SHORT_NAMES_STATIC_20260604",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "v4_feedback": "User reported all V4 cases failed with ISIS.dll and asked for smaller names.",
        "method": "Short direct project names plus known-good controls and mixed-source isolation cases.",
        "test_order": [item["name"] for item in cases],
        "cases": cases,
    }
    (OUT_ROOT / "manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README.txt").write_text(
        "MX5 short-name mixed DC source diagnostics.\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {name}.pdsprj" for index, name in enumerate(summary["test_order"], start=1))
        + "\n\nA0/A1 are known-good controls copied to short names. "
        "B0/B1/B2 isolate mixed source-only objects. C1-C5 are the requested circuits with short names.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "gen.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
