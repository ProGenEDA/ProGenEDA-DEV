# Beautifier VSOURCE Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `VSOURCE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `95`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `5/9` -> (-21188680, 14752320), `length_prefixed_text:V23`
- `73/77` -> (-21188680, 14371320), `length_prefixed_text:1V`
- `149/153` -> (-21188680, 14117320), `length_prefixed_text:VSOURCE`
- `233/237` -> (-21188680, 14117320), `length_prefixed_text:{PRIMITIVE=ANALOG}`
- `309/313` -> (-22352000, 14732000), `marker_body:VSOURCE`

## Test Files

- `00_VS00_1X_BASELINE/VS00_1X_BASELINE.pdsprj`: Baseline control. One `VSOURCE` should open in the original donor-selected position.
- `01_VS01_1X_COORDS/VS01_1X_COORDS.pdsprj`: 1 `VSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_VS02_3X_COORDS/VS02_3X_COORDS.pdsprj`: 3 `VSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_VS03_15X_COORDS/VS03_15X_COORDS.pdsprj`: 15 `VSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_VS04_25X_COORDS/VS04_25X_COORDS.pdsprj`: 25 `VSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `VSOURCE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `VSOURCE` is accepted for these counts.
