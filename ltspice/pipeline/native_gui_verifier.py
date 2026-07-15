"""Scoped KDE/Wayland GUI evidence for donor-native LTspice ASC candidates.

Desktop evidence is intentionally separate from deterministic generation.  On
this KDE Wayland workstation, LTspice is an XWayland application, so generic
``active window`` screenshots are not sufficient evidence: another application
can become active between launching LTspice and Spectacle capturing it.

This module uses a short-lived KWin D-Bus script for every sensitive desktop
operation.  The script matches the exact LTspice caption, resource class, and
KWin internal ID; the same ID is used for focus validation and cleanup.  It
never kills a process or closes windows selected only by application class.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from typing import Any, Callable, Iterable

from .donor_asc_parser import parse_donor_asc


NATIVE_GUI_VERIFIER_SCHEMA = "progen-ltspice-donor-native-gui-verifier/v2"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
LTSPICE_RESOURCE_CLASS = "ltspice.exe"
KWIN_RESULT_PREFIX = "PROGEN_LTSPICE_GUI_RESULT"
KWIN_RESULT_TIMEOUT_SECONDS = 3.0
KWIN_POLL_INTERVAL_SECONDS = 0.15


class NativeGuiVerificationError(RuntimeError):
    """The desktop evidence command could not capture a verified target window."""


def expected_ltspice_caption(path: str | Path) -> str:
    """Return LTspice 26's observed schematic caption for one ASC basename."""

    name = Path(path).name
    if not name.lower().endswith(".asc"):
        raise NativeGuiVerificationError(f"Expected an .asc basename, got {name!r}.")
    return f"LTspice - [{name}]"


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


def _safe_batch_name(path: Path) -> str:
    """Make a filesystem-safe, deterministic report stem from an ASC path."""

    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.stem).strip("._") or "ltspice_circuit"


def _render_kwin_script(
    *,
    marker: str,
    operation: str,
    expected_caption: str,
    expected_resource_class: str,
    expected_internal_id: str | None,
) -> str:
    """Render a one-shot KWin script with JSON literals, never interpolated JS.

    Its only side effects are the requested focus or close action on a window
    that matches *all* supplied identity fields.  ``console.log`` is used as a
    scoped, session-local acknowledgement channel; KWin does not provide a
    return value for a completed scripting action over ``/Scripting``.
    """

    if operation not in {"scan", "focus", "assert_active", "close"}:
        raise ValueError(f"Unsupported KWin operation {operation!r}.")
    request = json.dumps(
        {
            "marker": marker,
            "operation": operation,
            "expected_caption": expected_caption,
            "expected_resource_class": expected_resource_class,
            "expected_internal_id": expected_internal_id,
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return f"""// Generated by native_gui_verifier.py; short-lived and exact-match only.
const request = {request};

function stringValue(value) {{
    return value === undefined || value === null ? "" : String(value);
}}

function describe(window) {{
    if (!window) {{
        return null;
    }}
    return {{
        caption: stringValue(window.caption),
        resource_class: stringValue(window.resourceClass),
        resource_name: stringValue(window.resourceName),
        internal_id: stringValue(window.internalId),
        minimized: Boolean(window.minimized)
    }};
}}

const exactMatches = [];
for (const window of workspace.windowList()) {{
    const descriptor = describe(window);
    if (descriptor.caption === request.expected_caption
            && descriptor.resource_class === request.expected_resource_class) {{
        exactMatches.push(window);
    }}
}}
const targetMatches = request.expected_internal_id === null
    ? exactMatches
    : exactMatches.filter((window) => stringValue(window.internalId) === request.expected_internal_id);
const result = {{
    operation: request.operation,
    expected_caption: request.expected_caption,
    expected_resource_class: request.expected_resource_class,
    expected_internal_id: request.expected_internal_id,
    caption_match_count: exactMatches.length,
    target_match_count: targetMatches.length,
    target_matches: targetMatches.map(describe),
    target_active: false,
    close_requested: false
}};

if (request.operation === "focus") {{
    if (targetMatches.length === 1) {{
        const target = targetMatches[0];
        target.minimized = false;
        workspace.activeWindow = target;
        const active = describe(workspace.activeWindow);
        result.active = active;
        result.target_active = active !== null
            && active.internal_id === stringValue(target.internalId)
            && active.caption === request.expected_caption
            && active.resource_class === request.expected_resource_class;
    }}
}} else if (request.operation === "assert_active") {{
    const active = describe(workspace.activeWindow);
    result.active = active;
    result.target_active = targetMatches.length === 1
        && active !== null
        && active.internal_id === stringValue(targetMatches[0].internalId)
        && active.caption === request.expected_caption
        && active.resource_class === request.expected_resource_class;
}} else if (request.operation === "close") {{
    if (targetMatches.length === 1) {{
        // KWin closes this exact internal window only.  No process-level kill
        // and no class-only/window-caption-only fallback is ever used.
        targetMatches[0].closeWindow();
        result.close_requested = true;
    }}
}}

console.log(request.marker + "|" + JSON.stringify(result));
"""


def _journal_result(marker: str) -> dict[str, Any] | None:
    """Read the unique acknowledgement emitted by the short-lived KWin script."""

    journalctl = shutil.which("journalctl")
    if journalctl is None:
        raise NativeGuiVerificationError("journalctl is required to validate KWin scripting results.")
    completed = subprocess.run(
        [journalctl, "--user", "-n", "3000", "--no-pager", "--output=cat"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown journalctl error"
        raise NativeGuiVerificationError(f"Could not read KWin script acknowledgement: {detail}")
    prefix = f"{marker}|"
    for line in reversed(completed.stdout.splitlines()):
        offset = line.find(prefix)
        if offset < 0:
            continue
        raw = line[offset + len(prefix):]
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise NativeGuiVerificationError("KWin emitted an unreadable GUI verification acknowledgement.") from exc
        if not isinstance(result, dict):
            raise NativeGuiVerificationError("KWin emitted a non-object GUI verification acknowledgement.")
        return result
    return None


def _run_kwin_action(
    operation: str,
    *,
    expected_caption: str,
    expected_internal_id: str | None = None,
    expected_resource_class: str = LTSPICE_RESOURCE_CLASS,
) -> dict[str, Any]:
    """Run an exact-match KWin action and return its logged acknowledgement."""

    qdbus = shutil.which("qdbus")
    if qdbus is None:
        raise NativeGuiVerificationError("qdbus is required for KDE KWin GUI verification.")
    token = secrets.token_hex(16)
    marker = f"{KWIN_RESULT_PREFIX}:{token}"
    plugin_name = f"progen_ltspice_gui_{token}"
    script = _render_kwin_script(
        marker=marker,
        operation=operation,
        expected_caption=expected_caption,
        expected_resource_class=expected_resource_class,
        expected_internal_id=expected_internal_id,
    )
    with tempfile.TemporaryDirectory(prefix="progen-ltspice-kwin-") as temporary:
        script_path = Path(temporary) / f"{plugin_name}.js"
        script_path.write_text(script, encoding="utf-8")
        try:
            subprocess.run(
                [qdbus, "org.kde.KWin", "/Scripting", "loadScript", str(script_path), plugin_name],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=KWIN_RESULT_TIMEOUT_SECONDS,
            )
            subprocess.run(
                [qdbus, "org.kde.KWin", "/Scripting", "start"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                timeout=KWIN_RESULT_TIMEOUT_SECONDS,
            )
            deadline = time.monotonic() + KWIN_RESULT_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                result = _journal_result(marker)
                if result is not None:
                    return result
                time.sleep(0.05)
        except subprocess.TimeoutExpired as exc:
            raise NativeGuiVerificationError(f"KWin did not complete the {operation!r} action in time.") from exc
        except subprocess.CalledProcessError as exc:
            stderr = (exc.stderr or "").strip()
            raise NativeGuiVerificationError(
                f"Could not run KWin {operation!r} action over D-Bus: {stderr or exc}"
            ) from exc
        finally:
            # A one-shot script normally self-unloads.  This makes an error
            # path equally scoped and never touches any user-installed script.
            subprocess.run(
                [qdbus, "org.kde.KWin", "/Scripting", "unloadScript", plugin_name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
    raise NativeGuiVerificationError(f"KWin did not acknowledge the {operation!r} action.")


def _wait_for_exact_target(
    *,
    expected_caption: str,
    wait_seconds: float,
    sleeper: Callable[[float], None],
) -> dict[str, Any]:
    """Wait until exactly one newly-opened matching LTspice schematic exists."""

    deadline = time.monotonic() + wait_seconds
    last: dict[str, Any] | None = None
    while True:
        last = _run_kwin_action("scan", expected_caption=expected_caption)
        if last.get("target_match_count") == 1:
            return last
        if time.monotonic() >= deadline:
            break
        sleeper(min(KWIN_POLL_INTERVAL_SECONDS, max(0.0, deadline - time.monotonic())))
    count = 0 if last is None else last.get("target_match_count", 0)
    raise NativeGuiVerificationError(
        f"LTspice did not expose exactly one target window titled {expected_caption!r} within {wait_seconds:g}s "
        f"(matching windows: {count})."
    )


def _close_exact_target(
    *,
    expected_caption: str,
    expected_internal_id: str,
    sleeper: Callable[[float], None],
) -> dict[str, Any]:
    """Close only the target KWin internal ID, then prove it disappeared."""

    close_result = _run_kwin_action(
        "close",
        expected_caption=expected_caption,
        expected_internal_id=expected_internal_id,
    )
    report: dict[str, Any] = {
        "requested": bool(close_result.get("close_requested")),
        "close_action": close_result,
        "status": "not_requested",
    }
    if not report["requested"]:
        report["status"] = "not_closed_target_no_longer_matched"
        return report

    deadline = time.monotonic() + KWIN_RESULT_TIMEOUT_SECONDS
    last_scan: dict[str, Any] | None = None
    while True:
        last_scan = _run_kwin_action(
            "scan",
            expected_caption=expected_caption,
            expected_internal_id=expected_internal_id,
        )
        if last_scan.get("target_match_count") == 0:
            report["status"] = "closed_exact_target"
            report["post_close_scan"] = last_scan
            return report
        if time.monotonic() >= deadline:
            report["status"] = "close_requested_target_still_present"
            report["post_close_scan"] = last_scan
            return report
        sleeper(KWIN_POLL_INTERVAL_SECONDS)


def _write_evidence(path: str | Path | None, evidence: dict[str, Any]) -> None:
    if path is None:
        return
    output = Path(path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    evidence["evidence_path"] = str(output)
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def capture_native_gui_evidence(
    asc_path: str | Path,
    *,
    screenshot_path: str | Path,
    evidence_path: str | Path | None = None,
    wait_seconds: float = 20.0,
    opener: Callable[[list[str]], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    close_after_capture: bool = True,
) -> dict[str, Any]:
    """Open, identify, focus, capture, validate, and close one exact ASC window.

    A pre-existing window with the same caption is treated as user-owned and
    causes a safe failure before launch.  On every post-launch path, cleanup
    can only call ``closeWindow()`` against the KWin ID that this invocation
    discovered.  A screenshot is moved into its requested destination only
    after a second exact-target/active-window KWin validation succeeds.
    """

    if wait_seconds <= 0:
        raise NativeGuiVerificationError("wait_seconds must be positive.")
    candidate = inspect_native_asc_candidate(asc_path)
    evidence: dict[str, Any] = {
        **candidate,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "started",
        "catalogue_promotion": "forbidden_without_recorded_visual_review",
        "required_review": [
            "Confirm the LTspice schematic window was captured and contains no LTspice modal/load error.",
            "Confirm stock glyphs, attributes, direct wires, and ground anchors are readable with no unintended overlap.",
            "Treat KWin target validation as capture provenance, not a substitute for visual circuit review.",
        ],
    }
    expected_caption = expected_ltspice_caption(candidate["asc_path"])
    evidence["desktop_target"] = {
        "caption": expected_caption,
        "resource_class": LTSPICE_RESOURCE_CLASS,
        "backend": "KWin D-Bus scripting + Spectacle",
    }
    target = Path(screenshot_path).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_capture = target.parent / f".{target.name}.{secrets.token_hex(8)}.pending.png"
    owned_internal_id: str | None = None
    launched = False

    try:
        if not candidate["static_boundary_ok"]:
            raise NativeGuiVerificationError("; ".join(candidate["static_boundary_errors"]))
        xdg_open = shutil.which("xdg-open")
        spectacle = shutil.which("spectacle")
        if xdg_open is None:
            raise NativeGuiVerificationError("xdg-open is required to use the registered LTspice desktop association.")
        if spectacle is None:
            raise NativeGuiVerificationError("KDE Spectacle is required to capture the active LTspice window.")

        preflight = _run_kwin_action("scan", expected_caption=expected_caption)
        evidence["prelaunch_target_scan"] = preflight
        if preflight.get("target_match_count") != 0:
            raise NativeGuiVerificationError(
                f"Refusing to touch existing user-owned LTspice window(s) titled {expected_caption!r}."
            )

        command = [xdg_open, str(Path(candidate["asc_path"]))]
        evidence["desktop_launch"] = {"command": command, "association": "xdg-open"}
        try:
            if opener is None:
                subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                opener(command)
        except Exception as exc:
            raise NativeGuiVerificationError(f"Could not launch the ASC through its desktop association: {exc}") from exc
        launched = True

        discovery = _wait_for_exact_target(
            expected_caption=expected_caption,
            wait_seconds=wait_seconds,
            sleeper=sleeper,
        )
        evidence["postlaunch_target_scan"] = discovery
        descriptor = discovery.get("target_matches", [{}])[0]
        owned_internal_id = str(descriptor.get("internal_id", ""))
        if not owned_internal_id:
            raise NativeGuiVerificationError("KWin found a target caption but did not provide a stable internal ID.")
        evidence["desktop_target"]["internal_id"] = owned_internal_id

        focus = _run_kwin_action(
            "focus",
            expected_caption=expected_caption,
            expected_internal_id=owned_internal_id,
        )
        evidence["focus"] = focus
        if focus.get("target_match_count") != 1 or not focus.get("target_active"):
            raise NativeGuiVerificationError("KWin could not focus the exact LTspice target window.")

        subprocess.run(
            [
                spectacle,
                "--background",
                "--nonotify",
                "--activewindow",
                "--delay",
                "1",
                "--output",
                str(temporary_capture),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        width, height = _png_dimensions(temporary_capture)
        post_capture = _run_kwin_action(
            "assert_active",
            expected_caption=expected_caption,
            expected_internal_id=owned_internal_id,
        )
        evidence["post_capture_target_validation"] = post_capture
        if post_capture.get("target_match_count") != 1 or not post_capture.get("target_active"):
            raise NativeGuiVerificationError(
                "Discarded the pending screenshot because the exact LTspice target was not active after capture."
            )
        os.replace(temporary_capture, target)
        evidence["screenshot"] = {
            "path": str(target),
            "bytes": target.stat().st_size,
            "width": width,
            "height": height,
            "target_validation": "passed_before_and_after_capture",
        }
        evidence["ltspice_processes_seen"] = _ltspice_processes()
        evidence["status"] = "captured_target_validated_requires_visual_review"
    except subprocess.CalledProcessError as exc:
        raise NativeGuiVerificationError(f"Could not capture the exact LTspice target with Spectacle: {exc}") from exc
    except Exception as exc:
        if not isinstance(exc, NativeGuiVerificationError):
            exc = NativeGuiVerificationError(str(exc))
        evidence["status"] = "target_validation_failed"
        evidence["error"] = str(exc)
        raise exc
    finally:
        if temporary_capture.exists():
            temporary_capture.unlink()
            evidence["pending_screenshot"] = "discarded_before_target_validation"
        if launched and owned_internal_id is not None and close_after_capture:
            try:
                evidence["cleanup"] = _close_exact_target(
                    expected_caption=expected_caption,
                    expected_internal_id=owned_internal_id,
                    sleeper=sleeper,
                )
            except Exception as cleanup_exc:  # preserve the primary evidence error below
                evidence["cleanup"] = {"status": "cleanup_validation_failed", "error": str(cleanup_exc)}
            if evidence.get("status") == "captured_target_validated_requires_visual_review":
                cleanup_status = evidence["cleanup"].get("status")
                if cleanup_status != "closed_exact_target":
                    evidence["status"] = "captured_target_validated_cleanup_failed_requires_visual_review"
        elif launched and owned_internal_id is not None:
            evidence["cleanup"] = {"status": "left_open_by_request"}
        else:
            evidence["cleanup"] = {"status": "not_needed_no_owned_target"}
        evidence["finished_at"] = datetime.now(timezone.utc).isoformat()
        _write_evidence(evidence_path, evidence)

    return evidence


def capture_native_gui_batch_evidence(
    asc_paths: Iterable[str | Path],
    *,
    output_dir: str | Path,
    wait_seconds: float = 20.0,
) -> dict[str, Any]:
    """Review a finite sequential batch (for example, ten common circuits).

    Each ASC gets its own screenshot/evidence JSON and is closed before the
    next starts.  Failures are recorded per circuit so a bad GUI load cannot
    cause the rest of a review batch to be skipped.
    """

    paths = [Path(item).resolve() for item in asc_paths]
    if not paths:
        raise NativeGuiVerificationError("GUI batch review needs at least one ASC path.")
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    for index, asc_path in enumerate(paths, start=1):
        stem = f"{index:02d}_{_safe_batch_name(asc_path)}"
        screenshot = output / f"{stem}.png"
        evidence_path = output / f"{stem}.json"
        try:
            result = capture_native_gui_evidence(
                asc_path,
                screenshot_path=screenshot,
                evidence_path=evidence_path,
                wait_seconds=wait_seconds,
                close_after_capture=True,
            )
            entries.append({
                "asc_path": str(asc_path),
                "status": result["status"],
                "screenshot": result.get("screenshot", {}).get("path"),
                "evidence": str(evidence_path),
            })
        except NativeGuiVerificationError as exc:
            entries.append({
                "asc_path": str(asc_path),
                "status": "failed",
                "error": str(exc),
                "evidence": str(evidence_path),
            })
    failures = [entry for entry in entries if entry["status"] == "failed"]
    report = {
        "schema": NATIVE_GUI_VERIFIER_SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed" if not failures else "completed_with_failures",
        "requested_count": len(entries),
        "successful_count": len(entries) - len(failures),
        "failed_count": len(failures),
        "entries": entries,
        "batch_close_policy": "each owned exact KWin window is closed before the next ASC launches",
    }
    report_path = output / "batch_gui_evidence.json"
    report["evidence_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Open donor-native ASCs, capture exact LTspice windows, then close them safely.")
    parser.add_argument("asc", type=Path, nargs="+", help="Generated stock-only LTspice .asc candidate(s).")
    parser.add_argument("--screenshot", type=Path, help="PNG destination when reviewing one ASC.")
    parser.add_argument("--evidence", type=Path, help="JSON evidence destination when reviewing one ASC.")
    parser.add_argument("--batch-output-dir", type=Path, help="Directory for sequential multi-ASC screenshot/evidence pairs.")
    parser.add_argument("--wait-seconds", type=float, default=20.0, help="Deadline for LTspice to expose the exact target window.")
    args = parser.parse_args()
    if len(args.asc) == 1:
        if args.screenshot is None:
            parser.error("--screenshot is required when reviewing one ASC.")
        if args.batch_output_dir is not None:
            parser.error("--batch-output-dir is only valid with two or more ASC paths.")
        evidence = capture_native_gui_evidence(
            args.asc[0],
            screenshot_path=args.screenshot,
            evidence_path=args.evidence,
            wait_seconds=args.wait_seconds,
        )
    else:
        if args.batch_output_dir is None:
            parser.error("--batch-output-dir is required when reviewing multiple ASC paths.")
        if args.screenshot is not None or args.evidence is not None:
            parser.error("--screenshot and --evidence are single-ASC options; use --batch-output-dir instead.")
        evidence = capture_native_gui_batch_evidence(
            args.asc,
            output_dir=args.batch_output_dir,
            wait_seconds=args.wait_seconds,
        )
    print(json.dumps(evidence, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()
