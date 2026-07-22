"""Final independent validation for direct Altium pipeline outputs."""

from __future__ import annotations

from dataclasses import dataclass
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
    errors = tuple((*schematic.errors, *package.errors))
    return FinalValidationReport(
        passed=not errors,
        schematic=schematic,
        package=package,
        errors=errors,
    )
