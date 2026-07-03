"""Permanent EDA-neutral component catalogues for routing and generation."""

from .component_catalogue_loader import (
    CatalogueError,
    ComponentCatalogue,
    load_component_catalogue,
    normalize_type_id,
)

__all__ = [
    "CatalogueError",
    "ComponentCatalogue",
    "load_component_catalogue",
    "normalize_type_id",
]
