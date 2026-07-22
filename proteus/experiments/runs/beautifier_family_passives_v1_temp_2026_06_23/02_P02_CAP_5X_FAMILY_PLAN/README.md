# P02_CAP_5X_FAMILY_PLAN

## Purpose

Focused beautifier test for the first passive-family coordinate plans.
The component placer still performs removal-only donor packet selection; this test only changes coordinate movement.

## Input

```json
{
  "components": {
    "CAP": 5
  },
  "layout": {
    "strategy": "beautify"
  }
}
```

## Output

- Project: `P02_CAP_5X_FAMILY_PLAN.pdsprj`
- Manifest: `P02_CAP_5X_FAMILY_PLAN.pdsprj.manifest.json`

## What To Check In Proteus

Five capacitors should be visible, separated on the beautifier grid, with labels/values attached and no overlap.

Open the project first. If it opens, inspect visual placement. If applicable, run simulation and record any Proteus errors.

## User Result

Failed. User reported this V1 passive-family coordinate test gave `LXLCORE.dll`.

## Observation

Rejected method. The fixed offset plan touched non-coordinate constants inside
the donor packet instead of parsed capacitor coordinate fields. Follow-up must
use parsed length-prefixed text/body-marker coordinates only.
