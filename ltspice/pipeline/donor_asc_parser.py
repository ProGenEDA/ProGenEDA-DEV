"""Read-only parser and census tools for donor-authored LTspice ``.asc`` files.

This module is deliberately separate from :mod:`ltspice_asc_parser`.  The
older parser is part of the prototype generator's validation path and assumes
axis-aligned wires during connectivity reconstruction.  Donor inspection must
not inherit that limitation: LTspice donor files can contain negative
coordinates and arbitrary straight ``WIRE`` records, including diagonals.

The parser is intentionally bounded to the records present in the donor
corpus.  It preserves unknown records for review rather than silently treating
them as supported native semantics.  It never resolves symbols, creates model
files, or infers connectivity from labels; it is evidence collection for the
donor-native placer, property editor, and physical-wire router.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator


DONOR_ASC_SCHEMA = "progen-ltspice-donor-asc/v1"
LTSPICE_ELECTRICAL_GRID = 16
KNOWN_ORIENTATIONS = frozenset({"R0", "R90", "R180", "R270", "M0", "M90", "M180", "M270"})


class DonorAscParseError(ValueError):
    """A donor record cannot be represented without losing its LTspice meaning."""


@dataclass(frozen=True, order=True)
class DonorPoint:
    """An integer coordinate in LTspice ASC space.

    Negative values are valid: donors routinely place a source or annotation
    left of the visible sheet origin.  The electrical grid check is exposed as
    an audit, not a parser restriction, because WINDOW and TEXT positions are
    allowed to use a finer placement grid.
    """

    x: int
    y: int

    def translate(self, dx: int, dy: int) -> "DonorPoint":
        return DonorPoint(self.x + dx, self.y + dy)

    def is_grid_aligned(self, grid: int = LTSPICE_ELECTRICAL_GRID) -> bool:
        if grid <= 0:
            raise ValueError("LTspice grid must be positive.")
        return self.x % grid == 0 and self.y % grid == 0


@dataclass(frozen=True)
class DonorSheet:
    number: int
    width: int
    height: int
    line_number: int


@dataclass(frozen=True)
class DonorWire:
    """One physical, straight LTspice WIRE record.

    A WIRE record is a straight segment even when it is neither horizontal nor
    vertical.  In particular, no geometry helper here assumes Manhattan
    routing; that decision belongs to the new router/beautifier.
    """

    start: DonorPoint
    end: DonorPoint
    line_number: int

    @property
    def is_horizontal(self) -> bool:
        return self.start.y == self.end.y

    @property
    def is_vertical(self) -> bool:
        return self.start.x == self.end.x

    @property
    def is_diagonal(self) -> bool:
        return not self.is_horizontal and not self.is_vertical

    @property
    def is_degenerate(self) -> bool:
        return self.start == self.end


@dataclass(frozen=True)
class DonorFlag:
    point: DonorPoint
    name: str
    line_number: int


@dataclass(frozen=True)
class DonorWindow:
    number: int
    x: int
    y: int
    justification: str
    font_size: int
    line_number: int


@dataclass(frozen=True)
class DonorAttribute:
    key: str
    value: str
    line_number: int


@dataclass
class DonorSymbol:
    """A native SYMBOL block, retaining its stock path spelling verbatim."""

    name: str
    origin: DonorPoint
    orientation: str
    line_number: int
    windows: list[DonorWindow] = field(default_factory=list)
    attributes: dict[str, str] = field(default_factory=dict)
    attribute_records: list[DonorAttribute] = field(default_factory=list)

    @property
    def ref(self) -> str:
        """The native instance name, or an empty string when it is absent."""

        return self.attributes.get("InstName", "")

    def attribute(self, key: str, default: str | None = None) -> str | None:
        """Look up a SYMATTR key case-insensitively without changing raw data."""

        expected = key.casefold()
        for name, value in self.attributes.items():
            if name.casefold() == expected:
                return value
        return default


@dataclass(frozen=True)
class DonorText:
    point: DonorPoint
    justification: str
    font_size: int
    text: str
    line_number: int

    @property
    def is_directive(self) -> bool:
        return self.text.startswith("!")


@dataclass(frozen=True)
class DonorUnknownRecord:
    keyword: str
    raw: str
    line_number: int


@dataclass(frozen=True)
class ElectricalGridViolation:
    record: str
    point: DonorPoint
    line_number: int


@dataclass
class DonorAscDocument:
    """The bounded, loss-aware representation of one donor ``.asc`` file."""

    path: Path
    encoding: str
    version: str
    sheet: DonorSheet
    wires: list[DonorWire]
    flags: list[DonorFlag]
    symbols: list[DonorSymbol]
    texts: list[DonorText]
    unknown_records: list[DonorUnknownRecord]

    @property
    def directives(self) -> list[DonorText]:
        return [record for record in self.texts if record.is_directive]

    @property
    def diagonal_wires(self) -> list[DonorWire]:
        return [wire for wire in self.wires if wire.is_diagonal]

    def electrical_points(self) -> Iterator[tuple[str, DonorPoint, int]]:
        """Yield anchors that must live on the electrical placement grid.

        WINDOW and TEXT records are intentionally omitted: their display
        offsets have donor-proven values such as ``56`` and ``76`` and are not
        routing coordinates.
        """

        for wire in self.wires:
            yield "WIRE", wire.start, wire.line_number
            yield "WIRE", wire.end, wire.line_number
        for flag in self.flags:
            yield "FLAG", flag.point, flag.line_number
        for symbol in self.symbols:
            yield "SYMBOL", symbol.origin, symbol.line_number

    def electrical_grid_violations(self, grid: int = LTSPICE_ELECTRICAL_GRID) -> list[ElectricalGridViolation]:
        """Return, rather than hide, any donor electrical-grid exceptions."""

        if grid <= 0:
            raise ValueError("LTspice grid must be positive.")
        return [
            ElectricalGridViolation(record, point, line_number)
            for record, point, line_number in self.electrical_points()
            if not point.is_grid_aligned(grid)
        ]


@dataclass(frozen=True)
class DonorCorpusCensus:
    """Aggregate facts used to gate catalogue and generator claims."""

    root: Path
    files: tuple[Path, ...]
    encoding_counts: dict[str, int]
    version_counts: dict[str, int]
    sheet_counts: dict[tuple[int, int, int], int]
    symbol_counts: dict[str, int]
    symbol_orientation_counts: dict[tuple[str, str], int]
    wire_count: int
    diagonal_wire_count: int
    degenerate_wire_count: int
    flag_counts: dict[str, int]
    directive_count: int
    negative_electrical_point_count: int
    electrical_grid_violation_count: int
    unknown_record_count: int

    @property
    def all_flags_are_ground(self) -> bool:
        return bool(self.flag_counts) and set(self.flag_counts) == {"0"}


def decode_donor_bytes(data: bytes) -> tuple[str, str]:
    """Decode UTF-8 donors first, then LTspice's legacy CP1252 donor bytes.

    CP1252 fallback is required for donor values such as ``1µ`` written as the
    single byte ``0xB5``.  Trying UTF-8 first prevents a modern UTF-8 ``µ``
    from becoming the visual corruption ``Âµ``.
    """

    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        return data.decode("cp1252"), "cp1252"


def _parse_int(value: str, *, path: Path, line_number: int, record: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise DonorAscParseError(f"{path}:{line_number}: {record} needs an integer, got {value!r}.") from exc


def _split(raw: str, fields: int, *, path: Path, line_number: int, record: str) -> list[str]:
    parts = raw.split(maxsplit=fields - 1)
    if len(parts) < fields:
        raise DonorAscParseError(f"{path}:{line_number}: {record} has too few fields: {raw!r}")
    return parts


def _point(x: str, y: str, *, path: Path, line_number: int, record: str) -> DonorPoint:
    return DonorPoint(
        _parse_int(x, path=path, line_number=line_number, record=record),
        _parse_int(y, path=path, line_number=line_number, record=record),
    )


def parse_donor_asc(path: str | Path) -> DonorAscDocument:
    """Parse a donor ASC file without imposing router-era limitations.

    Supported records are VERSION, SHEET, WIRE, FLAG, SYMBOL, WINDOW,
    SYMATTR, and TEXT.  Unsupported records are retained in
    ``unknown_records`` for an explicit catalogue decision later.
    """

    document_path = Path(path)
    try:
        raw_bytes = document_path.read_bytes()
    except OSError as exc:
        raise DonorAscParseError(f"Cannot read donor ASC {document_path}: {exc}") from exc
    text, encoding = decode_donor_bytes(raw_bytes)

    version: str | None = None
    sheet: DonorSheet | None = None
    wires: list[DonorWire] = []
    flags: list[DonorFlag] = []
    symbols: list[DonorSymbol] = []
    texts: list[DonorText] = []
    unknown_records: list[DonorUnknownRecord] = []
    current_symbol: DonorSymbol | None = None

    for line_number, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip("\r")
        if not line.strip():
            continue
        keyword = line.split(maxsplit=1)[0].upper()

        if keyword == "VERSION":
            parts = _split(line, 2, path=document_path, line_number=line_number, record="VERSION")
            if version is not None:
                raise DonorAscParseError(f"{document_path}:{line_number}: repeated VERSION record.")
            version = parts[1]
            current_symbol = None
        elif keyword == "SHEET":
            parts = _split(line, 4, path=document_path, line_number=line_number, record="SHEET")
            if sheet is not None:
                raise DonorAscParseError(f"{document_path}:{line_number}: repeated SHEET record.")
            sheet = DonorSheet(
                number=_parse_int(parts[1], path=document_path, line_number=line_number, record="SHEET"),
                width=_parse_int(parts[2], path=document_path, line_number=line_number, record="SHEET"),
                height=_parse_int(parts[3], path=document_path, line_number=line_number, record="SHEET"),
                line_number=line_number,
            )
            current_symbol = None
        elif keyword == "WIRE":
            parts = _split(line, 5, path=document_path, line_number=line_number, record="WIRE")
            wires.append(
                DonorWire(
                    start=_point(parts[1], parts[2], path=document_path, line_number=line_number, record="WIRE"),
                    end=_point(parts[3], parts[4], path=document_path, line_number=line_number, record="WIRE"),
                    line_number=line_number,
                )
            )
            current_symbol = None
        elif keyword == "FLAG":
            parts = _split(line, 4, path=document_path, line_number=line_number, record="FLAG")
            flags.append(
                DonorFlag(
                    point=_point(parts[1], parts[2], path=document_path, line_number=line_number, record="FLAG"),
                    name=parts[3],
                    line_number=line_number,
                )
            )
            current_symbol = None
        elif keyword == "SYMBOL":
            parts = _split(line, 5, path=document_path, line_number=line_number, record="SYMBOL")
            current_symbol = DonorSymbol(
                name=parts[1],
                origin=_point(parts[2], parts[3], path=document_path, line_number=line_number, record="SYMBOL"),
                orientation=parts[4].upper(),
                line_number=line_number,
            )
            symbols.append(current_symbol)
        elif keyword == "WINDOW":
            if current_symbol is None:
                raise DonorAscParseError(f"{document_path}:{line_number}: WINDOW appears before a SYMBOL.")
            parts = _split(line, 6, path=document_path, line_number=line_number, record="WINDOW")
            current_symbol.windows.append(
                DonorWindow(
                    number=_parse_int(parts[1], path=document_path, line_number=line_number, record="WINDOW"),
                    x=_parse_int(parts[2], path=document_path, line_number=line_number, record="WINDOW"),
                    y=_parse_int(parts[3], path=document_path, line_number=line_number, record="WINDOW"),
                    justification=parts[4],
                    font_size=_parse_int(parts[5], path=document_path, line_number=line_number, record="WINDOW"),
                    line_number=line_number,
                )
            )
        elif keyword == "SYMATTR":
            if current_symbol is None:
                raise DonorAscParseError(f"{document_path}:{line_number}: SYMATTR appears before a SYMBOL.")
            parts = _split(line, 3, path=document_path, line_number=line_number, record="SYMATTR")
            attribute = DonorAttribute(key=parts[1], value=parts[2], line_number=line_number)
            current_symbol.attribute_records.append(attribute)
            # LTspice consumes the final occurrence.  Keep all occurrences in
            # attribute_records for evidence while exposing that native result.
            current_symbol.attributes[attribute.key] = attribute.value
        elif keyword == "TEXT":
            parts = _split(line, 6, path=document_path, line_number=line_number, record="TEXT")
            texts.append(
                DonorText(
                    point=_point(parts[1], parts[2], path=document_path, line_number=line_number, record="TEXT"),
                    justification=parts[3],
                    font_size=_parse_int(parts[4], path=document_path, line_number=line_number, record="TEXT"),
                    text=parts[5],
                    line_number=line_number,
                )
            )
            current_symbol = None
        else:
            unknown_records.append(DonorUnknownRecord(keyword=keyword, raw=raw, line_number=line_number))
            current_symbol = None

    if version is None:
        raise DonorAscParseError(f"{document_path} has no VERSION record.")
    if sheet is None:
        raise DonorAscParseError(f"{document_path} has no SHEET record.")
    return DonorAscDocument(
        path=document_path,
        encoding=encoding,
        version=version,
        sheet=sheet,
        wires=wires,
        flags=flags,
        symbols=symbols,
        texts=texts,
        unknown_records=unknown_records,
    )


def load_donor_documents(root: str | Path) -> tuple[DonorAscDocument, ...]:
    """Load every ``.asc`` donor beneath *root* in deterministic path order."""

    donor_root = Path(root)
    if not donor_root.is_dir():
        raise DonorAscParseError(f"Donor root does not exist or is not a directory: {donor_root}")
    paths = tuple(sorted((path for path in donor_root.rglob("*") if path.is_file() and path.suffix.lower() == ".asc"), key=lambda item: item.as_posix()))
    if not paths:
        raise DonorAscParseError(f"Donor root has no .asc files: {donor_root}")
    return tuple(parse_donor_asc(path) for path in paths)


def census_donor_documents(documents: Iterable[DonorAscDocument], *, root: str | Path) -> DonorCorpusCensus:
    """Return explicit corpus facts; no donor capability is inferred silently."""

    prepared = tuple(documents)
    if not prepared:
        raise DonorAscParseError("Cannot census an empty donor document collection.")
    encoding_counts: Counter[str] = Counter()
    version_counts: Counter[str] = Counter()
    sheet_counts: Counter[tuple[int, int, int]] = Counter()
    symbol_counts: Counter[str] = Counter()
    symbol_orientation_counts: Counter[tuple[str, str]] = Counter()
    flag_counts: Counter[str] = Counter()
    wire_count = 0
    diagonal_wire_count = 0
    degenerate_wire_count = 0
    directive_count = 0
    negative_electrical_point_count = 0
    electrical_grid_violation_count = 0
    unknown_record_count = 0

    for document in prepared:
        encoding_counts[document.encoding] += 1
        version_counts[document.version] += 1
        sheet_counts[(document.sheet.number, document.sheet.width, document.sheet.height)] += 1
        wire_count += len(document.wires)
        diagonal_wire_count += len(document.diagonal_wires)
        degenerate_wire_count += sum(wire.is_degenerate for wire in document.wires)
        directive_count += len(document.directives)
        unknown_record_count += len(document.unknown_records)
        for symbol in document.symbols:
            symbol_counts[symbol.name] += 1
            symbol_orientation_counts[(symbol.name, symbol.orientation)] += 1
        for flag in document.flags:
            flag_counts[flag.name] += 1
        points = tuple(document.electrical_points())
        negative_electrical_point_count += sum(point.x < 0 or point.y < 0 for _record, point, _line in points)
        electrical_grid_violation_count += len(document.electrical_grid_violations())

    return DonorCorpusCensus(
        root=Path(root),
        files=tuple(document.path for document in prepared),
        encoding_counts=dict(sorted(encoding_counts.items())),
        version_counts=dict(sorted(version_counts.items())),
        sheet_counts=dict(sorted(sheet_counts.items())),
        symbol_counts=dict(sorted(symbol_counts.items())),
        symbol_orientation_counts=dict(sorted(symbol_orientation_counts.items())),
        wire_count=wire_count,
        diagonal_wire_count=diagonal_wire_count,
        degenerate_wire_count=degenerate_wire_count,
        flag_counts=dict(sorted(flag_counts.items())),
        directive_count=directive_count,
        negative_electrical_point_count=negative_electrical_point_count,
        electrical_grid_violation_count=electrical_grid_violation_count,
        unknown_record_count=unknown_record_count,
    )


def census_donor_root(root: str | Path) -> DonorCorpusCensus:
    """Load and census a donor directory in one read-only operation."""

    donor_root = Path(root)
    return census_donor_documents(load_donor_documents(donor_root), root=donor_root)


def transform_local_offset(point: DonorPoint, orientation: str) -> DonorPoint:
    """Apply LTspice's documented local-symbol orientation transform.

    The formulas operate in screen coordinates where positive Y points down.
    They are used by the catalogue test and the new physical-wire router to
    convert a donor-measured pin offset into a world-coordinate wire endpoint.
    """

    token = orientation.upper()
    if token not in KNOWN_ORIENTATIONS:
        raise DonorAscParseError(
            f"Unsupported LTspice orientation {orientation!r}; expected one of {', '.join(sorted(KNOWN_ORIENTATIONS))}."
        )
    x, y = point.x, point.y
    transforms = {
        "R0": (x, y),
        "R90": (-y, x),
        "R180": (-x, -y),
        "R270": (y, -x),
        "M0": (-x, y),
        "M90": (y, x),
        "M180": (x, -y),
        "M270": (-y, -x),
    }
    return DonorPoint(*transforms[token])


def transform_catalogue_pin(anchor: DonorPoint, local: DonorPoint, orientation: str) -> DonorPoint:
    """Resolve a catalogue-local pin offset to its actual ASC wire endpoint."""

    offset = transform_local_offset(local, orientation)
    return anchor.translate(offset.x, offset.y)
