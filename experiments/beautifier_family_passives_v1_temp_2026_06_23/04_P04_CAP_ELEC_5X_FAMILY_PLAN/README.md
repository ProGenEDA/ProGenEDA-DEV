# P04_CAP_ELEC_5X_FAMILY_PLAN

## Purpose

Focused beautifier test for the first passive-family coordinate plans.
The component placer still performs removal-only donor packet selection; this test only changes coordinate movement.

## Input

```json
{
  "components": {
    "CAP-ELEC": 5
  },
  "layout": {
    "strategy": "beautify"
  }
}
```

## Output

- Project: `P04_CAP_ELEC_5X_FAMILY_PLAN.pdsprj`
- Manifest: `P04_CAP_ELEC_5X_FAMILY_PLAN.pdsprj.manifest.json`

## What To Check In Proteus

Five electrolytic capacitors should be visible and separated. This specifically checks that the old false coordinate near 16,384,000 is no longer moved as part of the packet.

Open the project first. If it opens, inspect visual placement. If applicable, run simulation and record any Proteus errors.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
