"""Deterministic orthogonal routing primitives shared by KiCad V1.

The router works in plain 2D geometry.  It does not know about KiCad
S-expressions, which keeps it reusable for a later Proteus visual router.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from statistics import median

Point = tuple[float, float]


@dataclass(frozen=True)
class Obstacle:
    owner: str
    left: float
    top: float
    right: float
    bottom: float

    def inflated(self, margin: float) -> "Obstacle":
        return Obstacle(
            self.owner,
            self.left - margin,
            self.top - margin,
            self.right + margin,
            self.bottom + margin,
        )

    def contains(self, p: Point, *, eps: float = 1e-6) -> bool:
        x, y = p
        return self.left - eps <= x <= self.right + eps and self.top - eps <= y <= self.bottom + eps


@dataclass(frozen=True)
class WireSegment:
    net: str
    a: Point
    b: Point


@dataclass(frozen=True)
class RoutingResult:
    segments: tuple[WireSegment, ...]
    junctions: tuple[Point, ...]
    label_points: dict[str, Point]
    warnings: tuple[str, ...]
    local_label_points: tuple[tuple[str, Point], ...] = ()


def _round_point(p: Point) -> Point:
    return (round(p[0], 3), round(p[1], 3))


def _dedupe(points: list[Point]) -> list[Point]:
    out: list[Point] = []
    seen: set[Point] = set()
    for p in points:
        rp = _round_point(p)
        if rp not in seen:
            seen.add(rp)
            out.append(rp)
    return out


def _axis_segment_crosses_obstacle(a: Point, b: Point, obstacle: Obstacle) -> bool:
    if a == b:
        return False
    ax, ay = a
    bx, by = b
    if obstacle.contains(a) or obstacle.contains(b):
        return False
    if ay == by:
        x1, x2 = sorted((ax, bx))
        return x1 < obstacle.right and x2 > obstacle.left and obstacle.top < ay < obstacle.bottom
    if ax == bx:
        y1, y2 = sorted((ay, by))
        return y1 < obstacle.bottom and y2 > obstacle.top and obstacle.left < ax < obstacle.right
    raise ValueError(f"non-orthogonal segment {a} -> {b}")


def _segment_clear(a: Point, b: Point, obstacles: tuple[Obstacle, ...]) -> bool:
    return not any(_axis_segment_crosses_obstacle(a, b, obstacle) for obstacle in obstacles)


def _path_clear(path: list[Point], obstacles: tuple[Obstacle, ...]) -> bool:
    for point in path[1:-1]:
        if any(obstacle.contains(point) for obstacle in obstacles):
            return False
    return all(_segment_clear(a, b, obstacles) for a, b in zip(path, path[1:]))


def _candidate_offsets(base: float, step: float) -> list[float]:
    offsets = [0.0]
    for i in range(1, 18):
        offsets.extend((-i * step, i * step))
    return [round(base + offset, 3) for offset in offsets]


def _path_length(path: list[Point]) -> float:
    return sum(abs(a[0] - b[0]) + abs(a[1] - b[1]) for a, b in zip(path, path[1:]))


def _path_cross_count(net: str, path: list[Point], routed: tuple[WireSegment, ...]) -> int:
    count = 0
    for segment in _segments_from_path(net, path):
        count += sum(1 for existing in routed if _crosses(segment, existing))
    return count


def _two_point_path(
    net: str,
    a: Point,
    b: Point,
    obstacles: tuple[Obstacle, ...],
    step: float,
    routed: tuple[WireSegment, ...],
) -> list[Point]:
    candidates = [
        [a, (b[0], a[1]), b],
        [a, (a[0], b[1]), b],
    ]
    if a[0] == b[0] or a[1] == b[1]:
        candidates.insert(0, [a, b])
    high = min(a[1], b[1]) - 2 * step
    low = max(a[1], b[1]) + 2 * step
    candidates.extend(
        [
            [a, (a[0], high), (b[0], high), b],
            [a, (a[0], low), (b[0], low), b],
        ]
    )
    left = min(a[0], b[0]) - 2 * step
    right = max(a[0], b[0]) + 2 * step
    candidates.extend(
        [
            [a, (left, a[1]), (left, b[1]), b],
            [a, (right, a[1]), (right, b[1]), b],
        ]
    )
    x_mid = round((a[0] + b[0]) / 2, 3)
    y_mid = round((a[1] + b[1]) / 2, 3)
    for x in _candidate_offsets(x_mid, step)[:12]:
        candidates.append([a, (x, a[1]), (x, b[1]), b])
    for y in _candidate_offsets(y_mid, step)[:12]:
        candidates.append([a, (a[0], y), (b[0], y), b])

    clear = [path for path in candidates if _path_clear(path, obstacles)]
    if clear:
        best = min(clear, key=lambda path: (_path_cross_count(net, path, routed), _path_length(path), len(path)))
        return [_round_point(p) for p in best]
    fallback = min(candidates, key=lambda path: (_path_cross_count(net, path, routed), _path_length(path), len(path)))
    return [_round_point(p) for p in fallback]


def _trunk_y(
    net: str,
    points: list[Point],
    obstacles: tuple[Obstacle, ...],
    step: float,
    routed: tuple[WireSegment, ...],
) -> float:
    ys = [p[1] for p in points]
    xs = [p[0] for p in points]
    low = max(ys) + 2 * step
    high = min(ys) - 2 * step
    base = low if net.upper() in {"GND", "0", "VSS"} else high if net.upper() in {"VCC", "VDD", "VIN"} else median(ys)
    left = min(xs) - step
    right = max(xs) + step
    candidates = []
    for y in _candidate_offsets(base, step):
        if any(
            branch != p and any(obstacle.contains(branch) for obstacle in obstacles)
            for p in points
            for branch in [_round_point((p[0], y))]
        ):
            continue
        if _segment_clear((left, y), (right, y), obstacles):
            trunk = [WireSegment(net, _round_point((left, y)), _round_point((right, y)))]
            crossings = sum(1 for segment in trunk for existing in routed if _crosses(segment, existing))
            candidates.append((crossings, abs(y - base), y))
    if candidates:
        return min(candidates)[2]
    return round(base, 3)


def _segments_from_path(net: str, path: list[Point]) -> list[WireSegment]:
    out: list[WireSegment] = []
    for a, b in zip(path, path[1:]):
        a = _round_point(a)
        b = _round_point(b)
        if a != b:
            out.append(WireSegment(net, a, b))
    return out


def _between(value: float, a: float, b: float) -> bool:
    low, high = sorted((a, b))
    return low < value < high


def _crosses(a: WireSegment, b: WireSegment) -> bool:
    if a.net == b.net:
        return False
    a_horizontal = a.a[1] == a.b[1]
    b_horizontal = b.a[1] == b.b[1]
    if a_horizontal == b_horizontal:
        return False
    horizontal = a if a_horizontal else b
    vertical = b if a_horizontal else a
    x = vertical.a[0]
    y = horizontal.a[1]
    if not (_between(x, horizontal.a[0], horizontal.b[0]) and _between(y, vertical.a[1], vertical.b[1])):
        return False
    if (x, y) in {horizontal.a, horizontal.b, vertical.a, vertical.b}:
        return False
    return True


def _crossing_warnings(segments: list[WireSegment]) -> list[str]:
    warnings: list[str] = []
    for index, left in enumerate(segments):
        for right in segments[index + 1 :]:
            if _crosses(left, right):
                warnings.append(
                    f"Different-net crossing: {left.net} {left.a}->{left.b} crosses {right.net} {right.a}->{right.b}"
                )
    return warnings


def _use_local_labels(net: str, points: list[Point]) -> bool:
    """Keep rails and broad fanout nets readable by labeling each endpoint."""
    upper = net.upper()
    if upper in {"GND", "0", "VSS", "VCC", "VDD", "VIN", "+5V", "5V"}:
        return True
    if re.match(r".*(CLK|CLOCK|RESET|CLR|LOAD|STORE|ENABLE|^EN|_EN$|OE|INH).*", upper):
        return len(points) >= 2
    if re.match(r"^(Q|D|A|B|S|P|Y|LQ|QA|QB|QC|QD|SEG_|LIM|CH|SW_|K|TZS)\w*$", upper):
        return len(points) >= 2
    return len(points) >= 7


def route_nets(
    points_by_net: dict[str, list[Point]],
    obstacles: tuple[Obstacle, ...],
    *,
    grid: float = 2.54,
    clearance: float = 1.27,
) -> RoutingResult:
    inflated = tuple(obstacle.inflated(clearance) for obstacle in obstacles)
    segments: list[WireSegment] = []
    routed: list[WireSegment] = []
    junction_candidates: dict[Point, int] = {}
    label_points: dict[str, Point] = {}
    local_label_points: list[tuple[str, Point]] = []
    warnings: list[str] = []

    for net in sorted(points_by_net):
        points = _dedupe(points_by_net[net])
        if not points:
            continue
        label_points[net] = points[0]
        if len(points) < 2:
            local_label_points.append((net, points[0]))
            continue
        if _use_local_labels(net, points):
            local_label_points.extend((net, point) for point in points)
            continue
        if len(points) == 2:
            path = _two_point_path(net, points[0], points[1], inflated, grid, tuple(routed))
            new_segments = _segments_from_path(net, path)
            segments.extend(new_segments)
            routed.extend(new_segments)
            continue

        trunk = _trunk_y(net, points, inflated, grid, tuple(routed))
        left = min(p[0] for p in points)
        right = max(p[0] for p in points)
        trunk_start = _round_point((left, trunk))
        trunk_end = _round_point((right, trunk))
        trunk_segment = WireSegment(net, trunk_start, trunk_end)
        segments.append(trunk_segment)
        routed.append(trunk_segment)
        for p in points:
            branch = _round_point((p[0], trunk))
            if branch != p:
                # KiCad needs an explicit junction where a branch wire lands on
                # a trunk segment; visual contact alone can leave ERC with a
                # dangling endpoint on multi-point nets.
                junction_candidates[branch] = junction_candidates.get(branch, 0) + 2
                path = _two_point_path(net, p, branch, inflated, grid, tuple(routed))
                new_segments = _segments_from_path(net, path)
                segments.extend(new_segments)
                routed.extend(new_segments)

    clean_segments: list[WireSegment] = []
    seen_segments: set[tuple[str, Point, Point]] = set()
    for seg in segments:
        if seg.a == seg.b:
            continue
        key_points = tuple(sorted((seg.a, seg.b)))
        key = (seg.net, key_points[0], key_points[1])
        if seg.a[0] != seg.b[0] and seg.a[1] != seg.b[1]:
            warnings.append(f"Skipped non-orthogonal segment on {seg.net}: {seg.a}->{seg.b}")
            continue
        if key not in seen_segments:
            seen_segments.add(key)
            clean_segments.append(seg)

    warnings.extend(_crossing_warnings(clean_segments))
    junctions = tuple(sorted((point for point, count in junction_candidates.items() if count >= 2), key=lambda p: (p[1], p[0])))
    return RoutingResult(tuple(clean_segments), junctions, label_points, tuple(warnings), tuple(local_label_points))
