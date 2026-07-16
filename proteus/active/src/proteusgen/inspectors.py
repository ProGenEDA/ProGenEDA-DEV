"""Lightweight binary/text inspection helpers for extracted Proteus files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StringHit:
    offset: int
    text: str


ASCII_RE = re.compile(rb"[ -~]{3,}")


def extract_ascii_strings(data: bytes, *, min_len: int = 3) -> list[StringHit]:
    """Extract printable ASCII strings with byte offsets."""

    pattern = re.compile(rb"[ -~]{%d,}" % min_len)
    hits: list[StringHit] = []
    for match in pattern.finditer(data):
        hits.append(StringHit(offset=match.start(), text=match.group().decode("ascii", errors="replace")))
    return hits


def find_all(data: bytes, needle: bytes) -> list[int]:
    """Return all byte offsets for `needle` in `data`."""

    offsets: list[int] = []
    start = 0
    while True:
        idx = data.find(needle, start)
        if idx == -1:
            return offsets
        offsets.append(idx)
        start = idx + 1


def diff_offsets(a: bytes, b: bytes, *, limit: int | None = None) -> list[tuple[int, int | None, int | None]]:
    """Return differing offsets between two byte strings.

    Each item is `(offset, byte_a, byte_b)`. Missing bytes are `None`.
    """

    diffs: list[tuple[int, int | None, int | None]] = []
    max_len = max(len(a), len(b))
    for i in range(max_len):
        ba = a[i] if i < len(a) else None
        bb = b[i] if i < len(b) else None
        if ba != bb:
            diffs.append((i, ba, bb))
            if limit is not None and len(diffs) >= limit:
                break
    return diffs


def write_strings_report(input_path: str | Path, output_path: str | Path) -> None:
    """Write an offseted ASCII string report for one binary file."""

    data = Path(input_path).read_bytes()
    hits = extract_ascii_strings(data)
    lines = [f"0x{hit.offset:08X}\t{hit.offset}\t{hit.text}" for hit in hits]
    Path(output_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
