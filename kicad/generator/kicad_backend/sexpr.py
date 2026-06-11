from __future__ import annotations

import re
import uuid
from typing import Any

ROOT_UUID = "00000000-0000-0000-0000-000000000001"


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip()) or "kicad_generated"


def q(value: Any) -> str:
    """Quote as a KiCad S-expression string.

    KiCad text objects must keep multiline SPICE directives as one quoted token,
    so Python newlines are escaped as the two characters "\\n".
    """
    return '"' + str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"') + '"'


def num(value: float) -> str:
    value = float(value)
    return str(int(value)) if value.is_integer() else f"{value:.6f}".rstrip("0").rstrip(".")


def stable_uuid(seed: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))


def paren_balance(text: str) -> tuple[bool, str]:
    depth = 0
    in_str = False
    esc = False
    for idx, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                return False, f"extra right parenthesis at offset {idx}"
    if in_str:
        return False, "unterminated quoted string"
    if depth:
        return False, f"unclosed parenthesis depth {depth}"
    return True, "ok"
