# R02_RESISTOR_3X_PARSED_COORDS

## Purpose

Focused resistor-only beautifier probe after V1 passive-family coordinate movement failed with `LXLCORE.dll`.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "RESISTOR": 3
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `R02_RESISTOR_3X_PARSED_COORDS.pdsprj`
- Manifest: `R02_RESISTOR_3X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

Three resistors should be separated on one row. This checks repeated parsed-coordinate movement without touching the old fixed offsets.

## User Result

Accepted. User reported this parsed-coordinate resistor case works.

## Codex Observation

Parsed coordinate fields worked for three resistors.
