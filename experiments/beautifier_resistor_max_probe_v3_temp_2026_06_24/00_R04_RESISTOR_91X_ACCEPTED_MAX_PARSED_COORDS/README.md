# R04_RESISTOR_91X_ACCEPTED_MAX_PARSED_COORDS

## Purpose

Focused resistor-only beautifier probe after V1 passive-family coordinate movement failed with `LXLCORE.dll`.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "RESISTOR": 91
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `R04_RESISTOR_91X_ACCEPTED_MAX_PARSED_COORDS.pdsprj`
- Manifest: `R04_RESISTOR_91X_ACCEPTED_MAX_PARSED_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

Accepted-limit resistor stress case: 91 resistors should open on the beautifier grid. Check that Proteus does not throw LXLCORE.dll and that labels/values remain near their resistor bodies.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
