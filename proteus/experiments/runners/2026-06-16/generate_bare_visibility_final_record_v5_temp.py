"""Generate V5 diagnostics for no-terminal final-object record handling.

The V3/V4 evidence suggests the failure is not that resistors are required.
Instead, the generator was making middle-of-stream records final by simply
placing FF after them. This pack compares failed baselines against variants
where the final selected object is a same-family record that was final in a
Proteus-created no-terminal donor.
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
V3_SCRIPT = ROOT / "tools/proteus_generation/2026-06-16/generate_bare_visibility_rlc_anchor_v3_temp.py"
OUT_DIR = ROOT / "experiments/bare_visibility_final_record_v5_temp_2026_06_16"
ZIP_OUT = ROOT / "experiments/BARE_VISIBILITY_FINAL_RECORD_V5_TEMP_2026_06_16.zip"

FINAL_DONORS = {
    "REALIND": ROOT / "proteus_ic/donors/manual_downloads_20260611/inductor_01_single_free.pdsprj",
    "CAP": ROOT / "proteus_ic/donors/manual_downloads_20260611/cap3.pdsprj",
    "LM741": ROOT / "proteus_ic/donors/manual_downloads_20260611/squence/PAIR_LM741_74HC85.pdsprj",
    "74HC160": ROOT / "proteus_ic/donors/manual_downloads_20260611/squence/MIX_SYNC_COUNTERS_160_161_163_192_193.pdsprj",
}


def load_v3_module():
    spec = importlib.util.spec_from_file_location("bare_visibility_rlc_anchor_v3_temp", V3_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import {V3_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.OUT_DIR = OUT_DIR
    module.ZIP_OUT = ZIP_OUT
    return module


def patch_ascii_same_len(data: bytes, old: str, new: str) -> bytes:
    old_b = old.encode("ascii")
    new_b = new.encode("ascii")
    if len(old_b) != len(new_b):
        raise ValueError(f"Cannot same-length patch {old!r} to {new!r}.")
    return data.replace(old_b, new_b)


def final_group(v3, family: str):
    donor = FINAL_DONORS[family]
    chunk = v3._extract_object_chunk(v3.read_internal_file(donor, "ROOT.DSN"))
    groups = v3.groups_from_no_terminal_chunk(chunk)
    candidates = groups.get(family, [])
    if not candidates:
        raise ValueError(f"No {family} final group found in {donor}.")
    # The source donors were selected because their last object is the desired
    # final family. Use the last matching group, preserving its final-byte form.
    return candidates[-1], donor


def object_chunk_from_groups(v3, groups) -> bytes:
    return b"\x00\x00" + b"".join(group.data for group in sorted(groups, key=lambda item: item.start)) + b"\xff"


def object_chunk_with_custom_final(v3, selected_groups, final_data: bytes) -> bytes:
    ordered = sorted(selected_groups, key=lambda item: item.start)
    return b"\x00\x00" + b"".join(group.data for group in ordered) + final_data + b"\xff"


def write_custom_case(v3, case_id: str, donor_dsn: bytes, donor_cdb: bytes, object_chunk: bytes, description: str):
    case_dir = OUT_DIR / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case_id}.pdsprj"
    dsn, pointers = v3.build_dsn(donor_dsn, donor_dsn, object_chunk)
    v3.write_project_from_parts(v3.DONOR, output, {"ROOT.DSN": dsn, "ROOT.CDB": donor_cdb}, compression=v3.ZIP_DEFLATED)
    final_chunk = v3._extract_object_chunk(v3.read_internal_file(output, "ROOT.DSN"))
    errors = []
    if final_chunk != object_chunk:
        errors.append("final object chunk differs")
    if any(marker in final_chunk for marker in v3.TERM_MARKERS):
        errors.append("terminal marker present")
    if v3.WIRE_MARKER in final_chunk:
        errors.append("WIRE marker present")
    return {
        "case_id": case_id,
        "output": str(output.relative_to(ROOT)),
        "description": f"{description} pointers={pointers}",
        "object_chunk_size": len(final_chunk),
        "object_chunk_head": final_chunk[:16].hex(),
        "object_chunk_tail": final_chunk[-16:].hex(),
        "object_chunk_sha256": v3.sha256_bytes(final_chunk),
        "marker_counts": v3.marker_counts(final_chunk),
        "errors": errors,
    }


def main() -> None:
    v3 = load_v3_module()
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    donor_dsn = v3.read_internal_file(v3.DONOR, "ROOT.DSN")
    donor_cdb = v3.read_internal_file(v3.DONOR, "ROOT.CDB")
    groups = v3.groups_from_no_terminal_chunk(v3._extract_object_chunk(donor_dsn))

    def select(counts):
        return v3.select_groups(groups, counts)

    full_digital = {"74HC160": 4, "7490": 2, "74HC08": 2, "74HC32": 2, "LM741": 2}
    f09_counts = {**full_digital, "CAP": 4, "REALIND": 4}
    f13_counts = {**full_digital, "CAP": 4}
    f14_counts = {**full_digital, "REALIND": 4}

    cases = []
    # Baselines from failed V3 cases.
    for case_id, counts, description in [
        ("H00_F09_MINUS_RESISTORS_BASELINE", f09_counts, "Known failed V3 F09 shape: no resistors, middle REALIND made final."),
        ("H01_F13_CAPS_ONLY_BASELINE", f13_counts, "Known failed V3 F13 shape: no resistors/inductors, middle LM741 made final."),
        ("H02_F14_INDUCTORS_ONLY_BASELINE", f14_counts, "Known failed V3 F14 shape: no resistors/caps, middle REALIND made final."),
        ("H03_160_1X_BASELINE", {"74HC160": 1}, "Known failed small 74HC160-only shape, middle 74HC160 made final."),
        ("H04_160_4X_BASELINE", {"74HC160": 4}, "Known failed 74HC160-only shape, middle 74HC160 made final."),
    ]:
        cases.append(write_custom_case(v3, case_id, donor_dsn, donor_cdb, object_chunk_from_groups(v3, select(counts)), description))

    final_l, final_l_donor = final_group(v3, "REALIND")
    final_c, final_c_donor = final_group(v3, "CAP")
    final_lm, final_lm_donor = final_group(v3, "LM741")
    final_160, final_160_donor = final_group(v3, "74HC160")

    # Same-family final-form substitutions/appends. For L/C we can patch to an
    # unused ref present in the full mixed donor CDB with same-length names.
    final_l4 = patch_ascii_same_len(final_l.data, final_l.refs[0], "L4")
    final_c7 = patch_ascii_same_len(final_c.data, final_c.refs[0], "C7")

    # Remove the original non-final last same-family group before appending a
    # final-form equivalent, so the requested family count remains comparable.
    f09_without_l4 = tuple(group for group in select(f09_counts) if group.key != "L4")
    f14_without_l4 = tuple(group for group in select(f14_counts) if group.key != "L4")
    f13_without_last_cap = tuple(group for group in select(f13_counts) if group.key != "C4")

    cases.append(
        write_custom_case(
            v3,
            "H05_F09_FINAL_FORM_L4",
            donor_dsn,
            donor_cdb,
            object_chunk_with_custom_final(v3, f09_without_l4, final_l4),
            f"F09 retry: replace middle L4 finalization with final-form REALIND from {final_l_donor.relative_to(ROOT)} patched to L4.",
        )
    )
    cases.append(
        write_custom_case(
            v3,
            "H06_F14_FINAL_FORM_L4",
            donor_dsn,
            donor_cdb,
            object_chunk_with_custom_final(v3, f14_without_l4, final_l4),
            f"F14 retry: replace middle L4 finalization with final-form REALIND from {final_l_donor.relative_to(ROOT)} patched to L4.",
        )
    )
    cases.append(
        write_custom_case(
            v3,
            "H07_F13_FINAL_FORM_C7",
            donor_dsn,
            donor_cdb,
            object_chunk_with_custom_final(v3, f13_without_last_cap, final_c7),
            f"F13 retry: append final-form CAP from {final_c_donor.relative_to(ROOT)} patched to C7 as final object.",
        )
    )
    cases.append(
        write_custom_case(
            v3,
            "H08_F13_FINAL_FORM_LM741_U1",
            donor_dsn,
            donor_cdb,
            object_chunk_with_custom_final(v3, select(f13_counts), final_lm.data),
            f"F13 retry: append final-form LM741 from {final_lm_donor.relative_to(ROOT)} as U1 final object.",
        )
    )
    cases.append(
        write_custom_case(
            v3,
            "H09_160_FINAL_FORM_U5_ONLY",
            donor_dsn,
            donor_cdb,
            b"\x00\x00" + final_160.data + b"\xff",
            f"Single final-form 74HC160 from {final_160_donor.relative_to(ROOT)} as U5.",
        )
    )
    cases.append(
        write_custom_case(
            v3,
            "H10_160_4X_APPEND_FINAL_FORM_U5",
            donor_dsn,
            donor_cdb,
            object_chunk_with_custom_final(v3, select({"74HC160": 4}), final_160.data),
            f"Four mixed-donor 74HC160 plus final-form 74HC160 from {final_160_donor.relative_to(ROOT)}.",
        )
    )

    summary = {
        "experiment": "bare_visibility_final_record_v5_temp_2026_06_16",
        "purpose": "Test whether failed no-terminal subsets are caused by making non-final records final.",
        "mixed_donor": str(v3.DONOR.relative_to(ROOT)),
        "final_record_donors": {family: str(path.relative_to(ROOT)) for family, path in FINAL_DONORS.items()},
        "cases": cases,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    v3.zip_dir(OUT_DIR, ZIP_OUT)
    print(json.dumps({"out_dir": str(OUT_DIR), "zip": str(ZIP_OUT), "cases": len(cases), "zip_sha256": v3.sha256_file(ZIP_OUT)}, indent=2))


if __name__ == "__main__":
    main()
