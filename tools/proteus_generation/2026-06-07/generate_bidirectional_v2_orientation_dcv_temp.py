"""Generate focused bidirectional-orientation and clean-DCV V2 diagnostics."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from proteusgen import mixed_rcl as rcl
from proteusgen import resistor_v9 as rv9
from proteusgen import source_driven as sd
from proteusgen.layout import apply_layout_to_payload, plan_with_actual_positions
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import generate_resistor_project_from_payload
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

from bidirectional_dcv_temp import (
    build_corrected_dc_cdb,
    build_dcv_unit,
    load_dcv_unit_template,
)
from bidirectional_temp import (
    BIDIR_MARKER,
    ORIENTATION_BY_TERMINAL_ROLE,
    extract_bidir_records,
    load_templates,
    replace_ordinary_terminals,
    validate_conversion,
)


OUT = ROOT / "experiments" / "bidirectional_v2_orientation_dcv_temp_2026_06_07"
ARCHIVE = ROOT / "experiments" / "BIDIRECTIONAL_V2_ORIENTATION_DCV_TEMP_2026_06_07.zip"
USER_ONE_DCV = Path(r"C:\Users\tahab\Downloads\1DCV.pdsprj")
USER_TWO_DCV = Path(r"C:\Users\tahab\Downloads\2DCV.pdsprj")
V1_SAVED_T09 = (
    ROOT
    / "experiments"
    / "bidirectional_v1_temp_2026_06_07"
    / "T09_2DCV_RCL"
    / "BIDIR"
    / "BIDIR_V1_T09_2DCV_RCL.pdsprj"
)
V1_DONORS = ROOT / "experiments" / "bidirectional_v1_temp_2026_06_07" / "donors"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256(path.read_bytes())


def _renamed(payload: dict[str, Any], basename: str) -> dict[str, Any]:
    copied = json.loads(json.dumps(payload))
    copied.setdefault("project", {})["name"] = basename
    copied["project"]["output_basename"] = basename
    copied["layout"] = {"strategy": "beautify"}
    return copied


def _resistor_payload() -> dict[str, Any]:
    return {
        "schema_version": "proteus-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-v9-resistor-terminal",
        "project": {
            "name": "BIDIR_V2_R",
            "output_basename": "BIDIR_V2_R",
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "nodes": [
            {"id": "N1", "kind": "internal"},
            {"id": "N2", "kind": "internal"},
        ],
        "components": [
            {
                "ref": "R1",
                "type": "RESISTOR",
                "value": "10k",
                "nodes": ["N1", "N2"],
            }
        ],
        "layout": {"strategy": "beautify"},
    }


def _rcl_payload() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "BIDIR_V2_RCL", "output_basename": "BIDIR_V2_RCL"},
        "groups": [{"mode": "RCL", "start": "A1", "end": "D0"}],
        "sources": [{"kind": "dc_voltage", "ref": "V1", "value": "10V", "positive": "A1", "negative": "D0"}],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _two_dcv_payload(*, shared_negative: bool) -> dict[str, Any]:
    second_negative = "D0" if shared_negative else "B0"
    name = "BIDIR_V2_2DCV_SHARED" if shared_negative else "BIDIR_V2_2DCV_ISOLATED"
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": name, "output_basename": name},
        "groups": [
            {"mode": "RCL", "start": "A1", "end": "D0" if shared_negative else "A0"},
            {"mode": "RL", "start": "B1", "end": second_negative},
        ],
        "sources": [
            {
                "kind": "dc_voltage",
                "ref": "V1",
                "value": "10V",
                "positive": "A1",
                "negative": "D0" if shared_negative else "A0",
            },
            {
                "kind": "dc_voltage",
                "ref": "V2",
                "value": "5V",
                "positive": "B1",
                "negative": second_negative,
            },
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _copy_evidence() -> dict[str, Any]:
    donor_dir = OUT / "donors"
    donor_dir.mkdir(parents=True)
    sources = {
        "1DCV.pdsprj": USER_ONE_DCV,
        "2DCV.pdsprj": USER_TWO_DCV,
        "V1_T09_AFTER_PROTEUS.pdsprj": V1_SAVED_T09,
    }
    manifest: dict[str, Any] = {}
    for name, source in sources.items():
        if not source.is_file():
            raise FileNotFoundError(source)
        target = donor_dir / name
        shutil.copy2(source, target)
        manifest[name] = {"bytes": target.stat().st_size, "sha256": _sha256_file(target)}
    (donor_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _write_exact_control(test_id: str, donor: Path) -> dict[str, Any]:
    case_dir = OUT / test_id
    case_dir.mkdir(parents=True)
    output = case_dir / f"BIDIR_V2_{test_id}.pdsprj"
    shutil.copy2(donor, output)
    chunk = rv9._extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    cdb = read_internal_file(output, "ROOT.CDB")
    records = extract_bidir_records(chunk)
    manifest = {
        "test_id": test_id,
        "kind": "exact_user_donor_control",
        "source": donor.name,
        "output": output.name,
        "output_sha256": _sha256_file(output),
        "bidirectional_terminal_count": len(records),
        "angles": [int.from_bytes(record[9:13], "little") for record in records],
        "vsource_marker_count": chunk.count(b"VSOURCE"),
        "component_id_count": chunk.count(b"COMPONENT ID"),
        "root_cdb_len": len(cdb),
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _convert_passive_case(
    test_id: str,
    payload: dict[str, Any],
    generator: Callable[..., Any],
    *,
    base: Path,
    templates: Any,
) -> dict[str, Any]:
    case_dir = OUT / test_id
    baseline = generator(_renamed(payload, f"BIDIR_V2_{test_id}_BASELINE"), case_dir / "BASELINE", layout_strategy="beautify")
    original_dsn = baseline.dsn_path.read_bytes()
    original_chunk = rv9._extract_object_chunk(original_dsn)
    converted, replacements = replace_ordinary_terminals(
        original_chunk,
        templates,
        orientation_policy=ORIENTATION_BY_TERMINAL_ROLE,
    )
    issues = validate_conversion(original_chunk, converted, replacements)
    issues.extend(rcl._scan_wire_issues(converted))
    if issues:
        raise RuntimeError(f"{test_id}: {issues}")
    dsn, pointers = rv9.build_dsn(read_internal_file(base, "ROOT.DSN"), original_dsn, converted)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    output_dir = case_dir / "BIDIR"
    output_dir.mkdir(parents=True)
    output = output_dir / f"BIDIR_V2_{test_id}.pdsprj"
    write_project_from_parts(
        base,
        output,
        {
            "PROJECT.XML": read_internal_file(baseline.output_path, "PROJECT.XML"),
            "ROOT.CDB": baseline.cdb_path.read_bytes(),
            "ROOT.DSN": dsn,
        },
    )
    manifest = {
        "test_id": test_id,
        "kind": "terminal_role_orientation_conversion",
        "output": str(output.relative_to(OUT)),
        "output_sha256": _sha256_file(output),
        "zero_degree_count": sum(item.angle_tenths == 0 for item in replacements),
        "one_eighty_degree_count": sum(item.angle_tenths == 1800 for item in replacements),
        "replacements": [item.as_dict() for item in replacements],
        "section_pointers": pointers,
        "static_validation_issues": [],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _generate_dcv_case(
    test_id: str,
    payload: dict[str, Any],
    *,
    registry: FixtureRegistry,
    bidir_templates: Any,
    dcv_template: Any,
) -> dict[str, Any]:
    application = apply_layout_to_payload(_renamed(payload, f"BIDIR_V2_{test_id}"), "beautify")
    ir, parse_issues = sd.parse_source_driven_ir(application.payload)
    if parse_issues or ir is None:
        raise RuntimeError(f"{test_id} payload failed validation: {parse_issues}")
    if any(source.kind != "dc_voltage" for source in ir.sources):
        raise RuntimeError("The clean V2 source path currently accepts DC voltage sources only.")

    base = registry.get("e001_empty")
    rcl_donor = registry.get("rcl_4x_t07_unit_donor")
    device_donor = registry.get("source_dc_mixed_v15_donor")
    rcl_templates = rcl._load_rcl_unit_templates(rcl_donor.path)
    passive_chunk, specs, topology, generation_counts = sd._source_net_rcl(
        ir,
        rcl_templates,
        application.plan,
    )
    converted_passive, replacements = replace_ordinary_terminals(
        passive_chunk,
        bidir_templates,
        orientation_policy=ORIENTATION_BY_TERMINAL_ROLE,
    )
    issues = validate_conversion(passive_chunk, converted_passive, replacements)

    units: list[bytes] = []
    source_metadata: list[dict[str, Any]] = []
    first_source_id = len(specs) + 1
    for source_index, source in enumerate(ir.sources, start=1):
        position = application.plan.source_positions[source.ref]
        unit, metadata = build_dcv_unit(
            dcv_template,
            bidir_templates,
            source,
            source_index=source_index,
            global_id=first_source_id + source_index - 1,
            target=(position.x, position.y),
        )
        units.append(unit)
        source_metadata.append(metadata)

    object_chunk = b"\x00" + converted_passive[1:-1] + b"".join(units) + b"\xff"
    cdb = build_corrected_dc_cdb(specs, ir.sources)
    issues.extend(sd._validate_object_chunk(object_chunk, specs, ir.sources))
    if object_chunk.count(b"$TERINPUT") or object_chunk.count(b"$TEROUTPUT"):
        issues.append("ordinary terminals remain after V2 conversion")
    if object_chunk.count(BIDIR_MARKER) != len(replacements) + 2 * len(ir.sources):
        issues.append("bidirectional terminal count does not match passive plus source endpoints")
    source_pin_map = rv9._u32(2) + sd._enc_str("+") + sd._enc_str("1") + sd._enc_str("-") + sd._enc_str("2")
    if cdb.count(source_pin_map) != len(ir.sources):
        issues.append("DCV CDB source pin mapping count is incorrect")
    for source_index in range(1, len(ir.sources) + 1):
        suffix_base = 0x7000 + (source_index - 1) * 0x80
        for suffix in (suffix_base, suffix_base + 0x32):
            if object_chunk.count(rv9._u16(suffix) + b"\x01\x00") != 2:
                issues.append(f"source suffix {suffix:04x} is not linked exactly twice")
    if issues:
        raise RuntimeError(f"{test_id}: {issues}")

    donor_dsn = read_internal_file(device_donor.path, "ROOT.DSN")
    devices = sd._device_section_from_dsn(donor_dsn)
    dsn, pointers = sd._build_dsn_with_devices(
        read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        object_chunk,
        devices,
    )
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), PROTEUS_813)
    case_dir = OUT / test_id
    case_dir.mkdir(parents=True)
    output = case_dir / f"BIDIR_V2_{test_id}.pdsprj"
    write_project_from_parts(
        base.path,
        output,
        {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn},
    )
    (case_dir / "object_chunk.bin").write_bytes(object_chunk)
    (case_dir / "ROOT.CDB.bin").write_bytes(cdb)
    final_layout = plan_with_actual_positions(application.plan, topology, source_metadata)
    (case_dir / "layout_plan.json").write_text(
        json.dumps(final_layout.as_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    manifest = {
        "test_id": test_id,
        "kind": "donor_native_bidirectional_dcv_generation",
        "output": output.name,
        "output_sha256": _sha256_file(output),
        "source_count": len(ir.sources),
        "sources": source_metadata,
        "passive_component_count": len(specs),
        "group_count": generation_counts["group_count"],
        "bidirectional_terminal_count": object_chunk.count(BIDIR_MARKER),
        "zero_degree_count": sum(
            int.from_bytes(record[9:13], "little") == 0 for record in extract_bidir_records(object_chunk)
        ),
        "one_eighty_degree_count": sum(
            int.from_bytes(record[9:13], "little") == 1800 for record in extract_bidir_records(object_chunk)
        ),
        "source_cdb_pin_mapping": ["+", "1", "-", "2"],
        "shared_negative": len({source.negative for source in ir.sources}) == 1,
        "section_pointers": pointers,
        "root_cdb_sha256": _sha256(cdb),
        "object_chunk_sha256": _sha256(object_chunk),
        "static_validation_issues": [],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    resolved = OUT.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError("Refusing to clear an output directory outside the repository.")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    evidence = _copy_evidence()
    bidir_templates = load_templates(
        V1_DONORS / "bider_empty.pdsprj",
        V1_DONORS / "180bider_empty.pdsprj",
    )
    dcv_template = load_dcv_unit_template(USER_ONE_DCV)
    registry = FixtureRegistry.load()
    failed_hashes = registry.verify_all()
    if failed_hashes:
        raise RuntimeError(f"Fixture integrity failure: {failed_hashes}")
    base = registry.get("e001_empty").path

    results = [
        _write_exact_control("T00A_EXACT_1DCV_DONOR", USER_ONE_DCV),
        _write_exact_control("T00B_EXACT_2DCV_DONOR", USER_TWO_DCV),
        _convert_passive_case(
            "T01_RESISTOR_0_180",
            _resistor_payload(),
            generate_resistor_project_from_payload,
            base=base,
            templates=bidir_templates,
        ),
        _generate_dcv_case(
            "T02_1DCV_RCL_CLEAN",
            _rcl_payload(),
            registry=registry,
            bidir_templates=bidir_templates,
            dcv_template=dcv_template,
        ),
        _generate_dcv_case(
            "T03_2DCV_ISOLATED_DIAGNOSTIC",
            _two_dcv_payload(shared_negative=False),
            registry=registry,
            bidir_templates=bidir_templates,
            dcv_template=dcv_template,
        ),
        _generate_dcv_case(
            "T04_2DCV_SHARED_NEGATIVE",
            _two_dcv_payload(shared_negative=True),
            registry=registry,
            bidir_templates=bidir_templates,
            dcv_template=dcv_template,
        ),
    ]
    summary = {
        "phase": "bidirectional_v2_orientation_and_clean_dcv",
        "evidence": evidence,
        "findings": {
            "orientation_rule": "ordinary output -> bidirectional 0 degrees; ordinary input -> bidirectional 180 degrees",
            "dcv_cdb_rule": "DC voltage sources require +->1 and -->2 pin mappings",
            "two_source_simulation_hypothesis": "separate negative nets create disconnected SPICE islands; T04 shares D0",
        },
        "cases": results,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT / "README_TEST_ORDER.txt").write_text(
        "BIDIRECTIONAL V2 ORIENTATION + CLEAN DCV TEST PACK\n\n"
        "T00A: exact manual 1DCV donor control\n"
        "T00B: exact manual 2DCV donor control\n"
        "T01: resistor with a true 180-degree bidirectional input and 0-degree output\n"
        "T02: one donor-native DCV source plus RCL load; corrected source CDB pin map\n"
        "T03: two donor-native DCV sources on disconnected negative nets (diagnostic)\n"
        "T04: two donor-native DCV sources sharing negative net D0 (expected simulation-safe topology)\n\n"
        "For every case report: opens without bad-object warning, visual direction, and simulation result.\n"
        "T03 may still report a singular matrix because it intentionally contains two disconnected islands.\n",
        encoding="utf-8",
    )
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                info = zipfile.ZipInfo(
                    path.relative_to(OUT.parent).as_posix(),
                    date_time=(2026, 6, 7, 0, 0, 0),
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, path.read_bytes())
    print(json.dumps({"output": str(OUT), "archive": str(ARCHIVE), "cases": len(results)}, indent=2))


if __name__ == "__main__":
    main()
