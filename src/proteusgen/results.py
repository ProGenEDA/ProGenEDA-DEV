"""Structured ingestion of human Proteus test results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .templates import repository_root

REQUIRED_RESULT_FIELDS = {"test_id", "proteus_version", "opened", "result_summary"}


def validate_result(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return ["Result JSON must be an object."]
    errors = [f"Missing required field `{field}`." for field in sorted(REQUIRED_RESULT_FIELDS - set(payload))]
    if "opened" in payload and not isinstance(payload["opened"], bool):
        errors.append("`opened` must be boolean.")
    if "proteus_version" in payload and not isinstance(payload["proteus_version"], str):
        errors.append("`proteus_version` must be a string.")
    if "test_id" in payload and not isinstance(payload["test_id"], str):
        errors.append("`test_id` must be a string.")
    if payload.get("acceptance_authoritative") is True:
        if payload.get("runtime_role") != "proteus_8_13_authoritative":
            errors.append("Authoritative acceptance requires `runtime_role` to be `proteus_8_13_authoritative`.")
        if not str(payload.get("proteus_version", "")).startswith("8.13"):
            errors.append("Authoritative acceptance requires a Proteus 8.13 result.")
    return errors


def record_result(payload: dict[str, Any], output_path: str | Path | None = None) -> Path:
    errors = validate_result(payload)
    if errors:
        raise ValueError(" ".join(errors))
    path = Path(output_path) if output_path is not None else repository_root() / "knowledge" / "test_results.jsonl"
    existing_ids: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                existing_ids.add(json.loads(line).get("test_id", ""))
    if payload["test_id"] in existing_ids:
        raise ValueError(f"Test result `{payload['test_id']}` already exists.")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return path
