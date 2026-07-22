"""Deterministic project/file naming stage for direct Altium generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .ir import AltiumCircuit
from .naming import is_safe_project_stem
from .pipeline_contracts import PipelineError


FILE_NAME_SCHEMA = "progen-altium-file-name-decision/v1"


class FileNameDecisionError(PipelineError):
    """A normalized project name cannot safely become native output paths."""


@dataclass(frozen=True)
class FileNameDecision:
    project_stem: str
    project_directory: str
    project_file: str
    schematic_file: str

    def json(self) -> dict[str, Any]:
        result = asdict(self)
        result["schema"] = FILE_NAME_SCHEMA
        return result


def decide_file_names(circuit: AltiumCircuit) -> FileNameDecision:
    """Convert the normalized project stem into stable, path-safe native names."""

    stem = circuit.name
    if not is_safe_project_stem(stem):
        raise FileNameDecisionError(f"Normalized project stem is not path-safe: {stem!r}")
    return FileNameDecision(
        project_stem=stem,
        project_directory=stem,
        project_file=f"{stem}.PrjPcb",
        schematic_file=f"Schematic/{stem}.SchDoc",
    )
