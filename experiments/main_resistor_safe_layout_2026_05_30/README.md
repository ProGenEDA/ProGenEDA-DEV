# Main Resistor Safe Layout Batch - 2026-05-30

Purpose: respond to the user-reported overlap and VGDVC.dll failures in the most recent generated 15 resistor circuits.

## Changes Under Test

- `.pdsprj` desktop opening was configured for Proteus 8.13 via Wine.
- `/mnt/MainExt/arch/run-proteus8.sh` now converts Unix paths and `file://` URIs to Wine paths before launching `/mnt/MainExt/arch/Proteus 8 Professional/BIN/PDS.EXE`.
- Production resistor generation stretches dense manual component positions to the safe V9 grid.
- Production resistor generation skips `layout.visual_wires` until a Proteus-created standalone wire donor proves a VGDVC-safe record format.

## Batch

Output root:

```text
experiments/main_resistor_safe_layout_2026_05_30/REQUESTED_15_SAFE_LAYOUT
```

Inputs were the existing oriented requested-resistor JSON files from:

```text
experiments/requested_resistor_networks_oriented_2026_05_30
```

Summary:

```text
15/15 generated with zero static validation issues
visual_wire_count = 0 for all cases
visual_wire_skipped_count > 0 for cases that requested experimental bus/junction wires
layout_adjusted_count > 0 for dense manual layouts
```

## Proteus Open Smoke

Command shape:

```bash
timeout 10s wine "/mnt/MainExt/arch/Proteus 8 Professional/BIN/PDS.EXE" "$(winepath -w "$project")"
```

Result:

```text
15/15 projects stayed running until the guard timeout
0/15 stderr logs contained VGDVC
0/15 early exits
```

Detailed log:

```text
experiments/main_resistor_safe_layout_2026_05_30/REQUESTED_15_SAFE_LAYOUT/proteus_open_smoke.jsonl
```

## Python Tests

```text
PYTHONPATH=src python -m unittest discover -s tests -v
Ran 30 tests
OK
```

## Remaining Acceptance Gap

This is a guarded loader/open smoke plus static validation pass. Manual visual confirmation and save-as/reopen comparison are still needed before calling the 15 safe-layout projects fully accepted.
