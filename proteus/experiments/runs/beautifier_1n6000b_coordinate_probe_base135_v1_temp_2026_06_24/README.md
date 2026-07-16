# Beautifier 1N6000B Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `1N6000B`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `100`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (18521680, -23347680), `length_prefixed_text:D171`
- `79/83` -> (18521680, -23896320), `length_prefixed_text:1N6000B`
- `155/159` -> (18521680, -24150320), `length_prefixed_text:1N6000B`
- `380/384` -> (18542000, -23622000), `marker_body:1N6000B`

## Test Files

- `00_1N600000_1N6000B_1X_BASELINE_NO_BEAUTIFY/1N600000_1N6000B_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `1N6000B` should open in the original donor-selected position.
- `01_1N600001_1N6000B_1X_PARSED_COORDS/1N600001_1N6000B_1X_PARSED_COORDS.pdsprj`: 1 `1N6000B` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_1N600002_1N6000B_3X_PARSED_COORDS/1N600002_1N6000B_3X_PARSED_COORDS.pdsprj`: 3 `1N6000B` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_1N600003_1N6000B_5X_PARSED_COORDS/1N600003_1N6000B_5X_PARSED_COORDS.pdsprj`: 5 `1N6000B` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `1N6000B` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `1N6000B` is accepted for these counts.
