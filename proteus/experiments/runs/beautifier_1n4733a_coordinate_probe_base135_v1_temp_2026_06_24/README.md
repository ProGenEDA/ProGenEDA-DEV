# Beautifier 1N4733A Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `1N4733A`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `130`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (-26690320, 15768320), `length_prefixed_text:D47`
- `78/82` -> (-26690320, 15219680), `length_prefixed_text:1N4733A`
- `154/158` -> (-26690320, 14965680), `length_prefixed_text:1N4733A`
- `379/383` -> (-26670000, 15494000), `marker_body:1N4733A`

## Test Files

- `00_1N473300_1N4733A_1X_BASELINE_NO_BEAUTIFY/1N473300_1N4733A_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `1N4733A` should open in the original donor-selected position.
- `01_1N473301_1N4733A_1X_PARSED_COORDS/1N473301_1N4733A_1X_PARSED_COORDS.pdsprj`: 1 `1N4733A` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_1N473302_1N4733A_3X_PARSED_COORDS/1N473302_1N4733A_3X_PARSED_COORDS.pdsprj`: 3 `1N4733A` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_1N473303_1N4733A_5X_PARSED_COORDS/1N473303_1N4733A_5X_PARSED_COORDS.pdsprj`: 5 `1N4733A` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `1N4733A` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `1N4733A` is accepted for these counts.
