"""Generate the first terminal-attached inductor diagnostic pack.

This is temporary research code. It uses the user-created inductor donors as
record templates and emits E001-based projects for Proteus testing.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

IN_SIZE = 103
OUT_SIZE = 104
IND_SIZE = 374
WIRE_SIZE = 50
POWER_BRIDGE_CORE_SIZE = 255
IND_PROP_TEXT = b"{MODFILE=REALIND}\n{RP=1M}\n{ESR=0.2}\n{CP=0.2pF}\n\n\n\x00"
OUT_ROOT = REPO_ROOT / "experiments" / "inductor_v1_terminal_temp_2026_05_31"


@dataclass(frozen=True)
class InductorSpec:
    ref: str
    value: str
    left: str
    right: str
    x: int
    y: int


@dataclass(frozen=True)
class InductorTemplates:
    header: bytes
    inputs: tuple[bytes, ...]
    outputs: tuple[bytes, ...]
    inductor_by_value_len: dict[int, bytes]
    wire_lefts: tuple[bytes, ...]
    wire_right: bytes


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    return bytes([len(raw)]) + raw


def _enc_text(data: bytes) -> bytes:
    return rv9._u32(4 + len(data)) + data


def _load_templates(project_path: Path) -> InductorTemplates:
    chunk = rv9._extract_object_chunk(read_internal_file(project_path, "ROOT.DSN"))
    if chunk.count(b"$TERINPUT") != 3 or chunk.count(b"$TEROUTPUT") != 3:
        raise ValueError("Inductor V1 donor must contain three terminal-attached inductors.")
    if chunk.count(b"REALIND") != 9 or chunk.count(b"WIRE") != 6:
        raise ValueError("Inductor V1 donor marker counts do not match the expected shape.")
    return InductorTemplates(
        header=chunk[:1],
        inputs=(chunk[1:104], chunk[889:992], chunk[1465:1568]),
        outputs=(chunk[104:208], chunk[681:785], chunk[785:889]),
        inductor_by_value_len={
            3: chunk[208:582],
            4: chunk[1568:1943],
        },
        wire_lefts=(chunk[582:632], chunk[1366:1416], chunk[1943:1993]),
        wire_right=chunk[1993:2043],
    )


def _patch_inductor(
    template: bytes,
    *,
    index: int,
    ref: str,
    value: str,
    x: int,
    y: int,
    in_suffix: int,
    out_suffix: int,
) -> bytes:
    if len(ref.encode("ascii")) != 2:
        raise ValueError("Inductor refs must be exactly two ASCII characters.")
    raw_value = value.encode("ascii")
    if len(raw_value) not in (3, 4):
        raise ValueError("Inductor V1 visible values must be 3 or 4 ASCII characters.")
    record = bytearray(template)
    delta = len(raw_value) - 3

    record[2] = 2
    record[3:5] = ref.encode("ascii")
    record[70] = len(raw_value)
    record[71 : 71 + len(raw_value)] = raw_value

    ref_x = x - 528320
    ref_y = y + 274320
    value_x = x - 528320
    value_y = y - 20320
    hidden_x = x - 528320
    hidden_y = y - 274320

    record[5:9] = rv9._i32(ref_x)
    record[9:13] = rv9._i32(ref_y)
    record[74 + delta : 78 + delta] = rv9._i32(value_x)
    record[78 + delta : 82 + delta] = rv9._i32(value_y)
    record[150 + delta : 154 + delta] = rv9._i32(hidden_x)
    record[154 + delta : 158 + delta] = rv9._i32(hidden_y)
    record[264 + delta : 268 + delta] = rv9._i32(hidden_x)
    record[268 + delta : 272 + delta] = rv9._i32(hidden_y)
    record[340 + delta : 344 + delta] = rv9._i32(x)
    record[344 + delta : 348 + delta] = rv9._i32(y)
    record[352 + delta : 356 + delta] = rv9._u32(index)
    record[364 + delta : 366 + delta] = rv9._u16(in_suffix)
    record[366 + delta] = 0x01
    record[367 + delta] = 0x00
    record[368 + delta : 370 + delta] = rv9._u16(out_suffix)
    record[370 + delta] = 0x01
    record[371 + delta] = 0x00
    record[-1] = 0x00
    return bytes(record)


def _build_cdb(specs: list[InductorSpec]) -> bytes:
    out = bytearray()
    count = len(specs)
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(count)
    for index, spec in enumerate(specs, start=1):
        out += rv9._u32(index) + rv9._u32(1) + rv9._u32(0) + rv9._u32(index) + _enc_str(spec.ref)
        out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(index) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(count)
    for index, spec in enumerate(specs, start=1):
        out += rv9._u32(index) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(IND_PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


def _patch_group(templates: InductorTemplates, spec: InductorSpec, index: int, count: int) -> dict[str, Any]:
    left_pin_x = spec.x - 762000
    right_pin_x = spec.x + 762000
    y = spec.y
    input_record, in_suffix = rv9._patch_input(
        templates.inputs[(index - 1) % len(templates.inputs)],
        spec.left,
        left_pin_x - 254000,
        y,
        left_pin_x - 635000,
        y,
        index,
        marker=b"$TERINPUT",
    )
    output_marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    output_record, out_suffix = rv9._patch_output(
        templates.outputs[(index - 1) % len(templates.outputs)],
        spec.right,
        right_pin_x + 508000,
        y,
        right_pin_x + 889000,
        y,
        index,
        marker=output_marker,
    )
    ind_template = templates.inductor_by_value_len[len(spec.value.encode("ascii"))]
    inductor = _patch_inductor(
        ind_template,
        index=index,
        ref=spec.ref,
        value=spec.value,
        x=spec.x,
        y=spec.y,
        in_suffix=in_suffix,
        out_suffix=out_suffix,
    )
    wire_left = rv9._patch_wire(templates.wire_lefts[(index - 1) % len(templates.wire_lefts)], left_pin_x, y, left_pin_x, y)
    wire_right = rv9._patch_wire(templates.wire_right, right_pin_x + 254000, y, right_pin_x, y)
    if index != count:
        wire_right = wire_right[:-1]
    return {
        "input": input_record,
        "output": output_record,
        "inductor": inductor,
        "wire_left": wire_left,
        "wire_right": wire_right,
        "map": {
            "idx": index,
            "ref": spec.ref,
            "value": spec.value,
            "left": spec.left,
            "right": spec.right,
            "input_marker": "$TERINPUT",
            "output_marker": output_marker.decode("ascii"),
            "in_suffix": f"{in_suffix:04x}",
            "out_suffix": f"{out_suffix:04x}",
            "x": spec.x,
            "y": spec.y,
        },
    }


def _build_object_chunk(specs: list[InductorSpec], templates: InductorTemplates, bridge_dsn: bytes | None) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    power_nodes = list(dict.fromkeys(spec.left for spec in specs if spec.left == "V0"))
    bridge_cores = [rv9._load_power_bridge_core(bridge_dsn, node) for node in power_nodes] if bridge_dsn else []
    groups = [_patch_group(templates, spec, index, len(specs)) for index, spec in enumerate(specs, start=1)]
    out = bytearray(templates.header + b"".join(bridge_cores))
    if len(groups) == 1:
        group = groups[0]
        out += group["input"] + group["output"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    else:
        first = groups[0]
        out += first["input"] + first["output"] + first["inductor"] + first["wire_left"] + first["wire_right"]
        out += b"".join(group["output"] for group in groups[1:])
        for group in groups[1:]:
            out += group["input"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    maps = [group["map"] for group in groups]
    counts = {
        "power_bridge_count": len(bridge_cores),
        "power_nodes": power_nodes,
        "ground_terminal_count": sum(1 for item in maps if item["output_marker"] == "$TERGROUND"),
    }
    return bytes(out), maps, counts


def _validate_chunk(chunk: bytes, specs: list[InductorSpec], maps: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    expected = {
        "$TERINPUT": len(specs),
        "$TERPOWER": counts["power_bridge_count"],
        "$TEROUTPUT": len(specs) - counts["ground_terminal_count"] + counts["power_bridge_count"],
        "$TERGROUND": counts["ground_terminal_count"],
        "REALIND": len(specs) * 3,
        "COMPONENT ID": len(specs),
        "WIRE": len(specs) * 2 + counts["power_bridge_count"],
    }
    for marker, expected_count in expected.items():
        actual = chunk.count(marker.encode("ascii"))
        if actual != expected_count:
            issues.append(f"{marker} count {actual} != {expected_count}")
    if not chunk or chunk[0] != 0:
        issues.append("chunk header not 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("final chunk byte not FF")
    for item in maps:
        if item["ref"].encode("ascii") not in chunk:
            issues.append(f"{item['ref']} ref missing from chunk")
    return issues


def _case_payload(name: str, specs: list[InductorSpec], notes: str) -> dict[str, Any]:
    nodes = sorted({node for spec in specs for node in (spec.left, spec.right)})
    return {
        "case_id": name,
        "component": "INDUCTOR",
        "method": "temporary_inductor_v1_terminal_donor",
        "notes": notes,
        "nodes": nodes,
        "components": [spec.__dict__ for spec in specs],
    }


def _write_case(
    name: str,
    specs: list[InductorSpec],
    notes: str,
    *,
    base_project: Path,
    donor_project: Path,
    bridge_project: Path,
    templates: InductorTemplates,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True)
    object_chunk, maps, counts = _build_object_chunk(specs, templates, read_internal_file(bridge_project, "ROOT.DSN"))
    base_dsn = read_internal_file(base_project, "ROOT.DSN")
    donor_dsn = read_internal_file(donor_project, "ROOT.DSN")
    dsn, section_pointers = rv9.build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    cdb = _build_cdb(specs)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{name}.pdsprj"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    (case_dir / f"{name}.ROOT.DSN.bin").write_bytes(dsn)
    (case_dir / f"{name}.ROOT.CDB.bin").write_bytes(cdb)
    payload = _case_payload(name, specs, notes)
    (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    manifest = {
        "case_id": name,
        "source": "user-supplied inductor donor projects",
        "base": "E001_EMPTY_BASE",
        "object_order": "header, optional power bridge, first full inductor group, remaining outputs, remaining input/inductor/wire groups",
        "component_count": len(specs),
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_chunk_len": len(object_chunk),
        "root_dsn_len": len(dsn),
        "root_cdb_len": len(cdb),
        "section_pointer_values": section_pointers,
        "marker_counts": {
            "$TERINPUT": object_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
            "$TERPOWER": object_chunk.count(b"$TERPOWER"),
            "$TERGROUND": object_chunk.count(b"$TERGROUND"),
            "REALIND": object_chunk.count(b"REALIND"),
            "WIRE": object_chunk.count(b"WIRE"),
        },
        "topology": maps,
        "static_validation_issues": _validate_chunk(object_chunk, specs, maps, counts),
        "output_hashes": {
            "pdsprj_sha256": rv9._sha256_file(output_path),
            "root_dsn_sha256": rv9._sha256_bytes(dsn),
            "root_cdb_sha256": rv9._sha256_bytes(cdb),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"Open {name}.pdsprj in Proteus 8.13 first.\n\n{notes}\n",
        encoding="utf-8",
    )
    return manifest


def _cases() -> list[tuple[str, list[InductorSpec], str]]:
    return [
        (
            "IND_V1_T01_SINGLE_N1_N2",
            [InductorSpec("L1", "1mH", "N1", "N2", -7366000, 1270000)],
            "One terminal-attached inductor, same topology as the two-terminal donor.",
        ),
        (
            "IND_V1_T02_RENAMED_TRANSLATED",
            [InductorSpec("LA", "2mH", "A1", "B1", -4826000, 2540000)],
            "One translated/renamed terminal-attached inductor.",
        ),
        (
            "IND_V1_T03_THREE_TERMINAL_INDUCTORS",
            [
                InductorSpec("L1", "1mH", "N1", "N2", -7366000, 1270000),
                InductorSpec("L2", "2mH", "N3", "N4", -7366000, 0),
                InductorSpec("L3", "10uH", "N5", "N6", -7366000, -1270000),
            ],
            "Three terminal-attached inductors, matching the scale donor pattern.",
        ),
        (
            "IND_V1_T04_POWER_GROUND_LOCKED_V0_G0",
            [InductorSpec("L1", "1mH", "V0", "G0", -7366000, 1270000)],
            "One inductor from V0 to G0 using the locked donor-derived power bridge and G0 ground endpoint.",
        ),
        (
            "IND_V1_T05_SERIES_POWER_GROUND_TWO_L",
            [
                InductorSpec("L1", "1mH", "V0", "N1", -7366000, 1270000),
                InductorSpec("L2", "2mH", "N1", "G0", -4826000, 1270000),
            ],
            "Two series inductors from V0 to G0 using terminal-label topology.",
        ),
    ]


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    registry = FixtureRegistry.load()
    base = registry.get("e001_empty")
    donor = registry.get("inductor_03_three_terminal")
    bridge = registry.get("power_terminal_bridge_donor")
    templates = _load_templates(donor.path)
    manifests = [
        _write_case(name, specs, notes, base_project=base.path, donor_project=donor.path, bridge_project=bridge.path, templates=templates)
        for name, specs, notes in _cases()
    ]
    summary = {
        "case": "INDUCTOR_V1_TERMINAL_TEMP_2026_05_31",
        "status": "awaiting_user_proteus_test",
        "method": "terminal-attached inductor donor records from E001",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V1 terminal diagnostic pack.\n\nOpen in this order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(manifests, 1))
        + "\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(REPO_ROOT / "experiments" / "INDUCTOR_V1_TERMINAL_TEMP_2026_05_31"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
