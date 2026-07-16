"""Hosted parser for the generated KiCad PCB subset."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kicad.generator.kicad_backend.sexpr import paren_balance
from kicad.pipeline.kicad_symbol_library import _balanced_block, _child_head, _direct_child_blocks


Point = tuple[float, float]


def _round_point(values: tuple[float, float]) -> Point:
    return (round(values[0], 4), round(values[1], 4))


def _numbers(block: str, token: str) -> tuple[float, ...]:
    match = re.search(rf"\({re.escape(token)}\s+([-0-9.]+)(?:\s+([-0-9.]+))?(?:\s+([-0-9.]+))?", block)
    if not match:
        return ()
    return tuple(float(value) for value in match.groups() if value is not None)


def _quoted(block: str, token: str) -> str:
    match = re.search(rf'\({re.escape(token)}\s+"((?:\\.|[^\"])*)"', block, re.S)
    return bytes(match.group(1), "utf-8").decode("unicode_escape") if match else ""


def _property(block: str, name: str) -> str:
    match = re.search(
        rf'\(property\s+"{re.escape(name)}"\s+"((?:\\.|[^\"])*)"',
        block,
        re.S,
    )
    return bytes(match.group(1), "utf-8").decode("unicode_escape") if match else ""


@dataclass(frozen=True)
class ParsedPad:
    ref: str
    number: str
    net_code: int
    net_name: str
    point: Point
    layers: tuple[str, ...]
    size: tuple[float, float]
    rotation: float
    mount_type: str
    drill: tuple[float, ...]

    @property
    def identity(self) -> str:
        return f"{self.ref}.{self.number}"


@dataclass(frozen=True)
class ParsedFootprint:
    library_id: str
    ref: str
    value: str
    at: Point
    rotation: float
    pads: tuple[ParsedPad, ...]


@dataclass(frozen=True)
class ParsedSegment:
    net_code: int
    net_name: str
    layer: str
    start: Point
    end: Point
    width: float


@dataclass(frozen=True)
class ParsedVia:
    net_code: int
    net_name: str
    at: Point
    size: float
    drill: float


@dataclass(frozen=True)
class ParsedPCB:
    path: Path
    nets: dict[int, str]
    footprints: tuple[ParsedFootprint, ...]
    segments: tuple[ParsedSegment, ...]
    vias: tuple[ParsedVia, ...]
    outline: tuple[float, float, float, float] | None
    file_validity: dict[str, Any]


def _world_pad(footprint_at: Point, footprint_rotation: float, pad_at: tuple[float, ...]) -> Point:
    local_x = pad_at[0] if len(pad_at) >= 1 else 0.0
    local_y = pad_at[1] if len(pad_at) >= 2 else 0.0
    angle = math.radians(footprint_rotation)
    return _round_point(
        (
            footprint_at[0] + local_x * math.cos(angle) - local_y * math.sin(angle),
            footprint_at[1] + local_x * math.sin(angle) + local_y * math.cos(angle),
        )
    )


def _parse_pad(block: str, *, ref: str, footprint_at: Point, footprint_rotation: float, nets: dict[int, str]) -> ParsedPad | None:
    match = re.match(r'\s*\(pad\s+"((?:\\.|[^\"])*)"\s+(\S+)\s+(\S+)', block, re.S)
    if not match:
        return None
    number = bytes(match.group(1), "utf-8").decode("unicode_escape")
    at = _numbers(block, "at")
    size = _numbers(block, "size")
    drill = _numbers(block, "drill")
    net_match = re.search(r"\(net\s+([0-9]+)(?:\s+\"((?:\\.|[^\"])*)\")?", block, re.S)
    net_code = int(net_match.group(1)) if net_match else 0
    net_name = bytes(net_match.group(2), "utf-8").decode("unicode_escape") if net_match and net_match.group(2) else nets.get(net_code, "")
    layers_match = re.search(r"\(layers\s+([^\)]+)\)", block)
    layers = tuple(re.findall(r'"([^"]+)"', layers_match.group(1))) if layers_match else ()
    if "*.Cu" in layers:
        layers = ("F.Cu", "B.Cu")
    else:
        layers = tuple(layer for layer in layers if layer in {"F.Cu", "B.Cu"})
    return ParsedPad(
        ref=ref,
        number=number,
        net_code=net_code,
        net_name=net_name or nets.get(net_code, ""),
        point=_world_pad(footprint_at, footprint_rotation, at),
        layers=layers or ("F.Cu",),
        size=tuple(size[:2] if len(size) >= 2 else (1.0, 1.0)),
        rotation=(footprint_rotation + (at[2] if len(at) >= 3 else 0.0)) % 360.0,
        mount_type=match.group(2),
        drill=tuple(drill[:2]),
    )


def parse_kicad_pcb(path: Path) -> ParsedPCB:
    text = path.read_text(encoding="utf-8")
    start = text.find("(kicad_pcb")
    root = _balanced_block(text, start) if start >= 0 else None
    balanced, balance_message = paren_balance(text)
    validity = {
        "exists": path.exists(),
        "root_present": start >= 0,
        "parentheses_balanced": balanced,
        "parentheses_message": balance_message,
        "version_present": bool(re.search(r"\(version\s+[0-9]+\)", text)),
    }
    validity["ok"] = bool(validity["exists"] and validity["root_present"] and validity["parentheses_balanced"] and validity["version_present"])
    if root is None:
        return ParsedPCB(path, {}, (), (), (), None, validity)
    top = _direct_child_blocks(root)
    nets: dict[int, str] = {}
    for block in top:
        if _child_head(block) != "net":
            continue
        match = re.match(r'\s*\(net\s+([0-9]+)\s+"((?:\\.|[^\"])*)"', block, re.S)
        if match:
            nets[int(match.group(1))] = bytes(match.group(2), "utf-8").decode("unicode_escape")

    footprints: list[ParsedFootprint] = []
    segments: list[ParsedSegment] = []
    vias: list[ParsedVia] = []
    outline: tuple[float, float, float, float] | None = None
    for block in top:
        head = _child_head(block)
        if head == "footprint":
            match = re.match(r'\s*\(footprint\s+"((?:\\.|[^\"])*)"', block, re.S)
            library_id = bytes(match.group(1), "utf-8").decode("unicode_escape") if match else ""
            at = _numbers(block, "at")
            footprint_at = _round_point((at[0], at[1])) if len(at) >= 2 else (0.0, 0.0)
            rotation = at[2] if len(at) >= 3 else 0.0
            ref = _property(block, "Reference")
            pads = tuple(
                pad
                for child in _direct_child_blocks(block)
                if _child_head(child) == "pad"
                for pad in [_parse_pad(child, ref=ref, footprint_at=footprint_at, footprint_rotation=rotation, nets=nets)]
                if pad is not None
            )
            footprints.append(
                ParsedFootprint(
                    library_id=library_id,
                    ref=ref,
                    value=_property(block, "Value"),
                    at=footprint_at,
                    rotation=rotation,
                    pads=pads,
                )
            )
        elif head == "segment":
            start_values = _numbers(block, "start")
            end_values = _numbers(block, "end")
            net_values = _numbers(block, "net")
            if len(start_values) >= 2 and len(end_values) >= 2 and net_values:
                net_code = int(net_values[0])
                segments.append(
                    ParsedSegment(
                        net_code=net_code,
                        net_name=nets.get(net_code, ""),
                        layer=_quoted(block, "layer"),
                        start=_round_point((start_values[0], start_values[1])),
                        end=_round_point((end_values[0], end_values[1])),
                        width=float((_numbers(block, "width") or (0.25,))[0]),
                    )
                )
        elif head == "via":
            at = _numbers(block, "at")
            net_values = _numbers(block, "net")
            if len(at) >= 2 and net_values:
                net_code = int(net_values[0])
                vias.append(
                    ParsedVia(
                        net_code=net_code,
                        net_name=nets.get(net_code, ""),
                        at=_round_point((at[0], at[1])),
                        size=float((_numbers(block, "size") or (0.8,))[0]),
                        drill=float((_numbers(block, "drill") or (0.4,))[0]),
                    )
                )
        elif head == "gr_rect" and '(layer "Edge.Cuts")' in block:
            start_values = _numbers(block, "start")
            end_values = _numbers(block, "end")
            if len(start_values) >= 2 and len(end_values) >= 2:
                outline = (
                    min(start_values[0], end_values[0]),
                    min(start_values[1], end_values[1]),
                    max(start_values[0], end_values[0]),
                    max(start_values[1], end_values[1]),
                )
    return ParsedPCB(path, nets, tuple(footprints), tuple(segments), tuple(vias), outline, validity)
