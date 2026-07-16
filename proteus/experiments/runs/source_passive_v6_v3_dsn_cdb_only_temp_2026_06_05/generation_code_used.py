"""Generate V3-DSN-preserving pure DCV2 passive CDB diagnostics.

User feedback rejected V5 with VGDVC.dll and clarified that generated V3 at
least opened and rendered correctly. This pack therefore preserves generated
V3 ROOT.DSN byte-for-byte and changes only ROOT.CDB variants.

Primary hypothesis: the bad-object/simulation issue is in source CDB rows, not
the V3 visual object stream.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen import mixed_rcl as rcl
from proteusgen import resistor_v9 as rv9
from proteusgen.pdsprj import read_internal_file, write_project_from_parts

OUT_ROOT = REPO_ROOT / "experiments" / "source_passive_v6_v3_dsn_cdb_only_temp_2026_06_05"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "SOURCE_PASSIVE_V6_V3_DSN_CDB_ONLY_TEMP_2026_06_05"
TEST_BATCH = OUT_ROOT / "SOURCE_PASSIVE_V6_V3_DSN_CDB_ONLY_TEST_BATCH"
DONOR_ROOT = OUT_ROOT / "donors"

V3_BATCH = REPO_ROOT / "experiments" / "source_passive_v3_dcv2_grounded_temp_2026_06_05" / "SOURCE_PASSIVE_V3_DCV2_GROUNDED_TEST_BATCH"
V3_T03_ID = "SRCP_V3_DCV2_T03_R_ONLY_D0_WITH_1G_REF"
V3_T04_ID = "SRCP_V3_DCV2_T04_RC_RL_D0_WITH_1G_REF"
USER_FIXED = Path(r"C:\Users\tahab\Downloads\SRCP_V3_DCV2_T03_R_ONLY_D0_WITH_1G_REF.pdsprj")

PinStyle = Literal["passive", "source"]


@dataclass(frozen=True)
class ComponentSpec:
    idx: int
    ref: str
    kind: str
    value: str


@dataclass(frozen=True)
class SourceSpec:
    idx: int
    ref: str
    value: str
    pin_style: PinStyle
    terminal_side: int


@dataclass(frozen=True)
class Case:
    case_id: str
    description: str
    template_project: Path
    source_manifest: Path
    cdb_mode: str
    source_values: tuple[str, str] = ("10V", "5V")
    pin_style: PinStyle = "source"
    terminal_side: int = -1
    exact_cdb: Path | None = None


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _enc_str(value: str) -> bytes:
    raw = value.encode("ascii")
    if len(raw) > 255:
        raise ValueError(value)
    return bytes([len(raw)]) + raw


def _enc_text(value: bytes) -> bytes:
    return rv9._u32(4 + len(value)) + value


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_paths(case_dir: Path, case_id: str) -> tuple[Path, Path, Path]:
    return (
        case_dir / f"{case_id}.pdsprj",
        case_dir / "manifest.json",
        case_dir / f"{case_id}.ROOT.CDB.bin",
    )


def _component_specs_from_manifest(manifest: dict) -> list[ComponentSpec]:
    exact = manifest["input"].get("exact_cdb_values", {})
    specs: list[ComponentSpec] = []
    for item in manifest["input"]["topology"]:
        kind = item["kind"]
        ref = item["ref"]
        specs.append(
            ComponentSpec(
                idx=int(item["global_id"]),
                ref=ref,
                kind=kind,
                value=exact.get(ref, item["value"]),
            )
        )
    return sorted(specs, key=lambda spec: spec.idx)


def _source_specs(first_source_id: int, values: tuple[str, str], pin_style: PinStyle, terminal_side: int) -> list[SourceSpec]:
    return [
        SourceSpec(first_source_id, "V1", values[0], pin_style, terminal_side),
        SourceSpec(first_source_id + 1, "V2", values[1], pin_style, terminal_side),
    ]


def _write_pin_map(out: bytearray, spec: ComponentSpec | SourceSpec) -> None:
    if isinstance(spec, SourceSpec):
        if spec.pin_style == "source":
            out += rv9._u32(2) + _enc_str("+") + _enc_str("1") + _enc_str("-") + _enc_str("2")
        else:
            out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
        out += rv9._u32(0) + rv9._u32(spec.idx) + struct.pack("<i", spec.terminal_side)
        return
    if spec.kind == "CAPACITOR":
        out += rv9._u32(2) + _enc_str("2") + _enc_str("2") + _enc_str("1") + _enc_str("1")
    else:
        out += rv9._u32(2) + _enc_str("1") + b"\x00" + _enc_str("2") + b"\x00"
    out += rv9._u32(0) + rv9._u32(spec.idx) + rv9._u32(0)


def _write_value_row(out: bytearray, spec: ComponentSpec | SourceSpec) -> None:
    out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(0) + rv9._u32(0)
    if isinstance(spec, SourceSpec):
        out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("VSOURCE") + _enc_str("") + _enc_text(b"{PRIMITIVE=ANALOG}\n\x00")
    elif spec.kind == "CAPACITOR":
        out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("CAP") + _enc_str("CAP10") + _enc_text(rcl.mp.CAP_PROP_TEXT)
    elif spec.kind == "INDUCTOR":
        out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("REALIND") + _enc_str("") + _enc_text(rcl.INDUCTOR_PROP_TEXT)
    else:
        out += _enc_str(spec.ref) + _enc_str(spec.value) + _enc_str("RESISTOR") + _enc_str("") + _enc_text(rv9.PROP_TEXT)


def _build_cdb(component_specs: list[ComponentSpec], source_specs: list[SourceSpec]) -> bytes:
    ordered: list[ComponentSpec | SourceSpec] = [*component_specs, *source_specs]
    out = bytearray()
    out += rv9._u32(7)
    out += rv9._u32(1) + rv9._u32(1) + rv9._u32(0) + _enc_str("ROOT") + b"\x00" + rv9._u32(0) + rv9._u32(1) + rv9._u32(1)
    out += rv9._u32(2)
    out += rv9._u32(1) + rv9._u32(3) + rv9._u32(1) + _enc_str("") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(2) + rv9._u32(2) + rv9._u32(0) + _enc_str("Master Sheet") + rv9._u32(10) + rv9._u32(0)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        out += rv9._u32(spec.idx) + rv9._u32(1) + rv9._u32(0) + rv9._u32(spec.idx) + _enc_str(spec.ref)
        _write_pin_map(out, spec)
    out += rv9._u32(1) + rv9._u32(1) + b"\x00" + _enc_str("") + rv9._u32(1)
    out += rv9._u32(len(ordered))
    for spec in ordered:
        _write_value_row(out, spec)
    out += rv9._u32(0)
    return bytes(out)


def _case_inputs(v3_id: str) -> tuple[Path, Path, Path]:
    case_dir = V3_BATCH / v3_id
    project, manifest, cdb = _manifest_paths(case_dir, v3_id)
    if not project.exists():
        raise FileNotFoundError(project)
    return project, manifest, cdb


def _cases() -> list[Case]:
    t03_project, t03_manifest, _t03_cdb = _case_inputs(V3_T03_ID)
    t04_project, t04_manifest, _t04_cdb = _case_inputs(V3_T04_ID)
    fixed_cdb = OUT_ROOT / "donors" / "user_fixed_v3_t03.ROOT.CDB.bin"
    return [
        Case("SRCP_V6_T00_V3_T03_ORIGINAL_COPY", "Original generated V3 T03 copied unchanged as the visual/open baseline.", t03_project, t03_manifest, "copy_original"),
        Case("SRCP_V6_T01_T03_ORIG_DSN_FIXED_CDB_EXACT", "Generated V3 T03 ROOT.DSN preserved; ROOT.CDB replaced with the exact user-fixed CDB.", t03_project, t03_manifest, "exact_fixed_cdb", exact_cdb=fixed_cdb),
        Case("SRCP_V6_T02_T03_ORIG_DSN_SOURCE_CDB_1V", "Generated V3 T03 ROOT.DSN preserved; regenerated source-style CDB with 1V/1V source values.", t03_project, t03_manifest, "source_pins_neg1_1v", source_values=("1V", "1V"), pin_style="source", terminal_side=-1),
        Case("SRCP_V6_T03_T03_ORIG_DSN_SOURCE_CDB_10V_5V", "Generated V3 T03 ROOT.DSN preserved; regenerated source-style CDB with 10V/5V source values.", t03_project, t03_manifest, "source_pins_neg1_10v_5v", source_values=("10V", "5V"), pin_style="source", terminal_side=-1),
        Case("SRCP_V6_T04_T03_ORIG_DSN_SOURCE_PINS_FIELD0", "Generated V3 T03 ROOT.DSN preserved; source +/1 -/2 pins but source row final field kept at 0.", t03_project, t03_manifest, "source_pins_field0", source_values=("10V", "5V"), pin_style="source", terminal_side=0),
        Case("SRCP_V6_T05_T03_ORIG_DSN_PASSIVE_PINS_NEG1", "Generated V3 T03 ROOT.DSN preserved; passive 1/2 pins but source row final field changed to -1.", t03_project, t03_manifest, "passive_pins_neg1", source_values=("10V", "5V"), pin_style="passive", terminal_side=-1),
        Case("SRCP_V6_T06_V3_T04_ORIGINAL_COPY", "Original generated V3 T04 copied unchanged as the RC/RL baseline.", t04_project, t04_manifest, "copy_original"),
        Case("SRCP_V6_T07_T04_ORIG_DSN_SOURCE_CDB_1V", "Generated V3 T04 ROOT.DSN preserved; source-style CDB with 1V/1V source values.", t04_project, t04_manifest, "source_pins_neg1_1v", source_values=("1V", "1V"), pin_style="source", terminal_side=-1),
        Case("SRCP_V6_T08_T04_ORIG_DSN_SOURCE_CDB_10V_5V", "Generated V3 T04 ROOT.DSN preserved; source-style CDB with 10V/5V source values.", t04_project, t04_manifest, "source_pins_neg1_10v_5v", source_values=("10V", "5V"), pin_style="source", terminal_side=-1),
    ]


def _copy_fixed_cdb() -> None:
    if not USER_FIXED.exists():
        raise FileNotFoundError(USER_FIXED)
    DONOR_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(USER_FIXED, DONOR_ROOT / "user_fixed_v3_t03.pdsprj")
    fixed_cdb = read_internal_file(USER_FIXED, "ROOT.CDB")
    (DONOR_ROOT / "user_fixed_v3_t03.ROOT.CDB.bin").write_bytes(fixed_cdb)


def _write_case(case: Case) -> dict:
    case_dir = TEST_BATCH / case.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    output_path = case_dir / f"{case.case_id}.pdsprj"
    if case.cdb_mode == "copy_original":
        shutil.copy2(case.template_project, output_path)
        cdb = read_internal_file(output_path, "ROOT.CDB")
    else:
        if case.exact_cdb is not None:
            cdb = case.exact_cdb.read_bytes()
        else:
            manifest = _read_json(case.source_manifest)
            component_specs = _component_specs_from_manifest(manifest)
            first_source_id = max(spec.idx for spec in component_specs) + 1
            source_specs = _source_specs(first_source_id, case.source_values, case.pin_style, case.terminal_side)
            cdb = _build_cdb(component_specs, source_specs)
        write_project_from_parts(case.template_project, output_path, {"ROOT.CDB": cdb})

    root_dsn = read_internal_file(output_path, "ROOT.DSN")
    root_cdb = read_internal_file(output_path, "ROOT.CDB")
    object_chunk = rv9._extract_object_chunk(root_dsn)
    dsn_path = case_dir / f"{case.case_id}.ROOT.DSN.bin"
    cdb_path = case_dir / f"{case.case_id}.ROOT.CDB.bin"
    dsn_path.write_bytes(root_dsn)
    cdb_path.write_bytes(root_cdb)
    info = {
        "case_id": case.case_id,
        "description": case.description,
        "status": "temporary_source_passive_v6_v3_dsn_cdb_only_pending_user_test",
        "output": f"{case.case_id}\\{case.case_id}.pdsprj",
        "object_chunk_len": len(object_chunk),
        "root_cdb_len": len(root_cdb),
        "root_dsn_len": len(root_dsn),
        "marker_counts": rcl._marker_counts(object_chunk),
        "static_validation_issues": rcl._scan_wire_issues(object_chunk),
        "cdb_mode": case.cdb_mode,
        "root_dsn_preserved_from": str(case.template_project),
        "hashes": {
            f"{case.case_id}.pdsprj": _sha256_file(output_path),
            f"{case.case_id}.ROOT.DSN.bin": _sha256_file(dsn_path),
            f"{case.case_id}.ROOT.CDB.bin": _sha256_file(cdb_path),
            "object_chunk": _sha256_bytes(object_chunk),
            "ROOT.CDB": _sha256_bytes(root_cdb),
        },
    }
    if case.cdb_mode != "copy_original":
        info["source_values"] = list(case.source_values)
        info["pin_style"] = case.pin_style
        info["terminal_side"] = case.terminal_side
    (case_dir / "manifest.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    (case_dir / "README_TEST_FIRST.txt").write_text(f"Open and simulate {case.case_id}.pdsprj\n", encoding="utf-8")
    return info


def main() -> None:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    archive = ARCHIVE_BASE.with_suffix(".zip")
    if archive.exists():
        archive.unlink()
    TEST_BATCH.mkdir(parents=True, exist_ok=True)
    _copy_fixed_cdb()
    manifests = [_write_case(case) for case in _cases()]
    order = [item["case_id"] for item in manifests]
    summary = {
        "batch_id": "SOURCE_PASSIVE_V6_V3_DSN_CDB_ONLY_STATIC_20260605",
        "status": "static_generated_awaiting_user_proteus_open_simulation_test",
        "source_feedback": "V5 gave VGDVC; user clarified generated V3 opened and visuals were correct.",
        "method": "Preserve generated V3 ROOT.DSN exactly and test CDB-only source row variants.",
        "test_order": order,
        "cases": [
            {
                "case_id": item["case_id"],
                "description": item["description"],
                "cdb_mode": item["cdb_mode"],
                "marker_counts": item["marker_counts"],
                "object_chunk_len": item["object_chunk_len"],
                "root_cdb_len": item["root_cdb_len"],
                "static_validation_issues": item["static_validation_issues"],
            }
            for item in manifests
        ],
    }
    (TEST_BATCH / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (TEST_BATCH / "README_TEST_ORDER.txt").write_text(
        "Source-passive V6 V3-DSN/CDB-only correction pack.\n\n"
        "This preserves generated V3 visuals. Test in order. T01/T02 are the main R-only CDB repair candidates; T07 is the main RC/RL scale-up candidate if the R-only candidate works.\n\n"
        + "\n".join(f"{idx}. {case_id}/{case_id}.pdsprj" for idx, case_id in enumerate(order, start=1))
        + "\n",
        encoding="utf-8",
    )
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    shutil.copy2(__file__, OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({**summary, "archive": str(archive), "archive_sha256": _sha256_file(archive)}, indent=2))


if __name__ == "__main__":
    main()
