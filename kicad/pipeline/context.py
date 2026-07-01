"""Shared state and result helpers for the KiCad stage pipeline."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class PipelineError(RuntimeError):
    """Raised when a required pipeline stage cannot continue."""

    def __init__(self, result: "StageResult") -> None:
        message = f"{result.stage} failed"
        if result.errors:
            message += f": {'; '.join(result.errors)}"
        super().__init__(message)
        self.result = result


@dataclass
class StageResult:
    stage: str
    ok: bool = True
    summary: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage,
            "ok": self.ok,
            "summary": self.summary,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "data": deepcopy(self.data),
        }


@dataclass
class PipelineContext:
    original_input: Any
    out_dir: Path | None = None
    circuit: dict[str, Any] = field(default_factory=dict)
    placement_plan: Any | None = None
    placement_report: dict[str, Any] = field(default_factory=dict)
    trace: list[StageResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def record(self, result: StageResult) -> StageResult:
        self.trace.append(result)
        self.warnings.extend(result.warnings)
        self.errors.extend(result.errors)
        return result

    def trace_dict(self) -> list[dict[str, Any]]:
        return [result.as_dict() for result in self.trace]

    def pipeline_summary(self) -> dict[str, Any]:
        return {
            "schema": "progen-kicad-placer-pipeline/v0.1",
            "stage_count": len(self.trace),
            "ok": not self.errors and bool(self.placement_report.get("valid", True)),
            "placement": self.placement_report,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "trace": self.trace_dict(),
        }
