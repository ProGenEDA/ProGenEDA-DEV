#!/usr/bin/env python3
"""Quality checks for generated KiCad projects."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import validate_schematic


DEFAULT_WINDOWS_KICAD_CLI = Path(r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe")
TOLERATED_ERC_TYPES = {
    # V1 intentionally exposes many named off-page/local IO labels.
    "isolated_pin_label",
    # Generated projects can embed exact/mined source symbols while the local KiCad install has a newer library.
    "lib_symbol_mismatch",
    # V1 power sources are schematic-level symbols, not full KiCad PWR_FLAG/power-tree modeling yet.
    "power_pin_not_driven",
    # Broad generated IC symbols may have unused pins where a no-connect marker would collide with a routed wire.
    "pin_not_connected",
}


def find_kicad_cli(explicit: str | None = None) -> str | None:
    if explicit:
        path = Path(explicit)
        return str(path) if path.exists() else explicit
    discovered = shutil.which("kicad-cli")
    if discovered:
        return discovered
    if DEFAULT_WINDOWS_KICAD_CLI.exists():
        return str(DEFAULT_WINDOWS_KICAD_CLI)
    return None


def discover_schematics(target: Path) -> list[Path]:
    if target.is_file() and target.suffix == ".kicad_sch":
        return [target]
    if target.is_dir():
        exact = sorted(target.glob("OPEN_THIS_PROJECT__*__PROJECT_FILE.kicad_sch"))
        if exact:
            return exact
        return sorted(
            path
            for path in target.rglob("*.kicad_sch")
            if path.name.startswith("OPEN_THIS_PROJECT__") and "__PROJECT_FILE" in path.name
        )
    raise FileNotFoundError(target)


def erc_violations(report: dict[str, Any]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    violations.extend(report.get("violations") or [])
    for sheet in report.get("sheets") or []:
        violations.extend(sheet.get("violations") or [])
    return violations


def run_erc(kicad_cli: str, schematic: Path, output_json: Path) -> dict[str, Any]:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.run(
        [kicad_cli, "sch", "erc", "--format", "json", "--output", str(output_json), str(schematic)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    report = json.loads(output_json.read_text(encoding="utf-8")) if output_json.exists() else {"violations": []}
    violations = erc_violations(report)
    tolerated = [item for item in violations if str(item.get("type", "unknown")) in TOLERATED_ERC_TYPES]
    blocking = [item for item in violations if str(item.get("type", "unknown")) not in TOLERATED_ERC_TYPES]
    by_type = Counter(str(item.get("type", "unknown")) for item in violations)
    tolerated_by_type = Counter(str(item.get("type", "unknown")) for item in tolerated)
    blocking_by_type = Counter(str(item.get("type", "unknown")) for item in blocking)
    return {
        "available": True,
        "exit_code": process.returncode,
        "loaded": process.returncode == 0,
        "stdout": process.stdout.strip(),
        "violation_count": len(violations),
        "violations_by_type": dict(sorted(by_type.items())),
        "tolerated_violation_count": len(tolerated),
        "tolerated_violations_by_type": dict(sorted(tolerated_by_type.items())),
        "blocking_violation_count": len(blocking),
        "blocking_violations_by_type": dict(sorted(blocking_by_type.items())),
        "report": str(output_json),
    }


def check_schematic(
    schematic: Path,
    *,
    report_dir: Path,
    kicad_cli: str | None,
    run_erc_check: bool,
) -> dict[str, Any]:
    text = schematic.read_text(encoding="utf-8")
    static = validate_schematic(text)
    erc: dict[str, Any]
    if run_erc_check and kicad_cli:
        erc = run_erc(kicad_cli, schematic, report_dir / f"{schematic.stem}.erc.json")
    else:
        erc = {
            "available": bool(kicad_cli),
            "skipped": True,
            "violation_count": None,
            "blocking_violation_count": None,
            "tolerated_violation_count": None,
        }
    erc_ok = not run_erc_check or not kicad_cli or (
        erc.get("exit_code") == 0 and erc.get("blocking_violation_count") == 0
    )
    ok = bool(static.get("ok")) and erc_ok
    return {
        "schematic": str(schematic),
        "ok": ok,
        "static": static,
        "erc": erc,
    }


def run_quality_check(
    target: Path,
    *,
    output: Path | None = None,
    kicad_cli: str | None = None,
    run_erc_check: bool = True,
) -> dict[str, Any]:
    schematics = discover_schematics(target)
    report_path = output or target / "kicad_quality_report.json"
    report_dir = report_path.parent / "kicad_erc_reports"
    cli = find_kicad_cli(kicad_cli)
    results = [
        check_schematic(schematic, report_dir=report_dir, kicad_cli=cli, run_erc_check=run_erc_check)
        for schematic in schematics
    ]
    failures = [row for row in results if not row["ok"]]
    summary = {
        "target": str(target),
        "kicad_cli": cli,
        "erc_requested": run_erc_check,
        "schematic_count": len(schematics),
        "ok_count": len(results) - len(failures),
        "failure_count": len(failures),
        "results": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run static and optional KiCad ERC checks on generated KiCad projects.")
    parser.add_argument("target", help="Generated project folder, run folder, or .kicad_sch file")
    parser.add_argument("--output", help="JSON report path")
    parser.add_argument("--kicad-cli", help="Explicit kicad-cli executable path")
    parser.add_argument("--skip-erc", action="store_true", help="Only run static Progen schematic checks")
    args = parser.parse_args()
    result = run_quality_check(
        Path(args.target),
        output=Path(args.output) if args.output else None,
        kicad_cli=args.kicad_cli,
        run_erc_check=not args.skip_erc,
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["failure_count"] == 0 else 2)


if __name__ == "__main__":
    main()
