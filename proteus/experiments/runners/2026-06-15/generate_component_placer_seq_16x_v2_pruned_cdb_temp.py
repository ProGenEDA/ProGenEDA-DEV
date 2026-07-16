"""Generate component-placer probes from the 16x donor with pruned ROOT.CDB.

This supersedes the rejected V1 pack. V1 selected and moved IC body packets but
copied the entire donor ROOT.CDB, leaving stale rows for deleted components.
This version keeps the same no-terminal/no-wire body-only output surface, then
rebuilds ROOT.CDB from only the selected packages' pin/property rows.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from collections import Counter
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.component_placer import (  # noqa: E402
    build_component_placer_cdb_subset,
    parse_component_placer_cdb,
    validate_project_placement,
)
from proteusgen.ic_native import build_dsn_with_device_section, device_section, marker_counts  # noqa: E402
from proteusgen.pdsprj import read_internal_file, write_project_from_parts  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version  # noqa: E402

V1_SCRIPT = Path(__file__).with_name("generate_component_placer_seq_16x_v1_temp.py")
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "component_placer_seq_16x_v2_pruned_cdb_temp_2026_06_15"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "COMPONENT_PLACER_SEQ_16X_V2_PRUNED_CDB_TEMP_2026_06_15.zip"


def _load_v1():
    spec = importlib.util.spec_from_file_location("component_placer_seq_16x_v1_temp", V1_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {V1_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_v1()


def build_project(case, donor_dsn: bytes, donor_cdb, output: Path) -> dict[str, object]:
    placed: list[bytes] = []
    placements: list[dict[str, object]] = []
    for index, packet in enumerate(case.selected):
        packet_bytes, placement = v1._place_packet(packet, index)
        placed.append(packet_bytes)
        placements.append(placement)

    object_chunk = b"\x00\x00" + b"".join(placed) + b"\xff"
    for marker in v1.FORBIDDEN_MARKERS:
        if marker in object_chunk:
            raise RuntimeError(f"{case.case_id} object chunk contains forbidden marker {marker!r}")

    keep_packages = tuple(packet.package for packet in case.selected)
    cdb = build_component_placer_cdb_subset(donor_cdb, keep_packages)
    parsed_subset = parse_component_placer_cdb(cdb)

    fixture = FixtureRegistry.load().get("e001_empty")
    base_dsn = read_internal_file(fixture.path, "ROOT.DSN")
    dsn, pointers = build_dsn_with_device_section(base_dsn, donor_dsn, object_chunk, device_section(donor_dsn))
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    write_project_from_parts(
        fixture.path,
        output,
        {
            "PROJECT.XML": patch_project_xml_version(read_internal_file(fixture.path, "PROJECT.XML"), PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": cdb,
        },
    )

    final_dsn = read_internal_file(output, "ROOT.DSN")
    final_chunk = _extract_object_chunk(final_dsn)
    validation = validate_project_placement(output)
    issues = [issue.as_dict() for issue in validation.errors]
    warnings = [issue.as_dict() for issue in validation.warnings]
    if final_chunk != object_chunk:
        issues.append({"code": "E_OBJECT_CHUNK_MISMATCH", "message": "final ROOT.DSN object chunk does not match planned object chunk", "severity": "error"})
    for marker in v1.FORBIDDEN_MARKERS:
        if marker in final_chunk:
            issues.append({"code": "E_FORBIDDEN_MARKER", "message": f"forbidden marker remains in final chunk: {marker.decode('ascii', errors='replace')}", "severity": "error"})

    requested_counts = Counter(packet.family for packet in case.selected)
    actual_counts = {
        family: sum(1 for placement in placements if placement["family"] == family)
        for family in sorted(requested_counts)
    }
    for family, expected in requested_counts.items():
        if actual_counts.get(family) != expected:
            issues.append({"code": "E_MARKER_COUNT", "message": f"{family} package count {actual_counts.get(family)} != {expected}", "severity": "error"})
        if family.encode("ascii") not in final_chunk:
            issues.append({"code": "E_MARKER_MISSING", "message": f"marker {family} missing from final chunk", "severity": "error"})

    subset_pin_packages = sorted({row.ref.split(":", 1)[0] for row in parsed_subset.pin_rows})
    subset_property_packages = sorted({row.ref.split(":", 1)[0] for row in parsed_subset.property_rows})
    return {
        "case_id": case.case_id,
        "description": case.description,
        "families": case.families,
        "selected_packages": [
            {"family": packet.family, "package": packet.package, "refs": [record.ref for record in packet.records]}
            for packet in case.selected
        ],
        "package_counts": dict(requested_counts),
        "terminal_policy": "component placer body-only output; no external terminals or wires emitted",
        "metadata_policy": "pruned 16x donor ROOT.CDB: keep only selected package pin/property rows; full donor device section preserved",
        "section_pointers": pointers,
        "placements": placements,
        "object_chunk_size": len(final_chunk),
        "marker_counts": marker_counts(final_chunk, v1.FAMILY_MARKERS),
        "terminal_counts": {
            "$TERBIDIR": final_chunk.count(b"$TERBIDIR"),
            "$TERINPUT": final_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": final_chunk.count(b"$TEROUTPUT"),
            "WIRE": final_chunk.count(b"WIRE"),
        },
        "cdb_subset": {
            "pin_row_count": len(parsed_subset.pin_rows),
            "property_row_count": len(parsed_subset.property_rows),
            "pin_packages": subset_pin_packages,
            "property_packages": subset_property_packages,
            "property_header_size": parsed_subset.property_header_size,
        },
        "static_validation_issues": issues,
        "static_validation_warnings": warnings,
        "output_hashes": {
            "project": _sha256_bytes(output.read_bytes()),
            "ROOT.DSN": _sha256_bytes(final_dsn),
            "ROOT.CDB": _sha256_bytes(read_internal_file(output, "ROOT.CDB")),
            "object_chunk": _sha256_bytes(final_chunk),
        },
    }


def write_case(case, donor_dsn: bytes, donor_cdb) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    manifest = build_project(case, donor_dsn, donor_cdb, output)
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "object_chunk.bin").write_bytes(_extract_object_chunk(read_internal_file(output, "ROOT.DSN")))
    (case_dir / "ROOT.CDB.bin").write_bytes(read_internal_file(output, "ROOT.CDB"))
    return manifest


def write_archive() -> str:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
            info.date_time = (2026, 6, 15, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, file_path.read_bytes())
    return _sha256_bytes(ARCHIVE.read_bytes())


def main() -> int:
    if not v1.DONOR.exists():
        raise FileNotFoundError(v1.DONOR)
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    donor_dsn = read_internal_file(v1.DONOR, "ROOT.DSN")
    donor_cdb = parse_component_placer_cdb(read_internal_file(v1.DONOR, "ROOT.CDB"))
    donor_chunk = _extract_object_chunk(donor_dsn)
    packets = v1.analyze_packages(donor_chunk)

    inventory = {
        family: {
            "package_count": len(items),
            "subpart_count_distribution": dict(Counter(len(packet.records) for packet in items)),
            "first_packages": [
                {"package": packet.package, "refs": [record.ref for record in packet.records]}
                for packet in items[:5]
            ],
        }
        for family, items in sorted(packets.items())
    }
    (OUT_ROOT / "donor_inventory.json").write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    cases = v1._same_family_cases(packets) + v1._pair_cases(packets)
    manifests = [write_case(case, donor_dsn, donor_cdb) for case in cases]
    static_issue_cases = {
        manifest["case_id"]: manifest["static_validation_issues"]
        for manifest in manifests
        if manifest["static_validation_issues"]
    }
    summary = {
        "batch": "COMPONENT_PLACER_SEQ_16X_V2_PRUNED_CDB_TEMP_2026_06_15",
        "status": "temporary_pending_user_proteus_testing",
        "purpose": "Removal-only component placer probes from the 16x sequential/native mega donor with CDB rows pruned to kept packages.",
        "donor": str(v1.DONOR.relative_to(REPO)),
        "donor_hashes": {
            "project": _sha256_bytes(v1.DONOR.read_bytes()),
            "ROOT.DSN": _sha256_bytes(donor_dsn),
            "ROOT.CDB": _sha256_bytes(read_internal_file(v1.DONOR, "ROOT.CDB")),
            "object_chunk": _sha256_bytes(donor_chunk),
        },
        "donor_cdb": donor_cdb.as_dict(),
        "target_families": v1.SEQUENTIAL_FAMILIES,
        "same_family_counts": v1.SAME_FAMILY_COUNTS,
        "pair_policy": "all unordered family pairs emitted in both 2x-left+1x-right and 1x-left+2x-right forms",
        "case_count": len(manifests),
        "same_family_case_count": len([m for m in manifests if len(m["families"]) == 1]),
        "pair_case_count": len([m for m in manifests if len(m["families"]) == 2]),
        "inventory": inventory,
        "static_issue_cases": static_issue_cases,
        "archive": str(ARCHIVE.relative_to(REPO)),
    }
    (OUT_ROOT / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    archive_hash = write_archive()
    summary["archive_sha256"] = archive_hash
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_ROOT),
                "archive": str(ARCHIVE),
                "archive_sha256": archive_hash,
                "case_count": len(manifests),
                "static_issue_cases": static_issue_cases,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
