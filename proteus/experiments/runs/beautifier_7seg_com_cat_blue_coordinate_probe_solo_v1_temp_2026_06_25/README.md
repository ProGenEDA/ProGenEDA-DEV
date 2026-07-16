# Beautifier 7SEG-COM-CAT-BLUE Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `7SEG-COM-CAT-BLUE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `100`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `156/160` -> (126471680, 126258320), `length_prefixed_text:7SEG-COM-CAT-BLUE`
- `261/265` -> (126471680, 126258320), `length_prefixed_text:{MODFILE=7SEGCOMK}\n{VF=1.5V}\n{`
- `556/560` -> (-149372320, -49550320), `length_prefixed_text:7SEG-COM-ANODE`
- `661/665` -> (-149372320, -49550320), `length_prefixed_text:{MODFILE=7SEGCOMA}\n{VF=1.5V}\n{`
- `744/748` -> (-149352000, -46482000), `marker_body:7SEG-COM-ANODE`
- `347/351` -> (126492000, 125984000), `marker_body:7SEG-COM-CAT-BLUE`

## Test Files

- `00_CC00_1X_BASELINE/CC00_1X_BASELINE.pdsprj`: Baseline control. One `7SEG-COM-CAT-BLUE` should open in the original donor-selected position.
- `01_CC01_1X_MOVE_D20_STATIC/CC01_1X_MOVE_D20_STATIC.pdsprj`: One `7SEG-COM-CAT-BLUE` should move onto the grid and remain intact. D20 should stay in its donor position. This separates display movement from D20 movement.
- `02_CC02_1X_COORDS/CC02_1X_COORDS.pdsprj`: 1 `7SEG-COM-CAT-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. D20 should move separately and must not count as a requested diode.
- `03_CC03_3X_COORDS/CC03_3X_COORDS.pdsprj`: 3 `7SEG-COM-CAT-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. D20 should move separately and must not count as a requested diode.
- `04_CC04_15X_COORDS/CC04_15X_COORDS.pdsprj`: 15 `7SEG-COM-CAT-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. D20 should move separately and must not count as a requested diode.
- `05_CC05_25X_COORDS/CC05_25X_COORDS.pdsprj`: 25 `7SEG-COM-CAT-BLUE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. D20 should move separately and must not count as a requested diode.

## User Results

Pending.

## What Success Means

If every `7SEG-COM-CAT-BLUE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `7SEG-COM-CAT-BLUE` is accepted for these counts.
