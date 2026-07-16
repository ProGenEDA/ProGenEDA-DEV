"""Generate R/C/L terminal-boundary diagnostics after V5 user feedback.

V5 proved the supplied manual RLC donor is valid and can be inserted into E001,
but every generated terminal-topology case failed. V6 isolates whether the
failure is caused by:

- one specific terminal-attached family record,
- pairwise terminal-attached coexistence,
- shared node labels between families, or
- using the wrong DSN device/header section for generated R/C/L terminals.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_passive as mp
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v6_terminal_boundary_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V3_PATH = Path(__file__).with_name("generate_mixed_rcl_v3_isolation_temp.py")
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")

BASE_X = -7366000
BASE_Y = 5080000
SAFE_X_STEP = 3810000


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {name} from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "WIRE",
        "RESISTOR",
        "CAPACITOR",
        "CAP10",
        "REALIND",
        "COMPONENT ID",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _zero_last(record: bytes) -> bytes:
    return record[:-1] + b"\x00" if record else record


def _free_slices(rlc_chunk: bytes) -> dict[str, bytes]:
    # Observed manual donor free component starts:
    # header 0:1, L1 1:375, R1 375:722, C1 722:end.
    return {
        "header": rlc_chunk[:1],
        "L": rlc_chunk[1:375],
        "R": rlc_chunk[375:722],
        "C": rlc_chunk[722:],
    }


def _specs(v2: Any, *, connected: bool) -> list[Any]:
    if connected:
        nodes = {
            "L": ("N1", "N2"),
            "R": ("N2", "N3"),
            "C": ("N3", "N4"),
        }
    else:
        nodes = {
            "L": ("L1", "L2"),
            "R": ("R1", "R2"),
            "C": ("C1", "C2"),
        }
    return [
        v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", nodes["L"][0], nodes["L"][1], BASE_X, BASE_Y, {}),
        v2.RclSpec(2, "R1", "R1", "RESISTOR", "10k", "10k", nodes["R"][0], nodes["R"][1], BASE_X + SAFE_X_STEP, BASE_Y, {}),
        v2.RclSpec(3, "C1", "C1", "CAPACITOR", "1nF", "1nF", nodes["C"][0], nodes["C"][1], BASE_X + 2 * SAFE_X_STEP, BASE_Y, {}),
    ]


def _records_for(v3: Any, v8: Any, specs: list[Any], *, cap_templates: Any, res_templates: Any, ind_templates: Any) -> dict[str, Any]:
    return v3._records(
        specs,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
        v8=v8,
    )


def _res_block(v3: Any, records: dict[str, Any], res_templates: Any, *, final: bool) -> bytes:
    block = v3._res_block(records, res_templates)
    return block if final else _zero_last(block)


def _cap_block(records: dict[str, Any], *, final: bool) -> bytes:
    if not records["cap_outputs"]:
        return b""
    parts = list(records["cap_groups"])
    if final:
        if len(parts[-1]) != mp.TRIMMED_WIRE_SIZE:
            raise RuntimeError("Expected trimmed capacitor right-wire record before finalizing.")
        parts[-1] = parts[-1] + b"\xff"
    return b"".join(records["cap_outputs"]) + b"".join(parts)


def _ind_block(v3: Any, records: dict[str, Any], *, final: bool) -> bytes:
    return v3._ind_seq_block(records, final=final)


def _terminal_blocks(v3: Any, records: dict[str, Any], res_templates: Any) -> dict[str, bytes]:
    return {
        "L_nonfinal": _ind_block(v3, records, final=False),
        "L_final": _ind_block(v3, records, final=True),
        "R_nonfinal": _res_block(v3, records, res_templates, final=False),
        "R_final": _res_block(v3, records, res_templates, final=True),
        "C_nonfinal": _cap_block(records, final=False),
        "C_final": _cap_block(records, final=True),
    }


def _build_chunk(header: bytes, parts: list[bytes]) -> bytes:
    chunk = bytearray(header + b"".join(parts))
    if not chunk or chunk[0] != 0:
        raise RuntimeError("Chunk does not start with 00.")
    chunk[-1] = 0xFF
    return bytes(chunk)


def _validate(chunk: bytes, expected: dict[str, int]) -> list[str]:
    issues: list[str] = []
    counts = _marker_counts(chunk)
    for marker, want in expected.items():
        if counts[marker] != want:
            issues.append(f"{marker} count {counts[marker]} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    return issues


def _payload(case_id: str, description: str, connected: bool, terminal_families: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v6-terminal-boundary",
        "generator_target": "proteus-8.13-mixed-rcl-terminal-boundary-diagnostic",
        "case_id": case_id,
        "description": description,
        "connected_terminal_nodes": connected,
        "terminal_attached_families": terminal_families,
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_header_project: Path,
    object_chunk: bytes,
    cdb: bytes,
    connected: bool,
    terminal_families: list[str],
    issues: list[str],
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_header_project, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues = [*issues, "ROOT.DSN object chunk differs from requested chunk"]
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v6_terminal_boundary_not_locked",
        "description": description,
        "donor_header_project": str(donor_header_project),
        "connected_terminal_nodes": connected,
        "terminal_attached_families": terminal_families,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            chunk_path.name: rv9._sha256_file(chunk_path),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
            "object_chunk": rv9._sha256_bytes(object_chunk),
        },
    }
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, description, connected, terminal_families), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _expected_counts(*, terminal_families: set[str], free_families: set[str]) -> dict[str, int]:
    terminal_count = len(terminal_families)
    return {
        "$TERPOWER": 0,
        "$TERINPUT": terminal_count,
        "$TEROUTPUT": terminal_count,
        "$TERGROUND": 0,
        "WIRE": terminal_count * 2,
        "RESISTOR": (2 if "R" in terminal_families else 0) + (2 if "R" in free_families else 0),
        "CAPACITOR": (1 if "C" in terminal_families else 0) + (1 if "C" in free_families else 0),
        "CAP10": (1 if "C" in terminal_families else 0) + (1 if "C" in free_families else 0),
        "REALIND": (3 if "L" in terminal_families else 0) + (3 if "L" in free_families else 0),
        "COMPONENT ID": terminal_count + len(free_families),
    }


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_temp_for_v6", V2_PATH)
    v3 = _load_module("mixed_rcl_v3_temp_for_v6", V3_PATH)
    v8 = _load_module("inductor_v8_temp_for_v6", V8_PATH)

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")

    base = registry.get("e001_empty").path
    resistor_donor = registry.get("r21_v9_resistor_terminal_donor").path
    cap_donor = registry.get("cap2_with_terminals_manual").path
    inductor_donor = registry.get("inductor_05_six_terminal").path
    rlc_donor = registry.get("rlc_manual_donor").path
    rlc_cdb = read_internal_file(rlc_donor, "ROOT.CDB")
    rlc_chunk = rv9._extract_object_chunk(read_internal_file(rlc_donor, "ROOT.DSN"))
    free = _free_slices(rlc_chunk)

    cap_templates = mp._load_manual_cap_templates(cap_donor)
    resistor_dsn = read_internal_file(resistor_donor, "ROOT.DSN")
    res_templates = rv9._load_templates(resistor_dsn, resistor_donor)
    ind_templates = v8._load_six_templates(inductor_donor)

    specs_disconnected = _specs(v2, connected=False)
    records_disconnected = _records_for(
        v3,
        v8,
        specs_disconnected,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
    )
    blocks_disconnected = _terminal_blocks(v3, records_disconnected, res_templates)

    specs_connected = _specs(v2, connected=True)
    records_connected = _records_for(
        v3,
        v8,
        specs_connected,
        cap_templates=cap_templates,
        res_templates=res_templates,
        ind_templates=ind_templates,
    )
    blocks_connected = _terminal_blocks(v3, records_connected, res_templates)

    cases: list[dict[str, Any]] = []

    def add_case(
        case_id: str,
        description: str,
        parts: list[bytes],
        *,
        terminal_families: set[str],
        free_families: set[str],
        connected: bool = False,
        donor_header_project: Path | None = None,
    ) -> None:
        chunk = _build_chunk(free["header"], parts)
        issues = _validate(chunk, _expected_counts(terminal_families=terminal_families, free_families=free_families))
        cases.append(
            _write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_header_project=donor_header_project or resistor_donor,
                object_chunk=chunk,
                cdb=rlc_cdb,
                connected=connected,
                terminal_families=sorted(terminal_families),
                issues=issues,
            )
        )

    # T01 checks whether an extra standalone powerless terminal family is required
    # before the exact free donor can coexist with generated terminal records.
    add_case(
        "RCL_V6_T01_FREE_LRC_REBUILT_FROM_SLICES",
        "Rebuild the worked manual donor free L/R/C chunk from explicit L/R/C slices.",
        [free["L"], free["R"], free["C"]],
        terminal_families=set(),
        free_families={"L", "R", "C"},
        donor_header_project=rlc_donor,
    )

    add_case(
        "RCL_V6_T02_TERM_L_FREE_R_C",
        "Only L1 is terminal-attached; R1 and C1 are exact free donor records. Disconnected labels.",
        [blocks_disconnected["L_nonfinal"], free["R"], free["C"]],
        terminal_families={"L"},
        free_families={"R", "C"},
    )
    add_case(
        "RCL_V6_T03_FREE_L_TERM_R_FREE_C",
        "Only R1 is terminal-attached; L1 and C1 are exact free donor records. Disconnected labels.",
        [free["L"], blocks_disconnected["R_nonfinal"], free["C"]],
        terminal_families={"R"},
        free_families={"L", "C"},
    )
    add_case(
        "RCL_V6_T04_FREE_L_R_TERM_C",
        "Only C1 is terminal-attached; L1 and R1 are exact free donor records. Disconnected labels.",
        [blocks_disconnected["C_nonfinal"], free["L"], free["R"]],
        terminal_families={"C"},
        free_families={"L", "R"},
    )
    add_case(
        "RCL_V6_T05_TERM_C_L_FREE_R",
        "C1 and L1 are terminal-attached with disconnected labels; R1 is exact free donor record.",
        [blocks_disconnected["C_nonfinal"], blocks_disconnected["L_nonfinal"], free["R"]],
        terminal_families={"C", "L"},
        free_families={"R"},
    )
    add_case(
        "RCL_V6_T06_TERM_R_C_FREE_L",
        "R1 and C1 are terminal-attached with disconnected labels; L1 is exact free donor record.",
        [blocks_disconnected["C_nonfinal"], blocks_disconnected["R_nonfinal"], free["L"]],
        terminal_families={"R", "C"},
        free_families={"L"},
    )
    add_case(
        "RCL_V6_T07_TERM_R_L_FREE_C",
        "R1 and L1 are terminal-attached with disconnected labels; C1 is exact free donor record.",
        [blocks_disconnected["L_nonfinal"], blocks_disconnected["R_nonfinal"], free["C"]],
        terminal_families={"R", "L"},
        free_families={"C"},
    )
    add_case(
        "RCL_V6_T08_ALL_TERM_DISCONNECTED_RES_HEADER",
        "All three families are terminal-attached, but labels are disconnected. Uses the resistor terminal donor header.",
        [blocks_disconnected["L_nonfinal"], blocks_disconnected["C_nonfinal"], blocks_disconnected["R_final"]],
        terminal_families={"L", "R", "C"},
        free_families=set(),
    )
    add_case(
        "RCL_V6_T09_ALL_TERM_CONNECTED_RES_HEADER",
        "All three families are terminal-attached in L/R/C order with shared series node labels. Uses the resistor terminal donor header.",
        [blocks_connected["L_nonfinal"], blocks_connected["C_nonfinal"], blocks_connected["R_final"]],
        terminal_families={"L", "R", "C"},
        free_families=set(),
        connected=True,
    )
    add_case(
        "RCL_V6_T10_CONNECTED_C_L_FREE_R",
        "Known-good C+L terminal topology with shared node labels, plus exact free R1 donor record.",
        [blocks_connected["C_nonfinal"], blocks_connected["L_nonfinal"], free["R"]],
        terminal_families={"C", "L"},
        free_families={"R"},
        connected=True,
    )
    add_case(
        "RCL_V6_T11_CONNECTED_R_C_FREE_L",
        "R+C terminal topology with shared node labels, plus exact free L1 donor record.",
        [blocks_connected["C_nonfinal"], blocks_connected["R_nonfinal"], free["L"]],
        terminal_families={"R", "C"},
        free_families={"L"},
        connected=True,
    )
    add_case(
        "RCL_V6_T12_CONNECTED_R_L_FREE_C",
        "R+L terminal topology with shared node labels, plus exact free C1 donor record.",
        [blocks_connected["L_nonfinal"], blocks_connected["R_nonfinal"], free["C"]],
        terminal_families={"R", "L"},
        free_families={"C"},
        connected=True,
    )
    add_case(
        "RCL_V6_T13_ALL_TERM_DISCONNECTED_RLC_HEADER",
        "Same object chunk as T08, but inserted using the manual RLC donor DSN header.",
        [blocks_disconnected["L_nonfinal"], blocks_disconnected["C_nonfinal"], blocks_disconnected["R_final"]],
        terminal_families={"L", "R", "C"},
        free_families=set(),
        donor_header_project=rlc_donor,
    )
    add_case(
        "RCL_V6_T14_ALL_TERM_CONNECTED_RLC_HEADER",
        "Same object chunk as T09, but inserted using the manual RLC donor DSN header.",
        [blocks_connected["L_nonfinal"], blocks_connected["C_nonfinal"], blocks_connected["R_final"]],
        terminal_families={"L", "R", "C"},
        free_families=set(),
        connected=True,
        donor_header_project=rlc_donor,
    )

    summary = {
        "batch_id": "MIXED_RCL_V6_TERMINAL_BOUNDARY_STATIC_20260601",
        "status": "static_generated_awaiting_user_proteus_test",
        "source_feedback": "V5 T01-T04 worked; V5 T05-T10 failed.",
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "terminal_attached_families": item["terminal_attached_families"],
                "connected_terminal_nodes": item["connected_terminal_nodes"],
                "donor_header_project": item["donor_header_project"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "MIXED_RCL_V6_TERMINAL_BOUNDARY_TEMP_2026_06_01\n\n"
        "Test in order:\n"
        "1. T01 first; it should behave like the worked donor controls.\n"
        "2. T02-T04: one terminal-attached family at a time with the other two as exact free donor records.\n"
        "3. T05-T07: two terminal-attached families with the third as exact free donor record.\n"
        "4. T08-T09: all terminal-attached with disconnected vs connected labels, resistor header.\n"
        "5. T13-T14 only if T08/T09 fail; they repeat all-terminal cases with the RLC donor header.\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(OUT_ROOT).replace("mixed_rcl_v6_terminal_boundary_temp_2026_06_01", "MIXED_RCL_V6_TERMINAL_BOUNDARY_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
