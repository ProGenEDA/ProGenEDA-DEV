# MIX03X_ALL_BASE135

## Purpose

Mixed-family stress case requesting 3 of every component family accepted in the 2026-06-24 base135 beautifier tests.
This case uses the normal component placer plus the shared parsed-coordinate beautifier.

## Input

```json
{
  "components": {
    "1N4007": 3,
    "1N4148": 3,
    "1N4733A": 3,
    "1N6000B": 3,
    "2N3904": 3,
    "2N4401": 3,
    "2N7000": 3,
    "40EPS08": 3,
    "BS170": 3,
    "BZX55C5V1": 3,
    "BZX79C5V1": 3,
    "BZY88C": 3,
    "CAP-ELEC": 3,
    "DIODE": 3,
    "FUSE": 3,
    "LED-RED": 3,
    "NMOSFET": 3,
    "NPN": 3,
    "PNP": 3,
    "REALIND": 3
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `MIX03X_ALL_BASE135.pdsprj`
- Manifest: `MIX03X_ALL_BASE135.pdsprj.manifest.json`

## What To Check In Proteus

All listed families should appear together, arranged by the beautifier grid. Requested count per family: 3. Check for open crashes, DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Observation

Pending user Proteus result.
