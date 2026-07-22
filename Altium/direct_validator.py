"""Deterministic validation for the direct ASCII Altium schematic writer.

This is deliberately independent from the generator's route objects: it
re-parses the saved ``.SchDoc`` record stream, reconstructs the physical wire
graph, and compares it with the expected canonical net membership.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re
from typing import Any, Mapping

from .source_catalogue import Bounds, Point


VALIDATION_SCHEMA = "progen-altium-direct-validation/v1"
_RECORD_PATTERN = re.compile(r"^\|RECORD=(\d+)(?:\||$)")


@dataclass(frozen=True)
class ParsedRecord:
    record_type: int
    text: str
    fields: dict[str, str]


@dataclass(frozen=True)
class DirectValidationReport:
    passed: bool
    schematic: str
    record_count: int
    component_count: int
    pin_count: int
    wire_count: int
    label_count: int
    expected_nets: tuple[str, ...]
    terminalized_nets: tuple[str, ...]
    errors: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = VALIDATION_SCHEMA
        return result


class DirectValidationError(ValueError):
    """The emitted ASCII schematic cannot be structurally or electrically validated."""


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self._parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        parent = self._parent[item]
        if parent != item:
            parent = self.find(parent)
            self._parent[item] = parent
        return parent

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


@dataclass(frozen=True)
class _Segment:
    start: Point
    end: Point

    def is_axis_aligned(self) -> bool:
        return self.start.x == self.end.x or self.start.y == self.end.y


@dataclass(frozen=True)
class _NetLabel:
    index: str
    text: str
    location: Point


def _fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in line.split("|")[1:]:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        fields.setdefault(key, value)
    return fields


def _coordinate(fields: Mapping[str, str], prefix: str, axis: str) -> int | None:
    whole = fields.get(f"{prefix}.{axis}")
    fraction = fields.get(f"{prefix}.{axis}_FRAC", "0")
    if whole is None:
        return None
    try:
        numerator = int(whole) * 100_000 + int(fraction)
    except ValueError:
        return None
    if numerator % 50_000:
        return None
    return numerator // 50_000


def _wire_points(fields: Mapping[str, str]) -> tuple[Point, ...]:
    try:
        count = int(fields.get("LOCATIONCOUNT", "0"))
    except ValueError:
        return ()
    points: list[Point] = []
    for number in range(1, count + 1):
        # Wire fields use X1/Y1 rather than LOCATION.X/LOCATION.Y.
        try:
            x_numerator = int(fields[f"X{number}"]) * 100_000 + int(
                fields.get(f"X{number}_FRAC", "0")
            )
            y_numerator = int(fields[f"Y{number}"]) * 100_000 + int(
                fields.get(f"Y{number}_FRAC", "0")
            )
        except (KeyError, ValueError):
            return ()
        if x_numerator % 50_000 or y_numerator % 50_000:
            return ()
        points.append(Point(x_numerator // 50_000, y_numerator // 50_000))
    return tuple(points)


def parse_ascii_schdoc(path: Path | str) -> tuple[str, tuple[ParsedRecord, ...]]:
    """Read the line-oriented ASCII SchDoc dialect used by the direct writer."""

    schematic = Path(path).expanduser().resolve()
    try:
        text = schematic.read_text(encoding="utf-8")
    except OSError as exc:
        raise DirectValidationError(f"Cannot read generated schematic {schematic}: {exc}") from exc
    lines = [line for line in text.splitlines() if line]
    if not lines or not lines[0].startswith("|HEADER=Protel for Windows - Schematic Capture Ascii"):
        raise DirectValidationError(f"{schematic} is not a direct ASCII Altium schematic document.")
    records: list[ParsedRecord] = []
    for line in lines[1:]:
        match = _RECORD_PATTERN.match(line)
        if not match:
            continue
        records.append(ParsedRecord(int(match.group(1)), line, _fields(line)))
    return lines[0], tuple(records)


def _point_on_segment(point: Point, segment: _Segment) -> bool:
    if segment.start.x == segment.end.x == point.x:
        return min(segment.start.y, segment.end.y) <= point.y <= max(segment.start.y, segment.end.y)
    if segment.start.y == segment.end.y == point.y:
        return min(segment.start.x, segment.end.x) <= point.x <= max(segment.start.x, segment.end.x)
    return False


def _segments_intersect(left: _Segment, right: _Segment) -> bool:
    if not left.is_axis_aligned() or not right.is_axis_aligned():
        return True
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


def _segment_has_invalid_body_contact(
    segment: _Segment,
    bounds: Bounds,
    allowed_points: set[Point],
) -> bool:
    """Reject every body touch except an endpoint at an actual pin."""

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
    segment: _Segment,
    pin: Point,
    direction: str,
    *,
    pin_is_start: bool,
) -> bool:
    """Recognize the generator's short, source-recorded pin escape."""

    if pin_is_start:
        if segment.start != pin:
            return False
        dx, dy = segment.end.x - pin.x, segment.end.y - pin.y
    else:
        if segment.end != pin:
            return False
        dx, dy = segment.start.x - pin.x, segment.start.y - pin.y
    length = abs(dx) + abs(dy)
    if not 0 < length <= 80:
        return False
    return {
        "left": dx < 0 and dy == 0,
        "right": dx > 0 and dy == 0,
        "top": dx == 0 and dy < 0,
        "bottom": dx == 0 and dy > 0,
    }.get(direction, False)


def _segments_connect(left: _Segment, right: _Segment) -> bool:
    """Connect endpoints/T-junctions, not a bare crossing with no junction."""

    return any(
        _point_on_segment(point, other)
        for point, other in (
            (left.start, right),
            (left.end, right),
            (right.start, left),
            (right.end, left),
        )
    )


def _point_from_manifest(value: Mapping[str, Any]) -> Point:
    return Point(int(value["x_ticks"]), int(value["y_ticks"]))


def _bounds_from_manifest(value: Mapping[str, Any]) -> Bounds:
    return Bounds(
        int(value["min_x_ticks"]),
        int(value["min_y_ticks"]),
        int(value["max_x_ticks"]),
        int(value["max_y_ticks"]),
    )


def validate_direct_schematic(
    path: Path | str,
    expected: Mapping[str, Any],
) -> DirectValidationReport:
    """Validate saved records, actual pin geometry, and the physical wire graph."""

    schematic = Path(path).expanduser().resolve()
    header, records = parse_ascii_schdoc(schematic)
    errors: list[str] = []
    header_fields = _fields(header)
    try:
        declared_weight = int(header_fields.get("WEIGHT", ""))
    except ValueError:
        declared_weight = -1
    if declared_weight != len(records):
        errors.append(
            f"header WEIGHT mismatch: declared {declared_weight}, saved {len(records)} records"
        )
    if not any(record.record_type == 31 for record in records):
        errors.append("generated schematic has no source-backed sheet record (RECORD=31)")

    expected_components = tuple(expected.get("components", ()))
    expected_pins: dict[str, Point] = {}
    expected_pin_directions: dict[str, str] = {}
    component_bounds: dict[str, Bounds] = {}
    for component in expected_components:
        reference = str(component["reference"])
        component_bounds[reference] = _bounds_from_manifest(component["bounds"])
        for pin, position in component["pins"].items():
            endpoint = f"{reference}.{pin}"
            expected_pins[endpoint] = _point_from_manifest(position)
            direction = str(position.get("escape_direction", ""))
            if direction not in {"left", "right", "top", "bottom"}:
                errors.append(f"expected pin {endpoint} lacks a valid escape direction")
            else:
                expected_pin_directions[endpoint] = direction

    actual_references: dict[str, str] = {}
    pending_pins: list[tuple[str, str, Point]] = []
    segments: list[_Segment] = []
    wire_indexes: list[str] = []
    labels: list[_NetLabel] = []
    label_indexes: list[str] = []
    component_unique_ids: list[str] = []
    for record in records:
        owner = record.fields.get("OWNERINDEX")
        if record.record_type == 1:
            unique_id = record.fields.get("UNIQUEID", "")
            if not re.fullmatch(r"pge\d+", unique_id):
                errors.append(f"component record has non-source-style UNIQUEID {unique_id!r}")
            else:
                component_unique_ids.append(unique_id)
        elif record.record_type == 34 and record.fields.get("NAME") == "Designator" and owner:
            actual_references[owner] = record.fields.get("TEXT", "")
        elif record.record_type == 2 and owner:
            x = _coordinate(record.fields, "LOCATION", "X")
            y = _coordinate(record.fields, "LOCATION", "Y")
            pin = record.fields.get("DESIGNATOR")
            if x is not None and y is not None and pin:
                pending_pins.append((owner, pin, Point(x, y)))
        elif record.record_type == 27:
            index_in_sheet = record.fields.get("INDEXINSHEET")
            if not index_in_sheet:
                errors.append(f"wire record has no INDEXINSHEET: {record.text[:160]}")
            else:
                wire_indexes.append(index_in_sheet)
            points = _wire_points(record.fields)
            if len(points) < 2:
                errors.append(f"invalid wire record: {record.text[:160]}")
                continue
            for start, end in zip(points, points[1:]):
                segment = _Segment(start, end)
                if not segment.is_axis_aligned() or start == end:
                    errors.append(f"non-orthogonal or zero-length wire: {record.text[:160]}")
                else:
                    segments.append(segment)
        elif record.record_type == 25:
            index_in_sheet = record.fields.get("INDEXINSHEET")
            text = record.fields.get("TEXT", "").strip()
            x = _coordinate(record.fields, "LOCATION", "X")
            y = _coordinate(record.fields, "LOCATION", "Y")
            if not index_in_sheet:
                errors.append(f"net-label record has no INDEXINSHEET: {record.text[:160]}")
            elif not text or x is None or y is None:
                errors.append(f"invalid net-label record: {record.text[:160]}")
            else:
                label_indexes.append(index_in_sheet)
                labels.append(_NetLabel(index_in_sheet, text, Point(x, y)))

    actual_pins: dict[str, Point] = {}
    for owner, pin, point in pending_pins:
        reference = actual_references.get(owner)
        if reference:
            actual_pins[f"{reference}.{pin}"] = point
        else:
            errors.append(f"physical pin {pin!r} has no component designator owner {owner!r}")

    expected_references = {str(component["reference"]) for component in expected_components}
    actual_reference_set = set(actual_references.values())
    missing_references = sorted(expected_references - actual_reference_set)
    unexpected_references = sorted(actual_reference_set - expected_references)
    if missing_references:
        errors.append(f"missing component designators in saved SchDoc: {missing_references}")
    if unexpected_references:
        errors.append(f"unexpected component designators in saved SchDoc: {unexpected_references}")
    if len(component_unique_ids) != len(expected_components):
        errors.append(
            f"saved SchDoc has {len(component_unique_ids)} source-style component UNIQUEIDs, "
            f"expected {len(expected_components)}"
        )
    duplicate_component_unique_ids = sorted(
        {value for value in component_unique_ids if component_unique_ids.count(value) > 1}
    )
    if duplicate_component_unique_ids:
        errors.append(f"duplicate component UNIQUEID values: {duplicate_component_unique_ids}")

    for endpoint, position in sorted(expected_pins.items()):
        actual = actual_pins.get(endpoint)
        if actual is None:
            errors.append(f"missing physical pin record for {endpoint}")
        elif actual != position:
            errors.append(
                f"pin position mismatch for {endpoint}: expected {position.json()}, got {actual.json()}"
            )
    unexpected_pins = sorted(set(actual_pins) - set(expected_pins))
    if unexpected_pins:
        errors.append(f"saved SchDoc contains unsupported/unexpected pins: {unexpected_pins}")

    placements = list(component_bounds.items())
    for index, (left_reference, left_bounds) in enumerate(placements):
        for right_reference, right_bounds in placements[index + 1 :]:
            if left_bounds.intersects(right_bounds):
                errors.append(f"component bodies overlap: {left_reference} and {right_reference}")

    for segment in segments:
        for reference, bounds in component_bounds.items():
            component_pins = [
                (point, expected_pin_directions.get(endpoint, ""))
                for endpoint, point in expected_pins.items()
                if endpoint.startswith(f"{reference}.")
            ]
            is_pin_escape = any(
                _is_outward_pin_escape(segment, point, direction, pin_is_start=True)
                or _is_outward_pin_escape(segment, point, direction, pin_is_start=False)
                for point, direction in component_pins
            )
            if not is_pin_escape and _segment_has_invalid_body_contact(segment, bounds, set()):
                errors.append(
                    f"wire {segment.start.json()} -> {segment.end.json()} touches component body {reference}"
                )

    duplicate_wire_indexes = sorted({index for index in wire_indexes if wire_indexes.count(index) > 1})
    if duplicate_wire_indexes:
        errors.append(f"duplicate wire INDEXINSHEET values: {duplicate_wire_indexes}")
    duplicate_label_indexes = sorted({index for index in label_indexes if label_indexes.count(index) > 1})
    if duplicate_label_indexes:
        errors.append(f"duplicate net-label INDEXINSHEET values: {duplicate_label_indexes}")

    graph = _UnionFind()
    for endpoint in expected_pins:
        graph.add(endpoint)
    segment_nodes: list[tuple[str, str, _Segment]] = []
    for index, segment in enumerate(segments):
        left = f"segment:{index}:start"
        right = f"segment:{index}:end"
        graph.union(left, right)
        segment_nodes.append((left, right, segment))
    for endpoint, point in expected_pins.items():
        for left, _, segment in segment_nodes:
            if _point_on_segment(point, segment):
                graph.union(endpoint, left)
    for index, (left_node, _, left_segment) in enumerate(segment_nodes):
        for right_node, _, right_segment in segment_nodes[index + 1 :]:
            if _segments_connect(left_segment, right_segment):
                graph.union(left_node, right_node)

    expected_nets = expected.get("nets", {})
    raw_terminalized = expected.get("terminalized_nets", ())
    if not isinstance(raw_terminalized, (list, tuple)):
        errors.append("terminalized_nets must be a list when present")
        raw_terminalized = ()
    expected_terminalized = {str(name) for name in raw_terminalized}
    unknown_terminalized = sorted(expected_terminalized - set(expected_nets))
    if unknown_terminalized:
        errors.append(f"terminalized_nets names unknown expected nets: {unknown_terminalized}")

    labels_by_net: dict[str, list[_NetLabel]] = {}
    for label in labels:
        labels_by_net.setdefault(label.text, []).append(label)
        if label.text not in expected_terminalized:
            errors.append(
                f"native label {label.text!r} is not declared as a terminalized expected net"
            )
        attached_segments = [
            left
            for left, _, segment in segment_nodes
            if _point_on_segment(label.location, segment)
        ]
        if not attached_segments:
            errors.append(
                f"native label {label.text!r} at {label.location.json()} is not attached to a wire"
            )
            continue
        label_node = f"label:{label.index}"
        for segment_node in attached_segments:
            graph.union(label_node, segment_node)
    for label_text, net_labels in labels_by_net.items():
        first_node = f"label:{net_labels[0].index}"
        for label in net_labels[1:]:
            graph.union(first_node, f"label:{label.index}")

    net_roots: dict[str, set[str]] = {}
    for net_name, members in sorted(expected_nets.items()):
        roots: set[str] = set()
        for endpoint in members:
            if endpoint not in expected_pins:
                errors.append(f"expected net {net_name!r} references unknown emitted endpoint {endpoint!r}")
                continue
            roots.add(graph.find(endpoint))
        net_roots[net_name] = roots
        expected_label_count = len(members) if net_name in expected_terminalized else 0
        actual_labels = labels_by_net.get(net_name, [])
        if len(actual_labels) != expected_label_count:
            errors.append(
                f"terminalized net {net_name!r} needs {expected_label_count} attached labels, "
                f"saved {len(actual_labels)}"
            )
        if len(members) > 1 and len(roots) != 1:
            errors.append(
                f"saved connectivity does not connect expected net {net_name!r}: {sorted(members)}"
            )
    root_to_nets: dict[str, set[str]] = {}
    for net_name, roots in net_roots.items():
        for root in roots:
            root_to_nets.setdefault(root, set()).add(net_name)
    shorts = sorted(sorted(nets) for nets in root_to_nets.values() if len(nets) > 1)
    if shorts:
        errors.append(f"physical wire graph merges distinct expected nets: {shorts}")

    return DirectValidationReport(
        passed=not errors,
        schematic=str(schematic),
        record_count=len(records),
        component_count=len(actual_reference_set),
        pin_count=len(actual_pins),
        wire_count=len(segments),
        label_count=len(labels),
        expected_nets=tuple(sorted(expected_nets)),
        terminalized_nets=tuple(sorted(expected_terminalized)),
        errors=tuple(errors),
    )
