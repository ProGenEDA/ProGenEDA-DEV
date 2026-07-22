"""Native-label terminal planning separate from direct Altium wire planning."""

from __future__ import annotations

from .pipeline_contracts import PlacedDesign, RoutingPlan, TerminalLabel, TerminalPlan, WirePlan, WireSegment
from .wire_planner import outward_escape


def _terminalized_nets(design: PlacedDesign, wire_plan: WirePlan) -> tuple[str, ...]:
    if wire_plan.routing_mode == "terminal":
        return tuple(sorted(net for net in design.nets if not net.startswith("NC_")))
    if wire_plan.routing_mode == "combination":
        return wire_plan.unresolved_nets
    return ()


def place_terminals(design: PlacedDesign, wire_plan: WirePlan) -> TerminalPlan:
    """Create short native-label stems only for explicitly selected whole nets."""

    endpoints = design.endpoint_locations()
    terminalized = _terminalized_nets(design, wire_plan)
    stems: list[WireSegment] = []
    labels: list[TerminalLabel] = []
    reasons: dict[str, str] = {}
    for net in terminalized:
        members = design.nets[net]
        if net.startswith("GUESS_TERMINAL_"):
            reasons[net] = "input_fixer_guess_terminal"
        elif wire_plan.routing_mode == "terminal":
            reasons[net] = "terminal_mode"
        elif len(members) < 2:
            reasons[net] = "single_endpoint_terminal"
        else:
            reasons[net] = "wire_planner_unroutable"
        for endpoint in members:
            point, component = endpoints[endpoint]
            pin = endpoint.rsplit(".", 1)[1]
            label_point = outward_escape(point, component, pin, 40)
            stems.append(WireSegment(net, point, label_point))
            labels.append(TerminalLabel(net, endpoint, label_point))
    return TerminalPlan(
        terminalized_nets=tuple(sorted(terminalized)),
        stems=tuple(stems),
        labels=tuple(labels),
        reasons=dict(sorted(reasons.items())),
    )


def combine_plans(wire_plan: WirePlan, terminal_plan: TerminalPlan) -> RoutingPlan:
    """Form the final draw plan without giving terminal logic to the wire planner."""

    unresolved = wire_plan.unresolved_nets if wire_plan.routing_mode == "wire" else ()
    return RoutingPlan(
        routing_mode=wire_plan.routing_mode,
        wires=(*wire_plan.wires, *terminal_plan.stems),
        terminalized_nets=terminal_plan.terminalized_nets,
        labels=terminal_plan.labels,
        unresolved_nets=tuple(sorted(unresolved)),
    )
