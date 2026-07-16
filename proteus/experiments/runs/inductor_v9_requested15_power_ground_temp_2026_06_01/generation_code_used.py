"""Generate the 15 requested inductor topologies with power/ground terminals.

V8 user feedback accepted donor05's sequential six-inductor method, including
the power/ground probe. V9 applies that method to the requested 15 topology
inputs.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
OUT_ROOT = REPO_ROOT / "experiments" / "inductor_v9_requested15_power_ground_temp_2026_06_01"
SOURCE_ROOT = REPO_ROOT / "experiments" / "requested_resistor_networks_oriented_2026_05_30"
V8_PATH = Path(__file__).with_name("generate_inductor_v8_six_donor_temp.py")


def _load_v8() -> Any:
    spec = importlib.util.spec_from_file_location("inductor_v8_temp", V8_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V8 generator from {V8_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _source_inputs() -> list[Path]:
    paths = sorted(SOURCE_ROOT.glob("[0-9][0-9]_*\\input.json"))
    if len(paths) != 15:
        raise RuntimeError(f"Expected 15 requested topology inputs, found {len(paths)}.")
    return paths


def _visible_inductor_from_resistor(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    number = int(digits or "1")
    if number >= 10:
        return "9mH"
    return f"{number}mH"


def _preserve_source_value_shape(source: dict[str, Any], specs: list[Any]) -> list[Any]:
    adjusted: list[Any] = []
    for component, spec in zip(source["components"], specs, strict=True):
        value = _visible_inductor_from_resistor(component.get("value", "1k"))
        adjusted.append(replace(spec, value=value, visible_value=value))
    return adjusted


def main() -> int:
    v8 = _load_v8()
    v8.OUT_ROOT = OUT_ROOT
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    registry = v8.FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")

    base = registry.get("e001_empty").path
    donor05 = registry.get("inductor_05_six_terminal").path
    bridge_donor = registry.get("power_terminal_bridge_donor").path
    templates = v8._load_six_templates(donor05)
    bridge_core = v8.rv9._load_power_bridge_core(v8.read_internal_file(bridge_donor, "ROOT.DSN"), "V0")

    manifests: list[dict[str, Any]] = []
    for source_path in _source_inputs():
        source, specs = v8._convert_source(source_path)
        specs = _preserve_source_value_shape(source, specs)
        chunk, maps, counts = v8._build_sequential_chunk(
            specs,
            templates,
            "extend_from_donor05",
            ground_endpoints=True,
            power_bridge=bridge_core,
        )
        original_case = source_path.parent.name
        case_id = f"IND_V9_{original_case}"
        description = source.get("metadata", {}).get("description", original_case.replace("_", " ").title())
        manifest = v8._write_case(
            case_id=case_id,
            description=f"Power/ground inductor version of requested topology: {description}",
            source=source,
            specs=specs,
            base_project=base,
            donor_project=donor05,
            donor_dsn_project=donor05,
            object_chunk=chunk,
            maps=maps,
            counts=counts,
        )
        manifest["source_input"] = str(source_path.relative_to(REPO_ROOT))
        manifests.append(manifest)

    summary = {
        "case": "INDUCTOR_V9_REQUESTED15_POWER_GROUND_TEMP_2026_06_01",
        "status": "temporary_diagnostic_not_locked",
        "why": "User accepted all V8 donor05 sequential-group diagnostics, including the power/ground probe.",
        "method": "Use donor05 sequential $TERINPUT/$TEROUTPUT-or-$TERGROUND/REALIND/wire groups, donor05 suffix step extension, one donor-derived $TERPOWER->$TEROUTPUT(V0) bridge, and G0 right endpoints as $TERGROUND.",
        "test_order": [item["case_id"] for item in manifests],
        "cases": manifests,
        "notes": [
            "These files use terminal-label topology and short endpoint wires.",
            "Powered inductor endpoints remain ordinary $TERINPUT(V0), connected through the donor-derived V0 power bridge.",
            "Grounded right endpoints are emitted as $TERGROUND(G0).",
            "Stop at the first fatal Proteus error and report the exact case id and error text.",
        ],
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Inductor V9 requested-15 power/ground pack.\n\n"
        "Open in order:\n"
        + "\n".join(f"{index}. {case['case_id']}/{case['case_id']}.pdsprj" for index, case in enumerate(manifests, 1))
        + "\n\nReport open errors, bad-object records, missing labels, overlap, or wrong component count.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")
    shutil.make_archive(str(REPO_ROOT / "experiments" / "INDUCTOR_V9_REQUESTED15_POWER_GROUND_TEMP_2026_06_01"), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "case_count": len(manifests), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
