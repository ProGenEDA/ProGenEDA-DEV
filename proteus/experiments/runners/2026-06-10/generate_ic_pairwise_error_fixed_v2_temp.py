"""Expand the accepted S01+S02 pairwise IC repair across matching V1 failures.

The user-tested S01+S02 sample proved that failed pairwise cases involving
accepted combinational families must be regenerated from fresh gate slices and
fresh CDB rows. This pack applies that rule to every rejected V1 pair where at
least one side is one of the locked combinational families S01..S07.

This deliberately does not regenerate V1-passed pairs, does not reuse the
rejected full V2 matrix, and does not emit non-combinational failure pairs that
need a separate no-model/CDB investigation.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes
from proteusgen.templates import FixtureRegistry


REPO = Path(__file__).resolve().parents[3]
OUT_ROOT = REPO / "experiments" / "ic_pairwise_error_fixed_v2_temp_2026_06_10"
ARCHIVE_PATH = REPO / "experiments" / "IC_PAIRWISE_ERROR_FIXED_V2_TEMP_2026_06_10.zip"

FOCUSED_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-10" / "generate_ic_pairwise_error_focused_v1_temp.py"
PAIRWISE_V1_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-10" / "generate_ic_pairwise_34_v1_temp.py"
CDB_V2_SCRIPT = REPO / "tools" / "proteus_generation" / "2026-06-09" / "generate_mixed_ic_cross_donor_v2_metadata_temp.py"

COMBINATIONAL_SOURCE_FAMILY = {
    "S01": "74hc00",
    "S02": "74hc02",
    "S03": "74hc04",
    "S04": "74hc08",
    "S05": "74hc32",
    "S06": "74hc86",
    "S07": "74hc266",
}


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


focused = _load_module("pairwise_error_focused_for_fixed_v2", FOCUSED_SCRIPT)
pairwise_v1 = _load_module("pairwise_v1_for_error_fixed_v2", PAIRWISE_V1_SCRIPT)
cdb_v2 = _load_module("mixed_cdb_v2_for_error_fixed_v2", CDB_V2_SCRIPT)
ic = focused.ic
seq = pairwise_v1.seq

PAIR_BY_SHORT = {
    tuple(sorted((case.left.short_id, case.right.short_id))): case
    for case in pairwise_v1.CASES
}
SOURCE_BY_SHORT = {source.short_id: source for source in pairwise_v1.SOURCES}


def _source_order(source_id: str) -> int:
    return int(source_id[1:])


def _gate_for_source(source_id: str, slot: int) -> ic.GateSpec:
    family = COMBINATIONAL_SOURCE_FAMILY[source_id]
    label = str(slot)
    if family == "74hc04":
        return ic.GateSpec(family, "A", f"I{label}", "", f"O{label}")
    return ic.GateSpec(family, "A", f"I{label}", f"J{label}", f"O{label}")


def _accepted_case_for_pair(original_case_id: str, left_id: str, right_id: str) -> ic.CircuitCase:
    gates = tuple(_gate_for_source(source_id, index + 1) for index, source_id in enumerate((left_id, right_id)))
    title = f"{left_id} plus {right_id} accepted combinational pair"
    expression = "; ".join(f"{gate.output} = {gate.family}:{gate.gate}" for gate in gates)
    description = (
        f"Replacement for failed pairwise {original_case_id}. "
        "Generated entirely through accepted combinational gate slices with fresh IDs and CDB rows."
    )
    return ic.CircuitCase(f"{original_case_id}_FIXED_ACCEPTED_COMBINATIONAL", title, expression, description, gates)


def _payload(chunk: bytes) -> bytes:
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        raise ValueError("Object chunk boundary is not 00...FF")
    return chunk[1:-1]


def _max_object_id(parsed) -> int:
    if not parsed.pin_rows:
        return 0
    return max(int.from_bytes(row[:4], "little") for _ref, row in parsed.pin_rows)


def _next_package_ref(used_refs: list[str]) -> str:
    used = set(used_refs)
    for index in range(1, 10):
        candidate = f"U{index}"
        if candidate not in used:
            return candidate
    raise ValueError("No U1..U9 package ref remains for accepted combinational repair.")


def _device_section_entry(key: str, donor: Path, section: bytes) -> dict[str, object]:
    return {
        "donor_key": key,
        "donor": str(donor.relative_to(REPO)) if donor.is_absolute() else str(donor),
        "section": bytearray(section),
        "old_tail_pointer": int.from_bytes(section[-4:], "little") if len(section) >= 4 else None,
        "size": len(section),
    }


def _accepted_gate_record_for_mixed(source_id: str, donor_parsed) -> tuple[bytes, bytes, dict[str, object], dict[str, object]]:
    gate = _gate_for_source(source_id, 1)
    package_ref = _next_package_ref(donor_parsed.pin_package_refs())
    package_number = int(package_ref[1:])
    object_id = _max_object_id(donor_parsed) + 1
    config = ic.FAMILIES[gate.family]
    if config.shape in {"hc08_script", "hc32_script"}:
        record, topology = ic._script_gate_record(
            config,
            gate,
            package_ref=package_ref,
            package_number=package_number,
            object_id=object_id,
            dx=pairwise_v1.SECOND_DONOR_DX,
            dy=0,
        )
    else:
        record, topology = ic._generic_gate_record(
            config,
            gate,
            package_ref=package_ref,
            object_id=object_id,
            dx=pairwise_v1.SECOND_DONOR_DX,
            dy=0,
        )
    package_row = {
        "family": gate.family,
        "device": config.device,
        "package_ref": package_ref,
        "package_number": package_number,
    }
    cdb = ic.build_cdb([topology], [package_row], [])
    return record, cdb, topology, package_row


def _static_issues(output: Path, expected_markers: tuple[str, ...]) -> list[str]:
    issues: list[str] = []
    info = seq.inspect_pdsprj(output)
    if not (info.has_project_xml and info.has_root_dsn and info.has_root_cdb and info.has_pwrails):
        issues.append("missing required internal project member")
    dsn = read_internal_file(output, "ROOT.DSN")
    cdb = read_internal_file(output, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    if not chunk or chunk[0] != 0 or chunk[-1] != 0xFF:
        issues.append("object chunk boundary is not 00...FF")
    for marker in expected_markers:
        if marker.encode("ascii") not in chunk:
            issues.append(f"missing DSN marker {marker}")
    try:
        parsed = pairwise_v1.split_cdb_generic(cdb)
        pin_refs = [ref for ref, _row in parsed.pin_rows]
        property_refs = parsed.property_package_refs()
        missing_property = sorted(set(pairwise_v1.package_ref(ref) for ref in pin_refs) - set(property_refs))
        if missing_property:
            issues.append(f"CDB pin package refs missing property rows: {missing_property}")
        row_ids = [int.from_bytes(row[:4], "little") for _ref, row in parsed.pin_rows]
        if len(row_ids) != len(set(row_ids)):
            issues.append(f"duplicate CDB object IDs: {row_ids}")
    except Exception as exc:
        issues.append(f"CDB parse failed: {exc}")
    return issues


def write_mixed_case(original_case, comb_id: str, donor_id: str) -> dict[str, object]:
    donor = SOURCE_BY_SHORT[donor_id]
    case_id = f"{original_case.case_id}_FIXED_ACCEPTED_PLUS_DONOR"
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"

    donor_dsn = read_internal_file(donor.donor, "ROOT.DSN")
    donor_chunk = _extract_object_chunk(donor_dsn)
    donor_parsed = pairwise_v1.split_cdb_generic(read_internal_file(donor.donor, "ROOT.CDB"))
    accepted_record, accepted_cdb, accepted_topology, package_row = _accepted_gate_record_for_mixed(comb_id, donor_parsed)
    accepted_parsed = pairwise_v1.split_cdb_generic(accepted_cdb)

    object_chunk = b"\x00" + _payload(donor_chunk) + accepted_record + b"\xff"
    cdb = pairwise_v1.build_cdb_from_generic_rows(
        donor_parsed,
        donor_parsed,
        accepted_parsed,
    )

    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    sections = [
        _device_section_entry(donor.case_id, donor.donor, seq._device_section(donor_dsn)),
        _device_section_entry(
            "accepted_combinational_combined",
            ic.COMBINED_DEVICE_DONOR,
            ic._combined_device_section(),
        ),
    ]
    dsn, pointers = cdb_v2.build_dsn_with_multi_device_sections(
        read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
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
    markers = (
        SOURCE_BY_SHORT[comb_id].proteus_marker,
        donor.proteus_marker,
    )
    manifest = {
        "case_id": case_id,
        "original_pair_case_id": original_case.case_id,
        "left": original_case.left.as_dict(),
        "right": original_case.right.as_dict(),
        "repair_method": "accepted_combinational_gate_slice_added_to_exact_donor_with_fresh_object_id_and_cdb_row",
        "accepted_combinational_source": comb_id,
        "exact_donor_source": donor_id,
        "accepted_topology": accepted_topology,
        "accepted_package_row": package_row,
        "section_pointers": pointers,
        "marker_counts": {marker: final_chunk.count(marker.encode("ascii")) for marker in markers},
        "cdb_marker_counts": {marker: final_cdb.count(marker.encode("ascii")) for marker in markers},
        "terminal_counts": {
            "$TERINPUT": final_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": final_chunk.count(b"$TEROUTPUT"),
            "$TERBIDIR": final_chunk.count(b"$TERBIDIR"),
        },
        "static_validation_issues": _static_issues(output, markers),
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


def write_accepted_pair_case(original_case, left_id: str, right_id: str) -> dict[str, object]:
    case = _accepted_case_for_pair(original_case.case_id, left_id, right_id)
    manifest = ic.write_case(case, out_root=OUT_ROOT)
    manifest["original_pair_case_id"] = original_case.case_id
    manifest["repair_method"] = "accepted_combinational_gate_slices_for_both_sides"
    case_dir = OUT_ROOT / case.case_id
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _supported_error_pairs() -> tuple[list[tuple[str, str, str]], list[dict[str, object]]]:
    selected: list[tuple[str, str, str]] = []
    deferred: list[dict[str, object]] = []
    for failure_class in ("duplicate_part_reference", "no_model_specified"):
        for raw_left, raw_right in focused.FAILED_PAIRS_FROM_V1_USER_NOTES[failure_class]:
            left, right = tuple(sorted((raw_left, raw_right), key=_source_order))
            comb_count = int(left in COMBINATIONAL_SOURCE_FAMILY) + int(right in COMBINATIONAL_SOURCE_FAMILY)
            if comb_count:
                selected.append((failure_class, left, right))
            else:
                deferred.append({"failure_class": failure_class, "pair": [left, right], "reason": "no accepted combinational side"})
    for left, right in focused.FAILED_PAIRS_FROM_V1_USER_NOTES["coordinate_artifact_only_in_v1"]:
        deferred.append(
            {
                "failure_class": "coordinate_artifact_only_in_v1",
                "pair": [left, right],
                "reason": "V1 coordinate-only cases are not regenerated in this error repair pack",
            }
        )
    return selected, deferred


def _write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 10, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    selected, deferred = _supported_error_pairs()
    manifests: list[dict[str, object]] = []
    for _failure_class, left_id, right_id in selected:
        original_case = PAIR_BY_SHORT[(left_id, right_id)]
        if left_id in COMBINATIONAL_SOURCE_FAMILY and right_id in COMBINATIONAL_SOURCE_FAMILY:
            manifests.append(write_accepted_pair_case(original_case, left_id, right_id))
        else:
            comb_id = left_id if left_id in COMBINATIONAL_SOURCE_FAMILY else right_id
            donor_id = right_id if comb_id == left_id else left_id
            manifests.append(write_mixed_case(original_case, comb_id, donor_id))

    issue_cases = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "IC_PAIRWISE_ERROR_FIXED_V2_TEMP_2026_06_10",
        "status": "pending_user_proteus_test",
        "basis": "S01+S02 accepted-combinational repair passed user Proteus testing.",
        "source_policy": "Only V1-reported rejected pairs are generated. V1-passed pairs are untouched.",
        "repair_policy": [
            "Accepted combinational + accepted combinational: regenerate both through locked combinational gate slices.",
            "Accepted combinational + exact donor: keep the exact non-combinational donor native and add the combinational gate with a fresh package ref, object id, and CDB row.",
            "Non-combinational-only failures are recorded as deferred, not emitted as likely-broken projects.",
        ],
        "generated_pair_count": len(manifests),
        "deferred_pair_count": len(deferred),
        "generated_pairs": [
            {
                "case_id": item["case_id"],
                "original_pair_case_id": item["original_pair_case_id"],
                "repair_method": item["repair_method"],
            }
            for item in manifests
        ],
        "deferred_pairs": deferred,
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
                "generated_pair_count": len(manifests),
                "deferred_pair_count": len(deferred),
                "static_issue_count": len(issue_cases),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
