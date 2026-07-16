"""Generate corrected mixed AND/OR/RCL diagnostics with directional IC pins.

V2 proved the user manual donor device-section path, but it converted IC signal
pins to bidirectional terminals. This V3 keeps the donor-derived manual device
section while preserving IC signal direction: IC inputs remain $TERINPUT, IC
outputs remain $TEROUTPUT, and only passive R/C/L endpoints remain $TERBIDIR.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from types import ModuleType
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.pdsprj import inspect_pdsprj, read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

MANUAL_DONOR = Path(r"C:\Users\tahab\Downloads\ddddddddzzzzzzzzzz.pdsprj")
V1_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-08" / "generate_ic_and_or_rcl_v1_temp.py"
OUT_ROOT = REPO / "experiments" / "ic_and_or_rcl_v3_directional_ic_temp_2026_06_08"
ARCHIVE_PATH = REPO / "experiments" / "IC_AND_OR_RCL_V3_DIRECTIONAL_IC_TEMP_2026_06_08.zip"

MARKERS = (
    b"74HC08",
    b"74AND2",
    b"74HC32",
    b"74OR2",
    b"$TERINPUT",
    b"$TEROUTPUT",
    b"$TERBIDIR",
    b"$TERPOWER",
    b"$TERGROUND",
    b"WIRE",
    b"COMPONENT ID",
    b"COMPONENT VALUE",
    b"RESISTOR",
    b"CAPACITOR",
    b"CAP10",
    b"REALIND",
    b"VSOURCE",
    b"CSOURCE",
    b"VSINE",
    b"LOGICSTATE",
    b"LOGICPROBE",
)


def _load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


V1 = _load_module("and_or_rcl_v1_directional_temp", V1_SCRIPT)


def marker_counts(data: bytes) -> dict[str, int]:
    return {marker.decode("ascii"): data.count(marker) for marker in MARKERS}


def _device_section(dsn: bytes) -> bytes:
    first = dsn.find(b"ISIS CIRCUIT FILE")
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = dsn.rfind(marker, 0, first)
    if first < 0 or insert < 0:
        raise ValueError("ROOT.DSN does not contain the expected device section.")
    return dsn[insert + len(marker) : first]


def _required_members(path: Path) -> dict[str, bytes]:
    return {
        "PROJECT.XML": read_internal_file(path, "PROJECT.XML"),
        "ROOT.DSN": read_internal_file(path, "ROOT.DSN"),
        "ROOT.CDB": read_internal_file(path, "ROOT.CDB"),
        "SCRIPTS/PWRRAILS.DAT": read_internal_file(path, "SCRIPTS/PWRRAILS.DAT"),
    }


def _write_control(case_id: str, source: Path, *, base: Path | None = None) -> dict[str, object]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    source_members = _required_members(source)
    if base is None:
        write_project_from_parts(source, output, source_members)
        method = "deterministic_manual_donor_repack"
    else:
        project_xml = patch_project_xml_version(read_internal_file(base, "PROJECT.XML"), PROTEUS_813)
        dsn = patch_root_dsn_version(source_members["ROOT.DSN"], PROTEUS_813)
        write_project_from_parts(
            base,
            output,
            {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": source_members["ROOT.CDB"]},
        )
        method = "manual_root_dsn_cdb_on_e001_container"
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    container = asdict(inspect_pdsprj(output))
    container["path"] = str(container["path"])
    manifest = {
        "case_id": case_id,
        "method": method,
        "manual_donor": str(source),
        "container": container,
        "marker_counts": marker_counts(chunk),
        "cdb_marker_counts": marker_counts(cdb),
        "object_chunk_len": len(chunk),
        "static_validation_issues": [],
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _generated_directional_ic_case(registry: FixtureRegistry) -> dict[str, object]:
    base = registry.get("e001_empty")
    manual_dsn = read_internal_file(MANUAL_DONOR, "ROOT.DSN")
    object_chunk, ic_topology, passive_specs, passive_topology, replacements, passive_issues = V1.build_object_chunk(registry)
    cdb = V1.build_cdb(ic_topology, passive_specs)
    dsn, pointers = V1.build_dsn_with_device_section(
        read_internal_file(base.path, "ROOT.DSN"),
        manual_dsn,
        object_chunk,
        _device_section(manual_dsn),
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)

    case_id = "T02_15IC_DIRECTIONAL_IC_RCL_BIDIR"
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(base.path, output, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)

    issues = list(passive_issues)
    if _extract_object_chunk(read_internal_file(output, "ROOT.DSN")) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from generated chunk")
    counts = marker_counts(object_chunk)
    expected = {
        "74HC08": 24,
        "74AND2": 8,
        "74HC32": 21,
        "74OR2": 7,
        "$TERINPUT": 30,
        "$TEROUTPUT": 15,
        "$TERBIDIR": 6,
        "$TERPOWER": 1,
        "$TERGROUND": 1,
        "COMPONENT ID": 18,
    }
    for marker, want in expected.items():
        if counts[marker] != want:
            issues.append(f"{marker} count {counts[marker]} != {want}")
    if object_chunk.count(b"VSOURCE") or object_chunk.count(b"CSOURCE") or object_chunk.count(b"VSINE"):
        issues.append("unexpected source marker in IC diagnostic")

    plan = {
        "ic_gate_count": len(ic_topology),
        "and_gate_count": sum(1 for row in ic_topology if row["family"] == "74HC08"),
        "or_gate_count": sum(1 for row in ic_topology if row["family"] == "74HC32"),
        "passive_component_count": len(passive_specs),
        "manual_donor_comparison": {
            "manual_object_counts": marker_counts(_extract_object_chunk(manual_dsn)),
            "generated_object_counts": counts,
            "key_change_from_v2": "IC signal terminals are restored to $TERINPUT/$TEROUTPUT; only passive endpoints remain $TERBIDIR",
        },
        "ic_topology": ic_topology,
        "passive_topology": passive_topology,
        "passive_terminal_replacements": replacements,
    }
    (case_dir / "logic_rcl_plan.json").write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    circuit_input = {
        "mode": "mixed_ic_logic_and_or_rcl_v3_directional_ic_method",
        "ic_gate_count": 15,
        "logic": "Eight 74HC08 AND2 gates produce A1..A8; seven 74HC32 OR2 gates reduce them to Y0.",
        "rlc_load": ["R1 Y0-P1", "C1 P1-P2", "L1 P2-G0"],
        "terminal_policy": {
            "ic_input_pins": "$TERINPUT",
            "ic_output_pins": "$TEROUTPUT",
            "passive_endpoints": "$TERBIDIR",
            "named_net_connection": "same labels connect across $TERINPUT, $TEROUTPUT, and $TERBIDIR records",
            "power_bridge": "$TERPOWER to $TERBIDIR V0",
            "ground": "$TERGROUND G0",
            "ic_supply": "hidden; no explicit pin 14 or pin 7 supply wiring",
        },
    }
    (case_dir / "circuit_input.json").write_text(json.dumps(circuit_input, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "case_id": case_id,
        "description": "Generated 15-gate mixed AND/OR/RCL diagnostic with IC inputs/outputs directional and only passive endpoints bidirectional.",
        "method": "v1_generated_15ic_topology_plus_manual_donor_device_section_plus_directional_ic_terminals",
        "status": "temporary_pending_user_proteus_testing",
        "manual_donor": str(MANUAL_DONOR),
        "ic_gate_count": len(ic_topology),
        "and_gate_count": 8,
        "or_gate_count": 7,
        "passive_component_count": len(passive_specs),
        "terminal_policy": circuit_input["terminal_policy"],
        "section_pointers": pointers,
        "static_validation_issues": issues,
        "marker_counts": counts,
        "cdb_marker_counts": marker_counts(cdb),
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(dsn),
            "ROOT.CDB": _sha256_bytes(cdb),
            "object_chunk": _sha256_bytes(object_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 8, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if not MANUAL_DONOR.exists():
        raise FileNotFoundError(MANUAL_DONOR)
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    manifests = [
        _write_control("T00_MANUAL_DONOR_EXACT_REPACK", MANUAL_DONOR),
        _write_control("T01_MANUAL_DONOR_DSN_CDB_ON_E001", MANUAL_DONOR, base=base.path),
        _generated_directional_ic_case(registry),
    ]
    summary = {
        "batch": "IC_AND_OR_RCL_V3_DIRECTIONAL_IC_TEMP_2026_06_08",
        "purpose": "Correct V2 by preserving IC input/output terminal direction while keeping the manual donor device-section path.",
        "promotion_status": "temporary_pending_user_proteus_testing",
        "manual_donor": str(MANUAL_DONOR),
        "test_order": [manifest["case_id"] for manifest in manifests],
        "cases": manifests,
    }
    summary["archive_sha256"] = write_archive()
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_ROOT), "archive": str(ARCHIVE_PATH), "case_count": len(manifests)}, indent=2))


if __name__ == "__main__":
    main()
