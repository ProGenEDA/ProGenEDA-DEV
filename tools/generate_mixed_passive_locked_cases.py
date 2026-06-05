"""Generate the locked mixed resistor/capacitor acceptance cases."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from proteusgen.mixed_passive import generate_mixed_passive_project_from_payload
from proteusgen.mixed_passive_examples import predefined_mixed_passive_cases


OUT_ROOT = REPO_ROOT / "experiments" / "main_mixed_res_cap_locked_v1_2026_05_31" / "MIXED_LOCKED_6R_21R"


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    cases = []
    for payload in predefined_mixed_passive_cases():
        case_dir = OUT_ROOT / payload["project"]["output_basename"]
        case_dir.mkdir(parents=True)
        result = generate_mixed_passive_project_from_payload(payload, case_dir)
        (case_dir / "input.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        cases.append(result.manifest)
    summary = {
        "case": "MAIN_MIXED_RES_CAP_LOCKED_V1_2026_05_31",
        "status": "locked_current_scope",
        "method": "main mixed passive generator: odd components resistor, even components capacitor, locked power bridge and ground endpoints",
        "test_order": [case["output_basename"] for case in cases],
        "cases": cases,
    }
    (OUT_ROOT / "summary_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_ROOT / "README_TEST_ORDER.txt").write_text(
        "Main mixed resistor/capacitor locked V1 outputs.\n\n"
        "Open in order:\n\n"
        + "\n".join(f"{idx}. {case['output_basename']}/{case['output_basename']}.pdsprj" for idx, case in enumerate(cases, 1))
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"out_root": str(OUT_ROOT), "test_order": summary["test_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
