"""Registry and integrity checks for clean Proteus fixture projects."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def repository_root() -> Path:
    """Locate repository data when executing from a checkout or installed CLI."""

    configured = os.environ.get("PROTEUSGEN_REPO_ROOT")
    if configured:
        root = Path(configured)
        if (root / "fixtures" / "manifest.json").exists():
            return root
        raise FileNotFoundError(f"`PROTEUSGEN_REPO_ROOT` does not contain fixtures/manifest.json: {root}")
    candidates = (Path.cwd(), *Path.cwd().parents, *Path(__file__).resolve().parents)
    for candidate in candidates:
        if (candidate / "fixtures" / "manifest.json").exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate fixtures/manifest.json. Run from the repository checkout or set `PROTEUSGEN_REPO_ROOT`."
    )


@dataclass(frozen=True)
class Fixture:
    id: str
    path: Path
    sha256: str
    role: str
    source: str
    status: str
    recipe: str | None = None

    def verify(self) -> bool:
        return hashlib.sha256(self.path.read_bytes()).hexdigest() == self.sha256


class FixtureRegistry:
    def __init__(self, fixtures: tuple[Fixture, ...], pending: tuple[dict[str, Any], ...] = ()) -> None:
        self._fixtures = {fixture.id: fixture for fixture in fixtures}
        self.pending = pending

    @classmethod
    def load(cls, path: str | Path | None = None) -> "FixtureRegistry":
        manifest_path = Path(path) if path is not None else repository_root() / "fixtures" / "manifest.json"
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        fixtures = tuple(
            Fixture(
                id=item["id"],
                path=manifest_path.parent / item["path"],
                sha256=item["sha256"],
                role=item["role"],
                source=item["source"],
                status=item["status"],
                recipe=item.get("recipe"),
            )
            for item in data["fixtures"]
        )
        return cls(fixtures=fixtures, pending=tuple(data.get("pending_fixtures", [])))

    def get(self, fixture_id: str) -> Fixture:
        try:
            return self._fixtures[fixture_id]
        except KeyError as exc:
            raise KeyError(f"Unknown fixture `{fixture_id}`.") from exc

    def verify_all(self) -> list[str]:
        return [fixture.id for fixture in self._fixtures.values() if not fixture.verify()]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fixtures": [
                {
                    "id": fixture.id,
                    "path": str(fixture.path),
                    "sha256": fixture.sha256,
                    "role": fixture.role,
                    "source": fixture.source,
                    "status": fixture.status,
                    "recipe": fixture.recipe,
                    "verified": fixture.verify(),
                }
                for fixture in self._fixtures.values()
            ],
            "pending_fixtures": list(self.pending),
        }
