"""Generate focused real 7490 circuits with locked passive/source records.

This pack stays on the accepted one-family path. Every case uses the
Proteus-created ``SQU/4_7490withRLC.pdsprj`` donor, then mutates only
bidirectional terminal labels to create useful counter/reset/filter circuits.

No cross-donor CDB synthesis is performed.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_7490_real_circuits_v1_temp_2026_06_12"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "IC_7490_REAL_CIRCUITS_V1_TEMP_2026_06_12.zip"
DONOR = "SQU/4_7490withRLC.pdsprj"

from proteusgen.ic_native import NativeRegistry, bidir_events, generate_ic_native_project_from_payload, read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


def _sha256_bytes(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


def four_7490_components(connections: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {"ref": f"U{index}", "part": "74HC90", "connections": conn}
        for index, conn in enumerate(connections, start=1)
    ]


def counter(ref_index: int, *, clk: str, ckb: str, rst_a: str = "G0", rst_b: str = "G0") -> dict[str, str]:
    prefix = f"C{ref_index}"
    return {
        "CKA": clk,
        "CKB": ckb,
        "R01": rst_a,
        "R02": rst_b,
        "R91": "G0",
        "R92": "G0",
        "Q0": f"{prefix}A",
        "Q1": f"{prefix}B",
        "Q2": f"{prefix}C",
        "Q3": f"{prefix}D",
    }


def with_rlc(component4: dict[str, str], *, a1: str = "V0", y0: str, p1: str, p2: str, b1: str = "G0") -> dict[str, str]:
    out = dict(component4)
    # The donor assigns the trailing RLC bider terminals to the last component
    # range. Mutating these signal names is safe and preserves donor geometry.
    out.update({"A1": a1, "Y0": y0, "P1": p1, "P2": p2, "B1": b1})
    return out


def payload(case_id: str, title: str, connections: list[dict[str, str]], description: str) -> dict[str, object]:
    return {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": case_id,
        "title": title,
        "description": description,
        "donor": DONOR,
        "components": four_7490_components(connections),
        "layout": {
            "strategy": "beautify",
            "mode": "native_ic_compact_donor_grid",
            "notes": "Preserve the Proteus donor 4-counter grid and compact labels around same-name nets.",
        },
    }


CASES = [
    payload(
        "T01_MOD10_OUTPUT_RLC_FILTER",
        "7490 decade divider with filtered Q3 monitor",
        [
            counter(1, clk="CLK", ckb="C1A"),
            counter(2, clk="CLK2", ckb="C2A"),
            counter(3, clk="CLK3", ckb="C3A"),
            with_rlc(counter(4, clk="CLK4", ckb="C4A"), y0="C1D", p1="F1", p2="G0"),
        ],
        "U1 is wired as a decade divider by feeding Q0 back to CKB. Its Q3 output drives the donor RLC monitor/load path.",
    ),
    payload(
        "T02_DIVIDE_BY_100_CASCADE_WITH_RLC_LOAD",
        "Two-stage 7490 divide-by-100 cascade with final RLC load",
        [
            counter(1, clk="CLK", ckb="C1A"),
            counter(2, clk="C1D", ckb="C2A"),
            counter(3, clk="TAP", ckb="C3A"),
            with_rlc(counter(4, clk="TAP2", ckb="C4A"), y0="C2D", p1="OUT", p2="G0"),
        ],
        "U1 and U2 form a divide-by-100 chain; the final decade output is loaded through the RLC chain for filtered observation.",
    ),
    payload(
        "T03_FOUR_DECADE_RIPPLE_CHAIN",
        "Four decade ripple divider with analog output tap",
        [
            counter(1, clk="CLK", ckb="C1A"),
            counter(2, clk="C1D", ckb="C2A"),
            counter(3, clk="C2D", ckb="C3A"),
            with_rlc(counter(4, clk="C3D", ckb="C4A"), y0="C4D", p1="AOUT", p2="G0"),
        ],
        "Four 7490 stages create a long division chain; the last stage Q3 is passed through the passive output network.",
    ),
    payload(
        "T04_RC_POWER_ON_RESET_BUS",
        "Power-on reset shaped by passive network",
        [
            counter(1, clk="CLK", ckb="C1A", rst_a="RST", rst_b="RST"),
            counter(2, clk="C1D", ckb="C2A", rst_a="RST", rst_b="RST"),
            counter(3, clk="C2D", ckb="C3A", rst_a="RST", rst_b="RST"),
            with_rlc(counter(4, clk="C3D", ckb="C4A", rst_a="RST", rst_b="RST"), y0="V0", p1="RST", p2="G0"),
        ],
        "The passive network pulls the shared reset bus from V0 toward G0; all four counters share the reset terminals.",
    ),
    payload(
        "T05_CLOCK_INPUT_CONDITIONER",
        "RLC-conditioned clock input feeding a decade chain",
        [
            counter(1, clk="CLKF", ckb="C1A"),
            counter(2, clk="C1D", ckb="C2A"),
            counter(3, clk="C2D", ckb="C3A"),
            with_rlc(counter(4, clk="C3D", ckb="C4A"), y0="CLK", p1="CLKF", p2="G0"),
        ],
        "The donor RLC path conditions the external clock node before it reaches the first counter input.",
    ),
    payload(
        "T06_MOD6_COUNTER_WITH_FILTERED_RESET",
        "Modulo-6 reset using decoded counter outputs and passive reset shaping",
        [
            counter(1, clk="CLK", ckb="C1A", rst_a="C1B", rst_b="C1C"),
            counter(2, clk="C1D", ckb="C2A", rst_a="RST", rst_b="RST"),
            counter(3, clk="C2D", ckb="C3A", rst_a="RST", rst_b="RST"),
            with_rlc(counter(4, clk="C3D", ckb="C4A", rst_a="RST", rst_b="RST"), y0="C1C", p1="RST", p2="G0"),
        ],
        "U1 uses its Q1/Q2 outputs to form a modulo-6 reset condition; the same reset line is passively shaped for later stages.",
    ),
    payload(
        "T07_BCD_TAPS_WITH_SHARED_RESET_AND_LOAD",
        "BCD tap bank with shared reset and filtered monitor output",
        [
            counter(1, clk="CLK", ckb="C1A", rst_a="RST", rst_b="RST"),
            counter(2, clk="C1D", ckb="C2A", rst_a="RST", rst_b="RST"),
            counter(3, clk="C2D", ckb="C3A", rst_a="RST", rst_b="RST"),
            with_rlc(counter(4, clk="C3D", ckb="C4A", rst_a="RST", rst_b="RST"), y0="C2D", p1="MON", p2="G0"),
        ],
        "All BCD taps remain exposed while a shared reset bus and a filtered monitor output provide practical counter-bank wiring.",
    ),
    payload(
        "T08_DUAL_RATE_OUTPUT_MONITOR",
        "Dual-rate divider taps with passive output averaging",
        [
            counter(1, clk="CLK", ckb="C1A"),
            counter(2, clk="C1D", ckb="C2A"),
            counter(3, clk="C1A", ckb="C3A"),
            with_rlc(counter(4, clk="C2D", ckb="C4A"), y0="C3D", p1="AVG", p2="G0"),
        ],
        "Two divider rates are exposed from the same input clock; the passive path monitors the slower branch output.",
    ),
]


def compact_ic_layout_plan(case_id: str, manifest: dict[str, object], object_chunk: bytes) -> dict[str, object]:
    events = bidir_events(object_chunk)
    labels = [event.label for event in events]
    bounds = {
        "min_x": min(event.symbol_x for event in events),
        "max_x": max(event.symbol_x for event in events),
        "min_y": min(event.symbol_y for event in events),
        "max_y": max(event.symbol_y for event in events),
    }
    same_name = {label: labels.count(label) for label in sorted(set(labels)) if labels.count(label) > 1}
    return {
        "layout_version": "native-ic-compact/v0.1",
        "case_id": case_id,
        "strategy": "donor_native_compact_same_name_nets",
        "notes": [
            "Complete Proteus donor coordinates are preserved.",
            "Net labels are compact ASCII names to reduce IC visual clutter.",
            "Same-name labels are intentionally reused for electrical connectivity and readability.",
            "No arbitrary standalone wires or cross-donor component placement is introduced.",
        ],
        "bounds": bounds,
        "terminal_count": len(events),
        "max_label_length": max(len(label) for label in labels),
        "same_name_net_counts": same_name,
        "method": manifest.get("method"),
    }


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
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests: list[dict[str, object]] = []
    blocked: list[dict[str, object]] = []
    for item in CASES:
        case_id = str(item["case_id"])
        case_dir = OUT_ROOT / case_id
        try:
            result = generate_ic_native_project_from_payload(item, case_dir)
            dsn = read_internal_file(result.output_path, "ROOT.DSN")
            cdb = read_internal_file(result.output_path, "ROOT.CDB")
            chunk = _extract_object_chunk(dsn)
            layout_plan = compact_ic_layout_plan(case_id, result.manifest, chunk)
            layout_path = case_dir / "ic_layout_plan.json"
            layout_path.write_text(json.dumps(layout_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifest = dict(result.manifest)
            manifest["real_circuit_description"] = item["description"]
            manifest["ic_layout_plan_path"] = layout_path.name
            manifest["ic_layout"] = layout_plan
            manifest["root_cdb_sha256"] = _sha256_bytes(cdb)
            result.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            manifests.append(manifest)
        except Exception as exc:  # noqa: BLE001 - temporary pack summary must keep blocked cases.
            blocked.append({"case_id": case_id, "error": repr(exc), "payload": item})

    static_issue_cases = {
        str(item["case_id"]): item.get("static_validation_issues", [])
        for item in manifests
        if item.get("static_validation_issues")
    }
    archive = write_archive()
    summary = {
        "pack": "IC_7490_REAL_CIRCUITS_V1_TEMP_2026_06_12",
        "generated_case_count": len(manifests),
        "blocked_cases": blocked,
        "static_issue_cases": static_issue_cases,
        "cases": [item["case_id"] for item in manifests],
        "archive": archive,
        "archive_sha256": _sha256_bytes(Path(archive).read_bytes()),
        "method": "single_same_family_4x_7490_with_rlc_donor_and_compact_same_name_bider_labels",
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
