"""Deterministic source-backed initial placement for direct Altium schematics."""

from __future__ import annotations

from .pipeline_contracts import ComponentSelection, PipelineError, PlacedComponent, PlacedDesign
from .source_catalogue import Point


class ComponentPlacementError(PipelineError):
    """The initial non-overlapping component placement could not be formed."""


def place_components(selection: ComponentSelection) -> PlacedDesign:
    """Create the baseline square grid before topology-aware arrangement.

    This stage has no routing behavior and writes no native records.  It is
    intentionally simple so a later placer can replace it while preserving the
    same :class:`PlacedDesign` contract.
    """

    resolved = selection.components
    if not resolved:
        raise ComponentPlacementError("A direct Altium project needs at least one resolved component.")
    max_width = max(item.template.bounds.max_x - item.template.bounds.min_x for item in resolved)
    max_height = max(item.template.bounds.max_y - item.template.bounds.min_y for item in resolved)
    columns = max(1, int(len(resolved) ** 0.5))
    if columns * columns < len(resolved):
        columns += 1
    cell_width = max_width + 320
    cell_height = max_height + 320
    base_x = 500
    base_y = 350
    owner_index = 1
    components: list[PlacedComponent] = []
    for index, item in enumerate(resolved):
        row, column = divmod(index, columns)
        template = item.template
        root = Point(
            base_x + column * cell_width + template.root_location.x % 2,
            base_y + row * cell_height + template.root_location.y % 2,
        )
        dx = root.x - template.root_location.x
        dy = root.y - template.root_location.y
        components.append(
            PlacedComponent(
                identifier=item.component.identifier,
                reference=item.component.reference,
                kind=item.component.kind,
                value=item.component.value,
                source_template=template.key,
                library_reference=template.library_reference,
                owner_index=owner_index,
                root_location=root,
                bounds=template.bounds.translated(dx, dy),
                pins={pin: point.translated(dx, dy) for pin, point in template.pins.items()},
                pin_directions=dict(template.pin_directions),
                pin_nets=dict(item.pin_nets),
                logical_pin_map=dict(item.logical_pin_map),
                record_count=template.record_count,
            )
        )
        owner_index += template.record_count
    return PlacedDesign(components=tuple(components), nets=dict(selection.nets))
