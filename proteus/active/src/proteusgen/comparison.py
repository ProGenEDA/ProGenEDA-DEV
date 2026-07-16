"""Semantic-oriented comparison for generated and Proteus-resaved projects."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from .pdsprj import REQUIRED_INTERNAL_FILES


def _semantic_bytes(name: str, data: bytes) -> bytes:
    if name == "PROJECT.XML":
        text = data.decode("utf-8", errors="replace")
        text = re.sub(r'(MODIFIED|CREATED)="\d+"', r'\1="<timestamp>"', text)
        return text.encode("utf-8")
    if name == "ROOT.DSN" and len(data) > 178:
        normalized = bytearray(data)
        normalized[177:179] = b"\x00\x00"
        return bytes(normalized)
    return data


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def compare_projects(left: str | Path, right: str | Path) -> dict[str, Any]:
    with ZipFile(left, "r") as left_zip, ZipFile(right, "r") as right_zip:
        left_names = set(left_zip.namelist())
        right_names = set(right_zip.namelist())
        members = sorted(left_names | right_names)
        files = []
        for name in members:
            left_data = left_zip.read(name) if name in left_names else None
            right_data = right_zip.read(name) if name in right_names else None
            semantic_equal = (
                left_data is not None
                and right_data is not None
                and _semantic_bytes(name, left_data) == _semantic_bytes(name, right_data)
            )
            files.append(
                {
                    "name": name,
                    "left_present": left_data is not None,
                    "right_present": right_data is not None,
                    "left_size": None if left_data is None else len(left_data),
                    "right_size": None if right_data is None else len(right_data),
                    "byte_equal": left_data == right_data,
                    "semantic_equal": semantic_equal,
                    "left_sha256": None if left_data is None else _sha(left_data),
                    "right_sha256": None if right_data is None else _sha(right_data),
                }
            )
    required_present = all(
        name in left_names and name in right_names for name in REQUIRED_INTERNAL_FILES
    )
    return {
        "left": str(Path(left)),
        "right": str(Path(right)),
        "required_files_present_in_both": required_present,
        "semantic_equal": required_present and all(item["semantic_equal"] for item in files),
        "files": files,
    }
