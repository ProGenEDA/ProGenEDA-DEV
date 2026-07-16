# Beautifier BS170 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `BS170`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `75`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (-21950680, -25557480), `length_prefixed_text:Q114`
- `77/81` -> (-21950680, -25938480), `length_prefixed_text:BS170`
- `151/155` -> (-21950680, -26192480), `length_prefixed_text:BS170`
- `389/393` -> (-22860000, -26162000), `marker_body:BS170`

## Test Files

- `00_BS17000_BS170_1X_BASELINE_NO_BEAUTIFY/BS17000_BS170_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `BS170` should open in the original donor-selected position.
- `01_BS17001_BS170_1X_PARSED_COORDS/BS17001_BS170_1X_PARSED_COORDS.pdsprj`: 1 `BS170` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_BS17002_BS170_3X_PARSED_COORDS/BS17002_BS170_3X_PARSED_COORDS.pdsprj`: 3 `BS170` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_BS17003_BS170_5X_PARSED_COORDS/BS17003_BS170_5X_PARSED_COORDS.pdsprj`: 5 `BS170` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `BS170` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `BS170` is accepted for these counts.
