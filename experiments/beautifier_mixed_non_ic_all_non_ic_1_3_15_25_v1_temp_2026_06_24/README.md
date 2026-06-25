# Beautifier Mixed Non-IC Counts

Generated on 2026-06-24.

This pack combines all current non-IC component-placer families from the new-component mega donor.
It includes sources, displays, controls, transformer/bridge/regulator/opamp, and the accepted passive/discrete families.

## Donor

- `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`

## Special Rules Under Test

- `7SEG-COM-AN-BLUE` and `7SEG-COM-CAT-BLUE` automatically carry the internal `D20` display bridge.
- `D20` is not included in the requested `DIODE` count.
- `hide_display_bridge=true` moves the `D20` bridge by the display-small relative beautifier mode.
- `SWITCH` and `POT-HG` request one extra internal dummy packet; the dummy does not count as a user component.
- `hidden_coordinate_mode=linked_relative` is used for the internal control dummy packets.

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
- `SWITCH`: donor inventory `105` (needs one extra dummy packet internally)
- `POT-HG`: donor inventory `100` (needs one extra dummy packet internally)

## Cases

- `01_NIC_01X/NIC01X_ALL_NON_IC.pdsprj`: 1 each, user-visible total `34`.
- `02_NIC_03X/NIC03X_ALL_NON_IC.pdsprj`: 3 each, user-visible total `102`.
- `03_NIC_15X/NIC15X_ALL_NON_IC.pdsprj`: 15 each, user-visible total `510`.
- `04_NIC_25X/NIC25X_ALL_NON_IC.pdsprj`: 25 each, user-visible total `850`.

## User Results

Rejected. User reported every mixed non-IC case failed.

Do not use this pack as coordinate-mutation evidence. It combined families
before BRIDGE, transformer, regulator/opamp, source, display, and control
coordinate mutation had been proven separately.

## Codex Observation

Static generation and manifest validation passed:

- `NIC01X_ALL_NON_IC`: 34 user-requested components, 1 `D20` bridge, 2 hidden control dummy groups
- `NIC03X_ALL_NON_IC`: 102 user-requested components, 1 `D20` bridge, 2 hidden control dummy groups
- `NIC15X_ALL_NON_IC`: 510 user-requested components, 1 `D20` bridge, 2 hidden control dummy groups
- `NIC25X_ALL_NON_IC`: 850 user-requested components, 1 `D20` bridge, 2 hidden control dummy groups
- No donor cap was hit; every case uses the requested user count exactly.
- `D20` starts at the hidden sentinel position and is not included in the requested `DIODE` count.
- Visible `SWITCH` and `POT-HG` packets are intentionally not grid-translated yet; only their internal dummy packets use `hidden_coordinate_mode=linked_relative`.
- Post-failure byte audit found that the unproven families fell through to the
  broad coordinate scanner. That scanner mostly found internal constants such
  as `(381000, 203200)` instead of the real reference/value/model/body
  coordinates. This pack is superseded by the 2026-06-25 solo family probes.
