# VS00_1X_BASELINE

## Purpose

Baseline donor-selected `VSOURCE` placement before coordinate mutation.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "VSOURCE": 1
  },
  "layout": {
    "binary_coordinate_mutation": false,
    "strategy": "legacy"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `VS00_1X_BASELINE.pdsprj`
- Manifest: `VS00_1X_BASELINE.pdsprj.manifest.json`

## What To Check In Proteus

Baseline control. One `VSOURCE` should open in the original donor-selected position.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
