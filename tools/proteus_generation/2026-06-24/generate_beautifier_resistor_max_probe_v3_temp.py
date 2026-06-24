from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import (
    MAIN_MEGA_NO_SOURCE_DONOR,
    _generation_markers,
    _inspect_donor_counts_for_selection,
    generate_component_placement_project,
)


OUT_DIR = ROOT / "experiments" / "beautifier_resistor_max_probe_v3_temp_2026_06_24"
ARCHIVE = ROOT / "experiments" / "BEAUTIFIER_RESISTOR_MAX_PROBE_V3_TEMP_2026_06_24.zip"
V2_SCRIPT = ROOT / "tools" / "proteus_generation" / "2026-06-24" / "generate_beautifier_resistor_coordinate_probe_v2_temp.py"
ACCEPTED_RESISTOR_LIMIT = 91


def load_v2_helpers() -> Any:
    spec = importlib.util.spec_from_file_location("beautifier_resistor_coordinate_probe_v2", V2_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load V2 helper script from {V2_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_root_readme(
    records: list[dict[str, Any]],
    accepted_count: int,
    donor_inventory_count: int,
    byte_probe: dict[str, Any],
) -> None:
    resistor_pairs = byte_probe["RESISTOR"]["parsed_coordinate_pairs"]
    lines = [
        "# Beautifier Resistor Max Probe V3",
        "",
        "Generated on 2026-06-24.",
        "",
        "`BEAUTIFIER_RESISTOR_COORDINATE_PROBE_V2_TEMP_2026_06_24` was accepted by user Proteus testing.",
        "This pack uses the same parsed-coordinate movement path for the accepted R91 resistor ceiling.",
        "",
        "`690` is only the raw resistor packet inventory found in the current main mega no-source donor.",
        "It is not treated as the safe generation limit because earlier large-rule testing recorded `R91` as accepted.",
        "",
        "## Max Count",
        "",
        f"- Donor: `{MAIN_MEGA_NO_SOURCE_DONOR}`",
        f"- Accepted `RESISTOR` test count: `{accepted_count}`",
        f"- Donor inventory count, not accepted limit: `{donor_inventory_count}`",
        "",
        "## Parsed Resistor Coordinates Under Test",
        "",
    ]
    for pair in resistor_pairs:
        lines.append(
            f"- `{pair['x_offset']}/{pair['y_offset']}` -> "
            f"({pair['x_value']}, {pair['y_value']}), `{pair['reason']}`"
        )
    lines.extend(["", "## Test File", ""])
    for record in records:
        lines.append(f"- `{record['case_folder']}/{record['output_name']}`: {record['what_to_check']}")
    lines.extend(
        [
            "",
            "## User Results",
            "",
            "Pending.",
            "",
            "## What Success Means",
            "",
            "If this opens without `LXLCORE.dll` and the resistor labels/values stay with their bodies,",
            "`RESISTOR` coordinate beautification is accepted at the R91 ceiling and we can move to `CAP` next.",
            "",
        ]
    )
    (OUT_DIR / "README.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    helpers = load_v2_helpers()
    counts = _inspect_donor_counts_for_selection(ROOT / MAIN_MEGA_NO_SOURCE_DONOR, _generation_markers())
    donor_inventory_count = int(counts.get("RESISTOR", 0))
    if donor_inventory_count <= 0:
        raise RuntimeError("Main mega no-source donor does not expose any RESISTOR packets.")
    if donor_inventory_count < ACCEPTED_RESISTOR_LIMIT:
        raise RuntimeError(
            f"Accepted R91 resistor test requested {ACCEPTED_RESISTOR_LIMIT}, "
            f"but donor only exposes {donor_inventory_count} RESISTOR packets."
        )

    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    byte_probe = helpers.build_byte_probe()
    (OUT_DIR / "byte_probe.json").write_text(json.dumps(byte_probe, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    case = {
        "name": f"R04_RESISTOR_{ACCEPTED_RESISTOR_LIMIT}X_ACCEPTED_MAX_PARSED_COORDS",
        "components": {"RESISTOR": ACCEPTED_RESISTOR_LIMIT},
        "layout": {"strategy": "beautify", "binary_coordinate_mutation": True},
        "what_to_check": (
            f"Accepted-limit resistor stress case: {ACCEPTED_RESISTOR_LIMIT} resistors should open on the beautifier grid. "
            "Check that Proteus does not throw LXLCORE.dll and that labels/values remain near their resistor bodies."
        ),
    }
    case_dir = OUT_DIR / f"00_{case['name']}"
    case_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "component-placement/v0.1",
        "components": case["components"],
        "layout": case["layout"],
    }
    (case_dir / "payload.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    output_path = case_dir / f"{case['name']}.pdsprj"
    result = generate_component_placement_project(
        payload,
        output_path,
        donor_path=MAIN_MEGA_NO_SOURCE_DONOR,
        full_cdb=True,
    )
    helpers.write_case_note(case_dir, case, output_path, result.manifest_path)
    record = {
        "case": case["name"],
        "case_folder": case_dir.name,
        "components": case["components"],
        "layout": case["layout"],
        "output": str(output_path.relative_to(ROOT)),
        "output_name": output_path.name,
        "manifest": str(result.manifest_path.relative_to(ROOT)),
        "valid": result.valid,
        "errors": [issue.as_dict() for issue in result.errors],
        "what_to_check": case["what_to_check"],
    }

    summary = {
        "test_id": "BEAUTIFIER_RESISTOR_MAX_PROBE_V3_TEMP_2026_06_24",
        "case_count": 1,
        "accepted_resistor_limit": ACCEPTED_RESISTOR_LIMIT,
        "donor_inventory_resistor_count": donor_inventory_count,
        "records": [record],
        "byte_probe": "byte_probe.json",
        "policy": {
            "actual_generator": "proteusgen.component_placer.generate_component_placement_project",
            "derived_from_script": str(V2_SCRIPT.relative_to(ROOT)),
            "explicit_donor": str(MAIN_MEGA_NO_SOURCE_DONOR),
            "focus": "accepted R91 resistor parsed coordinate fields",
            "full_cdb": True,
            "previous_accepted_pack": "BEAUTIFIER_RESISTOR_COORDINATE_PROBE_V2_TEMP_2026_06_24",
            "reason_not_690": "690 is raw donor inventory; docs/active_working_memory and V3 large-rule summary record R91 as the accepted resistor-heavy ceiling.",
        },
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_root_readme([record], ACCEPTED_RESISTOR_LIMIT, donor_inventory_count, byte_probe)
    if ARCHIVE.exists():
        ARCHIVE.unlink()
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    summary["archive"] = str(ARCHIVE.relative_to(ROOT))
    summary["archive_sha256"] = sha256(ARCHIVE)
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "accepted_resistor_limit": ACCEPTED_RESISTOR_LIMIT,
                "donor_inventory_resistor_count": donor_inventory_count,
                "out_dir": str(OUT_DIR),
                "archive": str(ARCHIVE),
                "sha256": summary["archive_sha256"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
