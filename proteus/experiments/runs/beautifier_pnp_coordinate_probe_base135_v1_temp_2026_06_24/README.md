# Beautifier PNP Coordinate Probe

Generated on 2026-06-24.

This pack uses the reusable passive-family beautifier probe harness.
It keeps the accepted parsed-coordinate method and avoids creating one-off scripts per component.

## Family

- Family under test: `PNP`
- Donor: `proteus_ic\donors\main_mega_20260618\Mega_7segan7segcom74hc0074hc02hc04hc08hc32hc74hc76hc85hc86hc151hc157hc160hc174hc174hc192hc266hc283_4027_4511_7447_7490capcapelecdiodelm741ne555npnpnprealindresistor.pdsprj`
- Donor inventory count: `600`
- Probe variant: `base135`

## Parsed Coordinates Under Test

- `5/9` -> (144165320, 130322320), `length_prefixed_text:Q21`
- `74/78` -> (144165320, 129941320), `length_prefixed_text:PNP`
- `146/150` -> (144165320, 129687320), `length_prefixed_text:PNP`
- `232/236` -> (144165320, 129687320), `length_prefixed_text:{PRIMITIVE=ANALOGUE}`
- `304/308` -> (144018000, 129032000), `marker_body:PNP`

## Test Files

- `00_QP00_PNP_1X_BASELINE_NO_BEAUTIFY/QP00_PNP_1X_BASELINE_NO_BEAUTIFY.pdsprj`: Baseline control. One `PNP` should open in the original donor-selected position.
- `01_QP01_PNP_1X_PARSED_COORDS/QP01_PNP_1X_PARSED_COORDS.pdsprj`: 1 `PNP` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `02_QP02_PNP_3X_PARSED_COORDS/QP02_PNP_3X_PARSED_COORDS.pdsprj`: 3 `PNP` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.
- `03_QP03_PNP_5X_PARSED_COORDS/QP03_PNP_5X_PARSED_COORDS.pdsprj`: 5 `PNP` components should move onto the beautifier grid. Check for DLL errors, bad object records, and detached labels/values.

## User Results

Pending.

## What Success Means

If every `PNP` case opens without DLL errors and labels/values stay attached,
coordinate beautification for `PNP` is accepted for these counts.
