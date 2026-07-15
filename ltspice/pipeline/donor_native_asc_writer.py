"""Donor-native LTspice ``.asc`` writer.

This module is deliberately separate from :mod:`ltspice_asc_writer`, which is
the older ProGenEDA prototype writer.  The prototype writes project-local
``progeneda_*.asy`` symbols, optional model libraries, and named FLAG based
terminal fallbacks.  None of those records are permitted here.

The only records this writer emits are the record families observed in the
supplied native LTspice donors:

* ``Version 4.1`` and the native ``SHEET 1 <width> <height>`` form
  (the donor baseline is 880 by 680; the physical router may grow the sheet);
* direct ``WIRE`` segments (including valid donor-style diagonal segments);
* ``FLAG X Y 0`` ground anchors only;
* stock-library ``SYMBOL`` records with ``WINDOW`` and ``SYMATTR`` records;
* ``TEXT ... !.analysis`` directives.

The recipe accepted by this module is an *internal generator recipe*, not a
replacement for the shared ProGenEDA main input JSON.  It gives the placement,
property, and routing stages a deterministic, testable native target while the
canonical-input adapter is being rebuilt around the donor-native catalogue.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from pathlib import Path
import re
from typing import Any

from ltspice.catalogues.ltspice_main_catalogue_loader import (
    NativeCatalogue,
    NativeCatalogueError,
    load_native_catalogue,
)


NATIVE_RECIPE_SCHEMA = "progen-ltspice-native-recipe/v1"
ASC_VERSION = "4.1"
SHEET_NUMBER = 1
SHEET_WIDTH = 880
SHEET_HEIGHT = 680

_SAFE_REFERENCE = re.compile(r"^[A-Za-z][A-Za-z0-9_.$-]*$")
_SAFE_ATTRIBUTE_VALUE = re.compile(r"^[^\r\n\x00]*$")
_SAFE_DIRECTIVE = re.compile(r"^\.[^\r\n\x00]*$")
_FORBIDDEN_DIRECTIVE_TOKENS = frozenset({".include", ".inc", ".lib", ".model", ".subckt", ".ends"})
_ORIENTATION_TRANSFORMS: dict[str, tuple[int, int, int, int]] = {
    # ``(a, b, c, d)`` means ``(a*x + b*y, c*x + d*y)``.  LTspice ASC uses a
    # screen coordinate system where +Y points down; these formulas match the
    # stock donor transforms and the catalogue's local pin coordinates.
    "R0": (1, 0, 0, 1),
    "R90": (0, -1, 1, 0),
    "R180": (-1, 0, 0, -1),
    "R270": (0, 1, -1, 0),
    "M0": (-1, 0, 0, 1),
    "M90": (0, 1, 1, 0),
    "M180": (1, 0, 0, -1),
    "M270": (0, -1, -1, 0),
}


class DonorNativeAscError(ValueError):
    """A recipe would create a non-native or unsafe LTspice schematic."""


@dataclass(frozen=True)
class NativeSymbol:
    """A validated stock-symbol instance ready for ASC serialization."""

    type_id: str
    symbol: str
    ref: str
    x: int
    y: int
    orientation: str
    windows: tuple[tuple[int, str], ...]
    attributes: tuple[tuple[str, str], ...]
    pin_points: tuple[tuple[str, tuple[int, int]], ...]


@dataclass(frozen=True)
class NativeDirective:
    """A native LTspice ``TEXT`` analysis directive."""

    x: int
    y: int
    text: str


@dataclass(frozen=True)
class NativeAscWriteResult:
    """The one and only generated artifact from the donor-native writer."""

    asc_path: Path
    sha256: str
    size_bytes: int
    component_count: int
    wire_count: int
    ground_count: int
    directive_count: int


def _as_mapping(value: object, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DonorNativeAscError(f"{context} must be an object.")
    return value


def _as_sequence(value: object, context: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise DonorNativeAscError(f"{context} must be an array.")
    return value


def _as_int(value: object, context: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise DonorNativeAscError(f"{context} must be an integer.")
    return value


def _as_text(value: object, context: str) -> str:
    if not isinstance(value, str):
        raise DonorNativeAscError(f"{context} must be text.")
    return value


def _point(value: object, context: str, *, grid: int) -> tuple[int, int]:
    items = _as_sequence(value, context)
    if len(items) != 2:
        raise DonorNativeAscError(f"{context} must have exactly two coordinates.")
    x = _as_int(items[0], f"{context}[0]")
    y = _as_int(items[1], f"{context}[1]")
    if x % grid or y % grid:
        raise DonorNativeAscError(f"{context} must use the native {grid}-unit LTspice grid.")
    return x, y


def _check_plain_text(value: str, context: str) -> str:
    if not _SAFE_ATTRIBUTE_VALUE.fullmatch(value):
        raise DonorNativeAscError(f"{context} must not contain a newline or NUL byte.")
    return value


def _format_attribute_value(value: str) -> str:
    """Preserve native empty attributes without inventing a JSON escaping rule."""

    return '""' if value == "" else value


def _transform_local(local: tuple[int, int], orientation: str) -> tuple[int, int]:
    try:
        a, b, c, d = _ORIENTATION_TRANSFORMS[orientation]
    except KeyError as exc:  # catalogue loader should make this unreachable.
        raise DonorNativeAscError(f"Unsupported native orientation {orientation!r}.") from exc
    x, y = local
    return a * x + b * y, c * x + d * y


def _pin_points(component: Mapping[str, Any], *, x: int, y: int, orientation: str) -> tuple[tuple[str, tuple[int, int]], ...]:
    points: list[tuple[str, tuple[int, int]]] = []
    pins = _as_mapping(component["pin_model"], "catalogue.pin_model")["pins"]
    for key, raw_pin in _as_mapping(pins, "catalogue.pin_model.pins").items():
        pin = _as_mapping(raw_pin, f"catalogue.pin_model.pins.{key}")
        local = pin["local"]
        if not isinstance(local, list) or len(local) != 2:  # defensive; loader already validates it.
            raise DonorNativeAscError(f"Catalogue pin {key!r} has no local point.")
        dx, dy = _transform_local((int(local[0]), int(local[1])), orientation)
        points.append((str(pin["number"]), (x + dx, y + dy)))
    return tuple(points)


def _parse_property_records(
    raw_properties: object,
    *,
    component: Mapping[str, Any],
    ref: str,
    context: str,
) -> tuple[tuple[tuple[int, str], ...], tuple[tuple[str, str], ...]]:
    """Map catalogue-approved property keys to native ASC records.

    ``SpiceLine`` component parameters are deliberately not free-form.  They
    are constructed from exact donor-backed keys such as ``spice_line.tol`` or
    ``spice_line.Rser`` only.
    """

    source = _as_mapping(raw_properties or {}, f"{context}.properties")
    approved = _as_mapping(component["properties"], f"{context}.catalogue.properties")
    supplied: dict[str, str] = {}
    for name, raw_value in source.items():
        if not isinstance(name, str):
            raise DonorNativeAscError(f"{context}.properties has a non-text key.")
        if name not in approved:
            raise DonorNativeAscError(
                f"{context}.properties.{name} is not a donor-supported property for this component."
            )
        property_definition = _as_mapping(approved[name], f"{context}.catalogue.properties.{name}")
        if property_definition.get("support_state") != "donor_proven":
            raise DonorNativeAscError(
                f"{context}.properties.{name} is not donor-proven and cannot be emitted yet."
            )
        value = _check_plain_text(_as_text(raw_value, f"{context}.properties.{name}"), f"{context}.properties.{name}")
        supplied[name] = value

    if "reference" in supplied and supplied["reference"] != ref:
        raise DonorNativeAscError(f"{context}.properties.reference must match {context}.ref.")

    windows: list[tuple[int, str]] = []
    attributes: list[tuple[str, str]] = [("InstName", ref)]
    native_attribute_values: dict[str, str] = {}
    spice_line_parts: list[str] = []

    # Iterate in catalogue order so generated native text stays deterministic.
    for name, definition_raw in approved.items():
        if name == "reference" or name not in supplied:
            continue
        definition = _as_mapping(definition_raw, f"{context}.catalogue.properties.{name}")
        record = _as_text(definition["record"], f"{context}.catalogue.properties.{name}.record")
        value = supplied[name]
        if record.startswith("WINDOW "):
            try:
                number = int(record.split(maxsplit=1)[1])
            except ValueError as exc:  # defensive catalogue fault
                raise DonorNativeAscError(f"Catalogue record {record!r} is not a native WINDOW record.") from exc
            fields = value.split()
            if len(fields) != 4:
                raise DonorNativeAscError(
                    f"{context}.properties.{name} must be '<x> <y> <justification> <font_size>'."
                )
            try:
                int(fields[0])
                int(fields[1])
                int(fields[3])
            except ValueError as exc:
                raise DonorNativeAscError(f"{context}.properties.{name} has an invalid native WINDOW value.") from exc
            windows.append((number, value))
        elif record == "SYMATTR SpiceLine":
            if not name.startswith("spice_line."):
                raise DonorNativeAscError(f"Catalogue property {name!r} cannot safely form SpiceLine.")
            parameter = name.rsplit(".", 1)[1]
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", parameter):
                raise DonorNativeAscError(f"Catalogue SpiceLine parameter {parameter!r} is unsafe.")
            if not value or any(character.isspace() for character in value):
                raise DonorNativeAscError(f"{context}.properties.{name} must be one native scalar token.")
            spice_line_parts.append(f"{parameter}={value}")
        elif record.startswith("SYMATTR "):
            attribute = record.split(maxsplit=1)[1]
            if attribute == "InstName":
                raise DonorNativeAscError(f"{context}.properties.reference is the only InstName entry.")
            previous = native_attribute_values.get(attribute)
            if previous is not None:
                raise DonorNativeAscError(
                    f"{context} supplies multiple donor properties for native {attribute}: {previous!r} and {value!r}."
                )
            native_attribute_values[attribute] = value
        else:  # defensive catalogue fault
            raise DonorNativeAscError(f"Catalogue property {name!r} has unsupported native record {record!r}.")

    if spice_line_parts:
        native_attribute_values["SpiceLine"] = " ".join(spice_line_parts)
    for attribute in ("Value", "Value2", "SpiceLine"):
        if attribute in native_attribute_values:
            attributes.append((attribute, native_attribute_values[attribute]))
    # A future donor-backed attribute may be added to the catalogue.  Do not
    # silently discard it; append it after known native attribute ordering.
    for attribute, value in native_attribute_values.items():
        if attribute not in {"Value", "Value2", "SpiceLine"}:
            attributes.append((attribute, value))
    return tuple(windows), tuple(attributes)


def _parse_symbol(
    raw: object,
    *,
    index: int,
    catalogue: NativeCatalogue,
) -> NativeSymbol:
    source = _as_mapping(raw, f"components[{index}]")
    if "type" not in source:
        raise DonorNativeAscError(f"components[{index}] requires a catalogue component type.")
    try:
        type_id = catalogue.resolve_type_id(source["type"])
        component = catalogue.get(type_id)
    except NativeCatalogueError as exc:
        raise DonorNativeAscError(str(exc)) from exc
    if type_id == "GROUND":
        raise DonorNativeAscError("GROUND is emitted only through ground_flags as native FLAG X Y 0.")

    ref = _as_text(source.get("ref"), f"components[{index}].ref")
    if not _SAFE_REFERENCE.fullmatch(ref):
        raise DonorNativeAscError(f"components[{index}].ref {ref!r} is not a safe native InstName.")
    expected_prefix = str(_as_mapping(component["native"], f"components[{index}].native").get("prefix", ""))
    if expected_prefix and not ref.upper().startswith(expected_prefix.upper()):
        raise DonorNativeAscError(
            f"components[{index}].ref {ref!r} must use the native {expected_prefix!r} reference prefix."
        )
    x, y = _point(source.get("at"), f"components[{index}].at", grid=catalogue.grid)
    orientation = _as_text(source.get("orientation", component["default_orientation"]), f"components[{index}].orientation").upper()
    if orientation not in component["legal_orientations"]:
        raise DonorNativeAscError(
            f"components[{index}].orientation {orientation!r} is not donor-proven for {type_id}."
        )
    windows, attributes = _parse_property_records(
        source.get("properties", {}), component=component, ref=ref, context=f"components[{index}]"
    )
    native = _as_mapping(component["native"], f"components[{index}].native")
    return NativeSymbol(
        type_id=type_id,
        symbol=_as_text(native["symbol"], f"components[{index}].native.symbol"),
        ref=ref,
        x=x,
        y=y,
        orientation=orientation,
        windows=windows,
        attributes=attributes,
        pin_points=_pin_points(component, x=x, y=y, orientation=orientation),
    )


def _parse_wire(raw: object, *, index: int, grid: int) -> tuple[tuple[int, int], tuple[int, int]]:
    values = _as_sequence(raw, f"wires[{index}]")
    if len(values) == 4:
        start = _point(values[:2], f"wires[{index}][0:2]", grid=grid)
        end = _point(values[2:], f"wires[{index}][2:4]", grid=grid)
    elif len(values) == 2:
        start = _point(values[0], f"wires[{index}][0]", grid=grid)
        end = _point(values[1], f"wires[{index}][1]", grid=grid)
    else:
        raise DonorNativeAscError(f"wires[{index}] must be [x1, y1, x2, y2] or [[x1, y1], [x2, y2]].")
    if start == end:
        raise DonorNativeAscError(f"wires[{index}] is zero-length.")
    # Do not restrict to orthogonal lines: lca2.asc proves diagonal native
    # WIRE records.  Routing may prefer orthogonal routes later, but the ASC
    # writer must faithfully represent all direct native segments.
    return start, end


def _parse_directive(raw: object, *, index: int, grid: int) -> NativeDirective:
    source = _as_mapping(raw, f"directives[{index}]")
    x, y = _point(source.get("at"), f"directives[{index}].at", grid=grid)
    text = _as_text(source.get("text"), f"directives[{index}].text")
    if not _SAFE_DIRECTIVE.fullmatch(text):
        raise DonorNativeAscError(f"directives[{index}].text must be one LTspice directive beginning with '.'.")
    command = text.split(maxsplit=1)[0].lower()
    if command in _FORBIDDEN_DIRECTIVE_TOKENS:
        raise DonorNativeAscError(
            f"directives[{index}].text uses {command}, which would require a non-donor-native model/library path."
        )
    return NativeDirective(x=x, y=y, text=text)


def _validate_wiring(
    symbols: Sequence[NativeSymbol],
    wires: Sequence[tuple[tuple[int, int], tuple[int, int]]],
    ground_flags: Sequence[tuple[int, int]],
) -> None:
    """Require every registered electrical pin to join a physical segment.

    This is intentionally conservative: a pin needs to be an endpoint of a
    direct wire rather than merely crossed by one.  It prevents the old named
    FLAG / virtual-terminal shortcut from masquerading as routed connectivity.
    Ground is the one native global-net construct and may be attached at a
    physical wire endpoint.
    """

    endpoints = {point for wire in wires for point in wire}
    for symbol in symbols:
        for pin_number, point in symbol.pin_points:
            if point not in endpoints:
                raise DonorNativeAscError(
                    f"{symbol.ref}.{pin_number} at {point} has no physical WIRE endpoint; named terminal fallbacks are forbidden."
                )
    for point in ground_flags:
        if point not in endpoints:
            raise DonorNativeAscError(
                f"ground FLAG at {point} must terminate a physical WIRE rather than stand in for a terminal."
            )


def _validate_sheet(source: Mapping[str, Any]) -> tuple[int, int, int]:
    raw_sheet = source.get("sheet", {"number": SHEET_NUMBER, "width": SHEET_WIDTH, "height": SHEET_HEIGHT})
    sheet = _as_mapping(raw_sheet, "sheet")
    number = _as_int(sheet.get("number", SHEET_NUMBER), "sheet.number")
    width = _as_int(sheet.get("width", SHEET_WIDTH), "sheet.width")
    height = _as_int(sheet.get("height", SHEET_HEIGHT), "sheet.height")
    # Every supplied donor uses sheet one and the 880×680 baseline, but the
    # ASC grammar also permits a larger visible sheet. A 43-component
    # physical-wire fixture cannot honestly be forced into the smallest donor
    # canvas, so retain the native record form while making the bounds explicit.
    if number != SHEET_NUMBER:
        raise DonorNativeAscError(
            f"Donor-native mode writes SHEET {SHEET_NUMBER}; got sheet number {number}."
        )
    if width <= 0 or height <= 0:
        raise DonorNativeAscError("sheet.width and sheet.height must be positive native ASC dimensions.")
    return number, width, height


def _validated_recipe(
    recipe: Mapping[str, Any], *, catalogue: NativeCatalogue
) -> tuple[
    tuple[NativeSymbol, ...],
    tuple[tuple[tuple[int, int], tuple[int, int]], ...],
    tuple[tuple[int, int], ...],
    tuple[NativeDirective, ...],
]:
    if recipe.get("schema") != NATIVE_RECIPE_SCHEMA:
        raise DonorNativeAscError(f"recipe.schema must be {NATIVE_RECIPE_SCHEMA!r}.")
    _validate_sheet(recipe)
    raw_components = _as_sequence(recipe.get("components"), "components")
    if not raw_components:
        raise DonorNativeAscError("components must not be empty.")
    if len(raw_components) > catalogue.max_components_per_circuit:
        raise DonorNativeAscError(
            f"components has {len(raw_components)} entries, above the donor-native cap of {catalogue.max_components_per_circuit}."
        )
    symbols = tuple(_parse_symbol(item, index=index, catalogue=catalogue) for index, item in enumerate(raw_components))
    refs = [symbol.ref.upper() for symbol in symbols]
    if len(set(refs)) != len(refs):
        raise DonorNativeAscError("components repeat a native InstName reference.")

    raw_wires = _as_sequence(recipe.get("wires"), "wires")
    if not raw_wires:
        raise DonorNativeAscError("wires must not be empty; no terminal fallback is available in donor-native mode.")
    wires = tuple(_parse_wire(item, index=index, grid=catalogue.grid) for index, item in enumerate(raw_wires))

    raw_grounds = _as_sequence(recipe.get("ground_flags", []), "ground_flags")
    ground_flags = tuple(_point(item, f"ground_flags[{index}]", grid=catalogue.grid) for index, item in enumerate(raw_grounds))
    if len(set(ground_flags)) != len(ground_flags):
        raise DonorNativeAscError("ground_flags repeats a native FLAG point.")

    raw_directives = _as_sequence(recipe.get("directives", []), "directives")
    directives = tuple(_parse_directive(item, index=index, grid=catalogue.grid) for index, item in enumerate(raw_directives))
    _validate_wiring(symbols, wires, ground_flags)
    return symbols, wires, ground_flags, directives


def render_donor_native_asc(
    recipe: Mapping[str, Any], *, catalogue: NativeCatalogue | None = None
) -> bytes:
    """Validate an internal recipe and return canonical CP1252 native ASC bytes.

    CP1252 is intentional.  Several real donor files contain the LTspice
    micro glyph (``µ`` as byte ``0xB5``); emitting it in CP1252 keeps generated
    values visually and byte-semantically consistent with those donors.
    """

    active_catalogue = catalogue or load_native_catalogue()
    source = _as_mapping(recipe, "recipe")
    symbols, wires, ground_flags, directives = _validated_recipe(source, catalogue=active_catalogue)
    sheet_number, sheet_width, sheet_height = _validate_sheet(source)

    lines = [f"Version {ASC_VERSION}", f"SHEET {sheet_number} {sheet_width} {sheet_height}"]
    for start, end in wires:
        lines.append(f"WIRE {start[0]} {start[1]} {end[0]} {end[1]}")
    for x, y in ground_flags:
        lines.append(f"FLAG {x} {y} 0")
    for symbol in symbols:
        lines.append(f"SYMBOL {symbol.symbol} {symbol.x} {symbol.y} {symbol.orientation}")
        for number, fields in symbol.windows:
            lines.append(f"WINDOW {number} {fields}")
        for name, value in symbol.attributes:
            lines.append(f"SYMATTR {name} {_format_attribute_value(value)}")
    for directive in directives:
        lines.append(f"TEXT {directive.x} {directive.y} Left 2 !{directive.text}")
    try:
        return ("\n".join(lines) + "\n").encode("cp1252")
    except UnicodeEncodeError as exc:
        raise DonorNativeAscError(
            "Donor-native ASC output is CP1252; a supplied property or directive contains an unsupported character."
        ) from exc


def write_donor_native_asc(
    recipe: Mapping[str, Any], path: str | Path, *, catalogue: NativeCatalogue | None = None
) -> NativeAscWriteResult:
    """Write exactly one native ``.asc`` file and never create ``.asy``/``.lib`` assets."""

    target = Path(path)
    if target.suffix.lower() != ".asc":
        raise DonorNativeAscError(f"Native schematic output must end in .asc, got {target.name!r}.")
    payload = render_donor_native_asc(recipe, catalogue=catalogue)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    active_catalogue = catalogue or load_native_catalogue()
    symbols, wires, ground_flags, directives = _validated_recipe(_as_mapping(recipe, "recipe"), catalogue=active_catalogue)
    return NativeAscWriteResult(
        asc_path=target,
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        component_count=len(symbols),
        wire_count=len(wires),
        ground_count=len(ground_flags),
        directive_count=len(directives),
    )


def donor_native_rc_pulse_recipe() -> dict[str, Any]:
    """Return a structured, stock-symbol RC pulse fixture derived from Draft7.

    The layout has a direct wire attached to every electrical pin; the return
    wire reaches a single physical ground FLAG.  It is useful as the first
    real native-generator smoke target, not as a special-case renderer.
    """

    return deepcopy(
        {
            "schema": NATIVE_RECIPE_SCHEMA,
            "circuit_id": "DONOR_NATIVE_RC_PULSE",
            "sheet": {"number": 1, "width": 880, "height": 680},
            "components": [
                {
                    "type": "VOLTAGE_SOURCE",
                    "ref": "V1",
                    "at": [208, -16],
                    "orientation": "R0",
                    "properties": {
                        "window.123": "0 0 Left 0",
                        "window.39": "0 0 Left 0",
                        "value.pulse": "PULSE(0 5 0 1u 1u 0.5m 1m 0)",
                    },
                },
                {
                    "type": "RESISTOR",
                    "ref": "R1",
                    "at": [432, -16],
                    "orientation": "R90",
                    "properties": {"value": "1k"},
                },
                {
                    "type": "CAPACITOR",
                    "ref": "C1",
                    "at": [448, 0],
                    "orientation": "R0",
                    "properties": {"value": "1µ"},
                },
            ],
            "wires": [
                [336, 0, 208, 0],
                [464, 0, 416, 0],
                [464, 80, 464, 64],
                [464, 80, 208, 80],
                [208, 96, 208, 80],
            ],
            "ground_flags": [[208, 96]],
            "directives": [{"at": [224, 128], "text": ".tran 0 10ms 0.1u 1"}],
        }
    )
