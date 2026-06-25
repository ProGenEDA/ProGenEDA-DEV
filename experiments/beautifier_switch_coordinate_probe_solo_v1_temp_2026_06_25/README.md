# Beautifier SWITCH Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `SWITCH`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `105`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `2/6` -> (-28976320, -37241480), `linked_packet:SWITCH`
- `68/72` -> (-28976320, -37661850), `linked_packet:SWITCH`
- `143/147` -> (-28976320, -37915850), `linked_packet:SWITCH`
- `208/212` -> (-28976320, -37915850), `linked_packet:SWITCH`
- `359/363` -> (-28702000, -37592000), `linked_packet:SWITCH`

## Test Files

- `00_SW00_1X_BASELINE/SW00_1X_BASELINE.pdsprj`: Baseline control. One `SWITCH` should open in the original donor-selected position.
- `01_SW01_1X_COORDS/SW01_1X_COORDS.pdsprj`: 1 `SWITCH` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.
- `02_SW02_3X_COORDS/SW02_3X_COORDS.pdsprj`: 3 `SWITCH` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.
- `03_SW03_15X_COORDS/SW03_15X_COORDS.pdsprj`: 15 `SWITCH` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.
- `04_SW04_25X_COORDS/SW04_25X_COORDS.pdsprj`: 25 `SWITCH` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.

## User Results

Pending.

## What Success Means

If every `SWITCH` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `SWITCH` is accepted for these counts.
