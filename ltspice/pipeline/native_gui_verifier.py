"""Explicit desktop verification for donor-native LTspice ASC candidates.

This tool is intentionally separate from the deterministic generator: opening
a desktop application is an evidence action, not a prerequisite for ordinary
headless generation. It launches the ASC through the registered desktop
association, captures the active LTspice window with KDE Spectacle, and writes
structured facts for a human/agent visual assessment. It never converts a
candidate into a supported catalogue entry by itself.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Callable

from .donor_asc_parser import parse_donor_asc


NATIVE_GUI_VERIFIER_SCHEMA = "progen-ltspice-donor-native-gui-verifier/v1"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class NativeGuiVerificationError(RuntimeError):
    """The desktop evidence command could not capture a reviewable window."""


def inspect_native_asc_candidate(path: str | Path) -> dict[str, Any]:
    """Return deterministic native-boundary facts before a desktop launch."""

    asc_path = Path(path).resolve()
    if asc_path.suffix.lower() != ".asc" or not asc_path.is_file():
        raise NativeGuiVerificationError(f"Expected an existing .asc file, got {asc_path}.")
    document = parse_donor_asc(asc_path)
    errors: list[str] = []
    if document.version != "4.1":
        errors.append(f"Version {document.version!r} is not donor-native Version 4.1.")
    if any("progeneda" in symbol.name.casefold() for symbol in document.symbols):
        errors.append("ASC contains a legacy ProGenEDA custom symbol.")
    if any(flag.name != "0" for flag in document.flags):
        errors.append("ASC contains a non-ground FLAG terminal.")
    return {
        "schema": NATIVE_GUI_VERIFIER_SCHEMA,
        "asc_path": str(asc_path),
        "static_boundary_ok": not errors,
        "static_boundary_errors": errors,
        "encoding": document.encoding,
        "symbol_names": [symbol.name for symbol in document.symbols],
        "symbol_refs": [symbol.ref for symbol in document.symbols],
        "wire_count": len(document.wires),
        "ground_flag_count": len(document.flags),
        "directive_count": len(document.directives),
        "terminal_fallback": "forbidden",
        "custom_symbols": "forbidden",
    }


def _png_dimensions(path: Path) -> tuple[int, int]:
    payload = path.read_bytes()
    if len(payload) < 24 or not payload.startswith(PNG_SIGNATURE) or payload[12:16] != b"IHDR":
        raise NativeGuiVerificationError(f"Spectacle did not produce a valid PNG at {path}.")
    return int.from_bytes(payload[16:20], "big"), int.from_bytes(payload[20:24], "big")


def _ltspice_processes() -> list[str]:
    executable = shutil.which("pgrep")
    if executable is None:
        return []
    completed = subprocess.run(
        [executable, "-af", "LTspice.exe"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return [line for line in completed.stdout.splitlines() if line.strip()]


def capture_native_gui_evidence(
    asc_path: str | Path,
    *,
    screenshot_path: str | Path,
    evidence_path: str | Path | None = None,
    wait_seconds: float = 5.0,
    opener: Callable[[list[str]], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Open one ASC through its desktop association and capture its window.

    The resulting state deliberately remains
    ``captured_requires_visual_review``. A reviewer must inspect the PNG for
    an LTspice load dialog, symbol readability, and unwanted overlaps before
    changing the permanent catalogue status.
    """

    if wait_seconds <= 0:
        raise NativeGuiVerificationError("wait_seconds must be positive.")
    candidate = inspect_native_asc_candidate(asc_path)
    if not candidate["static_boundary_ok"]:
        raise NativeGuiVerificationError("; ".join(candidate["static_boundary_errors"]))
    target = Path(screenshot_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    xdg_open = shutil.which("xdg-open")
    spectacle = shutil.which("spectacle")
    if xdg_open is None:
        raise NativeGuiVerificationError("xdg-open is required to use the registered LTspice desktop association.")
    if spectacle is None:
        raise NativeGuiVerificationError("KDE Spectacle is required to capture the active LTspice window.")

    command = [xdg_open, str(Path(candidate["asc_path"]))]
    try:
        if opener is None:
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            opener(command)
    except Exception as exc:
        raise NativeGuiVerificationError(f"Could not launch the ASC through its desktop association: {exc}") from exc
    sleeper(float(wait_seconds))
    try:
        subprocess.run(
            # Give the desktop compositor a final moment to raise the newly
            # opened LTspice window before Spectacle resolves "active".
            [spectacle, "--background", "--nonotify", "--activewindow", "--delay", "2", "--output", str(target)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:
        raise NativeGuiVerificationError(f"Could not capture the active LTspice window: {exc}") from exc
    width, height = _png_dimensions(target)
    evidence = {
        **candidate,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "desktop_launch": {"command": command, "association": "xdg-open"},
        "ltspice_processes_seen": _ltspice_processes(),
        "screenshot": {"path": str(target), "bytes": target.stat().st_size, "width": width, "height": height},
        "status": "captured_requires_visual_review",
        "required_review": [
            "Confirm the LTspice schematic window, rather than another active application, was captured.",
            "Reject any LTspice modal/load error.",
            "Confirm stock glyphs, attributes, direct wires, and ground anchors are readable with no unintended overlap.",
        ],
        "catalogue_promotion": "forbidden_without_recorded_visual_review",
    }
    if evidence_path is not None:
        output = Path(evidence_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        evidence["evidence_path"] = str(output)
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description="Open a donor-native ASC through LTspice and capture GUI evidence.")
    parser.add_argument("asc", type=Path, help="Generated stock-only LTspice .asc candidate.")
    parser.add_argument("--screenshot", type=Path, required=True, help="PNG destination for the active LTspice window.")
    parser.add_argument("--evidence", type=Path, help="Optional JSON evidence destination.")
    parser.add_argument("--wait-seconds", type=float, default=5.0, help="Seconds to wait for the desktop association to focus LTspice.")
    args = parser.parse_args()
    evidence = capture_native_gui_evidence(
        args.asc,
        screenshot_path=args.screenshot,
        evidence_path=args.evidence,
        wait_seconds=args.wait_seconds,
    )
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()
