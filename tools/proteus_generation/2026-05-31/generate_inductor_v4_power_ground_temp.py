"""Generate inductor V4 power/ground lock-candidate diagnostics.

V3 proved generated multi-inductor mutations. V4 applies the same per-index
REALIND template preservation to powered networks using the already locked
passive endpoint method:

- one donor-derived $TERPOWER -> $TEROUTPUT(V0) bridge
- ordinary $TERINPUT(V0) component endpoints
- $TERGROUND(G0) right endpoints
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
V1_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-31" / "generate_inductor_v1_terminal_temp.py"
V2_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-31" / "generate_inductor_v2_suffix_temp.py"
V3_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-31" / "generate_inductor_v3_multi_temp.py"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


v1 = _load_module("inductor_v1", V1_PATH)
v2 = _load_module("inductor_v2", V2_PATH)
v3 = _load_module("inductor_v3", V3_PATH)

OUT_ROOT = REPO_ROOT / "experiments" / "inductor_v4_power_ground_temp_2026_05_31"


def _donor_suffix(record: bytes) -> int:
    return int.from_bytes(record[-4:-2], "little")


def _build_power_ground_chunk(specs: list[Any], templates: Any, bridge_dsn: bytes) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    power_nodes = list(dict.fromkeys(spec.left for spec in specs if spec.left == "V0"))
    if len(power_nodes) > 1:
        raise ValueError("V4 supports one distinct power node.")
    bridge_cores = [v1.rv9._load_power_bridge_core(bridge_dsn, node) for node in power_nodes]
    groups = []
    for index, spec in enumerate(specs, start=1):
        input_template = templates.inputs[index - 1]
        output_template = templates.outputs[index - 1]
        ind_template = templates.inductors[index - 1]
        left_pin_x = spec.x - 762000
        right_pin_x = spec.x + 762000
        y = spec.y
        input_record, _ = v1.rv9._patch_input(
            input_template,
            spec.left,
            left_pin_x - 254000,
            y,
            left_pin_x - 635000,
            y,
            index,
            marker=b"$TERINPUT",
        )
        input_record = input_record[:-4] + input_template[-4:]
        output_marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
        output_record, _ = v1.rv9._patch_output(
            output_template,
            spec.right,
            right_pin_x + 508000,
            y,
            right_pin_x + 889000,
            y,
            index,
            marker=output_marker,
        )
        output_record = output_record[:-4] + output_template[-4:]
        inductor = v2._patch_inductor_preserve_suffix(
            ind_template,
            index=index,
            ref=spec.ref,
            value=spec.value,
            x=spec.x,
            y=spec.y,
        )
        wire_left = v1.rv9._patch_wire(templates.wire_lefts[index - 1], left_pin_x, y, left_pin_x, y)
        wire_right_template = templates.wire_rights[index - 1]
        wire_right = v1.rv9._patch_wire(wire_right_template, right_pin_x + 254000, y, right_pin_x, y)
        if index != len(specs):
            wire_right = wire_right[:-1]
        groups.append(
            {
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
                    "in_suffix": f"{_donor_suffix(input_template):04x}",
                    "out_suffix": f"{_donor_suffix(output_template):04x}",
                    "x": spec.x,
                    "y": spec.y,
                },
            }
        )
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


def _validate_chunk(chunk: bytes, specs: list[Any], maps: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues = v1._validate_chunk(chunk, specs, maps, counts)
    for index in range(counts["power_bridge_count"]):
        bridge_end = 1 + (index + 1) * v1.POWER_BRIDGE_CORE_SIZE - 1
        if chunk[bridge_end] != 0:
            issues.append(f"power bridge {index + 1} terminator {chunk[bridge_end]:02x}")
    return issues


def _write_case(name: str, specs: list[Any], notes: str, *, base: Any, donor: Any, bridge: Any, templates: Any) -> dict[str, Any]:
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True)
    object_chunk, maps, counts = _build_power_ground_chunk(specs, templates, v1.read_internal_file(bridge.path, "ROOT.DSN"))
    dsn, section_pointers = v1.rv9.build_dsn(
        v1.read_internal_file(base.path, "ROOT.DSN"),
        v1.read_internal_file(donor.path, "ROOT.DSN"),
        object_chunk,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    cdb = v1._build_cdb(specs)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base.path, "PROJECT.XML"), v1.PROTEUS_813)
    output_path = case_dir / f"{name}.pdsprj"
    v1.write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    (case_dir / f"{name}.ROOT.DSN.bin").write_bytes(dsn)
    (case_dir / f"{name}.ROOT.CDB.bin").write_bytes(cdb)
    payload = v1._case_payload(name, specs, notes)
    payload["method"] = "temporary_inductor_v4_power_ground_lock_candidate"
    (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open {name}.pdsprj in Proteus 8.13 first.\n\n{notes}\n", encoding="utf-8")
    manifest = {
        "case_id": name,
        "source": "inductor V4 power/ground lock-candidate diagnostics",
        "notes": notes,
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
            "pdsprj_sha256": v1.rv9._sha256_file(output_path),
            "root_dsn_sha256": v1.rv9._sha256_bytes(dsn),
            "root_cdb_sha256": v1.rv9._sha256_bytes(cdb),
            "object_chunk_sha256": v1.rv9._sha256_bytes(object_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _cases() -> list[tuple[str, list[Any], str]]:
    return [
        (
            "IND_V4_T01_SINGLE_V0_G0_GENERATED",
            [v1.InductorSpec("L1", "1mH", "V0", "G0", -7366000, 1270000)],
            "Generated single inductor from V0 to G0 using one power bridge and a G0 ground endpoint.",
        ),
        (
            "IND_V4_T02_SERIES2_V0_G0_GENERATED",
            [
                v1.InductorSpec("L1", "1mH", "V0", "N1", -7366000, 1270000),
                v1.InductorSpec("L2", "2mH", "N1", "G0", -4826000, 1270000),
            ],
            "Generated two series inductors from V0 to G0.",
        ),
        (
            "IND_V4_T03_SERIES3_V0_G0_GENERATED",
            [
                v1.InductorSpec("L1", "1mH", "V0", "N1", -7366000, 1270000),
                v1.InductorSpec("L2", "2mH", "N1", "N2", -4826000, 1270000),
                v1.InductorSpec("L3", "10uH", "N2", "G0", -2286000, 1270000),
            ],
            "Generated three series inductors from V0 to G0.",
        ),
        (
            "IND_V4_T04_PARALLEL3_V0_G0_GENERATED",
            [
                v1.InductorSpec("L1", "1mH", "V0", "G0", -7366000, 2540000),
                v1.InductorSpec("L2", "2mH", "V0", "G0", -7366000, 0),
                v1.InductorSpec("L3", "10uH", "V0", "G0", -7366000, -2540000),
            ],
            "Generated three parallel inductors from V0 to G0.",
        ),
        (
            "IND_V4_T05_T_NETWORK_POWER_GROUND_GENERATED",
            [
                v1.InductorSpec("LA", "1mH", "V0", "N1", -7366000, 2540000),
                v1.InductorSpec("LB", "2mH", "N1", "G0", -4826000, 2540000),
                v1.InductorSpec("LC", "10uH", "N1", "G0", -4826000, 0),
            ],
            "Generated three-inductor T network with one powered left endpoint and two ground endpoints.",
        ),
    ]


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    registry = v1.FixtureRegistry.load()
    base = registry.get("e001_empty")
    donor = registry.get("inductor_03_three_terminal")
    bridge = registry.get("power_terminal_bridge_donor")
    templates = v3._load_three_templates(donor.path)
    manifests = [_write_case(name, specs, notes, base=base, donor=donor, bridge=bridge, templates=templates) for name, specs, notes in _cases()]
    summary = {
        "case": "INDUCTOR_V4_POWER_GROUND_TEMP_2026_05_31",
        "status": "awaiting_user_proteus_test",
        "method": "V3 per-index REALIND generation plus locked passive power/ground endpoint method",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V4 power/ground lock-candidate diagnostic pack.\n\nOpen in this order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(manifests, 1))
        + "\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(REPO_ROOT / "experiments" / "INDUCTOR_V4_POWER_GROUND_TEMP_2026_05_31"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
