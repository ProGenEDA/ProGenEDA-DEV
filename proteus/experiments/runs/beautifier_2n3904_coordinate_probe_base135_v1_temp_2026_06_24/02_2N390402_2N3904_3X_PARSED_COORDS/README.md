# 2N390402_2N3904_3X_PARSED_COORDS

## Purpose

Focused `2N3904` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "2N3904": 3
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `2N390402_2N3904_3X_PARSED_COORDS.pdsprj`
- Manifest: `2N390402_2N3904_3X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

3 `2N3904` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
