"""Generate final-test mixed R/C/L 6, 21, and 15 topology pack.

V16 confirmed repeated full R/C/L units. V17 confirmed the intended direction
for uneven counts: remove whole C/L/R subgroups from accepted units. This V18
pack uses the same subgroup method to build the requested final-test set:

* one 6-component mixed circuit
* one 21-component mixed circuit
* fifteen named topology circuits

Do not promote this code until the user accepts the generated Proteus projects.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_passive as mp
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "experiments" / "mixed_rcl_v18_final_topology_temp_2026_06_02"
V17_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-02" / "generate_mixed_rcl_v17_component_removal_temp.py"

Mode = Literal["RCL", "RC", "LC", "RL", "C"]


@dataclass(frozen=True)
class Group:
    mode: Mode
    start: str
    end: str


def G(mode: Mode, start: str, end: str) -> Group:
    return Group(mode=mode, start=start, end=end)


def _load_v17() -> Any:
    spec = importlib.util.spec_from_file_location("mixed_rcl_v17_for_v18", V17_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V17 helper module from {V17_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v17 = _load_v17()
v16 = v17.v16


def _included(mode: Mode) -> tuple[str, ...]:
    return v17._included_components(mode)


def _last_group(mode: Mode) -> str:
    return v17._last_emitted_group(mode)


def _two(prefix: str, index: int) -> str:
    return v16._two_char(prefix, index)


def _make_specs(group: Group, unit_index: int, ids: dict[str, int], ref_counts: dict[str, int]) -> dict[str, Any]:
    dummy = {kind: ids.get(kind, 240 + "CLR".index(kind)) for kind in "CLR"}
    cap, ind, res = v16._unit_specs(unit_index, global_ids=(dummy["C"], dummy["L"], dummy["R"]))
    internal_1 = _two("A", unit_index)
    internal_2 = _two("B", unit_index)

    def with_ref(spec: Any, kind: str, left: str, right: str) -> Any:
        ref_counts[kind] += 1
        prefix = {"C": "C", "L": "L", "R": "R"}[kind]
        ref = _two(prefix, ref_counts[kind])
        return replace(spec, idx=ids[kind], ref=ref, source_ref=ref, left=left, right=right)

    if group.mode == "RCL":
        return {
            "R": with_ref(res, "R", group.start, internal_1),
            "C": with_ref(cap, "C", internal_1, internal_2),
            "L": with_ref(ind, "L", internal_2, group.end),
        }
    if group.mode == "RC":
        return {
            "R": with_ref(res, "R", group.start, internal_1),
            "C": with_ref(cap, "C", internal_1, group.end),
        }
    if group.mode == "LC":
        return {
            "C": with_ref(cap, "C", group.start, internal_1),
            "L": with_ref(ind, "L", internal_1, group.end),
        }
    if group.mode == "RL":
        return {
            "R": with_ref(res, "R", group.start, internal_1),
            "L": with_ref(ind, "L", internal_1, group.end),
        }
    if group.mode == "C":
        return {"C": with_ref(cap, "C", group.start, group.end)}
    raise ValueError(group.mode)


def _ids_for_groups(groups: list[Group]) -> list[dict[str, int]]:
    next_id = 1
    out: list[dict[str, int]] = []
    for group in groups:
        ids: dict[str, int] = {}
        # ID order must follow object-emission order, not electrical order.
        for kind in _included(group.mode):
            ids[kind] = next_id
            next_id += 1
        out.append(ids)
    return out


def _patch_cap(slot: Any, spec: Any, suffixes: dict[str, int], *, final: bool) -> bytes:
    cap_dx = spec.x - v16._s32(slot.cap_record, 332)
    cap_dy = spec.y - v16._s32(slot.cap_record, 336)
    marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    cap_output = mp._patch_cap_output(slot.cap_output, spec.right, cap_dx, cap_dy, suffixes["cap_out"], marker)
    cap_input = mp._patch_cap_input(slot.cap_input, spec.left, cap_dx, cap_dy, suffixes["cap_in"])
    cap_record = mp._patch_cap_record(
        slot.cap_record,
        spec,
        spec.visible_value,
        spec.x,
        spec.y,
        spec.idx,
        suffixes["cap_in"],
        suffixes["cap_out"],
    )
    cap_wire_left = v17._wire_with_optional_final(
        slot.cap_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    cap_wire_right = v17._wire_with_optional_final(
        slot.cap_wire_right,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return cap_output + cap_input + cap_record + cap_wire_left + cap_wire_right


def _patch_l_body(slot: Any, spec: Any, suffixes: dict[str, int], *, final: bool) -> bytes:
    marker = b"$TERGROUND" if spec.right == "G0" else b"$TEROUTPUT"
    l_output = v16._patch_ind_output(slot.l_output, spec.right, spec.idx, spec.x, spec.y, marker, suffixes["l_out"])
    l_inductor = v16._patch_inductor(slot.l_inductor, spec, spec.idx, suffixes["l_in"], suffixes["l_out"])
    l_wire_left = v17._wire_with_optional_final(
        slot.l_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    l_wire_right = v17._wire_with_optional_final(
        slot.l_wire_right,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return l_output + l_inductor + l_wire_left + l_wire_right


def _patch_group(
    *,
    group: Group,
    unit_index: int,
    is_final: bool,
    templates: Any,
    ids: dict[str, int],
    ref_counts: dict[str, int],
) -> tuple[bytes, list[Any], list[dict[str, Any]]]:
    slot = templates.units[(unit_index - 1) % len(templates.units)]
    suffixes = v16._suffixes(unit_index)
    specs = _make_specs(group, unit_index, ids, ref_counts)
    final_kind = _last_group(group.mode) if is_final else ""
    parts: list[bytes] = []
    emitted: list[Any] = []
    topology: list[dict[str, Any]] = []

    if "C" in specs:
        parts.append(_patch_cap(slot, specs["C"], suffixes, final=final_kind == "C"))
        emitted.append(specs["C"])
        topology.append(v17._topology_row("C", unit_index, specs["C"], suffixes))
    if "L" in specs:
        parts.append(v16._patch_ind_input(slot.l_input, specs["L"].left, specs["L"].idx, specs["L"].x, specs["L"].y, suffixes["l_in"]))
    if "R" in specs:
        parts.append(v16._patch_ind_input(slot.r_input, specs["R"].left, specs["R"].idx, specs["R"].x, specs["R"].y, suffixes["r_in"]))
    if "L" in specs:
        parts.append(_patch_l_body(slot, specs["L"], suffixes, final=final_kind == "L"))
        emitted.append(specs["L"])
        topology.append(v17._topology_row("L", unit_index, specs["L"], suffixes))
    if "R" in specs:
        parts.append(v17._patch_r_body(slot, specs["R"], templates, specs["R"].idx, suffixes, final=final_kind == "R"))
        emitted.append(specs["R"])
        topology.append(v17._topology_row("R", unit_index, specs["R"], suffixes))
    return b"".join(parts), emitted, topology


def _build_chunk(templates: Any, groups: list[Group]) -> tuple[bytes, list[Any], list[dict[str, Any]], dict[str, Any]]:
    ids_by_group = _ids_for_groups(groups)
    ref_counts = {"C": 0, "L": 0, "R": 0}
    chunks: list[bytes] = []
    specs: list[Any] = []
    topology: list[dict[str, Any]] = []
    for unit_index, (group, ids) in enumerate(zip(groups, ids_by_group, strict=True), start=1):
        chunk, group_specs, group_topology = _patch_group(
            group=group,
            unit_index=unit_index,
            is_final=unit_index == len(groups),
            templates=templates,
            ids=ids,
            ref_counts=ref_counts,
        )
        chunks.append(chunk)
        specs.extend(group_specs)
        topology.extend(group_topology)
    object_chunk = bytearray(templates.header + templates.bridge_core + b"".join(chunks))
    object_chunk[-1] = 0xFF
    counts = {
        "object_order": "header, V0 bridge, accepted V17 subgroup-removal groups",
        "group_modes": [group.mode for group in groups],
        "group_count": len(groups),
        "component_count": len(specs),
        "capacitor_count": sum(1 for item in specs if item.kind == "CAPACITOR"),
        "inductor_count": sum(1 for item in specs if item.kind == "INDUCTOR"),
        "resistor_count": sum(1 for item in specs if item.kind == "RESISTOR"),
        "power_bridge_count": 1,
        "ground_terminal_count": _marker_counts(bytes(object_chunk))["$TERGROUND"],
    }
    return bytes(object_chunk), specs, topology, counts


def _marker_counts(data: bytes) -> dict[str, int]:
    return v16._marker_counts(data)


def _validate_chunk(chunk: bytes, specs: list[Any], topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues = v17._scan_wire_issues(chunk)
    actual = _marker_counts(chunk)
    expected = {
        "CAPACITOR": counts["capacitor_count"],
        "CAP10": counts["capacitor_count"],
        "REALIND": counts["inductor_count"] * 3,
        "RESISTOR": counts["resistor_count"] * 2,
        "COMPONENT ID": counts["component_count"],
        "COMPONENT VALUE": counts["component_count"],
    }
    for marker, want in expected.items():
        if actual[marker] != want:
            issues.append(f"{marker} count {actual[marker]} != {want}")
    if not chunk or chunk[0] != 0:
        issues.append("object chunk does not start with 00")
    if not chunk or chunk[-1] != 0xFF:
        issues.append("object chunk does not end with FF")
    if len({spec.ref for spec in specs}) != len(specs):
        issues.append("component refs are not unique")
    if len({spec.idx for spec in specs}) != len(specs):
        issues.append("component global IDs are not unique")
    if len({item["in_suffix"] for item in topology}) != len(topology):
        issues.append("input suffixes are not unique")
    if len({item["out_suffix"] for item in topology}) != len(topology):
        issues.append("output suffixes are not unique")
    return issues


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _payload(case_id: str, specs: list[Any], counts: dict[str, Any], topology: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = list(dict.fromkeys(node for spec in specs for node in (spec.left, spec.right)))
    return {
        "schema_version": "mixed-rcl-temp/v18-final-topology",
        "generator_target": "proteus-8.13-mixed-rcl-final-testing",
        "case_id": case_id,
        "nodes": [{"id": node, "kind": _node_kind(node)} for node in nodes],
        "components": [
            {
                "idx": spec.idx,
                "ref": spec.ref,
                "type": spec.kind,
                "value": spec.value,
                "nodes": [spec.left, spec.right],
                "visual": {"x": spec.x, "y": spec.y},
            }
            for spec in sorted(specs, key=lambda item: item.idx)
        ],
        "metadata": {
            "temporary": True,
            "group_modes": counts["group_modes"],
            "object_order": counts["object_order"],
            "topology": sorted(topology, key=lambda item: item["idx"]),
        },
    }


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    templates: Any,
    groups: list[Group],
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, specs, topology, counts = _build_chunk(templates, groups)
    cdb = v16._build_rcl_cdb(specs)
    dsn, pointers = rv9.build_dsn(read_internal_file(base_project, "ROOT.DSN"), read_internal_file(donor_project, "ROOT.DSN"), object_chunk)
    dsn = patch_root_dsn_version(dsn, PROTEUS_813)
    project_xml = patch_project_xml_version(read_internal_file(base_project, "PROJECT.XML"), PROTEUS_813)
    output_path = case_dir / f"{case_id}.pdsprj"
    cdb_path = case_dir / f"{case_id}.ROOT.CDB.bin"
    dsn_path = case_dir / f"{case_id}.ROOT.DSN.bin"
    chunk_path = case_dir / f"{case_id}.OBJECT_CHUNK.bin"
    write_project_from_parts(base_project, output_path, {"PROJECT.XML": project_xml, "ROOT.DSN": dsn, "ROOT.CDB": cdb})
    cdb_path.write_bytes(cdb)
    dsn_path.write_bytes(dsn)
    chunk_path.write_bytes(object_chunk)
    issues = _validate_chunk(object_chunk, specs, topology, counts)
    if rv9._extract_object_chunk(dsn) != object_chunk:
        issues.append("ROOT.DSN object chunk differs from requested chunk")
    manifest = {
        "case_id": case_id,
        "status": "temporary_mixed_rcl_v18_final_topology_not_locked",
        "description": description,
        "component_count": counts["component_count"],
        "resistor_count": counts["resistor_count"],
        "capacitor_count": counts["capacitor_count"],
        "inductor_count": counts["inductor_count"],
        "group_modes": counts["group_modes"],
        "ground_terminal_count": counts["ground_terminal_count"],
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(cdb),
        "root_dsn_len": len(dsn),
        "marker_counts": _marker_counts(object_chunk),
        "section_pointer_values": pointers,
        "topology": sorted(topology, key=lambda item: item["idx"]),
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
    (case_dir / "input.json").write_text(json.dumps(_payload(case_id, specs, counts, topology), indent=2) + "\n", encoding="utf-8")
    (case_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{case_id}\n\n{description}\n\n"
        f"Counts: {counts['resistor_count']}R / {counts['capacitor_count']}C / {counts['inductor_count']}L\n"
        f"Groups: {', '.join(counts['group_modes'])}\n"
        f"Static validation issues: {issues}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")
    return manifest


def _cases() -> list[tuple[str, str, list[Group]]]:
    return [
        ("RCL_V18_T01_6_COMPONENT_MIXED", "Six-component mixed circuit using RCL + RC + C.", [G("RCL", "V0", "G0"), G("RC", "V0", "G0"), G("C", "V0", "G0")]),
        ("RCL_V18_T02_21_COMPONENT_MIXED", "Twenty-one-component mixed circuit using seven accepted full RCL units.", [G("RCL", "V0", "G0") for _ in range(7)]),
        ("RCL_V18_T03_01_SIMPLE_LOOP", "Simple loop: one RCL path from power to ground.", [G("RCL", "V0", "G0")]),
        ("RCL_V18_T04_02_SERIES_CIRCUIT", "Series circuit: RC section followed by RCL section.", [G("RC", "V0", "N1"), G("RCL", "N1", "G0")]),
        ("RCL_V18_T05_03_PARALLEL_CIRCUIT", "Parallel circuit: RCL, RC, and LC branches between power and ground.", [G("RCL", "V0", "G0"), G("RC", "V0", "G0"), G("LC", "V0", "G0")]),
        ("RCL_V18_T06_04_SERIES_PARALLEL_COMBO", "Series-parallel combo: RC section feeding parallel RCL and LC branches.", [G("RC", "V0", "N1"), G("RCL", "N1", "G0"), G("LC", "N1", "G0")]),
        ("RCL_V18_T07_05_BASIC_VOLTAGE_DIVIDER", "Basic divider: RL upper section and RC lower section with midpoint N1.", [G("RL", "V0", "N1"), G("RC", "N1", "G0")]),
        ("RCL_V18_T08_06_MULTI_STEP_VOLTAGE_DIVIDER", "Multi-step divider: RL, RC, and LC sections creating N1 and N2 taps.", [G("RL", "V0", "N1"), G("RC", "N1", "N2"), G("LC", "N2", "G0")]),
        ("RCL_V18_T09_07_CURRENT_DIVIDER", "Current divider: several parallel mixed paths from V0 to G0.", [G("RC", "V0", "G0"), G("RCL", "V0", "G0"), G("C", "V0", "G0"), G("LC", "V0", "G0")]),
        ("RCL_V18_T10_08_DELTA_NETWORK", "Delta network using V0, N1, and G0 as triangle vertices.", [G("RL", "V0", "N1"), G("RC", "N1", "G0"), G("LC", "G0", "V0")]),
        ("RCL_V18_T11_09_STAR_Y_NETWORK", "Star network with central node N1 and three mixed outer arms.", [G("RL", "N1", "V0"), G("RC", "N1", "G0"), G("LC", "N1", "N2")]),
        ("RCL_V18_T12_10_DELTA_TO_STAR_SETUP", "Delta-to-star setup with mixed delta and star sides for comparison.", [G("RL", "V0", "N1"), G("RC", "N1", "G0"), G("LC", "G0", "V0"), G("RL", "N2", "V0"), G("RC", "N2", "G0"), G("LC", "N2", "N1")]),
        ("RCL_V18_T13_11_WHEATSTONE_BRIDGE", "Wheatstone bridge: two mixed side branches and a bridge between N1 and N2.", [G("RC", "V0", "N1"), G("LC", "N1", "G0"), G("RL", "V0", "N2"), G("RCL", "N2", "G0"), G("LC", "N1", "N2")]),
        ("RCL_V18_T14_12_BALANCED_WHEATSTONE_BRIDGE", "Balanced Wheatstone bridge with symmetric mixed side branches.", [G("RC", "V0", "N1"), G("LC", "N1", "G0"), G("RC", "V0", "N2"), G("LC", "N2", "G0"), G("RL", "N1", "N2")]),
        ("RCL_V18_T15_13_UNBALANCED_WHEATSTONE_BRIDGE", "Unbalanced Wheatstone bridge with a heavier lower-right RCL section.", [G("RC", "V0", "N1"), G("LC", "N1", "G0"), G("RL", "V0", "N2"), G("RCL", "N2", "G0"), G("RC", "N1", "N2")]),
        ("RCL_V18_T16_14_H_BRIDGE_RESISTOR_VERSION", "H-bridge style network with two mixed vertical branches and one cross bridge.", [G("RC", "V0", "N1"), G("LC", "N1", "G0"), G("RL", "V0", "N2"), G("RCL", "N2", "G0"), G("LC", "N1", "N2")]),
        ("RCL_V18_T17_15_R_2R_LADDER_NETWORK", "R-2R-style ladder topology using repeated mixed series sections and LC shunts.", [G("RL", "V0", "N1"), G("LC", "N1", "G0"), G("RC", "N1", "N2"), G("LC", "N2", "G0"), G("RL", "N2", "N3"), G("LC", "N3", "G0"), G("RC", "N3", "G0")]),
    ]


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base = registry.get("e001_empty").path
    donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v16._load_rcl_unit_templates(donor)

    cases: list[dict[str, Any]] = []
    for case_id, description, groups in _cases():
        cases.append(_write_case(case_id=case_id, description=description, base_project=base, donor_project=donor, templates=templates, groups=groups))

    summary = {
        "batch_id": "MIXED_RCL_V18_FINAL_TOPOLOGY_STATIC_20260602",
        "status": "static_generated_awaiting_user_final_proteus_test",
        "source_feedback": "User reported all V17 component-removal cases worked. V18 applies that accepted method to 6-component, 21-component, and 15 named topology final-test cases.",
        "method": "Use accepted V17 subgroup-removal groups, marker-relative WIRE coordinates, unique global DSN/CDB IDs, and E001 as base.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "component_count": item["component_count"],
                "resistor_count": item["resistor_count"],
                "capacitor_count": item["capacitor_count"],
                "inductor_count": item["inductor_count"],
                "group_modes": item["group_modes"],
                "object_chunk_len": item["object_chunk_len"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V18 final topology test pack.\n\nOpen and run netlist/simulation in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(cases, 1))
        + "\n\nT01 is the 6-component case. T02 is the 21-component case. T03-T17 are the 15 requested topology cases.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(REPO_ROOT / "experiments" / "MIXED_RCL_V18_FINAL_TOPOLOGY_TEMP_2026_06_02"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "case_count": len(cases), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
