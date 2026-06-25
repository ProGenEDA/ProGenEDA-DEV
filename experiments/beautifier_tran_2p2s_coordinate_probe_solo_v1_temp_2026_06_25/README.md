# Beautifier TRAN-2P2S Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `TRAN-2P2S`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `50`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `5/9` -> (6583680, -29443680), `length_prefixed_text:TR1`
- `80/84` -> (6583680, -32024320), `length_prefixed_text:TRAN-2P2S`
- `158/162` -> (6583680, -32278320), `length_prefixed_text:TRAN-2P2S`
- `360/364` -> (6604000, -29464000), `marker_body:TRAN-2P2S`

## Test Files

- `00_TR00_1X_BASELINE/TR00_1X_BASELINE.pdsprj`: Baseline control. One `TRAN-2P2S` should open in the original donor-selected position.
- `01_TR01_1X_COORDS/TR01_1X_COORDS.pdsprj`: 1 `TRAN-2P2S` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_TR02_3X_COORDS/TR02_3X_COORDS.pdsprj`: 3 `TRAN-2P2S` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_TR03_15X_COORDS/TR03_15X_COORDS.pdsprj`: 15 `TRAN-2P2S` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_TR04_25X_COORDS/TR04_25X_COORDS.pdsprj`: 25 `TRAN-2P2S` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `TRAN-2P2S` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `TRAN-2P2S` is accepted for these counts.
