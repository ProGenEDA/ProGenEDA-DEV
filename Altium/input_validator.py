"""Input-stage validation after repair and native source resolution."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .pipeline_contracts import ComponentSelection


INPUT_VALIDATION_SCHEMA = "progen-altium-input-validation/v1"


@dataclass(frozen=True)
class InputValidationReport:
    passed: bool
    component_count: int
    net_count: int
    guessed_terminal_nets: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = INPUT_VALIDATION_SCHEMA
        return result


def validate_resolved_input(selection: ComponentSelection) -> InputValidationReport:
    """Verify that canonical intent and resolved native pins still agree."""

    errors: list[str] = []
    warnings: list[str] = []
    references = [item.component.reference for item in selection.components]
    identifiers = [item.component.identifier for item in selection.components]
    if len(set(references)) != len(references):
        errors.append("resolved component references are not unique")
    if len(set(identifiers)) != len(identifiers):
        errors.append("resolved component IDs are not unique")

    expected_endpoints: set[str] = set()
    for item in selection.components:
        if set(item.pin_nets) != set(item.template.pins):
            errors.append(f"{item.component.reference} does not account for every source pin")
        for pin, net in item.pin_nets.items():
            endpoint = f"{item.component.reference}.{pin}"
            expected_endpoints.add(endpoint)
            if not net:
                errors.append(f"{endpoint} has an empty net name")
    actual_endpoints = {
        endpoint
        for members in selection.nets.values()
        for endpoint in members
    }
    if expected_endpoints != actual_endpoints:
        errors.append("resolved source-pin netlist does not cover exactly the selected component pins")

    for net in selection.guessed_terminal_nets:
        members = selection.nets.get(net, ())
        if len(members) != 1:
            errors.append(f"guessed terminal net {net!r} must have exactly one endpoint")
        else:
            warnings.append(f"{net} was added by the input fixer and must use a native terminal")

    return InputValidationReport(
        passed=not errors,
        component_count=len(selection.components),
        net_count=len(selection.nets),
        guessed_terminal_nets=selection.guessed_terminal_nets,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )
