"""Generate inductor V2 diagnostics after V1 VGDVC failures.

V2 isolates the suspected REALIND link suffix issue:

- exact donor repacks
- exact donor object chunks inserted into E001
- generated mutations that preserve donor terminal/component suffix bytes
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
spec = importlib.util.spec_from_file_location("inductor_v1", V1_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("Could not load inductor V1 helper script.")
v1 = importlib.util.module_from_spec(spec)
sys.modules["inductor_v1"] = v1
spec.loader.exec_module(v1)

OUT_ROOT = REPO_ROOT / "experiments" / "inductor_v2_suffix_temp_2026_05_31"


def _donor_suffix(record: bytes) -> int:
    return int.from_bytes(record[-4:-2], "little")


def _patch_inductor_preserve_suffix(template: bytes, *, index: int, ref: str, value: str, x: int, y: int) -> bytes:
    record = bytearray(
        v1._patch_inductor(
            template,
            index=index,
            ref=ref,
            value=value,
            x=x,
            y=y,
            in_suffix=0,
            out_suffix=0,
        )
    )
    delta = len(value.encode("ascii")) - 3
    record[364 + delta : 372 + delta] = template[364 + delta : 372 + delta]
    record[-1] = 0x00
    return bytes(record)


def _patch_group_preserve_suffix(templates: Any, spec: Any, index: int, count: int) -> dict[str, Any]:
    input_template = templates.inputs[(index - 1) % len(templates.inputs)]
    output_template = templates.outputs[(index - 1) % len(templates.outputs)]
    ind_template = templates.inductor_by_value_len[len(spec.value.encode("ascii"))]
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
    in_suffix = _donor_suffix(input_template)
    out_suffix = _donor_suffix(output_template)
    inductor = _patch_inductor_preserve_suffix(ind_template, index=index, ref=spec.ref, value=spec.value, x=spec.x, y=spec.y)
    wire_left = v1.rv9._patch_wire(templates.wire_lefts[(index - 1) % len(templates.wire_lefts)], left_pin_x, y, left_pin_x, y)
    wire_right = v1.rv9._patch_wire(templates.wire_right, right_pin_x + 254000, y, right_pin_x, y)
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


def _build_object_chunk_preserve_suffix(specs: list[Any], templates: Any) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    groups = [_patch_group_preserve_suffix(templates, spec, index, len(specs)) for index, spec in enumerate(specs, start=1)]
    out = bytearray(templates.header)
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
        "power_bridge_count": 0,
        "power_nodes": [],
        "ground_terminal_count": sum(1 for item in maps if item["output_marker"] == "$TERGROUND"),
    }
    return bytes(out), maps, counts


def _write_payload(case_dir: Path, name: str, specs: list[Any], notes: str) -> None:
    payload = v1._case_payload(name, specs, notes)
    (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open {name}.pdsprj in Proteus 8.13 first.\n\n{notes}\n", encoding="utf-8")


def _write_case_from_parts(
    name: str,
    *,
    output_project: Path,
    dsn: bytes,
    cdb: bytes,
    object_chunk: bytes,
    specs: list[Any],
    maps: list[dict[str, Any]],
    counts: dict[str, Any],
    notes: str,
    section_pointers: dict[str, int] | None = None,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / f"{name}.ROOT.DSN.bin").write_bytes(dsn)
    (case_dir / f"{name}.ROOT.CDB.bin").write_bytes(cdb)
    destination_project = case_dir / f"{name}.pdsprj"
    if output_project.resolve() != destination_project.resolve():
        shutil.copy2(output_project, destination_project)
    _write_payload(case_dir, name, specs, notes)
    manifest = {
        "case_id": name,
        "source": "inductor V2 suffix-preservation diagnostics",
        "notes": notes,
        "component_count": len(specs),
        "power_bridge_count": counts.get("power_bridge_count", 0),
        "ground_terminal_count": counts.get("ground_terminal_count", 0),
        "object_chunk_len": len(object_chunk),
        "root_dsn_len": len(dsn),
        "root_cdb_len": len(cdb),
        "section_pointer_values": section_pointers or {},
        "marker_counts": {
            "$TERINPUT": object_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
            "$TERPOWER": object_chunk.count(b"$TERPOWER"),
            "$TERGROUND": object_chunk.count(b"$TERGROUND"),
            "REALIND": object_chunk.count(b"REALIND"),
            "WIRE": object_chunk.count(b"WIRE"),
        },
        "topology": maps,
        "static_validation_issues": v1._validate_chunk(object_chunk, specs, maps, counts),
        "output_hashes": {
            "pdsprj_sha256": v1.rv9._sha256_file(case_dir / f"{name}.pdsprj"),
            "root_dsn_sha256": v1.rv9._sha256_bytes(dsn),
            "root_cdb_sha256": v1.rv9._sha256_bytes(cdb),
            "object_chunk_sha256": v1.rv9._sha256_bytes(object_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _write_repack_case(name: str, donor: Any, specs: list[Any], notes: str) -> dict[str, Any]:
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True)
    output_path = case_dir / f"{name}.pdsprj"
    v1.write_project_from_parts(donor.path, output_path, {})
    dsn = v1.read_internal_file(output_path, "ROOT.DSN")
    cdb = v1.read_internal_file(output_path, "ROOT.CDB")
    object_chunk = v1.rv9._extract_object_chunk(dsn)
    _write_payload(case_dir, name, specs, notes)
    (case_dir / f"{name}.ROOT.DSN.bin").write_bytes(dsn)
    (case_dir / f"{name}.ROOT.CDB.bin").write_bytes(cdb)
    maps = [{"idx": i, "ref": spec.ref, "value": spec.value, "left": spec.left, "right": spec.right} for i, spec in enumerate(specs, 1)]
    counts = {"power_bridge_count": object_chunk.count(b"$TERPOWER"), "ground_terminal_count": object_chunk.count(b"$TERGROUND")}
    manifest = {
        "case_id": name,
        "source": f"deterministic repack of {donor.id}",
        "notes": notes,
        "component_count": len(specs),
        "power_bridge_count": counts["power_bridge_count"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_chunk_len": len(object_chunk),
        "root_dsn_len": len(dsn),
        "root_cdb_len": len(cdb),
        "marker_counts": {
            "$TERINPUT": object_chunk.count(b"$TERINPUT"),
            "$TEROUTPUT": object_chunk.count(b"$TEROUTPUT"),
            "$TERPOWER": object_chunk.count(b"$TERPOWER"),
            "$TERGROUND": object_chunk.count(b"$TERGROUND"),
            "REALIND": object_chunk.count(b"REALIND"),
            "WIRE": object_chunk.count(b"WIRE"),
        },
        "topology": maps,
        "static_validation_issues": [],
        "output_hashes": {
            "pdsprj_sha256": v1.rv9._sha256_file(output_path),
            "root_dsn_sha256": v1.rv9._sha256_bytes(dsn),
            "root_cdb_sha256": v1.rv9._sha256_bytes(cdb),
            "object_chunk_sha256": v1.rv9._sha256_bytes(object_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _write_exact_chunk_case(name: str, donor: Any, base: Any, specs: list[Any], notes: str) -> dict[str, Any]:
    object_chunk = v1.rv9._extract_object_chunk(v1.read_internal_file(donor.path, "ROOT.DSN"))
    dsn, section_pointers = v1.rv9.build_dsn(
        v1.read_internal_file(base.path, "ROOT.DSN"),
        v1.read_internal_file(donor.path, "ROOT.DSN"),
        object_chunk,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    cdb = v1.read_internal_file(donor.path, "ROOT.CDB")
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base.path, "PROJECT.XML"), v1.PROTEUS_813)
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True)
    output_path = case_dir / f"{name}.pdsprj"
    v1.write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    maps = [{"idx": i, "ref": spec.ref, "value": spec.value, "left": spec.left, "right": spec.right} for i, spec in enumerate(specs, 1)]
    counts = {"power_bridge_count": object_chunk.count(b"$TERPOWER"), "ground_terminal_count": object_chunk.count(b"$TERGROUND")}
    return _write_case_from_parts(
        name,
        output_project=output_path,
        dsn=dsn,
        cdb=cdb,
        object_chunk=object_chunk,
        specs=specs,
        maps=maps,
        counts=counts,
        notes=notes,
        section_pointers=section_pointers,
    )


def _write_suffix_case(name: str, base: Any, donor: Any, templates: Any, specs: list[Any], notes: str) -> dict[str, Any]:
    object_chunk, maps, counts = _build_object_chunk_preserve_suffix(specs, templates)
    dsn, section_pointers = v1.rv9.build_dsn(
        v1.read_internal_file(base.path, "ROOT.DSN"),
        v1.read_internal_file(donor.path, "ROOT.DSN"),
        object_chunk,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    cdb = v1._build_cdb(specs)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base.path, "PROJECT.XML"), v1.PROTEUS_813)
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True)
    output_path = case_dir / f"{name}.pdsprj"
    v1.write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    return _write_case_from_parts(
        name,
        output_project=output_path,
        dsn=dsn,
        cdb=cdb,
        object_chunk=object_chunk,
        specs=specs,
        maps=maps,
        counts=counts,
        notes=notes,
        section_pointers=section_pointers,
    )


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    registry = v1.FixtureRegistry.load()
    base = registry.get("e001_empty")
    donor02 = registry.get("inductor_02_two_terminal")
    donor03 = registry.get("inductor_03_three_terminal")
    donor04 = registry.get("inductor_04_power_ground")
    templates = v1._load_templates(donor03.path)
    s1 = [v1.InductorSpec("L1", "1mH", "N1", "N2", -7366000, 1270000)]
    s3 = [
        v1.InductorSpec("L1", "1mH", "N1", "N2", -7366000, 1270000),
        v1.InductorSpec("L2", "2mH", "N3", "N4", -7366000, 0),
        v1.InductorSpec("L3", "10uH", "N5", "N6", -7366000, -1270000),
    ]
    spg = [v1.InductorSpec("L1", "1mH", "V0", "G0", -7366000, 1270000)]
    manifests = [
        _write_repack_case("IND_V2_T01_DONOR02_REPACK_EXACT", donor02, s1, "Exact deterministic repack of your two-terminal donor."),
        _write_exact_chunk_case("IND_V2_T02_E001_DONOR02_EXACT_CHUNK", donor02, base, s1, "E001 base with exact donor02 ROOT.DSN object chunk and exact donor02 ROOT.CDB."),
        _write_suffix_case("IND_V2_T03_SUFFIX_PRESERVED_SINGLE", base, donor03, templates, s1, "Generated single inductor preserving donor suffix bytes; should match donor02 object chunk."),
        _write_suffix_case(
            "IND_V2_T04_SUFFIX_PRESERVED_RENAMED",
            base,
            donor03,
            templates,
            [v1.InductorSpec("LA", "2mH", "A1", "B1", -4826000, 2540000)],
            "Renamed/translated single inductor while preserving donor suffix bytes.",
        ),
        _write_repack_case("IND_V2_T05_DONOR03_REPACK_EXACT", donor03, s3, "Exact deterministic repack of your three-inductor donor."),
        _write_exact_chunk_case("IND_V2_T06_E001_DONOR03_EXACT_CHUNK", donor03, base, s3, "E001 base with exact donor03 object chunk and exact donor03 ROOT.CDB."),
        _write_suffix_case("IND_V2_T07_SUFFIX_PRESERVED_THREE", base, donor03, templates, s3, "Generated three-inductor case preserving donor suffix bytes; should match donor03 object chunk."),
        _write_repack_case("IND_V2_T08_DONOR04_REPACK_EXACT", donor04, spg, "Exact deterministic repack of your power/ground inductor donor."),
        _write_exact_chunk_case("IND_V2_T09_E001_DONOR04_EXACT_CHUNK", donor04, base, spg, "E001 base with exact donor04 object chunk and exact donor04 ROOT.CDB."),
    ]
    summary = {
        "case": "INDUCTOR_V2_SUFFIX_TEMP_2026_05_31",
        "status": "awaiting_user_proteus_test",
        "method": "exact donor controls plus REALIND suffix-preserving generation",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V2 suffix-preservation diagnostic pack.\n\nOpen in this order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(manifests, 1))
        + "\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(REPO_ROOT / "experiments" / "INDUCTOR_V2_SUFFIX_TEMP_2026_05_31"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
