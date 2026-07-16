"""Load real KiCad library symbols for placement-stage schematics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from kicad.generator.kicad_json_to_project import q


class KiCadSymbolLookupError(LookupError):
    """Raised when a requested KiCad symbol cannot be found in bundled sources."""


@dataclass(frozen=True)
class KiCadLibrarySymbol:
    lib_id: str
    text: str
    source: str
    extends: str | None
    pin_numbers: tuple[str, ...]
    unit_pin_numbers: dict[int, tuple[str, ...]]
    properties: dict[str, str]


@dataclass(frozen=True)
class ResolvedKiCadSymbols:
    symbols: tuple[KiCadLibrarySymbol, ...]
    pins_by_lib_id: dict[str, tuple[str, ...]]
    unit_pins_by_lib_id: dict[str, dict[int, tuple[str, ...]]]
    properties_by_lib_id: dict[str, dict[str, str]]

    def pin_numbers_for(self, lib_id: str) -> tuple[str, ...]:
        return self.pins_by_lib_id.get(lib_id, ())

    def unit_pin_numbers_for(self, lib_id: str, unit: int) -> tuple[str, ...]:
        return self.unit_pins_by_lib_id.get(lib_id, {}).get(unit, ())

    def units_for(self, lib_id: str) -> tuple[int, ...]:
        units = self.unit_pins_by_lib_id.get(lib_id, {})
        return tuple(sorted(units)) or (1,)

    def properties_for(self, lib_id: str) -> dict[str, str]:
        return self.properties_by_lib_id.get(lib_id, {})

    def source_map(self) -> dict[str, str]:
        return {symbol.lib_id: symbol.source for symbol in self.symbols}


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYMBOL_ROOT = PACKAGE_ROOT / ".local" / "AppDir" / "share" / "kicad" / "symbols"
DEFAULT_SUBSET_PATH = PACKAGE_ROOT / "source_pack" / "kicad_symbol_subset_v10_0_4.json"


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


def _extract_symbol_block(text: str, symbol_name: str) -> str | None:
    start = text.find(f'(symbol "{symbol_name}"')
    if start < 0:
        return None
    return _balanced_block(text, start)


def _indent_block(block: str) -> str:
    return "\n".join("    " + line.rstrip() for line in block.strip().splitlines()) + "\n"


def _rewrite_top_symbol_name(block: str, lib_id: str) -> str:
    return re.sub(r'^(\s*\(symbol\s+)"([^"]+)"', rf'\1{q(lib_id)}', block, count=1)


def _extends_target(block: str, library: str) -> str | None:
    match = re.search(r'\(extends\s+"([^"]+)"\)', block)
    if not match:
        return None
    parent = match.group(1)
    return parent if ":" in parent else f"{library}:{parent}"


def _rewrite_extends(block: str, library: str) -> str:
    def repl(match: re.Match[str]) -> str:
        parent = match.group(1)
        full_parent = parent if ":" in parent else f"{library}:{parent}"
        return f"(extends {q(full_parent)})"

    return re.sub(r'\(extends\s+"([^"]+)"\)', repl, block, count=1)


def _library_symbol_name(lib_id: str) -> str:
    return lib_id.split(":", 1)[1] if ":" in lib_id else lib_id


def _direct_child_blocks(block: str) -> list[str]:
    blocks: list[str] = []
    index = block.find("\n")
    if index < 0:
        return blocks
    index += 1
    while index < len(block):
        while index < len(block) and block[index].isspace():
            index += 1
        if index >= len(block) or block[index] == ")":
            break
        if block[index] != "(":
            index += 1
            continue
        child = _balanced_block(block, index)
        if child is None:
            break
        blocks.append(child)
        index += len(child)
    return blocks


def _child_head(block: str) -> str:
    match = re.match(r"\s*\(([^\s\)]+)", block)
    return match.group(1) if match else ""


def _property_name(block: str) -> str | None:
    match = re.match(r'\s*\(property\s+"((?:\\.|[^"])*)"', block, re.S)
    return _unescape_string(match.group(1)) if match else None


def _indented_child(block: str) -> str:
    return "\n".join("\t\t" + line.rstrip() for line in block.strip().splitlines()) + "\n"


def _rename_nested_symbol_prefix(block: str, old_name: str, new_name: str) -> str:
    pattern = r'(\(symbol\s+)"' + re.escape(old_name) + r'(_[^"]*)"'
    return re.sub(pattern, r'\1"' + new_name + r'\2"', block)


def _extract_pin_numbers(block: str) -> tuple[str, ...]:
    found: list[str] = []
    seen: set[str] = set()
    start = 0
    while True:
        pin_start = block.find("(pin ", start)
        if pin_start < 0:
            break
        pin_block = _balanced_block(block, pin_start)
        if pin_block is None:
            start = pin_start + 5
            continue
        start = pin_start + len(pin_block)
        match = re.search(r'\(number\s+"([^"]+)"', pin_block)
        if not match:
            continue
        number = match.group(1)
        if number not in seen:
            seen.add(number)
            found.append(number)
    return tuple(found)


def _extract_unit_pin_numbers(block: str) -> dict[int, tuple[str, ...]]:
    unit_pins: dict[int, list[str]] = {}
    for child in _direct_child_blocks(block):
        if _child_head(child) != "symbol":
            continue
        match = re.match(r'\s*\(symbol\s+"[^"]+_(\d+)_[^"]+"', child)
        if not match:
            continue
        unit = int(match.group(1))
        if unit <= 0:
            continue
        pins = _extract_pin_numbers(child)
        if not pins:
            continue
        bucket = unit_pins.setdefault(unit, [])
        for pin in pins:
            if pin not in bucket:
                bucket.append(pin)
    if unit_pins:
        return {unit: tuple(pins) for unit, pins in sorted(unit_pins.items())}
    pins = _extract_pin_numbers(block)
    return {1: pins} if pins else {}


def _unescape_string(value: str) -> str:
    return bytes(value, "utf-8").decode("unicode_escape")


def _extract_properties(block: str) -> dict[str, str]:
    properties: dict[str, str] = {}
    pattern = re.compile(r'\(property\s+"((?:\\.|[^"])*)"\s+"((?:\\.|[^"])*)"', re.S)
    for match in pattern.finditer(block):
        properties[_unescape_string(match.group(1))] = _unescape_string(match.group(2))
    return properties


def _symbol_file_candidates(symbol_root: Path, library: str, symbol_name: str) -> list[Path]:
    return [
        symbol_root / f"{library}.kicad_symdir" / f"{symbol_name}.kicad_sym",
        symbol_root / f"{library}.kicad_sym",
    ]


class KiCadSymbolLibrary:
    def __init__(
        self,
        *,
        symbol_root: Path = DEFAULT_SYMBOL_ROOT,
        subset_path: Path = DEFAULT_SUBSET_PATH,
        prefer_subset: bool = True,
    ) -> None:
        self.symbol_root = symbol_root
        self.subset_path = subset_path
        self.prefer_subset = prefer_subset
        self._cache: dict[str, KiCadLibrarySymbol] = {}
        self._flat_cache: dict[str, KiCadLibrarySymbol] = {}
        self._subset_symbols: dict[str, dict[str, object]] | None = None

    def _subset(self) -> dict[str, dict[str, object]]:
        if self._subset_symbols is not None:
            return self._subset_symbols
        if not self.subset_path.exists():
            self._subset_symbols = {}
            return self._subset_symbols
        data = json.loads(self.subset_path.read_text(encoding="utf-8"))
        raw_symbols = data.get("symbols", {})
        if not isinstance(raw_symbols, dict):
            self._subset_symbols = {}
            return self._subset_symbols
        self._subset_symbols = {
            str(lib_id): symbol
            for lib_id, symbol in raw_symbols.items()
            if isinstance(symbol, dict) and isinstance(symbol.get("block"), str)
        }
        return self._subset_symbols

    def _load_from_subset(self, lib_id: str) -> KiCadLibrarySymbol | None:
        raw = self._subset().get(lib_id)
        if raw is None:
            return None
        block = str(raw["block"])
        extends = raw.get("extends")
        pins = raw.get("pin_numbers")
        properties = raw.get("properties")
        return KiCadLibrarySymbol(
            lib_id=lib_id,
            text=_indent_block(block),
            source=str(raw.get("source", self.subset_path.name)),
            extends=str(extends) if extends else None,
            pin_numbers=tuple(str(pin) for pin in pins) if isinstance(pins, list) else _extract_pin_numbers(block),
            unit_pin_numbers={
                int(unit): tuple(str(pin) for pin in unit_pins)
                for unit, unit_pins in raw.get("unit_pin_numbers", {}).items()
            }
            if isinstance(raw.get("unit_pin_numbers"), dict)
            else _extract_unit_pin_numbers(block),
            properties={str(k): str(v) for k, v in properties.items()} if isinstance(properties, dict) else _extract_properties(block),
        )

    def _load_from_installed_library(self, lib_id: str) -> KiCadLibrarySymbol:
        if ":" not in lib_id:
            raise KiCadSymbolLookupError(f"KiCad symbol id must be Library:Symbol, got {lib_id!r}")
        library, symbol_name = lib_id.split(":", 1)
        candidates = _symbol_file_candidates(self.symbol_root, library, symbol_name)
        library_dir = self.symbol_root / f"{library}.kicad_symdir"
        if library_dir.exists():
            candidates.extend(sorted(library_dir.glob("*.kicad_sym")))
        seen_paths: set[Path] = set()
        for path in candidates:
            if path in seen_paths or not path.exists():
                continue
            seen_paths.add(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            block = _extract_symbol_block(text, symbol_name)
            if block is None:
                continue
            extends = _extends_target(block, library)
            embedded = _rewrite_extends(_rewrite_top_symbol_name(block, lib_id), library)
            return KiCadLibrarySymbol(
                lib_id=lib_id,
                text=_indent_block(embedded),
                source=str(path.relative_to(PACKAGE_ROOT)),
                extends=extends,
                pin_numbers=_extract_pin_numbers(embedded),
                unit_pin_numbers=_extract_unit_pin_numbers(embedded),
                properties=_extract_properties(embedded),
            )
        raise KiCadSymbolLookupError(f"KiCad symbol {lib_id!r} was not found under {self.symbol_root}")

    def load(self, lib_id: str) -> KiCadLibrarySymbol:
        if lib_id in self._cache:
            return self._cache[lib_id]
        symbol = self._load_from_subset(lib_id) if self.prefer_subset else None
        if symbol is None:
            symbol = self._load_from_installed_library(lib_id)
        self._cache[lib_id] = symbol
        return symbol

    def flattened(self, lib_id: str) -> KiCadLibrarySymbol:
        """Return a self-contained symbol block with inheritance expanded."""
        if lib_id in self._flat_cache:
            return self._flat_cache[lib_id]

        raw = self.load(lib_id)
        if raw.extends is None:
            self._flat_cache[lib_id] = raw
            return raw

        parent = self.flattened(raw.extends)
        raw_children = _direct_child_blocks(raw.text.strip())
        parent_children = _direct_child_blocks(parent.text.strip())

        child_configs = [block for block in raw_children if _child_head(block) not in {"extends", "property", "symbol"}]
        child_config_heads = {_child_head(block) for block in child_configs}
        parent_configs = [
            block
            for block in parent_children
            if _child_head(block) not in {"extends", "property", "symbol"} and _child_head(block) not in child_config_heads
        ]

        child_properties = [block for block in raw_children if _child_head(block) == "property"]
        child_property_names = {name for block in child_properties if (name := _property_name(block)) is not None}
        parent_properties = [
            block
            for block in parent_children
            if _child_head(block) == "property" and (name := _property_name(block)) not in child_property_names
        ]

        child_nested = [block for block in raw_children if _child_head(block) == "symbol"]
        parent_nested = [block for block in parent_children if _child_head(block) == "symbol"]
        nested = child_nested or [
            _rename_nested_symbol_prefix(block, _library_symbol_name(parent.lib_id), _library_symbol_name(lib_id))
            for block in parent_nested
        ]

        flat = [f"(symbol {q(lib_id)}\n"]
        for block in parent_configs + child_configs + parent_properties + child_properties + nested:
            flat.append(_indented_child(block))
        flat.append("\t\t(embedded_fonts no)\n")
        flat.append("\t)\n")
        text = _indent_block("".join(flat))
        symbol = KiCadLibrarySymbol(
            lib_id=lib_id,
            text=text,
            source=f"{raw.source}; flattened_from={parent.source}",
            extends=None,
            pin_numbers=_extract_pin_numbers(text),
            unit_pin_numbers=_extract_unit_pin_numbers(text),
            properties=_extract_properties(text),
        )
        self._flat_cache[lib_id] = symbol
        return symbol

    def pin_numbers_for(self, lib_id: str) -> tuple[str, ...]:
        return self.flattened(lib_id).pin_numbers

    def resolve(self, lib_ids: Iterable[str]) -> ResolvedKiCadSymbols:
        ordered: list[KiCadLibrarySymbol] = []
        seen: set[str] = set()

        def append_symbol(lib_id: str) -> None:
            if lib_id in seen:
                return
            symbol = self.flattened(lib_id)
            seen.add(lib_id)
            ordered.append(symbol)

        requested = tuple(dict.fromkeys(lib_ids))
        for lib_id in requested:
            append_symbol(lib_id)
        return ResolvedKiCadSymbols(
            symbols=tuple(ordered),
            pins_by_lib_id={lib_id: self.pin_numbers_for(lib_id) for lib_id in requested},
            unit_pins_by_lib_id={lib_id: self.flattened(lib_id).unit_pin_numbers for lib_id in requested},
            properties_by_lib_id={lib_id: self.flattened(lib_id).properties for lib_id in requested},
        )


def resolve_kicad_symbols(lib_ids: Iterable[str]) -> ResolvedKiCadSymbols:
    return KiCadSymbolLibrary().resolve(lib_ids)
