"""Compatibility facade for the full direct-Altium generation pipeline.

New code should normally use :func:`Altium.pipeline.generate_pipeline` so it
can inspect individual stage contracts.  This module preserves the original
public API and delegates to that pipeline; it no longer owns placement,
routing, terminal, value, writing, or validation logic itself.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping

from .pipeline import generate_pipeline
from .pipeline_contracts import (
    DIRECT_GENERATION_SCHEMA as GENERATOR_SCHEMA,
    PipelineError as DirectGenerationError,
    PipelineResult as DirectGenerationResult,
    PlacedComponent as GeneratedComponent,
    RoutingPlan,
    TerminalLabel,
    WireSegment,
)


def generate_direct_project(
    input_value: Path | str | Mapping[str, Any],
    *,
    output_root: Path | str,
    routing_mode: str | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> DirectGenerationResult:
    """Run the complete direct Altium pipeline and return its public result."""

    return generate_pipeline(
        input_value,
        output_root=output_root,
        routing_mode=routing_mode,
        on_progress=on_progress,
    )


__all__ = [
    "DirectGenerationError",
    "DirectGenerationResult",
    "GeneratedComponent",
    "GENERATOR_SCHEMA",
    "RoutingPlan",
    "TerminalLabel",
    "WireSegment",
    "generate_direct_project",
]
