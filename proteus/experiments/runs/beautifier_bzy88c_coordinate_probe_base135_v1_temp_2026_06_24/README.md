# Beautifier BZY88C Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `BZY88C`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `125`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (487680, -23601680), `length_prefixed_text:D105`
- `78/82` -> (487680, -24150320), `length_prefixed_text:BZY88C`
- `153/157` -> (487680, -24404320), `length_prefixed_text:BZY88C`
- `368/372` -> (508000, -23876000), `marker_body:BZY88C`

## Test Files

- `00_BZY88C00_BZY88C_1X_BASELINE_NO_BEAUTIFY/BZY88C00_BZY88C_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `BZY88C` should open in the original donor-selected position.
- `01_BZY88C01_BZY88C_1X_PARSED_COORDS/BZY88C01_BZY88C_1X_PARSED_COORDS.pdsprj`: 1 `BZY88C` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_BZY88C02_BZY88C_3X_PARSED_COORDS/BZY88C02_BZY88C_3X_PARSED_COORDS.pdsprj`: 3 `BZY88C` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_BZY88C03_BZY88C_5X_PARSED_COORDS/BZY88C03_BZY88C_5X_PARSED_COORDS.pdsprj`: 5 `BZY88C` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `BZY88C` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `BZY88C` is accepted for these counts.
