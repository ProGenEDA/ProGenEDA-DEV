"""Read-only access to an authorized EasyEDA Pro donor source pack.

No native payload is stored in this module.  The caller supplies an EasyEDA
desktop ZIP or an extracted source directory.  We materialize it in a private
cache, extract exact SQLite rows, and retain their hashes as generation
evidence.
"""

from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
from importlib import resources as importlib_resources
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
from typing import Any, Iterator
import zipfile

from .catalogue import CatalogueEntry, DonorSelector


SOURCE_SCHEMA = "progen-easyeda-donor-source/v1"
BUNDLED_SOURCE_FILES = (
    "easyeda-std.elib",
    "blank_template.eprj",
    "manifest.json",
)


class DonorSourceError(ValueError):
    """The supplied source pack cannot prove a requested native packet."""


def bundled_source_pack() -> Path:
    """Return a filesystem directory containing the locked runtime donor set."""

    direct = Path(__file__).resolve().parent / "donors" / "locked_catalogue_v2"
    if all((direct / name).is_file() for name in BUNDLED_SOURCE_FILES):
        return direct
    root = Path(tempfile.gettempdir()) / "progen_easyeda_locked_catalogue_v2"
    root.mkdir(parents=True, exist_ok=True)
    traversable = importlib_resources.files("Easyeda").joinpath(
        "donors",
        "locked_catalogue_v2",
    )
    for name in BUNDLED_SOURCE_FILES:
        destination = root / name
        data = traversable.joinpath(name).read_bytes()
        if not destination.is_file() or destination.read_bytes() != data:
            destination.write_bytes(data)
    return root


@dataclass(frozen=True)
class SourcePaths:
    source_pack: Path
    source_sha256: str
    library_path: Path
    supplemental_library_paths: tuple[Path, ...]
    template_path: Path
    source_version: str | None


@dataclass(frozen=True)
class PinDescriptor:
    number: str
    name: str
    pin_type: str
    x: float
    y: float


@dataclass(frozen=True)
class FootprintPadDescriptor:
    number: str
    identifier: str
    x: float
    y: float
    layer: int
    rotation: float
    shape: object
    hole: object
    through_hole: bool


@dataclass(frozen=True)
class DonorPacket:
    """Exact source rows plus parsed geometry needed by downstream stages."""

    kind: str
    resolved_title: str
    device: dict[str, Any]
    attributes: tuple[dict[str, Any], ...]
    symbol: dict[str, Any]
    footprint: dict[str, Any] | None
    resources: tuple[dict[str, Any], ...]
    pins: tuple[PinDescriptor, ...]
    body_bbox: tuple[float, float, float, float]
    part_name: str
    reference_prefix: str
    footprint_pads: dict[str, tuple[float, float]]
    footprint_pad_ids: dict[str, str]
    footprint_pad_details: dict[str, FootprintPadDescriptor]
    footprint_bbox: tuple[float, float, float, float] | None
    source_hashes: dict[str, str]

    @property
    def pcb_ready(self) -> bool:
        if self.footprint is None:
            return False
        if not self.pins:
            return True
        return all(pin.number in self.footprint_pads for pin in self.pins)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _row_dict(cursor: sqlite3.Cursor, row: sqlite3.Row | tuple[Any, ...]) -> dict[str, Any]:
    return {description[0]: row[index] for index, description in enumerate(cursor.description or [])}


def _stable_json_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _read_json_records(text: str) -> list[list[Any]]:
    records: list[list[Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        parsed = json.loads(line)
        if isinstance(parsed, list) and parsed:
            records.append(parsed)
    return records


def _symbol_geometry(data: str) -> tuple[tuple[PinDescriptor, ...], tuple[float, float, float, float], str, str]:
    records = _read_json_records(data)
    pin_rows: dict[str, list[Any]] = {}
    attributes: dict[str, dict[str, str]] = {}
    part_name = ""
    bbox: tuple[float, float, float, float] | None = None
    reference_prefix = "U"
    for row in records:
        if row[0] == "PART" and len(row) >= 3:
            part_name = str(row[1] or "")
            details = row[2] if isinstance(row[2], dict) else {}
            raw_bbox = details.get("BBOX")
            if isinstance(raw_bbox, list) and len(raw_bbox) == 4:
                bbox = tuple(float(value) for value in raw_bbox)
        elif row[0] == "PIN" and len(row) >= 8:
            pin_rows[str(row[1])] = row
        elif row[0] == "ATTR" and len(row) >= 5:
            parent = str(row[2] or "")
            key = str(row[3] or "")
            value = str(row[4] or "")
            attributes.setdefault(parent, {})[key] = value
            if parent == "" and key == "Designator" and value:
                reference_prefix = "".join(character for character in value if character.isalpha()) or reference_prefix
    pins: list[PinDescriptor] = []
    for identifier, row in pin_rows.items():
        pin_attrs = attributes.get(identifier, {})
        number = pin_attrs.get("NUMBER", identifier)
        name = pin_attrs.get("NAME", number)
        pin_type = pin_attrs.get("Pin Type", "")
        pins.append(PinDescriptor(number=str(number), name=str(name), pin_type=str(pin_type), x=float(row[4]), y=float(row[5])))
    if bbox is None:
        if pins:
            xs = [pin.x for pin in pins]
            ys = [pin.y for pin in pins]
            bbox = (min(xs) - 10, min(ys) - 10, max(xs) + 10, max(ys) + 10)
        else:
            bbox = (-10.0, -10.0, 10.0, 10.0)
    return tuple(pins), bbox, part_name, reference_prefix


def _shape_extents(value: object) -> tuple[float, float]:
    if not isinstance(value, list):
        return 0.0, 0.0
    numbers = [abs(float(item)) for item in value[1:] if isinstance(item, (int, float))]
    if not numbers:
        return 0.0, 0.0
    return numbers[0] / 2.0, (numbers[1] if len(numbers) > 1 else numbers[0]) / 2.0


def _footprint_geometry(
    data: str,
) -> tuple[
    dict[str, tuple[float, float]],
    dict[str, str],
    dict[str, FootprintPadDescriptor],
    tuple[float, float, float, float] | None,
]:
    pads: dict[str, tuple[float, float]] = {}
    identifiers: dict[str, str] = {}
    details: dict[str, FootprintPadDescriptor] = {}
    bounds: list[tuple[float, float, float, float]] = []
    for row in _read_json_records(data):
        if row[0] != "PAD" or len(row) < 8:
            continue
        number = str(row[5] or "").strip()
        if not number:
            continue
        x = float(row[6])
        y = float(row[7])
        layer = int(row[4]) if isinstance(row[4], (int, float)) else 0
        rotation = float(row[8]) if len(row) > 8 and isinstance(row[8], (int, float)) else 0.0
        shape = row[10] if len(row) > 10 else None
        hole = row[11] if len(row) > 11 else None
        half_width, half_height = _shape_extents(shape)
        if half_width == 0 and half_height == 0:
            half_width = half_height = 2.0
        pads[number] = (x, y)
        identifiers[number] = str(row[1])
        details[number] = FootprintPadDescriptor(
            number=number,
            identifier=str(row[1]),
            x=x,
            y=y,
            layer=layer,
            rotation=rotation,
            shape=shape,
            hole=hole,
            through_hole=layer == 12,
        )
        bounds.append((x - half_width, y - half_height, x + half_width, y + half_height))
    bbox = None
    if bounds:
        bbox = (
            min(item[0] for item in bounds),
            min(item[1] for item in bounds),
            max(item[2] for item in bounds),
            max(item[3] for item in bounds),
        )
    return pads, identifiers, details, bbox


class EasyedaDonorSource:
    """Materialize and query an EasyEDA Pro library without mutating it."""

    def __init__(self, source_pack: Path, *, cache_root: Path | None = None):
        self.source_pack = source_pack.expanduser().resolve()
        if not self.source_pack.is_file() and not self.source_pack.is_dir():
            raise DonorSourceError(f"EasyEDA donor source does not exist: {self.source_pack}")
        self.cache_root = cache_root or Path(tempfile.gettempdir()) / "progen_easyeda_source_cache"
        self._paths: SourcePaths | None = None

    def materialize(self) -> SourcePaths:
        if self._paths is not None:
            return self._paths
        if self.source_pack.is_dir():
            self._paths = self._materialize_directory()
        else:
            self._paths = self._materialize_zip()
        return self._paths

    def _materialize_directory(self) -> SourcePaths:
        libraries = sorted(self.source_pack.rglob("easyeda-std.elib"))
        templates = sorted(self.source_pack.rglob("*.eprj"))
        if not libraries:
            raise DonorSourceError("An extracted donor directory must contain easyeda-std.elib.")
        if templates:
            template = templates[0]
        else:
            example_archives = sorted(self.source_pack.rglob("example-projects.zip"))
            if not example_archives:
                raise DonorSourceError(
                    "An extracted donor directory must contain an .eprj project or example-projects.zip."
                )
            source_hash = sha256_file(libraries[0])
            root = self.cache_root / source_hash[:24]
            root.mkdir(parents=True, exist_ok=True)
            template = root / "blank_template.eprj"
            if not template.exists():
                with zipfile.ZipFile(example_archives[0]) as examples:
                    candidate = next(
                        (
                            name
                            for name in examples.namelist()
                            if name.lower().endswith(".eprj") and "quick" in name.lower()
                        ),
                        None,
                    )
                    candidate = candidate or next(
                        (name for name in examples.namelist() if name.lower().endswith(".eprj")),
                        None,
                    )
                    if candidate is None:
                        raise DonorSourceError("The EasyEDA example archive contains no .eprj template.")
                    with closing(examples.open(candidate)) as project, template.open("wb") as output:
                        shutil.copyfileobj(project, output, length=1024 * 1024)
        version: str | None = None
        package_files = sorted(self.source_pack.rglob("resources/app/package.json"))
        if package_files:
            try:
                version = str(json.loads(package_files[0].read_text(encoding="utf-8")).get("version") or "") or None
            except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                version = None
        return SourcePaths(
            source_pack=self.source_pack,
            source_sha256=sha256_file(libraries[0]),
            library_path=libraries[0],
            supplemental_library_paths=self._supplemental_library_paths(),
            template_path=template,
            source_version=version,
        )

    def _materialize_zip(self) -> SourcePaths:
        source_hash = sha256_file(self.source_pack)
        root = self.cache_root / source_hash[:24]
        root.mkdir(parents=True, exist_ok=True)
        library = root / "easyeda-std.elib"
        template = root / "blank_template.eprj"
        with zipfile.ZipFile(self.source_pack) as archive:
            names = archive.namelist()
            library_name = next((name for name in names if name.endswith("/assets/db/easyeda-std.elib")), None)
            examples_name = next((name for name in names if name.endswith("/assets/db/example-projects.zip")), None)
            package_name = next((name for name in names if name.endswith("/resources/app/package.json")), None)
            if library_name is None or examples_name is None:
                raise DonorSourceError("The source ZIP has no EasyEDA Pro standard library/examples database.")
            if not library.exists():
                with closing(archive.open(library_name)) as source, library.open("wb") as output:
                    shutil.copyfileobj(source, output, length=1024 * 1024)
            if not template.exists():
                with closing(archive.open(examples_name)) as source, zipfile.ZipFile(source) as examples:
                    candidate = next((name for name in examples.namelist() if name.lower().endswith(".eprj") and "quick" in name.lower()), None)
                    candidate = candidate or next((name for name in examples.namelist() if name.lower().endswith(".eprj")), None)
                    if candidate is None:
                        raise DonorSourceError("The EasyEDA example archive contains no .eprj template.")
                    with closing(examples.open(candidate)) as project, template.open("wb") as output:
                        shutil.copyfileobj(project, output, length=1024 * 1024)
            version: str | None = None
            if package_name is not None:
                try:
                    version = str(json.loads(archive.read(package_name)).get("version") or "") or None
                except (json.JSONDecodeError, UnicodeDecodeError):
                    version = None
        return SourcePaths(
            source_pack=self.source_pack,
            source_sha256=source_hash,
            library_path=library,
            supplemental_library_paths=self._supplemental_library_paths(),
            template_path=template,
            source_version=version,
        )

    def _connect_library(self) -> sqlite3.Connection:
        paths = self.materialize()
        connection = sqlite3.connect(f"file:{paths.library_path}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _supplemental_library_paths() -> tuple[Path, ...]:
        candidate = Path(__file__).resolve().parent / "donors" / "system_expansion_v2.elib"
        return (candidate,) if candidate.is_file() else ()

    def _library_paths(self) -> tuple[Path, ...]:
        paths = self.materialize()
        return (paths.library_path, *paths.supplemental_library_paths)

    def resolve(self, entry: CatalogueEntry) -> DonorPacket:
        """Resolve one catalogue entry to exact source records or fail closed."""

        resolved: tuple[
            dict[str, Any],
            list[dict[str, Any]],
            dict[str, Any],
            dict[str, Any] | None,
            list[dict[str, Any]],
        ] | None = None
        for library_path in self._library_paths():
            with sqlite3.connect(f"file:{library_path}?mode=ro", uri=True) as connection:
                connection.row_factory = sqlite3.Row
                try:
                    device = self._find_device(connection, entry)
                except DonorSourceError:
                    continue
                device_uuid = str(device["uuid"])
                attributes = self._attributes(connection, device_uuid)
                attribute_map = {str(row["key"]): str(row["value"]) for row in attributes}
                symbol_uuid = attribute_map.get("Symbol")
                if not symbol_uuid:
                    raise DonorSourceError(
                        f"{entry.kind} donor {device['title']!r} has no source Symbol binding."
                    )
                symbol = self._component_row(connection, symbol_uuid, entry.kind, "symbol")
                footprint: dict[str, Any] | None = None
                footprint_uuid = attribute_map.get("Footprint")
                if footprint_uuid:
                    footprint = self._component_row(
                        connection, footprint_uuid, entry.kind, "footprint"
                    )
                if entry.selector.pcb_required and footprint is None:
                    raise DonorSourceError(
                        f"{entry.kind} donor {device['title']!r} has no source Footprint binding."
                    )
                resources = self._resource_rows(connection, attribute_map.values())
                resolved = device, attributes, symbol, footprint, resources
                break
        if resolved is None:
            tried = ", ".join(entry.selector.titles)
            raise DonorSourceError(
                f"{entry.kind} has no exact donor device in the authorized source libraries; "
                f"tried: {tried}."
            )
        device, attributes, symbol, footprint, resources = resolved
        pins, bbox, part_name, donor_prefix = _symbol_geometry(str(symbol["dataStr"]))
        if not entry.selector.terminal and not part_name:
            raise DonorSourceError(f"{entry.kind} donor {device['title']!r} has no native symbol PART record.")
        pads, pad_ids, pad_details, footprint_bbox = (
            _footprint_geometry(str(footprint["dataStr"]))
            if footprint is not None
            else ({}, {}, {}, None)
        )
        hashes = {
            "device": _stable_json_hash(device),
            "attributes": _stable_json_hash(attributes),
            "symbol": hashlib.sha256(str(symbol["dataStr"]).encode("utf-8")).hexdigest(),
            "footprint": hashlib.sha256(str(footprint["dataStr"]).encode("utf-8")).hexdigest() if footprint is not None else "",
            "resources": _stable_json_hash(resources),
        }
        return DonorPacket(
            kind=entry.kind,
            resolved_title=str(device["title"]),
            device=device,
            attributes=tuple(attributes),
            symbol=symbol,
            footprint=footprint,
            resources=tuple(resources),
            pins=pins,
            body_bbox=bbox,
            part_name=part_name,
            reference_prefix=donor_prefix or entry.reference_prefix,
            footprint_pads=pads,
            footprint_pad_ids=pad_ids,
            footprint_pad_details=pad_details,
            footprint_bbox=footprint_bbox,
            source_hashes=hashes,
        )

    def resolve_terminal_port(self, *, direction: str = "in") -> DonorPacket:
        """Resolve the real source net-port device used by terminal routing."""

        normalized = direction.strip().lower()
        if normalized not in {"in", "out"}:
            raise DonorSourceError(f"Unsupported native terminal direction {direction!r}.")
        title = f"netport-{normalized}"
        entry = CatalogueEntry(
            kind=f"NETPORT_{normalized.upper()}",
            aliases=(),
            reference_prefix="PORT",
            selector=DonorSelector((title,), terminal=True, pcb_required=False),
            category="terminal",
            value_rule="display_text",
            default_value=title,
        )
        return self.resolve(entry)

    @staticmethod
    def _find_device(connection: sqlite3.Connection, entry: CatalogueEntry) -> dict[str, Any]:
        for title in entry.selector.titles:
            cursor = connection.execute(
                "SELECT * FROM devices WHERE lower(title) = lower(?) OR lower(display_title) = lower(?) LIMIT 1",
                (title, title),
            )
            row = cursor.fetchone()
            if row is not None:
                return dict(row)
        tried = ", ".join(entry.selector.titles)
        raise DonorSourceError(f"{entry.kind} has no exact donor device in this source pack; tried: {tried}.")

    @staticmethod
    def _attributes(connection: sqlite3.Connection, device_uuid: str) -> list[dict[str, Any]]:
        cursor = connection.execute("SELECT * FROM attributes WHERE device_uuid = ? ORDER BY key", (device_uuid,))
        return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _component_row(connection: sqlite3.Connection, uuid: str, kind: str, role: str) -> dict[str, Any]:
        row = connection.execute("SELECT * FROM components WHERE uuid = ?", (uuid,)).fetchone()
        if row is None:
            raise DonorSourceError(f"{kind} {role} {uuid!r} is absent from the donor source pack.")
        return dict(row)

    @staticmethod
    def _resource_rows(connection: sqlite3.Connection, values: Iterator[str] | Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in values:
            candidate = str(value)
            if candidate in seen:
                continue
            seen.add(candidate)
            row = connection.execute("SELECT * FROM resources WHERE hash = ?", (candidate,)).fetchone()
            if row is not None:
                rows.append(dict(row))
        return rows

    def provenance(self) -> dict[str, Any]:
        paths = self.materialize()
        return {
            "schema": SOURCE_SCHEMA,
            "source_pack": str(paths.source_pack),
            "source_sha256": paths.source_sha256,
            "source_version": paths.source_version,
            "library_sha256": sha256_file(paths.library_path),
            "supplemental_libraries": [
                {"path": str(path), "sha256": sha256_file(path)}
                for path in paths.supplemental_library_paths
            ],
            "template_sha256": sha256_file(paths.template_path),
            "raw_source_embedded": bool(paths.supplemental_library_paths),
        }
