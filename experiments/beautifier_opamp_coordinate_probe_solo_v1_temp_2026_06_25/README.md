# Beautifier OPAMP Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `OPAMP`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `105`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `6/10` -> (30713680, -17124680), `length_prefixed_text:U107`
- `77/81` -> (30713680, -18435320), `length_prefixed_text:OPAMP`
- `151/155` -> (30713680, -18689320), `length_prefixed_text:OPAMP`
- `358/362` -> (31242000, -17780000), `marker_body:OPAMP`

## Test Files

- `00_OA00_1X_BASELINE/OA00_1X_BASELINE.pdsprj`: Baseline control. One `OPAMP` should open in the original donor-selected position.
- `01_OA01_1X_COORDS/OA01_1X_COORDS.pdsprj`: 1 `OPAMP` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_OA02_3X_COORDS/OA02_3X_COORDS.pdsprj`: 3 `OPAMP` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_OA03_15X_COORDS/OA03_15X_COORDS.pdsprj`: 15 `OPAMP` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_OA04_25X_COORDS/OA04_25X_COORDS.pdsprj`: 25 `OPAMP` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `OPAMP` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `OPAMP` is accepted for these counts.
