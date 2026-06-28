"""Generate a donor-native four-plus component mixed validation pack.

This pack intentionally assumes the native pair route is broadly viable and
pushes into larger manual mixed donors without synthesizing CDB rows. Each case
is emitted in two forms:

- exact donor rezip control;
- complete donor packet inserted into E001.

No terminal labels are mutated here. These donors are testing whether complete
native mixed packets survive the route boundary before we attempt general
cross-donor synthesis.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[3]
SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.ic_native import (  # noqa: E402
    IcNativeGenerationBlocked,
    NativeRegistry,
    _extract_object_chunk,
    generate_ic_native_project_from_payload,
    read_internal_file,
)

OUT_ROOT = REPO / "experiments" / "ic_native_quad_mix_v1_temp_2026_06_12"
ARCHIVE = REPO / "experiments" / "IC_NATIVE_QUAD_MIX_V1_TEMP_2026_06_12.zip"


def _safe(text: str) -> str:
    out = "".join(ch if ch.isalnum() else "_" for ch in text)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")[:80] or "case"


def _rel(path: Path) -> str:
    registry = NativeRegistry.load()
    return path.relative_to(registry.root).as_posix()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inventory(path: Path, registry: NativeRegistry) -> dict[str, int]:
    dsn = read_internal_file(path, "ROOT.DSN")
    cdb = read_internal_file(path, "ROOT.CDB")
    chunk = _extract_object_chunk(dsn)
    markers = {component.marker for component in registry.components.values()}
    markers.update(registry.components)
    found: dict[str, int] = {}
    for marker in sorted(markers):
        raw = marker.encode("ascii", errors="ignore")
        count = chunk.count(raw) + cdb.count(raw)
        if count:
            found[marker] = count
    return found


def donor_specs(registry: NativeRegistry) -> list[dict[str, object]]:
    root = registry.root / "squence"
    return [
        {
            "phase": "four_plus_native_mix",
            "name": "TIMING_NE555_7490_4017_4020",
            "donor": root / "MIX_TIMING_NE555_7490_4017_4020.pdsprj",
            "notes": "Four-family timing/counter/divider donor.",
        },
        {
            "phase": "four_plus_native_mix",
            "name": "SYNC_COUNTERS_160_161_163_192_193",
            "donor": root / "MIX_SYNC_COUNTERS_160_161_163_192_193.pdsprj",
            "notes": "Five synchronous/up-down counter donor.",
        },
        {
            "phase": "four_plus_native_mix",
            "name": "FLIPFLOP_REGISTERS_74_76_4027_174_273",
            "donor": root / "MIX_FLIPFLOP_REGISTERS_74HC74_74HC76_4027_74HC174_74HC273.pdsprj",
            "notes": "Five flip-flop/register donor.",
        },
        {
            "phase": "four_plus_native_analog_mix",
            "name": "ANALOG_LM741_NE555_NPN_PNP_ECAP_RCL",
            "donor": root / "MIX_ANALOG_LM741_NE555_NPN_PNP_ELECCAP_RCL.pdsprj",
            "notes": "Analog/native/basic component donor with R/C/L and CAP-ELEC.",
        },
        {
            "phase": "display_driver_mix",
            "name": "FOUR_7447_WITH_7SEG_COM_ANODE",
            "donor": root / "4_7segcomanodewithbiderand4_7447.pdsprj",
            "notes": "Display-driver donor with bidirectional display terminals.",
        },
        {
            "phase": "model_issue_isolation_pair",
            "name": "PAIR_7490_74HC4060",
            "donor": root / "PAIR_7490_74HC4060.pdsprj",
            "notes": "4060-adjacent pair control for the no-model reports.",
        },
        {
            "phase": "model_issue_isolation_pair",
            "name": "PAIR_74HC4040_74HC4060",
            "donor": root / "PAIR_74HC4040_74HC4060.pdsprj",
            "notes": "4060-adjacent pair control for the no-model reports.",
        },
        {
            "phase": "model_issue_isolation_pair",
            "name": "PAIR_7490_74HC4520",
            "donor": root / "PAIR_7490_74HC4520.pdsprj",
            "notes": "4520-adjacent pair control for the no-model reports.",
        },
        {
            "phase": "model_issue_isolation_pair",
            "name": "PAIR_4518_74HC4520",
            "donor": root / "PAIR_4518_74HC4520.pdsprj",
            "notes": "4520-adjacent pair control for the no-model reports.",
        },
    ]


def case_specs(registry: NativeRegistry) -> list[dict[str, object]]:
    cases: list[dict[str, object]] = []
    for index, spec in enumerate(donor_specs(registry)):
        donor = Path(spec["donor"])
        if not donor.exists():
            raise FileNotFoundError(donor)
        inventory = _inventory(donor, registry)
        base = _safe(str(spec["name"]))
        for mode in ("EXACT", "E001_PACKET"):
            cases.append(
                {
                    "phase": spec["phase"],
                    "mode": mode,
                    "inventory": inventory,
                    "notes": spec["notes"],
                    "payload": {
                        "schema": "ic-native-circuit-ir/v0.1",
                        "case_id": f"Q{len(cases):03d}_{base}_{mode}",
                        "title": f"{spec['name']} {mode}",
                        "donor": _rel(donor),
                        "exact_rezip": mode == "EXACT",
                    },
                }
            )
    return cases


def write_archive() -> str:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
            info.date_time = (2026, 6, 12, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            zf.writestr(info, file_path.read_bytes())
    return str(ARCHIVE)


def main() -> int:
    registry = NativeRegistry.load()
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    specs = case_specs(registry)
    manifests: list[dict[str, object]] = []
    blocks: list[dict[str, object]] = []
    for spec in specs:
        payload = dict(spec["payload"])
        case_dir = OUT_ROOT / str(payload["case_id"])
        try:
            result = generate_ic_native_project_from_payload(payload, case_dir)
            manifests.append(
                {
                    "phase": spec["phase"],
                    "mode": spec["mode"],
                    "declared_inventory": spec["inventory"],
                    "notes": spec["notes"],
                    **result.manifest,
                }
            )
        except IcNativeGenerationBlocked as exc:
            blocks.append(
                {
                    "phase": spec["phase"],
                    "mode": spec["mode"],
                    "case_id": payload["case_id"],
                    "report": exc.report.as_dict(),
                }
            )

    static_issue_cases = {
        str(item["case_id"]): item.get("static_validation_issues", [])
        for item in manifests
        if item.get("static_validation_issues")
    }
    marker_warning_cases = {
        str(item["case_id"]): item.get("marker_expectation_warnings", [])
        for item in manifests
        if item.get("marker_expectation_warnings")
    }
    phase_counts: dict[str, int] = {}
    for item in manifests:
        phase = str(item["phase"])
        phase_counts[phase] = phase_counts.get(phase, 0) + 1

    archive = write_archive()
    summary = {
        "pack": "IC_NATIVE_QUAD_MIX_V1_TEMP_2026_06_12",
        "case_count": len(specs),
        "generated_case_count": len(manifests),
        "blocked_cases": blocks,
        "phase_counts": phase_counts,
        "static_issue_cases": static_issue_cases,
        "marker_warning_cases": marker_warning_cases,
        "archive": archive,
        "archive_sha256": _sha256_file(ARCHIVE),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "case_inputs.json").write_text(json.dumps(specs, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not blocks and not static_issue_cases else 2


if __name__ == "__main__":
    raise SystemExit(main())
