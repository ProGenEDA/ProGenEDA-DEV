"""Regenerate donor-audited DIL14 catalogue scale packs.

This is an experiment runner only. It delegates all component placement,
catalogue pin planning, terminal construction, WIRE emission, and link rebasing
to the existing shared Proteus stages.
"""

from __future__ import annotations

import argparse
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
from proteusgen.component_catalog import load_component_catalog  # noqa: E402
from proteusgen.component_terminal_placer import (  # noqa: E402
    ACCEPTED_TERMINAL_FAMILY_ORDER,
    attach_component_bidir_terminals_to_project,
    attach_catalogue_pin_bidir_terminals_to_project,
)
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


FAMILIES = ("74HC00", "74HC02", "74HC08", "74HC32", "74HC86", "74HC266")
OUT_ROOT = ROOT / "experiments" / "dil14_quad_2input_logic_terminal_v1_temp_2026_07_13"
REQUESTED_SCALES = (1, 9, 15)
# The ordinary visible shelf creates a third vertical row at 13+ quad-gate
# packages. Proteus then raises VGDVC.DLL once their terminal/WIRE stream is
# loaded. This is a placement-stage canvas width, not terminal logic.
MVP_SHELF_WIDTH = 75_000_000
MIXED_BASELINE_FOLDER = "04_mixed_accepted_two_pin_terminalized_dil14_bare_1x"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_scales(value: str) -> tuple[int, ...]:
    scales = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not scales or any(scale <= 0 for scale in scales):
        raise argparse.ArgumentTypeError("scales must be positive comma-separated integers")
    return scales


def _effective_scale(family: str, requested: int) -> tuple[int, dict[str, object]]:
    profile = load_component_catalog().get_profile(family)
    if profile is None:
        raise ValueError(f"{family} is missing from the component catalogue.")
    raw_limit = profile.limits.get("locked_new_components_5x_mega_clean_group_max")
    if raw_limit is None:
        # Do not invent a family capacity. The component placer itself remains
        # the source-packet availability gate for a requested experimental
        # scale. This lets a newly audited family prove 1x/9x/15x without
        # declaring an unsupported maximum.
        return requested, {
            "requested": requested,
            "effective": requested,
            "limiting_family": None,
            "catalogue_limit": None,
            "catalogue_limit_key": None,
            "capacity_policy": "no_catalogue_cap_declared_component_placer_preflight",
        }
    limit = int(raw_limit)
    effective = min(requested, limit)
    return effective, {
        "requested": requested,
        "effective": effective,
        "limiting_family": family if effective != requested else None,
        "catalogue_limit": limit,
        "catalogue_limit_key": "locked_new_components_5x_mega_clean_group_max",
    }


def _case_stem(index: int, family: str, requested: int, effective: int) -> str:
    if effective == requested:
        return f"S{index:02d}_{family}_{effective}X"
    return f"S{index:02d}_{family}_{effective}X_CAPPED_FROM_{requested}X_REQUEST"


def _generate_mixed_baseline(
    *,
    families: tuple[str, ...],
    out_root: Path,
) -> dict[str, object]:
    """Generate the requested boundary mix without terminalizing new DIL14.

    The accepted two-pin families retain their frozen shared attachment route.
    The newly accepted DIL14 families are intentionally preserved as ordinary
    placed packets, which makes this a clean boundary test before they are
    admitted to the all-terminalized mixed route.
    """

    case_dir = out_root / MIXED_BASELINE_FOLDER
    case_dir.mkdir(parents=True, exist_ok=True)
    components = {
        family: 1
        for family in (*ACCEPTED_TERMINAL_FAMILY_ORDER, *families)
    }
    payload = {
        "donor": str(ROOT / NEW_COMPONENT_MEGA_DONOR),
        "components": dict(sorted(components.items())),
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        },
    }
    base = case_dir / "M001_ACCEPTED_TWO_PIN_TERMINALIZED_DIL14_BARE_1X_NO_TERMINAL.pdsprj"
    terminalized = case_dir / "M001_ACCEPTED_TWO_PIN_TERMINALIZED_DIL14_BARE_1X_sa.pdsprj"
    _write_json(case_dir / "input.json", payload)
    placement = generate_component_placement_project(payload, base, full_cdb=True)
    if not placement.valid:
        raise RuntimeError("DIL14 mixed baseline component placement did not validate.")
    report = attach_component_bidir_terminals_to_project(
        base,
        terminalized,
        placement.selected_groups,
        terminal_families=ACCEPTED_TERMINAL_FAMILY_ORDER,
    )
    expected = len(ACCEPTED_TERMINAL_FAMILY_ORDER) * 2
    chunk = _extract_object_chunk(read_internal_file(terminalized, "ROOT.DSN"))
    preserved_dil14 = sorted(
        {
            str(row.get("component_family"))
            for row in report.get("preserved_groups", [])
            if str(row.get("component_family")) in families
        }
    )
    if (
        not report["valid"]
        or report["terminal_count_added"] != expected
        or report["wire_count_added"] != expected
        or chunk.count(b"$TERBIDIR") != expected
        or chunk.count(b"\x7fWIRE") != expected
        or preserved_dil14 != sorted(families)
    ):
        raise RuntimeError("DIL14 mixed baseline terminal boundary validation failed.")
    _write_json(case_dir / "terminal_report.json", report)
    return {
        "folder": str(case_dir.relative_to(ROOT)),
        "base": str(base.relative_to(ROOT)),
        "terminalized": str(terminalized.relative_to(ROOT)),
        "placement_valid": placement.valid,
        "terminal_valid": report["valid"],
        "terminalized_families": list(ACCEPTED_TERMINAL_FAMILY_ORDER),
        "unterminalized_families": list(families),
        "terminal_count": expected,
        "wire_count": expected,
    }


def main(
    scales: tuple[int, ...] = REQUESTED_SCALES,
    *,
    families: tuple[str, ...] = FAMILIES,
    out_root: Path = OUT_ROOT,
    include_mixed_baseline: bool = True,
) -> int:
    rows: list[dict[str, object]] = []
    for scale_index, requested in enumerate(scales, start=1):
        scale_root = out_root / f"{scale_index:02d}_solo_{requested}x"
        for index, family in enumerate(families, start=1):
            effective, capacity = _effective_scale(family, requested)
            stem = _case_stem(index, family, requested, effective)
            case_dir = scale_root / stem
            case_dir.mkdir(parents=True, exist_ok=True)
            base = case_dir / f"{stem}_NO_TERMINAL.pdsprj"
            terminalized = case_dir / f"{stem}_CATALOGUE_TERMINAL_sa.pdsprj"
            payload = {
                "donor": str(ROOT / NEW_COMPONENT_MEGA_DONOR),
                "components": {family: effective},
                "layout": {
                    "strategy": "beautify",
                    "binary_coordinate_mutation": True,
                    "shelf_width": MVP_SHELF_WIDTH,
                },
            }
            _write_json(case_dir / "input.json", payload)
            _write_json(case_dir / "capacity.json", capacity)
            placement = generate_component_placement_project(payload, base, full_cdb=True)
            if not placement.valid:
                raise RuntimeError(
                    f"{family} requested {requested}x/effective {effective}x component placement failed."
                )
            report = attach_catalogue_pin_bidir_terminals_to_project(
                base,
                terminalized,
                placement.selected_groups,
                terminal_families=(family,),
                use_donor_terminal_labels=True,
            )
            expected = 12 * effective
            chunk = _extract_object_chunk(read_internal_file(terminalized, "ROOT.DSN"))
            if (
                not report["valid"]
                or report["terminal_count_added"] != expected
                or report["wire_count_added"] != expected
                or chunk.count(b"$TERBIDIR") != expected
                or chunk.count(b"\x7fWIRE") != expected
            ):
                raise RuntimeError(
                    f"{family} requested {requested}x/effective {effective}x shared terminal placement failed."
                )
            _write_json(case_dir / "terminal_report.json", report)
            rows.append(
                {
                    "family": family,
                    "requested_scale": requested,
                    "effective_scale": effective,
                    "capacity": capacity,
                    "base": str(base.relative_to(ROOT)),
                    "terminalized": str(terminalized.relative_to(ROOT)),
                    "placement_valid": placement.valid,
                    "terminal_valid": report["valid"],
                    "terminal_count": expected,
                    "wire_count": expected,
                }
            )
    _write_json(
        out_root / "summary.json",
        {
            "families": list(families),
            "requested_scales": list(scales),
            "cases": rows,
            "mixed_baseline": (
                _generate_mixed_baseline(families=families, out_root=out_root)
                if include_mixed_baseline
                else None
            ),
        },
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scales", type=_parse_scales, default=REQUESTED_SCALES)
    parser.add_argument(
        "--families",
        default=",".join(FAMILIES),
        help="comma-separated catalogue families; terminal logic remains shared",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="repository-relative or absolute experiment folder",
    )
    parser.add_argument("--skip-mixed-baseline", action="store_true")
    args = parser.parse_args()
    selected_families = tuple(
        family.strip().upper()
        for family in str(args.families).split(",")
        if family.strip()
    )
    if not selected_families:
        parser.error("--families must contain at least one family")
    selected_root = (
        Path(args.output_root)
        if args.output_root and Path(args.output_root).is_absolute()
        else ROOT / args.output_root
        if args.output_root
        else OUT_ROOT
    )
    raise SystemExit(
        main(
            args.scales,
            families=selected_families,
            out_root=selected_root,
            include_mixed_baseline=not args.skip_mixed_baseline,
        )
    )
