"""Retry cross-donor mixed IC probes with safer metadata handling.

V1 used whole IC regions from accepted donors but concatenated complete donor
device sections without patching every embedded object-data pointer. User
testing reported LXLCORE.dll errors for T01/T06 and startup crashes for the
others. This V2 keeps the V1 visible object regions but changes two metadata
rules only:

- patch the final object-data pointer inside every concatenated donor device
  section, not just the last section;
- sort selected CDB rows by numeric U reference before writing ROOT.CDB.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
V1_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_cross_donor_v1_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_cross_donor_v2_metadata_temp_2026_06_09"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_CROSS_DONOR_V2_METADATA_TEMP_2026_06_09.zip"


def load_v1_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_v1_for_v2", V1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load V1 helper from {V1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = load_v1_module()
seq = v1.seq
mixed = v1.mixed


def ref_number(ref: str) -> int:
    match = re.fullmatch(r"U(\d+)", ref)
    if not match:
        raise ValueError(f"Unsupported component reference {ref!r}")
    return int(match.group(1))


def build_cross_cdb_sorted(selections) -> tuple[bytes, list[dict[str, object]]]:
    ref_sources: list[tuple[str, str]] = []
    for selection in selections:
        for ref in selection.cdb_refs:
            ref_sources.append((selection.donor_key, ref))
    ref_sources.sort(key=lambda item: ref_number(item[1]))
    refs = [ref for _donor_key, ref in ref_sources]
    if len(refs) != len(set(refs)):
        raise ValueError(f"Cross-donor case has duplicate CDB refs: {refs}")

    parts_by_donor = {}
    for donor_key, _ref in ref_sources:
        if donor_key not in parts_by_donor:
            donor = v1.donor_by_key(donor_key)
            parts_by_donor[donor_key] = v1.cdb_parts(seq.read_internal_file(donor.path, "ROOT.CDB"))

    first_parts = parts_by_donor[ref_sources[0][0]]
    header = bytearray(first_parts.header)
    if len(header) <= 92:
        raise ValueError("CDB header is too short for the observed component-count byte.")
    header[92] = len(ref_sources)

    pin_rows: list[bytes] = []
    prop_rows: list[bytes] = []
    row_plan: list[dict[str, object]] = []
    for donor_key, ref in ref_sources:
        parts = parts_by_donor[donor_key]
        if ref not in parts.pin_rows or ref not in parts.prop_rows:
            raise ValueError(f"{donor_key} CDB does not contain ref {ref}")
        pin_rows.append(parts.pin_rows[ref])
        prop_rows.append(parts.prop_rows[ref])
        row_plan.append(
            {
                "donor_key": donor_key,
                "ref": ref,
                "pin_row_size": len(parts.pin_rows[ref]),
                "prop_row_size": len(parts.prop_rows[ref]),
                "sort_key": ref_number(ref),
            }
        )
    return bytes(header) + b"".join(pin_rows) + first_parts.post_pin_header + b"".join(prop_rows), row_plan


def device_sections_for(selections) -> list[dict[str, object]]:
    sections: list[dict[str, object]] = []
    seen: set[str] = set()
    for selection in selections:
        if selection.donor_key in seen:
            continue
        seen.add(selection.donor_key)
        donor = v1.donor_by_key(selection.donor_key)
        section = bytearray(seq._device_section(seq.read_internal_file(donor.path, "ROOT.DSN")))
        sections.append(
            {
                "donor_key": selection.donor_key,
                "donor": str(donor.path.relative_to(REPO)),
                "section": section,
                "old_tail_pointer": int.from_bytes(section[-4:], "little") if len(section) >= 4 else None,
                "size": len(section),
            }
        )
    return sections


def build_dsn_with_multi_device_sections(base_dsn: bytes, donor_dsn: bytes, object_chunk: bytes, sections: list[dict[str, object]]):
    e0_first = base_dsn.find(b"ISIS CIRCUIT FILE")
    e0_second = base_dsn.find(b"ISIS CIRCUIT FILE", e0_first + 1)
    donor_first = donor_dsn.find(b"ISIS CIRCUIT FILE")
    donor_obj = donor_dsn.find(b"OBJECT DATA", donor_first)
    marker = b"{PACKAGE=NULL}\n\x00"
    insert = base_dsn.rfind(marker, 0, e0_first)
    if min(e0_first, e0_second, donor_first, donor_obj, insert) < 0:
        raise ValueError("Base or donor ROOT.DSN does not match the accepted section model.")
    insert += len(marker)

    total_device_size = sum(int(item["size"]) for item in sections)
    first_header = donor_dsn[donor_first : donor_obj + len(b"OBJECT DATA")]
    tail = bytearray(base_dsn[e0_second:])
    first_isis = insert + total_device_size
    second_isis = first_isis + len(first_header) + len(object_chunk)
    second_obj = second_isis + tail.find(b"OBJECT DATA")
    object_data_pointer = second_obj + 13

    patched_sections: list[bytes] = []
    section_plan: list[dict[str, object]] = []
    running_offset = insert
    for item in sections:
        section = bytearray(item["section"])
        if len(section) >= 4:
            section[-4:] = seq._u32(object_data_pointer)
        patched_sections.append(bytes(section))
        section_plan.append(
            {
                "donor_key": item["donor_key"],
                "donor": item["donor"],
                "start": running_offset,
                "size": item["size"],
                "old_tail_pointer": item["old_tail_pointer"],
                "new_tail_pointer": object_data_pointer,
            }
        )
        running_offset += int(item["size"])

    cct = tail.find(b"CCT000")
    if cct != -1:
        tail[cct + len(b"CCT000") + 2 : cct + len(b"CCT000") + 6] = seq._u32(first_isis)
    default = tail.find(b"__DEFAULT__\x00\x00")
    if default != -1:
        tail[default + len(b"__DEFAULT__\x00\x00") : default + len(b"__DEFAULT__\x00\x00") + 4] = seq._u32(
            second_isis
        )
    dsn = bytes(bytearray(base_dsn[:insert]) + b"".join(patched_sections) + first_header + bytearray(object_chunk) + tail)
    return dsn, {
        "insert": insert,
        "first_isis": first_isis,
        "second_isis": second_isis,
        "second_object_data": second_obj,
        "object_data_pointer": object_data_pointer,
        "device_sections": section_plan,
    }


def write_case(case) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    fragments: list[bytes] = []
    region_plan: list[dict[str, object]] = []
    for selection in case.selections:
        selected, metadata = v1.selected_fragments(selection)
        fragments.extend(selected)
        region_plan.extend(metadata)
    object_chunk = b"\x00" + b"".join(fragments) + b"\xff"
    cdb, row_plan = build_cross_cdb_sorted(case.selections)
    sections = device_sections_for(case.selections)

    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    first_donor = v1.donor_by_key(case.selections[0].donor_key)
    donor_dsn = seq.read_internal_file(first_donor.path, "ROOT.DSN")
    dsn, pointers = build_dsn_with_multi_device_sections(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        object_chunk,
        sections,
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "method": "v2_cross_donor_region_concat_sorted_cdb_rows_all_device_tail_pointers_patched",
        "changed_from_v1": [
            "Every donor device section tail pointer is patched to the generated object-data pointer.",
            "CDB rows are sorted by numeric U reference before emission.",
        ],
        "status": "temporary_pending_user_proteus_testing",
        "terminal_policy": "all retained visible endpoints use donor-native $TERBIDIR records with generated unique labels",
        "composition_policy": "same visible IC regions as V1; no analog/passive regions; no component ref rewriting",
        "selections": [
            {
                "donor_key": selection.donor_key,
                "markers": selection.markers,
                "cdb_refs": selection.cdb_refs,
                "label_prefix": selection.label_prefix,
            }
            for selection in case.selections
        ],
        "expected_markers": case.expected_markers,
        "region_plan": region_plan,
        "cdb_row_plan": row_plan,
        "section_pointers": pointers,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": mixed.marker_counts(chunk) | {"7447": chunk.count(b"7447")},
        "cdb_marker_counts": mixed.marker_counts(cdb) | {"7447": cdb.count(b"7447")},
        "object_chunk_size": len(chunk),
        "static_validation_issues": v1.static_issues(output, case, row_plan),
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
        },
    }
    if not all(
        item["new_tail_pointer"] == pointers["object_data_pointer"]
        for item in pointers["device_sections"]
    ):
        manifest["static_validation_issues"].append("not all device-section tail pointers match object-data pointer")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(seq.bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


def write_archive() -> str:
    if ARCHIVE_PATH.exists():
        ARCHIVE_PATH.unlink()
    with ZipFile(ARCHIVE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if file_path.is_file():
                info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
                info.date_time = (2026, 6, 9, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    manifests = [write_case(case) for case in v1.CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_CROSS_DONOR_V2_METADATA_TEMP_2026_06_09",
        "purpose": "Retry V1 cross-donor IC mixes after crash/LXLCORE reports by fixing device-section pointers and CDB row order.",
        "status": "temporary_pending_user_proteus_testing",
        "composition_policy": "same whole IC regions as V1; all concatenated device-section tail pointers patched; sorted CDB U rows",
        "terminal_policy": "all retained visible endpoints use relabeled $TERBIDIR records",
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "archive": str(ARCHIVE_PATH.relative_to(REPO)),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE_PATH),
                "archive_sha256": archive_hash,
                "static_issue_cases": summary_issues,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
