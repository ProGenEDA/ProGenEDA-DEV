"""Regenerate the donor-audited DIL14 quad 2-input logic 1x pack.

This is an experiment runner only. It delegates all component placement,
catalogue pin planning, terminal construction, WIRE emission, and link rebasing
to the existing shared Proteus stages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import (  # noqa: E402
    NEW_COMPONENT_MEGA_DONOR,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_catalogue_pin_bidir_terminals_to_project,
)
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


FAMILIES = ("74HC00", "74HC02", "74HC08", "74HC32", "74HC86", "74HC266")
OUT_ROOT = ROOT / "experiments" / "dil14_quad_2input_logic_terminal_v1_temp_2026_07_13"
SOLO_ROOT = OUT_ROOT / "01_solo_1x"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    rows: list[dict[str, object]] = []
    for index, family in enumerate(FAMILIES, start=1):
        case_dir = SOLO_ROOT / f"S{index:02d}_{family}_1X"
        case_dir.mkdir(parents=True, exist_ok=True)
        base = case_dir / f"S{index:02d}_{family}_1X_NO_TERMINAL.pdsprj"
        terminalized = case_dir / f"S{index:02d}_{family}_1X_CATALOGUE_TERMINAL_sa.pdsprj"
        payload = {
            "donor": str(ROOT / NEW_COMPONENT_MEGA_DONOR),
            "components": {family: 1},
            "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        }
        _write_json(case_dir / "input.json", payload)
        placement = generate_component_placement_project(payload, base, full_cdb=True)
        if not placement.valid:
            raise RuntimeError(f"{family} 1x component placement did not validate.")
        report = attach_catalogue_pin_bidir_terminals_to_project(
            base,
            terminalized,
            placement.selected_groups,
            terminal_families=(family,),
            use_donor_terminal_labels=True,
        )
        expected = 12
        chunk = _extract_object_chunk(read_internal_file(terminalized, "ROOT.DSN"))
        if (
            not report["valid"]
            or report["terminal_count_added"] != expected
            or report["wire_count_added"] != expected
            or chunk.count(b"$TERBIDIR") != expected
            or chunk.count(b"\x7fWIRE") != expected
        ):
            raise RuntimeError(f"{family} 1x shared terminal placement did not validate.")
        _write_json(case_dir / "terminal_report.json", report)
        rows.append(
            {
                "family": family,
                "base": str(base.relative_to(ROOT)),
                "terminalized": str(terminalized.relative_to(ROOT)),
                "placement_valid": placement.valid,
                "terminal_valid": report["valid"],
                "terminal_count": expected,
                "wire_count": expected,
            }
        )
    _write_json(
        OUT_ROOT / "summary.json",
        {
            "families": list(FAMILIES),
            "cases": rows,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
