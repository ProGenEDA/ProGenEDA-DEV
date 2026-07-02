"""Terminal/label placement foundation for KiCad pipeline routing.

This stage owns terminal-style connectivity. For KiCad schematics the current
terminal backend is local labels with short pin stubs. The strict wire path must
not call this implicitly; combination/terminal routing can use this explicitly.
"""

from __future__ import annotations

from typing import Any

from .wire_planner import plan_wire_routes


TERMINAL_PLACER_VERSION = "progen-kicad-terminal-placer/v0.1"


def place_terminals(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a pure JSON terminal plan.

    The plan deliberately mirrors the wire-plan endpoint contract so a KiCad
    backend can draw short terminal stubs/labels from the same resolved pin
    coordinates. It does not generate schematic objects itself.
    """

    terminal_config = dict(config or {})
    terminal_config["routing_mode"] = "terminal"
    wire_like_plan = plan_wire_routes(placement, circuit, config=terminal_config)
    return {
        "schema": "progen-kicad-terminal-plan/v0.1",
        "stage": "terminal_placer",
        "version": TERMINAL_PLACER_VERSION,
        "routing_mode": "terminal",
        "terminal_backend": "kicad_local_labels",
        "contract": {
            "owns_local_labels": True,
            "wire_mode_must_not_use_this_as_fallback": True,
        },
        "nets": wire_like_plan.get("nets", {}),
        "metrics": wire_like_plan.get("metrics", {}),
        "warnings": wire_like_plan.get("warnings", []),
    }
