# MIX15X_ALL_BASE135

## Purpose

Mixed-family stress case requesting 15 of every component family accepted in the 2026-06-24 base135 beautifier tests.
This case uses the normal component placer plus the shared parsed-coordinate beautifier.

## Input

```json
{
  "components": {
    "1N4007": 15,
    "1N4148": 15,
    "1N4733A": 15,
    "1N6000B": 15,
    "2N3904": 15,
    "2N4401": 15,
    "2N7000": 15,
    "40EPS08": 15,
    "BS170": 15,
    "BZX55C5V1": 15,
    "BZX79C5V1": 15,
    "BZY88C": 15,
    "CAP-ELEC": 15,
    "DIODE": 15,
    "FUSE": 15,
    "LED-RED": 15,
    "NMOSFET": 15,
    "NPN": 15,
    "PNP": 15,
    "REALIND": 15
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `MIX15X_ALL_BASE135.pdsprj`
- Manifest: `MIX15X_ALL_BASE135.pdsprj.manifest.json`

## What To Check In Proteus

All listed families should appear together, arranged by the beautifier grid. Requested count per family: 15. Check for open crashes, DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Observation

Pending user Proteus result.
