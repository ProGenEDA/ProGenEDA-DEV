"""Generate mutation-isolation diagnostics after V14 generated cases failed.

User feedback for V14:

* T00 exact 4x donor repack worked.
* T00B 4x donor chunk + CDB inserted into E001 worked.
* Every generated case after that gave Bad Object Record and rendered a large
  field of pink corrupt wires.

That proves the packer and the supplied 4x donor are valid. This V15 pack keeps
the working 4x donor structure wherever possible and mutates only one boundary
at a time:

* terminal labels only
* V14-generated geometry/records but donor labels
* exact first-unit subset with alternative final-wire/CDB choices

Do not promote this code. It is a byte-level diagnostic pack.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "mixed_rcl_v15_mutation_isolation_temp_2026_06_02"
V14_PATH = Path(__file__).with_name("generate_mixed_rcl_v14_repeated_unit_temp.py")
V14_ROOT = REPO_ROOT / "experiments" / "mixed_rcl_v14_repeated_unit_temp_2026_06_02"

UNIT_STARTS = (256, 2262, 4268, 6274)
UNIT_SIZE_NONFINAL = 2006
POWER_BRIDGE_END = 256

# (name, unit-relative record start, label length byte offset inside record)
TERMINAL_LABEL_SITES = (
    ("cap_out", 0, 31),
    ("cap_in", 104, 30),
    ("l_in", 672, 30),
    ("r_in", 775, 30),
    ("l_out", 878, 31),
    ("r_out", 1455, 31),
)


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {name} from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "WIRE",
        "RESISTOR",
        "REALIND",
        "CAPACITOR",
        "CAP10",
        "COMPONENT ID",
        "COMPONENT VALUE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _object_chunk(project_path: Path) -> bytes:
    return rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))


def _patch_two_char_label(chunk: bytearray, abs_len_offset: int, label: str) -> None:
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError("V15 label mutations require two-character ASCII labels.")
    if chunk[abs_len_offset] != 2:
        raise RuntimeError(f"Expected two-character terminal label at object offset {abs_len_offset}.")
    chunk[abs_len_offset + 1 : abs_len_offset + 3] = raw


def _labels_for_unit(unit_index: int, mode: str) -> dict[str, str]:
    if mode == "unit1_a_b":
        if unit_index == 1:
            return {"cap_out": "B1", "cap_in": "A1", "l_in": "B1", "r_in": "V0", "l_out": "G0", "r_out": "A1"}
        return {"cap_out": "X1", "cap_in": "VT", "l_in": "X1", "r_in": "V0", "l_out": "G0", "r_out": "VT"}
    if mode == "all_unique_a_b":
        return {
            "cap_out": f"B{unit_index}",
            "cap_in": f"A{unit_index}",
            "l_in": f"B{unit_index}",
            "r_in": "V0",
            "l_out": "G0",
            "r_out": f"A{unit_index}",
        }
    if mode == "all_same_n":
        return {"cap_out": "N2", "cap_in": "N1", "l_in": "N2", "r_in": "V0", "l_out": "G0", "r_out": "N1"}
    if mode == "donor":
        return {"cap_out": "X1", "cap_in": "VT", "l_in": "X1", "r_in": "V0", "l_out": "G0", "r_out": "VT"}
    raise ValueError(mode)


def _mutate_labels(chunk: bytes, mode: str) -> tuple[bytes, list[dict[str, Any]]]:
    out = bytearray(chunk)
    topology: list[dict[str, Any]] = []
    for unit_index, unit_start in enumerate(UNIT_STARTS, start=1):
        labels = _labels_for_unit(unit_index, mode)
        for name, rel_start, len_offset in TERMINAL_LABEL_SITES:
            abs_len_offset = unit_start + rel_start + len_offset
            before = out[abs_len_offset + 1 : abs_len_offset + 3].decode("ascii")
            after = labels[name]
            _patch_two_char_label(out, abs_len_offset, after)
            topology.append({"unit": unit_index, "terminal": name, "before": before, "after": after, "offset": abs_len_offset})
    return bytes(out), topology


def _restore_donor_labels(generated_chunk: bytes) -> tuple[bytes, list[dict[str, Any]]]:
    return _mutate_labels(generated_chunk, "donor")


def _first_unit_subset(donor_chunk: bytes, *, final_mode: str) -> bytes:
    out = bytearray(donor_chunk[:POWER_BRIDGE_END])
    unit = bytearray(donor_chunk[UNIT_STARTS[0] : UNIT_STARTS[1]])
    if final_mode == "set_unit1_wire_ff":
        unit[-1] = 0xFF
    elif final_mode == "append_extra_ff":
        unit[-1] = 0x00
        unit.append(0xFF)
    else:
        raise ValueError(final_mode)
    out += unit
    return bytes(out)


def _first_specs(v14: Any) -> list[Any]:
    return list(v14._unit_specs(1, global_ids=(1, 2, 3)))


def _write_project_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    topology: list[dict[str, Any]],
    expected_result: str,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_project, "ROOT.DSN"), object_chunk)
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
    issues: list[str] = []
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    if not object_chunk or object_chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not object_chunk or object_chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v15_mutation_isolation_not_locked",
        "description": description,
        "expected_result": expected_result,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "topology": topology,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            chunk_path.name: rv9._sha256_file(chunk_path),
            "object_chunk": rv9._sha256_bytes(object_chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nExpected diagnostic meaning: {expected_result}\n\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    v14 = _load_module("mixed_rcl_v14_for_v15", V14_PATH)
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")

    base = registry.get("e001_empty").path
    donor = registry.get("rcl_4x_t07_unit_donor").path
    donor_chunk = _object_chunk(donor)
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    first_cdb = v14._build_rcl_cdb(_first_specs(v14))
    v14_t05_project = V14_ROOT / "RCL_V14_T05_4X_UNIT_SUPPLIED_ID_GAPS" / "RCL_V14_T05_4X_UNIT_SUPPLIED_ID_GAPS.pdsprj"
    if not v14_t05_project.exists():
        raise RuntimeError(f"Required V14 T05 project not found: {v14_t05_project}")
    v14_t05_chunk = _object_chunk(v14_t05_project)
    if len(v14_t05_chunk) != len(donor_chunk):
        raise RuntimeError("V14 T05 chunk length no longer matches donor; regenerate V14 before V15.")

    cases: list[dict[str, Any]] = []
    cases.append(
        _write_project_case(
            case_id="RCL_V15_T00_4X_DONOR_CHUNK_IN_E001_CONTROL",
            description="Known-good control: exact supplied 4x object chunk and CDB inserted into E001.",
            base_project=base,
            donor_project=donor,
            object_chunk=donor_chunk,
            cdb=donor_cdb,
            topology=[],
            expected_result="Must work. If this fails, the test environment changed from V14 feedback.",
        )
    )

    for case_id, description, mode, expected in [
        (
            "RCL_V15_T01_LABEL_ONLY_UNIT1_A1_B1",
            "Only first donor unit terminal labels are changed from VT/X1 to A1/B1. Geometry, CDB, object count, and component records remain donor-exact.",
            "unit1_a_b",
            "If this fails, arbitrary two-character terminal label mutation is corrupting this donor family.",
        ),
        (
            "RCL_V15_T02_LABEL_ONLY_ALL_UNIQUE_A_B",
            "All four donor units keep donor geometry/CDB but use unique A#/B# terminal labels.",
            "all_unique_a_b",
            "If T01 passes but this fails, repeated-unit unique net labels are the failing boundary.",
        ),
        (
            "RCL_V15_T03_LABEL_ONLY_ALL_SAME_N1_N2",
            "All four donor units keep donor geometry/CDB and use the same N1/N2 labels on every unit.",
            "all_same_n",
            "If this passes while A#/B# fails, the exact label spellings or uniqueness policy matter.",
        ),
    ]:
        chunk, topology = _mutate_labels(donor_chunk, mode)
        cases.append(
            _write_project_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_project=donor,
                object_chunk=chunk,
                cdb=donor_cdb,
                topology=topology,
                expected_result=expected,
            )
        )

    restored_chunk, restored_topology = _restore_donor_labels(v14_t05_chunk)
    cases.append(
        _write_project_case(
            case_id="RCL_V15_T04_V14_T05_WITH_DONOR_LABELS",
            description="The failed V14 T05 generated 4x chunk, but all terminal labels are restored to donor labels VT/X1/V0/G0. CDB remains donor-exact.",
            base_project=base,
            donor_project=donor,
            object_chunk=restored_chunk,
            cdb=donor_cdb,
            topology=restored_topology,
            expected_result="If label-only cases pass but this fails, the corruption is in coordinate/component record mutation rather than terminal labels.",
        )
    )

    first_50 = _first_unit_subset(donor_chunk, final_mode="set_unit1_wire_ff")
    first_51 = _first_unit_subset(donor_chunk, final_mode="append_extra_ff")
    for case_id, description, chunk, cdb, expected in [
        (
            "RCL_V15_T05_1X_EXACT_UNIT1_50B_FINAL_3CDB",
            "Exact first donor unit only; original 50-byte right wire has its final byte set to FF; CDB contains only C1/L1/R1.",
            first_50,
            first_cdb,
            "If this fails, shortening the 4x donor object stream is not safe with this DSN header/model.",
        ),
        (
            "RCL_V15_T06_1X_EXACT_UNIT1_50B_FINAL_FULL_CDB",
            "Exact first donor unit only; original 50-byte right wire has its final byte set to FF; CDB remains the full 4x donor CDB.",
            first_50,
            donor_cdb,
            "If T05 fails but this works, the object stream can be shortened but CDB table cardinality must remain donor-like.",
        ),
        (
            "RCL_V15_T07_1X_EXACT_UNIT1_51B_FINAL_3CDB",
            "Exact first donor unit only; an extra FF byte is appended after the original 50-byte right wire, matching the V14 generated final-wire length.",
            first_51,
            first_cdb,
            "If T05 works but this fails, V14's 51-byte final wire is invalid for a shortened one-unit stream.",
        ),
    ]:
        cases.append(
            _write_project_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_project=donor,
                object_chunk=chunk,
                cdb=cdb,
                topology=[],
                expected_result=expected,
            )
        )

    summary = {
        "batch_id": "MIXED_RCL_V15_MUTATION_ISOLATION_STATIC_20260602",
        "status": "static_generated_awaiting_user_proteus_open_test",
        "source_feedback": "V14 T00 and T00B worked, proving donor import and E001 transplant are valid; every generated case after T00B gave Bad Object Record and corrupt pink wires.",
        "method": "Keep the working 4x donor object stream and CDB wherever possible, then mutate terminal labels, generated-coordinate records, and first-unit stream shortening independently.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "expected_result": item["expected_result"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V15 mutation-isolation diagnostic pack.\n\nOpen in order and stop at the first Bad Object Record or corrupt pink-wire render:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(cases, 1))
        + "\n\nReport which cases work and which first fails. T01-T03 isolate terminal labels; T04 isolates generated coordinate/component mutation; T05-T07 isolate whether a one-unit subset is valid.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(REPO_ROOT / "experiments" / "MIXED_RCL_V15_MUTATION_ISOLATION_TEMP_2026_06_02"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "case_count": len(cases), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
