# C03_CAP_5X_PARSED_COORDS

## Purpose

Focused `CAP` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "CAP": 5
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `C03_CAP_5X_PARSED_COORDS.pdsprj`
- Manifest: `C03_CAP_5X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

5 `CAP` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Result

Accepted. User reported this CAP parsed-coordinate case works.

## Codex Observation

Parsed coordinate fields worked for five CAP components.
