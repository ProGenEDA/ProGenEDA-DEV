from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "proteus" / "active" / "src"))

from proteusgen.component_placer import (  # noqa: E402
    MAIN_MEGA_NO_SOURCE_DONOR,
    MAIN_MEGA_SOURCE_DONOR,
    NEW_COMPONENT_MEGA_DONOR,
    _repo_path,
    generate_component_placement_project,
)


OUT_DIR = ROOT / "proteus" / "experiments" / "runs" / "value_changer_probe_v2_safe_values_temp_2026_06_26"
ARCHIVE = ROOT / "proteus" / "experiments" / "runs" / "VALUE_CHANGER_PROBE_V2_SAFE_VALUES_TEMP_2026_06_26.zip"


VALUE_SETS = {
    "RESISTOR": ["1k0", "2k2", "3k3", "4k7", "5k6", "6k8", "8k2", "10k", "12k", "15k", "18k", "22k", "27k", "33k", "47k"],
    "CAP": ["1uF", "2uF", "3uF", "4uF", "5uF", "6uF", "7uF", "8uF", "9uF", "1uF", "2uF", "3uF", "4uF", "5uF", "6uF"],
    "CAP-ELEC": ["1uF", "2uF", "3uF", "4uF", "5uF", "6uF", "7uF", "8uF", "9uF", "1uF", "2uF", "3uF", "4uF", "5uF", "6uF"],
    "REALIND": ["1mH", "2mH", "3mH", "4mH", "5mH", "6mH", "7mH", "8mH", "9mH", "1mH", "2mH", "3mH", "4mH", "5mH", "6mH"],
    "POT-HG": ["1k", "2k", "3k", "4k", "5k", "6k", "7k", "8k", "9k", "1M", "1k", "2k", "3k", "4k", "5k"],
    "VSOURCE": ["1V", "2V", "3V", "4V", "5V", "6V", "7V", "8V", "9V", "1V", "2V", "3V", "4V", "5V", "6V"],
    "CSOURCE": ["1A", "2A", "3A", "4A", "5A", "6A", "7A", "8A", "9A", "1A", "2A", "3A", "4A", "5A", "6A"],
}

DONOR_BY_FAMILY = {
    "RESISTOR": MAIN_MEGA_NO_SOURCE_DONOR,
    "CAP": MAIN_MEGA_NO_SOURCE_DONOR,
    "CAP-ELEC": MAIN_MEGA_NO_SOURCE_DONOR,
    "REALIND": MAIN_MEGA_NO_SOURCE_DONOR,
    "POT-HG": NEW_COMPONENT_MEGA_DONOR,
    "VSOURCE": MAIN_MEGA_SOURCE_DONOR,
    "CSOURCE": MAIN_MEGA_SOURCE_DONOR,
}


def clean() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()


def main() -> None:
    clean()
    summary = []
    for index, (family, values) in enumerate(VALUE_SETS.items(), start=1):
        case_id = f"V{index:02d}_{family.replace('-', '_')}_15X_VALUES"
        case_dir = OUT_DIR / case_id
        case_dir.mkdir()
        payload = {
            "donor": str(_repo_path(DONOR_BY_FAMILY[family])),
            "components": {family: {"count": 15, "values": values}},
            "layout": {"strategy": "beautify"},
        }
        output = case_dir / f"{case_id}.pdsprj"
        result = generate_component_placement_project(payload, output, full_cdb=True)
        (case_dir / "payload.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        (case_dir / "manifest.json").write_text(json.dumps(result.as_dict(), indent=2) + "\n", encoding="utf-8")
        summary.append(
            {
                "case_id": case_id,
                "family": family,
                "output": str(output.relative_to(OUT_DIR)),
                "valid": result.valid,
                "errors": [issue.as_dict() for issue in result.errors],
                "values": values,
            }
        )

    blocked = {
        "VSINE": "No normal visible value token was found in selected packets; property-row mutation needs a focused donor study.",
        "VPULSE": "No normal visible value token was found in selected packets; property-row mutation needs a focused donor study.",
    }
    (OUT_DIR / "blocked_value_families.json").write_text(json.dumps(blocked, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (OUT_DIR / "README.md").write_text(
        "# Value Changer Probe V2\n\n"
        "Each generated project uses the real component placer and the same-length value mutation stage.\n"
        "V2 deliberately avoids compact values like `10u` or `10` that are byte-length compatible but not family-safe.\n"
        "Open each 15x project and inspect whether the visible values changed across the components.\n"
        "The stage also patches matching CDB property rows when the selected row contains the old value token.\n\n"
        "VSINE and VPULSE are intentionally blocked for binary value mutation in this pass because their selected packets do not expose a normal visible value token.\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    print(json.dumps({"out_dir": str(OUT_DIR), "archive": str(ARCHIVE), "cases": len(summary)}, indent=2))


if __name__ == "__main__":
    main()
