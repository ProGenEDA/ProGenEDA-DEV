"""Launch a generated project through the registered .eprj association."""

from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
import shutil
import subprocess
import time


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


def open_project(project: Path, *, wait_seconds: float = 12.0) -> dict[str, object]:
    project = project.expanduser().resolve()
    if not project.is_file() or project.suffix.lower() != ".eprj":
        raise ValueError(f"Expected an existing .eprj file, received {project}.")
    opener = shutil.which("xdg-open")
    if opener is None:
        raise RuntimeError("xdg-open is unavailable.")
    mime = subprocess.run(
        ["xdg-mime", "query", "filetype", str(project)],
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
        [opener, str(project)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(wait_seconds)
    running = subprocess.run(
        [
            "pgrep",
            "-af",
            r"^/home/[^/]+/\.local/opt/easyeda-pro/easyeda-pro(?: |$)",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    window = _active_window_info()
    easyeda_visible = window.get("resourceClass") == "EasyEDA_Pro"
    activation_required = easyeda_visible and window.get("caption") == "Regist"
    project_loaded = easyeda_visible and not activation_required
    return {
        "project": str(project),
        "mime": mime,
        "default_application": default,
        "xdg_open_exit": process.poll(),
        "easyeda_processes": running.splitlines() if running else [],
        "active_window": window,
        "process_running": bool(running),
        "easyeda_visible": easyeda_visible,
        "activation_required": activation_required,
        "project_loaded": project_loaded,
        "opened": project_loaded,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("project", type=Path)
    parser.add_argument("--wait-seconds", type=float, default=12.0)
    args = parser.parse_args()
    result = open_project(args.project, wait_seconds=args.wait_seconds)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["opened"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
