"""Generate temporary 6L/21L inductor diagnostics.

This pack is deliberately experimental. V3 proved generated inductors only up
to the three donor slots. V5 proved one V0/G0 inductor only when preserving the
inductor_04 donor order. V6 tests the missing 6/21 scale cases before any
promotion back to main.
"""

from __future__ import annotations

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

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "inductor_v6_6_21_temp_2026_06_01"
SOURCE_6R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_21R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"

IN_SIZE = 103
OUT_SIZE = 104
WIRE_SIZE = 50
WIRE_TRIMMED_SIZE = 49
SAFE_X_STEP = 3810000
SAFE_Y_STEP = 2540000
BASE_X = -7366000
BASE_Y = 5080000
IND_PROP_TEXT = b"{MODFILE=REALIND}\n{RP=1M}\n{ESR=0.2}\n{CP=0.2pF}\n\n\n\x00"


@dataclass(frozen=True)
class IndSpec:
    idx: int
    source_ref: str
    ref: str
    value: str
    visible_value: str
    left: str
    right: str
    x: int
    y: int


@dataclass(frozen=True)
class ThreeTemplates:
    donor_chunk: bytes
    header: bytes
    inputs: tuple[bytes, bytes, bytes]
    outputs: tuple[bytes, bytes, bytes]
    inductors: tuple[bytes, bytes, bytes]
    wire_lefts: tuple[bytes, bytes, bytes]
    wire_rights: tuple[bytes, bytes, bytes]


@dataclass(frozen=True)
class Donor04Bridge:
    power_terminal: bytes
    power_output: bytes
    power_wire: bytes


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return rv9._u32(4 + len(data)) + data


def _s32(record: bytes, offset: int) -> int:
    return int.from_bytes(record[offset : offset + 4], "little", signed=True)


def _ref(index: int) -> str:
    if index <= 9:
        return f"L{index}"
    return f"L{chr(ord('A') + index - 10)}"


def _value_for_slot(index: int) -> tuple[str, str]:
    slot = (index - 1) % 3
    if slot == 0:
        return "1mH", "1mH"
    if slot == 1:
        return "2mH", "2mH"
    return "10uH", "10uH"


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _load_three_templates(project_path: Path) -> ThreeTemplates:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    if chunk.count(b"$TERINPUT") != 3 or chunk.count(b"$TEROUTPUT") != 3 or chunk.count(b"REALIND") != 9:
        raise RuntimeError("inductor_03 donor does not match V3 expectations.")
    return ThreeTemplates(
        donor_chunk=chunk,
        header=chunk[:1],
        inputs=(chunk[1:104], chunk[889:992], chunk[1465:1568]),
        outputs=(chunk[104:208], chunk[681:785], chunk[785:889]),
        inductors=(chunk[208:582], chunk[992:1366], chunk[1568:1943]),
        wire_lefts=(chunk[582:632], chunk[1366:1416], chunk[1943:1993]),
        wire_rights=(chunk[632:681] + b"\x00", chunk[1416:1465] + b"\x00", chunk[1993:2043]),
    )


def _load_donor04_bridge(project_path: Path) -> Donor04Bridge:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    if len(chunk) != 947:
        raise RuntimeError("inductor_04 donor does not match V5 expectations.")
    return Donor04Bridge(
        power_terminal=chunk[527:630],
        power_output=chunk[630:734],
        power_wire=chunk[734:784],
    )


def _safe_positions(source: dict[str, Any]) -> dict[str, tuple[int, int]]:
    raw_positions = source.get("layout", {}).get("component_positions", {})
    xs = sorted({position["x"] for position in raw_positions.values()})
    ys = sorted({position["y"] for position in raw_positions.values()}, reverse=True)
    x_map = {x: BASE_X + index * SAFE_X_STEP for index, x in enumerate(xs)}
    y_map = {y: BASE_Y - index * SAFE_Y_STEP for index, y in enumerate(ys)}
    out: dict[str, tuple[int, int]] = {}
    used: set[tuple[int, int]] = set()
    for index, component in enumerate(source["components"]):
        raw = raw_positions.get(component["ref"])
        if raw is None:
            x, y = BASE_X + (index % 7) * SAFE_X_STEP, BASE_Y - (index // 7) * SAFE_Y_STEP
        else:
            x, y = x_map[raw["x"]], y_map[raw["y"]]
        while (x, y) in used:
            y -= SAFE_Y_STEP
        used.add((x, y))
        out[component["ref"]] = (x, y)
    return out


def _convert_source(path: Path) -> tuple[dict[str, Any], list[IndSpec]]:
    source = json.loads(path.read_text(encoding="utf-8"))
    positions = _safe_positions(source)
    specs: list[IndSpec] = []
    for idx, component in enumerate(source["components"], start=1):
        value, visible = _value_for_slot(idx)
        x, y = positions[component["ref"]]
        left, right = component["nodes"]
        specs.append(
            IndSpec(
                idx=idx,
                source_ref=component["ref"],
                ref=_ref(idx),
                value=value,
                visible_value=visible,
                left=left,
                right=right,
                x=x,
                y=y,
            )
        )
    return source, specs


def _nodes(specs: list[IndSpec]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _extended_suffixes(index: int) -> tuple[int, int]:
    donor_inputs = (0x01B2, 0x04C2, 0x0703)
    donor_outputs = (0x01E4, 0x04F4, 0x0735)
    if index <= 3:
        return donor_inputs[index - 1], donor_outputs[index - 1]
    step = 0x0310
    return (donor_inputs[2] + (index - 3) * step) & 0xFFFF, (donor_outputs[2] + (index - 3) * step) & 0xFFFF


def _patch_terminal_suffix(record: bytes, suffix: int) -> bytes:
    out = bytearray(record)
    out[-4:-2] = rv9._u16(suffix)
    out[-2] = 0x01
    out[-1] = 0x00
    return bytes(out)


def _patch_input(template: bytes, label: str, index: int, x: int, y: int, suffix_policy: str) -> tuple[bytes, int]:
    left_pin_x = x - 762000
    record, _ = rv9._patch_input(
        template,
        label,
        left_pin_x - 254000,
        y,
        left_pin_x - 635000,
        y,
        index,
        marker=b"$TERINPUT",
    )
    if suffix_policy == "repeat":
        return record[:-4] + template[-4:], int.from_bytes(template[-4:-2], "little")
    suffix = _extended_suffixes(index)[0]
    return _patch_terminal_suffix(record, suffix), suffix


def _patch_output(template: bytes, label: str, index: int, x: int, y: int, marker: bytes, suffix_policy: str) -> tuple[bytes, int]:
    right_pin_x = x + 762000
    record, _ = rv9._patch_output(
        template,
        label,
        right_pin_x + 508000,
        y,
        right_pin_x + 889000,
        y,
        index,
        marker=marker,
    )
    if suffix_policy == "repeat":
        return record[:-4] + template[-4:], int.from_bytes(template[-4:-2], "little")
    suffix = _extended_suffixes(index)[1]
    return _patch_terminal_suffix(record, suffix), suffix


def _patch_inductor(template: bytes, spec: IndSpec, index: int, in_suffix: int, out_suffix: int, suffix_policy: str) -> bytes:
    raw_ref = spec.ref.encode("ascii")
    raw_value = spec.visible_value.encode("ascii")
    if len(raw_ref) != 2 or len(raw_value) != template[70]:
        raise ValueError(f"Unsupported inductor ref/value length for {spec.ref} {spec.visible_value}.")
    delta = len(raw_value) - 3
    record = bytearray(template)
    record[2] = 2
    record[3:5] = raw_ref
    record[70] = len(raw_value)
    record[71 : 71 + len(raw_value)] = raw_value
    ref_x = spec.x - 528320
    ref_y = spec.y + 274320
    value_x = spec.x - 528320
    value_y = spec.y - 20320
    hidden_x = spec.x - 528320
    hidden_y = spec.y - 274320
    record[5:9] = rv9._i32(ref_x)
    record[9:13] = rv9._i32(ref_y)
    record[74 + delta : 78 + delta] = rv9._i32(value_x)
    record[78 + delta : 82 + delta] = rv9._i32(value_y)
    record[150 + delta : 154 + delta] = rv9._i32(hidden_x)
    record[154 + delta : 158 + delta] = rv9._i32(hidden_y)
    record[264 + delta : 268 + delta] = rv9._i32(hidden_x)
    record[268 + delta : 272 + delta] = rv9._i32(hidden_y)
    record[340 + delta : 344 + delta] = rv9._i32(spec.x)
    record[344 + delta : 348 + delta] = rv9._i32(spec.y)
    record[352 + delta : 356 + delta] = rv9._u32(index)
    if suffix_policy == "repeat":
        record[364 + delta : 372 + delta] = template[364 + delta : 372 + delta]
    else:
        record[364 + delta : 366 + delta] = rv9._u16(in_suffix)
        record[366 + delta : 368 + delta] = b"\x01\x00"
        record[368 + delta : 370 + delta] = rv9._u16(out_suffix)
        record[370 + delta : 372 + delta] = b"\x01\x00"
    record[-1] = 0x00
    return bytes(record)


def _patch_donor04_power_bridge(bridge: Donor04Bridge, output_label: str) -> bytes:
    power = bytearray(bridge.power_terminal)
    power[30] = 2
    power[31:33] = b"V0"
    power[-4:] = bridge.power_terminal[-4:]
    output = bytearray(bridge.power_output)
    output[31] = 2
    output[32:34] = output_label.encode("ascii")
    output[-4:] = bridge.power_output[-4:]
    return bytes(power + output + bridge.power_wire)


def _records_for_spec(
    spec: IndSpec,
    index: int,
    count: int,
    templates: ThreeTemplates,
    suffix_policy: str,
    *,
    ground_endpoints: bool,
) -> dict[str, Any]:
    slot = (index - 1) % 3
    input_template = templates.inputs[slot]
    output_template = templates.outputs[slot]
    inductor_template = templates.inductors[slot]
    left_pin_x = spec.x - 762000
    right_pin_x = spec.x + 762000
    output_marker = b"$TERGROUND" if ground_endpoints and spec.right == "G0" else b"$TEROUTPUT"
    input_record, in_suffix = _patch_input(input_template, spec.left, index, spec.x, spec.y, suffix_policy)
    output_record, out_suffix = _patch_output(output_template, spec.right, index, spec.x, spec.y, output_marker, suffix_policy)
    inductor_record = _patch_inductor(inductor_template, spec, index, in_suffix, out_suffix, suffix_policy)
    wire_left = rv9._patch_wire(templates.wire_lefts[slot], left_pin_x, spec.y, left_pin_x, spec.y)
    wire_right = rv9._patch_wire(templates.wire_rights[2], right_pin_x + 254000, spec.y, right_pin_x, spec.y)
    if index != count:
        wire_right = wire_right[:-1]
    return {
        "input": input_record,
        "output": output_record,
        "inductor": inductor_record,
        "wire_left": wire_left,
        "wire_right": wire_right,
        "map": {
            "idx": index,
            "source_ref": spec.source_ref,
            "ref": spec.ref,
            "value": spec.value,
            "visible_value": spec.visible_value,
            "left": spec.left,
            "right": spec.right,
            "input_marker": "$TERINPUT",
            "output_marker": output_marker.decode("ascii"),
            "slot": slot + 1,
            "suffix_policy": suffix_policy,
            "in_suffix": f"{in_suffix:04x}",
            "out_suffix": f"{out_suffix:04x}",
            "x": spec.x,
            "y": spec.y,
        },
    }


def _build_terminal_chunk(specs: list[IndSpec], templates: ThreeTemplates, suffix_policy: str) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    groups = [_records_for_spec(spec, i, len(specs), templates, suffix_policy, ground_endpoints=False) for i, spec in enumerate(specs, start=1)]
    out = bytearray(templates.header)
    first = groups[0]
    out += first["input"] + first["output"] + first["inductor"] + first["wire_left"] + first["wire_right"]
    out += b"".join(group["output"] for group in groups[1:])
    for group in groups[1:]:
        out += group["input"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    counts = {"mode": f"terminal_only_{suffix_policy}", "power_bridge_count": 0, "ground_terminal_count": 0}
    return bytes(out), [group["map"] for group in groups], counts


def _build_power_chunk(
    specs: list[IndSpec],
    templates: ThreeTemplates,
    bridge: Donor04Bridge,
    suffix_policy: str,
    *,
    bridge_order: str,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    groups = [_records_for_spec(spec, i, len(specs), templates, suffix_policy, ground_endpoints=True) for i, spec in enumerate(specs, start=1)]
    power_bridge = _patch_donor04_power_bridge(bridge, "V0")
    out = bytearray(templates.header)
    if bridge_order == "after_header":
        out += power_bridge
        first = groups[0]
        out += first["input"] + first["output"] + first["inductor"] + first["wire_left"] + first["wire_right"]
    elif bridge_order == "after_first_left_wire":
        first = groups[0]
        out += first["input"] + first["inductor"] + first["wire_left"] + power_bridge + first["output"] + first["wire_right"]
    else:
        raise ValueError(f"Unknown bridge_order {bridge_order}.")
    out += b"".join(group["output"] for group in groups[1:])
    for group in groups[1:]:
        out += group["input"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    maps = [group["map"] for group in groups]
    counts = {
        "mode": f"power_ground_{bridge_order}_{suffix_policy}",
        "power_bridge_count": 1,
        "ground_terminal_count": sum(1 for item in maps if item["output_marker"] == "$TERGROUND"),
    }
    return bytes(out), maps, counts


def _build_cdb(specs: list[IndSpec]) -> bytes:
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(specs))
    for index, spec in enumerate(specs, start=1):
        out += rv9._u32(index) + rv9._u32(1) + rv9._u32(0) + rv9._u32(index) + _enc_str(spec.ref)
        out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(index) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(specs))
    for index, spec in enumerate(specs, start=1):
        out += rv9._u32(index) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(IND_PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _validate_chunk(chunk: bytes, maps: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    n = len(maps)
    ground_count = counts["ground_terminal_count"]
    expected_counts = {
        "$TERPOWER": counts["power_bridge_count"],
        "$TERINPUT": n,
        "$TEROUTPUT": n - ground_count + counts["power_bridge_count"],
        "$TERGROUND": ground_count,
        "REALIND": n * 3,
        "WIRE": n * 2 + counts["power_bridge_count"],
    }
    for marker, expected in expected_counts.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected:
            issues.append(f"{marker} count {actual} != {expected}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if len({item["in_suffix"] for item in maps}) != n and maps[0]["suffix_policy"] != "repeat":
        issues.append("extended input suffixes are not unique")
    if len({item["out_suffix"] for item in maps}) != n and maps[0]["suffix_policy"] != "repeat":
        issues.append("extended output suffixes are not unique")
    return issues


def _payload(case_id: str, source: dict[str, Any], specs: list[IndSpec], maps: list[dict[str, Any]], counts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "inductor-temp-v6/v0",
        "generator_target": "proteus-8.13-inductor-6-21-diagnostic",
        "case_id": case_id,
        "source_resistor_case": source.get("metadata", {}).get("case_id"),
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in _nodes(specs)],
        "components": [
            {
                "idx": spec.idx,
                "source_ref": spec.source_ref,
                "ref": spec.ref,
                "type": "INDUCTOR",
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y},
            }
            for spec in specs
        ],
        "metadata": {"mode": counts["mode"], "topology": maps},
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    source: dict[str, Any],
    specs: list[IndSpec],
    base_project: Path,
    donor_project: Path,
    donor_dsn_project: Path,
    object_chunk: bytes,
    maps: list[dict[str, Any]],
    counts: dict[str, Any],
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    cdb = _build_cdb(specs)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_dsn_project, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, source, specs, maps, counts), indent=2) + "\n", encoding="utf-8")
    issues = _validate_chunk(object_chunk, maps, counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_diagnostic_not_locked",
        "description": description,
        "component_count": len(specs),
        "node_count": len(_nodes(specs)),
        "mode": counts["mode"],
        "donor_record_project": donor_project.name,
        "donor_dsn_project": donor_dsn_project.name,
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": {
            "$TERPOWER": object_chunk.count(b"$TERPOWER"),
            "$TERINPUT": object_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
            "$TERGROUND": object_chunk.count(b"$TERGROUND"),
            "REALIND": object_chunk.count(b"REALIND"),
            "WIRE": object_chunk.count(b"WIRE"),
        },
        "section_pointer_values": pointers,
        "topology": maps,
        "static_validation_issues": issues,
        "output_hashes": {
            output_path.name: rv9._sha256_file(output_path),
            cdb_path.name: rv9._sha256_file(cdb_path),
            dsn_path.name: rv9._sha256_file(dsn_path),
            "object_chunk": rv9._sha256_bytes(object_chunk),
            "ROOT.CDB": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Project: {output_path.name}\n"
        f"Components: {len(specs)} inductors\n"
        f"Mode: {counts['mode']}\n"
        f"Static validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base = registry.get("e001_empty").path
    donor03 = registry.get("inductor_03_three_terminal").path
    donor04 = registry.get("inductor_04_power_ground").path
    templates = _load_three_templates(donor03)
    donor04_bridge = _load_donor04_bridge(donor04)
    source6, specs6 = _convert_source(SOURCE_6R)
    source21, specs21 = _convert_source(SOURCE_21R)

    case_defs: list[tuple[str, str, dict[str, Any], list[IndSpec], bytes, list[dict[str, Any]], dict[str, Any], Path]] = []
    chunk, maps, counts = _build_terminal_chunk(specs6, templates, "repeat")
    case_defs.append(("IND_V6_T01_6L_TERMINAL_ONLY_REPEAT_SUFFIX", "Six inductors, terminal-label topology only, donor slot suffixes repeated. Tests whether >3 repeated suffixes open at all.", source6, specs6, chunk, maps, counts, donor03))
    chunk, maps, counts = _build_terminal_chunk(specs6, templates, "extended")
    case_defs.append(("IND_V6_T02_6L_TERMINAL_ONLY_EXTENDED_SUFFIX", "Six inductors, terminal-label topology only, donor suffixes preserved for slots 1-3 and extended after that.", source6, specs6, chunk, maps, counts, donor03))
    chunk, maps, counts = _build_terminal_chunk(specs21, templates, "extended")
    case_defs.append(("IND_V6_T03_21L_TERMINAL_ONLY_EXTENDED_SUFFIX", "Twenty-one inductors, terminal-label topology only, extended inductor suffix sequence.", source21, specs21, chunk, maps, counts, donor03))
    chunk, maps, counts = _build_power_chunk(specs6, templates, donor04_bridge, "extended", bridge_order="after_header")
    case_defs.append(("IND_V6_T04_6L_POWER_GROUND_DONOR04_BRIDGE_HEADER", "Six inductors with V0/G0 labels, donor04 power bridge inserted immediately after header. Diagnostic contrast case.", source6, specs6, chunk, maps, counts, donor04))
    chunk, maps, counts = _build_power_chunk(specs6, templates, donor04_bridge, "extended", bridge_order="after_first_left_wire")
    case_defs.append(("IND_V6_T05_6L_POWER_GROUND_DONOR04_AFTER_FIRST_LEFT_WIRE", "Six inductors with V0/G0 labels, donor04 power bridge placed after first input/REALIND/left-wire to mimic V5 order more closely.", source6, specs6, chunk, maps, counts, donor04))
    chunk, maps, counts = _build_power_chunk(specs21, templates, donor04_bridge, "extended", bridge_order="after_first_left_wire")
    case_defs.append(("IND_V6_T06_21L_POWER_GROUND_DONOR04_AFTER_FIRST_LEFT_WIRE", "Twenty-one inductors with V0/G0 labels using the best V6 donor04-order guess. Test only after T05.", source21, specs21, chunk, maps, counts, donor04))

    manifests = [
        _write_case(
            case_id=case_id,
            description=description,
            source=source,
            specs=specs,
            base_project=base,
            donor_project=donor03,
            donor_dsn_project=donor_dsn,
            object_chunk=chunk,
            maps=maps,
            counts=counts,
        )
        for case_id, description, source, specs, chunk, maps, counts, donor_dsn in case_defs
    ]
    summary = {
        "case": "INDUCTOR_V6_6_21_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "why": "User corrected that inductor is not locked until 6/21, 15-topology, and R/C/L mixed tests pass.",
        "method": "Scale V3 REALIND terminal records past three components and test donor04 bridge ordering for real V0/G0 terminals.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "T01-T03 isolate scale beyond the three donor slots without real power/ground terminals.",
            "T04-T06 add real V0/G0 terminal records using donor04 bridge slices; these are more likely to fail and are diagnostic.",
            "If both T01 and T02 fail, ask for a manual 6-inductor donor before continuing.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V6 6/21 diagnostic pack.\n\n"
        "Open in this exact order and stop at the first fatal Proteus error unless you want to continue diagnostics:\n\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport which files open, exact error text, and whether component count/labels look correct.\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "INDUCTOR_V6_6_21_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
