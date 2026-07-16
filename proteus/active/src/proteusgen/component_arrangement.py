"""Reusable component arrangement helpers for Proteus layout stages.

This module deliberately works on layout metadata, not binary project members.
It exists so component placement, beautification, and validation can share the
same spacing policy without reaching into ROOT.CDB or donor-specific slot
numbers.
"""

from __future__ import annotations

from typing import Any, Iterable


def next_start_slot_after_layout_entries(
    entries: Iterable[dict[str, Any]],
    fallback_slot: int,
    *,
    origin_y: int,
    slot_y: int,
    columns: int,
    gap_y: int,
) -> int:
    """Return a conservative grid slot after variable-height placed entries.

    Shelf layout uses actual packet bounding boxes, so the count of emitted
    groups is not enough to infer the next safe row.  This helper derives the
    next start slot from the maximum emitted Y coordinate.
    """

    max_y: int | None = None
    for entry in entries:
        bbox = entry.get("after_bbox")
        if isinstance(bbox, dict) and "max_y" in bbox:
            max_y = int(bbox["max_y"]) if max_y is None else max(max_y, int(bbox["max_y"]))
    if max_y is None:
        return fallback_slot

    target_y = max_y + gap_y
    if target_y <= origin_y:
        return fallback_slot

    rows_after_origin = ((target_y - origin_y) // slot_y) + 1
    return max(fallback_slot, rows_after_origin * columns)
