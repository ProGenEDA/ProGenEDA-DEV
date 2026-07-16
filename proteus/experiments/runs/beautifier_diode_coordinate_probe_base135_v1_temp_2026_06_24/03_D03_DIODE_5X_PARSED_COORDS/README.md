# D03_DIODE_5X_PARSED_COORDS

## Purpose

Focused `DIODE` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "DIODE": 5
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `D03_DIODE_5X_PARSED_COORDS.pdsprj`
- Manifest: `D03_DIODE_5X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

5 `DIODE` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
