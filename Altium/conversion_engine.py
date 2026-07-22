"""Strict adapter for EasyEDA's locally installed Altium conversion engine.

This is a development bridge, not an Altium file-format reimplementation. It
only invokes the vendor-supplied local converter when a source format is
advertised by that converter. In particular, it rejects ProGenEDA's SQLite
``.eprj`` projects because the public converter does not expose them as a
decoder input.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any, Iterable

from .project_package import ProjectPackageReport, inspect_project_package


SQLITE_MAGIC = b"SQLite format 3\x00"
ENGINE_ENVIRONMENT_VARIABLE = "PROGENEDA_EASYEDA_CONVERTER"
_ENGINE_RELATIVE_PATH = Path(
    "resources/app/assets/chameleon/3.2.13.c7cfec74/js/convert-node-server.js"
)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.+-]+")


class ConverterError(RuntimeError):
    """The local conversion bridge cannot produce a verified package."""


class ConverterUnavailable(ConverterError):
    """No usable local conversion-engine script was found."""


class UnsupportedBridgeSource(ConverterError):
    """The requested input is not accepted by the engine's public decoder API."""


@dataclass(frozen=True)
class ConverterSupport:
    script: str
    node: str
    decoder_types: tuple[str, ...]
    encoder_types: tuple[str, ...]
    raw_output: str

    def json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BridgeResult:
    package_path: str
    source_path: str
    source_type: str
    support: ConverterSupport
    package: ProjectPackageReport

    def json(self) -> dict[str, Any]:
        return {
            "package_path": self.package_path,
            "source_path": self.source_path,
            "source_type": self.source_type,
            "support": self.support.json(),
            "package": self.package.json(),
        }


def _candidate_scripts() -> Iterable[Path]:
    configured = os.environ.get(ENGINE_ENVIRONMENT_VARIABLE)
    if configured:
        yield Path(configured).expanduser()
    home = Path.home()
    roots = (
        home / ".local/opt/easyeda-pro",
        Path("/opt/apps/easyeda-pro"),
        Path("/shared/easyeda-pro-linux-x64-3.2.149/easyeda-pro"),
    )
    for root in roots:
        yield root / _ENGINE_RELATIVE_PATH
        yield from sorted(
            root.glob("resources/app/assets/chameleon/*/js/convert-node-server.js"),
            reverse=True,
        )


def locate_converter_script(override: Path | str | None = None) -> Path:
    """Locate a converter installation without importing EasyEDA application code."""

    candidates = [Path(override).expanduser()] if override is not None else list(_candidate_scripts())
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    searched = ", ".join(str(candidate) for candidate in candidates)
    raise ConverterUnavailable(
        "EasyEDA's conversion engine was not found. Set "
        f"{ENGINE_ENVIRONMENT_VARIABLE} to convert-node-server.js. Searched: {searched}"
    )


def _node_executable(override: Path | str | None = None) -> str:
    if override is not None:
        candidate = Path(override).expanduser()
        if candidate.is_file():
            return str(candidate)
        raise ConverterUnavailable(f"Node executable does not exist: {candidate}")
    node = shutil.which("node")
    if node is None:
        raise ConverterUnavailable("Node.js is required to run the local conversion engine.")
    return node


def _parse_support_types(output: str, key: str) -> tuple[str, ...]:
    match = re.search(rf"{re.escape(key)}\s*:\s*\[(.*?)\]", output, flags=re.DOTALL)
    if match is None:
        return ()
    return tuple(re.findall(r"['\"]([^'\"]+)['\"]", match.group(1)))


def probe_converter(
    *,
    converter_script: Path | str | None = None,
    node_executable: Path | str | None = None,
    timeout_seconds: int = 30,
) -> ConverterSupport:
    """Ask the local converter for its actual public decoder/encoder registry."""

    script = locate_converter_script(converter_script)
    node = _node_executable(node_executable)
    try:
        completed = subprocess.run(
            [node, str(script), "--cmd", "supports"],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConverterUnavailable(
            f"Conversion-engine registry probe timed out after {timeout_seconds} seconds."
        ) from exc
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0:
        raise ConverterUnavailable(
            f"Conversion-engine registry probe failed with exit code {completed.returncode}: {output}"
        )
    decoders = _parse_support_types(output, "decoderTypes")
    encoders = _parse_support_types(output, "encoderTypes")
    if not decoders and not encoders:
        raise ConverterUnavailable("Conversion-engine registry probe returned no supported format list.")
    return ConverterSupport(
        script=str(script),
        node=node,
        decoder_types=decoders,
        encoder_types=encoders,
        raw_output=output,
    )


def _safe_name(value: str) -> str:
    result = _SAFE_NAME.sub("_", value.strip()).strip("_.")
    return result or "altium_project"


def _reject_sqlite_easyeda_project(source: Path) -> None:
    try:
        magic = source.read_bytes()[: len(SQLITE_MAGIC)]
    except OSError as exc:
        raise UnsupportedBridgeSource(f"Cannot read conversion source {source}: {exc}") from exc
    if magic == SQLITE_MAGIC:
        raise UnsupportedBridgeSource(
            f"{source.name} is a current SQLite EasyEDA project. The installed public "
            "Chameleon decoder registry does not expose this .eprj/.epro SQLite format; "
            "do not rename it and do not pass it to easyeda-pro-2. Use a genuine "
            "easyeda-pro-2 archive or wait for the direct Altium source-backed emitter."
        )


def convert_with_local_engine(
    source_path: Path | str,
    *,
    output_directory: Path | str,
    source_type: str = "easyeda-pro-2",
    project_name: str | None = None,
    converter_script: Path | str | None = None,
    node_executable: Path | str | None = None,
    timeout_seconds: int = 180,
) -> BridgeResult:
    """Convert one genuinely supported source into a validated Altium ZIP.

    The conversion engine owns translation into its internal model. This
    wrapper owns source preflight, immutable output naming, and structural
    validation of the package it returns.
    """

    source = Path(source_path).expanduser().resolve()
    if not source.is_file():
        raise UnsupportedBridgeSource(f"Conversion source does not exist: {source}")
    _reject_sqlite_easyeda_project(source)
    support = probe_converter(
        converter_script=converter_script,
        node_executable=node_executable,
    )
    if source_type not in support.decoder_types:
        raise UnsupportedBridgeSource(
            f"The local converter does not advertise {source_type!r} as a decoder. "
            f"Available: {list(support.decoder_types)}"
        )
    if "altium" not in support.encoder_types:
        raise ConverterUnavailable("The local converter does not advertise an Altium encoder.")

    output_root = Path(output_directory).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    output_name = _safe_name(project_name or source.stem)
    expected = output_root / f"{output_name}.zip"
    if expected.exists():
        raise ConverterError(
            f"Refusing to overwrite existing Altium project package: {expected}. "
            "Choose a new output directory or project name."
        )
    params = {
        "projectName": output_name,
        "decodingOptions": {
            "decodingType": source_type,
            "decodingFilePath": str(source),
        },
        "encodingOptions": {
            "encodingType": "altium",
            "savingDirPath": str(output_root),
            "savingFileName": output_name,
        },
        "logLevel": "error",
    }
    try:
        completed = subprocess.run(
            [support.node, support.script, "--cmd", "conversion", "--params", json.dumps(params)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise ConverterError(
            f"Altium conversion timed out after {timeout_seconds} seconds."
        ) from exc
    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    if completed.returncode != 0:
        raise ConverterError(
            f"Altium conversion exited with {completed.returncode}: {output[-4000:]}"
        )
    if not expected.is_file():
        raise ConverterError(
            "Conversion completed without the expected Altium ZIP "
            f"{expected.name}. Converter output: {output[-4000:]}"
        )
    package = inspect_project_package(expected)
    if not package.passed:
        raise ConverterError(
            "Converted Altium package failed structural validation: " + "; ".join(package.errors)
        )
    return BridgeResult(
        package_path=str(expected),
        source_path=str(source),
        source_type=source_type,
        support=support,
        package=package,
    )
