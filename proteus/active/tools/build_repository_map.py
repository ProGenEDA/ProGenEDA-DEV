"""Build the hash-backed inventory for the reorganized Proteus repository.

The map is intentionally generated from the working tree rather than a hand
maintained list.  It records the migration origin when Git can prove it and
uses only documented prefix rules for moves that were deliberately removed
from Git (for example Proteus GUI workspaces and disposable loader copies).

Run from any directory:

    python proteus/active/tools/build_repository_map.py
    python proteus/active/tools/build_repository_map.py --check
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_ROOT = REPOSITORY_ROOT / "proteus" / "active"
INVENTORY_ROOT = ACTIVE_ROOT / "inventory"
MAP_PATH = INVENTORY_ROOT / "repository_map.csv"
MANIFEST_PATH = INVENTORY_ROOT / "active_manifest.json"
IGNORED_PATH = INVENTORY_ROOT / "ignored_local_items.csv"
DEFAULT_BASELINE = "3acf1fdfb9ed02a1aba0c68da6aed2df1f422e2e"
GENERATED_RELATIVE_PATHS = {
    "proteus/active/inventory/repository_map.csv",
    "proteus/active/inventory/active_manifest.json",
    "proteus/active/inventory/ignored_local_items.csv",
}
PRUNED_LOCAL_DIRECTORIES = {
    ".agents",
    ".git",
    ".venv",
    ".test-install",
    "build",
    "dist",
    "out",
    "__pycache__",
    ".pytest_cache",
    ".vscode",
}
ROOT_CONTROLS = {
    ".gitignore",
    "AGENTS.md",
    "context.md",
    "pyproject.toml",
    "README.md",
}
KICAD_ROOT_FILES = {
    "KICAD_LINUX_HANDOFF.md",
    "LOCAL_RUN_README.md",
    "RUN_LOCAL__ASK_API_AND_GENERATE_KICAD_EXPERIMENTS.bat",
    "RUN_LOCAL__ASK_API_VIA_NOTEPAD_AND_GENERATE_KICAD_EXPERIMENTS.bat",
    "RUN_LOCAL__TEST_GROQ_CONNECTION.bat",
    "RUN_LOCAL__ZIP_LATEST_KICAD_EXPERIMENT.bat",
}


@dataclass(frozen=True)
class MapRecord:
    original_path: str
    destination_path: str
    sha256: str
    git_state: str
    classification: str
    purpose: str
    retention_reason: str
    scope: str


@dataclass(frozen=True)
class IgnoredRecord:
    original_path: str
    local_path: str
    sha256: str
    classification: str
    purpose: str
    retention_reason: str
    ignore_rule: str


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def _git_lines(*args: str) -> list[str]:
    return _git_bytes(*args).decode("utf-8", errors="surrogateescape").splitlines()


def _relative(path: Path) -> str:
    return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    native_path = str(path.resolve())
    # Several preserved donor names exceed Win32's legacy 260-character path
    # limit.  Do not rename them merely to make an inventory pass; use the
    # extended path prefix while reading the original bytes.
    if os.name == "nt" and not native_path.startswith("\\\\?\\"):
        native_path = "\\\\?\\" + native_path
    with open(native_path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_file(path: Path) -> bool:
    native_path = str(path.resolve())
    if os.name == "nt" and not native_path.startswith("\\\\?\\"):
        native_path = "\\\\?\\" + native_path
    return os.path.isfile(native_path)


def _tracked_paths() -> set[str]:
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in _git_bytes("ls-files", "-z").split(b"\0")
        if item
    }


def _baseline_paths(baseline: str) -> set[str]:
    return {
        item.decode("utf-8", errors="surrogateescape")
        for item in _git_bytes("ls-tree", "-r", "-z", "--name-only", baseline).split(b"\0")
        if item
    }


def _tree_blob_paths(revision: str) -> dict[str, list[str]]:
    """Return blob id -> paths without expensive whole-tree rename detection."""

    raw = _git_bytes("ls-tree", "-r", "-z", revision)
    blobs: dict[str, list[str]] = {}
    for item in raw.split(b"\0"):
        if not item:
            continue
        metadata, raw_path = item.split(b"\t", 1)
        fields = metadata.split()
        if len(fields) != 3 or fields[1] != b"blob":
            continue
        blob = fields[2].decode("ascii")
        path = raw_path.decode("utf-8", errors="surrogateescape")
        blobs.setdefault(blob, []).append(path)
    return blobs


def _rename_origins(baseline: str) -> dict[str, str]:
    """Return destination -> baseline origin for unchanged-byte moves.

    `git diff -M` on this corpus attempts a quadratic rename search across
    tens of thousands of binary files.  Blob identity proves all unchanged
    moves deterministically in linear time; the documented prefix rules below
    cover intentionally edited files such as active Python and configuration.
    """

    old_blobs = _tree_blob_paths(baseline)
    current_blobs = _tree_blob_paths("HEAD")
    origins: dict[str, str] = {}
    for blob, destinations in current_blobs.items():
        sources = old_blobs.get(blob, [])
        if len(sources) != 1:
            continue
        for destination in destinations:
            origins[destination] = sources[0]
    return origins


def _migrate_old_path(old_path: str) -> str | None:
    """Known no-loss move rules, used only when Git cannot report a rename."""

    if old_path in {
        "M03_IC_COMPATIBLE_17F_PLUS_RC_1X_TERMINAL_sa.pdsprj",
        "component_placer_latest_regenerated.zip",
    }:
        return "proteus/experiments/imports/" + old_path
    if old_path.startswith("examples/") and old_path.endswith(".json"):
        return "proteus/active/examples/" + old_path[len("examples/") :]
    if old_path in {
        "knowledge/component_catalog_v0.json",
        "knowledge/progen_proteus_executable_preflight_2026_07_16.md",
        "knowledge/terminal_placement_preflight_checklist.md",
        "knowledge/test_results.jsonl",
        "knowledge/validator_history_rules.json",
        "knowledge/value_and_properties_editor_preflight_2026_07_16.md",
    }:
        return "proteus/active/" + old_path
    archive_donor_prefixes = (
        "proteus_ic/donors/manual_downloads_20260616/",
        "proteus_ic/donors/manual_downloads_20260619/",
        "proteus_ic/donors/mixed_large_20260611/",
        "proteus_ic/donors/new_component_mega_supported_terminalized_evidence_20260708/",
    )
    for prefix in archive_donor_prefixes:
        if old_path.startswith(prefix):
            return "proteus/archive/donors/" + old_path[len("proteus_ic/donors/") :]
    if old_path.startswith("proteus_ic/donors/analysis"):
        return "proteus/archive/donors/analysis/" + old_path.rsplit("/", 1)[-1]
    rules = (
        ("src/proteusgen/", "proteus/active/src/proteusgen/"),
        ("fixtures/", "proteus/active/fixtures/"),
        ("schemas/", "proteus/active/schemas/"),
        ("release/", "proteus/active/release/"),
        ("experiments/", "proteus/experiments/runs/"),
        ("tools/proteus_generation/", "proteus/experiments/runners/"),
        ("tools/", "proteus/active/tools/"),
        ("proteus_ic/registry/", "proteus/active/evidence/registry/"),
        ("proteus_ic/donors/", "proteus/active/evidence/donors/"),
        ("proteus_ic/docs/", "proteus/archive/docs/proteus_ic/"),
        ("backups/", "proteus/archive/backups/"),
        ("artifacts/", "proteus/archive/recovered_artifacts/"),
        ("final/", "proteus/archive/historical_examples/final/"),
        ("main learning/", "proteus/archive/docs/main_learning/"),
        ("docs/", "proteus/archive/docs/"),
        ("knowledge/", "proteus/archive/knowledge/"),
        ("examples/", "proteus/archive/historical_examples/examples/"),
        ("prompts/", "proteus/active/docs/prompts/"),
        ("scripts/", "proteus/archive/legacy_entrypoints/"),
    )
    for source_prefix, destination_prefix in rules:
        if old_path.startswith(source_prefix):
            return destination_prefix + old_path[len(source_prefix) :]
    return None


def _infer_origin(destination: str, baseline_paths: set[str], origins: dict[str, str]) -> str:
    if destination in origins:
        return origins[destination]
    if destination in baseline_paths:
        return destination
    # Walk the documented old->new mapping in reverse, accepting it only when
    # the candidate actually existed in the captured baseline.
    if destination.startswith("proteus/experiments/imports/"):
        candidate = destination.rsplit("/", 1)[-1]
        if candidate in baseline_paths:
            return candidate
    if destination.startswith("proteus/active/examples/") and destination.endswith(".json"):
        candidate = "examples/" + destination[len("proteus/active/examples/") :]
        if candidate in baseline_paths:
            return candidate
    if destination.startswith("proteus/active/knowledge/"):
        candidate = "knowledge/" + destination[len("proteus/active/knowledge/") :]
        if candidate in baseline_paths:
            return candidate
    candidate_rules = (
        ("proteus/active/src/proteusgen/", "src/proteusgen/"),
        ("proteus/active/tests/", "tests/"),
        ("proteus/active/fixtures/", "fixtures/"),
        ("proteus/active/schemas/", "schemas/"),
        ("proteus/active/release/", "release/"),
        ("proteus/experiments/runs/", "experiments/"),
        ("proteus/experiments/runners/", "tools/proteus_generation/"),
        ("proteus/active/tools/", "tools/"),
        ("proteus/active/evidence/registry/", "proteus_ic/registry/"),
        ("proteus/active/evidence/donors/", "proteus_ic/donors/"),
        ("proteus/active/evidence/", "proteus_ic/"),
        ("proteus/archive/donors/manual_downloads_20260616/", "proteus_ic/donors/manual_downloads_20260616/"),
        ("proteus/archive/donors/manual_downloads_20260619/", "proteus_ic/donors/manual_downloads_20260619/"),
        ("proteus/archive/donors/mixed_large_20260611/", "proteus_ic/donors/mixed_large_20260611/"),
        ("proteus/archive/donors/new_component_mega_supported_terminalized_evidence_20260708/", "proteus_ic/donors/new_component_mega_supported_terminalized_evidence_20260708/"),
        ("proteus/archive/backups/", "backups/"),
        ("proteus/archive/recovered_artifacts/", "artifacts/"),
        ("proteus/archive/historical_examples/final/", "final/"),
        ("proteus/archive/docs/main_learning/", "main learning/"),
        ("proteus/archive/docs/proteus_ic/", "proteus_ic/docs/"),
        ("proteus/archive/docs/", "docs/"),
        ("proteus/archive/knowledge/", "knowledge/"),
        ("proteus/archive/historical_examples/examples/", "examples/"),
        ("proteus/active/docs/prompts/", "prompts/"),
        ("proteus/archive/legacy_entrypoints/", "scripts/"),
    )
    for destination_prefix, source_prefix in candidate_rules:
        if destination.startswith(destination_prefix):
            candidate = source_prefix + destination[len(destination_prefix) :]
            if candidate in baseline_paths:
                return candidate
    return "new during reorganization"


def _local_ignore_reason(relative: str) -> tuple[str, str] | None:
    """Return classification and exact retained-local reason for ignored paths."""

    normalized = relative.replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    parts = normalized.split("/")
    if name.endswith(".workspace"):
        return ("Proteus workspace sidecar", "*.workspace")
    if name.endswith(".pdsprj") and (name.endswith("_COPY.pdsprj") or name.endswith("_GATE.pdsprj")):
        return ("Disposable Proteus loader copy", "**/*_COPY.pdsprj or **/*_GATE.pdsprj")
    if name.endswith(".pdsprj") and any("local" in part.lower() and "gate" in part.lower() for part in parts[:-1]):
        return ("Disposable Proteus loader copy", "**/*local*gate*/**/*.pdsprj")
    if "Project Backups" in parts:
        return ("Proteus application backup", "**/Project Backups/")
    if any(part in {".venv", ".test-install", "build", "dist", "out", "__pycache__", ".pytest_cache", ".vscode"} for part in parts):
        return ("Reproducible local infrastructure", "directory ignore rule")
    if any(part.startswith(".pytest_tmp") or part.startswith(".codex_tmp") or part.startswith(".codex_pytest") for part in parts):
        return ("Reproducible local test infrastructure", "precise .pytest/.codex ignore rule")
    if any(part.endswith(".egg-info") for part in parts):
        return ("Generated package metadata", "*.egg-info/")
    if name.endswith((".pyc", ".pyo")):
        return ("Python bytecode cache", "*.py[cod]")
    return None


def _walk_files() -> Iterable[Path]:
    for root, directories, filenames in os.walk(REPOSITORY_ROOT):
        current = Path(root)
        retained_directories: list[str] = []
        for directory in directories:
            if (
                directory in PRUNED_LOCAL_DIRECTORIES
                or directory.endswith(".egg-info")
                or directory.startswith(".pytest_tmp")
                or directory.startswith(".codex_tmp")
                or directory.startswith(".codex_pytest")
            ):
                continue
            retained_directories.append(directory)
        directories[:] = retained_directories
        for filename in filenames:
            yield current / filename


def _pruned_local_roots() -> list[Path]:
    """Local directory roots intentionally represented as one ignored item."""

    roots: list[Path] = []
    for child in REPOSITORY_ROOT.iterdir():
        if not child.is_dir():
            continue
        if (
            child.name in PRUNED_LOCAL_DIRECTORIES - {".git", ".agents"}
            or child.name.endswith(".egg-info")
            or child.name.startswith(".pytest_tmp")
            or child.name.startswith(".codex_tmp")
            or child.name.startswith(".codex_pytest")
        ):
            roots.append(child)
    return sorted(roots, key=_relative)


def _classify(relative: str) -> tuple[str, str, str, str]:
    """Return classification, purpose, retention reason, and scope."""

    if relative in ROOT_CONTROLS:
        purpose = {
            ".gitignore": "repository-wide local-artifact policy",
            "AGENTS.md": "repository operating instructions",
            "context.md": "continuity log",
            "pyproject.toml": "cross-package build and command configuration",
            "README.md": "cross-backend repository entry point",
        }[relative]
        return ("repository_control", purpose, "must remain at repository root", "in_scope")
    if relative.startswith(("kicad/", "pspice/")) or relative in KICAD_ROOT_FILES or relative.startswith("tests/test_kicad_"):
        return ("excluded_backend", "KiCad/PSpice material", "explicitly excluded from Proteus migration", "out_of_scope")
    if relative.startswith("proteus/active/"):
        suffix = relative[len("proteus/active/") :]
        if suffix.startswith("src/"):
            return ("active_source", "current Proteus package implementation", "runtime source", "in_scope")
        if suffix.startswith("tests/"):
            return ("active_test", "current Proteus test suite", "relocation and regression validation", "in_scope")
        if suffix.startswith("tools/"):
            return ("active_tool", "current build, generation, or analysis tool", "operational tooling", "in_scope")
        if suffix.startswith("docs/"):
            return ("active_documentation", "current operational documentation", "current user and maintainer reference", "in_scope")
        if suffix.startswith("knowledge/"):
            return ("active_knowledge", "current catalogue, checklist, or validation knowledge", "runtime and validation source of truth", "in_scope")
        if suffix.startswith("schemas/"):
            return ("active_schema", "current structured input schema", "runtime validation", "in_scope")
        if suffix.startswith("examples/"):
            return ("active_example", "current executable input example", "smoke-test and user reference", "in_scope")
        if suffix.startswith("fixtures/"):
            return ("active_fixture", "current test fixture", "active test closure", "in_scope")
        if suffix.startswith("evidence/registry/"):
            return ("active_registry", "runtime donor or component registry", "runtime/test reference closure", "in_scope")
        if suffix.startswith("evidence/donors/"):
            return ("active_donor", "runtime or active-test donor evidence", "deterministic active donor closure", "in_scope")
        if suffix.startswith("release/"):
            return ("active_release", "current portable executable or release note", "current user-facing release", "in_scope")
        if suffix.startswith("inventory/"):
            return ("generated_inventory", "generated repository map or manifest", "reproducible consolidation evidence", "in_scope")
        return ("active_other", "active Proteus support material", "active contract closure", "in_scope")
    if relative.startswith("proteus/experiments/runs/"):
        return ("experiment_run", "dated Proteus experiment output", "preserved reproducibility and user evidence", "in_scope")
    if relative.startswith("proteus/experiments/runners/"):
        return ("experiment_runner", "dated reproducible experiment runner", "historical regeneration entry point", "in_scope")
    if relative.startswith("proteus/experiments/imports/"):
        return ("experiment_import", "imported loose Proteus project or package", "preserved external evidence", "in_scope")
    if relative.startswith("proteus/archive/"):
        subtype = relative[len("proteus/archive/") :].split("/", 1)[0]
        return (f"archive_{subtype}", "preserved historical Proteus material", "no-data-removal archive", "in_scope")
    return ("unclassified", "non-Proteus repository material", "requires explicit classification", "out_of_scope")


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _aggregate_hash(records: Iterable[MapRecord]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item.destination_path):
        if record.sha256 == "SELF_REFERENTIAL_GENERATED_OUTPUT":
            continue
        digest.update(f"{record.destination_path}\0{record.sha256}\n".encode("utf-8"))
    return digest.hexdigest()


def _records(baseline: str) -> tuple[list[MapRecord], list[IgnoredRecord], list[str]]:
    baseline_paths = _baseline_paths(baseline)
    origins = _rename_origins(baseline)
    tracked = _tracked_paths()
    paths = sorted(_walk_files(), key=_relative)
    records: list[MapRecord] = []
    ignored: list[IgnoredRecord] = []
    present_destinations: set[str] = set()
    ignored_origins: set[str] = set()

    for path in _pruned_local_roots():
        relative = _relative(path) + "/"
        ignored.append(
            IgnoredRecord(
                original_path="local-only infrastructure",
                local_path=relative,
                sha256="DIRECTORY_NOT_HASHED",
                classification="Reproducible local infrastructure",
                purpose="local virtual environment, cache, build output, or package metadata",
                retention_reason="recursively retained on disk and explicitly excluded from Git",
                ignore_rule="precise root .gitignore directory rule",
            )
        )

    for path in paths:
        relative = _relative(path)
        if relative.startswith(".git/"):
            continue
        ignore = _local_ignore_reason(relative)
        if ignore and relative not in tracked:
            classification, rule = ignore
            origin = _infer_origin(relative, baseline_paths, origins)
            if origin == "new during reorganization":
                # The reverse migration rules cover intentionally untracked
                # items too, since no Git rename remains after `git rm --cached`.
                for old_path in baseline_paths:
                    if _migrate_old_path(old_path) == relative:
                        origin = old_path
                        break
            ignored.append(
                IgnoredRecord(
                    original_path=origin,
                    local_path=relative,
                    sha256=_sha256(path),
                    classification=classification,
                    purpose="local-only reproducible infrastructure or disposable Proteus state",
                    retention_reason="preserved on disk, explicitly excluded from Git",
                    ignore_rule=rule,
                )
            )
            if origin in baseline_paths:
                ignored_origins.add(origin)
            continue
        if relative not in tracked and relative not in GENERATED_RELATIVE_PATHS:
            # A visible, nonignored file is intentionally retained in the map
            # as new local material, which makes an accidental omission visible.
            state = "untracked_visible"
        elif relative in GENERATED_RELATIVE_PATHS:
            state = "generated_inventory"
        else:
            state = "tracked"
        classification, purpose, retention, scope = _classify(relative)
        origin = _infer_origin(relative, baseline_paths, origins)
        if relative in GENERATED_RELATIVE_PATHS:
            file_hash = "SELF_REFERENTIAL_GENERATED_OUTPUT"
        else:
            file_hash = _sha256(path)
        records.append(
            MapRecord(
                original_path=origin,
                destination_path=relative,
                sha256=file_hash,
                git_state=state if origin == relative else f"{state}_moved",
                classification=classification,
                purpose=purpose,
                retention_reason=retention,
                scope=scope,
            )
        )
        present_destinations.add(relative)

    # Generated outputs might not exist before the first run; list them once
    # with the documented self-reference marker so every in-scope path is visible.
    existing = {record.destination_path for record in records}
    for relative in sorted(GENERATED_RELATIVE_PATHS - existing):
        classification, purpose, retention, scope = _classify(relative)
        records.append(
            MapRecord(
                original_path="generated during reorganization",
                destination_path=relative,
                sha256="SELF_REFERENTIAL_GENERATED_OUTPUT",
                git_state="generated_inventory",
                classification=classification,
                purpose=purpose,
                retention_reason=retention,
                scope=scope,
            )
        )

    record_origins = {record.original_path for record in records if record.original_path in baseline_paths}
    accounted = record_origins | ignored_origins
    missing = sorted(
        path
        for path in baseline_paths
        if path not in accounted and _migrate_old_path(path) != path
    )
    return records, ignored, missing


def build(baseline: str, *, check_only: bool = False) -> int:
    records, ignored, missing = _records(baseline)
    destinations = [record.destination_path for record in records]
    duplicates = sorted({path for path in destinations if destinations.count(path) > 1})
    if duplicates:
        raise RuntimeError(f"Duplicate repository-map destinations: {duplicates[:10]}")
    if missing:
        formatted = "\n".join(missing[:30])
        raise RuntimeError(f"Baseline files are not accounted for ({len(missing)}):\n{formatted}")
    if check_only:
        for record in records:
            if record.sha256 == "SELF_REFERENTIAL_GENERATED_OUTPUT":
                continue
            path = REPOSITORY_ROOT / record.destination_path
            if not _is_file(path) or _sha256(path) != record.sha256:
                raise RuntimeError(f"Hash mismatch: {record.destination_path}")
        if not MAP_PATH.is_file() or not IGNORED_PATH.is_file() or not MANIFEST_PATH.is_file():
            raise RuntimeError("Generated repository inventory is incomplete.")
        with MAP_PATH.open(newline="", encoding="utf-8") as stream:
            recorded_map = list(csv.DictReader(stream))
        expected_map = [asdict(record) for record in records]
        if recorded_map != expected_map:
            raise RuntimeError("repository_map.csv does not match the current working-tree inventory.")
        with IGNORED_PATH.open(newline="", encoding="utf-8") as stream:
            recorded_ignored = list(csv.DictReader(stream))
        expected_ignored = [asdict(record) for record in ignored]
        if recorded_ignored != expected_ignored:
            raise RuntimeError("ignored_local_items.csv does not match the current ignored-local inventory.")
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        active_records = [record for record in records if record.destination_path.startswith("proteus/active/")]
        if manifest.get("active_aggregate_sha256") != _aggregate_hash(active_records):
            raise RuntimeError("active_manifest.json has a stale active aggregate hash.")
        if manifest.get("repository_map_sha256") != _sha256(MAP_PATH):
            raise RuntimeError("active_manifest.json has a stale repository-map hash.")
        if manifest.get("ignored_local_items_sha256") != _sha256(IGNORED_PATH):
            raise RuntimeError("active_manifest.json has a stale ignored-local hash.")
        print(
            json.dumps(
                {
                    "baseline": baseline,
                    "records": len(records),
                    "ignored_local_items": len(ignored),
                    "active_aggregate_sha256": _aggregate_hash(active_records),
                    "status": "ok",
                },
                indent=2,
            )
        )
        return 0

    INVENTORY_ROOT.mkdir(parents=True, exist_ok=True)
    _write_csv(MAP_PATH, list(asdict(records[0]).keys()), (asdict(record) for record in records))
    _write_csv(IGNORED_PATH, list(asdict(ignored[0]).keys()) if ignored else list(IgnoredRecord.__annotations__), (asdict(record) for record in ignored))
    active_records = [record for record in records if record.destination_path.startswith("proteus/active/")]
    manifest = {
        "schema": "progen-proteus-active-manifest/v1",
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "baseline_commit": baseline,
        "active_file_count": len(active_records),
        "all_mapped_file_count": len(records),
        "local_ignored_file_count": len(ignored),
        "active_aggregate_sha256": _aggregate_hash(active_records),
        "repository_map_sha256": _sha256(MAP_PATH),
        "ignored_local_items_sha256": _sha256(IGNORED_PATH),
        "self_reference_policy": "The three generated inventory outputs use SELF_REFERENTIAL_GENERATED_OUTPUT in repository_map.csv; their bytes are protected by the manifest except for the manifest's own documented self-reference.",
        "active_files": [
            {
                "path": record.destination_path,
                "sha256": record.sha256,
                "classification": record.classification,
            }
            for record in sorted(active_records, key=lambda item: item.destination_path)
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "baseline": baseline,
                "records": len(records),
                "ignored_local_items": len(ignored),
                "active_file_count": len(active_records),
                "map": _relative(MAP_PATH),
                "manifest": _relative(MANIFEST_PATH),
            },
            indent=2,
        )
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default=DEFAULT_BASELINE, help="pre-reorganization preservation commit")
    parser.add_argument("--check", action="store_true", help="verify the generated map and hashes without rewriting it")
    args = parser.parse_args()
    return build(args.baseline, check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())
