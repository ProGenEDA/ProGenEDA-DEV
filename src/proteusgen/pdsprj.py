"""Utilities for Proteus `.pdsprj` ZIP-style containers.

These helpers are intentionally conservative. They do not know the full
Proteus project format. They only perform container-level operations that
were repeatedly validated during the research conversation:

- list internal files
- extract internal files
- repack internal files
- copy a project and replace selected internal files
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo


@dataclass(frozen=True)
class PdsprjInfo:
    """Basic information about a `.pdsprj` container."""

    path: Path
    names: list[str]
    has_project_xml: bool
    has_root_dsn: bool
    has_root_cdb: bool
    has_pwrails: bool


REQUIRED_INTERNAL_FILES = (
    "PROJECT.XML",
    "ROOT.DSN",
    "ROOT.CDB",
    "SCRIPTS/PWRRAILS.DAT",
)
DETERMINISTIC_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def _write_deterministic(zf: ZipFile, name: str, data: bytes, compression: int) -> None:
    """Write an archive member without host-time metadata."""

    info = ZipInfo(filename=name, date_time=DETERMINISTIC_ZIP_TIMESTAMP)
    info.compress_type = compression
    info.external_attr = 0o600 << 16
    zf.writestr(info, data)


def inspect_pdsprj(path: str | Path) -> PdsprjInfo:
    """Return internal file listing and required-file flags."""

    p = Path(path)
    with ZipFile(p, "r") as zf:
        names = zf.namelist()
    names_set = set(names)
    return PdsprjInfo(
        path=p,
        names=names,
        has_project_xml="PROJECT.XML" in names_set,
        has_root_dsn="ROOT.DSN" in names_set,
        has_root_cdb="ROOT.CDB" in names_set,
        has_pwrails="SCRIPTS/PWRRAILS.DAT" in names_set,
    )


def extract_pdsprj(path: str | Path, out_dir: str | Path) -> None:
    """Extract a `.pdsprj` container to a directory."""

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "r") as zf:
        zf.extractall(out)


def repack_pdsprj(
    source_dir: str | Path,
    output_path: str | Path,
    *,
    compression: int = ZIP_DEFLATED,
) -> None:
    """Pack a directory into a `.pdsprj` ZIP-style container.

    Files are written in sorted path order for deterministic output.
    Use `compression=ZIP_STORED` to test no-compression containers.
    """

    src = Path(source_dir)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    with ZipFile(out, "w") as zf:
        for file_path in sorted(p for p in src.rglob("*") if p.is_file()):
            arcname = file_path.relative_to(src).as_posix()
            _write_deterministic(zf, arcname, file_path.read_bytes(), compression)


def read_internal_file(path: str | Path, internal_name: str) -> bytes:
    """Read one internal file from a `.pdsprj`."""

    with ZipFile(path, "r") as zf:
        return zf.read(internal_name)


def write_project_from_parts(
    template_project: str | Path,
    output_path: str | Path,
    replacements: dict[str, bytes],
    *,
    compression: int = ZIP_DEFLATED,
) -> None:
    """Create a new `.pdsprj` by replacing selected internal files.

    This is useful for controlled experiments such as replacing ROOT.CDB
    while preserving ROOT.DSN, PROJECT.XML, and scripts from a template.
    """

    with ZipFile(template_project, "r") as zin:
        names = zin.namelist()
        original = {name: zin.read(name) for name in names}

    merged = {**original, **replacements}

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(out, "w") as zout:
        for name in names:
            if name in merged:
                _write_deterministic(zout, name, merged[name], compression)
        for name in sorted(set(merged) - set(names)):
            _write_deterministic(zout, name, merged[name], compression)
