"""Final independent validation for direct Altium pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Any

from .direct_validator import DirectValidationReport, validate_direct_schematic
from .native_writer import NativeWriteResult
from .project_package import ProjectPackageReport, inspect_project_package


FINAL_VALIDATION_SCHEMA = "progen-altium-final-validation/v1"


@dataclass(frozen=True)
class FinalValidationReport:
    passed: bool
    schematic: DirectValidationReport
    package: ProjectPackageReport
    errors: tuple[str, ...]

    def json(self) -> dict[str, Any]:
        return {
            "schema": FINAL_VALIDATION_SCHEMA,
            "passed": self.passed,
            "schematic": self.schematic.json(),
            "package": self.package.json(),
            "errors": list(self.errors),
        }


def validate_final_output(native: NativeWriteResult, project_archive: str) -> FinalValidationReport:
    """Reparse saved files and archive inventory rather than trusting stage memory."""

    schematic = validate_direct_schematic(native.schematic_file, native.expected_contract)
    package = inspect_project_package(project_archive)
    errors = [*schematic.errors, *package.errors]
    archive_files = {item.path: item for item in package.files}
    archive_root = native.project_directory.parent
    expected_project_path = native.project_file.relative_to(archive_root).as_posix()
    expected_schematic_path = native.schematic_file.relative_to(archive_root).as_posix()
    if set(package.project_files) != {expected_project_path}:
        errors.append(
            f"archive project inventory is not exactly {[expected_project_path]!r}: "
            f"{list(package.project_files)!r}"
        )
    if set(package.schematic_files) != {expected_schematic_path}:
        errors.append(
            f"archive schematic inventory is not exactly {[expected_schematic_path]!r}: "
            f"{list(package.schematic_files)!r}"
        )
    expected_inventory = {expected_project_path, expected_schematic_path}
    if set(archive_files) != expected_inventory:
        errors.append(
            "archive contains files outside the validated schematic project inventory: "
            f"{sorted(set(archive_files) - expected_inventory)}"
        )
    for saved in (native.project_file, native.schematic_file):
        expected_path = saved.relative_to(archive_root).as_posix()
        archived = archive_files.get(expected_path)
        if archived is None:
            errors.append(f"archive omits validated file {expected_path!r}")
            continue
        saved_hash = hashlib.sha256(Path(saved).read_bytes()).hexdigest()
        if archived.sha256 != saved_hash:
            errors.append(f"archive payload differs from validated file {expected_path!r}")
    errors_tuple = tuple(errors)
    return FinalValidationReport(
        passed=not errors_tuple,
        schematic=schematic,
        package=package,
        errors=errors_tuple,
    )
