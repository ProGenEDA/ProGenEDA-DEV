"""Run the KiCad 400 corpus through the portable executable as a black box."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any
import xml.etree.ElementTree as ET
import zipfile


RUN_SCHEMA = "progen-kicad-common-circuit-qualification-run/v1"
REQUIRED_GENERATION_FLAGS = (
    "all_static_checks_ok",
    "all_value_edits_ok",
    "all_value_validation_ok",
    "all_final_validation_ok",
    "all_component_body_overlap_ok",
    "all_geometry_ok",
    "all_strict_wire_ok",
    "all_local_netlist_ok",
)
REQUIRED_RESULT_FLAGS = (
    "static_checks_ok",
    "value_edit_ok",
    "value_validation_ok",
    "final_validation_ok",
    "component_body_overlap_ok",
    "geometry_ok",
    "strict_wire_ok",
    "local_netlist_ok",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_zip(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as archive:
            return archive.testzip()
    except (OSError, zipfile.BadZipFile) as exc:
        return str(exc)


def _resolve_run_path(base: Path, value: Any) -> Path:
    path = Path(str(value))
    return path if path.is_absolute() else base / path


def _run_cli_export(
    circuit_id: str,
    schematic: Path,
    *,
    kicad_cli: Path,
    appdir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    output = output_dir / f"{circuit_id}.net.xml"
    environment = dict(os.environ)
    environment.update(
        {
            "SHARUN_DIR": str(appdir),
            "APPDIR": str(appdir),
            "KICAD_STOCK_DATA_HOME": str(appdir / "share" / "kicad"),
        }
    )
    started = time.perf_counter()
    process = subprocess.run(
        [
            str(kicad_cli),
            "sch",
            "export",
            "netlist",
            "--format",
            "kicadxml",
            "-o",
            str(output),
            str(schematic),
        ],
        cwd=schematic.parent,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    parse_error = ""
    root_tag = ""
    node_count = 0
    net_count = 0
    try:
        root = ET.parse(output).getroot()
        root_tag = root.tag
        nodes = root.findall("./nets/net/node")
        node_count = len(nodes)
        net_count = len(root.findall("./nets/net"))
    except (OSError, ET.ParseError) as exc:
        parse_error = str(exc)
    return {
        "circuit_id": circuit_id,
        "schematic": str(schematic),
        "netlist": str(output),
        "return_code": process.returncode,
        "root_tag": root_tag,
        "net_count": net_count,
        "node_count": node_count,
        "parse_error": parse_error,
        "stdout": process.stdout.strip(),
        "stderr": process.stderr.strip(),
        "elapsed_seconds": round(time.perf_counter() - started, 4),
        "ok": process.returncode == 0 and not parse_error and root_tag == "export" and net_count > 0,
    }


def _audit_executable_summary(
    summary: dict[str, Any],
    *,
    expected_ids: set[str],
) -> tuple[dict[str, Any], list[tuple[str, Path]]]:
    run_root = Path(str(summary["run_dir"])).resolve()
    generation = summary.get("generation") if isinstance(summary.get("generation"), dict) else {}
    generation_root = _resolve_run_path(run_root, generation.get("run_dir", "generation")).resolve()
    results = generation.get("results") if isinstance(generation.get("results"), list) else []
    failures: list[str] = []
    artifact_failures: list[dict[str, str]] = []
    schematics: list[tuple[str, Path]] = []
    actual_ids = {str(item.get("circuit_id")) for item in results if isinstance(item, dict)}
    if int(summary.get("input_count", -1)) != len(expected_ids):
        failures.append(f"executable input_count is {summary.get('input_count')}, expected {len(expected_ids)}")
    if int(generation.get("project_count", -1)) != len(expected_ids):
        failures.append(f"generated project_count is {generation.get('project_count')}, expected {len(expected_ids)}")
    if not bool(summary.get("all_inputs_fixed")):
        failures.append("not all inputs passed the deterministic input fixer")
    if actual_ids != expected_ids:
        failures.append(
            f"generated IDs differ from corpus: missing={sorted(expected_ids - actual_ids)}, extra={sorted(actual_ids - expected_ids)}"
        )
    for flag in REQUIRED_GENERATION_FLAGS:
        if not bool(generation.get(flag)):
            failures.append(f"generation summary flag {flag} is false")

    for result in results:
        if not isinstance(result, dict):
            failures.append("generation result is not an object")
            continue
        circuit_id = str(result.get("circuit_id"))
        for flag in REQUIRED_RESULT_FLAGS:
            if not bool(result.get(flag)):
                failures.append(f"{circuit_id}: result flag {flag} is false")
        zero_metrics = (
            "unresolved_pin_count",
            "routing_unresolved_pin_count",
            "component_body_overlap_count",
            "deferred_net_count",
            "unrouted_net_count",
            "partial_wire_net_count",
            "geometry_violation_count",
            "strict_wire_violation_count",
            "local_netlist_blocking_failure_count",
            "local_netlist_physical_pin_conflict_count",
            "local_netlist_failed_net_count",
            "local_netlist_merged_net_count",
            "local_netlist_power_ground_short_count",
            "local_netlist_floating_expected_pin_count",
            "value_mismatch_count",
            "final_validation_blocking_failure_count",
        )
        for metric in zero_metrics:
            if int(result.get(metric, 0)) != 0:
                failures.append(f"{circuit_id}: {metric}={result.get(metric)}")

        required_paths = (
            ("project_manifest", result.get("project_manifest")),
            ("final_validation_report", result.get("final_validation_report_file")),
            ("project", result.get("open_this")),
            ("schematic", result.get("schematic_file")),
        )
        for artifact_type, value in required_paths:
            path = _resolve_run_path(generation_root, value)
            if not path.is_file():
                artifact_failures.append({"circuit_id": circuit_id, "artifact": artifact_type, "error": f"missing {path}"})
            elif artifact_type == "schematic":
                schematics.append((circuit_id, path))

        artifacts = result.get("output_artifacts") if isinstance(result.get("output_artifacts"), dict) else {}
        for name in ("user_project", "internal_bundle", "user_pcb"):
            descriptor = artifacts.get(name)
            if descriptor is None and name == "user_pcb":
                continue
            if not isinstance(descriptor, dict):
                artifact_failures.append({"circuit_id": circuit_id, "artifact": name, "error": "missing descriptor"})
                continue
            path = _resolve_run_path(generation_root, descriptor.get("path"))
            if not path.is_file():
                artifact_failures.append({"circuit_id": circuit_id, "artifact": name, "error": f"missing {path}"})
                continue
            expected_hash = str(descriptor.get("sha256") or "")
            if expected_hash and _sha256(path) != expected_hash:
                artifact_failures.append({"circuit_id": circuit_id, "artifact": name, "error": "SHA-256 mismatch"})
            if path.suffix.lower() == ".zip":
                zip_error = _verify_zip(path)
                if zip_error:
                    artifact_failures.append({"circuit_id": circuit_id, "artifact": name, "error": f"ZIP failure: {zip_error}"})

    failures.extend(
        f"{item['circuit_id']}: {item['artifact']} {item['error']}"
        for item in artifact_failures
    )
    pcb_counts = {
        "generated": sum(1 for item in results if isinstance(item, dict) and item.get("pcb_generated")),
        "ready_for_output": sum(1 for item in results if isinstance(item, dict) and item.get("pcb_ready_for_output")),
        "withheld": sum(1 for item in results if isinstance(item, dict) and not item.get("pcb_ready_for_output")),
    }
    return (
        {
            "run_root": str(run_root),
            "generation_root": str(generation_root),
            "expected_circuit_count": len(expected_ids),
            "generated_circuit_count": len(results),
            "all_expected_ids_present": actual_ids == expected_ids,
            "required_generation_flags": {flag: bool(generation.get(flag)) for flag in REQUIRED_GENERATION_FLAGS},
            "artifact_failure_count": len(artifact_failures),
            "pcb_counts": pcb_counts,
            "failure_count": len(failures),
            "failures": failures,
            "ok": not failures,
        },
        schematics,
    )


def run_qualification(
    corpus: Path,
    *,
    executable: Path,
    output_root: Path,
    label: str,
    timeout: float,
    kicad_cli: Path | None,
    appdir: Path | None,
    cli_jobs: int,
) -> dict[str, Any]:
    corpus = corpus.expanduser().resolve()
    source = corpus / "final_json" if (corpus / "final_json").is_dir() else corpus
    corpus_manifest_path = corpus / "manifest.json" if (corpus / "manifest.json").is_file() else source.parent / "manifest.json"
    corpus_manifest = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    expected_ids = {str(item["circuit_id"]) for item in corpus_manifest["records"]}
    executable = executable.expanduser().resolve()
    output_root = output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    command = [
        str(executable),
        "run",
        str(source),
        "--output-root",
        str(output_root),
        "--label",
        label,
        "--routing-mode",
        "combination",
        "--variation-mode",
    ]
    started = time.perf_counter()
    process = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    elapsed = time.perf_counter() - started
    try:
        executable_summary = json.loads(process.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Portable executable did not return JSON: {exc}\n{process.stderr}\n{process.stdout[-4000:]}") from exc
    run_root = Path(str(executable_summary["run_dir"])).resolve()
    (run_root / "qualification_executable_stdout.json").write_text(process.stdout, encoding="utf-8")
    if process.stderr:
        (run_root / "qualification_executable_stderr.txt").write_text(process.stderr, encoding="utf-8")
    audit, schematics = _audit_executable_summary(executable_summary, expected_ids=expected_ids)

    cli_summary: dict[str, Any] = {
        "enabled": kicad_cli is not None,
        "checked_count": 0,
        "passed_count": 0,
        "failed_count": 0,
        "all_passed": True,
        "results": [],
    }
    if kicad_cli is not None:
        kicad_cli = kicad_cli.expanduser().resolve()
        if appdir is None:
            appdir = kicad_cli.parent.parent
        appdir = appdir.expanduser().resolve()
        cli_dir = run_root / "qualification_kicad_cli_netlists"
        cli_dir.mkdir()
        cli_results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, cli_jobs)) as executor:
            futures = {
                executor.submit(
                    _run_cli_export,
                    circuit_id,
                    schematic,
                    kicad_cli=kicad_cli,
                    appdir=appdir,
                    output_dir=cli_dir,
                ): circuit_id
                for circuit_id, schematic in schematics
            }
            for future in as_completed(futures):
                cli_results.append(future.result())
        cli_results.sort(key=lambda item: str(item["circuit_id"]))
        cli_summary = {
            "enabled": True,
            "kicad_cli": str(kicad_cli),
            "appdir": str(appdir),
            "checked_count": len(cli_results),
            "passed_count": sum(1 for item in cli_results if item["ok"]),
            "failed_count": sum(1 for item in cli_results if not item["ok"]),
            "all_passed": len(cli_results) == len(expected_ids) and all(item["ok"] for item in cli_results),
            "results": cli_results,
        }

    report = {
        "schema": RUN_SCHEMA,
        "corpus": str(corpus),
        "corpus_manifest": str(corpus_manifest_path),
        "corpus_count": len(expected_ids),
        "executable": str(executable),
        "executable_sha256": _sha256(executable),
        "command": command,
        "return_code": process.returncode,
        "elapsed_seconds": round(elapsed, 4),
        "executable_audit": audit,
        "kicad_cli_oracle": cli_summary,
        "ok": process.returncode == 0 and audit["ok"] and cli_summary["all_passed"],
    }
    (run_root / "qualification_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (run_root / "QUALIFICATION.md").write_text(
        "# KiCad Common-400 Qualification\n\n"
        f"- Corpus inputs: {len(expected_ids)}\n"
        f"- Portable executable return code: {process.returncode}\n"
        f"- Hosted pipeline and artifact audit: {'PASS' if audit['ok'] else 'FAIL'}\n"
        f"- Installed KiCad parse oracle: {'PASS' if cli_summary['all_passed'] else 'FAIL'} "
        f"({cli_summary['passed_count']}/{cli_summary['checked_count']})\n"
        f"- PCB accepted: {audit['pcb_counts']['ready_for_output']}\n"
        f"- PCB withheld by declared support limits: {audit['pcb_counts']['withheld']}\n"
        f"- Overall: {'PASS' if report['ok'] else 'FAIL'}\n\n"
        "PCB withholding is reported coverage, not silently counted as a board pass. Schematic acceptance "
        "requires the executable's hosted expected-net comparison and every required stage flag.\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path, help="Corpus root or its final_json directory.")
    parser.add_argument("--executable", type=Path, default=Path("kicad/tools/progen-kicad"))
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--label", default="common_400_qualification_v1")
    parser.add_argument("--timeout", type=float, default=14_400.0)
    parser.add_argument("--kicad-cli", type=Path)
    parser.add_argument("--appdir", type=Path)
    parser.add_argument("--cli-jobs", type=int, default=8)
    args = parser.parse_args()
    report = run_qualification(
        args.corpus,
        executable=args.executable,
        output_root=args.output_root,
        label=args.label,
        timeout=args.timeout,
        kicad_cli=args.kicad_cli,
        appdir=args.appdir,
        cli_jobs=args.cli_jobs,
    )
    print(json.dumps({key: value for key, value in report.items() if key not in {"executable_audit", "kicad_cli_oracle"}}, indent=2))
    print(json.dumps({"executable_audit": {key: value for key, value in report["executable_audit"].items() if key != "failures"}}, indent=2))
    print(json.dumps({"kicad_cli_oracle": {key: value for key, value in report["kicad_cli_oracle"].items() if key != "results"}}, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
