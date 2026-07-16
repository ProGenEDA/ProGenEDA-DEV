"""Generate temporary inductor versions of the 15 requested resistor networks.

This pack stays experimental. It uses the corrected V6 placement/suffix code and
the best current donor04-order guess for real V0/G0 terminal records.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
OUT_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "inductor_v7_requested15_temp_2026_06_01"
SOURCE_ROOT = REPO_ROOT / "proteus" / "experiments" / "runs" / "requested_resistor_networks_oriented_2026_05_30"
V6_PATH = Path(__file__).with_name("generate_inductor_v6_6_21_temp.py")


def _load_v6() -> Any:
    spec = importlib.util.spec_from_file_location("inductor_v6_temp", V6_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V6 generator from {V6_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _source_inputs() -> list[Path]:
    paths = sorted(SOURCE_ROOT.glob("[0-9][0-9]_*\\input.json"))
    if len(paths) != 15:
        raise RuntimeError(f"Expected 15 requested topology inputs, found {len(paths)}.")
    return paths


def _visible_inductor_from_resistor(value: str, target_len: int) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    number = int(digits or "1")
    if target_len == 4:
        if number >= 10:
            return "10mH"
        return f"{number}0uH"
    if number >= 10:
        return "9mH"
    return f"{number}mH"


def _preserve_source_value_shape(source: dict[str, Any], specs: list[Any]) -> list[Any]:
    adjusted: list[Any] = []
    for component, spec in zip(source["components"], specs, strict=True):
        visible_value = _visible_inductor_from_resistor(component.get("value", "1k"), len(spec.visible_value))
        adjusted.append(replace(spec, value=visible_value, visible_value=visible_value))
    return adjusted


def main() -> int:
    v6 = _load_v6()
    v6.OUT_ROOT = OUT_ROOT
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = v6.FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")
    base = registry.get("e001_empty").path
    donor03 = registry.get("inductor_03_three_terminal").path
    donor04 = registry.get("inductor_04_power_ground").path
    templates = v6._load_three_templates(donor03)
    donor04_bridge = v6._load_donor04_bridge(donor04)

    manifests: list[dict[str, Any]] = []
    for source_path in _source_inputs():
        source, specs = v6._convert_source(source_path)
        specs = _preserve_source_value_shape(source, specs)
        chunk, maps, counts = v6._build_power_chunk(
            specs,
            templates,
            donor04_bridge,
            "extended",
            bridge_order="after_first_left_wire",
        )
        original_case = source_path.parent.name
        case_id = f"IND_V7_{original_case}"
        description = source.get("metadata", {}).get("description", original_case.replace("_", " ").title())
        manifest = v6._write_case(
            case_id=case_id,
            description=f"Inductor version of requested topology: {description}",
            source=source,
            specs=specs,
            base_project=base,
            donor_project=donor03,
            donor_dsn_project=donor04,
            object_chunk=chunk,
            maps=maps,
            counts=counts,
        )
        manifest["source_input"] = str(source_path.relative_to(REPO_ROOT))
        manifests.append(manifest)

    summary = {
        "case": "INDUCTOR_V7_REQUESTED15_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "why": "Covers the 15 user-requested network shapes with inductors after V6 6/21 scale diagnostics.",
        "method": "V6 extended suffixes, corrected no-overlap placement, donor04 bridge inserted after first left wire for V0/G0.",
        "test_after": [
            "IND_V6_T05_6L_POWER_GROUND_DONOR04_AFTER_FIRST_LEFT_WIRE",
            "IND_V6_T06_21L_POWER_GROUND_DONOR04_AFTER_FIRST_LEFT_WIRE",
        ],
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "These files intentionally represent topology with terminal labels and short endpoint wires.",
            "Physical triangle/star/bridge drawing is approximate; topology is carried by repeated net labels.",
            "Stop at the first fatal Proteus error and report exact text plus the case id.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V7 requested-15 topology pack.\n\n"
        "Test this only after V6 T05 and T06 open correctly.\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport open errors, bad-object records, missing labels, overlap, or wrong component count.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "proteus" / "experiments" / "runs" / "INDUCTOR_V7_REQUESTED15_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "case_count": len(manifests), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
