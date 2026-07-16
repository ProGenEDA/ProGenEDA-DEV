"""Coordinate-only graph-layout beautifier for donor-native LTspice symbols.

The implementation reuses the placement primitive's exact catalogue geometry
instead of copying a second pin model. It follows the KiCad pipeline boundary:
the beautifier may move or rotate automatic components, but it never changes
their reference, stock symbol, property records, or canonical net membership.
"""

from __future__ import annotations

from typing import Any, Mapping

from ltspice.catalogues.ltspice_main_catalogue_loader import NativeCatalogue

from .native_placer import NATIVE_PLACEMENT_SCHEMA, place_native_components


NATIVE_BEAUTIFIER_SCHEMA = "progen-ltspice-donor-native-beautifier/v1"


class NativeBeautifierError(ValueError):
    """A coordinate-only beautification invariant was not maintained."""


def beautify_native_placement(
    native_circuit: Mapping[str, Any],
    initial_placement: Mapping[str, Any],
    *,
    catalogue: NativeCatalogue | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the graph-layered native placement and its exact coordinate edits."""

    if initial_placement.get("schema") != NATIVE_PLACEMENT_SCHEMA:
        raise NativeBeautifierError("Initial placement does not use the donor-native placement contract.")
    before = initial_placement.get("components")
    if not isinstance(before, Mapping):
        raise NativeBeautifierError("Initial placement has no component map.")
    beautified, placement_report = place_native_components(native_circuit, catalogue=catalogue, arrange=True)
    after = beautified.get("components")
    if not isinstance(after, Mapping) or set(after) != set(before):
        raise NativeBeautifierError("Beautifier changed the physical component set.")

    edits: list[dict[str, Any]] = []
    for ref in sorted(after):
        old = before[ref]
        new = after[ref]
        if not isinstance(old, Mapping) or not isinstance(new, Mapping):
            raise NativeBeautifierError(f"Invalid placement entry for {ref}.")
        for key in ("ref", "type_id", "native_symbol", "properties"):
            if old.get(key) != new.get(key):
                raise NativeBeautifierError(f"Beautifier attempted to change {ref}.{key}.")
        old_origin = list(old.get("origin") or [])
        new_origin = list(new.get("origin") or [])
        old_orientation = str(old.get("orientation") or "")
        new_orientation = str(new.get("orientation") or "")
        if old_origin != new_origin or old_orientation != new_orientation:
            edits.append(
                {
                    "ref": ref,
                    "from": old_origin,
                    "to": new_origin,
                    "from_orientation": old_orientation,
                    "to_orientation": new_orientation,
                }
            )
    report = {
        "schema": NATIVE_BEAUTIFIER_SCHEMA,
        "stage": "donor_native_beautifier",
        "ok": True,
        "source_placement_schema": initial_placement.get("schema"),
        "output_placement_schema": beautified.get("schema"),
        "coordinate_edits": edits,
        "moved_component_count": len(edits),
        "invariants": {
            "topology_changed": False,
            "properties_changed": False,
            "symbol_changed": False,
            "terminal_fallback": "forbidden",
        },
        "placement_report": placement_report,
    }
    return beautified, report
