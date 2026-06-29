#!/usr/bin/env python3
"""
KiCad GitHub auto-downloader / inventory builder.

Purpose
-------
This tool discovers KiCad repositories on GitHub and downloads the files/assets
needed to build a visual KiCad generator without relying on a user's installed
KiCad library setup.

It intentionally writes downloads outside the repo by default:

    external/kicad_github/<run_id>/

so bulky upstream KiCad source/library artifacts are not accidentally committed
into memory.

Examples
--------
Inventory KiCad org repositories only:

    python kicad/tools/download_kicad_github_assets.py --mode inventory

Download the repos most useful for generator research as zip archives:

    python kicad/tools/download_kicad_github_assets.py --mode needed-archives

Build a file inventory for KiCad project/schematic/library file types across
selected repos:

    python kicad/tools/download_kicad_github_assets.py --mode file-inventory --preset generator

Download matching KiCad files from selected repos:

    python kicad/tools/download_kicad_github_assets.py --mode files --preset generator

Download archives for every repository in the KiCad GitHub org:

    python kicad/tools/download_kicad_github_assets.py --mode all-org-archives --confirm-large

Notes
-----
- Uses only the GitHub REST API and raw.githubusercontent.com URLs.
- Set GITHUB_TOKEN to avoid rate limits:

      set GITHUB_TOKEN=ghp_xxx        # Windows CMD
      $env:GITHUB_TOKEN="ghp_xxx"     # PowerShell
      export GITHUB_TOKEN=ghp_xxx     # Linux/macOS

- This script downloads from GitHub mirrors/archives only. Some KiCad projects
  point to GitLab as active upstream; keep that in mind when pinning final data.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

ORG = "KiCad"
API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"

GENERATOR_REPOS = [
    "kicad-source-mirror",
    "kicad-symbols",
    "kicad-templates",
    "kicad-doc",
]

EXTENDED_REPOS = GENERATOR_REPOS + [
    "kicad-footprints",
    "kicad-packages3D",
    "kicad-library-utils",
    "kicad-docker",
]

# File types relevant to native KiCad visual project generation.
KICAD_SUFFIXES = (
    ".kicad_pro",
    ".kicad_sch",
    ".kicad_sym",
    ".kicad_pcb",
    ".kicad_mod",
    ".kicad_wks",
    ".kicad_prl",
    ".kicad_dru",
    ".pretty",
    "sym-lib-table",
    "fp-lib-table",
    ".net",
    ".cir",
    ".spice",
    ".lib",
    ".sub",
    ".mod",
)

# Source files explicitly useful for the generator implementation.
TARGETED_SOURCE_PATHS = {
    "kicad-source-mirror": [
        "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_parser.cpp",
        "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr.cpp",
        "eeschema/sch_io/kicad_sexpr/sch_io_kicad_sexpr_lib_cache.cpp",
        "eeschema/sch_io/sch_io_mgr.cpp",
        "qa/schematic_utils/schematic_file_util.cpp",
        "qa/tests/eeschema/net_chains/test_net_chain_manual.cpp",
        "qa/tests/eeschema/net_chains/test_net_chain_synthetic_filter.cpp",
        "qa/tests/eeschema/net_chains/test_net_chain_hierarchical_roundtrip.cpp",
        "eeschema/sim/simulator_frame.cpp",
        "eeschema/sim/spice_circuit_model.h",
        "qa/tests/spice/test_netlist_exporter_spice.h",
        "qa/tests/spice/test_ngspice_helpers.cpp",
        "qa/data/eeschema/spice_netlists/directives/directives.kicad_sch",
    ],
    "kicad-symbols": [
        "Device.kicad_sym",
        "power.kicad_sym",
        "Simulation_SPICE.kicad_sym",
        "Diode.kicad_sym",
        "Transistor_BJT.kicad_sym",
        "Transistor_FET.kicad_sym",
    ],
}


@dataclass
class RepoInfo:
    name: str
    full_name: str
    html_url: str
    default_branch: str
    archived: bool
    fork: bool
    size: int
    pushed_at: str | None
    description: str | None


@dataclass
class DownloadRecord:
    kind: str
    repo: str
    path: str
    url: str
    local_path: str
    size_bytes: int
    sha256: str


def now_id() -> str:
    return dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "memory-kicad-downloader"}
    tok = os.environ.get("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    return h


def request_json(url: str, retries: int = 3) -> Any:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers())
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            last = RuntimeError(f"HTTP {e.code} for {url}: {body[:500]}")
            if e.code in {403, 429, 500, 502, 503, 504}:
                time.sleep(2 + attempt * 2)
                continue
            raise last
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1 + attempt)
    assert last is not None
    raise last


def download_bytes(url: str, retries: int = 3) -> bytes:
    last: Exception | None = None
    req_headers = {"User-Agent": "memory-kicad-downloader"}
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=120) as r:
                return r.read()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 + attempt * 2)
    assert last is not None
    raise last


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_bytes(path: Path, data: bytes) -> DownloadRecord:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return DownloadRecord("file", "", "", "", str(path), len(data), sha256_bytes(data))


def list_org_repos() -> list[RepoInfo]:
    repos: list[RepoInfo] = []
    page = 1
    while True:
        url = f"{API}/orgs/{ORG}/repos?per_page=100&page={page}&type=all&sort=full_name"
        data = request_json(url)
        if not data:
            break
        for r in data:
            repos.append(RepoInfo(
                name=r["name"],
                full_name=r["full_name"],
                html_url=r["html_url"],
                default_branch=r.get("default_branch") or "master",
                archived=bool(r.get("archived")),
                fork=bool(r.get("fork")),
                size=int(r.get("size") or 0),
                pushed_at=r.get("pushed_at"),
                description=r.get("description"),
            ))
        page += 1
    return repos


def repo_map(repos: Iterable[RepoInfo]) -> dict[str, RepoInfo]:
    return {r.name: r for r in repos}


def select_repos(all_repos: list[RepoInfo], preset: str) -> list[RepoInfo]:
    m = repo_map(all_repos)
    if preset == "generator":
        names = GENERATOR_REPOS
    elif preset == "extended":
        names = EXTENDED_REPOS
    elif preset == "all":
        return all_repos
    else:
        names = [x.strip() for x in preset.split(",") if x.strip()]
    missing = [n for n in names if n not in m]
    if missing:
        print(f"WARNING: repos not found in KiCad org: {missing}", file=sys.stderr)
    return [m[n] for n in names if n in m]


def repo_tree(repo: RepoInfo) -> list[dict[str, Any]]:
    branch = urllib.parse.quote(repo.default_branch, safe="")
    url = f"{API}/repos/{repo.full_name}/git/trees/{branch}?recursive=1"
    data = request_json(url)
    if data.get("truncated"):
        print(f"WARNING: tree truncated for {repo.full_name}; use archive mode for complete download", file=sys.stderr)
    return list(data.get("tree", []))


def is_kicad_related_path(path: str) -> bool:
    low = path.lower()
    if low.endswith(KICAD_SUFFIXES):
        return True
    # Special tables do not always have suffixes.
    if low.endswith("sym-lib-table") or low.endswith("fp-lib-table"):
        return True
    return False


def raw_url(repo: RepoInfo, path: str) -> str:
    return f"{RAW}/{repo.full_name}/{urllib.parse.quote(repo.default_branch)}/{urllib.parse.quote(path)}"


def archive_url(repo: RepoInfo) -> str:
    # codeload is direct and avoids HTML redirects.
    return f"https://codeload.github.com/{repo.full_name}/zip/refs/heads/{urllib.parse.quote(repo.default_branch)}"


def download_repo_archive(repo: RepoInfo, out_dir: Path) -> DownloadRecord:
    url = archive_url(repo)
    data = download_bytes(url)
    path = out_dir / "archives" / f"{repo.name}__{repo.default_branch}.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return DownloadRecord("archive", repo.name, f"{repo.default_branch}.zip", url, str(path), len(data), sha256_bytes(data))


def download_file(repo: RepoInfo, path: str, out_dir: Path) -> DownloadRecord:
    url = raw_url(repo, path)
    data = download_bytes(url)
    local = out_dir / "files" / repo.name / path
    local.parent.mkdir(parents=True, exist_ok=True)
    local.write_bytes(data)
    return DownloadRecord("file", repo.name, path, url, str(local), len(data), sha256_bytes(data))


def write_manifest(out_dir: Path, repos: list[RepoInfo], file_inventory: list[dict[str, Any]], downloads: list[DownloadRecord], mode: str, preset: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "tool": "download_kicad_github_assets.py",
        "created_utc": dt.datetime.utcnow().isoformat() + "Z",
        "mode": mode,
        "preset": preset,
        "org": ORG,
        "repo_count": len(repos),
        "file_inventory_count": len(file_inventory),
        "download_count": len(downloads),
        "repos": [asdict(r) for r in repos],
        "file_inventory": file_inventory,
        "downloads": [asdict(d) for d in downloads],
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    with (out_dir / "repos.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(repos[0]).keys()) if repos else ["name"])
        w.writeheader()
        for r in repos:
            w.writerow(asdict(r))

    if file_inventory:
        with (out_dir / "file_inventory.csv").open("w", newline="", encoding="utf-8") as f:
            keys = ["repo", "path", "type", "size", "sha", "url"]
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for row in file_inventory:
                w.writerow({k: row.get(k, "") for k in keys})

    if downloads:
        with (out_dir / "downloads.csv").open("w", newline="", encoding="utf-8") as f:
            keys = list(asdict(downloads[0]).keys())
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for d in downloads:
                w.writerow(asdict(d))

    (out_dir / "README.md").write_text(f"""# KiCad GitHub Download Run

Mode: `{mode}`
Preset: `{preset}`
Created: {dt.datetime.utcnow().isoformat()}Z

## Files

```text
manifest.json
repos.csv
file_inventory.csv        # when inventory mode is used
downloads.csv             # when files/archives are downloaded
archives/                 # repo zip archives
files/                    # raw matched files
```

## Notes

This folder is generated by `kicad/tools/download_kicad_github_assets.py`.
Do not commit downloaded archives or large upstream libraries into memory unless deliberately approved.
""", encoding="utf-8")


def build_inventory(repos: list[RepoInfo]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for repo in repos:
        print(f"Scanning tree: {repo.full_name}@{repo.default_branch}")
        try:
            tree = repo_tree(repo)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR scanning {repo.full_name}: {e}", file=sys.stderr)
            continue
        for item in tree:
            path = item.get("path", "")
            if item.get("type") == "blob" and is_kicad_related_path(path):
                rows.append({
                    "repo": repo.name,
                    "path": path,
                    "type": item.get("type"),
                    "size": item.get("size"),
                    "sha": item.get("sha"),
                    "url": raw_url(repo, path),
                })
    return rows


def download_targeted_files(all_repos: list[RepoInfo], out_dir: Path) -> list[DownloadRecord]:
    m = repo_map(all_repos)
    downloads: list[DownloadRecord] = []
    for repo_name, paths in TARGETED_SOURCE_PATHS.items():
        repo = m.get(repo_name)
        if not repo:
            print(f"WARNING: targeted repo missing: {repo_name}", file=sys.stderr)
            continue
        for path in paths:
            try:
                print(f"Downloading targeted {repo.name}:{path}")
                downloads.append(download_file(repo, path, out_dir))
            except Exception as e:  # noqa: BLE001
                print(f"ERROR downloading {repo.name}:{path}: {e}", file=sys.stderr)
    return downloads


def main() -> None:
    ap = argparse.ArgumentParser(description="Discover/download KiCad GitHub repositories and KiCad project/library files.")
    ap.add_argument("--mode", choices=["inventory", "needed-archives", "all-org-archives", "file-inventory", "files", "targeted-files"], required=True)
    ap.add_argument("--preset", default="generator", help="generator, extended, all, or comma-separated repo names")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--confirm-large", action="store_true", help="required for all-org-archives")
    ap.add_argument("--limit", type=int, default=0, help="optional max files to download in --mode files")
    args = ap.parse_args()

    out_dir = args.out or (Path("external") / "kicad_github" / now_id())
    print(f"Output directory: {out_dir}")
    all_repos = list_org_repos()
    selected = select_repos(all_repos, args.preset)
    file_inventory: list[dict[str, Any]] = []
    downloads: list[DownloadRecord] = []

    if args.mode == "inventory":
        selected = all_repos

    if args.mode == "needed-archives":
        selected = select_repos(all_repos, "generator")
        for repo in selected:
            print(f"Downloading archive: {repo.full_name}")
            downloads.append(download_repo_archive(repo, out_dir))

    elif args.mode == "all-org-archives":
        if not args.confirm_large:
            raise SystemExit("Refusing to download all KiCad org archives without --confirm-large")
        selected = all_repos
        for repo in selected:
            print(f"Downloading archive: {repo.full_name}")
            try:
                downloads.append(download_repo_archive(repo, out_dir))
            except Exception as e:  # noqa: BLE001
                print(f"ERROR downloading archive {repo.full_name}: {e}", file=sys.stderr)

    elif args.mode == "file-inventory":
        file_inventory = build_inventory(selected)

    elif args.mode == "files":
        file_inventory = build_inventory(selected)
        rows = file_inventory[: args.limit] if args.limit else file_inventory
        m = repo_map(all_repos)
        for row in rows:
            repo = m[row["repo"]]
            print(f"Downloading file: {repo.name}:{row['path']}")
            try:
                downloads.append(download_file(repo, row["path"], out_dir))
            except Exception as e:  # noqa: BLE001
                print(f"ERROR downloading file {repo.name}:{row['path']}: {e}", file=sys.stderr)

    elif args.mode == "targeted-files":
        selected = [r for r in selected if r.name in TARGETED_SOURCE_PATHS] or select_repos(all_repos, "generator")
        downloads = download_targeted_files(all_repos, out_dir)

    write_manifest(out_dir, selected, file_inventory, downloads, args.mode, args.preset)
    print(f"Done. Manifest: {out_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
