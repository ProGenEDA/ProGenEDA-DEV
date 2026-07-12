"""Native LTspice grid geometry and orientation transforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .catalogue import ORIENTATIONS


GRID = 16


@dataclass(frozen=True, order=True)
class Point:
    x: int
    y: int

    def translate(self, dx: int, dy: int) -> "Point":
        return Point(self.x + dx, self.y + dy)


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point

    @property
    def is_horizontal(self) -> bool:
        return self.start.y == self.end.y

    @property
    def is_vertical(self) -> bool:
        return self.start.x == self.end.x

    def contains(self, point: Point) -> bool:
        if self.is_horizontal:
            return point.y == self.start.y and min(self.start.x, self.end.x) <= point.x <= max(self.start.x, self.end.x)
        if self.is_vertical:
            return point.x == self.start.x and min(self.start.y, self.end.y) <= point.y <= max(self.start.y, self.end.y)
        return False


def snap(value: int, grid: int = GRID) -> int:
    """Round an integer to the nearest native grid coordinate."""

    return int(round(value / grid)) * grid


def normalize_orientation(value: object) -> str:
    orientation = str(value or "R0").upper()
    if orientation not in ORIENTATIONS:
        raise ValueError(f"Unsupported LTspice orientation {value!r}; expected one of {', '.join(ORIENTATIONS)}.")
    return orientation


def transform_offset(point: Point, orientation: object) -> Point:
    """Transform a symbol-local point around the LTspice symbol origin.

    LTspice uses a screen coordinate system (positive Y down). The formulas
    therefore express clockwise rotation directly in that coordinate system.
    Mirrors match the documented M0/M90/M180/M270 family.
    """

    x, y = point.x, point.y
    token = normalize_orientation(orientation)
    transforms = {
        "R0": (x, y),
        "R90": (-y, x),
        "R180": (-x, -y),
        "R270": (y, -x),
        "M0": (-x, y),
        "M90": (y, x),
        "M180": (x, -y),
        "M270": (-y, -x),
    }
    result = transforms[token]
    return Point(*result)


def transform_point(origin: Point, local: Point, orientation: object) -> Point:
    offset = transform_offset(local, orientation)
    return origin.translate(offset.x, offset.y)


def orthogonal_path(start: Point, end: Point, *, prefer_horizontal: bool = True) -> list[Segment]:
    """Return a compact axis-aligned route with no zero-length segments."""

    if start == end:
        return []
    if start.x == end.x or start.y == end.y:
        return [Segment(start, end)]
    elbow = Point(end.x, start.y) if prefer_horizontal else Point(start.x, end.y)
    return [Segment(start, elbow), Segment(elbow, end)]


def segment_intersection(first: Segment, second: Segment) -> Point | None:
    """Find an axis-aligned segment intersection, including endpoint contact."""

    if not (first.is_horizontal or first.is_vertical) or not (second.is_horizontal or second.is_vertical):
        return None
    if first.is_horizontal and second.is_vertical:
        point = Point(second.start.x, first.start.y)
        return point if first.contains(point) and second.contains(point) else None
    if first.is_vertical and second.is_horizontal:
        point = Point(first.start.x, second.start.y)
        return point if first.contains(point) and second.contains(point) else None
    if first.is_horizontal and second.is_horizontal:
        if first.start.y != second.start.y:
            return None
        low = max(min(first.start.x, first.end.x), min(second.start.x, second.end.x))
        high = min(max(first.start.x, first.end.x), max(second.start.x, second.end.x))
        return Point(low, first.start.y) if low <= high else None
    if first.start.x != second.start.x:
        return None
    low = max(min(first.start.y, first.end.y), min(second.start.y, second.end.y))
    high = min(max(first.start.y, first.end.y), max(second.start.y, second.end.y))
    return Point(first.start.x, low) if low <= high else None


def points_on_segments(segments: Iterable[Segment], candidates: Iterable[Point]) -> set[Point]:
    return {point for point in candidates if any(segment.contains(point) for segment in segments)}
