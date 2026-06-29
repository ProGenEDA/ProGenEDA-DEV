#!/usr/bin/env python3
"""
KiCad generated-project symbol fixer / auto library downloader.

Problem it fixes:
    Generated .kicad_sch files may open with red boxes and question marks if
    KiCad cannot resolve library IDs such as Device:R, power:GND, or
    Simulation_SPICE:VDC from the user's global library table.

What it does:
    1. Finds .kicad_sch projects under a folder.
    2. Parses used library names from (lib_id "Library:Symbol") entries.
    3. Copies matching *.kicad_sym files from an installed KiCad library folder
       if available.
    4. Otherwise downloads the needed *.kicad_sym files from official KiCad
       library URLs.
    5. Writes a per-project sym-lib-table using ${KIPRJMOD}/symbols/...

Usage on Windows from the extracted output ZIP folder:
    py fix_project_symbols.py . --recursive

Then reopen the .kicad_pro project file in KiCad.
"""
from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path
from typing import Iterable

DEFAULT_LIBS = ["Device", "power", "Simulation_SPICE"]
BRANCH_CANDIDATES = ["master", "8.0", "9.0", "10.0", "7.0", "6.0"]
URL_TEMPLATES = [
    "https://gitlab.com/kicad/libraries/kicad-symbols/-/raw/{branch}/{lib}.kicad_sym",
    "https://raw.githubusercontent.com/KiCad/kicad-symbols/master/{lib}.kicad_sym",
]
ENV_CANDIDATES = ["KICAD_SYMBOL_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR", "KICAD8_SYMBOL_DIR", "KICAD7_SYMBOL_DIR", "KICAD6_SYMBOL_DIR"]


def likely_windows_install_dirs() -> list[Path]:
    dirs: list[Path] = []
    roots = [os.environ.get("PROGRAMFILES"), os.environ.get("PROGRAMFILES(X86)")]
    versions = ["10.0", "9.0", "8.0", "7.0", "6.0"]
    for root in roots:
        if not root:
            continue
        for v in versions:
            dirs.append(Path(root) / "KiCad" / v / "share" / "kicad" / "symbols")
            dirs.append(Path(root) / "KiCad" / v / "share" / "kicad" / "library")
        dirs.append(Path(root) / "KiCad" / "share" / "kicad" / "symbols")
    return dirs


def local_symbol_dirs(extra: Iterable[str] = ()) -> list[Path]:
    dirs: list[Path] = []
    for env in ENV_CANDIDATES:
        val = os.environ.get(env)
        if val:
            dirs.append(Path(val))
    for x in extra:
        if x:
            dirs.append(Path(x))
    dirs.extend(likely_windows_install_dirs())
    out: list[Path] = []
    seen: set[str] = set()
    for d in dirs:
        key = str(d).lower()
        if key not in seen:
            out.append(d)
            seen.add(key)
    return out


def parse_libraries_from_schematic(sch: Path) -> set[str]:
    text = sch.read_text(encoding="utf-8", errors="replace")
    libs: set[str] = set()
    for m in re.finditer(r"\(lib_id\s+(?:\"([^\"]+)\"|([^\s\)]+))", text):
        lib_id = m.group(1) or m.group(2)
        if ":" in lib_id:
            libs.add(lib_id.split(":", 1)[0])
    return libs


def find_project_dirs(root: Path, recursive: bool) -> list[Path]:
    if recursive:
        return sorted({p.parent for p in root.rglob("*.kicad_sch")})
    return [root] if list(root.glob("*.kicad_sch")) else []


def find_local_symbol(lib: str, search_dirs: list[Path]) -> Path | None:
    filename = f"{lib}.kicad_sym"
    for d in search_dirs:
        p = d / filename
        if p.exists() and p.is_file() and p.stat().st_size > 100:
            return p
    return None


def download_symbol(lib: str, out_path: Path, timeout: int = 30) -> bool:
    for branch in BRANCH_CANDIDATES:
        for tmpl in URL_TEMPLATES:
            url = tmpl.format(branch=branch, lib=lib)
            try:
                print(f"  download {lib}: {url}")
                with urllib.request.urlopen(url, timeout=timeout) as r:
                    data = r.read()
                if len(data) < 100 or b"(kicad_symbol_lib" not in data[:500]:
                    print(f"    rejected: response did not look like a KiCad symbol library ({len(data)} bytes)")
                    continue
                out_path.write_bytes(data)
                return True
            except Exception as e:
                print(f"    failed: {e}")
    return False


def write_sym_lib_table(project_dir: Path, libs: list[str]) -> None:
    lines = ["(sym_lib_table\n", "  (version 7)\n"]
    for lib in libs:
        lines.append(f'  (lib (name "{lib}") (type "KiCad") (uri "${{KIPRJMOD}}/symbols/{lib}.kicad_sym") (options "") (descr "local {lib} symbols"))\n')
    lines.append(")\n")
    (project_dir / "sym-lib-table").write_text("".join(lines), encoding="utf-8")


def fix_project_dir(project_dir: Path, args: argparse.Namespace) -> dict[str, object]:
    sch_files = sorted(project_dir.glob("*.kicad_sch"))
    libs: set[str] = set(args.libs or [])
    if not args.libs:
        libs.update(DEFAULT_LIBS)
    for sch in sch_files:
        libs.update(parse_libraries_from_schematic(sch))
    libs_list = sorted(libs)
    symbols_dir = project_dir / "symbols"
    symbols_dir.mkdir(exist_ok=True)
    search_dirs = local_symbol_dirs(args.local_symbol_dir or [])
    copied: list[str] = []
    downloaded: list[str] = []
    failed: list[str] = []
    print(f"\nProject: {project_dir}")
    print(f"Needed libraries: {', '.join(libs_list) if libs_list else '(none)'}")
    for lib in libs_list:
        dst = symbols_dir / f"{lib}.kicad_sym"
        if dst.exists() and dst.stat().st_size > 100 and not args.force:
            print(f"  exists: {dst.name}")
            continue
        local = find_local_symbol(lib, search_dirs)
        if local:
            shutil.copy2(local, dst)
            copied.append(lib)
            print(f"  copied {lib} from {local}")
            continue
        if args.no_download:
            failed.append(lib)
            print(f"  missing {lib}; download disabled")
            continue
        if download_symbol(lib, dst, timeout=args.timeout):
            downloaded.append(lib)
            print(f"  downloaded {lib} -> {dst}")
        else:
            failed.append(lib)
            print(f"  FAILED {lib}")
    available = [lib for lib in libs_list if (symbols_dir / f"{lib}.kicad_sym").exists()]
    write_sym_lib_table(project_dir, available)
    return {"project_dir": str(project_dir), "schematics": [str(p.name) for p in sch_files], "needed_libraries": libs_list, "available_libraries": available, "copied": copied, "downloaded": downloaded, "failed": failed, "sym_lib_table": str(project_dir / "sym-lib-table")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root", type=Path, help="Project directory or folder containing generated project folders")
    ap.add_argument("--recursive", action="store_true", help="Fix all subfolders containing .kicad_sch files")
    ap.add_argument("--local-symbol-dir", action="append", help="Extra folder containing *.kicad_sym files")
    ap.add_argument("--libs", nargs="*", help="Override library list; default = parsed libs plus Device/power/Simulation_SPICE")
    ap.add_argument("--no-download", action="store_true", help="Only copy from installed/local KiCad libraries")
    ap.add_argument("--force", action="store_true", help="Overwrite existing local symbols")
    ap.add_argument("--timeout", type=int, default=30)
    args = ap.parse_args()
    root = args.root.resolve()
    if not root.exists():
        raise SystemExit(f"folder does not exist: {root}")
    projects = find_project_dirs(root, args.recursive)
    if not projects:
        raise SystemExit("No .kicad_sch files found. Run this in the extracted KiCad output folder.")
    results = [fix_project_dir(p, args) for p in projects]
    print("\nDone. Reopen the .kicad_pro file in KiCad.")
    print("If red boxes remain, send the exact missing library/symbol message.")
    failed = [x for r in results for x in r["failed"]]
    if failed:
        print("\nSome libraries failed:", ", ".join(sorted(set(failed))))
        sys.exit(2)


if __name__ == "__main__":
    main()
