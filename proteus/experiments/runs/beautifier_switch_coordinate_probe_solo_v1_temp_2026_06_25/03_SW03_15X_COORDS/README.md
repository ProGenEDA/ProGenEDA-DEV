# SW03_15X_COORDS

## Purpose

Focused `SWITCH` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "SWITCH": 15
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "hidden_coordinate_mode": "none",
    "move_visible_controls": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `SW03_15X_COORDS.pdsprj`
- Manifest: `SW03_15X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

15 `SWITCH` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.

## User Result

Pending.

## Observation

Pending user Proteus result.
