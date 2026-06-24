# Beautifier NPN Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `NPN`
- Donor: `proteus_ic\donors\main_mega_20260618\Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj`
- Donor inventory count: `600`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `4/8` -> (166771320, 133878320), `length_prefixed_text:Q1`
- `73/77` -> (166771320, 133497320), `length_prefixed_text:NPN`
- `145/149` -> (166771320, 133243320), `length_prefixed_text:NPN`
- `231/235` -> (166771320, 133243320), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `303/307` -> (166624000, 132588000), `marker_body:NPN`

## Test Files

- `00_Q00_NPN_1X_BASELINE_NO_BEAUTIFY/Q00_NPN_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `NPN` should open in the original donor-selected position.
- `01_Q01_NPN_1X_PARSED_COORDS/Q01_NPN_1X_PARSED_COORDS.pdsprj`: 1 `NPN` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_Q02_NPN_3X_PARSED_COORDS/Q02_NPN_3X_PARSED_COORDS.pdsprj`: 3 `NPN` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_Q03_NPN_5X_PARSED_COORDS/Q03_NPN_5X_PARSED_COORDS.pdsprj`: 5 `NPN` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `NPN` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `NPN` is accepted for these counts.
