"""Retry cross-donor mixed IC probes with filtered device definitions.

V2 still failed in Proteus, so the whole-device-section merge is rejected. The
device section appears to be a sequence of length-prefixed per-device
definitions followed by one final object-data pointer footer. V3 extracts only
the needed per-device definitions from donor sections, omits donor section
footers, and emits a single generated footer through the accepted single-section
builder.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
V2_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_cross_donor_v2_metadata_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_cross_donor_v3_filtered_device_temp_2026_06_09"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_CROSS_DONOR_V3_FILTERED_DEVICE_TEMP_2026_06_09.zip"


def load_v2_module():
    spec = importlib.util.spec_from_file_location("mixed_ic_cross_donor_v2_for_v3", V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load V2 helper from {V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v2 = load_v2_module()
v1 = v2.v1
seq = v2.seq
mixed = v2.mixed


DEVICE_MARKERS = (
    "74HC595",
    "74HC165",
    "7447",
    "74HC157",
    "74HC283",
    "74HC85",
    "74HC193",
    "74HC192",
    "4017",
    "4020",
    "74HC4024",
    "4518",
    "74HC4060",
    "74HC4040",
    "7490",
    "74HC160",
    "74HC161",
    "74HC163",
)

BOUNDARY_MARKERS = DEVICE_MARKERS + (
    "CAP",
    "CAP-ELEC",
    "LM741",
    "NPN",
    "PNP",
    "REALIND",
    "RESISTOR",
)


def marker_to_device(marker: str) -> str:
    return marker


def device_definition_starts(section: bytes) -> list[tuple[int, str]]:
    starts: list[tuple[int, str]] = []
    for marker in BOUNDARY_MARKERS:
        raw = marker.encode("ascii")
        pos = section.find(raw)
        if pos > 0 and section[pos - 1] == len(raw):
            starts.append((pos - 1, marker))
    return sorted(starts)


def device_definitions_for(donor_key: str) -> dict[str, bytes]:
    donor = v1.donor_by_key(donor_key)
    section = seq._device_section(seq.read_internal_file(donor.path, "ROOT.DSN"))
    starts = device_definition_starts(section)
    definitions: dict[str, bytes] = {}
    for index, (start, marker) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(section) - 4
        if end <= start:
            raise ValueError(f"Invalid device definition bounds for {donor_key}:{marker}")
        definitions[marker] = section[start:end]
    return definitions


def build_filtered_device_section(case) -> tuple[bytes, list[dict[str, object]]]:
    definitions_by_donor: dict[str, dict[str, bytes]] = {}
    emitted: set[str] = set()
    parts: list[bytes] = []
    plan: list[dict[str, object]] = []
    for selection in case.selections:
        if selection.donor_key not in definitions_by_donor:
            definitions_by_donor[selection.donor_key] = device_definitions_for(selection.donor_key)
        definitions = definitions_by_donor[selection.donor_key]
        for marker in selection.markers:
            device = marker_to_device(marker)
            if device in emitted:
                continue
            if device not in definitions:
                raise ValueError(f"{selection.donor_key} device section does not contain definition {device}")
            block = definitions[device]
            parts.append(block)
            emitted.add(device)
            plan.append(
                {
                    "donor_key": selection.donor_key,
                    "device": device,
                    "definition_size": len(block),
                }
            )
    return b"".join(parts) + b"\x00\x00\x00\x00", plan


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
    cdb, row_plan = v2.build_cross_cdb_sorted(case.selections)
    device_section, device_plan = build_filtered_device_section(case)

    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    first_donor = v1.donor_by_key(case.selections[0].donor_key)
    donor_dsn = seq.read_internal_file(first_donor.path, "ROOT.DSN")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        object_chunk,
        device_section,
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
    issues = v1.static_issues(output, case, row_plan)
    filtered_section = seq._device_section(dsn)
    for marker in ("CAP-ELEC", "LM741", "NPN", "PNP", "REALIND", "RESISTOR", "CAPACITOR"):
        if marker.encode("ascii") in filtered_section:
            issues.append(f"filtered device section unexpectedly contains analog/passive definition {marker}")
    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "method": "v3_cross_donor_filtered_device_definitions_single_footer",
        "changed_from_v2": [
            "Extract only selected per-device definitions from donor device sections.",
            "Drop donor device-section footers and emit one generated footer pointer.",
            "Continue using sorted union CDB rows and the same visible regions as V1/V2.",
        ],
        "status": "temporary_pending_user_proteus_testing",
        "terminal_policy": "all retained visible endpoints use donor-native $TERBIDIR records with generated unique labels",
        "composition_policy": "same visible IC regions as V1/V2; filtered per-device metadata; no analog/passive regions",
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
        "device_definition_plan": device_plan,
        "section_pointers": pointers,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": mixed.marker_counts(chunk) | {"7447": chunk.count(b"7447")},
        "cdb_marker_counts": mixed.marker_counts(cdb) | {"7447": cdb.count(b"7447")},
        "device_section_size": len(filtered_section),
        "object_chunk_size": len(chunk),
        "static_validation_issues": issues,
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
            "device_section": seq._sha256_bytes(filtered_section),
        },
    }
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

    discovery = {
        donor.key: [
            {"device": marker, "size": len(block)}
            for marker, block in device_definitions_for(donor.key).items()
        ]
        for donor in mixed.DONORS
        if donor.key in {"seq_counters_all", "misc_logic_analog"}
    }
    (OUT_ROOT / "device_definition_discovery.json").write_text(json.dumps(discovery, indent=2) + "\n", encoding="utf-8")

    manifests = [write_case(case) for case in v1.CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_CROSS_DONOR_V3_FILTERED_DEVICE_TEMP_2026_06_09",
        "purpose": "Retry V2 cross-donor IC mixes by filtering per-device definitions and emitting one device-section footer.",
        "status": "temporary_pending_user_proteus_testing",
        "composition_policy": "same whole IC regions as V1/V2; filtered device definitions; sorted CDB U rows",
        "terminal_policy": "all retained visible endpoints use relabeled $TERBIDIR records",
        "case_count": len(manifests),
        "cases": manifests,
        "static_issue_cases": summary_issues,
        "device_definition_discovery": "device_definition_discovery.json",
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
