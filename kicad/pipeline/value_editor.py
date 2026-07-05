"""Value Editor stage for generated KiCad schematics.

The component values come from the main CircuitIR JSON. This stage applies that
contract to the generated schematic file and records exactly what changed.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from kicad.generator.kicad_json_to_project import q

from .kicad_symbol_library import _balanced_block


VALUE_EDITOR_SCHEMA = "progen-kicad-value-editor/v0.1"


def expected_component_values(circuit: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for component in circuit.get("components", []):
        if not isinstance(component, dict):
            continue
        ref = str(component.get("ref") or component.get("id") or "").strip()
        if not ref:
            continue
        raw_value = component.get("value")
        if raw_value in (None, ""):
            raw_value = component.get("name")
        if raw_value in (None, ""):
            raw_value = component.get("kind") or component.get("type") or ref
        values[ref] = str(raw_value)
    return values


def _property_value(block: str, property_name: str) -> str | None:
    pattern = re.compile(rf'\(property\s+{re.escape(q(property_name))}\s+"((?:\\.|[^"])*)"', re.S)
    match = pattern.search(block)
    if not match:
        return None
    return bytes(match.group(1), "utf-8").decode("unicode_escape")


def _replace_value_property(block: str, expected_value: str) -> tuple[str, bool]:
    quoted = q(expected_value)
    pattern = re.compile(r'(\(property\s+"Value"\s+)"((?:\\.|[^"])*)"', re.S)
    if pattern.search(block):
        updated = pattern.sub(lambda match: match.group(1) + quoted, block, count=1)
        return updated, updated != block

    reference_pattern = re.compile(r'(\(property\s+"Reference"\s+"(?:\\.|[^"])*".*?\))', re.S)
    match = reference_pattern.search(block)
    if not match:
        return block, False
    insert = f'\n    (property "Value" {quoted} (at 0 0 0) (effects (font (size 1.27 1.27))))'
    return block[: match.end()] + insert + block[match.end() :], True


def _replace_instance_values(block: str, expected_value: str) -> tuple[str, int]:
    quoted = q(expected_value)
    pattern = re.compile(r'(\(value\s+)"((?:\\.|[^"])*)"', re.S)
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        if match.group(0) != match.group(1) + quoted:
            count += 1
        return match.group(1) + quoted

    return pattern.sub(repl, block), count


def _symbol_instance_blocks(text: str) -> list[tuple[int, int, str]]:
    blocks: list[tuple[int, int, str]] = []
    start = 0
    while True:
        index = text.find("(symbol (lib_id", start)
        if index < 0:
            break
        block = _balanced_block(text, index)
        if block is None:
            start = index + len("(symbol (lib_id")
            continue
        blocks.append((index, index + len(block), block))
        start = index + len(block)
    return blocks


def apply_value_edits(
    *,
    circuit: dict[str, Any],
    schematic_path: Path | str,
    output_report: Path | str | None = None,
) -> dict[str, Any]:
    path = Path(schematic_path)
    original = path.read_text(encoding="utf-8")
    expected_values = expected_component_values(circuit)
    blocks = _symbol_instance_blocks(original)

    chunks: list[str] = []
    cursor = 0
    edited_refs: list[dict[str, Any]] = []
    seen_refs: set[str] = set()
    unchanged_refs: list[str] = []

    for start, end, block in blocks:
        chunks.append(original[cursor:start])
        ref = _property_value(block, "Reference")
        if not ref:
            chunks.append(block)
            cursor = end
            continue
        seen_refs.add(ref)
        expected_value = expected_values.get(ref)
        if expected_value is None:
            chunks.append(block)
            cursor = end
            continue
        before_value = _property_value(block, "Value")
        updated, property_changed = _replace_value_property(block, expected_value)
        updated, instance_value_edits = _replace_instance_values(updated, expected_value)
        if property_changed or instance_value_edits:
            edited_refs.append(
                {
                    "ref": ref,
                    "before": before_value,
                    "after": expected_value,
                    "property_changed": property_changed,
                    "instance_value_edit_count": instance_value_edits,
                }
            )
        else:
            unchanged_refs.append(ref)
        chunks.append(updated)
        cursor = end

    chunks.append(original[cursor:])
    updated_text = "".join(chunks)
    changed = updated_text != original
    if changed:
        path.write_text(updated_text, encoding="utf-8")

    missing_refs = sorted(set(expected_values) - seen_refs)
    extra_refs = sorted(seen_refs - set(expected_values))
    report = {
        "schema": VALUE_EDITOR_SCHEMA,
        "stage": "value_editor",
        "ok": not missing_refs,
        "schematic": str(path),
        "kicad_cli_required": False,
        "expected_value_count": len(expected_values),
        "schematic_ref_count": len(seen_refs),
        "changed": changed,
        "edited_component_count": len({item["ref"] for item in edited_refs}),
        "edited_refs": edited_refs,
        "unchanged_ref_count": len(unchanged_refs),
        "missing_refs": missing_refs,
        "extra_refs": extra_refs[:100],
        "extra_refs_truncated": len(extra_refs) > 100,
    }
    if output_report is not None:
        Path(output_report).write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply CircuitIR component values to a generated KiCad schematic.")
    parser.add_argument("schematic", type=Path)
    parser.add_argument("circuit_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    circuit = json.loads(args.circuit_json.read_text(encoding="utf-8"))
    report = apply_value_edits(circuit=circuit, schematic_path=args.schematic, output_report=args.output)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
