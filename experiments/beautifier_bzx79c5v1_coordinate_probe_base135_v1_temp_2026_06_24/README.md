# Beautifier BZX79C5V1 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `BZX79C5V1`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `105`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (23347680, -33507680), `length_prefixed_text:D211`
- `81/85` -> (23347680, -34056320), `length_prefixed_text:BZX79C5V1`
- `159/163` -> (23347680, -34310320), `length_prefixed_text:BZX79C5V1`
- `385/389` -> (23368000, -33782000), `marker_body:BZX79C5V1`

## Test Files

- `00_BZX79C00_BZX79C5V1_1X_BASELINE_NO_BEAUTIFY/BZX79C00_BZX79C5V1_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `BZX79C5V1` should open in the original donor-selected position.
- `01_BZX79C01_BZX79C5V1_1X_PARSED_COORDS/BZX79C01_BZX79C5V1_1X_PARSED_COORDS.pdsprj`: 1 `BZX79C5V1` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_BZX79C02_BZX79C5V1_3X_PARSED_COORDS/BZX79C02_BZX79C5V1_3X_PARSED_COORDS.pdsprj`: 3 `BZX79C5V1` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_BZX79C03_BZX79C5V1_5X_PARSED_COORDS/BZX79C03_BZX79C5V1_5X_PARSED_COORDS.pdsprj`: 5 `BZX79C5V1` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `BZX79C5V1` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `BZX79C5V1` is accepted for these counts.
