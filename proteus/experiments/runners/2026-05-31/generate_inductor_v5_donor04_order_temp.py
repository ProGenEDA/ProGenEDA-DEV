"""Generate V5 inductor power/ground diagnostics using donor04 object order.

V4 failed because it prepended the generic passive power bridge before the
REALIND group. The accepted inductor power/ground donor uses a different order:

input terminal, REALIND, trimmed left wire, power terminal, output terminal,
bridge wire, ground terminal, final ground wire.
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
V1_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-05-31" / "generate_inductor_v1_terminal_temp.py"
V2_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-05-31" / "generate_inductor_v2_suffix_temp.py"


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

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "inductor_v5_donor04_order_temp_2026_05_31"


@dataclass(frozen=True)
class Donor04Templates:
    donor_chunk: bytes
    header: bytes
    input_terminal: bytes
    inductor: bytes
    wire_left_trimmed: bytes
    power_terminal: bytes
    power_output: bytes
    power_wire: bytes
    ground_terminal: bytes
    ground_wire_final: bytes


def _load_donor04_templates(project_path: Path) -> Donor04Templates:
    chunk = v1.rv9._extract_object_chunk(v1.read_internal_file(project_path, "ROOT.DSN"))
    if len(chunk) != 947:
        raise RuntimeError(f"Expected donor04 object chunk length 947, got {len(chunk)}.")
    return Donor04Templates(
        donor_chunk=chunk,
        header=chunk[0:1],
        input_terminal=chunk[1:104],
        inductor=chunk[104:478],
        wire_left_trimmed=chunk[478:527],
        power_terminal=chunk[527:630],
        power_output=chunk[630:734],
        power_wire=chunk[734:784],
        ground_terminal=chunk[784:888],
        ground_wire_final=chunk[888:947],
    )


def _patch_input(template: bytes, label: str) -> bytes:
    patched, _ = v1.rv9._patch_input(
        template,
        label,
        int.from_bytes(template[1:5], "little", signed=True),
        int.from_bytes(template[5:9], "little", signed=True),
        int.from_bytes(template[33:37], "little", signed=True),
        int.from_bytes(template[37:41], "little", signed=True),
        1,
        marker=b"$TERINPUT",
    )
    record = bytearray(patched)
    record[-4:] = template[-4:]
    return bytes(record)


def _patch_power(template: bytes, label: str) -> bytes:
    record = bytearray(template)
    if record.find(b"$TERPOWER") < 0:
        raise RuntimeError("Power terminal template marker not found.")
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError("Power label must be exactly two ASCII characters.")
    record[30] = 2
    record[31:33] = raw
    record[-4:] = template[-4:]
    return bytes(record)


def _patch_output(template: bytes, label: str, *, marker: bytes) -> bytes:
    record = bytearray(template)
    current_pos = record.find(b"$TEROUTPUT")
    if current_pos < 0:
        current_pos = record.find(b"$TERGROUND")
    if current_pos < 0:
        raise RuntimeError("Output/ground terminal template marker not found.")
    current_marker = b"$TEROUTPUT" if template[current_pos : current_pos + len(b"$TEROUTPUT")] == b"$TEROUTPUT" else b"$TERGROUND"
    if current_marker != marker:
        record[current_pos : current_pos + len(current_marker)] = marker
    raw = label.encode("ascii")
    if len(raw) != 2:
        raise ValueError("Output label must be exactly two ASCII characters.")
    record[31] = 2
    record[32:34] = raw
    record[-4:] = template[-4:]
    return bytes(record)


def _build_donor04_order_chunk(templates: Donor04Templates, spec: Any, *, internal_power_node: str, power_label: str = "V0", ground_label: str = "G0") -> bytes:
    inductor = v2._patch_inductor_preserve_suffix(
        templates.inductor,
        index=1,
        ref=spec.ref,
        value=spec.value,
        x=spec.x,
        y=spec.y,
    )
    out = bytearray(
        templates.header
        + _patch_input(templates.input_terminal, internal_power_node)
        + inductor
        + templates.wire_left_trimmed
        + _patch_power(templates.power_terminal, power_label)
        + _patch_output(templates.power_output, internal_power_node, marker=b"$TEROUTPUT")
        + templates.power_wire
        + _patch_output(templates.ground_terminal, ground_label, marker=b"$TERGROUND")
        + templates.ground_wire_final
    )
    out[-1] = 0xFF
    return bytes(out)


def _case_payload(name: str, spec: Any, internal_power_node: str, notes: str) -> dict[str, Any]:
    return {
        "case_id": name,
        "component": "INDUCTOR",
        "method": "temporary_inductor_v5_donor04_power_ground_order",
        "notes": notes,
        "power_label": "V0",
        "ground_label": "G0",
        "internal_power_connection_node": internal_power_node,
        "components": [spec.__dict__],
    }


def _write_case(
    name: str,
    *,
    base: Any,
    donor04: Any,
    object_chunk: bytes,
    cdb: bytes,
    spec: Any,
    internal_power_node: str,
    notes: str,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / name
    case_dir.mkdir(parents=True)
    dsn, section_pointers = v1.rv9.build_dsn(
        v1.read_internal_file(base.path, "ROOT.DSN"),
        v1.read_internal_file(donor04.path, "ROOT.DSN"),
        object_chunk,
    )
    dsn = v1.patch_root_dsn_version(dsn, v1.PROTEUS_813)
    project_xml = v1.patch_project_xml_version(v1.read_internal_file(base.path, "PROJECT.XML"), v1.PROTEUS_813)
    output_path = case_dir / f"{name}.pdsprj"
    v1.write_project_from_parts(base.path, output_path, {"PROJECT.XML": project_xml, "ROOT.CDB": cdb, "ROOT.DSN": dsn})
    (case_dir / f"{name}.ROOT.DSN.bin").write_bytes(dsn)
    (case_dir / f"{name}.ROOT.CDB.bin").write_bytes(cdb)
    (case_dir / "input.json").write_text(json.dumps(_case_payload(name, spec, internal_power_node, notes), indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open {name}.pdsprj in Proteus 8.13 first.\n\n{notes}\n", encoding="utf-8")
    counts = {
        "power_bridge_count": object_chunk.count(b"$TERPOWER"),
        "power_nodes": ["V0"],
        "ground_terminal_count": object_chunk.count(b"$TERGROUND"),
    }
    maps = [
        {
            "idx": 1,
            "ref": spec.ref,
            "value": spec.value,
            "left": "V0",
            "right": "G0",
            "input_marker": "$TERINPUT",
            "output_marker": "$TERGROUND",
            "internal_power_connection_node": internal_power_node,
            "object_order": "donor04",
            "x": spec.x,
            "y": spec.y,
        }
    ]
    manifest = {
        "case_id": name,
        "source": "inductor V5 donor04-order power/ground diagnostics",
        "notes": notes,
        "component_count": 1,
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
        "static_validation_issues": v1._validate_chunk(object_chunk, [spec], maps, counts),
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
    donor04 = registry.get("inductor_04_power_ground")
    templates = _load_donor04_templates(donor04.path)
    donor_spec = v1.InductorSpec("L1", "1mH", "V0", "G0", -7366000, 1270000)
    generated_same = v1.InductorSpec("L1", "1mH", "V0", "G0", -7366000, 1270000)
    renamed = v1.InductorSpec("LA", "1mH", "V0", "G0", -7366000, 1270000)
    renamed_value = v1.InductorSpec("LB", "2mH", "V0", "G0", -7366000, 1270000)
    exact_chunk = templates.donor_chunk
    manifests = [
        _write_case(
            "IND_V5_T01_E001_DONOR04_EXACT_CHUNK_CONTROL",
            base=base,
            donor04=donor04,
            object_chunk=exact_chunk,
            cdb=v1.read_internal_file(donor04.path, "ROOT.CDB"),
            spec=donor_spec,
            internal_power_node="N1",
            notes="Positive control: E001 base with exact donor04 object chunk and exact donor04 CDB.",
        ),
        _write_case(
            "IND_V5_T02_REBUILD_DONOR04_SLICES_EXACT",
            base=base,
            donor04=donor04,
            object_chunk=b"".join(
                [
                    templates.header,
                    templates.input_terminal,
                    templates.inductor,
                    templates.wire_left_trimmed,
                    templates.power_terminal,
                    templates.power_output,
                    templates.power_wire,
                    templates.ground_terminal,
                    templates.ground_wire_final,
                ]
            ),
            cdb=v1.read_internal_file(donor04.path, "ROOT.CDB"),
            spec=donor_spec,
            internal_power_node="N1",
            notes="Rebuild donor04 from explicit slices; should be byte-identical to donor04 object chunk.",
        ),
        _write_case(
            "IND_V5_T03_GENERATED_SAME_DONOR04_ORDER",
            base=base,
            donor04=donor04,
            object_chunk=_build_donor04_order_chunk(templates, generated_same, internal_power_node="N1"),
            cdb=v1._build_cdb([generated_same]),
            spec=generated_same,
            internal_power_node="N1",
            notes="Generated single V0/G0 inductor using donor04 object order and the original internal node label.",
        ),
        _write_case(
            "IND_V5_T04_RENAMED_REF_DONOR04_ORDER",
            base=base,
            donor04=donor04,
            object_chunk=_build_donor04_order_chunk(templates, renamed, internal_power_node="A1"),
            cdb=v1._build_cdb([renamed]),
            spec=renamed,
            internal_power_node="A1",
            notes="Rename the inductor ref and the internal power-bridge connection node while preserving donor04 order.",
        ),
        _write_case(
            "IND_V5_T05_RENAMED_VALUE_DONOR04_ORDER",
            base=base,
            donor04=donor04,
            object_chunk=_build_donor04_order_chunk(templates, renamed_value, internal_power_node="B1"),
            cdb=v1._build_cdb([renamed_value]),
            spec=renamed_value,
            internal_power_node="B1",
            notes="Rename ref, visible value, and internal power-bridge connection node while preserving donor04 order.",
        ),
    ]
    summary = {
        "case": "INDUCTOR_V5_DONOR04_ORDER_TEMP_2026_05_31",
        "status": "awaiting_user_proteus_test",
        "method": "single generated power/ground inductor using accepted donor04 object order",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V5 donor04-order diagnostic pack.\n\nOpen in this order:\n\n"
        + "\n".join(f"{idx}. {case['case_id']}/{case['case_id']}.pdsprj" for idx, case in enumerate(manifests, 1))
        + "\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "INDUCTOR_V5_DONOR04_ORDER_TEMP_2026_05_31"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
