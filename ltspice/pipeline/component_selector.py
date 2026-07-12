"""Select source-backed LTspice profiles for canonical circuit components."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .catalogue import CatalogueError, ComponentProfile, model_for, normalize_kind, resolve_profile
from .value_editor import ValueValidationError, validate_component_value, validate_metadata, validate_parameters


SELECTION_SCHEMA = "progen-ltspice-component-selection/v0.1"


@dataclass(frozen=True)
class SelectedComponent:
    ref: str
    kind: str
    value: str
    pins: dict[str, str]
    parameters: dict[str, str]
    metadata: dict[str, str]
    profile: ComponentProfile
    canonical_to_native: dict[str, str]

    @property
    def native_netlist_name(self) -> str:
        """Evidence-only identity after LTspice applies a locked Prefix.

        LTspice allows a free InstName (donors demonstrate this), while the
        symbol Prefix still governs primitive netlisting.  A section sign
        makes a non-prefix display name unambiguous in our internal evidence;
        it is not written into the ASC InstName field.
        """

        prefix = self.profile.electrical_prefix
        if not prefix or self.ref.upper().startswith(prefix.upper()):
            return self.ref
        return f"{prefix}\u00a7{self.ref}"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "kind": self.kind,
            "value": self.value,
            "pins": dict(self.pins),
            "parameters": dict(self.parameters),
            "metadata": dict(self.metadata),
            "canonical_to_native_pin": dict(self.canonical_to_native),
            "native_netlist_name": self.native_netlist_name,
            "profile": self.profile.as_dict(),
            "model": model_for(self.profile),
        }


def _component_ref(item: dict[str, Any], index: int) -> str:
    ref = str(item.get("ref") or item.get("id") or "").strip()
    if not ref:
        raise CatalogueError(f"Component {index} has no ref/id.")
    if not re.fullmatch(r"[A-Za-z#][A-Za-z0-9_#-]*", ref):
        raise CatalogueError(f"Component {ref!r} has an unsafe reference designator.")
    return ref


def _component_kind(item: dict[str, Any], ref: str) -> str:
    for key in ("kind", "type", "name"):
        if item.get(key):
            return str(item[key])
    raise CatalogueError(f"{ref} has no component kind/type.")


def _profile_for_raw_component(item: dict[str, Any], ref: str) -> ComponentProfile:
    """Resolve explicit kind first, then a safe model-specific profile hint."""

    raw_kind = _component_kind(item, ref)
    profile = resolve_profile(raw_kind)
    # A canonical circuit often represents a diode as kind D plus value
    # 1N4148. That is still the same backend-neutral input; select the more
    # specific backend model profile when such a profile is explicitly known.
    if profile.kind in {"D", "NMOS", "PMOS", "OPAMP"}:
        hinted = normalize_kind(item.get("value") or "")
        if hinted:
            candidate = resolve_profile(hinted)
            if candidate.reference_prefix == profile.reference_prefix:
                return candidate
    return profile


def _string_map(value: Any, *, field: str, ref: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CatalogueError(f"{ref}.{field} must be an object when supplied.")
    return {str(key).lower(): str(item).strip() for key, item in value.items() if str(item).strip()}


def select_components(circuit: dict[str, Any]) -> tuple[list[SelectedComponent], dict[str, Any]]:
    """Resolve all components against the backend profile catalogue.

    This stage deliberately fails before writing if a kind, pin, reference, or
    safe normal-mode parameter is not supported.  It does not substitute a
    visually similar but electrically unrelated component.
    """

    raw_components = circuit.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        raise CatalogueError("Canonical main JSON must contain a non-empty components array.")
    selected: list[SelectedComponent] = []
    errors: list[str] = []
    warnings: list[str] = []
    seen_refs: set[str] = set()
    for index, raw in enumerate(raw_components, 1):
        if not isinstance(raw, dict):
            errors.append(f"Component {index} is not an object.")
            continue
        try:
            ref = _component_ref(raw, index)
            if ref in seen_refs:
                raise CatalogueError(f"Duplicate reference {ref!r}.")
            seen_refs.add(ref)
            profile = _profile_for_raw_component(raw, ref)
            raw_pins = raw.get("pins") or {}
            if not isinstance(raw_pins, dict):
                raise CatalogueError(f"{ref}.pins must be an object.")
            raw_pin_assignments = {str(key): str(value) for key, value in raw_pins.items() if str(value).strip()}
            pins: dict[str, str] = {}
            canonical_to_native: dict[str, str] = {}
            unknown_pins: list[str] = []
            duplicate_native_pins: list[str] = []
            for canonical_pin, net_name in raw_pin_assignments.items():
                native_pin = profile.native_pin_for_canonical(canonical_pin)
                if native_pin is None:
                    unknown_pins.append(canonical_pin)
                    continue
                if native_pin in pins:
                    duplicate_native_pins.append(native_pin)
                    continue
                pins[native_pin] = net_name
                canonical_to_native[canonical_pin] = native_pin
            if unknown_pins:
                raise CatalogueError(f"{ref}/{profile.kind} contains unsupported canonical pins: {', '.join(sorted(unknown_pins))}.")
            if duplicate_native_pins:
                raise CatalogueError(
                    f"{ref}/{profile.kind} assigns multiple canonical pins to native pin(s): {', '.join(sorted(set(duplicate_native_pins)))}."
                )
            missing_pins = sorted(set(profile.pin_numbers) - set(pins))
            if missing_pins and not profile.is_pseudo_component:
                raise CatalogueError(f"{ref}/{profile.kind} is missing assigned pins: {', '.join(missing_pins)}.")
            parameters = _string_map(raw.get("parameters", raw.get("spice_params")), field="parameters", ref=ref)
            metadata = _string_map(raw.get("metadata"), field="metadata", ref=ref)
            raw_value = profile.default_value if raw.get("value") is None or not str(raw.get("value")).strip() else str(raw.get("value")).strip()
            try:
                parameters = validate_parameters(profile, parameters)
                metadata = validate_metadata(profile, metadata)
            except ValueValidationError as exc:
                raise CatalogueError(f"{ref}/{profile.kind}: {exc}") from exc
            try:
                value = validate_component_value(profile, raw_value)
                if profile.value_rule == "source_expression":
                    value_is_waveform = value.upper().startswith(("PULSE(", "SINE(", "EXP(", "SFFM(", "PWL("))
                    parameter_source = {"dc", "pulse", "sine", "exp", "sffm", "pwl"} & set(parameters)
                    if value_is_waveform and parameter_source:
                        raise ValueValidationError(
                            f"{profile.kind} value already defines a waveform and cannot also use source parameter(s) "
                            f"{', '.join(sorted(parameter_source))}."
                        )
            except ValueValidationError as exc:
                # Generic primitive profiles intentionally choose an owned
                # generic model when a loose main JSON carries an unverified
                # marketing/model name. Preserve the circuit and make the
                # substitution explicit instead of silently simulating a
                # guessed named device.
                if profile.kind in {"D", "NPN", "PNP", "NMOS", "PMOS", "OPAMP"} and profile.value_rule == "model_name":
                    value = profile.default_value
                    warnings.append(
                        f"{ref}/{profile.kind}: requested value {raw_value!r} is not a verified project-local model; "
                        f"emitting explicit generic model {value!r}."
                    )
                else:
                    raise CatalogueError(f"{ref}/{profile.kind}: {exc}") from exc
            model = model_for(profile)
            if profile.support_state == "unsupported":
                raise CatalogueError(f"{ref}/{profile.kind} is explicitly unsupported by the LTspice backend.")
            if profile.support_state == "render_only":
                warnings.append(f"{ref}/{profile.kind} is render-only and cannot be simulated.")
            if model and "approximation" in model.get("accuracy", "").lower():
                warnings.append(f"{ref}/{profile.kind}: {model['accuracy']}.")
            if metadata:
                warnings.append(f"{ref}/{profile.kind}: metadata is retained in internal evidence and does not alter the native simulation model.")
            selected.append(
                SelectedComponent(
                    ref=ref,
                    kind=profile.kind,
                    value=value,
                    pins=pins,
                    parameters=parameters,
                    metadata=metadata,
                    profile=profile,
                    canonical_to_native=canonical_to_native,
                )
            )
        except CatalogueError as exc:
            errors.append(str(exc))
    report = {
        "schema": SELECTION_SCHEMA,
        "stage": "ltspice_component_selector",
        "ok": not errors,
        "selected_component_count": len(selected),
        "errors": errors,
        "warnings": warnings,
        "components": [item.as_dict() for item in selected],
    }
    if errors:
        raise CatalogueError("LTspice component selection failed: " + " ".join(errors))
    return selected, report
