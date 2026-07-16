"""Build the portable, Proteus-only Windows executable with PyInstaller.

Run from the repository root after installing the optional ``build-exe``
dependency. The build bundles only the data needed by the locked component
placer and shared terminal/value pipeline; it does not bundle or invoke KiCad.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def build_arguments() -> list[str]:
    separator = os.pathsep
    add_data = (
        (ROOT / "fixtures", "fixtures"),
        (ROOT / "knowledge" / "component_catalog_v0.json", "knowledge"),
        (ROOT / "knowledge" / "validator_history_rules.json", "knowledge"),
        (
            ROOT / "proteus_ic" / "registry" / "trusted_donor_manifest.json",
            "proteus_ic/registry",
        ),
        (
            ROOT / "proteus_ic" / "registry" / "native_components.json",
            "proteus_ic/registry",
        ),
        (
            ROOT
            / "proteus_ic"
            / "donors"
            / "manual_downloads_20260618"
            / "new_component_mega"
            / "new_components_5x_mega.pdsprj",
            "proteus_ic/donors/manual_downloads_20260618/new_component_mega",
        ),
    )
    args = [
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        "--name=ProgenProteus",
        f"--paths={ROOT / 'src'}",
        f"--distpath={ROOT / 'release'}",
        f"--workpath={ROOT / 'build' / 'progen_proteus_exe'}",
        f"--specpath={ROOT / 'build' / 'progen_proteus_exe'}",
        "--collect-submodules=proteusgen",
    ]
    for source, destination in add_data:
        args.extend(("--add-data", f"{source}{separator}{destination}"))
    args.append(str(ROOT / "tools" / "progen_proteus_entry.py"))
    return args


def main() -> int:
    try:
        import PyInstaller.__main__
    except ImportError as exc:
        print("PyInstaller is required. Install with: python -m pip install -e .[build-exe]", file=sys.stderr)
        return 2
    PyInstaller.__main__.run(build_arguments())
    executable = ROOT / "release" / "ProgenProteus.exe"
    if not executable.exists():
        print(f"Build completed without expected executable: {executable}", file=sys.stderr)
        return 2
    print(executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
