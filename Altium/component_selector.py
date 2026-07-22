"""Resolve canonical components to audited direct-Altium source templates."""

from __future__ import annotations

from .ir import AltiumCircuit, AltiumComponent
from .pipeline_contracts import ComponentSelection, PipelineError, ResolvedComponent
from .source_catalogue import SourceCatalogue, SourceCatalogueError, SourceTemplate, load_source_catalogue


class ComponentSelectionError(PipelineError):
    """A logical component cannot be represented by the locked source catalogue."""


def _resolve_pin_nets(
    component: AltiumComponent,
    template: SourceTemplate,
) -> tuple[dict[str, str], dict[str, str]]:
    pin_nets: dict[str, str] = {}
    logical_map: dict[str, str] = {}
    for logical_pin, net in component.pins.items():
        try:
            designator = template.resolve_pin(logical_pin)
        except SourceCatalogueError as exc:
            raise ComponentSelectionError(str(exc)) from exc
        prior = pin_nets.setdefault(designator, net)
        if prior != net:
            raise ComponentSelectionError(
                f"{component.reference} maps aliases of source pin {designator!r} to both "
                f"{prior!r} and {net!r}."
            )
        logical_map[logical_pin] = designator
    missing = sorted(set(template.pins) - set(pin_nets))
    extra = sorted(set(pin_nets) - set(template.pins))
    if missing or extra:
        detail: list[str] = []
        if missing:
            detail.append(f"missing source pins {missing}")
        if extra:
            detail.append(f"unknown source pins {extra}")
        raise ComponentSelectionError(
            f"{component.reference} must account for every physical source pin: {'; '.join(detail)}."
        )
    return dict(sorted(pin_nets.items())), dict(sorted(logical_map.items()))


def resolve_components(
    circuit: AltiumCircuit,
    *,
    catalogue: SourceCatalogue | None = None,
) -> ComponentSelection:
    """Bind each logical component/pin to one immutable native template."""

    source = catalogue or load_source_catalogue()
    resolved: list[ResolvedComponent] = []
    nets: dict[str, list[str]] = {}
    for component in circuit.components:
        try:
            template = source.resolve(component.kind)
        except SourceCatalogueError as exc:
            raise ComponentSelectionError(str(exc)) from exc
        pin_nets, logical_map = _resolve_pin_nets(component, template)
        resolved_component = ResolvedComponent(component, template, pin_nets, logical_map)
        resolved.append(resolved_component)
        for pin, net in pin_nets.items():
            nets.setdefault(net, []).append(f"{component.reference}.{pin}")
    normalized_nets = {name: tuple(sorted(members)) for name, members in sorted(nets.items())}
    guessed = tuple(sorted(name for name in normalized_nets if name.startswith("GUESS_TERMINAL_")))
    return ComponentSelection(
        circuit=circuit,
        components=tuple(resolved),
        nets=normalized_nets,
        guessed_terminal_nets=guessed,
    )
