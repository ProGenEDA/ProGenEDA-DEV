"""Deterministic safe value editing for the direct Altium pipeline."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Mapping

from .ir import AltiumCircuit
from .pipeline_contracts import PipelineError


VALUE_EDITOR_SCHEMA = "progen-altium-value-editor/v1"
_UNSAFE_TEXT = re.compile(r"[|\r\n\x00]")


class ValueEditError(PipelineError):
    """A requested value cannot be written to a source-native property record."""


@dataclass(frozen=True)
class ValueEditResult:
    circuit: AltiumCircuit
    edits: tuple[dict[str, str], ...]

    def json(self) -> dict[str, Any]:
        return {
            "schema": VALUE_EDITOR_SCHEMA,
            "edits": list(self.edits),
            "components": [
                {"reference": component.reference, "value": component.value}
                for component in self.circuit.components
            ],
        }


def _clean_value(value: object, reference: str) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise ValueEditError(f"{reference} has an empty component value.")
    if _UNSAFE_TEXT.search(text):
        raise ValueEditError(f"{reference} value contains a native record delimiter.")
    return text


def apply_value_edits(
    circuit: AltiumCircuit,
    edits: Mapping[str, object] | None = None,
) -> ValueEditResult:
    """Normalize values and apply an explicit reference-to-value edit map.

    The stage intentionally edits only values.  It cannot change references,
    pin maps, native templates, or connectivity.
    """

    requested = dict(edits or {})
    known = {component.reference for component in circuit.components}
    unknown = sorted(set(requested) - known)
    if unknown:
        raise ValueEditError(f"Value edits reference unknown components: {unknown}")
    changed: list[dict[str, str]] = []
    components = []
    for component in circuit.components:
        original = component.value
        value = _clean_value(requested.get(component.reference, original), component.reference)
        if value != original:
            changed.append({"reference": component.reference, "from": original, "to": value})
        components.append(replace(component, value=value))
    return ValueEditResult(
        circuit=replace(circuit, components=tuple(components)),
        edits=tuple(changed),
    )
