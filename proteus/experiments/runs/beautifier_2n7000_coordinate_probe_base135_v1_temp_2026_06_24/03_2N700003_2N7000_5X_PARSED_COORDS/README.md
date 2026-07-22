# 2N700003_2N7000_5X_PARSED_COORDS

## Purpose

Focused `2N7000` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "2N7000": 5
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `2N700003_2N7000_5X_PARSED_COORDS.pdsprj`
- Manifest: `2N700003_2N7000_5X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

5 `2N7000` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Observation

Pending user Proteus result.
