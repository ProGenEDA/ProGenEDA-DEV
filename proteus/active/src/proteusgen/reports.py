"""Report helpers for comparing Proteus project internals."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile


@dataclass(frozen=True)
class InternalFileSummary:
    name: str
    size: int
    sha256: str


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def summarize_pdsprj(path: str | Path) -> list[InternalFileSummary]:
    """Summarize internal files of a `.pdsprj` container."""

    summaries: list[InternalFileSummary] = []
    with ZipFile(path, "r") as zf:
        for name in zf.namelist():
            data = zf.read(name)
            summaries.append(InternalFileSummary(name=name, size=len(data), sha256=sha256_bytes(data)))
    return summaries


def write_summary_markdown(path: str | Path, output_path: str | Path) -> None:
    """Write a markdown summary table for a `.pdsprj`."""

    rows = summarize_pdsprj(path)
    lines = [
        f"# Project Summary: {Path(path).name}",
        "",
        "| Internal file | Size | SHA256 |",
        "|---|---:|---|",
    ]
    for row in rows:
        lines.append(f"| `{row.name}` | {row.size} | `{row.sha256}` |")
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
