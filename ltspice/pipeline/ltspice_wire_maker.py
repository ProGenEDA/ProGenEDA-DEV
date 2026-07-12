"""Native LTspice wire/terminal planning from canonical expected connectivity."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .component_placer import PlacedComponent
from .geometry import GRID, Point, Segment, orthogonal_path, segment_intersection, transform_offset


WIRE_PLAN_SCHEMA = "progen-ltspice-wire-plan/v0.1"


@dataclass(frozen=True)
class NetFlag:
    point: Point
    name: str
    logical_net: str
    endpoint: str | None
    purpose: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "point": {"x": self.point.x, "y": self.point.y},
            "name": self.name,
            "logical_net": self.logical_net,
            "endpoint": self.endpoint,
            "purpose": self.purpose,
        }


@dataclass(frozen=True)
class VirtualNativeAnchor:
    endpoint: str
    logical_net: str
    point: Point
    native_flag: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "logical_net": self.logical_net,
            "point": {"x": self.point.x, "y": self.point.y},
            "native_flag": self.native_flag,
            "representation": "virtual_native_anchor",
        }


@dataclass(frozen=True)
class WirePlan:
    mode: str
    segments: tuple[Segment, ...]
    flags: tuple[NetFlag, ...]
    virtual_anchors: tuple[VirtualNativeAnchor, ...]
    expected_native_nets: dict[str, list[str]]
    label_map: dict[str, str]
    rejected_wire_routes: tuple[dict[str, Any], ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": WIRE_PLAN_SCHEMA,
            "stage": "ltspice_wire_maker",
            "mode": self.mode,
            "wire_segments": [
                {"start": {"x": item.start.x, "y": item.start.y}, "end": {"x": item.end.x, "y": item.end.y}}
                for item in self.segments
            ],
            "flags": [item.as_dict() for item in self.flags],
            "virtual_native_anchors": [item.as_dict() for item in self.virtual_anchors],
            "expected_native_nets": self.expected_native_nets,
            "logical_to_native_label": self.label_map,
            "rejected_wire_routes": list(self.rejected_wire_routes),
        }


def _logical_nets(circuit: dict[str, Any]) -> dict[str, list[str]]:
    raw = circuit.get("nets")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Canonical circuit has no nets object.")
    nets: dict[str, list[str]] = {}
    assigned: dict[str, str] = {}
    for raw_name, raw_members in raw.items():
        name = str(raw_name).strip()
        if not name or not isinstance(raw_members, list):
            raise ValueError("Every canonical net must have a non-empty name and an endpoint list.")
        members = [str(member).strip() for member in raw_members if str(member).strip()]
        if len(members) < 2:
            raise ValueError(f"Net {name!r} has fewer than two endpoints.")
        for endpoint in members:
            if not re.fullmatch(r"[^.\s]+\.\d+", endpoint):
                raise ValueError(f"Net {name!r} has malformed endpoint {endpoint!r}.")
            previous = assigned.setdefault(endpoint, name)
            if previous != name:
                raise ValueError(f"Endpoint {endpoint} belongs to both {previous!r} and {name!r}.")
        nets[name] = list(dict.fromkeys(members))
    return nets


def _is_ground(logical_net: str) -> bool:
    return logical_net.strip().upper() in {"0", "GND", "GROUND"}


def _native_label(logical_net: str, used: set[str]) -> str:
    if _is_ground(logical_net):
        return "0"
    compact = re.sub(r"[^A-Za-z0-9_]+", "_", logical_net.strip()).strip("_")
    if not compact:
        compact = "NET"
    if compact[0].isdigit():
        compact = "N_" + compact
    candidate = compact[:64]
    suffix = 2
    while candidate.upper() in used:
        ending = f"_{suffix}"
        candidate = compact[: 64 - len(ending)] + ending
        suffix += 1
    used.add(candidate.upper())
    return candidate


def _pin_exit_direction(placed: PlacedComponent, pin_number: str) -> Point:
    pin = placed.component.profile.pin(pin_number)
    directions = {
        "TOP": Point(0, -1),
        "BOTTOM": Point(0, 1),
        "LEFT": Point(-1, 0),
        "RIGHT": Point(1, 0),
    }
    local = directions.get(pin.justification.upper(), Point(0, -1))
    transformed = transform_offset(local, placed.orientation)
    return Point(0 if transformed.x == 0 else (1 if transformed.x > 0 else -1), 0 if transformed.y == 0 else (1 if transformed.y > 0 else -1))


def _stub(pin: Point, direction: Point) -> Segment:
    end = pin.translate(direction.x * GRID * 2, direction.y * GRID * 2)
    return Segment(pin, end)


def _route_is_safe(candidate: Iterable[Segment], existing: Iterable[Segment], forbidden: set[Point]) -> bool:
    proposed = list(candidate)
    for segment in proposed:
        if not (segment.is_horizontal or segment.is_vertical):
            return False
        for point in forbidden:
            # `forbidden` already excludes the route's own two endpoint pins.
            # A third component pin is unsafe even when it lands exactly on an
            # elbow or route endpoint: LTspice would electrically merge it.
            if segment.contains(point):
                return False
        for previous in existing:
            crossing = segment_intersection(segment, previous)
            # A shared endpoint can still be a T-junction when it is an elbow
            # or only one segment's endpoint. The planner has no same-net
            # context at this low-level predicate, so conservative rejection
            # is safer than accidentally merging two logical nets. Terminal
            # labels provide an explicit native fallback for every rejection.
            if crossing is not None:
                return False
    return True


def _direct_route(first: Point, second: Point, existing: list[Segment], forbidden: set[Point]) -> list[Segment] | None:
    candidates = [
        orthogonal_path(first, second, prefer_horizontal=True),
        orthogonal_path(first, second, prefer_horizontal=False),
    ]
    for route in candidates:
        if _route_is_safe(route, existing, forbidden):
            return route
    return None


def build_wire_plan(circuit: dict[str, Any], placed: list[PlacedComponent]) -> WirePlan:
    """Build an inspectable physical-wire/terminal hybrid plan.

    Two-pin non-rail nets receive a direct orthogonal wire only when it is
    provably clear on the current grid. Everything else is represented by a
    short pin lead and an LTspice FLAG. This is native terminal connectivity,
    not a guessed invisible net: each fallback is recorded in the plan.
    """

    nets = _logical_nets(circuit)
    requested_mode = str(circuit.get("routing", {}).get("mode", "combination"))
    if requested_mode not in {"wire", "terminal", "combination"}:
        requested_mode = "combination"
    by_ref = {item.component.ref: item for item in placed}
    endpoint_points: dict[str, Point] = {}
    pseudo_endpoints: set[str] = set()
    all_pin_points: set[Point] = set()
    for item in placed:
        for pin in item.component.profile.pins:
            endpoint = f"{item.component.ref}.{pin.number}"
            point = item.pin_point(pin.number)
            endpoint_points[endpoint] = point
            if item.component.profile.is_pseudo_component:
                pseudo_endpoints.add(endpoint)
            else:
                all_pin_points.add(point)
    unknown = sorted({endpoint for members in nets.values() for endpoint in members if endpoint not in endpoint_points})
    if unknown:
        raise ValueError(f"Canonical nets reference components/pins without a placed LTspice endpoint: {', '.join(unknown)}.")

    label_map: dict[str, str] = {}
    used_labels: set[str] = set()
    for net in nets:
        label_map[net] = _native_label(net, used_labels)
    segments: list[Segment] = []
    flags: list[NetFlag] = []
    virtual: list[VirtualNativeAnchor] = []
    rejected: list[dict[str, Any]] = []
    expected_native: dict[str, list[str]] = {}
    for net, endpoints in nets.items():
        label = label_map[net]
        native_members: list[str] = []
        physical = [endpoint for endpoint in endpoints if endpoint not in pseudo_endpoints]
        for endpoint in endpoints:
            if endpoint in pseudo_endpoints:
                if not _is_ground(net):
                    raise ValueError(f"Ground pseudo-component endpoint {endpoint} is assigned to non-ground net {net!r}.")
                virtual.append(VirtualNativeAnchor(endpoint, net, endpoint_points[endpoint], "0"))
            else:
                native_members.append(endpoint)
        expected_native[net] = native_members
        can_try_direct = requested_mode in {"wire", "combination"} and len(physical) == 2 and not _is_ground(net)
        if can_try_direct:
            route = _direct_route(endpoint_points[physical[0]], endpoint_points[physical[1]], segments, all_pin_points - {endpoint_points[physical[0]], endpoint_points[physical[1]]})
            if route is not None:
                segments.extend(route)
                continue
            rejected.append({"net": net, "reason": "direct_route_intersects_existing_geometry", "fallback": "terminal_flags"})
        elif requested_mode == "wire" and physical:
            rejected.append({"net": net, "reason": "strict_wire_mode_requires_safe_tree_router", "fallback": "terminal_flags"})
        for endpoint in physical:
            point = endpoint_points[endpoint]
            ref, pin = endpoint.rsplit(".", 1)
            direction = _pin_exit_direction(by_ref[ref], pin)
            lead = _stub(point, direction)
            if not _route_is_safe([lead], segments, all_pin_points - {point}):
                # The outward lead touches only its own pin by construction. A
                # collision means the placement itself is too dense to claim a
                # safe artifact, rather than something to hide with a label.
                raise ValueError(f"Terminal lead for {endpoint} collides with placed geometry; rerun with a looser placement.")
            segments.append(lead)
            flags.append(NetFlag(lead.end, label, net, endpoint, "terminal_fallback"))
        if not physical and _is_ground(net):
            # A canonical design composed only of ground pseudo-components is
            # still represented by real native ground flags at their anchors.
            pass
    for anchor in virtual:
        flags.append(NetFlag(anchor.point, anchor.native_flag, anchor.logical_net, anchor.endpoint, "virtual_ground_anchor"))
    return WirePlan(
        mode=requested_mode,
        segments=tuple(segments),
        flags=tuple(flags),
        virtual_anchors=tuple(virtual),
        expected_native_nets=expected_native,
        label_map=label_map,
        rejected_wire_routes=tuple(rejected),
    )
