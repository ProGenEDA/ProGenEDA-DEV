# BR04_25X_COORDS

## Purpose

Focused `BRIDGE` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "BRIDGE": 25
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `BR04_25X_COORDS.pdsprj`
- Manifest: `BR04_25X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

25 `BRIDGE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Result

Pending.

## Observation

Pending user Proteus result.
