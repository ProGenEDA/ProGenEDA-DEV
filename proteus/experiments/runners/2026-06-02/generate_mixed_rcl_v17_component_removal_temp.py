"""Generate mixed R/C/L component-removal diagnostics from accepted V16 units.

V16 user feedback accepted repeated full R/C/L units after fixing marker-relative
WIRE coordinate patching. This pack tests the next boundary requested by the
user: remove whole component subgroups from accepted units to produce RC, RL,
LC, and C-only branches, then emit a 3R/4C/1L project.

Do not promote this code until Proteus open/netlist feedback accepts these
removal cases.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "proteus" / "active" / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_passive as mp
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts
from proteusgen.templates import FixtureRegistry
from proteusgen.versioning import PROTEUS_813, patch_project_xml_version, patch_root_dsn_version

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "mixed_rcl_v17_component_removal_temp_2026_06_02"
V16_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-01" / "generate_mixed_rcl_v16_wire_offset_fix_temp.py"

BranchMode = Literal["RCL", "RC", "LC", "RL", "C"]


def _load_v16() -> Any:
    spec = importlib.util.spec_from_file_location("mixed_rcl_v16_for_v17", V16_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V16 helper module from {V16_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v16 = _load_v16()


def _marker_counts(data: bytes) -> dict[str, int]:
    return v16._marker_counts(data)


def _included_components(mode: BranchMode) -> tuple[str, ...]:
    if mode == "RCL":
        return ("C", "L", "R")
    if mode == "RC":
        return ("C", "R")
    if mode == "LC":
        return ("C", "L")
    if mode == "RL":
        return ("L", "R")
    if mode == "C":
        return ("C",)
    raise ValueError(mode)


def _last_emitted_group(mode: BranchMode) -> str:
    # Emission order follows the donor: C group, then L input/R input,
    # then L body, then R body.
    if "R" in _included_components(mode):
        return "R"
    if "L" in _included_components(mode):
        return "L"
    return "C"


def _component_ids_for_branches(branches: list[BranchMode]) -> list[dict[str, int]]:
    next_id = 1
    out: list[dict[str, int]] = []
    for mode in branches:
        ids: dict[str, int] = {}
        for kind in _included_components(mode):
            ids[kind] = next_id
            next_id += 1
        out.append(ids)
    return out


def _with_id_or_gap(ids: dict[str, int], kind: str) -> int:
    # Missing components still need a placeholder to build the sibling specs.
    return ids.get(kind, 240 + "CLR".index(kind))


def _branch_specs(mode: BranchMode, unit_index: int, ids: dict[str, int]) -> dict[str, Any]:
    cap, ind, res = v16._unit_specs(
        unit_index,
        global_ids=(
            _with_id_or_gap(ids, "C"),
            _with_id_or_gap(ids, "L"),
            _with_id_or_gap(ids, "R"),
        ),
    )
    node_a = v16._two_char("A", unit_index)
    node_b = v16._two_char("B", unit_index)

    if mode == "RCL":
        return {"C": cap, "L": ind, "R": res}
    if mode == "RC":
        return {"C": replace(cap, right="G0"), "R": res}
    if mode == "LC":
        return {"C": replace(cap, left="V0", right=node_b), "L": ind}
    if mode == "RL":
        return {"L": replace(ind, left=node_a), "R": res}
    if mode == "C":
        return {"C": replace(cap, left="V0", right="G0")}
    raise ValueError(mode)


def _wire_with_optional_final(template: bytes, x1: int, y1: int, x2: int, y2: int, *, final: bool) -> bytes:
    record = template
    if final and len(record) == v16.WIRE_TRIMMED_SIZE:
        record += b"\x00"
    if not final and len(record) == v16.WIRE_SIZE + 1:
        record = record[:-1]
    if final and len(record) == v16.WIRE_SIZE:
        # This byte is overwritten to FF by the marker-relative patch helper.
        pass
    return v16._patch_wire_keep_length(record, x1, y1, x2, y2, final=final)


def _patch_cap_group(
    slot: Any,
    spec: Any,
    global_id: int,
    suffixes: dict[str, int],
    *,
    final: bool,
) -> bytes:
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
        global_id,
        suffixes["cap_in"],
        suffixes["cap_out"],
    )
    cap_wire_left = _wire_with_optional_final(
        slot.cap_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    cap_wire_right = _wire_with_optional_final(
        slot.cap_wire_right,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return cap_output + cap_input + cap_record + cap_wire_left + cap_wire_right


def _patch_l_input(slot: Any, spec: Any, global_id: int, suffixes: dict[str, int]) -> bytes:
    return v16._patch_ind_input(slot.l_input, spec.left, global_id, spec.x, spec.y, suffixes["l_in"])


def _patch_l_body(slot: Any, spec: Any, global_id: int, suffixes: dict[str, int], *, final: bool) -> bytes:
    l_output = v16._patch_ind_output(
        slot.l_output,
        spec.right,
        global_id,
        spec.x,
        spec.y,
        b"$TERGROUND",
        suffixes["l_out"],
    )
    l_inductor = v16._patch_inductor(slot.l_inductor, spec, global_id, suffixes["l_in"], suffixes["l_out"])
    l_wire_left = _wire_with_optional_final(
        slot.l_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    l_wire_right = _wire_with_optional_final(
        slot.l_wire_right,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return l_output + l_inductor + l_wire_left + l_wire_right


def _patch_r_input(slot: Any, spec: Any, global_id: int, suffixes: dict[str, int]) -> bytes:
    return v16._patch_ind_input(slot.r_input, spec.left, global_id, spec.x, spec.y, suffixes["r_in"])


def _patch_r_body(slot: Any, spec: Any, templates: Any, global_id: int, suffixes: dict[str, int], *, final: bool) -> bytes:
    r_output = v16._patch_ind_output(
        slot.r_output,
        spec.right,
        global_id,
        spec.x,
        spec.y,
        b"$TEROUTPUT",
        suffixes["r_out"],
    )
    r_resistor = v16._patch_native_resistor(slot.r_resistor, spec, global_id, suffixes["r_in"], suffixes["r_out"])
    final_wire_template = templates.units[-1].r_wire_right if final else slot.r_wire_right
    if not final and len(final_wire_template) == v16.WIRE_SIZE + 1:
        final_wire_template = final_wire_template[:-1]
    if final and len(final_wire_template) == v16.WIRE_SIZE:
        final_wire_template += b"\x00"
    r_wire_left = _wire_with_optional_final(
        slot.r_wire_left,
        spec.x - 762000,
        spec.y,
        spec.x - 762000,
        spec.y,
        final=False,
    )
    r_wire_right = _wire_with_optional_final(
        final_wire_template,
        spec.x + 1016000,
        spec.y,
        spec.x + 762000,
        spec.y,
        final=final,
    )
    return r_output + slot.r_resistor_prefix + r_resistor + r_wire_left + r_wire_right


def _topology_row(kind: str, unit_index: int, spec: Any, suffixes: dict[str, int]) -> dict[str, Any]:
    in_key = {"C": "cap_in", "L": "l_in", "R": "r_in"}[kind]
    out_key = {"C": "cap_out", "L": "l_out", "R": "r_out"}[kind]
    return {
        "idx": spec.idx,
        "unit": unit_index,
        "kind": spec.kind,
        "ref": spec.ref,
        "value": spec.value,
        "left": spec.left,
        "right": spec.right,
        "global_id": spec.idx,
        "in_suffix": f"{suffixes[in_key]:04x}",
        "out_suffix": f"{suffixes[out_key]:04x}",
        "x": spec.x,
        "y": spec.y,
    }


def _patch_branch(
    *,
    mode: BranchMode,
    unit_index: int,
    is_final_branch: bool,
    templates: Any,
    ids: dict[str, int],
) -> tuple[bytes, list[Any], list[dict[str, Any]]]:
    slot = templates.units[(unit_index - 1) % len(templates.units)]
    suffixes = v16._suffixes(unit_index)
    specs = _branch_specs(mode, unit_index, ids)
    final_group = _last_emitted_group(mode) if is_final_branch else ""

    parts: list[bytes] = []
    emitted_specs: list[Any] = []
    topology: list[dict[str, Any]] = []

    if "C" in specs:
        parts.append(_patch_cap_group(slot, specs["C"], ids["C"], suffixes, final=final_group == "C"))
        emitted_specs.append(specs["C"])
        topology.append(_topology_row("C", unit_index, specs["C"], suffixes))
    if "L" in specs:
        parts.append(_patch_l_input(slot, specs["L"], ids["L"], suffixes))
    if "R" in specs:
        parts.append(_patch_r_input(slot, specs["R"], ids["R"], suffixes))
    if "L" in specs:
        parts.append(_patch_l_body(slot, specs["L"], ids["L"], suffixes, final=final_group == "L"))
        emitted_specs.append(specs["L"])
        topology.append(_topology_row("L", unit_index, specs["L"], suffixes))
    if "R" in specs:
        parts.append(_patch_r_body(slot, specs["R"], templates, ids["R"], suffixes, final=final_group == "R"))
        emitted_specs.append(specs["R"])
        topology.append(_topology_row("R", unit_index, specs["R"], suffixes))

    return b"".join(parts), emitted_specs, topology


def _build_removed_chunk(templates: Any, branches: list[BranchMode]) -> tuple[bytes, list[Any], list[dict[str, Any]], dict[str, Any]]:
    ids_by_branch = _component_ids_for_branches(branches)
    chunks: list[bytes] = []
    specs: list[Any] = []
    topology: list[dict[str, Any]] = []
    for unit_index, (mode, ids) in enumerate(zip(branches, ids_by_branch, strict=True), start=1):
        chunk, branch_specs, branch_topology = _patch_branch(
            mode=mode,
            unit_index=unit_index,
            is_final_branch=unit_index == len(branches),
            templates=templates,
            ids=ids,
        )
        chunks.append(chunk)
        specs.extend(branch_specs)
        topology.extend(branch_topology)
    object_chunk = bytearray(templates.header + templates.bridge_core + b"".join(chunks))
    object_chunk[-1] = 0xFF
    counts = {
        "object_order": "header, V0 bridge, donor-order units with whole C/L/R subgroups removed",
        "branch_modes": branches,
        "unit_count": len(branches),
        "component_count": len(specs),
        "capacitor_count": sum(1 for item in specs if item.kind == "CAPACITOR"),
        "inductor_count": sum(1 for item in specs if item.kind == "INDUCTOR"),
        "resistor_count": sum(1 for item in specs if item.kind == "RESISTOR"),
        "power_bridge_count": 1,
        "ground_terminal_count": _marker_counts(bytes(object_chunk))["$TERGROUND"],
    }
    return bytes(object_chunk), specs, topology, counts


def _node_kind(node: str) -> str:
    if node == "V0":
        return "power"
    if node == "G0":
        return "ground"
    return "internal"


def _payload(case_id: str, specs: list[Any], counts: dict[str, Any], topology: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = list(dict.fromkeys(node for spec in specs for node in (spec.left, spec.right)))
    return {
        "schema_version": "mixed-rcl-temp/v17-component-removal",
        "generator_target": "proteus-8.13-mixed-rcl-component-removal-diagnostic",
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
            "branch_modes": counts["branch_modes"],
            "object_order": counts["object_order"],
            "topology": sorted(topology, key=lambda item: item["idx"]),
        },
    }


def _scan_wire_issues(chunk: bytes) -> list[str]:
    issues: list[str] = []
    pos = 0
    while True:
        marker = chunk.find(b"WIRE", pos)
        if marker < 0:
            return issues
        coord_start = marker + 9
        if coord_start + 16 > len(chunk):
            issues.append(f"WIRE coordinate window exceeds stream at marker {marker}")
            return issues
        for offset in range(coord_start, coord_start + 16, 4):
            value = int.from_bytes(chunk[offset : offset + 4], "little", signed=True)
            if abs(value) > 80_000_000:
                issues.append(f"implausible WIRE coordinate {value} at offset {offset}")
        pos = marker + 4


def _validate_chunk(chunk: bytes, specs: list[Any], topology: list[dict[str, Any]], counts: dict[str, Any]) -> list[str]:
    issues = _scan_wire_issues(chunk)
    actual = _marker_counts(chunk)
    if actual["CAPACITOR"] != counts["capacitor_count"]:
        issues.append(f"CAPACITOR count {actual['CAPACITOR']} != {counts['capacitor_count']}")
    if actual["CAP10"] != counts["capacitor_count"]:
        issues.append(f"CAP10 count {actual['CAP10']} != {counts['capacitor_count']}")
    if actual["REALIND"] != counts["inductor_count"] * 3:
        issues.append(f"REALIND count {actual['REALIND']} != {counts['inductor_count'] * 3}")
    if actual["RESISTOR"] != counts["resistor_count"] * 2:
        issues.append(f"RESISTOR count {actual['RESISTOR']} != {counts['resistor_count'] * 2}")
    if actual["COMPONENT ID"] != counts["component_count"]:
        issues.append(f"COMPONENT ID count {actual['COMPONENT ID']} != {counts['component_count']}")
    if actual["COMPONENT VALUE"] != counts["component_count"]:
        issues.append(f"COMPONENT VALUE count {actual['COMPONENT VALUE']} != {counts['component_count']}")
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


def _write_case(
    *,
    case_id: str,
    description: str,
    base_project: Path,
    donor_project: Path,
    templates: Any,
    branches: list[BranchMode],
    expected_result: str,
) -> dict[str, Any]:
    case_dir = OUT_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    object_chunk, specs, topology, counts = _build_removed_chunk(templates, branches)
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
        "status": "temporary_mixed_rcl_v17_component_removal_not_locked",
        "description": description,
        "expected_result": expected_result,
        "branch_modes": branches,
        "component_count": counts["component_count"],
        "resistor_count": counts["resistor_count"],
        "capacitor_count": counts["capacitor_count"],
        "inductor_count": counts["inductor_count"],
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
        f"{case_id}\n\n{description}\n\nBranches: {', '.join(branches)}\n"
        f"Counts: {counts['resistor_count']}R / {counts['capacitor_count']}C / {counts['inductor_count']}L\n"
        f"Expected diagnostic meaning: {expected_result}\n"
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
    donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v16._load_rcl_unit_templates(donor)

    case_defs: list[tuple[str, str, list[BranchMode], str]] = [
        (
            "RCL_V17_T00_1X_FULL_RCL_CONTROL",
            "One full accepted V16-style RCL branch: V0 -> R -> C -> L -> G0.",
            ["RCL"],
            "Control. This should match the accepted one-unit V16 shape.",
        ),
        (
            "RCL_V17_T01_1X_RC_REMOVE_L",
            "One RC branch made by removing the L subgroup and converting the capacitor output terminal to G0.",
            ["RC"],
            "If this fails, removing L or grounding C output is unsafe.",
        ),
        (
            "RCL_V17_T02_1X_LC_REMOVE_R",
            "One LC branch made by removing the R subgroup and connecting C input to V0.",
            ["LC"],
            "If this fails, removing R from a C/L unit is unsafe.",
        ),
        (
            "RCL_V17_T03_1X_RL_REMOVE_C",
            "One RL branch made by removing the C subgroup and sharing R output/L input on A1.",
            ["RL"],
            "If this fails, removing C from a native unit is unsafe.",
        ),
        (
            "RCL_V17_T04_1X_C_ONLY_REMOVE_RL",
            "One capacitor-only branch between V0 and G0.",
            ["C"],
            "If this fails, ending a removed unit on a capacitor final wire is unsafe.",
        ),
        (
            "RCL_V17_T05_REQUESTED_3R_4C_1L",
            "Requested mixed count: one RCL branch, two RC branches, and one C-only branch, giving 3R/4C/1L.",
            ["RCL", "RC", "RC", "C"],
            "Target requested case. If controls pass and this fails, the issue is multi-branch subgroup removal.",
        ),
    ]

    cases: list[dict[str, Any]] = []
    for case_id, description, branches, expected in case_defs:
        cases.append(
            _write_case(
                case_id=case_id,
                description=description,
                base_project=base,
                donor_project=donor,
                templates=templates,
                branches=branches,
                expected_result=expected,
            )
        )

    summary = {
        "batch_id": "MIXED_RCL_V17_COMPONENT_REMOVAL_STATIC_20260602",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "source_feedback": "User reported all V16 wire-offset-fix cases worked and requested a 3R/4C/1L project by removing components from accepted full units.",
        "method": "Use accepted V16 full-unit templates, remove only whole C/L/R terminal-component-wire subgroups, and give the final kept subgroup a valid final FF wire terminator.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "branch_modes": item["branch_modes"],
                "component_count": item["component_count"],
                "resistor_count": item["resistor_count"],
                "capacitor_count": item["capacitor_count"],
                "inductor_count": item["inductor_count"],
                "object_chunk_len": item["object_chunk_len"],
                "marker_counts": item["marker_counts"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in cases
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V17 component-removal diagnostic pack.\n\nOpen and run netlist/simulation in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(cases, 1))
        + "\n\nT05 is the requested 3R/4C/1L circuit. T01-T04 isolate RC, LC, RL, and C-only removal before that target.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "MIXED_RCL_V17_COMPONENT_REMOVAL_TEMP_2026_06_02"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "case_count": len(cases), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
