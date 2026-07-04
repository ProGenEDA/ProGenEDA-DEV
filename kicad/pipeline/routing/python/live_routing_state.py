"""Mathematical live routing state.

This module is the Python implementation of the PDF's temporary catalogue /
LiveRoutingState contract. It does not know how to write KiCad files. It stores
component positions, rotations, bodies, keepouts, resolved pin anchors, nets,
routes, and metrics in a backend-neutral JSON shape.
"""

from __future__ import annotations

from collections import defaultdict
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
SIDE_VECTORS: dict[str, Point] = {
    "left": (-1.0, 0.0),
    "right": (1.0, 0.0),
    "top": (0.0, -1.0),
    "bottom": (0.0, 1.0),
}


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


def _manhattan(left: Point, right: Point) -> float:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])


def _side_faces_point(side: str, source: Point, target: Point) -> bool:
    vector = SIDE_VECTORS.get(str(side).lower(), SIDE_VECTORS["right"])
    delta = (target[0] - source[0], target[1] - source[1])
    return vector[0] * delta[0] + vector[1] * delta[1] > 0.0


def _bus_sort_key(pin: str) -> tuple[str, int, str]:
    prefix = "".join(ch for ch in pin if not ch.isdigit())
    digits = "".join(ch for ch in pin if ch.isdigit())
    return (prefix, int(digits) if digits else 0, pin)


def _inversion_count(values: list[float]) -> int:
    inversions = 0
    for index, left in enumerate(values):
        for right in values[index + 1 :]:
            if left > right:
                inversions += 1
    return inversions


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
        score["pin_facing_penalty"] = round(self.score_pin_facing(), 3)
        score["bus_order_penalty"] = round(self.score_bus_alignment(), 3)
        score["power_ground_side_penalty"] = round(self.score_power_ground_sides(), 3)
        score["score"] = round(
            float(score["score"])
            + score["pin_facing_penalty"] * 10.0
            + score["bus_order_penalty"] * 25.0
            + score["power_ground_side_penalty"] * 20.0,
            3,
        )
        return score

    def _net_median_center(self, net: dict[str, Any]) -> list[float]:
        points = [endpoint["point"] for endpoint in net.get("endpoints", []) if isinstance(endpoint.get("point"), list)]
        return [round(float(median(point[0] for point in points)), 3), round(float(median(point[1] for point in points)), 3)]

    def build_component_graph(self) -> dict[str, dict[str, float]]:
        graph: dict[str, dict[str, float]] = {ref: {} for ref in self.components}
        for net_name, net in self.nets.items():
            endpoints = net.get("endpoint_refs") or net.get("endpoints") or []
            refs = sorted({str(endpoint.get("ref") or "") for endpoint in endpoints if isinstance(endpoint, dict) and endpoint.get("ref")})
            if len(refs) < 2:
                continue
            weight = float(net.get("weight", net_weight(classify_net(net_name))))
            fanout_discount = max(1.0, (len(refs) - 1) ** 0.5)
            for index, left in enumerate(refs):
                for right in refs[index + 1 :]:
                    edge_weight = weight / fanout_discount
                    graph.setdefault(left, {})[right] = graph.setdefault(left, {}).get(right, 0.0) + edge_weight
                    graph.setdefault(right, {})[left] = graph.setdefault(right, {}).get(left, 0.0) + edge_weight
        return graph

    def select_pivot(self, *, user_primary_ref: str | None = None) -> str:
        graph = self.build_component_graph()
        scores: dict[str, float] = {}
        for ref, component in self.components.items():
            weighted_degree = sum(graph.get(ref, {}).values())
            bus_endpoint_count = 0
            clock_endpoint_count = 0
            large_fanout_control_count = 0
            power_only = True
            for net_name, net in self.nets.items():
                refs = {str(endpoint.get("ref") or "") for endpoint in net.get("endpoint_refs", []) if isinstance(endpoint, dict)}
                if ref not in refs:
                    continue
                net_class = str(net.get("class") or classify_net(net_name))
                if net_class not in {"power", "ground"}:
                    power_only = False
                if net_class == "bus":
                    bus_endpoint_count += 1
                if net_class == "clock_control":
                    clock_endpoint_count += 1
                    if int(net.get("fanout", 0)) >= 4:
                        large_fanout_control_count += 1
            score = (
                weighted_degree * 10.0
                + bus_endpoint_count * 6.0
                + clock_endpoint_count * 8.0
                + large_fanout_control_count * 5.0
                + (40.0 if component.get("locked") else 0.0)
                + (100.0 if user_primary_ref and ref == user_primary_ref else 0.0)
                - (25.0 if power_only else 0.0)
                + float(component.get("priority", 0.0)) * 0.1
            )
            scores[ref] = round(score, 3)
        self.metrics["pivot_scores"] = dict(sorted(scores.items()))
        if not scores:
            return ""
        return min(scores, key=lambda ref: (-scores[ref], ref))

    def select_next_component(self, placed_refs: set[str]) -> str:
        graph = self.build_component_graph()
        candidates = sorted(set(self.components) - placed_refs)
        if not candidates:
            return ""

        def score(ref: str) -> tuple[float, float, str]:
            cluster_weight = sum(graph.get(ref, {}).get(placed, 0.0) for placed in placed_refs)
            return (-cluster_weight, -float(self.components[ref].get("priority", 0.0)), ref)

        return min(candidates, key=score)

    def _connected_placed_points(self, ref: str, placed_refs: set[str]) -> list[Point]:
        points: list[Point] = []
        for net in self.nets.values():
            endpoint_refs = net.get("endpoint_refs", [])
            if not any(isinstance(endpoint, dict) and endpoint.get("ref") == ref for endpoint in endpoint_refs):
                continue
            for endpoint in endpoint_refs:
                if not isinstance(endpoint, dict):
                    continue
                other_ref = str(endpoint.get("ref") or "")
                if other_ref not in placed_refs:
                    continue
                pin_name = str(endpoint.get("pin") or "")
                pin = self.components.get(other_ref, {}).get("pins", {}).get(pin_name)
                if isinstance(pin, dict):
                    points.append(_point_from_raw(pin.get("point"), self.component_center(other_ref)))
                elif other_ref in self.components:
                    points.append(self.component_center(other_ref))
        return points

    def generate_candidate_locations(self, ref: str, placed_refs: set[str], config: dict[str, Any]) -> list[Point]:
        placement_cfg = config.get("placement", {}) if isinstance(config.get("placement"), dict) else {}
        limit = max(1, int(placement_cfg.get("candidate_locations_per_component", 24)))
        component = self.components[ref]
        current = self.component_center(ref)
        anchors = self._connected_placed_points(ref, placed_refs)
        if not anchors and placed_refs:
            anchors = [self.component_center(placed) for placed in sorted(placed_refs) if placed in self.components]
        if not anchors:
            anchors = [current]
        center = (
            snap(float(median(point[0] for point in anchors)), self.grid),
            snap(float(median(point[1] for point in anchors)), self.grid),
        )
        body = component.get("catalogue_body", {})
        spacing = float(component.get("placement_hints", {}).get("default_spacing", 10.16))
        x_step = snap(float(body.get("width", 10.0)) + spacing, self.grid)
        y_step = snap(float(body.get("height", 8.0)) + spacing, self.grid)
        sheet_w = float(self.sheet.get("width", 420.0))
        sheet_h = float(self.sheet.get("height", 297.0))
        margin = float(self.sheet.get("margin", 15.24))
        raw: list[Point] = [current, center]
        seeds = [center, *anchors[: max(1, min(len(anchors), 6))]]
        multipliers = (1.0, 1.5, 2.0)
        directions = (
            (1.0, 0.0),
            (-1.0, 0.0),
            (0.0, 1.0),
            (0.0, -1.0),
            (1.0, 1.0),
            (1.0, -1.0),
            (-1.0, 1.0),
            (-1.0, -1.0),
        )
        for seed in seeds:
            for multiplier in multipliers:
                for dx, dy in directions:
                    raw.append((snap(seed[0] + dx * x_step * multiplier, self.grid), snap(seed[1] + dy * y_step * multiplier, self.grid)))
        seen: set[Point] = set()
        candidates: list[Point] = []
        for point in raw:
            if point in seen:
                continue
            seen.add(point)
            if margin <= point[0] <= sheet_w - margin and margin <= point[1] <= sheet_h - margin:
                candidates.append(point)
        candidates.sort(key=lambda point: (_manhattan(point, center), _manhattan(point, current), point[1], point[0]))
        return candidates[:limit]

    def score_pin_facing(self) -> float:
        penalty = 0.0
        for net_name, net in self.nets.items():
            endpoints = [endpoint for endpoint in net.get("endpoints", []) if isinstance(endpoint, dict)]
            if len(endpoints) < 2:
                continue
            weight = float(net.get("weight", net_weight(classify_net(net_name))))
            for endpoint in endpoints:
                point = _point_from_raw(endpoint.get("point"))
                side = str(endpoint.get("side") or "right")
                for other in endpoints:
                    if endpoint is other:
                        continue
                    other_ref = str(other.get("ref") or "")
                    if other_ref not in self.components:
                        continue
                    target = self.component_center(other_ref)
                    if not _side_faces_point(side, point, target):
                        penalty += weight
        return penalty

    def score_power_ground_sides(self) -> float:
        penalty = 0.0
        for component in self.components.values():
            for pin in component.get("pins", {}).values():
                if not isinstance(pin, dict):
                    continue
                roles = {str(role).lower() for role in pin.get("roles", [])}
                pin_type = str(pin.get("type", "")).lower()
                side = str(pin.get("side", ""))
                if ("power" in roles or pin_type == "power") and side != "top":
                    penalty += 1.0
                if ("ground" in roles or pin_type == "ground") and side != "bottom":
                    penalty += 1.0
        return penalty

    def score_bus_alignment(self) -> float:
        penalty = 0.0
        for ref, component in self.components.items():
            hints = component.get("routing_hints", {})
            bus_groups = hints.get("bus_groups", []) if isinstance(hints, dict) else []
            if not isinstance(bus_groups, list):
                continue
            for group in bus_groups:
                if not isinstance(group, dict):
                    continue
                pins = [str(pin) for pin in group.get("pins", []) if str(pin) in component.get("pins", {})]
                if len(pins) < 2:
                    continue
                target_positions: list[tuple[str, float]] = []
                for pin in sorted(pins, key=_bus_sort_key):
                    for net in self.nets.values():
                        endpoints = net.get("endpoints", [])
                        if not any(isinstance(endpoint, dict) and endpoint.get("ref") == ref and endpoint.get("pin") == pin for endpoint in endpoints):
                            continue
                        others = [endpoint for endpoint in endpoints if isinstance(endpoint, dict) and endpoint.get("ref") != ref]
                        if not others:
                            continue
                        axis_value = float(median(float(endpoint.get("point", [0.0, 0.0])[1]) for endpoint in others))
                        target_positions.append((pin, axis_value))
                        break
                if len(target_positions) >= 2:
                    penalty += _inversion_count([value for _pin, value in target_positions])
        return penalty

    def score_location_rotation(self, ref: str, location: Point, rotation: int | float) -> dict[str, Any]:
        candidate = self.clone_state()
        candidate.apply_move_rotation(ref, location[0], location[1], rotation)
        fast = candidate.score_fast()
        pin_facing = candidate.score_pin_facing()
        bus_order = candidate.score_bus_alignment()
        power_ground = candidate.score_power_ground_sides()
        rotation_cost = 0.0 if int(rotation) % 360 == int(self.components[ref].get("rotation", 0)) % 360 else 1.0
        lower_bound = (
            float(fast["weighted_hpwl"])
            + int(fast["component_overlap_count"]) * 1_000_000.0
            + int(fast["out_of_sheet_count"]) * 1_000_000.0
            + pin_facing * 10.0
            + bus_order * 25.0
            + power_ground * 20.0
            + rotation_cost * 2.0
        )
        return {
            "ref": ref,
            "at": [location[0], location[1]],
            "rotation": int(rotation) % 360,
            "hpwl": fast["hpwl"],
            "weighted_hpwl": fast["weighted_hpwl"],
            "overlap_count": fast["component_overlap_count"],
            "out_of_sheet": bool(fast["out_of_sheet_count"]),
            "pin_facing_penalty": round(pin_facing, 3),
            "bus_misalignment": round(bus_order, 3),
            "power_ground_side_penalty": round(power_ground, 3),
            "rotation_cost": rotation_cost,
            "lower_bound_score": round(lower_bound, 3),
        }

    @staticmethod
    def pareto_prune_candidates(candidates: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
        survivors: list[dict[str, Any]] = []
        metrics = ("weighted_hpwl", "overlap_count", "pin_facing_penalty", "bus_misalignment", "power_ground_side_penalty")
        for candidate in candidates:
            dominated = False
            for other in candidates:
                if other is candidate:
                    continue
                no_worse = all(float(other.get(metric, 0.0)) <= float(candidate.get(metric, 0.0)) for metric in metrics)
                strictly_better = any(float(other.get(metric, 0.0)) < float(candidate.get(metric, 0.0)) for metric in metrics)
                if no_worse and strictly_better and not other.get("out_of_sheet", False):
                    dominated = True
                    break
            if not dominated:
                survivors.append(candidate)
        survivors.sort(key=lambda item: (float(item.get("lower_bound_score", 1.0e99)), str(item.get("ref", "")), item.get("rotation", 0), item.get("at", [0, 0])))
        return survivors[:limit]

    def legalize_candidate(self, ref: str, location: Point, rotation: int | float, config: dict[str, Any]) -> tuple["LiveRoutingState | None", dict[str, Any]]:
        legalization = config.get("legalization", {}) if isinstance(config.get("legalization"), dict) else {}
        max_depth = int(legalization.get("max_depth", 3))
        candidate = self.clone_state()
        original_priority = float(candidate.components[ref].get("priority", 0.0))
        boost = float(legalization.get("active_component_priority_boost", 1000.0))
        candidate.components[ref]["priority"] = original_priority + boost
        try:
            candidate.apply_move_rotation(ref, location[0], location[1], rotation)
            report = candidate.legalize_after_move(ref, max_depth=max_depth)
        finally:
            if ref in candidate.components:
                candidate.components[ref]["priority"] = original_priority
        failed = list(report.get("failed", []))
        out_of_sheet = [item_ref for item_ref in candidate.components if candidate._component_out_of_sheet(item_ref)]
        if failed or out_of_sheet or candidate.find_overlaps():
            report = dict(report)
            report["out_of_sheet"] = sorted(out_of_sheet)
            report["ok"] = False
            return None, report
        report = dict(report)
        report["ok"] = True
        report["out_of_sheet"] = []
        return candidate, report

    def beam_search_cluster_growth(self, config: dict[str, Any]) -> dict[str, Any]:
        placement_cfg = config.get("placement", {}) if isinstance(config.get("placement"), dict) else {}
        component_count = len(self.components)
        beam_width = max(1, int(placement_cfg.get("beam_width", 12)))
        max_states = max(1, int(placement_cfg.get("max_candidate_states_per_step", 128)))
        rotations_keep = max(1, int(placement_cfg.get("rotations_per_location_keep", 2)))
        deep_route_top_n = max(1, int(placement_cfg.get("deep_route_top_n", 4)))
        if component_count >= 90:
            beam_width = min(beam_width, 4)
            max_states = min(max_states, 48)
            rotations_keep = min(rotations_keep, 1)

        pivot = self.select_pivot(user_primary_ref=placement_cfg.get("user_primary_ref"))
        if not pivot:
            return {
                "selected_state": self,
                "final_states": [self],
                "report": {"pivot": "", "order": [], "variants": [], "selected_variant": "empty_state"},
            }
        order = [pivot]
        placed_for_order = {pivot}
        while len(order) < len(self.components):
            nxt = self.select_next_component(placed_for_order)
            if not nxt:
                break
            order.append(nxt)
            placed_for_order.add(nxt)

        beam: list[LiveRoutingState] = [self.clone_state()]
        placed_cluster: set[str] = {pivot}
        best_full_score = float(self.score_routeability()["score"])
        step_reports: list[dict[str, Any]] = []
        for step_index, ref in enumerate(order[1:], start=1):
            next_states: list[tuple[float, LiveRoutingState, dict[str, Any]]] = []
            candidate_reports: list[dict[str, Any]] = []
            for beam_index, state in enumerate(beam):
                if state.components.get(ref, {}).get("locked"):
                    score = float(state.score_routeability()["score"])
                    next_states.append((score, state, {"ref": ref, "status": "locked_kept", "beam_index": beam_index}))
                    continue
                candidate_locations = state.generate_candidate_locations(ref, placed_cluster, config)
                scored: list[dict[str, Any]] = []
                legal_rotations = [int(rotation) for rotation in state.components[ref].get("legal_rotations", [0])]
                for location in candidate_locations:
                    rotation_scores = [state.score_location_rotation(ref, location, rotation) for rotation in legal_rotations]
                    rotation_scores.sort(key=lambda item: (float(item["lower_bound_score"]), item["rotation"]))
                    scored.extend(rotation_scores[:rotations_keep])
                scored = state.pareto_prune_candidates(scored, limit=max_states)
                for candidate in scored:
                    if float(candidate["lower_bound_score"]) > best_full_score * 1.35 and len(next_states) >= beam_width:
                        candidate_reports.append({**candidate, "status": "branch_bound_pruned"})
                        continue
                    candidate_state, legalization_report = state.legalize_candidate(
                        ref,
                        _point_from_raw(candidate["at"]),
                        int(candidate["rotation"]),
                        config,
                    )
                    if candidate_state is None:
                        candidate_reports.append({**candidate, "status": "legalization_failed", "legalization": legalization_report})
                        continue
                    routeability = candidate_state.score_routeability()
                    score = float(routeability["score"])
                    best_full_score = min(best_full_score, score)
                    next_states.append(
                        (
                            score,
                            candidate_state,
                            {
                                **candidate,
                                "status": "accepted",
                                "routeability": routeability,
                                "legalization": legalization_report,
                                "beam_index": beam_index,
                            },
                        )
                    )
                    candidate_reports.append({**candidate, "status": "accepted", "score": round(score, 3)})
            if not next_states:
                beam = [state.clone_state() for state in beam[:beam_width]]
                step_reports.append({"step": step_index, "ref": ref, "accepted_count": 0, "candidate_count": len(candidate_reports), "fallback": "kept_previous_beam"})
            else:
                next_states.sort(key=lambda item: (item[0], item[2].get("rotation", 0), str(item[2].get("ref", ""))))
                beam = [item[1] for item in next_states[:beam_width]]
                step_reports.append(
                    {
                        "step": step_index,
                        "ref": ref,
                        "accepted_count": len(next_states),
                        "candidate_count": len(candidate_reports),
                        "best_score": round(next_states[0][0], 3),
                        "best_candidate": next_states[0][2],
                    }
                )
            placed_cluster.add(ref)

        beam.sort(key=lambda state: float(state.score_routeability()["score"]))
        final_states = beam[:deep_route_top_n]
        variants = [
            {
                "name": f"beam_state_{index}",
                "score": state.score_routeability(),
                "coordinate_edit_count": len(state.to_coordinate_plan().get("coordinate_edits", [])),
            }
            for index, state in enumerate(final_states)
        ]
        return {
            "selected_state": final_states[0] if final_states else self,
            "final_states": final_states or [self],
            "report": {
                "schema": "progen-kicad-live-state-beam-search/v0.2",
                "strategy": "pivot_cluster_growth_rotation_aware_legalized_beam",
                "pivot": pivot,
                "order": order,
                "beam_width": beam_width,
                "deep_route_top_n": deep_route_top_n,
                "step_reports": step_reports,
                "selected_variant": "beam_state_0",
                "variants": variants,
            },
        }

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
        source_backed_type = type_id in catalogue.components
        type_def = catalogue.get(type_id)
        body = type_def["body"]
        at = _point_from_raw(placed.get("at") if isinstance(placed, dict) else None, (0.0, 0.0))
        rotation = int(float(placed.get("rotation", raw_component.get("rotation", type_def.get("default_rotation", 0))) or 0)) % 360
        if rotation not in set(int(item) for item in type_def.get("legal_rotations", [0])):
            rotation = int(type_def.get("default_rotation", 0))
        pin_defs = deepcopy(type_def["pin_model"]["pins"])
        raw_pins = raw_component.get("pins", {})
        if isinstance(raw_pins, dict) and len(raw_pins) > len(pin_defs) and not source_backed_type:
            pin_defs = {}
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
            "routing_hints": deepcopy(type_def.get("routing_hints", {})),
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
