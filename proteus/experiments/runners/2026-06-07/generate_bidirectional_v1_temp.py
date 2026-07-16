"""Generate the first general bidirectional-terminal diagnostic pack."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable

from proteusgen import mixed_rcl as rcl
from proteusgen import resistor_v9 as rv9
from proteusgen.mixed_passive import generate_mixed_passive_project_from_payload
from proteusgen.mixed_rcl import generate_mixed_rcl_project_from_payload
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import generate_resistor_project_from_payload
from proteusgen.source_driven import generate_source_driven_project_from_payload
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

from bidirectional_temp import (  # noqa: E402
    BIDIR_MARKER,
    extract_bidir_records,
    load_templates,
    rebuild_existing_bidir_records,
    replace_ordinary_terminals,
    sha256_bytes,
    validate_conversion,
)

USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\projects")
OUT = ROOT / "proteus" / "experiments" / "runs" / "bidirectional_v1_temp_2026_06_07"
ARCHIVE = ROOT / "proteus" / "experiments" / "runs" / "BIDIRECTIONAL_V1_TEMP_2026_06_07.zip"

DONOR_NAMES = (
    "bider_180bider_RCL_2ACC.pdsprj",
    "bider_180bider_RCL_DCV_ACC.pdsprj",
    "bider_180bider_RCL_2DCC.pdsprj",
    "bider_180bider_RCL_DCV_DCC.pdsprj",
    "bider_180bider_RCL_DCV.pdsprj",
    "bider_180bider_RCL_2DCV.pdsprj",
    "4_bider_180bider_RCL.pdsprj",
    "2_bider_180bider_RCL.pdsprj",
    "bider_180bider_RCL.pdsprj",
    "bider_180bider_ind.pdsprj",
    "2_bider_180bider_ind.pdsprj",
    "4_bider_180bider_ind.pdsprj",
    "bider_180bider_cap.pdsprj",
    "2_bider_180bider_cap.pdsprj",
    "4_bider_180bider_cap.pdsprj",
    "180bider_empty.pdsprj",
    "2_180bider_empty.pdsprj",
    "4_180bider_empty.pdsprj",
    "bider_empty.pdsprj",
    "2_bider_empty.pdsprj",
    "4_bider_empty.pdsprj",
    "bider_180bider_empty.pdsprj",
    "2_bider_180bider_empty.pdsprj",
    "4_bider_180bider_empty.pdsprj",
    "2biderwithresistor.pdsprj",
    "4biderwithresistor.pdsprj",
    "biderwithresistor.pdsprj",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _renamed(payload: dict[str, Any], name: str) -> dict[str, Any]:
    out = copy.deepcopy(payload)
    project = out.setdefault("project", {})
    project["name"] = name
    project["output_basename"] = name
    out.setdefault("layout", {})["strategy"] = "beautify"
    return out


def _resistor_payload(count: int, *, power_ground: bool) -> dict[str, Any]:
    if power_ground:
        node_ids = ["V0", *[f"N{i}" for i in range(1, count)], "G0"]
    else:
        node_ids = [f"N{i}" for i in range(count + 1)]
    return {
        "schema_version": "proteus-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-v9-resistor-terminal",
        "project": {
            "name": "BIDIR_R",
            "output_basename": "BIDIR_R",
            "base": "E001_EMPTY_BASE",
            "units": "proteus_internal",
        },
        "nodes": [
            {
                "id": node,
                "kind": "power" if node == "V0" else "ground" if node == "G0" else "internal",
            }
            for node in node_ids
        ],
        "components": [
            {
                "ref": f"R{index}",
                "type": "RESISTOR",
                "value": f"{index}k",
                "nodes": [node_ids[index - 1], node_ids[index]],
            }
            for index in range(1, count + 1)
        ],
        "layout": {"strategy": "beautify"},
    }


def _mixed_rc_payload() -> dict[str, Any]:
    payload = json.loads((ROOT / "examples" / "my_test_circuit.json").read_text(encoding="utf-8"))
    payload["layout"] = {"strategy": "beautify"}
    return payload


def _single_group_payload(mode: str, name: str) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-mixed-rcl-locked",
        "project": {"name": name, "output_basename": name, "base": "E001_EMPTY_BASE"},
        "groups": [{"mode": mode, "start": "V0", "end": "G0"}],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _mixed_sources() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "BIDIR_DCV_DCC", "output_basename": "BIDIR_DCV_DCC"},
        "groups": [
            {"mode": "RC", "start": "DV", "end": "N1"},
            {"mode": "RL", "start": "N1", "end": "D0"},
        ],
        "sources": [
            {"kind": "dc_voltage", "ref": "V1", "value": "12V", "positive": "DV", "negative": "D0"},
            {"kind": "dc_current", "ref": "I1", "value": "2A", "positive": "N1", "negative": "D0"},
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _two_dcv() -> dict[str, Any]:
    return {
        "schema_version": "source-driven-rcl-circuit-ir/v0.1",
        "generator_target": "proteus-8.13-source-driven-rcl-locked",
        "project": {"name": "BIDIR_2DCV", "output_basename": "BIDIR_2DCV"},
        "groups": [
            {"mode": "RCL", "start": "A1", "end": "A0"},
            {"mode": "RL", "start": "B1", "end": "B0"},
        ],
        "sources": [
            {"kind": "dc_voltage", "ref": "V1", "value": "10V", "positive": "A1", "negative": "A0"},
            {"kind": "dc_voltage", "ref": "V2", "value": "5V", "positive": "B1", "negative": "B0"},
        ],
        "component_values": {},
        "layout": {"strategy": "beautify"},
    }


def _source_payload(path: str) -> dict[str, Any]:
    payload = json.loads((ROOT / "examples" / path).read_text(encoding="utf-8"))
    payload["layout"] = {"strategy": "beautify"}
    return payload


def _cases() -> list[tuple[str, dict[str, Any], Callable[..., Any]]]:
    return [
        ("T01_R_SINGLE_INTERNAL", _resistor_payload(1, power_ground=False), generate_resistor_project_from_payload),
        ("T02_R4_POWER_GROUND", _resistor_payload(4, power_ground=True), generate_resistor_project_from_payload),
        ("T03_RC_MIXED", _mixed_rc_payload(), generate_mixed_passive_project_from_payload),
        ("T04_CAP_ONLY_POWER_GROUND", _single_group_payload("C", "BIDIR_CAP"), generate_mixed_rcl_project_from_payload),
        ("T05_IND_ONLY_POWER_GROUND", _single_group_payload("L", "BIDIR_IND"), generate_mixed_rcl_project_from_payload),
        ("T06_RCL_POWER_GROUND", _single_group_payload("RCL", "BIDIR_RCL"), generate_mixed_rcl_project_from_payload),
        ("T07_DCV_RCL", _source_payload("source_driven_default_dcv.json"), generate_source_driven_project_from_payload),
        ("T08_DCV_DCC_RCL", _mixed_sources(), generate_source_driven_project_from_payload),
        ("T09_2DCV_RCL", _two_dcv(), generate_source_driven_project_from_payload),
        ("T10_ACV_RC", _source_payload("source_driven_acv.json"), generate_source_driven_project_from_payload),
    ]


def _copy_donors() -> list[dict[str, Any]]:
    donor_out = OUT / "donors"
    donor_out.mkdir(parents=True)
    manifest: list[dict[str, Any]] = []
    for name in DONOR_NAMES:
        source = USER_DONOR_ROOT / name
        if not source.is_file():
            raise FileNotFoundError(source)
        target = donor_out / name
        shutil.copy2(source, target)
        manifest.append({"name": name, "bytes": target.stat().st_size, "sha256": _sha256_file(target)})
    (donor_out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _verify_all_donor_terminals(templates: Any) -> dict[str, Any]:
    checked = 0
    failures: list[str] = []
    for name in DONOR_NAMES:
        project = OUT / "donors" / name
        chunk = rv9._extract_object_chunk(read_internal_file(project, "ROOT.DSN"))
        records = extract_bidir_records(chunk)
        checked += len(records)
        if rebuild_existing_bidir_records(chunk, templates) != chunk:
            failures.append(name)
    if failures:
        raise RuntimeError(f"Bidirectional terminal reconstruction mismatch: {', '.join(failures)}")
    return {"project_count": len(DONOR_NAMES), "terminal_record_count": checked, "failures": []}


def _write_exact_control(
    *,
    name: str,
    donor: Path,
    base: Path,
    templates: Any,
) -> dict[str, Any]:
    case_dir = OUT / name
    case_dir.mkdir(parents=True)
    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    chunk = rv9._extract_object_chunk(donor_dsn)
    rebuilt = rebuild_existing_bidir_records(chunk, templates)
    if rebuilt != chunk:
        raise RuntimeError(f"{name} did not rebuild its bidirectional records byte-exactly.")
    dsn, pointers = rv9.build_dsn(read_internal_file(base, "ROOT.DSN"), donor_dsn, rebuilt)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base, "PROJECT.XML"), PROTEUS_813)
    cdb = read_internal_file(donor, "ROOT.CDB")
    output = case_dir / f"BIDIR_V1_{name}.pdsprj"
    write_project_from_parts(base, output, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    manifest = {
        "test_id": name,
        "kind": "exact_rebuild_control",
        "donor": donor.name,
        "terminal_count": rebuilt.count(BIDIR_MARKER),
        "object_chunk_sha256": sha256_bytes(rebuilt),
        "object_chunk_equal": True,
        "section_pointers": pointers,
        "output": output.name,
        "output_sha256": _sha256_file(output),
        "static_validation_issues": [],
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _convert_generated(
    *,
    test_id: str,
    payload: dict[str, Any],
    generator: Callable[..., Any],
    base: Path,
    templates: Any,
) -> dict[str, Any]:
    case_dir = OUT / test_id
    baseline_dir = case_dir / "BASELINE"
    bidir_dir = case_dir / "BIDIR"
    generated = generator(_renamed(payload, f"BIDIR_V1_{test_id}_BASELINE"), baseline_dir, layout_strategy="beautify")
    original_dsn = generated.dsn_path.read_bytes()
    original_chunk = rv9._extract_object_chunk(original_dsn)
    converted_chunk, replacements = replace_ordinary_terminals(original_chunk, templates)
    issues = validate_conversion(original_chunk, converted_chunk, replacements)
    issues.extend(rcl._scan_wire_issues(converted_chunk))
    if issues:
        raise RuntimeError(f"{test_id} conversion failed static validation: {issues}")

    converted_dsn, pointers = rv9.build_dsn(read_internal_file(base, "ROOT.DSN"), original_dsn, converted_chunk)
    converted_dsn = patch_root_dsn_version(converted_dsn, PROTEUS_813)
    if rv9._extract_object_chunk(converted_dsn) != converted_chunk:
        raise RuntimeError(f"{test_id} rebuilt DSN did not preserve the converted object chunk.")

    bidir_dir.mkdir(parents=True)
    output = bidir_dir / f"BIDIR_V1_{test_id}.pdsprj"
    project_xml = read_internal_file(generated.output_path, "PROJECT.XML")
    cdb = generated.cdb_path.read_bytes()
    write_project_from_parts(base, output, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": converted_dsn})
    (bidir_dir / "object_chunk.bin").write_bytes(converted_chunk)
    manifest = {
        "test_id": test_id,
        "kind": "generated_terminal_conversion",
        "baseline_project": str(generated.output_path.relative_to(OUT)),
        "bidirectional_project": str(output.relative_to(OUT)),
        "ordinary_terminal_count_before": original_chunk.count(b"$TERINPUT") + original_chunk.count(b"$TEROUTPUT"),
        "ordinary_terminal_count_after": converted_chunk.count(b"$TERINPUT") + converted_chunk.count(b"$TEROUTPUT"),
        "bidirectional_terminal_count": converted_chunk.count(BIDIR_MARKER),
        "power_terminal_count": converted_chunk.count(b"$TERPOWER"),
        "ground_terminal_count": converted_chunk.count(b"$TERGROUND"),
        "wire_count": converted_chunk.count(b"WIRE"),
        "component_id_count": converted_chunk.count(b"COMPONENT ID"),
        "root_cdb_unchanged": cdb == generated.cdb_path.read_bytes(),
        "component_and_wire_marker_counts_unchanged": True,
        "replacements": [item.as_dict() for item in replacements],
        "object_chunk_before_sha256": sha256_bytes(original_chunk),
        "object_chunk_after_sha256": sha256_bytes(converted_chunk),
        "section_pointers": pointers,
        "output_sha256": _sha256_file(output),
        "static_validation_issues": [],
    }
    (bidir_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    resolved = OUT.resolve()
    if ROOT.resolve() not in resolved.parents:
        raise RuntimeError("Refusing to clear an output directory outside the repository.")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)

    donor_manifest = _copy_donors()
    templates = load_templates(
        OUT / "donors" / "bider_empty.pdsprj",
        OUT / "donors" / "180bider_empty.pdsprj",
    )
    donor_validation = _verify_all_donor_terminals(templates)
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty").path

    results = [
        _write_exact_control(
            name="T00A_EXACT_EMPTY_REBUILD",
            donor=OUT / "donors" / "bider_180bider_empty.pdsprj",
            base=base,
            templates=templates,
        ),
        _write_exact_control(
            name="T00B_EXACT_RESISTOR_REBUILD",
            donor=OUT / "donors" / "biderwithresistor.pdsprj",
            base=base,
            templates=templates,
        ),
    ]
    for test_id, payload, generator in _cases():
        results.append(
            _convert_generated(
                test_id=test_id,
                payload=payload,
                generator=generator,
                base=base,
                templates=templates,
            )
        )

    summary = {
        "phase": "bidirectional_v1_temp",
        "donor_manifest_count": len(donor_manifest),
        "donor_validation": donor_validation,
        "case_count": len(results),
        "cases": results,
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT / "README_TEST_ORDER.txt").write_text(
        "BIDIRECTIONAL TERMINAL V1 TEMP TEST PACK\n\n"
        "Test only the .pdsprj files inside each T00-T10 folder.\n"
        "T00A and T00B are exact donor-record rebuild controls.\n"
        "For T01-T10, open the BIDIR project, inspect it, and simulate where applicable.\n"
        "The BASELINE folders are comparison artifacts and already use the locked old terminal method.\n\n"
        "Recommended order:\n"
        "T00A exact empty bidirectional-terminal rebuild\n"
        "T00B exact resistor bidirectional-terminal rebuild\n"
        "T01 one internal resistor\n"
        "T02 four resistors with power and ground\n"
        "T03 mixed resistor/capacitor\n"
        "T04 capacitor only with power and ground\n"
        "T05 inductor only with power and ground\n"
        "T06 RCL with power and ground\n"
        "T07 DC voltage source with RCL\n"
        "T08 DC voltage plus DC current source\n"
        "T09 two DC voltage sources\n"
        "T10 AC voltage source with RC\n\n"
        "Report for each case: opens, visual correctness, and simulation result/error.\n",
        encoding="utf-8",
    )

    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(OUT.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(OUT.parent).as_posix())
    print(json.dumps({"output": str(OUT), "archive": str(ARCHIVE), "cases": len(results)}, indent=2))


if __name__ == "__main__":
    main()
