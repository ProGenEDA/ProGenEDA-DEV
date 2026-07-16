from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "proteus" / "active" / "src"))

from proteusgen.bidirectional import extract_bidir_records  # noqa: E402
from proteusgen.component_beautifier import MIXED_LAYOUT_BAND_GAP_Y  # noqa: E402
from proteusgen.component_placer import generate_component_placement_project  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_component_bidir_terminals_to_project,
    attach_mixed_native_bidir_terminals_to_project,
)
from proteusgen.pdsprj import inspect_pdsprj, read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


EXPERIMENT_NAME = "terminal_placer_native_wire_v7_temp_2026_07_01"
ARCHIVE_NAME = "TERMINAL_PLACER_NATIVE_WIRE_V7_TEMP_2026_07_01.zip"
DONOR_ID = "component_placer_main_15x_semimega_sources_20260618"
FAMILIES = (
    "RESISTOR",
    "CAP",
    "CAP-ELEC",
    "REALIND",
    "VSOURCE",
    "CSOURCE",
)
CONTROLS = ("DIODE", "NPN", "74HC08")


def _mixed_components(count: int) -> dict[str, int]:
    return {
        **{family: count for family in FAMILIES},
        **{family: 1 for family in CONTROLS},
    }


CASES: tuple[dict[str, Any], ...] = (
    *(
        {
            "case_id": f"N{index:02d}_{family.replace('-', '_')}_3X_NATIVE_ORACLE",
            "components": {family: 3},
            "terminal_families": (family,),
            "compare_accepted_oracle": True,
        }
        for index, family in enumerate(FAMILIES, start=1)
    ),
    {
        "case_id": "N07_MIXED_ALL_1X_WITH_CONTROLS",
        "components": _mixed_components(1),
        "terminal_families": FAMILIES,
    },
    {
        "case_id": "N08_MIXED_ALL_3X_WITH_CONTROLS",
        "components": _mixed_components(3),
        "terminal_families": FAMILIES,
    },
    {
        "case_id": "N09_MIXED_ALL_15X_WITH_CONTROLS",
        "components": _mixed_components(15),
        "terminal_families": FAMILIES,
    },
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_deterministic_archive(experiment: Path, archive: Path) -> None:
    if archive.exists():
        archive.unlink()
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as output:
        for file_path in sorted(experiment.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(
                file_path.relative_to(experiment.parent).as_posix(),
                date_time=(2026, 7, 1, 0, 0, 0),
            )
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            info.external_attr = 0
            output.writestr(info, file_path.read_bytes())


def _payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": "progen-terminal-native-wire-test/v0.7",
        "name": case["case_id"],
        "donor": DONOR_ID,
        "components": case["components"],
        "layout": {
            "strategy": "beautify",
            "direction": "left_to_right",
            "mixed_ic_non_ic_bands": "separate",
        },
        "routing": {
            "mode": "terminal",
            "method": "accepted_native_active_link_component_adjacent_short_wire",
            "terminal_families": list(case["terminal_families"]),
            "patch_component_links": True,
            "active_terminal_links": True,
            "include_wires": True,
        },
    }


def _terminal_pairs(report: dict[str, Any]) -> list[dict[str, Any]]:
    if "family_reports" in report:
        return [
            pair
            for family_report in report["family_reports"]
            for pair in family_report["terminal_pairs"]
        ]
    return list(report["terminal_pairs"])


def _expected_wire_coordinates(
    pairs: list[dict[str, Any]],
) -> list[tuple[int, int, int, int]]:
    return sorted(
        (
            wire["start"]["x"],
            wire["start"]["y"],
            wire["end"]["x"],
            wire["end"]["y"],
        )
        for pair in pairs
        for wire in pair["short_wires"].values()
    )


def _actual_wire_coordinates(chunk: bytes) -> list[tuple[int, int, int, int]]:
    coordinates: list[tuple[int, int, int, int]] = []
    search_from = 0
    while True:
        marker = chunk.find(b"\x7fWIRE", search_from)
        if marker < 0:
            break
        wire_start = marker - 23
        coordinates.append(
            tuple(
                int.from_bytes(
                    chunk[wire_start + offset : wire_start + offset + 4],
                    "little",
                    signed=True,
                )
                for offset in (33, 37, 41, 45)
            )
        )
        search_from = marker + len(b"\x7fWIRE")
    return sorted(coordinates)


def _layout_band_valid(placement: Any, *, mixed: bool) -> bool:
    if not mixed:
        return True
    entries = placement.layout_plan["actual_binary_placements"]
    ic_entries = [entry for entry in entries if entry.get("layout_band") == "ic"]
    non_ic_entries = [
        entry for entry in entries if entry.get("layout_band") == "non_ic"
    ]
    if not ic_entries or not non_ic_entries:
        return False
    ic_max_y = max(int(entry["after_bbox"]["max_y"]) for entry in ic_entries)
    non_ic_min_y = min(
        int(entry["after_bbox"]["min_y"]) for entry in non_ic_entries
    )
    return non_ic_min_y - ic_max_y >= MIXED_LAYOUT_BAND_GAP_Y


def _validate_case(
    case: dict[str, Any],
    base: Path,
    output: Path,
    placement: Any,
    report: dict[str, Any],
    *,
    oracle: Path | None,
) -> dict[str, Any]:
    base_chunk = _extract_object_chunk(read_internal_file(base, "ROOT.DSN"))
    chunk = _extract_object_chunk(read_internal_file(output, "ROOT.DSN"))
    terminals = extract_bidir_records(chunk)
    pairs = _terminal_pairs(report)
    expected_components = Counter(case["components"])
    actual_components = Counter(group.family for group in placement.selected_groups)
    expected_terminal_count = (
        sum(case["components"][family] for family in case["terminal_families"]) * 2
    )
    expected_wires = _expected_wire_coordinates(pairs)
    actual_wires = _actual_wire_coordinates(chunk)
    suffixes = [
        int.from_bytes(record[-4:-2], "little")
        for record in terminals
    ]
    info = inspect_pdsprj(output)
    mixed = bool(set(case["components"]) & set(CONTROLS))
    oracle_match = None
    if oracle is not None:
        oracle_chunk = _extract_object_chunk(read_internal_file(oracle, "ROOT.DSN"))
        oracle_match = chunk == oracle_chunk

    errors: list[str] = []
    if not placement.valid:
        errors.append("component placement failed")
    if actual_components != expected_components:
        errors.append("selected component counts differ from the request")
    if not _layout_band_valid(placement, mixed=mixed):
        errors.append("IC/non-IC layout bands overlap")
    if base_chunk.count(b"$TERBIDIR") or base_chunk.count(b"\x7fWIRE"):
        errors.append("base project is not terminal/wire free")
    if not report["valid"]:
        errors.append("terminal placer report failed")
    if len(terminals) != expected_terminal_count:
        errors.append("terminal count differs")
    if chunk.count(b"\x7fWIRE") != expected_terminal_count:
        errors.append("wire count differs")
    if any(suffix == 0 for suffix in suffixes):
        errors.append("a terminal suffix is inactive")
    if any(record[-2:] != b"\x01\x00" for record in terminals):
        errors.append("a terminal active-link tail is invalid")
    if len(suffixes) != len(set(suffixes)):
        errors.append("terminal suffixes collide")
    if any(chunk.count(suffix.to_bytes(2, "little") + b"\x01\x00") != 2 for suffix in suffixes):
        errors.append("a terminal suffix does not have terminal+component link copies")
    if actual_wires != expected_wires:
        errors.append("native wire coordinates differ from the terminal plan")
    if oracle_match is False:
        errors.append("native output differs from accepted single-family writer")
    if mixed and report.get("family_handler") != "MIXED/native-wire-v7-temp":
        errors.append("mixed case did not use the V7 native serializer")
    if mixed and not report.get("wire_path_contacts_valid"):
        errors.append("a terminal-to-wire-to-pin path is incomplete")
    if mixed and {
        row["component_family"] for row in report["preserved_groups"]
    } != set(CONTROLS):
        errors.append("unsupported control preservation set differs")
    if mixed and not all(row["byte_preserved"] for row in report["preserved_groups"]):
        errors.append("an unsupported control packet changed")
    if not all(
        (info.has_project_xml, info.has_root_dsn, info.has_root_cdb, info.has_pwrails)
    ):
        errors.append("required project files are missing")

    return {
        "valid": not errors,
        "errors": errors,
        "component_count": len(placement.selected_groups),
        "terminal_count": len(terminals),
        "wire_count": chunk.count(b"\x7fWIRE"),
        "all_terminals_active": all(
            suffix != 0 and record[-2:] == b"\x01\x00"
            for suffix, record in zip(suffixes, terminals, strict=True)
        ),
        "suffixes_unique": len(suffixes) == len(set(suffixes)),
        "terminal_component_link_pairs_valid": all(
            chunk.count(suffix.to_bytes(2, "little") + b"\x01\x00") == 2
            for suffix in suffixes
        ),
        "actual_wires_match_plan": actual_wires == expected_wires,
        "accepted_single_family_oracle_match": oracle_match,
        "layout_bands_valid": _layout_band_valid(placement, mixed=mixed),
        "base_sha256": _sha256(base),
        "output_sha256": _sha256(output),
        "object_chunk_sha256": hashlib.sha256(chunk).hexdigest(),
    }


def _readme() -> str:
    return """# Native component-adjacent wire V7 test pack

V6 was rejected because it appended inactive terminals and standalone wire
geometry after the component stream. V7 uses the complete Proteus-native unit:

`active terminal -> matching component pin-link suffix -> component-adjacent WIRE`

Every 3x solo native output is byte-identical to the corresponding previously
accepted single-family writer. The mixed cases use the same records in original
component order. DIODE, NPN, and 74HC08 are controls: they remain terminal-free
and byte-preserved.

## Test order

1. `N01` through `N06`: three of each researched family, plus an
   `_ACCEPTED_ORACLE.pdsprj` with an identical object chunk.
2. `N07_MIXED_ALL_1X_WITH_CONTROLS`
3. `N08_MIXED_ALL_3X_WITH_CONTROLS`
4. `N09_MIXED_ALL_15X_WITH_CONTROLS`

For each file check: no Bad Object Record, all components and terminals render,
each terminal is joined to its component pin by a wire, labels/orientations are
correct, Ctrl+S does not delete the wires, and a simple simulation recognizes
the connections.
"""


def main() -> None:
    experiment = ROOT / "proteus" / "experiments" / "runs" / EXPERIMENT_NAME
    archive = ROOT / "proteus" / "experiments" / "runs" / ARCHIVE_NAME
    if experiment.exists():
        resolved = experiment.resolve()
        experiments_root = (ROOT / "proteus" / "experiments" / "runs").resolve()
        if experiments_root not in resolved.parents:
            raise RuntimeError(f"Refusing to remove unexpected path: {resolved}")
        shutil.rmtree(resolved)
    experiment.mkdir(parents=True)

    summaries: list[dict[str, Any]] = []
    for case in CASES:
        case_id = case["case_id"]
        case_dir = experiment / case_id
        case_dir.mkdir()
        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        payload = _payload(case)
        (case_dir / "input.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        placement = generate_component_placement_project(
            payload,
            base,
            full_cdb=True,
        )
        if not placement.valid:
            raise RuntimeError(f"{case_id} placement failed.")

        oracle: Path | None = None
        if case.get("compare_accepted_oracle"):
            oracle = case_dir / f"{case_id}_ACCEPTED_ORACLE.pdsprj"
            oracle_report = attach_component_bidir_terminals_to_project(
                base,
                oracle,
                placement.selected_groups,
            )
            if not oracle_report["valid"]:
                raise RuntimeError(f"{case_id} accepted oracle failed.")
            report = attach_mixed_native_bidir_terminals_to_project(
                base,
                output,
                placement.selected_groups,
                terminal_families=case["terminal_families"],
            )
        else:
            report = attach_component_bidir_terminals_to_project(
                base,
                output,
                placement.selected_groups,
                terminal_families=case["terminal_families"],
            )

        validation = _validate_case(
            case,
            base,
            output,
            placement,
            report,
            oracle=oracle,
        )
        if not validation["valid"]:
            raise RuntimeError(f"{case_id} failed: {validation['errors']}")
        (case_dir / "terminal_plan.json").write_text(
            json.dumps(report, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "validation.json").write_text(
            json.dumps(validation, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "TEST.txt").write_text(
            f"Case: {case_id}\n"
            f"Components: {validation['component_count']}\n"
            f"Terminals: {validation['terminal_count']}\n"
            f"Wires: {validation['wire_count']}\n"
            "Method: active terminal + matching component link + adjacent native WIRE\n"
            "Check Bad Object Record, render, attachment, Ctrl+S persistence, and simulation.\n",
            encoding="utf-8",
        )
        summaries.append({"case": case_id, **validation})

    summary = {
        "schema": "terminal-placer-native-wire-summary/v0.7",
        "experiment": EXPERIMENT_NAME,
        "status": "static_valid_pending_proteus",
        "attachment_method": (
            "active_terminal_matching_component_link_component_adjacent_native_wire"
        ),
        "researched_families": list(FAMILIES),
        "case_count": len(summaries),
        "all_static_valid": all(case["valid"] for case in summaries),
        "all_solo_oracles_exact": all(
            case["accepted_single_family_oracle_match"] is not False
            for case in summaries
        ),
        "cases": summaries,
    }
    (experiment / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    (experiment / "README.md").write_text(_readme(), encoding="utf-8")
    _write_deterministic_archive(experiment, archive)
    print(json.dumps(summary, indent=2))
    print(archive)


if __name__ == "__main__":
    main()
