# NIC01X_ALL_NON_IC

## Purpose

Non-IC stress case requesting 1 of every non-IC component family currently exercised by the component placer.
This case uses the normal component placer plus the shared parsed-coordinate beautifier.

## Input

```json
{
  "components": {
    "1N4007": 1,
    "1N4148": 1,
    "1N4733A": 1,
    "1N6000B": 1,
    "2N3904": 1,
    "2N4401": 1,
    "2N7000": 1,
    "40EPS08": 1,
    "7SEG-COM-AN-BLUE": 1,
    "7SEG-COM-CAT-BLUE": 1,
    "BRIDGE": 1,
    "BS170": 1,
    "BZX55C5V1": 1,
    "BZX79C5V1": 1,
    "BZY88C": 1,
    "CAP": 1,
    "CAP-ELEC": 1,
    "CSOURCE": 1,
    "DIODE": 1,
    "FUSE": 1,
    "LED-RED": 1,
    "LM317T": 1,
    "NMOSFET": 1,
    "NPN": 1,
    "OPAMP": 1,
    "PNP": 1,
    "POT-HG": 1,
    "REALIND": 1,
    "RESISTOR": 1,
    "SWITCH": 1,
    "TRAN-2P2S": 1,
    "VPULSE": 1,
    "VSINE": 1,
    "VSOURCE": 1
  },
  "layout": {
    "binary_coordinate_mutation": true,
    "display_bridge_coordinate_mode": "display_absolute_100k",
    "hide_display_bridge": true,
    "strategy": "beautify"
  },
  "schema": "component-placement/v0.1"
}
```

## Output

- Project: `NIC01X_ALL_NON_IC.pdsprj`
- Manifest: `NIC01X_ALL_NON_IC.pdsprj.manifest.json`

## What To Check In Proteus

Requested count per family: 1. Displays should appear without counting the internal D20 bridge as a user diode. SWITCH and POT-HG should each have exactly the requested count, with no extra dummy packet. Check for open crashes, DLL errors, bad object records, missing controls, and detached labels.

## User Result

Pending.

## Codex Observation

Pending user Proteus result.
