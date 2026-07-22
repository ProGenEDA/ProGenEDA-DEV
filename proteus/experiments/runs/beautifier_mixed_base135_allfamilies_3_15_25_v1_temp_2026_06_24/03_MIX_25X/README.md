# MIX25X_ALL_BASE135

## Purpose

Mixed-family stress case requesting 25 of every component family accepted in the 2026-06-24 base135 beautifier tests.
This case uses the normal component placer plus the shared parsed-coordinate beautifier.

## Input

```json
{
  "components": {
    "1N4007": 25,
    "1N4148": 25,
    "1N4733A": 25,
    "1N6000B": 25,
    "2N3904": 25,
    "2N4401": 25,
    "2N7000": 25,
    "40EPS08": 25,
    "BS170": 25,
    "BZX55C5V1": 25,
    "BZX79C5V1": 25,
    "BZY88C": 25,
    "CAP-ELEC": 25,
    "DIODE": 25,
    "FUSE": 25,
    "LED-RED": 25,
    "NMOSFET": 25,
    "NPN": 25,
    "PNP": 25,
    "REALIND": 25
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `MIX25X_ALL_BASE135.pdsprj`
- Manifest: `MIX25X_ALL_BASE135.pdsprj.manifest.json`

## What To Check In Proteus

All listed families should appear together, arranged by the beautifier grid. Requested count per family: 25. Check for open crashes, DLL errors, bad object records, and detached labels/values.

## User Result

Pending.

## Observation

Pending user Proteus result.
