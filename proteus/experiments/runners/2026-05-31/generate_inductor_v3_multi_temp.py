"""Generate inductor V3 diagnostics for the V2 three-inductor failure.

V2 proved exact donor repacks, exact donor chunks, single suffix-preserved
mutation, and power/ground donor insertion. Only T7, the generated
three-inductor reconstruction, failed. V3 separates the remaining suspects:

- per-index REALIND template/link-suffix preservation
- donor-relative geometry preservation
- formula-recomputed geometry
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
V1_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-31" / "generate_inductor_v1_terminal_temp.py"
V2_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-05-31" / "generate_inductor_v2_suffix_temp.py"


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

OUT_ROOT = REPO_ROOT / "experiments" / "inductor_v3_multi_temp_2026_05_31"


@dataclass(frozen=True)
class ThreeInductorTemplates:
    donor_chunk: bytes
    header: bytes
    inputs: tuple[bytes, bytes, bytes]
    outputs: tuple[bytes, bytes, bytes]
    inductors: tuple[bytes, bytes, bytes]
    wire_lefts: tuple[bytes, bytes, bytes]
    wire_rights: tuple[bytes, bytes, bytes]


def _i32_at(record: bytes, offset: int) -> int:
    return int.from_bytes(record[offset : offset + 4], "little", signed=True)


def _add_i32(record: bytearray, offset: int, delta: int) -> None:
    record[offset : offset + 4] = v1.rv9._i32(_i32_at(record, offset) + delta)


def _load_three_templates(project_path: Path) -> ThreeInductorTemplates:
    chunk = v1.rv9._extract_object_chunk(v1.read_internal_file(project_path, "ROOT.DSN"))
    if chunk.count(b"$TERINPUT") != 3 or chunk.count(b"$TEROUTPUT") != 3:
        raise ValueError("V3 donor must contain three terminal-attached inductors.")
    if chunk.count(b"REALIND") != 9 or chunk.count(b"WIRE") != 6:
        raise ValueError("V3 donor marker counts do not match the expected three-inductor shape.")
    return ThreeInductorTemplates(
        donor_chunk=chunk,
        header=chunk[:1],
        inputs=(chunk[1:104], chunk[889:992], chunk[1465:1568]),
        outputs=(chunk[104:208], chunk[681:785], chunk[785:889]),
        inductors=(chunk[208:582], chunk[992:1366], chunk[1568:1943]),
        wire_lefts=(chunk[582:632], chunk[1366:1416], chunk[1943:1993]),
        wire_rights=(chunk[632:681], chunk[1416:1465], chunk[1993:2043]),
    )


def _patch_input_preserving_shape(template: bytes, label: str, index: int, *, dx: int = 0, dy: int = 0) -> bytes:
    symbol_x = _i32_at(template, 1) + dx
    symbol_y = _i32_at(template, 5) + dy
    label_x = _i32_at(template, 33) + dx
    label_y = _i32_at(template, 37) + dy
    patched, _ = v1.rv9._patch_input(template, label, symbol_x, symbol_y, label_x, label_y, index, marker=b"$TERINPUT")
    record = bytearray(patched)
    record[-4:] = template[-4:]
    return bytes(record)


def _patch_output_preserving_shape(template: bytes, label: str, index: int, *, dx: int = 0, dy: int = 0) -> bytes:
    symbol_x = _i32_at(template, 1) + dx
    symbol_y = _i32_at(template, 5) + dy
    label_x = _i32_at(template, 34) + dx
    label_y = _i32_at(template, 38) + dy
    patched, _ = v1.rv9._patch_output(template, label, symbol_x, symbol_y, label_x, label_y, index, marker=b"$TEROUTPUT")
    record = bytearray(patched)
    record[-4:] = template[-4:]
    return bytes(record)


def _patch_wire_preserving_shape(template: bytes, *, dx: int = 0, dy: int = 0) -> bytes:
    record = bytearray(template)
    for offset, delta in ((33, dx), (37, dy), (41, dx), (45, dy)):
        _add_i32(record, offset, delta)
    return bytes(record)


def _patch_inductor_preserving_shape(
    template: bytes,
    *,
    index: int,
    ref: str,
    value: str,
    dx: int = 0,
    dy: int = 0,
) -> bytes:
    raw_ref = ref.encode("ascii")
    raw_value = value.encode("ascii")
    if len(raw_ref) != 2:
        raise ValueError("Inductor refs must be exactly two ASCII characters.")
    if len(raw_value) != template[70]:
        raise ValueError("V3 text mutation keeps value byte length identical to its donor template.")
    delta = len(raw_value) - 3
    record = bytearray(template)
    record[2] = 2
    record[3:5] = raw_ref
    record[70] = len(raw_value)
    record[71 : 71 + len(raw_value)] = raw_value
    record[352 + delta : 356 + delta] = v1.rv9._u32(index)
    for offset in (5, 74 + delta, 150 + delta, 264 + delta, 340 + delta):
        _add_i32(record, offset, dx)
    for offset in (9, 78 + delta, 154 + delta, 268 + delta, 344 + delta):
        _add_i32(record, offset, dy)
    return bytes(record)


def _build_three_chunk_from_donor_shape(
    templates: ThreeInductorTemplates,
    specs: list[Any],
    *,
    dx: int = 0,
    dy: int = 0,
    mutate_text: bool = True,
) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    if len(specs) != 3:
        raise ValueError("V3 donor-shape builder is intentionally limited to three inductors.")
    groups = []
    for index, spec in enumerate(specs, start=1):
        input_template = templates.inputs[index - 1]
        output_template = templates.outputs[index - 1]
        inductor_template = templates.inductors[index - 1]
        if mutate_text or dx or dy:
            input_record = _patch_input_preserving_shape(input_template, spec.left, index, dx=dx, dy=dy)
            output_record = _patch_output_preserving_shape(output_template, spec.right, index, dx=dx, dy=dy)
            inductor_record = _patch_inductor_preserving_shape(
                inductor_template,
                index=index,
                ref=spec.ref,
                value=spec.value,
                dx=dx,
                dy=dy,
            )
            wire_left = _patch_wire_preserving_shape(templates.wire_lefts[index - 1], dx=dx, dy=dy)
            wire_right = _patch_wire_preserving_shape(templates.wire_rights[index - 1], dx=dx, dy=dy)
        else:
            input_record = input_template
            output_record = output_template
            inductor_record = inductor_template
            wire_left = templates.wire_lefts[index - 1]
            wire_right = templates.wire_rights[index - 1]
        groups.append(
            {
                "input": input_record,
                "output": output_record,
                "inductor": inductor_record,
                "wire_left": wire_left,
                "wire_right": wire_right,
                "map": {
                    "idx": index,
                    "ref": spec.ref,
                    "value": spec.value,
                    "left": spec.left,
                    "right": spec.right,
                    "input_marker": "$TERINPUT",
                    "output_marker": "$TEROUTPUT",
                    "dx": dx,
                    "dy": dy,
                },
            }
        )
    out = bytearray(templates.header)
    first = groups[0]
    out += first["input"] + first["output"] + first["inductor"] + first["wire_left"] + first["wire_right"]
    out += groups[1]["output"] + groups[2]["output"]
    for group in groups[1:]:
        out += group["input"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    maps = [group["map"] for group in groups]
    counts = {"power_bridge_count": 0, "power_nodes": [], "ground_terminal_count": 0}
    return bytes(out), maps, counts


def _build_three_chunk_formula_fixed_suffix(v1_templates: Any, v3_templates: ThreeInductorTemplates, specs: list[Any]) -> tuple[bytes, list[dict[str, Any]], dict[str, Any]]:
    groups = []
    for index, spec in enumerate(specs, start=1):
        input_template = v1_templates.inputs[index - 1]
        output_template = v1_templates.outputs[index - 1]
        ind_template = v3_templates.inductors[index - 1]
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
        output_record, _ = v1.rv9._patch_output(
            output_template,
            spec.right,
            right_pin_x + 508000,
            y,
            right_pin_x + 889000,
            y,
            index,
            marker=b"$TEROUTPUT",
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
        wire_left = v1.rv9._patch_wire(v1_templates.wire_lefts[index - 1], left_pin_x, y, left_pin_x, y)
        wire_right = v1.rv9._patch_wire(v3_templates.wire_rights[2], right_pin_x + 254000, y, right_pin_x, y)
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
                    "output_marker": "$TEROUTPUT",
                    "mode": "formula_coordinates_with_per_index_inductor_template",
                },
            }
        )
    out = bytearray(v1_templates.header)
    first = groups[0]
    out += first["input"] + first["output"] + first["inductor"] + first["wire_left"] + first["wire_right"]
    out += b"".join(group["output"] for group in groups[1:])
    for group in groups[1:]:
        out += group["input"] + group["inductor"] + group["wire_left"] + group["wire_right"]
    out[-1] = 0xFF
    maps = [group["map"] for group in groups]
    counts = {"power_bridge_count": 0, "power_nodes": [], "ground_terminal_count": 0}
    return bytes(out), maps, counts


def _write_payload(case_dir: Path, name: str, specs: list[Any], notes: str) -> None:
    payload = v1._case_payload(name, specs, notes)
    payload["method"] = "temporary_inductor_v3_multi_diagnostics"
    (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open {name}.pdsprj in Proteus 8.13 first.\n\n{notes}\n", encoding="utf-8")


def _write_case(
    name: str,
    *,
    base: Any,
    donor: Any,
    object_chunk: bytes,
    cdb: bytes,
    specs: list[Any],
    maps: list[dict[str, Any]],
    counts: dict[str, Any],
    notes: str,
    donor_chunk: bytes,
) -> dict[str, Any]:
    base_dsn = v1.read_internal_file(base.path, "ROOT.DSN")
    donor_dsn = v1.read_internal_file(donor.path, "ROOT.DSN")
    dsn, section_pointers = v1.rv9.build_dsn(base_dsn, donor_dsn, object_chunk)
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base.path, "PROJECT.XML"), v1.PROTEUS_813)
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True)
    output_path = case_dir / f"{name}.pdsprj"
    v1.write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    (case_dir / f"{name}.ROOT.DSN.bin").write_bytes(dsn)
    (case_dir / f"{name}.ROOT.CDB.bin").write_bytes(cdb)
    _write_payload(case_dir, name, specs, notes)
    static_issues = v1._validate_chunk(object_chunk, specs, maps, counts)
    manifest = {
        "case_id": name,
        "source": "inductor V3 multi-inductor diagnostics",
        "notes": notes,
        "component_count": len(specs),
        "power_bridge_count": counts.get("power_bridge_count", 0),
        "ground_terminal_count": counts.get("ground_terminal_count", 0),
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
        "matches_donor03_object_chunk": object_chunk == donor_chunk,
        "donor03_object_chunk_sha256": v1.rv9._sha256_bytes(donor_chunk),
        "static_validation_issues": static_issues,
        "output_hashes": {
            "pdsprj_sha256": v1.rv9._sha256_file(output_path),
            "root_dsn_sha256": v1.rv9._sha256_bytes(dsn),
            "root_cdb_sha256": v1.rv9._sha256_bytes(cdb),
            "object_chunk_sha256": v1.rv9._sha256_bytes(object_chunk),
        },
    }
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    registry = v1.FixtureRegistry.load()
    base = registry.get("e001_empty")
    donor03 = registry.get("inductor_03_three_terminal")
    templates = _load_three_templates(donor03.path)
    v1_templates = v1._load_templates(donor03.path)
    donor_specs = [
        v1.InductorSpec("L1", "1mH", "N1", "N2", -7366000, 1270000),
        v1.InductorSpec("L2", "2mH", "N3", "N4", -7366000, 0),
        v1.InductorSpec("L3", "10uH", "N5", "N6", -7366000, -1270000),
    ]
    renamed_donor_specs = [
        v1.InductorSpec("LA", "1mH", "A1", "B1", -7366000, 1270000),
        v1.InductorSpec("LB", "2mH", "C1", "D1", -7366000, 0),
        v1.InductorSpec("LC", "10uH", "E1", "F1", -7366000, -1270000),
    ]
    donor_translated_specs = [
        v1.InductorSpec("L1", "1mH", "N1", "N2", -4826000, 1778000),
        v1.InductorSpec("L2", "2mH", "N3", "N4", -4826000, 508000),
        v1.InductorSpec("L3", "10uH", "N5", "N6", -4826000, -762000),
    ]
    renamed_translated_specs = [
        v1.InductorSpec("LA", "1mH", "A1", "B1", -4826000, 1778000),
        v1.InductorSpec("LB", "2mH", "C1", "D1", -4826000, 508000),
        v1.InductorSpec("LC", "10uH", "E1", "F1", -4826000, -762000),
    ]
    manifests = []

    chunk, maps, counts = _build_three_chunk_from_donor_shape(templates, donor_specs, mutate_text=False)
    manifests.append(
        _write_case(
            "IND_V3_T01_REBUILD_DONOR03_PER_INDEX_EXACT",
            base=base,
            donor=donor03,
            object_chunk=chunk,
            cdb=v1.read_internal_file(donor03.path, "ROOT.CDB"),
            specs=donor_specs,
            maps=maps,
            counts=counts,
            notes="Rebuild donor03 object chunk from explicit per-index slices. This should be byte-identical to donor03.",
            donor_chunk=templates.donor_chunk,
        )
    )

    chunk, maps, counts = _build_three_chunk_from_donor_shape(templates, renamed_donor_specs, mutate_text=True)
    manifests.append(
        _write_case(
            "IND_V3_T02_THREE_RENAMED_DONOR_GEOMETRY",
            base=base,
            donor=donor03,
            object_chunk=chunk,
            cdb=v1._build_cdb(renamed_donor_specs),
            specs=renamed_donor_specs,
            maps=maps,
            counts=counts,
            notes="Rename refs and terminal labels while preserving donor03 per-index geometry and suffix bytes.",
            donor_chunk=templates.donor_chunk,
        )
    )

    chunk, maps, counts = _build_three_chunk_from_donor_shape(templates, donor_translated_specs, dx=2540000, dy=508000, mutate_text=True)
    manifests.append(
        _write_case(
            "IND_V3_T03_THREE_RIGID_TRANSLATED_DONOR_GEOMETRY",
            base=base,
            donor=donor03,
            object_chunk=chunk,
            cdb=v1._build_cdb(donor_translated_specs),
            specs=donor_translated_specs,
            maps=maps,
            counts=counts,
            notes="Translate every donor03 coordinate by the same offset while preserving relative geometry and suffix bytes.",
            donor_chunk=templates.donor_chunk,
        )
    )

    chunk, maps, counts = _build_three_chunk_from_donor_shape(templates, renamed_translated_specs, dx=2540000, dy=508000, mutate_text=True)
    manifests.append(
        _write_case(
            "IND_V3_T04_THREE_RENAMED_RIGID_TRANSLATED",
            base=base,
            donor=donor03,
            object_chunk=chunk,
            cdb=v1._build_cdb(renamed_translated_specs),
            specs=renamed_translated_specs,
            maps=maps,
            counts=counts,
            notes="Rename refs/labels and rigid-translate donor03 geometry. This is the candidate general multi-inductor method.",
            donor_chunk=templates.donor_chunk,
        )
    )

    chunk, maps, counts = _build_three_chunk_formula_fixed_suffix(v1_templates, templates, donor_specs)
    manifests.append(
        _write_case(
            "IND_V3_T05_FORMULA_COORDS_FIXED_INDEX_SUFFIX",
            base=base,
            donor=donor03,
            object_chunk=chunk,
            cdb=v1._build_cdb(donor_specs),
            specs=donor_specs,
            maps=maps,
            counts=counts,
            notes="Same style as failed V2 T7, but fixes the L2 REALIND template/suffix issue. This tests whether recomputed multi geometry is also unsafe.",
            donor_chunk=templates.donor_chunk,
        )
    )

    summary = {
        "case": "INDUCTOR_V3_MULTI_TEMP_2026_05_31",
        "status": "awaiting_user_proteus_test",
        "method": "per-index REALIND suffix preservation plus donor-relative geometry diagnostics",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V3 multi-inductor diagnostic pack.\n\nOpen in this order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(manifests, 1))
        + "\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(REPO_ROOT / "experiments" / "INDUCTOR_V3_MULTI_TEMP_2026_05_31"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
