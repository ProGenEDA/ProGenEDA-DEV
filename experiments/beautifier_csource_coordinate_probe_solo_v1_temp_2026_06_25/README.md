# Beautifier CSOURCE Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `CSOURCE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `70`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `4/8` -> (-21696680, -17505680), `length_prefixed_text:I7`
- `72/76` -> (-21696680, -17886680), `length_prefixed_text:1A`
- `148/152` -> (-21696680, -18140680), `length_prefixed_text:CSOURCE`
- `234/238` -> (-21696680, -18140680), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `310/314` -> (-22860000, -17526000), `marker_body:CSOURCE`

## Test Files

- `00_CS00_1X_BASELINE/CS00_1X_BASELINE.pdsprj`: Baseline control. One `CSOURCE` should open in the original donor-selected position.
- `01_CS01_1X_COORDS/CS01_1X_COORDS.pdsprj`: 1 `CSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_CS02_3X_COORDS/CS02_3X_COORDS.pdsprj`: 3 `CSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_CS03_15X_COORDS/CS03_15X_COORDS.pdsprj`: 15 `CSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_CS04_25X_COORDS/CS04_25X_COORDS.pdsprj`: 25 `CSOURCE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `CSOURCE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `CSOURCE` is accepted for these counts.
