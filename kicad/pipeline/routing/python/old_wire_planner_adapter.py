"""Compatibility wrapper for callers migrating from ``wire_planner.plan_wiring``.

The old module remains available during migration. New v2 callers should use
``routing_orchestrator.plan_wiring_v2`` directly; this wrapper exists so Phase 9
can flip old entry points without changing downstream JSON consumers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .routing_orchestrator import plan_wiring_v2


def plan_wiring(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return plan_wiring_v2(placement, circuit, config=config, wire_config=wire_config)


def write_wire_planner_jsons_v2(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    out_dir: str | Path,
    *,
    config: dict[str, Any] | None = None,
    wire_config: dict[str, Any] | None = None,
) -> dict[str, Path]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    planned = plan_wiring_v2(placement, circuit, config=config, wire_config=wire_config)
    paths = {
        "coordinate_plan": out_path / "wire_coordinate_plan.json",
        "routing_placement": out_path / "wire_routing_placement.json",
        "arrangement_selection": out_path / "wire_arrangement_selection.json",
        "wire_plan": out_path / "wire_plan.json",
        "validation_report": out_path / "validation_report.json",
    }
    paths["coordinate_plan"].write_text(json.dumps(planned["coordinate_plan"], indent=2), encoding="utf-8")
    paths["routing_placement"].write_text(json.dumps(planned["routing_placement"], indent=2), encoding="utf-8")
    paths["arrangement_selection"].write_text(json.dumps(planned["arrangement_selection"], indent=2), encoding="utf-8")
    paths["wire_plan"].write_text(json.dumps(planned["wire_plan"], indent=2), encoding="utf-8")
    paths["validation_report"].write_text(json.dumps(planned["validation_report"], indent=2), encoding="utf-8")
    return paths
