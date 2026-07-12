"""Deterministic native `.asc` and project-local `.asy` writers."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any, Iterable, Protocol

from .catalogue import ComponentProfile, model_for
from .component_placer import PlacedComponent
from .directive_validator import validate_analysis_directives
from .geometry import GRID, Point, Segment
from .symbol_semantics import expected_symbol_attributes


ASC_VERSION = "4.1"
ASC_WRITER_SCHEMA = "progen-ltspice-asc-writer/v0.1"
MODEL_LIBRARY_NAME = "progeneda_v1_models.lib"


class _FlagLike(Protocol):
    point: Any
    name: str


@dataclass(frozen=True)
class WrittenAsset:
    path: Path
    sha256: str
    kind: str

    def as_dict(self, root: Path) -> dict[str, Any]:
        return {
            "path": str(self.path.relative_to(root)),
            "sha256": self.sha256,
            "kind": self.kind,
            "size_bytes": self.path.stat().st_size,
        }


@dataclass(frozen=True)
class AscWriteResult:
    asc_path: Path
    symbol_assets: tuple[WrittenAsset, ...]
    model_asset: WrittenAsset | None
    directives: tuple[str, ...]
    directive_repairs: tuple[dict[str, str], ...] = ()

    def as_dict(self, root: Path) -> dict[str, Any]:
        return {
            "schema": ASC_WRITER_SCHEMA,
            "asc": WrittenAsset(self.asc_path, sha256_file(self.asc_path), "schematic").as_dict(root),
            "symbols": [item.as_dict(root) for item in self.symbol_assets],
            "model_library": self.model_asset.as_dict(root) if self.model_asset else None,
            "directives": list(self.directives),
            "directive_repairs": list(self.directive_repairs),
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_project_stem(value: object) -> str:
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip()).strip("._")
    return stem or "PROGEN_LTSPICE_PROJECT"


def _line(*parts: object) -> str:
    return " ".join(str(part) for part in parts)


def _symbol_graphics(template: str) -> list[str]:
    """Return intentionally owned vector geometry for a project-local symbol."""

    graphics: dict[str, list[str]] = {
        "resistor": [
            "LINE Normal 0 0 0 16",
            "LINE Normal 0 16 -16 28",
            "LINE Normal -16 28 16 40",
            "LINE Normal 16 40 -16 52",
            "LINE Normal -16 52 16 64",
            "LINE Normal 16 64 0 76",
            "LINE Normal 0 76 0 96",
        ],
        "fuse": [
            "LINE Normal 0 0 0 24",
            "RECTANGLE Normal -24 24 24 72",
            "LINE Normal -16 64 16 32",
            "LINE Normal 0 72 0 96",
        ],
        "capacitor": [
            "LINE Normal 0 0 0 24",
            "LINE Normal -32 24 32 24",
            "LINE Normal -32 40 32 40",
            "LINE Normal 0 40 0 64",
        ],
        "capacitor_polarized": [
            "LINE Normal 0 0 0 24",
            "LINE Normal -32 24 32 24",
            "ARC Normal -32 32 32 48 -32 40 32 40",
            "LINE Normal 0 40 0 64",
            "LINE Normal 20 12 20 28",
            "LINE Normal 12 20 28 20",
        ],
        "inductor": [
            "LINE Normal 0 0 0 16",
            "ARC Normal -16 16 16 40 -16 28 16 28",
            "ARC Normal -16 32 16 56 -16 44 16 44",
            "ARC Normal -16 48 16 72 -16 60 16 60",
            "ARC Normal -16 64 16 88 -16 76 16 76",
            "LINE Normal 0 88 0 96",
        ],
        "source": [
            "LINE Normal 0 0 0 16",
            "CIRCLE Normal -32 16 32 80",
            "LINE Normal 0 80 0 96",
            "LINE Normal -12 36 12 36",
            "LINE Normal 0 24 0 48",
            "LINE Normal -12 64 12 64",
        ],
        "source_current": [
            "LINE Normal 0 0 0 16",
            "CIRCLE Normal -32 16 32 80",
            "LINE Normal 0 80 0 96",
            "LINE Normal 0 64 0 32",
            "LINE Normal 0 32 -8 44",
            "LINE Normal 0 32 8 44",
        ],
        "diode": [
            "LINE Normal 0 0 0 24",
            "LINE Normal -28 24 28 24",
            "LINE Normal -28 24 0 64",
            "LINE Normal 28 24 0 64",
            "LINE Normal -28 64 28 64",
            "LINE Normal 0 64 0 96",
        ],
        "led": [
            "LINE Normal 0 0 0 24",
            "LINE Normal -28 24 28 24",
            "LINE Normal -28 24 0 64",
            "LINE Normal 28 24 0 64",
            "LINE Normal -28 64 28 64",
            "LINE Normal 0 64 0 96",
            "LINE Normal 24 20 48 -4",
            "LINE Normal 40 -4 48 -4",
            "LINE Normal 48 -4 48 4",
            "LINE Normal 8 36 32 12",
            "LINE Normal 24 12 32 12",
            "LINE Normal 32 12 32 20",
        ],
        "bjt_npn": [
            "LINE Normal 0 0 0 24",
            "CIRCLE Normal -32 16 32 80",
            "LINE Normal -64 48 -16 48",
            "LINE Normal -16 32 -16 64",
            "LINE Normal -16 40 16 24",
            "LINE Normal -16 56 16 72",
            "LINE Normal 16 72 0 96",
            "LINE Normal 8 72 16 72",
            "LINE Normal 16 72 12 64",
        ],
        "bjt_pnp": [
            "LINE Normal 0 0 0 24",
            "CIRCLE Normal -32 16 32 80",
            "LINE Normal -64 48 -16 48",
            "LINE Normal -16 32 -16 64",
            "LINE Normal -16 40 16 24",
            "LINE Normal -16 56 16 72",
            "LINE Normal 16 72 0 96",
            "LINE Normal 12 64 16 72",
            "LINE Normal 16 72 8 72",
        ],
        "mosfet_n": [
            "LINE Normal 0 0 0 24",
            "LINE Normal 0 72 0 96",
            "LINE Normal -8 32 -8 64",
            "LINE Normal -64 48 -24 48",
            "LINE Normal 8 24 8 72",
            "LINE Normal 8 32 24 32",
            "LINE Normal 24 32 24 64",
            "LINE Normal 24 64 8 64",
        ],
        "mosfet_p": [
            "LINE Normal 0 0 0 24",
            "LINE Normal 0 72 0 96",
            "LINE Normal -8 32 -8 64",
            "LINE Normal -64 48 -24 48",
            "LINE Normal 8 24 8 72",
            "LINE Normal 8 32 24 32",
            "LINE Normal 24 32 24 64",
            "LINE Normal 24 64 8 64",
            "CIRCLE Normal -32 40 -16 56",
        ],
        "switch": [
            "LINE Normal 0 16 24 32",
            "LINE Normal 72 32 0 96",
            "LINE Normal 24 32 64 16",
            "LINE Normal -48 32 -16 32",
            "LINE Normal -48 80 -16 80",
            "LINE Normal -16 24 -16 88",
            "LINE Normal -16 56 24 56",
        ],
        "potentiometer": [
            "LINE Normal 0 0 0 16",
            "LINE Normal 0 16 -16 28",
            "LINE Normal -16 28 16 40",
            "LINE Normal 16 40 -16 52",
            "LINE Normal -16 52 16 64",
            "LINE Normal 16 64 0 76",
            "LINE Normal 0 76 0 96",
            "LINE Normal -64 48 -24 48",
            "LINE Normal -32 40 -16 48",
            "LINE Normal -32 56 -16 48",
        ],
        "opamp": [
            "LINE Normal -32 16 -32 80",
            "LINE Normal -32 16 32 48",
            "LINE Normal -32 80 32 48",
            "LINE Normal -64 32 -32 32",
            "LINE Normal -64 64 -32 64",
            "LINE Normal 0 0 0 16",
            "LINE Normal 0 80 0 96",
            "LINE Normal 32 48 64 48",
            "LINE Normal -48 32 -40 32",
            "LINE Normal -44 28 -44 36",
            "LINE Normal -48 64 -40 64",
        ],
    }
    return list(graphics.get(template, []))


def asy_text(profile: ComponentProfile) -> str:
    if profile.is_pseudo_component or not profile.symbol:
        raise ValueError(f"{profile.kind} has no .asy asset.")
    lines = ["Version 4", "SymbolType CELL"]
    lines.extend(_symbol_graphics(profile.symbol_template))
    lines.extend(["WINDOW 0 80 16 Left 2", "WINDOW 3 80 48 Left 2"])
    if profile.electrical_prefix:
        lines.append(_line("SYMATTR", "Prefix", profile.electrical_prefix))
    lines.append(_line("SYMATTR", "Value", profile.default_value))
    for pin in profile.pins:
        lines.append(_line("PIN", pin.x, pin.y, pin.justification, 8))
        lines.append(_line("PINATTR", "PinName", pin.name))
        lines.append(_line("PINATTR", "SpiceOrder", pin.number))
    return "\n".join(lines) + "\n"


def _write_ascii(path: Path, text: str) -> None:
    try:
        data = text.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"Attempted to write non-ASCII LTspice data to {path}.") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def write_symbol_assets(project_dir: Path, profiles: Iterable[ComponentProfile]) -> tuple[WrittenAsset, ...]:
    by_symbol: dict[str, ComponentProfile] = {}
    for profile in profiles:
        if profile.is_pseudo_component or not profile.symbol:
            continue
        existing = by_symbol.get(profile.symbol)
        if existing is not None and (
            existing.symbol_template != profile.symbol_template
            or existing.electrical_prefix != profile.electrical_prefix
            or existing.pins != profile.pins
        ):
            raise ValueError(f"Conflicting project-local symbol definitions for {profile.symbol!r}.")
        by_symbol[profile.symbol] = profile
    assets: list[WrittenAsset] = []
    for symbol, profile in sorted(by_symbol.items()):
        path = project_dir / f"{symbol}.asy"
        _write_ascii(path, asy_text(profile))
        assets.append(WrittenAsset(path, sha256_file(path), "symbol"))
    return tuple(assets)


def write_model_library(project_dir: Path, profiles: Iterable[ComponentProfile]) -> WrittenAsset | None:
    models: dict[str, dict[str, str]] = {}
    for profile in profiles:
        model = model_for(profile)
        if model is not None and profile.model_key:
            models[profile.model_key] = model
    if not models:
        return None
    lines = ["* ProGenEDA project-local model library", "* Each approximation is declared in the internal model-resolution report."]
    for key, model in sorted(models.items()):
        lines.extend(["", f"* {key}: {model.get('accuracy', 'unspecified')}", model["text"]])
    path = project_dir / MODEL_LIBRARY_NAME
    _write_ascii(path, "\n".join(lines) + "\n")
    return WrittenAsset(path, sha256_file(path), "model_library")


def _directive_lines(directives: Iterable[str], *, needs_models: bool) -> tuple[list[str], list[dict[str, str]]]:
    output: list[str] = []
    repairs: list[dict[str, str]] = []
    if needs_models:
        output.append(f".include {MODEL_LIBRARY_NAME}")
    validated, directive_repairs = validate_analysis_directives(directives)
    output.extend(validated)
    repairs.extend(directive_repairs)
    return output, repairs


def _fit_sheet(
    placed: list[PlacedComponent],
    segments: list[Segment],
    flags: list[_FlagLike],
    directive_count: int,
    requested: tuple[int, int, int],
) -> tuple[int, int, int]:
    """Grow the native sheet around generated geometry instead of clipping it."""

    number, minimum_width, minimum_height = requested
    if minimum_width <= 0 or minimum_height <= 0:
        raise ValueError("LTspice SHEET width and height must be positive.")
    points: list[Point] = []
    for item in placed:
        points.append(item.origin)
        # Project-owned symbols stay within this conservative envelope. It
        # catches an explicit origin that would clip graphics even if its pin
        # coordinates happen to be non-negative.
        points.extend(
            (
                item.origin.translate(-GRID * 6, -GRID * 6),
                item.origin.translate(GRID * 6, GRID * 6),
            )
        )
        points.extend(item.pin_point(pin.number) for pin in item.component.profile.pins)
    for segment in segments:
        points.extend((segment.start, segment.end))
    points.extend(item.point for item in flags)
    points.extend(Point(16, 16 + index * 32) for index in range(directive_count))
    if not points:
        return requested
    minimum_x = min(point.x for point in points)
    minimum_y = min(point.y for point in points)
    if minimum_x < 0 or minimum_y < 0:
        raise ValueError(
            f"Generated LTspice geometry would leave the native sheet at ({minimum_x},{minimum_y}); "
            "choose non-negative native placement coordinates."
        )
    margin = GRID * 12
    maximum_x = max(point.x for point in points)
    maximum_y = max(point.y for point in points)
    width = max(minimum_width, ((maximum_x + margin + GRID - 1) // GRID) * GRID)
    height = max(minimum_height, ((maximum_y + margin + GRID - 1) // GRID) * GRID)
    return number, width, height


def write_asc(
    *,
    project_dir: Path,
    project_name: str,
    placed: Iterable[PlacedComponent],
    wire_segments: Iterable[Segment],
    flags: Iterable[_FlagLike],
    directives: Iterable[str] = (),
    sheet: tuple[int, int, int] = (1, 1760, 1360),
) -> AscWriteResult:
    """Write one native schematic and only the project-local assets it uses."""

    placed_list = list(placed)
    segments = list(wire_segments)
    flags_list = list(flags)
    profiles = [item.component.profile for item in placed_list]
    symbol_assets = write_symbol_assets(project_dir, profiles)
    model_asset = write_model_library(project_dir, profiles)
    directive_lines, directive_repairs = _directive_lines(directives, needs_models=model_asset is not None)
    fitted_sheet = _fit_sheet(placed_list, segments, flags_list, len(directive_lines), sheet)
    lines = [_line("Version", ASC_VERSION), _line("SHEET", *fitted_sheet)]
    for item in sorted(placed_list, key=lambda candidate: candidate.component.ref):
        profile = item.component.profile
        if profile.is_pseudo_component:
            continue
        assert profile.symbol is not None
        lines.append(_line("SYMBOL", profile.symbol, item.origin.x, item.origin.y, item.orientation))
        attributes = expected_symbol_attributes(item)
        lines.append(_line("SYMATTR", "InstName", attributes["INSTNAME"]))
        lines.append(_line("SYMATTR", "Value", attributes["VALUE"]))
        if "VALUE2" in attributes:
            lines.append(_line("SYMATTR", "Value2", attributes["VALUE2"]))
        if "SPICELINE" in attributes:
            lines.append(_line("SYMATTR", "SpiceLine", attributes["SPICELINE"]))
    for segment in segments:
        if not segment.is_horizontal and not segment.is_vertical:
            raise ValueError("LTspice writer only accepts orthogonal wire segments.")
        lines.append(_line("WIRE", segment.start.x, segment.start.y, segment.end.x, segment.end.y))
    for flag in sorted(flags_list, key=lambda item: (item.name, item.point.x, item.point.y)):
        lines.append(_line("FLAG", flag.point.x, flag.point.y, flag.name))
    for index, directive in enumerate(directive_lines):
        lines.append(_line("TEXT", 16, 16 + index * 32, "Left", 2, "!" + directive))
    path = project_dir / f"{safe_project_stem(project_name)}.asc"
    _write_ascii(path, "\n".join(lines) + "\n")
    return AscWriteResult(path, symbol_assets, model_asset, tuple(directive_lines), tuple(directive_repairs))
