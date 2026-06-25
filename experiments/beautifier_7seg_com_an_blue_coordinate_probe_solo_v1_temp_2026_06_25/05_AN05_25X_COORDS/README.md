# AN05_25X_COORDS

## Purpose

Focused `7SEG-COM-AN-BLUE` parsed-coordinate beautifier probe.
This case goes through `generate_component_placement_project`; it is not a helper-only binary edit.

## Input

```json
{
  "components": {
    "7SEG-COM-AN-BLUE": 25
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "display_bridge_coordinate_mode": "display_small_relative",
    "hide_display_bridge": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `AN05_25X_COORDS.pdsprj`
- Manifest: `AN05_25X_COORDS.pdsprj.manifest.json`

## What To Check In Proteus

25 `7SEG-COM-AN-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. D20 should move separately and must not count as a requested diode.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
