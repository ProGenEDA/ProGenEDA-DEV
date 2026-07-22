"""Package public Altium projects and private deterministic pipeline evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import zipfile

from .pipeline_contracts import PipelineError


PACKAGER_SCHEMA = "progen-altium-output-packager/v1"


class OutputPackagingError(PipelineError):
    """Generated output cannot be packaged into the release artifact contract."""


@dataclass(frozen=True)
class PackagingResult:
    project_archive: Path
    internal_archive: Path | None

    def json(self) -> dict[str, Any]:
        return {
            "schema": PACKAGER_SCHEMA,
            "project_archive": str(self.project_archive),
            "internal_archive": str(self.internal_archive) if self.internal_archive else None,
        }


def package_project(project_directory: Path, run_directory: Path, project_name: str) -> Path:
    """Create the user-facing ZIP with only native project files."""

    if not project_directory.is_dir():
        raise OutputPackagingError(f"Project directory does not exist: {project_directory}")
    archive = run_directory / f"{project_name}.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(project_directory.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(run_directory))
    return archive


def package_internal_evidence(run_directory: Path, internal_directory: Path, project_name: str) -> Path:
    """Create a private archive containing normalized input and every stage artifact."""

    if not internal_directory.is_dir():
        raise OutputPackagingError(f"Internal evidence directory does not exist: {internal_directory}")
    archive = run_directory / f"{project_name}_internal.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(run_directory.rglob("*")):
            if not path.is_file() or path == archive:
                continue
            if path.parent == run_directory and path.suffix.casefold() == ".zip":
                continue
            bundle.write(path, path.relative_to(run_directory))
    return archive
