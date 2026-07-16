# Beautifier 2N4401 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `2N4401`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `80`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (-15092680, -32237680), `length_prefixed_text:Q84`
- `77/81` -> (-15092680, -32618680), `length_prefixed_text:2N4401`
- `152/156` -> (-15092680, -32872680), `length_prefixed_text:2N4401`
- `360/364` -> (-15494000, -32766000), `marker_body:2N4401`

## Test Files

- `00_2N440100_2N4401_1X_BASELINE_NO_BEAUTIFY/2N440100_2N4401_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `2N4401` should open in the original donor-selected position.
- `01_2N440101_2N4401_1X_PARSED_COORDS/2N440101_2N4401_1X_PARSED_COORDS.pdsprj`: 1 `2N4401` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_2N440102_2N4401_3X_PARSED_COORDS/2N440102_2N4401_3X_PARSED_COORDS.pdsprj`: 3 `2N4401` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_2N440103_2N4401_5X_PARSED_COORDS/2N440103_2N4401_5X_PARSED_COORDS.pdsprj`: 5 `2N4401` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `2N4401` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `2N4401` is accepted for these counts.
