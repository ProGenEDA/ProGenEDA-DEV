"""Generate V11 diagnostics for mixed DC sources plus R/C/L group boundaries.

V10 still failed from T05 onward. A deeper byte check found that V10 spliced the
donor "final unit" too late: it started at OUT A9, but the actual final RL group
starts at the two input terminals IN A9 and IN F2. That left generated terminal
suffixes feeding donor component records.

This pack tests whole group boundaries and donor suffix remapping. It avoids
shrinking DVO to D0 on generated splice cases because V10 showed that can turn a
VGDVC failure into a malformed "device not in library" crash.
"""

from __future__ import annotations

import hashlib
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

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V9_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v9_donor_tail_temp.py"
OUT_ROOT = REPO_ROOT / "experiments" / "dc_mixed_sources_v11_group_boundary_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "DC_MIXED_SOURCES_V11_GROUP_BOUNDARY_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"

GROUP_STARTS = {
    "after_leading_v0_output": 105,
    "group_4_start": 4789,
    "group_7_start": 9455,
    "group_9_start": 12813,
    "source_tail_start": 14148,
}


def _load_v9() -> Any:
    spec = importlib.util.spec_from_file_location("dc_mixed_sources_v9_for_v11", V9_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V9 helper module from {V9_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v9 = _load_v9()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _copy_donor_for_v11() -> Path:
    v9.OUT_ROOT = OUT_ROOT
    v9.ARCHIVE_BASE = ARCHIVE_BASE
    v9.DONOR_ROOT = DONOR_ROOT
    return v9._copy_donor()


def _splice_generated_prefix(generated_body: bytes, donor_chunk: bytes, splice_start: int) -> bytes:
    if generated_body[-1] != 0xFF or donor_chunk[-1] != 0xFF:
        raise RuntimeError("Expected independently final generated body and donor chunk.")
    out = bytearray(generated_body[:splice_start] + donor_chunk[splice_start:])
    out[-1] = 0xFF
    return bytes(out)


def _terminal_suffixes(chunk: bytes, *, before: int) -> list[tuple[int, str, str, int]]:
    out: list[tuple[int, str, str, int]] = []
    for start, kind, label in v9._terminal_events(chunk):
        if start >= before:
            continue
        if kind == "OUT":
            suffix = int.from_bytes(chunk[start + 100 : start + 102], "little")
        else:
            suffix = int.from_bytes(chunk[start + 99 : start + 101], "little")
        out.append((start, kind, label, suffix))
    return out


def _suffix_map_by_terminal_order(donor_chunk: bytes, generated_chunk: bytes, *, before: int) -> dict[int, int]:
    donor_terms = _terminal_suffixes(donor_chunk, before=before)
    generated_terms = _terminal_suffixes(generated_chunk, before=before)
    if len(donor_terms) != len(generated_terms):
        raise RuntimeError(f"Terminal count mismatch before {before}: donor={len(donor_terms)} generated={len(generated_terms)}")
    mapping: dict[int, int] = {}
    for donor, generated in zip(donor_terms, generated_terms, strict=True):
        _d_start, d_kind, d_label, d_suffix = donor
        _g_start, g_kind, g_label, g_suffix = generated
        if (d_kind, d_label) != (g_kind, g_label):
            raise RuntimeError(
                f"Terminal mismatch before {before}: donor {(d_kind, d_label)} generated {(g_kind, g_label)}"
            )
        mapping[g_suffix] = d_suffix
    return mapping


def _apply_suffix_map_prefix(chunk: bytes, mapping: dict[int, int], *, before: int) -> tuple[bytes, dict[str, Any]]:
    # Replace only two-byte suffix fields immediately followed by 01 00. This
    # avoids accidental coordinate edits and avoids replacement cascades.
    prefixes = {old.to_bytes(2, "little") + b"\x01\x00": new.to_bytes(2, "little") + b"\x01\x00" for old, new in mapping.items() if old != new}
    out = bytearray()
    replacements = 0
    i = 0
    prefix = chunk[:before]
    while i < len(prefix):
        replaced = False
        for old, new in prefixes.items():
            if prefix[i : i + 4] == old:
                out += new
                i += 4
                replacements += 1
                replaced = True
                break
        if not replaced:
            out.append(prefix[i])
            i += 1
    out += chunk[before:]
    return bytes(out), {"mapped_suffix_count": len(prefixes), "replacement_count": replacements, "before": before}


def _validate_boundary_constants(donor_chunk: bytes) -> None:
    checks = {
        "after_leading_v0_output": (b"$TEROUTPUT", b"B1"),
        "group_4_start": (b"$TEROUTPUT", b"B4"),
        "group_7_start": (b"$TEROUTPUT", b"B7"),
        "group_9_start": (b"$TERINPUT", b"A9"),
        "source_tail_start": (b"$TERINPUT", b"DVO"),
    }
    for name, (marker, label) in checks.items():
        start = GROUP_STARTS[name]
        window = donor_chunk[start : start + 60]
        if marker not in window or label not in window:
            raise RuntimeError(f"Boundary {name} at {start} does not match expected marker/label.")


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    donor = _copy_donor_for_v11()
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v9.rcl._load_rcl_unit_templates(rcl_donor)

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_chunk = rv9._extract_object_chunk(donor_dsn)
    _validate_boundary_constants(donor_chunk)
    donor_cdb = read_internal_file(donor, "ROOT.CDB")
    donor_devices = v9.v5._device_section_from_dsn(donor_dsn)
    generated_body, generated_specs, generated_topology, generated_counts = v9._build_rcl_body_keep_v0_output(
        templates,
        negative_label="D0",
    )
    generated_cdb = v9._build_cdb(generated_specs)

    splice_group9 = _splice_generated_prefix(generated_body, donor_chunk, GROUP_STARTS["group_9_start"])
    splice_group7 = _splice_generated_prefix(generated_body, donor_chunk, GROUP_STARTS["group_7_start"])
    splice_group4 = _splice_generated_prefix(generated_body, donor_chunk, GROUP_STARTS["group_4_start"])
    splice_after_v0 = _splice_generated_prefix(generated_body, donor_chunk, GROUP_STARTS["after_leading_v0_output"])

    map_group9 = _suffix_map_by_terminal_order(donor_chunk, splice_group9, before=GROUP_STARTS["group_9_start"])
    splice_group9_mapped, group9_map_stats = _apply_suffix_map_prefix(
        splice_group9,
        map_group9,
        before=GROUP_STARTS["group_9_start"],
    )
    map_group7 = _suffix_map_by_terminal_order(donor_chunk, splice_group7, before=GROUP_STARTS["group_7_start"])
    splice_group7_mapped, group7_map_stats = _apply_suffix_map_prefix(
        splice_group7,
        map_group7,
        before=GROUP_STARTS["group_7_start"],
    )

    cases: list[dict[str, Any]] = [
        v9._copy_control("DCMS_V11_T00_DONOR_COPY", "Exact copy of the user donor control.", donor),
        v9._write_case(
            "DCMS_V11_T01_DONOR_OBJECT_GENERATED_CDB",
            "Exact donor object structure and donor device section, but generated CDB rows.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=donor_chunk,
            cdb=generated_cdb,
            devices=donor_devices,
            input_payload={"control": "donor_object_with_generated_cdb"},
        ),
        v9._write_case(
            "DCMS_V11_T02_GENERATED_PREFIX_DONOR_GROUP9",
            "Generated groups 1-8, then full donor group 9 and source tail.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=splice_group9,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "generated_prefix_donor_group9", "splice_start": GROUP_STARTS["group_9_start"]},
        ),
        v9._write_case(
            "DCMS_V11_T03_GENERATED_PREFIX_DONOR_GROUP9_SUFFIXMAP",
            "Same as T02, but generated prefix suffix fields remapped to donor suffixes.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=splice_group9_mapped,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "generated_prefix_donor_group9_suffixmap", "suffix_map_stats": group9_map_stats},
        ),
        v9._write_case(
            "DCMS_V11_T04_GENERATED_PREFIX_DONOR_GROUP7_TO_TAIL",
            "Generated groups 1-6, then donor groups 7-9 and source tail.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=splice_group7,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "generated_prefix_donor_groups7_to_tail", "splice_start": GROUP_STARTS["group_7_start"]},
        ),
        v9._write_case(
            "DCMS_V11_T05_GENERATED_PREFIX_DONOR_GROUP7_SUFFIXMAP",
            "Same as T04, but generated prefix suffix fields remapped to donor suffixes.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=splice_group7_mapped,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "generated_prefix_donor_groups7_to_tail_suffixmap", "suffix_map_stats": group7_map_stats},
        ),
        v9._write_case(
            "DCMS_V11_T06_GENERATED_PREFIX_DONOR_GROUP4_TO_TAIL",
            "Generated groups 1-3, then donor groups 4-9 and source tail.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=splice_group4,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "generated_prefix_donor_groups4_to_tail", "splice_start": GROUP_STARTS["group_4_start"]},
        ),
        v9._write_case(
            "DCMS_V11_T07_GENERATED_LEADING_V0_DONOR_REST",
            "Generated leading V0 output only, then donor groups 1-9 and source tail.",
            base_project=base_project,
            donor_project=donor,
            object_chunk=splice_after_v0,
            cdb=donor_cdb,
            devices=donor_devices,
            input_payload={"kind": "generated_leading_v0_then_donor_rest", "splice_start": GROUP_STARTS["after_leading_v0_output"]},
        ),
    ]

    summary = {
        "batch_id": "DC_MIXED_SOURCES_V11_GROUP_BOUNDARY_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "User reported V10 T05/T06 VGDVC.dll and T07/T08 missing-library dialog/crash.",
        "method": "Test whole donor group boundaries and donor suffix remapping; avoid DVO-to-D0 shrink patching on generated splice cases.",
        "group_starts": GROUP_STARTS,
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item.get("marker_counts"),
                "object_chunk_len": item.get("object_chunk_len"),
                "root_cdb_len": item.get("root_cdb_len"),
                "static_validation_issues": item.get("static_validation_issues"),
            }
            for item in cases
        ],
        "generated_counts": generated_counts,
        "generated_topology": generated_topology,
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "DC_MIXED_SOURCES_V11_GROUP_BOUNDARY_TEMP_2026_06_05\n\n"
        "Open in order:\n"
        + "\n".join(
            f"{index}. {case_id}.pdsprj" if index == 1 else f"{index}. {case_id}/{case_id}.pdsprj"
            for index, case_id in enumerate(summary["test_order"], start=1)
        )
        + "\n\nT00/T01 are controls. T02/T03 test a full donor group-9 splice. "
        "T04/T05 test donor groups 7-9. T06 tests donor groups 4-9. T07 tests whether even the leading generated V0 output is unsafe.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
