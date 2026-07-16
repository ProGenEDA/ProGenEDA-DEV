# P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN

## Purpose

Focused beautifier test for the first passive-family coordinate plans.
The component placer still performs removal-only donor packet selection; this test only changes coordinate movement.

## Input

```json
{
  "components": {
    "CAP": 3,
    "CAP-ELEC": 3,
    "DIODE": 3,
    "REALIND": 3,
    "RESISTOR": 3
  },
  "layout": {
    "strategy": "beautify"
  }
}
```

## Output

- Project: `P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN.pdsprj`
- Manifest: `P06_PASSIVE_MIXED_3X_EACH_FAMILY_PLAN.pdsprj.manifest.json`

## What To Check In Proteus

Mixed passive pack. All 15 components should be visible on the grid with no strange far-away labels, overlaps, or bad object records.

Open the project first. If it opens, inspect visual placement. If applicable, run simulation and record any Proteus errors.

## User Result

Failed. User reported this V1 passive-family coordinate test gave `LXLCORE.dll`.

## Codex Observation

Rejected method. Mixed passive movement used the same unsafe fixed offsets as
the single-family cases. Follow-up must prove one family at a time, starting
with resistor-only parsed-coordinate probes.
