# Beautifier 2N3904 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `2N3904`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `95`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (-2392680, -31475680), `length_prefixed_text:Q65`
- `77/81` -> (-2392680, -31856680), `length_prefixed_text:2N3904`
- `152/156` -> (-2392680, -32110680), `length_prefixed_text:2N3904`
- `360/364` -> (-2794000, -32004000), `marker_body:2N3904`

## Test Files

- `00_2N390400_2N3904_1X_BASELINE_NO_BEAUTIFY/2N390400_2N3904_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `2N3904` should open in the original donor-selected position.
- `01_2N390401_2N3904_1X_PARSED_COORDS/2N390401_2N3904_1X_PARSED_COORDS.pdsprj`: 1 `2N3904` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_2N390402_2N3904_3X_PARSED_COORDS/2N390402_2N3904_3X_PARSED_COORDS.pdsprj`: 3 `2N3904` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_2N390403_2N3904_5X_PARSED_COORDS/2N390403_2N3904_5X_PARSED_COORDS.pdsprj`: 5 `2N3904` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `2N3904` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `2N3904` is accepted for these counts.
