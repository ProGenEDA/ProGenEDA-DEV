# P01_RESISTOR_5X_FAMILY_PLAN

## Purpose

Focused beautifier test for the first passive-family coordinate plans.
The component placer still performs removal-only donor packet selection; this test only changes coordinate movement.

## Input

```json
{
  "components": {
    "RESISTOR": 5
  },
  "layout": {
    "strategy": "beautify"
  }
}
```

## Output

- Project: `P01_RESISTOR_5X_FAMILY_PLAN.pdsprj`
- Manifest: `P01_RESISTOR_5X_FAMILY_PLAN.pdsprj.manifest.json`

## What To Check In Proteus

Five resistors should be visible, separated on the beautifier grid, with names/values staying near their symbols.

Open the project first. If it opens, inspect visual placement. If applicable, run simulation and record any Proteus errors.

## User Result

Failed. User reported this V1 passive-family coordinate test gave `LXLCORE.dll`.

## Observation

Rejected method. The fixed offset plan touched non-coordinate constants inside
the donor packet instead of the parsed resistor coordinate fields. Follow-up
must use parsed length-prefixed text/body-marker coordinates only.
