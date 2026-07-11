"""Hosted footprint catalogue backed by the committed KiCad source pack."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


SOURCE_PACK_PATH = Path(__file__).resolve().parent / "source_pack" / "footprint_source_pack.json"
FOOTPRINT_MAP_PATH = Path(__file__).resolve().parents[1] / "pipeline" / "catelogues" / "kicad_footprint_map.json"


@dataclass(frozen=True)
class FootprintRecord:
    library_id: str
    source_file: str
    sha256: str
    bounds: dict[str, float]
    pads: tuple[dict[str, Any], ...]
    source_text: str

    @property
    def pad_numbers(self) -> frozenset[str]:
        return frozenset(str(pad["number"]) for pad in self.pads)


class FootprintCatalogue:
    def __init__(self, pack: dict[str, Any], footprint_map: dict[str, Any]) -> None:
        if pack.get("schema") != "progen-kicad-pcb-footprint-source-pack/v0.1":
            raise ValueError("Unsupported PCB footprint source pack schema")
        self.pack = pack
        self.footprint_map = footprint_map

    @property
    def source_metadata(self) -> dict[str, Any]:
        return {
            "schema": self.pack["schema"],
            "kicad_version": self.pack["kicad_version"],
            "kicad_source_tag": self.pack["kicad_source_tag"],
            "record_count": self.pack["record_count"],
            "kicad_source_references": deepcopy(self.pack.get("kicad_source_references", [])),
        }

    def record(self, footprint_id: str) -> FootprintRecord:
        raw = self.pack.get("footprints", {}).get(footprint_id)
        if not isinstance(raw, dict):
            raise KeyError(f"Footprint is not in hosted source pack: {footprint_id}")
        source_text = str(raw["source_text"])
        digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        if digest != raw.get("sha256"):
            raise ValueError(f"Footprint source digest mismatch: {footprint_id}")
        return FootprintRecord(
            library_id=footprint_id,
            source_file=str(raw["source_file"]),
            sha256=digest,
            bounds={key: float(value) for key, value in raw["bounds"].items()},
            pads=tuple(deepcopy(raw.get("pads", []))),
            source_text=source_text,
        )

    def footprint_id_for_abstract_type(self, type_id: str) -> str | None:
        raw = self.footprint_map.get(type_id)
        if not isinstance(raw, dict):
            return None
        value = str(raw.get("footprint") or "").strip()
        return value or None

    def connector_footprint(self, required_pad_numbers: set[str]) -> str | None:
        numeric: list[int] = []
        for number in required_pad_numbers:
            if not number.isdigit() or int(number) < 1:
                return None
            numeric.append(int(number))
        count = max(numeric, default=2)
        if count > 20:
            return None
        return f"Connector_PinHeader_2.54mm:PinHeader_1x{count:02d}_P2.54mm_Vertical"


@lru_cache(maxsize=1)
def load_footprint_catalogue() -> FootprintCatalogue:
    pack = json.loads(SOURCE_PACK_PATH.read_text(encoding="utf-8"))
    footprint_map = json.loads(FOOTPRINT_MAP_PATH.read_text(encoding="utf-8"))
    return FootprintCatalogue(pack, footprint_map)
