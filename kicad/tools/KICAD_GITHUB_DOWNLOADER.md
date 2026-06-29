# KiCad GitHub Auto-Downloader

The user clarified that the auto-downloader should not only fix local missing symbols. It should look around the KiCad GitHub organization and download/discover KiCad files needed for the generator track.

Persistent tool:

```text
kicad/tools/download_kicad_github_assets.py
```

## What it can do

### 1. Inventory every KiCad GitHub repository

```bash
python kicad/tools/download_kicad_github_assets.py --mode inventory
```

Outputs:

```text
manifest.json
repos.csv
```

### 2. Download the main generator-relevant repositories as zip archives

```bash
python kicad/tools/download_kicad_github_assets.py --mode needed-archives
```

Default generator preset repos:

```text
KiCad/kicad-source-mirror
KiCad/kicad-symbols
KiCad/kicad-templates
KiCad/kicad-doc
```

### 3. Build an inventory of KiCad project/library files from GitHub trees

```bash
python kicad/tools/download_kicad_github_assets.py --mode file-inventory --preset generator
```

It searches for relevant files such as:

```text
*.kicad_pro
*.kicad_sch
*.kicad_sym
*.kicad_pcb
*.kicad_mod
sym-lib-table
fp-lib-table
*.cir
*.spice
*.lib
*.sub
*.mod
```

### 4. Download matching KiCad files

```bash
python kicad/tools/download_kicad_github_assets.py --mode files --preset generator
```

For a safer first run:

```bash
python kicad/tools/download_kicad_github_assets.py --mode files --preset generator --limit 200
```

### 5. Download exact files useful for our generator implementation

```bash
python kicad/tools/download_kicad_github_assets.py --mode targeted-files
```

This includes schematic S-expression parser/writer sources, SPICE exporter tests, and important symbol-library files where GitHub paths exist.

### 6. Download every KiCad GitHub repo archive

This can be very large:

```bash
python kicad/tools/download_kicad_github_assets.py --mode all-org-archives --confirm-large
```

## Output location

Default:

```text
external/kicad_github/<UTC_RUN_ID>/
```

The downloaded files are deliberately outside the repo source folders so bulky upstream files do not get accidentally committed.

## Recommended first commands

```bash
python kicad/tools/download_kicad_github_assets.py --mode inventory
python kicad/tools/download_kicad_github_assets.py --mode needed-archives
python kicad/tools/download_kicad_github_assets.py --mode file-inventory --preset generator
python kicad/tools/download_kicad_github_assets.py --mode targeted-files
```

## GitHub API token

Unauthenticated GitHub API calls are rate limited. Use a token for bigger scans:

```powershell
$env:GITHUB_TOKEN="ghp_xxx"
```

or Windows CMD:

```cmd
set GITHUB_TOKEN=ghp_xxx
```

## Important warning

Some KiCad GitHub repos are mirrors or archived library repos, and some point to GitLab as active upstream. This tool is for the user's requested GitHub scan/download workflow, not a final statement about upstream authority.
