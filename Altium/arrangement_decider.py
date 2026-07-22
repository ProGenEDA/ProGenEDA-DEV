"""Topology-aware square arrangement planning for direct Altium schematics."""

from __future__ import annotations

from collections import defaultdict

from .pipeline_contracts import ArrangementPlan, CoordinateEdit, PlacedDesign
from .source_catalogue import Point


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
