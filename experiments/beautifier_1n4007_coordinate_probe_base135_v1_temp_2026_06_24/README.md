# Beautifier 1N4007 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `1N4007`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `105`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (7091680, -23601680), `length_prefixed_text:D130`
- `78/82` -> (7091680, -24150320), `length_prefixed_text:1N4007`
- `153/157` -> (7091680, -24404320), `length_prefixed_text:1N4007`
- `358/362` -> (7112000, -23876000), `marker_body:1N4007`

## Test Files

- `00_1N400700_1N4007_1X_BASELINE_NO_BEAUTIFY/1N400700_1N4007_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `1N4007` should open in the original donor-selected position.
- `01_1N400701_1N4007_1X_PARSED_COORDS/1N400701_1N4007_1X_PARSED_COORDS.pdsprj`: 1 `1N4007` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_1N400702_1N4007_3X_PARSED_COORDS/1N400702_1N4007_3X_PARSED_COORDS.pdsprj`: 3 `1N4007` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_1N400703_1N4007_5X_PARSED_COORDS/1N400703_1N4007_5X_PARSED_COORDS.pdsprj`: 5 `1N4007` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `1N4007` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `1N4007` is accepted for these counts.
