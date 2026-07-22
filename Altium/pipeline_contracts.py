"""Stable, backend-local contracts for the direct Altium generation pipeline.

The pipeline deliberately exchanges immutable, JSON-serializable contracts
instead of passing mutable writer state between stages.  Native source records
remain behind :mod:`Altium.source_catalogue` and :mod:`Altium.native_writer`;
geometry, connectivity, and routing stages only see the facts they need.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .ir import AltiumCircuit, AltiumComponent
from .source_catalogue import Bounds, Point, SourceTemplate


PIPELINE_SCHEMA = "progen-altium-pipeline/v2"
DIRECT_GENERATION_SCHEMA = "progen-altium-direct-generation/v1"


class PipelineError(ValueError):
    """One deterministic Altium pipeline stage could not satisfy its contract."""


@dataclass(frozen=True)
class ResolvedComponent:
    """One logical component bound to one audited Altium source template."""

    component: AltiumComponent
    template: SourceTemplate
    pin_nets: dict[str, str]
    logical_pin_map: dict[str, str]

    def json(self) -> dict[str, Any]:
        return {
            "id": self.component.identifier,
            "reference": self.component.reference,
            "kind": self.component.kind,
            "value": self.component.value,
            "source_template": self.template.key,
            "library_reference": self.template.library_reference,
            "logical_pin_map": dict(sorted(self.logical_pin_map.items())),
            "pins": {
                pin: {
                    "net": net,
                    "name": self.template.pin_names.get(pin, ""),
                    "escape_direction": self.template.pin_directions[pin],
                }
                for pin, net in sorted(self.pin_nets.items())
            },
        }


@dataclass(frozen=True)
class ComponentSelection:
    """Resolved source facts and the source-designator netlist."""

    circuit: AltiumCircuit
    components: tuple[ResolvedComponent, ...]
    nets: dict[str, tuple[str, ...]]
    guessed_terminal_nets: tuple[str, ...]

    def by_reference(self) -> dict[str, ResolvedComponent]:
        return {component.component.reference: component for component in self.components}

    def json(self) -> dict[str, Any]:
        return {
            "schema": "progen-altium-component-selection/v1",
            "components": [component.json() for component in self.components],
            "nets": {name: list(members) for name, members in sorted(self.nets.items())},
            "guessed_terminal_nets": list(self.guessed_terminal_nets),
        }


@dataclass(frozen=True)
class PlacedComponent:
    """Resolved source component with concrete schematic coordinates."""

    identifier: str
    reference: str
    kind: str
    value: str
    source_template: str
    library_reference: str
    owner_index: int
    root_location: Point
    bounds: Bounds
    pins: dict[str, Point]
    pin_names: dict[str, str]
    pin_directions: dict[str, str]
    pin_nets: dict[str, str]
    logical_pin_map: dict[str, str]
    record_count: int

    def translated(self, target_root: Point) -> "PlacedComponent":
        """Return the same native symbol moved without changing its pin identity."""

        dx = target_root.x - self.root_location.x
        dy = target_root.y - self.root_location.y
        return replace(
            self,
            root_location=target_root,
            bounds=self.bounds.translated(dx, dy),
            pins={pin: point.translated(dx, dy) for pin, point in self.pins.items()},
        )

    def json(self) -> dict[str, Any]:
        return {
            "id": self.identifier,
            "reference": self.reference,
            "kind": self.kind,
            "value": self.value,
            "source_template": self.source_template,
            "library_reference": self.library_reference,
            "owner_index": self.owner_index,
            "root_location": self.root_location.json(),
            "bounds": self.bounds.json(),
            "pins": {
                pin: {
                    "position": point.json(),
                    "name": self.pin_names.get(pin, ""),
                    "escape_direction": self.pin_directions[pin],
                    "net": self.pin_nets[pin],
                }
                for pin, point in sorted(self.pins.items())
            },
            "logical_pin_map": dict(sorted(self.logical_pin_map.items())),
            "record_count": self.record_count,
        }


@dataclass(frozen=True)
class PlacedDesign:
    """The EDA-neutral placed-design contract consumed by downstream stages."""

    components: tuple[PlacedComponent, ...]
    nets: dict[str, tuple[str, ...]]

    def by_reference(self) -> dict[str, PlacedComponent]:
        return {component.reference: component for component in self.components}

    def endpoint_locations(self) -> dict[str, tuple[Point, PlacedComponent]]:
        result: dict[str, tuple[Point, PlacedComponent]] = {}
        for component in self.components:
            for pin, point in component.pins.items():
                result[f"{component.reference}.{pin}"] = (point, component)
        return result

    def json(self) -> dict[str, Any]:
        return {
            "schema": "progen-altium-placed-design/v1",
            "components": [component.json() for component in self.components],
            "nets": {name: list(members) for name, members in sorted(self.nets.items())},
        }


@dataclass(frozen=True)
class CoordinateEdit:
    """One coordinate-only arrangement decision; rotation is intentionally absent."""

    reference: str
    from_root: Point
    to_root: Point
    reason: str

    def json(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "from_root": self.from_root.json(),
            "to_root": self.to_root.json(),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ArrangementPlan:
    """Pure coordinate instructions selected before physical routing."""

    layout: str
    edits: tuple[CoordinateEdit, ...]
    component_order: tuple[str, ...]
    metrics: Mapping[str, int]

    def json(self) -> dict[str, Any]:
        return {
            "schema": "progen-altium-arrangement-plan/v1",
            "layout": self.layout,
            "component_order": list(self.component_order),
            "metrics": dict(sorted(self.metrics.items())),
            "edits": [edit.json() for edit in self.edits],
        }


@dataclass(frozen=True)
class WireSegment:
    """One physical rectilinear source-record wire segment."""

    net: str
    start: Point
    end: Point

    def json(self) -> dict[str, Any]:
        return {"net": self.net, "start": self.start.json(), "end": self.end.json()}


@dataclass(frozen=True)
class WirePlan:
    """Pure physical-route output before terminal fallback is applied."""

    routing_mode: str
    wires: tuple[WireSegment, ...]
    routed_nets: tuple[str, ...]
    unresolved_nets: tuple[str, ...]
    skipped_nc_nets: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        return {
            "schema": "progen-altium-wire-plan/v1",
            "routing_mode": self.routing_mode,
            "wires": [wire.json() for wire in self.wires],
            "routed_nets": list(self.routed_nets),
            "unresolved_nets": list(self.unresolved_nets),
            "skipped_nc_nets": list(self.skipped_nc_nets),
        }


@dataclass(frozen=True)
class TerminalLabel:
    """One source-backed native label attached to a physical pin stem."""

    net: str
    endpoint: str
    location: Point

    def json(self) -> dict[str, Any]:
        return {
            "net": self.net,
            "endpoint": self.endpoint,
            "location": self.location.json(),
        }


@dataclass(frozen=True)
class TerminalPlan:
    """Terminal fallback plan independent from native record emission."""

    terminalized_nets: tuple[str, ...]
    stems: tuple[WireSegment, ...]
    labels: tuple[TerminalLabel, ...]
    reasons: Mapping[str, str]

    def json(self) -> dict[str, Any]:
        return {
            "schema": "progen-altium-terminal-plan/v1",
            "terminalized_nets": list(self.terminalized_nets),
            "stems": [stem.json() for stem in self.stems],
            "labels": [label.json() for label in self.labels],
            "reasons": dict(sorted(self.reasons.items())),
        }


@dataclass(frozen=True)
class RoutingPlan:
    """The complete wire/terminal decision consumed by the native writer."""

    routing_mode: str
    wires: tuple[WireSegment, ...]
    terminalized_nets: tuple[str, ...]
    labels: tuple[TerminalLabel, ...]
    unresolved_nets: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        return {
            "schema": "progen-altium-routing-plan/v1",
            "routing_mode": self.routing_mode,
            "wires": [wire.json() for wire in self.wires],
            "terminalized_nets": list(self.terminalized_nets),
            "labels": [label.json() for label in self.labels],
            "unresolved_nets": list(self.unresolved_nets),
        }


@dataclass(frozen=True)
class PipelineResult:
    """Public result of one immutable full-pipeline Altium generation run."""

    run_directory: Path
    project_directory: Path
    project_file: Path
    schematic_file: Path
    project_archive: Path
    internal_archive: Path
    internal_directory: Path
    validation: Any
    components: tuple[PlacedComponent, ...]
    wires: tuple[WireSegment, ...]
    terminalized_nets: tuple[str, ...]
    terminal_labels: tuple[TerminalLabel, ...]
    stage_reports: Mapping[str, Path]

    def json(self) -> dict[str, Any]:
        return {
            "schema": DIRECT_GENERATION_SCHEMA,
            "passed": bool(self.validation.passed),
            "run_directory": str(self.run_directory),
            "project_directory": str(self.project_directory),
            "project_file": str(self.project_file),
            "schematic_file": str(self.schematic_file),
            "project_archive": str(self.project_archive),
            "internal_archive": str(self.internal_archive),
            "internal_directory": str(self.internal_directory),
            "components": [component.json() for component in self.components],
            "wires": [wire.json() for wire in self.wires],
            "terminalized_nets": list(self.terminalized_nets),
            "terminal_labels": [label.json() for label in self.terminal_labels],
            "stage_reports": {name: str(path) for name, path in sorted(self.stage_reports.items())},
            "validation": self.validation.json(),
        }


def expected_physical_contract(
    design: PlacedDesign,
    routing: RoutingPlan,
    *,
    sheet_width_ticks: int,
    sheet_height_ticks: int,
) -> dict[str, Any]:
    """Convert stage contracts into the saved-file validator's public contract."""

    return {
        "schema": "progen-altium-expected-physical-contract/v2",
        "components": [
            {
                "reference": component.reference,
                "value": component.value,
                "source_template": component.source_template,
                "library_reference": component.library_reference,
                "record_count": component.record_count,
                "owner_index": component.owner_index,
                "root_location": {
                    "x_ticks": component.root_location.x,
                    "y_ticks": component.root_location.y,
                },
                "bounds": {
                    "min_x_ticks": component.bounds.min_x,
                    "min_y_ticks": component.bounds.min_y,
                    "max_x_ticks": component.bounds.max_x,
                    "max_y_ticks": component.bounds.max_y,
                },
                "pins": {
                    pin: {
                        "x_ticks": point.x,
                        "y_ticks": point.y,
                        "name": component.pin_names.get(pin, ""),
                        "escape_direction": component.pin_directions[pin],
                    }
                    for pin, point in component.pins.items()
                },
            }
            for component in design.components
        ],
        "nets": {name: list(members) for name, members in sorted(design.nets.items())},
        "terminalized_nets": list(routing.terminalized_nets),
        "wire_geometry": [
            {
                "start": {"x_ticks": wire.start.x, "y_ticks": wire.start.y},
                "end": {"x_ticks": wire.end.x, "y_ticks": wire.end.y},
            }
            for wire in routing.wires
        ],
        "label_geometry": [
            {
                "net": label.net,
                "location": {"x_ticks": label.location.x, "y_ticks": label.location.y},
            }
            for label in routing.labels
        ],
        "sheet": {
            "width_ticks": sheet_width_ticks,
            "height_ticks": sheet_height_ticks,
        },
    }


def as_json(value: Any) -> dict[str, Any]:
    """Serialize small dataclass stage reports without leaking implementation state."""

    if hasattr(value, "json"):
        return value.json()
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    raise PipelineError(f"Cannot serialize pipeline stage result {type(value).__name__}.")
