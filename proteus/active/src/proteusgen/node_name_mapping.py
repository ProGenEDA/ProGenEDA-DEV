"""Logical net/node-name mapping for component pins.

This is the integration layer between user JSON/CircuitIR and backend terminal
or wire emitters.  It resolves component aliases and pin aliases through the
component catalogue, then groups normalized endpoints by logical node name.
"""

from __future__ import annotations

from collections import OrderedDict
import re
from typing import Any, Mapping

from .circuit_ir import CircuitIR, Issue, parse_circuit_ir
from .component_catalog import ComponentCatalog, PinProfile, load_component_catalog


_SAFE_TERMINAL_LABEL_RE = re.compile(r"^[A-Za-z0-9_+./-]+$")
_POWER_NETS = {"V0", "VCC", "+5V", "5V", "VDD"}
_GROUND_NETS = {"G0", "GND", "0", "0V", "VSS"}
_FAMILY_REF_PREFIXES = {
    "RESISTOR": "R",
    "CAP": "C",
    "CAP-ELEC": "C",
    "REALIND": "L",
    "DIODE": "D",
    "LED-RED": "D",
    "FUSE": "FU",
    "VSOURCE": "V",
    "VSINE": "V",
    "VPULSE": "V",
    "CSOURCE": "I",
}


def _clean_terminal_label(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_+./-]+", "_", value.strip())
    cleaned = cleaned.strip("_")
    return cleaned or "N"


def terminal_label_for_node(
    node: str,
    *,
    kind: str = "internal",
    index: int = 0,
    used: set[str] | None = None,
) -> str:
    """Return a deterministic terminal label for a logical node name."""

    used_labels = used if used is not None else set()
    upper = node.upper()
    if kind == "power" or upper in _POWER_NETS:
        candidate = "V0" if upper in _POWER_NETS else _clean_terminal_label(node)
    elif kind == "ground" or upper in _GROUND_NETS:
        candidate = "G0" if upper in _GROUND_NETS else _clean_terminal_label(node)
    else:
        candidate = _clean_terminal_label(node)
        if len(candidate) > 16 or not _SAFE_TERMINAL_LABEL_RE.fullmatch(candidate):
            candidate = f"N{index:03d}"

    if candidate not in used_labels:
        used_labels.add(candidate)
        return candidate

    fallback_index = index
    while True:
        fallback = f"N{fallback_index:03d}"
        if fallback not in used_labels:
            used_labels.add(fallback)
            return fallback
        fallback_index += 1


def _endpoint_dict(
    *,
    component_ref: str,
    part: str,
    raw_pin: str,
    net: str,
    pin: PinProfile,
    source_path: str,
) -> dict[str, Any]:
    out = {
        "component": component_ref,
        "part": part,
        "pin": pin.name,
        "raw_pin": raw_pin,
        "net": net,
        "role": pin.role,
        "electrical_type": pin.electrical_type,
        "hidden": pin.hidden,
        "source_path": source_path,
    }
    if pin.subpart is not None:
        out["subpart"] = pin.subpart
    return out


def _from_circuit_ir(ir: CircuitIR, catalog: ComponentCatalog) -> dict[str, Any]:
    errors: list[Issue] = []
    components: dict[str, tuple[str, Any]] = {}
    for index, component in enumerate(ir.circuit.components):
        try:
            part = catalog.normalize_part(component.part)
        except ValueError as exc:
            errors.append(
                Issue(
                    "UNKNOWN_COMPONENT_PROFILE",
                    str(exc),
                    f"$.circuit.components[{index}].part",
                )
            )
            continue
        components[component.ref] = (part, catalog.profile(part))

    net_kinds = {net.name: net.kind for net in ir.circuit.nets}
    ordered_nodes: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    hidden_endpoints: list[dict[str, Any]] = []
    for index, connection in enumerate(ir.circuit.connections):
        component = components.get(connection.component)
        if component is None:
            errors.append(
                Issue(
                    "UNKNOWN_COMPONENT",
                    f"Connection references missing component `{connection.component}`.",
                    f"$.circuit.connections[{index}].component",
                )
            )
            continue
        part, profile = component
        try:
            pin = profile.normalize_pin(connection.pin)
        except ValueError as exc:
            errors.append(
                Issue(
                    "UNKNOWN_PIN",
                    str(exc),
                    f"$.circuit.connections[{index}].pin",
                )
            )
            continue
        endpoint = _endpoint_dict(
            component_ref=connection.component,
            part=part,
            raw_pin=connection.pin,
            net=connection.net,
            pin=pin,
            source_path=f"$.circuit.connections[{index}]",
        )
        ordered_nodes.setdefault(connection.net, []).append(endpoint)
        if pin.hidden:
            hidden_endpoints.append(endpoint)

    return _mapping_from_nodes(
        ordered_nodes,
        net_kinds=net_kinds,
        errors=errors,
        hidden_endpoints=hidden_endpoints,
        source="CircuitIR",
    )


def _component_part_from_payload(
    raw_components: Any,
    catalog: ComponentCatalog,
) -> dict[str, tuple[str, Any]]:
    components: dict[str, tuple[str, Any]] = {}
    if isinstance(raw_components, list):
        for index, raw in enumerate(raw_components):
            if not isinstance(raw, Mapping):
                continue
            ref = raw.get("ref") or raw.get("id") or raw.get("name")
            part = raw.get("part") or raw.get("family") or raw.get("kind") or raw.get("type")
            if ref is None or part is None:
                continue
            normalized = catalog.normalize_part(str(part))
            components[str(ref)] = (normalized, catalog.profile(normalized))
    elif isinstance(raw_components, Mapping):
        prefix_counts: dict[str, int] = {}
        for raw_family, raw_spec in raw_components.items():
            normalized = catalog.normalize_part(str(raw_family))
            profile = catalog.profile(normalized)
            if isinstance(raw_spec, Mapping):
                count = int(raw_spec.get("count", 1))
            else:
                count = int(raw_spec)
            prefix = _FAMILY_REF_PREFIXES.get(normalized, normalized[:1] or "U")
            for _index in range(count):
                prefix_counts[prefix] = prefix_counts.get(prefix, 0) + 1
                components[f"{prefix}{prefix_counts[prefix]}"] = (normalized, profile)
    return components


def _endpoint_from_raw(raw: Any) -> dict[str, str]:
    if isinstance(raw, Mapping):
        component = raw.get("component") or raw.get("ref") or raw.get("id")
        pin = raw.get("pin")
        return {
            "component": "" if component is None else str(component),
            "pin": "" if pin is None else str(pin),
        }
    return {"component": str(raw), "pin": ""}


def _from_lightweight_payload(payload: Mapping[str, Any], catalog: ComponentCatalog) -> dict[str, Any]:
    errors: list[Issue] = []
    components = _component_part_from_payload(payload.get("components", []), catalog)
    net_kinds: dict[str, str] = {}
    raw_nets = payload.get("nets", {})
    if isinstance(raw_nets, Mapping):
        net_kinds.update({str(name): str(kind) for name, kind in raw_nets.items()})
    elif isinstance(raw_nets, list):
        for raw in raw_nets:
            if isinstance(raw, Mapping) and raw.get("name") is not None:
                net_kinds[str(raw["name"])] = str(raw.get("kind", "internal"))

    ordered_nodes: OrderedDict[str, list[dict[str, Any]]] = OrderedDict()
    hidden_endpoints: list[dict[str, Any]] = []
    raw_connections = payload.get("connections", [])
    if not isinstance(raw_connections, list):
        raw_connections = []
    for index, raw_connection in enumerate(raw_connections):
        if not isinstance(raw_connection, Mapping):
            continue
        net = str(raw_connection.get("net") or raw_connection.get("name") or f"N{index + 1:03d}")
        raw_endpoints = []
        if raw_connection.get("from") is not None:
            raw_endpoints.append(raw_connection["from"])
        if raw_connection.get("to") is not None:
            raw_endpoints.append(raw_connection["to"])
        if isinstance(raw_connection.get("endpoints"), list):
            raw_endpoints.extend(raw_connection["endpoints"])

        for endpoint_index, raw_endpoint in enumerate(raw_endpoints):
            endpoint = _endpoint_from_raw(raw_endpoint)
            component_ref = endpoint["component"]
            component = components.get(component_ref)
            if component is None:
                errors.append(
                    Issue(
                        "UNKNOWN_COMPONENT",
                        f"Connection references missing component `{component_ref}`.",
                        f"$.connections[{index}].endpoints[{endpoint_index}]",
                    )
                )
                continue
            part, profile = component
            try:
                pin = profile.normalize_pin(endpoint["pin"])
            except ValueError as exc:
                errors.append(
                    Issue(
                        "UNKNOWN_PIN",
                        str(exc),
                        f"$.connections[{index}].endpoints[{endpoint_index}].pin",
                    )
                )
                continue
            normalized = _endpoint_dict(
                component_ref=component_ref,
                part=part,
                raw_pin=endpoint["pin"],
                net=net,
                pin=pin,
                source_path=f"$.connections[{index}].endpoints[{endpoint_index}]",
            )
            ordered_nodes.setdefault(net, []).append(normalized)
            if pin.hidden:
                hidden_endpoints.append(normalized)

    return _mapping_from_nodes(
        ordered_nodes,
        net_kinds=net_kinds,
        errors=errors,
        hidden_endpoints=hidden_endpoints,
        source="lightweight_payload",
    )


def _mapping_from_nodes(
    ordered_nodes: OrderedDict[str, list[dict[str, Any]]],
    *,
    net_kinds: Mapping[str, str],
    errors: list[Issue],
    hidden_endpoints: list[dict[str, Any]],
    source: str,
) -> dict[str, Any]:
    used_labels: set[str] = set()
    nodes: list[dict[str, Any]] = []
    endpoint_to_node: dict[str, str] = {}
    terminal_labels: dict[str, str] = {}
    for index, (node, endpoints) in enumerate(ordered_nodes.items()):
        kind = str(net_kinds.get(node, "internal"))
        label = terminal_label_for_node(node, kind=kind, index=index, used=used_labels)
        terminal_labels[node] = label
        for endpoint in endpoints:
            endpoint_to_node[f"{endpoint['component']}.{endpoint['pin']}"] = node
        nodes.append(
            {
                "node": node,
                "kind": kind,
                "terminal_label": label,
                "endpoint_count": len(endpoints),
                "visible_endpoint_count": sum(1 for endpoint in endpoints if not endpoint["hidden"]),
                "hidden_endpoint_count": sum(1 for endpoint in endpoints if endpoint["hidden"]),
                "endpoints": endpoints,
            }
        )

    return {
        "stage": "node_name_mapper",
        "source": source,
        "valid": not errors,
        "node_count": len(nodes),
        "endpoint_count": sum(node["endpoint_count"] for node in nodes),
        "visible_endpoint_count": sum(node["visible_endpoint_count"] for node in nodes),
        "hidden_endpoint_count": len(hidden_endpoints),
        "terminal_labels": terminal_labels,
        "endpoint_to_node": endpoint_to_node,
        "nodes": nodes,
        "hidden_endpoints": hidden_endpoints,
        "errors": [issue.as_dict() for issue in errors],
    }


def build_node_name_mapping(
    payload: CircuitIR | Mapping[str, Any],
    *,
    catalog: ComponentCatalog | None = None,
) -> dict[str, Any]:
    """Build a normalized logical node map from CircuitIR or lightweight JSON."""

    component_catalog = catalog or load_component_catalog()
    if isinstance(payload, CircuitIR):
        return _from_circuit_ir(payload, component_catalog)
    if "version" in payload and "circuit" in payload:
        ir, issues = parse_circuit_ir(payload)
        if issues or ir is None:
            return {
                "stage": "node_name_mapper",
                "source": "CircuitIR",
                "valid": False,
                "node_count": 0,
                "endpoint_count": 0,
                "visible_endpoint_count": 0,
                "hidden_endpoint_count": 0,
                "terminal_labels": {},
                "endpoint_to_node": {},
                "nodes": [],
                "hidden_endpoints": [],
                "errors": [issue.as_dict() for issue in issues],
            }
        return _from_circuit_ir(ir, component_catalog)
    return _from_lightweight_payload(payload, component_catalog)
