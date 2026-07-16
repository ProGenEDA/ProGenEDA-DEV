"""Generate focused V6 mixed analog/NE555 diagnostics with no 74HC4060.

V5 manual Proteus testing proved two useful facts:

- exact donor-native 74HC4060 still fails simulation with no model specified;
- donor-native analog/basic and NE555/RLC edits work.

This pack deliberately avoids 74HC4060 and the large mixed counter donor. It
keeps working donor-native metadata and makes a few small real terminal-label
edits so the next manual test advances the accepted analog/NE555 route instead
of repeating the 4060 model failure.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


REPO = Path(__file__).resolve().parents[4]
V5_SCRIPT = REPO / "proteus" / "experiments" / "runners" / "2026-06-10" / "generate_mixed_ic_focused_v5_donor_native_temp.py"
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "mixed_ic_focused_v6_no4060_temp_2026_06_10"
ARCHIVE_PATH = REPO / "proteus" / "experiments" / "runs" / "MIXED_IC_FOCUSED_V6_NO4060_TEMP_2026_06_10.zip"


def _load_v5():
    spec = importlib.util.spec_from_file_location("mixed_ic_focused_v5_for_v6", V5_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load V5 helper from {V5_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v5 = _load_v5()
seq = v5.seq
mixed = v5.mixed


@dataclass(frozen=True)
class FocusedV6Case:
    case_id: str
    description: str
    donor_path: Path
    required_markers: tuple[str, ...]
    replacements_by_index: dict[int, str]
    no_markers: tuple[str, ...] = ("74HC4060",)


def analog_topology_replacements() -> dict[int, str]:
    return v5.topology_preserving_replacements(v5.DONOR_ANALOG_ONLY)


def analog_lm741_output_to_rlc_node_replacements() -> dict[int, str]:
    """Tie the accepted analog donor's LM741 output-side label to the RLC node.

    V5's terminal plan shows original index 0 is the LM741 output-side donor
    net labelled "6", and index 5 is the donor RLC/resistor node labelled "r1".
    Reusing the same label joins those two nets while preserving the remaining
    donor topology.
    """

    replacements = analog_topology_replacements()
    replacements[0] = "AO0"
    replacements[5] = "AO0"
    return replacements


def ne555_u1_q_to_rlc_replacements() -> dict[int, str]:
    return v5.replacements_ne555_q_to_existing_rlc(v5.DONOR_NE555_RLC)


def ne555_u2_q_to_rlc_replacements() -> dict[int, str]:
    """Tie the second NE555 Q output to the existing RLC input."""

    replacements = v5.sequential_unique_replacements(v5.DONOR_NE555_RLC, max_index=15)
    replacements[8] = "NQ2"
    replacements[18] = "NQ2"
    return replacements


CASES: tuple[FocusedV6Case, ...] = (
    FocusedV6Case(
        "T01_ANALOG_ONLY_ACCEPTED_LABELS_NATIVE",
        "Accepted V5 analog/basic donor-native topology-preserving label mutation baseline.",
        v5.DONOR_ANALOG_ONLY,
        ("RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
        analog_topology_replacements(),
    ),
    FocusedV6Case(
        "T02_ANALOG_LM741_OUTPUT_TO_RLC_NODE_NATIVE",
        "Real analog edit: LM741 output-side terminal and RLC/resistor node share AO0.",
        v5.DONOR_ANALOG_ONLY,
        ("RESISTOR", "CAPACITOR", "REALIND", "NPN", "PNP", "LM741", "CAP-ELEC"),
        analog_lm741_output_to_rlc_node_replacements(),
    ),
    FocusedV6Case(
        "T03_NE555_U1_Q_DRIVES_RLC_NATIVE",
        "Accepted V5 NE555 edit: first NE555 Q output drives the existing RLC input.",
        v5.DONOR_NE555_RLC,
        ("NE555", "RESISTOR", "CAPACITOR", "REALIND"),
        ne555_u1_q_to_rlc_replacements(),
    ),
    FocusedV6Case(
        "T04_NE555_U2_Q_DRIVES_RLC_NATIVE",
        "Second-unit NE555 edit: U2 Q output drives the existing RLC input.",
        v5.DONOR_NE555_RLC,
        ("NE555", "RESISTOR", "CAPACITOR", "REALIND"),
        ne555_u2_q_to_rlc_replacements(),
    ),
)


def _write_project_from_case(case: FocusedV6Case) -> dict[str, object]:
    case_dir = OUT_ROOT / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output = case_dir / f"{case.case_id}.pdsprj"

    donor_dsn = seq.read_internal_file(case.donor_path, "ROOT.DSN")
    donor_cdb = seq.read_internal_file(case.donor_path, "ROOT.CDB")
    donor_project = seq.read_internal_file(case.donor_path, "PROJECT.XML")
    chunk = seq._extract_object_chunk(donor_dsn)
    events = seq.bidir_events(chunk)
    label_plan = [
        {
            "terminal_index": index,
            "old_label": events[index]["label"],
            "new_label": new_label,
            "angle_tenths": events[index]["angle_tenths"],
            "suffix": events[index]["suffix"],
        }
        for index, new_label in sorted(case.replacements_by_index.items())
    ]
    chunk, mutations = seq.patch_bidir_labels(chunk, case.replacements_by_index)
    dsn, pointers = v5.rebuild_donor_native_dsn(donor_dsn, chunk)

    seq.write_project_from_parts(
        case.donor_path,
        output,
        {
            "PROJECT.XML": seq.patch_project_xml_version(donor_project, seq.PROTEUS_813),
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
    for marker in case.no_markers:
        raw = marker.encode("ascii")
        if raw in chunk or raw in cdb:
            issues.append(f"forbidden marker {marker} present")
    if chunk.count(b"$TERBIDIR") != chunk.count(b"WIRE"):
        issues.append("bidirectional terminal count does not match WIRE count")
    for mutation in mutations:
        if chunk.count(str(mutation["new"]).encode("ascii")) == 0:
            issues.append(f"mutated label {mutation['new']} not present")

    manifest = {
        "case_id": case.case_id,
        "description": case.description,
        "method": "donor_native_no4060_focused_label_edit",
        "status": "temporary_pending_user_proteus_testing",
        "donor": str(case.donor_path.relative_to(REPO)),
        "required_markers": case.required_markers,
        "forbidden_markers": case.no_markers,
        "terminal_policy": "analog/basic and NE555 visible pins/endpoints use donor-native $TERBIDIR records",
        "model_policy": "74HC4060 is intentionally absent after V5 exact donor-native no-model failures",
        "section_pointers": pointers,
        "label_plan": label_plan,
        "mutations": mutations,
        "container": {
            key: (str(value) if key == "path" else value)
            for key, value in seq.inspect_pdsprj(output).__dict__.items()
        },
        "marker_counts": mixed.marker_counts(chunk),
        "cdb_marker_counts": mixed.marker_counts(cdb),
        "object_chunk_size": len(chunk),
        "terminal_count": chunk.count(b"$TERBIDIR") + chunk.count(b"$TERINPUT") + chunk.count(b"$TEROUTPUT"),
        "wire_count": chunk.count(b"WIRE"),
        "static_validation_issues": issues,
        "output_hashes": {
            "project": seq._sha256_bytes(output.read_bytes()),
            "ROOT.DSN": seq._sha256_bytes(dsn),
            "ROOT.CDB": seq._sha256_bytes(cdb),
            "object_chunk": seq._sha256_bytes(chunk),
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
                info.date_time = (2026, 6, 10, 0, 0, 0)
                info.compress_type = ZIP_DEFLATED
                info.create_system = 0
                info.external_attr = 0
                zf.writestr(info, file_path.read_bytes())
    return seq._sha256_bytes(ARCHIVE_PATH.read_bytes())


def main() -> None:
    missing = [str(case.donor_path) for case in CASES if not case.donor_path.exists()]
    if missing:
        raise FileNotFoundError("\n".join(missing))
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    manifests = [_write_project_from_case(case) for case in CASES]
    summary_issues = {
        str(item["case_id"]): item["static_validation_issues"]
        for item in manifests
        if item["static_validation_issues"]
    }
    summary = {
        "batch": "MIXED_IC_FOCUSED_V6_NO4060_TEMP_2026_06_10",
        "purpose": "Advance only the V5 accepted analog/basic and NE555 routes. 74HC4060 is intentionally absent because exact donor-native V5 T01 failed simulation with no model specified.",
        "status": "temporary_pending_user_proteus_testing",
        "v5_user_result": "T05 and T06 worked properly; all 4060-containing cases failed with no-model partition errors.",
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
