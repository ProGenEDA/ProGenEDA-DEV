"""Validation helpers for Proteus beautifier layout metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class BeautifierValidationIssue:
    code: str
    message: str
    severity: str = "error"

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
        }


def _bbox(entry: dict[str, Any]) -> dict[str, int] | None:
    bbox = entry.get("after_bbox")
    if not isinstance(bbox, dict):
        return None
    required = {"min_x", "min_y", "max_x", "max_y"}
    if not required <= set(bbox):
        return None
    return {key: int(bbox[key]) for key in required}


def _expanded(bbox: dict[str, int], spacing: int) -> dict[str, int]:
    return {
        "min_x": bbox["min_x"] - spacing,
        "min_y": bbox["min_y"] - spacing,
        "max_x": bbox["max_x"] + spacing,
        "max_y": bbox["max_y"] + spacing,
    }


def _overlap(left: dict[str, int], right: dict[str, int]) -> bool:
    return not (
        left["max_x"] <= right["min_x"]
        or right["max_x"] <= left["min_x"]
        or left["max_y"] <= right["min_y"]
        or right["max_y"] <= left["min_y"]
    )


def visible_layout_bboxes(
    layout_entries: Iterable[dict[str, Any]],
    *,
    visible_keys: set[str] | None = None,
) -> list[tuple[str, dict[str, int]]]:
    """Return placed visible bboxes from beautifier metadata."""

    placed: list[tuple[str, dict[str, int]]] = []
    for entry in layout_entries:
        key = str(entry.get("key", ""))
        if visible_keys is not None and key not in visible_keys:
            continue
        bbox = _bbox(entry)
        if bbox is None:
            continue
        already_at_target = (
            entry.get("target_min_x") is not None
            and entry.get("target_min_y") is not None
            and bbox["min_x"] == int(entry["target_min_x"])
            and bbox["min_y"] == int(entry["target_min_y"])
        )
        if not entry.get("translated") and not already_at_target:
            continue
        placed.append((key, bbox))
    return placed


def layout_overlap_pairs(
    layout_entries: Iterable[dict[str, Any]],
    *,
    visible_keys: set[str] | None = None,
) -> list[tuple[str, str]]:
    """Return pairs whose emitted bboxes overlap."""

    placed = visible_layout_bboxes(layout_entries, visible_keys=visible_keys)
    overlaps: list[tuple[str, str]] = []
    for left_index, (left_key, left_bbox) in enumerate(placed):
        for right_key, right_bbox in placed[left_index + 1 :]:
            if _overlap(left_bbox, right_bbox):
                overlaps.append((left_key, right_key))
    return overlaps


def layout_spacing_pairs(
    layout_entries: Iterable[dict[str, Any]],
    *,
    visible_keys: set[str] | None = None,
    min_spacing: int = 0,
) -> list[tuple[str, str]]:
    """Return pairs closer than ``min_spacing`` after bbox expansion."""

    if min_spacing <= 0:
        return []
    placed = visible_layout_bboxes(layout_entries, visible_keys=visible_keys)
    too_close: list[tuple[str, str]] = []
    for left_index, (left_key, left_bbox) in enumerate(placed):
        expanded_left = _expanded(left_bbox, min_spacing)
        for right_key, right_bbox in placed[left_index + 1 :]:
            if _overlap(expanded_left, right_bbox):
                too_close.append((left_key, right_key))
    return too_close


def _visible_layout_family_bboxes(
    layout_entries: Iterable[dict[str, Any]],
    *,
    visible_keys: set[str] | None = None,
) -> list[tuple[str, str, dict[str, int]]]:
    placed: list[tuple[str, str, dict[str, int]]] = []
    for entry in layout_entries:
        key = str(entry.get("key", ""))
        if visible_keys is not None and key not in visible_keys:
            continue
        bbox = _bbox(entry)
        if bbox is None:
            continue
        already_at_target = (
            entry.get("target_min_x") is not None
            and entry.get("target_min_y") is not None
            and bbox["min_x"] == int(entry["target_min_x"])
            and bbox["min_y"] == int(entry["target_min_y"])
        )
        if not entry.get("translated") and not already_at_target:
            continue
        placed.append((key, str(entry.get("family", "")), bbox))
    return placed


def layout_different_family_spacing_pairs(
    layout_entries: Iterable[dict[str, Any]],
    *,
    visible_keys: set[str] | None = None,
    min_spacing: int = 0,
) -> list[tuple[str, str]]:
    """Return different-family pairs closer than ``min_spacing``."""

    if min_spacing <= 0:
        return []
    placed = _visible_layout_family_bboxes(
        layout_entries,
        visible_keys=visible_keys,
    )
    too_close: list[tuple[str, str]] = []
    for left_index, (left_key, left_family, left_bbox) in enumerate(placed):
        expanded_left = _expanded(left_bbox, min_spacing)
        for right_key, right_family, right_bbox in placed[left_index + 1 :]:
            if left_family == right_family:
                continue
            if _overlap(expanded_left, right_bbox):
                too_close.append((left_key, right_key))
    return too_close


def multipart_packet_issues(
    layout_entries: Iterable[dict[str, Any]],
) -> list[BeautifierValidationIssue]:
    """Flag packed A/B/C subparts that remain one indivisible packet.

    This is intentionally diagnostic for now.  It records the user-observed
    4027/266-style weakness without doing unsafe binary splitting.
    """

    issues: list[BeautifierValidationIssue] = []
    for entry in layout_entries:
        spread = entry.get("multipart_subpart_spread")
        if isinstance(spread, dict) and spread.get("applied") is True:
            continue
        refs = entry.get("refs")
        if not isinstance(refs, list):
            continue
        subpart_refs = [ref for ref in refs if isinstance(ref, str) and ":" in ref]
        if len(subpart_refs) < 2:
            continue
        issues.append(
            BeautifierValidationIssue(
                "W_BEAUTIFIER_MULTIPART_PACKET_NOT_SPLIT",
                (
                    f"{entry.get('key', '<unknown>')} contains subparts "
                    f"{subpart_refs}; current beautifier moves the native packet "
                    "as one unit and does not yet separate A/B/C gates."
                ),
                "warning",
            )
        )
    return issues


def validate_beautifier_layout_entries(
    layout_entries: Iterable[dict[str, Any]],
    *,
    visible_keys: set[str] | None = None,
    min_spacing: int = 0,
    different_family_min_spacing: int = 0,
) -> list[BeautifierValidationIssue]:
    entries = list(layout_entries)
    issues: list[BeautifierValidationIssue] = []
    overlaps = layout_overlap_pairs(entries, visible_keys=visible_keys)
    if overlaps:
        issues.append(
            BeautifierValidationIssue(
                "E_BEAUTIFIER_LAYOUT_OVERLAP",
                f"Beautified visible packet bboxes overlap: {overlaps[:20]}",
            )
        )
    close_pairs = layout_spacing_pairs(
        entries,
        visible_keys=visible_keys,
        min_spacing=min_spacing,
    )
    if close_pairs:
        issues.append(
            BeautifierValidationIssue(
                "W_BEAUTIFIER_LAYOUT_SPACING_LOW",
                f"Beautified visible packet bboxes are below spacing margin: {close_pairs[:20]}",
                "warning",
            )
        )
    different_family_close_pairs = layout_different_family_spacing_pairs(
        entries,
        visible_keys=visible_keys,
        min_spacing=different_family_min_spacing,
    )
    if different_family_close_pairs:
        issues.append(
            BeautifierValidationIssue(
                "E_BEAUTIFIER_DIFFERENT_FAMILY_SPACING_LOW",
                (
                    "Beautified different-family visible packet bboxes are below "
                    f"spacing margin: {different_family_close_pairs[:20]}"
                ),
            )
        )
    issues.extend(multipart_packet_issues(entries))
    return issues
