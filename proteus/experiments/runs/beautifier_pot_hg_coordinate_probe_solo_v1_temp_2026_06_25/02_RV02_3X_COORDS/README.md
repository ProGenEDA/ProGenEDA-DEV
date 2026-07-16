# RV02_3X_COORDS

## Purpose

Focused `POT-HG` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "POT-HG": 3
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

- Project: `RV02_3X_COORDS.pdsprj`
- Manifest: `RV02_3X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

3 `POT-HG` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
