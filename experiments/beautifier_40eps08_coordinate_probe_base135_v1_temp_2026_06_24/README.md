# Beautifier 40EPS08 Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `40EPS08`
- Donor: `proteus_ic\donors\manual_downloads_20260618\new_component_mega\new_components_5x_mega.pdsprj`
- Donor inventory count: `160`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (-27538680, -27919680), `length_prefixed_text:D73`
- `78/82` -> (-27538680, -28300680), `length_prefixed_text:40EPS08`
- `154/158` -> (-27538680, -28554680), `length_prefixed_text:40EPS08`
- `376/380` -> (-27940000, -28194000), `marker_body:40EPS08`

## Test Files

- `00_40EPS000_40EPS08_1X_BASELINE_NO_BEAUTIFY/40EPS000_40EPS08_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `40EPS08` should open in the original donor-selected position.
- `01_40EPS001_40EPS08_1X_PARSED_COORDS/40EPS001_40EPS08_1X_PARSED_COORDS.pdsprj`: 1 `40EPS08` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_40EPS002_40EPS08_3X_PARSED_COORDS/40EPS002_40EPS08_3X_PARSED_COORDS.pdsprj`: 3 `40EPS08` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_40EPS003_40EPS08_5X_PARSED_COORDS/40EPS003_40EPS08_5X_PARSED_COORDS.pdsprj`: 5 `40EPS08` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `40EPS08` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `40EPS08` is accepted for these counts.
