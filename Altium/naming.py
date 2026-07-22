"""Shared conservative naming rules for native Altium project artifacts."""

from __future__ import annotations

import re


_SAFE_PROJECT_STEM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
_UNSAFE_PROJECT_CHARACTER = re.compile(r"[^A-Za-z0-9_-]+")
_WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def is_safe_project_stem(value: str) -> bool:
    """Return whether a stem is safe for Altium and common host filesystems."""

    return bool(_SAFE_PROJECT_STEM.fullmatch(value)) and value.upper() not in _WINDOWS_RESERVED


def normalize_project_stem(value: object, fallback: str = "altium_project") -> str:
    """Repair a loose project name without retaining path or extension syntax."""

    text = str(value or "").strip()
    normalized = _UNSAFE_PROJECT_CHARACTER.sub("_", text).strip("_") or fallback
    if normalized.upper() in _WINDOWS_RESERVED:
        normalized = f"project_{normalized}"
    if not normalized[0].isalnum():
        normalized = f"project_{normalized}"
    return normalized
