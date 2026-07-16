from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
if str(ROOT / "proteus" / "active" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "proteus" / "active" / "src"))

from proteusgen.component_placer import generate_component_placement_project, normalize_component


OUT_DIR = ROOT / "proteus" / "experiments" / "runs" / "beautifier_coordinate_stage_v4_visible_layout_temp_2026_06_22"
ARCHIVE = ROOT / "proteus" / "experiments" / "runs" / "BEAUTIFIER_COORDINATE_STAGE_V4_VISIBLE_LAYOUT_TEMP_2026_06_22.zip"
FIRST_30_DIR = ROOT / "proteus" / "experiments" / "runs" / "component_placer_30_large_complex_v2_2026_06_21"
SECOND_30_MANIFEST = ROOT / "proteus" / "experiments" / "runs" / "component_placer_31_60_r91_safe_v1_2026_06_21" / "manifest.json"
R91_LIMIT = 91


SMALL_CASES = [
    {
        "name": "B00_CONTROL_METADATA_ONLY",
        "payload": {"components": {"SWITCH": 1, "POT-HG": 1}, "control_strategy": "hidden_dummy_control", "layout": {"strategy": "beautify"}},
        "note": "Baseline: dummy SWITCH/POT-HG are selected but not moved far. Check controls remain donor-safe and manifest says controls were skipped by visible grid beautifier.",
    },
    {
        "name": "B01_SWITCH_DUMMY_NO_RUNAWAY",
        "payload": {
            "components": {"SWITCH": 1},
            "control_strategy": "hidden_dummy_control",
            "layout": {"strategy": "beautify"},
        },
        "note": "SWITCH dummy should not be sent to a huge coordinate. Check the visible requested switch keeps normal controls.",
    },
    {
        "name": "B02_POTHG_DUMMY_NO_RUNAWAY",
        "payload": {
            "components": {"POT-HG": 1},
            "control_strategy": "hidden_dummy_control",
            "layout": {"strategy": "beautify"},
        },
        "note": "POT-HG dummy should not be sent to a huge coordinate. Check the visible requested POT-HG remains normal.",
    },
    {
        "name": "B03_CONTROLS_AND_D20_SMALL_RELATIVE",
        "payload": {
            "components": {"SWITCH": 1, "POT-HG": 1, "7segcomanode": 1, "7segcomk": 1, "DIODE": 1},
            "control_strategy": "hidden_dummy_control",
            "hide_display_bridge": True,
            "layout": {"strategy": "beautify", "hide_display_bridge": True},
        },
        "note": "Combined retest. Requested controls/displays/diode stay visible; D20 moves only about 350k, not to a runaway coordinate.",
    },
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _has_display(components: dict[str, int]) -> bool:
    return any(
        normalize_component(family) in {"7SEG-COM-AN-BLUE", "7SEG-COM-CAT-BLUE"}
        for family, count in components.items()
        if count
    )


def _needs_hidden_mode(components: dict[str, int]) -> bool:
    normalized = {normalize_component(family): count for family, count in components.items()}
    return bool(normalized.get("SWITCH") or normalized.get("POT-HG") or _has_display(components))


def _payload_for_components(components: dict[str, int]) -> tuple[dict[str, Any], list[str]]:
    adjusted = dict(components)
    notes: list[str] = []
    if int(adjusted.get("RESISTOR", 0)) > R91_LIMIT:
        notes.append(f"RESISTOR reduced from {adjusted['RESISTOR']} to accepted R91 limit.")
        adjusted["RESISTOR"] = R91_LIMIT

    payload: dict[str, Any] = {
        "schema": "component-placement/v0.1",
        "components": adjusted,
        "layout": {"strategy": "beautify"},
    }
    if _needs_hidden_mode(adjusted):
        payload["control_strategy"] = "hidden_dummy_control"
    if _has_display(adjusted):
        payload["hide_display_bridge"] = True
        payload["layout"]["hide_display_bridge"] = True
        payload["display_bridge_coordinate_mode"] = "display_small_relative"
    return payload, notes


def _first_30_cases() -> list[dict[str, Any]]:
    cases = []
    for request_path in sorted(FIRST_30_DIR.glob("*/request.json")):
        original = json.loads(request_path.read_text(encoding="utf-8"))
        components = {str(k): int(v) for k, v in original.get("components", {}).items()}
        payload, notes = _payload_for_components(components)
        stem = request_path.parent.name
        if notes:
            stem = f"{stem}_R91_SAFE"
        cases.append(
            {
                "name": stem,
                "payload": payload,
                "note": "Replayed from the first 30 large-circuit request pack with V4 visible-layout beautifier rules. " + " ".join(notes),
                "source": str(request_path.relative_to(ROOT)),
            }
        )
    return cases


def _second_30_cases() -> list[dict[str, Any]]:
    manifest = json.loads(SECOND_30_MANIFEST.read_text(encoding="utf-8"))
    cases = []
    for record in manifest.get("records", []):
        if not isinstance(record, dict) or not record.get("request") or not record.get("output"):
            continue
        components = {str(k): int(v) for k, v in record["request"].items()}
        payload, notes = _payload_for_components(components)
        name = Path(str(record["output"])).stem
        if notes:
            name = f"{name}_R91_SAFE"
        cases.append(
            {
                "name": name,
                "payload": payload,
                "note": "Replayed from the accepted R91-safe 31-60 manifest with V4 visible-layout beautifier rules. " + " ".join(notes),
                "source": str(SECOND_30_MANIFEST.relative_to(ROOT)),
            }
        )
    return cases


def _write_case(case_dir: Path, case: dict[str, Any]) -> dict[str, Any]:
    case_dir.mkdir(parents=True, exist_ok=True)
    payload_path = case_dir / "payload.json"
    payload_path.write_text(json.dumps(case["payload"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (case_dir / "WHAT_TO_CHECK.txt").write_text(case["note"] + "\n", encoding="utf-8")
    output_path = case_dir / f"{case['name']}.pdsprj"
    result = generate_component_placement_project(case["payload"], output_path, full_cdb=True)
    return {
        "case": case["name"],
        "source": case.get("source", "inline_small_case"),
        "output": str(output_path.relative_to(ROOT)),
        "manifest": str(result.manifest_path.relative_to(ROOT)),
        "valid": result.valid,
        "errors": [issue.as_dict() for issue in result.errors],
        "request": result.request,
        "hidden_coordinate_mode": case["payload"].get("hidden_coordinate_mode", "none"),
        "hide_display_bridge": bool(case["payload"].get("hide_display_bridge")),
        "note": case["note"],
    }


def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sections = {
        "small_controls": SMALL_CASES,
        "large_rules_01_30": _first_30_cases(),
        "large_rules_31_60": _second_30_cases(),
    }
    results: dict[str, list[dict[str, Any]]] = {}
    for section, cases in sections.items():
        results[section] = []
        for index, case in enumerate(cases):
            safe_name = case["name"].replace(" ", "_").replace("/", "_")
            case_dir = OUT_DIR / section / f"{index + 1:02d}_{safe_name}"
            results[section].append(_write_case(case_dir, case))

    all_results = [row for section_rows in results.values() for row in section_rows]
    summary = {
        "test_id": "BEAUTIFIER_COORDINATE_STAGE_V4_VISIBLE_LAYOUT_STATIC_20260622",
        "case_count": len(all_results),
        "sections": {key: len(value) for key, value in results.items()},
        "cases": results,
        "policy": {
            "uses_actual_generator": "src.proteusgen.component_placer.generate_component_placement_project",
            "full_cdb": True,
            "pruned_cdb_cases": "omitted because the previous CDB-slice coordinate test was rejected",
            "coordinate_mutation_default": "none",
            "hidden_coordinate_mode_for_controls": "none; control dummies are not moved by the rejected runaway coordinate policy",
            "display_bridge_coordinate_mode": "display_small_relative",
            "display_bridge_relative_delta": 350_000,
            "visible_binary_layout": "layout.strategy=beautify translates non-control component packets onto a deterministic grid",
            "resistor_limit": "R91 accepted limit; higher original requests are labelled R91_SAFE variants",
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "README.txt").write_text(
        "\n".join(
            [
                "Beautifier coordinate stage V4 visible-layout test pack",
                "",
                "This evolves the V3 script. It still calls the actual component placer generator.",
                "Open the small_controls cases first, then spot-check large_rules_01_30 and large_rules_31_60.",
                "Every case folder has WHAT_TO_CHECK.txt.",
                "Control dummies are no longer sent to runaway coordinates.",
                "D20 uses display_small_relative, which moves the bridge by about 350,000 coordinate units.",
                "Visible non-control component packets are translated by the shared beautifier grid stage.",
                "Cases marked R91_SAFE intentionally reduce RESISTOR count to the accepted 91 limit.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    summary["archive"] = str(ARCHIVE.relative_to(ROOT))
    summary["archive_sha256"] = sha256(ARCHIVE)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "archive": str(ARCHIVE), "sha256": summary["archive_sha256"], "case_count": len(all_results)}, indent=2))


if __name__ == "__main__":
    main()
