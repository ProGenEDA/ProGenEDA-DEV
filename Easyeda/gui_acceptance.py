"""Launch a generated project through the registered .eprj association."""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
import time
from urllib.parse import unquote
from urllib.request import urlopen


def _active_window_info() -> dict[str, str]:
    qdbus = shutil.which("qdbus")
    if qdbus is None:
        return {}
    result = subprocess.run(
        [qdbus, "org.kde.KWin", "/KWin", "org.kde.KWin.queryWindowInfo"],
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    info: dict[str, str] = {}
    for line in result.stdout.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            info[key.strip()] = value.strip()
    return info


def _debug_pages() -> list[dict[str, str]]:
    try:
        with urlopen("http://127.0.0.1:9222/json/list", timeout=2) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(value, list):
        return []
    return [
        {
            "title": str(item.get("title") or ""),
            "url": str(item.get("url") or ""),
            "type": str(item.get("type") or ""),
        }
        for item in value
        if isinstance(item, dict)
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_integrity(path: Path) -> bool:
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            return connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
    except sqlite3.Error:
        return False


def _easyeda_processes() -> str:
    return subprocess.run(
        ["pgrep", "-af", r"easyeda-pro/easyeda-pro"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()


def open_project(
    project: Path,
    *,
    wait_seconds: float = 30.0,
    disposable_copy: bool = True,
) -> dict[str, object]:
    project = project.expanduser().resolve()
    if not project.is_file() or project.suffix.lower() != ".eprj":
        raise ValueError(f"Expected an existing .eprj file, received {project}.")
    original_hash = _sha256(project)
    if disposable_copy:
        acceptance_root = Path(
            tempfile.mkdtemp(prefix="progen_easyeda_native_open_")
        )
        launched_project = acceptance_root / project.name
        shutil.copy2(project, launched_project)
    else:
        acceptance_root = project.parent
        launched_project = project
    opener = shutil.which("xdg-open")
    if opener is None:
        raise RuntimeError("xdg-open is unavailable.")
    mime = subprocess.run(
        ["xdg-mime", "query", "filetype", str(launched_project)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    default = subprocess.run(
        ["xdg-mime", "query", "default", mime],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    process = subprocess.Popen(
        [opener, str(launched_project)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + wait_seconds
    converted_projects: list[Path] = []
    while time.monotonic() < deadline:
        converted_projects = [
            path
            for path in acceptance_root.glob("*.eprj2")
            if _sqlite_integrity(path)
        ]
        if converted_projects and _easyeda_processes():
            break
        time.sleep(0.5)
    running = _easyeda_processes()
    # KWin's queryWindowInfo method is interactive and can block automation.
    # CDP project tabs provide a deterministic native-open signal instead.
    window: dict[str, str] = {}
    pages = _debug_pages()
    project_text = str(launched_project)
    debug_project_loaded = any(
        item["type"] == "page"
        and (
            project_text in unquote(item["url"])
            or project_text in item["title"]
        )
        for item in pages
    )
    easyeda_visible = window.get("resourceClass") in {"EasyEDA_Pro", "EasyEDA Pro"}
    activation_required = easyeda_visible and window.get("caption") == "Regist"
    sidecars = sorted(
        path
        for path in acceptance_root.iterdir()
        if path != launched_project
    )
    converted_projects = [
        path
        for path in sidecars
        if path.suffix.lower() == ".eprj2" and _sqlite_integrity(path)
    ]
    native_conversion_completed = bool(converted_projects)
    project_loaded = debug_project_loaded or (
        bool(running) and native_conversion_completed
    )
    original_unchanged = project.is_file() and _sha256(project) == original_hash
    return {
        "project": str(project),
        "launched_project": str(launched_project),
        "disposable_copy": disposable_copy,
        "disposable_directory": str(acceptance_root) if disposable_copy else None,
        "generated_sidecars": [str(path) for path in sidecars],
        "converted_projects": [str(path) for path in converted_projects],
        "native_conversion_completed": native_conversion_completed,
        "original_sha256": original_hash,
        "original_unchanged": original_unchanged,
        "mime": mime,
        "default_application": default,
        "xdg_open_exit": process.poll(),
        "easyeda_processes": running.splitlines() if running else [],
        "active_window": window,
        "debug_pages": pages,
        "process_running": bool(running),
        "easyeda_visible": easyeda_visible,
        "activation_required": activation_required,
        "project_loaded": project_loaded,
        "opened": project_loaded and original_unchanged,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--wait-seconds", type=float, default=30.0)
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Open the audited artifact itself instead of a disposable copy.",
    )
    args = parser.parse_args()
    result = open_project(
        args.project,
        wait_seconds=args.wait_seconds,
        disposable_copy=not args.in_place,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["opened"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
