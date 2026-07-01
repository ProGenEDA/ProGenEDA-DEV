"""Compatibility wrapper for the canonical KiCad component placer."""

from __future__ import annotations

from .kicad_component_placer import place_components, run, run_placer_pack

__all__ = ["place_components", "run", "run_placer_pack"]
