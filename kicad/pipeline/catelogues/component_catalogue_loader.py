"""Loader for the permanent component routing catalogue.

The catalogue is intentionally abstract. It describes component geometry,
local pin anchors, legal rotations, priorities, and routing hints without
encoding KiCad schematic syntax. KiCad symbol and footprint maps are loaded
separately by exporters.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kicad.pipeline.placement_catalog import resolve_placement_spec


CATALOGUE_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOGUE_PATH = CATALOGUE_DIR / "component_catalogue.json"


class CatalogueError(ValueError):
    """Raised when a component catalogue is invalid or missing required data."""


def normalize_type_id(value: object) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", str(value or "").strip().upper())
    return re.sub(r"_+", "_", text).strip("_")


def _require_number(mapping: dict[str, Any], key: str, context: str) -> float:
    value = mapping.get(key)
    if not isinstance(value, (int, float)):
        raise CatalogueError(f"{context}.{key} must be a number")
    return float(value)


def _validate_component(type_id: str, component: dict[str, Any]) -> None:
    if not isinstance(component.get("category"), str) or not component["category"]:
        raise CatalogueError(f"{type_id}.category is required")
    body = component.get("body")
    if not isinstance(body, dict):
        raise CatalogueError(f"{type_id}.body is required")
    width = _require_number(body, "width", f"{type_id}.body")
    height = _require_number(body, "height", f"{type_id}.body")
    if width <= 0 or height <= 0:
        raise CatalogueError(f"{type_id}.body width/height must be positive")
    if body.get("origin") != "center":
        raise CatalogueError(f"{type_id}.body.origin must be center")
    keepout = body.get("keepout")
    if not isinstance(keepout, dict):
        raise CatalogueError(f"{type_id}.body.keepout is required")
    for side in ("left", "right", "top", "bottom"):
        if _require_number(keepout, side, f"{type_id}.body.keepout") < 0:
            raise CatalogueError(f"{type_id}.body.keepout.{side} must be nonnegative")
    rotations = component.get("legal_rotations")
    if not isinstance(rotations, list) or not rotations:
        raise CatalogueError(f"{type_id}.legal_rotations must be a non-empty list")
    legal = {0, 90, 180, 270}
    if any(rotation not in legal for rotation in rotations):
        raise CatalogueError(f"{type_id}.legal_rotations may only contain 0, 90, 180, 270")
    if component.get("default_rotation") not in rotations:
        raise CatalogueError(f"{type_id}.default_rotation must be legal")
    pin_model = component.get("pin_model")
    if not isinstance(pin_model, dict) or pin_model.get("coordinate_system") != "local_center_origin":
        raise CatalogueError(f"{type_id}.pin_model.coordinate_system must be local_center_origin")
    pins = pin_model.get("pins")
    if not isinstance(pins, dict) or not pins:
        raise CatalogueError(f"{type_id}.pin_model.pins must be a non-empty object")
    for pin_name, pin in pins.items():
        if not isinstance(pin, dict):
            raise CatalogueError(f"{type_id}.{pin_name} pin must be an object")
        local = pin.get("local")
        if not isinstance(local, list) or len(local) != 2 or not all(isinstance(item, (int, float)) for item in local):
            raise CatalogueError(f"{type_id}.{pin_name}.local must be two numbers")
        if pin.get("side") not in {"left", "right", "top", "bottom"}:
            raise CatalogueError(f"{type_id}.{pin_name}.side is invalid")
        if not isinstance(pin.get("number"), str):
            raise CatalogueError(f"{type_id}.{pin_name}.number must be a string")


def _generic_component(type_id: str, width: float, height: float, category: str) -> dict[str, Any]:
    half_w = round(max(width, 2.54) / 2, 3)
    return {
        "aliases": [type_id],
        "category": category or "generic",
        "body": {
            "width": float(width),
            "height": float(height),
            "origin": "center",
            "keepout": {"left": 2.54, "right": 2.54, "top": 2.54, "bottom": 2.54},
        },
        "legal_rotations": [0, 90, 180, 270],
        "default_rotation": 0,
        "pin_model": {
            "coordinate_system": "local_center_origin",
            "pins": {
                "1": {"number": "1", "local": [-half_w, 0], "side": "left", "type": "passive", "roles": ["generic"]},
                "2": {"number": "2", "local": [half_w, 0], "side": "right", "type": "passive", "roles": ["generic"]},
            },
        },
        "placement_hints": {"role": category or "generic", "can_be_pushed": True, "push_priority": 30, "default_spacing": 7.62},
    }


@dataclass(frozen=True)
class ComponentCatalogue:
    raw: dict[str, Any]
    components: dict[str, dict[str, Any]]
    aliases: dict[str, str]
    grid: float

    def resolve_type_id(self, value: object) -> str:
        normalized = normalize_type_id(value)
        if normalized in self.components:
            return normalized
        return self.aliases.get(normalized, normalized)

    def get(self, value: object) -> dict[str, Any]:
        type_id = self.resolve_type_id(value)
        component = self.components.get(type_id)
        if component is not None:
            return deepcopy(component)
        spec = resolve_placement_spec(str(value or ""))
        if spec is None:
            component = _generic_component(type_id or "GENERIC_COMPONENT", 10.0, 8.0, "generic")
        else:
            component = _generic_component(type_id or spec.kind, spec.width, spec.height, spec.category)
            component["aliases"] = [spec.kind]
            component["placement_hints"]["role"] = spec.category
            component["placement_hints"]["push_priority"] = 20 if any(token in spec.category for token in ("connector", "power_symbol")) else 35
        _validate_component(type_id or "GENERIC_COMPONENT", component)
        return component

    def as_dict(self) -> dict[str, Any]:
        return deepcopy(self.raw)


def load_component_catalogue(path: str | Path | None = None) -> ComponentCatalogue:
    catalogue_path = Path(path) if path is not None else DEFAULT_CATALOGUE_PATH
    data = json.loads(catalogue_path.read_text(encoding="utf-8"))
    if data.get("schema") != "progen-component-catalogue/v0.2":
        raise CatalogueError("component catalogue schema must be progen-component-catalogue/v0.2")
    if data.get("unit") != "mm":
        raise CatalogueError("component catalogue unit must be mm")
    grid = data.get("grid")
    if not isinstance(grid, (int, float)) or float(grid) <= 0:
        raise CatalogueError("component catalogue grid must be positive")
    components_in = data.get("components")
    if not isinstance(components_in, dict) or not components_in:
        raise CatalogueError("component catalogue must contain components")

    components: dict[str, dict[str, Any]] = {}
    aliases: dict[str, str] = {}
    for raw_type_id, component in components_in.items():
        type_id = str(raw_type_id)
        if not isinstance(component, dict):
            raise CatalogueError(f"{type_id} must be an object")
        _validate_component(type_id, component)
        components[type_id] = deepcopy(component)
        aliases[normalize_type_id(type_id)] = type_id
        for alias in component.get("aliases", []):
            aliases[normalize_type_id(alias)] = type_id

    return ComponentCatalogue(raw=deepcopy(data), components=components, aliases=aliases, grid=float(grid))
