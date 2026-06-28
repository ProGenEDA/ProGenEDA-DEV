"""Source-pack-backed KiCad symbol cache for V1 generation."""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from kicad.source_pack.source_pack_loader import candidate_zips


@dataclass(frozen=True)
class SymbolBlock:
    lib_id: str
    text: str
    source: str


V1_KIND_LIB_IDS = {
    "R": "Device:R",
    "L": "Device:L",
    "VDC": "Simulation_SPICE:VDC",
    "VSIN": "Simulation_SPICE:VSIN",
    "GND": "power:GND",
}


def _balanced_block(text: str, start: int) -> str | None:
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def _extract_symbol(text: str, lib_id: str) -> str | None:
    pattern = f'(symbol "{lib_id}"'
    start = text.find(pattern)
    if start < 0:
        return None
    return _balanced_block(text, start)


def _read_schematic_text_from_zip(path: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith(".kicad_sch"):
                raw = archive.read(name).decode("utf-8", errors="replace")
                out.append((name, raw))
    return out


def _indent_block(block: str) -> str:
    lines = block.strip().splitlines()
    return "\n".join("    " + line.rstrip() for line in lines) + "\n"


def load_source_symbols() -> dict[str, SymbolBlock]:
    """Load mined symbols from bundled KiCad source-pack schematics.

    The source zip is included in the repo so hosted/packaged runs can use the
    same source-derived symbol definitions without requiring a KiCad install.
    """

    wanted = set(V1_KIND_LIB_IDS.values())
    found: dict[str, SymbolBlock] = {}
    for zip_path in candidate_zips():
        if not zip_path.exists():
            continue
        try:
            schematics = _read_schematic_text_from_zip(zip_path)
        except (OSError, zipfile.BadZipFile):
            continue
        for name, text in schematics:
            if "(lib_symbols" not in text:
                continue
            for lib_id in sorted(wanted - set(found)):
                block = _extract_symbol(text, lib_id)
                if block:
                    found[lib_id] = SymbolBlock(lib_id, _indent_block(block), f"{zip_path.name}:{name}")
            if wanted <= set(found):
                return found
    return found


def extract_pin_defs(symbol_text: str) -> dict[str, tuple[float, float]]:
    pins: dict[str, tuple[float, float]] = {}
    pin_re = re.compile(
        r'\(pin\s+[^\n]+?\(at\s+([-0-9.]+)\s+([-0-9.]+)\s+[-0-9.]+\).*?'
        r'\(number\s+"([^"]+)"',
        re.S,
    )
    for match in pin_re.finditer(symbol_text):
        x, y, number = match.groups()
        pins[number] = (float(x), float(y))
    return pins
