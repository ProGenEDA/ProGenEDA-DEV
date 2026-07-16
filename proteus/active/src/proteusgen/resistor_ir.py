"""CircuitIR v0.1 parser for the locked V9 resistor generator."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .circuit_ir import Issue

SCHEMA_VERSION = "proteus-circuit-ir/v0.1"
GENERATOR_TARGET = "proteus-8.13-v9-resistor-terminal"
BASE_PROJECT = "E001_EMPTY_BASE"

NODE_ID_RE = re.compile(r"^[\x20-\x7e]{2}$")
REF_RE = re.compile(r"^[\x20-\x7e]{2}$")
VALUE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?[A-Za-z]?$")
NODE_KINDS = {"internal", "power", "ground"}
LAYOUT_MODES = {"manual_component_positions", "branch_grid", "auto_grid"}
ORIENTATION_ANGLE_BY_HINT = {
    "horizontal": 0,
    "right": 0,
    "east": 0,
    "vertical": -900,
    "vertical_down": -900,
    "down": -900,
    "south": -900,
    "vertical_up": 900,
    "up": 900,
    "north": 900,
    "left": 1800,
    "west": 1800,
}
ALLOWED_ORIENTATION_ANGLES = {0, 900, -900, 1800, -1800, 2700, -2700}


@dataclass(frozen=True)
class ResistorNode:
    id: str
    role: str | None = None
    kind: str = "internal"


@dataclass(frozen=True)
class ResistorComponent:
    ref: str
    type: str
    value: str
    nodes: tuple[str, str]
    visual: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ComponentPosition:
    x: int
    y: int


@dataclass(frozen=True)
class VisualWire:
    x1: int
    y1: int
    x2: int
    y2: int


@dataclass(frozen=True)
class ResistorLayout:
    mode: str
    coordinate_units: str
    component_positions: dict[str, ComponentPosition]
    visual_wires: tuple[VisualWire, ...] = ()
    auto_place: bool = False


@dataclass(frozen=True)
class ResistorProject:
    name: str
    output_basename: str
    base: str
    units: str


@dataclass(frozen=True)
class ResistorCircuitIR:
    schema_version: str
    generator_target: str
    project: ResistorProject
    nodes: tuple[ResistorNode, ...]
    components: tuple[ResistorComponent, ...]
    layout: ResistorLayout
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ResistorValidationReport:
    errors: tuple[Issue, ...]
    warnings: tuple[Issue, ...] = ()
    circuit: ResistorCircuitIR | None = None

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


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


def _nonempty_string(data: dict[str, Any], key: str, path: str, issues: list[Issue]) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        issues.append(Issue("INVALID_STRING", f"`{key}` must be a non-empty string.", f"{path}.{key}"))
        return ""
    return value


def _optional_string(data: dict[str, Any], key: str, path: str, issues: list[Issue]) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        issues.append(Issue("INVALID_TYPE", f"`{key}` must be a string.", f"{path}.{key}"))
        return None
    return value


def _unexpected(data: dict[str, Any], allowed: set[str], path: str, issues: list[Issue]) -> None:
    for key in sorted(set(data) - allowed):
        issues.append(Issue("UNEXPECTED_FIELD", f"Field `{key}` is not allowed.", f"{path}.{key}"))


def visible_resistor_value(value: str, visual: dict[str, Any] | None = None) -> str:
    """Return the two-character value field supported by the locked visual record."""

    override = (visual or {}).get("visible_value")
    if isinstance(override, str) and len(override.encode("ascii", errors="ignore")) == 2 and override.isascii():
        return override
    if len(value) == 2 and value.isascii():
        return value
    if len(value) > 2 and value[:2].isascii():
        return value[:2]
    raise ValueError(f"Value `{value}` has no validated two-character visible representation.")


def resistor_orientation_angle(visual: dict[str, Any] | None = None) -> int:
    """Return Proteus component rotation in tenths of a degree for a resistor."""

    data = visual or {}
    angle = data.get("angle_tenths")
    if angle is not None:
        if not isinstance(angle, int) or angle not in ALLOWED_ORIENTATION_ANGLES:
            raise ValueError("`angle_tenths` must be one of -2700, -1800, -900, 0, 900, 1800, or 2700.")
        return angle

    hint = data.get("orientation_hint", data.get("orientation"))
    if hint is None:
        return 0
    if not isinstance(hint, str):
        raise ValueError("`orientation_hint` must be a string.")
    key = hint.strip().lower().replace("-", "_")
    if key not in ORIENTATION_ANGLE_BY_HINT:
        allowed = ", ".join(sorted(ORIENTATION_ANGLE_BY_HINT))
        raise ValueError(f"Unsupported orientation hint `{hint}`. Use one of: {allowed}.")
    return ORIENTATION_ANGLE_BY_HINT[key]


def parse_resistor_ir(payload: Any) -> tuple[ResistorCircuitIR | None, list[Issue]]:
    issues: list[Issue] = []
    root = _mapping(payload, "$", issues)
    _unexpected(root, {"schema_version", "generator_target", "project", "nodes", "components", "layout", "metadata"}, "$", issues)

    schema_version = _nonempty_string(root, "schema_version", "$", issues)
    generator_target = _nonempty_string(root, "generator_target", "$", issues)

    project_obj = _mapping(root.get("project"), "$.project", issues)
    _unexpected(project_obj, {"name", "output_basename", "base", "units"}, "$.project", issues)
    project = ResistorProject(
        name=_nonempty_string(project_obj, "name", "$.project", issues),
        output_basename=_nonempty_string(project_obj, "output_basename", "$.project", issues),
        base=_nonempty_string(project_obj, "base", "$.project", issues),
        units=_nonempty_string(project_obj, "units", "$.project", issues),
    )

    nodes: list[ResistorNode] = []
    for index, raw in enumerate(_array(root.get("nodes"), "$.nodes", issues)):
        path = f"$.nodes[{index}]"
        item = _mapping(raw, path, issues)
        _unexpected(item, {"id", "role", "kind"}, path, issues)
        role = _optional_string(item, "role", path, issues)
        kind = item.get("kind", "internal")
        if not isinstance(kind, str):
            issues.append(Issue("INVALID_TYPE", "`kind` must be a string.", f"{path}.kind"))
            kind = "internal"
        nodes.append(ResistorNode(id=_nonempty_string(item, "id", path, issues), role=role, kind=kind))

    components: list[ResistorComponent] = []
    for index, raw in enumerate(_array(root.get("components"), "$.components", issues)):
        path = f"$.components[{index}]"
        item = _mapping(raw, path, issues)
        _unexpected(item, {"ref", "type", "value", "nodes", "visual"}, path, issues)
        raw_nodes = _array(item.get("nodes"), f"{path}.nodes", issues)
        component_nodes: tuple[str, str] = ("", "")
        if len(raw_nodes) != 2:
            issues.append(Issue("INVALID_ENDPOINT_COUNT", "`nodes` must contain exactly two endpoint node ids.", f"{path}.nodes"))
        else:
            left, right = raw_nodes
            if not isinstance(left, str) or not isinstance(right, str):
                issues.append(Issue("INVALID_TYPE", "Endpoint node ids must be strings.", f"{path}.nodes"))
            else:
                component_nodes = (left, right)
        visual = item.get("visual", {})
        if not isinstance(visual, dict):
            issues.append(Issue("INVALID_TYPE", "`visual` must be an object.", f"{path}.visual"))
            visual = {}
        components.append(
            ResistorComponent(
                ref=_nonempty_string(item, "ref", path, issues),
                type=_nonempty_string(item, "type", path, issues),
                value=_nonempty_string(item, "value", path, issues),
                nodes=component_nodes,
                visual=visual,
            )
        )

    layout_obj = _mapping(root.get("layout", {}), "$.layout", issues)
    _unexpected(
        layout_obj,
        {
            "mode",
            "coordinate_units",
            "component_positions",
            "source_positions",
            "visual_wires",
            "auto_place",
            "strategy",
            "direction",
        },
        "$.layout",
        issues,
    )
    positions_obj = layout_obj.get("component_positions", {})
    if positions_obj is None:
        positions_obj = {}
    positions_raw = _mapping(positions_obj, "$.layout.component_positions", issues)
    positions: dict[str, ComponentPosition] = {}
    for ref, raw_position in positions_raw.items():
        path = f"$.layout.component_positions.{ref}"
        position = _mapping(raw_position, path, issues)
        _unexpected(position, {"x", "y"}, path, issues)
        x = position.get("x")
        y = position.get("y")
        if not isinstance(x, int) or not isinstance(y, int):
            issues.append(Issue("INVALID_POSITION", "Component positions require integer `x` and `y`.", path))
            continue
        positions[ref] = ComponentPosition(x=x, y=y)
    visual_wires_raw = layout_obj.get("visual_wires", [])
    if visual_wires_raw is None:
        visual_wires_raw = []
    visual_wires: list[VisualWire] = []
    for index, raw_wire in enumerate(_array(visual_wires_raw, "$.layout.visual_wires", issues)):
        path = f"$.layout.visual_wires[{index}]"
        wire = _mapping(raw_wire, path, issues)
        _unexpected(wire, {"x1", "y1", "x2", "y2"}, path, issues)
        coords = {key: wire.get(key) for key in ("x1", "y1", "x2", "y2")}
        if not all(isinstance(value, int) for value in coords.values()):
            issues.append(Issue("INVALID_VISUAL_WIRE", "Visual wires require integer x1, y1, x2, and y2.", path))
            continue
        visual_wires.append(VisualWire(x1=coords["x1"], y1=coords["y1"], x2=coords["x2"], y2=coords["y2"]))
    strategy = layout_obj.get("strategy")
    if strategy is not None and strategy not in {"beautify", "manual", "legacy"}:
        issues.append(
            Issue(
                "UNSUPPORTED_LAYOUT_STRATEGY",
                "Use `beautify`, `manual`, or `legacy`.",
                "$.layout.strategy",
            )
        )
    direction = layout_obj.get("direction", "left_to_right")
    if direction != "left_to_right":
        issues.append(
            Issue(
                "UNSUPPORTED_LAYOUT_DIRECTION",
                "Only `left_to_right` is currently supported.",
                "$.layout.direction",
            )
        )
    auto_place = layout_obj.get("auto_place", strategy == "beautify" or not layout_obj)
    if not isinstance(auto_place, bool):
        issues.append(Issue("INVALID_TYPE", "`auto_place` must be a boolean.", "$.layout.auto_place"))
        auto_place = False
    layout = ResistorLayout(
        mode=layout_obj.get("mode", "auto_grid" if strategy == "beautify" else "manual_component_positions"),
        coordinate_units=layout_obj.get("coordinate_units", "proteus_internal"),
        component_positions=positions,
        visual_wires=tuple(visual_wires),
        auto_place=auto_place,
    )
    metadata = root.get("metadata", {})
    if not isinstance(metadata, dict):
        issues.append(Issue("INVALID_TYPE", "`metadata` must be an object.", "$.metadata"))
        metadata = {}

    if issues:
        return None, issues
    return (
        ResistorCircuitIR(
            schema_version=schema_version,
            generator_target=generator_target,
            project=project,
            nodes=tuple(nodes),
            components=tuple(components),
            layout=layout,
            metadata=metadata,
        ),
        [],
    )


def validate_resistor_circuit(ir: ResistorCircuitIR) -> ResistorValidationReport:
    errors: list[Issue] = []
    warnings: list[Issue] = []

    if ir.schema_version != SCHEMA_VERSION:
        errors.append(Issue("UNSUPPORTED_SCHEMA_VERSION", f"Use `{SCHEMA_VERSION}`.", "$.schema_version"))
    if ir.generator_target != GENERATOR_TARGET:
        errors.append(Issue("UNSUPPORTED_GENERATOR_TARGET", f"Use `{GENERATOR_TARGET}`.", "$.generator_target"))
    if ir.project.base != BASE_PROJECT:
        errors.append(Issue("UNSUPPORTED_BASE_PROJECT", f"Use `{BASE_PROJECT}`.", "$.project.base"))
    if ir.project.units != "proteus_internal":
        errors.append(Issue("UNSUPPORTED_UNITS", "Only `proteus_internal` coordinates are supported.", "$.project.units"))
    if not ir.project.output_basename or any(ch in ir.project.output_basename for ch in "\\/:*?\"<>|"):
        errors.append(Issue("INVALID_OUTPUT_BASENAME", "Output basename must be a filename, not a path.", "$.project.output_basename"))

    node_ids = [node.id for node in ir.nodes]
    node_set = set(node_ids)
    if not node_ids:
        errors.append(Issue("MISSING_NODES", "At least one node is required.", "$.nodes"))
    if len(node_set) != len(node_ids):
        errors.append(Issue("DUPLICATE_NODE_ID", "Node ids must be unique.", "$.nodes"))
    for index, node in enumerate(ir.nodes):
        path = f"$.nodes[{index}]"
        if not NODE_ID_RE.match(node.id):
            errors.append(Issue("INVALID_NODE_ID", "Node ids must be exactly two ASCII characters in v0.1.", f"{path}.id"))
        if node.kind not in NODE_KINDS:
            errors.append(Issue("INVALID_NODE_KIND", f"Unsupported node kind `{node.kind}`.", f"{path}.kind"))

    refs = [component.ref for component in ir.components]
    if not refs:
        errors.append(Issue("MISSING_COMPONENTS", "At least one resistor component is required.", "$.components"))
    if len(set(refs)) != len(refs):
        errors.append(Issue("DUPLICATE_COMPONENT_REF", "Component refs must be unique.", "$.components"))
    for index, component in enumerate(ir.components):
        path = f"$.components[{index}]"
        if not REF_RE.match(component.ref):
            errors.append(Issue("INVALID_COMPONENT_REF", "Component refs must be exactly two ASCII characters in v0.1.", f"{path}.ref"))
        if component.type != "RESISTOR":
            errors.append(Issue("UNSUPPORTED_COMPONENT_TYPE", "Only `RESISTOR` is supported.", f"{path}.type"))
        if not VALUE_RE.match(component.value):
            errors.append(Issue("INVALID_RESISTOR_VALUE", "Use compact resistor values such as `1k` or `10k`.", f"{path}.value"))
        else:
            try:
                visible_resistor_value(component.value, component.visual)
            except ValueError as exc:
                errors.append(Issue("UNSUPPORTED_VISIBLE_VALUE", str(exc), f"{path}.value"))
        try:
            resistor_orientation_angle(component.visual)
        except ValueError as exc:
            errors.append(Issue("UNSUPPORTED_ORIENTATION_HINT", str(exc), f"{path}.visual.orientation_hint"))
        for endpoint_index, node_id in enumerate(component.nodes):
            if node_id not in node_set:
                errors.append(
                    Issue(
                        "UNKNOWN_ENDPOINT_NODE",
                        f"Endpoint references undeclared node `{node_id}`.",
                        f"{path}.nodes[{endpoint_index}]",
                    )
                )

    if ir.layout.mode not in LAYOUT_MODES:
        errors.append(Issue("UNSUPPORTED_LAYOUT_MODE", "Use `manual_component_positions`, `branch_grid`, or `auto_grid`.", "$.layout.mode"))
    if ir.layout.coordinate_units != "proteus_internal":
        errors.append(Issue("UNSUPPORTED_COORDINATE_UNITS", "Only `proteus_internal` coordinates are supported.", "$.layout.coordinate_units"))
    if not ir.layout.auto_place:
        for component in ir.components:
            if component.ref not in ir.layout.component_positions:
                errors.append(
                    Issue(
                        "MISSING_COMPONENT_POSITION",
                        f"Missing position for `{component.ref}`.",
                        f"$.layout.component_positions.{component.ref}",
                        "Provide a manual position or set `layout.auto_place` to true.",
                    )
                )
    else:
        missing = [component.ref for component in ir.components if component.ref not in ir.layout.component_positions]
        if missing:
            warnings.append(
                Issue(
                    "AUTO_PLACEMENT_USED",
                    f"Auto-placement will assign positions for: {', '.join(missing)}.",
                    "$.layout.auto_place",
                )
            )

    power_nodes = {node.id for node in ir.nodes if node.kind == "power" or node.id == "V0"}
    ground_nodes = {node.id for node in ir.nodes if node.kind == "ground" or node.id == "G0"}
    for index, component in enumerate(ir.components):
        left, right = component.nodes
        if left in ground_nodes:
            errors.append(
                Issue(
                    "GROUND_LEFT_ENDPOINT_UNSUPPORTED",
                    "The locked ground method only supports ground on `nodes[1]` / right endpoints.",
                    f"$.components[{index}].nodes[0]",
                )
            )
        if right in power_nodes:
            errors.append(
                Issue(
                    "POWER_RIGHT_ENDPOINT_UNSUPPORTED",
                    "The locked power bridge method only supports powered resistor nodes on `nodes[0]` / left endpoints.",
                    f"$.components[{index}].nodes[1]",
                )
            )

    return ResistorValidationReport(errors=tuple(errors), warnings=tuple(warnings), circuit=ir)


def validate_resistor_payload(payload: Any) -> ResistorValidationReport:
    ir, issues = parse_resistor_ir(payload)
    if issues:
        return ResistorValidationReport(errors=tuple(issues), warnings=(), circuit=None)
    assert ir is not None
    return validate_resistor_circuit(ir)
