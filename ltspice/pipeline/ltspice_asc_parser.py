"""Independent parser and connectivity extractor for LTspice ASC/ASY files."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Iterable

from .geometry import Point, Segment, segment_intersection, transform_point


ASC_PARSER_SCHEMA = "progen-ltspice-asc-parser/v0.1"


class AscParseError(ValueError):
    """An ASC or ASY record cannot be safely reconstructed."""


@dataclass(frozen=True)
class WindowRecord:
    number: int
    x: int
    y: int
    justification: str
    font_size: int


@dataclass
class AscSymbol:
    name: str
    origin: Point
    orientation: str
    attributes: dict[str, str] = field(default_factory=dict)
    windows: list[WindowRecord] = field(default_factory=list)
    line_number: int = 0

    @property
    def ref(self) -> str:
        return self.attributes.get("INSTNAME", "")


@dataclass(frozen=True)
class AscFlag:
    point: Point
    name: str
    line_number: int


@dataclass(frozen=True)
class AsyPin:
    point: Point
    justification: str
    name: str
    spice_order: str


@dataclass(frozen=True)
class AsySymbol:
    name: str
    path: Path
    attributes: dict[str, str]
    pins: tuple[AsyPin, ...]
    windows: tuple[WindowRecord, ...]


@dataclass
class AscDocument:
    path: Path
    encoding: str
    version: str | None
    sheet: tuple[int, int, int] | None
    symbols: list[AscSymbol]
    wires: list[Segment]
    flags: list[AscFlag]
    texts: list[dict[str, Any]]
    unknown_records: list[dict[str, Any]]


@dataclass(frozen=True)
class ResolvedPin:
    endpoint: str
    ref: str
    spice_order: str
    pin_name: str
    point: Point
    symbol_name: str


class _DisjointSet:
    def __init__(self) -> None:
        self.parent: dict[object, object] = {}

    def add(self, item: object) -> None:
        self.parent.setdefault(item, item)

    def find(self, item: object) -> object:
        self.add(item)
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, first: object, second: object) -> None:
        left, right = self.find(first), self.find(second)
        if left != right:
            self.parent[right] = left


def decode_lts_text(data: bytes) -> tuple[str, str]:
    """Decode current UTF-8 data and legacy donor CP1252 data deterministically."""

    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252"), "cp1252"


def _parse_int(value: str, *, context: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise AscParseError(f"{context} requires an integer, got {value!r}.") from exc


def _split(line: str, count: int, *, context: str) -> list[str]:
    parts = line.strip().split(maxsplit=count - 1)
    if len(parts) < count:
        raise AscParseError(f"{context} has too few fields: {line!r}")
    return parts


def parse_asc(path: Path) -> AscDocument:
    text, encoding = decode_lts_text(path.read_bytes())
    symbols: list[AscSymbol] = []
    wires: list[Segment] = []
    flags: list[AscFlag] = []
    texts: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    version: str | None = None
    sheet: tuple[int, int, int] | None = None
    current_symbol: AscSymbol | None = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip("\r")
        if not line.strip():
            continue
        keyword = line.split(maxsplit=1)[0].upper()
        try:
            if keyword == "VERSION":
                version = _split(line, 2, context="VERSION")[1]
                current_symbol = None
            elif keyword == "SHEET":
                parts = _split(line, 4, context="SHEET")
                sheet = tuple(_parse_int(value, context="SHEET") for value in parts[1:4])  # type: ignore[assignment]
                current_symbol = None
            elif keyword == "SYMBOL":
                parts = _split(line, 5, context="SYMBOL")
                current_symbol = AscSymbol(
                    name=parts[1].replace("\\", "/"),
                    origin=Point(_parse_int(parts[2], context="SYMBOL"), _parse_int(parts[3], context="SYMBOL")),
                    orientation=parts[4].upper(),
                    line_number=line_number,
                )
                symbols.append(current_symbol)
            elif keyword == "WINDOW":
                if current_symbol is None:
                    raise AscParseError("WINDOW appears before a SYMBOL.")
                parts = _split(line, 6, context="WINDOW")
                current_symbol.windows.append(
                    WindowRecord(
                        _parse_int(parts[1], context="WINDOW"),
                        _parse_int(parts[2], context="WINDOW"),
                        _parse_int(parts[3], context="WINDOW"),
                        parts[4],
                        _parse_int(parts[5], context="WINDOW"),
                    )
                )
            elif keyword == "SYMATTR":
                if current_symbol is None:
                    raise AscParseError("SYMATTR appears before a SYMBOL.")
                parts = _split(line, 3, context="SYMATTR")
                current_symbol.attributes[parts[1].upper()] = parts[2]
            elif keyword == "WIRE":
                parts = _split(line, 5, context="WIRE")
                wires.append(
                    Segment(
                        Point(_parse_int(parts[1], context="WIRE"), _parse_int(parts[2], context="WIRE")),
                        Point(_parse_int(parts[3], context="WIRE"), _parse_int(parts[4], context="WIRE")),
                    )
                )
                current_symbol = None
            elif keyword == "FLAG":
                parts = _split(line, 4, context="FLAG")
                flags.append(
                    AscFlag(
                        Point(_parse_int(parts[1], context="FLAG"), _parse_int(parts[2], context="FLAG")),
                        parts[3],
                        line_number,
                    )
                )
                current_symbol = None
            elif keyword == "TEXT":
                parts = _split(line, 6, context="TEXT")
                texts.append(
                    {
                        "point": {"x": _parse_int(parts[1], context="TEXT"), "y": _parse_int(parts[2], context="TEXT")},
                        "justification": parts[3],
                        "font_size": _parse_int(parts[4], context="TEXT"),
                        "text": parts[5],
                        "line_number": line_number,
                    }
                )
                current_symbol = None
            else:
                # Preserve unimplemented graphics/hierarchy records for a raw
                # inspection tool instead of silently pretending they vanished.
                unknown.append({"line_number": line_number, "keyword": keyword, "raw": raw})
                current_symbol = None
        except AscParseError:
            raise
        except Exception as exc:  # pragma: no cover - defensive record context
            raise AscParseError(f"Cannot parse {path}:{line_number}: {raw!r}") from exc
    if version is None:
        raise AscParseError(f"{path} has no VERSION record.")
    if sheet is None:
        raise AscParseError(f"{path} has no SHEET record.")
    return AscDocument(path, encoding, version, sheet, symbols, wires, flags, texts, unknown)


def parse_asy(path: Path, *, symbol_name: str | None = None) -> AsySymbol:
    text, _encoding = decode_lts_text(path.read_bytes())
    attributes: dict[str, str] = {}
    pins: list[AsyPin] = []
    windows: list[WindowRecord] = []
    pending_pin: dict[str, Any] | None = None
    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip("\r")
        if not line.strip():
            continue
        keyword = line.split(maxsplit=1)[0].upper()
        if keyword == "PIN":
            parts = _split(line, 5, context="PIN")
            if pending_pin is not None:
                pins.append(_finish_pin(pending_pin, path))
            pending_pin = {
                "point": Point(_parse_int(parts[1], context="PIN"), _parse_int(parts[2], context="PIN")),
                "justification": parts[3],
                "attrs": {},
                "line_number": line_number,
            }
        elif keyword == "PINATTR":
            if pending_pin is None:
                raise AscParseError(f"{path}:{line_number} PINATTR appears before PIN.")
            parts = _split(line, 3, context="PINATTR")
            pending_pin["attrs"][parts[1].upper()] = parts[2]
        elif keyword == "SYMATTR":
            parts = _split(line, 3, context="SYMATTR")
            attributes[parts[1].upper()] = parts[2]
        elif keyword == "WINDOW":
            parts = _split(line, 6, context="WINDOW")
            windows.append(
                WindowRecord(
                    _parse_int(parts[1], context="WINDOW"),
                    _parse_int(parts[2], context="WINDOW"),
                    _parse_int(parts[3], context="WINDOW"),
                    parts[4],
                    _parse_int(parts[5], context="WINDOW"),
                )
            )
    if pending_pin is not None:
        pins.append(_finish_pin(pending_pin, path))
    if not pins:
        raise AscParseError(f"{path} has no PIN records.")
    orders = [pin.spice_order for pin in pins]
    if len(set(orders)) != len(orders):
        raise AscParseError(f"{path} repeats PINATTR SpiceOrder values.")
    return AsySymbol(symbol_name or path.stem, path, attributes, tuple(pins), tuple(windows))


def _finish_pin(raw: dict[str, Any], path: Path) -> AsyPin:
    attrs = raw["attrs"]
    if "SPICEORDER" not in attrs:
        raise AscParseError(f"{path}:{raw['line_number']} PIN has no PINATTR SpiceOrder.")
    return AsyPin(
        point=raw["point"],
        justification=str(raw["justification"]),
        name=str(attrs.get("PINNAME", "")),
        spice_order=str(attrs["SPICEORDER"]),
    )


def resolve_symbol_path(name: str, *, project_dir: Path, symbol_search_paths: Iterable[Path] = ()) -> Path:
    normalized = name.replace("\\", "/").lstrip("/")
    if ".." in Path(normalized).parts:
        raise AscParseError(f"Unsafe relative symbol path {name!r}.")
    candidates = [project_dir / f"{normalized}.asy"]
    candidates.extend(path / f"{normalized}.asy" for path in symbol_search_paths)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise AscParseError(f"Cannot resolve LTspice symbol {name!r} beside {project_dir} or in configured search paths.")


def resolve_document_pins(
    document: AscDocument,
    *,
    project_dir: Path | None = None,
    symbol_search_paths: Iterable[Path] = (),
) -> tuple[dict[str, ResolvedPin], dict[str, AsySymbol]]:
    root = project_dir or document.path.parent
    asy_cache: dict[str, AsySymbol] = {}
    resolved: dict[str, ResolvedPin] = {}
    refs: set[str] = set()
    for instance in document.symbols:
        ref = instance.ref
        if not ref:
            raise AscParseError(f"{document.path}:{instance.line_number} symbol {instance.name!r} has no SYMATTR InstName.")
        if ref in refs:
            raise AscParseError(f"{document.path} repeats InstName {ref!r}.")
        refs.add(ref)
        symbol = asy_cache.get(instance.name)
        if symbol is None:
            path = resolve_symbol_path(instance.name, project_dir=root, symbol_search_paths=symbol_search_paths)
            symbol = parse_asy(path, symbol_name=instance.name)
            asy_cache[instance.name] = symbol
        for pin in symbol.pins:
            endpoint = f"{ref}.{pin.spice_order}"
            if endpoint in resolved:
                raise AscParseError(f"Resolved duplicate endpoint {endpoint!r}.")
            resolved[endpoint] = ResolvedPin(
                endpoint=endpoint,
                ref=ref,
                spice_order=pin.spice_order,
                pin_name=pin.name,
                point=transform_point(instance.origin, pin.point, instance.orientation),
                symbol_name=instance.name,
            )
    return resolved, asy_cache


def _point_node(point: Point) -> tuple[str, int, int]:
    return ("point", point.x, point.y)


def _safe_union_segments(dsu: _DisjointSet, segments: list[Segment], points: set[Point]) -> None:
    for segment in segments:
        if not (segment.is_horizontal or segment.is_vertical):
            raise AscParseError("Non-orthogonal wire cannot be statically validated.")
        on_segment = sorted((point for point in points if segment.contains(point)), key=lambda point: (point.x, point.y))
        for point in on_segment:
            dsu.add(_point_node(point))
        for left, right in zip(on_segment, on_segment[1:]):
            dsu.union(_point_node(left), _point_node(right))


def extract_connectivity(
    document: AscDocument,
    *,
    project_dir: Path | None = None,
    virtual_anchors: Iterable[dict[str, Any]] = (),
    symbol_search_paths: Iterable[Path] = (),
) -> dict[str, Any]:
    """Reconstruct electrical connected components from the files on disk."""

    pins, symbols = resolve_document_pins(document, project_dir=project_dir, symbol_search_paths=symbol_search_paths)
    virtual_points: dict[str, Point] = {}
    for anchor in virtual_anchors:
        endpoint = str(anchor.get("endpoint") or "")
        raw_point = anchor.get("point")
        if not endpoint or not isinstance(raw_point, dict):
            raise AscParseError("Virtual native anchor needs endpoint and point fields.")
        virtual_points[endpoint] = Point(int(raw_point["x"]), int(raw_point["y"]))
    all_points = {pin.point for pin in pins.values()}
    all_points.update(virtual_points.values())
    for wire in document.wires:
        all_points.update({wire.start, wire.end})
    for flag in document.flags:
        all_points.add(flag.point)
    for index, first in enumerate(document.wires):
        for second in document.wires[index + 1 :]:
            crossing = segment_intersection(first, second)
            if crossing is not None:
                all_points.add(crossing)
    dsu = _DisjointSet()
    for point in all_points:
        dsu.add(_point_node(point))
    _safe_union_segments(dsu, document.wires, all_points)
    endpoint_nodes: dict[str, object] = {}
    for endpoint, pin in pins.items():
        node = _point_node(pin.point)
        endpoint_nodes[endpoint] = node
        dsu.add(node)
    for endpoint, point in virtual_points.items():
        node = _point_node(point)
        endpoint_nodes[endpoint] = node
        dsu.add(node)
    labels: dict[str, list[Point]] = defaultdict(list)
    for flag in document.flags:
        labels[flag.name].append(flag.point)
    for points in labels.values():
        for left, right in zip(points, points[1:]):
            dsu.union(_point_node(left), _point_node(right))
    groups: dict[object, list[str]] = defaultdict(list)
    for endpoint, node in endpoint_nodes.items():
        groups[dsu.find(node)].append(endpoint)
    endpoint_groups = {endpoint: sorted(members) for members in groups.values() for endpoint in members}
    label_members: dict[str, list[str]] = {}
    for name, points in labels.items():
        members: set[str] = set()
        for point in points:
            root = dsu.find(_point_node(point))
            members.update(groups.get(root, []))
        label_members[name] = sorted(members)
    return {
        "schema": ASC_PARSER_SCHEMA,
        "path": str(document.path),
        "encoding": document.encoding,
        "version": document.version,
        "sheet": {"number": document.sheet[0], "width": document.sheet[1], "height": document.sheet[2]} if document.sheet else None,
        "symbols": {
            name: {
                "path": str(symbol.path),
                "prefix": symbol.attributes.get("PREFIX"),
                "pins": [
                    {
                        "spice_order": pin.spice_order,
                        "name": pin.name,
                        "local": {"x": pin.point.x, "y": pin.point.y},
                    }
                    for pin in sorted(symbol.pins, key=lambda item: int(item.spice_order) if item.spice_order.isdigit() else item.spice_order)
                ],
            }
            for name, symbol in sorted(symbols.items())
        },
        "resolved_pins": {
            endpoint: {
                "point": {"x": pin.point.x, "y": pin.point.y},
                "pin_name": pin.pin_name,
                "symbol": pin.symbol_name,
            }
            for endpoint, pin in sorted(pins.items())
        },
        "component_groups": sorted(sorted(members) for members in groups.values()),
        "endpoint_groups": endpoint_groups,
        "flag_members": dict(sorted(label_members.items())),
        "unknown_records": document.unknown_records,
    }
