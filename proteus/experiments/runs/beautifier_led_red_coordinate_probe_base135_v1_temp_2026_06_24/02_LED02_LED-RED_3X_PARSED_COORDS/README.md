# LED02_LED-RED_3X_PARSED_COORDS

## Purpose

Focused `LED-RED` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "LED-RED": 3
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `LED02_LED-RED_3X_PARSED_COORDS.pdsprj`
- Manifest: `LED02_LED-RED_3X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

3 `LED-RED` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
