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

from .catalogue import CatalogueError, normalize_kind, resolve_profile
from .directive_validator import directive_report
from .value_editor import ValueValidationError, validate_component_value


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
            if any(name in component for name in ("parameters", "spice_params", "metadata", "spice_model", "at", "rotation", "ltspice_at", "ltspice_orientation")):
                warnings.append(f"Component {index} has LTspice-specific fields but no stable ref/id; fields were not restored.")
            continue
        if not re.fullmatch(r"[A-Za-z#][A-Za-z0-9_#-]*", ref):
            if any(name in component for name in ("parameters", "spice_params", "metadata", "spice_model", "at", "rotation", "ltspice_at", "ltspice_orientation")):
                warnings.append(f"Component {index} has LTspice-specific fields but unsafe ref/id {ref!r}; fields were not restored.")
            continue
        if ref in captured:
            duplicates.add(ref)
            continue
        extension: dict[str, Any] = {}
        # The shared fixer deliberately knows only the cross-backend KiCad
        # catalogue, so several valid LTspice aliases (I, POT, C_ELEC, source
        # spellings, etc.) would otherwise be repaired into a connector or a
        # different primitive.  Record the resolved backend profile *beside*
        # the portable kind; adapters must not rewrite a user's canonical
        # component identity merely to choose an LTspice implementation.
        raw_kind = next((component.get(name) for name in ("kind", "type", "name") if component.get(name) is not None), None)
        profile_kind = normalize_kind(raw_kind) if raw_kind is not None else ""
        if profile_kind:
            extension["ltspice_profile"] = profile_kind
        for name in ("kind", "type"):
            if name in component:
                extension[name] = deepcopy(component[name])
        if "parameters" in component:
            extension["parameters"] = deepcopy(component["parameters"])
        elif "spice_params" in component:
            extension["spice_params"] = deepcopy(component["spice_params"])
        if "metadata" in component:
            extension["metadata"] = deepcopy(component["metadata"])
        # These are portable placement hints.  The LTspice placer treats
        # generic ``at`` as an ordering hint and only ``ltspice_at`` as native
        # ASC geometry, so preserving both cannot accidentally reinterpret a
        # KiCad coordinate as an LTspice coordinate.
        for name in ("spice_model", "at", "rotation", "ltspice_at", "ltspice_orientation"):
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


def _canonical_expected_netlist_agrees(raw: dict[str, Any]) -> None:
    """Reject contradictory canonical topology instead of merging it away.

    The universal legacy fixer is intentionally helpful for loose JSON, but a
    declared v1 ``nets`` plus ``expected_netlist`` is an invariant: adapters
    must not choose which one is true.  Only enforce this when both sections
    are already explicit endpoint lists; old descriptive loose inputs retain
    the existing repair path.
    """

    raw_nets = raw.get("nets")
    expected = raw.get("expected_netlist")
    if not isinstance(raw_nets, dict) or not isinstance(expected, dict) or not isinstance(expected.get("nets"), list):
        return
    if not all(isinstance(members, list) for members in raw_nets.values()):
        return
    expected_nets: dict[str, list[str]] = {}
    for item in expected["nets"]:
        if not isinstance(item, dict) or not isinstance(item.get("members"), list) or not item.get("name"):
            return
        name = str(item["name"])
        if name in expected_nets:
            raise ValueError(f"Canonical expected_netlist repeats net {name!r}.")
        expected_nets[name] = [str(member) for member in item["members"]]
    actual = {str(name): [str(member) for member in members] for name, members in raw_nets.items()}
    if set(actual) != set(expected_nets):
        raise ValueError("Canonical nets and expected_netlist name sets disagree; refusing to mutate declared topology.")
    for name in sorted(actual):
        if set(actual[name]) != set(expected_nets[name]):
            raise ValueError(f"Canonical net {name!r} disagrees with expected_netlist; refusing to mutate declared topology.")


def _metadata_object(component: dict[str, Any]) -> dict[str, Any]:
    value = component.get("metadata")
    if not isinstance(value, dict):
        value = {}
        component["metadata"] = value
    return value


def _adapt_shared_component_values(fixed: dict[str, Any]) -> list[dict[str, str]]:
    """Normalize only unambiguous KiCad display conventions into LTspice data.

    This is a compatibility overlay on the shared JSON, not a second input
    format.  Every rewrite is reported, limited to a profile we own, and
    leaves ambiguous display prose to the strict selector.
    """

    adaptations: list[dict[str, str]] = []
    components = fixed.get("components")
    if not isinstance(components, list):
        return adaptations
    for component in components:
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or component.get("id") or "")
        try:
            profile = resolve_profile(component.get("ltspice_profile") or component.get("kind") or component.get("type") or "")
        except CatalogueError:
            continue
        raw_value = str(component.get("value") or "").strip()

        # Earlier KiCad fixtures carry the actual source expression separately
        # as spice_model while their display Value is VSIN/VPULSE. Preserve it
        # and let the same strict source validator handle it later.
        legacy_model = str(component.get("spice_model") or "").strip()
        if legacy_model and profile.value_rule == "source_expression":
            component["value"] = legacy_model
            adaptations.append({"ref": ref, "kind": profile.kind, "field": "spice_model", "action": "used_as_source_value"})
            raw_value = legacy_model

        # A KiCad VAC's visible value is its AC magnitude.  LTspice represents
        # that deterministically as a zero DC Value plus Value2 AC magnitude.
        if profile.kind == "VAC" and raw_value:
            ac_match = re.fullmatch(r"AC\s+(.+)", raw_value, flags=re.IGNORECASE)
            magnitude = ac_match.group(1) if ac_match else raw_value
            parameters = component.get("parameters")
            if not isinstance(parameters, dict):
                parameters = {}
                component["parameters"] = parameters
            if "ac" not in {str(key).lower() for key in parameters}:
                parameters["ac"] = magnitude
            component["value"] = "0"
            adaptations.append({"ref": ref, "kind": profile.kind, "field": "value", "action": "moved_ac_magnitude_to_parameters.ac"})
            raw_value = "0"

        # Common KiCad display fields combine an electrical value and a
        # deterministic rating, e.g. "100uF, 25V".  Only split one comma and
        # only retain it if the electrical prefix passes our existing value
        # validator.  This avoids treating arbitrary prose as a simulation
        # property.
        if profile.kind in {"R", "C", "C_ELEC", "L"} and "," in raw_value:
            electrical, rating = (part.strip() for part in raw_value.split(",", 1))
            try:
                normalized = validate_component_value(profile, electrical)
            except ValueValidationError:
                normalized = ""
            if normalized and rating:
                component["value"] = normalized
                metadata = _metadata_object(component)
                metadata_name = {
                    "R": "power_rating",
                    "C": "voltage_rating",
                    "C_ELEC": "voltage_rating",
                    "L": "current_rating",
                }[profile.kind]
                metadata.setdefault(metadata_name, rating)
                adaptations.append({"ref": ref, "kind": profile.kind, "field": "value", "action": f"split_display_value_to_{metadata_name}"})
                raw_value = normalized

        # The portable KiCad component value is sometimes a descriptive LED
        # label.  The selected generic LED model remains explicit; a standard
        # colour word is retained as design metadata rather than being
        # misrepresented as an electrical model parameter.
        if profile.kind == "LED":
            try:
                validate_component_value(profile, raw_value)
            except ValueValidationError:
                metadata = _metadata_object(component)
                colour = next(
                    (name for name in ("red", "green", "blue", "yellow", "white", "amber", "orange") if re.search(rf"\b{name}\b", raw_value, flags=re.IGNORECASE)),
                    None,
                )
                if colour:
                    metadata.setdefault("color", colour)
                component["value"] = profile.default_value
                adaptations.append({"ref": ref, "kind": profile.kind, "field": "value", "action": "replaced_display_label_with_generic_led_model"})

        # KiCad labels commonly expand a locked named model ("LM7805 Voltage
        # Regulator").  It is safe to normalize only when that text begins
        # with the selected profile's public kind/alias; unrelated model names
        # still fail rather than silently substituting a device.
        if profile.value_rule == "model_name":
            model_tokens = [profile.kind, *profile.aliases]
            upper_value = raw_value.upper()
            if any(upper_value.startswith(token.upper()) for token in model_tokens):
                try:
                    validate_component_value(profile, raw_value)
                except ValueValidationError:
                    component["value"] = profile.default_value
                    adaptations.append({"ref": ref, "kind": profile.kind, "field": "value", "action": "normalized_profile_display_label"})
    return adaptations


def _restore_portable_sections(fixed: dict[str, Any], raw: dict[str, Any]) -> list[str]:
    """Retain backend-neutral contract metadata through the legacy fixer."""

    restored: list[str] = []
    for name in ("main_json_contract", "compiler", "layout_intent", "stage_contracts", "generation_variation"):
        if name in raw:
            fixed[name] = deepcopy(raw[name])
            restored.append(name)
    raw_project = raw.get("project")
    if isinstance(raw_project, dict):
        project = fixed.setdefault("project", {})
        if isinstance(project, dict):
            for name, value in raw_project.items():
                if name not in {"analysis"}:
                    project[name] = deepcopy(value)
            restored.append("project.metadata")
    return restored


def canonicalize_source(source: Path, *, routing_mode: str | None = None) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    if source.suffix.lower() != ".json":
        raise ValueError(f"LTspice backend accepts canonical/loose ProGenEDA JSON, not {source.name!r}.")
    original = source.read_bytes()
    raw = load_json_lenient(source)
    if not isinstance(raw, dict):
        raise ValueError("LTspice input JSON must be an object.")
    _canonical_expected_netlist_agrees(raw)
    extensions, extension_warnings = _raw_component_extensions(raw)
    fixed, fixer_report = validate_and_fix_main_json(raw, routing_mode=routing_mode, source=str(source))
    restored_extensions, unmatched_extensions = _restore_component_extensions(fixed, extensions)
    restored_portable_sections = _restore_portable_sections(fixed, raw)
    value_adaptations = _adapt_shared_component_values(fixed)
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
        "portable_sections_restored": restored_portable_sections,
        "canonical_value_adaptations": value_adaptations,
        "warnings": extension_warnings,
        "analysis_directives": directives_report,
    }
    return fixed, report, original


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
