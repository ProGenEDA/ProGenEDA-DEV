#!/usr/bin/env python3
from __future__ import annotations

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOWNLOAD_DIR = ROOT / "downloaded_zip"
ZIP_NAME = "KiCad_Source_Files_Needed_20260612_030305.zip"
ZIP = ROOT / ZIP_NAME
DOWNLOADED_ZIP = DOWNLOAD_DIR / ZIP_NAME
B64 = ROOT / f"{ZIP_NAME}.b64"
DOWNLOADED_B64 = DOWNLOAD_DIR / f"{ZIP_NAME}.b64"
EXTRACTED = ROOT / "upstream_extracted"


def candidate_roots() -> list[Path]:
    roots = [ROOT]
    if getattr(sys, "frozen", False):
        bundle = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        roots.extend([bundle / "kicad" / "source_pack", Path(sys.executable).parent / "kicad" / "source_pack"])
    roots.append(Path.cwd() / "kicad" / "source_pack")
    return roots


def candidate_zips() -> list[Path]:
    paths: list[Path] = []
    for root in candidate_roots():
        paths.extend([root / ZIP_NAME, root / "downloaded_zip" / ZIP_NAME])
    seen: set[Path] = set()
    out: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            out.append(path)
    return out


def ensure_source_zip() -> Path:
    for path in candidate_zips():
        if path.exists():
            return path
    for b64, destination in ((B64, ZIP), (DOWNLOADED_B64, DOWNLOADED_ZIP)):
        if b64.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(base64.b64decode(b64.read_text(encoding="ascii")))
            return destination
    raise FileNotFoundError(
        f"Missing {ZIP_NAME}. It must be bundled in kicad/source_pack/downloaded_zip "
        "or supplied beside source_pack_loader.py as a zip or .zip.b64 file."
    )


def main() -> None:
    z = ensure_source_zip()
    print(f"ready: {z}")


if __name__ == "__main__":
    main()
