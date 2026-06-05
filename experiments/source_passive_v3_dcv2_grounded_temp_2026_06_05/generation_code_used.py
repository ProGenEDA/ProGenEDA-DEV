"""Generate corrected two-DC-voltage-source passive probes.

V2 showed that the reduced two-VSOURCE-only cases open visually but fail SPICE
with a singular ``#V2#branch``. This V3 pack keeps the visible source-terminal
method and tests the missing simulation reference explicitly:

* T01/T02 use G0 as the shared negative/source return.
* T03/T04 keep D0 as the shared source return and add a 1G D0-to-G0 reference.

The goal is to identify the smallest source-driven DCV2 rule that both opens
and simulates before promoting anything into main generation.
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

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import BASE_PROJECT, GENERATOR_TARGET, MixedRclCircuitIR, MixedRclGroup, SCHEMA_VERSION  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V14_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v14_requested5_v13_method_temp.py"
OUT_ROOT = REPO_ROOT / "experiments" / "source_passive_v3_dcv2_grounded_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "SOURCE_PASSIVE_V3_DCV2_GROUNDED_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V3_DCV2_GROUNDED_TEST_BATCH"

ARCHIVED_DONOR = (
    REPO_ROOT
    / "experiments"
    / "dc_mixed_sources_v14_requested5_v13_method_temp_2026_06_05"
    / "donors"
    / "rcl_v19_21_with_vsource_csource.pdsprj"
)


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    sources: tuple[Any, ...]
    visible_values: dict[str, str]
    exact_values: dict[str, str]
    reference_rule: str


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v14 = _load_module("dc_mixed_v14_for_source_passive_v3", V14_PATH)
v13 = v14.v13


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donor() -> Path:
    if not ARCHIVED_DONOR.exists():
        raise FileNotFoundError(ARCHIVED_DONOR)
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    target = DONOR_ROOT / "dc_mixed_v14_donor.pdsprj"
    shutil.copy2(ARCHIVED_DONOR, target)
    return target


def _source_net_rcl_ground_allowed(
    templates: Any,
    groups: tuple[tuple[str, str, str], ...],
    visible_values: dict[str, str],
) -> tuple[bytes, list[Any], list[dict[str, Any]], dict[str, Any]]:
    ir = MixedRclCircuitIR(
        schema_version=SCHEMA_VERSION,
        generator_target=GENERATOR_TARGET,
        name="SOURCE_PASSIVE_V3_DCV2_GROUNDED_BODY",
        output_basename="SOURCE_PASSIVE_V3_DCV2_GROUNDED_BODY",
        groups=tuple(MixedRclGroup(mode=mode, start=start, end=end) for mode, start, end in groups),
        component_values=visible_values,
        metadata={},
    )
    chunk_with_bridge, specs, topology, counts = v14.v9.rcl.build_object_chunk(ir, templates)
    bridge_end = 1 + rv9.POWER_BRIDGE_CORE_SIZE
    body = bytearray(chunk_with_bridge[bridge_end:])
    if body.count(b"$TERPOWER"):
        raise RuntimeError("Source-driven DCV2 body must not contain $TERPOWER.")
    body[-1] = 0xFF
    return bytes(b"\x00" + body), specs, topology, {**counts, "power_bridge_count": 0}


def _base_payload(case: Case) -> dict[str, Any]:
    node_ids = list(dict.fromkeys(label for _mode, start, end in case.groups for label in (start, end)))
    return {
        "schema_version": SCHEMA_VERSION,
        "generator_target": GENERATOR_TARGET,
        "project": {
            "name": case.case_id,
            "output_basename": case.case_id,
            "base": BASE_PROJECT,
            "units": "proteus_internal",
        },
        "nodes": [
            {
                "id": node,
                "kind": "ground" if node == "G0" else "source_net",
            }
            for node in node_ids
        ],
        "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
        "metadata": {
            "description": case.description,
            "source_kind": "dc_voltage_dc_voltage",
            "reference_rule": case.reference_rule,
        },
    }


def _cases() -> list[Case]:
    return [
        Case(
            case_id="SRCP_V3_DCV2_T01_R_ONLY_G0_RETURN",
            description="Two DC voltage sources, each driving one resistor branch to shared grounded G0 return.",
            sources=(
                v14.SourcePlan("dc_voltage", "V1", "10V", "DV", "G0"),
                v14.SourcePlan("dc_voltage", "V2", "5V", "D1", "G0"),
            ),
            groups=(("R", "DV", "G0"), ("R", "D1", "G0")),
            visible_values={"R1": "1k0", "R2": "2k0"},
            exact_values={"R1": "1k", "R2": "2k"},
            reference_rule="preferred: source negative terminals and passive returns share G0.",
        ),
        Case(
            case_id="SRCP_V3_DCV2_T02_RC_RL_G0_RETURN",
            description="Two DC voltage sources driving RC and RL branches to shared grounded G0 return.",
            sources=(
                v14.SourcePlan("dc_voltage", "V1", "10V", "DV", "G0"),
                v14.SourcePlan("dc_voltage", "V2", "5V", "D1", "G0"),
            ),
            groups=(("RC", "DV", "G0"), ("RL", "D1", "G0")),
            visible_values={"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH"},
            exact_values={"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH"},
            reference_rule="preferred: source negative terminals and passive returns share G0.",
        ),
        Case(
            case_id="SRCP_V3_DCV2_T03_R_ONLY_D0_WITH_1G_REF",
            description="Two DC voltage sources with D0 return and a high-value D0-to-G0 simulation reference.",
            sources=(
                v14.SourcePlan("dc_voltage", "V1", "10V", "DV", "D0"),
                v14.SourcePlan("dc_voltage", "V2", "5V", "D1", "D0"),
            ),
            groups=(("R", "DV", "D0"), ("R", "D1", "D0"), ("R", "D0", "G0")),
            visible_values={"R1": "1k0", "R2": "2k0", "R3": "1G0"},
            exact_values={"R1": "1k", "R2": "2k", "R3": "1G"},
            reference_rule="diagnostic fallback: keep D0 return and add a 1G reference resistor to G0.",
        ),
        Case(
            case_id="SRCP_V3_DCV2_T04_RC_RL_D0_WITH_1G_REF",
            description="Two DC voltage sources driving RC/RL branches with D0 return and a high-value G0 reference.",
            sources=(
                v14.SourcePlan("dc_voltage", "V1", "10V", "DV", "D0"),
                v14.SourcePlan("dc_voltage", "V2", "5V", "D1", "D0"),
            ),
            groups=(("RC", "DV", "D0"), ("RL", "D1", "D0"), ("R", "D0", "G0")),
            visible_values={"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH", "R3": "1G0"},
            exact_values={"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH", "R3": "1G"},
            reference_rule="diagnostic fallback: keep D0 return and add a 1G reference resistor to G0.",
        ),
    ]


def _make_case(
    case: Case,
    *,
    templates: Any,
    base_project: Path,
    donor_project: Path,
    donor_chunk: bytes,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = _source_net_rcl_ground_allowed(
        templates,
        case.groups,
        case.visible_values,
    )
    first_source_id = len(specs) + 1
    source_outputs, source_tails, source_metadata = v14._build_source_units(
        donor_chunk,
        source_net_chunk,
        case.sources,
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
        cdb=v14._build_cdb(cdb_specs, case.sources, first_source_id),
        devices=devices,
        input_payload={
            **_base_payload(case),
            "source_count": len(case.sources),
            "source_rule": "V14 donor-derived VSOURCE units with explicit simulation reference on the shared return.",
            "sources": source_metadata,
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "rcl_counts": rcl_counts,
            "topology": topology,
            "wire_repair": wire_repair,
        },
    )
    manifest["static_validation_issues"] = [
        issue
        for issue in manifest["static_validation_issues"]
        if issue != "source-tail case unexpectedly contains $TERGROUND"
    ]
    manifest["static_validation_notes"] = [
        "V3 intentionally permits $TERGROUND on the shared source return to test SPICE reference stability."
    ]
    manifest["status"] = "temporary_source_passive_v3_dcv2_grounded_pending_user_test"
    (TEST_BATCH / case.case_id / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _summarize(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": manifest["case_id"],
        "description": manifest["description"],
        "marker_counts": manifest["marker_counts"],
        "object_chunk_len": manifest["object_chunk_len"],
        "root_cdb_len": manifest["root_cdb_len"],
        "static_validation_issues": manifest["static_validation_issues"],
        "reference_rule": manifest["input"]["metadata"]["reference_rule"],
    }


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)
    v14.v9.OUT_ROOT = TEST_BATCH

    donor = _copy_donor()
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v14.v9.rcl._load_rcl_unit_templates(rcl_donor)

    donor_dsn = read_internal_file(donor, "ROOT.DSN")
    donor_chunk = rv9._extract_object_chunk(donor_dsn)
    devices = v14.v9.v5._device_section_from_dsn(donor_dsn)

    cases = [
        _make_case(
            case,
            templates=templates,
            base_project=base_project,
            donor_project=donor,
            donor_chunk=donor_chunk,
            devices=devices,
        )
        for case in _cases()
    ]
    summary = {
        "batch_id": "SOURCE_PASSIVE_V3_DCV2_GROUNDED_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_simulation_test",
        "source_feedback": "V2 DCV2 T01/T02 opened but gave bad object record and SPICE singular #V2#branch on simulation.",
        "method": "Focused DCV2 replacement: explicit G0 shared return first, D0 plus 1G G0 reference as fallback.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [_summarize(item) for item in cases],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V3 DCV2 grounded-return correction pack.\n\n"
        "Test in order. T01/T02 are the preferred corrected rule. "
        "T03/T04 are diagnostic fallbacks that keep D0 and add a 1G G0 reference.\n\n"
        + "\n".join(f"{index}. {case_id}/{case_id}.pdsprj" for index, case_id in enumerate(summary["test_order"], start=1))
        + "\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"archive": archive, "sha256": _sha256_file(Path(archive)), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
