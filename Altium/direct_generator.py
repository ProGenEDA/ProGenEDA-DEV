"""Direct native Altium schematic/project generator.

This module is intentionally separate from ``conversion_engine.py``.  It
consumes canonical JSON, resolves source-backed Altium component blocks, emits
a fresh native ASCII ``.SchDoc`` and a minimal ``.PrjPcb``, then validates the
saved document's actual pin/wire graph.  EasyEDA files are never generated or
consumed along this path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping
from uuid import NAMESPACE_URL, uuid5
import zipfile

from .direct_validator import DirectValidationReport, validate_direct_schematic
from .ir import AltiumCircuit, AltiumComponent, CircuitInputError, load_circuit
from .source_catalogue import Bounds, Point, SourceCatalogue, SourceCatalogueError, SourceTemplate, load_source_catalogue


GENERATOR_SCHEMA = "progen-altium-direct-generation/v1"
_SAFE_TEXT = re.compile(r"[|\r\n\x00]")
_COORDINATE_KEY = re.compile(r"^(?:LOCATION|CORNER)\.(X|Y)$|^([XY])\d+$")


class DirectGenerationError(ValueError):
    """The source-backed direct Altium route cannot produce a valid project."""


@dataclass(frozen=True)
class GeneratedComponent:
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
    pin_directions: dict[str, str]
    pin_nets: dict[str, str]
    logical_pin_map: dict[str, str]
    record_count: int

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
                    "escape_direction": self.pin_directions[pin],
                    "net": self.pin_nets[pin],
                }
                for pin, point in sorted(self.pins.items())
            },
            "logical_pin_map": dict(sorted(self.logical_pin_map.items())),
            "record_count": self.record_count,
        }


@dataclass(frozen=True)
class WireSegment:
    net: str
    start: Point
    end: Point

    def json(self) -> dict[str, Any]:
        return {"net": self.net, "start": self.start.json(), "end": self.end.json()}


@dataclass(frozen=True)
class TerminalLabel:
    """One source-backed Altium net label attached to a short pin stem."""

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
class RoutingPlan:
    wires: tuple[WireSegment, ...]
    terminalized_nets: tuple[str, ...]
    labels: tuple[TerminalLabel, ...]


@dataclass(frozen=True)
class DirectGenerationResult:
    run_directory: Path
    project_directory: Path
    project_file: Path
    schematic_file: Path
    project_archive: Path
    internal_directory: Path
    validation: DirectValidationReport
    components: tuple[GeneratedComponent, ...]
    wires: tuple[WireSegment, ...]
    terminalized_nets: tuple[str, ...]
    terminal_labels: tuple[TerminalLabel, ...]

    def json(self) -> dict[str, Any]:
        return {
            "schema": GENERATOR_SCHEMA,
            "passed": self.validation.passed,
            "run_directory": str(self.run_directory),
            "project_directory": str(self.project_directory),
            "project_file": str(self.project_file),
            "schematic_file": str(self.schematic_file),
            "project_archive": str(self.project_archive),
            "internal_directory": str(self.internal_directory),
            "components": [component.json() for component in self.components],
            "wires": [wire.json() for wire in self.wires],
            "terminalized_nets": list(self.terminalized_nets),
            "terminal_labels": [label.json() for label in self.terminal_labels],
            "validation": self.validation.json(),
        }


def _clean_text(value: str, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise DirectGenerationError(f"{field} must not be empty.")
    if _SAFE_TEXT.search(text):
        raise DirectGenerationError(f"{field} contains an unsupported record delimiter.")
    return text


def _field(record: str, name: str) -> str | None:
    match = re.search(rf"\|{re.escape(name)}=([^|]*)", record)
    return match.group(1) if match else None


def _replace_field(record: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\|{re.escape(name)}=)[^|]*")
    if not pattern.search(record):
        return record
    return pattern.sub(lambda match: f"{match.group(1)}{value}", record)


def _remove_field(record: str, name: str) -> str:
    return re.sub(rf"\|{re.escape(name)}=[^|]*", "", record)


def _set_field(record: str, name: str, value: str) -> str:
    if _field(record, name) is not None:
        return _replace_field(record, name, value)
    return f"{record}|{name}={value}"


def _coordinate_axis(key: str) -> str | None:
    match = _COORDINATE_KEY.match(key)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _translate_record_coordinates(record: str, dx: int, dy: int) -> str:
    if dx % 2 or dy % 2:
        raise DirectGenerationError("Direct source templates may only be translated by whole document units.")
    tokens = record.split("|")
    translated: list[str] = []
    for token in tokens:
        if "=" not in token:
            translated.append(token)
            continue
        key, value = token.split("=", 1)
        axis = _coordinate_axis(key)
        if axis is None:
            translated.append(token)
            continue
        try:
            delta = dx // 2 if axis == "X" else dy // 2
            translated.append(f"{key}={int(value) + delta}")
        except ValueError:
            translated.append(token)
    return "|".join(translated)


def _set_coordinate(record: str, name: str, value: int) -> str:
    whole, remainder = divmod(value, 2)
    result = _set_field(record, name, str(whole))
    fraction_name = f"{name}_FRAC"
    if remainder:
        return _set_field(result, fraction_name, "50000")
    return _remove_field(result, fraction_name)


def _replace_owner_indexes(record: str, owner_delta: int) -> str:
    value = _field(record, "OWNERINDEX")
    if value is None:
        return record
    try:
        owner = int(value)
    except ValueError:
        return record
    if owner < 0:
        return record
    return _replace_field(record, "OWNERINDEX", str(owner + owner_delta))


def _component_unique_id(index_in_sheet: int) -> str:
    """Allocate the compact `pge<number>` shape used by the native source."""

    return f"pge{index_in_sheet}"


def _rewrite_component_records(
    template: SourceTemplate,
    component: AltiumComponent,
    *,
    owner_index: int,
    target_root: Point,
    index_start: int,
) -> tuple[tuple[str, ...], int]:
    """Clone one complete source block while preserving its internal hierarchy."""

    reference = _clean_text(component.reference, "component reference")
    value = _clean_text(component.value, f"value for {reference}")
    dx = target_root.x - template.root_location.x
    dy = target_root.y - template.root_location.y
    owner_delta = owner_index - template.source_owner_index
    index_map: dict[str, str] = {}
    next_index = index_start
    records: list[str] = []
    for source_record_index, source_record in enumerate(template.records):
        record = _replace_owner_indexes(source_record, owner_delta)
        source_owner = _field(source_record, "OWNERINDEX")
        translates_with_component = source_record_index == 0 or source_owner == str(template.source_owner_index)
        if translates_with_component:
            record = _translate_record_coordinates(record, dx, dy)

        source_index = _field(source_record, "INDEXINSHEET")
        if source_index is not None:
            replacement = index_map.get(source_index)
            if replacement is None:
                replacement = str(next_index)
                index_map[source_index] = replacement
                next_index += 1
            record = _replace_field(record, "INDEXINSHEET", replacement)

        if source_record_index == 0:
            record = _replace_field(record, "UNIQUEID", _component_unique_id(index_start))

        name = _field(source_record, "NAME")
        if name == "Designator":
            record = _replace_field(record, "TEXT", reference)
        elif name in {"Value", "Comment"}:
            record = _replace_field(record, "TEXT", value)
        records.append(record)
    return tuple(records), next_index


def _component_pin_nets(component: AltiumComponent, template: SourceTemplate) -> tuple[dict[str, str], dict[str, str]]:
    pin_nets: dict[str, str] = {}
    logical_map: dict[str, str] = {}
    for logical_pin, net in component.pins.items():
        designator = template.resolve_pin(logical_pin)
        prior = pin_nets.setdefault(designator, net)
        if prior != net:
            raise DirectGenerationError(
                f"{component.reference} maps multiple input pins to source pin {designator}: "
                f"{prior!r} and {net!r}."
            )
        logical_map[logical_pin] = designator
    missing = sorted(set(template.pins) - set(pin_nets))
    extra = sorted(set(pin_nets) - set(template.pins))
    if missing or extra:
        details: list[str] = []
        if missing:
            details.append(f"missing source pins {missing}")
        if extra:
            details.append(f"unknown source pins {extra}")
        raise DirectGenerationError(
            f"{component.reference} must account for every physical source pin: {'; '.join(details)}."
        )
    return pin_nets, logical_map


def _place_components(circuit: AltiumCircuit, catalogue: SourceCatalogue) -> tuple[GeneratedComponent, ...]:
    resolved: list[tuple[AltiumComponent, SourceTemplate, dict[str, str], dict[str, str]]] = []
    for component in circuit.components:
        template = catalogue.resolve(component.kind)
        pin_nets, logical_map = _component_pin_nets(component, template)
        resolved.append((component, template, pin_nets, logical_map))
    if not resolved:
        raise DirectGenerationError("A direct Altium project needs at least one source-backed component.")

    max_width = max(template.bounds.max_x - template.bounds.min_x for _, template, _, _ in resolved)
    max_height = max(template.bounds.max_y - template.bounds.min_y for _, template, _, _ in resolved)
    columns = max(1, int(len(resolved) ** 0.5))
    if columns * columns < len(resolved):
        columns += 1
    cell_width = max_width + 320
    cell_height = max_height + 320
    base_x = 500
    base_y = 350
    owner_index = 1
    components: list[GeneratedComponent] = []
    for index, (component, template, pin_nets, logical_map) in enumerate(resolved):
        row, column = divmod(index, columns)
        target_root = Point(
            base_x + column * cell_width + template.root_location.x % 2,
            base_y + row * cell_height + template.root_location.y % 2,
        )
        dx = target_root.x - template.root_location.x
        dy = target_root.y - template.root_location.y
        pins = {
            designator: point.translated(dx, dy) for designator, point in template.pins.items()
        }
        components.append(
            GeneratedComponent(
                identifier=component.identifier,
                reference=component.reference,
                kind=component.kind,
                value=component.value,
                source_template=template.key,
                library_reference=template.library_reference,
                owner_index=owner_index,
                root_location=target_root,
                bounds=template.bounds.translated(dx, dy),
                pins=dict(sorted(pins.items())),
                pin_directions=dict(sorted(template.pin_directions.items())),
                pin_nets=dict(sorted(pin_nets.items())),
                logical_pin_map=dict(sorted(logical_map.items())),
                record_count=template.record_count,
            )
        )
        owner_index += template.record_count

    for index, left in enumerate(components):
        for right in components[index + 1 :]:
            if left.bounds.intersects(right.bounds):
                raise DirectGenerationError(
                    f"Deterministic placement collision between {left.reference} and {right.reference}."
                )
    return tuple(components)


def _segment_has_invalid_body_contact(
    segment: WireSegment,
    bounds: Bounds,
    allowed_points: set[Point],
) -> bool:
    """Return whether a segment touches a body anywhere except an allowed pin.

    A one-point touch is valid only at the exact source/target pin. A span
    along or through a body is always invalid, including one that starts at a
    pin and then crosses the component.
    """

    if segment.start.x == segment.end.x:
        if not bounds.min_x <= segment.start.x <= bounds.max_x:
            return False
        lower = max(min(segment.start.y, segment.end.y), bounds.min_y)
        upper = min(max(segment.start.y, segment.end.y), bounds.max_y)
        if lower > upper:
            return False
        if lower < upper:
            return True
        point = Point(segment.start.x, lower)
    elif segment.start.y == segment.end.y:
        if not bounds.min_y <= segment.start.y <= bounds.max_y:
            return False
        lower = max(min(segment.start.x, segment.end.x), bounds.min_x)
        upper = min(max(segment.start.x, segment.end.x), bounds.max_x)
        if lower > upper:
            return False
        if lower < upper:
            return True
        point = Point(lower, segment.start.y)
    else:
        return True
    return point not in allowed_points or point not in {segment.start, segment.end}


def _is_outward_pin_escape(
    segment: WireSegment,
    pin: Point,
    direction: str,
    *,
    pin_is_start: bool,
) -> bool:
    """Check one short source-recorded pin-escape segment."""

    if pin_is_start:
        if segment.start != pin:
            return False
        dx, dy = segment.end.x - pin.x, segment.end.y - pin.y
    else:
        if segment.end != pin:
            return False
        dx, dy = segment.start.x - pin.x, segment.start.y - pin.y
    return {
        "left": dx < 0 and dy == 0,
        "right": dx > 0 and dy == 0,
        "top": dx == 0 and dy < 0,
        "bottom": dx == 0 and dy > 0,
    }[direction]


def _segments_intersect(left: WireSegment, right: WireSegment) -> bool:
    if left.start.x == left.end.x and right.start.x == right.end.x:
        if left.start.x != right.start.x:
            return False
        return max(min(left.start.y, left.end.y), min(right.start.y, right.end.y)) <= min(
            max(left.start.y, left.end.y), max(right.start.y, right.end.y)
        )
    if left.start.y == left.end.y and right.start.y == right.end.y:
        if left.start.y != right.start.y:
            return False
        return max(min(left.start.x, left.end.x), min(right.start.x, right.end.x)) <= min(
            max(left.start.x, left.end.x), max(right.start.x, right.end.x)
        )
    vertical = left if left.start.x == left.end.x else right
    horizontal = right if vertical is left else left
    return (
        min(horizontal.start.x, horizontal.end.x) <= vertical.start.x <= max(horizontal.start.x, horizontal.end.x)
        and min(vertical.start.y, vertical.end.y) <= horizontal.start.y <= max(vertical.start.y, vertical.end.y)
    )


def _point_on_segment(point: Point, segment: WireSegment) -> bool:
    if segment.start.x == segment.end.x == point.x:
        return min(segment.start.y, segment.end.y) <= point.y <= max(segment.start.y, segment.end.y)
    if segment.start.y == segment.end.y == point.y:
        return min(segment.start.x, segment.end.x) <= point.x <= max(segment.start.x, segment.end.x)
    return False


def _segments_have_unsafe_contact(left: WireSegment, right: WireSegment) -> bool:
    """Allow bare perpendicular crossings, but never overlaps or endpoint joins.

    Altium source wires have no junction record in this direct pilot. A pure
    interior crossing is therefore visual-only; an endpoint touching another
    net or a shared collinear span is an electrical ambiguity and is rejected.
    """

    if not _segments_intersect(left, right):
        return False
    left_vertical = left.start.x == left.end.x
    right_vertical = right.start.x == right.end.x
    if left_vertical == right_vertical:
        return True
    return any(
        _point_on_segment(point, other)
        for point, other in (
            (left.start, right),
            (left.end, right),
            (right.start, left),
            (right.end, left),
        )
    )


def _outward_escape(
    point: Point,
    component: GeneratedComponent,
    pin: str,
    amount: int,
) -> Point:
    """Follow the source-recorded electrical pin direction, not bbox proximity."""

    side = component.pin_directions[pin]
    if side == "left":
        return Point(point.x - amount, point.y)
    if side == "right":
        return Point(point.x + amount, point.y)
    if side == "top":
        return Point(point.x, point.y - amount)
    return Point(point.x, point.y + amount)


def _deduplicate_points(points: Iterable[Point]) -> tuple[Point, ...]:
    result: list[Point] = []
    for point in points:
        if not result or result[-1] != point:
            result.append(point)
    return tuple(result)


def _points_to_segments(net: str, points: Iterable[Point]) -> tuple[WireSegment, ...]:
    compact = _deduplicate_points(points)
    segments = tuple(
        WireSegment(net, start, end)
        for start, end in zip(compact, compact[1:])
        if start != end
    )
    if any(segment.start.x != segment.end.x and segment.start.y != segment.end.y for segment in segments):
        raise DirectGenerationError("Internal route construction produced a diagonal segment.")
    return segments


def _path_is_clear(
    candidate: tuple[WireSegment, ...],
    *,
    source: GeneratedComponent,
    target: GeneratedComponent,
    components: tuple[GeneratedComponent, ...],
    existing: tuple[WireSegment, ...],
) -> bool:
    if not candidate:
        return False
    source_pin = next(
        (pin for pin, point in source.pins.items() if point == candidate[0].start),
        None,
    )
    target_pin = next(
        (pin for pin, point in target.pins.items() if point == candidate[-1].end),
        None,
    )
    if source_pin is None or target_pin is None:
        return False
    for segment in candidate:
        for component in components:
            is_source_escape = (
                component.reference == source.reference
                and segment == candidate[0]
                and _is_outward_pin_escape(
                    segment,
                    source.pins[source_pin],
                    source.pin_directions[source_pin],
                    pin_is_start=True,
                )
            )
            is_target_escape = (
                component.reference == target.reference
                and segment == candidate[-1]
                and _is_outward_pin_escape(
                    segment,
                    target.pins[target_pin],
                    target.pin_directions[target_pin],
                    pin_is_start=False,
                )
            )
            if is_source_escape or is_target_escape:
                continue
            if _segment_has_invalid_body_contact(
                segment,
                component.bounds.expanded(12),
                set(),
            ):
                return False
        for previous in existing:
            if previous.net == segment.net:
                continue
            if _segments_have_unsafe_contact(segment, previous):
                return False
    return True


def _perpendicular_offset(point: Point, direction: str, offset: int) -> Point:
    if direction in {"left", "right"}:
        return Point(point.x, point.y + offset)
    return Point(point.x + offset, point.y)


def _pin_port_options(
    point: Point,
    component: GeneratedComponent,
    pin: str,
) -> tuple[tuple[Point, Point, Point], ...]:
    """Return deterministic escape/jog/channel choices for a native pin.

    Adjacent pins on a shared component side cannot all turn onto one vertical
    or horizontal trunk: that would create a real T-junction. Each option
    creates a short outward escape, then a small side jog, then a distinct
    routing channel beyond the symbol clearance.
    """

    direction = component.pin_directions[pin]
    escape = _outward_escape(point, component, pin, 40)
    options: list[tuple[Point, Point, Point]] = []
    for offset in (0, -64, 64, -112, 112):
        jog = _perpendicular_offset(escape, direction, offset)
        channel = _outward_escape(jog, component, pin, 32)
        options.append((escape, jog, channel))
    return tuple(options)


def _candidate_paths(
    net: str,
    start: Point,
    end: Point,
    source: GeneratedComponent,
    source_pin: str,
    target: GeneratedComponent,
    target_pin: str,
    components: tuple[GeneratedComponent, ...],
) -> tuple[tuple[WireSegment, ...], ...]:
    start_ports = _pin_port_options(start, source, source_pin)
    end_ports = _pin_port_options(end, target, target_pin)
    left = min(component.bounds.min_x for component in components) - 80
    right = max(component.bounds.max_x for component in components) + 80
    top = min(component.bounds.min_y for component in components) - 80
    bottom = max(component.bounds.max_y for component in components) + 80
    candidates: list[tuple[WireSegment, ...]] = []
    seen: set[tuple[WireSegment, ...]] = set()

    def add(points: Iterable[Point]) -> None:
        candidate = _points_to_segments(net, points)
        if candidate and candidate not in seen:
            seen.add(candidate)
            candidates.append(candidate)

    for start_escape, start_jog, start_channel in start_ports:
        for end_escape, end_jog, end_channel in end_ports:
            start_prefix = (start, start_escape, start_jog, start_channel)
            end_suffix = (end_channel, end_jog, end_escape, end)
            add((*start_prefix, Point(end_channel.x, start_channel.y), *end_suffix))
            add((*start_prefix, Point(start_channel.x, end_channel.y), *end_suffix))
            x_lanes = (
                left,
                right,
                start_channel.x - 60,
                start_channel.x + 60,
                end_channel.x - 60,
                end_channel.x + 60,
            )
            y_lanes = (
                top,
                bottom,
                start_channel.y - 60,
                start_channel.y + 60,
                end_channel.y - 60,
                end_channel.y + 60,
            )
            for lane in x_lanes:
                add(
                    (
                        *start_prefix,
                        Point(lane, start_channel.y),
                        Point(lane, end_channel.y),
                        *end_suffix,
                    )
                )
            for lane in y_lanes:
                add(
                    (
                        *start_prefix,
                        Point(start_channel.x, lane),
                        Point(end_channel.x, lane),
                        *end_suffix,
                    )
                )
    return tuple(candidates)


def _endpoint_locations(
    components: tuple[GeneratedComponent, ...],
) -> dict[str, tuple[Point, GeneratedComponent]]:
    endpoint_locations: dict[str, tuple[Point, GeneratedComponent]] = {}
    for component in components:
        for pin, point in component.pins.items():
            endpoint_locations[f"{component.reference}.{pin}"] = (point, component)
    return endpoint_locations


def _ordered_nets(
    nets: Mapping[str, tuple[str, ...]],
    endpoint_locations: Mapping[str, tuple[Point, GeneratedComponent]],
) -> list[tuple[str, tuple[str, ...]]]:
    return sorted(
        nets.items(),
        key=lambda item: (
            len(item[1]),
            sum(
                abs(endpoint_locations[item[1][0]][0].x - endpoint_locations[member][0].x)
                + abs(endpoint_locations[item[1][0]][0].y - endpoint_locations[member][0].y)
                for member in item[1][1:]
            ),
            item[0],
        ),
    )


def _route_one_net(
    net: str,
    members: tuple[str, ...],
    *,
    components: tuple[GeneratedComponent, ...],
    endpoint_locations: Mapping[str, tuple[Point, GeneratedComponent]],
    existing: tuple[WireSegment, ...],
) -> tuple[WireSegment, ...] | None:
    """Route one full net atomically, returning ``None`` without partial wires."""

    endpoints: list[tuple[str, Point, GeneratedComponent]] = []
    for endpoint in members:
        location = endpoint_locations.get(endpoint)
        if location is None:
            raise DirectGenerationError(f"Expected net {net!r} has no emitted endpoint {endpoint!r}.")
        point, component = location
        endpoints.append((endpoint, point, component))
    if len(endpoints) < 2:
        return None
    endpoints.sort(key=lambda entry: entry[0])
    anchor_name, anchor_point, anchor_component = endpoints[0]
    local: list[WireSegment] = []
    for endpoint_name, point, component in endpoints[1:]:
        options = _candidate_paths(
            net,
            anchor_point,
            point,
            anchor_component,
            anchor_name.rsplit(".", 1)[1],
            component,
            endpoint_name.rsplit(".", 1)[1],
            components,
        )
        valid = next(
            (
                option
                for option in options
                if _path_is_clear(
                    option,
                    source=anchor_component,
                    target=component,
                    components=components,
                    existing=(*existing, *local),
                )
            ),
            None,
        )
        if valid is None:
            return None
        local.extend(valid)
    return tuple(local)


def _terminal_stems(
    net: str,
    members: tuple[str, ...],
    endpoint_locations: Mapping[str, tuple[Point, GeneratedComponent]],
) -> tuple[tuple[WireSegment, ...], tuple[TerminalLabel, ...]]:
    stems: list[WireSegment] = []
    labels: list[TerminalLabel] = []
    for endpoint in members:
        point, component = endpoint_locations[endpoint]
        pin = endpoint.rsplit(".", 1)[1]
        label_point = _outward_escape(point, component, pin, 40)
        stems.append(WireSegment(net, point, label_point))
        labels.append(TerminalLabel(net, endpoint, label_point))
    return tuple(stems), tuple(labels)


def _plan_routing(
    routing_mode: str,
    nets: Mapping[str, tuple[str, ...]],
    components: tuple[GeneratedComponent, ...],
) -> RoutingPlan:
    """Plan strict wires, source-backed labels, or a deterministic combination."""

    endpoint_locations = _endpoint_locations(components)
    ordered_nets = _ordered_nets(nets, endpoint_locations)
    physical: list[WireSegment] = []
    terminalized: list[str] = []

    for net, members in ordered_nets:
        if net.upper().startswith("NC_"):
            continue
        if routing_mode == "terminal":
            terminalized.append(net)
            continue
        routed = _route_one_net(
            net,
            members,
            components=components,
            endpoint_locations=endpoint_locations,
            existing=tuple(physical),
        )
        if routed is not None:
            physical.extend(routed)
            continue
        if routing_mode == "wire":
            raise DirectGenerationError(
                f"Direct wire router could not connect {net!r}. Strict wire mode does not terminalize failures."
            )
        terminalized.append(net)

    labels: list[TerminalLabel] = []
    for net in terminalized:
        stems, net_labels = _terminal_stems(net, nets[net], endpoint_locations)
        physical.extend(stems)
        labels.extend(net_labels)
    return RoutingPlan(
        wires=tuple(physical),
        terminalized_nets=tuple(sorted(terminalized)),
        labels=tuple(labels),
    )


def _emitted_nets(components: tuple[GeneratedComponent, ...]) -> dict[str, tuple[str, ...]]:
    """Use native source pin designators in the post-resolution net contract."""

    nets: dict[str, list[str]] = {}
    for component in components:
        for designator, net in component.pin_nets.items():
            nets.setdefault(net, []).append(f"{component.reference}.{designator}")
    return {name: tuple(sorted(members)) for name, members in sorted(nets.items())}


def _wire_record(source_record: str, segment: WireSegment, index_in_sheet: int) -> str:
    """Rebase an actual native source wire record without inventing fields."""

    record = _replace_field(source_record, "INDEXINSHEET", str(index_in_sheet))
    for name, value in (
        ("X1", segment.start.x),
        ("Y1", segment.start.y),
        ("X2", segment.end.x),
        ("Y2", segment.end.y),
    ):
        record = _set_coordinate(record, name, value)
    return record


def _net_label_record(source_record: str, label: TerminalLabel, index_in_sheet: int) -> str:
    """Rebase a native source net-label record onto one terminal stem.

    The complete label grammar comes from the audited source document.  The
    direct writer changes only its stable identity, text, and attachment point.
    """

    record = _replace_field(source_record, "INDEXINSHEET", str(index_in_sheet))
    record = _replace_field(record, "TEXT", _clean_text(label.net, "terminal net name"))
    record = _set_coordinate(record, "LOCATION.X", label.location.x)
    return _set_coordinate(record, "LOCATION.Y", label.location.y)


def _header_record(catalogue: SourceCatalogue, circuit: AltiumCircuit, weight: int) -> str:
    identity = uuid5(NAMESPACE_URL, f"progeneda:altium:{circuit.name}:{circuit.title}")
    source = catalogue.header_record
    source = _replace_field(source, "UNIQUEID", str(identity).upper())
    return _replace_field(source, "WEIGHT", str(weight))


def _manifest_components(components: tuple[GeneratedComponent, ...]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for component in components:
        result.append(
            {
                "reference": component.reference,
                "owner_index": component.owner_index,
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
                        "escape_direction": component.pin_directions[pin],
                    }
                    for pin, point in component.pins.items()
                },
            }
        )
    return result


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _project_descriptor(circuit: AltiumCircuit, schematic_relative_path: Path) -> str:
    return "\n".join(
        (
            "[Project]",
            f"ProjectName={_clean_text(circuit.name, 'project name')}",
            f"ProjectTitle={_clean_text(circuit.title, 'project title')}",
            "[Document1]",
            f"DocumentPath={schematic_relative_path.as_posix()}",
            "",
        )
    )


def _run_name(circuit: AltiumCircuit) -> str:
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    digest = hashlib.sha256(
        json.dumps(circuit.normalized_json(), sort_keys=True).encode("utf-8")
    ).hexdigest()[:10]
    return f"{circuit.name}_{now}_{digest}"


def generate_direct_project(
    input_value: Path | str | Mapping[str, Any],
    *,
    output_root: Path | str,
    routing_mode: str | None = None,
) -> DirectGenerationResult:
    """Generate a fresh direct native-Altium schematic project and ZIP artifact."""

    circuit = load_circuit(input_value, routing_mode=routing_mode)
    catalogue = load_source_catalogue()
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    run_directory = root / _run_name(circuit)
    if run_directory.exists():
        raise DirectGenerationError(
            f"Refusing to overwrite prior direct Altium run {run_directory}; rerun to create a new record."
        )
    project_directory = run_directory / circuit.name
    schematic_directory = project_directory / "Schematic"
    internal_directory = run_directory / "internal"
    schematic_directory.mkdir(parents=True)
    internal_directory.mkdir(parents=True)

    try:
        components = _place_components(circuit, catalogue)
        emitted_nets = _emitted_nets(components)
        routing = _plan_routing(circuit.routing_mode, emitted_nets, components)
    except (SourceCatalogueError, CircuitInputError) as exc:
        raise DirectGenerationError(str(exc)) from exc

    emitted_records: list[str] = [catalogue.sheet_record]
    index_cursor = 1
    for component in components:
        template = catalogue.templates[component.source_template]
        source_component = next(item for item in circuit.components if item.reference == component.reference)
        records, index_cursor = _rewrite_component_records(
            template,
            source_component,
            owner_index=component.owner_index,
            target_root=component.root_location,
            index_start=index_cursor,
        )
        emitted_records.extend(records)
    for segment in routing.wires:
        emitted_records.append(_wire_record(catalogue.wire_record, segment, index_cursor))
        index_cursor += 1
    for label in routing.labels:
        emitted_records.append(_net_label_record(catalogue.net_label_record, label, index_cursor))
        index_cursor += 1

    schematic_file = schematic_directory / f"{circuit.name}.SchDoc"
    header = _header_record(catalogue, circuit, len(emitted_records))
    schematic_file.write_text("\r\n".join((header, *emitted_records, "")), encoding="utf-8", newline="")

    expected_manifest = {
        "components": _manifest_components(components),
        "nets": {name: list(members) for name, members in emitted_nets.items()},
        "terminalized_nets": list(routing.terminalized_nets),
    }
    validation = validate_direct_schematic(schematic_file, expected_manifest)
    _write_json(internal_directory / "validation_report.json", validation.json())
    _write_json(internal_directory / "normalized_input.json", circuit.normalized_json())
    _write_json(
        internal_directory / "source_provenance.json",
        {
            "schema": GENERATOR_SCHEMA,
            "source_catalogue": catalogue.json(),
            "generation_path": "canonical_json -> direct_altium_ir -> direct_ascii_schdoc -> native_project_package",
            "easyeda_conversion_used": False,
        },
    )
    _write_json(
        internal_directory / "placement.json",
        {"components": [component.json() for component in components]},
    )
    _write_json(
        internal_directory / "routing.json",
        {
            "routing_mode": circuit.routing_mode,
            "wires": [segment.json() for segment in routing.wires],
            "terminalized_nets": list(routing.terminalized_nets),
            "labels": [label.json() for label in routing.labels],
        },
    )
    _write_json(internal_directory / "expected_physical_contract.json", expected_manifest)
    if not validation.passed:
        raise DirectGenerationError(
            "Direct Altium generator saved a failed candidate at "
            f"{run_directory}: {'; '.join(validation.errors)}"
        )

    project_file = project_directory / f"{circuit.name}.PrjPcb"
    project_file.write_text(
        _project_descriptor(circuit, Path("Schematic") / schematic_file.name), encoding="utf-8"
    )
    project_archive = run_directory / f"{circuit.name}.zip"
    with zipfile.ZipFile(project_archive, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(project_file, f"{circuit.name}/{project_file.name}")
        archive.write(schematic_file, f"{circuit.name}/Schematic/{schematic_file.name}")

    return DirectGenerationResult(
        run_directory=run_directory,
        project_directory=project_directory,
        project_file=project_file,
        schematic_file=schematic_file,
        project_archive=project_archive,
        internal_directory=internal_directory,
        validation=validation,
        components=components,
        wires=routing.wires,
        terminalized_nets=routing.terminalized_nets,
        terminal_labels=routing.labels,
    )
