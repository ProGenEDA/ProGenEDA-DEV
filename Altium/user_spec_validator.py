"""Validate that resolved native facts preserve the user's canonical circuit intent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .pipeline_contracts import ComponentSelection


USER_SPEC_VALIDATION_SCHEMA = "progen-altium-user-spec-validation/v1"


@dataclass(frozen=True)
class UserSpecificationReport:
    passed: bool
    component_count: int
    requested_pin_count: int
    errors: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = USER_SPEC_VALIDATION_SCHEMA
        return result


def validate_user_specification(selection: ComponentSelection) -> UserSpecificationReport:
    """Ensure source resolution changed spelling, never user connectivity or values."""

    errors: list[str] = []
    requested_pins = 0
    selected_by_reference = selection.by_reference()
    for component in selection.circuit.components:
        resolved = selected_by_reference.get(component.reference)
        if resolved is None:
            errors.append(f"requested component {component.reference} was not selected")
            continue
        if resolved.component.identifier != component.identifier:
            errors.append(f"{component.reference} changed its requested component ID")
        if resolved.component.value != component.value:
            errors.append(f"{component.reference} changed its requested component value")
        for logical_pin, net in component.pins.items():
            requested_pins += 1
            native_pin = resolved.logical_pin_map.get(logical_pin)
            if native_pin is None:
                errors.append(f"{component.reference}.{logical_pin} has no resolved native pin")
                continue
            if resolved.pin_nets.get(native_pin) != net:
                errors.append(
                    f"{component.reference}.{logical_pin} changed requested net {net!r} during source resolution"
                )
    return UserSpecificationReport(
        passed=not errors,
        component_count=len(selection.circuit.components),
        requested_pin_count=requested_pins,
        errors=tuple(errors),
    )
