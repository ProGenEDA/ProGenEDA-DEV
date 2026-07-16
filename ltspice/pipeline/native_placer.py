"""Donor-native stock-symbol placer and temporary live-catalogue builder.

The coordinate model follows the KiCad live-routing-state idea, but every
number here is an LTspice ASC grid coordinate and every pin comes from the
permanent donor catalogue. The output has no terminal anchors or synthetic
symbol geometry.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from ltspice.catalogues.ltspice_main_catalogue_loader import NativeCatalogue, load_native_catalogue


NATIVE_PLACEMENT_SCHEMA = "progen-ltspice-donor-native-placement/v1"
NATIVE_LIVE_STATE_SCHEMA = "progen-ltspice-donor-native-live-routing-state/v1"


class NativePlacementError(ValueError):
    """A stock symbol cannot be placed without overlapping native geometry."""


_TRANSFORMS: dict[str, tuple[int, int, int, int]] = {
    "R0": (1, 0, 0, 1),
    "R90": (0, -1, 1, 0),
    "R180": (-1, 0, 0, -1),
    "R270": (0, 1, -1, 0),
    "M0": (-1, 0, 0, 1),
    "M90": (0, 1, 1, 0),
    "M180": (1, 0, 0, -1),
    "M270": (0, -1, -1, 0),
}
_SIDE_VECTORS = {"top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0)}
_SIDE_NAMES = {(0, -1): "top", (1, 0): "right", (0, 1): "bottom", (-1, 0): "left"}

# These are deliberately expressed in ASC grid increments rather than screen
# pixels.  They give stock source symbols and their display text a useful
# breathing room while retaining a compact, readable sheet at LTspice's
# fit-to-page zoom.  The old one-cell-per-graph-layer layout had no wrapping:
# a 20-part series chain became a four-thousand-unit horizontal strip and a
# 20-way shunt became a similarly tall vertical strip.
_AUTOMATIC_X_PITCH_GRIDS = 14
_AUTOMATIC_Y_PITCH_GRIDS = 13
_MAX_FLOW_COLUMNS = 7
_MAX_LAYER_ROWS = 4


def _transform(point: tuple[int, int], orientation: str) -> tuple[int, int]:
    a, b, c, d = _TRANSFORMS[orientation]
    x, y = point
    return a * x + b * y, c * x + d * y


def _point(origin: list[int], local: tuple[int, int], orientation: str) -> list[int]:
    dx, dy = _transform(local, orientation)
    return [origin[0] + dx, origin[1] + dy]


def _side(side: str, orientation: str) -> str:
    vector = _SIDE_VECTORS.get(side.lower(), (0, -1))
    transformed = _transform(vector, orientation)
    return _SIDE_NAMES.get(transformed, "top")


def _rect(definition: Mapping[str, Any], origin: list[int], orientation: str) -> dict[str, int]:
    bounds = definition["body"]["local_bounds"]
    corners = [
        (int(bounds["left"]), int(bounds["top"])),
        (int(bounds["left"]), int(bounds["bottom"])),
        (int(bounds["right"]), int(bounds["top"])),
        (int(bounds["right"]), int(bounds["bottom"])),
    ]
    transformed = [_point(origin, corner, orientation) for corner in corners]
    return {
        "left": min(item[0] for item in transformed),
        "right": max(item[0] for item in transformed),
        "top": min(item[1] for item in transformed),
        "bottom": max(item[1] for item in transformed),
    }


def _expand(rect: Mapping[str, int], amount: int) -> dict[str, int]:
    return {
        "left": int(rect["left"]) - amount,
        "right": int(rect["right"]) + amount,
        "top": int(rect["top"]) - amount,
        "bottom": int(rect["bottom"]) + amount,
    }


def _overlap(left: Mapping[str, int], right: Mapping[str, int]) -> bool:
    return not (
        int(left["right"]) < int(right["left"])
        or int(left["left"]) > int(right["right"])
        or int(left["bottom"]) < int(right["top"])
        or int(left["top"]) > int(right["bottom"])
    )


def _sheet_size(placed: Mapping[str, Mapping[str, Any]], grid: int) -> dict[str, int]:
    if not placed:
        return {"number": 1, "width": 880, "height": 680}
    max_right = max(int(item["body"]["right"]) for item in placed.values())
    max_bottom = max(int(item["body"]["bottom"]) for item in placed.values())
    width = max(880, int(math.ceil((max_right + grid * 8) / grid)) * grid)
    height = max(680, int(math.ceil((max_bottom + grid * 8) / grid)) * grid)
    return {"number": 1, "width": width, "height": height}


def _automatic_origin(index: int, population: int, grid: int) -> list[int]:
    """Use a stable sparse grid, then let the later router tighten only safely."""

    columns = max(1, math.ceil(math.sqrt(max(1, population))))
    x_pitch = grid * _AUTOMATIC_X_PITCH_GRIDS
    y_pitch = grid * _AUTOMATIC_Y_PITCH_GRIDS
    return [grid * 10 + (index % columns) * x_pitch, grid * 8 + (index // columns) * y_pitch]


def _topology_slots(native_circuit: Mapping[str, Any], physical: list[Mapping[str, Any]]) -> dict[str, tuple[int, int]]:
    """Turn the shared non-ground graph into a compact, wrapped flow layout.

    This is the first LTspice beautifier pass adapted from the KiCad
    arrangement idea: related components get nearby graph layers before the
    physical router spends any wire budget. Ground is intentionally ignored
    while building layers because a high-fanout return rail must not collapse
    every component into one placement column.
    """

    refs = [str(item["ref"]) for item in physical]
    order = {ref: index for index, ref in enumerate(refs)}
    adjacency: dict[str, set[str]] = {ref: set() for ref in refs}
    nets = native_circuit.get("nets")
    if isinstance(nets, Mapping):
        for raw in nets.values():
            details = raw if isinstance(raw, Mapping) else {}
            if bool(details.get("is_ground")):
                continue
            members = [
                str(endpoint).rsplit(".", 1)[0]
                for endpoint in details.get("members", [])
                if "." in str(endpoint)
            ]
            members = [ref for ref in members if ref in adjacency]
            for index, left in enumerate(members):
                for right in members[index + 1 :]:
                    adjacency[left].add(right)
                    adjacency[right].add(left)

    source_refs = {
        str(item["ref"])
        for item in physical
        if str(item.get("type_id") or "") in {"VOLTAGE_SOURCE", "CURRENT_SOURCE", "SIGNAL_SOURCE"}
    }

    # Find disconnected non-ground blocks first.  The prior global BFS made
    # twenty independent source/load demonstrations into one 7,000-unit-wide
    # strip.  A block retains its signal-flow layers, then the blocks tile in
    # a stable square-ish grid just like KiCad's arrangement stage.
    blocks: list[list[str]] = []
    unseen = set(refs)
    for seed in refs:
        if seed not in unseen:
            continue
        block: list[str] = []
        queue = [seed]
        unseen.remove(seed)
        while queue:
            current = queue.pop(0)
            block.append(current)
            for neighbour in sorted(adjacency[current], key=lambda ref: (order[ref], ref)):
                if neighbour in unseen:
                    unseen.remove(neighbour)
                    queue.append(neighbour)
        blocks.append(block)

    # Each graph layer is a small rectangle: a one-member series layer stays
    # one cell wide, while a large fan-out (for example twenty shunt
    # capacitors) folds into at most four rows.  Layer rectangles then flow
    # left-to-right and wrap.  This preserves the visual source-to-load
    # direction for ordinary circuits without producing long strips for
    # perfectly legal large donor fixtures.
    local_blocks: list[tuple[dict[str, tuple[int, int]], int, int]] = []
    for block in blocks:
        roots = [ref for ref in block if ref in source_refs]
        root = roots[0] if roots else block[0]
        layer = {root: 0}
        queue = [root]
        while queue:
            current = queue.pop(0)
            for neighbour in sorted(adjacency[current], key=lambda ref: (order[ref], ref)):
                if neighbour in layer:
                    continue
                layer[neighbour] = layer[current] + 1
                queue.append(neighbour)
        # A graph component is connected by construction; retain this
        # deterministic fallback for a malformed adjacency record rather than
        # producing an unset component coordinate.
        for ref in block:
            layer.setdefault(ref, 0)
        by_layer: dict[int, list[str]] = {}
        for ref in block:
            by_layer.setdefault(layer[ref], []).append(ref)
        local: dict[str, tuple[int, int]] = {}
        flow_x = 0
        flow_y = 0
        current_band_height = 0
        for _layer, members in sorted(by_layer.items()):
            ranked = sorted(members, key=lambda ref: (-len(adjacency[ref]), order[ref], ref))
            layer_rows = min(_MAX_LAYER_ROWS, len(ranked))
            layer_width = max(1, math.ceil(len(ranked) / layer_rows))
            if flow_x and flow_x + layer_width > _MAX_FLOW_COLUMNS:
                flow_x = 0
                flow_y += current_band_height
                current_band_height = 0
            for member_index, ref in enumerate(ranked):
                local[ref] = (
                    flow_x + member_index // layer_rows,
                    flow_y + member_index % layer_rows,
                )
            flow_x += layer_width
            current_band_height = max(current_band_height, layer_rows)
        local_blocks.append(
            (
                local,
                max(column for column, _row in local.values()) + 1,
                max(row for _column, row in local.values()) + 1,
            )
        )

    # Blocks have different logical dimensions (a source/load pair is 2x1;
    # a high fan-out can be 6x4).  Pack their real slot rectangles in a
    # square-ish matrix instead of using one oversized global cell.  This
    # removes the empty columns/rows visible in the prior source matrix.
    block_columns = max(1, math.ceil(math.sqrt(len(local_blocks))))
    column_widths = [0] * block_columns
    row_count = max(1, math.ceil(len(local_blocks) / block_columns))
    row_heights = [0] * row_count
    for index, (_slots, width, height) in enumerate(local_blocks):
        block_x = index % block_columns
        block_y = index // block_columns
        column_widths[block_x] = max(column_widths[block_x], width)
        row_heights[block_y] = max(row_heights[block_y], height)
    column_offsets: list[int] = []
    running_x = 0
    for width in column_widths:
        column_offsets.append(running_x)
        running_x += width
    row_offsets: list[int] = []
    running_y = 0
    for height in row_heights:
        row_offsets.append(running_y)
        running_y += height
    slots: dict[str, tuple[int, int]] = {}
    for index, (local, _width, _height) in enumerate(local_blocks):
        block_x = index % block_columns
        block_y = index // block_columns
        for ref, (column, row) in local.items():
            slots[ref] = (column_offsets[block_x] + column, row_offsets[block_y] + row)
    return slots


def place_native_components(
    native_circuit: Mapping[str, Any], *, catalogue: NativeCatalogue | None = None, arrange: bool = True
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Place only real stock symbols and resolve every physical pin anchor.

    With arrange false this is the deterministic initial grid. The separate
    beautifier then calls the same pin-accurate primitive with graph
    arrangement enabled, ensuring it changes coordinates/rotations only and
    never rewrites topology or properties.
    """

    active = catalogue or load_native_catalogue()
    raw_components = native_circuit.get("components")
    if not isinstance(raw_components, list):
        raise NativePlacementError("native circuit.components must be an array.")
    physical = [item for item in raw_components if isinstance(item, Mapping) and item.get("type_id") != "GROUND"]
    topology_slots = _topology_slots(native_circuit, physical) if arrange else {}
    placed: dict[str, dict[str, Any]] = {}
    keepouts: list[dict[str, Any]] = []
    warnings: list[str] = []

    for index, raw in enumerate(physical):
        ref = str(raw.get("ref") or "")
        type_id = str(raw.get("type_id") or "")
        if not ref or not type_id:
            raise NativePlacementError("Native component has no ref/type_id.")
        definition = active.get(type_id)
        orientation = str(raw.get("orientation") or definition["default_orientation"]).upper()
        # Donor evidence proves R90 for the three passive families. Horizontal
        # pins make graph layers readable and dramatically reduce unnecessary
        # physical detours. Explicit user orientation remains authoritative.
        if (
            arrange
            and raw.get("orientation_source") == "catalogue_default"
            and type_id in {"RESISTOR", "INDUCTOR"}
            and "R90" in definition["legal_orientations"]
        ):
            orientation = "R90"
        if orientation not in definition["legal_orientations"]:
            raise NativePlacementError(f"{ref} orientation {orientation!r} is not catalogue-approved.")
        origin = raw.get("ltspice_at")
        requested = isinstance(origin, list) and len(origin) == 2
        if requested:
            candidate = [int(origin[0]), int(origin[1])]
        else:
            if arrange:
                column, row = topology_slots.get(ref, (index, 0))
                candidate = [
                    active.grid * 10 + column * active.grid * _AUTOMATIC_X_PITCH_GRIDS,
                    active.grid * 8 + row * active.grid * _AUTOMATIC_Y_PITCH_GRIDS,
                ]
            else:
                candidate = _automatic_origin(index, len(physical), active.grid)
        attempts = 0
        while True:
            body = _rect(definition, candidate, orientation)
            keepout = _expand(body, int(definition["body"]["wire_clearance"]))
            if not any(_overlap(keepout, item["keepout"]) for item in keepouts):
                break
            if requested:
                raise NativePlacementError(f"{ref}.ltspice_at overlaps existing stock-symbol keepout.")
            candidate[0] += active.grid * _AUTOMATIC_X_PITCH_GRIDS
            attempts += 1
            if attempts > active.max_components_per_circuit * 3:
                raise NativePlacementError(f"Could not find a deterministic non-overlapping placement for {ref}.")
        if attempts:
            warnings.append(
                f"Shifted {ref} right by {attempts * active.grid * _AUTOMATIC_X_PITCH_GRIDS} ASC units "
                "to avoid a body keepout."
            )

        pins: dict[str, dict[str, Any]] = {}
        for pin_name, raw_pin in definition["pin_model"]["pins"].items():
            pin = dict(raw_pin)
            number = str(pin["number"])
            local = (int(pin["local"][0]), int(pin["local"][1]))
            pins[number] = {
                "number": number,
                "name": str(pin["name"]),
                "point": _point(candidate, local, orientation),
                "side": _side(str(pin["side"]), orientation),
                "type": str(pin["type"]),
                "roles": list(pin["roles"]),
            }
        record = {
            "ref": ref,
            "type_id": type_id,
            "native_symbol": str(definition["native"]["symbol"]),
            "origin": candidate,
            "orientation": orientation,
            "body": body,
            "keepout": keepout,
            "pins": pins,
            "properties": dict(raw.get("properties") or {}),
            "placement_evidence": dict(definition["placement_evidence"]),
        }
        placed[ref] = record
        keepouts.append({"ref": ref, "keepout": keepout})

    placement = {
        "schema": NATIVE_PLACEMENT_SCHEMA,
        "stage": "donor_native_component_placer",
        "arrangement": "graph_layered" if arrange else "initial_sparse_grid",
        "grid": active.grid,
        "sheet": _sheet_size(placed, active.grid),
        "components": placed,
        "component_count": len(raw_components),
        "physical_component_count": len(placed),
        "warnings": warnings,
    }
    report = {
        "schema": NATIVE_PLACEMENT_SCHEMA,
        "stage": "donor_native_component_placer",
        "ok": True,
        "arrangement": "graph_layered" if arrange else "initial_sparse_grid",
        "grid": active.grid,
        "sheet": placement["sheet"],
        "component_count": len(raw_components),
        "physical_component_count": len(placed),
        "terminal_fallback": "forbidden",
        "placed_components": [
            {
                "ref": item["ref"],
                "type_id": item["type_id"],
                "symbol": item["native_symbol"],
                "origin": item["origin"],
                "orientation": item["orientation"],
                "pins": item["pins"],
            }
            for item in placed.values()
        ],
        "warnings": warnings,
    }
    return placement, report


def native_live_state(
    native_circuit: Mapping[str, Any],
    placement: Mapping[str, Any],
    *,
    routes: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Serialize a temporary catalogue snapshot in the KiCad live-state spirit."""

    raw_components = placement.get("components")
    components = raw_components if isinstance(raw_components, Mapping) else {}
    nets_source = native_circuit.get("nets")
    nets: dict[str, Any] = {}
    if isinstance(nets_source, Mapping):
        for name, raw in nets_source.items():
            item = raw if isinstance(raw, Mapping) else {}
            nets[str(name)] = {
                "members": list(item.get("members") or []),
                "ground_refs": list(item.get("ground_refs") or []),
                "is_ground": bool(item.get("is_ground")),
                "fanout": len(item.get("members") or []),
            }
    route_data = dict(routes or {})
    return {
        "schema": NATIVE_LIVE_STATE_SCHEMA,
        "unit": "ltspice_asc_grid",
        "grid": placement.get("grid"),
        "sheet": dict(placement.get("sheet") or {}),
        "components": components,
        "nets": nets,
        "routes": route_data,
        "metrics": {
            "component_count": int(placement.get("component_count") or 0),
            "physical_component_count": int(placement.get("physical_component_count") or 0),
            "wire_count": len(route_data.get("wire_segments") or []),
            "ground_flag_count": len(route_data.get("ground_flags") or []),
        },
    }
