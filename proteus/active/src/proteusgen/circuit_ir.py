"""Typed in-memory representation of the CircuitIR JSON contract."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Issue:
    code: str
    message: str
    path: str | None = None
    suggestion: str | None = None

    def as_dict(self) -> dict[str, str]:
        out = {"code": self.code, "message": self.message}
        if self.path is not None:
            out["path"] = self.path
        if self.suggestion is not None:
            out["suggestion"] = self.suggestion
        return out


@dataclass(frozen=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True)
class Target:
    proteus_version: str
    style: str
    sheet_count: int = 1
    mode: str = "production"


@dataclass(frozen=True)
class Component:
    ref: str
    part: str
    value: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Net:
    name: str
    kind: str


@dataclass(frozen=True)
class Connection:
    component: str
    pin: str
    net: str


@dataclass(frozen=True)
class Terminal:
    label: str
    net: str
    kind: str
    at: Point


@dataclass(frozen=True)
class Wire:
    net: str
    points: tuple[Point, ...]


@dataclass(frozen=True)
class Junction:
    net: str
    at: Point


@dataclass(frozen=True)
class Placement:
    component: str
    at: Point
    unit: str | None = None
    orientation: str = "horizontal"


@dataclass(frozen=True)
class Layout:
    terminals: tuple[Terminal, ...] = ()
    wires: tuple[Wire, ...] = ()
    junctions: tuple[Junction, ...] = ()
    placements: tuple[Placement, ...] = ()

    @property
    def has_rendered_geometry(self) -> bool:
        return bool(self.terminals or self.wires or self.junctions or self.placements)


@dataclass(frozen=True)
class Circuit:
    name: str
    components: tuple[Component, ...]
    nets: tuple[Net, ...]
    connections: tuple[Connection, ...]
    equation: str | None = None
    layout: Layout = Layout()


@dataclass(frozen=True)
class CircuitIR:
    version: str
    target: Target
    circuit: Circuit


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _mapping(value: Any, path: str, issues: list[Issue]) -> dict[str, Any]:
    if not isinstance(value, dict):
        issues.append(Issue("INVALID_TYPE", "Expected an object.", path))
        return {}
    return value


def _array(value: Any, path: str, issues: list[Issue]) -> list[Any]:
    if not isinstance(value, list):
        issues.append(Issue("INVALID_TYPE", "Expected an array.", path))
        return []
    return value


def _string(data: dict[str, Any], key: str, path: str, issues: list[Issue], default: str = "") -> str:
    value = data.get(key, default)
    if not isinstance(value, str) or not value:
        issues.append(Issue("INVALID_STRING", f"`{key}` must be a non-empty string.", f"{path}.{key}"))
        return default
    return value


def _point(data: Any, path: str, issues: list[Issue]) -> Point:
    obj = _mapping(data, path, issues)
    _unexpected(obj, {"x", "y"}, path, issues)
    x = obj.get("x")
    y = obj.get("y")
    if not isinstance(x, int) or not isinstance(y, int):
        issues.append(Issue("INVALID_POINT", "Grid point requires integer `x` and `y`.", path))
        return Point(0, 0)
    return Point(x=x, y=y)


def _unexpected(data: dict[str, Any], allowed: set[str], path: str, issues: list[Issue]) -> None:
    for key in sorted(set(data) - allowed):
        issues.append(Issue("UNEXPECTED_FIELD", f"Field `{key}` is not allowed.", f"{path}.{key}"))


def parse_circuit_ir(payload: Any) -> tuple[CircuitIR | None, list[Issue]]:
    """Parse JSON into CircuitIR and return structural issues without raising."""

    issues: list[Issue] = []
    root = _mapping(payload, "$", issues)
    _unexpected(root, {"version", "target", "circuit"}, "$", issues)
    version = _string(root, "version", "$", issues)
    target_obj = _mapping(root.get("target"), "$.target", issues)
    _unexpected(target_obj, {"proteus_version", "style", "sheet_count", "mode"}, "$.target", issues)
    target = Target(
        proteus_version=_string(target_obj, "proteus_version", "$.target", issues),
        style=_string(target_obj, "style", "$.target", issues),
        sheet_count=target_obj.get("sheet_count", 1),
        mode=target_obj.get("mode", "production"),
    )
    if not isinstance(target.sheet_count, int):
        issues.append(Issue("INVALID_TYPE", "`sheet_count` must be an integer.", "$.target.sheet_count"))
    if not isinstance(target.mode, str):
        issues.append(Issue("INVALID_TYPE", "`mode` must be a string.", "$.target.mode"))

    circuit_obj = _mapping(root.get("circuit"), "$.circuit", issues)
    _unexpected(circuit_obj, {"name", "components", "nets", "connections", "equation", "layout"}, "$.circuit", issues)
    name = _string(circuit_obj, "name", "$.circuit", issues)
    equation = circuit_obj.get("equation")
    if equation is not None and not isinstance(equation, str):
        issues.append(Issue("INVALID_TYPE", "`equation` must be a string.", "$.circuit.equation"))
        equation = None
    components: list[Component] = []
    for index, raw in enumerate(_array(circuit_obj.get("components"), "$.circuit.components", issues)):
        item = _mapping(raw, f"$.circuit.components[{index}]", issues)
        _unexpected(item, {"ref", "part", "value", "metadata"}, f"$.circuit.components[{index}]", issues)
        value = item.get("value")
        if value is not None and not isinstance(value, str):
            issues.append(Issue("INVALID_TYPE", "`value` must be a string.", f"$.circuit.components[{index}].value"))
            value = None
        metadata = item.get("metadata", {})
        if not isinstance(metadata, dict):
            issues.append(Issue("INVALID_TYPE", "`metadata` must be an object.", f"$.circuit.components[{index}].metadata"))
            metadata = {}
        components.append(
            Component(
                ref=_string(item, "ref", f"$.circuit.components[{index}]", issues),
                part=_string(item, "part", f"$.circuit.components[{index}]", issues),
                value=value,
                metadata=metadata,
            )
        )
    nets: list[Net] = []
    for index, raw in enumerate(_array(circuit_obj.get("nets"), "$.circuit.nets", issues)):
        item = _mapping(raw, f"$.circuit.nets[{index}]", issues)
        _unexpected(item, {"name", "kind"}, f"$.circuit.nets[{index}]", issues)
        nets.append(
            Net(
                name=_string(item, "name", f"$.circuit.nets[{index}]", issues),
                kind=_string(item, "kind", f"$.circuit.nets[{index}]", issues),
            )
        )
    connections: list[Connection] = []
    for index, raw in enumerate(_array(circuit_obj.get("connections"), "$.circuit.connections", issues)):
        item = _mapping(raw, f"$.circuit.connections[{index}]", issues)
        _unexpected(item, {"component", "pin", "net"}, f"$.circuit.connections[{index}]", issues)
        connections.append(
            Connection(
                component=_string(item, "component", f"$.circuit.connections[{index}]", issues),
                pin=_string(item, "pin", f"$.circuit.connections[{index}]", issues),
                net=_string(item, "net", f"$.circuit.connections[{index}]", issues),
            )
        )

    layout_obj = circuit_obj.get("layout", {})
    if layout_obj is None:
        layout_obj = {}
    layout_raw = _mapping(layout_obj, "$.circuit.layout", issues)
    _unexpected(layout_raw, {"terminals", "wires", "junctions", "placements"}, "$.circuit.layout", issues)
    terminals: list[Terminal] = []
    for index, raw in enumerate(_array(layout_raw.get("terminals", []), "$.circuit.layout.terminals", issues)):
        item = _mapping(raw, f"$.circuit.layout.terminals[{index}]", issues)
        _unexpected(item, {"label", "net", "kind", "at"}, f"$.circuit.layout.terminals[{index}]", issues)
        terminals.append(
            Terminal(
                label=_string(item, "label", f"$.circuit.layout.terminals[{index}]", issues),
                net=_string(item, "net", f"$.circuit.layout.terminals[{index}]", issues),
                kind=_string(item, "kind", f"$.circuit.layout.terminals[{index}]", issues),
                at=_point(item.get("at"), f"$.circuit.layout.terminals[{index}].at", issues),
            )
        )
    wires: list[Wire] = []
    for index, raw in enumerate(_array(layout_raw.get("wires", []), "$.circuit.layout.wires", issues)):
        item = _mapping(raw, f"$.circuit.layout.wires[{index}]", issues)
        _unexpected(item, {"net", "points"}, f"$.circuit.layout.wires[{index}]", issues)
        points = tuple(
            _point(point, f"$.circuit.layout.wires[{index}].points[{point_index}]", issues)
            for point_index, point in enumerate(_array(item.get("points"), f"$.circuit.layout.wires[{index}].points", issues))
        )
        wires.append(Wire(net=_string(item, "net", f"$.circuit.layout.wires[{index}]", issues), points=points))
    junctions: list[Junction] = []
    for index, raw in enumerate(_array(layout_raw.get("junctions", []), "$.circuit.layout.junctions", issues)):
        item = _mapping(raw, f"$.circuit.layout.junctions[{index}]", issues)
        _unexpected(item, {"net", "at"}, f"$.circuit.layout.junctions[{index}]", issues)
        junctions.append(
            Junction(
                net=_string(item, "net", f"$.circuit.layout.junctions[{index}]", issues),
                at=_point(item.get("at"), f"$.circuit.layout.junctions[{index}].at", issues),
            )
        )
    placements: list[Placement] = []
    for index, raw in enumerate(_array(layout_raw.get("placements", []), "$.circuit.layout.placements", issues)):
        item = _mapping(raw, f"$.circuit.layout.placements[{index}]", issues)
        _unexpected(item, {"component", "unit", "orientation", "at"}, f"$.circuit.layout.placements[{index}]", issues)
        unit = item.get("unit")
        orientation = item.get("orientation", "horizontal")
        if unit is not None and not isinstance(unit, str):
            issues.append(Issue("INVALID_TYPE", "`unit` must be a string.", f"$.circuit.layout.placements[{index}].unit"))
            unit = None
        if not isinstance(orientation, str):
            issues.append(Issue("INVALID_TYPE", "`orientation` must be a string.", f"$.circuit.layout.placements[{index}].orientation"))
            orientation = "horizontal"
        placements.append(
            Placement(
                component=_string(item, "component", f"$.circuit.layout.placements[{index}]", issues),
                unit=unit,
                orientation=orientation,
                at=_point(item.get("at"), f"$.circuit.layout.placements[{index}].at", issues),
            )
        )

    if issues:
        return None, issues
    return (
        CircuitIR(
            version=version,
            target=target,
            circuit=Circuit(
                name=name,
                components=tuple(components),
                nets=tuple(nets),
                connections=tuple(connections),
                equation=equation,
                layout=Layout(
                    terminals=tuple(terminals),
                    wires=tuple(wires),
                    junctions=tuple(junctions),
                    placements=tuple(placements),
                ),
            ),
        ),
        [],
    )
