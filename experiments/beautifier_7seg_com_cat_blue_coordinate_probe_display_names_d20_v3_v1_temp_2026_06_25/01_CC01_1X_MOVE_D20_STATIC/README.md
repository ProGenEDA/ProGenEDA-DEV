# CC01_1X_MOVE_D20_STATIC

## Purpose

Isolate `7SEG-COM-CAT-BLUE` row-coordinate mutation while leaving D20 unchanged.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "7SEG-COM-CAT-BLUE": 1
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "display_bridge_coordinate_mode": "display_absolute_100k",
    "hide_display_bridge": false,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `CC01_1X_MOVE_D20_STATIC.pdsprj`
- Manifest: `CC01_1X_MOVE_D20_STATIC.pdsprj.manifest.json`

## What To Check In Proteus

One `7SEG-COM-CAT-BLUE` should move onto the grid and remain intact. D20 should stay in its donor position. This separates display movement from D20 movement.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
