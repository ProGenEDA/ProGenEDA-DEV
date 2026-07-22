# VS03_15X_COORDS

## Purpose

Focused `VSOURCE` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "VSOURCE": 15
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `VS03_15X_COORDS.pdsprj`
- Manifest: `VS03_15X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

15 `VSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Result

Pending.

## Observation

Pending user Proteus result.
