# Baseline C11 Spacing Fix V1

Date: 2026-07-01

## What Was Tested

Generated the 20 baseline practical circuits into a fresh immutable examples
run after the first C11 spacing adjustment.

## Outcome

Passed KiCad CLI quality:

- 20 schematics checked.
- 20 passed.
- 0 failed.

## Why Superseded

The later stress run still exposed pin-overlap failures in larger schematics, so
the placer spacing heuristic was widened again. This folder is superseded by:

```text
kicad/examples/placer_run_2026_07_01_baseline_c11_spacing_fix_v2
```

## Next

Use the v2 folder as current baseline evidence.
