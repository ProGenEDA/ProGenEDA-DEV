# R01_RESISTOR_1X_PARSED_COORDS

## Purpose

Focused resistor-only beautifier probe after V1 passive-family coordinate movement failed with `LXLCORE.dll`.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "RESISTOR": 1
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `R01_RESISTOR_1X_PARSED_COORDS.pdsprj`
- Manifest: `R01_RESISTOR_1X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

One resistor should move to the beautifier grid. Ref text, value text, model text, property text, and symbol body should stay together. No LXLCORE.dll.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
