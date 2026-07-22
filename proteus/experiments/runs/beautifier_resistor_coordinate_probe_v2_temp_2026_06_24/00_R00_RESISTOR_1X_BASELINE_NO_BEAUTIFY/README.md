# R00_RESISTOR_1X_BASELINE_NO_BEAUTIFY

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
    "binary_coordinate_mutation": false,
    "strategy": "legacy"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `R00_RESISTOR_1X_BASELINE_NO_BEAUTIFY.pdsprj`
- Manifest: `R00_RESISTOR_1X_BASELINE_NO_BEAUTIFY.pdsprj.manifest.json`

## What To Check In Proteus

Baseline control. One resistor should open in the original donor-selected position. This proves the placer/donor path is still sound before coordinate mutation.

## User Result

Accepted. User reported this baseline works.

## Observation

Baseline donor-selected resistor path is sound.
