"""Value-stage validation independent from native source-record writing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .ir import AltiumCircuit


VALUE_VALIDATION_SCHEMA = "progen-altium-value-validation/v1"
_UNSAFE_TEXT = re.compile(r"[|\r\n\x00]")


@dataclass(frozen=True)
class ValueValidationReport:
    passed: bool
    component_count: int
    errors: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = VALUE_VALIDATION_SCHEMA
        return result


def validate_component_values(circuit: AltiumCircuit) -> ValueValidationReport:
    errors: list[str] = []
    for component in circuit.components:
        if not component.value.strip():
            errors.append(f"{component.reference} has an empty value")
        if _UNSAFE_TEXT.search(component.value):
            errors.append(f"{component.reference} value contains a native record delimiter")
    return ValueValidationReport(
        passed=not errors,
        component_count=len(circuit.components),
        errors=tuple(errors),
    )
