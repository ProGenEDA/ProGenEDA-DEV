# Beautifier NMOSFET Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `NMOSFET`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `120`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (31643320, 9926320), `length_prefixed_text:Q41`
- `78/82` -> (31643320, 9545320), `length_prefixed_text:NMOSFET`
- `154/158` -> (31643320, 9291320), `length_prefixed_text:NMOSFET`
- `241/245` -> (31643320, 9291320), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `317/321` -> (30988000, 9398000), `marker_body:NMOSFET`

## Test Files

- `00_NMOSFE00_NMOSFET_1X_BASELINE_NO_BEAUTIFY/NMOSFE00_NMOSFET_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `NMOSFET` should open in the original donor-selected position.
- `01_NMOSFE01_NMOSFET_1X_PARSED_COORDS/NMOSFE01_NMOSFET_1X_PARSED_COORDS.pdsprj`: 1 `NMOSFET` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_NMOSFE02_NMOSFET_3X_PARSED_COORDS/NMOSFE02_NMOSFET_3X_PARSED_COORDS.pdsprj`: 3 `NMOSFET` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_NMOSFE03_NMOSFET_5X_PARSED_COORDS/NMOSFE03_NMOSFET_5X_PARSED_COORDS.pdsprj`: 5 `NMOSFET` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `NMOSFET` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `NMOSFET` is accepted for these counts.
