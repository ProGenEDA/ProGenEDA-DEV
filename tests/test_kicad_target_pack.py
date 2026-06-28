from __future__ import annotations

import json
from pathlib import Path

from kicad.automation.generate_target_pack import TARGET_BUILDERS, generate, target_id, validate_targets


def test_target_pack_covers_c01_to_c55() -> None:
    circuits = [builder() for builder in TARGET_BUILDERS]
    validate_targets(circuits)
    assert [target_id(item) for item in circuits] == [f"C{i:02d}" for i in range(1, 56)]


def test_target_pack_generates_static_valid_projects(tmp_path: Path) -> None:
    manifest = generate(tmp_path / "target_pack", clean=True)
    assert manifest["target_count"] == 55
    assert manifest["ok_count"] == 55
    assert manifest["failure_count"] == 0
    assert max(row["router_warning_count"] for row in manifest["results"]) <= 3

    first = tmp_path / "target_pack" / manifest["results"][0]["manifest"]
    first_manifest = json.loads(first.read_text(encoding="utf-8"))
    assert first_manifest["static_checks"]["ok"]
    assert first_manifest["source_reference"]["conclusions"][-1] == "All required V1 source reference files are present."
