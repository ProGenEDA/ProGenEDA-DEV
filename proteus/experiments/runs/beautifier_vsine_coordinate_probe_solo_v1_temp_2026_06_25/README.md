# Beautifier VSINE Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `VSINE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `110`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `4/8` -> (-19410680, 14752320), `length_prefixed_text:V1`
- `75/79` -> (-19410680, 14371320), `length_prefixed_text:VSINE`
- `149/153` -> (-19410680, 14117320), `length_prefixed_text:VSINE`
- `235/239` -> (-19410680, 14117320), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `309/313` -> (-20574000, 14732000), `marker_body:VSINE`

## Test Files

- `00_AC00_1X_BASELINE/AC00_1X_BASELINE.pdsprj`: Baseline control. One `VSINE` should open in the original donor-selected position.
- `01_AC01_1X_COORDS/AC01_1X_COORDS.pdsprj`: 1 `VSINE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_AC02_3X_COORDS/AC02_3X_COORDS.pdsprj`: 3 `VSINE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_AC03_15X_COORDS/AC03_15X_COORDS.pdsprj`: 15 `VSINE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_AC04_25X_COORDS/AC04_25X_COORDS.pdsprj`: 25 `VSINE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `VSINE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `VSINE` is accepted for these counts.
