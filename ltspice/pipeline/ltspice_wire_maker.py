"""Native LTspice wire/terminal planning from canonical expected connectivity."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Iterable

from .component_placer import PlacedComponent
from .geometry import GRID, Point, Segment, orthogonal_path, segment_intersection, transform_offset


WIRE_PLAN_SCHEMA = "progen-ltspice-wire-plan/v0.1"
TREE_ROUTE_MAX_HUB_CANDIDATES = 48


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
    forced_terminal_nets: tuple[str, ...]
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
            "forced_terminal_nets": list(self.forced_terminal_nets),
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


def _canonical_tree_segments(segments: Iterable[Segment]) -> list[Segment]:
    """Merge collinear pieces of one proposed tree into a non-overlapping set.

    A star-shaped Manhattan tree naturally contains overlapping branch
    portions when two endpoints approach the same trunk from one side.  LTspice
    does not need duplicate WIRE records there, and the independent geometry
    validator quite rightly treats an interior overlap as ambiguous.  Merge
    only same-axis, same-line intervals; perpendicular branches remain
    separate so their shared endpoint is an explicit electrical junction.
    """

    horizontal: dict[int, list[tuple[int, int]]] = {}
    vertical: dict[int, list[tuple[int, int]]] = {}
    for segment in segments:
        if segment.start == segment.end:
            continue
        if segment.is_horizontal:
            low, high = sorted((segment.start.x, segment.end.x))
            horizontal.setdefault(segment.start.y, []).append((low, high))
        elif segment.is_vertical:
            low, high = sorted((segment.start.y, segment.end.y))
            vertical.setdefault(segment.start.x, []).append((low, high))
        else:
            # Callers only construct paths with ``orthogonal_path``.  Keep the
            # defensive branch so a future route strategy cannot accidentally
            # make diagonal output appear valid.
            return []

    result: list[Segment] = []
    for y, intervals in sorted(horizontal.items()):
        left: int | None = None
        right: int | None = None
        for low, high in sorted(intervals):
            if left is None or right is None:
                left, right = low, high
            elif low <= right:
                right = max(right, high)
            else:
                result.append(Segment(Point(left, y), Point(right, y)))
                left, right = low, high
        if left is not None and right is not None:
            result.append(Segment(Point(left, y), Point(right, y)))
    for x, intervals in sorted(vertical.items()):
        top: int | None = None
        bottom: int | None = None
        for low, high in sorted(intervals):
            if top is None or bottom is None:
                top, bottom = low, high
            elif low <= bottom:
                bottom = max(bottom, high)
            else:
                result.append(Segment(Point(x, top), Point(x, bottom)))
                top, bottom = low, high
        if top is not None and bottom is not None:
            result.append(Segment(Point(x, top), Point(x, bottom)))
    return result


def _tree_route_is_safe(candidate: Iterable[Segment], existing: Iterable[Segment], forbidden: set[Point]) -> bool:
    """Prove that a proposed single-net tree cannot create an accidental join.

    Unlike ``_route_is_safe``, an explicit tree may meet itself at a T-junction
    or a shared endpoint.  It may *not* cross itself where neither segment
    terminates, touch any foreign component pin, or intersect any wire already
    claimed by an earlier logical net.
    """

    proposed = list(candidate)
    if not proposed:
        return False
    for segment in proposed:
        if not (segment.is_horizontal or segment.is_vertical):
            return False
        if any(segment.contains(point) for point in forbidden):
            return False
        for previous in existing:
            if segment_intersection(segment, previous) is not None:
                return False
    for index, first in enumerate(proposed):
        for second in proposed[index + 1 :]:
            crossing = segment_intersection(first, second)
            if crossing is None:
                continue
            first_end = crossing in {first.start, first.end}
            second_end = crossing in {second.start, second.end}
            # A branch ending on the trunk is a deliberate same-net junction;
            # an interior/interior crossing would be an unproven short.
            if not first_end and not second_end:
                return False
    return True


def _tree_axis_candidates(values: Iterable[int]) -> list[int]:
    """Return a compact deterministic set of possible trunk coordinates."""

    ordered = sorted(set(values))
    if not ordered:
        return []
    median = ordered[(len(ordered) - 1) // 2]
    # Native placement is on a 16-unit grid.  Two nearby outer lanes give the
    # bounded router a chance to avoid a central pin without turning this into
    # an unbounded maze search.
    candidates = [median]
    candidates.extend(sorted(ordered, key=lambda value: (abs(value - median), value)))
    lower = ordered[0] - GRID * 2
    if lower >= 0:
        candidates.append(lower)
    candidates.append(ordered[-1] + GRID * 2)
    return list(dict.fromkeys(candidates))


def _tree_hub_candidates(points: Iterable[Point]) -> list[Point]:
    """Choose bounded star hubs ordered by compactness and stable coordinates."""

    endpoints = sorted(set(points))
    if not endpoints:
        return []
    x_values = _tree_axis_candidates(point.x for point in endpoints)
    y_values = _tree_axis_candidates(point.y for point in endpoints)
    median_x = sorted(point.x for point in endpoints)[(len(endpoints) - 1) // 2]
    median_y = sorted(point.y for point in endpoints)[(len(endpoints) - 1) // 2]
    candidates = {Point(x, y) for x in x_values for y in y_values}
    return sorted(
        candidates,
        key=lambda point: (
            sum(abs(point.x - endpoint.x) + abs(point.y - endpoint.y) for endpoint in endpoints),
            abs(point.x - median_x) + abs(point.y - median_y),
            point.x,
            point.y,
        ),
    )[:TREE_ROUTE_MAX_HUB_CANDIDATES]


def _safe_tree_route(points: Iterable[Point], existing: list[Segment], forbidden: set[Point]) -> list[Segment] | None:
    """Return a conservative Manhattan tree for three or more endpoint pins.

    Each candidate is an H/V star: either a vertical trunk with horizontal
    branches, or its transpose.  This deliberately small search gives a
    readable result for donor-style resistor ladders while retaining a
    deterministic proof obligation.  It is not a general autorouter; callers
    retain labelled-terminal fallback whenever no candidate clears the proof.
    """

    endpoints = sorted(set(points))
    if len(endpoints) < 3:
        return None
    for hub in _tree_hub_candidates(endpoints):
        # Try a vertical trunk first, then a horizontal trunk.  The ordering is
        # fixed, so equal-cost layouts stay byte-for-byte deterministic.
        for prefer_horizontal in (True, False):
            raw = [
                segment
                for endpoint in endpoints
                for segment in orthogonal_path(endpoint, hub, prefer_horizontal=prefer_horizontal)
            ]
            candidate = _canonical_tree_segments(raw)
            if _tree_route_is_safe(candidate, existing, forbidden):
                return candidate
    return None


def build_wire_plan(
    circuit: dict[str, Any],
    placed: list[PlacedComponent],
    *,
    force_terminal_nets: Iterable[str] = (),
) -> WirePlan:
    """Build an inspectable physical-wire/terminal hybrid plan.

    Two-pin non-rail nets receive a direct orthogonal wire only when it is
    provably clear on the current grid. Larger non-rail nets receive a bounded
    same-net Manhattan tree when every branch, junction, and foreign obstacle
    can be proven safe. Everything else is represented by a short pin lead and
    an LTspice FLAG. This is native terminal connectivity, not a guessed
    invisible net: each fallback is recorded in the plan.
    """

    nets = _logical_nets(circuit)
    forced_terminal_names = {str(name).strip().upper() for name in force_terminal_nets if str(name).strip()}
    requested_mode = str(circuit.get("routing", {}).get("mode", "combination"))
    if requested_mode not in {"wire", "terminal", "combination"}:
        requested_mode = "combination"
    by_ref = {item.component.ref: item for item in placed}
    endpoint_points: dict[str, Point] = {}
    pseudo_endpoints: set[str] = set()
    pseudo_representation_by_endpoint: dict[str, str] = {}
    all_pin_points: set[Point] = set()
    for item in placed:
        for pin in item.component.profile.pins:
            endpoint = f"{item.component.ref}.{pin.number}"
            point = item.pin_point(pin.number)
            endpoint_points[endpoint] = point
            if item.component.profile.is_pseudo_component:
                pseudo_endpoints.add(endpoint)
                pseudo_representation_by_endpoint[endpoint] = str(item.component.profile.native_representation or "")
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
        has_virtual_terminal = False
        for endpoint in endpoints:
            if endpoint in pseudo_endpoints:
                representation = pseudo_representation_by_endpoint[endpoint]
                if representation == "flag_0":
                    if not _is_ground(net):
                        raise ValueError(f"Ground pseudo-component endpoint {endpoint} is assigned to non-ground net {net!r}.")
                    virtual.append(VirtualNativeAnchor(endpoint, net, endpoint_points[endpoint], "0"))
                elif representation == "virtual_terminal":
                    # A portable connector/power marker is not a SPICE
                    # primitive, but it remains a real canonical endpoint.
                    # Give it the same deterministic native label as physical
                    # terminals so the independent parser can prove its net
                    # membership without fabricating a device card.
                    virtual.append(VirtualNativeAnchor(endpoint, net, endpoint_points[endpoint], label))
                    has_virtual_terminal = True
                else:  # Defensive guard against a future pseudo profile.
                    raise ValueError(f"Pseudo-component endpoint {endpoint} has unknown native representation {representation!r}.")
            else:
                native_members.append(endpoint)
        expected_native[net] = native_members
        # A virtual terminal needs a persisted native label.  A direct wire is
        # electrically valid but LTspice may rename it to N00x in the exported
        # netlist, leaving the interface marker unprovable.  Terminal labels
        # make that contract exact and are still native LTspice connectivity.
        force_terminal = net.upper() in forced_terminal_names or has_virtual_terminal
        can_try_direct = (
            requested_mode in {"wire", "combination"}
            and len(physical) == 2
            and not _is_ground(net)
            and not force_terminal
        )
        can_try_tree = (
            requested_mode in {"wire", "combination"}
            and len(physical) >= 3
            and not _is_ground(net)
            and not force_terminal
        )
        if can_try_direct:
            route = _direct_route(endpoint_points[physical[0]], endpoint_points[physical[1]], segments, all_pin_points - {endpoint_points[physical[0]], endpoint_points[physical[1]]})
            if route is not None:
                segments.extend(route)
                continue
            if requested_mode == "wire":
                raise ValueError(f"Strict wire routing could not prove a safe direct route for net {net!r}.")
            rejected.append({"net": net, "reason": "direct_route_intersects_existing_geometry", "fallback": "terminal_flags"})
        elif can_try_tree:
            physical_points = {endpoint_points[endpoint] for endpoint in physical}
            route = _safe_tree_route(physical_points, segments, all_pin_points - physical_points)
            if route is not None:
                segments.extend(route)
                continue
            if requested_mode == "wire":
                raise ValueError(f"Strict wire routing could not prove a safe Manhattan tree for net {net!r}.")
            rejected.append(
                {
                    "net": net,
                    "reason": "safe_tree_router_could_not_prove_route",
                    "fallback": "terminal_flags",
                }
            )
        elif force_terminal and physical:
            # An analysis V(net) expression must name a native LTspice node.
            # Direct wires lack a persisted label and netlist as simulator
            # generated Nxxx nodes, so retain deterministic terminal flags.
            if requested_mode == "wire" and not _is_ground(net):
                raise ValueError(f"Strict wire routing cannot use a required terminal label for net {net!r}.")
            rejected.append(
                {
                    "net": net,
                    "reason": "analysis_voltage_trace_requires_stable_native_label",
                    "fallback": "terminal_flags",
                }
            )
        elif requested_mode == "wire" and physical and not _is_ground(net):
            raise ValueError(f"Strict wire routing cannot use terminal fallback for net {net!r}.")
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
        purpose = "virtual_ground_anchor" if anchor.native_flag == "0" else "virtual_interface_anchor"
        flags.append(NetFlag(anchor.point, anchor.native_flag, anchor.logical_net, anchor.endpoint, purpose))
    return WirePlan(
        mode=requested_mode,
        segments=tuple(segments),
        flags=tuple(flags),
        virtual_anchors=tuple(virtual),
        expected_native_nets=expected_native,
        label_map=label_map,
        forced_terminal_nets=tuple(net for net in nets if net.upper() in forced_terminal_names),
        rejected_wire_routes=tuple(rejected),
    )
