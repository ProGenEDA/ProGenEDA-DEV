# NIC25X_ALL_NON_IC

## Purpose

Non-IC stress case requesting 25 of every non-IC component family currently exercised by the component placer.
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
    "7SEG-COM-AN-BLUE": 25,
    "7SEG-COM-CAT-BLUE": 25,
    "BRIDGE": 25,
    "BS170": 25,
    "BZX55C5V1": 25,
    "BZX79C5V1": 25,
    "BZY88C": 25,
    "CAP": 25,
    "CAP-ELEC": 25,
    "CSOURCE": 25,
    "DIODE": 25,
    "FUSE": 25,
    "LED-RED": 25,
    "LM317T": 25,
    "NMOSFET": 25,
    "NPN": 25,
    "OPAMP": 25,
    "PNP": 25,
    "POT-HG": 25,
    "REALIND": 25,
    "RESISTOR": 25,
    "SWITCH": 25,
    "TRAN-2P2S": 25,
    "VPULSE": 25,
    "VSINE": 25,
    "VSOURCE": 25
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "display_bridge_coordinate_mode": "display_small_relative",
    "hidden_coordinate_mode": "linked_relative",
    "hide_display_bridge": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `NIC25X_ALL_NON_IC.pdsprj`
- Manifest: `NIC25X_ALL_NON_IC.pdsprj.manifest.json`

## What To Check In Proteus

Requested count per family: 25. Displays should appear without counting the internal D20 bridge as a user diode. SWITCH and POT-HG should each have the requested visible count, with the internal dummy control moved by the layout/beautifier stage. Check for open crashes, DLL errors, bad object records, missing controls, and detached labels.

## User Result

Pending.

## Observation

Pending user Proteus result.
