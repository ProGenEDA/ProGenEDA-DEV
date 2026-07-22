# NIC15X_ALL_NON_IC

## Purpose

Non-IC stress case requesting 15 of every non-IC component family currently exercised by the component placer.
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
    "7SEG-COM-AN-BLUE": 15,
    "7SEG-COM-CAT-BLUE": 15,
    "BRIDGE": 15,
    "BS170": 15,
    "BZX55C5V1": 15,
    "BZX79C5V1": 15,
    "BZY88C": 15,
    "CAP": 15,
    "CAP-ELEC": 15,
    "CSOURCE": 15,
    "DIODE": 15,
    "FUSE": 15,
    "LED-RED": 15,
    "LM317T": 15,
    "NMOSFET": 15,
    "NPN": 15,
    "OPAMP": 15,
    "PNP": 15,
    "POT-HG": 15,
    "REALIND": 15,
    "RESISTOR": 15,
    "SWITCH": 15,
    "TRAN-2P2S": 15,
    "VPULSE": 15,
    "VSINE": 15,
    "VSOURCE": 15
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

- Project: `NIC15X_ALL_NON_IC.pdsprj`
- Manifest: `NIC15X_ALL_NON_IC.pdsprj.manifest.json`

## What To Check In Proteus

Requested count per family: 15. Displays should appear without counting the internal D20 bridge as a user diode. SWITCH and POT-HG should each have the requested visible count, with the internal dummy control moved by the layout/beautifier stage. Check for open crashes, DLL errors, bad object records, missing controls, and detached labels.

## User Result

Pending.

## Observation

Pending user Proteus result.
