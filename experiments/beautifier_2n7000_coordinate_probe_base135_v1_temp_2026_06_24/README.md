# Beautifier 2N7000 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `2N7000`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `70`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (-20934680, -32237680), `length_prefixed_text:Q100`
- `78/82` -> (-20934680, -32618680), `length_prefixed_text:2N7000`
- `153/157` -> (-20934680, -32872680), `length_prefixed_text:2N7000`
- `399/403` -> (-21590000, -32766000), `marker_body:2N7000`

## Test Files

- `00_2N700000_2N7000_1X_BASELINE_NO_BEAUTIFY/2N700000_2N7000_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `2N7000` should open in the original donor-selected position.
- `01_2N700001_2N7000_1X_PARSED_COORDS/2N700001_2N7000_1X_PARSED_COORDS.pdsprj`: 1 `2N7000` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_2N700002_2N7000_3X_PARSED_COORDS/2N700002_2N7000_3X_PARSED_COORDS.pdsprj`: 3 `2N7000` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_2N700003_2N7000_5X_PARSED_COORDS/2N700003_2N7000_5X_PARSED_COORDS.pdsprj`: 5 `2N7000` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `2N7000` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `2N7000` is accepted for these counts.
