# Beautifier FUSE Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `FUSE`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `145`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `70/74` -> (-6624320, -21026120), `length_prefixed_text:1A`
- `143/147` -> (-6624320, -21280120), `length_prefixed_text:FUSE`
- `231/235` -> (-6624320, -21280120), `length_prefixed_text:{MODFILE=FUSE}\n{R=0.1}`
- `304/308` -> (-6096000, -20828000), `marker_body:FUSE`

## Test Files

- `00_FU00_FUSE_1X_BASELINE_NO_BEAUTIFY/FU00_FUSE_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `FUSE` should open in the original donor-selected position.
- `01_FU01_FUSE_1X_PARSED_COORDS/FU01_FUSE_1X_PARSED_COORDS.pdsprj`: 1 `FUSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_FU02_FUSE_3X_PARSED_COORDS/FU02_FUSE_3X_PARSED_COORDS.pdsprj`: 3 `FUSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_FU03_FUSE_5X_PARSED_COORDS/FU03_FUSE_5X_PARSED_COORDS.pdsprj`: 5 `FUSE` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `FUSE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `FUSE` is accepted for these counts.
