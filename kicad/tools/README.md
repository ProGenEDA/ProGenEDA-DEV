# KiCad Tools

## open_local_kicad.sh

Launches the local KiCad 10.0.4 AppImage unpacked under `kicad/.local/`.
The wrapper avoids the AppImage `AppRun` script because that file uses a
`/bin/bash` shebang that is not portable on this NixOS workspace.

Register it as the default opener for `.kicad_pro` files:

```bash
kicad/tools/open_local_kicad.sh --install-desktop
```

Normal launches default to native Wayland with software rendering when a
Wayland session is detected. This avoids the XWayland resize crash seen on this
NixOS/KDE workspace:

```bash
kicad/tools/open_local_kicad.sh path/to/project.kicad_pro
```

To explicitly test the old XWayland fallback:

```bash
KICAD_LOCAL_RENDERING=x11-safe kicad/tools/open_local_kicad.sh path/to/project.kicad_pro
```

To test native GPU/desktop rendering later:

```bash
KICAD_LOCAL_RENDERING=native kicad/tools/open_local_kicad.sh path/to/project.kicad_pro
```

## download_kicad_github_assets.py

Auto-discovers/downloads KiCad files and repositories from the KiCad GitHub organization.

This is the tool for the user's intended meaning of auto-downloader:

```text
look around GitHub for KiCad repos/files and download what the generator needs
```

Docs:

```text
kicad/tools/KICAD_GITHUB_DOWNLOADER.md
```

Quick commands:

```bash
python kicad/tools/download_kicad_github_assets.py --mode inventory
python kicad/tools/download_kicad_github_assets.py --mode needed-archives
python kicad/tools/download_kicad_github_assets.py --mode file-inventory --preset generator
python kicad/tools/download_kicad_github_assets.py --mode targeted-files
```

For a huge full GitHub-org archive pull:

```bash
python kicad/tools/download_kicad_github_assets.py --mode all-org-archives --confirm-large
```

Default output folder:

```text
external/kicad_github/<UTC_RUN_ID>/
```

Use a GitHub token for bigger scans:

```powershell
$env:GITHUB_TOKEN="ghp_xxx"
```

## fix_project_symbols.py

Fixes generated KiCad projects that open with red question-mark boxes because stock libraries are not resolved.

Usage from inside an extracted generated-output folder:

```bash
python kicad/tools/fix_project_symbols.py . --recursive
```

For the downloadable test ZIP, the same tool is included at the root with a Windows batch file:

```text
RUN_THIS_FIRST__download_kicad_symbols.bat
```

What it does:

```text
1. scans .kicad_sch files for lib_id entries
2. detects required libraries such as Device, power, Simulation_SPICE
3. copies local installed KiCad libraries if found
4. otherwise downloads official KiCad symbol library files
5. writes project-local sym-lib-table files
```

This is a portability fix for the first generator outputs. Later generator versions should either emit project-local symbol tables automatically or embed symbol cache blocks directly into `.kicad_sch` after KiCad roundtrip validation.
