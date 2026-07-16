"""Generate DCV2 source-passive probes from the manual 2x voltage donor.

V2 proved most two-source cases worked, but pure DCV+DCV loads failed
simulation with ``#V2#branch``. V3 then proved source-driven streams reject the
ground-endpoint fix with bad object record errors.

This V4 pack returns to the manual two-voltage-source donor. Its important
observed rule is that the second voltage source has its own return label
(``DV1/D01``), not the same ``D0`` return as the first source. The preferred
tests therefore use separate source returns with two-character labels:

* first source: ``DV`` / ``D0``
* second source: ``D1`` / ``D2``

No ``$TERGROUND`` records are emitted in this pack.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import resistor_v9 as rv9  # noqa: E402
from proteusgen.mixed_rcl import BASE_PROJECT, GENERATOR_TARGET, SCHEMA_VERSION  # noqa: E402
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.templates import FixtureRegistry  # noqa: E402

V14_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v14_requested5_v13_method_temp.py"
V9_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-05" / "generate_dc_mixed_sources_v9_donor_tail_temp.py"

OUT_ROOT = REPO_ROOT / "experiments" / "source_passive_v4_dcv2_manual2x_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "SOURCE_PASSIVE_V4_DCV2_MANUAL2X_TEMP_2026_06_05"
DONOR_ROOT = OUT_ROOT / "donors"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V4_DCV2_MANUAL2X_TEST_BATCH"

USER_DONOR_ROOT = Path(r"C:\Users\tahab\Downloads\New folder (3)")
MANUAL_2X_10V = USER_DONOR_ROOT / "2x dc_voltage_01_default_10v.pdsprj"
MIXED_V14_DONOR = (
    REPO_ROOT
    / "experiments"
    / "dc_mixed_sources_v14_requested5_v13_method_temp_2026_06_05"
    / "donors"
    / "rcl_v19_21_with_vsource_csource.pdsprj"
)

CdbOrder = Literal["passives_first", "sources_first"]


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    groups: tuple[tuple[str, str, str], ...]
    labels: dict[str, str]
    cdb_order: CdbOrder
    visible_values: dict[str, str]
    exact_values: dict[str, str]
    diagnostic_rule: str


@dataclass(frozen=True)
class SourceRow:
    idx: int
    ref: str
    value: str
    model: str = "VSOURCE"
    prop_text: bytes = b"{PRIMITIVE=ANALOG}\n\x00"


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import helper module from {path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


v14 = _load_module("dc_mixed_v14_for_source_passive_v4", V14_PATH)
v9temp = _load_module("dc_mixed_v9_for_source_passive_v4", V9_PATH)
v13 = v14.v13


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _copy_donors() -> dict[str, Path]:
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    sources = {
        "manual_2x_dcv_10v": MANUAL_2X_10V,
        "mixed_v14_donor": MIXED_V14_DONOR,
    }
    copied: dict[str, Path] = {}
    for name, src in sources.items():
        if not src.exists():
            raise FileNotFoundError(src)
        dst = DONOR_ROOT / f"{name}.pdsprj"
        shutil.copy2(src, dst)
        copied[name] = dst
    return copied


def _patch_two_source_global_ids(source_block: bytes, first_source_id: int) -> bytes:
    out = bytearray(source_block)
    marker = b"\x02\x00\x07VSOURCE"
    found: list[int] = []
    pos = 0
    while True:
        index = bytes(out).find(marker, pos)
        if index < 0:
            break
        found.append(index)
        pos = index + 1
    if len(found) != 2:
        raise RuntimeError(f"Manual 2x DCV source block should contain two final VSOURCE markers, found {len(found)}.")
    for offset, global_id in zip(found, (first_source_id, first_source_id + 1), strict=True):
        body_coord = offset + len(marker)
        out[body_coord + 12 : body_coord + 16] = rv9._u32(global_id)
    return bytes(out)


def _manual_two_source_block(donor: Path, *, labels: dict[str, str], first_source_id: int) -> tuple[bytes, dict[str, Any]]:
    chunk = rv9._extract_object_chunk(read_internal_file(donor, "ROOT.DSN"))
    if chunk.count(b"VSOURCE") != 4 or chunk.count(b"$TEROUTPUT") != 2 or chunk.count(b"$TERINPUT") != 2:
        raise RuntimeError("Unexpected manual 2x DCV donor structure.")
    block = chunk[:-1]
    block = v9temp._patch_terminal_labels(block, labels)
    block = _patch_two_source_global_ids(block, first_source_id)
    terms = [(kind, label) for _start, kind, label in v9temp._terminal_events(block)]
    return block, {
        "source_block": "manual 2x dc_voltage donor without final FF",
        "label_replacements": labels,
        "source_ids": [first_source_id, first_source_id + 1],
        "terminals": terms,
    }


def _build_cdb(rcl_specs: list[Any], source_rows: tuple[SourceRow, SourceRow], order: CdbOrder) -> bytes:
    passive_rows = sorted(rcl_specs, key=lambda item: item.idx)
    ordered: list[Any]
    if order == "sources_first":
        ordered = [*source_rows, *passive_rows]
    else:
        ordered = [*passive_rows, *source_rows]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + v14.v9.v5._enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + v14.v9.v5._enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + v14.v9.v5._enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + v14.v9.v5._enc_str(spec.ref)
        if getattr(spec, "kind", "") == "CAPACITOR":
            out += rv9._u32(2) + v14.v9.v5._enc_str("2") + v14.v9.v5._enc_str("2") + v14.v9.v5._enc_str("1") + v14.v9.v5._enc_str("1")
        else:
            out += rv9._u32(2) + v14.v9.v5._enc_str("1") + b"\x00" + v14.v9.v5._enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + v14.v9.v5._enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
        if isinstance(spec, SourceRow):
            out += v14.v9.v5._enc_str(spec.ref) + v14.v9.v5._enc_str(spec.value) + v14.v9.v5._enc_str(spec.model) + v14.v9.v5._enc_str("") + v14.v9.v5._enc_text(spec.prop_text)
        elif spec.kind == "CAPACITOR":
            out += v14.v9.v5._enc_str(spec.ref) + v14.v9.v5._enc_str(spec.value) + v14.v9.v5._enc_str("CAP") + v14.v9.v5._enc_str("CAP10") + v14.v9.v5._enc_text(v14.v9.rcl.mp.CAP_PROP_TEXT)
        elif spec.kind == "INDUCTOR":
            out += v14.v9.v5._enc_str(spec.ref) + v14.v9.v5._enc_str(spec.value) + v14.v9.v5._enc_str("REALIND") + v14.v9.v5._enc_str("") + v14.v9.v5._enc_text(v14.v9.rcl.INDUCTOR_PROP_TEXT)
        else:
            out += v14.v9.v5._enc_str(spec.ref) + v14.v9.v5._enc_str(spec.value) + v14.v9.v5._enc_str("RESISTOR") + v14.v9.v5._enc_str("") + v14.v9.v5._enc_text(rv9.PROP_TEXT)
    out += rv9._u32(0)
    return bytes(out)


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
        "nodes": [{"id": node, "kind": "source_net"} for node in node_ids],
        "groups": [{"mode": mode, "start": start, "end": end} for mode, start, end in case.groups],
        "metadata": {
            "description": case.description,
            "source_kind": "dc_voltage_dc_voltage",
            "diagnostic_rule": case.diagnostic_rule,
            "cdb_order": case.cdb_order,
        },
    }


def _cases() -> list[Case]:
    separate_labels = {"DV1": "D1", "D01": "D2"}
    shared_labels = {"DV1": "D1", "D01": "D0"}
    return [
        Case(
            case_id="SRCP_V4_DCV2_T01_R_ONLY_SEPARATE_RETURNS_SOURCE_FIRST_CDB",
            description="Two manual-donor DC voltage sources with separate returns, each driving one resistor.",
            groups=(("R", "DV", "D0"), ("R", "D1", "D2")),
            labels=separate_labels,
            cdb_order="sources_first",
            visible_values={"R1": "1k0", "R2": "2k0"},
            exact_values={"R1": "1k", "R2": "2k"},
            diagnostic_rule="preferred: manual 2x DCV source block, separate returns DV/D0 and D1/D2, source rows first in CDB.",
        ),
        Case(
            case_id="SRCP_V4_DCV2_T02_RC_RL_SEPARATE_RETURNS_SOURCE_FIRST_CDB",
            description="Two manual-donor DC voltage sources with separate returns driving RC and RL branches.",
            groups=(("RC", "DV", "D0"), ("RL", "D1", "D2")),
            labels=separate_labels,
            cdb_order="sources_first",
            visible_values={"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH"},
            exact_values={"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH"},
            diagnostic_rule="preferred: manual 2x DCV source block, separate returns DV/D0 and D1/D2, source rows first in CDB.",
        ),
        Case(
            case_id="SRCP_V4_DCV2_T03_R_ONLY_SHARED_D0_SOURCE_FIRST_CDB",
            description="Manual-donor DCV2 block but both voltage sources share D0 return.",
            groups=(("R", "DV", "D0"), ("R", "D1", "D0")),
            labels=shared_labels,
            cdb_order="sources_first",
            visible_values={"R1": "1k0", "R2": "2k0"},
            exact_values={"R1": "1k", "R2": "2k"},
            diagnostic_rule="control: manual 2x DCV source block with V2-style shared D0 return, source rows first in CDB.",
        ),
        Case(
            case_id="SRCP_V4_DCV2_T04_RC_RL_SHARED_D0_SOURCE_FIRST_CDB",
            description="Manual-donor DCV2 block with shared D0 return driving RC/RL branches.",
            groups=(("RC", "DV", "D0"), ("RL", "D1", "D0")),
            labels=shared_labels,
            cdb_order="sources_first",
            visible_values={"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH"},
            exact_values={"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH"},
            diagnostic_rule="control: manual 2x DCV source block with V2-style shared D0 return, source rows first in CDB.",
        ),
        Case(
            case_id="SRCP_V4_DCV2_T05_R_ONLY_SEPARATE_RETURNS_PASSIVE_FIRST_CDB",
            description="Separate-return DCV2 resistor branches with passive rows first in CDB.",
            groups=(("R", "DV", "D0"), ("R", "D1", "D2")),
            labels=separate_labels,
            cdb_order="passives_first",
            visible_values={"R1": "1k0", "R2": "2k0"},
            exact_values={"R1": "1k", "R2": "2k"},
            diagnostic_rule="CDB-order check: same preferred separate-return geometry, passive rows first.",
        ),
        Case(
            case_id="SRCP_V4_DCV2_T06_RC_RL_SEPARATE_RETURNS_PASSIVE_FIRST_CDB",
            description="Separate-return DCV2 RC/RL branches with passive rows first in CDB.",
            groups=(("RC", "DV", "D0"), ("RL", "D1", "D2")),
            labels=separate_labels,
            cdb_order="passives_first",
            visible_values={"R1": "1k0", "C1": "1uF", "R2": "2k0", "L1": "5mH"},
            exact_values={"R1": "1k", "C1": "1uF", "R2": "2k", "L1": "5mH"},
            diagnostic_rule="CDB-order check: same preferred separate-return geometry, passive rows first.",
        ),
    ]


def _make_case(
    case: Case,
    *,
    templates: Any,
    base_project: Path,
    source_donor: Path,
    device_donor: Path,
    devices: bytes,
) -> dict[str, Any]:
    source_net_chunk, specs, topology, rcl_counts = v14._source_net_rcl_with_values(
        templates,
        case.groups,
        case.visible_values,
    )
    first_source_id = len(specs) + 1
    source_block, source_info = _manual_two_source_block(source_donor, labels=case.labels, first_source_id=first_source_id)
    object_chunk = bytearray(b"\x00" + source_block + source_net_chunk[1:])
    object_chunk[-1] = 0xFF
    object_chunk, wire_repair = v13._repair_generated_negative_wire_high_bytes(bytes(object_chunk))
    cdb_specs = [v14.replace(spec, value=case.exact_values.get(spec.ref, spec.value)) for spec in specs]
    source_rows = (
        SourceRow(first_source_id, "V1", "10V"),
        SourceRow(first_source_id + 1, "V2", "10V"),
    )
    manifest = v14.v9._write_case(
        case.case_id,
        case.description,
        base_project=base_project,
        donor_project=device_donor,
        object_chunk=object_chunk,
        cdb=_build_cdb(cdb_specs, source_rows, case.cdb_order),
        devices=devices,
        input_payload={
            **_base_payload(case),
            "source_count": 2,
            "source_rule": "Manual 2x DC voltage source donor block placed before generated source-net passive body; no $TERGROUND records.",
            "sources": source_info,
            "visible_values": case.visible_values,
            "exact_cdb_values": case.exact_values,
            "rcl_counts": rcl_counts,
            "topology": topology,
            "wire_repair": wire_repair,
        },
    )
    manifest["status"] = "temporary_source_passive_v4_dcv2_manual2x_pending_user_test"
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
        "diagnostic_rule": manifest["input"]["metadata"]["diagnostic_rule"],
    }


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    TEST_BATCH.mkdir(parents=True)
    v14.v9.OUT_ROOT = TEST_BATCH

    donors = _copy_donors()
    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base_project = registry.get("e001_empty").path
    rcl_donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v14.v9.rcl._load_rcl_unit_templates(rcl_donor)

    devices = v14.v9.v5._device_section_from_dsn(read_internal_file(donors["mixed_v14_donor"], "ROOT.DSN"))
    cases = [
        _make_case(
            case,
            templates=templates,
            base_project=base_project,
            source_donor=donors["manual_2x_dcv_10v"],
            device_donor=donors["mixed_v14_donor"],
            devices=devices,
        )
        for case in _cases()
    ]
    summary = {
        "batch_id": "SOURCE_PASSIVE_V4_DCV2_MANUAL2X_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_simulation_test",
        "source_feedback": "V2 pure DCV+DCV cases opened but failed simulation; V3 grounded-return cases all gave bad object record.",
        "method": "Use the manual 2x DC-voltage source donor block, no $TERGROUND, and test separate source returns first.",
        "test_order": [item["case_id"] for item in cases],
        "cases": [_summarize(item) for item in cases],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V4 DCV2 manual-2x-source correction pack.\n\n"
        "Test in order. T01/T02 are preferred. T03/T04 check whether shared D0 is the failure. "
        "T05/T06 check whether CDB row order matters.\n\n"
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
