# Beautifier 1N4148 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `1N4148`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `100`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `6/10` -> (12425680, -26395680), `length_prefixed_text:D151`
- `78/82` -> (12425680, -26944320), `length_prefixed_text:1N4148`
- `153/157` -> (12425680, -27198320), `length_prefixed_text:1N4148`
- `357/361` -> (12446000, -26670000), `marker_body:1N4148`

## Test Files

- `00_1N414800_1N4148_1X_BASELINE_NO_BEAUTIFY/1N414800_1N4148_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `1N4148` should open in the original donor-selected position.
- `01_1N414801_1N4148_1X_PARSED_COORDS/1N414801_1N4148_1X_PARSED_COORDS.pdsprj`: 1 `1N4148` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_1N414802_1N4148_3X_PARSED_COORDS/1N414802_1N4148_3X_PARSED_COORDS.pdsprj`: 3 `1N4148` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_1N414803_1N4148_5X_PARSED_COORDS/1N414803_1N4148_5X_PARSED_COORDS.pdsprj`: 5 `1N4148` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `1N4148` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `1N4148` is accepted for these counts.
