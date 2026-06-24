# Beautifier BZX55C5V1 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `BZX55C5V1`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `100`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (23601680, -29443680), `length_prefixed_text:D191`
- `81/85` -> (23601680, -29992320), `length_prefixed_text:BZX55C5V1`
- `159/163` -> (23601680, -30246320), `length_prefixed_text:BZX55C5V1`
- `385/389` -> (23622000, -29718000), `marker_body:BZX55C5V1`

## Test Files

- `00_BZX55C00_BZX55C5V1_1X_BASELINE_NO_BEAUTIFY/BZX55C00_BZX55C5V1_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `BZX55C5V1` should open in the original donor-selected position.
- `01_BZX55C01_BZX55C5V1_1X_PARSED_COORDS/BZX55C01_BZX55C5V1_1X_PARSED_COORDS.pdsprj`: 1 `BZX55C5V1` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_BZX55C02_BZX55C5V1_3X_PARSED_COORDS/BZX55C02_BZX55C5V1_3X_PARSED_COORDS.pdsprj`: 3 `BZX55C5V1` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_BZX55C03_BZX55C5V1_5X_PARSED_COORDS/BZX55C03_BZX55C5V1_5X_PARSED_COORDS.pdsprj`: 5 `BZX55C5V1` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `BZX55C5V1` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `BZX55C5V1` is accepted for these counts.
