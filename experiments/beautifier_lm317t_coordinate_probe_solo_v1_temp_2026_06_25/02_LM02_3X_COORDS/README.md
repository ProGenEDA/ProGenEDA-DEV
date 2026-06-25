# LM02_3X_COORDS

## Purpose

Focused `LM317T` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "LM317T": 3
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `LM02_3X_COORDS.pdsprj`
- Manifest: `LM02_3X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

3 `LM317T` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
