# Baseline C11 Spacing Fix V2

Date: 2026-07-01

## What Was Tested

Generated the 20 baseline practical circuits into a fresh immutable examples
run using the canonical placer:

```text
kicad/pipeline/kicad_component_placer.py
```

This run specifically fixes the reported C11 placement issue where the Micro USB
connector and protection IC were too close in the older `placer_projects`
folder.

## Outcome

Passed KiCad CLI quality:

- 20 schematics checked.
- 20 passed.
- 0 failed.
- `ProgenPlace` count: 0.
- Embedded `(extends ...)` count: 0.

C11 spacing evidence from manifests:

- Old C11 X4/X5 positions: `[87.63, 33.02]`, `[105.41, 33.02]`.
- New C11 X4/X5 positions: `[158.75, 35.56]`, `[30.48, 83.82]`.

## Next

Use this as the current 20-circuit placer baseline.
