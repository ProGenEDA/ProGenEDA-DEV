"""Generate broader pairwise probes using the accepted combinational-side method.

V2 proved in user Proteus testing that failed pairwise cases work when any
accepted combinational IC side is regenerated from fresh gate slices instead of
copying that donor's full exact-rezip object/CDB records.

This pack applies that accepted path to every unordered pair that contains at
least one accepted combinational source, not only the V1-reported failures. It
also emits a small non-combinational-only probe pack using the closest analogue
available for non-combinational donors: preserve both native donor chunks but
renumber the right-side CDB object IDs after same-length U-ref remapping.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import package_ref
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes
from proteusgen.templates import FixtureRegistry


REPO = Path(__file__).resolve().parents[4]
FIXED_V2_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-10" / "generate_ic_pairwise_error_fixed_v2_temp.py"

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_pairwise_combinational_method_v1_temp_2026_06_11"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "IC_PAIRWISE_COMBINATIONAL_METHOD_V1_TEMP_2026_06_11.zip"

NONCOMB_PROBE_PAIRS = (
    ("S08", "S09"),
    ("S08", "S10"),
    ("S08", "S12"),
    ("S08", "S14"),
    ("S08", "S16"),
    ("S08", "S29"),
    ("S08", "S30"),
    ("S15", "S21"),
    ("S21", "S22"),
    ("S21", "S23"),
    ("S21", "S24"),
    ("S21", "S25"),
    ("S21", "S26"),
    ("S21", "S27"),
    ("S21", "S29"),
    ("S22", "S27"),
    ("S22", "S29"),
    ("S21", "S32"),
    ("S21", "S33"),
    ("S22", "S32"),
    ("S22", "S33"),
)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


fixed = _load_module("pairwise_error_fixed_v2_for_comb_method_v1", FIXED_V2_SCRIPT)
pairwise_v1 = fixed.pairwise_v1
cdb_v2 = fixed.cdb_v2
seq = pairwise_v1.seq


def _source_order(source_id: str) -> int:
    return int(source_id[1:])


def _comb_count(left_id: str, right_id: str) -> int:
    return int(left_id in fixed.COMBINATIONAL_SOURCE_FAMILY) + int(right_id in fixed.COMBINATIONAL_SOURCE_FAMILY)


def all_pairs_with_combinational_side():
    return [
        case
        for case in pairwise_v1.CASES
        if _comb_count(case.left.short_id, case.right.short_id)
    ]


def _supported_noncomb_probe_pairs():
    cases = []
    for raw_left, raw_right in NONCOMB_PROBE_PAIRS:
        left, right = tuple(sorted((raw_left, raw_right), key=_source_order))
        if _comb_count(left, right):
            raise ValueError(f"Probe pair {left}+{right} unexpectedly includes a combinational source")
        cases.append(pairwise_v1.PAIR_BY_SHORT[(left, right)] if hasattr(pairwise_v1, "PAIR_BY_SHORT") else None)
    if all(item is not None for item in cases):
        return cases
    pair_by_short = {
        tuple(sorted((case.left.short_id, case.right.short_id), key=_source_order)): case
        for case in pairwise_v1.CASES
    }
    return [pair_by_short[tuple(sorted(pair, key=_source_order))] for pair in NONCOMB_PROBE_PAIRS]


def _u32_at(row: bytes, offset: int) -> int:
    return int.from_bytes(row[offset : offset + 4], "little")


def _patch_u32(row: bytes, offset: int, value: int) -> bytes:
    data = bytearray(row)
    data[offset : offset + 4] = int(value).to_bytes(4, "little")
    return bytes(data)


def _max_ids(parsed) -> int:
    ids: list[int] = []
    for _ref, row in parsed.pin_rows:
        ids.append(_u32_at(row, 0))
        if len(row) >= 16:
            ids.append(_u32_at(row, 12))
    for _ref, row in parsed.property_rows:
        ids.append(_u32_at(row, 0))
    return max(ids) if ids else 0


def _renumber_right_rows(parsed, used_left_ids: set[int]):
    used_ids = set(used_left_ids)
    next_id = max(used_ids) if used_ids else 0

    def next_free_id() -> int:
        nonlocal next_id
        next_id += 1
        while next_id in used_ids:
            next_id += 1
        used_ids.add(next_id)
        return next_id

    pin_rows = []
    package_ids: dict[str, int] = {}
    id_plan = []
    for ref, row in parsed.pin_rows:
        old_id = _u32_at(row, 0)
        old_id_2 = _u32_at(row, 12) if len(row) >= 16 else None
        if old_id in used_ids or (old_id_2 is not None and old_id_2 in used_ids):
            new_id = next_free_id()
        else:
            new_id = old_id
            used_ids.add(new_id)
            if old_id_2 is not None:
                used_ids.add(old_id_2)
        new_row = _patch_u32(row, 0, new_id)
        if len(new_row) >= 16:
            new_row = _patch_u32(new_row, 12, new_id)
        pin_rows.append((ref, new_row))
        package_ids.setdefault(package_ref(ref), new_id)
        id_plan.append(
            {
                "row_type": "pin",
                "ref": ref,
                "old_id": old_id,
                "old_id_2": old_id_2,
                "new_id": new_id,
                "changed": new_id != old_id or (old_id_2 is not None and new_id != old_id_2),
            }
        )

    property_rows = []
    for ref, row in parsed.property_rows:
        old_id = _u32_at(row, 0)
        pin_package_id = package_ids.get(package_ref(ref))
        if pin_package_id is not None and pin_package_id != old_id and old_id in used_left_ids:
            new_id = pin_package_id
        elif old_id in used_ids:
            new_id = next_free_id()
        else:
            new_id = old_id
            used_ids.add(new_id)
        property_rows.append((ref, _patch_u32(row, 0, new_id)))
        id_plan.append({"row_type": "property", "ref": ref, "old_id": old_id, "new_id": new_id, "changed": new_id != old_id})

    return pairwise_v1.GenericCdb(
        prefix=parsed.prefix,
        pin_rows=tuple(pin_rows),
        between_sections=parsed.between_sections,
        property_rows=tuple(property_rows),
        suffix=parsed.suffix,
    ), id_plan


def _cdb_for_noncomb_probe(left, right, ref_map):
    left_parsed = pairwise_v1.split_cdb_generic(read_internal_file(left.donor, "ROOT.CDB"))
    right_cdb = pairwise_v1.patch_refs(read_internal_file(right.donor, "ROOT.CDB"), ref_map)
    right_parsed = pairwise_v1.split_cdb_generic(right_cdb)
    used_left_ids = set()
    for _ref, row in left_parsed.pin_rows:
        used_left_ids.add(_u32_at(row, 0))
        if len(row) >= 16:
            used_left_ids.add(_u32_at(row, 12))
    for _ref, row in left_parsed.property_rows:
        used_left_ids.add(_u32_at(row, 0))
    right_parsed, id_plan = _renumber_right_rows(right_parsed, used_left_ids)
    cdb = pairwise_v1.build_cdb_from_generic_rows(left_parsed, left_parsed, right_parsed)
    cdb_plan = {
        "left_pin_refs": [ref for ref, _row in left_parsed.pin_rows],
        "right_pin_refs_after_map": [ref for ref, _row in right_parsed.pin_rows],
        "left_property_refs": [ref for ref, _row in left_parsed.property_rows],
        "right_property_refs_after_map": [ref for ref, _row in right_parsed.property_rows],
        "combined_pin_refs": [ref for ref, _row in left_parsed.pin_rows + right_parsed.pin_rows],
        "combined_property_refs": [ref for ref, _row in left_parsed.property_rows + right_parsed.property_rows],
        "combined_count": left_parsed.count + right_parsed.count,
        "right_id_renumber_plan": id_plan,
    }
    return cdb, cdb_plan


def _static_issues_noncomb(output: Path, left, right, ref_map) -> list[str]:
    issues = pairwise_v1.static_issues(output, left, right, ref_map)
    cdb = read_internal_file(output, "ROOT.CDB")
    try:
        parsed = pairwise_v1.split_cdb_generic(cdb)
        pin_ids = [_u32_at(row, 0) for _ref, row in parsed.pin_rows]
        pin_ids_2 = [_u32_at(row, 12) for _ref, row in parsed.pin_rows if len(row) >= 16]
        property_ids = [_u32_at(row, 0) for _ref, row in parsed.property_rows]
        if len(pin_ids) != len(set(pin_ids)):
            issues.append(f"duplicate CDB pin row ids: {pin_ids}")
        if len(pin_ids_2) != len(set(pin_ids_2)):
            issues.append(f"duplicate CDB pin secondary ids: {pin_ids_2}")
        package_refs = [package_ref(ref) for ref, _row in parsed.pin_rows]
        property_refs = parsed.property_package_refs()
        missing_props = sorted(set(package_refs) - set(property_refs), key=lambda item: int(item[1:]))
        if missing_props:
            issues.append(f"CDB pin package refs missing property rows: {missing_props}")
        if len(property_ids) != len(set(property_ids)):
            issues.append(f"duplicate CDB property row ids: {property_ids}")
    except Exception as exc:
        issues.append(f"CDB id validation failed: {exc}")
    return issues


def write_noncomb_probe_case(case) -> dict[str, object]:
    case_id = f"{case.case_id}_NONCOMB_FRESH_CDB_IDS_PROBE"
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    left_dsn = read_internal_file(case.left.donor, "ROOT.DSN")
    right_dsn = read_internal_file(case.right.donor, "ROOT.DSN")
    left_chunk = _extract_object_chunk(left_dsn)
    right_chunk = _extract_object_chunk(right_dsn)
    ref_map = pairwise_v1.same_length_ref_map(
        pairwise_v1.cdb_package_refs(case.left.donor),
        pairwise_v1.cdb_package_refs(case.right.donor),
    )
    right_chunk = pairwise_v1.patch_refs(right_chunk, ref_map)
    right_chunk, terminal_label_plan = pairwise_v1.patch_second_terminal_labels(right_chunk)
    right_chunk, translation_plan = pairwise_v1.translate_chunk(
        right_chunk,
        pairwise_v1.SECOND_DONOR_DX,
        pairwise_v1.SECOND_DONOR_DY,
    )
    object_chunk = b"\x00" + pairwise_v1.payload(left_chunk) + pairwise_v1.payload(right_chunk) + b"\xff"
    cdb, cdb_plan = _cdb_for_noncomb_probe(case.left, case.right, ref_map)
    sections = pairwise_v1.device_sections_for(case.left, case.right)

    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = cdb_v2.build_dsn_with_multi_device_sections(
        read_internal_file(base.path, "ROOT.DSN"),
        left_dsn,
        object_chunk,
        sections,
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_cdb = read_internal_file(output, "ROOT.CDB")
    final_chunk = _extract_object_chunk(final_dsn)
    issues = _static_issues_noncomb(output, case.left, case.right, ref_map)
    manifest = {
        "case_id": case_id,
        "original_pair_case_id": case.case_id,
        "description": f"Non-combinational probe: {case.left.family} with {case.right.family}.",
        "method": "native_donor_pair_with_same_length_ref_map_and_right_side_fresh_cdb_object_ids",
        "status": "experimental_noncomb_probe_pending_user_proteus_testing",
        "left": case.left.as_dict(),
        "right": case.right.as_dict(),
        "ref_map_right": ref_map,
        "terminal_label_plan_right": terminal_label_plan,
        "translation_plan_right": translation_plan,
        "cdb_plan": cdb_plan,
        "device_sections": [
            {
                "donor_key": item["donor_key"],
                "donor": item["donor"],
                "size": item["size"],
                "old_tail_pointer": item["old_tail_pointer"],
            }
            for item in sections
        ],
        "section_pointers": pointers,
        "marker_counts": {
            marker: final_chunk.count(marker.encode("ascii"))
            for marker in sorted({case.left.proteus_marker, case.right.proteus_marker})
        },
        "cdb_marker_counts": {
            marker: final_cdb.count(marker.encode("ascii"))
            for marker in sorted({case.left.proteus_marker, case.right.proteus_marker})
        },
        "static_validation_issues": issues,
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(final_dsn),
            "ROOT.CDB": _sha256_bytes(final_cdb),
            "object_chunk": _sha256_bytes(final_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "object_chunk.bin").write_bytes(final_chunk)
    (case_dir / "ROOT.DSN.bin").write_bytes(final_dsn)
    (case_dir / "ROOT.CDB.bin").write_bytes(final_cdb)
    return manifest


def write_combinational_method_case(case) -> dict[str, object]:
    left_id = case.left.short_id
    right_id = case.right.short_id
    if left_id in fixed.COMBINATIONAL_SOURCE_FAMILY and right_id in fixed.COMBINATIONAL_SOURCE_FAMILY:
        return fixed.write_accepted_pair_case(case, left_id, right_id)
    comb_id = left_id if left_id in fixed.COMBINATIONAL_SOURCE_FAMILY else right_id
    donor_id = right_id if comb_id == left_id else left_id
    return fixed.write_mixed_case(case, comb_id, donor_id)


def _write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 11, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    fixed.OUT_ROOT = OUT_ROOT

    comb_cases = all_pairs_with_combinational_side()
    comb_manifests = [write_combinational_method_case(case) for case in comb_cases]
    noncomb_cases = _supported_noncomb_probe_pairs()
    noncomb_manifests = [write_noncomb_probe_case(case) for case in noncomb_cases]

    all_manifests = comb_manifests + noncomb_manifests
    issue_cases = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in all_manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_PAIRWISE_COMBINATIONAL_METHOD_V1_TEMP_2026_06_11",
        "status": "temporary_pending_user_proteus_testing",
        "basis": "IC_PAIRWISE_ERROR_FIXED_V2 passed user Proteus testing for all 65 generated cases.",
        "combinational_method_policy": [
            "Every pair containing S01..S07 is regenerated through the accepted combinational-side method.",
            "Accepted combinational + accepted combinational uses fresh gate slices for both sides.",
            "Accepted combinational + non-combinational keeps the non-combinational exact donor native and adds a fresh generated gate slice.",
        ],
        "noncomb_probe_policy": [
            "Non-combinational-only probes are not promoted.",
            "They preserve both exact donor chunks but renumber right-side CDB pin/property IDs after U-ref remapping.",
            "This tests whether the accepted fresh-identity principle can transfer beyond combinational gates.",
        ],
        "source_count": len(pairwise_v1.SOURCES),
        "combinational_method_pair_count": len(comb_manifests),
        "noncomb_probe_pair_count": len(noncomb_manifests),
        "cases": [
            {
                "case_id": item["case_id"],
                "original_pair_case_id": item.get("original_pair_case_id"),
                "method": item.get("repair_method") or item.get("method"),
            }
            for item in all_manifests
        ],
        "static_issue_cases": issue_cases,
        "archive": str(ARCHIVE_PATH.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = _write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE_PATH),
                "archive_sha256": archive_hash,
                "combinational_method_pair_count": len(comb_manifests),
                "noncomb_probe_pair_count": len(noncomb_manifests),
                "static_issue_count": len(issue_cases),
                "static_issue_cases_sample": list(issue_cases)[:10],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
