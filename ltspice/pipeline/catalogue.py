"""Typed access to the LTspice component and model catalogues.

The catalogue deliberately carries backend facts (pin geometry, native prefix,
model state, and safe editable parameters) separately from the canonical
ProGenEDA circuit JSON.  This keeps a user circuit portable across backends.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
from typing import Any


CATALOGUE_SCHEMA = "progen-ltspice-component-catalogue/v0.1"
MODEL_MAP_SCHEMA = "progen-ltspice-model-map/v0.1"
ORIENTATIONS = ("R0", "R90", "R180", "R270", "M0", "M90", "M180", "M270")


class CatalogueError(ValueError):
    """Raised when an LTspice profile is missing or structurally unsafe."""


def _token(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", str(value).strip().upper()).strip("_")


def _pin_token(value: object) -> str:
    """Normalize pin aliases without collapsing signed names such as IN+/IN-."""

    text = str(value).strip().upper().replace("+", " PLUS ").replace("-", " MINUS ")
    return re.sub(r"[^A-Z0-9]+", "_", text).strip("_")


@dataclass(frozen=True)
class PinProfile:
    number: str
    name: str
    role: str
    x: int
    y: int
    justification: str


@dataclass(frozen=True)
class ComponentProfile:
    kind: str
    aliases: tuple[str, ...]
    symbol: str | None
    symbol_template: str
    reference_prefix: str
    support_state: str
    pins: tuple[PinProfile, ...]
    default_value: str
    value_rule: str
    editable_parameters: tuple[str, ...]
    metadata_fields: tuple[str, ...]
    model_key: str | None
    symbol_prefix: str | None = None
    canonical_pin_map: dict[str, str] | None = None
    native_representation: str | None = None
    semantics_note: str | None = None
    native_semantics: dict[str, str] | None = None

    @property
    def is_pseudo_component(self) -> bool:
        return self.native_representation == "flag_0"

    @property
    def pin_numbers(self) -> tuple[str, ...]:
        return tuple(pin.number for pin in self.pins)

    def pin(self, number: object) -> PinProfile:
        wanted = str(number)
        for pin in self.pins:
            if pin.number == wanted:
                return pin
        raise CatalogueError(f"{self.kind} has no LTspice pin {wanted!r}.")

    @property
    def electrical_prefix(self) -> str:
        """The ASY Prefix that controls the emitted LTspice netlist primitive."""

        return self.symbol_prefix if self.symbol_prefix is not None else self.reference_prefix

    def native_pin_for_canonical(self, canonical_pin: object) -> str | None:
        mapping = self.canonical_pin_map or {}
        return mapping.get(_pin_token(canonical_pin))

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def catalogue_path() -> Path:
    return Path(__file__).with_name("ltspice_component_catalogue.json")


def model_map_path() -> Path:
    return Path(__file__).with_name("ltspice_model_map.json")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogueError(f"{path} is not valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise CatalogueError(f"{path} must contain a JSON object.")
    return value


@lru_cache(maxsize=1)
def load_catalogue() -> dict[str, ComponentProfile]:
    raw = _read_json(catalogue_path())
    if raw.get("schema") != CATALOGUE_SCHEMA:
        raise CatalogueError(f"Unexpected LTspice component catalogue schema: {raw.get('schema')!r}.")
    source = raw.get("components")
    if not isinstance(source, dict) or not source:
        raise CatalogueError("LTspice component catalogue has no components object.")

    profiles: dict[str, ComponentProfile] = {}
    for raw_kind, raw_profile in source.items():
        if not isinstance(raw_profile, dict):
            raise CatalogueError(f"Profile {raw_kind!r} must be an object.")
        kind = _token(raw_kind)
        raw_pins = raw_profile.get("pins")
        if not isinstance(raw_pins, list) or not raw_pins:
            raise CatalogueError(f"Profile {kind} must have at least one pin.")
        pins: list[PinProfile] = []
        for item in raw_pins:
            if not isinstance(item, dict):
                raise CatalogueError(f"Profile {kind} contains a non-object pin.")
            try:
                pins.append(
                    PinProfile(
                        number=str(item["number"]),
                        name=str(item["name"]),
                        role=str(item["role"]),
                        x=int(item["x"]),
                        y=int(item["y"]),
                        justification=str(item["justification"]),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise CatalogueError(f"Profile {kind} has an invalid pin descriptor: {item!r}.") from exc
        numbers = [pin.number for pin in pins]
        if len(numbers) != len(set(numbers)):
            raise CatalogueError(f"Profile {kind} repeats a pin number.")
        support_state = str(raw_profile.get("support_state") or "")
        if support_state not in {"native_simulation", "project_local_model", "render_only", "unsupported"}:
            raise CatalogueError(f"Profile {kind} has unsupported support_state {support_state!r}.")
        default_pin_map: dict[str, str] = {}
        role_numbers: dict[str, list[str]] = {}
        for pin in pins:
            for alias in (pin.number, pin.name):
                token = _pin_token(alias)
                if token:
                    default_pin_map[token] = pin.number
            role = _pin_token(pin.role)
            if role:
                role_numbers.setdefault(role, []).append(pin.number)
        for role, numbers_for_role in role_numbers.items():
            if len(numbers_for_role) == 1:
                default_pin_map.setdefault(role, numbers_for_role[0])
        raw_pin_map = raw_profile.get("canonical_pin_map", {})
        if raw_pin_map is not None and not isinstance(raw_pin_map, dict):
            raise CatalogueError(f"Profile {kind} canonical_pin_map must be an object when supplied.")
        if isinstance(raw_pin_map, dict):
            for raw_alias, raw_native_pin in raw_pin_map.items():
                alias = _pin_token(raw_alias)
                native_pin = str(raw_native_pin)
                if not alias:
                    raise CatalogueError(f"Profile {kind} canonical_pin_map has an empty alias.")
                if native_pin not in numbers:
                    raise CatalogueError(f"Profile {kind} maps canonical pin {raw_alias!r} to missing native pin {native_pin!r}.")
                default_pin_map[alias] = native_pin
        profile = ComponentProfile(
            kind=kind,
            aliases=tuple(_token(alias) for alias in raw_profile.get("aliases", []) if _token(alias)),
            symbol=(str(raw_profile["symbol"]) if raw_profile.get("symbol") else None),
            symbol_template=str(raw_profile.get("symbol_template") or ""),
            reference_prefix=str(raw_profile.get("reference_prefix") or ""),
            support_state=support_state,
            pins=tuple(pins),
            default_value=str(raw_profile.get("default_value") or ""),
            value_rule=str(raw_profile.get("value_rule") or ""),
            editable_parameters=tuple(str(x).lower() for x in raw_profile.get("editable_parameters", [])),
            metadata_fields=tuple(str(x).lower() for x in raw_profile.get("metadata_fields", [])),
            model_key=(str(raw_profile["model_key"]) if raw_profile.get("model_key") else None),
            symbol_prefix=(str(raw_profile["symbol_prefix"]) if raw_profile.get("symbol_prefix") is not None else None),
            canonical_pin_map=dict(sorted(default_pin_map.items())),
            native_representation=(str(raw_profile["native_representation"]) if raw_profile.get("native_representation") else None),
            semantics_note=(str(raw_profile["semantics_note"]) if raw_profile.get("semantics_note") else None),
            native_semantics=(
                {str(key): str(value) for key, value in raw_profile["native_semantics"].items()}
                if isinstance(raw_profile.get("native_semantics"), dict)
                else None
            ),
        )
        if not profile.symbol_template:
            raise CatalogueError(f"Profile {kind} has no symbol_template.")
        if not profile.is_pseudo_component and not profile.symbol:
            raise CatalogueError(f"Profile {kind} must have a project-local symbol name.")
        if profile.support_state == "project_local_model" and not profile.model_key:
            raise CatalogueError(f"Profile {kind} requires a model_key.")
        profiles[kind] = profile
    return profiles


@lru_cache(maxsize=1)
def alias_index() -> dict[str, str]:
    index: dict[str, str] = {}
    for kind, profile in load_catalogue().items():
        for token in (kind, *profile.aliases):
            owner = index.setdefault(token, kind)
            if owner != kind:
                raise CatalogueError(f"Alias {token!r} belongs to both {owner} and {kind}.")
    return index


def normalize_kind(value: object) -> str:
    """Return the normalized catalogue kind or an empty string when unknown."""

    return alias_index().get(_token(value), "")


def resolve_profile(value: object) -> ComponentProfile:
    kind = normalize_kind(value)
    if not kind:
        raise CatalogueError(f"No supported LTspice profile for component kind {value!r}.")
    return load_catalogue()[kind]


@lru_cache(maxsize=1)
def load_model_map() -> dict[str, dict[str, str]]:
    raw = _read_json(model_map_path())
    if raw.get("schema") != MODEL_MAP_SCHEMA:
        raise CatalogueError(f"Unexpected LTspice model map schema: {raw.get('schema')!r}.")
    models = raw.get("models")
    if not isinstance(models, dict):
        raise CatalogueError("LTspice model map has no models object.")
    normalized: dict[str, dict[str, str]] = {}
    for key, entry in models.items():
        if not isinstance(entry, dict) or not entry.get("text"):
            raise CatalogueError(f"Model {key!r} must contain model text.")
        normalized[str(key)] = {str(k): str(v) for k, v in entry.items()}
    return normalized


def model_for(profile: ComponentProfile) -> dict[str, str] | None:
    if not profile.model_key:
        return None
    try:
        return load_model_map()[profile.model_key]
    except KeyError as exc:
        raise CatalogueError(f"Profile {profile.kind} names unknown model {profile.model_key!r}.") from exc


def catalogue_summary() -> dict[str, Any]:
    profiles = load_catalogue()
    return {
        "schema": CATALOGUE_SCHEMA,
        "supported_component_count": len(profiles),
        "support_states": {
            state: sorted(profile.kind for profile in profiles.values() if profile.support_state == state)
            for state in ("native_simulation", "project_local_model", "render_only", "unsupported")
        },
        "profiles": {kind: profile.as_dict() for kind, profile in sorted(profiles.items())},
    }
