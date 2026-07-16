# Beautifier DIODE Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `DIODE`
- Donor: `proteus_ic\donors\main_mega_20260618\Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj`
- Donor inventory count: `600`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `4/8` -> (128249680, 138196320), `length_prefixed_text:D1`
- `75/79` -> (128249680, 137647680), `length_prefixed_text:DIODE`
- `149/153` -> (128249680, 137393680), `length_prefixed_text:DIODE`
- `342/346` -> (128270000, 137922000), `marker_body:DIODE`

## Test Files

- `00_D00_DIODE_1X_BASELINE_NO_BEAUTIFY/D00_DIODE_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `DIODE` should open in the original donor-selected position.
- `01_D01_DIODE_1X_PARSED_COORDS/D01_DIODE_1X_PARSED_COORDS.pdsprj`: 1 `DIODE` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_D02_DIODE_3X_PARSED_COORDS/D02_DIODE_3X_PARSED_COORDS.pdsprj`: 3 `DIODE` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_D03_DIODE_5X_PARSED_COORDS/D03_DIODE_5X_PARSED_COORDS.pdsprj`: 5 `DIODE` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `DIODE` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `DIODE` is accepted for these counts.
