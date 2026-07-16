"""CircuitIR parser for the locked mixed resistor/capacitor generator."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .circuit_ir import Issue
from .resistor_ir import ComponentPosition, VisualWire, resistor_orientation_angle, visible_resistor_value

SCHEMA_VERSION = "proteus-mixed-passive-ir/v0.1"
GENERATOR_TARGET = "proteus-8.13-mixed-passive-terminal-power-ground"
BASE_PROJECT = "E001_EMPTY_BASE"

NODE_ID_RE = re.compile(r"^[\x20-\x7e]{2}$")
REF_RE = re.compile(r"^[\x20-\x7e]{2}$")
RESISTOR_VALUE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?[A-Za-z]?$")
CAPACITOR_VALUE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?[A-Za-z]{1,2}$")
NODE_KINDS = {"internal", "power", "ground"}
LAYOUT_MODES = {"manual_component_positions", "branch_grid", "auto_grid"}
COMPONENT_TYPES = {"RESISTOR", "CAPACITOR"}


@dataclass(frozen=True)
class MixedPassiveNode:
    id: str
    role: str | None = None
    kind: str = "internal"


@dataclass(frozen=True)
class MixedPassiveComponent:
    ref: str
    type: str
    value: str
    nodes: tuple[str, str]
    visual: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MixedPassiveLayout:
    mode: str
    coordinate_units: str
    component_positions: dict[str, ComponentPosition]
    visual_wires: tuple[VisualWire, ...] = ()
    auto_place: bool = False


@dataclass(frozen=True)
class MixedPassiveProject:
    name: str
    output_basename: str
    base: str
    units: str


@dataclass(frozen=True)
class MixedPassiveCircuitIR:
    schema_version: str
    generator_target: str
    project: MixedPassiveProject
    nodes: tuple[MixedPassiveNode, ...]
    components: tuple[MixedPassiveComponent, ...]
    layout: MixedPassiveLayout
    metadata: dict[str, Any]


@dataclass(frozen=True)
class MixedPassiveValidationReport:
    errors: tuple[Issue, ...]
    warnings: tuple[Issue, ...] = ()
    circuit: MixedPassiveCircuitIR | None = None

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


def visible_capacitor_value(value: str, visual: dict[str, Any] | None = None) -> str:
    override = (visual or {}).get("visible_value")
    if isinstance(override, str) and len(override.encode("ascii", errors="ignore")) == 3 and override.isascii():
        return override
    if len(value) == 3 and value.isascii():
        return value
    if len(value) > 3 and value[:3].isascii():
        return value[:3]
    raise ValueError(f"Value `{value}` has no validated three-character visible representation.")


def parse_mixed_passive_ir(payload: Any) -> tuple[MixedPassiveCircuitIR | None, list[Issue]]:
    issues: list[Issue] = []
    root = _mapping(payload, "$", issues)
    _unexpected(root, {"schema_version", "generator_target", "project", "nodes", "components", "layout", "metadata"}, "$", issues)

    project_obj = _mapping(root.get("project"), "$.project", issues)
    _unexpected(project_obj, {"name", "output_basename", "base", "units"}, "$.project", issues)
    project = MixedPassiveProject(
        name=_nonempty_string(project_obj, "name", "$.project", issues),
        output_basename=_nonempty_string(project_obj, "output_basename", "$.project", issues),
        base=_nonempty_string(project_obj, "base", "$.project", issues),
        units=_nonempty_string(project_obj, "units", "$.project", issues),
    )

    nodes: list[MixedPassiveNode] = []
    for index, raw in enumerate(_array(root.get("nodes"), "$.nodes", issues)):
        path = f"$.nodes[{index}]"
        item = _mapping(raw, path, issues)
        _unexpected(item, {"id", "role", "kind"}, path, issues)
        kind = item.get("kind", "internal")
        if not isinstance(kind, str):
            issues.append(Issue("INVALID_TYPE", "`kind` must be a string.", f"{path}.kind"))
            kind = "internal"
        nodes.append(
            MixedPassiveNode(
                id=_nonempty_string(item, "id", path, issues),
                role=_optional_string(item, "role", path, issues),
                kind=kind,
            )
        )

    components: list[MixedPassiveComponent] = []
    for index, raw in enumerate(_array(root.get("components"), "$.components", issues)):
        path = f"$.components[{index}]"
        item = _mapping(raw, path, issues)
        _unexpected(item, {"ref", "type", "value", "nodes", "visual"}, path, issues)
        raw_nodes = _array(item.get("nodes"), f"{path}.nodes", issues)
        component_nodes: tuple[str, str] = ("", "")
        if len(raw_nodes) != 2:
            issues.append(Issue("INVALID_ENDPOINT_COUNT", "`nodes` must contain exactly two endpoint node ids.", f"{path}.nodes"))
        elif not isinstance(raw_nodes[0], str) or not isinstance(raw_nodes[1], str):
            issues.append(Issue("INVALID_TYPE", "Endpoint node ids must be strings.", f"{path}.nodes"))
        else:
            component_nodes = (raw_nodes[0], raw_nodes[1])
        visual = item.get("visual", {})
        if not isinstance(visual, dict):
            issues.append(Issue("INVALID_TYPE", "`visual` must be an object.", f"{path}.visual"))
            visual = {}
        components.append(
            MixedPassiveComponent(
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
    positions_raw = _mapping(layout_obj.get("component_positions", {}) or {}, "$.layout.component_positions", issues)
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
    visual_wires_raw = layout_obj.get("visual_wires", []) or []
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
    metadata = root.get("metadata", {})
    if not isinstance(metadata, dict):
        issues.append(Issue("INVALID_TYPE", "`metadata` must be an object.", "$.metadata"))
        metadata = {}

    if issues:
        return None, issues
    return (
        MixedPassiveCircuitIR(
            schema_version=_nonempty_string(root, "schema_version", "$", issues),
            generator_target=_nonempty_string(root, "generator_target", "$", issues),
            project=project,
            nodes=tuple(nodes),
            components=tuple(components),
            layout=MixedPassiveLayout(
                mode=layout_obj.get("mode", "auto_grid" if strategy == "beautify" else "manual_component_positions"),
                coordinate_units=layout_obj.get("coordinate_units", "proteus_internal"),
                component_positions=positions,
                visual_wires=tuple(visual_wires),
                auto_place=auto_place,
            ),
            metadata=metadata,
        ),
        issues,
    )


def validate_mixed_passive_circuit(ir: MixedPassiveCircuitIR) -> MixedPassiveValidationReport:
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
    component_types = {component.type for component in ir.components}
    if not refs:
        errors.append(Issue("MISSING_COMPONENTS", "At least one passive component is required.", "$.components"))
    if len(set(refs)) != len(refs):
        errors.append(Issue("DUPLICATE_COMPONENT_REF", "Component refs must be unique.", "$.components"))
    if not {"RESISTOR", "CAPACITOR"}.issubset(component_types):
        errors.append(Issue("MIXED_COMPONENTS_REQUIRED", "Mixed passive generation requires at least one RESISTOR and one CAPACITOR.", "$.components"))

    power_nodes = {node.id for node in ir.nodes if node.kind == "power" or node.id == "V0"}
    ground_nodes = {node.id for node in ir.nodes if node.kind == "ground" or node.id == "G0"}
    for index, component in enumerate(ir.components):
        path = f"$.components[{index}]"
        if not REF_RE.match(component.ref):
            errors.append(Issue("INVALID_COMPONENT_REF", "Component refs must be exactly two ASCII characters in v0.1.", f"{path}.ref"))
        if component.type not in COMPONENT_TYPES:
            errors.append(Issue("UNSUPPORTED_COMPONENT_TYPE", "Use RESISTOR or CAPACITOR.", f"{path}.type"))
        elif component.type == "RESISTOR":
            if not RESISTOR_VALUE_RE.match(component.value):
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
        elif component.type == "CAPACITOR":
            if not CAPACITOR_VALUE_RE.match(component.value):
                errors.append(Issue("INVALID_CAPACITOR_VALUE", "Use compact capacitor values such as `1uF`.", f"{path}.value"))
            else:
                try:
                    visible_capacitor_value(component.value, component.visual)
                except ValueError as exc:
                    errors.append(Issue("UNSUPPORTED_VISIBLE_VALUE", str(exc), f"{path}.value"))
        for endpoint_index, node_id in enumerate(component.nodes):
            if node_id not in node_set:
                errors.append(Issue("UNKNOWN_ENDPOINT_NODE", f"Endpoint references undeclared node `{node_id}`.", f"{path}.nodes[{endpoint_index}]"))
        left, right = component.nodes
        if left in ground_nodes:
            errors.append(Issue("GROUND_LEFT_ENDPOINT_UNSUPPORTED", "The locked ground method only supports ground on `nodes[1]` / right endpoints.", f"{path}.nodes[0]"))
        if right in power_nodes:
            errors.append(Issue("POWER_RIGHT_ENDPOINT_UNSUPPORTED", "The locked power bridge method only supports powered nodes on `nodes[0]` / left endpoints.", f"{path}.nodes[1]"))

    if ir.layout.mode not in LAYOUT_MODES:
        errors.append(Issue("UNSUPPORTED_LAYOUT_MODE", "Use `manual_component_positions`, `branch_grid`, or `auto_grid`.", "$.layout.mode"))
    if ir.layout.coordinate_units != "proteus_internal":
        errors.append(Issue("UNSUPPORTED_COORDINATE_UNITS", "Only `proteus_internal` coordinates are supported.", "$.layout.coordinate_units"))
    if ir.layout.visual_wires:
        warnings.append(Issue("VISUAL_WIRES_SKIPPED", "Standalone visual wires are parsed but not emitted in the locked mixed passive generator.", "$.layout.visual_wires"))
    if not ir.layout.auto_place:
        for component in ir.components:
            if component.ref not in ir.layout.component_positions:
                errors.append(Issue("MISSING_COMPONENT_POSITION", f"Missing position for `{component.ref}`.", f"$.layout.component_positions.{component.ref}"))
    else:
        missing = [component.ref for component in ir.components if component.ref not in ir.layout.component_positions]
        if missing:
            warnings.append(Issue("AUTO_PLACEMENT_USED", f"Auto-placement will assign positions for: {', '.join(missing)}.", "$.layout.auto_place"))

    return MixedPassiveValidationReport(errors=tuple(errors), warnings=tuple(warnings), circuit=ir)


def validate_mixed_passive_payload(payload: Any) -> MixedPassiveValidationReport:
    ir, issues = parse_mixed_passive_ir(payload)
    if issues:
        return MixedPassiveValidationReport(errors=tuple(issues), warnings=(), circuit=None)
    assert ir is not None
    return validate_mixed_passive_circuit(ir)
