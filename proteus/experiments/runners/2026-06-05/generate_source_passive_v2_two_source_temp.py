"""Generate two-source source-driven passive probes.

This temp batch follows SOURCE_PASSIVE_V1, which proved single-source passive
loads for R, C, L, RC, RL, and LC. V2 tests source multiplicity:

* two DC voltage sources
* two DC current sources
* one DC voltage source plus one DC current source
* two AC voltage sources

AC current remains intentionally out of scope.
"""

from __future__ import annotations

import hashlib
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

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import BASE_PROJECT, GENERATOR_TARGET, SCHEMA_VERSION  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V14_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-05" / "generate_dc_mixed_sources_v14_requested5_v13_method_temp.py"
ACV2_PATH = REPO_ROOT / "proteus" / "experiments" / "runners" / "2026-06-04" / "generate_ac_voltage_v2_nonfinal_source_unit_temp.py"

OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "source_passive_v2_two_source_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "proteus" / "experiments" / "runs" / "SOURCE_PASSIVE_V2_TWO_SOURCE_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V2_TWO_SOURCE_TEST_BATCH"

ARCHIVED_DONORS = {
    "dc_mixed_v14_donor": REPO_ROOT
    / "experiments"
    / "dc_mixed_sources_v14_requested5_v13_method_temp_2026_06_05"
    / "donors"
    / "rcl_v19_21_with_vsource_csource.pdsprj",
    "acv_variant_source": REPO_ROOT
    / "experiments"
    / "ac_voltage_v2_nonfinal_source_unit_temp_2026_06_04"
    / "donors"
    / "ac_voltage_02_variant.pdsprj",
    "acv_two_source": REPO_ROOT
    / "experiments"
    / "ac_voltage_v2_nonfinal_source_unit_temp_2026_06_04"
    / "donors"
    / "2xac_voltage_02_variant.pdsprj",
    "acv_source_load": REPO_ROOT
    / "experiments"
    / "ac_voltage_v2_nonfinal_source_unit_temp_2026_06_04"
    / "donors"
    / "ac_voltage_03_resistor_load.pdsprj",
}


@dataclass(frozen=True)
class TwoSourceCase:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    source_kind: str
    source_plans: tuple[Any, ...]
    visible_values: dict[str, str]
    exact_values: dict[str, str]


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v14 = _load_module("dc_mixed_v14_for_source_passive_v2", V14_PATH)
acv2 = _load_module("acv2_for_source_passive_v2", ACV2_PATH)
v13 = v14.v13


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _set_module_paths() -> None:
    for module in (v14, v14.v9, acv2, acv2.v1):
        if hasattr(module, "OUT_ROOT"):
            module.OUT_ROOT = OUT_ROOT
        if hasattr(module, "ARCHIVE_BASE"):
            module.ARCHIVE_BASE = ARCHIVE_BASE
        if hasattr(module, "DONOR_ROOT"):
            module.DONOR_ROOT = DONOR_ROOT
        if hasattr(module, "TEST_BATCH"):
            module.TEST_BATCH = TEST_BATCH
    # The V14 DC helper predates per-batch subfolders and writes cases under
    # its OUT_ROOT. Point only that helper at this batch directory.
    v14.v9.OUT_ROOT = TEST_BATCH


def _copy_archived_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    copied: dict[str, Path] = {}
    for name, source in ARCHIVED_DONORS.items():
        if not source.exists():
            raise FileNotFoundError(source)
        target = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(source, target)
        copied[name] = target
    return copied


def _base_payload(case: TwoSourceCase) -> dict[str, Any]:
    node_ids = list(dict.fromkeys(label for mode, start, end in case.groups for label in (start, end)))
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_target": GENERATOR_TARGET,
        "project": {
            "name": case.case_id,
            "output_basename": case.case_id,
            "base": BASE_PROJECT,
            "units": "proteus_internal",
        },
        "nodes": [{"id": node, "kind": "source_net"} for node in node_ids],
        "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
        "metadata": {"description": case.description, "source_kind": case.source_kind},
    }


def _dc_cases() -> list[TwoSourceCase]:
    return [
        TwoSourceCase(
            case_id="SRCP_V2_DCV2_T01_R_ONLY",
            description="Two DC voltage sources, each driving one resistor branch to common D0.",
            source_kind="dc_voltage_dc_voltage",
            source_plans=(
                v14.SourcePlan("dc_voltage", "V1", "10V", "DV"),
                v14.SourcePlan("dc_voltage", "V2", "5V", "D1"),
            ),
            groups=(("R", "DV", "D0"), ("R", "D1", "D0")),
            visible_values={"R1": "1k0", "R2": "2k0"},
            exact_values={"R1": "1k", "R2": "2k"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_DCV2_T02_RC_RL",
            description="Two DC voltage sources driving RC and RL two-family branches.",
            source_kind="dc_voltage_dc_voltage",
            source_plans=(
                v14.SourcePlan("dc_voltage", "V1", "10V", "DV"),
                v14.SourcePlan("dc_voltage", "V2", "5V", "D1"),
            ),
            groups=(("RC", "DV", "D0"), ("RL", "D1", "D0")),
            visible_values={"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH"},
            exact_values={"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_DCI2_T03_R_ONLY",
            description="Two DC current sources, each driving one resistor branch to common D0.",
            source_kind="dc_current_dc_current",
            source_plans=(
                v14.SourcePlan("dc_current", "I1", "1A", "D1"),
                v14.SourcePlan("dc_current", "I2", "2A", "D2"),
            ),
            groups=(("R", "D1", "D0"), ("R", "D2", "D0")),
            visible_values={"R1": "470", "R2": "220"},
            exact_values={"R1": "470", "R2": "220"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_DCI2_T04_RC_RL",
            description="Two DC current sources driving RC and RL two-family branches.",
            source_kind="dc_current_dc_current",
            source_plans=(
                v14.SourcePlan("dc_current", "I1", "1A", "D1"),
                v14.SourcePlan("dc_current", "I2", "2A", "D2"),
            ),
            groups=(("RC", "D1", "D0"), ("RL", "D2", "D0")),
            visible_values={"R1": "470", "C1": "2u2", "R2": "220", "L1": "5mH"},
            exact_values={"R1": "470", "C1": "2.2uF", "R2": "220", "L1": "5mH"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_DCV_DCI_T05_R_ONLY",
            description="One DC voltage source and one DC current source driving separate resistor branches.",
            source_kind="dc_voltage_dc_current",
            source_plans=(
                v14.SourcePlan("dc_voltage", "V1", "10V", "DV"),
                v14.SourcePlan("dc_current", "I1", "1A", "D1"),
            ),
            groups=(("R", "DV", "D0"), ("R", "D1", "D0")),
            visible_values={"R1": "1k0", "R2": "470"},
            exact_values={"R1": "1k", "R2": "470"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_DCV_DCI_T06_RCL_RC",
            description="One DC voltage source and one DC current source driving RCL and RC branches.",
            source_kind="dc_voltage_dc_current",
            source_plans=(
                v14.SourcePlan("dc_voltage", "V1", "12V", "DV"),
                v14.SourcePlan("dc_current", "I1", "1A", "D1"),
            ),
            groups=(("RCL", "DV", "D0"), ("RC", "D1", "D0")),
            visible_values={"R1": "1k0", "C1": "1uF", "L1": "5mH", "R2": "470", "C2": "2u2"},
            exact_values={"R1": "1k", "C1": "1uF", "L1": "5mH", "R2": "470", "C2": "2.2uF"},
        ),
    ]


def _make_dc_case(
    case: TwoSourceCase,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    donor_chunk: bytes,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v14._source_net_rcl_with_values(
        templates,
        case.groups,
        case.visible_values,
    )
    first_source_id = len(specs) + 1
    source_outputs, source_tails, source_metadata = v14._build_source_units(
        donor_chunk,
        source_net_chunk,
        case.source_plans,
        first_source_id,
    )
    object_chunk = bytearray(b"\x00" + source_outputs + source_net_chunk[1:-1] + source_tails)
    object_chunk[-1] = 0xFF
    object_chunk, wire_repair = v13._repair_generated_negative_wire_high_bytes(bytes(object_chunk))

    cdb_specs = [v14.replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    manifest = v14.v9._write_case(
        case.case_id,
        case.description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=v14._build_cdb(cdb_specs, case.source_plans, first_source_id),
        devices=devices,
        input_payload={
            **_base_payload(case),
            "source_count": len(case.source_plans),
            "source_rule": "V14 locked DC mixed-source method: generated source-net passive body plus duplicated donor-derived VSOURCE/CSOURCE units.",
            "sources": source_metadata,
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "rcl_counts": rcl_counts,
            "topology": topology,
            "wire_repair": wire_repair,
        },
    )
    manifest["status"] = "temporary_source_passive_v2_two_source_pending_user_test"
    (TEST_BATCH / case.case_id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _ac_source_unit_suffixes(source_index: int) -> tuple[int, int]:
    base = 0x7600 + (source_index - 1) * 0x80
    return base, base + 0x32


def _split_ac_source_block(block: bytes) -> tuple[bytes, bytes, bytes, bytes]:
    terms = v14.v9._terminal_events(block)
    if len(terms) != 2 or terms[0][1] != "OUT" or terms[1][1] != "IN":
        raise RuntimeError(f"Unexpected AC source block terminals: {terms}")
    out_start = terms[0][0]
    in_start = terms[1][0]
    source_start = block.find(b"\xff\x02V1") - 1
    first_wire = block.find(b"WIRE")
    if out_start != 0 or in_start <= 0 or source_start <= in_start or first_wire <= source_start:
        raise RuntimeError("Unexpected AC source unit boundaries.")
    return block[out_start:in_start], block[in_start:source_start], block[source_start:first_wire], block[first_wire:]


def _translate_ac_source_text_fields(out: bytearray, dx: int, dy: int) -> int:
    patterns = [
        (b"\xff\x02V1", 4),
        (b"\xff\x02V2", 4),
        (b"\xff\x05VSINE", 7),
        (b"\x02\x00\x05VSINE", 8),
        (b"{PRIMITIVE=ANALOGUE}\n", len(b"{PRIMITIVE=ANALOGUE}\n")),
    ]
    count = 0
    data = bytes(out)
    for pattern, coord_delta in patterns:
        pos = 0
        while True:
            found = data.find(pattern, pos)
            if found < 0:
                break
            coord = found + coord_delta
            if coord + 8 <= len(out):
                v13._add_s32(out, coord, dx)
                v13._add_s32(out, coord + 4, dy)
                count += 1
            pos = found + 1
    return count


def _patch_ac_source_record(
    record: bytes,
    *,
    ref: str,
    global_id: int,
    old_in_suffix: int,
    new_in_suffix: int,
    old_out_suffix: int,
    new_out_suffix: int,
) -> bytes:
    out = bytearray(record)
    if len(ref) != 2:
        raise ValueError("AC source refs must remain two ASCII characters.")
    old_ref = b"\xff\x02V1"
    new_ref = b"\xff\x02" + ref.encode("ascii")
    if old_ref not in out:
        raise RuntimeError("Could not find AC source ref marker V1.")
    out = bytearray(bytes(out).replace(old_ref, new_ref, 1))
    model_pos = bytes(out).find(b"\x02\x00\x05VSINE")
    if model_pos < 0:
        raise RuntimeError("Could not find AC final VSINE marker.")
    body_coord = model_pos + 8
    out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    data = bytes(out)
    old_in = rv9._u16(old_in_suffix) + b"\x01\x00"
    old_out = rv9._u16(old_out_suffix) + b"\x01\x00"
    data = data.replace(old_in, rv9._u16(new_in_suffix) + b"\x01\x00", 1)
    data = data.replace(old_out, rv9._u16(new_out_suffix) + b"\x01\x00", 1)
    return data


def _build_ac_source_unit(
    template_block: bytes,
    *,
    source_index: int,
    ref: str,
    positive: str,
    negative: str,
    global_id: int,
    dx: int,
    dy: int,
) -> tuple[bytes, dict[str, Any]]:
    out_suffix, in_suffix = _ac_source_unit_suffixes(source_index)
    out_record, in_record, source_record, wires = _split_ac_source_block(template_block)
    old_out_suffix = int.from_bytes(out_record[-4:-2], "little")
    old_in_suffix = int.from_bytes(in_record[-4:-2], "little")

    out_record = v14._patch_terminal_label_suffix(out_record, "OUT", positive, out_suffix)
    in_record = v14._patch_terminal_label_suffix(in_record, "IN", negative, in_suffix)
    source_record = _patch_ac_source_record(
        source_record,
        ref=ref,
        global_id=global_id,
        old_in_suffix=old_in_suffix,
        new_in_suffix=in_suffix,
        old_out_suffix=old_out_suffix,
        new_out_suffix=out_suffix,
    )
    block = bytearray(out_record + in_record + source_record + wires)
    if dx or dy:
        for start, end, kind, _label in v13._terminal_bounds(bytes(block)):
            v13._translate_terminal(block, start, end, kind, dx, dy)
        v13._translate_wires(block, 0, len(block), dx, dy)
        _translate_ac_source_text_fields(block, dx, dy)
    block[-1] = 0x00
    return bytes(block), {
        "kind": "ac_voltage",
        "ref": ref,
        "model": "VSINE",
        "positive": positive,
        "negative": negative,
        "global_id": global_id,
        "out_suffix": f"{out_suffix:04x}",
        "in_suffix": f"{in_suffix:04x}",
        "dx": dx,
        "dy": dy,
    }


def _ac_cases() -> list[TwoSourceCase]:
    return [
        TwoSourceCase(
            case_id="SRCP_V2_ACV2_T07_R_ONLY",
            description="Two AC voltage sources, each driving one resistor branch.",
            source_kind="ac_voltage_ac_voltage",
            source_plans=(),
            groups=(("R", "AV", "A0"), ("R", "BV", "B0")),
            visible_values={"R1": "1k0", "R2": "2k0"},
            exact_values={"R1": "1k", "R2": "2k"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_ACV2_T08_RC_RL",
            description="Two AC voltage sources driving RC and RL two-family branches.",
            source_kind="ac_voltage_ac_voltage",
            source_plans=(),
            groups=(("RC", "AV", "A0"), ("RL", "BV", "B0")),
            visible_values={"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH"},
            exact_values={"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_ACV2_T09_RCL_RC",
            description="Two AC voltage sources driving RCL and RC branches.",
            source_kind="ac_voltage_ac_voltage",
            source_plans=(),
            groups=(("RCL", "AV", "A0"), ("RC", "BV", "B0")),
            visible_values={"R1": "1k0", "C1": "1uF", "L1": "5mH", "R2": "2k0", "C2": "2u2"},
            exact_values={"R1": "1k", "C1": "1uF", "L1": "5mH", "R2": "2k", "C2": "2.2uF"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_ACV2_T10_C_ONLY",
            description="Two AC voltage sources, each driving one capacitor branch.",
            source_kind="ac_voltage_ac_voltage",
            source_plans=(),
            groups=(("C", "AV", "A0"), ("C", "BV", "B0")),
            visible_values={"C1": "1uF", "C2": "2u2"},
            exact_values={"C1": "1uF", "C2": "2.2uF"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_ACV2_T11_L_ONLY",
            description="Two AC voltage sources, each driving one inductor branch.",
            source_kind="ac_voltage_ac_voltage",
            source_plans=(),
            groups=(("L", "AV", "A0"), ("L", "BV", "B0")),
            visible_values={"L1": "5mH", "L2": "2mH"},
            exact_values={"L1": "5mH", "L2": "2mH"},
        ),
        TwoSourceCase(
            case_id="SRCP_V2_ACV2_T12_CL_RL",
            description="Two AC voltage sources driving CL and RL two-family branches.",
            source_kind="ac_voltage_ac_voltage",
            source_plans=(),
            groups=(("LC", "AV", "A0"), ("RL", "BV", "B0")),
            visible_values={"C1": "1uF", "L1": "5mH", "R1": "2k0", "L2": "2mH"},
            exact_values={"C1": "1uF", "L1": "5mH", "R1": "2k", "L2": "2mH"},
        ),
    ]


def _make_ac_case(
    case: TwoSourceCase,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    two_source_project: Path,
    variant_project: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = acv2.v1.v5._source_net_rcl(templates, case.groups)
    cdb_specs = [v14.replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    first_source_id = len(specs) + 1
    template_block = acv2._nonfinal_two_source_av_a0_block(two_source_project, global_id=first_source_id)
    block1, info1 = _build_ac_source_unit(
        template_block,
        source_index=1,
        ref="V1",
        positive="AV",
        negative="A0",
        global_id=first_source_id,
        dx=0,
        dy=0,
    )
    block2, info2 = _build_ac_source_unit(
        template_block,
        source_index=2,
        ref="V2",
        positive="BV",
        negative="B0",
        global_id=first_source_id + 1,
        dx=0,
        dy=-1_524_000,
    )
    object_chunk = bytearray(b"\x00" + block1 + block2 + source_net_chunk[1:])
    object_chunk[-1] = 0xFF
    object_chunk, wire_repair = v13._repair_generated_negative_wire_high_bytes(bytes(object_chunk))
    prop_text = acv2.v1._source_prop_text(variant_project)
    source_specs = [
        acv2.v1.AcVoltageSpec(idx=first_source_id, ref="V1", value="VSINE", prop_text=prop_text),
        acv2.v1.AcVoltageSpec(idx=first_source_id + 1, ref="V2", value="VSINE", prop_text=prop_text),
    ]
    manifest = acv2.v1._write_case(
        case.case_id,
        case.description,
        base_project=base_project,
        donor_project=donor_project,
        object_chunk=object_chunk,
        cdb=acv2.v1._build_cdb(cdb_specs, source_specs, "before_rcl"),
        devices=devices,
        input_payload={
            **_base_payload(case),
            "source_count": 2,
            "source_rule": "ACV V2-derived duplicate exact non-final AV/A0 VSINE unit, repatched to AV/A0 and BV/B0.",
            "sources": [info1, info2],
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "rcl_counts": rcl_counts,
            "topology": topology,
            "wire_repair": wire_repair,
        },
    )
    manifest["status"] = "temporary_source_passive_v2_two_source_pending_user_test"
    (TEST_BATCH / case.case_id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _summarize_case(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": manifest["case_id"],
        "description": manifest["description"],
        "marker_counts": manifest["marker_counts"],
        "device_marker_counts": manifest.get("device_marker_counts"),
        "object_chunk_len": manifest["object_chunk_len"],
        "root_cdb_len": manifest["root_cdb_len"],
        "static_validation_issues": manifest["static_validation_issues"],
        "source_kind": manifest.get("input", {}).get("source_kind"),
    }


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)
    _set_module_paths()
    donors = _copy_archived_donors()

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v14.v9.rcl._load_rcl_unit_templates(rcl_donor)

    dc_donor = donors["dc_mixed_v14_donor"]
    dc_donor_dsn = read_internal_file(dc_donor, "ROOT.DSN")
    dc_donor_chunk = rv9._extract_object_chunk(dc_donor_dsn)
    dc_devices = v14.v9.v5._device_section_from_dsn(dc_donor_dsn)

    ac_devices = acv2.v1.v5._device_section_from_dsn(read_internal_file(donors["acv_source_load"], "ROOT.DSN"))

    cases: list[dict[str, Any]] = []
    for case in _dc_cases():
        cases.append(
            _make_dc_case(
                case,
                templates=templates,
                base_project=base_project,
                donor_project=dc_donor,
                donor_chunk=dc_donor_chunk,
                devices=dc_devices,
            )
        )
    for case in _ac_cases():
        cases.append(
            _make_ac_case(
                case,
                templates=templates,
                base_project=base_project,
                donor_project=donors["acv_source_load"],
                two_source_project=donors["acv_two_source"],
                variant_project=donors["acv_variant_source"],
                devices=ac_devices,
            )
        )

    summary = {
        "batch_id": "SOURCE_PASSIVE_V2_TWO_SOURCE_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_netlist_test",
        "purpose": "Test source multiplicity after Source Passive V1 proved single-source passive loads.",
        "method": {
            "dc_two_source": "V14 locked mixed DC source-unit duplication with common D0 return.",
            "ac_two_source": "ACV V2 exact non-final source unit duplicated with unique two-character labels and suffix bytes.",
            "passive_body": "Accepted mixed_rcl subgroup modes.",
        },
        "test_order": [item["case_id"] for item in cases],
        "cases": [_summarize_case(item) for item in cases],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V2 two-source probe pack.\n\nOpen in order:\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n\nT01-T06 are DC two-source cases. T07-T12 are AC-voltage two-source cases. AC current remains out of scope.\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")

    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
