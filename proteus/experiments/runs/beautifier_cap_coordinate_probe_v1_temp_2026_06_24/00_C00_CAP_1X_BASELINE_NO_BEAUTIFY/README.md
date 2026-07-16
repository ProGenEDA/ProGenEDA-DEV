# C00_CAP_1X_BASELINE_NO_BEAUTIFY

## Purpose

Baseline donor-selected `CAP` placement before coordinate mutation.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "CAP": 1
  },
  "layout": {
    "binary_coordinate_mutation": false,
    "strategy": "legacy"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `C00_CAP_1X_BASELINE_NO_BEAUTIFY.pdsprj`
- Manifest: `C00_CAP_1X_BASELINE_NO_BEAUTIFY.pdsprj.manifest.json`

## What To Check In Proteus

Baseline control. One `CAP` should open in the original donor-selected position.

## User Result

Accepted. User reported this CAP baseline works.

## Codex Observation

Baseline donor-selected CAP path is sound.
