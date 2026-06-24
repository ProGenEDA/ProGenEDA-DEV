# NMOSFE00_NMOSFET_1X_BASELINE_NO_BEAUTIFY

## Purpose

Baseline donor-selected `NMOSFET` placement before coordinate mutation.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "NMOSFET": 1
  },
  "layout": {
    "binary_coordinate_mutation": false,
    "strategy": "legacy"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `NMOSFE00_NMOSFET_1X_BASELINE_NO_BEAUTIFY.pdsprj`
- Manifest: `NMOSFE00_NMOSFET_1X_BASELINE_NO_BEAUTIFY.pdsprj.manifest.json`

## What To Check In Proteus

Baseline control. One `NMOSFET` should open in the original donor-selected position.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
