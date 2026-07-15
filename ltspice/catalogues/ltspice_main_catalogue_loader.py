"""Strict loader for the donor-native LTspice permanent catalogue.

Unlike the older prototype catalogue, this module intentionally has no generic
fallback.  A missing native symbol, pin geometry, property grammar, or donor
path is a development gap, not permission to invent a visual component.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any


CATALOGUE_SCHEMA = "progen-ltspice-native-main-catalogue/v1"
CATALOGUE_PATH = Path(__file__).with_name("ltspice_main_catalogue.json")
ORIENTATIONS = frozenset({"R0", "R90", "R180", "R270", "M0", "M90", "M180", "M270"})


class NativeCatalogueError(ValueError):
    """A donor-native catalogue record is absent or structurally unsafe."""


def normalize_type_id(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().upper())
    return re.sub(r"_+", "_", text).strip("_")


def _require_mapping(value: object, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NativeCatalogueError(f"{context} must be an object.")
    return value


def _require_text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NativeCatalogueError(f"{context} must be non-empty text.")
    return value


def _require_int(value: object, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise NativeCatalogueError(f"{context} must be an integer.")
    return value


def _validate_component(type_id: str, component: dict[str, Any]) -> None:
    _require_text(component.get("category"), f"{type_id}.category")
    if component.get("status") not in {"pending_donor", "donor_observed", "generated_static", "gui_verified", "supported"}:
        raise NativeCatalogueError(f"{type_id}.status must name a known donor-native support state.")

    native = _require_mapping(component.get("native"), f"{type_id}.native")
    _require_text(native.get("record"), f"{type_id}.native.record")
    evidence = native.get("donor_evidence")
    if not isinstance(evidence, list) or not evidence or not all(isinstance(item, str) and item.strip() for item in evidence):
        raise NativeCatalogueError(f"{type_id}.native.donor_evidence must be a non-empty path list.")
    if type_id != "GROUND":
        _require_text(native.get("symbol"), f"{type_id}.native.symbol")
        _require_text(native.get("stock_library_path"), f"{type_id}.native.stock_library_path")

    body = _require_mapping(component.get("body"), f"{type_id}.body")
    if body.get("coordinate_system") not in {"asc_symbol_anchor", "physical_anchor"}:
        raise NativeCatalogueError(f"{type_id}.body.coordinate_system is invalid.")
    bounds = _require_mapping(body.get("local_bounds"), f"{type_id}.body.local_bounds")
    left = _require_int(bounds.get("left"), f"{type_id}.body.local_bounds.left")
    right = _require_int(bounds.get("right"), f"{type_id}.body.local_bounds.right")
    top = _require_int(bounds.get("top"), f"{type_id}.body.local_bounds.top")
    bottom = _require_int(bounds.get("bottom"), f"{type_id}.body.local_bounds.bottom")
    if right < left or bottom < top:
        raise NativeCatalogueError(f"{type_id}.body.local_bounds are inverted.")
    if _require_int(body.get("wire_clearance"), f"{type_id}.body.wire_clearance") < 0:
        raise NativeCatalogueError(f"{type_id}.body.wire_clearance must be non-negative.")

    orientations = component.get("legal_orientations")
    if not isinstance(orientations, list) or not orientations or any(item not in ORIENTATIONS for item in orientations):
        raise NativeCatalogueError(f"{type_id}.legal_orientations contains an invalid LTspice orientation.")
    if component.get("default_orientation") not in orientations:
        raise NativeCatalogueError(f"{type_id}.default_orientation must be donor-proven legal.")

    pin_model = _require_mapping(component.get("pin_model"), f"{type_id}.pin_model")
    if pin_model.get("coordinate_system") != body["coordinate_system"]:
        raise NativeCatalogueError(f"{type_id}.pin_model.coordinate_system must match body geometry.")
    pins = _require_mapping(pin_model.get("pins"), f"{type_id}.pin_model.pins")
    if not pins:
        raise NativeCatalogueError(f"{type_id}.pin_model.pins must not be empty.")
    numbers: set[str] = set()
    for key, pin_raw in pins.items():
        pin = _require_mapping(pin_raw, f"{type_id}.pin_model.pins.{key}")
        number = _require_text(pin.get("number"), f"{type_id}.{key}.number")
        if number in numbers:
            raise NativeCatalogueError(f"{type_id} repeats native pin number {number!r}.")
        numbers.add(number)
        _require_text(pin.get("name"), f"{type_id}.{key}.name")
        local = pin.get("local")
        if not isinstance(local, list) or len(local) != 2:
            raise NativeCatalogueError(f"{type_id}.{key}.local must be a two-item ASC point.")
        for index, coordinate in enumerate(local):
            _require_int(coordinate, f"{type_id}.{key}.local[{index}]")
        if pin.get("side") not in {"left", "right", "top", "bottom"}:
            raise NativeCatalogueError(f"{type_id}.{key}.side is invalid.")

    properties = _require_mapping(component.get("properties"), f"{type_id}.properties")
    for name, property_raw in properties.items():
        property_record = _require_mapping(property_raw, f"{type_id}.properties.{name}")
        _require_text(property_record.get("record"), f"{type_id}.properties.{name}.record")
        _require_text(property_record.get("syntax"), f"{type_id}.properties.{name}.syntax")
        _require_text(property_record.get("effect"), f"{type_id}.properties.{name}.effect")
        if property_record.get("support_state") not in {"donor_proven", "inferred_from_donor", "pending_donor"}:
            raise NativeCatalogueError(f"{type_id}.properties.{name}.support_state is required.")
        property_evidence = property_record.get("evidence")
        if not isinstance(property_evidence, list) or not property_evidence:
            raise NativeCatalogueError(f"{type_id}.properties.{name}.evidence must be non-empty.")

    placement = _require_mapping(component.get("placement_evidence"), f"{type_id}.placement_evidence")
    for name in ("observed_count", "donor_max_count"):
        if _require_int(placement.get(name), f"{type_id}.placement_evidence.{name}") < 0:
            raise NativeCatalogueError(f"{type_id}.placement_evidence.{name} must be non-negative.")
    progression = placement.get("target_progression")
    if not isinstance(progression, list) or not progression or any(not isinstance(item, int) or item < 1 for item in progression):
        raise NativeCatalogueError(f"{type_id}.placement_evidence.target_progression must be positive counts.")
    _require_text(placement.get("target_status"), f"{type_id}.placement_evidence.target_status")
    _require_text(placement.get("mixed_family_status"), f"{type_id}.placement_evidence.mixed_family_status")


@dataclass(frozen=True)
class NativeCatalogue:
    raw: dict[str, Any]
    components: dict[str, dict[str, Any]]
    aliases: dict[str, str]
    grid: int
    max_components_per_circuit: int

    def resolve_type_id(self, value: object) -> str:
        token = normalize_type_id(value)
        if token in self.components:
            return token
        candidate = self.aliases.get(token)
        if candidate is None:
            raise NativeCatalogueError(f"No donor-native LTspice component is registered for {value!r}.")
        return candidate

    def get(self, value: object) -> dict[str, Any]:
        return deepcopy(self.components[self.resolve_type_id(value)])


def load_native_catalogue(path: str | Path | None = None) -> NativeCatalogue:
    catalogue_path = Path(path) if path is not None else CATALOGUE_PATH
    try:
        raw = json.loads(catalogue_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise NativeCatalogueError(f"{catalogue_path} is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema") != CATALOGUE_SCHEMA:
        raise NativeCatalogueError(f"{catalogue_path} must use {CATALOGUE_SCHEMA}.")
    if raw.get("unit") != "ltspice_asc_grid":
        raise NativeCatalogueError("The donor-native catalogue must use LTspice ASC grid coordinates.")
    grid = _require_int(raw.get("grid"), "catalogue.grid")
    if grid <= 0:
        raise NativeCatalogueError("catalogue.grid must be positive.")
    cap = _require_int(raw.get("max_components_per_circuit"), "catalogue.max_components_per_circuit")
    if cap < 1:
        raise NativeCatalogueError("catalogue.max_components_per_circuit must be positive.")
    source = _require_mapping(raw.get("components"), "catalogue.components")
    if not source:
        raise NativeCatalogueError("catalogue.components must not be empty.")

    components: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for raw_type_id, component_raw in source.items():
        type_id = normalize_type_id(raw_type_id)
        if not type_id:
            raise NativeCatalogueError("catalogue has an empty component type id.")
        component = _require_mapping(component_raw, f"catalogue.components.{raw_type_id}")
        _validate_component(type_id, component)
        components[type_id] = deepcopy(component)
        for name in (type_id, *component.get("aliases", [])):
            alias = normalize_type_id(name)
            previous = aliases.setdefault(alias, type_id)
            if previous != type_id:
                raise NativeCatalogueError(f"Alias {alias!r} belongs to both {previous} and {type_id}.")

    return NativeCatalogue(
        raw=deepcopy(raw),
        components=components,
        aliases=aliases,
        grid=grid,
        max_components_per_circuit=cap,
    )
