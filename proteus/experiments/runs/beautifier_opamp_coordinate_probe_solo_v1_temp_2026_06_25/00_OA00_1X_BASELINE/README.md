# OA00_1X_BASELINE

## Purpose

Baseline donor-selected `OPAMP` placement before coordinate mutation.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "OPAMP": 1
  },
  "layout": {
    "binary_coordinate_mutation": false,
    "strategy": "legacy"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `OA00_1X_BASELINE.pdsprj`
- Manifest: `OA00_1X_BASELINE.pdsprj.manifest.json`

## What To Check In Proteus

Baseline control. One `OPAMP` should open in the original donor-selected position.

## User Result

Pending.

## Observation

Pending user Proteus result.
