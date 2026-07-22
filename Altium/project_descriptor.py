"""Pinned donor-backed Altium ``.PrjPcb`` descriptor rendering."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

from .pipeline_contracts import PipelineError


PROJECT_TEMPLATE_PATH = (
    Path(__file__).with_name("source_pack") / "donors" / "nodemcu_project_seed.PrjPcb"
)
PROJECT_TEMPLATE_SHA256 = "ab26512b221a97af8f2f39342ecf886d134b24b685a8cb1a196720e0cc9b9f96"
PROJECT_TEMPLATE_SOURCE_COMMIT = "587a0881f7ee9c02b628323909afa40c92162c1a"
_DOCUMENT_PATH = re.compile(r"(?m)^DocumentPath=.*$")


class ProjectDescriptorError(PipelineError):
    """The pinned native project descriptor cannot be loaded or rendered."""


def _template_text() -> str:
    try:
        data = PROJECT_TEMPLATE_PATH.read_bytes()
    except OSError as exc:
        raise ProjectDescriptorError(f"Cannot read project descriptor donor: {exc}") from exc
    digest = hashlib.sha256(data).hexdigest()
    if digest != PROJECT_TEMPLATE_SHA256:
        raise ProjectDescriptorError(
            f"Project descriptor donor hash mismatch: expected {PROJECT_TEMPLATE_SHA256}, got {digest}."
        )
    text = data.decode("utf-8")
    required = ("[Design]", "[Preferences]", "[Document1]", "[Configuration1]")
    if any(section not in text for section in required) or len(_DOCUMENT_PATH.findall(text)) != 1:
        raise ProjectDescriptorError("Project descriptor donor is missing its locked native sections.")
    return text


def render_project_descriptor(schematic_path: str) -> str:
    """Change only the donor's schematic document path."""

    if not schematic_path or any(character in schematic_path for character in "\r\n=|"):
        raise ProjectDescriptorError("Generated schematic path is unsafe for a .PrjPcb descriptor.")
    return _DOCUMENT_PATH.sub(f"DocumentPath={schematic_path}", _template_text(), count=1)


def project_template_provenance() -> dict[str, str]:
    return {
        "path": str(PROJECT_TEMPLATE_PATH.resolve()),
        "sha256": PROJECT_TEMPLATE_SHA256,
        "source_repository": "https://github.com/nodemcu/nodemcu-devkit",
        "source_commit": PROJECT_TEMPLATE_SOURCE_COMMIT,
        "license": "MIT",
    }
