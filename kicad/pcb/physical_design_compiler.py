"""Compile backend-neutral main JSON into a supported physical PCB subset."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from kicad.pipeline.catelogues.component_catalogue_loader import load_component_catalogue

from .footprint_catalogue import FootprintRecord, load_footprint_catalogue


PHYSICAL_DESIGN_SCHEMA = "progen-kicad-physical-design/v0.1"
NON_PHYSICAL_TYPES = {"GND_Symbol", "Power_Symbol", "VSource_DC"}


@dataclass(frozen=True)
class PhysicalComponent:
    ref: str
    kind: str
    value: str
    role: str
    block: str
    abstract_type: str
    footprint_id: str
    footprint_sha256: str
    pad_nets: dict[str, str]
    logical_pin_to_pad: dict[str, str]
    footprint: FootprintRecord

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "kind": self.kind,
            "value": self.value,
            "role": self.role,
            "block": self.block,
            "abstract_type": self.abstract_type,
            "footprint_id": self.footprint_id,
            "footprint_sha256": self.footprint_sha256,
            "pad_nets": dict(sorted(self.pad_nets.items())),
            "logical_pin_to_pad": dict(sorted(self.logical_pin_to_pad.items())),
            "bounds": dict(self.footprint.bounds),
        }


@dataclass(frozen=True)
class PhysicalDesign:
    circuit_id: str
    components: tuple[PhysicalComponent, ...]
    omitted_components: tuple[dict[str, Any], ...]
    nets: dict[str, tuple[str, ...]]
    source_metadata: dict[str, Any]

    @property
    def generated(self) -> bool:
        return bool(self.components)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": PHYSICAL_DESIGN_SCHEMA,
            "circuit_id": self.circuit_id,
            "generated": self.generated,
            "supported_component_count": len(self.components),
            "omitted_component_count": len(self.omitted_components),
            "components": {component.ref: component.as_dict() for component in self.components},
            "omitted_components": list(self.omitted_components),
            "nets": {name: list(members) for name, members in sorted(self.nets.items())},
            "net_count": len(self.nets),
            "source_metadata": self.source_metadata,
        }


def _component_pin_points(routing_placement: dict[str, Any], ref: str) -> dict[str, Any]:
    pin_points = routing_placement.get("pin_points", {})
    if not isinstance(pin_points, dict):
        return {}
    value = pin_points.get(ref, {})
    return value if isinstance(value, dict) else {}


def _resolve_pin_number(logical_pin: str, metadata: Any) -> str | None:
    if isinstance(metadata, dict):
        resolved = str(metadata.get("resolved_pin_number") or "").strip()
        if resolved:
            return resolved
    fallback = str(logical_pin).strip()
    return fallback if fallback.isdigit() else None


def _select_footprint(abstract_type: str, required_pads: set[str]) -> tuple[str | None, str | None]:
    footprints = load_footprint_catalogue()
    footprint_id = footprints.footprint_id_for_abstract_type(abstract_type)
    if footprint_id:
        record = footprints.record(footprint_id)
        if required_pads.issubset(record.pad_numbers):
            return footprint_id, None
    if abstract_type == "Connector_Generic":
        dynamic = footprints.connector_footprint(required_pads)
        if dynamic:
            record = footprints.record(dynamic)
            if required_pads.issubset(record.pad_numbers):
                return dynamic, None
    if footprint_id:
        return None, "footprint_missing_required_pads"
    return None, "no_supported_physical_footprint"


def compile_physical_design(circuit: dict[str, Any], routing_placement: dict[str, Any]) -> PhysicalDesign:
    abstract_catalogue = load_component_catalogue()
    footprints = load_footprint_catalogue()
    selected: list[PhysicalComponent] = []
    omitted: list[dict[str, Any]] = []

    for raw in circuit.get("components", []):
        if not isinstance(raw, dict):
            continue
        ref = str(raw.get("ref") or raw.get("id") or "").strip()
        kind = str(raw.get("kind") or raw.get("type") or "").strip()
        value = str(raw.get("value") or kind).strip()
        abstract_type = abstract_catalogue.resolve_type_id(kind)
        omission = {"ref": ref, "kind": kind, "abstract_type": abstract_type}
        if abstract_type in NON_PHYSICAL_TYPES:
            omitted.append({**omission, "reason": "non_physical_schematic_object"})
            continue

        pins = raw.get("pins", {})
        if not isinstance(pins, dict) or not pins:
            omitted.append({**omission, "reason": "component_has_no_compiled_pin_nets"})
            continue
        pin_metadata = _component_pin_points(routing_placement, ref)
        logical_to_pad: dict[str, str] = {}
        pad_nets: dict[str, str] = {}
        unresolved: list[str] = []
        conflicts: list[dict[str, str]] = []
        for logical_pin, raw_net in pins.items():
            net = str(raw_net).strip()
            if not net:
                continue
            pad = _resolve_pin_number(str(logical_pin), pin_metadata.get(str(logical_pin)))
            if not pad:
                unresolved.append(str(logical_pin))
                continue
            existing = pad_nets.get(pad)
            if existing and existing != net:
                conflicts.append({"pad": pad, "left_net": existing, "right_net": net})
                continue
            logical_to_pad[str(logical_pin)] = pad
            pad_nets[pad] = net
        if unresolved:
            omitted.append({**omission, "reason": "unresolved_physical_pin", "pins": sorted(unresolved)})
            continue
        if conflicts:
            omitted.append({**omission, "reason": "physical_pad_net_conflict", "conflicts": conflicts})
            continue
        if not pad_nets:
            omitted.append({**omission, "reason": "no_physical_pad_nets"})
            continue

        footprint_id, reason = _select_footprint(abstract_type, set(pad_nets))
        if not footprint_id:
            omitted.append({**omission, "reason": reason or "unsupported"})
            continue
        footprint = footprints.record(footprint_id)
        selected.append(
            PhysicalComponent(
                ref=ref,
                kind=kind,
                value=value,
                role=str(raw.get("role") or ""),
                block=str(raw.get("block") or ""),
                abstract_type=abstract_type,
                footprint_id=footprint_id,
                footprint_sha256=footprint.sha256,
                pad_nets=pad_nets,
                logical_pin_to_pad=logical_to_pad,
                footprint=footprint,
            )
        )

    net_members: dict[str, list[str]] = {}
    for component in selected:
        for pad, net in component.pad_nets.items():
            net_members.setdefault(net, []).append(f"{component.ref}.{pad}")
    nets = {name: tuple(sorted(set(members))) for name, members in net_members.items()}
    return PhysicalDesign(
        circuit_id=str(circuit.get("circuit_id") or circuit.get("project", {}).get("name") or "circuit"),
        components=tuple(selected),
        omitted_components=tuple(omitted),
        nets=nets,
        source_metadata=footprints.source_metadata,
    )
