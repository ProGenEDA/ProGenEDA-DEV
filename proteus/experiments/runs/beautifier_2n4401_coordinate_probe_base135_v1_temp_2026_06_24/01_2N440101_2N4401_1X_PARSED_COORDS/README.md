# 2N440101_2N4401_1X_PARSED_COORDS

## Purpose

Focused `2N4401` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "2N4401": 1
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `2N440101_2N4401_1X_PARSED_COORDS.pdsprj`
- Manifest: `2N440101_2N4401_1X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

1 `2N4401` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Observation

Pending user Proteus result.
