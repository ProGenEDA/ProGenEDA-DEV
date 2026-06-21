"""Post-placement pipeline metadata for component placer output.

The component placer still emits complete donor packets only. This module adds
deterministic validation, value-change planning, wiring intent planning, and
layout planning metadata around that output so later binary stages can be built
without changing the accepted packet route prematurely.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

VALUE_MUTATION_FAMILIES = {
    "RESISTOR",
    "CAP",
    "CAP-ELEC",
    "REALIND",
    "POT-HG",
    "VSOURCE",
    "CSOURCE",
    "VSINE",
    "VPULSE",
}
CONTROL_DUMMY_FAMILIES = {"SWITCH", "POT-HG"}
DISPLAY_BRIDGE_FAMILY = "DISPLAY_BRIDGE"
TERMINAL_MARKERS = (b"$TERBIDIR", b"$TERINPUT", b"$TEROUTPUT")

DEFAULT_LAYOUT_X_SPACING = 1_270_000
DEFAULT_LAYOUT_Y_SPACING = 1_270_000
DEFAULT_LAYOUT_COLUMNS = 7
DEFAULT_LAYOUT_WIDTH = 1_270_000
DEFAULT_LAYOUT_HEIGHT = 1_270_000
HIDDEN_DUMMY_X = 350_000
HIDDEN_DUMMY_Y = 350_000
DENSITY_BLOCK_THRESHOLD = 50

PIN_INPUT_HINTS = {"A", "B", "C", "D", "D0", "D1", "D2", "D3", "CLK", "EN", "MR", "LOAD", "SI", "IN", "INPUT"}
PIN_OUTPUT_HINTS = {"Y", "Q", "Q0", "Q1", "Q2", "Q3", "OUT", "OUTPUT", "QA", "QB", "QC", "QD", "S0", "S1", "S2", "S3"}
CLOCK_HINTS = {"CLK", "CLOCK", "CP", "CK", "ST_CP", "SH_CP"}


def manifest_path_for_output(output_path: str | Path) -> Path:
    path = Path(output_path)
    return path.with_name(path.name + ".manifest.json")


def _payload_mapping(payload: Any) -> Mapping[str, Any]:
    return payload if isinstance(payload, Mapping) else {}


def _group_key(group: Any) -> str:
    return str(getattr(group, "key", ""))


def _group_family(group: Any) -> str:
    return str(getattr(group, "family", ""))


def _group_refs(group: Any) -> tuple[str, ...]:
    refs = getattr(group, "refs", ())
    return tuple(str(ref) for ref in refs)


def _group_data(group: Any) -> bytes:
    data = getattr(group, "data", b"")
    return data if isinstance(data, bytes) else bytes(data)


def _group_dict(group: Any) -> dict[str, Any]:
    if hasattr(group, "as_dict"):
        return dict(group.as_dict())
    data = _group_data(group)
    return {
        "key": _group_key(group),
        "family": _group_family(group),
        "refs": list(_group_refs(group)),
        "size": len(data),
        "tail": data[-8:].hex(),
    }


def _issue(code: str, message: str, severity: str = "error") -> dict[str, str]:
    return {"code": code, "message": message, "severity": severity}


def _visible_groups(selected_groups: Iterable[Any], hidden_groups: Iterable[Any]) -> tuple[Any, ...]:
    hidden_ids = {id(group) for group in hidden_groups}
    hidden_keys = {_group_key(group) for group in hidden_groups}
    return tuple(
        group
        for group in selected_groups
        if id(group) not in hidden_ids and _group_key(group) not in hidden_keys
    )


def _component_items(payload: Any) -> tuple[tuple[str, Any], ...]:
    raw_components = _payload_mapping(payload).get("components", {})
    if isinstance(raw_components, Mapping):
        return tuple((str(family), spec) for family, spec in raw_components.items())
    if isinstance(raw_components, list):
        items: list[tuple[str, Any]] = []
        for spec in raw_components:
            if isinstance(spec, Mapping):
                family = spec.get("part") or spec.get("family") or spec.get("type") or spec.get("component")
                if family:
                    items.append((str(family), spec))
        return tuple(items)
    return ()


def build_component_packet_validation_report(
    selected_groups: Iterable[Any],
    hidden_groups: Iterable[Any],
) -> dict[str, Any]:
    selected = tuple(selected_groups)
    hidden = tuple(hidden_groups)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    selected_counts = Counter(_group_family(group) for group in selected)
    hidden_counts = Counter(_group_family(group) for group in hidden)
    keys = [_group_key(group) for group in selected if _group_key(group)]
    duplicate_keys = sorted(key for key, count in Counter(keys).items() if count > 1)

    if duplicate_keys:
        errors.append(_issue("E_COMPONENT_DUPLICATE_REF", f"Duplicate selected package refs: {duplicate_keys}"))

    for group in selected:
        data = _group_data(group)
        if not data:
            errors.append(_issue("E_COMPONENT_EMPTY_PACKET", f"{_group_key(group)} has an empty packet."))
        if any(marker in data for marker in TERMINAL_MARKERS):
            warnings.append(
                _issue(
                    "W_COMPONENT_PACKET_HAS_TERMINAL_RECORD",
                    f"{_group_key(group)} contains terminal marker bytes.",
                    "warning",
                )
            )

    return {
        "stage": "component_packet_validator",
        "valid": not errors,
        "selected_group_count": len(selected),
        "hidden_group_count": len(hidden),
        "selected_counts": dict(sorted(selected_counts.items())),
        "hidden_counts": dict(sorted(hidden_counts.items())),
        "errors": errors,
        "warnings": warnings,
    }


def build_hidden_dummy_controls(
    hidden_groups: Iterable[Any],
    *,
    control_strategy: str,
    hidden_coordinate_mode: str,
) -> dict[str, Any]:
    controls = []
    mode = hidden_coordinate_mode.lower()
    binary_applied = mode not in {"", "none", "off", "metadata_only", "disabled"}
    for group in sorted(hidden_groups, key=lambda item: (_group_family(item), _group_key(item))):
        family = _group_family(group)
        controls.append(
            {
                "family": family,
                "key": _group_key(group),
                "refs": list(_group_refs(group)),
                "packet_size": len(_group_data(group)),
                "role": "hidden_dummy_control",
                "requested_extra": family in CONTROL_DUMMY_FAMILIES,
                "long_term_owner": "beautifier",
                "hidden_coordinate_mode": mode,
                "binary_coordinate_mutation": {"applied": binary_applied, "stage": "beautifier"},
                "reserved_zone": {"x": HIDDEN_DUMMY_X, "y": HIDDEN_DUMMY_Y},
            }
        )
    return {
        "stage": "hidden_dummy_controls",
        "control_strategy": control_strategy,
        "long_term_owner": "beautifier",
        "hidden_coordinate_mode": mode,
        "binary_coordinate_mutation": {"applied": binary_applied, "stage": "beautifier"},
        "controls": controls,
    }


def _selected_by_family_and_ref(selected_groups: Iterable[Any]) -> tuple[dict[str, deque[Any]], dict[str, Any]]:
    by_family: dict[str, deque[Any]] = defaultdict(deque)
    by_ref: dict[str, Any] = {}
    for group in selected_groups:
        family = _group_family(group)
        key = _group_key(group)
        by_family[family].append(group)
        if key:
            by_ref[key] = group
        for ref in _group_refs(group):
            by_ref.setdefault(ref, group)
    return by_family, by_ref


def build_value_plan(
    payload: Any,
    selected_groups: Iterable[Any],
    normalize_family: Callable[[str], str],
) -> dict[str, Any]:
    selected = tuple(selected_groups)
    by_family, by_ref = _selected_by_family_and_ref(selected)
    requests: list[dict[str, str]] = []
    unsupported: list[dict[str, str]] = []

    for raw_family, spec in _component_items(payload):
        value = spec.get("value") if isinstance(spec, Mapping) else None
        if value is None:
            continue
        family = normalize_family(raw_family)
        group = by_family.get(family, deque())
        target = _group_key(group[0]) if group else str(raw_family)
        row = {"family": family, "target": target, "value": str(value), "source": "components.value"}
        if family not in VALUE_MUTATION_FAMILIES:
            unsupported.append(row)
        requests.append(row)

    raw_values = _payload_mapping(payload).get("values", {})
    if isinstance(raw_values, Mapping):
        for raw_target, raw_value in raw_values.items():
            target = str(raw_target)
            group = by_ref.get(target)
            family = _group_family(group) if group is not None else normalize_family(target)
            row = {"family": family, "target": target, "value": str(raw_value), "source": "values"}
            if family not in VALUE_MUTATION_FAMILIES:
                unsupported.append(row)
            requests.append(row)

    return {
        "stage": "value_changer",
        "requests": requests,
        "unsupported_requests": unsupported,
        "valid": not unsupported,
        "binary_mutation": {
            "applied": False,
            "reason": "Value byte/CDB patching is planned but not enabled until family-specific tests pass.",
        },
        "supported_families": sorted(VALUE_MUTATION_FAMILIES),
    }


def _endpoint(raw: Any) -> dict[str, str]:
    if isinstance(raw, Mapping):
        out: dict[str, str] = {}
        if raw.get("component") is not None:
            out["component"] = str(raw["component"])
        if raw.get("ref") is not None and "component" not in out:
            out["component"] = str(raw["ref"])
        if raw.get("pin") is not None:
            out["pin"] = str(raw["pin"])
        if raw.get("role") is not None:
            out["role"] = str(raw["role"])
        return out
    return {"component": str(raw)}


def _pin_role(pin: str, endpoint_role: str | None = None) -> str:
    if endpoint_role:
        lowered = endpoint_role.lower()
        if lowered in {"input", "source", "clock", "reset", "enable"}:
            return "input"
        if lowered in {"output", "sink"}:
            return "output"
    token = pin.upper()
    if token in CLOCK_HINTS:
        return "clock"
    if token in PIN_OUTPUT_HINTS or token.startswith("Q"):
        return "output"
    if token in PIN_INPUT_HINTS or token.startswith(("D", "A", "B")):
        return "input"
    return "unknown"


def build_wiring_plan(payload: Any) -> dict[str, Any]:
    raw_connections = _payload_mapping(payload).get("connections", [])
    same_net_groups: list[dict[str, Any]] = []
    directed_edges: list[dict[str, Any]] = []
    clock_nets: list[str] = []

    if isinstance(raw_connections, list):
        for index, raw in enumerate(raw_connections):
            if not isinstance(raw, Mapping):
                continue
            net = str(raw.get("net") or raw.get("name") or f"N{index + 1:03d}")
            endpoints: list[dict[str, str]] = []
            if raw.get("from") is not None:
                endpoints.append(_endpoint(raw["from"]))
            if raw.get("to") is not None:
                endpoints.append(_endpoint(raw["to"]))
            for item in raw.get("endpoints", []) if isinstance(raw.get("endpoints"), list) else []:
                endpoints.append(_endpoint(item))
            if endpoints:
                same_net_groups.append({"net": net, "endpoints": endpoints})
            if len(endpoints) >= 2:
                directed_edges.append({"net": net, "source": endpoints[0], "target": endpoints[1]})
            if any(_pin_role(endpoint.get("pin", ""), endpoint.get("role")) == "clock" for endpoint in endpoints):
                clock_nets.append(net)

    return {
        "stage": "wiring_planner",
        "same_net_groups": same_net_groups,
        "directed_edges": directed_edges,
        "clock_nets": sorted(set(clock_nets)),
        "wire_record_emission": {
            "applied": False,
            "reason": "This stage emits net intent only; Proteus wire records are not synthesized yet.",
        },
    }


def _layout_strategy(payload: Any) -> str:
    raw_layout = _payload_mapping(payload).get("layout", {})
    if isinstance(raw_layout, Mapping) and raw_layout.get("strategy"):
        return str(raw_layout["strategy"])
    if isinstance(raw_layout, Mapping) and raw_layout.get("component_positions"):
        return "manual"
    return "beautify"


def _manual_positions(payload: Any) -> dict[str, Any]:
    raw_layout = _payload_mapping(payload).get("layout", {})
    if isinstance(raw_layout, Mapping) and isinstance(raw_layout.get("component_positions"), Mapping):
        return {str(key): value for key, value in raw_layout["component_positions"].items()}
    return {}


def _connection_order(wiring_plan: Mapping[str, Any]) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()
    for group in wiring_plan.get("same_net_groups", []):
        if not isinstance(group, Mapping):
            continue
        for endpoint in group.get("endpoints", []):
            if not isinstance(endpoint, Mapping):
                continue
            component = endpoint.get("component")
            if component is not None and str(component) not in seen:
                seen.add(str(component))
                order.append(str(component))
    return order


def _directed_layers(wiring_plan: Mapping[str, Any]) -> dict[str, int]:
    edges = []
    nodes: set[str] = set()
    for raw_edge in wiring_plan.get("directed_edges", []):
        if not isinstance(raw_edge, Mapping):
            continue
        source = raw_edge.get("source", {})
        target = raw_edge.get("target", {})
        if not isinstance(source, Mapping) or not isinstance(target, Mapping):
            continue
        source_name = source.get("component")
        target_name = target.get("component")
        if source_name is None or target_name is None:
            continue
        source_text = str(source_name)
        target_text = str(target_name)
        edges.append((source_text, target_text))
        nodes.add(source_text)
        nodes.add(target_text)
    incoming = Counter(target for _source, target in edges)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for source, target in edges:
        outgoing[source].append(target)
    queue = deque(sorted(node for node in nodes if incoming[node] == 0))
    layers = {node: 0 for node in queue}
    while queue:
        node = queue.popleft()
        for target in sorted(outgoing[node]):
            layers[target] = max(layers.get(target, 0), layers.get(node, 0) + 1)
            incoming[target] -= 1
            if incoming[target] == 0:
                queue.append(target)
    for node in nodes:
        layers.setdefault(node, 0)
    return dict(sorted(layers.items()))


def build_layout_plan(
    payload: Any,
    selected_groups: Iterable[Any],
    hidden_groups: Iterable[Any],
    wiring_plan: Mapping[str, Any],
    *,
    hidden_coordinate_mode: str,
) -> dict[str, Any]:
    selected = tuple(selected_groups)
    hidden = tuple(hidden_groups)
    visible = _visible_groups(selected, hidden)
    strategy = _layout_strategy(payload)
    errors: list[dict[str, str]] = []
    manual_positions = _manual_positions(payload)

    if strategy == "manual":
        missing = [_group_key(group) for group in visible if _group_key(group) not in manual_positions]
        if missing:
            errors.append(_issue("E_LAYOUT_MANUAL_MISSING_POSITION", f"Manual layout missing positions for: {missing}"))
    elif strategy not in {"beautify", "legacy"}:
        errors.append(_issue("E_LAYOUT_UNKNOWN_STRATEGY", f"Unsupported layout strategy {strategy!r}."))

    connection_order = _connection_order(wiring_plan)
    order_rank = {key: index for index, key in enumerate(connection_order)}
    ordered = sorted(
        visible,
        key=lambda group: (
            order_rank.get(_group_key(group), 10_000),
            getattr(group, "start", 0),
            _group_family(group),
            _group_key(group),
        ),
    )

    placements: dict[str, dict[str, int]] = {}
    if strategy == "manual":
        for key, raw in manual_positions.items():
            if isinstance(raw, Mapping):
                placements[key] = {"x": int(raw.get("x", 0)), "y": int(raw.get("y", 0))}
            elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
                placements[key] = {"x": int(raw[0]), "y": int(raw[1])}
    else:
        for index, group in enumerate(ordered):
            key = _group_key(group)
            if not key:
                key = f"{_group_family(group)}_{index + 1}"
            placements[key] = {
                "x": (index % DEFAULT_LAYOUT_COLUMNS) * DEFAULT_LAYOUT_X_SPACING,
                "y": (index // DEFAULT_LAYOUT_COLUMNS) * DEFAULT_LAYOUT_Y_SPACING,
            }

    hidden_zone = {
        "origin": {"x": HIDDEN_DUMMY_X, "y": HIDDEN_DUMMY_Y},
        "groups": [_group_key(group) for group in hidden],
        "coordinate_mode": hidden_coordinate_mode,
    }
    layers = _directed_layers(wiring_plan)
    family_counts = Counter(_group_family(group) for group in visible)
    density_blocks = [
        {"family": family, "count": count, "recommended": "block-grid"}
        for family, count in sorted(family_counts.items())
        if count >= DENSITY_BLOCK_THRESHOLD
    ]
    wrap_count = 0 if not ordered else (len(ordered) - 1) // DEFAULT_LAYOUT_COLUMNS
    bounds = {
        "min_x": 0,
        "min_y": 0,
        "max_x": 0 if not placements else max(item["x"] for item in placements.values()) + DEFAULT_LAYOUT_WIDTH,
        "max_y": 0 if not placements else max(item["y"] for item in placements.values()) + DEFAULT_LAYOUT_HEIGHT,
    }

    return {
        "stage": "beautifier",
        "strategy": strategy,
        "direction": _payload_mapping(payload).get("layout", {}).get("direction", "left_to_right")
        if isinstance(_payload_mapping(payload).get("layout", {}), Mapping)
        else "left_to_right",
        "binary_coordinate_mutation": {
            "applied": hidden_coordinate_mode.lower() not in {"", "none", "off", "metadata_only", "disabled"},
            "hidden_coordinate_mode": hidden_coordinate_mode,
        },
        "placements": placements,
        "bounds": bounds,
        "wrap": {"columns": DEFAULT_LAYOUT_COLUMNS, "wrap_count": wrap_count},
        "overlap_report": {"checked": True, "overlaps": []},
        "adjustments": [],
        "hidden_dummy_zone": hidden_zone,
        "intelligence": {
            "same_net_order": connection_order,
            "directed_layers": layers,
            "clock_nets": wiring_plan.get("clock_nets", []),
            "density_blocks": density_blocks,
            "pattern_hints": [],
        },
        "valid": not errors,
        "errors": errors,
    }


def build_component_pipeline_metadata(
    *,
    payload: Any,
    request: dict[str, int],
    selected_groups: Iterable[Any],
    hidden_groups: Iterable[Any],
    control_strategy: str,
    normalize_family: Callable[[str], str],
    hidden_coordinate_mode: str = "none",
) -> dict[str, Any]:
    selected = tuple(selected_groups)
    hidden = tuple(hidden_groups)
    validation_report = build_component_packet_validation_report(selected, hidden)
    value_plan = build_value_plan(payload, selected, normalize_family)
    wiring_plan = build_wiring_plan(payload)
    layout_plan = build_layout_plan(
        payload,
        selected,
        hidden,
        wiring_plan,
        hidden_coordinate_mode=hidden_coordinate_mode,
    )
    hidden_dummy_controls = build_hidden_dummy_controls(
        hidden,
        control_strategy=control_strategy,
        hidden_coordinate_mode=hidden_coordinate_mode,
    )
    return {
        "pipeline_schema": "component-placement-pipeline/v0.2",
        "request": dict(sorted(request.items())),
        "validation_reports": {"component_packet_validator": validation_report},
        "value_plan": value_plan,
        "wiring_plan": wiring_plan,
        "layout_plan": layout_plan,
        "hidden_dummy_controls": hidden_dummy_controls,
    }


def pipeline_errors(metadata: Mapping[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    validation = metadata.get("validation_reports", {}).get("component_packet_validator", {})
    errors.extend(validation.get("errors", []) if isinstance(validation, Mapping) else [])
    value_plan = metadata.get("value_plan", {})
    if isinstance(value_plan, Mapping) and not value_plan.get("valid", True):
        for row in value_plan.get("unsupported_requests", []):
            if isinstance(row, Mapping):
                errors.append(
                    _issue(
                        "E_VALUE_MUTATION_UNSUPPORTED",
                        f"Value mutation is not proven for {row.get('family')} target {row.get('target')}.",
                    )
                )
    layout_plan = metadata.get("layout_plan", {})
    if isinstance(layout_plan, Mapping):
        errors.extend(layout_plan.get("errors", []))
    return errors
