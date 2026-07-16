"""Generate a self-contained, deterministic 100-circuit LTspice bundle.

This is deliberately a thin orchestration layer over the ordinary
``run_donor_native_executable`` path.  It never writes ASC text itself, never
adds placement coordinates to a corpus input, and never invokes the LTspice
GUI or a netlisting executable.  Its job is simply to:

1. write the 100 named shared-JSON inputs from ``common_circuit_corpus``;
2. give those untouched inputs to the normal donor-native executable;
3. copy each emitted ASC into the matching named corpus folder;
4. append deterministic generation facts to that folder's checklist; and
5. package the result in a reproducible ZIP.

All paths supplied to this module must be outside the repository.  Generated
evidence belongs in a run/output location, never in version-controlled source
directories.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Mapping
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
from typing import Any
import zipfile

from ltspice.pipeline.common_circuit_corpus import CORPUS_SIZE, write_common_circuit_corpus
from ltspice.pipeline.donor_native_executable import run_donor_native_executable


BUNDLE_SCHEMA = "progen-ltspice-common-circuit-bundle/v1"
_FIXED_ZIP_ROOT = "ltspice_common_circuit_bundle"
_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
_MANUAL_PLACEMENT_KEYS = frozenset({"ltspice_at", "at", "position", "coordinates"})
_EXTERNAL_ORACLE_SUFFIXES = frozenset({".cir", ".log", ".net", ".raw"})
_NETLIST_RECORD_MARKER = "Installed LTspice netlist validation:"
Executor = Callable[..., Mapping[str, Any]]


class CommonCircuitBundleError(RuntimeError):
    """The complete generated bundle cannot safely be released."""


def _repository_root() -> Path:
    # .../kicad/ltspice/pipeline/common_circuit_bundle.py -> .../kicad
    return Path(__file__).resolve().parents[2]


def _resolved(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def _require_external(path: str | Path, *, label: str) -> Path:
    candidate = _resolved(path)
    root = _repository_root()
    try:
        candidate.relative_to(root)
    except ValueError:
        return candidate
    raise CommonCircuitBundleError(
        f"{label} must be outside repository {root}; generated artifacts are never written into source control."
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as payload:
        for chunk in iter(lambda: payload.read(131072), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_no_manual_placement_hints(value: object, *, context: str = "input") -> None:
    """Reject corpus drift before the ordinary generator sees its inputs."""

    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in _MANUAL_PLACEMENT_KEYS:
                raise CommonCircuitBundleError(
                    f"{context} contains manual placement key {key!r}; the native placer must choose all coordinates."
                )
            _assert_no_manual_placement_hints(item, context=context)
    elif isinstance(value, list):
        for item in value:
            _assert_no_manual_placement_hints(item, context=context)


def _load_inputs(bundle_root: Path) -> dict[str, dict[str, Any]]:
    """Map every corpus circuit ID to its JSON path and target folder."""

    records: dict[str, dict[str, Any]] = {}
    for source in sorted(bundle_root.rglob("circuit.json")):
        document = json.loads(source.read_text(encoding="utf-8"))
        circuit_id = str(document.get("circuit_id") or "")
        if not circuit_id:
            raise CommonCircuitBundleError(f"{source} lacks circuit_id.")
        if circuit_id in records:
            raise CommonCircuitBundleError(f"Corpus repeats circuit_id {circuit_id!r}.")
        _assert_no_manual_placement_hints(document, context=str(source))
        records[circuit_id] = {
            "source": source,
            "folder": source.parent,
            "document": document,
        }
    if len(records) != CORPUS_SIZE:
        raise CommonCircuitBundleError(
            f"Corpus writer produced {len(records)} inputs, expected exactly {CORPUS_SIZE}."
        )
    return records


def _safe_generated_asc(run_dir: Path, result: Mapping[str, Any]) -> Path:
    raw = result.get("asc_path")
    if not isinstance(raw, str) or not raw:
        raise CommonCircuitBundleError(f"Native result has no asc_path: {result!r}")
    candidate = (run_dir / raw).resolve()
    try:
        candidate.relative_to(run_dir)
    except ValueError as exc:
        raise CommonCircuitBundleError(f"Native result ASC path escapes its run directory: {raw!r}") from exc
    if not candidate.is_file():
        raise CommonCircuitBundleError(f"Native result ASC is missing: {candidate}")
    return candidate


def _result_facts(result: Mapping[str, Any], *, destination_name: str, document: Mapping[str, Any]) -> dict[str, Any]:
    validation = result.get("final_validation")
    if not isinstance(validation, Mapping) or not validation.get("ok"):
        raise CommonCircuitBundleError(f"Native result failed final ASC validation: {result.get('circuit_id')!r}")
    return {
        "circuit_id": str(result["circuit_id"]),
        "asc": destination_name,
        "asc_sha256": "",  # filled after the copy is made
        "logical_component_count": len(document.get("components", [])),
        "stock_symbol_count": int(validation.get("symbol_count", 0)),
        "wire_count": int(validation.get("wire_count", 0)),
        "ground_flag_count": int(validation.get("ground_flag_count", 0)),
        "directive_count": int(validation.get("directive_count", 0)),
        "terminal_fallback": str(validation.get("terminal_fallback", "unknown")),
        "custom_symbols": str(validation.get("custom_symbols", "unknown")),
    }


def _append_generation_facts(checklist: Path, facts: Mapping[str, Any]) -> None:
    """Append stable, inspectable facts—not run timing or machine paths."""

    block = "\n".join(
        (
            "",
            "Deterministic donor-native generation facts:",
            f"  circuit_id: {facts['circuit_id']}",
            f"  generated_asc: {facts['asc']}",
            f"  asc_sha256: {facts['asc_sha256']}",
            f"  logical_component_count: {facts['logical_component_count']}",
            f"  stock_symbol_count: {facts['stock_symbol_count']}",
            f"  physical_wire_count: {facts['wire_count']}",
            f"  physical_ground_flag_count: {facts['ground_flag_count']}",
            f"  directive_count: {facts['directive_count']}",
            f"  terminal_fallback: {facts['terminal_fallback']}",
            f"  custom_symbols: {facts['custom_symbols']}",
            "  native_asc_validation: passed",
            "",
        )
    )
    checklist.write_text(checklist.read_text(encoding="utf-8") + block, encoding="utf-8")


def _bundle_manifest_markdown(records: Mapping[str, Mapping[str, Any]]) -> str:
    """A stable text manifest, deliberately avoiding a 101st JSON input."""

    rows = sorted(records.values(), key=lambda item: str(item["folder"].name))
    lines = [
        "# Donor-native common circuit bundle",
        "",
        "Every ASC was produced by the ordinary donor-native executable from its sibling canonical `circuit.json` without explicit placement hints.",
        "",
        "| Folder | Circuit ID | ASC | SHA-256 | Symbols | Wires | Ground flags |",
        "| --- | --- | --- | --- | ---: | ---: | ---: |",
    ]
    for item in rows:
        facts = item["facts"]
        lines.append(
            f"| {item['folder'].name} | {facts['circuit_id']} | {facts['asc']} | "
            f"{facts['asc_sha256']} | {facts['stock_symbol_count']} | {facts['wire_count']} | "
            f"{facts['ground_flag_count']} |"
        )
    lines.extend(
        (
            "",
            "The archive intentionally excludes ephemeral executable internals, GUI screenshots, and external LTspice netlists.",
            "",
        )
    )
    return "\n".join(lines)


def _is_release_file(path: Path, *, bundle_root: Path) -> bool:
    """Keep temporary generator/oracle outputs out of the portable ZIP."""

    relative = path.relative_to(bundle_root)
    if ".native_run" in relative.parts:
        return False
    return path.suffix.casefold() not in _EXTERNAL_ORACLE_SUFFIXES


def _write_deterministic_zip(bundle_root: Path, archive: Path, *, replace_existing: bool = False) -> Path:
    """Create a byte-stable archive for equal input/output contents.

    Zip timestamps and Unix permissions are explicitly fixed, and files are
    added in relative-path order.  The caller must provide a new archive path
    outside the bundle directory so no archive can accidentally include itself.
    """

    if archive.exists() and not replace_existing:
        raise CommonCircuitBundleError(f"Refusing to overwrite existing bundle archive: {archive}")
    try:
        archive.relative_to(bundle_root)
    except ValueError:
        pass
    else:
        raise CommonCircuitBundleError("Bundle archive must not be placed inside its source bundle folder.")
    archive.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(
        path for path in bundle_root.rglob("*")
        if path.is_file() and _is_release_file(path, bundle_root=bundle_root)
    )
    temporary = archive.with_name(f".{archive.name}.{os.getpid()}.pending")
    if temporary.exists():
        raise CommonCircuitBundleError(f"Temporary archive path already exists: {temporary}")
    try:
        with zipfile.ZipFile(temporary, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for path in files:
                relative = path.relative_to(bundle_root).as_posix()
                info = zipfile.ZipInfo(f"{_FIXED_ZIP_ROOT}/{relative}", date_time=_FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                output.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
        os.replace(temporary, archive)
    finally:
        temporary.unlink(missing_ok=True)
    return archive


def record_installed_netlist_validation(
    bundle_directory: str | Path,
    *,
    archive_path: str | Path | None = None,
) -> dict[str, Any]:
    """Record already-completed installed-LTspice ``.net`` exports for a bundle.

    The external executable is deliberately not launched here. This method
    accepts only nonempty native netlists that a caller has already generated,
    verifies all 100 before altering a checklist, records the bounded result
    in every `accuracy_check.txt`, and optionally refreshes the portable ZIP.
    The local oracle sidecars remain inspectable beside the unzipped bundle but
    are excluded from its release archive.
    """

    bundle_root = _require_external(bundle_directory, label="Bundle directory")
    if not bundle_root.is_dir():
        raise CommonCircuitBundleError(f"Bundle directory does not exist: {bundle_root}")
    records = _load_inputs(bundle_root)
    evidence_by_id: dict[str, dict[str, str]] = {}
    versions: set[str] = set()
    for circuit_id, record in sorted(records.items()):
        folder = Path(record["folder"])
        asc = folder / f"{folder.name}.asc"
        net = asc.with_suffix(".net")
        if not asc.is_file():
            raise CommonCircuitBundleError(f"Cannot record netlisting: generated ASC is missing for {circuit_id}: {asc}")
        if not net.is_file() or not net.stat().st_size:
            raise CommonCircuitBundleError(f"Cannot record netlisting: LTspice .net is missing for {circuit_id}: {net}")
        text = net.read_text(encoding="utf-8", errors="replace")
        version = re.search(r"Generated by LTspice\s+([^\r\n]+)", text, flags=re.IGNORECASE)
        if version is None:
            raise CommonCircuitBundleError(f"Cannot record netlisting: {net} lacks an LTspice export header.")
        versions.add(version.group(1).strip())
        evidence_by_id[circuit_id] = {
            "net": net.name,
            "net_sha256": _sha256(net),
        }

    for circuit_id, record in records.items():
        checklist = Path(record["folder"]) / "accuracy_check.txt"
        current = checklist.read_text(encoding="utf-8")
        if _NETLIST_RECORD_MARKER in current:
            raise CommonCircuitBundleError(f"Checklist already has installed netlist evidence: {checklist}")
        item = evidence_by_id[circuit_id]
        checklist.write_text(
            current
            + "\n"
            + _NETLIST_RECORD_MARKER
            + "\n"
            + "  status: passed\n"
            + f"  exported_netlist: {item['net']}\n"
            + f"  exported_netlist_sha256: {item['net_sha256']}\n"
            + "  scope: installed LTspice accepted the generated ASC and exported a native netlist; expected signal response still requires the listed analysis/inspection.\n",
            encoding="utf-8",
        )

    versions_text = ", ".join(sorted(versions))
    bundle_report = bundle_root / "LTSPICE_26_NETLIST_VALIDATION.txt"
    bundle_report.write_text(
        "Installed LTspice netlist validation\n"
        "\n"
        f"Result: passed ({len(evidence_by_id)}/{CORPUS_SIZE} generated ASC files exported a nonempty LTspice netlist)\n"
        f"Observed exporter: {versions_text}\n"
        "Method: each generated ASC was supplied to the installed LTspice executable with -netlist.\n"
        "Scope: confirms native ASC parsing/netlist export. It does not replace the deterministic wire validator or the circuit-specific expected-behavior review.\n"
        "The local .net sidecars are intentionally excluded from the portable ZIP; their SHA-256 values are recorded in each accuracy_check.txt.\n",
        encoding="utf-8",
    )
    archive: Path | None = None
    if archive_path is not None:
        archive = _require_external(archive_path, label="Bundle archive")
        _write_deterministic_zip(bundle_root, archive, replace_existing=True)
    return {
        "schema": BUNDLE_SCHEMA,
        "ok": True,
        "bundle_directory": str(bundle_root),
        "netlisted_count": len(evidence_by_id),
        "ltspice_exporter_versions": sorted(versions),
        "bundle_report": str(bundle_report),
        "archive_path": str(archive) if archive is not None else None,
    }


def build_common_circuit_bundle(
    bundle_directory: str | Path,
    *,
    archive_path: str | Path | None = None,
    retain_native_work: bool = False,
    executor: Executor = run_donor_native_executable,
) -> dict[str, Any]:
    """Generate and package all 100 corpus circuits through the native path.

    ``executor`` is dependency-injected solely for deterministic unit tests;
    normal callers use ``run_donor_native_executable``.  No GUI or external
    netlisting call exists in this module.
    """

    bundle_root = _require_external(bundle_directory, label="Bundle directory")
    if bundle_root.exists() and any(bundle_root.iterdir()):
        raise CommonCircuitBundleError(f"Bundle directory must be new or empty: {bundle_root}")
    archive = _require_external(
        archive_path if archive_path is not None else Path(f"{bundle_root}.zip"),
        label="Bundle archive",
    )
    if archive.exists():
        raise CommonCircuitBundleError(f"Refusing to overwrite existing bundle archive: {archive}")
    try:
        archive.relative_to(bundle_root)
    except ValueError:
        pass
    else:
        raise CommonCircuitBundleError("Bundle archive must be outside the bundle directory.")

    # This writer creates 100 named folders and only canonical user JSON—no
    # native output or coordinate hints.  The ordinary executable is invoked
    # immediately afterwards using those exact files as its source directory.
    written_inputs = write_common_circuit_corpus(bundle_root)
    if len(written_inputs) != CORPUS_SIZE:
        raise CommonCircuitBundleError(f"Corpus writer returned {len(written_inputs)} inputs, expected {CORPUS_SIZE}.")
    records = _load_inputs(bundle_root)
    native_work = bundle_root / ".native_run"

    try:
        summary = executor(bundle_root, output_root=native_work, label="common_circuit_bundle")
    except Exception as exc:
        raise CommonCircuitBundleError(f"Ordinary donor-native execution failed before a complete bundle was available: {exc}") from exc
    if not isinstance(summary, Mapping) or not summary.get("ok"):
        failures = summary.get("results", []) if isinstance(summary, Mapping) else []
        raise CommonCircuitBundleError(f"Ordinary donor-native execution rejected corpus inputs: {failures!r}")
    if int(summary.get("accepted_count", -1)) != CORPUS_SIZE or int(summary.get("input_count", -1)) != CORPUS_SIZE:
        raise CommonCircuitBundleError(
            "Ordinary donor-native execution did not accept exactly all 100 corpus inputs: "
            f"accepted={summary.get('accepted_count')!r}, input_count={summary.get('input_count')!r}."
        )
    run_dir_value = summary.get("run_dir")
    if not isinstance(run_dir_value, str):
        raise CommonCircuitBundleError("Ordinary donor-native execution returned no run_dir.")
    run_dir = _resolved(run_dir_value)
    try:
        run_dir.relative_to(native_work)
    except ValueError as exc:
        raise CommonCircuitBundleError("Ordinary donor-native run escaped its dedicated external work directory.") from exc

    results = summary.get("results")
    if not isinstance(results, list) or len(results) != CORPUS_SIZE:
        raise CommonCircuitBundleError("Ordinary donor-native execution returned an incomplete result list.")
    seen: set[str] = set()
    completed: dict[str, dict[str, Any]] = {}
    for raw_result in results:
        if not isinstance(raw_result, Mapping) or not raw_result.get("ok"):
            raise CommonCircuitBundleError(f"Native generation has a failed result: {raw_result!r}")
        circuit_id = str(raw_result.get("circuit_id") or "")
        if circuit_id not in records or circuit_id in seen:
            raise CommonCircuitBundleError(f"Native result has unknown or repeated circuit ID {circuit_id!r}.")
        seen.add(circuit_id)
        record = records[circuit_id]
        origin = _safe_generated_asc(run_dir, raw_result)
        destination = Path(record["folder"]) / f"{Path(record['folder']).name}.asc"
        shutil.copyfile(origin, destination)
        facts = _result_facts(raw_result, destination_name=destination.name, document=record["document"])
        facts["asc_sha256"] = _sha256(destination)
        checklist = Path(record["folder"]) / "accuracy_check.txt"
        _append_generation_facts(checklist, facts)
        completed[circuit_id] = {**record, "facts": facts}
    if len(completed) != CORPUS_SIZE:
        raise CommonCircuitBundleError("Native generation did not produce one ASC for every corpus folder.")

    # Keep only the user-facing corpus in the release ZIP.  On failure the
    # work directory is intentionally preserved for deterministic diagnosis.
    if not retain_native_work:
        shutil.rmtree(native_work)
    (bundle_root / "BUNDLE_MANIFEST.md").write_text(_bundle_manifest_markdown(completed), encoding="utf-8")
    produced_archive = _write_deterministic_zip(bundle_root, archive)
    return {
        "schema": BUNDLE_SCHEMA,
        "ok": True,
        "bundle_directory": str(bundle_root),
        "archive_path": str(produced_archive),
        "circuit_count": CORPUS_SIZE,
        "generated_asc_count": len(completed),
        "native_work_retained": retain_native_work,
        "items": [
            deepcopy(completed[circuit_id]["facts"])
            for circuit_id in sorted(completed, key=lambda item: Path(completed[item]["folder"]).name)
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and package the 100-circuit donor-native LTspice corpus.")
    parser.add_argument("output", type=Path, help="New or empty output directory outside this repository.")
    parser.add_argument("--archive", type=Path, help="New ZIP path outside the output directory; default is OUTPUT.zip.")
    parser.add_argument("--retain-native-work", action="store_true", help="Keep ordinary executable internals beside the bundle for diagnosis (excluded from ZIP).")
    args = parser.parse_args()
    result = build_common_circuit_bundle(
        args.output,
        archive_path=args.archive,
        retain_native_work=args.retain_native_work,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":  # pragma: no cover
    main()
