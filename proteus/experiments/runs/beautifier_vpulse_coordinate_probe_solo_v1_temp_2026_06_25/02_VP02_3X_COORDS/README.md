# VP02_3X_COORDS

## Purpose

Focused `VPULSE` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "VPULSE": 3
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `VP02_3X_COORDS.pdsprj`
- Manifest: `VP02_3X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

3 `VPULSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
