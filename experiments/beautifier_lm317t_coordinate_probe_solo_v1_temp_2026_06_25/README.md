# Beautifier LM317T Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `LM317T`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `80`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `6/10` -> (-9164320, -20680680), `length_prefixed_text:U132`
- `78/82` -> (-9164320, -21061680), `length_prefixed_text:LM317T`
- `153/157` -> (-9164320, -21315680), `length_prefixed_text:LM317T`
- `263/267` -> (-9164320, -21315680), `length_prefixed_text:{MODFILE=LM317_1}\n{RSC=0.3}\n\n`
- `338/342` -> (-8128000, -21844000), `marker_body:LM317T`

## Test Files

- `00_LM00_1X_BASELINE/LM00_1X_BASELINE.pdsprj`: Baseline control. One `LM317T` should open in the original donor-selected position.
- `01_LM01_1X_COORDS/LM01_1X_COORDS.pdsprj`: 1 `LM317T` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_LM02_3X_COORDS/LM02_3X_COORDS.pdsprj`: 3 `LM317T` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_LM03_15X_COORDS/LM03_15X_COORDS.pdsprj`: 15 `LM317T` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_LM04_25X_COORDS/LM04_25X_COORDS.pdsprj`: 25 `LM317T` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `LM317T` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `LM317T` is accepted for these counts.
