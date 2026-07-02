"""Updateable component catalogue and pin normalization helpers.

The catalogue is intentionally data-first.  Backend-specific scripts should
consume this module instead of duplicating aliases, pin names, pin roles, and
hidden-supply policy in each pipeline stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping

from .templates import repository_root


CATALOG_PATH = Path("knowledge/component_catalog_v0.json")


def _token(value: str) -> str:
    stripped = value.strip()
    if stripped == "+":
        return "PLUS"
    if stripped == "-":
        return "MINUS"
    return re.sub(r"[^A-Z0-9+]", "", stripped.upper())


@dataclass(frozen=True)
class PinProfile:
    name: str
    role: str = "unknown"
    electrical_type: str = "unknown"
    aliases: tuple[str, ...] = ()
    hidden: bool = False
    subpart: str | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "role": self.role,
            "electrical_type": self.electrical_type,
            "aliases": list(self.aliases),
            "hidden": self.hidden,
        }
        if self.subpart is not None:
            out["subpart"] = self.subpart
        return out


@dataclass(frozen=True)
class ComponentProfile:
    part: str
    category: str
    proteus_marker: str
    terminal_support: str
    aliases: tuple[str, ...]
    pins: tuple[PinProfile, ...]
    package: str | None = None
    inherited_pin_model: str | None = None

    @property
    def pin_by_name(self) -> dict[str, PinProfile]:
        return {pin.name: pin for pin in self.pins}

    @property
    def pin_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        for pin in self.pins:
            aliases[_token(pin.name)] = pin.name
            for alias in pin.aliases:
                aliases[_token(alias)] = pin.name
        return aliases

    def normalize_pin(self, pin: str | int) -> PinProfile:
        text = re.sub(r"^\s*pin\s*[-_:]?\s*", "", str(pin), flags=re.I)
        token = _token(text)
        try:
            name = self.pin_aliases[token]
            return self.pin_by_name[name]
        except KeyError as exc:
            raise ValueError(
                f"Unsupported pin token {pin!r} for component family {self.part}."
            ) from exc

    def pin_names(self, *, include_hidden: bool = False) -> tuple[str, ...]:
        return tuple(
            pin.name
            for pin in self.pins
            if include_hidden or not pin.hidden
        )

    def role_pins(self, roles: Iterable[str], *, include_hidden: bool = False) -> tuple[str, ...]:
        wanted = {role.upper() for role in roles}
        return tuple(
            pin.name
            for pin in self.pins
            if (include_hidden or not pin.hidden) and pin.role.upper() in wanted
        )

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "part": self.part,
            "category": self.category,
            "proteus_marker": self.proteus_marker,
            "terminal_support": self.terminal_support,
            "aliases": list(self.aliases),
            "pins": [pin.as_dict() for pin in self.pins],
        }
        if self.package is not None:
            out["package"] = self.package
        if self.inherited_pin_model is not None:
            out["inherited_pin_model"] = self.inherited_pin_model
        return out


@dataclass(frozen=True)
class ComponentCatalog:
    schema_version: str
    components: Mapping[str, ComponentProfile]
    alias_to_part: Mapping[str, str]
    terminal_label_policy: Mapping[str, str]

    def normalize_part(self, value: str) -> str:
        token = _token(value)
        try:
            return self.alias_to_part[token]
        except KeyError as exc:
            raise ValueError(f"Unknown component family {value!r}.") from exc

    def profile(self, value: str) -> ComponentProfile:
        return self.components[self.normalize_part(value)]

    def get_profile(self, value: str) -> ComponentProfile | None:
        try:
            return self.profile(value)
        except ValueError:
            return None

    def pin_vocabulary(
        self,
        parts: Iterable[str] | None = None,
        *,
        include_hidden: bool = False,
    ) -> dict[str, set[str]]:
        selected = self.components if parts is None else {
            self.normalize_part(part): self.profile(part)
            for part in parts
        }
        return {
            part: set(profile.pin_names(include_hidden=include_hidden))
            for part, profile in selected.items()
        }


def _raw_pin_from_dict(raw: Mapping[str, Any], *, hidden: bool = False) -> PinProfile:
    return PinProfile(
        name=str(raw["name"]),
        role=str(raw.get("role", "unknown")),
        electrical_type=str(raw.get("electrical_type", "unknown")),
        aliases=tuple(str(item) for item in raw.get("aliases", [])),
        hidden=bool(raw.get("hidden", hidden)),
        subpart=str(raw["subpart"]) if raw.get("subpart") is not None else None,
    )


def _pin_model_from_raw(
    raw_components: Mapping[str, Mapping[str, Any]],
    part: str,
    raw_profile: Mapping[str, Any],
    resolved: dict[str, ComponentProfile],
) -> tuple[PinProfile, ...]:
    inherited = raw_profile.get("inherits_pin_model")
    if inherited:
        inherited_part = str(inherited)
        if inherited_part not in resolved:
            resolved[inherited_part] = _profile_from_raw(
                raw_components,
                inherited_part,
                raw_components[inherited_part],
                resolved,
            )
        return resolved[inherited_part].pins

    pin_model = raw_profile.get("pin_model")
    if not isinstance(pin_model, Mapping):
        raise ValueError(f"Catalogue profile {part} lacks a pin_model.")

    pin_aliases = {
        str(alias): str(target)
        for alias, target in dict(pin_model.get("pin_aliases", {})).items()
    }
    hidden = {str(item) for item in pin_model.get("hidden_pins", [])}
    overrides = {
        str(pin): dict(value)
        for pin, value in dict(pin_model.get("overrides", {})).items()
    }

    if "pins" in pin_model:
        pins = [_raw_pin_from_dict(raw) for raw in pin_model["pins"]]
    else:
        pin_count = int(pin_model.get("pin_count", 0))
        if pin_count <= 0:
            raise ValueError(f"Catalogue profile {part} has no pins.")
        pins = [
            PinProfile(
                name=str(index),
                role="unknown",
                electrical_type="unknown",
                hidden=str(index) in hidden,
            )
            for index in range(1, pin_count + 1)
        ]

    by_name = {pin.name: pin for pin in pins}
    for pin_name, raw_override in overrides.items():
        base = by_name.get(pin_name, PinProfile(name=pin_name))
        by_name[pin_name] = PinProfile(
            name=base.name,
            role=str(raw_override.get("role", base.role)),
            electrical_type=str(raw_override.get("electrical_type", base.electrical_type)),
            aliases=tuple(str(item) for item in raw_override.get("aliases", base.aliases)),
            hidden=bool(raw_override.get("hidden", base.hidden or pin_name in hidden)),
            subpart=(
                str(raw_override["subpart"])
                if raw_override.get("subpart") is not None
                else base.subpart
            ),
        )

    for alias, target in pin_aliases.items():
        if target not in by_name:
            raise ValueError(
                f"Catalogue profile {part} maps alias {alias!r} to missing pin {target!r}."
            )
        pin = by_name[target]
        aliases = tuple(dict.fromkeys((*pin.aliases, alias)))
        by_name[target] = PinProfile(
            name=pin.name,
            role=pin.role,
            electrical_type=pin.electrical_type,
            aliases=aliases,
            hidden=pin.hidden,
            subpart=pin.subpart,
        )

    return tuple(by_name[name] for name in by_name)


def _profile_from_raw(
    raw_components: Mapping[str, Mapping[str, Any]],
    part: str,
    raw_profile: Mapping[str, Any],
    resolved: dict[str, ComponentProfile],
) -> ComponentProfile:
    return ComponentProfile(
        part=part,
        category=str(raw_profile.get("category", "unknown")),
        proteus_marker=str(raw_profile.get("proteus_marker", part)),
        terminal_support=str(raw_profile.get("terminal_support", "unknown")),
        aliases=tuple(str(item) for item in raw_profile.get("aliases", [])),
        pins=_pin_model_from_raw(raw_components, part, raw_profile, resolved),
        package=str(raw_profile["package"]) if raw_profile.get("package") is not None else None,
        inherited_pin_model=(
            str(raw_profile["inherits_pin_model"])
            if raw_profile.get("inherits_pin_model") is not None
            else None
        ),
    )


@lru_cache(maxsize=4)
def load_component_catalog(path: str | Path | None = None) -> ComponentCatalog:
    catalog_path = repository_root() / (Path(path) if path is not None else CATALOG_PATH)
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    raw_components = {
        str(part): profile
        for part, profile in dict(raw["components"]).items()
    }
    resolved: dict[str, ComponentProfile] = {}
    for part, raw_profile in raw_components.items():
        if part not in resolved:
            resolved[part] = _profile_from_raw(raw_components, part, raw_profile, resolved)

    aliases: dict[str, str] = {}
    for part, profile in resolved.items():
        for value in (part, profile.proteus_marker, *profile.aliases):
            aliases[_token(value)] = part
    return ComponentCatalog(
        schema_version=str(raw["schema_version"]),
        components=dict(sorted(resolved.items())),
        alias_to_part=aliases,
        terminal_label_policy=dict(raw.get("terminal_label_policy", {})),
    )
