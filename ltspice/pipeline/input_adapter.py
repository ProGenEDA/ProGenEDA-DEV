"""Adapter to the shared canonical ProGenEDA JSON fixer.

No LTspice-specific user JSON is accepted here.  A loose input is repaired by
the existing universal KiCad-era fixer, then the LTspice stages consume the
same canonical logical components and nets.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
import re
from typing import Any

from kicad.pipeline.input_json_validator_fixer import load_json_lenient, validate_and_fix_main_json

from .catalogue import normalize_kind
from .directive_validator import directive_report


INPUT_ADAPTER_SCHEMA = "progen-ltspice-input-adapter/v0.1"


def _raw_component_extensions(raw: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Capture backend-owned fields before the shared fixer deliberately trims them.

    The shared fixer owns logical topology and intentionally emits a minimal
    portable CircuitIR.  These optional fields are neither topology nor a new
    user schema: they are a profile-validated LTspice placement/property
    extension that is restored only when a raw reference maps uniquely to the
    canonical reference.
    """

    captured: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    duplicates: set[str] = set()
    for index, component in enumerate(raw.get("components", []), 1):
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or component.get("id") or "").strip()
        if not ref:
            if any(name in component for name in ("parameters", "spice_params", "metadata", "ltspice_at", "ltspice_orientation")):
                warnings.append(f"Component {index} has LTspice-specific fields but no stable ref/id; fields were not restored.")
            continue
        if not re.fullmatch(r"[A-Za-z#][A-Za-z0-9_#-]*", ref):
            if any(name in component for name in ("parameters", "spice_params", "metadata", "ltspice_at", "ltspice_orientation")):
                warnings.append(f"Component {index} has LTspice-specific fields but unsafe ref/id {ref!r}; fields were not restored.")
            continue
        if ref in captured:
            duplicates.add(ref)
            continue
        extension: dict[str, Any] = {}
        # The shared fixer deliberately knows only the cross-backend KiCad
        # catalogue, so several valid LTspice aliases (I, POT, C_ELEC, source
        # spellings, etc.) would otherwise be repaired into a connector or a
        # different primitive. Preserve only an alias that resolves in the
        # LTspice profile catalogue, keyed by a stable safe ref; selector/pin
        # validation still decides whether it can actually be emitted.
        raw_kind = next((component.get(name) for name in ("kind", "type", "name") if component.get(name) is not None), None)
        profile_kind = normalize_kind(raw_kind) if raw_kind is not None else ""
        if profile_kind:
            extension["kind"] = profile_kind
        if "parameters" in component:
            extension["parameters"] = deepcopy(component["parameters"])
        elif "spice_params" in component:
            extension["spice_params"] = deepcopy(component["spice_params"])
        if "metadata" in component:
            extension["metadata"] = deepcopy(component["metadata"])
        for name in ("ltspice_at", "ltspice_orientation"):
            if name in component:
                extension[name] = deepcopy(component[name])
        if extension:
            captured[ref] = extension
    for ref in sorted(duplicates):
        captured.pop(ref, None)
        warnings.append(f"Duplicate raw reference {ref!r} has LTspice-specific fields; fields were not restored after canonical ref repair.")
    return captured, warnings


def _restore_component_extensions(fixed: dict[str, Any], captured: dict[str, dict[str, Any]]) -> tuple[list[str], list[str]]:
    restored: list[str] = []
    unmatched = set(captured)
    components = fixed.get("components")
    if not isinstance(components, list):
        return restored, sorted(unmatched)
    for component in components:
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or component.get("id") or "").strip()
        extension = captured.get(ref)
        if extension is None:
            continue
        component.update(deepcopy(extension))
        restored.extend(f"{ref}.{name}" for name in sorted(extension))
        unmatched.discard(ref)
    return restored, sorted(unmatched)


def canonicalize_source(source: Path, *, routing_mode: str = "combination") -> tuple[dict[str, Any], dict[str, Any], bytes]:
    if source.suffix.lower() != ".json":
        raise ValueError(f"LTspice backend accepts canonical/loose ProGenEDA JSON, not {source.name!r}.")
    original = source.read_bytes()
    raw = load_json_lenient(source)
    if not isinstance(raw, dict):
        raise ValueError("LTspice input JSON must be an object.")
    extensions, extension_warnings = _raw_component_extensions(raw)
    fixed, fixer_report = validate_and_fix_main_json(raw, routing_mode=routing_mode, source=str(source))
    restored_extensions, unmatched_extensions = _restore_component_extensions(fixed, extensions)
    # Analysis directives describe a requested simulator run, not circuit
    # connectivity. The older universal fixer understandably does not retain
    # them, so preserve this backend-neutral optional section verbatim while
    # leaving components/nets under the shared deterministic fixer.
    raw_directives: list[object] = []
    if isinstance(raw.get("spice_directives"), list):
        raw_directives.extend(raw["spice_directives"])
    if isinstance(raw.get("project"), dict) and isinstance(raw["project"].get("analysis"), list):
        raw_directives.extend(raw["project"]["analysis"])
    directives, directives_report = directive_report(raw_directives)
    if directives:
        fixed["spice_directives"] = directives
    report = {
        "schema": INPUT_ADAPTER_SCHEMA,
        "stage": "shared_main_json_canonicalizer",
        "ok": bool(fixer_report.get("ok")),
        "source": str(source),
        "shared_fixer_report": fixer_report,
        "contract": "The unchanged logical circuit JSON is shared with all ProGenEDA backends; backend selection is executable-owned.",
        "ltspice_component_extensions_restored": restored_extensions,
        "ltspice_component_extensions_unmatched": unmatched_extensions,
        "warnings": extension_warnings,
        "analysis_directives": directives_report,
    }
    return fixed, report, original


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
