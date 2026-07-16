"""Generate inductor V8 diagnostics from the user-supplied six-inductor donor.

V6 failed because it extrapolated from the three-inductor donor. This pack uses
the new six-terminal-inductor donor directly. It also includes one cap-style
outputs-first probe because the non-final right-wire trimming rule matches the
manual capacitor donor, even though the observed six-inductor donor order is
sequential groups.
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

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "inductor_v8_six_donor_temp_2026_06_01"
SOURCE_6R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T01_6R_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"
SOURCE_21R = REPO_ROOT / "proteus" / "experiments" / "runs" / "power_ground_endpoint_examples_2026_05_30" / "BOTH_T02_R21_V0_G0_SHORTWIRE_ATTEMPT" / "input.json"

IN_SIZE = 103
OUT_SIZE = 104
IND_SIZE = 374
WIRE_SIZE = 50
WIRE_TRIMMED_SIZE = 49
GROUP_SIZE_TRIMMED = IN_SIZE + OUT_SIZE + IND_SIZE + WIRE_SIZE + WIRE_TRIMMED_SIZE
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
class SixTemplates:
    donor_chunk: bytes
    header: bytes
    inputs: tuple[bytes, ...]
    outputs: tuple[bytes, ...]
    inductors: tuple[bytes, ...]
    wire_lefts: tuple[bytes, ...]
    wire_rights: tuple[bytes, ...]


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


def _visible_value(index: int) -> str:
    value = ((index - 1) % 9) + 1
    return f"{value}mH"


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _load_six_templates(project_path: Path) -> SixTemplates:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    expected_len = 1 + 5 * GROUP_SIZE_TRIMMED + (GROUP_SIZE_TRIMMED + 1)
    if len(chunk) != expected_len:
        raise RuntimeError(f"Expected six-inductor object chunk length {expected_len}, got {len(chunk)}.")
    if chunk.count(b"$TERINPUT") != 6 or chunk.count(b"$TEROUTPUT") != 6 or chunk.count(b"REALIND") != 18:
        raise RuntimeError("Six-inductor donor marker counts do not match expectations.")
    inputs: list[bytes] = []
    outputs: list[bytes] = []
    inductors: list[bytes] = []
    wire_lefts: list[bytes] = []
    wire_rights: list[bytes] = []
    starts = [1 + i * GROUP_SIZE_TRIMMED for i in range(6)]
    starts.append(len(chunk))
    for index in range(6):
        start = starts[index]
        end = starts[index + 1]
        inputs.append(chunk[start : start + IN_SIZE])
        outputs.append(chunk[start + IN_SIZE : start + IN_SIZE + OUT_SIZE])
        inductors.append(chunk[start + IN_SIZE + OUT_SIZE : start + IN_SIZE + OUT_SIZE + IND_SIZE])
        wire_lefts.append(chunk[start + IN_SIZE + OUT_SIZE + IND_SIZE : start + IN_SIZE + OUT_SIZE + IND_SIZE + WIRE_SIZE])
        wire_rights.append(chunk[start + IN_SIZE + OUT_SIZE + IND_SIZE + WIRE_SIZE : end])
    return SixTemplates(
        donor_chunk=chunk,
        header=chunk[:1],
        inputs=tuple(inputs),
        outputs=tuple(outputs),
        inductors=tuple(inductors),
        wire_lefts=tuple(wire_lefts),
        wire_rights=tuple(wire_rights),
    )


def _safe_positions(source: dict[str, Any]) -> dict[str, tuple[int, int]]:
    raw_positions = source.get("layout", {}).get("component_positions", {})
    xs = sorted({position["x"] for position in raw_positions.values()})
    ys = sorted({position["y"] for position in raw_positions.values()}, reverse=True)
    x_map = {x: BASE_X + index * SAFE_X_STEP for index, x in enumerate(xs)}
    y_map = {y: BASE_Y - index * SAFE_Y_STEP for index, y in enumerate(ys)}
    used: set[tuple[int, int]] = set()
    out: dict[str, tuple[int, int]] = {}
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
        x, y = positions[component["ref"]]
        left, right = component["nodes"]
        value = _visible_value(idx)
        specs.append(IndSpec(idx, component["ref"], _ref(idx), value, value, left, right, x, y))
    return source, specs


def _nodes(specs: list[IndSpec]) -> list[str]:
    out: list[str] = []
    for spec in specs:
        out.extend([spec.left, spec.right])
    return list(dict.fromkeys(out))


def _suffixes(index: int, policy: str, template_input: bytes, template_output: bytes) -> tuple[int, int]:
    if policy == "preserve_slot":
        return int.from_bytes(template_input[-4:-2], "little"), int.from_bytes(template_output[-4:-2], "little")
    if policy != "extend_from_donor05":
        raise ValueError(f"Unknown suffix policy {policy}.")
    step = 0x02A8
    return (0x01B2 + (index - 1) * step) & 0xFFFF, (0x01E4 + (index - 1) * step) & 0xFFFF


def _patch_terminal_suffix(record: bytes, suffix: int) -> bytes:
    out = bytearray(record)
    out[-4:-2] = rv9._u16(suffix)
    out[-2:] = b"\x01\x00"
    return bytes(out)


def _patch_input(template: bytes, label: str, index: int, x: int, y: int, suffix: int) -> bytes:
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
    return _patch_terminal_suffix(record, suffix)


def _patch_output(template: bytes, label: str, index: int, x: int, y: int, marker: bytes, suffix: int) -> bytes:
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
    return _patch_terminal_suffix(record, suffix)


def _patch_inductor(template: bytes, spec: IndSpec, index: int, in_suffix: int, out_suffix: int) -> bytes:
    raw_ref = spec.ref.encode("ascii")
    raw_value = spec.visible_value.encode("ascii")
    if len(raw_ref) != 2 or len(raw_value) != template[70]:
        raise ValueError(f"Unsupported inductor ref/value for template: {spec.ref} {spec.visible_value}")
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
    record[74:78] = rv9._i32(value_x)
    record[78:82] = rv9._i32(value_y)
    record[150:154] = rv9._i32(hidden_x)
    record[154:158] = rv9._i32(hidden_y)
    record[264:268] = rv9._i32(hidden_x)
    record[268:272] = rv9._i32(hidden_y)
    record[340:344] = rv9._i32(spec.x)
    record[344:348] = rv9._i32(spec.y)
    record[352:356] = rv9._u32(index)
    # REALIND donor link bytes begin at 365, unlike resistor records.
    record[365:367] = rv9._u16(in_suffix)
    record[367:369] = b"\x01\x00"
    record[369:371] = rv9._u16(out_suffix)
    record[371:373] = b"\x01\x00"
    record[-1] = 0x00
    return bytes(record)


def _patch_wire_keep_length(template: bytes, x1: int, y1: int, x2: int, y2: int, *, final: bool) -> bytes:
    record = bytearray(template)
    record[33:37] = rv9._i32(x1)
    record[37:41] = rv9._i32(y1)
    record[41:45] = rv9._i32(x2)
    record[45:49] = rv9._i32(y2)
    if len(record) == WIRE_SIZE:
        record[-1] = 0xFF if final else 0x00
    return bytes(record)


def _records_for_spec(
    spec: IndSpec,
    index: int,
    count: int,
    templates: SixTemplates,
    suffix_policy: str,
    *,
    ground_endpoints: bool,
) -> dict[str, Any]:
    slot = (index - 1) % 6
    input_template = templates.inputs[slot]
    output_template = templates.outputs[slot]
    inductor_template = templates.inductors[slot]
    in_suffix, out_suffix = _suffixes(index, suffix_policy, input_template, output_template)
    output_marker = b"$TERGROUND" if ground_endpoints and spec.right == "G0" else b"$TEROUTPUT"
    left_pin_x = spec.x - 762000
    right_pin_x = spec.x + 762000
    wire_right_template = templates.wire_rights[slot]
    if index != count and len(wire_right_template) == WIRE_SIZE:
        wire_right_template = wire_right_template[:-1]
    if index == count and len(wire_right_template) == WIRE_TRIMMED_SIZE:
        wire_right_template = wire_right_template + b"\x00"
    return {
        "input": _patch_input(input_template, spec.left, index, spec.x, spec.y, in_suffix),
        "output": _patch_output(output_template, spec.right, index, spec.x, spec.y, output_marker, out_suffix),
        "inductor": _patch_inductor(inductor_template, spec, index, in_suffix, out_suffix),
        "wire_left": _patch_wire_keep_length(templates.wire_lefts[slot], left_pin_x, spec.y, left_pin_x, spec.y, final=False),
        "wire_right": _patch_wire_keep_length(wire_right_template, right_pin_x + 254000, spec.y, right_pin_x, spec.y, final=index == count),
        "map": {
            "idx": index,
            "source_ref": spec.source_ref,
            "ref": spec.ref,
            "value": spec.value,
            "left": spec.left,
            "right": spec.right,
            "slot": slot + 1,
            "suffix_policy": suffix_policy,
            "input_marker": "$TERINPUT",
            "output_marker": output_marker.decode("ascii"),
            "in_suffix": f"{in_suffix:04x}",
            "out_suffix": f"{out_suffix:04x}",
            "x": spec.x,
            "y": spec.y,
            "wire_right_len": len(wire_right_template),
        },
    }


def _build_sequential_chunk(
    specs: list[IndSpec],
    templates: SixTemplates,
    suffix_policy: str,
    *,
    ground_endpoints: bool = False,
    power_bridge: bytes = b"",
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    groups = [
        _records_for_spec(spec, index, len(specs), templates, suffix_policy, ground_endpoints=ground_endpoints)
        for index, spec in enumerate(specs, start=1)
    ]
    out = bytearray(templates.header + power_bridge)
    for group in groups:
        out += group["input"] + group["output"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    maps = [group["map"] for group in groups]
    counts = {
        "mode": "sequential_groups",
        "power_bridge_count": 1 if power_bridge else 0,
        "ground_terminal_count": sum(1 for item in maps if item["output_marker"] == "$TERGROUND"),
    }
    return bytes(out), maps, counts


def _build_exact_rebuild_chunk(templates: SixTemplates) -> bytes:
    out = bytearray(templates.header)
    for index in range(6):
        out += (
            templates.inputs[index]
            + templates.outputs[index]
            + templates.inductors[index]
            + templates.wire_lefts[index]
            + templates.wire_rights[index]
        )
    return bytes(out)


def _build_cap_style_chunk(
    specs: list[IndSpec],
    templates: SixTemplates,
    suffix_policy: str,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    groups = [
        _records_for_spec(spec, index, len(specs), templates, suffix_policy, ground_endpoints=False)
        for index, spec in enumerate(specs, start=1)
    ]
    out = bytearray(templates.header)
    out += b"".join(group["output"] for group in groups)
    for group in groups:
        out += group["input"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    maps = [group["map"] for group in groups]
    counts = {"mode": "cap_style_outputs_first", "power_bridge_count": 0, "ground_terminal_count": 0}
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
    if len({item["in_suffix"] for item in maps}) != n:
        issues.append("input suffixes are not unique")
    if len({item["out_suffix"] for item in maps}) != n:
        issues.append("output suffixes are not unique")
    return issues


def _payload(case_id: str, source: dict[str, Any], specs: list[IndSpec], maps: list[dict[str, Any]], counts: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "inductor-temp-v8/v0",
        "generator_target": "proteus-8.13-inductor-six-donor-diagnostic",
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
    cdb: bytes | None = None,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    cdb = cdb if cdb is not None else _build_cdb(specs)
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
    donor05 = registry.get("inductor_05_six_terminal").path
    bridge_donor = registry.get("power_terminal_bridge_donor").path
    templates = _load_six_templates(donor05)
    bridge_core = rv9._load_power_bridge_core(read_internal_file(bridge_donor, "ROOT.DSN"), "V0")
    source6, specs6 = _convert_source(SOURCE_6R)
    source21, specs21 = _convert_source(SOURCE_21R)
    donor_source = {"metadata": {"case_id": "inductor_05_six_terminal_donor"}, "components": []}
    donor_specs = [
        IndSpec(i, f"L{i}", f"L{i}", "1mH", "1mH", f"N{2 * i - 1}" if i < 5 else ("N9" if i == 5 else "NB"), f"N{2 * i}" if i < 5 else ("Na" if i == 5 else "NC"), 0, 0)
        for i in range(1, 7)
    ]

    case_defs: list[tuple[str, str, dict[str, Any], list[IndSpec], bytes, list[dict[str, Any]], dict[str, Any], bytes | None]] = []
    exact_maps = [
        {"idx": i, "ref": f"L{i}", "value": "1mH", "left": donor_specs[i - 1].left, "right": donor_specs[i - 1].right, "input_marker": "$TERINPUT", "output_marker": "$TEROUTPUT", "in_suffix": f"{int.from_bytes(templates.inputs[i - 1][-4:-2], 'little'):04x}", "out_suffix": f"{int.from_bytes(templates.outputs[i - 1][-4:-2], 'little'):04x}"}
        for i in range(1, 7)
    ]
    exact_counts = {"mode": "donor05_exact_chunk", "power_bridge_count": 0, "ground_terminal_count": 0}
    case_defs.append(("IND_V8_T01_E001_DONOR05_EXACT_CHUNK", "E001 plus exact six-inductor donor05 object chunk and donor05 CDB.", donor_source, donor_specs, templates.donor_chunk, exact_maps, exact_counts, read_internal_file(donor05, "ROOT.CDB")))
    chunk = _build_exact_rebuild_chunk(templates)
    case_defs.append(("IND_V8_T02_REBUILD_DONOR05_SEQUENTIAL_EXACT", "Rebuilt donor05 sequential groups from slices; should match donor05 object bytes.", donor_source, donor_specs, chunk, exact_maps, exact_counts, read_internal_file(donor05, "ROOT.CDB")))
    chunk, maps, counts = _build_sequential_chunk(specs6, templates, "extend_from_donor05")
    case_defs.append(("IND_V8_T03_6L_SEQUENTIAL_EXTENDED_SUFFIX", "Six generated inductors using donor05 sequential order and the donor05 suffix step.", source6, specs6, chunk, maps, counts, None))
    chunk, maps, counts = _build_sequential_chunk(specs21, templates, "extend_from_donor05")
    case_defs.append(("IND_V8_T04_21L_SEQUENTIAL_EXTENDED_SUFFIX", "Twenty-one generated inductors using donor05 sequential order and extended suffixes.", source21, specs21, chunk, maps, counts, None))
    chunk, maps, counts = _build_cap_style_chunk(specs6, templates, "extend_from_donor05")
    case_defs.append(("IND_V8_T05_6L_CAP_STYLE_OUTPUTS_FIRST", "Six generated inductors using capacitor-style outputs-first order as a same-family probe.", source6, specs6, chunk, maps, counts, None))
    chunk, maps, counts = _build_sequential_chunk(specs6, templates, "extend_from_donor05", ground_endpoints=True, power_bridge=bridge_core)
    case_defs.append(("IND_V8_T06_6L_POWER_GROUND_CAP_BRIDGE_SEQUENTIAL", "Six generated inductors with resistor/capacitor-style power bridge plus donor05 sequential groups.", source6, specs6, chunk, maps, counts, None))

    manifests = [
        _write_case(
            case_id=case_id,
            description=description,
            source=source,
            specs=specs,
            base_project=base,
            donor_project=donor05,
            donor_dsn_project=donor05,
            object_chunk=chunk,
            maps=maps,
            counts=counts,
            cdb=cdb,
        )
        for case_id, description, source, specs, chunk, maps, counts, cdb in case_defs
    ]
    summary = {
        "case": "INDUCTOR_V8_SIX_DONOR_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "trigger": "User supplied a six-terminal-inductor donor after V6/V7/RCL failed.",
        "method": "Use donor05's observed sequential six-group order. Also test one capacitor-style outputs-first probe because the trimmed right-wire rule matches the cap donor.",
        "donor_finding": "Donor05 order is header, then six repeated $TERINPUT/$TEROUTPUT/REALIND/left-wire/right-wire groups. Non-final right wires are 49 bytes, matching the capacitor trim rule; the outputs-first cap order is not the observed donor05 order.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "T01 and T02 are controls; if either fails, stop and report exact error.",
            "T03 is the main six-inductor candidate using donor05's real order.",
            "T05 is the explicit capacitor-family ordering hypothesis.",
            "T06 is power/ground only after T03 works.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V8 six-donor diagnostic pack.\n\n"
        "Open in this exact order and stop at the first fatal Proteus error unless collecting diagnostics:\n\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport which files open, exact error text, and whether component count/labels look correct.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "INDUCTOR_V8_SIX_DONOR_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
