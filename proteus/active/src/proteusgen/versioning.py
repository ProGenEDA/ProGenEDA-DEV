"""Version-normalization helpers for Proteus 8.x project trials.

Finding from tests:

- PROJECT.XML contains RELEASE and FILEVER metadata.
- ROOT.DSN also contains two little-endian uint16 fields near the header.
- For Proteus 8.13, observed values are release=813 and filever=830.

The helper below patches both places. This is intentionally narrow and
should only be applied to user-created `.pdsprj` test projects.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class ProteusVersionTarget:
    release: int
    filever: int


PROTEUS_813 = ProteusVersionTarget(release=813, filever=830)
PROTEUS_816 = ProteusVersionTarget(release=816, filever=847)
PROTEUS_900 = ProteusVersionTarget(release=900, filever=907)


def patch_project_xml_version(xml_bytes: bytes, target: ProteusVersionTarget = PROTEUS_813) -> bytes:
    """Patch RELEASE and FILEVER attributes in PROJECT.XML bytes."""

    text = xml_bytes.decode("utf-8", errors="replace")
    text = re.sub(r'RELEASE="\d+"', f'RELEASE="{target.release}"', text)
    text = re.sub(r'FILEVER="\d+"', f'FILEVER="{target.filever}"', text)
    return text.encode("utf-8")


def read_root_dsn_version(root_dsn: bytes) -> tuple[int, int]:
    """Read observed ROOT.DSN release/filever fields.

    Offsets were discovered from user-created test projects:
    offset 167 = release, offset 169 = filever, both uint16 little-endian.
    """

    if len(root_dsn) < 171:
        raise ValueError("ROOT.DSN too short to contain observed version header")
    release = struct.unpack_from("<H", root_dsn, 167)[0]
    filever = struct.unpack_from("<H", root_dsn, 169)[0]
    return release, filever


def patch_root_dsn_version(root_dsn: bytes, target: ProteusVersionTarget = PROTEUS_813) -> bytes:
    """Patch observed ROOT.DSN release/filever fields."""

    if len(root_dsn) < 171:
        raise ValueError("ROOT.DSN too short to patch observed version header")
    out = bytearray(root_dsn)
    struct.pack_into("<H", out, 167, target.release)
    struct.pack_into("<H", out, 169, target.filever)
    return bytes(out)
