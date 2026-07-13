"""Deterministic normal-mode edits and LTspice value validation.

This is intentionally a profile-driven editor, not a free-form SPICE command
box.  Advanced raw-ASC editing belongs to a separately authorized surface;
normal users can only change fields that the selected component profile proves
safe to emit.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from .catalogue import CatalogueError, ComponentProfile


SAFE_TEXT = re.compile(r"^[A-Za-z0-9_+\-.,=(){}*/: Ωµμ\t]+$")
SAFE_METADATA_TEXT = re.compile(r"^[A-Za-z0-9_+\-.,=(){}*/:% Ωµμ\t]+$")
# Dots delimit `REF.PIN` endpoints in the backend-neutral circuit contract,
# so accepting a dot in a reference makes a later native wire ambiguous.
REFERENCE = re.compile(r"[A-Za-z#][A-Za-z0-9_#-]*\Z")
NUMBER = re.compile(
    r"^(?P<number>[+-]?(?:(?:\d+(?:\.\d*)?)|(?:\.\d+))(?:[eE][+-]?\d+)?)"
    r"(?P<scale>meg|[TGMKkmunpfF])?(?P<unit>[A-Za-zΩ]*)$"
)
SOURCE_PREFIXES = ("PULSE(", "SINE(", "EXP(", "SFFM(", "PWL(")
EDIT_SCHEMA = "progen-ltspice-normal-mode-edit/v0.1"


class ValueValidationError(ValueError):
    """A safe normal-mode edit cannot be represented by the selected profile."""


def _plain_text(value: object, *, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueValidationError(f"{field} cannot be empty.")
    if "\n" in text or "\r" in text or "!" in text or ";" in text or not SAFE_TEXT.fullmatch(text):
        raise ValueValidationError(f"{field} contains unsupported or unsafe SPICE text.")
    return text


def _numeric_parts(value: object, *, field: str) -> tuple[str, str, str]:
    # Normalize common UI glyphs before applying the ASCII-only native writer
    # policy. Donor ASC files use a legacy micro byte, while generated output
    # must always use the deterministic ASCII spelling `u`.
    normalized = str(value).strip().replace("µ", "u").replace("μ", "u").replace("Ω", "ohm")
    text = _plain_text(normalized, field=field)
    match = NUMBER.fullmatch(text)
    if not match:
        raise ValueValidationError(f"{field} must be a SPICE numeric value such as 10k, 100n, or 2.2m.")
    return match.group("number"), (match.group("scale") or ""), (match.group("unit") or "")


def normalize_spice_number(value: object, *, field: str, capacitance: bool = False) -> str:
    """Normalize a passive/source number without changing its SPICE magnitude.

    LTspice treats an `f` suffix as femto. A bare `12F` is visually ambiguous
    in a UI that calls a field capacitance, so normal mode rejects it rather
    than quietly changing a requested 12 farads into 12 femtofarads.
    """

    number, scale, unit = _numeric_parts(value, field=field)
    if capacitance and scale.lower() == "f" and not unit:
        raise ValueValidationError(
            f"{field} value {value!r} is ambiguous: LTspice interprets f/F as femto. "
            "Use 12 for 12 farads, or 12f for 12 femtofarads."
        )
    if unit and unit.lower() not in {"v", "a", "h", "f", "ohm", "r"}:
        raise ValueValidationError(f"{field} has unsupported unit suffix {unit!r}.")
    # Units are display information for primitive numeric values. The SPICE
    # scale is retained; e.g. 10kOhm becomes 10k.
    return f"{number}{scale.lower() if scale.lower() == 'meg' else scale}"


def normalize_voltage_gain(value: object, *, field: str) -> str:
    """Normalize an E-source gain without silently accepting a physical unit.

    A VCVS gain is a voltage ratio.  LTspice's primitive consumes a bare
    scalar, so accepting a value such as ``2V`` and stripping the unit would
    make a normal-mode edit look more precise than it is.  Keep this field
    intentionally narrower than a generic passive number.
    """

    number, scale, unit = _numeric_parts(value, field=field)
    if unit:
        raise ValueValidationError(f"{field} is a dimensionless V/V gain and cannot include unit {unit!r}.")
    return f"{number}{scale.lower() if scale.lower() == 'meg' else scale}"


def normalize_transconductance(value: object, *, field: str) -> str:
    """Normalize a G-source transconductance to LTspice's bare siemens scalar."""

    number, scale, unit = _numeric_parts(value, field=field)
    if unit.lower() not in {"", "s", "siemens"}:
        raise ValueValidationError(f"{field} is a transconductance and accepts only a bare value or an S/siemens suffix.")
    return f"{number}{scale.lower() if scale.lower() == 'meg' else scale}"


def normalize_source_expression(value: object, *, field: str) -> str:
    text = _plain_text(value, field=field)
    uppercase = text.upper()
    # KiCad fixtures and LTspice documentation both use the common `SIN`
    # shorthand, while LTspice's persisted source form is `SINE(...)`.
    if uppercase.startswith("SIN("):
        uppercase = "SINE(" + uppercase[len("SIN(") :]
    if uppercase.startswith(SOURCE_PREFIXES):
        if not text.endswith(")"):
            raise ValueValidationError(f"{field} source expression must close its parenthesis.")
        if uppercase.count("(") != 1 or uppercase.count(")") != 1:
            raise ValueValidationError(f"{field} source expression has unbalanced parentheses.")
        body = text.partition("(")[2][:-1].strip()
        if not body:
            raise ValueValidationError(f"{field} source expression requires at least one argument.")
        values = [item for item in re.split(r"[\s,]+", body) if item]
        expected_ranges = {
            "PULSE(": (7, 8),
            "SINE(": (3, 7),
            "EXP(": (6, 6),
            "SFFM(": (5, 5),
            "PWL(": (2, None),
        }
        prefix = next(item for item in SOURCE_PREFIXES if uppercase.startswith(item))
        lower, upper = expected_ranges[prefix]
        if len(values) < lower or upper is not None and len(values) > upper or prefix == "PWL(" and len(values) % 2:
            expected = f"{lower}" if upper == lower else f"{lower}–{upper}" if upper is not None else f"an even count of at least {lower}"
            raise ValueValidationError(f"{field} {prefix[:-1]} requires {expected} numeric arguments.")
        # LTspice accepts an optional eighth PULSE argument as a cycle count.
        # A newly supplied donor uses ``0`` here; LTspice merely warns and
        # ignores it.  Normal mode must not quietly retain a parameter the
        # simulator discards, so require a positive integer or ask the caller
        # to omit the optional argument entirely.
        if prefix == "PULSE(" and len(values) == 8 and not re.fullmatch(r"[1-9]\d*", values[-1]):
            raise ValueValidationError(
                f"{field} PULSE Ncycles must be a positive integer when supplied; omit the eighth argument for continuous pulses."
            )
        normalized_values = [
            normalize_spice_number(item, field=f"{field} {prefix[:-1]} argument {index}")
            for index, item in enumerate(values, 1)
        ]
        return prefix + " ".join(normalized_values) + ")"
    return normalize_spice_number(text, field=field)


def validate_component_value(profile: ComponentProfile, value: object) -> str:
    """Return a safe native value suitable for a SYMATTR Value record."""

    raw = profile.default_value if value is None or not str(value).strip() else str(value).strip()
    if profile.value_rule == "fixed":
        if raw not in {"", "0", "GND", "gnd", "GROUND", "ground"}:
            raise ValueValidationError(f"{profile.kind} has a fixed native ground value.")
        return "0"
    if profile.value_rule == "spice_number":
        return normalize_spice_number(raw, field=f"{profile.kind}.value")
    if profile.value_rule == "capacitance":
        return normalize_spice_number(raw, field=f"{profile.kind}.value", capacitance=True)
    if profile.value_rule == "inductance":
        return normalize_spice_number(raw, field=f"{profile.kind}.value")
    if profile.value_rule == "voltage_gain":
        return normalize_voltage_gain(raw, field=f"{profile.kind}.value")
    if profile.value_rule == "transconductance":
        return normalize_transconductance(raw, field=f"{profile.kind}.value")
    if profile.value_rule == "source_expression":
        return normalize_source_expression(raw, field=f"{profile.kind}.value")
    if profile.value_rule == "model_name":
        candidate = _plain_text(raw, field=f"{profile.kind}.value")
        # A user selects a named device through its profile (for example kind
        # D with value 1N4148).  The emitted value is intentionally the
        # project-local, evidence-labelled model name, but accepting the
        # profile's public kind and aliases prevents a valid named selection
        # from falling through to a generic model warning.
        def token(text: str) -> str:
            return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")

        accepted = {token(profile.default_value), token(profile.kind), *(token(alias) for alias in profile.aliases)}
        if token(candidate) not in accepted:
            raise ValueValidationError(
                f"{profile.kind}.value is model-locked in normal mode. "
                f"Use the profile default {profile.default_value!r}, or select a profile with that model."
            )
        return profile.default_value
    raise ValueValidationError(f"{profile.kind} declares unknown value rule {profile.value_rule!r}.")


def validate_metadata(profile: ComponentProfile, metadata: dict[str, object] | None) -> dict[str, str]:
    """Validate documentation-only profile fields without accepting raw ASC text."""

    if not metadata:
        return {}
    if not isinstance(metadata, dict):
        raise ValueValidationError(f"{profile.kind}.metadata must be an object.")
    allowed = set(profile.metadata_fields)
    output: dict[str, str] = {}
    for raw_name, raw_value in metadata.items():
        name = str(raw_name).lower()
        if name not in allowed:
            raise ValueValidationError(f"{profile.kind} does not expose metadata field {name!r}.")
        value = str(raw_value).strip()
        if not value or len(value) > 160 or "\n" in value or "\r" in value or "!" in value or ";" in value or not SAFE_METADATA_TEXT.fullmatch(value):
            raise ValueValidationError(f"{profile.kind}.metadata.{name} contains unsupported text.")
        output[name] = value
    return dict(sorted(output.items()))


def validate_parameters(profile: ComponentProfile, parameters: dict[str, object] | None) -> dict[str, str]:
    if not parameters:
        return {}
    if not isinstance(parameters, dict):
        raise ValueValidationError(f"{profile.kind}.parameters must be an object.")
    allowed = set(profile.editable_parameters)
    output: dict[str, str] = {}
    for raw_name, raw_value in parameters.items():
        name = str(raw_name).lower()
        if name not in allowed:
            raise ValueValidationError(f"{profile.kind} does not allow normal-mode parameter {name!r}.")
        value = _plain_text(raw_value, field=f"{profile.kind}.parameters.{name}")
        if name in {"tc", "tc1", "tc2", "temp", "m", "ic", "ipk", "rser", "lser", "rpar", "cpar", "rlshunt", "area", "n", "l", "w", "ad", "as", "pd", "ps", "r", "wiper"}:
            # The currently supported passive profiles use scalar initial
            # conditions only. A parenthesized device-vector IC would need a
            # profile-specific arity/meaning contract rather than free text.
            if name == "ic" and value.startswith("("):
                raise ValueValidationError(f"{profile.kind}.parameters.ic must be one scalar numeric initial condition.")
            value = normalize_spice_number(value, field=f"{profile.kind}.parameters.{name}", capacitance=name == "cpar")
        elif name in {"off", "load"}:
            if value.lower() not in {"0", "1", "true", "false", "yes", "no", "off"}:
                raise ValueValidationError(f"{profile.kind}.parameters.{name} must be a boolean-like value.")
        elif name in {"dc", "ac"}:
            value = normalize_spice_number(value, field=f"{profile.kind}.parameters.{name}")
        elif name in {"pulse", "sine", "exp", "sffm", "pwl"}:
            prefix = name.upper() + "("
            if not value.upper().startswith(prefix):
                value = prefix + value + ")"
            value = normalize_source_expression(value, field=f"{profile.kind}.parameters.{name}")
        output[name] = value
    waveform_names = {"pulse", "sine", "exp", "sffm", "pwl"}
    selected_waveforms = sorted(waveform_names & set(output))
    if len(selected_waveforms) > 1:
        raise ValueValidationError(
            f"{profile.kind}.parameters selects incompatible source waveforms: {', '.join(selected_waveforms)}."
        )
    if selected_waveforms and "dc" in output:
        raise ValueValidationError(
            f"{profile.kind}.parameters cannot combine {selected_waveforms[0]} with dc in normal mode; choose one source definition."
        )
    return dict(sorted(output.items()))


def spice_line_from_parameters(profile: ComponentProfile, parameters: dict[str, str]) -> str | None:
    """Render a stable, profile-whitelisted `SpiceLine` value."""

    if not parameters:
        return None
    source_names = {"dc", "ac", "pulse", "sine", "exp", "sffm", "pwl"}
    tokens: list[str] = []
    for name, value in sorted(parameters.items()):
        if name in source_names:
            tokens.append(value if name not in {"dc", "ac"} else f"{name.upper()} {value}")
        elif name in {"off", "load"} and value.lower() in {"1", "true", "yes", "off"}:
            tokens.append(name)
        else:
            tokens.append(f"{name}={value}")
    return " ".join(tokens)


def normal_mode_fields(profile: ComponentProfile) -> dict[str, Any]:
    """Return the deterministic edit schema presented by a normal UI."""

    return {
        "value": {"rule": profile.value_rule, "default": profile.default_value},
        "reference": {"pattern": REFERENCE.pattern, "renames_net_endpoints": True},
        "parameters": list(profile.editable_parameters),
        "metadata": list(profile.metadata_fields),
        "advanced_raw_asc": {"available": False, "reason": "admin/demo mode only"},
    }


def build_editable_component_index(circuit: dict[str, Any], profiles_by_ref: dict[str, ComponentProfile]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for component in circuit.get("components", []):
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or component.get("id") or "")
        profile = profiles_by_ref.get(ref)
        if not ref or profile is None:
            continue
        items.append(
            {
                "ref": ref,
                "kind": profile.kind,
                "native_symbol": profile.symbol,
                "support_state": profile.support_state,
                "fields": normal_mode_fields(profile),
            }
        )
    return {"schema": EDIT_SCHEMA, "mode": "normal", "components": items}


def rename_component_reference(circuit: dict[str, Any], old_ref: str, new_ref: str) -> dict[str, Any]:
    """Rename a component and every canonical endpoint deterministically."""

    old = str(old_ref).strip()
    new = str(new_ref).strip()
    if not REFERENCE.fullmatch(new):
        raise ValueValidationError(f"Reference {new!r} is not safe.")
    result = deepcopy(circuit)
    components = result.get("components")
    if not isinstance(components, list):
        raise ValueValidationError("circuit.components must be an array.")
    refs = [str(item.get("ref") or item.get("id") or "") for item in components if isinstance(item, dict)]
    if old not in refs:
        raise ValueValidationError(f"Cannot rename unknown reference {old!r}.")
    if new != old and new in refs:
        raise ValueValidationError(f"Cannot rename {old!r} to duplicate reference {new!r}.")
    # Analysis cards can name a source/reference (`.dc V1 ...`, `.tf ... V1`,
    # and so on). The normal editor deliberately has no free-form directive
    # editor, so it must not leave a renamed component behind in a card that
    # would later fail only in an optional simulator run. Admin mode can edit
    # both under the directive validator; normal mode reports the dependency.
    ref_token = re.compile(rf"(?<![A-Za-z0-9_#-]){re.escape(old)}(?![A-Za-z0-9_#-])", re.IGNORECASE)
    directive_values: list[object] = []
    if isinstance(result.get("spice_directives"), list):
        directive_values.extend(result["spice_directives"])
    project = result.get("project")
    if isinstance(project, dict) and isinstance(project.get("analysis"), list):
        directive_values.extend(project["analysis"])
    for directive in directive_values:
        text = str(directive.get("text") or "") if isinstance(directive, dict) else str(directive)
        if ref_token.search(text):
            raise ValueValidationError(
                f"Cannot rename {old!r}: a validated analysis directive references it. "
                "Update that directive in admin/demo mode first."
            )
    for item in components:
        if not isinstance(item, dict):
            continue
        if str(item.get("ref") or item.get("id") or "") == old:
            if item.get("ref") == old:
                item["ref"] = new
            if item.get("id") == old:
                item["id"] = new
    def replace_endpoint(endpoint: object) -> object:
        text = str(endpoint)
        return new + text[len(old):] if text.startswith(old + ".") else endpoint
    nets = result.get("nets")
    if isinstance(nets, dict):
        for name, members in nets.items():
            if isinstance(members, list):
                nets[name] = [replace_endpoint(member) for member in members]
    expected = result.get("expected_netlist")
    if isinstance(expected, dict) and isinstance(expected.get("nets"), list):
        for net in expected["nets"]:
            if isinstance(net, dict) and isinstance(net.get("members"), list):
                net["members"] = [replace_endpoint(member) for member in net["members"]]
    return result


def apply_normal_mode_edits(
    circuit: dict[str, Any],
    profiles_by_ref: dict[str, ComponentProfile],
    edits: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply a small, audited edit set without accepting arbitrary ASC text."""

    result = deepcopy(circuit)
    audit: list[dict[str, Any]] = []
    active_profiles = dict(profiles_by_ref)
    for index, edit in enumerate(edits, 1):
        if not isinstance(edit, dict):
            raise ValueValidationError(f"Edit {index} must be an object.")
        ref = str(edit.get("ref") or "")
        field = str(edit.get("field") or "")
        if ref not in active_profiles:
            raise ValueValidationError(f"Edit {index} targets unsupported reference {ref!r}.")
        profile = active_profiles[ref]
        if field == "reference":
            new_ref = str(edit.get("value") or "")
            result = rename_component_reference(result, ref, new_ref)
            active_profiles[new_ref] = active_profiles.pop(ref)
            audit.append({"ref": ref, "field": field, "value": new_ref})
            continue
        target = next(
            (item for item in result.get("components", []) if isinstance(item, dict) and str(item.get("ref") or item.get("id") or "") == ref),
            None,
        )
        if target is None:
            raise ValueValidationError(f"Edit {index} cannot find component {ref!r}.")
        if field == "value":
            normalized = validate_component_value(profile, edit.get("value"))
            target["value"] = normalized
        elif field.startswith("parameters."):
            name = field.partition(".")[2].lower()
            existing = dict(target.get("parameters") or target.get("spice_params") or {})
            existing[name] = edit.get("value")
            target["parameters"] = validate_parameters(profile, existing)
            target.pop("spice_params", None)
            normalized = target["parameters"][name]
        elif field.startswith("metadata."):
            name = field.partition(".")[2].lower()
            if name not in profile.metadata_fields:
                raise ValueValidationError(f"{profile.kind} does not expose metadata field {name!r}.")
            existing = dict(target.get("metadata") or {})
            existing[name] = str(edit.get("value") or "").strip()
            target["metadata"] = validate_metadata(profile, existing)
            normalized = target["metadata"][name]
        else:
            raise ValueValidationError(f"Edit {index} uses unsupported normal-mode field {field!r}.")
        audit.append({"ref": ref, "field": field, "value": normalized})
    return result, {"schema": EDIT_SCHEMA, "mode": "normal", "ok": True, "edits": audit}
