# AN04_15X_COORDS

## Purpose

Focused `7SEG-COM-AN-BLUE` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "7SEG-COM-AN-BLUE": 15
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "display_bridge_coordinate_mode": "display_absolute_100k",
    "hide_display_bridge": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `AN04_15X_COORDS.pdsprj`
- Manifest: `AN04_15X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

15 `7SEG-COM-AN-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. Proteus-generated Dxxx names should stay attached to their displays. D20 should be in the 100000/100000 infrastructure region and must not count as a requested diode.

## User Result

Pending.

## Observation

Pending user Proteus result.
