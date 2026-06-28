"""Static KiCad schematic validation helpers."""

from __future__ import annotations

from pathlib import Path

from .kicad_json_to_project import validate_schematic


def validate_file(path: str | Path) -> dict[str, object]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return validate_schematic(text)
