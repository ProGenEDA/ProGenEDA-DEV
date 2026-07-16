"""Deterministic EasyEDA value and reference editing."""

from __future__ import annotations

from dataclasses import replace
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from .catalogue import get_entry
from .ir import Circuit, CircuitComponent, CircuitInputError, load_circuit


VALUE_EDITOR_SCHEMA = "progen-easyeda-value-editor/v1"
REFERENCE = re.compile(r"[A-Za-z#][A-Za-z0-9_#-]*\Z")
SAFE_TEXT = re.compile(r"^[A-Za-z0-9_+\-.,=(){}*/: %Ωµμ]+$")
NUMBER = re.compile(
    r"^(?P<number>[+]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)"
    r"(?P<scale>meg|[TGMKkmunpfF])?(?P<unit>[A-Za-zΩ]*)$"
)
SCALE = {
    "": 1.0,
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
}


class ValueEditorError(ValueError):
    """An edit would make the canonical circuit ambiguous or unsafe."""


def validate_reference(value: object) -> str:
    reference = str(value or "").strip()
    if not REFERENCE.fullmatch(reference):
        raise ValueEditorError(
            "References must start with a letter or # and contain only letters, digits, _, #, or -."
        )
    return reference


def _safe_text(value: object, *, field: str) -> str:
    text = str(value or "").strip()
    if (
        not text
        or len(text) > 160
        or "\n" in text
        or "\r" in text
        or ";" in text
        or not SAFE_TEXT.fullmatch(text)
    ):
        raise ValueEditorError(f"{field} contains unsupported display text.")
    return text


def _positive_number(value: object, *, field: str) -> str:
    normalized = (
        str(value or "")
        .strip()
        .replace("µ", "u")
        .replace("μ", "u")
        .replace("Ω", "ohm")
    )
    match = NUMBER.fullmatch(normalized)
    if not match:
        raise ValueEditorError(
            f"{field} must be a positive value such as 10k, 100n, 47uF, or 500mA."
        )
    scale = match.group("scale") or ""
    factor = SCALE.get(scale.lower())
    if factor is None:
        raise ValueEditorError(f"{field} has unsupported scale {scale!r}.")
    numeric = float(match.group("number")) * factor
    if not math.isfinite(numeric) or numeric <= 0:
        raise ValueEditorError(f"{field} must be greater than zero.")
    unit = match.group("unit") or ""
    if unit.lower() not in {"", "a", "v", "f", "h", "ohm", "r", "hz"}:
        raise ValueEditorError(f"{field} has unsupported unit suffix {unit!r}.")
    canonical_scale = "meg" if scale.lower() == "meg" else scale
    canonical_unit = "ohm" if unit.lower() in {"ohm", "r"} else unit
    return f"{match.group('number')}{canonical_scale}{canonical_unit}"


def normalize_value(kind: str, value: object) -> str:
    entry = get_entry(kind)
    raw = entry.default_value if value is None or not str(value).strip() else value
    if entry.value_rule == "positive_number":
        return _positive_number(raw, field=f"{entry.kind}.value")
    if entry.value_rule == "fixed_terminal":
        text = _safe_text(raw, field=f"{entry.kind}.value")
        if entry.kind == "GND" and text.upper() not in {"GND", "GROUND", "0"}:
            raise ValueEditorError("GND value is fixed to the ground net.")
        return entry.default_value if entry.kind == "GND" else text
    return _safe_text(raw, field=f"{entry.kind}.value")


def normalize_circuit_values(circuit: Circuit) -> tuple[Circuit, dict[str, Any]]:
    changes: list[dict[str, str]] = []
    components: list[CircuitComponent] = []
    for component in circuit.components:
        value = normalize_value(component.kind, component.value)
        if value != component.value:
            changes.append(
                {
                    "reference": component.reference,
                    "field": "value",
                    "before": component.value,
                    "after": value,
                }
            )
        components.append(replace(component, value=value))
    normalized = replace(circuit, components=tuple(components))
    return normalized, {
        "schema": VALUE_EDITOR_SCHEMA,
        "passed": True,
        "changes": changes,
        "editable_components": editable_component_index(normalized),
    }


def editable_component_index(circuit: Circuit) -> list[dict[str, Any]]:
    return [
        {
            "id": component.identifier,
            "reference": component.reference,
            "kind": component.kind,
            "value": component.value,
            "editable": ["value", "reference"],
            "value_rule": get_entry(component.kind).value_rule,
            "donor_identity_locked": True,
        }
        for component in circuit.components
    ]


def apply_value_edits(
    input_value: Path | str | Mapping[str, Any],
    edits: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    circuit = load_circuit(input_value)
    raw_edits = edits.get("components", edits)
    if not isinstance(raw_edits, Mapping):
        raise ValueEditorError(
            "Value edits must be an object keyed by component id or reference."
        )
    by_key = {
        key: component
        for component in circuit.components
        for key in (component.identifier, component.reference)
    }
    requested: dict[str, Mapping[str, Any]] = {}
    for key, value in raw_edits.items():
        if key not in by_key:
            raise ValueEditorError(f"Edit target {key!r} is not present in the circuit.")
        if not isinstance(value, Mapping):
            raise ValueEditorError(f"Edit target {key!r} must contain an object.")
        requested[by_key[key].identifier] = value

    references = {component.reference for component in circuit.components}
    replacements: dict[str, str] = {}
    output_components: list[CircuitComponent] = []
    audit: list[dict[str, str]] = []
    for component in circuit.components:
        edit = requested.get(component.identifier, {})
        unknown = set(edit) - {"value", "reference", "ref"}
        if unknown:
            raise ValueEditorError(
                f"Unsupported edit fields for {component.reference}: {sorted(unknown)}"
            )
        value = normalize_value(component.kind, edit.get("value", component.value))
        reference = validate_reference(
            edit.get("reference", edit.get("ref", component.reference))
        )
        if reference != component.reference:
            if reference in references:
                raise ValueEditorError(f"Reference {reference!r} already exists.")
            references.remove(component.reference)
            references.add(reference)
            replacements[component.reference] = reference
            audit.append(
                {
                    "component": component.identifier,
                    "field": "reference",
                    "before": component.reference,
                    "after": reference,
                }
            )
        if value != component.value:
            audit.append(
                {
                    "component": component.identifier,
                    "field": "value",
                    "before": component.value,
                    "after": value,
                }
            )
        output_components.append(replace(component, reference=reference, value=value))

    def rename_endpoint(endpoint: str) -> str:
        reference, separator, pin = endpoint.partition(".")
        if not separator:
            return endpoint
        return f"{replacements.get(reference, reference)}.{pin}"

    nets = {
        name: tuple(sorted(rename_endpoint(endpoint) for endpoint in members))
        for name, members in circuit.nets.items()
    }
    edited = replace(circuit, components=tuple(output_components), nets=nets)
    return edited.normalized_json(), {
        "schema": VALUE_EDITOR_SCHEMA,
        "passed": True,
        "changes": audit,
        "editable_components": editable_component_index(edited),
    }


def load_edits(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CircuitInputError(f"Cannot read value edits {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueEditorError("Value edits must be one JSON object.")
    return value
