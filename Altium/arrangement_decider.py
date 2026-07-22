"""Topology-aware square arrangement planning for direct Altium schematics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from .beautifier import apply_coordinate_edits
from .pipeline_contracts import ArrangementPlan, CoordinateEdit, PlacedDesign
from .placement_validator import validate_placement
from .source_catalogue import Point
from .wire_planner import plan_wires


@dataclass(frozen=True)
class RouteInformedArrangement:
    """Accepted arrangement plus every deterministic route trial."""

    plan: ArrangementPlan
    candidates: tuple[dict[str, Any], ...]

    def json(self) -> dict[str, Any]:
        accepted = next(candidate for candidate in self.candidates if candidate["layout"] == self.plan.layout)
        return {
            "schema": "progen-altium-route-informed-arrangement/v1",
            "accepted_layout": self.plan.layout,
            "accepted_score": accepted["score"],
            "plan": self.plan.json(),
            "candidates": list(self.candidates),
        }


def _component_degrees(design: PlacedDesign) -> dict[str, int]:
    degrees: dict[str, int] = defaultdict(int)
    for net, members in design.nets.items():
        if net.startswith("NC_") or net.startswith("GUESS_TERMINAL_"):
            continue
        references = {member.rsplit(".", 1)[0] for member in members}
        contribution = max(0, len(references) - 1)
        for reference in references:
            degrees[reference] += contribution
    return degrees


def _span(design: PlacedDesign, roots: dict[str, Point]) -> int:
    """Use total Manhattan bounding span as a deterministic routeability proxy."""

    component_by_reference = design.by_reference()
    total = 0
    for net, members in design.nets.items():
        if net.startswith("NC_") or len(members) < 2:
            continue
        points: list[Point] = []
        for endpoint in members:
            reference, pin = endpoint.rsplit(".", 1)
            component = component_by_reference[reference]
            target_root = roots[reference]
            dx = target_root.x - component.root_location.x
            dy = target_root.y - component.root_location.y
            points.append(component.pins[pin].translated(dx, dy))
        total += max(point.x for point in points) - min(point.x for point in points)
        total += max(point.y for point in points) - min(point.y for point in points)
    return total


def decide_arrangement(design: PlacedDesign) -> ArrangementPlan:
    """Choose a compact, near-square order before the wire planner runs.

    The native source catalogue does not yet contain rotation evidence, so this
    stage intentionally produces coordinates only.  High-connectivity parts
    are kept early and close to the centre; equal scores preserve input order
    for deterministic compatibility with the initial placer.
    """

    components = design.components
    degree = _component_degrees(design)
    original_order = {component.reference: index for index, component in enumerate(components)}
    ordered = tuple(
        sorted(
            components,
            key=lambda component: (-degree.get(component.reference, 0), original_order[component.reference]),
        )
    )
    max_width = max(component.bounds.max_x - component.bounds.min_x for component in components)
    max_height = max(component.bounds.max_y - component.bounds.min_y for component in components)
    columns = max(1, int(len(components) ** 0.5))
    if columns * columns < len(components):
        columns += 1
    cell_width = max_width + 320
    cell_height = max_height + 320
    targets: dict[str, Point] = {}
    for index, component in enumerate(ordered):
        row, column = divmod(index, columns)
        targets[component.reference] = Point(
            500 + column * cell_width + component.root_location.x % 2,
            350 + row * cell_height + component.root_location.y % 2,
        )
    current = {component.reference: component.root_location for component in components}
    edits = tuple(
        CoordinateEdit(
            reference=component.reference,
            from_root=component.root_location,
            to_root=targets[component.reference],
            reason=(
                "connectivity_priority_square_grid"
                if component.root_location != targets[component.reference]
                else "baseline_square_grid_retained"
            ),
        )
        for component in components
    )
    before = _span(design, current)
    after = _span(design, targets)
    return ArrangementPlan(
        layout="connectivity_priority_square_grid",
        edits=edits,
        component_order=tuple(component.reference for component in ordered),
        metrics={
            "component_count": len(components),
            "columns": columns,
            "net_span_before_ticks": before,
            "net_span_after_ticks": after,
            "net_span_delta_ticks": after - before,
        },
    )


def _grid_plan(
    design: PlacedDesign,
    ordered_references: Iterable[str],
    *,
    layout: str,
    serpentine: bool = False,
    column_major: bool = False,
) -> ArrangementPlan:
    by_reference = design.by_reference()
    ordered = tuple(by_reference[reference] for reference in ordered_references)
    max_width = max(component.bounds.max_x - component.bounds.min_x for component in ordered)
    max_height = max(component.bounds.max_y - component.bounds.min_y for component in ordered)
    columns = max(1, int(len(ordered) ** 0.5))
    if columns * columns < len(ordered):
        columns += 1
    rows = (len(ordered) + columns - 1) // columns
    cell_width = max_width + 220
    cell_height = max_height + 220
    targets: dict[str, Point] = {}
    for index, component in enumerate(ordered):
        if column_major:
            column, row = divmod(index, rows)
        else:
            row, column = divmod(index, columns)
        if serpentine and row % 2:
            column = columns - 1 - column
        targets[component.reference] = Point(
            420 + column * cell_width + component.root_location.x % 2,
            300 + row * cell_height + component.root_location.y % 2,
        )
    edits = tuple(
        CoordinateEdit(
            reference=component.reference,
            from_root=component.root_location,
            to_root=targets[component.reference],
            reason=layout,
        )
        for component in design.components
    )
    return ArrangementPlan(
        layout=layout,
        edits=edits,
        component_order=tuple(component.reference for component in ordered),
        metrics={
            "component_count": len(ordered),
            "columns": columns,
            "net_span_before_ticks": _span(
                design,
                {component.reference: component.root_location for component in design.components},
            ),
            "net_span_after_ticks": _span(design, targets),
        },
    )


def _route_score(design: PlacedDesign, wires: tuple[Any, ...], unresolved_count: int) -> tuple[int, ...]:
    route_length = sum(
        abs(segment.end.x - segment.start.x) + abs(segment.end.y - segment.start.y)
        for segment in wires
    )
    x_values = [coordinate for component in design.components for coordinate in (component.bounds.min_x, component.bounds.max_x)]
    y_values = [coordinate for component in design.components for coordinate in (component.bounds.min_y, component.bounds.max_y)]
    for segment in wires:
        x_values.extend((segment.start.x, segment.end.x))
        y_values.extend((segment.start.y, segment.end.y))
    width = max(x_values) - min(x_values)
    height = max(y_values) - min(y_values)
    return (
        unresolved_count,
        route_length,
        width * height,
        abs(width - height),
    )


def choose_route_informed_arrangement(
    design: PlacedDesign,
    routing_mode: str,
    *,
    forced_terminal_nets: tuple[str, ...] = (),
) -> RouteInformedArrangement:
    """Run a bounded Beautifier -> Wire Planner loop and keep the best trial."""

    degree = _component_degrees(design)
    input_order = tuple(component.reference for component in design.components)
    connectivity_order = tuple(
        component.reference
        for component in sorted(
            design.components,
            key=lambda component: (-degree.get(component.reference, 0), input_order.index(component.reference)),
        )
    )
    plans = (
        _grid_plan(design, connectivity_order, layout="route_trial_connectivity_square"),
        _grid_plan(design, input_order, layout="route_trial_input_square"),
        _grid_plan(
            design,
            connectivity_order,
            layout="route_trial_connectivity_serpentine",
            serpentine=True,
        ),
        _grid_plan(
            design,
            connectivity_order,
            layout="route_trial_connectivity_columns",
            column_major=True,
        ),
    )
    trials: list[tuple[tuple[int, ...], str, ArrangementPlan, dict[str, Any]]] = []
    for plan in plans:
        candidate_design = apply_coordinate_edits(design, plan).design
        placement = validate_placement(candidate_design)
        if placement.passed:
            wire_plan = plan_wires(
                candidate_design,
                routing_mode,
                forced_terminal_nets=forced_terminal_nets,
            )
            score = _route_score(candidate_design, wire_plan.wires, len(wire_plan.unresolved_nets))
            routed_nets = len(wire_plan.routed_nets)
            unresolved_nets = list(wire_plan.unresolved_nets)
        else:
            score = (10**9, 10**9, 10**9, 10**9)
            routed_nets = 0
            unresolved_nets = sorted(candidate_design.nets)
        report = {
            "layout": plan.layout,
            "score": list(score),
            "placement_passed": placement.passed,
            "routed_net_count": routed_nets,
            "unresolved_nets": unresolved_nets,
            "plan_metrics": dict(plan.metrics),
        }
        trials.append((score, plan.layout, plan, report))
    _, _, accepted, _ = min(trials, key=lambda trial: (trial[0], trial[1]))
    return RouteInformedArrangement(
        plan=accepted,
        candidates=tuple(trial[3] for trial in trials),
    )
