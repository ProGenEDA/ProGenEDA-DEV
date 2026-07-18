"""Deterministic validation of generated EasyEDA Pro projects."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from .donor_source import DonorPacket, _symbol_geometry
from .geometry import (
    Point,
    Rect,
    WireSpanIndex,
    inflate,
    rects_overlap,
    rotate_point,
    segment_hits_rect,
    transform_rect,
)
from .ir import Circuit, resolve_pin
from .native import NativeWriteResult


VALIDATION_SCHEMA = "progen-easyeda-validation-report/v1"


@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    report: dict[str, Any]


def _records(text: str) -> list[list[Any]]:
    rows: list[list[Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid native JSON record on line {line_number}: {exc}") from exc
        if not isinstance(value, list) or not value:
            raise ValueError(f"Native record line {line_number} is not a non-empty array.")
        rows.append(value)
    return rows


def _attrs(rows: Iterable[list[Any]], *, pcb: bool = False) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        if row[0] != "ATTR":
            continue
        if pcb:
            if len(row) < 9:
                continue
            parent = str(row[3])
            key = str(row[7])
            value = str(row[8])
        else:
            if len(row) < 5:
                continue
            parent = str(row[2])
            key = str(row[3])
            value = str(row[4])
        result.setdefault(parent, {})[key] = value
    return result


def _point_on_segment(point: Point, start: Point, end: Point, tolerance: float = 1e-5) -> bool:
    x, y = point
    x1, y1 = start
    x2, y2 = end
    if abs(y1 - y2) <= tolerance:
        return abs(y - y1) <= tolerance and min(x1, x2) - tolerance <= x <= max(x1, x2) + tolerance
    if abs(x1 - x2) <= tolerance:
        return abs(x - x1) <= tolerance and min(y1, y2) - tolerance <= y <= max(y1, y2) + tolerance
    return False


def _segments_intersect(
    first_start: Point,
    first_end: Point,
    second_start: Point,
    second_end: Point,
) -> bool:
    if first_start[0] == first_end[0] and second_start[1] == second_end[1]:
        return _point_on_segment(
            (first_start[0], second_start[1]),
            first_start,
            first_end,
        ) and _point_on_segment(
            (first_start[0], second_start[1]),
            second_start,
            second_end,
        )
    if first_start[1] == first_end[1] and second_start[0] == second_end[0]:
        return _point_on_segment(
            (second_start[0], first_start[1]),
            first_start,
            first_end,
        ) and _point_on_segment(
            (second_start[0], first_start[1]),
            second_start,
            second_end,
        )
    if first_start[0] == first_end[0] == second_start[0] == second_end[0]:
        return max(min(first_start[1], first_end[1]), min(second_start[1], second_end[1])) <= min(
            max(first_start[1], first_end[1]),
            max(second_start[1], second_end[1]),
        )
    if first_start[1] == first_end[1] == second_start[1] == second_end[1]:
        return max(min(first_start[0], first_end[0]), min(second_start[0], second_end[0])) <= min(
            max(first_start[0], first_end[0]),
            max(second_start[0], second_end[0]),
        )
    return False


def _wire_nets(rows: list[list[Any]], attrs: dict[str, dict[str, str]]) -> list[tuple[str, Point, Point]]:
    result: list[tuple[str, Point, Point]] = []
    for row in rows:
        if row[0] != "WIRE" or len(row) < 3:
            continue
        net = attrs.get(str(row[1]), {}).get("NET", "")
        geometry = row[2] if isinstance(row[2], list) else []
        for segment in geometry:
            if isinstance(segment, list) and len(segment) == 4:
                result.append(
                    (
                        net,
                        (float(segment[0]), float(segment[1])),
                        (float(segment[2]), float(segment[3])),
                    )
                )
    return result


def _device_symbol_map(connection: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    result: dict[str, dict[str, Any]] = {}
    for device in connection.execute("SELECT * FROM devices"):
        attributes = dict(
            connection.execute(
                "SELECT key, value FROM attributes WHERE device_uuid = ?",
                (device["uuid"],),
            ).fetchall()
        )
        symbol_uuid = attributes.get("Symbol")
        if not symbol_uuid:
            continue
        symbol = connection.execute("SELECT * FROM components WHERE uuid = ?", (symbol_uuid,)).fetchone()
        if symbol is not None:
            result[str(device["uuid"])] = dict(symbol)
    return result


def _instance_geometry(
    rows: list[list[Any]],
    attrs: dict[str, dict[str, str]],
    symbols: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    instances: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for row in rows:
        if row[0] != "COMPONENT" or len(row) < 6:
            continue
        identifier = str(row[1])
        instance_attrs = attrs.get(identifier, {})
        device_uuid = instance_attrs.get("Device", "")
        symbol = symbols.get(device_uuid)
        if symbol is None:
            errors.append(f"component {identifier} references missing device/symbol {device_uuid!r}")
            continue
        pins, bbox, part_name, _ = _symbol_geometry(str(symbol["dataStr"]))
        x = float(row[3])
        y = float(row[4])
        rotation = int(float(row[5])) % 360
        pin_points: dict[tuple[str, str], Point] = {}
        for pin in pins:
            local_x, local_y = rotate_point((pin.x, pin.y), rotation)
            pin_points[(pin.number, pin.name)] = (round(x + local_x, 6), round(y + local_y, 6))
        instances[identifier] = {
            "id": identifier,
            "reference": instance_attrs.get("Designator", ""),
            "value": instance_attrs.get("Value", ""),
            "name": instance_attrs.get("Name", ""),
            "global_net": instance_attrs.get("Global Net Name", ""),
            "device_uuid": device_uuid,
            "part_name": part_name,
            "x": x,
            "y": y,
            "rotation": rotation,
            "body": transform_rect(bbox, x, y, rotation),
            "pins": pin_points,
        }
    return instances, errors


def _find_instance_by_reference(instances: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(instance["reference"]): instance
        for instance in instances.values()
        if instance.get("reference")
    }


def _actual_membership(
    circuit: Circuit,
    instances: dict[str, dict[str, Any]],
    wires: list[tuple[str, Point, Point]],
    packets: dict[str, DonorPacket],
) -> tuple[dict[str, set[str]], list[str]]:
    membership: dict[str, set[str]] = {}
    errors: list[str] = []
    reference_instances = _find_instance_by_reference(instances)
    terminal_nets_by_point: dict[Point, set[str]] = {}
    for instance in instances.values():
        if instance.get("reference"):
            continue
        terminal_net = str(
            instance.get("global_net")
            or instance.get("name")
            or ""
        )
        if not terminal_net:
            continue
        for terminal_point in instance.get("pins", {}).values():
            terminal_nets_by_point.setdefault(terminal_point, set()).add(
                terminal_net
            )
    packet_by_reference = {
        component.reference: packets[component.identifier]
        for component in circuit.components
    }
    for component in circuit.components:
        instance = reference_instances.get(component.reference)
        if instance is None:
            errors.append(f"missing component reference {component.reference}")
            continue
        packet = packet_by_reference[component.reference]
        for requested, expected_net in component.pins.items():
            try:
                descriptor = resolve_pin(packet, requested)
            except ValueError as exc:
                errors.append(str(exc))
                continue
            point = instance["pins"].get((descriptor.number, descriptor.name))
            if point is None:
                errors.append(f"missing emitted pin {component.reference}.{requested}")
                continue
            connected_nets = {
                net
                for net, start, end in wires
                if net and _point_on_segment(point, start, end)
            }
            connected_nets.update(terminal_nets_by_point.get(point, set()))
            if component.kind in {"GND", "VCC"}:
                native_net = instance.get("global_net") or instance.get("name")
                if native_net:
                    connected_nets.add(str(native_net))
            wrong_nets = connected_nets - {expected_net}
            if wrong_nets:
                errors.append(
                    f"{component.reference}.{requested} expected only {expected_net!r}, "
                    f"also connected to {sorted(wrong_nets)}"
                )
            if expected_net in connected_nets:
                membership.setdefault(expected_net, set()).add(f"{component.reference}.{requested}")
            else:
                errors.append(
                    f"{component.reference}.{requested} expected {expected_net!r}, connected to {sorted(connected_nets)}"
                )
    return membership, errors


def _component_errors(
    circuit: Circuit,
    instances: dict[str, dict[str, Any]],
    packets: dict[str, DonorPacket],
) -> list[str]:
    errors: list[str] = []
    emitted = [
        instance
        for instance in instances.values()
        if instance.get("reference")
    ]
    expected_references = {component.reference for component in circuit.components}
    emitted_references = [str(instance["reference"]) for instance in emitted]
    duplicates = sorted(
        reference
        for reference in set(emitted_references)
        if emitted_references.count(reference) > 1
    )
    if duplicates:
        errors.append(f"duplicate emitted component references: {duplicates}")
    actual_references = set(emitted_references)
    missing = expected_references - actual_references
    extra = actual_references - expected_references
    if missing:
        errors.append(f"missing schematic references: {sorted(missing)}")
    if extra:
        errors.append(f"unexpected schematic references: {sorted(extra)}")
    by_reference = _find_instance_by_reference(instances)
    for component in circuit.components:
        instance = by_reference.get(component.reference)
        if instance is None:
            continue
        packet = packets[component.identifier]
        expected_device = str(packet.device["uuid"])
        if instance["device_uuid"] != expected_device:
            errors.append(
                f"{component.reference} device mismatch: "
                f"{instance['device_uuid']!r} != {expected_device!r}"
            )
        if instance["part_name"] != packet.part_name:
            errors.append(
                f"{component.reference} symbol part mismatch: "
                f"{instance['part_name']!r} != {packet.part_name!r}"
            )
        if component.kind not in {"GND", "VCC"} and instance["value"] != component.value:
            errors.append(
                f"{component.reference} value mismatch: "
                f"{instance['value']!r} != {component.value!r}"
            )
    return errors


def _terminal_errors(
    instances: dict[str, dict[str, Any]],
    native: NativeWriteResult,
) -> list[str]:
    errors: list[str] = []
    actual = [
        instance
        for instance in instances.values()
        if not instance.get("reference") and instance.get("name")
    ]
    unmatched = list(actual)
    for terminal in native.terminal_instances:
        expected_device = str(terminal.packet.device["uuid"])
        match = next(
            (
                instance
                for instance in unmatched
                if instance["name"] == terminal.net
                and instance["device_uuid"] == expected_device
                and abs(instance["x"] - terminal.x) <= 1e-6
                and abs(instance["y"] - terminal.y) <= 1e-6
                and instance["rotation"] == terminal.rotation
            ),
            None,
        )
        if match is None:
            errors.append(
                f"missing native terminal {terminal.net!r} for {terminal.endpoint} "
                f"at ({terminal.x}, {terminal.y})"
            )
        else:
            unmatched.remove(match)
    if unmatched:
        errors.append(
            "unexpected native terminals: "
            + repr(
                sorted(
                    (
                        str(instance["name"]),
                        float(instance["x"]),
                        float(instance["y"]),
                    )
                    for instance in unmatched
                )
            )
        )
    return errors


def _geometry_errors(
    instances: dict[str, dict[str, Any]],
    wires: list[tuple[str, Point, Point]],
) -> list[str]:
    errors: list[str] = []
    all_instances = list(instances.values())

    def label(instance: dict[str, Any]) -> str:
        reference = str(instance.get("reference") or "")
        if reference:
            return reference
        return (
            f"terminal:{instance.get('name') or instance.get('global_net') or '?'}"
            f"@{instance['x']},{instance['y']}"
        )

    for index, first in enumerate(all_instances):
        for second in all_instances[index + 1 :]:
            if rects_overlap(first["body"], second["body"], touch_is_overlap=False):
                errors.append(f"component overlap: {label(first)} and {label(second)}")
    for net, start, end in wires:
        for instance in all_instances:
            body = instance["body"]
            if not instance.get("reference"):
                body = (
                    body[0] + 1e-6,
                    body[1] + 1e-6,
                    body[2] - 1e-6,
                    body[3] - 1e-6,
                )
            if not segment_hits_rect(start, end, body):
                continue
            allowed = set(instance["pins"].values())
            if start in allowed or end in allowed:
                continue
            errors.append(
                f"wire {net!r} touches component body {label(instance)} away from a pin: {start}->{end}"
            )
    wire_spans = WireSpanIndex()
    for net, start, end in wires:
        conflict = wire_spans.find_overlap(((start, end),), net)
        if conflict is not None:
            other_net, _, _, other_start, other_end = conflict
            errors.append(
                f"different-net wires share a collinear span: "
                f"{net!r} {start}->{end} and "
                f"{other_net!r} {other_start}->{other_end}"
            )
        wire_spans.add(net, start, end)
    physical_bodies = [
        instance["body"]
        for instance in all_instances
        if instance.get("reference")
    ]
    if physical_bodies:
        component_bounds = (
            min(body[0] for body in physical_bodies),
            min(body[1] for body in physical_bodies),
            max(body[2] for body in physical_bodies),
            max(body[3] for body in physical_bodies),
        )
        span = max(
            component_bounds[2] - component_bounds[0],
            component_bounds[3] - component_bounds[1],
        )
        # Native geometry is grid-aligned while donor body bounds can be
        # fractional. Round the adaptive allowance outward to the next
        # EasyEDA grid line so a valid terminal contact is not rejected by a
        # sub-grid fraction; retain the existing 280-unit anti-sprawl cap.
        adaptive_margin = max(120.0, min(280.0, span * 0.18))
        margin = min(280.0, math.ceil(adaptive_margin / 12.0) * 12.0)
        wire_bounds = inflate(component_bounds, margin)
        for net, start, end in wires:
            start_inside = (
                wire_bounds[0] <= start[0] <= wire_bounds[2]
                and wire_bounds[1] <= start[1] <= wire_bounds[3]
            )
            end_inside = (
                wire_bounds[0] <= end[0] <= wire_bounds[2]
                and wire_bounds[1] <= end[1] <= wire_bounds[3]
            )
            if start_inside and end_inside:
                continue
            errors.append(
                f"wire {net!r} leaves compact schematic bounds "
                f"{wire_bounds}: {start}->{end}"
            )
    return errors


def _source_errors(
    connection: sqlite3.Connection,
    packets: dict[str, DonorPacket],
) -> list[str]:
    connection.row_factory = sqlite3.Row
    errors: list[str] = []
    seen: set[str] = set()
    for packet in packets.values():
        device_uuid = str(packet.device["uuid"])
        if device_uuid in seen:
            continue
        seen.add(device_uuid)
        device = connection.execute("SELECT * FROM devices WHERE uuid = ?", (device_uuid,)).fetchone()
        if device is None:
            errors.append(f"missing source device row {device_uuid}")
        else:
            for key, expected in packet.device.items():
                if key == "project_uuid":
                    continue
                if key in device.keys() and device[key] != expected:
                    errors.append(f"device source mismatch {device_uuid}.{key}")
        symbol = connection.execute(
            "SELECT dataStr FROM components WHERE uuid = ?",
            (packet.symbol["uuid"],),
        ).fetchone()
        if symbol is None:
            errors.append(f"missing source symbol {packet.symbol['uuid']}")
        elif hashlib.sha256(str(symbol[0]).encode("utf-8")).hexdigest() != packet.source_hashes["symbol"]:
            errors.append(f"source symbol payload changed for {device_uuid}")
        if packet.footprint is not None:
            footprint = connection.execute(
                "SELECT dataStr FROM components WHERE uuid = ?",
                (packet.footprint["uuid"],),
            ).fetchone()
            if footprint is None:
                errors.append(f"missing source footprint {packet.footprint['uuid']}")
            elif hashlib.sha256(str(footprint[0]).encode("utf-8")).hexdigest() != packet.source_hashes["footprint"]:
                errors.append(f"source footprint payload changed for {device_uuid}")
    return errors


def _pcb_errors(
    connection: sqlite3.Connection,
    circuit: Circuit,
    native: NativeWriteResult,
    packets: dict[str, DonorPacket],
) -> list[str]:
    errors: list[str] = []
    row = connection.execute("SELECT dataStr FROM documents WHERE docType = 3 LIMIT 1").fetchone()
    if not native.pcb.ready:
        if row is not None:
            errors.append("PCB document exists although PCB readiness is false")
        return errors
    if row is None:
        return ["PCB readiness is true but no PCB document exists"]
    try:
        rows = _records(str(row[0]))
    except ValueError as exc:
        return [str(exc)]
    if not any(item[0] == "POLY" and len(item) > 4 and item[4] == 11 for item in rows):
        errors.append("PCB has no closed outline record")
    pcb_attrs = _attrs(rows, pcb=True)
    references = {
        values.get("Designator", "")
        for values in pcb_attrs.values()
        if values.get("Designator")
    }
    expected_references = {
        component.reference
        for component in circuit.components
        if component.kind not in {"GND", "VCC"}
    }
    missing = expected_references - references
    extra = references - expected_references
    if missing:
        errors.append(f"PCB missing references: {sorted(missing)}")
    if extra:
        errors.append(f"PCB has unexpected references: {sorted(extra)}")
    net_records = {str(item[1]) for item in rows if item[0] == "NET" and len(item) > 1}
    if not set(circuit.nets).issubset(net_records):
        errors.append(f"PCB missing net records: {sorted(set(circuit.nets) - net_records)}")
    tracks = [
        (
            str(item[3]),
            int(item[4]),
            (float(item[5]), float(item[6])),
            (float(item[7]), float(item[8])),
        )
        for item in rows
        if item[0] == "LINE" and len(item) >= 9
    ]
    vias = [
        (str(item[3]), (float(item[6]), float(item[7])))
        for item in rows
        if item[0] == "PAD"
        and len(item) >= 8
        and int(item[4]) == 12
        and str(item[3])
    ]
    pad_net_rows = {
        (str(item[1]), str(item[2])): str(item[3])
        for item in rows
        if item[0] == "PAD_NET" and len(item) >= 5
    }
    component_id_by_reference = {
        values.get("Designator", ""): parent
        for parent, values in pcb_attrs.items()
        if values.get("Designator")
    }
    for endpoint, expected_net in (
        (endpoint, net)
        for net, members in circuit.nets.items()
        for endpoint in members
        if endpoint in native.pcb.pad_points
    ):
        reference, requested = endpoint.rsplit(".", 1)
        component_id = component_id_by_reference.get(reference)
        if component_id is None:
            continue
        component = next(item for item in circuit.components if item.reference == reference)
        try:
            descriptor = resolve_pin(packets[component.identifier], requested)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if pad_net_rows.get((component_id, descriptor.number)) != expected_net:
            errors.append(f"PCB PAD_NET mismatch for {endpoint}: expected {expected_net}")
    expected_pad_nets = {
        endpoint: net
        for net, members in circuit.nets.items()
        for endpoint in members
        if endpoint in native.pcb.pad_points
    }
    for endpoint, point in native.pcb.pad_points.items():
        expected_net = next(
            (
                net
                for net, members in circuit.nets.items()
                if endpoint in members
            ),
            None,
        )
        if expected_net is None:
            continue
        same_net_pad_count = sum(
            1 for member in circuit.nets[expected_net] if member in native.pcb.pad_points
        )
        if same_net_pad_count < 2:
            continue
        if not any(
            net == expected_net and _point_on_segment(point, start, end)
            for net, _, start, end in tracks
        ):
            errors.append(f"PCB pad {endpoint} is not physically tracked on {expected_net}")
    for first_index, (net, layer, start, end) in enumerate(tracks):
        for other_net, other_layer, other_start, other_end in tracks[first_index + 1 :]:
            if (
                layer == other_layer
                and net != other_net
                and _segments_intersect(start, end, other_start, other_end)
            ):
                errors.append(
                    f"PCB copper short on layer {layer}: {net!r} {start}->{end} "
                    f"intersects {other_net!r} {other_start}->{other_end}"
                )
        for endpoint, expected_net in expected_pad_nets.items():
            if expected_net != net and _point_on_segment(native.pcb.pad_points[endpoint], start, end):
                errors.append(
                    f"PCB track {net!r} touches wrong-net pad {endpoint} "
                    f"assigned to {expected_net!r}"
                )

    class _UnionFind:
        def __init__(self, size: int) -> None:
            self.parent = list(range(size))

        def find(self, item: int) -> int:
            while self.parent[item] != item:
                self.parent[item] = self.parent[self.parent[item]]
                item = self.parent[item]
            return item

        def union(self, first: int, second: int) -> None:
            first_root = self.find(first)
            second_root = self.find(second)
            if first_root != second_root:
                self.parent[second_root] = first_root

    for net, members in circuit.nets.items():
        pad_endpoints = [
            endpoint
            for endpoint in members
            if endpoint in native.pcb.pad_points
        ]
        if len(pad_endpoints) < 2:
            continue
        net_tracks = [
            (layer, start, end)
            for track_net, layer, start, end in tracks
            if track_net == net
        ]
        if not net_tracks:
            errors.append(f"PCB net {net!r} has multiple pads but no copper tracks")
            continue
        connected = _UnionFind(len(net_tracks))
        for first_index, (layer, start, end) in enumerate(net_tracks):
            for second_index, (other_layer, other_start, other_end) in enumerate(
                net_tracks[first_index + 1 :],
                start=first_index + 1,
            ):
                if layer == other_layer and _segments_intersect(start, end, other_start, other_end):
                    connected.union(first_index, second_index)
        net_vias = [point for via_net, point in vias if via_net == net]
        for via_point in net_vias:
            touching = [
                index
                for index, (_, start, end) in enumerate(net_tracks)
                if _point_on_segment(via_point, start, end)
            ]
            for index in touching[1:]:
                connected.union(touching[0], index)
        pad_roots: list[int] = []
        for endpoint in pad_endpoints:
            point = native.pcb.pad_points[endpoint]
            touching = [
                index
                for index, (_, start, end) in enumerate(net_tracks)
                if _point_on_segment(point, start, end)
            ]
            if not touching:
                continue
            reference, requested = endpoint.rsplit(".", 1)
            component = next(item for item in circuit.components if item.reference == reference)
            descriptor = resolve_pin(packets[component.identifier], requested)
            pad = packets[component.identifier].footprint_pad_details.get(descriptor.number)
            has_via = any(
                abs(point[0] - via[0]) <= 1e-5 and abs(point[1] - via[1]) <= 1e-5
                for via in net_vias
            )
            if has_via or (pad is not None and pad.through_hole):
                for index in touching[1:]:
                    connected.union(touching[0], index)
            pad_roots.append(connected.find(touching[0]))
        if pad_roots and len({connected.find(root) for root in pad_roots}) != 1:
            errors.append(f"PCB net {net!r} has disconnected copper islands")
    return errors


def validate_native_project(
    project_path: Path,
    circuit: Circuit,
    native: NativeWriteResult,
    packets: dict[str, DonorPacket],
) -> ValidationResult:
    """Validate native records without requiring EasyEDA to be installed."""

    checks: dict[str, Any] = {}
    errors: list[str] = []
    try:
        with sqlite3.connect(project_path) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()
            checks["sqlite_integrity"] = integrity[0] if integrity else None
            if integrity is None or integrity[0] != "ok":
                errors.append(f"SQLite integrity failed: {integrity!r}")
            project_uuid = str(native.donor_manifest["project"]["project_uuid"])
            expected_branch_uuid = str(native.donor_manifest["project"]["branch_uuid"])
            project_columns = {
                info[1] for info in connection.execute("PRAGMA table_info(projects)")
            }
            if "branch_uuid" not in project_columns:
                actual_branch_uuid = None
                errors.append("generated project has no EasyEDA 3.x branch_uuid column")
            else:
                project_row = connection.execute(
                    "SELECT branch_uuid FROM projects WHERE uuid = ?",
                    (project_uuid,),
                ).fetchone()
                actual_branch_uuid = project_row[0] if project_row else None
                if actual_branch_uuid != expected_branch_uuid:
                    errors.append(
                        "generated project branch identity does not match the native manifest"
                    )
            member_projects = {
                str(row[0])
                for row in connection.execute(
                    "SELECT DISTINCT project_uuid FROM project_members"
                )
            }
            if member_projects and member_projects != {project_uuid}:
                errors.append(
                    f"project_members contains stale donor identities: {sorted(member_projects)}"
                )
            stale_cache_rows = {
                table: connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
                for table in ("coppers", "texts")
            }
            if any(stale_cache_rows.values()):
                errors.append(
                    f"generated project contains donor PCB cache rows: {stale_cache_rows}"
                )
            document = connection.execute(
                "SELECT dataStr FROM documents WHERE uuid = ? AND docType = 1",
                (native.schematic_document_uuid,),
            ).fetchone()
            if document is None:
                errors.append("missing generated schematic document")
                rows: list[list[Any]] = []
            else:
                try:
                    rows = _records(str(document[0]))
                except ValueError as exc:
                    errors.append(str(exc))
                    rows = []
            attrs = _attrs(rows)
            symbols = _device_symbol_map(connection)
            instances, instance_errors = _instance_geometry(rows, attrs, symbols)
            wires = _wire_nets(rows, attrs)
            reference_instances = _find_instance_by_reference(instances)
            membership, connectivity_errors = _actual_membership(
                circuit, instances, wires, packets
            )
            component_errors = _component_errors(circuit, instances, packets)
            pin_coverage_errors: list[str] = []
            pin_coverage: dict[str, dict[str, Any]] = {}
            for component in circuit.components:
                packet = packets[component.identifier]
                expected_numbers = {pin.number for pin in packet.pins}
                resolved_numbers: set[str] = set()
                for requested in component.pins:
                    try:
                        resolved_numbers.add(resolve_pin(packet, requested).number)
                    except ValueError as exc:
                        pin_coverage_errors.append(str(exc))
                missing = sorted(expected_numbers - resolved_numbers)
                extra = sorted(resolved_numbers - expected_numbers)
                if missing:
                    pin_coverage_errors.append(
                        f"{component.reference} does not account for source pins {missing}"
                    )
                if extra:
                    pin_coverage_errors.append(
                        f"{component.reference} resolves unexpected source pins {extra}"
                    )
                pin_coverage[component.reference] = {
                    "raw_symbol_pin_count": len(packet.pins),
                    "unique_electrical_pin_count": len(expected_numbers),
                    "accounted_pin_count": len(resolved_numbers),
                    "missing": missing,
                    "complete": not missing and not extra,
                }
            terminal_errors = _terminal_errors(instances, native)
            for net, expected_members in circuit.nets.items():
                actual_members = membership.get(net, set())
                if actual_members != set(expected_members):
                    connectivity_errors.append(
                        f"net {net!r} membership mismatch: "
                        f"expected {sorted(expected_members)}, actual {sorted(actual_members)}"
                    )
            source_packets = dict(packets)
            for terminal in native.terminal_instances:
                source_packets[f"terminal:{terminal.endpoint}"] = terminal.packet
            source_errors = _source_errors(connection, source_packets)
            geometry_errors = _geometry_errors(instances, wires)
            pcb_errors = _pcb_errors(connection, circuit, native, packets)
            errors.extend(instance_errors)
            errors.extend(component_errors)
            errors.extend(pin_coverage_errors)
            errors.extend(terminal_errors)
            errors.extend(connectivity_errors)
            errors.extend(source_errors)
            errors.extend(geometry_errors)
            errors.extend(pcb_errors)
            checks.update(
                {
                    "schematic_record_count": len(rows),
                    "project_uuid": project_uuid,
                    "branch_uuid": actual_branch_uuid,
                    "project_member_projects": sorted(member_projects),
                    "donor_cache_rows": stale_cache_rows,
                    "component_references": sorted(reference_instances),
                    "wire_segment_count": len(wires),
                    "actual_net_members": {
                        net: sorted(members) for net, members in sorted(membership.items())
                    },
                    "expected_net_members": {
                        net: sorted(members) for net, members in sorted(circuit.nets.items())
                    },
                    "source_payload_errors": source_errors,
                    "component_errors": component_errors,
                    "pin_coverage": pin_coverage,
                    "pin_coverage_errors": pin_coverage_errors,
                    "terminal_errors": terminal_errors,
                    "geometry_errors": geometry_errors,
                    "pcb_ready": native.pcb.ready,
                    "pcb_reason": native.pcb.reason,
                    "pcb_errors": pcb_errors,
                }
            )
    except sqlite3.Error as exc:
        errors.append(f"Cannot parse generated EasyEDA SQLite project: {exc}")
    report = {
        "schema": VALIDATION_SCHEMA,
        "passed": not errors,
        "project_path": str(project_path),
        "routing_mode": circuit.routing_mode,
        "component_count": len(circuit.components),
        "net_count": len(circuit.nets),
        "checks": checks,
        "errors": errors,
    }
    return ValidationResult(passed=not errors, report=report)
