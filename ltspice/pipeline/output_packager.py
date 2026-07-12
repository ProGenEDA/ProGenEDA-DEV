"""Create separate user and internal artifact archives for LTspice runs."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import zipfile
import re
from typing import Any, Iterable


OUTPUT_SCHEMA = "progen-ltspice-output-artifacts/v0.1"
USER_ZIP_NAME = "PROGEN_LTSPICE_PROJECT.zip"
INTERNAL_ZIP_NAME = "internal_bundle.zip"


def _json(data: Any) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _zip(path: Path, entries: Iterable[tuple[str, bytes]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        written: set[str] = set()
        for name, content in entries:
            normalized = name.replace("\\", "/").lstrip("/")
            if normalized in written:
                continue
            written.add(normalized)
            info = zipfile.ZipInfo(normalized, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, content)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _safe_output_id(circuit_id: object) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "_", str(circuit_id).lower()).strip("._") or "circuit"


def _contained_output_dir(run_dir: Path, circuit_id: object) -> tuple[Path, str]:
    """Return a slugged output directory that cannot escape this run."""

    root = (run_dir / "outputs").resolve()
    safe_id = _safe_output_id(circuit_id)
    output_dir = (root / safe_id).resolve()
    try:
        output_dir.relative_to(root)
    except ValueError as exc:
        raise ValueError("Refusing an output path outside this LTspice run.") from exc
    return output_dir, safe_id


def package_output(
    *,
    run_dir: Path,
    circuit_id: str,
    output_id: str,
    project_dir: Path,
    asc_path: Path,
    original_input: bytes,
    stage_json: dict[str, Any],
) -> dict[str, Any]:
    """Package only openable project assets for users; retain evidence privately."""

    output_dir, safe_circuit_id = _contained_output_dir(run_dir, output_id)
    user_zip = output_dir / "user_project" / USER_ZIP_NAME
    internal_zip = output_dir / "internal" / INTERNAL_ZIP_NAME
    allowed = {".asc", ".asy", ".lib"}
    user_entries: list[tuple[str, bytes]] = []
    for path in sorted(project_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in allowed:
            user_entries.append((f"project/{path.name}", path.read_bytes()))
    if not any(name.endswith(".asc") for name, _ in user_entries):
        raise ValueError("Cannot package an LTspice user archive without an .asc schematic.")
    user_entries.append(
        (
            "project/README_OPEN_IN_LTSPICE.txt",
            (
                "Open the .asc file in LTspice. This archive keeps the required project-local .asy symbols and .lib models "
                "in the same folder as the schematic; do not separate them.\n"
            ).encode("ascii"),
        )
    )
    _zip(user_zip, user_entries)
    internal_entries = [("internal/main-input-original.json", original_input)]
    for name, value in sorted(stage_json.items()):
        internal_entries.append((f"internal/{name}.json", _json(value)))
    internal_entries.append((f"reconstruction/{asc_path.name}", asc_path.read_bytes()))
    _zip(internal_zip, internal_entries)
    manifest = {
        "schema": OUTPUT_SCHEMA,
        "backend": "ltspice",
        "circuit_id": circuit_id,
        "artifact_id": output_id,
        "safe_output_id": safe_circuit_id,
        "serial": None,
        "serial_note": "No LTspice website service code is reserved yet; this package intentionally does not invent one.",
        "user_project": {
            "path": str(user_zip.relative_to(run_dir)),
            "file_name": user_zip.name,
            "sha256": _sha(user_zip),
            "size_bytes": user_zip.stat().st_size,
            "visibility": "user_downloadable",
        },
        "internal_bundle": {
            "path": str(internal_zip.relative_to(run_dir)),
            "file_name": internal_zip.name,
            "sha256": _sha(internal_zip),
            "size_bytes": internal_zip.stat().st_size,
            "visibility": "internal_only",
        },
    }
    manifest_path = output_dir / "output_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_bytes(_json(manifest))
    return manifest
