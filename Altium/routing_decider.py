"""Make the wire/terminal/combination policy explicit before route planning."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .pipeline_contracts import ComponentSelection, PipelineError


ROUTING_DECISION_SCHEMA = "progen-altium-routing-decision/v1"


@dataclass(frozen=True)
class RoutingDecision:
    routing_mode: str
    allow_terminal_fallback: bool
    terminalize_all_non_nc: bool
    forced_terminal_nets: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = ROUTING_DECISION_SCHEMA
        return result


def decide_routing(selection: ComponentSelection) -> RoutingDecision:
    """Translate user mode and known safe guesses into explicit planner policy."""

    mode = selection.circuit.routing_mode
    if mode not in {"wire", "terminal", "combination"}:
        raise PipelineError(f"Unsupported routing mode {mode!r}.")
    return RoutingDecision(
        routing_mode=mode,
        allow_terminal_fallback=mode in {"terminal", "combination"},
        terminalize_all_non_nc=mode == "terminal",
        forced_terminal_nets=(selection.guessed_terminal_nets if mode in {"terminal", "combination"} else ()),
    )
