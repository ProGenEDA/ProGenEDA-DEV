# Beautifier LED-RED Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `LED-RED`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `130`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (25090120, 17851120), `length_prefixed_text:D21`
- `78/82` -> (25090120, 17470120), `length_prefixed_text:LED-RED`
- `154/158` -> (25090120, 17216120), `length_prefixed_text:LED-RED`
- `383/387` -> (24638000, 17526000), `marker_body:LED-RED`

## Test Files

- `00_LED00_LED-RED_1X_BASELINE_NO_BEAUTIFY/LED00_LED-RED_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `LED-RED` should open in the original donor-selected position.
- `01_LED01_LED-RED_1X_PARSED_COORDS/LED01_LED-RED_1X_PARSED_COORDS.pdsprj`: 1 `LED-RED` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_LED02_LED-RED_3X_PARSED_COORDS/LED02_LED-RED_3X_PARSED_COORDS.pdsprj`: 3 `LED-RED` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_LED03_LED-RED_5X_PARSED_COORDS/LED03_LED-RED_5X_PARSED_COORDS.pdsprj`: 5 `LED-RED` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `LED-RED` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `LED-RED` is accepted for these counts.
