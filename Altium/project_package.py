"""Structural inspection for Altium project archives.

The converter engine exports one ZIP containing native Altium project
artifacts. This validator never claims to understand every binary record in
``.SchDoc`` or ``.PcbDoc``; it verifies the project-package contract, file
integrity, and declared document inventory before a desktop-open gate.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path, PurePosixPath
from typing import Any
import zipfile


PACKAGE_SCHEMA = "progen-altium-project-package-report/v1"


class ProjectPackageError(ValueError):
    """The archive is not a structurally usable Altium project package."""


@dataclass(frozen=True)
class PackageFile:
    path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class ProjectPackageReport:
    passed: bool
    archive: str
    project_files: tuple[str, ...]
    schematic_files: tuple[str, ...]
    pcb_files: tuple[str, ...]
    symbol_libraries: tuple[str, ...]
    footprint_libraries: tuple[str, ...]
    declared_documents: tuple[str, ...]
    files: tuple[PackageFile, ...]
    errors: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = PACKAGE_SCHEMA
        return result


def _safe_entry(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def _decode_project(data: bytes) -> tuple[str, ...]:
    """Extract document references from the textual ``.PrjPcb`` descriptor."""

    text = data.decode("utf-8-sig", errors="replace")
    documents: list[str] = []
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if key.casefold() in {"documentpath", "document"} and value:
            documents.append(value.replace("\\", "/"))
    return tuple(sorted(set(documents)))


def _validate_project_descriptor(path: str, data: bytes) -> tuple[str, ...]:
    text = data.decode("utf-8-sig", errors="replace")
    sections = {
        line.strip()[1:-1]
        for line in text.splitlines()
        if line.strip().startswith("[") and line.strip().endswith("]")
    }
    required = {"Design", "Preferences", "Configuration1"}
    missing = sorted(required - sections)
    errors: list[str] = []
    if missing:
        errors.append(f"{path} is missing native project sections: {missing}")
    if not any(section.casefold().startswith("document") for section in sections):
        errors.append(f"{path} has no native Document section")
    if "Version=1.0" not in text:
        errors.append(f"{path} has no supported Design Version=1.0 declaration")
    return tuple(errors)


def inspect_project_package(path: Path | str) -> ProjectPackageReport:
    """Inspect an exported ZIP without requiring Altium Designer to be installed."""

    archive = Path(path).expanduser().resolve()
    if not archive.is_file():
        raise ProjectPackageError(f"Altium project package does not exist: {archive}")
    try:
        with zipfile.ZipFile(archive) as bundle:
            infos = [info for info in bundle.infolist() if not info.is_dir()]
            names = [info.filename for info in infos]
            unsafe = [name for name in names if not _safe_entry(name)]
            duplicates = sorted({name for name in names if names.count(name) > 1})
            files = tuple(
                PackageFile(
                    path=info.filename,
                    bytes=info.file_size,
                    sha256=hashlib.sha256(bundle.read(info)).hexdigest(),
                )
                for info in sorted(infos, key=lambda item: item.filename.casefold())
            )
            by_suffix = {
                suffix: tuple(
                    sorted(
                        (info.filename for info in infos if info.filename.casefold().endswith(suffix)),
                        key=str.casefold,
                    )
                )
                for suffix in (".prjpcb", ".schdoc", ".pcbdoc", ".schlib", ".pcblib")
            }
            declared_documents: set[str] = set()
            declared_document_candidates: dict[str, set[str]] = {}
            descriptor_errors: list[str] = []
            for project_path in by_suffix[".prjpcb"]:
                project_data = bundle.read(project_path)
                descriptor_errors.extend(_validate_project_descriptor(project_path, project_data))
                project_parent = PurePosixPath(project_path).parent
                for document in _decode_project(project_data):
                    declared_documents.add(document)
                    declared_document_candidates.setdefault(document, set()).update(
                        {
                            document,
                            str(project_parent / document),
                        }
                    )
    except (OSError, zipfile.BadZipFile) as exc:
        raise ProjectPackageError(f"Cannot read Altium project ZIP {archive}: {exc}") from exc

    errors: list[str] = []
    if unsafe:
        errors.append(f"archive contains unsafe paths: {sorted(unsafe)}")
    if duplicates:
        errors.append(f"archive contains duplicate paths: {duplicates}")
    errors.extend(descriptor_errors)
    if not by_suffix[".prjpcb"]:
        errors.append("archive has no .PrjPcb project descriptor")
    if not by_suffix[".schdoc"]:
        errors.append("archive has no .SchDoc schematic document")
    empty = [item.path for item in files if item.bytes == 0]
    if empty:
        errors.append(f"archive contains empty native artifacts: {empty}")
    archive_names = {name.replace("\\", "/") for name in names}
    missing_declarations = sorted(
        document
        for document, candidates in declared_document_candidates.items()
        if not candidates.intersection(archive_names)
    )
    if missing_declarations:
        errors.append(f".PrjPcb declares missing documents: {missing_declarations}")

    return ProjectPackageReport(
        passed=not errors,
        archive=str(archive),
        project_files=by_suffix[".prjpcb"],
        schematic_files=by_suffix[".schdoc"],
        pcb_files=by_suffix[".pcbdoc"],
        symbol_libraries=by_suffix[".schlib"],
        footprint_libraries=by_suffix[".pcblib"],
        declared_documents=tuple(sorted(declared_documents)),
        files=files,
        errors=tuple(errors),
    )
