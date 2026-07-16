# Beautifier POT-HG Coordinate Probe

Generated on 2026-06-25.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `POT-HG`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `100`
- Probe variant: `solo`

## Parsed Coordinates Under Test

- `5/9` -> (4592330, 18308320), `linked_packet:POT-HG`
- `73/77` -> (4592330, 16743680), `linked_packet:POT-HG`
- `148/152` -> (4592330, 16489680), `linked_packet:POT-HG`
- `213/217` -> (4592330, 16489680), `linked_packet:POT-HG`
- `393/397` -> (4318000, 17526000), `linked_packet:POT-HG`

## Test Files

- `00_RV00_1X_BASELINE/RV00_1X_BASELINE.pdsprj`: Baseline control. One `POT-HG` should open in the original donor-selected position.
- `01_RV01_1X_COORDS/RV01_1X_COORDS.pdsprj`: 1 `POT-HG` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.
- `02_RV02_3X_COORDS/RV02_3X_COORDS.pdsprj`: 3 `POT-HG` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.
- `03_RV03_15X_COORDS/RV03_15X_COORDS.pdsprj`: 15 `POT-HG` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.
- `04_RV04_25X_COORDS/RV04_25X_COORDS.pdsprj`: 25 `POT-HG` components should move onto the beautifier grid. Check for DLL errors, bad object records, detached labels/values, or damaged controls. The requested visible controls should move as complete linked packets; the extra dummy control remains excluded from the user count.

## User Results

Pending.

## What Success Means

If every `POT-HG` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `POT-HG` is accepted for these counts.
