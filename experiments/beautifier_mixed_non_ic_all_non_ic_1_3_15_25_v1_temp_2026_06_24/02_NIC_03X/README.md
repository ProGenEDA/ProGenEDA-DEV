# NIC03X_ALL_NON_IC

## Purpose

Non-IC stress case requesting 3 of every non-IC component family currently exercised by the component placer.
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
    "7SEG-COM-AN-BLUE": 3,
    "7SEG-COM-CAT-BLUE": 3,
    "BRIDGE": 3,
    "BS170": 3,
    "BZX55C5V1": 3,
    "BZX79C5V1": 3,
    "BZY88C": 3,
    "CAP": 3,
    "CAP-ELEC": 3,
    "CSOURCE": 3,
    "DIODE": 3,
    "FUSE": 3,
    "LED-RED": 3,
    "LM317T": 3,
    "NMOSFET": 3,
    "NPN": 3,
    "OPAMP": 3,
    "PNP": 3,
    "POT-HG": 3,
    "REALIND": 3,
    "RESISTOR": 3,
    "SWITCH": 3,
    "TRAN-2P2S": 3,
    "VPULSE": 3,
    "VSINE": 3,
    "VSOURCE": 3
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

- Project: `NIC03X_ALL_NON_IC.pdsprj`
- Manifest: `NIC03X_ALL_NON_IC.pdsprj.manifest.json`

## What To Check In Proteus

Requested count per family: 3. Displays should appear without counting the internal D20 bridge as a user diode. SWITCH and POT-HG should each have the requested visible count, with the internal dummy control moved by the layout/beautifier stage. Check for open crashes, DLL errors, bad object records, missing controls, and detached labels.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
