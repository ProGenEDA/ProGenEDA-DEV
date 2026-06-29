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
    attach_component_bidir_terminals_to_project,
)


SOURCE_PAYLOAD = (
    ROOT
    / "experiments"
    / "beautifier_cap_coordinate_probe_v1_temp_2026_06_24"
    / "01_C01_CAP_1X_PARSED_COORDS"
    / "payload.json"
)
OUT_DIR = (
    ROOT
    / "experiments"
    / "terminal_placer_capacitor_attachment_v1_temp_2026_06_29"
)
ARCHIVE = (
    ROOT
    / "experiments"
    / "TERMINAL_PLACER_CAPACITOR_ATTACHMENT_V1_TEMP_2026_06_29.zip"
)
COUNTS = (1, 3, 15)


README = """# Terminal Placer Capacitor Attachment V1

## Purpose

This is the second family-specific terminal-attachment test. It uses the
accepted component placer and beautifier, then the shared terminal placer with
the new `CAP/v1` handler. The JSON comes from the accepted capacitor
beautifier probe and only the count is changed for C01, C03, and C15.

## Why This Is Focused

Older capacitor work proved that ordinary input/output terminal ordering is
fragile when multiple terminal-attached capacitors are synthesized. This V1
pack is narrower:

- bare `CAP` packets come from the current main mega donor;
- bidirectional terminals come from the production terminal templates;
- capacitor pin-link suffix fields are patched from byte-proven CAP offsets;
- donor-proven body-center geometry determines the real left/right pin points;
- short wires are emitted explicitly so attachment is visible and testable.

## V1 Capacitor Structure

For each capacitor V1 emits:

- one left `$TERBIDIR` at 180 degrees;
- one right `$TERBIDIR` at 0 degrees;
- terminal symbols one fixed bidirectional-terminal span away from each pin;
- one short wire from each terminal contact to its real pin;
- capacitor link suffixes patched into the bare mega packet tail.

The binary object order follows the same accepted shared pattern:

```text
header
left terminal records
right terminal records
separator
capacitor + left short wire + right short wire
...
final FF
```

## Test Cases

- C01: one capacitor, two attached terminals.
- C03: three capacitors, six attached terminals.
- C15: fifteen capacitors, thirty attached terminals.

Each case folder contains the reused `payload.json`, bare base project,
terminalized project, placer manifest, terminal plan, and `WHAT_TO_CHECK.txt`.

## Acceptance

For every case:

1. Open the terminalized file, not the `_BASE` file.
2. Confirm every capacitor has one bidirectional terminal on each side.
3. Confirm left arrows face into the body from the left and right arrows from the right.
4. Confirm each terminal reaches its capacitor pin through a visible short wire.
5. Confirm no terminal floats, overlaps, or lands between the plates instead of on a pin.
6. Run simulation/netlist and report any DLL, bad-object, duplicate-reference,
   or unconnected-pin error.

## Result

Static generation passed on 2026-06-29:

- C01/C03/C15 have exactly two terminals and two short wires per capacitor;
- terminal suffixes are patched into the capacitor tail fields;
- local regression tests pass with the shared terminal dispatcher;
- Proteus acceptance is still pending user testing.
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
        case_id = f"C{count:02d}_CAP_{count}X_ATTACHED_BIDIR"
        case_dir = OUT_DIR / case_id
        case_dir.mkdir()
        payload = json.loads(json.dumps(reused_payload))
        payload["donor"] = str(_repo_path(MAIN_MEGA_NO_SOURCE_DONOR))
        payload["components"] = {"CAP": count}
        payload["layout"] = {
            "strategy": "beautify",
            "binary_coordinate_mutation": True,
        }
        base = case_dir / f"{case_id}_BASE.pdsprj"
        output = case_dir / f"{case_id}.pdsprj"
        placement = generate_component_placement_project(payload, base, full_cdb=True)
        if not placement.valid:
            raise RuntimeError(f"{case_id} component placement failed: {placement.errors}")
        terminal_report = attach_component_bidir_terminals_to_project(
            base,
            output,
            placement.selected_groups,
            label_prefix="C",
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
            f"Expected capacitors: {count}\n"
            f"Expected bidirectional terminals: {count * 2}\n"
            f"Expected short wires: {count * 2}\n\n"
            "Check one 180-degree terminal on the left and one 0-degree terminal "
            "on the right of every capacitor. Each terminal must meet its real pin "
            "through a short wire. Then run simulation/netlist.\n",
            encoding="utf-8",
        )
        summary.append(
            {
                "case_id": case_id,
                "capacitor_count": count,
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
