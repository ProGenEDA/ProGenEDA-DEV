"""Build a single-file executable Python archive for the EasyEDA backend."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import tempfile
import zipapp


def build(output: Path) -> Path:
    package_root = Path(__file__).resolve().parents[2]
    source_package = package_root / "Easyeda"
    output = output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="progen_easyeda_build_") as temporary:
        stage = Path(temporary)
        shutil.copytree(
            source_package,
            stage / "Easyeda",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tests", "examples"),
        )
        (stage / "__main__.py").write_text(
            "from Easyeda.executable import main\nraise SystemExit(main())\n",
            encoding="ascii",
        )
        zipapp.create_archive(
            stage,
            target=output,
            interpreter="/usr/bin/env python3",
            compressed=True,
        )
    output.chmod(0o755)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("Easyeda/dist/progen-easyeda"),
    )
    args = parser.parse_args()
    print(build(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
