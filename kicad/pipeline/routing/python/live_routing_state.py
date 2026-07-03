"""Mathematical live routing state.

This module is the Python implementation of the PDF's temporary catalogue /
LiveRoutingState contract. It does not know how to write KiCad files. It stores
component positions, rotations, bodies, keepouts, resolved pin anchors, nets,
routes, and metrics in a backend-neutral JSON shape.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from statistics import median
from typing import Any

from kicad.pipeline.arrangement_decider import GROUND_NETS, POWER_NETS, extract_connection_nets
from kicad.pipeline.catelogues import ComponentCatalogue, load_component_catalogue, normalize_type_id


Point = tuple[float, float]
SIDE_ORDER = ("left", "top", "right", "bottom")
CLOCK_TOKENS = ("CLK", "CLOCK", "SHCP", "STCP", "RESET", "LATCH")
BUS_TOKENS = ("SPI", "I2C", "UART", "SEG", "DATA", "ADDRESS", "SHIFT", "CAN", "RS485", "MOSI", "MISO", "SCK")


def snap(value: float, grid: float) -> float:
    return round(round(float(value) / grid) * grid, 3)


def rotate_point(point: Point, rotation: int | float) -> Point:
    """Rotate a local point around a component center by 0/90/180/270."""
    x, y = float(point[0]), float(point[1])
    normalized = int(rotation) % 360
    if normalized == 0:
        return (x, y)
    if normalized == 90:
        return (-y, x)
    if normalized == 180:
        return (-x, -y)
    if normalized == 270:
        return (y, -x)
    raise ValueError(f"rotation must be 0/90/180/270, got {rotation!r}")


def rotate_side(side: str, rotation: int | float) -> str:
    """Rotate a pin side using the transform specified by the PDF plan."""
    value = str(side or "right").lower()
    if value not in SIDE_ORDER:
        value = "right"
    steps = (int(rotation) % 360) // 90
    order = list(SIDE_ORDER)
    return order[(order.index(value) + steps) % len(order)]


def classify_net(net: str) -> str:
    upper = str(net).upper()
    if upper in POWER_NETS:
        return "power"
    if upper in GROUND_NETS:
        return "ground"
    if any(token in upper for token in CLOCK_TOKENS):
        return "clock_control"
    if any(token in upper for token in BUS_TOKENS):
        return "bus"
    if upper.startswith("SEG_") or upper in {"A", "B", "C", "D", "E", "F", "G", "DP"}:
        return "display_segment"
    return "ordinary_signal"


def net_weight(net_class: str) -> float:
    return {
        "clock_control": 10.0,
        "bus": 6.0,
        "display_segment": 5.0,
        "ordinary_signal": 3.0,
        "power": 0.5,
        "ground": 0.5,
    }.get(net_class, 3.0)


def _body_rect(at: Point, width: float, height: float, rotation: int | float) -> dict[str, float]:
    normalized = int(rotation) % 360
    body_width, body_height = (height, width) if normalized in {90, 270} else (width, height)
    x, y = at
    return {
        "left": round(x - body_width / 2, 3),
        "top": round(y - body_height / 2, 3),
        "right": round(x + body_width / 2, 3),
        "bottom": round(y + body_height / 2, 3),
    }


def _inflate(rect: dict[str, float], keepout: dict[str, Any]) -> dict[str, float]:
    return {
        "left": round(rect["left"] - float(keepout.get("left", 0.0)), 3),
        "top": round(rect["top"] - float(keepout.get("top", 0.0)), 3),
        "right": round(rect["right"] + float(keepout.get("right", 0.0)), 3),
        "bottom": round(rect["bottom"] + float(keepout.get("bottom", 0.0)), 3),
    }


def _rect_overlap(left: dict[str, float], right: dict[str, float]) -> bool:
    return left["left"] < right["right"] and left["right"] > right["left"] and left["top"] < right["bottom"] and left["bottom"] > right["top"]


def _point_from_raw(value: Any, fallback: Point = (0.0, 0.0)) -> Point:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    return fallback


def _pin_lookup(pin_defs: dict[str, Any]) -> dict[str, tuple[str, dict[str, Any]]]:
    lookup: dict[str, tuple[str, dict[str, Any]]] = {}
    for name, pin in pin_defs.items():
        keys = {name, str(pin.get("number", "")), normalize_type_id(name), normalize_type_id(pin.get("number", ""))}
        for key in keys:
            if key:
                lookup[str(key)] = (str(name), pin)
    return lookup


def _fallback_pin_def(pin_name: str, index: int, total: int, width: float, height: float, net: str) -> dict[str, Any]:
    net_class = classify_net(net)
    if net_class == "power":
        return {"number": str(pin_name), "local": [0.0, -height / 2], "side": "top", "type": "power", "roles": ["power"]}
    if net_class == "ground":
        return {"number": str(pin_name), "local": [0.0, height / 2], "side": "bottom", "type": "ground", "roles": ["ground"]}
    side = "left" if index % 2 == 0 else "right"
    rows = max(1, (total + 1) // 2)
    row = index // 2
    y = 0.0 if rows == 1 else -height * 0.35 + (height * 0.7 * row / max(1, rows - 1))
    x = -width / 2 if side == "left" else width / 2
    return {"number": str(pin_name), "local": [round(x, 3), round(y, 3)], "side": side, "type": "passive", "roles": [net_class]}


@dataclass
class LiveRoutingState:
    schema: str
    unit: str
    grid: float
    sheet: dict[str, float]
    components: dict[str, dict[str, Any]]
    nets: dict[str, dict[str, Any]]
    routes: dict[str, Any]
    metrics: dict[str, Any]
    source_placement: dict[str, Any]

    def clone_state(self) -> "LiveRoutingState":
        return LiveRoutingState.from_dict(self.as_dict(), source_placement=deepcopy(self.source_placement))

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, source_placement: dict[str, Any] | None = None) -> "LiveRoutingState":
        return cls(
            schema=str(data.get("schema") or "progen-live-routing-state/v0.2"),
            unit=str(data.get("unit") or "mm"),
            grid=float(data.get("grid", 2.54)),
            sheet=deepcopy(data.get("sheet") or {"width": 420.0, "height": 297.0, "margin": 15.24}),
            components=deepcopy(data.get("components") or {}),
            nets=deepcopy(data.get("nets") or {}),
            routes=deepcopy(data.get("routes") or {}),
            metrics=deepcopy(data.get("metrics") or {}),
            source_placement=deepcopy(source_placement if source_placement is not None else data.get("source_placement") or {}),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "unit": self.unit,
            "grid": self.grid,
            "sheet": deepcopy(self.sheet),
            "components": deepcopy(self.components),
            "nets": deepcopy(self.nets),
            "routes": deepcopy(self.routes),
            "metrics": deepcopy(self.metrics),
        }

    def component_center(self, ref: str) -> Point:
        at = self.components[ref].get("at", [0.0, 0.0])
        return (float(at[0]), float(at[1]))

    def apply_move(self, ref: str, x: float, y: float) -> None:
        component = self.components[ref]
        component["at"] = [snap(x, self.grid), snap(y, self.grid)]
        self.recompute_component_body(ref)
        self.recompute_component_keepout(ref)
        self.recompute_component_pin_anchors(ref)
        self._recompute_net_endpoints()

    def apply_rotation(self, ref: str, rotation: int | float) -> None:
        component = self.components[ref]
        legal = set(int(item) for item in component.get("legal_rotations", [0, 90, 180, 270]))
        normalized = int(rotation) % 360
        if normalized not in legal:
            raise ValueError(f"{ref} cannot rotate to {normalized}; legal rotations: {sorted(legal)}")
        component["rotation"] = normalized
        self.recompute_component_body(ref)
        self.recompute_component_keepout(ref)
        self.recompute_component_pin_anchors(ref)
        self._recompute_net_endpoints()

    def apply_move_rotation(self, ref: str, x: float, y: float, rotation: int | float) -> None:
        component = self.components[ref]
        legal = set(int(item) for item in component.get("legal_rotations", [0, 90, 180, 270]))
        normalized = int(rotation) % 360
        if normalized not in legal:
            raise ValueError(f"{ref} cannot rotate to {normalized}; legal rotations: {sorted(legal)}")
        component["rotation"] = normalized
        component["at"] = [snap(x, self.grid), snap(y, self.grid)]
        self.recompute_component_body(ref)
        self.recompute_component_keepout(ref)
        self.recompute_component_pin_anchors(ref)
        self._recompute_net_endpoints()

    def recompute_component_body(self, ref: str) -> None:
        component = self.components[ref]
        component["body"] = _body_rect(
            self.component_center(ref),
            float(component["catalogue_body"]["width"]),
            float(component["catalogue_body"]["height"]),
            int(component.get("rotation", 0)),
        )

    def recompute_component_keepout(self, ref: str) -> None:
        component = self.components[ref]
        component["keepout"] = _inflate(component["body"], component["catalogue_body"].get("keepout", {}))

    def recompute_component_pin_anchors(self, ref: str) -> None:
        component = self.components[ref]
        at = self.component_center(ref)
        rotation = int(component.get("rotation", 0))
        pins: dict[str, Any] = {}
        for pin_name, pin in component.get("pin_defs", {}).items():
            local = _point_from_raw(pin.get("local"), (0.0, 0.0))
            rotated = rotate_point(local, rotation)
            point = [round(at[0] + rotated[0], 3), round(at[1] + rotated[1], 3)]
            pins[str(pin_name)] = {
                "number": str(pin.get("number", pin_name)),
                "point": point,
                "side": rotate_side(str(pin.get("side", "right")), rotation),
                "type": str(pin.get("type", "passive")),
                "roles": list(pin.get("roles", [])),
                "source": str(pin.get("source", "component_catalogue")),
            }
        component["pins"] = pins

    def _recompute_net_endpoints(self) -> None:
        for net_name, net in self.nets.items():
            endpoints = []
            for endpoint in net.get("endpoint_refs", []):
                ref = str(endpoint.get("ref") or "")
                pin = str(endpoint.get("pin") or "")
                component = self.components.get(ref)
                if not component:
                    continue
                pin_data = component.get("pins", {}).get(pin)
                if not pin_data:
                    pin_data = component.get("pins", {}).get(normalize_type_id(pin))
                if not pin_data:
                    continue
                endpoints.append(
                    {
                        "ref": ref,
                        "pin": pin,
                        "point": list(pin_data["point"]),
                        "side": pin_data.get("side"),
                        "type": pin_data.get("type"),
                        "roles": pin_data.get("roles", []),
                    }
                )
            net["endpoints"] = endpoints
            net["fanout"] = len(endpoints)

    def find_overlaps(self, ref: str | None = None) -> list[dict[str, Any]]:
        refs = [ref] if ref else sorted(self.components)
        overlaps: list[dict[str, Any]] = []
        for left_ref in refs:
            if left_ref not in self.components:
                continue
            left = self.components[left_ref]["keepout"]
            for right_ref, right_component in self.components.items():
                if left_ref == right_ref:
                    continue
                if ref is None and left_ref > right_ref:
                    continue
                right = right_component["keepout"]
                if _rect_overlap(left, right):
                    overlaps.append({"left": left_ref, "right": right_ref})
        return overlaps

    def find_blockers(self, ref: str) -> list[str]:
        if ref not in self.components:
            return []
        active = self.components[ref]["keepout"]
        blockers = [
            other_ref
            for other_ref, other in self.components.items()
            if other_ref != ref and _rect_overlap(active, other["keepout"])
        ]
        return sorted(blockers)

    def legalize_after_move(self, ref: str, *, max_depth: int = 3) -> dict[str, Any]:
        moved: list[dict[str, Any]] = []
        failed: list[str] = []
        self._legalize_ref(ref, moved=moved, failed=failed, depth=0, max_depth=max_depth)
        self.metrics["component_overlap_count"] = len(self.find_overlaps())
        return {"ok": not failed and not self.find_overlaps(), "moved": moved, "failed": failed}

    def _legalize_ref(self, ref: str, *, moved: list[dict[str, Any]], failed: list[str], depth: int, max_depth: int) -> None:
        if depth > max_depth:
            failed.append(ref)
            return
        active = self.components[ref]
        active_priority = float(active.get("priority", 0.0)) + (1000.0 if depth == 0 else 0.0)
        for blocker_ref in self.find_blockers(ref):
            blocker = self.components[blocker_ref]
            if blocker.get("locked"):
                failed.append(blocker_ref)
                continue
            if float(blocker.get("priority", 0.0)) >= active_priority:
                failed.append(blocker_ref)
                continue
            slot = self._nearest_legal_slot(blocker_ref, avoid_ref=ref)
            if slot is None:
                failed.append(blocker_ref)
                continue
            before = list(blocker.get("at", [0.0, 0.0]))
            self.apply_move(blocker_ref, slot[0], slot[1])
            moved.append({"ref": blocker_ref, "from": before, "to": [slot[0], slot[1]], "reason": f"pushed_by:{ref}"})
            if self.find_blockers(blocker_ref):
                self._legalize_ref(blocker_ref, moved=moved, failed=failed, depth=depth + 1, max_depth=max_depth)

    def _nearest_legal_slot(self, ref: str, *, avoid_ref: str) -> Point | None:
        component = self.components[ref]
        original = self.component_center(ref)
        sheet_w = float(self.sheet.get("width", 420.0))
        sheet_h = float(self.sheet.get("height", 297.0))
        margin = float(self.sheet.get("margin", 15.24))
        step = self.grid
        candidates: list[Point] = []
        for radius in (10.16, 20.32, 30.48, 40.64, 60.96, 81.28, 101.6):
            for dx, dy in ((radius, 0), (-radius, 0), (0, radius), (0, -radius), (radius, radius), (-radius, radius), (radius, -radius), (-radius, -radius)):
                x = snap(original[0] + dx, step)
                y = snap(original[1] + dy, step)
                if margin <= x <= sheet_w - margin and margin <= y <= sheet_h - margin:
                    candidates.append((x, y))
        for x, y in sorted(candidates, key=lambda item: abs(item[0] - original[0]) + abs(item[1] - original[1])):
            old_at = list(component["at"])
            self.apply_move(ref, x, y)
            blockers = self.find_blockers(ref)
            out_of_sheet = self._component_out_of_sheet(ref)
            component["at"] = old_at
            self.recompute_component_body(ref)
            self.recompute_component_keepout(ref)
            self.recompute_component_pin_anchors(ref)
            self._recompute_net_endpoints()
            if not blockers and not out_of_sheet:
                return (x, y)
        return None

    def _component_out_of_sheet(self, ref: str) -> bool:
        keepout = self.components[ref]["keepout"]
        margin = float(self.sheet.get("margin", 15.24))
        return (
            keepout["left"] < margin
            or keepout["top"] < margin
            or keepout["right"] > float(self.sheet.get("width", 420.0)) - margin
            or keepout["bottom"] > float(self.sheet.get("height", 297.0)) - margin
        )

    def score_fast(self) -> dict[str, Any]:
        hpwl = 0.0
        weighted_hpwl = 0.0
        for net_name, net in self.nets.items():
            points = [tuple(endpoint["point"]) for endpoint in net.get("endpoints", []) if isinstance(endpoint.get("point"), list)]
            if len(points) < 2:
                continue
            raw = (max(point[0] for point in points) - min(point[0] for point in points)) + (
                max(point[1] for point in points) - min(point[1] for point in points)
            )
            hpwl += raw
            weighted_hpwl += raw * net_weight(str(net.get("class") or classify_net(net_name)))
        overlap_count = len(self.find_overlaps())
        out_of_sheet = sum(1 for ref in self.components if self._component_out_of_sheet(ref))
        score = weighted_hpwl + overlap_count * 1_000_000.0 + out_of_sheet * 1_000_000.0
        return {
            "hpwl": round(hpwl, 3),
            "weighted_hpwl": round(weighted_hpwl, 3),
            "component_overlap_count": overlap_count,
            "out_of_sheet_count": out_of_sheet,
            "score": round(score, 3),
        }

    def score_routeability(self) -> dict[str, Any]:
        score = self.score_fast()
        score["median_cluster_centers"] = {
            net_name: self._net_median_center(net)
            for net_name, net in self.nets.items()
            if len(net.get("endpoints", [])) >= 2
        }
        return score

    def _net_median_center(self, net: dict[str, Any]) -> list[float]:
        points = [endpoint["point"] for endpoint in net.get("endpoints", []) if isinstance(endpoint.get("point"), list)]
        return [round(float(median(point[0] for point in points)), 3), round(float(median(point[1] for point in points)), 3)]

    def to_coordinate_plan(self) -> dict[str, Any]:
        edits: list[dict[str, Any]] = []
        source_components = self.source_placement.get("components", {})
        if not isinstance(source_components, dict):
            source_components = {}
        for ref, component in sorted(self.components.items()):
            original = source_components.get(ref, {}) if isinstance(source_components.get(ref), dict) else {}
            original_at = _point_from_raw(original.get("at"), self.component_center(ref))
            current_at = self.component_center(ref)
            original_rotation = int(float(original.get("rotation", 0) or 0)) % 360
            current_rotation = int(component.get("rotation", 0)) % 360
            if abs(original_at[0] - current_at[0]) > 0.001 or abs(original_at[1] - current_at[1]) > 0.001 or original_rotation != current_rotation:
                edits.append(
                    {
                        "ref": ref,
                        "from": [round(original_at[0], 3), round(original_at[1], 3)],
                        "to": [round(current_at[0], 3), round(current_at[1], 3)],
                        "rotation": current_rotation,
                        "reason": "live_routing_state_selected_position",
                    }
                )
        return {
            "schema": "progen-kicad-coordinate-plan/v0.2",
            "stage": "live_routing_state",
            "coordinate_edits": edits,
            "metrics": self.score_fast(),
        }

    def to_routing_placement(self) -> dict[str, Any]:
        return {
            "schema": "progen-kicad-routing-placement/v0.2",
            "components": {
                ref: {
                    "kind": component.get("kind"),
                    "type_id": component.get("type_id"),
                    "name": component.get("name", ref),
                    "at": list(component.get("at", [0.0, 0.0])),
                    "rotation": component.get("rotation", 0),
                    "width": component["body"]["right"] - component["body"]["left"],
                    "height": component["body"]["bottom"] - component["body"]["top"],
                    "category": component.get("category"),
                    "locked": bool(component.get("locked", False)),
                    "priority": component.get("priority", 0),
                }
                for ref, component in sorted(self.components.items())
            },
            "obstacles": [
                {
                    "owner": ref,
                    "component_ref": ref,
                    "left": component["body"]["left"],
                    "top": component["body"]["top"],
                    "right": component["body"]["right"],
                    "bottom": component["body"]["bottom"],
                }
                for ref, component in sorted(self.components.items())
            ],
            "keepouts": [
                {
                    "owner": ref,
                    "component_ref": ref,
                    "left": component["keepout"]["left"],
                    "top": component["keepout"]["top"],
                    "right": component["keepout"]["right"],
                    "bottom": component["keepout"]["bottom"],
                }
                for ref, component in sorted(self.components.items())
            ],
            "pin_points": {
                ref: {
                    pin: {
                        "point": list(pin_data["point"]),
                        "side": pin_data.get("side"),
                        "type": pin_data.get("type"),
                        "roles": pin_data.get("roles", []),
                        "source": pin_data.get("source", "live_routing_state"),
                    }
                    for pin, pin_data in sorted(component.get("pins", {}).items())
                }
                for ref, component in sorted(self.components.items())
            },
        }


def _component_priority(component: dict[str, Any], connected_weight: float) -> float:
    hints = component.get("placement_hints", {})
    base = float(hints.get("push_priority", 30.0))
    role = str(hints.get("role", component.get("category", "")))
    if role in {"controller", "middle_logic", "power_block"}:
        base += 30.0
    if role in {"connector", "ground", "source"}:
        base -= 10.0
    return round(base + connected_weight, 3)


def build_live_routing_state(
    placement: dict[str, Any],
    circuit: dict[str, Any],
    *,
    component_catalogue: ComponentCatalogue | None = None,
    config: dict[str, Any] | None = None,
) -> LiveRoutingState:
    catalogue = component_catalogue or load_component_catalogue()
    config = config or {}
    sheet = dict(config.get("sheet") or {"width": 420.0, "height": 297.0, "margin": 15.24})
    components_by_ref = {
        str(item.get("id") or item.get("ref") or ""): item
        for item in circuit.get("components", [])
        if isinstance(item, dict) and (item.get("id") or item.get("ref"))
    }
    placement_components = placement.get("components", {})
    if not isinstance(placement_components, dict):
        placement_components = {}
    refs = sorted(set(components_by_ref) | set(str(ref) for ref in placement_components))
    nets_raw = extract_connection_nets(circuit)

    connected_weight_by_ref: dict[str, float] = {ref: 0.0 for ref in refs}
    for net_name, endpoints in nets_raw.items():
        weight = net_weight(classify_net(net_name))
        for endpoint in endpoints:
            connected_weight_by_ref[endpoint.ref] = connected_weight_by_ref.get(endpoint.ref, 0.0) + weight

    components: dict[str, dict[str, Any]] = {}
    for ref in refs:
        raw_component = components_by_ref.get(ref, {})
        placed = placement_components.get(ref, {}) if isinstance(placement_components.get(ref), dict) else {}
        kind = str(raw_component.get("kind") or placed.get("kind") or raw_component.get("name") or placed.get("name") or "GENERIC_COMPONENT")
        type_id = catalogue.resolve_type_id(kind)
        type_def = catalogue.get(type_id)
        body = type_def["body"]
        at = _point_from_raw(placed.get("at") if isinstance(placed, dict) else None, (0.0, 0.0))
        rotation = int(float(placed.get("rotation", raw_component.get("rotation", type_def.get("default_rotation", 0))) or 0)) % 360
        if rotation not in set(int(item) for item in type_def.get("legal_rotations", [0])):
            rotation = int(type_def.get("default_rotation", 0))
        pin_defs = deepcopy(type_def["pin_model"]["pins"])
        raw_pins = raw_component.get("pins", {})
        if isinstance(raw_pins, dict):
            lookup = _pin_lookup(pin_defs)
            for index, (pin_name, net_name) in enumerate(sorted(raw_pins.items())):
                key = str(pin_name)
                normalized = normalize_type_id(key)
                if key in pin_defs or normalized in pin_defs:
                    continue
                matched = lookup.get(key) or lookup.get(normalized)
                if matched:
                    pin_defs[key] = deepcopy(matched[1])
                    pin_defs[key]["source"] = f"alias:{matched[0]}"
                else:
                    pin_defs[key] = _fallback_pin_def(
                        key,
                        index,
                        len(raw_pins),
                        float(body["width"]),
                        float(body["height"]),
                        str(net_name),
                    )
                    pin_defs[key]["source"] = "circuit_pin_fallback"
        component = {
            "type_id": type_id,
            "kind": kind,
            "name": str(placed.get("name") or raw_component.get("name") or kind),
            "category": type_def.get("category", "generic"),
            "at": [snap(at[0], catalogue.grid), snap(at[1], catalogue.grid)],
            "rotation": rotation,
            "locked": bool(raw_component.get("locked") or placed.get("manual", False)),
            "legal_rotations": list(type_def.get("legal_rotations", [0, 90, 180, 270])),
            "catalogue_body": deepcopy(body),
            "pin_defs": pin_defs,
            "placement_hints": deepcopy(type_def.get("placement_hints", {})),
        }
        component["priority"] = _component_priority(component, connected_weight_by_ref.get(ref, 0.0))
        components[ref] = component

    state = LiveRoutingState(
        schema="progen-live-routing-state/v0.2",
        unit="mm",
        grid=catalogue.grid,
        sheet={key: float(value) for key, value in sheet.items()},
        components=components,
        nets={},
        routes={},
        metrics={},
        source_placement=deepcopy(placement),
    )
    for ref in sorted(state.components):
        state.recompute_component_body(ref)
        state.recompute_component_keepout(ref)
        state.recompute_component_pin_anchors(ref)

    nets: dict[str, dict[str, Any]] = {}
    for net_name, endpoints in sorted(nets_raw.items()):
        net_class = classify_net(net_name)
        nets[net_name] = {
            "class": net_class,
            "weight": net_weight(net_class),
            "endpoint_refs": [{"ref": endpoint.ref, "pin": endpoint.pin} for endpoint in endpoints],
            "endpoints": [],
            "fanout": 0,
            "criticality": int(net_weight(net_class)),
        }
    state.nets = nets
    state._recompute_net_endpoints()
    state.metrics = state.score_fast()
    return state
