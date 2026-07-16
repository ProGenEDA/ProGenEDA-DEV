# Beautifier VPULSE Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `VPULSE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `100`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `5/9` -> (-22966680, 14752320), `length_prefixed_text:V42`
- `77/81` -> (-22966680, 14371320), `length_prefixed_text:VPULSE`
- `152/156` -> (-22966680, 14117320), `length_prefixed_text:VPULSE`
- `238/242` -> (-22966680, 14117320), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `313/317` -> (-24130000, 14732000), `marker_body:VPULSE`

## Test Files

- `00_VP00_1X_BASELINE/VP00_1X_BASELINE.pdsprj`: Baseline control. One `VPULSE` should open in the original donor-selected position.
- `01_VP01_1X_COORDS/VP01_1X_COORDS.pdsprj`: 1 `VPULSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_VP02_3X_COORDS/VP02_3X_COORDS.pdsprj`: 3 `VPULSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_VP03_15X_COORDS/VP03_15X_COORDS.pdsprj`: 15 `VPULSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_VP04_25X_COORDS/VP04_25X_COORDS.pdsprj`: 25 `VPULSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `VPULSE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `VPULSE` is accepted for these counts.
