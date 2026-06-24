# P05_DIODE_5X_FAMILY_PLAN

## Purpose

Focused beautifier test for the first passive-family coordinate plans.
The component placer still performs removal-only donor packet selection; this test only changes coordinate movement.

## Input

```json
{
  "components": {
    "DIODE": 5
  },
  "layout": {
    "strategy": "beautify"
  }
}
```

## Output

- Project: `P05_DIODE_5X_FAMILY_PLAN.pdsprj`
- Manifest: `P05_DIODE_5X_FAMILY_PLAN.pdsprj.manifest.json`

## What To Check In Proteus

Five diodes should be visible, separated on the beautifier grid, with labels attached and no overlap.

Open the project first. If it opens, inspect visual placement. If applicable, run simulation and record any Proteus errors.

## User Result

Failed. User reported this V1 passive-family coordinate test gave `LXLCORE.dll`.

## Codex Observation

Rejected method. The fixed offset plan touched non-coordinate constants inside
the donor packet instead of parsed diode coordinate fields. Follow-up must use
parsed length-prefixed text/body-marker coordinates only.
