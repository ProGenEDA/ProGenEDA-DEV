# Beautifier 7SEG-COM-AN-BLUE Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `7SEG-COM-AN-BLUE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `100`
- Probe variant: `display_names_d20_v3`

## Parsed Coordinates Under Test

- `4/8` -> (-149372320, -48915320), `display_row_anchor`
- `70/74` -> (-149372320, -49296320), `display_component_id`
- `153/157` -> (-149372320, -49550320), `length_prefixed_text:7SEG-COM-ANODE`
- `258/262` -> (-149372320, -49550320), `length_prefixed_text:{MODFILE=7SEGCOMA}\n{VF=1.5V}\n{`
- `341/345` -> (-149352000, -46482000), `marker_body:7SEG-COM-ANODE`

## Test Files

- `00_AN00_1X_BASELINE/AN00_1X_BASELINE.pdsprj`: Baseline control. One `7SEG-COM-AN-BLUE` should open in the original donor-selected position.
- `01_AN01_1X_MOVE_D20_STATIC/AN01_1X_MOVE_D20_STATIC.pdsprj`: One `7SEG-COM-AN-BLUE` should move onto the grid and remain intact. D20 should stay in its donor position. This separates display movement from D20 movement.
- `02_AN02_1X_COORDS/AN02_1X_COORDS.pdsprj`: 1 `7SEG-COM-AN-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. Proteus-generated Dxxx names should stay attached to their displays. D20 should be in the 100000/100000 infrastructure region and must not count as a requested diode.
- `03_AN03_3X_COORDS/AN03_3X_COORDS.pdsprj`: 3 `7SEG-COM-AN-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. Proteus-generated Dxxx names should stay attached to their displays. D20 should be in the 100000/100000 infrastructure region and must not count as a requested diode.
- `04_AN04_15X_COORDS/AN04_15X_COORDS.pdsprj`: 15 `7SEG-COM-AN-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. Proteus-generated Dxxx names should stay attached to their displays. D20 should be in the 100000/100000 infrastructure region and must not count as a requested diode.
- `05_AN05_25X_COORDS/AN05_25X_COORDS.pdsprj`: 25 `7SEG-COM-AN-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. Proteus-generated Dxxx names should stay attached to their displays. D20 should be in the 100000/100000 infrastructure region and must not count as a requested diode.

## User Results

Pending.

## What Success Means

If every `7SEG-COM-AN-BLUE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `7SEG-COM-AN-BLUE` is accepted for these counts.
