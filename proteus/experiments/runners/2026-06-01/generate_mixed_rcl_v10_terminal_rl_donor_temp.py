"""Generate R/L diagnostics from manual terminal resistor+inductor donors.

V9 proved that composing independent resistor and inductor terminal records is
not enough. This pack uses the user-supplied R+L donor as the source of truth
for object ordering:

    header, all inputs, L output+REALIND+wires, R output+RESISTOR+wires

Keep this temporary until Proteus accepts the generated cases.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v10_terminal_rl_donor_temp_2026_06_01"
V2_PATH = Path(__file__).with_name("generate_mixed_rcl_v2_v8_temp.py")
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")

IN_SIZE = 103
OUT_SIZE = 104
IND_SIZE = 374
RES_SIZE = 346
WIRE_SIZE = 50
L_RIGHT_WIRE_TRIMMED_SIZE = 49
POWER_BRIDGE_CORE_SIZE = rv9.POWER_BRIDGE_CORE_SIZE

DONOR_L_X = -9398000
DONOR_L_Y = 3556000
DONOR_R_X = -9652000
DONOR_R_Y = 2032000
TRANSLATED_L_X = -7366000
TRANSLATED_L_Y = 5080000
TRANSLATED_R_X = -3556000
TRANSLATED_R_Y = 5080000


@dataclass(frozen=True)
class RlNativeTemplates:
    donor_chunk: bytes
    header: bytes
    l_input: bytes
    r_input: bytes
    l_output: bytes
    r_output: bytes
    l_inductor: bytes
    r_resistor: bytes
    r_resistor_prefix: bytes
    l_wire_left: bytes
    l_wire_right_trimmed: bytes
    r_wire_left: bytes
    r_wire_right: bytes


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import {name} from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_rl_native_templates(project_path: Path) -> RlNativeTemplates:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    if chunk.count(b"$TERINPUT") != 2 or chunk.count(b"$TEROUTPUT") != 2:
        raise RuntimeError("R/L donor must contain two input and two output terminals.")
    if chunk.count(b"REALIND") != 3 or chunk.count(b"RESISTOR") != 2:
        raise RuntimeError("R/L donor must contain one REALIND visual record and one RESISTOR visual record.")

    cursor = 0
    header = chunk[cursor : cursor + 1]
    cursor += 1
    l_input = chunk[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    r_input = chunk[cursor : cursor + IN_SIZE]
    cursor += IN_SIZE
    l_output = chunk[cursor : cursor + OUT_SIZE]
    cursor += OUT_SIZE
    l_inductor = chunk[cursor : cursor + IND_SIZE]
    cursor += IND_SIZE
    l_wire_left = chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    l_wire_right_trimmed = chunk[cursor : cursor + L_RIGHT_WIRE_TRIMMED_SIZE]
    cursor += L_RIGHT_WIRE_TRIMMED_SIZE
    r_output = chunk[cursor : cursor + OUT_SIZE]
    cursor += OUT_SIZE

    # The native stream has a single 00 boundary byte before the V9-style
    # resistor visual record. Keep it outside the resistor template so the
    # existing resistor patcher can operate on the normal 346-byte record.
    r_resistor_prefix = chunk[cursor : cursor + 1]
    cursor += 1
    r_resistor = chunk[cursor : cursor + RES_SIZE]
    cursor += RES_SIZE
    r_wire_left = chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    r_wire_right = chunk[cursor : cursor + WIRE_SIZE]
    cursor += WIRE_SIZE
    if cursor != len(chunk):
        raise RuntimeError(f"Unexpected R/L donor cursor {cursor} != chunk length {len(chunk)}.")
    if header != b"\x00" or r_resistor_prefix != b"\x00" or chunk[-1] != 0xFF:
        raise RuntimeError("R/L donor has unexpected stream boundary bytes.")
    return RlNativeTemplates(
        donor_chunk=chunk,
        header=header,
        l_input=l_input,
        r_input=r_input,
        l_output=l_output,
        r_output=r_output,
        l_inductor=l_inductor,
        r_resistor=r_resistor,
        r_resistor_prefix=r_resistor_prefix,
        l_wire_left=l_wire_left,
        l_wire_right_trimmed=l_wire_right_trimmed,
        r_wire_left=r_wire_left,
        r_wire_right=r_wire_right,
    )


def _marker_counts(data: bytes) -> dict[str, int]:
    markers = (
        "$TERPOWER",
        "$TERINPUT",
        "$TEROUTPUT",
        "$TERGROUND",
        "WIRE",
        "RESISTOR",
        "REALIND",
        "CAPACITOR",
        "CAP10",
        "COMPONENT ID",
        "COMPONENT VALUE",
    )
    return {marker: data.count(marker.encode("ascii")) for marker in markers}


def _positions(data: bytes, marker: bytes) -> list[int]:
    out: list[int] = []
    start = 0
    while True:
        pos = data.find(marker, start)
        if pos < 0:
            return out
        out.append(pos)
        start = pos + 1


def _terminal_suffix(record: bytes) -> int:
    return int.from_bytes(record[-4:-2], "little")


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _node_list(specs: list[Any]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _patch_wire(template: bytes, x1: int, y1: int, x2: int, y2: int, *, final: bool) -> bytes:
    record = bytearray(template)
    record[33:37] = rv9._i32(x1)
    record[37:41] = rv9._i32(y1)
    record[41:45] = rv9._i32(x2)
    record[45:49] = rv9._i32(y2)
    if len(record) == WIRE_SIZE:
        record[-1] = 0xFF if final else 0x00
    return bytes(record)


def _patch_rl_records(specs: list[Any], templates: RlNativeTemplates, v8: Any) -> tuple[bytes, list[dict[str, Any]], dict[str, int]]:
    l_spec = next(spec for spec in specs if spec.kind == "INDUCTOR")
    r_spec = next(spec for spec in specs if spec.kind == "RESISTOR")
    l_in_suffix = _terminal_suffix(templates.l_input)
    l_out_suffix = _terminal_suffix(templates.l_output)
    r_in_suffix = _terminal_suffix(templates.r_input)
    r_out_suffix = _terminal_suffix(templates.r_output)

    l_input = v8._patch_input(templates.l_input, l_spec.left, 1, l_spec.x, l_spec.y, l_in_suffix)
    l_output_marker = b"$TERGROUND" if l_spec.right == "G0" else b"$TEROUTPUT"
    l_output = v8._patch_output(templates.l_output, l_spec.right, 1, l_spec.x, l_spec.y, l_output_marker, l_out_suffix)
    l_ind_spec = v8.IndSpec(
        idx=l_spec.idx,
        source_ref=l_spec.source_ref,
        ref=l_spec.ref,
        value=l_spec.value,
        visible_value=l_spec.visible_value,
        left=l_spec.left,
        right=l_spec.right,
        x=l_spec.x,
        y=l_spec.y,
    )
    l_inductor = v8._patch_inductor(templates.l_inductor, l_ind_spec, 1, l_in_suffix, l_out_suffix)
    l_left_pin_x = l_spec.x - 762000
    l_right_pin_x = l_spec.x + 762000
    l_wire_left = _patch_wire(templates.l_wire_left, l_left_pin_x, l_spec.y, l_left_pin_x, l_spec.y, final=False)
    l_wire_right = _patch_wire(
        templates.l_wire_right_trimmed,
        l_right_pin_x + 254000,
        l_spec.y,
        l_right_pin_x,
        l_spec.y,
        final=False,
    )

    r_input = v8._patch_input(templates.r_input, r_spec.left, 2, r_spec.x, r_spec.y, r_in_suffix)
    r_output_marker = b"$TERGROUND" if r_spec.right == "G0" else b"$TEROUTPUT"
    r_output = v8._patch_output(templates.r_output, r_spec.right, 2, r_spec.x, r_spec.y, r_output_marker, r_out_suffix)
    r_resistor = rv9._patch_resistor(
        templates.r_resistor,
        2,
        r_spec.ref,
        r_spec.visible_value,
        r_spec.x,
        r_spec.y,
        0,
        r_in_suffix,
        r_out_suffix,
    )
    r_left_pin_x = r_spec.x - 762000
    r_right_pin_x = r_spec.x + 762000
    r_wire_left = _patch_wire(templates.r_wire_left, r_left_pin_x, r_spec.y, r_left_pin_x, r_spec.y, final=False)
    r_wire_right = _patch_wire(templates.r_wire_right, r_right_pin_x + 254000, r_spec.y, r_right_pin_x, r_spec.y, final=True)

    chunk = (
        templates.header
        + l_input
        + r_input
        + l_output
        + l_inductor
        + l_wire_left
        + l_wire_right
        + r_output
        + templates.r_resistor_prefix
        + r_resistor
        + r_wire_left
        + r_wire_right
    )
    l_map = {
        "idx": l_spec.idx,
        "kind": "INDUCTOR",
        "ref": l_spec.ref,
        "value": l_spec.value,
        "left": l_spec.left,
        "right": l_spec.right,
        "input_marker": "$TERINPUT",
        "output_marker": l_output_marker.decode("ascii"),
        "in_suffix": f"{l_in_suffix:04x}",
        "out_suffix": f"{l_out_suffix:04x}",
        "x": l_spec.x,
        "y": l_spec.y,
    }
    r_map = {
        "idx": r_spec.idx,
        "kind": "RESISTOR",
        "ref": r_spec.ref,
        "value": r_spec.value,
        "left": r_spec.left,
        "right": r_spec.right,
        "input_marker": "$TERINPUT",
        "output_marker": r_output_marker.decode("ascii"),
        "in_suffix": f"{r_in_suffix:04x}",
        "out_suffix": f"{r_out_suffix:04x}",
        "x": r_spec.x,
        "y": r_spec.y,
    }
    counts = {
        "power_bridge_count": 0,
        "ground_terminal_count": int(l_output_marker == b"$TERGROUND") + int(r_output_marker == b"$TERGROUND"),
        "resistor_count": 1,
        "inductor_count": 1,
    }
    return chunk, sorted([l_map, r_map], key=lambda item: item["idx"]), counts


def _validate_chunk(chunk: bytes, topology: list[dict[str, Any]], counts: dict[str, int]) -> list[str]:
    issues: list[str] = []
    ground_count = counts["ground_terminal_count"]
    power_count = counts["power_bridge_count"]
    expected = {
        "$TERPOWER": power_count,
        "$TERINPUT": 2,
        "$TEROUTPUT": 2 - ground_count + power_count,
        "$TERGROUND": ground_count,
        "WIRE": 4 + power_count,
        "REALIND": 3,
        "RESISTOR": 2,
        "COMPONENT ID": 2,
        "COMPONENT VALUE": 2,
    }
    actual = _marker_counts(chunk)
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    for marker, want in expected.items():
        got = actual[marker]
        if got != want:
            issues.append(f"{marker} count {got} != {want}")
    if len({item["in_suffix"] for item in topology}) != len(topology):
        issues.append("input suffixes are not unique")
    if len({item["out_suffix"] for item in topology}) != len(topology):
        issues.append("output suffixes are not unique")
    return issues


def _payload(case_id: str, description: str, specs: list[Any], topology: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "mixed-rcl-temp/v10-terminal-rl-donor",
        "generator_target": "proteus-8.13-terminal-rl-boundary-diagnostic",
        "case_id": case_id,
        "description": description,
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _node_list(specs)],
        "components": [
            {
                "idx": spec.idx,
                "ref": spec.ref,
                "type": spec.kind,
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y},
            }
            for spec in specs
        ],
        "metadata": {
            "temporary": True,
            "object_order": "header, all inputs, L output+REALIND+wires, R output+RESISTOR+wires",
            "topology": topology,
        },
    }


def _write_project_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_header_project: Path,
    cdb: bytes,
    object_chunk: bytes,
    specs: list[Any],
    topology: list[dict[str, Any]],
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
        "status": "temporary_mixed_rcl_v10_terminal_rl_donor_not_locked",
        "description": description,
        "donor_header_project": str(donor_header_project.relative_to(REPO_ROOT)),
        "object_order": "header, all inputs, L output+REALIND+wires, R output+RESISTOR+wires",
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "topology": topology,
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            chunk_path.name: rv9._sha256_file(chunk_path),
            "object_chunk": rv9._sha256_bytes(object_chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, description, specs, topology), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\nStatic validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _write_repack_case(case_id: str, description: str, source_project: Path) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    project_xml = patch_project_xml_version(read_internal_file(source_project, "PROJECT.XML"), PROTEUS_813)
    dsn = patch_root_dsn_version(read_internal_file(source_project, "ROOT.DSN"), PROTEUS_813)
    cdb = read_internal_file(source_project, "ROOT.CDB")
    output_path = case_dir / f"{case_id}.pdsprj"
    write_project_from_parts(source_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    chunk = rv9._extract_object_chunk(dsn)
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v10_exact_repack_control",
        "description": description,
        "source_project": str(source_project.relative_to(REPO_ROOT)),
        "marker_counts": _marker_counts(chunk),
        "object_chunk_len": len(chunk),
        "root_cdb_len": len(cdb),
        "static_validation_issues": [],
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            "object_chunk": rv9._sha256_bytes(chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"{case_id}\n\n{description}\n", encoding="utf-8")
    return manifest


def _rl_specs(v2: Any, mode: str) -> list[Any]:
    if mode == "donor_disconnected":
        return [
            v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", "L1", "L2", DONOR_L_X, DONOR_L_Y, {}),
            v2.RclSpec(2, "R1", "R1", "RESISTOR", "1k", "1k", "R1", "R2", DONOR_R_X, DONOR_R_Y, {}),
        ]
    if mode == "connected":
        return [
            v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", "N2", "N3", DONOR_L_X, DONOR_L_Y, {}),
            v2.RclSpec(2, "R1", "R1", "RESISTOR", "1k", "1k", "N1", "N2", DONOR_R_X, DONOR_R_Y, {}),
        ]
    if mode == "translated":
        return [
            v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", "L1", "L2", TRANSLATED_L_X, TRANSLATED_L_Y, {}),
            v2.RclSpec(2, "R1", "R1", "RESISTOR", "1k", "1k", "R1", "R2", TRANSLATED_R_X, TRANSLATED_R_Y, {}),
        ]
    if mode == "power_ground":
        return [
            v2.RclSpec(1, "L1", "L1", "INDUCTOR", "1mH", "1mH", "N1", "G0", TRANSLATED_L_X + 3810000, TRANSLATED_L_Y, {}),
            v2.RclSpec(2, "R1", "R1", "RESISTOR", "1k", "1k", "V0", "N1", TRANSLATED_L_X, TRANSLATED_L_Y, {}),
        ]
    raise ValueError(mode)


def _donor_analysis(project_path: Path) -> dict[str, Any]:
    dsn = read_internal_file(project_path, "ROOT.DSN")
    cdb = read_internal_file(project_path, "ROOT.CDB")
    chunk = rv9._extract_object_chunk(dsn)
    return {
        "project": str(project_path.relative_to(REPO_ROOT)),
        "pdsprj_sha256": rv9._sha256_file(project_path),
        "root_dsn_len": len(dsn),
        "root_cdb_len": len(cdb),
        "object_chunk_len": len(chunk),
        "object_chunk_sha256": rv9._sha256_bytes(chunk),
        "root_cdb_sha256": rv9._sha256_bytes(cdb),
        "marker_counts": _marker_counts(chunk),
        "marker_positions": {
            "$TERINPUT": _positions(chunk, b"$TERINPUT"),
            "$TEROUTPUT": _positions(chunk, b"$TEROUTPUT"),
            "REALIND": _positions(chunk, b"REALIND"),
            "RESISTOR": _positions(chunk, b"RESISTOR"),
            "WIRE": _positions(chunk, b"WIRE"),
            "COMPONENT ID": _positions(chunk, b"COMPONENT ID"),
            "COMPONENT VALUE": _positions(chunk, b"COMPONENT VALUE"),
        },
    }


def main() -> int:
    v2 = _load_module("mixed_rcl_v2_for_v10", V2_PATH)
    v8 = _load_module("inductor_v8_for_v10", V8_PATH)

    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")

    base = registry.get("e001_empty").path
    disconnected = registry.get("rl_terminal_disconnected").path
    series = registry.get("rl_terminal_series").path
    bridge_donor = registry.get("power_terminal_bridge_donor").path
    templates = _load_rl_native_templates(disconnected)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")

    cases: list[dict[str, Any]] = []
    cases.append(_write_repack_case("RCL_V10_T01_EXACT_DISCONNECTED_REPACK", "Exact deterministic repack of the manual disconnected terminal R+L donor.", disconnected))
    cases.append(_write_project_case(
        case_id="RCL_V10_T02_DISCONNECTED_CHUNK_IN_E001",
        description="Manual disconnected donor object chunk and CDB inserted into the clean E001 base.",
        base_project=base,
        donor_header_project=disconnected,
        cdb=read_internal_file(disconnected, "ROOT.CDB"),
        object_chunk=templates.donor_chunk,
        specs=_rl_specs(v2, "donor_disconnected"),
        topology=[],
        issues=[],
    ))
    cases.append(_write_repack_case("RCL_V10_T03_EXACT_SERIES_REPACK", "Exact deterministic repack of the manual series terminal R+L donor.", series))
    cases.append(_write_project_case(
        case_id="RCL_V10_T04_SERIES_CHUNK_IN_E001",
        description="Manual series donor object chunk and CDB inserted into the clean E001 base. This is a control for donor header/base compatibility.",
        base_project=base,
        donor_header_project=series,
        cdb=read_internal_file(series, "ROOT.CDB"),
        object_chunk=rv9._extract_object_chunk(read_internal_file(series, "ROOT.DSN")),
        specs=_rl_specs(v2, "connected"),
        topology=[],
        issues=[],
    ))

    for case_id, description, mode, add_power in [
        ("RCL_V10_T05_NATIVE_REBUILD_SAME_LABELS", "Generated rebuild from disconnected donor templates using the same labels and donor coordinates.", "donor_disconnected", False),
        ("RCL_V10_T06_NATIVE_CONNECTED_LABELS", "Generated R+L series using donor-native order and shared N2 terminal label, no power/ground.", "connected", False),
        ("RCL_V10_T07_NATIVE_TRANSLATED_DISCONNECTED", "Generated disconnected R+L translated to a new horizontal placement, proving coordinate mutation separately.", "translated", False),
        ("RCL_V10_T08_NATIVE_POWER_GROUND_SERIES", "Generated V0 to G0 R+L series using one donor-derived V0 power bridge and G0 ground endpoint.", "power_ground", True),
    ]:
        specs = _rl_specs(v2, mode)
        chunk, topology, counts = _patch_rl_records(specs, templates, v8)
        if add_power:
            chunk = templates.header + bridge_core + chunk[1:]
            counts["power_bridge_count"] = 1
        issues = _validate_chunk(chunk, topology, counts)
        cdb = v2._build_rcl_cdb(specs, v8)
        cases.append(_write_project_case(
            case_id=case_id,
            description=description,
            base_project=base,
            donor_header_project=disconnected,
            cdb=cdb,
            object_chunk=chunk,
            specs=specs,
            topology=topology,
            issues=issues,
        ))

    summary = {
        "batch_id": "MIXED_RCL_V10_TERMINAL_RL_DONOR_STATIC_20260601",
        "status": "static_generated_awaiting_user_proteus_test",
        "source_feedback": "V9 all generated terminal R+L guesses failed. V10 uses the manual terminal R+L donor native order instead.",
        "donor_analysis": {
            "disconnected": _donor_analysis(disconnected),
            "series": _donor_analysis(series),
            "finding": "The disconnected donor object order is header, both inputs, L output+REALIND+wires, then R output+RESISTOR+wires. The series donor is retained as a control because its CDB/component refs appear swapped relative to the requested names.",
        },
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "marker_counts": item["marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "DONOR_ANALYSIS.json").write_text(json.dumps(summary["donor_analysis"], indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Open in this order and report the first case that errors or renders wrong:\n\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(cases, 1))
        + "\n\nIf T01-T04 fail, the donor/control import is bad. If T05 fails, the donor-native mutation is still wrong. If T05 works, T06-T08 identify connected labels, translation, and V0/G0 behavior.\n",
        encoding="utf-8",
    )
    zip_base = REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V10_TERMINAL_RL_DONOR_TEMP_2026_06_01"
    archive = shutil.make_archive(str(zip_base), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "case_count": len(cases), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
