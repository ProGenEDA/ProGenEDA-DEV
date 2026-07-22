# Beautifier Mixed Non-IC Counts

Generated on 2026-06-25.

This pack combines all current non-IC component-placer families from the new-component mega donor.
It includes sources, displays, controls, transformer/bridge/regulator/opamp, and the accepted passive/discrete families.

## Donor

- `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`

## Special Rules Under Test

- `7SEG-COM-AN-BLUE` and `7SEG-COM-CAT-BLUE` automatically carry the internal `D20` display bridge.
- `D20` is not included in the requested `DIODE` count.
- `hide_display_bridge=true` moves the `D20` bridge to a parsed-coordinate bbox origin near `100000/100000`.
- `SWITCH` and `POT-HG` use the exact requested count with no extra dummy packet.

## Families

- `RESISTOR`: donor inventory `115`
- `CAP`: donor inventory `100`
- `REALIND`: donor inventory `100`
- `CAP-ELEC`: donor inventory `105`
- `DIODE`: donor inventory `100`
- `1N4007`: donor inventory `105`
- `1N4148`: donor inventory `100`
- `1N4733A`: donor inventory `130`
- `1N6000B`: donor inventory `100`
- `40EPS08`: donor inventory `160`
- `BZX55C5V1`: donor inventory `100`
- `BZX79C5V1`: donor inventory `105`
- `BZY88C`: donor inventory `125`
- `NPN`: donor inventory `100`
- `PNP`: donor inventory `100`
- `2N3904`: donor inventory `95`
- `2N4401`: donor inventory `80`
- `2N7000`: donor inventory `70`
- `BS170`: donor inventory `75`
- `NMOSFET`: donor inventory `120`
- `FUSE`: donor inventory `145`
- `LED-RED`: donor inventory `130`
- `BRIDGE`: donor inventory `105`
- `TRAN-2P2S`: donor inventory `50`
- `LM317T`: donor inventory `80`
- `OPAMP`: donor inventory `105`
- `VSOURCE`: donor inventory `95`
- `CSOURCE`: donor inventory `70`
- `VSINE`: donor inventory `110`
- `VPULSE`: donor inventory `100`
- `7SEG-COM-AN-BLUE`: donor inventory `100`
- `7SEG-COM-CAT-BLUE`: donor inventory `100`
- `SWITCH`: donor inventory `105`
- `POT-HG`: donor inventory `100`

## Cases

- `01_NIC_01X/NIC01X_ALL_NON_IC.pdsprj`: 1 each, user-visible total `34`.

## User Results

Pending.

## Observation

Static generation and manifest validation pending in this run.
