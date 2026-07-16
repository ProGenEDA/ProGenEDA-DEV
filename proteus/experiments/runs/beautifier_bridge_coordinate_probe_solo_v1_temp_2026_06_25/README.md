# Beautifier BRIDGE Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `BRIDGE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `105`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `5/9` -> (-28681670, 17292320), `length_prefixed_text:BR1`
- `77/81` -> (-28681670, 15219680), `length_prefixed_text:BRIDGE`
- `152/156` -> (-28681670, 14965680), `length_prefixed_text:BRIDGE`
- `251/255` -> (-28681670, 14965680), `length_prefixed_text:{MODFILE=DIODE}\n{PACKAGE=BRIDGE`
- `326/330` -> (-29464000, 16256000), `marker_body:BRIDGE`

## Test Files

- `00_BR00_1X_BASELINE/BR00_1X_BASELINE.pdsprj`: Baseline control. One `BRIDGE` should open in the original donor-selected position.
- `01_BR01_1X_COORDS/BR01_1X_COORDS.pdsprj`: 1 `BRIDGE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `02_BR02_3X_COORDS/BR02_3X_COORDS.pdsprj`: 3 `BRIDGE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `03_BR03_15X_COORDS/BR03_15X_COORDS.pdsprj`: 15 `BRIDGE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.
- `04_BR04_25X_COORDS/BR04_25X_COORDS.pdsprj`: 25 `BRIDGE` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls.

## User Results

Pending.

## What Success Means

If every `BRIDGE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `BRIDGE` is accepted for these counts.
