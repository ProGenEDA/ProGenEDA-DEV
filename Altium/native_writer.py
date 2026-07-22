"""Native ASCII Altium writer consuming only completed pipeline contracts."""

from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .ir import AltiumCircuit, AltiumComponent
from .pipeline_contracts import (
    ComponentSelection,
    PipelineError,
    PlacedDesign,
    RoutingPlan,
    expected_physical_contract,
)
from .project_descriptor import render_project_descriptor
from .source_catalogue import Point, SourceCatalogue, SourceTemplate
from .wire_maker import WireMakerResult


NATIVE_WRITE_SCHEMA = "progen-altium-native-write/v2"
_UNSAFE_TEXT = re.compile(r"[|\r\n\x00]")
_COORDINATE_KEY = re.compile(r"^(?:LOCATION|CORNER)\.(X|Y)$|^([XY])\d+$")


class NativeWriteError(PipelineError):
    """A completed stage contract cannot be serialized into native source records."""


@dataclass(frozen=True)
class NativeWriteResult:
    project_directory: Path
    project_file: Path
    schematic_file: Path
    expected_contract: dict[str, Any]
    emitted_record_count: int
    sheet_width_ticks: int
    sheet_height_ticks: int

    def json(self) -> dict[str, Any]:
        return {
            "schema": NATIVE_WRITE_SCHEMA,
            "project_directory": str(self.project_directory),
            "project_file": str(self.project_file),
            "schematic_file": str(self.schematic_file),
            "emitted_record_count": self.emitted_record_count,
            "sheet_width_ticks": self.sheet_width_ticks,
            "sheet_height_ticks": self.sheet_height_ticks,
        }


def _clean_text(value: object, field: str) -> str:
    text = str(value).strip()
    if not text:
        raise NativeWriteError(f"{field} must not be empty.")
    if _UNSAFE_TEXT.search(text):
        raise NativeWriteError(f"{field} contains an unsupported native record delimiter.")
    return text


def _field(record: str, name: str) -> str | None:
    match = re.search(rf"\|{re.escape(name)}=([^|]*)", record)
    return match.group(1) if match else None


def _replace_field(record: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\|{re.escape(name)}=)[^|]*")
    if not pattern.search(record):
        return record
    return pattern.sub(lambda match: f"{match.group(1)}{value}", record)


def _set_field(record: str, name: str, value: str) -> str:
    if _field(record, name) is not None:
        return _replace_field(record, name, value)
    return f"{record}|{name}={value}"


def _coordinate_axis(key: str) -> str | None:
    match = _COORDINATE_KEY.match(key)
    if not match:
        return None
    return match.group(1) or match.group(2)


def _translate_record_coordinates(record: str, dx: int, dy: int) -> str:
    if dx % 2 or dy % 2:
        raise NativeWriteError("Source templates may only be translated by whole document units.")
    translated: list[str] = []
    for token in record.split("|"):
        if "=" not in token:
            translated.append(token)
            continue
        key, value = token.split("=", 1)
        axis = _coordinate_axis(key)
        if axis is None:
            translated.append(token)
            continue
        try:
            delta = dx // 2 if axis == "X" else dy // 2
            translated.append(f"{key}={int(value) + delta}")
        except ValueError:
            translated.append(token)
    return "|".join(translated)


def _replace_owner_indexes(record: str, owner_delta: int) -> str:
    value = _field(record, "OWNERINDEX")
    if value is None:
        return record
    try:
        owner = int(value)
    except ValueError:
        return record
    if owner < 0:
        return record
    return _replace_field(record, "OWNERINDEX", str(owner + owner_delta))


def _rewrite_component_records(
    template: SourceTemplate,
    component: AltiumComponent,
    *,
    owner_index: int,
    target_root: Point,
    index_start: int,
) -> tuple[tuple[str, ...], int]:
    reference = _clean_text(component.reference, "component reference")
    value = _clean_text(component.value, f"value for {reference}")
    dx = target_root.x - template.root_location.x
    dy = target_root.y - template.root_location.y
    owner_delta = owner_index - template.source_owner_index
    index_map: dict[str, str] = {}
    next_index = index_start
    records: list[str] = []
    for source_record_index, source_record in enumerate(template.records):
        record = _replace_owner_indexes(source_record, owner_delta)
        source_owner = _field(source_record, "OWNERINDEX")
        if source_record_index == 0 or source_owner == str(template.source_owner_index):
            record = _translate_record_coordinates(record, dx, dy)
        source_index = _field(source_record, "INDEXINSHEET")
        if source_index is not None:
            replacement = index_map.get(source_index)
            if replacement is None:
                replacement = str(next_index)
                index_map[source_index] = replacement
                next_index += 1
            record = _replace_field(record, "INDEXINSHEET", replacement)
        if source_record_index == 0:
            record = _replace_field(record, "UNIQUEID", f"pge{index_start}")
        name = _field(source_record, "NAME")
        if name == "Designator":
            record = _replace_field(record, "TEXT", reference)
        elif name in {"Value", "Comment"}:
            record = _replace_field(record, "TEXT", value)
        records.append(record)
    return tuple(records), next_index


def _header_record(catalogue: SourceCatalogue, circuit: AltiumCircuit, weight: int) -> str:
    identity = uuid5(NAMESPACE_URL, f"progeneda:altium:{circuit.name}:{circuit.title}")
    return _replace_field(
        _replace_field(catalogue.header_record, "UNIQUEID", str(identity).upper()),
        "WEIGHT",
        str(weight),
    )


def _required_sheet_size(
    design: PlacedDesign,
    routing: RoutingPlan,
    catalogue: SourceCatalogue,
) -> tuple[int, int]:
    points: list[Point] = []
    for component in design.components:
        points.extend(
            (
                Point(component.bounds.min_x, component.bounds.min_y),
                Point(component.bounds.max_x, component.bounds.max_y),
                *component.pins.values(),
            )
        )
    for wire in routing.wires:
        points.extend((wire.start, wire.end))
    points.extend(label.location for label in routing.labels)
    if any(point.x < 0 or point.y < 0 for point in points):
        raise NativeWriteError("Placed/routed geometry extends into negative sheet coordinates.")

    def round_up(value: int, quantum: int = 100) -> int:
        return ((value + quantum - 1) // quantum) * quantum

    width = max(catalogue.sheet_width_ticks, round_up(max(point.x for point in points) + 160))
    height = max(catalogue.sheet_height_ticks, round_up(max(point.y for point in points) + 160))
    return width, height


def _sheet_record(catalogue: SourceCatalogue, width_ticks: int, height_ticks: int) -> str:
    if width_ticks % 2 or height_ticks % 2:
        raise NativeWriteError("Altium source sheet dimensions must use whole document units.")
    record = _set_field(catalogue.sheet_record, "CUSTOMX", str(width_ticks // 2))
    return _set_field(record, "CUSTOMY", str(height_ticks // 2))


def write_native_project(
    circuit: AltiumCircuit,
    selection: ComponentSelection,
    design: PlacedDesign,
    routing: RoutingPlan,
    route_records: WireMakerResult,
    *,
    catalogue: SourceCatalogue,
    project_directory: Path,
) -> NativeWriteResult:
    """Emit a fresh source-backed `.SchDoc` and `.PrjPcb` from stage contracts."""

    project_directory.mkdir(parents=True, exist_ok=False)
    schematic_directory = project_directory / "Schematic"
    schematic_directory.mkdir()
    source_by_reference = selection.by_reference()
    sheet_width_ticks, sheet_height_ticks = _required_sheet_size(design, routing, catalogue)
    emitted_records: list[str] = [_sheet_record(catalogue, sheet_width_ticks, sheet_height_ticks)]
    index_cursor = 1
    for component in design.components:
        try:
            source = source_by_reference[component.reference]
            template = catalogue.templates[component.source_template]
        except KeyError as exc:
            raise NativeWriteError(f"Placed component {component.reference} has no matching source selection.") from exc
        records, index_cursor = _rewrite_component_records(
            template,
            source.component,
            owner_index=component.owner_index,
            target_root=component.root_location,
            index_start=index_cursor,
        )
        emitted_records.extend(records)
    if route_records.wire_count != len(routing.wires) or route_records.label_count != len(routing.labels):
        raise NativeWriteError("Wire-maker record counts do not match the validated routing contract.")
    for native_route in route_records.records:
        emitted_records.append(_set_field(native_route.record, "INDEXINSHEET", str(index_cursor)))
        index_cursor += 1
    schematic_file = schematic_directory / f"{circuit.name}.SchDoc"
    header = _header_record(catalogue, circuit, len(emitted_records))
    schematic_file.write_text("\r\n".join((header, *emitted_records, "")), encoding="utf-8", newline="")
    project_file = project_directory / f"{circuit.name}.PrjPcb"
    project_file.write_text(
        render_project_descriptor(f"Schematic/{schematic_file.name}").replace("\n", "\r\n"),
        encoding="utf-8",
        newline="",
    )
    return NativeWriteResult(
        project_directory=project_directory,
        project_file=project_file,
        schematic_file=schematic_file,
        expected_contract=expected_physical_contract(
            design,
            routing,
            sheet_width_ticks=sheet_width_ticks,
            sheet_height_ticks=sheet_height_ticks,
        ),
        emitted_record_count=len(emitted_records),
        sheet_width_ticks=sheet_width_ticks,
        sheet_height_ticks=sheet_height_ticks,
    )
