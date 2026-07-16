"""Generate the first conservative native IC/display support pack."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

REPO = Path(__file__).resolve().parents[4]
SRC = REPO / "proteus" / "active" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from proteusgen.ic_native import IcNativeGenerationBlocked, generate_ic_native_project_from_payload  # noqa: E402

OUT_ROOT = REPO / "proteus" / "experiments" / "runs" / "ic_native_v1_temp_2026_06_11"
ARCHIVE = REPO / "proteus" / "experiments" / "runs" / "IC_NATIVE_V1_TEMP_2026_06_11.zip"


CASES = [
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T00_7SEG_7447_EXACT_CONTROL",
        "title": "Exact 7447 plus four common-anode 7SEG donor control",
        "donor": "squence/4_7segcomanodewithbiderand4_7447.pdsprj",
        "exact_rezip": True
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T01_74HC160_SINGLE_BIDIR_LABELS",
        "components": [
            {
                "ref": "U1",
                "part": "74HC160",
                "connections": {"CLK": "CLK0", "MR": "RST0", "RCO": "RCO0"}
            }
        ]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T02_4017_SINGLE_BIDIR_LABELS",
        "components": [
            {
                "ref": "U1",
                "part": "4017",
                "connections": {"CLK": "CLK0", "MR": "RST0", "CO": "CO0"}
            }
        ]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T03_REFRESHED_4060_SINGLE_RENDER_CONTROL",
        "components": [{"ref": "U1", "part": "74HC4060"}]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T04_REFRESHED_4520_SINGLE_RENDER_CONTROL",
        "components": [{"ref": "U1", "part": "74HC4520"}]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T05_7SEG_COM_ANODE_SINGLE_BIDIR",
        "components": [{"ref": "D1", "part": "7segcomanode"}]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T06_NE555_SINGLE_BIDIR",
        "components": [{"ref": "U1", "part": "NE555"}]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T07_LM741_SINGLE_BIDIR",
        "components": [{"ref": "U1", "part": "LM741"}]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T08_PAIR_7490_4017_MANUAL_CONTROL",
        "components": [{"ref": "U1", "part": "74HC90"}, {"ref": "U2", "part": "4017"}]
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T09_ANALOG_MISC_MIXED_EXACT_CONTROL",
        "title": "Exact LM741 NPN PNP CAP-ELEC RLC mixed donor control",
        "donor": "New folder (8)/cap_elecap_resistor_ind_lm741_NPN_PNP.pdsprj",
        "exact_rezip": True
    },
    {
        "schema": "ic-native-circuit-ir/v0.1",
        "case_id": "T10_CAP_ELEC_SINGLE_BIDIR",
        "components": [{"ref": "C1", "part": "CAP-ELEC"}]
    }
]


def write_archive() -> str:
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    with ZipFile(ARCHIVE, "w", compression=ZIP_DEFLATED) as zf:
        for file_path in sorted(OUT_ROOT.rglob("*")):
            if not file_path.is_file():
                continue
            info = ZipInfo(file_path.relative_to(OUT_ROOT.parent).as_posix())
            info.date_time = (2026, 6, 11, 0, 0, 0)
            info.compress_type = ZIP_DEFLATED
            info.create_system = 0
            zf.writestr(info, file_path.read_bytes())
    return str(ARCHIVE)


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)
    manifests = []
    for payload in CASES:
        case_dir = OUT_ROOT / payload["case_id"]
        try:
            result = generate_ic_native_project_from_payload(payload, case_dir)
            manifests.append(result.manifest)
        except IcNativeGenerationBlocked as exc:
            manifests.append({"case_id": payload["case_id"], "blocked": True, "report": exc.report.as_dict()})
    summary = {
        "pack": "IC_NATIVE_V1_TEMP_2026_06_11",
        "case_count": len(CASES),
        "static_issue_cases": {
            item["case_id"]: item.get("static_validation_issues", [])
            for item in manifests
            if item.get("static_validation_issues")
        },
        "blocked_cases": [item for item in manifests if item.get("blocked")],
        "archive": write_archive(),
    }
    (OUT_ROOT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_ROOT / "manifests.json").write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if not summary["blocked_cases"] and not summary["static_issue_cases"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
