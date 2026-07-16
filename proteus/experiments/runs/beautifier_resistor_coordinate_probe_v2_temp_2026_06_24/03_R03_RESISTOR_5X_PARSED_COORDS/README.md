# R03_RESISTOR_5X_PARSED_COORDS

## Purpose

Focused resistor-only beautifier probe after V1 passive-family coordinate movement failed with `LXLCORE.dll`.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "RESISTOR": 5
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `R03_RESISTOR_5X_PARSED_COORDS.pdsprj`
- Manifest: `R03_RESISTOR_5X_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

Five resistors should be separated on the grid, with all visible labels still attached to their matching resistor bodies.

## User Result

Accepted. User reported this parsed-coordinate resistor case works.

## Codex Observation

Parsed coordinate fields worked for five resistors.
