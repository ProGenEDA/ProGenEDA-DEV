"""Package-aware entry point for the portable ProgenProteus executable."""

from __future__ import annotations

from proteusgen.proteus_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
