"""Regenerate the donor-audited current-group mixed terminal evidence.

This is an experiment runner only.  It deliberately contains no terminal
geometry, WIRE synthesis, pin mapping, or family exception logic: those are
read from the shared component catalogue and emitted solely by
``component_terminal_placer``.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_catalog import load_component_catalog  # noqa: E402
from proteusgen.component_placer import (  # noqa: E402
    NEW_COMPONENT_MEGA_DONOR,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    ACCEPTED_TERMINAL_FAMILY_ORDER,
    attach_mixed_component_and_catalogue_bidir_terminals_to_project,
)
from proteusgen.pdsprj import read_internal_file  # noqa: E402
from proteusgen.resistor_v9 import _extract_object_chunk  # noqa: E402


OUT_ROOT = ROOT / "experiments" / "current_group_mixed_tail_oracle_v1_temp_2026_07_12"
DONOR = ROOT / NEW_COMPONENT_MEGA_DONOR
CATALOGUE_PATH = ROOT / "knowledge" / "component_catalog_v0.json"
ROUTE_LIMIT_KEY = "current_group_mixed_tail"
SCALES = (1, 9, 15, 23)


@dataclass(frozen=True)
class Case:
    requested_scale: int
    folder: str


def _catalogue_tail_families(catalogue: Any) -> tuple[str, ...]:
    ranked: list[tuple[int, str]] = []
    for part, profile in catalogue.components.items():
        geometry = profile.proteus.get("pin_geometry", {})
        if not isinstance(geometry, dict):
            continue
        raw_rank = geometry.get("mixed_tail_group_rank")
        if raw_rank is None:
            continue
        ranked.append((int(raw_rank), part))
    if not ranked:
        raise ValueError("No catalogue profiles expose mixed-tail group evidence.")
    if len({rank for rank, _part in ranked}) != len(ranked):
        raise ValueError("Mixed-tail catalogue ranks must be unique.")
    return tuple(part for _rank, part in sorted(ranked))


def _cases(scales: tuple[int, ...]) -> tuple[Case, ...]:
    folder_by_scale = {
        1: "01_1x_user_donor_oracle",
        9: "02_9x_full_current_group",
        15: "03_15x_full_current_group",
        23: "04_up_to_23x_full_current_group",
    }
    unsupported = sorted(set(scales) - set(folder_by_scale))
    if unsupported:
        raise ValueError(f"Unsupported current-group scale(s): {unsupported}.")
    return tuple(Case(scale, folder_by_scale[scale]) for scale in scales)


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _payload(scale: int, catalogue_tail_families: tuple[str, ...]) -> dict[str, Any]:
    components = {
        family: scale
        for family in (*ACCEPTED_TERMINAL_FAMILY_ORDER, *catalogue_tail_families)
    }
    return {
        "donor": str(DONOR),
        "components": dict(sorted(components.items())),
        "layout": {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        },
    }


def _uniform_capacity(
    catalogue: Any,
    *,
    requested_scale: int,
    families: tuple[str, ...],
) -> tuple[int, tuple[str, ...], tuple[str, ...]]:
    """Return the locked-mega uniform count and its documented limiting families."""

    known_limits: list[tuple[str, int]] = []
    for family in families:
        profile = catalogue.get_profile(family)
        if profile is None:
            continue
        raw_limit = profile.limits.get("locked_new_components_5x_mega_clean_group_max")
        if isinstance(raw_limit, int) and raw_limit > 0:
            known_limits.append((family, raw_limit))
    raw_catalogue = json.loads(CATALOGUE_PATH.read_text(encoding="utf-8"))
    route_limits = raw_catalogue.get("catalogue_policy", {}).get(
        "proteus_route_limits",
        {},
    )
    route_limit = route_limits.get(ROUTE_LIMIT_KEY, {})
    raw_terminal_limit = route_limit.get("uniform_terminal_max")
    if not isinstance(raw_terminal_limit, int) or raw_terminal_limit <= 0:
        raise ValueError(
            f"Catalogue route limit {ROUTE_LIMIT_KEY!r} lacks a positive "
            "uniform_terminal_max."
        )

    all_limits = [*known_limits, (ROUTE_LIMIT_KEY, raw_terminal_limit)]
    effective_scale = min(requested_scale, *(limit for _source, limit in all_limits))
    limiting = tuple(
        family
        for family, limit in known_limits
        if limit == effective_scale and limit < requested_scale
    )
    limiting_constraints = tuple(
        source
        for source, limit in all_limits
        if limit == effective_scale and limit < requested_scale
    )
    return effective_scale, limiting, limiting_constraints


def _case_paths(case: Case, effective_scale: int) -> tuple[Path, Path, Path]:
    folder = OUT_ROOT / case.folder
    suffix = (
        ""
        if effective_scale == case.requested_scale
        else f"_CAPPED_FROM_{case.requested_scale}X_REQUEST"
    )
    stem = f"ALL_ACCEPTED_CURRENT_GROUP_{effective_scale}X{suffix}"
    return (
        folder / f"{stem}_NO_TERMINAL.pdsprj",
        folder / f"{stem}_TAIL_ORACLE_sa.pdsprj",
        folder / "input.json",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scale",
        action="append",
        type=int,
        choices=SCALES,
        help="Regenerate only this scale; pass more than once for several scales.",
    )
    args = parser.parse_args(argv)
    scales = tuple(args.scale) if args.scale else SCALES
    catalogue = load_component_catalog()
    catalogue_tail_families = _catalogue_tail_families(catalogue)
    all_families = (*ACCEPTED_TERMINAL_FAMILY_ORDER, *catalogue_tail_families)
    expected_per_component_set = (
        len(ACCEPTED_TERMINAL_FAMILY_ORDER) * 2
        + len(catalogue_tail_families) * 3
    )
    summary_path = OUT_ROOT / "summary.json"
    existing_rows: dict[int, dict[str, Any]] = {}
    if summary_path.exists():
        existing = json.loads(summary_path.read_text(encoding="utf-8"))
        for row in existing.get("cases", []):
            if isinstance(row, dict) and isinstance(row.get("requested_scale"), int):
                existing_rows[int(row["requested_scale"])] = row
            elif isinstance(row, dict) and isinstance(row.get("scale"), int):
                existing_rows[int(row["scale"])] = row
    for case in _cases(scales):
        effective_scale, limiting_families, limiting_constraints = _uniform_capacity(
            catalogue,
            requested_scale=case.requested_scale,
            families=all_families,
        )
        bare_output, terminal_output, input_path = _case_paths(case, effective_scale)
        bare_output.parent.mkdir(parents=True, exist_ok=True)
        payload = _payload(effective_scale, catalogue_tail_families)
        _write_json(input_path, payload)
        _write_json(
            bare_output.parent / "capacity.json",
            {
                "requested_uniform_scale": case.requested_scale,
                "effective_uniform_scale": effective_scale,
                "limiting_families": list(limiting_families),
                "limiting_constraints": list(limiting_constraints),
                "capacity_source": "component_catalogue.catalogue_policy.proteus_route_limits",
            },
        )
        placement = generate_component_placement_project(
            payload,
            bare_output,
            full_cdb=True,
        )
        if not placement.valid:
            raise RuntimeError(
                f"{effective_scale}x component placement failed validation."
            )
        report = attach_mixed_component_and_catalogue_bidir_terminals_to_project(
            bare_output,
            terminal_output,
            placement.selected_groups,
            native_terminal_families=ACCEPTED_TERMINAL_FAMILY_ORDER,
            catalogue_terminal_families=catalogue_tail_families,
            use_donor_terminal_labels=False,
        )
        expected = expected_per_component_set * effective_scale
        terminal_chunk = _extract_object_chunk(read_internal_file(terminal_output, "ROOT.DSN"))
        if (
            not report["valid"]
            or report["terminal_count_added"] != expected
            or report["wire_count_added"] != expected
            or terminal_chunk.count(b"$TERBIDIR") != expected
            or terminal_chunk.count(b"\x7fWIRE") != expected
        ):
            raise RuntimeError(
                f"{effective_scale}x mixed terminal validation failed: "
                f"{report['terminal_count_added']} terminals, "
                f"{report['wire_count_added']} wires, expected {expected}."
            )
        _write_json(bare_output.parent / "terminal_report.json", report)
        existing_rows[case.requested_scale] = {
            "requested_scale": case.requested_scale,
            "effective_scale": effective_scale,
            "limiting_families": list(limiting_families),
            "limiting_constraints": list(limiting_constraints),
            "folder": str(bare_output.parent.relative_to(ROOT)),
            "bare_output": str(bare_output.relative_to(ROOT)),
            "terminal_output": str(terminal_output.relative_to(ROOT)),
            "placement_valid": placement.valid,
            "terminal_valid": report["valid"],
            "terminal_count": expected,
            "wire_count": expected,
            "object_stream_finalizer": report["object_stream_finalizer"],
        }
        _write_json(
            summary_path,
            {
                "cases": [
                    existing_rows[scale] for scale in sorted(existing_rows)
                ]
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
