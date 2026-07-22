"""Source-backed native wire/label record construction.

This stage owns native route geometry serialization. The project writer only
allocates final record indexes and composes already-built records with placed
component blocks.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .pipeline_contracts import PipelineError, RoutingPlan
from .source_catalogue import Point, SourceCatalogue


WIRE_MAKER_SCHEMA = "progen-altium-wire-maker/v1"
_UNSAFE_TEXT = re.compile(r"[|\r\n\x00]")


class WireMakingError(PipelineError):
    """A validated route cannot be represented using the locked source records."""


@dataclass(frozen=True)
class NativeRouteRecord:
    kind: str
    net: str
    record: str

    def json(self) -> dict[str, str]:
        return {"kind": self.kind, "net": self.net, "record": self.record}


@dataclass(frozen=True)
class WireMakerResult:
    records: tuple[NativeRouteRecord, ...]
    wire_count: int
    label_count: int

    def json(self) -> dict[str, Any]:
        return {
            "schema": WIRE_MAKER_SCHEMA,
            "wire_count": self.wire_count,
            "label_count": self.label_count,
            "records": [record.json() for record in self.records],
        }


def _field(record: str, name: str) -> str | None:
    match = re.search(rf"\|{re.escape(name)}=([^|]*)", record)
    return match.group(1) if match else None


def _set_field(record: str, name: str, value: str) -> str:
    pattern = re.compile(rf"(\|{re.escape(name)}=)[^|]*")
    if pattern.search(record):
        return pattern.sub(lambda match: f"{match.group(1)}{value}", record)
    return f"{record}|{name}={value}"


def _remove_field(record: str, name: str) -> str:
    return re.sub(rf"\|{re.escape(name)}=[^|]*", "", record)


def _set_coordinate(record: str, name: str, value: int) -> str:
    whole, remainder = divmod(value, 2)
    result = _set_field(record, name, str(whole))
    fraction_name = f"{name}_FRAC"
    return _set_field(result, fraction_name, "50000") if remainder else _remove_field(result, fraction_name)


def _wire_record(source_record: str, start: Point, end: Point) -> str:
    record = _set_field(source_record, "INDEXINSHEET", "0")
    for name, value in (("X1", start.x), ("Y1", start.y), ("X2", end.x), ("Y2", end.y)):
        record = _set_coordinate(record, name, value)
    return record


def _label_record(source_record: str, net: str, location: Point) -> str:
    if not net or _UNSAFE_TEXT.search(net):
        raise WireMakingError(f"Terminal net name {net!r} is unsafe for a native record.")
    record = _set_field(source_record, "INDEXINSHEET", "0")
    record = _set_field(record, "TEXT", net)
    record = _set_coordinate(record, "LOCATION.X", location.x)
    return _set_coordinate(record, "LOCATION.Y", location.y)


def make_native_route_records(routing: RoutingPlan, catalogue: SourceCatalogue) -> WireMakerResult:
    """Build native records from the routing contract without writing project files."""

    records = [
        NativeRouteRecord("wire", segment.net, _wire_record(catalogue.wire_record, segment.start, segment.end))
        for segment in routing.wires
    ]
    records.extend(
        NativeRouteRecord(
            "net_label",
            label.net,
            _label_record(catalogue.net_label_record, label.net, label.location),
        )
        for label in routing.labels
    )
    return WireMakerResult(
        records=tuple(records),
        wire_count=len(routing.wires),
        label_count=len(routing.labels),
    )
