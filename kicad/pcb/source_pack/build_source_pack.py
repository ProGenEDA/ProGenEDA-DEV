"""Build the deterministic hosted KiCad PCB footprint source pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from kicad.pipeline.kicad_symbol_library import _child_head, _direct_child_blocks


PACK_SCHEMA = "progen-kicad-pcb-footprint-source-pack/v0.1"
KICAD_VERSION = "10.0.4"
KICAD_SOURCE_TAG = "10.0.4"

FIXED_FOOTPRINT_IDS = (
    "Resistor_THT:R_Axial_DIN0207_L6.3mm_D2.5mm_P7.62mm_Horizontal",
    "Capacitor_THT:C_Disc_D5.0mm_W2.5mm_P2.50mm",
    "Capacitor_THT:CP_Radial_D6.3mm_P2.50mm",
    "Diode_THT:D_DO-41_SOD81_P10.16mm_Horizontal",
    "LED_THT:LED_D5.0mm",
    "Package_DIP:DIP-8_W7.62mm",
    "Package_DIP:DIP-14_W7.62mm",
    "Package_DIP:DIP-16_W7.62mm",
    "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",
    "Package_TO_SOT_THT:TO-220-3_Vertical",
    "Package_TO_SOT_THT:TO-92_Inline",
    "TerminalBlock_Altech:Altech_AK100_1x02_P5.00mm",
    "Module:Arduino_Nano",
    "RF_Module:ESP32-WROOM-32",
)

DYNAMIC_HEADER_IDS = tuple(
    f"Connector_PinHeader_2.54mm:PinHeader_1x{count:02d}_P2.54mm_Vertical"
    for count in range(1, 21)
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _footprint_path(root: Path, footprint_id: str) -> Path:
    library, name = footprint_id.split(":", 1)
    return root / f"{library}.pretty" / f"{name}.kicad_mod"


def _quoted_head(block: str, head: str) -> str:
    match = re.match(rf"\s*\({re.escape(head)}\s+\"((?:\\.|[^\"])*)\"", block, re.S)
    return bytes(match.group(1), "utf-8").decode("unicode_escape") if match else ""


def _numbers(block: str, token: str) -> tuple[float, ...]:
    match = re.search(rf"\({re.escape(token)}\s+([-0-9.]+)(?:\s+([-0-9.]+))?(?:\s+([-0-9.]+))?", block)
    if not match:
        return ()
    return tuple(float(value) for value in match.groups() if value is not None)


def _parse_pad(block: str) -> dict[str, Any]:
    match = re.match(r'\s*\(pad\s+"((?:\\.|[^\"])*)"\s+(\S+)\s+(\S+)', block, re.S)
    if not match:
        raise ValueError("Unable to parse footprint pad")
    layers_match = re.search(r"\(layers\s+([^\)]+)\)", block)
    layers = re.findall(r'"([^"]+)"', layers_match.group(1)) if layers_match else []
    at = _numbers(block, "at")
    size = _numbers(block, "size")
    drill = _numbers(block, "drill")
    return {
        "number": bytes(match.group(1), "utf-8").decode("unicode_escape"),
        "mount_type": match.group(2),
        "shape": match.group(3),
        "at": list(at[:2] if len(at) >= 2 else (0.0, 0.0)),
        "rotation": float(at[2]) if len(at) >= 3 else 0.0,
        "size": list(size[:2] if len(size) >= 2 else (1.0, 1.0)),
        "drill": list(drill[:2] if len(drill) >= 2 else drill),
        "layers": layers,
    }


def _bounds(children: list[str], pads: list[dict[str, Any]]) -> dict[str, float]:
    points: list[tuple[float, float]] = []
    for block in children:
        if '(layer "F.CrtYd")' not in block:
            continue
        for match in re.finditer(r"\((?:start|end|mid|center|xy)\s+([-0-9.]+)\s+([-0-9.]+)", block):
            points.append((float(match.group(1)), float(match.group(2))))
    if not points:
        for pad in pads:
            x, y = pad["at"]
            width, height = pad["size"]
            points.extend(((x - width / 2, y - height / 2), (x + width / 2, y + height / 2)))
    if not points:
        points = [(-2.5, -2.5), (2.5, 2.5)]
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    margin = 0.5
    return {
        "min_x": round(min_x - margin, 4),
        "min_y": round(min_y - margin, 4),
        "max_x": round(max_x + margin, 4),
        "max_y": round(max_y + margin, 4),
        "width": round(max_x - min_x + 2 * margin, 4),
        "height": round(max_y - min_y + 2 * margin, 4),
    }


def _source_references(source_root: Path) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    if not source_root.exists():
        return references
    for path in sorted(source_root.glob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        references.append(
            {
                "path": f"pcbnew/pcb_io/kicad_sexpr/{path.name}",
                "bundled_path": str(path.relative_to(source_root.parent)),
                "sha256": _sha256(data),
                "size_bytes": len(data),
            }
        )
    return references


def build_source_pack(footprint_root: Path, output: Path) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for footprint_id in (*FIXED_FOOTPRINT_IDS, *DYNAMIC_HEADER_IDS):
        path = _footprint_path(footprint_root, footprint_id)
        if not path.exists():
            raise FileNotFoundError(f"Missing KiCad footprint source: {path}")
        source_text = path.read_text(encoding="utf-8")
        children = _direct_child_blocks(source_text)
        pads = [_parse_pad(block) for block in children if _child_head(block) == "pad"]
        records[footprint_id] = {
            "library_id": footprint_id,
            "source_file": str(path.relative_to(footprint_root)),
            "sha256": _sha256(source_text.encode("utf-8")),
            "source_name": _quoted_head(source_text, "footprint"),
            "bounds": _bounds(children, pads),
            "pad_count": len(pads),
            "pad_numbers": sorted({pad["number"] for pad in pads}),
            "pads": pads,
            "source_text": source_text,
        }
    source_root = Path(__file__).resolve().parent / "kicad_source"
    pack = {
        "schema": PACK_SCHEMA,
        "kicad_version": KICAD_VERSION,
        "kicad_source_tag": KICAD_SOURCE_TAG,
        "unit": "mm",
        "record_count": len(records),
        "kicad_source_references": _source_references(source_root),
        "footprints": records,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(pack, indent=2, sort_keys=True), encoding="utf-8")
    return pack


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bundled KiCad PCB footprint source pack")
    parser.add_argument("--footprint-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parent / "footprint_source_pack.json",
    )
    args = parser.parse_args()
    pack = build_source_pack(args.footprint_root, args.output)
    print(json.dumps({"output": str(args.output), "record_count": pack["record_count"]}, indent=2))


if __name__ == "__main__":
    main()
