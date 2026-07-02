"""Semantic and generation-readiness validation for CircuitIR."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .circuit_ir import CircuitIR, Issue, parse_circuit_ir
from .component_catalog import load_component_catalog

REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
LABEL_RE = re.compile(r"^[A-Za-z0-9_+./-]+$")
VALUE_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)?(?:[kKmM])?$")
_VALIDATION_COMPONENT_PARTS = ("RESISTOR", "74HC08", "LOGICSTATE", "LOGICPROBE")
_CATALOG = load_component_catalog()
COMPONENT_PINS = _CATALOG.pin_vocabulary(_VALIDATION_COMPONENT_PARTS)
_HC08_PROFILE = _CATALOG.profile("74HC08")
HC08_INPUT_PINS = set(
    _HC08_PROFILE.role_pins(("IN", "IN1", "IN2"))
)
HC08_OUTPUT_PINS = set(_HC08_PROFILE.role_pins(("OUT",)))
NET_KINDS = {"power", "ground", "input", "output", "internal"}
TERMINAL_KINDS = {"input", "output", "power", "ground", "default"}
SUPPORTED_IR_VERSION = "0.2"


def is_and_reference_circuit(ir: CircuitIR) -> bool:
    return (
        ir.version == SUPPORTED_IR_VERSION
        and ir.target.proteus_version == "8.13"
        and ir.target.style == "terminal_based"
        and ir.target.sheet_count == 1
        and ir.target.mode == "production"
        and {
            (component.ref, component.part, component.value)
            for component in ir.circuit.components
        }
        == {("U1", "74HC08", None), ("R1", "RESISTOR", "10k"), ("R2", "RESISTOR", "10k")}
        and {
            (net.name, net.kind) for net in ir.circuit.nets
        }
        == {
            ("VCC", "power"),
            ("GND", "ground"),
            ("ODD_PULLUP", "internal"),
            ("EVEN_PULLDOWN", "internal"),
            ("Y_A", "output"),
            ("Y_B", "output"),
            ("Y_C", "output"),
            ("Y_D", "output"),
        }
        and {
            (connection.component, connection.pin, connection.net)
            for connection in ir.circuit.connections
        }
        == {
            ("R1", "1", "VCC"),
            ("R1", "2", "ODD_PULLUP"),
            ("R2", "1", "EVEN_PULLDOWN"),
            ("R2", "2", "GND"),
            ("U1", "1", "ODD_PULLUP"),
            ("U1", "2", "EVEN_PULLDOWN"),
            ("U1", "3", "Y_A"),
            ("U1", "4", "ODD_PULLUP"),
            ("U1", "5", "EVEN_PULLDOWN"),
            ("U1", "6", "Y_B"),
            ("U1", "8", "Y_C"),
            ("U1", "9", "ODD_PULLUP"),
            ("U1", "10", "EVEN_PULLDOWN"),
            ("U1", "11", "Y_D"),
            ("U1", "12", "ODD_PULLUP"),
            ("U1", "13", "EVEN_PULLDOWN"),
        }
        and {
            (terminal.label, terminal.net, terminal.kind, terminal.at.x, terminal.at.y)
            for terminal in ir.circuit.layout.terminals
        }
        == {
            ("1", "ODD_PULLUP", "input", 8, 2),
            ("2", "EVEN_PULLDOWN", "input", 8, 3),
            ("3", "ODD_PULLUP", "input", 8, 6),
            ("4", "EVEN_PULLDOWN", "input", 8, 7),
            ("5", "ODD_PULLUP", "input", 8, 10),
            ("6", "EVEN_PULLDOWN", "input", 8, 11),
            ("7", "ODD_PULLUP", "input", 8, 14),
            ("8", "EVEN_PULLDOWN", "input", 8, 15),
        }
        and {
            (wire.net, tuple((point.x, point.y) for point in wire.points))
            for wire in ir.circuit.layout.wires
        }
        == {
            ("ODD_PULLUP", ((2, 4), (4, 4), (4, 14))),
            ("EVEN_PULLDOWN", ((2, 16), (4, 16), (4, 6))),
        }
        and {
            (junction.net, junction.at.x, junction.at.y)
            for junction in ir.circuit.layout.junctions
        }
        == {
            ("ODD_PULLUP", 4, 6),
            ("ODD_PULLUP", 4, 10),
            ("EVEN_PULLDOWN", 4, 7),
            ("EVEN_PULLDOWN", 4, 11),
        }
        and (
            ir.circuit.equation is None
            or ir.circuit.equation == "Y = [((A0A1)(A2A3))((A4A5)(A6A7))][((A8A9)(A10A11))((A12A13)(A14A15))]"
        )
    )


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[Issue, ...]
    warnings: tuple[Issue, ...]
    circuit: CircuitIR | None = None

    @property
    def valid(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": [issue.as_dict() for issue in self.errors],
            "warnings": [issue.as_dict() for issue in self.warnings],
        }


def validate_payload(payload: Any, *, require_generation_ready: bool = True) -> ValidationReport:
    circuit, parse_issues = parse_circuit_ir(payload)
    if parse_issues:
        return ValidationReport(errors=tuple(parse_issues), warnings=(), circuit=None)
    assert circuit is not None
    return validate_circuit(circuit, require_generation_ready=require_generation_ready)


def validate_circuit(ir: CircuitIR, *, require_generation_ready: bool = True) -> ValidationReport:
    errors: list[Issue] = []
    warnings: list[Issue] = []
    target = ir.target
    circuit = ir.circuit
    and_reference = is_and_reference_circuit(ir)

    if ir.version != SUPPORTED_IR_VERSION:
        errors.append(Issue("UNSUPPORTED_IR_VERSION", f"Only CircuitIR version `{SUPPORTED_IR_VERSION}` is supported.", "$.version"))
    if target.proteus_version != "8.13":
        errors.append(Issue("UNSUPPORTED_TARGET_VERSION", "Only Proteus 8.13 output is supported in v0.", "$.target.proteus_version"))
    if target.style != "terminal_based":
        errors.append(Issue("UNSUPPORTED_STYLE", "Only `terminal_based` rendering is supported.", "$.target.style"))
    if target.sheet_count != 1:
        errors.append(Issue("MULTISHEET_UNSUPPORTED", "v0 emits single-sheet projects only.", "$.target.sheet_count"))
    if target.mode not in {"production", "diagnostic_control"}:
        errors.append(Issue("INVALID_MODE", "Mode must be `production` or `diagnostic_control`.", "$.target.mode"))

    components = {component.ref: component for component in circuit.components}
    if len(components) != len(circuit.components):
        errors.append(Issue("DUPLICATE_COMPONENT_REF", "Every component reference must be unique.", "$.circuit.components"))
    hc08_refs = [component.ref for component in circuit.components if component.part == "74HC08"]
    if len(hc08_refs) > 1:
        errors.append(Issue("MULTIPLE_74HC08_PACKAGES_UNSUPPORTED", "v0 supports one quad 74HC08 package only.", "$.circuit.components"))

    for index, component in enumerate(circuit.components):
        path = f"$.circuit.components[{index}]"
        if not REF_RE.match(component.ref):
            errors.append(Issue("INVALID_COMPONENT_REF", "Component refs must start with a letter and contain letters, digits, or underscore.", f"{path}.ref"))
        if component.part not in COMPONENT_PINS:
            errors.append(Issue("UNSUPPORTED_COMPONENT", f"Part `{component.part}` is outside the v0 component vocabulary.", f"{path}.part"))
            continue
        if component.part == "RESISTOR":
            if not component.value:
                errors.append(Issue("MISSING_VALUE", "Resistors require a value.", f"{path}.value"))
            elif not VALUE_RE.match(component.value):
                errors.append(Issue("UNTESTED_RESISTOR_VALUE_FORMAT", "Use values such as `1k`, `10k`, `330`, or `4.7k` in v0.", f"{path}.value"))
        if component.part == "74HC08" and component.ref != "U1":
            errors.append(Issue("UNSUPPORTED_74HC08_REFERENCE", "The validated donor exposes the quad package as `U1` only.", f"{path}.ref"))
        if require_generation_ready and target.mode == "production" and component.part in {"74HC08", "LOGICSTATE", "LOGICPROBE"} and not and_reference:
            errors.append(
                Issue(
                    "COMPONENT_NOT_GENERATION_READY",
                    f"`{component.part}` has a clean donor but no accepted composed-output template yet.",
                    f"{path}.part",
                    "Supply and validate the D05 oracle before enabling composed AND output.",
                )
            )

    nets = {net.name: net for net in circuit.nets}
    if len(nets) != len(circuit.nets):
        errors.append(Issue("DUPLICATE_NET", "Every electrical net name must be unique.", "$.circuit.nets"))
    for index, net in enumerate(circuit.nets):
        path = f"$.circuit.nets[{index}]"
        if not LABEL_RE.match(net.name):
            errors.append(Issue("INVALID_NET_NAME", "Net names contain unsupported terminal-label characters.", f"{path}.name"))
        if net.kind not in NET_KINDS:
            errors.append(Issue("INVALID_NET_KIND", f"Unsupported net kind `{net.kind}`.", f"{path}.kind"))
        if net.name == "VCC" and net.kind != "power":
            errors.append(Issue("VCC_KIND_MISMATCH", "`VCC` must be a power net.", f"{path}.kind"))
        if net.name == "GND" and net.kind != "ground":
            errors.append(Issue("GND_KIND_MISMATCH", "`GND` must be a ground net.", f"{path}.kind"))

    occupied: set[tuple[str, str]] = set()
    pins_by_component: dict[str, set[str]] = {ref: set() for ref in components}
    for index, connection in enumerate(circuit.connections):
        path = f"$.circuit.connections[{index}]"
        component = components.get(connection.component)
        if component is None:
            errors.append(Issue("UNKNOWN_COMPONENT", f"Connection references missing component `{connection.component}`.", f"{path}.component"))
            continue
        if connection.net not in nets:
            errors.append(Issue("UNKNOWN_NET", f"Connection references missing net `{connection.net}`.", f"{path}.net"))
        if connection.pin not in COMPONENT_PINS.get(component.part, set()):
            errors.append(Issue("INVALID_PIN", f"Pin `{connection.pin}` is not supported for `{component.part}`.", f"{path}.pin"))
        key = (connection.component, connection.pin)
        if key in occupied:
            errors.append(Issue("DUPLICATE_PIN_CONNECTION", f"`{connection.component}.{connection.pin}` is connected more than once.", path))
        occupied.add(key)
        pins_by_component[connection.component].add(connection.pin)

    for ref in hc08_refs:
        connected = pins_by_component.get(ref, set())
        if target.mode == "production":
            missing_inputs = sorted(HC08_INPUT_PINS - connected, key=int)
            if missing_inputs:
                errors.append(Issue("UNCONNECTED_74HC08_INPUTS", f"`{ref}` inputs are unconnected: {', '.join(missing_inputs)}.", "$.circuit.connections"))
            missing_outputs = sorted(HC08_OUTPUT_PINS - connected, key=int)
            if missing_outputs:
                warnings.append(Issue("UNCONNECTED_74HC08_OUTPUTS", f"`{ref}` outputs are unconnected: {', '.join(missing_outputs)}.", "$.circuit.connections"))

    for index, terminal in enumerate(circuit.layout.terminals):
        path = f"$.circuit.layout.terminals[{index}]"
        if terminal.net not in nets:
            errors.append(Issue("UNKNOWN_LAYOUT_NET", f"Terminal references missing net `{terminal.net}`.", f"{path}.net"))
        if not LABEL_RE.match(terminal.label):
            errors.append(Issue("INVALID_TERMINAL_LABEL", "Terminal labels contain unsupported characters.", f"{path}.label"))
        if terminal.kind not in TERMINAL_KINDS:
            errors.append(Issue("INVALID_TERMINAL_KIND", f"Unsupported terminal kind `{terminal.kind}`.", f"{path}.kind"))
    for index, wire in enumerate(circuit.layout.wires):
        if wire.net not in nets:
            errors.append(Issue("UNKNOWN_LAYOUT_NET", f"Wire references missing net `{wire.net}`.", f"$.circuit.layout.wires[{index}].net"))
        if len(wire.points) < 2:
            errors.append(Issue("INVALID_WIRE", "A wire requires at least two grid points.", f"$.circuit.layout.wires[{index}].points"))
    for index, junction in enumerate(circuit.layout.junctions):
        if junction.net not in nets:
            errors.append(Issue("UNKNOWN_LAYOUT_NET", f"Junction references missing net `{junction.net}`.", f"$.circuit.layout.junctions[{index}].net"))
    for index, placement in enumerate(circuit.layout.placements):
        if placement.component not in components:
            errors.append(Issue("UNKNOWN_PLACEMENT_COMPONENT", f"Placement references missing component `{placement.component}`.", f"$.circuit.layout.placements[{index}].component"))
        if placement.orientation != "horizontal":
            errors.append(Issue("UNSUPPORTED_ORIENTATION", "v0 supports horizontal placement only.", f"$.circuit.layout.placements[{index}].orientation"))

    if require_generation_ready and target.mode == "production" and circuit.layout.has_rendered_geometry and not and_reference:
        errors.append(
            Issue(
                "LAYOUT_RENDERING_UNVALIDATED",
                "Terminal, wire, junction, and free-placement rendering require a clean composed-project oracle.",
                "$.circuit.layout",
                "Provide HC08_D05_exact_picture_manual_control.pdsprj for comparison and renderer validation.",
            )
        )

    return ValidationReport(errors=tuple(errors), warnings=tuple(warnings), circuit=ir)
