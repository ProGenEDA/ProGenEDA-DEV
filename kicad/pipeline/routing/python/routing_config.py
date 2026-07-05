"""Configuration for the PDF-defined routing v2 architecture."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_ROUTING_V2_CONFIG: dict[str, Any] = {
    "schema": "progen-routing-config/v0.2",
    "unit": "mm",
    "grid": 2.54,
    "sheet": {"width": 420.0, "height": 297.0, "margin": 15.24},
    "placement": {
        "beam_width": 12,
        "candidate_locations_per_component": 24,
        "rotations_per_location_keep": 2,
        "deep_route_top_n": 4,
        "max_candidate_states_per_step": 128,
        "enable_python_live_state_placement": True,
        "enable_cluster_growth_beam_search": True,
        "max_beam_search_components": 12,
        "enable_pivot_rotation_search": True,
        "user_primary_ref": "",
    },
    "legalization": {
        "max_depth": 3,
        "window_initial_radius": 25.4,
        "window_max_radius": 101.6,
        "slot_grid": 2.54,
        "max_slots_per_component": 64,
        "active_component_priority_boost": 1000,
        "locked_component_infinite_cost": True,
    },
    "crossing": {
        "base_crossing_weight": 2.0,
        "clock_crossing_weight": 25.0,
        "bus_crossing_weight": 4.0,
        "near_pin_crossing_weight": 50.0,
        "density_tile_size": 25.4,
        "max_crossings_per_tile_soft": 6,
        "tile_overflow_weight": 30.0,
        "forbid_collinear_overlap": True,
        "forbid_t_touch_different_net": True,
    },
    "parallel": {
        "threads": 8,
        "beam_width": 12,
        "max_candidate_states_per_step": 128,
        "deep_route_top_n": 4,
        "final_state_route_workers": 0,
        "final_state_parallel_min_variants": 2,
        "max_final_state_route_variants": 4,
        "debug_parallel": False,
    },
    "variation": {
        "enabled": False,
        "disable_adaptive_cap": True,
    },
    "wire_fallback": {
        "routing_mode": "wire",
        "arrangement_variant_search": 0.0,
        "arrangement_final_wire_route": 1.0,
        "block_existing_wires": 0.0,
        "near_wire_penalty": 0.0,
        "crossing_penalty": 0.0,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def routing_v2_config(override: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return deterministic routing-v2 config with optional deep overrides."""
    if not override:
        return deepcopy(DEFAULT_ROUTING_V2_CONFIG)
    return _deep_merge(DEFAULT_ROUTING_V2_CONFIG, override)
