# Beautifier CAP Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `CAP`
- Donor: `proteus_ic\donors\main_mega_20260618\Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj`
- Donor inventory count: `600`

## Parsed Coordinates Under Test

- `4/8` -> (163047680, 147340320), `length_prefixed_text:C1`
- `73/77` -> (163047680, 146791680), `length_prefixed_text:1nF`
- `145/149` -> (163047680, 146537680), `length_prefixed_text:CAP`
- `259/263` -> (163047680, 146537680), `length_prefixed_text:{PRIMITIVE=ANALOGUE,CAPACITOR}\n`
- `331/335` -> (163322000, 147066000), `marker_body:CAP`

## Test Files

- `00_C00_CAP_1X_BASELINE_NO_BEAUTIFY/C00_CAP_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `CAP` should open in the original donor-selected position.
- `01_C01_CAP_1X_PARSED_COORDS/C01_CAP_1X_PARSED_COORDS.pdsprj`: 1 `CAP` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_C02_CAP_3X_PARSED_COORDS/C02_CAP_3X_PARSED_COORDS.pdsprj`: 3 `CAP` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_C03_CAP_5X_PARSED_COORDS/C03_CAP_5X_PARSED_COORDS.pdsprj`: 5 `CAP` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Accepted. User reported the CAP baseline and 1/3/5 parsed-coordinate cases work.

## What Success Means

If every `CAP` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `CAP` is accepted for these counts.
