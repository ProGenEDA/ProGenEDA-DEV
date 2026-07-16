"""Create the Camber handoff pack for the component placer reset.

This is analysis-only. It does not generate Proteus circuit packs, does not
delete existing files, and does not mutate donor projects.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.pdsprj import inspect_pdsprj, read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk, _sha256_bytes  # noqa: E402

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "camber_component_placer_analysis_2026_06_15"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "CAMBER_COMPONENT_PLACER_ANALYSIS_2026_06_15.zip"
STAGING = REPO / "proteus" / "experiments" / "runs" / "camber_component_placer_analysis_2026_06_15.building"

FAILED_PACK = REPO / "proteus" / "experiments" / "runs" / "component_placer_seq_16x_v1_temp_2026_06_15"
FAILED_ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "COMPONENT_PLACER_SEQ_16X_V1_TEMP_2026_06_15.zip"
MEGA_DONOR_COPY = REPO / "proteus" / "active" / "evidence" / "donors" / "manual_downloads_20260615" / "component_placer" / "16x_seq_combo_mega_donor.pdsprj"
MEGA_DONOR_ORIGINAL = Path(
    r"C:\Users\tahab\Downloads\ICcombinationfinal\16x_4X_160,74,76,85,157,160,174,266,283,4027,7447,7490withallcombunational_21Rlc.pdsprj"
)
SOURCE_PLAN = Path(r"C:\Users\tahab\.codex\attachments\e7a33824-157c-40fa-82bd-5d5e568c26d2\pasted-text.txt")

TARGET_FAMILIES = (
    "7490",
    "74HC160",
    "74HC74",
    "74HC76",
    "74HC85",
    "74HC157",
    "74HC174",
    "74HC283",
    "4027",
    "7447",
    "4511",
    "74HC151",
    "74HC192",
)

LATER_FAMILIES = (
    "74HC00",
    "74HC02",
    "74HC04",
    "74HC08",
    "74HC32",
    "74HC86",
    "74HC266",
    "RESISTOR",
    "CAPACITOR",
    "CAP-ELEC",
    "ELEC-CAP",
    "REALIND",
    "LED",
    "NPN",
    "PNP",
    "LM741",
    "NE555",
    "VSOURCE",
    "ISOURCE",
    "ACVSOURCE",
    "$TERPOWER",
    "$TERGROUND",
    "$TERINPUT",
    "$TEROUTPUT",
    "$TERBIDIR",
)

ALL_MARKERS = tuple(sorted(set(TARGET_FAMILIES + LATER_FAMILIES), key=len, reverse=True))
TERMINAL_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT", b"$TERPOWER", b"$TERGROUND")
WIRE_MARKER = b"WIRE"
RECORD_START_RE = re.compile(rb"\xff([\x02-\x08])(U\d+(?::[A-Z])?)")


@dataclass(frozen=True)
class IncludedFile:
    relative_path: str
    absolute_original_path: str
    size: int
    sha256: str
    category: str
    why_included: str


def log(action: str, **data: object) -> None:
    row = {"action": action, **data}
    with (STAGING / "ACTION_LOG.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True) + "\n")


def sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def rel_to_repo(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO.resolve()))
    except ValueError:
        return str(path)


def safe_name(path: Path, prefix: str = "") -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._")[:90] or "file"
    suffix = path.suffix if path.suffix.lower() == ".pdsprj" else ".pdsprj"
    digest = sha256_file(path)[:10] if path.exists() else "missing"
    return f"{prefix}{stem}__{digest}{suffix}"


def copy_included(src: Path, dst_rel: str, category: str, why: str) -> IncludedFile:
    dst = STAGING / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    log("copy_file", source=str(src), destination=dst_rel, category=category)
    return IncludedFile(
        relative_path=dst_rel.replace("\\", "/"),
        absolute_original_path=str(src.resolve()),
        size=dst.stat().st_size,
        sha256=sha256_file(dst),
        category=category,
        why_included=why,
    )


def write_text(rel: str, text: str, category: str, why: str) -> IncludedFile:
    path = STAGING / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    log("write_text", destination=rel, category=category)
    return IncludedFile(
        relative_path=rel.replace("\\", "/"),
        absolute_original_path=str(path.resolve()),
        size=path.stat().st_size,
        sha256=sha256_file(path),
        category=category,
        why_included=why,
    )


def write_json(rel: str, data: object, category: str, why: str) -> IncludedFile:
    return write_text(rel, json.dumps(data, indent=2, sort_keys=True) + "\n", category, why)


def try_read_project(path: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "zip_readable": False,
        "required_files": {},
        "internal_sizes": {},
        "component_marker_counts": {},
        "refs": [],
        "ref_count": 0,
        "duplicate_u_record_refs": [],
        "package_counts": {},
        "contains_terminals": False,
        "contains_wires": False,
        "terminal_counts": {},
        "wire_count": 0,
        "object_chunk_size": None,
        "parse_errors": [],
    }
    try:
        info = inspect_pdsprj(path)
        result["zip_readable"] = True
        result["required_files"] = {
            "PROJECT.XML": info.has_project_xml,
            "ROOT.DSN": info.has_root_dsn,
            "ROOT.CDB": info.has_root_cdb,
            "SCRIPTS/PWRRAILS.DAT": info.has_pwrails,
        }
        for name in info.names:
            try:
                result["internal_sizes"][name] = len(read_internal_file(path, name))
            except Exception as exc:  # pragma: no cover - diagnostic only
                result["parse_errors"].append(f"cannot read {name}: {exc}")
    except Exception as exc:
        result["parse_errors"].append(f"zip inspect failed: {exc}")
        return result

    try:
        dsn = read_internal_file(path, "ROOT.DSN")
        cdb = read_internal_file(path, "ROOT.CDB") if result["required_files"].get("ROOT.CDB") else b""
        chunk = _extract_object_chunk(dsn)
        result["object_chunk_size"] = len(chunk)
        marker_counts = {marker: chunk.count(marker.encode("ascii")) + cdb.count(marker.encode("ascii")) for marker in ALL_MARKERS}
        result["component_marker_counts"] = {key: value for key, value in marker_counts.items() if value}
        terminal_counts = {marker.decode("ascii"): chunk.count(marker) for marker in TERMINAL_MARKERS}
        result["terminal_counts"] = terminal_counts
        result["contains_terminals"] = any(terminal_counts.values())
        wire_count = chunk.count(WIRE_MARKER)
        result["wire_count"] = wire_count
        result["contains_wires"] = wire_count > 0
        refs = sorted(set(match.group().decode("ascii") for match in re.finditer(rb"U\d+(?::[A-Z])?", chunk + cdb)))
        result["refs"] = refs[:200]
        result["ref_count"] = len(refs)
        u_records = [match.group(2).decode("ascii") for match in RECORD_START_RE.finditer(chunk)]
        duplicates = [ref for ref, count in Counter(u_records).items() if count > 1]
        result["duplicate_u_record_refs"] = duplicates[:100]
        result["package_counts"] = detect_package_counts(chunk)
    except Exception as exc:
        result["parse_errors"].append(f"ROOT.DSN/CDB analysis failed: {exc}")
    return result


def detect_package_counts(chunk: bytes) -> dict[str, int]:
    starts = [(match.start(), match.group(2).decode("ascii")) for match in RECORD_START_RE.finditer(chunk)]
    grouped: dict[str, set[str]] = defaultdict(set)
    for index, (start, ref) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else max(0, len(chunk) - 1)
        raw = chunk[start:end]
        hits = [marker for marker in TARGET_FAMILIES if marker.encode("ascii") in raw]
        if not hits:
            continue
        family = sorted(hits, key=len, reverse=True)[0]
        grouped[family].add(ref.split(":", 1)[0])
    return {family: len(packages) for family, packages in sorted(grouped.items())}


def classify_project(path: Path, analysis: dict[str, object]) -> str:
    lower = str(path).lower()
    package_counts = analysis.get("package_counts") if isinstance(analysis.get("package_counts"), dict) else {}
    total_packages = sum(int(value) for value in package_counts.values()) if package_counts else 0
    if path.is_relative_to(FAILED_PACK):
        return "failed_generated"
    if "empty" in lower or "e001" in lower:
        return "base_or_empty"
    if "template" in lower:
        return "template"
    if total_packages >= 50 or "mega" in lower or "16x" in lower or "all" in lower:
        return "mega_or_large_multi_family"
    if "pair" in lower or len(package_counts) == 2:
        return "pair_donor"
    if total_packages == 1 and len(package_counts) == 1:
        return "single_component_donor"
    if total_packages > 1 and len(package_counts) == 1:
        return "family_repetition_donor"
    if "experiment" in lower:
        return "experiment_output"
    if "donor" in lower or "manual_download" in lower:
        return "donor"
    return "unknown"


def can_satisfy_removal_only(analysis: dict[str, object]) -> dict[str, object]:
    package_counts = analysis.get("package_counts") if isinstance(analysis.get("package_counts"), dict) else {}
    same_family_23 = sorted(family for family, count in package_counts.items() if int(count) >= 23)
    same_family_15 = sorted(family for family, count in package_counts.items() if int(count) >= 15)
    pair_3 = []
    families = sorted(family for family, count in package_counts.items() if int(count) >= 1)
    for left_index, left in enumerate(families):
        for right in families[left_index + 1 :]:
            if int(package_counts[left]) + int(package_counts[right]) >= 3:
                pair_3.append([left, right])
    return {
        "possible": bool(same_family_15 or pair_3),
        "same_family_15": same_family_15,
        "same_family_23": same_family_23,
        "three_component_pairs_possible": pair_3[:200],
    }


def scan_projects() -> list[dict[str, object]]:
    candidates: dict[Path, str] = {}
    roots = [REPO / "proteus" / "active" / "evidence", REPO / "proteus" / "experiments" / "runs", REPO / "proteus" / "active" / "fixtures", REPO / "templates", REPO / "out"]
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*.pdsprj"):
            if OUT_ROOT in path.parents or STAGING in path.parents:
                continue
            candidates[path.resolve()] = "repo_scan"
    for extra in (MEGA_DONOR_ORIGINAL, MEGA_DONOR_COPY):
        if extra.exists():
            candidates[extra.resolve()] = "explicit_mega_donor"

    inventory: list[dict[str, object]] = []
    for path in sorted(candidates):
        analysis = try_read_project(path)
        classification = classify_project(path, analysis)
        component_counts = analysis.get("component_marker_counts") if isinstance(analysis.get("component_marker_counts"), dict) else {}
        package_counts = analysis.get("package_counts") if isinstance(analysis.get("package_counts"), dict) else {}
        relevant = bool(component_counts) or classification in {
            "base_or_empty",
            "failed_generated",
            "template",
            "mega_or_large_multi_family",
            "family_repetition_donor",
            "pair_donor",
            "single_component_donor",
        }
        if not relevant:
            continue
        inventory.append(
            {
                "path": rel_to_repo(path),
                "absolute_path": str(path),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
                "classification": classification,
                "component_families_detected": sorted(component_counts),
                "component_marker_counts": component_counts,
                "package_counts": package_counts,
                "refs_detected_sample": analysis.get("refs", []),
                "ref_count": analysis.get("ref_count", 0),
                "contains_terminals": analysis.get("contains_terminals", False),
                "contains_wires": analysis.get("contains_wires", False),
                "terminal_counts": analysis.get("terminal_counts", {}),
                "wire_count": analysis.get("wire_count", 0),
                "appears_to_be": classification,
                "can_possibly_satisfy_removal_only_generation": can_satisfy_removal_only(analysis),
                "notes": donor_notes(path, analysis, classification),
                "scan_source": candidates[path],
            }
        )
    return inventory


def donor_notes(path: Path, analysis: dict[str, object], classification: str) -> str:
    package_counts = analysis.get("package_counts") if isinstance(analysis.get("package_counts"), dict) else {}
    missing_23 = [family for family in TARGET_FAMILIES if int(package_counts.get(family, 0)) < 23]
    notes = [f"classified as {classification}"]
    if path.resolve() == MEGA_DONOR_COPY.resolve() or path.resolve() == MEGA_DONOR_ORIGINAL.resolve():
        notes.append("16x mega donor used by the failed body-only component placer pack")
        if missing_23:
            notes.append("cannot satisfy 23x for: " + ", ".join(missing_23))
    if analysis.get("contains_terminals"):
        notes.append("contains terminal records")
    if analysis.get("contains_wires"):
        notes.append("contains WIRE records")
    if analysis.get("duplicate_u_record_refs"):
        notes.append("duplicate U-record refs detected")
    if analysis.get("parse_errors"):
        notes.append("parse warnings: " + "; ".join(str(x) for x in analysis["parse_errors"][:3]))
    return "; ".join(notes)


def audit_failed_pack() -> list[dict[str, object]]:
    audits: list[dict[str, object]] = []
    if not FAILED_PACK.exists():
        return audits
    for project in sorted(FAILED_PACK.glob("*/*.pdsprj")):
        manifest_path = project.parent / "manifest.json"
        manifest: dict[str, object] = {}
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                manifest = {"manifest_parse_error": "invalid JSON"}
        analysis = try_read_project(project)
        package_counts = analysis.get("package_counts") if isinstance(analysis.get("package_counts"), dict) else {}
        static_checks = {
            "zip_readable": analysis.get("zip_readable"),
            "required_files": analysis.get("required_files"),
            "parse_errors": analysis.get("parse_errors"),
            "object_chunk_size": analysis.get("object_chunk_size"),
            "static_validation_issues_from_manifest": manifest.get("static_validation_issues", []),
        }
        probable_reasons = []
        if not analysis.get("contains_terminals") and not analysis.get("contains_wires"):
            probable_reasons.append("body-only output removed all terminal and wire records; Proteus may require pin-anchor/association records that were trimmed")
        if manifest.get("metadata_policy") and "full 16x donor ROOT.CDB" in str(manifest.get("metadata_policy")):
            probable_reasons.append("full donor CDB/device metadata was copied while DSN kept only selected body packets, likely leaving metadata/object mismatch")
        if analysis.get("duplicate_u_record_refs"):
            probable_reasons.append("duplicate U-record references detected")
        if not package_counts:
            probable_reasons.append("no target package counts detected from U body records")
        if not probable_reasons:
            probable_reasons.append("not statically obvious; requires byte-level donor comparison")
        audits.append(
            {
                "file_name": project.name,
                "relative_path": rel_to_repo(project),
                "requested_composition": {
                    "case_id": manifest.get("case_id", project.parent.name),
                    "description": manifest.get("description", ""),
                    "families": manifest.get("families", []),
                    "package_counts": manifest.get("package_counts", {}),
                    "selected_packages": manifest.get("selected_packages", []),
                },
                "file_size": project.stat().st_size,
                "sha256": sha256_file(project),
                "static_checks": static_checks,
                "wires_or_terminals_present": {
                    "contains_terminals": analysis.get("contains_terminals", False),
                    "contains_wires": analysis.get("contains_wires", False),
                    "terminal_counts": analysis.get("terminal_counts", {}),
                    "wire_count": analysis.get("wire_count", 0),
                },
                "component_counts_detected": package_counts,
                "duplicate_references": {
                    "duplicate_u_record_refs": analysis.get("duplicate_u_record_refs", []),
                    "obvious_duplicate_refs_present": bool(analysis.get("duplicate_u_record_refs")),
                },
                "missing_model_or_name_signatures": detect_model_name_signatures(project),
                "probable_failure_reason": probable_reasons,
                "send_to_camber": "full_file_included",
            }
        )
    return audits


def detect_model_name_signatures(path: Path) -> dict[str, object]:
    result = {
        "contains_properties_text": False,
        "contains_modfile_text": False,
        "contains_component_id_text": False,
        "contains_component_value_text": False,
        "warnings": [],
    }
    try:
        chunk = _extract_object_chunk(read_internal_file(path, "ROOT.DSN"))
        result["contains_properties_text"] = b"PROPERTIES" in chunk
        result["contains_modfile_text"] = b"MODFILE" in chunk
        result["contains_component_id_text"] = b"COMPONENT ID" in chunk
        result["contains_component_value_text"] = b"COMPONENT VALUE" in chunk
        if not result["contains_modfile_text"]:
            result["warnings"].append("MODFILE text not found in object chunk")
    except Exception as exc:
        result["warnings"].append(f"signature scan failed: {exc}")
    return result


def select_learning_donors(inventory: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: list[dict[str, object]] = []
    seen: set[str] = set()

    def add(row: dict[str, object], reason: str) -> None:
        key = str(row["absolute_path"])
        if key in seen:
            return
        if not Path(key).exists():
            return
        seen.add(key)
        selected.append({**row, "selection_reason": reason})

    for row in inventory:
        if Path(str(row["absolute_path"])).resolve() in {MEGA_DONOR_COPY.resolve(), MEGA_DONOR_ORIGINAL.resolve()}:
            add(row, "primary failed-pack mega donor")

    for row in inventory:
        classification = str(row["classification"])
        package_counts = row.get("package_counts") if isinstance(row.get("package_counts"), dict) else {}
        target_hits = [family for family in TARGET_FAMILIES if int(package_counts.get(family, 0)) > 0]
        if not target_hits:
            continue
        if classification in {"single_component_donor", "family_repetition_donor", "pair_donor", "mega_or_large_multi_family"}:
            add(row, f"{classification} with target families {', '.join(target_hits[:6])}")
        if len(selected) >= 90:
            break

    for row in inventory:
        if len(selected) >= 110:
            break
        path = str(row["path"]).lower()
        if "host_donor_recovery" in path or "accepted" in path or "golden" in path:
            add(row, "previous accepted/golden experiment output useful for failure comparison")
    return selected


def copy_failed_cases(audits: list[dict[str, object]], included: list[IncludedFile]) -> None:
    for audit in audits:
        src = REPO / str(audit["relative_path"])
        if not src.exists():
            continue
        dst_rel = f"REPRESENTATIVE_FAILURES/ALL_FAILED_CASES/{src.parent.name}/{src.name}"
        included.append(
            copy_included(
                src,
                dst_rel,
                "failed_generated_output",
                "All 140 failed generated cases are included because total size is manageable.",
            )
        )
        manifest = src.parent / "manifest.json"
        if manifest.exists():
            included.append(
                copy_included(
                    manifest,
                    f"REPRESENTATIVE_FAILURES/ALL_FAILED_CASES/{src.parent.name}/manifest.json",
                    "failed_generated_manifest",
                    "Manifest for the failed generated case.",
                )
            )


def copy_learning_donors(selected: list[dict[str, object]], included: list[IncludedFile]) -> None:
    for index, row in enumerate(selected, 1):
        src = Path(str(row["absolute_path"]))
        name = safe_name(src, f"D{index:03d}_")
        included.append(
            copy_included(
                src,
                f"DONORS_FOR_REMOVAL_LEARNING/{name}",
                "learning_donor",
                str(row.get("selection_reason", "selected donor for removal-only analysis")),
            )
        )


def build_comparison_tasks(inventory: list[dict[str, object]], audits: list[dict[str, object]]) -> list[dict[str, object]]:
    tasks: list[dict[str, object]] = []
    same_failures = [a for a in audits if str(a["requested_composition"]["case_id"]).startswith("SAME_")]
    pair_failures = [a for a in audits if str(a["requested_composition"]["case_id"]).startswith("PAIR3_")]
    for audit in same_failures[:10] + pair_failures[:10]:
        tasks.append(
            {
                "task_id": f"FAILED_{audit['requested_composition']['case_id']}",
                "before_file": rel_to_repo(MEGA_DONOR_COPY),
                "after_file": audit["relative_path"],
                "operation_type": "failed_generation",
                "target_component_family": audit["requested_composition"].get("families", []),
                "what_camber_should_compare": [
                    "object record boundaries",
                    "removed terminal/wire records",
                    "CDB/device metadata refs retained from donor",
                    "component body records and associated text/model fields",
                ],
                "expected_output": "Explain which required records were deleted or orphaned and provide validator signatures.",
            }
        )

    for family in TARGET_FAMILIES:
        donors = [
            row
            for row in inventory
            if int((row.get("package_counts") if isinstance(row.get("package_counts"), dict) else {}).get(family, 0)) > 0
        ]
        donors = sorted(donors, key=lambda row: (int((row.get("package_counts") or {}).get(family, 0)), int(row["size"])))
        if donors:
            tasks.append(
                {
                    "task_id": f"INVENTORY_{family}",
                    "before_file": donors[-1]["path"],
                    "after_file": None,
                    "operation_type": "inventory",
                    "target_component_family": family,
                    "what_camber_should_compare": [
                        "package count",
                        "subpart count",
                        "terminal/wire dependency",
                        "MODFILE/PACKAGE/ITFMOD properties",
                    ],
                    "expected_output": "component_fingerprints.json entry and donor_selector_rules.json coverage decision.",
                }
            )
        else:
            tasks.append(
                {
                    "task_id": f"TODO_DONOR_{family}",
                    "before_file": None,
                    "after_file": None,
                    "operation_type": "unknown",
                    "target_component_family": family,
                    "what_camber_should_compare": ["No donor found in current scan."],
                    "expected_output": "Add this to required_new_donors.md with exact donor shape.",
                }
            )

    tasks.extend(
        [
            {
                "task_id": "TODO_DELETION_VARIANT_SINGLE_FAMILY",
                "before_file": "manual donor with 23x one family",
                "after_file": "same donor manually saved after deleting down to 15x/5x/3x/1x",
                "operation_type": "deletion",
                "target_component_family": "all target families",
                "what_camber_should_compare": ["deleted object records", "CDB changes", "device section changes", "PROJECT.XML changes"],
                "expected_output": "deletion_patterns.json with exact records to remove and records that must remain.",
            },
            {
                "task_id": "TODO_MOVE_VARIANT",
                "before_file": "manual donor with several ICs",
                "after_file": "same donor manually saved after moving one IC",
                "operation_type": "move",
                "target_component_family": "representative IC package",
                "what_camber_should_compare": ["body coords", "pin coords", "reference/model/value text coords", "wire/terminal coords"],
                "expected_output": "move_patterns.json and reference_text_linkage_patterns.json.",
            },
            {
                "task_id": "TODO_RENAME_VARIANT",
                "before_file": "manual donor with labeled refs",
                "after_file": "same donor manually saved after changing visible ref/value",
                "operation_type": "rename",
                "target_component_family": "representative IC package",
                "what_camber_should_compare": ["visible ref text", "CDB ref", "hidden model/package ref", "duplicate reference protection"],
                "expected_output": "reference_text_linkage_patterns.json and validator_rules.json.",
            },
        ]
    )
    return tasks


def known_failure_signatures() -> list[dict[str, object]]:
    return [
        {
            "signature_id": "NO_MODEL_SPECIFIED",
            "message_patterns": ["No model specified for U*", "No CDB element record for element U*"],
            "category": "missing_model_or_cdb_metadata",
            "source": "Proteus netlist/partition analyzer reports observed during native IC experiments",
            "notes": "Usually indicates DSN component refs and CDB/device metadata are not coherent.",
        },
        {
            "signature_id": "DUPLICATE_PART_REFERENCE",
            "message_patterns": ["Duplicate part reference:*", "Duplicate part reference: X#########"],
            "category": "duplicate_ref_or_duplicate_hidden_id",
            "source": "Proteus netlist compiler reports observed during mixed IC/passive experiments",
            "notes": "Can come from visible refs, CDB package refs, or hidden object IDs.",
        },
        {
            "signature_id": "MOVED_BODY_STALE_TEXT",
            "message_patterns": ["component body moved but label/model/ref text remains at old coordinates"],
            "category": "coordinate_linkage_failure",
            "source": "Visual artifacts in prior IC experiments",
            "notes": "Move logic must update component body, component ID, value, subckt, properties, pins, and any terminal/label records together.",
        },
        {
            "signature_id": "ORPHAN_MODEL_TEXT",
            "message_patterns": ["orphaned model/reference/name text", "component visible but detached text remains"],
            "category": "partial_packet_deletion",
            "source": "Failed broad slicing experiments",
            "notes": "Deletion must remove all associated text/model/pin records, not only the body symbol.",
        },
        {
            "signature_id": "VISIBLE_BUT_NONFUNCTIONAL",
            "message_patterns": ["opens visually but simulation fails", "components visible but nonfunctional"],
            "category": "metadata_mismatch",
            "source": "User reports for native IC pair experiments",
            "notes": "Open/render is weaker than netlist validation.",
        },
        {
            "signature_id": "DONOR_DELETION_ORPHAN_RECORDS",
            "message_patterns": ["donor deletion leaving orphan records", "body-only record trimming"],
            "category": "unsafe_deletion",
            "source": "COMPONENT_PLACER_SEQ_16X_V1 failed pack",
            "notes": "The 140-case pack removed terminals/wires and kept full metadata, and user reported all cases failed.",
        },
        {
            "signature_id": "RESERVED_NET_MISUSE",
            "message_patterns": ["V0/G0/VCC/GND misuse", "reserved net used as arbitrary signal"],
            "category": "semantic_net_policy_failure",
            "source": "Earlier source/passive testing",
            "notes": "Less relevant for no-terminal component placer, but must return when terminal/wire stage is added.",
        },
    ]


def validator_rule_candidates() -> list[dict[str, object]]:
    return [
        {
            "rule_id": "V_COMPONENT_PACKET_COMPLETE",
            "stage": "deletion_plan_validator",
            "what_to_check": "Every kept/deleted component is represented by a complete packet, including body, ID/value/subckt/properties text, pin anchors, terminal records if required, wires if required, CDB rows, and device metadata.",
            "why_it_matters": "Partial packet deletion leaves orphan text or removes required model linkage.",
            "failure_category": "partial_packet_deletion",
            "how_to_reproduce": "Compare the failed 16x body-only pack against the 16x mega donor.",
            "supporting_files": ["FAILED_PACK_AUDIT.json", "REPRESENTATIVE_FAILURES/ALL_FAILED_CASES", "DONORS_FOR_REMOVAL_LEARNING"],
        },
        {
            "rule_id": "V_NO_ORPHAN_CDB_REFS",
            "stage": "final_validator",
            "what_to_check": "Every package ref in ROOT.CDB must have a corresponding DSN component packet, unless Camber proves the row is harmless donor metadata.",
            "why_it_matters": "CDB/DSN mismatch is a likely source of no-model/no-CDB errors.",
            "failure_category": "metadata_mismatch",
            "how_to_reproduce": "The failed pack copies full donor CDB while keeping only a subset of body packets.",
            "supporting_files": ["FAILED_PACK_AUDIT.json"],
        },
        {
            "rule_id": "V_NO_DUPLICATE_VISIBLE_OR_HIDDEN_REFS",
            "stage": "final_validator",
            "what_to_check": "Scan DSN and CDB for duplicate package refs, duplicate subpart refs, and duplicate hidden IDs.",
            "why_it_matters": "Proteus reports duplicate part reference and may crash or fail simulation.",
            "failure_category": "duplicate_ref_or_duplicate_hidden_id",
            "how_to_reproduce": "Use known duplicate-reference reports from knowledge/test_results.jsonl.",
            "supporting_files": ["KNOWN_FAILURE_SIGNATURES.json", "knowledge/test_results.jsonl summary in README"],
        },
        {
            "rule_id": "V_MOVE_ALL_LINKED_COORDS",
            "stage": "beautifier_validator",
            "what_to_check": "When an object is moved, body coordinates and all linked component ID/value/subckt/properties/pin/terminal coordinates move by the same delta.",
            "why_it_matters": "Bad movement leaves visible artifacts and nonfunctional pins/text.",
            "failure_category": "coordinate_linkage_failure",
            "how_to_reproduce": "Create manual before/after move donor requested in DONOR_REQUEST_LIST.md.",
            "supporting_files": ["COMPARISON_TASKS.json", "DONOR_REQUEST_LIST.md"],
        },
        {
            "rule_id": "V_REMOVAL_ONLY_QUANTITY_CHECK",
            "stage": "donor_selector_validator",
            "what_to_check": "Selected donor must already contain every requested family and quantity. No cloning is allowed in production.",
            "why_it_matters": "Cloning repeatedly produced Proteus crashes and metadata mismatch.",
            "failure_category": "donor_insufficient",
            "how_to_reproduce": "Request 23x for a family absent from the 16x donor, such as 4511 or 74HC151 if no high-count donor exists.",
            "supporting_files": ["DONOR_INVENTORY.json", "DONOR_REQUEST_LIST.md"],
        },
        {
            "rule_id": "V_NO_TERMINAL_WIRE_STAGE_LEAKAGE",
            "stage": "component_placer_validator",
            "what_to_check": "For the current component-placer-only phase, output must not add new terminal or wire records. If donor-native terminals are required for model linkage, the output must fail with a clear algorithm note rather than stripping them blindly.",
            "why_it_matters": "The failed pack stripped terminals/wires but may also have stripped required pin-anchor records.",
            "failure_category": "unsafe_terminal_wire_removal",
            "how_to_reproduce": "Open any failed body-only output from COMPONENT_PLACER_SEQ_16X_V1.",
            "supporting_files": ["FAILED_PACK_AUDIT.json"],
        },
    ]


def donor_request_list(inventory: list[dict[str, object]]) -> str:
    max_counts: dict[str, int] = {}
    for family in TARGET_FAMILIES:
        max_counts[family] = max(
            [int((row.get("package_counts") if isinstance(row.get("package_counts"), dict) else {}).get(family, 0)) for row in inventory]
            or [0]
        )
    lines = [
        "# Donor Request List",
        "",
        "Current rule: production component placement must be removal-only. If a donor does not already contain enough components, the generator must fail cleanly instead of cloning.",
        "",
        "## Quantity Gaps",
        "",
    ]
    for family in TARGET_FAMILIES:
        max_count = max_counts.get(family, 0)
        status = "OK for 23x removal-only" if max_count >= 23 else "NEEDS DONOR"
        lines.append(f"- {family}: max detected package count = {max_count}. {status}.")
    lines.extend(
        [
            "",
            "The current 16x mega donor can satisfy 23x only for families it contains at high count. It cannot satisfy 23x requests for missing families such as 4511 or 74HC151 unless another donor in the inventory has enough copies.",
            "",
            "## Exact Manual Donors Needed Next",
            "",
            "- 23x single-family donor for every target family that has max detected count below 23.",
            "- 15x and 23x clean no-terminal/no-wire variants for each target family, if Proteus can save them manually.",
            "- 3+ package pair donors for target-family pairs that do not coexist in a known working donor.",
            "- Before/after deletion donor: create 23x of one family, save, delete down to 15x, save, delete down to 5x, save, delete down to 3x, save, delete down to 1x, save.",
            "- Before/after move donor: create at least 5 ICs, move one IC, save as a new file.",
            "- Before/after rename donor: change visible ref/value on one IC and save as a new file.",
            "- Clean 4511 donor set if 4511 is intended for this phase.",
            "- Clean 74HC151 donor set if 74HC151 is intended for this phase.",
            "- Clean 74HC192 high-count donor if current donors do not contain at least 23 copies.",
            "- Screenshots are optional but helpful when visible artifacts appear.",
        ]
    )
    return "\n".join(lines) + "\n"


def readme_text(case_count: int, donor_count: int) -> str:
    return f"""# Camber Component Placer Analysis Handoff

This pack is for analysis only. It does not claim the failed component-placer output works.

## What Failed

The temporary pack `COMPONENT_PLACER_SEQ_16X_V1_TEMP_2026_06_15` generated 140 `.pdsprj` files from the 16x mega donor. User testing reported that all generated circuits failed. The pack used body-only IC packet selection, stripped terminals/wires, and copied the full donor CDB/device metadata.

## New Plan

Build only the component placer first. The production method must be removal-only donor mutation:

1. Choose an exact or closest donor that already contains the requested component quantities.
2. Delete extras.
3. Move/beautify only after deletion patterns are proven.
4. Do not clone components in production.
5. Do not synthesize IC records.
6. Do not add terminal/wire logic yet.
7. If no donor has enough parts, fail with a donor-insufficiency report.

## What Camber Should Analyze

Camber should inspect donor and failed files byte-by-byte and explain how to safely identify, delete, and move complete Proteus component packets without leaving orphan metadata.

## Included Data

- Donor inventory entries: {donor_count}
- Failed generated cases audited: {case_count}
- All failed `.pdsprj` files are copied under `REPRESENTATIVE_FAILURES/ALL_FAILED_CASES`.
- Selected learning donors are copied under `DONORS_FOR_REMOVAL_LEARNING`.

Start with `CAMBER_PROMPT.md`, then inspect `DONOR_INVENTORY.json`, `FAILED_PACK_AUDIT.json`, and `COMPARISON_TASKS.json`.
"""


def camber_prompt_text() -> str:
    questions = [
        "A. Why did the generated 140 component-placer cases fail?",
        "B. Which failure signatures are visible from the failed files?",
        "C. Which donor files are most useful for learning removal-only component placement?",
        "D. Can the 16x donor satisfy 23x requests without cloning? If not, state that clearly.",
        "E. What exact file patterns identify a component record, reference text, model/name field, coordinate field, and linked metadata?",
        "F. How can we delete extra components without leaving orphan model/reference/name fields?",
        "G. How can we detect \"No model specified for ...\" before output?",
        "H. How can we detect \"Duplicate part reference at ...\" before output?",
        "I. How can we detect that a component moved but its model/name/reference text did not move?",
        "J. What validator rules must exist before component placer output is trusted?",
        "K. What extra donor circuits should we create next to learn safe removal?",
        "L. What should the removal-only component placer algorithm be?",
        "M. What outputs should Codex implement first?",
    ]
    return """# Prompt For Camber

You are analyzing a Proteus 8.13 `.pdsprj` generator project. The current goal is not full circuit generation. The goal is to discover a safe removal-only component placer.

The previous generated pack failed. Do not assume it is valid. Analyze the included donor and failed project files at byte level.

## Core Rule

Production component placement must be removal-only donor mutation:

- Use a donor that already contains the requested components and quantities.
- Delete extras.
- Move/beautify only after complete packet boundaries are known.
- Do not clone components.
- Do not synthesize new IC records.
- Do not add terminal or wire logic in this phase.
- If no donor contains enough requested components, return donor insufficiency.

## Required Questions

""" + "\n".join(f"- {item}" for item in questions) + """

## Required Concrete JSON Outputs

Do not return vague advice. Produce exact files matching `CAMBER_EXPECTED_OUTPUT_SCHEMA.md`:

- `component_fingerprints.json`
- `donor_inventory_verified.json`
- `deletion_patterns.json`
- `move_patterns.json`
- `reference_text_linkage_patterns.json`
- `model_field_patterns.json`
- `failure_signatures.json`
- `validator_rules.json`
- `donor_selector_rules.json`
- `required_new_donors.md`
- `recommended_component_placer_algorithm.md`

## Specific Analysis Instructions

1. Compare failed generated files in `REPRESENTATIVE_FAILURES/ALL_FAILED_CASES` against the 16x mega donor in `DONORS_FOR_REMOVAL_LEARNING`.
2. Identify whether body-only output removed required pin/model/association records.
3. Identify CDB/device metadata relationships that must be kept or pruned during deletion.
4. Define exact signatures for no-model, duplicate-ref, stale-coordinate, and orphan-record failures.
5. Define a donor selector that rejects requests needing cloning.
6. State exactly which new manual donors are required next.
"""


def expected_schema_text() -> str:
    return """# Camber Expected Output Schema

Camber should return these files:

## component_fingerprints.json

Map each component family to markers, package/subpart structure, required DSN records, required CDB rows, required device-section entries, coordinate fields, and known safe donors.

## donor_inventory_verified.json

Verify or correct `DONOR_INVENTORY.json`. Include donor path, supported families, quantities, terminal/wire presence, and removal-only suitability.

## deletion_patterns.json

For each before/after deletion comparison, list exact record classes removed, records preserved, CDB/device changes, and unsafe orphan risks.

## move_patterns.json

For each move comparison, list coordinate fields that move together and coordinate fields that must not move.

## reference_text_linkage_patterns.json

Explain how visible reference text, package ref, model/property text, and CDB rows are linked.

## model_field_patterns.json

Explain MODFILE/PACKAGE/ITFMOD/VOLTAGE/INIT fields and how to validate model availability.

## failure_signatures.json

Machine-readable signatures for no-model, duplicate-ref, stale-text, orphan CDB, orphan DSN, and missing device metadata.

## validator_rules.json

Rules with id, stage, check, severity, reproduction file, and implementation hint.

## donor_selector_rules.json

Exact rules for selecting exact, closest, family, template, and mega donors under removal-only constraints.

## required_new_donors.md

Human-readable donor request list with exact component counts and shapes.

## recommended_component_placer_algorithm.md

Step-by-step algorithm for Codex to implement first, including what not to implement yet.
"""


def write_archive() -> str:
    if ARCHIVE.exists():
        raise FileExistsError(f"Archive already exists: {ARCHIVE}")
    source = OUT_ROOT if OUT_ROOT.exists() else STAGING
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(source.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(source.parent).as_posix())
            info.date_time = (2026, 6, 15, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            zf.writestr(info, file_path.read_bytes())
    return sha256_file(ARCHIVE)


def write_file_index(included: list[IncludedFile]) -> None:
    rows = [item.__dict__ for item in included]
    index_path = STAGING / "FILE_INDEX.json"
    index_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    log("write_file_index", count=len(rows))


def main() -> int:
    if OUT_ROOT.exists():
        raise FileExistsError(f"Requested handoff folder already exists: {OUT_ROOT}")
    if STAGING.exists():
        raise FileExistsError(f"Staging folder already exists: {STAGING}")
    if ARCHIVE.exists():
        raise FileExistsError(f"Requested handoff archive already exists: {ARCHIVE}")
    STAGING.mkdir(parents=True)
    log("start", repo=str(REPO))

    missing = [str(path) for path in (FAILED_PACK, FAILED_ARCHIVE, MEGA_DONOR_COPY, SOURCE_PLAN) if not path.exists()]
    if missing:
        raise FileNotFoundError("Required handoff inputs missing: " + "; ".join(missing))

    included: list[IncludedFile] = []
    inventory = scan_projects()
    failed_audit = audit_failed_pack()
    learning_donors = select_learning_donors(inventory)
    comparison_tasks = build_comparison_tasks(inventory, failed_audit)

    included.append(write_text("README.md", readme_text(len(failed_audit), len(inventory)), "documentation", "Handoff overview."))
    included.append(write_text("CAMBER_PROMPT.md", camber_prompt_text(), "documentation", "Prompt for Camber analysis."))
    included.append(write_json("DONOR_INVENTORY.json", inventory, "analysis_json", "Inventory of relevant repo donors and outputs."))
    included.append(write_json("FAILED_PACK_AUDIT.json", failed_audit, "analysis_json", "Audit of the rejected 140-case generated pack."))
    included.append(write_json("COMPARISON_TASKS.json", comparison_tasks, "analysis_json", "Before/after analysis tasks for Camber."))
    included.append(write_json("KNOWN_FAILURE_SIGNATURES.json", known_failure_signatures(), "analysis_json", "Known Proteus failure signatures from project history."))
    included.append(write_json("VALIDATOR_RULE_CANDIDATES.json", validator_rule_candidates(), "analysis_json", "Candidate validator rules derived from failures."))
    included.append(write_text("DONOR_REQUEST_LIST.md", donor_request_list(inventory), "documentation", "Manual donors needed for next safe step."))
    included.append(write_text("CAMBER_EXPECTED_OUTPUT_SCHEMA.md", expected_schema_text(), "documentation", "Expected output schema for Camber."))
    included.append(copy_included(SOURCE_PLAN, "SOURCE_REQUEST.txt", "source_instruction", "Original user instruction for this handoff pack."))
    included.append(copy_included(FAILED_ARCHIVE, "FAILED_PACK_ORIGINAL_ARCHIVE/COMPONENT_PLACER_SEQ_16X_V1_TEMP_2026_06_15.zip", "failed_generated_archive", "Original rejected generated pack archive."))

    copy_failed_cases(failed_audit, included)
    copy_learning_donors(learning_donors, included)

    write_file_index(included)

    # Rename only after all required files are present.
    STAGING.rename(OUT_ROOT)
    archive_hash = write_archive()
    summary = {
        "folder": str(OUT_ROOT),
        "archive": str(ARCHIVE),
        "archive_sha256": archive_hash,
        "included_file_count": len(list(OUT_ROOT.rglob("*"))),
        "donor_inventory_count": len(inventory),
        "failed_audit_count": len(failed_audit),
        "learning_donor_count": len(learning_donors),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
