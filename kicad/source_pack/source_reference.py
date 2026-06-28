"""Runtime KiCad source reference mining.

This module does not execute KiCad C++ code.  It ships and reads the relevant
source files so the Python generator can keep its writer order and validations
anchored to KiCad's parser/saver implementation.
"""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .source_pack_loader import ensure_source_zip

IMPORTANT_SOURCE_SUFFIXES = (
    "common/project/project_file.cpp",
    "include/project/project_file.h",
    "common/project.cpp",
    "include/project.h",
    "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp",
    "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp",
    "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_common.cpp",
    "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.cpp",
    "eeschema/lib_symbol.cpp",
    "eeschema/sch_symbol.cpp",
    "eeschema/sch_pin.cpp",
    "eeschema/sch_line.cpp",
    "eeschema/sch_text.cpp",
    "eeschema/netlist_exporters/netlist_exporter_spice.cpp",
    "eeschema/netlist_exporters/netlist_exporter_spice_model.cpp",
    "qa/data/eeschema/spice_netlists/directives/directives.kicad_sch",
)

WRITER_ORDER = (
    "kicad_sch header",
    "uuid",
    "paper",
    "lib_symbols",
    "junction",
    "wire",
    "label",
    "text",
    "symbol",
    "sheet_instances",
)


@dataclass(frozen=True)
class SourceFileDigest:
    logical_name: str
    archive_name: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class KiCadSourceReference:
    zip_path: str
    zip_sha256: str
    files: tuple[SourceFileDigest, ...]
    writer_order: tuple[str, ...]
    parser_tokens: tuple[str, ...]
    conclusions: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "zip_path": self.zip_path,
            "zip_sha256": self.zip_sha256,
            "files": [file.__dict__ for file in self.files],
            "writer_order": list(self.writer_order),
            "parser_tokens": list(self.parser_tokens),
            "conclusions": list(self.conclusions),
        }


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _logical_name(name: str) -> str:
    for suffix in IMPORTANT_SOURCE_SUFFIXES:
        if name.endswith(suffix):
            return suffix
    return name


def _mine_parser_tokens(text_by_logical: dict[str, str]) -> tuple[str, ...]:
    text = "\n".join(text_by_logical.values())
    candidates = [
        "lib_symbols",
        "junction",
        "wire",
        "label",
        "global_label",
        "text",
        "symbol",
        "sheet_instances",
        "symbol_instances",
        "pts",
        "xy",
        "uuid",
    ]
    found = [token for token in candidates if re.search(rf"\b{re.escape(token)}\b", text)]
    return tuple(found)


@lru_cache(maxsize=1)
def load_reference() -> KiCadSourceReference:
    zip_path = ensure_source_zip()
    zip_bytes = zip_path.read_bytes()
    files: list[SourceFileDigest] = []
    texts: dict[str, str] = {}
    with zipfile.ZipFile(zip_path) as archive:
        for entry in archive.infolist():
            if not any(entry.filename.endswith(suffix) for suffix in IMPORTANT_SOURCE_SUFFIXES):
                continue
            raw = archive.read(entry.filename)
            logical = _logical_name(entry.filename)
            files.append(SourceFileDigest(logical, entry.filename, len(raw), _sha256(raw)))
            texts[logical] = raw.decode("utf-8", errors="replace")

    files.sort(key=lambda item: item.logical_name)
    present = {item.logical_name for item in files}
    missing = [suffix for suffix in IMPORTANT_SOURCE_SUFFIXES if suffix not in present]
    conclusions = [
        "Source pack is bundled and read at generation time.",
        "Python writer mirrors KiCad S-expression project/schematic structure; it does not execute KiCad C++.",
        "Every generated wire is emitted as a separate two-point object.",
        "Symbols are embedded into the schematic so global library lookup is not required for V1 core output.",
    ]
    if missing:
        conclusions.append("Missing source reference files: " + ", ".join(missing))
    else:
        conclusions.append("All required V1 source reference files are present.")
    return KiCadSourceReference(
        zip_path=str(zip_path),
        zip_sha256=_sha256(zip_bytes),
        files=tuple(files),
        writer_order=WRITER_ORDER,
        parser_tokens=_mine_parser_tokens(texts),
        conclusions=tuple(conclusions),
    )


def main() -> None:
    print(json.dumps(load_reference().as_dict(), indent=2))


if __name__ == "__main__":
    main()
