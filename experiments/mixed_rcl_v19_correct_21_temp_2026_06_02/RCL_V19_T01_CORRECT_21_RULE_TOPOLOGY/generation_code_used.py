"""Generate a corrected 21-component mixed R/C/L topology test.

V18 T02 had 21 components but used seven independent V0-to-G0 RCL branches.
That does not follow the accepted 21-circuit rule from the earlier resistor and
mixed RC tests. This V19 diagnostic emits only the corrected 21 circuit:

* two seven-component series strings from V0 to M0
* one seven-component series string from M0 to G0
* balanced component mix: 7 resistors, 7 capacitors, 7 inductors

The object records still use the accepted V17/V18 full/removal unit method.
Do not promote until the user confirms this 21 circuit in Proteus.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from proteusgen.templates import FixtureRegistry

OUT_ROOT = REPO_ROOT / "experiments" / "mixed_rcl_v19_correct_21_temp_2026_06_02"
ARCHIVE_BASE = REPO_ROOT / "experiments" / "MIXED_RCL_V19_CORRECT_21_TEMP_2026_06_02"
V18_PATH = REPO_ROOT / "tools" / "proteus_generation" / "2026-06-02" / "generate_mixed_rcl_v18_final_topology_temp.py"

CASE_ID = "RCL_V19_T01_CORRECT_21_RULE_TOPOLOGY"


def _load_v18() -> Any:
    spec = importlib.util.spec_from_file_location("mixed_rcl_v18_for_v19", V18_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import V18 helper module from {V18_PATH}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _required_file_check(project_path: Path) -> list[str]:
    required = {"PROJECT.XML", "ROOT.DSN", "ROOT.CDB", "SCRIPTS/PWRRAILS.DAT"}
    with zipfile.ZipFile(project_path) as zf:
        names = set(zf.namelist())
    return sorted(required - names)


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    v18 = _load_v18()
    v18.OUT_ROOT = OUT_ROOT

    registry = FixtureRegistry.load()
    failed = registry.verify_all()
    if failed:
        raise RuntimeError(f"Fixture hash failure: {', '.join(failed)}")

    base = registry.get("e001_empty").path
    donor = registry.get("rcl_4x_t07_unit_donor").path
    templates = v18.v16._load_rcl_unit_templates(donor)

    groups = [
        # Row 1: seven components from V0 to M0.
        v18.G("RCL", "V0", "D1"),
        v18.G("RC", "D1", "D2"),
        v18.G("LC", "D2", "M0"),
        # Row 2: another seven-component string from V0 to M0.
        v18.G("RCL", "V0", "E1"),
        v18.G("RL", "E1", "E2"),
        v18.G("RC", "E2", "M0"),
        # Row 3: seven components from M0 to G0.
        v18.G("RCL", "M0", "F1"),
        v18.G("LC", "F1", "F2"),
        v18.G("RL", "F2", "G0"),
    ]
    circuit_rows = [
        {
            "row": 1,
            "rule": "seven components in series from V0 to M0",
            "group_modes": ["RCL", "RC", "LC"],
            "nodes": ["V0", "D1", "D2", "M0"],
            "unit_indices": [1, 2, 3],
        },
        {
            "row": 2,
            "rule": "seven components in series from V0 to M0",
            "group_modes": ["RCL", "RL", "RC"],
            "nodes": ["V0", "E1", "E2", "M0"],
            "unit_indices": [4, 5, 6],
        },
        {
            "row": 3,
            "rule": "seven components in series from M0 to G0",
            "group_modes": ["RCL", "LC", "RL"],
            "nodes": ["M0", "F1", "F2", "G0"],
            "unit_indices": [7, 8, 9],
        },
    ]

    manifest = v18._write_case(
        case_id=CASE_ID,
        description="Corrected 21-component rule topology: two V0-to-M0 seven-component strings feeding one M0-to-G0 seven-component string.",
        base_project=base,
        donor_project=donor,
        templates=templates,
        groups=groups,
    )

    case_dir = OUT_ROOT / CASE_ID
    manifest_path = case_dir / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_data.update(
        {
            "status": "temporary_mixed_rcl_v19_correct_21_not_locked",
            "source_feedback": "User reported V18 T02 was wrong because 21 components must follow the accepted 21-circuit topology, not just contain 21 components.",
            "correction_from_v18": "V18 T02 emitted seven separate V0-to-G0 RCL branches. V19 emits two seven-component V0-to-M0 series strings and one seven-component M0-to-G0 series string.",
            "circuit_rule": "21-circuit rule: branch A V0->M0 has 7 components, branch B V0->M0 has 7 components, branch C M0->G0 has 7 components.",
            "circuit_rows": circuit_rows,
            "coordinate_model": "Unit blocks 1-3, 4-6, and 7-9 occupy three separate visual rows; each row has three accepted V17 group blocks with safe donor-derived spacing.",
            "expected_counts": {"RESISTOR": 7, "CAPACITOR": 7, "INDUCTOR": 7},
        }
    )
    manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    input_path = case_dir / "input.json"
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    payload["schema_version"] = "mixed-rcl-temp/v19-correct-21"
    payload["generator_target"] = "proteus-8.13-mixed-rcl-correct-21-testing"
    payload["metadata"]["circuit_rule"] = manifest_data["circuit_rule"]
    payload["metadata"]["circuit_rows"] = circuit_rows
    payload["metadata"]["correction_from_v18"] = manifest_data["correction_from_v18"]
    input_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    (case_dir / "README_TEST_FIRST.txt").write_text(
        f"{CASE_ID}\n\n"
        "Corrected 21-component topology for manual Proteus confirmation.\n\n"
        "Circuit rule:\n"
        "1. Row 1: V0 -> seven mixed components -> M0\n"
        "2. Row 2: V0 -> seven mixed components -> M0\n"
        "3. Row 3: M0 -> seven mixed components -> G0\n\n"
        "Counts: 7R / 7C / 7L\n"
        f"Groups: {', '.join(manifest_data['group_modes'])}\n"
        f"Static validation issues: {manifest_data['static_validation_issues']}\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), case_dir / "generation_code_used.py")

    project_path = case_dir / f"{CASE_ID}.pdsprj"
    missing_required = _required_file_check(project_path)
    summary = {
        "batch_id": "MIXED_RCL_V19_CORRECT_21_STATIC_20260602",
        "status": "static_generated_awaiting_user_21_confirmation",
        "source_feedback": manifest_data["source_feedback"],
        "method": "Use accepted V17 subgroup-removal groups but arrange them into the accepted 21-circuit topology.",
        "test_order": [CASE_ID],
        "archive_expected": str(ARCHIVE_BASE.with_suffix(".zip")),
        "cases": [
            {
                "case_id": CASE_ID,
                "component_count": manifest_data["component_count"],
                "resistor_count": manifest_data["resistor_count"],
                "capacitor_count": manifest_data["capacitor_count"],
                "inductor_count": manifest_data["inductor_count"],
                "group_modes": manifest_data["group_modes"],
                "circuit_rows": circuit_rows,
                "static_validation_issues": manifest_data["static_validation_issues"],
                "missing_required_internal_files": missing_required,
            }
        ],
    }
    (OUT_ROOT / "batch_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Mixed R/C/L V19 corrected 21-circuit test pack.\n\n"
        "Open and run netlist/simulation:\n"
        f"1. {CASE_ID}/{CASE_ID}.pdsprj\n\n"
        "This is only the corrected 21 case. Do not lock the full R/C/L generator until the user confirms this case.\n",
        encoding="utf-8",
    )
    shutil.copy(Path(__file__), OUT_ROOT / "generation_code_used.py")

    archive = shutil.make_archive(str(ARCHIVE_BASE), "zip", OUT_ROOT)
    print(json.dumps({"out_root": str(OUT_ROOT), "archive": archive, "case_count": 1, "test_order": [CASE_ID]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
