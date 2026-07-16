"""Strict shared-JSON adapter for donor-native LTspice generation.

This module accepts the existing repaired ProGenEDA circuit JSON. It resolves
only permanent-catalogue components and evidence-backed editable properties,
then returns internal native facts for the placer/router/writer. It is not a
second user-authored circuit format and has no custom-symbol or terminal
fallback.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Mapping

from ltspice.catalogues.ltspice_main_catalogue_loader import (
    NativeCatalogue,
    NativeCatalogueError,
    load_native_catalogue,
    normalize_type_id,
)


NATIVE_CANONICAL_ADAPTER_SCHEMA = "progen-ltspice-donor-native-adapter/v1"
GROUND_NET_NAMES = frozenset({"0", "GND", "GROUND"})


class NativeCanonicalAdapterError(ValueError):
    """The shared JSON asks for a component or property without native evidence."""


# Shared canonicalizer terms which map to exactly one existing stock family.
# This table does not make a generic component or visual substitute available.
_TYPE_ALIASES = {
    "R": "RESISTOR", "RES": "RESISTOR", "RESISTOR": "RESISTOR", "RESISTOR_AXIAL": "RESISTOR",
    "C": "CAPACITOR", "CAP": "CAPACITOR", "CAPACITOR": "CAPACITOR", "CAPACITOR_GENERIC": "CAPACITOR",
    "L": "INDUCTOR", "IND": "INDUCTOR", "INDUCTOR": "INDUCTOR",
    "V": "VOLTAGE_SOURCE", "VDC": "VOLTAGE_SOURCE", "VAC": "VOLTAGE_SOURCE",
    "VSIN": "VOLTAGE_SOURCE", "VPULSE": "VOLTAGE_SOURCE", "VOLTAGE": "VOLTAGE_SOURCE",
    "VOLTAGE_SOURCE": "VOLTAGE_SOURCE",
    "I": "CURRENT_SOURCE", "IDC": "CURRENT_SOURCE", "CURRENT": "CURRENT_SOURCE",
    "CURRENT_SOURCE": "CURRENT_SOURCE",
    "MISC_SIGNAL": "SIGNAL_SOURCE", "SIGNAL": "SIGNAL_SOURCE", "SIGNAL_SOURCE": "SIGNAL_SOURCE",
    "GND": "GROUND", "GROUND": "GROUND", "0": "GROUND",
}
_SAFE_REFERENCE = re.compile(r"^[A-Za-z][A-Za-z0-9_.$-]*$")
_SAFE_SCALAR = re.compile(r"^[^\s\r\n\x00]+$")
_SAFE_SOURCE = re.compile(r"^[^\r\n\x00]+$")
_WAVEFORM = re.compile(r"^(SINE|SIN|PULSE|EXP|SFFM|PWL)\(([^\r\n\x00]*)\)$", re.IGNORECASE)
_WAVEFORM_ARITY: dict[str, tuple[int, int | None]] = {
    # LTspice 26's installed official help documents the same source grammar
    # for voltage and current.  The optional trailing fields are allowed, but
    # arbitrary free-form Value strings are deliberately not accepted.
    "SINE": (3, 7),
    # LTspice permits omitted trailing pulse parameters interactively, but the
    # normal JSON editor intentionally requires the documented complete timing
    # form (with only Ncycles optional). This prevents an edit from silently
    # inheriting simulator defaults.
    "PULSE": (7, 8),
    "EXP": (6, 6),
    "SFFM": (5, 5),
    "PWL": (4, None),
}


def _mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise NativeCanonicalAdapterError(f"{context} must be an object.")
    return value


def _text(value: object, context: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise NativeCanonicalAdapterError(f"{context} must be text.")
    result = value.strip()
    if not allow_empty and not result:
        raise NativeCanonicalAdapterError(f"{context} must not be empty.")
    if "\r" in result or "\n" in result or "\x00" in result:
        raise NativeCanonicalAdapterError(f"{context} must not contain a newline or NUL byte.")
    return result


def _ground_name(value: object) -> bool:
    return str(value).strip().upper() in GROUND_NET_NAMES


def _resolve_type(raw: Mapping[str, Any], catalogue: NativeCatalogue, context: str) -> str:
    candidates: list[str] = []
    for key in ("ltspice_native_type", "ltspice_profile", "kind", "type"):
        if raw.get(key) is not None:
            token = normalize_type_id(raw[key])
            if token:
                candidates.append(token)
    for token in candidates:
        try:
            return catalogue.resolve_type_id(_TYPE_ALIASES.get(token, token))
        except NativeCatalogueError:
            pass
    wanted = ", ".join(candidates) or "<missing kind/type>"
    raise NativeCanonicalAdapterError(
        f"{context} requests {wanted}, which has no donor-native LTspice record. "
        "Add donor evidence rather than using a custom symbol."
    )


def _orientation(raw: Mapping[str, Any], definition: Mapping[str, Any], context: str) -> tuple[str, str]:
    value = raw.get("ltspice_orientation")
    origin = "ltspice_orientation"
    if value is None and raw.get("rotation") is not None:
        try:
            value = f"R{int(raw['rotation']) % 360}"
        except (TypeError, ValueError) as exc:
            raise NativeCanonicalAdapterError(f"{context}.rotation must be a right angle.") from exc
        origin = "rotation"
    if value is None:
        return str(definition["default_orientation"]), "catalogue_default"
    result = str(value).upper()
    if result not in definition["legal_orientations"]:
        raise NativeCanonicalAdapterError(f"{context}.{origin}={result!r} is not donor-proven for this component.")
    return result, origin


def _native_at(raw: Mapping[str, Any], context: str, grid: int) -> tuple[list[int] | None, str | None]:
    value = raw.get("ltspice_at")
    if value is None:
        return None, "generic_at_ignored" if raw.get("at") is not None else None
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise NativeCanonicalAdapterError(f"{context}.ltspice_at must be [x, y].")
    result: list[int] = []
    for index, coordinate in enumerate(value):
        if not isinstance(coordinate, int) or isinstance(coordinate, bool):
            raise NativeCanonicalAdapterError(f"{context}.ltspice_at[{index}] must be an integer.")
        if coordinate % grid:
            raise NativeCanonicalAdapterError(f"{context}.ltspice_at[{index}] must use the {grid}-unit ASC grid.")
        result.append(coordinate)
    return result, "ltspice_at"


def _parameters(raw: Mapping[str, Any], context: str) -> dict[str, str]:
    source = raw.get("parameters", raw.get("spice_params", {}))
    if source is None:
        return {}
    params = _mapping(source, f"{context}.parameters")
    result: dict[str, str] = {}
    for name, value in params.items():
        if not isinstance(name, str):
            raise NativeCanonicalAdapterError(f"{context}.parameters has a non-text key.")
        token = name.casefold()
        if token in result:
            raise NativeCanonicalAdapterError(f"{context}.parameters repeats {name!r} ignoring case.")
        result[token] = _text(value, f"{context}.parameters.{name}")
    return result


def _optional_value(raw: Mapping[str, Any], context: str) -> str | None:
    if raw.get("value") is None:
        return None
    value = _text(raw["value"], f"{context}.value", allow_empty=True)
    return value or None


def _scalar(value: str, context: str) -> str:
    if not _SAFE_SCALAR.fullmatch(value):
        raise NativeCanonicalAdapterError(f"{context} must be one native scalar token.")
    return value


def _source(value: str, context: str) -> str:
    if not _SAFE_SOURCE.fullmatch(value):
        raise NativeCanonicalAdapterError(f"{context} must be one LTspice source expression.")
    return value


def _waveform_tokens(arguments: str, context: str) -> list[str]:
    """Split one inline source expression into safe scalar arguments.

    Inline PWL accepts spaces or commas between time/value entries.  File,
    repeat, trigger, and behavioural forms intentionally stay out of normal
    mode until their own deterministic file/security contracts exist.
    """

    tokens = [item for item in re.split(r"[\s,]+", arguments.strip()) if item]
    if not tokens or any(not _SAFE_SCALAR.fullmatch(item) for item in tokens):
        raise NativeCanonicalAdapterError(f"{context} must contain only LTspice scalar waveform arguments.")
    return tokens


def _normalise_waveform(kind: str, value: str, context: str) -> tuple[str, str]:
    """Return ``(catalogue_key_suffix, native Value expression)`` safely."""

    requested = kind.upper()
    if requested == "SIN":
        requested = "SINE"
    candidate = value.strip()
    match = _WAVEFORM.fullmatch(candidate)
    if match is not None:
        actual = match.group(1).upper()
        if actual == "SIN":
            actual = "SINE"
        if actual != requested:
            raise NativeCanonicalAdapterError(
                f"{context} declares {requested} but supplies a conflicting {actual} source expression."
            )
        arguments = match.group(2)
    else:
        actual = requested
        arguments = candidate
    minimum, maximum = _WAVEFORM_ARITY[actual]
    tokens = _waveform_tokens(arguments, context)
    if len(tokens) < minimum or (maximum is not None and len(tokens) > maximum):
        expected = f"{minimum} to {maximum}" if maximum is not None else f"at least {minimum}"
        raise NativeCanonicalAdapterError(
            f"{context} {actual} needs {expected} scalar argument(s); got {len(tokens)}."
        )
    if actual == "PWL" and len(tokens) % 2:
        raise NativeCanonicalAdapterError(f"{context} PWL requires time/value pairs.")
    # Normalized spaces make generated ASC deterministic even when a user
    # supplied comma-separated PWL points.
    return actual.casefold(), f"{actual}({' '.join(tokens)})"


def _waveform_from_value(value: str, context: str) -> tuple[str, str] | None:
    match = _WAVEFORM.fullmatch(value.strip())
    if match is None:
        return None
    return _normalise_waveform(match.group(1), value, context)


def _source_ac_value(params: Mapping[str, str], context: str) -> str | None:
    """Build LTspice's native ``Value2`` AC text with optional phase."""

    if "ac_phase" in params and "ac" not in params:
        raise NativeCanonicalAdapterError(f"{context}.parameters.ac_phase requires parameters.ac.")
    if "ac" not in params:
        return None
    magnitude = _scalar(params["ac"], f"{context}.parameters.ac")
    phase = params.get("ac_phase")
    if phase is None:
        return f"AC {magnitude}"
    return f"AC {magnitude} {_scalar(phase, f'{context}.parameters.ac_phase')}"


def _literal_enabled(value: str, context: str) -> str:
    if value.casefold() not in {"1", "true", "yes", "on"}:
        raise NativeCanonicalAdapterError(f"{context} must be true to enable this LTspice flag.")
    return "true"


def _properties(
    type_id: str, raw: Mapping[str, Any], definition: Mapping[str, Any], ref: str, context: str
) -> dict[str, str]:
    """Map shared fields to exact catalogue property keys, without injection."""

    params = _parameters(raw, context)
    value = _optional_value(raw, context)
    # The shared cross-backend normalizer may put a human display label in
    # ``value`` when an LTspice source intentionally omitted it.  The input
    # adapter preserves the original source field alongside the portable
    # result; restore it before property selection for every stock source.
    if type_id in {"VOLTAGE_SOURCE", "CURRENT_SOURCE", "SIGNAL_SOURCE"} and "ltspice_native_value" in raw:
        native_value = raw.get("ltspice_native_value")
        if native_value is None:
            value = None
        else:
            value = _text(native_value, f"{context}.ltspice_native_value", allow_empty=True) or None
    if type_id == "GROUND":
        if params:
            raise NativeCanonicalAdapterError(f"{context}.parameters are invalid for GROUND.")
        return {}
    supported = definition["properties"]
    result: dict[str, str] = {"reference": ref}

    def add(name: str, item: str, item_context: str) -> None:
        if name not in supported:
            raise NativeCanonicalAdapterError(f"{context} asks for unsupported donor-native property {name}.")
        result[name] = item

    if type_id in {"RESISTOR", "CAPACITOR", "INDUCTOR"}:
        if value is not None:
            add("value", _scalar(value, f"{context}.value"), f"{context}.value")
        allowed = {
            "RESISTOR": {"tol": "spice_line.tol", "pwr": "spice_line.pwr"},
            "CAPACITOR": {},
            "INDUCTOR": {"ipk": "spice_line.Ipk", "rser": "spice_line.Rser", "rpar": "spice_line.Rpar", "cpar": "spice_line.Cpar"},
        }[type_id]
        unknown = sorted(set(params) - set(allowed))
        if unknown:
            raise NativeCanonicalAdapterError(
                f"{context}.parameters has no donor-proven field(s) for {type_id}: {', '.join(unknown)}."
            )
        for source_name, native_name in allowed.items():
            if source_name in params:
                add(native_name, _scalar(params[source_name], f"{context}.parameters.{source_name}"), f"{context}.parameters.{source_name}")
        return result

    if type_id in {"VOLTAGE_SOURCE", "CURRENT_SOURCE"}:
        # Native stock sources serialize their electrical expression through
        # SYMATTR Value and their small-signal definition through Value2.  The
        # 2026 installed LTspice help and an LTspice 26 oracle export verify
        # this exact record mapping for both source families.
        window_fields = {"window_123": "window.123", "window_39": "window.39"}
        waveform_names = ("sine", "pulse", "exp", "sffm", "pwl")
        extra = {"rser", "cpar"} if type_id == "VOLTAGE_SOURCE" else {"load"}
        allowed = {"dc", "ac", "ac_phase", *waveform_names, *window_fields, *extra}
        unknown = sorted(set(params) - allowed)
        family = "voltage" if type_id == "VOLTAGE_SOURCE" else "current"
        if unknown:
            raise NativeCanonicalAdapterError(
                f"{context}.parameters has no evidence-backed {family} field(s): {', '.join(unknown)}."
            )

        requested_waveforms = [name for name in waveform_names if name in params]
        if len(requested_waveforms) > 1 or (requested_waveforms and "dc" in params):
            raise NativeCanonicalAdapterError(
                f"{context}.parameters must specify exactly one {family} Value definition."
            )
        if requested_waveforms:
            name = requested_waveforms[0]
            suffix, expression = _normalise_waveform(name, params[name], f"{context}.parameters.{name}")
            if value is not None:
                from_value = _waveform_from_value(value, f"{context}.value")
                if from_value is None or from_value[1].casefold() != expression.casefold():
                    raise NativeCanonicalAdapterError(f"{context}.value conflicts with parameters.{name}.")
            add(f"value.{suffix}", expression, f"{context}.parameters.{name}")
        elif "dc" in params:
            if value is not None and value != params["dc"]:
                raise NativeCanonicalAdapterError(f"{context}.value conflicts with parameters.dc.")
            add("value.dc", _scalar(params["dc"], f"{context}.parameters.dc"), f"{context}.parameters.dc")
        elif value is not None:
            waveform = _waveform_from_value(value, f"{context}.value")
            if waveform is not None:
                suffix, expression = waveform
                add(f"value.{suffix}", expression, f"{context}.value")
            else:
                add("value.dc", _scalar(value, f"{context}.value"), f"{context}.value")

        ac_value = _source_ac_value(params, context)
        if not result.get("value.dc") and not any(name.startswith("value.") for name in result if name != "value2.ac") and ac_value is not None:
            # LTspice's AC-only donor pattern explicitly uses a zero DC Value.
            add("value.dc", "0", f"{context}.parameters.ac")
        if ac_value is not None:
            add("value2.ac", ac_value, f"{context}.parameters.ac")
        if type_id == "VOLTAGE_SOURCE":
            if "rser" in params:
                add("spice_line.Rser", _scalar(params["rser"], f"{context}.parameters.rser"), f"{context}.parameters.rser")
            if "cpar" in params:
                add("spice_line.Cpar", _scalar(params["cpar"], f"{context}.parameters.cpar"), f"{context}.parameters.cpar")
        elif "load" in params:
            add("spice_line.load", _literal_enabled(params["load"], f"{context}.parameters.load"), f"{context}.parameters.load")
        for source_name, native_name in window_fields.items():
            if source_name in params:
                add(native_name, _source(params[source_name], f"{context}.parameters.{source_name}"), f"{context}.parameters.{source_name}")
        return result

    if type_id == "SIGNAL_SOURCE":
        window_fields = {"window_123": "window.123", "window_39": "window.39"}
        unknown = sorted(set(params) - {"ac", *window_fields})
        if unknown:
            raise NativeCanonicalAdapterError(
                f"{context}.parameters has no donor-proven Misc signal field(s): {', '.join(unknown)}."
            )
        if value is not None:
            add("value", _source(value, f"{context}.value"), f"{context}.value")
        if "ac" in params:
            # The donor's stock Misc\\signal source uses a blank Value with
            # Value2 AC <magnitude>.  Preserve that exact native pattern when
            # the shared JSON requests its one observed source mode.
            if value is None:
                add("value", "", f"{context}.parameters.ac")
            magnitude = _scalar(params["ac"], f"{context}.parameters.ac")
            add("value2.ac", f"AC {magnitude}", f"{context}.parameters.ac")
        for source_name, native_name in window_fields.items():
            if source_name in params:
                add(native_name, _source(params[source_name], f"{context}.parameters.{source_name}"), f"{context}.parameters.{source_name}")
        return result
    raise NativeCanonicalAdapterError(f"{context} has unknown donor-native type {type_id}.")


def _pin_lookup(definition: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for local, raw_pin in definition["pin_model"]["pins"].items():
        pin = _mapping(raw_pin, "catalogue pin")
        number = str(pin["number"])
        for name in (str(local), number, str(pin["name"])):
            result.setdefault(name.casefold(), number)
    return result


def _endpoint(value: object, context: str) -> tuple[str, str]:
    item = _text(value, context)
    if "." not in item:
        raise NativeCanonicalAdapterError(f"{context} must use REF.PIN.")
    ref, pin = item.rsplit(".", 1)
    if not ref or not pin:
        raise NativeCanonicalAdapterError(f"{context} must use REF.PIN.")
    return ref, pin


def _expected_netlist_agrees(source: Mapping[str, Any]) -> bool:
    """Defend the shared topology invariant at the native boundary too.

    ``canonicalize_source`` already rejects a contradiction before its shared
    fixer runs.  Keeping the same deterministic check here protects callers
    that use this adapter directly (including the native test/fixture tools),
    so a writer can never pick whichever of ``nets`` or ``expected_netlist``
    happens to be more convenient.
    """

    expected = source.get("expected_netlist")
    if expected is None:
        return False
    if not isinstance(expected, Mapping) or not isinstance(expected.get("nets"), list):
        raise NativeCanonicalAdapterError("expected_netlist must contain a nets array when supplied.")
    raw_nets = source.get("nets")
    if not isinstance(raw_nets, Mapping):
        raise NativeCanonicalAdapterError("nets must be an object before expected_netlist can be checked.")
    expected_nets: dict[str, set[str]] = {}
    for index, item in enumerate(expected["nets"]):
        if not isinstance(item, Mapping) or not isinstance(item.get("members"), list) or not item.get("name"):
            raise NativeCanonicalAdapterError(f"expected_netlist.nets[{index}] needs name and members.")
        name = str(item["name"])
        if name in expected_nets:
            raise NativeCanonicalAdapterError(f"expected_netlist repeats net {name!r}.")
        expected_nets[name] = {str(member) for member in item["members"]}
    actual_nets: dict[str, set[str]] = {}
    for name, members in raw_nets.items():
        if not isinstance(members, list):
            raise NativeCanonicalAdapterError(f"nets.{name} must be an endpoint array.")
        token = str(name)
        if token in actual_nets:
            raise NativeCanonicalAdapterError(f"nets repeats net {token!r} after text conversion.")
        actual_nets[token] = {str(member) for member in members}
    if set(actual_nets) != set(expected_nets):
        raise NativeCanonicalAdapterError("nets and expected_netlist name sets disagree; refusing native generation.")
    for name in sorted(actual_nets):
        if actual_nets[name] != expected_nets[name]:
            raise NativeCanonicalAdapterError(
                f"net {name!r} disagrees with expected_netlist; refusing native generation."
            )
    return True


def normal_editable_fields(type_id: object, *, catalogue: NativeCatalogue | None = None) -> dict[str, Any]:
    """Expose only normal-mode fields backed by donor or oracle evidence."""

    active = catalogue or load_native_catalogue()
    try:
        resolved = active.resolve_type_id(type_id)
    except NativeCatalogueError as exc:
        raise NativeCanonicalAdapterError(str(exc)) from exc
    definition = active.get(resolved)
    fields = {
        name: {
            "record": item["record"], "syntax": item["syntax"], "effect": item["effect"],
            "evidence": deepcopy(item["evidence"]),
        }
        for name, item in definition["properties"].items()
        if item.get("support_state") in {"donor_proven", "official_help_ltspice26_verified"}
    }
    return {
        "schema": "progen-ltspice-donor-native-normal-editor/v1",
        "type_id": resolved,
        "normal_mode": fields,
        "advanced_mode": {
            "available": False,
            "reason": "Raw ASC edit mode awaits its separately permission-gated deterministic validator.",
        },
    }


def adapt_canonical_native_circuit(
    circuit: Mapping[str, Any], *, catalogue: NativeCatalogue | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve the shared canonical circuit into bounded donor-native facts."""

    active = catalogue or load_native_catalogue()
    source = _mapping(circuit, "canonical circuit")
    expected_netlist_checked = _expected_netlist_agrees(source)
    raw_components = source.get("components")
    if not isinstance(raw_components, list) or not raw_components:
        raise NativeCanonicalAdapterError("canonical circuit.components must be a non-empty array.")
    if len(raw_components) > active.max_components_per_circuit:
        raise NativeCanonicalAdapterError(
            f"canonical circuit has {len(raw_components)} components; cap is {active.max_components_per_circuit}."
        )

    components: list[dict[str, Any]] = []
    by_ref: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    for index, item in enumerate(raw_components):
        raw = _mapping(item, f"components[{index}]")
        ref = _text(raw.get("ref", raw.get("id")), f"components[{index}].ref")
        if not _SAFE_REFERENCE.fullmatch(ref):
            raise NativeCanonicalAdapterError(f"components[{index}].ref {ref!r} is not a safe LTspice instance name.")
        if ref.casefold() in by_ref:
            raise NativeCanonicalAdapterError(f"components repeats {ref!r} ignoring case.")
        type_id = _resolve_type(raw, active, f"components[{index}]")
        definition = active.get(type_id)
        if type_id != "GROUND":
            prefix = str(definition["native"].get("prefix", ""))
            if prefix and not ref.upper().startswith(prefix.upper()):
                raise NativeCanonicalAdapterError(
                    f"components[{index}].ref {ref!r} must use LTspice prefix {prefix!r} for {type_id}."
                )
        orientation, orientation_source = _orientation(raw, definition, f"components[{index}]")
        at, at_source = _native_at(raw, f"components[{index}]", active.grid)
        if at_source == "generic_at_ignored":
            warnings.append(f"{ref}.at is shared layout intent; native placer will choose an ASC position.")
        prepared = {
            "ref": ref,
            "type_id": type_id,
            "orientation": orientation,
            "orientation_source": orientation_source,
            "ltspice_at": at,
            "properties": _properties(type_id, raw, definition, ref, f"components[{index}]"),
            "pin_lookup": _pin_lookup(definition),
        }
        components.append(prepared)
        by_ref[ref.casefold()] = prepared

    raw_nets = source.get("nets")
    if not isinstance(raw_nets, Mapping) or not raw_nets:
        raise NativeCanonicalAdapterError("canonical circuit.nets must be a non-empty object.")
    physical_pins = {
        (component["ref"].casefold(), number)
        for component in components if component["type_id"] != "GROUND"
        for number in set(component["pin_lookup"].values())
    }
    assigned: dict[tuple[str, str], str] = {}
    nets: dict[str, dict[str, Any]] = {}
    for raw_name, members in raw_nets.items():
        name = _text(raw_name, "net name")
        if not isinstance(members, list):
            raise NativeCanonicalAdapterError(f"nets.{name} must be an endpoint array.")
        physical: list[str] = []
        ground_refs: list[str] = []
        seen: set[str] = set()
        for index, member in enumerate(members):
            ref, pin_name = _endpoint(member, f"nets.{name}[{index}]")
            component = by_ref.get(ref.casefold())
            if component is None:
                raise NativeCanonicalAdapterError(f"nets.{name} references unknown component {ref!r}.")
            pin = component["pin_lookup"].get(pin_name.casefold())
            if pin is None:
                raise NativeCanonicalAdapterError(f"nets.{name} references unknown native pin {ref}.{pin_name}.")
            endpoint = f"{component['ref']}.{pin}"
            if endpoint.casefold() in seen:
                continue
            seen.add(endpoint.casefold())
            if component["type_id"] == "GROUND":
                if not _ground_name(name):
                    raise NativeCanonicalAdapterError(f"ground {endpoint} may only belong to 0/GND/GROUND.")
                ground_refs.append(component["ref"])
                continue
            identity = (component["ref"].casefold(), pin)
            previous = assigned.setdefault(identity, name)
            if previous != name:
                raise NativeCanonicalAdapterError(f"{endpoint} belongs to both {previous!r} and {name!r}.")
            physical.append(endpoint)
        if _ground_name(name):
            if not physical:
                raise NativeCanonicalAdapterError(f"ground net {name!r} needs one physical pin.")
        elif len(physical) < 2:
            raise NativeCanonicalAdapterError(f"net {name!r} needs two physical pins for wire-only routing.")
        nets[name] = {"members": physical, "ground_refs": ground_refs, "is_ground": _ground_name(name)}

    missing = sorted(f"{ref}.{pin}" for ref, pin in physical_pins if (ref, pin) not in assigned)
    if missing:
        raise NativeCanonicalAdapterError("Every native pin needs exactly one net; missing: " + ", ".join(missing))

    directives: list[str] = []
    raw_directives = source.get("spice_directives", [])
    if isinstance(raw_directives, list):
        for item in raw_directives:
            value = item.get("text") if isinstance(item, Mapping) else item
            for line in str(value or "").splitlines():
                directive = line.strip()
                if directive:
                    if not directive.startswith("."):
                        raise NativeCanonicalAdapterError("Analysis directives must begin with '.'.")
                    directives.append(directive)

    circuit_id = str(source.get("circuit_id") or source.get("circuit_name") or source.get("project", {}).get("name") or "ltspice_native")
    native = {
        "schema": NATIVE_CANONICAL_ADAPTER_SCHEMA,
        "circuit_id": circuit_id,
        "components": components,
        "nets": nets,
        "directives": directives,
        "max_components_per_circuit": active.max_components_per_circuit,
    }
    report = {
        "schema": NATIVE_CANONICAL_ADAPTER_SCHEMA,
        "stage": "donor_native_shared_json_adapter",
        "ok": True,
        "component_count": len(components),
        "physical_component_count": sum(item["type_id"] != "GROUND" for item in components),
        "net_count": len(nets),
        "expected_netlist_checked": expected_netlist_checked,
        "terminal_fallback": "forbidden",
        "custom_symbol_fallback": "forbidden",
        "warnings": warnings,
        "resolved_components": [
            {"ref": item["ref"], "type_id": item["type_id"], "orientation": item["orientation"],
             "orientation_source": item["orientation_source"], "property_keys": sorted(item["properties"])}
            for item in components
        ],
    }
    return native, report
