# AC03_15X_COORDS

## Purpose

Focused `VSINE` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "VSINE": 15
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `AC03_15X_COORDS.pdsprj`
- Manifest: `AC03_15X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

15 `VSINE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
