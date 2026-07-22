"""Source-backed catalogue for direct ASCII Altium schematic emission.

The first direct Altium writer uses complete component and wire record blocks
from one audited native ASCII ``.SchDoc`` seed. It does not redraw symbols,
does not invent library records, and does not call EasyEDA at generation time.
Every emitted component is a rebased fresh instance of an audited source block.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from pathlib import Path
import re
from typing import Iterable


CATALOGUE_SCHEMA = "progen-altium-source-catalogue/v1"
_SOURCE_PATH = Path(__file__).with_name("source_pack") / "donors" / "logic_trainer_ascii_seed.SchDoc"
_SOURCE_SHA256 = "bfc862eff7dc73bcc787fde8d6fdfc37e283b6249a6e029ee946abf681c2dde8"
_RECORD_PATTERN = re.compile(r"^\|RECORD=(\d+)(?:\||$)")
_FIELD_PATTERN = re.compile(r"\|([^=|]+)=([^|]*)")
_COORDINATE_PATTERN = re.compile(r"^(?:LOCATION|CORNER)\.(X|Y)$|^([XY])\d+$")
_KIND_PATTERN = re.compile(r"[^a-z0-9]+")
_PIN_DIRECTION_BY_CONGLOMERATE = {
    0: "right",
    1: "bottom",
    2: "left",
    3: "top",
}


class SourceCatalogueError(ValueError):
    """A requested family is absent from the audited direct-emission catalogue."""


@dataclass(frozen=True, order=True)
class Point:
    """Schematic coordinates in half-document-unit ticks."""

    x: int
    y: int

    def translated(self, dx: int, dy: int) -> "Point":
        return Point(self.x + dx, self.y + dy)

    def json(self) -> dict[str, float]:
        return {"x": self.x / 2, "y": self.y / 2}


@dataclass(frozen=True)
class Bounds:
    """Axis-aligned source geometry bounds in half-document-unit ticks."""

    min_x: int
    min_y: int
    max_x: int
    max_y: int

    def translated(self, dx: int, dy: int) -> "Bounds":
        return Bounds(self.min_x + dx, self.min_y + dy, self.max_x + dx, self.max_y + dy)

    def expanded(self, amount: int) -> "Bounds":
        return Bounds(
            self.min_x - amount,
            self.min_y - amount,
            self.max_x + amount,
            self.max_y + amount,
        )

    def intersects(self, other: "Bounds") -> bool:
        return not (
            self.max_x < other.min_x
            or other.max_x < self.min_x
            or self.max_y < other.min_y
            or other.max_y < self.min_y
        )

    def json(self) -> dict[str, float]:
        return {
            "min_x": self.min_x / 2,
            "min_y": self.min_y / 2,
            "max_x": self.max_x / 2,
            "max_y": self.max_y / 2,
        }


@dataclass(frozen=True)
class SourceTemplate:
    """One complete source-native component block and its extracted pin facts."""

    key: str
    library_reference: str
    source_owner_index: int
    root_location: Point
    records: tuple[str, ...]
    pins: dict[str, Point]
    pin_names: dict[str, str]
    pin_directions: dict[str, str]
    bounds: Bounds

    @property
    def record_count(self) -> int:
        return len(self.records)

    def resolve_pin(self, supplied: str) -> str:
        """Resolve a canonical numeric/name pin spelling to the source designator."""

        normalized = supplied.strip().casefold()
        aliases = {designator.casefold(): designator for designator in self.pins}
        aliases.update({
            name.casefold(): designator
            for designator, name in self.pin_names.items()
            if name.strip()
        })
        try:
            return aliases[normalized]
        except KeyError as exc:
            raise SourceCatalogueError(
                f"{self.key} has no source-backed pin {supplied!r}; "
                f"supported pins are {sorted(self.pins)} and names "
                f"{sorted(name for name in self.pin_names.values() if name)}."
            ) from exc

    def json(self) -> dict[str, object]:
        return {
            "key": self.key,
            "library_reference": self.library_reference,
            "source_owner_index": self.source_owner_index,
            "record_count": self.record_count,
            "pins": {
                designator: {
                    "name": self.pin_names.get(designator, ""),
                    "escape_direction": self.pin_directions[designator],
                    "position": point.json(),
                }
                for designator, point in sorted(self.pins.items())
            },
            "bounds": self.bounds.json(),
        }


@dataclass(frozen=True)
class SourceCatalogue:
    """Immutable source pack used by the direct writer."""

    header_record: str
    sheet_record: str
    wire_record: str
    net_label_record: str
    templates: dict[str, SourceTemplate]
    aliases: dict[str, str]
    source_path: Path
    source_sha256: str

    def resolve(self, kind: str) -> SourceTemplate:
        normalized = _normalize_kind(kind)
        target = self.aliases.get(normalized)
        if target is None:
            supported = ", ".join(sorted(self.aliases))
            raise SourceCatalogueError(
                f"No direct Altium source template is locked for {kind!r}. "
                f"Known aliases: {supported}."
            )
        return self.templates[target]

    def json(self) -> dict[str, object]:
        return {
            "schema": CATALOGUE_SCHEMA,
            "source": {
                "path": str(self.source_path),
                "sha256": self.source_sha256,
                "format": "Protel for Windows - Schematic Capture Ascii File Version 5.0",
            },
            "components": {
                key: template.json() for key, template in sorted(self.templates.items())
            },
            "aliases": dict(sorted(self.aliases.items())),
            "source_record_types": {"sheet": 31, "wire": 27, "net_label": 25},
        }


def _normalize_kind(value: str) -> str:
    return _KIND_PATTERN.sub("", value.strip().casefold())


def _field(record: str, name: str) -> str | None:
    match = re.search(rf"\|{re.escape(name)}=([^|]*)", record)
    return match.group(1) if match else None


def _record_type(record: str) -> int | None:
    match = _RECORD_PATTERN.match(record)
    return int(match.group(1)) if match else None


def _coordinate(record: str, axis: str) -> int | None:
    whole = _field(record, f"LOCATION.{axis}")
    fraction = _field(record, f"LOCATION.{axis}_FRAC")
    if whole is None:
        return None
    try:
        numerator = int(whole) * 100_000 + int(fraction or "0")
    except ValueError as exc:
        raise SourceCatalogueError(f"Invalid source coordinate in {record[:100]!r}.") from exc
    if numerator % 50_000:
        raise SourceCatalogueError(
            "The locked source uses a coordinate finer than half a document unit."
        )
    return numerator // 50_000


def _coordinates_in_record(record: str) -> Iterable[Point]:
    fields = dict(_FIELD_PATTERN.findall(record))
    pairs: dict[str, dict[str, int]] = {}
    for key, value in fields.items():
        match = _COORDINATE_PATTERN.match(key)
        if not match:
            continue
        axis = match.group(1) or match.group(2)
        prefix = (
            key[:-1]
            if key.startswith(("LOCATION.", "CORNER."))
            else key[1:]
        )
        try:
            pairs.setdefault(prefix, {})[axis] = int(value) * 2
        except ValueError:
            continue
    for key, value in fields.items():
        if not key.endswith("_FRAC"):
            continue
        stem = key[:-5]
        match = _COORDINATE_PATTERN.match(stem)
        if not match:
            continue
        axis = match.group(1) or match.group(2)
        prefix = (
            stem[:-1]
            if stem.startswith(("LOCATION.", "CORNER."))
            else stem[1:]
        )
        if prefix in pairs and axis in pairs[prefix]:
            try:
                pairs[prefix][axis] += int(value) // 50_000
            except ValueError:
                continue
    for pair in pairs.values():
        if "X" in pair and "Y" in pair:
            yield Point(pair["X"], pair["Y"])


def _source_lines(path: Path) -> tuple[str, ...]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SourceCatalogueError(f"Cannot read locked Altium source pack {path}: {exc}") from exc
    lines = tuple(line for line in text.splitlines() if line)
    if not lines or not lines[0].startswith("|HEADER=Protel for Windows - Schematic Capture Ascii"):
        raise SourceCatalogueError(f"{path} is not the locked ASCII Altium source seed.")
    return lines


def _component_blocks(lines: tuple[str, ...]) -> tuple[tuple[str, ...], ...]:
    # Icon storage may follow the schematic stream. It is not part of the
    # final component block merely because it occurs after the last component.
    document_end = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.startswith("|HEADER=")
        ),
        len(lines),
    )
    document_lines = lines[:document_end]
    starts = [index for index, line in enumerate(document_lines) if line.startswith("|RECORD=1|")]
    blocks: list[tuple[str, ...]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(document_lines)
        blocks.append(document_lines[start:end])
    return tuple(blocks)


def _root_owner_index(records: tuple[str, ...]) -> int:
    for record in records[1:]:
        value = _field(record, "OWNERINDEX")
        if value is None:
            continue
        try:
            return int(value)
        except ValueError:
            continue
    raise SourceCatalogueError("A source component block has no owner-index evidence.")


def _make_template(key: str, library_reference: str, records: tuple[str, ...]) -> SourceTemplate:
    forbidden_records = {
        record_type
        for record in records
        if (record_type := _record_type(record)) in {25, 27, 31}
    }
    if forbidden_records:
        raise SourceCatalogueError(
            f"Source component {library_reference!r} contains non-component records "
            f"{sorted(forbidden_records)}; catalogue block boundaries are unsafe."
        )
    source_owner = _root_owner_index(records)
    root_location = Point(
        _coordinate(records[0], "X") or 0,
        _coordinate(records[0], "Y") or 0,
    )
    pins: dict[str, Point] = {}
    names: dict[str, str] = {}
    directions: dict[str, str] = {}
    geometry: list[Point] = []
    for record in records:
        owner = _field(record, "OWNERINDEX")
        if owner is not None:
            try:
                if int(owner) != source_owner:
                    continue
            except ValueError:
                continue
        record_type = _record_type(record)
        if record_type == 2:
            designator = _field(record, "DESIGNATOR")
            x = _coordinate(record, "X")
            y = _coordinate(record, "Y")
            if designator and x is not None and y is not None:
                conglomerate = _field(record, "PINCONGLOMERATE")
                try:
                    direction = _PIN_DIRECTION_BY_CONGLOMERATE[int(conglomerate or "") & 0b11]
                except (KeyError, ValueError) as exc:
                    raise SourceCatalogueError(
                        f"Source pin {designator!r} on {library_reference!r} has no usable "
                        "PINCONGLOMERATE direction."
                    ) from exc
                pins[designator] = Point(x, y)
                names[designator] = _field(record, "NAME") or ""
                directions[designator] = direction
        if record_type in {2, 6, 8, 10, 12, 13, 14}:
            geometry.extend(_coordinates_in_record(record))
    if not pins:
        raise SourceCatalogueError(f"Source component {library_reference!r} has no extractable pins.")
    if not geometry:
        geometry = list(pins.values())
    bounds = Bounds(
        min(point.x for point in geometry),
        min(point.y for point in geometry),
        max(point.x for point in geometry),
        max(point.y for point in geometry),
    )
    return SourceTemplate(
        key=key,
        library_reference=library_reference,
        source_owner_index=source_owner,
        root_location=root_location,
        records=records,
        pins=dict(sorted(pins.items())),
        pin_names=dict(sorted(names.items())),
        pin_directions=dict(sorted(directions.items())),
        bounds=bounds,
    )


_TEMPLATE_SOURCES = {
    "resistor": "MFR-25JT-52-10K",
    "capacitor": "FN43N104J500EGG",
    "led": "204-10SDRD/S530-A3-L",
    "switch": "Key_TH_3.5x6x4.3",
    "pin_header_2": "2.54-1*2P_",
    "header_2x5": "1.27_2x5_3.6THR",
    "74hc00": "SN74HC00N",
    "74hc04": "SN74HC04N",
    "74hc08": "SN74HC08N",
    "74hc32": "74HC32D,653",
    "74hc74": "SN74HC74N",
    "ne555": "NE555DR",
}

_ALIASES = {
    "resistor": "resistor",
    "res": "resistor",
    "r": "resistor",
    "capacitor": "capacitor",
    "cap": "capacitor",
    "c": "capacitor",
    "led": "led",
    "switch": "switch",
    "pushbutton": "switch",
    "button": "switch",
    "pinheader": "pin_header_2",
    "header": "pin_header_2",
    "connector": "pin_header_2",
    "connector2": "pin_header_2",
    "pinheader2": "pin_header_2",
    "header2x5": "header_2x5",
    "74hc00": "74hc00",
    "sn74hc00": "74hc00",
    "74hc04": "74hc04",
    "sn74hc04": "74hc04",
    "74hc08": "74hc08",
    "sn74hc08": "74hc08",
    "74hc32": "74hc32",
    "sn74hc32": "74hc32",
    "74hc74": "74hc74",
    "sn74hc74": "74hc74",
    "ne555": "ne555",
    "timer555": "ne555",
}


@lru_cache(maxsize=1)
def load_source_catalogue() -> SourceCatalogue:
    """Load and integrity-check the compact, audited native record source pack."""

    source_path = _SOURCE_PATH.resolve()
    try:
        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise SourceCatalogueError(f"Cannot hash locked Altium source pack {source_path}: {exc}") from exc
    if digest != _SOURCE_SHA256:
        raise SourceCatalogueError(
            f"Locked Altium source pack hash mismatch: expected {_SOURCE_SHA256}, got {digest}."
        )
    lines = _source_lines(source_path)
    document_end = next(
        (
            index
            for index, line in enumerate(lines[1:], start=1)
            if line.startswith("|HEADER=")
        ),
        len(lines),
    )
    document_lines = lines[:document_end]
    sheet_record = next((line for line in document_lines if line.startswith("|RECORD=31|")), None)
    if sheet_record is None:
        raise SourceCatalogueError("Locked Altium source pack has no source-backed sheet record.")
    wire_record = next((line for line in document_lines if line.startswith("|RECORD=27|")), None)
    if wire_record is None:
        raise SourceCatalogueError("Locked Altium source pack has no source-backed wire record.")
    net_label_record = next((line for line in document_lines if line.startswith("|RECORD=25|")), None)
    if net_label_record is None:
        raise SourceCatalogueError("Locked Altium source pack has no source-backed net-label record.")

    blocks = _component_blocks(document_lines)
    by_reference: dict[str, tuple[str, ...]] = {}
    for block in blocks:
        library_reference = _field(block[0], "LIBREFERENCE")
        if library_reference and library_reference not in by_reference:
            by_reference[library_reference] = block

    templates: dict[str, SourceTemplate] = {}
    for key, library_reference in _TEMPLATE_SOURCES.items():
        try:
            block = by_reference[library_reference]
        except KeyError as exc:
            raise SourceCatalogueError(
                f"Locked source pack is missing required template {library_reference!r}."
            ) from exc
        templates[key] = _make_template(key, library_reference, block)

    return SourceCatalogue(
        header_record=lines[0],
        sheet_record=sheet_record,
        wire_record=wire_record,
        net_label_record=net_label_record,
        templates=dict(sorted(templates.items())),
        aliases=dict(sorted(_ALIASES.items())),
        source_path=source_path,
        source_sha256=digest,
    )
