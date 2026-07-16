"""Generate focused mixed IC/analog V4 diagnostics.

This pack backs away from V3's heuristic coordinate scan. It uses only accepted
whole-region assembly plus explicit, auditable edits:

- T01/T02 repeat the accepted no-layout cross-donor controls.
- T03/T04 keep RLC/NPN/PNP/LM741/CAP-ELEC in the active samples.
- T05-T07 patch the observed 74HC4060 missing-model metadata in DSN and CDB.
- T08-T09 keep NE555 and analog-only edits in the sample set without broad
  cross-family synthesis.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from proteusgen.cdb import CdbPropertyRow, build_cdb_from_rows, parse_cdb


REPO = Path(__file__).resolve().parents[4]
ACCEPTED_V1_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-10" / "generate_mixed_ic_cross_donor_accepted_v1_temp.py"
SUBSET_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-09" / "generate_mixed_ic_analog_subset_v1_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_focused_v4_temp_2026_06_10"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_FOCUSED_V4_TEMP_2026_06_10.zip"

OLD_4060_PROPS = b"{ITFMOD=CMOS}\n{PACKAGE=DIL16}\n"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


accepted_v1 = _load_module("mixed_ic_cross_donor_accepted_v1_for_focused_v4", ACCEPTED_V1_SCRIPT)
subset_v1 = _load_module("mixed_ic_analog_subset_v1_for_focused_v4", SUBSET_SCRIPT)
seq = accepted_v1.base_iso.seq


@dataclass(frozen=True)
class CrossBaselineCase:
    case_id: str
    description: str
    selections: tuple[object, ...]
    header_donor_key: str
    expected_markers: tuple[str, ...]


@dataclass(frozen=True)
class AnalogSubsetCase:
    case_id: str
    description: str
    donor_key: str
    keep_markers: tuple[str, ...]
    mutate_labels: bool = True
    patch_4060_model: str | None = None


@dataclass(frozen=True)
class WholeDonorCase:
    case_id: str
    description: str
    donor_path: Path
    required_markers: tuple[str, ...]
    mutate_labels: bool = False
    patch_4060_model: str | None = None


def _read_lp_ascii(data: bytes, offset: int) -> tuple[str, int]:
    length = data[offset]
    start = offset + 1
    end = start + length
    return data[start:end].decode("ascii", errors="replace"), end


def _property_text_bounds(row: CdbPropertyRow) -> tuple[int, int]:
    pos = 20
    _ref, pos = _read_lp_ascii(row.data, pos)
    for _field in range(3):
        _value, pos = _read_lp_ascii(row.data, pos)
    return pos, pos + 4


def _rewrite_property_text(row: CdbPropertyRow, text: bytes, *, is_last: bool) -> CdbPropertyRow:
    length_offset, text_offset = _property_text_bounds(row)
    encoded_len = len(text) + (0 if is_last else 4)
    data = bytearray(row.data[:length_offset])
    data.extend(encoded_len.to_bytes(4, "little"))
    data.extend(text)
    return CdbPropertyRow(ref=row.ref, data=bytes(data))


def _patch_4060_cdb(cdb: bytes, *, modfile: str) -> tuple[bytes, list[dict[str, object]]]:
    parsed = parse_cdb(cdb)
    pins_by_ref = parsed.pin_by_ref()
    props_by_ref = parsed.property_by_ref()
    text = (
        f"{{PACKAGE=DIL16}}\n{{MODFILE={modfile}}}\n{{VOLTAGE=4.5V}}\n{{ITFMOD=CMOS}}\n"
    ).encode("ascii")
    rows = []
    plan: list[dict[str, object]] = []
    for index, pin in enumerate(parsed.pin_rows):
        prop_ref = pin.ref.split(":", 1)[0]
        prop = props_by_ref[prop_ref]
        if b"74HC4060" in prop.data and OLD_4060_PROPS in prop.data:
            old_size = len(prop.data)
            prop = _rewrite_property_text(prop, text, is_last=index == len(parsed.pin_rows) - 1)
            plan.append(
                {
                    "ref": prop_ref,
                    "modfile": modfile,
                    "old_property_size": old_size,
                    "new_property_size": len(prop.data),
                }
            )
        rows.append((pin.ref, pins_by_ref[pin.ref], prop))
    return build_cdb_from_rows(parsed, rows), plan


def _patch_4060_dsn_chunk(chunk: bytes, *, modfile: str) -> tuple[bytes, dict[str, object]]:
    text = (
        f"{{PACKAGE=DIL16}}\n{{MODFILE={modfile}}}\n{{VOLTAGE=4.5V}}\n{{ITFMOD=CMOS}}\n"
    ).encode("ascii")
    old = b"\xff" + bytes([len(OLD_4060_PROPS)]) + OLD_4060_PROPS
    new = b"\xff" + bytes([len(text)]) + text
    count = chunk.count(old)
    return chunk.replace(old, new), {
        "modfile": modfile,
        "old_property_text_len": len(OLD_4060_PROPS),
        "new_property_text_len": len(text),
        "patched_dsn_property_records": count,
    }


def cdb_for_cross_case(case: CrossBaselineCase) -> tuple[bytes, list[dict[str, object]], str]:
    replacement_sources = accepted_v1.replacements_for(case.header_donor_key, case.selections)
    if not replacement_sources:
        return accepted_v1.base_iso.donor_cdb(case.header_donor_key), [], "full_header_donor"
    cdb, row_plan = accepted_v1.cdb_v2.build_full_skeleton_cdb(
        case.header_donor_key,
        replacement_sources,
        replace_pins=True,
        replace_properties=True,
    )
    return cdb, row_plan, "accepted_full_skeleton_replaced_rows"


def write_cross_baseline_case(case: CrossBaselineCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    object_chunk, region_plan = accepted_v1.base_iso.object_chunk_for(case.selections)
    cdb, cdb_row_plan, cdb_mode = cdb_for_cross_case(case)
    pointers, device_plan = accepted_v1.base_iso.write_dsn(
        output,
        object_chunk=object_chunk,
        cdb=cdb,
        header_donor_key=case.header_donor_key,
        device_mode="full_multi",
        selections=case.selections,
    )
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    parsed = parse_cdb(cdb)
    return _write_manifest(
        case_dir,
        output,
        {
            "case_id": case.case_id,
            "description": case.description,
            "method": "accepted_cross_donor_no_layout_baseline",
            "status": "temporary_pending_user_proteus_testing",
            "header_donor_key": case.header_donor_key,
            "cdb_mode": cdb_mode,
            "expected_markers": case.expected_markers,
            "region_plan": region_plan,
            "cdb_row_plan": cdb_row_plan,
            "parsed_cdb": {
                "count": parsed.count,
                "pin_refs": [row.ref for row in parsed.pin_rows],
                "property_refs": [row.ref for row in parsed.property_rows],
            },
            "device_plan": device_plan,
            "section_pointers": pointers,
            "object_refs": accepted_v1.base_iso.refs_in(chunk),
            "cdb_refs": accepted_v1.base_iso.refs_in(cdb),
            "marker_counts": accepted_v1.base_iso.mixed.marker_counts(chunk) | {"7447": chunk.count(b"7447")},
            "cdb_marker_counts": accepted_v1.base_iso.mixed.marker_counts(cdb) | {"7447": cdb.count(b"7447")},
            "static_validation_issues": accepted_v1.base_iso.static_issues(output, case.expected_markers),
        },
    )


def write_analog_subset_case(case: AnalogSubsetCase) -> dict[str, object]:
    donor = subset_v1.donor_by_key(case.donor_key)
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    donor_dsn = seq.read_internal_file(donor.path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(donor.path, "ROOT.CDB")
    original_chunk = seq._extract_object_chunk(donor_dsn)
    regions = subset_v1.discover_regions(original_chunk)
    subset_chunk, kept_regions, removed_regions = subset_v1.build_subset_chunk(original_chunk, regions, case.keep_markers)

    dsn_patch_plan: dict[str, object] | None = None
    cdb_patch_plan: list[dict[str, object]] = []
    if case.patch_4060_model:
        subset_chunk, dsn_patch_plan = _patch_4060_dsn_chunk(subset_chunk, modfile=case.patch_4060_model)
        donor_cdb, cdb_patch_plan = _patch_4060_cdb(donor_cdb, modfile=case.patch_4060_model)

    label_plan: list[dict[str, object]] = []
    mutations: list[dict[str, object]] = []
    if case.mutate_labels:
        replacements, label_plan = subset_v1.mixed.topology_preserving_replacements(subset_chunk)
        subset_chunk, mutations = seq.patch_bidir_labels(subset_chunk, replacements)

    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        subset_chunk,
        seq._device_section(donor_dsn),
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": donor_cdb,
        },
    )
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    removed_markers = tuple(sorted({str(region["marker"]) for region in removed_regions}))
    return _write_manifest(
        case_dir,
        output,
        {
            "case_id": case.case_id,
            "description": case.description,
            "method": "real_mixed_donor_subset_with_optional_4060_model_patch",
            "status": "temporary_pending_user_proteus_testing",
            "donor_key": donor.key,
            "donor": str(donor.path.relative_to(REPO)),
            "keep_markers": case.keep_markers,
            "removed_markers": removed_markers,
            "terminal_policy": "retained visible endpoints use donor-native $TERBIDIR records",
            "composition_policy": "complete object-region subset removal; full donor device section; optional CDB/DSN property patch",
            "label_plan": label_plan,
            "mutations": mutations,
            "kept_regions": kept_regions,
            "removed_regions": removed_regions,
            "patch_4060_dsn": dsn_patch_plan,
            "patch_4060_cdb": cdb_patch_plan,
            "section_pointers": pointers,
            "marker_counts": subset_v1.mixed.marker_counts(chunk),
            "cdb_marker_counts": subset_v1.mixed.marker_counts(cdb),
            "static_validation_issues": subset_v1.static_issues(output, case.keep_markers, removed_markers, mutations),
        },
    )


def write_whole_donor_case(case: WholeDonorCase) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"
    donor_dsn = seq.read_internal_file(case.donor_path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(case.donor_path, "ROOT.CDB")
    chunk = seq._extract_object_chunk(donor_dsn)

    dsn_patch_plan: dict[str, object] | None = None
    cdb_patch_plan: list[dict[str, object]] = []
    if case.patch_4060_model:
        chunk, dsn_patch_plan = _patch_4060_dsn_chunk(chunk, modfile=case.patch_4060_model)
        donor_cdb, cdb_patch_plan = _patch_4060_cdb(donor_cdb, modfile=case.patch_4060_model)

    label_plan: list[dict[str, object]] = []
    mutations: list[dict[str, object]] = []
    if case.mutate_labels and chunk.count(b"$TERBIDIR"):
        replacements, label_plan = subset_v1.mixed.topology_preserving_replacements(chunk)
        chunk, mutations = seq.patch_bidir_labels(chunk, replacements)

    registry = seq.FixtureRegistry.load()
    base = registry.get("e001_empty")
    dsn, pointers = seq.build_dsn_with_device_section(
        seq.read_internal_file(base.path, "ROOT.DSN"),
        donor_dsn,
        chunk,
        seq._device_section(donor_dsn),
    )
    dsn = seq.patch_root_dsn_version(dsn, seq.PROTEUS_813)
    seq.write_project_from_parts(
        base.path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(seq.read_internal_file(base.path, "PROJECT.XML"), seq.PROTEUS_813),
            "ROOT.DSN": dsn,
            "ROOT.CDB": donor_cdb,
        },
    )
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    issues: list[str] = []
    for marker in case.required_markers:
        raw = marker.encode("ascii")
        if raw not in chunk:
            issues.append(f"expected DSN marker {marker} missing")
        if raw not in cdb:
            issues.append(f"expected CDB marker {marker} missing")
    if chunk.count(b"$TERBIDIR") and chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    return _write_manifest(
        case_dir,
        output,
        {
            "case_id": case.case_id,
            "description": case.description,
            "method": "whole_donor_object_with_optional_label_or_4060_model_patch",
            "status": "temporary_pending_user_proteus_testing",
            "donor": str(case.donor_path.relative_to(REPO)),
            "required_markers": case.required_markers,
            "terminal_policy": "donor-native visible endpoints retained; optional topology-preserving relabel",
            "label_plan": label_plan,
            "mutations": mutations,
            "patch_4060_dsn": dsn_patch_plan,
            "patch_4060_cdb": cdb_patch_plan,
            "section_pointers": pointers,
            "marker_counts": subset_v1.mixed.marker_counts(chunk),
            "cdb_marker_counts": subset_v1.mixed.marker_counts(cdb),
            "static_validation_issues": issues,
        },
    )


def _write_manifest(case_dir: Path, output: Path, manifest: dict[str, object]) -> dict[str, object]:
    dsn = seq.read_internal_file(output, "ROOT.DSN")
    cdb = seq.read_internal_file(output, "ROOT.CDB")
    chunk = seq._extract_object_chunk(dsn)
    manifest = dict(manifest)
    manifest["container"] = {
        key: (str(value) if key == "path" else value)
        for key, value in seq.inspect_pdsprj(output).__dict__.items()
    }
    manifest["object_chunk_size"] = len(chunk)
    manifest["terminal_count"] = chunk.count(b"$TERBIDIR") + chunk.count(b"$TERINPUT") + chunk.count(b"$TEROUTPUT")
    manifest["wire_count"] = chunk.count(b"WIRE")
    manifest["output_hashes"] = {
        "project": seq._sha256_bytes(output.read_bytes()),
        "ROOT.DSN": seq._sha256_bytes(dsn),
        "ROOT.CDB": seq._sha256_bytes(cdb),
        "object_chunk": seq._sha256_bytes(chunk),
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "terminal_plan.json").write_text(json.dumps(seq.bidir_events(chunk), indent=2) + "\n", encoding="utf-8")
    return manifest


CROSS_BASELINE_CASES: tuple[CrossBaselineCase, ...] = (
    CrossBaselineCase(
        "T01_SAFE_SHIFT_DIVIDERS_NO_LAYOUT",
        "No-layout accepted baseline: 74HC595/74HC165 with 4017/4020/74HC4024.",
        (accepted_v1.MISC_SHIFT, accepted_v1.SEQ_DIVIDERS),
        "misc_logic_analog",
        ("74HC595", "74HC165", "4017", "4020", "74HC4024"),
    ),
    CrossBaselineCase(
        "T02_SAFE_DECODER_SYNC_NO_LAYOUT",
        "No-layout accepted baseline: 7447 with 74HC160/161/163.",
        (accepted_v1.MISC_DECODER, accepted_v1.SEQ_SYNC),
        "seq_counters_all",
        ("7447", "74HC160", "74HC161", "74HC163"),
    ),
)


ANALOG_CASES: tuple[AnalogSubsetCase, ...] = (
    AnalogSubsetCase(
        "T03_ANALOG_RCL_SHIFT_REGISTERS_SUBSET",
        "Real mixed donor subset: RLC, NPN, PNP, LM741, CAP-ELEC plus 74HC595/74HC165.",
        "misc_logic_analog",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "74HC595", "74HC165"),
    ),
    AnalogSubsetCase(
        "T04_ANALOG_RCL_DIVIDERS_SUBSET",
        "Real mixed donor subset: RLC, NPN, PNP, LM741, CAP-ELEC plus 4017/4020/74HC4024.",
        "seq_4017_4020_4024",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "4017", "4020", "74HC4024"),
    ),
    AnalogSubsetCase(
        "T07_4060_ANALOG_RCL_PREFIX_MODFILE_MDF",
        "4060 subset from the real mixed counter donor with analog/RLC prefix and 4060.MDF model metadata patched.",
        "seq_counters_all",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC", "74HC4060"),
        patch_4060_model="4060.MDF",
    ),
    AnalogSubsetCase(
        "T08_ANALOG_ONLY_RLC_BJT_OPAMP_ECAP_MUTATED",
        "Analog/basic component control: RLC plus NPN, PNP, LM741, and CAP-ELEC with labels mutated.",
        "analog_only",
        ("LM741", "CAPACITOR", "PNP", "NPN", "REALIND", "RESISTOR", "CAP-ELEC"),
    ),
)


WHOLE_DONOR_CASES: tuple[WholeDonorCase, ...] = (
    WholeDonorCase(
        "T05_4060_RLC_MODFILE_MDF",
        "74HC4060 with RLC, patched in both DSN and CDB to add MODFILE=4060.MDF and VOLTAGE=4.5V.",
        REPO / "proteus" / "active" / "evidence" / "donors" / "sequential_ics_batch3" / "4_74HC4060withRLC.pdsprj",
        ("74HC4060", "RESISTOR", "CAPACITOR", "REALIND"),
        patch_4060_model="4060.MDF",
    ),
    WholeDonorCase(
        "T06_4060_RLC_MODFILE_NOEXT",
        "74HC4060 with RLC, patched in both DSN and CDB to add MODFILE=4060 and VOLTAGE=4.5V.",
        REPO / "proteus" / "active" / "evidence" / "donors" / "sequential_ics_batch3" / "4_74HC4060withRLC.pdsprj",
        ("74HC4060", "RESISTOR", "CAPACITOR", "REALIND"),
        patch_4060_model="4060",
    ),
    WholeDonorCase(
        "T09_NE555_RLC_LABEL_MUTATION",
        "NE555 with RLC, topology-preserving terminal label mutation retained as a real edit rather than an exact copy.",
        REPO / "proteus" / "active" / "evidence" / "donors" / "analog_misc_batch1" / "2_NE555WITHRLC.pdsprj",
        ("NE555", "RESISTOR", "CAPACITOR", "REALIND"),
        mutate_labels=True,
    ),
)


def write_archive() -> str:
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
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests: list[dict[str, object]] = []
    manifests.extend(write_cross_baseline_case(case) for case in CROSS_BASELINE_CASES)
    manifests.extend(write_analog_subset_case(case) for case in ANALOG_CASES)
    manifests.extend(write_whole_donor_case(case) for case in WHOLE_DONOR_CASES)
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_FOCUSED_V4_TEMP_2026_06_10",
        "purpose": "Reject V3 coordinate-scan layout for T01/T02, patch 74HC4060 model metadata, and keep analog/NE555 manipulations in small focused cases.",
        "status": "temporary_pending_user_proteus_testing",
        "testing_order": [
            "T01-T02: no-layout accepted baselines for the two V3 failures.",
            "T03-T04: analog/RLC subset controls with NPN, PNP, LM741, and CAP-ELEC.",
            "T05-T07: 74HC4060 model metadata patch variants.",
            "T08: analog/basic-only mutation control.",
            "T09: NE555/RLC label-mutation control.",
        ],
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
