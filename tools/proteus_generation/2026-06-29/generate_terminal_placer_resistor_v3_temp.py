from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from proteusgen.component_placer import (  # noqa: E402
    MAIN_MEGA_NO_SOURCE_DONOR,
    _repo_path,
    generate_component_placement_project,
)
from proteusgen.component_terminal_placer import (  # noqa: E402
    attach_resistor_bidir_terminals_to_project,
)


SOURCE_PAYLOAD = (
    ROOT
    / "experiments"
    / "beautifier_resistor_coordinate_probe_v2_temp_2026_06_24"
    / "01_R01_RESISTOR_1X_PARSED_COORDS"
    / "payload.json"
)
OUT_DIR = (
    ROOT
    / "experiments"
    / "terminal_placer_resistor_attachment_v3_temp_2026_06_29"
)
ARCHIVE = (
    ROOT
    / "experiments"
    / "TERMINAL_PLACER_RESISTOR_ATTACHMENT_V3_TEMP_2026_06_29.zip"
)
COUNTS = (1, 3, 15)


README = """# Terminal Placer Resistor Attachment V3

## Purpose

This is the first family-specific terminal-attachment test. It uses the
accepted component placer and beautifier, then the unified terminal placer.
The JSON comes from the accepted resistor beautifier probe and only the count
is changed for R01, R03, and R15.

## Previous Result

- Value changer V2: user-confirmed working.
- Generic terminal placer V2: rejected because terminals were incorrectly
  positioned and not electrically attached.

V2 used bounding-box edges and no wires. V3 does not use that method.

## V3 Resistor Structure

For each horizontal resistor V3 emits:

- one left `$TERBIDIR` at 180 degrees;
- one right `$TERBIDIR` at 0 degrees;
- terminal symbols at the locked 508,000-unit resistor spacing;
- one donor-derived 254,000-unit short wire on each side;
- resistor pin-link suffixes matching the corresponding terminal suffixes.

The binary object order follows the locked resistor route:

```text
header
left terminal records
right terminal records
separator
resistor + left short wire + right short wire
...
final FF
```

## Test Cases

- R01: one resistor, two attached terminals.
- R03: three resistors, six attached terminals.
- R15: fifteen resistors, thirty attached terminals.

Each case folder contains the reused `payload.json`, bare base project,
terminalized project, placer manifest, terminal plan, and `WHAT_TO_CHECK.txt`.

## Acceptance

For every case:

1. Open the terminalized file, not the `_BASE` file.
2. Confirm every resistor has one terminal on each side.
3. Confirm left arrows face right and right arrows face left toward the body.
4. Confirm there is a short green wire from each terminal contact to its pin.
5. Confirm no terminal floats or overlaps the resistor.
6. Run simulation/netlist and report any DLL, bad-object, duplicate-reference,
   or unconnected-pin error.

## Result

Static generation passed on 2026-06-29:

- R01/R03/R15 have exactly two terminals and two short wires per resistor;
- terminal suffixes match resistor pin-link fields;
- short-wire endpoints match terminal contacts and resistor pins;
- object lengths and final terminators are exact;
- the component-placer test file passes.

Proteus acceptance remains pending user testing.
"""


def clean() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)
    if ARCHIVE.exists():
        ARCHIVE.unlink()


def main() -> None:
    clean()
    reused_payload = json.loads(SOURCE_PAYLOAD.read_text(encoding="utf-8"))
    summary: list[dict[str, object]] = []
    for count in COUNTS:
        case_id = f"R{count:02d}_RESISTOR_{count}X_ATTACHED_BIDIR"
        case_dir = OUT_DIR / case_id
        case_dir.mkdir()
        payload = json.loads(json.dumps(reused_payload))
        payload["donor"] = str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR))
        payload["components"] = {"RESISTOR": count}
        payload["layout"] = {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        }
        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        placement = generate_component_placement_project(payload, base, full_cdb=True)
        if not placement.valid:
            raise RuntimeError(f"{case_id} component placement failed: {placement.errors}")
        terminal_report = attach_resistor_bidir_terminals_to_project(
            base,
            output,
            placement.selected_groups,
            label_prefix="R",
        )
        if not terminal_report["valid"]:
            raise RuntimeError(f"{case_id} terminal attachment failed static validation.")

        (case_dir / "payload.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "base_manifest.json").write_text(
            json.dumps(placement.as_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "terminal_plan.json").write_text(
            json.dumps(terminal_report, indent=2) + "\n",
            encoding="utf-8",
        )
        (case_dir / "WHAT_TO_CHECK.txt").write_text(
            f"{case_id}\n\n"
            f"Open: {output.name}\n"
            f"Expected resistors: {count}\n"
            f"Expected bidirectional terminals: {count * 2}\n"
            f"Expected short wires: {count * 2}\n\n"
            "Check one 180-degree terminal on the left and one 0-degree terminal "
            "on the right of every resistor. Each terminal must meet its resistor "
            "pin through a short wire. Then run simulation/netlist.\n",
            encoding="utf-8",
        )
        summary.append(
            {
                "case_id": case_id,
                "resistor_count": count,
                "terminal_count": terminal_report["terminal_count_added"],
                "wire_count": terminal_report["wire_count_added"],
                "placement_valid": placement.valid,
                "terminal_static_valid": terminal_report["valid"],
                "output": str(output.relative_to(OUT_DIR)),
            }
        )

    (OUT_DIR / "README.md").write_text(README, encoding="utf-8")
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )
    shutil.make_archive(str(ARCHIVE.with_suffix("")), "zip", OUT_DIR)
    print(
        json.dumps(
            {
                "out_dir": str(OUT_DIR),
                "archive": str(ARCHIVE),
                "source_payload": str(SOURCE_PAYLOAD),
                "cases": summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
